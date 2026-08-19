"use strict";

const loadStyle = (id, href) => {
  if (document.getElementById(id)) return;
  const link = document.createElement("link");
  link.id = id;
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
};

loadStyle("ultronCompletionStyle", "/ui/ultron-completion.css?v=20260819-notas1");

function ensureDialog(id, className, titleId, title, mountId) {
  if (document.getElementById(id)) return;
  const dialog = document.createElement("dialog");
  dialog.id = id;
  dialog.className = className;
  dialog.setAttribute("aria-labelledby", titleId);
  dialog.innerHTML = `<span id="${titleId}" hidden>${title}</span><div id="${mountId}"></div>`;
  document.body.appendChild(dialog);
}

ensureDialog("memoryExplorerDialog", "memory-explorer-dialog", "memoryExplorerTitle", "Explorar memória", "memoryExplorerMount");
ensureDialog("actionPermissionsDialog", "action-permissions-dialog", "actionPermissionsTitle", "Permissões de ações", "actionPermissionsMount");
ensureDialog("notesPadDialog", "notes-pad-dialog", "notesPadHeading", "Bloco de notas", "notesPadMount");
ensureDialog("codePadDialog", "code-pad-dialog", "codePadHeading", "JARVIS Code", "codePadMount");

// Assinatura do dono: leva ao LinkedIn do Theo, sem embed de terceiro.
const authorLink = document.createElement("a");
authorLink.className = "author-link";
authorLink.href = "https://www.linkedin.com/in/theo-lorentz-padilha-0b9b99287/";
authorLink.target = "_blank";
authorLink.rel = "noopener noreferrer";
authorLink.title = "Theo Lorentz Padilha no LinkedIn";
authorLink.setAttribute("aria-label", "Abrir o LinkedIn de Theo Lorentz Padilha");
authorLink.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-.95 1.83-1.95 3.76-1.95 4.02 0 4.76 2.5 4.76 5.76V21h-4v-5.6c0-1.34-.03-3.07-1.9-3.07-1.9 0-2.19 1.46-2.19 2.97V21H9z"></path></svg><span>Theo</span>';
document.getElementById("integrationsButton")?.before(authorLink);

fetch("/github-star", { signal: AbortSignal.timeout?.(8000) })
  .then((response) => (response.ok ? response.json() : null))
  .then((data) => {
    const stars = Number(data?.stars);
    const counter = document.getElementById("githubStarCount");
    if (!counter || !Number.isFinite(stars)) return;
    counter.textContent = stars >= 1000 ? `${(stars / 1000).toFixed(1).replace(/\.0$/, "")}k` : String(stars);
    counter.hidden = false;
  })
  .catch(() => null);

document.getElementById("memoryExplorerButton")?.addEventListener("click", () => {
  import("/ui/memory-explorer.js?v=20260813-ultronfix1").catch(() => null);
}, { once: true });

document.getElementById("notesPadButton")?.addEventListener("click", () => {
  import("/ui/notes-pad.js?v=20260819-notas1").then(() => window.JarvisNotesPad?.open()).catch(() => null);
});

function openCodePad(detail) {
  import("/ui/code-pad.js?v=20260819-bar1").then(() => window.JarvisCodePad?.open(detail || {})).catch(() => null);
}

document.getElementById("codePadButton")?.addEventListener("click", () => {
  document.getElementById("codeLaunchDialog")?.showModal();
});
window.addEventListener("jarvis-open-code", (event) => {
  const detail = event.detail || {};
  if (detail.terminal) {
    openCodePad({ terminal: true });
    return;
  }
  openCodePad(detail);
});
document.getElementById("codeLaunchPad")?.addEventListener("click", () => {
  document.getElementById("codeLaunchDialog")?.close();
  openCodePad({});
});
document.getElementById("codeLaunchTerminal")?.addEventListener("click", () => {
  document.getElementById("codeLaunchDialog")?.close();
  openCodePad({ terminal: true });
});
document.getElementById("closeCodeLaunch")?.addEventListener("click", () => {
  document.getElementById("codeLaunchDialog")?.close();
});
document.getElementById("downloadButton")?.addEventListener("click", () => {
  document.getElementById("downloadDialog")?.showModal();
});
document.getElementById("closeDownloadDialog")?.addEventListener("click", () => {
  document.getElementById("downloadDialog")?.close();
});
document.getElementById("welcomeAppButton")?.addEventListener("click", () => {
  document.getElementById("downloadDialog")?.showModal();
});

const permissions = () => import("/ui/action-permissions.js?v=20260813-ultronfix1");

document.getElementById("actionPermissionsButton")?.addEventListener("click", () => {
  permissions().then((module) => module.open()).catch(() => null);
});

function categoryForCommand(command) {
  const text = String(command || "").toLocaleLowerCase("pt-BR");
  if (/\b(?:cri\w*|dupli\w*|ativ\w*)\b.{0,80}\b(?:n8n|workflow|automa[cç][aã]o)\b|\b(?:n8n|workflow)\b.{0,80}\b(?:cri\w*|dupli\w*|ativ\w*)\b/.test(text)) return "automation";
  if (/\b(?:mand\w*|envi\w*|public\w*)\b.{0,100}\b(?:mensagem|whatsapp|webhook|discord|slack|e-?mail)\b/.test(text)) return "outbound";
  if (/\b(?:abra|abre|abrir|feche|fecha|fechar|print|captur\w*|gravar?\s+(?:a\s+)?tela|spotify|aplicativo)\b/.test(text)) return "mac";
  if (/\b(?:cri\w*|desenh\w*)\b.{0,80}\bvoz\b/.test(text)) return "provider";
  return "";
}

window.JarvisFeatureLoader = Object.freeze({
  authorize: (category, operation) => permissions().then((module) => module.authorize(category, operation)).catch(() => false),
  categoryForCommand,
  screenUnavailable: (command, online) => !online && /\b(?:tir(?:a|e|ar)|faz(?:er)?|captur\w*)\b.{0,45}\b(?:print|screenshot|tela)\b/i.test(String(command || "")),
});
