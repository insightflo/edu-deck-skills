/* viewer.js — 검색(Ctrl+K·/), 목차(O·상단 단추), 상·하단 크롬(.ed-top/.ed-bot),
   data-fit 제목 맞춤, 엔진 준비 표시.
   solo·pack·series 포털에 공통 탑재. series 에서는 편 안(.deck.on) 기준으로 동작한다.

   크롬 계약:
   - .ed-top(44px)·.ed-bot(48px)은 무대 위 오버레이 — 유휴 2.5s 후 자동 숨김,
     가장자리 접근·키·터치·포커스로 복귀, 핀 버튼(localStorage ed-chrome-pin)으로 고정.
   - 기존 id 계약 유지: .ed-topbar(도구 띠) · #ed-clock · #progress · #dots · #counter · #help.
     #progress/#dots/#counter 는 .ed-bot 안으로 옮겨진다(엔진이 계속 갱신한다).
   - #help 는 DOM 에만 남는 문구 소스(display:none). 시각 표시는 .ed-help-modal 단축키 시트.
   - ?sheet/?shot/인쇄/발표자/허브/미준비 표면은 CSS 가 막대를 숨긴다(무대 치수 불변). */
(function(){
var doc=document, root=doc.documentElement, body=doc.body;
var SERIES=function(){return !!window.seriesInfo;};
function decks(){return [].slice.call(doc.querySelectorAll('#stage>.deck'));}
function slidesOf(d){return [].slice.call(d.querySelectorAll('.slide'));}
function slideEntries(){ /* [{ep,idx,el,eyebrow,title,text}] — series 면 모든 편, 아니면 #stage>.slide */
 var out=[], ds=decks();
 if(ds.length){ds.forEach(function(d){var ep=d.getAttribute('data-ep');slidesOf(d).forEach(function(s,i){out.push({ep:ep,idx:i,el:s});});});}
 else{slidesOf(doc.getElementById('stage')).forEach(function(s,i){out.push({ep:null,idx:i,el:s});});}
 return out;
}
function curInfo(){try{return window.deckInfo?deckInfo():{};}catch(e){return{}};}
function goTo(ent){if(!ent)return;if(ent.ep!=null&&SERIES())deckGo(ent.ep,ent.idx,0);else deckGo(ent.idx,0);}

/* ---------- 상·하단 크롬 ---------- */
var bar=null,topEl=null,botEl=null,crumbEl=null,brandTxt='',pageInput=null,pageEcho=null,
    searchBox=null,searchInput=null,searchList=null,tocBox=null,tocList=null,toastEl=null,toastT=null,
    helpEl=null,helpBtn=null,helpModal=null,helpLastFocus=null,
    prevBtn=null,nextBtn=null,moreBtn=null,morePop=null,pinBtn=null,
    segBox=null,chromePin=false,chromeT=null,chromeHover=false;
function el(tag,cls,txt){var e=doc.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e;}
function toast(msg){if(!toastEl){toastEl=el('div','ed-toast');body.appendChild(toastEl);}toastEl.textContent=msg;toastEl.classList.add('on');clearTimeout(toastT);toastT=setTimeout(function(){toastEl.classList.remove('on');},2600);}
window.edToast=toast;
function press(k){doc.dispatchEvent(new KeyboardEvent('keydown',{key:k,bubbles:true,cancelable:true}));}

/* 24 viewBox 윤곽 아이콘(윤곽선: fill none·stroke currentColor·width 2·round). 라벨은 .ed-tl span. */
var IC={
 toc:'<path d="M3 5h.01M3 12h.01M3 19h.01M8 5h13M8 12h13M8 19h13"/>',
 search:'<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
 notes:'<path d="M4 4h16v12H8l-4 4z"/><path d="M8 9h8M8 12h5"/>',
 terms:'<path d="M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"/>',
 study:'<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
 clock:'<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2.5"/><path d="M9 2h6"/>',
 theme:'<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18v0"/><circle cx="8.5" cy="10" r="1.1"/><circle cx="12" cy="8" r="1.1"/><circle cx="15.5" cy="10" r="1.1"/>',
 print:'<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>',
 help:'<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
 full:'<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
 pin:'<path d="M12 17v5"/><path d="M8 3h8l-1 7 3 3v2H6v-2l3-3z"/>',
 more:'<circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/>',
 prev:'<path d="M15 18l-6-6 6-6"/>',
 next:'<path d="M9 18l6-6-6-6"/>'
};
function ic(name){
 var s=doc.createElementNS('http://www.w3.org/2000/svg','svg');
 s.setAttribute('viewBox','0 0 24 24');s.setAttribute('class','ed-ic');s.setAttribute('aria-hidden','true');
 s.innerHTML=IC[name];return s;
}
/* 도구 버튼: 아이콘+라벨(+선택 kbd). label·title·aria-label·aria-keyshortcuts 일치 */
function toolBtn(icon,label,key,onclick,kbdTxt){
 var b=el('button','ed-tbtn ed-tool');b.type='button';
 var a=label+(key?' ('+key+')':'');
 b.setAttribute('aria-label',a);b.title=a;
 if(key)b.setAttribute('aria-keyshortcuts',key);
 b.appendChild(ic(icon));
 b.appendChild(el('span','ed-tl',label));
 if(kbdTxt)b.appendChild(el('kbd','ed-kbd',kbdTxt));
 b.addEventListener('click',function(e){e.stopPropagation();onclick();});
 return b;
}

/* ---------- 검색 ---------- */
var INDEX=null;
function buildIndex(){
 INDEX=slideEntries().map(function(ent){
  var s=ent.el, c=s.cloneNode(true);
  c.querySelectorAll('.notes,aside,script,style,svg,.sr,.ed-diagram-labels').forEach(function(x){x.remove();});
  var txt=(c.textContent||'').replace(/\s+/g,' ').trim();
  var t=s.querySelector('.title,.big,h2,h1');
  var eb=s.querySelector('.eyebrow');
  ent.title=t?t.textContent.trim():('슬라이드 '+(ent.idx+1));
  ent.eyebrow=eb?eb.textContent.trim():'';
  ent.text=txt;
  return ent;
 });
}
function openSearch(){
 if(!INDEX)buildIndex();
 searchBox.classList.add('on');searchInput.value='';filter('');setTimeout(function(){searchInput.focus();},0);
}
function closeSearch(){if(!searchBox)return;searchBox.classList.remove('on');var a=doc.activeElement;if(a&&a.blur)a.blur();}
function filter(q){
 q=(q||'').trim().toLowerCase();
 searchList.innerHTML='';
 var hits=!q?INDEX.slice(0,60):INDEX.filter(function(e){return e.title.toLowerCase().indexOf(q)>=0||e.text.toLowerCase().indexOf(q)>=0||e.eyebrow.toLowerCase().indexOf(q)>=0;}).slice(0,60);
 if(!hits.length){searchList.appendChild(el('div','ed-sch-empty','일치하는 슬라이드가 없습니다'));return;}
 hits.forEach(function(ent){
  var b=el('button','ed-sch-item');b.type='button';
  var row=el('div','t');row.appendChild(el('span','n',(ent.idx+1)+''));row.appendChild(doc.createTextNode(ent.title));b.appendChild(row);
  var snip=ent.text;if(q&&snip.toLowerCase().indexOf(q)>=0){var p=snip.toLowerCase().indexOf(q);snip='…'+snip.slice(Math.max(0,p-30),p+50)+'…';}
  if(snip)b.appendChild(el('div','s',snip.slice(0,140)));
  b.addEventListener('click',function(){closeSearch();goTo(ent);});
  b._ent=ent;searchList.appendChild(b);
 });
}
function searchKeys(e){
 var items=[].slice.call(searchList.querySelectorAll('.ed-sch-item')),sel=searchList.querySelector('.ed-sch-item.sel'),i=items.indexOf(sel);
 if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();var n=e.key==='ArrowDown'?(i+1):(i-1);n=Math.max(0,Math.min(items.length-1,n));items.forEach(function(x){x.classList.remove('sel');});if(items[n]){items[n].classList.add('sel');items[n].scrollIntoView({block:'nearest'});}}
 else if(e.key==='Enter'){e.preventDefault();var t=sel||items[0];if(t){closeSearch();goTo(t._ent);}}
 else if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeSearch();}
}

