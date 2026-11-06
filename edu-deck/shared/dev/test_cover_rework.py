#!/usr/bin/env python3
"""표지 개편 계약 시험 (TASK-cover-rework).

[목적] ① 기본 변형 01-cover.html 제거 + 명명 6종 유지 + 시안 10종 등재 = 16변형.
       ② 모든 표지가 cover 계약(data-archetype·data-variant·.cx-title·.cx-eyebrow·
       notes·cx-typed)을 지킨다.
       ③ 주제 비특정 장식 자리는 .cover-art 자리표시 그림이고, «…» 잔류는
       --allow-placeholders 없이 ERROR, 허용 시 조용하다.
       ④ 시안 10종은 고정 hex 0개·토큰만·외부 자원 0개다.
       ⑤ tone_router.COVERS 가 16종과 정확히 일치하고 변형 총수는 231이다.
[입력] assets/snippets/01-cover*.html + manifest 슬러그 목록 + 정적 조각 fixture.
[출력] 없음(단정문).
"""
import re
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
import check_deck  # noqa: E402
import tone_router  # noqa: E402

SNIPPETS = S / 'assets' / 'snippets'

# 유지된 명명 카탈로그 6종 + TASK-cover-rework 시안 10종(manifest slug)
BASE_SIX = ('bigstat', 'center', 'diagram', 'mosaic', 'split', 'stripes')
CONCEPT_TEN = ('editorial-lab', 'bold-poster', 'blueprint', 'monograph',
               'learning-path', 'paper-collage', 'workbook-notes',
               'future-portal', 'bauhaus', 'modular-cards')
ALL_SIXTEEN = BASE_SIX + CONCEPT_TEN

# 주제 비특정 장식 자리를 .cover-art 로 연 카탈로그 변형(4종)
ART_CONVERTED = ('center', 'diagram', 'mosaic', 'split')
# 뼈대가 곧 정체성이라 자리를 열지 않는 변형
ART_EXEMPT = ('bigstat', 'stripes', 'blueprint', 'bauhaus', 'workbook-notes',
              'future-portal', 'modular-cards', 'learning-path')

HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')
TOKEN = re.compile(r'var\(--[\w-]+\)')


def section_of(slug):
    path = SNIPPETS / f'01-cover-{slug}.html'
    soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
    return path, soup.select_one('section.slide')


def run_static(inner, allow=False):
    html = ('<!doctype html><html lang="ko"><head><title>t</title></head><body>'
            '<div id="stage"><section class="slide cx" data-archetype="cover" '
            'data-variant="center">' + inner + '</section></div></body></html>')
    rep = check_deck.Report()
    check_deck.static_checks(html, BeautifulSoup(html, 'html.parser'), rep, allow)
    return rep


class CatalogShapeTest(unittest.TestCase):
    """16변형 구성: 기본 제거 + 6종 유지 + 시안 10종."""

    def test_legacy_default_removed(self):
        self.assertFalse((SNIPPETS / '01-cover.html').exists(),
                         '기본 표지 조각이 남아 있다')

    def test_six_catalog_variants_kept(self):
        for slug in BASE_SIX:
            with self.subTest(slug=slug):
                self.assertTrue((SNIPPETS / f'01-cover-{slug}.html').exists(), slug)

    def test_ten_concepts_registered(self):
        for slug in CONCEPT_TEN:
            with self.subTest(slug=slug):
                self.assertTrue((SNIPPETS / f'01-cover-{slug}.html').exists(), slug)

    def test_exactly_sixteen_cover_files(self):
        files = sorted(SNIPPETS.glob('01-cover*.html'))
        self.assertEqual(len(files), 16, [f.name for f in files])

    def test_router_covers_match_catalog(self):
        self.assertEqual(set(tone_router.COVERS), set(ALL_SIXTEEN))

    def test_total_variant_count_231(self):
        n = 0
        for f in SNIPPETS.glob('*.html'):
            n += len(BeautifulSoup(
                f.read_text(encoding='utf-8'), 'html.parser').select('section.slide'))
        self.assertEqual(n, 231)


