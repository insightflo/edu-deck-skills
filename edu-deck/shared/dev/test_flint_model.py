#!/usr/bin/env python3
"""flint_gen.mjs 모델 검증·환경 도구 시험.

스키마 오류 경로는 flint 미설치 환경에서도 돈다(node만 필요 — 스키마 검사가
flint 로딩보다 먼저다). 실 렌더 통합은 FLINT_HOME 에 flint가 있을 때만 돌린다.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FGEN = ROOT / 'consulting-deck' / 'charts' / 'flint_gen.mjs'
FENV = ROOT / 'consulting-deck' / 'charts' / 'flint_env.py'
NODE = shutil.which('node')
FLINT_HOME = Path(os.environ.get('FLINT_HOME') or (Path.home() / '.edu-deck' / 'flint'))
FLINT_OK = (FLINT_HOME / 'node_modules' / 'flint-chart' / 'package.json').exists()

VALID = {
    "engine": "flint", "flintVersion": "1.0.1", "theme": "consult",
    "slide": {"eyebrow": "비용", "title": "시험 제목", "notes": "노트"},
    "flint": {
        "data": {"values": [{"항목": "A", "금액": 10}, {"항목": "B", "금액": 20}]},
        "semantic_types": {"항목": "Category", "금액": "Amount"},
        "chart_spec": {"chartType": "Bar Chart",
                       "encodings": {"x": {"field": "항목"}, "y": {"field": "금액"}},
                       "baseSize": {"width": 600, "height": 300}},
    },
    "source": {"text": "시험 원장", "asOf": "2026-11", "synthetic": True},
}


def gen(model, *extra):
    return subprocess.run([NODE, str(FGEN), '--in', model, *extra],
                          capture_output=True, text=True, timeout=120)


@unittest.skipUnless(NODE, 'node 없음')
class ModelGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='flint-model-')
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def write(self, obj, name='m.flint.json'):
        p = Path(self.tmp) / name
        p.write_text(json.dumps(obj, ensure_ascii=False))
        return str(p)

    def run_bad(self, obj, frag):
        p = self.write(obj)
        r = gen(p)
        self.assertEqual(r.returncode, 1, r.stderr[-400:])
        self.assertIn('FAIL', r.stderr)
        self.assertIn(frag, r.stderr)

    def test_engine_required(self):
        m = dict(VALID)
        del m['engine']
        self.run_bad(m, 'engine')

    def test_engine_not_chartgen(self):
        m = dict(VALID, engine='chart_gen')
        self.run_bad(m, 'engine')

    def test_theme_whitelist(self):
        m = dict(VALID, theme='economist')
        self.run_bad(m, 'theme')

    def test_values_required(self):
        m = json.loads(json.dumps(VALID))
        del m['flint']['data']['values']
        self.run_bad(m, 'values')

    def test_foreign_toplevel_key_rejected(self):
        m = dict(VALID, hack=True)
        self.run_bad(m, '금지 키')

    def test_synthetic_declared(self):
        m = json.loads(json.dumps(VALID))
        del m['source']['synthetic']
        self.run_bad(m, 'synthetic')

    def test_source_text_required(self):
        m = json.loads(json.dumps(VALID))
        del m['source']
        self.run_bad(m, 'source.text')

    def test_canvas_size_cap(self):
        m = json.loads(json.dumps(VALID))
        m['flint']['chart_spec']['canvasSize'] = {"width": 9000, "height": 100}
        self.run_bad(m, 'canvasSize')

    def test_help_exits_zero(self):
        r = subprocess.run([NODE, str(FGEN), '--help'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn('flint_gen.mjs', r.stdout)


@unittest.skipUnless(FLINT_OK, 'flint 미설치 — 통합 케이스 생략')
class FlintIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='flint-it-')
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.model = str(Path(self.tmp) / 'm.flint.json')
        Path(self.model).write_text(json.dumps(VALID, ensure_ascii=False))

    def test_render_then_check_same_and_deterministic(self):
        out = str(Path(self.tmp) / 'slide.html')
        r = gen(self.model, '-o', out)
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        r = gen(self.model, '-o', out, '--check')
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        self.assertIn('SAME', r.stdout)
        # 별도 프로세스 재생성 바이트 동일
        svg1 = subprocess.run([NODE, str(FGEN), '--in', self.model, '--svg-only'],
                              capture_output=True, text=True).stdout
        svg2 = subprocess.run([NODE, str(FGEN), '--in', self.model, '--svg-only'],
                              capture_output=True, text=True).stdout
        self.assertEqual(svg1, svg2)
        self.assertTrue(svg1.lstrip().startswith('<svg'))
        self.assertNotIn('<script', svg1)

    def test_env_check_reports_installed(self):
        r = subprocess.run(['python3', str(FENV), 'check'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('flint-chart', r.stdout)

    def test_state_roundtrip(self):
        r = subprocess.run(['python3', str(FENV), 'state', 'set', 'testFlag', 'true'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        r = subprocess.run(['python3', str(FENV), 'state', 'get', 'testFlag'],
                           capture_output=True, text=True)
        self.assertIn('true', r.stdout)
        subprocess.run(['python3', str(FENV), 'state', 'set', 'testFlag', 'null'],
                       capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
