"""Acceptance: data-fx effects and authoring patterns (.code/.tabs/.faq/.pin-shot).

Builds a temporary deck into /tmp and drives real Chromium (channel='chrome'):
every fx fires an animation at its reveal moment and settles on the authored
final DOM/text/position; static modes (reduced motion, body.st-self, print
emulation) show the final state immediately; back-navigation never replays;
patterns behave without advancing the deck; check_deck reports the new rules.
"""
import sys, unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build
from check_deck import launch, Report, static_checks

OUT = Path('/tmp/edudeck-fx-pat')
SRC = OUT / 'src'
NOTES = ('이 장에서는 시험용 내용을 차근차근 확인합니다. 발표 중에는 단계를 넘기며 '
         '각 요소가 정해진 순서에 드러나고, 자습 모드에서는 최종 상태만 보입니다. '
         '아래 설명을 따라 진행하면 됩니다. 추가 설명을 조금 더 덧붙입니다. ')

IMG1PX = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ'
          'AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')

SLIDES = {
'01-cover.html': '''<section class="slide" data-archetype="cover">
  <div class="cx-inner"><p class="cx-eyebrow">시험</p><h2 class="cx-title">모션과 패턴 시험</h2></div>
  <aside class="notes">''' + NOTES + '''</aside></section>''',

'02-fx.html': '''<section class="slide" data-archetype="statement">
  <div class="head"><p class="eyebrow">모션 시험</p><h2 class="title">여덟 효과 점검</h2></div>
  <div class="big" style="font-size:64px">효과를 지켜봅니다</div>
  <p class="body" style="font-size:30px">기존 <s data-fx="strike">3일</s> 걸리던 일이
    <b data-fx="count" data-from="72">4</b>시간으로 줄고, 핵심은
    <span data-fx="mark">한 번의 확인</span>입니다.
    <span class="stamp ok" data-fx="stamp">통과</span>
    <span class="kbd" data-fx="press">Enter</span> 로 완료합니다.</p>
  <p class="body" data-fx="travel" style="--dx:-200px;font-size:28px">travel 문장이 자리로 들어옵니다.</p>
  <p class="body" data-fx="block" style="--dx:-200px;font-size:28px">block 문장이 벽에 부딪힙니다.</p>
  <p class="body" data-fx="type" data-fx-speed="30" style="font-size:28px">타자처럼 한 자씩 드러납니다.</p>
  <p class="body" style="font-size:28px"><span data-step="1" data-fx="strike" id="fx-step">단계 1에서 그어지는 선</span></p>
  <aside class="notes">''' + NOTES + '''</aside></section>''',

'03-patterns.html': '''<section class="slide" data-archetype="worked-example">
  <div class="head"><p class="eyebrow">패턴 시험</p><h2 class="title">도구 패턴 모음</h2></div>
  <div class="row" style="flex:1;min-height:0">
    <div class="col f1" style="display:flex;flex-direction:column;gap:24px">
      <div class="code">
        <div class="code-head"><span>터미널</span><button type="button" class="code-copy">복사</button></div>
<pre><span class="p">$ </span>python3 build.py
<span class="out">OK done</span>
<span class="p">$ </span>python3 check.py
<span class="c"># 이 주석은 복사되지 않는다</span></pre>
      </div>
      <div class="faq">
        <details><summary>질문 하나입니다</summary><p>첫 번째 답변입니다.</p></details>
        <details><summary>질문 둘입니다</summary><p>두 번째 답변입니다.</p></details>
      </div>
      <button type="button" class="go" data-go="4" data-tab="2">다음 장 2번 탭으로</button>
    </div>
    <div class="col f1" style="display:flex;flex-direction:column;gap:24px">
      <div class="tabs">
        <div class="tab-bar"><button>① 첫 탭</button><button>② 둘째 탭</button></div>
        <div class="tab-pane"><p class="body">첫 탭 내용입니다.</p></div>
        <div class="tab-pane"><p class="body">둘째 탭 내용입니다.</p></div>
      </div>
      <figure class="pin-shot">
        <div class="pin-frame"><img src="''' + IMG1PX + '''" alt="시험용 화면 이미지">
          <button type="button" class="pin" data-k="1" style="left:30%;top:30%">1</button>
          <button type="button" class="pin" data-k="2" style="left:65%;top:60%">2</button>
        </div>
      </figure>
      <ol class="pin-list"><li data-k="1">첫 지점 설명입니다</li><li data-k="2">둘째 지점 설명입니다</li></ol>
    </div>
  </div>
  <aside class="notes">''' + NOTES + '''</aside></section>''',

'04-tabs2.html': '''<section class="slide" data-archetype="worked-example">
  <div class="head"><p class="eyebrow">연결 시험</p><h2 class="title">탭 두 개 더</h2></div>
  <div class="tabs">
    <div class="tab-bar"><button>① 가나다</button><button>② 라마바</button></div>
    <div class="tab-pane"><p class="body">가나다 탭입니다.</p></div>
    <div class="tab-pane"><p class="body">라마바 탭입니다.</p></div>
  </div>
  <aside class="notes">''' + NOTES + '''</aside></section>''',

'05-checker.html': '''<section class="slide" data-archetype="statement">
  <div class="head"><p class="eyebrow">검사 시험</p><h2 class="title">검사기 규칙 확인</h2></div>
  <p class="body" style="font-size:28px"><span data-fx="spin">알 수 없는 효과</span></p>
  <p class="body" style="font-size:28px"><span data-fx="mark" data-crayon="underline">효과와 크레파스 중복</span></p>
  <p class="body" style="font-size:28px"><span data-fx="type" data-fx-at="2600">늦게 시작하는 타자</span></p>
  <p class="body" style="font-size:28px">The quick brown fox jumps over the lazy dog quickly again.</p>
  <figure class="pin-shot"><div class="pin-frame"><img src="https://example.com/shot.png" alt="외부 이미지">
    <button type="button" class="pin" data-k="1" style="left:10%;top:10%">1</button></div></figure>
  <ol class="pin-list"><li data-k="1">외부 주소는 허용하지 않습니다</li></ol>
  <aside class="notes">''' + NOTES + '''</aside></section>''',

'06-korean.html': '''<section class="slide" data-archetype="statement">
  <div class="head"><p class="eyebrow">문장 시험</p><h2 class="title">한국어 문장 속 이름</h2></div>
  <p class="body" style="font-size:30px">Claude Code 와 MCP 서버 설정은 환경 변수로 관리하고, API 키는 별도 보관함에 둡니다.</p>
  <aside class="notes">''' + NOTES + '''</aside></section>''',

'07-closing.html': '''<section class="slide" data-archetype="closing">
  <div class="head"><h2 class="title">마침</h2></div><p class="body">시험을 마칩니다.</p>
  <aside class="notes">''' + NOTES + '''</aside></section>''',
}


