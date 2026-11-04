"""P1-1 숫자 증거 스트립 계약: 조각 31 의 구조·정적 검사·렌더·모션·출처 연결을 검증한다.

계약(지시문 v3 P1-1):
  (a) 정적: 지표마다 data-src 사실 id 가 있어야 하고(없으면 ERROR), 지표는 3~6개이며,
      숫자·라벨 글자 수는 catalog.json content_budget(stat_number/stat_label) 안에 든다.
  (b) 조각 31-stat-strip.html 은 section.slide 한 개(아키타입 stat-strip), 지표 3~6개,
      각 지표 .stat-num[data-count] + .stat-label + «Fxx» data-src 자리표시를 가진다.
  (c) 렌더: 스트립을 포함한 덱에서 넘침 0 · metric-rally 발화(sigLog) ·
      reduced-motion 에서 최종 값 정적 완결(숫자 릴이 만들어지지 않는다).
  (d) 출처: .stat-strip data-src 는 verify_sources 의 인용 체계로 검증된다
      (research.md 에 없는 id ERROR · 참고 자료 슬라이드 등록 누락 ERROR).
"""
import json
import sys
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build
from check_deck import ARCHETYPES, RENDER_JS, Report, launch, static_checks
import os, tempfile
_TEST_OUT = Path(os.environ.get('EDU_DECK_TEST_OUT', str(Path(tempfile.gettempdir()) / 'edu-deck-dev-tests')))

OUT = _TEST_OUT / 'stat-strip'
NOTE = ('<aside class="notes">이 장에서는 화면의 증거 숫자를 차례로 설명합니다. 화살표를 누르면 지표가 채워집니다. '
        '먼저 청중에게 어떤 기준이 궁금한지 물어본 뒤 숫자를 보여 주세요. 출처는 참고 자료 장에 있습니다. '
        '끝나면 다음 장으로 넘어갑니다.</aside>')

STATS_3 = "".join(
    f'<div class="stat" data-src="{sid}"><p class="stat-num" data-count>{v}</p>'
    f'<p class="stat-label">{lab}</p></div>'
    for sid, v, lab in [("F01", "31", "체감온도 기준(℃)"), ("F02", "20", "최소 휴식(분)"), ("F07", "35", "작업중지 권고(℃)")])

STATS_7 = "".join(f'<div class="stat" data-src="F0{i}"><p class="stat-num" data-count>{i}</p>'
                  f'<p class="stat-label">지표 {i}</p></div>' for i in range(1, 8))

SOURCES = ('<section class="slide" data-archetype="sources"><div class="head"><p class="eyebrow">참고 자료</p>'
           '<h2 class="title">오늘 숫자의 근거</h2></div><ul class="src-list">'
           '<li data-src="F01"><span class="sid">F01</span><span><b>법제처</b>, 「안전보건규칙 제559조」, 2025-07-17 — law.go.kr</span></li>'
           '<li data-src="F02"><span class="sid">F02</span><span><b>법제처</b>, 「안전보건규칙 제560조」, 2025-07-17 — law.go.kr</span></li>'
           '<li data-src="F07"><span class="sid">F07</span><span><b>고용노동부</b>, 「폭염 대비 노동자 건강보호 대책」, 2026-05-13 — moel.go.kr</span></li>'
           '</ul>' + NOTE + '</section>')


def stat_slide(stats, title="숫자로 보는 근거"):
    """아키타입 stat-strip 시험 슬라이드. 지표 마크업만 갈아 끼운다."""
    return (f'<section class="slide" data-archetype="stat-strip" style="gap:32px">'
            f'<div class="head"><p class="eyebrow">시험</p><h2 class="title">{title}</h2></div>'
            f'<div class="stat-strip" style="margin-top:auto">{stats}</div>{NOTE}</section>')


def run_static(slides):
    """정적 검사만 실행해 Report 를 돌려준다(브라우저 없음)."""
    html = ('<html><head><title>시험 덱</title></head><body><div id="stage">' + "\n".join(slides) + '</div></body></html>')
    rep = Report()
    static_checks(html, _soup(html), rep, allow_placeholders=False)
    return rep


def _soup(html):
    from bs4 import BeautifulSoup
    try:
        import lxml  # noqa: F401
        return BeautifulSoup(html, 'lxml')
    except ImportError:
        return BeautifulSoup(html, 'html.parser')


