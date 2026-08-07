/* EXTRACT from cockpit.html — MODE ORCHESTRATION (Avatar/Core/Source/Forge switch)
 * Lines 2626-2790 of 11_SCRIPTS/jarvis_ui_assets/cockpit.html
 */
   MODE ORCHESTRATION
   ============================================================ */
function applyHue(mode){
  try{ heroEl.style.setProperty('--acc-dyn', HUE[mode]||HUE.avatar); }catch(e){}
}
function setMicro(mode){
  const arr = MICRO[mode]||MICRO.avatar;
  microEls.forEach((el,i)=>{ if(!el) return; el.textContent=arr[i]||''; el.classList.toggle('show', !!arr[i]); });
}
function ensureHolders(){
  try{
    const tag = q('.tagtop');
    if(tag && !tag.querySelector('[data-mode-label]')){
      const sp=document.createElement('span'); sp.setAttribute('data-mode-label','');
      sp.style.cssText='margin-left:8px;opacity:.85;letter-spacing:.22em;font-size:.92em';
      tag.appendChild(document.createTextNode(' \u00b7 ')); tag.appendChild(sp);
    }
  }catch(e){}
  try{
    const meta = q('.herometa');
    if(meta && !meta.querySelector('[data-mode-meta]')){
      const sp=document.createElement('span'); sp.setAttribute('data-mode-meta','');
      sp.style.cssText='display:block;margin-top:4px;opacity:.7';
      meta.appendChild(sp);
    }
  }catch(e){}
}
function setLabels(mode){
  try{ const tl = q('[data-mode-label]'); if(tl) tl.textContent = TAG[mode]||''; }catch(e){}
  try{ const meta = q('.herometa [data-mode-meta]'); if(meta) meta.textContent = META[mode]||''; }catch(e){}
}

async function ensureEngine(mode){
  try{
    if(mode==='avatar'){ if(!engines.avatar) engines.avatar = makeAvatar();
      if(engines.avatar){ try{ await engines.avatar.start(); engines.avatar.setState(STATE_MAP[curState]||'idle'); }
        catch(e){ avatarFallback(); } } else { avatarFallback(); } }
    else if(mode==='source'){ if(!engines.source) engines.source = makeSource();
      if(engines.source){ await engines.source.start(); engines.source.setState(STATE_MAP[curState]||'idle'); } }
    else if(mode==='forge'){ if(!engines.forge) engines.forge = makeForge();
      if(engines.forge){ await engines.forge.start(); engines.forge.setState(STATE_MAP[curState]||'idle'); } }
    else if(mode==='core'){ /* core engine owns #bust3d; just reveal via data-mode */ }
  }catch(e){ if(mode==='avatar') avatarFallback(); }
}

function avatarFallback(){
  // GLB failed / WebGL missing / timeout -> guarantee a visual.
  // The dependable default is the existing procedural CORE entity, so the hero is NEVER empty.
  try{
    const av = q('#avatar3d');
    const hasCanvas = av && av.querySelector('canvas');
    if(!hasCanvas){
      // try to trigger the core's own SVG fallback too (harmless if absent)
      try{ if(typeof window.__jarvisModelFallback==='function') window.__jarvisModelFallback(); }catch(_){}
      setMode('core');
    }
  }catch(e){}
}

function stopOthers(active){
  ['avatar','source','forge'].forEach(k=>{ if(k!==active && engines[k]){ try{ engines[k].stop(); }catch(e){} } });
  // core engine: we let it idle when hidden; it owns #bust3d (cannot safely stop its loop)
}

