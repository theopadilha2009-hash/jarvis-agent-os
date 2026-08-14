"use strict";

const loadStyle = (id, href) => {
  if (document.getElementById(id)) return;
  const link = document.createElement("link");
  link.id = id;
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
};

loadStyle("ultronCompletionStyle", "/ui/ultron-completion.css?v=20260814-chatfix1");

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

const GITHUB_REPO = "theopadilha2009-hash/jarvis-agent-os";
const githubStar = document.createElement("a");
githubStar.className = "github-star-button";
githubStar.href = `https://github.com/${GITHUB_REPO}`;
githubStar.target = "_blank";
githubStar.rel = "noopener noreferrer";
githubStar.title = "Star no GitHub";
githubStar.setAttribute("aria-label", "Dar uma estrela no GitHub");
githubStar.innerHTML = (
  '<span class="github-star-mark" aria-hidden="true">'
  + '<svg viewBox="0 0 16 16" width="16" height="16"><path fill="currentColor" d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"></path></svg>'
  + "Star"
  + "</span>"
  + '<span class="github-star-count" id="githubStarCount">—</span>'
);
document.getElementById("integrationsButton")?.before(githubStar);
fetch(`https://api.github.com/repos/${GITHUB_REPO}`)
  .then((response) => (response.ok ? response.json() : null))
  .then((data) => {
    const count = Number(data?.stargazers_count);
    const label = document.getElementById("githubStarCount");
    if (label && Number.isFinite(count)) label.textContent = count.toLocaleString("en-US");
  })
  .catch(() => null);

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
