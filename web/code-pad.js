"use strict";

const dialog = document.getElementById("codePadDialog");
const mount = document.getElementById("codePadMount");
const LANG_FILE = {
  js: "snippet.js", javascript: "snippet.js", ts: "snippet.ts", typescript: "snippet.ts",
  py: "snippet.py", python: "snippet.py", html: "snippet.html", css: "snippet.css",
  json: "snippet.json", bash: "snippet.sh", sh: "snippet.sh", zsh: "snippet.sh",
  rust: "snippet.rs", go: "snippet.go", sql: "snippet.sql", yaml: "snippet.yml",
  md: "snippet.md", markdown: "README.md", txt: "snippet.txt",
};
const VSCODE_URI = "vscode://theopadilha.jarvis-theo/from-clipboard";
const PACK_URL = "/download/vscode";
let loadedFences = [];

if (!document.querySelector("link[data-jarvis-code-pad]")) {
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "/ui/code-pad.css?v=20260819-bar1";
  stylesheet.dataset.jarvisCodePad = "true";
  document.head.appendChild(stylesheet);
}

function isWindows() {
  return /Windows/i.test(navigator.userAgent || "");
}

function pasteHint() {
  return isWindows()
    ? "No Windows: Ctrl+N e depois Ctrl+V no VS Code."
    : "No Mac: ⌘N e depois ⌘V no VS Code.";
}

function extractFences(text) {
  const fences = [];
  const source = String(text || "");
  const re = /```([^\n`]*)\n([\s\S]*?)```/g;
  let match;
  while ((match = re.exec(source))) {
    const lang = String(match[1] || "").trim().split(/\s+/)[0];
    const code = String(match[2] || "").replace(/\s+$/, "");
    if (code) fences.push({ lang, code });
  }
  return fences;
}

function lastJarvisText() {
  const nodes = document.querySelectorAll(".message.jarvis > span");
  return nodes.length ? (nodes[nodes.length - 1].innerText || "") : "";
}

function guessName(lang, code) {
  const hinted = String(code || "").match(/^(?:\/\/|#)\s*([A-Za-z0-9._/-]+\.[A-Za-z0-9]+)\s*$/m);
  if (hinted) return hinted[1].split("/").pop();
  return LANG_FILE[String(lang || "").toLowerCase()] || "snippet.txt";
}

function sanitizeFilename(name) {
  const clean = String(name || "snippet.txt").replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
  return (clean || "snippet") + (clean.includes(".") ? "" : ".txt");
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  }
}

function launchProtocol(uri) {
  const link = document.createElement("a");
  link.href = uri;
  link.rel = "noreferrer";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function setStatus(text) {
  const status = document.getElementById("codePadStatus");
  if (status) status.textContent = text;
}

function currentCode() {
  return document.getElementById("codePadBody")?.value || "";
}

function applyFence(fence) {
  const body = document.getElementById("codePadBody");
  const file = document.getElementById("codePadFilename");
  if (body) body.value = fence?.code || "";
  if (file && (!file.value || file.dataset.auto !== "0")) {
    file.value = guessName(fence?.lang, fence?.code);
    file.dataset.auto = "1";
  }
}

function fillSelect(fences) {
  const select = document.getElementById("codePadSelect");
  if (!select) return;
  select.hidden = fences.length < 2;
  select.replaceChildren();
  fences.forEach((fence, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${fence.lang || "código"} · ${fence.code.split("\n").length} linha(s)`;
    select.appendChild(option);
  });
}

async function copyCode() {
  const text = currentCode();
  if (!text.trim()) {
    setStatus("Nada para copiar. Cole um código ou peça no chat.");
    return false;
  }
  const ok = await copyText(text);
  setStatus(ok ? `Copiado. ${pasteHint()}` : "Não copiei sozinho. Selecione o texto e copie.");
  return ok;
}

async function pasteVSCode() {
  const ok = await copyCode();
  launchProtocol(VSCODE_URI);
  window.setTimeout(() => launchProtocol("vscode://"), 450);
  setStatus(
    (ok ? "Código na área de transferência. " : "Não copiei sozinho. ")
    + pasteHint()
    + " Se a extensão JARVIS Theo estiver instalada, o arquivo novo abre sozinho."
  );
}

function alterCode() {
  const body = document.getElementById("codePadBody");
  if (!body) return;
  body.readOnly = false;
  body.focus();
  body.setSelectionRange(body.value.length, body.value.length);
  setStatus("Altere o código aqui. Depois copie, cole no VS Code, use no terminal ou peça outra versão no chat.");
}

function askJarvis() {
  const input = document.getElementById("commandInput");
  const text = currentCode().trim();
  if (!input) return;
  input.value = text
    ? `altere este código com mais força, deixe pronto para colar:\n\`\`\`\n${text}\n\`\`\``
    : "abre o jarvis code e constrói o que eu pedi, com o arquivo pronto para o terminal";
  dialog?.close();
  input.focus();
}