def findings(rep, kind):
    return [it for it in rep.items if it['kind'] == kind]


class StaticStatStripTest(unittest.TestCase):
    """(a) data-src 필수 · 지표 수 · 글자 예산의 정적 계약."""

    def test_stat_strip_is_a_known_archetype(self):
        self.assertIn('stat-strip', ARCHETYPES)

    def test_good_strip_has_no_band_findings(self):
        rep = run_static([stat_slide(STATS_3), SOURCES])
        self.assertEqual(findings(rep, '증거 띠'), [], rep.lines())
        self.assertEqual(rep.count('ERROR'), 0, rep.lines())

    def test_missing_data_src_is_error(self):
        broken = STATS_3.replace(' data-src="F02"', '', 1)
        rep = run_static([stat_slide(broken), SOURCES])
        errs = findings(rep, '증거 띠')
        self.assertTrue(errs and errs[0]['sev'] == 'ERROR', rep.lines())
        self.assertIn('data-src', errs[0]['message'])

    def test_metric_count_out_of_3_to_6_is_error(self):
        for stats in (STATS_3.rsplit('<div class="stat"', 1)[0], STATS_7):
            rep = run_static([stat_slide(stats), SOURCES])
            errs = [it for it in findings(rep, '증거 띠') if '3~6' in it['message']]
            self.assertTrue(errs, rep.lines())
            self.assertEqual(errs[0]['sev'], 'ERROR')

    def test_over_budget_number_and_label_warn(self):
        fat = STATS_3.replace('>31<', '>123,456,789,012<', 1).replace('체감온도 기준(℃)', '체감온도 폭염작업 기준이 넘는 긴 라벨')
        rep = run_static([stat_slide(fat), SOURCES])
        msgs = " ".join(it['message'] for it in findings(rep, '증거 띠'))
        self.assertIn('15자 > 12자', msgs)  # 숫자 예산 12자 초과("123,456,789,012" = 15자)
        self.assertIn('라벨', msgs)

    def test_budget_comes_from_catalog(self):
        catalog = json.loads((S / 'assets/packs/catalog.json').read_text(encoding='utf-8'))
        b = catalog['content_budget']
        self.assertEqual((b['stat_number'], b['stat_label']), (12, 16))

    def test_strip_without_sources_slide_is_error(self):
        rep = run_static([stat_slide(STATS_3)])
        self.assertTrue(findings(rep, '참고 자료'), rep.lines())


class SnippetMarkupTest(unittest.TestCase):
    """(b) 조각 31 파일의 구조 계약."""

    @classmethod
    def setUpClass(cls):
        import re
        cls.text = (S / 'assets/snippets/31-stat-strip.html').read_text(encoding='utf-8')
        cls.body = re.sub(r'<!--.*?-->', '', cls.text, flags=re.S)
        cls.soup = _soup('<html><body><div id="stage">' + cls.body + '</div></body></html>')
        cls.slide_el = cls.soup.select_one('section.slide')

    def test_single_stat_strip_section(self):
        self.assertIsNotNone(self.slide_el)
        self.assertEqual(self.slide_el.get('data-archetype'), 'stat-strip')
        self.assertEqual(len(self.soup.select('section.slide')), 1)

    def test_metrics_are_placeholder_bounded(self):
        stats = self.slide_el.select('.stat-strip .stat')
        self.assertTrue(3 <= len(stats) <= 6, f'지표 {len(stats)}개')
        for st in stats:
            self.assertRegex(st.get('data-src', ''), r'^«F\d{2,3}»$')
            num = st.select_one('.stat-num[data-count]')
            lab = st.select_one('.stat-label')
            self.assertIsNotNone(num, '.stat-num[data-count] 필요')
            self.assertIsNotNone(lab, '.stat-label 필요')
            self.assertRegex(num.get_text(strip=True), r'^«숫자 ≤\d+자»$')
            self.assertRegex(lab.get_text(strip=True), r'^«라벨 ≤\d+자»$')

    def test_placement_rule_is_documented(self):
        self.assertRegex(self.text, r'표지 하단.*목차 상단.*마무리 상단|표지 하단')
        self.assertIn('한 곳', self.text)
        self.assertIn('본문 중간', self.text)


