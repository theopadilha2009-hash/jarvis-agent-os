(() => {
  "use strict";
  const statusLine = document.getElementById("statusLine");
  const caption = document.getElementById("caption");
  const orb = document.getElementById("orb");
  const form = document.getElementById("askForm");
  const input = document.getElementById("askInput");
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const OWNER_TOKEN_KEY = "jarvis-owner-token-v1";
  let busy = false;
  let listening = false;
  let greeted = false;

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

  function hear() {
    if (!Recognition) {
      input.focus();
      say("Sem microfone neste navegador.", "Escreva o pedido abaixo.");
      return;
    }
    const rec = new Recognition();
    rec.lang = "pt-BR";
    rec.interimResults = false;
    listening = true;
    orb.classList.add("listening");
    say("Estou ouvindo.", "Pode falar.");
    rec.onresult = (event) => {
      const spoken = event.results?.[0]?.[0]?.transcript || "";
      const cleaned = spoken.replace(/^(?:oi|olá|ola)\s+/i, "").replace(/^jarvis[,.\s]+/i, "").trim();
      ask(cleaned || spoken);
    };
    rec.onerror = () => {
      listening = false;
      orb.classList.remove("listening");
      say("Não ouvi.", "Toque de novo no brilho.");
    };
    rec.onend = () => {
      listening = false;
      orb.classList.remove("listening");
    };
    try {
      rec.start();
    } catch {
      listening = false;
      orb.classList.remove("listening");
      say("Microfone bloqueado.", "Permita o microfone ou escreva.");
    }
  }

  orb.addEventListener("click", () => {
    greetOnce(); // user-gesture: só gasta voz depois do toque
    if (listening) return;
    hear();
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    greetOnce();
    const value = input.value;
    input.value = "";
    ask(value);
  });
  document.querySelectorAll("[data-open]").forEach((button) => {
    button.addEventListener("click", () => {
      greetOnce();
      openTarget(button.getAttribute("data-open"));
    });
  });

  say(`Oi. Eu sou o JARVIS de ${creator()}.`, "Diga “oi Jarvis” ou toque no brilho.");
})();
