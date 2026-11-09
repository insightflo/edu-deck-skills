/*
  자습 레이어(클린룸 재작성): 자습 모드(S 키), 인쇄(P 키 — 한 장 요약·발표 대본),
  용어집(D 키), 확인 문제(.chk) 채점과 복습 안내.
  [하는 일] 발표용 덱을 혼자 보는 사람이 장마다 발표자 노트를 읽고, 한 장 요약과
    발표 대본을 A4로 인쇄하고, 용어를 찾고, 확인 문제를 풀 수 있게 한다.
  [안 하는 일] 덱 원고(슬라이드 마크업)를 고치지 않는다. aside.notes,
    data-archetype="closing"/"rules-dark", .chk 마크업을 읽어 화면 요소를 만든다.
    이 파일이 만드는 요소의 클래스는 st- 로 시작해 원고 클래스와 섞이지 않는다.
  [입력] window.EDU_STUDY — 조립기가 넣는 데이터. 없어도 동작한다.
    단일 덱(build_deck.py, deck.json): summary={…} · glossary=[{term,en,alias,plain,slide}]
    시리즈 포털(build_series.py, series.json): summaries={편:summary} · glossary=[{…,ep}] · meta={편:{label,title}}
  [두 가지 덱] #stage 아래에 .deck[data-ep] 포장이 있으면 시리즈 포털이다.
    시리즈는 엔진의 deckGo(ep,i,st) 와 편 단위 저장 키를 쓰고, 없으면 단일 덱으로
    deckGo(i,st) 와 덱 파일 단위 키를 쓴다. 분기는 PORTAL 플래그 하나로 갈린다.
  [연결] 발표 엔진의 deckslide 이벤트와 window.deckGo 를 쓴다. 시리즈 엔진이
    목차에서 진도를 지우면 edeck-reset 이벤트로 확인 문제 기록도 같이 지운다.
    window.studyApi 는 시험용 진입점이다.
*/
(function(){
  'use strict';
  var DATA=window.EDU_STUDY||{};
  var PORTAL=!!document.querySelector('#stage > .deck');
  var FILEKEY=(decodeURIComponent(location.pathname.split('/').pop())||'deck');
  var DOC_SUMMARY=(DATA.summary&&typeof DATA.summary==='object'&&!Array.isArray(DATA.summary))?DATA.summary:null;
  var EP_SUMMARIES=(PORTAL&&DATA.summaries&&typeof DATA.summaries==='object'&&!Array.isArray(DATA.summaries))?DATA.summaries:{};
  var EP_META=(PORTAL&&DATA.meta&&typeof DATA.meta==='object'&&!Array.isArray(DATA.meta))?DATA.meta:{};
  var TERMS=Array.isArray(DATA.glossary)?DATA.glossary.filter(function(g){ return g&&g.term; }):[];
  var KEY_SELF='edeck-selfstudy', KEY_FOLD='edeck-selfstudy-fold';
  var KEY_QUIZ='edeck-chk-'+FILEKEY;               /* 단일 덱: 파일 이름 단위 기록 */
  var KEY_QUIZ_EP='edeck-ser-chk-'+FILEKEY+'-';    /* 시리즈: 파일 + 편 단위 기록 */

  /* ---------- 작은 도우미 ---------- */
  function store(k,v){ try{ if(v===undefined) return localStorage.getItem(k); localStorage.setItem(k,v); }catch(e){ return null; } }
  function q(sel,root){ return (root||document).querySelector(sel); }
  function qa(sel,root){ return [].slice.call((root||document).querySelectorAll(sel)); }
  function mk(tag,cls,text){ var e=document.createElement(tag); if(cls) e.className=cls; if(text!=null) e.textContent=text; return e; }
  function mkBtn(cls,text){ var b=mk('button',cls,text); b.type='button'; return b; }
  function squash(s){ return String(s==null?'':s).replace(/\s+/g,' ').trim(); }
  function linesOf(x){ if(Array.isArray(x)) return x.map(squash).filter(Boolean); x=squash(x); return x?[x]:[]; }
  function plainText(node){ /* 화면 글자를 한 줄로: <br>은 띄어쓰기, 노트·스크립트는 뺀다 */
    if(!node) return '';
    var c=node.cloneNode(true);
    qa('br',c).forEach(function(b){ b.parentNode.replaceChild(document.createTextNode(' '),b); });
    qa('aside,.notes,script,style',c).forEach(function(x){ x.parentNode.removeChild(x); });
    return squash(c.textContent);
  }
  function deckEl(ep){ return q('#stage > .deck[data-ep="'+String(ep==null?'':ep).replace(/[^0-9A-Za-z_-]/g,'')+'"]'); }
  function liveDeck(){ return q('#stage > .deck.on'); }
  function allDecks(){ return qa('#stage > .deck'); }
  function epNow(){ var d=liveDeck(); return d?String(d.getAttribute('data-ep')||''):''; }
  function epOf(node){ if(!PORTAL) return ''; var d=node&&node.closest?node.closest('.deck'):null; return d?String(d.getAttribute('data-ep')||''):epNow(); }
  function epTag(ep){ var d=deckEl(ep); return d?squash(d.getAttribute('data-label')):''; }
  function epTitle(ep){ /* "3편 스킬" 꼴: series meta 의 title 이 있으면 붙인다 */
    if(!PORTAL) return '';
    var m=EP_META[String(ep)], t=m&&squash(m.title)?squash(m.title):'';
    return (epTag(ep)+' '+t).trim()||(''+ep+'편');
  }
  function atHub(){ return PORTAL&&document.body.classList.contains('in-hub'); }
  function pickedEp(){ /* 목차에서 고른 편(.sel 카드), 없으면 첫 편 */
    if(!PORTAL) return '';
    var c=q('#hub [data-ep].sel');
    if(c) return String(c.getAttribute('data-ep'));
    var first=allDecks()[0];
    return first?String(first.getAttribute('data-ep')||''):'';
  }
  function epForPrint(){ return atHub()?pickedEp():epNow(); }
  function sheets(root){ /* 단일 덱: 무대 직속 장. 시리즈: 지금(또는 노드가 속한) 편의 장 */
    if(!PORTAL) return qa('#stage > .slide');
    var d=root?((root.classList&&root.classList.contains('deck'))?root:root.closest?root.closest('.deck'):null):liveDeck();
    return qa('.slide',d);
  }
  function liveSheet(){ return PORTAL?q('#stage > .deck.on > .slide.active'):q('#stage > .slide.active'); }
  function sheetName(s){
    var t=plainText(q('.title,.big,h1,h2',s));
    if(!t) t=plainText(q('.eyebrow',s));
    return t||'제목 없는 장';
  }
  function noteSplit(s){ /* 발표자 노트: "출처:" 줄은 따로 모은다 */
    var n=s&&q('aside.notes',s); if(!n) return null;
    var raw=String(n.textContent||'').split(/\n+/).map(squash).filter(Boolean), body=[], refs=[];
    raw.forEach(function(l){ (/^출처\s*[:：]/.test(l)?refs:body).push(l); });
    return {body:body,refs:refs};
  }
  function toPx(millimeters){ return millimeters*96/25.4; }
  function docName(){ return squash(document.title)||'교육 자료'; }
  function jump(idx,ep,st){ /* 장 이동. st 생략 시 단일 덱은 마지막 단계, 시리즈는 첫 단계 */
    if(PORTAL){ window.deckGo(ep==null?epNow():ep,idx,st==null?0:st); }
    else window.deckGo(idx,st);
  }

  /* ---------- 모달 하나씩, 알림 한 줄 ---------- */
  var openLayer=null;
  function showLayer(m){ hideLayer(); openLayer=m; m.classList.add('st-show'); }
  function hideLayer(){
    if(!openLayer) return;
    openLayer.classList.remove('st-show');
    if(openLayer===printView){ document.body.classList.remove('st-printing'); a4Page(false); }
    openLayer=null;
  }
  var toastBox=mk('div','st-toast'), toastTimer=null;
  toastBox.setAttribute('role','status');
  function toast(msg){
    toastBox.textContent=msg; toastBox.classList.add('st-show');
    clearTimeout(toastTimer); toastTimer=setTimeout(function(){ toastBox.classList.remove('st-show'); },2600);
  }
  /* 인쇄 미리보기가 열린 동안만 @page 를 A4 로 바꾼다. 닫으면 평소 규칙(쪽마다 한 슬라이드)으로 돌아간다 */
  var pageRule=null;
  function a4Page(on){
    if(on&&!pageRule){ pageRule=document.createElement('style'); pageRule.textContent='@page{size:A4;margin:14mm}'; document.head.appendChild(pageRule); }
    else if(!on&&pageRule){ pageRule.parentNode.removeChild(pageRule); pageRule=null; }
  }

  /* =========================================================
     1. 자습 모드(S): 화면 아래 고정 패널에 장 설명을 붙인다
     ========================================================= */
  var selfOn=store(KEY_SELF)==='1', folded=store(KEY_FOLD)==='1';
  var panel=mk('div','st-panel'); panel.id='st-panel';
  panel.setAttribute('role','region'); panel.setAttribute('aria-label','자습 설명');
  var pWrap=mk('div','st-pin');
  var pBar=mk('div','st-ph');
  var pTag=mk('span','st-ptag','자습 설명'), pPos=mk('span','st-ppos'), pHint=mk('span','st-hint');
  var pPrev=mkBtn('st-pbtn st-prev','← 이전'), pNext=mkBtn('st-pbtn st-next st-main','다음 →');
  var pTerms=mkBtn('st-pbtn st-tool','용어집'), pPrint=mkBtn('st-pbtn st-tool','인쇄');
  var pFold=mkBtn('st-pbtn st-fold',''), pOff=mkBtn('st-pbtn st-off','자습 끄기');
  pTerms.title='용어집 (D)'; pPrint.title='인쇄 (P)'; pOff.title='자습 모드 끄기 (S)';
  var pGap=mk('span','st-sp');
  [pTag,pPos,pHint,pGap,pPrev,pNext,pTerms,pPrint,pFold,pOff].forEach(function(x){ pBar.appendChild(x); });
  var pText=mk('div','st-pb'); pText.setAttribute('aria-live','polite'); pText.tabIndex=0;
  pWrap.appendChild(pBar); pWrap.appendChild(pText); panel.appendChild(pWrap);

  function paintPanel(){
    var s=liveSheet();
    pFold.textContent=folded?'설명 펼치기':'접기';
    pFold.setAttribute('aria-expanded',folded?'false':'true');
    if(atHub()){ /* 목차에서는 설명 대상 장이 없으므로 안내 문구만 */
      pPos.textContent='목차';
      pText.innerHTML='';
      pText.appendChild(mk('p','st-empty','목차 화면입니다. 편을 열면 장마다 설명이 여기에 붙습니다.'));
      paintHint();
      return;
    }
    if(!s) return;
    var all=sheets(s), i=all.indexOf(s);
    pPos.textContent=(PORTAL?epTag(epNow())?epTag(epNow())+' · ':(epNow()===''?'':'편 '):'')+(i+1)+' / '+all.length+'장';
    pText.innerHTML='';
    var np=noteSplit(s);
    if(!np||!np.body.length&&!np.refs.length){ pText.appendChild(mk('p','st-empty','이 장에는 따로 붙은 설명이 없습니다. 화면을 천천히 읽고 다음으로 넘어가세요.')); }
    else{
      np.body.forEach(function(l){ pText.appendChild(mk('p','st-txt',l)); });
      np.refs.forEach(function(l){ pText.appendChild(mk('p','st-src',l)); });
    }
    var cs=quizTally();
    if(cs&&cs.done){ pText.appendChild(mk('p','st-chk','확인 문제 '+cs.ok+'/'+cs.done+' 맞음'+(cs.ng.length?' · 다시 볼 곳: '+cs.ng.map(function(x){ return x+'장'; }).join(', '):''))); }
    pText.scrollTop=0;
    paintHint();
  }
  function paintHint(){
    var s=liveSheet(); if(!s){ pHint.textContent=''; return; }
    var dots=qa('#dots i'), lit=dots.filter(function(x){ return x.classList.contains('on'); }).length;
    var all=sheets(s), last=all.indexOf(s)===all.length-1;
    if(lit<dots.length) pHint.textContent='→ 다음 단계 ('+lit+'/'+dots.length+')';
    else pHint.textContent=last?'마지막 장입니다':'→ 다음 장';
    pHint.classList.toggle('st-hint-on',lit<dots.length);
  }
  function fitStage(){ /* 패널 높이만큼 무대 비율·위치를 조정한다(엔진이 읽는 CSS 변수) */
    var b=document.body;
    if(!selfOn||document.documentElement.classList.contains('ed-compact')){
      b.style.removeProperty('--st-sc'); b.style.removeProperty('--st-top');
      panel.style.removeProperty('--st-k'); panel.style.removeProperty('--st-w'); return;
    }
    var W=window.innerWidth, H=window.innerHeight;
    var k=Math.max(Math.min(W/1920,H/1080),0.62);
    panel.style.setProperty('--st-k',k.toFixed(4));
    var ph=panel.offsetHeight||0, room=Math.max(160,H-ph);
    var sc=Math.min(W/1920,room/1080);
    b.style.setProperty('--st-sc',sc.toFixed(5));
    b.style.setProperty('--st-top',(room/2).toFixed(1)+'px');
    panel.style.setProperty('--st-w',Math.max(560,Math.round(1920*sc))+'px');
  }
  function setSelf(on,quiet){
    selfOn=!!on; store(KEY_SELF,selfOn?'1':'0');
    document.body.classList.toggle('st-self',selfOn);
    document.body.classList.toggle('st-fold',folded);
    paintPanel(); fitStage();
    if(!quiet) toast(selfOn?'자습 모드를 켰습니다. 장마다 설명이 아래에 나옵니다. (S 끄기 · D 용어집 · P 인쇄)':'자습 모드를 껐습니다. (S로 다시 켜기)');
  }
  function setFold(f){ folded=!!f; store(KEY_FOLD,folded?'1':'0'); document.body.classList.toggle('st-fold',folded); paintPanel(); fitStage(); }
  function fakeKey(key){ document.dispatchEvent(new KeyboardEvent('keydown',{key:key,bubbles:true,cancelable:true})); }
  pPrev.addEventListener('click',function(){ fakeKey('ArrowLeft'); });
  pNext.addEventListener('click',function(){ fakeKey('ArrowRight'); });
  pFold.addEventListener('click',function(){ setFold(!folded); });
  pOff.addEventListener('click',function(){ setSelf(false); });
  pTerms.addEventListener('click',function(){ openGlossary(); });
  pPrint.addEventListener('click',function(){ openPicker(); });

  /* =========================================================
     2. 인쇄(P): 한 장 요약 · 발표 대본을 A4 문서로 조립해 미리 본다
     ========================================================= */
  var printView=mk('div','st-print'); printView.id='st-print';
  var pvBar=mk('div','st-prbar'), pvTitle=mk('span','st-prtitle'), pvGap=mk('span','st-sp');
  var pvGo=mkBtn('st-mbtn st-main','인쇄'), pvClose=mkBtn('st-mbtn','닫기');
  var pvHint=mk('span','st-prnote','A4 용지로 인쇄됩니다. PDF로 저장하려면 인쇄 창에서 "PDF로 저장"을 고르세요.');
  [pvTitle,pvHint,pvGap,pvGo,pvClose].forEach(function(x){ pvBar.appendChild(x); });
  var pvScroll=mk('div','st-prscroll');
  printView.appendChild(pvBar); printView.appendChild(pvScroll);
  printView.setAttribute('role','dialog'); printView.setAttribute('aria-modal','true'); printView.setAttribute('aria-label','인쇄 미리보기');
  pvGo.addEventListener('click',function(){ try{ window.print(); }catch(e){} });
  pvClose.addEventListener('click',hideLayer);

  var printEp='';   /* 시리즈 전용: 인쇄 대상 편 번호 */
  function printSheets(){ return PORTAL?sheets(deckEl(printEp)||liveDeck()):sheets(); }
  function printWho(){ return PORTAL?epTitle(printEp):docName(); }
  function printData(){ return PORTAL?EP_SUMMARIES[String(printEp)]||null:DOC_SUMMARY; }
  function docMast(kind){
    var hd=mk('div','st-dh');
    var top=mk('div','st-dtop'); top.appendChild(mk('span','st-dseries',docName()+' · '+kind)); hd.appendChild(top);
    hd.appendChild(mk('h1','st-dtitle',printWho()||docName()));
    return hd;
  }
  function block(title,items,ordered,cls){
    if(!items.length) return null;
    var s=mk('section','st-sec'+(cls?' '+cls:'')); s.appendChild(mk('h2','st-sech',title));
    var l=mk(ordered?'ol':'ul','st-list'); items.forEach(function(t){ l.appendChild(mk('li','',t)); }); s.appendChild(l);
    return s;
  }
  function termEntry(term){
    var t=squash(term).toLowerCase();
    for(var i=0;i<TERMS.length;i++){ var g=TERMS[i]; if(squash(g.term).toLowerCase()===t||squash(g.en).toLowerCase()===t) return g; }
    return null;
  }
  /* 한 장 요약: summary 데이터가 있으면 그대로 펼치고, 없으면 마무리 장(closing)의
     큰 문장·알약과 규칙 장(rules-dark)의 항목에서 뽑아 만든다(원고 무수정 원칙) */
  function pageSummary(){
    var SM=printData();
    var paper=mk('div','st-paper st-sum'), pin=mk('div','st-ppin');
    paper.appendChild(pin);
    pin.appendChild(docMast('한 장 요약'));
    var one='', remember=[], caution=[], terms=[];
    if(SM){
      one=squash(SM.one_line); remember=linesOf(SM.remember); caution=linesOf(SM.caution); terms=linesOf(SM.terms);
      var g=mk('div','st-grid');
      [block('핵심',linesOf(SM.points),true),block('오늘의 세 줄',remember,true,'st-hot')].forEach(function(x){ if(x) g.appendChild(x); });
      if(g.children.length) pin.appendChild(g);
      if(squash(SM.analogy)){ var an=mk('p','st-ana'); an.appendChild(mk('span','st-anatag','비유')); an.appendChild(document.createTextNode(squash(SM.analogy))); pin.appendChild(an); }
      var t=block('이렇게 쓰면 좋습니다',linesOf(SM['try']),false); if(t) pin.appendChild(t);
    }else{
      var closing=printSheets().filter(function(s){ return s.getAttribute('data-archetype')==='closing'; })[0];
      if(closing){
        var big=q('.big',closing); if(big) one=plainText(big);
        qa('.pill',closing).forEach(function(p){ var t=squash(p.textContent); if(t) remember.push(t); });
      }
      var rules=printSheets().filter(function(s){ return s.getAttribute('data-archetype')==='rules-dark'; })[0];
      if(rules) qa('h3',rules).forEach(function(h){ var t=squash(h.textContent); if(t) caution.push(t); });
      if(remember.length){ var sec=mk('section','st-sec st-hot'); sec.appendChild(mk('h2','st-sech','오늘의 세 줄'));
        var ol=mk('ol','st-list st-wide'); remember.forEach(function(t){ ol.appendChild(mk('li','',t)); }); sec.appendChild(ol); pin.appendChild(sec); }
    }
    if(one) pin.insertBefore(mk('p','st-one',one), pin.children[1]||null);
    if(!SM) pin.appendChild(mk('p','st-pending',PORTAL?'한 장 요약의 핵심·주의 목록은 series.json 편 항목의 summary 키로 더 채울 수 있습니다.':'한 장 요약의 핵심·주의 목록은 deck.json 의 summary 키로 더 채울 수 있습니다.'));
    if(caution.length){ var c=block('주의할 점',caution,false,'st-warn'); if(c) pin.appendChild(c); }
    if(terms.length){
      var ts=mk('section','st-sec st-terms'); ts.appendChild(mk('h2','st-sech','핵심 용어'));
      var tl=mk('dl','st-tl'), rest=[];
      terms.forEach(function(t){
        var g=termEntry(t); if(!g||!squash(g.plain)){ rest.push(t); return; }
        var row=mk('div','st-trow'), dt=mk('dt','',t);
        if(squash(g.en)&&squash(g.en)!==t) dt.appendChild(mk('span','st-ten',' '+squash(g.en)));
        row.appendChild(dt); row.appendChild(mk('dd','',squash(g.plain)+(squash(g.alias)?' (비유: '+squash(g.alias)+')':'')));
        tl.appendChild(row);
      });
      if(tl.children.length) ts.appendChild(tl);
      if(rest.length) ts.appendChild(mk('p','st-tmore',(tl.children.length?'그 밖의 용어: ':'')+rest.join(' · ')));
      pin.appendChild(ts);
    }
    var ft=mk('div','st-dfoot'); ft.appendChild(mk('span','',printWho()||docName())); ft.appendChild(mk('span','','한 장 요약')); pin.appendChild(ft);
    return paper;
  }
  function pageScript(){
    var paper=mk('div','st-paper st-script'), pin=mk('div','st-ppin');
    paper.appendChild(pin);
    pin.appendChild(docMast('발표 대본'));
    var all=printSheets();
    pin.appendChild(mk('p','st-intro','장마다 화면 제목과 발표자 노트를 순서대로 옮겼습니다. 화면을 넘기며 그대로 읽으면 됩니다. 모두 '+all.length+'장.'));
    all.forEach(function(s,i){
      var b=mk('section','st-blk');
      var h=mk('h2','st-bh'); h.appendChild(mk('span','st-bn',(i+1)+'장')); h.appendChild(document.createTextNode(sheetName(s))); b.appendChild(h);
      var np=noteSplit(s);
      if(!np||!np.body.length&&!np.refs.length) b.appendChild(mk('p','st-bnone','(노트 없음)'));
      else{ np.body.forEach(function(l){ b.appendChild(mk('p','st-bt',l)); }); np.refs.forEach(function(l){ b.appendChild(mk('p','st-bsrc',l)); }); }
      pin.appendChild(b);
    });
    return paper;
  }
  function shrinkToPage(paper){ /* 한 장 요약이 A4 한 장을 넘기면 글자를 조금씩 줄인다 */
    var pin=q('.st-ppin',paper), limit=toPx(297-28)-6;
    for(var f=1;f>=0.62;f-=0.03){ paper.style.setProperty('--st-fs',f.toFixed(2)); if(pin.offsetHeight<=limit) break; }
  }
  function openPrint(kind,ep){
    if(PORTAL) printEp=(ep==null||ep==='')?String(epForPrint()):String(ep);
    pvScroll.innerHTML='';
    var paper=kind==='script'?pageScript():pageSummary();
    pvScroll.appendChild(paper);
    pvTitle.textContent=(kind==='script'?'발표 대본':'한 장 요약')+' 미리보기 · '+(PORTAL?epTitle(printEp)+' — ':'')+docName();
    printView.setAttribute('data-kind',kind==='script'?'script':'summary');
    showLayer(printView); document.body.classList.add('st-printing'); a4Page(true);
    if(kind!=='script') shrinkToPage(paper);
    pvScroll.scrollTop=0; pvGo.focus();
  }
  /* 인쇄할 자료 고르기 */
  var picker=mk('div','st-modal st-chooser'); picker.id='st-choose';
  var pkBox=mk('div','st-mbox st-chbox'), pkTitle=mk('h2','st-mh','인쇄 · '+docName()), pkSub=mk('p','st-msub','어떤 자료를 인쇄할까요?');
  var pkSum=mkBtn('st-mbtn st-main st-big','1  한 장 요약'), pkScr=mkBtn('st-mbtn st-main st-big','2  발표 대본'), pkX=mkBtn('st-mbtn','닫기');
  var pkRow=mk('div','st-chrow'); pkRow.appendChild(pkSum); pkRow.appendChild(pkScr);
  [pkTitle,pkSub,pkRow,pkX].forEach(function(x){ pkBox.appendChild(x); }); picker.appendChild(pkBox);
  picker.setAttribute('role','dialog'); picker.setAttribute('aria-modal','true'); picker.setAttribute('aria-label','인쇄할 자료 고르기');
  function openPicker(){ /* 시리즈에서는 지금(또는 목차에서 고른) 편이 인쇄 대상 */
    if(PORTAL) pkTitle.textContent='인쇄 · '+epTitle(epForPrint());
    showLayer(picker); pkSum.focus();
  }
  pkSum.addEventListener('click',function(){ openPrint('summary'); });
  pkScr.addEventListener('click',function(){ openPrint('script'); });
  pkX.addEventListener('click',hideLayer);

  /* =========================================================
     3. 용어집(D): glossary 데이터로 만든다. slide 키 또는 본문 찾기로 그 장으로 간다
     ========================================================= */
  var gloss=mk('div','st-modal st-gloss'); gloss.id='st-gloss';
  gloss.setAttribute('role','dialog'); gloss.setAttribute('aria-modal','true'); gloss.setAttribute('aria-label','용어집');
  var gBox=mk('div','st-mbox st-glbox');
  var gHead=mk('div','st-mhead'); gHead.appendChild(mk('h2','st-mh','용어집')); var gX=mkBtn('st-mbtn','닫기 (Esc)'); gHead.appendChild(mk('span','st-sp')); gHead.appendChild(gX);
  var gFind=mk('input','st-gq'); gFind.type='search'; gFind.placeholder='용어 찾기 (예: 컨텍스트, 책상, context)'; gFind.setAttribute('aria-label','용어 찾기');
  var gCount=mk('p','st-gcnt'), gList=mk('div','st-glist');
  [gHead,gFind,gCount,gList].forEach(function(x){ gBox.appendChild(x); }); gloss.appendChild(gBox);
  gX.addEventListener('click',hideLayer);
  function termSheet(g){ /* 용어가 실린 장. 시리즈는 {ep,idx}, 단일 덱은 idx. 찾지 못하면 -1 */
    var ep=PORTAL?String(g.ep!=null?g.ep:epNow()):'';
    var all=PORTAL?sheets(deckEl(ep)||liveDeck()):sheets();
    var found=function(i){ return PORTAL?{ep:ep,idx:i}:i; };
    if(+g.slide>0&&+g.slide<=all.length) return found(+g.slide-1);
    var t=squash(g.term), head=squash(t.split('(')[0]), txt=all.map(plainText);
    var tries=[t,head].concat(t.split(/[\/,·(]/).map(function(x){ return squash(x.replace(')','')); })).filter(function(x){ return x&&x.length>=2; });
    for(var c=0;c<tries.length;c++){ for(var i=1;i<all.length;i++){ if(txt[i].indexOf(tries[c])>=0) return found(i); } }
    var en=squash(g.en).toLowerCase();
    if(en.length>=3) for(var i=1;i<all.length;i++){ if(txt[i].toLowerCase().indexOf(en)>=0) return found(i); }
    return found(-1);
  }
  function paintGloss(){
    var f=squash(gFind.value).toLowerCase();
    gList.innerHTML='';
    if(!TERMS.length){ gCount.textContent=''; gList.appendChild(mk('p','st-gempty',PORTAL?'이 시리즈에는 용어집이 없습니다. series.json 의 glossary 키로 용어를 넣으면 여기에 나옵니다.':'이 덱에는 용어집이 없습니다. deck.json 의 glossary 키로 용어를 넣으면 여기에 나옵니다.')); return; }
    var hits=TERMS.filter(function(g){ return !f||[g.term,g.en,g.alias,g.plain].map(function(x){ return squash(x).toLowerCase(); }).join(' ').indexOf(f)>=0; });
    gCount.textContent=f?'"'+squash(gFind.value)+'" 찾은 용어 '+hits.length+'개 / 전체 '+TERMS.length+'개':'전체 '+TERMS.length+'개';
    if(!hits.length){ gList.appendChild(mk('p','st-gempty','찾는 용어가 없습니다. 다른 말로 찾아보세요.')); return; }
    hits.forEach(function(g){
      var it=mk('div','st-gi'), tx=mk('div','st-gtx'), top=mk('p','st-gt');
      top.appendChild(mk('b','st-gterm',squash(g.term)));
      if(squash(g.en)) top.appendChild(mk('span','st-gen',squash(g.en)));
      if(squash(g.alias)) top.appendChild(mk('span','st-gal','비유: '+squash(g.alias)));
      tx.appendChild(top);
      if(squash(g.plain)) tx.appendChild(mk('p','st-gp',squash(g.plain)));
      it.appendChild(tx);
      var r=termSheet(g), idx=PORTAL?r.idx:r, ep=PORTAL?r.ep:'';
      if(PORTAL&&squash(epTag(ep))) top.appendChild(mk('span','st-gen',epTag(ep)));
      if(idx>=0){ var gb=mkBtn('st-mbtn st-go',(PORTAL?(epTag(ep)?epTag(ep)+' · ':''):'')+(idx+1)+'장 보기'); gb.setAttribute('data-idx',idx); if(PORTAL) gb.setAttribute('data-ep',ep); it.appendChild(gb); }
      gList.appendChild(it);
    });
  }
  function openGlossary(){ gFind.value=''; paintGloss(); showLayer(gloss); gList.scrollTop=0; setTimeout(function(){ try{ gFind.focus(); }catch(e){} },0); }
  gFind.addEventListener('input',paintGloss);

  /* =========================================================
     4. 확인 문제(.chk): 틀리면 해설과 "○장 다시 보기"를 보여 준다(진행은 막지 않음)
        원고: <div class="chk" data-review="열쇠"> <p class="chk-q"><span class="chk-n">1</span>질문</p>
          <div class="chk-opts"><button class="chk-o">보기</button><button class="chk-o" data-ok>정답</button>…</div>
          <p class="chk-why">해설</p></div>
        다시 볼 장: 같은 덱의 <section class="slide" data-key="열쇠">. 없으면 단추를 만들지 않는다.
        기록: localStorage 'edeck-chk-<파일이름>' = {"장번호-문제번호": 1(맞음)|0(틀림)}
        시리즈는 'edeck-ser-chk-<파일이름>-<편>' 단위로 나눠 저장한다.
     ========================================================= */
  var returnTo=null, returnBtn=mkBtn('chk-back','← 확인 문제로 돌아가기');
  returnBtn.hidden=true;
  function quizKey(ep){ return PORTAL?KEY_QUIZ_EP+(ep==null?epNow():ep):KEY_QUIZ; }
  function quizLoad(ep){ if(PORTAL&&ep==null) ep=epNow(); try{ return JSON.parse(store(quizKey(ep))||'{}')||{}; }catch(e){ return {}; } }
  function quizSave(o,ep){ store(quizKey(PORTAL?ep:null),JSON.stringify(o)); }
  function reviewTarget(c){
    var key=c.getAttribute('data-review'); if(!key) return null;
    var all=sheets(c), t=all.filter(function(x){ return x.getAttribute('data-key')===key; })[0];
    if(!t) return null;
    return {idx:all.indexOf(t), title:sheetName(t)};
  }
  function quizId(c){
    var sl=c.closest('.slide'), all=sheets(c), qs=qa('.chk',sl);
    return (all.indexOf(sl)+1)+'-'+(qs.indexOf(c)+1);
  }
  function buildQuizzes(){
    qa('#stage .chk').forEach(function(c){
      if(c.getAttribute('data-chk-built')) return; c.setAttribute('data-chk-built','1');
      var fb=mk('div','chk-fb'); fb.appendChild(mk('p','chk-msg'));
      var why=q('.chk-why',c); if(why) fb.appendChild(why);
      var t=reviewTarget(c);
      if(t){ var go=mkBtn('chk-go',(t.idx+1)+'장 「'+t.title+'」 다시 보기 →'); go.setAttribute('data-idx',t.idx); fb.appendChild(go); }
      fb.appendChild(mkBtn('chk-again','다시 풀기'));
      c.appendChild(fb);
    });
  }
  function quizAnswer(o){
    var c=o.closest('.chk'); if(!c||c.classList.contains('chk-done')) return;
    var ok=o.hasAttribute('data-ok');
    qa('.chk-o',c).forEach(function(x){ x.disabled=true; x.classList.toggle('chk-right',x.hasAttribute('data-ok')); });
    o.classList.add('chk-picked');
    c.classList.add('chk-done',ok?'chk-ok':'chk-ng');
    markVerdict(q('.chk-o.chk-right',c));   /* 정답 단추에 채점 표시(공용 모션 엔진) */
    q('.chk-msg',c).textContent=ok?'맞았습니다.':'아직 헷갈리는 개념입니다. 해설을 읽고, 설명한 장을 한 번 더 보면 좋습니다.';
    var id=quizId(c), st=quizLoad(epOf(c)); st[id]=ok?1:0; quizSave(st,epOf(c));
    paintPanel();
  }
  function quizReset(c){
    var right=q('.chk-o.chk-right',c);     /* 채점 표시도 함께 지운다 */
    c.classList.remove('chk-done','chk-ok','chk-ng');
    qa('.chk-o',c).forEach(function(x){ x.disabled=false; x.classList.remove('chk-right','chk-picked'); });
    unmarkVerdict(right);
    var st=quizLoad(epOf(c)); delete st[quizId(c)]; quizSave(st,epOf(c)); paintPanel();
  }
  function quizJump(b){
    var cur=liveSheet(); if(!cur) return;
    returnTo=PORTAL?{ep:epOf(cur),idx:sheets(cur).indexOf(cur)}:{idx:sheets(cur).indexOf(cur)};
    jump(+b.getAttribute('data-idx'),PORTAL?epOf(cur):null,0);
    syncReturn();
  }
  function syncReturn(){
    var cur=liveSheet();
    if(PORTAL){ /* 목차로 나갔거나 다른 편으로 옮기면 돌아갈 문제가 없어진다 */
      if(!cur||atHub()){ returnBtn.hidden=true; return; }
      var d=liveDeck();
      if(returnTo&&d&&String(d.getAttribute('data-ep'))!==returnTo.ep) returnTo=null;
      var i=sheets(cur).indexOf(cur);
      if(returnTo&&i===returnTo.idx) returnTo=null;
      returnBtn.hidden=!returnTo;
      return;
    }
    if(!cur) return;
    var i=sheets(cur).indexOf(cur);
    if(returnTo&&i===returnTo.idx) returnTo=null;
    returnBtn.hidden=!(returnTo&&i!==returnTo.idx);
  }
  function quizTally(ep){ /* 자습 설명 아래 한 줄: 푼 문제·맞은 수·다시 볼 곳 */
    var cs=PORTAL?qa('.chk',deckEl(ep==null?epNow():ep)||liveDeck()):qa('#stage .chk');
    if(!cs.length) return null;
    var st=quizLoad(PORTAL?(ep==null?epNow():ep):null), done=0, ok=0, ng=[];
    cs.forEach(function(c){ var id=quizId(c); if(id in st){ done++; if(st[id]) ok++; else{ var t=reviewTarget(c); if(t&&ng.indexOf(t.idx+1)<0) ng.push(t.idx+1); } } });
    return {n:cs.length, done:done, ok:ok, ng:ng};
  }

  /* 채점 표시는 모션 엔진(window.eduMotion)이 그린다 — 여기서는 위임만 한다 */
  var marked=[];
  function markVerdict(el){ if(window.eduMotion) window.eduMotion.verdict(el,!!el.closest('.chk-ok')); }
  function unmarkVerdict(el){ if(window.eduMotion) window.eduMotion.unmark(el); }
  function unmarkAll(){ qa('.ed-mark').forEach(function(x){ unmarkVerdict(x.parentElement); }); }
  function markOnEnter(){ /* deckslide/deckstep 는 엔진이 이미 처리(첫 장 포함) */ }

  document.addEventListener('deckslide',function(){ paintPanel(); syncReturn(); fitStage(); });
  /* 키: 레이어가 열려 있으면 발표 엔진보다 먼저 받아서 막는다 */
  window.addEventListener('keydown',function(e){
    var k=e.key;
    if(openLayer){
      if(k==='Escape'){ e.preventDefault(); e.stopImmediatePropagation(); hideLayer(); return; }
      if(openLayer===picker&&(k==='1'||k==='2')){ e.preventDefault(); e.stopImmediatePropagation(); openPrint(k==='1'?'summary':'script',PORTAL?epForPrint():null); return; }
      e.stopImmediatePropagation();          /* 장 넘김·엔진 단축키로 새지 않게. 입력 칸의 글자는 그대로 */
      return;
    }
    if(e.ctrlKey||e.metaKey||e.altKey||e.isComposing) return;
    var t=e.target; if(t&&(t.tagName==='INPUT'||t.tagName==='TEXTAREA'||t.isContentEditable)) return;
    if(k==='s'||k==='S'||k==='ㄴ'){
      e.preventDefault();
      if(atHub()){ toast('목차 화면에서는 자습 모드를 쓰지 않습니다. 편을 열면 장마다 설명이 붙습니다.'); }
      else setSelf(!selfOn);
    }
    else if(k==='d'||k==='D'||k==='ㅇ'){ e.preventDefault(); openGlossary(); }
    else if(k==='p'||k==='P'||k==='ㅔ'){ e.preventDefault(); openPicker(); }
  },true);
  /* 클릭: 레이어 배경을 누르면 닫기만 하고 장은 넘기지 않는다 */
  document.addEventListener('click',function(e){
    var t=e.target; if(!t||!t.closest) return;
    var b;
    if(openLayer&&t===openLayer){ hideLayer(); e.stopImmediatePropagation(); return; }
    if((b=t.closest('.chk-o'))){ quizAnswer(b); return; }
    if((b=t.closest('.chk-go'))){ quizJump(b); return; }
    if((b=t.closest('.chk-again'))){ quizReset(b.closest('.chk')); return; }
    if((b=t.closest('.chk-back'))){ var bk=returnTo; returnTo=null; returnBtn.hidden=true; if(bk) jump(bk.idx,PORTAL?bk.ep:null,0); return; }
    if((b=t.closest('.st-go'))){ hideLayer(); jump(+b.getAttribute('data-idx'),PORTAL?b.getAttribute('data-ep'):null); return; }
    if((b=t.closest('[data-study]'))){ /* 목차의 용어집·인쇄·자습 단추(시리즈 엔진이 심는다) */
      var kind=b.getAttribute('data-study');
      if(kind==='glossary') openGlossary();
      else if(kind==='print-summary') openPrint('summary',PORTAL?b.getAttribute('data-ep'):null);
      else if(kind==='print-script') openPrint('script',PORTAL?b.getAttribute('data-ep'):null);
      else if(kind==='selfstudy'){ if(atHub()) toast('목차 화면에서는 자습 모드를 쓰지 않습니다. 편을 열면 장마다 설명이 붙습니다.'); else setSelf(!selfOn); }
      return;
    }
  },true);
  /* 목차의 "기록 지우기": 시리즈 엔진이 진도를 지운 뒤 이 이벤트로 확인 문제 기록도 지운다 */
  document.addEventListener('edeck-reset',function(){
    /* 화면의 채점 상태를 먼저 되돌리고(저장하지 않는다) 저장 키를 지운다 */
    qa('#stage .chk.chk-done').forEach(function(c){
      c.classList.remove('chk-done','chk-ok','chk-ng');
      qa('.chk-o',c).forEach(function(x){ x.disabled=false; x.classList.remove('chk-right','chk-picked'); });
    });
    unmarkAll(); marked.length=0;
    if(PORTAL){ allDecks().forEach(function(d){ try{ localStorage.removeItem(KEY_QUIZ_EP+d.getAttribute('data-ep')); }catch(e){} }); }
    else{ try{ localStorage.removeItem(KEY_QUIZ); }catch(e){} }
    returnTo=null; returnBtn.hidden=true;
    paintPanel();
  });
  window.addEventListener('resize',fitStage);
  var dotsEl=document.getElementById('dots');
  if(dotsEl&&window.MutationObserver) new MutationObserver(paintHint).observe(dotsEl,{childList:true,subtree:true,attributes:true});

  /* ---------- 시작 ---------- */
  [panel,printView,picker,gloss,toastBox,returnBtn].forEach(function(x){ document.body.appendChild(x); });
  buildQuizzes();
  setSelf(selfOn,true);
  paintPanel();
  fitStage();
  markOnEnter();   /* 첫 장(주소 #N 포함) 채점 표시 — 첫 deckslide 는 이미 지나갔다 */
  /* 시험용 진입점 */
  window.studyApi={selfstudy:function(on){ setSelf(on===undefined?!selfOn:on,true); return selfOn; },
    glossary:openGlossary, print:openPrint, close:hideLayer, checks:quizTally,
    setSummary:function(ep,obj){ if(PORTAL){ EP_SUMMARIES[String(ep)]=(obj&&typeof obj==='object'&&!Array.isArray(obj))?obj:null; } },
    meta:function(){ return {series:PORTAL, ep:PORTAL?(atHub()?pickedEp():epNow()):null}; }};
})();