async function useInTerminal() {
  const text = currentCode().trim();
  const win = isWindows();
  const launcher = win ? "jarvis-theo.cmd" : "jarvis-theo";
  const copied = await copyText(text || launcher);
  setStatus(
    copied
      ? (text
          ? `Código copiado. Cole no ${win ? "cmd ou PowerShell" : "Terminal.app"} e rode.`
          : `Copiei \`${launcher}\`. Cole no ${win ? "cmd/PowerShell" : "Terminal"}. Sem o comando no PATH, use Baixar JARVIS Theo.`)
      : "Não copiei sozinho. Use Baixar JARVIS Theo e rode o instalador."
  );
}

function downloadSnippet() {
  const text = currentCode();
  if (!text.trim()) {
    setStatus("Nada para baixar.");
    return;
  }
  const name = sanitizeFilename(document.getElementById("codePadFilename")?.value);
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  setStatus(`Baixei ${name}. Abra no VS Code no Mac ou no Windows.`);
}

function render() {
  if (!mount || mount.dataset.ready === "1") return;
  mount.dataset.ready = "1";
  mount.innerHTML = `
    <div class="dialog-head code-pad-head">
      <span><small>JARVIS CODE</small><b>Copiar · alterar · VS Code</b></span>
      <button id="codePadClose" type="button" aria-label="Fechar JARVIS Code">×</button>
    </div>
    <section class="code-pad-body">
      <p class="code-pad-hint" id="codePadHint">Tela pequena para copiar, alterar e colar no VS Code no Mac e no Windows. O JARVIS abre isto sozinho quando manda um bloco de código.</p>
      <form class="code-pad-form" id="codePadForm">
        <div class="code-pad-meta">
          <input id="codePadFilename" maxlength="80" placeholder="nome-do-arquivo.py" aria-label="Nome do arquivo" autocomplete="off">
          <select id="codePadSelect" hidden aria-label="Bloco de código"></select>
        </div>
        <textarea id="codePadBody" maxlength="120000" placeholder="O código aparece aqui. Altere antes de copiar ou colar no VS Code." aria-label="Código" spellcheck="false"></textarea>
        <div class="code-pad-actions">
          <button type="button" id="codePadTerminal">Usar no terminal</button>
          <button type="button" id="codePadPaste">Colar no VS Code</button>
          <button type="button" id="codePadAlter">Alterar</button>
          <button type="button" id="codePadAsk">Pedir ao JARVIS</button>
          <button type="button" id="codePadCopy">Copiar</button>
          <button type="button" id="codePadFile">Baixar arquivo</button>
        </div>
        <p class="code-pad-hint">Baixar JARVIS Code + terminal</p>
        <div class="code-pad-actions download-grid" id="codePadDownloads">
          <a href="/download/vscode/mac">Mac</a>
          <a href="/download/vscode/windows">Windows</a>
        </div>
      </form>
      <p class="code-pad-status" id="codePadStatus">Mac e Windows: copie, abra o VS Code e cole. A extensão JARVIS Theo cola num arquivo novo.</p>
    </section>
  `;
  document.getElementById("codePadClose")?.addEventListener("click", () => dialog?.close());
  document.getElementById("codePadTerminal")?.addEventListener("click", () => { useInTerminal(); });
  document.getElementById("codePadCopy")?.addEventListener("click", () => { copyCode(); });
  document.getElementById("codePadPaste")?.addEventListener("click", () => { pasteVSCode(); });
  document.getElementById("codePadAlter")?.addEventListener("click", alterCode);
  document.getElementById("codePadAsk")?.addEventListener("click", askJarvis);
  document.getElementById("codePadFile")?.addEventListener("click", downloadSnippet);
  document.getElementById("codePadFilename")?.addEventListener("input", (event) => {
    event.currentTarget.dataset.auto = "0";
  });
  document.getElementById("codePadSelect")?.addEventListener("change", (event) => {
    const index = Number(event.currentTarget.value || 0);
    if (loadedFences[index]) applyFence(loadedFences[index]);
  });
  document.getElementById("codePadForm")?.addEventListener("submit", (event) => event.preventDefault());
}

function openPad(detail = {}) {
  render();
  const incoming = String(detail.text || "");
  const fences = extractFences(incoming).concat(incoming.trim() ? [] : extractFences(lastJarvisText()));
  const unique = fences.length ? fences : (incoming.trim() ? [{ lang: "", code: incoming }] : []);
  loadedFences = unique;
  fillSelect(unique);
  applyFence(unique[0] || { lang: "", code: "" });
  if (detail.notice) setStatus(detail.notice);
  else if (unique[0]?.code) setStatus(`Bloco pronto. ${pasteHint()} Use no terminal ou no VS Code.`);
  else setStatus("Vazio. Peça um código, use no terminal (`jarvis-theo`) ou baixe o JARVIS Theo.");
  dialog?.showModal();
  window.setTimeout(() => {
    if (detail.terminal) useInTerminal();
    else if (!detail.auto) document.getElementById("codePadBody")?.focus();
  }, 30);
}

window.JarvisCodePad = Object.freeze({ open: openPad });
