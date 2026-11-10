#!/usr/bin/env node
/**
 * chart_gen.mjs — 컨설팅 차트 의미 모델(charts.json 스키마) → 완성된 슬라이드 조각을
 * 빌드 시점에 굽는 생성기. arch_lanes.mjs/arch_layout.mjs 와 같은 계약:
 *   의미 모델만 고치고 다시 생성한다(산출물 손편집 금지) · 시간·난수 없는 결정적 출력 ·
 *   검증 실패는 FAIL 로 exit 1 · 결과에는 레이아웃 엔진이 남지 않는다(런타임 의존 0).
 *
 * [존재 이유] 컨설팅 장의 "수치-주장 일치"를 사람 눈이 아니라 계산으로 막는다.
 *   waterfall 은 시작+증감 합계가 주장(expectTotal)과 다르면 생성 자체를 거부하고,
 *   출처 블록·주석 수·강조 참조·데이터 수 범위를 스키마 수준에서 강제한다.
 *
 * [입력] --in MODEL.json   (스키마: consulting-deck/charts/schema.md)
 *   slide : { eyebrow, title, notes, ariaLabel }  — eyebrow 생략 시 "단위 · 기간" 합성
 *   chart : { type:"waterfall|ranked-bar-h|diverging-bar", question,
 *             measure:{ unit, period },
 *             data:[{ label, value, kind:"base|delta|total"(waterfall) }],
 *             highlight:[label…], annotations:[{ label, on:label, kind:"main|sub" }],
 *             calc:{ expectTotal } }
 *   source: { text, asOf, note?, synthetic:bool }
 * [출력] -o <슬라이드.html|->  (기본 stdout) · --svg-only <section> 없이 <svg> 만 ·
 *        --check  검증 + -o 파일과 바이트 비교(재생성 결정성) · --quiet 요약 생략
 *
 * [계약] viewBox 폭 1560 · 색은 var(--…) 토큰만(hex 직접 금지) · 글자는
 *   t-l/k-t-* 클래스 또는 스니펫 관례의 font-size+fill 속성 · script·SMIL·CSS 애니메이션
 *   0 · 모션은 엔진 속성만(data-step/.wf/data-fx="bar-grow"/data-count) · 출처 블록은
 *   그림 하단 <p class="small"> 로 항상 방출(synthetic 이면 "가상 데이터" 강제 표기).
 *
 * [재현성] 같은 입력 → 같은 바이트. 정렬은 value 내림차순·label 오름차순 고정 규칙,
 *   시스템 로캘 의존 함수(toLocaleString 등)는 쓰지 않는다.
 *
 * [수정 시 주의] data-step 외 새 모션 속성을 넣지 말 것. 출처 블록을 지우지 말 것
 *   (근거 없는 수치는 이 스킬의 금지 사항이다). 실패 메시지는 무엇이 왜 틀렸는지 말한다.
 */
import fs from 'node:fs';
import process from 'node:process';

/* ── 0. CLI ──────────────────────────────────────────────────────── */
const argv = process.argv.slice(2);
const arg = (k, d = null) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const has = (k) => argv.includes(k);
if (!argv.length || has('--help') || has('-h')) {
  console.log(`chart_gen.mjs — 컨설팅 차트 생성기(11종: waterfall · ranked-bar-h · diverging-bar · stacked-bar · line · scatter · heatmap · matrix-2x2 · tornado · sankey · pareto)
usage: node chart_gen.mjs --in MODEL.json [-o SLIDE.html] [--svg-only] [--check] [--quiet]
  --in       차트 의미 모델(스키마: consulting-deck/charts/schema.md)
  -o         슬라이드 단편 출력(기본 stdout)
  --svg-only <section> 없이 <svg> 만
  --check    검증 + -o 파일과 바이트 비교(재생성 결정성)
  --quiet    요약 생략`);
  process.exit(argv.length ? 0 : 1);
}
const inPath = arg('--in');
if (!inPath || !fs.existsSync(inPath)) { console.error(`FAIL: 모델 파일 없음: ${inPath || '(없음)'}`); process.exit(1); }
let model;
try { model = JSON.parse(fs.readFileSync(inPath, 'utf8')); }
catch (e) { console.error(`FAIL: JSON 파싱 실패: ${e.message}`); process.exit(1); }
const outPath = arg('-o', arg('--out'));
const svgOnly = has('--svg-only');
const checkOnly = has('--check');
const quiet = has('--quiet');

/* ── 1. 검증 ─────────────────────────────────────────────────────── */
const errors = [];
const warns = [];
const fail = (m) => errors.push(m);
const warn = (m) => warns.push(m);
const die = (m) => { fail(m); for (const e of errors) console.error(`FAIL: ${e}`); process.exit(1); };

const TYPES = {
  'waterfall':     { min: 3, max: 8,  archetype: 'waterfall',    variant: 'bridge' },
  'ranked-bar-h':  { min: 3, max: 10, archetype: 'chart-bar',    variant: 'ranked' },
  'diverging-bar': { min: 3, max: 9,  archetype: 'chart-bar',    variant: 'diverging' },
  'stacked-bar':   { min: 2, max: 6,  archetype: 'chart-bar',    variant: 'stacked' },
  'line':          { min: 3, max: 12, archetype: 'chart-line',   variant: 'line' },
  'scatter':       { min: 4, max: 30, archetype: 'chart-line',   variant: 'scatter' },
  'heatmap':       { min: 4, max: 64, archetype: 'heatmap-grid', variant: 'matrix' },
  'matrix-2x2':    { min: 4, max: 12, archetype: 'quadrant',     variant: 'matrix-2x2' },
  'tornado':       { min: 3, max: 8,  archetype: 'chart-bar',    variant: 'tornado' },
  'sankey':        { min: 2, max: 18, archetype: 'sankey-flow',  variant: 'data' },
  'pareto':        { min: 4, max: 10, archetype: 'chart-bar',    variant: 'pareto' },
};
/* data 가 {rows,cols,cells}·{nodes,flows} 객체인 타입 — 그 외는 행 배열 */
const OBJ_DATA = new Set(['heatmap', 'sankey']);
const WF_KINDS = ['base', 'delta', 'total'];
const ANN_KINDS = ['main', 'sub'];

const slide = model.slide || {};
const chart = model.chart || {};
const source = model.source;
const type = TYPES[chart.type];
// 덱 로컬 테마·스타일 클래스(예: consult) — 추가 클래스는 모델에 선언해 재생성 계약을 유지한다
const extraCls = typeof slide.class === 'string' ? slide.class.trim().replace(/[^a-z0-9 -]/gi, '') : '';

if (!slide.title) fail('slide.title 누락 — 주장형 제목은 필수다');
if (!type) fail(`chart.type 은 ${Object.keys(TYPES).join('|')} 중 하나여야 한다: '${chart.type}'`);
if (!chart.question) fail('chart.question 누락 — 이 차트가 답하는 분석 질문을 적어야 한다');
if (!(chart.measure || {}).unit) fail('chart.measure.unit 누락 — 단위(%, 억 원, 명…)는 필수다');
if (!source || !source.text) fail('source.text 누락 — 출처 없는 수치는 쓸 수 없다');
if (source && typeof source.synthetic !== 'boolean') fail('source.synthetic 은 true/false 명시 필수 — 가상 데이터는 반드시 표기한다');
if (source && !source.asOf) warn('source.asOf(기준일) 없음 — 출처 블록에 기준일이 빠진다');
if (!slide.notes) warn('slide.notes 없음 — 발표 노트를 권장한다');

/* P2 옵션 — 캔버스 폭·다리/브래킷·목표 사분면·사이드카 칼럼 */
if (chart.canvas != null && !['full', 'sidecar'].includes(chart.canvas))
  fail(`chart.canvas '${chart.canvas}' — full|sidecar 만 허용`);
if (chart.bridge != null && chart.bridge !== 'total' && chart.bridge !== 'segment')
  fail(`chart.bridge '${chart.bridge}' — total|segment 만 허용`);
if (chart.bridge != null && chart.type !== 'stacked-bar')
  warn('chart.bridge 는 stacked-bar 전용 — 무시된다');
if (chart.bridgeSegments != null && !Array.isArray(chart.bridgeSegments))
  fail('chart.bridgeSegments 는 세그먼트 name 배열이어야 한다');
if (chart.targetQuadrant != null && !['tr', 'tl', 'br', 'bl'].includes(chart.targetQuadrant))
  fail(`chart.targetQuadrant '${chart.targetQuadrant}' — tr|tl|br|bl 만 허용`);
if (chart.targetQuadrant != null && chart.type !== 'matrix-2x2')
  warn('chart.targetQuadrant 는 matrix-2x2 전용 — 무시된다');
const sidecar = chart.sidecar;
if (sidecar != null) {
  if (typeof sidecar !== 'object' || Array.isArray(sidecar)) fail('chart.sidecar 는 {k,v,unit?,h?,bullets[]} 객체여야 한다');
  else {
    if (sidecar.v == null || sidecar.v === '') fail('chart.sidecar.v(헤드라인 수치) 누락');
    if (!Array.isArray(sidecar.bullets) || !sidecar.bullets.length || sidecar.bullets.length > 3)
      fail('chart.sidecar.bullets 는 1~3개 문자열 배열');
    else sidecar.bullets.forEach((b, i) => { if (typeof b !== 'string' || !b.trim()) fail(`chart.sidecar.bullets[${i}] 빈 문자열`); });
    if (chart.canvas !== 'sidecar') warn('chart.sidecar 는 chart.canvas:"sidecar" 와 함께 쓴다 — 캔버스가 좁아지지 않으면 패널이 어색하다');
  }
}
if (chart.canvas === 'sidecar' && !sidecar)
  warn('canvas:"sidecar" 인데 chart.sidecar 가 없다 — 우측 칼럼 없이 좁은 캔버스만 그린다');

if ((chart.measure || {}).axisBreak != null && (typeof chart.measure.axisBreak !== 'number' || !Number.isFinite(chart.measure.axisBreak)))
  fail('chart.measure.axisBreak 은 숫자여야 한다 — 축 생략 구간의 하한값');
if (!Array.isArray(chart.data) && !OBJ_DATA.has(chart.type)) fail('chart.data 는 배열이어야 한다');
const data = OBJ_DATA.has(chart.type)
  ? (chart.data && typeof chart.data === 'object' && !Array.isArray(chart.data) ? chart.data : null)
  : (Array.isArray(chart.data) ? chart.data : []);
if (OBJ_DATA.has(chart.type) && !data) fail('chart.data 는 {rows,cols,cells}|{nodes,flows} 객체여야 한다');

const labels = new Set();
/* label 등록 — 중복이면 FAIL(주석·강조 참조가 모호해지므로) */
const lab = (d, i, tag = 'data') => {
  if (!d || typeof d.label !== 'string' || !d.label) { fail(`${tag}[${i}].label 누락`); return; }
  if (labels.has(d.label)) fail(`${tag}[${i}].label '${d.label}' 중복 — 주석·강조 참조가 모호해진다`);
  labels.add(d.label);
};
const num = (v, w) => { if (typeof v !== 'number' || !Number.isFinite(v)) fail(`${w} 는 유한 숫자여야 한다: '${v}'`); };

