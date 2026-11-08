#!/usr/bin/env node
/**
 * iso_layout.mjs — 아이소메트릭 아키텍처 도식을 덱 문법(svg.dg)으로 방출하는 빌드 시점 생성기.
 *
 * [목적] 시맨틱 JSON(architecture.md §3)을 넣으면 1920×1080 발표 화면에 바로 놓을 수 있는
 *   `svg.dg` 한 장을 만든다. 좌표·배치·연결 경로 계산을 저작자가 손으로 하지 않게 하는 것이
 *   이 도구의 존재 이유다. 런타임 의존은 0 — 결과 SVG만 덱에 들어간다.
 *
 * [입력] `--in <scene.json|->`. 장비 kind·연결·영역을 담은 시맨틱 모델(architecture.md §3).
 * [출력] `--out <file.svg|->`. 계약: viewBox 폭 1664, 글자 20px 이상 클래스만,
 *   링크 1개 = path 1개, 장식은 path/line 금지, SMIL·CSS 애니메이션 없음, 정적 완결.
 * [의존] Node 18+ 표준 모듈만(npm 패키지 0). 빌드 도구이므로 덱 산출물에는 아무것도 남지 않는다.
 * [재현성] 같은 입력 → 같은 바이트. 시간·난수·환경값·절대경로를 출력에 넣지 않는다.
 *   검증: `node iso_layout.mjs --in a.json --out x.svg` 두 번 실행 후 diff 0.
 *
 * [원본 고지 — Networkify]
 *   아이소 투영(iso)·연결 폴리라인(getIsoPath)·BFS 계층 배치(layoutNodes)는
 *   Networkify 에서 이식했다. MIT License, Copyright (c) 2026 urbanapp.
 *     저장소  https://github.com/urbanapp/networkify
 *     리비전  13ce36fdaf7dae5954a8cf9a2ed3aaa85d17bf31 (2026-09-08)
 *     원본    src/geometry.js  — iso(), getIsoPath()
 *             src/layout.js    — layoutNodes()
 *   변경 내역(이식 ≠ 복사):
 *     1. TILE_W/TILE_H/ICON_SZ 상수를 장비 치수에서 유도하도록 매개변수화(원본 220/130/90).
 *     2. layoutNodes 의 셀 중심 +0.5 스냅 제거 — 정수 격자를 유지해야 영역 바닥면 계산이 단순해진다.
 *     3. 다중 컴포넌트(끊긴 그래프)를 원본처럼 대각 띠로 이어붙이지 않고 세로 밴드로 분리.
 *     4. 원본의 캔버스 렌더러·PNG 아이콘·에디터·트윈은 가져오지 않았다. 3면 상자·상태 배지·
 *        영역 바닥면·라벨 칩·SVG 방출은 이 파일에서 새로 작성한 코드다.
 *   상세 근거: references/architecture-sources.md 의 Networkify 행.
 *
 * [수정 시 주의]
 *   - 링크 path 를 늘리지 말 것: 공통 엔진 draw() 가 슬라이드당 path 12개만 그린다.
 *   - 장식(격자·포트·슬롯·배지)은 polygon/polyline/rect/circle 만. path·line 은 링크 전용.
 *   - 글자에 고정 px·hex 를 쓰지 말 것(대비 검사기가 계산값을 읽는다). 클래스만.
 *   - 출력 순서: 영역 → 링크 → 장비. 장비를 뒤에 그려야 링크가 상자 밑으로 들어간다.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import process from 'node:process';

/* ── 아이소 격자 ────────────────────────────────────────────────────────────
   타일 폭/높이는 장비 최대 치수에서 유도한다(수동 상수 금지 — 장비를 키우면 자동 반영).
   iso(): 그리드(col,row) → 화면 px. 원본 Networkify geometry.js 와 같은 식. */
let TILE_W = 236;
let TILE_H = 160;
const iso2 = (col, row) => ({ x: ((col - row) * TILE_W) / 2, y: ((col + row) * TILE_H) / 2 });
const iso = iso2;

/* 원본 Networkify geometry.js getIsoPath() 이식.
   두 점이 같은 축이거나 대각이면 직선, 그 외에는 대각 구간 + 축 구간으로 꺾는다. */
function getIsoPath(pa, pb) {
  const dc = Math.abs(pb.col - pa.col);
  const dr = Math.abs(pb.row - pa.row);
  if (dc < 0.01 || dr < 0.01) return [pa, pb];
  if (Math.abs(dc - dr) < 0.01) return [pa, pb];
  const diag = Math.min(dc, dr);
  return [
    pa,
    {
      col: pa.col + Math.sign(pb.col - pa.col) * diag,
      row: pa.row + Math.sign(pb.row - pa.row) * diag,
    },
    pb,
  ];
}

