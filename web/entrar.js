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
  const signupForm = document.getElementById("signupForm");
  const signupToggle = document.getElementById("signupToggle");
  const signupError = document.getElementById("signupError");
  const signupDone = document.getElementById("signupDone");
  const signupUser = document.getElementById("signupUser");
  const signupPass = document.getElementById("signupPass");
  const signupPass2 = document.getElementById("signupPass2");
  const signupTerms = document.getElementById("signupTerms");
  const signupSubmit = document.getElementById("signupSubmit");

  const showSignupError = (text) => {
    signupError.hidden = !text;
    signupError.textContent = text || "";
  };

  const showSignup = (visible) => {
    form.hidden = visible;
    signupForm.hidden = !visible;
    if (visible) signupUser.focus();
    else pass.focus();
  };

  signupToggle.addEventListener("click", () => {
    showSignupError("");
    signupDone.hidden = true;
    showSignup(signupForm.hidden);
  });

  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = signupUser.value.trim().toLowerCase();
    const password = signupPass.value;
    if (!username || !password) {
      showSignupError("Informe login e senha.");
      return;
    }
    if (password !== signupPass2.value) {
      showSignupError("As senhas não conferem.");
      return;
    }
    if (!signupTerms.checked) {
      showSignupError("Aceite os termos de uso para criar a conta.");
      return;
    }
    signupSubmit.disabled = true;
    showSignupError("");
    signupDone.hidden = true;
    try {
      const response = await fetch("/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, accepted_terms: true }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        showSignupError(data.error || "Não consegui criar a conta agora.");
        return;
      }
      user.value = username;
      pass.value = "";
      signupPass.value = "";
      signupPass2.value = "";
      signupDone.textContent = "Conta criada. " + (data.message || "Aguardando aprovação do Theo para o modo code.") + " Faça login acima.";
      showSignup(false);
      signupDone.hidden = false;
    } catch {
      showSignupError("Não consegui criar a conta agora.");
    } finally {
      signupSubmit.disabled = false;
    }
  });

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
      // Onboarding de primeira experiencia: o trigger atravessa a navegação
      // para /cockpit, onde /ui/onboarding.js escuta o evento e abre o wizard.
      try { localStorage.setItem("jarvis-onboarding-trigger", username); } catch { /* sem storage */ }
      window.dispatchEvent(new CustomEvent("jarvis-onboarding", { detail: { username } }));
      goCockpit();
    } catch {
      showError("Não consegui validar o login agora.");
    } finally {
      submit.disabled = false;
    }
  });

  probeSession();
})();
