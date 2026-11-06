#!/usr/bin/env python3
"""39-quadrant · 40-flashcards 계약 시험 (TASK-quadrant-flash).

[목적] ① 두 계열 어휘(.quad·.qax·.qcell·.qplot·.qp·.qbub / .fcards·.fc·.fc-front·.fc-back)가
         재생성된 두 셸에 있다.
       ② 39·40 조각이 5변형씩·자리표시 규약·aside.notes·정적 계약(SMIL/script 없음)을 지킨다.
       ③ check_deck: quadrant 축 라벨 2개·flashcards 카드 3장+앞뒷면 짝 최소 계약(WARN),
         둘 다 시각 계열로 센다.
       ④ 브라우저: 10변형 렌더·카드 뒤집기·인쇄 전개(뒷면 표시)·다크 1종·시그니처 기록.
[입력] assets/snippets/39-quadrant.html + 40-flashcards.html + 정적 조각 fixture + Chromium.
[출력] 없음(단정문).
"""
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build  # noqa: E402
import check_deck  # noqa: E402

SNIPPETS = S / 'assets' / 'snippets'
OUT = Path('/tmp/edudeck-quadrant-flash')
SRC = OUT / 'src'

QUAD_VARIANTS = ('classic', 'plotted', 'bubble', 'axis-decision', 'teaching')
FC_VARIANTS = ('term-def', 'picture-word', 'qa', 'cut-sheet', 'category')

NOTES = ('시험 장의 발표 노트입니다. 사분면·플래시카드 계약을 확인하는 '
         '안내 문구이며 자습 모드에서는 이 화면 그대로 읽습니다.')


def section(arch, inner='', variant=None):
    v = f' data-variant="{variant}"' if variant else ''
    return (f'<section class="slide" data-archetype="{arch}"{v}>'
            f'<h2 class="title">제목</h2>{inner}<aside class="notes">{NOTES}</aside></section>')


def run_static(sections, allow=False):
    html = ('<!doctype html><html lang="ko"><head><title>t</title></head><body>'
            '<div id="stage">' + ''.join(sections) + '</div></body></html>')
    rep = check_deck.Report()
    check_deck.static_checks(html, BeautifulSoup(html, 'html.parser'), rep, allow)
    return rep


def kinds(rep, kind):
    return [it for it in rep.items if it['kind'] == kind]


class ShellTest(unittest.TestCase):
    """(a) 재생성된 두 셸에 사분면·플래시카드 규칙이 있다."""

    def test_both_shells_carry_vocabulary(self):
        for name in ('shell.html', 'pack-shell.html'):
            with self.subTest(shell=name):
                text = (S / 'assets' / name).read_text(encoding='utf-8')
                for sel in ('.quad{', '.qax{', '.qgrid{', '.qcell{', '.qplot{', '.qp{', '.qbub{',
                            '.fcards{', '.fc{', '.fc-front', '.fc-back{', '.fc.on .fc-in',
                            '.fc-no{', '.fc.open'):
                    self.assertIn(sel, text, f'{name} 에 {sel} 규칙 없음')
                self.assertIn('body.st-self .fc-in', text, '정적 완결(자습) 규칙 없음')


class ContractTest(unittest.TestCase):
    """(b) 조각 계약: 5변형씩 · 자리표시 · 노트 · 정적 계약 · 어휘 요소."""

    def test_five_variants_each(self):
        quad = BeautifulSoup((SNIPPETS / '39-quadrant.html').read_text(encoding='utf-8'),
                             'html.parser')
        fc = BeautifulSoup((SNIPPETS / '40-flashcards.html').read_text(encoding='utf-8'),
                           'html.parser')
        self.assertEqual([s.get('data-variant') for s in quad.select('section.slide')],
                         list(QUAD_VARIANTS))
        self.assertEqual([s.get('data-variant') for s in fc.select('section.slide')],
                         list(FC_VARIANTS))
        self.assertTrue(all(s.get('data-archetype') == 'quadrant'
                            for s in quad.select('section.slide')))
        self.assertTrue(all(s.get('data-archetype') == 'flashcards'
                            for s in fc.select('section.slide')))

    def test_notes_and_placeholders(self):
        for name in ('39-quadrant.html', '40-flashcards.html'):
            soup = BeautifulSoup((SNIPPETS / name).read_text(encoding='utf-8'), 'html.parser')
            for sec in soup.select('section.slide'):
                with self.subTest(file=name, variant=sec.get('data-variant')):
                    n = sec.select_one('aside.notes')
                    self.assertIsNotNone(n)
                    self.assertGreaterEqual(len(n.get_text()), 50)
                    self.assertIn('«', sec.get_text(), '자리표시 규약 없음')
                    self.assertIsNone(sec.find('script'))
                    self.assertIsNone(sec.find('animate'), 'SMIL 없음')

    def test_quadrant_axis_labels_present(self):
        soup = BeautifulSoup((SNIPPETS / '39-quadrant.html').read_text(encoding='utf-8'),
                             'html.parser')
        for sec in soup.select('section.slide'):
            with self.subTest(variant=sec.get('data-variant')):
                qax = sec.select('.qax')
                self.assertGreaterEqual(len(qax), 2, '축 라벨 2개 계약')
                self.assertTrue(any('qax-x' in q.get('class', []) for q in qax))
                self.assertTrue(any('qax-y' in q.get('class', []) for q in qax))

    def test_flashcards_faces_paired(self):
        soup = BeautifulSoup((SNIPPETS / '40-flashcards.html').read_text(encoding='utf-8'),
                             'html.parser')
        for sec in soup.select('section.slide'):
            with self.subTest(variant=sec.get('data-variant')):
                fcs = sec.select('.fc')
                self.assertGreaterEqual(len(fcs), 3, '카드 3장 이상')
                for c in fcs:
                    self.assertIsNotNone(c.select_one('.fc-front'), '앞면 없음')
                    self.assertIsNotNone(c.select_one('.fc-back'), '뒷면 없음')

    def test_motion_js_recipes_registered(self):
        text = (S / 'assets/js/motion.js').read_text(encoding='utf-8')
        self.assertIn("'quadrant':{name:'grid-wave'", text)
        self.assertIn("'flashcards':{name:'facet-flip'", text)
        self.assertIn("'quadrant':'.qcell,.qp,.qbub'", text)
        self.assertIn("'flashcards':'.fc'", text)


