"""Acceptance: viewer additions — search, TOC, no-JS/init-fail fallback, data-fit, viewport modes.

Builds a small deck into /tmp and drives real Chromium (channel='chrome'):
- Ctrl+K / Cmd+K and "/" open the search dialog; typing filters; Enter jumps; Escape closes.
- "목차" button and key O open the TOC (eyebrow groups, current marked); click jumps.
- JavaScript disabled or an init throw both fall back to a stacked all-slides view + notice.
- data-fit shrinks a long title by at most 20%; a title that still overflows warns in check_deck.
- 1024x768 landscape = fitted slide view (ed-slidefit); 390x844 and 844x390 = reading view.
"""
import re, subprocess, sys, unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build
from check_deck import launch

OUT = Path('/tmp/edudeck-viewer')
SRC = OUT / 'src'
NOTES = '시험용 발표 노트입니다. 내용을 차근차근 설명합니다. ' * 3
LONG = '아주아주 길어서 절대 한 줄에 들어갈 수 없는 시험용 제목입니다 더 길게 더 길게 더더'  # ~47자 — 80%로도 2줄
MID = '조금 더 길어져서 살짝만 줄이면 한 줄에 들어가는 진짜 긴 제목'  # 35자 — 72px엔 2줄, ~68px에 1줄
SLIDES = {
'01-cover.html': '''<section class="slide" data-archetype="cover">
  <div class="cx-inner"><p class="cx-eyebrow">첫째부</p><h2 class="cx-title">표지 제목</h2>
  <p class="cx-sub">검색 대상 본문 사과</p></div>
  <aside class="notes">''' + NOTES + '''</aside></section>''',
'02-a.html': '''<section class="slide" data-archetype="statement">
  <div class="head"><p class="eyebrow">첫째부</p><h2 class="title">바나나 슬라이드</h2></div>
  <p class="body" style="font-size:30px">본문에 바나나가 있습니다.</p>
  <aside class="notes">''' + NOTES + '''</aside></section>''',
'03-fit.html': '''<section class="slide" data-archetype="statement">
  <div class="head"><p class="eyebrow">둘째부</p><h2 class="title" data-fit>''' + LONG + '''</h2></div>
  <p class="body" style="font-size:30px">맞춤 제목 시험.</p>
  <aside class="notes">''' + NOTES + '''</aside></section>''',
'04-fit2.html': '''<section class="slide" data-archetype="statement">
  <div class="head"><p class="eyebrow">둘째부</p><h2 class="title" data-fit>''' + MID + '''</h2></div>
  <p class="body" style="font-size:30px">맞춤 성공 시험.</p>
  <aside class="notes">''' + NOTES + '''</aside></section>''',
'05-c.html': '''<section class="slide" data-archetype="closing">
  <div class="head"><h2 class="title">마침</h2></div><p class="body">끝.</p>
  <aside class="notes">''' + NOTES + '''</aside></section>''',
}


class Viewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SRC.mkdir(parents=True, exist_ok=True)
        srcs = []
        for name, html in sorted(SLIDES.items()):
            p = SRC / name
            p.write_text(html, encoding='utf-8')
            srcs.append(p)
        cls.html = OUT / 'deck.html'
        build('뷰어 시험', srcs, [S / 'assets/css'], [S / 'assets/icons'], cls.html)
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def page(self, w=1920, h=1080, url=None, ctx=None):
        c = ctx or self.browser.new_context(viewport={'width': w, 'height': h},
                                            reduced_motion='reduce')
        self.addCleanup(c.close)
        p = c.new_page()
        p.goto(url or self.html.as_uri())
        p.evaluate('document.fonts.ready')
        return p

    # ---------- A1 검색 ----------
    def test_search_open_filter_jump_escape(self):
        p = self.page()
        p.keyboard.press('Control+k')
        self.assertTrue(p.evaluate("document.querySelector('.ed-sch').classList.contains('on')"))
        p.fill('.ed-sch input', '바나나')
        p.wait_for_timeout(100)
        self.assertEqual(p.evaluate("document.querySelectorAll('.ed-sch-list .ed-sch-item').length"), 1)
        p.keyboard.press('Enter')
        self.assertEqual(p.evaluate('deckInfo().slide'), 1)
        # '/' 로 다시 열고 Escape 로 닫기
        p.keyboard.press('/')
        self.assertTrue(p.evaluate("document.querySelector('.ed-sch').classList.contains('on')"))
        p.keyboard.press('Escape')
        self.assertFalse(p.evaluate("document.querySelector('.ed-sch').classList.contains('on')"))
        # 입력란에 포커스가 있을 때 '/' 는 열리지 않는다
        p.evaluate("""()=>{const i=document.createElement('input');i.id='ti';document.body.appendChild(i);i.focus();}""")
        p.keyboard.press('/')
        self.assertFalse(p.evaluate("document.querySelector('.ed-sch').classList.contains('on')"))

    # ---------- A2 목차 ----------
    def test_toc_button_key_group_jump(self):
        p = self.page()
        p.keyboard.press('o')
        self.assertTrue(p.evaluate("document.querySelector('.ed-toc').classList.contains('on')"))
        self.assertEqual(p.evaluate("document.querySelectorAll('.ed-toc-g').length"), 2)
        self.assertEqual(p.evaluate("document.querySelector('.ed-toc-item.is-cur .t').textContent"), '표지 제목')
        p.click(".ed-toc-item >> nth=3")   # 네 번째 항목(04-fit2)
        self.assertEqual(p.evaluate('deckInfo().slide'), 3)
        self.assertFalse(p.evaluate("document.querySelector('.ed-toc').classList.contains('on')"))
        p.click('.ed-topbar .ed-tbtn')     # 상단 바 '목차' 단추
        self.assertTrue(p.evaluate("document.querySelector('.ed-toc').classList.contains('on')"))
        p.keyboard.press('Escape')
        self.assertFalse(p.evaluate("document.querySelector('.ed-toc').classList.contains('on')"))

    # ---------- A3 대체 표시 ----------
    def test_nojs_shows_all_slides_and_notice(self):
        c = self.browser.new_context(viewport={'width': 1920, 'height': 1080},
                                     java_script_enabled=False)
        self.addCleanup(c.close)
        p = c.new_page()
        p.goto(self.html.as_uri())
        st = p.evaluate("""()=>{
          const slides=[...document.querySelectorAll('#stage>.slide')];
          return {shown:slides.filter(s=>getComputedStyle(s).display!=='none').length,
                  cls:document.documentElement.className,
                  nojsText:[...document.querySelectorAll('p.ed-nojs')].some(e=>e.getClientRects().length),
                  flow:getComputedStyle(document.getElementById('stage')).position};}""")
        self.assertEqual(st['shown'], 5)          # 전부 보임
        self.assertNotIn('ed-js', st['cls'])       # 엔진 표시 없음
        self.assertTrue(st['nojsText'])            # 안내 줄 보임
        self.assertEqual(st['flow'], 'static')     # 누적 흐름

    def test_init_throw_shows_all_slides_and_notice(self):
        c = self.browser.new_context(viewport={'width': 1920, 'height': 1080},
                                     reduced_motion='reduce')
        self.addCleanup(c.close)
        p = c.new_page()
        p.add_init_script("history.replaceState=function(){throw new Error('boom-init')}")
        p.goto(self.html.as_uri())
        p.wait_for_timeout(400)
        st = p.evaluate("""()=>({cls:document.documentElement.className,
          shown:[...document.querySelectorAll('#stage>.slide')].filter(s=>getComputedStyle(s).display!=='none').length,
          notice:getComputedStyle(document.querySelector('p.ed-nojs')).display});""")
        self.assertIn('ed-fail', st['cls'])
        self.assertEqual(st['shown'], 5)
        self.assertEqual(st['notice'], 'block')

    # ---------- A4 제목 맞춤 ----------
    def test_data_fit_shrinks_at_most_20pct(self):
        p = self.page()
        # 03: 41자 — 80% 로도 1줄 불가 → 57.6px 까지만 내려가고 여전히 2줄+
        p.evaluate('deckGo(2,0)')
        r = p.evaluate("""()=>{const t=document.querySelector('.slide.active .title');
          const r=document.createRange();r.selectNodeContents(t);
          const ls=new Set([...r.getClientRects()].map(x=>Math.round(x.top))).size;
          return {fs:parseFloat(getComputedStyle(t).fontSize),lines:ls};}""")
        self.assertGreaterEqual(r['fs'], 57.0)     # 72px × 80% = 57.6 바닥
        self.assertLessEqual(r['fs'], 72.0)
        self.assertGreater(r['lines'], 1)
        # 04: 18자 — 약간만 줄여 1줄에 들어감 (축소율 <20%)
        p.evaluate('deckGo(3,0)')
        r2 = p.evaluate("""()=>{const t=document.querySelector('.slide.active .title');
          const r=document.createRange();r.selectNodeContents(t);
          const ls=new Set([...r.getClientRects()].map(x=>Math.round(x.top))).size;
          return {fs:parseFloat(getComputedStyle(t).fontSize),lines:ls};}""")
        self.assertEqual(r2['lines'], 1)
        self.assertLess(r2['fs'], 72.0)
        self.assertGreaterEqual(r2['fs'], 57.0)

    def test_data_fit_warns_in_check_deck(self):
        out = subprocess.run(
            [sys.executable, str(S / 'scripts' / 'check_deck.py'),
             str(self.html), '--slides', '3', '--render-only'],
            capture_output=True, text=True, timeout=300)
        self.assertIn('data-fit 제목', out.stdout)
        self.assertIn('제목 줄 수', out.stdout)

    # ---------- 뷰포트 모드 ----------
    def test_view_modes(self):
        # 1024x768 가로 → 맞춤 슬라이드 뷰(무대 배율 유지, 읽기 모드 아님)
        p = self.page(1024, 768)
        self.assertTrue(p.evaluate("document.documentElement.classList.contains('ed-slidefit')"))
        self.assertFalse(p.evaluate("document.documentElement.classList.contains('ed-compact')"))
        sc = p.evaluate("getComputedStyle(document.getElementById('stage')).transform")
        self.assertNotEqual(sc, 'none')
        # 터치 내비 버튼이 보인다
        self.assertTrue(p.evaluate("document.querySelector('.ed-reader-nav').getClientRects().length>0"))
        # 390x844 세로 → 읽기 뷰
        p2 = self.page(390, 844)
        self.assertTrue(p2.evaluate("document.documentElement.classList.contains('ed-compact')"))
        self.assertFalse(p2.evaluate("document.documentElement.classList.contains('ed-slidefit')"))
        # 844x390 가로(폭 부족) → 읽기 뷰
        p3 = self.page(844, 390)
        self.assertTrue(p3.evaluate("document.documentElement.classList.contains('ed-compact')"))
        self.assertFalse(p3.evaluate("document.documentElement.classList.contains('ed-slidefit')"))
        # ?view=slide 강제 / ?view=scroll 강제
        u = self.html.as_uri()
        p4 = self.page(390, 844, url=u + '?view=slide')
        self.assertTrue(p4.evaluate("document.documentElement.classList.contains('ed-slidefit')"))
        p5 = self.page(1024, 768, url=u + '?view=scroll')
        self.assertTrue(p5.evaluate("document.documentElement.classList.contains('ed-compact')"))
        self.assertFalse(p5.evaluate("document.documentElement.classList.contains('ed-slidefit')"))


if __name__ == '__main__':
    unittest.main()
