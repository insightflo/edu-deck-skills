#!/usr/bin/env python3
"""pack_router.py 표준 라이브러리 테스트.

확인하는 계약: 결정성, 주제별 다양성, 후보 3종의 디자인 중복 없음, 신호 우선,
--recent 감점, --seed 변주, 잘못된 입력 거부, 신호어 표와 DESIGNS/FLOWS 일치.
"""
import json
from pathlib import Path
import subprocess
import sys
import unittest

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / 'scripts'))
import pack_router  # noqa: E402
from resource_packs import DESIGNS, FLOWS  # noqa: E402

TOPICS = [
    '비와 비율 학습지', '물질의 상태 변화 단원 퀴즈', '개인정보 보호 기본',
    '폭염 작업 안전', '재무제표 읽는 법', '신입 온보딩', '독서 토론 입문', '고객 응대 사례 판단',
]


class RouterContract(unittest.TestCase):
    def test_signal_tables_match_pack_ids(self):
        self.assertEqual(set(pack_router.DESIGN_SIGNALS), set(DESIGNS))
        self.assertEqual(set(pack_router.FLOW_SIGNALS), set(FLOWS))

    def test_deterministic_for_same_input(self):
        a = pack_router.route('개인정보 보호 기본', audience='일반 직원')
        b = pack_router.route('개인정보 보호 기본', audience='일반 직원')
        self.assertEqual(a, b)

    def test_three_distinct_designs_and_valid_ids(self):
        for title in TOPICS:
            with self.subTest(title=title):
                r = pack_router.route(title)
                designs = [c['design'] for c in r['candidates']]
                self.assertEqual(len(designs), 3)
                self.assertEqual(len(set(designs)), 3)
                self.assertTrue(set(designs) <= set(DESIGNS))
                self.assertEqual(r['recommend'], designs[0])
                self.assertIn(r['flow'], FLOWS)
                self.assertNotEqual(r['flow'], r['flow_runner_up'])

    def test_topics_do_not_collapse_to_one_pack(self):
        """매번 같은 모양이 나오던 문제의 회귀: 주제 8개의 추천이 최소 4종으로 갈라져야 한다."""
        picks = {pack_router.route(t)['recommend'] for t in TOPICS}
        self.assertGreaterEqual(len(picks), 4, picks)

    def test_signal_beats_jitter(self):
        self.assertEqual(pack_router.route('현장 작업 절차 점검')['recommend'], 'field')
        self.assertEqual(pack_router.route('데이터 통계 지표 보고')['recommend'], 'briefing')
        self.assertEqual(pack_router.route('실험 관찰 가설 검증')['recommend'], 'lab')

    def test_recent_penalty_breaks_repeat_when_signal_is_weak(self):
        """감점은 신호가 약한 주제에서 직전 디자인의 반복을 끊는다."""
        base = pack_router.route('신입 온보딩')
        self.assertTrue(base['weak_signal'])
        demoted = pack_router.route('신입 온보딩', recent=[base['recommend']])
        self.assertNotEqual(demoted['recommend'], base['recommend'])

    def test_strong_signal_survives_recent_penalty(self):
        """강한 신호는 최근 사용 감점보다 우선한다(주제에 맞는 팩을 버리지 않는다)."""
        r = pack_router.route('현장 작업 절차 점검', recent=['field'])
        self.assertEqual(r['recommend'], 'field')
        self.assertIn('최근 사용', r['candidates'][0]['because'])

    def test_seed_changes_weak_signal_order(self):
        orders = {tuple(c['design'] for c in pack_router.route('신입 온보딩', seed=str(s))['candidates'])
                  for s in range(8)}
        self.assertGreater(len(orders), 1)

    def test_weak_signal_flagged_and_explained(self):
        r = pack_router.route('신입 온보딩')
        self.assertTrue(r['weak_signal'])
        self.assertTrue(all('신호어가 약해' in c['because'] for c in r['candidates']))

    def test_rejects_bad_input(self):
        with self.assertRaises(pack_router.RouterError):
            pack_router.route('   ')
        with self.assertRaises(pack_router.RouterError):
            pack_router.route('x', recent=['nope'])

    def test_preview_command_is_shell_safe_and_complete(self):
        r = pack_router.route("O'Reilly 데이터 통계")
        cmd = pack_router.preview_command(r, '/tmp/w')
        self.assertEqual(cmd.count('--pack'), 3)
        self.assertEqual(cmd.count('--because'), 3)
        self.assertIn('--recommend', cmd)
        self.assertIn("O'\"'\"'Reilly", cmd)
        self.assertTrue(cmd.startswith('python3 <solo>/scripts/preview_pack.py make '))

    def test_cli_outputs_json_and_command(self):
        out = subprocess.run(
            [sys.executable, str(SHARED / 'scripts' / 'pack_router.py'),
             '--title', '재무제표 읽는 법', '--emit-command'],
            capture_output=True, text=True, check=True).stdout
        data = json.loads(out.split('\n\n# ')[0])
        self.assertEqual(len(data['candidates']), 3)
        self.assertIn('preview_pack.py make', out)

    def test_cli_rejects_empty_title(self):
        proc = subprocess.run(
            [sys.executable, str(SHARED / 'scripts' / 'pack_router.py'), '--title', ' '],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)


if __name__ == '__main__':
    unittest.main()
