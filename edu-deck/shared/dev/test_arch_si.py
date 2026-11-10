#!/usr/bin/env python3
"""arch_layout.mjs SI 확장 옵션 계약 시험 (SI 실무형 구성도 Step 5).

[목적] 생성기 확장 7종을 잠근다 —
   ① edges[].kind:'r'  → k-ln-g + stroke-dasharray 8 8 + marker-end ah-open
   ② zones[].kind      → member 는 k-paper 면색 띠 / trust·미지정은 k-frame 점선
   ③ zones[].between   → 두 존 사이 점선 polyline 경계 + 라벨
   ④ zones[].labelPos  → top|bottom 라벨 방향
   ⑤ 범례 자동 유도    → legend 생략 + 사용 kind 2종 이상이면 자동 생성
   ⑥ edges[].aux:true  → data-step 없는 정적 보조선, draw 예산(12) 밖
   ⑦ layout.chipAvoid  → 옵트인 라벨 칩 상호 충돌 회피
   + ah-open 마커가 assets/icons/extra.svg 에 존재
   + 결정성: 같은 모델 두 번 생성은 바이트 동일
[입력] 인라인 모델 JSON을 /tmp 에 생성 → node 로 생성기 실행 → svg 문자열 검사.
[출력] 없음(단정문).
"""
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

S = Path(__file__).resolve().parents[1]
GEN = S / 'scripts' / 'arch_layout.mjs'
EXTRA = S / 'assets/icons' / 'extra.svg'

BASE = {
    'title': '시험', 'small': 's', 'ariaLabel': '시험용',
    'layout': {'dir': 'LR', 'ranksep': 40, 'nodesep': 30},
    'steps': {'zones': 1, 'nodes': 2, 'edges': 3},
    'nodes': [
        {'id': 'a', 'name': 'A', 'icon': 'i-globe', 'w': 120, 'h': 96},
        {'id': 'b', 'name': 'B', 'icon': 'i-server', 'w': 120, 'h': 96},
        {'id': 'c', 'name': 'C', 'icon': 'i-db', 'w': 120, 'h': 96},
        {'id': 'd', 'name': 'D', 'icon': 'i-doc', 'w': 120, 'h': 96},
    ],
    'edges': [],
    'zones': [],
    'notes': '시험용 장입니다. 생성기 확장 옵션만 검증하며 실제 시스템과 무관합니다.',
}


