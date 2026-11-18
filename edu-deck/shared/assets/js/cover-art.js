/* cover-art.js — 표지 아키텍트(cover architect): 소재 이미지를 실측해 그 덱만의 제도 리빌 표지를
 * 그리는 엔진과 .ko-cover 자가 초기화 마운트. 설정·재생·폴백 계약은 references/authoring.md 표지 절.
 * 출처: ko-document-studio © 2026 acc0mplish (MIT — licenses/KO-DOCUMENT-MIT.txt).
 * ko-slide 견본 ko-cover-regression.html(2026-11-18 확보, references/samples/ 사본)에서
 * 엔진·마운트 IIFE를 그대로 이식(원문의 "프로젝트 custom.js" 표시 줄만 제외). 원천 스스로
 * "리빌 엔진 8파일(7모듈+진입)을 평탄화한 단일 파일"(스냅샷 2026-11-13)이다.
 * build_deck.py 는 src 에 ko-cover 를 쓴 덱에만 이 파일을 인라인한다(약 85KB). */
if (!window.createCoverReveal) {
// ko-document-cover 리빌 엔진 — 원천 리빌 엔진 8파일(7모듈+진입)을 평탄화한 단일 파일이다.
// 스냅샷 확보 일자: 2026-11-13 (docs/task-id/cover-architect/src-snapshot 기준).
// 모듈 간 참조는 전부 호출 시점에 해소되므로 선언 순서 = 평탄화 순서(util→palettes→analyze→build→render→options→engine/index→create)가 안전하다.
// 전역 진입: createCoverReveal(container | canvas, options) → controller.
(() => {
const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
const lerp = (a, b, t) => a + (b - a) * t;
const TAU = Math.PI * 2;

/** Deterministic PRNG so a seed always produces the same drawing. */
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const EASES = {
  linear: (t) => t,
  smooth: (t) => t * t * (3 - 2 * t),
  easeOut: (t) => 1 - Math.pow(1 - t, 3),
  easeInOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  expoOut: (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t)),
  backOut: (t) => {
    const c1 = 1.70158, c3 = c1 + 1;
    return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
  },
};

/** Local progress of an element whose window is [t0, t1] on the normalized timeline. */
const prog = (u, t0, t1) => (t1 <= t0 ? (u >= t1 ? 1 : 0) : clamp((u - t0) / (t1 - t0)));

/** Parse any CSS colour (hex, rgb, oklch, p3...) to [r,g,b] 0-255 via a 1px canvas. */
const _cc = typeof document !== 'undefined' ? document.createElement('canvas').getContext('2d', { willReadFrequently: true }) : null;
const _cache = new Map();
function toRGB(color) {
  if (_cache.has(color)) return _cache.get(color);
  _cc.clearRect(0, 0, 1, 1);
  _cc.fillStyle = '#000';
  _cc.fillStyle = color;
  _cc.fillRect(0, 0, 1, 1);
  const d = _cc.getImageData(0, 0, 1, 1).data;
  const rgb = [d[0], d[1], d[2]];
  _cache.set(color, rgb);
  return rgb;
}

/** Polyline helpers. pts = flat [x0,y0,x1,y1...]; cum = cumulative length per vertex. */
function cumLengths(pts) {
  const n = pts.length / 2;
  const cum = new Float32Array(n);
  for (let i = 1; i < n; i++) {
    const dx = pts[i * 2] - pts[i * 2 - 2], dy = pts[i * 2 + 1] - pts[i * 2 - 1];
    cum[i] = cum[i - 1] + Math.hypot(dx, dy);
  }
  return cum;
}

/** Ramer–Douglas–Peucker on flat arrays. */
function rdp(pts, eps) {
  const n = pts.length / 2;
  if (n < 3) return pts.slice();
  const keep = new Uint8Array(n);
  keep[0] = keep[n - 1] = 1;
  const stack = [[0, n - 1]];
  const e2 = eps * eps;
  while (stack.length) {
    const [a, b] = stack.pop();
    const ax = pts[a * 2], ay = pts[a * 2 + 1], bx = pts[b * 2], by = pts[b * 2 + 1];
    const dx = bx - ax, dy = by - ay;
    const L2 = dx * dx + dy * dy || 1e-9;
    let best = -1, bi = -1;
    for (let i = a + 1; i < b; i++) {
      const px = pts[i * 2] - ax, py = pts[i * 2 + 1] - ay;
      const c = px * dy - py * dx;
      const d2 = (c * c) / L2;
      if (d2 > best) { best = d2; bi = i; }
    }
    if (best > e2) {
      keep[bi] = 1;
      stack.push([a, bi], [bi, b]);
    }
  }
  const out = [];
  for (let i = 0; i < n; i++) if (keep[i]) out.push(pts[i * 2], pts[i * 2 + 1]);
  return out;
}

/** One Chaikin pass, keeps endpoints. */
function chaikin(pts, closed) {
  const n = pts.length / 2;
  if (n < 3) return pts;
  const out = closed ? [] : [pts[0], pts[1]];
  const m = closed ? n : n - 1;
  for (let i = 0; i < m; i++) {
    const j = (i + 1) % n;
    const x0 = pts[i * 2], y0 = pts[i * 2 + 1], x1 = pts[j * 2], y1 = pts[j * 2 + 1];
    out.push(0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1, 0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1);
  }
  if (closed) out.push(out[0], out[1]);
  else out.push(pts[n * 2 - 2], pts[n * 2 - 1]);
  return out;
}

const fmtNum = (v, decimals) => {
  const s = v.toFixed(decimals);
  return decimals > 0 ? s.replace(/\.?0+$/, '') : s;
};

// bg: paper / plate colour (also text knock-outs) · grid: graph paper · line: main ink · accent: centre lines, compass, plotter head
// dim: dimensions/leaders · text: numbers & labels · m1..m4: extra inks for "multi" colour mode
// plate: fill the image area with bg (dark looks); off = transparent canvas that sits on any page
const PALETTES = {
  ink: { plate: false, bg: '#ffffff', grid: '#e4e6ea', line: '#747474', accent: '#3376ff', dim: '#5b6170', text: '#121212', m1: '#121212', m2: '#2f6bff', m3: '#ff5a1f', m4: '#7a7f8c' },
  graphite: { plate: false, bg: '#ffffff', grid: '#e2e2de', line: '#2b2b2e', accent: '#ff5a1f', dim: '#55555a', text: '#2b2b2e', m1: '#2b2b2e', m2: '#ff5a1f', m3: '#7a7a80', m4: '#1f6feb' },
  drafting: { plate: false, bg: '#ffffff', grid: '#e6e0d2', line: '#161616', accent: '#c8372d', dim: '#3a3a3a', text: '#161616', m1: '#161616', m2: '#c8372d', m3: '#2f5fb3', m4: '#5a5a5a' },
  blueline: { plate: false, bg: '#ffffff', grid: '#dfe3ff', line: '#2433f5', accent: '#1424c9', dim: '#3445ff', text: '#1424c9', m1: '#2433f5', m2: '#5160ff', m3: '#0d1a9e', m4: '#7a86ff' },
  blueprint: { plate: true, bg: '#1d4f9e', grid: '#4f7cc4', line: '#f2f6ff', accent: '#ffffff', dim: '#c7dbff', text: '#ffffff', m1: '#ffffff', m2: '#9fd0ff', m3: '#d9e6ff', m4: '#7fb2ff' },
  retro: { plate: true, bg: '#07070d', grid: '#152643', line: '#3fb8ff', accent: '#ff40c0', dim: '#4fb4ff', text: '#9bdcff', m1: '#ff3b5c', m2: '#ffd23f', m3: '#3dff8a', m4: '#ff40c0' },
  amber: { plate: true, bg: '#0e0a04', grid: '#2b1c07', line: '#ffb000', accent: '#ffe08a', dim: '#ff9500', text: '#ffc94d', m1: '#ffb000', m2: '#ff7a00', m3: '#ffe08a', m4: '#ff5a1f' },
  phosphor: { plate: true, bg: '#030b06', grid: '#0c2a17', line: '#39ff88', accent: '#b6ffd4', dim: '#2ad873', text: '#7dffb0', m1: '#39ff88', m2: '#b6ffd4', m3: '#18b85c', m4: '#e2ff6b' },
};

const PALETTE_KEYS = Object.keys(PALETTES);

// Image → drawing primitives: edge contours (Canny-lite + tracing), arcs (circle fits),
// corners, construction-line peaks and a luminance map for hatching.

/**
 * Heuristic subject classifier used by detection.preset 'auto':
 * schematics trace back as mostly axis-aligned segments, photos/illustrations don't.
 * @returns {'diagram'|'image'}
 */
function classifyImage(an) {
  let total = 0, aligned = 0;
  for (const ch of an.chains.slice(0, 200)) {
    const p = ch.pts; // RDP-simplified, so segments are meaningful strokes
    for (let i = 2; i < p.length; i += 2) {
      const dx = Math.abs(p[i] - p[i - 2]), dy = Math.abs(p[i + 1] - p[i - 1]);
      const l = Math.hypot(dx, dy);
      total += l;
      if (dx < 1.5 || dy < 1.5) aligned += l;
    }
  }
  return total > 400 && aligned / total > 0.6 ? 'diagram' : 'image';
}

function analyzeImage(source, o) {
  const iw = source.naturalWidth || source.width;
  const ih = source.naturalHeight || source.height;
  const k = Math.min(1, o.resolution / Math.max(iw, ih));
  const w = Math.max(16, Math.round(iw * k));
  const h = Math.max(16, Math.round(ih * k));

  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const cx = c.getContext('2d', { willReadFrequently: true });
  cx.drawImage(source, 0, 0, w, h);
  const data = cx.getImageData(0, 0, w, h).data;

  const N = w * h;
  const gray = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const a = data[i * 4 + 3] / 255;
    const l = (0.299 * data[i * 4] + 0.587 * data[i * 4 + 1] + 0.114 * data[i * 4 + 2]) / 255;
    gray[i] = l * a + (1 - a); // transparent → white so cut-outs keep their silhouette
  }

  const sm = gaussBlur(gray, w, h, o.blur);
  const lum = gaussBlur(gray, w, h, Math.max(1.5, o.blur * 2));

  // Sobel
  const mag = new Float32Array(N), gxA = new Float32Array(N), gyA = new Float32Array(N);
  let maxMag = 0;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      const tl = sm[i - w - 1], t = sm[i - w], tr = sm[i - w + 1];
      const l = sm[i - 1], r = sm[i + 1];
      const bl = sm[i + w - 1], b = sm[i + w], br = sm[i + w + 1];
      const gx = tr + 2 * r + br - (tl + 2 * l + bl);
      const gy = bl + 2 * b + br - (tl + 2 * t + tr);
      gxA[i] = gx; gyA[i] = gy;
      const m = Math.hypot(gx, gy);
      mag[i] = m;
      if (m > maxMag) maxMag = m;
    }
  }

  // Non-maximum suppression
  const nms = new Float32Array(N);
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      const m = mag[i];
      if (m === 0) continue;
      let a = (Math.atan2(gyA[i], gxA[i]) * 180) / Math.PI;
      if (a < 0) a += 180;
      let n1, n2;
      if (a < 22.5 || a >= 157.5) { n1 = mag[i - 1]; n2 = mag[i + 1]; }
      else if (a < 67.5) { n1 = mag[i - w - 1]; n2 = mag[i + w + 1]; }
      else if (a < 112.5) { n1 = mag[i - w]; n2 = mag[i + w]; }
      else { n1 = mag[i - w + 1]; n2 = mag[i + w - 1]; }
      if (m >= n1 && m >= n2) nms[i] = m;
    }
  }

  // Thresholds from the gradient distribution (sensitivity = share of pixels that count as strong)
  const bins = 2048;
  const hist = new Uint32Array(bins);
  let cnt = 0;
  for (let i = 0; i < N; i++) if (nms[i] > 0) { hist[Math.min(bins - 1, ((nms[i] / maxMag) * bins) | 0)]++; cnt++; }
  let acc = 0, hiBin = bins - 1;
  const want = cnt * o.sensitivity;
  for (let b = bins - 1; b >= 0; b--) { acc += hist[b]; if (acc >= want) { hiBin = b; break; } }
  const high = Math.max((hiBin / bins) * maxMag, maxMag * 0.04);
  const low = high * 0.4;

  // Hysteresis
  const edges = new Uint8Array(N);
  const stack = [];
  for (let i = 0; i < N; i++) if (nms[i] >= high) { edges[i] = 1; stack.push(i); }
  while (stack.length) {
    const i = stack.pop();
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const j = i + dy * w + dx;
      if (j > 0 && j < N && !edges[j] && nms[j] >= low) { edges[j] = 1; stack.push(j); }
    }
  }

  // Trace edge pixels into chains
  const raw = traceChains(edges, w, h);
  const minLen = Math.max(3, o.minLength * (Math.max(w, h) / 600));
  const chains = [];
  let bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity;
  for (const pts of raw) {
    const n = pts.length / 2;
    if (n < minLen) continue;
    const simp = rdp(pts, o.simplify);
    let len = 0, x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    let r = 0, g = 0, b = 0;
    for (let i = 0; i < simp.length / 2; i++) {
      const x = simp[i * 2], y = simp[i * 2 + 1];
      if (i) len += Math.hypot(x - simp[i * 2 - 2], y - simp[i * 2 - 1]);
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
    // sample colour slightly to both sides of the edge so the line takes the object's hue
    const step = Math.max(1, (n / 24) | 0);
    let sc = 0;
    for (let i = 0; i < n; i += step) {
      const px = pts[i * 2] | 0, py = pts[i * 2 + 1] | 0;
      const j = (py * w + px) * 4;
      r += data[j]; g += data[j + 1]; b += data[j + 2]; sc++;
    }
    const closed = Math.hypot(pts[0] - pts[pts.length - 2], pts[1] - pts[pts.length - 1]) < 3;
    chains.push({ raw: pts, pts: simp, len, closed, bbox: { x: x0, y: y0, w: x1 - x0, h: y1 - y0 }, color: [r / sc, g / sc, b / sc] });
    if (x0 < bx0) bx0 = x0; if (y0 < by0) by0 = y0; if (x1 > bx1) bx1 = x1; if (y1 > by1) by1 = y1;
  }
  chains.sort((a, b) => b.len - a.len);
  if (chains.length > 5000) chains.length = 5000;
  if (!chains.length) { bx0 = 0; by0 = 0; bx1 = w; by1 = h; }

  return {
    w, h, data, lum, chains,
    bbox: { x: bx0, y: by0, w: bx1 - bx0, h: by1 - by0 },
    arcs: fitArcs(chains, w, h),
    corners: findCorners(chains, w, h),
    ...peaks(edges, gxA, gyA, w, h),
  };
}