RESEARCH = """# 조사 기록: 숫자 증거 스트립 단위 시험
기준일: 2026-11-03 · 청중: 단위 시험

## F01
- 주장: 폭염작업은 체감온도 31도 이상 장소에서의 장시간 작업이다.
- 값: 31
- 원문: "31도 이상이 되는 작업장소에서의 장시간 작업을 말한다."
- 출처: 법제처, 「안전보건규칙 제559조제4항」
- 발행일: 2025-07-17
- URL: https://www.law.go.kr/LSW/lsSideInfoP.do?lsiSeq=273603&joNo=0559
- 확인: 원문대조
- 대조: 2026-10-30 verify_sources.py --fetch (인용·값 일치)

## F02
- 주장: 체감온도 33도 이상 폭염작업에는 매 2시간 이내 20분 이상 휴식 의무가 있다.
- 값: 20
- 원문: "매 2시간 이내에 20분 이상의 휴식을 주어야 한다."
- 출처: 법제처, 「안전보건규칙 제560조제3항」
- 발행일: 2025-07-17
- URL: https://www.law.go.kr/LSW/lsSideInfoP.do?lsiSeq=273603&joNo=0560
- 확인: 원문대조
- 대조: 2026-10-30 verify_sources.py --fetch (인용·값 일치)

## F07
- 주장: 정부는 체감온도 35℃ 이상에서 무더위 시간대 옥외작업 중지를 권고한다.
- 값: 35
- 원문: "(체감온도 35℃ 이상, 폭염경보) 무더위 시간대(14시~17시) 옥외작업 중지"
- 출처: 고용노동부, 「폭염 대비 노동자 건강보호 대책 p.2」
- 발행일: 2026-05-13
- URL: https://www.moel.go.kr/common/downloadFile.do?file_seq=20260500843
- 확인: 원문대조
- 대조: 2026-10-30 verify_sources.py --fetch (인용·값 일치)
"""


class VerifySourcesStatStripTest(unittest.TestCase):
    """(d) .stat-strip data-src ↔ research.md·참고 자료 연결."""

    @classmethod
    def setUpClass(cls):
        import verify_sources as vs
        cls.vs = vs
        cls.dir = OUT / 'refs'
        cls.dir.mkdir(parents=True, exist_ok=True)
        (cls.dir / 'research.md').write_text(RESEARCH, encoding='utf-8')
        rep = run_static([stat_slide(STATS_3), SOURCES])
        assert rep.count('ERROR') == 0, rep.lines()
        html = ('<html><head><title>시험 덱</title></head><body><div id="stage">' + stat_slide(STATS_3) + SOURCES + '</div></body></html>')
        (cls.dir / 'deck.html').write_text(html, encoding='utf-8')

    def test_strip_ids_resolve_and_list(self):
        out = self.vs.Out()
        facts = self.vs.parse_research(self.dir / 'research.md', out)
        cited = self.vs.check_html(self.dir / 'deck.html', facts, out)
        self.assertEqual(cited, {'F01', 'F02', 'F07'})
        self.assertEqual(out.count('ERROR'), 0, out.rows)

    def test_unknown_strip_id_is_error(self):
        bad = stat_slide(STATS_3.replace('F01', 'F99'))
        (self.dir / 'deck.html').write_text(
            '<html><head><title>시험 덱</title></head><body><div id="stage">' + bad + SOURCES + '</div></body></html>', encoding='utf-8')
        out = self.vs.Out()
        facts = self.vs.parse_research(self.dir / 'research.md', out)
        self.vs.check_html(self.dir / 'deck.html', facts, out)
        errs = [msg for sev, _, msg in out.rows if sev == 'ERROR' and 'F99' in msg]
        self.assertTrue(errs, out.rows)


