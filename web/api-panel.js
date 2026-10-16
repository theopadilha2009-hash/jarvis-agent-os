"use strict";

// CONTAS sob comando do dono: lista quem existe, aprova, pausa, promove e apaga.
// Regra dura: só chama endpoint que o gateway já tem (GET/POST /accounts).
// O que o gateway ainda não tem fica fora do ar com motivo visível:
// reset de senha, rebaixar dono (só existe promote) e revogar aprovação (voltar a pending).
window.JarvisAccountsPanel = (() => {
  const OWNER_TOKEN_KEY = "jarvis-owner-token-v1";
  const STYLE_HREF = "/ui/api-panel.css?v=20260813-ultronfix1";
  const ROLE_LABEL = { owner: "DONO", member: "MEMBRO", pending: "PENDENTE" };
  const CONFIRM_TEXT = {
    approve: (name) => `Aprovar "${name}" para o modo code?`,
    disable: (name) => `Pausar "${name}"? Ela não entra até você reativar.`,
    enable: (name) => `Reativar "${name}"?`,
    promote: (name) => `Tornar "${name}" dono? O gateway não tem como rebaixar depois.`,
    delete: (name) => `Apagar "${name}"? Não tem volta.`,
  };
  const CONFIRMED = new Set(["approve", "disable", "enable", "promote", "delete"]);
  const PASSWORD_TOOLTIP = "endpoint ausente — pediu para criar";

  let dialog = null;
  let list = null;
  let hint = null;
  let loading = false;
  let pendingNote = null;

  if (!document.querySelector(`link[href="${STYLE_HREF}"]`)) {
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = STYLE_HREF;
    document.head.appendChild(stylesheet);
  }

  function token() {
    try {
      return localStorage.getItem(OWNER_TOKEN_KEY) || "";
    } catch {
      return "";
    }
  }

  async function call(path, payload) {
    const headers = { "Content-Type": "application/json" };
    const owner = token();
    if (owner) headers["X-Jarvis-Owner-Token"] = owner;
    try {
      const response = await fetch(path, {
        method: payload ? "POST" : "GET",
        headers,
        body: payload ? JSON.stringify(payload) : undefined,
        signal: typeof AbortSignal?.timeout === "function" ? AbortSignal.timeout(20000) : undefined,
      });
      const data = await response.json().catch(() => ({ ok: false, error: "O runtime respondeu em um formato inválido." }));
      if (!response.ok && data.ok !== false) data.ok = false;
      return data;
    } catch {
      return { ok: false, error: "Sem rede. Tente de novo." };
    }
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[ch]));
  }

  function seenLabel(value) {
    const stamp = Date.parse(value || "");
    if (!stamp) return "nunca entrou";
    const delta = Math.max(0, Date.now() - stamp);
    if (delta < 60_000) return "agora";
    if (delta < 3_600_000) return `há ${Math.floor(delta / 60_000)} min`;
    if (delta < 86_400_000) return `há ${Math.floor(delta / 3_600_000)} h`;
    return `há ${Math.floor(delta / 86_400_000)} d`;
  }

  function shortDate(value) {
    const stamp = Date.parse(value || "");
    if (!stamp) return "";
    const at = new Date(stamp);
    const day = String(at.getDate()).padStart(2, "0");
    const month = String(at.getMonth() + 1).padStart(2, "0");
    return `${day}/${month}`;
  }

  function badges(user) {
    const role = ROLE_LABEL[user.role] || escapeHtml(String(user.role || "?")).toUpperCase();
    const parts = [`<span class="ap-badge" data-kind="${escapeHtml(user.role)}">${role}</span>`];
    if (user.disabled) parts.push('<span class="ap-badge" data-kind="off">PAUSADA</span>');
    return parts.join("");
  }

  function metaLine(user) {
    const bits = [];
    if (user.email) bits.push(escapeHtml(user.email));
    bits.push(`acesso: ${escapeHtml((user.access || []).join(", ") || "nenhum")}`);
    bits.push(`última vez ${seenLabel(user.last_seen_at)}`);
    const created = shortDate(user.created_at);
    if (created) bits.push(`criada ${created}`);
    if (user.accepted_terms === false) bits.push("termos não aceitos");
    return `<small>${bits.join(" · ")}</small>`;
  }

  function actionButton(act, label, user, extra = "") {
    return `<button type="button" data-ap-act="${act}" data-ap-user="${escapeHtml(user.username)}" aria-label="${label} de ${escapeHtml(user.username)}"${extra}>${label}</button>`;
  }

  function rowMenu(user) {
    const menu = [];
    if (user.role !== "owner") {
      if (user.role === "pending") menu.push(actionButton("approve", "Aprovar code", user));
      menu.push(actionButton(user.disabled ? "enable" : "disable", user.disabled ? "Reativar" : "Pausar", user));
      if (!user.disabled && user.role !== "pending") menu.push(actionButton("promote", "Tornar dono", user));
      menu.push(actionButton("delete", "Apagar", user, ' class="integration-danger"'));
    }
    // Reset de senha: o gateway não tem endpoint. Botão morto de propósito, com o motivo.
    menu.push(`<button type="button" disabled aria-disabled="true" title="${PASSWORD_TOOLTIP}" aria-label="Definir nova senha de ${escapeHtml(user.username)} — ${PASSWORD_TOOLTIP}">Nova senha</button>`);
    return `<menu aria-label="Ações da conta ${escapeHtml(user.username)}">${menu.join("")}</menu>`;
  }

  function rowHtml(user) {
    return `<article class="account-row" data-ap-user="${escapeHtml(user.username)}">
  <div>
    <b>${escapeHtml(user.username)} ${badges(user)}</b>
    ${metaLine(user)}
    <p class="integration-feedback" data-ap-note hidden role="status" aria-live="polite"></p>
    <div class="ap-confirm" data-ap-confirm hidden role="alert">
      <span data-ap-text></span>
      <button type="button" data-ap-act="go" aria-label="Confirmar ação em ${escapeHtml(user.username)}">Confirmar</button>
      <button type="button" data-ap-act="cancel" aria-label="Cancelar ação em ${escapeHtml(user.username)}">Cancelar</button>
    </div>
  </div>
  ${rowMenu(user)}
</article>`;
  }

  function headHtml(users) {
    const pending = users.filter((user) => user.role === "pending").length;
    const summary = `${users.length} conta(s) · ${pending ? `${pending} aguardando aprovação` : "nada pendente"}`;
    return `<article class="account-row">
  <div><small>${summary} · ordem do gateway (dono primeiro)</small></div>
  <menu><button type="button" data-ap-act="reload" aria-label="Recarregar lista de contas">Recarregar</button></menu>
</article>`;
  }

  function setNote(user, state, text, sticky = false) {
    pendingNote = sticky ? { user, state, text } : null;
    paintNote(user, state, text);
    if (!sticky) return;
    window.setTimeout(() => {
      if (pendingNote && pendingNote.user === user) {
        pendingNote = null;
        paintNote(user, "", "");
      }
    }, 6000);
  }

  function paintNote(user, state, text) {
    const row = list?.querySelector(`[data-ap-user="${CSS.escape(user)}"]`);
    const note = row?.querySelector("[data-ap-note]");
    if (!note) return;
    note.textContent = text || "";
    if (state) note.dataset.state = state;
    else delete note.dataset.state;
    note.hidden = !text;
  }

  function askConfirm(row, act, user) {
    const strip = row.querySelector("[data-ap-confirm]");
    if (!strip) return;
    strip.dataset.apPending = act;
    strip.dataset.apUser = user;
    row.querySelector("[data-ap-text]").textContent = (CONFIRM_TEXT[act] || ((name) => `Executar em "${name}"?`))(user);
    strip.hidden = false;
  }

  function closeConfirm(row) {
    const strip = row.querySelector("[data-ap-confirm]");
    if (strip) strip.hidden = true;
  }

  async function run(row, act, user) {
    if (loading || !act || !user) return;
    loading = true;
    const wasEnabled = [...row.querySelectorAll("button:not(:disabled)")];
    wasEnabled.forEach((button) => { button.disabled = true; });
    const data = await call("/accounts", { action: act, username: user });
    loading = false;
    if (data.ok) {
      setNote(user, "success", "Feito. " + String(data.status_real || "conta atualizada"), true);
      await refresh();
      return;
    }
    wasEnabled.forEach((button) => { button.disabled = false; });
    closeConfirm(row);
    setNote(user, "error", String(data.error || "Não consegui atualizar a conta."));
  }

  function onListClick(event) {
    const button = event.target.closest("[data-ap-act]");
    if (!button || button.disabled) return;
    const row = button.closest(".account-row");
    const act = button.dataset.apAct;
    if (act === "reload") { refresh(); return; }
    if (act === "cancel") { closeConfirm(row); return; }
    if (act === "go") {
      const strip = row?.querySelector("[data-ap-confirm]");
      run(row, strip?.dataset.apPending || "", strip?.dataset.apUser || "");
      return;
    }
    if (!CONFIRMED.has(act)) return;
    askConfirm(row, act, button.dataset.apUser);
  }

  function renderError(message) {
    list.innerHTML = `<article class="account-row"><div><small>${escapeHtml(message)}</small></div><menu><button type="button" data-ap-act="reload" aria-label="Tentar de novo">Tentar de novo</button></menu></article>`;
  }

  async function refresh() {
    if (loading || !list) return;
    loading = true;
    list.innerHTML = '<article class="account-row"><small>Carregando contas…</small></article>';
    const data = await call("/accounts");
    loading = false;
    if (!data.ok) {
      if (hint) hint.textContent = String(data.error || "Não consegui ler as contas.");
      renderError(String(data.error || "Não consegui ler as contas."));
      return;
    }
    const users = Array.isArray(data.users) ? data.users : [];
    list.innerHTML = headHtml(users) + users.map(rowHtml).join("");
    if (hint) hint.textContent = "Senha nunca aparece aqui: só definir nova senha, e o endpoint ainda não existe.";
    if (pendingNote) paintNote(pendingNote.user, pendingNote.state, pendingNote.text);
  }

  function ensureDialog() {
    dialog = document.getElementById("accountsDialog");
    if (dialog) {
      list = document.getElementById("accountsList");
      hint = document.getElementById("accountsHint");
      return;
    }
    dialog = document.createElement("dialog");
    dialog.className = "accounts-dialog";
    dialog.setAttribute("aria-labelledby", "apAccountsTitle");
    dialog.innerHTML = `<div class="dialog-head"><b id="apAccountsTitle">CONTAS</b><button type="button" data-ap-close aria-label="Fechar contas">×</button></div><p class="accounts-hint" data-ap-hint></p><div class="accounts-list" data-ap-list></div>`;
    document.body.appendChild(dialog);
    list = dialog.querySelector("[data-ap-list]");
    hint = dialog.querySelector("[data-ap-hint]");
    dialog.querySelector("[data-ap-close]").addEventListener("click", () => dialog.close());
  }

  function open() {
    ensureDialog();
    dialog.addEventListener("close", () => { pendingNote = null; }, { once: true });
    if (!dialog.open) dialog.showModal();
    refresh();
  }

  function bootstrap() {
    ensureDialog();
    list?.addEventListener("click", onListClick);
    document.getElementById("crownButton")?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      open();
    }, true);
  }

  if (document.body) bootstrap();
  else document.addEventListener("DOMContentLoaded", bootstrap, { once: true });

  return Object.freeze({ open, refresh });
})();
