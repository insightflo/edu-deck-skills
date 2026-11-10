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
 *               fam:"paper|blue|orange", w, h, step? }]
 *   edges  : [{ from, to, label, kind:"b|o|g|r", flow?:bool, step?, aux?:bool }]
 *             kind b=동기(k-ln-b) o=이벤트(k-ln-o) g=보조(k-ln-g) r=응답(k-ln-g+점선+ah-open);
 *             flow→dash-flow 입자 · aux→data-step 없는 정적 보조선(draw 예산·dagre 배치 밖,
 *             두 노드 사이 직선 — 랭크 제약을 주고 싶지 않은 보조 경로에 사용)
 *   zones  : [{ id, label, members:[id…], kind:"member|trust", labelPos:"top|bottom",
 *               pad:{top,bottom,side}, step? }] member=k-paper 면색 띠(소속) ·
 *             trust·미지정=k-frame 점선(신뢰 경계) · pad는 존별 여백 덮어쓰기
 *             between:[zoneA,zoneB?] 멤버 대신 두 존 사이의 경계선(점선 polyline+라벨)
 *   states : [{ node, at, state:"ok|warn|down", text? }]  상태 칩 교체 — 이전 칩
 *             data-until=at-1, 새 칩 data-step=at(failover 시나리오 §4.7).
 *             node.state는 초기 칩, node.stateText 는 초기 칩 문구 덮어쓰기.
 *             text 는 칩 글자를 역할 문구(예 "Active·운영")로 구분할 때 쓴다.
 *   legend : [{ kind:"b|o|g|r", label } | { fam:"blue|orange|paper|gray", label }]
 *             선 어휘 범례 1줄 — 생략하고 사용 kind가 2종 이상이면 자동 유도
 *             (기본 라벨 b:동기 호출 o:이벤트 g:보조·연계 r:응답).
 *             fam 항목은 노드 색 의미(예 주황=경계 장비)를 선 범례 옆에 함께 찍는다.
 *   handover : { title, points:[{t,d}] }  우측 인수인계 카드 열 — 있으면 도식 70% +
 *             카드 30% 2단 구성. 도식이 작고 여백이 남는 장의 리듬 변주용.
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
for (const n of model.nodes || []) {
  if (!n.id || !n.name) fail(`node에 id/name 필요: ${JSON.stringify(n)}`);
  NODES[n.id] = { w: 152, h: 140, shape: 'card', fam: 'paper', icon: null, role: '', ...n };
}
const EDGES = (model.edges || []).map((e, i) => {
  if (!NODES[e.from] || !NODES[e.to]) fail(`edge ${i}: 알 수 없는 노드 ${e.from}→${e.to}`);
  if (!KIND[e.kind || 'b']) fail(`edge ${i}: 알 수 없는 kind ${e.kind}`);
  return { a: e.from, b: e.to, label: e.label || '', kind: e.kind || 'b', flow: !!e.flow, step: e.step, aux: !!e.aux };
});
const ZONES = (model.zones || []).map((z) => ({ ...z }));
for (const z of ZONES) {
  if (z.between) continue;                       // 경계선 존 — 멤버 없음
  if (!z.members || !z.members.length) fail(`zone ${z.id}: members 또는 between 필요`);
  for (const m of z.members) if (!NODES[m]) fail(`zone ${z.id}: 알 수 없는 노드 ${m}`);
}
const DRAW_EDGES = EDGES.filter((e) => !e.aux);
if (DRAW_EDGES.length > 12) fail(`링크 ${DRAW_EDGES.length}개 > 12(draw 예산) — 장을 나눌 것(aux:true는 예산 밖)`);

