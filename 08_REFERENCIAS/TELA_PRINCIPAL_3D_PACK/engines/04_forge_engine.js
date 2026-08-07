/* EXTRACT from cockpit.html — FORGE ENGINE (forja visual 2D)
 * Lines 2568-2624 of 11_SCRIPTS/jarvis_ui_assets/cockpit.html
 * Mount: #forgeStage | Mode tab: Forge
 * NÃO é o boneco 3D — é scaffold/shards. Boneco = Avatar engine + GLB.
 */
   FORGE ENGINE — wireframe scaffold + shards converging to a core
   ============================================================ */
function makeForge(){
  const mount = q('#forgeStage'); if(!mount) return null;
  const cvs = document.createElement('canvas'); mount.appendChild(cvs);
  const ctx = cvs.getContext('2d');
  let raf=0, running=false, w=0,h=0, dpr=Math.min(devicePixelRatio||1,2);
  let shards=[], sparks=[], state='idle', t0=performance.now();

  function resize(){ w=mount.clientWidth||520; h=mount.clientHeight||520; cvs.width=w*dpr; cvs.height=h*dpr; cvs.style.width=w+'px'; cvs.style.height=h+'px'; ctx.setTransform(dpr,0,0,dpr,0,0); }
  function build(){
    shards=[]; for(let i=0;i<26;i++){ const a=Math.random()*Math.PI*2;
      shards.push({a, r0:0.42+Math.random()*0.2, ph:Math.random()*Math.PI*2, sz:6+Math.random()*14}); }
    sparks=[]; for(let i=0;i<40;i++){ sparks.push({a:Math.random()*Math.PI*2, r:Math.random(), sp:0.3+Math.random()*0.7}); }
  }
  function frame(){
    if(!running) return; raf=requestAnimationFrame(frame);
    const tt=(performance.now()-t0)/1000, speed=(state==='working')?2.2:1.0;
    ctx.clearRect(0,0,w,h);
    const cx=w/2, cy=h*0.52, R=Math.min(w,h);
    const conv = 0.5+0.5*Math.sin(tt*0.5*speed);     // breathing build convergence
    // blueprint scaffold (concentric hex rings)
    ctx.strokeStyle='rgba(192,107,255,.15)'; ctx.lineWidth=1;
    for(let ring=1;ring<=4;ring++){ const rr=ring*0.085*R*1.15, sides=6; ctx.beginPath();
      for(let s=0;s<=sides;s++){ const ang=(s/sides)*Math.PI*2 + tt*0.08*ring*speed + ring*0.2; const x=cx+Math.cos(ang)*rr, y=cy+Math.sin(ang)*rr*0.86; s?ctx.lineTo(x,y):ctx.moveTo(x,y);} ctx.closePath(); ctx.stroke(); }
    // construction beams + converging shards
    shards.forEach(sh=>{
      const r=(sh.r0*(0.40+0.60*(1-conv)))*R, ang=sh.a+tt*0.12*speed;
      const x=cx+Math.cos(ang)*r, y=cy+Math.sin(ang)*r*0.86;
      ctx.strokeStyle='rgba(192,107,255,'+(0.05+conv*0.10)+')'; ctx.lineWidth=1;
      ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(x,y); ctx.stroke();
      ctx.save(); ctx.translate(x,y); ctx.rotate(sh.ph+tt*speed*0.6); ctx.fillStyle='rgba(206,140,255,'+(0.30+conv*0.45)+')';
      ctx.beginPath(); ctx.moveTo(0,-sh.sz); ctx.lineTo(sh.sz*0.5,sh.sz*0.5); ctx.lineTo(-sh.sz*0.5,sh.sz*0.5); ctx.closePath(); ctx.fill(); ctx.restore(); });
    // spinning containment ring
    ctx.strokeStyle='rgba(220,180,255,'+(0.18+conv*0.22)+')'; ctx.lineWidth=1.4;
    ctx.beginPath(); for(let s=0;s<=48;s++){ const ang=(s/48)*Math.PI*2, rr=(0.16+conv*0.03)*R; const x=cx+Math.cos(ang+tt*0.5*speed)*rr, y=cy+Math.sin(ang+tt*0.5*speed)*rr*0.86; s?ctx.lineTo(x,y):ctx.moveTo(x,y);} ctx.stroke();
    // forming core
    const cr = 10+conv*22;
    const g=ctx.createRadialGradient(cx,cy,0,cx,cy,cr*2.2);
    g.addColorStop(0,'rgba(235,205,255,'+(0.55+conv*0.4)+')'); g.addColorStop(.5,'rgba(192,107,255,'+(0.25+conv*0.2)+')'); g.addColorStop(1,'rgba(192,107,255,0)');
    ctx.fillStyle=g; ctx.beginPath(); ctx.arc(cx,cy,cr*2.2,0,7); ctx.fill();
    ctx.fillStyle='rgba(255,255,255,'+(0.65+conv*0.3)+')'; ctx.beginPath(); ctx.arc(cx,cy,cr*0.45,0,7); ctx.fill();
    // build-sparks rising into the core
    sparks.forEach(sp=>{ sp.r-= 0.006*sp.sp*speed; if(sp.r<0){ sp.r=1; sp.a=Math.random()*Math.PI*2; }
      const x=cx+Math.cos(sp.a)*sp.r*R*0.42, y=cy+Math.sin(sp.a)*sp.r*R*0.36;
      ctx.fillStyle='rgba(255,230,255,'+(1-sp.r)*0.8+')'; ctx.fillRect(x,y,2,2); });
  }
  return {
    name:'forge', inited:false,
    async start(){ if(!this.inited){ resize(); build(); this.inited=true; window.addEventListener('resize',resize); }
      running=true; if(!RM){ if(!raf) frame(); } else { frame(); } },
    stop(){ running=false; if(raf){cancelAnimationFrame(raf);raf=0;} },
    setState(s){ state=s; },
    dispose(){ this.stop(); }
  };
}

