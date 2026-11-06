#!/usr/bin/env python3
"""운영 지표 보고 계열(41-ops-report) 계약 시험 (TASK-ops-report).

[목적] ① 조각이 6변형·표준 헤더·aside.notes·정적 계약(canvas/script/SMIL 없음)을 지킨다.
       ② 사실 계약: 값을 싣는 그룹(.ofr/.oab/.ors/.ocm/.ome/.odi)·큰 수(.ov)마다 data-src.
       ③ check_deck: data-src 누락/형식 ERROR · 깔때기 비감소 WARN · 달력 칸 수 ERROR.
       ④ 브라우저: 자습 전개 완결 · 인쇄 에뮬레이션 완결 · metric-rally 발화 기록.
[입력] assets/snippets/41-ops-report.html + 정적 조각 fixture + Chromium.
[출력] 없음(단정문).
"""
import re
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
import check_deck  # noqa: E402

SNIPPET = S / 'assets' / 'snippets' / '41-ops-report.html'
HTML = SNIPPET.read_text(encoding='utf-8')
SECS = re.findall(r'<section[\s\S]*?</section>', HTML)
VARIANTS = ('funnel', 'aging', 'ratio', 'calendar', 'median', 'distribution')

NOTES = ('시험 장의 발표 노트입니다. 운영 지표 계약을 확인하는 안내 문구이며 '
         '자습 모드에서는 이 화면 그대로 읽습니다.')


def run_static(sections, allow=False):
    html = ('<!doctype html><html lang="ko"><head><title>t</title></head><body>'
            '<div id="stage">' + ''.join(sections) + '</div></body></html>')
    rep = check_deck.Report()
    check_deck.static_checks(html, BeautifulSoup(html, 'html.parser'), rep, allow)
    return rep


def kinds(rep, kind):
    return [it for it in rep.items if it['kind'] == kind]


OPS = ('<section class="slide" data-archetype="ops-report" data-variant="{v}" style="gap:22px">'
       '<div class="head"><p class="eyebrow">e</p><h2 class="title">t</h2></div>{body}'
       '<aside class="notes">' + NOTES + '</aside></section>')


class SnippetTest(unittest.TestCase):
    """(a) 조각 파일의 구조·정적 계약."""

    def test_six_variants(self):
        variants = re.findall(r'data-variant="([a-z-]+)"', HTML)
        self.assertEqual(variants, list(VARIANTS))
        self.assertEqual(len(SECS), 6)

    def test_header_notes_contract(self):
        for sec in SECS:
            self.assertIn('class="slide"', sec)
            self.assertIn('data-archetype="ops-report"', sec)
            self.assertIn('class="head"', sec)
            self.assertIn('class="eyebrow"', sec)
            self.assertIn('class="title"', sec)
            self.assertIn('aside class="notes"', sec)

    def test_no_canvas_or_runtime(self):
        self.assertNotIn('<canvas', HTML)
        self.assertNotIn('<script', HTML)
        self.assertNotIn('<animate', HTML)
        self.assertNotIn('@keyframes', HTML)
        self.assertNotIn('setInterval', HTML)

    def test_every_value_group_has_data_src(self):
        """값을 싣는 그룹·큰 수는 전부 data-src 사실 id 를 단다."""
        soup = BeautifulSoup(HTML, 'html.parser')
        for sel in ('.ofr', '.oab', '.ors', '.ocm', '.ome', '.odi', '.ov'):
            for el in soup.select(sel):
                self.assertTrue(el.get('data-src'), f'{sel} missing data-src')
                self.assertRegex(el['data-src'].strip('«»'), r'^F\d{2,3}$')

    def test_token_only_colors(self):
        """고정 hex 없음(토큰·명명색만)."""
        self.assertEqual(len(re.findall(r'#[0-9a-fA-F]{3,8}\b', HTML)), 0)

    def test_calendar_cells_in_range(self):
        soup = BeautifulSoup(HTML, 'html.parser')
        for m in soup.select('.ocm'):
            self.assertTrue(28 <= len(m.select('.ocd')) <= 31)

    def test_educational_copy_no_dev(self):
        """개발 보고서 소재 문구가 남지 않는다."""
        for word in ('PR', '랜딩', '워크플로', '커밋', '저장소', '픽'):
            self.assertNotIn(word, HTML)


