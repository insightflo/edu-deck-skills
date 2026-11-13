#!/usr/bin/env python3
"""공통 모션 기법 draft 계약 시험 (TASK-tech-reveal-absorb).

[목적] data-fx="draft"(이미지 도면 드로잉)가
       ① motion.js FX 표 ↔ check_deck FX_KINDS 에 같은 이름·예산(2400≤3000)으로 등록되고
       ② 실제 브라우저에서 aria-hidden 캔버스 오버레이가 발화·2400ms 안에 제거되며
       ③ 정적 모드·뒤로가기 재방문에서는 캔버스 없이 저작 <img> 만 남고
       ④ 오염 캔버스(SecurityError)에서 이미지만 즉시 보이며 'fx-draft-degraded' 를 기록하고
       ⑤ check_deck 이 외부 http(s) src 를 WARN, data: URI 를 무WARN 으로 보고하고
       ⑥ 기존 실덱에 data-fx="draft" 가 없어 회귀 영향이 0임을 잠근다.
[입력] 인코더로 만든 data: URI 흑백 이미지 미니덱 + 실제 Chromium.
[출력] 없음(단정문).
"""
import base64
import os
import re
import struct
import sys
import unittest
import zlib
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build  # noqa: E402
from check_deck import FX_KINDS, Report, static_checks  # noqa: E402

MOTION = (S / 'assets' / 'js' / 'motion.js').read_text(encoding='utf-8')
OUT = Path('/tmp/edudeck-fx-draft')
SRC = OUT / 'src'
REAL_DECK = os.environ.get('EDU_DECK_TEST_DECK', '')

NOTES = '발표자 노트: 도면이 그려지는 장면을 보여 주고 실물 이미지가 드러나는 의미를 설명한다.' * 2


def _png(w, h, px):
    """RGB 바이트 배열을 최소 PNG로 인코딩 — 외부 의존 없이 시험 이미지 생성."""
    def chunk(t, d):
        return (struct.pack('>I', len(d)) + t + d
                + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF))
    raw = b''.join(b'\x00' + bytes(px[y * w * 3:(y + 1) * w * 3]) for y in range(h))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b''))


def _test_img_uri(w=96, h=96):
    """흑백 도형 PNG data: URI — 테두리·대각선·원판으로 소벨 가장자리 확보."""
    px = bytearray(b'\xf7\xf5\xee' * w * h)
    ink = bytes((40, 46, 56))

    def put(x, y):
        if 0 <= x < w and 0 <= y < h:
            i = (y * w + x) * 3
            px[i:i + 3] = ink
    for x in range(12, w - 12):                       # 사각 테두리
        for t in range(3):
            put(x, 12 + t)
            put(x, h - 15 + t)
    for y in range(12, h - 12):
        for t in range(3):
            put(12 + t, y)
            put(w - 15 + t, y)
    for k in range(w):                                # 대각선
        for t in (-1, 0, 1):
            put(k + t, int(k * (h - 1) / (w - 1)))
    cx, cy, r = w // 2, h // 2, 22                    # 중심 원판
    for yy in range(-r, r + 1):
        for xx in range(-r, r + 1):
            if xx * xx + yy * yy <= r * r:
                put(cx + xx, cy + yy)
    return 'data:image/png;base64,' + base64.b64encode(bytes(_png(w, h, px))).decode()


IMG = _test_img_uri()


def _slide(img_src, fx=True, notes=NOTES):
    attr = ' data-fx="draft"' if fx else ''
    fig = (f'<div style="width:400px"><img src="{img_src}" alt="시험 흑백 도형"'
           f' style="width:100%;display:block"{attr}></div>' if img_src else '')
    return (f'<section class="slide" data-archetype="statement"><div class="pad">'
            f'<h2 class="title">도면 드로잉</h2>{fig}'
            f'<aside class="notes">{notes}</aside></div></section>')


