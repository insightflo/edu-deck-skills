#!/usr/bin/env node
/* arch_layout.mjs — semantic JSON → dagre 빌드 시점 배치 → svg.dg 슬라이드 방출
 *
 * 축 ② 생성기(design.md §1.1): @dagrejs/dagre@3.1.3 고정본(vendor/dagre.esm.js, MIT —
 * vendor/dagre.esm.js.LEGAL.txt)으로 좌표·waypoint를 빌드 시점에 계산해 구운다.
 * 산출물에는 레이아웃 엔진이 없다(런타임 무게 0).
 *
 * 사용:
 *   node scripts/arch_layout.mjs MODEL.json [-o SLIDE.html] [--coords OUT.json]
 *                                          [--svg-only] [--quiet]
 *   node scripts/arch_layout.mjs --help
 *
 * MODEL.json(semantic JSON — design §2.2 부분집합):
 *   title·eyebrow·small·notes·ariaLabel·titleSvg : 슬라이드 문자열
 *   layout : { dir:"LR|TB", nodesep, ranksep, edgesep?, chipAvoid?:bool }
 *             기본 LR 48/96 · chipAvoid:true면 라벨 칩끼리의 충돌도 회피(옵트인)
 *             edgesep: 같은 노드 쌍의 병렬 간선(요청/응답) 벌어짐(px, 기본 0)
 *   hints  : [{ from, to, minlen?, weight? }]  배치 전용 보이지 않는 간선 —
 *             그리지도, draw 예산에도 들지 않는다. 존(Zone) 사각형에서 비멤버
 *             노드(예: 외부기관)를 밀어내 한 존이 다른 망을 삼키는 위상 왜곡을
 *             막을 때 쓴다(hint 로 랭크를 밀어 존 바깥에 둔다).
 *   steps  : { zones:1, nodes:2, edges:3 }          g[data-step] 단계 번호(기본값)
 *   nodes  : [{ id, name, role, icon:"i-*"|null, shape:"card|circle",
 *               fam:"paper|blue|orange", w, h, step?,
 *               template:"card|equip|cluster|rack-group", qty?, spec?,
 *               subitems?:[str…], res?, items?:[{icon?,label}] }]
 *             template(기본 card=기존 대형 카드, 하위호환):
 *               equip     컴팩트 장비형 96×88 — 아이콘 36 + 이름 15 + 스펙 13 +
 *                         우상단 수량 배지(qty:"2식"|"#1")
 *               cluster   헤더 + 내부 subitems 미니칩(2열) + 하단 리소스 바(res)
 *               rack-group 동종 소형 장비 items 2~4 가로 배열(#1|#2|#3)
 *   edges  : [{ from, to, label, kind:"b|o|g|r", flow?:bool, step?, aux?:bool }]
 *             kind b=동기(k-ln-b) o=이벤트(k-ln-o) g=보조(k-ln-g) r=응답(k-ln-g+점선+ah-open);
 *             flow→dash-flow 입자 · aux→data-step 없는 정적 보조선(draw 예산·dagre 배치 밖).
 *             모든 간선은 맨해튼 직교 라우팅(r=6)으로 굽는다 — 사선 세그먼트 없음.
 *   buses  : [{ id, label, from:[id…], to:[id…], y?, style:"trunk|san|lan", step? }]
 *             수평 백본 1줄 + 각 노드 수직 T-드롭(┬/┴). 드롭은 draw 예산에서 제외하고,
 *             버스 from×to 와 같은 쌍의 점대점 엣지는 자동 제거된다.
 *   haPairs: [[id, id, label?], …]  이중화 쌍 사이 이중 실선(═) 마커.
 *   zones  : [{ id, label, members:[id…], kind:"member|trust", labelPos:"top|bottom",
 *               pad:{top,bottom,side}, step?, parent?, headerStyle?, snap?:false }]
 *             member=k-paper 면색 띠(소속) · trust·미지정=k-frame 점선(신뢰 경계)
 *             between:[zoneA,zoneB?] 멤버 대신 두 존 사이의 경계선(점선 polyline+라벨)
 *             parent: 부모 존 id → 최대 3단계 중첩. 부모 상자는 자식 존 포함 bbox.
 *             headerStyle:"solid-navy"(딥 네이비 바) |"solid-blue"(로열 블루 바)
 *                        |"tinted"(아이스 틴트 면+좌상단 캡슐 헤더) — 상단 32px 바.
 *             같은 부모 아래(또는 최상위끼리) 존은 snap 기본 켜짐: 가로 나열이면
 *             y0·y1, 세로 나열이면 x0·x1 을 묶어 격자 정렬한다.
 *   states : [{ node, at, state:"ok|warn|down", text? }]  상태 칩 교체 — 이전 칩
 *             data-until=at-1, 새 칩 data-step=at(failover 시나리오 §4.7).
 *             node.state는 초기 칩, node.stateText 는 초기 칩 문구 덮어쓰기.
 *             text 는 칩 글자를 역할 문구(예 "Active·운영")로 구분할 때 쓴다.
 *   legend : [{ kind:"b|o|g|r", label } | { fam:"blue|orange|paper|gray", label }
 *             | { icon:"i-*", label } | { badge:"new|chg|old", label }]
 *             선 어휘 범례 1줄 — 생략하고 사용 kind가 2종 이상이면 자동 유도
 *             (기본 라벨 b:동기 호출 o:이벤트 g:보조·연계 r:응답).
 *             fam 항목은 노드 색 의미(예 주황=경계 장비)를 선 범례 옆에 함께 찍는다.
 *   legendStyle:"bar" → 하단 전폭 도면 범례 바(장비 미니 아이콘·회선 종류·배지).
 *   handover : { title, points:[{t,d}] }  우측 인수인계 카드 열 — 있으면 도식 70% +
 *             카드 30% 2단 구성. 도식이 작고 여백이 남는 장의 리듬 변주용.
 *   sidePanel: { title, table:{cols:[…],rows:[[…]]} | items:[{t,d}] }
 *             우측 24% 명세표 패널(BOM·핵심 리스트) — 도면과 같은 높이 맞물림.
 *   theme  : "blueprint" → 슬라이드에 .arch-blueprint(쿨화이트 도면 팔레트).
 *   chrome : "blueprint" → 1줄 컴팩트 도면 헤더(serial·title·eyebrow), 캔버스 확대.
 *   serial : "001" 같은 도면 번호(blueprint 크롬 좌단).
 *
 * 산출: 슬라이드 <section class="slide" data-archetype="arch-diagram"> 단편(기본 stdout→파일)
 *   --svg-only : svg.dg 단편만 / --coords : 좌표·경로 JSON 별도 파일
 * 계약(diagrams.md + archpi §5): 글자 k·t 접두 클래스(≥20px)·링크=path 1개씩(≤12)·
 *   장식 rect/polyline/circle·ah-* 화살촉·viewBox 폭 1664·role="img"+aria-label.
 * 재현성: 동일 입력 → 동일 출력(날짜·난수 없음, JSON 키 순서 고정).
 */
import fs from 'node:fs';
import path from 'node:path';
import dagre from './vendor/dagre.esm.js';

const VBW = 1664, PAD = 30, ZP = { side: 24, top: 56, bottom: 24 };
const KIND = {
  b: { mk: 'ah-b', label: '동기 호출' },
  o: { mk: 'ah-o', label: '이벤트' },
  g: { mk: 'ahg', label: '보조·연계' },
  r: { mk: 'ah-open', dash: '8 8', cls: 'g', label: '응답' },   // 응답선: 회색 점선 + open 화살촉
};
const ICON_COLOR = { paper: 'var(--ink)', blue: 'var(--blue)', orange: 'var(--accent)' };
const FAM_CLASS = { paper: 'k-paper', blue: 'k-blue', orange: 'k-orange' };
const STATE_ICON = { ok: ['정상', 'var(--blue)'], warn: ['주의', 'var(--accent)'], down: ['장애', 'var(--accent)'], degraded: ['저하', 'var(--accent)'] };
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function fail(msg) { console.error(`FAIL: ${msg}`); process.exit(1); }
const HELP = `arch_layout.mjs — semantic JSON → svg.dg 아키텍처 슬라이드 생성기
usage: node scripts/arch_layout.mjs MODEL.json [-o SLIDE.html] [--coords OUT.json] [--svg-only] [--quiet]
  MODEL.json  semantic JSON(nodes·edges·zones·states·legend·title·notes — 파일 헤더 스키마 참조)
  -o          슬라이드 단편 출력 파일(기본 stdout)
  --coords    좌표·waypoint JSON을 이 파일에도 기록
  --svg-only  <section> 없이 <svg class="dg"> 단편만 출력
  --quiet     요약 출력 생략
필요: node 18+, vendor/dagre.esm.js(@dagrejs/dagre@3.1.3, MIT) — 빌드 시점 전용`;

/* ── 진입 ── */
const argv = process.argv.slice(2);
if (argv.includes('--help') || argv.includes('-h') || !argv.length) { console.log(HELP); process.exit(argv.length ? 0 : 1); }
const input = argv.find((a) => !a.startsWith('-'));
const opt = (k) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : null; };
if (!input || !fs.existsSync(input)) fail(`입력 파일 없음: ${input || '(없음)'}`);
const model = JSON.parse(fs.readFileSync(input, 'utf8'));
const outSlide = opt('-o') || opt('--out');
const outCoords = opt('--coords');
const svgOnly = argv.includes('--svg-only');
const quiet = argv.includes('--quiet');

