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
        # 단일 존 경계(between:[z]) — 라벨은 존 하단(y1) 밖에 있어야 한다
        zid = bounds[0]['between'][0]
        zr = next(z['r'] for z in coords['zones'] if z['id'] == zid)
        self.assertGreater(y_label, zr['y1'],
                           f'경계 라벨 y={y_label} 가 존 하단 {zr["y1"]} 안에 있다(정규화 미적용 버그 회귀)')


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


class DeterminismTest(unittest.TestCase):
    def test_same_model_same_bytes(self):
        model = m(edges=[{'from': 'a', 'to': 'b', 'label': '1', 'kind': 'r'}],
                  zones=[{'id': 'z', 'label': 'Z', 'members': ['a', 'b'], 'kind': 'member'}])
        self.assertEqual(gen(model), gen(model))


if __name__ == '__main__':
    unittest.main()
