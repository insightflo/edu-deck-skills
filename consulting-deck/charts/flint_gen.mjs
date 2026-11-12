#!/usr/bin/env node
/**
 * flint_gen.mjs — flint-chart(MIT, Microsoft) 정적 SVG 경로 → 컨설팅 슬라이드 조각을
 * 빌드 시점에 굽는 생성기. chart_gen.mjs 와 같은 계약:
 *   의미 모델만 고치고 다시 생성한다 · 결정적 출력 · FAIL=exit 1 · 산출물 런타임 의존 0.
 *
 * [chart_gen 과의 관계] 대체가 아니라 병행 엔진 — 모델 확장자 *.flint.json 이
 *   디스패치 키다(regen.py 참조). 마크별 순차 등장(data-fx)은 없고 그림 전체 등장만
 *   가능하므로, 단계 공개가 필요한 차트는 chart_gen 쪽을 택한다(flint-schema.md 6절).
 *
 * [입력] --in MODEL.flint.json   (스키마: consulting-deck/charts/flint-schema.md)
 *   engine:"flint" · flintVersion:"1.0.1" · theme:"consult|consult-tech"
 *   slide : { eyebrow?, title, notes?, ariaLabel?, class? }
 *   flint : ChartAssemblyInput — data.values 인라인 필수(근거 대조 때문)
 *   source: { text, asOf?, note?, synthetic:bool }
 * [출력] -o <슬라이드.html|->  (기본 stdout) · --svg-only <section> 없이 <svg> 만 ·
 *        --check  validateChart + 팔레트 허용목록 + -o 파일과 바이트 비교 · --quiet
 *
 * [환경] FLINT_HOME(기본 ~/.edu-deck/flint)의 node_modules 를 createRequire 로 해석.
 *   없으면 FAIL — flint_env.py check/install 안내를 출력한다.
 * [계약] 생성 SVG 는 flint 산물 무손실 삽입(후처리 금지). 색은 flint-theme.json
 *   허용목록 안으로 제한 — 모델이 임의 hex 를 들여오면 --check 가 FAIL 낸다.
 *   시간·난수 금지(스키마). 같은 입력 → 같은 바이트.
 */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { createRequire } from 'node:module';
import process from 'node:process';

const CHARTS = path.dirname(new URL(import.meta.url).pathname);
const THEME_FILE = path.join(CHARTS, 'flint-theme.json');
const PINNED = { 'flint-chart': '1.0.1', vega: '6.4.0', 'vega-lite': '6.5.0' };

