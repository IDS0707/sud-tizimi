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

let state = { docs: [], active: null };

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
      <span class="badge ${badgeCls}">${badgeTxt}</span>`;
    li.onclick = () => selectDocument(d.public_id);
    list.appendChild(li);
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
    $("#viewer-title").textContent = doc.filename;
    $("#viewer-meta").textContent =
      `${doc.file_type.toUpperCase()} · ${doc.page_count} sahifa · ${doc.status}`;
    renderViewer(doc);
    renderOcrTab(doc);
    renderMetaTab(doc);
  } catch (e) {
    viewer.innerHTML = `<div class="empty-state"><p>Xato: ${esc(e.message)}</p></div>`;
  }
}

function renderViewer(doc) {
  const viewer = $("#viewer");
  const fileUrl = `${API}/documents/${doc.public_id}/file`;
  const cat = doc.category;

  if (cat === "image") {
    viewer.innerHTML = `<img src="${fileUrl}" alt="${esc(doc.filename)}" />`;
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

function renderOcrTab(doc) {
  const box = $("#ocr-results");
  const scanned = (doc.pages || []).filter((p) => (p.text || "").trim().length);
  if (!scanned.length) {
    box.innerHTML = '<p class="hint">Bu hujjatda OCR/matn natijasi topilmadi.</p>';
    return;
  }
  box.innerHTML = "";
  for (const p of doc.pages) {
    if (!(p.text || "").trim()) continue;
    const b = el("div", "ocr-box");
    b.innerHTML = `<div class="ocr-box-head"><span>Sahifa ${p.page_number}</span></div>
      <div class="ocr-box-text">${esc(p.text)}</div>`;
    box.appendChild(b);
  }
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

  loadDocuments();
  loadEngineStatus();
}

document.addEventListener("DOMContentLoaded", init);
