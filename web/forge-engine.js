// FORJA 3D — port do engine antigo da Forja (08_REFERENCIAS/TELA_PRINCIPAL_3D_PACK/
// engines/04_forge_engine.js, canvas 2D) para o runtime atual (three r160, ES module).
// Essência portada do original: scaffold hexagonal em blueprint girando, vigas de
// construção + 26 estilhaços convergindo com respiração de montagem, anel de
// contenção girando, núcleo em formação e faíscas subindo. O bônus do port: o
// boneco antigo (jarvis-humanoid.glb, o mesmo GLB do pack) é a peça sendo forjada
// dentro da gaiola, materializando junto com a convergência.
// Tudo vive em unidades locais onde "1" é o R do canvas antigo (min(w,h) de 520px);
// o grupo inteiro escala pela altura visível da câmera.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "./vendor/draco/DRACOLoader.js";

const SHARD_COUNT = 26;
const SPARK_COUNT = 40;
const RING_COUNT = 4;
// Altura do boneco forjado em unidades R (metade do diâmetro do anel externo).
const FORGED_MODEL_SIZE = 0.52;
// Fração da altura visível que a Forja ocupa (raio máximo dos estilhaços: 0.62R).
const FORGE_VIEW_FRACTION = 0.58;
const PALETTE = {
  jarvis: { shard: 0xce8cff, scaffold: 0xc06bff, containment: 0xdcb4ff, soul: 0xebcdff, spark: 0xffe6ff, emissive: 0x2a1454, model: 0x130a2c, light: 0xc084fc },
  ultron: { shard: 0xfca5a5, scaffold: 0xef4444, containment: 0xfca5a5, soul: 0xffe0e0, spark: 0xffe0e0, emissive: 0x7f1d1d, model: 0x2c0a0a, light: 0xff6b6b },
};
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

function loadGltf(loader, url) {
  return new Promise((resolve, reject) => loader.load(url, resolve, undefined, reject));
}

// Mesmos paths do dono (jarvis-3d.js): mesmo arquivo em cache de HTTP, decode Draco
// com fallback pro glb original quando o worker/WASM está bloqueado por CSP.
async function loadForgedModel() {
  const dracoLoader = new DRACOLoader().setDecoderPath("/ui/vendor/draco/");
  try {
    return await loadGltf(new GLTFLoader().setDRACOLoader(dracoLoader), "/asset/models/jarvis-humanoid.draco.glb?v=20261016-draco1");
  } catch {
    return loadGltf(new GLTFLoader(), "/asset/models/jarvis-humanoid.glb?v=20260807-voicecyan1");
  } finally {
    dracoLoader.dispose();
  }
}

function makeGlowTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const context = canvas.getContext("2d");
  const gradient = context.createRadialGradient(32, 32, 0, 32, 32, 32);
  gradient.addColorStop(0, "rgba(255,255,255,.95)");
  gradient.addColorStop(0.35, "rgba(235,205,255,.55)");
  gradient.addColorStop(0.7, "rgba(192,107,255,.16)");
  gradient.addColorStop(1, "rgba(192,107,255,0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, 64, 64);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export function makeForgeEntity(scene, options = {}) {
  const camera = options.camera || null;
  const anchorX = options.anchorX ?? 0.66;
  const anchorY = options.anchorY ?? 0.43;

  const group = new THREE.Group();
  group.visible = false;
  scene.add(group);

  let disposed = false;
  let loading = false;
  let ready = false;
  let failed = false;
  let modelReady = false;

  // Referências construídas no init (lazy): nada de geometria antes do modo acender.
  let scaffoldRings = null;
  let scaffoldMaterial = null;
  let containment = null;
  let containmentMaterial = null;
  let shards = null;
  let shardGroup = null;
  let shardMaterial = null;
  let beams = null;
  let beamMaterial = null;
  let core = null;
  let coreMaterial = null;
  let soul = null;
  let soulMaterial = null;
  let glow = null;
  let glowMaterial = null;
  let sparks = null;
  let sparkMaterial = null;
  let sparkData = null;
  let corePoint = null;
  let forgedModel = null;
  let forgedWireframes = null;
  let forgedMaterial = null;
  let forgedWireMaterial = null;
  let glowTexture = null;

  let alpha = 0;

  const shardSeeds = Array.from({ length: SHARD_COUNT }, (_, index) => ({
    a: Math.random() * Math.PI * 2,
    // Mesmas faixas do engine antigo: raio orbital 0.42–0.62R, tamanho 6–20px→0.011–0.038R.
    r0: 0.42 + Math.random() * 0.2,
    ph: Math.random() * Math.PI * 2,
    size: 1 + (6 + Math.random() * 14) / 8.6,
    tumble: 0.4 + ((index * 37) % 11) / 11,
  }));
  sparkData = Array.from({ length: SPARK_COUNT }, () => ({
    a: Math.random() * Math.PI * 2,
    r: Math.random(),
    sp: 0.3 + Math.random() * 0.7,
  }));

  function hexGeometry() {
    const points = [];
    for (let side = 0; side < 6; side += 1) {
      const angle = (side / 6) * Math.PI * 2;
      points.push(new THREE.Vector3(Math.cos(angle), Math.sin(angle), 0));
    }
    return new THREE.BufferGeometry().setFromPoints(points);
  }

  function buildProcedural() {
    // Blueprint: 4 anéis hexagonais concêntricos (raio ring*0.085*1.15R no original),
    // achatados em y (o 0.86 do canvas 2D) para ler como o scaffold de planta baixa.
    scaffoldMaterial = new THREE.LineBasicMaterial({
      color: PALETTE.jarvis.scaffold,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    scaffoldRings = [];
    for (let ring = 1; ring <= RING_COUNT; ring += 1) {
      const pivot = new THREE.Group();
      pivot.scale.y = 0.86;
      const hex = new THREE.LineLoop(hexGeometry(), scaffoldMaterial);
      hex.scale.setScalar(ring * 0.085 * 1.15);
      hex.rotation.z = ring * 0.2;
      pivot.add(hex);
      group.add(pivot);
      scaffoldRings.push({ pivot, hex, ring });
    }

    // Anel de contenção girando (círculo de 64 pontos no lugar dos 48 do 2D).
    const containmentPoints = [];
    for (let side = 0; side < 64; side += 1) {
      const angle = (side / 64) * Math.PI * 2;
      containmentPoints.push(new THREE.Vector3(Math.cos(angle), Math.sin(angle), 0));
    }
    containmentMaterial = new THREE.LineBasicMaterial({
      color: PALETTE.jarvis.containment,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    containment = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(containmentPoints), containmentMaterial);
    containment.scale.y = 0.86;
    group.add(containment);

    // Estilhaços: octaedros facetados (o triangulozinho 2D ganhou profundidade).
    shardGroup = new THREE.Group();
    shardGroup.scale.y = 0.86;
    shardMaterial = new THREE.MeshStandardMaterial({
      color: 0x161031,
      metalness: 0.1,
      roughness: 0.22,
      emissive: PALETTE.jarvis.emissive,
      emissiveIntensity: 0.25,
      flatShading: true,
      transparent: true,
      opacity: 0,
    });
    const shardGeometry = new THREE.OctahedronGeometry(0.012, 0);
    shards = shardSeeds.map((seed) => {
      const shard = new THREE.Mesh(shardGeometry, shardMaterial);
      shard.scale.setScalar(seed.size);
      shard.rotation.z = seed.ph;
      shard.frustumCulled = false;
      shardGroup.add(shard);
      return shard;
    });
    group.add(shardGroup);

    // Vigas de construção: centro → estilhaço, um LineSegments atualizado por frame.
    const beamPositions = new Float32Array(SHARD_COUNT * 2 * 3);
    const beamGeometry = new THREE.BufferGeometry();
    beamGeometry.setAttribute("position", new THREE.BufferAttribute(beamPositions, 3));
    beamMaterial = new THREE.LineBasicMaterial({
      color: PALETTE.jarvis.scaffold,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    beams = new THREE.LineSegments(beamGeometry, beamMaterial);
    beams.frustumCulled = false;
    group.add(beams);

    // Núcleo em formação: cristal de obsidiana + alma aditiva + brilho, a essência
    // do coração do engine do Core (02_core_engine.js) no lugar do gradiente 2D.
    coreMaterial = new THREE.MeshPhysicalMaterial({
      color: 0x120d22,
      metalness: 0,
      roughness: 0.15,
      clearcoat: 1,
      clearcoatRoughness: 0.15,
      emissive: PALETTE.jarvis.emissive,
      emissiveIntensity: 0.2,
      flatShading: true,
      transparent: true,
      opacity: 0,
    });
    core = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 1), coreMaterial);
    core.position.z = 0.32;
    group.add(core);

    soulMaterial = new THREE.MeshBasicMaterial({
      color: PALETTE.jarvis.soul,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    soul = new THREE.Mesh(new THREE.IcosahedronGeometry(0.45, 0), soulMaterial);
    soul.position.z = 0.32;
    group.add(soul);

    glowTexture = makeGlowTexture();
    glowMaterial = new THREE.SpriteMaterial({
      map: glowTexture,
      color: PALETTE.jarvis.soul,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    glow = new THREE.Sprite(glowMaterial);
    glow.position.z = 0.34;
    group.add(glow);

    // Faíscas de montagem subindo pro núcleo; o fade (1-r) do 2D vira vertex color
    // porque blending aditivo escurecendo = sumindo.
    const sparkPositions = new Float32Array(SPARK_COUNT * 3);
    const sparkColors = new Float32Array(SPARK_COUNT * 3);
    const sparkGeometry = new THREE.BufferGeometry();
    sparkGeometry.setAttribute("position", new THREE.BufferAttribute(sparkPositions, 3));
    sparkGeometry.setAttribute("color", new THREE.BufferAttribute(sparkColors, 3));
    sparkMaterial = new THREE.PointsMaterial({
      color: PALETTE.jarvis.spark,
      size: 0.02,
      vertexColors: true,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    sparks = new THREE.Points(sparkGeometry, sparkMaterial);
    sparks.frustumCulled = false;
    group.add(sparks);

    // Luz do coração: acende a peça forjada junto com a convergência.
    corePoint = new THREE.PointLight(PALETTE.jarvis.light, 0, 9, 2);
    corePoint.position.z = 0.9;
    group.add(corePoint);
  }

  function attachForgedModel(gltf) {
    const model = gltf.scene || gltf.scenes[0];
    forgedMaterial = new THREE.MeshStandardMaterial({
      color: 0x070612,
      metalness: 0.58,
      roughness: 0.36,
      emissive: PALETTE.jarvis.model,
      emissiveIntensity: 0.14,
      transparent: true,
      opacity: 0,
    });
    forgedWireMaterial = new THREE.MeshBasicMaterial({
      color: PALETTE.jarvis.scaffold,
      wireframe: true,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    // Snapshot primeiro: adicionar o wire durante o traverse faria o three
    // visitar o próprio wire (filhos novos entram na iteração).
    const meshes = [];
    model.traverse((object) => {
      if (object.isMesh && object.geometry) meshes.push(object);
    });
    meshes.forEach((object, meshIndex) => {
      object.material = forgedMaterial;
      object.castShadow = false;
      object.receiveShadow = false;
      // Overlay wireframe estilo blueprint, como o avatar engine antigo fazia
      // (atalho: teto de 24 overlays; geometria extra não cresce sem limite).
      if (meshIndex < 24) {
        const wire = new THREE.Mesh(object.geometry, forgedWireMaterial);
        wire.scale.setScalar(1.004);
        object.add(wire);
        forgedWireframes.push(wire);
      }
    });
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const scale = FORGED_MODEL_SIZE / (Math.max(size.x, size.y, size.z) || 1);
    model.scale.setScalar(scale);
    model.position.set(-center.x * scale, -center.y * scale - 0.02, -center.z * scale);
    model.visible = true;
    forgedModel = model;
    group.add(model);
    modelReady = true;
  }

  async function init() {
    buildProcedural();
    ready = true;
    // O GLB entra por fora: se falhar (offline, CSP, 404), a forja procedural
    // continua sozinha — igual ao engine antigo, que nunca dependeu de asset.
    forgedWireframes = [];
    try {
      const gltf = await loadForgedModel();
      if (!disposed) attachForgedModel(gltf);
    } catch (error) {
      console.warn("[forge-engine] GLB da forja indisponível, scaffold puro:", error?.message || error);
    }
  }

  function ensureLoaded() {
    // failed entra na guarda: falhou uma vez, não martela o servidor todo frame.
    if (ready || loading || failed || disposed) return;
    loading = true;
    init()
      .catch((error) => {
        console.warn("[forge-engine] inicialização falhou:", error);
        failed = true;
      })
      .finally(() => {
        loading = false;
      });
  }

  function update(time, intensity, deltaSeconds = 0) {
    if (disposed || failed) return;
    const ease = 1 - Math.exp(-Math.max(deltaSeconds, 0.016) * 1.65);
    alpha += (Math.max(0, Math.min(1, intensity)) - alpha) * ease;
    // Pausa real: modo saiu e o fade terminou → nada anima, nada desenha.
    if (alpha <= 0.004 && intensity <= 0.004) {
      group.visible = false;
      return;
    }
    if (!ready) return;
    group.visible = true;

    // Âncora em fração de tela (o overlay 2D desenha em 0.66/0.62 da largura e
    // 0.43 da altura): um unproject por frame é barato e segue a câmera com zoom.
    if (camera) {
      camera.updateMatrixWorld();
      const viewHeight = 2 * Math.tan((camera.fov * Math.PI) / 180 / 2) * camera.position.z;
      const viewWidth = viewHeight * camera.aspect;
      group.position.x = (anchorX - 0.5) * viewWidth;
      group.position.y = (0.5 - anchorY) * viewHeight;
      group.scale.setScalar(viewHeight * FORGE_VIEW_FRACTION);
    }

    // Estado do dono: persona ultron pinta a forja inteira de vermelho.
    const ultron = document.documentElement.dataset.persona === "ultron";
    const palette = ultron ? PALETTE.ultron : PALETTE.jarvis;

    // Respiração de montagem do engine antigo; working acelerava 2.2x — aqui o
    // modo ativo (intensity→1) leva o speed ao mesmo 2.2.
    const speed = 1 + alpha * 1.2;
    const conv = reducedMotion ? 0.55 : 0.5 + 0.5 * Math.sin(time * 0.5 * speed);

    scaffoldMaterial.color.setHex(palette.scaffold);
    scaffoldMaterial.opacity = alpha * 0.15;
    scaffoldRings.forEach(({ hex, ring }) => {
      if (!reducedMotion) hex.rotation.z = time * 0.08 * ring * speed + ring * 0.2;
    });

    containmentMaterial.color.setHex(palette.containment);
    containmentMaterial.opacity = alpha * (0.18 + conv * 0.22);
    const containmentRadius = 0.16 + conv * 0.03;
    containment.scale.set(containmentRadius, containmentRadius * 0.86, 1);
    if (!reducedMotion) containment.rotation.z = time * 0.5 * speed;

    shardMaterial.emissive.setHex(palette.emissive);
    shardMaterial.opacity = alpha * (0.3 + conv * 0.45);
    // Convergência: r = r0*(0.40+0.60*(1-conv)) — no pico da respiração os
    // estilhaços encostam no centro e o núcleo se forma.
    const converge = 0.4 + 0.6 * (1 - conv);
    const beamPositions = beams.geometry.getAttribute("position");
    shardSeeds.forEach((seed, index) => {
      const shard = shards[index];
      const radius = seed.r0 * converge;
      const angle = seed.a + time * 0.12 * speed;
      shard.position.set(
        Math.cos(angle) * radius,
        Math.sin(angle) * radius,
        Math.sin(seed.ph * 2 + time * 0.25 * speed) * 0.14,
      );
      shard.rotation.z = seed.ph + time * speed * 0.6;
      if (!reducedMotion) {
        shard.rotation.x += deltaSeconds * seed.tumble * 0.5;
        shard.rotation.y += deltaSeconds * seed.tumble * 0.3;
      }
      beamPositions.setXYZ(index * 2, 0, 0, 0);
      // As vigas moram fora do grupo achatado: replicar o squash y de 0.86 do shardGroup.
      beamPositions.setXYZ(index * 2 + 1, shard.position.x, shard.position.y * 0.86, shard.position.z);
    });
    beamPositions.needsUpdate = true;
    beamMaterial.color.setHex(palette.scaffold);
    beamMaterial.opacity = alpha * (0.05 + conv * 0.1);

    // Núcleo em formação: brilha e cresce com a convergência.
    const coreScale = 0.055 + conv * 0.075;
    coreMaterial.emissive.setHex(palette.emissive);
    coreMaterial.opacity = alpha * 0.85;
    core.scale.setScalar(coreScale);
    core.rotation.y += deltaSeconds * 0.4 * speed;
    soulMaterial.color.setHex(palette.soul);
    soulMaterial.opacity = alpha * (0.5 + conv * 0.4);
    soul.scale.setScalar(coreScale);
    soul.rotation.y -= deltaSeconds * 0.6 * speed;
    glowMaterial.color.setHex(palette.soul);
    glowMaterial.opacity = alpha * (0.55 + conv * 0.35);
    glow.scale.setScalar((0.05 + conv * 0.11) * 2.2);
    corePoint.color.setHex(palette.light);
    corePoint.intensity = alpha * (0.3 + conv * 1.6);

    // Faíscas caem pro centro e renascem na borda (mesmo loop do original).
    const sparkPositions = sparks.geometry.getAttribute("position");
    const sparkColors = sparks.geometry.getAttribute("color");
    const step = Math.max(deltaSeconds, 0.016) * 60;
    sparkData.forEach((spark, index) => {
      spark.r -= 0.006 * spark.sp * speed * step;
      if (spark.r < 0) {
        spark.r = 1;
        spark.a = Math.random() * Math.PI * 2;
      }
      sparkPositions.setXYZ(
        index,
        Math.cos(spark.a) * spark.r * 0.42,
        Math.sin(spark.a) * spark.r * 0.36,
        0.05,
      );
      const fade = (1 - spark.r) * 0.8 * alpha;
      sparkColors.setXYZ(index, fade, fade, fade);
    });
    sparkPositions.needsUpdate = true;
    sparkColors.needsUpdate = true;
    sparkMaterial.opacity = alpha * 0.9;

    // A peça forjada materializa com a convergência (o boneco antigo dentro da jaula).
    if (forgedModel) {
      forgedMaterial.emissive.setHex(palette.model);
      forgedMaterial.opacity = alpha * (0.35 + conv * 0.65);
      forgedWireMaterial.color.setHex(palette.scaffold);
      forgedWireMaterial.opacity = alpha * (0.06 + conv * 0.12);
      if (!reducedMotion) forgedModel.rotation.y = time * 0.1 * speed;
    }
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    group.traverse((object) => {
      if (!(object.isMesh || object.isLineSegments || object.isLineLoop || object.isPoints || object.isSprite)) return;
      object.geometry?.dispose();
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.filter(Boolean).forEach((material) => {
        if (material.map) material.map.dispose();
        material.dispose();
      });
    });
    glowTexture?.dispose();
    scene.remove(group);
  }

  return {
    group,
    ensureLoaded,
    update,
    dispose,
    get ready() { return ready; },
    get loading() { return loading; },
    get failed() { return failed; },
    get modelReady() { return modelReady; },
    get status() {
      if (failed) return "failed";
      if (loading) return "loading";
      return ready ? (modelReady ? "ready" : "ready-nomodel") : "lazy";
    },
  };
}
