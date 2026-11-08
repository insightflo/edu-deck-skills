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
 *   layout : { dir:"LR|TB", nodesep, ranksep }      기본 LR 48/96
 *   steps  : { zones:1, nodes:2, edges:3 }          g[data-step] 단계 번호(기본값)
 *   nodes  : [{ id, name, role, icon:"i-*"|null, shape:"card|circle",
 *               fam:"paper|blue|orange", w, h, step? }]
 *   edges  : [{ from, to, label, kind:"b|o|g", flow?:bool, step? }]
 *             kind b=동기(k-ln-b) o=이벤트(k-ln-o) g=보조(k-ln-g); flow→dash-flow 입자
 *   zones  : [{ id, label, members:[id…], step? }] 점선 신뢰 경계(k-frame)
 *   states : [{ node, at, state:"ok|warn|down" }]  상태 칩 교체 — 이전 칩 data-until=at-1,
 *             새 칩 data-step=at(failover 시나리오 §4.7). node.state는 초기 칩.
 *   legend : [{ kind:"b|o|g", label }]             선 어휘 범례 1줄
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
const KIND = { b: { mk: 'ah-b' }, o: { mk: 'ah-o' }, g: { mk: 'ahg' } };
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
  return { a: e.from, b: e.to, label: e.label || '', kind: e.kind || 'b', flow: !!e.flow, step: e.step };
});
const ZONES = (model.zones || []).map((z) => ({ ...z }));
for (const z of ZONES) for (const m of z.members) if (!NODES[m]) fail(`zone ${z.id}: 알 수 없는 노드 ${m}`);
if (EDGES.length > 12) fail(`링크 ${EDGES.length}개 > 12(draw 예산) — 장을 나눌 것`);

/* ── 1. dagre 배치 ── */
const g = new dagre.graphlib.Graph({ multigraph: true });
g.setGraph({ rankdir: L.dir || 'LR', nodesep: L.nodesep ?? 48, ranksep: L.ranksep ?? 96, marginx: 0, marginy: 0 });
g.setDefaultEdgeLabel(() => ({}));
for (const [id, d] of Object.entries(NODES)) g.setNode(id, { width: d.w, height: d.h });
EDGES.forEach((e, i) => g.setEdge(e.a, e.b, { label: e.label, width: 40, height: 30, labelpos: 'c' }, `e${i}`));
dagre.layout(g);

const nodes = Object.fromEntries(Object.entries(NODES).map(([id, d]) => {
  const v = g.node(id);
  return [id, { cx: v.x, cy: v.y, ...d }];
}));
const edges = EDGES.map((e, i) => ({ ...e, pts: g.edge(e.a, e.b, `e${i}`).points.map((p) => ({ x: p.x, y: p.y })) }));

/* ── 2. 정규화: 존 패딩 포함 전체 bbox → 1664 폭·여백 안 가운데 ── */
const nRect = (n) => ({ x0: n.cx - n.w / 2, x1: n.cx + n.w / 2, y0: n.cy - n.h / 2, y1: n.cy + n.h / 2 + (n.shape === 'circle' ? 34 : 0) });
const zoneBox = (z) => {
  const rs = z.members.map((m) => nRect(nodes[m]));
  return { x0: Math.min(...rs.map((r) => r.x0)) - ZP.side, x1: Math.max(...rs.map((r) => r.x1)) + ZP.side,
           y0: Math.min(...rs.map((r) => r.y0)) - ZP.top, y1: Math.max(...rs.map((r) => r.y1)) + ZP.bottom };
};
const zones = ZONES.map((z) => ({ ...z, r: zoneBox(z) }));
let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
const eat = (x0, y0, x1, y1) => { minX = Math.min(minX, x0); minY = Math.min(minY, y0); maxX = Math.max(maxX, x1); maxY = Math.max(maxY, y1); };
for (const n of Object.values(nodes)) { const r = nRect(n); eat(r.x0, r.y0, r.x1, r.y1); }
for (const z of zones) eat(z.r.x0, z.r.y0, z.r.x1, z.r.y1);
for (const e of edges) for (const p of e.pts) eat(p.x, p.y, p.x, p.y);
const contentW = maxX - minX, H = maxY - minY + PAD * 2 + ((model.legend || []).length ? 56 : 0);
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
const overlaps = (r) => Object.values(nodes).some((n) => {
  const b = nRect(n);
  return r.x0 < b.x1 && r.x1 > b.x0 && r.y0 < b.y1 && r.y1 > b.y0;
}) || zones.some((z) => {
  // 존 라벨 영역(상단 띠 48px)도 회피 — 칩이 존 이름 위에 올라가지 않게
  const b = { x0: z.r.x0, x1: z.r.x1, y0: z.r.y0, y1: z.r.y0 + 48 };
  return r.x0 < b.x1 && r.x1 > b.x0 && r.y0 < b.y1 && r.y1 > b.y0;
});
const labelPos = (e, idx) => {
  const m = midPoint(e.pts), w = e.label.length * 17 + 30;
  const pair = edges.findIndex((q) => q.a === e.b && q.b === e.a);
  const off = pair >= 0 && pair < idx ? 26 : pair >= 0 ? -26 : 0;
  for (const dy of [off, off - 34, off + 34, off - 68, off + 68, off - 102, off + 102]) {
    for (const dx of [0, -44, 44, -88, 88, -132, 132, -176, 176]) {
      const r = { x0: m.x + dx - w / 2, x1: m.x + dx + w / 2, y0: m.y - 18 + dy, y1: m.y + 18 + dy };
      if (!overlaps(r)) return { x: m.x + dx, y: m.y + dy, w };
    }
  }
  return { x: m.x, y: m.y + off, w };
};

