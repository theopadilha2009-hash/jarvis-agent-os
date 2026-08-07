/* EXTRACT from cockpit.html — AVATAR ENGINE (GLB humanoid / boneco 3D)
 * Lines 2247-2412 of 11_SCRIPTS/jarvis_ui_assets/cockpit.html
 * Mount: #avatar3d | Mode tab: Avatar (DEFAULT)
 * Loads: /asset/models/jarvis-humanoid.glb
 */
   AVATAR ENGINE — GLB as dark glass / obsidian mask entity
   ============================================================ */
function makeAvatar(){
  const mount = q('#avatar3d'); if(!mount) return null;
  let THREE, renderer, scene, camera, root, wire, visor, particles, env;
  let raf=0, running=false, ready=false, disposed=false;
  let mx=0, my=0, tYaw=0, tPitch=0, cYaw=0, cPitch=0, t0=performance.now();
  let state='idle', flash=0, silhouette=true; // dependable default: dark silhouette + crystal overlays (not a face)

  function onMove(e){
    const r = heroEl.getBoundingClientRect();
    mx = ((e.clientX-r.left)/r.width)*2-1;
    my = ((e.clientY-r.top)/r.height)*2-1;
  }

  async function init(){
    if(ready||disposed) return;
    if(!webglOK()) throw new Error('no-webgl');
    THREE = await loadThree();
    renderer = new THREE.WebGLRenderer({alpha:true, antialias:true, powerPreference:'high-performance'});
    renderer.setClearColor(0x000000,0);
    renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));
    const w=mount.clientWidth||520, h=mount.clientHeight||520;
    renderer.setSize(w,h,false);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.82;   // darker, less blown-out → obsidian read
    mount.appendChild(renderer.domElement);
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(32, w/h, 0.1, 100);
    camera.position.set(0,0.02,5.4);

    // env (PMREM) so glass reads — graceful if RoomEnvironment missing
    try{
      const {RoomEnvironment} = await loadRoomEnv();
      const pmrem = new THREE.PMREMGenerator(renderer);
      env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
      scene.environment = env;
    }catch(e){ /* no env, still render */ }

    // lights: dim fill, restrained violet key/rim -> the mask stays in shadow, glassy not washed
    scene.add(new THREE.AmbientLight(0x141226, 0.26));
    const key = new THREE.DirectionalLight(0x8666ff, 0.92); key.position.set(2.2,2.4,3); scene.add(key);
    const rim = new THREE.DirectionalLight(0x547fd6, 0.68); rim.position.set(-3,1.2,-2); scene.add(rim);
    const under = new THREE.PointLight(0x7a5cff, 0.30, 12); under.position.set(0,-2,2); scene.add(under);

    root = new THREE.Group(); scene.add(root);

    // load GLB with timeout -> else throw to fallback
    const {GLTFLoader} = await loadGLTF();
    const url = '/asset/models/jarvis-humanoid.glb';
    const gltf = await new Promise((res,rej)=>{
      const to=setTimeout(()=>rej(new Error('glb-timeout')), 8000);
      try{
        new GLTFLoader().load(url, g=>{clearTimeout(to);res(g);}, undefined, err=>{clearTimeout(to);rej(err);});
      }catch(err){ clearTimeout(to); rej(err); }
    });

    const model = gltf.scene || gltf.scenes[0];
    // normalize scale/center
    const box = new THREE.Box3().setFromObject(model);
    const size = new THREE.Vector3(); box.getSize(size);
    const center = new THREE.Vector3(); box.getCenter(center);
    const maxd = Math.max(size.x,size.y,size.z)||1;
    const s = 2.15/maxd; model.scale.setScalar(s);   // smaller → headroom, no top clip
    model.position.sub(center.multiplyScalar(s));
    model.position.y -= 0.06;                          // settle low → reads as a bust rising from the dark

    // OBSIDIAN GLASS material override on every mesh
    const glassMat = new THREE.MeshPhysicalMaterial({
      color:0x0b0a16, flatShading:true, metalness:0.10, roughness:0.25,
      transmission:0.55, thickness:1.2, ior:1.3,
      attenuationColor:new THREE.Color(0x8a6cff), attenuationDistance:2.2,
      emissive:new THREE.Color(0x190f3a), emissiveIntensity:0.25,
      envMapIntensity:1.2, transparent:true, opacity:0.92, side:THREE.DoubleSide
    });
    const silMat = new THREE.MeshStandardMaterial({
      color:0x070612, flatShading:true, metalness:0.58, roughness:0.36,
      emissive:0x130a2c, emissiveIntensity:0.14, envMapIntensity:0.9
    });
    const wires=[];
    model.traverse(o=>{
      if(o.isMesh && o.geometry){
        o.material = silhouette ? silMat : glassMat;
        o.castShadow=false; o.receiveShadow=false;
        try{
          const wg = o.geometry;
          const wmat = new THREE.MeshBasicMaterial({color:0x8a6cff, wireframe:true, transparent:true, opacity:0.10, blending:THREE.AdditiveBlending, depthWrite:false});
          const wm = new THREE.Mesh(wg, wmat); wm.position.copy(o.position); wm.scale.copy(o.scale).multiplyScalar(1.004); wm.quaternion.copy(o.quaternion);
          wires.push([o,wm]);
        }catch(e){}
      }
    });
    root.add(model);
    wires.forEach(([o,wm])=> o.parent && o.parent.add(wm));
    wire = wires;

    // iconic luminous VISOR scan-band — now THIN + soft + slow (elegant, not harsh)
    const visGeo = new THREE.PlaneGeometry(2.6, 0.075);
    const visMat = new THREE.MeshBasicMaterial({color:0xb6a0ff, transparent:true, opacity:0.32, blending:THREE.AdditiveBlending, depthWrite:false, depthTest:false});
    visor = new THREE.Mesh(visGeo, visMat);
    visor.position.set(0, 0.34, 1.35); root.add(visor);

    // orbiting particles
    const N=140, pg=new THREE.BufferGeometry(), pa=new Float32Array(N*3);
    for(let i=0;i<N;i++){ const a=Math.random()*Math.PI*2, rr=1.6+Math.random()*1.4, yy=(Math.random()-0.5)*3;
      pa[i*3]=Math.cos(a)*rr; pa[i*3+1]=yy; pa[i*3+2]=Math.sin(a)*rr; }
    pg.setAttribute('position', new THREE.BufferAttribute(pa,3));
    const pmat = new THREE.PointsMaterial({color:0x9a7bff, size:0.026, transparent:true, opacity:0.32, blending:THREE.AdditiveBlending, depthWrite:false});
    particles = new THREE.Points(pg,pmat); scene.add(particles);

    ready=true;
    window.addEventListener('pointermove', onMove, {passive:true});
    window.addEventListener('resize', resize);
    resize();
  }

  function resize(){
    if(!renderer||!camera) return;
    const w=mount.clientWidth||520, h=mount.clientHeight||520;
    renderer.setSize(w,h,false); camera.aspect=w/h; camera.updateProjectionMatrix();
  }

  function setState(s){
    state=s; if(s==='ok'||s==='error') flash=1;
  }

  function frame(){
    if(!running) return;
    raf=requestAnimationFrame(frame);
    const now=performance.now(), tt=(now-t0)/1000;
    const speed = (state==='working')?2.0:1.0;
    // mouse follow (limited)
    tYaw = THREE.MathUtils.clamp(mx*0.32, -0.32, 0.32);   // ~±18deg
    tPitch = THREE.MathUtils.clamp(my*0.18, -0.18, 0.18); // ~±10deg
    cYaw += (tYaw-cYaw)*0.06; cPitch += (tPitch-cPitch)*0.06;
    if(root){
      root.rotation.y = cYaw + Math.sin(tt*0.4)*0.03;
      root.rotation.x = cPitch + Math.sin(tt*0.5)*0.015;
      root.position.y = Math.sin(tt*0.9)*0.04; // breathe
    }
    if(visor){
      visor.position.y = 0.30 + Math.sin(tt*speed*0.5)*0.58;   // slow, graceful full-mask sweep
      const base = state==='working'?0.46:0.28;
      visor.material.opacity = base + Math.sin(tt*speed*1.3)*0.07 + flash*0.28;
    }
    if(particles){
      particles.rotation.y += 0.0012*speed;
      particles.material.opacity = 0.26 + (state==='working'?0.18:0.0) + flash*0.28;
    }
    if(flash>0) flash = Math.max(0, flash-0.02);
    renderer.render(scene,camera);
  }

  return {
    name:'avatar', get inited(){return ready;}, get ok(){return ready && !disposed;},
    async start(){
      if(disposed) return;
      if(!ready){ await init(); }
      running=true; if(!RM){ if(!raf) frame(); } else { renderer&&renderer.render(scene,camera); }
    },
    stop(){ running=false; if(raf){cancelAnimationFrame(raf); raf=0;} },
    setState, useSilhouette(){ silhouette=true; },
    dispose(){ disposed=true; this.stop(); try{ window.removeEventListener('pointermove',onMove); }catch(e){} }
  };
}