function gaussBlur(src, w, h, sigma) {
  if (sigma < 0.05) return src.slice();
  const r = Math.max(1, Math.ceil(sigma * 2.5));
  const ker = new Float32Array(r * 2 + 1);
  let s = 0;
  for (let i = -r; i <= r; i++) { ker[i + r] = Math.exp(-(i * i) / (2 * sigma * sigma)); s += ker[i + r]; }
  for (let i = 0; i < ker.length; i++) ker[i] /= s;
  const tmp = new Float32Array(w * h), out = new Float32Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let a = 0;
    for (let k = -r; k <= r; k++) { const xx = x + k < 0 ? 0 : x + k >= w ? w - 1 : x + k; a += src[y * w + xx] * ker[k + r]; }
    tmp[y * w + x] = a;
  }
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let a = 0;
    for (let k = -r; k <= r; k++) { const yy = y + k < 0 ? 0 : y + k >= h ? h - 1 : y + k; a += tmp[yy * w + x] * ker[k + r]; }
    out[y * w + x] = a;
  }
  return out;
}

const NB = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];
function traceChains(edges, w, h) {
  const seen = new Uint8Array(w * h);
  const chains = [];
  const walk = (start) => {
    const out = [];
    let cur = start, pdx = 0, pdy = 0;
    for (;;) {
      const cx = cur % w, cy = (cur / w) | 0;
      let next = -1, best = -9, bdx = 0, bdy = 0;
      for (const [dx, dy] of NB) {
        const x = cx + dx, y = cy + dy;
        if (x < 0 || y < 0 || x >= w || y >= h) continue;
        const j = y * w + x;
        if (!edges[j] || seen[j]) continue;
        const score = dx * pdx + dy * pdy - (dx && dy ? 0.1 : 0); // prefer going straight
        if (score > best) { best = score; next = j; bdx = dx; bdy = dy; }
      }
      if (next < 0) break;
      pdx = bdx; pdy = bdy;
      seen[next] = 1;
      out.push(next);
      cur = next;
    }
    return out;
  };
  for (let i = 0; i < w * h; i++) {
    if (!edges[i] || seen[i]) continue;
    seen[i] = 1;
    const fwd = walk(i);
    const back = walk(i);
    const idx = back.reverse().concat([i], fwd);
    const pts = new Array(idx.length * 2);
    for (let k = 0; k < idx.length; k++) { pts[k * 2] = idx[k] % w; pts[k * 2 + 1] = (idx[k] / w) | 0; }
    chains.push(pts);
  }
  return chains;
}

function circle3(ax, ay, bx, by, cx, cy) {
  const d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by));
  if (Math.abs(d) < 1e-6) return null;
  const a2 = ax * ax + ay * ay, b2 = bx * bx + by * by, c2 = cx * cx + cy * cy;
  const ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d;
  const uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d;
  return { x: ux, y: uy, r: Math.hypot(ax - ux, ay - uy) };
}

function fitArcs(chains, w, h) {
  const maxR = Math.max(w, h) * 0.6;
  const arcs = [];
  for (const ch of chains.slice(0, 400)) {
    const p = ch.raw, n = p.length / 2;
    if (n < 18) continue;
    let found = null;
    for (const frac of [1, 0.7, 0.5, 0.35]) {
      const L = Math.max(14, (n * frac) | 0);
      for (let s = 0; s + L <= n && !found; s += Math.max(4, (L / 2) | 0)) {
        const a = s, b = s + ((L / 2) | 0), e = s + L - 1;
        const c = circle3(p[a * 2], p[a * 2 + 1], p[b * 2], p[b * 2 + 1], p[e * 2], p[e * 2 + 1]);
        if (!c || c.r < 5 || c.r > maxR) continue;
        let err = 0;
        for (let i = a; i <= e; i += 2) err += Math.abs(Math.hypot(p[i * 2] - c.x, p[i * 2 + 1] - c.y) - c.r);
        err /= Math.ceil((e - a + 1) / 2);
        if (err > Math.max(0.7, c.r * 0.025)) continue;
        const a0 = Math.atan2(p[a * 2 + 1] - c.y, p[a * 2] - c.x);
        const a1 = Math.atan2(p[e * 2 + 1] - c.y, p[e * 2] - c.x);
        const cross = (p[b * 2] - p[a * 2]) * (p[e * 2 + 1] - p[b * 2 + 1]) - (p[b * 2 + 1] - p[a * 2 + 1]) * (p[e * 2] - p[b * 2]);
        const span = Math.min(Math.PI * 2, L / c.r);
        if (span < 0.6) continue;
        found = { ...c, a0, a1, ccw: cross < 0, span, score: L * Math.min(span, 4) };
      }
      if (found) break;
    }
    if (!found) continue;
    if (arcs.some((q) => Math.hypot(q.x - found.x, q.y - found.y) < Math.max(4, q.r * 0.25) && Math.abs(q.r - found.r) < q.r * 0.3)) continue;
    arcs.push(found);
  }
  return arcs.sort((a, b) => b.score - a.score).slice(0, 60);
}

function findCorners(chains, w, h) {
  const minSeg = Math.max(w, h) * 0.02;
  const out = [];
  for (const ch of chains.slice(0, 300)) {
    const p = ch.pts, n = p.length / 2;
    for (let i = 1; i < n - 1; i++) {
      const x = p[i * 2], y = p[i * 2 + 1];
      const v1x = p[i * 2 - 2] - x, v1y = p[i * 2 - 1] - y;
      const v2x = p[i * 2 + 2] - x, v2y = p[i * 2 + 3] - y;
      const l1 = Math.hypot(v1x, v1y), l2 = Math.hypot(v2x, v2y);
      if (l1 < minSeg || l2 < minSeg) continue;
      const deg = (Math.acos(Math.max(-1, Math.min(1, (v1x * v2x + v1y * v2y) / (l1 * l2)))) * 180) / Math.PI;
      if (deg < 25 || deg > 155) continue;
      out.push({ x, y, a1: Math.atan2(v1y, v1x), a2: Math.atan2(v2y, v2x), deg, strength: Math.min(l1, l2) });
    }
  }
  return out.sort((a, b) => b.strength - a.strength).slice(0, 80);
}

function peaks(edges, gx, gy, w, h) {
  const rows = new Float32Array(h), cols = new Float32Array(w);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = y * w + x;
    if (!edges[i]) continue;
    if (Math.abs(gy[i]) > Math.abs(gx[i])) rows[y]++; else cols[x]++;
  }
  const pick = (arr, n, len) => {
    const sm = new Float32Array(len);
    for (let i = 0; i < len; i++) { let a = 0; for (let k = -2; k <= 2; k++) a += arr[Math.min(len - 1, Math.max(0, i + k))]; sm[i] = a; }
    const mean = sm.reduce((a, b) => a + b, 0) / len || 1;
    const idx = [...sm.keys()].sort((a, b) => sm[b] - sm[a]);
    const out = [];
    const gap = Math.max(4, len * 0.025);
    for (const i of idx) {
      if (sm[i] < mean * 1.6 || out.length >= n) break;
      if (out.some((q) => Math.abs(q.p - i) < gap)) continue;
      out.push({ p: i, s: sm[i] / sm[idx[0]] });
    }
    return out;
  };
  return { hPeaks: pick(rows, 30, h), vPeaks: pick(cols, 30, w) };
}

// Analysis + config → timed scene (all geometry in canvas pixels, times on a 0..1 timeline).

