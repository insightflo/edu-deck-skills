#!/usr/bin/env python3
"""P0-1 색 대비 자동 검사 단위 시험: 토큰 매트릭스·sRGB 합성·CLI.

[목적] check_deck.py 에 추가한 토큰 대비 매트릭스(hex·var()·color-mix 해석, WCAG 상대 휘도·
       비율 계산, 기본+8팩 전수 채점, --contrast-matrix 진입점)를 데이터로 검증한다.
[입력] shared/assets/css/tokens.css 원본(읽기 전용)과 인라인 문자열.
[출력] 없음(단정문). 실패는 계산 오류이거나 tokens.css 위반이다.
[연결] check_deck.py --contrast-matrix --matrix-dir 이 같은 함수들을 쓴다.
[주의] P0-1 신규 파일이다. 기존 테스트 파일은 수정하지 않는다(병렬 작업 소유권 존중).
"""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / 'scripts'))
checker = importlib.import_module('check_deck')

TOKENS = SHARED / 'assets' / 'css' / 'tokens.css'


class TestColorMath(unittest.TestCase):
    """WCAG 상대 휘도·비율·sRGB 합성의 산수가 표준 값과 일치하는지."""

    def test_hex_parsing(self):
        self.assertEqual(checker.hex_to_rgb('#202b32'), (32, 43, 50))
        self.assertEqual(checker.hex_to_rgb('#FFFDF8'), (255, 253, 248))
        self.assertEqual(checker.hex_to_rgb('#abc'), (170, 187, 204))  # 3자리 축약
        self.assertIsNone(checker.hex_to_rgb('202b32'))
        self.assertIsNone(checker.hex_to_rgb('#12g345'))

    def test_luminance_extremes(self):
        self.assertAlmostEqual(checker.rel_luminance((255, 255, 255)), 1.0, places=6)
        self.assertAlmostEqual(checker.rel_luminance((0, 0, 0)), 0.0, places=6)

    def test_contrast_black_white_is_21(self):
        self.assertAlmostEqual(checker.contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0, places=6)

    def test_blend_over_opaque_background(self):
        self.assertEqual(checker.blend((0, 0, 0), (100, 100, 100), 0.0), (100.0, 100.0, 100.0))
        self.assertEqual(checker.blend((200, 100, 0), (100, 100, 100), 1.0), (200.0, 100.0, 0.0))
        self.assertEqual(checker.blend((100, 100, 100), (0, 0, 0), 0.25), (25.0, 25.0, 25.0))


class TestColorValueResolution(unittest.TestCase):
    """tokens.css 의 값 문법(hex, var() 참조, color-mix)을 sRGB 단색으로 푸는지."""

    ENV = {'--accent': '#a54716', '--accent-text': '#873912', '--paper': '#fffdf8',
           '--accent-deep': 'var(--accent-text)',
           '--accent-soft': 'color-mix(in srgb,var(--accent) 8%,var(--paper))'}

    def test_plain_hex(self):
        self.assertEqual(checker.parse_color_value('#a54716', self.ENV), (165, 71, 22))

    def test_var_reference_resolves(self):
        self.assertEqual(checker.parse_color_value('var(--accent)', self.ENV), (165, 71, 22))

    def test_var_chain_resolves(self):
        self.assertEqual(checker.parse_color_value('var(--accent-deep)', self.ENV), (135, 57, 18))

    def test_color_mix_blends_in_srgb(self):
        got = checker.parse_color_value('var(--accent-soft)', self.ENV)
        want = checker.blend((165, 71, 22), (255, 253, 248), 0.08)
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, places=4)

    def test_unknown_token_returns_none(self):
        self.assertIsNone(checker.parse_color_value('var(--missing)', self.ENV))
        self.assertIsNone(checker.parse_color_value('red', self.ENV))


class TestTokensParsing(unittest.TestCase):
    """실제 tokens.css 에서 15 의미 역할과 8팩 오버라이드를 읽어 내는지."""

    @classmethod
    def setUpClass(cls):
        cls.base, cls.packs = checker.parse_tokens(TOKENS.read_text(encoding='utf-8'))

    def test_fifteen_semantic_roles_present(self):
        for role in ('ink', 'paper', 'light', 'soft', 'line', 'accent', 'accent-text', 'accent-light',
                     'blue', 'blue-text', 'blue-soft', 'success', 'danger', 'muted', 'chip'):
            self.assertIn(role, self.base, f'--{role} 가 :root 에 없습니다')

    def test_eight_packs_with_four_overrides(self):
        self.assertEqual(set(self.packs), set(checker.PACK_ORDER))
        for pack, overrides in self.packs.items():
            self.assertEqual(set(overrides), {'accent', 'accent-text', 'paper', 'light'},
                             f'{pack} 팩 오버라이드 키가 다릅니다')

    def test_pack_paper_differs_from_base(self):
        self.assertNotEqual(self.packs['atlas']['paper'], self.base['paper'])