/* ── 4. 방출 ── */
const zoneMarkup = (z) => `<g data-step="${z.step ?? STEP.zones}">
    <rect class="k-frame" x="${X(z.r.x0)}" y="${Y(z.r.y0)}" width="${r2(z.r.x1 - z.r.x0)}" height="${r2(z.r.y1 - z.r.y0)}" style="rx:12px"/>
    <text class="k-t-tag" x="${X(z.r.x0 + 16)}" y="${Y(z.r.y0 + 34)}">${esc(z.label)}</text>
  </g>`;

const stateChips = (id, n, x, y) => {
  // states[]: node.at 시점에 칩 교체 — 이전 칩 data-until=at-1, 새 칩 data-step=at
  const trans = (model.states || []).filter((s) => s.node === id).sort((p, q) => p.at - q.at);
  if (!n.state && !trans.length) return '';
  const chain = [{ at: 0, state: n.state || 'ok' }, ...trans];
  return chain.map((c, i) => {
    const next = chain[i + 1];
    const vis = i === 0 ? (next ? ` data-until="${next.at - 1}"` : '') : ` data-step="${c.at}"${next ? ` data-until="${next.at - 1}"` : ''}`;
    const [txt, col] = STATE_ICON[c.state] || STATE_ICON.ok;
    return `<g${vis}><circle cx="${x}" cy="${y}" r="9" style="fill:${col}"/><text class="k-t-tag" x="${x + 15}" y="${y + 7}">${txt}</text></g>`;
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
    if (n.icon) o.push(`<use href="#${n.icon}" x="${r2(hasState ? x + n.w - 62 : x + n.w / 2 - 24)}" y="${y + 14}" width="48" height="48" style="color:${ICON_COLOR[n.fam]}"/>`);
    o.push(`<text class="t-l" x="${r2(x + n.w / 2)}" y="${y + (n.icon ? 96 : 78)}" text-anchor="middle">${esc(n.name)}</text>`);
    if (n.role) o.push(`<text class="k-t-tag" x="${r2(x + n.w / 2)}" y="${y + (n.icon ? 124 : 106)}" text-anchor="middle">${esc(n.role)}</text>`);
    o.push(stateChips(id, n, x + 16, y + 16));
  }
  o.push('</g>');
  return o.filter(Boolean).join('\n    ');
};

const edgeMarkup = (e, idx) => {
  const cls = `k-ln-${e.kind}${e.flow ? ' dash-flow' : ''}`;
  const o = [`<g data-step="${e.step ?? STEP.edges}">`,
    `  <path class="${cls}" d="${pathOf(e.pts, 12)}" marker-end="url(#${KIND[e.kind].mk})"/>`];
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
    const seg = `<polyline class="k-ln-${it.kind}" points="${x},${r2(H - 40)} ${x + 70},${r2(H - 40)}"/><text class="k-t-tag" x="${x + 84}" y="${r2(H - 32)}">${esc(it.label)}</text>`;
    x += 84 + it.label.length * 24 + 60;
    return seg;
  }).join('\n    ')}</g>`;
};

const svg = `<svg class="dg" viewBox="0 0 ${VBW} ${Math.ceil(H)}" role="img" aria-label="${esc(model.ariaLabel || model.title || '아키텍처 구성도')}">
  <title>${esc(model.titleSvg || model.title || '아키텍처 구성도')}</title>
  ${zones.map(zoneMarkup).join('\n  ')}
  ${edges.map(edgeMarkup).join('\n  ')}
  ${Object.entries(nodes).map(([id, n]) => nodeMarkup(id, n)).join('\n  ')}
  ${legendMarkup(model.legend)}
</svg>`;

const slide = `<section class="slide" data-archetype="arch-diagram" style="gap:20px">
  <div class="head"><p class="eyebrow">${esc(model.eyebrow || '가상 예시 · 아키텍처')}</p><h2 class="title">${esc(model.title || '')}</h2></div>
  ${svg}
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
