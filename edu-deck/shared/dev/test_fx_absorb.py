#!/usr/bin/env python3
"""공통 모션 기법 3종 계약 시험 (TASK-fx-absorb).

[목적] bar-grow·card-deal·blinds 가
       ① 채택 스니펫의 저작 속성 계약(data-fx 이름·대상·한도)을 지키고
       ② 정적 모드(인쇄·감속·자습)에서 저작한 최종 DOM 그대로 완결되며
       ③ 미지원 브라우저(clip-path)에서 침묵으로 최종 상태를 보이고
       ④ 화면 발화 후 이탈·재방문 시 잔재 없이 취소된다 — 를 잠근다.
       ⑤ transform 등장 기법을 선언한 요소는 계열 시그니처의 transform
          안무와 겹쳐 발화하지 않는다(FX_OWN_TRANSFORM 가드).
[입력] assets/snippets 3계열 채택 section 으로 /tmp 미니덱 빌드 + 실제 Chromium.
[출력] 없음(단정문).
[주의] 시각적 차이(픽셀·중간 프레임)는 TASK-fx-absorb-STATE.md 증거가 맡고,
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
OUT = Path('/tmp/edudeck-fx-absorb')
SRC = OUT / 'src'

TECHNIQUES = ('bar-grow', 'card-deal', 'blinds')

# 채택 계열 -> (스니펫 파일, data-fx 이름, 대상 선택자, 장당 최대 대상 수)
ADOPTIONS = {
    'meter': ('07-meter.html', 'bar-grow', '.meter-seg', 12),
    'tile-grid': ('12-tile-grid.html', 'card-deal', '.sk-card', 12),
    'rules-dark': ('26-rules-dark.html', 'blinds', '.col', 1),
}

# 미니덱 구성: 계열 파일 -> 골라낼 변형(None 이면 첫 section)
SECTIONS = [
    ('07-meter.html', None),
    ('12-tile-grid.html', 'cards'),
    ('26-rules-dark.html', 'numbered-clauses'),
]


def pick_section(stem, variant):
    soup = BeautifulSoup(
        (SNIPPETS / stem).read_text(encoding='utf-8'), 'html.parser')
    sel = 'section.slide'
    if variant:
        sel += f'[data-variant="{variant}"]'
    return str(soup.select_one(sel))


def build_mini():
    SRC.mkdir(parents=True, exist_ok=True)
    srcs = []
    for i, (stem, variant) in enumerate(SECTIONS):
        p = SRC / f'{i:02d}-{stem}'
        p.write_text(pick_section(stem, variant), encoding='utf-8')
        srcs.append(p)
    html = OUT / 'deck.html'
    build('fx 흡수 시험', srcs, [S / 'assets/css'],
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

    def test_engine_registers_three_techniques(self):
        for name in TECHNIQUES:
            with self.subTest(fx=name):
                self.assertIn(f"'{name}'", MOTION, 'motion.js FX 표 미등록')
                self.assertIn(name, FX_KINDS, 'check_deck FX_KINDS 미등록')
        # 기존 5종·원시 어휘·실행 이름 체계는 무변경 — 신규는 어휘 추가뿐.
        names = set(re.findall(r"name:'([a-z-]+)'", MOTION))
        self.assertEqual(len(names), 41,
                         f'실행 이름 {len(names)}종 — 41종 체계 변경 감지: {sorted(names)}')

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

    def _settled(self, pg):
        """세 채택 장의 최종 상태 단정 묶음(전 단계 이동 후)."""
        pg.evaluate('deckGo(0,7)')
        pg.evaluate('deckGo(1,4)')
        pg.evaluate('deckGo(2,3)')
        pg.wait_for_timeout(1200)
        self.assertEqual(pg.evaluate(
            "document.querySelectorAll('.meter-seg')[0].style.transform"), '')
        self.assertEqual(pg.evaluate(
            "getComputedStyle(document.querySelectorAll('.sk-card')[0]).transform"),
            'none')
        self.assertEqual(pg.evaluate(
            "getComputedStyle(document.querySelector('[data-fx=\"blinds\"]')).clipPath"),
            'none')
        self.assertEqual(pg.evaluate(
            "document.getAnimations().length"), 0)

    def test_reduced_motion_shows_authored_final(self):
        ctx, pg = self._page(reduced_motion='reduce')
        try:
            self._settled(pg)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.meter-seg').length"), 5)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.sk-card').length"), 6)
        finally:
            ctx.close()

    def test_print_emulation_settles(self):
        ctx, pg = self._page()
        try:
            pg.evaluate('deckGo(0,7)')
            pg.evaluate('deckGo(1,4)')
            pg.wait_for_timeout(800)
            pg.emulate_media(media='print')
            pg.wait_for_timeout(400)
            self.assertEqual(pg.evaluate(
                "getComputedStyle(document.querySelectorAll('.meter-seg')[0]).transform"),
                'none')
            self.assertEqual(pg.evaluate(
                "getComputedStyle(document.querySelector('[data-fx=\"blinds\"]')).clipPath"),
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
                "document.getAnimations().length"), 0)
            self.assertEqual(pg.evaluate(
                "getComputedStyle(document.querySelector('[data-fx=\"blinds\"]')).clipPath"),
                'none')
        finally:
            ctx.close()


class UnsupportedSilenceTest(unittest.TestCase):
    """미지원 브라우저: clip-path 없이 침묵 + 최종 상태."""

    @classmethod
    def setUpClass(cls):
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(channel='chrome')

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()

    def test_unsupported_clip_path_is_silent(self):
        ctx = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080})
        pg = ctx.new_page()
        pg.add_init_script("""()=>{const o=CSS.supports.bind(CSS);
          CSS.supports=(p,v)=>(p==='clip-path'?false:o(p,v));}""")
        errors = []
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.goto('file://' + str(build_mini()))
        pg.wait_for_timeout(2400)
        try:
            pg.evaluate('deckGo(2)')
            pg.wait_for_timeout(1200)
            # blinds: clip-path 미지원 → 즉시 최종 상태, 예외 없음
            self.assertEqual(pg.evaluate(
                "getComputedStyle(document.querySelector('[data-fx=\"blinds\"]')).clipPath"),
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

    def _page(self):
        ctx = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080})
        pg = ctx.new_page()
        pg.goto('file://' + str(build_mini()))
        pg.wait_for_timeout(1200)
        return ctx, pg

    def test_bar_grow_owns_single_transform(self):
        ctx, pg = self._page()
        try:
            # 막대 상승 도중: fx 애니메이션 1개뿐 — 계열 시그니처의 transform
            # 안무가 겹치면 2개가 된다(FX_OWN_TRANSFORM 가드 회귀 잠금).
            pg.evaluate('deckGo(0,1)')
            pg.wait_for_timeout(150)
            own = pg.evaluate(
                "document.querySelectorAll('.meter-seg')[0]"
                ".getAnimations().filter(a=>a.effect.target===document"
                ".querySelectorAll('.meter-seg')[0]).length")
            self.assertEqual(own, 1, '막대에 걸린 transform 애니메이션은 1개여야 한다')
            pg.evaluate('deckGo(1)')
            pg.wait_for_timeout(400)
            # 재방문: 새로 발화해 완주 뒤에도 인라인 transform 이 남지 않는다
            pg.evaluate('deckGo(0,7)')
            pg.wait_for_timeout(1600)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.meter-seg')[0].style.transform"), '')
            self.assertEqual(pg.evaluate(
                "document.getAnimations().length"), 0)
        finally:
            ctx.close()

    def test_card_deal_settles_square(self):
        ctx, pg = self._page()
        try:
            pg.evaluate('deckGo(1,1)')
            pg.wait_for_timeout(200)
            mid = pg.evaluate(
                "getComputedStyle(document.querySelectorAll('.sk-card')[0]).transform")
            self.assertNotEqual(mid, 'none', '딜 도중 transform 이 걸려 있어야 한다')
            pg.wait_for_timeout(1400)
            for i in range(3):
                self.assertEqual(pg.evaluate(
                    f"getComputedStyle(document.querySelectorAll('.sk-card')[{i}]).transform"),
                    'none', f'카드 {i} 는 제자리에 정착해야 한다(회전 0)')
        finally:
            ctx.close()

    def test_blinds_cancels_cleanly(self):
        ctx, pg = self._page()
        try:
            pg.evaluate('deckGo(2)')
            pg.wait_for_timeout(220)
            mid = pg.evaluate(
                "getComputedStyle(document.querySelector('[data-fx=\"blinds\"]')).clipPath")
            self.assertIn('polygon', mid, '띠 공개 도중 clip-path 가 걸려 있어야 한다')
            pg.evaluate('deckGo(0)')
            pg.wait_for_timeout(300)
            self.assertEqual(pg.evaluate(
                "getComputedStyle(document.querySelector('[data-fx=\"blinds\"]')).clipPath"),
                'none', '이탈 시 진행 중 블라인드가 정리돼야 한다')
            pg.evaluate('deckGo(2,3)')
            pg.wait_for_timeout(1400)
            self.assertEqual(pg.evaluate(
                "getComputedStyle(document.querySelector('[data-fx=\"blinds\"]')).clipPath"),
                'none')
            self.assertEqual(pg.evaluate(
                "document.getAnimations().length"), 0)
        finally:
            ctx.close()

    def test_fires_once_and_logs_sig(self):
        ctx, pg = self._page()
        try:
            pg.evaluate('deckGo(0,7)')
            pg.evaluate('deckGo(1,4)')
            pg.evaluate('deckGo(2,3)')
            pg.wait_for_timeout(1200)
            sigs = [e['sig'] for e in pg.evaluate('window.eduMotion.sigLog')]
            for want in ('fx-bar-grow', 'fx-card-deal', 'fx-blinds'):
                self.assertIn(want, sigs, f'sigLog 에 {want} 없음')
            # 왕복 재방문은 재발화 없음 — fx- 항목 수가 늘지 않는다
            before = sum(1 for s in sigs if s.startswith('fx-'))
            pg.evaluate('deckGo(0)')
            pg.evaluate('deckGo(1,4)')
            pg.evaluate('deckGo(2)')
            pg.wait_for_timeout(800)
            sigs2 = [e['sig'] for e in pg.evaluate('window.eduMotion.sigLog')]
            self.assertEqual(sum(1 for s in sigs2 if s.startswith('fx-')), before,
                             '재방문에서 기법이 다시 발화했다')
        finally:
            ctx.close()


if __name__ == '__main__':
    unittest.main()