const L = model.layout || {};
const STEP = { zones: 1, nodes: 2, edges: 3, ...(model.steps || {}) };
const NODES = {};
const TPL_DEF = {
  card: { w: 152, h: 140 },
  equip: { w: 96, h: 88 },
  cluster: { w: 220, h: 150 },
  'rack-group': { w: 300, h: 96 },
};
for (const n of model.nodes || []) {
  if (!n.id || !n.name) fail(`node에 id/name 필요: ${JSON.stringify(n)}`);
  const tpl = n.template || 'card';
  if (!TPL_DEF[tpl]) fail(`node ${n.id}: 알 수 없는 template ${tpl}`);
  NODES[n.id] = { shape: 'card', fam: 'paper', icon: null, role: '', template: tpl, ...TPL_DEF[tpl], ...n };
}
// 버스 — 수평 백본 + T-드롭. 같은 from×to 점대점 엣지는 버스가 대신 그린다.
const BUSES = (model.buses || []).map((b, i) => {
  for (const id of [...(b.from || []), ...(b.to || [])])
    if (!NODES[id]) fail(`buses[${i}]: 알 수 없는 노드 ${id}`);
  if (!(b.from || []).length || !(b.to || []).length) fail(`buses[${i}]: from·to 모두 필요`);
  if (b.style && !['trunk', 'san', 'lan'].includes(b.style)) fail(`buses[${i}]: 알 수 없는 style ${b.style}`);
  return { id: b.id || `bus${i}`, label: b.label || '', from: b.from, to: b.to, y: b.y, style: b.style || 'trunk', step: b.step };
});
const busPairs = new Set(BUSES.flatMap((b) => b.from.flatMap((f) => b.to.map((t) => `${f}→${t}`))));
// ALL_EDGES = dagre 랭크 제약용(버스가 대신 그리는 쌍도 배치에는 살린다)
// EDGES = 방출용(버스 중복 점대점 자동 제거)
const ALL_EDGES = (model.edges || []).map((e, i) => {
  if (!NODES[e.from] || !NODES[e.to]) fail(`edge ${i}: 알 수 없는 노드 ${e.from}→${e.to}`);
  if (!KIND[e.kind || 'b']) fail(`edge ${i}: 알 수 없는 kind ${e.kind}`);
  return { a: e.from, b: e.to, label: e.label || '', kind: e.kind || 'b', flow: !!e.flow, step: e.step, aux: !!e.aux };
});
const EDGES = ALL_EDGES.filter((e) => !busPairs.has(`${e.a}→${e.b}`));
// 버스 연결도 배치 제약으로 준다 — from 노드가 to 노드보다 위쪽 랭크에 오도록
const edgeSet = new Set(ALL_EDGES.map((e) => `${e.a}→${e.b}`));
for (const b of BUSES) for (const f of b.from) for (const t of b.to)
  if (!edgeSet.has(`${f}→${t}`)) ALL_EDGES.push({ a: f, b: t, label: '', kind: 'b', aux: true, busRef: true });
const HAPAIRS = (model.haPairs || []).map((p, i) => {
  if (!Array.isArray(p) || p.length < 2 || !NODES[p[0]] || !NODES[p[1]]) fail(`haPairs[${i}]: 노드 2개 필요`);
  return { a: p[0], b: p[1], label: p[2] || '' };
});
const ZONES = (model.zones || []).map((z) => ({ ...z }));
for (const z of ZONES) {
  if (z.between) continue;                       // 경계선 존 — 멤버 없음
  const kids = ZONES.some((q) => q.parent === z.id);
  if ((!z.members || !z.members.length) && !kids) fail(`zone ${z.id}: members·하위존·between 중 하나 필요`);
  for (const m of z.members || []) if (!NODES[m]) fail(`zone ${z.id}: 알 수 없는 노드 ${m}`);
}
for (const z of ZONES) {
  if (!z.parent) continue;
  const p = ZONES.find((q) => q.id === z.parent);
  if (!p || p.between) fail(`zone ${z.id}: 알 수 없는 parent ${z.parent}`);
}
const DRAW_EDGES = EDGES.filter((e) => !e.aux);
// 버스·HA는 예산 밖 — 고밀도 연결은 cap 상향이 아니라 버스 구조로 표현한다(개편 계약).
if (DRAW_EDGES.length > 12) fail(`링크 ${DRAW_EDGES.length}개 > 12(draw 예산) — 장을 나눌 것(aux·버스는 예산 밖)`);

/* ── 1. dagre 배치 ── */
const g = new dagre.graphlib.Graph({ multigraph: true });
g.setGraph({ rankdir: L.dir || 'LR', nodesep: L.nodesep ?? 48, ranksep: L.ranksep ?? 96, edgesep: L.edgesep ?? 0, align: L.align, marginx: 0, marginy: 0 });
g.setDefaultEdgeLabel(() => ({}));
for (const [id, d] of Object.entries(NODES)) g.setNode(id, { width: d.w, height: d.h });
ALL_EDGES.forEach((e, i) => { if (!e.aux || e.busRef) g.setEdge(e.a, e.b, { label: e.label, width: 40, height: 30, labelpos: 'c' }, `e${i}`); });
// 배치 전용 힌트 간선 — 그리지 않고 예산에도 안 들린다(존 침범 방지용 랭크 pushed)
for (const [i, h] of (model.hints || []).entries()) {
  if (!NODES[h.from] || !NODES[h.to]) fail(`hints[${i}]: 알 수 없는 노드 ${h.from}→${h.to}`);
  g.setEdge(h.from, h.to, { minlen: h.minlen ?? 1, weight: h.weight ?? 1 }, `h${i}`);
}
dagre.layout(g);

