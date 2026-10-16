(() => {
  "use strict";

  // Onboarding de primeira experiencia do cockpit.
  // Gatilho: entrar.js grava "jarvis-onboarding-trigger" antes de navegar para
  // /cockpit e dispara o evento "jarvis-onboarding". Aqui o wizard abre UMA vez
  // por usuario (chave localStorage com username) e so desaparece para sempre
  // quando todos os passos sao marcados ou o usuario pula tudo.

  const TRIGGER_KEY = "jarvis-onboarding-trigger";
  const KEY_PREFIX = "jarvis-onboarding-v1:";
  const OPEN_DELAY_MS = 700;

  const stepIds = ["ia", "app", "agenda", "code"];

  const currentUsername = () => {
    try {
      return (localStorage.getItem("jarvis-last-login") || "").trim();
    } catch {
      return "";
    }
  };

  const recordKey = (username) => KEY_PREFIX + (username || "visitante");

  const readRecord = (username) => {
    try {
      const parsed = JSON.parse(localStorage.getItem(recordKey(username)) || "null");
      if (parsed && parsed.version === 1 && parsed.steps && typeof parsed.steps === "object") {
        return parsed;
      }
    } catch { /* registro corrompido: recomeca do zero */ }
    return null;
  };

  const writeRecord = (username, steps, done) => {
    try {
      localStorage.setItem(recordKey(username), JSON.stringify({
        version: 1,
        done: Boolean(done),
        steps,
        at: new Date().toISOString(),
      }));
    } catch { /* sem storage: wizard continua apenas nesta sessao */ }
  };

  const clearTrigger = () => {
    try { localStorage.removeItem(TRIGGER_KEY); } catch { /* ignore */ }
  };

  const iaConnected = () => {
    try {
      return Boolean(window.JarvisApiVault?.configured("openrouter"));
    } catch {
      return false;
    }
  };

  const steps = [
    {
      id: "ia",
      title: "Conecte sua IA",
      text: "Traga sua própria chave (OpenRouter, ElevenLabs). Fica criptografada neste dispositivo, no cofre de APIs.",
      actionLabel: "Abrir cofre de APIs",
      autoCheck: iaConnected,
      run: () => {
        const button = document.getElementById("integrationsButton");
        if (button) button.click();
        return Boolean(button);
      },
    },
    {
      id: "app",
      title: "Baixe o app no Mac",
      text: "O cockpit roda no navegador, mas o app nativo traz o wake word e o orbe na sua mesa.",
      actionHtml: { tag: "a", href: "/download/mac", label: "Baixar app do Mac" },
      secondaryLabel: "Já tenho o app",
    },
    {
      id: "agenda",
      title: "Conecte agenda e integrações",
      text: "A agenda vive no próprio cockpit (peça \"mostre minha agenda\") e o cofre também guarda n8n e outras APIs.",
      actionLabel: "Abrir integrações",
      run: () => {
        const button = document.getElementById("integrationsButton");
        if (button) button.click();
        return Boolean(button);
      },
    },
    {
      id: "code",
      title: "Peça aprovação do modo code",
      text: "Contas novas nascem pendentes: o Theo aprova manualmente para liberar execução de código. Peça por aqui mesmo.",
      actionLabel: "Ver contas",
      run: () => {
        window.JarvisAccountsPanel?.open?.();
        return Boolean(window.JarvisAccountsPanel?.open);
      },
    },
  ];

  let dialog = null;
  let refs = null;
  let openUsername = "";

  const doneSteps = () => stepIds.filter((id) => refs?.state[id]).length;

  const paint = () => {
    if (!refs) return;
    refs.cards.forEach((card) => {
      card.dataset.done = String(Boolean(refs.state[card.dataset.step]));
      const box = card.querySelector("input[type=\"checkbox\"]");
      if (box) box.checked = Boolean(refs.state[card.dataset.step]);
    });
    refs.dots.forEach((dot, index) => {
      const id = stepIds[index];
      dot.dataset.state = refs.state[id] ? "done" : index === doneSteps() ? "current" : "todo";
    });
    refs.progressLabel.textContent = `Passo ${Math.min(doneSteps() + 1, stepIds.length)} de ${stepIds.length}`;
    refs.finish.disabled = doneSteps() !== stepIds.length;
  };

  const persist = (done) => {
    writeRecord(openUsername, refs.state, done);
  };

  const finish = () => {
    persist(true);
    clearTrigger();
    closeDialog();
    window.dispatchEvent(new CustomEvent("jarvis-onboarding-done", { detail: { username: openUsername } }));
  };

  const closeDialog = () => {
    if (dialog?.open) dialog.close("finished");
  };

  const buildCard = (step) => {
    const card = document.createElement("div");
    card.className = "onboarding-step";
    card.dataset.step = step.id;

    const box = document.createElement("input");
    box.type = "checkbox";
    box.id = `onboarding-${step.id}`;
    box.dataset.testid = `onboarding-check-${step.id}`;
    box.checked = Boolean(refs.state[step.id]) || Boolean(step.autoCheck?.());
    if (step.autoCheck?.()) box.disabled = true;
    box.addEventListener("change", () => {
      refs.state[step.id] = box.checked;
      persist(false);
      paint();
    });

    const label = document.createElement("label");
    label.className = "onboarding-step-body";
    label.htmlFor = box.id;

    const title = document.createElement("p");
    title.className = "onboarding-step-title";
    title.textContent = step.title;

    const text = document.createElement("p");
    text.className = "onboarding-step-text";
    text.textContent = step.text;

    label.append(title, text);

    const actions = document.createElement("div");
    actions.className = "onboarding-step-actions";

    if (step.actionHtml) {
      const link = document.createElement(step.actionHtml.tag);
      link.href = step.actionHtml.href;
      link.textContent = step.actionHtml.label;
      link.className = "onboarding-action";
      link.rel = "noopener";
      actions.append(link);
    }

    if (step.actionLabel) {
      const action = document.createElement("button");
      action.type = "button";
      action.className = "onboarding-action";
      action.textContent = step.actionLabel;
      action.addEventListener("click", () => {
        const ok = step.run?.();
        if (!ok) {
          action.disabled = true;
          action.textContent = "Indisponível agora";
        }
      });
      actions.append(action);
    }

    if (step.secondaryLabel) {
      const secondary = document.createElement("button");
      secondary.type = "button";
      secondary.className = "onboarding-action onboarding-action-secondary";
      secondary.textContent = step.secondaryLabel;
      secondary.addEventListener("click", () => {
        refs.state[step.id] = true;
        persist(false);
        paint();
      });
      actions.append(secondary);
    }

    if (actions.childElementCount) label.append(actions);

    if (step.autoCheck?.()) {
      const chip = document.createElement("span");
      chip.className = "onboarding-done-chip";
      chip.textContent = "Conectado";
      label.append(chip);
    }

    card.append(box, label);
    return card;
  };

  const buildDialog = (username) => {
    const element = document.createElement("dialog");
    element.className = "onboarding-dialog";
    element.setAttribute("aria-labelledby", "onboardingTitle");
    element.setAttribute("aria-describedby", "onboardingIntro");

    const head = document.createElement("div");
    head.className = "onboarding-head";
    const headText = document.createElement("div");
    headText.className = "onboarding-head-text";
    const eyebrow = document.createElement("p");
    eyebrow.className = "onboarding-eyebrow";
    eyebrow.textContent = "Primeiros passos";
    const title = document.createElement("h2");
    title.className = "onboarding-title";
    title.id = "onboardingTitle";
    title.textContent = username ? `Bem-vindo, ${username}` : "Bem-vindo ao JARVIS";
    headText.append(eyebrow, title);
    const close = document.createElement("button");
    close.type = "button";
    close.className = "onboarding-close";
    close.textContent = "×";
    close.setAttribute("aria-label", "Fechar onboarding");
    close.addEventListener("click", closeDialog);
    head.append(headText, close);

    const intro = document.createElement("p");
    intro.className = "onboarding-progress-label";
    intro.id = "onboardingIntro";
    intro.hidden = true;
    intro.textContent = "Quatro passos para deixar o JARVIS do seu jeito. Pode pular e voltar depois.";

    const progress = document.createElement("div");
    progress.className = "onboarding-progress";
    const track = document.createElement("div");
    track.className = "onboarding-progress-track";
    const dots = stepIds.map(() => {
      const dot = document.createElement("span");
      dot.className = "onboarding-dot";
      dot.setAttribute("aria-hidden", "true");
      track.append(dot);
      return dot;
    });
    const progressLabel = document.createElement("p");
    progressLabel.className = "onboarding-progress-label";
    progressLabel.setAttribute("aria-live", "polite");
    progress.append(track, progressLabel);

    const stepsWrap = document.createElement("div");
    stepsWrap.className = "onboarding-steps";
    steps.forEach((step) => stepsWrap.append(buildCard(step)));
    const builtCards = [...stepsWrap.children];

    const foot = document.createElement("div");
    foot.className = "onboarding-foot";
    const skip = document.createElement("button");
    skip.type = "button";
    skip.className = "onboarding-skip";
    skip.textContent = "Pular tudo";
    skip.setAttribute("aria-label", "Pular onboarding e não mostrar novamente");
    skip.addEventListener("click", finish);
    const finishButton = document.createElement("button");
    finishButton.type = "button";
    finishButton.className = "onboarding-finish";
    finishButton.dataset.testid = "onboarding-finish";
    finishButton.textContent = "Concluir";
    finishButton.addEventListener("click", finish);
    foot.append(skip, finishButton);

    element.append(head, intro, progress, stepsWrap, foot);
    element.addEventListener("cancel", () => {
      // Esc fecha sem concluir: progresso fica salvo e o wizard volta no próximo login.
      element.close("dismissed");
    });

    refs = { state: refs?.state || {}, dots, progressLabel, finish: finishButton, cards: builtCards };
    dialog = element;
    document.body.append(element);
  };

  const maybeOpen = (username) => {
    const user = (username || currentUsername()).trim();
    const record = readRecord(user);
    if (record?.done) return;

    if (!dialog || !dialog.isConnected) buildDialog(user);
    openUsername = user;
    refs.state = { ...(record?.steps || {}), ia: iaConnected() || Boolean(record?.steps?.ia) };
    persist(false);
    paint();
    if (!dialog.open) dialog.showModal();
  };

  window.addEventListener("jarvis-onboarding", (event) => {
    maybeOpen(event.detail?.username);
  });

  const boot = () => {
    let trigger = "";
    try {
      trigger = (localStorage.getItem(TRIGGER_KEY) || "").trim();
    } catch { /* sem storage */ }
    if (trigger) {
      clearTrigger();
      maybeOpen(trigger);
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => window.setTimeout(boot, OPEN_DELAY_MS), { once: true });
  } else {
    window.setTimeout(boot, OPEN_DELAY_MS);
  }
})();
