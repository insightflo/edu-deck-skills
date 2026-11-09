"""Acceptance: charts/regen.py — 컨설팅 차트 조각 재생성.

[검사 항목]
- 재생성: 작업 폴더 charts/*.json 을 chart_gen.mjs 로 굽고 src/<stem>.html 에 쓴다.
- NN- 접두사 규칙: charts/<stem>.json → src/NN-<stem>.html 기존 파일이면 그 경로에 덮어쓴다.
- --check: 재생성 결과와 바이트가 같으면 exit 0 · 다르면 DIFF 목록과 함께 exit 1 —
  생성기/모델과 화면 조각이 어긋났을 때 조용히 지나가지 않는다.
- 실패: 차트 모델이 생성기를 통과하지 못하면 FAIL + exit 1.

[실행] cd edu-deck/shared && python3 -m unittest dev.test_consult_regen -v
[주의] node 18+ 가 PATH 에 있어야 한다(없으면 skip). 저장소에는 아무것도 쓰지 않는다.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

S = Path(__file__).resolve().parents[1]
ROOT = S.parents[1]
REGEN = ROOT / 'consulting-deck' / 'charts' / 'regen.py'
EX = ROOT / 'consulting-deck' / 'charts' / 'examples' / 'rb-ai-gap.json'
NODE = shutil.which('node')


def deck(tmp, tag):
    d = Path(tmp) / tag
    (d / 'charts').mkdir(parents=True)
    (d / 'src').mkdir()
    return d


def run(d, *args):
    p = subprocess.run([sys.executable, str(REGEN), *args, str(d)],
                       capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr


@unittest.skipUnless(NODE, 'node 없음')
class ConsultRegenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='edudeck-cregen-')

    def test_regen_then_check_same(self):
        d = deck(self.tmp, 'ok')
        shutil.copy(EX, d / 'charts' / 'rb-ai-gap.json')
        rc, out = run(d)
        self.assertEqual(rc, 0, out)
        self.assertTrue((d / 'src' / 'rb-ai-gap.html').exists())
        rc, out = run(d, '--check')
        self.assertEqual(rc, 0, out)
        self.assertIn('diff=0', out)

    def test_nn_prefix_output_path(self):
        d = deck(self.tmp, 'nn')
        shutil.copy(EX, d / 'charts' / 'rb-ai-gap.json')
        stub = d / 'src' / '03-rb-ai-gap.html'
        stub.write_text('<!-- 이전 조각 -->', encoding='utf-8')
        rc, out = run(d)
        self.assertEqual(rc, 0, out)
        self.assertIn('<section', stub.read_text())
        self.assertFalse((d / 'src' / 'rb-ai-gap.html').exists())

    def test_check_detects_tampering(self):
        d = deck(self.tmp, 'diff')
        shutil.copy(EX, d / 'charts' / 'rb-ai-gap.json')
        run(d)
        frag = d / 'src' / 'rb-ai-gap.html'
        frag.write_text(frag.read_text() + '\n<!-- tamper -->', encoding='utf-8')
        rc, out = run(d, '--check')
        self.assertEqual(rc, 1)
        self.assertIn('DIFF', out)
        self.assertIn('rb-ai-gap', out)

    def test_check_missing_output_is_diff(self):
        d = deck(self.tmp, 'miss')
        shutil.copy(EX, d / 'charts' / 'rb-ai-gap.json')
        rc, out = run(d, '--check')
        self.assertEqual(rc, 1)
        self.assertIn('DIFF', out)

    def test_bad_model_fails(self):
        d = deck(self.tmp, 'bad')
        (d / 'charts' / 'x.json').write_text(
            json.dumps({'slide': {'title': 'x'}, 'chart': {'type': 'ranked-bar-h'},
                        'source': {'text': 't', 'synthetic': True}}), encoding='utf-8')
        rc, out = run(d)
        self.assertEqual(rc, 1)
        self.assertIn('FAIL', out)
        self.assertIn('failed=1', out)


if __name__ == '__main__':
    unittest.main()
