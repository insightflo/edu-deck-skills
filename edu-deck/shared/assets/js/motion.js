/* edu-deck semantic motion. Sole motion owner for legacy, packs and series.
 * Presentation engines own visibility and grading; this module only animates the
 * already-visible semantic state. All effects are finite and cancellable.
 * Approved exceptions: title blur <= 6px / m2, SVG stroke drawing / m3.
 */
(function(){
  'use strict';
  if(window.eduMotion) return;
  const stage=document.getElementById('stage');
  if(!stage) return;
  const reduce=matchMedia('(prefers-reduced-motion: reduce)');
  const mediaPrint=matchMedia('print');
  let printing=false, still=false, seen=new WeakMap(), animations=new Set(), cleanups=new Set(), active=null, priorStep=-1, queued=false, transition=null, navigation=0;
  // P0-2 silent-slide audit: every real signature firing is recorded here as a
  // frozen {slide,step,sig} entry (bounded window; audit needs recency, not history).
  const sigLog=[];
  const all=(q,r=document)=>Array.from(r.querySelectorAll(q));
  const current=()=>document.body.classList.contains('in-hub')?null:stage.querySelector('.deck.on>.slide.active,:scope>.slide.active');
  const staticMode=()=>reduce.matches||printing||mediaPrint.matches||document.body.classList.contains('st-self')||document.body.classList.contains('st-printing')||document.body.classList.contains('st-presenter')||document.body.classList.contains('st-sheet');
  function token(name,el=stage){return getComputedStyle(el).getPropertyValue(name).trim()||getComputedStyle(document.documentElement).getPropertyValue(name).trim();}
  function duration(name,el){const v=token('--'+name,el);return parseFloat(v)*(v.endsWith('ms')?1:1000);}
  function shown(el){return !!el&&!el.closest('.step-hide,.gone,.notes')&&getComputedStyle(el).display!=='none'&&getComputedStyle(el).visibility!=='hidden';}
  function animate(el,frames,m='m3',ease='e-out',delay=0,cleanup){
    if(!el||staticMode()||!el.animate){if(cleanup)cleanup();return null;}
    const a=el.animate(frames,{duration:duration(m,el),easing:token('--'+ease,el),delay,fill:'backwards'});
    animations.add(a);
    let done=false;
    const finish=()=>{if(done)return;done=true;animations.delete(a);cleanups.delete(finish);if(cleanup)cleanup();a.cancel();};
    cleanups.add(finish);a.finished.then(finish,finish);return a;
  }
  function cancel(skipTransition=false){
    for(const a of animations)a.cancel();animations.clear();
    for(const fn of [...cleanups])fn();cleanups.clear();
    if(skipTransition&&transition){navigation++;transition.skipTransition();transition=null;}
    all('.ed-particle,.ed-number-reel').forEach(e=>e.remove());
  }
  function move(el,transforms,m='m3',ease='e-out',delay=0){
    if(!shown(el))return;
    // Keep author SVG transforms and rotated stamps instead of resetting them.
    const base=getComputedStyle(el).transform;
    const suffix=base==='none'?'':' '+base;
    // Semantic text stays legible throughout entry; fading a parent also fades
    // its labels below AA contrast. Spatial motion supplies the emphasis.
    animate(el,transforms.map(t=>({transform:t+suffix})),m,ease,delay);
  }
  const selectors={
    cover:'.cx-orbit,.cx-tokens span,.cx-title',agenda:'.rm-col,.rm-node',timeline:'.t-year,.t-mile,svg g[data-step]',
    map:'.tile,svg g[data-step]',mechanism:'.tok,.cand,.card', 'traits-grid':'.trait,.card',meter:'.meter-seg,.meter-use',
    'compare-2':'.card,.cmp,.chip','compare-table':'.cmp>*',hub:'.hrow,.t-seg,.seg',levels:'.lv,.lv-bar',
    'tile-grid':'.sk-card,.tile,.ft','sequence':'.lane,svg g[data-step]','mapping':'.card,.mk',
    'mock-legend':'.mk,.legend li','mock-options':'.mode,.pi,.bx','statement':'.big','build-up':'.pb,.add,.verdict',
    'frame-form':'.tp,.fm-row,.pb','before-after':'.win,.stack,.card','worked-example':'.win,.card,.list li',
    'quiz-ab':'.opt','quiz-sort':'.qrow,.ans','quiz-ox':'.qrow,.ox','check':'.chk,.chk-o',
    'rules-dark':'.num,.body','checklist':'.todo,.tbox','sources':'.src-list li','closing':'.pill,.big',
    'stat-strip':'.stat','quadrant':'.qcell,.qp,.qbub','flashcards':'.fc','ops-report':'.oi',
    'sankey-flow':'.sk','decision-tree':'.dt','kanban-board':'.kb','version-graph':'.vg',
    'event-fanout':'.ef','route-tour':'.rt','waterfall':'.wf','mesh-network':'.ms',
    'heatmap-grid':'.hm','swimlane':'.sl','cycle-ring':'.cy'
  };
  const packTargets={atlas:'.atlas-origin,.atlas-source,.atlas-destination',briefing:'.briefing-row',casebook:'.casebook-narrative,.casebook-exhibit,.casebook-decision',editorial:'.editorial-story,.editorial-margin,.editorial-bottom',field:'.field-row',lab:'.lab-observation,.lab-evidence,.lab-next',seminar:'.seminar-turns span,.seminar-preparation,.seminar-invitation',workbook:'.workbook-read,.workbook-write,.workbook-reflection'};
  const packArch={atlas:'map',briefing:'compare-table',casebook:'before-after',editorial:'build-up',field:'sequence',lab:'mechanism',seminar:'hub',workbook:'frame-form'};
  // Each recipe expresses a different relationship, not a renamed generic rise.
  const recipes={
    cover:{name:'orbit-and-type',frames:i=>['rotate(-12deg) scale(.92)','rotate(2deg) scale(1.02)','rotate(0deg) scale(1)'],m:'m4'},
    agenda:{name:'route-cascade',frames:i=>['translateX(-80px)','translateX(8px)','translateX(0px)']},
    timeline:{name:'line-then-year',frames:i=>['translateY(48px) scale(.96)','translateY(0px) scale(1)'],draw:true},
    map:{name:'radial-grid-boundary',frames:i=>[`translate(${(i%3-1)*48}px,${(Math.floor(i/3)-1)*32}px) scale(.94)`,'translate(0px,0px) scale(1)'],draw:true},
    mechanism:{name:'input-process-output',frames:i=>['translateX(-64px) scale(.96)','translateX(0px) scale(1)'],particles:true},
    'traits-grid':{name:'facet-flip',frames:i=>['perspective(1200px) rotateY(-32deg)','perspective(1200px) rotateY(0deg)']},
    meter:{name:'gauge-settle',frames:i=>['scaleX(.08)','scaleX(1.04)','scaleX(1)'],ease:'e-spring',numbers:true},
    'compare-2':{name:'opposed-faces',frames:i=>[`perspective(1200px) rotateY(${i%2?28:-28}deg) translateX(${i%2?48:-48}px)`,'perspective(1200px) rotateY(0deg) translateX(0px)']},
    'compare-table':{name:'row-scan',frames:i=>['translateX(40px) scaleX(.97)','translateX(0px) scaleX(1)']},
    hub:{name:'center-spoke-ignite',frames:i=>['scale(.92)','scale(1.04)','scale(1)'],draw:true},
    levels:{name:'ladder-rise',frames:i=>[`translateY(${64-i%4*8}px)`,'translateY(0px)']},
    'tile-grid':{name:'grid-wave',frames:i=>[`translateY(${24+(i%3)*16}px) rotateX(12deg)`,'translateY(0px) rotateX(0deg)']},
    sequence:{name:'causal-domino',frames:i=>['perspective(1000px) rotateX(-24deg) translateX(-24px)','perspective(1000px) rotateX(0deg) translateX(0px)'],draw:true},
    mapping:{name:'paired-connection',frames:i=>[`translateX(${i%2?56:-56}px)`,'translateX(0px)'],draw:true},
    'mock-legend':{name:'spotlight-pin',frames:i=>['translateY(-32px) scale(1.16)','translateY(4px) scale(.98)','translateY(0px) scale(1)']},
    'mock-options':{name:'selection-track',frames:i=>['translateX(56px)','translateX(-4px)','translateX(0px)']},
    statement:{name:'kinetic-thesis',frames:i=>['scale(.96) translateY(32px)','scale(1) translateY(0px)'],kinetic:true},
    'build-up':{name:'accumulating-pieces',frames:i=>['translateY(24px) scale(.92)','translateY(-4px) scale(1.02)','translateY(0px) scale(1)']},
    'frame-form':{name:'outline-then-fill',frames:i=>['scaleX(.92) translateX(-16px)','scaleX(1) translateX(0px)'],draw:true},
    'before-after':{name:'paired-wipe',frames:i=>[`translateX(${i%2?96:-96}px) scaleX(.92)`,'translateX(0px) scaleX(1)']},
    'worked-example':{name:'scene-replay',frames:i=>['translateY(40px) scale(.97)','translateY(0px) scale(1)'],draw:true},
    'quiz-ab':{name:'choice-verdict',frames:i=>[`translateX(${i%2?40:-40}px) rotate(${i%2?2:-2}deg)`,'translateX(0px) rotate(0deg)']},
    'quiz-sort':{name:'classification-lanes',frames:i=>[`translateX(${i%2?64:-64}px) scale(.96)`,'translateX(0px) scale(1)']},
    'quiz-ox':{name:'judgment-stamp',frames:i=>['scale(1.18) rotate(-8deg)','scale(.98) rotate(1deg)','scale(1) rotate(0deg)']},
    check:{name:'feedback-beacon',frames:i=>['scale(.97)','scale(1.015)','scale(1)']},
    'rules-dark':{name:'spotlight-focus',frames:i=>['scale(.96) translateY(16px)','scale(1) translateY(0px)']},
    checklist:{name:'commitment-stamps',frames:i=>['translateY(-24px) rotate(-4deg) scale(1.04)','translateY(0px) rotate(0deg) scale(1)']},
    sources:{name:'evidence-align',frames:i=>[`translateX(${i%2?40:-40}px) rotate(${i%2?1:-1}deg)`,'translateX(0px) rotate(0deg)']},
    closing:{name:'summary-convergence',frames:i=>[`translate(${(i-1)*72}px,32px) scale(.94)`,'translate(0px,0px) scale(1)']},
    // P1-1: numbers() 재사용 등록 — 지표 카드가 한 덩어리로 등장하며 숫자 릴이 카운트업한다(transform 만, m4).
    'stat-strip':{name:'metric-rally',frames:i=>['translateY(44px)','translateY(0px)'],m:'m4',numbers:6},
    // TASK-tools G3: SVG 차트 조각은 기존 시그니처 이름만 재사용한다(신규 시그니처 없음).
    // 막대는 지표와 같은 metric-rally 상승, 선 그래프는 타일 파형(grid-wave)으로 계열이 모인다.
    'chart-bar':{name:'metric-rally',frames:i=>['translateY(44px)','translateY(0px)'],m:'m4'},
    'chart-line':{name:'grid-wave',frames:i=>[`translateY(${24+(i%3)*16}px) rotateX(12deg)`,'translateY(0px) rotateX(0deg)']},
    // 탐색 위젯·사이드 시트도 기존 이름만 재사용한다 — 위젯 조작 자체는 시그니처가 아니라 클릭 핸들러다.
    'explore':{name:'grid-wave',frames:i=>[`translateY(${24+(i%3)*16}px) rotateX(12deg)`,'translateY(0px) rotateX(0deg)']},
    'detail-sheet':{name:'accumulating-pieces',frames:i=>['translateY(24px) scale(.92)','translateY(-4px) scale(1.02)','translateY(0px) scale(1)']},
    // 파트 구분지는 agenda 경로 위의 정류장 — route-cascade 재사용(chart-bar/chart-line 의
    // 이름 공유 선례와 같은 이유로 신규 실행 이름을 만들지 않는다).
    'part-divider':{name:'route-cascade',frames:i=>['translateX(-80px)','translateX(8px)','translateX(0px)']},
    // 2×2 사분면은 타일 파형(grid-wave)으로 네 영역·좌표 칩이 모인다, 플래시카드는 카드 회전
    // 등장(facet-flip — traits-grid 와 같은 이름). 둘 다 기존 실행 이름 재사용.
    'quadrant':{name:'grid-wave',frames:i=>[`translateY(${24+(i%3)*16}px) rotateX(12deg)`,'translateY(0px) rotateX(0deg)']},
    'flashcards':{name:'facet-flip',frames:i=>['perspective(1200px) rotateY(-32deg)','perspective(1200px) rotateY(0deg)']},
    // TASK-ops-report: 지표 덩어리(.oi)는 증거 띠·막대와 같은 metric-rally 상승 — 신규 이름 없이 재사용.
    'ops-report':{name:'metric-rally',frames:i=>['translateY(44px)','translateY(0px)'],m:'m4'},
    // TASK-workflow-series: 워크플로 도식 11계열 — 실행 이름 신규 11종(31→42). 각 이름이 다른
    // 관계를 표현한다 — 이름만 다른 일반 상승 복사가 아니라 조각의 .마커 대상에 개별 움직임.
    // 샌키: 유입 밴드가 왼쪽에서 밀려와 합류·분출 — 수평 수렴(dash-flow 안내길 입자 포함).
    'sankey-flow':{name:'stream-converge',frames:i=>['translateX(-64px) scaleX(.92)','translateX(0px) scaleX(1)'],draw:true},
    // 판단트리: 마름모가 점등되며 가지선이 그려지고 끝 판정이 도장처럼 자리 잡는다.
    'decision-tree':{name:'branch-verdict',frames:i=>['translateY(-24px) scale(.94)','translateY(0px) scale(1.02)','scale(1)'],draw:true},
    // 칸반: 카드가 칸 사이를 오른쪽으로 미끄러지듯 드리프트 — 느린 이행 m2.
    'kanban-board':{name:'card-drift',frames:i=>['translateX(56px)','translateX(-4px)','translateX(0px)'],m:'m2'},
    // 버전그래프: 줄기·갈래 선이 그려지고(draw) 커밋·병합 도장이 찍힌다.
    'version-graph':{name:'merge-trace',frames:i=>['scale(.8)','scale(1.06)','scale(1)'],draw:true},
    // 팬아웃: 중심 사건이 자리 잡고 외곽 노드가 동시에 켜진다 — 스태거 축소로 동시성 유지.
    'event-fanout':{name:'pulse-fanout',frames:i=>['scale(.7)','scale(1.08)','scale(1)'],draw:true,particles:true},
    // 경로순회: 순회선이 그려지고 정거장 번호가 차례로 찍힌다.
    'route-tour':{name:'waypoint-crawl',frames:i=>['translateY(24px) scale(.9)','translateY(0px) scale(1)'],draw:true},
    // 폭포수: 증감 막대가 위에서 매달리듯 내려와 누적 높이에 자리 잡고 합계가 카운트된다.
    'waterfall':{name:'cascade-ledge',frames:i=>['translateY(-32px)','translateY(0px)'],numbers:true},
    // 메시: 연결선이 그려지고 노드가 홉 단계로 자리 잡는다.
    'mesh-network':{name:'hop-relay',frames:i=>['scale(.88)','scale(1.04)','scale(1)'],draw:true},
    // 히트맵: 칸이 행·열 순서로 플레어(작게→크게→제자리) — 면적이 곧 강도.
    'heatmap-grid':{name:'grid-flare',frames:i=>['scale(.5)','scale(1.12)','scale(1)']},
    // 스윔레인: 카드가 띠 위에 올라가고 인계 화살표가 다음 띠로 넘어간다.
    'swimlane':{name:'lane-slide',frames:i=>['translateY(28px)','translateY(-3px)','translateY(0px)'],draw:true},
    // 순환링: 조각이 회전하듯 제자리로 돌아와 시계 방향 한 바퀴가 완성된다.
    'cycle-ring':{name:'ring-circuit',frames:i=>['rotate(-14deg) scale(.94)','rotate(2deg) scale(1.01)','rotate(0deg) scale(1)'],draw:true}
  };
  // Wipe a prior result in-place: the mask and its content counter-translate,
  // so the old words remain stationary as the new result is uncovered. Neither
  // source content nor presentation-owned step visibility is changed.
  function compareWipe(before,after){
    const host=after.closest('.win')||after;
    const h=host.getBoundingClientRect(),r=after.getBoundingClientRect();
    const scale=h.width/host.offsetWidth,position=host.style.position;
    if(getComputedStyle(host).position==='static')host.style.position='relative';
    const frame=document.createElement('div');frame.className='ed-wipe-frame';frame.setAttribute('aria-hidden','true');
    Object.assign(frame.style,{left:(r.left-h.left)/scale-host.clientLeft+'px',top:(r.top-h.top)/scale-host.clientTop+'px',width:r.width/scale+'px',height:r.height/scale+'px'});
    const mask=document.createElement('div');mask.className='ed-wipe';
    const copy=before.cloneNode(true);copy.classList.add('ed-wipe-before');
    [copy,...all('*',copy)].forEach(e=>{e.removeAttribute('id');for(const a of ['data-step','data-add','data-until','data-only','data-lit'])e.removeAttribute(a);});
    all('.ed-scene-cue,.ed-wipe',copy).forEach(e=>e.remove());
    mask.append(copy);frame.append(mask);host.append(frame);
    animate(copy,[{transform:'translateX(0%)'},{transform:'translateX(100%)'}],'m4','e-inout');
    animate(mask,[{transform:'translateX(0%)'},{transform:'translateX(-100%)'}],'m4','e-inout',0,()=>{frame.remove();host.style.position=position;});
  }
  // A scene is replayed where the work happens: message -> response rows,
  // document lines, form value, highlighted cell or messenger reply. Covers
  // uncover existing ink; the window and explanatory card never fly around.
  function sceneReplay(root,step){
    const scene=root.closest('.win,.stack')||root;
    let leaves=all('.u,.at>p,.at tr,.at>.filechip,.doc>p,.doc-meta,.doc-sign,.xl tr,.xl-formula,.fm-row,.fm-check,.fm-btns,.mail-h,.mail-b>p,.mail-b>.filechip,.mg,.sb,.list li,.wk',root);
    if(root.matches('.a'))leaves=all('.at>p,.at tr,.at>.filechip',root);
    if(!leaves.length)leaves=[root];
    leaves=leaves.filter(e=>shown(e)&&!e.closest('.ed-wipe')&&!all('[data-add],[data-step]',e).some(n=>!shown(n)));
    leaves=leaves.filter(e=>!leaves.some(p=>p!==e&&p.contains(e)));
    leaves.forEach((e,i)=>{
      const host=e.closest('.win,.stack,.card')||scene;
      const h=host.getBoundingClientRect(),r=e.getBoundingClientRect(),scale=h.width/host.offsetWidth;
      if(!r.width||!r.height||!scale)return;
      const position=host.style.position;
      if(getComputedStyle(host).position==='static')host.style.position='relative';
      let bg=e;while(bg!==host&&getComputedStyle(bg).backgroundColor==='rgba(0, 0, 0, 0)')bg=bg.parentElement;
      const cue=document.createElement('span');cue.className='ed-scene-cue';cue.setAttribute('aria-hidden','true');cue.dataset.ownerStep=String(step);
      Object.assign(cue.style,{left:(r.left-h.left)/scale+'px',top:(r.top-h.top)/scale+'px',width:r.width/scale+'px',height:r.height/scale+'px'});
      cue.style.setProperty('--ed-cue-bg',getComputedStyle(bg).backgroundColor);
      host.append(cue);
      animate(cue,[{transform:'scaleX(1)'},{transform:'scaleX(0)'}],'m3','e-inout',Math.min(i,6)*duration('m1',host)/4,()=>{cue.remove();if(!host.querySelector('.ed-scene-cue'))host.style.position=position;});
    });
  }
  // Record one actual firing. slide index comes from the engine's deckInfo when
  // present (it owns the logical numbering); DOM order is only a fallback.
  function logSig(s,step,sig){
    let slide=-1;
    if(window.deckInfo){const info=window.deckInfo();if(info&&typeof info.slide==='number')slide=info.slide;}
    if(slide<0)slide=all('.slide',stage).indexOf(s);
    sigLog.push(Object.freeze({slide:slide,step:step,sig:sig}));
    if(sigLog.length>500)sigLog.shift();
    // deckslide is engine-owned (detail is the bare slide index), so the sig is
    // published on a follow-up event instead of mutating the engine's detail.
    document.dispatchEvent(new CustomEvent('edumotion',{detail:{slide:slide,step:step,sig:sig}}));
  }
  function semanticScene(s,arch,step,entry){
    // Only exact current-step owners, never their already-visible ancestors.
    let roots=all('[data-step],[data-add],[data-only],[data-lit]',s).filter(e=>shown(e)&&['step','add','only','lit'].some(k=>e.dataset[k]!==undefined&&+e.dataset[k]===step));
    if(entry&&step===0)roots=all('.u,.a,.casebook-narrative',s).filter(shown);
    roots=roots.filter(e=>!roots.some(p=>p!==e&&p.contains(e)));
    for(const root of roots){
      const after=root.matches('.a')?root.querySelector('.at'):root.matches('.stack')?root:null;
      if(arch==='before-after'&&after){
        const peers=all(after.matches('.stack')?'.stack':'.at',s).filter(e=>shown(e)&&!e.closest('.ed-wipe'));
        const index=peers.indexOf(after),before=peers[index-1];
        if(before){compareWipe(before,after);continue;}
      }
      sceneReplay(root,step);
    }
  }
  // Line drawing. On slide entry every visible line draws once. On a later step only
  // lines owned by the elements revealed at that step draw; lines already on screen
  // stay still (redrawing them reads as the whole diagram restarting).
  // Each line runs from its path start to its end; the arrowhead (marker-end) is held
  // back until the line arrives, so the arrow visibly travels start → end.
  function draw(s,newly){
    let paths=all('svg:not(.ico):not(.ed-mark) path,svg:not(.ico) line,.ed-diagram path',s).filter(shown);
    if(newly)paths=paths.filter(p=>newly.some(n=>n===p||n.contains(p)));
    paths.slice(0,12).forEach((p,i)=>{
      if(!p.getTotalLength||getComputedStyle(p).stroke==='none')return;
      const len=p.getTotalLength();if(!len)return;
      const dash=p.style.strokeDasharray,offset=p.style.strokeDashoffset,marker=p.getAttribute('marker-end');
      p.style.strokeDasharray=String(len);
      const delay=Math.min(i,4)*duration('m1',s)/4;
      const a=animate(p,[{strokeDashoffset:len},{strokeDashoffset:0}],'m3','e-inout',delay,()=>{p.style.strokeDasharray=dash;p.style.strokeDashoffset=offset;if(marker)p.setAttribute('marker-end',marker);});
      if(a&&marker)p.removeAttribute('marker-end');
    });
  }
  function kinetic(title){
    if(!title||title.dataset.edKinetic)return;
    title.dataset.edKinetic='1';
    const walk=document.createTreeWalker(title,NodeFilter.SHOW_TEXT);let node,nodes=[];
    while((node=walk.nextNode()))if(node.textContent.trim()&&!node.parentElement.closest('[data-fx]'))nodes.push(node);
    for(const text of nodes){
      const frag=document.createDocumentFragment();
      for(const ch of Array.from(text.textContent)){if(/\s/.test(ch)){frag.append(document.createTextNode(ch));continue;}
        const span=document.createElement('span');span.className='ed-letter';span.textContent=ch;frag.append(span);}
      text.replaceWith(frag);
    }
  }
  function titleImpact(s,arch){
    const t=s.querySelector('.cx-title,.big,.title,.pack-prompt');if(!t)return;
    if(arch==='cover'||arch==='statement'){
      kinetic(t);all('.ed-letter',t).filter(e=>!e.closest('[data-fx]')).slice(0,48).forEach((e,i)=>{
        move(e,['translateY(32px) scale(.92)','translateY(0px) scale(1)'],'m3','e-spring',Math.min(i,16)*duration('m1',s)/8);
        animate(e,[{filter:'blur(6px)'},{filter:'blur(0px)'}],'m2','e-out',Math.min(i,16)*duration('m1',s)/8);
      });
    }else move(t,['translateY(24px)','translateY(0px)'],'m3');
  }
  // Flow dots run only along lines that are new at this step (entry: all visible lines).
  function particles(s,newly){
    let paths=all('.dash-flow, .ed-pipe, .atlas-route path',s).filter(shown);
    if(newly)paths=paths.filter(p=>newly.some(n=>n===p||n.contains(p)));
    paths=paths.slice(0,3);
    for(const p of paths){if(!p.getPointAtLength)continue;const svg=p.ownerSVGElement,len=p.getTotalLength();
      const dot=document.createElementNS('http://www.w3.org/2000/svg','circle');dot.setAttribute('r','5');dot.setAttribute('fill','var(--accent)');dot.setAttribute('aria-hidden','true');dot.classList.add('ed-particle');p.parentElement.append(dot);
      const frames=Array.from({length:9},(_,i)=>{const pt=p.getPointAtLength(len*i/8);return{transform:`translate(${pt.x}px,${pt.y}px)`,opacity:i===0||i===8?0:1};});
      animate(dot,frames,'m4','e-inout',0,()=>dot.remove());
    }
  }
  function numbers(s,limit){
    all('[data-count],.meter-use>span,.num',s).filter(shown).slice(0,limit||3).forEach(e=>{
      const text=e.textContent.trim();if(!/^\d+(?:[.,]\d+)?%?$/.test(text))return;
      // A decorative number reel counts without mutating the source text or live regions.
      const box=document.createElement('span');box.className='ed-number-reel';box.setAttribute('aria-hidden','true');
      const n=Number(text.replace(/[^\d.]/g,''));const suffix=text.endsWith('%')?'%':'';
      const track=document.createElement('span');track.className='ed-number-track';box.append(track);
      for(let i=0;i<5;i++){const v=document.createElement('span');v.textContent=String(Math.round(n*i/4))+suffix;track.append(v);}
      const old=e.style.position;e.style.position='relative';e.append(box);
      animate(track,[{transform:'translateY(0)'},{transform:'translateY(-80%)'}],'m4','e-out',0,()=>{box.remove();e.style.position=old;});
    });
  }
  // Crayon grading marks — grain particles, pressure profile and hand-speed easing
  // ported from the approved demo dev/crayon-reference.html. One canvas lives inside
  // the .ed-mark wrapper and each stroke is painted progressively along its path.
  const rand=(a,b)=>Math.random()*(b-a)+a;
  const MARK_MS={circle:750,check:560,underline:600,highlight:900};
  function crayonPalette(css){
    const m=css.match(/[\d.]+/g);
    if(!m)return{h:[352,6],s:[78,96],l:[38,56]};
    const r=+m[0]/255,g=+m[1]/255,b=+m[2]/255,mx=Math.max(r,g,b),mn=Math.min(r,g,b),d=mx-mn,l=(mx+mn)/2;
    let h=0,s=0;
    if(d){s=l>.5?d/(2-mx-mn):d/(mx+mn);h=mx===r?((g-b)/d+(g<b?6:0)):mx===g?(b-r)/d+2:(r-g)/d+4;h*=60;}
    const S=s*100,L=l*100;
    return{h:[Math.max(0,h-5),h+6],s:[Math.max(20,S-8),Math.min(100,S+18)],l:[Math.max(18,L-7),Math.min(72,L+15)]};
  }
  function cubic(t,p0,p1,p2,p3){const u=1-t,v=u*u,w=v*u,x=t*t,y=x*t;
    return{x:w*p0.x+3*v*t*p1.x+3*u*x*p2.x+y*p3.x,y:w*p0.y+3*v*t*p1.y+3*u*x*p2.y+y*p3.y};}
  function bezier(segs,steps){const out=[];for(const s of segs)for(let i=0;i<=steps;i++)out.push(cubic(i/steps,...s));return out;}
  // Human hand velocity: distance covered per unit time is never linear.
  function hand(t,kind){
    if(kind==='circle')return t<.25?2.2*t*t+.3*t:1-Math.pow(1-t,2.3)*.85;
    if(kind==='fast-snap')return 1-Math.pow(1-t,2.8);
    if(kind==='down-tick')return Math.pow(t,1.4);
    return t<.5?2*t*t:1-Math.pow(-2*t+2,2)/2;
  }
  // Dense interpolated points along the raw path; spacing is capped so a few
  // marks per slide stay cheap even around large cards.
  function dense(raw,cap=2200){
    let len=0;for(let i=0;i<raw.length-1;i++)len+=Math.hypot(raw[i+1].x-raw[i].x,raw[i+1].y-raw[i].y);
    const gap=Math.max(.9,len/cap),pts=[];
    for(let i=0;i<raw.length-1;i++){
      const p0=raw[i],p1=raw[i+1],d=Math.hypot(p1.x-p0.x,p1.y-p0.y),steps=Math.max(Math.round(d/gap),1),ang=Math.atan2(p1.y-p0.y,p1.x-p0.x);
      for(let s=0;s<steps;s++){const t=s/steps;pts.push({x:p0.x+(p1.x-p0.x)*t,y:p0.y+(p1.y-p0.y)*t,angle:ang});}
    }
    if(raw.length>1){const a=raw[raw.length-2],b=raw[raw.length-1];pts.push({x:b.x,y:b.y,angle:Math.atan2(b.y-a.y,b.x-a.x)});}
    return pts;
  }
  function grains(ctx,pts,a,b,o){
    const total=pts.length;
    for(let i=a;i<b&&i<total;i++){
      const pt=pts[i],prog=i/total;let pressure=1;
      if(o.pressure==='grading-circle'){
        if(prog<.06)pressure=.75+prog/.06*.25;
        else if(prog>.88){const t=(prog-.88)/.12;pressure=Math.max(.32,1-t*.68);}
        else pressure=.9+.2*Math.sin(prog*Math.PI*3.5);
      }else if(o.pressure==='taper'){
        if(prog<.15)pressure=.75+prog/.15*.35;else if(prog>.62)pressure=Math.max(.08,1-(prog-.62)/.38*.92);else pressure=1.05;
      }else if(o.pressure==='underline'){
        const e=Math.sin(prog*Math.PI);pressure=Math.pow(e,.3)*(.8+.3*Math.sin(prog*Math.PI*3));
      }else if(o.pressure==='highlight')pressure=.85+.2*Math.sin(prog*Math.PI*3);
      const w=o.w*(.72+.35*pressure),n=Math.floor(w*(1.8+pressure*1.5));
      const hr=o.palette.h,hue=hr[0]>hr[1]?(hr[0]+rand(0,360-hr[0]+hr[1]))%360:rand(hr[0],hr[1]);
      const sat=rand(o.palette.s[0],o.palette.s[1]);
      const light=Math.max(24,Math.min(72,rand(o.palette.l[0],o.palette.l[1])-(pressure-.75)*16));
      for(let g=0;g<n;g++){
        const spread=(Math.random()+Math.random()-1)*(w/2),along=rand(-1.5,1.5);
        const gx=pt.x+Math.cos(pt.angle+Math.PI/2)*spread+Math.cos(pt.angle)*along;
        const gy=pt.y+Math.sin(pt.angle+Math.PI/2)*spread+Math.sin(pt.angle)*along;
        const tooth=Math.sin(gx*.85)*Math.cos(gy*.85)+Math.sin((gx-gy)*.45);
        if(tooth>pressure*.92)continue;
        const ratio=Math.abs(spread)/(w/2);
        let alpha=(1-ratio*.7)*rand(.22,.55)*pressure;
        const clump=Math.random()<o.clump*.08*pressure;
        const gl=clump?light-11:light+rand(-5,5);
        if(clump)alpha=Math.min(.95,alpha*2.1);
        ctx.fillStyle=`hsla(${hue},${sat}%,${gl}%,${alpha})`;
        ctx.beginPath();
        ctx.ellipse(gx,gy,clump?rand(1.4,2.6):rand(.7,1.8),clump?rand(1,2):rand(.45,1.15),pt.angle+rand(-.35,.35),0,Math.PI*2);
        ctx.fill();
      }
    }
  }
  function gradingCircle(w,h){
    const jx=()=>rand(-w*.025,w*.025),jy=()=>rand(-h*.025,h*.025);
    const P=[[w*.76,h*.57],[w*.45,h*.73],[w*.12,h*.73],[w*.14,h*.47],[w*.16,h*.17],[w*.56,h*.07],[w*.82,h*.2],[w*.97,h*.34],[w*.87,h*.65],[w*.47,h*.91]].map(([x,y])=>({x:x+jx(),y:y+jy()}));
    return bezier([[P[0],P[1],P[2],P[3]],[P[3],P[4],P[5],P[6]],[P[6],P[7],P[8],P[9]]],65);
  }
  function mark(el,type='circle'){
    if(!shown(el)||el.closest('[data-crayon="off"]')||el._edMark)return;
    const box=el.getBoundingClientRect(),ew=el.offsetWidth||box.width,eh=el.offsetHeight||box.height;if(!ew||!eh)return;
    const wrap=document.createElement('span');wrap.className='ed-mark';wrap.setAttribute('aria-hidden','true');
    const color=el.dataset.crayonColor||(type==='check'?'blue':type==='highlight'?'yellow':'red');
    wrap.style.color='var(--'+({red:'danger',blue:'blue',yellow:'accent'}[color]||'danger')+')';
    const position=el.style.position;if(getComputedStyle(el).position==='static')el.style.position='relative';
    el.append(wrap);
    // Layout px drive drawing; the stage transform only magnifies the raster.
    const scale=box.width/ew||1,dpr=Math.min(3,(window.devicePixelRatio||1)*Math.max(1,scale));
    const padX=type==='circle'?Math.min(40,Math.max(10,ew*.06)):Math.min(24,Math.max(8,ew*.05));
    const padY=type==='circle'?Math.min(36,Math.max(14,eh*.3)):type==='highlight'?Math.min(10,Math.max(4,eh*.12)):Math.min(18,Math.max(8,eh*.18));
    const W=ew+padX*2,H=eh+padY*2;
    const canvas=document.createElement('canvas');
    canvas.width=Math.round(W*dpr);canvas.height=Math.round(H*dpr);
    Object.assign(canvas.style,{left:4-padX+'px',top:4-padY+'px',width:W+'px',height:H+'px'});
    wrap.append(canvas);
    const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
    const k=Math.min(1.5,Math.max(.7,Math.min(W,H)/110)),palette=crayonPalette(getComputedStyle(wrap).color);
    // Each stroke: dense path, grain options, share of the type duration, hand timing, pause after.
    const strokes=[];
    if(type==='check'){
      const sx=padX+rand(4,10),sy=padY+H*rand(.28,.38),mx=padX+W*rand(.25,.34),my=padY+H*rand(.52,.62),ex=W-padX+rand(2,12),ey=padY-rand(0,8);
      strokes.push({pts:dense([{x:sx,y:sy},{x:mx,y:my}]),o:{palette,w:9.5*k,pressure:'underline',clump:.28},dur:.32,timing:'down-tick',pause:35});
      strokes.push({pts:dense([{x:mx-1,y:my+1},{x:(mx+ex)*.48,y:(my+ey)*.52-rand(2,6)},{x:ex,y:ey}]),o:{palette,w:10*k,pressure:'taper',clump:.25},dur:.68,timing:'fast-snap'});
    }else if(type==='underline'){
      const y=H-padY-2;
      strokes.push({pts:dense([{x:padX-rand(2,6),y:y+rand(-2,3)},{x:W*.35,y:y+rand(-3,2)},{x:W*.7,y:y+rand(-2,3)},{x:W-padX+rand(2,8),y:y+rand(-4,2)}]),o:{palette,w:8*k,pressure:'underline',clump:.25},dur:1,timing:'normal'});
    }else if(type==='highlight'){
      const y=H/2+2,hw=Math.min(30,Math.max(14,eh*.55));
      strokes.push({pts:dense([{x:padX-rand(3,8),y:y-2.5+rand(-1.5,1.5)},{x:W*.5,y:y-2.5+rand(-2,2)},{x:W-padX+rand(3,8),y:y-2.5+rand(-2,2)}]),o:{palette,w:hw,pressure:'highlight',clump:.12},dur:.52,timing:'normal',pause:50});
      strokes.push({pts:dense([{x:padX-rand(2,6),y:y+2.5+rand(-1.5,1.5)},{x:W*.5,y:y+2.5+rand(-2,2)},{x:W-padX+rand(3,8),y:y+2.5+rand(-2,2)}]),o:{palette,w:hw,pressure:'highlight',clump:.12},dur:.48,timing:'normal'});
    }else{
      strokes.push({pts:dense(gradingCircle(W,H)),o:{palette,w:9.5*k,pressure:'grading-circle',clump:.26},dur:1,timing:'circle'});
    }
    const state={node:wrap,position,dead:false,raf:0,sum:strokes.reduce((a,s)=>a+s.pts.length,0)};
    canvas._edProgress=0;el._edMark=state;
    if(staticMode()||still){
      for(const s of strokes)grains(ctx,s.pts,0,s.pts.length,s.o);
      canvas._edProgress=1;return;
    }
    const total=MARK_MS[type]||750;let done=0;
    const draw=(s,from,to)=>{grains(ctx,s.pts,from,to,s.o);canvas._edProgress=(done+to)/state.sum;};
    (async()=>{
      for(const s of strokes){
        await new Promise(res=>{
          const n=s.pts.length,ms=total*s.dur;let i=0,t0=null;
          const tick=ts=>{
            if(state.dead||!wrap.isConnected){res();return;}
            if(staticMode()){draw(s,i,n);res();return;}
            if(t0===null)t0=ts;
            const p=Math.min((ts-t0)/ms,1),tgt=Math.floor(hand(p,s.timing)*n);
            if(tgt>i){draw(s,i,tgt);i=tgt;}
            if(p<1)state.raf=requestAnimationFrame(tick);
            else{if(i<n)draw(s,i,n);res();}
          };
          state.raf=requestAnimationFrame(tick);
        });
        if(state.dead)return;
        done+=s.pts.length;
        if(s.pause)await new Promise(r=>setTimeout(r,s.pause));
      }
      canvas._edProgress=1;
    })();
  }
  function unmark(el){if(!el||!el._edMark)return;const m=el._edMark;m.dead=true;if(m.raf)cancelAnimationFrame(m.raf);m.node.remove();el.style.position=m.position;delete el._edMark;}
  function marks(s){
    all('[data-crayon]',s).filter(e=>/^(circle|check|underline|highlight)$/.test(e.dataset.crayon)).slice(0,2).forEach(e=>mark(e,e.dataset.crayon));
    all('.opt.right.lit,.chk-right',s).forEach(e=>mark(e));
  }
  function verdict(el,ok){
    mark(el);const c=el&&el.closest('.chk');if(!c||staticMode())return;
    // Grading reveals the .chk-why/.chk-fb block outside the step contract, so
    // due data-fx inside it (e.g. rack-focus on the explanation) fire here.
    all('[data-fx]',c).filter(e=>!e._edFx&&shown(e)&&e.getClientRects().length).forEach(fxFire);
    if(!ok){const picked=c.querySelector('.chk-picked');move(picked,['translateX(0px)','translateX(-12px)','translateX(10px)','translateX(-6px)','translateX(0px)'],'m2');return;}
    // Eight short rays, once; no flashing or confetti obscuring the explanation.
    for(let i=0;i<8;i++){const ray=document.createElement('i');ray.className='ed-particle ed-ray';ray.setAttribute('aria-hidden','true');c.append(ray);
      const angle=i*Math.PI/4;animate(ray,[{transform:'translate(0px,0px) scale(.8)',opacity:1},{transform:`translate(${Math.cos(angle)*64}px,${Math.sin(angle)*48}px) scale(1)`,opacity:0}],'m3','e-out',0,()=>ray.remove());}
  }
  function adapt(s){
    if(!s.dataset.archetype)s.dataset.archetype=s.querySelector('.chk')?'check':packArch[s.dataset.design]||'statement';
    const arch=s.dataset.archetype;if(recipes[arch])s.dataset.motionSignature=recipes[arch].name;
    return arch;
  }
  // P1-1 숫자 증거 띠: 조각 31의 .stat-strip 은 표지·목차·마무리 장 안에 붙여 넣는다. host 아키타입의
  // 안무와 함께 띠 레시피(stat-strip=metric-rally)가 발화하며 두 이름 모두 기록에 남는다.
  // 등장 시에만 재생하고 숫자 릴은 numbers() 를 그대로 쓴다(정적 완결=최종 값).
  function rally(s,entry){
    const r=recipes['stat-strip'];
    const stats=all('.stat-strip .stat',s).filter(shown);
    if(!entry||!stats.length)return false;
    const before=animations.size;
    stats.slice(0,6).forEach((e,i)=>move(e,r.frames(i),r.m||'m4','e-out',Math.min(i,6)*duration('m1',s)/4));
    all('.stat-strip',s).forEach(st=>numbers(st,6));
    return animations.size>before;
  }
  // ---- Author-declared effects: data-fx="<name>" + optional data-fx-at="<ms 0..2000>" ----
  // One finite, cancellable effect per element; it fires once when the element
  // becomes visible (slide entry when visible at step 0, or at the step whose
  // data-step/data-add/data-only reveals it). Static modes and revisited
  // (back) states show the authored final DOM — overlays stay, text is intact.
  const FX={strike:'m3',stamp:'m3',mark:'m4',count:'m4',travel:'m4',block:'m4',type:1500,press:'m2','scatter-gather':'m4','slice-reveal':'m4','row-mask-rise':'m3','weight-wave':'m3','rack-focus':'m3','bar-grow':'m3','card-deal':'m3',blinds:'m4'};
  // A declared transform-reveal technique owns the element's own entrance: the
  // archetype signature must not stack a second transform animation on it.
  const FX_OWN_TRANSFORM=new Set(['bar-grow','card-deal']);
  function animateMs(el,frames,ms,ease='e-out',delay=0,cleanup){
    if(!el||staticMode()||!el.animate){if(cleanup)cleanup();return null;}
    const a=el.animate(frames,{duration:ms,easing:token('--'+ease,el),delay,fill:'backwards'});
    animations.add(a);
    let done=false;
    const finish=()=>{if(done)return;done=true;animations.delete(a);cleanups.delete(finish);if(cleanup)cleanup();a.cancel();};
    cleanups.add(finish);a.finished.then(finish,finish);return a;
  }
  function revealStep(el,s){
    let r=0;
    for(let x=el;x&&x!==s;x=x.parentElement)
      for(const a of ['step','add','only'])
        if(x.dataset[a]!==undefined)r=Math.max(r,+x.dataset[a]);
    return r;
  }
  function fxOverlay(el,cls){
    // The overlay IS the final state: it persists after drawing and in print.
    if(getComputedStyle(el).position==='static')el.style.position='relative';
    let i=el.querySelector(':scope>.'+cls);
    if(!i){i=document.createElement('i');i.className=cls;i.setAttribute('aria-hidden','true');el.append(i);}
    return i;
  }
  function fxFinal(el){
    const name=el.dataset.fx;
    if(name==='strike')fxOverlay(el,'ed-fx-strike');
    else if(name==='mark')fxOverlay(el,'ed-fx-mark');
    // Other kinds leave no overlay: the authored DOM is already final.
  }
  function fxCount(el,at){
    const orig=el.textContent;
    const m=orig.match(/^\s*([+-]?[\d,]+(?:\.\d+)?)\s*(%?)\s*$/);
    if(!m)return;
    const to=parseFloat(m[1].replace(/,/g,''));
    if(!isFinite(to))return;
    const from=parseFloat(el.dataset.from)||0;
    const dec=(m[1].split('.')[1]||'').length,comma=m[1].includes(','),suf=m[2];
    const dur=duration(FX.count,el);
    const fmt=v=>{const neg=v<0,s=Math.abs(v).toFixed(dec);let[i,f]=s.split('.');if(comma)i=i.replace(/\B(?=(\d{3})+(?!\d))/g,',');return(neg?'-':'')+i+(f?'.'+f:'')+suf;};
    let raf=0,dead=false;
    // The authored text is authoritative: any interruption restores it exactly.
    const stop=()=>{if(dead)return;dead=true;if(raf)cancelAnimationFrame(raf);el.textContent=orig;cleanups.delete(stop);};
    cleanups.add(stop);
    const t0=performance.now()+at;
    const tick=now=>{if(dead)return;
      if(staticMode()){stop();return;}
      const x=Math.min(1,Math.max(0,(now-t0)/dur));
      el.textContent=fmt(from+(to-from)*(1-Math.pow(1-x,3)));
      if(x<1)raf=requestAnimationFrame(tick);else stop();};
    raf=requestAnimationFrame(tick);
  }
  function fxType(el,at){
    if(el.children.length)return;               // text-only targets
    const orig=el.textContent;
    const chars=Array.from(orig),len=chars.length||1;
    const rate=Math.min(parseFloat(el.dataset.fxSpeed)||24,1500/len);
    const hadLabel=el.hasAttribute('aria-label'),oldLabel=el.getAttribute('aria-label');
    el.setAttribute('aria-label',orig);         // AT/search keep the full text
    el.textContent='';
    chars.forEach(ch=>{const s=document.createElement('span');s.className='ed-fx-ch';s.setAttribute('aria-hidden','true');s.textContent=ch;el.append(s);});
    const restore=()=>{el.textContent=orig;if(hadLabel)el.setAttribute('aria-label',oldLabel);else el.removeAttribute('aria-label');};
    const spans=all('.ed-fx-ch',el);
    spans.forEach((s,k)=>animateMs(s,[{visibility:'hidden'},{visibility:'visible'}],1,'e-out',at+k*rate,k===len-1?restore:null));
  }
  // ---- TASK-motions + TASK-fx-absorb: shared technique vocabulary (8 kinds) ----
  // Each one is a finite, cancellable opt-in effect; static modes keep the
  // authored final DOM untouched. Letter splits match kinetic() exactly —
  // .ed-letter spans for glyphs, plain text nodes for spaces — so the settled
  // DOM is byte-identical to a slide the technique never visited (print diff 0).
  function fxLetters(el){
    if(el.children.length)return null;
    const orig=el.textContent;if(!orig.trim())return null;
    el.textContent='';
    const spans=[];
    for(const ch of Array.from(orig)){
      if(/\s/.test(ch)){el.append(document.createTextNode(ch));continue;}
      const s=document.createElement('span');s.className='ed-letter';s.textContent=ch;el.append(s);spans.push(s);
    }
    return spans.length?spans:null;
  }
  // scatter-gather: title letters converge from scattered positions into place.
  // Deterministic offsets (index-hash) — the assemble is a hero moment, once.
  function fxScatter(el,at){
    const spans=fxLetters(el);if(!spans)return;
    const ms=duration(FX['scatter-gather'],el);
    spans.slice(0,48).forEach((s,k)=>{
      const dx=((k*37)%5-2)*120,dy=((k*53)%7-3)*72,rot=((k*29)%7-3)*10;
      animateMs(s,[{transform:`translate(${dx}px,${dy}px) rotate(${rot}deg)`,opacity:0},{transform:'translate(0px,0px) rotate(0deg)',opacity:1}],ms,'e-spring',at+Math.min(k,16)*45);
    });
  }
  // slice-reveal: the element's own clip-path opens horizontal bands in spatial
  // order (top -> bottom). One of the two approved property exceptions.
  function fxSlice(el,at){
    if(!CSS.supports('clip-path','inset(0px)'))return;
    const N=5,frames=[];
    for(let i=0;i<=N;i++)frames.push({clipPath:`inset(0% 0% ${(1-i/N)*100}% 0%)`,offset:i/N});
    animateMs(el,frames,duration(FX['slice-reveal'],el),'e-out',at);
  }
  // row-mask-rise: each child line rises out of an overflow-hidden mask, one at
  // a time. Masks are display:block spans removed by the last line's cleanup.
  function fxRowMask(el,at){
    const kids=Array.from(el.children).filter(shown).slice(0,12);
    if(!kids.length)return;
    const ms=duration(FX['row-mask-rise'],el),wraps=[];
    const unwrap=()=>{for(const w of wraps){while(w.firstChild)w.before(w.firstChild);w.remove();}};
    kids.forEach((k,i)=>{
      const w=document.createElement('span');w.className='ed-fx-mask';
      w.style.display='block';w.style.overflow='hidden';
      k.before(w);w.append(k);wraps.push(w);
      animateMs(k,[{transform:'translateY(110%)'},{transform:'translateY(0%)'}],ms,'e-spring',at+i*Math.max(40,ms/5),i===kids.length-1?unwrap:null);
    });
  }
  // weight-wave: the Pretendard Variable wght axis swells and releases across
  // the phrase, so emphasis visibly travels. For titles/keywords only.
  function fxWeight(el,at){
    const spans=fxLetters(el);if(!spans)return;
    // Unsupported engines still keep the kinetic-style letter split so the
    // settled DOM matches a slide that never carried the attribute.
    if(!CSS.supports('font-variation-settings','"wght" 700'))return;
    const base=Math.round(parseFloat(getComputedStyle(el).fontWeight)||400);
    const peak=Math.min(900,Math.max(base+250,700));
    const ms=duration(FX['weight-wave'],el)*1.8;
    spans.slice(0,48).forEach((s,k)=>{
      animateMs(s,[{fontVariationSettings:`"wght" ${base}`},{fontVariationSettings:`"wght" ${peak}`,offset:.45},{fontVariationSettings:`"wght" ${base}`}],ms,'e-inout',at+k*60);
    });
  }
  // rack-focus: attention transfers — the incoming element pulls into focus
  // (blur -> sharp, second approved exception) while data-fx-dim targets dip
  // and recover. Nothing stays blurred: the final state is the authored DOM.
  function fxRack(el,at){
    const ms=duration(FX['rack-focus'],el);
    animateMs(el,[{filter:'blur(6px)'},{filter:'blur(0px)'}],ms,'e-out',at);
    const scope=el.closest('.chk')||el.closest('.slide')||document;
    if(el.dataset.fxDim)all(el.dataset.fxDim,scope).slice(0,3).forEach(d=>animateMs(d,[{filter:'blur(0px)'},{filter:'blur(3px)',offset:.4},{filter:'blur(3px)',offset:.72},{filter:'blur(0px)'}],ms*1.8,'e-inout',at));
  }
  // ---- TASK-fx-absorb: three techniques ported by concept from the klic
  // motion catalogue (own implementation; no code copied) ----
  // bar-grow: a bar, gauge or progress strip grows from its fixed base edge
  // into the authored size — the element's own width/height IS the final state.
  // The authored transform-origin picks the axis (bottom anchors a vertical
  // grow, left a horizontal one; top/right follow the same rule). Without an
  // edge anchor the aspect ratio decides: taller than wide grows upward,
  // wider than tall grows rightward, and the base edge is set for the play.
  function fxBarGrow(el,at){
    const base=getComputedStyle(el).transform,suffix=base==='none'?'':' '+base;
    const w=el.offsetWidth||el.getBoundingClientRect().width||0,h=el.offsetHeight||el.getBoundingClientRect().height||0;
    const o=getComputedStyle(el).transformOrigin.split(' ').map(parseFloat);
    const edge=Math.abs(o[1]-h)<2?'bottom':Math.abs(o[1])<2?'top':Math.abs(o[0])<2?'left':Math.abs(o[0]-w)<2?'right':'';
    const vertical=edge?edge==='bottom'||edge==='top':h>w;
    if(!edge)el.style.transformOrigin=vertical?'center bottom':'left center';
    const axis=vertical?'scaleY':'scaleX';
    const peers=all('[data-fx="bar-grow"]',el.closest('.slide')||document),i=Math.max(0,peers.indexOf(el));
    animateMs(el,[{transform:`${axis}(0)`+suffix},{transform:`${axis}(1)`+suffix}],duration(FX['bar-grow'],el),'e-spring',at+Math.min(i,6)*duration('m1',el)/4);
  }
  // card-deal: a card is dealt out of a slightly stacked pile — it slides from
  // a small offset toward the pile's centre with a hint of index-hashed tilt
  // and settles square (final rotation 0). Offsets stay within ±24px/±4deg.
  function fxDeal(el,at){
    const base=getComputedStyle(el).transform,suffix=base==='none'?'':' '+base;
    const pile=el.parentElement?el.parentElement.getBoundingClientRect():null,r=el.getBoundingClientRect();
    let dx=0,dy=0;
    if(pile&&r.width&&r.height){
      dx=Math.max(-24,Math.min(24,(pile.left+pile.width/2-(r.left+r.width/2))*.35));
      dy=Math.max(-24,Math.min(24,(pile.top+pile.height/2-(r.top+r.height/2))*.35));
    }
    const peers=all('[data-fx="card-deal"]',el.closest('.slide')||document),i=Math.max(0,peers.indexOf(el));
    const rot=((i*29)%7-3)*4/3;
    animateMs(el,[{transform:`translate(${dx.toFixed(1)}px,${dy.toFixed(1)}px) rotate(${rot.toFixed(2)}deg)`+suffix,opacity:0},{transform:'translate(0px,0px) rotate(0deg)'+suffix,opacity:1}],duration(FX['card-deal'],el),'e-spring',at+Math.min(i,6)*duration('m1',el)/4);
  }
  // blinds: the element is cut into horizontal strips that open top to bottom
  // in stagger — the clip-path exception slice-reveal already owns, so the
  // bands are one multi-rect polygon whose per-band edge sweeps down in turn.
  // One large-area element at a time; strip edges collapse to zero-height
  // rects until their window so the vertex count never changes.
  function fxBlinds(el,at){
    if(!CSS.supports('clip-path','polygon(0% 0%,100% 0%,100% 100%,0% 100%)'))return;
    const N=5,stagger=.12,span=.52;
    const times=new Set([0,1]);for(let i=0;i<N;i++){times.add(i*stagger);times.add(Math.min(1,i*stagger+span));}
    const frames=[...times].sort((a,b)=>a-b).map(t=>{
      const pts=[];for(let i=0;i<N;i++){
        const y0=i*100/N,y1=y0+Math.min(1,Math.max(0,(t-i*stagger)/span))*100/N;
        pts.push(`0% ${y0.toFixed(2)}%`,`100% ${y0.toFixed(2)}%`,`100% ${y1.toFixed(2)}%`,`0% ${y1.toFixed(2)}%`);
      }
      return{clipPath:`polygon(${pts.join(',')})`,offset:t};
    });
    animateMs(el,frames,duration(FX.blinds,el),'e-out',at);
  }
  function fxFire(el){
    const name=el.dataset.fx;
    if(!FX[name])return false;
    el._edFx=1;
    if(staticMode()){fxFinal(el);return false;}
    const at=Math.min(2000,Math.max(0,parseFloat(el.dataset.fxAt)||0));
    const base=getComputedStyle(el).transform,suffix=base==='none'?'':' '+base;
    switch(name){
      case 'strike':animate(fxOverlay(el,'ed-fx-strike'),[{transform:'scaleX(0)'},{transform:'scaleX(1)'}],FX.strike,'e-out',at);break;
      case 'mark':animate(fxOverlay(el,'ed-fx-mark'),[{transform:'scaleX(0)'},{transform:'scaleX(1)'}],FX.mark,'e-inout',at);break;
      case 'stamp':animate(el,[{transform:'scale(2.4) rotate(4deg)'+suffix,opacity:0},{transform:'scale(1) rotate(0deg)'+suffix,opacity:1}],FX.stamp,'e-out',at);break;
      case 'count':fxCount(el,at);break;
      case 'type':fxType(el,at);break;
      case 'travel':animate(el,[{transform:`translateX(${token('--dx',el)||'-240px'})`+suffix},{transform:'translateX(0px)'+suffix}],FX.travel,'e-out',at);break;
      case 'block':animate(el,[{transform:`translateX(${token('--dx',el)||'-240px'})`+suffix,offset:0},{transform:'translateX(0px)'+suffix,offset:.55},{transform:'translateX(-16px)'+suffix,offset:.8},{transform:'translateX(0px)'+suffix}],FX.block,'e-out',at);break;
      case 'press':animate(el,[{transform:'translateY(0px)'+suffix},{transform:'translateY(4px) scale(.96)'+suffix,offset:.4},{transform:'translateY(0px)'+suffix}],FX.press,'e-inout',at);break;
      case 'scatter-gather':fxScatter(el,at);break;
      case 'slice-reveal':fxSlice(el,at);break;
      case 'row-mask-rise':fxRowMask(el,at);break;
      case 'weight-wave':fxWeight(el,at);break;
      case 'rack-focus':fxRack(el,at);break;
      case 'bar-grow':fxBarGrow(el,at);break;
      case 'card-deal':fxDeal(el,at);break;
      case 'blinds':fxBlinds(el,at);break;
    }
    return 'fx-'+name;
  }
  // Fire every not-yet-fired fx element that is now visible and due (its reveal
  // step has been reached). Back/static visits only settle the final state.
  function fxSweep(s,step,back){
    const names=[];
    for(const el of all('[data-fx]',s)){
      // shown() reads only the element's own box: content hidden by an ancestor's
      // display:none (e.g. .chk-why inside .chk-fb) still reports shown, so it
      // must also have a rendered box or it would fire before it is visible.
      if(el._edFx||!shown(el)||!el.getClientRects().length)continue;
      if(revealStep(el,s)>step)continue;
      if(back||staticMode()){el._edFx=1;fxFinal(el);continue;}
      const sig=fxFire(el);
      if(sig)names.push(sig);
    }
    return names;
  }
  // A step's motion plays once, when that step is reached going forward. Moving back a
  // step or returning to an earlier slide shows the settled state without replaying
  // anything that was already presented.
  function play(s,step,entry,back){
    const arch=adapt(s),r=recipes[arch];if(!r)return null;
    if(back){still=true;try{marks(s);fxSweep(s,step,true);}finally{still=false;}return null;}
    marks(s);const fxNames=fxSweep(s,step,false);if(staticMode())return null;
    // A signature "fired" only when its choreography actually scheduled an
    // animation; crayon marks alone are not the layout signature. Multiple
    // signatures can fire on one slide (host archetype + embedded stat band).
    const before=animations.size,fired=[];
    let targets=all(selectors[arch],s).filter(shown);
    if(s.dataset.design)targets=all(packTargets[s.dataset.design]||'.pack-body,.pack-evidence,.pack-action',s).filter(shown);
    let newly=null;
    if(!entry){
      // Only elements that become visible at this step move. data-lit only restyles an
      // element that was already on screen, so it gets no movement (crayon marks still
      // draw for newly lit answers). A container that merely holds the new part does
      // not move; the new part itself does.
      newly=all('[data-step],[data-add],[data-only]',s).filter(e=>shown(e)&&['step','add','only'].some(a=>e.dataset[a]!==undefined&&+e.dataset[a]===step));
      const own=targets.filter(e=>newly.some(n=>n===e||n.contains(e)));
      const inner=newly.filter(n=>targets.some(e=>e!==n&&e.contains(n)));
      targets=own.length?own:inner;
      if(!targets.length)targets=newly;
    }
    // Avoid animating both an ancestor and its child in the same choreography.
    targets=targets.filter(e=>!targets.some(p=>p!==e&&p.contains(e))).slice(0,12);
    if(entry)titleImpact(s,arch);
    if(arch==='before-after'||arch==='worked-example')semanticScene(s,arch,step,entry);
    else{
      targets.forEach((e,i)=>{if(FX_OWN_TRANSFORM.has(e.dataset.fx))return;
        e.style.transformOrigin=arch==='meter'?'left center':arch==='sequence'?'left bottom':'center';
        // A newly revealed chat bubble is not a pin: pin overshoot crosses the
        // clipped chat viewport. Keep the bubble inside its final footprint.
        const frames=arch==='mock-legend'&&!e.matches('.mk')?['scale(.96)','scale(1)']:r.frames(i);
        move(e,frames,r.m||'m3',r.ease||'e-out',Math.min(i,6)*duration('m1',s)/4);});
      if(r.draw||s.dataset.design==='editorial'||s.dataset.design==='lab')draw(s,newly);
      if(r.particles)particles(s,newly);
      if(r.numbers)numbers(s,r.numbers===true?3:r.numbers);
      // Pack-owned motifs reinforce the reading path, independently of hue.
      const motif={editorial:'.editorial-rule',lab:'.lab-cycle span',field:'.field-wayfinding',casebook:'.casebook-stamp',atlas:'.atlas-route',workbook:'.workbook-lines span',briefing:'.briefing-readout',seminar:'.seminar-turns span'}[s.dataset.design];
      if(entry&&motif)all(motif,s).filter(shown).forEach((e,i)=>move(e,['scaleX(.1)','scaleX(1)'],'m3','e-out',i*duration('m1',s)/4));
    }
    if(animations.size>before)fired.push(r.name||arch);
    if(arch!=='stat-strip'&&rally(s,entry))fired.push(recipes['stat-strip'].name);
    fired.push(...fxNames);
    return fired.length?fired:null;
  }
  function sync(){
    queued=false;const s=current(),info=window.deckInfo?window.deckInfo():{},step=info.step||0;
    if(!s){cancel(true);active=null;priorStep=-1;return;}
    const entry=s!==active;if(!entry&&step===priorStep)return;
    // seen: the furthest step each slide has already presented. Re-entering a slide
    // at a step it already showed, or stepping back to a lower step on the same
    // slide, settles without motion. Moving forward inside a slide always plays —
    // even to a step visited before a detour back.
    const shownUpTo=seen.has(s)?seen.get(s):-1,back=entry?step<=shownUpTo:step<priorStep;
    if(step>shownUpTo)seen.set(s,step);
    cancel();if(active)all('.ed-mark',active).forEach(x=>unmark(x.parentElement));
    active=s;priorStep=step;
    const fired=play(s,step,entry,back);
    if(fired)for(const sig of fired)logSig(s,step,sig);
  }
  function schedule(){if(!queued){queued=true;queueMicrotask(sync);}}
  function settle(){cancel(true);if(current())marks(current());}
  function navigate(update,dir){
    cancel(true);const id=++navigation;
    // Reading pages can be much taller than the viewport. Keep semantic entry
    // signatures, but avoid full-page snapshots / 1920px ghosts on narrow screens.
    if(document.documentElement.classList.contains('ed-compact')){update();return;}
    if(staticMode()||!document.startViewTransition){
      const old=current();let ghost=null;
      if(old&&!staticMode()){
        ghost=document.createElement('div');ghost.className='ed-ghost';ghost.setAttribute('aria-hidden','true');ghost.inert=true;
        const copy=old.cloneNode(true);copy.removeAttribute('id');all('[id]',copy).forEach(e=>e.removeAttribute('id'));all('.ed-mark,.ed-particle,.ed-number-reel',copy).forEach(e=>e.remove());
        ghost.append(copy);old.parentElement.append(ghost);
      }
      update();const s=current();
      // Schedule after the semantic event's microtask, so it cannot cancel this pair.
      queueMicrotask(()=>{if(id!==navigation||staticMode()){if(ghost)ghost.remove();return;}
        if(ghost)animate(ghost,[{transform:'translateX(0px)',opacity:1},{transform:`translateX(${dir==='back'?96:-96}px)`,opacity:0}],'m3','e-inout',0,()=>ghost.remove());
        if(s)move(s,[`translateX(${dir==='back'?-96:96}px) scale(.985)`,'translateX(0px) scale(1)'],'m3');
      });return;
    }
    document.documentElement.dataset.edDirection=dir;
    transition=document.startViewTransition(()=>{if(id===navigation)update();});
    transition.ready.catch(()=>{});
    transition.updateCallbackDone.catch(()=>{});
    transition.finished.catch(()=>{}).finally(()=>{if(id===navigation)transition=null;});
  }
  function init(){
    all('.slide',stage).forEach(s=>{adapt(s);all('[data-text]',s).forEach(e=>{if(!e.textContent)e.textContent=e.dataset.text;});});
    document.fonts.ready.then(()=>{
      all('.cx-title',stage).forEach(t=>{const room=t.parentElement.clientWidth-40;for(const n of [160,128,104]){t.style.fontSize=n+'px';if(t.scrollWidth<=room)break;}});
      schedule();
    });
  }
  window.eduMotion={navigate,mark,unmark,verdict,settle,signatures:Object.keys(recipes),sigLog};
  document.addEventListener('deckslide',schedule);document.addEventListener('deckstep',schedule);
  // Interactive patterns may reveal content between steps (e.g. a tab pane opened
  // without a deckstep): any data-fx inside it is due the moment it shows.
  document.addEventListener('edpattern',()=>{const s=current();if(s)fxSweep(s,(window.deckInfo&&window.deckInfo().step)||0,false);});
  window.addEventListener('beforeprint',()=>{printing=true;settle();});
  window.addEventListener('afterprint',()=>{printing=false;settle();});
  reduce.addEventListener('change',settle);mediaPrint.addEventListener('change',settle);
  document.addEventListener('edmode',settle);
  new MutationObserver(()=>{if(staticMode())settle();}).observe(document.body,{attributes:true,attributeFilter:['class']});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)settle();});
  init();
})();

