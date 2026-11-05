// Modo leve: o JARVIS inteiro num Chromebook de escola.
//
// Chromebook de escola tem 4 GB (às vezes 2), Celeron, GPU que é só um nome e
// wifi que cai. O cockpit carrega 1,2 MB e monta três cenas WebGL; nesse
// aparelho isso vira aba travada e o aluno desiste.
//
// A regra: nenhum sinal sozinho é confiável. `deviceMemory` mente (o Chrome
// arredonda para 0.25/0.5/1/2/4/8), `hardwareConcurrency` mente em aparelho
// virtualizado, e WebGL "funciona" via SwiftShader — que é software puro e
// congela a aba. Por isso somamos sinais e deixamos o dono forçar.
//
// Carregado como script clássico, antes de qualquer módulo, para a decisão
// valer já no primeiro paint (sem piscar a cena 3D e depois sumir).
(() => {
  "use strict";

  const CHAVE = "jarvis-modo-leve-v1";
  const RAIZ = document.documentElement;

  function lerForcado() {
    // ?leve=1 liga, ?leve=0 desliga. O dono manda mais que a heurística.
    try {
      const params = new URLSearchParams(window.location.search);
      const bruto = params.get("leve");
      if (bruto === "1" || bruto === "true") return true;
      if (bruto === "0" || bruto === "false") return false;
    } catch { /* URL estranha: segue a heurística */ }
    return null;
  }

  function lerGravado() {
    try {
      const valor = window.localStorage.getItem(CHAVE);
      if (valor === "1") return true;
      if (valor === "0") return false;
    } catch { /* aba anônima bloqueia: não é erro, é só ausência */ }
    return null;
  }

  function gravar(ligado) {
    try {
      window.localStorage.setItem(CHAVE, ligado ? "1" : "0");
    } catch { /* sem storage a escolha vale só nesta sessão */ }
  }

  function webglPorSoftware() {
    // SwiftShader/llvmpipe rodam WebGL na CPU. Renderiza, mas a 3 fps.
    try {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
      if (!gl) return true; // sem WebGL nenhum: definitivamente leve
      const info = gl.getExtension("WEBGL_debug_renderer_info");
      const renderer = info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL) || "") : "";
      const vendor = info ? String(gl.getParameter(info.UNMASKED_VENDOR_WEBGL) || "") : "";
      const assinatura = `${renderer} ${vendor}`.toLowerCase();
      return /swiftshader|llvmpipe|software|mesa offscreen/.test(assinatura);
    } catch {
      return true;
    }
  }

  function sinais() {
    const motivos = [];
    const nucleos = Number(navigator.hardwareConcurrency) || 0;
    if (nucleos && nucleos <= 4) motivos.push(`nucleos:${nucleos}`);

    const memoria = Number(navigator.deviceMemory) || 0;
    if (memoria && memoria <= 4) motivos.push(`memoria:${memoria}`);

    const conexao = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (conexao) {
      if (conexao.saveData) motivos.push("economia-de-dados");
      if (/^(?:slow-2g|2g|3g)$/.test(String(conexao.effectiveType || ""))) {
        motivos.push(`rede:${conexao.effectiveType}`);
      }
    }

    try {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) motivos.push("movimento-reduzido");
    } catch { /* navegador antigo sem matchMedia */ }

    if (webglPorSoftware()) motivos.push("webgl-por-software");
    return motivos;
  }

  function decidir() {
    const forcado = lerForcado();
    if (forcado !== null) {
      gravar(forcado);
      return { leve: forcado, motivos: ["escolha-manual"] };
    }
    const gravado = lerGravado();
    if (gravado !== null) return { leve: gravado, motivos: ["preferencia-salva"] };

    const motivos = sinais();
    // Dois sinais ou mais: um só dá falso positivo (um Mac com 4 núcleos não
    // é fraco). WebGL por software sozinho já basta — é o caso do Chromebook.
    const leve = motivos.length >= 2 || motivos.includes("webgl-por-software");
    return { leve, motivos };
  }

  const decisao = decidir();

  // A classe no <html> é o contrato com o CSS: tudo que é pesado se esconde
  // por seletor, sem esperar JavaScript de módulo carregar.
  RAIZ.classList.toggle("modo-leve", decisao.leve);
  RAIZ.dataset.modoLeve = decisao.leve ? "1" : "0";
  if (decisao.motivos.length) RAIZ.dataset.modoLeveMotivos = decisao.motivos.join(",");

  window.JarvisLeve = {
    ativo: decisao.leve,
    motivos: decisao.motivos,
    ligar() { gravar(true); window.location.reload(); },
    desligar() { gravar(false); window.location.reload(); },
  };

  // Aviso discreto quando o modo leve entrou sozinho. Sem isso o dono acha
  // que o 3D quebrou; com o botão, ele sai quando quiser e a escolha fica.
  // Mostra sempre que o modo leve estiver ligado, inclusive quando veio de
  // ?leve=1: aquela visita grava a escolha, e sem o aviso o dono não teria
  // como voltar atrás nas próximas. Sempre tem saída visível.
  if (!decisao.leve) return;

  function montarAviso() {
    if (document.querySelector(".modo-leve-aviso")) return;
    const caixa = document.createElement("div");
    caixa.className = "modo-leve-aviso";
    const rotulo = document.createElement("span");
    rotulo.textContent = "Modo leve";
    const botao = document.createElement("button");
    botao.type = "button";
    botao.textContent = "Usar efeitos completos";
    botao.addEventListener("click", () => window.JarvisLeve.desligar());
    caixa.append(rotulo, botao);
    document.body.appendChild(caixa);
  }

  if (document.body) montarAviso();
  else document.addEventListener("DOMContentLoaded", montarAviso, { once: true });
})();