def build_mini():
    SRC.mkdir(parents=True, exist_ok=True)
    srcs = []
    for i, body in enumerate((_slide(IMG), _slide(IMG), _slide('', fx=False))):
        p = SRC / f'{i:02d}-slide.html'
        p.write_text(body, encoding='utf-8')
        srcs.append(p)
    html = OUT / 'deck.html'
    build('fx draft 시험', srcs, [S / 'assets/css'], [S / 'assets/icons'], html)
    return html


def check_items(img_src):
    """img src 하나를 단 미니 section 을 static_checks 에 태워 보고 항목을 돌려준다."""
    html_text = ('<html><body><div id="stage">' + _slide(img_src)
                 + '</div></body></html>')
    rep = Report()
    static_checks(html_text, BeautifulSoup(html_text, 'html.parser'), rep, False)
    return rep.items


class RegistrySyncTest(unittest.TestCase):
    """엔진 FX 표 ↔ check_deck FX_KINDS 동기화·예산."""

    def test_draft_registered_in_engine_and_checker(self):
        self.assertIn('draft:2400', MOTION, 'motion.js FX 표에 draft:2400 미등록')
        self.assertIn("'draft'", MOTION, "fxFire 분기에 'draft' 미등록")
        self.assertEqual(FX_KINDS.get('draft'), 2400,
                         'check_deck FX_KINDS draft 예산이 2400 이 아님')

    def test_fx_tables_have_same_names(self):
        table = re.search(r'const FX=\{([^}]+)\}', MOTION).group(1)
        engine = {m.group(1) or m.group(2)
                  for m in re.finditer(r"(?:'([^']+)'|(\w+))\s*:", table)}
        self.assertEqual(engine, set(FX_KINDS),
                         f'엔진↔검사 이름 불일치: {engine ^ set(FX_KINDS)}')

    def test_draft_budget_within_limit(self):
        self.assertLessEqual(FX_KINDS['draft'], 3000, 'draft 예산이 3초 상한 초과')
        for name, ms in FX_KINDS.items():
            with self.subTest(fx=name):
                self.assertLessEqual(ms, 3000, f'{name} 예산 초과')


class AuthoringContractTest(unittest.TestCase):
    """정적 완결·안전 가드의 문서 계약 수준 잠금."""

    def test_static_contract_in_source(self):
        # 캔버스 미생성은 DOM 불변으로만 증명된다 — 코드 수준에서 가드를 잠근다.
        self.assertIn("el._edFx=1;fxFinal(el)", MOTION,
                      'back·정적 경로가 fxFinal 만 호출해야 한다')
        fx_final = MOTION.split('function fxFinal', 1)[1].split('function ', 1)[0]
        self.assertNotIn('draft', fx_final,
                         'fxFinal 은 저작 DOM 만 남겨야 한다(캔버스 생성 금지)')
        body = MOTION.split('function fxDraft', 1)[1].split('function fxFire', 1)[0]
        self.assertIn('staticMode()', body, '도중 정적 전환 가드 필요')
        self.assertIn("aria-hidden", body, '오버레이 캔버스는 장식 — aria-hidden 필수')
        self.assertIn('SecurityError', body, 'getImageData 오염 폴백 주석/처리 필요')
        self.assertIn('fx-draft-degraded', body, '퇴화 sigLog 기록 필요')

    def test_external_src_warns_and_data_uri_does_not(self):
        warns = [it for it in check_items('https://example.com/a.png')
                 if it['sev'] == 'WARN' and it['kind'] == '캔버스' and 'draft' in it['message']]
        self.assertTrue(warns, '외부 http(s) draft 이미지에 캔버스 오염 WARN 이 없다')
        quiet = [it for it in check_items(IMG)
                 if it['sev'] == 'WARN' and it['kind'] == '캔버스' and 'draft' in it['message']]
        self.assertEqual(quiet, [], 'data: URI draft 이미지에 WARN 이 붙었다')

    def test_real_decks_carry_no_draft(self):
        if not REAL_DECK or not Path(REAL_DECK).is_file():
            self.skipTest('EDU_DECK_TEST_DECK 미지정 — 실덱 회귀 검사 생략')
        text = Path(REAL_DECK).read_text(encoding='utf-8')
        # 슬라이드 조각의 실제 속성 사용만 잡는다 — 셸에 내장된 motion.js 의
        # '[data-fx="draft"]' 셀렉터 문자열은 모든 덱이 공유하므로 제외한다.
        self.assertNotRegex(text, r'<[a-zA-Z][^>]*\sdata-fx="draft"',
                            '기존 실덱에 draft 가 있으면 회귀 영향이 생긴다')


