/* ====================================================================
   UDIP web client — talks to the FastAPI backend (TZ section 7)
   Vanilla JS, no build step. Served at "/" by FastAPI.
   ==================================================================== */
"use strict";

const API = "/api/v1";

// ---- tiny helpers --------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};
const esc = (s) => (s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const FILE_ICONS = {
  pdf: "📕", docx: "📘", xlsx: "📗", pptx: "📙",
  txt: "📄", rtf: "📄", jpg: "🖼️", jpeg: "🖼️", png: "🖼️", webp: "🖼️",
};
const STATUS_BADGE = {
  uploaded: ["badge-muted", "Yuklandi"],
  processing: ["badge-amber", "Ishlanmoqda"],
  parsed: ["badge-blue", "Tahlil qilindi"],
  ocr_done: ["badge-green", "OCR tayyor"],
  indexed: ["badge-green", "Indekslandi"],
  failed: ["badge-red", "Xato"],
};

let state = { docs: [], active: null, activeDoc: null, activeText: "" };

function toast(msg, kind = "") {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show " + kind;
  setTimeout(() => (t.className = "toast"), 2800);
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}

// ---- file list (left panel) ---------------------------------------
async function loadDocuments() {
  try {
    state.docs = await api("/documents");
    renderFileList();
  } catch (e) {
    toast("Hujjatlarni yuklab bo'lmadi: " + e.message, "err");
  }
}

function renderFileList() {
  const list = $("#file-list");
  list.innerHTML = "";
  if (!state.docs.length) {
    list.appendChild(el("li", "hint", "Hali hujjat yo'q. Yuqoridan fayl yuklang."));
    return;
  }
  for (const d of state.docs) {
    const [badgeCls, badgeTxt] = STATUS_BADGE[d.status] || ["badge-muted", d.status];
    const li = el("li", "file-item" + (state.active === d.public_id ? " active" : ""));
    li.dataset.id = d.public_id;
    li.innerHTML = `
      <span class="file-ico">${FILE_ICONS[d.file_type] || "📄"}</span>
      <div class="file-info">
        <div class="file-name" title="${esc(d.filename)}">${esc(d.filename)}</div>
        <div class="file-sub">${d.page_count} sahifa · ${(d.size_bytes/1024).toFixed(0)} KB</div>
      </div>
      <span class="badge ${badgeCls}">${badgeTxt}</span>
      <button class="file-del" title="O'chirish">✕</button>`;
    li.onclick = () => selectDocument(d.public_id);
    li.querySelector(".file-del").onclick = (e) => {
      e.stopPropagation();
      deleteDocument(d.public_id, d.filename);
    };
    list.appendChild(li);
  }
}

async function deleteDocument(publicId, name) {
  if (!confirm(`"${name}" o'chirilsinmi? Bu amalni qaytarib bo'lmaydi.`)) return;
  try {
    await api(`/documents/${publicId}`, { method: "DELETE" });
    toast("O'chirildi: " + name, "ok");
    if (state.active === publicId) {
      state.active = null;
      state.activeDoc = null;
      state.activeText = "";
      $("#viewer").innerHTML =
        '<div class="empty-state"><div class="empty-icon">🗂️</div>' +
        '<p>Hujjat tanlang yoki yangi fayl yuklang.</p></div>';
      $("#viewer-title").textContent = "Ko'rish";
      $("#viewer-meta").textContent = "";
      $("#text-output").innerHTML = "";
      $("#text-info").textContent = "Chapdan hujjat tanlang.";
    }
    await loadDocuments();
  } catch (e) {
    toast("O'chirishda xato: " + e.message, "err");
  }
}

// ---- viewer (center) ----------------------------------------------
async function selectDocument(publicId) {
  state.active = publicId;
  renderFileList();
  const viewer = $("#viewer");
  viewer.innerHTML = '<div class="empty-state"><span class="spinner"></span></div>';
  try {
    const doc = await api(`/documents/${publicId}`);
    state.activeDoc = doc;
    $("#viewer-title").textContent = doc.filename;
    $("#viewer-meta").textContent =
      `${doc.file_type.toUpperCase()} · ${doc.page_count} sahifa · ${doc.status}`;
    renderViewer(doc);
    renderTextTab(doc);
    renderMetaTab(doc);
    resetAiTab();
    switchTab("text");   // hujjat tanlanganda matnni ko'rsatamiz
  } catch (e) {
    viewer.innerHTML = `<div class="empty-state"><p>Xato: ${esc(e.message)}</p></div>`;
  }
}

function renderViewer(doc) {
  const viewer = $("#viewer");
  const fileUrl = `${API}/documents/${doc.public_id}/file`;
  const cat = doc.category;

  if (cat === "image") {
    // Image + its extracted (OCR) text right below — always visible,
    // even if the right results panel is hidden on narrow screens.
    const text = (doc.pages || []).map((p) => p.text || "").join("\n").trim();
    const body = text
      ? esc(text).replace(/\n/g, "<br>")
      : `<span class="muted">Matn topilmadi. Skan/rasm OCR mexanizmi kerak ` +
        `(Tesseract/PaddleOCR o'rnatilgan bo'lsa avtomatik o'qiydi).</span>`;
    viewer.innerHTML =
      `<img src="${fileUrl}" alt="${esc(doc.filename)}" />` +
      `<div class="viewer-text">` +
      `<div class="viewer-text-head">📄 Rasmdan o'qilgan matn (OCR)` +
      (text ? ` <span class="muted">— ${text.length} belgi</span>` : "") + `</div>` +
      `<div class="viewer-text-body">${body}</div></div>`;
  } else if (doc.file_type === "pdf") {
    viewer.innerHTML = `<iframe src="${fileUrl}#view=fitH" title="PDF"></iframe>`;
  } else if (doc.pages && doc.pages.length) {
    // Text-based formats (docx/xlsx/pptx/txt/...): render structured blocks.
    viewer.innerHTML = "";
    for (const p of doc.pages) {
      const block = el("div", "page-block");
      block.appendChild(el("div", "page-num", `Sahifa ${p.page_number}`));
      block.appendChild(renderBlocks(p));
      viewer.appendChild(block);
    }
  } else {
    viewer.innerHTML = `<div class="empty-state"><p>Ko'rish uchun mazmun yo'q.</p>
      <a class="btn btn-ghost" href="${fileUrl}" target="_blank">Faylni ochish</a></div>`;
  }
}

function renderBlocks(page) {
  // Render structured layout blocks if present, else fall back to plain text.
  const wrap = el("div");
  const blocks = page.layout && page.layout.blocks;
  if (!blocks || !blocks.length) {
    wrap.innerHTML = esc(page.text || "(matn yo'q)").replace(/\n/g, "<br>");
    return wrap;
  }
  for (const b of blocks) {
    if (b.type === "heading") {
      const h = el("h3"); h.style.margin = "12px 0 6px"; h.textContent = b.text;
      wrap.appendChild(h);
    } else if (b.type === "table" && b.rows) {
      wrap.appendChild(renderTable(b.rows));
    } else if (b.type === "notes") {
      const n = el("div"); n.style.cssText = "color:#64748b;font-style:italic;margin:8px 0";
      n.textContent = "Izoh: " + b.text; wrap.appendChild(n);
    } else if (b.text) {
      const p = el("p"); p.style.margin = "4px 0"; p.textContent = b.text;
      wrap.appendChild(p);
    }
  }
  return wrap;
}

function renderTable(rows) {
  const t = el("table");
  t.style.cssText = "border-collapse:collapse;margin:8px 0;width:100%;font-size:13px";
  rows.forEach((row, i) => {
    const tr = el("tr");
    row.forEach((cell) => {
      const td = el(i === 0 ? "th" : "td");
      td.textContent = cell;
      td.style.cssText = "border:1px solid #e2e8f0;padding:5px 8px;text-align:left" +
        (i === 0 ? ";background:#f8fafc;font-weight:600" : "");
      tr.appendChild(td);
    });
    t.appendChild(tr);
  });
  return t;
}

function renderTextTab(doc) {
  const box = $("#text-output");
  const info = $("#text-info");
  const withText = (doc.pages || []).filter((p) => (p.text || "").trim().length);
  const fullText = (doc.pages || []).map((p) => p.text || "").join("\n\n").trim();
  state.activeText = fullText;

  if (!withText.length) {
    const isImage = doc.category === "image" || doc.file_type === "pdf";
    info.textContent = "Matn topilmadi";
    box.innerHTML = `<p class="hint">Bu hujjatdan matn ajratilmadi.` +
      (isImage ? " Skan/rasm bo'lsa OCR mexanizmi kerak (Tesseract/PaddleOCR)." : "") +
      `</p>`;
    return;
  }

  info.textContent = `${doc.page_count} sahifa · ${fullText.length.toLocaleString()} belgi`;
  box.innerHTML = "";
  for (const p of doc.pages) {
    if (!(p.text || "").trim()) continue;
    const block = el("div", "text-page");
    block.innerHTML =
      `<div class="text-page-num">Sahifa ${p.page_number}</div>` +
      `<div class="text-page-body">${esc(p.text)}</div>`;
    box.appendChild(block);
  }
}

function copyActiveText() {
  if (!state.activeText) { toast("Nusxalanadigan matn yo'q", "err"); return; }
  navigator.clipboard.writeText(state.activeText)
    .then(() => toast("Matn nusxalandi ✓", "ok"))
    .catch(() => toast("Nusxalab bo'lmadi (brauzer ruxsati)", "err"));
}

function renderMetaTab(doc) {
  const grid = $("#meta-results");
  const rows = {
    "Fayl nomi": doc.filename,
    "Turi": doc.file_type.toUpperCase(),
    "Toifa": doc.category,
    "MIME": doc.mime_type || "—",
    "Hajmi": `${(doc.size_bytes / 1024).toFixed(1)} KB`,
    "Sahifalar": doc.page_count,
    "Holati": doc.status,
    "ID": doc.public_id,
  };
  grid.innerHTML = "";
  for (const [k, v] of Object.entries(rows)) {
    grid.appendChild(el("div", "meta-row", `<span class="k">${k}</span><span class="v">${esc(String(v))}</span>`));
  }
  if (doc.doc_metadata) {
    for (const [k, v] of Object.entries(doc.doc_metadata)) {
      if (v == null || v === "") continue;
      grid.appendChild(el("div", "meta-row",
        `<span class="k">${esc(k)}</span><span class="v">${esc(String(v))}</span>`));
    }
  }
}

// ---- upload --------------------------------------------------------
async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  toast(`"${file.name}" yuklanmoqda…`);
  try {
    const res = await api("/upload", { method: "POST", body: fd });
    toast("Yuklandi: " + file.name, "ok");
    await loadDocuments();
    selectDocument(res.document.public_id);
  } catch (e) {
    toast("Yuklashda xato: " + e.message, "err");
  }
}