const nodes = Object.fromEntries(Object.entries(NODES).map(([id, d]) => {
  const v = g.node(id);
  return [id, { cx: v.x, cy: v.y, ...d }];
}));
const nRect = (n) => ({ x0: n.cx - n.w / 2, x1: n.cx + n.w / 2, y0: n.cy - n.h / 2, y1: n.cy + n.h / 2 + (n.shape === 'circle' ? 34 : 0) });
// HA 쌍 마주보는 면의 최소 간격 — 배지(원 r10 + 라벨 여유)가 들어갈 44px를 확보한다.
// 부족하면 면 기준 아래/오른쪽 노드를 밀고, 연쇄 충돌 노드도 같은 규칙으로 민다(결정적 fixpoint).
const HA_GAP = 44;
const axisOf = (ra, rb) => (rb.x0 > ra.x1 || rb.x1 < ra.x0) ? 'x' : 'y';
const overlapOn = (r, q, ax) => ax === 'y' ? Math.min(r.x1, q.x1) - Math.max(r.x0, q.x0) : Math.min(r.y1, q.y1) - Math.max(r.y0, q.y0);
for (let round = 0; round < 4; round++) {
  let changed = false;
  for (const p of HAPAIRS) {
    const a = nodes[p.a], b = nodes[p.b];
    const ax = axisOf(nRect(a), nRect(b));
    const [lo, hi] = ax === 'y' ? (a.cy < b.cy ? [a, b] : [b, a]) : (a.cx < b.cx ? [a, b] : [b, a]);
    const gap = ax === 'y' ? nRect(hi).y0 - nRect(lo).y1 : nRect(hi).x0 - nRect(lo).x1;
    if (gap >= HA_GAP) continue;
    const shove = (n, d) => {
      if (ax === 'y') n.cy += d; else n.cx += d;
      const r = nRect(n);
      for (const q of Object.values(nodes)) {
        if (q === n) continue;
        const qr = nRect(q);
        const behind = ax === 'y' ? qr.y0 >= r.y0 - 2 && qr.y0 < r.y1 + HA_GAP / 2 : qr.x0 >= r.x0 - 2 && qr.x0 < r.x1 + HA_GAP / 2;
        if (overlapOn(r, qr, ax) > 20 && behind)
          shove(q, (ax === 'y' ? r.y1 + HA_GAP / 2 - qr.y0 : r.x1 + HA_GAP / 2 - qr.x0));
      }
    };
    shove(hi, HA_GAP - gap);
    changed = true;
  }
  if (!changed) break;
}
// aux 엣지는 dagre에 넣지 않는다(레이아웃 비구동 정적 보조선) — 두 노드 상자 경계를 잇되,
// 직선이 다른 노드 사각형과 교차하면 직교(elbow) 채널로 우회한다.
// 결정성: 우회 후보는 고정 순서로 평가하고 첫 번째 무교차 후보를 택한다(시간·난수 없음).
const clip = (to, n) => {
  const dx = to.x - n.cx, dy = to.y - n.cy;
  const t = Math.min(dx ? (n.w / 2) / Math.abs(dx) : 1e9, dy ? (n.h / 2) / Math.abs(dy) : 1e9);
  return { x: n.cx + dx * t, y: n.cy + dy * t };
};
const AUX_M = 10;                                        // 우회 시 노드와의 최소 이격
const auxSegRect = (p, q, r) => {
  const inside = (v) => v.x > r.x0 && v.x < r.x1 && v.y > r.y0 && v.y < r.y1;
  if (inside(p) || inside(q)) return true;
  const ccw = (a, b, c) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
  const crosses = (a, b, c, d) => ccw(a, b, c) * ccw(a, b, d) < 0 && ccw(c, d, a) * ccw(c, d, b) < 0;
  const c = [{ x: r.x0, y: r.y0 }, { x: r.x1, y: r.y0 }, { x: r.x1, y: r.y1 }, { x: r.x0, y: r.y1 }];
  return c.some((v, i) => crosses(p, q, v, c[(i + 1) % 4]));
};
const auxClear = (pts, skip) => {
  const rs = Object.keys(nodes).filter((id) => !skip.has(id)).map((id) => {
    const r = nRect(nodes[id]);
    return { x0: r.x0 - AUX_M, y0: r.y0 - AUX_M, x1: r.x1 + AUX_M, y1: r.y1 + AUX_M };
  });
  for (let i = 1; i < pts.length; i++)
    for (const r of rs) if (auxSegRect(pts[i - 1], pts[i], r)) return false;
  return true;
};
// 맨해튼 직교 라우팅 — 포트는 상대편을 향하는 면 중점(수평·수직 세그먼트만).
// dagre 웨이포인트 사선은 쓰지 않는다(원본 대조 분석: SI 도식은 100% 직교).
const portOf = (a, b) => {
  const ra = nRect(a), rb = nRect(b);
  if (rb.x0 > ra.x1) return { x: ra.x1, y: a.cy };                    // b 가 오른쪽
  if (rb.x1 < ra.x0) return { x: ra.x0, y: a.cy };                    // b 가 왼쪽
  return rb.y0 > ra.y1 ? { x: a.cx, y: ra.y1 } : { x: a.cx, y: ra.y0 }; // 위·아래
};
const orthoRoute = (ea, eb, lane = 0) => {
  const fa = nodes[ea], fb = nodes[eb], skip = new Set([ea, eb]);
  const p0 = portOf(fa, fb), p1 = portOf(fb, fa);
  const lanesX = [], lanesY = [];
  for (const [id, n] of Object.entries(nodes)) {
    if (skip.has(id)) continue;
    const r = nRect(n);
    lanesX.push(r.x0 - AUX_M - 4, r.x1 + AUX_M + 4);
    lanesY.push(r.y0 - AUX_M - 4, r.y1 + AUX_M + 4);
  }
  const ux = [...new Set(lanesX)].sort((a, b) => a - b), uy = [...new Set(lanesY)].sort((a, b) => a - b);
  const shx = (x) => lane ? x + lane : x, shy = (y) => lane ? y + lane : y;
  const tryC = (mid) => {
    const pts = [p0, ...mid, p1];
    // 축 정렬이 아닌 세그먼트는 후보에서 배제(순수 직교 보장)
    for (let i = 1; i < pts.length; i++)
      if (Math.abs(pts[i].x - pts[i - 1].x) > 0.5 && Math.abs(pts[i].y - pts[i - 1].y) > 0.5) return null;
    return auxClear(pts, skip) ? pts : null;
  };
  const cands = [
    [[], [{ x: p0.x, y: p1.y }], [{ x: p1.x, y: p0.y }]],
    ux.map((x) => [{ x: shx(x), y: p0.y }, { x: shx(x), y: p1.y }]),
    uy.map((y) => [{ x: p0.x, y: shy(y) }, { x: p1.x, y: shy(y) }]),
    ux.flatMap((x) => uy.map((y) => [{ x: shx(x), y: p0.y }, { x: shx(x), y: shy(y) }, { x: p1.x, y: shy(y) }])),
    uy.flatMap((y) => ux.map((x) => [{ x: p0.x, y: shy(y) }, { x: shx(x), y: shy(y) }, { x: shx(x), y: p1.y }])),
  ];
  for (const group of cands) for (const c of group) { const p = tryC(c); if (p) return p; }
  return [p0, { x: p1.x, y: p0.y }, p1];                            // 최종 폴백 — L자 직교
};
const edges = EDGES.map((e, i) => {
  // 병렬 쌍(a→b·b→a)은 가운데 차선을 ±edgesep/2 만큼 벌려 겹침 방지
  const pair = EDGES.findIndex((q, j) => j !== i && q.a === e.b && q.b === e.a);
  const sep = (L.edgesep ?? 24) / 2;
  const lane = pair < 0 ? 0 : pair < i ? sep : -sep;
  return { ...e, pts: orthoRoute(e.a, e.b, lane) };
});

/* ── 2. 정규화: 존 패딩 포함 전체 bbox → 1664 폭·여백 안 가운데 ── */
const zoneRects = ZONES.filter((z) => !z.between);
const bounds = ZONES.filter((z) => z.between);
// 중첩 존 — 자식 먼저 상자를 구하고 부모는 자식 상자를 포함하는 bbox.
// 깊이 제한 3단계(대권역→서브존→랙 열) — 그 이상은 FAIL.
const depthOf = (z, seen = new Set()) => {
  if (!z.parent) return 0;
  if (seen.has(z.id)) fail(`zone ${z.id}: parent 순환`);
  seen.add(z.id);
  const p = zoneRects.find((q) => q.id === z.parent);
  return 1 + depthOf(p, seen);
};
for (const z of zoneRects) if (depthOf(z) > 2) fail(`zone ${z.id}: 중첩 ${depthOf(z) + 1}단계 > 3단계`);
const zoneBox = (z) => {
  const p = { ...ZP, ...(z.pad || {}) };
  const hs = z.headerStyle;
  // 솔리드 헤더 바 32px + 라벨 띠(48px)는 노드가 못 들어오게 패딩으로 확보한다
  const top = hs ? Math.max(p.top, 40)
    : z.label && z.labelPos !== 'bottom' ? Math.max(p.top, 48) : p.top;
  const bottom = !hs && z.label && z.labelPos === 'bottom' ? Math.max(p.bottom, 48) : p.bottom;
  const rs = (z.members || []).map((m) => nRect(nodes[m]));
  const kids = zoneRects.filter((q) => q.parent === z.id);
  const all = [...rs, ...kids.map((k) => k.r)];
  return { x0: Math.min(...all.map((r) => r.x0)) - p.side, x1: Math.max(...all.map((r) => r.x1)) + p.side,
           y0: Math.min(...all.map((r) => r.y0)) - top, y1: Math.max(...all.map((r) => r.y1)) + bottom };
};
for (const z of [...zoneRects].sort((a, b) => depthOf(b) - depthOf(a))) z.r = zoneBox(z);
const zones = [...zoneRects].sort((a, b) => depthOf(a) - depthOf(b));   // 방출은 부모 먼저
// 격자 스냅 — 같은 부모(또는 최상위끼리) 존의 외곽을 맞춘다. 가로 나열이면
// y0·y1, 세로 나열이면 x0·x1 통일. z.snap:false 면 제외.
for (const key of new Set(zones.map((z) => z.parent || ' top'))) {
  const grp = zones.filter((z) => (z.parent || ' top') === key && z.snap !== false);
  if (grp.length < 2) continue;
  const xs = grp.map((z) => z.r.x0).sort((a, b) => a - b);
  const ys = grp.map((z) => z.r.y0).sort((a, b) => a - b);
  // 나열 방향 추정 — 시작 좌표가 서로 다른 축이 나열축
  const xSpread = xs[xs.length - 1] - xs[0], ySpread = ys[ys.length - 1] - ys[0];
  if (xSpread >= ySpread) {                        // 가로 나열 → 상하 맞춤
    const y0 = Math.min(...grp.map((z) => z.r.y0)), y1 = Math.max(...grp.map((z) => z.r.y1));
    for (const z of grp) { z.r.y0 = y0; z.r.y1 = y1; }
  } else {                                         // 세로 나열 → 좌우 맞춤
    const x0 = Math.min(...grp.map((z) => z.r.x0)), x1 = Math.max(...grp.map((z) => z.r.x1));
    for (const z of grp) { z.r.x0 = x0; z.r.x1 = x1; }
  }
}
// 스냅으로 늘어난 자식에 맞춰 부모 상자만 다시 계산한다(자식의 스냅 결과는 유지)
for (const z of [...zones].sort((a, b) => depthOf(b) - depthOf(a)))
  if (zoneRects.some((q) => q.parent === z.id)) z.r = zoneBox(z);
