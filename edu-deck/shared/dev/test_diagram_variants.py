#!/usr/bin/env python3
"""전체 슬라이드 조각 계열의 변형과 A단계 실행 계약을 검사한다.

번호가 같은 조각 파일은 한 계열로 발견한다(표지처럼 여러 파일인 경우 포함).
02·17·20·30은 병행 B단계이므로 현재 개수만 보존하며, B 완료 뒤
EDU_DECK_ALL_VARIANTS_COMPLETE=1로 실행하면 모든 계열에 5개를 요구한다.
화면 인용(32)은 새 아키타입 대신 mapping/compare-2 호스트를 쓴다.
픽셀 차이는 이 구조/동작 시험과 별도의 인쇄 캡처 검증이다.
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SHARED = Path(__file__).resolve().parents[1]
SNIPPETS = SHARED / 'assets' / 'snippets'
sys.path.insert(0, str(SHARED / 'scripts'))
from build_deck import build
from check_deck import launch

A_FAMILIES = {'15', '16', '19', '23', '24', '25', '26', '27', '28', '29', '32', '35', '36'}
PENDING_B = {'02': 1, '17': 2, '20': 4, '30': 2,
             # TASK-workflow-series: 계약상 계열당 2변형(22장).
             '42': 2, '43': 2, '44': 2, '45': 2, '46': 2, '47': 2,
             '48': 2, '49': 2, '50': 2, '51': 2, '52': 2,
             # P3 visual-absorb: 판정(53)=3변형 · 실물 진단(54)=1변형
             '53': 3, '54': 1,
             # TASK-style-absorb: 창 프레임(55)=1변형 — 새 아키타입 대신 도식 호스트를 쓴다
             '55': 1}
LEGACY_VARIANTS = {'15': {'tour', 'cases'}, '19': {'form', 'rules'}, '32': {None, 'screens'}}
A_SIGNATURE = {'15': 'spotlight-pin', '16': 'selection-track', '19': 'outline-then-fill',
               '23': 'choice-verdict', '24': 'classification-lanes', '25': 'judgment-stamp',
               '26': 'spotlight-focus', '27': 'commitment-stamps', '28': 'evidence-align',
               '29': 'summary-convergence', '32': 'paired-connection', '35': 'grid-wave',
               '36': 'accumulating-pieces'}


def families():
    result = {}
    for path in sorted(SNIPPETS.glob('[0-9][0-9]-*.html')):
        family = path.name[:2]
        text = path.read_text(encoding='utf-8')
        for sec in BeautifulSoup(text, 'html.parser').select('section.slide'):
            result.setdefault(family, []).append((path, sec))
    return result


def new_a_variants(groups):
    for family in sorted(A_FAMILIES):
        legacy = LEGACY_VARIANTS.get(family, {None})
        for path, sec in groups[family]:
            if sec.get('data-variant') not in legacy:
                yield family, path, sec


class DiagramVariantsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.groups = families()

    def test_each_discovered_family_has_the_required_variants(self):
        self.assertEqual(set(self.groups), {f'{n:02}' for n in range(1, 56)})
        all_complete = os.environ.get('EDU_DECK_ALL_VARIANTS_COMPLETE') == '1'
        for family, variants in self.groups.items():
            required = 5 if all_complete else PENDING_B.get(family, 5)
            with self.subTest(family=family):
                self.assertGreaterEqual(len(variants), required)

    def test_variants_keep_family_archetypes_and_unique_ids(self):
        for family, variants in self.groups.items():
            names = set()
            for path, sec in variants:
                variant = sec.get('data-variant')
                with self.subTest(family=family, variant=variant):
                    self.assertNotIn(variant, names)
                    names.add(variant)
                    if family == '01': expected = {'cover'}
                    elif family == '22': expected = {'worked-example'}
                    elif family == '32': expected = {'mapping', 'compare-2'}
                    elif family == '55': expected = {'mapping'}
                    else: expected = {path.stem[3:]}
                    self.assertIn(sec.get('data-archetype'), expected)

    def test_variant_structure_contracts(self):
        for family, variants in self.groups.items():
            for path, sec in variants:
                with self.subTest(family=family, variant=sec.get('data-variant')):
                    self.assertIn('«', str(sec))
                    self.assertIsNotNone(sec.select_one('aside.notes'))
                    for tag in ('script', 'link', 'animate'):
                        self.assertIsNone(sec.find(tag), tag)
                    if family != '32': self.assertIsNone(sec.find('img'))
                    else:
                        for image in sec.select('.screen-cite img'):
                            self.assertIn('«사용자가 제공한 화면 이미지', image.get('src', ''))
                            self.assertTrue(image.get('alt'))
                    text = path.read_text(encoding='utf-8')
                    self.assertNotIn('@keyframes', text)
                    self.assertNotIn('animation:', text)

    def test_step_attributes_are_numeric(self):
        for family, variants in self.groups.items():
            for _, sec in variants:
                for attr in ('data-step', 'data-add', 'data-only', 'data-lit', 'data-until'):
                    for el in sec.select(f'[{attr}]'):
                        with self.subTest(family=family, variant=sec.get('data-variant'), attr=attr):
                            self.assertRegex(el[attr], r'^\d+$')

    def test_chart_variants_keep_source_convention(self):
        for family in ('33', '34'):
            for _, sec in self.groups[family]:
                self.assertTrue(sec.select('[data-src]'), family)
                for el in sec.select('[data-src]'):
                    self.assertRegex(el['data-src'], r'^(«F\d+»|F\d+)$')

    def test_aria_labels_on_svg_diagrams(self):
        for family, variants in self.groups.items():
            for _, sec in variants:
                for svg in sec.select('svg.dg'):
                    if svg.get('aria-hidden') != 'true':
                        self.assertTrue(svg.get('aria-label'), (family, sec.get('data-variant')))

    def test_new_variants_steps_and_source_pairs(self):
        added = list(new_a_variants(self.groups))
        self.assertGreaterEqual(len(added), 49)
        for family, _, sec in added:
            with self.subTest(family=family, variant=sec.get('data-variant')):
                steps = {int(el['data-step']) for el in sec.select('[data-step]')}
                self.assertTrue(2 <= len(steps) <= 4, steps)
                if family == '28':
                    lines = sec.select('.src-list li[data-src]')
                    self.assertGreaterEqual(len(lines), 2)
                    for line in lines:
                        self.assertRegex(line['data-src'], r'^F\d+$')
                        self.assertGreaterEqual(len(line.select('a[href]')), 2)

    def test_new_variants_actual_motion_and_interaction(self):
        added = list(new_a_variants(self.groups))
        with tempfile.TemporaryDirectory(prefix='edu-snippet-variants-') as d:
            root = Path(d)
            srcs = []
            # Self-authored single-pixel PNG is only a browser-test fixture.
            image = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC'
                     'AAAAC0lEQVR42mP8/x8AAwMCAO+/aN8AAAAASUVORK5CYII=')
            for i, (_, _, original) in enumerate(added):
                sec = BeautifulSoup(str(original), 'html.parser').select_one('section.slide')
                for el in sec.select('.screen-cite img'): el['src'] = image
                path = root / f'{i:03}.html'
                path.write_text(str(sec), encoding='utf-8')
                srcs.append(path)
            out = root / 'deck.html'
            build('변형 실행 검증', srcs, [SHARED / 'assets/css'], [SHARED / 'assets/icons'], out)
            with sync_playwright() as pw:
                browser = launch(pw)
                try:
                    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(out.as_uri())
                    page.evaluate("""() => { window.variantEvents = []; document.addEventListener('edumotion',
                        e => window.variantEvents.push({slide:e.detail.slide, sig:e.detail.sig})); }""")
                    for i, (family, _, sec) in enumerate(added):
                        with self.subTest(family=family, variant=sec.get('data-variant')):
                            slide = page.locator('#stage > .slide').nth(i)
                            page.evaluate('i => deckGo(i,0)', i)
                            page.wait_for_timeout(40)
                            if family in {'23', '24', '25'}:
                                before = slide.locator('[data-step="2"]').evaluate_all(
                                    '(es)=>es.filter(e=>getComputedStyle(e).visibility!=="hidden" && getComputedStyle(e).display!=="none").length')
                                self.assertEqual(before, 0, '정답 공개 전 단계에 답이 보임')
                                if family == '23':
                                    styles = slide.locator('.opt').evaluate_all(
                                        '(es)=>es.map(e=>[e.classList.contains("lit"),getComputedStyle(e).backgroundColor,getComputedStyle(e).borderColor])')
                                    self.assertTrue(all(not item[0] for item in styles))
                                    self.assertEqual(len({tuple(item[1:]) for item in styles}), 1)
                            page.evaluate('i => deckGo(i,1)', i)
                            page.wait_for_timeout(40)
                            page.evaluate('i => deckGo(i,2)', i)
                            page.wait_for_timeout(40)
                            if family == '23':
                                self.assertTrue(slide.locator('.opt.right.lit').count())
                            if family == '35':
                                for chip in slide.locator('.expl-chip').all():
                                    wanted = chip.get_attribute('data-x')
                                    chip.click()
                                    self.assertEqual(slide.locator('.expl-state.on').get_attribute('data-x'), wanted)
                            if family == '36':
                                for opener in slide.locator('.dsheet-open').all():
                                    wanted = opener.get_attribute('data-open')
                                    opener.click()
                                    self.assertEqual(slide.locator('.dsheet-panel.on').get_attribute('data-sheet'), wanted)
                                    page.keyboard.press('Escape')
                                    self.assertEqual(slide.locator('.dsheet-panel.on').count(), 0)
                            if family == '27':
                                todo = slide.locator('.todo').first
                                todo.click()
                                self.assertIn('done', todo.get_attribute('class').split())
                    events = page.evaluate('window.variantEvents')
                    for i, (family, _, sec) in enumerate(added):
                        self.assertTrue(any(e['slide'] == i and e['sig'] == A_SIGNATURE[family] for e in events),
                                        (family, sec.get('data-variant'), A_SIGNATURE[family]))
                    page.emulate_media(media='print')
                    for i, (family, _, sec) in enumerate(added):
                        if family not in {'35', '36'}: continue
                        selector = '.expl-state' if family == '35' else '.dsheet-panel'
                        result = page.locator('#stage > .slide').nth(i).locator(selector).evaluate_all(
                            '(es)=>es.map(e=>({display:getComputedStyle(e).display,visibility:getComputedStyle(e).visibility,bottom:e.getBoundingClientRect().bottom,slide:e.closest(".slide").getBoundingClientRect().bottom}))')
                        self.assertTrue(result, (family, sec.get('data-variant')))
                        for item in result:
                            self.assertNotEqual(item['display'], 'none')
                            self.assertNotEqual(item['visibility'], 'hidden')
                            self.assertLessEqual(item['bottom'], item['slide'] + 1, (family, sec.get('data-variant')))
                    page.emulate_media(media='screen')
                    page.evaluate('studyApi.selfstudy(true)')
                    for i, (family, _, sec) in enumerate(added):
                        if family not in {'23', '24', '25', '35', '36'}: continue
                        page.evaluate('i => deckGo(i,0)', i)
                        if family in {'23', '24', '25'}:
                            leaked = page.locator('#stage > .slide').nth(i).locator('[data-step="2"]').evaluate_all(
                                '(es)=>es.filter(e=>getComputedStyle(e).visibility!=="hidden" && getComputedStyle(e).display!=="none").length')
                            self.assertEqual(leaked, 0, (family, sec.get('data-variant'), '자습 중 정답 조기 공개'))
                        else:
                            selector = '.expl-state' if family == '35' else '.dsheet-panel'
                            result = page.locator('#stage > .slide').nth(i).locator(selector).evaluate_all(
                                '(es)=>es.map(e=>[getComputedStyle(e).display,getComputedStyle(e).visibility])')
                            self.assertTrue(result)
                            self.assertTrue(all(x[0] != 'none' and x[1] != 'hidden' for x in result), (family, sec.get('data-variant')))
                    self.assertFalse(errors, errors)
                finally:
                    browser.close()


if __name__ == '__main__':
    unittest.main()
