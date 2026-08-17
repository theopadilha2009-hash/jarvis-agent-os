(() => {
  "use strict";
  const statusLine = document.getElementById("statusLine");
  const caption = document.getElementById("caption");
  const accessLine = document.getElementById("accessLine");
  const orb = document.getElementById("orb");
  const form = document.getElementById("askForm");
  const loginForm = document.getElementById("loginForm");
  const input = document.getElementById("askInput");
  const logoutButton = document.getElementById("logoutButton");
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const OWNER_TOKEN_KEY = "jarvis-owner-token-v1";
  const WAKE = /(?:^|\b)(?:oi|olá|ola)?\s*jarvis\b/i;
  let busy = false;
  let greeted = false;
  let keepListening = false;
  let armed = false;
  let rec = null;

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
    if (detail) caption.textContent = detail;
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

  function speak(text) {
    return fetch("/speech", {
      method: "POST",
      headers: apiHeaders(),
      body: JSON.stringify({ text }),
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
    })).catch(() => {
      if (!window.speechSynthesis) return;
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "pt-BR";
      window.speechSynthesis.speak(utterance);
    });
  }

  function greetOnce() {
    if (greeted) return;
    greeted = true;
    speak(`Oi. Eu sou o JARVIS de ${creator()}.`);
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
      return;
    }
    busy = true;
    say("Pensando…", command);
    try {
      const response = await fetch("/command", {
        method: "POST",
        headers: apiHeaders(),
        body: JSON.stringify({ command }),
      });
      const data = await response.json();
      const message = data.message || data.error || "Sem resposta.";
      if (response.status === 429) {
        say("Fila cheia.", message);
        return;
      }
      say(data.ok === false ? "Não consegui." : "Pronto.", message);
      if (data.ok !== false) speak(message);
    } catch {
      say("Falha de rede.", "Tente de novo em alguns segundos.");
    } finally {
      busy = false;
    }
  }

  function hearSpoken(spoken) {
    const text = String(spoken || "").trim();
    if (!text) return;
    if (WAKE.test(text)) {
      const command = text.replace(WAKE, "").replace(/^[,.\s]+/, "").trim();
      greetOnce();
      if (command) {
        armed = false;
        ask(command);
      } else {
        armed = true;
        say("Pode falar.", "Estou ouvindo o pedido.");
      }
      return;
    }
    if (armed) {
      armed = false;
      greetOnce();
      ask(text);
    }
  }

  function listenLoop() {
    if (!keepListening || !Recognition) return;
    rec = new Recognition();
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
        orb.classList.remove("listening");
        say("Microfone bloqueado.", "Toque no brilho e permita o microfone.");
        return;
      }
      if (keepListening) window.setTimeout(listenLoop, 700);
    };
    rec.onend = () => {
      if (keepListening) window.setTimeout(listenLoop, 220);
    };
    try {
      rec.start();
      orb.classList.add("listening");
    } catch {
      if (keepListening) window.setTimeout(listenLoop, 800);
    }
  }

  function startWakeLoop() {
    if (!Recognition) {
      input.focus();
      say("Sem microfone neste navegador.", "Escreva o pedido ou entre com login.");
      return;
    }
    if (keepListening) return;
    keepListening = true;
    say("Pode me chamar.", "Diga “oi Jarvis”.");
    listenLoop();
  }

  orb.addEventListener("click", () => {
    greetOnce(); // user-gesture: só gasta voz depois do toque
    startWakeLoop();
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    greetOnce();
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
      say("Informe login e senha.", "A mesma conta do cockpit.");
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
        say("Não entrei.", data.error || "Login inválido.");
        return;
      }
      localStorage.setItem(OWNER_TOKEN_KEY, data.session_token);
      document.getElementById("loginPass").value = "";
      await refreshAccess();
      greetOnce();
      startWakeLoop();
      say("Entrou.", data.message || "Sessão ativa neste app.");
    } catch {
      say("Falha de rede.", "Tente o login de novo.");
    }
  });
  logoutButton.addEventListener("click", () => {
    localStorage.removeItem(OWNER_TOKEN_KEY);
    refreshAccess();
    say("Saiu.", "Voltou ao modo visitante.");
  });
  document.querySelectorAll("[data-open]").forEach((button) => {
    button.addEventListener("click", () => {
      greetOnce();
      startWakeLoop();
      openTarget(button.getAttribute("data-open"));
    });
  });

  say(`Oi. Eu sou o JARVIS de ${creator()}.`, "Toque no brilho e diga “oi Jarvis”.");
  refreshAccess();
})();
