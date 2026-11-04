/* talk.js — deck.json "talk" 이 있는 발표 덱: T/R 타이머, N 패널 머리 계획, V 발표자 보기.
   발표자 보기는 같은 파일을 ?presenter 로 열어 BroadcastChannel(없으면 storage)로 양방향 동기한다. */
(function(){
var doc=document, root=doc.documentElement, body=doc.body;
var P=new URLSearchParams(location.search), PRESENTER=P.has('presenter');
var STUDY=function(){return window.EDU_STUDY||{};};
var TALK=function(){var t=STUDY().talk;return (t&&typeof t==='object')?t:null;};
function slides(){return [].slice.call(doc.querySelectorAll('#stage>.slide'));}
function fmt(s){s=Math.max(0,Math.round(s));var m=Math.floor(s/60),x=s%60;return m+':'+('0'+x).slice(-2);}
function el(tag,cls,txt){var e=doc.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e;}

if(PRESENTER){doc.addEventListener('DOMContentLoaded',function(){body.classList.add('st-presenter');});body&&body.classList.add('st-presenter');}

/* ---------- 타이머 상태 ---------- */
var elapsed=0,running=false,lastTick=0,timer=null;
function tick(){var n=Date.now();if(running)elapsed+=(n-lastTick)/1000;lastTick=n;paintClock();}
function timerStart(){if(running)return;running=true;lastTick=Date.now();timer=setInterval(function(){tick();post();},500);paintClock();}
function timerStop(){if(!running)return;tick();running=false;clearInterval(timer);paintClock();}
function timerToggle(){running?timerStop():timerStart();post();}
function timerReset(){elapsed=0;lastTick=Date.now();paintClock();post();}

/* ---------- 발표 계획(누적) ---------- */
var planEnd=[],planSec=[];
function buildPlan(){var acc=0;planEnd=slides().map(function(s){var sec=parseFloat(s.getAttribute('data-sec'))||0;planSec.push(sec);acc+=sec;return acc;});}

/* ---------- 시계 칠하기 ---------- */
var clockEl=null;
function paintClock(){
 var i=(function(){try{return deckInfo().slide||0;}catch(e){return 0;}})();
 var plan=planEnd[i]||0,t=TALK();
 if(clockEl){clockEl.innerHTML='';clockEl.appendChild(doc.createTextNode(fmt(elapsed)+' '));
  var pl=el('span','plan','/ '+fmt(plan));clockEl.appendChild(pl);
  clockEl.classList.toggle('is-run',running);clockEl.classList.toggle('is-late',running&&plan>0&&elapsed>plan);}
 if(presClock){presClock.querySelector('.t').textContent=fmt(elapsed);
  var r=t?(t.total||0)-elapsed:0;
  presClock.querySelector('.r').textContent=t?('남은 시간 '+fmt(Math.abs(r))+(r<0?' 초과':'')):'';
  presClock.classList.toggle('is-run',running);presClock.classList.toggle('is-late',running&&plan>0&&elapsed>plan);}
}

/* ---------- 노트 패널 머리(D2) ---------- */
function paintNotesHead(){
 var h=doc.querySelector('#notes .h');if(!h||!TALK())return;
 var i=deckInfo().slide||0,sec=planSec[i]||0,end=planEnd[i]||0;
 h.textContent=(sec?('이 장 '+sec+'초 · '):'')+'~'+fmt(end)+'까지 · 발표자 노트 (N으로 닫기)';
}

/* ---------- 동기 채널: BroadcastChannel + storage 예비(두 채널로 보내고 id로 중복을 버림) ---------- */
var UID=Math.random().toString(36).slice(2),MID=0,SEEN={},BUSK='edtalk'+location.pathname;
var bc=(window.BroadcastChannel)?new BroadcastChannel(BUSK):null;
function post(msg){var m=Object.assign({_u:UID,_i:++MID,type:'state',slide:curSlide(),step:curStep(),el:elapsed,run:running,total:(TALK()||{}).total||0},msg||{});
 if(bc)try{bc.postMessage(m);}catch(e){}
 try{localStorage.setItem(BUSK,JSON.stringify(m));}catch(e){}}
function curSlide(){try{return deckInfo().slide||0;}catch(e){return 0;}}
function curStep(){try{return deckInfo().step||0;}catch(e){return 0;}}
var applying=false;
function onMsg(m){
 if(!m||typeof m!=='object'||!m._u)return;
 var k=m._u+':'+m._i;if(SEEN[k])return;SEEN[k]=1;
 if(m.type==='state'&&PRESENTER){elapsed=m.el||0;running=!!m.run;
  if(!applying&&(curSlide()!==m.slide||curStep()!==m.step)){applying=true;try{deckGo(m.slide,m.step);}finally{applying=false;}}
  paintPres();}
 if(m.type==='go'&&!PRESENTER){if(curSlide()!==m.slide||curStep()!==m.step)deckGo(m.slide,m.step);}
 if(m.type==='timer'&&!PRESENTER){if(m.op==='reset')timerReset();else timerToggle();}
 if(m.type==='req'&&!PRESENTER)post();
}
if(bc)bc.onmessage=function(e){onMsg(e.data);};
window.addEventListener('storage',function(e){if(e.key===BUSK&&e.newValue){try{onMsg(JSON.parse(e.newValue));}catch(x){}}});

/* ---------- 발표자 창 ---------- */
var presClock=null,presNext=null,presNotes=null,presCur=null;
function paintPres(){
 if(!PRESENTER)return;
 var i=curSlide(),ss=slides();
 if(presCur)presCur.textContent=(i+1)+' / '+ss.length+'장 · '+(curStep()+1)+'단계';
 if(presNext){presNext.innerHTML='';var nx=ss[i+1];
  if(nx){var c=nx.cloneNode(true);c.classList.add('active');c.removeAttribute('id');
   var w=presNext.clientWidth||320;c.style.setProperty('--pres-ns',(w/1920).toFixed(4));
   presNext.appendChild(c);}else{presNext.appendChild(el('div',null,'마지막 장'));}}
 var n=ss[i]&&ss[i].querySelector('.notes');
 if(presNotes)presNotes.innerHTML='<div class="h">노트</div>'+(n?String(n.innerHTML):'(없음)');
 paintClock();
}
function openPresenter(){
 var u=location.pathname+'?presenter';
 var w=window.open(u,'edpresenter','width=1100,height=760');
 if(!w||w.closed){if(window.edToast)edToast('팝업이 차단됐습니다. 팝업을 허용해 주세요.');return;}
}
function buildPresDom(){
 var p=el('div','ed-pres');
 presClock=el('div','ed-pres-clock');presClock.appendChild(el('span','t','0:00'));presClock.appendChild(el('span','r',''));
 var row=el('div','ed-pres-row');
 var bP=el('button','ed-pbtn','← 이전'),bN=el('button','ed-pbtn','다음 →'),bT=el('button','ed-pbtn','타이머'),bR=el('button','ed-pbtn','리셋');
 bP.addEventListener('click',function(){go(-1);});bN.addEventListener('click',function(){go(1);});
 bT.addEventListener('click',function(){post({type:'timer',op:'toggle'});running?timerStop():timerStart();});
 bR.addEventListener('click',function(){post({type:'timer',op:'reset'});elapsed=0;paintClock();});
 row.appendChild(bP);row.appendChild(bN);row.appendChild(bT);row.appendChild(bR);
 presCur=el('div','ed-pres-cur');
 var nl=el('div','ed-pres-nextlab','다음 장 미리보기');
 presNext=el('div','ed-pres-next');
 presNotes=el('div','ed-pres-notes');
 p.appendChild(presClock);p.appendChild(presCur);p.appendChild(row);p.appendChild(nl);p.appendChild(presNext);p.appendChild(presNotes);
 body.appendChild(p);
}
function go(d){var i=curSlide()+d;i=Math.max(0,Math.min(slides().length-1,i));post({type:'go',slide:i,step:0});if(!applying){applying=true;try{deckGo(i,0);}finally{applying=false;}}paintPres();}
function presFit(){var s=Math.min((innerWidth*0.62)/1920,(innerHeight*0.72)/1080);root.style.setProperty('--pres-s',s.toFixed(4));}
window.addEventListener('resize',presFit);

/* ---------- 키 ---------- */
window.addEventListener('keydown',function(e){
 if(!TALK()&&!PRESENTER)return;
 if(e.ctrlKey||e.metaKey||e.altKey||e.isComposing)return;
 var t=e.target;if(t&&(t.isContentEditable||/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)))return;
 var k=e.key;
 if(k==='t'||k==='T'||k==='ㅅ'){e.preventDefault();timerToggle();}
 else if(k==='r'||k==='R'||k==='ㄱ'){e.preventDefault();timerReset();}
 else if((k==='v'||k==='V'||k==='ㅍ')&&!PRESENTER){e.preventDefault();openPresenter();}
},true);

/* ---------- 초기화 ---------- */
function init(){
 var t=TALK();if(!t&&!PRESENTER)return;
 root.classList.add('ed-talk');
 buildPlan();
 clockEl=doc.getElementById('ed-clock');
 if(PRESENTER){body.classList.add('st-presenter');presFit();buildPresDom();post({type:'req'});}
 paintClock();paintNotesHead();
 doc.addEventListener('deckslide',function(){paintClock();paintNotesHead();if(PRESENTER)paintPres();else if(!applying)post();});
 doc.addEventListener('deckstep',function(){if(!PRESENTER&&!applying)post();});
 /* 발표 키는 발표 덱일 때만 도움말에 단다(목차·검색은 viewer.js 가 항상 표기) */
 var help=doc.getElementById('help');
 if(help&&!PRESENTER)help.textContent=help.textContent.replace('N 발표자 노트','N 발표자 노트 · T 타이머 · R 리셋 · V 발표자 보기');
 var nav=doc.querySelector('.ed-reader-nav');
 if(nav){var b=el('button',null,'타이머');b.type='button';b.addEventListener('click',function(){timerToggle();});
  nav.insertBefore(b,nav.querySelector('.ed-reader-status')||null);}
}
if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',init);else init();
})();
