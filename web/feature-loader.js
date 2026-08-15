"use strict";

const loadStyle = (id, href) => {
  if (document.getElementById(id)) return;
  const link = document.createElement("link");
  link.id = id;
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
};

loadStyle("ultronCompletionStyle", "/ui/ultron-completion.css?v=20260815-nucleus4");

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

// Botão nativo: o embed de terceiro só desenhava para repositório público e
// sumia por completo aqui. Este sempre aparece; a contagem entra depois se a
// API do GitHub responder.
const GITHUB_REPO = "theopadilha2009-hash/jarvis-agent-os";
const githubStar = document.createElement("a");
githubStar.className = "github-star-button";
githubStar.href = `https://github.com/${GITHUB_REPO}`;
githubStar.target = "_blank";
githubStar.rel = "noopener noreferrer";
githubStar.title = "Dar uma estrela no GitHub";
githubStar.setAttribute("aria-label", "Dar uma estrela no GitHub");
githubStar.innerHTML = '<i aria-hidden="true">★</i><span>Star</span><b hidden></b>';
document.getElementById("integrationsButton")?.before(githubStar);

fetch(`https://api.github.com/repos/${GITHUB_REPO}`, { headers: { Accept: "application/vnd.github+json" } })
  .then((response) => (response.ok ? response.json() : null))
  .then((data) => {
    const stars = Number(data?.stargazers_count);
    if (!Number.isFinite(stars)) return;
    const counter = githubStar.querySelector("b");
    counter.textContent = stars >= 1000 ? `${(stars / 1000).toFixed(1)}k` : String(stars);
    counter.hidden = false;
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
