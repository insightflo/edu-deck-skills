"""P0-2 무성 장 감사 계약: motion.js 의 발화 기록(sigLog·edumotion 이벤트)을 검증한다.

계약(지시문 v3 P0-2):
  (a) 시그니처가 실제로 발화하면 window.eduMotion.sigLog 에 {slide,step,sig} 가 쌓이고
      같은 내용의 edumotion 이벤트(detail) 가 따라나온다.
  (b) 발화하지 않은 (장,단계) 는 기록이 남지 않는다 — 숨은 대상만 있는 단계는 무성이다.
  (c) 같은 장·단계의 중복 deckslide/deckstep 재생 금지 계약은 유지된다(기록도 중복되지 않는다).
      다른 장을 거쳐 되돌아오면 엔트리 시그니처가 다시 발화하므로 기록은 다시 쌓인다(재방문 정책).
"""
import sys, unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build
from check_deck import launch
import os, tempfile
_TEST_OUT = Path(os.environ.get('EDU_DECK_TEST_OUT', str(Path(tempfile.gettempdir()) / 'edu-deck-dev-tests')))

OUT = _TEST_OUT / 'sig-log'


class SigLogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True, exist_ok=True)
        build('Motion contracts', sorted((S / 'assets/snippets').glob('*.html')),
              [S / 'assets/css'], [S / 'assets/icons'], OUT / 'gallery.html')
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def page(self):
        c = self.browser.new_context(viewport={'width': 1920, 'height': 1080},
                                     reduced_motion='no-preference')
        self.addCleanup(c.close)
        p = c.new_page()
        p.goto((OUT / 'gallery.html').as_uri())
        p.evaluate('document.fonts.ready')
        p.wait_for_timeout(80)
        return p

    def idx(self, p, arch):
        return p.evaluate('(a)=>[...document.querySelectorAll("#stage>.slide")].findIndex(s=>s.dataset.archetype===a)', arch)

    def test_a_signature_fire_is_logged_with_event(self):
        p = self.page()
        self.assertTrue(p.evaluate('!!window.eduMotion && Array.isArray(window.eduMotion.sigLog)'),
                        'shell must expose window.eduMotion.sigLog')
        p.evaluate('window.__sigEvents=[];document.addEventListener("edumotion",e=>window.__sigEvents.push(e.detail))')
        i = self.idx(p, 'quiz-ab')
        p.evaluate(f'deckGo({i},0)')
        p.wait_for_timeout(40)
        entries = [e for e in p.evaluate('()=>window.eduMotion.sigLog') if e['slide'] == i]
        self.assertTrue(entries, 'quiz-ab entry must be logged')
        sig = entries[-1]
        self.assertEqual(sig['step'], 0)
        self.assertEqual(sig['sig'], p.evaluate(f'document.querySelectorAll("#stage>.slide")[{i}].dataset.motionSignature'))
        events = p.evaluate('()=>window.__sigEvents.filter(e=>e.slide===%d)' % i)
        self.assertTrue(events and events[-1] == sig, f'edumotion event detail must match sigLog entry: {events} vs {sig}')

    def test_b_silent_step_leaves_no_record(self):
        p = self.page()
        i = self.idx(p, 'quiz-ab')
        p.evaluate(f'deckGo({i},0)')
        p.wait_for_timeout(40)
        # 1단계 공개 대상을 전부 숨긴다 — 이 단계는 발화할 것이 없다(무성 단계).
        # quiz-ab 의 보기는 data-lit 으로 공개되므로 lit 도 함께 숨긴다.
        p.evaluate(f'''() => document.querySelectorAll("#stage>.slide")[{i}]
            .querySelectorAll('[data-step="1"],[data-add="1"],[data-only="1"],[data-lit="1"]').forEach(e=>e.style.visibility='hidden')''')
        p.evaluate(f'deckGo({i},1)')
        p.wait_for_timeout(40)
        step1 = [e for e in p.evaluate('()=>window.eduMotion.sigLog') if e['slide'] == i and e['step'] == 1]
        self.assertEqual(step1, [], 'hidden-target step must not be logged as fired')
        step0 = [e for e in p.evaluate('()=>window.eduMotion.sigLog') if e['slide'] == i and e['step'] == 0]
        self.assertTrue(step0, 'visible entry step should still be logged')

    def test_c_duplicate_events_do_not_replay_or_relog(self):
        p = self.page()
        i = self.idx(p, 'quiz-ab')
        p.evaluate(f'deckGo({i},0)')
        p.wait_for_timeout(40)
        before = len(p.evaluate('()=>window.eduMotion.sigLog'))
        for _ in range(3):
            p.evaluate('document.dispatchEvent(new Event("deckslide"));document.dispatchEvent(new Event("deckstep"))')
        p.wait_for_timeout(60)
        self.assertEqual(len(p.evaluate('()=>window.eduMotion.sigLog')), before,
                         'duplicate deckslide/deckstep on same slide+step must not relog or replay')
        p.evaluate(f'deckGo({i+1},0)')
        p.wait_for_timeout(40)
        p.evaluate(f'deckGo({i},0)')
        p.wait_for_timeout(40)
        entries = [e for e in p.evaluate('()=>window.eduMotion.sigLog') if e['slide'] == i and e['step'] == 0]
        # 2026-11-04 user rule: a step already presented never replays (revisit = settled, no motion).
        self.assertEqual(len(entries), 1, 'revisit must not replay the entry signature or log a new record')
        self.assertEqual(p.evaluate('()=>document.querySelector(".slide.active").getAnimations({subtree:true}).length'), 0,
                         'revisited slide must show its settled state without motion')

    def test_every_gallery_slide_fires_on_entry(self):
        p = self.page()
        total = p.evaluate('deckInfo().count')
        for i in range(total):
            p.evaluate(f'deckGo({i})')
            p.wait_for_timeout(20)
        seen = {e['slide'] for e in p.evaluate('()=>window.eduMotion.sigLog')}
        self.assertEqual(seen, set(range(total)), f'silent slides in gallery: {sorted(set(range(total))-seen)}')


if __name__ == '__main__':
    unittest.main()
