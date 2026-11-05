"""W1/W2 regressions: real scene effects and rendered glyph/background support.

Removing semantic replay or shrinking an avatar back to 40px must fail. The
pixel oracle renders the same glyphs with a rectangular, unclipped background;
it then tests their actual ink against the original rounded background shape.
It is not a bounding-box-only test and cannot pass by hiding overflowing ink.
"""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build
from check_deck import launch


def glyph_support(page, selector):
    """Measure actual rasterized glyph pixels against the original round shape."""
    el = page.locator(selector)
    el.scroll_into_view_if_needed()
    # 세로 읽기에서는 스크롤이 지나며 단계가 자동 공개되어 위쪽 배치가 밀릴 수 있다.
    # 공개가 멈춘 뒤 좌표를 재야 클립이 어긋나지 않는다. 수만 px 문서의 전체 캡처는
    # 무거우므로 화면 안에 들어온 요소를 뷰포트 좌표로 잘라 찍는다(오라클은 같다).
    # rAF 대기는 프레임이 멎은 헤드리스에서 영원히 걸릴 수 있어 고정 시간으로 둔다.
    page.wait_for_timeout(80)
    info = el.evaluate('''e=>{const r=e.getBoundingClientRect(),c=getComputedStyle(e),sl=e.closest('.slide'),sw=sl?sl.getBoundingClientRect().width:innerWidth;return {text:e.textContent,x:r.x,y:r.y,w:r.width,h:r.height,font:parseFloat(c.fontSize),scale:sw/1920,radius:c.borderTopLeftRadius,style:e.getAttribute('style')};}''')
    margin = 10
    clip = {'x': max(0, info['x']-margin), 'y': max(0, info['y']-margin), 'width': info['w']+2*margin, 'height': info['h']+2*margin}
    # Keep the real font, wrapping, line height and layout. Only remove clipping
    # and curvature to recover the glyphs a clipping-based "fix" would conceal.
    el.evaluate("e=>{e.style.setProperty('border-radius','0','important');e.style.setProperty('overflow','visible','important');}")
    ink = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert('RGB')
    el.evaluate("e=>e.style.setProperty('color','transparent','important')")
    blank = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert('RGB')
    el.evaluate("(e,s)=>s===null?e.removeAttribute('style'):e.setAttribute('style',s)", info['style'])
    diff = ImageChops.difference(ink, blank)
    radius = float(info['radius'].rstrip('%px'))
    if '%' in info['radius']:
        radius = min(info['w'], info['h']) * radius / 100
    radius = min(radius, info['w']/2, info['h']/2)
    outside = pixels = 0
    for y in range(diff.height):
        for x in range(diff.width):
            if max(diff.getpixel((x, y))) < 35:
                continue
            pixels += 1
            px = x + clip['x'] - info['x'] + .5
            py = y + clip['y'] - info['y'] + .5
            # Rounded rectangle signed-distance, with a 1px safe ink margin.
            cx = min(max(px, radius), info['w']-radius)
            cy = min(max(py, radius), info['h']-radius)
            if px < 1 or py < 1 or px > info['w']-1 or py > info['h']-1 or (px-cx)**2+(py-cy)**2 > max(0, radius-1)**2:
                outside += 1
    return {**info, 'glyph_pixels': pixels, 'unsupported_glyph_pixels': outside}


