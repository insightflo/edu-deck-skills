#!/usr/bin/env python3
"""키보드 모션 조작 계약 시험 — G 끝까지 재생 · M 자동 완주 토글.

[목적] 엔진 keydown 이
       ① G(g/ㅎ) = dblclick 과 같은 finishSteps — 남은 단계 순차 재생, 장 이동 없음
       ② 마지막 단계에서 G 는 무동작
       ③ M(m/ㅡ) 토글: 켜면 localStorage 'edeck-motion-auto'='1' + 토스트 안내,
         장을 넘기면(←·→·Home 등 사용자 넘김) 도착 장의 남은 단계를 자동 완주
       ④ 끄면 다시 입력마다 한 단계 — 장 이동 후 step 0 에 머문다
       ⑤ deckGo(검사기 점프)는 모드와 무관하게 자동 완주를 일으키지 않는다 — 를 잠근다.
[입력] 3장 × data-step 4단계 미니덱을 /tmp 에 빌드 + 실제 Chromium.
[출력] 없음(단정문).
"""
import sys
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build  # noqa: E402

OUT = Path('/tmp/edudeck-keymotion')
SRC = OUT / 'src'

NOTES = ('이 장에서는 시험용 내용을 차근차근 확인합니다. 발표 중에는 단계를 넘기며 '
         '각 요소가 정해진 순서에 드러나고, 자습 모드에서는 최종 상태만 보입니다. '
         '아래 설명을 따라 진행하면 됩니다. 추가 설명을 조금 더 덧붙입니다. ')

SLIDE = '''<section class="slide" data-archetype="statement">
  <div class="head"><p class="eyebrow">시험</p><h2 class="title">키 모션 시험 {n}</h2></div>
  <div class="col" style="flex:1;gap:24px;justify-content:center">
    <p class="big" data-step="1" style="font-size:40px">한 번째 공개 {n}</p>
    <p class="big" data-step="2" style="font-size:40px">두 번째 공개 {n}</p>
    <p class="big" data-step="3" style="font-size:40px">세 번째 공개 {n}</p>
    <p class="big" data-step="4" style="font-size:40px">네 번째 공개 {n}</p>
  </div>
  <aside class="notes">''' + NOTES + '''</aside>
</section>'''

# 확인 문제 장 — .chk 마크업 + archetype check 로 판별. 정답 표식은 수동 단계와 무관한 부수 표식.
QUIZ = '''<section class="slide" data-archetype="check">
  <div class="head"><p class="eyebrow">확인</p><h2 class="title">퀴즈 장</h2></div>
  <div class="chk">
    <div class="chk-q"><span class="chk-n">1</span>어느 쪽이 맞나요?</div>
    <div class="chk-opts">
      <button class="chk-o" type="button">갑</button>
      <button class="chk-o chk-right" type="button">을</button>
    </div>
    <div class="chk-why">해설</div>
  </div>
  <p class="big" data-step="1" style="font-size:40px">퀴즈 단계 1</p>
  <p class="big" data-step="2" style="font-size:40px">퀴즈 단계 2</p>
</section>'''


def build_mini():
    SRC.mkdir(parents=True, exist_ok=True)
    srcs = []
    for i in (1, 2, 3):
        p = SRC / f'{i:02d}.html'
        p.write_text(SLIDE.format(n=i), encoding='utf-8')
        srcs.append(p)
    html = OUT / 'deck.html'
    build('키 모션 시험', srcs, [S / 'assets/css'],
          [S / 'assets/icons'], html)
    q = SRC / 'quiz-deck'
    q.mkdir(exist_ok=True)
    qsrcs = []
    for name, body in (('01-a.html', SLIDE.format(n=1)),
                       ('02-quiz.html', QUIZ),
                       ('03-b.html', SLIDE.format(n=3))):
        p = q / name
        p.write_text(body, encoding='utf-8')
        qsrcs.append(p)
    html_quiz = OUT / 'deck-quiz.html'
    build('키 모션 퀴즈 시험', qsrcs, [S / 'assets/css'],
          [S / 'assets/icons'], html_quiz)
    return html, html_quiz


