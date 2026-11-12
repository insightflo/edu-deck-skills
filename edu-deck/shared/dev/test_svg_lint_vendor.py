#!/usr/bin/env python3
"""벤더 svg-lint 무결성 시험 — SHA256SUMS 전수 검증 + 최소 실행 증명.

[목적] scripts/vendor/svg-lint 아래 사본이 매니페스트와 바이트 일치하는지 잠근다.
       VENDOR.md 해시는 상류 매니페스트가 부패(해시 후 문구 추가)해 우리 사본에서만 재계산했다 —
       나머지 27개 해시는 상류(bybit-exchange/svg-diagram c30c9e3) 게시값 그대로다.
       린트 본체가 node 로 실제 돌아가는지도 --help 로 확인한다(node 없으면 skip).
[입력] scripts/vendor/svg-lint/{SHA256SUMS,tools/svg-lint/bin/svg-lint.mjs}
[출력] 없음(단정문).
"""
import hashlib
import shutil
import subprocess
import unittest
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[1] / 'scripts' / 'vendor' / 'svg-lint'
LINT_JS = VENDOR / 'tools' / 'svg-lint' / 'bin' / 'svg-lint.mjs'


class SvgLintVendorTest(unittest.TestCase):

    def test_manifest_complete(self):
        sums = VENDOR / 'SHA256SUMS'
        self.assertTrue(sums.exists(), 'SHA256SUMS 없음')
        files = [VENDOR / 'LICENSE', VENDOR / 'SKILL.upstream.md', VENDOR / 'VENDOR.md', LINT_JS]
        for f in files:
            self.assertTrue(f.exists(), f'{f.name} 없음')

    def test_sha256sums_verify(self):
        ok = bad = 0
        missing = []
        for raw in (VENDOR / 'SHA256SUMS').read_text().splitlines():
            raw = raw.strip()
            if not raw:
                continue
            want, rel = raw.split(None, 1)
            rel = rel.lstrip('./')
            f = VENDOR / rel
            if not f.exists():
                missing.append(rel)
                continue
            got = hashlib.sha256(f.read_bytes()).hexdigest()
            if got == want:
                ok += 1
            else:
                bad += 1
        self.assertFalse(missing, f'매니페스트 대상 파일 없음: {missing}')
        self.assertGreaterEqual(ok, 27, '벤더 파일 수가 기대보다 적다')
        self.assertEqual(bad, 0, '해시 불일치 파일이 있다')

    def test_lint_runs_on_node(self):
        if not shutil.which('node'):
            self.skipTest('node 없음')
        p = subprocess.run(['node', str(LINT_JS), '--help'],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('svg-lint', p.stdout)

    def test_lint_reports_findings_json(self):
        if not shutil.which('node'):
            self.skipTest('node 없음')
        import json
        import tempfile
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'
               '<rect x="10" y="10" width="80" height="30" fill="#dbeafe" stroke="#3b82f6"/>'
               '<text x="20" y="30">가</text></svg>')
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / 'a.svg'
            f.write_text(svg, encoding='utf-8')
            p = subprocess.run(['node', str(LINT_JS), '--json', str(f)],
                               capture_output=True, text=True, timeout=30)
        data = json.loads(p.stdout)
        self.assertIn('files', data)
        self.assertEqual(len(data['files']), 1)


if __name__ == '__main__':
    unittest.main()
