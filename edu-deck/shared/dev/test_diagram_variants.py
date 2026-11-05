#!/usr/bin/env python3
"""도식·차트 조각 변형 확장 회귀 시험 (TASK-diagrams).

[목적] 16개 본문 도식·차트 조각 계열이 변형 5개 이상을 유지하고, 각 변형이
       ① 계열 data-archetype 을 유지(모션 시그니처 발화 보장) ② data-variant
       id 가 계열 안에서 유일 ③ 자리표시·발표 노트·단계 속성 계약을 지키고
       ④ 외부 자원·스크립트·SMIL 없이 정적 완결이다 — 를 잠근다.
[입력] assets/snippets/NN-이름.html 의 <section class="slide"> 단위.
[출력] 없음(단정문).
[주의] 변형의 도식 문법 차이는 픽셀 검증(TASK-diagrams-STATE.md 증거)이 맡고,
       이 시험은 구조 계약만 잠근다. 새 변형을 추가할 때 같은 계열 파일 안에
       section 을 넣는 규칙(새 파일·새 아키타입 금지)도 여기서 강제한다.
"""
import re
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

SHARED = Path(__file__).resolve().parents[1]
SNIPPETS = SHARED / 'assets' / 'snippets'

# 16계열 파일 -> 기대 data-archetype (과제 TASK-diagrams.md 목록)
FAMILIES = {
    '03-timeline': 'timeline',
    '04-map': 'map',
    '05-mechanism': 'mechanism',
    '06-traits-grid': 'traits-grid',
    '07-meter': 'meter',
    '08-compare-2': 'compare-2',
    '09-compare-table': 'compare-table',
    '10-hub': 'hub',
    '11-levels': 'levels',
    '12-tile-grid': 'tile-grid',
    '13-sequence': 'sequence',
    '14-mapping': 'mapping',
    '18-build-up': 'build-up',
    '31-stat-strip': 'stat-strip',
    '33-chart-bar': 'chart-bar',
    '34-chart-line': 'chart-line',
}
CHART_FAMILIES = {'33-chart-bar', '34-chart-line'}


def sections(stem):
    text = (SNIPPETS / f'{stem}.html').read_text(encoding='utf-8')
    soup = BeautifulSoup(text, 'html.parser')
    return text, soup.select('section.slide')


class DiagramVariantsTest(unittest.TestCase):

    def test_each_family_has_five_or_more_variants(self):
        for stem in FAMILIES:
            with self.subTest(stem=stem):
                _, secs = sections(stem)
                self.assertGreaterEqual(len(secs), 5, f'{stem}: {len(secs)}개 변형')

    def test_variants_keep_family_archetype_and_unique_ids(self):
        for stem, arch in FAMILIES.items():
            _, secs = sections(stem)
            ids = set()
            for sec in secs:
                with self.subTest(stem=stem, variant=sec.get('data-variant')):
                    self.assertEqual(sec.get('data-archetype'), arch,
                                     f'{stem} 변형이 계열 아키타입을 벗어남 — 시그니처 미발화')
                    vid = sec.get('data-variant')
                    if vid is not None:  # 기본 변형은 id 생략 관례
                        self.assertNotIn(vid, ids, f'{stem}: data-variant "{vid}" 중복')
                        ids.add(vid)

    def test_variant_structure_contracts(self):
        for stem in FAMILIES:
            text, secs = sections(stem)
            for i, sec in enumerate(secs):
                with self.subTest(stem=stem, idx=i):
                    self.assertIn('«', str(sec), f'{stem} 변형 {i}: 자리표시 없음')
                    self.assertTrue(sec.select_one('aside.notes'),
                                    f'{stem} 변형 {i}: 발표 노트 asdie.notes 없음')
                    self.assertIsNone(sec.find('script'), f'{stem} 변형 {i}: <script> 금지')
                    self.assertIsNone(sec.find('link'), f'{stem} 변형 {i}: 외부 link 금지')
                    self.assertIsNone(sec.find('animate'), f'{stem} 변형 {i}: SMIL 금지')
                    self.assertIsNone(sec.find('img'), f'{stem} 변형 {i}: img 금지(정적·라이선스)')
            # 파일 수준: CSS 애니메이션 선언 금지(정적 완결은 셸이 책임)
            with self.subTest(stem=stem, scope='file'):
                self.assertNotIn('@keyframes', text, f'{stem}: 조각 안 keyframes 금지')
                self.assertNotIn('animation:', text, f'{stem}: 조각 안 animation 금지')

    def test_step_attributes_are_numeric(self):
        for stem in FAMILIES:
            _, secs = sections(stem)
            for i, sec in enumerate(secs):
                for attr in ('data-step', 'data-only', 'data-lit', 'data-until'):
                    for el in sec.select(f'[{attr}]'):
                        with self.subTest(stem=stem, idx=i, attr=attr):
                            self.assertRegex(el[attr], r'^\d+$',
                                             f'{stem} 변형 {i}: {attr}="{el[attr]}" 비정수')

    def test_chart_variants_keep_source_convention(self):
        for stem in CHART_FAMILIES:
            text, secs = sections(stem)
            with self.subTest(stem=stem):
                # 모든 차트 변형의 수치 요소는 사실 id 자리표시 «Fxx» 를 유지
                self.assertIn('data-src="«F', text, f'{stem}: data-src 자리표시 소실')
            for i, sec in enumerate(secs):
                for el in sec.select('[data-src]'):
                    with self.subTest(stem=stem, idx=i, src=el['data-src']):
                        self.assertRegex(el['data-src'], r'^(«F\d+»|F\d+)$',
                                         f'{stem} 변형 {i}: data-src="{el["data-src"]}"')

    def test_aria_labels_on_svg_diagrams(self):
        for stem in FAMILIES:
            _, secs = sections(stem)
            for i, sec in enumerate(secs):
                for svg in sec.select('svg.dg'):
                    if svg.get('aria-hidden') == 'true':
                        continue
                    with self.subTest(stem=stem, idx=i):
                        self.assertTrue(svg.get('aria-label'),
                                        f'{stem} 변형 {i}: 도식 svg.dg aria-label 없음')


if __name__ == '__main__':
    unittest.main()
