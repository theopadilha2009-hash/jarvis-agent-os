"use strict";

const OWNER_TOKEN_KEY = "jarvis-owner-token-v1";
const MODULE_VERSION = "20260813-missions1";
const hub = document.getElementById("actionHub");
let panel = null;
let pollTimer = 0;
let loading = false;

function escapeHtml(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function ownerToken() {
  try { return localStorage.getItem(OWNER_TOKEN_KEY) || ""; } catch { return ""; }
}

function assistantName() {
  return document.documentElement.dataset.persona === "ultron" ? "ULTRON" : "JARVIS";
}

function formatMoment(value) {
  const date = new Date(value || "");
  if (Number.isNaN(date.getTime())) return "agora";
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = ownerToken();
  if (token) headers.set("X-Jarvis-Owner-Token", token);
  if (options.body) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || "A Central de Missões não confirmou a operação.");
    error.status = response.status;
    throw error;
  }
  return data;
}

function stateTone(state) {
  if (state === "completed") return "success";
  if (state === "failed") return "error";
  if (state === "waiting_confirmation") return "attention";
  if (state === "running" || state === "planned") return "active";
  return "quiet";
}

function operationLabel(operation) {
  return { confirm: "Confirmar", cancel: "Cancelar", retry: "Tentar novamente" }[operation] || operation;
}

function missionRow(mission) {
  const operations = Array.isArray(mission.operations) ? mission.operations : [];
  const progress = mission.progress || {};
  const event = mission.last_event || {};
  return `<article class="mission-control-row" data-state="${escapeHtml(mission.state)}">`
    + `<header><span><i>${escapeHtml(mission.action?.executor || "núcleo")}</i><b>${escapeHtml(mission.action?.label || "Missão")}</b></span>`
    + `<small data-tone="${stateTone(mission.state)}">${escapeHtml(mission.state_label || mission.state)}</small></header>`
    + `<p>${escapeHtml(mission.objective || "Pedido sem descrição")}</p>`
    + `<progress max="100" value="${Math.max(0, Math.min(100, Number(progress.percent) || 0))}" aria-label="Progresso da missão"></progress>`
    + `<div class="mission-control-meta"><span>${Number(progress.completed) || 0}/${Number(progress.total) || 1} etapas</span><span>${Number(mission.evidence_count) || 0} evidências</span><time>${escapeHtml(formatMoment(mission.updated_at))}</time></div>`
    + `<footer><span><small>PRÓXIMO PASSO</small><b>${escapeHtml(mission.next_step || "Revisar estado")}</b></span>`
    + `<div>${operations.map((operation) => `<button type="button" data-mission-operation="${escapeHtml(operation)}" data-run-id="${escapeHtml(mission.run_id)}">${operationLabel(operation)}</button>`).join("")}</div></footer>`
    + `<details><summary>Rastro verificável</summary><small>${Number(mission.event_count) || 0} eventos · último: ${escapeHtml(event.type || "sem evento")}</small><code>${escapeHtml(mission.run_id || "")}</code></details></article>`;
}

function render(data) {
  if (!panel) return;
  const summary = data.summary || {};
  const missions = Array.isArray(data.missions) ? data.missions : [];
  panel.dataset.health = data.health || "empty";
  panel.innerHTML = `<div class="mission-control-head"><span><small>CENTRAL DE MISSÕES</small><strong>Execução sob controle</strong></span><button type="button" data-mission-refresh aria-label="Atualizar missões">↻</button></div>`
    + `<p class="mission-control-message">${escapeHtml(data.message || "Estado real carregado.")}</p>`
    + `<div class="mission-control-summary"><span><small>ATIVAS</small><b>${Number(summary.active) || 0}</b></span><span><small>CONFIRMAR</small><b>${Number(summary.waiting_confirmation) || 0}</b></span><span><small>CONCLUÍDAS</small><b>${Number(summary.completed) || 0}</b></span><span><small>FALHAS</small><b>${Number(summary.failed) || 0}</b></span></div>`
    + `<div class="mission-control-list">${missions.length ? missions.map(missionRow).join("") : "<div class=\"mission-control-empty\">Seu próximo pedido real aparecerá aqui com etapas, estado e evidências.</div>"}</div>`;
}

function renderUnavailable(message) {
  if (!panel) return;
  panel.dataset.health = "error";
  panel.innerHTML = `<div class="mission-control-head"><span><small>CENTRAL DE MISSÕES</small><strong>Estado protegido</strong></span><button type="button" data-mission-refresh aria-label="Tentar novamente">↻</button></div><p class="mission-control-message">${escapeHtml(message)}</p>`;
}

async function refresh() {
  if (!panel || loading) return;
  loading = true;
  panel.setAttribute("aria-busy", "true");
  try {
    const data = await request("/mission-control?limit=12");
    if (data.protocol !== "jarvis-mission-control/1") throw new Error("O núcleo respondeu sem o contrato de missões.");
    render(data);
  } catch (error) {
    renderUnavailable(error.status === 401 ? `Entre no modo Ultron para abrir as missões privadas do ${assistantName()}.` : error.message);
  } finally {
    loading = false;
    panel?.removeAttribute("aria-busy");
  }
}

async function operate(button) {
  const operation = button.dataset.missionOperation;
  const runId = button.dataset.runId;
  if (!operation || !runId) return;
  const warnings = { confirm: "Confirmar esta missão e permitir que ela siga pela rota exibida?", cancel: "Cancelar esta missão antes de novas etapas?", retry: "Criar uma nova tentativa desta missão?" };
  if (!window.confirm(warnings[operation] || "Continuar?")) return;
  button.disabled = true;
  try {
    await request(`/runs/${encodeURIComponent(runId)}/${operation}`, { method: "POST", body: "{}" });
    await refresh();
  } catch (error) {
    renderUnavailable(error.message);
  } finally {
    button.disabled = false;
  }
}

function schedulePoll() {
  window.clearInterval(pollTimer);
  if (!hub || hub.hidden) return;
  pollTimer = window.setInterval(() => { if (!hub.hidden && !document.hidden) refresh(); }, 5000);
}

function mount() {
  if (!hub || panel) return;
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = `/ui/mission-control.css?v=${MODULE_VERSION}`;
  document.head.appendChild(stylesheet);
  const headerCopy = hub.querySelector("header span");
  if (headerCopy) headerCopy.innerHTML = "<small>CENTRAL DE MISSÕES</small><strong>Veja. Decida. Continue.</strong>";
  panel = document.createElement("section");
  panel.id = "missionControl";
  panel.className = "mission-control";
  panel.setAttribute("aria-live", "polite");
  panel.innerHTML = "<div class=\"mission-control-empty\">Carregando missões reais…</div>";
  const actionSection = hub.querySelector(".action-hub-section");
  hub.insertBefore(panel, actionSection || null);
  panel.addEventListener("click", (event) => {
    const refreshButton = event.target.closest("[data-mission-refresh]");
    if (refreshButton) return refresh();
    const operationButton = event.target.closest("[data-mission-operation]");
    if (operationButton) operate(operationButton);
  });
  new MutationObserver(() => {
    if (!hub.hidden) refresh();
    schedulePoll();
  }).observe(hub, { attributes: true, attributeFilter: ["hidden"] });
  if (!hub.hidden) refresh();
  schedulePoll();
}

mount();
