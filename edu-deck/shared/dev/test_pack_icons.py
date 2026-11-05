#!/usr/bin/env python3
"""팩 덱의 공용 아이콘 묶음·개념 도식 수용, 카드 가로줄 경고 회귀 검사."""
import contextlib
import importlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / 'scripts'))
build_deck = importlib.import_module('build_deck')
check_deck = importlib.import_module('check_deck')
from bs4 import BeautifulSoup  # noqa: E402

NOTES = 'x' * 160


def check_html(html, pack=False):
    # TASK-free-mode: 취향 규칙의 기존 심각도(WARN)를 검증하려면 --style 모드 리포트가 필요하다
    report = check_deck.Report(style=True)
    check_deck.static_checks(html, BeautifulSoup(html, 'html.parser'), report, pack)
    return [(item['sev'], item['kind']) for item in report.items]


class PackIconsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assets = self.root / 'shared' / 'assets'
        self.assets.mkdir(parents=True)
        self.deck = self.root / 'deck'
        (self.deck / 'src').mkdir(parents=True)
        (self.deck / 'src' / '01.html').write_text(
            '<section class="slide" data-archetype="mechanism">'
            '<p><svg class="ico" aria-hidden="true"><use href="#i-gear"/></svg> 톱니</p>'
            f'<aside class="notes">{NOTES}</aside></section>')
        self.original_base = build_deck.BASE
        build_deck.BASE = self.assets.parent
        self.addCleanup(setattr, build_deck, 'BASE', self.original_base)
        shutil.copy2(SHARED / 'assets' / 'pack-shell.html', self.assets / 'pack-shell.html')
        (self.assets / 'css').mkdir()
        shutil.copy2(SHARED / 'assets' / 'css' / 'pack-runtime.css', self.assets / 'css')
        pack = self.assets / 'packs' / 'editorial'
        pack.mkdir(parents=True)
        (pack.parent / 'base.css').write_text('/* PACK_BASE */')
        (pack / 'style.css').write_text('/* PACK_EDITORIAL */')
        (self.deck / 'deck.json').write_text(json.dumps({
            'title': 'Fixture', 'output': 'result.html',
            'resource_pack': {'design': 'editorial', 'flow': 'problem'}}))

    def run_build(self) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return build_deck.main([str(self.deck)])

    def test_pack_build_includes_shared_icon_sprite(self) -> None:
        icons = self.assets / 'icons'
        icons.mkdir()
        (icons / 'base.svg').write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><defs>'
            '<symbol id="i-gear" viewBox="0 0 100 100"><path d="M0 0L1 1"/></symbol>'
            '<marker id="ah-o" viewBox="0 0 10 10"><path d="M0 0L10 5L0 10Z"/></marker>'
            '</defs></svg>')
        self.assertEqual(self.run_build(), 0)
        result = (self.deck / 'result.html').read_text()
        self.assertIn('<symbol id="i-gear"', result)
        self.assertIn('<marker id="ah-o"', result)

    def test_pack_build_without_shared_icons_still_works(self) -> None:
        self.assertEqual(self.run_build(), 0)
        self.assertNotIn('<symbol', (self.deck / 'result.html').read_text())

    def test_pack_slide_accepts_labelled_concept_svg(self) -> None:
        html = ('<html><head><title>t</title>'
                '<meta name="edu-deck-resource-pack" content="{&quot;design&quot;:&quot;editorial&quot;,&quot;flow&quot;:&quot;problem&quot;}">'
                '</head><body><div id="stage">'
                '<section class="slide pack pack-editorial" data-design="editorial" data-archetype="build-up">'
                '<h1 class="pack-prompt">질문?</h1>'
                '<svg role="img" aria-label="개념 관계 설명" viewBox="0 0 100 100"></svg>'
                f'<aside class="notes">{NOTES}</aside></section></div></body></html>')
        self.assertNotIn(('WARN', '시각 짝'), check_html(html, pack=True))

    def test_pack_slide_without_visual_warns(self) -> None:
        html = ('<html><head><title>t</title>'
                '<meta name="edu-deck-resource-pack" content="{&quot;design&quot;:&quot;editorial&quot;,&quot;flow&quot;:&quot;problem&quot;}">'
                '</head><body><div id="stage">'
                '<section class="slide pack pack-editorial" data-design="editorial" data-archetype="build-up">'
                '<h1 class="pack-prompt">질문?</h1>'
                f'<aside class="notes">{NOTES}</aside></section></div></body></html>')
        self.assertIn(('WARN', '시각 짝'), check_html(html, pack=True))


class CardRowTests(unittest.TestCase):
    def deck(self, inner, arch='mechanism'):
        return ('<html><head><title>t</title></head><body><div id="stage">'
                f'<section class="slide" data-archetype="{arch}">{inner}'
                f'<aside class="notes">{NOTES}</aside></section></div></body></html>')

    def warns(self, html):
        return check_html(html)

    def test_card_row_without_diagram_warns(self) -> None:
        for parent in ('<div class="row">',
                       '<div style="display:grid;grid-template-columns:1fr 1fr 1fr">'):
            with self.subTest(parent=parent):
                html = self.deck(parent + '<div class="card">a</div>' * 3 + '</div>')
                self.assertIn(('WARN', '카드 나열'), self.warns(html))

    def test_vertical_card_stack_is_quiet(self) -> None:
        for parent in ('<div class="col">', '<div class="stack">'):
            with self.subTest(parent=parent):
                html = self.deck(parent + '<div class="card">a</div>' * 3 + '</div>')
                self.assertNotIn(('WARN', '카드 나열'), self.warns(html))

    def test_card_row_with_labelled_svg_is_quiet(self) -> None:
        html = self.deck(
            '<div class="row"><div class="card">a</div><div class="card">b</div><div class="card">c</div></div>'
            '<svg aria-label="개념 관계 설명" viewBox="0 0 100 100"></svg>')
        self.assertNotIn(('WARN', '카드 나열'), self.warns(html))

    def test_exempt_archetypes_do_not_warn(self) -> None:
        row = '<div class="row"><div class="card">a</div><div class="card">b</div><div class="card">c</div></div>'
        for arch in ('cover', 'statement', 'quiz-ab', 'quiz-ox', 'check',
                     'sources', 'closing', 'checklist', 'agenda'):
            with self.subTest(arch=arch):
                self.assertNotIn(('WARN', '카드 나열'), self.warns(self.deck(row, arch)))


if __name__ == '__main__':
    unittest.main()