/* ---------- 목차 ---------- */
function openToc(){
 if(SERIES()&&body.classList.contains('in-hub'))return;
 buildToc();tocBox.classList.add('on');
 var cur=tocList.querySelector('.is-cur');if(cur)cur.scrollIntoView({block:'center'});
 var f=tocList.querySelector('.is-cur')||tocList.querySelector('.ed-toc-item');if(f)f.focus();
}
function closeToc(){if(!tocBox)return;tocBox.classList.remove('on');var a=doc.activeElement;if(a&&a.blur)a.blur();}
function buildToc(){
 tocList.innerHTML='';
 var ents=slideEntries(),info=curInfo(),lastG=null;
 if(SERIES()&&info&&info.ep!=null){ents=ents.filter(function(e){return String(e.ep)===String(info.ep);});}
 ents.forEach(function(ent){
  var eb=(ent.el.querySelector('.eyebrow')||{}).textContent||'';
  if(eb.trim()!==lastG){lastG=eb.trim();if(lastG)tocList.appendChild(el('div','ed-toc-g',lastG));}
  var t=ent.el.querySelector('.title,.big,h2,h1');
  var b=el('button','ed-toc-item');b.type='button';
  b.appendChild(el('span','n',String(ent.idx+1)));
  b.appendChild(el('span','t',t?t.textContent.trim():('슬라이드 '+(ent.idx+1))));
  if(!SERIES()&&ent.idx===info.slide)b.classList.add('is-cur');
  if(SERIES()&&ent.ep!=null&&String(ent.ep)===String(info.ep)&&ent.idx===info.slide)b.classList.add('is-cur');
  b.addEventListener('click',function(){closeToc();goTo(ent);});
  b._ent=ent;tocList.appendChild(b);
 });
}
function tocKeys(e){
 var items=[].slice.call(tocList.querySelectorAll('.ed-toc-item')),sel=doc.activeElement,i=items.indexOf(sel);
 if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();var n=e.key==='ArrowDown'?(i<0?0:i+1):(i<0?0:i-1);n=Math.max(0,Math.min(items.length-1,n));if(items[n])items[n].focus();}
 else if(e.key==='Enter'&&i>=0){e.preventDefault();closeToc();goTo(items[i]._ent);}
 else if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeToc();}
}

