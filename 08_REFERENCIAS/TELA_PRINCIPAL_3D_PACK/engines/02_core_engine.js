/* EXTRACT from cockpit.html — AI-CORE ENGINE (procedural Three.js, no GLB)
 * Lines 1568-1821 of 11_SCRIPTS/jarvis_ui_assets/cockpit.html
 * Mount: #bust3d | Mode tab: Core
 */
     AI-CORE ENGINE · Three.js (module). NO humanoid GLB anymore — the centre is a
     fully procedural entity: a faceted obsidian-crystal heart with a glowing inner
     "soul", wrapped in a Fresnel energy shell (rising holographic scan), suspended
     inside a counter-rotating geodesic containment field, ringed by an orbiting
     fractal shard-burst and a fine particle dust, crossed by an abstract sensor
     visor. There is no face, no head, no body — it reads as a living AI core, not a
     person. idle = dark & contracted · processing = blooms, shards burst outward,
     visor ignites. Any failure → window.__jarvisModelFallback() shows the abstract
     crystal SVG instead. Pure rendering — no app framework, no model file needed.
     ============================================================ -->
<script type="module">
const STATE_COLORS = { idle:0x8a6cff, working:0xc3b0ff, ok:0xaab1ff, error:0xff708d, offline:0x4a4866 };
const EMISSIVE     = { idle:0x150a38, working:0x3a1f7a, ok:0x241a55, error:0x7a1430, offline:0x080518 };
(async () => {
  const mount = document.getElementById("bust3d");
  if (!mount) return;
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion:reduce)").matches;
  try {
    const THREE = await import("three");
    const { RoomEnvironment } = await import("three/addons/environments/RoomEnvironment.js");

    const W = () => mount.clientWidth || 1, H = () => mount.clientHeight || 1;

    const renderer = new THREE.WebGLRenderer({ antialias:true, alpha:true, powerPreference:"high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(W(), H());
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, W()/H(), 0.1, 100);
    camera.position.set(0, 0.12, 7.6);
    camera.lookAt(0, 0, 0);

    // soft neutral reflections so the obsidian doesn't read as flat black
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

    // ---- lighting: cold key · violet rim · weak fill · inner core point ----
    scene.add(new THREE.AmbientLight(0x101018, 0.6));
    scene.add(new THREE.HemisphereLight(0x232844, 0x05040a, 0.5));
    const key  = new THREE.DirectionalLight(0xeaf0ff, 2.2); key.position.set(-2.4, 3.6, 3.2); scene.add(key);
    const rim  = new THREE.DirectionalLight(STATE_COLORS.idle, 3.2); rim.position.set(3.0, 1.6, -2.6); scene.add(rim);
    const fill = new THREE.DirectionalLight(0x4a5480, 0.6); fill.position.set(2.4, -0.6, 2.0); scene.add(fill);
    const corePoint = new THREE.PointLight(STATE_COLORS.idle, 0.4, 9, 2); scene.add(corePoint);

    // the whole entity lives under one group that floats + parallax-rotates
    const root = new THREE.Group(); scene.add(root);

    // ---- obsidian crystal heart (faceted icosahedron, glassy, deep-violet core) ----
    const obsidian = new THREE.MeshPhysicalMaterial({
      color:0x120d22, metalness:0.0, roughness:0.15,
      transmission:0.55, thickness:1.6, ior:1.5,
      attenuationColor:new THREE.Color(0x6a44ff), attenuationDistance:1.5,
      clearcoat:1.0, clearcoatRoughness:0.15,
      emissive:new THREE.Color(EMISSIVE.idle), emissiveIntensity:0.2,
      envMapIntensity:1.3, transparent:true, flatShading:true, side:THREE.DoubleSide
    });
    const coreGeo = new THREE.IcosahedronGeometry(1.2, 1);
    const core = new THREE.Mesh(coreGeo, obsidian); core.rotation.set(0.5, 0.3, 0.1); root.add(core);

    // ---- inner "soul": additive glow seen through the transmissive crystal ----
    const soulMat = new THREE.MeshBasicMaterial({ color:STATE_COLORS.idle, transparent:true, opacity:0.5, blending:THREE.AdditiveBlending, depthWrite:false });
    const soul = new THREE.Mesh(new THREE.IcosahedronGeometry(0.54, 0), soulMat); root.add(soul);

    // ---- Fresnel energy shell (edge bloom + rising holographic scan) ----
    const fresnelMat = new THREE.ShaderMaterial({
      transparent:true, depthWrite:false, side:THREE.FrontSide, blending:THREE.AdditiveBlending,
      uniforms:{
        uColor:{ value:new THREE.Color(STATE_COLORS.idle) },
        uCore:{ value:new THREE.Color(0x0b0718) },
        uPower:{ value:2.6 }, uInt:{ value:0.95 }, uScan:{ value:0.0 }, uTime:{ value:0.0 }
      },
      vertexShader:`
        varying vec3 vN; varying vec3 vV; varying vec3 vW;
        void main(){
          vec4 wp = modelMatrix * vec4(position, 1.0);
          vW = wp.xyz; vN = normalize(mat3(modelMatrix) * normal);
          vV = normalize(cameraPosition - wp.xyz);
          gl_Position = projectionMatrix * viewMatrix * wp;
        }`,
      fragmentShader:`
        varying vec3 vN; varying vec3 vV; varying vec3 vW;
        uniform vec3 uColor, uCore; uniform float uPower, uInt, uScan, uTime;
        void main(){
          float f = pow(1.0 - clamp(dot(normalize(vN), normalize(vV)), 0.0, 1.0), uPower);
          float bands = pow(0.5 + 0.5 * sin(vW.y * 30.0 - uTime * 1.6), 6.0);
          float sweep = smoothstep(0.05, 0.0, abs(fract(vW.y * 0.42 - uTime * 0.12) - 0.5));
          float a = f * uInt + bands * 0.05 * (0.5 + uScan) + sweep * (0.10 + 0.5 * uScan);
          vec3 col = mix(uCore, uColor, clamp(f + sweep * 0.55, 0.0, 1.0));
          gl_FragColor = vec4(col, clamp(a, 0.0, 0.95));
        }`
    });
    const shell = new THREE.Mesh(coreGeo, fresnelMat); shell.scale.setScalar(1.05); root.add(shell);

    // ---- geodesic containment field (two counter-rotating wire shells) ----
    const wireMat  = new THREE.MeshBasicMaterial({ color:0x9a86ff, wireframe:true, transparent:true, opacity:0.10, blending:THREE.AdditiveBlending, depthWrite:false });
    const wire  = new THREE.Mesh(new THREE.IcosahedronGeometry(1.78, 2), wireMat); root.add(wire);
    const wire2Mat = new THREE.MeshBasicMaterial({ color:0x6f5ad6, wireframe:true, transparent:true, opacity:0.05, blending:THREE.AdditiveBlending, depthWrite:false });
    const wire2 = new THREE.Mesh(new THREE.IcosahedronGeometry(2.18, 1), wire2Mat); root.add(wire2);

    // ---- fractal shard burst orbiting the core (fibonacci sphere) ----
    const shardMat = new THREE.MeshPhysicalMaterial({
      color:0x161031, metalness:0.1, roughness:0.22,
      clearcoat:0.8, clearcoatRoughness:0.25,
      emissive:new THREE.Color(EMISSIVE.idle), emissiveIntensity:0.25,
      envMapIntensity:1.1, flatShading:true
    });
    const shardGeos = [ new THREE.TetrahedronGeometry(0.17), new THREE.OctahedronGeometry(0.14), new THREE.IcosahedronGeometry(0.13, 0) ];
    const shardGroup = new THREE.Group(); root.add(shardGroup);
    const shards = [];
    const N = reduce ? 16 : 32;
    for (let i = 0; i < N; i++){
      const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(Math.max(0, 1 - y*y)), phi = i * 2.399963;
      const dir = new THREE.Vector3(Math.cos(phi)*r, y*0.82, Math.sin(phi)*r);
      const s = new THREE.Mesh(shardGeos[i % shardGeos.length], shardMat);
      s.userData = { dir, baseR:1.78 + (i % 5) * 0.07,
        spin:new THREE.Vector3(Math.sin(i)*0.5, Math.cos(i*1.3)*0.6, Math.sin(i*0.7)*0.45) };
      s.scale.setScalar(0.65 + (i % 4) * 0.2);
      shardGroup.add(s); shards.push(s);
    }

    // ---- particle dust (in-scene, additive) ----
    const pCount = reduce ? 70 : 160;
    const pPos = new Float32Array(pCount * 3);
    for (let i = 0; i < pCount; i++){
      const rr = 2.3 + Math.sqrt(i / pCount) * 1.9, th = i * 2.399963, ph = Math.acos(1 - 2 * ((i + 0.5) / pCount));
      pPos[i*3]   = Math.sin(ph) * Math.cos(th) * rr;
      pPos[i*3+1] = Math.cos(ph) * rr * 0.68;
      pPos[i*3+2] = Math.sin(ph) * Math.sin(th) * rr;
    }
    const pGeo = new THREE.BufferGeometry(); pGeo.setAttribute("position", new THREE.BufferAttribute(pPos, 3));
    const pMat = new THREE.PointsMaterial({ color:0xb7a6ff, size:0.03, transparent:true, opacity:0.5, blending:THREE.AdditiveBlending, depthWrite:false });
    const points = new THREE.Points(pGeo, pMat); root.add(points);

    // ---- abstract sensor visor (thin glowing bar across the core — no eyes) ----
    const visorMat = new THREE.MeshBasicMaterial({ color:0xeef0ff, transparent:true, opacity:0.12, blending:THREE.AdditiveBlending, depthWrite:false });
    const visor = new THREE.Mesh(new THREE.PlaneGeometry(2.7, 0.05), visorMat); visor.position.z = 1.25; root.add(visor);
    const visorGlowMat = new THREE.MeshBasicMaterial({ color:STATE_COLORS.idle, transparent:true, opacity:0.08, blending:THREE.AdditiveBlending, depthWrite:false });
    const visorGlow = new THREE.Mesh(new THREE.PlaneGeometry(3.3, 0.5), visorGlowMat); visorGlow.position.z = 1.1; root.add(visorGlow);

    const emissiveMats = [obsidian, shardMat]; // tinted together on state change

    // ---- state driver: idle calm → processing alive (all values lerp smoothly) ----
    let curState = "idle", curExpand = 0;
    let tExpand = 0, tRim = 3.2, tKey = 2.2, tCoreL = 0.4, tEm = 0.2, tWire = 0.10,
        tSoul = 0.5, tVisor = 0.12, tFresI = 0.95, tFresScan = 0.0, tPts = 0.5;
    const colCur = new THREE.Color(STATE_COLORS.idle), colTgt = new THREE.Color(STATE_COLORS.idle);
    const emCur  = new THREE.Color(EMISSIVE.idle),     emTgt  = new THREE.Color(EMISSIVE.idle);
    window.__jarvisModelState = (state) => {
      curState = state;
      const on = state === "working", off = state === "offline", err = state === "error", okk = state === "ok";
      colTgt.setHex(STATE_COLORS[state] != null ? STATE_COLORS[state] : STATE_COLORS.idle);
      emTgt.setHex(EMISSIVE[state]   != null ? EMISSIVE[state]   : EMISSIVE.idle);
      tExpand   = on ? 1 : okk ? 0.5 : err ? 0.4 : off ? -0.45 : 0;
      tRim      = on ? 5.2 : off ? 1.1 : err ? 3.8 : 3.2;
      tKey      = off ? 1.4 : 2.2;
      tCoreL    = on ? 2.4 : okk ? 1.5 : err ? 1.7 : off ? 0.05 : 0.5;
      tEm       = on ? 0.55 : err ? 0.42 : off ? 0.04 : okk ? 0.4 : 0.2;
      tWire     = on ? 0.18 : off ? 0.025 : 0.10;
      tSoul     = on ? 0.95 : off ? 0.12 : okk ? 0.8 : 0.5;
      tVisor    = on ? 0.95 : off ? 0.0 : okk ? 0.6 : err ? 0.7 : 0.12;
      tFresI    = on ? 1.45 : off ? 0.35 : 0.95;
      tFresScan = on ? 1.0 : err ? 0.5 : 0.0;
      tPts      = off ? 0.16 : on ? 0.75 : 0.5;
    };

    // ---- gentle mouse-follow (parallax rotation of the whole entity) ----
    const MAXY = 11*Math.PI/180, MAXP = 7*Math.PI/180;
    let tYaw = 0, tPitch = 0, cYaw = 0, cPitch = 0;
    const hero = document.querySelector(".hero") || mount;
    hero.addEventListener("mousemove", (e) => {
      const b = hero.getBoundingClientRect();
      const nx = ((e.clientX-b.left)/b.width - 0.5)*2, ny = ((e.clientY-b.top)/b.height - 0.5)*2;
      tYaw = Math.max(-1, Math.min(1, nx)) * MAXY;
      tPitch = Math.max(-1, Math.min(1, ny)) * MAXP;
    }, {passive:true});
    hero.addEventListener("mouseleave", () => { tYaw = 0; tPitch = 0; });

    let ready = false, t = 0;
    const K = 0.06;
    function render(){
      if (document.hidden) { requestAnimationFrame(render); return; }
      t += 0.016;
      const pulse = (curState === "working" && !reduce) ? (Math.sin(t * 3.0) + 1) / 2 : 0;

      // smooth every state value toward its target
      curExpand += (tExpand - curExpand) * K;
      rim.intensity += (tRim - rim.intensity) * K;
      key.intensity += (tKey - key.intensity) * K;
      corePoint.intensity += ((tCoreL + pulse * 0.8) - corePoint.intensity) * K;
      colCur.lerp(colTgt, K); emCur.lerp(emTgt, K);
      rim.color.copy(colCur); corePoint.color.copy(colCur);
      soulMat.color.copy(colCur); soulMat.opacity += (tSoul - soulMat.opacity) * K;
      visorGlowMat.color.copy(colCur);
      wireMat.color.copy(colCur); wireMat.opacity += ((tWire + pulse * 0.06) - wireMat.opacity) * K;
      wire2Mat.opacity += (tWire * 0.5 - wire2Mat.opacity) * K;
      visorMat.opacity += (tVisor - visorMat.opacity) * K;
      visorGlowMat.opacity += ((tVisor * 0.45) - visorGlowMat.opacity) * K;
      pMat.opacity += (tPts - pMat.opacity) * K;
      for (let i = 0; i < emissiveMats.length; i++){ const m = emissiveMats[i];
        m.emissive.copy(emCur); m.emissiveIntensity += ((tEm + pulse * 0.18) - m.emissiveIntensity) * K; }
      fresnelMat.uniforms.uColor.value.copy(colCur);
      fresnelMat.uniforms.uTime.value = t;
      fresnelMat.uniforms.uInt.value  += ((tFresI + pulse * 0.4) - fresnelMat.uniforms.uInt.value) * K;
      fresnelMat.uniforms.uScan.value += (tFresScan - fresnelMat.uniforms.uScan.value) * K;

      // rotation accelerates while processing
      const spd = reduce ? 0 : (0.0016 + Math.max(0, curExpand) * 0.0045);
      core.rotation.y += spd; core.rotation.x += spd * 0.4;
      shell.rotation.copy(core.rotation);
      soul.rotation.y -= spd * 1.5; soul.rotation.x += spd * 0.8;
      wire.rotation.y -= spd * 0.7; wire.rotation.z += spd * 0.3;
      wire2.rotation.y += spd * 0.5; wire2.rotation.x -= spd * 0.2;
      if (!reduce) points.rotation.y += 0.0006;

      // shard burst: drift outward + tumble
      const expand = 1 + Math.max(0, curExpand) * 0.46 + pulse * 0.06;
      for (let i = 0; i < shards.length; i++){
        const s = shards[i], u = s.userData, rr = u.baseR * expand;
        s.position.set(u.dir.x * rr, u.dir.y * rr, u.dir.z * rr);
        s.rotation.x += u.spin.x * (spd + 0.002);
        s.rotation.y += u.spin.y * (spd + 0.002);
        s.rotation.z += u.spin.z * (spd + 0.002);
      }
      shardGroup.rotation.y += spd * 0.5;

      // sensor visor breathes
      visor.scale.x = 0.8 + 0.18 * Math.sin(t * 1.2) + pulse * 0.12;

      // float + parallax of the whole entity
      cYaw += (tYaw - cYaw) * 0.06; cPitch += (tPitch - cPitch) * 0.06;
      root.position.y = reduce ? 0 : Math.sin(t * 0.6) * 0.05;
      root.rotation.y = cYaw + (reduce ? 0 : Math.sin(t * 0.4) * 0.02);
      root.rotation.x = cPitch;

      renderer.render(scene, camera);
      if (!ready) { ready = true; window.__jarvisModelReady = true; mount.setAttribute("data-loaded",""); }
      requestAnimationFrame(render);
    }
    render();

    // keep crisp on resize / layout changes
    const onResize = () => { renderer.setSize(W(), H()); camera.aspect = W()/H(); camera.updateProjectionMatrix(); };
    if (window.ResizeObserver) new ResizeObserver(onResize).observe(mount);
    window.addEventListener("resize", onResize);

  } catch (err) {
    if (window.__jarvisModelFallback) window.__jarvisModelFallback();
  }
})();
</script>