function buildScene(an, W, H, dpr, cfg) {
  const rnd = mulberry32(cfg.playback.seed * 9973 + 17);
  const P = cfg.palette, D = cfg.drafting, S = cfg.stroke, T = cfg.timing, R = cfg.reveal;

  // ---- fit image into canvas ----
  // canvas = image + bleed margin on every side (lines and dimensions overflow into it)
  const bl = cfg.source.bleed;
  const s = Math.min(W / (an.w * (1 + 2 * bl)), H / (an.h * (1 + 2 * bl)));
  let ox, oy;
  ox = (W - an.w * s) / 2;
  oy = (H - an.h * s) / 2;
  const imgRect = { x: ox, y: oy, w: an.w * s, h: an.h * s };
  const bleedPx = Math.max(0, Math.min(imgRect.x, imgRect.y));
  const gox = Math.max(0, imgRect.x) * cfg.source.gridOverflow, goy = Math.max(0, imgRect.y) * cfg.source.gridOverflow;
  const G = { x: imgRect.x - gox, y: imgRect.y - goy, w: imgRect.w + 2 * gox, h: imgRect.h + 2 * goy }; // grid / plate area
  const M = (x, y) => [ox + x * s, oy + y * s];
  const B = { x: ox + an.bbox.x * s, y: oy + an.bbox.y * s, w: an.bbox.w * s, h: an.bbox.h * s };
  const mmPerPx = D.realWidth / Math.max(1, B.w); // canvas px → "mm"
  const ts = D.textSize * dpr;
  const scene = { W, H, dpr, s, imgRect, B, mmPerPx, bleedPx, G, grid: [], ink: [], notes: [], brush: [], stats: {} };

  const span = (a, b) => Math.max(0.0001, b - a);

  // ---- grid (graph paper) ----
  if (D.grid) {
    const g = Math.max(4, D.gridSize * dpr);
    const gs = 0, ge = T.gridEnd;
    const add = (x1, y1, x2, y2, major, d) => {
      const t0 = gs + d * span(gs, ge) * 0.55;
      scene.grid.push(poly([x1, y1, x2, y2], {
        w: (major ? 1 : 0.6) * dpr, color: P.grid, alpha: (major ? 1 : 0.5) * D.gridOpacity, t0, t1: t0 + span(gs, ge) * 0.45,
      }));
    };
    const gx0 = G.x, gx1 = G.x + G.w, gy0 = G.y, gy1 = G.y + G.h;
    const kx0 = Math.ceil((gx0 - ox) / g), kx1 = Math.floor((gx1 - ox) / g);
    for (let k = kx0; k <= kx1; k++) {
      const x = Math.round(ox + k * g) + 0.5;
      const d = clamp(Math.abs(x - W / 2) / (G.w / 2));
      k % 2 ? add(x, gy1, x, gy0, k % 5 === 0, d) : add(x, gy0, x, gy1, k % 5 === 0, d);
    }
    const ky0 = Math.ceil((gy0 - oy) / g), ky1 = Math.floor((gy1 - oy) / g);
    for (let k = ky0; k <= ky1; k++) {
      const y = Math.round(oy + k * g) + 0.5;
      const d = clamp(Math.abs(y - H / 2) / (G.h / 2));
      k % 2 ? add(gx1, y, gx0, y, k % 5 === 0, d) : add(gx0, y, gx1, y, k % 5 === 0, d);
    }
  }
  if (D.sheetFrame) scene.notes.push({ kind: 'frame', t0: 0, t1: Math.max(0.02, T.gridEnd) });

  // ---- construction lines ----
  const cs = T.constructStart, ce = T.constructEnd;
  const cons = [];
  const nH = Math.round(D.construction / 2), nV = D.construction - nH;
  an.hPeaks.slice(0, nH).forEach((pk) => { const y = oy + pk.p * s; cons.push({ pts: [0, y, W, y], s: pk.s }); });
  an.vPeaks.slice(0, nV).forEach((pk) => { const x = ox + pk.p * s; cons.push({ pts: [x, 0, x, H], s: pk.s }); });
  cons.sort((a, b) => b.s - a.s);
  cons.forEach((c, i) => {
    const t0 = cs + (i / Math.max(1, cons.length)) * span(cs, ce) * 0.7 + rnd() * 0.01;
    let pts = c.pts;
    if (rnd() < 0.5) pts = [pts[2], pts[3], pts[0], pts[1]];
    scene.ink.push(poly(pts, {
      w: S.constructionWidth * dpr, color: P.line, alpha: 0.42 * S.opacity, t0, t1: t0 + span(cs, ce) * 0.3,
      dash: S.dashedConstruction ? [8 * dpr, 6 * dpr] : null,
    }));
  });

  // centre lines (dash-dot) through the subject + main circles
  if (D.centerLines && an.chains.length) {
    const ext = Math.min(W, H) * 0.06;
    const cx = B.x + B.w / 2, cy = B.y + B.h / 2;
    const dd = [22 * dpr, 5 * dpr, 4 * dpr, 5 * dpr];
    const t0 = cs + span(cs, ce) * 0.55;
    scene.ink.push(poly([cx, B.y - ext, cx, B.y + B.h + ext], { w: S.constructionWidth * dpr, color: P.accent, alpha: 0.8 * S.opacity, dash: dd, t0, t1: t0 + span(cs, ce) * 0.4 }));
    scene.ink.push(poly([B.x - ext, cy, B.x + B.w + ext, cy], { w: S.constructionWidth * dpr, color: P.accent, alpha: 0.8 * S.opacity, dash: dd, t0: t0 + 0.02, t1: t0 + 0.02 + span(cs, ce) * 0.4 }));
    an.arcs.slice(0, Math.min(6, D.radii + 2)).forEach((a, i) => {
      const [x, y] = M(a.x, a.y), r = a.r * s * 1.25 + 6 * dpr;
      if (r < 10 * dpr) return;
      const tt = cs + span(cs, ce) * (0.6 + 0.06 * i);
      scene.ink.push(poly([x - r, y, x + r, y], { w: S.constructionWidth * dpr, color: P.accent, alpha: 0.7 * S.opacity, dash: dd, t0: tt, t1: tt + 0.05 }));
      scene.ink.push(poly([x, y - r, x, y + r], { w: S.constructionWidth * dpr, color: P.accent, alpha: 0.7 * S.opacity, dash: dd, t0: tt + 0.01, t1: tt + 0.06 }));
    });
  }

  // ---- contours (the actual drawing) ----
  const ds = T.drawStart, de = T.drawEnd;
  const chains = an.chains.slice(0, D.maxLines);
  const diag = Math.hypot(W, H);
  const multi = [P.m1, P.m2, P.m3, P.m4, P.line];
  chains.forEach((ch, rank) => {
    let pts = [];
    for (let i = 0; i < ch.pts.length; i += 2) { const [x, y] = M(ch.pts[i], ch.pts[i + 1]); pts.push(x, y); }
    if (cfg.detail.smooth && pts.length > 4) pts = chaikin(chaikin(pts, ch.closed), ch.closed);
    const len = ch.len * s;
    const imp = clamp(len / (diag * 0.25));
    const order = Math.pow(rank / Math.max(1, chains.length), 0.75);
    const dur = span(ds, de) * (0.035 + 0.22 * Math.sqrt(imp));
    let t0 = ds + order * span(ds, de) * 0.9 + (rnd() - 0.5) * 0.02;
    t0 = clamp(t0, ds, de - dur);
    let color = P.line;
    if (P.colorMode === 'multi') color = multi[hueIndex(ch.color, multi.length, rnd)];
    else if (P.colorMode === 'image') color = `rgb(${ch.color.map((v) => v | 0).join(',')})`;
    const el = poly(pts, {
      w: S.lineWidth * dpr * (0.55 + 0.45 * imp), color, alpha: S.opacity, t0, t1: t0 + dur,
      closed: ch.closed, style: S.style, jitter: S.jitter * dpr, overshoot: S.overshoot * dpr, rnd,
    });
    el.contour = true;
    scene.ink.push(el);
  });
  scene.stats.entities = chains.length;

  // ---- hatching on dark areas ----
  if (D.hatch) {
    const hs = T.drawStart + span(ds, de) * 0.45, he = Math.min(1, T.drawEnd + 0.08);
    const segs = [];
    const passes = [[D.hatchAngle, D.hatchThreshold]];
    if (D.crossHatch) passes.push([D.hatchAngle + 90, D.hatchThreshold * 0.6]);
    const step = 2 * dpr, gap = Math.max(2, D.hatchSpacing * dpr);
    for (const [deg, thr] of passes) {
      const a = (deg * Math.PI) / 180, dx = Math.cos(a), dy = Math.sin(a), nx = -dy, ny = dx;
      const corners = [[0, 0], [imgRect.w, 0], [0, imgRect.h], [imgRect.w, imgRect.h]].map(([x, y]) => [x + imgRect.x, y + imgRect.y]);
      const pn = corners.map(([x, y]) => x * nx + y * ny), pd = corners.map(([x, y]) => x * dx + y * dy);
      const n0 = Math.min(...pn), n1 = Math.max(...pn), d0 = Math.min(...pd), d1 = Math.max(...pd);
      for (let o = n0 + gap / 2; o < n1; o += gap) {
        let run = null;
        for (let t = d0; t <= d1 + step; t += step) {
          const x = nx * o + dx * t, y = ny * o + dy * t;
          const ax = (x - ox) / s, ay = (y - oy) / s;
          const inside = ax >= 0 && ay >= 0 && ax < an.w && ay < an.h && x >= 0 && y >= 0 && x <= W && y <= H;
          const dark = inside && an.lum[(ay | 0) * an.w + (ax | 0)] < thr;
          if (dark && !run) run = [x, y];
          if (!dark && run) {
            if (Math.hypot(x - run[0], y - run[1]) > 4 * dpr) segs.push({ pts: [run[0], run[1], x - dx * step, y - dy * step], o: (o - n0) / (n1 - n0 || 1) });
            run = null;
          }
        }
      }
    }
    const lim = segs.slice(0, 9000);
    lim.forEach((sg) => {
      const t0 = hs + sg.o * span(hs, he) * 0.75;
      scene.ink.push(poly(sg.pts, { w: S.constructionWidth * dpr * 0.9, color: P.line, alpha: 0.45 * S.opacity, t0, t1: t0 + span(hs, he) * 0.25 }));
    });
    scene.stats.hatch = lim.length;
  }

  // ---- annotations ----
  const as = T.annotateStart, ae = T.annotateEnd;
  const gap = clamp(bleedPx * 0.42, 16 * dpr, 64 * dpr);
  const fmt = (px) => fmtNum(px * mmPerPx, D.decimals);
  const notes = [];
  const used = [];
  const free = (r) => !used.some((u) => r.x < u.x + u.w && r.x + r.w > u.x && r.y < u.y + u.h && r.y + r.h > u.y);
  const claim = (r) => used.push(r);
  const onCanvas = (v, max) => v > ts * 1.6 && v < max - ts * 1.6;

  if (an.chains.length && D.dimensions > 0 && onCanvas(B.y - gap, H)) {
    notes.push({ kind: 'dim', dir: 'h', a: [B.x, B.y], b: [B.x + B.w, B.y], at: B.y - gap, label: fmt(B.w), pri: 1 });
    claim({ x: B.x, y: B.y - gap - ts, w: B.w, h: ts * 2 });
  }
  if (an.chains.length && D.dimensions > 1 && onCanvas(B.x - gap, W)) {
    notes.push({ kind: 'dim', dir: 'v', a: [B.x, B.y], b: [B.x, B.y + B.h], at: B.x - gap, label: fmt(B.h), pri: 1 });
    claim({ x: B.x - gap - ts, y: B.y, w: ts * 2, h: B.h });
  }

  // baseline / ordinate stacks (bottom from vertical features, right from horizontal features)
  if (D.baselineDims > 0) {
    const nb = Math.ceil(D.baselineDims / 2), nr = D.baselineDims - nb;
    const xs = an.vPeaks.map((p) => ox + p.p * s).filter((x) => x > B.x + Math.max(B.w * 0.08, 40 * dpr) && x <= B.x + B.w + 1).sort((a, b) => a - b);
    pickSpread(xs, nb).forEach((x, k) => {
      const at = B.y + B.h + gap * (0.8 + k * 0.7);
      if (!onCanvas(at, H)) return;
      notes.push({ kind: 'dim', dir: 'h', a: [B.x, B.y + B.h], b: [x, B.y + B.h], at, label: fmt(x - B.x), pri: 2 });
    });
    const ys = an.hPeaks.map((p) => oy + p.p * s).filter((y) => y >= B.y - 1 && y < B.y + B.h - Math.max(B.h * 0.08, 40 * dpr)).sort((a, b) => b - a);
    pickSpread(ys, nr).forEach((y, k) => {
      const at = B.x + B.w + gap * (0.8 + k * 0.7);
      if (!onCanvas(at, W)) return;
      notes.push({ kind: 'dim', dir: 'v', a: [B.x + B.w, B.y + B.h], b: [B.x + B.w, y], at, label: fmt(B.y + B.h - y), pri: 2 });
    });
  }

  // feature dimensions on individual parts
  let fd = Math.max(0, D.dimensions - 2);
  for (const ch of an.chains.slice(0, 120)) {
    if (fd <= 0) break;
    const bx = ox + ch.bbox.x * s, by = oy + ch.bbox.y * s, bw = ch.bbox.w * s, bh = ch.bbox.h * s;
    if (bw < B.w * 0.1 && bh < B.h * 0.1) continue;
    if (bw > B.w * 0.9 && bh > B.h * 0.9) continue;
    const horiz = bw >= bh ? rnd() < 0.75 : rnd() < 0.25;
    if (horiz && bw > 30 * dpr) {
      const at = by - gap * 0.55;
      const r = { x: bx - 4, y: at - ts, w: bw + 8, h: ts * 1.8 };
      if (!free(r) || !onCanvas(at, H)) continue;
      claim(r);
      notes.push({ kind: 'dim', dir: 'h', a: [bx, by], b: [bx + bw, by], at, label: fmt(bw), pri: 3 });
      fd--;
    } else if (!horiz && bh > 30 * dpr) {
      const at = bx + bw + gap * 0.55;
      const r = { x: at - ts, y: by - 4, w: ts * 1.8, h: bh + 8 };
      if (!free(r) || !onCanvas(at, W)) continue;
      claim(r);
      notes.push({ kind: 'dim', dir: 'v', a: [bx + bw, by], b: [bx + bw, by + bh], at, label: fmt(bh), pri: 3 });
      fd--;
    }
  }

  // radius / diameter callouts with compass sweep
  const cxI = B.x + B.w / 2, cyI = B.y + B.h / 2;
  const centres = [];
  for (const a of an.arcs) {
    if (centres.length >= D.radii) break;
    const [x, y] = M(a.x, a.y), r = a.r * s;
    if (r < 8 * dpr || r > Math.min(B.w, B.h) * 0.6 || x < 0 || y < 0 || x > W || y > H) continue;
    if (centres.some((c) => Math.hypot(c[0] - x, c[1] - y) < 40 * dpr)) continue;
    centres.push([x, y]);
    const full = a.span > 5.2;
    let la = Math.atan2(y - cyI, x - cxI);
    if (!isFinite(la) || (Math.abs(x - cxI) < 2 && Math.abs(y - cyI) < 2)) la = -Math.PI * 0.75;
    la = Math.round((la - Math.PI / 4) / (Math.PI / 2)) * (Math.PI / 2) + Math.PI / 4; // snap to diagonals
    const label = full ? `Ø${fmt(r * 2)}` : `R${fmt(r)}`;
    notes.push({ kind: 'radius', c: [x, y], r, a0: a.a0, a1: a.a1, ccw: a.ccw, full, la, label, pri: 3 });
  }

  // angle callouts
  let na = 0;
  for (const c of an.corners) {
    if (na >= D.angles) break;
    const [x, y] = M(c.x, c.y);
    if (centres.some((q) => Math.hypot(q[0] - x, q[1] - y) < 50 * dpr)) continue;
    centres.push([x, y]);
    const ra = clamp(c.strength * s * 0.4, 14 * dpr, 36 * dpr);
    notes.push({ kind: 'angle', c: [x, y], a1: c.a1, a2: c.a2, r: ra, label: `${fmtNum(c.deg, Math.min(1, D.decimals))}°`, pri: 3 });
    na++;
  }

  // reference markers
  const pts = [...an.arcs.map((a) => M(a.x, a.y)), ...an.corners.map((c) => M(c.x, c.y))];
  let nm = 0;
  for (const [x, y] of pts) {
    if (nm >= D.markers) break;
    if (x < 0 || y < 0 || x > W || y > H) continue;
    if (notes.some((n) => n.kind === 'marker' && Math.hypot(n.c[0] - x, n.c[1] - y) < 36 * dpr)) continue;
    notes.push({ kind: 'marker', c: [x, y], label: `${String.fromCharCode(65 + (nm % 26))}${1 + Math.floor(nm / 26)}`, pri: 4 });
    nm++;
  }

  // schedule: overall first, the rest shuffled so the sheet fills in organically
  const head = notes.filter((n) => n.pri === 1);
  const rest = notes.filter((n) => n.pri !== 1).sort(() => rnd() - 0.5);
  const ordered = [...head, ...rest];
  const nd = span(as, ae) * clamp(2.5 / Math.max(3, ordered.length), 0.08, 0.3);
  ordered.forEach((n, i) => {
    n.t0 = as + (i / Math.max(1, ordered.length - 1 || 1)) * Math.max(0, span(as, ae) - nd);
    n.t1 = n.t0 + nd;
    scene.notes.push(n);
  });
  if (D.titleBlock) scene.notes.push({ kind: 'title', t0: as + span(as, ae) * 0.55, t1: ae, seed: cfg.playback.seed });

  // ---- reveal brush strokes ----
  buildBrush(scene, cfg, rnd);

  scene.grid.sort((a, b) => a.t1 - b.t1);
  scene.ink.sort((a, b) => a.t1 - b.t1);
  return scene;
}

