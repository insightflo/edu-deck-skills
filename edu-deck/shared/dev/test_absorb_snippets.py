#!/usr/bin/env python3
"""흡수 신규 조각(P2·P3·P4) 정적 계약 시험 — bento 표지·win-frame·screen-cite 텍스트 인용.

[목적] ① 01-cover-bento: data-variant="bento" · .cx 계약(제목은 .cx-title) · 단계 없음 · aside.notes.
       ② 55-window-frame: .win-frame 뼈대(wf-bar·wf-dots·wf-title·wf-tag·wf-body·wf-foot) +
          호스트 아키타입 장 + aside.notes — 프레임 자체는 단계 없음(안쪽 내용만 단계).
       ③ 32-screen-cite quote-text: .sc-tag + .sc-quote + 캡션 3요소가 조각에 있다.
       ④ check_deck 텍스트 인용 규율: .sc-quote + <img> 공존 ERROR · 빈 .sc-quote ERROR ·
          빈 .sc-tag ERROR (정상 텍스트 인용은 통과).
[입력] assets/snippets/*.html 원본 + 인라인 fixture → check_deck 정적 검사. 브라우저 없음.
[출력] 없음(단정문).
"""
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
import check_deck  # noqa: E402

SNIP = S / 'assets/snippets'


def parse(name):
    return BeautifulSoup((SNIP / name).read_text(encoding='utf-8'), 'html.parser')


def check_slide(inner):
    """조각 한 장을 최소 문서로 싸서 정적 검사를 돌리고 '실물 화면' kind 의 (sev, message) 만 돌려준다."""
    html = ('<html><body><div id="stage">'
            f'<section class="slide" data-archetype="mapping" data-variant="quote-text">{inner}</section>'
            '</div></body></html>')
    soup = BeautifulSoup(html, 'html.parser')
    rep = check_deck.Report()
    check_deck.static_checks(html, soup, rep, allow_placeholders=False)
    return [(i['sev'], i['message']) for i in rep.items if i['kind'] == '실물 화면']


QUOTE_OK = ('<figure class="screen-cite f3"><span class="sc-tag">원문 표현: "최소한"</span>'
            '<blockquote class="sc-quote">목적에 필요한 최소한의 개인정보만을 처리하여야 한다.</blockquote>'
            '<figcaption class="sc-cap"><p class="sc-line">'
            '<span class="sc-src" data-src="F01"><b>개인정보 보호법</b>, 「제3조」</span>'
            '<span class="sc-date">조회일 2026-11-14</span></p>'
            '<p class="sc-gist"><b>이 문장이 증명하는 것</b> — 법의 명문 요구</p>'
            '</figcaption></figure>')


class CoverBento(unittest.TestCase):
    def test_contract(self):
        soup = parse('01-cover-bento.html')
        sec = soup.find('section')
        self.assertIsNotNone(sec, '조각에 section 이 없다')
        self.assertEqual(sec.get('data-archetype'), 'cover')
        self.assertEqual(sec.get('data-variant'), 'bento')
        self.assertIn('cx', sec.get('class', []), '표지는 .slide.cx')
        self.assertIsNotNone(soup.select_one('.cx-title'), '제목은 .cx-title 안')
        self.assertIsNotNone(soup.select_one('.cx-eyebrow'))
        self.assertIsNotNone(soup.select_one('aside.notes'), '발표자 노트 필수')
        self.assertFalse(sec.select('[data-step]'), '표지는 단계 없음')
        self.assertFalse(soup.find('script'), '조각에 스크립트 금지')


class WindowFrame(unittest.TestCase):
    def test_structure(self):
        soup = parse('55-window-frame.html')
        sec = soup.find('section')
        self.assertIsNotNone(sec)
        self.assertTrue(sec.get('data-archetype'), '호스트 아키타입이 있어야 한다')
        for cls in ('.win-frame', '.wf-bar', '.wf-title', '.wf-tag', '.wf-body', '.wf-foot'):
            self.assertIsNotNone(soup.select_one(cls), f'{cls} 누락')
        self.assertEqual(len(soup.select('.wf-dots i')), 3, '창 점 3개')
        self.assertIsNotNone(soup.select_one('aside.notes'))
        self.assertFalse(soup.select_one('.win-frame[data-step]'),
                         '프레임 자체는 단계 없음 — 안쪽 내용만 단계')
        self.assertFalse(soup.find('script'), '조각에 스크립트 금지')


class QuoteText(unittest.TestCase):
    def test_snippet_has_variant(self):
        soup = parse('32-screen-cite.html')
        sec = soup.select_one('[data-variant="quote-text"]')
        self.assertIsNotNone(sec, 'quote-text 변형 section 이 없다')
        self.assertIsNotNone(sec.select_one('.sc-tag'))
        self.assertIsNotNone(sec.select_one('.sc-quote'))
        self.assertIsNotNone(sec.select_one('.sc-src[data-src]'))
        self.assertIsNotNone(sec.select_one('.sc-date'))
        self.assertIsNotNone(sec.select_one('.sc-gist'))

    def test_check_rules(self):
        # 정상 텍스트 인용은 통과
        res = check_slide(QUOTE_OK)
        self.assertFalse([r for r in res if r[0] == 'ERROR'], f'정상 인용에 ERROR: {res}')
        # .sc-quote + img 공존은 ERROR
        bad = check_slide(QUOTE_OK.replace('</blockquote>', '</blockquote><img src="x.png" alt="y">'))
        self.assertTrue(any(sev == 'ERROR' and ('이미지' in m or 'img' in m or '혼용' in m or '함께' in m)
                            for sev, m in bad), f'공존 미검출: {bad}')
        # 빈 .sc-quote 는 ERROR
        bad = check_slide(QUOTE_OK.replace('목적에 필요한 최소한의 개인정보만을 처리하여야 한다.', ''))
        self.assertTrue(any(sev == 'ERROR' and 'sc-quote' in m for sev, m in bad), f'빈 인용 미검출: {bad}')
        # 빈 .sc-tag 는 ERROR
        bad = check_slide(QUOTE_OK.replace('원문 표현: "최소한"', ''))
        self.assertTrue(any(sev == 'ERROR' and 'sc-tag' in m for sev, m in bad), f'빈 꼬리표 미검출: {bad}')


if __name__ == '__main__':
    unittest.main()
