import { Renderer, Program, Mesh, Color, Triangle } from "ogl";

const VERT = `#version 300 es
in vec2 position;
void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const FRAG = `#version 300 es
precision highp float;

uniform float uTime;
uniform float uAmplitude;
uniform vec3 uColorStops[3];
uniform vec2 uResolution;
uniform float uBlend;

out vec4 fragColor;

vec3 permute(vec3 x) {
  return mod(((x * 34.0) + 1.0) * x, 289.0);
}

float snoise(vec2 v) {
  const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
  vec2 i = floor(v + dot(v, C.yy));
  vec2 x0 = v - i + dot(i, C.xx);
  vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;
  i = mod(i, 289.0);
  vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
  vec3 m = max(0.5 - vec3(dot(x0, x0), dot(x12.xy, x12.xy), dot(x12.zw, x12.zw)), 0.0);
  m = m * m;
  m = m * m;
  vec3 x = 2.0 * fract(p * C.www) - 1.0;
  vec3 h = abs(x) - 0.5;
  vec3 ox = floor(x + 0.5);
  vec3 a0 = x - ox;
  m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);
  vec3 g;
  g.x = a0.x * x0.x + h.x * x0.y;
  g.yz = a0.yz * x12.xz + h.yz * x12.yw;
  return 130.0 * dot(m, g);
}

struct ColorStop {
  vec3 color;
  float position;
};

#define COLOR_RAMP(colors, factor, finalColor) { \
  int index = 0; \
  for (int i = 0; i < 2; i++) { \
    ColorStop currentColor = colors[i]; \
    bool isInBetween = currentColor.position <= factor; \
    index = int(mix(float(index), float(i), float(isInBetween))); \
  } \
  ColorStop currentColor = colors[index]; \
  ColorStop nextColor = colors[index + 1]; \
  float range = nextColor.position - currentColor.position; \
  float lerpFactor = (factor - currentColor.position) / range; \
  finalColor = mix(currentColor.color, nextColor.color, lerpFactor); \
}

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution;
  ColorStop colors[3];
  colors[0] = ColorStop(uColorStops[0], 0.0);
  colors[1] = ColorStop(uColorStops[1], 0.5);
  colors[2] = ColorStop(uColorStops[2], 1.0);
  vec3 rampColor;
  COLOR_RAMP(colors, uv.x, rampColor);
  float height = snoise(vec2(uv.x * 2.0 + uTime * 0.1, uTime * 0.25)) * 0.5 * uAmplitude;
  height = exp(height);
  height = uv.y * 2.0 - height + 0.2;
  float intensity = 0.6 * height;
  float midPoint = 0.20;
  float auroraAlpha = smoothstep(midPoint - uBlend * 0.5, midPoint + uBlend * 0.5, intensity);
  vec3 auroraColor = intensity * rampColor;
  fragColor = vec4(auroraColor * auroraAlpha, auroraAlpha);
}
`;

const DEFAULT_PROPS = {
  colorStops: ["#2E1065", "#7C3AED", "#A855F7"],
  blend: 0.5,
  amplitude: 1,
  speed: 0.5,
};

function buildColors(stops) {
  return stops.map((hex) => {
    const color = new Color(hex);
    return [color.r, color.g, color.b];
  });
}

export function createAurora(mount, initialProps = {}) {
  if (!mount) return null;
  const props = { ...DEFAULT_PROPS, ...initialProps };
  const container = document.createElement("div");
  container.className = "aurora-container";
  container.setAttribute("aria-hidden", "true");
  mount.appendChild(container);

  let disposed = false;
  let animationFrameId = 0;
  let lastFrame = -Infinity;
  let visualState = "idle";
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
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

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
      uAmplitude: { value: props.amplitude },
      uColorStops: { value: buildColors(props.colorStops) },
      uResolution: { value: [1, 1] },
      uBlend: { value: props.blend },
    },
  });
  const mesh = new Mesh(gl, { geometry, program });
  container.appendChild(gl.canvas);

  function resize() {
    if (disposed) return;
    const width = Math.max(container.offsetWidth, 1);
    const height = Math.max(container.offsetHeight, 1);
    renderer.dpr = Math.min(window.devicePixelRatio || 1, qualityProfiles[graphicsQuality].pixelRatio);
    renderer.setSize(width, height);
    program.uniforms.uResolution.value = [gl.canvas.width, gl.canvas.height];
  }

  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(container);
  resize();

  function render(time) {
    if (disposed) return;
    animationFrameId = requestAnimationFrame(render);
    if (document.hidden || !document.hasFocus()) return;
    const profile = qualityProfiles[graphicsQuality];
    const targetFps = activeStates.has(visualState) ? profile.activeFps : profile.idleFps;
    if (time - lastFrame < 1000 / targetFps) return;
    lastFrame = time;
    program.uniforms.uTime.value = reducedMotion ? 0 : time * 0.001 * props.speed;
    program.uniforms.uAmplitude.value = props.amplitude;
    program.uniforms.uBlend.value = props.blend;
    program.uniforms.uColorStops.value = buildColors(props.colorStops);
    renderer.render({ scene: mesh });
  }
  animationFrameId = requestAnimationFrame(render);

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

  window.addEventListener("jarvis-state", onState);
  window.addEventListener("jarvis-graphics-quality", onQuality);
  visualState = document.getElementById("stage")?.dataset?.state || "idle";

  return {
    setProps(next) {
      Object.assign(props, next || {});
    },
    resize,
    dispose() {
      if (disposed) return;
      disposed = true;
      cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();
      window.removeEventListener("jarvis-state", onState);
      window.removeEventListener("jarvis-graphics-quality", onQuality);
      if (container.contains(gl.canvas)) container.removeChild(gl.canvas);
      container.remove();
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    },
  };
}

export default createAurora;