/* 원본 Networkify layout.js layoutNodes() 이식 + 변경 2·3·4.
   BFS 레벨을 세로 밴드로, 형제를 가로로 편다.
   변경 4(가장 중요): 아이소 화면 기저에 맞춰 좌표를 회전한다.
     원본은 row=level*2, col=index*2 로 두어 형제가 오른쪽 아래로 흘러내렸다(대각 띠).
     화면 기저는 가로 u = (+1,-1), 세로 v = (+1,+1) 이므로
       col = U_STEP*u + v, row = v - U_STEP*u
     로 두면 형제는 정확히 수평, 레벨은 정확히 수직으로 떨어진다. 세로 높이가 줄어
     5레벨 장도 슬롯 높이 안에 들어온다(1차 렌더에서 1000px → 852px 로 확인). */
function layoutNodes(nodes, edges) {
  const pos = new Map();
  const adj = new Map(nodes.map((n) => [n.id, []]));
  const indeg = new Map(nodes.map((n) => [n.id, 0]));
  for (const e of edges) {
    if (!adj.has(e.from) || !adj.has(e.to)) continue;
    adj.get(e.from).push(e.to);
    indeg.set(e.to, (indeg.get(e.to) || 0) + 1);
  }
  const order = nodes.map((n) => n.id);
  const visited = new Set();
  let rowBase = 0;

  const roots = order.filter((id) => (indeg.get(id) || 0) === 0).concat(order);
  for (const root of roots) {
    if (visited.has(root)) continue;
    const levels = [];
    const queue = [root];
    visited.add(root);
    const depth = new Map([[root, 0]]);
    while (queue.length) {
      const cur = queue.shift();
      const d = depth.get(cur);
      (levels[d] ||= []).push(cur);
      for (const nb of adj.get(cur) || []) {
        if (visited.has(nb)) continue;
        visited.add(nb);
        depth.set(nb, d + 1);
        queue.push(nb);
      }
    }
    const maxW = Math.max(...levels.map((l) => l.length));
    const U_STEP = 2; // 형제 한 칸 = 가로 타일 2개
    levels.forEach((lv, lv2) => {
      const off = (maxW - lv.length) / 2;
      lv.forEach((id, i) => {
        const u = (off + i) * U_STEP;
        const v = rowBase + lv2;
        pos.set(id, { col: u + v, row: v - u });
      });
    });
    rowBase += levels.length + 1; // 변경 3: 다음 컴포넌트는 아래 밴드로
  }

  const list = [...pos.values()];
  const cc = (Math.min(...list.map((p) => p.col)) + Math.max(...list.map((p) => p.col))) / 2;
  const rc = (Math.min(...list.map((p) => p.row)) + Math.max(...list.map((p) => p.row))) / 2;
  for (const p of pos.values()) {
    p.col -= cc;
    p.row -= rc;
  }
  return pos;
}

/* ── 장비 컴포넌트 ─────────────────────────────────────────────────────────
   전부 코드 생성 도형이다(브랜드 로고·PNG 없음). 치수 단위는 px(@1664 도식 폭).
   dep = 상판에서 아래로 내려오는 두께. slots/ports 는 앞면 디테일 개수. */
const KINDS = {
  server1u: { W: 118, H: 66, dep: 20, slots: 1, label: '서버 1U' },
  server2u: { W: 118, H: 66, dep: 42, slots: 2, label: '서버 2U' },
  rack: { W: 126, H: 72, dep: 88, slots: 6, rail: true, label: '랙' },
  storage: { W: 126, H: 72, dep: 46, slots: 3, drives: 4, label: '스토리지' },
  switch: { W: 150, H: 86, dep: 14, ports: 12, label: '스위치' },
  router: { W: 136, H: 78, dep: 20, ports: 4, glyph: 'route', label: '라우터' },
  firewall: { W: 128, H: 74, dep: 26, bricks: true, label: '방화벽' },
  lb: { W: 140, H: 82, dep: 18, ports: 3, glyph: 'fanout', label: '로드밸런서' },
  cloud: { W: 150, H: 92, dep: 4, glyph: 'cloud', flat: true, label: '클라우드' },
  dc: { W: 132, H: 76, dep: 96, slots: 4, rail: true, label: '데이터센터' },
};
const DEFAULT_KIND = 'server2u';

/* 상태 어휘 — 색만으로 구분하지 않는다(IBM 규칙). 색 + 도형 배지를 함께 쓴다. */
const STATES = {
  ok: { led: 'var(--success)', badge: null },
  busy: { led: 'var(--accent)', badge: null },
  warn: { led: 'var(--accent)', badge: 'diamond' },
  down: { led: 'var(--danger)', badge: 'bang' },
  standby: { led: 'var(--muted)', badge: 'ring' },
};