/* ── 1. dagre 배치 ── */
const g = new dagre.graphlib.Graph({ multigraph: true });
g.setGraph({ rankdir: L.dir || 'LR', nodesep: L.nodesep ?? 48, ranksep: L.ranksep ?? 96, edgesep: L.edgesep ?? 0, marginx: 0, marginy: 0 });
g.setDefaultEdgeLabel(() => ({}));
for (const [id, d] of Object.entries(NODES)) g.setNode(id, { width: d.w, height: d.h });
EDGES.forEach((e, i) => { if (!e.aux) g.setEdge(e.a, e.b, { label: e.label, width: 40, height: 30, labelpos: 'c' }, `e${i}`); });
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
const auxRoute = (ea, eb) => {
  const fa = nodes[ea], fb = nodes[eb], skip = new Set([ea, eb]);
  const straight = [clip({ x: fb.cx, y: fb.cy }, fa), clip({ x: fa.cx, y: fa.cy }, fb)];
  if (auxClear(straight, skip)) return straight;
  const blockers = Object.keys(nodes).filter((id) => !skip.has(id)).map((id) => nRect(nodes[id]));
  if (!blockers.length) return straight;
  // 차선 후보 — 각 블로커 사각형 바깥 변에서 만드는 직교 통로(안쪽 틈 + 바깥쪽 모두 포함).
  // 정렬된 좌표를 고정 순서로 순회하므로 결정적이다.
  const lanesX = [...new Set(blockers.flatMap((r) => [r.x0 - AUX_M - 4, r.x1 + AUX_M + 4]))].sort((p, q) => p - q);
  const lanesY = [...new Set(blockers.flatMap((r) => [r.y0 - AUX_M - 4, r.y1 + AUX_M + 4]))].sort((p, q) => p - q);
  const degenerate = (c) => c.some((v) => [fa, fb].some((n) => Math.abs(v.x - n.cx) < 0.5 && Math.abs(v.y - n.cy) < 0.5));
  const tryC = (c) => {
    if (degenerate(c)) return null;
    const pts = [clip(c[0], fa), ...c, clip(c[c.length - 1], fb)];
    return auxClear(pts, skip) ? pts : null;
  };
  // 단순 → 복합 순: L자 → V-H-V·H-V-H → 갭 차선을 쓰는 5점 훅
  const cands = [
    [[{ x: fb.cx, y: fa.cy }], [{ x: fa.cx, y: fb.cy }]],
    lanesX.map((x) => [{ x, y: fa.cy }, { x, y: fb.cy }]),
    lanesY.map((y) => [{ x: fa.cx, y }, { x: fb.cx, y }]),
    lanesX.flatMap((x) => lanesY.map((y) => [{ x, y: fa.cy }, { x, y }, { x: fb.cx, y }])),
    lanesY.flatMap((y) => lanesX.map((x) => [{ x: fa.cx, y }, { x, y }, { x, y: fb.cy }])),
  ];
  for (const group of cands) for (const c of group) { const p = tryC(c); if (p) return p; }
  return straight;                                             // 최종 폴백 — 직선 유지
};
const edges = EDGES.map((e, i) => {
  if (!e.aux) return { ...e, pts: g.edge(e.a, e.b, `e${i}`).points.map((p) => ({ x: p.x, y: p.y })) };
  return { ...e, pts: auxRoute(e.a, e.b) };
});

/* ── 2. 정규화: 존 패딩 포함 전체 bbox → 1664 폭·여백 안 가운데 ── */
const zoneBox = (z) => {
  const p = { ...ZP, ...(z.pad || {}) };
  // 라벨이 앉는 띠(48px)는 노드가 못 들어오게 패딩으로 확보한다
  const top = z.label && z.labelPos !== 'bottom' ? Math.max(p.top, 48) : p.top;
  const bottom = z.label && z.labelPos === 'bottom' ? Math.max(p.bottom, 48) : p.bottom;
  const rs = z.members.map((m) => nRect(nodes[m]));
  return { x0: Math.min(...rs.map((r) => r.x0)) - p.side, x1: Math.max(...rs.map((r) => r.x1)) + p.side,
           y0: Math.min(...rs.map((r) => r.y0)) - top, y1: Math.max(...rs.map((r) => r.y1)) + bottom };
};
const zoneRects = ZONES.filter((z) => !z.between);
const bounds = ZONES.filter((z) => z.between);
const zones = zoneRects.map((z) => ({ ...z, r: zoneBox(z) }));
const zmap = Object.fromEntries(zones.map((z) => [z.id, z]));
for (const b of bounds) {
  for (const zid of b.between) if (zid && !zmap[zid]) fail(`boundary ${b.id || b.label}: 알 수 없는 존 ${zid}`);
}
// 범례: 명시 우선, 없고 사용 kind 2종↑이면 자동 유도
const usedKinds = [...new Set(EDGES.map((e) => e.kind))];
const legendItems = (model.legend && model.legend.length) ? model.legend
  : usedKinds.length >= 2 ? ['b', 'r', 'o', 'g'].filter((k) => usedKinds.includes(k))
      .map((k) => ({ kind: k, label: KIND[k].label })) : [];
let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
const eat = (x0, y0, x1, y1) => { minX = Math.min(minX, x0); minY = Math.min(minY, y0); maxX = Math.max(maxX, x1); maxY = Math.max(maxY, y1); };
for (const n of Object.values(nodes)) { const r = nRect(n); eat(r.x0, r.y0, r.x1, r.y1); }
for (const z of zones) eat(z.r.x0, z.r.y0, z.r.x1, z.r.y1);
for (const e of edges) for (const p of e.pts) eat(p.x, p.y, p.x, p.y);
const contentW = maxX - minX, H = maxY - minY + PAD * 2 + (legendItems.length ? 56 : 0);
if (contentW + PAD * 2 > VBW) fail(`내용 폭 ${(contentW + PAD * 2).toFixed(0)} > ${VBW} — 노드·랭크를 줄이거나 장 분할`);
const tx = (VBW - contentW) / 2 - minX, ty = PAD - minY;
const X = (v) => +(v + tx).toFixed(1), Y = (v) => +(v + ty).toFixed(1);
const r2 = (n) => +n.toFixed(1);

