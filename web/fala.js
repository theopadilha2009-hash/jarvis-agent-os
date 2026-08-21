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
  const SHELL_VERSION = "20260821-one1";
  const WAKE_NAME = /\b(?:jarvis|jarvius|jarbis|javis|jarbas|jarvas|jarves|gervis|gerivis|charvis|yarvis|ultron|ja vis|ja viu)\b/;
  const WAKE_CALL = /(?:^|\s)(?:oi|ola|eae|eai|e ai|ei|hey|fala|eita|alou|iae)(?:\s+|$)/g;
  const WAKE_ONLY = /^(?:oi|ola|eae|eai|e ai|ei|hey|fala|eita|alou|iae)$/;
  const appMode = new URLSearchParams(window.location.search).get("app") === "1"
    || window.matchMedia("(display-mode: standalone)").matches;
  let busy = false;
  let keepListening = false;
  let armed = false;
  let armUntil = 0;
  let speaking = false;
  let recHandle = null;
  let pendingHeard = "";
  let heardTimer = 0;
  let listenPainted = false;
  let lastAckAt = 0;
  let lastAsked = "";
  let lastAskedAt = 0;
  let lastOpenAt = 0;
  let stayQuiet = false;
  let askQueue = [];
  let meeting = false;
  let clickWait = 0;

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

  function applyPersona(_label) {
    document.documentElement.dataset.persona = "jarvis";
  }

  function clearStaleSession() {
    try { window.localStorage.removeItem(OWNER_TOKEN_KEY); } catch { /* private */ }
  }

  function renderAccess(label, signedIn) {
    accessLine.textContent = label;
    applyPersona(label);
    const inSession = Boolean(signedIn);
    document.documentElement.classList.toggle("signed-in", inSession);
    document.documentElement.classList.toggle("needs-login", !inSession);
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
      renderAccess(mode === "owner" ? "JARVIS" : "Conta JARVIS", true);
    } catch {
      renderAccess("Sessão", Boolean(ownerToken()));
    }
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
    window.clearTimeout(heardTimer);
    pendingHeard = "";
    try { recHandle && recHandle.stop(); } catch { /* already stopped */ }
  }

  function stopSpeak() {
    try { nativeHandlers()?.jarvisSpeak.postMessage("stop"); } catch { /* web */ }
    speaking = false;
  }

  function unmuteMicAfterSpeech() {
    speaking = false;
    if (!stayQuiet) keepArmed();
    try { nativeHandlers()?.jarvisListen.postMessage("resume"); } catch { /* web */ }
    if (keepListening && !hasNativeListen()) listenLoop();
    drainQueue();
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
    const persona = "jarvis";
    return Promise.resolve(window.JarvisLocalVoice?.speakBlob(clip, { persona }))
      .then((localBlob) => {
        if (localBlob) return playBlob(localBlob);
      })
      .catch(() => {})
      .finally(() => unmuteMicAfterSpeech());
  }

  let lastOpenUrl = "";
  let lastError = "";
  let lastCommand = "";

  function openTarget(url) {
    const href = String(url || "");
    if (!href) return false;
    const now = Date.now();
    if (href === lastOpenUrl && now - lastOpenAt < 8000) return true;
    lastOpenUrl = href;
    lastOpenAt = now;
    const popup = window.open(href, "_blank", "noopener,noreferrer");
    if (popup) return true;
    showAnswerLink("Popup bloqueado.", href, "Toque para abrir");
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
    if (!/\bspotify\b/.test(text)) return false;
    if (/\b(?:com|paus|to(?:c|q)|play|pr[oó]xim|volum|status|aleat|shuffle|repet)\w*/.test(text)) return true;
    return hasNativeListen() && /\b(?:abre|abrir|abra|inici(?:a|e|ar))\b/.test(text);
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
    if (/^(?:entrar|login|fazer login|conectar)$/.test(value.trim())) {
      return { run: () => revealLogin(), speak: "" };
    }
    const opened = resolveOpen(value);
    if (opened) {
      return {
        run: () => openTarget(opened.url),
        title: "Abrindo.",
        detail: opened.label,
        speak: `Abrindo o ${opened.label}.`,
      };
    }
    if (/\bhoras?\b|\bque dia\b|\bdata de hoje\b/.test(value)) {
      return {
        run: () => {
          const now = localClock();
          say("Agora.", now);
          showAnswer(now);
        },
        speak: () => `São ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}, senhor.`,
      };
    }
    if (/^copia/.test(value)) {
      return {
        run: () => {
          const textToCopy = lastAnswer.textContent || "";
          if (textToCopy && navigator.clipboard?.writeText) navigator.clipboard.writeText(textToCopy);
          say("Copiado.", textToCopy || "Nada ainda.");
        },
        speak: "",
      };
    }
    if (/\bcockpit\b|\bjanela grande\b/.test(value)) {
      return { run: () => { window.location.href = "/"; }, speak: "" };
    }
    return null;
  }

  function isQuietAsk(text) {
    const folded = foldSpeech(text);
    if (/^(?:silencio|quieto)$/.test(folded)) return true;
    return /\b(?:fica\s+quieto|fica\s+calado|cala\s+a\s+boca|para\s+de\s+falar|modo\s+foco|nao\s+me\s+perturba|estou\s+ocupado)\b/.test(folded);
  }

  function looksLikeCommand(text) {
    const folded = foldSpeech(text);
    if (!folded || folded.length < 3) return false;
    if (WAKE_NAME.test(folded)) return true;
    return /\b(?:abre|abrir|abra|fecha|fechar|toca|toque|paus|play|spotify|whatsapp|youtube|google|hora|horas|data|pesquisa|busca|procura|volume|proximo|proxima|calendario|agenda|gmail|maps|mapa|silencio|quieto|cala|foco|ocupado|copia|cockpit|repete|de novo|outra vez)\b/.test(folded);
  }

  function expandCommands(text) {
    const folded = foldSpeech(text);
    if (!/\b(?:abre|abrir|abra|inici(?:a|e|ar))\b/.test(folded)) return [text];
    const catalog = [
      ["whatsapp", "abre o whatsapp"],
      ["youtube", "abre o youtube"],
      ["spotify", "abre o spotify"],
      ["gmail", "abre o gmail"],
      ["instagram", "abre o instagram"],
      ["github", "abre o github"],
      ["discord", "abre o discord"],
      ["notion", "abre o notion"],
      ["drive", "abre o drive"],
      ["agenda", "abre a agenda"],
      ["calendario", "abre a agenda"],
      ["maps", "abre o maps"],
      ["mapa", "abre o maps"],
      ["google", "abre o google"],
    ];
    const hits = [];
    const seen = new Set();
    const finder = /whatsapp|youtube|spotify|gmail|instagram|github|discord|notion|drive|agenda|calendario|maps|mapa|google/g;
    let match = finder.exec(folded);
    while (match) {
      const key = match[0];
      const row = catalog.find(([name]) => name === key);
      if (row && !seen.has(row[1])) {
        seen.add(row[1]);
        hits.push(row[1]);
      }
      match = finder.exec(folded);
    }
    if (hits.includes("abre o maps")) {
      const google = hits.indexOf("abre o google");
      if (google >= 0) hits.splice(google, 1);
    }
    if (hits.includes("abre o drive")) {
      const google = hits.indexOf("abre o google");
      if (google >= 0) hits.splice(google, 1);
    }
    return hits.length >= 2 ? hits : [text];
  }

  function enterQuiet() {
    stayQuiet = true;
    armed = false;
    askQueue = [];
    try { nativeHandlers()?.jarvisSpeak.postMessage("stop"); } catch { /* web */ }
    nativeWindow("hide");
    say("Quieto.", "Diga Jarvis quando quiser.");
  }

  function enqueue(command) {
    const clip = String(command || "").replace(/\s+/g, " ").trim();
    if (!clip || stayQuiet) return;
    if (askQueue.length >= 4) return;
    const folded = foldSpeech(clip);
    if (folded === foldSpeech(lastAsked)) return;
    if (askQueue.some((item) => foldSpeech(item) === folded)) return;
    askQueue.push(clip);
  }

  function drainQueue() {
    if (busy || speaking || stayQuiet) return;
    const next = askQueue.shift();
    if (next) ask(next);
  }

  async function ask(text) {
    const command = String(text || "").trim();
    if (!command) return;
    if (busy) {
      enqueue(command);
      return;
    }
    busy = true;
    lastCommand = command;
    try {
      if (isQuietAsk(command)) enterQuiet();
      if (navigator.onLine === false) {
        const local = localAction(command);
        if (local) {
          local.run();
          const spoken = typeof local.speak === "function" ? local.speak() : local.speak;
          if (spoken && !stayQuiet) await speak(spoken);
          return;
        }
        say("Offline.", "Sem internet para o restante.");
        if (!stayQuiet) await speak("Sem internet");
        return;
      }
      const local = localAction(command);
      if (local) {
        local.run();
        if (local.title) say(local.title, local.detail || command);
        const spoken = typeof local.speak === "function" ? local.speak() : local.speak;
        if (spoken && !stayQuiet) await speak(spoken);
        return;
      }
      say("…", command);
      if (!stayQuiet && hasNativeSpeak()) {
        try { nativeHandlers().jarvisSpeak.postMessage("Sim, senhor."); } catch { /* web */ }
      }
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
      if (data.client_action === "quiet_mode" || isQuietAsk(command)) {
        enterQuiet();
        if (response.status === 429) {
          say("Limite.", message);
          return;
        }
        say("Quieto.", "Diga Jarvis quando quiser.");
        return;
      }
      if (response.status === 429) {
        say("Limite.", message);
        return;
      }
      if (!stayQuiet && hasNativeSpeak()) {
        try { nativeHandlers().jarvisSpeak.postMessage("stop"); } catch { /* web */ }
      }
      say(data.ok === false ? "Não." : "Senhor.", "");
      if (data.status_real === "free_web_search_unavailable") {
        showAnswerLink(message, `https://www.google.com/search?q=${encodeURIComponent(command)}`, "Buscar no Google");
      } else if (!opened) {
        showAnswer(message);
      }
      if (!stayQuiet) await speak(spokenReply(message));
    } finally {
      busy = false;
      drainQueue();
    }
  }

  function nativeWindow(action) {
    try { nativeHandlers()?.jarvisWindow.postMessage(action); } catch { /* web */ }
  }

  function keepArmed() {
    armed = true;
    armUntil = Date.now() + 45_000;
    nativeWindow("touch");
  }

  window.__jarvisNativeListen = function (state) {
    const raw = String(state || "");
    if (raw.startsWith("level:")) {
      const n = Number(raw.slice(6));
      const node = document.getElementById("heardLine");
      if (node && node.hidden && n > 0.008) {
        node.hidden = false;
        node.textContent = "mic ok";
      }
      return;
    }
    if (raw.startsWith("error:")) {
      const msg = raw.slice(6);
      if (/no speech|sem fala|1110|retry/i.test(msg)) return;
      paintHeard(msg);
      return;
    }
    if (raw === "waiting") {
      keepListening = true;
      orb.classList.add("listening");
      say("Ouvindo.", "Preparando fala no Mac…");
      listenPainted = false;
      return;
    }
    if (raw === "voice:down") {
      document.documentElement.classList.add("voice-down");
      return;
    }
    if (raw === "voice:ok") {
      document.documentElement.classList.remove("voice-down");
      return;
    }
    if (raw === "denied") {
      listenPainted = false;
      orb.classList.remove("listening");
      say("Mic.", "Ajustes → Privacidade → Microfone e Fala.");
      return;
    }
    if (raw === "listening" || raw === "waiting") {
      keepListening = true;
      orb.classList.add("listening");
      if (!listenPainted) {
        listenPainted = true;
        say("Ouvindo.", "Às suas ordens, senhor.");
      }
    }
  };

  window.__jarvisNativeHeard = function (spoken, isFinal) {
    hearSpoken(spoken, isFinal !== false);
  };

  window.__jarvisSetIdle = function (on) {
    const idle = on === true || on === "true";
    document.documentElement.classList.toggle("idle-orb", idle);
  };

  function foldSpeech(text) {
    return String(text || "")
      .toLocaleLowerCase("pt-BR")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/['"`´]/g, "")
      .replace(/[^a-z0-9\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function splitWake(text) {
    const folded = foldSpeech(text);
    if (!folded) return null;
    const hit = folded.match(WAKE_NAME);
    if (!hit || hit.index == null) return null;
    const after = folded.slice(hit.index + hit[0].length).replace(WAKE_CALL, " ").replace(/\s+/g, " ").trim();
    let before = folded.slice(0, hit.index).replace(WAKE_CALL, " ").replace(/\s+/g, " ").trim();
    if (WAKE_ONLY.test(before)) before = "";
    return { command: after || before, folded };
  }

  function paintHeard(text) {
    const node = document.getElementById("heardLine");
    if (!node) return;
    const clean = String(text || "").replace(/\s+/g, " ").trim();
    node.hidden = !clean;
    node.textContent = clean ? `ouvi: ${clean}` : "";
  }

  function takeWake(text, isFinal) {
    if (isQuietAsk(text)) {
      const hit = splitWake(text);
      if (!armed && !hit) return;
      if (!isFinal) return;
      stayQuiet = false;
      fireAsk(text);
      return;
    }
    const hit = splitWake(text);
    if (stayQuiet && !hit) return;
    if (hit) {
      stayQuiet = false;
      nativeWindow("touch");
      keepArmed();
      if (!hit.command) {
        say("Senhor.", "Pode falar.");
        return;
      }
      if (isRepeatAsk(hit.command)) {
        lastAsked = "";
        lastAskedAt = 0;
        if (lastCommand) fireAsk(lastCommand);
        return;
      }
      if (!isFinal) {
        say("Ouvindo.", hit.command);
        return;
      }
      fireAsk(hit.command);
      return;
    }
    if (armed && Date.now() <= armUntil) {
      if (!looksLikeCommand(text)) return;
      if (!isFinal) {
        say("Ouvindo.", text);
        return;
      }
      if (isRepeatAsk(text)) {
        lastAsked = "";
        lastAskedAt = 0;
        if (lastCommand) fireAsk(lastCommand);
        return;
      }
      keepArmed();
      fireAsk(text);
    }
  }

  function fireAsk(command) {
    const clip = String(command || "").replace(/\s+/g, " ").trim();
    if (!clip) return;
    const folded = foldSpeech(clip);
    if (folded === foldSpeech(lastAsked) && Date.now() - lastAskedAt < 4000) return;
    const items = expandCommands(clip);
    lastAsked = items[0];
    lastAskedAt = Date.now();
    for (let index = 1; index < items.length; index += 1) enqueue(items[index]);
    ask(items[0]);
  }

  function isRepeatAsk(text) {
    return /^(?:repete|repete isso|de novo|outra vez|diz de novo|fala de novo|repete o ultimo)$/.test(foldSpeech(text));
  }

  function spokenReply(text) {
    const clip = String(text || "").replace(/\s+/g, " ").trim();
    if (!clip) return "";
    const first = clip.match(/^.+?[.!?…](?=\s|$)/);
    return (first ? first[0] : clip).trim().slice(0, 160);
  }

  function hearSpoken(spoken, isFinal = true) {
    const text = String(spoken || "").trim();
    if (!text) return;
    paintHeard(text);
    if (speaking) {
      const hit = splitWake(text);
      if (!hit && !(isQuietAsk(text) && (armed || hit))) return;
      stopSpeak();
      try { nativeHandlers()?.jarvisListen.postMessage("resume"); } catch { /* web */ }
      takeWake(text, isFinal);
      return;
    }
    if (isQuietAsk(text) && (armed || splitWake(text))) {
      takeWake(text, isFinal);
      return;
    }
    if (!isFinal) {
      pendingHeard = text;
      window.clearTimeout(heardTimer);
      takeWake(text, false);
      heardTimer = window.setTimeout(() => hearSpoken(pendingHeard, true), 550);
      return;
    }
    window.clearTimeout(heardTimer);
    pendingHeard = "";
    takeWake(text, true);
  }

  function listenLoop() {
    if (!keepListening || speaking) return;
    if (hasNativeListen()) {
      try { nativeHandlers().jarvisListen.postMessage("start"); } catch { /* web */ }
      orb.classList.add("listening");
      say("Ouvindo.", "Às suas ordens, senhor.");
      return;
    }
    if (!Recognition) return;
    const rec = new Recognition();
    recHandle = rec;
    rec.lang = "pt-BR";
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (event) => {
      const last = event.results?.[event.results.length - 1];
      hearSpoken(last?.[0]?.transcript || "", Boolean(last?.isFinal));
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
      say("Ouvindo.", "Às suas ordens, senhor.");
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
    if (appMode) return true;
    try {
      const stored = window.localStorage.getItem(LISTEN_KEY);
      if (stored === "0") return false;
      return stored === "1";
    } catch {
      return false;
    }
  }

  function startWebBackup() {
    if (hasNativeListen()) return;
    if (!Recognition) return;
    try { recHandle && recHandle.stop(); } catch { /* already stopped */ }
    const rec = new Recognition();
    recHandle = rec;
    rec.lang = "pt-BR";
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (event) => {
      const last = event.results?.[event.results.length - 1];
      hearSpoken(last?.[0]?.transcript || "", Boolean(last?.isFinal));
    };
    rec.onerror = () => {};
    rec.onend = () => {
      if (recHandle === rec) recHandle = null;
      if (keepListening && !speaking) window.setTimeout(startWebBackup, 250);
    };
    try { rec.start(); } catch { /* native segue */ }
  }

  function forceListen() {
    speaking = false;
    stayQuiet = false;
    meeting = false;
    document.documentElement.classList.remove("meeting");
    keepListening = false;
    listenPainted = false;
    window.clearTimeout(heardTimer);
    pendingHeard = "";
    try { nativeHandlers()?.jarvisListen.postMessage("restart"); } catch { /* web */ }
    nativeWindow("focus");
    startWakeLoop({ force: true });
    startWebBackup();
  }

  function startWakeLoop(options) {
    const silent = Boolean(options && options.silent);
    const force = Boolean(options && options.force);
    if (!Recognition && !hasNativeListen()) {
      if (!silent) {
        input.focus();
        say("Escreva.", "Sem microfone aqui.");
      }
      return;
    }
    if (keepListening && !force) return;
    keepListening = true;
    persistListen(true);
    say("Ouvindo.", "Às suas ordens, senhor.");
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
    const kick = () => {
      if (!wantsListen() || speaking) return;
      if (!keepListening) startWakeLoop({ silent: true });
      else if (hasNativeListen()) {
        try { nativeHandlers().jarvisListen.postMessage("start"); } catch { /* web */ }
      }
    };
    kick();
    window.setInterval(kick, 4000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) kick(); });
    if (!Recognition || hasNativeListen()) return;
    const permissions = navigator.permissions;
    if (permissions && permissions.query) {
      Promise.resolve(permissions.query({ name: "microphone" })).then((status) => {
        if (status.state === "denied") {
          say("Mic.", "Ajustes → Privacidade → Microfone.");
          return;
        }
        status.onchange = () => { if (status.state === "granted") kick(); };
      }).catch(() => {});
    }
  }

  moreButton.addEventListener("click", () => {
    extras.hidden = !extras.hidden;
    moreButton.textContent = extras.hidden ? "mais" : "fechar";
  });
  document.getElementById("loginToggle")?.addEventListener("click", () => {
    nativeWindow("focus");
    revealLogin();
  });
  document.getElementById("retryButton")?.addEventListener("click", () => {
    if (lastCommand) ask(lastCommand);
  });
  document.getElementById("debugToggle")?.addEventListener("click", () => {
    mountDebug(true);
  });
  document.getElementById("reloadButton")?.addEventListener("click", restartForUpdate);
  const minimizeButton = document.getElementById("minimizeButton");
  if (minimizeButton) {
    minimizeButton.hidden = !hasNativeListen();
    minimizeButton.addEventListener("click", () => nativeWindow("hide"));
  }
  function toggleMeeting() {
    meeting = !meeting;
    document.documentElement.classList.toggle("meeting", meeting);
    if (meeting) {
      stayQuiet = true;
      armed = false;
      try { nativeHandlers()?.jarvisListen.postMessage("pause"); } catch { /* web */ }
      say("Reunião.", "Mic off. Duplo clique no brilho.");
      return;
    }
    stayQuiet = false;
    forceListen();
  }

  orb.addEventListener("click", () => {
    window.clearTimeout(clickWait);
    clickWait = window.setTimeout(() => forceListen(), 280); // user-gesture
  });
  orb.addEventListener("dblclick", (event) => {
    event.preventDefault();
    window.clearTimeout(clickWait);
    toggleMeeting();
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
  say("JARVIS", "Às suas ordens, senhor.");
  if (hasNativeListen()) document.documentElement.classList.add("idle-orb");
  refreshAccess();
  refreshVoiceChip();
  watchShellVersion();
  window.setInterval(refreshVoiceChip, 8000);
  tryAutoListen();
  window.setTimeout(() => document.documentElement.classList.remove("booting"), 650);
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
        `lastHeard ${document.getElementById("heardLine")?.textContent || "—"}`,
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