class RenderStatStripTest(unittest.TestCase):
    """(c) 발화·넘침·정적 완결의 렌더 계약(Playwright)."""

    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True, exist_ok=True)
        cover = ('<section class="slide cx" data-archetype="cover" id="cover" style="padding:0">'
                 '<div aria-hidden="true" class="cx-blob cx-b1"></div>'
                 '<div class="cx-text" style="top:200px;position:absolute"><p class="cx-eyebrow">폭염 작업 안전</p>'
                 '<h1 class="cx-title" style="font-size:104px">숫자로 보는 폭염 안전</h1>'
                 '<p class="cx-sub">체감온도 기준과 휴식 의무를 근거와 함께 확인합니다</p></div>'
                 '<div class="stat-strip" style="margin:auto 128px 128px">' + STATS_3 + '</div>'
                 '<p class="cover-date" style="z-index:3">2026. 11. 03</p>' + NOTE + '</section>')
        closing = ('<section class="slide dark center" data-archetype="closing"><div class="bar"></div>'
                   '<h2 class="big">숫자를 기준으로 지킵니다</h2>' + NOTE + '</section>')
        src = OUT / 'src'
        src.mkdir(parents=True, exist_ok=True)
        for name, html in [('01-cover.html', cover), ('02-stat.html', stat_slide(STATS_3)),
                           ('03-sources.html', SOURCES), ('04-closing.html', closing)]:
            (src / name).write_text(html + '\n', encoding='utf-8')
        build('stat strip contracts', sorted(src.glob('*.html')),
              [S / 'assets/css'], [S / 'assets/icons'], OUT / 'stat-strip.html')
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def page(self, reduced=False):
        c = self.browser.new_context(viewport={'width': 1920, 'height': 1080},
                                     reduced_motion='reduce' if reduced else 'no-preference')
        self.addCleanup(c.close)
        p = c.new_page()
        p.goto((OUT / 'stat-strip.html').as_uri())
        p.evaluate('document.fonts.ready')
        p.wait_for_timeout(80)
        return p

    def test_entry_fires_metric_rally_on_cover_host_and_standalone(self):
        p = self.page()
        p.evaluate('deckGo(0,0)')
        p.wait_for_timeout(60)
        cover_sigs = {e['sig'] for e in p.evaluate('()=>window.eduMotion.sigLog') if e['slide'] == 0}
        self.assertIn('metric-rally', cover_sigs, '표지 안 스트립이 metric-rally 를 발화해야 한다')
        self.assertIn('orbit-and-type', cover_sigs, 'host 표지 시그니처도 함께 발화해야 한다')
        i = p.evaluate('()=>[...document.querySelectorAll("#stage>.slide")].findIndex(s=>s.dataset.archetype==="stat-strip")')
        p.evaluate(f'deckGo({i},0)')
        p.wait_for_timeout(60)
        solo = {e['sig'] for e in p.evaluate('()=>window.eduMotion.sigLog') if e['slide'] == i}
        self.assertEqual(solo, {'metric-rally'})

    def test_count_up_reel_appears_with_motion_then_cleanup(self):
        p = self.page()
        i = p.evaluate('()=>[...document.querySelectorAll("#stage>.slide")].findIndex(s=>s.dataset.archetype==="stat-strip")')
        p.evaluate(f'deckGo({i},0)')
        self.assertGreater(p.locator('.slide.active .ed-number-reel').count(), 0,
                           '모션 켬에서 등장 시 카운트업 릴이 만들어져야 한다')
        p.wait_for_timeout(1000)  # m4=800ms 종료 후
        self.assertEqual(p.locator('.slide.active .ed-number-reel').count(), 0, '릴은 종료 후 스스로 지워진다')

    def test_reduced_motion_completes_with_final_values_and_no_reel(self):
        p = self.page(reduced=True)
        i = p.evaluate('()=>[...document.querySelectorAll("#stage>.slide")].findIndex(s=>s.dataset.archetype==="stat-strip")')
        p.evaluate(f'deckGo({i},0)')
        p.wait_for_timeout(60)
        self.assertEqual(p.locator('.ed-number-reel').count(), 0)
        texts = p.evaluate('()=>[...document.querySelectorAll(".slide.active .stat-num")].map(e=>e.textContent.trim())')
        self.assertEqual(texts, ['31', '20', '35'], 'reduced-motion 정적 완결은 최종 값')

    def test_render_probe_reports_no_overflow_on_band_slide(self):
        p = self.page(reduced=True)
        p.add_style_tag(content='*,*::before,*::after{animation-duration:0s!important;transition-duration:0s!important}'
                                 '#help,#counter,#dots,#progress{display:none!important}')
        i = p.evaluate('()=>[...document.querySelectorAll("#stage>.slide")].findIndex(s=>s.dataset.archetype==="stat-strip")')
        p.evaluate(f'deckGo({i},0)')
        out = p.evaluate(RENDER_JS, [i])
        self.assertEqual(out, [], out)


if __name__ == '__main__':
    unittest.main()
