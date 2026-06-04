/* UDIP admin panel client (TZ section 6: boshqaruv paneli) */
"use strict";

const API = "/api/v1";
const $ = (s) => document.querySelector(s);
const esc = (s) => (s ?? "").toString().replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const KEY_STORE = "udip_api_key";

function toast(msg, kind = "") {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show " + kind;
  setTimeout(() => (t.className = "toast"), 2800);
}

function getKey() { return localStorage.getItem(KEY_STORE) || ""; }

async function api(path, opts = {}) {
  opts.headers = Object.assign({ "X-API-Key": getKey() }, opts.headers || {});
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    let d = res.statusText;
    try { d = (await res.json()).detail || d; } catch (_) {}
    const e = new Error(d); e.status = res.status; throw e;
  }
  return res.headers.get("content-type")?.includes("json") ? res.json() : res;
}

function saveKey() {
  const v = $("#apikey-input").value.trim();
  if (!v) return toast("Kalit kiriting", "err");
  localStorage.setItem(KEY_STORE, v);
  toast("Kalit saqlandi", "ok");
  loadDashboard();
}
function clearKey() { localStorage.removeItem(KEY_STORE); $("#dashboard").style.display = "none"; toast("Tozalandi"); }

async function createKey() {
  const name = $("#newkey-name").value.trim() || "Nomsiz kalit";
  try {
    const r = await api("/keys", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    $("#raw-key-box").innerHTML =
      `<div class="raw-key">✅ Kalit yaratildi (faqat bir marta ko'rsatiladi):<br><strong>${esc(r.api_key)}</strong></div>`;
    localStorage.setItem(KEY_STORE, r.api_key);
    $("#apikey-input").value = r.api_key;
    toast("Kalit yaratildi va saqlandi", "ok");
    loadDashboard();
  } catch (e) { toast("Xato: " + e.message, "err"); }
}

async function revokeKey(id) {
  if (!confirm("Bu kalitni bekor qilishni xohlaysizmi?")) return;
  try {
    await api(`/keys/${id}`, { method: "DELETE" });
    toast("Kalit bekor qilindi", "ok");
    loadDashboard();
  } catch (e) { toast("Xato: " + e.message, "err"); }
}

const STAT_LABELS = {
  documents: "Hujjatlar", pages: "Sahifalar", ocr_results: "OCR natijalari",
  entities: "Ma'lumotlar", ai_results: "AI natijalari", tasks: "Vazifalar",
  api_keys: "API kalitlar", users: "Foydalanuvchilar",
};

function bars(container, obj) {
  const el = $(container);
  const entries = Object.entries(obj || {});
  if (!entries.length) { el.innerHTML = '<p class="muted">Ma\'lumot yo\'q.</p>'; return; }
  const max = Math.max(...entries.map(([, v]) => v));
  el.innerHTML = entries.map(([k, v]) =>
    `<div class="bar-row"><span>${esc(k)}</span>
       <div class="bar" style="width:${Math.max(2, (v / max) * 100)}%"></div>
       <span>${v}</span></div>`).join("");
}

async function loadDashboard() {
  if (!getKey()) return;
  try {
    const s = await api("/admin/stats");
    $("#dashboard").style.display = "block";
    $("#stat-cards").innerHTML = Object.keys(STAT_LABELS).map((k) =>
      `<div class="card"><div class="num">${s[k] ?? 0}</div><div class="lbl">${STAT_LABELS[k]}</div></div>`
    ).join("") +
      `<div class="card"><div class="num">${((s.total_storage_bytes||0)/1048576).toFixed(1)}</div><div class="lbl">MB saqlangan</div></div>`;
    bars("#type-bars", s.documents_by_type);
    bars("#status-bars", s.documents_by_status);
    await loadKeys();
  } catch (e) {
    $("#dashboard").style.display = "none";
    if (e.status === 401) toast("Kalit yaroqsiz yoki kerak", "err");
    else toast("Xato: " + e.message, "err");
  }
}

async function loadKeys() {
  try {
    const keys = await api("/keys");
    const tb = $("#keys-table tbody");
    tb.innerHTML = keys.map((k) => `
      <tr>
        <td>${esc(k.name)}</td>
        <td><code>${esc(k.key_prefix)}…</code></td>
        <td>${k.is_active ? "✅ Faol" : "⛔ Bekor"}</td>
        <td>${(k.created_at || "").slice(0, 10)}</td>
        <td>${k.last_used_at ? k.last_used_at.slice(0, 10) : "—"}</td>
        <td>${k.is_active ? `<button class="btn btn-ghost btn-sm" onclick="revokeKey(${k.id})">Bekor</button>` : ""}</td>
      </tr>`).join("");
  } catch (_) {}
}

document.addEventListener("DOMContentLoaded", () => {
  const k = getKey();
  if (k) { $("#apikey-input").value = k; loadDashboard(); }
});
