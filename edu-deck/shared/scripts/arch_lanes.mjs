#!/usr/bin/env node
/**
 * arch_lanes.mjs — 업무 절차(레인) · 호출 순서(시퀀스) 도식을 덱 문법(svg.dg)으로 방출하는
 * 빌드 시점 생성기.
 *
 * [목적] SI 실무형 구성도 중 "업무 흐름(B1 Swimlane)"과 "호출/응답 순서(B2 Sequence)"를
 *   의미 모델(JSON)만으로 만든다. 좌표·레인 밴드·흐름 경로·토큰 위치를 손으로 잡지 않는 것이
 *   이 도구의 존재 이유다. 결과 SVG에는 레이아웃 엔진이 남지 않는다(런타임 의존 0).
 *
 * [흐름]
 *   1. 모델 검증(참조·예산·분기 완전성·루프 방향) — 실패는 즉시 FAIL.
 *   2. 토큰 시뮬레이션(process): 시작 → 이동마다 1단계, 게이트에 들어오면 나가는 갈래 전체를
 *      그 단계에서 공개한다. 출력은 nodeStep/edgeStep(단계→요소) 표.
 *   3. 레이아웃: 레인 밴드(행위자) 안에서 열=단계, 행=레인 내부 순번.
 *      sequence 는 행위자를 열로, 메시지를 행으로 놓는다(생명선=점선 polyline).
 *   4. 방출: 풀/레인 헤더 → 흐름 → 노드 → 현재 토큰 → 범례. 단계 속성만 붙인다.
 *
 * [입력] --in MODEL.json
 *   공통: view(process|sequence) · title · eyebrow · ariaLabel · notes · caption
 *   process: pool · lanes[{id,actor,order}] · nodes[{id,type,name,role,lane,col,row,labelSide}]
 *            edges[{id,from,to,flow,label,branch,labelSide}] · scenario{게이트id:키|[키,…]}
 *   sequence: actors[{id,name,role}] · messages[{id,from,to,label,kind(call|reply)}]
 *   type: start|end|task|system|decision      flow: seq|loop      kind: call|reply
 * [출력] -o <슬라이드.html|->  (기본 stdout)
 *   --svg-only  <section> 없이 <svg> 단편만
 *   --tokens F  토큰 시뮬레이션 결과(단계·현재 위치·가시 요소) JSON
 *   --check     검증만 수행하고, -o 파일이 있으면 바이트 비교(재생성 결정성)
 *   --quiet     요약 출력 생략
 *
 * [계약] viewBox 폭 1664 · 글자는 t-l/k-t-* 클래스(26/22px) · 링크 1개 = path 1개(≤12) ·
 *   장식은 rect/polygon/polyline/circle 만(path·line 은 draw 예산을 먹는다) ·
 *   화살촉 marker-end · SMIL·script·CSS 애니메이션 0 · 색은 var(--…) 토큰만.
 *   이 덱의 k-* 어휘로 그린 실무형 레인·시퀀스 표기다.
 *
 * [재현성] 같은 입력 → 같은 바이트. 시간·난수·환경값·절대경로를 출력에 넣지 않는다.
 *   검증: `node arch_lanes.mjs --in a.json -o x.html` 두 번 실행 후 diff 0.
 *
 * [수정 시 주의]
 *   - 링크 path 를 늘리지 말 것: 공통 엔진 draw() 가 슬라이드당 path 12개만 그린다.
 *   - 장식(레인 밴드·생명선·활성 막대·격자)에 path/line 을 쓰지 말 것. polyline 은 안전하다.
 *   - 글자에 고정 px·hex 를 쓰지 말 것(대비 검사기가 계산값을 읽는다). 클래스만.
 *   - 단계 번호를 코드에 적지 말 것 — 전부 시뮬레이터 출력(nodeStep/edgeStep)에서 온다.
 */
import fs from 'node:fs';
import process from 'node:process';

/* ── 0. CLI ──────────────────────────────────────────────────────── */
const argv = process.argv.slice(2);
const arg = (k, d = null) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const has = (k) => argv.includes(k);
if (!argv.length || has('--help') || has('-h')) {
  console.log(`arch_lanes.mjs — 레인/시퀀스 도식 생성기
usage: node arch_lanes.mjs --in MODEL.json [-o SLIDE.html] [--svg-only] [--tokens OUT.json]
                           [--check] [--quiet]
  --in       의미 모델(process|sequence)
  -o         슬라이드 단편 출력(기본 stdout)
  --svg-only <section> 없이 <svg> 만
  --tokens   토큰/단계 스냅샷 JSON 출력
  --check    검증만 수행 + -o 파일과 바이트 비교
  --quiet    요약 생략`);
  process.exit(argv.length ? 0 : 1);
}
const inPath = arg('--in');
if (!inPath || !fs.existsSync(inPath)) { console.error(`FAIL: 모델 파일 없음: ${inPath || '(없음)'}`); process.exit(1); }
const model = JSON.parse(fs.readFileSync(inPath, 'utf8'));
const outPath = arg('-o', arg('--out'));
const tokPath = arg('--tokens');
const svgOnly = has('--svg-only');
const checkOnly = has('--check');
const quiet = has('--quiet');

/* ── 1. 검증 ─────────────────────────────────────────────────────── */
const errors = [];
const warns = [];
const fail = (m) => errors.push(m);
const warn = (m) => warns.push(m);
// 시뮬레이션 단(검증 통과 뒤)의 오류 — fail 에 싣고 즉시 종료한다
const die = (m) => { fail(m); for (const e of errors) console.error(`FAIL: ${e}`); process.exit(1); };
const VIEW = ['sequence', 'compare'].includes(model.view) ? model.view : 'process';
const CHANGES = ['keep', 'new', 'change', 'remove'];
/* ── 3. 좌표 ─────────────────────────────────────────────────────── */
const VBW = 1664;
const C = {
  margin: 15, laneHead: 150, poolH: 42, padT: 24, padB: 10, rowH: 72,
  taskW: 168, taskH: 54, decW: 88, decH: 60, evtR: 20, legend: 46,
};
const boxW = (type) => (type === 'decision' ? C.decW : type === 'start' || type === 'end' ? C.evtR * 2 : C.taskW);

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const round = (v) => +(+v).toFixed(1);
/** 글자 폭 근사(px). 한글·전각 1em, 라틴·숫자·공백 0.56em — 넘침 검사의 1차 방어선. */
const textW = (s, px) => [...String(s)].reduce((w, ch) => w + (/[\u3000-\u9fff\uac00-\ud7af]/.test(ch) ? px : px * 0.56), 0);

if (!model.title) fail('title 필수');
if (VIEW === 'process') validateProcess();
else if (VIEW === 'sequence') validateSequence();
else validateCompare();
if (errors.length) { for (const e of errors) console.error(`FAIL: ${e}`); process.exit(1); }

