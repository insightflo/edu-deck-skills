/* themes.js — 저작 도구: legacy 테마 실시간 미리보기 패널.
   ?themes=1 또는 T 키로 패널을 연다(기본은 숨김 — 일반 시청자에게 보이지 않는다).
   ?theme=<id> 는 패널 없이 바로 미리보기를 적용한다(classic 은 속성 제거).
   전환은 <html data-theme> 교체 — themes.css 블록은 덱에 이미 임베드돼 있어
   따로 CSS 를 주입하지 않는다. 덱 실제 테마는 deck.json 'theme' 이 정하고,
   여기서 바꾼 것은 이 브라우저·이 파일의 localStorage('edu-theme-preview-<파일이름>')
   에만 남는 세션 미리보기다. 팩 덱(resource_pack)·시리즈 포털(.deck[data-ep])은
   자체 스타일 계층이라 비활성. */
(function(){
  var doc=document, root=doc.documentElement, body=doc.body;
  if(doc.querySelector('meta[name="edu-deck-resource-pack"],.deck[data-ep]'))return;
  var LS='edu-theme-preview-'+(decodeURIComponent(location.pathname.split('/').pop())||'deck');

  /* 내장 17종 한글명 — 미등록 사용자 정의 [data-theme] 블록은 id 만 표시한다 */
  var KR={classic:'기본',ocean:'청록 기술',cobalt:'코발트 격식',forest:'포레스트 자연',
    solar:'솔라 현장',berry:'베리 서비스',cocoa:'코코아 실무',graphite:'그래파이트 절차',
    midnight:'미드나잇 야간',mono:'무채 인쇄',brick:'벽돌 인문',honey:'앰버 안내',
    mint:'민트 입문',violet:'보라 창의',coral:'코랄 소통',olive:'올리브 실무',espresso:'다크 카페'};
  /* 스와치 4점: 지면 · 먹 · 주색 · 보조 — 라이트/다크 반전과 주·보조 색조를 함께 대표 */
  var SW=['paper','ink','accent','accent-light'];

  /* 페이지 안 실제 CSS 에서 [data-theme="id"] 블록을 찾아 목록과 대표 스와치를 만든다.
     classic 은 블록이 없으므로 :root 값으로 맨 앞에 단다. */
  function rulesOf(rule,acc){
    var sel=rule.selectorText||'',m=/^\[data-theme="([\w-]+)"\]$/.exec(sel);
    if(m)acc.list.push({id:m[1],st:rule.style});
    else if(sel===':root')acc.rootSt=rule.style;
    if(rule.cssRules)for(var i=0;i<rule.cssRules.length;i++)rulesOf(rule.cssRules[i],acc);
  }
  function collect(){
    var acc={rootSt:null,list:[]};
    [].slice.call(doc.styleSheets).forEach(function(sh){
      var rs;try{rs=sh.cssRules;}catch(e){return;}
      if(!rs)return;
      for(var i=0;i<rs.length;i++)rulesOf(rs[i],acc);
    });
    var list=acc.list,found=acc;
    var sw=function(st){var o={};SW.forEach(function(k){
      o[k]=st?st.getPropertyValue('--'+k).trim():'';});return o;};
    var items=list.map(function(t){return{id:t.id,sw:sw(t.st)};});
    if(found.rootSt)items.unshift({id:'classic',sw:sw(found.rootSt)});
    return items;
  }

  var items=collect();
  if(!items.length)return;                      /* 테마 블록이 없는 문서에서는 무동작 */
  var ids=items.map(function(t){return t.id;});
  var built=root.getAttribute('data-theme')||'classic';  /* deck.json 이 정한 실제 테마 */

  var panel=null;
  function buildPanel(){
    function el(tag,cls,txt){var e=doc.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e;}
    panel=el('div','','');panel.id='edThemes';panel.setAttribute('role','dialog');panel.setAttribute('aria-label','테마 미리보기 (저작 도구)');
    var head=el('div','ed-th-head');head.appendChild(el('b',null,'테마 미리보기'));
    var x=el('button','ed-th-x','닫기');x.type='button';x.addEventListener('click',function(){show(false);});head.appendChild(x);
    var note=el('div','ed-th-note');
    note.innerHTML='저작 도구 — 이 브라우저 미리보기만 바뀝니다. 실제 테마는 deck.json 의 theme 이 정합니다. 이 덱의 빌드 테마: <b>'+built+'</b><br><span class="ed-th-legend">스와치: 지면 · 먹 · 주색 · 보조</span>';
    var list=el('div','ed-th-list');
    items.forEach(function(t){
      var b=el('button','ed-th-item');b.type='button';b.setAttribute('data-th',t.id);
      b.setAttribute('aria-pressed','false');
      var dots=el('span','ed-th-dots');dots.title='지면 · 먹 · 주색 · 보조';
      SW.forEach(function(k){var d=el('i');d.style.background=t.sw[k]||'#999';dots.appendChild(d);});
      b.appendChild(dots);
      b.appendChild(el('span','ed-th-name',t.id+(KR[t.id]?' · '+KR[t.id]:'')));
      if(t.id===built)b.appendChild(el('span','ed-th-tag','빌드'));
      b.addEventListener('click',function(){apply(t.id,true);});
      list.appendChild(b);
    });
    var foot=el('div','ed-th-foot');
    var rs=el('button','ed-th-reset','빌드 테마로 되돌리기');rs.type='button';
    rs.addEventListener('click',function(){apply(built,true);});
    foot.appendChild(rs);foot.appendChild(el('span','ed-th-kbd','T 토글 · Esc 닫기'));
    panel.appendChild(head);panel.appendChild(note);panel.appendChild(list);panel.appendChild(foot);
    /* 패널 안 클릭이 장 넘김(엔진 document click)으로 번지지 않게 여기서 멈춘다 */
    panel.addEventListener('click',function(e){e.stopPropagation();});
    panel.addEventListener('dblclick',function(e){e.stopPropagation();});
    panel.addEventListener('touchstart',function(e){e.stopPropagation();},{passive:true});
    panel.addEventListener('touchend',function(e){e.stopPropagation();});
    body.appendChild(panel);
  }
  function mark(){
    if(!panel)return;
    var cur=root.getAttribute('data-theme')||'classic';
    [].slice.call(panel.querySelectorAll('.ed-th-item')).forEach(function(b){
      var on=b.getAttribute('data-th')===cur;
      b.classList.toggle('on',on);
      b.setAttribute('aria-pressed',on?'true':'false');});
  }
  function apply(id,save){
    if(ids.indexOf(id)<0)return;
    if(id==='classic')root.removeAttribute('data-theme');else root.setAttribute('data-theme',id);
    /* 빌드 테마로 되돌리면 키를 통째로 지운다 — 남겨 두면 추후 deck.json 테마 변경
       재빌드 시 구버전 미리보기가 새 빌드를 덮어쓰는 잔류 버그가 된다 */
    if(save)try{
      if(id===built)localStorage.removeItem(LS);else localStorage.setItem(LS,id);
    }catch(e){}
    mark();
    if(window.edToast)edToast('테마 미리보기: '+id+' — 이 브라우저에만 적용됩니다 (빌드: '+built+')');
  }
  function show(on){if(!panel)buildPanel();panel.classList.toggle('on',on);if(on)mark();}
  function toggle(){show(!(panel&&panel.classList.contains('on')));}

  /* 초기 적용: ?theme= 파라미터 > localStorage 미리보기 > 빌드 테마.
     URL 파라미터는 저장하지 않는다(링크로 공유할 때 1회 미리보기). */
  var P=new URLSearchParams(location.search);
  var want=P.get('theme');
  if(want!==null&&ids.indexOf(want)>=0)apply(want,false);
  else{try{var s=localStorage.getItem(LS);if(s&&ids.indexOf(s)>=0&&s!==built)apply(s,false);}catch(e){}}
  if(P.has('themes'))show(true);

  window.addEventListener('keydown',function(e){
    if(panel&&panel.classList.contains('on')&&e.key==='Escape'){
      e.preventDefault();e.stopImmediatePropagation();show(false);return;}
    if(e.ctrlKey||e.metaKey||e.altKey||e.isComposing)return;
    var t=e.target;
    if(t&&(t.isContentEditable||/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)))return;
    /* 상위 모달·오버레이가 열려 있으면 패널은 모달 뒤에서 켜지면 안 된다 */
    if(doc.querySelector('.st-modal.st-show,.st-print.st-show,.ed-sch.on,.ed-toc.on'))return;
    /* 접촉판·캡처·인쇄·발표자 표면에서는 토글 입력 자체를 무시한다 */
    if(root.classList.contains('is-sheet')||root.classList.contains('is-shot')||
       body.classList.contains('st-printing')||body.classList.contains('st-presenter'))return;
    if(e.key==='t'||e.key==='T'||e.key==='ㅅ'){e.preventDefault();toggle();}
  },true);
  window.eduThemePreview={apply:apply,toggle:toggle,built:function(){return built;},themes:ids};
})();