/* ---------- 도움말 모달: #help 의 문구를 2열 단축키 시트로 시각화한다 ---------- */
function buildHelp(){
 if(helpModal)return;
 helpModal=el('div','ed-help-modal');helpModal.setAttribute('role','dialog');
 helpModal.setAttribute('aria-modal','true');helpModal.setAttribute('aria-label','도움말 — 키 안내');
 var box=el('div','ed-hm-box'),head=el('div','ed-hm-h');
 head.appendChild(el('span','ed-hm-t','도움말'));
 var x=el('button','ed-hm-x','닫기 (Esc)');x.type='button';
 x.addEventListener('click',function(){toggleHelpModal(false);});
 head.appendChild(x);box.appendChild(head);
 var list=el('div','ed-hm-list');
 /* #help 의 "키 설명 · 키 설명 …" 문자열을 kbd·설명 쌍으로 나눈다(talk 덱은 talk.js 가 뒤에 덧붙인다) */
 var src=(helpEl?helpEl.textContent:'').replace(/\s+/g,' ').trim();
 src.split('·').forEach(function(item){
  item=item.trim();if(!item)return;
  var m=item.match(/^(\S+)\s+(.+)$/);
  var row=el('div','ed-hm-row'),kk=el('span','ed-hm-k');
  kk.appendChild(el('kbd','ed-kbd',m?m[1]:item));
  row.appendChild(kk);
  row.appendChild(el('span','ed-hm-d',m?m[2]:''));
  list.appendChild(row);
 });
 box.appendChild(list);helpModal.appendChild(box);body.appendChild(helpModal);
 helpModal.addEventListener('click',function(e){if(e.target===helpModal)toggleHelpModal(false);});
 helpModal.addEventListener('keydown',function(e){
  if(e.key==='Escape'){e.preventDefault();e.stopPropagation();toggleHelpModal(false);return;}
  if(e.key==='Tab'){ /* 대화상자 안에서 포커스 순환 */
   var f=[].slice.call(helpModal.querySelectorAll('button'));if(!f.length)return;
   var i=f.indexOf(doc.activeElement);
   if(e.shiftKey&&i<=0){e.preventDefault();f[f.length-1].focus();}
   else if(!e.shiftKey&&i===f.length-1){e.preventDefault();f[0].focus();}
  }
 });
}
function toggleHelpModal(on){
 buildHelp();
 var opening=on===undefined?!helpModal.classList.contains('on'):on;
 if(opening){
  helpLastFocus=doc.activeElement;
  helpModal.classList.add('on');reveal();clearTimeout(chromeT);
  var f=helpModal.querySelector('button');if(f)f.focus();
 }else{
  helpModal.classList.remove('on');
  if(helpLastFocus&&helpLastFocus.focus)helpLastFocus.focus();helpLastFocus=null;
  arm();
 }
}

