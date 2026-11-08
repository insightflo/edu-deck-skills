#!/usr/bin/env python3
"""arch-diagram 계열 시그니처 arch-trace 계약 시험 (TASK-arch-kit Stage 4).

[목적] 생성기(scripts/arch_layout.mjs) 산출 svg.dg 장에서
       ① 엔진이 'arch-diagram' 아키타입을 'arch-trace' 실행 이름으로 등록했고
       ② 단계마다 sigLog 에 arch-trace@k 가 정확히 1회씩 기록되며
       ③ dash-flow 경로에 .ed-particle 입자가 흐르고
       ④ 마지막 단계에서 step-hide 잔재가 0이고(정적 완결)
       ⑤ 인쇄 매체에서도 전 요소가 드러난다 — 를 잠근다.
[입력] svg.dg 1장 미니덱을 /tmp 에 빌드 + 실제 Chromium.
[출력] 없음(단정문).
"""
import re
import sys
import time
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build  # noqa: E402
import check_deck  # noqa: E402

OUT = Path('/tmp/edudeck-arch-trace')
SRC = OUT / 'src'
MOTION = (S / 'assets/js/motion.js').read_text(encoding='utf-8')

SLIDE = '''<section class="slide" data-archetype="arch-diagram" style="gap:20px">
  <div class="head"><p class="eyebrow">시험 · 아키텍처</p><h2 class="title">arch-trace 계약 시험</h2></div>
  <svg class="dg" viewBox="0 0 1664 500" role="img" aria-label="시험용 구성도: 클라이언트가 게이트웨이를 거쳐 앱에 닿는다">
    <title>arch-trace 시험</title>
    <g data-step="1"><rect class="k-frame" x="120" y="80" width="700" height="340" style="rx:12px"/>
      <text class="k-t-tag" x="140" y="120">경계</text></g>
    <g data-step="2"><rect class="k-paper" x="200" y="180" width="140" height="128" style="rx:9px"/>
      <text class="t-l" x="270" y="252" text-anchor="middle">GW</text></g>
    <g data-step="2"><rect class="k-blue" x="560" y="180" width="140" height="128" style="rx:9px"/>
      <text class="t-l" x="630" y="252" text-anchor="middle">App</text></g>
    <g data-step="3"><path class="k-ln-o dash-flow" d="M340 244 L560 244" marker-end="url(#ah-o)"/></g>
  </svg>
  <aside class="notes">시험용 장입니다. 경계가 먼저 뜨고 노드 두 개가 켜진 뒤 연결선이 그려지며 패킷이 흐르는지 확인합니다. 발표용 시험 시나리오이며 실제 시스템과 무관합니다.</aside>
</section>'''


def build_mini():
    SRC.mkdir(parents=True, exist_ok=True)
    p = SRC / '01.html'
    p.write_text(SLIDE, encoding='utf-8')
    html = OUT / 'deck.html'
    build('arch-trace 시험', [p], [S / 'assets/css'], [S / 'assets/icons'], html)
    return html


class ArchTraceTest(unittest.TestCase):
    """arch-diagram → arch-trace 시그니처 계약."""

    def test_engine_registers_signature(self):
        self.assertIn("'arch-diagram':'svg g[data-step]'", MOTION)
        self.assertIn("'arch-diagram':{name:'arch-trace'", MOTION)
        self.assertIn("draw:true", MOTION.split("'arch-diagram':")[1])
        self.assertIn("particles:true", MOTION.split("'arch-diagram':")[1])

    def test_archetype_registered(self):
        self.assertIn('arch-diagram', check_deck.ARCHETYPES)
        self.assertIn('arch-diagram', check_deck.VISUAL_ARCHS)

    @classmethod
    def setUpClass(cls):
        cls.html = build_mini()
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception:
            cls.browser = cls.pw.chromium.launch(channel='chrome')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def open(self):
        pg = self.browser.new_page(viewport={'width': 1920, 'height': 1080})
        pg.goto('file://' + str(self.html))
        pg.wait_for_timeout(600)
        return pg

    def test_siglog_once_per_step_and_static_complete(self):
        pg = self.open()
        for k in range(4):
            pg.evaluate(f"deckGo(0,{k})")
            pg.wait_for_timeout(500)
            if k == 3:
                deadline = time.time() + 4
                while time.time() < deadline:
                    if pg.evaluate("document.querySelectorAll('.slide')[0].querySelectorAll('.ed-particle').length"):
                        break
                    pg.wait_for_timeout(60)
        pg.wait_for_timeout(1200)
        res = pg.evaluate("""()=>({
          sigs: window.eduMotion.sigLog.filter(s=>s.slide===0).map(s=>s.sig+'@'+s.step),
          hidden: document.querySelectorAll('.slide')[0].querySelectorAll('[data-step].step-hide').length
        })""")
        self.assertEqual(res['sigs'], ['arch-trace@0', 'arch-trace@1', 'arch-trace@2', 'arch-trace@3'],
                         f'sigLog 순서·1회 발화 어긋남: {res["sigs"]}')
        self.assertEqual(res['hidden'], 0, '마지막 단계에 숨은 단계 잔재')
        pg.close()

    def test_particles_flowed(self):
        pg = self.open()
        pg.evaluate("deckGo(0,3)")
        seen = False
        deadline = time.time() + 4
        while time.time() < deadline:
            if pg.evaluate("document.querySelectorAll('.slide')[0].querySelectorAll('.ed-particle').length"):
                seen = True
                break
            pg.wait_for_timeout(60)
        self.assertTrue(seen, 'dash-flow 경로에 .ed-particle 미관측')
        pg.close()

    def test_print_reveals_all(self):
        pg = self.open()
        pg.emulate_media(media='print')
        pg.wait_for_timeout(300)
        hidden = pg.evaluate("document.querySelectorAll('.slide')[0].querySelectorAll('[data-step].step-hide').length")
        self.assertEqual(hidden, 0, '인쇄 매체에서 숨은 단계 잔재')
        pg.close()


if __name__ == '__main__':
    unittest.main()