class CheckerTest(unittest.TestCase):
    """(b) check_deck 계열 규칙."""

    def test_missing_data_src_is_error(self):
        sec = OPS.format(v='aging', body='<g class="oab"><text>10</text></g>'
                         '<g class="oab" data-src="F01"><text>2</text></g>'
                         '<g class="oab" data-src="F02"><text>3</text></g>')
        rep = run_static([sec])
        self.assertTrue(kinds(rep, '운영 지표'))

    def test_bad_src_format_is_error(self):
        sec = OPS.format(v='aging', body='<g class="oab" data-src="JIRA-1"><text>a</text></g>'
                         '<g class="oab" data-src="F01"><text>b</text></g>'
                         '<g class="oab" data-src="F02"><text>c</text></g>')
        rep = run_static([sec])
        self.assertTrue(any('Fxx' in it['message'] for it in kinds(rep, '운영 지표')))

    def test_funnel_direction_warns(self):
        body = ('<g class="ofr" data-src="F01" data-val="100"><text>a</text></g>'
                '<g class="ofr" data-src="F02" data-val="250"><text>b</text></g>'
                '<g class="ofr" data-src="F03" data-val="60"><text>c</text></g>')
        rep = run_static([OPS.format(v='funnel', body=body)])
        warns = [it for it in kinds(rep, '운영 지표') if it['sev'] == 'WARN']
        self.assertTrue(any('위 단계' in it['message'] for it in warns))

    def test_funnel_ok_when_descending(self):
        body = ('<g class="ofr" data-src="F01" data-val="300"><text>a</text></g>'
                '<g class="ofr" data-src="F02" data-val="200"><text>b</text></g>'
                '<g class="ofr" data-src="F03" data-val="60"><text>c</text></g>')
        rep = run_static([OPS.format(v='funnel', body=body)])
        self.assertFalse([it for it in kinds(rep, '운영 지표') if it['sev'] in ('ERROR', 'WARN')])

    def test_funnel_placeholder_vals_skip(self):
        """자리표시 data-val 은 방향 검사를 건너뛴다(ERROR·WARN 없음)."""
        body = ('<g class="ofr" data-src="F01" data-val="«건수»"><text>a</text></g>'
                '<g class="ofr" data-src="F02" data-val="«건수»"><text>b</text></g>'
                '<g class="ofr" data-src="F03" data-val="«건수»"><text>c</text></g>')
        rep = run_static([OPS.format(v='funnel', body=body)], allow=True)
        self.assertFalse(kinds(rep, '운영 지표'))

    def test_calendar_cell_count_error(self):
        body = ('<g class="ocm" data-src="F01">'
                + ''.join('<rect class="ocd"/>' for _ in range(20)) + '</g>')
        rep = run_static([OPS.format(v='calendar', body=body)])
        self.assertTrue(any('28~31' in it['message'] for it in kinds(rep, '운영 지표')))

    def test_minimal_group_count_error(self):
        sec = OPS.format(v='aging', body='<g class="oab" data-src="F01"><text>a</text></g>')
        rep = run_static([sec])
        self.assertTrue(any('최소' in it['message'] for it in kinds(rep, '운영 지표')))

    def test_sources_required(self):
        """ops data-src 보유 덱에 sources 장이 없으면 참고 자료 ERROR."""
        body = ('<g class="oab" data-src="F01"><text>a</text></g>'
                '<g class="oab" data-src="F02"><text>b</text></g>'
                '<g class="oab" data-src="F03"><text>c</text></g>')
        rep = run_static([OPS.format(v='aging', body=body)])
        self.assertTrue(kinds(rep, '참고 자료'))


DECK = Path('/tmp/ops-deck/deck.html')


