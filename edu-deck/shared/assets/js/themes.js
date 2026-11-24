/* themes.js — 저작 도구: legacy 테마·스타일 계열 실시간 미리보기 패널.
   ?themes=1 또는 T 키로 패널을 연다(기본은 숨김 — 일반 시청자에게 보이지 않는다).
   ?theme=<id> / ?family=<studio|vivid|drawing|classic> 는 패널 없이 바로 미리보기를
   적용한다(classic 은 속성 제거). 전환은 <html data-theme|data-family> 교체 —
   themes.css·families.css 블록은 덱에 이미 임베드돼 있어 따로 CSS 를 주입하지 않는다.
   덱 실제 테마·계열은 deck.json 'theme'·'family' 가 정하고, 여기서 바꾼 것은 이
   브라우저·이 파일의 localStorage('edu-theme-preview-<파일이름>' 테마,
   'edu-family-preview-<파일이름>' 계열)에만 남는 세션 미리보기다.

   상호배제: themes.css 블록은 색뿐 아니라 여백·모서리·전환까지 바꾸므로 테마
   미리보기와 계열 미리보기가 동시에 붙는 것을 금지한다 — 한쪽을 켜면 다른 쪽
   미리보기 속성을 제거하고, 해제(reset)하면 빌드 본래 data-theme·data-family 로
   정확히 복원한다. 프리셋 덱(페이지 <style> 의 preset-css 표식)에서는 계열
   미리보기를 비활성화한다(프리셋이 :root·.slide.dark 에 직접 적용돼 루트 속성
   만으로는 색·모서리·어두운 면 규칙이 남기 때문). 팩 덱(resource_pack)·시리즈
   포털(.deck[data-ep])은 자체 스타일 계층이라 비활성. */
