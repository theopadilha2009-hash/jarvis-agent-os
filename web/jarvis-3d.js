import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const mount = document.getElementById("avatar3d");
const stage = document.getElementById("stage");
const presenceValue = document.getElementById("presenceValue");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const compactViewport = matchMedia("(max-width: 900px)").matches;
const EFFECT_TARGET_FPS = 12;
const QUALITY_PROFILES = {
  excellent: { activeFps: 45, idleFps: 24, pixelRatio: 1.25 },
  medium: { activeFps: 30, idleFps: 18, pixelRatio: 1 },
  low: { activeFps: 20, idleFps: 10, pixelRatio: 0.75 },
};
let graphicsQuality = (() => {
  try {
    const saved = localStorage.getItem("jarvis-graphics-quality");
    return QUALITY_PROFILES[saved] ? saved : "excellent";
  } catch {
    return "excellent";
  }
})();

const COLORS = {
  idle: 0x8b5cf6,
  listening: 0xa855f7,
  thinking: 0xc084fc,
  research: 0x8b5cf6,
  planning: 0xa78bfa,
  forge: 0xd8b4fe,
  speaking: 0xc084fc,
  response: 0xa78bfa,
  memory: 0xb794f4,
  preview: 0x8b5cf6,
  local: 0xa855f7,
  success: 0x9f7aea,
  error: 0xfb7185,
  offline: 0x51445f,
};
const OWNER_RED = 0xef3340;

const VISITOR_HEAD_POSE_GLSL = `
  vec3 jarvisPoseHead(vec3 source, vec3 look) {
    float weight = smoothstep(10.5, 15.5, source.z);
    vec3 pivot = vec3(0.0, -2.8, 10.8);
    vec3 posed = source - pivot;
    float cy = cos(look.x);
    float sy = sin(look.x);
    posed.xy = mat2(cy, sy, -sy, cy) * posed.xy;
    float cp = cos(look.y);
    float sp = sin(look.y);
    posed.yz = mat2(cp, sp, -sp, cp) * posed.yz;
    float cr = cos(look.z);
    float sr = sin(look.z);
    posed.xz = mat2(cr, -sr, sr, cr) * posed.xz;
    return mix(source, posed + pivot, weight);
  }
`;