class KeyMotionTest(unittest.TestCase):
    """G = 현재 장 끝까지 재생 · M = 장 진입 시 자동 완주 토글(지속)."""

    @classmethod
    def setUpClass(cls):
        cls.html, cls.html_quiz = build_mini()
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(channel='chrome')

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()

    def _page(self, html=None):
        ctx = self._browser.new_context(viewport={'width': 1920, 'height': 1080})
        pg = ctx.new_page()
        pg.goto('file://' + str(html or self.html))
        pg.wait_for_timeout(1500)
        return ctx, pg

    def _info(self, pg):
        return pg.evaluate('window.deckInfo()')

    def test_g_finishes_remaining_steps_on_same_slide(self):
        ctx, pg = self._page()
        try:
            self.assertEqual(self._info(pg)['step'], 0)
            pg.keyboard.press('g')
            pg.wait_for_timeout(3500)
            info = self._info(pg)
            self.assertEqual(info['slide'], 0, 'G는 장을 넘기면 안 된다')
            self.assertEqual(info['step'], 4, 'G는 남은 단계를 끝까지 공개해야 한다')
        finally:
            ctx.close()

    def test_g_at_last_step_is_noop(self):
        ctx, pg = self._page()
        try:
            pg.evaluate('deckGo(2)')  # 마지막 장 동기 점프 = 마지막 단계
            pg.wait_for_timeout(300)
            before = self._info(pg)
            pg.keyboard.press('g')
            pg.wait_for_timeout(800)
            self.assertEqual(self._info(pg), before,
                             '마지막 단계의 G는 무동작이어야 한다')
        finally:
            ctx.close()

    def test_m_on_autofinishes_on_user_navigation(self):
        ctx, pg = self._page()
        try:
            pg.keyboard.press('m')            # 자동 완주 켬
            pg.wait_for_timeout(300)          # 토스트 2.6초 자동 소멸 전에 확인
            toast = pg.evaluate("document.querySelector('.ed-toast') && document.querySelector('.ed-toast').classList.contains('on')")
            self.assertTrue(toast, '토글 안내 토스트가 보여야 한다')
            flag = pg.evaluate("localStorage.getItem('edeck-motion-auto')")
            self.assertEqual(flag, '1', '방식은 localStorage 에 남겨야 한다')
            pg.wait_for_timeout(3300)          # 현재 장(0) 즉시 완주 분산 완료 대기
            self.assertEqual(self._info(pg)['step'], 4, '토글 켜짐 즉시 현재 장 완주')
            pg.keyboard.press('ArrowRight')   # 다음 장 → 자동 완주
            pg.wait_for_timeout(3500)
            info = self._info(pg)
            self.assertEqual(info['slide'], 1)
            self.assertEqual(info['step'], 4, '모드 켬 = 장 진입 시 끝까지 재생')
        finally:
            ctx.close()

    def test_m_off_restores_step_per_input(self):
        ctx, pg = self._page()
        try:
            pg.keyboard.press('m')            # 켬
            pg.wait_for_timeout(3500)         # 현재 장(0) 완주 확정 후
            pg.keyboard.press('ArrowRight')
            pg.wait_for_timeout(3500)         # 장1 자동 완주
            pg.keyboard.press('m')            # 끔 — 현재 재생 중이면 취소
            pg.wait_for_timeout(300)
            self.assertEqual(pg.evaluate("localStorage.getItem('edeck-motion-auto')"), '0')
            pg.keyboard.press('ArrowRight')   # 장2 진입 — 자동 완주 없음
            pg.wait_for_timeout(1000)
            info = self._info(pg)
            self.assertEqual(info['slide'], 2)
            self.assertEqual(info['step'], 0, '모드 끔 = 장 진입 후 0단계에 머문다')
        finally:
            ctx.close()

    def test_deckgo_is_not_affected_by_mode(self):
        ctx, pg = self._page()
        try:
            pg.keyboard.press('m')
            pg.wait_for_timeout(3500)         # 현재 장(0) 완주 분산 대기
            pg.evaluate('deckGo(2, 0)')       # 검사기 점프 — instant
            pg.wait_for_timeout(1200)
            self.assertEqual(self._info(pg)['step'], 0,
                             'deckGo 점프는 자동 완주를 일으키지 않는다')
        finally:
            ctx.close()

    def test_m_stops_on_quiz_slide_and_resumes_after(self):
        ctx, pg = self._page(self.html_quiz)
        try:
            pg.keyboard.press('m')            # 자동 완주 켬 — 장0(비퀴즈) 완주
            pg.wait_for_timeout(3500)
            self.assertEqual(self._info(pg)['step'], 4)
            pg.keyboard.press('ArrowRight')   # 퀴즈 장 진입 — 자동 완주가 멈춘다
            pg.wait_for_timeout(2000)
            info = self._info(pg)
            self.assertEqual(info['slide'], 1)
            self.assertEqual(info['step'], 0,
                             '확인 문제 장에서는 단계가 자동으로 열리면 안 된다')
            toast = pg.evaluate("(document.querySelector('.ed-toast')||{textContent:''}).textContent")
            self.assertIn('멈췄', toast)
            pg.keyboard.press('ArrowRight')   # 수동으로는 단계가 열린다
            pg.wait_for_timeout(300)
            self.assertEqual(self._info(pg)['step'], 1)
            pg.keyboard.press('ArrowRight')   # 장의 마지막 단계
            pg.wait_for_timeout(300)
            self.assertEqual(self._info(pg)['step'], 2)
            pg.keyboard.press('ArrowRight')   # 다음 장 → 자동 완주 재개
            pg.wait_for_timeout(3500)
            info = self._info(pg)
            self.assertEqual(info['slide'], 2)
            self.assertEqual(info['step'], 4,
                             '퀴즈 장을 지나면 자동 완주가 재개된다')
        finally:
            ctx.close()


if __name__ == '__main__':
    unittest.main()