const zmap = Object.fromEntries(zones.map((z) => [z.id, z]));
for (const b of bounds) {
  for (const zid of b.between) if (zid && !zmap[zid]) fail(`boundary ${b.id || b.label}: 알 수 없는 존 ${zid}`);
}
// 버스 기하 — TB: 수평 백본 + 수직 T-드롭 / LR: 수직 백본 + 수평 T-드롭.
// 백본은 from·to 사이 빈 공간의 가운데(모델 y/x 지정 시 그 값). 드롭은 노드 중심축에 맞춘다.
const busGeom = BUSES.map((b) => {
  const fR = b.from.map((id) => nRect(nodes[id])), tR = b.to.map((id) => nRect(nodes[id]));
  const lr = (L.dir || 'LR') === 'LR';
  if (lr) {
    const fx = Math.max(...fR.map((r) => r.x1)), tx = Math.min(...tR.map((r) => r.x0));
    const bx = (b.x ?? (fx + tx) / 2);
    const ys = [...b.from, ...b.to].map((id) => nodes[id].cy);
    return { ...b, vert: true, bx, y0: Math.min(...ys) - 24, y1: Math.max(...ys) + 24,
             ups: b.from.map((id) => ({ y: nodes[id].cy, x0: nRect(nodes[id]).x1, x1: bx })),
             downs: b.to.map((id) => ({ y: nodes[id].cy, x0: bx, x1: nRect(nodes[id]).x0 })) };
  }
  const fy = Math.max(...fR.map((r) => r.y1)), ty = Math.min(...tR.map((r) => r.y0));
  const by = b.y ?? (fy + ty) / 2;
  const xs = [...b.from, ...b.to].map((id) => nodes[id].cx);
  return { ...b, by, x0: Math.min(...xs) - 24, x1: Math.max(...xs) + 24,
           ups: b.from.map((id) => ({ x: nodes[id].cx, y0: nRect(nodes[id]).y1, y1: by })),
           downs: b.to.map((id) => ({ x: nodes[id].cx, y0: by, y1: nRect(nodes[id]).y0 })) };
});
// HA 이중화 쌍 — 두 노드의 마주보는 면 사이 이중 실선(═). 세로 나열이면 수평 이중선.
const haGeom = HAPAIRS.map((p) => {
  const ra = nRect(nodes[p.a]), rb = nRect(nodes[p.b]);
  const horiz = rb.x0 > ra.x1 || rb.x1 < ra.x0;
  const [s, e2] = horiz
    ? [rb.x0 > ra.x1 ? { x: ra.x1, y: nodes[p.a].cy } : { x: ra.x0, y: nodes[p.a].cy },
       rb.x0 > ra.x1 ? { x: rb.x0, y: nodes[p.b].cy } : { x: rb.x1, y: nodes[p.b].cy }]
    : [rb.y0 > ra.y1 ? { x: nodes[p.a].cx, y: ra.y1 } : { x: nodes[p.a].cx, y: ra.y0 },
       rb.y0 > ra.y1 ? { x: nodes[p.b].cx, y: rb.y0 } : { x: nodes[p.b].cx, y: rb.y1 }];
  // 배지 점유 영역 — 칩 라벨이 배지 자리에 앉으면 배지 글자가 칩 상자에 페어링돼
  // 'SVG 글자 넘침' 오류가 난다. overlaps() 의 장애물로 쓴다.
  const mx = (s.x + e2.x) / 2, my = (s.y + e2.y) / 2;
  const labW = p.label ? p.label.length * 17 + 20 : 0;
  const badgeBox = horiz
    ? { x0: mx - 14 - labW / 2, x1: mx + 14 + labW / 2, y0: my - 32, y1: my + 14 }
    : { x0: mx - 14, x1: mx + 14 + labW, y0: my - 14, y1: my + 14 };
  return { ...p, s, e: e2, horiz, badgeBox };
});
// 범례: 명시 우선, 없고 사용 kind 2종↑이면 자동 유도
const legBar = model.legendStyle === 'bar' || model.legend === 'bar';
const usedKinds = [...new Set(EDGES.map((e) => e.kind))];
const legendItems = Array.isArray(model.legend) && model.legend.length ? model.legend
  : legBar && Array.isArray(model.legendItems) && model.legendItems.length ? model.legendItems
  : usedKinds.length >= 2 ? ['b', 'r', 'o', 'g'].filter((k) => usedKinds.includes(k))
      .map((k) => ({ kind: k, label: KIND[k].label })) : [];
let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
const eat = (x0, y0, x1, y1) => { minX = Math.min(minX, x0); minY = Math.min(minY, y0); maxX = Math.max(maxX, x1); maxY = Math.max(maxY, y1); };
for (const n of Object.values(nodes)) { const r = nRect(n); eat(r.x0, r.y0, r.x1, r.y1); }
for (const z of zones) eat(z.r.x0, z.r.y0, z.r.x1, z.r.y1);
for (const e of edges) for (const p of e.pts) eat(p.x, p.y, p.x, p.y);
for (const b of busGeom) b.vert ? eat(b.bx, b.y0, b.bx, b.y1) : eat(b.x0, b.by, b.x1, b.by);
for (const h of haGeom) eat(h.s.x, h.s.y, h.e.x, h.e.y);
const contentW = maxX - minX, H = maxY - minY + PAD * 2 + (legendItems.length ? (legBar ? 72 : 56) : 0);
if (contentW + PAD * 2 > VBW) fail(`내용 폭 ${(contentW + PAD * 2).toFixed(0)} > ${VBW} — 노드·랭크를 줄이거나 장 분할`);
const tx = (VBW - contentW) / 2 - minX, ty = PAD - minY;
const X = (v) => +(v + tx).toFixed(1), Y = (v) => +(v + ty).toFixed(1);
const r2 = (n) => +n.toFixed(1);

/* ── 3. 경로·라벨 기하 ── */
function pathOf(pts, r) {
  // 연속 중복점(0길이 세그먼트)은 코너 라운딩이 0/0으로 NaN을 낸다 — 방출 전 제거
  pts = pts.filter((p, i) => !i || Math.abs(p.x - pts[i - 1].x) > 0.5 || Math.abs(p.y - pts[i - 1].y) > 0.5);
  let d = `M${r2(X(pts[0].x))} ${r2(Y(pts[0].y))}`;
  for (let i = 1; i < pts.length; i++) {
    const p = pts[i], q = pts[i - 1], nx = pts[i + 1];
    if (!nx) { d += ` L${r2(X(p.x))} ${r2(Y(p.y))}`; break; }
    const l1 = Math.hypot(p.x - q.x, p.y - q.y), l2 = Math.hypot(nx.x - p.x, nx.y - p.y);
    const k = Math.min(r, l1 / 2, l2 / 2);
    const a = [p.x - ((p.x - q.x) / l1) * k, p.y - ((p.y - q.y) / l1) * k];
    const c = [p.x + ((nx.x - p.x) / l2) * k, p.y + ((nx.y - p.y) / l2) * k];
    d += ` L${r2(X(a[0]))} ${r2(Y(a[1]))} Q${r2(X(p.x))} ${r2(Y(p.y))} ${r2(X(c[0]))} ${r2(Y(c[1]))}`;
  }
  return d;
}
function midPoint(pts) {
  const segs = []; let tot = 0;
  for (let i = 1; i < pts.length; i++) { const l = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y); segs.push(l); tot += l; }
  let half = tot / 2;
  for (let i = 0; i < segs.length; i++) {
    if (half > segs[i]) { half -= segs[i]; continue; }
    const t = segs[i] ? half / segs[i] : 0, a = pts[i], b = pts[i + 1];
    return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
  }
  return pts[0];
}
// 기배치 라벨 칩 bbox — 칩끼리의 상호 충돌은 항상 회피한다(agy 이슈-5: 알약끼리
// 겹치는 것 자체가 결함). layout.chipAvoid 는 레거시 플래그로 남기되 기본 켜짐과 같다.
const placedChips = [];
const hit = (r, b) => r.x0 < b.x1 && r.x1 > b.x0 && r.y0 < b.y1 && r.y1 > b.y0;
const grow = (b, m) => ({ x0: b.x0 - m, x1: b.x1 + m, y0: b.y0 - m, y1: b.y1 + m });
// 다른 엣지의 선분·화살촉도 칩 장애물로 본다(기본 동작 — 정확성 문제다).
// 칩이 자기 선 위에 앉는 것은 종이 배경이 가려주므로 허용하고, 남의 선·화살촉과
// 겹치면 우선순위 후보 순서대로 비껴 앉는다. 결정성: 후보 순서 고정.
const SEG_M = 7, CAP_M = 15;                                 // 선분 여유 · 화살촉 영역
const segBox = (p, q, m) => ({ x0: Math.min(p.x, q.x) - m, x1: Math.max(p.x, q.x) + m,
                               y0: Math.min(p.y, q.y) - m, y1: Math.max(p.y, q.y) + m });
const capBox = (p, m) => ({ x0: p.x - m, x1: p.x + m, y0: p.y - m, y1: p.y + m });
const overlaps = (r, own) => Object.values(nodes).some((n) => hit(r, grow(nRect(n), 4)))
  || zones.some((z) => {
    // 존 라벨 영역(띠 48px, labelPos 방향)도 회피 — 칩이 존 이름 위에 올라가지 않게
    const b = z.labelPos === 'bottom'
      ? { x0: z.r.x0, x1: z.r.x1, y0: z.r.y1 - 48, y1: z.r.y1 }
      : { x0: z.r.x0, x1: z.r.x1, y0: z.r.y0, y1: z.r.y0 + 48 };
    return hit(r, b);
  }) || haGeom.some((h) => hit(r, h.badgeBox))
  || edges.some((e, i) => i !== own && (
    e.pts.some((p, k) => k > 0 && hit(r, segBox(e.pts[k - 1], p, SEG_M)))
    || hit(r, capBox(e.pts[e.pts.length - 1], CAP_M))
  ))
  // 기본 규칙: 나중 칩이 먼저 칩의 글자 앵커(중심)를 덮으면 검사기가 그 칩을 상자로
  // 읽어 “글자 넘침”이 된다 — 앵커 커버는 칩Avoid 옵션과 무관하게 항상 금지.
  || placedChips.some((b) => hit(r, { x0: b.ax - 3, x1: b.ax + 3, y0: b.ay - 3, y1: b.ay + 3 }))
  || placedChips.some((b) => hit(r, b));
