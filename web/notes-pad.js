"use strict";

const dialog = document.getElementById("notesPadDialog");
const mount = document.getElementById("notesPadMount");

if (!document.querySelector("link[data-jarvis-notes-pad]")) {
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "/ui/notes-pad.css?v=20260819-notas1";
  stylesheet.dataset.jarvisNotesPad = "true";
  document.head.appendChild(stylesheet);
}

function ownerHeaders(json) {
  const token = (() => { try { return localStorage.getItem("jarvis-owner-token-v1") || ""; } catch { return ""; } })();
  const headers = token ? { "X-Jarvis-Owner-Token": token } : {};
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...ownerHeaders(Boolean(options.body)), ...(options.headers || {}) },
    signal: AbortSignal.timeout?.(20_000),
  });
  const data = await response.json().catch(() => ({ ok: false, error: "Resposta inválida." }));
  if (!response.ok && data.ok !== false) data.ok = false;
  return data;
}

function paint(data, statusText) {
  const status = document.getElementById("notesPadStatus");
  const list = document.getElementById("notesPadList");
  if (!status || !list) return;
  status.textContent = statusText || data.error || `${data.count || 0} nota(s) no bloco do JARVIS`;
  list.replaceChildren();
  const notes = Array.isArray(data.notes) ? data.notes : [];
  if (!notes.length) {
    const empty = document.createElement("p");
    empty.className = "notes-pad-empty";
    empty.textContent = "Nada ainda. Escreva acima ou peça: “salva no bloco de notas: …”";
    list.appendChild(empty);
    return;
  }
  notes.forEach((note) => {
    const item = document.createElement("article");
    const head = document.createElement("header");
    const title = document.createElement("strong");
    const time = document.createElement("time");
    const body = document.createElement("p");
    const meta = document.createElement("small");
    title.textContent = note.title || "Nota";
    time.dateTime = note.created_at || "";
    time.textContent = note.created_at ? new Date(note.created_at).toLocaleString("pt-BR") : "";
    body.textContent = note.body || "";
    meta.textContent = note.mac_saved ? "JARVIS · cópia no Mac" : "JARVIS";
    head.append(title, time);
    item.append(head, body, meta);
    list.appendChild(item);
  });
}

async function refresh(statusText) {
  const data = await api("/notes?limit=40");
  paint(data, statusText);
}

async function save(event) {
  event.preventDefault();
  const title = document.getElementById("notesPadTitle")?.value.trim() || "";
  const body = document.getElementById("notesPadBody")?.value.trim() || "";
  const saveMac = Boolean(document.getElementById("notesPadMac")?.checked);
  if (!body) {
    document.getElementById("notesPadStatus").textContent = "Escreva a nota antes de salvar.";
    return;
  }
  const data = await api("/notes", {
    method: "POST",
    body: JSON.stringify({ title, body, save_mac: saveMac }),
  });
  if (!data.ok) {
    document.getElementById("notesPadStatus").textContent = data.error || "Não gravei a nota.";
    return;
  }
  document.getElementById("notesPadBody").value = "";
  if (!title) document.getElementById("notesPadTitle").value = "";
  await refresh(data.message || "Nota salva no bloco do JARVIS.");
}

function render() {
  if (!mount || mount.dataset.ready === "1") return;
  mount.dataset.ready = "1";
  mount.innerHTML = `
    <div class="dialog-head notes-pad-head">
      <span><small>BLOCO DE NOTAS</small><b>JARVIS</b></span>
      <button id="notesPadClose" type="button" aria-label="Fechar bloco de notas">×</button>
    </div>
    <section class="notes-pad-body">
      <form class="notes-pad-form" id="notesPadForm">
        <input id="notesPadTitle" maxlength="80" placeholder="Título (opcional)" aria-label="Título da nota">
        <textarea id="notesPadBody" maxlength="4000" placeholder="Escreva a nota. Vale em qualquer computador." aria-label="Texto da nota"></textarea>
        <div class="notes-pad-actions">
          <button type="submit">Salvar no JARVIS</button>
          <label><input id="notesPadMac" type="checkbox"> também no Mac</label>
        </div>
      </form>
      <p class="notes-pad-status" id="notesPadStatus">Carregando notas…</p>
      <div class="notes-pad-list" id="notesPadList"></div>
    </section>
  `;
  document.getElementById("notesPadClose")?.addEventListener("click", () => dialog?.close());
  document.getElementById("notesPadForm")?.addEventListener("submit", save);
}

function openPad() {
  render();
  dialog?.showModal();
  refresh();
  window.setTimeout(() => document.getElementById("notesPadBody")?.focus(), 30);
}

window.JarvisNotesPad = Object.freeze({ open: openPad });
