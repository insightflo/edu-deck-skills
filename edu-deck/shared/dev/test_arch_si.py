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
        def ly(pos):
            svg = gen(m(zones=[{'id': 'z', 'label': 'L', 'members': ['a', 'b'],
                                'kind': 'member', 'labelPos': pos}]))
            for seg in svg.split('<text'):
                if 'L</text>' in seg:
                    return float(seg.split('y="')[1].split('"')[0])
            raise AssertionError('존 라벨 없음')
        self.assertGreater(ly('bottom'), ly('top'))


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


class ChipAvoidTest(unittest.TestCase):
    def test_optin_moves_colliding_chips(self):
        # 실제 칩 충돌이 있는 기존 데모 모델 — chipAvoid 옵트인 시 배치가 달라져야 한다
        demo = S.parents[1] / 'examples' / 'arch-demo' / 'models' / '01-microservices.json'
        if not demo.exists():
            self.skipTest('기존 데모 모델 없음')
        model = json.loads(demo.read_text(encoding='utf-8'))
        off = gen(model)
        on = gen({**model, 'layout': {**model.get('layout', {}), 'chipAvoid': True}})
        self.assertNotEqual(off, on)


class DeterminismTest(unittest.TestCase):
    def test_same_model_same_bytes(self):
        model = m(edges=[{'from': 'a', 'to': 'b', 'label': '1', 'kind': 'r'}],
                  zones=[{'id': 'z', 'label': 'Z', 'members': ['a', 'b'], 'kind': 'member'}])
        self.assertEqual(gen(model), gen(model))


if __name__ == '__main__':
    unittest.main()
