import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const mount = document.getElementById("avatar3d");
const stage = document.getElementById("stage");
const presenceValue = document.getElementById("presenceValue");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const compactViewport = matchMedia("(max-width: 900px)").matches;
const constrainedHardware = (navigator.deviceMemory && navigator.deviceMemory <= 4)
  || (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4);
const ACTIVE_TARGET_FPS = compactViewport || constrainedHardware ? 24 : 45;
const IDLE_TARGET_FPS = compactViewport || constrainedHardware ? 10 : 18;
const BACKGROUND_TARGET_FPS = 1;
const EFFECT_TARGET_FPS = 10;
const BASE_FRAME_INTERVAL_MS = 1000 / ACTIVE_TARGET_FPS;

const COLORS = {
  idle: 0x46e6ff,
  listening: 0x22d3ee,
  thinking: 0x67e8f9,
  research: 0x38bdf8,
  planning: 0x38bdf8,
  forge: 0xf5b957,
  speaking: 0x67e8f9,
  response: 0x67e8f9,
  memory: 0x5eead4,
  local: 0xf5b957,
  success: 0x6ee7b7,
  error: 0xfb7185,
  offline: 0x475569,
};

let visualState = stage.dataset.state || "idle";
function visualModeForState(state) {
  if (["thinking", "planning", "research"].includes(state)) return "core";
  if (["forge", "local"].includes(state)) return "forge";
  if (state === "memory") return "memory";
  return "avatar";
}

function applyVisualMode(state) {
  visualState = state || "idle";
  stage.dataset.visualMode = visualModeForState(visualState);
}

window.addEventListener("jarvis-state", (event) => {
  applyVisualMode(event.detail?.state);
});
applyVisualMode(visualState);

function makeEffectCanvas() {
  const canvas = document.createElement("canvas");
  canvas.className = "effect-canvas";
  canvas.style.position = "absolute";
  canvas.style.inset = "0";
  canvas.style.zIndex = "0";
  canvas.style.pointerEvents = "none";
  canvas.dataset.visualLayer = "effects";
  mount.appendChild(canvas);
  return canvas;
}

async function loadMemoryLabels() {
  try {
    let pairingValue = "";
    try {
      pairingValue = localStorage.getItem("jarvis-owner-token-v1") || "";
    } catch {
      // O visual segue com rótulos locais quando o storage está indisponível.
    }
    const response = await fetch("/memory-tree", {
      headers: pairingValue ? { "X-Jarvis-Owner-Token": pairingValue } : {},
    });
    if (!response.ok) throw new Error("memory tree unavailable");
    const data = await response.json();
    return (data.nodes || []).slice(0, 28).map((node) => String(node.label || node.name || "MEMORY").slice(0, 18).toUpperCase());
  } catch {
    return ["DECISIONS", "LEARNINGS", "PROJECTS", "CONTEXT", "TASKS", "ACTIONS", "THEO"];
  }
}