class TestMatrix(unittest.TestCase):
    """기본+8팩 × 쌍 목록 전수 채점 매트릭스의 구조와 판정."""

    @classmethod
    def setUpClass(cls):
        cls.base, cls.packs = checker.parse_tokens(TOKENS.read_text(encoding='utf-8'))
        cls.rows = checker.build_matrix(cls.base, cls.packs)

    def test_matrix_covers_base_plus_eight_packs(self):
        self.assertEqual({r['pack'] for r in self.rows}, {'base'} | set(checker.PACK_ORDER))

    def test_every_pack_scores_every_pair_row(self):
        by_pack = {}
        for r in self.rows:
            by_pack.setdefault(r['pack'], set()).add(r['row'])
        want = {row[0] for row in checker.MATRIX_ROWS}
        for pack, rows in by_pack.items():
            self.assertEqual(rows, want, f'{pack} 팩의 채점 행이 빠졌습니다')

    def test_pair_list_matches_directive(self):
        keys = [row[0] for row in checker.MATRIX_ROWS]
        for required in ('body-ink', 'body-soft', 'accent-text-small', 'accent-text-large',
                         'accent-large', 'blue-text-body', 'blue-text-on-blue-soft', 'muted-on-dark',
                         'success-on-paper', 'danger-on-paper', 'success-on-light', 'danger-on-light'):
            self.assertIn(required, keys)

    def test_thresholds_follow_body_large_and_boundary_rules(self):
        needs = {row[0]: row[3] for row in checker.MATRIX_ROWS}
        self.assertEqual(needs['body-ink'], 4.5)
        self.assertEqual(needs['accent-large'], 3.0)
        self.assertEqual(needs['accent-text-large'], 3.0)
        self.assertEqual(needs['muted-on-dark'], 3.0)

    def test_all_ratios_positive_and_rounded(self):
        for r in self.rows:
            self.assertIsInstance(r['ratio'], float)
            self.assertGreater(r['ratio'], 1.0)
            self.assertEqual(r['ratio'], round(r['ratio'], 2))

    def test_pack_independent_rows_are_identical_across_packs(self):
        """muted/accent-light 은 ink 면(팩 오버라이드 없음) 위라 팩 간 값이 같아야 한다."""
        for key in ('muted-on-dark', 'accent-light-on-dark'):
            values = {r['ratio'] for r in self.rows if r['row'] == key}
            self.assertEqual(len(values), 1, f'{key} 행이 팩마다 다릅니다: {values}')

    def test_current_tokens_pass_every_cell(self):
        """납품 기준: 현재 tokens.css 로 매트릭스 전 셀 통과(위반은 tokens.css 수정으로 해소)."""
        fails = [f"{r['pack']}/{r['row']} {r['ratio']}:1 < {r['need']}" for r in self.rows if not r['pass']]
        self.assertEqual(fails, [])


class TestContrastMatrixCLI(unittest.TestCase):
    """--contrast-matrix 진입점: 종료 코드 0, 수치표 md/json 생성."""

    def test_cli_writes_tables_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'evidence'
            code = checker.contrast_matrix_main(SimpleNamespace(tokens=str(TOKENS), matrix_dir=str(out)))
            self.assertEqual(code, 0)
            data = json.loads((out / 'matrix-table.json').read_text(encoding='utf-8'))
            self.assertGreater(len(data['rows']), 100)  # 9팩 × 14행 = 126
            self.assertTrue(all('pass' in r and 'ratio' in r for r in data['rows']))
            md = (out / 'matrix-table.md').read_text(encoding='utf-8')
            self.assertIn('| 팩 |', md)
            self.assertIn('base', md)
            for pack in checker.PACK_ORDER:
                self.assertIn(pack, md)

    def test_cli_fails_on_low_contrast_tokens(self):
        """위반이 있으면 ERROR 로 보고하고 종료 코드 1(수정 의무가 있는 방향으로만 신호)."""
        text = TOKENS.read_text(encoding='utf-8').replace('--soft:#485660', '--soft:#c7d1d4')
        with tempfile.TemporaryDirectory() as tmp:
            low = Path(tmp) / 'low.css'
            low.write_text(text, encoding='utf-8')
            out = Path(tmp) / 'evidence'
            code = checker.contrast_matrix_main(SimpleNamespace(tokens=str(low), matrix_dir=str(out)))
            self.assertEqual(code, 1)
            md = (out / 'matrix-table.md').read_text(encoding='utf-8')
            self.assertIn('미달', md)


class TestRenderContrastPromotion(unittest.TestCase):
    """렌더 대비 검사가 전 단계로 확대되고 ERROR 로 승격됐는지(소스 수준 확인)."""

    def test_render_js_no_longer_gated_to_final_step(self):
        self.assertNotIn('finalStep && op', checker.RENDER_JS)

    def test_render_js_reports_contrast_as_error(self):
        self.assertIn("sev: 'ERROR', kind: '대비'", checker.RENDER_JS)

    def test_render_js_keeps_opacity_and_window_exceptions(self):
        self.assertIn('op >= 0.6', checker.RENDER_JS)   # WCAG 비활성 표시 예외 유지
        self.assertIn("closest('.win')", checker.RENDER_JS)  # 모형 창 3.0 기준 유지


if __name__ == '__main__':
    unittest.main()