/* ---------- 크롬 자동 숨김(핀 고정 시 상시) ---------- */
var HIDING_LAYER='.ed-sch.on,.ed-toc.on,.ed-help-modal.on,.st-modal.st-show,.st-print.st-show';
function focusInBars(){var a=doc.activeElement;return a&&((topEl&&topEl.contains(a))||(botEl&&botEl.contains(a)));}
function reveal(){body.classList.add('ed-chrome-on');[topEl,botEl].forEach(function(b){if(b)b.inert=false;});}
function arm(){clearTimeout(chromeT);if(chromePin)return;chromeT=setTimeout(hide,2500);}
function hide(){
 if(chromePin||chromeHover||focusInBars()){arm();return;}
 if(doc.querySelector(HIDING_LAYER)){arm();return;}
 body.classList.remove('ed-chrome-on');
 [topEl,botEl].forEach(function(b){if(b)b.inert=true;});
}
function poke(){reveal();arm();}
function setPin(on){
 chromePin=on;try{localStorage.setItem('ed-chrome-pin',on?'1':'0');}catch(e){}
 if(pinBtn)pinBtn.setAttribute('aria-pressed',on?'true':'false');
 if(on){reveal();clearTimeout(chromeT);}else arm();
}

/* ---------- 진행 세그먼트·단계 점·쪽 번호 ---------- */
function currentEnts(){
 var ents=slideEntries(),info=curInfo();
 if(SERIES()&&info.ep!=null)ents=ents.filter(function(e){return String(e.ep)===String(info.ep);});
 return ents;
}
function buildSegs(){
 var info=curInfo(),ents=currentEnts(),prog=doc.getElementById('progress');
 if(!prog)return;
 prog.innerHTML='';
 if(ents.length>60){prog.classList.remove('is-segs');return;} /* 과밀: 연속 막대 폴백(엔진 scaleX) */
 prog.classList.add('is-segs');
 ents.forEach(function(ent,i){
  var b=el('button','ed-seg');b.type='button';
  var t=ent.el.querySelector('.title,.big,h2,h1');
  b.setAttribute('aria-label',(i+1)+'장 '+(t?t.textContent.trim():''));
  b.title=(i+1)+'장';b.appendChild(el('i'));
  (function(k){b.addEventListener('click',function(e){e.stopPropagation();goTo(currentEnts()[k]);});})(i);
  prog.appendChild(b);
 });
}
function paintSegs(){
 var info=curInfo(),prog=doc.getElementById('progress');
 if(!prog||!prog.classList.contains('is-segs'))return;
 var segs=prog.children,frac;
 for(var i=0;i<segs.length;i++){
  var f=segs[i].querySelector('i');
  if(i<info.slide)frac=1;
  else if(i===info.slide)frac=info.maxStep?(info.step/info.maxStep):1;
  else frac=0;
  f.style.width=(frac*100)+'%';
  segs[i].classList.toggle('is-past',i<info.slide);
  segs[i].setAttribute('aria-current',i===info.slide?'true':'false');
 }
}
function paintPage(){
 var info=curInfo(),c=doc.getElementById('counter');
 if(pageInput)pageInput.value=(info.slide+1);
 if(c){c.textContent='/ '+(info.count||0);c.setAttribute('data-text',(info.slide+1)+' / '+(info.count||0));}
 if(pageEcho)pageEcho.textContent=(info.slide+1)+' / '+(info.count||0);
 if(prevBtn){var atFirst=info.slide===0&&info.step===0;prevBtn.disabled=atFirst;prevBtn.setAttribute('aria-disabled',atFirst?'true':'false');}
 if(nextBtn){var atLast=info.slide===info.count-1&&info.step>=info.maxStep;nextBtn.disabled=atLast;nextBtn.setAttribute('aria-disabled',atLast?'true':'false');}
 if(crumbEl){
  var ents=currentEnts(),ent=ents[info.slide];
  if(ent){var eb=(ent.el.querySelector('.eyebrow')||{}).textContent||'',t=ent.el.querySelector('.title,.big,h2,h1');
   var txt=((eb.trim()?eb.trim()+' · ':'')+(t?t.textContent.trim():'')).replace(/\s+/g,' ').trim();
   /* 크럼브가 덱 제목과 같으면(보통 표지) 브랜드와 문구가 겹치니 생략한다 */
   crumbEl.textContent=(txt===brandTxt)?'':txt;}
 }
}
/* 엔진이 쓰는 <i> 단계 점을 접근 가능한 버튼으로 승격한다(내용은 엔진 소유) */
function upgradeDots(){
 var pips=doc.getElementById('dots');if(!pips)return;
 [].slice.call(pips.querySelectorAll('i')).forEach(function(x,i){
  if(x.getAttribute('role'))return;
  x.setAttribute('role','button');x.setAttribute('tabindex','0');
  x.setAttribute('aria-label','단계 '+(i+1));
 });
}
function gotoStepDot(dot){
 var pips=doc.getElementById('dots');if(!pips||!window.deckGo)return;
 var i=[].slice.call(pips.children).indexOf(dot);if(i<0)return;
 var info=curInfo();
 if(SERIES()&&info.ep!=null)deckGo(info.ep,info.slide,i+1);else deckGo(info.slide,i+1);
}

