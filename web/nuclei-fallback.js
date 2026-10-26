// Fallback da presença 3D: quando o WebGL falha (GPU desativada, driver,
// contexto perdido), o cockpit não vira bolinhas mortas nem cena animada.
// A cena SVG girando foi removida (pesava e ninguém usava); sobra o aviso
// fixo na tela com os passos para o dono reativar o 3D de verdade.
(() => {
  "use strict";

  const STYLES = `
.nuclei-fallback{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:24px;pointer-events:none}
.nuclei-banner{pointer-events:auto;display:flex;flex-direction:column;gap:6px;max-width:min(92vw,420px);padding:12px 16px;border:1px solid rgba(160,140,255,.28);border-radius:14px;background:rgba(12,10,22,.88);backdrop-filter:blur(6px);font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#cfc6ff}
.nuclei-banner strong{color:#b8a8ff;font-size:12px;letter-spacing:.08em;text-transform:uppercase}
.nuclei-banner ol{margin:0;padding-left:18px}
.nuclei-banner a{color:#8fb8ff}
.nuclei-banner button{align-self:flex-start;padding:4px 10px;border:1px solid rgba(160,140,255,.4);border-radius:999px;background:none;color:#cfc6ff;font:inherit;cursor:pointer}
.nuclei-banner button:hover{background:rgba(160,140,255,.12)}
`;

  const HELP_URL = "https://support.google.com/chrome/answer/95346?hl=pt-BR";

  // O aviso fica na tela: é a única explicação de por que a presença 3D sumiu.
  function bannerHtml(reason) {
    const steps = [
      "Abra chrome://settings/system",
      "Ative “Usar aceleração de hardware quando disponível”",
      "Reinicie o Chrome e recarregue o cockpit",
    ].map((step) => `<li>${step}</li>`).join("");
    return `<div class="nuclei-banner" role="status">
<strong>3D indisponível — presença em modo seguro</strong>
<span>${reason ? String(reason).slice(0, 120) : "O WebGL deste navegador está desligado."}</span>
<ol>${steps}</ol>
<span>Guia oficial: <a href="${HELP_URL}" target="_blank" rel="noopener noreferrer">ativar aceleração de hardware no Chrome</a></span>
<button type="button" data-nfx-copy>Copiar passos</button>
</div>`;
  }

  function mount(reason) {
    const host = document.getElementById("avatar3d") || document.getElementById("presence");
    if (!host || host.querySelector(".nuclei-fallback")) return;
    const style = document.createElement("style");
    style.textContent = STYLES;
    document.head.appendChild(style);
    const wrap = document.createElement("div");
    wrap.className = "nuclei-fallback";
    wrap.innerHTML = bannerHtml(reason);
    host.classList.add("nuclei-live");
    // Sem isso o palco pode ficar preso em data-nuclei="3d" e a legenda dos
    // núcleos aparecer flutuando sobre o aviso.
    document.querySelector(".stage")?.setAttribute("data-nuclei", "fallback");
    // Sem GPU, cada backdrop-filter é rasterizado na CPU a cada frame:
    // medido 29,2% → 22,5% de CPU do Chrome desligando o vidro.
    document.documentElement.dataset.gpu = "off";
    host.appendChild(wrap);
    wrap.querySelector("[data-nfx-copy]")?.addEventListener("click", () => {
      const text = [
        "Reativar o 3D do cockpit JARVIS:",
        "1. Abra chrome://settings/system",
        "2. Ative “Usar aceleração de hardware quando disponível”",
        "3. Reinicie o Chrome e recarregue o cockpit",
        `Guia: ${HELP_URL}`,
      ].join("\n");
      navigator.clipboard?.writeText(text);
    });
  }

  window.JarvisNucleiFallback = { mount };
})();