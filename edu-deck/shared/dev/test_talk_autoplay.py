#!/usr/bin/env python3
"""Acceptance: 셸 자동 발표(P1 재지시) — A 칩·남은 시간 카운트다운·임계값 클래스·발표자 표시.

기존 셸 eduAuto 엔진(800ms 단계·data-sec 홀드·기본 6초·최소 2초·마지막 장 정지)은 불변.
이 시험이 잠그는 것은 재지시로 얹은 표시 계약뿐이다:
  ① #edAutoBtn 칩이 .ed-bot 안에 있고 클릭·A 키·ㅁ 입력으로 토글된다(aria-pressed·ed-auto 반영).
  ② #edAutoClock 이 켜진 동안 이 장 잔여 시간을 mm:ss 로 표시하고,
     ≤15초 .is-red · ≤5초 .is-blink 를 단다(움직임 줄이기에서는 깜빡임이 점등으로 바뀐다).
  ③ talk 덱은 ed-clock 에 '· A m:ss' 접미사가 붙고 발표자 창에는 '· 자동 m:ss' 가 표시된다
     (발표자 창에는 토글이 없다 — 표시 전용, A 입력도 삼킨다). 비발표 덱은 ed-clock 자체가 없다.
  ④ 자동 발표 의미는 그대로: 단계 소진 → 홀드 → 다음 장, 아무 키나 누르면 즉시 정지,
     마지막 장에서 스스로 멈춘다.

/tmp 에 4장 시험 덱(data-sec 8·3·10·3, talk.total=26)을 빌드해 실제 Chromium(channel='chrome')으로 잰다.
"""
import sys
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build  # noqa: E402
from check_deck import launch  # noqa: E402

OUT = Path('/tmp/edudeck-autoplay')
SRC = OUT / 'src'
NOTES = '짧은 노트'
SECS = [8, 3, 10, 3]
TALK = {'total': 26, 'rate': 300}


def slide(i, title, sec):
    arch = 'cover' if i == 1 else 'statement'
    steps = '' if i != 2 else ''.join(
        f'<p class="body" data-step="{k}" style="font-size:30px">단계 {k}.</p>' for k in range(1, 3))
    inner = (f'<div class="cx-inner"><p class="cx-eyebrow">시험</p><h2 class="cx-title">{title}</h2></div>'
             if arch == 'cover' else
             f'<div class="head"><p class="eyebrow">시험</p><h2 class="title">{title}</h2></div>{steps}')
    return (f'<section class="slide" data-archetype="{arch}" data-sec="{sec}">{inner}'
            f'<aside class="notes">{NOTES}</aside></section>')


class AutoPlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SRC.mkdir(parents=True, exist_ok=True)
        srcs = []
        for i, sec in enumerate(SECS, 1):
            p = SRC / f'{i:02d}-s.html'
            p.write_text(slide(i, f'장 {i}', sec), encoding='utf-8')
            srcs.append(p)
        cls.html = OUT / 'auto.html'
        build('자동 발표 시험', srcs, [S / 'assets/css'], [S / 'assets/icons'],
              cls.html, study={'talk': dict(TALK)})
        cls.html_plain = OUT / 'auto-plain.html'
        build('자동 발표 시험(무계약)', srcs, [S / 'assets/css'], [S / 'assets/icons'], cls.html_plain)
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def page(self, url=None, reduced=False):
        c = self.browser.new_context(viewport={'width': 1920, 'height': 1080},
                                     reduced_motion='reduce' if reduced else 'no-preference')
        self.addCleanup(c.close)
        p = c.new_page()
        p.goto(url or self.html.as_uri())
        p.evaluate('document.fonts.ready')
        p.wait_for_timeout(400)
        return p

    def wait_auto_off(self, p, tries=80):
        for _ in range(tries):
            if not p.evaluate('window.eduAuto.on()'):
                return True
            p.wait_for_timeout(100)
        return False

    # ---------- ① A 칩 ----------
    def test_chip_toggle_key_and_click(self):
        p = self.page()
        self.assertTrue(p.evaluate("!!document.querySelector('.ed-bot #edAutoBtn')"),
                        'A 칩은 .ed-bot 안에 있어야 한다')
        self.assertTrue(p.evaluate("!!document.querySelector('.ed-bot #edAutoClock')"))
        p.keyboard.press('a'); p.wait_for_timeout(300)
        self.assertTrue(p.evaluate('window.eduAuto.on()'))
        self.assertEqual(p.evaluate("document.getElementById('edAutoBtn').getAttribute('aria-pressed')"), 'true')
        self.assertTrue(p.evaluate("document.documentElement.classList.contains('ed-auto')"))
        p.click('#edAutoBtn'); p.wait_for_timeout(200)
        self.assertFalse(p.evaluate('window.eduAuto.on()'))
        self.assertEqual(p.evaluate("document.getElementById('edAutoBtn').getAttribute('aria-pressed')"), 'false')
        # 한자리 ㅁ — 실 IME 입력은 못 흉내내므로 같은 key 값의 합성 keydown 으로 본다
        p.evaluate("document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'ㅁ',bubbles:true}))")
        p.wait_for_timeout(200)
        self.assertTrue(p.evaluate('window.eduAuto.on()'), '한자리 ㅁ 으로도 켜진다')
        p.keyboard.press('a')

    # ---------- ② 남은 시간 칩 ----------
    def test_countdown_mmss_and_thresholds(self):
        p = self.page()
        self.assertEqual(p.evaluate("document.getElementById('edAutoClock').textContent"), '')
        p.evaluate('deckGo(2,0)')  # data-sec=10, 단계 없음
        p.keyboard.press('a')
        p.wait_for_timeout(1400)  # 0.7s 진입 지연 후 10초 홀드 예약
        t = p.evaluate("document.getElementById('edAutoClock').textContent")
        self.assertRegex(t, r'^\d{2}:\d{2}$', 'mm:ss 형식')
        left = int(t.split(':')[0]) * 60 + int(t.split(':')[1])
        self.assertGreaterEqual(left, 6, '10초 홀드가 거의 그대로 남아 있어야 한다')
        self.assertLessEqual(left, 10)
        self.assertTrue(p.evaluate("document.getElementById('edAutoClock').classList.contains('is-red')"),
                        '≤15초는 is-red')
        self.assertFalse(p.evaluate("document.getElementById('edAutoClock').classList.contains('is-blink')"))
        for _ in range(80):  # ≤5초까지 기다려 is-blink 확인
            if p.evaluate("document.getElementById('edAutoClock').classList.contains('is-blink')"):
                break
            p.wait_for_timeout(100)
        else:
            self.fail('잔여 ≤5초에서 is-blink 가 붙지 않았다')
        p.keyboard.press('a'); p.wait_for_timeout(200)
        self.assertEqual(p.evaluate("document.getElementById('edAutoClock').textContent"), '')

    def test_reduced_motion_blink_is_solid(self):
        p = self.page(reduced=True)
        p.evaluate('deckGo(2,0)')
        p.keyboard.press('a')
        for _ in range(120):
            if p.evaluate("document.getElementById('edAutoClock').classList.contains('is-blink')"):
                break
            p.wait_for_timeout(100)
        anim = p.evaluate("""()=>{const c=document.getElementById('edAutoClock');
          return {blink:c.classList.contains('is-blink'),
                  anims:c.getAnimations().filter(a=>a.playState==='running').length}}""")
        self.assertTrue(anim['blink'])
        self.assertEqual(anim['anims'], 0, '움직임 줄이기에서는 깜빡임 애니메이션이 없어야 한다')
        p.keyboard.press('a')

    # ---------- ③ talk 시계 접미사 + 발표자 표시 ----------
    def test_talk_clock_suffix_and_presenter(self):
        p = self.page()
        self.assertNotIn('· A', p.evaluate("document.getElementById('ed-clock').textContent"))
        p.keyboard.press('a'); p.wait_for_timeout(600)
        self.assertRegex(p.evaluate("document.getElementById('ed-clock').textContent"),
                         r'·\s*A\s*\d+:\d{2}')
        with p.context.expect_page() as pop_info:
            p.keyboard.press('v')  # 아무 키 정지 규칙으로 V 가 자동 발표를 끈다 — 켰다는 증거는 위에서 끝냄
        pop = pop_info.value
        self.addCleanup(pop.close)
        pop.wait_for_timeout(800)
        self.assertFalse(p.evaluate('window.eduAuto.on()'), '아무 키 입력은 자동 발표를 멈춘다(V 도 마찬가지)')
        # 자동 상태는 post 페이로드를 타고 온다 — 다시 켜고 장 이동 이벤트로 보낸다
        p.keyboard.press('a'); p.wait_for_timeout(300)
        p.evaluate('deckGo(1,0)')
        for _ in range(50):
            t = pop.evaluate("(document.querySelector('.ed-pres-clock .r')||{textContent:''}).textContent")
            if '자동' in t:
                break
            pop.wait_for_timeout(100)
        self.assertIn('자동', t, '발표자 창 시계에 자동 남은 시간이 표시돼야 한다')
        self.assertIsNone(pop.evaluate("document.getElementById('edAutoBtn')"),
                          '발표자 창에 A 칩이 있으면 안 된다')
        # 발표자 창에서 A 를 눌러도 양쪽 자동 발표는 건드리지 않는다(표시 전용)
        pop.keyboard.press('a'); pop.wait_for_timeout(300)
        self.assertTrue(p.evaluate('window.eduAuto.on()'))
        self.assertFalse(pop.evaluate('window.eduAuto.on()'))
        p.keyboard.press('a')

    def test_non_talk_deck_also_autoplays_but_no_clock(self):
        p = self.page(url=self.html_plain.as_uri())
        self.assertIsNone(p.evaluate("document.getElementById('ed-clock')"))
        self.assertTrue(p.evaluate("!!document.getElementById('edAutoBtn')"),
                        '자동 발표는 talk 계약이 없는 덱에서도 동작한다')
        p.keyboard.press('a'); p.wait_for_timeout(300)
        self.assertTrue(p.evaluate('window.eduAuto.on()'))
        self.assertRegex(p.evaluate("document.getElementById('edAutoClock').textContent"), r'^\d{2}:\d{2}$')
        p.keyboard.press('a')

    # ---------- ④ 의미 불변 ----------
    def test_semantics_unchanged(self):
        p = self.page(url=self.html_plain.as_uri())
        p.evaluate('deckGo(1,0)')  # 단계 2개 + data-sec=3
        p.keyboard.press('a')
        p.wait_for_timeout(1000)
        s1 = p.evaluate('deckInfo().step')
        self.assertEqual(s1, 1, '남은 단계를 한 단계씩 공개한다')
        p.wait_for_timeout(900)
        self.assertEqual(p.evaluate('deckInfo().step'), 2)
        p.keyboard.press('ArrowRight')  # 아무 키로 즉시 정지
        self.assertFalse(p.evaluate('window.eduAuto.on()'))
        # 마지막 장에서 스스로 멈춘다
        p.evaluate('deckGo(3,0)')
        p.keyboard.press('a')
        self.assertTrue(self.wait_auto_off(p, 80), '마지막 장에서 자동 정지')
        self.assertEqual(p.evaluate('deckInfo().slide'), 3)


if __name__ == '__main__':
    unittest.main()
