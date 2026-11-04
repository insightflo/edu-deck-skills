#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""koboyo_icons.py(손그림 IT 아이콘 도우미) 회귀 검사.

[검사 범위]
  search 검색·그룹 필터 / add 심볼 조립·멱등·정렬·40개 상한·모르는 slug /
  list / 갤러리 파일 없음(종료 코드 2) / 조립기(build_deck.py)와의 결합:
  덱에 추가한 심볼이 최종 HTML 에 들어가고, 넣은 것 외에 더 들어가지 않는다.

[입력]
  갤러리 파일은 스킬에 포함되지 않은 사용자 제공 자료다.
  환경변수 EDU_DECK_KOBOYO_LIB 또는 ~/Downloads/koboyo_gallery.html 이
  있을 때만 갤러리가 필요한 검사를 돌리고, 없으면 이유를 남기고 건너뛴다.
  (갤러리가 필요 없는 종료 코드 2 검사는 항상 돌린다.)

[출력]
  없음. 모든 검사는 임시 디렉터리에서 하고, 스킬 폴더에 갤러리를
  만들거나 복사하지 않는다.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import xml.dom.minidom
from pathlib import Path

SHARED = Path(__file__).resolve().parents[1]
SCRIPT = SHARED / 'scripts' / 'koboyo_icons.py'
BUILD = SHARED / 'scripts' / 'build_deck.py'
NOTES = 'x' * 160  # test_pack_icons.py 와 같은 발표자 노트 길이 관습
HEADER = ('<!-- Koboyo hand-drawn icons (koboyo.com/icons, free license; '
          '덱에 쓰는 아이콘만 복사) -->')

_LIB_CANDIDATES = (os.environ.get('EDU_DECK_KOBOYO_LIB'),
                   str(Path.home() / 'Downloads' / 'koboyo_gallery.html'))
LIB = next((c for c in _LIB_CANDIDATES if c and os.path.isfile(c)), None)


def run(args):
    """도우미 스크립트를 서브프로세스로 돌려 실제 종료 코드를 검사한다."""
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


def make_deck(root, slug):
    """최소 덱을 만든다. src/01.html 형식은 assets/snippets/29-closing.html 의
    <section class="slide">+aside.notes 관습을, 구성은 dev/test_pack_icons.py
    의 임시 덱 관습을 따른다."""
    deck = root / 'deck'
    (deck / 'src').mkdir(parents=True)
    (deck / 'deck.json').write_text(json.dumps(
        {'title': 'Koboyo 아이콘 검증 덱', 'output': 'result.html'}),
        encoding='utf-8')
    slide = ('<section class="slide" data-archetype="mechanism">'
             f'<p><svg class="ico" aria-hidden="true">'
             f'<use href="#kb-{slug}"/></svg> 인수 조건</p>'
             f'<aside class="notes">{NOTES}</aside></section>')
    (deck / 'src' / '01.html').write_text(slide, encoding='utf-8')
    return deck


def symbol_ids(text):
    return re.findall(r'id="kb-([^"]+)"', text)


@unittest.skipIf(LIB is None,
                 '갤러리 파일이 없어 스킵(사용자 제공 자료: '
                 '~/Downloads/koboyo_gallery.html 또는 EDU_DECK_KOBOYO_LIB)')
