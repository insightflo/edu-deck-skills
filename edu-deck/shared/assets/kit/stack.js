/* 구성도·업무 흐름 부품 — 슬라이드에서 data-c="stack" 으로 켠다.
   <div class="stack-fig" data-c="stack" data-d='{"nodes":[…],"edges":[…],"groups":[…]}' role="img" aria-label="…"></div>
   노드는 행·열 격자에 놓고, 좌표·그룹 상자·화살표 경로는 이 파일이 규칙으로 계산한다(사람이 좌표를 짜지 않는다).
   배치 규칙은 caru-ini/stack-diagram(MIT)의 geometry 규칙을 따라 한글 폭·슬라이드 크기에 맞게 옮겼다:
     · 노드 = 타일 + 그 아래 글자(박스). 세로 화살표는 위 노드의 박스 아래쪽 → 아래 노드의 타일 위쪽을 잇는다(글자를 가로지르지 않는다).
     · 같은 줄의 먼 노드 사이는 노드가 없는 위쪽 통로, 줄·열이 다르면 열 사이 틈과 줄 사이 띠로만 꺾는다(노드 박스를 지나지 않는다).
   아이콘은 Lucide 선 아이콘(ISC)만 쓴다(빌드가 <script id="ppt-stack-icons"> 로 넣는 사본). 로고(브랜드 마크)는 쓰지 않는다.
   색은 슬라이드 토큰(--ink·--accent 등)을 따르고 어두운 장(.slide.dark)도 따른다.
   데이터 형식은 references/stack.md, 검사는 scripts/stack_schema.py.

   edu-deck 마운트(아래 "마운트" 절): 모든 data-c="stack" 요소는 로드 시 즉시 그린다(인쇄·자습·reduced 완성 모습).
   화면 발표에서 장에 들어올 때만 is-play 를 켜 그룹→노드→화살표 순 등장을 태우고, 한 번 본 요소는 다시 재생하지 않는다.
   발화 감사는 eduMotion.sigLog 에 'stack-reveal' 로 기록한다. */