function pickSpread(arr, n) {
  if (n <= 0 || !arr.length) return [];
  if (arr.length <= n) return arr;
  const out = [];
  for (let i = 0; i < n; i++) out.push(arr[Math.round((i / Math.max(1, n - 1)) * (arr.length - 1))]);
  return [...new Set(out)];
}

function hueIndex([r, g, b], n, rnd) {
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
  if (mx - mn < 18) return Math.floor(rnd() * n);
  let h;
  if (mx === r) h = ((g - b) / (mx - mn)) % 6;
  else if (mx === g) h = (b - r) / (mx - mn) + 2;
  else h = (r - g) / (mx - mn) + 4;
  h = (h * 60 + 360) % 360;
  return Math.floor((h / 360) * n) % n;
}

/** Create a stroke element; style passes (sketch/pencil/brush) are baked here so rendering stays cheap. */
function poly(pts, o) {
  const el = { kind: 'poly', w: o.w, color: o.color, alpha: o.alpha, t0: o.t0, t1: o.t1, dash: o.dash || null, passes: [] };
  const style = o.style || 'flat';
  const rnd = o.rnd || Math.random;
  let base = pts;
  if (o.overshoot && !o.closed && pts.length >= 4) base = extend(pts, o.overshoot * (0.4 + rnd() * 0.8));
  const j = o.jitter || 0;
  const add = (p, alpha, wMul, taper = false) => el.passes.push({ pts: p, cum: cumLengths(p), alpha, wMul, taper });
  switch (style) {
    case 'pen':
      add(jitter(base, j * 0.3, rnd), 1, 1, true);
      break;
    case 'sketch':
      add(jitter(base, j * 0.4, rnd), 0.95, 1);
      add(jitter(o.overshoot && !o.closed ? extend(pts, o.overshoot * (0.3 + rnd())) : pts, j, rnd), 0.45, 0.7);
      break;
    case 'pencil':
      for (let k = 0; k < 3; k++) add(jitter(base, j, rnd), 0.34, 0.75 + rnd() * 0.4);
      break;
    case 'brush':
      add(jitter(base, j * 0.3, rnd), 0.85, 1.9, true);
      add(jitter(base, j, rnd), 0.5, 0.5);
      break;
    default:
      add(j ? jitter(base, j * 0.3, rnd) : base, 1, 1);
  }
  return el;
}

function extend(pts, d) {
  const n = pts.length / 2;
  const out = pts.slice();
  const ex = (ia, ib) => {
    const dx = pts[ia * 2] - pts[ib * 2], dy = pts[ia * 2 + 1] - pts[ib * 2 + 1];
    const l = Math.hypot(dx, dy) || 1;
    return [pts[ia * 2] + (dx / l) * d, pts[ia * 2 + 1] + (dy / l) * d];
  };
  const s0 = ex(0, 1), s1 = ex(n - 1, n - 2);
  out[0] = s0[0]; out[1] = s0[1];
  out[out.length - 2] = s1[0]; out[out.length - 1] = s1[1];
  return out;
}

function jitter(pts, amt, rnd) {
  if (!amt) return pts;
  const n = pts.length / 2;
  const out = new Array(pts.length);
  const f = 0.3 + rnd() * 0.5, ph = rnd() * TAU;
  for (let i = 0; i < n; i++) {
    const a = i > 0 ? i - 1 : i, b = i < n - 1 ? i + 1 : i;
    let nx = -(pts[b * 2 + 1] - pts[a * 2 + 1]), ny = pts[b * 2] - pts[a * 2];
    const l = Math.hypot(nx, ny) || 1;
    const off = amt * (Math.sin(i * f + ph) * 0.7 + (rnd() - 0.5) * 0.6);
    out[i * 2] = pts[i * 2] + (nx / l) * off;
    out[i * 2 + 1] = pts[i * 2 + 1] + (ny / l) * off;
  }
  return out;
}

function buildBrush(scene, cfg, rnd) {
  const R = cfg.reveal, T = cfg.timing, { W, H } = scene;
  const r = scene.imgRect;
  const x0 = Math.max(0, r.x), y0 = Math.max(0, r.y), x1 = Math.min(W, r.x + r.w), y1 = Math.min(H, r.y + r.h);
  const rw = x1 - x0, rh = y1 - y0;
  const size = Math.max(8, R.brushSize * Math.min(rw, rh));
  const rs = T.revealStart, re = Math.max(T.revealStart + 0.01, T.revealEnd);
  const sweepEnd = rs + (re - rs) * 0.82;
  const strokes = [];

  const wav = (u, ph, f) => Math.sin(u * Math.PI * f + ph) * R.wobble * size * 0.6;

  if (R.mode === 'radial') {
    const cx = x0 + rw / 2, cy = y0 + rh / 2, maxR = Math.hypot(rw, rh) / 2 + size / 2;
    const turns = maxR / (size * 0.6);
    const pts = [];
    const steps = Math.ceil(turns * 48);
    for (let i = 0; i <= steps; i++) {
      const u = i / steps, a = u * turns * TAU, rr = u * maxR;
      pts.push(cx + Math.cos(a) * rr + wav(u, 0, 9) * 0.3, cy + Math.sin(a) * rr);
    }
    strokes.push({ pts, order: 0 });
  } else if (R.mode !== 'scribble') {
    const deg = R.mode === 'horizontal' ? 0 : R.mode === 'vertical' ? 90 : R.angle;
    const a = (deg * Math.PI) / 180, dx = Math.cos(a), dy = Math.sin(a), nx = -dy, ny = dx;
    const corners = [[x0, y0], [x1, y0], [x0, y1], [x1, y1]];
    const pn = corners.map(([x, y]) => x * nx + y * ny), pd = corners.map(([x, y]) => x * dx + y * dy);
    const n0 = Math.min(...pn) - size * 0.3, n1 = Math.max(...pn) + size * 0.3;
    const d0 = Math.min(...pd) - size, d1 = Math.max(...pd) + size;
    let k = 0;
    for (let o = n0; o <= n1; o += size * 0.62, k++) {
      const pts = [];
      const ph = rnd() * TAU, f = 1 + rnd() * 2;
      for (let i = 0; i <= 24; i++) {
        const u = i / 24, t = k % 2 ? d1 - u * (d1 - d0) : d0 + u * (d1 - d0);
        const oo = o + wav(u, ph, f);
        pts.push(nx * oo + dx * t, ny * oo + dy * t);
      }
      strokes.push({ pts, order: k });
    }
  }
  // free dabs/scribbles (also the whole reveal in scribble mode)
  const dabs = R.mode === 'scribble' ? Math.max(6, R.dabs) : R.dabs;
  for (let i = 0; i < dabs; i++) {
    const pts = [];
    let px = x0 + rnd() * rw, py = y0 + rnd() * rh, ang = rnd() * TAU;
    const L = size * (2 + rnd() * 4);
    for (let k = 0; k <= 16; k++) {
      pts.push(px, py);
      ang += (rnd() - 0.5) * 0.9;
      px += Math.cos(ang) * (L / 16);
      py += Math.sin(ang) * (L / 16);
    }
    strokes.push({ pts, order: rnd() * 1e3, dab: true });
  }

  const sweeps = strokes.filter((s) => !s.dab).length;
  strokes.forEach((st, i) => {
    let t0, t1;
    if (st.dab) {
      t0 = rs + rnd() * (sweepEnd - rs) * 0.8;
      t1 = t0 + (sweepEnd - rs) * (0.12 + rnd() * 0.12);
    } else if (R.mode === 'radial') {
      t0 = rs; t1 = sweepEnd;
    } else {
      const f = st.order / Math.max(1, sweeps);
      t0 = rs + f * (sweepEnd - rs) * 0.72;
      t1 = t0 + (sweepEnd - rs) * 0.28;
    }
    // bristles: thinner parallel hairs that give a dry-brush edge
    const bristles = [];
    const nb = Math.round(R.bristles * 9);
    for (let b = 0; b < nb; b++) bristles.push({ off: (rnd() - 0.5) * size * 1.05, w: size * (0.06 + rnd() * 0.12), a: 0.25 + rnd() * 0.5 });
    const n = st.pts.length / 2;
    const dirx = st.pts[n * 2 - 2] - st.pts[0], diry = st.pts[n * 2 - 1] - st.pts[1];
    const dl = Math.hypot(dirx, diry) || 1;
    scene.brush.push({ pts: st.pts, cum: cumLengths(st.pts), size: st.dab ? size * (0.6 + rnd() * 0.5) : size, t0, t1, bristles, nx: -diry / dl, ny: dirx / dl });
  });
  scene.reveal = { rs, re, fillStart: rs + (re - rs) * 0.7 };
}

// Drawing routines for one frame. Everything is a pure function of (scene, u, cfg).

function font(size, italic, weight = 500) {
  return `${italic ? 'italic ' : ''}${weight} ${size}px "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace`;
}

/** Stroke the [f0, f1] fraction of a polyline. Returns the tip at f1. */
function traceRange(ctx, pts, cum, f0, f1) {
  const n = cum.length, total = cum[n - 1];
  const s = total * f0, e = total * f1;
  let started = false, tx = pts[0], ty = pts[1];
  for (let i = 1; i < n; i++) {
    const a = cum[i - 1], b = cum[i];
    if (b < s) continue;
    const seg = b - a || 1;
    if (!started) {
      const k = Math.max(0, (s - a) / seg);
      ctx.moveTo(lerp(pts[i * 2 - 2], pts[i * 2], k), lerp(pts[i * 2 - 1], pts[i * 2 + 1], k));
      started = true;
    }
    if (b >= e) {
      const k = (e - a) / seg;
      tx = lerp(pts[i * 2 - 2], pts[i * 2], k); ty = lerp(pts[i * 2 - 1], pts[i * 2 + 1], k);
      ctx.lineTo(tx, ty);
      return [tx, ty];
    }
    tx = pts[i * 2]; ty = pts[i * 2 + 1];
    ctx.lineTo(tx, ty);
  }
  return [tx, ty];
}

function drawPoly(ctx, el, frac, alphaMul) {
  if (frac <= 0) return null;
  ctx.strokeStyle = el.color;
  ctx.setLineDash(el.dash || []);
  let tip = null;
  for (const p of el.passes) {
    ctx.globalAlpha = el.alpha * p.alpha * alphaMul;
    if (p.taper) {
      ctx.lineWidth = el.w * p.wMul * 0.45;
      ctx.beginPath(); tip = traceRange(ctx, p.pts, p.cum, 0, frac); ctx.stroke();
      const a = 0.08, b = Math.min(frac, 0.92);
      if (b > a) { ctx.lineWidth = el.w * p.wMul; ctx.beginPath(); traceRange(ctx, p.pts, p.cum, a, b); ctx.stroke(); }
    } else {
      ctx.lineWidth = el.w * p.wMul;
      ctx.beginPath(); tip = traceRange(ctx, p.pts, p.cum, 0, frac); ctx.stroke();
    }
  }
  return tip;
}

// ---------- annotation primitives ----------
function arrowHead(ctx, x, y, ang, size, style) {
  const c = Math.cos(ang), s = Math.sin(ang);
  if (style === 'tick') {
    const k = size * 0.6;
    ctx.beginPath(); ctx.moveTo(x - k * 0.7, y + k * 0.7); ctx.lineTo(x + k * 0.7, y - k * 0.7); ctx.stroke();
    return;
  }
  if (style === 'dot') { ctx.beginPath(); ctx.arc(x, y, size * 0.22, 0, TAU); ctx.fill(); return; }
  const bx = x - c * size, by = y - s * size, w = size * 0.32;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(bx - s * w, by + c * w);
  if (style === 'open') { ctx.moveTo(x, y); ctx.lineTo(bx + s * w, by - c * w); ctx.stroke(); return; }
  ctx.lineTo(bx + s * w, by - c * w);
  ctx.closePath();
  ctx.fill();
}

