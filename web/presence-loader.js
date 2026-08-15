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
  const [auroraModule, strandsModule] = await Promise.all([
    import("/ui/aurora.js?v=20260813-apitools1"),
    import("/ui/strands.js?v=20260813-apitools1"),
    import("/ui/jarvis-3d.js?v=20260814-nucleus2"),
  ]);
  const initialPalette = paletteForPersona();
  const aurora = auroraModule.createAurora(document.getElementById("auroraVisual"), {
    colorStops: initialPalette.aurora,
    blend: 0.5,
    amplitude: 1,
    speed: 0.5,
  });
  const strands = strandsModule.createStrands(document.getElementById("strandsVisual"), {
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
  });
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
