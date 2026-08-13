import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const mount = document.getElementById("avatar3d");
const stage = document.getElementById("stage");
const presenceValue = document.getElementById("presenceValue");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const compactViewport = matchMedia("(max-width: 900px)").matches;
const constrainedHardware = (navigator.deviceMemory && navigator.deviceMemory <= 4)
  || (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4);
const ACTIVE_TARGET_FPS = compactViewport || constrainedHardware ? 16 : 24;
const IDLE_TARGET_FPS = 2;
const BACKGROUND_TARGET_FPS = 1;
const EFFECT_TARGET_FPS = 10;
const BASE_FRAME_INTERVAL_MS = 1000 / ACTIVE_TARGET_FPS;

const COLORS = {
  idle: 0xa78bfa,
  listening: 0x8b5cf6,
  thinking: 0xc4b5fd,
  research: 0xa78bfa,
  planning: 0xa78bfa,
  forge: 0xd8b4fe,
  speaking: 0xc4b5fd,
  response: 0xc4b5fd,
  memory: 0xc084fc,
  preview: 0xc4b5fd,
  local: 0xd8b4fe,
  success: 0xc4b5fd,
  error: 0xfb7185,
  offline: 0x475569,
};

let visualState = stage.dataset.state || "idle";
function visualModeForState(state) {
  if (["thinking", "planning", "research"].includes(state)) return "core";
  if (["forge", "local"].includes(state)) return "forge";
  if (state === "memory") return "memory";
  if (["voice", "speaking"].includes(state)) return "voice";
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
  const centerX = width * 0.5;
  const centerY = height * 0.43;
  const span = Math.min(width, height);
  const visibleLabels = labels.slice(0, 16);
  ctx.save();
  ctx.globalAlpha = Math.max(0, Math.min(1, opacity));
  const aura = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, span * 0.42);
  aura.addColorStop(0, "rgba(192,132,252,.14)");
  aura.addColorStop(0.5, "rgba(167,139,250,.055)");
  aura.addColorStop(1, "rgba(91,33,182,0)");
  ctx.fillStyle = aura;
  ctx.fillRect(0, 0, width, height);

  ctx.lineWidth = 1;
  for (let ring = 1; ring <= 4; ring += 1) {
    ctx.strokeStyle = `rgba(192,132,252,${0.16 - ring * 0.022})`;
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
    ctx.strokeStyle = "rgba(192,132,252,.12)";
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.fillStyle = index % 3 ? "rgba(192,132,252,.9)" : "rgba(196,181,253,.95)";
    ctx.shadowColor = "#c084fc";
    ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.arc(x, y, 2 + (index % 3) * 0.7, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    if (index < 10) {
      ctx.fillStyle = "rgba(237,233,254,.66)";
      ctx.textAlign = x < centerX ? "right" : "left";
      ctx.fillText(label, x + (x < centerX ? -7 : 7), y + 3);
    }
  });

  const writeProgress = (time * 0.24) % 1;
  const writeX = centerX - span * (0.38 - writeProgress * 0.38);
  const writeY = centerY + Math.sin(writeProgress * Math.PI) * -span * 0.055;
  ctx.strokeStyle = "rgba(196,181,253,.26)";
  ctx.beginPath();
  ctx.moveTo(centerX - span * 0.38, centerY);
  ctx.quadraticCurveTo(centerX - span * 0.18, centerY - span * 0.11, centerX, centerY);
  ctx.stroke();
  ctx.fillStyle = `rgba(245,243,255,${0.25 + writeProgress * 0.65})`;
  ctx.shadowColor = "#c4b5fd";
  ctx.shadowBlur = 18;
  ctx.fillRect(writeX - 7, writeY - 4, 14, 8);
  ctx.shadowBlur = 0;

  ctx.fillStyle = "rgba(192,132,252,.95)";
  ctx.shadowColor = "#c084fc";
  ctx.shadowBlur = 28;
  ctx.beginPath();
  ctx.arc(centerX, centerY, 7 + Math.sin(time * 2) * 1.5, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.fillStyle = "rgba(245,243,255,.92)";
  ctx.textAlign = "center";
  ctx.font = "700 18px ui-sans-serif, system-ui";
  ctx.fillText(String(labels.length), centerX, centerY - 18);
  ctx.font = "8px ui-monospace, Menlo, monospace";
  ctx.fillText("MEMÓRIA · REGISTRO CONFIRMADO", centerX, centerY + 26);
  ctx.textAlign = "right";
  ctx.fillStyle = "rgba(216,180,254,.45)";
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
  const centerX = width * 0.5;
  const centerY = height * 0.43;
  const span = Math.min(width, height);
  const assembly = 0.5 + 0.5 * Math.sin(time * 0.92);
  ctx.save();
  ctx.globalAlpha = Math.max(0, Math.min(1, opacity));
  const aura = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, span * 0.42);
  aura.addColorStop(0, `rgba(192,132,252,${0.13 + assembly * 0.08})`);
  aura.addColorStop(0.48, "rgba(139,92,246,.045)");
  aura.addColorStop(1, "rgba(109,40,217,0)");
  ctx.fillStyle = aura;
  ctx.fillRect(0, 0, width, height);

  for (let ring = 1; ring <= 3; ring += 1) {
    const radius = ring * span * 0.09;
    ctx.strokeStyle = ring === 2 ? "rgba(192,132,252,.2)" : "rgba(196,181,253,.12)";
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
    ctx.strokeStyle = index % 3 ? "rgba(196,181,253,.11)" : "rgba(192,132,252,.18)";
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(component.phase + time * (0.18 + index % 3 * 0.04));
    ctx.strokeStyle = index % 3 ? `rgba(221,214,254,${0.34 + assembly * 0.38})` : `rgba(233,213,255,${0.4 + assembly * 0.4})`;
    ctx.fillStyle = index % 3 ? "rgba(109,40,217,.12)" : "rgba(126,34,206,.13)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(-component.size, -component.size * 0.55, component.size * 2, component.size * 1.1, 2);
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  });

  const coreRadius = 12 + assembly * 14;
  const glow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, coreRadius * 2.4);
  glow.addColorStop(0, `rgba(250,245,255,${0.7 + assembly * 0.24})`);
  glow.addColorStop(0.42, `rgba(192,132,252,${0.24 + assembly * 0.18})`);
  glow.addColorStop(1, "rgba(139,92,246,0)");
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(centerX, centerY, coreRadius * 2.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "rgba(255,255,255,.9)";
  ctx.beginPath();
  ctx.arc(centerX, centerY, coreRadius * 0.35, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "rgba(196,181,253,.5)";
  ctx.strokeRect(centerX - span * 0.105, centerY - span * 0.06, span * 0.21, span * 0.12);
  ctx.fillStyle = "rgba(243,232,255,.75)";
  ctx.font = "700 9px ui-monospace, Menlo, monospace";
  ctx.textAlign = "center";
  ctx.fillText("FORJA · CONSTRUÇÃO EM CURSO", centerX, centerY + span * 0.28);
  ["ANALISAR", "MONTAR", "TESTAR", "ENTREGAR"].forEach((label, index) => {
    const angle = -Math.PI * 0.8 + index * Math.PI * 0.53;
    const x = centerX + Math.cos(angle) * span * 0.27;
    const y = centerY + Math.sin(angle) * span * 0.25;
    ctx.fillStyle = index <= Math.floor(assembly * 4) ? "rgba(243,232,255,.72)" : "rgba(221,214,254,.38)";
    ctx.fillText(label, x, y);
  });
  ctx.restore();
}

function drawVoiceWaves(ctx, width, height, time, opacity = 1) {
  const centerX = width * 0.5;
  const centerY = height * 0.43;
  const span = Math.min(width, height);
  ctx.save();
  ctx.globalCompositeOperation = "screen";
  for (let ring = 0; ring < 4; ring += 1) {
    const progress = (time * 0.18 + ring * 0.24) % 1;
    const fade = Math.sin(progress * Math.PI) * Math.max(0, Math.min(1, opacity));
    const radiusX = span * (0.2 + progress * 0.13);
    const radiusY = span * (0.14 + progress * 0.085);
    ctx.strokeStyle = `rgba(196,181,253,${fade * 0.1})`;
    ctx.lineWidth = 0.8 + fade * 0.45;
    ctx.shadowColor = "rgba(139,92,246,.28)";
    ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.ellipse(centerX, centerY, radiusX, radiusY, 0, Math.PI * 0.14, Math.PI * 0.86);
    ctx.stroke();
    ctx.beginPath();
    ctx.ellipse(centerX, centerY, radiusX, radiusY, 0, Math.PI * 1.14, Math.PI * 1.86);
    ctx.stroke();
  }
  ctx.restore();
}

function createInternalNetwork(parent) {
  const group = new THREE.Group();
  group.name = "internal-neural-network";
  group.position.z = 0.13;
  parent.add(group);

  const pathMaterial = new THREE.MeshBasicMaterial({
    color: 0xb99cff,
    transparent: true,
    opacity: 0.34,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const pulseMaterial = new THREE.MeshBasicMaterial({
    color: 0xf1e9ff,
    transparent: true,
    opacity: 0.86,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const coreMaterial = new THREE.MeshPhysicalMaterial({
    color: 0x7c3aed,
    roughness: 0.12,
    clearcoat: 1,
    emissive: 0x6d28d9,
    emissiveIntensity: 1.2,
    transparent: true,
    opacity: 0.78,
  });

  const routes = [
    [[0, -0.96, -0.08], [0.02, -0.54, 0.02], [-0.03, -0.1, 0.12], [0, 0.34, 0.16], [0, 0.82, 0.08]],
    [[0, -0.62, 0.02], [-0.32, -0.7, 0.06], [-0.7, -0.79, -0.02], [-0.98, -0.72, -0.11]],
    [[0, -0.62, 0.02], [0.32, -0.7, 0.06], [0.7, -0.79, -0.02], [0.98, -0.72, -0.11]],
    [[-0.02, -0.13, 0.12], [-0.28, 0.04, 0.19], [-0.39, 0.33, 0.2], [-0.48, 0.58, 0.08]],
    [[0.02, -0.13, 0.12], [0.28, 0.04, 0.19], [0.39, 0.33, 0.2], [0.48, 0.58, 0.08]],
    [[0, 0.28, 0.16], [-0.17, 0.42, 0.28], [-0.31, 0.39, 0.31]],
    [[0, 0.28, 0.16], [0.17, 0.42, 0.28], [0.31, 0.39, 0.31]],
    [[0, 0.58, 0.13], [-0.2, 0.71, 0.14], [-0.31, 0.84, 0.04]],
    [[0, 0.58, 0.13], [0.2, 0.71, 0.14], [0.31, 0.84, 0.04]],
  ];

  const curves = routes.map((route, index) => {
    const curve = new THREE.CatmullRomCurve3(route.map((point) => new THREE.Vector3(...point)));
    const tube = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 22, index === 0 ? 0.012 : 0.007, 5, false),
      pathMaterial,
    );
    tube.name = `internal-path-${index + 1}`;
    group.add(tube);
    return curve;
  });

  const pulseGeometry = new THREE.SphereGeometry(0.022, 10, 8);
  const pulses = curves.map((curve, index) => {
    const pulse = new THREE.Mesh(pulseGeometry, pulseMaterial);
    pulse.userData = { curve, offset: index / curves.length, speed: 0.045 + index % 3 * 0.012 };
    group.add(pulse);
    return pulse;
  });
  const core = new THREE.Mesh(new THREE.SphereGeometry(0.085, 18, 12), coreMaterial);
  core.name = "internal-heart-core";
  core.position.set(0, -0.48, 0.04);
  group.add(core);

  return {
    group,
    setColor(color) {
      pathMaterial.color.copy(color).lerp(new THREE.Color(0xe9d5ff), 0.28);
      coreMaterial.emissive.copy(color);
    },
    update(time, intensity = 1) {
      const pulse = 0.5 + 0.5 * Math.sin(time * 1.8);
      pathMaterial.opacity = 0.2 + intensity * 0.22 + pulse * 0.06;
      pulseMaterial.opacity = 0.58 + intensity * 0.28;
      coreMaterial.emissiveIntensity = 0.9 + intensity * 0.8 + pulse * 0.35;
      core.scale.setScalar(0.92 + pulse * 0.16);
      pulses.forEach((signal) => {
        const progress = (time * signal.userData.speed + signal.userData.offset) % 1;
        signal.position.copy(signal.userData.curve.getPointAt(progress));
      });
    },
    dispose() {
      group.traverse((object) => object.geometry?.dispose());
      pathMaterial.dispose();
      pulseMaterial.dispose();
      coreMaterial.dispose();
    },
  };
}

async function loadCognitiveBust(root) {
  const gltf = await new GLTFLoader().loadAsync("/asset/models/jarvis-humanoid.glb?v=20260813-purple-bust");
  const model = gltf.scene || gltf.scenes[0];
  const shellMaterial = new THREE.MeshPhysicalMaterial({
    name: "jarvis-purple-shell",
    color: 0x5b21b6,
    metalness: 0.16,
    roughness: 0.28,
    clearcoat: 0.82,
    clearcoatRoughness: 0.18,
    transmission: 0.12,
    thickness: 0.5,
    emissive: 0x2e1065,
    emissiveIntensity: 0.32,
    transparent: true,
    opacity: 0.84,
    side: THREE.DoubleSide,
  });
  const headMaterial = shellMaterial.clone();
  headMaterial.name = "jarvis-purple-face";
  headMaterial.color.setHex(0x6d28d9);
  headMaterial.roughness = 0.34;
  headMaterial.opacity = 0.88;
  const eyeMaterial = new THREE.MeshPhysicalMaterial({
    name: "jarvis-real-eye-glass",
    color: 0xf5f3ff,
    metalness: 0,
    roughness: 0.035,
    clearcoat: 1,
    clearcoatRoughness: 0.01,
    transmission: 0.08,
    emissive: 0x8b5cf6,
    emissiveIntensity: 0.16,
  });

  const decorations = [];
  model.traverse((object) => {
    if (/halo|radiator/i.test(object.name || "")) {
      object.scale.setScalar(0.0001);
      object.userData.jarvisDecorationRemoved = true;
    }
    if (!object.isMesh) return;
    const hierarchy = [];
    let cursor = object;
    while (cursor && hierarchy.length < 5) {
      hierarchy.push(cursor.name || "");
      cursor = cursor.parent;
    }
    const identity = hierarchy.join(" ");
    const originalMaterials = Array.isArray(object.material) ? object.material : [object.material];
    const materialNames = originalMaterials.map((material) => material?.name || "").join(" ");
    if (/sketchfab_plane|particles/i.test(`${identity} ${materialNames}`)) {
      decorations.push(object);
      return;
    }
    object.frustumCulled = true;
    object.castShadow = false;
    object.receiveShadow = false;
    if (/glow|eye/i.test(`${identity} ${materialNames}`)) object.material = eyeMaterial;
    else if (/head/i.test(materialNames)) object.material = headMaterial;
    else object.material = shellMaterial;
  });
  decorations.forEach((object) => object.removeFromParent());

  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const scale = 2.08 / (Math.max(size.x, size.y, size.z) || 1);
  model.scale.setScalar(scale);
  model.position.set(-center.x * scale, -center.y * scale - 0.08, -center.z * scale);
  model.name = "jarvis-purple-cognitive-bust";
  root.add(model);

  const neural = createInternalNetwork(root);
  return { model, neural, shellMaterials: [shellMaterial, headMaterial], eyeMaterial, gltf };
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
  renderer.setPixelRatio(compactViewport || constrainedHardware ? 1 : Math.min(window.devicePixelRatio || 1, 1.25));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.92;
  mount.appendChild(renderer.domElement);

  const effectCanvas = makeEffectCanvas();
  const effectContext = effectCanvas.getContext("2d");
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  camera.position.set(0, 0.02, 5.1);

  scene.add(new THREE.AmbientLight(0x160b2b, 1.12));
  const key = new THREE.DirectionalLight(0xd8b4fe, 2.65);
  key.position.set(2.6, 3.4, 4.2);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x7c3aed, 2.15);
  rim.position.set(-3, 1.3, -2);
  scene.add(rim);
  const eyeCatchlight = new THREE.PointLight(0xf5f3ff, 4.2, 5, 1.8);
  eyeCatchlight.position.set(0.16, 0.55, 2.7);
  scene.add(eyeCatchlight);
  const root = new THREE.Group();
  scene.add(root);

  const bust = await loadCognitiveBust(root);
  const model = bust.model;
  stage.dataset.modelAsset = "jarvis-purple-cognitive-bust";
  stage.dataset.modelAnimations = "0";
  stage.dataset.modelAnimationSeconds = "0";
  stage.dataset.removedDecorations = "scan-line,halo,radiators,floating-triangles";
  stage.dataset.renderProfile = constrainedHardware ? "adaptive-lite" : "purple-neural-bust";

  const particleCount = compactViewport || constrainedHardware ? 12 : 22;
  const particlePositions = new Float32Array(particleCount * 3);
  for (let index = 0; index < particleCount; index += 1) {
    const height = (Math.random() - 0.5) * 1.7;
    const width = height < -0.45 ? 0.95 : 0.48;
    particlePositions[index * 3] = (Math.random() - 0.5) * width * 2;
    particlePositions[index * 3 + 1] = height;
    particlePositions[index * 3 + 2] = (Math.random() - 0.5) * 0.28 + 0.04;
  }
  const particleGeometry = new THREE.BufferGeometry();
  particleGeometry.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
  const particleMaterial = new THREE.PointsMaterial({ color: COLORS.idle, size: 0.018, transparent: true, opacity: 0.24, blending: THREE.AdditiveBlending, depthWrite: false });
  const particles = new THREE.Points(particleGeometry, particleMaterial);
  particles.name = "internal-neural-points";
  root.add(particles);

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
  const whiteColor = new THREE.Color(0xffffff);

  stage.addEventListener("pointermove", (event) => {
    const rect = mount.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) {
      pointerX = 0;
      pointerY = 0;
      return;
    }
    pointerX = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointerY = ((event.clientY - rect.top) / rect.height) * 2 - 1;
  }, { passive: true });
  stage.addEventListener("pointerleave", () => {
    pointerX = 0;
    pointerY = 0;
  });

  let canvasWidth = 1;
  let canvasHeight = 1;
  let layoutScale = 1;
  function resize() {
    const rect = mount.getBoundingClientRect();
    canvasWidth = Math.max(rect.width, 1);
    canvasHeight = Math.max(rect.height, 1);
    camera.aspect = canvasWidth / canvasHeight;
    camera.updateProjectionMatrix();
    layoutScale = Math.min(1, Math.max(0.58, camera.aspect * 1.25));
    renderer.setSize(canvasWidth, canvasHeight, false);
    const density = Math.min(window.devicePixelRatio || 1, 1.25);
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
  presenceValue.textContent = "Busto cognitivo · rede neural interna · olhos ópticos";

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
  let mountVisible = true;
  let visibilityObserver = null;
  let lastRenderTargetFps = 0;
  let lastRenderProfile = "";
  const modeBlend = { core: 0, forge: 0, memory: 0, voice: 0 };

  const activeStates = new Set(["listening", "thinking", "planning", "research", "forge", "voice", "speaking", "preview", "memory", "local"]);
  function requestedTargetFps() {
    if (document.hidden || !mountVisible) return 0;
    if (!windowFocused) return BACKGROUND_TARGET_FPS;
    return activeStates.has(visualState) ? ACTIVE_TARGET_FPS : IDLE_TARGET_FPS;
  }

  function updateRenderBudget() {
    const requestedFps = requestedTargetFps();
    const targetFps = requestedFps === 0 ? 0 : Math.max(1, Math.min(requestedFps, adaptiveMaxFps));
    frameIntervalMs = targetFps === 0 ? 1000 : 1000 / targetFps;
    const profile = targetFps === 0
      ? "paused"
      : !windowFocused
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
    if (disposed || reducedMotion || document.hidden || !mountVisible) return;
    window.clearTimeout(animationTimerId);
    animationTimerId = window.setTimeout(() => {
      animationFrameId = requestAnimationFrame(render);
    }, Math.max(0, delay));
  }

  function wakeRender() {
    window.clearTimeout(animationTimerId);
    cancelAnimationFrame(animationFrameId);
    previousFrameMs = 0;
    updateRenderBudget();
    scheduleRender(0);
  }

  window.addEventListener("jarvis-state", wakeRender);
  document.addEventListener("visibilitychange", wakeRender);
  if ("IntersectionObserver" in window) {
    visibilityObserver = new IntersectionObserver((entries) => {
      mountVisible = entries.some((entry) => entry.isIntersecting && entry.intersectionRatio > 0);
      wakeRender();
    }, { threshold: 0.01 });
    visibilityObserver.observe(mount);
  }

  function render(timeMs) {
    if (disposed) return;
    updateRenderBudget();
    if (document.hidden || !mountVisible) {
      previousFrameMs = timeMs;
      return;
    }
    const deltaSeconds = previousFrameMs ? Math.min((timeMs - previousFrameMs) / 1000, 0.1) : 0;
    previousFrameMs = timeMs;
    sampledFrames += 1;
    if (timeMs - fpsWindowStart >= 1000) {
      const measuredFps = Math.round(sampledFrames * 1000 / (timeMs - fpsWindowStart));
      stage.dataset.renderFps = String(measuredFps);
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
    const blendEase = 1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 1.65);
    Object.keys(modeBlend).forEach((mode) => {
      const target = visualMode === mode ? 1 : 0;
      modeBlend[mode] += (target - modeBlend[mode]) * blendEase;
    });
    const activeColor = COLORS[visualState] || COLORS.idle;
    const isWorking = modeBlend.forge > 0.08;
    targetColor.setHex(activeColor);
    const colorEase = 1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 1.8);
    currentColor.lerp(targetColor, colorEase);
    particleMaterial.color.copy(currentColor);
    bust.shellMaterials.forEach((material, index) => {
      material.emissive.copy(currentColor).multiplyScalar(index ? 0.2 : 0.14);
      material.emissiveIntensity = isWorking ? 0.5 : visualState === "speaking" ? 0.46 : 0.32;
    });
    bust.eyeMaterial.emissive.copy(currentColor).lerp(whiteColor, 0.36);
    bust.eyeMaterial.emissiveIntensity = visualState === "speaking" ? 0.34 : isWorking ? 0.26 : 0.16;
    bust.neural.setColor(currentColor);

    const motion = activeStates.has(visualState) ? 1 : 0.24;
    bust.neural.update(time, isWorking || visualState === "speaking" ? 1 : 0.45 * motion);

    const orientationEase = 1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 1.45);
    currentX += (pointerX * 0.12 - currentX) * orientationEase;
    currentY += (pointerY * 0.035 - currentY) * orientationEase;
    const cameraTargetX = 0;
    const cameraTargetZ = 5.02 + modeBlend.memory * 0.18 + modeBlend.forge * 0.12 + modeBlend.core * 0.08;
    const cameraEase = 1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 1.2);
    camera.position.x += (cameraTargetX - camera.position.x) * cameraEase;
    camera.position.z += (cameraTargetZ - camera.position.z) * cameraEase;
    camera.lookAt(0, -0.01, 0);
    const targetPositionX = 0;
    const positionEase = 1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 1.35);
    root.position.x += (targetPositionX - root.position.x) * positionEase;
    const activePresence = activeStates.has(visualState) ? 1 : 0;
    root.position.y = -0.02 + Math.sin(time * 0.48) * 0.008 * activePresence;
    const facingYaw = Math.atan2(camera.position.x - root.position.x, camera.position.z - root.position.z);
    root.rotation.y = currentX + facingYaw + Math.sin(time * 0.22) * 0.012;
    root.rotation.x = currentY + Math.sin(time * 0.28) * 0.002 * activePresence;
    const speakingPulse = visualState === "speaking" ? (Math.sin(time * 2.4) + 1) * 0.08 : 0;
    const targetScale = layoutScale * (1 - modeBlend.memory * 0.07 - modeBlend.forge * 0.045 - modeBlend.core * 0.025 + speakingPulse * 0.035);
    currentScale += (targetScale - currentScale) * (1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 1.8));
    root.scale.setScalar(currentScale);
    particleMaterial.opacity = isWorking ? 0.27 : 0.16 + speakingPulse * 0.22;
    particles.rotation.y = Math.sin(time * 0.18) * 0.025;

    const effectFrameDue = timeMs - effectLastFrameMs >= 1000 / EFFECT_TARGET_FPS;
    const effectBlend = Math.max(modeBlend.memory, modeBlend.forge, modeBlend.voice);
    if (effectBlend > 0.01 && effectFrameDue) {
      effectContext.clearRect(0, 0, canvasWidth, canvasHeight);
      if (modeBlend.memory > 0.01) drawMemory(effectContext, canvasWidth, canvasHeight, time, memoryLabels, modeBlend.memory);
      if (modeBlend.forge > 0.01) drawForge(effectContext, canvasWidth, canvasHeight, time, modeBlend.forge);
      if (modeBlend.voice > 0.01) drawVoiceWaves(effectContext, canvasWidth, canvasHeight, time, modeBlend.voice);
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
    visibilityObserver?.disconnect();
    bust.neural.dispose();
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