// ---- search (top bar, always visible — TZ 4.4) ---------------------
async function doSearch(query) {
  const list = $("#search-results");
  switchTab("search");
  if (!query.trim()) { list.innerHTML = ""; return; }
  list.innerHTML = '<li class="hint"><span class="spinner"></span> Qidirilmoqda…</li>';
  try {
    const data = await api("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit: 30 }),
    });
    renderSearchResults(data.results || [], query);
  } catch (e) {
    if (e.status === 404) {
      list.innerHTML = '<li class="hint">🔎 Aqlli qidiruv V4 bosqichida ulanadi.</li>';
    } else {
      list.innerHTML = `<li class="hint">Xato: ${esc(e.message)}</li>`;
    }
  }
}

function renderSearchResults(results, query) {
  const list = $("#search-results");
  if (!results.length) {
    list.innerHTML = `<li class="hint">"${esc(query)}" bo'yicha natija topilmadi.</li>`;
    return;
  }
  list.innerHTML = "";
  for (const r of results) {
    const li = el("li", "result-item");
    li.innerHTML = `
      <div class="result-doc">${esc(r.filename || "Hujjat")}</div>
      <div class="result-ctx">${r.snippet || esc(r.context || "")}</div>
      <div class="result-page">Sahifa ${r.page_number ?? "—"}</div>`;
    if (r.public_id) li.onclick = () => selectDocument(r.public_id);
    list.appendChild(li);
  }
}

