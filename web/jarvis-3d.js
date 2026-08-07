import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const mount = document.getElementById("avatar3d");
const stage = document.getElementById("stage");
const presenceValue = document.getElementById("presenceValue");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const compactViewport = matchMedia("(max-width: 900px)").matches;
const FRAME_INTERVAL_MS = 1000 / 30;

const COLORS = {
  idle: 0x46e6ff,
  listening: 0x22d3ee,
  thinking: 0x8b5cf6,
  planning: 0x8b5cf6,
  speaking: 0x67e8f9,
  response: 0x67e8f9,
  memory: 0x7fb6ff,
  local: 0xfbbf24,
  success: 0x6ee7b7,
  error: 0xfb7185,
  offline: 0x475569,
};

let visualState = stage.dataset.state || "idle";
function visualModeForState(state) {
  if (["thinking", "planning", "local"].includes(state)) return "forge";
  if (state === "memory") return "source";
  if (["listening", "speaking"].includes(state)) return "core";
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

function webglAvailable() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(window.WebGLRenderingContext && (canvas.getContext("webgl") || canvas.getContext("experimental-webgl")));
  } catch {
    return false;
  }
}

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
    const response = await fetch("/memory-tree");
    if (!response.ok) throw new Error("memory tree unavailable");
    const data = await response.json();
    return (data.nodes || []).slice(0, 28).map((node) => String(node.label || node.name || "MEMORY").slice(0, 18).toUpperCase());
  } catch {
    return ["DECISIONS", "LEARNINGS", "PROJECTS", "CONTEXT", "TASKS", "ACTIONS", "THEO"];
  }
}

