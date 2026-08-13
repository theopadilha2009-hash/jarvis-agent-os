"use strict";

document.getElementById("memoryExplorerButton")?.addEventListener("click", () => {
  import("/ui/memory-explorer.js?v=20260813-permissions1").catch(() => null);
}, { once: true });

const permissions = () => import("/ui/action-permissions.js?v=20260813-permissions1");

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
});
