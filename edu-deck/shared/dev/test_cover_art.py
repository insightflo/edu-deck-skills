#!/usr/bin/env python3
"""표지 아키텍트(ko-cover) 이식 계약 시험 (workspace/absorb/ko-cover-analysis.md).

[목적] ko-document-studio(ko-slide ko-cover-regression 견본, MIT)에서 이식한
       생성형 제도 표지가
       ① 엔진 assets/js/cover-art.js 가 기준 샘플의 엔진+마운트와 본문이 바이트 같고(베리타 이식)
       ② 기준 샘플 references/samples/ko-cover-regression.html 이 무결하게 보존되어 있으며
       ③ CSS 풀(전면 배치·인쇄·정적 완결)이 visual-motion.css 와 재생성된 양 셸에 함께 있고
       ④ build_deck 이 src 에 ko-cover 를 쓴 덱에만 엔진을 인라인하고(미사용 덱 불변)
       ⑤ 실제 브라우저에서 figure 가 ko-cover-live 로 살아나 캔버스에 그림이 생기며
          정적 모드(body.st-self)·인쇄 매체에서는 캔버스가 접히고 소재 이미지로 완결되며
          같은 덱의 ko-cover 둘 이상이 모두 자가 기동하는지를 잠근다.
[입력] 인코더로 만든 data: URI 흑백 도형 미니덱 + 실제 Chromium + 기준 샘플 파일.
[출력] 없음(단정문).
"""
import base64
import hashlib
import struct
import sys
import unittest
import zlib
from pathlib import Path

from bs4 import BeautifulSoup

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build  # noqa: E402
from check_deck import Report, static_checks  # noqa: E402

ENGINE = S / 'assets' / 'js' / 'cover-art.js'
SAMPLE = S / 'references' / 'samples' / 'ko-cover-regression.html'
VMCSS = S / 'assets' / 'css' / 'visual-motion.css'
SAMPLE_SHA = '4ebc23a18e1684a333f7b3abc8c56a7fa2ad994e56674f1a20540babbfd9c188'
NOTES = ('발표자 노트: 소재가 도면으로 재구성되는 표지 장면을 보여 주고 실물이 드러나는 의미를 '
         '설명한다. 인쇄·자습에서는 소재 이미지로 완결된다.') * 2

# ---- 시험용 흑백 도형 PNG(data: URI) — 사각 테두리·대각선·원판으로 윤곽 확보 ----


def _png(w, h, px):
    def chunk(t, d):
        return (struct.pack('>I', len(d)) + t + d
                + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF))
    raw = b''.join(b'\x00' + bytes(px[y * w * 3:(y + 1) * w * 3]) for y in range(h))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b''))


def _img_uri(w=96, h=96, ink=(30, 34, 44)):
    px = bytearray(b'\xf6\xf4\xec' * w * h)
    ink = bytes(ink)

    def put(x, y):
        if 0 <= x < w and 0 <= y < h:
            i = (y * w + x) * 3
            px[i:i + 3] = ink
    for x in range(10, w - 10):
        put(x, 10); put(x, h - 11)
    for y in range(10, h - 10):
        put(10, y); put(w - 11, y)
    for k in range(w):
        put(k, int(k * (h - 1) / (w - 1)))
    cx, cy, r = w // 2, h // 2, 20
    for yy in range(-r, r + 1):
        for xx in range(-r, r + 1):
            if xx * xx + yy * yy <= r * r:
                put(cx + xx, cy + yy)
    return 'data:image/png;base64,' + base64.b64encode(bytes(_png(w, h, px))).decode()


IMG = _img_uri()


def _cover_slide(extra='', preset='blueprint'):
    """ko-cover 표지 조각 — data-cover 약칭 preset/keepLines 만 쓰는 저작 계약 그대로."""
    return (f'<section class="slide cx" data-archetype="cover" style="padding:0">'
            f'<figure class="ko-cover ko-cover-bleed{extra}" '
            f'data-cover=\'{{"preset":"{preset}","keepLines":0}}\'>'
            f'<img class="ko-cover-img" src="{IMG}" alt="시험 흑백 도형">'
            f'<canvas class="ko-cover-canvas" aria-hidden="true"></canvas></figure>'
            f'<div class="cx-text" style="left:0;top:236px;width:1920px;align-items:center;text-align:center">'
            f'<h1 class="cx-title" style="color:var(--paper)">제도 표지</h1></div>'
            f'<aside class="notes">{NOTES}</aside></section>')


def _plain_slide():
    return ('<section class="slide" data-archetype="statement"><div class="pad">'
            '<h2 class="title">이동 목적지</h2>'
            f'<aside class="notes">{NOTES}</aside></div></section>')


def build_mini(slides, name):
    out = Path('/tmp/edudeck-cover-art') / name
    src = out.parent / ('src-' + name)
    src.mkdir(parents=True, exist_ok=True)
    srcs = []
    for i, body in enumerate(slides):
        p = src / f'{i:02d}-slide.html'
        p.write_text(body, encoding='utf-8')
        srcs.append(p)
    build('ko-cover 시험', srcs, [S / 'assets' / 'css'], [S / 'assets' / 'icons'], out)
    return out


def _sample_engine_text():
    """기준 샘플에서 엔진 가드 시작부터 마운트 IIFE 끝까지 잘라 낸다(원문 그대로)."""
    text = SAMPLE.read_text(encoding='utf-8')
    start = text.index('if (!window.createCoverReveal) {')
    end = text.index('\n</script>', start)
    return text[start:end]


