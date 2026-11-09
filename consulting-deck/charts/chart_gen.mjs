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
  console.log(`chart_gen.mjs — 컨설팅 차트 생성기(waterfall · ranked-bar-h · diverging-bar)
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
  'waterfall':     { min: 3, max: 8,  archetype: 'waterfall', variant: 'bridge' },
  'ranked-bar-h':  { min: 3, max: 10, archetype: 'chart-bar', variant: 'ranked' },
  'diverging-bar': { min: 3, max: 9,  archetype: 'chart-bar', variant: 'diverging' },
};
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
if (!Array.isArray(chart.data)) fail('chart.data 는 배열이어야 한다');
if (!source || !source.text) fail('source.text 누락 — 출처 없는 수치는 쓸 수 없다');
if (source && typeof source.synthetic !== 'boolean') fail('source.synthetic 은 true/false 명시 필수 — 가상 데이터는 반드시 표기한다');
if (source && !source.asOf) warn('source.asOf(기준일) 없음 — 출처 블록에 기준일이 빠진다');
if (!slide.notes) warn('slide.notes 없음 — 발표 노트를 권장한다');

if ((chart.measure || {}).axisBreak != null && (typeof chart.measure.axisBreak !== 'number' || !Number.isFinite(chart.measure.axisBreak)))
  fail('chart.measure.axisBreak 은 숫자여야 한다 — 축 생략 구간의 하한값');
const data = Array.isArray(chart.data) ? chart.data : [];
if (type) {
  if (data.length < type.min || data.length > type.max)
    fail(`${chart.type} 데이터 수 ${data.length}개 — ${type.min}~${type.max}개 범위를 벗어났다`);
}
const labels = new Set();
data.forEach((d, i) => {
  if (!d || typeof d.label !== 'string' || !d.label) fail(`data[${i}].label 누락`);
  if (labels.has(d.label)) fail(`data[${i}].label '${d.label}' 중복 — 주석·강조 참조가 모호해진다`);
  labels.add(d.label);
  if (typeof d.value !== 'number' || !Number.isFinite(d.value)) fail(`data[${i}].value 는 유한 숫자여야 한다: '${d.value}'`);
  if (d.kind != null && !WF_KINDS.includes(d.kind)) fail(`data[${i}].kind '${d.kind}' — ${WF_KINDS.join('|')} 만 허용`);
});

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
const VBW = 1560;
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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
/* 주석 한 건을 최대 2줄로 접는다 — 넘치면 둘째 줄 끝을 '…' 로 자른다 */
const wrapLines = (s, maxW, fs) => {
  const lines = []; let cur = '';
  for (const ch of String(s)) {
    if (cur && tw(cur + ch, fs) > maxW) { lines.push(cur); cur = ch; } else cur += ch;
  }
  if (cur) lines.push(cur);
  return lines.length > 2 ? [lines[0], lines[1].slice(0, -1) + '…'] : lines;
};
const annText = (a) => `「${a.kind === 'main' ? '핵심' : '참고'}」 ${a.label}`;
const annFont = (a) => (a.kind === 'main' ? 24 : 20);
const eyebrow = slide.eyebrow || `${chart.measure.unit} · ${chart.measure.period || ''}`.replace(/ · $/, '');
const unitTag = `    <text class="k-t-tag" x="60" y="42">(단위: ${esc(chart.measure.unit)})</text>`;

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
  const h = [
    header(),
    `<section class="slide${extraCls ? ' ' + extraCls : ''}" data-archetype="${type.archetype}" data-variant="${type.variant}" style="gap:18px">`,
    `  <div class="head"><p class="eyebrow">${esc(eyebrow)}</p><h2 class="title">${esc(slide.title)}</h2></div>`,
    ...svg,
    `  </svg>`,
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

/* ── 3-A. waterfall ──────────────────────────────────────────────── */
function buildWaterfall() {
  const n = data.length;
  const BASE_Y = 460, PLOT = 360, CONN = 60, NAME_Y = 508;
  const H = 580;
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
  const sc = PLOT / Math.max(maxV - brk, 1e-9);
  const U = (v) => (v - brk) * sc;
  const barW = Math.min(200, Math.floor((VBW - 180 - (n - 1) * CONN) / n));
  const span = n * barW + (n - 1) * CONN;
  const left = (VBW - span) / 2;

  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  svg.push(`    <path d="M60,${BASE_Y} L1500,${BASE_Y}" class="k-ln-n"/>`);
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
    const tCls = k === 'delta' ? (d.value >= 0 ? 'k-t-b' : 'k-t-o') : '';
    svg.push(`      <text x="${r2(cx)}" y="${r2(y - 24)}" font-size="26" font-weight="800" ${tCls ? `class="${tCls}"` : 'fill="var(--ink)"'} text-anchor="middle"${isLast ? ' data-count' : ''}>${esc(val)}</text>`);
    svg.push(`      <text x="${r2(cx)}" y="${NAME_Y}" font-size="22" font-weight="700" fill="var(--ink)" text-anchor="middle">${esc(d.label)}</text>`);
    /* 주석 — 막대 아래 빈 공간에 점선 리더로 연결. 컬럼 폭(barW+CONN/2) 이내, 최대 2줄.
       부유 막대 밑 공간이 부족하면 항목 라벨 아래로 내린다(복수 주석은 아래로 누적). */
    let annCursor = 0;
    annBy(d.label).forEach((a) => {
      const fs = annFont(a), maxW = barW + CONN / 2;
      const lines = wrapLines(annText(a), maxW, fs);
      const need = lines.length * 24 + 16;
      const inGap = k === 'delta' && barBottom + annCursor + need <= NAME_Y - 8;
      const ly0 = inGap ? barBottom + annCursor + 10 + fs : NAME_Y + 14 + annCursor + fs;
      const leadFrom = inGap ? barBottom + annCursor + 4 : NAME_Y + 8;
      svg.push(`      <path d="M${r2(cx)},${r2(leadFrom)} L${r2(cx)},${r2(ly0 - fs - 4)}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-dasharray="4 5"/>`);
      lines.forEach((line, li) => {
        svg.push(`      <text x="${r2(cx)}" y="${r2(ly0 + li * 24)}" font-size="${fs}" font-weight="${a.kind === 'main' ? 800 : 600}" class="${a.kind === 'main' ? 'k-t-o' : 'k-t-tag'}" text-anchor="middle">${esc(line)}</text>`);
      });
      annCursor += need;
    });
    svg.push(`    </g>`);
  });
  return section(svg, { bars: n, steps: n });
}

