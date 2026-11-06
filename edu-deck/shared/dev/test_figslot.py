#!/usr/bin/env python3
"""공용 그림 자리(fig-slot) 계약 시험 (TASK-figslots).

[목적] ① 5개 일반 계열의 data-variant="fig" 변형이 슬롯 계약을 지킨다 —
       figure.fig-slot 단 1개 · 견본 svg.dg · role="img"+aria-label · «…» 자리표시 · 노트.
       ② check_deck 규칙 3종(빈 슬롯·자리표시·svg 읽기 계약 ERROR, 텍스트 나열 WARN)이
       유효·무효 조각에서 정확히 발화한다.
       ③ 브라우저에서 5변형 완성 표시·인쇄 완결·다크 장·리소스팩 덱 탑재가 된다.
       ④ 재생성된 두 셸(shell.html·pack-shell.html)에 .fig-slot 규칙이 있다.
[입력] assets/snippets 5개 파일 + 정적 조각 fixture + 실제 Chromium.
[출력] 없음(단정문).
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
import check_deck  # noqa: E402

SNIPPETS = S / 'assets' / 'snippets'
OUT = Path('/tmp/edudeck-figslot')
SRC = OUT / 'src'

# 지시서 §3: fig 변형을 얻는 5개 일반 배치 계열
FIG_FAMILIES = ('02-agenda', '06-traits-grid', '11-levels',
                '17-statement', '26-rules-dark')

NOTES = ('시험 장의 발표 노트입니다. 그림 자리 계약과 정적 완결을 확인하는 '
         '안내 문구이며 자습 모드에서는 이 화면 그대로 읽습니다.')

SAMPLE_SVG = ('<svg class="dg" viewBox="0 0 400 300" role="img" '
              'aria-label="시험 도식"><circle class="k-blue" cx="200" cy="150" r="80"/>'
              '<text class="t-l" text-anchor="middle" x="200" y="160">핵심</text></svg>')


def fig_section(arch, variant=None, inner='', dark=False):
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


class SnippetContractTest(unittest.TestCase):
    """슬롯 계약: 5계열 × data-variant="fig" × 단일 figure.fig-slot × 견본 svg.dg."""

    def fig_section(self, stem):
        soup = BeautifulSoup(
            (SNIPPETS / f'{stem}.html').read_text(encoding='utf-8'), 'html.parser')
        secs = soup.select('section.slide[data-variant="fig"]')
        self.assertEqual(len(secs), 1, f'{stem}: data-variant="fig" 섹션이 {len(secs)}개')
        return secs[0]

    def test_five_families_have_fig_variant(self):
        for stem in FIG_FAMILIES:
            with self.subTest(stem=stem):
                self.fig_section(stem)

    def test_slot_contract(self):
        for stem in FIG_FAMILIES:
            with self.subTest(stem=stem):
                sec = self.fig_section(stem)
                figs = sec.select('figure.fig-slot')
                self.assertEqual(len(figs), 1, 'fig-slot 은 섹션에 정확히 1개')
                fig = figs[0]
                svg = fig.find('svg', class_='dg')
                self.assertIsNotNone(svg, '슬롯 안에 견본 svg.dg 가 있어야 한다')
                self.assertEqual(svg.get('role'), 'img')
                self.assertTrue(svg.get('aria-label'), 'aria-label(도식 요지) 필수')
                self.assertIn('«', fig.get_text(), '견본은 자리표시 규약(«…»)을 따른다')
                self.assertIsNotNone(sec.select_one('aside.notes'), '노트 필수')

    def test_no_motion_recipe_inside(self):
        # 신규 모션 시그니처 금지: 슬롯 안 SMIL·script·keyframes 없음
        for stem in FIG_FAMILIES:
            with self.subTest(stem=stem):
                sec = self.fig_section(stem)
                fig = sec.select_one('figure.fig-slot')
                self.assertIsNone(fig.find('script'))
                self.assertIsNone(fig.find('animate'))


class CheckerRuleTest(unittest.TestCase):
    """check_deck 규칙: 빈 슬롯·자리표시·읽기 계약 ERROR + 텍스트 나열 WARN."""

    def test_empty_slot_is_error(self):
        rep = run_static([fig_section('checklist', 'fig', '<figure class="fig-slot"></figure>')])
        msgs = kinds(rep, '그림 자리')
        self.assertTrue(any('비었' in m['message'] for m in msgs), rep.items)

    def test_placeholder_in_slot_is_error(self):
        svg = ('<svg class="dg" viewBox="0 0 400 300" role="img" aria-label="«그림 설명»">'
               '<text class="t-l" x="10" y="20">«레이블»</text></svg>')
        rep = run_static([fig_section('checklist', 'fig', f'<figure class="fig-slot">{svg}</figure>')])
        msgs = kinds(rep, '그림 자리')
        self.assertTrue(any('자리표시' in m['message'] for m in msgs), rep.items)

    def test_placeholder_allowed_for_snippets(self):
        svg = ('<svg class="dg" viewBox="0 0 400 300" role="img" aria-label="«그림 설명»">'
               '<text class="t-l" x="10" y="20">«레이블»</text></svg>')
        rep = run_static([fig_section('checklist', 'fig', f'<figure class="fig-slot">{svg}</figure>')],
                         allow=True)
        self.assertFalse(kinds(rep, '그림 자리'), 'allow_placeholders 면 조각 견본은 조용해야 한다')

    def test_missing_aria_is_error(self):
        svg = '<svg class="dg" viewBox="0 0 400 300"><circle cx="200" cy="150" r="80"/></svg>'
        rep = run_static([fig_section('checklist', 'fig', f'<figure class="fig-slot">{svg}</figure>')])
        msgs = kinds(rep, '그림 자리')
        self.assertTrue(any('aria-label' in m['message'] for m in msgs), rep.items)

    def test_valid_slot_quiet(self):
        rep = run_static([fig_section('checklist', 'fig', f'<figure class="fig-slot">{SAMPLE_SVG}</figure>')])
        self.assertFalse(kinds(rep, '그림 자리'), rep.items)

    def test_text_run_five_warns(self):
        secs = [fig_section('checklist', inner='<p class="body">본문</p>') for _ in range(5)]
        rep = run_static(secs)
        self.assertTrue(kinds(rep, '텍스트 나열'), rep.items)

    def test_visual_family_breaks_run(self):
        secs = ([fig_section('checklist', inner='<p class="body">본문</p>') for _ in range(4)]
                + [fig_section('timeline', inner='<p class="body">도식 장</p>')]
                + [fig_section('checklist', inner='<p class="body">본문</p>') for _ in range(4)])
        rep = run_static(secs)
        self.assertFalse(kinds(rep, '텍스트 나열'), '시각 계열이 끊으면 경고 없음')

    def test_fig_variant_counts_as_visual(self):
        secs = ([fig_section('checklist', inner='<p class="body">본문</p>') for _ in range(4)]
                + [fig_section('agenda', 'fig', f'<figure class="fig-slot">{SAMPLE_SVG}</figure>')]
                + [fig_section('checklist', inner='<p class="body">본문</p>') for _ in range(4)])
        rep = run_static(secs)
        self.assertFalse(kinds(rep, '텍스트 나열'), 'fig 변형 장은 시각으로 센다')

    def test_fixed_family_not_counted(self):
        # cover·quiz·closing 같은 고정 형식은 연속열에서 빠진다(세지도 끊지도 않는다)
        secs = ([fig_section('cover', inner='<p class="body">표지</p>')]
                + [fig_section('checklist', inner='<p class="body">본문</p>') for _ in range(3)]
                + [fig_section('quiz-ab', inner='<p class="body">퀴즈</p>')]
                + [fig_section('statement', inner='<p class="body">본문</p>')]
                + [fig_section('closing', inner='<p class="body">끝</p>')])
        rep = run_static(secs)
        self.assertFalse(kinds(rep, '텍스트 나열'),
                         '고정 형식 장은 텍스트도 시각도 아니다 — 나열에 안 잡힌다')

    def test_family_sets_disjoint_and_cover_archetypes(self):
        self.assertFalse(check_deck.VISUAL_ARCHS & check_deck.FIXED_ARCHS)
        self.assertTrue(check_deck.VISUAL_ARCHS <= check_deck.ARCHETYPES)
        self.assertTrue(check_deck.FIXED_ARCHS <= check_deck.ARCHETYPES)
        text = check_deck.ARCHETYPES - check_deck.VISUAL_ARCHS - check_deck.FIXED_ARCHS
        self.assertEqual(text, {'agenda', 'statement', 'frame-form', 'before-after',
                                'rules-dark', 'checklist'}, f'텍스트 계열 집합: {text}')


def build_mini():
    SRC.mkdir(parents=True, exist_ok=True)
    order = FIG_FAMILIES + ('28-sources',)
    srcs = []
    for i, stem in enumerate(order):
        text = (SNIPPETS / f'{stem}.html').read_text(encoding='utf-8')
        soup = BeautifulSoup(text, 'html.parser')
        sec = (soup.select_one('section.slide[data-variant="fig"]')
               if stem != '28-sources' else soup.select_one('section.slide'))
        for notes in sec.select('aside.notes'):
            notes.string = NOTES + ' 화면의 그림 자리를 살펴본 뒤 다음 장으로 이어갑니다.'
        p = SRC / f'{i + 1:02d}-{stem}.html'
        p.write_text(str(sec), encoding='utf-8')
        srcs.append(p)
    html = OUT / 'deck.html'
    build('fig-slot 시험', srcs, [S / 'assets/css'], [S / 'assets/icons'], html)
    return html


def build_pack_slot():
    """리소스팩 덱에 fig-slot 을 얹은 최소 팩 장 — 공용 슬롯이 팩 경로에도 탑재되는지."""
    SRC.mkdir(parents=True, exist_ok=True)
    sec = ('<section class="slide pack pack-editorial" data-design="editorial">'
           '<p class="pack-kicker">시험</p><h1 class="pack-prompt">그림 자리가 팩 덱에도 놓이는가</h1>'
           '<p class="pack-body" data-step="1">도식 문법으로 채운 그림입니다.</p>'
           f'<figure class="fig-slot" data-step="2">{SAMPLE_SVG}</figure>'
           f'<aside class="notes">{NOTES} 팩 덱의 그림 자리 계약을 확인합니다.</aside></section>')
    p = SRC / 'pack-fig.html'
    p.write_text(sec, encoding='utf-8')
    html = OUT / 'pack-deck.html'
    build('팩 fig 시험', [p], [S / 'assets/css'], [S / 'assets/icons'], html,
          resource_pack={'design': 'editorial', 'flow': 'problem'})
    return html


class BrowserTest(unittest.TestCase):
    """실제 렌더: 5변형 완성 표시·인쇄 완결·다크·팩 탑재."""

    @classmethod
    def setUpClass(cls):
        cls.html = build_mini()
        cls.pack_html = build_pack_slot()
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

    def test_five_variants_fully_visible(self):
        pg = self._page(self.html)
        for i in range(5):
            with self.subTest(slide=i):
                pg.evaluate(f'window.deckGo({i})')
                pg.wait_for_timeout(300)
                self._advance_all(pg)
                pg.wait_for_timeout(900)
                box = pg.evaluate(
                    "document.querySelectorAll('#stage>.slide')[%d]"
                    ".querySelector('.fig-slot').getBoundingClientRect().toJSON()" % i)
                self.assertGreater(box['width'], 300, 'fig-slot 이 화면에 넓게 보여야 한다')
                self.assertGreater(box['height'], 200)
                vb = pg.evaluate(
                    "document.querySelectorAll('#stage>.slide')[%d]"
                    ".querySelector('.fig-slot svg.dg').getBoundingClientRect().toJSON()" % i)
                self.assertGreater(vb['height'], 150, '견본 svg.dg 가 보인다')
        pg.context.close()

    def test_print_completeness(self):
        pg = self._page(self.html)
        pg.emulate_media(media='print')
        pg.wait_for_timeout(500)
        box = pg.evaluate(
            "document.querySelector('#stage>.slide .fig-slot')"
            ".getBoundingClientRect().toJSON()")
        self.assertGreater(box['height'], 200, '인쇄에서도 그림 자리가 완성 상태로 보인다')
        pg.context.close()

    def test_dark_slide_renders(self):
        pg = self._page(self.html)
        pg.evaluate('window.deckGo(4)')
        pg.wait_for_timeout(300)
        self._advance_all(pg)
        bg = pg.evaluate(
            "getComputedStyle(document.querySelectorAll('#stage>.slide')[4]).backgroundColor")
        self.assertNotIn('250,', bg, 'rules-dark fig 는 어두운 장')
        pg.context.close()

    def test_pack_deck_mounts_slot(self):
        pg = self._page(self.pack_html)
        self._advance_all(pg)
        pg.wait_for_timeout(600)
        box = pg.evaluate(
            "document.querySelector('.fig-slot').getBoundingClientRect().toJSON()")
        self.assertGreater(box['width'], 200, '팩 덱에도 fig-slot 이 탑재된다')
        pg.context.close()


class ShellTest(unittest.TestCase):
    """재생성된 두 셸에 .fig-slot 규칙이 있다."""

    def test_both_shells_carry_rule(self):
        for name in ('shell.html', 'pack-shell.html'):
            with self.subTest(shell=name):
                text = (S / 'assets' / name).read_text(encoding='utf-8')
                self.assertIn('.fig-slot{', text, f'{name} 에 .fig-slot 규칙 없음')
                self.assertIn('.fig-slot>svg.dg', text)
                self.assertIn('.fig-slot figcaption', text)


if __name__ == '__main__':
    unittest.main()