// 라벨 칩은 svg·범례 영역 안에 있어야 한다 — 정규화 좌표로 검사
const legH = legendItems.length ? (legBar ? 72 : 56) : 0;
const inBox = (r) => X(r.x0) >= 2 && X(r.x1) <= VBW - 2 && Y(r.y0) >= 2 && Y(r.y1) <= H - 2 - legH;
// 칩 회랑(corridor) — 회피 오프셋은 컨테이너/캔버스 경계 안에서만 굴린다.
// 두 끝점이 속한 존 rect ∪ 엣지 자체 bbox 의 외접 상자를 +10 여유로 쓴다
// (agy 이슈-6: 존 밖 허공으로 밀려나 화살표에서 분리되는 회귀 방지).
const corridorOf = (e) => {
  const zs = zones.filter((z) => z.members.includes(e.a) || z.members.includes(e.b)).map((z) => z.r);
  const ex = e.pts.map((p) => p.x), ey = e.pts.map((p) => p.y);
  const bb = { x0: Math.min(...ex), x1: Math.max(...ex), y0: Math.min(...ey), y1: Math.max(...ey) };
  const parts = [...zs, bb];
  return { x0: Math.min(...parts.map((r) => r.x0)) - 10, x1: Math.max(...parts.map((r) => r.x1)) + 10,
           y0: Math.min(...parts.map((r) => r.y0)) - 10, y1: Math.max(...parts.map((r) => r.y1)) + 10 };
};
const labelPos = (e, idx) => {
  const m = midPoint(e.pts), w = e.label.length * 17 + 30, corr = corridorOf(e);
  const inside = (r) => r.x0 >= corr.x0 && r.x1 <= corr.x1 && r.y0 >= corr.y0 && r.y1 <= corr.y1;
  const pair = edges.findIndex((q) => q.a === e.b && q.b === e.a);
  const off = pair >= 0 && pair < idx ? 26 : pair >= 0 ? -26 : 0;
  const grid = (gate) => {
    for (const dy of [off, off - 34, off + 34, off - 68, off + 68, off - 102, off + 102, -136, 136]) {
      for (const dx of [0, -44, 44, -88, 88, -132, 132, -176, 176]) {
        const r = { x0: m.x + dx - w / 2, x1: m.x + dx + w / 2, y0: m.y - 18 + dy, y1: m.y + 18 + dy };
        if (inBox(r) && gate(r) && !overlaps(r, idx)) { placedChips.push({ ...r, ax: m.x + dx, ay: m.y + dy }); return { x: m.x + dx, y: m.y + dy, w }; }
      }
    }
    return null;
  };
  // 1차 — 회랑 안 후보 / 2차 — 회랑 해제(캔버스 안 빈 자리) / 3차 — 회랑 조밀 스캔.
  // 폴백도 장애물을 피해야 한다: 장애물을 무시하고 눌러 앉은 칩은 노드 글자·존 라벨·
  // 다른 칩을 덮어 “상자 밖 넘침” 검사 오류와 시각 결함을 만든다.
  const found = grid(inside)
    || grid(() => true)
    || (() => {
      for (let y = corr.y0 + 18; y <= corr.y1 - 18; y += 40)
        for (let x = corr.x0 + w / 2; x <= corr.x1 - w / 2; x += 44) {
          const r = { x0: x - w / 2, x1: x + w / 2, y0: y - 18, y1: y + 18 };
          if (inBox(r) && !overlaps(r, idx)) { placedChips.push({ ...r, ax: x, ay: y }); return { x, y, w }; }
        }
      return null;
    })();
  if (found) return found;
  const ly = Math.min(Math.max(m.y + off, minY - PAD + 22), maxY + PAD - 22 - legH);
  const lx = Math.min(Math.max(m.x, minX - PAD + w / 2 + 4), maxX + PAD - w / 2 - 4);
  placedChips.push({ x0: lx - w / 2, x1: lx + w / 2, y0: ly - 18, y1: ly + 18, ax: lx, ay: ly });  // fallback 도 등록 — 다음 칩이 겹치지 않게
  return { x: lx, y: ly, w };
};

/* ── 4. 방출 ── */
const zoneMarkup = (z) => {
  // headerStyle — 엔지니어링 블루프린트 존 표기:
  //   solid-navy/solid-blue = 상단 32px 솔리드 헤더 바 + 흰 굵은 라벨
  //   tinted = 아이스블루 면 + 좌상단 솔리드 캡슐 라벨(2단계 서브존용)
  // kind member=면색 소속 띠 · trust·미지정=점선 상자(신뢰 경계)
  const W = r2(z.r.x1 - z.r.x0), HH = r2(z.r.y1 - z.r.y0), zy = Y(z.r.y0);
  if (z.headerStyle) {
    const solid = z.headerStyle !== 'tinted';
    const barCls = z.headerStyle === 'solid-blue' ? 'k-zbar-b' : 'k-zbar-n';
    const face = solid ? 'k-zface' : 'k-zface-t';
    const lw = (z.label || '').length * 17 + 8;
    // 캡슐은 면 안에 들어가야 한다 — 면 밖으로 넘친 캡슐은 이웃 글자 앵커를 삼켜
    // 'SVG 글자 넘침' 오류를 만든다. 면이 캡슐보다 좁으면 캡슐 없이 글자만 둔다.
    const capW = lw + 20, capFits = capW + 8 <= W;
    const capX = capFits ? Math.min(z.r.x0 + 12, z.r.x1 - capW - 4) : z.r.x0;
    const label = solid
      ? `<rect class="${barCls}" x="${X(z.r.x0)}" y="${zy}" width="${W}" height="32" style="rx:10px"/><text class="k-t-zh" x="${X(z.r.x0 + 16)}" y="${zy + 23}">${esc(z.label)}</text>`
      : (capFits
        ? `<rect class="k-zbar-n" x="${X(capX)}" y="${zy + 6}" width="${r2(capW)}" height="28" style="rx:14px"/><text class="k-t-zh" x="${X(capX + 22)}" y="${zy + 26}">${esc(z.label)}</text>`
        : `<text class="k-t-zh" x="${X(z.r.x0 + 10)}" y="${zy + 26}">${esc(z.label)}</text>`);
    return `<g data-step="${z.step ?? STEP.zones}">
    <rect class="${face}" x="${X(z.r.x0)}" y="${zy}" width="${W}" height="${HH}" style="rx:12px"/>
    ${label}
  </g>`;
  }
  const rect = z.kind === 'member'
    ? `<rect class="k-paper" x="${X(z.r.x0)}" y="${Y(z.r.y0)}" width="${W}" height="${HH}" style="rx:12px;fill-opacity:${z.opacity ?? .55}"/>`
    : `<rect class="k-frame" x="${X(z.r.x0)}" y="${Y(z.r.y0)}" width="${W}" height="${HH}" style="rx:12px"/>`;
  // 존 라벨이 멤버/외부 노드 위에 앉으면 띠 안에서 비켜 찍는다
  // (agy 이슈-5: 원형 노드가 컨테이너 제목을 가리는 결함). 선호 띠에
  // 자리가 없으면 반대 띠로 보낸다.
  const lw = z.label.length * 15 + 8;
  const freeX = (y0, y1) => {
    for (let x = z.r.x0 + 16; x + lw <= z.r.x1 - 8; x += 40) {
      const r = { x0: x - 4, x1: x + lw + 4, y0: y0 + 6, y1: y1 - 6 };
      if (!Object.values(nodes).some((n) => hit(r, nRect(n)))) return x;
    }
    return null;
  };
  const spots = z.labelPos === 'bottom'
    ? [[z.r.y1 - 48, z.r.y1, Y(z.r.y1 - 14)], [z.r.y0, z.r.y0 + 48, Y(z.r.y0 + 34)]]
    : [[z.r.y0, z.r.y0 + 48, Y(z.r.y0 + 34)], [z.r.y1 - 48, z.r.y1, Y(z.r.y1 - 14)]];
  let lx = z.r.x0 + 16, ly = spots[0][2];
  for (const [y0, y1, lyv] of spots) {
    const x = freeX(y0, y1);
    if (x !== null) { lx = x; ly = lyv; break; }
  }
  return `<g data-step="${z.step ?? STEP.zones}">
    ${rect}
    <text class="k-t-tag" x="${X(lx)}" y="${ly}">${esc(z.label)}</text>
  </g>`;
};

