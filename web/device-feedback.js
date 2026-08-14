"use strict";

const pollDelay = (attempt) => Math.min(1200, 250 + (attempt * 190));

function mountOfflineActions({ message, dialog, refresh, onConnected }) {
  const actions = document.createElement("div");
  actions.className = "message-actions";
  actions.innerHTML = '<button class="copy-response worker-diagnostic" type="button">Verificar Mac</button><button class="copy-command worker-settings" type="button">Abrir sistema</button>';
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
}

window.JarvisDeviceFeedback = Object.freeze({ pollDelay, mountOfflineActions });