class ReviewRemediation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='edu-review-')
        cls.out = Path(os.environ.get('ED_REVIEW_OUT', cls.tmp.name))
        cls.out.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(S/'dev/fill_test.py'), str(cls.out/'filled')], check=True, capture_output=True)
        build('Review regressions', sorted((cls.out/'filled/src').glob('*.html')), [S/'assets/css'], [S/'assets/icons'], cls.out/'gallery.html')
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.tmp.cleanup()

    def page(self, width=1920, mode='normal'):
        p = self.browser.new_page(viewport={'width': width, 'height': 1080 if width==1920 else 844}, reduced_motion='reduce' if mode=='reduced' else 'no-preference')
        self.addCleanup(p.close)
        p.goto((self.out/'gallery.html').as_uri())
        p.evaluate('document.fonts.ready')
        p.evaluate("deckGo([...document.querySelectorAll('#stage>.slide')].findIndex(s=>s.dataset.archetype==='before-after'),3)")
        p.wait_for_timeout(1200)
        if mode=='study':
            p.keyboard.press('s')
            p.wait_for_timeout(100)
        if mode=='print':
            p.emulate_media(media='print')
            p.evaluate('dispatchEvent(new Event("beforeprint"))')
        return p

    def test_glyph_ink_fits_background_in_all_reading_modes(self):
        results = []
        for width, mode in [(1920,'normal'),(1920,'reduced'),(1920,'study'),(1920,'print'),(320,'normal'),(390,'reduced'),(768,'study'),(1024,'normal')]:
            p = self.page(width,mode)
            selector = '#stage>.slide[data-archetype="before-after"] .av'
            # Independent reviewer reproductions plus every supported name length.
            for text in ['김','팀장','저처커','노도로모','WWWW']:
                p.locator(selector).first.evaluate('(e,t)=>e.textContent=t',text)
                row = glyph_support(p,selector+' >> nth=0')
                row.update(width=width,mode=mode)
                results.append(row)
            p.close()
        (self.out/'avatar-pixels.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
        # 축소 세로 읽기에서는 글리프 잉크도 배율의 제곱으로 줄어든다 — 임계값도 같은 비율로.
        self.assertTrue(all(r['glyph_pixels']>10*min(1,r['scale'])**2 for r in results),results)
        # computed fontSize 는 transform 전의 작성값이라 모든 폭에서 같다 — 바닥은 유지.
        self.assertTrue(all(r['font']>=16 for r in results),results)
        self.assertEqual([r for r in results if r['unsupported_glyph_pixels']],[], 'Actual glyph ink leaves its rounded high-contrast background')

    def test_before_after_wipes_prior_result_not_window(self):
        p = self.page()
        ix = "([...document.querySelectorAll('#stage>.slide')].findIndex(s=>s.dataset.archetype==='before-after'))"
        p.evaluate(f'deckGo({ix},1)')
        p.wait_for_timeout(1000)
        before = p.locator('.active .at').first.inner_text()
        p.evaluate(f'deckGo({ix},2)')
        p.evaluate('document.getAnimations().forEach(a=>{a.pause();a.currentTime=150})')
        old = p.locator('.active .ed-wipe-before')
        self.assertGreater(old.count(),0,'A real prior-result overlay must connect the two scenes')
        self.assertEqual(old.inner_text(),before)
        self.assertEqual(p.evaluate("document.querySelector('.active .win').getAnimations().length"),0)
        # New and old layers counter-translate, so words stay stationary while
        # the boundary wipes. A plain panel translation cannot satisfy this.
        transforms = p.locator('.active .ed-wipe,.active .ed-wipe-before').evaluate_all("es=>es.map(e=>getComputedStyle(e).transform)")
        self.assertEqual(len(transforms),2)
        self.assertTrue(all(t!='none' for t in transforms),transforms)
        effects=p.evaluate_handle('document.getAnimations()')
        p.evaluate('as=>as.forEach(a=>a.currentTime=300)',effects)
        avatar=p.locator('.active .av').last
        moving=Image.open(io.BytesIO(avatar.screenshot())).convert('RGB')
        p.evaluate('as=>as.forEach(a=>a.currentTime=1200)',effects)
        stable=Image.open(io.BytesIO(avatar.screenshot())).convert('RGB')
        self.assertIsNone(ImageChops.difference(moving,stable).getbbox(),'Wipe must not cover the adjacent speaker label')
        p.evaluate(f'deckGo({ix},0)')
        self.assertEqual(p.locator('.ed-wipe').count(),0)
        self.assertGreater(p.locator('.active .a.step-hide').count(),0)

    def test_worked_replay_stays_inside_current_semantic_step(self):
        p = self.page()
        results=[]
        find_ix = "(v)=>[...document.querySelectorAll('#stage>.slide')].findIndex(s=>s.dataset.variant===v)"
        for var in ['chat-points','doc-points','sheet-points','form-points','mail-points','msgr-points']:
            step = 2
            p.evaluate(f'()=>deckGo(({find_ix})({json.dumps(var)}),0)')
            p.wait_for_timeout(900)
            p.evaluate(f'()=>deckGo(({find_ix})({json.dumps(var)}),{step})')
            p.evaluate('document.getAnimations().forEach(a=>{a.pause();a.currentTime=150})')
            row=p.evaluate('''()=>{const s=document.querySelector('.slide.active');return {variant:s.dataset.variant,windowMotion:[...s.querySelectorAll('.win,.card')].reduce((n,e)=>n+e.getAnimations().length,0),replay:[...s.querySelectorAll('.ed-scene-cue')].map(e=>({text:e.parentElement.textContent,hidden:!!e.closest('.step-hide,.gone'),animations:e.getAnimations().length})),future:[...s.querySelectorAll('[data-step="3"]')].every(e=>e.classList.contains('step-hide'))}}''')
            results.append(row)
        (self.out/'semantic-replay.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
        self.assertTrue(all(r['replay'] for r in results),results)
        self.assertTrue(all(r['windowMotion']==0 and r['future'] for r in results),results)
        self.assertTrue(all(not e['hidden'] and e['animations'] for r in results for e in r['replay']),results)
        p.emulate_media(reduced_motion='reduce')
        p.wait_for_timeout(30)
        self.assertEqual(p.locator('.ed-scene-cue').count(),0)


if __name__=='__main__':
    unittest.main()
