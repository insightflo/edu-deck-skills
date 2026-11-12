#!/usr/bin/env python3
"""Standard-library tests for the P1-3 pack preview (preview_pack.py).

Fixtures isolate the pack assets behind a fake shared tree; the real
check_deck.py/resource_packs.py are copied in so the static gate runs
hermetically without a browser. Record tests also run the installed CLI.
"""
import contextlib
import importlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILLS = Path(__file__).resolve().parents[3]  # …/skills (dev → shared → edu-deck → skills)
SHARED = SKILLS / 'edu-deck' / 'shared'
sys.path.insert(0, str(SHARED / 'scripts'))
sys.path.insert(0, str(SKILLS / 'edu-deck-solo' / 'scripts'))
preview_pack = importlib.import_module('preview_pack')

SHELL = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{{TITLE}}</title>'
         '<style>/*EXTRA_CSS*/</style></head><body><!--STUDY_DATA-->'
         '<div id="stage"><!--ICONS--><!--SLIDES--></div></body></html>')
TEMPLATE = ('<section class="slide pack pack-__DESIGN__" data-design="__DESIGN__" data-archetype="map">'
            '<header class="pack-topline"><p class="pack-topic">{{TITLE}}</p>'
            '<span class="pack-mark">FIXTURE</span></header>'
            '<p class="pack-kicker">{{KICKER}}</p><h1 class="pack-prompt">{{PROMPT}}</h1>'
            '<p class="pack-body">{{BODY}}</p><p class="pack-evidence">{{EVIDENCE}}</p>'
            '<p class="pack-action">{{ACTION}}</p>'
            '<aside class="notes">{{KICKER}} 템플릿 노트 기본 문장. {{BODY}} 확인: {{EVIDENCE}} 활동: {{ACTION}}</aside>'
            '</section>')
FLOW = {"flows": [{"id": "problem", "stages": [
    {"title": "첫 단계", "prompt": "첫 질문인가요?", "body": "첫 단계 본문 설명입니다.", "evidence": "첫 단계 근거입니다.", "action": "첫 단계 활동입니다."},
    {"title": "둘 단계", "prompt": "둘 질문인가요?", "body": "둘 단계 본문 설명입니다.", "evidence": "둘 단계 근거입니다.", "action": "둘 단계 활동입니다."},
    {"title": "셋 단계", "prompt": "셋 질문인가요?", "body": "셋 단계 본문 설명입니다.", "evidence": "셋 단계 근거입니다.", "action": "셋 단계 활동입니다."}]}]}
REASON = ('청중이 비전공 현장 직원이라 개념의 구조를 먼저 봐야 하고, '
          '교육 뒤 스스로 관계를 그려 설명하는 수행 행동이 성과 증거이므로 이 팩을 후보로 넣습니다.')


class PreviewFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.shared = self.root / 'shared'
        (self.shared / 'assets' / 'css').mkdir(parents=True)
        (self.shared / 'assets' / 'packs').mkdir(parents=True)
        (self.shared / 'scripts').mkdir(parents=True)
        (self.shared / 'assets' / 'pack-shell.html').write_text(SHELL, encoding='utf-8')
        (self.shared / 'assets' / 'css' / 'pack-runtime.css').write_text('.slide{display:none}\n', encoding='utf-8')
        (self.shared / 'assets' / 'css' / 'tokens.css').write_text(
            ':root{--ink:#202b32;--paper:#fffdf8}\n'
            '.slide.pack-atlas{--accent:#245b72;--accent-text:#204b69}\n'
            '.slide.pack-seminar{--accent:#7d4b39;--accent-text:#693e30}\n', encoding='utf-8')
        (self.shared / 'assets' / 'packs' / 'base.css').write_text(
            '.slide.pack{padding:64px}\n.pack .pack-prompt{font-size:52px}\n.pack .pack-topic{color:var(--soft)}\n',
            encoding='utf-8')
        catalog = {"designs": [
            {"id": d, "name": f"팩{d}"} for d in ('atlas', 'seminar', 'workbook')]}
        (self.shared / 'assets' / 'packs' / 'catalog.json').write_text(
            json.dumps(catalog, ensure_ascii=False), encoding='utf-8')
        (self.shared / 'assets' / 'packs' / 'flows.json').write_text(
            json.dumps(FLOW, ensure_ascii=False), encoding='utf-8')
        for design in ('atlas', 'seminar', 'workbook'):
            pack_dir = self.shared / 'assets' / 'packs' / design
            pack_dir.mkdir()
            (pack_dir / 'template.html').write_text(
                TEMPLATE.replace('__DESIGN__', design), encoding='utf-8')
            (pack_dir / 'style.css').write_text(
                f'.slide.pack-{design}{{gap:24px}}\n.{design}-box{{border:2px solid var(--accent)}}\n', encoding='utf-8')
        for name in ('check_deck.py', 'resource_packs.py', 'diagram_lint.py'):
            shutil.copy(SHARED / 'scripts' / name, self.shared / 'scripts' / name)
        self.original_shared = preview_pack.SHARED
        preview_pack.SHARED = self.shared
        self.addCleanup(setattr, preview_pack, 'SHARED', self.original_shared)
        self.folder = self.root / 'work'
        self.folder.mkdir()
        self.candidates = [('atlas', REASON), ('seminar', '근거 두 번째.' + REASON), ('workbook', '근거 세 번째.' + REASON)]

    def make(self, **overrides):
        kwargs = dict(folder=self.folder, title='프리뷰 시험', flow='problem', stage_no=3,
                      candidates=self.candidates, recommend='atlas',
                      content={'cover': {}, 'rep': {}}, gate_args=['--no-render'])
        kwargs.update(overrides)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return preview_pack.make_preview(**kwargs)


class MakePreviewTests(PreviewFixture):
    def test_three_packs_two_slides_each_with_gate_pass(self) -> None:
        ok, result, preview = self.make()
        self.assertTrue(ok, result)
        self.assertTrue(preview.is_file())
        text = preview.read_text(encoding='utf-8')
        sections = re.findall(r'<section class="([^"]*)"[^>]*data-archetype="([^"]*)"', text)
        self.assertEqual(len(sections), 8)
        self.assertEqual(sections[0], ('slide pv pv-guide', 'agenda'))
        self.assertEqual(sections[-1], ('slide pv pv-guide', 'closing'))
        for offset, (design, _) in enumerate(self.candidates):
            cover, rep = sections[1 + offset * 2:3 + offset * 2]
            self.assertEqual(cover, (f'slide pv pv-{design}', 'cover'))
            self.assertEqual(rep, (f'slide pv pv-{design}', 'map'))  # 템플릿 원형 아키타입 유지
        self.assertNotIn('data-design', text)
        self.assertNotIn('{{', text)  # 토큰 전부 치환
        self.assertIn('<h1 class="pack-prompt">프리뷰 시험</h1>', text)  # 표지 PROMPT=제목
        self.assertIn('셋 질문인가요?', text)  # 대표 장=--stage 3 흐름 값
        for design, reason in self.candidates:
            self.assertIn(f'후보 근거: {reason}', text)  # 노트에 후보 근거 표기
        self.assertIn('답이 없으면', text)  # 무응답 시 추천 진행 안내
        check = json.loads((self.folder / 'qa' / 'preview-check.json').read_text(encoding='utf-8'))
        self.assertEqual(check['result'], 'PASS')
        spec = json.loads((self.folder / 'preview-candidates.json').read_text(encoding='utf-8'))
        self.assertEqual(spec['recommend'], 'atlas')
        self.assertEqual([c['design'] for c in spec['candidates']], ['atlas', 'seminar', 'workbook'])

    def test_css_is_scoped_to_preview_classes(self) -> None:
        ok, _, preview = self.make()
        self.assertTrue(ok)
        css = preview.read_text(encoding='utf-8')
        self.assertNotIn('.slide.pack{', css)
        self.assertNotIn('.slide.pack-atlas', css)
        self.assertIn('.slide.pv{', css)                       # base.css 섹션 클래스 변환
        self.assertIn('.pv .pack-prompt', css)                 # 내용 클래스는 유지
        self.assertIn('.slide.pv-atlas{gap:24px}', css)        # 팩 스타일 변환
        self.assertIn('.slide.pv-atlas{--accent:#245b72', css)  # 토큰 오버라이드 변환

    def test_gate_blocks_placeholder_preview(self) -> None:
        broken = self.shared / 'assets' / 'packs' / 'atlas' / 'template.html'
        broken.write_text(broken.read_text(encoding='utf-8').replace('{{BODY}}', '«자리표시»'),
                          encoding='utf-8')
        ok, result, _ = self.make()
        self.assertFalse(ok)
        self.assertIn('FAIL', result)

    def test_pack_count_and_recommend_validation(self) -> None:
        with self.assertRaises(preview_pack.PreviewError):
            preview_pack.parse_packs(['atlas', 'seminar'], ['a', 'b'])
        with self.assertRaises(preview_pack.PreviewError):
            preview_pack.parse_packs(['atlas', 'atlas', 'seminar'], ['a', 'b', 'c'])
        with self.assertRaises(preview_pack.PreviewError):
            preview_pack.parse_packs(['atlas', 'seminar', 'nope'], ['a', 'b', 'c'])


