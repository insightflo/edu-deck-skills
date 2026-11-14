#!/usr/bin/env python3
"""check_deck 표 비중 검사 — <table> 포함 장이 전체의 1/3 초과 시 '표 비중' 취향(INFO) 지적.

[목적] ① 비중은 장 안의 <table> 유무로 센다(장 내부 — aside.notes 포함, spec: '<table> 포함 장').
       ② 표 장 비중 > 1/3 이면 덱 단위 지적 1건 — 기본 표시는 INFO, --style 에서 WARN.
       ③ 지적 문구는 절차·기준·단계 내용을 도식 형태(13-sequence·56-gate-chain 등)로 안내한다.
       ④ 임계(정확히 1/3)와 그 아래는 지적하지 않는다.
[입력] 인라인 HTML 문자열 → BeautifulSoup. 브라우저 없음.
[출력] 없음(단정문).
"""
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
import check_deck  # noqa: E402


def sec(table=False):
    body = ('<div class="head"><h2 class="title">t</h2></div>'
            + ('<table><tr><td>x</td></tr></table>' if table else '<p>x</p>')
            + '<aside class="notes">' + '노' * 120 + '</aside>')
    return f'<section class="slide" data-archetype="statement">{body}</section>'


def check(html, style=False):
    page = ('<html><head><title>t</title></head><body><div id="stage">'
            + html + '</div></body></html>')
    soup = BeautifulSoup(page, 'html.parser')
    rep = check_deck.Report(style=style)
    check_deck.static_checks(page, soup, rep, allow_placeholders=True)
    return rep


def findings(rep):
    return [i for i in rep.items if i['kind'] == '표 비중']


class TableRatio(unittest.TestCase):
    def test_over_third_one_info(self):
        rep = check(sec(table=True) + sec() + sec(table=True))
        hits = findings(rep)
        self.assertEqual(len(hits), 1, '표 장 2/3 > 1/3 → 지적 1건')
        self.assertIn('표 비중 2/3', hits[0]['message'])
        self.assertIn('도식 형태', hits[0]['message'])
        self.assertIn('56-gate-chain', hits[0]['message'])
        self.assertEqual(hits[0]['sev'], 'INFO', '취향 규칙 — 기본 표시는 INFO')
        self.assertIsNone(hits[0]['slide'], '덱 단위 지적 — 장 번호 없음')

    def test_style_mode_raises_warn(self):
        rep = check(sec(table=True) + sec() + sec(table=True), style=True)
        hits = findings(rep)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]['sev'], 'WARN', '--style 에서 취향 상세는 WARN')

    def test_exactly_third_no_finding(self):
        html = sec(table=True) + sec() + sec()
        self.assertEqual(findings(check(html)), [], '정확히 1/3 은 초과가 아니므로 지적 없음')

    def test_below_third_no_finding(self):
        html = sec(table=True) + sec() + sec() + sec()
        self.assertEqual(findings(check(html)), [], '1/4 는 지적 없음')

    def test_no_tables_no_finding(self):
        self.assertEqual(findings(check(sec() * 3)), [])


if __name__ == '__main__':
    unittest.main()