function counted(n, p) {
  if (!n._parsed) {
    const m = String(n.label).match(/^([^\d-]*)(-?\d+(?:\.\d+)?)(.*)$/);
    n._parsed = m ? { pre: m[1], num: parseFloat(m[2]), dec: (m[2].split('.')[1] || '').length, suf: m[3] } : null;
  }
  const q = n._parsed;
  if (!q) return n.label;
  if (p >= 1) return n.label;
  return `${q.pre}${(q.num * EASES.easeOut(p)).toFixed(q.dec)}${q.suf}`;
}

function textBox(ctx, txt, x, y, bg, knock) {
  if (knock > 0.01) {
    const w = ctx.measureText(txt).width, h = parseFloat(ctx.font.match(/(\d+(?:\.\d+)?)px/)[1]);
    const prev = ctx.fillStyle, pa = ctx.globalAlpha;
    ctx.fillStyle = bg;
    ctx.globalAlpha = pa * knock;
    ctx.fillRect(x - w / 2 - h * 0.25, y - h * 0.62, w + h * 0.5, h * 1.24);
    ctx.fillStyle = prev;
    ctx.globalAlpha = pa;
  }
  ctx.fillText(txt, x, y);
}

const sub = (p, a, b) => clamp((p - a) / (b - a));

function drawNote(ctx, n, u, scene, cfg, alpha) {
  const p = prog(u, n.t0, n.t1);
  if (p <= 0) return;
  const P = cfg.palette, D = cfg.drafting, S = cfg.stroke;
  const dpr = scene.dpr, ts = D.textSize * dpr;
  const E = EASES.easeInOut;
  ctx.setLineDash([]);
  ctx.lineCap = 'round';
  ctx.strokeStyle = P.dim;
  ctx.fillStyle = P.dim;
  ctx.lineWidth = S.dimWidth * dpr;
  ctx.globalAlpha = alpha;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const ah = 9 * dpr * D.arrowSize;

  switch (n.kind) {
    case 'dim': {
      const [ax, ay] = n.a, [bx, by] = n.b, at = n.at;
      const pe = E(sub(p, 0, 0.35)), pl = E(sub(p, 0.15, 0.7)), pt = sub(p, 0.3, 1);
      const off = 3 * dpr, over = 5 * dpr;
      ctx.beginPath();
      if (n.dir === 'h') {
        const sa = Math.sign(at - ay) || -1, sb = Math.sign(at - by) || -1;
        ctx.moveTo(ax, ay + sa * off); ctx.lineTo(ax, lerp(ay + sa * off, at + sa * over, pe));
        ctx.moveTo(bx, by + sb * off); ctx.lineTo(bx, lerp(by + sb * off, at + sb * over, pe));
        ctx.stroke();
        if (pl > 0) {
          const mx = (ax + bx) / 2, l = mx - (mx - ax) * pl, r = mx + (bx - mx) * pl;
          ctx.beginPath(); ctx.moveTo(l, at); ctx.lineTo(r, at); ctx.stroke();
          arrowHead(ctx, l, at, ax < bx ? Math.PI : 0, ah, D.arrowStyle);
          arrowHead(ctx, r, at, ax < bx ? 0 : Math.PI, ah, D.arrowStyle);
        }
        if (pt > 0) {
          ctx.fillStyle = P.text;
          ctx.font = font(ts, D.italic);
          ctx.globalAlpha = alpha * clamp(pt * 3);
          textBox(ctx, counted(n, pt), (ax + bx) / 2, at - ts * 0.75, P.bg, D.knockout ? scene.knockA : 0);
        }
      } else {
        const sa = Math.sign(at - ax) || -1, sb = Math.sign(at - bx) || -1;
        ctx.moveTo(ax + sa * off, ay); ctx.lineTo(lerp(ax + sa * off, at + sa * over, pe), ay);
        ctx.moveTo(bx + sb * off, by); ctx.lineTo(lerp(bx + sb * off, at + sb * over, pe), by);
        ctx.stroke();
        if (pl > 0) {
          const my = (ay + by) / 2, t = my - (my - ay) * pl, b = my + (by - my) * pl;
          ctx.beginPath(); ctx.moveTo(at, t); ctx.lineTo(at, b); ctx.stroke();
          arrowHead(ctx, at, t, ay < by ? -Math.PI / 2 : Math.PI / 2, ah, D.arrowStyle);
          arrowHead(ctx, at, b, ay < by ? Math.PI / 2 : -Math.PI / 2, ah, D.arrowStyle);
        }
        if (pt > 0) {
          ctx.save();
          ctx.translate(at - ts * 0.75, (ay + by) / 2);
          ctx.rotate(-Math.PI / 2);
          ctx.fillStyle = P.text;
          ctx.font = font(ts, D.italic);
          ctx.globalAlpha = alpha * clamp(pt * 3);
          textBox(ctx, counted(n, pt), 0, 0, P.bg, D.knockout ? scene.knockA : 0);
          ctx.restore();
        }
      }
      break;
    }
    case 'radius': {
      const [cx, cy] = n.c, r = n.r;
      const pc = sub(p, 0, 0.15), ps = E(sub(p, 0.05, 0.6)), pl = E(sub(p, 0.5, 0.75)), pt = sub(p, 0.6, 1);
      // centre mark
      const cm = 6 * dpr * EASES.backOut(pc);
      ctx.beginPath(); ctx.moveTo(cx - cm, cy); ctx.lineTo(cx + cm, cy); ctx.moveTo(cx, cy - cm); ctx.lineTo(cx, cy + cm); ctx.stroke();
      // faint construction circle
      if (!n.full && ps > 0) {
        ctx.save();
        ctx.globalAlpha = alpha * 0.35;
        ctx.setLineDash([4 * dpr, 4 * dpr]);
        ctx.beginPath(); ctx.arc(cx, cy, r, n.a0, n.a0 + TAU * ps); ctx.stroke();
        ctx.restore();
      }
      // compass sweep along the real arc
      let sweep;
      if (n.full) sweep = TAU;
      else {
        let d = n.ccw ? n.a0 - n.a1 : n.a1 - n.a0;
        d = ((d % TAU) + TAU) % TAU || TAU;
        sweep = d;
      }
      const dir = n.ccw ? -1 : 1;
      const end = n.a0 + dir * sweep * ps;
      if (ps > 0) {
        ctx.strokeStyle = P.accent;
        ctx.lineWidth = S.dimWidth * dpr * 1.6;
        ctx.beginPath(); ctx.arc(cx, cy, r, n.a0, end, n.ccw); ctx.stroke();
        const armA = alpha * (1 - sub(p, 0.6, 0.75));
        if (armA > 0) {
          ctx.globalAlpha = armA;
          ctx.lineWidth = S.dimWidth * dpr;
          ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(end) * r, cy + Math.sin(end) * r); ctx.stroke();
          ctx.beginPath(); ctx.arc(cx + Math.cos(end) * r, cy + Math.sin(end) * r, 2.5 * dpr, 0, TAU); ctx.fillStyle = P.accent; ctx.fill();
          ctx.globalAlpha = alpha;
        }
        ctx.strokeStyle = P.dim; ctx.fillStyle = P.dim; ctx.lineWidth = S.dimWidth * dpr;
      }
      // leader
      if (pl > 0) {
        const sx = cx + Math.cos(n.la) * r, sy = cy + Math.sin(n.la) * r;
        const L1 = Math.max(26 * dpr, r * 0.35);
        const ex = sx + Math.cos(n.la) * L1, ey = sy + Math.sin(n.la) * L1;
        const sh = (Math.cos(n.la) >= 0 ? 1 : -1) * 46 * dpr;
        const l1 = clamp(pl * 1.6), l2 = clamp(pl * 1.6 - 0.6);
        ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(lerp(sx, ex, l1), lerp(sy, ey, l1));
        if (l2 > 0) ctx.lineTo(ex + sh * l2, ey);
        ctx.stroke();
        arrowHead(ctx, sx, sy, n.la + Math.PI, ah, D.arrowStyle === 'tick' ? 'arrow' : D.arrowStyle);
        if (pt > 0) {
          ctx.fillStyle = P.text;
          ctx.font = font(ts, D.italic);
          ctx.globalAlpha = alpha * clamp(pt * 3);
          ctx.textAlign = sh > 0 ? 'left' : 'right';
          ctx.fillText(counted(n, pt), ex + (sh > 0 ? 4 * dpr : -4 * dpr), ey - ts * 0.7);
        }
      }
      break;
    }
    case 'angle': {
      const [cx, cy] = n.c, r = n.r;
      let d = n.a2 - n.a1;
      d = Math.atan2(Math.sin(d), Math.cos(d));
      const ps = E(sub(p, 0, 0.6)), pt = sub(p, 0.4, 1);
      const cur = n.a1 + d * ps;
      ctx.beginPath(); ctx.arc(cx, cy, r, n.a1, cur, d < 0); ctx.stroke();
      const rayA = alpha * (1 - sub(p, 0.6, 0.8));
      if (rayA > 0) {
        ctx.globalAlpha = rayA;
        ctx.strokeStyle = P.accent;
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(cur) * (r + 10 * dpr), cy + Math.sin(cur) * (r + 10 * dpr)); ctx.stroke();
        ctx.strokeStyle = P.dim; ctx.globalAlpha = alpha;
      }
      if (ps > 0.98) {
        arrowHead(ctx, cx + Math.cos(n.a1) * r, cy + Math.sin(n.a1) * r, n.a1 - Math.sign(d) * Math.PI / 2, ah * 0.7, D.arrowStyle);
        arrowHead(ctx, cx + Math.cos(n.a2) * r, cy + Math.sin(n.a2) * r, n.a2 + Math.sign(d) * Math.PI / 2, ah * 0.7, D.arrowStyle);
      }
      if (pt > 0) {
        const bis = n.a1 + d / 2, rr = r + ts * 1.1;
        ctx.fillStyle = P.text;
        ctx.font = font(ts * 0.9, D.italic);
        ctx.globalAlpha = alpha * clamp(pt * 3);
        textBox(ctx, counted(n, pt), cx + Math.cos(bis) * rr, cy + Math.sin(bis) * rr, P.bg, D.knockout ? scene.knockA : 0);
      }
      break;
    }
    case 'marker': {
      const [cx, cy] = n.c;
      const k = EASES.backOut(sub(p, 0, 0.5));
      ctx.strokeStyle = P.accent;
      ctx.beginPath(); ctx.arc(cx, cy, 6 * dpr * k, 0, TAU); ctx.stroke();
      const l = 11 * dpr * k;
      ctx.beginPath(); ctx.moveTo(cx - l, cy); ctx.lineTo(cx + l, cy); ctx.moveTo(cx, cy - l); ctx.lineTo(cx, cy + l); ctx.stroke();
      const pt = sub(p, 0.3, 1);
      if (pt > 0) {
        ctx.fillStyle = P.accent;
        ctx.font = font(ts * 0.75, D.italic, 600);
        ctx.textAlign = 'left';
        ctx.globalAlpha = alpha * pt;
        ctx.fillText(n.label, cx + 9 * dpr, cy - 10 * dpr);
      }
      break;
    }
    case 'frame': drawFrame(ctx, p, scene, cfg, alpha); break;
    case 'title': drawTitle(ctx, p, n, scene, cfg, alpha); break;
  }
}

function rectPath(ctx, x, y, w, h, f) {
  const per = 2 * (w + h);
  let L = per * f;
  ctx.moveTo(x, y);
  const seg = [[x + w, y], [x + w, y + h], [x, y + h], [x, y]];
  let px = x, py = y;
  for (const [qx, qy] of seg) {
    const d = Math.hypot(qx - px, qy - py);
    if (L >= d) { ctx.lineTo(qx, qy); L -= d; px = qx; py = qy; }
    else { ctx.lineTo(px + ((qx - px) * L) / d, py + ((qy - py) * L) / d); break; }
  }
}

