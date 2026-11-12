// 출처: ko-document-studio © 2026 acc0mplish, MIT — engines/ko-doc/tests/viewer_smoke.mjs
// 이식: 우리 뷰어(bookstyle-html/assets/kit/viewer.js) 계약으로 재작성.
//   상태: [data-role=pg] 라벨("1 / 8"·"2–3 / 8")·location.hash(#pN)·#book.className(single)
//   넘김: 책 오른쪽/왼쪽 클릭·→/←/Home/End·[data-act] 버튼·터치 스와이프·data-goto
//   부가: .chk 체크 유지·[data-zoom] 라이트박스(Esc)·좁은 화면 단일 모드·reduced-motion
// 드래그-필 물리(corner/peel)는 우리 뷰어에 없으므로 해당 시험은 제외하고 CSS 리프 넘김
// (.leaf.turning)으로 대체한다.
// 사용: node tests/viewer_smoke.mjs <빌드한 book.html>
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, readdirSync, rmSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

function findChrome() {
  if (process.env.KDS_CHROME || process.env.CHROME_PATH) return process.env.KDS_CHROME || process.env.CHROME_PATH;
  const fixed = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'];
  for (const f of fixed) if (existsSync(f)) return f;
  const pw = join(homedir(), '.cache', 'ms-playwright');
  if (existsSync(pw)) {
    const dirs = readdirSync(pw).sort().reverse();
    for (const [pre, sub, exe] of [['chromium_headless_shell-', 'chrome-headless-shell-linux64', 'chrome-headless-shell'], ['chromium-', 'chrome-linux64', 'chrome']]) {
      const d = dirs.find((x) => x.startsWith(pre));
      if (d && existsSync(join(pw, d, sub, exe))) return join(pw, d, sub, exe);
    }
  }
  return fixed[0];
}

const CHROME = findChrome();
const SANDBOX = process.getuid && process.getuid() === 0 ? ['--no-sandbox'] : [];
const html = resolve(process.argv[2] || '');
const url = pathToFileURL(html).href;
const port = 9400 + Math.floor(Math.random() * 400);
const profile = mkdtempSync(join(tmpdir(), 'bsh-smoke-'));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const chrome = spawn(CHROME, ['--headless=new', ...SANDBOX, '--disable-gpu', '--no-first-run', `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`, '--window-size=1440,1000', 'about:blank'], { stdio: 'ignore', detached: true });

