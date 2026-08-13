import { Renderer, Program, Mesh, Color, Triangle, RenderTarget } from "ogl";

const MAX_STRANDS = 12;
const MAX_COLORS = 8;

const VERT = `#version 300 es
in vec2 position;
void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const FRAG = `#version 300 es
precision highp float;

uniform float uTime;
uniform vec2 uResolution;
uniform vec3 uColors[${MAX_COLORS}];
uniform int uColorCount;
uniform int uStrandCount;
uniform float uSpeed;
uniform float uAmplitude;
uniform float uWaviness;
uniform float uThickness;
uniform float uGlow;
uniform float uTaper;
uniform float uSpread;
uniform float uHueShift;
uniform float uIntensity;
uniform float uOpacity;
uniform float uScale;
uniform float uSaturation;

out vec4 fragColor;

const float PI = 3.14159265;

vec3 spectrum(float t) {
  return 0.5 + 0.5 * cos(2.0 * PI * (t + vec3(0.00, 0.33, 0.67)));
}

vec3 samplePalette(float t) {
  t = fract(t);
  float scaled = t * float(uColorCount);
  int idx = int(floor(scaled));
  float blend = fract(scaled);
  int nextIdx = idx + 1;
  if (nextIdx >= uColorCount) nextIdx = 0;
  return mix(uColors[idx], uColors[nextIdx], blend);
}

vec3 strandColor(float t) {
  if (uColorCount > 0) return samplePalette(t);
  return spectrum(t);
}

void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;
  uv /= max(uScale, 0.0001);

  float e = 0.06 + uIntensity * 0.94;
  float env = pow(max(cos(uv.x * PI * 1.3), 0.0), uTaper);

  vec3 col = vec3(0.0);

  for (int i = 0; i < ${MAX_STRANDS}; i++) {
    if (i >= uStrandCount) break;

    float fi = float(i);
    float ph = fi * 1.7 * uSpread;
    float freq = (2.0 + fi * 0.35) * uWaviness;
    float spd = 1.4 + fi * 1.2;

    float tt = uTime * uSpeed;
    float w = sin(uv.x * freq + tt * spd + ph) * 0.60
            + sin(uv.x * freq * 1.1 - tt * spd * 0.7 + ph * 1.7) * 0.40;

    float amp = (0.1 + 0.02 * e) * env * uAmplitude;
    float y = w * amp;

    float d = abs(uv.y - y);
    float thick = (0.001 + 0.05 * e) * (0.35 + env) * uThickness;
    float g = thick / (d + thick * 0.45);
    g = g * g;

    float h = fi / float(uStrandCount) + uv.x * 0.30 + uTime * 0.04 + uHueShift;
    col += strandColor(h) * g * env;
  }

  col *= 0.45 + 0.7 * e;
  col = 1.0 - exp(-col * uGlow);

  float gray = dot(col, vec3(0.2126, 0.7152, 0.0722));
  col = max(mix(vec3(gray), col, uSaturation), 0.0);

  float lum = max(max(col.r, col.g), col.b);
  float alpha = clamp(lum, 0.0, 1.0) * uOpacity;

  fragColor = vec4(col * uOpacity, alpha);
}
`;

const GLASS_FRAG = `#version 300 es
precision highp float;

uniform sampler2D uScene;
uniform vec2 uResolution;
uniform float uRadius;
uniform float uRefraction;
uniform float uDispersion;

out vec4 fragColor;

vec2 toUv(vec2 p) {
  return p * (uResolution.y / uResolution) + 0.5;
}

