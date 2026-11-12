/* Shared on-screen reader. It never owns lesson state: deckGo/step events and
   the existing study/quiz engine remain authoritative. No content is rewritten.
   Compact (≤1199px, slide-fit 제외) = 원래 1920×1080 배치를 그대로 축소한 장들의
   연속 스크롤. 재배치는 없다 — 배치가 뜻을 전하므로. 읽기 보조는 스크롤 단계
   공개와 "눌러서 크게 보기" 줌 뷰어다. */
(function(){
  'use strict';
  /* 읽기 모드 결정: ≤1199px 은 세로 읽기. 단 가로 방향이고 폭≥960·높이≥540 이면
     무대를 그대로 맞춰 보여 주는 slide-fit 모드다. ?view=slide|scroll 이 우선한다. */
  var mqNarrow=matchMedia('(max-width:1199px)'),
      mqFit=matchMedia('(orientation:landscape) and (min-width:960px) and (min-height:540px)'),
      VIEW=new URLSearchParams(location.search).get('view'),
      driving=false, lastW=0;
  /* 세로 읽기는 모든 장이 축소된 1920×1080으로 이어진 한 줄 스크롤이다. 단계는 요소
     위쪽이 화면 높이의 85% 선을 넘어올 때 자동으로 열리고, 한 번 연 단계는 위로
     스크롤해도 닫지 않는다. 현재 장은 화면에서 가장 넓게 보이는 장, 이전/다음·키보드
     넘김은 장 단위 점프다. */
  var LINE=0.85, GAP=8,
      ATTRS=['step','add','only','lit','until'], STEPKEYS=['step','add','only','lit'];
  function reading(){ /* 세로 읽기 모드인가 */
    if(VIEW==='slide')return false;
    if(VIEW==='scroll')return true;
    return mqNarrow.matches&&!mqFit.matches;
  }
  function slideFit(){ /* 좁은 화면이지만 가로·충분한 크기라 무대를 맞춰 보여 주는가 */
    if(VIEW==='scroll')return false;
    return VIEW==='slide'?mqNarrow.matches:(mqNarrow.matches&&mqFit.matches);
  }
  var stage=document.getElementById('stage');
  var isSeries=!!document.querySelector('#stage>.deck');
  var nav=document.createElement('nav');nav.className='ed-reader-nav';nav.setAttribute('aria-label','교육 자료 탐색');
  var status=document.createElement('div');status.className='ed-reader-status';status.setAttribute('aria-live','polite');nav.appendChild(status);
  function press(key){document.dispatchEvent(new KeyboardEvent('keydown',{key:key,bubbles:true,cancelable:true}));}
  [['이전','ArrowLeft'],['다음','ArrowRight'],['검색','/'],['설명','s'],['노트','n'],['용어집','g'],['인쇄','p'],['전체화면','f'],isSeries?['목차','Escape']:['목차','o'],isSeries?null:['처음','Home']].forEach(function(item){
    if(!item)return;
    var b=document.createElement('button');b.type='button';b.textContent=item[0];
    b.addEventListener('click',function(){press(item[1]);});nav.appendChild(b);
  });
  document.body.appendChild(nav);

  /* ---------- 세로 읽기: 스크롤을 따라 장·단계가 열린다 ---------- */
  function inHub(){ return document.body.classList.contains('in-hub'); }
  function deckSlides(){ /* 지금 읽는 편의 장 목록(시리즈는 .deck.on 안만) */
    return isSeries?[].slice.call(document.querySelectorAll('#stage>.deck.on>.slide')):allSlides();
  }
  function allSlides(){ return [].slice.call(stage.querySelectorAll(':scope>.slide')); }
  function curSel(){ return isSeries?'#stage>.deck.on>.slide.active':'#stage>.slide.active'; }
  function info(){ try{ return window.deckInfo?window.deckInfo():null; }catch(e){ return null; } }
  function go(i,st){ /* 엔진에 현재 장·단계를 맞춘다(시리즈는 지금 편 안에서) */
    if(isSeries){var d=document.querySelector('#stage>.deck.on');if(d)window.deckGo(d.getAttribute('data-ep'),i,st);}
    else window.deckGo(i,st);
  }
  function maxStepOf(s){
    var m=0;
    s.querySelectorAll('[data-step],[data-add],[data-only],[data-lit],[data-until]').forEach(function(e){
      ATTRS.forEach(function(a){ if(e.dataset[a]!==undefined) m=Math.max(m,+e.dataset[a]); });
    });
    return m;
  }
  /* 엔진 paint() 와 같은 규칙으로 현재 장이 아닌 장을 조용히 그린다.
     모션(.pop·data-fx)은 현재 장에만 엔진이 켠다. */
  function paintSlide(s,n){
    s.querySelectorAll('[data-step]').forEach(function(e){e.classList.toggle('step-hide',+e.dataset.step>n);});
    s.querySelectorAll('[data-add]').forEach(function(e){var k=+e.dataset.add;e.classList.toggle('gone',k>n);e.classList.toggle('new',k===n&&n>0);});
    s.querySelectorAll('[data-only]').forEach(function(e){e.classList.toggle('gone',+e.dataset.only!==n);});
    s.querySelectorAll('[data-until]').forEach(function(e){e.classList.toggle('gone',n>+e.dataset.until);});
    s.querySelectorAll('[data-lit]').forEach(function(e){e.classList.toggle('lit',+e.dataset.lit<=n);});
  }
  var reached=new WeakMap(); /* 장마다 열린 최대 단계 — 위로 스크롤해도 줄지 않는다 */
  function stepEls(s){
    if(!s._edSteps){
      var out=[];
      s.querySelectorAll('[data-step],[data-add],[data-only],[data-lit]').forEach(function(e){
        var k=0;STEPKEYS.forEach(function(a){ if(e.dataset[a]!==undefined) k=Math.max(k,+e.dataset[a]); });
        out.push({el:e,k:k});
      });
      s._edSteps=out;
    }
    return s._edSteps;
  }
  /* 요소가 자리 잡는 화면 위치. display:none 단계는 상자가 없으므로 보이는 이전 형제의
     아래쪽, 없으면 가장 가까운 보이는 조상의 위쪽을 자리로 쓴다. */
  function slotTop(el){
    var r=el.getBoundingClientRect();
    if(r.width||r.height)return r.top;
    var p=el.previousElementSibling;
    while(p){var pr=p.getBoundingClientRect();if(pr.width||pr.height)return pr.bottom;p=p.previousElementSibling;}
    var a=el.parentElement,g=0;
    while(a&&a!==document.body&&g++<10){var ar=a.getBoundingClientRect();if(ar.width||ar.height)return ar.top;a=a.parentElement;}
    return Infinity;
  }
  /* 화면 위·아래를 가리는 고정 크롬의 실측 경계. 위쪽 막대가 비어 있거나 둘 다
     숨겨졌으면 그쪽 화면 가장자리를 쓴다(장 맞춤·배율의 세로 여유 기준). */
  function chrome(){
    var tb=document.querySelector('.ed-top')||document.querySelector('.ed-topbar'),nv=document.querySelector('.ed-reader-nav');
    return {
      top:(tb&&tb.getClientRects().length)?tb.getBoundingClientRect().bottom:0,
      bot:(nv&&nv.getClientRects().length)?nv.getBoundingClientRect().top:window.innerHeight
    };
  }
  function anchorTop(s){
    var y=s.getBoundingClientRect().top+window.scrollY-chrome().top-GAP;
    window.scrollTo(0,Math.max(0,y));
  }
  function jumpTo(i){
    var list=deckSlides();if(!list.length)return;
    i=Math.max(0,Math.min(list.length-1,i));
    anchorTop(list[i]);
  }
  /* 이전/다음은 장 단위. 현재 장은 엔진 값이 아니라 화면에서 가장 넓게 보이는 장으로
     잰다(스크롤 직후 엔진 동기가 아직 안 돼도 연속 입력이 바로 먹는다). */
  function jump(d){
    var list=deckSlides();if(!list.length)return;
    var inf=info(),curI=(inf&&inf.slide!=null)?Math.max(0,Math.min(list.length-1,inf.slide|0)):0;
    var vh=window.innerHeight,bestI=curI,bestA=-1;
    for(var i=0;i<list.length;i++){var r=list[i].getBoundingClientRect();var ov=Math.min(r.bottom,vh)-Math.max(r.top,0);if(ov>bestA){bestA=ov;bestI=i;}}
    jumpTo(bestI+d);
  }
  /* 스크롤 한 칸마다: 가까운 장의 넘어온 단계를 열고, 가장 넓게 보이는 장을 현재 장으로 맞춘다.
     rAF 를 타지 않는다 — 프레임이 멎은 환경(헤드리스·절전 탭)에서도 스크롤 이벤트만으로
     공개가 진행돼야 한다. 한 번의 scrub 은 장 수에 비례한 저렴한 측정이다. */
  function scrub(){
    var pass=0,again=true;
    while(again&&pass++<6){again=scrubPass();if(again)sync();}
  }
  function scrubPass(){
    if(!reading()||inHub()||!window.deckGo)return false;
    var vh=window.innerHeight,line=vh*LINE,list=deckSlides();
    if(!list.length)return false;
    var inf=info();if(!inf||inf.slide==null)return false;
    var curI=Math.max(0,Math.min(list.length-1,inf.slide|0)),curS=list[curI];
    if(inf.step!=null)reached.set(curS,inf.step); /* 현재 장 단계는 엔진이 주인 */
    var bestI=curI,bestA=-1,dirty=false;
    for(var i=0;i<list.length;i++){
      var s=list[i],r=s.getBoundingClientRect();
      if(r.bottom<-vh||r.top>vh*2)continue;
      var ov=Math.min(r.bottom,vh)-Math.max(r.top,0);
      if(ov>bestA){bestA=ov;bestI=i;}
      var m=maxStepOf(s),target=reached.get(s)||0;
      /* 비현재 장은 reached 상태로 되돌린다(인쇄·외부 페인트 뒤 복원 포함).
         _edPaint 에 그린 값을 남겨 같은 값을 매 프레임 다시 그리지 않게 한다. */
      if(i!==curI&&s._edPaint!==target){paintSlide(s,target);s._edPaint=target;dirty=true;}
      if(target<m){
        var k=target,els=stepEls(s);
        for(var j=0;j<els.length;j++){var e=els[j];if(e.k<=k)continue;if(slotTop(e.el)<=line)k=e.k;}
        if(r.bottom<=line)k=m;
        if(k>target){reached.set(s,k);dirty=true;if(i!==curI){paintSlide(s,k);s._edPaint=k;}}
      }
    }
    if(bestI!==curI){
      dirty=true;driving=true;
      try{go(bestI,reached.get(list[bestI])||0);}finally{driving=false;}
      var inf2=info();if(inf2&&inf2.step!=null)reached.set(list[bestI],inf2.step);
    }else if(inf.step!=null&&(reached.get(curS)||0)>inf.step){
      dirty=true;driving=true;
      try{go(curI,reached.get(curS));}finally{driving=false;}
    }
    return dirty;
  }
  function sync(){
    var inf=info();
    if(inf&&inf.count)status.textContent=(inf.slide+1)+' / '+inf.count+'장 · '+(inf.step+1)+'단계';
  }
  /* 축소 배율: --ed-s = min(무대 폭/1920, 사용 높이/1080). 사용 높이는 위쪽 막대와
     아래 탐색줄 사이의 띈 높이 — 가로 폰에서도 한 장이 화면 크롬 사이에 통째로 든다.
     높이가 기준을 잡을 때는 --ed-x 로 장을 가로 가운데 둔다(가로 넘침 없음).
     허브에서는 무대가 숨겨져 폭이 0 — 이전 값을 둔다. */
  function applyScale(){
    if(!stage)return;
    if(!reading()){stage.style.removeProperty('--ed-s');stage.style.removeProperty('--ed-x');return;}
    var w=stage.clientWidth;
    if(w>0){
      var c=chrome(),s=Math.max(0.02,Math.min(w/1920,(c.bot-c.top-2*GAP)/1080));
      stage.style.setProperty('--ed-s',s.toFixed(5));
      var x=(w-1920*s)/2;
      if(x>0.5)stage.style.setProperty('--ed-x',x.toFixed(2)+'px');
      else stage.style.removeProperty('--ed-x');
    }
  }

  /* ---------- 눌러서 크게 보기(줌 뷰어) ----------
     장 본문을 누르면 그 장을 현재 공개 단계 그대로 복제해 전체 화면으로 보여 준다.
     한 손가락은 이동, 두 손가락은 핀치 배율, 두 번 탭은 1×↔2.5×. 읽기 전용 복제라
     퀴즈·탭 상태는 원본과 항상 같다. */
  var NOOPEN='a[href],button,input,textarea,select,summary,details,.chk,.tabs,.faq,.code,.todo,.pin-shot,.pin-list,.pin,.go,.notes,.sr';
  var zoomEl=null,zBox=null,zView=null,zNum=null,zPrev=null,zNext=null,zClose=null,
      zI=-1,zK=1,zTx=0,zTy=0,zPushed=false,zFocus=null;
  function zBase(){return Math.min(window.innerWidth/1920,window.innerHeight/1080);}
  function zClamp(){
    var vw=window.innerWidth,vh=window.innerHeight,W=1920*zK,H=1080*zK;
    zTx=W>vw?Math.min(0,Math.max(vw-W,zTx)):(vw-W)/2;
    zTy=H>vh?Math.min(0,Math.max(vh-H,zTy)):(vh-H)/2;
  }
  function zRender(anim){if(!zBox)return;zBox.classList.toggle('anim',!!anim);zBox.style.transform='translate('+zTx+'px,'+zTy+'px) scale('+zK+')';}
  function zAt(sx,sy,kNew){ /* 화면 점 (sx,sy) 아래 내용을 고정한 채 배율 교체 */
    var k0=zK;zK=kNew;zTx=sx-(sx-zTx)*zK/k0;zTy=sy-(sy-zTy)*zK/k0;zClamp();
  }
  function zToggle(sx,sy){zAt(sx,sy,zBase()*(zK>zBase()*1.4?1:2.5));zRender(true);}
  function zShow(i){
    var list=deckSlides();if(i<0||i>=list.length||!zBox)return;
    zI=i;
    var c=list[i].cloneNode(true);
    c.removeAttribute('id');[].slice.call(c.querySelectorAll('[id]')).forEach(function(e){e.removeAttribute('id');});
    zBox.innerHTML='';zBox.appendChild(c);
    zK=zBase();zTx=(window.innerWidth-1920*zK)/2;zTy=(window.innerHeight-1080*zK)/2;
    zNum.textContent=(i+1)+' / '+list.length+'장';
    zPrev.disabled=i<=0;zNext.disabled=i>=list.length-1;
    zRender();
  }
  function zTrap(e){
    var f=[].slice.call(zoomEl.querySelectorAll('button:not(:disabled)'));
    if(!f.length)return;
    var i=f.indexOf(document.activeElement),n=i<0?0:i+(e.shiftKey?-1:1);
    f[(n+f.length)%f.length].focus();
  }
  function zKeys(e){ /* 줌 뷰어가 열린 동안 모든 넘김 키를 여기서 처리·흡수한다 */
    var k=e.key;
    if(k==='Escape'){e.preventDefault();e.stopImmediatePropagation();closeZoom();}
    else if(k==='ArrowLeft'){e.preventDefault();e.stopImmediatePropagation();zShow(zI-1);}
    else if(k==='ArrowRight'){e.preventDefault();e.stopImmediatePropagation();zShow(zI+1);}
    else if(k==='Tab'){e.preventDefault();e.stopImmediatePropagation();zTrap(e);}
    else{e.preventDefault();e.stopImmediatePropagation();}
  }
  function openZoom(i){
    if(zoomEl)return;
    zFocus=document.activeElement;
    var d=document.createElement('div');d.className='ed-zoom on';d.setAttribute('role','dialog');d.setAttribute('aria-modal','true');d.setAttribute('aria-label','슬라이드 크게 보기');d.tabIndex=-1;
    zView=document.createElement('div');zView.className='ed-zoom-view';
    zBox=document.createElement('div');zBox.className='ed-zoom-box';
    zView.appendChild(zBox);d.appendChild(zView);
    zPrev=document.createElement('button');zPrev.type='button';zPrev.className='ed-zoom-nav ed-zoom-prev';zPrev.setAttribute('aria-label','이전 장');zPrev.textContent='‹';
    zNext=document.createElement('button');zNext.type='button';zNext.className='ed-zoom-nav ed-zoom-next';zNext.setAttribute('aria-label','다음 장');zNext.textContent='›';
    zNum=document.createElement('div');zNum.className='ed-zoom-num';
    zClose=document.createElement('button');zClose.type='button';zClose.className='ed-zoom-x';zClose.textContent='닫기';
    zClose.addEventListener('click',function(){closeZoom();});
    zPrev.addEventListener('click',function(){zShow(zI-1);});
    zNext.addEventListener('click',function(){zShow(zI+1);});
    d.appendChild(zPrev);d.appendChild(zNext);d.appendChild(zNum);d.appendChild(zClose);
    bindGestures(zView);
    document.body.appendChild(d);
    zoomEl=d;zShow(i);
    document.documentElement.style.overflow='hidden';
    try{history.pushState({edz:1},'');zPushed=true;}catch(err){zPushed=false;}
    zClose.focus();
  }
  function closeZoom(fromPop){
    if(!zoomEl)return;
    zoomEl.remove();zoomEl=null;zBox=null;
    document.documentElement.style.overflow='';
    if(zPushed){zPushed=false;if(!fromPop){try{history.back();}catch(err){}}}
    if(zFocus&&zFocus.focus){try{zFocus.focus();}catch(err){}}
    zFocus=null;
  }
  window.addEventListener('popstate',function(){if(zoomEl)closeZoom(true);});
  /* 제스처: 1손가락 이동(확대 시), 2손가락 핀치, 두 번 탭 1×↔2.5× */
  var zPts=new Map(),zPinch=null,zPan=null,zLast={t:0,x:0,y:0};
  function zDist(a,b){var dx=a.x-b.x,dy=a.y-b.y;return Math.sqrt(dx*dx+dy*dy)||1;}
  function zMid(a,b){return {x:(a.x+b.x)/2,y:(a.y+b.y)/2};}
  function zContent(sx,sy){return {x:(sx-zTx)/zK,y:(sy-zTy)/zK};}
  function bindGestures(v){
    v.addEventListener('pointerdown',function(e){
      try{v.setPointerCapture(e.pointerId);}catch(err){}
      zPts.set(e.pointerId,{x:e.clientX,y:e.clientY});
      if(zPts.size===2){var a=[].slice.call(zPts.values());var m=zMid(a[0],a[1]);
        zPinch={d:zDist(a[0],a[1]),k:zK,u:zContent(m.x,m.y)};zPan=null;}
      else{zPan={x:e.clientX,y:e.clientY,tx:zTx,ty:zTy};zPinch=null;}
    });
    v.addEventListener('pointermove',function(e){
      if(!zPts.has(e.pointerId))return;
      zPts.set(e.pointerId,{x:e.clientX,y:e.clientY});
      if(zPinch&&zPts.size>=2){var a=[].slice.call(zPts.values());var m=zMid(a[0],a[1]);
        zK=Math.min(zBase()*5,Math.max(zBase(),zPinch.k*zDist(a[0],a[1])/zPinch.d));
        zTx=m.x-zPinch.u.x*zK;zTy=m.y-zPinch.u.y*zK;zClamp();zRender();}
      else if(zPan&&zPts.size===1&&zK>zBase()*1.001){zTx=zPan.tx+e.clientX-zPan.x;zTy=zPan.ty+e.clientY-zPan.y;zClamp();zRender();}
    });
    function up(e){
      zPts.delete(e.pointerId);if(zPts.size<2)zPinch=null;if(zPts.size===0)zPan=null;
      if(e.type==='pointerup'&&!zPinch){
        var t=e.timeStamp;
        if(t-zLast.t<350&&Math.abs(e.clientX-zLast.x)<40&&Math.abs(e.clientY-zLast.y)<40){zLast.t=0;zToggle(e.clientX,e.clientY);}
        else zLast={t:t,x:e.clientX,y:e.clientY};
      }
    }
    v.addEventListener('pointerup',up);v.addEventListener('pointercancel',up);
  }
  /* 장 본문 탭 → 줌 뷰어. 버튼·퀴즈·탭·코드·핀 같은 조작 요소 위에서는 열지 않는다. */
  if(stage)stage.addEventListener('click',function(e){
    if(!reading()||zoomEl||inHub())return;
    var t=e.target;if(!t||!t.closest)return;
    var s=t.closest('.slide');if(!s)return;
    if(t.closest(NOOPEN))return;
    var i=deckSlides().indexOf(s);if(i<0)return;
    openZoom(i);
  });

  /* ---------- 세로 폰 한 줄 안내: 세션당 한 번 ---------- */
  var hintEl=null,HINTKEY='ed-zoom-hint-seen';
  function updateHint(){
    var on=false;
    if(reading()&&!inHub()&&window.innerHeight>window.innerWidth){
      try{on=sessionStorage.getItem(HINTKEY)!=='1';}catch(e){on=true;}
    }
    if(on&&!hintEl){
      hintEl=document.createElement('div');hintEl.className='ed-zoom-hint';
      var t=document.createElement('span');t.className='t';t.textContent='가로로 돌리면 더 크게 보입니다 · 장을 누르면 크게 볼 수 있습니다';
      var x=document.createElement('button');x.type='button';x.className='x';x.setAttribute('aria-label','안내 닫기');x.textContent='✕';
      x.addEventListener('click',function(){try{sessionStorage.setItem(HINTKEY,'1');}catch(e){}updateHint();});
      hintEl.appendChild(t);hintEl.appendChild(x);document.body.appendChild(hintEl);
    }
    if(hintEl)hintEl.classList.toggle('on',on);
  }

  /* slide-fit: 무대를 탐색줄 높이만큼 위로 비켜 맞춘다. 엔진의 resize→fit 이 먼저 돌 수 있으므로
     rAF 로 마지막에 다시 잰다(solo·pack·series 엔진 공통 — 이 파일이 더 먼저 등록된다). */
  function stageFit(){
    var st=document.getElementById('stage');
    if(!st)return;
    if(slideFit()){
      var nav=document.querySelector('.ed-reader-nav');
      var nh=(nav&&nav.getClientRects().length)?Math.round(nav.getBoundingClientRect().height):0;
      if(nh>0){
        var sc=Math.min(window.innerWidth/1920,(window.innerHeight-nh)/1080);
        st.style.transform='translate(-50%,-50%) scale('+sc+')';
        st.style.top='calc(50% - '+Math.round(nh/2)+'px)';
      }
    }else if(st.style.top){st.style.top='';}
  }
  function anchorCur(){
    var s=document.querySelector(curSel());
    if(s)anchorTop(s);
  }
  function fit(){
    var r=reading();
    var html=document.documentElement;
    var was=html.classList.contains('ed-compact');
    html.classList.toggle('ed-compact',r);
    html.classList.toggle('ed-slidefit',slideFit());
    if(zoomEl&&!r)closeZoom();
    applyScale();
    stageFit();
    sync();updateHint();
    lastW=window.innerWidth;
    if(r){if(!was)anchorCur();scrub();}
    document.dispatchEvent(new Event('edmode'));
  }
  document.addEventListener('deckstep',sync);
  /* 장이 바뀌면(탐색·검색·목차·해시·자습) 그 장의 머리로 스크롤한다.
     scrub 이 엔진을 맞출 때는 driving=true 라 스크롤을 건드리지 않는다. */
  document.addEventListener('deckslide',function(){
    sync();applyScale();updateHint();
    if(!reading()||inHub()||driving)return;
    anchorCur();
  });
  /* 세로 읽기에서 화살표·스페이스·Home·End 는 단계가 아니라 장을 넘긴다.
     탐색줄 단추도 같은 키를 누르므로 결과는 같다(입력은 창 캡처 단계에서 막아
     엔진의 문서 리스너에 닿지 않게 한다). 줌 뷰어가 열려 있으면 그 키 처리가 먼저다. */
  var NEXT={ArrowRight:1,ArrowDown:1,PageDown:1,' ':1,Enter:1},
      PREV={ArrowLeft:1,ArrowUp:1,PageUp:1,Backspace:1};
  window.addEventListener('keydown',function(e){
    if(zoomEl){zKeys(e);return;}
    if(!reading()||inHub()||e.isComposing)return;
    if(document.querySelector('.st-modal.st-show,.st-print.st-show,.ed-sch.on,.ed-toc.on'))return;
    var t=e.target;
    if(t&&(t.isContentEditable||(t.closest&&t.closest('a[href],button,input,textarea,select,summary,.code,.tabs,.faq,.pin-shot,.pin-list,.ed-sch,.ed-toc'))))return;
    var k=e.key;
    if(NEXT[k]){e.preventDefault();e.stopPropagation();jump(1);}
    else if(PREV[k]){e.preventDefault();e.stopPropagation();jump(-1);}
    else if(k==='Home'){e.preventDefault();e.stopPropagation();jumpTo(0);}
    else if(k==='End'){e.preventDefault();e.stopPropagation();jumpTo(1e9);}
  },true);
  window.addEventListener('scroll',function(){ if(reading())scrub(); },{passive:true});
  window.addEventListener('resize',function(){
    sync();requestAnimationFrame(stageFit);
    if(reading()){
      applyScale();updateHint();
      if(zoomEl)zShow(zI);
      if(lastW&&lastW!==window.innerWidth)anchorCur(); /* 회전해도 읽던 장 머리를 유지한다 */
      lastW=window.innerWidth;
      scrub();
    }
  });
  /* 인쇄 때 엔진이 모든 장을 마지막 단계로 펼치므로, 돌아와서 비현재 장의 그린 값 표시를
     지우면 다음 scrub 이 reached 상태로 되돌린다. */
  window.addEventListener('afterprint',function(){
    deckSlides().forEach(function(s){s._edPaint=null;});
    if(reading())scrub();
  });
  window.addEventListener('load',function(){ requestAnimationFrame(stageFit); if(reading()){applyScale();scrub();} });
  mqNarrow.addEventListener('change',fit);mqFit.addEventListener('change',fit);
  fit();
})();
