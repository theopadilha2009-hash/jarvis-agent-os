"use strict";

const loadStyle = (id, href) => {
  if (document.getElementById(id)) return;
  const link = document.createElement("link");
  link.id = id;
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
};

loadStyle("ultronCompletionStyle", "/ui/ultron-completion.css?v=20260813-ultronfix1");

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

const githubStar = document.createElement("a");
githubStar.className = "quiet-button github-star-button";
githubStar.href = "https://github.com/theopadilha2009-hash/jarvis-agent-os";
githubStar.target = "_blank";
githubStar.rel = "noopener noreferrer";
githubStar.title = "Abrir o JARVIS no GitHub e dar uma estrela";
githubStar.setAttribute("aria-label", "Dar uma estrela no JARVIS no GitHub");
githubStar.innerHTML = '<span aria-hidden="true">★</span><b>GitHub</b>';
document.getElementById("integrationsButton")?.before(githubStar);

document.getElementById("memoryExplorerButton")?.addEventListener("click", () => {
  import("/ui/memory-explorer.js?v=20260813-ultronfix1").catch(() => null);
}, { once: true });

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
