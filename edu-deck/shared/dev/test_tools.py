"""Acceptance: TASK-tools — 자동 발표(A)·화면 편집(E)·탐색 위젯·사이드 시트·차트의 정적 완결.

Builds a small deck into /tmp and drives real Chromium (channel='chrome'):
- explore 칩 클릭이 .expl-state 를 전환하고, 인쇄/자습에서는 모든 상태가 펼쳐진다.
- dsheet 칩이 시트를 열고(Escape·딤·닫기로 닫힘), 인쇄/자습에서는 평면으로 펼쳐진다.
- A 키가 자동 발표를 시작해 data-sec 후 다음 장으로 가고, 아무 키로 멈춘다.
- E 키가 contenteditable 편집을 켜고, 수정본이 localStorage 에 저장·재적용되며
  '수정 초기화' 로 되돌아간다. 편집 시작은 자동 발표를 멈춘다.
- .chart 의 막대/점이 data-src 없이 두면 check_deck ERROR (사실 연결 재사용 규칙).
"""
import subprocess, sys, unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build
from check_deck import launch

OUT = Path('/tmp/edudeck-tools')
SRC = OUT / 'src'
NOTES = '시험용 발표 노트입니다. 내용을 차근차근 설명합니다. ' * 3
SLIDES = {
'01-explore.html': '''<section class="slide" data-archetype="explore" style="gap:32px" data-sec="2">
  <div class="head"><p class="eyebrow">첫째부</p><h2 class="title">탐색 시험</h2></div>
  <div class="expl">
    <div class="expl-ctrl">
      <button type="button" class="expl-chip on" data-x="0">갑</button>
      <button type="button" class="expl-chip" data-x="1">을</button>
    </div>
    <div class="expl-state on" data-x="0"><p class="expl-cap">갑 상태</p><p class="body">갑 본문</p></div>
    <div class="expl-state" data-x="1"><p class="expl-cap">을 상태</p><p class="body">을 본문</p></div>
  </div>
  <aside class="notes">''' + NOTES + '''</aside></section>''',
'02-sheet.html': '''<section class="slide" data-archetype="detail-sheet" style="gap:32px" data-sec="2">
  <div class="head"><p class="eyebrow">첫째부</p><h2 class="title">시트 시험</h2></div>
  <p class="body">본문</p>
  <button type="button" class="dsheet-open" data-open="a">더 보기</button>
  <div class="dsheet-dim"></div>
  <div class="dsheet-panel" data-sheet="a">
    <div class="dsheet-h"><h3>상세</h3><button type="button" class="dsheet-close">닫기</button></div>
    <div class="dsheet-b"><p>시트 본문</p></div>
  </div>
  <aside class="notes">''' + NOTES + '''</aside></section>''',
'03-chart.html': '''<section class="slide" data-archetype="chart-bar" data-sec="2" style="gap:28px">
  <div class="head"><p class="eyebrow">둘째부</p><h2 class="title">차트 시험</h2></div>
  <div class="chart"><svg viewBox="0 0 1560 600" role="img" aria-label="막대 차트">
    <g class="chart-bar" data-src="F01"><rect x="300" y="200" width="200" height="300" fill="var(--blue)"/><text x="400" y="180">50</text></g>
    <g class="chart-bar" data-src="F02"><rect x="800" y="100" width="200" height="400" fill="var(--accent)"/><text x="900" y="80">80</text></g>
  </svg></div>
  <aside class="notes">''' + NOTES + '''</aside></section>''',
'04-edit.html': '''<section class="slide" data-archetype="statement" data-sec="2">
  <div class="head"><p class="eyebrow">둘째부</p><h2 class="title">편집 전 제목</h2></div>
  <p class="body">편집 전 본문.</p>
  <aside class="notes">''' + NOTES + '''</aside></section>''',
'05-end.html': '''<section class="slide" data-archetype="closing"><div class="head"><h2 class="title">마침</h2></div>
  <aside class="notes">''' + NOTES + '''</aside></section>''',
'06-sources.html': '''<section class="slide" data-archetype="sources"><div class="head"><h2 class="title">참고 자료</h2></div>
  <ul class="src-list"><li><span class="sid">F01</span><b>출처A</b> 문서명 2024</li>
  <li><span class="sid">F02</span><b>출처B</b> 문서명 2024</li></ul>
  <aside class="notes">''' + NOTES + '''</aside></section>''',
}


