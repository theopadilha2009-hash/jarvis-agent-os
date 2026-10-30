
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
  const SHELL_VERSION = "20261030-voz2";
  const WEB_VOLUME_KEY = "jarvis-web-volume";
  // Variantes fonéticas mínimas: "jarbas" é nome de pessoa e "ja viu" é
  // homófono de frase comum — as duas fontes de disparo falso relatadas.
  const WAKE_NAME = /\b(?:jarvis|jarvius|jarbis|javis)\b/;
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
  let speakRunId = 0;
  let meeting = false;
  let clickWait = 0;
  let parkTimer = 0;
  let lastStatus = null;
  let voiceLocalOk = null;
  let micPermission = "";
  let debugTimer = 0;

  if (appMode) document.documentElement.classList.add("app-mode");
  document.documentElement.classList.toggle("needs-login", !ownerToken());
  document.documentElement.classList.toggle("signed-in", Boolean(ownerToken()));

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
      window.localStorage.setItem(REMEMBER_KEY, appMode || rememberLoginEnabled() ? "1" : "0");
      window.localStorage.setItem(OWNER_IDLE_KEY, String(Date.now()));
    } catch { /* private mode */ }
    try { nativeHandlers()?.jarvisWindow.postMessage("token:" + (token || "")); } catch { /* web */ }
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
          signal: window.AbortSignal?.timeout ? window.AbortSignal.timeout(path === "/command" ? (payload && payload.attachments ? 40000 : 22000) : 14000) : undefined,
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
    holdReply();
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
    holdReply();
  }

  function applyPersona(_label) {
    document.documentElement.dataset.persona = "jarvis";
  }

  function clearStaleSession() {
    try { window.localStorage.removeItem(OWNER_TOKEN_KEY); } catch { /* private */ }
    try { nativeHandlers()?.jarvisWindow.postMessage("token:"); } catch { /* web */ }
  }

  function paintHome() {
    // O #hint ficou oculto de propósito: a linha "Neste Mac você entra só agora"
    // não dizia nada útil. O elemento continua no HTML por causa do contrato
    // verificado em 10_TESTES/fala_overlay_test.py.
    if (ownerToken()) {
      say("JARVIS", "Diga Jarvis.");
      return;
    }
    say("JARVIS", appMode ? "A mesma conta do site." : "Diga Jarvis.");
  }

  function renderAccess(label, signedIn) {
    accessLine.textContent = label;
    applyPersona(label);
    const inSession = Boolean(signedIn);
    document.documentElement.classList.toggle("signed-in", inSession);
    document.documentElement.classList.toggle("needs-login", !inSession);
    logoutButton.hidden = !inSession;
    loginForm.querySelector("#loginUser").hidden = inSession;
    loginForm.querySelector("#loginPass").hidden = inSession;
    loginForm.querySelector("button[type='submit']").hidden = inSession;
    const remember = document.getElementById("rememberLogin");
    if (remember) remember.closest("label").hidden = inSession;
    paintHome();
  }

  function noteStatus(data) {
    if (!data || typeof data !== "object") return;
    lastStatus = data;
  }

  async function refreshAccess() {
    if (!ownerToken()) {
      renderAccess("Visitante", false);
      return;
    }
    try {
      const data = await fetch("/status", { headers: apiHeaders() }).then((row) => row.json());
      noteStatus(data);
      const mode = data.access?.mode;
      if (mode !== "owner" && mode !== "member") {
        clearStaleSession();
        renderAccess("Visitante", false);
        return;
      }
      const power = data.power_profile?.mode === "jarvis_3x" || mode === "owner";
      renderAccess(power ? "JARVIS · 3×" : "Conta JARVIS", true);
    } catch {
      renderAccess("Sessão", Boolean(ownerToken()));
    }
  }

  function webVolume() {
    try {
      const raw = Number(window.localStorage.getItem(WEB_VOLUME_KEY));
      if (Number.isFinite(raw) && raw >= 0 && raw <= 1) return raw;
    } catch { /* private mode */ }
    return 1;
  }

  function playBlob(blob) {
    return new Promise((resolve) => {
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.volume = webVolume();
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
    speakRunId += 1;
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

  // Mesma regra do app nativo: frases por . ! ? … e quebra de linha; frase
  // <8 chars gruda na seguinte. Texto sem separador vira frase única —
  // caminho comum, igual ao comportamento antigo.
  function pushSpeechPart(parts, current) {
    const piece = current.trim();
    if (piece) parts.push(piece);
  }

  function speechSentences(text) {
    const parts = [];
    let current = "";
    for (const ch of text) {
      if (ch === "." || ch === "!" || ch === "?" || ch === "…") {
        current += ch;
        pushSpeechPart(parts, current);
        current = "";
      } else if (ch === "\n" || ch === "\r") {
        pushSpeechPart(parts, current);
        current = "";
      } else {
        current += ch;
      }
    }
    pushSpeechPart(parts, current);
    if (parts.length <= 1) return parts;
    const merged = [];
    let index = 0;
    while (index < parts.length) {
      let piece = parts[index];
      while (piece.length < 8 && index + 1 < parts.length) {
        index += 1;
        piece += ` ${parts[index]}`;
      }
      merged.push(piece);
      index += 1;
    }
    return merged;
  }

  // Web: busca o blob da frase 1 e toca; em paralelo pré-busca a próxima
  // (no máximo 1 fetch em voo, como no app) e encadeia playBlob sequencial.
  // Frase com erro é pulada e a fila segue; o unmute fica no .finally de speak.
  function speakChunksQueue(chunks, persona) {
    let next = 0;
    const ready = [];
    let fetching = false;
    let waiting = false;
    let finish = null;
    // Cancelamento: enterQuiet/stopSpeak incrementam o run global e a fila
    // inteira abandona o resto (antes "fica quieto" continuava falando).
    const myRun = speakRunId;

    const aborted = () => myRun !== speakRunId || stayQuiet;
    const stopIfAborted = () => {
      if (aborted()) {
        ready.length = 0;
        return true;
      }
      return false;
    };

    const fetchNext = () => {
      if (stopIfAborted()) {
        if (!fetching && !ready.length) finish();
        return;
      }
      if (fetching || next >= chunks.length) return;
      const chunk = chunks[next];
      next += 1;
      fetching = true;
      let pending;
      try {
        pending = Promise.resolve(window.JarvisLocalVoice?.speakBlob(chunk, { persona }));
      } catch {
        pending = Promise.reject(new Error("speakBlob"));
      }
      pending.then(
        (blob) => { if (blob && !aborted()) ready.push(blob); },
        () => { /* frase falha: pula */ }
      ).then(() => {
        fetching = false;
        fetchNext();
        if (waiting) {
          waiting = false;
          playNext();
        }
      });
    };

    const playNext = () => {
      if (stopIfAborted()) {
        if (!fetching) finish();
        return;
      }
      if (!ready.length) {
        if (fetching || next < chunks.length) {
          fetchNext();
          waiting = true;
          return;
        }
        finish();
        return;
      }
      const blob = ready.shift();
      fetchNext();
      Promise.resolve()
        .then(() => playBlob(blob))
        .catch(() => {})
        .then(() => { if (!aborted()) playNext(); else finish(); });
    };

    return new Promise((resolveQueue) => {
      finish = resolveQueue;
      playNext();
    });
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
    return speakChunksQueue(speechSentences(clip), "jarvis")
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

  // Abrir app do Mac não existe client-side: manda pelo gateway, que roda
  // open_application com allowlist (APPLICATION_ALIASES) no Mac dele.
  function openAppOnMac(app, label) {
    cancelPark();
    nativeWindow("touch");
    postJson("/command", { command: `abrir aplicativo ${app}`, strength: "auto" }).then(({ data }) => {
      const message = data.ok === false
        ? (data.error || "Não consegui abrir o app.")
        : (data.message || `Abrindo o ${label}.`);
      say(data.ok === false ? "Não." : "Senhor.", "");
      showAnswer(message);
      if (!stayQuiet) speak(spokenReply(message));
    });
  }

  // App do Mac: a janela é borderless, então o handler nativo cobre o frame
  // da tela. Web puro: Fullscreen API, com aviso claro se o gesto for cobrado.
  function toggleFullscreen() {
    if (nativeHandlers()) {
      nativeWindow("fullscreen");
      return;
    }
    const doc = document;
    if (doc.fullscreenElement || doc.webkitFullscreenElement) {
      const exit = doc.exitFullscreen || doc.webkitExitFullscreen;
      if (exit) exit.call(doc);
      say("Saindo.", "Tela cheia desligada.");
      return;
    }
    const root = doc.documentElement;
    const request = root.requestFullscreen || root.webkitRequestFullscreen;
    if (!request) {
      say("Tela cheia.", "Este navegador não suporta.");
      speak("Este navegador não suporta tela cheia.");
      return;
    }
    Promise.resolve(request.call(root)).then(() => {
      say("Tela cheia.", "Diga tela cheia de novo para sair.");
    }).catch(() => {
      say("Tela cheia.", "O navegador bloqueou. Toque na página e tente de novo.");
      speak("O navegador bloqueou a tela cheia. Toque na página e tente de novo.");
    });
  }

  function remainderAfter(value, match) {
    const rest = String(match || "").replace(/\s+(?:pra mim|para mim|por favor)$/i, "").trim();
    if (!rest || /^(?:o|a|o youtube|youtube|mapa|maps)$/i.test(rest)) return "";
    return rest;
  }

  function isMacSpotifyCommand(value) {
    const text = String(value || "").toLocaleLowerCase("pt-BR");
    // Faixas do catálogo disparam sem a palavra "spotify".
    if (/\b(?:homem\s+de\s+ferro|iron\s+man|back\s+in\s+black|spotify:track:)\b/.test(text)) return true;
    if (!/\bspotify\b/.test(text)) return false;
    // No app nativo o Spotify é SEMPRE o app do Mac; abrir o web player no
    // navegador não toca nada e ainda cobre a tela de abas.
    if (hasNativeListen()) return true;
    if (/\b(?:com|paus|to(?:c|q)|play|pr[oó]xim|volum|status|aleat|shuffle|repet)\w*/.test(text)) return true;
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
    // Navegadores são apps do Mac, não abas: o gateway tem open_application
    // com allowlist (aliases em api/index.py). "navegador" cai no Safari,
    // o padrão do dono.
    const appTargets = [
      [/\bchrome\b|\bgoogle\s+chrome\b/, "Google Chrome", "Chrome"],
      [/\bsafari\b/, "Safari", "Safari"],
      [/\bedge\b|\bmicrosoft\s+edge\b/, "Microsoft Edge", "Edge"],
      [/\bbrave\b/, "Brave Browser", "Brave"],
      [/\b(?:navegador|browser)\b/, "Safari", "navegador"],
    ];
    for (const [pattern, app, label] of appTargets) {
      if (pattern.test(value)) return { app, label };
    }
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

  // Mesmo contrato dos modos do cockpit (jarvis.js): verde = plano,
  // vermelho = bypass/sempre-aceitar, modo normal apaga tudo.
  function voiceModeFor(value) {
    const clean = String(value || "").trim().replace(/^jarvis[,\s]+/i, "");
    if (/^(?:vai|vá|va)\s+dormir\.?$|^(?:entrar?\s+no\s+)?modo\s+plano\.?$|^plano\.?$/i.test(clean)) {
      return {
        mode: "plan",
        title: "Modo plano.",
        detail: "Borda verde: só planejo, nada executo sem aprovação.",
        speak: "Modo plano ativado. Borda verde: só planejo, nada executo sem a sua aprovação.",
      };
    }
    if (/^bypass(?:\s+permissions?)?\.?$|^pular\s+permiss(?:ões|oes|ão|ao)\.?$/i.test(clean)) {
      return {
        mode: "bypass",
        title: "Bypass de permissões.",
        detail: "Borda vermelha: executo sem confirmar cada passo.",
        speak: "Bypass de permissões ativado. Borda vermelha: executo sem confirmar cada passo.",
      };
    }
    if (/^always\s+accept(?:ed)?\.?$|^(?:aceite|aceitar)\s+tudo\.?$|^sempre\s+aceite\.?$/i.test(clean)) {
      return {
        mode: "bypass",
        title: "Sempre aceitar.",
        detail: "Borda vermelha: aprovo tudo automaticamente.",
        speak: "Sempre aceitar ativado. Borda vermelha: aprovo tudo automaticamente.",
      };
    }
    if (/^modo\s+normal\.?$|^acordar?\.?$|^sai(?:r)?\s+do\s+modo\.?$|^despertar\.?$/i.test(clean)) {
      return { mode: "normal", title: "Modo normal.", detail: "Borda apagada.", speak: "De volta ao modo normal." };
    }
    return null;
  }

  function applyVoiceMode(mode) {
    document.body.classList.remove("jarvis-mode-plan", "jarvis-mode-bypass");
    if (mode === "plan") document.body.classList.add("jarvis-mode-plan");
    else if (mode === "bypass") document.body.classList.add("jarvis-mode-bypass");
    try {
      if (mode && mode !== "normal") window.localStorage.setItem("jarvis-assistant-mode", mode);
      else window.localStorage.removeItem("jarvis-assistant-mode");
    } catch { /* private */ }
  }

  function localAction(text) {
    const value = String(text || "").toLocaleLowerCase("pt-BR");
    if (/^(?:entrar|login|fazer login|conectar)$/.test(value.trim())) {
      return { run: () => revealLogin(), speak: "" };
    }
    if (/\btela\s+(?:cheia|inteira)\b/.test(value)) {
      return { run: () => toggleFullscreen(), speak: "" };
    }
    // Modos explícitos do dono: borda verde (plano) / vermelha (bypass,
    // sempre-aceitar) na tela inteira, com confirmação falada — sem IA.
    const voiceMode = voiceModeFor(value.trim());
    if (voiceMode) {
      return {
        run: () => applyVoiceMode(voiceMode.mode),
        title: voiceMode.title,
        detail: voiceMode.detail,
        speak: voiceMode.speak,
      };
    }
    const opened = resolveOpen(value);
    if (opened) {
      if (opened.app) {
        return {
          run: () => openAppOnMac(opened.app, opened.label),
          title: "Abrindo.",
          detail: opened.label,
          speak: `Abrindo o ${opened.label}.`,
        };
      }
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

  // Sem wake armado, só um comando que COMEÇA com verbo de ação passa —
  // "contém youtube" fazia conversa casual virar comando.
  function looksLikeCommand(text) {
    const folded = foldSpeech(text);
    if (!folded || folded.length < 3) return false;
    if (WAKE_NAME.test(folded)) return true;
    return /^(?:abre|abrir|abra|fecha|fechar|toca|toque|paus|play|pesquisa|busca|procura|volume|proximo|proxima|silencio|quieto|cala|copia|cockpit|repete|de novo|outra vez|analisa|analise|olha|veja|que horas|horas|que dia|data|bateria|clima|tempo|previsao|cotacao|dolar|euro|bitcoin|specs|hardware|noticias|analisa isso|tela cheia|tela inteira)\b/.test(folded);
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
      ["chrome", "abre o chrome"],
      ["safari", "abre o safari"],
      ["edge", "abre o edge"],
      ["brave", "abre o brave"],
      ["navegador", "abre o navegador"],
    ];
    const hits = [];
    const seen = new Set();
    const finder = /whatsapp|youtube|spotify|gmail|instagram|github|discord|notion|drive|agenda|calendario|maps|mapa|google|\bchrome\b|\bsafari\b|\bedge\b|\bbrave\b|\bnavegador\b/g;
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
    speakRunId += 1;
    armed = false;
    askQueue = [];
    try { nativeHandlers()?.jarvisSpeak.postMessage("stop"); } catch { /* web */ }
    parkNow();
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

  function hasNativeSee() {
    return Boolean(nativeHandlers() && nativeHandlers().jarvisSee);
  }

  function isLookAsk(text) {
    const folded = foldSpeech(text);
    if (!folded) return false;
    if (/\b(?:o que|oq|que)\b.{0,24}\b(?:estou|to|eu to|eu estou)\s+vendo\b/.test(folded)) return true;
    if (/\b(?:analis|olh|veja|ve |leia|le )\w*.{0,48}\b(?:isso|aqui|tela|pagina|navegador|site|print)\b/.test(folded)) return true;
    if (/\b(?:o que|oq)\s+(?:eu\s+)?(?:faco|fazer)\s+(?:com\s+)?(?:isso|aqui)\b/.test(folded)) return true;
    return /^(?:analisa|analise|olha|olhe|veja|ve|le|leia)(?:\s+(?:isso|aqui|a tela))?$/.test(folded);
  }

  function seeScreen(command) {
    if (hasNativeSee()) {
      say("Olhando.", "Vou ver a tela.");
      cancelPark();
      nativeWindow("touch");
      window.__jarvisOnScreen = (raw) => {
        window.__jarvisOnScreen = null;
        const dataUrl = String(raw || "");
        if (dataUrl === "denied") {
          say("Tela.", "Ajustes → Privacidade → Gravação de Tela → JARVIS.");
          speak("Preciso da permissão de gravação de tela.");
          return;
        }
        if (!dataUrl.startsWith("data:image")) {
          say("Tela.", "Não consegui ver. Tente de novo.");
          speak("Não consegui ver a tela.");
          return;
        }
        ask(command || "analisa o que está na tela e me diz o que fazer", {
          type: "image/jpeg",
          name: "tela.jpg",
          data_url: dataUrl,
        });
      };
      try { nativeHandlers().jarvisSee.postMessage("screen"); } catch {
        say("Tela.", "Não consegui ver.");
      }
      return;
    }
    seeScreenWeb(command);
  }

  // Web puro: getDisplayMedia pede a tela/janela ao dono, captura UM frame e
  // segue o mesmo fluxo de attachment do app nativo.
  async function seeScreenWeb(command) {
    if (!navigator.mediaDevices?.getDisplayMedia) {
      say("Tela.", "Este navegador não permite captura de tela.");
      speak("Este navegador não permite que eu veja a tela.");
      return;
    }
    say("Olhando.", "Escolha a tela ou a janela para compartilhar.");
    let stream;
    try {
      stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
    } catch {
      say("Tela.", "Permita a captura de tela para eu analisar.");
      speak("Permita a captura de tela para eu analisar.");
      return;
    }
    try {
      const dataUrl = await frameFromStream(stream);
      ask(command || "analisa o que está na tela e me diz o que fazer", {
        type: "image/jpeg",
        name: "tela.jpg",
        data_url: dataUrl,
      });
    } catch {
      say("Tela.", "Não consegui ver. Tente de novo.");
      speak("Não consegui ver a tela.");
    }
  }

  function frameFromStream(stream) {
    return new Promise((resolve, reject) => {
      const video = document.createElement("video");
      video.muted = true;
      video.playsInline = true;
      video.srcObject = stream;
      const cleanup = () => {
        try { video.pause(); } catch { /* já parado */ }
        video.srcObject = null;
        stream.getTracks().forEach((track) => track.stop());
      };
      video.addEventListener("error", () => { cleanup(); reject(new Error("frame")); }, { once: true });
      video.addEventListener("loadedmetadata", () => {
        video.play().then(() => {
          const width = Math.min(1280, video.videoWidth || 1280);
          const scale = width / Math.max(video.videoWidth, 1);
          const canvas = document.createElement("canvas");
          canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
          canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
          const ctx = canvas.getContext("2d");
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          const dataUrl = canvas.toDataURL("image/jpeg", 0.72);
          cleanup();
          if (!dataUrl.startsWith("data:image")) {
            reject(new Error("frame"));
            return;
          }
          resolve(dataUrl);
        }, (error) => { cleanup(); reject(error); });
      }, { once: true });
    });
  }

  async function ask(text, attachment) {
    const command = String(text || "").trim();
    if (!command) return;
    if (busy) {
      enqueue(command);
      return;
    }
    busy = true;
    lastCommand = command;
    cancelPark();
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
      const local = attachment ? null : localAction(command);
      if (local) {
        local.run();
        if (local.title) say(local.title, local.detail || command);
        const spoken = typeof local.speak === "function" ? local.speak() : local.speak;
        if (spoken && !stayQuiet) await speak(spoken);
        return;
      }
      say("Pensando.", command);
      const payload = {
        command: attachment
          ? `${command}. Isto é um print da tela onde o JARVIS está; diga o que aparece e o que eu devo fazer agora.`
          : command,
        strength: ownerToken() ? "maximum" : "auto",
      };
      if (attachment) payload.attachments = [attachment];
      if (attachment) nativeWindow("touch");
      const { response, data } = await postJson("/command", payload);
      const message = data.message || data.error || "Sem resposta.";
      lastError = data.ok === false ? message : "";
      const retry = document.getElementById("retryButton");
      if (retry) retry.hidden = !lastError;
      if (response.status === 401 || data.pairing_required) {
        clearStaleSession();
        renderAccess("Visitante", false);
        revealLogin();
        cancelPark();
        nativeWindow("focus");
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
      // `spoken` é o texto que o servidor preparou para a voz; sem ele, cai no
      // recorte de duas frases da mensagem de tela.
      const spokenText = data.spoken ? String(data.spoken) : spokenReply(message);
      if (!stayQuiet) await speak(spokenText);
    } finally {
      busy = false;
      drainQueue();
      if (!busy && !stayQuiet) parkSoon();
    }
  }

  function nativeWindow(action) {
    try { nativeHandlers()?.jarvisWindow.postMessage(action); } catch { /* web */ }
  }

  function cancelPark() {
    window.clearTimeout(parkTimer);
    parkTimer = 0;
  }

  function compactReply() {
    const text = String(lastAnswer.textContent || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    return text.length > 80 ? `${text.slice(0, 77)}…` : text;
  }

  function holdReply() {
    const chip = compactReply();
    nativeWindow(chip ? `reply:${chip}` : "reply:");
  }

  function parkNow() {
    cancelPark();
    holdReply();
    nativeWindow("hide");
  }

  function parkSoon() {
    cancelPark();
    if (!appMode || !ownerToken()) return;
    if (busy || speaking || meeting || stayQuiet) return;
    parkTimer = window.setTimeout(() => {
      if (busy || speaking || meeting || stayQuiet) return;
      if (document.documentElement.classList.contains("needs-login")) return;
      if (document.activeElement === input) return;
      if (extras && !extras.hidden) return;
      parkNow();
    }, 8000);
  }

  function nativeListen(action) {
    try { nativeHandlers()?.jarvisListen.postMessage(action); } catch { /* web */ }
  }

  let armTimer = 0;
  function keepArmed() {
    armed = true;
    armUntil = Date.now() + 45_000;
    document.documentElement.classList.add("armed");
    orb.classList.add("listening");
    cancelPark();
    nativeWindow("touch");
    nativeListen("arm");
    window.clearTimeout(armTimer);
    armTimer = window.setTimeout(sleepUntilWake, 45_000);
  }

  function sleepUntilWake() {
    armed = false;
    armUntil = 0;
    window.clearTimeout(armTimer);
    pendingHeard = "";
    window.clearTimeout(heardTimer);
    orb.classList.remove("listening");
    document.documentElement.classList.remove("armed");
    paintHeard("");
    nativeListen("sleep");
    if (!busy && !speaking && !meeting) paintHome();
  }

  window.__jarvisNativeListen = function (state) {
    const raw = String(state || "");
    if (raw.startsWith("level:")) {
      if (!armed) return;
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
      if (armed) say("Ouvindo.", "Preparando fala no Mac…");
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
      listenPainted = true;
      if (armed) {
        orb.classList.add("listening");
        say("Ouvindo.", "Pode falar.");
      }
    }
  };

  window.__jarvisNativeHeard = function (spoken, isFinal) {
    hearSpoken(spoken, isFinal !== false);
  };

  window.__jarvisSetIdle = function (on) {
    const idle = on === true || on === "true";
    const text = String(lastAnswer.textContent || "").replace(/\s+/g, " ").trim();
    if (idle && text) lastAnswer.hidden = false;
    document.documentElement.classList.toggle("idle-orb", idle);
    document.documentElement.classList.toggle("has-reply", idle && Boolean(text));
    if (idle) sleepUntilWake();
  };

  window.__jarvisOnActionResult = function(result) {
    if (!result) return;
    say("JARVIS", result);
    paintHeard(result);
    try {
      if (lastAnswer) {
        lastAnswer.textContent = result;
        lastAnswer.hidden = false;
      }
    } catch(e){}
  };

  document.querySelectorAll(".btn-chip").forEach(btn => {
    btn.addEventListener("click", () => {
      const act = btn.getAttribute("data-action");
      if (act) fireAsk(act);
    });
  });


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
    try {
      if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.jarvisAction) {
        window.webkit.messageHandlers.jarvisAction.postMessage(clip);
      }
    } catch(e){}
    // Acordar: volta a ouvir sem reabrir nada.
    if (/^(?:acorda|acordar|acorde|volta|voltar)$/i.test(folded)) {
      say("Acordado.", "Pode falar.");
      keepArmed();
      if (!stayQuiet) speak("Pode falar, senhor.");
      return;
    }
    // Desligar de verdade: verbo explícito de fechar/encerrar.
    if (/^(?:desliga|desligar)$|desliga(?:r)?(?:\s+o)?\s*jarvis\b|fechar?\s*(?:o)?\s*jarvis|encerrar?\s*(?:o)?\s*jarvis/i.test(folded)) {
      say("Desligando.", "Até logo, senhor.");
      speak("Até logo, senhor. Desligando.");
      window.setTimeout(() => nativeWindow("shutdown"), 1800);
      return;
    }
    // Dormir: para de ouvir e fica quieto — NÃO fecha o app. Antes "dorme"
    // caía no mesmo ramo do desligar e fechava o JARVIS.
    if (/(?:vai|va)\s+dormir|^(?:dorme|durma|dormir)$/i.test(folded)) {
      say("Dormindo.", 'Chame "Jarvis, acorda" quando precisar.');
      if (!stayQuiet) speak("Dormindo, senhor.");
      sleepUntilWake();
      return;
    }

    if (folded === foldSpeech(lastAsked) && Date.now() - lastAskedAt < 4000) return;
    if (isLookAsk(clip)) {
      lastAsked = clip;
      lastAskedAt = Date.now();
      seeScreen(clip);
      return;
    }
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
    // Até 2 frases: falar só a primeira dava a impressão de cortar no meio.
    const parts = clip.match(/[^.!?…]+[.!?…]*\s*/g) || [clip];
    const spoken = parts.slice(0, 2).join("").trim();
    return spoken.slice(0, 300).trim();
  }

  function hearSpoken(spoken, isFinal = true) {
    const text = String(spoken || "").trim();
    if (!text) return;
    const woke = Boolean(splitWake(text));
    if (!armed && !woke && !(isQuietAsk(text) && armed)) return;
    if (armed || woke) paintHeard(text);
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
      // 550ms cortava quem respira depois do nome. Pausa depois de "Jarvis,"
      // é natural e ganha mais folga; frase em andamento ganha 1,4s.
      const justWake = /^\s*(?:jarvis|jarvius|jarbis|javis)\s*[,.]?\s*$/i.test(text);
      heardTimer = window.setTimeout(
        () => hearSpoken(pendingHeard, true),
        justWake ? 1800 : 1400,
      );
      return;
    }
    window.clearTimeout(heardTimer);
    pendingHeard = "";
    takeWake(text, true);
  }

  function listenLoop() {
    if (!keepListening || speaking) return;
    if (hasNativeListen()) {
      nativeListen(armed ? "arm" : "start");
      if (armed) {
        orb.classList.add("listening");
        say("Ouvindo.", "Pode falar.");
      }
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
      if (armed) {
        orb.classList.add("listening");
        say("Ouvindo.", "Pode falar.");
      }
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
    cancelPark();
    speaking = false;
    stayQuiet = false;
    meeting = false;
    document.documentElement.classList.remove("meeting");
    keepListening = false;
    listenPainted = false;
    window.clearTimeout(heardTimer);
    pendingHeard = "";
    nativeListen("restart");
    nativeWindow("touch");
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
    if (force) keepArmed();
    else sleepUntilWake();
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
    cancelPark();
    nativeWindow("touch");
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
  document.getElementById("meetingButton")?.addEventListener("click", toggleMeeting);
  const minimizeButton = document.getElementById("minimizeButton");
  if (minimizeButton) {
    minimizeButton.hidden = !hasNativeListen();
    minimizeButton.addEventListener("click", () => parkNow());
  }
  const btnMacClose = document.getElementById("btnMacClose");
  if (btnMacClose) {
    btnMacClose.addEventListener("click", (e) => {
      e.stopPropagation();
      nativeWindow("shutdown");
    });
  }
  const btnMacMin = document.getElementById("btnMacMin");
  if (btnMacMin) {
    btnMacMin.addEventListener("click", (e) => {
      e.stopPropagation();
      nativeWindow("minimize");
      if (window.__jarvisSetIdle) window.__jarvisSetIdle(true);
    });
  }
  const btnMacZoom = document.getElementById("btnMacZoom");
  if (btnMacZoom) {
    btnMacZoom.addEventListener("click", (e) => {
      e.stopPropagation();
      nativeWindow("zoom");
      extras.hidden = !extras.hidden;
      moreButton.textContent = extras.hidden ? "mais" : "fechar";
    });
  }
  function toggleMeeting() {
    meeting = !meeting;
    document.documentElement.classList.toggle("meeting", meeting);
    if (meeting) {
      stayQuiet = true;
      armed = false;
      try { nativeHandlers()?.jarvisListen.postMessage("pause"); } catch { /* web */ }
      say("Reunião.", "Mic off. Em mais, reunião de novo.");
      return;
    }
    stayQuiet = false;
    forceListen();
  }

  orb.addEventListener("click", () => {
    window.clearTimeout(clickWait);
    clickWait = window.setTimeout(() => {
      if (document.documentElement.classList.contains("idle-orb")) {
        nativeWindow("focus");
        return;
      }
      forceListen(); // user-gesture
    }, 280);
  });
  orb.addEventListener("dblclick", (event) => {
    event.preventDefault();
    window.clearTimeout(clickWait);
    parkNow();
  });
  lastAnswer.addEventListener("click", () => {
    if (document.documentElement.classList.contains("idle-orb")) nativeWindow("focus");
  });
  input.addEventListener("focus", () => {
    cancelPark();
    nativeWindow("touch");
  });
  input.addEventListener("input", () => {
    cancelPark();
    nativeWindow("touch");
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
        flashLoginError();
        return;
      }
      const keep = document.getElementById("rememberLogin");
      try { localStorage.setItem(REMEMBER_KEY, keep && !keep.checked ? "0" : "1"); } catch { /* ignore */ }
      persistSession(data.session_token, username);
      nativeWindow("touch");
      document.getElementById("loginPass").value = "";
      extras.hidden = true;
      moreButton.textContent = "mais";
      await refreshAccess();
      startWakeLoop();
      // Sem isso a janela pode estar em modo compacto e parecer vazia logo
      // depois do login.
      if (window.__jarvisSetIdle) window.__jarvisSetIdle(false);
      say("JARVIS · 3×", "Diga Jarvis. Arraste e peça analisa isso.");
    } catch {
      say("Rede.", "Tente o login de novo.");
      flashLoginError();
    }
  });

  function flashLoginError() {
    if (!loginForm) return;
    loginForm.classList.remove("login-error");
    // Reflow força a animação a reiniciar quando o erro repete.
    void loginForm.offsetWidth;
    loginForm.classList.add("login-error");
    document.getElementById("loginPass").value = "";
    document.getElementById("loginPass").focus();
    window.setTimeout(() => loginForm.classList.remove("login-error"), 1000);
  }
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
      closeDebug();
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
  paintHome();
  refreshAccess();
  refreshVoiceChip();
  watchShellVersion();
  window.setInterval(refreshVoiceChip, 8000);
  tryAutoListen();
  window.setTimeout(() => document.documentElement.classList.remove("booting"), 650);
  if (/[?&]debug=1(?:&|$)/.test(location.search)) mountDebug(false);

  function restartForUpdate() {
    const url = new URL(location.href);
    url.searchParams.set("r", Date.now().toString(36));
    try {
      const native = nativeHandlers() && nativeHandlers().jarvisRestart;
      if (native) {
        native.postMessage("now");
        window.setTimeout(() => location.replace(url.href), 500);
        return;
      }
    } catch { /* web */ }
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
      noteStatus(data);
      paintShellVersion(data?.shell?.overlay || data?.shell?.version || "");
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
    if (!chip || !window.JarvisLocalVoice?.probe) {
      voiceLocalOk = false;
      return;
    }
    Promise.resolve(window.JarvisLocalVoice.probe()).then(() => {
      voiceLocalOk = true;
      chip.hidden = false;
      chip.textContent = hasNativeSpeak() ? "voz JARVIS" : "voz local";
      chip.dataset.state = "local";
    }).catch(() => {
      voiceLocalOk = false;
      chip.hidden = false;
      chip.textContent = hasNativeSpeak() ? "voz JARVIS" : "voz local";
      chip.dataset.state = "local";
    });
  }

  function closeDebug() {
    const panel = document.getElementById("jarvisDebug");
    if (panel) panel.remove();
    window.clearInterval(debugTimer);
    debugTimer = 0;
  }

  function debugSet(id, text, state) {
    const node = document.getElementById(id);
    if (!node) return;
    node.textContent = text;
    if (state) node.dataset.state = state;
    else delete node.dataset.state;
  }

  function debugGatewayText() {
    if (!lastStatus) return "sem resposta";
    const mode = lastStatus.access?.mode;
    if (mode === "owner" || mode === "member") {
      return lastStatus.power_profile?.mode === "jarvis_3x" ? "conectado · 3×" : `conectado · ${mode}`;
    }
    return "respondeu, sem acesso";
  }

  function debugGatewayState() {
    return lastStatus && (lastStatus.access?.mode === "owner" || lastStatus.access?.mode === "member") ? "ok" : "bad";
  }

  function debugVoiceText() {
    if (hasNativeSpeak()) return "voz JARVIS do app";
    if (voiceLocalOk) {
      const info = window.JarvisLocalVoice?.info?.() || {};
      return info.engine ? `Pocket · ${info.engine}` : "Pocket ativa";
    }
    return "indisponível — fala cai pro navegador";
  }

  function debugVoiceState() {
    return hasNativeSpeak() || voiceLocalOk ? "ok" : "bad";
  }

  function micPermissionText() {
    if (micPermission === "granted") return "permitido";
    if (micPermission === "denied") return "bloqueado";
    if (micPermission === "prompt") return "pedir ao usar";
    if (micPermission) return micPermission;
    return hasNativeListen() ? "pelo app" : "desconhecido";
  }

  function probeMicPermission() {
    const permissions = navigator.permissions;
    if (!permissions?.query) {
      micPermission = "";
      return;
    }
    Promise.resolve(permissions.query({ name: "microphone" })).then((status) => {
      const update = () => { micPermission = status.state; };
      update();
      status.onchange = update;
    }).catch(() => {
      micPermission = "";
    });
  }

  function buildDebugText() {
    const tts = window.JarvisLocalVoice?.info?.() || {};
    return [
      `JARVIS diagnóstico · shell ${SHELL_VERSION}`,
      `quando ${new Date().toLocaleString("pt-BR")}`,
      `modo ${appMode ? "app (Mac)" : "web"}`,
      `gateway ${debugGatewayText()}`,
      `voz ${debugVoiceText()}`,
      `microfone ${micPermissionText()}`,
      `escuta automática ${keepListening ? "ligada" : "desligada"}`,
      `modo quieto ${stayQuiet ? "ligado" : "desligado"}`,
      `volume web ${Math.round(webVolume() * 100)}%`,
      `último comando ${lastCommand || "—"}`,
      `último erro ${lastError || "—"}`,
      `token ${ownerToken() ? "sim" : "não"}`,
      `login lembrado ${rememberLoginEnabled() ? "sim" : "não"}`,
      `persona ${document.documentElement.dataset.persona || "—"}`,
      `tts ${tts.ok ? `${tts.engine || "ok"} ${tts.voice || ""}`.trim() : "offline"}`,
      `último ouvido ${document.getElementById("heardLine")?.textContent || "—"}`,
    ].join("\n");
  }

  function copyDebug() {
    const text = buildDebugText();
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(
        () => say("Copiado.", "Diagnóstico na área de transferência."),
        () => say("Copiar.", "Não consegui copiar."),
      );
      return;
    }
    say("Copiar.", "Sem área de transferência aqui.");
  }

  function mountDebug(fromButton) {
    if (document.getElementById("jarvisDebug")) {
      closeDebug();
      return;
    }
    const panel = document.createElement("div");
    panel.id = "jarvisDebug";
    panel.className = "debug-panel";
    panel.setAttribute("role", "region");
    panel.setAttribute("aria-label", "Diagnóstico do JARVIS");
    panel.innerHTML = [
      '<header class="debug-head">',
      '<strong>diagnóstico</strong>',
      '<button id="debugClose" class="btn debug-close" type="button" aria-label="Fechar diagnóstico">',
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>',
      "</button>",
      "</header>",
      '<p class="debug-note" id="debugVoiceDown" hidden>voz local indisponível — fala cai pro navegador</p>',
      '<div class="debug-block" aria-label="Estado">',
      '<p class="debug-title">estado</p>',
      '<div class="debug-row"><span class="debug-label">gateway</span><span class="debug-value" id="debugGateway">consultando…</span></div>',
      '<div class="debug-row"><span class="debug-label">voz</span><span class="debug-value" id="debugVoice">verificando…</span></div>',
      '<div class="debug-row"><span class="debug-label">microfone</span><span class="debug-value" id="debugMic">—</span></div>',
      '<div class="debug-row"><span class="debug-label">modo</span><span class="debug-value" id="debugMode">—</span></div>',
      '<div class="debug-row"><span class="debug-label">shell</span><span class="debug-value" id="debugShell">—</span></div>',
      '<div class="debug-row"><span class="debug-label">último comando</span><span class="debug-value" id="debugCommand">—</span></div>',
      '<div class="debug-row"><span class="debug-label">último erro</span><span class="debug-value" id="debugError">—</span></div>',
      "</div>",
      '<div class="debug-block" aria-label="Ações">',
      '<p class="debug-title">ações</p>',
      '<div class="debug-actions">',
      '<button id="debugTestVoice" class="btn" type="button" aria-label="Testar a voz do JARVIS">',
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M19 5a9 9 0 0 1 0 14"/></svg>',
      "testar voz",
      "</button>",
      '<button id="debugCopy" class="btn" type="button" aria-label="Copiar o diagnóstico para a área de transferência">',
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>',
      "copiar diagnóstico",
      "</button>",
      '<button id="debugReload" class="btn" type="button" aria-label="Recarregar o aplicativo">',
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>',
      "recarregar app",
      "</button>",
      "</div>",
      "</div>",
      '<div class="debug-block" aria-label="Ajustes">',
      '<p class="debug-title">ajustes</p>',
      '<label class="debug-row debug-toggle"><span>escuta automática</span>',
      '<input id="debugListen" class="debug-switch" type="checkbox" role="switch" aria-label="Escuta automática ligada ou desligada"></label>',
      '<label class="debug-row debug-toggle"><span>modo quieto</span>',
      '<input id="debugQuiet" class="debug-switch" type="checkbox" role="switch" aria-label="Modo quieto ligado ou desligado"></label>',
      appMode ? '<p class="debug-hint">no app do Mac a escuta é gerenciada pelo JARVIS.</p>' : "",
      '<div class="debug-row debug-volume-row"><span class="debug-label" id="debugVolumeLabel">volume da fala</span>',
      '<input id="debugVolume" class="debug-volume" type="range" min="0" max="100" step="5" value="100" aria-labelledby="debugVolumeLabel"></div>',
      "</div>",
    ].join("");
    document.body.appendChild(panel);

    panel.querySelector("#debugClose")?.addEventListener("click", closeDebug);
    panel.querySelector("#debugTestVoice")?.addEventListener("click", () => {
      cancelPark();
      speak("Teste de voz do Jarvis.");
    });
    panel.querySelector("#debugCopy")?.addEventListener("click", copyDebug);
    panel.querySelector("#debugReload")?.addEventListener("click", restartForUpdate);

    const listenToggle = panel.querySelector("#debugListen");
    listenToggle?.addEventListener("change", () => {
      if (listenToggle.checked) startWakeLoop();
      else stopWakeLoop();
    });
    const quietToggle = panel.querySelector("#debugQuiet");
    quietToggle?.addEventListener("change", () => {
      if (quietToggle.checked) {
        enterQuiet();
        return;
      }
      stayQuiet = false;
      say("De volta.", "Pode pedir, senhor.");
    });
    const volume = panel.querySelector("#debugVolume");
    if (volume) {
      volume.value = String(Math.round(webVolume() * 100));
      volume.addEventListener("input", () => {
        try {
          window.localStorage.setItem(WEB_VOLUME_KEY, String(Number(volume.value) / 100));
        } catch { /* private mode */ }
      });
    }

    probeMicPermission();
    const paint = () => {
      const voiceDown = document.documentElement.classList.contains("voice-down");
      const note = document.getElementById("debugVoiceDown");
      if (note) note.hidden = !voiceDown;
      debugSet("debugGateway", debugGatewayText(), debugGatewayState());
      debugSet("debugVoice", debugVoiceText(), debugVoiceState());
      debugSet("debugMic", micPermissionText(), micPermission === "denied" ? "bad" : "");
      debugSet("debugMode", appMode ? "app (Mac)" : "web", "");
      const stale = document.getElementById("buildLine")?.dataset.state === "stale";
      debugSet("debugShell", stale ? `v${SHELL_VERSION} · desatualizada` : `v${SHELL_VERSION}`, stale ? "warn" : "ok");
      debugSet("debugCommand", lastCommand || "—", "");
      debugSet("debugError", lastError || (lastCommand && !lastError ? "nenhum" : "—"), lastError ? "bad" : "");
      if (listenToggle) {
        listenToggle.checked = keepListening;
        listenToggle.disabled = appMode;
      }
      if (quietToggle) quietToggle.checked = stayQuiet;
    };
    paint();
    debugTimer = window.setInterval(paint, 2000);
  }
})();


