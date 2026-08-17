(() => {
  "use strict";
  const statusLine = document.getElementById("statusLine");
  const caption = document.getElementById("caption");
  const lastAnswer = document.getElementById("lastAnswer");
  const accessLine = document.getElementById("accessLine");
  const orb = document.getElementById("orb");
  const form = document.getElementById("askForm");
  const extras = document.getElementById("extras");
  const moreButton = document.getElementById("moreButton");
  const loginForm = document.getElementById("loginForm");
  const input = document.getElementById("askInput");
  const logoutButton = document.getElementById("logoutButton");
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const OWNER_TOKEN_KEY = "jarvis-owner-token-v1";
  const LISTEN_KEY = "jarvis-fala-listen";
  const WAKE = /(?:^|\b)(?:oi|olá|ola)?\s*jarvis\b/i;
  const appMode = new URLSearchParams(window.location.search).get("app") === "1"
    || window.matchMedia("(display-mode: standalone)").matches;
  let busy = false;
  let keepListening = false;
  let armed = false;

  if (appMode) document.documentElement.classList.add("app-mode");

  const creator = () => window.JarvisCreator?.name?.() || "Theo Lorentz Padilha";

  function ownerToken() {
    try { return window.localStorage.getItem(OWNER_TOKEN_KEY) || ""; } catch { return ""; }
  }

  function apiHeaders() {
    const headers = { "Content-Type": "application/json" };
    const token = ownerToken();
    if (token) headers["X-Jarvis-Owner-Token"] = token;
    return headers;
  }

  function say(title, detail) {
    statusLine.textContent = title;
    if (detail !== undefined) caption.textContent = detail;
  }

  function showAnswer(text) {
    const clean = String(text || "").replace(/\s+/g, " ").trim();
    if (!clean) return;
    lastAnswer.hidden = false;
    lastAnswer.textContent = clean.length > 180 ? `${clean.slice(0, 177)}…` : clean;
  }

  function renderAccess(label) {
    accessLine.textContent = label;
    const inSession = Boolean(ownerToken());
    logoutButton.hidden = !inSession;
    loginForm.querySelector("#loginUser").hidden = inSession;
    loginForm.querySelector("#loginPass").hidden = inSession;
    loginForm.querySelector("button[type='submit']").hidden = inSession;
  }

  async function refreshAccess() {
    if (!ownerToken()) {
      renderAccess("Visitante");
      return;
    }
    try {
      const data = await fetch("/status", { headers: apiHeaders() }).then((row) => row.json());
      const mode = data.access?.mode;
      renderAccess(mode === "owner" ? "Ultron" : mode === "member" ? "Conta JARVIS" : "Visitante");
    } catch {
      renderAccess("Sessão");
    }
  }

  function speakLocal(text) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "pt-BR";
    window.speechSynthesis.speak(utterance);
  }

  function speak(text) {
    const clip = String(text || "").replace(/\s+/g, " ").trim().slice(0, 220);
    if (!clip) return Promise.resolve();
    return fetch("/speech", {
      method: "POST",
      headers: apiHeaders(),
      body: JSON.stringify({ text: clip }),
    }).then((response) => {
      if (!response.ok) throw new Error("speech");
      return response.blob();
    }).then((blob) => new Promise((resolve) => {
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      const finish = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
      audio.addEventListener("ended", finish, { once: true });
      audio.addEventListener("error", finish, { once: true });
      audio.play().catch(finish);
    })).catch(() => speakLocal(clip));
  }

  function openTarget(url) {
    window.open(url, "_blank", "noopener,noreferrer");
  }

  function localAction(text) {
    const value = String(text || "").toLocaleLowerCase("pt-BR");
    if (/\bwhatsapp\b/.test(value)) return () => openTarget("https://web.whatsapp.com");
    if (/\byoutube\b/.test(value)) return () => openTarget("https://www.youtube.com");
    if (/\b(?:abre|abrir|abra)\s+(?:o\s+)?gmail\b/.test(value)) return () => openTarget("https://mail.google.com");
    const search = value.match(/(?:pesquisa|busca|google)\s+(.+)/);
    if (search) return () => openTarget(`https://www.google.com/search?q=${encodeURIComponent(search[1])}`);
    if (/^(?:abre|abrir|abra)\s+(?:o\s+)?google\b/.test(value)) return () => openTarget("https://www.google.com");
    if (/\bcockpit\b|\bjanela grande\b/.test(value)) return () => { window.location.href = "/"; };
    return null;
  }

  async function ask(text) {
    const command = String(text || "").trim();
    if (!command || busy) return;
    const local = localAction(command);
    if (local) {
      local();
      say("Aberto.", command);
      speakLocal("Aberto");
      return;
    }
    busy = true;
    say("…", command);
    try {
      const response = await fetch("/command", {
        method: "POST",
        headers: apiHeaders(),
        body: JSON.stringify({ command }),
      });
      const data = await response.json();
      const message = data.message || data.error || "Sem resposta.";
      if (response.status === 429) {
        say("Limite.", message);
        return;
      }
      say(data.ok === false ? "Não." : "Pronto.", "");
      showAnswer(message);
      if (data.ok !== false) speak(message);
    } catch {
      say("Rede.", "Tente de novo.");
    } finally {
      busy = false;
    }
  }

  function hearSpoken(spoken) {
    const text = String(spoken || "").trim();
    if (!text) return;
    if (WAKE.test(text)) {
      const command = text.replace(WAKE, "").replace(/^[,.\s]+/, "").trim();
      if (command) {
        armed = false;
        ask(command);
      } else {
        armed = true;
        say("Pode falar.", "");
      }
      return;
    }
    if (armed) {
      armed = false;
      ask(text);
    }
  }

  function listenLoop() {
    if (!keepListening || !Recognition) return;
    const rec = new Recognition();
    rec.lang = "pt-BR";
    rec.continuous = true;
    rec.interimResults = false;
    rec.onresult = (event) => {
      const last = event.results?.[event.results.length - 1];
      hearSpoken(last?.[0]?.transcript || "");
    };
    rec.onerror = (event) => {
      if (event.error === "not-allowed") {
        keepListening = false;
        try { sessionStorage.removeItem(LISTEN_KEY); } catch { /* private */ }
        orb.classList.remove("listening");
        say("Mic.", "Toque no brilho e permita.");
        return;
      }
      if (keepListening) window.setTimeout(listenLoop, 500);
    };
    rec.onend = () => {
      if (keepListening) window.setTimeout(listenLoop, 180);
    };
    try {
      rec.start();
      orb.classList.add("listening");
    } catch {
      if (keepListening) window.setTimeout(listenLoop, 600);
    }
  }

  function startWakeLoop() {
    if (!Recognition) {
      input.focus();
      say("Escreva.", "Sem microfone aqui.");
      return;
    }
    if (keepListening) return;
    keepListening = true;
    try { sessionStorage.setItem(LISTEN_KEY, "1"); } catch { /* private */ }
    say("Ouvindo.", "“oi Jarvis”.");
    listenLoop();
  }

  moreButton.addEventListener("click", () => {
    extras.hidden = !extras.hidden;
    moreButton.textContent = extras.hidden ? "conta" : "fechar";
  });
  orb.addEventListener("click", () => {
    startWakeLoop(); // user-gesture
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    startWakeLoop();
    const value = input.value;
    input.value = "";
    ask(value);
  });
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = document.getElementById("loginUser").value.trim();
    const password = document.getElementById("loginPass").value;
    if (!username || !password) {
      say("Login.", "Mesma conta do cockpit.");
      return;
    }
    try {
      const response = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json();
      if (!response.ok || !data.session_token) {
        say("Não.", data.error || "Login inválido.");
        return;
      }
      localStorage.setItem(OWNER_TOKEN_KEY, data.session_token);
      document.getElementById("loginPass").value = "";
      await refreshAccess();
      startWakeLoop();
      say("Entrou.", "");
    } catch {
      say("Rede.", "Tente o login de novo.");
    }
  });
  logoutButton.addEventListener("click", () => {
    localStorage.removeItem(OWNER_TOKEN_KEY);
    refreshAccess();
    say("Saiu.", "Visitante.");
  });
  document.querySelectorAll("[data-open]").forEach((button) => {
    button.addEventListener("click", () => {
      startWakeLoop();
      openTarget(button.getAttribute("data-open"));
    });
  });

  say("Oi.", `Toque e diga “oi Jarvis”.`);
  caption.textContent = appMode ? "Widget no canto." : `Toque e diga “oi Jarvis”.`;
  refreshAccess();
  try {
    if (sessionStorage.getItem(LISTEN_KEY) === "1") startWakeLoop();
  } catch { /* first visit */ }
})();