function drawMemory(ctx, width, height, time, labels) {
  const centerX = width * (compactViewport ? 0.62 : 0.69);
  const centerY = height * 0.45;
  const span = Math.min(width, height);
  const clusters = [
    [centerX - span * 0.17, centerY - span * 0.15],
    [centerX + span * 0.18, centerY - span * 0.12],
    [centerX - span * 0.14, centerY + span * 0.17],
    [centerX + span * 0.17, centerY + span * 0.16],
  ];
  ctx.save();
  const aura = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, span * 0.42);
  aura.addColorStop(0, "rgba(93,139,255,.12)");
  aura.addColorStop(0.6, "rgba(53,88,180,.035)");
  aura.addColorStop(1, "rgba(53,88,180,0)");
  ctx.fillStyle = aura;
  ctx.fillRect(0, 0, width, height);
  ctx.setLineDash([2, 7]);
  ctx.strokeStyle = "rgba(127,182,255,.08)";
  for (let row = 0; row < 5; row += 1) {
    const y = height * (0.22 + row * 0.12);
    ctx.beginPath();
    ctx.moveTo(width * 0.42, y);
    ctx.lineTo(width * 0.94, y);
    ctx.stroke();
  }
  ctx.setLineDash([]);
  ctx.font = "9px ui-monospace, Menlo, monospace";
  labels.forEach((label, index) => {
    const cluster = clusters[index % clusters.length];
    const angle = index * 2.17 + time * (index % 2 ? -0.045 : 0.045);
    const distance = span * (0.07 + (index % 4) * 0.018);
    const x = cluster[0] + Math.cos(angle) * distance;
    const y = cluster[1] + Math.sin(angle) * distance * 0.8;
    ctx.strokeStyle = "rgba(127,182,255,.13)";
    ctx.beginPath();
    ctx.moveTo(cluster[0], cluster[1]);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.fillStyle = "rgba(180,220,255,.92)";
    ctx.shadowColor = "#7fb6ff";
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(x, y, 2.5 + (index % 3), 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.fillStyle = "rgba(204,226,248,.74)";
    ctx.fillText(label, x + 7, y + 3);
  });
  clusters.forEach(([x, y], index) => {
    ctx.strokeStyle = "rgba(127,182,255,.16)";
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(x, y);
    ctx.stroke();
    const flow = (time * 0.2 + index * 0.23) % 1;
    ctx.fillStyle = "rgba(192,215,255,.72)";
    ctx.beginPath();
    ctx.arc(centerX + (x - centerX) * flow, centerY + (y - centerY) * flow, 1.7, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(127,182,255,.7)";
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.fillStyle = "rgba(127,182,255,.95)";
  ctx.shadowColor = "#7fb6ff";
  ctx.shadowBlur = 22;
  ctx.beginPath();
  ctx.arc(centerX, centerY, 7, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.fillStyle = "rgba(215,238,255,.9)";
  ctx.textAlign = "center";
  ctx.font = "700 22px ui-sans-serif, system-ui";
  ctx.fillText(String(labels.length), centerX, centerY - 16);
  ctx.font = "8px ui-monospace, Menlo, monospace";
  ctx.fillText("MEMORY CONSTELLATION", centerX, centerY + 24);
  ctx.textAlign = "right";
  ctx.fillStyle = "rgba(150,180,220,.54)";
  ctx.fillText("SOURCE · CONTEXT INDEX", width - 22, height - 26);
  ctx.restore();
}

const FORGE_SHARDS = Array.from({ length: 26 }, (_, index) => ({
  angle: index * 2.399963,
  radius: 0.34 + (index % 6) * 0.035,
  phase: index * 1.731,
  size: 5 + (index % 5) * 2.2,
}));

function drawForge(ctx, width, height, time) {
  const centerX = width * (compactViewport ? 0.62 : 0.69);
  const centerY = height * 0.45;
  const span = Math.min(width, height);
  const convergence = 0.5 + 0.5 * Math.sin(time * 1.1);
  ctx.save();
  const aura = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, span * 0.42);
  aura.addColorStop(0, `rgba(192,107,255,${0.16 + convergence * 0.08})`);
  aura.addColorStop(0.55, "rgba(125,72,190,.04)");
  aura.addColorStop(1, "rgba(125,72,190,0)");
  ctx.fillStyle = aura;
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(192,107,255,.16)";
  for (let ring = 1; ring <= 4; ring += 1) {
    const radius = ring * span * 0.082;
    ctx.beginPath();
    for (let side = 0; side <= 6; side += 1) {
      const angle = side / 6 * Math.PI * 2 + time * 0.12 * ring + ring * 0.2;
      const x = centerX + Math.cos(angle) * radius;
      const y = centerY + Math.sin(angle) * radius * 0.86;
      if (side) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    }
    ctx.closePath();
    ctx.stroke();
  }
  FORGE_SHARDS.forEach((shard, index) => {
    const distance = shard.radius * span * (0.46 + 0.54 * (1 - convergence));
    const angle = shard.angle + time * 0.22;
    const x = centerX + Math.cos(angle) * distance;
    const y = centerY + Math.sin(angle) * distance * 0.86;
    ctx.strokeStyle = `rgba(192,107,255,${0.06 + convergence * 0.11})`;
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(shard.phase + time * (0.7 + index % 3 * 0.12));
    ctx.fillStyle = `rgba(218,162,255,${0.32 + convergence * 0.4})`;
    ctx.beginPath();
    ctx.moveTo(0, -shard.size);
    ctx.lineTo(shard.size * 0.55, shard.size * 0.52);
    ctx.lineTo(-shard.size * 0.55, shard.size * 0.52);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  });
  const coreRadius = 10 + convergence * 20;
  const glow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, coreRadius * 2.4);
  glow.addColorStop(0, `rgba(247,224,255,${0.7 + convergence * 0.25})`);
  glow.addColorStop(0.45, `rgba(192,107,255,${0.28 + convergence * 0.2})`);
  glow.addColorStop(1, "rgba(192,107,255,0)");
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(centerX, centerY, coreRadius * 2.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "rgba(255,255,255,.9)";
  ctx.beginPath();
  ctx.arc(centerX, centerY, coreRadius * 0.35, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "rgba(222,188,255,.72)";
  ctx.font = "700 9px ui-monospace, Menlo, monospace";
  ctx.textAlign = "center";
  ctx.fillText("FORGE · BUILD PIPELINE", centerX, centerY + span * 0.27);
  ["CONTEXT", "PLAN", "EXECUTE", "VERIFY"].forEach((label, index) => {
    const angle = -Math.PI * 0.8 + index * Math.PI * 0.53;
    const x = centerX + Math.cos(angle) * span * 0.3;
    const y = centerY + Math.sin(angle) * span * 0.25;
    ctx.fillStyle = "rgba(205,174,238,.48)";
    ctx.fillText(label, x, y);
  });
  ctx.restore();
}

function makeCoreEntity(scene) {
  const group = new THREE.Group();
  group.position.set(1.08, 0.02, -1.05);
  group.scale.setScalar(0.68);
  group.visible = false;
  scene.add(group);

  const obsidianMaterial = new THREE.MeshPhysicalMaterial({
    color: 0x120d22,
    roughness: 0.16,
    transmission: 0.34,
    thickness: 1.2,
    ior: 1.46,
    clearcoat: 0.9,
    emissive: 0x271052,
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
    color: 0x8b5cf6,
    wireframe: true,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const containment = new THREE.Mesh(new THREE.IcosahedronGeometry(1.28, 1), wireMaterial);
  group.add(containment);

  const shardMaterial = new THREE.MeshBasicMaterial({
    color: 0xa78bfa,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const shards = Array.from({ length: reducedMotion ? 8 : 14 }, (_, index) => {
    const shard = new THREE.Mesh(new THREE.TetrahedronGeometry(0.1 + index % 3 * 0.025), shardMaterial);
    const y = 1 - index / Math.max(1, (reducedMotion ? 8 : 14) - 1) * 2;
    const radius = Math.sqrt(Math.max(0, 1 - y * y));
    const angle = index * 2.399963;
    shard.userData.direction = new THREE.Vector3(Math.cos(angle) * radius, y * 0.76, Math.sin(angle) * radius);
    group.add(shard);
    return shard;
  });

  let alpha = 0;
  function update(time, visible) {
    alpha += ((visible ? 1 : 0) - alpha) * 0.08;
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

async function start() {
  if (!webglAvailable()) throw new Error("WebGL unavailable");

  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: !compactViewport, powerPreference: "high-performance" });
  renderer.domElement.style.position = "absolute";
  renderer.domElement.style.inset = "0";
  renderer.domElement.style.zIndex = "1";
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, compactViewport ? 1 : 1.35));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.92;
  mount.appendChild(renderer.domElement);

  const effectCanvas = makeEffectCanvas();
  const effectContext = effectCanvas.getContext("2d");
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  camera.position.set(0, 0.02, 5.1);

  scene.add(new THREE.AmbientLight(0x071723, 0.75));
  const key = new THREE.DirectionalLight(0x67e8f9, 2.3);
  key.position.set(2.6, 3.4, 4.2);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x8b5cf6, 1.7);
  rim.position.set(-3, 1.3, -2);
  scene.add(rim);
  const coreEntity = makeCoreEntity(scene);

  const root = new THREE.Group();
  scene.add(root);
  const gltf = await new Promise((resolve, reject) => {
    new GLTFLoader().load("/asset/models/jarvis-humanoid.glb?v=20260806-real", resolve, undefined, reject);
  });

  const model = gltf.scene || gltf.scenes[0];
  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const scale = 2.42 / (Math.max(size.x, size.y, size.z) || 1);
  model.scale.setScalar(scale);
  model.position.set(-center.x * scale, -center.y * scale - 0.02, -center.z * scale);
  root.add(model);

  const shellMaterial = new THREE.MeshPhysicalMaterial({
    color: 0x0d1720,
    metalness: 0.52,
    roughness: 0.29,
    clearcoat: 0.68,
    clearcoatRoughness: 0.24,
    transmission: 0.04,
    thickness: 0.48,
    ior: 1.32,
    emissive: 0x062b36,
    emissiveIntensity: 0.28,
    envMapIntensity: 1.25,
    transparent: true,
    opacity: 0.92,
    side: THREE.DoubleSide,
  });
  const eyeMaterial = new THREE.MeshBasicMaterial({ color: 0xb6f7ff, transparent: true, opacity: 0.96, blending: THREE.AdditiveBlending });
  const wireMaterial = new THREE.MeshBasicMaterial({ color: COLORS.idle, wireframe: true, transparent: true, opacity: 0.1, blending: THREE.AdditiveBlending, depthWrite: false });
  const overlays = [];
  model.traverse((object) => {
    if (!object.isMesh || !object.geometry) return;
    const identity = `${object.name} ${object.parent?.name || ""}`;
    object.material = /eye/i.test(identity) ? eyeMaterial : shellMaterial;
    const wire = new THREE.Mesh(object.geometry, wireMaterial);
    wire.position.copy(object.position);
    wire.scale.copy(object.scale).multiplyScalar(1.005);
    wire.quaternion.copy(object.quaternion);
    overlays.push([object.parent, wire]);
  });
  overlays.forEach(([parent, wire]) => parent?.add(wire));

  const visorMaterial = new THREE.MeshBasicMaterial({ color: COLORS.idle, transparent: true, opacity: 0.34, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false });
  const visor = new THREE.Mesh(new THREE.PlaneGeometry(2.55, 0.055), visorMaterial);
  visor.position.set(0, 0.32, 1.38);
  root.add(visor);

  const particleCount = 190;
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
  const white = new THREE.Color(0xffffff);

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
    const density = Math.min(devicePixelRatio || 1, compactViewport ? 1 : 1.35);
    effectCanvas.width = canvasWidth * density;
    effectCanvas.height = canvasHeight * density;
    effectCanvas.style.width = `${canvasWidth}px`;
    effectCanvas.style.height = `${canvasHeight}px`;
    effectContext.setTransform(density, 0, 0, density, 0, 0);
  }
  new ResizeObserver(resize).observe(mount);
  resize();

  stage.classList.add("model-ready");
  presenceValue.textContent = "Avatar GLB · Core · Forja · Memória";

  let previousFrameMs = 0;
  let effectVisible = false;
  let currentScale = 1;
  function render(timeMs) {
    requestAnimationFrame(render);
    if (document.hidden || timeMs - previousFrameMs < FRAME_INTERVAL_MS) return;
    previousFrameMs = timeMs;
    const time = timeMs * 0.001;
    const visualMode = visualModeForState(visualState);
    stage.dataset.visualMode = visualMode;
    const activeColor = COLORS[visualState] || COLORS.idle;
    const isWorking = visualMode === "forge";
    targetColor.setHex(activeColor);
    currentColor.lerp(targetColor, 0.065);
    wireMaterial.color.copy(currentColor);
    visorMaterial.color.copy(currentColor);
    particleMaterial.color.copy(currentColor);
    eyeMaterial.color.copy(currentColor).lerp(white, 0.22);

    currentX += (pointerX * 0.25 - currentX) * 0.055;
    currentY += (pointerY * 0.12 - currentY) * 0.055;
    const targetPositionX = visualMode === "source" ? -0.9 : visualMode === "forge" ? -0.78 : visualMode === "core" ? -0.44 : 0;
    root.position.x += (targetPositionX - root.position.x) * 0.045;
    root.position.y = Math.sin(time * 0.9) * 0.035;
    root.rotation.y = currentX + Math.sin(time * 0.38) * 0.035 + (visualMode === "avatar" ? 0 : -0.1);
    root.rotation.x = currentY + Math.sin(time * 0.47) * 0.012;
    const speakingPulse = visualState === "speaking" ? (Math.sin(time * 10) + 1) * 0.12 : 0;
    const targetScale = (visualMode === "source" ? 0.92 : visualMode === "forge" ? 0.95 : visualMode === "core" ? 0.97 : 1) + speakingPulse * 0.035;
    currentScale += (targetScale - currentScale) * 0.055;
    root.scale.setScalar(currentScale);
    visor.position.y = 0.3 + Math.sin(time * (isWorking ? 1.8 : 0.7)) * 0.57;
    visorMaterial.opacity = (visualState === "listening" ? 0.52 : 0.32) + speakingPulse;
    wireMaterial.opacity = isWorking ? 0.16 : 0.09 + speakingPulse * 0.24;
    particleMaterial.opacity = isWorking ? 0.46 : 0.32 + speakingPulse;
    particles.rotation.y += 0.0012 * (isWorking ? 2 : 1);
    coreEntity.update(time, visualMode === "core");

    if (visualMode === "source") {
      effectContext.clearRect(0, 0, canvasWidth, canvasHeight);
      drawMemory(effectContext, canvasWidth, canvasHeight, time, memoryLabels);
      effectVisible = true;
    } else if (visualMode === "forge") {
      effectContext.clearRect(0, 0, canvasWidth, canvasHeight);
      drawForge(effectContext, canvasWidth, canvasHeight, time);
      effectVisible = true;
    } else if (effectVisible) {
      effectContext.clearRect(0, 0, canvasWidth, canvasHeight);
      effectVisible = false;
    }

    renderer.render(scene, camera);
  }

  if (reducedMotion) renderer.render(scene, camera);
  else requestAnimationFrame(render);
}

start().catch((error) => {
  stage.classList.remove("model-ready");
  presenceValue.textContent = "busto holográfico de contingência";
  console.warn("JARVIS 3D fallback", error);
});
