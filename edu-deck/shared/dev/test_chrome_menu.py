"""Acceptance: 상·하단 크롬(.ed-top 헤더·.ed-bot 푸터) — menu-agy-spec 계약.

- 상단 막대: 브랜드 제목 + 도구 띠(목차·검색·노트·용어집·자습·타이머·테마·도움말·인쇄) + ⋯ 버튼.
- 하단 막대: 장 세그먼트 ×3·단계 점 ×2·쪽 입력(`/ 3`)·이전/다음 버튼.
- 유휴 2.5s 자동 숨김, 키 입력으로 복귀; F6·⋯ 고정이 localStorage 에 유지되어 재방문에도 지속.
- 도움말: H 키·도움말 버튼·닫기 버튼·Esc — #help 는 항상 display:none.
- compact(390×844)·?sheet 에서 막대 비렌더; 인쇄·발표자 표면 숨김은 CSS 계약.
"""
import sys, unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build
from check_deck import launch

OUT = Path('/tmp/edudeck-chrome')
SRC = OUT / 'src'
SLIDES = {
    '01-a.html': '''<section class="slide" data-archetype="cover">
  <div class="cx-inner"><p class="cx-eyebrow">하나부</p><h2 class="cx-title">첫 장</h2></div></section>''',
    '02-b.html': '''<section class="slide" data-archetype="statement">
  <div class="head"><p class="eyebrow">하나부</p><h2 class="title">둘째 장</h2></div>
  <p class="body" data-step="1">한 단계</p><p class="body" data-step="2">두 단계</p>
  <aside class="notes">둘째 장 발표 노트</aside></section>''',
    '03-c.html': '''<section class="slide" data-archetype="closing">
  <div class="head"><h2 class="title">셋째 장</h2></div><p class="body">끝.</p></section>''',
}


class ChromeMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SRC.mkdir(parents=True, exist_ok=True)
        srcs = []
        for name, html in sorted(SLIDES.items()):
            p = SRC / name
            p.write_text(html, encoding='utf-8')
            srcs.append(p)
        cls.html = OUT / 'deck.html'
        build('크롬 시험 덱', srcs, [S / 'assets/css'], [S / 'assets/icons'], cls.html)
        cls.html_talk = OUT / 'deck-talk.html'
        build('크롬 시험 덱', srcs, [S / 'assets/css'], [S / 'assets/icons'],
              cls.html_talk, study={'talk': {'total': 200, 'rate': 300}})
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def page(self, w=1920, h=1080, url=None):
        c = self.browser.new_context(viewport={'width': w, 'height': h},
                                     reduced_motion='reduce')
        self.addCleanup(c.close)
        p = c.new_page()
        p.goto(url or self.html.as_uri())
        p.evaluate('document.fonts.ready')
        return p

    # ---------- 구조 ----------
    def test_top_structure_and_labels(self):
        p = self.page()
        st = p.evaluate("""()=>{
          const top=document.querySelector('.ed-top');
          const b=document.querySelector('.ed-top .ed-brand b');
          const crumb=document.querySelector('.ed-top .ed-crumb');
          const labels=[...document.querySelectorAll('.ed-topbar .ed-tool .ed-tl')].map(e=>e.textContent);
          const ids=[...document.querySelectorAll('.ed-topbar .ed-tool')].map(e=>e.getAttribute('aria-label'));
          const more=document.querySelector('.ed-top .ed-more');
          return {on:!!top, brand:b&&b.textContent, crumb:crumb&&crumb.textContent,
                  labels, ids, more:more&&more.getAttribute('aria-label')};}""")
        self.assertEqual(st['brand'], '크롬 시험 덱')
        self.assertIn('첫 장', st['crumb'])
        for want in ('목차', '검색', '노트', '인쇄', '전체', '도움말', '핀'):
            self.assertIn(want, ''.join(st['labels']))
        # 기능 없는 덱(용어집·자습 데이터·talk·?themes 미지정)은 버튼 자체가 없다
        for absent in ('용어', '자습', '타이머', '테마'):
            self.assertNotIn(absent, ''.join(st['labels']))
        self.assertIn('도움말 (H)', st['ids'])
        self.assertEqual(st['more'], '도구 더보기')
        # 도움말 버튼이 검색 버튼 바로 옆 계열에 있다(띠 안 순서: …검색·…도움말)
        order = [l for l in st['labels']]
        self.assertLess(order.index('검색'), order.index('도움말'))

    def test_bot_structure(self):
        p = self.page()
        st = p.evaluate("""()=>({
          segs:document.querySelectorAll('.ed-bot .ed-seg').length,
          counter:document.getElementById('counter').textContent,
          page:!!document.querySelector('.ed-bot .ed-page'),
          nav:[...document.querySelectorAll('.ed-bot .ed-btn')].map(b=>b.textContent.trim())})""")
        self.assertEqual(st['segs'], 3)
        self.assertIn('/ 3', st['counter'])
        # 단계 점은 현재 장의 topMark — 둘째 장(data-step 1·2)에서 2개
        p.evaluate('deckGo(1,0)')
        self.assertEqual(p.evaluate("document.querySelectorAll('.ed-bot #dots i').length"), 2)
        p.evaluate('deckGo(0,0)')
        self.assertTrue(st['page'])
        self.assertEqual(st['nav'], ['이전', '다음'])
        # 첫 장: 이전 disabled
        self.assertTrue(p.evaluate("document.querySelectorAll('.ed-bot .ed-btn')[0].disabled"))

    # ---------- 탐색 ----------
    def test_seg_click_and_nav_buttons(self):
        p = self.page()
        p.click('.ed-bot .ed-seg >> nth=2')
        self.assertEqual(p.evaluate('deckInfo().slide'), 2)
        p.click('.ed-bot .ed-btn >> nth=0')          # 이전
        self.assertEqual(p.evaluate('deckInfo().slide'), 1)
        p.click('.ed-bot .ed-btn >> nth=1')          # 다음
        self.assertEqual(p.evaluate('deckInfo().slide'), 2)
        # 쪽 입력 점프
        p.fill('.ed-bot .ed-page', '1')
        p.keyboard.press('Enter')
        self.assertEqual(p.evaluate('deckInfo().slide'), 0)

    # ---------- 자동 숨김·복귀·고정 ----------
    def test_autohide_reveal_pin(self):
        p = self.page()
        p.wait_for_timeout(2900)                    # 유휴 → 숨김
        self.assertFalse(p.evaluate("document.body.classList.contains('ed-chrome-on')"))
        p.keyboard.press('Shift')                   # 아무 키 → 복귀 + 재무장
        self.assertTrue(p.evaluate("document.body.classList.contains('ed-chrome-on')"))
        p.wait_for_timeout(2900)
        self.assertFalse(p.evaluate("document.body.classList.contains('ed-chrome-on')"))
        # F6 = 막대로 포커스 이동(복귀 + 첫 버튼 포커스)
        p.keyboard.press('F6')
        self.assertTrue(p.evaluate("document.body.classList.contains('ed-chrome-on')"))
        self.assertTrue(p.evaluate("document.activeElement.closest('.ed-top')!==null"))
        # 핀 버튼 → 고정 → 새로고침해도 유지
        self.assertEqual(p.evaluate("document.querySelector('.ed-pin').getAttribute('aria-pressed')"), 'false')
        p.click('.ed-pin')
        self.assertEqual(p.evaluate("localStorage.getItem('ed-chrome-pin')"), '1')
        self.assertEqual(p.evaluate("document.querySelector('.ed-pin').getAttribute('aria-pressed')"), 'true')
        p.wait_for_timeout(2900)
        self.assertTrue(p.evaluate("document.body.classList.contains('ed-chrome-on')"))
        p.reload(); p.wait_for_timeout(600)
        self.assertTrue(p.evaluate("document.body.classList.contains('ed-chrome-on')"))
        # 고정 해제 — 포인터·포커스가 막대에 남아 있으면 숨김이 유예되므로 비켜 둔다
        p.click('.ed-pin')
        self.assertEqual(p.evaluate("localStorage.getItem('ed-chrome-pin')"), '0')
        p.evaluate('document.activeElement.blur()')
        p.mouse.move(960, 540)
        p.wait_for_timeout(2900)
        self.assertFalse(p.evaluate("document.body.classList.contains('ed-chrome-on')"))

    # ---------- 도움말 모달 ----------
    def test_help_modal_h_button_escape(self):
        p = self.page()
        self.assertEqual(p.evaluate("getComputedStyle(document.getElementById('help')).display"), 'none')
        p.keyboard.press('h')
        self.assertTrue(p.evaluate("document.querySelector('.ed-help-modal').classList.contains('on')"))
        txt = p.evaluate("document.querySelector('.ed-help-modal').textContent")
        self.assertIn('테마 미리보기', txt)
        self.assertIn('다음', txt)
        p.keyboard.press('Escape')
        self.assertFalse(p.evaluate("document.querySelector('.ed-help-modal').classList.contains('on')"))
        # 버튼으로 토글 → 닫기 버튼
        p.click('.ed-topbar .ed-tool[aria-label="도움말 (H)"]')
        self.assertTrue(p.evaluate("document.querySelector('.ed-help-modal').classList.contains('on')"))
        p.click('.ed-help-modal .ed-hm-x')
        self.assertFalse(p.evaluate("document.querySelector('.ed-help-modal').classList.contains('on')"))

    # ---------- 라벨 숨김(좁은 폭, sr-only)·compact ----------
    def test_narrow_and_compact(self):
        p = self.page(1100, 800)
        w = p.evaluate("document.querySelector('.ed-topbar .ed-tool .ed-tl').getBoundingClientRect().width")
        self.assertLess(w, 5)                      # 라벨은 시각 숨김(AT엔 유지)
        p2 = self.page(390, 844)
        st = p2.evaluate("""()=>({topbar:getComputedStyle(document.querySelector('.ed-topbar')).display,
          bot:getComputedStyle(document.querySelector('.ed-bot')).display,
          brand:getComputedStyle(document.querySelector('.ed-top')).display,
          more:!!document.querySelector('.ed-top .ed-more')})""")
        self.assertEqual(st['topbar'], 'none')
        self.assertEqual(st['bot'], 'none')
        self.assertNotEqual(st['brand'], 'none')   # 상단 막대(브랜드+⋯)는 남는다
        self.assertTrue(st['more'])

    # ---------- ?sheet 격리 ----------
    def test_sheet_hides_chrome(self):
        p = self.page(url=self.html.as_uri() + '?sheet')
        st = p.evaluate("""()=>({top:getComputedStyle(document.querySelector('.ed-top')).display,
          bot:getComputedStyle(document.querySelector('.ed-bot')).display})""")
        self.assertEqual(st['top'], 'none')
        self.assertEqual(st['bot'], 'none')

    # ---------- ?check = 검사기 표면(QUIET_CSS 와 같은 숨김 셋) ----------
    def test_check_hides_chrome(self):
        p = self.page(url=self.html.as_uri() + '?check')
        st = p.evaluate("""()=>({isCheck:document.documentElement.classList.contains('is-check'),
          top:getComputedStyle(document.querySelector('.ed-top')).display,
          bot:getComputedStyle(document.querySelector('.ed-bot')).display,
          nav:getComputedStyle(document.querySelector('.ed-reader-nav')).display,
          prog:getComputedStyle(document.getElementById('progress')).display})""")
        self.assertTrue(st['isCheck'])
        for k in ('top', 'bot', 'nav', 'prog'):
            self.assertEqual(st[k], 'none', k)

    # ---------- 회귀: 타이머 버튼이 막대 안에 들어가는가(.plan 카드 충돌) ----------
    def test_clock_fits_topbar(self):
        p = self.page(url=self.html_talk.as_uri())
        st = p.evaluate("""()=>{const c=document.getElementById('ed-clock');
          const top=document.querySelector('.ed-top').getBoundingClientRect();
          const r=c.getBoundingClientRect();const plan=c.querySelector('.ed-clock-plan');
          return {clock:{top:r.top,bot:r.bottom,h:r.height},bar:{top:top.top,bot:top.bottom},
                  plan:!!plan,planCard:plan?getComputedStyle(plan).display:''};}""")
        self.assertTrue(st['plan'])
        self.assertNotEqual(st['planCard'], 'flex')      # 팩 .plan 카드 스타일을 물려받으면 안 됨
        self.assertLessEqual(st['clock']['h'], 44)        # 버튼 높이는 막대 높이 안
        self.assertGreaterEqual(st['clock']['top'], st['bar']['top'] - 0.5)
        self.assertLessEqual(st['clock']['bot'], st['bar']['bot'] + 0.5)

    # ---------- 회귀: slide-fit 에서 하단 크롬은 한 벌(.ed-reader-nav 만) ----------
    def test_slidefit_single_bottom_chrome(self):
        p = self.page(1000, 700)
        st = p.evaluate("""()=>({slidefit:document.documentElement.classList.contains('ed-slidefit'),
          bot:getComputedStyle(document.querySelector('.ed-bot')).display,
          nav:document.querySelector('.ed-reader-nav').getClientRects().length>0})""")
        self.assertTrue(st['slidefit'])
        self.assertEqual(st['bot'], 'none')
        self.assertTrue(st['nav'])

    # ---------- 쪽 입력 타이핑 가드: 중간 장에서 화살표가 장을 움직이지 않는다 ----------
    def test_page_input_typing_guard(self):
        p = self.page()
        p.evaluate('deckGo(1,0)')                        # 중간 장(3장 중 2번째)
        p.keyboard.press('Shift')                        # 막대 복귀(클릭 대상 확보)
        p.click('.ed-bot .ed-page')
        p.keyboard.press('ArrowRight')
        p.keyboard.press('ArrowLeft')
        self.assertEqual(p.evaluate('deckInfo().slide'), 1)
        p.keyboard.press('3')                            # 숫자 입력도 장을 움직이지 않는다
        self.assertEqual(p.evaluate('deckInfo().slide'), 1)
        p.keyboard.press('Escape')                       # 빠져나오면 입력값이 현재 장으로 복귀
        self.assertEqual(p.evaluate("document.getElementById('edPage').value"), '2')


if __name__ == '__main__':
    unittest.main()