/* 주석 계획 — 수치 뒤 인라인으로 들어가면 인라인(같은 y), 아니면 항목 이름 아래에
   행 높이를 가산해 둔다(둘 중 겹침이 없는 쪽 — 하-1). */
function annPlan(d, valStr, valX, dir, labelX) {
  const inline = [], below = [];
  let cursor = valX + dir * (tw(valStr, 28) + 24);
  for (const a of annBy(d.label)) {
    const fs = annFont(a), txt = annText(a), w = tw(txt, fs);
    const fits = dir > 0 ? cursor + w <= 1500 : cursor - w >= 60;
    if (fits && !below.length) {
      inline.push({ a, txt, fs, x: cursor, anchor: dir > 0 ? 'start' : 'end' });
      cursor += dir * (w + 24);
    } else {
      wrapLines(txt, 1100, fs).forEach((line) => below.push({ line, fs, main: a.kind === 'main' }));
    }
  }
  return { inline, below, extra: below.length ? below.length * 26 + 8 : 0 };
}

/* ── 3-B. ranked-bar-h ───────────────────────────────────────────── */
function buildRanked() {
  const ROW = 82, BAR_H = 56, AXIS_X = 320, TOP = 70, MAX_W = 1100;
  const rows = [...data].sort((a, b) => b.value - a.value || String(a.label).localeCompare(String(b.label)));
  const maxV = Math.max(...rows.map((d) => d.value), 1e-9);
  const plans = rows.map((d) => {
    const w = Math.max((d.value / maxV) * MAX_W, 4);
    return { w, ...annPlan(d, fmt(d.value), AXIS_X + w + 16, 1, AXIS_X - 20) };
  });
  const ys = []; let yy = TOP;
  plans.forEach((p) => { ys.push(yy); yy += ROW + p.extra; });
  const H = yy + 56;
  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  svg.push(`    <line x1="${AXIS_X}" y1="56" x2="${AXIS_X}" y2="${H - 44}" stroke="var(--soft)" stroke-width="3"/>`);
  svg.push(`    <line x1="${AXIS_X}" y1="${H - 44}" x2="1500" y2="${H - 44}" stroke="var(--soft)" stroke-width="3"/>`);
  rows.forEach((d, i) => {
    const { w, inline, below } = plans[i];
    const y = ys[i], cy = y + BAR_H / 2 + 8;
    const fill = highlights.includes(d.label) ? 'var(--accent)' : 'var(--blue)';
    svg.push(`    <g data-step="${i + 1}">`);
    svg.push(`      <text x="${AXIS_X - 20}" y="${cy}" text-anchor="end" font-size="26" font-weight="700" fill="var(--ink)">${esc(d.label)}</text>`);
    svg.push(`      <rect x="${AXIS_X}" y="${y}" width="${r2(w)}" height="${BAR_H}" rx="8" fill="${fill}" ${growL}/>`);
    svg.push(`      <text x="${r2(AXIS_X + w + 16)}" y="${cy}" font-size="28" font-weight="800" fill="var(--ink)">${esc(fmt(d.value))}</text>`);
    inline.forEach((t) => {
      svg.push(`      <text x="${r2(t.x)}" y="${cy}" font-size="${t.fs}" font-weight="${t.a.kind === 'main' ? 800 : 600}" class="${t.a.kind === 'main' ? 'k-t-o' : 'k-t-tag'}" text-anchor="${t.anchor}">${esc(t.txt)}</text>`);
    });
    below.forEach((t, li) => {
      svg.push(`      <text x="${AXIS_X}" y="${r2(cy + 36 + li * 26)}" font-size="${t.fs}" font-weight="${t.main ? 800 : 600}" class="${t.main ? 'k-t-o' : 'k-t-tag'}" text-anchor="start">${esc(t.line)}</text>`);
    });
    svg.push(`    </g>`);
  });
  return section(svg, { bars: rows.length, steps: rows.length });
}