function drawFrame(ctx, p, scene, cfg, alpha) {
  const { W, H, dpr } = scene, P = cfg.palette, D = cfg.drafting;
  const m = 14 * dpr, m2 = m + 9 * dpr;
  const e = EASES.easeInOut(p);
  ctx.strokeStyle = P.dim;
  ctx.globalAlpha = alpha * 0.9;
  ctx.lineWidth = dpr;
  ctx.beginPath(); rectPath(ctx, m, m, W - 2 * m, H - 2 * m, e); ctx.stroke();
  ctx.lineWidth = 2 * dpr;
  ctx.beginPath(); rectPath(ctx, m2, m2, W - 2 * m2, H - 2 * m2, clamp(e * 1.15 - 0.15)); ctx.stroke();
  const zt = clamp(p * 2 - 1);
  if (zt <= 0) return;
  ctx.lineWidth = dpr;
  ctx.globalAlpha = alpha * zt;
  ctx.fillStyle = P.text;
  ctx.font = font(8 * dpr, false, 500);
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  const nx = 8, ny = 6;
  for (let i = 1; i < nx; i++) {
    const x = m2 + ((W - 2 * m2) * i) / nx;
    ctx.beginPath(); ctx.moveTo(x, m); ctx.lineTo(x, m2); ctx.moveTo(x, H - m); ctx.lineTo(x, H - m2); ctx.stroke();
  }
  for (let i = 0; i < nx; i++) {
    const x = m2 + ((W - 2 * m2) * (i + 0.5)) / nx;
    ctx.fillText(String(nx - i), x, (m + m2) / 2);
    ctx.fillText(String(nx - i), x, H - (m + m2) / 2);
  }
  for (let i = 1; i < ny; i++) {
    const y = m2 + ((H - 2 * m2) * i) / ny;
    ctx.beginPath(); ctx.moveTo(m, y); ctx.lineTo(m2, y); ctx.moveTo(W - m, y); ctx.lineTo(W - m2, y); ctx.stroke();
  }
  for (let i = 0; i < ny; i++) {
    const y = m2 + ((H - 2 * m2) * (i + 0.5)) / ny;
    const L = String.fromCharCode(65 + (ny - 1 - i));
    ctx.fillText(L, (m + m2) / 2, y);
    ctx.fillText(L, W - (m + m2) / 2, y);
  }
}

function drawTitle(ctx, p, n, scene, cfg, alpha) {
  const { W, H, dpr } = scene, P = cfg.palette, D = cfg.drafting;
  const inset = (cfg.drafting.sheetFrame ? 23 : 12) * dpr;
  const w = Math.min(320 * dpr, W * 0.42), h = 76 * dpr;
  const x = W - inset - w, y = H - inset - h;
  const pb = EASES.easeInOut(sub(p, 0, 0.4)), pi = sub(p, 0.3, 0.6), pt = sub(p, 0.4, 1);
  ctx.globalAlpha = alpha * pb;
  ctx.fillStyle = P.bg;
  ctx.fillRect(x, y, w, h);
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = P.dim;
  ctx.lineWidth = 1.5 * dpr;
  ctx.beginPath(); rectPath(ctx, x, y, w, h, pb); ctx.stroke();
  const r1 = y + h * 0.48;
  const cols = [0, 0.34, 0.56, 0.76, 1].map((f) => x + w * f);
  ctx.lineWidth = dpr;
  if (pi > 0) {
    ctx.beginPath();
    ctx.moveTo(x, r1); ctx.lineTo(x + w * pi, r1);
    for (let i = 1; i < cols.length - 1; i++) { ctx.moveTo(cols[i], r1); ctx.lineTo(cols[i], r1 + (y + h - r1) * pi); }
    ctx.stroke();
  }
  if (pt <= 0) return;
  const type = (s) => s.slice(0, Math.ceil(s.length * clamp(pt * 1.4)));
  const date = new Date();
  const fields = [
    ['DWG NO.', `TD-${String(n.seed).padStart(4, '0')}`],
    ['SCALE', '1:1'],
    ['SHEET', '1/1'],
    ['DATE', `${String(date.getDate()).padStart(2, '0')}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getFullYear()).slice(2)}`],
  ];
  ctx.fillStyle = P.text;
  ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  ctx.font = font(15 * dpr, D.italic, 600);
  ctx.fillText(type(D.title || 'TECHNICAL DRAWING'), x + 10 * dpr, y + h * 0.33);
  fields.forEach(([k, v], i) => {
    ctx.font = font(7 * dpr, false, 500);
    ctx.globalAlpha = alpha * 0.7;
    ctx.fillText(type(k), cols[i] + 6 * dpr, r1 + 12 * dpr);
    ctx.font = font(11 * dpr, D.italic, 600);
    ctx.globalAlpha = alpha;
    ctx.fillText(type(v), cols[i] + 6 * dpr, y + h - 9 * dpr);
  });
}

/** Plotter head: follows the newest active line with crosshair + coordinate readout. */
function drawHead(ctx, head, scene, cfg, alpha) {
  if (!head || head.a <= 0.01) return;
  const { W, H, dpr, B, mmPerPx } = scene, P = cfg.palette, D = cfg.drafting;
  const { x, y } = head;
  ctx.setLineDash([]);
  ctx.globalAlpha = alpha * head.a * 0.22;
  ctx.strokeStyle = P.accent;
  ctx.lineWidth = dpr;
  ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  ctx.globalAlpha = alpha * head.a;
  const s = 7 * dpr;
  ctx.strokeRect(x - s, y - s, s * 2, s * 2);
  ctx.beginPath(); ctx.arc(x, y, 1.8 * dpr, 0, TAU); ctx.fillStyle = P.accent; ctx.fill();
  if (D.readout) {
    const rx = (x - B.x) * mmPerPx, ry = (B.y + B.h - y) * mmPerPx;
    ctx.font = font(10 * dpr, false, 500);
    ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    const tx = x + 12 * dpr, ty = y + 10 * dpr;
    const l1 = `X ${rx.toFixed(2)}`, l2 = `Y ${ry.toFixed(2)}`;
    const w = Math.max(ctx.measureText(l1).width, ctx.measureText(l2).width) + 10 * dpr;
    ctx.globalAlpha = alpha * head.a * 0.85;
    ctx.fillStyle = P.bg;
    ctx.fillRect(tx - 5 * dpr, ty - 4 * dpr, w, 30 * dpr);
    ctx.globalAlpha = alpha * head.a;
    ctx.fillStyle = P.accent;
    ctx.fillText(l1, tx, ty);
    ctx.fillText(l2, tx, ty + 13 * dpr);
  }
}

function drawHud(ctx, scene, cfg, u, info, alpha) {
  const { dpr, H } = scene, P = cfg.palette, T = cfg.timing;
  const phase = u < T.gridEnd ? 'GRID' : u < T.constructEnd ? 'CONSTRUCT' : u < T.drawEnd ? 'LINE' : u < T.annotateEnd ? 'DIMENSION' : u < T.revealEnd ? 'RENDER' : 'DONE';
  const inset = (cfg.drafting.sheetFrame ? 30 : 16) * dpr;
  ctx.globalAlpha = alpha;
  ctx.fillStyle = P.text;
  ctx.font = font(10 * dpr, false, 500);
  ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  const blink = Math.floor(performance.now() / 450) % 2 ? '_' : ' ';
  ctx.fillText(`> ${phase}${blink}`, inset, H - inset - 14 * dpr);
  ctx.globalAlpha = alpha * 0.7;
  ctx.fillText(`ENT ${String(info.done).padStart(4, '0')}/${String(info.total).padStart(4, '0')}   T ${(u * 100).toFixed(1).padStart(5, '0')}%`, inset, H - inset);
}

// 공개 옵션: 기본값, 병합, 엔진 내부 config로의 해석.
// 옵션 그룹은 studio 표지 패널과 1:1로 대응되어 "파라미터 복사" 출력을 그대로 붙여넣을 수 있다.

const DEFAULTS = {
  playback: {
    duration: 10, // seconds the drawing takes (0 → 1 progress)
    hold: 2.5, // seconds to hold the finished frame before looping / ending
    speed: 0.8,
    loop: true,
    autoplay: true, // true | 'inView' | false
    seed: 7, // changes the random choices (ordering, which features get dimensioned…)
    pixelRatio: 2, // max device pixel ratio used for the canvas
    reducedMotion: 'end', // 'end' = show the finished frame when the user prefers reduced motion; 'play' = ignore
  },
  layout: {
    bleed: 0.14, // margin around the image (fraction of image size) that lines may overflow into
    gridOverflow: 0.6, // how far grid / plate extend into the bleed (0–1)
    edgeFade: 0.9, // soft fade of everything toward the canvas edge (0–1)
  },
  colors: {
    preset: 'ink', // ink | graphite | drafting | blueline | blueprint | retro | amber | phosphor
    colorMode: 'multi', // single | multi | image
    // plate, bg, grid, line, accent, dim, text, inks.m1–m4 default to the preset's values
  },
  detection: {
    preset: 'photo', // 'photo' = fixed defaults | 'auto' = classify after analysis (schematics get diagram-tuned detection)
    maxLines: 1370,
    sensitivity: 0.3,
    minLength: 39,
    blur: 1.1,
    simplify: 1.1,
    resolution: 830,
    smooth: true,
  },
  drafting: {
    sheet: { grid: true, gridSize: 10, gridOpacity: 0.33, sheetFrame: false, titleBlock: false, title: 'COVER DRAWING' },
    construction: { construction: 24, centerLines: true },
    measure: { dimensions: 3, baselineDims: 5, radii: 10, angles: 3, markers: 7, realWidth: 269, decimals: 3 },
    type: { textSize: 13, italic: true, knockout: true, arrowStyle: 'open', arrowSize: 1 },
    hatching: { hatch: false, hatchSpacing: 8.5, hatchThreshold: 0.32, hatchAngle: 34, crossHatch: true },
    live: { plotter: true, readout: true, hud: false },
  },
  stroke: {
    style: 'flat', // flat | pen | sketch | pencil | brush
    lineWidth: 1.7,
    constructionWidth: 0.9,
    dimWidth: 2.15,
    opacity: 1,
    overshoot: 10.5,
    jitter: 0,
    dashedConstruction: true,
  },
  timing: {
    // phase windows as fractions of `duration`
    ease: 'easeInOut', // easeInOut | easeOut | expoOut | smooth | linear
    gridEnd: 0.1,
    constructStart: 0.03,
    constructEnd: 0.3,
    drawStart: 0.1,
    drawEnd: 0.62,
    annotateStart: 0.3,
    annotateEnd: 0.8,
    revealStart: 0.52,
    revealEnd: 0.75,
  },
  reveal: {
    mode: 'sweep', // sweep | horizontal | vertical | radial | scribble
    angle: -45,
    brushSize: 0.18,
    dabs: 9,
    wobble: 0.59,
    softness: 10,
    bristles: 0.3,
    keepLines: 1, // 0 = linework fades away, 1 = stays on top of the image
    imageMode: 'original', // original | duotone | mono | inverted
    lineBlend: 'screen', // any canvas composite op: source-over | screen | multiply | overlay | difference | lighter
  },
};

const isObj = (v) => v && typeof v === 'object' && !Array.isArray(v);

/** {"sheet.grid": true} → {sheet: {grid: true}} (dotted 키 JSON을 그대로 받는다). */
function expandDotted(obj) {
  if (!isObj(obj)) return obj;
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    const val = isObj(v) && !('type' in v) ? expandDotted(v) : v;
    if (!k.includes('.')) { out[k] = isObj(val) && isObj(out[k]) ? deepMerge(out[k], val) : val; continue; }
    const parts = k.split('.');
    let cur = out;
    for (let i = 0; i < parts.length - 1; i++) cur = isObj(cur[parts[i]]) ? cur[parts[i]] : (cur[parts[i]] = {});
    cur[parts[parts.length - 1]] = val;
  }
  return out;
}

function deepMerge(base, over) {
  if (!isObj(over)) return over === undefined ? base : over;
  const out = { ...base };
  for (const [k, v] of Object.entries(over)) {
    if (v === undefined) continue;
    out[k] = isObj(v) && isObj(base?.[k]) ? deepMerge(base[k], v) : v;
  }
  return out;
}

/** Public options (partial) → complete public options with defaults applied and colours filled from the preset. */
function withDefaults(options = {}) {
  const o = deepMerge(DEFAULTS, expandDotted(stripRuntime(options)));
  // dotted 키 JSON을 그대로 받는다: export.pixelRatio 폴더, 문자열 autoplay 선택값
  const { export: ex, ...pb } = o.playback;
  o.playback = { ...pb, pixelRatio: ex?.pixelRatio ?? pb.pixelRatio };
  if (o.playback.autoplay === 'true') o.playback.autoplay = true;
  if (o.playback.autoplay === 'false') o.playback.autoplay = false;
  const preset = PALETTES[o.colors.preset] || PALETTES.ink;
  const { m1, m2, m3, m4, ...base } = preset;
  o.colors = deepMerge({ ...base, inks: { m1, m2, m3, m4 } }, o.colors);
  return o;
}

const RUNTIME_KEYS = ['src', 'alt', 'progress', 'onReady', 'onComplete', 'onError', 'onAspect', 'className', 'style'];
function stripRuntime(o) {
  const out = {};
  for (const [k, v] of Object.entries(o || {})) if (!RUNTIME_KEYS.includes(k) && typeof v !== 'function') out[k] = v;
  return out;
}