// ---- AI: summary, entities, chat, export (V5) ----------------------
function resetAiTab() {
  $("#ai-summary").innerHTML = "";
  $("#ai-entities").innerHTML = "";
  $("#chat-log").innerHTML = "";
}

function _needDoc() {
  if (!state.activeDoc) { toast("Avval hujjat tanlang", "err"); return null; }
  return state.activeDoc;
}

async function doSummary() {
  const doc = _needDoc(); if (!doc) return;
  const box = $("#ai-summary");
  box.innerHTML = '<span class="spinner"></span> Xulosa tayyorlanmoqda…';
  try {
    const r = await api("/ai/summarize", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_id: doc.id, max_sentences: 5 }),
    });
    box.innerHTML = `<strong>Xulosa (${esc(r.model)}):</strong><br>${esc(r.summary) || "—"}`;
  } catch (e) { box.innerHTML = `<span class="hint">Xato: ${esc(e.message)}</span>`; }
}

async function doEntities() {
  const doc = _needDoc(); if (!doc) return;
  const box = $("#ai-entities");
  box.innerHTML = '<span class="spinner"></span> Ajratilmoqda…';
  try {
    const r = await api(`/ai/entities/${doc.id}`, { method: "POST" });
    if (!r.count) { box.innerHTML = '<span class="hint">Muhim ma\'lumot topilmadi.</span>'; return; }
    const labels = { date: "sana", money: "summa", email: "email", phone: "tel", percent: "%" };
    box.innerHTML = `<strong>${r.count} ta topildi:</strong><br>` + r.entities.map((e) =>
      `<span class="entity-chip"><span class="et">${labels[e.entity_type] || e.entity_type}</span>${esc(e.value)}</span>`
    ).join("");
  } catch (e) { box.innerHTML = `<span class="hint">Xato: ${esc(e.message)}</span>`; }
}