@unittest.skipUnless(DECK.exists(), 'mini-deck not built')
class BrowserTest(unittest.TestCase):
    """(c) 브라우저 완결성 — 미니덱(표지+6변형+sources+closing)."""

    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.b = cls.pw.chromium.launch(channel='chrome')

    @classmethod
    def tearDownClass(cls):
        cls.b.close(); cls.pw.stop()

    def test_selfstudy_static_complete(self):
        """자습 모드에서 data-step 요소가 전부 보이는 완성 상태다."""
        pg = self.b.new_page(viewport={'width': 1920, 'height': 1080})
        pg.goto('file://' + str(DECK))
        pg.wait_for_timeout(400)
        pg.evaluate("document.body.classList.add('st-self')")
        pg.wait_for_timeout(300)
        for i in range(1, 7):
            pg.evaluate(f'deckGo({i})')
            pg.wait_for_timeout(250)
            hidden = pg.evaluate("""() => {
                const s = document.querySelectorAll('section.slide')[%d];
                return [...s.querySelectorAll('[data-step]')].filter(e =>
                    getComputedStyle(e).opacity < 0.95 ||
                    getComputedStyle(e).visibility === 'hidden').length;
            }""" % i)
            self.assertEqual(hidden, 0, f'slide {i+1} has hidden steps in st-self')
        pg.close()

    def test_print_static_complete(self):
        """인쇄 에뮬레이션에서도 data-step 요소가 전부 보인다."""
        pg = self.b.new_page(viewport={'width': 1920, 'height': 1080})
        pg.goto('file://' + str(DECK))
        pg.wait_for_timeout(400)
        pg.emulate_media(media='print')
        pg.wait_for_timeout(300)
        for i in range(1, 7):
            pg.evaluate(f'deckGo({i})')
            pg.wait_for_timeout(250)
            hidden = pg.evaluate("""() => {
                const s = document.querySelectorAll('section.slide')[%d];
                return [...s.querySelectorAll('[data-step]')].filter(e =>
                    getComputedStyle(e).opacity < 0.95 ||
                    getComputedStyle(e).visibility === 'hidden').length;
            }""" % i)
            self.assertEqual(hidden, 0, f'slide {i+1} has hidden steps in print')
        pg.close()

    def test_metric_rally_fires(self):
        """ops-report 장에서 metric-rally 발화가 기록된다."""
        pg = self.b.new_page(viewport={'width': 1920, 'height': 1080})
        pg.goto('file://' + str(DECK))
        pg.wait_for_timeout(400)
        pg.evaluate('deckGo(1)')  # funnel
        pg.wait_for_timeout(900)
        log = pg.evaluate('window.eduMotion ? window.eduMotion.sigLog.map(l=>l.sig) : []')
        pg.close()
        self.assertTrue(any('metric-rally' in str(n) for n in log), f'sigLog={log}')

    def test_dark_surface_text_adapts(self):
        """다크 슬라이드에서 k-ds 글자는 밝은 토큰으로, 면 위 글자는 잉크로 남는다."""
        dark = Path('/tmp/ops-deck-dark/deck.html')
        if not dark.exists():
            self.skipTest('dark mini-deck not built')
        pg = self.b.new_page(viewport={'width': 1920, 'height': 1080})
        pg.goto('file://' + str(dark))
        pg.wait_for_timeout(400)
        pg.evaluate("document.body.classList.add('st-self')")
        pg.evaluate('deckGo(1)')
        pg.wait_for_timeout(300)
        # funnel 단계 라벨: k-t-b k-ds(바탕) vs k-blue 다각형 위 잉크 글자
        surf = pg.evaluate("""() => {
            const s = document.querySelectorAll('section.slide')[1];
            const el = s.querySelector('.k-t-b.k-ds');
            return el ? getComputedStyle(el).fill : null;
        }""")
        onshape = pg.evaluate("""() => {
            const s = document.querySelectorAll('section.slide')[1];
            const el = s.querySelector('text[fill="var(--ink)"]');
            return el ? getComputedStyle(el).fill : null;
        }""")
        pg.close()
        self.assertIsNotNone(surf)
        self.assertNotEqual(surf, 'rgb(32, 43, 50)')  # --ink 아님 — 밝은 토큰으로 적응
        if onshape:  # 면 위 글자는 잉크 유지(밝은 도형 위라 식별 가능)
            self.assertEqual(onshape, 'rgb(32, 43, 50)')


if __name__ == '__main__':
    unittest.main()
