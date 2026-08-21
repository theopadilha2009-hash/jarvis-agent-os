"use strict";

const STORAGE_KEY = "jarvis-action-permissions-v1";
const SESSION_KEY = "jarvis-action-permissions-session-v1";
const categories = Object.freeze({
  mac: { label: "Mac e tela", detail: "Abrir apps, capturar ou gravar a tela." },
  outbound: { label: "Envios externos", detail: "Mensagens, e-mail, WhatsApp e webhooks." },
  automation: { label: "Automações n8n", detail: "Criar ou duplicar workflows inativos." },
  provider: { label: "Criações em APIs", detail: "Criar voz ou outro recurso num provedor." },
});
const dialog = document.getElementById("actionPermissionsDialog");
const mount = document.getElementById("actionPermissionsMount");
let pending = null;

if (!document.querySelector("link[data-jarvis-action-permissions]")) {
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "/ui/action-permissions.css?v=20260813-ultronfix1";
  stylesheet.dataset.jarvisActionPermissions = "true";
  document.head.appendChild(stylesheet);
}

function read(storage, fallback) {
  try { return { ...fallback, ...JSON.parse(storage.getItem(storage === localStorage ? STORAGE_KEY : SESSION_KEY) || "{}") }; }
  catch { return { ...fallback }; }
}

function policies() { return read(localStorage, Object.fromEntries(Object.keys(categories).map((key) => [key, "ask"]))); }
function sessionAllows() { return read(sessionStorage, {}); }
function updateSummary() {
  const label = document.querySelector("#actionPermissionsButton b");
  if (!label) return;
  const blocked = Object.values(policies()).filter((value) => value === "block").length;
  const allowed = Object.keys(sessionAllows()).length;
  label.textContent = blocked ? `${blocked} bloqueada(s)` : allowed ? `${allowed} nesta sessão` : "perguntar antes";
}
function setPolicy(category, value) {
  const next = policies();
  next[category] = value === "block" ? "block" : "ask";
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch { /* política permanece na sessão atual */ }
  updateSummary();
}
function allowSession(category) {
  const next = sessionAllows();
  next[category] = true;
  try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(next)); } catch { /* uma autorização não persistida */ }
  updateSummary();
}
function revokeSession(category) {
  const next = sessionAllows();
  delete next[category];
  try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(next)); } catch { /* sessão já restrita */ }
  updateSummary();
}

function settle(value) {
  const resolve = pending;
  pending = null;
  resolve?.(Boolean(value));
}

function renderSettings() {
  if (!mount) return;
  const saved = policies();
  const allowed = sessionAllows();
  mount.innerHTML = `
    <div class="dialog-head permissions-head"><span><small>CONTROLE DO JARVIS</small><b>Permissões de ações</b></span><button id="permissionsClose" type="button" aria-label="Fechar permissões">×</button></div>
    <section class="permissions-body"><p>Nenhuma ação externa recebe permissão permanente. Escolha perguntar sempre ou bloquear; liberações duram somente esta aba.</p>
      <div class="permissions-list">${Object.entries(categories).map(([id, item]) => `
        <article><span><strong>${item.label}</strong><small>${item.detail}</small></span>
          <select data-permission-policy="${id}" aria-label="Política para ${item.label}"><option value="ask"${saved[id] === "ask" ? " selected" : ""}>Perguntar sempre</option><option value="block"${saved[id] === "block" ? " selected" : ""}>Bloquear</option></select>
          <button type="button" data-permission-revoke="${id}"${allowed[id] ? "" : " disabled"}>${allowed[id] ? "Revogar sessão" : "Sem liberação"}</button>
        </article>`).join("")}</div>
    </section>`;
  document.getElementById("permissionsClose")?.addEventListener("click", () => dialog?.close());
  mount.querySelectorAll("[data-permission-policy]").forEach((select) => select.addEventListener("change", () => {
    setPolicy(select.dataset.permissionPolicy, select.value);
    if (select.value === "block") revokeSession(select.dataset.permissionPolicy);
    renderSettings();
  }));
  mount.querySelectorAll("[data-permission-revoke]").forEach((button) => button.addEventListener("click", () => {
    revokeSession(button.dataset.permissionRevoke);
    renderSettings();
  }));
}

function renderRequest(category, operation) {
  const item = categories[category];
  if (!mount || !item) return;
  mount.innerHTML = `
    <div class="dialog-head permissions-head"><span><small>AUTORIZAÇÃO NECESSÁRIA</small><b>${item.label}</b></span><button id="permissionDenyTop" type="button" aria-label="Cancelar ação">×</button></div>
    <section class="permission-request"><i>JARVIS</i><strong>Permitir esta ação?</strong><p id="permissionOperation"></p><small>${item.detail}</small>
      <div><button id="permissionDeny" type="button">Cancelar</button><button id="permissionOnce" type="button">Permitir uma vez</button><button id="permissionSession" type="button">Liberar nesta sessão</button></div>
      <em>Fechar ou pressionar Esc cancela. Não existe “permitir para sempre”.</em>
    </section>`;
  document.getElementById("permissionOperation").textContent = String(operation || item.label).slice(0, 220);
  ["permissionDeny", "permissionDenyTop"].forEach((id) => document.getElementById(id)?.addEventListener("click", () => { settle(false); dialog?.close(); }));
  document.getElementById("permissionOnce")?.addEventListener("click", () => { settle(true); dialog?.close(); });
  document.getElementById("permissionSession")?.addEventListener("click", () => { allowSession(category); settle(true); dialog?.close(); });
}

function open() {
  settle(false);
  renderSettings();
  dialog?.showModal();
}

function authorize(category, operation) {
  if (!categories[category]) return Promise.resolve(false);
  if (policies()[category] === "block") return Promise.resolve(false);
  if (sessionAllows()[category]) return Promise.resolve(true);
  settle(false);
  renderRequest(category, operation);
  dialog?.showModal();
  return new Promise((resolve) => { pending = resolve; });
}

dialog?.addEventListener("close", () => settle(false));
updateSummary();

export { authorize, categories, open };