function validateProcess() {
  const ids = new Set();
  const lanes = model.lanes || [];
  if (!lanes.length) return fail('lanes 필수');
  const laneIds = new Set(lanes.map((l) => l.id));
  for (const l of lanes) { if (!l.id || !l.actor) fail('lane 은 id·actor 필수'); }
  for (const n of model.nodes || []) {
    if (!n.id || !n.name) fail(`node id·name 필수: ${JSON.stringify(n).slice(0, 80)}`);
    if (ids.has(n.id)) fail(`중복 node id: ${n.id}`);
    ids.add(n.id);
    if (!laneIds.has(n.lane)) fail(`${n.id}: 알 수 없는 lane ${n.lane}`);
    if (!['start', 'end', 'task', 'system', 'decision'].includes(n.type)) fail(`${n.id}: 알 수 없는 type ${n.type}`);
    if ((n.col ?? -1) < 0) fail(`${n.id}: col 은 0 이상`);
    // 판정·이벤트 라벨은 상자 밖(아래 칩)에 그리므로 상자 폭 검사 대상이 아니다
    if (n.type === 'task' || n.type === 'system') {
      const box = boxW(n.type);
      if (textW(n.name, 26) > box - 8) warn(`${n.id}: 이름이 상자 폭을 넘습니다(약 ${Math.round(textW(n.name, 26))}px > ${box - 8}px)`);
      if (n.role && textW(n.role, 22) > box - 8) warn(`${n.id}: 역할이 상자 폭을 넘습니다(약 ${Math.round(textW(n.role, 22))}px > ${box - 8}px)`);
    }
  }
  const edgeIds = new Set();
  for (const e of model.edges || []) {
    if (!e.id) fail('edge id 필수');
    if (edgeIds.has(e.id)) fail(`중복 edge id: ${e.id}`);
    edgeIds.add(e.id);
    if (!ids.has(e.from) || !ids.has(e.to)) fail(`${e.id}: 알 수 없는 끝점 ${e.from}→${e.to}`);
    if (!['seq', 'loop'].includes(e.flow || 'seq')) fail(`${e.id}: flow 는 seq|loop`);
  }
  const edges = model.edges || [];
  if (edges.length > 12) fail(`링크 ${edges.length}개 > 12(draw 예산) — 장을 나눌 것`);
  const outOf = new Map();
  for (const e of edges) outOf.set(e.from, [...(outOf.get(e.from) || []), e]);
  for (const n of model.nodes || []) {
    const outs = outOf.get(n.id) || [];
    if (n.type === 'decision' && outs.length < 2) fail(`${n.id}: decision 은 나가는 흐름이 2개 이상이어야 한다`);
    if (!['end'].includes(n.type) && outs.length === 0) warn(`${n.id}: 나가는 흐름이 없다(고아 노드)`);
  }
  const starts = (model.nodes || []).filter((n) => n.type === 'start');
  if (starts.length !== 1) fail(`start 노드는 정확히 1개여야 한다(현재 ${starts.length})`);
  const byId = Object.fromEntries((model.nodes || []).map((n) => [n.id, n]));
  for (const e of edges) {
    if (e.flow === 'loop' && byId[e.to].col >= byId[e.from].col) fail(`${e.id}: loop 은 앞 열로 돌아가야 한다(${byId[e.from].col} → ${byId[e.to].col})`);
  }
  const maxRow = Math.max(...(model.nodes || []).map((n) => n.row || 0));
  if (maxRow > 2) warn(`레인 최대 행 ${maxRow + 1} — 높이 초과 위험(2 이하 권장)`);
}

function validateSequence() {
  const ids = new Set();
  for (const a of model.actors || []) {
    if (!a.id || !a.name) fail('actor 는 id·name 필수');
    if (ids.has(a.id)) fail(`중복 actor id: ${a.id}`);
    ids.add(a.id);
  }
  if (!(model.actors || []).length) fail('actors 필수');
  const msgs = model.messages || [];
  if (!msgs.length) fail('messages 필수');
  if (msgs.length > 12) fail(`메시지 ${msgs.length}개 > 12(draw 예산)`);
  for (const m of msgs) {
    if (!ids.has(m.from) || !ids.has(m.to)) fail(`${m.id}: 알 수 없는 액터 ${m.from}→${m.to}`);
    if (!['call', 'reply'].includes(m.kind || 'call')) fail(`${m.id}: kind 는 call|reply`);
    if (m.from === m.to) fail(`${m.id}: 자기 호출은 이번 범위 밖`);
  }
}

function validateCompare() {
  const rows = model.rows || [];
  if (!rows.length) return fail('rows 필수(계층 띠)');
  const ids = new Set();
  for (const n of model.nodes || []) {
    if (!n.id || !n.name) fail('compare node 는 id·name 필수');
    if (ids.has(n.id)) fail(`중복 node id: ${n.id}`);
    ids.add(n.id);
    if (!CHANGES.includes(n.change || 'keep')) fail(`${n.id}: change 는 keep|new|change|remove`);
    if (!rows[n.row ?? -1]) fail(`${n.id}: 알 수 없는 row ${n.row}`);
    if ((n.col ?? -1) < 0) fail(`${n.id}: col 은 0 이상`);
    if (textW(n.name, 26) > 236) warn(`${n.id}: 이름이 카드 폭을 넘을 수 있습니다(약 ${Math.round(textW(n.name, 26))}px)`);
  }
  let paths = 0;
  for (const e of model.edges || []) {
    if (!ids.has(e.from) || !ids.has(e.to)) fail(`${e.id}: 알 수 없는 끝점 ${e.from}→${e.to}`);
    if (!CHANGES.includes(e.state || 'keep')) fail(`${e.id}: state 는 keep|new|remove(change 는 노드 전용)`);
    paths++;
  }
  if (paths > 12) fail(`링크 ${paths}개 > 12(draw 예산)`);
}

