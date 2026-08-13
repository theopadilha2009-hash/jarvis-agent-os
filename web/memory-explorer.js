"use strict";

const dialog = document.getElementById("memoryExplorerDialog");
const mount = document.getElementById("memoryExplorerMount");
const kindLabels = Object.freeze({ all: "Todos", decision: "Decisão", preference: "Preferência", learning: "Aprendizado", context: "Contexto" });

if (!document.querySelector("link[data-jarvis-memory-explorer]")) {
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "/ui/memory-explorer.css?v=20260813-memory1";
  stylesheet.dataset.jarvisMemoryExplorer = "true";
  document.head.appendChild(stylesheet);
}

function isoDate(date) { return date.toISOString().slice(0, 10); }

function setPeriod(days) {
  const from = document.getElementById("memoryDateFrom");
  const to = document.getElementById("memoryDateTo");
  if (!from || !to) return;
  if (!days) {
    from.value = "";
    to.value = "";
    return;
  }
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - days + 1);
  from.value = isoDate(start);
  to.value = isoDate(end);
}

async function privateRequest(path) {
  const token = (() => { try { return localStorage.getItem("jarvis-owner-token-v1") || ""; } catch { return ""; } })();
  const headers = token ? { "X-Jarvis-Owner-Token": token } : {};
  const response = await fetch(path, { headers, signal: AbortSignal.timeout?.(20_000) });
  const data = await response.json().catch(() => ({ ok: false, error: "Resposta inválida." }));
  if (!response.ok && data.ok !== false) data.ok = false;
  return data;
}

function renderResults(data) {
  const status = document.getElementById("memoryExplorerStatus");
  const target = document.getElementById("memoryExplorerResults");
  if (!status || !target) return;
  target.replaceChildren();
  if (!data?.ok) {
    status.textContent = data?.error || "A memória privada não respondeu.";
    return;
  }
  status.textContent = `${data.count} de ${data.total_active} memória(s) ativa(s) · somente leitura`;
  if (!data.results?.length) {
    const empty = document.createElement("p");
    empty.className = "memory-explorer-empty";
    empty.textContent = "Nada encontrado nesse assunto e período.";
    target.appendChild(empty);
    return;
  }
  data.results.forEach((row) => {
    const item = document.createElement("article");
    const head = document.createElement("header");
    const title = document.createElement("strong");
    const date = document.createElement("time");
    const snippet = document.createElement("p");
    const meta = document.createElement("small");
    title.textContent = row.title || "Memória";
    date.dateTime = row.created_at || "";
    date.textContent = row.created_at ? new Date(row.created_at).toLocaleDateString("pt-BR") : "sem data";
    snippet.textContent = row.snippet || "";
    meta.textContent = `${kindLabels[row.kind] || row.kind || "Contexto"} · ${row.category || "MEMÓRIA"}`;
    head.append(title, date);
    item.append(head, snippet, meta);
    target.appendChild(item);
  });
}

async function search() {
  const form = document.getElementById("memoryExplorerForm");
  const status = document.getElementById("memoryExplorerStatus");
  if (!form || !status) return;
  const params = new URLSearchParams(new FormData(form));
  params.set("limit", "30");
  status.textContent = "Consultando a memória privada…";
  try { renderResults(await privateRequest(`/memory-explorer?${params}`)); }
  catch { renderResults({ ok: false, error: "A consulta demorou demais ou ficou indisponível." }); }
}

function mountExplorer() {
  if (!mount || mount.dataset.ready) return;
  mount.dataset.ready = "true";
  mount.innerHTML = `
    <div class="dialog-head memory-explorer-head"><span><small>MEMÓRIA PRIVADA</small><b>Explorar lembranças</b></span><button id="memoryExplorerClose" type="button" aria-label="Fechar memória">×</button></div>
    <form id="memoryExplorerForm" class="memory-explorer-form">
      <label class="memory-query">Assunto<input name="q" id="memoryQuery" type="search" maxlength="300" placeholder="Ex.: voz, busto, deploy"></label>
      <label>Tipo<select name="kind" id="memoryKind">${Object.entries(kindLabels).map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}</select></label>
      <label>De<input name="from" id="memoryDateFrom" type="date"></label>
      <label>Até<input name="to" id="memoryDateTo" type="date"></label>
      <div class="memory-periods"><button type="button" data-memory-days="7">7 dias</button><button type="button" data-memory-days="30">30 dias</button><button type="button" data-memory-days="365">1 ano</button><button type="button" data-memory-days="0">Tudo</button></div>
      <button class="memory-search-button" type="submit">Pesquisar</button>
    </form>
    <p id="memoryExplorerStatus" class="memory-explorer-status" aria-live="polite">Preparando consulta…</p>
    <div id="memoryExplorerResults" class="memory-explorer-results"></div>`;
  document.getElementById("memoryExplorerClose")?.addEventListener("click", () => dialog?.close());
  document.getElementById("memoryExplorerForm")?.addEventListener("submit", (event) => { event.preventDefault(); search(); });
  mount.querySelectorAll("[data-memory-days]").forEach((button) => button.addEventListener("click", () => {
    setPeriod(Number(button.dataset.memoryDays));
    search();
  }));
  setPeriod(30);
}

mountExplorer();
dialog?.showModal();
search();
document.getElementById("memoryExplorerButton")?.addEventListener("click", () => {
  dialog?.showModal();
  search();
});

export { search, setPeriod };