if (type && data) {
  if (!OBJ_DATA.has(chart.type) && (data.length < type.min || data.length > type.max))
    fail(`${chart.type} 데이터 수 ${data.length}개 — ${type.min}~${type.max}개 범위를 벗어났다`);
  switch (chart.type) {
    case 'stacked-bar': {
      const segNames = new Set();
      data.forEach((d, i) => {
        lab(d, i);
        if (!Array.isArray(d.segments) || !d.segments.length) fail(`data[${i}].segments — 최소 1개 필요`);
        else {
          if (d.segments.length > 6) fail(`data[${i}].segments ${d.segments.length}개 — 최대 6개`);
          let sum = 0;
          d.segments.forEach((g, j) => {
            if (!g || typeof g.name !== 'string' || !g.name) fail(`data[${i}].segments[${j}].name 누락`);
            else { segNames.add(g.name); labels.add(g.name); }
            if (g) { num(g.value, `data[${i}].segments[${j}].value`); if (typeof g.value === 'number' && g.value < 0) fail(`data[${i}].segments[${j}] 음수 — 적층은 양수만`); sum += g.value || 0; }
          });
          if (d.total != null && Math.abs(sum - d.total) > 1e-6) fail(`data[${i}] '${d.label}' 세그먼트 합 ${Math.round(sum * 100) / 100} ≠ 명시 total ${d.total}`);
        }
      });
      if (segNames.size > 6) fail(`세그먼트 이름 ${segNames.size}종 — 최대 6종`);
      if (Array.isArray(chart.bridgeSegments))
        chart.bridgeSegments.forEach((nm) => { if (!segNames.has(nm)) fail(`bridgeSegments '${nm}' — 세그먼트에 없는 name`); });
      break;
    }
    case 'line': {
      const series = chart.series;
      if (!Array.isArray(series) || !series.length) fail('line 은 chart.series 배열이 필요하다 — [{name,points:[v…],fill?}]');
      else {
        if (series.length > 4) fail(`line 계열 ${series.length}개 — 최대 4개`);
        series.forEach((s, i) => {
          if (!s || typeof s.name !== 'string' || !s.name) fail(`series[${i}].name 누락`);
          else labels.add(s.name);
          if (!Array.isArray(s.points) || s.points.length !== data.length) fail(`series[${i}].points 수 ${Array.isArray(s.points) ? s.points.length : 0} — x 개수 ${data.length} 와 달라야 한다`);
          else s.points.forEach((v, j) => num(v, `series[${i}].points[${j}]`));
        });
      }
      data.forEach((d, i) => lab(d, i));
      break;
    }
    case 'scatter':
    case 'matrix-2x2': {
      data.forEach((d, i) => {
        /* scatter 는 무명 점을 허용한다(배경 점) — 라벨이 있으면 등록·중복 검사 */
        if (chart.type === 'scatter' && (d.label == null || d.label === '')) { /* 무명 점 */ }
        else lab(d, i);
        num(d.x, `data[${i}].x`); num(d.y, `data[${i}].y`);
        if (d.size != null && (typeof d.size !== 'number' || d.size <= 0)) fail(`data[${i}].size 는 양수여야 한다`);
      });
      if (!(chart.measure || {}).x || !(chart.measure || {}).y)
        fail(`${chart.type} 는 measure.x·measure.y 축 라벨이 필수다`);
      if (chart.type === 'matrix-2x2' && !(chart.axes && chart.axes.x && chart.axes.y))
        fail('matrix-2x2 는 chart.axes = {x:{min,max,label},y:{…}} 가 필요하다');
      break;
    }
    case 'tornado':
      data.forEach((d, i) => {
        lab(d, i);
        num(d.low, `data[${i}].low`); num(d.high, `data[${i}].high`);
        if (typeof d.low === 'number' && typeof d.high === 'number' && d.low >= d.high)
          fail(`data[${i}] '${d.label}' low ${d.low} ≥ high ${d.high} — 민감도 쌍은 low < high 여야 한다`);
      });
      break;
    case 'heatmap': {
      const rows = data.rows || [], cols = data.cols || [], cells = data.cells || [];
      const rl = rows.map((r) => (typeof r === 'string' ? r : r && r.label));
      const cl = cols.map((c) => (typeof c === 'string' ? c : c && c.label));
      rl.forEach((x, i) => lab({ label: x }, i, 'rows'));
      cl.forEach((x, i) => lab({ label: x }, i, 'cols'));
      if (rl.length < 2 || rl.length > 8 || cl.length < 2 || cl.length > 8)
        fail(`heatmap 격자 ${rl.length}×${cl.length} — 행·열 각 2~8`);
      if (cells.length < type.min || cells.length > type.max)
        fail(`heatmap cells ${cells.length}개 — ${type.min}~${type.max}`);
      const seen = new Set();
      cells.forEach((c, i) => {
        const ri = typeof c.r === 'string' ? rl.indexOf(c.r) : c.r;
        const ci = typeof c.c === 'string' ? cl.indexOf(c.c) : c.c;
        if (ri < 0 || ri >= rl.length || ci < 0 || ci >= cl.length) fail(`cells[${i}] r,c 참조 불가 — 행·열 인덱스/라벨이 아니다`);
        else { const k = `${ri},${ci}`; if (seen.has(k)) fail(`cells[${i}] (${c.r},${c.c}) 중복`); seen.add(k); }
        num(c.v, `cells[${i}].v`);
      });
      break;
    }
    case 'sankey': {
      const nodes = data.nodes || [], flows = data.flows || [];
      const ids = new Set();
      nodes.forEach((n, i) => {
        if (!n || typeof n.id !== 'string' || !n.id) { fail(`nodes[${i}].id 누락`); return; }
        if (ids.has(n.id)) fail(`nodes[${i}].id '${n.id}' 중복`);
        ids.add(n.id);
        lab({ label: n.label || n.id }, i, 'nodes');
      });
      if (nodes.length < 3 || nodes.length > 12) fail(`sankey 노드 ${nodes.length}개 — 3~12`);
      if (flows.length < type.min || flows.length > type.max) fail(`sankey flows ${flows.length}개 — ${type.min}~${type.max}`);
      const adj = new Map();
      flows.forEach((f, i) => {
        if (!ids.has(f.from)) fail(`flows[${i}].from '${f.from}' — nodes 에 없는 id`);
        if (!ids.has(f.to)) fail(`flows[${i}].to '${f.to}' — nodes 에 없는 id`);
        if (f.from === f.to) fail(`flows[${i}] '${f.from}' 자기 순환`);
        if (typeof f.value !== 'number' || !(f.value > 0)) fail(`flows[${i}].value 는 양수여야 한다: '${f.value}'`);
        if (ids.has(f.from) && ids.has(f.to)) (adj.get(f.from) || adj.set(f.from, []).get(f.from)).push(f.to);
      });
      /* DAG 검증 — 순환이 있으면 열 배치가 발산하므로 FAIL */
      const state = new Map();
      const cyc = (u, path) => {
        if (state.get(u) === 1) { fail(`sankey 순환 발견: ${[...path, u].join('→')}`); return true; }
        if (state.get(u) === 2) return false;
        state.set(u, 1);
        for (const v of adj.get(u) || []) if (cyc(v, [...path, u])) return true;
        state.set(u, 2);
        return false;
      };
      for (const u of ids) if (!errors.length && cyc(u, [])) break;
      break;
    }
    case 'pareto':
      data.forEach((d, i) => {
        lab(d, i);
        num(d.value, `data[${i}].value`);
        if (typeof d.value === 'number' && d.value <= 0) fail(`pareto data[${i}] '${d.label}' 값 ${d.value} — 양수만(누적 곡선 불가)`);
      });
      if ((chart.measure || {}).unit === '%') {
        const s = data.reduce((a, d) => a + (d.value || 0), 0);
        if (Math.abs(s - 100) > 0.5) fail(`pareto 비율 모드(단위 %) — 합계 ${Math.round(s * 100) / 100} ≠ 100`);
      }
      if (chart.calc && chart.calc.expectTotal != null) {
        const s = data.reduce((a, d) => a + (d.value || 0), 0);
        if (Math.abs(s - chart.calc.expectTotal) > 1e-6) fail(`pareto 합계 ${Math.round(s * 100) / 100} ≠ calc.expectTotal ${chart.calc.expectTotal}`);
      }
      break;
    default:
      data.forEach((d, i) => {
        lab(d, i);
        num(d.value, `data[${i}].value`);
        if (d.kind != null && !WF_KINDS.includes(d.kind)) fail(`data[${i}].kind '${d.kind}' — ${WF_KINDS.join('|')} 만 허용`);
      });
  }
}

/* highlight — data 에 없는 label 참조는 오타다 */
const highlights = chart.highlight || [];
for (const h of highlights) if (!labels.has(h)) fail(`highlight '${h}' — data 에 없는 label`);

/* annotations — main 1 + sub ≤2, on 은 실존 label */
const anns = chart.annotations || [];
const nMain = anns.filter((a) => a.kind === 'main').length;
const nSub = anns.filter((a) => a.kind === 'sub').length;
if (nMain > 1 || nSub > 2)
  fail(`annotations 초과 — main ${nMain}개(최대 1) · sub ${nSub}개(최대 2): 차트는 주장 하나에 수렴해야 한다`);
anns.forEach((a, i) => {
  if (!a.label) fail(`annotations[${i}].label 누락`);
  if (!ANN_KINDS.includes(a.kind)) fail(`annotations[${i}].kind '${a.kind}' — main|sub 만 허용`);
  if (!labels.has(a.on)) fail(`annotations[${i}].on '${a.on}' — data 에 없는 label`);
});

/* 타입별 계산 가드 */
const kindOf = (d, i) => d.kind || (i === 0 ? 'base' : i === data.length - 1 ? 'total' : 'delta');
if (type && chart.type === 'waterfall' && data.length) {
  const calc = chart.calc || {};
  if (typeof calc.expectTotal !== 'number' || !Number.isFinite(calc.expectTotal))
    fail('waterfall 은 calc.expectTotal 필수 — 시작+증감 합계가 주장과 일치하는지 검증한다');
  let cum = 0, firstBase = true;
  data.forEach((d, i) => {
    const k = kindOf(d, i);
    if (k === 'base' && !firstBase) fail(`data[${i}] '${d.label}': base 는 첫 항목에만 온다`);
    if (k === 'total' && i !== data.length - 1) fail(`data[${i}] '${d.label}': total 은 마지막 항목에만 온다`);
    if (k !== 'total') cum += d.value;
    firstBase = false;
  });
  const last = data[data.length - 1];
  const EPS = 1e-6;
  if (typeof calc.expectTotal === 'number' && Number.isFinite(calc.expectTotal) &&
      Math.abs(cum - calc.expectTotal) > EPS)
    fail(`waterfall 합계 불일치 — 시작+증감 = ${cum} 인데 expectTotal = ${calc.expectTotal} (데이터-주장 불일치)`);
  if (kindOf(last, data.length - 1) === 'total' && Math.abs(last.value - cum) > EPS)
    fail(`waterfall total '${last.label}' 값 ${last.value} 가 누적 ${cum} 과 다르다`);
  if (cum < 0) warn('waterfall 누적이 0 아래로 내려간다 — 기준선 아래 막대는 지원하지 않는다');
}
if (type && chart.type === 'ranked-bar-h') {
  data.forEach((d, i) => { if (d.value < 0) fail(`ranked-bar-h data[${i}] '${d.label}' 음수 ${d.value} — 음수 순위는 diverging-bar 를 쓴다`); });
}
if (type && chart.type === 'diverging-bar' && data.length) {
  const pos = data.some((d) => d.value > 0), neg = data.some((d) => d.value < 0);
  if (!(pos && neg)) warn('diverging-bar 인데 부호가 한쪽뿐 — 0축 발산이 아니라 ranked-bar-h 가 적합할 수 있다');
}

if (errors.length) { for (const e of errors) console.error(`FAIL: ${e}`); process.exit(1); }

/* ── 2. 공통 도우미 ──────────────────────────────────────────────── */
/* 캔버스 폭 — 기본 1560(전폭). canvas:"sidecar" 는 68% 차트 칼럼용 1040 */
const VBW = chart.canvas === 'sidecar' ? 1040 : 1560;
const R_EDGE = VBW - 60;
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
/* 사이드카 문구용 — 모델의 <b>…</b> 강조만 되살리고 그 외 마크업은 계속 이스케이프한다 */
const escRich = (s) => esc(s).replace(/&lt;(\/?b)&gt;/g, '<$1>');
const r2 = (v) => Math.round(v * 100) / 100;
const fmt = (v) => {
  const [i, f] = String(v).split('.');
  const sign = i.startsWith('-') ? '−' : '';
  const digits = (i.startsWith('-') ? i.slice(1) : i).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return sign + digits + (f ? '.' + f : '');
};
const fmtDelta = (v) => (v > 0 ? '+' + fmt(v) : fmt(v));
const annBy = (on) => anns.filter((a) => a.on === on);
/* 추정 글자 폭 — 전각(CJK·괄호)은 fs, 그 외는 0.55fs 로 근사한다(결정적·폰트 무의존) */
const tw = (s, fs) => [...String(s)].reduce((w, c) => w + (c.charCodeAt(0) > 0x2e7f ? fs : fs * 0.55), 0);
/* 주석 한 건을 최대 2줄로 접는다 — 어절(공백) 우선 병합, 한 어절이 maxW 를 넘으면 그것만 글자 단위로 쪼갠다.
   숫자·단위가 행갈이로 분단(“202/4재계약”형) 되는 것을 막는다(agy 리뷰 치명-4). 둘째 줄까지 넘치면 끝에 '…' 로 자른다. */
const wrapLines = (s, maxW, fs) => {
  const lines = []; let cur = '';
  const split = (w) => {              // 한 토큰을 maxW 안에서 글자 단위로
    let piece = '';
    for (const ch of w) {
      if (piece && tw(piece + ch, fs) > maxW) { lines.push(piece); piece = ch; } else piece += ch;
    }
    return piece;
  };
  for (const w of String(s).split(/(\s+)/)) {
    if (!w) continue;
    if (!cur) { cur = split(w); continue; }
    if (tw(cur + w, fs) > maxW) { lines.push(cur); cur = split(w); }
    else cur += w;
  }
  if (cur) lines.push(cur);
  if (lines.length > 2) {
    let rest = lines.slice(1).join('');
    while (rest && tw(rest + '…', fs) > maxW) rest = [...rest].slice(0, -1).join('');
    return [lines[0], rest + '…'];
  }
  return lines;
};
/* 주석 캡슐 배지 — 「핵심」/「참고」 텍스트 표식 대신 채움 캡슐(rounded rect+흰 글자).
   main=accent(초점), sub=track-strong(비초점) — 종이 톤 위에서도 종별이 읽힌다.
   배지 폭은 폭 계산에 ANN_PAD 로 예약한다. */