/* ── 2. 토큰 시뮬레이션(process) ─────────────────────────────────── */
/** 시작 → 이동마다 1단계. 게이트 진입 시 나가는 갈래 전체 공개, 실행은 scenario 대로 하나만. */
function simulate() {
  const byId = Object.fromEntries(model.nodes.map((n) => [n.id, n]));
  const outs = (id) => model.edges.filter((e) => e.from === id);
  const start = model.nodes.find((n) => n.type === 'start');
  const nodeStep = { [start.id]: 1 };
  const edgeStep = {};
  const route = [];
  const queue = {}; // 게이트별 분기키 소비 대기열
  let cur = start;
  let ended = false;
  for (let i = 1; i <= 40; i++) {
    const o = outs(cur.id);
    if (!o.length || cur.type === 'end') { ended = true; break; }
    let pick = o[0];
    if (cur.type === 'decision') {
      const q = queue[cur.id] || (queue[cur.id] = [...(model.scenario?.[cur.id] || [])]);
      const key = q.shift();
      if (key === undefined)
        die(`분기키 소진 — 게이트 ${cur.id} 재방문인데 scenario 대기열이 비었다: scenario 에는 게이트 방문 순서대로 키를 전부 나열해야 한다`);
      pick = o.find((e) => e.branch === key);
      if (!pick)
        die(`분기키 오류 — 게이트 ${cur.id}: scenario 키 '${key}'가 나가는 branch [${o.map((e) => e.branch).join(', ')}] 어느 것과도 일치하지 않는다`);
    }
    const nxt = byId[pick.to];
    const step = i + 1;
    route.push({ step, edge: pick.id, from: cur.id, to: nxt.id });
    if (edgeStep[pick.id] === undefined) edgeStep[pick.id] = step;
    if (nodeStep[nxt.id] === undefined) nodeStep[nxt.id] = step;
    if (nxt.type === 'decision') {
      for (const e of outs(nxt.id)) {
        if (edgeStep[e.id] === undefined) edgeStep[e.id] = step;
        if (nodeStep[e.to] === undefined) nodeStep[e.to] = step;
      }
    }
    cur = nxt;
    if (cur.type === 'end') { ended = true; break; }
  }
  if (!ended) die(`시뮬레이션 미종료 — 40회 이동 안에 end 노드에 도달하지 못했다(순환 시나리오 의심)`);
  // 구조 마감: 실행되지 않은 갈래의 다음 흐름도 출발 노드가 보이는 단계에 공개
  for (const e of model.edges) if (edgeStep[e.id] === undefined) edgeStep[e.id] = nodeStep[e.from] ?? 2;
  // 양 끝점이 보이기 전에는 흐름도 보이지 않는다(끝점 없는 화살표 방지)
  for (const e of model.edges) edgeStep[e.id] = Math.max(edgeStep[e.id], nodeStep[e.from] ?? 1, nodeStep[e.to] ?? 1);
  const steps = [];
  const top = Math.max(...Object.values(edgeStep), ...Object.values(nodeStep));
  for (let n = 1; n <= top; n++) {
    steps.push({
      n,
      at: [...route].reverse().find((m) => m.step <= n)?.to ?? start.id,
      via: route.find((m) => m.step === n)?.edge ?? null,
      nodes: model.nodes.filter((x) => (nodeStep[x.id] ?? 1e9) <= n).map((x) => x.id),
      edges: model.edges.filter((x) => edgeStep[x.id] <= n).map((x) => x.id),
    });
  }
  return { route, nodeStep, edgeStep, steps };
}

/* ── 4. 방출 ─────────────────────────────────────────────────────── */
const doc = VIEW === 'process' ? buildProcess() : VIEW === 'sequence' ? buildSequence() : buildCompare();
const body = svgOnly ? doc.svg : doc.section;
if (outPath) {
  if (checkOnly) {
    const prev = fs.existsSync(outPath) ? fs.readFileSync(outPath, 'utf8') : null;
    const same = prev === body + (body.endsWith('\n') ? '' : '\n') || prev === body;
    console.log(`${same ? 'SAME' : 'DIFF'}  ${outPath}${prev === null ? ' (없음 → 새로 만듦)' : ''}`);
    if (!quiet) report();
    process.exit(same ? 0 : 1);
  }
  fs.writeFileSync(outPath, body.endsWith('\n') ? body : body + '\n');
} else {
  process.stdout.write(body.endsWith('\n') ? body : body + '\n');
}
if (tokPath) {
  const t = VIEW === 'process' ? simulate() : { steps: doc.steps };
  fs.writeFileSync(tokPath, JSON.stringify({ view: VIEW, ...t }, null, 1) + '\n');
}
if (!quiet) report();

function report() {
  for (const w of warns) console.error(`WARN: ${w}`);
  console.log(`${VIEW} · lanes=${doc.meta.lanes ?? doc.meta.actors} · steps=${doc.meta.steps} · paths=${doc.meta.paths} · viewBox=${VBW}x${doc.meta.h}`);
}

function header(kind) {
  const rel = inPath.replace(/^.*?(?=examples\/|models\/)/, '');
  return `<!-- ${kind}
     모델: ${rel} · 생성: node edu-deck/shared/scripts/arch_lanes.mjs --in ${rel} -o <이 파일>
     손으로 고치지 않는다. 모델을 고치고 다시 생성한다. -->`;
}

