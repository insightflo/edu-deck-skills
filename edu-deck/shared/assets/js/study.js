/*
  자습 레이어: 자습 모드(S), 인쇄(P: 한 장 요약 · 발표 대본), 용어집(G), 확인 문제(.chk), 채점 크레파스 모션(data-crayon)
  [목적] 발표용 덱을 혼자 공부하는 사람에게 장마다 설명(발표자 노트)을 붙여 보여 주고,
    한 장 요약·발표 대본을 A4 로 인쇄하게 하며, 용어집을 찾게 한다. 확인 문제는 보기를 눌러 답한다.
  [원칙] 덱 원고(슬라이드 마크업)는 고치지 않는다. aside.notes · data-archetype="closing"/"rules-dark" ·
    .chk 마크업을 읽어서 만든다. 이 스크립트가 만드는 클래스는 모두 st- 로 시작한다(원고와 섞이지 않게).
  [입력] window.EDU_STUDY = 조립기가 넣는 데이터(없어도 동작).
    단일 덱(build_deck.py, deck.json): summary={…} · glossary=[{term,en,alias,plain,slide}]
    시리즈 포털(build_series.py, series.json): summaries={편: summary} · glossary=[{…,ep}] · meta={편:{label,title}}
  [두 가지 모드] #stage 아래 .deck[data-ep] 포장이 있으면 시리즈 포털(엔진의 deckGo(ep,i,st), 편 단위 진도),
    없으면 단일 덱(deckGo(i,st)). 아래 분기는 SERIES 플래그로 갈라지고 단일 덱 동작은 그대로다.
  [연결] 발표 엔진의 deckslide 이벤트와 window.deckGo 를 쓴다. window.studyApi 는 시험용.
    시리즈 엔진이 목차에서 지우면 edeck-reset 이벤트로 확인 문제 기록도 같이 지운다.
*/
(function(){
  'use strict';
  var D=window.EDU_STUDY||{};
  var SERIES=!!document.querySelector('#stage > .deck');
  var FILE=(decodeURIComponent(location.pathname.split('/').pop())||'deck');
  var SUMMARY=(D.summary&&typeof D.summary==='object'&&!Array.isArray(D.summary))?D.summary:null;
  var SUMS=(SERIES&&D.summaries&&typeof D.summaries==='object'&&!Array.isArray(D.summaries))?D.summaries:{};
  var META=(SERIES&&D.meta&&typeof D.meta==='object'&&!Array.isArray(D.meta))?D.meta:{};
  var GLOSS=Array.isArray(D.glossary)?D.glossary.filter(function(g){ return g&&g.term; }):[];
  var K_SELF='edeck-selfstudy', K_FOLD='edeck-selfstudy-fold';
  var K_CHK='edeck-chk-'+FILE;                /* 단일 덱: 덱 파일 단위 */
  var K_CHK_SER='edeck-ser-chk-'+FILE+'-';    /* 시리즈: 덱 파일 + 편 단위 */

  /* ---------- 도우미 ---------- */
  function ls(k,v){ try{ if(v===undefined) return localStorage.getItem(k); localStorage.setItem(k,v); }catch(e){ return null; } }
  function $(sel,root){ return (root||document).querySelector(sel); }
  function $$(sel,root){ return [].slice.call((root||document).querySelectorAll(sel)); }
  function el(tag,cls,text){ var e=document.createElement(tag); if(cls) e.className=cls; if(text!=null) e.textContent=text; return e; }
  function btn(cls,text){ var b=el('button',cls,text); b.type='button'; return b; }
  function norm(s){ return String(s==null?'':s).replace(/\s+/g,' ').trim(); }
  function arr(x){ if(Array.isArray(x)) return x.map(norm).filter(Boolean); x=norm(x); return x?[x]:[]; }
  function textOf(node){ /* <br>을 띄어쓰기로 바꿔 읽는다 */
    if(!node) return '';
    var c=node.cloneNode(true);
    $$('br',c).forEach(function(b){ b.parentNode.replaceChild(document.createTextNode(' '),b); });
    $$('aside,.notes,script,style',c).forEach(function(x){ x.parentNode.removeChild(x); });
    return norm(c.textContent);
  }
  function deckOf(ep){ return $('#stage > .deck[data-ep="'+String(ep==null?'':ep).replace(/[^0-9A-Za-z_-]/g,'')+'"]'); }
  function deckOn(){ return $('#stage > .deck.on'); }
  function decksAll(){ return $$('#stage > .deck'); }
  function curEp(){ var d=deckOn(); return d?String(d.getAttribute('data-ep')||''):''; }
  function cEp(node){ if(!SERIES) return ''; var d=node&&node.closest?node.closest('.deck'):null; return d?String(d.getAttribute('data-ep')||''):curEp(); }
  function epLabel(ep){ var d=deckOf(ep); return d?norm(d.getAttribute('data-label')):''; }
  function epName(ep){ /* 편 이름: "3편 스킬" (meta 우선, 없으면 라벨만) */
    if(!SERIES) return '';
    var m=META[String(ep)], t=m&&norm(m.title)?norm(m.title):'';
    return (epLabel(ep)+' '+t).trim()||(''+ep+'편');
  }
  function inHub(){ return SERIES&&document.body.classList.contains('in-hub'); }
  function selEp(){ /* 목차에서 마지막으로 고른(또는 첫) 편. 시리즈 엔진이 카드에 .sel 을 단다 */
    if(!SERIES) return '';
    var c=$('#hub [data-ep].sel');
    if(c) return String(c.getAttribute('data-ep'));
    var first=decksAll()[0];
    return first?String(first.getAttribute('data-ep')||''):'';
  }
  function epForPrint(){ return inHub()?selEp():curEp(); }
  function slides(root){ /* 단일 덱: 무대 직속 장. 시리즈: 지금(또는 지정 노드가 속한) 편의 장 */
    if(!SERIES) return $$('#stage > .slide');
    var d=root?((root.classList&&root.classList.contains('deck'))?root:root.closest?root.closest('.deck'):null):deckOn();
    return $$('.slide',d);
  }
  function curSlide(){ return SERIES?$('#stage > .deck.on > .slide.active'):$('#stage > .slide.active'); }
  function slideTitle(s){
    var t=textOf($('.title,.big,h1,h2',s));
    if(!t) t=textOf($('.eyebrow',s));
    return t||'제목 없는 장';
  }
  function noteParts(s){ /* 발표자 노트를 본문 줄과 출처 줄로 나눈다 */
    var n=s&&$('aside.notes',s); if(!n) return null;
    var lines=String(n.textContent||'').split(/\n+/).map(norm).filter(Boolean), main=[], src=[];
    lines.forEach(function(l){ (/^출처\s*[:：]/.test(l)?src:main).push(l); });
    return {main:main,src:src};
  }
  function mm(x){ return x*96/25.4; }
  function deckTitle(){ return norm(document.title)||'교육 자료'; }
  function go(idx,ep,st){ /* 장 이동: 단일 덱 deckGo(i,st), 시리즈 deckGo(ep,i,st).
     st 를 생략하면 단일 덱은 마지막 단계까지 펼치고(원래 동작), 시리즈는 첫 단계부터 보여 준다 */
    if(SERIES){ window.deckGo(ep==null?curEp():ep,idx,st==null?0:st); }
    else window.deckGo(idx,st);
  }

  /* ---------- 공통: 모달과 알림 ---------- */
  var modal=null;
  function openModal(m){ closeModal(); modal=m; m.classList.add('st-show'); }
  function closeModal(){
    if(!modal) return;
    modal.classList.remove('st-show');
    if(modal===printBox){ document.body.classList.remove('st-printing'); pageA4(false); }
    modal=null;
  }
  var toastEl=el('div','st-toast'), toastT=null;
  toastEl.setAttribute('role','status');
  function toast(msg){
    toastEl.textContent=msg; toastEl.classList.add('st-show');
    clearTimeout(toastT); toastT=setTimeout(function(){ toastEl.classList.remove('st-show'); },2600);
  }
  /* P 인쇄 중에는 @page 를 A4 로 바꾼다(마지막 규칙이 이긴다). 닫으면 원래대로(한 쪽에 한 슬라이드) */
  var pageEl=null;
  function pageA4(on){
    if(on&&!pageEl){ pageEl=document.createElement('style'); pageEl.textContent='@page{size:A4;margin:14mm}'; document.head.appendChild(pageEl); }
    else if(!on&&pageEl){ pageEl.parentNode.removeChild(pageEl); pageEl=null; }
  }

  /* =========================================================
     1. 자습 모드(S): 화면 아래에 장마다 설명(발표자 노트)을 붙인다
     ========================================================= */
  var selfOn=ls(K_SELF)==='1', fold=ls(K_FOLD)==='1';
  var panel=el('div','st-panel'); panel.id='st-panel';
  panel.setAttribute('role','region'); panel.setAttribute('aria-label','자습 설명');
  var pIn=el('div','st-pin');
  var pHead=el('div','st-ph');
  var pTag=el('span','st-ptag','자습 설명'), pPos=el('span','st-ppos'), pHint=el('span','st-hint');
  var pPrev=btn('st-pbtn st-prev','← 이전'), pNext=btn('st-pbtn st-next st-main','다음 →');
  var pGl=btn('st-pbtn st-tool','용어집'), pPr=btn('st-pbtn st-tool','인쇄');
  var pFold=btn('st-pbtn st-fold',''), pOff=btn('st-pbtn st-off','자습 끄기');
  pGl.title='용어집 (G)'; pPr.title='인쇄 (P)'; pOff.title='자습 모드 끄기 (S)';
  var pSp=el('span','st-sp');
  [pTag,pPos,pHint,pSp,pPrev,pNext,pGl,pPr,pFold,pOff].forEach(function(x){ pHead.appendChild(x); });
  var pBody=el('div','st-pb'); pBody.setAttribute('aria-live','polite'); pBody.tabIndex=0;
  pIn.appendChild(pHead); pIn.appendChild(pBody); panel.appendChild(pIn);

  function renderPanel(){
    var s=curSlide();
    pFold.textContent=fold?'설명 펼치기':'접기';
    pFold.setAttribute('aria-expanded',fold?'false':'true');
    if(inHub()){ /* 시리즈 목차: 편을 열면 설명이 붙는다는 안내만 */
      pPos.textContent='목차';
      pBody.innerHTML='';
      pBody.appendChild(el('p','st-empty','목차 화면입니다. 편을 열면 장마다 설명이 여기에 붙습니다.'));
      updateHint();
      return;
    }
    if(!s) return;
    var all=slides(s), i=all.indexOf(s);
    pPos.textContent=(SERIES?epLabel(curEp())?epLabel(curEp())+' · ':(curEp()===''?'':'편 '):'')+(i+1)+' / '+all.length+'장';
    pBody.innerHTML='';
    var np=noteParts(s);
    if(!np||!np.main.length&&!np.src.length){ pBody.appendChild(el('p','st-empty','이 장에는 따로 붙은 설명이 없습니다. 화면을 천천히 읽고 다음으로 넘어가세요.')); }
    else{
      np.main.forEach(function(l){ pBody.appendChild(el('p','st-txt',l)); });
      np.src.forEach(function(l){ pBody.appendChild(el('p','st-src',l)); });
    }
    var cs=chkSummary();
    if(cs&&cs.done){ pBody.appendChild(el('p','st-chk','확인 문제 '+cs.ok+'/'+cs.done+' 맞음'+(cs.ng.length?' · 다시 볼 곳: '+cs.ng.map(function(x){ return x+'장'; }).join(', '):''))); }
    pBody.scrollTop=0;
    updateHint();
  }
  function updateHint(){
    var s=curSlide(); if(!s){ pHint.textContent=''; return; }
    var dots=$$('#dots i'), on=dots.filter(function(x){ return x.classList.contains('on'); }).length;
    var all=slides(s), last=all.indexOf(s)===all.length-1;
    if(on<dots.length) pHint.textContent='→ 다음 단계 ('+on+'/'+dots.length+')';
    else pHint.textContent=last?'마지막 장입니다':'→ 다음 장';
    pHint.classList.toggle('st-hint-on',on<dots.length);
  }
  function fitStage(){ /* 자습 모드에서는 화면 아래 패널 자리를 빼고 무대를 맞춘다 */
    var b=document.body;
    if(!selfOn||document.documentElement.classList.contains('ed-compact')){
      b.style.removeProperty('--st-sc'); b.style.removeProperty('--st-top');
      panel.style.removeProperty('--st-k'); panel.style.removeProperty('--st-w'); return;
    }
    var W=window.innerWidth, H=window.innerHeight;
    var k=Math.max(Math.min(W/1920,H/1080),0.62);
    panel.style.setProperty('--st-k',k.toFixed(4));
    var ph=panel.offsetHeight||0, avail=Math.max(160,H-ph);
    var sc=Math.min(W/1920,avail/1080);
    b.style.setProperty('--st-sc',sc.toFixed(5));
    b.style.setProperty('--st-top',(avail/2).toFixed(1)+'px');
    panel.style.setProperty('--st-w',Math.max(560,Math.round(1920*sc))+'px');
  }
  function setSelf(on,quiet){
    selfOn=!!on; ls(K_SELF,selfOn?'1':'0');
    document.body.classList.toggle('st-self',selfOn);
    document.body.classList.toggle('st-fold',fold);
    renderPanel(); fitStage();
    if(!quiet) toast(selfOn?'자습 모드를 켰습니다. 장마다 설명이 아래에 나옵니다. (S 끄기 · G 용어집 · P 인쇄)':'자습 모드를 껐습니다. (S로 다시 켜기)');
  }
  function setFold(f){ fold=!!f; ls(K_FOLD,fold?'1':'0'); document.body.classList.toggle('st-fold',fold); renderPanel(); fitStage(); }
  function press(key){ document.dispatchEvent(new KeyboardEvent('keydown',{key:key,bubbles:true,cancelable:true})); }
  pPrev.addEventListener('click',function(){ press('ArrowLeft'); });
  pNext.addEventListener('click',function(){ press('ArrowRight'); });
  pFold.addEventListener('click',function(){ setFold(!fold); });
  pOff.addEventListener('click',function(){ setSelf(false); });
  pGl.addEventListener('click',function(){ openGlossary(); });
  pPr.addEventListener('click',function(){ openChooser(); });

  /* =========================================================
     2. 인쇄(P): 한 장 요약 · 발표 대본을 A4 미리보기로 만든다
     ========================================================= */
  var printBox=el('div','st-print'); printBox.id='st-print';
  var prBar=el('div','st-prbar'), prTitle=el('span','st-prtitle'), prSp=el('span','st-sp');
  var prGo=btn('st-mbtn st-main','인쇄'), prClose=btn('st-mbtn','닫기');
  var prNote=el('span','st-prnote','A4 용지로 인쇄됩니다. PDF로 저장하려면 인쇄 창에서 "PDF로 저장"을 고르세요.');
  [prTitle,prNote,prSp,prGo,prClose].forEach(function(x){ prBar.appendChild(x); });
  var prScroll=el('div','st-prscroll');
  printBox.appendChild(prBar); printBox.appendChild(prScroll);
  printBox.setAttribute('role','dialog'); printBox.setAttribute('aria-modal','true'); printBox.setAttribute('aria-label','인쇄 미리보기');
  prGo.addEventListener('click',function(){ try{ window.print(); }catch(e){} });
  prClose.addEventListener('click',closeModal);

  var printEp='';   /* 시리즈: 인쇄 대상 편. 단일 덱에서는 쓰지 않는다 */
  function printSlides(){ return SERIES?slides(deckOf(printEp)||deckOn()):slides(); }
  function printName(){ return SERIES?epName(printEp):deckTitle(); }
  function printSummary(){ return SERIES?SUMS[String(printEp)]||null:SUMMARY; }
  function docHead(kind){
    var hd=el('div','st-dh');
    var top=el('div','st-dtop'); top.appendChild(el('span','st-dseries',deckTitle()+' · '+kind)); hd.appendChild(top);
    hd.appendChild(el('h1','st-dtitle',printName()||deckTitle()));
    return hd;
  }
  function section(title,items,ordered,cls){
    if(!items.length) return null;
    var s=el('section','st-sec'+(cls?' '+cls:'')); s.appendChild(el('h2','st-sech',title));
    var l=el(ordered?'ol':'ul','st-list'); items.forEach(function(t){ l.appendChild(el('li','',t)); }); s.appendChild(l);
    return s;
  }
  function glossFor(term){
    var t=norm(term).toLowerCase();
    for(var i=0;i<GLOSS.length;i++){ var g=GLOSS[i]; if(norm(g.term).toLowerCase()===t||norm(g.en).toLowerCase()===t) return g; }
    return null;
  }
  /* 한 장 요약: deck.json summary 가 있으면 그걸로, 없으면 마무리 장(closing)과 규칙 장(rules-dark)의 마크업에서 만든다.
     시리즈는 편마다 주어진 summary(summaries[편])를 쓴다 */
  function buildSummary(){
    var SM=printSummary();
    var paper=el('div','st-paper st-sum'), pin=el('div','st-ppin');
    paper.appendChild(pin);
    pin.appendChild(docHead('한 장 요약'));
    var one='', remember=[], caution=[], terms=[];
    if(SM){
      one=norm(SM.one_line); remember=arr(SM.remember); caution=arr(SM.caution); terms=arr(SM.terms);
      var g=el('div','st-grid');
      [section('핵심',arr(SM.points),true),section('오늘의 세 줄',remember,true,'st-hot')].forEach(function(x){ if(x) g.appendChild(x); });
      if(g.children.length) pin.appendChild(g);
      if(norm(SM.analogy)){ var an=el('p','st-ana'); an.appendChild(el('span','st-anatag','비유')); an.appendChild(document.createTextNode(norm(SM.analogy))); pin.appendChild(an); }
      var t=section('이렇게 쓰면 좋습니다',arr(SM['try']),false); if(t) pin.appendChild(t);
    }else{
      /* 원고 무수정 원칙: 마무리 장의 큰 문장과 알약, 규칙 장의 항목을 그대로 옮긴다 */
      var closing=printSlides().filter(function(s){ return s.getAttribute('data-archetype')==='closing'; })[0];
      if(closing){
        var big=$('.big',closing); if(big) one=textOf(big);
        $$('.pill',closing).forEach(function(p){ var t=norm(p.textContent); if(t) remember.push(t); });
      }
      var rules=printSlides().filter(function(s){ return s.getAttribute('data-archetype')==='rules-dark'; })[0];
      if(rules) $$('h3',rules).forEach(function(h){ var t=norm(h.textContent); if(t) caution.push(t); });
      if(remember.length){ var sec=el('section','st-sec st-hot'); sec.appendChild(el('h2','st-sech','오늘의 세 줄'));
        var ol=el('ol','st-list st-wide'); remember.forEach(function(t){ ol.appendChild(el('li','',t)); }); sec.appendChild(ol); pin.appendChild(sec); }
    }
    if(one) pin.insertBefore(el('p','st-one',one), pin.children[1]||null);
    if(!SM) pin.appendChild(el('p','st-pending',SERIES?'한 장 요약의 핵심·주의 목록은 series.json 편 항목의 summary 키로 더 채울 수 있습니다.':'한 장 요약의 핵심·주의 목록은 deck.json 의 summary 키로 더 채울 수 있습니다.'));
    if(caution.length){ var c=section('주의할 점',caution,false,'st-warn'); if(c) pin.appendChild(c); }
    if(terms.length){
      var ts=el('section','st-sec st-terms'); ts.appendChild(el('h2','st-sech','핵심 용어'));
      var tl=el('dl','st-tl'), rest=[];
      terms.forEach(function(t){
        var g=glossFor(t); if(!g||!norm(g.plain)){ rest.push(t); return; }
        var row=el('div','st-trow'), dt=el('dt','',t);
        if(norm(g.en)&&norm(g.en)!==t) dt.appendChild(el('span','st-ten',' '+norm(g.en)));
        row.appendChild(dt); row.appendChild(el('dd','',norm(g.plain)+(norm(g.alias)?' (비유: '+norm(g.alias)+')':'')));
        tl.appendChild(row);
      });
      if(tl.children.length) ts.appendChild(tl);
      if(rest.length) ts.appendChild(el('p','st-tmore',(tl.children.length?'그 밖의 용어: ':'')+rest.join(' · ')));
      pin.appendChild(ts);
    }
    var ft=el('div','st-dfoot'); ft.appendChild(el('span','',printName()||deckTitle())); ft.appendChild(el('span','','한 장 요약')); pin.appendChild(ft);
    return paper;
  }
  function buildScript(){
    var paper=el('div','st-paper st-script'), pin=el('div','st-ppin');
    paper.appendChild(pin);
    pin.appendChild(docHead('발표 대본'));
    var all=printSlides();
    pin.appendChild(el('p','st-intro','장마다 화면 제목과 발표자 노트를 순서대로 옮겼습니다. 화면을 넘기며 그대로 읽으면 됩니다. 모두 '+all.length+'장.'));
    all.forEach(function(s,i){
      var b=el('section','st-blk');
      var h=el('h2','st-bh'); h.appendChild(el('span','st-bn',(i+1)+'장')); h.appendChild(document.createTextNode(slideTitle(s))); b.appendChild(h);
      var np=noteParts(s);
      if(!np||!np.main.length&&!np.src.length) b.appendChild(el('p','st-bnone','(노트 없음)'));
      else{ np.main.forEach(function(l){ b.appendChild(el('p','st-bt',l)); }); np.src.forEach(function(l){ b.appendChild(el('p','st-bsrc',l)); }); }
      pin.appendChild(b);
    });
    return paper;
  }
  function fitOnePage(paper){ /* 한 장 요약이 A4 한 장에 들어가게 글자 크기를 줄인다 */
    var pin=$('.st-ppin',paper), limit=mm(297-28)-6;
    for(var f=1;f>=0.62;f-=0.03){ paper.style.setProperty('--st-fs',f.toFixed(2)); if(pin.offsetHeight<=limit) break; }
  }
  function openPrint(kind,ep){
    if(SERIES) printEp=(ep==null||ep==='')?String(epForPrint()):String(ep);
    prScroll.innerHTML='';
    var paper=kind==='script'?buildScript():buildSummary();
    prScroll.appendChild(paper);
    prTitle.textContent=(kind==='script'?'발표 대본':'한 장 요약')+' 미리보기 · '+(SERIES?epName(printEp)+' — ':'')+deckTitle();
    printBox.setAttribute('data-kind',kind==='script'?'script':'summary');
    openModal(printBox); document.body.classList.add('st-printing'); pageA4(true);
    if(kind!=='script') fitOnePage(paper);
    prScroll.scrollTop=0; prGo.focus();
  }
  /* 인쇄 고르기(P) */
  var chooser=el('div','st-modal st-chooser'); chooser.id='st-choose';
  var chBox=el('div','st-mbox st-chbox'), chT=el('h2','st-mh','인쇄 · '+deckTitle()), chS=el('p','st-msub','어떤 자료를 인쇄할까요?');
  var chA=btn('st-mbtn st-main st-big','1  한 장 요약'), chB=btn('st-mbtn st-main st-big','2  발표 대본'), chX=btn('st-mbtn','닫기');
  var chRow=el('div','st-chrow'); chRow.appendChild(chA); chRow.appendChild(chB);
  [chT,chS,chRow,chX].forEach(function(x){ chBox.appendChild(x); }); chooser.appendChild(chBox);
  chooser.setAttribute('role','dialog'); chooser.setAttribute('aria-modal','true'); chooser.setAttribute('aria-label','인쇄할 자료 고르기');
  function openChooser(){ /* 시리즈에서는 지금(또는 목차에서 고른) 편이 대상. 제목에 편 이름을 띄운다 */
    if(SERIES) chT.textContent='인쇄 · '+epName(epForPrint());
    openModal(chooser); chA.focus();
  }
  chA.addEventListener('click',function(){ openPrint('summary'); });
  chB.addEventListener('click',function(){ openPrint('script'); });
  chX.addEventListener('click',closeModal);

  /* =========================================================
     3. 용어집(G): deck.json glossary 로 만든다. slide 키나 본문 찾기로 그 장으로 간다
     ========================================================= */
  var gl=el('div','st-modal st-gloss'); gl.id='st-gloss';
  gl.setAttribute('role','dialog'); gl.setAttribute('aria-modal','true'); gl.setAttribute('aria-label','용어집');
  var glBox=el('div','st-mbox st-glbox');
  var glHead=el('div','st-mhead'); glHead.appendChild(el('h2','st-mh','용어집')); var glX=btn('st-mbtn','닫기 (Esc)'); glHead.appendChild(el('span','st-sp')); glHead.appendChild(glX);
  var glQ=el('input','st-gq'); glQ.type='search'; glQ.placeholder='용어 찾기 (예: 컨텍스트, 책상, context)'; glQ.setAttribute('aria-label','용어 찾기');
  var glCnt=el('p','st-gcnt'), glList=el('div','st-glist');
  [glHead,glQ,glCnt,glList].forEach(function(x){ glBox.appendChild(x); }); gl.appendChild(glBox);
  glX.addEventListener('click',closeModal);
  function termSlide(g){ /* 용어가 나오는 장: slide 숫자가 있으면 그 장, 없으면 본문 찾기.
                             시리즈는 용어에 붙은 ep 편 안에서 찾아 {ep, idx} 로 돌려준다 */
    var ep=SERIES?String(g.ep!=null?g.ep:curEp()):'';
    var all=SERIES?slides(deckOf(ep)||deckOn()):slides();
    var found=function(i){ return SERIES?{ep:ep,idx:i}:i; };
    if(+g.slide>0&&+g.slide<=all.length) return found(+g.slide-1);
    var t=norm(g.term), head=norm(t.split('(')[0]), txt=all.map(textOf);
    var cands=[t,head].concat(t.split(/[\/,·(]/).map(function(x){ return norm(x.replace(')','')); })).filter(function(x){ return x&&x.length>=2; });
    for(var c=0;c<cands.length;c++){ for(var i=1;i<all.length;i++){ if(txt[i].indexOf(cands[c])>=0) return found(i); } }
    var en=norm(g.en).toLowerCase();
    if(en.length>=3) for(var i=1;i<all.length;i++){ if(txt[i].toLowerCase().indexOf(en)>=0) return found(i); }
    return found(-1);
  }
  function renderGloss(){
    var q=norm(glQ.value).toLowerCase();
    glList.innerHTML='';
    if(!GLOSS.length){ glCnt.textContent=''; glList.appendChild(el('p','st-gempty',SERIES?'이 시리즈에는 용어집이 없습니다. series.json 의 glossary 키로 용어를 넣으면 여기에 나옵니다.':'이 덱에는 용어집이 없습니다. deck.json 의 glossary 키로 용어를 넣으면 여기에 나옵니다.')); return; }
    var hits=GLOSS.filter(function(g){ return !q||[g.term,g.en,g.alias,g.plain].map(function(x){ return norm(x).toLowerCase(); }).join(' ').indexOf(q)>=0; });
    glCnt.textContent=q?'"'+norm(glQ.value)+'" 찾은 용어 '+hits.length+'개 / 전체 '+GLOSS.length+'개':'전체 '+GLOSS.length+'개';
    if(!hits.length){ glList.appendChild(el('p','st-gempty','찾는 용어가 없습니다. 다른 말로 찾아보세요.')); return; }
    hits.forEach(function(g){
      var it=el('div','st-gi'), tx=el('div','st-gtx'), top=el('p','st-gt');
      top.appendChild(el('b','st-gterm',norm(g.term)));
      if(norm(g.en)) top.appendChild(el('span','st-gen',norm(g.en)));
      if(norm(g.alias)) top.appendChild(el('span','st-gal','비유: '+norm(g.alias)));
      tx.appendChild(top);
      if(norm(g.plain)) tx.appendChild(el('p','st-gp',norm(g.plain)));
      it.appendChild(tx);
      var r=termSlide(g), idx=SERIES?r.idx:r, ep=SERIES?r.ep:'';
      if(SERIES&&norm(epLabel(ep))) top.appendChild(el('span','st-gen',epLabel(ep)));
      if(idx>=0){ var gbtn=btn('st-mbtn st-go',(SERIES?(epLabel(ep)?epLabel(ep)+' · ':''):'')+(idx+1)+'장 보기'); gbtn.setAttribute('data-idx',idx); if(SERIES) gbtn.setAttribute('data-ep',ep); it.appendChild(gbtn); }
      glList.appendChild(it);
    });
  }
  function openGlossary(){ glQ.value=''; renderGloss(); openModal(gl); glList.scrollTop=0; setTimeout(function(){ try{ glQ.focus(); }catch(e){} },0); }
  glQ.addEventListener('input',renderGloss);

  /* =========================================================
     4. 확인 문제(.chk): 틀리면 해설 + "○장 다시 보기"로 이끈다(막지는 않음)
        원고: <div class="chk" data-review="열쇠"> <p class="chk-q"><span class="chk-n">1</span>질문</p>
          <div class="chk-opts"><button class="chk-o">보기</button><button class="chk-o" data-ok>정답</button>…</div>
          <p class="chk-why">해설</p></div>
        다시 볼 장: 같은 덱의 <section class="slide" data-key="열쇠">. 없으면 버튼을 만들지 않는다.
        결과: localStorage 'edeck-chk-<파일이름>' = {"장번호-문제번호": 1(맞음)|0(틀림)}
     ========================================================= */
  var chkBack=null, backBtn=btn('chk-back','← 확인 문제로 돌아가기');
  backBtn.hidden=true;
  function chkKey(ep){ return SERIES?K_CHK_SER+(ep==null?curEp():ep):K_CHK; }
  function chkLoad(ep){ if(SERIES&&ep==null) ep=curEp(); try{ return JSON.parse(ls(chkKey(ep))||'{}')||{}; }catch(e){ return {}; } }
  function chkSave(o,ep){ ls(chkKey(SERIES?ep:null),JSON.stringify(o)); }
  function reviewTarget(c){
    var key=c.getAttribute('data-review'); if(!key) return null;
    var all=slides(c), t=all.filter(function(x){ return x.getAttribute('data-key')===key; })[0];
    if(!t) return null;
    return {idx:all.indexOf(t), title:slideTitle(t)};
  }
  function chkId(c){
    var sl=c.closest('.slide'), all=slides(c), qs=$$('.chk',sl);
    return (all.indexOf(sl)+1)+'-'+(qs.indexOf(c)+1);
  }
  function buildChecks(){
    $$('#stage .chk').forEach(function(c){
      if(c.getAttribute('data-chk-built')) return; c.setAttribute('data-chk-built','1');
      var fb=el('div','chk-fb'); fb.appendChild(el('p','chk-msg'));
      var why=$('.chk-why',c); if(why) fb.appendChild(why);
      var t=reviewTarget(c);
      if(t){ var go=btn('chk-go',(t.idx+1)+'장 「'+t.title+'」 다시 보기 →'); go.setAttribute('data-idx',t.idx); fb.appendChild(go); }
      fb.appendChild(btn('chk-again','다시 풀기'));
      c.appendChild(fb);
    });
  }
  function chkAnswer(o){
    var c=o.closest('.chk'); if(!c||c.classList.contains('chk-done')) return;
    var ok=o.hasAttribute('data-ok');
    $$('.chk-o',c).forEach(function(x){ x.disabled=true; x.classList.toggle('chk-right',x.hasAttribute('data-ok')); });
    o.classList.add('chk-picked');
    c.classList.add('chk-done',ok?'chk-ok':'chk-ng');
    crayonGrade($('.chk-o.chk-right',c));   /* 정답 단추에 빨간 동그라미(5절) */
    $('.chk-msg',c).textContent=ok?'맞았습니다.':'아직 헷갈리는 개념입니다. 해설을 읽고, 설명한 장을 한 번 더 보면 좋습니다.';
    var id=chkId(c), st=chkLoad(cEp(c)); st[id]=ok?1:0; chkSave(st,cEp(c));
    renderPanel();
  }
  function chkReset(c){
    var right=$('.chk-o.chk-right',c);    /* 채점 동그라미도 같이 지운다(5절) */
    c.classList.remove('chk-done','chk-ok','chk-ng');
    $$('.chk-o',c).forEach(function(x){ x.disabled=false; x.classList.remove('chk-right','chk-picked'); });
    crayonUnmark(right);
    var st=chkLoad(cEp(c)); delete st[chkId(c)]; chkSave(st,cEp(c)); renderPanel();
  }
  function chkGo(b){
    var cur=curSlide(); if(!cur) return;
    chkBack=SERIES?{ep:cEp(cur),idx:slides(cur).indexOf(cur)}:{idx:slides(cur).indexOf(cur)};
    go(+b.getAttribute('data-idx'),SERIES?cEp(cur):null,0);
    syncBack();
  }
  function syncBack(){
    var cur=curSlide();
    if(SERIES){ /* 목차에 나갔거나 다른 편으로 옮겼으면 돌아가기 대상이 사라진다 */
      if(!cur||inHub()){ backBtn.hidden=true; return; }
      var d=deckOn();
      if(chkBack&&d&&String(d.getAttribute('data-ep'))!==chkBack.ep) chkBack=null;
      var i=slides(cur).indexOf(cur);
      if(chkBack&&i===chkBack.idx) chkBack=null;
      backBtn.hidden=!chkBack;
      return;
    }
    if(!cur) return;
    var i=slides(cur).indexOf(cur);
    if(chkBack&&i===chkBack.idx) chkBack=null;
    backBtn.hidden=!(chkBack&&i!==chkBack.idx);
  }
  function chkSummary(ep){ /* 자습 설명 아래 줄: 확인 문제 결과와 다시 볼 곳. 시리즈는 편 단위로 묶는다 */
    var cs=SERIES?$$('.chk',deckOf(ep==null?curEp():ep)||deckOn()):$$('#stage .chk');
    if(!cs.length) return null;
    var st=chkLoad(SERIES?(ep==null?curEp():ep):null), done=0, ok=0, ng=[];
    cs.forEach(function(c){ var id=chkId(c); if(id in st){ done++; if(st[id]) ok++; else{ var t=reviewTarget(c); if(t&&ng.indexOf(t.idx+1)<0) ng.push(t.idx+1); } } });
    return {n:cs.length, done:done, ok:ok, ng:ng};
  }

  /* Compatibility adapter: grading state remains above; visual marks have one owner. */
  var crayonDrawn=[];
  function crayonGrade(el){ if(window.eduMotion) window.eduMotion.verdict(el,!!el.closest('.chk-ok')); }
  function crayonUnmark(el){ if(window.eduMotion) window.eduMotion.unmark(el); }
  function crayonClear(){ $$('.ed-mark').forEach(function(x){ crayonUnmark(x.parentElement); }); }
  function crayonEnter(){ /* Shared engine handles deckslide/deckstep, including initial state. */ }

  document.addEventListener('deckslide',function(){ renderPanel(); syncBack(); fitStage(); });
  /* 키: 모달이 열려 있으면 엔진보다 먼저 받아서 막는다 */
  window.addEventListener('keydown',function(e){
    var k=e.key;
    if(modal){
      if(k==='Escape'){ e.preventDefault(); e.stopImmediatePropagation(); closeModal(); return; }
      if(modal===chooser&&(k==='1'||k==='2')){ e.preventDefault(); e.stopImmediatePropagation(); openPrint(k==='1'?'summary':'script',SERIES?epForPrint():null); return; }
      e.stopImmediatePropagation();          /* 엔진(장 넘김, F, N)으로 가지 않게. 글자 입력은 그대로 */
      return;
    }
    if(e.ctrlKey||e.metaKey||e.altKey||e.isComposing) return;
    var t=e.target; if(t&&(t.tagName==='INPUT'||t.tagName==='TEXTAREA'||t.isContentEditable)) return;
    if(k==='s'||k==='S'||k==='ㄴ'){
      e.preventDefault();
      if(inHub()){ toast('목차 화면에서는 자습 모드를 쓰지 않습니다. 편을 열면 장마다 설명이 붙습니다.'); }
      else setSelf(!selfOn);
    }
    else if(k==='g'||k==='G'||k==='ㅎ'){ e.preventDefault(); openGlossary(); }
    else if(k==='p'||k==='P'||k==='ㅔ'){ e.preventDefault(); openChooser(); }
  },true);
  /* 클릭: 모달 배경을 누르면 닫기만 하고 장은 넘기지 않는다 */
  document.addEventListener('click',function(e){
    var t=e.target; if(!t||!t.closest) return;
    var b;
    if(modal&&t===modal){ closeModal(); e.stopImmediatePropagation(); return; }
    if((b=t.closest('.chk-o'))){ chkAnswer(b); return; }
    if((b=t.closest('.chk-go'))){ chkGo(b); return; }
    if((b=t.closest('.chk-again'))){ chkReset(b.closest('.chk')); return; }
    if((b=t.closest('.chk-back'))){ var bk=chkBack; chkBack=null; backBtn.hidden=true; if(bk) go(bk.idx,SERIES?bk.ep:null,0); return; }
    if((b=t.closest('.st-go'))){ closeModal(); go(+b.getAttribute('data-idx'),SERIES?b.getAttribute('data-ep'):null); return; }
    if((b=t.closest('[data-study]'))){ /* 허브의 용어집·인쇄 단추. 시리즈 엔진이 목차에 심는다 */
      var kind=b.getAttribute('data-study');
      if(kind==='glossary') openGlossary();
      else if(kind==='print-summary') openPrint('summary',SERIES?b.getAttribute('data-ep'):null);
      else if(kind==='print-script') openPrint('script',SERIES?b.getAttribute('data-ep'):null);
      else if(kind==='selfstudy'){ if(inHub()) toast('목차 화면에서는 자습 모드를 쓰지 않습니다. 편을 열면 장마다 설명이 붙습니다.'); else setSelf(!selfOn); }
      return;
    }
  },true);
  /* 목차의 "기록 지우기": 시리즈 엔진이 진도를 지운 뒤 이 이벤트로 확인 문제 기록도 지운다 */
  document.addEventListener('edeck-reset',function(){
    /* 풀었던 표시를 먼저 지우고(저장은 하지 않는다) 그다음 저장소 키를 지운다 */
    $$('#stage .chk.chk-done').forEach(function(c){
      c.classList.remove('chk-done','chk-ok','chk-ng');
      $$('.chk-o',c).forEach(function(x){ x.disabled=false; x.classList.remove('chk-right','chk-picked'); });
    });
    crayonClear(); crayonDrawn.length=0;   /* 채점 동그라미도 함께 지운다(5절) */
    if(SERIES){ decksAll().forEach(function(d){ try{ localStorage.removeItem(K_CHK_SER+d.getAttribute('data-ep')); }catch(e){} }); }
    else{ try{ localStorage.removeItem(K_CHK); }catch(e){} }
    chkBack=null; backBtn.hidden=true;
    renderPanel();
  });
  window.addEventListener('resize',fitStage);
  var dots=document.getElementById('dots');
  if(dots&&window.MutationObserver) new MutationObserver(updateHint).observe(dots,{childList:true,subtree:true,attributes:true});

  /* ---------- 시작 ---------- */
  [panel,printBox,chooser,gl,toastEl,backBtn].forEach(function(x){ document.body.appendChild(x); });
  buildChecks();
  setSelf(selfOn,true);
  renderPanel();
  fitStage();
  crayonEnter();   /* 첫 장(주소 #N 으로 열었을 때 포함)의 채점 표시 — 엔진의 첫 deckslide 는 이미 지나갔다 */
  /* 시험용 */
  window.studyApi={selfstudy:function(on){ setSelf(on===undefined?!selfOn:on,true); return selfOn; },
    glossary:openGlossary, print:openPrint, close:closeModal, checks:chkSummary,
    setSummary:function(ep,obj){ if(SERIES){ SUMS[String(ep)]=(obj&&typeof obj==='object'&&!Array.isArray(obj))?obj:null; } },
    meta:function(){ return {series:SERIES, ep:SERIES?(inHub()?selEp():curEp()):null}; }};
})();