async function waitForChrome() {
  for (let i = 0; i < 60; i += 1) {
    try { if ((await fetch(`http://127.0.0.1:${port}/json/version`)).ok) return; } catch { /* 아직 뜨는 중 */ }
    await sleep(200);
  }
  throw new Error('크롬이 뜨지 않았습니다');
}
function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  const pending = new Map();
  const errors = [];
  let id = 0;
  ws.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
  });
  const send = (method, params = {}) => new Promise((res) => { id += 1; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
  return new Promise((res) => ws.addEventListener('open', () => res({ send, errors, close: () => ws.close() })));
}

let page;
const ev = async (expr) => (await page.send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result.result?.value;
const state = () => ev(`(() => { const l = document.querySelector('[data-role=pg]'); return { label: l ? l.textContent.trim() : '', hash: location.hash, single: document.getElementById('book').className === 'single', turning: !!document.querySelector('#book .leaf.turning'), pages: (window.__book || {}).pages || 0 }; })()`);
const box = () => ev(`(() => { const r = document.getElementById('book').getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; })()`);
const mouse = (type, x, y, buttons = 0, button = 'none') => page.send('Input.dispatchMouseEvent', { type, x, y, buttons, button, clickCount: type === 'mouseMoved' ? 0 : 1 });
async function click(x, y) { await mouse('mouseMoved', x, y); await mouse('mousePressed', x, y, 1, 'left'); await mouse('mouseReleased', x, y, 0, 'left'); }
const key = (k) => page.send('Input.dispatchKeyEvent', { type: 'keyDown', key: k, code: k, windowsVirtualKeyCode: { ArrowRight: 39, ArrowLeft: 37, Escape: 27, Home: 36, End: 35 }[k] || 0 });
const settle = async () => { for (let i = 0; i < 80; i += 1) { const s = await state(); if (!s.turning) return s; await sleep(50); } return state(); };
const open = async (hash = '') => { await page.send('Page.navigate', { url: url + hash }); await sleep(900); return settle(); };

const results = [];
async function test(name, fn) {
  try { const r = await fn(); results.push({ name, ok: r === true, detail: r === true ? '' : JSON.stringify(r) }); }
  catch (e) { results.push({ name, ok: false, detail: e.message }); }
}

async function run() {
  await waitForChrome();
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  page = await connect(target.webSocketDebuggerUrl);
  await page.send('Runtime.enable');
  await page.send('Page.enable');
  const N = await open().then((s) => s.pages);

  await test('처음은 표지 한 쪽(펼침 모드)', async () => {
    const s = await state();
    return (!s.single && s.label === `1 / ${N}` && s.hash === '#p1') || s;
  });

  await test('오른쪽을 누르면 리프가 넘어감(중간 .turning 있음)', async () => {
    const b = await box();
    await click(b.x + b.w * 0.8, b.y + b.h * 0.6);
    let sawTurning = false;
    for (let i = 0; i < 14; i += 1) { const s = await state(); if (s.turning) sawTurning = true; if (!s.turning && s.label !== '1 / ' + N) break; await sleep(50); }
    const s = await settle();
    return (s.label === `2–3 / ${N}` && sawTurning && s.hash === '#p2') || { s, sawTurning };
  });

  await test('→ ← 키로 넘김', async () => {
    await key('ArrowRight'); let s = await settle(); const a = s.label;
    await key('ArrowLeft'); s = await settle();
    return (a === `4–5 / ${N}` && s.label === `2–3 / ${N}`) || { a, s };
  });

  await test('키를 빠르게 여러 번 눌러도 안전(무시 또는 순차)', async () => {
    await key('ArrowRight'); await key('ArrowRight'); await key('ArrowRight');
    const s = await settle();
    const m = /^(\d+)/.exec(s.label);
    return (m && +m[1] >= 4 && s.label.endsWith(`/ ${N}`)) || s;
  });

  await test('data-goto 를 누르면 그 쪽으로 감(넘김 클릭이 아님)', async () => {
    await open('#p2');
    const p = await ev(`(() => { const el = [...document.querySelectorAll('#book [data-goto]')].find((e) => e.dataset.goto === '5' && e.getBoundingClientRect().width); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
    if (!p) return { skip: 'data-goto=5 요소가 보이지 않음' };
    await click(p.x, p.y);
    const s = await settle();
    return (/^(4|5)/.test(s.label) && s.hash === '#p4') || s;
  });

  await test('점검표는 넘겼다 돌아와도 체크가 남음', async () => {
    const chkAt = await ev(`(() => { const pg = [...document.querySelectorAll('#pages > .page')].find((p) => p.querySelector('.chk')); return pg ? +(pg.dataset.pno || 0) : 0; })()`);
    if (!chkAt) return true; // .chk 없는 책 — 계약상 검사할 것이 없다
    await open('#p' + chkAt);
    const p = await ev(`(() => { const el = [...document.querySelectorAll('#book .chk')].find((e) => { const r = e.getBoundingClientRect(); return r.width && r.right <= innerWidth && r.left >= 0; }); const r = el.getBoundingClientRect(); return { x: r.left + 20, y: r.top + r.height / 2 }; })()`);
    await click(p.x, p.y);
    const on1 = await ev(`!!document.querySelector('#book .chk.on')`);
    await key('ArrowRight'); await sleep(200); await settle(); await key('ArrowLeft'); await sleep(200); await settle();
    const on2 = await ev(`!!document.querySelector('#book .chk.on')`);
    return (on1 && on2) || { on1, on2 };
  });

  await test('그림을 누르면 크게 보기, Esc 로 닫기', async () => {
    const zoomAt = await ev(`(() => { const pg = [...document.querySelectorAll('#pages > .page')].find((p) => p.querySelector('[data-zoom]')); return pg ? +(pg.dataset.pno || 0) : 0; })()`);
    if (!zoomAt) return true; // data-zoom 없는 책
    await open('#p' + zoomAt);
    const p = await ev(`(() => { const el = [...document.querySelectorAll('#book [data-zoom]')].find((e) => e.getBoundingClientRect().width); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
    await click(p.x, p.y);
    const on = await ev(`document.getElementById('lightbox').classList.contains('on')`);
    await key('Escape');
    const off = await ev(`!document.getElementById('lightbox').classList.contains('on')`);
    return (on && off) || { on, off };
  });

  await test('좁은 화면은 한 쪽 보기로 바뀌고, 눌러서 넘어감', async () => {
    await open('#p4');
    await page.send('Emulation.setDeviceMetricsOverride', { width: 420, height: 860, deviceScaleFactor: 1, mobile: false });
    await sleep(400);
    let s = await settle();
    const before = s.label;
    const b = await box();
    await click(b.x + b.w * 0.8, b.y + b.h * 0.5);
    const s2 = await settle();
    await page.send('Emulation.clearDeviceMetricsOverride');
    await sleep(400);
    const s3 = await settle();
    return (s.single && s2.label !== before && !s3.single) || { s, s2, s3 };
  });

  await test('동작 줄이기 설정이면 바로 넘어감', async () => {
    await page.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    await page.send('Page.navigate', { url: 'about:blank' });  // 해시만 바뀌면 재로드되지 않아
    await sleep(150);
    await open('#p4');                                       // 완전 재로드로 init 시 reduce=true 읽게 한다
    const applied = await ev(`matchMedia('(prefers-reduced-motion: reduce)').matches`);
    const before = (await state()).label;
    await key('ArrowRight');
    let cleared = 0, s = null;
    for (let i = 0; i < 10; i += 1) {  // reduce 이면 1100ms 전에 turning 이 풀린다
      await sleep(60); s = await state();
      if (!s.turning) { cleared = i + 1; break; }
    }
    await page.send('Emulation.setEmulatedMedia', { features: [] });
    return (applied && s.label !== before && !s.turning) || { applied, before, s, cleared };
  });

  await test('마지막 쪽에서는 더 넘어가지 않음', async () => {
    await open('#p' + N);
    const s1 = await state();
    await key('ArrowRight');
    const s = await settle();
    return (s.label === s1.label && s.hash === s1.hash) || { s1, s };
  });

  await test('[data-act] 버튼으로 처음·다음 이동', async () => {
    await ev(`document.querySelector('[data-act=first]').click()`);
    await sleep(350);  // goTo 점프는 180ms 지연 뒤 place 한다
    let s = await settle();
    const first = s.label === `1 / ${N}`;
    await ev(`document.querySelector('[data-act=next]').click()`);
    await sleep(200);
    s = await settle();
    return (first && /^2/.test(s.label)) || { first, s };
  });

  results.push({ name: '스크립트 오류 없음', ok: page.errors.length === 0, detail: page.errors.join(' | ') });
  page.close();
  return results;
}

let code = 1;
try {
  const res = await run();
  res.forEach((r) => process.stdout.write(`${r.ok ? '통과' : '실패'}  ${r.name}${r.detail ? `  → ${r.detail}` : ''}\n`));
  const failed = res.filter((r) => !r.ok).length;
  process.stdout.write(`\n책 뷰어 점검: ${res.length - failed}/${res.length} 통과\n`);
  code = failed ? 1 : 0;
} catch (err) {
  process.stderr.write(`점검 실패: ${err.message}\n`);
} finally {
  try { process.kill(-chrome.pid); } catch { chrome.kill(); }
  await sleep(300);
  rmSync(profile, { recursive: true, force: true });
}
process.exit(code);