class KoboyoWithLibraryTests(unittest.TestCase):
    """갤러리 파일이 있을 때만 의미가 있는 동작 검사."""

    @classmethod
    def setUpClass(cls):
        result = run(['search', 'api', '--limit', '60'])
        if result.returncode != 0:
            raise AssertionError(f'search 기본 동작 실패: {result.stderr}')
        cls.slugs = [line.split('\t')[0]
                     for line in result.stdout.splitlines() if line.strip()]
        if len(cls.slugs) < 41:
            raise AssertionError('상한 검사에 필요한 slug 이 41개 미만입니다')

    def test_search_finds_acceptance_criterion(self):
        result = run(['search', 'acceptance-criterion'])
        self.assertEqual(result.returncode, 0)
        self.assertIn('acceptance-criterion\tdev\tacceptance criterion',
                      result.stdout)

    def test_search_requires_every_word_and_group(self):
        result = run(['search', 'api', 'endpoint'])
        self.assertEqual(result.returncode, 0)
        self.assertIn('api-endpoint', result.stdout)
        result = run(['search', 'api', '--group', 'sysdesign'])
        self.assertEqual(result.returncode, 0)
        for line in result.stdout.splitlines():
            if line.strip():
                self.assertEqual(line.split('\t')[1], 'sysdesign')
        result = run(['search', 'api', '--group', 'NoSuchGroup'])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')

    def test_add_and_build_includes_only_added_symbol(self):
        root = tempfile.mkdtemp(prefix='kb-deck-')
        self.addCleanup(_rmtree, root)
        deck = make_deck(Path(root), 'acceptance-criterion')
        result = run(['add', str(deck), 'acceptance-criterion'])
        self.assertEqual(result.returncode, 0, result.stderr)
        icon_file = deck / 'src' / 'koboyo-icons.svg'
        content = icon_file.read_text(encoding='utf-8')
        self.assertTrue(content.startswith(HEADER))
        self.assertEqual(symbol_ids(content), ['acceptance-criterion'])
        self.assertIn('fill="currentColor"', content)
        xml.dom.minidom.parseString(content)  # 중복 속성이 남으면 여기서 실패
        symbol = re.search(r'<symbol id="kb-acceptance-criterion".*?</symbol>',
                           content, re.S).group(0)
        self.assertNotIn('aria-label', symbol)
        self.assertNotIn('xmlns', symbol)
        self.assertNotIn('role=', symbol)

        build = subprocess.run([sys.executable, str(BUILD), str(deck)],
                               capture_output=True, text=True)
        self.assertEqual(build.returncode, 0, build.stderr)
        html = (deck / 'result.html').read_text(encoding='utf-8')
        self.assertEqual(html.count('id="kb-'), 1)  # 넣은 것 외엔 더 없음
        self.assertEqual(html.count('href="#kb-'), 1)
        self.assertIn('<symbol id="kb-acceptance-criterion"', html)

    def test_add_is_idempotent_and_sorted(self):
        root = tempfile.mkdtemp(prefix='kb-deck-')
        self.addCleanup(_rmtree, root)
        deck = make_deck(Path(root), self.slugs[0])
        picked = sorted(self.slugs[:3])
        self.assertEqual(run(['add', str(deck), *reversed(picked)]).returncode, 0)
        self.assertEqual(run(['add', str(deck), picked[0]]).returncode, 0)
        content = (deck / 'src' / 'koboyo-icons.svg').read_text(encoding='utf-8')
        self.assertEqual(symbol_ids(content), picked)  # 다시 넣어도 정렬·중복 없음

    def test_add_refuses_more_than_40_symbols(self):
        root = tempfile.mkdtemp(prefix='kb-deck-')
        self.addCleanup(_rmtree, root)
        deck = make_deck(Path(root), self.slugs[0])
        result = run(['add', str(deck), *self.slugs[:41]])
        self.assertEqual(result.returncode, 1)
        self.assertIn('최대 40개', result.stderr)
        self.assertFalse((deck / 'src' / 'koboyo-icons.svg').exists())

    def test_unknown_slug_exits_1_with_suggestions(self):
        root = tempfile.mkdtemp(prefix='kb-deck-')
        self.addCleanup(_rmtree, root)
        deck = make_deck(Path(root), self.slugs[0])
        bogus = 'zzz-no-such-icon'
        result = run(['add', str(deck), self.slugs[0], bogus])
        self.assertEqual(result.returncode, 1)
        self.assertIn(bogus, result.stderr)
        self.assertIn('비슷한 후보', result.stderr)
        self.assertFalse((deck / 'src' / 'koboyo-icons.svg').exists())

    def test_list_reports_symbols(self):
        root = tempfile.mkdtemp(prefix='kb-deck-')
        self.addCleanup(_rmtree, root)
        deck = make_deck(Path(root), self.slugs[0])
        missing = run(['list', str(deck)])
        self.assertEqual(missing.returncode, 1)
        self.assertEqual(run(['add', str(deck), self.slugs[0]]).returncode, 0)
        listed = run(['list', str(deck)])
        self.assertEqual(listed.returncode, 0)
        self.assertIn(f'kb-{self.slugs[0]}', listed.stdout)
        self.assertIn('symbols=1', listed.stdout)


class KoboyoMissingLibraryTests(unittest.TestCase):
    """갤러리 파일이 없어도 항상 돌아가는 검사(사용자 제공 자료 안내)."""

    def test_missing_lib_add_exits_2(self):
        root = tempfile.mkdtemp(prefix='kb-deck-')
        self.addCleanup(_rmtree, root)
        result = run(['add', root, 'some-slug',
                      '--lib', '/nonexistent/koboyo_gallery.html'])
        self.assertEqual(result.returncode, 2)
        self.assertIn('사용자 제공', result.stderr)

    def test_missing_lib_search_exits_2(self):
        result = run(['search', 'api',
                      '--lib', '/nonexistent/koboyo_gallery.html'])
        self.assertEqual(result.returncode, 2)
        self.assertIn('사용자 제공', result.stderr)


def _rmtree(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