class CheckerTest(unittest.TestCase):
    """(c) check_deck 최소 계약 + 시각 분류."""

    def test_archetypes_registered(self):
        self.assertIn('quadrant', check_deck.ARCHETYPES)
        self.assertIn('flashcards', check_deck.ARCHETYPES)
        self.assertIn('quadrant', check_deck.VISUAL_ARCHS)
        self.assertIn('flashcards', check_deck.VISUAL_ARCHS)

    def test_quadrant_axis_warn(self):
        rep = run_static([section('quadrant', '<div class="quad"><div class="qgrid">'
                                            '<div class="qcell">a</div></div></div>')])
        self.assertTrue(any(it['sev'] == 'WARN' for it in kinds(rep, '사분면')),
                        '축 라벨 부족 WARN 없음')

    def test_flashcards_count_and_face_warn(self):
        rep = run_static([section('flashcards', '<div class="fcards">'
                                              '<button class="fc"><span class="fc-in">'
                                              '<span class="fc-front">앞</span>'
                                              '</span></button></div>')])
        warns = [it for it in rep.items if it['sev'] == 'WARN']
        self.assertGreaterEqual(len(kinds(rep, '플래시카드')), 2, '카드 수+면 짝 WARN 없음')

    def test_fc_click_handler_in_motion(self):
        text = (S / 'assets/js/motion.js').read_text(encoding='utf-8')
        self.assertIn("closest('.fc')", text, '카드 뒤집기 핸들러 없음')
        self.assertIn("classList.toggle('on')", text)


def build_mini():
    """10변형+sources 로 실덱을 만든다(자리표시 채운 노트로 정적 검사 가능)."""
    SRC.mkdir(parents=True, exist_ok=True)
    for p in SRC.glob('*.html'):
        p.unlink()
    srcs, files = [], []
    for name in ('39-quadrant.html', '40-flashcards.html'):
        soup = BeautifulSoup((SNIPPETS / name).read_text(encoding='utf-8'), 'html.parser')
        files.extend(soup.select('section.slide'))
    files.append(BeautifulSoup((SNIPPETS / '28-sources.html').read_text(encoding='utf-8'),
                               'html.parser').select_one('section.slide'))
    # 다크 검증 — term-def 를 어두운 장으로 하나 더
    dark = BeautifulSoup(str(files[5]), 'html.parser').select_one('section.slide')
    dark['class'] = 'slide dark'
    files.append(dark)
    for i, sec in enumerate(files, 1):
        for notes in sec.select('aside.notes'):
            notes.string = NOTES + ' 화면의 사분면·플래시카드를 살펴본 뒤 다음 장으로 이어갑니다.'
        p = SRC / f'{i:02d}.html'
        p.write_text(str(sec), encoding='utf-8')
        srcs.append(p)
    html = OUT / 'deck.html'
    build('사분면·플래시카드 시험', srcs, [S / 'assets/css'], [S / 'assets/icons'], html)
    return html