void main() {
  vec2 p = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;
  float d = length(p);
  float r = uRadius;

  float edge = fwidth(d) * 1.5;
  float mask = 1.0 - smoothstep(r - edge, r + edge, d);
  if (mask <= 0.0) {
    fragColor = vec4(0.0);
    return;
  }

  float z = sqrt(max(r * r - d * d, 0.0)) / r;
  float nd = d / r;

  vec2 dir = d > 0.0 ? p / d : vec2(0.0);
  float lens = smoothstep(0.85, 1.0, nd) * pow(nd, 6.0);
  vec2 offset = -dir * lens * uRefraction * 0.15;
  vec2 disp = -dir * lens * uDispersion * 0.012;

  vec3 light;
  light.r = texture(uScene, toUv(p + offset - disp)).r;
  light.g = texture(uScene, toUv(p + offset)).g;
  light.b = texture(uScene, toUv(p + offset + disp)).b;

  float fres = pow(1.0 - z, 3.0);
  vec3 rim = vec3(1.0) * fres * 0.18;

  vec2 lightDir = normalize(vec2(-0.55, 0.6));
  float spec = pow(max(dot(p / max(r, 1e-4), lightDir), 0.0), 6.0);
  spec *= smoothstep(r, r * 0.55, d);

  vec3 emissive = light + rim + vec3(spec) * 0.4;
  float emissiveA = clamp(max(max(emissive.r, emissive.g), emissive.b), 0.0, 1.0);
  float bodyA = 0.05 + fres * 0.05;
  float outA = emissiveA + bodyA * (1.0 - emissiveA);
  vec3 outRGB = emissive;

  outRGB *= mask;
  outA *= mask;

  fragColor = vec4(outRGB, outA);
}
`;

function buildPalette(colors) {
  const filled = colors && colors.length ? colors : ["#ffffff"];
  const padded = [];
  for (let i = 0; i < MAX_COLORS; i += 1) {
    const hex = filled[i] ?? filled[filled.length - 1];
    const c = new Color(hex);
    padded.push([c.r, c.g, c.b]);
  }
  return padded;
}

const DEFAULT_PROPS = {
  colors: ["#6D28D9", "#A855F7", "#C084FC"],
  count: 3,
  speed: 0.5,
  amplitude: 1,
  waviness: 1,
  thickness: 0.7,
  glow: 2.6,
  taper: 3,
  spread: 1,
  hueShift: 0,
  intensity: 0.6,
  saturation: 1.5,
  opacity: 1,
  scale: 1.5,
  glass: false,
  refraction: 1,
  dispersion: 1,
  glassSize: 1,
};

/**
 * Vanilla port of React Bits <Strands /> for the JARVIS cockpit.
 * Returns a controller with setProps / state / quality / dispose controls.
 */
export function createStrands(mount, initialProps = {}) {
  if (!mount) return null;

  const props = { ...DEFAULT_PROPS, ...initialProps };
  const container = document.createElement("div");
  container.className = "strands-container";
  container.setAttribute("aria-hidden", "true");
  mount.appendChild(container);

  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let disposed = false;
  let active = true;
  let animateId = 0;
  let lastFrame = -Infinity;
  let visualState = "idle";
  let voiceEnergy = 0;
  let targetVoiceEnergy = 0;
  let graphicsQuality = "excellent";
  try {
    graphicsQuality = localStorage.getItem("jarvis-graphics-quality") || "excellent";
  } catch {
    // The excellent profile remains the safe local default.
  }
  const qualityProfiles = {
    excellent: { activeFps: 45, idleFps: 24, pixelRatio: 1.25 },
    medium: { activeFps: 30, idleFps: 18, pixelRatio: 1 },
    low: { activeFps: 20, idleFps: 10, pixelRatio: 0.75 },
  };
  if (!qualityProfiles[graphicsQuality]) graphicsQuality = "excellent";
  const activeStates = new Set(["listening", "thinking", "planning", "research", "forge", "speaking", "preview", "memory", "local"]);

  const renderer = new Renderer({
    alpha: true,
    premultipliedAlpha: true,
    antialias: true,
    dpr: Math.min(window.devicePixelRatio || 1, qualityProfiles[graphicsQuality].pixelRatio),
  });
  const gl = renderer.gl;
  gl.clearColor(0, 0, 0, 0);
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  gl.canvas.style.backgroundColor = "transparent";

  const geometry = new Triangle(gl);
  if (geometry.attributes.uv) delete geometry.attributes.uv;

  const program = new Program(gl, {
    vertex: VERT,
    fragment: FRAG,
    uniforms: {
      uTime: { value: 0 },
      uResolution: { value: [1, 1] },
      uColors: { value: buildPalette(props.colors) },
      uColorCount: { value: Math.min(props.colors.length, MAX_COLORS) },
      uStrandCount: { value: Math.min(props.count, MAX_STRANDS) },
      uSpeed: { value: props.speed },
      uAmplitude: { value: props.amplitude },
      uWaviness: { value: props.waviness },
      uThickness: { value: props.thickness },
      uGlow: { value: props.glow },
      uTaper: { value: props.taper },
      uSpread: { value: props.spread },
      uHueShift: { value: props.hueShift },
      uIntensity: { value: props.intensity },
      uOpacity: { value: props.opacity },
      uScale: { value: props.scale },
      uSaturation: { value: props.saturation },
    },
  });

  const mesh = new Mesh(gl, { geometry, program });
  const renderTarget = new RenderTarget(gl, { width: 1, height: 1 });
  const glassProgram = new Program(gl, {
    vertex: VERT,
    fragment: GLASS_FRAG,
    uniforms: {
      uScene: { value: renderTarget.texture },
      uResolution: { value: [1, 1] },
      uRadius: { value: 0.46 * props.glassSize },
      uRefraction: { value: props.refraction },
      uDispersion: { value: props.dispersion },
    },
  });
  const glassMesh = new Mesh(gl, { geometry, program: glassProgram });
  container.appendChild(gl.canvas);

  function resize() {
    if (disposed || !container) return;
    const width = Math.max(container.offsetWidth, 1);
    const height = Math.max(container.offsetHeight, 1);
    renderer.dpr = Math.min(window.devicePixelRatio || 1, qualityProfiles[graphicsQuality].pixelRatio);
    renderer.setSize(width, height);
    const renderWidth = gl.canvas.width;
    const renderHeight = gl.canvas.height;
    program.uniforms.uResolution.value = [renderWidth, renderHeight];
    renderTarget.setSize(renderWidth, renderHeight);
    glassProgram.uniforms.uResolution.value = [renderWidth, renderHeight];
  }

  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(container);
  resize();

  function update(t) {
    if (disposed) return;
    animateId = requestAnimationFrame(update);
    if (!active || document.hidden || !document.hasFocus()) return;
    const profile = qualityProfiles[graphicsQuality];
    const targetFps = activeStates.has(visualState) ? profile.activeFps : profile.idleFps;
    if (t - lastFrame < 1000 / targetFps) return;
    lastFrame = t;
    const current = props;
    voiceEnergy += (targetVoiceEnergy - voiceEnergy) * 0.24;
    if (visualState !== "speaking" && visualState !== "listening") targetVoiceEnergy *= 0.72;
    const voiceBoost = reducedMotion || visualState !== "speaking" ? 0 : voiceEnergy;
    program.uniforms.uTime.value = reducedMotion ? 0 : t * 0.001;
    program.uniforms.uColors.value = buildPalette(current.colors);
    program.uniforms.uColorCount.value = Math.min(current.colors.length, MAX_COLORS);
    program.uniforms.uStrandCount.value = Math.min(Math.max(Math.round(current.count), 1), MAX_STRANDS);
    program.uniforms.uSpeed.value = current.speed * (1 + voiceBoost * 0.72);
    program.uniforms.uAmplitude.value = current.amplitude * (1 + voiceBoost * 0.38);
    program.uniforms.uWaviness.value = current.waviness;
    program.uniforms.uThickness.value = current.thickness * (1 + voiceBoost * 0.3);
    program.uniforms.uGlow.value = current.glow * (1 + voiceBoost * 0.48);
    program.uniforms.uTaper.value = current.taper;
    program.uniforms.uSpread.value = current.spread;
    program.uniforms.uHueShift.value = current.hueShift;
    program.uniforms.uIntensity.value = Math.min(1.2, current.intensity * (1 + voiceBoost * 0.42));
    program.uniforms.uOpacity.value = current.opacity;
    program.uniforms.uScale.value = current.scale;
    program.uniforms.uSaturation.value = current.saturation;

    if (current.glass) {
      renderer.render({ scene: mesh, target: renderTarget });
      glassProgram.uniforms.uScene.value = renderTarget.texture;
      glassProgram.uniforms.uRefraction.value = current.refraction;
      glassProgram.uniforms.uDispersion.value = current.dispersion;
      glassProgram.uniforms.uRadius.value = 0.46 * current.glassSize;
      renderer.render({ scene: glassMesh });
    } else {
      renderer.render({ scene: mesh });
    }
  }

  animateId = requestAnimationFrame(update);

  function onState(event) {
    visualState = event.detail?.state || "idle";
  }

  function onQuality(event) {
    const requested = event.detail?.quality;
    if (!qualityProfiles[requested]) return;
    graphicsQuality = requested;
    lastFrame = -Infinity;
    resize();
  }

  function onVoiceLevel(event) {
    const level = Number(event.detail?.level);
    if (!Number.isFinite(level)) return;
    targetVoiceEnergy = Math.max(0, Math.min(1, level));
  }

  window.addEventListener("jarvis-state", onState);
  window.addEventListener("jarvis-graphics-quality", onQuality);
  window.addEventListener("jarvis-voice-level", onVoiceLevel);
  visualState = document.getElementById("stage")?.dataset?.state || "idle";

  return {
    setProps(next) {
      Object.assign(props, next || {});
    },
    setState(state) {
      visualState = state || "idle";
    },
    setVoiceEnergy(level) {
      targetVoiceEnergy = Math.max(0, Math.min(1, Number(level) || 0));
    },
    setActive(value) {
      active = Boolean(value);
      container.hidden = !active;
      if (active) resize();
    },
    resize,
    dispose() {
      if (disposed) return;
      disposed = true;
      cancelAnimationFrame(animateId);
      resizeObserver.disconnect();
      window.removeEventListener("jarvis-state", onState);
      window.removeEventListener("jarvis-graphics-quality", onQuality);
      window.removeEventListener("jarvis-voice-level", onVoiceLevel);
      if (container.contains(gl.canvas)) container.removeChild(gl.canvas);
      container.remove();
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    },
  };
}

export default createStrands;