/*
  상호작용 조각 위젯(TASK-tools G4·G5 · TASK-quadrant-flash): 탐색 칩(.expl) · 사이드 시트(.dsheet) · 플래시카드(.fc).
  [카드] .fc 를 누르면 .on 토글로 앞↔뒷면이 뒤집힌다. 조작 자체는 시그니처가 아니며
    인쇄·자습·정지 펼치기는 CSS(정적 완결)가 맡는다.
  [탐색] .expl-chip[data-x] 를 누르면 같은 .expl 안에서 data-x 가 같은 .expl-state 하나만 켠다.
    채점 없음. 상태를 바꾼 뒤 edpattern 을 흘려 그 안의 data-fx 가 필요하면 발화하게 한다.
  [시트] .dsheet-open[data-open] 를 누르면 같은 장의 .dsheet-panel[data-sheet=값] 과 .dsheet-dim 을 켠다.
    닫기: .dsheet-close·dim 클릭·Escape. 인쇄·자습 펼치기는 CSS(정적 완결)가 맡고 여기선 화면 조작만 한다.
*/
(function(){
  var doc=document;
  doc.addEventListener('click',function(e){
    var t=e.target;
    var chip=t&&t.closest?t.closest('.expl-chip'):null;
    if(chip){
      var box=chip.closest('.expl');if(!box)return;
      var x=chip.getAttribute('data-x');
      [].forEach.call(box.querySelectorAll('.expl-chip'),function(c){c.classList.toggle('on',c===chip);});
      [].forEach.call(box.querySelectorAll('.expl-state'),function(s){s.classList.toggle('on',s.getAttribute('data-x')===x);});
      doc.dispatchEvent(new Event('edpattern'));
      return;
    }
    var fc=t&&t.closest?t.closest('.fc'):null;
    if(fc){fc.classList.toggle('on');return;}
    var open=t&&t.closest?t.closest('.dsheet-open'):null;
    if(open){
      var sl=open.closest('.slide');if(!sl)return;
      var id=open.getAttribute('data-open');
      [].forEach.call(sl.querySelectorAll('.dsheet-panel'),function(p){p.classList.toggle('on',p.getAttribute('data-sheet')===id);});
      var dim=sl.querySelector('.dsheet-dim');if(dim)dim.classList.add('on');
      doc.dispatchEvent(new Event('edpattern'));
      return;
    }
    if(t&&t.closest&&(t.closest('.dsheet-close')||t.closest('.dsheet-dim'))){
      [].forEach.call(doc.querySelectorAll('.dsheet-panel.on,.dsheet-dim.on'),function(el){el.classList.remove('on');});
    }
  });
  doc.addEventListener('keydown',function(e){
    if(e.key==='Escape')[].forEach.call(doc.querySelectorAll('.dsheet-panel.on,.dsheet-dim.on'),function(el){el.classList.remove('on');});
  });
})();