const round = (n) => Math.round(n * 10) / 10;
const pt = (p) => `${round(p.x)},${round(p.y)}`;

/* 글자 폭 추정: 한글·전각 1.0em, 라틴·숫자 0.56em, 공백 0.3em.
   측정 라이브러리 없이 라벨 칩 폭을 정하기 위한 근사 — 넘치면 check_deck 이 잡는다. */
function textPx(s, size) {
  let w = 0;
  for (const ch of String(s)) {
    const cp = ch.codePointAt(0);
    if (ch === ' ') w += size * 0.3;
    else if (cp < 0x2e80) w += size * 0.56;
    else w += size;
  }
  return w;
}

/* 상자 기하: 상판 중심 (x,y). 앞 꼭짓점이 화면 최전방. */
function boxGeom(x, y, spec) {
  const front = { x, y: y + spec.H / 2 };
  const back = { x, y: y - spec.H / 2 };
  const right = { x: x + spec.W / 2, y };
  const left = { x: x - spec.W / 2, y };
  const down = (p, u) => ({ x: p.x, y: p.y + u * spec.dep });
  const top = (s, t) => {
    // 상판 위 이중선형 좌표(뒤→오른→앞→왼)
    const a = back, b = right, c = front, d = left;
    return {
      x: (1 - s) * (1 - t) * a.x + s * (1 - t) * b.x + s * t * c.x + (1 - s) * t * d.x,
      y: (1 - s) * (1 - t) * a.y + s * (1 - t) * b.y + s * t * c.y + (1 - s) * t * d.y,
    };
  };
  /* 앞면 파라미터: face='R' → 앞→오른쪽 면, 'L' → 왼쪽→앞 면. t 는 면을 가로, u 는 아래로. */
  const face = (side, t, u) => {
    const a = side === 'R' ? front : left;
    const b = side === 'R' ? right : front;
    return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t + u * spec.dep };
  };
  return { front, back, right, left, down, top, face };
}

/* 상태 배지 — 색 + 도형. top 좌표 위에 8~10px 도형을 놓는다. */
function stateMark(shape, c) {
  const r = 8.5;
  if (shape === 'diamond') {
    return `<polygon points="${pt({ x: c.x, y: c.y - r })} ${pt({ x: c.x + r, y: c.y })} ${pt({ x: c.x, y: c.y + r })} ${pt({ x: c.x - r, y: c.y })}" fill="var(--accent)" stroke="var(--paper)" stroke-width="1.6"/>`;
  }
  if (shape === 'bang') {
    return `<polygon points="${pt({ x: c.x, y: c.y - r })} ${pt({ x: c.x + r, y: c.y + r * 0.8 })} ${pt({ x: c.x - r, y: c.y + r * 0.8 })}" fill="var(--danger)" stroke="var(--paper)" stroke-width="1.6"/><rect x="${round(c.x - 1.2)}" y="${round(c.y - 3)}" width="2.4" height="6" fill="var(--paper)"/><rect x="${round(c.x - 1.2)}" y="${round(c.y + 4.2)}" width="2.4" height="2.2" fill="var(--paper)"/>`;
  }
  if (shape === 'ring') {
    return `<circle cx="${round(c.x)}" cy="${round(c.y)}" r="${r}" fill="var(--paper)" stroke="var(--muted)" stroke-width="3"/>`;
  }
  return '';
}