/* ── 3-C. diverging-bar ──────────────────────────────────────────── */
function buildDiverging() {
  const ROW = 82, BAR_H = 56, ZERO = 800, TOP = 70, HALF = 460;
  const LABEL_X = ZERO - HALF - 20;
  const maxA = Math.max(...data.map((d) => Math.abs(d.value)), 1e-9);
  const plans = data.map((d) => {
    const w = Math.max((Math.abs(d.value) / maxA) * HALF, 4);
    const neg = d.value < 0;
    const vx = neg ? ZERO - w - 16 : ZERO + w + 16;
    return { w, neg, vx, ...annPlan(d, fmtDelta(d.value), vx, neg ? -1 : 1, LABEL_X) };
  });
  const ys = []; let yy = TOP;
  plans.forEach((p) => { ys.push(yy); yy += ROW + p.extra; });
  const H = yy + 60;
  const svg = svgOpen(H, slide.ariaLabel || `${chart.type} — ${chart.question}`);
  svg.push(unitTag);
  svg.push(`    <line x1="${ZERO - HALF}" y1="${H - 40}" x2="${ZERO + HALF}" y2="${H - 40}" stroke="var(--soft)" stroke-width="3"/>`);
  svg.push(`    <line x1="${ZERO}" y1="56" x2="${ZERO}" y2="${H - 40}" stroke="var(--ink)" stroke-width="3"/>`);
  svg.push(`    <line x1="${ZERO - HALF}" y1="56" x2="${ZERO - HALF}" y2="${H - 40}" stroke="var(--line)" stroke-width="2" stroke-dasharray="6 8"/>`);
  svg.push(`    <line x1="${ZERO + HALF}" y1="56" x2="${ZERO + HALF}" y2="${H - 40}" stroke="var(--line)" stroke-width="2" stroke-dasharray="6 8"/>`);
  svg.push(`    <text x="${ZERO - HALF}" y="${H - 12}" text-anchor="middle" font-size="22" fill="var(--soft)">−${esc(fmt(maxA))}</text>`);
  svg.push(`    <text x="${ZERO}" y="${H - 12}" text-anchor="middle" font-size="22" fill="var(--soft)">0</text>`);
  svg.push(`    <text x="${ZERO + HALF}" y="${H - 12}" text-anchor="middle" font-size="22" fill="var(--soft)">+${esc(fmt(maxA))}</text>`);
  data.forEach((d, i) => {
    const { w, neg, vx, inline, below } = plans[i];
    const y = ys[i], cy = y + BAR_H / 2 + 8;
    const x = neg ? ZERO - w : ZERO;
    const fill = neg ? 'var(--accent)' : 'var(--blue)';
    const grow = neg ? growR : growL;
    const anchor = neg ? 'end' : 'start';
    const ring = highlights.includes(d.label) ? ` stroke="var(--ink)" stroke-width="3"` : '';
    svg.push(`    <g data-step="${i + 1}">`);
    svg.push(`      <text x="${LABEL_X}" y="${cy}" text-anchor="end" font-size="26" font-weight="700" fill="var(--ink)">${esc(d.label)}</text>`);
    svg.push(`      <rect x="${r2(x)}" y="${y}" width="${r2(w)}" height="${BAR_H}" rx="8" fill="${fill}"${ring} ${grow}/>`);
    svg.push(`      <text x="${r2(vx)}" y="${cy}" font-size="28" font-weight="800" fill="var(--ink)" text-anchor="${anchor}">${esc(fmtDelta(d.value))}</text>`);
    inline.forEach((t) => {
      svg.push(`      <text x="${r2(t.x)}" y="${cy}" font-size="${t.fs}" font-weight="${t.a.kind === 'main' ? 800 : 600}" class="${t.a.kind === 'main' ? 'k-t-o' : 'k-t-tag'}" text-anchor="${t.anchor}">${esc(t.txt)}</text>`);
    });
    below.forEach((t, li) => {
      svg.push(`      <text x="${r2(x)}" y="${r2(cy + 36 + li * 26)}" font-size="${t.fs}" font-weight="${t.main ? 800 : 600}" class="${t.main ? 'k-t-o' : 'k-t-tag'}" text-anchor="start">${esc(t.line)}</text>`);
    });
    svg.push(`    </g>`);
  });
  return section(svg, { bars: data.length, steps: data.length });
}

/* ── 4. 방출 ─────────────────────────────────────────────────────── */
const doc = chart.type === 'waterfall' ? buildWaterfall()
          : chart.type === 'ranked-bar-h' ? buildRanked() : buildDiverging();
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
