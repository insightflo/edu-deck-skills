#!/usr/bin/env node
/* capture_ui.mjs — 로컬 HTML 파일·웹 URL 을 Chromium(Playwright) 으로 캡처해
 * PNG + edu-deck .win-frame(조각 55) <img> 스니펫을 낸다 (실물 캐리어 수집기·경량판).
 *
 * [왜] 교육 덱의 '실물 화면' 캐리어는 저자가 지정한 화면만 수집한다 — 임의 웹 수집 금지는
 *      32-screen-cite 의 규율 그대로. 이 도구는 저자가 건 URL/파일을 지정 치수·DPR 로
 *      캡처하고, 붙여 넣을 조각과 함께 어디를 어떻게 찍었는지(주석)를 남긴다.
 * [입력] node scripts/capture_ui.mjs --url <url|파일경로> --out <출력.png>
 *        [--html-out <스니펫.html>] [--selector <css>] [--full-page]
 *        [--width 1280] [--height 800] [--dpr 2] [--hide-banners] [--dark]
 *        [--title "..."] [--inline]
 *   --url          http(s):// · file:// · 로컬 파일 경로(자동 file:// 변환)
 *   --selector     요소 캡처(해당 요소만) — full-page 보다 우선
 *   --dpr          deviceScaleFactor(기본 2 → PNG 물리 픽셀 2배, 선명한 축소판)
 *   --hide-banners 쿠키·동의 배너를 가리고 본문 스크롤 잠금을 푼다
 *   --dark         prefers-color-scheme: dark 로 에뮬레이트
 *   --inline       스니펫의 img src 를 PNG base64 data URI 로(덱 폴더에 PNG 없이 삽입)
 * [출력] PNG 파일 + .win-frame 스니펫(--html-out 없으면 표준 출력으로). 스니펫의 img src 는
 *        PNG 파일 이름(상대 경로) — 덱 src 폴더에 PNG 를 나란히 두고 빌드한다.
 * [의존] playwright 또는 playwright-core (node_modules 탐색 순서: 스크립트 상위
 *        find-up → cwd find-up → PLAYWRIGHT_MODULE 환경변수 → npm 전역). 실행기는
 *        playwright 내장 → CHROME_PATH → 시스템 Chrome/Chromium/Edge 순. 표준
 *        라이브러리 외 설치를 하지 않는다 — 못 찾으면 안내만 출력하고 끝낸다.
 * [출처] 개념 참조: awesomezun/awesome-showreels(MIT) — '실물 캡처를 덱 캐리어로 수집'
 *        개념만 참조한 클린룸 구현(원본 코드·식별자 미참조). node 18+.
 */
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { parseArgs } from 'node:util';

const USAGE = `사용: capture_ui.mjs --url <url|파일> --out <png> [옵션]
  --html-out <f>  스니펫 파일 경로(기본: 표준 출력)
  --selector <s>  요소 캡처, --full-page 무시
  --full-page     페이지 전체 높이
  --width/--height/--dpr  뷰포트·배율(기본 1280×800@2x)
  --hide-banners  쿠키·동의 배너 숨김 + 스크롤 잠금 해제
  --dark          다크 컬러 스킴 에뮬레이트
  --title "..."   창 제목·alt 텍스트
  --inline        img 를 base64 data URI 로`;

