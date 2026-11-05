// Instalação no Chromebook (e em qualquer Chrome/Edge desktop).
//
// No ChromeOS o JARVIS não vira .zip nem .dmg: o Chrome instala a página
// como app. O navegador só deixa o botão funcionar quando dispara
// `beforeinstallprompt` sozinho — por isso guardamos o evento e só
// mostramos o botão quando ele existe. Prometer um botão que não instala
// seria pior do que não ter botão nenhum.
(() => {
  "use strict";

  const botao = document.getElementById("instalarChromebook");
  const nota = document.getElementById("notaChromebook");
  const botaoBoasVindas = document.getElementById("welcomeChromebookButton");
  let evento = null;

  const ehChromeOS = /CrOS/i.test(navigator.userAgent || "");
  const ehChrome = /\bChrome\/\d+/i.test(navigator.userAgent || "");
  const jaInstalado = window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true;

  function mostrarNota() {
    if (nota) nota.hidden = false;
  }

  // Na tela de boas-vindas o botão de Mac/Windows não serve para quem está
  // num Chromebook. Trocamos o rótulo e o destino em vez de oferecer um
  // download que não instala.
  function ajustarBoasVindas() {
    if (!botaoBoasVindas || !ehChromeOS) return;
    botaoBoasVindas.hidden = false;
    const mac = document.getElementById("welcomeAppButton");
    if (mac) mac.hidden = true;
    botaoBoasVindas.addEventListener("click", () => {
      if (evento) {
        evento.prompt();
        return;
      }
      // Sem prompt disponível: abre o painel de download, onde está a
      // instrução manual do menu do Chrome.
      document.querySelector('[data-system-tab="baixar"]')?.click();
    });
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    evento = event;
    if (botao) botao.hidden = false;
    // No Chromebook a dica aparece mesmo com o botão: o aluno precisa saber
    // que existe app instalável, senão nunca procura no menu do Chrome.
    if (ehChromeOS) mostrarNota();
  });

  window.addEventListener("appinstalled", () => {
    if (botao) botao.hidden = true;
    if (nota) nota.hidden = true;
    evento = null;
  });

  ajustarBoasVindas();

  if (botao) {
    botao.addEventListener("click", async () => {
      if (!evento) return;
      botao.disabled = true;
      try {
        evento.prompt();
        const escolha = await evento.userChoice;
        if (escolha?.outcome === "dismissed") {
          botao.disabled = false;
        }
      } catch {
        botao.disabled = false;
      }
      evento = null;
    });
  }

  // Chromebook com a página já instalada: não oferece de novo.
  if (jaInstalado) {
    if (botao) botao.hidden = true;
    if (nota) nota.hidden = true;
    return;
  }

  // ChromeOS sem beforeinstallprompt (comum quando faltam ícones maskable):
  // mostra só a instrução manual, que sempre funciona.
  if (ehChromeOS && ehChrome) {
    window.setTimeout(() => {
      if (!evento) mostrarNota();
    }, 1500);
  }
})();