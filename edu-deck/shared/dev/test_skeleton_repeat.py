#!/usr/bin/env python3
"""check_deck 골격 반복 검사 — 같은 구조 지문 3장 연속 시 '골격 반복' 취향(INFO) 지적.

[목적] ① 지문 = data-archetype + data-variant + 직속 자식의 '태그.첫클래스' 정렬 목록.
       ② 같은 지문 3장 연속 → '골격 반복' 1건 — 기본 표시는 INFO, --style 에서 WARN.
       ③ quiz-* 계열은 같은 골격 반복이 정상이라 제외 — 퀴즈 사이에 끼면 연속도 끊긴다.
       ④ 직속 자식 순서를 바꿔도 지문은 같다(정렬).
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


def sec(arch='statement', variant=None, kids=None):
    v = f' data-variant="{variant}"' if variant else ''
    kids = kids if kids is not None else ('<div class="head"><h2>t</h2></div>',
                                          '<div class="card"><p>x</p></div>')
    return (f'<section class="slide" data-archetype="{arch}"{v}>'
            + ''.join(kids) + '</section>')


def check(html, style=False):
    page = ('<html><head><title>t</title></head><body><div id="stage">'
            + html + '</div></body></html>')
    soup = BeautifulSoup(page, 'html.parser')
    rep = check_deck.Report(style=style)
    check_deck.static_checks(page, soup, rep, allow_placeholders=True)
    return rep


def findings(rep):
    return [i for i in rep.items if i['kind'] == '골격 반복']


class SkeletonRepeat(unittest.TestCase):
    def test_three_consecutive_one_info(self):
        rep = check(sec() + sec() + sec())
        hits = findings(rep)
        self.assertEqual(len(hits), 1, '3장 연속 같은 골격 → 지적 1건')
        self.assertIn('같은 골격이 3장 연속입니다', hits[0]['message'])
        self.assertIn('구성 리듬 점검', hits[0]['message'])
        self.assertEqual(hits[0]['sev'], 'INFO', '취향 규칙 — 기본 표시는 INFO')

    def test_style_mode_raises_warn(self):
        rep = check(sec() + sec() + sec(), style=True)
        hits = findings(rep)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]['sev'], 'WARN', '--style 에서 취향 상세는 WARN')

    def test_quiz_family_exempt(self):
        html = sec(arch='quiz-ab') * 3
        self.assertEqual(findings(check(html)), [], 'quiz-* 반복은 정상 — 제외')

    def test_quiz_breaks_the_run(self):
        html = sec() + sec() + sec(arch='quiz-ab') + sec() + sec()
        self.assertEqual(findings(check(html)), [], '퀴즈가 끼면 연속이 끊긴다')

    def test_two_slides_no_finding(self):
        self.assertEqual(findings(check(sec() + sec())), [], '2장은 지문이 같아도 연속 아님')

    def test_four_run_still_one_finding(self):
        rep = check(sec() * 4)
        self.assertEqual(len(findings(rep)), 1, '4장 연속이어도 지적은 한 번')

    def test_fingerprint_ignores_child_order(self):
        a = sec(kids=('<div class="head"></div>', '<div class="card"></div>', '<p class="callout"></p>'))
        b = sec(kids=('<p class="callout"></p>', '<div class="head"></div>', '<div class="card"></div>'))
        soup = BeautifulSoup(a + b, 'html.parser')
        s1, s2 = soup.select('section.slide')
        self.assertEqual(check_deck.slide_fingerprint(s1), check_deck.slide_fingerprint(s2),
                         '직속 자식 순서가 달라도 지문은 같다')

    def test_fingerprint_sees_variant_and_first_class(self):
        a = BeautifulSoup(sec(variant='x'), 'html.parser').section
        b = BeautifulSoup(sec(variant='y'), 'html.parser').section
        self.assertNotEqual(check_deck.slide_fingerprint(a), check_deck.slide_fingerprint(b),
                            'data-variant 가 다르면 다른 골격')
        c = BeautifulSoup(sec(kids=('<div class="head"></div>', '<div class="card"></div>')),
                          'html.parser').section
        d = BeautifulSoup(sec(kids=('<div class="head"></div>', '<div class="panel"></div>')),
                          'html.parser').section
        self.assertNotEqual(check_deck.slide_fingerprint(c), check_deck.slide_fingerprint(d),
                            '직속 자식의 첫 클래스가 다르면 다른 골격')


if __name__ == '__main__':
    unittest.main()