async function loadObjGeometry(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`OBJ unavailable (${response.status})`);
  const source = await response.text();
  const vertices = [];
  const normals = [];
  const positions = [];
  const outputNormals = [];
  source.split(/\r?\n/).forEach((line) => {
    const parts = line.trim().split(/\s+/);
    if (parts[0] === "v") vertices.push(parts.slice(1, 4).map(Number));
    else if (parts[0] === "vn") normals.push(parts.slice(1, 4).map(Number));
    else if (parts[0] === "f") {
      const corners = parts.slice(1).map((value) => value.split("/").map(Number));
      for (let index = 1; index < corners.length - 1; index += 1) {
        [corners[0], corners[index], corners[index + 1]].forEach(([vertexIndex, , normalIndex]) => {
          positions.push(...(vertices[vertexIndex - 1] || [0, 0, 0]));
          outputNormals.push(...(normals[normalIndex - 1] || [0, 0, 1]));
        });
      }
    }
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  if (normals.length) geometry.setAttribute("normal", new THREE.Float32BufferAttribute(outputNormals, 3));
  else geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  return geometry;
}

async function loadObjHead(url) {
  const geometry = await loadObjGeometry(url);
  const material = new THREE.MeshPhysicalMaterial({
    color: 0x7741ad,
    metalness: 0.04,
    roughness: 0.7,
    emissive: 0x2e105c,
    emissiveIntensity: 0.54,
    transparent: true,
    opacity: 0.66,
    depthWrite: false,
    side: THREE.FrontSide,
    clearcoat: 0.12,
    clearcoatRoughness: 0.8,
  });
  material.name = "visitor-purple-volume";
  const head = new THREE.Mesh(geometry, material);
  return head;
}

function installVisitorHeadPose(material) {
  const look = { value: new THREE.Vector3() };
  const previousCompile = material.onBeforeCompile;
  material.onBeforeCompile = (shader, renderer) => {
    if (previousCompile) previousCompile(shader, renderer);
    shader.uniforms.uJarvisHeadLook = look;
    shader.vertexShader = shader.vertexShader.replace(
      "void main() {",
      `uniform vec3 uJarvisHeadLook;\n${VISITOR_HEAD_POSE_GLSL}\nvoid main() {`,
    );
    shader.vertexShader = shader.vertexShader.replace(
      "#include <begin_vertex>",
      "vec3 transformed = jarvisPoseHead(vec3(position), uJarvisHeadLook);",
    );
  };
  material.customProgramCacheKey = () => "jarvis-human-head-pose-v1";
  material.needsUpdate = true;
  return look;
}

function makeVisitorLife(topologyGeometry) {
  const surface = new THREE.Group();
  surface.name = "visitor-topology-surface";

  const topologyMaterial = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uEnergy: { value: 0 },
      uHeadLook: { value: new THREE.Vector3() },
    },
    vertexShader: `
      varying float vSweep;
      uniform float uTime;
      uniform vec3 uHeadLook;
      ${VISITOR_HEAD_POSE_GLSL}
      void main() {
        float diagonal = position.x * 0.034 + position.z * 0.028;
        float wave = 0.5 + 0.5 * sin((diagonal - uTime * 0.17) * 6.2831853);
        vSweep = pow(wave, 10.0);
        vec3 posed = jarvisPoseHead(position, uHeadLook);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(posed, 1.0);
      }
    `,
    fragmentShader: `
      varying float vSweep;
      uniform float uEnergy;
      void main() {
        float alpha = 0.055 + vSweep * (0.36 + uEnergy * 0.16);
        gl_FragColor = vec4(0.75, 0.48, 1.0, alpha);
      }
    `,
    transparent: true,
    depthWrite: false,
    depthTest: true,
    blending: THREE.AdditiveBlending,
  });
  topologyMaterial.name = "visitor-animated-surface-topology";
  const topology = new THREE.LineSegments(new THREE.WireframeGeometry(topologyGeometry), topologyMaterial);
  topology.name = "visitor-surface-topology-2225";
  topology.renderOrder = 2;

  const source = topologyGeometry.getAttribute("position");
  const box = new THREE.Box3().setFromBufferAttribute(source);
  const cutoff = box.min.x + (box.max.x - box.min.x) * 0.28;
  const dissolvePositions = [];
  const dissolveSeeds = [];
  for (let index = 0; index < source.count; index += 7) {
    const x = source.getX(index);
    if (x > cutoff) continue;
    dissolvePositions.push(x, source.getY(index), source.getZ(index));
    dissolveSeeds.push(((index * 73) % 997) / 997);
  }
  const dissolveGeometry = new THREE.BufferGeometry();
  dissolveGeometry.setAttribute("position", new THREE.Float32BufferAttribute(dissolvePositions, 3));
  dissolveGeometry.setAttribute("aSeed", new THREE.Float32BufferAttribute(dissolveSeeds, 1));
  const dissolveMaterial = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uEnergy: { value: 0 },
      uPixelRatio: { value: 1 },
      uHeadLook: { value: new THREE.Vector3() },
    },
    vertexShader: `
      attribute float aSeed;
      varying float vAlpha;
      uniform float uTime;
      uniform float uEnergy;
      uniform float uPixelRatio;
      uniform vec3 uHeadLook;
      ${VISITOR_HEAD_POSE_GLSL}
      void main() {
        float flow = 0.5 + 0.5 * sin(uTime * 0.52 + aSeed * 12.0);
        vec3 p = position;
        p.x -= flow * (0.45 + aSeed * 0.75);
        p.z += sin(uTime * 0.38 + aSeed * 18.0) * 0.12;
        p = jarvisPoseHead(p, uHeadLook);
        vAlpha = (1.0 - flow * 0.62) * (0.28 + uEnergy * 0.18);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
        gl_PointSize = (1.1 + aSeed * 1.8 + uEnergy) * uPixelRatio;
      }
    `,
    fragmentShader: `
      varying float vAlpha;
      void main() {
        vec2 point = gl_PointCoord - 0.5;
        float soft = 1.0 - smoothstep(0.16, 0.5, length(point));
        gl_FragColor = vec4(0.72, 0.42, 1.0, vAlpha * soft);
      }
    `,
    transparent: true,
    depthWrite: false,
    depthTest: true,
    blending: THREE.AdditiveBlending,
  });
  dissolveMaterial.name = "visitor-left-silhouette-dissolve";
  const dissolve = new THREE.Points(dissolveGeometry, dissolveMaterial);
  dissolve.name = "visitor-mesh-derived-dissolution";
  dissolve.renderOrder = 3;
  surface.add(topology, dissolve);

  function update(time, speakingEnergy = 0, headYaw = 0, headPitch = 0, headRoll = 0) {
    const voiceNod = Math.sin(time * 5.4) * speakingEnergy * 0.012;
    topologyMaterial.uniforms.uHeadLook.value.set(headYaw, headPitch + voiceNod, headRoll);
    dissolveMaterial.uniforms.uHeadLook.value.set(headYaw, headPitch + voiceNod, headRoll);
    topologyMaterial.uniforms.uTime.value = time;
    topologyMaterial.uniforms.uEnergy.value = speakingEnergy;
    dissolveMaterial.uniforms.uTime.value = time;
    dissolveMaterial.uniforms.uEnergy.value = speakingEnergy;
    dissolveMaterial.uniforms.uPixelRatio.value = Math.min(window.devicePixelRatio || 1, 1.5);
  }

  return { surface, topology, dissolve, update };
}

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
  aura.addColorStop(0, "rgba(167,139,250,.14)");
  aura.addColorStop(0.5, "rgba(139,92,246,.055)");
  aura.addColorStop(1, "rgba(91,33,182,0)");
  ctx.fillStyle = aura;
  ctx.fillRect(0, 0, width, height);

  ctx.lineWidth = 1;
  for (let ring = 1; ring <= 4; ring += 1) {
    ctx.strokeStyle = `rgba(167,139,250,${0.16 - ring * 0.022})`;
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
    ctx.strokeStyle = "rgba(167,139,250,.12)";
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.fillStyle = index % 3 ? "rgba(167,139,250,.9)" : "rgba(216, 180, 254,.95)";
    ctx.shadowColor = "#a78bfa";
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
  ctx.strokeStyle = "rgba(216, 180, 254,.26)";
  ctx.beginPath();
  ctx.moveTo(centerX - span * 0.38, centerY);
  ctx.quadraticCurveTo(centerX - span * 0.18, centerY - span * 0.11, centerX, centerY);
  ctx.stroke();
  ctx.fillStyle = `rgba(207,250,254,${0.25 + writeProgress * 0.65})`;
  ctx.shadowColor = "#a855f7";
  ctx.shadowBlur = 18;
  ctx.fillRect(writeX - 7, writeY - 4, 14, 8);
  ctx.shadowBlur = 0;

  ctx.fillStyle = "rgba(167,139,250,.95)";
  ctx.shadowColor = "#a78bfa";
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
  ctx.fillStyle = "rgba(221,214,254,.45)";
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
  aura.addColorStop(0, `rgba(168, 85, 247,${0.13 + assembly * 0.08})`);
  aura.addColorStop(0.48, "rgba(192,132,252,.045)");
  aura.addColorStop(1, "rgba(109,40,217,0)");
  ctx.fillStyle = aura;
  ctx.fillRect(0, 0, width, height);

  for (let ring = 1; ring <= 3; ring += 1) {
    const radius = ring * span * 0.09;
    ctx.strokeStyle = ring === 2 ? "rgba(168, 85, 247,.2)" : "rgba(168,85,247,.12)";
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
    ctx.strokeStyle = index % 3 ? "rgba(168,85,247,.11)" : "rgba(168, 85, 247,.18)";
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(component.phase + time * (0.18 + index % 3 * 0.04));
    ctx.strokeStyle = index % 3 ? `rgba(233,213,255,${0.34 + assembly * 0.38})` : `rgba(216,180,254,${0.4 + assembly * 0.4})`;
    ctx.fillStyle = index % 3 ? "rgba(109,40,217,.12)" : "rgba(168,85,247,.13)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(-component.size, -component.size * 0.55, component.size * 2, component.size * 1.1, 2);
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  });

  const coreRadius = 12 + assembly * 14;
  const glow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, coreRadius * 2.4);
  glow.addColorStop(0, `rgba(243,232,255,${0.7 + assembly * 0.24})`);
  glow.addColorStop(0.42, `rgba(168, 85, 247,${0.24 + assembly * 0.18})`);
  glow.addColorStop(1, "rgba(192,132,252,0)");
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(centerX, centerY, coreRadius * 2.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "rgba(255,255,255,.9)";
  ctx.beginPath();
  ctx.arc(centerX, centerY, coreRadius * 0.35, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "rgba(168,85,247,.5)";
  ctx.strokeRect(centerX - span * 0.105, centerY - span * 0.06, span * 0.21, span * 0.12);
  ctx.fillStyle = "rgba(233,213,255,.75)";
  ctx.font = "700 9px ui-monospace, Menlo, monospace";
  ctx.textAlign = "center";
  ctx.fillText("FORJA · CONSTRUÇÃO EM CURSO", centerX, centerY + span * 0.28);
  ["ANALISAR", "MONTAR", "TESTAR", "ENTREGAR"].forEach((label, index) => {
    const angle = -Math.PI * 0.8 + index * Math.PI * 0.53;
    const x = centerX + Math.cos(angle) * span * 0.27;
    const y = centerY + Math.sin(angle) * span * 0.25;
    ctx.fillStyle = index <= Math.floor(assembly * 4) ? "rgba(233,213,255,.72)" : "rgba(233,213,255,.38)";
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
    color: 0x120825,
    roughness: 0.16,
    transmission: 0.34,
    thickness: 1.2,
    ior: 1.46,
    clearcoat: 0.9,
    emissive: 0x3b1675,
    emissiveIntensity: 0.32,
    transparent: true,
    opacity: 0,
    flatShading: true,
  });
  const coreGeometry = new THREE.IcosahedronGeometry(0.84, 1);
  const core = new THREE.Mesh(coreGeometry, obsidianMaterial);
  group.add(core);

  const soulMaterial = new THREE.MeshBasicMaterial({
    color: 0xc084fc,
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
    color: 0xc084fc,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const shardCount = reducedMotion ? 6 : 10;
  const shards = Array.from({ length: shardCount }, (_, index) => {
    const shard = new THREE.Mesh(new THREE.SphereGeometry(0.055 + index % 3 * 0.012, 10, 8), shardMaterial);
    const y = 1 - index / Math.max(1, shardCount - 1) * 2;
    const radius = Math.sqrt(Math.max(0, 1 - y * y));
    const angle = index * 2.399963;
    shard.userData.direction = new THREE.Vector3(Math.cos(angle) * radius, y * 0.76, Math.sin(angle) * radius);
    group.add(shard);
    return shard;
  });

  let alpha = 0;
  function update(time, visibility, deltaSeconds = 0) {
    const transitionEase = 1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 1.8);
    alpha += (Math.max(0, Math.min(1, visibility)) - alpha) * transitionEase;
    group.visible = alpha > 0.01;
    if (!group.visible) return;
    const pulse = 0.5 + 0.5 * Math.sin(time * 2.2);
    obsidianMaterial.opacity = alpha * 0.58;
    obsidianMaterial.emissiveIntensity = alpha * (0.28 + pulse * 0.2);
    soulMaterial.opacity = alpha * (0.44 + pulse * 0.28);
    wireMaterial.opacity = alpha * (0.08 + pulse * 0.045);
    shardMaterial.opacity = alpha * (0.2 + pulse * 0.16);
    core.rotation.y += deltaSeconds * 0.1;
    core.rotation.x += deltaSeconds * 0.035;
    soul.rotation.y -= deltaSeconds * 0.15;
    containment.rotation.y -= deltaSeconds * 0.065;
    containment.rotation.z += deltaSeconds * 0.025;
    shards.forEach((shard, index) => {
      const distance = 1.36 + pulse * 0.12 + index % 4 * 0.045;
      shard.position.copy(shard.userData.direction).multiplyScalar(distance);
      shard.rotation.x += deltaSeconds * (0.1 + index % 3 * 0.018);
      shard.rotation.y -= deltaSeconds * 0.085;
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
        vec3 jarvisUltronRed = vec3(jarvisEnergy * 1.3, jarvisEnergy * 0.08, jarvisEnergy * 0.055);
        outgoingLight = mix(outgoingLight, jarvisUltronRed, jarvisAccentMask * 0.96);
        #include <opaque_fragment>
      `,
    );
  };
  material.customProgramCacheKey = () => "ultron-red-identity-v1";
  material.needsUpdate = true;
}

async function start() {
  const renderer = new THREE.WebGLRenderer({
    alpha: true,
    antialias: true,
    powerPreference: "high-performance",
    preserveDrawingBuffer: false,
  });
  renderer.domElement.style.position = "absolute";
  renderer.domElement.style.inset = "0";
  renderer.domElement.style.zIndex = "1";
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, QUALITY_PROFILES[graphicsQuality].pixelRatio));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.16;
  mount.appendChild(renderer.domElement);

  const effectCanvas = makeEffectCanvas();
  const effectContext = effectCanvas.getContext("2d");
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  camera.position.set(0, 0.02, 5.1);

  const ambient = new THREE.AmbientLight(0x2b174d, 1.04);
  scene.add(ambient);
  const key = new THREE.DirectionalLight(0xb899ff, 3.1);
  key.position.set(2.6, 3.4, 4.2);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x6d5cff, 2.45);
  rim.position.set(-3, 1.3, -2);
  scene.add(rim);
  const faceFill = new THREE.PointLight(0xdacfff, 8.2, 7, 1.7);
  faceFill.position.set(0.15, 0.45, 3.1);
  scene.add(faceFill);
  const lowerFill = new THREE.PointLight(0x8b5cf6, 4.8, 6, 2);
  lowerFill.position.set(-1.2, -1.8, 2.4);
  scene.add(lowerFill);
  const coreEntity = makeCoreEntity(scene);

  const root = new THREE.Group();
  scene.add(root);
  const [visitorModel, topologyGeometry] = await Promise.all([
    loadObjHead("/asset/models/male_head.obj?v=20260813-smartforge1"),
    loadObjGeometry("/asset/models/male_head_topology.obj?v=20260813-smartforge1"),
  ]);
  const visitorHeadLook = installVisitorHeadPose(visitorModel.material);
  let ownerModel = new THREE.Group();
  let ownerMixer = null;
  let ownerLoadPromise = null;

  function normalizeModel(model, rotationX = 0, rotationY = 0, rotationZ = 0, targetSize = 1.72) {
    model.rotation.set(rotationX, rotationY, rotationZ);
    model.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const scale = targetSize / (Math.max(size.x, size.y, size.z) || 1);
    model.scale.setScalar(scale);
    model.position.set(-center.x * scale, -center.y * scale - 0.02, -center.z * scale);
    root.add(model);
  }
  // The OBJ is Z-up with its face toward negative Y. Converting that axis to
  // Three.js Y-up makes the eyes and face point directly at the camera.
  normalizeModel(visitorModel, -Math.PI / 2, 0, 0, 1.5);
  const visitorLife = makeVisitorLife(topologyGeometry);
  normalizeModel(visitorLife.surface, -Math.PI / 2, 0, 0, 1.5);

  const glowMaterials = new Set();
  function prepareOwnerModel(model) {
    model.traverse((object) => {
      if (!object.isMesh) return;
      object.frustumCulled = true;
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      const identity = `${object.name} ${object.parent?.name || ""} ${materials.map((material) => material?.name || "").join(" ")}`;
      if (/sketchfab.*particles|particle.*plane/i.test(identity)) {
        object.visible = false;
        object.userData.jarvisSuppressedEffect = true;
        return;
      }
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
  }

  async function loadOwnerModel() {
    if (ownerLoadPromise) return ownerLoadPromise;
    stage.dataset.ownerModel = "loading";
    ownerLoadPromise = new Promise((resolve, reject) => {
      new GLTFLoader().load("/asset/models/jarvis-humanoid.glb?v=20260807-voicecyan1", resolve, undefined, reject);
    }).then((alienGltf) => {
      ownerModel = alienGltf.scene || alienGltf.scenes[0];
      normalizeModel(ownerModel);
      prepareOwnerModel(ownerModel);
      ownerMixer = alienGltf.animations.length ? new THREE.AnimationMixer(ownerModel) : null;
      if (ownerMixer && !reducedMotion) {
        const action = ownerMixer.clipAction(alienGltf.animations[0]);
        action.play();
        action.paused = true;
        ownerMixer.setTime(0.04);
      }
      ownerModel.visible = stage.dataset.access === "owner";
      stage.dataset.ownerModel = "ready";
      stage.dataset.modelAnimations = String(alienGltf.animations.length);
      stage.dataset.modelAnimationSeconds = alienGltf.animations[0]?.duration?.toFixed(1) || "0";
      return ownerModel;
    }).catch((error) => {
      stage.dataset.ownerModel = "error";
      ownerLoadPromise = null;
      throw error;
    });
    return ownerLoadPromise;
  }

  stage.dataset.modelAsset = "visitor-purple-bust";
  stage.dataset.modelAnimations = "lazy-owner";
  stage.dataset.renderProfile = `quality-${graphicsQuality}`;

  const particleCount = 20;
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
  let currentZ = 0;
  let voiceEnergy = 0;
  let targetVoiceEnergy = 0;
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

  const onVoiceLevel = (event) => {
    const level = Number(event.detail?.level);
    if (!Number.isFinite(level)) return;
    targetVoiceEnergy = Math.max(0, Math.min(1, level));
  };
  window.addEventListener("jarvis-voice-level", onVoiceLevel);

  let canvasWidth = 1;
  let canvasHeight = 1;
  function resize() {
    const rect = mount.getBoundingClientRect();
    canvasWidth = Math.max(rect.width, 1);
    canvasHeight = Math.max(rect.height, 1);
    camera.aspect = canvasWidth / canvasHeight;
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, QUALITY_PROFILES[graphicsQuality].pixelRatio));
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
  presenceValue.textContent = "Busto visitante roxo · volume facial · malha sutil";

  let previousFrameMs = performance.now();
  let effectVisible = false;
  let currentScale = 1;
  let sampledFrames = 0;
  let fpsWindowStart = performance.now();
  let frameIntervalMs = 1000 / QUALITY_PROFILES[graphicsQuality].activeFps;
  let lastVisualMode = "";
  let effectLastFrameMs = 0;
  let windowFocused = document.hasFocus();
  let animationFrameId = 0;
  let animationTimerId = 0;
  let disposed = false;
  let lastRenderTargetFps = 0;
  let lastRenderProfile = "";
  const modeBlend = { core: 0, forge: 0, memory: 0 };

  const activeStates = new Set(["listening", "thinking", "planning", "research", "forge", "speaking", "preview", "memory", "local"]);
  function requestedTargetFps() {
    if (!windowFocused || document.hidden) return 0;
    const profile = QUALITY_PROFILES[graphicsQuality];
    return activeStates.has(visualState) ? profile.activeFps : profile.idleFps;
  }

  function updateRenderBudget() {
    const targetFps = requestedTargetFps();
    if (targetFps > 0) frameIntervalMs = 1000 / targetFps;
    const profile = targetFps === 0
      ? "paused"
      : `${graphicsQuality}-${activeStates.has(visualState) ? "active" : "idle"}-${targetFps}fps`;
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
    window.clearTimeout(animationTimerId);
    cancelAnimationFrame(animationFrameId);
    updateRenderBudget();
  });
  updateRenderBudget();

  window.addEventListener("jarvis-graphics-quality", (event) => {
    const requested = event.detail?.quality;
    if (!QUALITY_PROFILES[requested]) return;
    graphicsQuality = requested;
    resize();
    updateRenderBudget();
    scheduleRender(0);
  });

  function scheduleRender(delay = frameIntervalMs) {
    if (disposed || !windowFocused || document.hidden) return;
    window.clearTimeout(animationTimerId);
    animationTimerId = window.setTimeout(() => {
      animationFrameId = requestAnimationFrame(render);
    }, reducedMotion ? 0 : Math.max(0, delay));
  }

  function wakeRender() {
    previousFrameMs = 0;
    scheduleRender(0);
  }

  function syncAccessModel() {
    const ownerAccess = stage.dataset.access === "owner";
    visitorModel.visible = !ownerAccess;
    visitorLife.surface.visible = !ownerAccess;
    if (ownerAccess) {
      presenceValue.textContent = "Busto Ultron carregando";
      if (ownerLoadPromise) {
        loadOwnerModel()
          .then(() => {
            presenceValue.textContent = "Busto Ultron · acesso privado";
            wakeRender();
          })
          .catch(() => {
            presenceValue.textContent = "Busto Ultron indisponível";
          });
      } else {
        window.setTimeout(() => {
          loadOwnerModel()
            .then(() => {
              presenceValue.textContent = "Busto Ultron · acesso privado";
              wakeRender();
            })
            .catch(() => {
              presenceValue.textContent = "Busto Ultron indisponível";
            });
        }, 0);
      }
    } else {
      ownerModel.visible = false;
      presenceValue.textContent = "Busto visitante roxo · volume facial · malha sutil";
      wakeRender();
    }
  }
  const accessObserver = new MutationObserver(syncAccessModel);
  accessObserver.observe(stage, { attributes: true, attributeFilter: ["data-access"] });
  syncAccessModel();

  window.addEventListener("jarvis-state", wakeRender);
  const onVisibilityChange = () => {
    if (document.hidden) {
      window.clearTimeout(animationTimerId);
      cancelAnimationFrame(animationFrameId);
      updateRenderBudget();
    } else if (windowFocused) {
      wakeRender();
    }
  };
  document.addEventListener("visibilitychange", onVisibilityChange);

  function render(timeMs) {
    if (disposed) return;
    updateRenderBudget();
    if (document.hidden || !windowFocused) {
      previousFrameMs = timeMs;
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
    const isOwner = stage.dataset.access === "owner";
    visitorModel.visible = !isOwner;
    visitorLife.surface.visible = !isOwner;
    ownerModel.visible = isOwner;
    ambient.color.setHex(isOwner ? 0x33070b : 0x2b174d);
    key.color.setHex(isOwner ? 0xffb4b4 : 0xb899ff);
    rim.color.setHex(isOwner ? 0xdc2626 : 0x6d5cff);
    faceFill.color.setHex(isOwner ? 0xffe0e0 : 0xdacfff);
    lowerFill.color.setHex(isOwner ? 0xb91c1c : 0x8b5cf6);
    const activeColor = isOwner ? OWNER_RED : (COLORS[visualState] || COLORS.idle);
    const isWorking = modeBlend.forge > 0.08;
    targetColor.setHex(activeColor);
    const colorEase = 1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 1.8);
    currentColor.lerp(targetColor, colorEase);
    particleMaterial.color.copy(currentColor);
    glowMaterials.forEach((material) => {
      material.emissive.copy(material.userData.jarvisBaseEmissive).lerp(currentColor, 0.28);
      material.emissiveIntensity = material.userData.jarvisBaseIntensity * (isWorking ? 1.28 : visualState === "speaking" ? 1.18 : 1);
    });
    if (ownerMixer) ownerMixer.update(deltaSeconds);

    const orientationEase = 1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 9.2);
    currentX += (pointerX * 0.15 - currentX) * orientationEase;
    currentY += (pointerY * 0.08 - currentY) * orientationEase;
    currentZ += (-pointerX * 0.025 - currentZ) * orientationEase;
    voiceEnergy += (targetVoiceEnergy - voiceEnergy) * (1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 8));
    const cameraTargetX = 0;
    const cameraTargetZ = 5.02 + modeBlend.memory * 0.18 + modeBlend.forge * 0.12 + modeBlend.core * 0.08;
    const cameraEase = 1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 1.2);
    camera.position.x += (cameraTargetX - camera.position.x) * cameraEase;
    camera.position.z += (cameraTargetZ - camera.position.z) * cameraEase;
    camera.lookAt(0, -0.01, 0);
    const spatialResult = stage.classList.contains("spatial-result") && canvasWidth > 900 ? 1 : 0;
    const modeTargetX = -modeBlend.memory * 0.34 - modeBlend.forge * 0.3 - modeBlend.core * 0.18;
    const targetPositionX = spatialResult ? -1.35 : modeTargetX;
    const positionEase = 1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 1.35);
    root.position.x += (targetPositionX - root.position.x) * positionEase;
    root.position.y = -0.07 + Math.sin(time * 0.28) * 0.006;
    const facingYaw = Math.atan2(camera.position.x - root.position.x, camera.position.z - root.position.z);
    root.rotation.y = facingYaw + Math.sin(time * 0.14) * 0.005;
    root.rotation.x = Math.sin(time * 0.17) * 0.0015;
    root.rotation.z = 0;
    const liveSpeakingEnergy = visualState === "speaking" ? voiceEnergy : 0;
    const voiceNod = Math.sin(time * 5.4) * liveSpeakingEnergy * 0.012;
    const inwardGaze = spatialResult * 0.11;
    visitorHeadLook.value.set(currentX + inwardGaze, currentY + voiceNod, currentZ);
    const speakingPulse = liveSpeakingEnergy * 0.055;
    const targetScale = 1 - modeBlend.memory * 0.07 - modeBlend.forge * 0.045 - modeBlend.core * 0.025 + speakingPulse * 0.035;
    currentScale += (targetScale - currentScale) * (1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 1.8));
    root.scale.setScalar(currentScale);
    visitorLife.update(time, liveSpeakingEnergy, currentX + inwardGaze, currentY, currentZ);
    particleMaterial.opacity = isWorking ? 0.27 : 0.16 + speakingPulse * 0.22;
    particles.rotation.y += deltaSeconds * (isWorking ? 0.022 : 0.008);
    coreEntity.update(time, modeBlend.core, deltaSeconds);

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
    if (stage.dataset.renderTriangles !== String(renderer.info.render.triangles)) {
      stage.dataset.renderTriangles = String(renderer.info.render.triangles);
    }
    if (!reducedMotion) scheduleRender(frameIntervalMs);
  }

  render(performance.now());

  window.addEventListener("pagehide", (event) => {
    if (event.persisted) return;
    disposed = true;
    window.clearTimeout(animationTimerId);
    cancelAnimationFrame(animationFrameId);
    window.removeEventListener("jarvis-state", wakeRender);
    window.removeEventListener("jarvis-voice-level", onVoiceLevel);
    document.removeEventListener("visibilitychange", onVisibilityChange);
    resizeObserver.disconnect();
    accessObserver.disconnect();
    ownerMixer?.stopAllAction();
    const disposedTextures = new Set();
    [visitorModel, visitorLife.surface, ownerModel].forEach((model) => {
      model.traverse((object) => {
        if (!(object.isMesh || object.isLineSegments || object.isPoints)) return;
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
