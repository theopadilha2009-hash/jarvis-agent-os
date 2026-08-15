"use strict";

// Personalidade sob comando: o Theo escolhe o jeito, a identidade continua a mesma.
window.JarvisPersonaPanel = (() => {
  const STORAGE_KEY = "jarvis-persona-style-v1";
  const FALLBACK = Object.freeze([
    { id: "padrao", label: "Padrão", description: "Presença competente, calma e afiada." },
    { id: "direto", label: "Direto", description: "Só o essencial, sem rodeio." },
    { id: "mordomo", label: "Mordomo", description: "Formalidade britânica e autoridade serena." },
    { id: "afiado", label: "Afiado", description: "Humor seco mais presente." },
    { id: "tecnico", label: "Técnico", description: "Detalhe de engenharia e trade-offs." },
    { id: "parceiro", label: "Parceiro", description: "Solto e próximo, como quem trabalha do seu lado." },
  ]);
  let styles = FALLBACK.slice();
  let active = load();
  let dialog = null;

  if (!document.querySelector("link[data-jarvis-persona-panel]")) {
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = "/ui/persona-panel.css?v=20260815-persona1";
    stylesheet.dataset.jarvisPersonaPanel = "true";
    document.head.appendChild(stylesheet);
  }

  function load() {
    try {
      return localStorage.getItem(STORAGE_KEY) || "padrao";
    } catch {
      return "padrao";
    }
  }

  function current() {
    return active;
  }

  function select(id) {
    if (!styles.some((row) => row.id === id)) return;
    active = id;
    try { localStorage.setItem(STORAGE_KEY, id); } catch { /* vale nesta aba */ }
    paint();
    window.dispatchEvent(new CustomEvent("jarvis-persona-style", { detail: { style: id } }));
  }

  function paint() {
    document.querySelectorAll("[data-persona-style]").forEach((button) => {
      button.dataset.active = String(button.dataset.personaStyle === active);
    });
    const label = styles.find((row) => row.id === active)?.label || "Padrão";
    const summary = document.getElementById("personaValue");
    if (summary) summary.textContent = label;
  }

  async function loadStyles() {
    try {
      const response = await fetch("/persona-styles", { headers: { Accept: "application/json" } });
      const data = await response.json();
      if (Array.isArray(data?.styles) && data.styles.length) styles = data.styles;
    } catch { /* o catálogo local já cobre */ }
  }

  function render() {
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.className = "persona-panel-dialog";
    dialog.innerHTML = `
      <div class="persona-panel-head">
        <strong>Personalidade</strong>
        <button type="button" data-persona-close aria-label="Fechar">×</button>
      </div>
      <p class="persona-panel-hint">
        A identidade é a mesma; o que muda é o jeito de responder. Vale também por comando:
        “muda sua personalidade”, “responde mais direto”.
      </p>
      <div class="persona-style-list"></div>
    `;
    dialog.addEventListener("click", (event) => {
      if (event.target.closest("[data-persona-close]")) dialog.close();
      const option = event.target.closest("[data-persona-style]");
      if (option) select(option.dataset.personaStyle);
    });
    document.body.appendChild(dialog);
    return dialog;
  }

  function fill() {
    const list = dialog?.querySelector(".persona-style-list");
    if (!list) return;
    list.innerHTML = styles
      .map((row) => `
        <button type="button" data-persona-style="${row.id}">
          <b>${row.label}</b>
          <small>${row.description || ""}</small>
        </button>
      `)
      .join("");
    paint();
  }

  async function open() {
    render();
    await loadStyles();
    fill();
    if (!dialog.open) dialog.showModal();
  }

  loadStyles().then(paint);

  return Object.freeze({ open, current, select, styles: () => styles.slice() });
})();