def anims(page, sel):
    return page.evaluate(
        "(s)=>{const e=document.querySelector(s);return e?e.getAnimations({subtree:true}).length:0;}", sel)


class FxPatterns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SRC.mkdir(parents=True, exist_ok=True)
        srcs = []
        for name, html in sorted(SLIDES.items()):
            p = SRC / name
            p.write_text(html, encoding='utf-8')
            srcs.append(p)
        cls.html = OUT / 'deck.html'
        build('모션·패턴 시험', srcs, [S / 'assets/css'], [S / 'assets/icons'], cls.html)
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def page(self, reduced=False):
        c = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            reduced_motion='reduce' if reduced else 'no-preference')
        self.addCleanup(c.close)
        p = c.new_page()
        p.goto(self.html.as_uri())
        p.evaluate('document.fonts.ready')
        return p

    # ---------- B: data-fx ----------
    def test_fx_fire_at_reveal(self):
        p = self.page()
        p.evaluate('deckGo(1,0)')
        p.wait_for_timeout(80)
        for sel in ('[data-fx="strike"]', '[data-fx="mark"]', '[data-fx="stamp"]',
                    '[data-fx="travel"]', '[data-fx="block"]', '[data-fx="press"]',
                    '[data-fx="type"]'):
            self.assertGreater(anims(p, f'.slide.active {sel}'), 0, sel)
        # count 타자(count/type)는 요소 상태로 발화를 본다
        self.assertTrue(p.evaluate(
            "document.querySelector('.slide.active [data-fx=type] .ed-fx-ch')!=null"))
        cnt = p.evaluate("document.querySelector('.slide.active [data-fx=count]').textContent")
        self.assertNotEqual(cnt, '4')
        # step 가림 요소는 아직 발화하지 않는다
        self.assertIsNone(p.evaluate(
            "document.querySelector('#fx-step .ed-fx-strike')"))
        self.assertEqual(anims(p, '#fx-step'), 0)
        # 단계를 넘기면 그때 발화한다
        p.evaluate('deckGo(1,1)')
        p.wait_for_timeout(80)
        self.assertIsNotNone(p.evaluate(
            "document.querySelector('#fx-step .ed-fx-strike')"))

    def test_fx_settle_on_final(self):
        p = self.page()
        p.evaluate('deckGo(1,1)')
        p.wait_for_timeout(2600)
        ok = p.evaluate('''()=>{
          const s=document.querySelector('.slide.active');
          const out={};
          out.countText=s.querySelector('[data-fx=count]').textContent==='4';
          out.typeText=s.querySelector('[data-fx=type]').textContent==='타자처럼 한 자씩 드러납니다.';
          out.noChars=!s.querySelector('.ed-fx-ch');
          out.strike=!!s.querySelector('[data-fx=strike]>.ed-fx-strike');
          out.mark=!!s.querySelector('[data-fx=mark]>.ed-fx-mark');
          out.transforms=['travel','block','press'].every(n=>{
            const m=getComputedStyle(s.querySelector('[data-fx='+n+']')).transform;
            return m==='none'||m==='matrix(1, 0, 0, 1, 0, 0)';});
          // .stamp 의 최종은 도장 각도 rotate(-12deg) 그대로
          const dm=new DOMMatrixReadOnly(getComputedStyle(s.querySelector('[data-fx=stamp]')).transform);
          out.stampRot=Math.abs(Math.atan2(dm.b,dm.a)*180/Math.PI+12)<0.5;
          out.anims=s.getAnimations({subtree:true}).filter(a=>a.playState==='running').length===0;
          return out;}''')
        self.assertTrue(all(ok.values()), ok)

    def test_fx_static_modes_final_immediately(self):
        p = self.page(reduced=True)
        p.evaluate('deckGo(1,1)')
        p.wait_for_timeout(60)
        ok = p.evaluate('''()=>{
          const s=document.querySelector('.slide.active');
          return {strike:!!s.querySelector('[data-fx=strike]>.ed-fx-strike'),
            mark:!!s.querySelector('[data-fx=mark]>.ed-fx-mark'),
            count:s.querySelector('[data-fx=count]').textContent==='4',
            type:s.querySelector('[data-fx=type]').textContent==='타자처럼 한 자씩 드러납니다.',
            none:document.getAnimations().filter(a=>a.playState==='running').length===0};}''')
        self.assertTrue(all(ok.values()), ok)
        # body.st-self 도 같은 즉시 최종 상태
        p2 = self.page()
        p2.evaluate("document.body.classList.add('st-self')")
        p2.evaluate('deckGo(1,1)')
        p2.wait_for_timeout(60)
        ok2 = p2.evaluate('''()=>{
          const s=document.querySelector('.slide.active');
          return {strike:!!s.querySelector('[data-fx=strike]>.ed-fx-strike'),
            count:s.querySelector('[data-fx=count]').textContent==='4',
            none:document.getAnimations().filter(a=>a.playState==='running').length===0};}''')
        self.assertTrue(all(ok2.values()), ok2)

    def test_fx_no_replay_on_back(self):
        p = self.page()
        p.evaluate('deckGo(1,0)')
        p.wait_for_timeout(120)
        p.evaluate('deckGo(0,0)')
        p.wait_for_timeout(60)
        p.evaluate('deckGo(1,0)')
        p.wait_for_timeout(120)
        self.assertEqual(
            p.evaluate('document.querySelector(".slide.active").getAnimations({subtree:true}).filter(a=>a.playState==="running").length'), 0)

    # ---------- C: patterns ----------
    def test_code_copy_excludes_prompt_out_comment(self):
        p = self.page()
        p.evaluate('deckGo(2,0)')
        p.evaluate('''()=>{window.__copied=null;
          Object.defineProperty(navigator,'clipboard',{configurable:true,value:
            {writeText:t=>{window.__copied=t;return Promise.resolve();}}});}''')
        p.click('.code-copy')
        p.wait_for_timeout(60)
        copied = p.evaluate('window.__copied')
        self.assertIsNotNone(copied)
        self.assertIn('python3 build.py', copied)
        self.assertIn('python3 check.py', copied)
        self.assertNotIn('OK done', copied)
        self.assertNotIn('주석', copied)
        self.assertNotIn('$', copied)
        self.assertEqual(p.evaluate("document.querySelector('.code-copy').textContent"), '복사됨')

    def test_tabs_click_and_arrow(self):
        p = self.page()
        p.evaluate('deckGo(2,0)')
        self.assertTrue(p.evaluate("document.querySelectorAll('.active .tab-pane')[1].hidden"))
        p.click('.active .tab-bar button:nth-child(2)')
        self.assertFalse(p.evaluate("document.querySelectorAll('.active .tab-pane')[1].hidden"))
        self.assertTrue(p.evaluate("document.querySelectorAll('.active .tab-pane')[0].hidden"))
        p.locator('.active .tab-bar button[aria-selected="true"]').press('ArrowRight')
        self.assertFalse(p.evaluate("document.querySelectorAll('.active .tab-pane')[0].hidden"))
        self.assertTrue(p.evaluate("document.querySelectorAll('.active .tab-pane')[1].hidden"))

    def test_tabs_faq_in_print_and_study(self):
        p = self.page()
        p.evaluate('deckGo(2,0)')
        p.emulate_media(media='print')
        p.wait_for_timeout(60)
        self.assertEqual(p.evaluate(
            "document.querySelectorAll('.active .tab-pane:not([hidden])').length"), 2)
        self.assertEqual(p.evaluate(
            "document.querySelectorAll('.active .tab-pane-label').length"), 2)
        self.assertEqual(p.evaluate(
            "document.querySelectorAll('.active .faq details[open]').length"), 2)
        p.emulate_media(media='screen')
        p.wait_for_timeout(60)
        self.assertEqual(p.evaluate(
            "document.querySelectorAll('.active .tab-pane:not([hidden])').length"), 1)
        p.evaluate("document.body.classList.add('st-self')")
        p.wait_for_timeout(60)
        self.assertEqual(p.evaluate(
            "document.querySelectorAll('.active .tab-pane:not([hidden])').length"), 2)
        self.assertEqual(p.evaluate(
            "document.querySelectorAll('.active .faq details[open]').length"), 2)

    def test_pins_pair_highlight(self):
        p = self.page()
        p.evaluate('deckGo(2,0)')
        p.hover('.pin[data-k="2"]')
        self.assertTrue(p.evaluate("document.querySelector('.pin[data-k=\\'2\\']').classList.contains('on')"))
        self.assertTrue(p.evaluate("document.querySelector('.pin-list li[data-k=\\'2\\']').classList.contains('on')"))
        p.click('.pin-list li[data-k="1"]')
        self.assertTrue(p.evaluate("document.querySelector('.pin[data-k=\\'1\\']').classList.contains('on')"))
        self.assertTrue(p.evaluate("document.querySelector('.pin-list li[data-k=\\'1\\']').classList.contains('on')"))

    def test_pattern_clicks_do_not_advance(self):
        p = self.page()
        p.evaluate('deckGo(2,0)')
        p.wait_for_timeout(60)
        for sel in ('.code pre', '.tab-pane', '.faq summary', '.pin-list li',
                    '.pin-frame', '.tab-bar button:first-child'):
            p.locator(f'.active {sel}').first.click()
            self.assertEqual(p.evaluate('deckInfo().slide'), 2, sel)

    def test_go_link_jumps_slide_and_tab(self):
        p = self.page()
        p.evaluate('deckGo(2,0)')
        p.click('.active .go')
        p.wait_for_timeout(80)
        self.assertEqual(p.evaluate('deckInfo().slide'), 3)
        self.assertFalse(p.evaluate("document.querySelectorAll('.active .tab-pane')[1].hidden"))

    # ---------- E: check_deck rules ----------
    def test_checker_rules(self):
        text = self.html.read_text(encoding='utf-8')
        rep = Report()
        static_checks(text, BeautifulSoup(text, 'html.parser'), rep, False)
        items = rep.items
        has = lambda kind, sev=None, slide=None, frag='': any(
            x['kind'] == kind and (sev is None or x['sev'] == sev)
            and (slide is None or x['slide'] == slide) and frag in x['message']
            for x in items)
        self.assertTrue(has('모션', 'ERROR', 5, 'spin'), items)
        self.assertTrue(has('모션', 'WARN', 5, 'crayon'), items)
        self.assertTrue(has('모션 길이', 'WARN', 5), items)
        self.assertTrue(has('외국어 문장', 'WARN', 5), items)
        self.assertTrue(has('화면 핀', 'ERROR', 5), items)
        self.assertFalse(has('외국어 문장', 'WARN', 6), items)


if __name__ == '__main__':
    unittest.main()