// 존 사이 경계선 — 점선 세로 polyline + 라벨(상하 클램프). between:[a]면 a의 바깥쪽
// labelAt:'top'|'bottom'(기본 bottom) — 아래쪽이 노드 라벨과 겹칠 때 모델에서만 전환한다.
// 라벨이 선 구간 안에 들면 선을 라벨 위·아래로 쪼갠다 — 점선이 글자를 관통하면
// '신뢰|경계' 처럼 읽히다 끊겨 보인다(크리틱 기술-1 근본 패치).
const boundMarkup = (b) => {
  const a = zmap[b.between[0]], c = b.between[1] ? zmap[b.between[1]] : null;
  // 수평 경계 — 위아래로 쌓인 두 존(TB 배치) 사이에는 가로 점선을 그린다
  if (c && a.r.y1 < c.r.y0 - 2 || c && c.r.y1 < a.r.y0 - 2) {
    const [t, bt] = a.r.y1 < c.r.y0 ? [a.r, c.r] : [c.r, a.r];
    const hy = (t.y1 + bt.y0) / 2, hx0 = Math.min(t.x0, bt.x0) - 10, hx1 = Math.max(t.x1, bt.x1) + 10;
    const lx = b.labelAt === 'top' ? hx0 + 40 : hx1 - 40;
    const seg = (xa, xb) => (xb - xa > 4)
      ? `\n    <polyline points="${r2(X(xa))},${r2(Y(hy))} ${r2(X(xb))},${r2(Y(hy))}" fill="none" stroke="var(--accent)" stroke-width="3.5" stroke-dasharray="11 9"/>` : '';
    const lw = (b.label || '신뢰 경계').length * 15 + 20;
    const inSpan = lx - lw / 2 < hx1 && lx + lw / 2 > hx0;
    const lines = inSpan ? seg(hx0, lx - lw / 2 - 12) + seg(lx + lw / 2 + 12, hx1) : seg(hx0, hx1);
    return `<g data-step="${b.step ?? STEP.zones}">${lines}
    <text class="k-t-tag" x="${r2(X(lx))}" y="${r2(Y(hy) + 8)}" text-anchor="middle" style="fill:var(--accent)">${esc(b.label || '신뢰 경계')}</text>
  </g>`;
  }
  let x, y0, y1;
  if (c) {
    const [l, rr] = a.r.x0 < c.r.x0 ? [a.r, c.r] : [c.r, a.r];
    x = (l.x1 + rr.x0) / 2;
    y0 = Math.min(a.r.y0, c.r.y0) - 10; y1 = Math.max(a.r.y1, c.r.y1) + 10;
  } else {
    x = a.r.x0 - 22; y0 = a.r.y0 - 10; y1 = a.r.y1 + 10;
  }
  const ly = b.labelAt === 'top'
    ? Math.min(Math.max(y0 - 8, minY - PAD + 26), y1)
    : Math.min(Math.max(y1 + 18, y0 + 22), maxY + PAD - 4);
  const line = (ya, yb) => (yb - ya > 4)
    ? `\n    <polyline points="${r2(X(x))},${r2(Y(ya))} ${r2(X(x))},${r2(Y(yb))}" fill="none" stroke="var(--accent)" stroke-width="3.5" stroke-dasharray="11 9"/>`
    : '';
  // 라벨 글자 밴드(±안전 여유)가 선 구간에 걸치면 선을 라벨 위·아래로 쪼갠다
  const inSpan = ly > y0 - 12 && ly - 20 < y1 + 12;
  const lines = inSpan ? line(y0, ly - 26) + line(ly + 22, y1) : line(y0, y1);
  return `<g data-step="${b.step ?? STEP.zones}">${lines}
    <text class="k-t-tag" x="${r2(X(x))}" y="${r2(Y(ly))}" text-anchor="middle" style="fill:var(--accent)">${esc(b.label || '신뢰 경계')}</text>
  </g>`;
};

const stateChips = (id, n, x, y) => {
  // states[]: node.at 시점에 칩 교체 — 이전 칩 data-until=at-1, 새 칩 data-step=at
  // text/stateText 는 칩 문구를 역할(예 "Active·운영")로 구분하는 덮어쓰기다.
  const trans = (model.states || []).filter((s) => s.node === id).sort((p, q) => p.at - q.at);
  if (!n.state && !trans.length) return '';
  const chain = [{ at: 0, state: n.state || 'ok', text: n.stateText }, ...trans];
  return chain.map((c, i) => {
    const next = chain[i + 1];
    const vis = i === 0 ? (next ? ` data-until="${next.at - 1}"` : '') : ` data-step="${c.at}"${next ? ` data-until="${next.at - 1}"` : ''}`;
    const [txt, col] = STATE_ICON[c.state] || STATE_ICON.ok;
    const label = c.text || txt;
    return `<g${vis}><circle cx="${x}" cy="${y}" r="9" style="fill:${col}"/><text class="k-t-tag" x="${x + 15}" y="${y + 7}">${esc(label)}</text></g>`;
  }).join('\n    ');
};

const nodeMarkup = (id, n) => {
  const o = [`<g data-step="${n.step ?? STEP.nodes}">`];
  const x = X(n.cx - n.w / 2), y = Y(n.cy - n.h / 2);
  if (n.template === 'equip') {
    // 장비 소자 96×88 — 아이콘 36 + 15px 굵은 장비명 + 13px spec + 우상단 수량 배지
    // h<78 소형: 아이콘 22(y+5)로 축소하고 이름·spec 베이스라인을 아래로 — 아이콘 하단이 장비명 글리프를 덮지 않게
    const eqS = n.h < 78, isz = eqS ? 22 : 36;
    o.push(`<rect class="${FAM_CLASS[n.fam]}" x="${x}" y="${y}" width="${n.w}" height="${n.h}" style="rx:8px"/>`);
    if (n.icon) o.push(`<use aria-hidden="true" href="#${n.icon}" x="${r2(x + n.w / 2 - isz / 2)}" y="${r2(y + (eqS ? 5 : 8))}" width="${isz}" height="${isz}" style="color:${ICON_COLOR[n.fam]}"/>`);
    o.push(`<text class="k-t-eq" x="${r2(x + n.w / 2)}" y="${r2(y + n.h - (n.spec ? (eqS ? 23 : 26) : (eqS ? 14 : 16)))}" text-anchor="middle">${esc(n.name)}</text>`);
    if (n.spec) o.push(`<text class="k-t-spec" x="${r2(x + n.w / 2)}" y="${r2(y + n.h - (eqS ? 6 : 9))}" text-anchor="middle">${esc(n.spec)}</text>`);
    if (n.qty != null && n.qty > 1) o.push(`<g class="k-qty"><circle cx="${r2(x + n.w - 12)}" cy="${r2(y + 12)}" r="10"/><text class="k-t-qty" x="${r2(x + n.w - 12)}" y="${r2(y + 16.5)}" text-anchor="middle">${n.qty > 99 ? '99+' : n.qty}</text></g>`);
    o.push(stateChips(id, n, x + 8, y - 10));
  } else if (n.template === 'cluster') {
    // 클러스터 220×150 — 헤더 28 + 내부 미니칩 격자(2×2 또는 1×3) + 하단 자원 바
    const items = (n.subitems || []).slice(0, 4);
    const cols = items.length > 3 ? 2 : items.length;                 // ≤3이면 1행
    const rows = Math.ceil(items.length / cols) || 1;
    const barH = n.res != null ? 20 : 0;
    const gridH = n.h - 32 - barH - 10;
    o.push(`<rect class="k-clus" x="${x}" y="${y}" width="${n.w}" height="${n.h}" style="rx:10px"/>`);
    o.push(`<rect class="k-clus-hd" x="${x}" y="${y}" width="${n.w}" height="30" style="rx:10px"/>`);
    o.push(`<text class="k-t-zh" x="${r2(x + 12)}" y="${r2(y + 21)}">${esc(n.name)}</text>`);
    const cw = (n.w - 24 - (cols - 1) * 8) / cols, ch = Math.min(30, (gridH - (rows - 1) * 8) / rows);
    items.forEach((it, i) => {
      const cx = x + 12 + (i % cols) * (cw + 8), cy = y + 38 + Math.floor(i / cols) * (ch + 8);
      o.push(`<rect class="k-chip" x="${r2(cx)}" y="${r2(cy)}" width="${r2(cw)}" height="${r2(ch)}" style="rx:6px"/><text class="k-t-spec" x="${r2(cx + cw / 2)}" y="${r2(cy + ch / 2 + 5)}" text-anchor="middle">${esc(it)}</text>`);
    });
    if (n.res != null) {
      // % 라벨은 막대 오른쪽에 둔다 — 막대 안에 넣으면 앵커가 얇은 채움 막대(k-res-f)를
      // 상자로 읽혀 “글자 넘침”이 되고, 채움 위 글자는 대비도 애매해진다.
      const bw = n.w - 24 - 46, fy = y + n.h - 26, fv = Math.max(0, Math.min(100, n.res));
      o.push(`<rect class="k-res" x="${r2(x + 12)}" y="${r2(fy)}" width="${bw}" height="14" style="rx:7px"/>`);
      if (fv > 0) o.push(`<rect class="k-res-f" x="${r2(x + 12)}" y="${r2(fy)}" width="${r2(bw * fv / 100)}" height="14" style="rx:7px"/>`);
      o.push(`<text class="k-t-spec" x="${r2(x + 12 + bw + 8)}" y="${r2(fy + 11.5)}">${fv}%</text>`);
    }
    o.push(stateChips(id, n, x + 12, y - 10));
  } else if (n.template === 'rack-group') {
    // 랙 그룹 300×96 — 같은 종류 소형 장비 2~4대 가로 나열 + #1·#2·#3 라벨
    const units = (n.items && n.items.length ? n.items : [n.name]).slice(0, 4);
    const uw = (n.w - 20 - (units.length - 1) * 10) / units.length;
    o.push(`<rect class="k-clus" x="${x}" y="${y}" width="${n.w}" height="${n.h}" style="rx:10px"/>`);
    units.forEach((u, i) => {
      const ux = x + 10 + i * (uw + 10), uy = y + 8, uh = n.h - 32;
      o.push(`<rect class="${FAM_CLASS[n.fam]}" x="${r2(ux)}" y="${r2(uy)}" width="${r2(uw)}" height="${r2(uh)}" style="rx:6px"/>`);
      if (n.icon) o.push(`<use aria-hidden="true" href="#${n.icon}" x="${r2(ux + uw / 2 - 14)}" y="${r2(uy + 6)}" width="28" height="28" style="color:${ICON_COLOR[n.fam]}"/>`);
      o.push(`<text class="k-t-spec" x="${r2(ux + uw / 2)}" y="${r2(uy + uh - 8)}" text-anchor="middle">#${i + 1}</text>`);
      if (typeof u === 'string' && u !== n.name) o.push(`<title>${esc(u)}</title>`);
    });
    o.push(`<text class="k-t-spec" x="${r2(x + n.w / 2)}" y="${r2(y + n.h - 7)}" text-anchor="middle">${esc(n.name)}${n.spec ? ` · ${esc(n.spec)}` : ''}</text>`);
    o.push(stateChips(id, n, x + 10, y - 10));
  } else if (n.shape === 'circle') {
    o.push(`<circle class="${FAM_CLASS[n.fam]}" cx="${X(n.cx)}" cy="${Y(n.cy)}" r="${n.w / 2}"/>`);
    if (n.icon) o.push(`<use aria-hidden="true" href="#${n.icon}" x="${X(n.cx - 22)}" y="${Y(n.cy - 30)}" width="44" height="44" style="color:${ICON_COLOR[n.fam]}"/>`);
    o.push(`<text class="k-t-tag" x="${X(n.cx)}" y="${Y(n.cy + 34)}" text-anchor="middle" style="fill:${ICON_COLOR[n.fam]}">${esc(n.name)}</text>`);
    if (n.role) o.push(`<text class="k-t-tag" x="${X(n.cx)}" y="${Y(n.cy + n.h / 2 + 26)}" text-anchor="middle">${esc(n.role)}</text>`);
    o.push(stateChips(id, n, X(n.cx - n.w / 2), Y(n.cy - n.h / 2 - 16)));
  } else {
    const x = X(n.cx - n.w / 2), y = Y(n.cy - n.h / 2);
    o.push(`<rect class="${FAM_CLASS[n.fam]}" x="${x}" y="${y}" width="${n.w}" height="${n.h}" style="rx:9px"/>`);
    // 상태 칩이 있으면 칩 좌상단·아이콘 우상단의 헤더 행으로 나눈다(겹침 방지)
    const hasState = n.state || (model.states || []).some((s) => s.node === id);
    // 글자 세로 배치는 노드 높이에서 비롯한다 — h=100 처럼 낮은 상자에 96/124 고정
    // 오프셋을 쓰면 글자가 밑단에 밀착하거나 상자 밖으로 빠진다(기술 결함의 근본 원인).
    // 아이콘은 h<124 에서 40px 로 줄여 아이콘+이름+역할 3줄이 상자 안에 든다.
    const iconS = !n.icon ? 0 : n.h >= 124 ? 48 : 40;
    if (n.icon) o.push(`<use aria-hidden="true" href="#${n.icon}" x="${r2(hasState ? x + n.w - 16 - iconS : x + n.w / 2 - iconS / 2)}" y="${y + 16}" width="${iconS}" height="${iconS}" style="color:${ICON_COLOR[n.fam]}"/>`);
    const nameY = n.icon ? y + 16 + iconS + 24 : y + Math.round(n.h * 0.52);
    o.push(`<text class="t-l" x="${r2(x + n.w / 2)}" y="${r2(nameY)}" text-anchor="middle">${esc(n.name)}</text>`);
    if (n.role) o.push(`<text class="k-t-tag" x="${r2(x + n.w / 2)}" y="${r2(nameY + 28)}" text-anchor="middle">${esc(n.role)}</text>`);
    o.push(stateChips(id, n, x + 16, y + 16));
  }
  o.push('</g>');
  return o.filter(Boolean).join('\n    ');
};

