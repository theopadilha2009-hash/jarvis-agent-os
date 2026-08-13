"use strict";

const recipes = Object.freeze([
  {
    id: "whatsapp-lead",
    tag: "WHATSAPP",
    label: "Responder novo lead",
    detail: "Webhook · telefone · resposta",
    template: "webhook",
    goal: "Receber um lead por webhook, normalizar nome e telefone e enviar uma resposta pelo WhatsApp",
  },
  {
    id: "gmail-digest",
    tag: "GMAIL",
    label: "Resumo de pendências",
    detail: "Agenda · resumo · e-mail",
    template: "schedule",
    goal: "Todo dia buscar pendências, montar um resumo organizado e enviar por Gmail",
  },
  {
    id: "github-incident",
    tag: "GITHUB",
    label: "Incidente de deploy",
    detail: "Webhook · falha · issue",
    template: "webhook",
    goal: "Receber uma falha de deploy do GitHub por webhook e abrir uma issue de incidente no GitHub",
  },
  {
    id: "supabase-intake",
    tag: "SUPABASE",
    label: "Entrada validada",
    detail: "Webhook · validar · salvar",
    template: "webhook",
    goal: "Receber dados por webhook, validar os campos e salvar no Supabase",
  },
]);

const gallery = document.getElementById("n8nTemplateGallery");
if (gallery && !gallery.dataset.ready) {
  gallery.dataset.ready = "true";
  gallery.replaceChildren(...recipes.map((recipe) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.n8nRecipe = recipe.id;
    button.dataset.n8nTemplate = recipe.template;
    button.dataset.n8nGoal = recipe.goal;
    const tag = document.createElement("small");
    const label = document.createElement("b");
    const detail = document.createElement("span");
    tag.textContent = recipe.tag;
    label.textContent = recipe.label;
    detail.textContent = recipe.detail;
    button.append(tag, label, detail);
    return button;
  }));
  gallery.addEventListener("click", (event) => {
    const button = event.target.closest("[data-n8n-recipe]");
    if (!button) return;
    const goal = document.getElementById("n8nWorkflowGoal");
    const template = document.getElementById("n8nWorkflowTemplate");
    if (goal) goal.value = button.dataset.n8nGoal || "";
    if (template) template.value = button.dataset.n8nTemplate || "auto";
    document.getElementById("n8nPreviewButton")?.click();
  });
}

export { recipes };
