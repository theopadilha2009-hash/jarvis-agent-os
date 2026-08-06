import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const mount = document.getElementById("avatar3d");
const stage = document.getElementById("stage");
const presenceValue = document.getElementById("presenceValue");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

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
window.addEventListener("jarvis-state", (event) => {
  visualState = event.detail?.state || "idle";
});

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
  canvas.style.zIndex = "2";
  canvas.style.pointerEvents = "none";
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
  const centerX = width * 0.56;
  const centerY = height * 0.47;
  const span = Math.min(width, height);
  const clusters = [
    [centerX - span * 0.22, centerY - span * 0.13],
    [centerX + span * 0.20, centerY - span * 0.12],
    [centerX - span * 0.18, centerY + span * 0.18],
    [centerX + span * 0.22, centerY + span * 0.17],
  ];
  ctx.save();
  ctx.font = "9px ui-monospace, Menlo, monospace";
  labels.forEach((label, index) => {
    const cluster = clusters[index % clusters.length];
    const angle = index * 2.17 + time * (index % 2 ? -0.045 : 0.045);
    const distance = span * (0.07 + (index % 4) * 0.018);
    const x = cluster[0] + Math.cos(angle) * distance;
    const y = cluster[1] + Math.sin(angle) * distance * 0.8;
    ctx.strokeStyle = "rgba(127,182,255,.15)";
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
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
  ctx.fillText("LOCAL MEMORY", centerX, centerY + 24);
  ctx.restore();
}

function drawThinking(ctx, width, height, time) {
  const centerX = width * 0.59;
  const centerY = height * 0.45;
  const radius = Math.min(width, height) * 0.2;
  ctx.save();
  ctx.strokeStyle = "rgba(167,139,250,.22)";
  ctx.lineWidth = 1;
  for (let index = 0; index < 5; index += 1) {
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius * (0.45 + index * 0.17), time * (0.4 + index * 0.1), time * (0.4 + index * 0.1) + Math.PI * (0.55 + index * 0.12));
    ctx.stroke();
  }
  ctx.restore();
}

async function start() {
  if (!webglAvailable()) throw new Error("WebGL unavailable");

  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "high-performance" });
  renderer.domElement.style.position = "absolute";
  renderer.domElement.style.inset = "0";
  renderer.domElement.style.zIndex = "1";
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.92;
  mount.appendChild(renderer.domElement);

  const effectCanvas = makeEffectCanvas();
  const effectContext = effectCanvas.getContext("2d");
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  camera.position.set(0, 0.02, 5.1);

  try {
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
  } catch {
    // Direct lights below keep the model usable without an environment map.
  }

  scene.add(new THREE.AmbientLight(0x071723, 0.75));
  const key = new THREE.DirectionalLight(0x67e8f9, 2.3);
  key.position.set(2.6, 3.4, 4.2);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x8b5cf6, 1.7);
  rim.position.set(-3, 1.3, -2);
  scene.add(rim);

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

  let memoryLabels = await loadMemoryLabels();
  window.addEventListener("jarvis-memory-refresh", async () => {
    memoryLabels = await loadMemoryLabels();
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
    const density = Math.min(devicePixelRatio || 1, 2);
    effectCanvas.width = canvasWidth * density;
    effectCanvas.height = canvasHeight * density;
    effectCanvas.style.width = `${canvasWidth}px`;
    effectCanvas.style.height = `${canvasHeight}px`;
    effectContext.setTransform(density, 0, 0, density, 0, 0);
  }
  new ResizeObserver(resize).observe(mount);
  resize();

  stage.classList.add("model-ready");
  presenceValue.textContent = "humanoide 3D local + modos vivos";

  function render(timeMs) {
    const time = timeMs * 0.001;
    const activeColor = COLORS[visualState] || COLORS.idle;
    const isWorking = ["thinking", "planning", "memory"].includes(visualState);
    const sideMode = isWorking;
    targetColor.setHex(activeColor);
    currentColor.lerp(targetColor, 0.065);
    wireMaterial.color.copy(currentColor);
    visorMaterial.color.copy(currentColor);
    particleMaterial.color.copy(currentColor);
    eyeMaterial.color.copy(currentColor).lerp(white, 0.22);

    currentX += (pointerX * 0.25 - currentX) * 0.055;
    currentY += (pointerY * 0.12 - currentY) * 0.055;
    const targetPositionX = sideMode ? -0.72 : 0;
    root.position.x += (targetPositionX - root.position.x) * 0.045;
    root.position.y = Math.sin(time * 0.9) * 0.035;
    root.rotation.y = currentX + Math.sin(time * 0.38) * 0.035 + (sideMode ? -0.12 : 0);
    root.rotation.x = currentY + Math.sin(time * 0.47) * 0.012;
    const speakingPulse = visualState === "speaking" ? (Math.sin(time * 10) + 1) * 0.12 : 0;
    root.scale.setScalar(1 + speakingPulse * 0.035);
    visor.position.y = 0.3 + Math.sin(time * (isWorking ? 1.8 : 0.7)) * 0.57;
    visorMaterial.opacity = (visualState === "listening" ? 0.52 : 0.32) + speakingPulse;
    wireMaterial.opacity = isWorking ? 0.16 : 0.09 + speakingPulse * 0.24;
    particleMaterial.opacity = isWorking ? 0.46 : 0.32 + speakingPulse;
    particles.rotation.y += 0.0012 * (isWorking ? 2 : 1);

    effectContext.clearRect(0, 0, canvasWidth, canvasHeight);
    if (visualState === "memory") drawMemory(effectContext, canvasWidth, canvasHeight, time, memoryLabels);
    else if (["thinking", "planning"].includes(visualState)) drawThinking(effectContext, canvasWidth, canvasHeight, time);

    renderer.render(scene, camera);
    requestAnimationFrame(render);
  }

  if (reducedMotion) renderer.render(scene, camera);
  else requestAnimationFrame(render);
}

start().catch((error) => {
  stage.classList.remove("model-ready");
  presenceValue.textContent = "busto holográfico de contingência";
  console.warn("JARVIS 3D fallback", error);
});
