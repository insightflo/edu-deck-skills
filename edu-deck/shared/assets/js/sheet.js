/* 저자 검수 뷰어 모드 — ?sheet(전 장 축소판·접촉판)과 ?shot=N(한 장 캡처).
   덱 결과물 하나를 URL 만으로 검수·캡처에 쓴다. 수업·발표 동작은 바꾸지 않는다:
   파라미터가 없으면 아무 일도 하지 않는다. 단계·애니메이션의 주인은 기존 엔진이고
   여기서는 클래스만 단다(st-sheet 는 motion.js 정적 판정에 합류해 전 장 완성 상태). */
(function(){
  'use strict';
  var P=new URLSearchParams(location.search);
  if(P.has('sheet')){
    document.documentElement.classList.add('is-sheet');
    document.body.classList.add('st-sheet'); /* 전 장 정적 완결(motion.js staticMode) */
    var cols=parseInt(P.get('sheet')||'',10);
    if(cols>=2&&cols<=6)document.documentElement.style.setProperty('--sheet-cols',cols);
    try{if(window.eduMotion&&window.eduMotion.settle)window.eduMotion.settle();}catch(e){}
    return;
  }
  var shot=P.get('shot');
  if(shot!==null){
    var n=parseInt(shot,10)||0;
    document.documentElement.classList.add('is-shot');
    document.body.classList.add('st-shot');
    var go=function(){ if(typeof window.deckGo==='function')window.deckGo(n);else setTimeout(go,30); };
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go);else go();
  }
})();