/* ---------- 더보기 ⋯ 팝오버(좁은 창·compact) ---------- */
var toolOrder=[];
function closePop(){if(morePop)morePop.classList.remove('on');if(moreBtn)moreBtn.setAttribute('aria-expanded','false');}
function togglePop(){if(!morePop)return;var on=!morePop.classList.contains('on');morePop.classList.toggle('on',on);moreBtn.setAttribute('aria-expanded',on?'true':'false');}
function refitChrome(){
 if(!bar||!morePop)return;
 /* 전부 도구 띠로 되돌린 뒤 넘치는 만큼 뒤에서부터 팝오버로 옮긴다 */
 while(morePop.firstChild)bar.appendChild(morePop.firstChild);
 toolOrder.forEach(function(node){bar.appendChild(node);});
 var compact=root.classList.contains('ed-compact');
 if(compact){toolOrder.forEach(function(n){morePop.appendChild(n);});return;}
 var guard=60;
 while(guard-->0&&bar.scrollWidth>bar.clientWidth&&bar.children.length){
  var last=bar.lastElementChild;if(!last)break;
  morePop.insertBefore(last,morePop.firstChild);
 }
}
window.addEventListener('resize',function(){refitChrome();});

/* ---------- 크롬 조립 ---------- */
function buildChrome(){
 var PACK=!!doc.querySelector('meta[name="edu-deck-resource-pack"]');
 var isSheet=root.classList.contains('is-sheet')||root.classList.contains('is-shot');
 try{chromePin=localStorage.getItem('ed-chrome-pin')==='1';}catch(e){}

 topEl=el('div','ed-top');
 var brand=el('div','ed-brand'),t=el('b',null,(doc.title||'').replace(/\s+/g,' ').trim());
 brandTxt=t.textContent;
 crumbEl=el('span','ed-crumb');
 brand.appendChild(t);brand.appendChild(crumbEl);topEl.appendChild(brand);
 bar=el('nav','ed-topbar');bar.setAttribute('aria-label','도구');

 function sep(){var s=el('i','ed-sep');s.setAttribute('aria-hidden','true');return s;}
 var groups=[],g;

 g=[];
 g.push(toolBtn('toc','목차','O',openToc));
 g.push(toolBtn('search','검색','Ctrl+K',openSearch,'/'));
 groups.push(g);

 g=[];
 if(doc.querySelector('.slide .notes, .slide aside.notes')){
  var bn=toolBtn('notes','노트','N',function(){press('n');});
  bn.setAttribute('aria-pressed','false');g.push(bn);
  new MutationObserver(function(){
   var n=doc.getElementById('notes');
   bn.setAttribute('aria-pressed',n&&n.style.display==='block'?'true':'false');
  }).observe(doc.getElementById('notes'),{attributes:true,attributeFilter:['style']});
 }
 var DATA=window.EDU_STUDY||{};
 if(Array.isArray(DATA.glossary)&&DATA.glossary.length){
  g.push(toolBtn('terms','용어','D',function(){press('d');}));
 }
 if(window.EDU_STUDY){
  var bs=toolBtn('study','자습','S',function(){press('s');});
  bs.setAttribute('aria-pressed','false');g.push(bs);
  new MutationObserver(function(){
   bs.setAttribute('aria-pressed',body.classList.contains('st-self')?'true':'false');
  }).observe(body,{attributes:true,attributeFilter:['class']});
 }
 /* 발표 타이머: #ed-clock 을 도구 버튼으로 승격(내용은 talk.js 가 칠한다).
    발표 덱(EDU_STUDY.talk)이나 ?presenter 에서만 만든다 — 기능 없는 덱엔 버튼 자체가 없다 */
 var _pp=new URLSearchParams(location.search);
 if((window.EDU_STUDY&&window.EDU_STUDY.talk)||_pp.has('presenter')){
  var clock=el('button','ed-tbtn ed-tool ed-clock');clock.id='ed-clock';clock.type='button';
  clock.setAttribute('aria-label','타이머 시작·멈춤 (X)');clock.title='타이머 시작·멈춤 (X) · 처음부터 (R · Shift+클릭)';
  clock.setAttribute('aria-keyshortcuts','X');
  clock.appendChild(ic('clock'));clock.appendChild(el('span','t'));
  g.push(clock);
 }
 if(g.length)groups.push(g);

 var P=new URLSearchParams(location.search);
 if(P.has('themes')&&window.eduThemePreview){
  var bt=toolBtn('theme','테마','T',function(){if(window.eduThemePreview)window.eduThemePreview.toggle();});
  groups.push([bt]);
 }

 g=[];
 g.push(toolBtn('print','인쇄','P',function(){press('p');}));
 g.push(toolBtn('full','전체','F',function(){press('f');}));
 if(!PACK&&helpEl){
  helpBtn=toolBtn('help','도움말','H',function(){toggleHelpModal();},'H');
  g.push(helpBtn);
 }
 pinBtn=toolBtn('pin','핀',null,function(){setPin(!chromePin);});
 pinBtn.classList.add('ed-pin');
 pinBtn.setAttribute('aria-pressed',chromePin?'true':'false');
 pinBtn.title='막대 항상 표시 고정';
 g.push(pinBtn);
 groups.push(g);

 groups.forEach(function(gr,i){
  if(i>0)bar.appendChild(sep());
  gr.forEach(function(b){bar.appendChild(b);});
 });
 toolOrder=[].slice.call(bar.children);
 topEl.appendChild(bar);

 moreBtn=el('button','ed-more');moreBtn.type='button';
 moreBtn.setAttribute('aria-label','도구 더보기');moreBtn.setAttribute('aria-expanded','false');
 moreBtn.appendChild(ic('more'));
 moreBtn.addEventListener('click',function(e){e.stopPropagation();togglePop();});
 topEl.appendChild(moreBtn);
 morePop=el('div','ed-chrome-pop');
 body.appendChild(topEl);body.appendChild(morePop);

 /* 하단 막대: 기존 #progress·#dots·#counter 를 옮겨 담는다(엔진이 계속 갱신) */
 botEl=el('div','ed-bot');
 var track=el('div','ed-prog-track');
 var prog=doc.getElementById('progress');if(prog)track.appendChild(prog);
 botEl.appendChild(track);
 var pips=doc.getElementById('dots');
 if(pips){
  pips.removeAttribute('aria-hidden');
  pips.addEventListener('click',function(e){
   var d=e.target.closest&&e.target.closest('i');if(d){e.stopPropagation();gotoStepDot(d);}
  });
  pips.addEventListener('keydown',function(e){
   if(e.key!=='Enter'&&e.key!==' ')return;
   var d=e.target.closest&&e.target.closest('i');if(d){e.preventDefault();e.stopPropagation();gotoStepDot(d);}
  });
  new MutationObserver(upgradeDots).observe(pips,{childList:true});
  botEl.appendChild(pips);
 }
 var pagebox=el('div','ed-pagebox');
 pageInput=el('input','ed-page');pageInput.id='edPage';pageInput.type='text';
 pageInput.setAttribute('inputmode','numeric');pageInput.setAttribute('aria-label','쪽 번호');
 pageInput.addEventListener('keydown',function(e){
  e.stopPropagation();
  if(e.key==='Enter'){
   e.preventDefault();
   var n=parseInt(pageInput.value,10),info=curInfo();
   if(isFinite(n)){n=Math.max(1,Math.min(info.count||1,n));
    if(SERIES()&&info.ep!=null)deckGo(info.ep,n-1,0);else deckGo(n-1,0);}
   pageInput.value=(curInfo().slide+1);pageInput.blur();
  }else if(e.key==='Escape'){e.preventDefault();pageInput.value=(curInfo().slide+1);pageInput.blur();}
 });
 pageInput.addEventListener('input',function(){pageInput.value=pageInput.value.replace(/[^0-9]/g,'');});
 pagebox.appendChild(pageInput);
 var c=doc.getElementById('counter');
 if(c){c.setAttribute('aria-live','polite');c.setAttribute('aria-atomic','true');pagebox.appendChild(c);}
 botEl.appendChild(pagebox);
 var nav=el('div','ed-nav');
 prevBtn=el('button','ed-btn');prevBtn.type='button';
 prevBtn.setAttribute('aria-label','이전 장 (←)');prevBtn.title='이전 장 (←)';
 prevBtn.appendChild(ic('prev'));prevBtn.appendChild(el('span','ed-tl','이전'));
 prevBtn.addEventListener('click',function(e){e.stopPropagation();if(!prevBtn.disabled)press('ArrowLeft');});
 nextBtn=el('button','ed-btn');nextBtn.type='button';
 nextBtn.setAttribute('aria-label','다음 단계·장 (→)');nextBtn.title='다음 단계·장 (→)';
 nextBtn.appendChild(el('span','ed-tl','다음'));nextBtn.appendChild(ic('next'));
 nextBtn.addEventListener('click',function(e){e.stopPropagation();if(!nextBtn.disabled)press('ArrowRight');});
 nav.appendChild(prevBtn);nav.appendChild(nextBtn);botEl.appendChild(nav);
 body.appendChild(botEl);

 /* 막대 숨김 중에도 쪽수는 스크린리더에 읽힌다(시각 숨김은 opacity·inert) */
 pageEcho=el('span','sr');pageEcho.setAttribute('aria-live','polite');body.appendChild(pageEcho);

 /* 자동 숨김 트리거 */
 doc.addEventListener('mousemove',function(e){
  if(e.clientY<40||e.clientY>window.innerHeight-40)poke();
 });
 [topEl,botEl].forEach(function(b){
  b.addEventListener('mouseenter',function(){chromeHover=true;poke();});
  b.addEventListener('mouseleave',function(){chromeHover=false;arm();});
 });
 doc.addEventListener('touchstart',function(){poke();},{passive:true});
 doc.addEventListener('focusin',function(e){if(focusInBars())poke();},true);
 doc.addEventListener('focusout',function(e){arm();},true);
 doc.addEventListener('click',function(e){
  if(morePop&&morePop.classList.contains('on')&&!morePop.contains(e.target)&&e.target!==moreBtn)closePop();
 });

 buildSegs();upgradeDots();
 doc.addEventListener('deckslide',function(){buildSegsIfEp();paintSegs();paintPage();});
 doc.addEventListener('deckstep',function(){paintSegs();paintPage();upgradeDots();});
 paintPage();

 if(chromePin){reveal();}else{reveal();arm();}
 refitChrome();
 if(!isSheet)requestAnimationFrame(refitChrome);
}
var lastEp=null;
function buildSegsIfEp(){
 var info=curInfo(),ep=(info&&info.ep!=null)?String(info.ep):null;
 if(SERIES()&&ep!==lastEp){lastEp=ep;buildSegs();}
}

