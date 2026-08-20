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
  const LAST_LOGIN_KEY = "jarvis-last-login";
  const REMEMBER_KEY = "jarvis-remember-login-v1";
  const OWNER_IDLE_KEY = "jarvis-owner-last-active";
  const LISTEN_KEY = "jarvis-fala-listen";
  const SHELL_VERSION = "20260820-update1";
  const WAKE = /(?:^|\b)(?:oi|ol[aá]|ei|hey|ok|eai|e a[ií])?\s*(?:jarvis|ultron)\b/i;
  const appMode = new URLSearchParams(window.location.search).get("app") === "1"
    || window.matchMedia("(display-mode: standalone)").matches;
  let busy = false;
  let keepListening = false;
  let armed = false;
  let armUntil = 0;
  let speaking = false;
  let recHandle = null;

  if (appMode) document.documentElement.classList.add("app-mode");

  const creator = () => window.JarvisCreator?.name?.() || "Theo Lorentz Padilha";

  function ownerToken() {
    try { return window.localStorage.getItem(OWNER_TOKEN_KEY) || ""; } catch { return ""; }
  }

  function rememberLoginEnabled() {
    try { return window.localStorage.getItem(REMEMBER_KEY) !== "0"; } catch { return true; }
  }

  function persistSession(token, username) {
    try {
      if (token) window.localStorage.setItem(OWNER_TOKEN_KEY, token);
      if (username) window.localStorage.setItem(LAST_LOGIN_KEY, username);
      window.localStorage.setItem(REMEMBER_KEY, rememberLoginEnabled() ? "1" : "0");
      window.localStorage.setItem(OWNER_IDLE_KEY, String(Date.now()));
    } catch { /* private mode */ }
  }

  function apiHeaders() {
    const headers = { "Content-Type": "application/json" };
    const token = ownerToken();
    if (token) headers["X-Jarvis-Owner-Token"] = token;
    return headers;
  }

  async function postJson(path, payload) {
    let lastError = "Sem rede.";
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const response = await fetch(path, {
          method: "POST",
          headers: apiHeaders(),
          body: JSON.stringify(payload),
          signal: window.AbortSignal?.timeout ? window.AbortSignal.timeout(path === "/command" ? 22000 : 14000) : undefined,
        });
        const data = await response.json().catch(() => ({ ok: false, error: "Resposta inválida." }));
        if (response.status >= 500 && attempt === 0) {
          lastError = data.error || "Servidor ocupado.";
          await new Promise((resolve) => window.setTimeout(resolve, 350));
          continue;
        }
        return { response, data };
      } catch (error) {
        lastError = navigator.onLine === false ? "Você está offline." : "Falha de rede.";
        if (attempt === 0) await new Promise((resolve) => window.setTimeout(resolve, 350));
      }
    }
    return { response: { status: 0, ok: false }, data: { ok: false, error: lastError, retryable: true } };
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

  function showAnswerLink(prefix, href, label) {
    lastAnswer.hidden = false;
    lastAnswer.textContent = "";
    if (prefix) lastAnswer.append(document.createTextNode(`${prefix} `));
    const link = document.createElement("a");
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = label;
    lastAnswer.append(link);
  }

  function applyPersona(label) {
    const ultron = /ultron/i.test(String(label || ""));
    document.documentElement.dataset.persona = ultron ? "ultron" : "jarvis";
  }

  function clearStaleSession() {
    try { window.localStorage.removeItem(OWNER_TOKEN_KEY); } catch { /* private */ }
  }

  function renderAccess(label, signedIn) {
    accessLine.textContent = label;
    applyPersona(label);
    const inSession = Boolean(signedIn);
    document.documentElement.classList.toggle("signed-in", inSession);
    const loginToggle = document.getElementById("loginToggle");
    if (loginToggle) loginToggle.hidden = inSession;
    logoutButton.hidden = !inSession;
    loginForm.querySelector("#loginUser").hidden = inSession;
    loginForm.querySelector("#loginPass").hidden = inSession;
    loginForm.querySelector("button[type='submit']").hidden = inSession;
    const remember = document.getElementById("rememberLogin");
    if (remember) remember.closest("label").hidden = inSession;
  }

  async function refreshAccess() {
    if (!ownerToken()) {
      renderAccess("Visitante", false);
      return;
    }
    try {
      const data = await fetch("/status", { headers: apiHeaders() }).then((row) => row.json());
      const mode = data.access?.mode;
      if (mode !== "owner" && mode !== "member") {
        clearStaleSession();
        renderAccess("Visitante", false);
        return;
      }
      renderAccess(mode === "owner" ? "Ultron" : "Conta JARVIS", true);
    } catch {
      renderAccess("Sessão", Boolean(ownerToken()));
    }
  }

  function speakLocal(text) {
    if (!window.speechSynthesis) return Promise.resolve();
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "pt-BR";
    return new Promise((resolve) => {
      utterance.onend = resolve;
      utterance.onerror = resolve;
      window.speechSynthesis.speak(utterance);
    });
  }

  function playBlob(blob) {
    return new Promise((resolve) => {
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      const finish = () => {
        orb.classList.remove("speaking");
        URL.revokeObjectURL(url);
        resolve();
      };
      audio.addEventListener("ended", finish, { once: true });
      audio.addEventListener("error", finish, { once: true });
      orb.classList.add("speaking");
      audio.play().catch(finish);
    });
  }

  function nativeHandlers() {
    try { return window.webkit && window.webkit.messageHandlers; } catch { return null; }
  }

  function hasNativeSpeak() {
    return Boolean(nativeHandlers() && nativeHandlers().jarvisSpeak);
  }

  function hasNativeListen() {
    return Boolean(nativeHandlers() && nativeHandlers().jarvisListen);
  }

  function muteMicForSpeech() {
    speaking = true;
    armed = false;
    try { recHandle && recHandle.stop(); } catch { /* already stopped */ }
    try { nativeHandlers()?.jarvisListen.postMessage("stop"); } catch { /* web */ }
  }

  function unmuteMicAfterSpeech() {
    speaking = false;
    keepArmed();
    if (keepListening) listenLoop();
  }

  function speak(text) {
    const clip = String(text || "").replace(/\s+/g, " ").trim().slice(0, 220);
    if (!clip) return Promise.resolve();
    muteMicForSpeech();
    if (hasNativeSpeak()) {
      return new Promise((resolve) => {
        const timer = window.setTimeout(resolve, 20_000);
        window.__jarvisOnSpeakDone = () => {
          window.clearTimeout(timer);
          window.__jarvisOnSpeakDone = null;
          resolve();
        };
        try { nativeHandlers().jarvisSpeak.postMessage(clip); } catch { resolve(); }
      }).finally(() => unmuteMicAfterSpeech());
    }
    const persona = ownerToken() ? "ultron" : "jarvis";
    return Promise.resolve(window.JarvisLocalVoice?.speakBlob(clip, { persona }))
      .then((localBlob) => {
        if (localBlob) return playBlob(localBlob);
        return fetch("/speech", {
          method: "POST",
          headers: apiHeaders(),
          body: JSON.stringify({ text: clip, persona }),
        }).then((response) => {
          if (!response.ok) throw new Error("speech");
          return response.blob();
        }).then((blob) => playBlob(blob));
      })
      .catch(() => speakLocal(clip))
      .finally(() => unmuteMicAfterSpeech());
  }

  let lastOpenUrl = "";
  let lastError = "";
  let lastCommand = "";

  function openTarget(url) {
    lastOpenUrl = url;
    const popup = window.open(url, "_blank", "noopener,noreferrer");
    if (popup) return true;
    showAnswerLink("Popup bloqueado.", url, "Toque para abrir");
    return false;
  }

  function localClock() {
    return new Date().toLocaleString("pt-BR", {
      weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit",
    });
  }

  function remainderAfter(value, match) {
    const rest = String(match || "").replace(/\s+(?:pra mim|para mim|por favor)$/i, "").trim();
    if (!rest || /^(?:o|a|o youtube|youtube|mapa|maps)$/i.test(rest)) return "";
    return rest;
  }

  function isMacSpotifyCommand(value) {
    const text = String(value || "").toLocaleLowerCase("pt-BR");
    if (/\b(?:homem\s+de\s+ferro|iron\s+man|spotify:track:)\b/.test(text)) return true;
    if (/\bspotify\b/.test(text) && /\b(?:com|paus|to(?:c|q)|play|pr[oó]xim|volum|status|aleat|shuffle|repet)\w*/.test(text)) return true;
    return false;
  }

  function resolveOpen(text) {
    const value = String(text || "").toLocaleLowerCase("pt-BR").trim();
    if (isMacSpotifyCommand(value)) return null;
    const google = value.match(/^(?:google|pesquisa no google|busca no google)\s+(.+)/);
    if (google) return { url: `https://www.google.com/search?q=${encodeURIComponent(google[1])}`, label: "Google" };
    const youtubeSearch = value.match(/^(?:pesquisa|busca|procura)\s+(?:no\s+)?youtube\s+(.+)/)
      || value.match(/^(?:abre|abrir|abra|inici(?:a|e|ar))\s+(?:o\s+)?youtube\s+(?:de|do|da|das|dos|sobre)\s+(.+)/)
      || value.match(/^(?:abre|abrir|abra|inici(?:a|e|ar))\s+(?:o\s+)?youtube\s+(.+)/);
    if (youtubeSearch) {
      const query = remainderAfter(value, youtubeSearch[1]);
      if (query) return { url: `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`, label: "YouTube" };
    }
    const mapsSearch = value.match(/^(?:como chegar(?:\s+(?:em|no|na|ao|à|a))?)\s+(.+)/)
      || value.match(/^(?:abre|abrir|abra)\s+(?:o\s+)?(?:mapa|maps)\s+(?:de|para|em|no|na)\s+(.+)/);
    if (mapsSearch) {
      const query = remainderAfter(value, mapsSearch[1]);
      if (query) return { url: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`, label: "Maps" };
    }
    const opening = /\b(?:abre|abrir|abra|inici(?:a|e|ar))\b/.test(value);
    if (!opening) return null;
    const targets = [
      [/\bwhatsapp\b/, "https://web.whatsapp.com", "WhatsApp"],
      [/\byoutube\b/, "https://www.youtube.com", "YouTube"],
      [/\bspotify\b/, "https://open.spotify.com", "Spotify"],
      [/\b(?:mapa|maps|como chegar)\b/, "https://maps.google.com", "Google Maps"],
      [/\bcalend[aá]rio|agenda\b/, "https://calendar.google.com", "Agenda"],
      [/\b(?:o\s+)?gmail\b/, "https://mail.google.com", "Gmail"],
      [/\bgithub\b/, "https://github.com", "GitHub"],
      [/\b(?:instagram|insta)\b/, "https://www.instagram.com", "Instagram"],
      [/\b(?:chat\s*gpt|chatgpt)\b/, "https://chatgpt.com", "ChatGPT"],
      [/\b(?:google\s+)?drive\b/, "https://drive.google.com", "Drive"],
      [/\bdiscord\b/, "https://discord.com/app", "Discord"],
      [/\bnotion\b/, "https://www.notion.so", "Notion"],
      [/\btwitter\b|(?:abre|abrir|abra)\s+(?:o\s+)?x\b/, "https://x.com", "X"],
      [/\bgoogle\b/, "https://www.google.com", "Google"],
    ];
    for (const [pattern, url, label] of targets) {
      if (pattern.test(value)) return { url, label };
    }
    return null;
  }

  function revealLogin() {
    extras.hidden = false;
    moreButton.textContent = "fechar";
    document.getElementById("loginUser")?.focus();
    say("Login.", "Mesma conta do cockpit.");
  }

  function localAction(text) {
    const value = String(text || "").toLocaleLowerCase("pt-BR");
    if (/^(?:entrar|login|fazer login|conectar)$/.test(value.trim())) return () => revealLogin();
    const opened = resolveOpen(value);
    if (opened) return () => openTarget(opened.url);
    if (/\bhoras?\b|\bque dia\b|\bdata de hoje\b/.test(value)) {
      return () => {
        const now = localClock();
        say("Agora.", now);
        showAnswer(now);
        speak(now);
      };
    }
    if (/^copia/.test(value)) {
      return () => {
        const textToCopy = lastAnswer.textContent || "";
        if (textToCopy && navigator.clipboard?.writeText) navigator.clipboard.writeText(textToCopy);
        say("Copiado.", textToCopy || "Nada ainda.");
      };
    }
    if (/\bcockpit\b|\bjanela grande\b/.test(value)) return () => { window.location.href = "/"; };
    return null;
  }

  async function ask(text) {
    const command = String(text || "").trim();
    if (!command || busy) return;
    lastCommand = command;
    if (navigator.onLine === false) {
      const local = localAction(command);
      if (local) {
        local();
        keepArmed();
        return;
      }
      say("Offline.", "Sem internet para o restante.");
      speak("Sem internet");
      return;
    }
    const local = localAction(command);
    if (local) {
      local();
      if (!/\bhoras?\b|\bque dia\b|\bdata de hoje\b|^copia|^(?:entrar|login|fazer login|conectar)$/.test(command.toLocaleLowerCase("pt-BR"))) {
        say("Aberto.", command);
        speak("Aberto");
        return;
      }
      if (!/\bhoras?\b|\bque dia\b|\bdata de hoje\b/.test(command.toLocaleLowerCase("pt-BR"))) keepArmed();
      return;
    }
    busy = true;
    say("…", command);
    const { response, data } = await postJson("/command", {
      command,
      strength: ownerToken() ? "strong" : "auto",
    });
    const message = data.message || data.error || "Sem resposta.";
    lastError = data.ok === false ? message : "";
    const retry = document.getElementById("retryButton");
    if (retry) retry.hidden = !lastError;
    if (response.status === 401 || data.pairing_required) {
      clearStaleSession();
      renderAccess("Visitante", false);
      revealLogin();
    }
    const opened = data.client_action === "open_url" && data.open_url ? openTarget(data.open_url) : false;
    if (data.client_action === "quiet_mode") {
      keepListening = false;
      armed = false;
      orb.classList.remove("listening");
    }
    if (response.status === 429) {
      say("Limite.", message);
      busy = false;
      return;
    }
    say(data.ok === false ? "Não." : (data.client_action === "quiet_mode" ? "Modo foco." : "Pronto."), data.client_action === "quiet_mode" ? "Toque no brilho quando quiser de volta." : "");
    if (data.status_real === "free_web_search_unavailable") {
      showAnswerLink(message, `https://www.google.com/search?q=${encodeURIComponent(command)}`, "Buscar no Google");
    } else if (!opened) {
      showAnswer(message);
    }
    busy = false;
    await speak(message);
  }

  function keepArmed() {
    armed = true;
    armUntil = Date.now() + 8000;
  }

  window.__jarvisNativeHeard = function (spoken) {
    hearSpoken(spoken);
  };

  function hearSpoken(spoken) {
    if (speaking) return;
    const text = String(spoken || "").trim();
    if (!text) return;
    if (WAKE.test(text)) {
      const command = text.replace(WAKE, "").replace(/^[,.\s]+/, "").trim();
      keepArmed();
      if (command) ask(command);
      else say("Pode falar.", "");
      return;
    }
    if (armed && Date.now() <= armUntil) {
      keepArmed();
      ask(text);
    }
  }

  function listenLoop() {
    if (!keepListening || speaking) return;
    if (hasNativeListen()) {
      try { nativeHandlers().jarvisListen.postMessage("start"); } catch { /* web */ }
      orb.classList.add("listening");
      say("Ouvindo.", "“oi Jarvis”.");
      return;
    }
    if (!Recognition) return;
    const rec = new Recognition();
    recHandle = rec;
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
        recHandle = null;
        orb.classList.remove("listening");
        say("Mic.", "Toque no brilho e permita.");
        return;
      }
      if (keepListening && !speaking) window.setTimeout(listenLoop, 500);
    };
    rec.onend = () => {
      if (recHandle === rec) recHandle = null;
      if (keepListening && !speaking) window.setTimeout(listenLoop, 180);
    };
    try {
      rec.start();
      orb.classList.add("listening");
      say("Ouvindo.", "“oi Jarvis”.");
    } catch {
      if (keepListening && !speaking) window.setTimeout(listenLoop, 600);
    }
  }

  function persistListen(on) {
    try {
      if (on) window.localStorage.setItem(LISTEN_KEY, "1");
      else window.localStorage.setItem(LISTEN_KEY, "0");
    } catch { /* private */ }
  }

  function wantsListen() {
    try {
      const stored = window.localStorage.getItem(LISTEN_KEY);
      if (stored === "0") return false;
      if (appMode) return true;
      return stored === "1";
    } catch {
      return appMode;
    }
  }

  function startWakeLoop(options) {
    const silent = Boolean(options && options.silent);
    if (!Recognition && !hasNativeListen()) {
      if (!silent) {
        input.focus();
        say("Escreva.", "Sem microfone aqui.");
      }
      return;
    }
    if (keepListening) return;
    keepListening = true;
    persistListen(true);
    say("Ouvindo.", "“oi Jarvis”.");
    listenLoop();
  }

  function stopWakeLoop() {
    keepListening = false;
    armed = false;
    persistListen(false);
    orb.classList.remove("listening");
    say("Parei.", "Toque no brilho para ouvir de novo.");
  }

  function tryAutoListen() {
    if (!wantsListen()) return;
    if (hasNativeListen()) {
      startWakeLoop({ silent: true });
      return;
    }
    if (!Recognition) return;
    const start = () => startWakeLoop({ silent: true });
    const permissions = navigator.permissions;
    if (permissions && permissions.query) {
      Promise.resolve(permissions.query({ name: "microphone" })).then((status) => {
        if (status.state === "denied") {
          say("Mic.", "Toque no brilho e permita.");
          return;
        }
        if (status.state === "granted" || appMode) start();
        status.onchange = () => { if (status.state === "granted") start(); };
      }).catch(start);
      return;
    }
    if (appMode) start();
  }

  moreButton.addEventListener("click", () => {
    extras.hidden = !extras.hidden;
    moreButton.textContent = extras.hidden ? "mais" : "fechar";
  });
  document.getElementById("loginToggle")?.addEventListener("click", () => {
    revealLogin();
  });
  document.getElementById("retryButton")?.addEventListener("click", () => {
    if (lastCommand) ask(lastCommand);
  });
  document.getElementById("debugToggle")?.addEventListener("click", () => {
    mountDebug(true);
  });
  orb.addEventListener("click", () => {
    startWakeLoop(); // user-gesture — never persist off
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
      const keep = document.getElementById("rememberLogin");
      try { localStorage.setItem(REMEMBER_KEY, keep && !keep.checked ? "0" : "1"); } catch { /* ignore */ }
      persistSession(data.session_token, username);
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

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      extras.hidden = true;
      moreButton.textContent = "mais";
    }
    if (event.key === "/" && document.activeElement !== input && document.activeElement?.tagName !== "INPUT") {
      event.preventDefault();
      input.focus();
    }
  });
  window.addEventListener("offline", () => say("Offline.", "Atalhos locais ainda funcionam."));
  window.addEventListener("online", () => say("Online.", "Pode pedir de novo."));
  try {
    const remembered = localStorage.getItem(LAST_LOGIN_KEY);
    const user = document.getElementById("loginUser");
    if (remembered && user) user.value = remembered;
    const keep = document.getElementById("rememberLogin");
    if (keep) keep.checked = rememberLoginEnabled();
  } catch { /* first visit */ }
  say("oi Jarvis", "toque no brilho e permita o microfone");
  refreshAccess();
  refreshVoiceChip();
  watchShellVersion();
  window.setInterval(refreshVoiceChip, 8000);
  tryAutoListen();
  if (/[?&]debug=1(?:&|$)/.test(location.search)) mountDebug(false);

  function restartForUpdate() {
    try {
      const native = nativeHandlers() && nativeHandlers().jarvisRestart;
      if (native) {
        native.postMessage("now");
        return;
      }
    } catch { /* web */ }
    const url = new URL(location.href);
    url.searchParams.set("r", Date.now().toString(36));
    location.replace(url.href);
  }

  function paintShellVersion(live) {
    const localLabel = `v${SHELL_VERSION}`;
    const stale = Boolean(live && live !== SHELL_VERSION);
    const line = document.getElementById("buildLine");
    if (line) {
      line.textContent = stale ? `${localLabel} · desatualizada` : localLabel;
      line.dataset.state = stale ? "stale" : "current";
      line.hidden = false;
    }
    const toast = document.getElementById("updateToast");
    if (!toast) return;
    toast.hidden = !stale;
    const versions = document.getElementById("updateToastVersions");
    if (versions && stale) versions.textContent = `você ${localLabel} · no ar v${live}`;
  }

  async function checkShellVersion() {
    try {
      const response = await fetch("/status", { headers: apiHeaders() });
      const data = await response.json().catch(() => ({}));
      paintShellVersion(data?.shell?.version || "");
    } catch {
      paintShellVersion("");
    }
  }

  function watchShellVersion() {
    paintShellVersion("");
    checkShellVersion();
    window.setInterval(checkShellVersion, 60 * 1000);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) checkShellVersion();
    });
    document.getElementById("updateReloadButton")?.addEventListener("click", restartForUpdate);
  }

  function refreshVoiceChip() {
    const chip = document.getElementById("voiceChip");
    if (!chip || !window.JarvisLocalVoice?.probe) return;
    Promise.resolve(window.JarvisLocalVoice.probe()).then(() => {
      chip.hidden = false;
      chip.textContent = hasNativeSpeak() ? "voz JARVIS" : "voz local";
      chip.dataset.state = "local";
    }).catch(() => {
      chip.hidden = false;
      chip.textContent = hasNativeSpeak() ? "voz JARVIS" : "voz local";
      chip.dataset.state = "local";
    });
  }

  function mountDebug(fromButton) {
    if (document.getElementById("jarvisDebug")) return;
    const box = document.createElement("pre");
    box.id = "jarvisDebug";
    box.style.cssText = "position:fixed;left:8px;bottom:8px;z-index:99;max-width:92vw;margin:0;font:11px/1.35 ui-monospace,monospace;background:#000c;color:#c4b5fd;padding:8px;border-radius:8px;white-space:pre-wrap";
    const paint = () => {
      const tts = window.JarvisLocalVoice?.info?.() || {};
      box.textContent = [
        "debug fala",
        `shell ${SHELL_VERSION}`,
        `token ${ownerToken() ? "sim" : "não"}`,
        `remember ${rememberLoginEnabled() ? "sim" : "não"}`,
        `persona ${document.documentElement.dataset.persona || "—"}`,
        `tts ${tts.ok ? `${tts.engine || "ok"} ${tts.voice || ""}`.trim() : "offline"}`,
        `lastOpen ${lastOpenUrl || "—"}`,
        `lastCommand ${lastCommand || "—"}`,
        `lastError ${lastError || "—"}`,
        fromButton ? "via diagnóstico" : "via ?debug=1",
      ].join("\n");
    };
    document.body.appendChild(box);
    paint();
    window.setInterval(paint, 2000);
  }
})();