/* ── 4-A. process(레인) ──────────────────────────────────────────── */
function buildProcess() {
  const sim = simulate();
  const lanes = [...model.lanes].sort((a, b) => a.order - b.order);
  const cols = Math.max(...model.nodes.map((n) => n.col)) + 1;
  const colW = (VBW - C.laneHead - C.margin * 2) / cols;
  const colX = (c) => round(C.laneHead + C.margin + colW * (c + 0.5));

  let y = C.poolH;
  for (const L of lanes) {
    const rows = Math.max(...model.nodes.filter((n) => n.lane === L.id).map((n) => n.row || 0)) + 1;
    Object.assign(L, { rows, y0: y, h: C.padT + rows * C.rowH + C.padB });
    y += L.h;
  }
  const H = y + C.legend;
  const laneOf = Object.fromEntries(lanes.map((l) => [l.id, l]));
  const N = {};
  for (const n of model.nodes) {
    const L = laneOf[n.lane];
    const cx = colX(n.col);
    const cy = round(L.y0 + C.padT + (n.row || 0) * C.rowH + C.rowH / 2);
    N[n.id] = { ...n, cx, cy, ...geometry(n.type, cx, cy) };
  }
  const P = (id, side) => {
    const n = N[id];
    const m = { left: [n.l, n.cy], right: [n.r, n.cy], top: [n.cx, n.t], bottom: [n.cx, n.b] }[side];
    return { x: round(m[0]), y: round(m[1]) };
  };
  /**
   * 대조 모드 전용 경로 — 카드 사이 '채널'(행 사이 여백)로만 꺾는다.
   * [이유] 행이 3개뿐인 격자에서 기본 직교 경로를 쓰면 뒤쪽 열로 가는 선이 카드를 관통한다.
   *   아래로 내려갈 때는 이 행 아래 채널, 위로 올라갈 때는 위 채널에서 가로로 이동한다.
   */
  const routeC = (e) => {
    const a = N[e.from], b = N[e.to];
    if (a.row === b.row) {
      if (Math.abs(a.cx - b.cx) < 1) return [{ x: a.cx, y: a.t }, { x: b.cx, y: b.b }];
      return [P(e.from, b.cx > a.cx ? 'right' : 'left'), P(e.to, b.cx > a.cx ? 'left' : 'right')];
    }
    if (Math.abs(a.cx - b.cx) < 1) return [P(e.from, b.row > a.row ? 'bottom' : 'top'), P(e.to, b.row > a.row ? 'top' : 'bottom')];
    const y = b.row > a.row ? round(bandY(a.row) + ROW - 16) : round(bandY(a.row) + 16);
    return [P(e.from, b.row > a.row ? 'bottom' : 'top'), { x: a.cx, y }, { x: b.cx, y }, P(e.to, b.row > a.row ? 'top' : 'bottom')];
  };
  const opts = model.options || {};
  const routeOf = (e) => routeEdge(e, N, P, laneOf, opts);
  // 칩 배치 순서: 흐름 라벨(모델 순서). 겹치면 자동으로 위/아래/좌/우를 옮긴다.
  // 판정(마름모) 이름은 알약이 아니라 마름모 위 잉크 글자로 찍는다 — 같은 흰색
  // 알약이면 분기 조건(엣지 라벨)과 구분되지 않는다(크리틱 Major-4).
  const chips = {};
  {
    const obstacles = Object.values(N).map((n) => ({ x0: n.l - 4, x1: n.r + 4, y0: n.t - 4, y1: n.b + 4 }));
    for (const n of Object.values(N)) {
      if (n.type !== 'decision') continue;
      const nw = Math.round(textW(n.name, 22)) + 8;
      obstacles.push({ x0: n.cx - nw / 2, x1: n.cx + nw / 2, y0: n.t - 36, y1: n.t - 8 });
      if (n.role) {
        const rw = Math.round(textW(n.role, 22)) + 8;
        obstacles.push({ x0: n.cx - rw / 2, x1: n.cx + rw / 2, y0: n.b + 8, y1: n.b + 36 });
      }
    }
    for (const e of model.edges) {
      if (!e.label) continue;
      const pts = routeOf(e);
      const w = Math.round(textW(e.label, 22) + 24), h = 36;
      const a = labelAt(e, pts);
      if (a.side === 'on') { chips[e.id] = { x: round(a.x - w / 2), y: round(a.y - h / 2), w, h }; continue; }
      const c = placeChip(a.x, a.y, w, h, [a.side, 'above', 'below', 'right', 'left'], obstacles, { x0: 8, x1: VBW - 8, y0: C.poolH + 6, y1: H - 8 });
      // 캔버스 위로 밀려 올라간 칩은 머리띠를 덮는다 — 아래로 내린다
      if (c.y < C.poolH + 6) c.y = C.poolH + 6;
      chips[e.id] = { ...c, w, h };
      obstacles.push({ x0: c.x, x1: c.x + w, y0: c.y, y1: c.y + h });
    }
  }
  const svg = [];
  svg.push(`  <svg class="dg" viewBox="0 0 ${VBW} ${H}" role="img" aria-label="${esc(model.ariaLabel || model.title)}">`);
  svg.push(`  <title>${esc(model.title)}</title>`);
  svg.push(`  <g data-step="0">
    <rect class="k-solid-b" x="0" y="0" width="${VBW}" height="${C.poolH}" style="rx:10px"/>
    <text class="t-l k-t-w" x="16" y="34">${esc(model.pool || model.title)}</text>
    <text class="k-t-tag k-t-w" x="${VBW - 16}" y="33" text-anchor="end">행위자 ${lanes.length} · 단계 ${sim.steps.length}</text>`);
  for (const L of lanes) {
    svg.push(`    <rect class="k-gray" x="0" y="${round(L.y0)}" width="${VBW}" height="${round(L.h)}"/>`);
    svg.push(`    <rect class="k-solid-b" x="0" y="${round(L.y0)}" width="${C.laneHead}" height="${round(L.h)}"/>`);
    svg.push(`    <text class="k-t-tag k-t-w" transform="translate(30 ${round(L.y0 + L.h / 2)}) rotate(-90)" text-anchor="middle">${esc(L.actor)}</text>`);
  }
  svg.push(`  </g>`);
  // 흐름 — loop 는 문서 순서를 마지막으로(엔진 draw 가 순서대로 12개를 그린다)
  const ordered = [...model.edges].sort((a, b) => (a.flow === 'loop' ? 1 : 0) - (b.flow === 'loop' ? 1 : 0));
  for (const e of ordered) {
    const pts = routeOf(e);
    const st = sim.edgeStep[e.id] || 2;
    const loop = e.flow === 'loop';
    const cls = loop ? 'k-ln-o' : 'k-ln-b';
    const dash = loop ? ' style="stroke-dasharray:14 10"' : '';
    svg.push(`    <g data-step="${st}">`);
    svg.push(`      <path class="${cls}" d="${pathD(pts)}"${dash} marker-end="url(#${loop ? 'ah-o' : 'ah-b'})"/>`);
    if (e.label) {
      const c = chips[e.id];
      svg.push(`      <rect class="k-paper" x="${c.x}" y="${c.y}" width="${c.w}" height="${c.h}" style="rx:9px"/>`);
      svg.push(`      <text class="k-t-tag" x="${round(c.x + c.w / 2)}" y="${round(c.y + c.h - 8)}" text-anchor="middle">${esc(e.label)}</text>`);
    }
    svg.push(`    </g>`);
  }
  // 노드
  for (const raw of model.nodes) {
    const n = N[raw.id];
    const st = sim.nodeStep[n.id] || 2;
    svg.push(`    <g data-step="${st}">`);
    if (n.type === 'decision') {
      svg.push(`      <polygon class="k-orange" points="${n.cx},${n.t} ${n.r},${n.cy} ${n.cx},${n.b} ${n.l},${n.cy}"/>`);
      // 판정 기준명 — 알약이 아닌 잉크 글자(배경 마스크만). 분기 조건 칩과 시각 위계를
      // 나눈다(크리틱 Major-4). 마스크는 글자가 레인 띠 경계 밖으로 걸치는 것도 막는다.
      const nw = Math.round(textW(n.name, 22)) + 16;
      svg.push(`      <rect x="${round(n.cx - nw / 2)}" y="${round(n.t - 40)}" width="${nw}" height="32" style="fill:var(--light);rx:8px"/>`);
      svg.push(`      <text class="k-t-tag" x="${n.cx}" y="${round(n.t - 16)}" text-anchor="middle" style="fill:var(--ink)">${esc(n.name)}</text>`);
      if (n.role) svg.push(`      <text class="k-t-tag" x="${n.cx}" y="${round(n.b + 30)}" text-anchor="middle">${esc(n.role)}</text>`);
    } else if (n.type === 'start' || n.type === 'end') {
      svg.push(`      <circle class="k-paper" cx="${n.cx}" cy="${n.cy}" r="${C.evtR}"/>`);
      if (n.type === 'end') svg.push(`      <circle cx="${n.cx}" cy="${n.cy}" r="${C.evtR - 6}" style="fill:none;stroke:var(--ink);stroke-width:4"/>`);
      const ey = n.type === 'end' ? n.cy - 32 : n.cy + 40;
      svg.push(`      <text class="k-t-tag" x="${n.cx}" y="${round(ey)}" text-anchor="middle">${esc(n.name)}</text>`);
    } else {
      const bw = n.w || C.taskW, bh = n.h || C.taskH;
      const x = round(n.cx - bw / 2), yy = round(n.cy - bh / 2);
      svg.push(`      <rect class="${n.type === 'system' ? 'k-blue' : 'k-paper'}" x="${x}" y="${yy}" width="${bw}" height="${bh}" style="rx:10px"/>`);
      svg.push(`      <text class="t-l" x="${n.cx}" y="${round(n.cy - 4)}" text-anchor="middle">${esc(n.name)}</text>`);
      if (n.role) svg.push(`      <text class="k-t-tag" x="${n.cx}" y="${round(n.cy + 20)}" text-anchor="middle">${esc(n.role)}</text>`);
    }
    svg.push(`    </g>`);
  }
  // 현재 토큰 — data-only(그 단계에서만). 마지막 단계가 종료 노드면 링을 생략한다 —
  // 완결 화면에서 종료 기호 위 주황 링이 3중 과녁처럼 남는다(크리틱 Major-4).
  for (const s of sim.steps) {
    const n = N[s.at];
    if (!n) continue;
    if (s.n === sim.steps.length && n.type === 'end') continue;
    const ring = n.type === 'decision'
      ? `<polygon class="k-ln-o" points="${n.cx},${round(n.cy - C.decH / 2 - 16)} ${round(n.cx + C.decW / 2 + 10)},${n.cy} ${n.cx},${round(n.cy + C.decH / 2 + 16)} ${round(n.cx - C.decW / 2 - 10)},${n.cy}" style="fill:none"/>`
      : n.type === 'start' || n.type === 'end'
        ? `<circle class="k-ln-o" cx="${n.cx}" cy="${n.cy}" r="${C.evtR + 10}" style="fill:none"/>`
        : `<rect class="k-ln-o" x="${round(n.cx - (n.w || C.taskW) / 2 - 8)}" y="${round(n.cy - C.taskH / 2 - 8)}" width="${(n.w || C.taskW) + 16}" height="${C.taskH + 16}" style="rx:16px;fill:none"/>`;
    const evt = n.type === 'start' || n.type === 'end';
    const dot = evt ? '' : `<circle class="k-solid-o" cx="${round(n.cx + (n.type === 'decision' ? 0 : (n.w || C.taskW) / 2 - 2))}" cy="${round(n.cy - (n.type === 'decision' ? C.decH / 2 - 4 : C.taskH / 2 - 2))}" r="7"/>`;
    svg.push(`    <g data-only="${s.n}">${ring}${dot}</g>`);
  }
  svg.push(legend(H).map((l) => `    ${l}`).join('\n'));
  svg.push(`  </svg>`);
  const section = [
    header('업무 절차(레인) · arch_lanes 생성'),
    `<section class="slide" data-archetype="arch-diagram" style="gap:18px">`,
    `  <div class="head"><p class="eyebrow">${esc(model.eyebrow || '')}</p><h2 class="title">${esc(model.title)}</h2></div>`,
    ...svg,
    `  <p class="small">${esc(model.caption || '')}</p>`,
    `  <aside class="notes">${esc(model.notes || '')}</aside>`,
    `</section>`,
  ].join('\n');
  return { svg: svg.join('\n'), section, meta: { lanes: lanes.length, steps: sim.steps.length, paths: model.edges.length, h: H } };
}

