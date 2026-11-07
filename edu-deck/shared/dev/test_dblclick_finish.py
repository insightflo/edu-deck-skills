#!/usr/bin/env python3
"""뷰어 더블클릭 "현재 장 끝까지 재생" 계약 시험 (TASK-dblclick-finish).

[목적] 데스크탑 뷰의 dblclick 이
       ① 남은 단계를 순차 재생해 마지막 단계에 도달하고 장 인덱스를 바꾸지 않으며
       ② 이미 마지막 단계(마지막 장)에서는 아무 일도 하지 않고
       ③ click 1회는 여전히 1단계만 넘기고(기존 동작 회귀)
       ④ 재생 중 이전 이동을 하면 잔여 재생이 취소되되 공개된 단계는 유지되고
       ⑤ reduced-motion 에서는 지연 없이 즉시 완결된다 — 를 잠근다.
[입력] 2장 × data-step 4단계 미니덱을 /tmp 에 빌드 + 실제 Chromium.
[출력] 없음(단정문).
"""
import sys
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build  # noqa: E402

OUT = Path('/tmp/edudeck-dblclick')
SRC = OUT / 'src'

NOTES = ('이 장에서는 시험용 내용을 차근차근 확인합니다. 발표 중에는 단계를 넘기며 '
         '각 요소가 정해진 순서에 드러나고, 자습 모드에서는 최종 상태만 보입니다. '
         '아래 설명을 따라 진행하면 됩니다. 추가 설명을 조금 더 덧붙입니다. ')

SLIDE = '''<section class="slide" data-archetype="statement">
  <div class="head"><p class="eyebrow">시험</p><h2 class="title">더블클릭 시험 {n}</h2></div>
  <div class="col" style="flex:1;gap:24px;justify-content:center">
    <p class="big" data-step="1" style="font-size:40px">한 번째 공개 {n}</p>
    <p class="big" data-step="2" style="font-size:40px">두 번째 공개 {n}</p>
    <p class="big" data-step="3" style="font-size:40px">세 번째 공개 {n}</p>
    <p class="big" data-step="4" style="font-size:40px">네 번째 공개 {n}</p>
    <button class="kbd" type="button">가드 버튼 {n}</button>
  </div>
  <aside class="notes">''' + NOTES + '''</aside>
</section>'''


def build_mini():
    SRC.mkdir(parents=True, exist_ok=True)
    srcs = []
    for i in (1, 2):
        p = SRC / f'{i:02d}.html'
        p.write_text(SLIDE.format(n=i), encoding='utf-8')
        srcs.append(p)
    html = OUT / 'deck.html'
    build('dblclick 시험', srcs, [S / 'assets/css'],
          [S / 'assets/icons'], html)
    return html


class DblClickFinishTest(unittest.TestCase):
    """데스크탑 뷰 dblclick = 현재 장 끝까지 재생(장 이동 없음)."""

    @classmethod
    def setUpClass(cls):
        cls.html = build_mini()
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(channel='chrome')

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()

    def _page(self, **ctx_kw):
        ctx = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080}, **ctx_kw)
        pg = ctx.new_page()
        pg.goto('file://' + str(self.html))
        pg.wait_for_timeout(1500)
        return ctx, pg

    def _info(self, pg):
        return pg.evaluate('window.deckInfo()')

    def test_dblclick_finishes_remaining_steps_on_same_slide(self):
        ctx, pg = self._page()
        try:
            self.assertEqual(self._info(pg), {'slide': 0, 'step': 0,
                                              'maxStep': 4, 'count': 2})
            pg.mouse.dblclick(1400, 540)
            pg.wait_for_timeout(3500)
            info = self._info(pg)
            self.assertEqual(info['slide'], 0, '장을 넘기면 안 된다')
            self.assertEqual(info['step'], 4, '남은 단계가 끝까지 공개돼야 한다')
            # 순차 재생 확인 — 발화 직후에는 마지막 단계가 아니어야 한다
            # (click 2회 진행분 이후 finishSteps 가 나머지를 틱마다 공개)
        finally:
            ctx.close()

    def test_dblclick_at_last_step_is_noop(self):
        ctx, pg = self._page()
        try:
            pg.evaluate('deckGo(1)')  # 마지막 장, 동기 점프 = 마지막 단계
            pg.wait_for_timeout(300)
            before = self._info(pg)
            pg.mouse.dblclick(1400, 540)
            pg.wait_for_timeout(800)
            self.assertEqual(self._info(pg), before,
                             '마지막 장 마지막 단계의 더블클릭은 무동작이어야 한다')
        finally:
            ctx.close()

    def test_single_click_still_advances_one_step(self):
        ctx, pg = self._page()
        try:
            pg.mouse.click(1400, 540)
            pg.wait_for_timeout(300)
            self.assertEqual(self._info(pg)['step'], 1, 'click 1회 = 1단계')
            self.assertEqual(self._info(pg)['slide'], 0)
        finally:
            ctx.close()

    def test_retreat_cancels_pending_finish(self):
        ctx, pg = self._page()
        try:
            pg.mouse.dblclick(1400, 540)
            pg.wait_for_timeout(700)   # click 2회 + 틱 1~2개 발화한 중간
            pg.keyboard.press('ArrowLeft')
            settled = self._info(pg)
            pg.wait_for_timeout(3600)  # 잔여 재생이 취소됐는지 충분히 관찰
            after = self._info(pg)
            self.assertEqual(after, settled,
                             '이전 이동 뒤 잔여 재생이 더 진행되면 안 된다')
            self.assertLess(after['step'], 4,
                            '취소됐다면 마지막 단계에 도달하지 않는다')
            self.assertGreaterEqual(after['step'], 0)
            self.assertEqual(after['slide'], 0)
        finally:
            ctx.close()

    def test_reduced_motion_finishes_instantly(self):
        ctx, pg = self._page(reduced_motion='reduce')
        try:
            pg.mouse.dblclick(1400, 540)
            pg.wait_for_timeout(400)   # 재생 간격 없이 즉시 완결
            info = self._info(pg)
            self.assertEqual(info['step'], 4)
            self.assertEqual(info['slide'], 0)
        finally:
            ctx.close()

    def test_dblclick_on_guarded_element_does_not_finish(self):
        ctx, pg = self._page()
        try:
            # .chk·버튼 등 조작 요소 위의 더블클릭은 장 진행을 넘기지 않는다
            pg.locator('.slide.active button.kbd').dblclick()
            pg.wait_for_timeout(1200)
            info = self._info(pg)
            self.assertEqual(info['step'], 0,
                             '가드 요소 위 더블클릭은 단계를 넘기면 안 된다')
        finally:
            ctx.close()


if __name__ == '__main__':
    unittest.main()