const BADGE_W = 64, BADGE_H = 26, ANN_PAD = 72;
const badgeFill = (a) => a.kind === 'main' ? 'var(--accent)' : 'var(--track-strong)';
const badgeTxt = (a) => (a.kind === 'main' ? '핵심' : '참고');
const emitBadge = (svg, x, yBase, a) => {
  svg.push(`<rect x="${r2(x)}" y="${r2(yBase - 19)}" width="${BADGE_W}" height="${BADGE_H}" rx="${BADGE_H / 2}" fill="${badgeFill(a)}"/>`);
  svg.push(`<text x="${r2(x + BADGE_W / 2)}" y="${r2(yBase + 1)}" font-size="18" font-weight="800" class="k-t-w" text-anchor="middle">${badgeTxt(a)}</text>`);
};
const annFont = (a) => (a.kind === 'main' ? 24 : 20);
const eyebrow = slide.eyebrow || `${chart.measure.unit} · ${chart.measure.period || ''}`.replace(/ · $/, '');
const unitTag = `    <text class="k-t-tag" x="0" y="42">(단위: ${esc(chart.measure.unit)})</text>`;

function svgOpen(h, aria) {
  return [
    `  <svg class="dg" viewBox="0 0 ${VBW} ${h}" role="img" aria-label="${esc(aria)}">`,
    `    <title>${esc(slide.title)}</title>`,
  ];
}
function section(svg, meta) {
  /* 출처 블록 — c-note·c-src·s-syn 클래스는 덱 src css(deck 로컬)에 정의된다.
     마지막 단계에 함께 공개해 수치가 다 보인 뒤 근거가 읽히도록 한다. */
  const last = meta.steps;
  const srcBlock = [
    ...(source.note ? [`  <p class="c-note" data-step="${last}"><b>방법론·한계</b> — ${esc(source.note)}</p>`] : []),
    `  <div class="c-src" data-step="${last}">`,
    `    <p>Source: ${esc(source.text)}${source.asOf ? ` · 기준 ${esc(source.asOf)}` : ''}</p>`,
    ...(source.synthetic ? ['    <p class="s-syn">가상 데이터</p>'] : []),
    `  </div>`,
  ];
  /* 사이드카 — 차트 68% + 시사점 칼럼 32%(상단 3px accent 룰·헤드라인 수치·불릿 ≤3).
     c-sidecar 계열 클래스는 덱 src css 가 정의한다. */
  const bodyBlock = sidecar
    ? [
      `  <div class="c-sidecar">`,
      `    <div class="c-sidecar-main">`,
      ...svg,
      `    </svg>`,
      `    </div>`,
      `    <aside class="c-sidecar-panel" data-step="${last}">`,
      `      <p class="sc-k">${esc(sidecar.k || 'SO WHAT')}</p>`,
      `      <p class="sc-v">${esc(sidecar.v)}${sidecar.unit ? `<small>${esc(sidecar.unit)}</small>` : ''}</p>`,
      ...(sidecar.h ? [`      <p class="sc-h">${escRich(sidecar.h)}</p>`] : []),
      `      <ul>`,
      ...(sidecar.bullets || []).map((b) => `        <li>${escRich(b)}</li>`),
      `      </ul>`,
      `    </aside>`,
      `  </div>`,
    ]
    : [...svg, `  </svg>`];
  const h = [
    header(),
    `<section class="slide${extraCls ? ' ' + extraCls : ''}" data-archetype="${type.archetype}" data-variant="${type.variant}" style="gap:18px">`,
    `  <div class="head"><p class="eyebrow">${esc(eyebrow)}</p><h2 class="title">${esc(slide.title)}</h2></div>`,
    ...bodyBlock,
    ...srcBlock,
    `  <aside class="notes">${esc(slide.notes || '')}</aside>`,
    `</section>`,
  ];
  return { svg: svg.concat(`  </svg>`).join('\n'), section: h.join('\n'), meta };
}
function header() {
  const rel = inPath.replace(/^.*?(?=consulting-deck\/|examples\/)/, '');
  return `<!-- consulting chart — ${chart.type}
     모델: ${rel} · 생성: node consulting-deck/charts/chart_gen.mjs --in ${rel} -o <이 파일>
     질문: ${chart.question}
     손으로 고치지 않는다. 모델을 고치고 다시 생성한다. -->`;
}
/* 발산·순위 막대의 성장 기준점 — transform-box:fill-box 로 막대 자체 상자 기준 */
const growL = `data-fx="bar-grow" style="transform-box:fill-box;transform-origin:left center"`;
const growR = `data-fx="bar-grow" style="transform-box:fill-box;transform-origin:right center"`;
const growB = `data-fx="bar-grow" style="transform-box:fill-box;transform-origin:center bottom"`;

/* ── 3-A. waterfall ──────────────────────────────────────────────── */
function buildWaterfall() {
  const n = data.length;
  const BASE_Y = 460, PLOT = 360, CONN = 60, NAME_Y = 508;
  let H = 580;
  /* 스케일: 누적 최고점이 PLOT 안에 들어오도록 */
  let cum = 0, top = 0;
  const cums = data.map((d, i) => { const k = kindOf(d, i); if (k !== 'total') cum += d.value; top = Math.max(top, cum); return cum; });
  const maxV = Math.max(top, 1e-9);
  const minCum = Math.min(...cums);
  const deltas = data.filter((d, i) => kindOf(d, i) === 'delta').map((d) => Math.abs(d.value));
  const minDelta = deltas.length ? Math.min(...deltas) : 1e9;
  /* 축 생략(axis break): 명시값 우선, 없으면 base≥max*60% 일 때 자동 —
     증감 막대가 ≥18px(막대 값의 20배 구간)이 되는 선에서 최소누적 아래의 둥근 값으로. */
  let brk = 0;
  const expl = chart.measure.axisBreak;
  if (typeof expl === 'number' && Number.isFinite(expl)) {
    if (expl > 0 && expl < minCum) brk = expl;
    else warn(`axisBreak ${expl} 은 0~최소누적 ${minCum} 사이여야 한다 — 무시`);
  } else if (data[0].value / maxV >= 0.6) {
    const p = 10 ** Math.max(0, Math.floor(Math.log10(minCum)) - 1);
    let auto = Math.floor(minCum / p) * p;
    if (auto >= minCum) auto -= p;
    brk = Math.max(0, Math.min(Math.max(auto, maxV - minDelta * 20), minCum - 1));
  }
  /* base 막대 최소 가시 폭 — 생략 하한이 base 바로 밑까지 오르면 base 가 몇 px 로 찌그러든다
     (agy 치명-6). (base−brk)/(maxV−brk) ≥ 22% 가 되도록 brk 상한을 준다. */
  if (brk > 0) {
    const endV = cums[cums.length - 1];
    const minBar = Math.min(data[0].value, endV);
    const cap = (minBar - 0.2 * maxV) / 0.8;
    if (Number.isFinite(cap) && cap > 0 && brk > cap) {
      if (typeof expl === 'number') warn(`axisBreak ${expl} 은 base/total 가시 폭(≥20%) 때문에 ${r2(cap)} 로 줄인다`);
      brk = Math.max(0, cap);
    }
  }
  const sc = PLOT / Math.max(maxV - brk, 1e-9);
  const U = (v) => (v - brk) * sc;
  const barW = Math.min(200, Math.floor((VBW - 180 - (n - 1) * CONN) / n));
  const span = n * barW + (n - 1) * CONN;
  const left = (VBW - span) / 2;
  /* X축 라벨 2단 스태거 — 슬롯(막대+연결 폭)보다 라벨이 넓으면 홀수 번째를 한 줄 아래로.
     좁은 사이드카 캔버스에서 인접 라벨 상호 겹침 방지(agy 갤러리 이슈-1). */
  const slot = barW + CONN;
  const stagger = data.some((d) => tw(String(d.label), 22) > slot * 0.94);
  const nameY = (i) => NAME_Y + (stagger && i % 2 === 1 ? 32 : 0);
  const nameBottom = NAME_Y + (stagger ? 32 : 0);
  /* 스태거+아래줄 주석이 같이 오면 캔버스를 40px 늘려 넘침을 막는다 */
  if (stagger && (chart.annotations || []).length) H += 40;

  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  svg.push(`    <path d="M60,${BASE_Y} L${R_EDGE},${BASE_Y}" fill="none" stroke="var(--line)" stroke-width="2.5" stroke-linecap="round"/>`);
  data.forEach((d, i) => {
    const k = kindOf(d, i);
    const prevCum = i === 0 ? 0 : cums[i - 1];
    const x = left + i * (barW + CONN), cx = x + barW / 2;
    const isLast = i === n - 1;
    const step = isLast ? n : i + 1;
    let y, h, fillAttr, val;
    if (k === 'delta') {
      y = BASE_Y - Math.max(U(prevCum), U(cums[i]));
      h = Math.abs(U(cums[i]) - U(prevCum));
      /* 축 생략 활성 시 가독성 하한 — 막대 상단(높은 누적)은 진짜 값 위치를 유지하고
         하단만 18px 미만일 때 늘인다. 값 라벨은 실측치 그대로라 시각 과장이 아니라 최소 가시 폭 보장이다. */
      if (brk > 0) h = Math.max(h, 18);
      /* 역할별 색 — 일회성 oneoff 는 회색+테두리, highlight 는 초점색, 일반은 파랑 */
      fillAttr = d.oneoff ? `fill="var(--muted)" stroke="var(--soft)" stroke-width="3"`
               : highlights.includes(d.label) ? 'fill="var(--accent)"' : 'class="k-solid-b"';
      val = fmtDelta(d.value);
    } else {
      const v = k === 'total' ? cums[n - 1] : d.value;
      y = BASE_Y - U(v);
      h = U(v);
      fillAttr = 'class="k-solid-n"';
      val = fmt(v);
    }
    const barBottom = y + Math.max(h, 2);
    svg.push(`    <g class="wf" data-step="${step}">`);
    if (i > 0) {
      const connY = k === 'delta' ? BASE_Y - U(prevCum) : y;
      svg.push(`      <path d="M${r2(x - CONN)},${r2(connY)} L${r2(x)},${r2(connY)}" class="k-ln-g"/>`);
    }
    svg.push(`      <rect x="${r2(x)}" y="${r2(y)}" width="${barW}" height="${r2(Math.max(h, 2))}" ${fillAttr}/>`);
    if (brk > 0 && k !== 'delta')
      svg.push(`      <path d="M${r2(x + 16)},${BASE_Y + 8} L${r2(x + 30)},${BASE_Y - 16} M${r2(x + 32)},${BASE_Y + 8} L${r2(x + 46)},${BASE_Y - 16}" fill="none" stroke="var(--line)" stroke-width="3" class="axis-brk"/>`);
    const tCls = k === 'delta' && highlights.includes(d.label) ? 'k-t-o' : '';
    svg.push(`      <text x="${r2(cx)}" y="${r2(y - 24)}" font-size="26" font-weight="800" ${tCls ? `class="${tCls}"` : 'fill="var(--ink)"'} text-anchor="middle"${isLast ? ' data-count' : ''}>${esc(val)}</text>`);
    svg.push(`      <text x="${r2(cx)}" y="${nameY(i)}" font-size="22" font-weight="700" fill="var(--ink)" text-anchor="middle">${esc(d.label)}</text>`);
    /* 주석 — 막대 아래 빈 공간에 점선 리더로 연결. 컬럼 폭(barW+CONN/2) 이내, 최대 2줄.
       부유 막대 밑 공간이 부족하면 항목 라벨 아래로 내린다(복수 주석은 아래로 누적). */
    let annCursor = 0;
    annBy(d.label).forEach((a) => {
      const fs = annFont(a), maxW = barW + CONN;
      const lines = wrapLines(a.label, maxW - ANN_PAD, fs);
      const need = lines.length * 24 + 16;
      const inGap = k === 'delta' && barBottom + annCursor + need <= nameY(i) - 8;
      const ly0 = inGap ? barBottom + annCursor + 10 + fs : nameBottom + 14 + annCursor + fs;
      const leadFrom = inGap ? barBottom + annCursor + 4 : nameY(i) + 8;
      const widest = Math.max(...lines.map((l) => tw(l, fs)), 40) + ANN_PAD;
      const x0 = Math.max(60, Math.min(cx - widest / 2, R_EDGE - widest - 10));
      svg.push(`      <path d="M${r2(cx)},${r2(leadFrom)} L${r2(cx)},${r2(ly0 - fs - 4)}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-dasharray="4 5"/>`);
      emitBadge(svg, x0, ly0, a);
      lines.forEach((line, li) => {
        svg.push(`      <text x="${r2(x0 + ANN_PAD)}" y="${r2(ly0 + li * 24)}" font-size="${fs}" font-weight="${a.kind === 'main' ? 800 : 600}" class="${a.kind === 'main' ? 'k-t-o' : 'k-t-tag'}" text-anchor="start">${esc(line)}</text>`);
      });
      annCursor += need;
    });
    svg.push(`    </g>`);
  });
  return section(svg, { bars: n, steps: n });
}

