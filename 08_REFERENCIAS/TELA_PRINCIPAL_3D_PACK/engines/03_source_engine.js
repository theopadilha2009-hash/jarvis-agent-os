/* EXTRACT from cockpit.html — SOURCE ENGINE (canvas constellation)
 * Lines 2414-2566 of 11_SCRIPTS/jarvis_ui_assets/cockpit.html
 * Mount: #sourceMap | Mode tab: Source
 */
   SOURCE ENGINE — canvas constellation of intelligence sources
   ============================================================ */
function makeSource(){
  const mount = q('#sourceMap'); if(!mount) return null;
  const cvs = document.createElement('canvas'); mount.appendChild(cvs);
  const ctx = cvs.getContext('2d');
  let raf=0, running=false, w=0,h=0, dpr=Math.min(devicePixelRatio||1,2);
  let nodes=[], clusters=[], total=0, state='idle', t0=performance.now();
  const PLACEHOLDER=['PLAN','BACKLOG','N8N','DIGEST','SOURCES','MEMORY','CONTEXT','RESEARCH','DOCTOR','ACCEPTANCE'];
  // pan/zoom view + interaction state
  const view={k:1,x:0,y:0};
  let fitted=false, wired=false, dragging=false, lastX=0, lastY=0;
  let mX=-1, mY=-1, hoverIdx=-1;

  function resize(){ w=mount.clientWidth||520; h=mount.clientHeight||520; cvs.width=w*dpr; cvs.height=h*dpr; cvs.style.width=w+'px'; cvs.style.height=h+'px'; ctx.setTransform(dpr,0,0,dpr,0,0); }

  function base(name){ try{ return String(name).split('/').pop().split('\\').pop().slice(0,16).toUpperCase(); }catch(e){ return String(name).slice(0,16); } }

  // ---- mouse control: reset, wheel-zoom (toward cursor), drag-pan ----
  function fit(){ view.k=1; view.x=0; view.y=0; fitted=true; }
  function clampK(k){ return Math.max(0.5, Math.min(4.2, k)); }
  function localXY(e){ const r=cvs.getBoundingClientRect(); return {x:e.clientX-r.left, y:e.clientY-r.top}; }
  function onWheel(e){ e.preventDefault(); const p=localXY(e), old=view.k, nk=clampK(old*Math.exp(-e.deltaY*0.0016)); if(nk===old) return;
    view.x = p.x-(p.x-view.x)*(nk/old); view.y = p.y-(p.y-view.y)*(nk/old); view.k = nk; }
  function onDown(e){ if(e.button!=null && e.button!==0) return; dragging=true; const p=localXY(e); lastX=p.x; lastY=p.y; mount.classList.add('grabbing'); try{ cvs.setPointerCapture(e.pointerId); }catch(_){} }
  function onMove(e){ const p=localXY(e); mX=p.x; mY=p.y; if(dragging){ view.x+=p.x-lastX; view.y+=p.y-lastY; lastX=p.x; lastY=p.y; } }
  function onUp(e){ dragging=false; mount.classList.remove('grabbing'); try{ cvs.releasePointerCapture(e.pointerId); }catch(_){} }
  function onLeave(){ dragging=false; mX=-1; mY=-1; mount.classList.remove('grabbing'); }
  function wire(){ if(wired) return; wired=true;
    cvs.addEventListener('wheel', onWheel, {passive:false});
    cvs.addEventListener('pointerdown', onDown); cvs.addEventListener('pointermove', onMove);
    cvs.addEventListener('pointerup', onUp); cvs.addEventListener('pointercancel', onUp);
    cvs.addEventListener('pointerleave', onLeave); cvs.addEventListener('dblclick', e=>{ e.preventDefault(); fit(); }); }

  async function fetchSources(){
    let labels=[];
    try{
      const r = await fetch('/sources'); if(r.ok){
        const j = await r.json();
        let arr = Array.isArray(j)?j:(j.sources||j.items||j.data||[]);
        if(!Array.isArray(arr)) arr=[];
        labels = arr.slice(0,26).map(x=> base(typeof x==='string'?x:(x.name||x.path||x.id||x.title||'SRC')));
      }
    }catch(e){}
    if(!labels.length) labels = PLACEHOLDER.slice();
    total = labels.length;
    // cluster anchors distributed across the width → the graph fills the band,
    // not a single tight ring in the middle (Obsidian-graph read).
    const CN = Math.max(2, Math.min(5, Math.round(labels.length/4)));
    clusters = [];
    for(let i=0;i<CN;i++){
      const u = CN>1 ? i/(CN-1) : 0.5;
      clusters.push({
        nx: 0.22 + u*0.56,                                  // tighter spread → stays on-screen + readable
        ny: 0.34 + (i%2?0.22:0.02) + Math.sin(i*2.1)*0.04,  // alternating high/low band
        ph: i*1.3
      });
    }
    nodes = labels.map((lab,i)=>{
      const cl = i % CN;
      const a  = (i/labels.length)*Math.PI*2 + cl*0.7;
      const r  = 0.05 + (i%3)*0.032;                        // small radius around its cluster
      return {lab, cl, a, r, sp:(0.20+ (i%5)*0.10)*((i%2)?-1:1), p:(i*0.137)%1, sz:3.0+(i%3)*0.9};
    });
  }

  function frame(){
    if(!running) return;
    raf=requestAnimationFrame(frame);
    const tt=(performance.now()-t0)/1000;
    const speed=(state==='working')?1.7:1.0;
    // clear in device space, then draw the world under the pan/zoom transform
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,w,h);
    ctx.setTransform(dpr*view.k,0,0,dpr*view.k, view.x*dpr, view.y*dpr);
    const k=view.k, m=Math.min(w,h), hx=w*0.5, hy=h*0.52;
    const wmx=(mX-view.x)/k, wmy=(mY-view.y)/k;   // mouse in world space (hover)
    // faint dotted baseline
    ctx.save(); ctx.globalAlpha=0.05; ctx.strokeStyle='#7fb6ff'; ctx.lineWidth=1/k; ctx.setLineDash([2/k,7/k]);
    for(let y=h*0.22;y<=h*0.82;y+=Math.max(46,h/7)){ ctx.beginPath();ctx.moveTo(w*0.06,y);ctx.lineTo(w*0.94,y);ctx.stroke(); }
    ctx.setLineDash([]); ctx.restore();
    // cluster pixel positions with gentle organic drift
    const cpos = clusters.map(c=>({
      x: c.nx*w + Math.sin(tt*0.22*speed + c.ph)*8,
      y: c.ny*h + Math.cos(tt*0.18*speed + c.ph)*8
    }));
    // hub → cluster spines
    cpos.forEach(c=>{ ctx.strokeStyle='rgba(127,182,255,.18)'; ctx.lineWidth=1.1/k;
      ctx.beginPath(); ctx.moveTo(hx,hy); ctx.lineTo(c.x,c.y); ctx.stroke(); });
    // node positions
    const npos = nodes.map(n=>{
      const ang = n.a + tt*n.sp*0.05*speed;
      const c = cpos[n.cl];
      return { x:c.x+Math.cos(ang)*n.r*m, y:c.y+Math.sin(ang)*n.r*m*0.92, n };
    });
    // hover pick (nearest node within radius, world space)
    hoverIdx=-1;
    if(mX>=0 && !dragging){ let best=Infinity;
      for(let i=0;i<npos.length;i++){ const dx=npos[i].x-wmx, dy=npos[i].y-wmy, d=dx*dx+dy*dy;
        if(d<best && d < (18/k)*(18/k)){ best=d; hoverIdx=i; } } }
    // node → cluster links
    npos.forEach(p=>{ const c=cpos[p.n.cl]; ctx.strokeStyle='rgba(127,182,255,.12)'; ctx.lineWidth=1/k;
      ctx.beginPath(); ctx.moveTo(c.x,c.y); ctx.lineTo(p.x,p.y); ctx.stroke(); });
    // a few cross-links between near nodes → graph density
    for(let i=0;i<npos.length;i++){ const a=npos[i], b=npos[(i+3)%npos.length];
      const dx=a.x-b.x, dy=a.y-b.y; if(dx*dx+dy*dy < (m*0.22)*(m*0.22)){
        ctx.strokeStyle='rgba(160,150,255,.05)'; ctx.lineWidth=1/k;
        ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke(); } }
    // data particles flowing hub → clusters
    cpos.forEach((c,i)=>{ const t=(tt*0.22*speed + i*0.31)%1; const px=hx+(c.x-hx)*t, py=hy+(c.y-hy)*t;
      ctx.fillStyle='rgba(184,163,255,.6)'; ctx.beginPath(); ctx.arc(px,py,1.8/k,0,7); ctx.fill(); });
    // cluster cores
    cpos.forEach(c=>{ ctx.fillStyle='rgba(127,182,255,.55)'; ctx.shadowColor='#7fb6ff'; ctx.shadowBlur=10;
      ctx.beginPath(); ctx.arc(c.x,c.y,4.4,0,7); ctx.fill(); ctx.shadowBlur=0; });
    // nodes + readable labels (dark outline for contrast on any background)
    const fs=11; ctx.textAlign='left'; ctx.lineJoin='round';
    npos.forEach((p,i)=>{
      const hot=i===hoverIdx, sz=p.n.sz*(hot?1.6:1);
      ctx.fillStyle= hot?'#eaf2ff':'rgba(196,214,248,.95)'; ctx.shadowColor='#7fb6ff'; ctx.shadowBlur= hot?16:8;
      ctx.beginPath(); ctx.arc(p.x,p.y,sz,0,7); ctx.fill(); ctx.shadowBlur=0;
      if(hot){ ctx.strokeStyle='rgba(180,205,255,.7)'; ctx.lineWidth=1.4/k; ctx.beginPath(); ctx.arc(p.x,p.y,sz+4/k,0,7); ctx.stroke(); }
      ctx.font=(hot?'700 '+(fs+1):''+fs)+'px ui-monospace,Menlo,monospace';
      const lx=p.x+sz+5, ly=p.y+3.5;
      ctx.lineWidth=3/k; ctx.strokeStyle='rgba(4,7,18,.9)'; ctx.strokeText(p.n.lab, lx, ly);
      ctx.fillStyle= hot?'#dfeaff':'rgba(210,222,246,.82)'; ctx.fillText(p.n.lab, lx, ly);
    });
    // central hub (index count)
    ctx.fillStyle='rgba(127,182,255,.95)'; ctx.shadowColor='#7fb6ff'; ctx.shadowBlur=18;
    ctx.beginPath(); ctx.arc(hx,hy,7,0,7); ctx.fill(); ctx.shadowBlur=0;
    ctx.textAlign='center';
    ctx.lineWidth=4/k; ctx.strokeStyle='rgba(4,7,18,.85)'; ctx.font='700 32px ui-sans-serif,system-ui';
    ctx.strokeText(String(total), hx, hy-15); ctx.fillStyle='#eaf1ff'; ctx.fillText(String(total), hx, hy-15);
    ctx.fillStyle='rgba(170,186,214,.8)'; ctx.font='9px ui-monospace,Menlo,monospace';
    ctx.fillText('LOCAL MEMORY · CONTEXT INDEX', hx, hy+24);
    ctx.textAlign='left';
    // ---- fixed HUD (screen space, not zoomed): controls hint + zoom % ----
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.font='9px ui-monospace,Menlo,monospace'; ctx.textAlign='left'; ctx.fillStyle='rgba(150,168,200,.5)';
    ctx.fillText('scroll: zoom   ·   drag: pan   ·   dbl-click: reset', 16, h-16);
    ctx.textAlign='right'; ctx.fillStyle='rgba(127,182,255,.6)'; ctx.fillText(Math.round(view.k*100)+'%', w-16, h-16);
    ctx.textAlign='left';
  }

  return {
    name:'source', inited:false,
    async start(){ if(!this.inited){ resize(); await fetchSources(); fit(); wire(); this.inited=true; window.addEventListener('resize',resize); }
      running=true; if(!RM){ if(!raf) frame(); } else { frame(); } },
    stop(){ running=false; if(raf){cancelAnimationFrame(raf);raf=0;} },
    setState(s){ state=s; },
    dispose(){ this.stop(); }
  };
}