def gen(model):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(model, f, ensure_ascii=False)
        mpath = f.name
    out = Path(mpath).with_suffix('.html')
    r = subprocess.run(['node', str(GEN), mpath, '-o', str(out), '--quiet'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f'생성 실패: {r.stderr.strip() or r.stdout.strip()}')
    return out.read_text(encoding='utf-8')


def m(**kw):
    d = json.loads(json.dumps(BASE))
    d.update(kw)
    return d


class MarkerTest(unittest.TestCase):
    def test_extra_svg_has_open_marker(self):
        svg = EXTRA.read_text(encoding='utf-8')
        self.assertIn('id="ah-open"', svg)


class KindRTest(unittest.TestCase):
    def test_response_edge_dashed_open_head(self):
        svg = gen(m(edges=[{'from': 'a', 'to': 'b', 'label': '응답', 'kind': 'r'}]))
        self.assertIn('stroke-dasharray="8 8"', svg)
        self.assertIn('marker-end="url(#ah-open)"', svg)
        self.assertIn('k-ln-g', svg)


class ZoneKindTest(unittest.TestCase):
    def test_member_paper_trust_frame(self):
        svg = gen(m(zones=[
            {'id': 'z1', 'label': '소속', 'members': ['a', 'b'], 'kind': 'member'},
            {'id': 'z2', 'label': '경계', 'members': ['c', 'd']},
        ]))
        self.assertIn('k-paper', svg.split('소속')[0])
        self.assertIn('k-frame', svg.split('경계')[0])


class BetweenTest(unittest.TestCase):
    def test_boundary_polyline_and_label(self):
        svg = gen(m(zones=[
            {'id': 'z1', 'label': '내부', 'members': ['a', 'b'], 'kind': 'member'},
            {'id': 'z2', 'label': '외부', 'members': ['c', 'd'], 'kind': 'member'},
            {'id': 'bt', 'label': '신뢰 경계', 'between': ['z1', 'z2']},
        ]))
        self.assertIn('stroke-dasharray="11 9"', svg)
        self.assertIn('신뢰 경계', svg)


class LabelPosTest(unittest.TestCase):
    def test_bottom_label_moves_down(self):
        # franja inferior libre → labelPos bottom se respeta
        nodes2 = [n for n in BASE['nodes'] if n['id'] in ('a', 'b')]
        def ly(pos):
            svg = gen(m(nodes=nodes2,
                        zones=[{'id': 'z', 'label': 'L', 'members': ['a', 'b'],
                                'kind': 'member', 'labelPos': pos}]))
            for seg in svg.split('<text'):
                if 'L</text>' in seg:
                    return float(seg.split('y="')[1].split('"')[0])
            raise AssertionError('존 라벨 없음')
        self.assertGreater(ly('bottom'), ly('top'))

    def test_blocked_bottom_falls_back_to_top_strip(self):
        # nodos ajenos invaden la franja inferior → la etiqueta cae en la franja libre
        def ly(pos):
            svg = gen(m(zones=[{'id': 'z', 'label': 'L', 'members': ['a', 'b'],
                                'kind': 'member', 'labelPos': pos}]))
            for seg in svg.split('<text'):
                if 'L</text>' in seg:
                    return float(seg.split('y="')[1].split('"')[0])
            raise AssertionError('존 라벨 없음')
        self.assertEqual(ly('bottom'), ly('top'))


class AutoLegendTest(unittest.TestCase):
    def test_legend_synthesized_from_used_kinds(self):
        svg = gen(m(edges=[
            {'from': 'a', 'to': 'b', 'label': '1', 'kind': 'b'},
            {'from': 'a', 'to': 'c', 'label': '2', 'kind': 'r'},
        ]))
        self.assertIn('동기 호출', svg)
        self.assertIn('응답', svg)

    def test_explicit_legend_wins(self):
        svg = gen(m(edges=[{'from': 'a', 'to': 'b', 'label': '1', 'kind': 'b'}],
                    legend=[{'kind': 'b', 'label': '커스텀'}]))
        self.assertIn('커스텀', svg)
        self.assertNotIn('동기 호출', svg)


class AuxTest(unittest.TestCase):
    def test_aux_edge_has_no_step_and_skips_budget(self):
        edges = [{'from': 'a', 'to': 'b', 'label': f'e{i}', 'kind': 'b'} for i in range(12)]
        edges.append({'from': 'b', 'to': 'a', 'label': '보조', 'kind': 'g', 'aux': True})
        svg = gen(m(edges=edges))                      # 13개여도 aux 는 예산 밖 → 통과
        aux_seg = svg.split('보조')[0].rsplit('<g', 1)[1]
        self.assertNotIn('data-step', aux_seg.split('>', 1)[0])


SI_MODELS = S.parents[1] / 'examples' / 'arch-si' / 'models'


def gen_with_coords(model_path):
    """실제 모델 파일로 생성기 실행 — (svg, coords dict)."""
    out = Path(tempfile.mkdtemp(prefix='edudeck-si-')) / 'out.html'
    cpath = out.with_suffix('.coords.json')
    r = subprocess.run(['node', str(GEN), str(model_path), '-o', str(out),
                        '--coords', str(cpath), '--quiet'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f'생성 실패: {r.stderr.strip() or r.stdout.strip()}')
    return out.read_text(encoding='utf-8'), json.loads(cpath.read_text(encoding='utf-8'))


def seg_rect(p, q, r):
    """선분 p→q 가 사각형 r 과 교차하면 True(내부 포함 또는 변 교차)."""
    def inside(v):
        return r['x0'] < v['x'] < r['x1'] and r['y0'] < v['y'] < r['y1']
    if inside(p) or inside(q):
        return True
    def ccw(a, b, c):
        return (b['x'] - a['x']) * (c['y'] - a['y']) - (b['y'] - a['y']) * (c['x'] - a['x'])
    def crosses(a, b, c, d):
        return ccw(a, b, c) * ccw(a, b, d) < 0 and ccw(c, d, a) * ccw(c, d, b) < 0
    cs = [{'x': r['x0'], 'y': r['y0']}, {'x': r['x1'], 'y': r['y0']},
          {'x': r['x1'], 'y': r['y1']}, {'x': r['x0'], 'y': r['y1']}]
    return any(crosses(p, q, cs[i], cs[(i + 1) % 4]) for i in range(4))


class AuxRouteTest(unittest.TestCase):
    """aux 보조선 직교 우회 — 전 구간이 노드 사각형과 무교차여야 한다."""

    def _aux_pts(self, name):
        mp = SI_MODELS / f'{name}.json'
        if not mp.exists():
            self.skipTest(f'{name} 모델 없음')
        model = json.loads(mp.read_text(encoding='utf-8'))
        auxs = [(e['from'], e['to']) for e in model['edges'] if e.get('aux')]
        if not auxs:
            self.skipTest(f'{name}: aux 엣지 없음')
        _, coords = gen_with_coords(mp)
        return model, coords, auxs

    def test_aux_segments_clear_node_rects(self):
        for name in ('a1b-detail', 'c3-dr'):
            _, coords, auxs = self._aux_pts(name)
            rects = {nid: {'x0': nn['x'] - nn['w'] / 2, 'x1': nn['x'] + nn['w'] / 2,
                           'y0': nn['y'] - nn['h'] / 2, 'y1': nn['y'] + nn['h'] / 2}
                     for nid, nn in coords['nodes'].items()}
            for a, b in auxs:
                pts = next(e['pts'] for e in coords['edges'] if e['a'] == a and e['b'] == b)
                for i in range(1, len(pts)):
                    for nid, r in rects.items():
                        if nid in (a, b):
                            continue
                        self.assertFalse(
                            seg_rect(pts[i - 1], pts[i], r),
                            f'{name}: aux {a}->{b} 세그먼트 {i}이 노드 {nid} 와 교차')

    def test_aux_models_deterministic(self):
        for name in ('a1b-detail', 'c3-dr'):
            mp = SI_MODELS / f'{name}.json'
            if not mp.exists():
                self.skipTest(f'{name} 모델 없음')
            a = gen_with_coords(mp)[0]
            b = gen_with_coords(mp)[0]
            self.assertEqual(a, b, f'{name}: 두 실행 결과가 다르다')


class BoundaryLabelTest(unittest.TestCase):
    """경계 라벨 기본값(bottom) — 정규화 좌표로 존 사각형 하단 밖에 놓여야 한다."""

    def test_bottom_label_below_zone(self):
        mp = SI_MODELS / 'a1a-overview.json'
        if not mp.exists():
            self.skipTest('a1a 모델 없음')
        svg, coords = gen_with_coords(mp)
        model = json.loads(mp.read_text(encoding='utf-8'))
        bounds = [z for z in model['zones'] if z.get('between')]
        if not bounds:
            self.skipTest('a1a: 경계 존 없음')
        # 경계 라벨(신뢰 경계)의 정규화 y 추출
        label = bounds[0].get('label', '신뢰 경계')
        m2 = re.search(r'<text[^>]*y="([\d.]+)"[^>]*>' + re.escape(label) + r'</text>', svg)
        self.assertIsNotNone(m2, f'경계 라벨 "{label}" 텍스트를 찾지 못했다')
        y_label = float(m2.group(1))
        zrs = [next(z['r'] for z in coords['zones'] if z['id'] == zid) for zid in bounds[0]['between']]
        # 경계선 방향 판별 — 수직선(좌우 분리)이면 라벨은 두 존 위(선 상단)에,
        # 수평선(상하 분리)이면 첫 존 하단 밖에 놓인다. 둘 다 존 사각형 밖이 계약이다.
        pline = re.search(r'<polyline points="([^"]+)"[^>]*stroke-dasharray="11 9"', svg)
        self.assertIsNotNone(pline, '경계 polyline 없음')
        pts = [tuple(map(float, p.split(','))) for p in pline.group(1).split()]
        vertical = abs(pts[-1][0] - pts[0][0]) < 2
        if vertical:
            self.assertLess(y_label, min(z['y0'] for z in zrs),
                            f'수직 경계 라벨 y={y_label} 가 존 상단 안쪽에 있다')
        else:
            self.assertGreater(y_label, zrs[0]['y1'],
                               f'경계 라벨 y={y_label} 가 존 하단 {zrs[0]["y1"]} 안에 있다(정규화 미적용 버그 회귀)')


class FallbackChipTest(unittest.TestCase):
    """labelPos fallback 도 placedChips 등록 — 이후 칩이 fallback 칩과 겹치면 안 된다."""

    def test_chips_pairwise_disjoint_on_fallback_models(self):
        # fallback 이 실제 발생하는 chipAvoid 모델(a1b:1, c3:2)의 라벨 칩 무겹침 회귀 가드.
        # (b3-batch 는 HEAD 시점부터 칩 겹침 1건이 선재 — 별도 과제라 여기선 제외)
        import itertools
        for name in ('a1b-detail', 'c3-dr'):
            mp = SI_MODELS / f'{name}.json'
            if not mp.exists():
                self.skipTest(f'{name} 모델 없음')
            svg, _ = gen_with_coords(mp)
            chips = [tuple(map(float, g)) for g in
                     re.findall(r'<rect class="k-paper" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="36"', svg)]
            def ov(a, b):
                return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + 36 and a[1] + 36 > b[1]
            bad = [(a, b) for a, b in itertools.combinations(chips, 2) if ov(a, b)]
            self.assertFalse(bad, f'{name}: 라벨 칩 겹침 {len(bad)}건')


class ChipAvoidTest(unittest.TestCase):
    def test_avoid_keeps_demo_chips_separated(self):
        # 회피가 상시 동작 — 기존 데모 모델에서 칩 겹침이 없어야 한다
        demo = S.parents[1] / 'examples' / 'arch-demo' / 'models' / '01-microservices.json'
        if not demo.exists():
            self.skipTest('기존 데모 모델 없음')
        svg = gen(json.loads(demo.read_text(encoding='utf-8')))
        chips = [tuple(map(float, g)) for g in
                 re.findall(r'<rect class="k-paper" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="36"', svg)]
        import itertools
        def ov(a, b):
            return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + 36 and a[1] + 36 > b[1]
        bad = [(a, b) for a, b in itertools.combinations(chips, 2) if ov(a, b)]
        self.assertFalse(bad, f'라벨 칩 겹침 {len(bad)}건')


class OrthoRouteTest(unittest.TestCase):
    """직교 배선 계약 — 방출된 path·line·polyline 세그먼트에 사선이 없어야 한다."""

    def test_no_diagonal_segments(self):
        svg = gen(m(edges=[
            {'from': 'a', 'to': 'b'}, {'from': 'a', 'to': 'c'},
            {'from': 'b', 'to': 'd'}, {'from': 'd', 'to': 'a', 'aux': True},
        ]))
        body = svg[svg.find('<svg'):svg.find('</svg>')]
        diag = 0
        for d in re.findall(r'<path[^>]*d="([^"]+)"', body):
            pts = [(float(a), float(b)) for a, b in re.findall(r'[MLQ]\s*([\d.\-]+)\s+([\d.\-]+)', d)]
            diag += sum(1 for i in range(1, len(pts))
                        if abs(pts[i][0] - pts[i-1][0]) > 0.5 and abs(pts[i][1] - pts[i-1][1]) > 0.5)
        self.assertEqual(diag, 0, '사선 세그먼트 발견')


class NestedZoneTest(unittest.TestCase):
    """존 중첩은 parent 체인으로 3단계까지 — 4단계는 FAIL."""

    def _zones(self):
        return [
            {'id': 'l1', 'label': 'L1', 'members': [], 'headerStyle': 'solid-navy'},
            {'id': 'l2', 'label': 'L2', 'members': ['a', 'b'], 'parent': 'l1'},
            {'id': 'l3', 'label': 'L3', 'members': ['c'], 'parent': 'l2'},
            {'id': 'l4', 'label': 'L4', 'members': ['d'], 'parent': 'l3'},
        ]

    def test_three_levels_emit(self):
        svg = gen(m(zones=self._zones()[:3]))
        self.assertIn('k-zface', svg)
        self.assertIn('L3', svg)

    def test_fourth_level_fails(self):
        r = subprocess.run(['node', str(GEN), self._tmp(self._zones()), '-o', '/dev/null'],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('중첩', r.stderr)

    @staticmethod
    def _tmp(zones):
        import tempfile, os
        f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(m(zones=zones), f, ensure_ascii=False)
        f.close()
        return f.name


class BusHATest(unittest.TestCase):
    """버스 = 백본 + T-드롭(draw 예산 밖)·from×to 점대점 자동 제거 / HA쌍 = 이중선."""

    def test_bus_trunk_drops_and_dedupe(self):
        svg = gen(m(edges=[{'from': 'a', 'to': 'c'}, {'from': 'b', 'to': 'c'}],
                    buses=[{'id': 'bs', 'from': ['a'], 'to': ['c', 'd']}]))
        self.assertIn('k-bus-trunk', svg)
        body = svg[svg.find('<svg'):svg.find('</svg>')]
        # 백본 1 + from 1개·to 2개 T-드롭 = 4개 polyline
        self.assertEqual(len(re.findall(r'<polyline class="k-bus-', body)), 4)

    def test_ha_pair_double_line(self):
        svg = gen(m(haPairs=[['a', 'b']]))
        self.assertIn('k-hab', svg)
        self.assertGreaterEqual(svg.count('class="k-ha"'), 2)


class MicroTypoTest(unittest.TestCase):
    """마이크로 타이포 계약 — k-t-spec/eq/qty 는 svg.dg 안에서만 12px+ 허용.
    계약 근거는 architecture.md 문서 + check_deck 스코프 규칙 + CSS 크기다."""

    def test_checker_keeps_scoped_rule(self):
        src = (S / 'scripts' / 'check_deck.py').read_text(encoding='utf-8')
        self.assertIn('k-t-(spec|eq|qty)', src)
        self.assertIn('svg.dg', src)

    def test_css_sizes_within_contract(self):
        css = (S / 'assets' / 'css' / 'visual-motion.css').read_text(encoding='utf-8')
        for cls in ('k-t-spec', 'k-t-eq', 'k-t-qty'):
            mt = re.search(rf'\.{cls}\{{[^}}]*font-size:(\d+)px', css)
            self.assertIsNotNone(mt, f'{cls} 크기 정의 없음')
            self.assertTrue(12 <= int(mt.group(1)) <= 16, f'{cls} {mt.group(1)}px — 12~16px 계약 밖')


class IconA11yTest(unittest.TestCase):
    def test_use_icons_aria_hidden(self):
        nodes = [dict(n) for n in BASE['nodes']]
        nodes[0].update(template='equip', icon='i-si-fw')
        svg = gen(m(nodes=nodes, edges=[{'from': 'a', 'to': 'b'}]))
        body = svg[svg.find('<svg'):svg.find('</svg>')]
        uses = re.findall(r'<use\b[^>]*>', body)
        self.assertTrue(uses)
        self.assertTrue(all('aria-hidden="true"' in u for u in uses),
                        'aria-hidden 없는 아이콘 use 발견')


class DeterminismTest(unittest.TestCase):
    def test_same_model_same_bytes(self):
        model = m(edges=[{'from': 'a', 'to': 'b', 'label': '1', 'kind': 'r'}],
                  zones=[{'id': 'z', 'label': 'Z', 'members': ['a', 'b'], 'kind': 'member'}])
        self.assertEqual(gen(model), gen(model))


if __name__ == '__main__':
    unittest.main()
