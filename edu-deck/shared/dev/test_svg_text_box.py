#!/usr/bin/env python3
"""SVG 도식 안의 글자가 담고 있는 <rect> 상자 밖으로 나가는 결함의 양성·음성 통제.

양성(넘침 → ERROR), 음성(상자에 맞음·상자 밖에 나란히 그림 → 무결함), 보이지 않는
상자 제외, 가장 작은 상자 우선 규칙을 browser RENDER_JS 로 직접 잰다.
"""
import importlib
import unittest
from pathlib import Path
import sys

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / 'scripts'))
checker = importlib.import_module('check_deck')

TEXT = '가나다라마바사아자차카타파하거너더러머버서'  # 20 글자 — 글꼴 폭과 무관하게 상자를 넘게 만들 길이


def document(content):
    return ('<html><head><style>body{margin:0}.slide{width:1920px;height:1080px;background:white}'
            'svg{font-size:24px}</style></head><body><div id="stage">'
            '<section class="slide"><svg width="1000" height="600" viewBox="0 0 1000 600">'
            + content + '</svg></section></div></body></html>')


class SvgTextBoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise unittest.SkipTest(str(exc))
        cls.pw = sync_playwright().start()
        try:
            cls.browser = checker.launch(cls.pw)
        except RuntimeError as exc:
            cls.pw.stop()
            raise unittest.SkipTest(str(exc))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def findings(self, content):
        page = self.browser.new_page(viewport={'width': 1920, 'height': 1080})
        self.addCleanup(page.close)
        page.set_content(document(content))
        return page.evaluate(checker.RENDER_JS, [0])

    def svg_errors(self, content):
        return [f for f in self.findings(content) if f['kind'] == 'SVG 글자 넘침']

    def test_overflowing_text_in_box_is_error(self):
        # 상자 100..200 안에 앵커(120)를 두고 글자는 200 을 크게 넘긴다 — 결함 보고 사례의 형태
        rows = self.svg_errors('<rect x="100" y="100" width="100" height="80" fill="#dbeafe" stroke="#2563eb"/>'
                               f'<text x="120" y="148">{TEXT}</text>')
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]['sev'], 'ERROR')
        self.assertIn('상자(rect)', rows[0]['msg'])
        self.assertIn('가나다', rows[0]['msg'])

    def test_fitting_text_inside_box_is_clean(self):
        rows = self.svg_errors('<rect x="100" y="100" width="800" height="80" fill="#dbeafe" stroke="#2563eb"/>'
                               f'<text x="150" y="148">{TEXT}</text>')
        self.assertEqual(rows, [])

    def test_text_not_inside_any_rect_is_clean(self):
        # 상자는 글자 아래에 있고 앵커점이 상자에 닿지 않으면 나란히 그린 것이라 검사하지 않는다
        rows = self.svg_errors('<rect x="100" y="400" width="800" height="80" fill="#dbeafe" stroke="#2563eb"/>'
                               f'<text x="150" y="100">{TEXT}</text>')
        self.assertEqual(rows, [])

    def test_middle_anchor_overflow_is_error(self):
        # 실제 결함 사례와 같은 text-anchor:middle 형태 — 상자 370..660, 앵커 462
        rows = self.svg_errors('<rect x="370" y="100" width="290" height="80" fill="#dbeafe" stroke="#2563eb"/>'
                               f'<text x="462" y="148" text-anchor="middle">{TEXT}</text>')
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]['sev'], 'ERROR')

    def test_end_anchor_overflow_is_error(self):
        rows = self.svg_errors('<rect x="100" y="100" width="100" height="80" fill="#dbeafe" stroke="#2563eb"/>'
                               f'<text x="200" y="148" text-anchor="end">{TEXT}</text>')
        self.assertEqual(len(rows), 1, rows)

    def test_unpainted_rect_is_not_a_box(self):
        # fill·stroke 가 모두 없는 rect 는 눈에 보이는 상자가 아니므로 글자가 있어도 검사 대상이 아니다
        rows = self.svg_errors('<rect x="100" y="100" width="100" height="80" fill="none" stroke="none"/>'
                               f'<text x="120" y="148">{TEXT}</text>')
        self.assertEqual(rows, [])

    def test_smallest_containing_rect_wins(self):
        # 큰 상자는 넘침이 없어도 앵커를 담는 가장 작은 상자 기준으로 잰다
        rows = self.svg_errors('<rect x="50" y="50" width="900" height="500" fill="none" stroke="#94a3b8"/>'
                               '<rect x="400" y="100" width="100" height="80" fill="#dbeafe" stroke="#2563eb"/>'
                               f'<text x="420" y="148">{TEXT}</text>')
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]['sev'], 'ERROR')

    def test_text_hidden_in_defs_is_not_checked(self):
        rows = self.svg_errors('<defs><text id="d" x="120" y="148">'
                               + TEXT + '</text></defs>'
                               '<rect x="100" y="100" width="100" height="80" fill="#dbeafe" stroke="#2563eb"/>')
        self.assertEqual(rows, [])
        self.assertFalse(self.findings('<rect x="100" y="100" width="100" height="80" fill="#dbeafe" stroke="#2563eb"/>'
                                       f'<text x="120" y="148" aria-hidden="true">{TEXT}</text>'))


if __name__ == '__main__':
    unittest.main()
