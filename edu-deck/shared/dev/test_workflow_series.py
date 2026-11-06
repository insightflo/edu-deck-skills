#!/usr/bin/env python3
"""워크플로 도식 계열(42~52) 계약 시험 (TASK-workflow-series).

[목적] ① 11개 조각 파일이 각 2변형·표준 헤더·aside.notes·정적 계약(스크립트·SMIL·외부 자원 없음)을 지킨다.
       ② data-step 계약(변형당 2~5단계, 연속 정수)·계열별 마커 클래스·svg.dg 문법.
       ③ check_deck: 11 아키타입 인식(모름 ERROR 없음)·자리표시 덱에서 구조 오류 없음.
       ④ 브라우저: 자습 전개·인쇄 에뮬레이션 정적 완결, 신규 11종 시그니처 발화 기록.
[입력] assets/snippets/{42..52}-*.html + /tmp/wf-deck/deck.html(미니덱) + Chromium.
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

# (번호, 파일, 아키타입, 변형2, 시그니처, 발화 마커)
FAMILIES = (
    (42, '42-sankey-flow.html', 'sankey-flow', ('hub-split', 'composition'), 'stream-converge', '.sk'),
    (43, '43-decision-tree.html', 'decision-tree', ('approve', 'triage'), 'branch-verdict', '.dt'),
    (44, '44-kanban-board.html', 'kanban-board', ('flow', 'stages'), 'card-drift', '.kb'),
    (45, '45-version-graph.html', 'version-graph', ('release', 'documents'), 'merge-trace', '.vg'),
    (46, '46-event-fanout.html', 'event-fanout', ('notice', 'roles'), 'pulse-fanout', '.ef'),
    (47, '47-route-tour.html', 'route-tour', ('round', 'inspection'), 'waypoint-crawl', '.rt'),
    (48, '48-waterfall.html', 'waterfall', ('budget', 'enroll'), 'cascade-ledge', '.wf'),
    (49, '49-mesh-network.html', 'mesh-network', ('nodes', 'resilient'), 'hop-relay', '.ms'),
    (50, '50-heatmap-grid.html', 'heatmap-grid', ('timeslot', 'month'), 'grid-flare', '.hm'),
    (51, '51-swimlane.html', 'swimlane', ('process', 'roles'), 'lane-slide', '.sl'),
    (52, '52-cycle-ring.html', 'cycle-ring', ('ring', 'spiral'), 'ring-circuit', '.cy'),
)

NOTES_LEN = (110, 450)


def load(fname):
    html = (S / 'assets' / 'snippets' / fname).read_text(encoding='utf-8')
    return html, re.findall(r'<section[\s\S]*?</section>', html)


def run_static(sections, allow=False):
    html = ('<!doctype html><html lang="ko"><head><title>t</title></head><body>'
            '<div id="stage">' + ''.join(sections) + '</div></body></html>')
    rep = check_deck.Report()
    check_deck.static_checks(html, BeautifulSoup(html, 'html.parser'), rep, allow)
    return rep


class FamilyTest(unittest.TestCase):
    """(a) 각 계열 조각 파일의 구조·정적 계약 — 11계열 순회."""

    def test_files_and_variants(self):
        for _, fname, arch, variants, _, _ in FAMILIES:
            html, secs = load(fname)
            self.assertEqual(len(secs), 2, fname)
            got = re.findall(r'data-variant="([a-z-]+)"', html)
            self.assertEqual(got, list(variants), fname)
            for sec in secs:
                self.assertIn(f'data-archetype="{arch}"', sec)
                self.assertIn('class="slide"', sec)
                self.assertIn('class="head"', sec)

    def test_notes_length(self):
        for num, fname, *_ in FAMILIES:
            _, secs = load(fname)
            for sec in secs:
                m = re.search(r'<aside class="notes">([\s\S]*?)</aside>', sec)
                self.assertIsNotNone(m, f'{num} notes')
                n = len(m.group(1).strip())
                self.assertTrue(NOTES_LEN[0] <= n <= NOTES_LEN[1], f'{num} notes {n}')

    def test_no_runtime_or_external(self):
        for _, fname, *_ in FAMILIES:
            html, _ = load(fname)
            for bad in ('<script', '<animate', '@keyframes', 'setInterval',
                        'http://', 'https://', 'url(http'):
                self.assertNotIn(bad, html, f'{fname}: {bad}')

    def test_token_only_colors(self):
        for _, fname, *_ in FAMILIES:
            html, _ = load(fname)
            self.assertEqual(len(re.findall(r'#[0-9a-fA-F]{3,8}\b', html)), 0, fname)

    def test_svg_dg_grammar(self):
        """전 계열 svg.dg + role/aria-label + 회전 글자 없음."""
        for _, fname, *_ in FAMILIES:
            html, secs = load(fname)
            for sec in secs:
                self.assertIn('class="dg"', sec, fname)
                self.assertIn('role="img"', sec, fname)
                self.assertIn('aria-label=', sec, fname)
                self.assertNotIn('rotate(', re.sub(r'rotate\(-?\d+deg\)', '', sec), fname)
            self.assertNotIn('text-transform: rotate', html)

    def test_data_step_contract(self):
        """data-step 1~5 이내 연속 정수, 마커 클래스 존재."""
        for _, fname, arch, variants, _, marker in FAMILIES:
            html, secs = load(fname)
            soup = BeautifulSoup(html, 'html.parser')
            self.assertTrue(soup.select(marker), f'{fname} marker {marker}')
            for i, sec in enumerate(secs):
                steps = sorted({int(m) for m in re.findall(r'data-step="(\d+)"', sec)})
                self.assertTrue(2 <= len(steps) <= 5, f'{fname} v{i} steps={steps}')
                self.assertEqual(steps, list(range(steps[0], steps[-1] + 1)),
                                 f'{fname} v{i} 비연속 {steps}')
                self.assertEqual(steps[0], 1)

    def test_font_size_floor(self):
        """svg 글자 18px 미만 없음."""
        for _, fname, *_ in FAMILIES:
            html, _ = load(fname)
            for m in re.findall(r'font-size="(\d+)"', html):
                self.assertGreaterEqual(int(m), 18, f'{fname} font {m}')

    def test_signature_names_in_engine(self):
        engine = (S / 'assets' / 'js' / 'motion.js').read_text(encoding='utf-8')
        for _, _, arch, _, sig, _ in FAMILIES:
            self.assertIn(f"'{sig}'", engine, sig)
            self.assertIn(f"'{arch}'", engine, arch)


class CheckerTest(unittest.TestCase):
    """(b) check_deck 인식 — 스니펫 원문(자리표시 포함)에서 아키타입 모름 ERROR 없음."""

    def test_archetypes_registered(self):
        for _, _, arch, *_ in FAMILIES:
            self.assertIn(arch, check_deck.ARCHETYPES)
            self.assertIn(arch, check_deck.VISUAL_ARCHS)

    def test_no_unknown_archetype_errors(self):
        for _, fname, arch, *_ in FAMILIES:
            _, secs = load(fname)
            rep = run_static(secs, allow=True)
            arch_items = [it for it in rep.items
                          if '아키타입' in it['message'] or 'archetype' in it['message'].lower()]
            self.assertFalse([it for it in arch_items if it['sev'] == 'ERROR'],
                             f'{arch}: {[i["message"] for i in arch_items]}')


DECK = Path('/tmp/wf-deck/deck.html')
FIRED = {'stream-converge', 'branch-verdict', 'card-drift', 'merge-trace', 'pulse-fanout',
         'waypoint-crawl', 'cascade-ledge', 'hop-relay', 'grid-flare', 'lane-slide', 'ring-circuit'}


@unittest.skipUnless(DECK.exists(), 'wf mini-deck not built')
class BrowserTest(unittest.TestCase):
    """(c) 브라우저 완결성 — 미니덱(표지+11계열 기본 변형+마무리)."""

    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.b = cls.pw.chromium.launch(channel='chrome')

    @classmethod
    def tearDownClass(cls):
        cls.b.close(); cls.pw.stop()

    def _hidden_steps(self, pg, i):
        return pg.evaluate("""() => {
            const s = document.querySelectorAll('section.slide')[%d];
            return [...s.querySelectorAll('[data-step]')].filter(e =>
                getComputedStyle(e).opacity < 0.95 ||
                getComputedStyle(e).visibility === 'hidden').length;
        }""" % i)

    def test_selfstudy_static_complete(self):
        pg = self.b.new_page(viewport={'width': 1920, 'height': 1080})
        pg.goto('file://' + str(DECK))
        pg.wait_for_timeout(400)
        pg.evaluate("document.body.classList.add('st-self')")
        pg.wait_for_timeout(300)
        for i in range(1, 12):
            pg.evaluate(f'deckGo({i})')
            pg.wait_for_timeout(200)
            self.assertEqual(self._hidden_steps(pg, i), 0, f'slide {i+1} hidden in st-self')
        pg.close()

    def test_print_static_complete(self):
        pg = self.b.new_page(viewport={'width': 1920, 'height': 1080})
        pg.goto('file://' + str(DECK))
        pg.wait_for_timeout(400)
        pg.emulate_media(media='print')
        pg.wait_for_timeout(300)
        for i in range(1, 12):
            pg.evaluate(f'deckGo({i})')
            pg.wait_for_timeout(200)
            self.assertEqual(self._hidden_steps(pg, i), 0, f'slide {i+1} hidden in print')
        pg.close()

    def test_signatures_fire(self):
        """11종 신규 실행 이름이 각 계열 장에서 전부 발화 기록된다."""
        pg = self.b.new_page(viewport={'width': 1920, 'height': 1080})
        pg.goto('file://' + str(DECK))
        pg.wait_for_timeout(400)
        for i in range(1, 12):
            pg.evaluate(f'deckGo({i})')
            pg.wait_for_timeout(700)
        log = set(pg.evaluate('window.eduMotion ? window.eduMotion.sigLog.map(l=>l.sig) : []'))
        pg.close()
        missing = FIRED - log
        self.assertFalse(missing, f'not fired: {missing} (log={log})')


if __name__ == '__main__':
    unittest.main()