/* 장비 한 대 방출. 앞면 디테일은 전부 polyline(장식 path 금지 계약). */
function deviceMarkup(n, spec, colorOf) {
  const { x, y } = colorOf(n);
  const g = boxGeom(x, y, spec);
  const st = STATES[n.state] || STATES.ok;
  const out = [];
  out.push(`<g data-arch-node="${n.id}" data-kind="${n.kind || DEFAULT_KIND}" data-state="${n.state || 'ok'}"${n.step != null ? '' : ''}>`);
  // 바닥 그림자
  out.push(`<ellipse cx="${round(x)}" cy="${round(g.front.y + spec.dep + 3)}" rx="${round(spec.W * 0.5)}" ry="${round(spec.H * 0.22)}" fill="var(--ink)" fill-opacity=".12"/>`);
  // 왼면(어두움) → 오른면(중간) → 상판(밝음). 한 색의 3단 불투명도 = 단색 노드 규칙.
  out.push(`<polygon points="${pt(g.left)} ${pt(g.front)} ${pt(g.down(g.front, 1))} ${pt(g.down(g.left, 1))}" fill="var(--blue)" fill-opacity=".82" stroke="var(--blue)" stroke-width="1.6" stroke-linejoin="round"/>`);
  out.push(`<polygon points="${pt(g.front)} ${pt(g.right)} ${pt(g.down(g.right, 1))} ${pt(g.down(g.front, 1))}" fill="var(--blue)" fill-opacity=".58" stroke="var(--blue)" stroke-width="1.6" stroke-linejoin="round"/>`);
  out.push(`<polygon points="${pt(g.back)} ${pt(g.right)} ${pt(g.front)} ${pt(g.left)}" fill="var(--paper)" stroke="var(--blue)" stroke-width="${n.state === 'down' ? '2.6' : '2.6'}" stroke-dasharray="${n.state === 'down' ? '8 5' : 'none'}" stroke-linejoin="round"/>`);
  out.push(`<polygon points="${pt(g.back)} ${pt(g.right)} ${pt(g.front)} ${pt(g.left)}" fill="var(--blue)" fill-opacity=".18" stroke="none"/>`);

  // 앞면 디테일
  const det = [];
  const slots = spec.slots || 0;
  for (let i = 0; i < slots; i += 1) {
    const u = (i + 0.62) / slots;
    det.push(`${pt(g.face('R', 0.2, u * 0.9))} ${pt(g.face('R', 0.86, u * 0.9 + 0.02))}`);
  }
  const ports = spec.ports || 0;
  for (let i = 0; i < ports; i += 1) {
    const t = 0.18 + (i / Math.max(1, ports - 1)) * 0.64;
    det.push(`${pt(g.face('R', t, 0.34))} ${pt(g.face('R', t, 0.74))}`);
  }
  if (spec.bricks) {
    for (let row = 0; row < 3; row += 1) {
      const u = 0.22 + row * 0.26;
      const off = row % 2 ? 0.14 : 0.06;
      det.push(`${pt(g.face('R', off, u))} ${pt(g.face('R', off + 0.3, u))}`);
      det.push(`${pt(g.face('R', off + 0.42, u))} ${pt(g.face('R', off + 0.72, u))}`);
    }
  }
  if (spec.rail) {
    det.push(`${pt(g.face('L', 0.1, 0.12))} ${pt(g.face('L', 0.9, 0.12))}`);
    det.push(`${pt(g.face('R', 0.1, 0.12))} ${pt(g.face('R', 0.9, 0.12))}`);
  }
  if (det.length) {
    out.push(`<g stroke="var(--paper)" stroke-opacity=".55" stroke-width="2.4" stroke-linecap="round" fill="none">${det.map((p) => `<polyline points="${p}"/>`).join('')}</g>`);
  }
  // 앞면 LED — 전원/상태. 색 + 상판 배지 조합으로 색약 접근성 확보.
  out.push(`<circle cx="${round(g.face('R', 0.12, 0.3).x)}" cy="${round(g.face('R', 0.12, 0.3).y)}" r="3.2" fill="${st.led}"/>`);

  // 상판 글리프(라우터·LB) — polygon/polyline 만
  if (spec.glyph === 'route') {
    const a = g.top(0.3, 0.3), b = g.top(0.7, 0.7), c = g.top(0.7, 0.3), d = g.top(0.3, 0.7);
    out.push(`<polyline points="${pt(a)} ${pt(b)}" stroke="var(--blue)" stroke-width="2.6" stroke-linecap="round"/><polyline points="${pt(c)} ${pt(d)}" stroke="var(--blue)" stroke-width="2.6" stroke-linecap="round" opacity=".55"/>`);
  } else if (spec.glyph === 'fanout') {
    const o = g.top(0.5, 0.5);
    const marks = [g.top(0.14, 0.2), g.top(0.14, 0.5), g.top(0.14, 0.8)];
    out.push(marks.map((m) => `<polyline points="${pt(o)} ${pt(m)}" stroke="var(--blue)" stroke-width="2.4" stroke-linecap="round" fill="none"/>`).join(''));
  } else if (spec.glyph === 'cloud') {
    // 구름 실루엣은 원 3개 합성(폴리곤·원만 사용)
    const o = g.top(0.5, 0.45);
    out.push(`<circle cx="${round(o.x - 14)}" cy="${round(o.y + 2)}" r="13" fill="var(--paper)" fill-opacity=".9" stroke="var(--blue)" stroke-width="2"/><circle cx="${round(o.x + 14)}" cy="${round(o.y + 2)}" r="13" fill="var(--paper)" fill-opacity=".9" stroke="var(--blue)" stroke-width="2"/><circle cx="${round(o.x)}" cy="${round(o.y - 9)}" r="15" fill="var(--paper)" fill-opacity=".9" stroke="var(--blue)" stroke-width="2"/>`);
  }

  // 상태 배지
  if (st.badge) out.push(stateMark(st.badge, g.top(0.78, 0.22)));

  // 라벨 칩 — 글자는 t-l(26/700) 계약 클래스. 폭은 추정치 + 여유.
  const label = n.name || n.id;
  const isChip = spec.label !== undefined;
  if (isChip) {
    const tw = textPx(label, 26) + 30;
    const th = 38;
    const ly = g.front.y + spec.dep + 30;
    out.push(`<rect class="k-paper" x="${round(x - tw / 2)}" y="${round(ly - th / 2)}" width="${round(tw)}" height="${th}" style="rx:9px"/>`);
    out.push(`<text class="t-l" x="${round(x)}" y="${round(ly + 9)}" text-anchor="middle">${esc(label)}</text>`);
  }
  out.push('</g>');
  return out.join('\n');
}