/* 주석 계획 — 수치 뒤 인라인으로 들어가면 인라인(같은 y), 아니면 항목 이름 아래에
   행 높이를 가산해 둔다(둘 중 겹침이 없는 쪽 — 하-1). */
function annPlan(d, valStr, valX, dir, labelX, belowX) {
  const inline = [], below = [];
  let cursor = valX + dir * (tw(valStr, 28) + 24);
  /* 아래줄 주석은 belowX+ANN_PAD 에서 시작해 R_EDGE 안에서 접는다(사이드카 1040폭 대응) */
  const belowW = Math.max(320, R_EDGE - belowX - ANN_PAD);
  for (const a of annBy(d.label)) {
    const fs = annFont(a), w = tw(a.label, fs) + ANN_PAD;
    const fits = dir > 0 ? cursor + w <= R_EDGE : cursor - w >= 60;
    if (fits && !below.length) {
      /* 인라인 — 블록 왼쪽 가장자리를 기억한다(음수 방향이면 cursor-w) */
      inline.push({ a, fs, x: dir > 0 ? cursor : cursor - w });
      cursor += dir * (w + 24);
    } else {
      wrapLines(a.label, belowW, fs).forEach((line, li) => below.push({ line, fs, main: a.kind === 'main', badge: li === 0 ? a : null }));
    }
  }
  return { inline, below, extra: below.length ? below.length * 26 + 20 : 0 };
}

/* ── 3-B. ranked-bar-h ───────────────────────────────────────────── */
function buildRanked() {
  const ROW = 82, BAR_H = 56, AXIS_X = 320, TOP = 70, MAX_W = Math.min(1100, R_EDGE - AXIS_X - 80);
  const rows = [...data].sort((a, b) => b.value - a.value || String(a.label).localeCompare(String(b.label)));
  const maxV = Math.max(...rows.map((d) => d.value), 1e-9);
  const plans = rows.map((d) => {
    const w = Math.max((d.value / maxV) * MAX_W, 4);
    return { w, ...annPlan(d, fmt(d.value), AXIS_X + w + 16, 1, AXIS_X - 20, AXIS_X) };
  });
  const ys = []; let yy = TOP;
  plans.forEach((p) => { ys.push(yy); yy += ROW + p.extra; });
  const H = yy + 56;
  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  svg.push(`    <line x1="${AXIS_X}" y1="56" x2="${AXIS_X}" y2="${ys[ys.length - 1] + BAR_H}" stroke="var(--line)" stroke-width="2.5"/>`);
  svg.push(`    <line x1="${AXIS_X}" y1="${H - 44}" x2="${R_EDGE}" y2="${H - 44}" stroke="var(--line)" stroke-width="2.5"/>`);
  rows.forEach((d, i) => {
    const { w, inline, below } = plans[i];
    const y = ys[i], cy = y + BAR_H / 2 + 8;
    const fill = highlights.includes(d.label) ? 'var(--accent)' : 'var(--track)';
    svg.push(`    <g data-step="${i + 1}">`);
    svg.push(`      <text x="${AXIS_X - 20}" y="${cy}" text-anchor="end" font-size="26" font-weight="700" fill="var(--ink)">${esc(d.label)}</text>`);
    svg.push(`      <rect x="${AXIS_X}" y="${y}" width="${r2(w)}" height="${BAR_H}" rx="8" fill="${fill}" ${growL}/>`);
    svg.push(`      <text x="${r2(AXIS_X + w + 16)}" y="${cy}" font-size="28" font-weight="800" fill="var(--ink)">${esc(fmt(d.value))}</text>`);
    inline.forEach((t) => {
      emitBadge(svg, r2(t.x), cy, t.a);
      svg.push(`      <text x="${r2(t.x + ANN_PAD)}" y="${cy}" font-size="${t.fs}" font-weight="${t.a.kind === 'main' ? 800 : 600}" class="${t.a.kind === 'main' ? 'k-t-o' : 'k-t-tag'}" text-anchor="start">${esc(t.a.label)}</text>`);
    });
    below.forEach((t, li) => {
      if (t.badge) emitBadge(svg, AXIS_X, cy + 44 + li * 26, t.badge);
      svg.push(`      <text x="${AXIS_X + ANN_PAD}" y="${r2(cy + 44 + li * 26)}" font-size="${t.fs}" font-weight="${t.main ? 800 : 600}" class="${t.main ? 'k-t-o' : 'k-t-tag'}" text-anchor="start">${esc(t.line)}</text>`);
    });
    svg.push(`    </g>`);
  });
  return section(svg, { bars: rows.length, steps: rows.length });
}

/* ── 3-C. diverging-bar ──────────────────────────────────────────── */
function buildDiverging() {
  const ROW = 82, BAR_H = 56, ZERO = Math.round(VBW / 2) + 20, TOP = 56, HALF = Math.min(460, R_EDGE - ZERO - 60);
  const LABEL_X = ZERO - HALF - 20;
  const maxA = Math.max(...data.map((d) => Math.abs(d.value)), 1e-9);
  const plans = data.map((d) => {
    const w = Math.max((Math.abs(d.value) / maxA) * HALF, 4);
    const neg = d.value < 0;
    const valStr = fmtDelta(d.value);
    const vx = neg ? ZERO - w - 16 : ZERO + w + 16;
    /* 최대 음수 막대의 값 라벨이 항목명(LABEL_X)과 겹치면 막대 안쪽(밝은 글자)로 뺀다(agy 치명-2) */
    const inNeg = neg && vx - tw(valStr, 28) < LABEL_X + 14;
    return { w, neg, vx, valStr, inNeg, ...annPlan(d, valStr, vx, neg ? -1 : 1, LABEL_X, neg ? ZERO - w : ZERO) };
  });
  const ys = []; let yy = TOP;
  plans.forEach((p) => { ys.push(yy); yy += ROW + p.extra; });
  const H = yy + 48;
  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  svg.push(`    <line x1="${ZERO - HALF}" y1="${H - 40}" x2="${ZERO + HALF}" y2="${H - 40}" stroke="var(--line)" stroke-width="2.5"/>`);
  svg.push(`    <line x1="${ZERO}" y1="56" x2="${ZERO}" y2="${H - 40}" stroke="var(--soft)" stroke-width="2.5"/>`);
  svg.push(`    <line x1="${ZERO - HALF}" y1="56" x2="${ZERO - HALF}" y2="${H - 40}" stroke="var(--line)" stroke-width="2" stroke-dasharray="6 8"/>`);
  svg.push(`    <line x1="${ZERO + HALF}" y1="56" x2="${ZERO + HALF}" y2="${H - 40}" stroke="var(--line)" stroke-width="2" stroke-dasharray="6 8"/>`);
  svg.push(`    <text x="${ZERO - HALF}" y="${H - 12}" text-anchor="middle" font-size="22" fill="var(--soft)">−${esc(fmt(maxA))}</text>`);
  svg.push(`    <text x="${ZERO}" y="${H - 12}" text-anchor="middle" font-size="22" fill="var(--soft)">0</text>`);
  svg.push(`    <text x="${ZERO + HALF}" y="${H - 12}" text-anchor="middle" font-size="22" fill="var(--soft)">+${esc(fmt(maxA))}</text>`);
  data.forEach((d, i) => {
    const { w, neg, vx, valStr, inNeg, inline, below } = plans[i];
    const y = ys[i], cy = y + BAR_H / 2 + 8;
    const x = neg ? ZERO - w : ZERO;
    const fill = highlights.includes(d.label) ? 'var(--accent)' : (neg ? 'var(--track-strong)' : 'var(--track)');
    const grow = neg ? growR : growL;
    const anchor = inNeg ? 'start' : neg ? 'end' : 'start';
    const ring = highlights.includes(d.label) ? ` stroke="var(--ink)" stroke-width="3"` : '';
    svg.push(`    <g data-step="${i + 1}">`);
    svg.push(`      <text x="${LABEL_X}" y="${cy}" text-anchor="end" font-size="26" font-weight="700" fill="var(--ink)">${esc(d.label)}</text>`);
    svg.push(`      <rect x="${r2(x)}" y="${y}" width="${r2(w)}" height="${BAR_H}" rx="8" fill="${fill}"${ring} ${grow}/>`);
    svg.push(`      <text x="${r2(inNeg ? ZERO - w + 16 : vx)}" y="${cy}" font-size="28" font-weight="800" fill="${inNeg ? 'var(--paper)' : 'var(--ink)'}" text-anchor="${anchor}">${esc(valStr)}</text>`);
    inline.forEach((t) => {
      emitBadge(svg, r2(t.x), cy, t.a);
      svg.push(`      <text x="${r2(t.x + ANN_PAD)}" y="${cy}" font-size="${t.fs}" font-weight="${t.a.kind === 'main' ? 800 : 600}" class="${t.a.kind === 'main' ? 'k-t-o' : 'k-t-tag'}" text-anchor="start">${esc(t.a.label)}</text>`);
    });
    below.forEach((t, li) => {
      if (t.badge) emitBadge(svg, x, cy + 44 + li * 26, t.badge);
      svg.push(`      <text x="${r2(x + ANN_PAD)}" y="${r2(cy + 44 + li * 26)}" font-size="${t.fs}" font-weight="${t.main ? 800 : 600}" class="${t.main ? 'k-t-o' : 'k-t-tag'}" text-anchor="start">${esc(t.line)}</text>`);
    });
    svg.push(`    </g>`);
  });
  return section(svg, { bars: data.length, steps: data.length });
}

/* 공통 주석 방출 — 대상 아래 (x,topY) 에 캡슐 배지+라벨을 최대 2줄로 두고
   leadY0 가 있으면 점선 리더로 잇는다(가로막대 계열은 annPlan 이 처리).
   소비한 세로 높이(px)를 돌려준다 — 레인을 쌓는 호출자(heatmap)가 쓴다. */
function emitAnn(svg, a, x, topY, leadY0, maxW = 560) {
  const fs = annFont(a);
  const lines = wrapLines(a.label, maxW - ANN_PAD, fs);
  /* 가장 넓은 줄+배지 폭 기준으로 중심을 클램프 — 캔버스 밖으로 새지 않게 */
  const widest = Math.max(...lines.map((l) => tw(l, fs)), 40) + ANN_PAD;
  x = Math.max(70 + widest / 2, Math.min(x, R_EDGE - 10 - widest / 2));
  if (leadY0 != null)
    svg.push(`      <path d="M${r2(x)},${r2(leadY0)} L${r2(x)},${r2(topY - fs - 4)}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-dasharray="4 5"/>`);
  const x0 = r2(x - widest / 2);
  emitBadge(svg, x0, topY, a);
  lines.forEach((line, li) => {
    svg.push(`      <text x="${r2(x0 + ANN_PAD)}" y="${r2(topY + li * 24)}" font-size="${fs}" font-weight="${a.kind === 'main' ? 800 : 600}" class="${a.kind === 'main' ? 'k-t-o' : 'k-t-tag'}" text-anchor="start">${esc(line)}</text>`);
  });
  return lines.length * 24 + 8;
}