const edgeMarkup = (e, idx) => {
  const k = KIND[e.kind], cls = `k-ln-${k.cls || e.kind}${e.flow ? ' dash-flow' : ''}`;
  const dash = k.dash ? ` stroke-dasharray="${k.dash}"` : '';
  const o = [e.aux ? '<g>' : `<g data-step="${e.step ?? STEP.edges}">`,
    `  <path class="${cls}" d="${pathOf(e.pts, 12)}"${dash} marker-end="url(#${k.mk})"/>`];
  if (e.label) {
    const lp = labelPos(e, idx);
    o.push(`  <rect class="k-paper" x="${r2(X(lp.x - lp.w / 2))}" y="${r2(Y(lp.y - 18))}" width="${lp.w}" height="36" style="rx:9px"/>`);
    o.push(`  <text class="k-t-tag" x="${r2(X(lp.x))}" y="${r2(Y(lp.y) + 8)}" text-anchor="middle">${esc(e.label)}</text>`);
  }
  o.push('</g>');
  return o.join('\n    ');
};

const busMarkup = (b) => {
  // 트렁크 백본 + T-드롭(드롭은 draw 예산 밖 — 버스는 고밀도 연결의 기구)
  const cls = `k-bus-${b.style}`;
  const seg = (x0, y0, x1, y1) => `<polyline class="${cls}" points="${r2(X(x0))},${r2(Y(y0))} ${r2(X(x1))},${r2(Y(y1))}"/>`;
  if (b.vert) {
    const drops = [...b.ups.map((d) => seg(d.x0, d.y, d.x1, d.y)), ...b.downs.map((d) => seg(d.x0, d.y, d.x1, d.y))];
    const dots = [...b.ups, ...b.downs].map((d) => `<circle class="${cls}-dot" cx="${r2(X(b.bx))}" cy="${r2(Y(d.y))}" r="4"/>`);
    const lab = b.label ? `<text class="k-t-spec" x="${r2(X(b.bx) + 8)}" y="${r2(Y(b.y0) + 12)}">${esc(b.label)}</text>` : '';
    return `<g${b.step != null ? ` data-step="${b.step}"` : ` data-step="${STEP.edges}"`}>${seg(b.bx, b.y0, b.bx, b.y1)}\n    ${drops.join('\n    ')}\n    ${dots.join('')}${lab}</g>`;
  }
  const drops = [...b.ups.map((d) => seg(d.x, d.y0, d.x, d.y1)), ...b.downs.map((d) => seg(d.x, d.y0, d.x, d.y1))];
  const dots = [...b.ups, ...b.downs].map((d) => `<circle class="${cls}-dot" cx="${r2(X(d.x))}" cy="${r2(Y(b.by))}" r="4"/>`);
  const lab = b.label ? `<text class="k-t-spec" x="${r2(X((b.x0 + b.x1) / 2))}" y="${r2(Y(b.by) - 8)}" text-anchor="middle">${esc(b.label)}</text>` : '';
  return `<g${b.step != null ? ` data-step="${b.step}"` : ` data-step="${STEP.edges}"`}>${seg(b.x0, b.by, b.x1, b.by)}\n    ${drops.join('\n    ')}\n    ${dots.join('')}${lab}</g>`;
};
const haMarkup = (h) => {
  // HA 이중화 — 이중 실선 + 중점 하트비트 마커(작은 원 + 'HA')
  const off = h.horiz ? { dx: 0, dy: 4 } : { dx: 4, dy: 0 };
  const seg = (d) => `<line class="k-ha" x1="${r2(X(h.s.x + d.dx))}" y1="${r2(Y(h.s.y + d.dy))}" x2="${r2(X(h.e.x + d.dx))}" y2="${r2(Y(h.e.y + d.dy))}"/>`;
  const mx = (h.s.x + h.e.x) / 2, my = (h.s.y + h.e.y) / 2;
  return `<g data-step="${STEP.edges}">${seg({ dx: -off.dx, dy: -off.dy })}${seg(off)}
    <g class="k-hab"><circle cx="${r2(X(mx))}" cy="${r2(Y(my))}" r="10"/><text class="k-t-qty" x="${r2(X(mx))}" y="${r2(Y(my) + 3.5)}" text-anchor="middle">HA</text></g>${h.label ? `<text class="k-t-spec" x="${r2(X(mx) + (h.horiz ? 0 : 14))}" y="${r2(Y(my) - (h.horiz ? 14 : -4))}" text-anchor="${h.horiz ? 'middle' : 'start'}">${esc(h.label)}</text>` : ''}</g>`;
};