async function doChat(question) {
  const doc = _needDoc(); if (!doc) return;
  const logEl = $("#chat-log");
  const entry = el("div", "chat-msg");
  entry.innerHTML = `<div class="chat-q">❓ ${esc(question)}</div>
    <div class="chat-a"><span class="spinner"></span></div>`;
  logEl.appendChild(entry);
  logEl.scrollTop = logEl.scrollHeight;
  try {
    const r = await api("/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, document_id: doc.id }),
    });
    const src = (r.sources || []).map((s) => `s.${s.page_number ?? "—"}`).join(", ");
    entry.querySelector(".chat-a").innerHTML =
      `💡 ${esc(r.answer)}` + (src ? `<div class="chat-src">Manba: ${src}</div>` : "");
  } catch (e) {
    entry.querySelector(".chat-a").innerHTML = `<span class="hint">Xato: ${esc(e.message)}</span>`;
  }
  logEl.scrollTop = logEl.scrollHeight;
}

async function doExport(fmt) {
  const doc = _needDoc(); if (!doc) return;
  toast(`${fmt.toUpperCase()} eksport qilinmoqda…`);
  try {
    const r = await api("/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_id: doc.id, format: fmt }),
    });
    toast("Eksport tayyor: " + r.filename, "ok");
    window.open(r.download_url, "_blank");
  } catch (e) { toast("Eksport xatosi: " + e.message, "err"); }
}

// ---- tabs ----------------------------------------------------------
function switchTab(name) {
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $$(".tab-pane").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));
}

// ---- engine badge --------------------------------------------------
async function loadEngineStatus() {
  try {
    const { real_engine } = await api("/ocr/engine");
    const b = $("#engine-badge");
    b.textContent = real_engine ? "OCR: faol" : "OCR: stub";
    b.className = "badge " + (real_engine ? "badge-green" : "badge-amber");
  } catch (_) {}
}

// ---- wiring --------------------------------------------------------
function init() {
  $("#upload-btn").onclick = () => $("#file-input").click();
  $("#file-input").onchange = (e) => { if (e.target.files[0]) uploadFile(e.target.files[0]); e.target.value = ""; };

  const dz = $("#dropzone");
  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("dragover"); }));
  dz.addEventListener("drop", (e) => { if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]); });

  $("#search-form").onsubmit = (e) => { e.preventDefault(); doSearch($("#search-input").value); };
  $$(".tab").forEach((t) => (t.onclick = () => switchTab(t.dataset.tab)));

  // Matn tab
  $("#btn-copy-text").onclick = copyActiveText;

  // AI tab (V5)
  $("#btn-summary").onclick = doSummary;
  $("#btn-entities").onclick = doEntities;
  $("#chat-form").onsubmit = (e) => {
    e.preventDefault();
    const q = $("#chat-input").value.trim();
    if (q) { doChat(q); $("#chat-input").value = ""; }
  };
  $$(".export-btn").forEach((b) => (b.onclick = () => doExport(b.dataset.fmt)));

  loadDocuments();
  loadEngineStatus();
}

document.addEventListener("DOMContentLoaded", init);