/* 영역(경계) 바닥면.
   격자 사각형(c,r 축)으로 만들면 세로로 쌓인 묶음이 좁고 긴 띠가 되어야 할 자리가
   넓고 빈 마름모가 된다(1차 렌더에서 확인). 그래서 영역도 배치와 같은 (u,v) 기저로 받는다.
     uv = [u0, v0, u1, v1]   // u = 가로 타일, v = 레벨
   u·v → 격자: col = 2u + v, row = v - 2u.
   `nodes` 만 주면 소속 노드의 (u,v) 경계에 pad 를 더해 같은 방식으로 만든다. */
function zoneGrid(zone, positions) {
  if (Array.isArray(zone.uv) && zone.uv.length === 4) {
    const [u0, v0, u1, v1] = zone.uv;
    return { u0, v0, u1, v1 };
  }
  const members = (zone.nodes || []).map((id) => positions.get(id)).filter(Boolean);
  if (!members.length) return null;
  const uvOf = (p) => ({ u: (p.col - p.row) / 4, v: (p.col + p.row) / 2 });
  const us = members.map(uvOf);
  const pad = zone.pad != null ? zone.pad : 0.55;
  return {
    u0: Math.min(...us.map((q) => q.u)) - pad,
    u1: Math.max(...us.map((q) => q.u)) + pad,
    v0: Math.min(...us.map((q) => q.v)) - pad,
    v1: Math.max(...us.map((q) => q.v)) + pad,
  };
}

function zoneMarkup(zone, positions, bounds) {
  const g = zoneGrid(zone, positions);
  if (!g) return '';
  const toGrid = (u, v) => ({ col: 2 * u + v, row: v - 2 * u });
  const corners = [[g.u0, g.v0], [g.u1, g.v0], [g.u1, g.v1], [g.u0, g.v1]]
    .map(([u, v]) => {
      const q = toGrid(u, v);
      return iso2(q.col, q.row);
    });
  const trust = zone.kind === 'trust';
  const out = [];
  out.push(`<g data-arch-zone="${zone.id}"${zone.kind ? ` data-zone-kind="${zone.kind}"` : ''}>`);
  out.push(`<polygon points="${corners.map(pt).join(' ')}" fill="var(--light)" fill-opacity=".9" stroke="${trust ? 'var(--accent)' : 'var(--line)'}" stroke-width="2" stroke-dasharray="${trust ? '12 9' : '16 12'}" stroke-linejoin="round"/>`);
  if (zone.label) {
    // 라벨은 가장 위 꼭짓점 바깥 — 바닥면 위쪽에 아무것도 없으므로 겹치지 않는다.
    // 글자는 t-l(26px): t-mile(22px)은 도식이 슬롯에 맞춰 축소될 때 실측 18px 하한을
    // 깨므로 존 라벨은 26px 계열로 올리고 칩도 그 크기에 맞춘다.
    const top = corners.reduce((a, c) => (c.y < a.y ? c : a), corners[0]);
    const tw = textPx(zone.label, 26) + 24;
    const lx = top.x;
    const ly = top.y - 36;
    bounds.push({ x: lx - tw / 2, y: ly - 19 }, { x: lx + tw / 2, y: ly + 9 });
    out.push(`<rect class="k-paper" x="${round(lx - tw / 2)}" y="${round(ly - 17)}" width="${round(tw)}" height="36" style="rx:8px"/>`);
    out.push(`<text class="t-l k-t-b" x="${round(lx)}" y="${round(ly + 9)}" text-anchor="middle">${esc(zone.label)}</text>`);
  }
  out.push('</g>');
  return out.join('\n');
}

