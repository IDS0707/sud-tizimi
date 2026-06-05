/* UDIP admin panel — simple system-status dashboard (no API key needed). */
"use strict";

const API = "/api/v1";
const $ = (s) => document.querySelector(s);
const esc = (s) => (s ?? "").toString().replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function toast(msg, kind = "") {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show " + kind;
  setTimeout(() => (t.className = "toast"), 2800);
}

// SVG icons (stroke, inherit color)
const IC = {
  doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
  pages: '<rect x="4" y="3" width="13" height="16" rx="2"/><path d="M9 7h6M9 11h6M9 15h4"/>',
  ocr: '<rect x="3" y="4" width="18" height="14" rx="2"/><path d="M7 9h2M7 13h6M15 9h2"/>',
  tag: '<path d="M20.6 13.4 12 22l-9-9V4h9z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
  ai: '<path d="M12 3l1.7 5.3 5.3 1.7-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7z"/>',
  disk: '<path d="M5 4h11l3 3v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/><path d="M8 4v5h6V4M8 14h8"/>',
};

// Cards to show (curated — only the meaningful, easy-to-understand ones)
const CARDS = [
  { key: "documents",   icon: "doc",   label: "Yuklangan hujjatlar", desc: "Jami fayllar" },
  { key: "pages",       icon: "pages", label: "Sahifalar",           desc: "Barcha sahifalar soni" },
  { key: "ocr_results", icon: "ocr",   label: "OCR o'qilgan",        desc: "Rasm/skandan matn olingan" },
  { key: "entities",    icon: "tag",   label: "Topilgan ma'lumotlar", desc: "Sana, summa, telefon…" },
  { key: "ai_results",  icon: "ai",    label: "AI tahlillari",       desc: "Xulosa va javoblar" },
  { key: "storage",     icon: "disk",  label: "Saqlangan hajm",      desc: "Megabaytda" },
];

const STATUS_LABELS = {
  uploaded: "Yuklandi", processing: "Ishlanmoqda", parsed: "Tahlil qilindi",
  ocr_done: "OCR tayyor", indexed: "Indekslandi", failed: "Xato",
};
const TYPE_LABELS = {
  png: "Rasm (PNG)", jpg: "Rasm (JPG)", jpeg: "Rasm (JPEG)", webp: "Rasm (WEBP)",
  pdf: "PDF", docx: "Word", xlsx: "Excel", pptx: "PowerPoint", txt: "Matn", rtf: "RTF",
};

function bars(container, obj, labels) {
  const el = $(container);
  const entries = Object.entries(obj || {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    el.innerHTML = '<p class="muted">Hali ma\'lumot yo\'q — fayl yuklang.</p>';
    return;
  }
  const max = Math.max(...entries.map(([, v]) => v), 1);
  el.innerHTML = entries.map(([k, v]) => `
    <div class="bar-row">
      <span class="name">${esc(labels[k] || k)}</span>
      <div class="bar-track"><div class="bar" style="width:${Math.max(4, (v / max) * 100)}%"></div></div>
      <span class="bar-val">${v}</span>
    </div>`).join("");
}

async function loadDashboard() {
  try {
    const res = await fetch(API + "/admin/overview");
    if (!res.ok) throw new Error("Server javob bermadi (" + res.status + ")");
    const s = await res.json();

    const val = (c) => c.key === "storage"
      ? (((s.total_storage_bytes || 0) / 1048576).toFixed(1))
      : (s[c.key] ?? 0);

    $("#stat-cards").innerHTML = CARDS.map((c) => `
      <div class="card">
        <div class="ic"><svg viewBox="0 0 24 24">${IC[c.icon]}</svg></div>
        <div>
          <div class="num">${val(c)}</div>
          <div class="lbl">${c.label}</div>
          <div class="desc">${c.desc}</div>
        </div>
      </div>`).join("");

    bars("#type-bars", s.documents_by_type, TYPE_LABELS);
    bars("#status-bars", s.documents_by_status, STATUS_LABELS);

    $("#loading").style.display = "none";
    $("#stat-cards").style.display = "grid";
    $("#type-section").style.display = "block";
    $("#status-section").style.display = "block";
    await loadRecent();
  } catch (e) {
    $("#loading").textContent = "Ma'lumotni yuklab bo'lmadi: " + e.message;
    toast("Xato: " + e.message, "err");
  }
}

const COURT_TYPES = {
  ariza: "Ariza", qaror: "Sud qarori", bayonnoma: "Bayonnoma",
  dalil: "Dalil", shartnoma: "Shartnoma", hisobot: "Hisobot", boshqa: "Boshqa",
};

async function loadRecent() {
  try {
    const res = await fetch(API + "/documents?limit=8");
    const docs = await res.json();
    const tb = $("#recent-list");
    tb.innerHTML = docs.length
      ? docs.map((d) => `
          <tr>
            <td>${esc(d.filename)}</td>
            <td>${d.doc_type ? `<span class="t-chip">${esc(COURT_TYPES[d.doc_type] || d.doc_type)}</span>` : "—"}</td>
            <td>${d.case_number ? esc(d.case_number) : "—"}</td>
            <td>${esc(STATUS_LABELS[d.status] || d.status)}</td>
          </tr>`).join("")
      : '<tr><td colspan="4" class="muted">Hali hujjat yo\'q.</td></tr>';
    $("#recent-section").style.display = "block";
  } catch (_) { /* recent is optional */ }
}

// ====================== API keys drawer (edge icon) ======================
const KEY_STORE = "udip_api_key";
const getKey = () => localStorage.getItem(KEY_STORE) || "";

function openDrawer() {
  $("#keys-drawer").classList.add("show");
  $("#drawer-overlay").classList.add("show");
  if (getKey()) { $("#apikey-input").value = getKey(); loadKeys(); }
}
function closeDrawer() {
  $("#keys-drawer").classList.remove("show");
  $("#drawer-overlay").classList.remove("show");
}

async function keyApi(path, opts = {}) {
  opts.headers = Object.assign({ "X-API-Key": getKey() }, opts.headers || {});
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    let d = res.statusText;
    try { d = (await res.json()).detail || d; } catch (_) {}
    const e = new Error(d); e.status = res.status; throw e;
  }
  return res.headers.get("content-type")?.includes("json") ? res.json() : res;
}