/** Public options → the engine's internal config shape. */
function resolveOptions(options = {}) {
  const o = withDefaults(options);
  const { inks, preset, ...colors } = o.colors;
  const progress = typeof options.progress === 'number' ? options.progress : null;
  return {
    source: { ...o.layout },
    playback: {
      ...o.playback,
      dpr: o.playback.pixelRatio,
      scrub: progress !== null,
      progress: progress ?? 0,
    },
    palette: { ...colors, ...inks, preset },
    detail: { ...o.detection },
    drafting: Object.assign({}, ...Object.values(o.drafting)),
    stroke: { ...o.stroke },
    timing: { ...o.timing },
    reveal: { ...o.reveal },
  };
}

// RevealEngine — 프레임워크 없이 동작하는 리빌 엔진. canvas와 이미지 URL, 해석된 config만 주면
// CAD식 "제도" 인트로가 재생되고 브러시 마스크로 이미지가 드러난다.
// 일반적인 사용처는 options·기본값을 덧대는 createCoverReveal()(파일 말미 진입 함수)이다.


const MASK_SCALE = 0.25;
const mk = () => document.createElement('canvas');

/** Diagram-tuned detection: keep thin box edges at (near) native resolution, drop
 *  text-glyph fragments, and disable polyline smoothing (chaikin rounds corners). */
function applyDiagramDetail(d, img) {
  const side = Math.max(img?.naturalWidth || 1600, img?.naturalHeight || 1600);
  d.resolution = Math.min(1600, side);
  d.sensitivity = 0.35;
  d.minLength = 42;
  d.blur = 0.7;
  d.simplify = 0.8;
  d.smooth = false;
}

class RevealEngine {
  constructor(canvas, { onState } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.layers = { grid: mk(), ink: mk(), image: mk(), reveal: mk(), mask: mk(), fade: mk() };
    this.cache = { grid: { idx: 0, u: -1 }, ink: { idx: 0, u: -1, done: 0 } };
    this.onState = onState || (() => {});
    this.time = 0;
    this.playing = false;
    this.visible = true;
    this.dirty = true;
    this.completed = false;
    this.cfg = null;
    this.img = null;
    this.an = null;
    this.imgType = null;
    this.autoTuned = false;
    this.scene = null;
    this.head = null;
    this.need = { analyze: false, build: false, image: false };
    this.keys = {};
    this.last = performance.now();
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(canvas);
    this.resize();
    this.raf = requestAnimationFrame(this.tick);
  }

  destroy() {
    cancelAnimationFrame(this.raf);
    this.ro.disconnect();
    this.stopRecording(true);
    this.destroyed = true;
  }

  // ---------- public API ----------
  setConfig(cfg) {
    const prev = this.cfg;
    // detection.preset 'auto': keep the diagram-tuned detail alive across config
    // refreshes (a fresh resolveOptions would otherwise reset it to photo defaults)
    if (cfg.detail.preset === 'auto' && this.imgType === 'diagram') applyDiagramDetail(cfg.detail, this.img);
    this.cfg = cfg;
    const k = {
      analyze: JSON.stringify(cfg.detail && { ...cfg.detail, maxLines: 0, smooth: 0 }),
      build: JSON.stringify([cfg.source, cfg.palette, cfg.detail, cfg.drafting, cfg.stroke, cfg.timing, cfg.reveal, cfg.playback.seed]),
      image: JSON.stringify([cfg.reveal.imageMode, cfg.palette.bg, cfg.palette.line, cfg.source]),
    };
    if (k.analyze !== this.keys.analyze) this.need.analyze = true;
    if (k.build !== this.keys.build) this.need.build = true;
    if (k.image !== this.keys.image) this.need.image = true;
    this.keys = k;
    if (prev && prev.playback.dpr !== cfg.playback.dpr) this.resize();
    this.dirty = true;
  }

  async setImage(url) {
    if (!url) return;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.decoding = 'async';
    img.src = url;
    try { await img.decode(); } catch (e) { this.onState({ error: new Error(`ko-cover: could not load image "${String(url).slice(0, 120)}"`) }); return; }
    if (this.destroyed) return;
    this.img = img;
    this.imgType = null;
    this.autoTuned = false;
    this.onState({ aspect: img.naturalWidth / img.naturalHeight });
    this.need.analyze = this.need.build = this.need.image = true;
    if (this.cfg?.playback.autoplay === true) this.replay();
    else { this.time = 0; this.completed = false; this.dirty = true; }
  }

  play() { if (this.time >= this.total()) this.time = 0; this.playing = true; this.emit(); }
  pause() { this.playing = false; this.emit(); }
  toggle() { this.playing ? this.pause() : this.play(); }
  replay() { this.time = 0; this.playing = true; this.head = null; this.completed = false; this.dirty = true; this.emit(); }
  /** Jump to a point of the animation, 0..1. */
  seek(u) { this.time = clamp(u) * (this.cfg?.playback.duration ?? 1); this.completed = this.time >= (this.cfg?.playback.duration ?? 1); this.dirty = true; }
  get progress() { return this.cfg ? clamp(this.time / this.cfg.playback.duration) : 0; }
  total() { const p = this.cfg?.playback; return p ? p.duration + p.hold : 1; }
  emit() { this.onState({ playing: this.playing, recording: !!this.rec }); }

  exportPNG() {
    this.canvas.toBlob((b) => download(b, `ko-cover-${Date.now()}.png`), 'image/png');
  }

  record() {
    if (this.rec || !this.canvas.captureStream) return;
    const types = ['video/mp4;codecs=avc1.640033', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm'];
    const mimeType = types.find((t) => window.MediaRecorder?.isTypeSupported?.(t));
    if (!mimeType) { this.onState({ error: 'MediaRecorder not supported in this browser' }); return; }
    const stream = this.canvas.captureStream(60);
    const rec = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 24_000_000 });
    const chunks = [];
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      if (!rec._cancel) download(new Blob(chunks, { type: mimeType }), `ko-cover-${Date.now()}.${mimeType.includes('mp4') ? 'mp4' : 'webm'}`);
      stream.getTracks().forEach((t) => t.stop());
    };
    this.rec = rec;
    this.replay();
    rec.start();
    this.emit();
  }

  stopRecording(cancel = false) {
    if (!this.rec) return;
    this.rec._cancel = cancel;
    this.rec.stop();
    this.rec = null;
    this.emit();
  }

  // ---------- internals ----------
  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, this.cfg?.playback.dpr ?? 2);
    const r = this.canvas.getBoundingClientRect();
    const W = Math.max(2, Math.round(r.width * dpr)), H = Math.max(2, Math.round(r.height * dpr));
    if (W === this.canvas.width && H === this.canvas.height && dpr === this.dpr) return;
    this.dpr = dpr;
    this.canvas.width = W; this.canvas.height = H;
    for (const [k, c] of Object.entries(this.layers)) {
      if (k === 'mask') { c.width = Math.ceil(W * MASK_SCALE); c.height = Math.ceil(H * MASK_SCALE); }
      else { c.width = W; c.height = H; }
    }
    this.need.build = this.need.image = true;
    this.dirty = true;
  }

  prepare() {
    if (!this.img || !this.cfg) return false;
    if (this.need.analyze) {
      const t = performance.now();
      try {
        this.an = analyzeImage(this.img, this.cfg.detail);
      } catch (e) {
        // usually a cross-origin image without CORS headers (canvas pixels are unreadable)
        this.img = null;
        this.onState({ error: new Error(`ko-cover: could not read image pixels (${e.message}). Serve the image from the same origin or with CORS headers.`) });
        return false;
      }
      this.imgType = classifyImage(this.an);
      this.need.analyze = false;
      // preset 'auto': schematics get one re-analysis with diagram-tuned detection
      // (native resolution, short-stroke filter, no smoothing — sharp corners)
      if (this.cfg.detail.preset === 'auto' && !this.autoTuned) {
        this.autoTuned = true;
        if (this.imgType === 'diagram') {
          applyDiagramDetail(this.cfg.detail, this.img);
          this.keys.analyze = JSON.stringify({ ...this.cfg.detail, maxLines: 0, smooth: 0 });
          this.need.analyze = true;
        }
      }
      if (!this.need.analyze) {
        this.need.build = true;
        this.onState({ analyzed: { ms: Math.round(performance.now() - t), chains: this.an.chains.length, arcs: this.an.arcs.length, type: this.imgType } });
      }
    }
    if (this.need.build) {
      const { width: W, height: H } = this.canvas;
      this.scene = buildScene(this.an, W, H, this.dpr, this.cfg);
      this.scene.contourTotal = this.scene.ink.filter((e) => e.contour).length;
      this.need.build = false;
      this.need.image = true;
      this.resetCaches();
      this.buildFade();
      this.dirty = true;
    }
    if (this.need.image) { this.prepareImage(); this.need.image = false; }
    return true;
  }

  /** Alpha mask that softly fades everything (lines, grid) out toward the canvas edges. */
  buildFade() {
    const f = this.layers.fade, c = f.getContext('2d');
    const { width: W, height: H } = f;
    const r = this.scene.imgRect, k = this.cfg.source.edgeFade;
    const wx = Math.max(1, r.x * k), wy = Math.max(1, r.y * k); // fade only inside the bleed margin
    c.globalCompositeOperation = 'source-over';
    c.clearRect(0, 0, W, H);
    c.fillStyle = '#fff';
    c.fillRect(0, 0, W, H);
    c.globalCompositeOperation = 'destination-in';
    const edge = (x0, y0, x1, y1) => {
      const g = c.createLinearGradient(x0, y0, x1, y1);
      g.addColorStop(0, 'rgba(0,0,0,0)');
      g.addColorStop(0.55, 'rgba(0,0,0,0.6)');
      g.addColorStop(1, '#000');
      c.fillStyle = g;
      c.fillRect(0, 0, W, H);
    };
    edge(0, 0, wx, 0); edge(W, 0, W - wx, 0); edge(0, 0, 0, wy); edge(0, H, 0, H - wy);
    c.globalCompositeOperation = 'source-over';
  }

  resetCaches() {
    for (const k of ['grid', 'ink']) {
      const L = this.layers[k];
      L.getContext('2d').clearRect(0, 0, L.width, L.height);
      this.cache[k] = { idx: 0, u: -1, done: 0 };
    }
  }

  prepareImage() {
    const { image } = this.layers, c = image.getContext('2d', { willReadFrequently: true });
    const r = this.scene.imgRect, mode = this.cfg.reveal.imageMode;
    c.clearRect(0, 0, image.width, image.height);
    c.imageSmoothingQuality = 'high';
    c.filter = mode === 'mono' ? 'grayscale(1) contrast(1.1)' : mode === 'inverted' ? 'invert(1) hue-rotate(180deg)' : 'none';
    c.drawImage(this.img, r.x, r.y, r.w, r.h);
    c.filter = 'none';
    if (mode === 'duotone') {
      const x0 = Math.max(0, Math.floor(r.x)), y0 = Math.max(0, Math.floor(r.y));
      const w = Math.min(image.width, Math.ceil(r.x + r.w)) - x0, h = Math.min(image.height, Math.ceil(r.y + r.h)) - y0;
      try {
        const d = c.getImageData(x0, y0, w, h);
        const [br, bg, bb] = toRGB(this.cfg.palette.bg), [lr, lg, lb] = toRGB(this.cfg.palette.line);
        const p = d.data;
        for (let i = 0; i < p.length; i += 4) {
          const l = (0.299 * p[i] + 0.587 * p[i + 1] + 0.114 * p[i + 2]) / 255;
          p[i] = br + (lr - br) * l; p[i + 1] = bg + (lg - bg) * l; p[i + 2] = bb + (lb - bb) * l;
        }
        c.putImageData(d, x0, y0);
      } catch (e) { /* tainted canvas: keep original */ }
    }
  }

  advanceCache(name, list, u) {
    const L = this.layers[name], lc = L.getContext('2d');
    const cache = this.cache[name];
    if (u < cache.u) { lc.clearRect(0, 0, L.width, L.height); cache.idx = 0; cache.done = 0; }
    lc.lineCap = 'round'; lc.lineJoin = 'round';
    while (cache.idx < list.length && list[cache.idx].t1 <= u) {
      const el = list[cache.idx++];
      drawPoly(lc, el, 1, 1);
      if (el.contour) cache.done++;
    }
    lc.globalAlpha = 1;
    cache.u = u;
  }

  /** Draws in-progress elements; returns the tip of the newest contour (plotter head target). */
  drawActive(ctx, list, start, u, alpha, ease) {
    let tip = null, newest = -1;
    for (let i = start; i < list.length; i++) {
      const el = list[i];
      if (el.t0 > u) continue;
      const t = drawPoly(ctx, el, ease(prog(u, el.t0, el.t1)), alpha);
      if (el.contour && el.t0 > newest && t) { newest = el.t0; tip = t; }
    }
    return tip;
  }

  tick = (now) => {
    this.raf = requestAnimationFrame(this.tick);
    const dt = Math.min(0.1, (now - this.last) / 1000);
    this.last = now;
    if (!this.visible && !this.rec) return; // offscreen: freeze and skip work
    if (!this.prepare()) return;
    const P = this.cfg.playback;
    if (this.playing && !P.scrub) {
      this.time += dt * P.speed;
      if (!this.completed && this.time >= P.duration) { this.completed = true; this.onState({ complete: true }); }
      if (this.time >= this.total()) {
        if (this.rec) { this.time = this.total(); this.stopRecording(); this.playing = false; }
        else if (P.loop) { this.time = 0; this.head = null; this.completed = false; }
        else { this.time = this.total(); this.playing = false; this.emit(); }
      }
    }
    const u = P.scrub ? clamp(P.progress) : clamp(this.time / P.duration);
    // idle: nothing animating and nothing changed → don't redraw
    if (!this.playing && !this.dirty && u === this.lastU && !(this.head && this.head.a > 0.01)) return;
    this.lastU = u;
    this.dirty = false;
    this.render(u);
  };

  render(u) {
    const { ctx, scene: sc, cfg } = this;
    const { W, H } = sc;
    const T = cfg.timing, R = cfg.reveal, D = cfg.drafting;
    const ease = EASES[T.ease] || EASES.easeInOut;
    const rv = sc.reveal;
    const fadeStart = rv.rs + (rv.re - rv.rs) * 0.45;
    const inkA = lerp(1, R.keepLines, EASES.smooth(prog(u, fadeStart, rv.re)));
    sc.knockA = 1 - EASES.smooth(prog(u, rv.rs, rv.rs + (rv.re - rv.rs) * 0.3));

    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1;
    ctx.setLineDash([]);
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.clearRect(0, 0, W, H);
    if (cfg.palette.plate) {
      ctx.globalAlpha = inkA; // plate fades with the linework so only the image remains
      ctx.fillStyle = cfg.palette.bg;
      ctx.fillRect(sc.G.x, sc.G.y, sc.G.w, sc.G.h);
      ctx.globalAlpha = 1;
    }

    // grid
    this.advanceCache('grid', sc.grid, u);
    ctx.globalAlpha = inkA;
    if (inkA > 0.001) ctx.drawImage(this.layers.grid, 0, 0);
    this.drawActive(ctx, sc.grid, this.cache.grid.idx, u, inkA, EASES.easeOut);
    for (const n of sc.notes) if (n.kind === 'frame') drawNote(ctx, n, u, sc, cfg, 1);

    // image reveal
    if (u >= rv.rs) {
      ctx.globalAlpha = 1;
      if (u >= rv.re) ctx.drawImage(this.layers.image, 0, 0);
      else ctx.drawImage(this.renderReveal(u), 0, 0);
    }

    // ink (construction, contours, hatch)
    ctx.globalCompositeOperation = R.lineBlend;
    this.advanceCache('ink', sc.ink, u);
    if (inkA > 0.001) {
      ctx.globalAlpha = inkA;
      ctx.drawImage(this.layers.ink, 0, 0);
    }
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    const tip = this.drawActive(ctx, sc.ink, this.cache.ink.idx, u, inkA, ease);

    // annotations
    ctx.globalCompositeOperation = 'source-over';
    if (inkA > 0.001) for (const n of sc.notes) if (n.kind !== 'frame') drawNote(ctx, n, u, sc, cfg, inkA);

    // plotter head
    if (D.plotter) {
      if (tip) {
        if (!this.head || this.head.a < 0.05 || this.cfg.playback.scrub) this.head = { x: tip[0], y: tip[1], a: this.head?.a ?? 0 };
        this.head.x = lerp(this.head.x, tip[0], 0.45);
        this.head.y = lerp(this.head.y, tip[1], 0.45);
        this.head.a = lerp(this.head.a, 1, 0.2);
      } else if (this.head) this.head.a = lerp(this.head.a, 0, 0.12);
      drawHead(ctx, this.head, sc, cfg, inkA);
    }
    if (D.hud) drawHud(ctx, sc, cfg, u, { done: this.cache.ink.done, total: sc.contourTotal }, inkA);
    if (cfg.source.edgeFade > 0) {
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = 'destination-in';
      ctx.drawImage(this.layers.fade, 0, 0);
      ctx.globalCompositeOperation = 'source-over';
    }
    ctx.globalAlpha = 1;
  }

  renderReveal(u) {
    const { mask, reveal, image } = this.layers;
    const sc = this.scene, R = this.cfg.reveal, rv = sc.reveal;
    const m = mask.getContext('2d');
    m.setTransform(1, 0, 0, 1, 0, 0);
    m.clearRect(0, 0, mask.width, mask.height);
    m.setTransform(MASK_SCALE, 0, 0, MASK_SCALE, 0, 0);
    m.lineCap = 'round'; m.lineJoin = 'round';
    m.strokeStyle = '#fff';
    const mainA = 1 - 0.55 * R.bristles;
    for (const st of sc.brush) {
      const p = prog(u, st.t0, st.t1);
      if (p <= 0) continue;
      const f = EASES.easeInOut(p);
      m.globalAlpha = mainA;
      m.lineWidth = st.size;
      m.beginPath(); tracePartial(m, st.pts, st.cum, f); m.stroke();
      for (const b of st.bristles) {
        m.globalAlpha = b.a;
        m.lineWidth = b.w;
        m.save();
        m.translate(st.nx * b.off, st.ny * b.off);
        m.beginPath(); tracePartial(m, st.pts, st.cum, Math.max(0, f - Math.abs(b.off) / (st.cum[st.cum.length - 1] || 1))); m.stroke();
        m.restore();
      }
    }
    const fill = prog(u, rv.fillStart, rv.re);
    if (fill > 0) {
      m.globalAlpha = EASES.smooth(fill);
      m.fillStyle = '#fff';
      m.fillRect(0, 0, sc.W, sc.H);
    }
    const rc = reveal.getContext('2d');
    rc.globalCompositeOperation = 'source-over';
    rc.globalAlpha = 1;
    rc.clearRect(0, 0, reveal.width, reveal.height);
    rc.drawImage(image, 0, 0);
    rc.globalCompositeOperation = 'destination-in';
    rc.imageSmoothingEnabled = true;
    rc.filter = R.softness > 0 ? `blur(${R.softness * sc.dpr}px)` : 'none';
    rc.drawImage(mask, 0, 0, sc.W, sc.H);
    rc.filter = 'none';
    rc.globalCompositeOperation = 'source-over';
    return reveal;
  }
}