let switching=false;
function setMode(mode, silent){
  if(!['avatar','core','source','forge'].includes(mode)) mode='avatar';
  MODE = mode;
  try{ figure.setAttribute('data-mode', mode); }catch(e){}
  try{ heroEl.setAttribute('data-mode', mode); }catch(e){}   // per-mode wordmark/aura composition
  // switch button states
  try{ qa('.modeSwitch button').forEach(b=>{ const on=b.getAttribute('data-mode')===mode; b.classList.toggle('on',on); b.setAttribute('aria-selected', on?'true':'false'); }); }catch(e){}
  applyHue(mode); setMicro(mode); setLabels(mode);
  // forge CTA + command placeholder
  try{
    if(forgeCTA) forgeCTA.classList.toggle('show', mode==='forge');
    const inp = q('#hero ~ * input, .cmdbar input, .chatbar input, #cmd, input[type="text"]') || qa('input').find(i=>/cmd|chat|command|describe/i.test((i.placeholder||'')+i.id+i.className));
    if(inp){
      if(mode==='forge'){ inp.dataset._ph = inp.dataset._ph || inp.placeholder || ''; inp.placeholder='Describe a feature to forge…  e.g. add a notes endpoint'; }
      else if(inp.dataset._ph!=null){ inp.placeholder = inp.dataset._ph; }
    }
  }catch(e){}
  ensureEngine(mode);
  stopOthers(mode);
}

window.setJarvisHeroMode = function(mode){ try{ setMode(mode); }catch(e){ console.warn('heroMode fail',e); } };

/* ---------- state routing: wrap existing setJarvisVisualState ---------- */
function driveState(state){
  curState = state;
  const norm = STATE_MAP[state]||'idle';
  // route to active engine
  const eng = engines[MODE]; if(eng && eng.setState){ try{ eng.setState(norm); }catch(e){} }
  // hero alive class
  try{ heroEl.classList.toggle('thinking', norm==='working'); }catch(e){}
  // flash on ok/error
  try{
    if((norm==='ok'||norm==='error') && flashEl){
      flashEl.classList.remove('ok','bad'); void flashEl.offsetWidth;
      flashEl.classList.add(norm==='ok'?'ok':'bad');
      setTimeout(()=>{ try{flashEl.classList.remove('ok','bad');}catch(e){} }, 1800);
    }
  }catch(e){}
}
(function wrapVisual(){
  const orig = window.setJarvisVisualState;
  window.setJarvisVisualState = function(state){
    let r; try{ if(typeof orig==='function') r = orig.apply(this, arguments); }catch(e){}
    try{ driveState(state); }catch(e){}
    return r;
  };
})();

/* ---------- forge CTA -> real Forge Engine, rendered in the existing viewer ---------- */
function wireForge(){
  if(!forgeCTA) return;
  forgeCTA.addEventListener('click', ()=>{
    try{
      const inp = q('#cmd, input[type="text"]') || qa('input').find(i=>/cmd|chat|command|describe/i.test((i.placeholder||'')+i.id+i.className));
      const desc = inp && inp.value && inp.value.trim();
      // With a feature typed: run the real engine and show it in the main viewer.
      if(desc && typeof window.call==='function' && typeof window.post==='function'){
        if(inp) inp.value='';
        window.call('/forge-run', window.post({goal:desc, mode:'normal'}), 'Forge · '+desc);
        return;
      }
      // Empty: open the dedicated FORGE console so the user can describe a feature.
      const launch = document.getElementById('j83-launch');
      if(launch){ launch.click(); return; }
      if(inp){ inp.focus(); }
    }catch(e){ console.warn('forge cta fail',e); }
  });
}

/* ---------- wire mode switch buttons ---------- */
function wireSwitch(){
  if(!switchEl) return;
  switchEl.addEventListener('click', e=>{
    const b = e.target.closest('button[data-mode]'); if(!b) return;
    setMode(b.getAttribute('data-mode'));
  });
}

/* ---------- boot ---------- */
function boot(){
  try{
    figure = q('#figure') || q('.figure');
    heroEl = q('#hero') || q('.hero');
    switchEl = q('.modeSwitch');
    microEls = ['m1','m2','m3','m4'].map(c=> q('.heroMicro.'+c));
    flashEl = q('.hero .stateFlash');
    forgeCTA = q('.forgeCTA');
    if(!figure || !heroEl){ return; }
    // refresh endpoint count microcopy if present (non-destructive)
    ensureHolders();
    wireSwitch(); wireForge();
    // DEFAULT MODE = avatar
    setMode('avatar');
  }catch(e){ console.warn('hero boot fail', e); }
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', boot);
else boot();
})();
</script>
