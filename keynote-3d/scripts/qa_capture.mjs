import { chromium } from 'playwright';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs/promises';

const here = path.dirname(fileURLToPath(import.meta.url));
const sample = path.resolve(here, '../examples/phase1-sample/index.html');
const outDir = process.env.K3D_SHOT_DIR || path.resolve(here, './shots');
await fs.mkdir(outDir, { recursive: true });

const result = {
  pageerrors: [],
  consoleErrors: [],
  externalRequests: [],
  checks: {},
  shots: {}
};

const browser = await chromium.launch({
  headless: true,
  channel: 'chrome',
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl']
});
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.on('pageerror', err => result.pageerrors.push(String(err.message || err)));
page.on('console', msg => { if (msg.type() === 'error') result.consoleErrors.push(msg.text()); });
page.on('request', req => {
  const url = req.url();
  if (/^https?:\/\//i.test(url)) result.externalRequests.push(url);
});

const started = Date.now();
await page.goto(pathToFileURL(sample).href + '?headless=1', { waitUntil: 'load' });
await page.waitForFunction(() => window.ready === true, null, { timeout: 10000 });
result.checks.readyMs = Date.now() - started;
result.checks.webgl2 = await page.evaluate(() => !!document.querySelector('#stage')?.getContext('webgl2'));
result.checks.initialState = await page.evaluate(() => window.kn3d.state());

await page.mouse.click(1120, 360);
await page.waitForTimeout(260);
result.checks.afterClick = await page.evaluate(() => window.kn3d.state());

await page.mouse.wheel(0, 260);
await page.waitForTimeout(520);
result.checks.afterWheel = await page.evaluate(() => window.kn3d.state());

await page.evaluate(() => { location.hash = '#2-2'; });
await page.waitForTimeout(700);
result.checks.afterHash = await page.evaluate(() => window.kn3d.state());
result.checks.hash = await page.evaluate(() => location.hash);

async function capture(scene, beat, name) {
  await page.evaluate(([s, b]) => window.kn3d.go(s, b), [scene, beat]);
  await page.waitForTimeout(1250);
  const file = path.join(outDir, name);
  await page.screenshot({ path: file, fullPage: false });
  result.shots[name] = file;
}
await capture(1, 1, 'k3d-scene1.png');
await capture(2, 2, 'k3d-scene2.png');
await capture(3, 3, 'k3d-scene3.png');

result.checks.pixelProbe = await page.evaluate(() => {
  const c = document.querySelector('#stage');
  const probe = document.createElement('canvas');
  probe.width = 64; probe.height = 64;
  const g = probe.getContext('2d', { willReadFrequently: true });
  g.drawImage(c, 0, 0, 64, 64);
  const px = g.getImageData(0, 0, 64, 64).data;
  let sum = 0, lit = 0;
  for (let i = 0; i < px.length; i += 4) {
    const v = (px[i] + px[i + 1] + px[i + 2]) / 3;
    sum += v;
    if (v > 12) lit++;
  }
  return { mean: sum / (px.length / 4), litRatio: lit / (px.length / 4), width: c.width, height: c.height };
});

const quickStarted = Date.now();
await page.goto(pathToFileURL(sample).href + '?quick&headless=1', { waitUntil: 'load' });
await page.waitForFunction(() => window.ready === true, null, { timeout: 10000 });
result.checks.quickReadyMs = Date.now() - quickStarted;

await browser.close();

const pass = result.pageerrors.length === 0
  && result.consoleErrors.length === 0
  && result.externalRequests.length === 0
  && result.checks.webgl2 === true
  && result.checks.readyMs < 10000
  && result.checks.quickReadyMs < 5000
  && result.checks.afterClick.beat === 2
  && result.checks.afterWheel.beat === 3
  && result.checks.afterHash.scene === 2
  && result.checks.afterHash.beat === 2
  && result.checks.pixelProbe.mean > 5
  && result.checks.pixelProbe.litRatio > .05;

console.log(JSON.stringify({ pass, ...result }, null, 2));
process.exit(pass ? 0 : 1);