/* ── 3-D. stacked-bar — 막대당 구성 비교(세로 적층) ────────────────── */
function buildStacked() {
  const n = data.length;
  const BASE_Y = 470, PLOT = 350, NAME_Y = 516, H = 590;
  /* 세그먼트 색 — 이름 첫 등장 순으로 파랑 농도 순환(sequential), highlight=초점, oneoff=회색 */
  const segOrder = [];
  data.forEach((d) => d.segments.forEach((g) => { if (!segOrder.includes(g.name)) segOrder.push(g.name); }));
  /* 세그먼트 색 — ztd 참조: 초점=accent, 나머지는 회색 램프 + 종이색 분리선(stroke)으로
     서로를 가른다. 이름 순서로 램프를 순환한다. */
  const RAMP = ['var(--track-strong)', 'var(--track)', 'var(--muted)', 'var(--line)'];
  const segColor = (g) => g.oneoff ? 'var(--muted)'
    : highlights.includes(g.name) ? 'var(--accent)'
    : RAMP[segOrder.indexOf(g.name) % 4];
  const segFill = (g) => g.oneoff ? 'fill="var(--muted)" stroke="var(--soft)" stroke-width="2"'
    : `fill="${segColor(g)}" stroke="var(--paper)" stroke-width="2.5"`;
  const totalOf = (d) => d.total != null ? d.total : d.segments.reduce((a, g) => a + g.value, 0);
  const maxT = Math.max(...data.map(totalOf), 1e-9);
  const sc = PLOT / maxT;
  const barW = Math.min(240, Math.floor((VBW - 160 - (n - 1) * 90) / n));
  const span = n * barW + (n - 1) * 90;
  /* 세그먼트 브래킷은 끝 막대 우측에 라벨 자리가 필요하다 — 막대 묶음을 왼쪽으로 밀어 둔다 */
  let left = (VBW - span) / 2;
  if (chart.bridge === 'segment') left = Math.max(60, (VBW - span - 340) / 2);
  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  /* 범례 — 세그먼트 이름 칩(우상단, 첫 등장 순).
     칩 스와치는 막대 분리선(--paper)이 아니라 --line 테두리 — 배경 온도에 묻히지 않는다 */
  let lw = 0;
  const chips = segOrder.map((nm) => { const w = tw(nm, 20) + 52; lw += w; return { nm, w }; });
  let lx = R_EDGE - lw;
  chips.forEach(({ nm, w }) => {
    const g = data.flatMap((d) => d.segments).find((s) => s.name === nm);
    svg.push(`    <rect x="${r2(lx)}" y="24" width="16" height="14" rx="3" fill="${segColor(g || { name: nm })}" stroke="var(--line)" stroke-width="1.5"/>`);
    svg.push(`    <text x="${r2(lx + 22)}" y="37" font-size="20" font-weight="600" fill="var(--ink)">${esc(nm)}</text>`);
    lx += w;
  });
  svg.push(`    <path d="M60,${BASE_Y} L${R_EDGE},${BASE_Y}" class="k-ln-n"/>`);
  data.forEach((d, i) => {
    const x = left + i * (barW + 90), cx = x + barW / 2;
    const total = totalOf(d);
    let acc = 0;
    svg.push(`    <g data-step="${i + 1}">`);
    d.segments.forEach((g) => {
      const h = g.value * sc, y = BASE_Y - (acc + g.value) * sc;
      const labWhite = highlights.includes(g.name);
      svg.push(`      <rect x="${r2(x)}" y="${r2(y)}" width="${barW}" height="${r2(Math.max(h, 1))}" ${segFill(g)}/>`);
      if (h >= 22) svg.push(`      <text x="${r2(cx)}" y="${r2(y + h / 2 + 6)}" font-size="18" font-weight="700" ${labWhite ? 'class="k-t-w"' : 'fill="var(--ink)"'} text-anchor="middle">${esc(fmt(g.value))}</text>`);
      acc += g.value;
    });
    svg.push(`      <text x="${r2(cx)}" y="${r2(BASE_Y - total * sc - 18)}" font-size="26" font-weight="800" fill="var(--ink)" text-anchor="middle">${esc(fmt(total))}</text>`);
    svg.push(`      <text x="${r2(cx)}" y="${NAME_Y}" font-size="22" font-weight="700" fill="var(--ink)" text-anchor="middle">${esc(d.label)}</text>`);
    let ay = NAME_Y + 34;
    annBy(d.label).forEach((a) => { emitAnn(svg, a, cx, ay, NAME_Y + 8, barW + 60); ay += 56; });
    svg.push(`    </g>`);
  });
  /* 세그먼트 이름에 걸린 주석 — 첫 등장 막대에 단다 */
  segOrder.forEach((nm) => {
    const ai = data.findIndex((d) => d.segments.some((g) => g.name === nm));
    if (ai < 0) return;
    const cx = left + ai * (barW + 90) + barW / 2;
    annBy(nm).forEach((a) => emitAnn(svg, a, cx, NAME_Y + 34 + 0, NAME_Y + 8, barW + 60));
  });
  /* 총량 다리 — 첫·끝 막대 꼭대기를 점선으로 잇고 증감률 캡슐(+39%)과 절대 증감을 단다.
     끝 막대 단계와 함께 공개해 '마지막 펀치'가 되도록 한다. */
  if (chart.bridge === 'total' && n >= 2) {
    const t0 = totalOf(data[0]), tN = totalOf(data[n - 1]);
    const xA = left + barW, xB = left + (n - 1) * (barW + 90);
    const yA = BASE_Y - t0 * sc, yB = BASE_Y - tN * sc;
    const by = Math.min(yA, yB) - 44;
    const pct = t0 ? Math.round((tN - t0) / t0 * 100) : 0;
    const cxm = (xA + xB) / 2;
    const cap = `${fmtDelta(pct)}%`;
    const capW = Math.max(tw(cap, 21) + 32, 72);
    svg.push(`    <g data-step="${n}">`);
    svg.push(`      <path d="M${r2(xA)},${r2(yA)} L${r2(xA)},${r2(by)} L${r2(xB)},${r2(by)} L${r2(xB)},${r2(yB)}" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-dasharray="6 7"/>`);
    svg.push(`      <rect x="${r2(cxm - capW / 2)}" y="${r2(by - 15)}" width="${r2(capW)}" height="30" rx="15" fill="var(--accent)"/>`);
    svg.push(`      <text x="${r2(cxm)}" y="${r2(by + 7)}" font-size="21" font-weight="800" class="k-t-w" text-anchor="middle">${esc(cap)}</text>`);
    svg.push(`      <text x="${r2(cxm)}" y="${r2(by + 40)}" font-size="18" font-weight="700" class="k-t-o" text-anchor="middle">${esc(`${fmtDelta(tN - t0)}${chart.measure.unit}`)}</text>`);
    svg.push(`    </g>`);
  }
  /* 강조 세그먼트 브래킷 — 끝 막대의 묶음 세그먼트를 '}' 로 감싸고 합계·비중을 단다 */
  if (chart.bridge === 'segment') {
    const last = data[n - 1];
    const names = Array.isArray(chart.bridgeSegments) && chart.bridgeSegments.length ? chart.bridgeSegments : highlights;
    let acc = 0, yTop = null, yBot = null, segSum = 0;
    last.segments.forEach((g) => {
      const gy = BASE_Y - (acc + g.value) * sc;
      if (names.includes(g.name)) {
        if (yTop == null) yTop = gy;
        yBot = BASE_Y - acc * sc;
        segSum += g.value;
      }
      acc += g.value;
    });
    if (yTop != null) {
      const x0 = left + (n - 1) * (barW + 90) + barW, my = (yTop + yBot) / 2;
      const pct = Math.round(segSum / Math.max(totalOf(last), 1e-9) * 100);
      svg.push(`    <g data-step="${n}">`);
      svg.push(`      <path d="M${r2(x0 + 8)},${r2(yTop)} C${r2(x0 + 28)},${r2(yTop)} ${r2(x0 + 28)},${r2(my - 20)} ${r2(x0 + 28)},${r2(my - 8)} C${r2(x0 + 28)},${r2(my)} ${r2(x0 + 38)},${r2(my)} ${r2(x0 + 46)},${r2(my)} C${r2(x0 + 38)},${r2(my)} ${r2(x0 + 28)},${r2(my)} ${r2(x0 + 28)},${r2(my + 8)} C${r2(x0 + 28)},${r2(my + 20)} ${r2(x0 + 28)},${r2(yBot)} ${r2(x0 + 8)},${r2(yBot)}" fill="none" stroke="var(--accent)" stroke-width="3"/>`);
      svg.push(`      <text x="${r2(x0 + 54)}" y="${r2(my + 7)}" font-size="24" font-weight="800" class="k-t-o">${esc(`${fmt(segSum)}${chart.measure.unit} (${pct}%)`)}</text>`);
      svg.push(`    </g>`);
    } else warn(`bridge:"segment" — 끝 막대에 대상 세그먼트(${names.join('|')})가 없다`);
  }
  return section(svg, { bars: n, steps: n });
}

/* ── 3-E. line — 시계열 추이(계열 ≤4, fill 면적 변형) ──────────────── */
function buildLine() {
  const series = chart.series;
  const n = data.length;
  const L = 150, R = R_EDGE, TOP = 96, BASE_Y = 470, PLOT = 340, H = 580;
  const allV = series.flatMap((s) => s.points);
  let lo = Math.min(0, ...allV), hi = Math.max(...allV, 1e-9);
  const pad = (hi - lo) * 0.06 || 1;
  hi += pad; if (lo < 0) lo -= pad;
  const X = (i) => L + (n > 1 ? (R - L) * i / (n - 1) : (R - L) / 2);
  const Y = (v) => BASE_Y - (v - lo) / (hi - lo) * PLOT;
  const SCOL = ['var(--ink)', 'var(--track-strong)', 'var(--soft)', 'var(--muted)'];
  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  /* 눈금 — 보기 좋은 값(1·2·2.5·5×10^k) 간격으로 — 중간값 눈금(11.9 같은)을 없앤다 */
  const niceStep = (raw) => {
    const e = 10 ** Math.floor(Math.log10(raw));
    for (const m of [1, 2, 2.5, 5, 10]) if (m * e >= raw) return m * e;
    return 10 * e;
  };
  const stepV = niceStep((hi - lo) / 4);
  const t0 = Math.ceil(lo / stepV) * stepV;
  const tN = Math.floor(hi / stepV) * stepV;
  if (tN > t0 && (tN - t0) / stepV <= 8)
    for (let v = t0; v <= tN + 1e-9; v += stepV) {
      const y = r2(Y(v));
      svg.push(`    <path d="M${L},${y} L${R},${y}" stroke="var(--grid)" stroke-width="2.5"/>`);
      svg.push(`    <text x="${L - 14}" y="${y + 7}" font-size="20" fill="var(--soft)" text-anchor="end">${esc(fmt(Math.round(v * 10) / 10))}</text>`);
    }
  else
    for (let i = 0; i <= 4; i++) {
      const v = lo + (hi - lo) * i / 4, y = r2(Y(v));
      svg.push(`    <path d="M${L},${y} L${R},${y}" stroke="var(--grid)" stroke-width="2.5"/>`);
      svg.push(`    <text x="${L - 14}" y="${y + 7}" font-size="20" fill="var(--soft)" text-anchor="end">${esc(fmt(Math.round(v * 10) / 10))}</text>`);
    }
  svg.push(`    <path d="M${L},${BASE_Y} L${R},${BASE_Y}" fill="none" stroke="var(--line)" stroke-width="2.5"/>`);
  /* x 라벨 — 슬롯보다 길면 −38° 회전 */
  const slot = n > 1 ? (R - L) / (n - 1) : R - L;
  const rot = data.some((d) => tw(d.label, 22) > slot - 14);
  data.forEach((d, i) => {
    const x = r2(X(i));
    svg.push(rot
      ? `    <text x="${x}" y="${BASE_Y + 34}" font-size="20" font-weight="600" fill="var(--ink)" text-anchor="end" transform="rotate(-38 ${x} ${BASE_Y + 34})">${esc(d.label)}</text>`
      : `    <text x="${x}" y="${BASE_Y + 38}" font-size="20" font-weight="600" fill="var(--ink)" text-anchor="middle">${esc(d.label)}</text>`);
  });
  /* 계열 범례(우상단) */
  let lw = 0;
  const chips = series.map((s) => { const w = tw(s.name, 20) + 60; lw += w; return { s, w }; });
  let lx = R - lw;
  chips.forEach(({ s, w }, si) => {
    const col = highlights.includes(s.name) ? 'var(--accent)' : SCOL[si % 4];
    svg.push(`    <path d="M${r2(lx)},30 L${r2(lx + 28)},30" stroke="${col}" stroke-width="5"/>`);
    svg.push(`    <text x="${r2(lx + 36)}" y="37" font-size="20" font-weight="600" fill="var(--ink)">${esc(s.name)}</text>`);
    lx += w;
  });
  series.forEach((s, si) => {
    const col = highlights.includes(s.name) ? 'var(--accent)' : SCOL[si % 4];
    const pts = s.points.map((v, i) => `${r2(X(i))},${r2(Y(v))}`);
    svg.push(`    <g data-step="${si + 1}">`);
    if (s.fill)
      svg.push(`      <path d="M${pts.join(' L')} L${r2(X(n - 1))},${BASE_Y} L${r2(X(0))},${BASE_Y} Z" fill="${col}" opacity=".14"/>`);
    svg.push(`      <path d="M${pts.join(' L')}" fill="none" stroke="${col}" stroke-width="4" stroke-linejoin="round"/>`);
    s.points.forEach((v, i) => {
      svg.push(`      <circle cx="${r2(X(i))}" cy="${r2(Y(v))}" r="5.5" fill="${col}"/>`);
    });
    const lx2 = X(n - 1), ly2 = Y(s.points[n - 1]);
    svg.push(`      <text x="${r2(lx2 + 14)}" y="${r2(ly2 + 8)}" font-size="24" font-weight="800" fill="var(--ink)">${esc(fmt(s.points[n - 1]))}</text>`);
    annBy(s.name).forEach((a) => emitAnn(svg, a, Math.min(lx2 - 40, R_EDGE - 300), TOP + 10, ly2 - 10, 620));
    svg.push(`    </g>`);
  });
  /* 끝점 격차 브리지 — 사이드카 결합 장에서 문장 캡슐 대신 수치 기호만 남긴다 */
  if (chart.endDelta && series.length >= 2) {
    const vA = series[0].points[n - 1], vB = series[1].points[n - 1];
    const xE = X(n - 1), yA = Y(vA), yB = Y(vB);
    const d = vA - vB, r = vB ? vA / vB : 0;
    const u = chart.measure.unit === '%' ? '%p' : chart.measure.unit;
    const dStr = u === '%p' ? (Math.round(d * 10) / 10).toFixed(1) : fmt(Math.round(d * 10) / 10);
    const lbl = `${d > 0 ? '+' : ''}${dStr}${u} · ${fmt(Math.round(r * 10) / 10)}×`;
    svg.push(`    <g data-step="${series.length}">`);
    svg.push(`      <path d="M${r2(xE - 12)},${r2(yA)} L${r2(xE - 26)},${r2(yA + 8)} L${r2(xE - 26)},${r2(yB - 8)} L${r2(xE - 12)},${r2(yB)}" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-dasharray="6 5"/>`);
    svg.push(`      <text x="${r2(xE - 42)}" y="${r2((yA + yB) / 2 + 7)}" font-size="22" font-weight="800" class="k-t-o" text-anchor="end">${esc(lbl)}</text>`);
    svg.push(`    </g>`);
  }
  /* x 라벨에 걸린 주석 — 해당 눈금 아래 */
  data.forEach((d, i) => {
    let ay = BASE_Y + (rot ? 96 : 74);
    annBy(d.label).forEach((a) => { emitAnn(svg, a, Math.max(160, Math.min(X(i), R_EDGE - 100)), ay, null, 700); ay += 56; });
  });
  return section(svg, { bars: series.length, steps: series.length });
}