class EngineAsset(unittest.TestCase):
    def test_header_and_contract_tokens(self):
        js = ENGINE.read_text(encoding='utf-8')
        self.assertIn('ko-document-studio', js.split('\n')[:8].__str__())
        self.assertIn('KO-DOCUMENT-MIT.txt', js)
        for token in ('window.createCoverReveal = createCoverReveal',
                      "querySelectorAll('.ko-cover')", 'data-cover',
                      'ko-cover-live', "playback = { autoplay: 'inView' }"):
            self.assertIn(token, js)
        self.assertNotIn('</script', js.lower())

    def test_port_body_verbatim_from_sample(self):
        js = ENGINE.read_text(encoding='utf-8')
        body = js.split('*/\n', 1)[1].strip('\n')
        self.assertEqual(body, _sample_engine_text().strip('\n'))

    def test_sample_benchmark_pinned(self):
        self.assertTrue(SAMPLE.exists())
        self.assertEqual(hashlib.sha256(SAMPLE.read_bytes()).hexdigest(), SAMPLE_SHA)


class CssGlue(unittest.TestCase):
    def test_visual_motion_and_shells(self):
        css = VMCSS.read_text(encoding='utf-8')
        for rule in ('.ko-cover{', '.ko-cover-bleed .ko-cover-img',
                     'body.st-self .ko-cover-canvas,body.st-printing .ko-cover-canvas',
                     '@media print{.ko-cover-canvas{display:none}}'):
            self.assertIn(rule, css)
        for shell in ('shell.html', 'pack-shell.html'):
            self.assertIn('.ko-cover-bleed', (S / 'assets' / shell).read_text(encoding='utf-8'))


class ConditionalInline(unittest.TestCase):
    def test_used_deck_gets_engine_unused_deck_does_not(self):
        with_cover = build_mini([_cover_slide(), _plain_slide()], 'with-cover.html')
        without = build_mini([_plain_slide(), _plain_slide()], 'without-cover.html')
        used = with_cover.read_text(encoding='utf-8')
        unused = without.read_text(encoding='utf-8')
        self.assertIn('createCoverReveal', used)
        self.assertIn('class="ko-cover', used)
        self.assertNotIn('createCoverReveal', unused)
        # 두 번째 ko-cover(패널형·다른 preset)도 같은 덱에서 함께 산다
        duo = build_mini([_cover_slide(), _cover_slide(extra='', preset='ink'), _plain_slide()],
                         'duo-cover.html')
        soup = BeautifulSoup(duo.read_text(encoding='utf-8'), 'html.parser')
        self.assertEqual(len(soup.select('figure.ko-cover')), 2)

    def test_static_checks_clean_on_ko_cover_slide(self):
        html_text = ('<html><head><title>시험</title></head><body><div id="stage">'
                     + _cover_slide() + '</div></body></html>')
        rep = Report()
        static_checks(html_text, BeautifulSoup(html_text, 'html.parser'), rep, False)
        bad = [i for i in rep.items if i["sev"] in ("ERROR", "WARN")]
        self.assertEqual(bad, [])


class BrowserBoot(unittest.TestCase):
    """Chromium 에서의 자가 기동·캔버스 드로잉·정적/인쇄 완결."""

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel='chrome')
        cls.deck = build_mini([_cover_slide(), _cover_slide(preset='ink'), _plain_slide()],
                              'browser.html')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def _open(self):
        page = self.browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.goto(self.deck.as_uri())
        page.wait_for_selector('.ko-cover', timeout=8000)
        page.wait_for_timeout(1400)  # 그리드→구성선→초기 체인까지
        return page

    def test_boot_live_and_canvas_paints(self):
        page = self._open()
        try:
            live = page.eval_on_selector_all('.ko-cover', 'els => els.map(e => e.classList.contains("ko-cover-live"))')
            self.assertTrue(all(live) and len(live) == 2, live)
            painted = page.evaluate('''() => {
              const cv = document.querySelector('.ko-cover-canvas');
              const ctx = cv.getContext('2d');
              const d = ctx.getImageData(0, 0, cv.width, cv.height).data;
              let n = 0;
              for (let i = 3; i < d.length; i += 4) if (d[i] > 8) n++;
              return n;
            }''')
            self.assertGreater(painted, 2000, painted)
        finally:
            page.close()

    def test_static_mode_falls_back_to_image(self):
        page = self._open()
        try:
            page.evaluate('document.body.classList.add("st-self")')
            page.wait_for_timeout(120)
            disp = page.eval_on_selector('.ko-cover-canvas', 'e => getComputedStyle(e).display')
            img = page.eval_on_selector('.ko-cover-img', 'e => getComputedStyle(e).visibility')
            self.assertEqual(disp, 'none')
            self.assertNotEqual(img, 'hidden')
        finally:
            page.close()

    def test_print_media_hides_canvas(self):
        page = self._open()
        try:
            page.emulate_media(media='print')
            page.wait_for_timeout(120)
            disp = page.eval_on_selector('.ko-cover-canvas', 'e => getComputedStyle(e).display')
            self.assertEqual(disp, 'none')
        finally:
            page.close()

    def test_revisit_keeps_figure_alive(self):
        page = self._open()
        try:
            page.keyboard.press('ArrowRight')   # 두 번째 장(패널형 ink)
            page.wait_for_timeout(400)
            page.keyboard.press('ArrowRight')   # 빈 장으로 이동
            page.wait_for_timeout(300)
            page.keyboard.press('ArrowLeft')
            page.keyboard.press('ArrowLeft')    # 표지로 복귀
            page.wait_for_timeout(500)
            alive = page.eval_on_selector('.ko-cover', 'e => e.classList.contains("ko-cover-live")')
            self.assertTrue(alive)
        finally:
            page.close()


if __name__ == '__main__':
    unittest.main()