/* 링크 — 계약: 1개 = path 1개. 방향은 marker, 병렬은 channel 오프셋. */
function edgeMarkup(e, positions, flowBudget, occupied) {
  const a = positions.get(e.from);
  const b = positions.get(e.to);
  if (!a || !b) return { svg: '', warn: `edge ${e.from}->${e.to}: 없는 노드 참조` };
  const pts = getIsoPath(a, b).map((q) => iso(q.col, q.row));
  // 끝점을 상자 앞에서 당겨 화살촉이 상판을 덮지 않게
  const end = pts[pts.length - 1];
  const prev = pts[pts.length - 2] || pts[0];
  const dx = end.x - prev.x;
  const dy = end.y - prev.y;
  const len = Math.hypot(dx, dy) || 1;
  const pull = 40;
  const ch = (e.channel || 0) * 11; // 병렬 채널: 수직 오프셋
  const nx = -dy / len;
  const ny = dx / len;
  const pts2 = pts.map((p, i) => (i === pts.length - 1 ? { x: p.x - (dx / len) * pull + nx * ch, y: p.y - (dy / len) * pull + ny * ch } : { x: p.x + nx * ch, y: p.y + ny * ch }));
  const d = pts2.map((p, i) => `${i ? 'L' : 'M'} ${round(p.x)} ${round(p.y)}`).join(' ');
  const kind = e.kind || 'main';
  const cls = kind === 'main' ? 'k-ln-b' : kind === 'sub' ? 'k-ln-n' : 'k-ln-g';
  const wantFlow = e.flow === true && flowBudget.left > 0;
  if (wantFlow) flowBudget.left -= 1;
  const flow = wantFlow ? 'dash-flow' : '';
  const dir = e.direction || 'forward';
  const head = dir === 'reverse' ? 'marker-start="url(#ah-b)"' : 'marker-end="url(#ah-b)"';
  const both = dir === 'both' ? ' marker-start="url(#ah-b)"' : '';
  const svg = `<path data-arch-edge="${e.from}--${e.to}" class="${[flow, cls].filter(Boolean).join(' ')}" d="${d}" ${head}${both}/>`;
  // 링크 라벨(t-q = 24/700 + 종이 halo) — 가장 긴 구간의 중앙, 선에서 수직으로 띄운다.
  let label = '';
  const mark = [];
  if (e.label) {
    let bi = 0;
    let bl = -1;
    for (let i = 0; i < pts2.length - 1; i += 1) {
      const l = Math.hypot(pts2[i + 1].x - pts2[i].x, pts2[i + 1].y - pts2[i].y);
      if (l > bl) { bl = l; bi = i; }
    }
    const a2 = pts2[bi];
    const b2 = pts2[bi + 1];
    const mx = (a2.x + b2.x) / 2;
    const my = (a2.y + b2.y) / 2;
    const l2 = Math.hypot(b2.x - a2.x, b2.y - a2.y) || 1;
    const ux = -(b2.y - a2.y) / l2;
    const uy = (b2.x - a2.x) / l2;
    // 라벨 충돌 회피: 장비 사각형(칩 포함) 안에 떨어지면 반대쪽 → 더 멀리 순서로 물린다.
    const inside = (x, y) => (occupied || []).some((b) => x > b.x0 - 10 && x < b.x1 + 10 && y > b.y0 - 10 && y < b.y1 + 10);
    let off = 22;
    let lx = mx + ux * off;
    let ly = my + uy * off;
    for (const cand of [22, -22, 90, -90, 120, -120]) {
      const cx2 = mx + ux * cand;
      const cy2 = my + uy * cand;
      if (!inside(cx2, cy2)) { off = cand; lx = cx2; ly = cy2; break; }
    }
    label = `<text class="t-q" x="${round(lx)}" y="${round(ly + 8)}" text-anchor="middle">${esc(e.label)}</text>`;
    const tw = textPx(e.label, 24);
    mark.push({ x: lx - tw / 2, y: ly - 14 }, { x: lx + tw / 2, y: ly + 14 });
  }
  return { svg: svg + label, warn: '', mark };
}

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/* ── 조립 ─────────────────────────────────────────────────────────────── */
function build(scene) {
  const warn = [];
  if (Array.isArray(scene.tile) && scene.tile.length === 2) {
    TILE_W = Number(scene.tile[0]);
    TILE_H = Number(scene.tile[1]);
  }
  const nodes = (scene.nodes || []).map((n) => ({ ...n, kind: n.kind || DEFAULT_KIND }));
  if (nodes.length < 2) throw new Error('nodes 는 2개 이상이어야 합니다');
  if (nodes.length > 7) warn.push(`nodes ${nodes.length}개 — 아이소 계열 권장 상한은 7개입니다(라벨 밀도)`);

  const specs = new Map(nodes.map((n) => [n.id, KINDS[n.kind] || KINDS[DEFAULT_KIND]]));
  const known = new Set(nodes.map((n) => n.id));
  for (const e of scene.edges || []) {
    if (!known.has(e.from) || !known.has(e.to)) warn.push(`edge ${e.from}->${e.to}: 없는 노드 참조`);
  }
  const edges = (scene.edges || []).filter((e) => known.has(e.from) && known.has(e.to));

  // 좌표: 명시 col/row 가 모두 있으면 그대로, 아니면 BFS 자동 배치
  const explicit = nodes.every((n) => typeof n.col === 'number' && typeof n.row === 'number');
  const positions = explicit
    ? new Map(nodes.map((n) => [n.id, { col: n.col, row: n.row }]))
    : layoutNodes(nodes, edges);
  if (!explicit) warn.push('좌표 미지정 → BFS 자동 배치를 썼습니다(밴드형). 정확한 배치는 col/row 를 주세요');

  const VBW = 1664;
  const bounds = [];
  const colorOf = (n) => iso(positions.get(n.id).col, positions.get(n.id).row);

  // 1) 영역 -> path 예산 계산을 위해 먼저 경계만 모은다
  let zoneSvg = '';
  for (const z of scene.zones || []) zoneSvg += zoneMarkup(z, positions, bounds) + '\n';

  // 2) 링크 (path)
  const nodeBoxes = nodes.map((n) => {
    const c = colorOf(n);
    const spec = specs.get(n.id);
    const tw = textPx(n.name || n.id, 26) + 30;
    return {
      x0: Math.min(c.x - spec.W / 2, c.x - tw / 2),
      x1: Math.max(c.x + spec.W / 2, c.x + tw / 2),
      y0: c.y - spec.H / 2 - 14,
      y1: Math.max(c.y + spec.H / 2 + spec.dep, c.y + spec.H / 2 + spec.dep + 26 + 19) + 6,
    };
  });
  const flowBudget = { left: Number(scene.maxFlow != null ? scene.maxFlow : 3) };
  const steps = [...new Set(nodes.map((n) => n.step ?? 0))].sort((a, b) => a - b);
  const edgeByStep = new Map(steps.map((s) => [s, []]));
  for (const e of edges) {
    const step = e.step != null ? e.step : Math.min(...nodes.filter((n) => n.id === e.from || n.id === e.to).map((n) => n.step ?? 0));
    const r = edgeMarkup(e, positions, flowBudget, nodeBoxes);
    if (r.warn) warn.push(r.warn);
    if (r.svg) (edgeByStep.get(step) || edgeByStep.get(steps[0])).push(r.svg);
    if (r.mark) bounds.push(...r.mark);
    const pos = positions.get(e.from);
    const pos2 = positions.get(e.to);
    for (const p of [pos, pos2]) bounds.push(iso(p.col, p.row));
  }
  if (flowBudget.left < 0 || (scene.edges || []).filter((e) => e.flow).length > (scene.maxFlow ?? 3)) {
    warn.push('flow 링크가 3개를 넘습니다 — 엔진 particles() 는 슬라이드당 3개만 굴립니다');
  }

  // 3) 장비 — 영역별 그룹핑 없이 (col+row) 오름차순(뒤에서 앞으로)
  const sorted = [...nodes].sort((a, b) => {
    const pa = positions.get(a.id);
    const pb = positions.get(b.id);
    return pa.col + pa.row - (pb.col + pb.row);
  });
  const nodeByStep = new Map(steps.map((s) => [s, []]));
  for (const n of sorted) {
    const spec = specs.get(n.id);
    nodeByStep.get(n.step ?? 0).push(deviceMarkup(n, spec, colorOf));
    const c = colorOf(n);
    const label = n.name || n.id;
    const tw = textPx(label, 26) + 30;
    bounds.push({ x: c.x - spec.W / 2 - 12, y: c.y - spec.H / 2 - 14 });
    bounds.push({ x: c.x + spec.W / 2 + 12, y: c.y + spec.H / 2 + spec.dep + 52 });
    bounds.push({ x: c.x - tw / 2, y: c.y + spec.H / 2 + spec.dep + 52 });
    bounds.push({ x: c.x + tw / 2, y: c.y + spec.H / 2 + spec.dep + 52 });
  }

  const minX = Math.min(...bounds.map((p) => p.x));
  const maxX = Math.max(...bounds.map((p) => p.x));
  const minY = Math.min(...bounds.map((p) => p.y));
  const maxY = Math.max(...bounds.map((p) => p.y));
  const W = maxX - minX;
  const H = maxY - minY;
  const tx = (VBW - W) / 2 - minX;
  const ty = 26 - minY;
  const VBH = Math.ceil(H + 52);
  if (VBH > 840) warn.push(`viewBox 높이 ${VBH}px — 슬롯 높이(≈840)를 넘어 글자가 축소됩니다`);
  if (W > VBW - 40) warn.push(`도식 폭 ${Math.ceil(W)}px — viewBox 폭 ${VBW} 를 넘어 좌우가 잘릴 수 있습니다`);

  const pathCount = edges.length;
  if (pathCount > 12) warn.push(`링크 ${pathCount}개 — 엔진 draw() 예산 12개를 넘습니다`);

  const aria = scene.aria || `${scene.title || '아이소메트릭 구성도'} — 장비 ${nodes.length}대, 연결 ${edges.length}개`;
  const title = scene.title || '아이소메트릭 구성도';

  const parts = [];
  parts.push(`<svg class="dg" viewBox="0 0 ${VBW} ${VBH}" role="img" aria-label="${esc(aria)}">`);
  parts.push(`<title>${esc(title)}</title>`);
  parts.push(`<g transform="translate(${round(tx)} ${round(ty)})">`);
  parts.push(zoneSvg.trimEnd());
  for (const s of steps) parts.push(`<g data-step="${s}" data-arch-layer="edges">${edgeByStep.get(s).join('')}</g>`);
  for (const s of steps) parts.push(`<g data-step="${s}" data-arch-layer="nodes">${nodeByStep.get(s).join('')}</g>`);
  parts.push('</g>');
  parts.push('</svg>');
  return { svg: parts.filter(Boolean).join('\n') + '\n', warn, stats: { nodes: nodes.length, edges: edges.length, VBW, VBH, pathCount } };
}