function drawMemory(ctx, width, height, time, labels, opacity = 1) {
  const centerX = width * (compactViewport ? 0.62 : 0.66);
  const centerY = height * 0.43;
  const span = Math.min(width, height);
  const visibleLabels = labels.slice(0, 16);
  ctx.save();
  ctx.globalAlpha = Math.max(0, Math.min(1, opacity));
  const aura = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, span * 0.42);
  aura.addColorStop(0, "rgba(94,234,212,.14)");
  aura.addColorStop(0.5, "rgba(56,189,248,.055)");
  aura.addColorStop(1, "rgba(14,116,144,0)");
  ctx.fillStyle = aura;
  ctx.fillRect(0, 0, width, height);

  ctx.lineWidth = 1;
  for (let ring = 1; ring <= 4; ring += 1) {
    ctx.strokeStyle = `rgba(94,234,212,${0.16 - ring * 0.022})`;
    ctx.setLineDash(ring % 2 ? [3, 8] : []);
    ctx.beginPath();
    ctx.ellipse(centerX, centerY, span * ring * 0.082, span * ring * 0.061, time * 0.025 * (ring % 2 ? 1 : -1), 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.setLineDash([]);

  ctx.font = "8px ui-monospace, Menlo, monospace";
  visibleLabels.forEach((label, index) => {
    const lane = 1 + index % 4;
    const angle = index * 2.399963 + time * (index % 2 ? -0.018 : 0.018);
    const radius = span * (0.075 + lane * 0.052);
    const x = centerX + Math.cos(angle) * radius;
    const y = centerY + Math.sin(angle) * radius * 0.76;
    ctx.strokeStyle = "rgba(94,234,212,.12)";
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.fillStyle = index % 3 ? "rgba(94,234,212,.9)" : "rgba(125,211,252,.95)";
    ctx.shadowColor = "#5eead4";
    ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.arc(x, y, 2 + (index % 3) * 0.7, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    if (index < 10) {
      ctx.fillStyle = "rgba(204,251,241,.66)";
      ctx.textAlign = x < centerX ? "right" : "left";
      ctx.fillText(label, x + (x < centerX ? -7 : 7), y + 3);
    }
  });

  const writeProgress = (time * 0.24) % 1;
  const writeX = centerX - span * (0.38 - writeProgress * 0.38);
  const writeY = centerY + Math.sin(writeProgress * Math.PI) * -span * 0.055;
  ctx.strokeStyle = "rgba(125,211,252,.26)";
  ctx.beginPath();
  ctx.moveTo(centerX - span * 0.38, centerY);
  ctx.quadraticCurveTo(centerX - span * 0.18, centerY - span * 0.11, centerX, centerY);
  ctx.stroke();
  ctx.fillStyle = `rgba(207,250,254,${0.25 + writeProgress * 0.65})`;
  ctx.shadowColor = "#67e8f9";
  ctx.shadowBlur = 18;
  ctx.fillRect(writeX - 7, writeY - 4, 14, 8);
  ctx.shadowBlur = 0;

  ctx.fillStyle = "rgba(94,234,212,.95)";
  ctx.shadowColor = "#5eead4";
  ctx.shadowBlur = 28;
  ctx.beginPath();
  ctx.arc(centerX, centerY, 7 + Math.sin(time * 2) * 1.5, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.fillStyle = "rgba(220,252,248,.92)";
  ctx.textAlign = "center";
  ctx.font = "700 18px ui-sans-serif, system-ui";
  ctx.fillText(String(labels.length), centerX, centerY - 18);
  ctx.font = "8px ui-monospace, Menlo, monospace";
  ctx.fillText("MEMÓRIA · REGISTRO CONFIRMADO", centerX, centerY + 26);
  ctx.textAlign = "right";
  ctx.fillStyle = "rgba(153,246,228,.45)";
  ctx.fillText("CONTEXTO · ÍNDICE PERSISTENTE", width - 24, height - 28);
  ctx.restore();
}

const FORGE_COMPONENTS = Array.from({ length: 20 }, (_, index) => ({
  angle: index * 2.399963,
  radius: 0.24 + (index % 5) * 0.042,
  phase: index * 1.731,
  size: 5 + (index % 4) * 2,
}));

function drawForge(ctx, width, height, time, opacity = 1) {
  const centerX = width * (compactViewport ? 0.62 : 0.66);
  const centerY = height * 0.43;
  const span = Math.min(width, height);
  const assembly = 0.5 + 0.5 * Math.sin(time * 0.92);
  ctx.save();
  ctx.globalAlpha = Math.max(0, Math.min(1, opacity));
  const aura = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, span * 0.42);
  aura.addColorStop(0, `rgba(245,185,87,${0.13 + assembly * 0.08})`);
  aura.addColorStop(0.48, "rgba(34,211,238,.045)");
  aura.addColorStop(1, "rgba(8,145,178,0)");
  ctx.fillStyle = aura;
  ctx.fillRect(0, 0, width, height);

  for (let ring = 1; ring <= 3; ring += 1) {
    const radius = ring * span * 0.09;
    ctx.strokeStyle = ring === 2 ? "rgba(245,185,87,.2)" : "rgba(103,232,249,.12)";
    ctx.lineWidth = ring === 2 ? 1.4 : 1;
    ctx.beginPath();
    for (let side = 0; side <= 8; side += 1) {
      const angle = side / 8 * Math.PI * 2 + time * 0.055 * (ring % 2 ? 1 : -1);
      const x = centerX + Math.cos(angle) * radius;
      const y = centerY + Math.sin(angle) * radius * 0.78;
      if (side) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    }
    ctx.closePath();
    ctx.stroke();
  }

  FORGE_COMPONENTS.forEach((component, index) => {
    const distance = component.radius * span * (0.58 + 0.7 * (1 - assembly));
    const angle = component.angle + time * (index % 2 ? -0.08 : 0.08);
    const x = centerX + Math.cos(angle) * distance;
    const y = centerY + Math.sin(angle) * distance * 0.78;
    ctx.strokeStyle = index % 3 ? "rgba(103,232,249,.11)" : "rgba(245,185,87,.18)";
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(component.phase + time * (0.18 + index % 3 * 0.04));
    ctx.strokeStyle = index % 3 ? `rgba(165,243,252,${0.34 + assembly * 0.38})` : `rgba(253,230,138,${0.4 + assembly * 0.4})`;
    ctx.fillStyle = index % 3 ? "rgba(8,145,178,.12)" : "rgba(245,158,11,.13)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(-component.size, -component.size * 0.55, component.size * 2, component.size * 1.1, 2);
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  });

  const coreRadius = 12 + assembly * 14;
  const glow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, coreRadius * 2.4);
  glow.addColorStop(0, `rgba(255,251,235,${0.7 + assembly * 0.24})`);
  glow.addColorStop(0.42, `rgba(245,185,87,${0.24 + assembly * 0.18})`);
  glow.addColorStop(1, "rgba(34,211,238,0)");
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(centerX, centerY, coreRadius * 2.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "rgba(255,255,255,.9)";
  ctx.beginPath();
  ctx.arc(centerX, centerY, coreRadius * 0.35, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "rgba(103,232,249,.5)";
  ctx.strokeRect(centerX - span * 0.105, centerY - span * 0.06, span * 0.21, span * 0.12);
  ctx.fillStyle = "rgba(254,243,199,.75)";
  ctx.font = "700 9px ui-monospace, Menlo, monospace";
  ctx.textAlign = "center";
  ctx.fillText("FORJA · CONSTRUÇÃO EM CURSO", centerX, centerY + span * 0.28);
  ["ANALISAR", "MONTAR", "TESTAR", "ENTREGAR"].forEach((label, index) => {
    const angle = -Math.PI * 0.8 + index * Math.PI * 0.53;
    const x = centerX + Math.cos(angle) * span * 0.27;
    const y = centerY + Math.sin(angle) * span * 0.25;
    ctx.fillStyle = index <= Math.floor(assembly * 4) ? "rgba(254,243,199,.72)" : "rgba(165,243,252,.38)";
    ctx.fillText(label, x, y);
  });
  ctx.restore();
}

function makeCoreEntity(scene) {
  const group = new THREE.Group();
  group.position.set(0.94, 0.02, -1.05);
  group.scale.setScalar(0.58);
  group.visible = false;
  scene.add(group);

  const obsidianMaterial = new THREE.MeshPhysicalMaterial({
    color: 0x071b22,
    roughness: 0.16,
    transmission: 0.34,
    thickness: 1.2,
    ior: 1.46,
    clearcoat: 0.9,
    emissive: 0x063746,
    emissiveIntensity: 0.32,
    transparent: true,
    opacity: 0,
    flatShading: true,
  });
  const coreGeometry = new THREE.IcosahedronGeometry(0.84, 1);
  const core = new THREE.Mesh(coreGeometry, obsidianMaterial);
  group.add(core);

  const soulMaterial = new THREE.MeshBasicMaterial({
    color: 0x67e8f9,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const soul = new THREE.Mesh(new THREE.IcosahedronGeometry(0.38, 0), soulMaterial);
  group.add(soul);

  const wireMaterial = new THREE.MeshBasicMaterial({
    color: 0x38bdf8,
    wireframe: true,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const containment = new THREE.Mesh(new THREE.IcosahedronGeometry(1.28, 1), wireMaterial);
  group.add(containment);

  const shardMaterial = new THREE.MeshBasicMaterial({
    color: 0x67e8f9,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const shardCount = reducedMotion ? 6 : 10;
  const shards = Array.from({ length: shardCount }, (_, index) => {
    const shard = new THREE.Mesh(new THREE.TetrahedronGeometry(0.1 + index % 3 * 0.025), shardMaterial);
    const y = 1 - index / Math.max(1, shardCount - 1) * 2;
    const radius = Math.sqrt(Math.max(0, 1 - y * y));
    const angle = index * 2.399963;
    shard.userData.direction = new THREE.Vector3(Math.cos(angle) * radius, y * 0.76, Math.sin(angle) * radius);
    group.add(shard);
    return shard;
  });

  let alpha = 0;
  function update(time, visibility) {
    alpha += (Math.max(0, Math.min(1, visibility)) - alpha) * 0.11;
    group.visible = alpha > 0.01;
    if (!group.visible) return;
    const pulse = 0.5 + 0.5 * Math.sin(time * 2.2);
    obsidianMaterial.opacity = alpha * 0.58;
    obsidianMaterial.emissiveIntensity = alpha * (0.28 + pulse * 0.2);
    soulMaterial.opacity = alpha * (0.44 + pulse * 0.28);
    wireMaterial.opacity = alpha * (0.08 + pulse * 0.045);
    shardMaterial.opacity = alpha * (0.2 + pulse * 0.16);
    core.rotation.y += 0.004;
    core.rotation.x += 0.0015;
    soul.rotation.y -= 0.007;
    containment.rotation.y -= 0.0025;
    containment.rotation.z += 0.001;
    shards.forEach((shard, index) => {
      const distance = 1.36 + pulse * 0.12 + index % 4 * 0.045;
      shard.position.copy(shard.userData.direction).multiplyScalar(distance);
      shard.rotation.x += 0.005 + index % 3 * 0.001;
      shard.rotation.y -= 0.004;
    });
    group.rotation.y = Math.sin(time * 0.34) * 0.12;
    group.position.y = 0.02 + Math.sin(time * 0.8) * 0.035;
  }

  return { group, update };
}

function installCyanRemap(material) {
  if (!material || material.userData.jarvisCyanRemap) return;
  material.userData.jarvisCyanRemap = true;
  const previousCompile = material.onBeforeCompile;
  material.onBeforeCompile = (shader, renderer) => {
    if (previousCompile) previousCompile(shader, renderer);
    shader.fragmentShader = shader.fragmentShader.replace(
      "#include <opaque_fragment>",
      `
        float jarvisRedLead = outgoingLight.r - max(outgoingLight.g, outgoingLight.b);
        float jarvisRedMask = smoothstep(0.035, 0.28, jarvisRedLead)
          * smoothstep(0.08, 0.34, outgoingLight.r);
        float jarvisMagentaLead = min(outgoingLight.r, outgoingLight.b) - outgoingLight.g;
        float jarvisMagentaMask = smoothstep(0.02, 0.2, jarvisMagentaLead)
          * smoothstep(0.1, 0.38, max(outgoingLight.r, outgoingLight.b));
        float jarvisAccentMask = max(jarvisRedMask, jarvisMagentaMask);
        float jarvisEnergy = max(outgoingLight.r, max(outgoingLight.g, outgoingLight.b));
        vec3 jarvisCyan = vec3(jarvisEnergy * 0.05, jarvisEnergy * 0.92, jarvisEnergy * 1.28);
        outgoingLight = mix(outgoingLight, jarvisCyan, jarvisAccentMask * 0.96);
        #include <opaque_fragment>
      `,
    );
  };
  material.customProgramCacheKey = () => "jarvis-cyan-remap-v2";
  material.needsUpdate = true;
}

async function start() {
  const renderer = new THREE.WebGLRenderer({
    alpha: true,
    antialias: !compactViewport && !constrainedHardware,
    powerPreference: constrainedHardware ? "low-power" : "high-performance",
    preserveDrawingBuffer: false,
  });
  renderer.domElement.style.position = "absolute";
  renderer.domElement.style.inset = "0";
  renderer.domElement.style.zIndex = "1";
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(compactViewport || constrainedHardware ? 1 : Math.min(window.devicePixelRatio || 1, 1.35));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.16;
  mount.appendChild(renderer.domElement);

  const effectCanvas = makeEffectCanvas();
  const effectContext = effectCanvas.getContext("2d");
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  camera.position.set(0, 0.02, 5.1);

  scene.add(new THREE.AmbientLight(0x163448, 1.08));
  const key = new THREE.DirectionalLight(0x9af4ff, 3.15);
  key.position.set(2.6, 3.4, 4.2);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x60a5fa, 2.35);
  rim.position.set(-3, 1.3, -2);
  scene.add(rim);
  const faceFill = new THREE.PointLight(0xbff9ff, 9.5, 7, 1.7);
  faceFill.position.set(0.15, 0.45, 3.1);
  scene.add(faceFill);
  const lowerFill = new THREE.PointLight(0x22d3ee, 5.2, 6, 2);
  lowerFill.position.set(-1.2, -1.8, 2.4);
  scene.add(lowerFill);
  const coreEntity = makeCoreEntity(scene);

  const root = new THREE.Group();
  scene.add(root);
  const gltf = await new Promise((resolve, reject) => {
    new GLTFLoader().load("/asset/models/jarvis-humanoid.glb?v=20260807-voicecyan1", resolve, undefined, reject);
  });

  const model = gltf.scene || gltf.scenes[0];
  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const scale = 2.42 / (Math.max(size.x, size.y, size.z) || 1);
  model.scale.setScalar(scale);
  model.position.set(-center.x * scale, -center.y * scale - 0.02, -center.z * scale);
  root.add(model);

  const glowMaterials = new Set();
  model.traverse((object) => {
    if (!object.isMesh) return;
    object.frustumCulled = true;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.filter(Boolean).forEach((material) => {
      installCyanRemap(material);
      if ("envMapIntensity" in material) material.envMapIntensity = 1.42;
      if (material.emissive && /glow|emissive/i.test(material.name || "")) {
        material.userData.jarvisBaseEmissive = material.emissive.clone();
        material.userData.jarvisBaseIntensity = material.emissiveIntensity || 1;
        glowMaterials.add(material);
      }
    });
  });
  const mixer = gltf.animations.length ? new THREE.AnimationMixer(model) : null;
  if (mixer && !reducedMotion) mixer.clipAction(gltf.animations[0]).play();
  stage.dataset.modelAsset = "mech-bust";
  stage.dataset.modelAnimations = String(gltf.animations.length);
  stage.dataset.modelAnimationSeconds = gltf.animations[0]?.duration?.toFixed(1) || "0";
  stage.dataset.renderProfile = constrainedHardware ? "adaptive-lite" : "command-deck";

  const particleCount = compactViewport || constrainedHardware ? 24 : 42;
  const particlePositions = new Float32Array(particleCount * 3);
  for (let index = 0; index < particleCount; index += 1) {
    const angle = Math.random() * Math.PI * 2;
    const radius = 1.5 + Math.random() * 1.8;
    particlePositions[index * 3] = Math.cos(angle) * radius;
    particlePositions[index * 3 + 1] = (Math.random() - 0.5) * 3.5;
    particlePositions[index * 3 + 2] = Math.sin(angle) * radius - 0.3;
  }
  const particleGeometry = new THREE.BufferGeometry();
  particleGeometry.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
  const particleMaterial = new THREE.PointsMaterial({ color: COLORS.idle, size: 0.025, transparent: true, opacity: 0.34, blending: THREE.AdditiveBlending, depthWrite: false });
  const particles = new THREE.Points(particleGeometry, particleMaterial);
  scene.add(particles);

  let memoryLabels = ["DECISIONS", "LEARNINGS", "PROJECTS", "CONTEXT", "TASKS", "ACTIONS", "THEO"];
  let memoryLabelsLoaded = false;
  async function refreshMemoryLabels() {
    memoryLabels = await loadMemoryLabels();
    memoryLabelsLoaded = true;
  }
  window.addEventListener("jarvis-memory-refresh", refreshMemoryLabels);
  window.addEventListener("jarvis-state", () => {
    if (visualState === "memory" && !memoryLabelsLoaded) refreshMemoryLabels();
  });
  let pointerX = 0;
  let pointerY = 0;
  let currentX = 0;
  let currentY = 0;
  const currentColor = new THREE.Color(COLORS.idle);
  const targetColor = new THREE.Color(COLORS.idle);

  stage.addEventListener("pointermove", (event) => {
    const rect = stage.getBoundingClientRect();
    pointerX = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointerY = ((event.clientY - rect.top) / rect.height) * 2 - 1;
  }, { passive: true });
  stage.addEventListener("pointerleave", () => {
    pointerX = 0;
    pointerY = 0;
  });

  let canvasWidth = 1;
  let canvasHeight = 1;
  function resize() {
    const rect = mount.getBoundingClientRect();
    canvasWidth = Math.max(rect.width, 1);
    canvasHeight = Math.max(rect.height, 1);
    camera.aspect = canvasWidth / canvasHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(canvasWidth, canvasHeight, false);
    const density = Math.min(window.devicePixelRatio || 1, 1.5);
    effectCanvas.width = Math.round(canvasWidth * density);
    effectCanvas.height = Math.round(canvasHeight * density);
    effectCanvas.style.width = `${canvasWidth}px`;
    effectCanvas.style.height = `${canvasHeight}px`;
    effectContext.setTransform(density, 0, 0, density, 0, 0);
  }
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(mount);
  resize();

  stage.classList.add("model-ready");
  stage.classList.remove("model-error");
  stage.classList.remove("gpu-error");
  presenceValue.textContent = "Mech Bust GLB · animação real · Forja · Memória";

  let previousFrameMs = 0;
  let effectVisible = false;
  let currentScale = 1;
  let sampledFrames = 0;
  let fpsWindowStart = performance.now();
  let frameIntervalMs = BASE_FRAME_INTERVAL_MS;
  let adaptiveMaxFps = ACTIVE_TARGET_FPS;
  let slowFrameWindows = 0;
  let lastVisualMode = "";
  let effectLastFrameMs = 0;
  let windowFocused = document.hasFocus();
  let animationFrameId = 0;
  let animationTimerId = 0;
  let disposed = false;
  let lastRenderTargetFps = 0;
  let lastRenderProfile = "";
  const modeBlend = { core: 0, forge: 0, memory: 0 };

  const activeStates = new Set(["listening", "thinking", "planning", "research", "forge", "speaking", "memory", "local"]);
  function requestedTargetFps() {
    if (!windowFocused) return BACKGROUND_TARGET_FPS;
    return activeStates.has(visualState) ? ACTIVE_TARGET_FPS : IDLE_TARGET_FPS;
  }

  function updateRenderBudget() {
    const requestedFps = requestedTargetFps();
    const targetFps = Math.max(1, Math.min(requestedFps, adaptiveMaxFps));
    frameIntervalMs = 1000 / targetFps;
    const profile = !windowFocused
      ? `background-${targetFps}fps`
      : targetFps < requestedFps
        ? `adaptive-lite-${targetFps}fps`
        : activeStates.has(visualState) ? `active-${targetFps}fps` : `idle-${targetFps}fps`;
    if (lastRenderTargetFps !== targetFps) {
      stage.dataset.renderTargetFps = String(targetFps);
      lastRenderTargetFps = targetFps;
    }
    if (lastRenderProfile !== profile) {
      stage.dataset.renderProfile = profile;
      lastRenderProfile = profile;
    }
  }

  window.addEventListener("focus", () => {
    windowFocused = true;
    updateRenderBudget();
    scheduleRender(0);
  });
  window.addEventListener("blur", () => {
    windowFocused = false;
    updateRenderBudget();
  });
  updateRenderBudget();

  function scheduleRender(delay = frameIntervalMs) {
    if (disposed || reducedMotion) return;
    window.clearTimeout(animationTimerId);
    animationTimerId = window.setTimeout(() => {
      animationFrameId = requestAnimationFrame(render);
    }, Math.max(0, delay));
  }

  function wakeRender() {
    previousFrameMs = 0;
    scheduleRender(0);
  }

  window.addEventListener("jarvis-state", wakeRender);
  document.addEventListener("visibilitychange", wakeRender);

  function render(timeMs) {
    if (disposed) return;
    updateRenderBudget();
    if (document.hidden) {
      previousFrameMs = timeMs;
      scheduleRender(1000);
      return;
    }
    const deltaSeconds = previousFrameMs ? Math.min((timeMs - previousFrameMs) / 1000, 0.1) : 0;
    previousFrameMs = timeMs;
    sampledFrames += 1;
    if (timeMs - fpsWindowStart >= 1000) {
      const measuredFps = Math.round(sampledFrames * 1000 / (timeMs - fpsWindowStart));
      stage.dataset.renderFps = String(measuredFps);
      const renderTelemetry = document.getElementById("sceneRender");
      if (renderTelemetry) renderTelemetry.textContent = `3D ${measuredFps} FPS`;
      const currentTargetFps = 1000 / frameIntervalMs;
      slowFrameWindows = measuredFps < currentTargetFps * 0.72
        ? slowFrameWindows + 1
        : Math.max(0, slowFrameWindows - 1);
      if (slowFrameWindows >= 5) {
        adaptiveMaxFps = Math.min(adaptiveMaxFps, 12);
      } else if (slowFrameWindows >= 2) {
        adaptiveMaxFps = Math.min(adaptiveMaxFps, 18);
      }
      sampledFrames = 0;
      fpsWindowStart = timeMs;
    }
    const time = timeMs * 0.001;
    const visualMode = visualModeForState(visualState);
    if (visualMode !== lastVisualMode) {
      stage.dataset.visualMode = visualMode;
      lastVisualMode = visualMode;
    }
    const blendEase = Math.min(1, Math.max(0.08, deltaSeconds * 4.2));
    Object.keys(modeBlend).forEach((mode) => {
      const target = visualMode === mode ? 1 : 0;
      modeBlend[mode] += (target - modeBlend[mode]) * blendEase;
    });
    const activeColor = COLORS[visualState] || COLORS.idle;
    const isWorking = modeBlend.forge > 0.08;
    targetColor.setHex(activeColor);
    currentColor.lerp(targetColor, 0.065);
    particleMaterial.color.copy(currentColor);
    glowMaterials.forEach((material) => {
      material.emissive.copy(material.userData.jarvisBaseEmissive).lerp(currentColor, 0.28);
      material.emissiveIntensity = material.userData.jarvisBaseIntensity * (isWorking ? 1.28 : visualState === "speaking" ? 1.18 : 1);
    });
    if (mixer) {
      mixer.timeScale = isWorking ? 1.18 : visualState === "speaking" ? 1.05 : 0.72;
      mixer.update(deltaSeconds);
    }

    currentX += (pointerX * 0.25 - currentX) * 0.055;
    currentY += (pointerY * 0.12 - currentY) * 0.055;
    const cameraTargetX = modeBlend.memory * 0.08 + modeBlend.forge * 0.05;
    const cameraTargetZ = 5.02 + modeBlend.memory * 0.18 + modeBlend.forge * 0.12 + modeBlend.core * 0.08;
    camera.position.x += (cameraTargetX - camera.position.x) * 0.035;
    camera.position.z += (cameraTargetZ - camera.position.z) * 0.035;
    camera.lookAt(0, -0.01, 0);
    const targetPositionX = -modeBlend.memory * 0.72 - modeBlend.forge * 0.62 - modeBlend.core * 0.38;
    root.position.x += (targetPositionX - root.position.x) * 0.045;
    root.position.y = Math.sin(time * 0.9) * 0.035;
    root.rotation.y = currentX + Math.sin(time * 0.38) * 0.035 - Math.max(modeBlend.memory, modeBlend.forge, modeBlend.core) * 0.08;
    root.rotation.x = currentY + Math.sin(time * 0.47) * 0.012;
    const speakingPulse = visualState === "speaking" ? (Math.sin(time * 10) + 1) * 0.12 : 0;
    const targetScale = 1 - modeBlend.memory * 0.07 - modeBlend.forge * 0.045 - modeBlend.core * 0.025 + speakingPulse * 0.035;
    currentScale += (targetScale - currentScale) * 0.055;
    root.scale.setScalar(currentScale);
    particleMaterial.opacity = isWorking ? 0.32 : 0.2 + speakingPulse * 0.35;
    particles.rotation.y += deltaSeconds * (isWorking ? 0.072 : 0.036);
    coreEntity.update(time, modeBlend.core);

    const effectFrameDue = timeMs - effectLastFrameMs >= 1000 / EFFECT_TARGET_FPS;
    const effectBlend = Math.max(modeBlend.memory, modeBlend.forge);
    if (effectBlend > 0.01 && effectFrameDue) {
      effectContext.clearRect(0, 0, canvasWidth, canvasHeight);
      if (modeBlend.memory > 0.01) drawMemory(effectContext, canvasWidth, canvasHeight, time, memoryLabels, modeBlend.memory);
      if (modeBlend.forge > 0.01) drawForge(effectContext, canvasWidth, canvasHeight, time, modeBlend.forge);
      effectVisible = true;
      effectLastFrameMs = timeMs;
    } else if (effectVisible && effectBlend <= 0.01) {
      effectContext.clearRect(0, 0, canvasWidth, canvasHeight);
      effectVisible = false;
    }

    renderer.render(scene, camera);
    scheduleRender(frameIntervalMs);
  }

  if (reducedMotion) renderer.render(scene, camera);
  else scheduleRender(0);

  window.addEventListener("pagehide", (event) => {
    if (event.persisted) return;
    disposed = true;
    window.clearTimeout(animationTimerId);
    cancelAnimationFrame(animationFrameId);
    window.removeEventListener("jarvis-state", wakeRender);
    document.removeEventListener("visibilitychange", wakeRender);
    resizeObserver.disconnect();
    mixer?.stopAllAction();
    const disposedTextures = new Set();
    model.traverse((object) => {
      if (!object.isMesh) return;
      object.geometry?.dispose();
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.filter(Boolean).forEach((material) => {
        Object.values(material).forEach((value) => {
          if (value?.isTexture && !disposedTextures.has(value)) {
            disposedTextures.add(value);
            value.dispose();
          }
        });
        material.dispose();
      });
    });
    particleGeometry.dispose();
    particleMaterial.dispose();
    renderer.dispose();
    renderer.forceContextLoss();
  }, { once: true });
}

start().catch((error) => {
  stage.classList.remove("model-ready");
  stage.classList.add("model-error");
  const reason = String(error?.message || error || "falha desconhecida").slice(0, 180);
  const gpuFailure = /webgl|context/i.test(reason);
  stage.dataset.modelErrorReason = reason;
  stage.classList.toggle("gpu-error", gpuFailure);
  presenceValue.textContent = gpuFailure ? "GPU 3D desativada · reinicie o Chrome" : "modelo 3D indisponível";
  console.warn("JARVIS 3D model unavailable", error);
});
