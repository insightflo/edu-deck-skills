"""Acceptance: check_consulting.py — 근거 원장 대조 (evidence.md §2 스키마 원본).

[검사 항목]
- 유효 픽스처: evidence.json + src 2장 + 차트 모델 2건이 서로 대응하면 exit 0.
- 스키마 FAIL: claim_id 중복·필수 필드 누락·없는 source_id 참조.
- 출처 FAIL: 비가상 모델의 source.text 가 sources 어느 항목과도 대응하지 않음.
- 가상 FAIL: 모델 synthetic ↔ kind=synthetic claim 양방향 · 화면 s-syn ↔ 원장.
- 수치 FAIL: 모델 주요 값(expectTotal·data.value)이 claim 수치 안에 없음.
- WARN: stale 출처인데 asOf 없음 / 화면 수치 원장 미대조 — exit 는 0.

[실행] cd edu-deck/shared && python3 -m unittest dev.test_consulting_check -v
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

S = Path(__file__).resolve().parents[1]
ROOT = S.parents[1]
CHK = ROOT / 'consulting-deck' / 'checks' / 'check_consulting.py'


def deck_dir(tmp):
    d = Path(tmp) / 'deck'
    (d / 'src').mkdir(parents=True)
    (d / 'charts').mkdir()
    (d / 'deck.json').write_text(json.dumps({'title': 't', 'output': 't.html'}), encoding='utf-8')
    return d


EVIDENCE = {
    'sources': [
        {'source_id': 'S01', 'kind': 'internal', 'title': 'IT 비용 추출', 'publisher': '사내 ERP',
         'locator': 'erp://it-cost', 'asOf': '2025-12-31', 'freshness': 'current'},
    ],
    'claims': [
        {'claim_id': 'C01', 'slide': 'bridge', 'statement': 'IT 운영비 890억까지 절감 가능',
         'value': '890억', 'source_id': 'S01',
         'original': '1,240억 − 인건비 140 − 라이선스 110 − 클라우드 60 − 일회성 40 = 890',
         'kind': 'calculated'},
        {'claim_id': 'C02', 'slide': 'note', 'statement': '시장 규모는 가상 추정',
         'value': '120억', 'source_id': 'S01', 'kind': 'synthetic'},
        {'claim_id': 'C03', 'slide': 'ranked', 'statement': '전환율 상위 3개',
         'value': '62%', 'source_id': 'S01', 'original': '62 · 41 · 9', 'kind': 'synthetic'},
    ],
}

MODEL_WF = {
    'slide': {'title': 'IT 운영비는 890억까지 절감된다'},
    'chart': {'type': 'waterfall', 'question': '운영비는 어떻게 줄어드는가',
              'measure': {'unit': '억 원', 'period': '2025'},
              'data': [{'label': '기준', 'value': 1240, 'kind': 'base'},
                       {'label': '인건비', 'value': -140},
                       {'label': '라이선스', 'value': -110},
                       {'label': '클라우드', 'value': -60},
                       {'label': '일회성', 'value': -40, 'oneoff': True},
                       {'label': '목표', 'value': 890, 'kind': 'total'}],
              'calc': {'expectTotal': 890}},
    'source': {'text': '사내 ERP IT 비용 추출 — 운영비 원장', 'synthetic': False, 'asOf': '2025-12-31'},
}

MODEL_RB = {
    'slide': {'title': '전환율 상위 과제'},
    'chart': {'type': 'ranked-bar-h', 'question': '어느 과제가 앞서는가',
              'measure': {'unit': '%', 'period': '2025'},
              'data': [{'label': 'A', 'value': 62}, {'label': 'B', 'value': 41}, {'label': 'C', 'value': 9}]},
    'source': {'text': '가상 데이터', 'synthetic': True},
}

HTML_BRIDGE = '''<section class="slide consult"><h2 class="title">IT 운영비는 890억까지 절감된다</h2>
<div class="c-src"><p>Source: 사내 ERP IT 비용 추출 — 운영비 원장 · 기준 2025-12-31</p></div></section>'''
HTML_NOTE = '''<section class="slide consult"><h2 class="title">시장 규모 120억</h2>
<div class="c-src"><p>Source: 가상 데이터</p><p class="s-syn">가상 데이터</p></div></section>'''


def build(tmp, evidence=EVIDENCE, models=None, htmls=None):
    d = deck_dir(tmp)
    (d / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False), encoding='utf-8')
    for name, m in (models or {'bridge.json': MODEL_WF, 'ranked.json': MODEL_RB}).items():
        (d / 'charts' / name).write_text(json.dumps(m, ensure_ascii=False), encoding='utf-8')
    for name, h in (htmls or {'01-bridge.html': HTML_BRIDGE, '02-note.html': HTML_NOTE}).items():
        (d / 'src' / name).write_text(h, encoding='utf-8')
    return d


def run(d):
    p = subprocess.run([sys.executable, str(CHK), str(d)], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


class CheckConsultingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='edudeck-ccheck-')

    def work(self, tag, **kw):
        return build(Path(self.tmp) / tag, **kw)

    def test_valid_fixture_passes(self):
        rc, out = run(self.work('ok'))
        self.assertEqual(rc, 0, out)
        self.assertIn('errors=0', out)

    def test_schema_duplicate_claim_id(self):
        ev = json.loads(json.dumps(EVIDENCE))
        ev['claims'].append(dict(ev['claims'][0]))
        rc, out = run(self.work('schema', evidence=ev))
        self.assertEqual(rc, 1)
        self.assertIn('claim_id 중복', out)

    def test_schema_dangling_source_ref(self):
        ev = json.loads(json.dumps(EVIDENCE))
        ev['claims'][0]['source_id'] = 'S99'
        rc, out = run(self.work('schema2', evidence=ev))
        self.assertEqual(rc, 1)
        self.assertIn('S99', out)

    def test_missing_source_text(self):
        m = json.loads(json.dumps(MODEL_WF))
        m['source']['text'] = '출처를 알 수 없는 자료'
        rc, out = run(self.work('src', models={'bridge.json': m}))
        self.assertEqual(rc, 1)
        self.assertIn('대응하지 않는다', out)

    def test_synthetic_model_without_claim(self):
        m = json.loads(json.dumps(MODEL_WF))
        m['source']['synthetic'] = True
        rc, out = run(self.work('syn', models={'bridge.json': m}))
        self.assertEqual(rc, 1)
        self.assertIn('synthetic', out)

    def test_synthetic_claim_on_real_model(self):
        ev = json.loads(json.dumps(EVIDENCE))
        ev['claims'].append({'claim_id': 'C9', 'slide': 'bridge', 'statement': 'x',
                             'value': '1', 'source_id': 'S01', 'kind': 'synthetic'})
        rc, out = run(self.work('syn2', evidence=ev))
        self.assertEqual(rc, 1)
        self.assertIn('실데이터', out)

    def test_html_ssyn_without_claim(self):
        ev = json.loads(json.dumps(EVIDENCE))
        ev['claims'] = [c for c in ev['claims'] if c['claim_id'] != 'C02']
        rc, out = run(self.work('ssyn', evidence=ev))
        self.assertEqual(rc, 1)
        self.assertIn('s-syn', out)

    def test_number_mismatch(self):
        m = json.loads(json.dumps(MODEL_WF))
        m['chart']['data'][0]['value'] = 9999
        m['chart']['calc']['expectTotal'] = 9999 - 350
        rc, out = run(self.work('num', models={'bridge.json': m}))
        self.assertEqual(rc, 1)
        self.assertIn('불일치 수치', out)

    def test_stale_source_warns_not_fails(self):
        ev = json.loads(json.dumps(EVIDENCE))
        ev['sources'][0]['freshness'] = 'stale'
        m = json.loads(json.dumps(MODEL_WF))
        del m['source']['asOf']
        rc, out = run(self.work('stale', evidence=ev, models={'bridge.json': m, 'ranked.json': MODEL_RB}))
        self.assertEqual(rc, 0, out)
        self.assertIn('WARN', out)
        self.assertIn('stale', out)

    def test_missing_evidence_fails(self):
        d = deck_dir(Path(self.tmp) / 'noev')
        rc, out = run(d)
        self.assertEqual(rc, 1)
        self.assertIn('evidence.json', out)


if __name__ == '__main__':
    unittest.main()