/* ---------- data-fit: 제목을 1(또는 지정)줄 안에 최대 20% 줄여 맞춘다 ---------- */
function fitTitles(){
 doc.querySelectorAll('.title[data-fit]').forEach(function(t){
  t.style.fontSize='';
  var base=parseFloat(getComputedStyle(t).fontSize)||72,maxL=+(t.getAttribute('data-fit')||1)||1,min=base*0.8,fs=base,g=60;
  var lh=function(){var v=parseFloat(getComputedStyle(t).lineHeight);return isFinite(v)?v:fs*1.15;};
  while(t.offsetHeight>lh()*maxL+2&&fs>min&&g-->0){fs=Math.max(min,fs-1);t.style.fontSize=fs+'px';}
  if(t.offsetHeight>lh()*maxL+2)t.style.fontSize=min+'px';
 });
}
/* ---------- 키 ---------- */
function typing(t){return t&&(t.isContentEditable||/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));}
window.addEventListener('keydown',function(e){
 var k=e.key;
 if(e.isComposing)return;
 var schOn=searchBox&&searchBox.classList.contains('on'),tocOn=tocBox&&tocBox.classList.contains('on'),
     hmOn=helpModal&&helpModal.classList.contains('on');
 if(schOn||tocOn||hmOn){
  if(k==='Escape'){e.preventDefault();e.stopImmediatePropagation();(schOn?closeSearch:(tocOn?closeToc:function(){toggleHelpModal(false);}))();return;}
  if(hmOn&&(k==='h'||k==='H'||k==='ㅗ')){e.preventDefault();e.stopImmediatePropagation();toggleHelpModal(false);return;}
  var inside=e.target&&e.target.closest&&(e.target.closest('.ed-sch')||e.target.closest('.ed-toc')||e.target.closest('.ed-help-modal'));
  if(!inside)e.stopImmediatePropagation(); /* 대화상자 밖의 키가 엔진에 새지 않게 막는다 */
  return;
 }
 if((e.ctrlKey||e.metaKey)&&!e.altKey&&(k==='k'||k==='K')){if(typing(e.target))return;e.preventDefault();openSearch();return;}
 if(e.ctrlKey||e.metaKey||e.altKey)return;
 if(typing(e.target))return;
 if(k==='/'){e.preventDefault();openSearch();return;}
 if(k==='o'||k==='O'||k==='ㅐ'){openToc();return;}
 /* F6 = 막대로 포커스 이동(숨겨진 포커스 방지 — 막대는 숨김 상태에서 inert) */
 if(k==='F6'){e.preventDefault();reveal();arm();var f=bar&&bar.querySelector('button');if(f)f.focus();return;}
 /* H/ㅗ/? = 도움말 모달 토글. 팩 덱의 #help 는 4초 뒤 사라지는 부트 힌트라 대상 아님 */
 if(helpBtn&&(k==='h'||k==='H'||k==='ㅗ'||k==='?')){
  if(doc.querySelector('.st-modal.st-show,.st-print.st-show'))return;
  e.preventDefault();toggleHelpModal();return;}
},true);
/* 모든 키 입력은 막대를 복귀시킨다(실제 단축키 처리는 위 리스너가 순서대로 맡는다) */
window.addEventListener('keydown',function(){poke();},true);

