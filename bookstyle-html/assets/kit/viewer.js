/* bookstyle-html · book viewer runtime
 * Source of truth: statically rendered <section class="page"> elements inside #pages.
 * Modes: viewer (default) · ?check=1 · ?sheet[=cols] · ?shot=N (native 600×820 page)
 * The book frame fills the viewport (no chrome gutter, no 0.96 shrink).
 * A single visible page (cover, back, or narrow/portrait mode) scales to the full viewport;
 * a two-page spread scales to fill the shorter viewport side.
 */
(function () {
  'use strict';
  var root = document.documentElement;
  root.classList.remove('no-js');
  root.classList.add('js');

  var params = new URLSearchParams(location.search);
  var src = Array.prototype.slice.call(document.querySelectorAll('#pages > .page'));
  var N = src.length;
  if (!N) return;

  if (params.has('check')) { root.classList.add('mode-check'); ready().then(runCheck); return; }
  if (params.has('sheet')) { root.classList.add('mode-sheet'); buildSheet(parseInt(params.get('sheet'), 10) || 6); return; }
  if (params.has('shot')) { root.classList.add('mode-shot'); showShot(parseInt(params.get('shot'), 10) || 1); return; }

  /* ───────── viewer ───────── */
  var book = document.getElementById('book');
  var scaler = document.getElementById('scaler');
  var stage = document.getElementById('stage');
  var label = document.querySelector('[data-role=pg]');
  var range = document.querySelector('[data-role=range]');
  var lightbox = document.getElementById('lightbox');
  var css = getComputedStyle(root);
  var PW = parseFloat(css.getPropertyValue('--pw')) || 600;
  var PH = parseFloat(css.getPropertyValue('--ph')) || 820;
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var mode = null, cur = 0, items = [], busy = false, queued = null;
  // spread mode: cur = number of turned leaves · single mode: cur = page index

  var tocIndex = src.findIndex(function (p) { return p.dataset.type === 'toc'; });
  var tocBtn = document.querySelector('[data-act=toc]');
  if (tocBtn && tocIndex < 0) tocBtn.hidden = true;
  if (range) { range.max = N; range.min = 1; }

  function isSingle() { return innerWidth < 900 || innerWidth / innerHeight < 1.05; }
  function clone(i) { return i < N ? src[i].cloneNode(true) : blank(); }
  function blank() { var s = document.createElement('section'); s.className = 'page'; return s; }

  function buildSpread() {
    book.className = '';
    book.innerHTML = '<div class="book-shadow"></div><div class="spine"></div>';
    items = [];
    var L = Math.ceil(N / 2);
    for (var k = 0; k < L; k++) {
      var leaf = document.createElement('div'); leaf.className = 'leaf';
      var f = document.createElement('div'); f.className = 'face front'; f.appendChild(clone(2 * k));
      var b = document.createElement('div'); b.className = 'face back'; b.appendChild(clone(2 * k + 1));
      leaf.appendChild(f); leaf.appendChild(b); book.appendChild(leaf); items.push(leaf);
    }
    layoutSpread();
  }
  function zFix() {
    var L = items.length;
    items.forEach(function (lf, k) { lf.style.zIndex = k < cur ? k + 1 : (L - k) + 1; });
  }
  function layoutSpread() {
    items.forEach(function (lf, k) { lf.classList.toggle('flipped', k < cur); });
    zFix(); shift();
  }
  function shift() {
    var L = items.length, x = 0;
    if (cur === 0) x = -PW / 2; else if (cur === L) x = PW / 2;
    book.style.transform = 'translateX(' + x + 'px)';
    var sh = book.querySelector('.book-shadow');
    if (sh) { sh.style.left = cur === 0 ? PW + 'px' : '-2px'; sh.style.right = cur === L ? PW + 'px' : '-2px'; }
  }
  function flip(dir) {
    return new Promise(function (res) {
      var L = items.length;
      if ((dir > 0 && cur >= L) || (dir < 0 && cur <= 0)) return res(false);
      var k = dir > 0 ? cur : cur - 1, lf = items[k], finished = false;
      lf.classList.add('turning'); lf.style.zIndex = 1000;
      cur += dir; lf.classList.toggle('flipped', dir > 0); shift(); update(); scaleBook();
      function done() {
        if (finished) return; finished = true;
        lf.removeEventListener('transitionend', onEnd);
        lf.classList.remove('turning'); zFix(); res(true);
      }
      function onEnd(e) { if (e.target === lf && e.propertyName === 'transform') done(); }
      lf.addEventListener('transitionend', onEnd);
      setTimeout(done, reduce ? 0 : 1100);
    });
  }

  function buildSingle() {
    book.className = 'single'; book.style.transform = ''; book.innerHTML = '';
    items = src.map(function (p, i) {
      var w = document.createElement('div'); w.className = 'sheet'; w.hidden = i !== cur;
      w.appendChild(clone(i)); w.style.zIndex = N - i; book.appendChild(w); return w;
    });
  }
  function flipSingle(dir) {
    return new Promise(function (res) {
      var nx = cur + dir; if (nx < 0 || nx >= N) return res(false);
      var a = items[cur], b = items[nx], t = reduce ? 0 : 700;
      if (dir > 0) {
        b.hidden = false; b.classList.remove('out'); a.classList.add('out');
        setTimeout(function () { a.hidden = true; a.classList.remove('out'); res(true); }, t);
      } else {
        b.hidden = false; b.classList.add('out'); b.style.zIndex = N + 1; void b.offsetWidth; b.classList.remove('out');
        setTimeout(function () { a.hidden = true; b.style.zIndex = N - nx; res(true); }, t);
      }
      cur = nx; update();
    });
  }

  function visible() {
    if (mode === 'single') return [cur + 1];
    var L = items.length;
    if (cur === 0) return [1];
    if (cur === L) return [Math.min(2 * L, N)];
    return [2 * cur, Math.min(2 * cur + 1, N)];
  }
  function update() {
    var v = visible();
    if (label) label.textContent = (v.length > 1 && v[1] !== v[0] ? v[0] + '–' + v[1] : v[0]) + ' / ' + N;
    if (range) range.value = v[0];
    if (history.replaceState) history.replaceState(null, '', '#p' + v[0]);
  }
  function place(p) {
    book.classList.add('noanim');
    scaler.classList.add('noanim');
    if (mode === 'single') { items[cur].hidden = true; cur = clamp(p - 1, 0, N - 1); items[cur].hidden = false; items[cur].classList.remove('out'); }
    else { cur = clamp(Math.floor(p / 2), 0, items.length); layoutSpread(); }
    update(); scaleBook();
    void book.offsetWidth;
    requestAnimationFrame(function () { book.classList.remove('noanim'); scaler.classList.remove('noanim'); });
  }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  function go(dir) {
    if (busy) return;
    busy = true;
    (mode === 'single' ? flipSingle(dir) : flip(dir)).then(release);
  }
  function goTo(p) {
    p = clamp(p | 0, 1, N);
    if (busy) { queued = p; return; }
    var target = mode === 'single' ? p - 1 : Math.floor(p / 2);
    var dist = Math.abs(target - cur);
    if (!dist) return;
    if (dist === 1) { go(target > cur ? 1 : -1); return; }
    busy = true;
    book.classList.add('jump');
    setTimeout(function () { place(p); book.classList.remove('jump'); release(); }, reduce ? 0 : 180);
  }
  function release() {
    busy = false;
    if (queued != null) { var q = queued; queued = null; goTo(q); }
  }

  function visibleBookWidth() {
    if (mode === 'single') return PW;
    var L = items.length;
    if (cur === 0 || cur === L) return PW;
    return PW * 2;
  }
  function viewport() {
    var vv = window.visualViewport;
    if (vv && vv.width && vv.height) return { w: vv.width, h: vv.height };
    return { w: innerWidth, h: innerHeight };
  }
  function scaleBook() {
    var W = visibleBookWidth();
    var s = Math.min(stage.clientWidth / W, stage.clientHeight / PH);
    scaler.style.zoom = '';
    scaler.style.transform = 'scale(' + s + ')';
  }
  function fit() {
    var want = isSingle() ? 'single' : 'spread';
    if (want !== mode) {
      var vp = mode ? visible()[0] : pageFromHash();
      mode = want;
      if (mode === 'single') { cur = clamp(vp - 1, 0, N - 1); buildSingle(); }
      else { cur = clamp(Math.floor(vp / 2), 0, Math.ceil(N / 2)); buildSpread(); }
      book.classList.add('noanim'); scaler.classList.add('noanim'); update();
      requestAnimationFrame(function () { book.classList.remove('noanim'); scaler.classList.remove('noanim'); });
    }
    scaleBook();
  }
  function pageFromHash() { var m = /^#p(\d+)$/.exec(location.hash); return m ? clamp(+m[1], 1, N) : 1; }

  /* chrome auto-hide so the book can occupy the full screen */
  var chromeTimer = null;
  function showChrome() {
    root.classList.remove('chrome-idle');
    clearTimeout(chromeTimer);
    chromeTimer = setTimeout(function () { root.classList.add('chrome-idle'); }, 2400);
  }
  addEventListener('mousemove', showChrome);
  addEventListener('touchstart', showChrome, { passive: true });
  addEventListener('keydown', showChrome);

  /* controls */
  document.querySelectorAll('[data-act]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var act = btn.dataset.act;
      if (act === 'prev') go(-1);
      else if (act === 'next') go(1);
      else if (act === 'first') goTo(1);
      else if (act === 'toc') goTo(tocIndex + 1);
      else if (act === 'print') window.print();
      else if (act === 'fs') {
        if (document.fullscreenElement) document.exitFullscreen();
        else if (root.requestFullscreen) root.requestFullscreen();
      }
    });
  });
  if (range) range.addEventListener('input', function () { goTo(+range.value); });

  addEventListener('keydown', function (e) {
    if (lightbox.classList.contains('on')) {
      if (e.key === 'Escape' || e.key === ' ' || e.key === 'Enter') { closeLightbox(); e.preventDefault(); }
      return;
    }
    if (e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { e.preventDefault(); go(1); }
    else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); go(-1); }
    else if (e.key === 'Home') { e.preventDefault(); goTo(1); }
    else if (e.key === 'End') { e.preventDefault(); goTo(N); }
  });

  book.addEventListener('click', function (e) {
    var z = e.target.closest('[data-zoom]');
    if (z) {
      var im = z.querySelector('img');
      if (im) { lightbox.querySelector('img').src = im.currentSrc || im.src; lightbox.querySelector('p').textContent = im.alt || ''; lightbox.classList.add('on'); }
      return;
    }
    var g = e.target.closest('[data-goto]');
    if (g) { goTo(+g.dataset.goto); return; }
    var c = e.target.closest('.chk');
    if (c) {
      c.classList.toggle('on');
      c.setAttribute('aria-checked', c.classList.contains('on'));
      var pg = c.closest('.page'), sc = pg && pg.querySelector('[data-role=score]');
      if (sc) sc.textContent = pg.querySelectorAll('.chk.on').length;
      return;
    }
    if (e.target.closest('a')) return;
    var r = book.getBoundingClientRect(), x = (e.clientX - r.left) / r.width;
    if (mode === 'single') go(x > 0.35 ? 1 : -1); else go(x > 0.5 ? 1 : -1);
  });
  var tx = null;
  book.addEventListener('touchstart', function (e) { tx = e.touches[0].clientX; }, { passive: true });
  book.addEventListener('touchend', function (e) {
    if (tx == null) return;
    var dx = e.changedTouches[0].clientX - tx;
    if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1);
    tx = null;
  });
  function closeLightbox() { lightbox.classList.remove('on'); }
  lightbox.addEventListener('click', closeLightbox);
  addEventListener('resize', fit);
  addEventListener('hashchange', function () { var p = pageFromHash(); if (visible().indexOf(p) < 0) goTo(p); });

  showChrome();
  fit();
  setTimeout(function () { root.classList.add('book-ready'); }, 300);
  window.__book = { goTo: goTo, next: function () { go(1); }, prev: function () { go(-1); }, pages: N };

  function showShot(n) {
    var i = clamp(n, 1, N) - 1;
    src.forEach(function (p, k) { p.classList.toggle('is-shot', k === i); });
  }

  function buildSheet(cols) {
    var host = document.getElementById('pages');
    host.style.setProperty('--cols', cols);
    src.forEach(function (p, i) {
      var cell = document.createElement('div');
      cell.className = 'sheet-cell';
      cell.dataset.label = 'p.' + (i + 1) + ' · ' + (p.dataset.type || '') + (p.dataset.id ? ' · ' + p.dataset.id : '');
      host.insertBefore(cell, p); cell.appendChild(p);
    });
  }

  function ready() {
    var fonts = document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
    var imgs = Array.prototype.slice.call(document.images).map(function (im) {
      if (im.complete) return Promise.resolve();
      return new Promise(function (r) { im.addEventListener('load', r); im.addEventListener('error', r); });
    });
    return Promise.all([fonts].concat(imgs));
  }
  function describe(el) {
    if (!el) return '';
    var s = el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '');
    var t = (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40);
    return t ? s + ' "' + t + '"' : s;
  }
  function freeFlow(el, stop) {
    for (var n = el; n && n !== stop; n = n.parentElement) {
      var cs = getComputedStyle(n);
      if (cs.position === 'absolute' || cs.position === 'fixed') return false;
      if (n !== el && (cs.overflowX !== 'visible' || cs.overflowY !== 'visible')) return false;
    }
    return true;
  }
  function measure(pg, i) {
    var issues = [];
    var pc = pg.querySelector(':scope > .pc');
    if (pc) {
      var cr = pc.getBoundingClientRect(), limit = cr.bottom, dockName = '';
      pg.querySelectorAll(':scope > [data-dock]').forEach(function (d) {
        var t = d.getBoundingClientRect().top - 6;
        if (t < limit) { limit = t; dockName = d.dataset.dock; }
      });
      var maxB = cr.top, worst = null, maxR = cr.right, wide = null;
      pc.querySelectorAll('*').forEach(function (el) {
        if (!freeFlow(el, pc)) return;
        var r = el.getBoundingClientRect();
        if (!r.width && !r.height) return;
        if (r.bottom > maxB) { maxB = r.bottom; worst = el; }
        if (r.right > maxR + 0.5) { maxR = r.right; wide = el; }
      });
      if (maxB > limit + 0.5) issues.push({ kind: 'overflow', px: Math.round(maxB - limit), into: dockName || 'page-bottom', el: describe(worst) });
      if (wide) issues.push({ kind: 'overflow-x', px: Math.round(maxR - cr.right), el: describe(wide) });
    }
    pg.querySelectorAll('*').forEach(function (el) {
      var cs = getComputedStyle(el);
      if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1) issues.push({ kind: 'truncated', el: describe(el) });
    });
    pg.querySelectorAll('img').forEach(function (im) {
      if (!im.naturalWidth) issues.push({ kind: 'image-broken', src: (im.getAttribute('src') || '').slice(0, 80) });
    });
    return { page: i + 1, type: pg.dataset.type || '', id: pg.dataset.id || '', issues: issues };
  }
  function runCheck() {
    var r = src.map(measure);
    var out = document.createElement('script');
    out.type = 'application/json'; out.id = 'check-result';
    out.textContent = JSON.stringify({ pages: N, results: r });
    document.body.appendChild(out);
  }
})();
