/* viewer.js — 검색(Ctrl+K·/), 목차(O·상단 단추), data-fit 제목 맞춤, 엔진 준비 표시.
   solo·pack·series 포털에 공통 탑재. series 에서는 편 안(.deck.on) 기준으로 동작한다. */
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
function curInfo(){try{return window.deckInfo?deckInfo():{};}catch(e){return{};}}
function goTo(ent){if(!ent)return;if(ent.ep!=null&&SERIES())deckGo(ent.ep,ent.idx,0);else deckGo(ent.idx,0);}

/* ---------- 상단 바 ---------- */
var bar=null,searchBox=null,searchInput=null,searchList=null,tocBox=null,tocList=null,toastEl=null,toastT=null,helpEl=null,helpBtn=null;
function el(tag,cls,txt){var e=doc.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e;}
function toast(msg){if(!toastEl){toastEl=el('div','ed-toast');body.appendChild(toastEl);}toastEl.textContent=msg;toastEl.classList.add('on');clearTimeout(toastT);toastT=setTimeout(function(){toastEl.classList.remove('on');},2600);}
window.edToast=toast;

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
function toggleHelp(on){if(!helpEl)return;helpEl.classList.toggle('on',on===undefined?!helpEl.classList.contains('on'):on);}
window.addEventListener('keydown',function(e){
 var k=e.key;
 if(e.isComposing)return;
 var schOn=searchBox&&searchBox.classList.contains('on'),tocOn=tocBox&&tocBox.classList.contains('on'),
     helpOn=helpEl&&helpEl.classList.contains('on');
 if(schOn||tocOn||helpOn){
  if(k==='Escape'){e.preventDefault();e.stopImmediatePropagation();(schOn?closeSearch:(tocOn?closeToc:function(){toggleHelp(false);}))();return;}
  if(helpOn&&(k==='h'||k==='H'||k==='ㅗ')){e.preventDefault();e.stopImmediatePropagation();toggleHelp(false);return;}
  var inside=e.target&&e.target.closest&&(e.target.closest('.ed-sch')||e.target.closest('.ed-toc')||e.target.closest('#help'));
  if(!inside)e.stopImmediatePropagation(); /* 대화상자 밖의 키가 엔진에 새지 않게 막는다 */
  return;}
 if((e.ctrlKey||e.metaKey)&&!e.altKey&&(k==='k'||k==='K')){if(typing(e.target))return;e.preventDefault();openSearch();return;}
 if(e.ctrlKey||e.metaKey||e.altKey)return;
 if(typing(e.target))return;
 if(k==='/'){e.preventDefault();openSearch();return;}
 if(k==='o'||k==='O'||k==='ㅐ'){openToc();return;}
 /* H/ㅗ = 도움말 토글. 팩 덱의 #help 는 4초 뒤 사라지는 부트 힌트라 대상 아님 */
 if(helpBtn&&(k==='h'||k==='H'||k==='ㅗ')){
  if(doc.querySelector('.st-modal.st-show,.st-print.st-show'))return;
  e.preventDefault();toggleHelp();return;}
},true);

/* ---------- 초기화 ---------- */
function init(){
 if(root.classList.contains('ed-nojs'))return;
 bar=el('div','ed-topbar');
 var bT=el('button','ed-tbtn','목차');bT.type='button';bT.setAttribute('aria-label','목차 열기 (O)');
 bT.addEventListener('click',openToc);
 var bS=el('button','ed-tbtn','검색');bS.type='button';bS.setAttribute('aria-label','검색 (Ctrl+K)');
 bS.addEventListener('click',openSearch);
 var clock=el('span','ed-clock');clock.id='ed-clock';
 bar.appendChild(clock);bar.appendChild(bT);bar.appendChild(bS);
 /* 도움말(H) — 검색 옆 세 번째 단추. 팩 덱 #help 는 부트 힌트라 이 단추는 legacy 전용 */
 helpEl=doc.getElementById('help');
 if(!doc.querySelector('meta[name="edu-deck-resource-pack"]')&&helpEl){
  helpBtn=el('button','ed-tbtn');helpBtn.type='button';helpBtn.setAttribute('aria-label','도움말 (H)');
  var ic=el('span',null,'?');ic.setAttribute('aria-hidden','true');ic.style.fontWeight='800';
  helpBtn.appendChild(ic);helpBtn.appendChild(doc.createTextNode(' 도움말(H)'));
  helpBtn.addEventListener('click',function(){toggleHelp();});
  bar.appendChild(helpBtn);}
 body.appendChild(bar);

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