function tracePartial(ctx, pts, cum, frac) {
  const n = cum.length, total = cum[n - 1] * frac;
  ctx.moveTo(pts[0], pts[1]);
  for (let i = 1; i < n; i++) {
    if (cum[i] <= total) ctx.lineTo(pts[i * 2], pts[i * 2 + 1]);
    else {
      const k = (total - cum[i - 1]) / (cum[i] - cum[i - 1] || 1);
      ctx.lineTo(lerp(pts[i * 2 - 2], pts[i * 2], k), lerp(pts[i * 2 - 1], pts[i * 2 + 1], k));
      break;
    }
  }
}

function download(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

// 진입점: createCoverReveal(container | canvas, options) → controller.

/**
 * 표지용 제도 리빌을 마운트한다.
 * @param {HTMLElement|HTMLCanvasElement} target a container (a canvas is created inside, sized to the image) or a canvas you size yourself
 * @param {object} options
 */
function createCoverReveal(target, options = {}) {
  if (typeof window === 'undefined') throw new Error('ko-cover: createCoverReveal() must run in the browser');
  if (!target) throw new Error('ko-cover: missing target element');

  const owned = !(target instanceof HTMLCanvasElement);
  const canvas = owned ? document.createElement('canvas') : target;
  if (owned) {
    canvas.style.display = 'block';
    canvas.style.width = '100%';
    canvas.style.height = 'auto';
    target.appendChild(canvas);
  }

  let opts = { ...options };
  let src = null;
  let played = false;
  const reduced = () => opts.playback?.reducedMotion !== 'play' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  const applyA11y = () => {
    canvas.setAttribute('role', 'img');
    if (opts.alt != null) canvas.setAttribute('aria-label', opts.alt);
  };

  const engine = new RevealEngine(canvas, {
    onState: (s) => {
      if (s.aspect) {
        if (owned || opts.autoSize) canvas.style.aspectRatio = String(s.aspect);
        opts.onAspect?.(s.aspect);
      }
      if (s.analyzed) {
        opts.onReady?.(s.analyzed);
        if (reduced()) { engine.seek(1); engine.pause(); }
      }
      if (s.complete) opts.onComplete?.();
      if (s.error) {
        const err = s.error instanceof Error ? s.error : new Error(String(s.error));
        if (opts.onError) opts.onError(err);
        else console.error(err);
      }
    },
  });

  // play-in-view + skip rendering while offscreen
  const io = 'IntersectionObserver' in window
    ? new IntersectionObserver(([e]) => {
        engine.visible = e.isIntersecting;
        if (e.isIntersecting) {
          engine.dirty = true;
          if (opts.playback?.autoplay === 'inView' && !played && !reduced()) { played = true; engine.replay(); }
        }
      }, { threshold: opts.inViewThreshold ?? 0.3 })
    : null;
  io?.observe(canvas);

  const sync = () => {
    applyA11y();
    engine.setConfig(resolveOptions(opts));
    if (opts.src && opts.src !== src) {
      src = opts.src;
      played = false;
      engine.setImage(src);
    }
  };
  sync();

  return {
    canvas,
    engine,
    /** Replace all options (missing keys fall back to defaults). */
    setOptions(next) { opts = { ...next }; sync(); },
    /** Deep-merge a partial update into the current options. */
    update(partial) { opts = deepMerge(opts, partial); sync(); },
    setSource(url) { opts = { ...opts, src: url }; sync(); },
    play: () => engine.play(),
    pause: () => engine.pause(),
    toggle: () => engine.toggle(),
    replay: () => { played = true; engine.replay(); },
    seek: (progress) => engine.seek(progress),
    get progress() { return engine.progress; },
    get playing() { return engine.playing; },
    record: () => engine.record(),
    stopRecording: () => engine.stopRecording(),
    exportPNG: () => engine.exportPNG(),
    destroy() {
      io?.disconnect();
      engine.destroy();
      if (owned) canvas.remove();
    },
  };
}
window.createCoverReveal = createCoverReveal;
})();

}
(function () {
  'use strict';
  var DEFAULTS = {"preset": "auto", "keepLines": 0};
  // 단축 키 → 엔진이 기대하는 중첩 객체. createCoverReveal은 raw opts를 얕은 복사로만 쓰고
  // IO 콜백은 중첩 키(opts.playback.autoplay)를 읽으므로 dotted 키는 트리거에 도달하지 못한다.
  function toMapped(raw) {
    var opts = Object.assign({}, DEFAULTS, raw);
    var mapped = {};
    if (opts.preset !== undefined) { // 가정 A1: preset 'auto'면 'ink'+detection auto
      mapped.colors = { preset: opts.preset === 'auto' ? 'ink' : opts.preset };
      mapped.detection = { preset: 'auto' };
    }
    if (opts.keepLines !== undefined) {
      mapped.reveal = { keepLines: opts.keepLines };
    }
    return mapped;
  }
  function init(figure) {
    if (figure.dataset.koCoverInit) return; // 이미 초기화된 figure — 재초기화 금지
    var img = figure.querySelector('.ko-cover-img');
    var canvas = figure.querySelector('.ko-cover-canvas'); // 조각의 기존 캔버스를 채택(no-JS 폴백 유지)
    // 플래그는 호출 성공 후에 부여한다 — 엔진 부재·조각 불완전 시 다음 boot에서 재시도
    if (!img || !canvas || !window.createCoverReveal) return;
    var raw = {};
    try {
      raw = JSON.parse(figure.getAttribute('data-cover') || '{}');
    } catch (e) {
      raw = {};
    }
    var opts = toMapped(raw);
    opts.src = img.src;
    opts.alt = img.alt;
    opts.playback = { autoplay: 'inView' }; // 표지 장 노출 시 재생(deckslide 이벤트 불요)
    // 결함 4 — 재생 개시에만 폴백 이미지를 숨기고(live), 엔진 실패 시 되돌려 no-JS 폴백으로 복귀
    opts.onError = function () {
      figure.classList.remove('ko-cover-live');
      canvas.setAttribute('aria-hidden', 'true'); // 폴백 복귀 — 접근성 상태도 원래대로(항목 8)
    };
    window.createCoverReveal(canvas, opts); // 캔버스 자체를 넘겨 owned=false — 새 캔버스 추가 없음
    figure.dataset.koCoverInit = '1'; // 호출 성공 후 부여 — 수동 통합 재실행 시 영구 스킵 함정 제거
    figure.classList.add('ko-cover-live');
    canvas.removeAttribute('aria-hidden'); // 라이브 표지를 스크린리더에 노출(항목 8)
  }
  function boot() {
    document.querySelectorAll('.ko-cover').forEach(init);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();