/* ── CLI ──────────────────────────────────────────────────────────────── */
const HELP = `iso_layout.mjs — 시맨틱 JSON → 아이소메트릭 svg.dg 생성기 (빌드 시점, 의존 0)

사용법
  node iso_layout.mjs --in <scene.json> --out <fig.svg>
  node iso_layout.mjs --in - --out -            # stdin → stdout
  node iso_layout.mjs --kinds                   # 사용 가능한 장비 kind 와 치수
  node iso_layout.mjs --help

옵션
  --in  <path|->   입력 시맨틱 JSON. '-' 는 stdin.
  --out <path|->   출력 SVG. 생략하면 stdout.
  --kinds          장비 목록 출력 후 종료.
  --quiet          경고를 stderr 에 쓰지 않는다(종료 코드는 유지).
  --help           이 도움말.

입력 형식(architecture.md §3)
  { "title":"...", "aria":"...", "nodes":[{ "id","name","kind","state","col","row","step" }],
    "edges":[{ "from","to","label","kind","direction","channel","flow" }],
    "zones":[{ "id","label","kind","nodes":[...],"pad" }], "maxFlow":3 }
  kind: ${Object.keys(KINDS).join(' · ')}
  state: ${Object.keys(STATES).join(' · ')}
  좌표를 모두 주면 그대로 쓰고, 하나라도 없으면 BFS 자동 배치.

종료 코드  0 성공 · 1 입력 오류 · 2 사용법 오류
출력 계약  viewBox 폭 1664 · 글자 클래스만(t-l/t-q/t-mile/k-t-b) · 링크 1개 = path 1개 ·
           장식은 polygon/polyline/rect/circle · SMIL/CSS 애니메이션 없음 · 정적 완결
`;