/* ── 3-F. scatter — 상관·분포(버블 겸용) ─────────────────────────── */
function buildScatter() {
  const L = 170, R = R_EDGE, TOP = 90, BOT = 460, H = 580;
  const xs = data.map((d) => d.x), ys = data.map((d) => d.y);
  const padR = (a, b) => { const p = (b - a) * 0.08 || Math.abs(a) * 0.08 || 1; return [a - p, b + p]; };
  const [x0, x1] = padR(Math.min(...xs), Math.max(...xs));
  const [y0, y1] = padR(Math.min(...ys), Math.max(...ys));
  const X = (v) => L + (v - x0) / (x1 - x0) * (R - L);
  const Y = (v) => BOT - (v - y0) / (y1 - y0) * (BOT - TOP);
  const sizes = data.map((d) => d.size || 0);
  const maxS = Math.max(...sizes, 0);
  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  svg.push(`    <path d="M${L},${TOP} L${L},${BOT} L${R},${BOT}" fill="none" stroke="var(--line)" stroke-width="2.5"/>`);
  svg.push(`    <text x="${L}" y="${BOT + 34}" font-size="20" fill="var(--soft)" text-anchor="middle">${esc(fmt(Math.round(x0 * 10) / 10))}</text>`);
  svg.push(`    <text x="${R}" y="${BOT + 34}" font-size="20" fill="var(--soft)" text-anchor="middle">${esc(fmt(Math.round(x1 * 10) / 10))}</text>`);
  svg.push(`    <text x="${L - 14}" y="${TOP + 4}" font-size="20" fill="var(--soft)" text-anchor="end">${esc(fmt(Math.round(y1 * 10) / 10))}</text>`);
  svg.push(`    <text x="${L - 14}" y="${BOT + 4}" font-size="20" fill="var(--soft)" text-anchor="end">${esc(fmt(Math.round(y0 * 10) / 10))}</text>`);
  svg.push(`    <text x="${(L + R) / 2}" y="${BOT + 78}" font-size="22" font-weight="700" fill="var(--ink)" text-anchor="middle">${esc(chart.measure.x)}</text>`);
  svg.push(`    <text x="${L}" y="${TOP - 24}" font-size="22" font-weight="700" fill="var(--ink)">${esc(chart.measure.y)}</text>`);
  /* 라벨 겹침 회피 — 같은 y 띠에 겹치면 아래로 30씩 내린다 */
  const placed = [];
  const labelXY = (d, px, py, r) => {
    const right = px < R - 220;
    let lx = right ? px + r + 12 : px - r - 12, ly = py + 7;
    while (placed.some((q) => Math.abs(q.ly - ly) < 26 && (right ? lx < q.lx + q.w && lx + q.w > q.lx - q.w : lx > q.lx - q.w))) ly += 30;
    placed.push({ lx, ly, w: tw(d.label, 20) });
    return { lx, ly, anchor: right ? 'start' : 'end' };
  };
  let step = 2;
  const emit = (d, st) => {
    const px = X(d.x), py = Y(d.y);
    const r = d.size ? Math.max(6, Math.sqrt(d.size / maxS) * 22) : 9;
    const hot = highlights.includes(d.label) || d.highlight;
    svg.push(`    <g data-step="${st}">`);
    svg.push(`      <circle cx="${r2(px)}" cy="${r2(py)}" r="${r2(r)}" fill="${hot ? 'var(--accent)' : 'var(--track-strong)'}" opacity="${hot ? '.95' : '.72'}"/>`);
    if (d.label) {
      const { lx, ly, anchor } = labelXY(d, px, py, r);
      svg.push(`      <text x="${r2(lx)}" y="${r2(ly)}" font-size="20" font-weight="${hot ? 800 : 600}" fill="var(--ink)" text-anchor="${anchor}">${esc(d.label)}</text>`);
    }
    annBy(d.label).forEach((a) => emitAnn(svg, a, Math.max(200, Math.min(px, R_EDGE - 100)), Math.min(py + r + 40, H - 30), py + r + 6, 560));
    svg.push(`    </g>`);
  };
  svg.push(`    <g data-step="1">`);
  data.forEach((d) => { if (!d.label) { const px = X(d.x), py = Y(d.y); const r = d.size ? Math.max(6, Math.sqrt(d.size / maxS) * 22) : 9; svg.push(`      <circle cx="${r2(px)}" cy="${r2(py)}" r="${r2(r)}" fill="var(--track-strong)" opacity=".72"/>`); } });
  svg.push(`    </g>`);
  data.forEach((d) => { if (d.label) emit(d, step++); });
  return section(svg, { bars: data.length, steps: step - 1 });
}

/* ── 3-G. heatmap — 행×열 밀도(단일 hue 농도) ─────────────────────── */
function buildHeatmap() {
  const rl = data.rows.map((r) => (typeof r === 'string' ? r : r.label));
  const cl = data.cols.map((c) => (typeof c === 'string' ? c : c.label));
  const gridX = 250, gridY = 96;
  const cw = (R_EDGE - gridX) / cl.length;
  const rh = Math.min(66, 380 / rl.length);
  const gridH = rh * rl.length;
  /* 주석 레인 높이 사전 계산 — H 결정에 반영. 열 주석은 열 폭(cw) 안으로 접는다. */
  const colAnnW = Math.max(cw - 24, 140);
  const rowAnnW = Math.min(900, R_EDGE - gridX - 80);
  const laneH = (a, w) => wrapLines(a.label, w - ANN_PAD, annFont(a)).length * 24 + 26;
  let totalAnnH = 0;
  rl.forEach((nm) => annBy(nm).forEach((a) => { totalAnnH += laneH(a, rowAnnW); }));
  cl.forEach((nm) => annBy(nm).forEach((a) => { totalAnnH += laneH(a, colAnnW); }));
  const H = gridY + gridH + 96 + totalAnnH;
  const vmap = new Map();
  data.cells.forEach((c) => {
    const ri = typeof c.r === 'string' ? rl.indexOf(c.r) : c.r;
    const ci = typeof c.c === 'string' ? cl.indexOf(c.c) : c.c;
    vmap.set(`${ri},${ci}`, c.v);
  });
  const vs = [...vmap.values()];
  const vmin = Math.min(...vs), vmax = Math.max(...vs, vmin + 1e-9);
  const hot = (r, c) => highlights.includes(rl[r]) || highlights.includes(cl[c]);
  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  cl.forEach((nm, c) => {
    svg.push(`    <text x="${r2(gridX + c * cw + cw / 2)}" y="${gridY - 16}" font-size="20" font-weight="700" fill="var(--ink)" text-anchor="middle">${esc(nm)}</text>`);
  });
  /* 주석 레인 커서 — 행·열 주석을 격자 아래로 한 줄씩 순차 누적한다.
     같은 y 단계에 두 블록이 나란히 서지 않으므로 수평 충돌(≥60px 여백 요건)이 원천 제거된다. */
  let annLane = gridY + gridH + 64;
  rl.forEach((nm, r) => {
    const y = gridY + r * rh;
    svg.push(`    <g data-step="${r + 1}">`);
    svg.push(`      <text x="${gridX - 16}" y="${r2(y + rh / 2 + 7)}" font-size="22" font-weight="700" fill="var(--ink)" text-anchor="end">${esc(nm)}</text>`);
    cl.forEach((cnm, c) => {
      const key = `${r},${c}`;
      const x = r2(gridX + c * cw), yv = r2(y + 2), w = r2(cw - 4), h = r2(rh - 4);
      if (!vmap.has(key)) {
        svg.push(`      <rect x="${x}" y="${yv}" width="${w}" height="${h}" fill="none" stroke="var(--soft)" stroke-width="2" stroke-dasharray="6 6"/>`);
        return;
      }
      const v = vmap.get(key);
      const pct = Math.round(12 + 80 * ((v - vmin) / (vmax - vmin)));
      /* 단일 색조 히트맵(ztd 참조): 강조 열/행=accent, 본 셀=슬레이트 blue —
         재조정 팔레트의 blue 는 회청색이라 강조와 자연 분리된다 */
      const color = hot(r, c) ? 'var(--accent)' : 'var(--blue)';
      svg.push(`      <rect x="${x}" y="${yv}" width="${w}" height="${h}" rx="4" style="fill:color-mix(in srgb, ${color} ${pct}%, transparent)"/>`);
      if (cw >= 64 && rh >= 34)
        svg.push(`      <text x="${r2(gridX + c * cw + cw / 2)}" y="${r2(y + rh / 2 + 7)}" font-size="20" font-weight="700" ${pct > 55 ? 'class="k-t-w"' : 'fill="var(--ink)"'} text-anchor="middle">${esc(fmt(v))}</text>`);
    });
    /* 행 주석 — 자기 행 단계 안에서, 그리드 중앙 정렬 레인 */
    annBy(nm).forEach((a) => {
      annLane += emitAnn(svg, a, gridX + (R_EDGE - gridX) / 2, annLane, null, rowAnnW) + 18;
    });
    svg.push(`    </g>`);
  });
  /* 열 주석 — 해당 열 중심에서 열 폭(colAnnW)으로 접어 같은 단계 충돌을 막고,
     격자 하단에서 리더로 연결한다 */
  cl.forEach((nm, c) => {
    annBy(nm).forEach((a) => {
      annLane += emitAnn(svg, a, r2(gridX + c * cw + cw / 2), annLane, gridY + gridH + 8, colAnnW) + 18;
    });
  });
  /* 농도 범례 — min→max 단일 hue 그라디언트. 단위 태그와 같은 행의 우측 끝:
     하단 두면 사이드카 결합 시 주석 레인·푸터와 충돌한다(재크리틱 기술-1) */
  svg.push(`    <defs><linearGradient id="hm-grad" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="var(--blue)" stop-opacity=".14"/><stop offset="1" stop-color="var(--blue)" stop-opacity=".92"/></linearGradient></defs>`);
  svg.push(`    <text x="${R_EDGE - 196}" y="36" font-size="18" fill="var(--soft)" text-anchor="end">${esc(fmt(vmin))}</text>`);
  svg.push(`    <rect x="${R_EDGE - 186}" y="24" width="140" height="14" rx="3" fill="url(#hm-grad)"/>`);
  svg.push(`    <text x="${R_EDGE - 36}" y="36" font-size="18" fill="var(--soft)">${esc(fmt(vmax))}</text>`);
  return section(svg, { bars: rl.length, steps: rl.length });
}