function geometry(type, cx, cy) {
  const [w, h] = type === 'decision' ? [C.decW, C.decH] : type === 'start' || type === 'end' ? [C.evtR * 2, C.evtR * 2] : [C.taskW, C.taskH];
  return { l: round(cx - w / 2), r: round(cx + w / 2), t: round(cy - h / 2), b: round(cy + h / 2), w, h };
}

function routeEdge(e, N, P, laneOf, opts) {
  const a = N[e.from], b = N[e.to];
  const side = (opts.route || {})[e.id];
  if (side === 'straight') return [P(e.from, 'right'), P(e.to, 'left')];
  if (side === 'h') return [P(e.from, 'right'), P(e.to, 'left')];
  if (side === 'fromBottom') return [P(e.from, 'bottom'), { x: a.cx, y: b.cy }, P(e.to, 'left')];
  if (side === 'toBottom') return [P(e.from, 'right'), { x: b.cx, y: a.cy }, P(e.to, 'bottom')];
  if (side === 'toTop') return [P(e.from, 'right'), { x: b.cx, y: a.cy }, P(e.to, 'top')];
  if (side === 'loop') {
    const top = laneOf[a.lane].y0 + 13;
    return [P(e.from, 'top'), { x: a.cx, y: round(top) }, { x: b.cx, y: round(top) }, P(e.to, 'top')];
  }
  if (side === 'up') { // 오른쪽 위로: 위 → 오른쪽 → 위
    const yy = round(Math.min(a.cy, b.cy) - (opts.upGap || 78));
    return [P(e.from, 'top'), { x: a.cx, y: yy }, { x: b.cx, y: yy }, P(e.to, 'top')];
  }
  if (Math.abs(a.cy - b.cy) < 1) return [P(e.from, 'right'), P(e.to, 'left')];
  if (Math.abs(a.cx - b.cx) < 1) return [P(e.from, 'bottom'), P(e.to, 'top')];
  const x = round(b.l - 26);
  return [P(e.from, 'right'), { x, y: a.cy }, { x, y: b.cy }, P(e.to, 'left')];
}

function pathD(pts, r = 10) {
  let d = `M${pts[0].x} ${pts[0].y}`;
  for (let i = 1; i < pts.length; i++) {
    const p = pts[i], q = pts[i - 1], nx = pts[i + 1];
    if (!nx) { d += ` L${p.x} ${p.y}`; break; }
    const l1 = Math.hypot(p.x - q.x, p.y - q.y), l2 = Math.hypot(nx.x - p.x, nx.y - p.y);
    const k = Math.min(r, l1 / 2, l2 / 2);
    if (!l1 || !l2) { d += ` L${p.x} ${p.y}`; continue; }
    const ax = p.x - ((p.x - q.x) / l1) * k, ay = p.y - ((p.y - q.y) / l1) * k;
    const bx = p.x + ((nx.x - p.x) / l2) * k, by = p.y + ((nx.y - p.y) / l2) * k;
    d += ` L${round(ax)} ${round(ay)} Q${p.x} ${p.y} ${round(bx)} ${round(by)}`;
  }
  return d;
}

/** 칩이 노드·이미 놓인 칩과 겹치는지. */
function hits(r, obstacles) {
  return obstacles.some((b) => r.x < b.x1 && r.x + r.w > b.x0 && r.y < b.y1 && r.y + r.h > b.y0);
}

/**
 * 라벨 칩 자리 고르기 — 후보를 순서대로 시도해 처음 겹치지 않는 자리를 쓴다.
 * [이유] 레인 도식은 라벨이 흐름 위에 놓이기 쉬워 고정 오프셋으로는 반드시 겹친다.
 *   노드 상자와 이미 놓은 칩만 장애물로 본다(선은 칩이 덮어도 읽힌다).
 */
function placeChip(ax, ay, w, h, prefer, obstacles, box) {
  const cands = [];
  for (const side of prefer) {
    for (const d of [10, 34, 58, 82]) {
      if (side === 'above') cands.push({ x: round(ax - w / 2), y: round(ay - h - d) });
      if (side === 'below') cands.push({ x: round(ax - w / 2), y: round(ay + d) });
      if (side === 'right') cands.push({ x: round(ax + d), y: round(ay - h / 2) });
      if (side === 'left') cands.push({ x: round(ax - w - d), y: round(ay - h / 2) });
    }
  }
  /* 칩은 캔버스 경계(box) 안에만 — 회피 오프셋이 컨테이너 밖 허공으로 튀는 회귀 방지 */
  const fits = box ? (c) => c.x >= box.x0 && c.x + w <= box.x1 && c.y >= box.y0 && c.y + h <= box.y1 : () => true;
  for (const c of cands) if (fits(c) && !hits({ ...c, w, h }, obstacles)) return c;
  const c0 = cands[0];
  if (!box) return c0;
  return { x: Math.min(Math.max(c0.x, box.x0), box.x1 - w), y: Math.min(Math.max(c0.y, box.y0), box.y1 - h) };
}