async function createKey() {
  const name = $("#newkey-name").value.trim() || "Nomsiz kalit";
  try {
    const r = await keyApi("/keys", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    $("#raw-key-box").innerHTML =
      `<div class="raw-key"><b>Kalit yaratildi</b> — saqlab qo'ying (faqat bir marta ko'rsatiladi):` +
      `<br><strong>${esc(r.api_key)}</strong></div>`;
    localStorage.setItem(KEY_STORE, r.api_key);
    $("#apikey-input").value = r.api_key;
    $("#newkey-name").value = "";
    toast("Kalit yaratildi", "ok");
    loadKeys();
  } catch (e) { toast("Xato: " + e.message, "err"); }
}

function showKeys() {
  const v = $("#apikey-input").value.trim();
  if (!v) return toast("Kalit kiriting", "err");
  localStorage.setItem(KEY_STORE, v);
  loadKeys();
}

async function loadKeys() {
  const box = $("#keys-list");
  if (!getKey()) { box.innerHTML = ""; return; }
  try {
    const keys = await keyApi("/keys");
    if (!keys.length) { box.innerHTML = '<p class="muted">Hali kalit yo\'q.</p>'; return; }
    box.innerHTML = keys.map((k) => `
      <div class="kl-item">
        <div>
          <div class="kl-name">${esc(k.name)}</div>
          <div class="kl-prefix">${esc(k.key_prefix)}…</div>
        </div>
        <div>${k.is_active
          ? `<span class="badge badge-green">Faol</span> <button class="btn btn-ghost btn-sm" onclick="revokeKey(${k.id})">Bekor</button>`
          : '<span class="badge badge-red">Bekor</span>'}</div>
      </div>`).join("");
  } catch (e) {
    box.innerHTML = `<p class="muted">Kalitlar ko'rinmadi: ${esc(e.message)}</p>`;
  }
}

async function revokeKey(id) {
  if (!confirm("Bu kalitni bekor qilasizmi?")) return;
  try {
    await keyApi(`/keys/${id}`, { method: "DELETE" });
    toast("Kalit bekor qilindi", "ok");
    loadKeys();
  } catch (e) { toast("Xato: " + e.message, "err"); }
}
window.revokeKey = revokeKey;  // inline onclick uchun global

// ====================== OCR provider settings ======================
const ENGINE_LABEL = { gemini: "Gemini AI", tesseract: "Mahalliy (Tesseract)", stub: "—" };

function updateProvUI() {
  const checked = document.querySelector('input[name="prov"]:checked');
  document.querySelectorAll(".prov").forEach((p) =>
    p.classList.toggle("active", p.querySelector("input").checked));
  $("#gemini-fields").style.display = (checked && checked.value === "gemini") ? "block" : "none";
}

async function loadOcrConfig() {
  try {
    const c = await (await fetch(API + "/admin/ocr-config")).json();
    $("#ocr-active").textContent = ENGINE_LABEL[c.active_engine] || c.active_engine;
    const radio = document.querySelector(`input[name="prov"][value="${c.ocr_provider}"]`);
    if (radio) radio.checked = true;
    $("#gemini-model").value = c.gemini_model || "gemini-2.5-flash";
    if (c.has_key) $("#gemini-key").placeholder = "•••• saqlangan — almashtirish uchun yangisini kiriting";
    updateProvUI();
  } catch (_) {}
}

function _ocrBody() {
  const body = { gemini_model: $("#gemini-model").value.trim() || "gemini-2.5-flash" };
  const key = $("#gemini-key").value.trim();
  if (key) body.gemini_api_key = key;
  return body;
}

async function saveOcrConfig() {
  const provider = (document.querySelector('input[name="prov"]:checked') || {}).value || "tesseract";
  const body = Object.assign({ ocr_provider: provider }, _ocrBody());
  try {
    await fetch(API + "/admin/ocr-config", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    toast("OCR sozlamasi saqlandi", "ok");
    $("#gemini-key").value = "";
    loadOcrConfig();
  } catch (e) { toast("Xato: " + e.message, "err"); }
}

async function testOcrConfig() {
  const st = $("#ocr-status");
  st.className = "ocr-status"; st.textContent = "Tekshirilmoqda…";
  try {
    const r = await (await fetch(API + "/admin/ocr-config/test", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(_ocrBody()),
    })).json();
    st.className = "ocr-status " + (r.ok ? "ok" : "err");
    st.textContent = r.message;
  } catch (e) { st.className = "ocr-status err"; st.textContent = "Xato: " + e.message; }
}

document.addEventListener("DOMContentLoaded", () => {
  loadDashboard();
  loadOcrConfig();
  document.querySelectorAll('input[name="prov"]').forEach((r) => (r.onchange = updateProvUI));
  $("#ocr-save").onclick = saveOcrConfig;
  $("#ocr-test").onclick = testOcrConfig;
  $("#keys-fab").onclick = openDrawer;
  $("#drawer-close").onclick = closeDrawer;
  $("#drawer-overlay").onclick = closeDrawer;
  $("#btn-create-key").onclick = createKey;
  $("#btn-show-keys").onclick = showKeys;
});