/* ── 3-H. matrix-2x2 — 전략 사분면 ───────────────────────────────── */
function buildMatrix() {
  const ax = chart.axes.x, ay2 = chart.axes.y;
  const PX0 = 300, PX1 = R_EDGE, PY0 = 80, PY1 = 520, H = 620;
  const X = (v) => PX0 + (v - ax.min) / Math.max(ax.max - ax.min, 1e-9) * (PX1 - PX0);
  const Y = (v) => PY1 - (v - ay2.min) / Math.max(ay2.max - ay2.min, 1e-9) * (PY1 - PY0);
  const midX = X((ax.min + ax.max) / 2), midY = Y((ay2.min + ay2.max) / 2);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const quad = chart.quadrants || {};
  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  svg.push(`    <g data-step="1">`);
  /* 목표 사분면 — 옅은 초점색 틴트 + 라벨 강조(리더는 아래 점 방출에서) */
  const tq = chart.targetQuadrant ? { tr: 'ne', tl: 'nw', br: 'se', bl: 'sw' }[chart.targetQuadrant] : null;
  if (tq) {
    const qx = tq === 'nw' ? PX0 : midX, qy = (tq === 'nw' || tq === 'ne') ? PY0 : midY;
    /* 틴트는 rect 가 아니라 path 로 — 검사기가 보이는 rect 를 '상자'로 인식해 가장자리 라벨을 넘침으로 잡는 것을 피한다 */
    svg.push(`      <path d="M${r2(qx)},${r2(qy)} h${r2(PX1 - midX)} v${r2(PY1 - midY)} h${r2(midX - PX1)} Z" style="fill:color-mix(in srgb, var(--accent) 7%, transparent)"/>`);
  }
  svg.push(`      <rect x="${PX0}" y="${PY0}" width="${PX1 - PX0}" height="${PY1 - PY0}" fill="none" stroke="var(--line)" stroke-width="3"/>`);
  svg.push(`      <path d="M${r2(midX)},${PY0} L${r2(midX)},${PY1} M${PX0},${r2(midY)} L${PX1},${r2(midY)}" stroke="var(--soft)" stroke-width="2" stroke-dasharray="8 8"/>`);
  /* 사분면 라벨 — 네 귀퉁이 안쪽. 목표 사분면은 초점색·굵게 */
  const q = [
    ['nw', quad.nw, PX0 + 22, PY0 + 34, 'start'], ['ne', quad.ne, PX1 - 22, PY0 + 34, 'end'],
    ['sw', quad.sw, PX0 + 22, PY1 - 18, 'start'], ['se', quad.se, PX1 - 22, PY1 - 18, 'end'],
  ];
  q.forEach(([k, t, x, y, a]) => {
    if (!t) return;
    const isT = tq === k;
    svg.push(`      <text x="${x}" y="${y}" font-size="21" font-weight="${isT ? 800 : 700}" class="${isT ? 'k-t-o' : 'k-t-tag'}" text-anchor="${a}">${esc(t)}</text>`);
  });
  /* 축 라벨 — 모델 라벨에 이미 화살표가 있으면 중복 부착하지 않는다(agy 치명-1) */
  const stripArrow = (t) => String(t).replace(/[\s]*[→↔↘←↓↑]+\s*$/u, '').trim();
  svg.push(`      <text x="${PX1}" y="${PY1 + 46}" font-size="22" font-weight="700" fill="var(--ink)" text-anchor="end">${esc(stripArrow(ax.label) || ax.label)} →</text>`);
  svg.push(`      <text x="${PX0}" y="${PY0 - 20}" font-size="22" font-weight="700" fill="var(--ink)">↑ ${esc(stripArrow(ay2.label) || ay2.label)}</text>`);
  svg.push(`    </g>`);
  /* 점 먼저 계산 → 라벨 레인 배치(다른 점의 원도 피한다) → 주석은 라벨 바로 아래 레인(agy 치명-1) */
  const pts = data.map((d, i) => {
    const px = clamp(X(d.x), PX0 + 14, PX1 - 14), py = clamp(Y(d.y), PY0 + 14, PY1 - 14);
    if (px !== X(d.x) || py !== Y(d.y)) warn(`'${d.label}' 축 범위 밖 — 경계로 이동`);
    return { d, i, px, py, hot: highlights.includes(d.label) || d.highlight };
  });
  const ANN_W = 560;
  const placed = [];
  pts.forEach((p) => {
    p.lw = tw(p.d.label, 20) + 4;
    /* 후보 배치 — 점 근처(±22px)부터 우→좌→우상→좌상→아래→위 순.
       어느 자리도 못 찾으면 우측 자리에서 아래로 한 레인씩 민다(점에서 24px 안팎 유지).
       재크리틱 기술-2: 같은 좌표 포개짐·점에서 200px 이탈 방지 */
    const spot = (dx, dy, anch) => {
      const x0 = p.px + dx, y0 = p.py + dy;
      const l = anch === 'start' ? x0 : anch === 'end' ? x0 - p.lw : x0 - p.lw / 2;
      const r = l + p.lw;
      if (l < PX0 + 4 || r > PX1 - 4 || y0 < PY0 + 18 || y0 > PY1 - 4) return null;
      const bad =
        placed.some((q) => Math.abs(q.ly - y0) < 26 && l < q.cx + q.hw && r > q.cx - q.hw) ||
        pts.some((q2) => q2 !== p && q2.px > l - 14 && q2.px < r + 14 && Math.abs(q2.py - (y0 - 7)) < 24);
      return bad ? null : { lx: x0, ly: y0, anch, cx: (l + r) / 2 };
    };
    let s = spot(22, 7, 'start') || spot(-22, 7, 'end') ||
            spot(22, -19, 'start') || spot(-22, -19, 'end') ||
            spot(0, 34, 'middle') || spot(0, -22, 'middle');
    if (!s) {
      /* 후보 전멸 — 플롯 끝에 붙여(end→start) 아래 레인으로만 이동: viewBox 밖으로 새지 않게 */
      for (const [anch, x0] of [['end', PX1 - 22], ['start', PX0 + 22]]) {
        const l = anch === 'end' ? x0 - p.lw : x0, r = l + p.lw;
        /* 자기 점이 라벨 폭 안이면 그 아래 한 레인부터 시작 — 점을 글자로 덮지 않는다 */
        let y0 = (p.px > l - 8 && p.px < r + 8) ? p.py + 40 : p.py + 7;
        const hit = () =>
          placed.some((q) => Math.abs(q.ly - y0) < 26 && l < q.cx + q.hw && r > q.cx - q.hw) ||
          pts.some((q2) => q2 !== p && q2.px > l - 14 && q2.px < r + 14 && Math.abs(q2.py - (y0 - 7)) < 24);
        while (hit() && y0 < PY1 - 4) y0 += 28;
        if (y0 <= PY1 - 4) { s = { lx: x0, ly: y0, anch, cx: (l + r) / 2 }; break; }
      }
      if (!s) s = { lx: p.px + 22, ly: p.py + 7, anch: 'start', cx: p.px + 22 + p.lw / 2 };
    }
    placed.push({ ly: s.ly, cx: s.cx, hw: p.lw / 2 });
    p.lx = s.lx; p.ly = s.ly; p.lcx = s.cx; p.anch = s.anch;
    /* 주석 줄 — 이 점의 라벨 아래에 이어서 배치하고 레인에 등록한다(나중 점이 피한다) */
    const anns2 = annBy(p.d.label);
    if (!anns2.length) { p.annTop = null; return; }
    let ay = p.ly + 32, first = null;
    const annHit = (w2) =>
      placed.some((q) => Math.abs(q.ly - ay) < 26 && Math.abs(q.cx - p.px) < q.hw + w2 / 2) ||
      pts.some((q2) => q2 !== p && Math.abs(q2.py - ay + 6) < 26 && Math.abs(q2.px - p.px) < w2 / 2 + 16);
    anns2.forEach((an) => {
      const fs2 = annFont(an);
      wrapLines(an.label, ANN_W - ANN_PAD, fs2).forEach((l) => {
        const w2 = tw(l, fs2);
        while (annHit(w2) && ay < PY1 - 4) ay += 28;
        if (first == null) first = ay;
        placed.push({ ly: ay, cx: p.px, hw: Math.max(w2 / 2, 80) });
        ay += 26;
      });
    });
    p.annTop = Math.min(first, PY1 - 8);
  });
  /* 모션 압축 — step1 축/사분면, step2 비초점 점 일괄, step3 초점 점+주석 일괄 */
  const emitPoint = (p) => {
    const { px, py, hot, d } = p;
    svg.push(`      <circle cx="${r2(px)}" cy="${r2(py)}" r="${hot ? 13 : 10}" fill="${hot ? 'var(--accent)' : 'var(--track-strong)'}" opacity="${hot ? '.95' : '.78'}"/>`);
    /* 라벨이 원래 자리에서 한 레인 이상 밀려났을 때만 점→라벨 리더선을 긋는다 */
    if (Math.abs(p.ly - (p.py + 7)) > 20)
      svg.push(`      <path d="M${r2(px)},${r2(py + 12)} L${r2(p.lcx)},${r2(p.ly - 16)}" fill="none" stroke="var(--line)" stroke-width="1.5" stroke-dasharray="3 4"/>`);
    svg.push(`      <text x="${r2(p.lx)}" y="${r2(p.ly)}" font-size="20" font-weight="${hot ? 800 : 600}" fill="var(--ink)" text-anchor="${p.anch}" paint-order="stroke" stroke="var(--paper)" stroke-width="4" stroke-linejoin="round">${esc(d.label)}</text>`);
    if (p.annTop != null)
      annBy(d.label).forEach((a) => emitAnn(svg, a, Math.max(PX0 + 80, Math.min(px, PX1 - 80)), p.annTop, p.annTop - p.ly > 40 ? p.ly + 8 : null, ANN_W));
  };
  svg.push(`    <g data-step="2">`);
  pts.filter((p) => !p.hot).forEach(emitPoint);
  svg.push(`    </g>`);
  svg.push(`    <g data-step="3">`);
  pts.filter((p) => p.hot).forEach(emitPoint);
  svg.push(`    </g>`);
  return section(svg, { bars: data.length, steps: 3 });
}

/* ── 3-I. tornado — 민감도(대칭축 가로 발산 쌍) ────────────────────── */
function buildTornado() {
  const rows = [...data].sort((a, b) => (b.high - b.low) - (a.high - a.low) || String(a.label).localeCompare(String(b.label)));
  const ROW = 84, BAR_H = 52, TOP = 64;
  /* 행 라벨이 캔버스 왼쪽 밖으로 새지 않게 HALF 를 라벨 폭으로도 상한한다(사이드카 1040 폭) */
  const ZERO = Math.round(VBW / 2) + 50, LBL_W = Math.max(...rows.map((d) => tw(d.label, 26))) + 32;
  const HALF = Math.min(560, R_EDGE - ZERO - 60, ZERO - LBL_W - 24), LABEL_X = ZERO - HALF - 24;
  const maxA = Math.max(...rows.flatMap((d) => [Math.abs(d.low), Math.abs(d.high)]), 1e-9);
  /* 행별 주석 줄 수만큼 행 높이를 늘린다 — 2줄 주석이 다음 행 막대와 겹치는 것을 막는다(agy 치명-2/3) */
  const rowExtra = rows.map((d) => {
    const lines = annBy(d.label).reduce((a2, an) => a2 + wrapLines(an.label, 900 - ANN_PAD, annFont(an)).length, 0);
    return lines ? lines * 24 + 14 : 0;
  });
  const H = TOP + rows.reduce((a2, _d, i) => a2 + ROW + rowExtra[i], 0) + 76;   /* X축 눈금-방법론 줄 12px+ */
  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  svg.push(`    <line x1="${ZERO - HALF}" y1="${H - 56}" x2="${ZERO + HALF}" y2="${H - 56}" stroke="var(--soft)" stroke-width="3"/>`);
  svg.push(`    <line x1="${ZERO}" y1="64" x2="${ZERO}" y2="${H - 56}" stroke="var(--soft)" stroke-width="2.5"/>`);
  svg.push(`    <line x1="${ZERO - HALF}" y1="64" x2="${ZERO - HALF}" y2="${H - 56}" stroke="var(--line)" stroke-width="2" stroke-dasharray="6 8"/>`);
  svg.push(`    <line x1="${ZERO + HALF}" y1="64" x2="${ZERO + HALF}" y2="${H - 56}" stroke="var(--line)" stroke-width="2" stroke-dasharray="6 8"/>`);
  svg.push(`    <text x="${ZERO - HALF}" y="${H - 24}" text-anchor="middle" font-size="22" fill="var(--soft)">−${esc(fmt(maxA))}</text>`);
  svg.push(`    <text x="${ZERO}" y="${H - 24}" text-anchor="middle" font-size="22" fill="var(--soft)">0</text>`);
  svg.push(`    <text x="${ZERO + HALF}" y="${H - 24}" text-anchor="middle" font-size="22" fill="var(--soft)">+${esc(fmt(maxA))}</text>`);
  rows.forEach((d, i) => {
    const y = TOP + rows.slice(0, i).reduce((a2, _r, j) => a2 + ROW + rowExtra[j], 0), cy = y + BAR_H / 2 + 8;
    const wl = Math.abs(d.low) / maxA * HALF, wh = Math.abs(d.high) / maxA * HALF;
    const rowHot = highlights.includes(d.label);
    /* 최대 음수 막대의 값 라벨이 항목명(LABEL_X)과 겹치면 막대 안쪽(밝은 글자)로 뺀다(agy 치명-2) */
    const lowStr = fmtDelta(d.low), inLow = ZERO - wl - 14 - tw(lowStr, 24) < LABEL_X + 14;
    svg.push(`    <g data-step="${i + 1}">`);
    svg.push(`      <text x="${LABEL_X}" y="${cy}" text-anchor="end" font-size="26" font-weight="700" fill="var(--ink)">${esc(d.label)}</text>`);
    svg.push(`      <rect x="${r2(ZERO - wl)}" y="${y}" width="${r2(wl)}" height="${BAR_H}" rx="6" fill="${rowHot ? 'var(--accent)' : 'var(--track-strong)'}" ${growR}/>`);
    svg.push(`      <rect x="${ZERO}" y="${y}" width="${r2(wh)}" height="${BAR_H}" rx="6" fill="${rowHot ? 'var(--accent)' : 'var(--track)'}" ${growL}/>`);
    svg.push(`      <text x="${r2(inLow ? ZERO - wl + 16 : ZERO - wl - 14)}" y="${cy}" font-size="24" font-weight="800" fill="${inLow ? 'var(--paper)' : 'var(--ink)'}" text-anchor="${inLow ? 'start' : 'end'}">${esc(lowStr)}</text>`);
    svg.push(`      <text x="${r2(ZERO + wh + 14)}" y="${cy}" font-size="24" font-weight="800" fill="var(--ink)">${esc(fmtDelta(d.high))}</text>`);
    let ay = cy + 46;
    annBy(d.label).forEach((a) => { emitAnn(svg, a, ZERO, ay, cy + 8, 900); ay += 56; });
    svg.push(`    </g>`);
  });
  return section(svg, { bars: rows.length, steps: rows.length });
}