/* ---------- 초기화 ---------- */
function init(){
 if(root.classList.contains('ed-nojs'))return;
 helpEl=doc.getElementById('help');
 buildChrome();

 searchBox=el('div','ed-sch');var sb=el('div','ed-sch-box');
 var sin=el('div','ed-sch-in');searchInput=el('input');searchInput.type='text';searchInput.placeholder='슬라이드 검색…';searchInput.setAttribute('aria-label','슬라이드 검색');
 sin.appendChild(searchInput);sin.appendChild(el('span','kbd','esc'));
 searchList=el('div','ed-sch-list');
 sb.appendChild(sin);sb.appendChild(searchList);searchBox.appendChild(sb);body.appendChild(searchBox);
 searchInput.addEventListener('input',function(){filter(searchInput.value);});
 searchBox.addEventListener('keydown',searchKeys);
 searchBox.addEventListener('click',function(e){if(e.target===searchBox)closeSearch();});

 tocBox=el('div','ed-toc');var tb=el('div','ed-toc-box');
 var th=el('div','ed-toc-h');th.appendChild(el('span',null,'목차'));
 var tx=el('button','ed-toc-x','닫기');tx.type='button';tx.addEventListener('click',closeToc);th.appendChild(tx);
 tocList=el('div','ed-toc-list');tb.appendChild(th);tb.appendChild(tocList);tocBox.appendChild(tb);body.appendChild(tocBox);
 tocBox.addEventListener('keydown',tocKeys);
 tocBox.addEventListener('click',function(e){if(e.target===tocBox)closeToc();});

 var help=doc.getElementById('help');
 if(help)help.textContent=help.textContent.replace('F 전체화면','O 목차 · / 검색 · F 전체화면');
 fitTitles();
 var rT=null;window.addEventListener('resize',function(){clearTimeout(rT);rT=setTimeout(fitTitles,120);});
 if(doc.fonts&&doc.fonts.ready)doc.fonts.ready.then(function(){fitTitles();});
 doc.addEventListener('edmode',fitTitles);
 doc.addEventListener('deckslide',fitTitles); /* 새로 켜진 장만 높이가 있다 — 동기로 재야 검사기가 곧바로 잰다 */
}
if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',init);else init();
})();