class RecordChoiceTests(PreviewFixture):
    def setUp(self) -> None:
        super().setUp()
        self.ok, _, _ = self.make()
        self.deck = self.folder / 'deck.json'
        self.deck.write_text(json.dumps(
            {'title': '프리뷰 시험', 'output': 'deck.html',
             'resource_pack': {'design': 'atlas', 'flow': 'problem', 'activities': ['case']}},
            ensure_ascii=False), encoding='utf-8')

    def test_record_writes_design_and_reason(self) -> None:
        preview_pack.record_choice(self.folder, 'seminar', '사용자가 세미나형을 골랐다', 'user', None)
        cfg = json.loads(self.deck.read_text(encoding='utf-8'))
        self.assertEqual(cfg['resource_pack'], {'design': 'seminar', 'flow': 'problem', 'activities': ['case']})
        choice = cfg['resource_pack_choice']
        self.assertEqual(choice['design'], 'seminar')
        self.assertEqual(choice['by'], 'user')
        self.assertEqual(choice['reason'], '사용자가 세미나형을 골랐다')
        self.assertEqual(choice['preview'], 'preview.html')
        self.assertEqual([c['design'] for c in choice['candidates']], ['atlas', 'seminar', 'workbook'])

    def test_record_default_path_keeps_recommendation(self) -> None:
        preview_pack.record_choice(self.folder, 'atlas', '무응답이라 추천 후보로 진행했다', 'default', 'atlas')
        cfg = json.loads(self.deck.read_text(encoding='utf-8'))
        self.assertEqual(cfg['resource_pack_choice']['by'], 'default')
        self.assertEqual(cfg['resource_pack_choice']['recommended'], 'atlas')

    def test_record_rejects_invalid_input(self) -> None:
        with self.assertRaises(preview_pack.PreviewError):
            preview_pack.record_choice(self.folder, 'nope', '이유', 'user', None)
        with self.assertRaises(preview_pack.PreviewError):
            preview_pack.record_choice(self.folder, 'atlas', '이유', 'default', None)  # 추천 팩 누락
        empty = self.root / 'empty'
        empty.mkdir()
        (empty / 'deck.json').write_text('{"title":"t","output":"d.html"}', encoding='utf-8')
        with self.assertRaises(preview_pack.PreviewError):
            preview_pack.record_choice(empty, 'atlas', '이유', 'user', None)  # resource_pack 없음


class CliRecordTests(unittest.TestCase):
    def test_record_cli_updates_deck_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'deck.json').write_text(json.dumps(
                {'title': 'CLI 시험', 'output': 'deck.html',
                 'resource_pack': {'design': 'atlas', 'flow': 'problem'}}), encoding='utf-8')
            proc = subprocess.run(
                [sys.executable, str(SKILLS / 'edu-deck-solo' / 'scripts' / 'preview_pack.py'),
                 'record', str(folder), '--design', 'lab',
                 '--reason', '사용자가 실험 노트형을 골랐다', '--by', 'user'],
                capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            cfg = json.loads((folder / 'deck.json').read_text(encoding='utf-8'))
            self.assertEqual(cfg['resource_pack']['design'], 'lab')
            self.assertEqual(cfg['resource_pack_choice']['reason'], '사용자가 실험 노트형을 골랐다')


if __name__ == '__main__':
    unittest.main()