class Tools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SRC.mkdir(parents=True, exist_ok=True)
        srcs = []
        for name, html in sorted(SLIDES.items()):
            p = SRC / name
            p.write_text(html, encoding='utf-8')
            srcs.append(p)
        cls.html = OUT / 'deck.html'
        build('도구 시험', srcs, [S / 'assets/css'], [S / 'assets/icons'], cls.html)
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def page(self, url=None):
        c = self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        self.addCleanup(c.close)
        p = c.new_page()
        p.goto(url or self.html.as_uri())
        p.evaluate('document.fonts.ready')
        return p

    # ---------- G4 explore ----------
    def test_explore_chip_switches_state(self):
        p = self.page()
        on = "document.querySelectorAll('.expl .expl-state.on').length"
        self.assertEqual(p.evaluate(on), 1)
        cap = "document.querySelector('.expl .expl-state.on .expl-cap').textContent"
        self.assertEqual(p.evaluate(cap), '갑 상태')
        p.click('.expl-chip[data-x="1"]')
        self.assertEqual(p.evaluate(cap), '을 상태')
        self.assertEqual(p.evaluate("document.querySelectorAll('.expl-chip.on').length"), 1)

    def test_explore_all_states_visible_print_and_selfstudy(self):
        p = self.page()
        vis = """()=>[...document.querySelectorAll('.expl .expl-state')]
             .filter(e=>getComputedStyle(e).display!=='none').length"""
        self.assertEqual(p.evaluate(vis), 1)          # 화면에서는 선택 상태 하나
        p.emulate_media(media='print')
        self.assertEqual(p.evaluate(vis), 2)          # 인쇄에서는 모두 펼쳐짐
        p.emulate_media(media='screen')
        p.keyboard.press('s')                          # 자습 모드
        p.wait_for_timeout(200)
        self.assertEqual(p.evaluate(vis), 2)
        self.assertEqual(p.evaluate("getComputedStyle(document.querySelector('.expl-ctrl')).display"), 'none')

    # ---------- G5 detail-sheet ----------
    def test_dsheet_open_dim_close(self):
        p = self.page()
        p.evaluate('deckGo(1,99)')                       # 단계 리빌 요소를 모두 공개
        clk = "document.querySelector('%s').click()"     # 시그니처가 붙은 요소는 JS 클릭으로
        p.evaluate(clk % '.dsheet-open')
        self.assertEqual(p.evaluate("document.querySelectorAll('.dsheet-panel.on').length"), 1)
        self.assertTrue(p.evaluate("document.querySelector('.dsheet-dim').classList.contains('on')"))
        p.keyboard.press('Escape')
        self.assertEqual(p.evaluate("document.querySelectorAll('.dsheet-panel.on').length"), 0)
        p.evaluate(clk % '.dsheet-open')
        p.evaluate(clk % '.dsheet-dim')
        self.assertEqual(p.evaluate("document.querySelectorAll('.dsheet-panel.on').length"), 0)
        p.evaluate(clk % '.dsheet-open')
        p.evaluate(clk % '.dsheet-close')
        self.assertEqual(p.evaluate("document.querySelectorAll('.dsheet-panel.on').length"), 0)

    def test_dsheet_flat_in_print_and_selfstudy(self):
        p = self.page()
        p.evaluate('deckGo(1,0)')
        flat = """()=>{const el=document.querySelector('.dsheet-panel');
          const cs=getComputedStyle(el);return {pos:cs.position,vis:cs.visibility,disp:cs.display};}"""
        self.assertEqual(p.evaluate(flat)['vis'], 'hidden')   # 화면: 닫힘
        p.emulate_media(media='print')
        r = p.evaluate(flat)
        self.assertEqual(r['vis'], 'visible')                  # 인쇄: 평면 펼침
        self.assertNotEqual(r['disp'], 'none')
        p.emulate_media(media='screen')
        p.keyboard.press('s')
        p.wait_for_timeout(200)
        r = p.evaluate(flat)
        self.assertEqual(r['vis'], 'visible')

    # ---------- G1 자동 발표 ----------
    def test_auto_advance_and_stop_on_key(self):
        p = self.page()
        self.assertFalse(p.evaluate('eduAuto.on()'))
        p.keyboard.press('a')
        self.assertTrue(p.evaluate('eduAuto.on()'))
        self.assertEqual(p.evaluate("document.documentElement.className.includes('ed-auto')"), True)
        p.wait_for_function("deckInfo().slide>=1", timeout=12000)   # 단계 공개+data-sec=2+전이
        self.assertGreaterEqual(p.evaluate('deckInfo().slide'), 1)
        self.assertTrue(p.evaluate('eduAuto.on()'))
        p.keyboard.press('x')                          # 아무 키 → 정지
        self.assertFalse(p.evaluate('eduAuto.on()'))
        slide = p.evaluate('deckInfo().slide')
        p.wait_for_timeout(1200)
        self.assertEqual(p.evaluate('deckInfo().slide'), slide)   # 더 진행 안 함

    def test_auto_toggle_off_with_a(self):
        p = self.page()
        p.keyboard.press('a')
        self.assertTrue(p.evaluate('eduAuto.on()'))
        p.keyboard.press('a')
        self.assertFalse(p.evaluate('eduAuto.on()'))

    # ---------- G2 화면 편집 ----------
    def test_edit_mode_persist_reset(self):
        c = self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        self.addCleanup(c.close)
        p = c.new_page(); p.goto(self.html.as_uri()); p.evaluate('document.fonts.ready')
        p.evaluate('deckGo(3,99)')
        p.keyboard.press('e')
        self.assertTrue(p.evaluate("document.body.classList.contains('ed-edit')"))
        n = p.evaluate("document.querySelectorAll('.slide [contenteditable=true]').length")
        self.assertGreater(n, 0)
        # 노트·칩·시트는 편집 대상이 아니다
        self.assertEqual(p.evaluate("document.querySelectorAll('aside [contenteditable], .dsheet-panel [contenteditable], .expl-chip[contenteditable]').length"), 0)
        # 제목을 고친다
        p.evaluate("""()=>{const t=document.querySelector('.slide.active .title');
          t.focus();t.textContent='편집된 제목';t.dispatchEvent(new Event('input',{bubbles:true}));}""")
        p.evaluate("document.activeElement.blur()")    # 편집 필드 안에서 E 는 글자 입력이므로 먼저 포커스를 뺀다
        p.keyboard.press('e')                          # 편집 종료 → 저장
        p.wait_for_timeout(600)
        key = "edeck-edit-deck.html"
        self.assertIsNotNone(p.evaluate("localStorage.getItem('" + key + "')"))
        # 같은 컨텍스트에서 다시 로드해도 수정본이 적용된다
        p2 = c.new_page(); p2.goto(self.html.as_uri()); p2.evaluate('document.fonts.ready')
        p2.evaluate('deckGo(3,0)')
        self.assertEqual(p2.evaluate("document.querySelector('.slide.active .title').textContent"), '편집된 제목')
        # 수정 초기화 → 원문 복귀
        p2.keyboard.press('e')
        p2.click('#edEdit .ed-reset')
        self.assertEqual(p2.evaluate("document.querySelector('.slide.active .title').textContent"), '편집 전 제목')
        self.assertIsNone(p2.evaluate("localStorage.getItem('" + key + "')"))

    def test_edit_stops_auto(self):
        p = self.page()
        p.keyboard.press('a')
        self.assertTrue(p.evaluate('eduAuto.on()'))
        p.keyboard.press('e')
        self.assertFalse(p.evaluate('eduAuto.on()'))

    def test_edit_enter_blocked(self):
        p = self.page()
        p.evaluate('deckGo(3,0)')
        p.keyboard.press('e')
        p.evaluate("document.querySelector('.slide.active .title').focus()")
        p.keyboard.press('Enter')
        html = p.evaluate("document.querySelector('.slide.active .title').innerHTML")
        self.assertNotIn('<br', html)
        self.assertNotIn('<div', html)

    # ---------- G3 차트 사실 연결 ----------
    def test_chart_without_data_src_is_error(self):
        bad_dir = OUT / 'bad'; bad_src = bad_dir / 'src'
        bad_src.mkdir(parents=True, exist_ok=True)
        (bad_src / '01.html').write_text(
            '''<section class="slide" data-archetype="chart-bar"><div class="head"><h2 class="title">무출처 차트</h2></div>
<div class="chart"><svg viewBox="0 0 100 100"><rect x="10" y="10" width="80" height="80"/></svg></div>
<aside class="notes">''' + NOTES + '</aside></section>', encoding='utf-8')
        bad_html = bad_dir / 'bad.html'
        build('무출처 시험', [bad_src / '01.html'], [S / 'assets/css'], [S / 'assets/icons'], bad_html)
        out = subprocess.run(
            [sys.executable, str(S / 'scripts' / 'check_deck.py'),
             str(bad_html), '--no-render'],
            capture_output=True, text=True, timeout=120)
        self.assertIn('차트', out.stdout)
        self.assertIn('ERROR', out.stdout)
        # 정상 덱(03-chart, data-src 있음)은 차트 ERROR 없음
        ok = subprocess.run(
            [sys.executable, str(S / 'scripts' / 'check_deck.py'),
             str(self.html), '--no-render'],
            capture_output=True, text=True, timeout=120)
        self.assertNotIn('차트', ok.stdout)


if __name__ == '__main__':
    unittest.main()
