"""Behavior contracts for the shared visual runtime (not the independent visual audit).
Breaking the shell injection, pack adapter, semantic gating, or cancellation must fail.
"""
import json,sys,unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
S=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(S/'scripts'))
from build_deck import build
from check_deck import launch,Report,static_checks
from bs4 import BeautifulSoup
import os, tempfile
_TEST_OUT = Path(os.environ.get('EDU_DECK_TEST_OUT', str(Path(tempfile.gettempdir()) / 'edu-deck-dev-tests')))
OUT = _TEST_OUT / 'visual-motion'
class VisualMotion(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  OUT.mkdir(parents=True,exist_ok=True)
  build('Motion contracts',sorted((S/'assets/snippets').glob('*.html')),[S/'assets/css'],[S/'assets/icons'],OUT/'gallery.html')
  cls.pw=sync_playwright().start();cls.browser=launch(cls.pw)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.pw.stop()
 def page(self,reduced=False):
  c=self.browser.new_context(viewport={'width':1920,'height':1080},reduced_motion='reduce' if reduced else 'no-preference');self.addCleanup(c.close)
  p=c.new_page();p.goto((OUT/'gallery.html').as_uri());p.evaluate('document.fonts.ready');return p
 def test_all_variants_dispatch_and_animate(self):
  p=self.page()
  self.assertTrue(p.evaluate('!!window.eduMotion'),'shell must install the shared motion engine')
  rows=p.evaluate('''async()=>{let out=[];const N=deckInfo().count;for(let i=0;i<N;i++){deckGo(i,0);await new Promise(r=>requestAnimationFrame(r));let s=document.querySelector('.slide.active');out.push({arch:s.dataset.archetype,signature:s.dataset.motionSignature,n:s.getAnimations({subtree:true}).length});}return out;}''')
  self.assertEqual(len({r['arch'] for r in rows}),36)
  # arch-flow는 부품(data-c=stack)이 'stack-reveal'을 직접 기록한다 — 엔진 레시피 밖이라
  # data-motion-signature가 없는 게 계약이다(애니메이션은 부품의 is-play CSS가 돌린다).
  self.assertTrue(all(r['n'] and (r['signature'] or r['arch']=='arch-flow') for r in rows),rows)
 def test_step_replay_and_no_future_answer(self):
  p=self.page();self.assertTrue(p.evaluate('!!window.eduMotion'))
  idx=p.evaluate('()=>[...document.querySelectorAll("#stage>.slide")].findIndex(s=>s.dataset.archetype==="quiz-ab")')
  p.evaluate('(i)=>deckGo(i,0)',idx)
  self.assertEqual(p.locator('.active .opt.right.lit').count(),0)
  p.evaluate('(i)=>deckGo(i,2)',idx);p.wait_for_timeout(40)
  self.assertGreater(p.locator('.active .opt.right.lit').count(),0)
  self.assertGreater(p.evaluate('document.querySelector(".active").getAnimations({subtree:true}).length'),0)
  p.evaluate('(i)=>deckGo(i,0)',idx)
  self.assertEqual(p.locator('.active .opt.right.lit').count(),0)
 def test_static_modes_cancel_without_revealing_future_steps(self):
  p=self.page();self.assertTrue(p.evaluate('!!window.eduMotion'))
  p.evaluate("deckGo([...document.querySelectorAll('#stage>.slide')].findIndex(s=>s.dataset.archetype==='agenda'),0)");p.emulate_media(reduced_motion='reduce');p.wait_for_timeout(150)
  self.assertEqual(p.evaluate('document.getAnimations().filter(a=>a.playState==="running").length'),0)
  self.assertGreater(p.locator('.active .step-hide').count(),0)
  p.emulate_media(reduced_motion='no-preference');p.keyboard.press('s');p.wait_for_timeout(150)
  self.assertEqual(p.evaluate('document.getAnimations().filter(a=>a.playState==="running").length'),0)
  p.evaluate('window.dispatchEvent(new Event("beforeprint"))')
  self.assertEqual(p.evaluate('document.getAnimations().filter(a=>a.playState==="running").length'),0)
 def test_fallback_groups_outgoing_and_incoming(self):
  p=self.page();p.evaluate('document.startViewTransition=undefined;deckGo(0,0)');p.wait_for_timeout(50)
  p.keyboard.press('ArrowRight');p.wait_for_timeout(40)
  self.assertEqual(p.locator('.ed-ghost').count(),1)
  self.assertEqual(p.evaluate('deckInfo().slide'),1)
  self.assertGreater(p.evaluate('document.querySelector(".ed-ghost").getAnimations().length'),0)
  p.emulate_media(reduced_motion='reduce');p.wait_for_timeout(50)
  self.assertEqual(p.locator('.ed-ghost').count(),0)
 def test_font_is_loaded_offline(self):
  p=self.page(True)
  self.assertTrue(p.evaluate('document.fonts.check("32px \'Pretendard Variable\'")'))
  self.assertIn('Pretendard Variable',p.evaluate('getComputedStyle(document.querySelector(".slide")).fontFamily'))
  self.assertGreater(p.evaluate('[...document.fonts].filter(f=>f.family.includes("Pretendard")&&f.status==="loaded").length'),0)
 def test_text_only_warning(self):
  text='<html><head><title>Test</title></head><body><div id="stage"><section class="slide" data-archetype="mechanism"><h2 class="title">원리</h2><p>글로만 설명한 본문입니다.</p><aside class="notes">'+('설명을 차근차근 확인합니다. '*12)+'</aside></section></div></body></html>'
  r=Report();static_checks(text,BeautifulSoup(text,'html.parser'),r,False)
  self.assertTrue(any(x['kind']=='시각 짝' for x in r.items),r.items)
if __name__=='__main__':unittest.main()
