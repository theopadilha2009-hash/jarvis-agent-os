(() => {
  "use strict";

  const TOKEN_KEY = "jarvis-owner-token-v1";
  const LAST_LOGIN_KEY = "jarvis-last-login";
  const form = document.getElementById("loginForm");
  const errorBox = document.getElementById("loginError");
  const submit = document.getElementById("loginSubmit");
  const user = document.getElementById("loginUser");
  const pass = document.getElementById("loginPass");
  const sessionHint = document.getElementById("sessionHint");

  const showError = (text) => {
    errorBox.hidden = !text;
    errorBox.textContent = text || "";
  };

  const token = () => {
    try { return localStorage.getItem(TOKEN_KEY) || ""; } catch { return ""; }
  };

  const persist = (sessionToken, username) => {
    localStorage.setItem(TOKEN_KEY, sessionToken);
    if (username) localStorage.setItem(LAST_LOGIN_KEY, username);
  };

  const goCockpit = () => {
    window.location.replace("/cockpit" + (window.location.search || ""));
  };

  if (/[?&]arrival=/.test(window.location.search)) {
    window.location.replace("/cockpit" + window.location.search);
    return;
  }

  async function probeSession() {
    const value = token();
    if (!value) return;
    try {
      const response = await fetch("/status", {
        headers: { "X-Jarvis-Owner-Token": value },
        signal: AbortSignal.timeout?.(8000),
      });
      const data = await response.json().catch(() => ({}));
      const access = data.access || {};
      if (access.owner || access.code || data.owner) {
        sessionHint.hidden = false;
      }
    } catch { /* sessão morta: o formulário continua sendo a entrada */ }
  }

  try {
    const remembered = localStorage.getItem(LAST_LOGIN_KEY);
    if (remembered) user.value = remembered;
  } catch { /* primeira visita */ }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = user.value.trim();
    const password = pass.value;
    if (!username || !password) {
      showError("Informe login e senha.");
      return;
    }
    submit.disabled = true;
    showError("");
    try {
      const response = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.session_token) {
        showError(data.error || "Login recusado.");
        return;
      }
      persist(data.session_token, username);
      pass.value = "";
      goCockpit();
    } catch {
      showError("Não consegui validar o login agora.");
    } finally {
      submit.disabled = false;
    }
  });

  probeSession();
})();