class BrowserTest(unittest.TestCase):
    """(d) 실제 렌더: 10변형·뒤집기·인쇄 전개·다크·시그니처."""

    @classmethod
    def setUpClass(cls):
        cls.html = build_mini()
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(channel='chrome')

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()

    def _page(self, path, **kw):
        pg = self._browser.new_context(viewport={'width': 1920, 'height': 1080}, **kw).new_page()
        pg.goto('file://' + str(path))
        pg.wait_for_selector('.slide.active', timeout=10000)
        return pg

    def _advance_all(self, pg):
        for _ in range(10):
            info = pg.evaluate('window.deckInfo()')
            if info['step'] >= info['maxStep']:
                return
            pg.keyboard.press('ArrowRight')
            pg.wait_for_timeout(350)

    def test_ten_variants_render_and_signatures(self):
        pg = self._page(self.html)
        expect = ['grid-wave'] * 5 + ['facet-flip'] * 5
        for i in range(10):
            with self.subTest(slide=i):
                pg.evaluate(f'window.deckGo({i})')
                pg.wait_for_timeout(300)
                self._advance_all(pg)
                pg.wait_for_timeout(500)
                sig = pg.evaluate(
                    "document.querySelectorAll('#stage>.slide')[%d].dataset.motionSignature" % i)
                self.assertEqual(sig, expect[i], f'장 {i} 시그니처')
                box = pg.evaluate(
                    "document.querySelectorAll('#stage>.slide')[%d]"
                    ".getBoundingClientRect().toJSON()" % i)
                self.assertGreater(box['width'], 1800)
        pg.context.close()

    def test_quadrant_axes_and_items_visible(self):
        pg = self._page(self.html)
        for i, sel in ((0, '.qcell'), (1, '.qp'), (2, '.qbub')):
            with self.subTest(slide=i, sel=sel):
                pg.evaluate(f'window.deckGo({i})')
                pg.wait_for_timeout(300)
                self._advance_all(pg)
                pg.wait_for_timeout(500)
                n = pg.evaluate(
                    "document.querySelectorAll('#stage>.slide')[%d]"
                    ".querySelectorAll('%s').length" % (i, sel))
                self.assertGreaterEqual(n, 4 if sel == '.qcell' else 3)
        pg.context.close()

    def test_card_flip_click(self):
        pg = self._page(self.html)
        pg.evaluate('window.deckGo(5)')  # term-def
        pg.wait_for_timeout(500)
        pg.locator('.slide.active .fc').first.click()
        pg.wait_for_timeout(600)
        self.assertTrue(pg.evaluate(
            "document.querySelector('.slide.active .fc').classList.contains('on')"),
            '클릭으로 카드가 뒤집히지 않음')
        pg.context.close()

    def test_print_expands_all_faces(self):
        pg = self._page(self.html)
        pg.emulate_media(media='print')
        pg.evaluate('window.deckGo(5)')
        pg.wait_for_timeout(400)
        pos = pg.evaluate(
            "getComputedStyle(document.querySelectorAll('#stage>.slide')[5]"
            ".querySelector('.fc-back')).position")
        self.assertEqual(pos, 'static', '인쇄에서 뒷면이 펼쳐지지 않음')
        # 모든 카드 뒷면이 펼쳐진다
        n = pg.evaluate(
            "[...document.querySelectorAll('#stage>.slide')[5].querySelectorAll('.fc-back')]"
            ".filter(e=>getComputedStyle(e).position==='static').length")
        self.assertEqual(n, 4)
        pg.context.close()

    def test_self_study_expands_faces(self):
        pg = self._page(self.html)
        pg.evaluate('window.deckGo(7)')  # qa
        pg.wait_for_timeout(400)
        pg.evaluate('document.body.classList.add("st-self")')
        pg.wait_for_timeout(300)
        pos = pg.evaluate(
            "getComputedStyle(document.querySelectorAll('#stage>.slide')[7]"
            ".querySelector('.fc-back')).position")
        self.assertEqual(pos, 'static', '자습에서 뒷면이 펼쳐지지 않음')
        pg.context.close()

    def test_dark_flashcards_readable(self):
        pg = self._page(self.html)
        pg.evaluate('window.deckGo(11)')  # dark term-def
        pg.wait_for_timeout(500)
        # 앞면 글자가 어두운 색(면이 밝다)
        color = pg.evaluate(
            "getComputedStyle(document.querySelectorAll('#stage>.slide')[11]"
            ".querySelector('.fc-front span:last-child')).color")
        self.assertIn('rgb(32,', color, '다크 장 앞면 글자가 --ink 가 아니다')
        # 뒤집으면 뒷면도 읽힌다(밝은 면)
        pg.locator('.slide.active .fc').first.click()
        pg.wait_for_timeout(500)
        bg = pg.evaluate(
            "getComputedStyle(document.querySelectorAll('#stage>.slide')[11]"
            ".querySelector('.fc-back')).backgroundColor")
        self.assertNotEqual(bg, 'rgba(0, 0, 0, 0)')
        pg.context.close()


if __name__ == '__main__':
    unittest.main()
