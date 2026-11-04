/* edu-deck authoring patterns: code copy, tabs, FAQ, screen pins, cross-links.
 * Attribute-driven — slides never carry their own scripts. The presentation
 * engine owns visibility and navigation; this module owns pattern behaviour.
 * Static modes (prefers-reduced-motion, print/beforeprint, body.st-self,
 * body.st-printing) expose every pane and every answer instead of the
 * interactive default, so print/self-study readers see the full content.
 */
(function(){
  'use strict';
  if(window.eduPatterns)return;
  const stage=document.getElementById('stage');
  if(!stage)return;
  const reduce=matchMedia('(prefers-reduced-motion: reduce)');
  const mediaPrint=matchMedia('print');
  const all=(q,r=document)=>Array.from(r.querySelectorAll(q));
  const staticMode=()=>reduce.matches||mediaPrint.matches||document.body.classList.contains('st-self')||document.body.classList.contains('st-printing');

  /* ---------- 코드 상자 복사 (.code > .code-head > .code-copy) ----------
     pre 안의 .p(프롬프트) .out(출력) .c(주석) span 은 복사에서 빠진다. */
  function copyText(pre){
    let out='';
    for(const n of pre.childNodes){
      if(n.nodeType===3)out+=n.textContent;
      else if(n.nodeType===1&&!n.matches('.p,.out,.c'))out+=n.textContent;
    }
    return out;
  }
  function clipboardFallback(t){
    const ta=document.createElement('textarea');
    ta.value=t;ta.style.cssText='position:fixed;top:0;left:0;opacity:0';
    document.body.append(ta);ta.select();
    try{document.execCommand('copy');}catch(e){}
    ta.remove();
  }
  function copyWrite(t){
    if(navigator.clipboard&&navigator.clipboard.writeText)
      return navigator.clipboard.writeText(t).catch(()=>clipboardFallback(t));
    return Promise.resolve(clipboardFallback(t));
  }
  function flashCopied(b){
    if(b._edBusy)return;
    b._edBusy=true;
    const orig=b.textContent;
    b.textContent='복사됨';
    setTimeout(()=>{b.textContent=orig;b._edBusy=false;},1500);
  }
  document.addEventListener('click',e=>{
    const b=e.target&&e.target.closest?e.target.closest('.code .code-copy'):null;
    if(!b)return;
    e.stopPropagation();
    const pre=b.closest('.code').querySelector('pre');
    if(pre)copyWrite(copyText(pre)).then(()=>flashCopied(b),()=>flashCopied(b));
  });

  /* ---------- 탭 (.tabs > .tab-bar > button × .tab-pane) ---------- */
  function tabsInit(){
    all('.tabs',stage).forEach(t=>{
      if(t._edTabs)return;
      const bar=t.querySelector(':scope>.tab-bar');
      const btns=bar?all(':scope>button',bar):[];
      const panes=all(':scope>.tab-pane',t);
      if(!btns.length||!panes.length)return;
      t._edTabs=true;
      bar.setAttribute('role','tablist');
      btns.forEach((b,i)=>{
        b.setAttribute('role','tab');
        if(!b.id)b.id='ed-tab-'+Math.random().toString(36).slice(2,9);
        const p=panes[i];
        if(p){
          p.setAttribute('role','tabpanel');
          if(!p.id)p.id=b.id+'-pane';
          b.setAttribute('aria-controls',p.id);
          p.setAttribute('aria-labelledby',b.id);
        }
        b.addEventListener('click',ev=>{ev.stopPropagation();show(i);});
      });
      const show=i=>{
        t._at=i;
        btns.forEach((b,k)=>{
          b.setAttribute('aria-selected',k===i?'true':'false');
          b.tabIndex=k===i?0:-1;
        });
        panes.forEach((p,k)=>{p.hidden=staticMode()?false:k!==i;});
        // A pane may hide data-fx content the step engine already passed:
        // opening it is a fresh reveal, so the motion sweep must look again.
        document.dispatchEvent(new CustomEvent('edpattern'));
      };
      t._show=show;
      bar.addEventListener('keydown',e=>{
        const i=t._at||0,pick=k=>{e.preventDefault();e.stopPropagation();show(k);btns[t._at].focus();};
        if(e.key==='ArrowRight'||e.key==='ArrowDown')pick((i+1)%btns.length);
        else if(e.key==='ArrowLeft'||e.key==='ArrowUp')pick((i-1+btns.length)%btns.length);
        else if(e.key==='Home')pick(0);
        else if(e.key==='End')pick(btns.length-1);
      });
      show(0);
    });
  }
  // Static modes stack every pane with its tab label so nothing is hidden.
  function tabsStatic(on){
    all('.tabs',stage).forEach(t=>{
      if(!t._edTabs)return;
      const panes=all(':scope>.tab-pane',t),btns=all(':scope>.tab-bar>button',t);
      panes.forEach((p,i)=>{
        if(on){
          p.hidden=false;
          if(!p.querySelector(':scope>.tab-pane-label')){
            const l=document.createElement('p');
            l.className='tab-pane-label';
            l.textContent=btns[i]?btns[i].textContent.trim():'';
            p.prepend(l);
          }
        }else{
          all(':scope>.tab-pane-label',p).forEach(x=>x.remove());
          p.hidden=i!==(t._at||0);
        }
      });
    });
  }

  /* ---------- 다른 장·다른 탭으로 가기 (.go[data-go][data-tab]) ---------- */
  document.addEventListener('click',e=>{
    const b=e.target&&e.target.closest?e.target.closest('.go[data-go]'):null;
    if(!b)return;
    e.stopPropagation();
    const n=parseInt(b.dataset.go,10);
    if(!(n>=1))return;
    if(window.deckGo)window.deckGo(n-1);
    const tab=parseInt(b.dataset.tab||'',10);
    if(tab>=1){
      const s=document.querySelector('#stage .slide.active');
      const t=s&&s.querySelector('.tabs');
      if(t&&t._show)t._show(tab-1);
    }
  });

  /* ---------- FAQ (.faq details) — 네이티브 toggle, 정적 모드=전부 펼침 ---------- */
  function faqStatic(on){
    all('.faq details',stage).forEach(d=>{
      if(on){if(!d.open){d.dataset.edStaticClosed='1';d.open=true;}}
      else if(d.dataset.edStaticClosed){delete d.dataset.edStaticClosed;d.open=false;}
    });
  }

  /* ---------- 화면 핀 (.pin-shot .pin[data-k] ↔ .pin-list [data-k]) ---------- */
  function pinsInit(){
    all('.pin-shot',stage).forEach(fig=>{
      if(fig._edPins)return;
      const slide=fig.closest('.slide')||stage;
      const pins=all('.pin[data-k]',fig);
      const items=all('.pin-list [data-k]',slide);
      if(!pins.length&&!items.length)return;
      fig._edPins=true;
      const pair=k=>{
        pins.forEach(n=>n.classList.toggle('on',k!==null&&n.dataset.k===k));
        items.forEach(n=>n.classList.toggle('on',k!==null&&n.dataset.k===k));
      };
      pins.concat(items).forEach(n=>{
        if(!n.matches('button,a,input')&&n.tabIndex<0)n.tabIndex=0;
        const on=()=>pair(n.dataset.k);
        n.addEventListener('mouseenter',on);
        n.addEventListener('focus',on);
        n.addEventListener('click',ev=>{ev.stopPropagation();on();});
      });
      fig.addEventListener('mouseleave',()=>pair(null));
      const list=slide.querySelector('.pin-list');
      if(list)list.addEventListener('mouseleave',()=>pair(null));
    });
  }

  function applyStatic(){
    const on=staticMode();
    tabsStatic(on);faqStatic(on);
  }
  window.addEventListener('beforeprint',()=>{tabsStatic(true);faqStatic(true);});
  window.addEventListener('afterprint',applyStatic);
  reduce.addEventListener('change',applyStatic);
  mediaPrint.addEventListener('change',applyStatic);
  new MutationObserver(applyStatic).observe(document.body,{attributes:true,attributeFilter:['class']});
  tabsInit();
  pinsInit();
  applyStatic();
  window.eduPatterns={};
})();
