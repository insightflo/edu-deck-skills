#!/usr/bin/env python3
"""미니 흐름 어휘 + 파트 구분지(part-divider) 계약 시험 (TASK-miniflow-divider).

[목적] ① 미니 흐름 어휘(.vflow·.vnode·.varr·.vpills)가 재생성된 두 셸에 있다.
       ② 38계열 조각이 5변형·자리표시 규약·aside.notes·정적 계약(SMIL/script 없음)을 지킨다.
       ③ check_deck: part-divider 는 FIXED(나열 계산 제외), 미니 흐름 보유 장은 시각으로 센다.
       ④ 브라우저: 구분지 5종 렌더·인쇄 완결·다크 장·미니 흐름 카드 렌더·시그니처 기록.
[입력] assets/snippets/38-part-divider.html + 06·26 flow 변형 + 정적 조각 fixture + Chromium.
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
OUT = Path('/tmp/edudeck-miniflow')
SRC = OUT / 'src'

DIVIDER_VARIANTS = ('big-number', 'progress-map', 'question', 'takeaways', 'quiet')

NOTES = ('시험 장의 발표 노트입니다. 미니 흐름 어휘와 구분지 계약을 확인하는 '
         '안내 문구이며 자습 모드에서는 이 화면 그대로 읽습니다.')


def section(arch, inner='', dark=False, variant=None):
    v = f' data-variant="{variant}"' if variant else ''
    cls = 'slide dark' if dark else 'slide'
    return (f'<section class="{cls}" data-archetype="{arch}"{v}>'
            f'<h2 class="title">제목</h2>{inner}<aside class="notes">{NOTES}</aside></section>')


def run_static(sections, allow=False):
    html = ('<!doctype html><html lang="ko"><head><title>t</title></head><body>'
            '<div id="stage">' + ''.join(sections) + '</div></body></html>')
    rep = check_deck.Report()
    check_deck.static_checks(html, BeautifulSoup(html, 'html.parser'), rep, allow)
    return rep


def kinds(rep, kind):
    return [it for it in rep.items if it['kind'] == kind]


MINIFLOW = ('<div class="vflow"><span class="vnode">시작</span><span class="varr">→</span>'
            '<span class="vnode is-on">끝</span></div>')


class ShellTest(unittest.TestCase):
    """(a) 재생성된 두 셸에 미니 흐름 규칙이 있다."""

    def test_both_shells_carry_vocabulary(self):
        for name in ('shell.html', 'pack-shell.html'):
            with self.subTest(shell=name):
                text = (S / 'assets' / name).read_text(encoding='utf-8')
                for sel in ('.vflow{', '.vnode{', '.varr{', '.vpills{'):
                    self.assertIn(sel, text, f'{name} 에 {sel} 규칙 없음')
                self.assertIn('.vnode.is-on', text)
                self.assertIn('.vflow.col', text)


class DividerContractTest(unittest.TestCase):
    """(b) 38계열: 5변형 · 자리표시 · 노트 · 정적 계약."""

    def sections(self):
        soup = BeautifulSoup((SNIPPETS / '38-part-divider.html').read_text(encoding='utf-8'),
                             'html.parser')
        return soup.select('section.slide[data-archetype="part-divider"]')

    def test_five_variants(self):
        secs = self.sections()
        self.assertEqual(len(secs), 5)
        got = {s.get('data-variant') for s in secs}
        self.assertEqual(got, set(DIVIDER_VARIANTS), got)

    def test_placeholder_and_notes_contract(self):
        for sec in self.sections():
            with self.subTest(variant=sec.get('data-variant')):
                self.assertIn('«', sec.get_text(), '자리표시 규약(«…»)')
                notes = sec.select_one('aside.notes')
                self.assertIsNotNone(notes, 'aside.notes 필수')
                self.assertIsNone(sec.find('script'))
                self.assertIsNone(sec.find('animate'))

    def test_progress_map_uses_miniflow(self):
        secs = {s.get('data-variant'): s for s in self.sections()}
        pm = secs['progress-map']
        self.assertIsNotNone(pm.select_one('.vflow .vnode.is-on'),
                             '진행 지도는 현재 파트를 is-on 으로 강조한다')
        self.assertIsNotNone(pm.select_one('.vnode.is-off'), '지난 파트는 is-off')


class CheckerTest(unittest.TestCase):
    """(c) part-divider=FIXED · 미니 흐름=시각 분류."""

    def test_divider_in_fixed_set(self):
        self.assertIn('part-divider', check_deck.FIXED_ARCHS)
        self.assertIn('part-divider', check_deck.ARCHETYPES)
        self.assertNotIn('part-divider', check_deck.VISUAL_ARCHS)

    def test_divider_excluded_even_with_miniflow(self):
        # 구분지가 .vflow 를 써도 FIXED — 연속열에서 빠진다(끊지도 세지도 않는다)
        secs = ([section('checklist', inner='<p class="body">본문</p>') for _ in range(4)]
                + [section('part-divider', inner=MINIFLOW, variant='progress-map')]
                + [section('checklist', inner='<p class="body">본문</p>') for _ in range(4)])
        rep = run_static(secs)
        self.assertTrue(kinds(rep, '텍스트 나열'),
                        '구분지는 제외라 앞뒤 텍스트 8장이 이어진다 — WARN 발화가 정상')

    def test_miniflow_counts_as_visual(self):
        secs = ([section('checklist', inner='<p class="body">본문</p>') for _ in range(4)]
                + [section('checklist', inner=MINIFLOW)]
                + [section('checklist', inner='<p class="body">본문</p>') for _ in range(4)])
        rep = run_static(secs)
        self.assertFalse(kinds(rep, '텍스트 나열'), '미니 흐름 보유 장은 시각이라 연속을 끊는다')

    def test_vpills_counts_as_visual(self):
        secs = ([section('checklist', inner='<p class="body">본문</p>') for _ in range(4)]
                + [section('checklist', inner='<div class="vpills"><span class="vnode">가</span>'
                                             '<span class="vnode">나</span></div>')]
                + [section('checklist', inner='<p class="body">본문</p>') for _ in range(4)])
        rep = run_static(secs)
        self.assertFalse(kinds(rep, '텍스트 나열'), '알약 나열(화살표 없음)도 시각')

    def test_miniflow_no_own_motion(self):
        # 미니 흐름은 독자 등장 모션 없음 — 시그니처 이름·data-fx 도 어휘가 아니다
        for name in ('shell.html', 'pack-shell.html'):
            text = (S / 'assets' / name).read_text(encoding='utf-8')
            self.assertNotIn('@keyframes vnode', text)
            self.assertNotIn('@keyframes vflow', text)


def build_mini():
    SRC.mkdir(parents=True, exist_ok=True)
    soup = BeautifulSoup((SNIPPETS / '38-part-divider.html').read_text(encoding='utf-8'),
                         'html.parser')
    srcs = []
    files = list(soup.select('section.slide'))
    for stem, variant in (('06-traits-grid', 'flow'), ('26-rules-dark', 'flow')):
        s2 = BeautifulSoup((SNIPPETS / f'{stem}.html').read_text(encoding='utf-8'),
                           'html.parser')
        files.append(s2.select_one(f'section.slide[data-variant="{variant}"]'))
    s3 = BeautifulSoup((SNIPPETS / '28-sources.html').read_text(encoding='utf-8'),
                       'html.parser')
    files.append(s3.select_one('section.slide'))
    for i, sec in enumerate(files, 1):
        for notes in sec.select('aside.notes'):
            notes.string = NOTES + ' 화면의 미니 흐름·구분지를 살펴본 뒤 다음 장으로 이어갑니다.'
        p = SRC / f'{i:02d}.html'
        p.write_text(str(sec), encoding='utf-8')
        srcs.append(p)
    html = OUT / 'deck.html'
    build('미니흐름 시험', srcs, [S / 'assets/css'], [S / 'assets/icons'], html)
    return html


class BrowserTest(unittest.TestCase):
    """(d) 실제 렌더: 구분지 5종·인쇄·다크·미니 흐름 카드·시그니처."""

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

    def test_five_dividers_render_and_signature(self):
        pg = self._page(self.html)
        for i in range(5):
            with self.subTest(slide=i):
                pg.evaluate(f'window.deckGo({i})')
                pg.wait_for_timeout(300)
                self._advance_all(pg)
                pg.wait_for_timeout(600)
                sig = pg.evaluate(
                    "document.querySelectorAll('#stage>.slide')[%d].dataset.motionSignature" % i)
                self.assertEqual(sig, 'route-cascade', '구분지는 route-cascade 재사용')
                title = pg.evaluate(
                    "document.querySelectorAll('#stage>.slide')[%d]"
                    ".querySelector('.title,.big').getBoundingClientRect().toJSON()" % i)
                self.assertGreater(title['width'], 200, '구분지 제목이 보인다')
        pg.context.close()

    def test_progress_map_miniflow_visible(self):
        pg = self._page(self.html)
        pg.evaluate('window.deckGo(1)')
        pg.wait_for_timeout(300)
        self._advance_all(pg)
        pg.wait_for_timeout(500)
        box = pg.evaluate(
            "document.querySelectorAll('#stage>.slide')[1]"
            ".querySelector('.vflow.col').getBoundingClientRect().toJSON()")
        self.assertGreater(box['width'], 200, '진행 지도 미니 흐름이 보인다')
        self.assertGreater(box['height'], 80)
        on = pg.evaluate(
            "document.querySelectorAll('#stage>.slide')[1]"
            ".querySelector('.vnode.is-on').getBoundingClientRect().toJSON()")
        self.assertGreater(on['width'], 60, '현재 파트 is-on 노드가 보인다')
        pg.context.close()

    def test_print_completeness(self):
        pg = self._page(self.html)
        pg.emulate_media(media='print')
        pg.evaluate('window.deckGo(1)')
        pg.wait_for_timeout(500)
        box = pg.evaluate(
            "document.querySelectorAll('#stage>.slide')[1]"
            ".querySelector('.vflow.col').getBoundingClientRect().toJSON()")
        self.assertGreater(box['height'], 80, '인쇄에서도 미니 흐름이 완성 상태')
        pg.context.close()

    def test_dark_variants_render(self):
        pg = self._page(self.html)
        for i in (0, 4):  # big-number · quiet
            with self.subTest(slide=i):
                pg.evaluate(f'window.deckGo({i})')
                pg.wait_for_timeout(400)
                bg = pg.evaluate(
                    "getComputedStyle(document.querySelectorAll('#stage>.slide')[%d])"
                    '.backgroundColor' % i)
                self.assertNotIn('250,', bg, '다크 구분지는 어두운 장')
        pg.context.close()

    def test_flow_variant_cards_render(self):
        # 06 traits-grid(flow)는 슬라이드 5(0기준) — 카드 안 미니 흐름이 보인다
        pg = self._page(self.html)
        pg.evaluate('window.deckGo(5)')
        pg.wait_for_timeout(300)
        self._advance_all(pg)
        pg.wait_for_timeout(600)
        n = pg.evaluate(
            "document.querySelectorAll('#stage>.slide')[5].querySelectorAll('.vnode').length")
        self.assertGreaterEqual(n, 8, 'flow 카드들에 미니 흐름 노드가 있다')
        pg.context.close()


if __name__ == '__main__':
    unittest.main()
