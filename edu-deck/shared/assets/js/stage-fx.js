/* stage-fx.js — file-free procedural sound, slide-step hash links, blackout. */
(function(){
  'use strict';
  if(window.eduAudio&&window.eduStageFx)return;
  const doc=document,win=window;
  const reduce=win.matchMedia?win.matchMedia('(prefers-reduced-motion: reduce)'):{matches:false};

  /* ---------- procedural audio (off until explicit opt-in) ---------- */
  let ctx=null,graph=null,noiseBuf=null,enabled=false,gestureBound=false;
  function impulse(c){
    const len=Math.max(1,Math.floor(c.sampleRate*0.32));
    const buf=c.createBuffer(2,len,c.sampleRate);
    for(let ch=0;ch<2;ch++){
      const data=buf.getChannelData(ch);
      for(let i=0;i<len;i++){
        const rest=1-i/len;
        data[i]=(Math.random()*2-1)*Math.pow(rest,2.7)*(ch?0.92:1);
      }
    }
    return buf;
  }
  function ensureCtx(){
    if(ctx)return ctx;
    const AC=win.AudioContext||win.webkitAudioContext;
    if(!AC)return null;
    ctx=new AC();
    const input=ctx.createGain();
    const lowpass=ctx.createBiquadFilter();
    const convolver=ctx.createConvolver();
    const dry=ctx.createGain();
    const wet=ctx.createGain();
    const master=ctx.createGain();
    lowpass.type='lowpass';
    lowpass.frequency.value=5200;
    lowpass.Q.value=0.45;
    convolver.buffer=impulse(ctx);
    dry.gain.value=0.86;
    wet.gain.value=0.18;
    master.gain.value=0.58;
    input.connect(lowpass);
    lowpass.connect(dry);
    dry.connect(master);
    lowpass.connect(convolver);
    convolver.connect(wet);
    wet.connect(master);
    master.connect(ctx.destination);
    graph={input};
    return ctx;
  }
  function resumeCtx(){
    const c=ensureCtx();
    if(c&&c.state==='suspended'&&c.resume)c.resume().catch(function(){});
    return c;
  }
  function bindGesture(){
    if(gestureBound)return;
    gestureBound=true;
    const wake=function(){if(enabled)resumeCtx();};
    doc.addEventListener('pointerdown',wake,true);
    doc.addEventListener('keydown',wake,true);
  }
  function enable(){
    enabled=true;
    bindGesture();
    resumeCtx();
    return enabled;
  }
  function disable(){
    enabled=false;
    if(ctx&&ctx.suspend)ctx.suspend().catch(function(){});
    return enabled;
  }
  function toggle(){
    if(enabled)disable();else enable();
    return enabled;
  }
  function isEnabled(){return enabled;}
  function noise(c){
    if(noiseBuf)return noiseBuf;
    noiseBuf=c.createBuffer(1,c.sampleRate,c.sampleRate);
    const data=noiseBuf.getChannelData(0);
    for(let i=0;i<data.length;i++)data[i]=Math.random()*2-1;
    return noiseBuf;
  }
  function envelope(g,t,peak,dur,attack){
    g.gain.setValueAtTime(0.0001,t);
    g.gain.exponentialRampToValueAtTime(Math.max(0.0002,peak),t+(attack||0.012));
    g.gain.exponentialRampToValueAtTime(0.0001,t+dur);
  }
  function tone(c,type,freq,endFreq,t,dur,peak){
    const o=c.createOscillator(),g=c.createGain();
    o.type=type;
    o.frequency.setValueAtTime(freq,t);
    if(endFreq)o.frequency.exponentialRampToValueAtTime(endFreq,t+dur*0.86);
    envelope(g,t,peak,dur);
    o.connect(g);g.connect(graph.input);
    o.start(t);o.stop(t+dur+0.03);
  }
  function noiseHit(c,type,freq,endFreq,t,dur,peak){
    const src=c.createBufferSource(),fl=c.createBiquadFilter(),g=c.createGain();
    src.buffer=noise(c);
    src.loop=true;
    fl.type=type;
    fl.frequency.setValueAtTime(freq,t);
    if(endFreq)fl.frequency.exponentialRampToValueAtTime(endFreq,t+dur*0.86);
    envelope(g,t,peak,dur,0.006);
    src.connect(fl);fl.connect(g);g.connect(graph.input);
    src.start(t);src.stop(t+dur+0.03);
  }
  function play(kind){
    if(!enabled)return false;
    const c=resumeCtx();
    if(!c||!graph)return false;
    const t=c.currentTime+0.008;
    try{
      if(kind==='slide'){
        noiseHit(c,'bandpass',680,245,t,0.12,0.18);
        tone(c,'triangle',172,108,t,0.12,0.09);
      }else if(kind==='step'){
        noiseHit(c,'highpass',2600,0,t,0.055,0.075);
        tone(c,'square',1450,980,t,0.045,0.035);
      }else if(kind==='ok'){
        tone(c,'triangle',523.25,0,t,0.13,0.16);
        tone(c,'sine',783.99,0,t+0.07,0.15,0.13);
      }else if(kind==='ng'){
        tone(c,'sine',142,92,t,0.056,0.14);
        tone(c,'sine',128,86,t+0.07,0.056,0.12);
      }else{
        return false;
      }
    }catch(e){
      return false;
    }
    return true;
  }

  function params(){
    try{return new URLSearchParams(win.location.search||'');}
    catch(e){return new URLSearchParams();}
  }
  function headless(){
    return !!navigator.webdriver||/HeadlessChrome/i.test(navigator.userAgent||'');
  }
  function autoBlocked(){
    return headless()||params().has('quick')||!!reduce.matches||(doc.body&&doc.body.classList.contains('st-printing'));
  }
  function playAuto(kind){
    if(autoBlocked())return false;
    return play(kind);
  }

  /* ---------- slide-step hash deep links ---------- */
  function sections(){
    return Array.prototype.slice.call(doc.querySelectorAll('section[id]'));
  }
  function findSection(id){
    const list=sections();
    for(let i=0;i<list.length;i++)if(list[i].id===id)return list[i];
    return null;
  }
  function slideIndex(sec){
    const parent=sec.parentElement||doc.getElementById('stage');
    if(!parent)return -1;
    const siblings=Array.prototype.slice.call(parent.children).filter(function(el){
      return el.classList&&el.classList.contains('slide');
    });
    return siblings.indexOf(sec);
  }
  function parseHash(hash){
    let raw=(typeof hash==='string'?hash:win.location.hash)||'';
    if(raw.charAt(0)==='#')raw=raw.slice(1);
    if(!raw)return null;
    try{raw=decodeURIComponent(raw);}catch(e){}
    if(!raw||/[\s?#]/.test(raw))return null;
    const num=/^(\d+)(?:-(\d+))?$/.exec(raw);
    if(num){
      return {slide:Math.max(0,parseInt(num[1],10)-1),step:parseInt(num[2]||'0',10),id:null};
    }
    let id=raw,step=0;
    const tail=/^(.+)-(\d+)$/.exec(raw);
    if(tail){id=tail[1];step=parseInt(tail[2],10);}
    const sec=id&&findSection(id);
    if(!sec)return null;
    const idx=slideIndex(sec);
    if(idx<0)return null;
    return {slide:idx,step,id};
  }
  function seriesInfo(){
    try{return typeof win.seriesInfo==='function'?win.seriesInfo():null;}
    catch(e){return null;}
  }
  function jumpParsed(parsed){
    if(!parsed||typeof win.deckGo!=='function')return false;
    const series=seriesInfo();
    if(series){
      /* Series already owns numeric #episode-slide links; only section-id links are safe here. */
      if(!parsed.id)return false;
      const sec=findSection(parsed.id),deck=sec&&sec.closest?sec.closest('.deck'):null;
      const ep=deck&&deck.getAttribute('data-ep');
      if(!ep)return false;
      win.deckGo(ep,parsed.slide,parsed.step);
      return true;
    }
    win.deckGo(parsed.slide,parsed.step);
    return true;
  }
  let hashRetries=0;
  function jumpHash(){
    const parsed=parseHash();
    if(!parsed)return false;
    if(typeof win.deckGo!=='function'){
      if(hashRetries++<20)setTimeout(jumpHash,30);
      return false;
    }
    hashRetries=0;
    return jumpParsed(parsed);
  }
  function info(){
    try{return typeof win.deckInfo==='function'?win.deckInfo():null;}
    catch(e){return null;}
  }
  function syncHash(){
    const cur=info();
    if(!cur||typeof cur.slide!=='number'||cur.slide<0)return;
    if(doc.body.classList.contains('in-hub'))return;
    if(seriesInfo())return;
    const next='#'+(cur.slide+1)+(cur.step>0?'-'+cur.step:'');
    try{
      if(win.location.hash!==next)win.history.replaceState(null,'',next);
    }catch(e){}
  }

  /* ---------- blackout ---------- */
  let blackout=null;
  function ensureBlackout(){
    if(blackout&&blackout.isConnected)return blackout;
    blackout=doc.getElementById('ed-blackout');
    if(!blackout){
      blackout=doc.createElement('div');
      blackout.id='ed-blackout';
      blackout.className='ed-blackout';
      blackout.hidden=true;
      blackout.setAttribute('aria-hidden','true');
      doc.body.appendChild(blackout);
    }
    if(!blackout._edFx){
      blackout._edFx=true;
      blackout.addEventListener('click',function(e){
        e.preventDefault();
        e.stopPropagation();
        setBlackout(false);
      });
    }
    return blackout;
  }
  function isBlackout(){
    const el=doc.getElementById('ed-blackout');
    return !!(el&&!el.hidden);
  }
  function setBlackout(on){
    const el=ensureBlackout();
    el.hidden=!on;
    el.setAttribute('aria-hidden',on?'false':'true');
    return on;
  }
  function toggleBlackout(force){
    const on=typeof force==='boolean'?force:!isBlackout();
    setBlackout(on);
    return on;
  }

  /* ---------- shared input guards ---------- */
  function typing(t){
    return !!(t&&(t.isContentEditable||/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)));
  }
  function modalOpen(){
    return !!doc.querySelector('.st-modal.st-show,.st-print.st-show,.ed-sch.on,.ed-toc.on,.ed-help-modal.on');
  }
  let live=null;
  function announce(msg){
    if(typeof win.edToast==='function'){win.edToast(msg);return;}
    if(!live){
      live=doc.createElement('div');
      live.className='sr';
      live.setAttribute('role','status');
      live.setAttribute('aria-live','polite');
      doc.body.appendChild(live);
    }
    live.textContent=msg;
  }
  win.addEventListener('keydown',function(e){
    if(e.isComposing)return;
    const k=e.key;
    if(isBlackout()&&(k==='.'||k==='Escape')){
      e.preventDefault();
      e.stopImmediatePropagation();
      setBlackout(false);
      return;
    }
    if(e.defaultPrevented||e.ctrlKey||e.metaKey||e.altKey)return;
    if(typing(e.target)||modalOpen())return;
    if(k==='u'||k==='U'){
      e.preventDefault();
      const on=toggle();
      announce(on?'소리를 켰습니다 (U 끄기)':'소리를 껐습니다 (U 켜기)');
    }else if(k==='.'){
      e.preventDefault();
      toggleBlackout();
    }
  },true);

  /* ---------- event wiring ---------- */
  doc.addEventListener('deckslide',function(){
    playAuto('slide');
    syncHash();
  });
  doc.addEventListener('deckstep',function(){
    playAuto('step');
    syncHash();
  });
  win.addEventListener('hashchange',function(){jumpHash();});

  const pendingQuiz=typeof WeakMap==='function'?new WeakMap():null;
  const quizState=typeof WeakMap==='function'?new WeakMap():null;
  if(pendingQuiz){
    doc.addEventListener('click',function(e){
      const box=e.target&&e.target.closest?e.target.closest('.chk'):null;
      if(box)pendingQuiz.set(box,Date.now());
    },true);
  }
  if(win.MutationObserver&&pendingQuiz){
    const observer=new MutationObserver(function(records){
      records.forEach(function(rec){
        const box=rec.target;
        if(!box||!box.classList||!box.classList.contains('chk'))return;
        const now=box.classList.contains('chk-ok')?'ok':(box.classList.contains('chk-ng')?'ng':'');
        const before=quizState.get(box)||'';
        quizState.set(box,now);
        if((now==='ok'||now==='ng')&&now!==before){
          const at=pendingQuiz.get(box)||0;
          if(at&&Date.now()-at<1200){
            pendingQuiz.delete(box);
            playAuto(now);
          }
        }
      });
    });
    observer.observe(doc.documentElement,{subtree:true,attributes:true,attributeFilter:['class']});
  }

  function boot(){
    if(params().get('sound')==='1'&&!autoBlocked())enable();
    jumpHash();
  }
  if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',function(){setTimeout(boot,0);});
  else setTimeout(boot,0);

  win.eduAudio={enable,disable,toggle,isEnabled,play};
  win.eduStageFx={toggleBlackout,isBlackout,parseHash};
})();