(function(){
  var doc=document, root=doc.documentElement, body=doc.body;
  if(doc.querySelector('meta[name="edu-deck-resource-pack"],.deck[data-ep]'))return;
  var F=(decodeURIComponent(location.pathname.split('/').pop())||'deck');
  var LS='edu-theme-preview-'+F, FLS='edu-family-preview-'+F;

  /* 내장 17종 한글명 — 미등록 사용자 정의 [data-theme] 블록은 id 만 표시한다 */
  var KR={classic:'기본',ocean:'청록 기술',cobalt:'코발트 격식',forest:'포레스트 자연',
    solar:'솔라 현장',berry:'베리 서비스',cocoa:'코코아 실무',graphite:'그래파이트 절차',
    midnight:'미드나잇 야간',mono:'무채 인쇄',brick:'벽돌 인문',honey:'앰버 안내',
    mint:'민트 입문',violet:'보라 창의',coral:'코랄 소통',olive:'올리브 실무',espresso:'다크 카페'};
  /* 스타일 계열 — families.css 의 [data-family] 블록 id 와 1:1 (classic=속성 없음=오늘의 모습) */
  var FAMIDS=['studio','vivid','drawing'];
  var FAMKR={classic:'기본',studio:'스튜디오',vivid:'비비드',drawing:'도면'};
  /* families.css 블록을 덱이 아직 싣지 않을 때 쓰는 대표 스와치(계열 팔레트 초안) —
     블록이 있으면 collect() 가 읽은 실제 값으로 덮어쓴다 */
  var FAM_SW={
    studio:{paper:'#F5F3ED',ink:'#1E2A44',accent:'#E8772E','accent-light':'#2F6FB0'},
    vivid:{paper:'#F6F4EF',ink:'#0E1A33',accent:'#E8772E','accent-light':'#9CBFF7'},
    drawing:{paper:'#FAF8F3',ink:'#1C2530',accent:'#E34D2E','accent-light':'#2F6FB0'}};
  /* 스와치 4점: 지면 · 먹 · 주색 · 보조 — 라이트/다크 반전과 주·보조 색조를 함께 대표 */
  var SW=['paper','ink','accent','accent-light'];

  /* 프리셋 덱 감지 — 페이지 <style> 안에 preset-css 표식이 있으면 계열 미리보기 비활성.
     (패널 계열 섹션을 만들지 않고 ?family= · 저장 키를 모두 무시한다) */
  var preset=false;
  [].slice.call(doc.querySelectorAll('style')).forEach(function(s){
    if((s.textContent||'').indexOf('preset-css')>=0)preset=true;});
  var famOn=!preset;

  /* 페이지 안 실제 CSS 에서 [data-theme="id"]·[data-family="id"] 블록을 찾아
     테마 목록과 계열 스와치를 만든다. classic 은 블록이 없으므로 :root 값으로 맨 앞에 단다. */
  function rulesOf(rule,acc){
    var sel=rule.selectorText||'',m=/^\[data-theme="([\w-]+)"\]$/.exec(sel);
    if(m)acc.list.push({id:m[1],st:rule.style});
    else if(sel===':root')acc.rootSt=rule.style;
    else if((m=/^\[data-family="([\w-]+)"\]$/.exec(sel)))acc.fams.push({id:m[1],st:rule.style});
    if(rule.cssRules)for(var i=0;i<rule.cssRules.length;i++)rulesOf(rule.cssRules[i],acc);
  }
  function collect(){
    var acc={rootSt:null,list:[],fams:[]};
    [].slice.call(doc.styleSheets).forEach(function(sh){
      var rs;try{rs=sh.cssRules;}catch(e){return;}
      if(!rs)return;
      for(var i=0;i<rs.length;i++)rulesOf(rs[i],acc);
    });
    var sw=function(st){var o={};SW.forEach(function(k){
      o[k]=st?st.getPropertyValue('--'+k).trim():'';});return o;};
    var items=acc.list.map(function(t){return{id:t.id,sw:sw(t.st)};});
    if(acc.rootSt)items.unshift({id:'classic',sw:sw(acc.rootSt)});
    var famSw={};acc.fams.forEach(function(t){famSw[t.id]=sw(t.st);});
    return{items:items,famSw:famSw};
  }

  var got=collect(),items=got.items,famSw=got.famSw;
  if(!items.length)return;                      /* 테마 블록이 없는 문서에서는 무동작 */
  var ids=items.map(function(t){return t.id;});
  var famIds=FAMIDS.concat(['classic']);        /* ?family= 허용 값 (classic=속성 제거) */

  /* 빌드 시점 본래 속성 — 해제(reset) 시 이 값으로 정확히 복원한다(null=속성 없음=classic) */
  var origTheme=root.getAttribute('data-theme');
  var origFamily=root.getAttribute('data-family');
  var built=origTheme||'classic';               /* deck.json 이 정한 실제 테마 */
  var builtFamily=origFamily||'classic';        /* deck.json 이 정한 실제 계열 */
  /* 미리보기 상태 — 둘 중 하나만 켜진다(상호배제). null 이면 그쪽은 빌드 상태 */
  var pvTheme=null,pvFamily=null;

  var panel=null;
  function buildPanel(){
    function el(tag,cls,txt){var e=doc.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e;}
    panel=el('div','','');panel.id='edThemes';panel.setAttribute('role','dialog');panel.setAttribute('aria-label','테마 미리보기 (저작 도구)');
    var head=el('div','ed-th-head');head.appendChild(el('b',null,'테마 미리보기'));
    var x=el('button','ed-th-x','닫기');x.type='button';x.addEventListener('click',function(){show(false);});head.appendChild(x);
    var note=el('div','ed-th-note');
    note.innerHTML='저작 도구 — 이 브라우저 미리보기만 바뀝니다. 실제 테마는 deck.json 의 theme 이 정합니다. 이 덱의 빌드 테마: <b>'+built+'</b>'
      +(famOn?' · 계열: <b>'+builtFamily+'</b>':'')+'<br><span class="ed-th-legend">스와치: 지면 · 먹 · 주색 · 보조'
      +(famOn?' — 테마와 계열은 동시에 켜지지 않습니다':'')+'</span>';
    var list=el('div','ed-th-list');
    if(famOn){
      var flab=el('div','ed-th-legend','스타일 계열');
      flab.style.padding='6px 10px 2px';list.appendChild(flab);
      FAMIDS.forEach(function(fid){
        var b=el('button','ed-th-item');b.type='button';b.setAttribute('data-fam',fid);
        b.setAttribute('aria-pressed','false');
        var dots=el('span','ed-th-dots');dots.title='지면 · 먹 · 주색 · 보조';
        var swf=famSw[fid]||FAM_SW[fid]||{};
        SW.forEach(function(k){var d=el('i');d.style.background=swf[k]||'#999';dots.appendChild(d);});
        b.appendChild(dots);
        b.appendChild(el('span','ed-th-name',fid+' · '+FAMKR[fid]));
        if(fid===builtFamily)b.appendChild(el('span','ed-th-tag','빌드'));
        b.addEventListener('click',function(){applyFamily(fid,true);});
        list.appendChild(b);
      });
      var bf=el('button','ed-th-item');bf.type='button';bf.setAttribute('data-fam','classic');
      bf.setAttribute('aria-pressed','false');
      bf.appendChild(el('span','ed-th-name','기본 — 빌드 상태 복원(해제)'));
      bf.addEventListener('click',function(){reset();});
      list.appendChild(bf);
      var tlab=el('div','ed-th-legend','테마 (classic 계열 색 조합)');
      tlab.style.padding='8px 10px 2px';list.appendChild(tlab);
    }
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
    var rs=el('button','ed-th-reset','빌드 상태로 되돌리기');rs.type='button';
    rs.addEventListener('click',function(){reset();});
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
    /* 상대 미리보기가 켜진 동안에는 이쪽 목록의 선택 표시를 비운다(상호배제 표시) */
    var curT=pvFamily!==null?null:(root.getAttribute('data-theme')||'classic');
    [].slice.call(panel.querySelectorAll('.ed-th-item[data-th]')).forEach(function(b){
      var on=b.getAttribute('data-th')===curT;
      b.classList.toggle('on',on);
      b.setAttribute('aria-pressed',on?'true':'false');});
    var curF=pvTheme!==null?null:(root.getAttribute('data-family')||'classic');
    [].slice.call(panel.querySelectorAll('.ed-th-item[data-fam]')).forEach(function(b){
      var on=b.getAttribute('data-fam')===curF;
      b.classList.toggle('on',on);
      b.setAttribute('aria-pressed',on?'true':'false');});
  }
  /* <html> 속성 실제 반영 — 상호배제와 빌드 복원을 한 곳에서 강제한다 */
  function paint(){
    if(pvFamily!==null){                        /* 계열 미리보기: 테마 속성 제거 */
      root.removeAttribute('data-theme');
      if(pvFamily==='classic')root.removeAttribute('data-family');
      else root.setAttribute('data-family',pvFamily);
    }else if(pvTheme!==null){                   /* 테마 미리보기: 계열 속성 제거 */
      root.removeAttribute('data-family');
      if(pvTheme==='classic')root.removeAttribute('data-theme');
      else root.setAttribute('data-theme',pvTheme);
    }else{                                      /* 미리보기 없음: 빌드 본래 속성 복원 */
      if(origTheme===null)root.removeAttribute('data-theme');
      else root.setAttribute('data-theme',origTheme);
      if(origFamily===null)root.removeAttribute('data-family');
      else root.setAttribute('data-family',origFamily);
    }
    mark();
  }
  function apply(id,save){
    if(ids.indexOf(id)<0)return;
    pvTheme=id;pvFamily=null;paint();
    /* 빌드 테마로 되돌리면 키를 통째로 지운다 — 남겨 두면 추후 deck.json 테마 변경
       재빌드 시 구버전 미리보기가 새 빌드를 덮어쓰는 잔류 버그가 된다.
       상호배제: 테마를 저장하면 계열 미리보기 키도 함께 지운다. */
    if(save)try{
      if(id===built)localStorage.removeItem(LS);else localStorage.setItem(LS,id);
      localStorage.removeItem(FLS);
    }catch(e){}
    if(window.edToast)edToast('테마 미리보기: '+id+' — 이 브라우저에만 적용됩니다 (빌드: '+built+')');
  }
  function applyFamily(id,save){
    if(!famOn||famIds.indexOf(id)<0)return;
    pvFamily=id;pvTheme=null;paint();
    if(save)try{
      if(id===builtFamily)localStorage.removeItem(FLS);else localStorage.setItem(FLS,id);
      localStorage.removeItem(LS);
    }catch(e){}
    if(window.edToast)edToast('계열 미리보기: '+id+' — 이 브라우저에만 적용됩니다 (빌드: '+builtFamily+')');
  }
  /* 미리보기 해제 — 빌드 시점의 본래 data-theme·data-family 로 정확히 복원하고
     두 미리보기 키를 모두 지운다 */
  function reset(){
    pvTheme=null;pvFamily=null;paint();
    try{localStorage.removeItem(LS);localStorage.removeItem(FLS);}catch(e){}
    if(window.edToast)edToast('미리보기 해제 — 빌드 상태로 되돌렸습니다');
  }
  function show(on){if(!panel)buildPanel();panel.classList.toggle('on',on);if(on)mark();}
  function toggle(){show(!(panel&&panel.classList.contains('on')));}

  /* 초기 적용: ?family= > ?theme= > localStorage 미리보기 > 빌드 상태.
     두 파라미터가 함께 오면 계열이 이긴다(어차피 동시에 붙을 수 없다).
     URL 파라미터는 저장하지 않는다(링크로 공유할 때 1회 미리보기). */
  var P=new URLSearchParams(location.search);
  var wantT=P.get('theme'),wantF=P.get('family');
  if(famOn&&wantF!==null&&famIds.indexOf(wantF)>=0)applyFamily(wantF,false);
  else if(wantT!==null&&ids.indexOf(wantT)>=0)apply(wantT,false);
  else{try{
    var sf=localStorage.getItem(FLS),s=localStorage.getItem(LS);
    if(famOn&&sf&&famIds.indexOf(sf)>=0&&sf!==builtFamily)applyFamily(sf,false);
    else if(s&&ids.indexOf(s)>=0&&s!==built)apply(s,false);
  }catch(e){}}
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
  window.eduThemePreview={apply:apply,family:applyFamily,reset:reset,toggle:toggle,
    built:function(){return built;},builtFamily:function(){return builtFamily;},
    themes:ids,families:famOn?famIds.slice(0):[]};
})();
