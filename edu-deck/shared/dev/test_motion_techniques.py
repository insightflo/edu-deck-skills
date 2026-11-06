#!/usr/bin/env python3
"""공통 모션 기법 5종 계약 시험 (TASK-motions).

[목적] scatter-gather·slice-reveal·row-mask-rise·weight-wave·rack-focus 가
       ① 채택 스니펫의 저작 속성 계약(data-fx 이름·대상·한도)을 지키고
       ② 정적 모드(인쇄·감속·자습)에서 저작한 최종 DOM 그대로 완결되며
       ③ 미지원 브라우저(clip-path·가변 wght)에서 침묵으로 최종 상태를 보이고
       ④ 화면 발화 후 이탈 시 마스크·글자·필터 잔재 없이 취소된다 — 를 잠근다.
[입력] assets/snippets 5계열 첫 section 으로 /tmp 미니덱 빌드 + 실제 Chromium.
[출력] 없음(단정문).
[주의] 시각적 차이(픽셀·중간 프레임)는 TASK-motions-STATE.md 증거가 맡고,
       이 시험은 계약과 정적 완결만 잠근다.
"""
import re
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build  # noqa: E402
from check_deck import FX_KINDS  # noqa: E402

SNIPPETS = S / 'assets' / 'snippets'
MOTION = (S / 'assets' / 'js' / 'motion.js').read_text(encoding='utf-8')
OUT = Path('/tmp/edudeck-motion-fx')
SRC = OUT / 'src'

TECHNIQUES = ('scatter-gather', 'slice-reveal', 'row-mask-rise',
              'weight-wave', 'rack-focus')

# 채택 계열 -> (스니펫 파일, 아키타입, data-fx 이름, 대상 선택자, 최대 대상 수)
ADOPTIONS = {
    'cover': ('01-cover-center.html', 'scatter-gather', '#cx-typed', 48),
    'agenda': ('02-agenda.html', 'row-mask-rise', '.rm-col', 12),
    'statement': ('17-statement.html', 'weight-wave', '.t2', 48),
    'before-after': ('20-before-after.html', 'slice-reveal', '.win', 12),
    'check': ('30-check.html', 'rack-focus', '.chk-why', 12),
}

NOTES = ('시험 장의 발표 노트입니다. 각 단계의 드러남과 최종 상태를 확인하는 '
         '안내 문구이며 자습 모드에서는 이 화면 그대로 읽습니다.')


def first_section(stem):
    soup = BeautifulSoup(
        (SNIPPETS / stem).read_text(encoding='utf-8'), 'html.parser')
    return str(soup.select_one('section.slide'))


def build_mini():
    SRC.mkdir(parents=True, exist_ok=True)
    order = ['01-cover-center.html', '02-agenda.html', '17-statement.html',
             '20-before-after.html', '30-check.html']
    srcs = []
    for i, name in enumerate(order):
        p = SRC / f'{i:02d}-{name}'
        p.write_text(first_section(name), encoding='utf-8')
        srcs.append(p)
    html = OUT / 'deck.html'
    build('모션 기법 시험', srcs, [S / 'assets/css'],
          [S / 'assets/icons'], html)
    return html


class AttributeContractTest(unittest.TestCase):
    """저작 속성 계약: 채택처·이름·한도·엔진 등록."""

    def test_adopted_snippets_carry_declared_fx(self):
        for arch, (stem, fx, sel, cap) in ADOPTIONS.items():
            text = (SNIPPETS / stem).read_text(encoding='utf-8')
            soup = BeautifulSoup(text, 'html.parser')
            with self.subTest(arch=arch):
                hits = soup.select(f'{sel}[data-fx="{fx}"]')
                self.assertTrue(hits, f'{stem}: {sel} 에 data-fx="{fx}" 없음')
                for el in hits:
                    self.assertEqual(el.get('data-archetype'), None,
                                     '효과는 요소 속성 — 계열 속성과 혼합 금지')
            # 대상 한도: 변형(섹션)마다 해당 속성 요소 수가 계약 상한 이하
            for sec in soup.select('section.slide'):
                with self.subTest(arch=arch, scope='limit',
                                  variant=sec.get('data-variant')):
                    self.assertLessEqual(len(sec.select(f'[data-fx="{fx}"]')),
                                         cap,
                                         f'{stem}: 대상 {cap}개 초과')

    def test_engine_registers_five_techniques(self):
        for name in TECHNIQUES:
            with self.subTest(fx=name):
                self.assertIn(f"'{name}'", MOTION, 'motion.js FX 표 미등록')
                self.assertIn(name, FX_KINDS, 'check_deck FX_KINDS 미등록')
        # 새 시그니처 이름 금지: 실행 이름 수는 30 유지
        names = set(re.findall(r"name:'([a-z-]+)'", MOTION))
        self.assertEqual(len(names), 30,
                         f'실행 이름 {len(names)}종 — 30종 체계 변경 감지: {sorted(names)}')

    def test_no_forbidden_motion_in_snippets(self):
        for stem, _, _, _ in ADOPTIONS.values():
            text = (SNIPPETS / stem).read_text(encoding='utf-8')
            with self.subTest(stem=stem):
                self.assertNotIn('@keyframes', text)
                self.assertNotIn('<animate', text)  # SMIL
                self.assertIsNone(BeautifulSoup(text, 'html.parser')
                                  .find('script'))


