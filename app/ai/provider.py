"""AI provider abstraction (TZ section 2.10 / 2.11).

Three interchangeable providers:

  * **stub**      — default, no API key required. Produces *extractive*
                    summaries and grounded answers straight from the document
                    text, so AI features work out of the box.
  * **anthropic** — Claude via the Messages API (httpx; no SDK dependency).
  * **openai**    — GPT via the Chat Completions API.

Selection is driven by ``settings.ai_provider`` + ``settings.ai_api_key``.
Every provider implements ``summarize`` and ``answer`` with the same signature,
so the rest of the platform never branches on the provider.
"""
from __future__ import annotations

import re
from collections import Counter

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("udip.ai.provider")

# Minimal Uzbek + English stopword set for extractive scoring.
_STOP = {
    "va", "bilan", "uchun", "bu", "shu", "ham", "yoki", "lekin", "ammo", "agar",
    "edi", "bo", "boldi", "qilish", "kerak", "men", "siz", "ular", "biz", "u",
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "to", "of",
    "in", "on", "for", "with", "as", "by", "at", "it", "this", "that", "be",
}
_SENT_RE = re.compile(r"(?<=[.!?。])\s+")
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_RE.split(text) if len(s.strip()) > 15]


class BaseProvider:
    name = "base"

    def summarize(self, text: str, *, max_sentences: int = 5) -> str:  # pragma: no cover
        raise NotImplementedError

    def answer(self, question: str, contexts: list[str]) -> str:  # pragma: no cover
        raise NotImplementedError


class StubProvider(BaseProvider):
    """Dependency-free extractive AI: real, grounded output without an LLM."""

    name = "stub"

    def summarize(self, text: str, *, max_sentences: int = 5) -> str:
        sents = _sentences(text)
        if len(sents) <= max_sentences:
            return " ".join(sents)
        words = [w for w in _WORD_RE.findall(text.lower()) if w not in _STOP and len(w) > 2]
        freq = Counter(words)
        scored = []
        for i, s in enumerate(sents):
            sw = _WORD_RE.findall(s.lower())
            score = sum(freq[w] for w in sw) / (len(sw) + 1)
            scored.append((score, i, s))
        top = sorted(scored, reverse=True)[:max_sentences]
        return " ".join(s for _, _, s in sorted(top, key=lambda x: x[1]))

    def answer(self, question: str, contexts: list[str]) -> str:
        if not contexts:
            return "Hujjatda bu savolga oid ma'lumot topilmadi."
        # Pick the context chunk most lexically similar to the question.
        q_words = {w for w in _WORD_RE.findall(question.lower()) if w not in _STOP}
        best = max(
            contexts,
            key=lambda c: len(q_words & set(_WORD_RE.findall(c.lower()))),
        )
        return "Hujjatga asoslangan javob: " + best.strip()


class _HttpLLMProvider(BaseProvider):
    """Shared helper for HTTP-based LLM providers."""

    def _post(self, url: str, headers: dict, payload: dict) -> str:  # pragma: no cover
        import httpx

        with httpx.Client(timeout=60) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()


class AnthropicProvider(_HttpLLMProvider):
    name = "anthropic"

    def _chat(self, system: str, user: str) -> str:  # pragma: no cover - needs API key
        data = self._post(
            "https://api.anthropic.com/v1/messages",
            {
                "x-api-key": settings.ai_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            {
                "model": settings.ai_model,
                "max_tokens": 1024,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        return "".join(b.get("text", "") for b in data.get("content", []))

    def summarize(self, text: str, *, max_sentences: int = 5) -> str:  # pragma: no cover
        return self._chat(
            "Siz hujjatlarni xulosalovchi yordamchisiz. Qisqa, aniq xulosa bering.",
            f"Quyidagi hujjatni {max_sentences} gapda xulosala:\n\n{text[:12000]}",
        )

    def answer(self, question: str, contexts: list[str]) -> str:  # pragma: no cover
        ctx = "\n---\n".join(contexts)
        return self._chat(
            "Faqat berilgan kontekstga asoslanib javob bering. Bilmasangiz, "
            "'Hujjatda topilmadi' deng.",
            f"Kontekst:\n{ctx}\n\nSavol: {question}",
        )


class OpenAIProvider(_HttpLLMProvider):
    name = "openai"

    def _chat(self, system: str, user: str) -> str:  # pragma: no cover - needs API key
        data = self._post(
            "https://api.openai.com/v1/chat/completions",
            {"Authorization": f"Bearer {settings.ai_api_key}", "content-type": "application/json"},
            {
                "model": settings.ai_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        return data["choices"][0]["message"]["content"]

    def summarize(self, text: str, *, max_sentences: int = 5) -> str:  # pragma: no cover
        return self._chat(
            "You summarise documents concisely.",
            f"Summarise in {max_sentences} sentences:\n\n{text[:12000]}",
        )

    def answer(self, question: str, contexts: list[str]) -> str:  # pragma: no cover
        ctx = "\n---\n".join(contexts)
        return self._chat(
            "Answer only from the given context; if unknown, say so.",
            f"Context:\n{ctx}\n\nQuestion: {question}",
        )


def get_provider() -> BaseProvider:
    """Return the configured provider, falling back to the stub."""
    if settings.ai_provider == "anthropic" and settings.ai_api_key:
        return AnthropicProvider()
    if settings.ai_provider == "openai" and settings.ai_api_key:
        return OpenAIProvider()
    return StubProvider()
