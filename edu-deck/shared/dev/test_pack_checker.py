#!/usr/bin/env python3
"""Pack checker regression tests: real static parsing and optional browser geometry."""
import html
import importlib
import json
from pathlib import Path
import sys
import unittest

from bs4 import BeautifulSoup

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / 'scripts'))
checker = importlib.import_module('check_deck')

NOTES = '학습자가 근거를 먼저 읽고 자신의 판단을 설명하도록 기다립니다. ' * 4
META = {'design': 'editorial', 'flow': 'problem'}


def slide(attrs='class="slide pack pack-editorial" data-design="editorial"', content=None):
    if content is None:
        content = '<h1 class="pack-prompt">어떤 문제인가요?</h1><p class="pack-body">본문</p>'
    return f'<section {attrs}>{content}<aside class="notes">{NOTES}</aside></section>'


def document(slides, selection=META):
    meta = '' if selection is None else (
        '<meta name="edu-deck-resource-pack" content="'
        + html.escape(json.dumps(selection), quote=True) + '">')
    return f'<html><head><title>교육</title>{meta}</head><body><div id="stage">{slides}</div></body></html>'


def check(text):
    report = checker.Report()
    checker.static_checks(text, BeautifulSoup(text, 'html.parser'), report, False)
    return report


class PackCheckerTests(unittest.TestCase):
    def test_valid_pack_uses_question_as_title_without_legacy_storyline(self):
        report = check(document(slide() * 15))
        self.assertEqual(report.count('ERROR'), 0, report.lines())
        self.assertEqual(report.slide_meta[1][1], '어떤 문제인가요?')
        self.assertFalse([i for i in report.items if i['kind'] == '흐름'], report.lines())

    def test_missing_metadata_is_not_a_pack_bypass(self):
        report = check(document(slide(), None))
        self.assertTrue([i for i in report.items if i['kind'] == '리소스팩' and i['sev'] == 'ERROR'])

    def test_invalid_metadata_rejected_even_with_valid_legacy_archetype(self):
        legacy = slide('class="slide" data-archetype="agenda"')
        for value in ({}, [], None, {'design': 'fake', 'flow': 'problem'},
                      {'design': 'editorial', 'flow': 'fake'},
                      {'design': 'editorial', 'flow': 'problem', 'activities': ['problem']}):
            with self.subTest(value=value):
                # JSON null must remain present, unlike document(..., None).
                text = document(legacy).replace(html.escape(json.dumps(META), quote=True),
                                                html.escape(json.dumps(value), quote=True))
                self.assertGreater(check(text).count('ERROR'), 0)

    def test_malformed_json_and_duplicate_metadata_rejected(self):
        text = document(slide())
        bad = text.replace(html.escape(json.dumps(META), quote=True), '{broken')
        self.assertGreater(check(bad).count('ERROR'), 0)
        duplicate = text.replace('</head>', '<meta name="edu-deck-resource-pack" content="{}"></head>')
        self.assertGreater(check(duplicate).count('ERROR'), 0)

    def test_metadata_alone_cannot_disable_legacy_storyline(self):
        report = check(document(slide('class="slide" data-archetype="statement"')))
        self.assertGreater(report.count('ERROR'), 0)
        self.assertTrue([i for i in report.items if i['kind'] == '흐름'])

    def test_malformed_pack_slides_rejected(self):
        variants = [
            'class="slide pack pack-editorial"',
            'class="slide pack pack-editorial" data-design="bogus"',
            'class="slide pack pack-lab" data-design="lab"',
            'class="slide pack" data-design="editorial"',
            'class="slide pack-editorial" data-design="editorial"',
            'class="slide pack pack-editorial pack-lab" data-design="editorial"',
            'class="slide pack pack-editorial" data-design="editorial" data-archetype="bogus"',
            'class="slide"',
        ]
        for attrs in variants:
            with self.subTest(attrs=attrs):
                self.assertGreater(check(document(slide() + slide(attrs))).count('ERROR'), 0)

    def test_plain_utility_slide_cannot_bypass_pack_identity(self):
        for arch in ('sources', 'check', 'closing'):
            with self.subTest(arch=arch):
                report = check(document(slide() + slide(f'class="slide" data-archetype="{arch}"')))
                self.assertTrue([i for i in report.items if i['kind'] == '리소스팩'
                                 and i['sev'] == 'ERROR' and i['slide'] == 2], report.lines())

    def test_pack_needs_nonempty_prompt(self):
        for content in ('<p>본문만</p>', '<h1 class="pack-prompt"> </h1>'):
            with self.subTest(content=content):
                self.assertGreater(check(document(slide(content=content))).count('ERROR'), 0)

    def test_utility_archetypes_remain_valid_and_sources_links_allowed(self):
        for arch in ('sources', 'check', 'quiz-ab', 'quiz-sort', 'quiz-ox', 'closing'):
            content = '<h1 class="pack-prompt">참고</h1>'
            if arch == 'sources':
                content += '<a href="https://example.org">출처</a>'
            if arch == 'check':
                content += ('<div class="chk"><p class="chk-q">질문</p>'
                            '<button class="chk-o" data-ok>맞음</button>'
                            '<button class="chk-o">아님</button><p class="chk-why">해설</p></div>')
            report = check(document(slide() + slide(f'class="slide pack pack-editorial" data-design="editorial" data-archetype="{arch}"', content)))
            self.assertEqual(report.count('ERROR'), 0, report.lines())

    def test_pack_retains_notes_steps_scripts_external_and_placeholder_checks(self):
        text = document(slide(content='<h1 class="pack-prompt">«제목»</h1>'
                              '<p data-step="x">본문</p><script>alert(1)</script>'
                              '<img src="https://example.org/a.png">'))
        text = text.replace(NOTES, '')
        kinds = {i['kind'] for i in check(text).items if i['sev'] == 'ERROR'}
        self.assertTrue({'발표자 노트', '단계 값', '스크립트', '외부 자원', '자리표시'} <= kinds)

    def test_pack_title_length_warning(self):
        report = check(document(slide(content='<h1 class="pack-prompt">' + '가' * 31 + '</h1>')))
        self.assertTrue([i for i in report.items if i['kind'] == '제목'])

    def test_legacy_missing_unknown_archetype_and_flow_checks_preserved(self):
        for attrs in ('class="slide"', 'class="slide" data-archetype="fake"'):
            report = check(document(slide(attrs), None))
            self.assertTrue([i for i in report.items if i['kind'] == '아키타입'])
        report = check(document(slide('class="slide" data-archetype="statement"') * 15, None))
        self.assertEqual(len([i for i in report.items if i['kind'] == '흐름']), 4)
        self.assertEqual(report.count('ERROR'), 0, report.lines())

    def test_legacy_valid_storyline_unchanged(self):
        text = ''.join(slide(f'class="slide" data-archetype="{a}"', '<h1 class="title">제목</h1>' + ('<div class="rm"><div class="rm-col">순서 1</div><div class="rm-col">순서 2</div></div>' if a == 'agenda' else ''))
                       for a in ('cover', 'agenda', 'quiz-ab', 'sources', 'closing'))
        report = check(document(text, None))
        self.assertEqual(report.items, [])
        self.assertEqual(report.slide_meta[1], ('cover', '제목'))

    def test_all_installed_pack_templates_satisfy_structure(self):
        for design in ('editorial', 'lab', 'field', 'casebook', 'atlas', 'workbook', 'briefing', 'seminar'):
            with self.subTest(design=design):
                text = (SHARED / 'assets' / 'packs' / design / 'template.html').read_text()
                for key in ('TITLE', 'KICKER', 'PROMPT', 'BODY', 'EVIDENCE', 'ACTION'):
                    text = text.replace('{{' + key + '}}', '검증할 학습 내용')
                report = check(document(text, {'design': design, 'flow': 'inquiry'}))
                self.assertEqual(report.count('ERROR'), 0, report.lines())


