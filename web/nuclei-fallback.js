// Fallback da presença 3D: quando o WebGL falha (GPU desativada, driver,
// contexto perdido), o cockpit não pode virar bolinhas mortas. Aqui ficam os
// núcleos em SVG animado — CSS puro, funciona em qualquer navegador — e o
// guia para o dono reativar o 3D de verdade.
(() => {
  "use strict";
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const STYLES = `
.nuclei-fallback{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;pointer-events:none}
.nuclei-fallback svg{width:min(74vmin,560px);height:auto;overflow:visible}
.nuclei-fallback .nfx-ring{transform-origin:300px 300px}
.nfx-slow{animation:nfx-spin 46s linear infinite}
.nfx-mid{animation:nfx-spin 30s linear infinite reverse}
.nfx-fast{animation:nfx-spin 18s linear infinite}
.nfx-core{transform-origin:300px 300px;animation:nfx-pulse 5.2s ease-in-out infinite}
.nfx-spark{animation:nfx-flicker 2.4s ease-in-out infinite}
.nfx-spark2{animation:nfx-flicker 3.1s ease-in-out infinite .8s}
.nfx-orbit{transform-origin:300px 300px}
.nfx-orbit-1{animation:nfx-spin 26s linear infinite}
.nfx-orbit-2{animation:nfx-spin 38s linear infinite reverse}
.nfx-orbit-3{animation:nfx-spin 52s linear infinite}
@keyframes nfx-spin{to{transform:rotate(360deg)}}
@keyframes nfx-pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}
@keyframes nfx-flicker{0%,100%{opacity:.25}50%{opacity:1}}
@media (prefers-reduced-motion: reduce){
  .nuclei-fallback .nfx-ring,.nuclei-fallback .nfx-core,.nuclei-fallback .nfx-spark,.nuclei-fallback .nfx-orbit{animation:none}
}
.nuclei-chip{pointer-events:auto;position:absolute;left:12px;bottom:12px;padding:3px 10px;border:1px solid rgba(160,140,255,.3);border-radius:999px;background:rgba(12,10,22,.7);color:#9c90c9;font:10px/1.4 ui-monospace,Menlo,monospace;letter-spacing:.06em;cursor:pointer}
.nuclei-chip:hover{color:#cfc6ff;border-color:rgba(160,140,255,.6)}
.nuclei-banner{pointer-events:auto;display:flex;flex-direction:column;gap:6px;max-width:min(92vw,420px);padding:12px 16px;border:1px solid rgba(160,140,255,.28);border-radius:14px;background:rgba(12,10,22,.88);backdrop-filter:blur(6px);font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#cfc6ff}
.nuclei-banner strong{color:#b8a8ff;font-size:12px;letter-spacing:.08em;text-transform:uppercase}
.nuclei-banner ol{margin:0;padding-left:18px}
.nuclei-banner a{color:#8fb8ff}
.nuclei-banner button{align-self:flex-start;padding:4px 10px;border:1px solid rgba(160,140,255,.4);border-radius:999px;background:none;color:#cfc6ff;font:inherit;cursor:pointer}
.nuclei-banner button:hover{background:rgba(160,140,255,.12)}
`;

  function sceneSvg() {
    return `<svg viewBox="0 0 600 600" role="img" aria-label="Presença do JARVIS em modo seguro">
<defs>
<radialGradient id="nfxGlowCore" cx="50%" cy="45%" r="60%">
<stop offset="0%" stop-color="#d8ccff"/><stop offset="45%" stop-color="#8a6cff"/><stop offset="100%" stop-color="#241a4d"/>
</radialGradient>
<radialGradient id="nfxGlowNucleus" cx="50%" cy="42%" r="60%">
<stop offset="0%" stop-color="#efe9ff"/><stop offset="55%" stop-color="#8a6cff"/><stop offset="100%" stop-color="#2a2058"/>
</radialGradient>
<radialGradient id="nfxGlowForge" cx="50%" cy="42%" r="60%">
<stop offset="0%" stop-color="#ffe7cf"/><stop offset="55%" stop-color="#ff9d5c"/><stop offset="100%" stop-color="#4d2a12"/>
</radialGradient>
<radialGradient id="nfxGlowMemory" cx="50%" cy="42%" r="60%">
<stop offset="0%" stop-color="#dff1ff"/><stop offset="55%" stop-color="#7fb6ff"/><stop offset="100%" stop-color="#12314d"/>
</radialGradient>
<filter id="nfxBlur" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="7"/></filter>
</defs>
<g class="nfx-ring nfx-slow" stroke="#8a6cff" stroke-opacity=".28" fill="none">
<circle cx="300" cy="300" r="252" stroke-dasharray="3 14" stroke-width="1.4"/>
</g>
<g class="nfx-ring nfx-mid" stroke="#7fb6ff" stroke-opacity=".22" fill="none">
<circle cx="300" cy="300" r="212" stroke-dasharray="60 26 8 26" stroke-width="1.6"/>
</g>
<g class="nfx-ring nfx-fast" stroke="#ff9d5c" stroke-opacity=".2" fill="none">
<circle cx="300" cy="300" r="176" stroke-dasharray="2 10" stroke-width="1.2"/>
</g>
<g class="nfx-core">
<circle cx="300" cy="300" r="86" fill="#8a6cff" opacity=".22" filter="url(#nfxBlur)"/>
<circle cx="300" cy="300" r="58" fill="url(#nfxGlowCore)"/>
<circle cx="300" cy="300" r="58" fill="none" stroke="#cfc6ff" stroke-opacity=".5" stroke-width="1.2"/>
<ellipse cx="300" cy="278" rx="30" ry="12" fill="#efe9ff" opacity=".35"/>
</g>
<g class="nfx-orbit nfx-orbit-1">
<g transform="translate(300 88)">
<circle r="30" fill="#8a6cff" opacity=".25" filter="url(#nfxBlur)"/>
<circle r="19" fill="url(#nfxGlowNucleus)"/>
<circle r="19" fill="none" stroke="#cfc6ff" stroke-opacity=".4"/>
<text y="52" text-anchor="middle" font-family="ui-monospace,Menlo,monospace" font-size="15" letter-spacing="2" fill="#cfc6ff">NÚCLEO</text>
</g>
</g>
<g class="nfx-orbit nfx-orbit-2">
<g transform="translate(475 385)">
<g class="nfx-spark" stroke="#ff9d5c" stroke-width="2" stroke-linecap="round">
<line x1="-30" y1="-6" x2="-20" y2="-6"/><line x1="20" y1="8" x2="30" y2="8"/><line x1="-8" y1="-28" x2="-8" y2="-20"/>
</g>
<circle r="30" fill="#ff9d5c" opacity=".25" filter="url(#nfxBlur)"/>
<circle r="19" fill="url(#nfxGlowForge)"/>
<circle r="19" fill="none" stroke="#ffe7cf" stroke-opacity=".4"/>
<text y="52" text-anchor="middle" font-family="ui-monospace,Menlo,monospace" font-size="15" letter-spacing="2" fill="#ffe0c4">FORJA</text>
</g>
</g>
<g class="nfx-orbit nfx-orbit-3">
<g transform="translate(125 385)">
<g class="nfx-spark2" fill="#7fb6ff">
<circle cx="-14" cy="-24" r="2.2"/><circle cx="18" cy="-16" r="1.8"/><circle cx="6" cy="26" r="2"/>
</g>
<circle r="30" fill="#7fb6ff" opacity=".25" filter="url(#nfxBlur)"/>
<circle r="19" fill="url(#nfxGlowMemory)"/>
<circle r="19" fill="none" stroke="#dff1ff" stroke-opacity=".4"/>
<text y="52" text-anchor="middle" font-family="ui-monospace,Menlo,monospace" font-size="15" letter-spacing="2" fill="#c4e2ff">MEMÓRIA</text>
</g>
</g>
</svg>`;
  }

  const HELP_URL = "https://support.google.com/chrome/answer/95346?hl=pt-BR";

  // O aviso não pode poluir a cena: fica num chip discreto e só abre quem clicar.
  function bannerHtml(reason) {
    const steps = [
      "Abra chrome://settings/system",
      "Ative “Usar aceleração de hardware quando disponível”",
      "Reinicie o Chrome e recarregue o cockpit",
    ].map((step) => `<li>${step}</li>`).join("");
    return `<button class="nuclei-chip" type="button" data-nfx-toggle aria-expanded="false" title="3D indisponível — ver como reativar">3D off</button>
<div class="nuclei-banner" role="status" data-nfx-panel hidden>
<strong>3D indisponível — presença em modo seguro</strong>
<span>${reason ? String(reason).slice(0, 120) : "O WebGL deste navegador está desligado."} A cena SVG animada assume enquanto isso.</span>
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
    wrap.innerHTML = sceneSvg() + bannerHtml(reason);
    host.classList.add("nuclei-live");
    host.appendChild(wrap);
    const chip = wrap.querySelector("[data-nfx-toggle]");
    const panel = wrap.querySelector("[data-nfx-panel]");
    chip?.addEventListener("click", () => {
      const open = panel.hasAttribute("hidden");
      panel.toggleAttribute("hidden", !open);
      chip.setAttribute("aria-expanded", String(open));
    });
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