/** 라벨 자리: 가장 긴 구간의 중앙. side 로 위/아래/오른쪽/선 위를 고른다. */
function labelAt(e, pts) {
  let best = { len: 0, a: pts[0], b: pts[1] || pts[0] };
  for (let i = 1; i < pts.length; i++) {
    const len = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
    if (len > best.len) best = { len, a: pts[i - 1], b: pts[i] };
  }
  const horizontal = Math.abs(best.a.y - best.b.y) < 0.5;
  const x = round((best.a.x + best.b.x) / 2), y = round((best.a.y + best.b.y) / 2);
  const side = e.labelSide || (e.flow === 'loop' ? 'on' : horizontal ? 'above' : 'right');
  return { x, y, side };
}

function legend(H) {
  const ly = H - 22;
  return [`<g><polyline class="k-ln-b" points="20,${ly} 92,${ly}"/><text class="k-t-tag" x="106" y="${ly + 8}">순차</text>
      <polyline class="k-ln-o" points="210,${ly} 284,${ly}" style="stroke-dasharray:14 10"/><text class="k-t-tag" x="298" y="${ly + 8}">반려·재작업(역방향)</text>
      <polygon class="k-orange" points="600,${ly - 13} 615,${ly} 600,${ly + 13} 585,${ly}"/><text class="k-t-tag" x="627" y="${ly + 8}">판정</text>
      <rect class="k-blue" x="716" y="${ly - 14}" width="34" height="28" style="rx:8px"/><text class="k-t-tag" x="762" y="${ly + 8}">시스템 작업</text>
      <circle class="k-ln-o" cx="960" cy="${ly}" r="15" style="fill:none"/><text class="k-t-tag" x="984" y="${ly + 8}">현재 토큰</text></g>`];
}

/* ── 4-B. sequence(호출/응답) ────────────────────────────────────── */
function buildSequence() {
  const actors = model.actors;
  const msgs = model.messages;
  const headH = 76, rowH = model.rowH || 64, padT = 94, padB = 40;
  const H = headH + padT + msgs.length * rowH + padB;
  const laneW = (VBW - 80) / actors.length;
  const ax = (id) => round(40 + laneW * (actors.findIndex((a) => a.id === id) + 0.5));
  const A = Object.fromEntries(actors.map((a, i) => [a.id, { ...a, x: round(40 + laneW * (i + 0.5)) }]));
  // 활성 구간: 액터가 처음 메시지에 관여한 단계 ~ 마지막 관여 단계 (응답자 기준)
  const span = {};
  msgs.forEach((m, i) => {
    const step = i + 1;
    for (const id of [m.from, m.to]) {
      if (!span[id]) span[id] = { from: step, to: step };
      span[id].to = step;
    }
  });
  const svg = [];
  svg.push(`  <svg class="dg" viewBox="0 0 ${VBW} ${H}" role="img" aria-label="${esc(model.ariaLabel || model.title)}">`);
  svg.push(`  <title>${esc(model.title)}</title>`);
  const bottom = H - 26;
  // 헤더 + 생명선(점선 polyline — 장식이므로 draw 예산 밖)
  svg.push(`  <g data-step="0">
    <rect class="k-solid-b" x="0" y="0" width="${VBW}" height="${headH - 18}" style="rx:10px"/>
    <text class="t-l k-t-w" x="16" y="38">${esc(model.pool || model.title)}</text>
    <text class="k-t-tag k-t-w" x="${VBW - 16}" y="37" text-anchor="end">액터 ${actors.length} · 메시지 ${msgs.length}</text>`);
  for (const a of Object.values(A)) {
    svg.push(`    <rect class="k-paper" x="${round(a.x - 120)}" y="${headH - 6}" width="240" height="60" style="rx:10px"/>`);
    svg.push(`    <text class="t-l" x="${a.x}" y="${headH + 22}" text-anchor="middle">${esc(a.name)}</text>`);
    if (a.role) svg.push(`    <text class="k-t-tag" x="${a.x}" y="${headH + 48}" text-anchor="middle">${esc(a.role)}</text>`);
    svg.push(`    <polyline class="k-ln-g" points="${a.x},${headH + 60} ${a.x},${bottom}" style="stroke-dasharray:6 10"/>`);
  }
  svg.push(`  </g>`);
  // 메시지 — 1개 = path 1개. call 실선 / reply 점선(점선은 class+style, path 수는 그대로)
  // 라벨은 종이 마스크 칩에 담는다 — 중간 생명선이 글자를 관통하지 않게 한다.
  // 시작점 순번 배지(1~N)는 circle+text 장식 — draw 예산(path)을 쓰지 않는다.
  msgs.forEach((m, i) => {
    const step = i + 1;
    const y = headH + padT + i * rowH;
    const x1 = A[m.from].x, x2 = A[m.to].x;
    const dir = x2 > x1 ? 1 : -1;
    const reply = m.kind === 'reply';
    const cls = reply ? 'k-ln-g' : 'k-ln-b';
    const style = reply ? ' style="stroke-dasharray:10 8"' : '';
    const mk = reply ? 'ah-open' : 'ah-b';
    const x1e = round(x1 + dir * 10), x2e = round(x2 - dir * 10);
    const lw = round(textW(m.label, 22)) + 20;
    const nb = round(x1 + dir * 36);
    svg.push(`    <g data-step="${step}">`);
    svg.push(`      <path class="${cls}" d="M${x1e} ${round(y)} L${x2e} ${round(y)}"${style} marker-end="url(#${mk})"/>`);
    svg.push(`      <rect class="k-paper" x="${round((x1 + x2) / 2 - lw / 2)}" y="${round(y - 40)}" width="${lw}" height="32" style="rx:9px"/>`);
    svg.push(`      <text class="k-t-tag" x="${round((x1 + x2) / 2)}" y="${round(y - 16)}" text-anchor="middle">${esc(m.label)}</text>`);
    svg.push(`      <circle cx="${nb}" cy="${round(y)}" r="16" style="fill:var(--light);stroke:var(--line);stroke-width:2"/>`);
    svg.push(`      <text class="k-t-tag" x="${nb}" y="${round(y + 8)}" text-anchor="middle">${i + 1}</text>`);
    svg.push(`    </g>`);
  });
  // 활성 막대 — 액터가 관여한 구간. data-step 으로 켜지고 마지막 단계까지 남는다.
  for (const [id, s] of Object.entries(span)) {
    const x = A[id].x;
    const y1 = headH + padT + (s.from - 1) * rowH;
    const y2 = headH + padT + (s.to - 1) * rowH;
    svg.push(`    <g data-step="${s.from}"><rect class="k-orange" x="${round(x - 8)}" y="${round(y1 - 16)}" width="16" height="${round(y2 - y1 + 32)}" style="rx:5px;opacity:.45"/></g>`);
  }
  // 현재 메시지 표시 — 왼쪽 여백의 작은 표식만(그 단계에서만 보인다). 행 전체를 감싸면 화면이 무거워진다.
  // 마지막 메시지의 표식은 생략한다 — 완결 상태(마지막 단계)에서 좌측 구석에 남는
  // 유령 캡슐 아티팩트가 된다(크리틱 기술-3).
  msgs.forEach((m, i) => {
    if (i === msgs.length - 1) return;
    const y = headH + padT + i * rowH;
    svg.push(`    <g data-only="${i + 1}"><rect class="k-orange" x="14" y="${round(y - 14)}" width="10" height="28" style="rx:5px"/>`
      + `</g>`);
  });
  // 범례
  const ly = H - 14;
  svg.push(`    <g><polyline class="k-ln-b" points="20,${ly} 92,${ly}"/><text class="k-t-tag" x="106" y="${ly + 8}">호출</text>
      <polyline class="k-ln-g" points="210,${ly} 284,${ly}" style="stroke-dasharray:10 8"/><text class="k-t-tag" x="298" y="${ly + 8}">응답</text>
      <rect class="k-orange" x="396" y="${ly - 10}" width="12" height="20" style="rx:4px;opacity:.45"/><text class="k-t-tag" x="418" y="${ly + 8}">활성 구간</text>
      <rect class="k-orange" x="556" y="${ly - 12}" width="10" height="24" style="rx:5px"/><text class="k-t-tag" x="578" y="${ly + 8}">현재 메시지</text></g>`);
  svg.push(`  </svg>`);
  const steps = msgs.map((m, i) => ({ n: i + 1, at: m.from, via: m.id, nodes: [], edges: [m.id] }));
  const section = [
    header('호출 순서(시퀀스) · arch_lanes 생성'),
    `<section class="slide" data-archetype="arch-diagram" style="gap:18px">`,
    `  <div class="head"><p class="eyebrow">${esc(model.eyebrow || '')}</p><h2 class="title">${esc(model.title)}</h2></div>`,
    ...svg,
    `  <p class="small">${esc(model.caption || '')}</p>`,
    `  <aside class="notes">${esc(model.notes || '')}</aside>`,
    `</section>`,
  ].join('\n');
  return { svg: svg.join('\n'), section, steps, meta: { actors: actors.length, steps: msgs.length, paths: msgs.length, h: H } };
}