class PackGeometryTests(unittest.TestCase):
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

    def findings(self, content, css='', archetype=''):
        page = self.browser.new_page(viewport={'width': 1920, 'height': 1080})
        self.addCleanup(page.close)
        page.set_content('<style>.slide{width:1920px;height:1080px;background:white;color:black;}'
                         '.notes{display:none}p{margin:0;font-size:24px}' + css + '</style>'
                         + document(slide(attrs='class="slide pack pack-editorial" data-design="editorial" '
                                          + archetype, content=content)))
        return page.evaluate(checker.RENDER_JS, [0, True])

    def test_transparent_pack_container_overflow_detected(self):
        result = self.findings('<article class="editorial-story"><p>넘치는 본문</p></article>',
                               '.editorial-story{width:100px;height:30px}p{width:300px}')
        self.assertIn('상자 밖 넘침', {i['kind'] for i in result})

    def test_pack_cover_archetype_cannot_disable_overflow(self):
        result = self.findings('<p>화면 밖 본문</p>', 'p{width:3000px}', 'data-archetype="cover"')
        self.assertIn('화면 밖 넘침', {i['kind'] for i in result})

    def test_typography_contrast_and_clipping_still_checked(self):
        result = self.findings('<article style="overflow:hidden;width:100px;height:20px">'
                               '<p>본문이 상자에서 잘립니다</p></article>',
                               'p{width:300px;font-size:12px;color:#eee}')
        self.assertTrue({'잘린 글자', '글자 크기', '대비'} <= {i['kind'] for i in result})


if __name__ == '__main__':
    unittest.main()