/* ── playwright 모듈 탐색 ────────────────────────────────────────────── */
function findUpModule(start, name, tried) {
  let dir = path.resolve(start);
  for (;;) {
    const cand = path.join(dir, 'node_modules', name);
    tried.push(cand);
    if (fs.existsSync(cand)) return cand;
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

function resolvePlaywright() {
  const tried = [];
  const roots = [];
  const seen = new Set();
  const add = (d) => {
    if (!d) return;
    const abs = path.resolve(d);
    if (!seen.has(abs)) { seen.add(abs); roots.push(abs); }
  };
  add(path.dirname(fileURLToPath(import.meta.url)));
  add(process.cwd());

  for (const name of ['playwright', 'playwright-core']) {
    for (const root of roots) {
      const hit = findUpModule(root, name, tried);
      if (hit) return { modPath: hit, name, tried };
    }
  }
  if (process.env.PLAYWRIGHT_MODULE) {
    tried.push(process.env.PLAYWRIGHT_MODULE);
    if (fs.existsSync(process.env.PLAYWRIGHT_MODULE)) {
      return {
        modPath: process.env.PLAYWRIGHT_MODULE,
        name: path.basename(process.env.PLAYWRIGHT_MODULE),
        tried,
      };
    }
  }
  const g = spawnSync('npm', ['root', '-g'], { encoding: 'utf8' });
  if (g.status === 0 && g.stdout) {
    for (const name of ['playwright', 'playwright-core']) {
      const cand = path.join(g.stdout.trim(), name);
      tried.push(cand);
      if (fs.existsSync(cand)) return { modPath: cand, name, tried };
    }
  }
  return { modPath: null, name: null, tried };
}

/* ── Chromium 실행기 탐색 ─────────────────────────────────────────────── */
const CHROME_CANDIDATES = {
  darwin: [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Arc.app/Contents/MacOS/Arc',
  ],
  linux: [
    '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium', '/usr/bin/chromium-browser', '/snap/bin/chromium',
  ],
  win32: [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  ],
};

function findExecutable() {
  const tried = [];
  const envs = [process.env.CHROME_PATH, process.env.CHROMIUM_PATH];
  for (const p of envs) {
    if (!p) continue;
    tried.push(p);
    if (fs.existsSync(p)) return p;
  }
  for (const p of CHROME_CANDIDATES[process.platform] || []) {
    tried.push(p);
    if (fs.existsSync(p)) return p;
  }
  if (process.platform === 'linux') {
    for (const name of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']) {
      const w = spawnSync('which', [name], { encoding: 'utf8' });
      if (w.status === 0 && w.stdout.trim()) return w.stdout.trim();
    }
  }
  return { tried };
}

/* ── 배너 은닉(가리기만 — 클릭 등 부작용 없음) ──────────────────────────── */
const HIDE_CSS = `
[id*="cookie" i],[class*="cookie" i],[id*="consent" i],[class*="consent" i],
[id*="onetrust" i],[class*="onetrust" i],[id*="gdpr" i],[class*="gdpr" i],
[aria-label*="cookie" i],[role="dialog"][aria-label*="consent" i]
{display:none!important}
html,body{overflow:auto!important;position:static!important}`;

/* ── PNG 크기(IHDR) — 요약 보고용 ─────────────────────────────────────── */
function pngSize(buf) {
  if (buf.length > 24 && buf.toString('ascii', 12, 16) === 'IHDR') {
    return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
  }
  return { w: null, h: null };
}

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
  .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const clip = (s, n) => (s.length <= n ? s : s.slice(0, n - 1) + '…');

function buildSnippet({ src, alt, title, tag, url, width, height, dpr, stamp }) {
  const head = `<!-- capture_ui.mjs 실물 캡처 · ${esc(url)} · ${width}×${height}@${dpr}x · ${stamp}
     win-frame(조각 55) 규약 · 실물 화면을 '증거'로 인용할 때는 32-screen-cite 규율(출처 data-src·조회일 캡션)로 담는다 -->`;
  return `${head}
<div class="win-frame">
  <div class="wf-bar"><span class="wf-dots"><i></i><i></i><i></i></span><span class="wf-title">${esc(title)}</span><span class="wf-tag">${esc(tag)}</span></div>
  <div class="wf-body"><img src="${esc(src)}" alt="${esc(alt)}" data-visual style="max-width:100%;height:auto;border:1px solid var(--line)"></div>
</div>
`;
}

async function main() {
  let values;
  try {
    ({ values } = parseArgs({
      options: {
        url: { type: 'string' }, out: { type: 'string' }, 'html-out': { type: 'string' },
        selector: { type: 'string' }, 'full-page': { type: 'boolean' },
        width: { type: 'string' }, height: { type: 'string' }, dpr: { type: 'string' },
        'hide-banners': { type: 'boolean' }, dark: { type: 'boolean' },
        'title': { type: 'string' }, inline: { type: 'boolean' }, help: { type: 'boolean' },
      },
    }));
  } catch (e) {
    console.error(`인자 오류: ${e.message}\n\n${USAGE}`);
    process.exit(1);
  }
  if (values.help || !values.url || !values.out) {
    console.error(USAGE);
    process.exit(values.help ? 0 : 1);
  }
  const num = (v, dft, lo, hi) => {
    const n = Math.round(Number(v ?? dft));
    if (!Number.isFinite(n) || n < lo || n > hi) {
      console.error(`값 오류: ${v} — ${lo}~${hi} 범위의 수를 주세요`);
      process.exit(1);
    }
    return n;
  };
  const width = num(values.width, 1280, 200, 4000);
  const height = num(values.height, 800, 200, 8000);
  const dpr = num(values.dpr, 2, 1, 4);

  const url = /^(https?|file|data|about):/i.test(values.url)
    ? values.url
    : pathToFileURL(path.resolve(values.url)).href;

  /* playwright 모듈 */
  const { modPath, name: modName, tried } = resolvePlaywright();
  if (!modPath) {
    console.error(`ERROR: playwright 모듈을 찾을 수 없습니다(이 도구는 브라우저 구동에 playwright 가 필요).
탐색한 위치:
${tried.map((t) => `  - ${t}`).join('\n')}
해결 방법:
  1) 이 프로젝트에 설치: npm i -D playwright-core (또는 playwright)
  2) 이미 설치된 모듈 경로 지정: PLAYWRIGHT_MODULE=/경로/node_modules/playwright-core node capture_ui.mjs ...
  3) 의존 무단 설치는 하지 않는다 — 설치 승인은 저자 몫이다.`);
    process.exit(1);
  }
  const require = createRequire(import.meta.url);
  let chromium;
  try {
    ({ chromium } = require(modPath));
  } catch (e) {
    console.error(`ERROR: ${modPath} 를 불러올 수 없습니다: ${e.message}`);
    process.exit(1);
  }

  /* 실행기 — playwright 풀패키지는 내장 브라우저 우선, core 는 시스템 실행기 필수 */
  let executablePath;
  if (modName === 'playwright-core') {
    const exe = findExecutable();
    if (typeof exe !== 'string') {
      console.error(`ERROR: Chromium 실행기를 찾을 수 없습니다(playwright-core 는 브라우저를 포함하지 않음).
시도한 경로:
${exe.tried.map((t) => `  - ${t}`).join('\n')}
해결 방법: CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" 처럼 지정하거나 Chrome/Chromium 을 설치하세요.`);
      process.exit(1);
    }
    executablePath = exe;
  }

  const browser = await (async () => {
    try {
      return await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
    } catch (e) {
      // 풀패키지인데 내장 브라우저가 없을 때 — 시스템 실행기로 재시도
      if (!executablePath) {
        const exe = findExecutable();
        if (typeof exe === 'string') {
          return await chromium.launch({ headless: true, executablePath: exe });
        }
      }
      throw e;
    }
  })().catch((e) => {
    console.error(`ERROR: Chromium 실행 실패: ${e.message.split('\n')[0]}\n브라우저: ${executablePath || '(playwright 내장)'}`);
    process.exit(1);
  });

  try {
    const ctx = await browser.newContext({
      viewport: { width, height },
      deviceScaleFactor: dpr,
      colorScheme: values.dark ? 'dark' : 'light',
    });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: 'load', timeout: 30000 });
    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
    if (values['hide-banners']) {
      await page.addStyleTag({ content: HIDE_CSS }).catch(() => {});
      await page.evaluate(() => {
        document.body && (document.body.style.position = '');
        document.documentElement.style.overflow = 'auto';
      }).catch(() => {});
    }
    await page.waitForTimeout(250);

    const out = path.resolve(values.out);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    if (values.selector) {
      const el = page.locator(values.selector).first();
      try {
        await el.waitFor({ state: 'visible', timeout: 8000 });
      } catch {
        console.error(`ERROR: 셀렉터 요소가 보이지 않습니다: ${values.selector}`);
        process.exit(2);
      }
      await el.scrollIntoViewIfNeeded().catch(() => {});
      await el.screenshot({ path: out });
    } else {
      await page.screenshot({ path: out, fullPage: Boolean(values['full-page']) });
    }

    const buf = fs.readFileSync(out);
    const { w, h } = pngSize(buf);
    let host = '';
    try { host = new URL(url).hostname; } catch { /* file: 등 */ }
    const label = values.title || host || path.basename(fileURLToPath(url));
    const stamp = new Date().toISOString().replace(/\.\d+Z$/, 'Z');
    const src = values.inline
      ? `data:image/png;base64,${buf.toString('base64')}`
      : path.basename(out);
    const tag = `${dpr}x${values['full-page'] ? ' 전체' : ''}`.trim();
    const snippet = buildSnippet({
      src, alt: `${label} 화면 캡처`, title: clip(label, 28), tag,
      url, width, height, dpr, stamp,
    });
    if (values['html-out']) {
      const hp = path.resolve(values['html-out']);
      fs.mkdirSync(path.dirname(hp), { recursive: true });
      fs.writeFileSync(hp, snippet, 'utf8');
    } else {
      process.stdout.write(snippet);
    }
    console.error(`캡처 완료: ${out} (${w}×${h}px · ${width}×${height}@${dpr}x · ${(buf.length / 1024).toFixed(0)}KB)`);
    console.error(`모듈: ${modPath} · 브라우저: ${executablePath || '(playwright 내장)'}`);
    if (values['html-out']) console.error(`스니펫: ${path.resolve(values['html-out'])}`);
  } finally {
    await browser.close().catch(() => {});
  }
}

main().catch((e) => {
  console.error(`ERROR: ${e.message ? e.message.split('\n')[0] : e}`);
  process.exit(1);
});