const argv = process.argv.slice(2);
const arg = (k, d = null) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const has = (k) => argv.includes(k);
if (!argv.length || has('--help') || has('-h')) {
  console.log(`flint_gen.mjs — flint 정적 SVG → 컨설팅 차트 조각 생성기
usage: node flint_gen.mjs --in MODEL.flint.json [-o SLIDE.html] [--svg-only] [--check] [--quiet]
  --in       flint 차트 의미 모델(스키마: consulting-deck/charts/flint-schema.md)
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

const warn = (m) => console.error(`WARN  ${m}`);
const fail = (m) => { console.error(`FAIL  ${m}`); process.exit(1); };
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/* ── 모델 검증(스키마 수준) ──────────────────────────────────── */
const slide = model.slide || {};
const input = model.flint;
const source = model.source;
if (model.engine !== 'flint') fail('engine:"flint" 명시 필수 — chart_gen 모델은 chart_gen.mjs 로');
const themes = JSON.parse(fs.readFileSync(THEME_FILE, 'utf8'));
const themeKey = model.theme || 'consult';
if (!themes.presets[themeKey]) fail(`theme '${themeKey}' — flint-theme.json presets 키 중 하나여야 한다: ${Object.keys(themes.presets).join('|')}`);
if (!slide.title) fail('slide.title 누락 — 주장형 제목은 필수다');
if (!input || typeof input !== 'object') fail('flint(ChartAssemblyInput) 누락');
if (!Array.isArray(input?.data?.values) || !input.data.values.length) fail('flint.data.values 인라인 배열 필수 — 근거 대조 때문');
if (input.data.values.length > 10000) fail(`data.values ${input.data.values.length}행 — 상한 10,000행 초과`);
if (!input.chart_spec?.chartType) fail('flint.chart_spec.chartType 누락');
const cs = input.chart_spec?.canvasSize;
if (cs && ((cs.width || 0) > 2000 || (cs.height || 0) > 1200)) fail('canvasSize 상한 2000×1200 초과');
for (const k of Object.keys(model)) if (!['engine', 'flintVersion', 'slide', 'flint', 'theme', 'source'].includes(k)) fail(`모델 최상위 금지 키: ${k}`);
if (!source || !source.text) fail('source.text 누락 — 출처 없는 수치는 쓸 수 없다');
if (typeof source.synthetic !== 'boolean') fail('source.synthetic 은 true/false 명시 필수 — 가상 데이터는 반드시 표기한다');
if (!source.asOf) warn('source.asOf(기준일) 없음 — 출처 블록에 기준일이 빠진다');
if (!slide.notes) warn('slide.notes 없음 — 발표 노트를 권장한다');

/* ── FLINT_HOME 해석 → flint 로딩 ───────────────────────────── */
const home = process.env.FLINT_HOME || path.join(os.homedir(), '.edu-deck', 'flint');
const req = createRequire(path.join(home, 'package.json'));
let renderSvg, validateChart;
try {
  ({ renderSvg } = await import(req.resolve('flint-chart/render')));
  ({ validateChart } = await import(req.resolve('flint-chart/validate')));
} catch (e) {
  fail(`flint-chart 해석 실패(${home}) — python3 consulting-deck/charts/flint_env.py check|install · ${e.message}`);
}
const installed = JSON.parse(fs.readFileSync(path.join(home, 'node_modules', 'flint-chart', 'package.json'), 'utf8')).version;
if (model.flintVersion && model.flintVersion !== installed) warn(`flintVersion ${model.flintVersion} ≠ 설치 ${installed} — 바이트 diff 가능`);

/* ── 검증 → 렌더(정적 vegalite 경로만) ───────────────────────── */
input.theme_spec = themes.presets[themeKey];
const verdict = validateChart(input, 'vegalite');
(verdict.errors || []).forEach((e) => console.error(`  validate[${e.severity || 'error'}] ${e.code || ''} ${e.message}`));
if (!verdict.valid || (verdict.errors || []).some((e) => (e.severity || 'error') === 'error')) fail('validateChart 오류 — 위 메시지대로 모델을 고친다');
(verdict.warnings || []).forEach((w) => warn(`validate ${typeof w === 'string' ? w : w.message || JSON.stringify(w)}`));
const svg = await renderSvg(input, { backend: 'vegalite' });
if (typeof svg !== 'string' || !svg.trimStart().startsWith('<svg')) fail('renderSvg 산출물이 SVG 문서가 아니다');

/* ── 팔레트 허용목록(모델 hex 누수 차단) ────────────────────── */
const allow = new Set(themes.allowlist[themeKey].map((h) => h.toLowerCase()));
const seen = new Set();
for (const m of svg.matchAll(/#[0-9a-fA-F]{3,8}\b/g)) seen.add(m[0].toLowerCase());
const stray = [...seen].filter((h) => !allow.has(h));
if (stray.length) fail(`팔레트 허용목록 밖 색 ${stray.join(', ')} — 모델 hex 누수 또는 테마 이탈(flint-theme.json allowlist 갱신이면 의도 기록)`);

/* ── 조각 크롬(chart_gen 동일 구조) ─────────────────────────── */
const extraCls = typeof slide.class === 'string' ? slide.class.trim().replace(/[^a-z0-9 -]/gi, '') : '';
const eyebrow = slide.eyebrow || '데이터';
const aria = slide.ariaLabel || slide.title;
const srcBlock = [
  ...(source.note ? [`  <p class="c-note" data-step="1"><b>방법론·한계</b> — ${esc(source.note)}</p>`] : []),
  `  <div class="c-src" data-step="1">`,
  `    <p>Source: ${esc(source.text)}${source.asOf ? ` · 기준 ${esc(source.asOf)}` : ''}</p>`,
  ...(source.synthetic ? ['    <p class="s-syn">가상 데이터</p>'] : []),
  `  </div>`,
];
const body = [
  `  <figure class="c-fig" role="img" aria-label="${esc(aria)}" data-step="1" style="margin:0;flex:1;min-height:0">`,
  svg,
  `  </figure>`,
];
const section = [
  `<section class="slide${extraCls ? ' ' + extraCls : ''}" data-archetype="chart-flint" style="gap:18px">`,
  `  <div class="head"><p class="eyebrow">${esc(eyebrow)}</p><h2 class="title">${esc(slide.title)}</h2></div>`,
  ...body,
  ...srcBlock,
  `  <aside class="notes">${esc(slide.notes || '')}</aside>`,
  `</section>`,
].join('\n');
const rel = inPath.includes(`${path.sep}charts${path.sep}`) ? `charts/${path.basename(inPath)}` : path.basename(inPath);
const head = `<!-- consulting chart — flint:${input.chart_spec.chartType} (theme ${themeKey})
     모델: ${rel} · 생성: node consulting-deck/charts/flint_gen.mjs --in ${rel} -o <이 파일>
     flint-chart ${installed} renderSvg 정적 산출물 무손실 삽입 — 손으로 고치지 않는다. -->`;
const output = svgOnly ? svg : head + '\n' + section + '\n';

/* ── 출력·--check ────────────────────────────────────────────── */
if (checkOnly) {
  if (!outPath || !fs.existsSync(outPath)) fail('--check 는 -o <기존 파일> 이 필요하다');
  const cur = fs.readFileSync(outPath, 'utf8');
  if (cur !== output) fail(`diff — ${outPath} 이 재생성 결과와 다르다(모델을 고치고 다시 생성)`);
  console.log(`SAME  ${inPath} → ${outPath}`);
} else if (outPath) {
  fs.writeFileSync(outPath, output);
  console.log(`OK  ${outPath} (${svg.length}B svg, theme ${themeKey}, engine flint@${installed})`);
} else {
  console.log(output);
}
if (!quiet && !checkOnly) console.error(`svg ${svg.length}B · 팔레트 ${seen.size}색 전부 허용목록 안`);
process.exit(0);