class StaticCompletenessTest(unittest.TestCase):
    """정적 완결: 인쇄·감속·자습에서 최종 DOM = 저작 DOM."""

    @classmethod
    def setUpClass(cls):
        cls.html = build_mini()
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(channel='chrome')

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()

    def _page(self, **ctx_kw):
        ctx = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080}, **ctx_kw)
        pg = ctx.new_page()
        pg.goto('file://' + str(self.html))
        pg.wait_for_timeout(2000)
        return ctx, pg

    def test_reduced_motion_shows_authored_final(self):
        ctx, pg = self._page(reduced_motion='reduce')
        try:
            self.assertEqual(pg.evaluate(
                "document.getElementById('cx-typed').textContent"), '«표지 제목 ≤12자»')
            pg.evaluate('deckGo(1,5)')
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-fx-mask').length"), 0)
            pg.evaluate('deckGo(2)')
            self.assertEqual(pg.evaluate(
                "document.querySelector('.t2').textContent"), '«마지막 어절 ≤4자»')
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.t2 .ed-letter').length"), 0,
                '정적 모드에서 글자 분할은 일어나지 않는다')
        finally:
            ctx.close()

    def test_print_emulation_settles(self):
        ctx, pg = self._page()
        try:
            pg.evaluate('deckGo(1,5)')
            pg.wait_for_timeout(800)
            pg.emulate_media(media='print')
            pg.wait_for_timeout(400)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-fx-mask').length"), 0)
            self.assertEqual(pg.evaluate(
                "getComputedStyle(document.querySelector('[data-fx=\"slice-reveal\"]')).clipPath"),
                'none')
            self.assertEqual(pg.evaluate(
                "document.getAnimations().length"), 0)
        finally:
            ctx.close()

    def test_self_study_is_complete(self):
        ctx, pg = self._page()
        try:
            pg.keyboard.press('s')
            pg.wait_for_timeout(500)
            self.assertIn('st-self', pg.evaluate('document.body.className'))
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-fx-mask').length"), 0)
        finally:
            ctx.close()


class UnsupportedSilenceTest(unittest.TestCase):
    """미지원 브라우저: clip-path·가변 wght 없이 침묵 + 최종 상태."""

    @classmethod
    def setUpClass(cls):
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(channel='chrome')

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()

    def test_unsupported_apis_are_silent(self):
        ctx = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080})
        pg = ctx.new_page()
        pg.add_init_script("""()=>{const o=CSS.supports.bind(CSS);
          CSS.supports=(p,v)=>((p==='clip-path'||p==='font-variation-settings')
            ?false:o(p,v));}""")
        errors = []
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.goto('file://' + str(build_mini()))
        pg.wait_for_timeout(2400)
        try:
            # scatter-gather 는 transform/opacity — 글자 분할은 kinetic 과 동일
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('#cx-typed .ed-letter').length"), 10)
            pg.evaluate('deckGo(2)')
            pg.wait_for_timeout(1200)
            # weight-wave: 분할은 kinetic 동일, wght 애니메이션은 침묵
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.t2 .ed-letter').length"), 10)
            pg.evaluate('deckGo(3)')
            pg.wait_for_timeout(1000)
            # slice-reveal: clip-path 미지원 → 즉시 최종 상태
            self.assertEqual(pg.evaluate(
                "getComputedStyle(document.querySelector('[data-fx=\"slice-reveal\"]')).clipPath"),
                'none')
            self.assertEqual(pg.evaluate(
                "document.getAnimations().length"), 0)
            self.assertEqual(errors, [], f'pageerror: {errors}')
        finally:
            ctx.close()


class CancellationContractTest(unittest.TestCase):
    """취소·정착 계약: 이탈 시 잔재 0, 뒤로가기·재방문 재생 없음."""

    @classmethod
    def setUpClass(cls):
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(channel='chrome')

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()

    def test_mid_flight_navigation_leaves_no_residue(self):
        ctx = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080})
        pg = ctx.new_page()
        pg.goto('file://' + str(build_mini()))
        pg.wait_for_timeout(800)
        try:
            # 의제 행 상승 도중 즉시 이탈 — 마스크가 남지 않아야 한다
            pg.evaluate('deckGo(1,1)')
            pg.wait_for_timeout(120)
            self.assertGreater(pg.evaluate(
                "document.querySelectorAll('.ed-fx-mask').length"), 0,
                '상승 도중 마스크가 있어야 이탈 시험이 의미 있다')
            pg.evaluate('deckGo(0)')
            pg.wait_for_timeout(300)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-fx-mask').length"), 0,
                '이탈 시 진행 중 마스크가 제거돼야 한다')
            # 재방문: 새로 발화해 완주 뒤에도 래퍼가 정리된다
            pg.evaluate('deckGo(1,5)')
            pg.wait_for_timeout(1800)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-fx-mask').length"), 0)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.rm-col')[2].children.length"), 4)
        finally:
            ctx.close()

    def test_rack_focus_settles_after_verdict(self):
        ctx = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080})
        pg = ctx.new_page()
        pg.goto('file://' + str(build_mini()))
        pg.wait_for_timeout(2400)
        try:
            pg.evaluate('deckGo(4)')
            pg.wait_for_timeout(400)
            pg.evaluate("document.querySelector('.chk-o').click()")
            pg.wait_for_timeout(1400)
            self.assertEqual(pg.evaluate(
                "getComputedStyle(document.querySelector('.chk-why')).filter"),
                'none')
            self.assertEqual(pg.evaluate(
                "getComputedStyle(document.querySelector('.chk-q')).filter"),
                'none')
            self.assertEqual(pg.evaluate(
                "document.getAnimations().length"), 0)
        finally:
            ctx.close()


if __name__ == '__main__':
    unittest.main()