(function () {
  'use strict';
  const ICONS = (() => {
    try {
      const tag = document.getElementById('ppt-stack-icons');
      const o = tag ? JSON.parse(tag.textContent) : (window.PPTStackIcons || {});
      return o.icons || {};
    } catch (e) { return {}; }
  })();

  // 격자 상수(논리 단위). scripts/stack_schema.py 의 같은 이름 상수와 맞춰 둔다.
  const T = 64, BW = 176, BH = 110, PX = 204, PY = 166, OX = 40, OY = 44, GPX = 12, GPT = 40, GPB = 8, NEST = 12;
  const NS = 'http://www.w3.org/2000/svg';
  let SEQ = 0;
  const mk = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };
  const mcv = document.createElement('canvas').getContext('2d');
  function fit(s, max, size, w, family) {      // 칸 폭을 넘으면 …으로 줄인다
    s = String(s); mcv.font = `${w} ${size}px ${family}`;
    if (mcv.measureText(s).width <= max) return s;
    while (s.length > 1 && mcv.measureText(s + '…').width > max) s = s.slice(0, -1);
    return s + '…';
  }

  /* ───────── 배치 ───────── */
  function geometry(o) {
    const N = {}, G = {};
    o.nodes.forEach((n, i) => { N[n.id] = Object.assign({}, n, { i, cx: OX + n.col * PX + BW / 2, top: OY + n.row * PY }); });
    (o.groups || []).forEach((g, i) => { G[g.id] = Object.assign({}, g, { i, kids: [] }); });
    Object.values(G).forEach((g) => { if (g.parent && G[g.parent]) G[g.parent].kids.push(g.id); });
    const cache = {};
    const rect = (g) => {
      if (cache[g.id]) return cache[g.id];
      let c0 = Infinity, c1 = -Infinity, r0 = Infinity, r1 = -Infinity;
      for (const id of g.nodes || []) { const n = N[id]; if (!n) continue; c0 = Math.min(c0, n.col); c1 = Math.max(c1, n.col); r0 = Math.min(r0, n.row); r1 = Math.max(r1, n.row); }
      if (g.cols) { c0 = g.cols[0]; c1 = g.cols[1]; }
      const has = c0 !== Infinity;
      let x0 = has ? OX + c0 * PX - GPX : Infinity, x1 = has ? OX + c1 * PX + BW + GPX : -Infinity;
      let y0 = has ? OY + r0 * PY - GPT : Infinity, y1 = has ? OY + r1 * PY + BH + GPB : -Infinity;
      for (const kid of g.kids) { const k = rect(G[kid]); x0 = Math.min(x0, k.x0 - NEST); x1 = Math.max(x1, k.x1 + NEST); y0 = Math.min(y0, k.y0 - 30); y1 = Math.max(y1, k.y1 + NEST); }
      return (cache[g.id] = { x0, y0, x1, y1 });
    };
    Object.values(G).forEach((g) => { g.r = rect(g); });
    let W = 0, H = 0;
    Object.values(N).forEach((n) => { W = Math.max(W, n.cx + BW / 2 + OX); H = Math.max(H, n.top + BH + 24); });
    Object.values(G).forEach((g) => { W = Math.max(W, g.r.x1 + 16); H = Math.max(H, g.r.y1 + 12); });
    return { N, G, W, H };
  }

  /* ───────── 화살표 경로 ───────── */
  function route(a, b, at, shift) {   // shift: 서로 반대로 가는 한 쌍이면 ±9 로 나란히 벌린다(같은 선에 겹치지 않게)
    const dr = b.row - a.row, dc = b.col - a.col, s = dc > 0 ? 1 : -1, M = T / 2 + 5;
    const ym = (n) => n.top + T / 2;
    let pts, lab;
    if (dr === 0) {
      const lo = Math.min(a.col, b.col), hi = Math.max(a.col, b.col);
      let blocked = false;
      for (let c = lo + 1; c < hi; c++) if (at(a.row, c)) blocked = true;
      if (!blocked) { const y = ym(a) + shift; pts = [[a.cx + s * M, y], [b.cx - s * M, y]]; lab = { x: (a.cx + b.cx) / 2, y: shift > 0 ? y + 21 : y - 10, a: 'middle' }; }
      else { const y = a.top - 20; pts = [[a.cx, a.top - 5], [a.cx, y], [b.cx, y], [b.cx, b.top - 5]]; lab = { x: (a.cx + b.cx) / 2, y: y - 7, a: 'middle' }; }
    } else if (dc === 0) {
      const lo = Math.min(a.row, b.row), hi = Math.max(a.row, b.row);
      let blocked = false;
      for (let r = lo + 1; r < hi; r++) if (at(r, a.col)) blocked = true;
      if (!blocked) {
        const x = a.cx + shift;
        pts = dr > 0 ? [[x, a.top + BH + 4], [x, b.top - 5]] : [[x, a.top - 4], [x, b.top + BH + 5]];
        lab = { x: shift < 0 ? x - 11 : x + 11, y: dr > 0 ? a.top + BH + (PY - BH) / 2 : a.top - (PY - BH) / 2, a: shift < 0 ? 'end' : 'start' };
      } else {
        const gx = a.cx + PX / 2;
        pts = [[a.cx + M, ym(a)], [gx, ym(a)], [gx, ym(b)], [b.cx + M, ym(b)]];
        lab = { x: gx + 9, y: (ym(a) + ym(b)) / 2, a: 'start' };
      }
    } else if (Math.abs(dc) === 1) {
      const gx = a.cx + s * PX / 2;
      pts = [[a.cx + s * M, ym(a)], [gx, ym(a)], [gx, ym(b)], [b.cx - s * M, ym(b)]];
      lab = { x: gx, y: dr > 0 ? a.top + BH + (PY - BH) / 2 : a.top - (PY - BH) / 2, a: 'middle' };
    } else {
      const xs = a.cx + s * PX / 2, xt = b.cx - s * PX / 2, yb = dr > 0 ? b.top - 34 : b.top + BH + 12;
      pts = [[a.cx + s * M, ym(a)], [xs, ym(a)], [xs, yb], [xt, yb], [xt, ym(b)], [b.cx - s * M, ym(b)]];
      lab = { x: (xs + xt) / 2, y: yb - 7, a: 'middle' };
    }
    return { pts, lab };
  }
  function pathOf(pts, r) {                     // 꺾이는 곳을 둥글게
    let d = `M${pts[0][0]} ${pts[0][1]}`;
    for (let i = 1; i < pts.length; i++) {
      const p = pts[i], q = pts[i - 1], n = pts[i + 1];
      if (!n) { d += ` L${p[0]} ${p[1]}`; break; }
      const l1 = Math.hypot(p[0] - q[0], p[1] - q[1]), l2 = Math.hypot(n[0] - p[0], n[1] - p[1]), k = Math.min(r, l1 / 2, l2 / 2);
      const a = [p[0] - ((p[0] - q[0]) / l1) * k, p[1] - ((p[1] - q[1]) / l1) * k], b = [p[0] + ((n[0] - p[0]) / l2) * k, p[1] + ((n[1] - p[1]) / l2) * k];
      d += ` L${a[0]} ${a[1]} Q${p[0]} ${p[1]} ${b[0]} ${b[1]}`;
    }
    return d;
  }

  /* ───────── 그리기 ───────── */
  function draw(host, o) {
    const family = getComputedStyle(host).getPropertyValue('--pack-sans').trim() || getComputedStyle(host).fontFamily || 'Pretendard,system-ui,sans-serif';
    const { N, G, W, H } = geometry(o);
    const at = (r, c) => o.nodes.find((n) => n.row === r && n.col === c);
    const uid = 'sf' + (++SEQ);
    host.textContent = '';
    const svg = mk('svg', { viewBox: `0 0 ${W} ${H}`, 'aria-hidden': 'true', preserveAspectRatio: 'xMidYMid meet' });
    const defs = mk('defs', {}, svg);
    [['m', 'sf-ar-main'], ['s', 'sf-ar-sub']].forEach(([k, cls]) => {
      const m = mk('marker', { id: `${uid}-${k}`, viewBox: '0 0 12 12', refX: 11, refY: 6, markerWidth: 12, markerHeight: 12, markerUnits: 'userSpaceOnUse', orient: 'auto' }, defs);
      mk('path', { d: 'M1 1 L11 6 L1 11 L4 6 Z', class: cls }, m);
    });
    const lg = mk('g', { class: 'sf-groups' }, svg), le = mk('g', { class: 'sf-edges' }, svg), ln = mk('g', { class: 'sf-nodes' }, svg), ll = mk('g', { class: 'sf-labels' }, svg);

    // 그룹: 큰 것부터(바깥 → 안쪽)
    Object.values(G).sort((p, q) => (q.r.x1 - q.r.x0) * (q.r.y1 - q.r.y0) - (p.r.x1 - p.r.x0) * (p.r.y1 - p.r.y0)).forEach((g) => {
      const r = g.r, gg = mk('g', { class: `sf-group sf-g-${g.tone || 'plain'}`, style: `--d:${g.i * 60}ms` }, lg);
      mk('rect', { x: r.x0, y: r.y0, width: r.x1 - r.x0, height: r.y1 - r.y0, rx: 16 }, gg);
      // 라벨은 화살표 위 레이어에 둔다: 선이 라벨을 지나가면 라벨 글자 둘레의 그룹색 테두리(halo)가 선을 가린다
      const gl = mk('g', { class: `sf-glw sf-lg-${g.tone || 'plain'}`, style: `--d:${g.i * 60}ms` }, ll);
      let lx = r.x0 + 16;
      if (g.icon && ICONS[g.icon]) { const ic = mk('g', { transform: `translate(${lx} ${r.y0 + 10}) scale(.85)`, class: 'sf-gico', 'stroke-width': 2.2 }, gl); ic.innerHTML = ICONS[g.icon]; lx += 27; }
      const t = mk('text', { x: lx, y: r.y0 + 25, class: 'sf-glabel' }, gl);
      t.textContent = fit(g.label, r.x1 - lx - 14, 16, 700, family);
    });

    // 화살표
    const base = 150 + o.nodes.length * 80;
    (o.edges || []).forEach((e, j) => {
      const a = N[e.from], b = N[e.to], kind = e.kind || 'main';
      const rev = o.edges.some((x) => x.from === e.to && x.to === e.from), fwd = a.row < b.row || (a.row === b.row && a.col < b.col);
      const { pts, lab } = route(a, b, at, rev ? (fwd ? -9 : 9) : 0);
      const ge = mk('g', { class: `sf-edge sf-e-${kind}`, style: `--d:${base + j * 110}ms` }, le);
      mk('path', { d: pathOf(pts, 12), pathLength: 1, 'marker-end': `url(#${uid}-${kind === 'main' ? 'm' : 's'})` }, ge);
      if (e.label) {
        const t = mk('text', { x: lab.x, y: lab.y, 'text-anchor': lab.a, class: 'sf-el' }, ll);
        t.setAttribute('style', `--d:${base + j * 110 + 300}ms`);
        t.textContent = fit(e.label, 104, 14, 600, family);
      }
    });

    // 노드
    o.nodes.forEach((n0) => {
      const n = N[n0.id], tone = n.tone || 'plain', g = mk('g', { class: `sf-node sf-t-${tone}`, style: `--d:${150 + n.i * 80}ms` }, ln);
      mk('rect', { x: n.cx - T / 2, y: n.top, width: T, height: T, rx: 15, class: 'sf-tile' }, g);
      if (ICONS[n.icon]) { const ic = mk('g', { transform: `translate(${n.cx - 16} ${n.top + 16}) scale(1.333)`, class: 'sf-ico', 'stroke-width': 1.6 }, g); ic.innerHTML = ICONS[n.icon]; }
      const nm = mk('text', { x: n.cx, y: n.top + T + 20, 'text-anchor': 'middle', class: 'sf-name' }, g);
      nm.textContent = fit(n.name, BW - 6, 19, 700, family);
      if (n.role) { const rl = mk('text', { x: n.cx, y: n.top + T + 42, 'text-anchor': 'middle', class: 'sf-role' }, g); rl.textContent = fit(n.role, BW - 6, 14, 500, family); }
      if (n.badge) {
        mk('circle', { cx: n.cx - T / 2 + 2, cy: n.top + 2, r: 12, class: 'sf-badge' }, g);
        const bt = mk('text', { x: n.cx - T / 2 + 2, y: n.top + 2.5, 'text-anchor': 'middle', class: 'sf-badge-t' }, g);
        bt.textContent = String(n.badge);
      }
    });
    host.appendChild(svg);
  }

  window.PPTStack = { draw, geometry, route, consts: { T, BW, BH, PX, PY, OX, OY, GPX, GPT, GPB, NEST } };

  /* ───────── 마운트: edu-deck ─────────
     모든 요소는 로드 시 즉시 그린다 — 인쇄·자습·reduced·미지원 환경의 완성 모습.
     화면 발표에서는 활성 장에 들어올 때 한 번만 is-play 를 켠다(그룹→노드→화살표 순, CSS).
     무성 장 감사와 맞추기 위해 발화는 'stack-reveal' 로 sigLog 에 남긴다. */
  const REDUCE = matchMedia('(prefers-reduced-motion: reduce)');
  const PRINT = matchMedia('print');
  const seen = new WeakSet();      // 발표에서 한 번 본 요소 — 재방문해도 다시 재생하지 않는다
  let printing = false;
  const staticMode = () => printing || PRINT.matches || REDUCE.matches ||
    document.body.classList.contains('st-self') ||
    document.body.classList.contains('st-printing') ||
    document.body.classList.contains('st-presenter');
  const currentSlide = () => document.querySelector('.deck.on>.slide.active, #stage>.slide.active');
  const DATA = new WeakMap();      // 리사이즈 재그리기용 — 파싱한 데이터를 요소에 묶어 둔다
  function mount(el) {
    let o;
    try { o = JSON.parse(el.dataset.d || '{}'); } catch (e) { return; }
    if (!Array.isArray(o.nodes) || !o.nodes.length) return;
    try { draw(el, o); } catch (e) { return; }   // 데이터가 어긋나면 비워 둔다. 빌드 검사가 먼저 알린다
    DATA.set(el, o);
    el.classList.add('is-ready');
  }
  function sig(s, step) {
    const log = window.eduMotion && window.eduMotion.sigLog;
    if (!log) return;
    let slide = -1;
    if (window.deckInfo) { const info = window.deckInfo(); if (info && typeof info.slide === 'number') slide = info.slide; }
    if (slide < 0) slide = [...document.querySelectorAll('.slide')].indexOf(s);
    log.push(Object.freeze({ slide, step, sig: 'stack-reveal' }));
    if (log.length > 500) log.shift();
    document.dispatchEvent(new CustomEvent('edumotion', { detail: { slide, step, sig: 'stack-reveal' } }));
  }
  function enter(el) {
    if (staticMode() || seen.has(el)) { el.classList.remove('is-play'); el.classList.add('is-done'); return; }
    seen.add(el);
    el.classList.remove('is-play', 'is-done'); void el.offsetWidth;
    el.classList.add('is-play');
    const s = el.closest('.slide'), info = window.deckInfo ? window.deckInfo() : {};
    if (s) sig(s, info.step || 0);
    const o = DATA.get(el) || {};
    const last = 150 + (o.nodes || []).length * 80 + ((o.edges || []).length) * 110 + 700;
    setTimeout(() => { el.classList.remove('is-play'); el.classList.add('is-done'); }, last);
  }
  function onSlide() {
    const s = currentSlide();
    if (s) s.querySelectorAll('[data-c="stack"]').forEach(enter);
  }
  function settle() {
    document.querySelectorAll('[data-c="stack"].is-play').forEach((el) => {
      el.classList.remove('is-play'); el.classList.add('is-done');
    });
  }
  document.addEventListener('deckslide', onSlide);
  window.addEventListener('beforeprint', () => { printing = true; settle(); });
  window.addEventListener('afterprint', () => { printing = false; });
  REDUCE.addEventListener('change', settle);
  PRINT.addEventListener('change', settle);
  document.addEventListener('edmode', settle);
  new MutationObserver(() => { if (staticMode()) settle(); }).observe(document.body, { attributes: true, attributeFilter: ['class'] });
  document.querySelectorAll('[data-c="stack"]').forEach(mount);
  /* 리사이즈: 폰트·폭이 바뀌면 fit() 결과가 달라지므로 다시 그린다. is-done 요소는 그대로 완성 모습. */
  let rzT = 0;
  window.addEventListener('resize', () => {
    clearTimeout(rzT);
    rzT = setTimeout(() => document.querySelectorAll('[data-c="stack"].is-ready').forEach((el) => {
      const o = DATA.get(el); if (o) try { draw(el, o); } catch (e) {}
    }), 150);
  });
  onSlide();   /* 첫 장(주소 #N 포함)은 deckslide 가 이미 지났다 */
})();