class FiringContractTest(unittest.TestCase):
    """브라우저 발화: 오버레이 등장 → 제거 → 저작 이미지."""

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
        return ctx, pg

    def test_overlay_fires_then_settles(self):
        ctx, pg = self._page()
        try:
            pg.wait_for_timeout(500)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 1,
                '장 진입 시 draft 오버레이 캔버스가 없다')
            self.assertEqual(pg.evaluate(
                "document.querySelector('.ed-draft').getAttribute('aria-hidden')"),
                'true')
            pg.wait_for_timeout(2500)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 0,
                '2400ms 안에 오버레이가 제거돼야 한다')
            self.assertIn(pg.evaluate(
                "document.querySelector('[data-fx=\"draft\"]').style.opacity"),
                ('', '1'), '이미지가 최종 모습으로 보여야 한다')
            sigs = [e['sig'] for e in pg.evaluate('window.eduMotion.sigLog')]
            self.assertIn('fx-draft', sigs, 'sigLog 에 fx-draft 없음')
        finally:
            ctx.close()

    def test_reduced_motion_never_creates_canvas(self):
        ctx, pg = self._page(reduced_motion='reduce')
        try:
            pg.wait_for_timeout(1200)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 0,
                '정적 모드에서 캔버스가 생성됐다')
            self.assertIn(pg.evaluate(
                "document.querySelector('[data-fx=\"draft\"]').style.opacity"),
                ('', '1'), '정적 모드에서 이미지가 숨겨졌다')
        finally:
            ctx.close()

    def test_back_revisit_shows_final_only(self):
        ctx, pg = self._page()
        try:
            pg.wait_for_timeout(2700)  # 0번 장 draft 완주
            pg.evaluate('deckGo(1)')
            pg.wait_for_timeout(2700)
            pg.evaluate('deckGo(0)')
            pg.wait_for_timeout(800)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 0,
                '재방문에서 오버레이가 다시 만들어졌다')
            self.assertIn(pg.evaluate(
                "document.querySelector('[data-fx=\"draft\"]').style.opacity"),
                ('', '1'))
            sigs = [e['sig'] for e in pg.evaluate('window.eduMotion.sigLog')]
            self.assertEqual(sigs.count('fx-draft'), 2,
                             '재방문에서 draft 가 재발화했다')
        finally:
            ctx.close()

    def test_tainted_canvas_degrades_to_image(self):
        ctx, pg = self._page()
        try:
            pg.wait_for_timeout(2700)  # 0번 장 draft 는 정상 완주
            # 오염 캔버스 시뮬레이션: getImageData 가 SecurityError 를 던지게 하고
            # 1번 장의 draft 가 발화할 때 폴백 경로를 검증한다.
            pg.evaluate("""()=>{
              CanvasRenderingContext2D.prototype.getImageData = function(){
                throw new DOMException('tainted canvas', 'SecurityError');};
              }""")
            pg.evaluate('deckGo(1)')
            pg.wait_for_timeout(1400)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 0,
                '오염 폴백에서 캔버스가 남았다')
            self.assertIn(pg.evaluate(
                "document.querySelectorAll('[data-fx=\"draft\"]')[1].style.opacity"),
                ('', '1'), '오염 폴백에서 이미지가 보이지 않는다')
            sigs = [e['sig'] for e in pg.evaluate('window.eduMotion.sigLog')]
            self.assertIn('fx-draft-degraded', sigs,
                          'sigLog 에 fx-draft-degraded 없음')
        finally:
            ctx.close()


if __name__ == '__main__':
    unittest.main()