class CoverContractTest(unittest.TestCase):
    """표지 계약: 아키타입·변형·제목 훅·노트·자리표시·외부 자원 금지."""

    def test_archetype_variant_hooks(self):
        for slug in ALL_SIXTEEN:
            with self.subTest(slug=slug):
                path, sec = section_of(slug)
                self.assertEqual(sec.get('data-archetype'), 'cover', slug)
                self.assertEqual(sec.get('data-variant'), slug, slug)
                self.assertIsNotNone(sec.select_one('.cx-title'), slug)
                self.assertIsNotNone(sec.select_one('.cx-eyebrow'), slug)
                self.assertIsNotNone(sec.select_one('aside.notes'), slug)
                text = path.read_text(encoding='utf-8')
                self.assertIn('id="cx-typed"', text, slug)
                self.assertIn('data-text=', text, slug)
                self.assertIn('«', text, slug)

    def test_no_scripts_or_external_resources(self):
        for slug in ALL_SIXTEEN:
            with self.subTest(slug=slug):
                path, sec = section_of(slug)
                for tag in ('script', 'link', 'img', 'animate'):
                    self.assertIsNone(sec.find(tag), f'{slug}: {tag}')
                text = path.read_text(encoding='utf-8')
                self.assertNotIn('@keyframes', text, slug)
                self.assertNotIn('http://', text, slug)
                self.assertNotIn('https://', text, slug)
                self.assertNotIn('@font-face', text, slug)
                # url(#id) 는 같은 문서 안 svg 조각 참조 — 외부 url() 만 금지
                self.assertFalse(re.search(r'url\((?!#)', text), slug)

    def test_no_fixed_hex_anywhere(self):
        for slug in ALL_SIXTEEN:
            with self.subTest(slug=slug):
                text = (SNIPPETS / f'01-cover-{slug}.html').read_text(encoding='utf-8')
                self.assertFalse(HEX.search(text), HEX.findall(text))

    def test_tokens_used(self):
        for slug in ALL_SIXTEEN:
            with self.subTest(slug=slug):
                text = (SNIPPETS / f'01-cover-{slug}.html').read_text(encoding='utf-8')
                self.assertTrue(TOKEN.search(text), slug)

    def test_decorative_svgs_aria_hidden(self):
        for slug in ALL_SIXTEEN:
            with self.subTest(slug=slug):
                _, sec = section_of(slug)
                for svg in sec.find_all('svg'):
                    self.assertEqual(svg.get('aria-hidden'), 'true',
                                     f'{slug}: 장식 svg aria-hidden 누락')


class CoverArtTest(unittest.TestCase):
    """cover-art 그림 자리 계약: 변환분 4종 + 검사기 발화."""

    def test_converted_catalogs_have_art(self):
        for slug in ART_CONVERTED:
            with self.subTest(slug=slug):
                _, sec = section_of(slug)
                arts = sec.select('.cover-art')
                self.assertTrue(arts, slug)
                for art in arts:
                    self.assertEqual(art.get('aria-hidden'), 'true', slug)
                    self.assertIn('«그림', art.get_text(), slug)

    def test_custom_art_slots_use_placeholder_guidance(self):
        for slug in ('editorial-lab', 'bold-poster', 'paper-collage', 'monograph'):
            with self.subTest(slug=slug):
                _, sec = section_of(slug)
                arts = sec.select('.cover-art')
                self.assertTrue(arts, slug)
                for art in arts:
                    self.assertEqual(art.get('aria-hidden'), 'true', slug)
                    self.assertIn('«그림', art.get_text(), slug)

    def test_identity_covers_have_no_art(self):
        for slug in ART_EXEMPT:
            with self.subTest(slug=slug):
                _, sec = section_of(slug)
                self.assertFalse(sec.select('.cover-art'),
                                 f'{slug}: 뼈대가 정체성인 변형에 art 자리가 생겼다')

    def test_leftover_placeholder_is_error(self):
        art = ('<div class="cover-art" aria-hidden="true">'
               '<span>«그림: 주제 일러스트»</span></div>')
        rep = run_static(art)
        kinds = [i for i in rep.items if i['sev'] == 'ERROR' and i['kind'] == '표지 그림']
        self.assertTrue(kinds, rep.items)

    def test_placeholder_silent_when_allowed(self):
        art = ('<div class="cover-art" aria-hidden="true">'
               '<span>«그림: 주제 일러스트»</span></div>')
        rep = run_static(art, allow=True)
        kinds = [i for i in rep.items if i['kind'] == '표지 그림']
        self.assertFalse(kinds, rep.items)


if __name__ == '__main__':
    unittest.main()
