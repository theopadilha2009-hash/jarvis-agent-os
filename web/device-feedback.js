"use strict";

const pollDelay = (attempt) => Math.min(1200, 250 + (attempt * 190));

function mountOfflineActions({ message, dialog, refresh, onConnected }) {
  const actions = document.createElement("div");
  actions.className = "message-actions";
  actions.innerHTML = '<button class="copy-response worker-diagnostic" type="button">Verificar Mac</button><button class="copy-command worker-settings" type="button">Abrir sistema</button><button class="copy-command worker-install" type="button">Como instalar</button>';
  message.appendChild(actions);

  const diagnostic = actions.querySelector(".worker-diagnostic");
  diagnostic.addEventListener("click", async () => {
    diagnostic.disabled = true;
    diagnostic.textContent = "Verificando…";
    if (await refresh()) {
      diagnostic.textContent = "Mac conectado";
      message.classList.remove("error");
      onConnected();
      return;
    }
    diagnostic.disabled = false;
    diagnostic.textContent = "Ainda offline · verificar de novo";
  });

  actions.querySelector(".worker-settings").addEventListener("click", () => {
    if (!dialog.open) dialog.showModal();
    window.setTimeout(() => document.getElementById("workerValue")?.scrollIntoView({ block: "center" }), 30);
  });
  actions.querySelector(".worker-install")?.addEventListener("click", async () => {
    const hint = "./jarvis computer-worker --install";
    try {
      await navigator.clipboard.writeText(hint);
    } catch { /* ignore */ }
    const span = message.querySelector("span");
    if (span) span.textContent = "No Mac: baixe o App e rode INSTALAR.command, ou no repo execute ./jarvis computer-worker --install.";
  });
}

window.JarvisDeviceFeedback = Object.freeze({ pollDelay, mountOfflineActions });