/* ── 3. 경로·라벨 기하 ── */
function pathOf(pts, r) {
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
  }) || edges.some((e, i) => i !== own && (
    e.pts.some((p, k) => k > 0 && hit(r, segBox(e.pts[k - 1], p, SEG_M)))
    || hit(r, capBox(e.pts[e.pts.length - 1], CAP_M))
  ))
  // 기본 규칙: 나중 칩이 먼저 칩의 글자 앵커(중심)를 덮으면 검사기가 그 칩을 상자로
  // 읽어 “글자 넘침”이 된다 — 앵커 커버는 칩Avoid 옵션과 무관하게 항상 금지.
  || placedChips.some((b) => hit(r, { x0: b.ax - 3, x1: b.ax + 3, y0: b.ay - 3, y1: b.ay + 3 }))
  || placedChips.some((b) => hit(r, b));
// 라벨 칩은 svg·범례 영역 안에 있어야 한다 — 정규화 좌표로 검사
const legH = legendItems.length ? 56 : 0;
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
  for (const dy of [off, off - 34, off + 34, off - 68, off + 68, off - 102, off + 102]) {
    for (const dx of [0, -44, 44, -88, 88, -132, 132, -176, 176]) {
      const r = { x0: m.x + dx - w / 2, x1: m.x + dx + w / 2, y0: m.y - 18 + dy, y1: m.y + 18 + dy };
      if (inBox(r) && inside(r) && !overlaps(r, idx)) { placedChips.push({ ...r, ax: m.x + dx, ay: m.y + dy }); return { x: m.x + dx, y: m.y + dy, w }; }
    }
  }
  const ly = Math.min(Math.max(m.y + off, minY - PAD + 22), maxY + PAD - 22 - legH);
  const lx = Math.min(Math.max(m.x, minX - PAD + w / 2 + 4), maxX + PAD - w / 2 - 4);
  placedChips.push({ x0: lx - w / 2, x1: lx + w / 2, y0: ly - 18, y1: ly + 18, ax: lx, ay: ly });  // fallback 도 등록 — 다음 칩이 겹치지 않게
  return { x: lx, y: ly, w };
};

/* ── 4. 방출 ── */
const zoneMarkup = (z) => {
  // kind member=면색 소속 띠 · trust·미지정=점선 상자(신뢰 경계). labelPos로 라벨 방향 선택
  const rect = z.kind === 'member'
    ? `<rect class="k-paper" x="${X(z.r.x0)}" y="${Y(z.r.y0)}" width="${r2(z.r.x1 - z.r.x0)}" height="${r2(z.r.y1 - z.r.y0)}" style="rx:12px;fill-opacity:${z.opacity ?? .55}"/>`
    : `<rect class="k-frame" x="${X(z.r.x0)}" y="${Y(z.r.y0)}" width="${r2(z.r.x1 - z.r.x0)}" height="${r2(z.r.y1 - z.r.y0)}" style="rx:12px"/>`;
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
  if (n.shape === 'circle') {
    o.push(`<circle class="${FAM_CLASS[n.fam]}" cx="${X(n.cx)}" cy="${Y(n.cy)}" r="${n.w / 2}"/>`);
    if (n.icon) o.push(`<use href="#${n.icon}" x="${X(n.cx - 22)}" y="${Y(n.cy - 30)}" width="44" height="44" style="color:${ICON_COLOR[n.fam]}"/>`);
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
    if (n.icon) o.push(`<use href="#${n.icon}" x="${r2(hasState ? x + n.w - 16 - iconS : x + n.w / 2 - iconS / 2)}" y="${y + 16}" width="${iconS}" height="${iconS}" style="color:${ICON_COLOR[n.fam]}"/>`);
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

const legendMarkup = (items) => {
  if (!items || !items.length) return '';
  let x = PAD + 4;
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

const svg = `<svg class="dg" viewBox="0 0 ${VBW} ${Math.ceil(H)}" role="img" aria-label="${esc(model.ariaLabel || model.title || '아키텍처 구성도')}">
  <title>${esc(model.titleSvg || model.title || '아키텍처 구성도')}</title>
  ${zones.map(zoneMarkup).join('\n  ')}${bounds.length ? '\n  ' + bounds.map(boundMarkup).join('\n  ') : ''}
  ${edges.map(edgeMarkup).join('\n  ')}
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

const slide = `<section class="slide" data-archetype="arch-diagram" style="gap:${duo ? 14 : 20}px">
  <div class="head"><p class="eyebrow">${esc(model.eyebrow || '가상 예시 · 아키텍처')}</p><h2 class="title">${esc(model.title || '')}</h2></div>
  ${duo || svg}
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
