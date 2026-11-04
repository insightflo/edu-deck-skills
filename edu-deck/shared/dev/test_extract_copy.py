#!/usr/bin/env python3
"""extract_copy.py 추출 → 편집 → 되돌리기 회귀 테스트.

실제 덱(im-human 산출물)을 /tmp 로 복사해 그 복사본에서만 실행한다 —
원본 덱 폴더는 절대 건드리지 않는다.
"""
import importlib
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from bs4 import BeautifulSoup
import os, tempfile
_TEST_OUT = Path(os.environ.get('EDU_DECK_TEST_OUT', str(Path(tempfile.gettempdir()) / 'edu-deck-dev-tests')))

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / 'scripts'))
extract_copy = importlib.import_module('extract_copy')

SRC_DECK = Path(os.environ.get('EDU_DECK_TEST_DECK', ''))
# 원본 덱 경로는 개인 작업 환경마다 다르므로 EDU_DECK_TEST_DECK 로 지정한다.


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)],
                          capture_output=True, text=True)


def tag_attrs(path):
    """태그 이름·속성 시퀀스 — 구조/속성이 바뀌지 않았는지 비교용."""
    soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
    return [(el.name, tuple(sorted(el.attrs.items()))) for el in soup.find_all(True)]


class ExtractCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('EDU_DECK_TEST_DECK') or not SRC_DECK.is_dir():
            raise unittest.SkipTest(f'회귀 원본 덱이 없습니다: {SRC_DECK}')
        cls.tmp = Path(tempfile.mkdtemp(prefix='edudeck-copy-'))
        cls.deck = cls.tmp / SRC_DECK.name
        shutil.copytree(SRC_DECK, cls.deck)
        r = run(SHARED / 'scripts' / 'extract_copy.py', cls.deck)
        assert r.returncode == 0, r.stderr
        cls.copy_md = cls.deck / 'qa' / 'copy' / 'copy.md'

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.md = self.copy_md.read_text(encoding='utf-8')

    def units(self):
        """덱 src 의 추출 단위 전부."""
        out = []
        for f in extract_copy.find_src(self.deck):
            for _t, sec_units in extract_copy.file_units(f)[0]:
                out.extend((f.name, u) for u in sec_units)
        return out

    def single_hit(self, fname, text):
        """원문이 src 파일에 딱 1곳 매치되는가(그래야 되돌리기가 보류하지 않는다)."""
        raw = (self.deck / 'src' / fname).read_text(encoding='utf-8')
        return len(list(extract_copy.raw_flex(text).finditer(raw))) == 1

    def test_extract_writes_located_lines(self):
        self.assertIn('# sha256 ', self.md)
        self.assertIn('### 화면', self.md)
        self.assertIn('### 노트', self.md)
        self.assertRegex(self.md, r'- \[\S+\.html:s\d{2}\|')
        self.assertRegex(self.md, r'- \[\S+\.html:n\d{2}\|aside\.notes\]')
        # svg 화면 글과 보호 단위(사실 칩·출처·지표)가 표시돼 있는가
        self.assertIn('svg>text', self.md)
        self.assertIn('·보호', self.md)

    def test_apply_changes_and_defers(self):
        units = self.units()
        # 화면 줄: 보호·태그섞임이 아니고 숫자·라틴·「」 없는 첫 줄 → 편집해도 반영돼야 한다
        plain = next((fn, u) for fn, u in units
                     if u['bucket'] == 's' and not u['protected'] and not u['mixed']
                     and not extract_copy.KEEP_NUM.search(u['text'])
                     and not extract_copy.KEEP_LATIN.search(u['text'])
                     and not extract_copy.KEEP_QUOTE.search(u['text'])
                     and self.single_hit(fn, u['text']))
        note = next((fn, u) for fn, u in units
                    if u['bucket'] == 'n' and not u['mixed']
                    and self.single_hit(fn, u['text']))
        # 숫자가 있는 화면 줄 → 숫자를 바꾸면 보류돼야 한다
        numeric = next((fn, u) for fn, u in units
                       if u['bucket'] == 's' and not u['protected'] and not u['mixed']
                       and extract_copy.KEEP_NUM.search(u['text']))

        before = {f.name: tag_attrs(f) for f in extract_copy.find_src(self.deck)}

        edited = self.md
        edited = re.sub(r'(\[' + re.escape(f'{plain[0]}:{plain[1]["key"]}') + r'\|[^\]]*\] ).*',
                        r'\g<1>화면 글을 사람 말투로 다듬은 문장입니다', edited, count=1)
        # 노트는 110~450자 계약이 있으므로 그 길이에 맞는 문장으로 바꾼다
        new_note = ('노트도 같은 방식으로 다듬은 문장입니다. 이 장에서는 먼저 화면의 제목을 읽고, '
                    '학습자가 지난 시간에 배운 내용과 어떻게 이어지는지 한마디로 짚어 줍니다. '
                    '그다음 중앙의 도식을 가리키며 각 요소가 무엇을 뜻하는지 차례로 설명하고, '
                    '마지막으로 다음 장에서 다룰 확인 문제를 미리 알려 줍니다.')
        edited = re.sub(r'(\[' + re.escape(f'{note[0]}:{note[1]["key"]}') + r'\|[^\]]*\] ).*',
                        lambda m: m.group(1) + new_note, edited, count=1)
        num_new = re.sub(r'\d', lambda m: '9' if m.group(0) != '9' else '8',
                         numeric[1]['text'], count=1)
        edited = re.sub(r'(\[' + re.escape(f'{numeric[0]}:{numeric[1]["key"]}') + r'\|[^\]]*\] ).*',
                        lambda m: m.group(1) + num_new, edited, count=1)
        ed = self.deck / 'qa' / 'copy' / 'copy.edited.md'
        ed.write_text(edited, encoding='utf-8')

        r = run(SHARED / 'scripts' / 'extract_copy.py', self.deck, '--apply', ed)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('changed=2', r.stdout)
        self.assertIn('보류=1', r.stdout)

        # 반영 확인: 두 줄만 바뀌고, 숫자 줄은 원문 그대로
        raw_plain = (self.deck / 'src' / plain[0]).read_text(encoding='utf-8')
        raw_note = (self.deck / 'src' / note[0]).read_text(encoding='utf-8')
        raw_num = (self.deck / 'src' / numeric[0]).read_text(encoding='utf-8')
        self.assertIn('화면 글을 사람 말투로 다듬은 문장입니다', raw_plain)
        self.assertIn('노트도 같은 방식으로 다듬은 문장입니다', raw_note)
        self.assertNotIn(num_new, raw_num)

        # 구조·속성 불변: 모든 파일의 태그/속성 시퀀스가 추출 전과 같아야 한다
        after = {f.name: tag_attrs(f) for f in extract_copy.find_src(self.deck)}
        self.assertEqual(before, after)

        report = (self.deck / 'qa' / 'copy' / 'apply-report.md').read_text(encoding='utf-8')
        self.assertIn('보류', report)
        self.assertIn('전:', report)

    def test_rebuild_and_check_clean(self):
        # 되돌리기가 끝난 복사본은 다시 조립해도 ERROR 0 이어야 한다
        import json
        out_name = json.loads((self.deck / 'deck.json').read_text(encoding='utf-8-sig'))['output']
        r = run(SHARED / 'scripts' / 'build_deck.py', self.deck)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.deck / out_name
        self.assertTrue(out.is_file(), f'조립 결과가 없습니다: {out_name}')
        r = run(SHARED / 'scripts' / 'check_deck.py', out, '--no-render')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('errors=0', r.stdout)


if __name__ == '__main__':
    unittest.main()
