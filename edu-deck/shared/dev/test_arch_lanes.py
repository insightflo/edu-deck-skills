"""Acceptance: arch_lanes.mjs — 레인(업무 절차) · 시퀀스(호출/응답) 생성기.

[검사 항목]
- 결정성: 같은 모델 → 같은 바이트(2회 실행). 레이아웃·토큰 계산에 시간·난수가 없다는 증거.
- 스키마: draw 예산(12)·루프 방향·분기 완전성·참조 무결 위반은 FAIL(exit 1)로 막는다.
- 토큰: 반려 루프에서 t1 이 두 번(2·9단계) 점등되고, 실행되지 않은 갈래(t4·e07)는
  게이트 단계에서 구조로만 공개된다 — 손plot 없이 계산기 출력만 쓴다는 증거.
- 엔진 의존 0: 산출 조각의 모션 속성은 data-step/only 뿐이고 data-step·data-only 외
  새 속성, script, SMIL, CSS 애니메이션이 없다.
- 문서 순서: loop 흐름이 마지막 path — engine draw() 가 순서대로 12개를 그리므로
  반려선이 마지막에 그려져야 재방문 장면이 자연스럽다.

[실행] cd edu-deck/shared && python3 -m unittest dev.test_arch_lanes -v
[주의] node 18+ 가 PATH 에 있어야 한다(없으면 skip). 저장소에는 아무것도 쓰지 않는다(임시 폴더 사용).
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

S = Path(__file__).resolve().parents[1]      # edu-deck/shared
ROOT = S.parents[1]                          # 저장소 루트
GEN = S / 'scripts' / 'arch_lanes.mjs'
MODELS = ROOT / 'examples' / 'arch-si' / 'models'
B1 = MODELS / 'b1-swimlane.json'
B2 = MODELS / 'b2-sequence.json'
D1 = MODELS / 'd1-astobe.json'
NODE = shutil.which('node')


def run(model_path, out=None, extra=()):
    """생성기 실행 — (returncode, stdout+stderr). out 이 있으면 그 파일에 쓴다."""
    cmd = [NODE, str(GEN), '--in', str(model_path)]
    if out:
        cmd += ['-o', str(out)]
    cmd += list(extra)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return p.returncode, (p.stdout + p.stderr)


@unittest.skipUnless(NODE, 'node 없음')
class ArchLanesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='edudeck-lanes-'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ── 결정성 ──────────────────────────────────────────────────────
    def test_b1_deterministic(self):
        a, b = self.tmp / 'b1a.html', self.tmp / 'b1b.html'
        for f in (a, b):
            code, log = run(B1, f)
            self.assertEqual(code, 0, log)
        self.assertEqual(a.read_bytes(), b.read_bytes(), 'b1: 두 실행 결과가 다르다')

    def test_b2_deterministic(self):
        a, b = self.tmp / 'b2a.html', self.tmp / 'b2b.html'
        for f in (a, b):
            code, log = run(B2, f)
            self.assertEqual(code, 0, log)
        self.assertEqual(a.read_bytes(), b.read_bytes(), 'b2: 두 실행 결과가 다르다')

    # ── 스키마 가드 ─────────────────────────────────────────────────
    def _mutate(self, src, fn, name):
        model = json.loads(Path(src).read_text(encoding='utf-8'))
        fn(model)
        p = self.tmp / name
        p.write_text(json.dumps(model, ensure_ascii=False), encoding='utf-8')
        return p

    def test_draw_budget_rejected(self):
        def add_edges(m):
            m['edges'].append({'id': 'e99', 'from': 't3', 'to': 't6', 'flow': 'seq'})
        p = self._mutate(B1, add_edges, 'over.json')
        code, log = run(p, self.tmp / 'over.html')
        self.assertEqual(code, 1)
        self.assertIn('draw 예산', log)

    def test_loop_must_go_back(self):
        def bad(m):
            for e in m['edges']:
                if e['id'] == 'e12':
                    e['from'], e['to'] = 't1', 't7'
        p = self._mutate(B1, bad, 'loop.json')
        code, log = run(p, self.tmp / 'loop.html')
        self.assertEqual(code, 1)
        self.assertIn('loop 은 앞 열로', log)

    def test_decision_needs_two_branches(self):
        def bad(m):
            m['edges'] = [e for e in m['edges'] if e['id'] != 'e05']
        p = self._mutate(B1, bad, 'dec.json')
        code, log = run(p, self.tmp / 'dec.html')
        self.assertEqual(code, 1)
        self.assertIn('decision 은 나가는 흐름이 2개 이상', log)

    def test_unknown_lane_rejected(self):
        def bad(m):
            m['nodes'][1]['lane'] = 'nope'
        p = self._mutate(B1, bad, 'lane.json')
        code, log = run(p, self.tmp / 'lane.html')
        self.assertEqual(code, 1)
        self.assertIn('알 수 없는 lane', log)

    # ── 토큰: 반려 재방문 ───────────────────────────────────────────
    def test_token_revisit_and_structure(self):
        tok = self.tmp / 'b1-tokens.json'
        code, log = run(B1, self.tmp / 'b1.html', ['--tokens', str(tok)])
        self.assertEqual(code, 0, log)
        t = json.loads(tok.read_text(encoding='utf-8'))
        at = [s['at'] for s in t['steps']]
        self.assertEqual(at[:2], ['s1', 't1'])
        # 반려 루프: t1 이 2단계와 9단계에 다시 점등된다
        self.assertEqual([i + 1 for i, a in enumerate(at) if a == 't1'], [2, 9])
        self.assertTrue(t['route'][-1]['to'] == 'e1')
        # 실행되지 않은 갈래(t4)는 게이트 단계에서 구조로 공개된다
        self.assertIn('t4', t['nodeStep'])
        self.assertEqual(t['nodeStep']['t4'], t['nodeStep']['g1'])
        # loop 흐름은 재방문 단계에 켜진다
        self.assertEqual(t['edgeStep']['e12'], 9)
        # 모든 노드·흐름이 끝 단계까지 공개된다
        self.assertEqual(set(t['nodeStep']), {n['id'] for n in json.loads(B1.read_text())['nodes']})
        self.assertEqual(set(t['edgeStep']), {e['id'] for e in json.loads(B1.read_text())['edges']})

    # ── 엔진 의존 0 ─────────────────────────────────────────────────
    def test_only_engine_attributes(self):
        for src in (B1, B2, D1):
            out = self.tmp / (src.stem + '.html')
            code, log = run(src, out)
            self.assertEqual(code, 0, log)
            html = out.read_text(encoding='utf-8')
            attrs = set(re.findall(r'\bdata-[a-z-]+', html))
            self.assertTrue(attrs <= {'data-archetype', 'data-step', 'data-only', 'data-until'}, f'{src.name}: 예상 밖 속성 {attrs}')
            for bad in ('<script', '<animate', '@keyframes', 'data-fx', 'requestAnimationFrame'):
                self.assertNotIn(bad, html, f'{src.name}: {bad} 발견')

    def test_loop_is_last_path(self):
        out = self.tmp / 'b1-order.html'
        code, log = run(B1, out)
        self.assertEqual(code, 0, log)
        paths = re.findall(r'<path class="(k-ln-[bo])"[^>]*', out.read_text(encoding='utf-8'))
        self.assertEqual(len(paths), 12, 'path 는 링크 수와 같아야 한다(장식 path 금지)')
        self.assertEqual(paths[-1], 'k-ln-o', 'loop(점선) 흐름이 마지막 path 여야 한다')
        self.assertEqual(paths.count('k-ln-o'), 1)

    def test_only_one_path_per_edge(self):
        out = self.tmp / 'b1-paths.html'
        run(B1, out)
        html = out.read_text(encoding='utf-8')
        self.assertEqual(html.count('<path '), 12, '장식에 path 를 쓰면 draw 예산이 줄어든다')

    # ── 시퀀스 모드 ─────────────────────────────────────────────────
    def test_sequence_messages_and_kinds(self):
        out = self.tmp / 'b2.html'
        code, log = run(B2, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertEqual(html.count('<path '), 8, '메시지 1개 = path 1개')
        replies = re.findall(r'<path class="k-ln-g"[^>]*stroke-dasharray:10 8', html)
        self.assertEqual(len(replies), 4, '응답(reply) 4개만 점선 path — 범례는 polyline')
        self.assertEqual(html.count('data-step='), 8 + 1 + 4, 'data-step = 메시지 8 + 헤더·생명선 그룹 1 + 활성 막대 4')
        # 생명선은 polyline(장식) — path 가 아니다
        self.assertGreaterEqual(html.count('class="k-ln-g" points='), 4)

    # ── 대조(compare) 모드 ─────────────────────────────────────────
    def test_compare_deterministic(self):
        a, b = self.tmp / 'd1a.html', self.tmp / 'd1b.html'
        for f in (a, b):
            code, log = run(D1, f)
            self.assertEqual(code, 0, log)
        self.assertEqual(a.read_bytes(), b.read_bytes(), 'd1: 두 실행 결과가 다르다')

    def test_compare_four_states(self):
        out = self.tmp / 'd1.html'
        code, log = run(D1, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        for word in ('유지', '신규', '변경', '제거'):
            self.assertIn(f'>{word}</text>', html, f'범례에 {word} 없음')
        # 제거 = 1단계까지 원형, 2단계부터 흐린 취소선 카드
        self.assertIn('data-until="1"', html)
        self.assertIn('>제거</text>', html)
        # 변경 = 3단계까지 옛 모습, 4단계에 새 모습
        self.assertIn('data-until="3"', html)
        self.assertIn('>변경</text>', html)
        # 위치 아이덴티티: 같은 시스템이 한 좌표에 두 번 그려지지 않는다(상태 교체는 data-until/step 쌍)
        self.assertEqual(html.count('>단일 WAS</text>'), 1, '변경 전 모습은 한 번만')
        self.assertEqual(html.count('>WAS-1</text>'), 1, '변경 후 모습은 한 번만')

    def test_compare_rejects_unknown_state(self):
        def bad(m):
            m['nodes'][0]['change'] = 'maybe'
        p = self._mutate(D1, bad, 'cmp.json')
        code, log = run(p, self.tmp / 'cmp.html')
        self.assertEqual(code, 1)
        self.assertIn('change 는 keep|new|change|remove', log)

    def test_sequence_unknown_actor_rejected(self):
        def bad(m):
            m['messages'][0]['to'] = 'ghost'
        p = self._mutate(B2, bad, 'seq.json')
        code, log = run(p, self.tmp / 'seq.html')
        self.assertEqual(code, 1)
        self.assertIn('알 수 없는 액터', log)

    # ── 시나리오 키 계약 ────────────────────────────────────────────
    def test_scenario_bad_branch_key_rejected(self):
        # 게이트 g1 의 나가는 갈래는 A|B 뿐 — 'X' 는 조용한 대체 없이 명시 오류
        def bad(m):
            m['scenario']['g1'] = ['X']
        p = self._mutate(B1, bad, 'sckey.json')
        code, log = run(p, self.tmp / 'sckey.html')
        self.assertEqual(code, 1)
        self.assertIn('g1', log)
        self.assertIn('X', log)
        self.assertIn('branch', log)

    def test_scenario_key_exhaustion_rejected(self):
        # g2 는 반려 루프로 두 번 방문 — 키 하나면 두 번째 방문에서 소진
        def bad(m):
            m['scenario']['g2'] = ['R']
        p = self._mutate(B1, bad, 'scex.json')
        code, log = run(p, self.tmp / 'scex.html')
        self.assertEqual(code, 1)
        self.assertIn('분기키 소진', log)
        self.assertIn('g2', log)

    def test_scenario_cycle_rejected(self):
        # 반려만 계속 고르는 시나리오 — end 에 도달하지 못하고 40회 상한에 걸린다
        # (g1 도 매 순환마다 재방문되므로 키를 충분히 줘 소진 오류가 먼저 나지 않게 한다)
        def bad(m):
            m['scenario']['g1'] = ['A'] * 30
            m['scenario']['g2'] = ['R'] * 30
        p = self._mutate(B1, bad, 'sccyc.json')
        code, log = run(p, self.tmp / 'sccyc.html')
        self.assertEqual(code, 1)
        self.assertIn('end 노드에 도달하지 못했다', log)


if __name__ == '__main__':
    unittest.main()
