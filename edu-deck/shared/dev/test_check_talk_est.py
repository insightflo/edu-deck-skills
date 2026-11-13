#!/usr/bin/env python3
"""check_deck.estimate_sec — data-sec 누락 WARN 의 어림 권장 초 산식 시험 (P1b).

[목적] talk 덱에서 data-sec 가 빠진 장에 대해 check_deck 가 권장 초를 같이 쓸 때,
       그 산식이 계약대로인지 고정한다:
       ① 장 종류 상수 — cover 30 · part-divider 15 · closing 45.
       ② 본문 장 — 보이는 글자÷12자/초 + pre 1블록 25초 + figure·(figure 밖 img) 하나 5초,
          5초 단위 반올림, 70~180초 클램프. aside.notes 글자는 보이는 글자에서 뺀다.
       ③ 누락 WARN 문장에 어림 값이 실린다.
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


def sec(inner, arch='statement', variant=None, cls='slide'):
    v = f' data-variant="{variant}"' if variant else ''
    return BeautifulSoup(
        f'<section class="{cls}" data-archetype="{arch}"{v}>{inner}</section>',
        'html.parser').section


HEAD = '<div class="head"><p class="eyebrow">표시</p><h2 class="title">제목</h2></div>'


class EstimateSec(unittest.TestCase):
    # ---------- ① 장 종류 상수 ----------
    def test_archetype_constants(self):
        self.assertEqual(check_deck.estimate_sec(sec('', 'cover')), 30)
        self.assertEqual(check_deck.estimate_sec(sec('', 'part-divider')), 15)
        self.assertEqual(check_deck.estimate_sec(sec('', 'mapping', variant='part-divider')), 15)
        self.assertEqual(check_deck.estimate_sec(sec('', 'closing')), 45)

    # ---------- ② 본문 산식 ----------
    def test_body_floor_and_rounding(self):
        # 글자가 거의 없는 본문 장은 하한 70초
        self.assertEqual(check_deck.estimate_sec(sec(HEAD)), 70)
        # 글자 240자→20초 + pre 2개→50초 = 70초 — 하한 경계에서도 산식이 통한다
        html = HEAD + '<p class="body">' + '가' * 240 + '</p><pre>x</pre><pre>y</pre>'
        self.assertEqual(check_deck.estimate_sec(sec(html)), 70)
        # 글자 720자→60초 + pre 1개→25초 = 85초
        html = HEAD + '<p class="body">' + '가' * 720 + '</p><pre>x</pre>'
        self.assertEqual(check_deck.estimate_sec(sec(html)), 85)

    def test_figures_and_loose_imgs_count(self):
        # 글자 900자→75초 + figure 2·밖 img 1 → 시각 3개×5초=15 → 90초
        html = (HEAD + '<p class="body">' + '가' * 900 + '</p>'
                '<figure>f</figure><figure>g</figure><img src="x">')
        self.assertEqual(check_deck.estimate_sec(sec(html)), 90)
        # figure 안 img 는 figure 로만 센다 — 75+5=80초
        html = HEAD + '<p class="body">' + '가' * 900 + '</p><figure><img src="x"></figure>'
        self.assertEqual(check_deck.estimate_sec(sec(html)), 80)

    def test_clamp_high(self):
        html = HEAD + '<p class="body">' + '가' * 6000 + '</p>'
        self.assertEqual(check_deck.estimate_sec(sec(html)), 180)

    def test_notes_are_excluded(self):
        # 노트를 아무리 길게 써도 보이는 글자에 들어가지 않는다
        html = HEAD + '<p class="body">' + '가' * 240 + '</p><aside class="notes">' + '노' * 5000 + '</aside>'
        self.assertEqual(check_deck.estimate_sec(sec(html)), 70)

    # ---------- ③ WARN 문장에 어림 값 ----------
    def test_missing_sec_warn_carries_estimate(self):
        slides = [BeautifulSoup(
            f'<section class="slide" data-archetype="statement">{HEAD}</section>',
            'html.parser').section]
        text = ('<html><body><script>window.EDU_STUDY = {"talk":{"total":600,"rate":300}};</script>'
                + ''.join(str(s) for s in slides) + '</body></html>')
        rep = check_deck.Report()
        check_deck.talk_checks(text, slides, rep)
        warns = [i['message'] for i in rep.items if i['kind'] == '예상 시간']
        self.assertEqual(len(warns), 1)
        self.assertIn('어림 70초 권장', warns[0])


if __name__ == '__main__':
    unittest.main()
