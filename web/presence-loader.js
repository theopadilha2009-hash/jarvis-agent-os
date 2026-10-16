let presenceScheduled = false;

const paletteForPersona = () => document.documentElement.dataset.persona === "ultron"
  ? {
      aurora: ["#240307", "#7F1D1D", "#EF4444"],
      strands: ["#7F1D1D", "#DC2626", "#FB7185"],
    }
  : {
      aurora: ["#2E1065", "#7C3AED", "#A855F7"],
      strands: ["#6D28D9", "#A855F7", "#C084FC"],
    };

const loadPresence = async () => {
  // Cada camada falha por conta própria: o 3D (WebGL) não pode derrubar
  // aurora/strands, e falhando qualquer uma entra o fallback SVG animado.
  const settle = (promise) => promise.then(
    (module) => ({ ok: true, module }),
    (error) => ({ ok: false, error }),
  );
  const [auroraResult, strandsResult, module3d] = await Promise.all([
    settle(import("/ui/aurora.js?v=20260813-apitools1")),
    settle(import("/ui/strands.js?v=20260813-apitools1")),
    settle(import("/ui/jarvis-3d.js?v=20261016-svgfb").catch((error) => {
      window.JarvisNucleiFallback?.mount(
        /webgl|context/i.test(String(error)) ? "WebGL indisponível neste navegador." : "Cena 3D não carregou.",
      );
      return { ok: false, error };
    })),
  ]);
  // WebGL falho dentro do jarvis-3d aciona o fallback no catch dele;
  // aqui só cobrimos a falha do import em si.
  const initialPalette = paletteForPersona();
  const aurora = auroraResult.ok
    ? auroraResult.module.createAurora(document.getElementById("auroraVisual"), {
        colorStops: initialPalette.aurora,
        blend: 0.5,
        amplitude: 1,
        speed: 0.5,
      })
    : null;
  const strands = strandsResult.ok
    ? strandsResult.module.createStrands(document.getElementById("strandsVisual"), {
        colors: initialPalette.strands,
        count: 3,
        speed: 0.5,
        amplitude: 1,
        waviness: 1,
        thickness: 0.7,
        glow: 2.6,
        taper: 3,
        spread: 1,
        intensity: 0.6,
        saturation: 1.5,
        opacity: 1,
        scale: 1.5,
        glass: false,
      })
    : null;
  window.addEventListener("jarvis-persona", () => {
    const palette = paletteForPersona();
    aurora?.setProps({ colorStops: palette.aurora });
    strands?.setProps({ colors: palette.strands });
  });
  const renderTelemetry = document.getElementById("sceneRender");
  if (renderTelemetry) renderTelemetry.textContent = "Aurora + Strands + 3D";
};

const schedulePresence = () => {
  if (presenceScheduled) return;
  presenceScheduled = true;
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(loadPresence, { timeout: 700 });
  } else {
    window.setTimeout(loadPresence, 200);
  }
};

schedulePresence();