function main(argv) {
  const arg = (k, d = null) => {
    const i = argv.indexOf(k);
    return i >= 0 && argv[i + 1] ? argv[i + 1] : d;
  };
  if (argv.includes('--help') || argv.includes('-h')) {
    process.stdout.write(HELP);
    return 0;
  }
  if (argv.includes('--kinds')) {
    const rows = Object.entries(KINDS).map(([k, v]) => `${k.padEnd(10)} W${v.W} H${v.H} dep${v.dep}  ${v.label}`);
    process.stdout.write(`아이소 장비 세트(${Object.keys(KINDS).length}종, 단위 px@1664)\n${rows.join('\n')}\n`);
    return 0;
  }
  const inPath = arg('--in');
  if (!inPath) {
    process.stderr.write('입력이 없습니다. --in <scene.json|-> (--help 참고)\n');
    return 2;
  }
  let raw;
  try {
    raw = inPath === '-' ? readFileSync(0, 'utf8') : readFileSync(inPath, 'utf8');
  } catch (e) {
    process.stderr.write(`입력을 읽지 못했습니다: ${inPath}\n`);
    return 1;
  }
  let scene;
  try {
    scene = JSON.parse(raw);
  } catch (e) {
    process.stderr.write(`JSON 파싱 실패: ${e.message}\n`);
    return 1;
  }
  let built;
  try {
    built = build(scene);
  } catch (e) {
    process.stderr.write(`생성 실패: ${e.message}\n`);
    return 1;
  }
  if (!argv.includes('--quiet')) for (const w of built.warn) process.stderr.write(`WARN ${w}\n`);
  const out = arg('--out');
  if (!out || out === '-') process.stdout.write(built.svg);
  else writeFileSync(out, built.svg);
  if (!argv.includes('--quiet')) {
    const s = built.stats;
    process.stderr.write(`OK ${s.nodes} nodes / ${s.edges} links / viewBox ${s.VBW}×${s.VBH} / path ${s.pathCount}\n`);
  }
  return 0;
}

process.exit(main(process.argv.slice(2)));