const legendMarkup = (items) => {
  if (!items || !items.length) return '';
  const bar = model.legendStyle === 'bar' || model.legend === 'bar';
  const items2 = bar && Array.isArray(model.legendItems) ? model.legendItems : items;
  let x = PAD + 4;
  if (bar) {
    // 하단 전폭 범례 바 — 선 종류 + 장비 미니 아이콘 + 상태 배지(new/replaced/existing)
    const y0 = H - 64;
    const segs = items2.map((it) => {
      let seg;
      if (it.icon) { seg = `<use aria-hidden="true" href="#${it.icon}" x="${r2(x)}" y="${r2(y0 + 10)}" width="30" height="30" style="color:var(--blue)"/><text class="k-t-tag" x="${r2(x + 40)}" y="${r2(y0 + 32)}">${esc(it.label)}</text>`; x += 40 + it.label.length * 24 + 56; }
      else if (it.badge) {
        const bc = { new: 'var(--amber, #d97706)', replaced: 'var(--coral, #dc2626)', existing: 'var(--mut)' }[it.badge] || 'var(--mut)';
        seg = `<rect x="${r2(x)}" y="${r2(y0 + 12)}" width="34" height="24" rx="12" fill="${bc}"/><text class="k-t-tag" x="${r2(x + 44)}" y="${r2(y0 + 32)}">${esc(it.label)}</text>`;
        x += 44 + it.label.length * 24 + 56;
      } else if (it.fam) {
        const cls = FAM_CLASS[it.fam] || 'k-paper';
        seg = `<rect class="${cls}" x="${r2(x)}" y="${r2(y0 + 12)}" width="36" height="26" style="rx:8px"/><text class="k-t-tag" x="${r2(x + 48)}" y="${r2(y0 + 32)}">${esc(it.label)}</text>`;
        x += 48 + it.label.length * 24 + 56;
      } else {
        const kk = KIND[it.kind] || { mk: 'ahg' };
        const kd = kk.dash ? ` stroke-dasharray="${kk.dash}"` : '';
        seg = `<polyline class="k-ln-${kk.cls || it.kind}"${kd} points="${x},${r2(y0 + 26)} ${x + 70},${r2(y0 + 26)}"/><text class="k-t-tag" x="${r2(x + 84)}" y="${r2(y0 + 32)}">${esc(it.label)}</text>`;
        x += 84 + it.label.length * 24 + 56;
      }
      return seg;
    });
    return `<g><rect class="k-legbar" x="0" y="${r2(y0)}" width="${VBW}" height="56"/>${segs.join('\n    ')}</g>`;
  }
  return `<g>${items.map((it) => {
    if (it.fam) {                                  // 노드 색 의미 스토치 — 선 범례 옆에 함께
      const cls = FAM_CLASS[it.fam] || 'k-paper';
      const seg = `<rect class="${cls}" x="${r2(x)}" y="${r2(H - 52)}" width="36" height="26" style="rx:8px"/><text class="k-t-tag" x="${x + 48}" y="${r2(H - 32)}">${esc(it.label)}</text>`;
      x += 48 + it.label.length * 24 + 60;
      return seg;
    }
    const kk = KIND[it.kind] || { mk: 'ahg' };
    const kd = kk.dash ? ` stroke-dasharray="${kk.dash}"` : '';
    const seg = `<polyline class="k-ln-${kk.cls || it.kind}"${kd} points="${x},${r2(H - 40)} ${x + 70},${r2(H - 40)}"/><text class="k-t-tag" x="${x + 84}" y="${r2(H - 32)}">${esc(it.label)}</text>`;
    x += 84 + it.label.length * 24 + 60;
    return seg;
  }).join('\n    ')}</g>`;
};

const svg = `<svg class="dg" data-lint="svg-diagram" viewBox="0 0 ${VBW} ${Math.ceil(H)}" role="img" aria-label="${esc(model.ariaLabel || model.title || '아키텍처 구성도')}">
  <title>${esc(model.titleSvg || model.title || '아키텍처 구성도')}</title>
  ${zones.map(zoneMarkup).join('\n  ')}${bounds.length ? '\n  ' + bounds.map(boundMarkup).join('\n  ') : ''}
  ${edges.map(edgeMarkup).join('\n  ')}
  ${busGeom.map(busMarkup).join('\n  ')}${haGeom.length ? '\n  ' + haGeom.map(haMarkup).join('\n  ') : ''}
  ${Object.entries(nodes).map(([id, n]) => nodeMarkup(id, n)).join('\n  ')}
  ${legendMarkup(legendItems)}
</svg>`;

// 우측 인수인계 카드 열(선택) — 도식이 작아 여백이 남는 장의 리듬 변주.
// 폭은 260px 로 고정: 도식 칸이 1392px 이상 확보돼야 svg 글자가 화면에서
// 18px 하한(22px × 1392/1664 = 18.4px)을 지킨다. 인라인 스타일 + 토큰만 쓴다.
const handoverMarkup = (hv) => {
  if (!hv) return null;
  const cards = (hv.points || []).map((p) => `      <div style="border:2px solid var(--line);border-left:8px solid var(--blue);border-radius:12px;background:var(--paper);padding:12px 16px">
        <p style="margin:0;font-size:24px;font-weight:800;color:var(--ink)">${esc(p.t)}</p>
        <p style="margin:6px 0 0;font-size:22px;line-height:1.4;color:var(--soft)">${esc(p.d)}</p>
      </div>`).join('\n');
  return `<div style="display:flex;gap:12px;align-items:center;flex:1;min-height:0">
  <div style="flex:1;min-width:0">
  ${svg}
  </div>
  <div style="flex:0 0 260px;display:flex;flex-direction:column;gap:12px">
    <p class="eyebrow" style="margin:0">${esc(hv.title)}</p>
${cards}
  </div>
</div>`;
};
const duo = handoverMarkup(model.handover);

// 우측 스펙 패널(선택) — 도식 폭의 ~24% 를 쓰는 BOM·핵심 목록·스택 요약 열.
// 도식과 상하가 같은 라인에 정렬된다(블루프린트 원본 도식의 스펙 시트 레이아웃).
const sidePanelMarkup = (sp) => {
  if (!sp) return null;
  const sec = (s) => {
    if (s.columns && s.rows) {
      return `<div class="arch-side-blk"><p class="arch-side-h">${esc(s.t)}</p><table class="arch-side-tb"><thead><tr>${s.columns.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${s.rows.map((r) => `<tr>${r.map((c) => `<td>${esc(String(c))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    }
    if (s.items) return `<div class="arch-side-blk"><p class="arch-side-h">${esc(s.t)}</p><ul class="arch-side-ul">${s.items.map((it) => `<li>${esc(it)}</li>`).join('')}</ul></div>`;
    return s.text ? `<div class="arch-side-blk"><p class="arch-side-h">${esc(s.t)}</p><p class="arch-side-p">${esc(s.text)}</p></div>` : '';
  };
  return `<div style="display:flex;gap:16px;align-items:stretch;flex:1;min-height:0">
  <div style="flex:1;min-width:0">
  ${svg}
  </div>
  <aside class="arch-side">
    ${sp.eyebrow ? `<p class="eyebrow" style="margin:0 0 4px">${esc(sp.eyebrow)}</p>` : ''}
    ${sp.title ? `<p class="arch-side-t">${esc(sp.title)}</p>` : ''}
${(sp.sections || []).map(sec).join('\n')}
  </aside>
</div>`;
};
const side = sidePanelMarkup(model.sidePanel);

// theme:'blueprint' → .arch-blueprint · chrome:'blueprint' → 1행 컴팩트 헤더
const bp = model.theme === 'blueprint';
const head = model.chrome === 'blueprint'
  ? `<div class="bp-head"><span class="bp-serial">${esc(model.serial || '000')}</span><h2 class="title">${esc(model.title || '')}</h2><span class="bp-eyebrow">${esc(model.eyebrow || '아키텍처 구성도')}</span></div>`
  : `<div class="head"><p class="eyebrow">${esc(model.eyebrow || '가상 예시 · 아키텍처')}</p><h2 class="title">${esc(model.title || '')}</h2></div>`;

const slide = `<section class="slide${bp ? ' arch-blueprint' : ''}" data-archetype="arch-diagram" style="gap:${duo || side ? 14 : 20}px">
  ${head}
  ${duo || side || svg}
  ${model.small ? `<p class="small">${esc(model.small)}</p>` : ''}
  <aside class="notes">${esc(model.notes || '')}</aside>
</section>
`;

const payload = svgOnly ? svg + '\n' : slide;
if (outSlide) fs.writeFileSync(outSlide, payload); else process.stdout.write(payload);
if (outCoords) {
  fs.writeFileSync(outCoords, JSON.stringify({
    viewBox: [0, 0, VBW, Math.ceil(H)],
    nodes: Object.fromEntries(Object.entries(nodes).map(([k, n]) => [k, { x: X(n.cx), y: Y(n.cy), w: n.w, h: n.h }])),
    edges: edges.map((e) => ({ a: e.a, b: e.b, pts: e.pts.map((p) => ({ x: X(p.x), y: Y(p.y) })) })),
    zones: zones.map((z) => ({ id: z.id, r: { x0: X(z.r.x0), y0: Y(z.r.y0), x1: X(z.r.x1), y1: Y(z.r.y1) } })),
  }, null, 2) + '\n');
}
if (!quiet) console.error(`viewBox 0 0 ${VBW} x ${Math.ceil(H)} · contentW=${contentW.toFixed(0)} · paths=${(svg.match(/<path/g) || []).length} · nodes=${Object.keys(nodes).length} edges=${edges.length}`);