/* ── 4-C. compare(As-Is → To-Be) ─────────────────────────────────── */
/**
 * 변경 대조 모드. 좌표를 모델이 정하므로 두 상태의 같은 시스템이 **같은 자리**에 남는다
 * (dagre 는 노드 집합이 바뀌면 좌표가 흔들려 "위치 아이덴티티"를 보장하지 못한다).
 * 4상태: keep(유지) · new(신규) · change(변경) · remove(제거).
 * 단계: 1 As-Is 전체 → 2 제거 소거(흐림+취소선) → 3 신규 등장 → 4 변경 강조.
 */
function buildCompare() {
  const rows = model.rows;
  const cols = Math.max(...model.nodes.map((n) => n.col)) + 1;
  // 우측 여백 96 — 오른쪽 바깥 상태 배지(신규/변경/제거)가 표 외곽선·viewBox 를
  // 뚫고 나가지 않도록 열 너비 계산에 미리 빼 둔다(크리틱 기술-7 근본 패치).
  const RIGHT = 96;
  const colW = (VBW - C.laneHead - C.margin - RIGHT) / cols;
  const ROW = C.rowH + 56;   // 카드(56) + 채널 여백 — 칩이 행 사이에 들어갈 자리
  const CW = Math.min(260, Math.round(colW - 80));
  const colX = (c) => round(C.laneHead + C.margin + colW * (c + 0.5));
  const pool = C.poolH;
  const bandY = (i) => round(pool + i * ROW);
  const H = pool + rows.length * ROW + 58;
  const N = {};
  for (const n of model.nodes) {
    const cx = colX(n.col);
    const cy = round(bandY(n.row) + ROW / 2);
    N[n.id] = { ...n, cx, cy, l: round(cx - CW / 2), r: round(cx + CW / 2), t: round(cy - 28), b: round(cy + 28) };
  }
  const P = (id, side) => {
    const n = N[id];
    const m = { left: [n.l, n.cy], right: [n.r, n.cy], top: [n.cx, n.t], bottom: [n.cx, n.b] }[side];
    return { x: round(m[0]), y: round(m[1]) };
  };
  /**
   * 대조 모드 전용 경로 — 카드 사이 '채널'(행 사이 여백)로만 꺾는다.
   * [이유] 행이 3개뿐인 격자에서 기본 직교 경로를 쓰면 뒤쪽 열로 가는 선이 카드를 관통한다.
   *   아래로 내려갈 때는 이 행 아래 채널, 위로 올라갈 때는 위 채널에서 가로로 이동한다.
   */
  const routeC = (e) => {
    const a = N[e.from], b = N[e.to];
    if (a.row === b.row) {
      if (Math.abs(a.cx - b.cx) < 1) return [{ x: a.cx, y: a.t }, { x: b.cx, y: b.b }];
      return [P(e.from, b.cx > a.cx ? 'right' : 'left'), P(e.to, b.cx > a.cx ? 'left' : 'right')];
    }
    if (Math.abs(a.cx - b.cx) < 1) return [P(e.from, b.row > a.row ? 'bottom' : 'top'), P(e.to, b.row > a.row ? 'top' : 'bottom')];
    const y = b.row > a.row ? round(bandY(a.row) + ROW - 16) : round(bandY(a.row) + 16);
    return [P(e.from, b.row > a.row ? 'bottom' : 'top'), { x: a.cx, y }, { x: b.cx, y }, P(e.to, b.row > a.row ? 'top' : 'bottom')];
  };
  const chips = {};
  {
    const obstacles = Object.values(N).map((n) => ({ x0: n.l - 4, x1: n.r + 4, y0: n.t - 4, y1: n.b + 4 }));
    obstacles.push({ x0: 0, x1: VBW, y0: 0, y1: pool });   // 머리띠도 장애물
    for (const e of model.edges) {
      if (!e.label) continue;
      const pts = routeC(e);
      const w = Math.round(textW(e.label, 22) + 24), h = 36;
      const a = labelAt(e, pts);
      const c = placeChip(a.x, a.y, w, h, ['below', 'above', 'right', 'left'], obstacles, { x0: 8, x1: VBW - 8, y0: pool + 6, y1: H - 8 });
      // 캔버스 위로 밀려 올라간 칩은 머리띠를 덮는다 — 아래로 내린다
      if (c.y < pool + 6) c.y = pool + 6;
      chips[e.id] = { ...c, w, h };
      obstacles.push({ x0: c.x, x1: c.x + w, y0: c.y, y1: c.y + h });
    }
  }
  const svg = [];
  svg.push(`  <svg class="dg" viewBox="0 0 ${VBW} ${H}" role="img" aria-label="${esc(model.ariaLabel || model.title)}">`);
  svg.push(`  <title>${esc(model.title)}</title>`);
  svg.push(`  <g data-step="0">
    <rect class="k-solid-b" x="0" y="0" width="${VBW}" height="${pool}" style="rx:10px"/>
    <text class="t-l k-t-w" x="16" y="34">${esc(model.pool || model.title)}</text>
    <text class="k-t-tag k-t-w" x="${VBW - 16}" y="33" text-anchor="end">4단계 · 유지 ${model.nodes.filter((n) => (n.change || 'keep') === 'keep').length} · 신규 ${model.nodes.filter((n) => n.change === 'new').length} · 변경 ${model.nodes.filter((n) => n.change === 'change').length} · 제거 ${model.nodes.filter((n) => n.change === 'remove').length}</text>`);
  for (let i = 0; i < rows.length; i++) {
    svg.push(`    <rect class="k-gray" x="0" y="${bandY(i)}" width="${VBW}" height="${ROW}"/>`);
    svg.push(`    <rect class="k-solid-b" x="0" y="${bandY(i)}" width="${C.laneHead}" height="${ROW}"/>`);
    svg.push(`    <text class="k-t-tag k-t-w" transform="translate(30 ${round(bandY(i) + ROW / 2)}) rotate(-90)" text-anchor="middle">${esc(rows[i].label)}</text>`);
  }
  svg.push(`  </g>`);
  // 흐름 — 제거되는 선은 1단계까지만(2단계에서 소거), 신규 선은 3단계에 등장
  for (const e of model.edges) {
    const pts = routeC(e);
    const st = e.state === 'remove' ? ' data-until="1"' : ` data-step="${e.state === 'new' ? 3 : 1}"`;
    svg.push(`    <g${st}>`);
    svg.push(`      <path class="k-ln-b" d="${pathD(pts)}" marker-end="url(#ah-b)"/>`);
    if (e.label) {
      const c = chips[e.id];
      svg.push(`      <rect class="k-paper" x="${c.x}" y="${c.y}" width="${c.w}" height="${c.h}" style="rx:9px"/>`);
      svg.push(`      <text class="k-t-tag" x="${round(c.x + c.w / 2)}" y="${round(c.y + c.h - 8)}" text-anchor="middle">${esc(e.label)}</text>`);
    }
    svg.push(`    </g>`);
  }
  // 노드 — 상태마다 등장/소거 묶음이 다르다
  const card = (n, cls, label, role, extra = '') => {
    const o = [`      <rect class="${cls}" x="${n.l}" y="${n.t}" width="${CW}" height="56" style="rx:10px${extra}"/>`];
    // compare 카드는 글자만 — 아이콘을 왼쪽에 넣으면 정렬 때문에 쓸 수 있는 폭이 줄어 장문이 넘친다.
    o.push(`      <text class="t-l" x="${n.cx}" y="${round(n.cy - 2)}" text-anchor="middle">${esc(label)}</text>`);
    if (role) o.push(`      <text class="k-t-tag" x="${n.cx}" y="${round(n.cy + 22)}" text-anchor="middle">${esc(role)}</text>`);
    return o;
  };
  // 배지: 카드 오른쪽 바깥(행 사이 여백) — 카드 위에 얹으면 위 카드와 붙어 보인다.
  // 솔리드 배경(신규=주황 · 변경=청색) 위 글자는 종이색(k-t-w) — 어두운 바탕에
  // 어두운 글자면 명도 대비 1.8:1 로 읽히지 않는다(크리틱 Blocker-1).
  const badge = (n, text, cls) => {
    const w = Math.round(textW(text, 22) + 22);
    const dark = cls !== 'k-gray';
    return [`      <rect class="${cls}" x="${round(n.r + 10)}" y="${round(n.cy - 14)}" width="${w}" height="28" style="rx:8px"/>`,
      `      <text class="k-t-tag${dark ? ' k-t-w' : ''}" x="${round(n.r + 10 + w / 2)}" y="${round(n.cy + 6)}" text-anchor="middle">${esc(text)}</text>`];
  };
  for (const raw of model.nodes) {
    const n = N[raw.id];
    const ch = n.change || 'keep';
    if (ch === 'keep') {
      svg.push(`    <g data-step="1">`, ...card(n, 'k-paper', n.name, n.role), `    </g>`);
    } else if (ch === 'new') {
      svg.push(`    <g data-step="3">`, ...card(n, 'k-orange', n.name, n.role), ...badge(n, '신규', 'k-solid-o'), `    </g>`);
    } else if (ch === 'change') {
      svg.push(`    <g data-until="3">`, ...card(n, 'k-paper', n.was || n.name, n.wasRole || n.role), `    </g>`);
      svg.push(`    <g data-step="4">`, ...card(n, 'k-blue', n.name, n.role), ...badge(n, '변경', 'k-solid-b'), `    </g>`);
    } else {
      svg.push(`    <g data-until="1">`, ...card(n, 'k-paper', n.name, n.role), `    </g>`);
      // 제거: 흐린 카드 + 취소선(polyline — path 가 아니므로 draw 예산 밖)
      svg.push(`    <g data-step="2" opacity="0.6">`, ...card(n, 'k-gray', n.name, n.role, ';stroke-dasharray:8 6'),
        `      <polyline points="${round(n.l + 10)},${round(n.cy)} ${round(n.r - 10)},${round(n.cy)}" style="fill:none;stroke:var(--soft);stroke-width:4;stroke-linecap:round"/>`,
        ...badge(n, '제거', 'k-gray'), `    </g>`);
    }
  }
  // 범례 — 4상태 필수
  const ly = round(H - 24);
  let x = 20;
  const items = [
    ['k-paper', '유지', '그대로'],
    ['k-orange', '신규', '주황 등장'],
    ['k-blue', '변경', '청색 교체'],
    ['k-gray', '제거', '흐림+취소선'],
  ];
  const parts = [];
  for (const [cls, label, desc] of items) {
    parts.push(`<rect class="${cls}" x="${x}" y="${ly - 14}" width="34" height="28" style="rx:8px"/><text class="k-t-tag" x="${x + 46}" y="${ly + 8}">${label}</text><text class="k-t-tag" x="${x + 46 + textW(label, 22) + 14}" y="${ly + 8}" opacity=".8">${desc}</text>`);
    x += 46 + textW(label, 22) + 14 + textW(desc, 22) + 54;
  }
  svg.push(`    <g>${parts.join('')}</g>`);
  svg.push(`  </svg>`);
  const section = [
    header('변경 대조(As-Is → To-Be) · 자체 저작 문법 — 위치는 모델이 고정한다'),
    `<section class="slide" data-archetype="arch-diagram" style="gap:18px">`,
    `  <div class="head"><p class="eyebrow">${esc(model.eyebrow || '')}</p><h2 class="title">${esc(model.title)}</h2></div>`,
    ...svg,
    `  <p class="small">${esc(model.caption || '')}</p>`,
    `  <aside class="notes">${esc(model.notes || '')}</aside>`,
    `</section>`,
  ].join('\n');
  return { svg: svg.join('\n'), section, meta: { lanes: rows.length, steps: 4, paths: model.edges.length, h: H } };
}