/* ── 3-J. sankey — 흐름(데이터 구동, 42-sankey-flow 시각 언어) ─────── */
function buildSankey() {
  const nodes = data.nodes, flows = data.flows;
  const idmap = new Map(nodes.map((n) => [n.id, n]));
  const tin = new Map(), tout = new Map(), adj = new Map();
  flows.forEach((f) => {
    tin.set(f.to, (tin.get(f.to) || 0) + f.value);
    tout.set(f.from, (tout.get(f.from) || 0) + f.value);
    (adj.get(f.from) || adj.set(f.from, []).get(f.from)).push(f.to);
  });
  const thr = (id) => Math.max(tin.get(id) || 0, tout.get(id) || 0);
  /* 열 배정 — 최장 경로 깊이(위상 정렬) */
  const depth = new Map();
  const indeg = new Map(nodes.map((n) => [n.id, tin.has(n.id) ? (data.flows.filter((f) => f.to === n.id).length) : 0]));
  const queue = nodes.filter((n) => !tin.has(n.id)).map((n) => n.id);
  queue.forEach((id) => depth.set(id, 0));
  const seen = new Set(queue);
  while (queue.length) {
    const u = queue.shift();
    for (const v of adj.get(u) || []) {
      depth.set(v, Math.max(depth.get(v) || 0, depth.get(u) + 1));
      if (!seen.has(v)) { seen.add(v); queue.push(v); }
    }
  }
  const cols = Math.max(...depth.values(), 0) + 1;
  const colNodes = Array.from({ length: cols }, () => []);
  nodes.forEach((n) => colNodes[depth.get(n.id) || 0].push(n));
  const NODE_W = 170, TOP = 90, PLOT_H = 380;
  const colTotal = colNodes.map((cn) => cn.reduce((a, n) => a + thr(n.id), 0));
  const sc = PLOT_H / Math.max(...colTotal, 1e-9);
  const colX = (c) => cols > 1 ? 60 + c * (VBW - 120 - NODE_W) / (cols - 1) : (VBW - NODE_W) / 2;
  /* 노드 y — 열 안에서 균등 간격 쌓기 */
  const pos = new Map();
  colNodes.forEach((cn, c) => {
    const hs = cn.map((n) => Math.max(thr(n.id) * sc, 26));
    const gap = cn.length > 1 ? Math.max(18, (PLOT_H - hs.reduce((a, b) => a + b, 0)) / (cn.length - 1)) : 0;
    let y = TOP + (cn.length > 1 ? 0 : (PLOT_H - hs[0]) / 2);
    cn.forEach((n, i) => { pos.set(n.id, { x: colX(c), y, h: hs[i], c }); y += hs[i] + gap; });
  });
  const H = TOP + PLOT_H + 110;
  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  const roleCls = (c) => c === 0 ? 'k-solid-b' : c === cols - 1 ? 'k-solid-o' : 'k-solid-n';
  /* 흐름 밴드 — 소스 노드 오른쪽 → 대상 왼쪽, 두께 = 값×스케일 */
  const inOff = new Map(), outOff = new Map();
  const flowStep = new Map();
  flows.forEach((f, i) => flowStep.set(i, Math.max(depth.get(f.from) + 1, depth.get(f.to))));
  [...Array(cols).keys()].forEach((c) => {
    const stepFlows = flows.map((f, i) => [f, i]).filter(([, i]) => flowStep.get(i) === c + 1 || (cols === 1 && c === 0));
    if (!stepFlows.length) return;
    svg.push(`    <g data-step="${c + 1}">`);
    stepFlows.forEach(([f]) => {
      const s = pos.get(f.from), t = pos.get(f.to);
      const w = Math.max(f.value * sc, 3);
      const sy = s.y + (outOff.get(f.from) || 0), ty = t.y + (inOff.get(f.to) || 0);
      outOff.set(f.from, (outOff.get(f.from) || 0) + w);
      inOff.set(f.to, (inOff.get(f.to) || 0) + w);
      const x0 = s.x + NODE_W, x1 = t.x, cx = (x0 + x1) / 2;
      const hot = highlights.includes(idmap.get(f.to).label) || highlights.includes(idmap.get(f.from).label);
      svg.push(`      <path d="M${r2(x0)},${r2(sy)} C${r2(cx)},${r2(sy)} ${r2(cx)},${r2(ty)} ${r2(x1)},${r2(ty)} L${r2(x1)},${r2(ty + w)} C${r2(cx)},${r2(ty + w)} ${r2(cx)},${r2(sy + w)} ${r2(x0)},${r2(sy + w)} Z" fill="${hot ? 'var(--accent)' : 'var(--track-strong)'}" opacity="${hot ? '.7' : '.45'}"/>`);
    });
    svg.push(`    </g>`);
  });
  /* 노드 — 열별 단계에 라벨·값 */
  colNodes.forEach((cn, c) => {
    svg.push(`    <g data-step="${c + 1}">`);
    cn.forEach((n) => {
      const p = pos.get(n.id);
      const cls = roleCls(c);
      svg.push(`      <rect x="${p.x}" y="${r2(p.y)}" width="${NODE_W}" height="${r2(p.h)}" class="${cls}"/>`);
      const label = n.label || n.id;
      const inner = tw(label, 22) <= NODE_W - 20;
      svg.push(inner
        ? `      <text x="${p.x + NODE_W / 2}" y="${r2(p.y + p.h / 2 + 7)}" font-size="22" font-weight="700" class="k-t-w" text-anchor="middle">${esc(label)}</text>`
        : `      <text x="${p.x + NODE_W / 2}" y="${r2(p.y - 10)}" font-size="20" font-weight="700" fill="var(--ink)" text-anchor="middle">${esc(label)}</text>`);
      svg.push(`      <text x="${p.x + NODE_W / 2}" y="${r2(p.y + p.h + 30)}" font-size="20" font-weight="700" fill="var(--ink)" text-anchor="middle">${esc(fmt(thr(n.id)))}</text>`);
      annBy(label).forEach((a) => emitAnn(svg, a, p.x + NODE_W / 2, TOP + PLOT_H + 76, p.y + p.h + 34, 420));
    });
    svg.push(`    </g>`);
  });
  return section(svg, { bars: nodes.length, steps: cols });
}

/* ── 3-K. pareto — 누적 곡선 + 내림차 막대 ────────────────────────── */
function buildPareto() {
  const rows = [...data].sort((a, b) => b.value - a.value || String(a.label).localeCompare(String(b.label)));
  const n = rows.length;
  const BASE_Y = 460, PLOT = 340, NAME_Y = 506, H = 590;
  const sum = rows.reduce((a, d) => a + d.value, 0) || 1e-9;
  const maxV = rows[0].value;
  const sc = PLOT / maxV;
  const barW = Math.min(170, Math.floor((VBW - 200 - (n - 1) * 46) / n));
  const span = n * barW + (n - 1) * 46;
  const left = (VBW - span) / 2;
  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  svg.push(`    <path d="M60,${BASE_Y} L${R_EDGE},${BASE_Y}" class="k-ln-n"/>`);
  /* 80% 임계선 + 우측 % 축 */
  const cumY = (p) => BASE_Y - (p / 100) * PLOT;
  svg.push(`    <path d="M60,${r2(cumY(80))} L${R_EDGE},${r2(cumY(80))}" class="k-ln-g"/>`);
  svg.push(`    <text x="${R_EDGE}" y="${r2(cumY(80)) - 10}" font-size="18" class="k-t-o" text-anchor="end" font-weight="700">80%</text>`);
  [0, 50, 100].forEach((p) => {
    svg.push(`    <text x="${R_EDGE + 20}" y="${r2(cumY(p)) + 7}" font-size="18" fill="var(--soft)">${p}%</text>`);
  });
  let acc = 0, prev = null;
  rows.forEach((d, i) => {
    acc += d.value;
    const cumpct = acc / sum * 100;
    const x = left + i * (barW + 46), cx = x + barW / 2;
    const h = d.value * sc, y = BASE_Y - h;
    const hot = highlights.includes(d.label);
    svg.push(`    <g data-step="${i + 1}">`);
    svg.push(`      <rect x="${r2(x)}" y="${r2(y)}" width="${barW}" height="${r2(h)}" rx="6" fill="${hot ? 'var(--accent)' : 'var(--track)'}" opacity="${hot ? '.95' : '.82'}" ${growB}/>`);
    svg.push(`      <text x="${r2(cx)}" y="${r2(y - 12)}" font-size="22" font-weight="800" fill="var(--ink)" text-anchor="middle">${esc(fmt(d.value))}</text>`);
    const cy2 = cumY(cumpct);
    if (prev) svg.push(`      <path d="M${r2(prev.x)},${r2(prev.y)} L${r2(cx)},${r2(cy2)}" fill="none" stroke="var(--accent)" stroke-width="4"/>`);
    svg.push(`      <circle cx="${r2(cx)}" cy="${r2(cy2)}" r="6" fill="var(--accent)"/>`);
    svg.push(`      <text x="${r2(cx)}" y="${r2(cy2 - 14)}" font-size="18" font-weight="700" class="k-t-o" text-anchor="middle">${Math.round(cumpct)}%</text>`);
    const slot = barW + 46;
    if (tw(d.label, 22) > slot - 10)
      svg.push(`      <text x="${r2(cx)}" y="${NAME_Y}" font-size="20" font-weight="700" fill="var(--ink)" text-anchor="end" transform="rotate(-38 ${r2(cx)} ${NAME_Y})">${esc(d.label)}</text>`);
    else
      svg.push(`      <text x="${r2(cx)}" y="${NAME_Y}" font-size="22" font-weight="700" fill="var(--ink)" text-anchor="middle">${esc(d.label)}</text>`);
    let ay = NAME_Y + 40;
    annBy(d.label).forEach((a) => { emitAnn(svg, a, cx, ay, NAME_Y + 10, barW + 40); ay += 56; });
    svg.push(`    </g>`);
    prev = { x: cx, y: cy2 };
  });
  return section(svg, { bars: n, steps: n });
}

/* ── 4. 방출 ─────────────────────────────────────────────────────── */
const BUILD = {
  'waterfall': buildWaterfall, 'ranked-bar-h': buildRanked, 'diverging-bar': buildDiverging,
  'stacked-bar': buildStacked, 'line': buildLine, 'scatter': buildScatter,
  'heatmap': buildHeatmap, 'matrix-2x2': buildMatrix, 'tornado': buildTornado,
  'sankey': buildSankey, 'pareto': buildPareto,
};
const doc = BUILD[chart.type]();
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
if (!quiet) report();
for (const w of warns) console.warn(`WARN: ${w}`);

function report() {
  console.log(`${chart.type} · bars=${doc.meta.bars} · steps=${doc.meta.steps} · viewBox ${VBW}폭`);
}
