#!/usr/bin/env python3
"""공통 모션 기법 draft·draft-loop 계약 시험 (TASK-tech-reveal-absorb·TASK-draft-v2).

[목적] data-fx="draft"(이미지 도면 드로잉, 스텝 원샷 2400ms)가
       ① motion.js FX 표 ↔ check_deck FX_KINDS 에 같은 이름·예산(2400≤3000)으로 등록되고
       ② 실제 브라우저에서 aria-hidden 캔버스 오버레이가 발화·2400ms 안에 제거되며
       ③ 정적 모드·뒤로가기 재방문에서는 캔버스 없이 저작 <img> 만 남고
       ④ 오염 캔버스(SecurityError)에서 이미지만 즉시 보이며 'fx-draft-degraded' 를 기록하고
       ⑤ check_deck 이 외부 http(s) src 를 WARN, data: URI 를 무WARN 으로 보고하고
       ⑥ 기존 실덱에 data-fx="draft" 가 없어 회귀 영향이 0임을 잠근다.
       v2 추가 계약(TASK-draft-v2):
       ⑦ 체인 분석(≥1·≤700체인·결정적)·위상 창(시트→체인→치수/헤드→브러시 리빌)의
          캔버스 픽셀 변화·부분 트레이스·헤드 accent 픽셀을 시간 시뮬레이션으로 잠그고
       ⑧ data-fx="draft-loop"(표지 순환 8000+2500)이 주기 재시작·홀드·슬라이드 이탈
          정리·더블클릭 완주 정착·정적/오염 불변·check_deck 3000ms 면제를 지킨다.
[입력] 인코더로 만든 data: URI 흑백/파란 잉크 이미지 미니덱 + 실제 Chromium.
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
from check_deck import FX_KINDS, LOOP_FX, Report, static_checks  # noqa: E402

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


def _test_img_uri(w=96, h=96, ink=(40, 46, 56)):
    """흑백 도형 PNG data: URI — 테두리·대각선·원판으로 소벨 가장자리 확보."""
    px = bytearray(b'\xf7\xf5\xee' * w * h)
    ink = bytes(ink)

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
# 리빌 단계에서 실물 픽셀을 회색 드로잉 선과 구분하기 위한 파란 잉크 변형
BLUE_IMG = _test_img_uri(ink=(30, 60, 150))


def _slide(img_src, fx='draft', notes=NOTES):
    attr = f' data-fx="{fx}"' if fx else ''
    fig = (f'<div style="width:400px"><img src="{img_src}" alt="시험 흑백 도형"'
           f' style="width:100%;display:block"{attr}></div>' if img_src else '')
    return (f'<section class="slide" data-archetype="statement"><div class="pad">'
            f'<h2 class="title">도면 드로잉</h2>{fig}'
            f'<aside class="notes">{notes}</aside></div></section>')


def build_mini(img=IMG, name='deck.html'):
    SRC.mkdir(parents=True, exist_ok=True)
    srcs = []
    slides = (_slide(img), _slide(img), _slide(img, fx='draft-loop'),
              _slide('', fx=None))
    for i, body in enumerate(slides):
        p = SRC / f'{i:02d}-slide.html'
        p.write_text(body, encoding='utf-8')
        srcs.append(p)
    html = OUT / name
    build('fx draft 시험', srcs, [S / 'assets/css'], [S / 'assets/icons'], html)
    return html


def check_items(img_src, fx='draft'):
    """img src 하나를 단 미니 section 을 static_checks 에 태워 보고 항목을 돌려준다."""
    html_text = ('<html><body><div id="stage">' + _slide(img_src, fx=fx)
                 + '</div></body></html>')
    rep = Report()
    static_checks(html_text, BeautifulSoup(html_text, 'html.parser'), rep, False)
    return rep.items


# 시간 시뮬레이션 — rAF 를 큐에 넣고 __step(ms) 으로 프레임을 정확히 진행시킨다.
# __probe 는 오버레이 캔버스의 픽셀을 부류별로 센다.
MOCK_JS = """
window.__t=0;window.__raf=[];
performance.now=()=>window.__t;
window.requestAnimationFrame=cb=>{window.__raf.push(cb);return window.__raf.length;};
window.__step=ms=>{while(ms>0){const d=Math.min(100,ms);ms-=d;window.__t+=d;
  const q=window.__raf;window.__raf=[];for(const cb of q)cb(window.__t);}};
window.__probe=(x,y,w,h)=>{
  const c=document.querySelector('.ed-draft');if(!c)return{dead:1};
  const r=c.getBoundingClientRect(),dpr=(c.width/r.width)||1;
  const d=c.getContext('2d').getImageData(x*dpr,y*dpr,w*dpr,h*dpr).data;
  let a=0,acc=0,blue=0,ink=0;
  for(let i=0;i<d.length;i+=4){const R=d[i],G=d[i+1],B=d[i+2],A=d[i+3];
    if(A>20)a++;
    if(A>120&&R>110&&R-B>45)acc++;
    if(A>120&&B>R+35)blue++;
    if(A>150&&R<120&&G<125&&B<140)ink++;}
  return{a,acc,blue,ink};};
"""
ED_EXPR = "(()=>{const i=document.querySelector('img[data-fx=\"draft\"]');" \
          "return i&&i._edDraft&&i._edDraft.an.chains.length>0})()"
LOOP_ED_EXPR = "(()=>{const i=document.querySelector('img[data-fx=\"draft-loop\"]');" \
               "return i&&i._edDraft&&i._edDraft.an.chains.length>0})()"


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
                if name in LOOP_FX:
                    continue  # 루프 종류는 표지 순환 전용 — 3초 상한 면제(TASK-draft-v2)
                self.assertLessEqual(ms, 3000, f'{name} 예산 초과')

    def test_draft_loop_registered_in_engine_and_checker(self):
        self.assertIn("'draft-loop':8000", MOTION,
                      'motion.js FX 표에 draft-loop:8000 미등록')
        self.assertIn("'draft-loop'", MOTION, "fxFire 분기에 'draft-loop' 미등록")
        self.assertEqual(FX_KINDS.get('draft-loop'), 8000,
                         'check_deck FX_KINDS draft-loop 예산이 8000 이 아님')
        self.assertIn('draft-loop', LOOP_FX, 'LOOP_FX 면제 집합에 draft-loop 없음')


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

    def test_draft_loop_checker_contract(self):
        # 신설 종류 수용 + 표지 순환 전용으로 3000ms 모션 길이 WARN 면제 + 캔버스 WARN 적용
        items = check_items(IMG, fx='draft-loop')
        errors = [it for it in items if it['sev'] == 'ERROR'
                  and it['kind'] in ('data-fx', '모션')]
        self.assertEqual(errors, [],
                         f'유효한 draft-loop 저작에 data-fx/모션 ERROR 발생: {errors}')
        warns = [it for it in items if it['sev'] == 'WARN']
        self.assertFalse([it for it in warns if it['kind'] == '모션 길이'],
                         '루프 종류에 모션 길이 3000ms WARN 이 붙었다')
        self.assertFalse([it for it in warns if it['kind'] == '캔버스'],
                         'data: URI draft-loop 이미지에 캔버스 WARN 이 붙었다')
        ext = check_items('https://example.com/a.png', fx='draft-loop')
        self.assertTrue(
            [it for it in ext if it['sev'] == 'WARN' and it['kind'] == '캔버스'
             and 'draft-loop' in it['message']],
            '외부 http(s) draft-loop 이미지에 캔버스 오염 WARN 이 없다')

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


class DraftV2ContractTest(unittest.TestCase):
    """v2 브라우저 계약 — 체인 분석·위상 창·브러시 리빌·draft-loop 수명주기."""

    @classmethod
    def setUpClass(cls):
        cls.html = build_mini()
        cls.blue = build_mini(img=BLUE_IMG, name='deck-blue.html')
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(channel='chrome')

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()

    def _page(self, deck=None, init=None, **ctx_kw):
        ctx = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080}, **ctx_kw)
        if init:
            ctx.add_init_script(init)
        pg = ctx.new_page()
        pg.goto('file://' + str(deck or self.html))
        return ctx, pg

    def test_chain_analysis_deterministic(self):
        sig = ("(()=>{const a=document.querySelector('img[data-fx=\"draft\"]')"
               "._edDraft.an;return{n:a.chains.length,t:Math.round(a.totalLen),"
               "pk:a.peaks,ci:a.circle?Math.round(a.circle.r):0,"
               "lens:a.chains.map(c=>Math.round(c.len))}})()")
        ctx, pg = self._page()
        try:
            pg.wait_for_function(ED_EXPR, polling=100)
            a = pg.evaluate(sig)
            self.assertGreaterEqual(a['n'], 1, '윤곽 체인이 하나도 없다')
            self.assertLessEqual(a['n'], 700, '체인 상한 700 초과')
            self.assertGreater(a['t'], 0, '체인 총 길이가 0')
            self.assertTrue(all(l > 0 for l in a['lens']),
                            '길이 0 체인이 섞여 있다')
        finally:
            ctx.close()
        ctx, pg = self._page()
        try:
            pg.wait_for_function(ED_EXPR, polling=100)
            self.assertEqual(pg.evaluate(sig), a,
                             '같은 이미지 두 로드에서 분석이 달라졌다(비결정적)')
        finally:
            ctx.close()

    def test_partial_trace_and_plotter_head(self):
        ctx, pg = self._page(init=MOCK_JS)
        try:
            pg.wait_for_function(ED_EXPR, polling=100)
            pg.evaluate('window.__step(500)')     # ~t=517ms — 윤곽 체인 진행 중
            p1 = pg.evaluate('window.__probe(0,0,400,400)')
            self.assertGreater(p1['a'], 0, '시트 단계 캔버스가 비어 있다')
            self.assertGreater(p1['acc'], 0,
                               '치수 전 구간에 accent 픽셀 없음 — 플로터 헤드 의심')
            pg.evaluate('window.__step(700)')     # ~t=1217ms — 체인+치수
            p2 = pg.evaluate('window.__probe(0,0,400,400)')
            self.assertGreater(p2['ink'], p1['ink'],
                               '트레이스가 진행돼도 잉크가 늘지 않는다(부분 트레이스 의심)')
            self.assertGreater(p2['acc'], 0, '치수 단계 accent 픽셀 없음')
            phase = pg.evaluate("document.querySelector('img[data-fx=\"draft\"]')"
                                "._edDraft.phase")
            self.assertIn(phase, ('LINE', 'DIM'), f'위상 순서 이탈: {phase}')
        finally:
            ctx.close()

    def test_brush_mask_reveal_and_completion(self):
        ctx, pg = self._page(deck=self.blue, init=MOCK_JS)
        try:
            pg.wait_for_function(ED_EXPR, polling=100)
            pg.evaluate('window.__step(300)')     # 시트 창 — 실물 픽셀 0
            p0 = pg.evaluate('window.__probe(0,0,400,400)')
            self.assertGreater(p0['a'], 0, '시트 창에 아무것도 안 그려졌다')
            self.assertEqual(p0['blue'], 0, '시트 창에 실물 픽셀이 샜다')
            pg.evaluate('window.__step(1400)')    # ~t=1717ms — 리빌 중반: 부분 노출
            p1 = pg.evaluate('window.__probe(0,0,400,400)')
            self.assertGreater(p1['blue'], 0,
                               '브러시 리빌 중반에 실물(파란 잉크) 픽셀이 없다')
            pg.evaluate('window.__step(350)')     # ~t=2067ms — 리빌 진행
            p2 = pg.evaluate('window.__probe(0,0,400,400)')
            self.assertGreater(p2['blue'], p1['blue'],
                               '리빌 진행에도 노출 영역이 늘지 않는다')
            pg.evaluate('window.__step(500)')     # ~t=2567ms > 2400 — 완료·정리
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 0,
                '2400ms 뒤 오버레이가 남았다')
            self.assertIn(pg.evaluate(
                "document.querySelector('img[data-fx=\"draft\"]').style.opacity"),
                ('', '1'), '완료 뒤 저작 이미지가 보이지 않는다')
        finally:
            ctx.close()

    def test_loop_restart_and_hold(self):
        ctx, pg = self._page(init=MOCK_JS)
        try:
            pg.evaluate('deckGo(2)')
            pg.wait_for_function(LOOP_ED_EXPR, polling=100)
            pg.evaluate('window.__step(8500)')    # 홀드 창(8000~10500)
            self.assertEqual(pg.evaluate(
                "document.querySelector('img[data-fx=\"draft-loop\"]')"
                "._edDraft.phase"), 'DONE', '홀드 창에 DONE 위상이 아니다')
            pg.evaluate('window.__step(2600)')    # 새 주기 진입
            st = pg.evaluate(
                "(()=>{const d=document.querySelector('img[data-fx=\"draft-loop\"]')"
                "._edDraft;return{c:d.cycle,p:d.phase}})()")
            self.assertGreaterEqual(st['c'], 1, '주기 재시작이 감지되지 않는다')
            self.assertIn(st['p'], ('SHEET', 'CONSTRUCT', 'LINE'),
                          f'재시작 직후 위상 이탈: {st["p"]}')
            pg.evaluate('window.__step(10500)')   # 두 번째 주기로 래핑
            self.assertGreaterEqual(pg.evaluate(
                "document.querySelector('img[data-fx=\"draft-loop\"]')"
                "._edDraft.cycle"), 2, '두 번째 순환 주기가 없다')
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft-loop').length"), 1,
                '순환 중 오버레이가 사라졌다')
        finally:
            ctx.close()

    def test_loop_leave_cleanup(self):
        ctx, pg = self._page()
        try:
            pg.evaluate('deckGo(2)')
            pg.wait_for_timeout(900)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft-loop').length"), 1,
                'loop 발화 후 오버레이가 없다')
            pg.evaluate('deckGo(3)')
            pg.wait_for_timeout(300)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 0,
                '슬라이드 이탈 후 오버레이가 남았다')
            self.assertIn(pg.evaluate(
                "document.querySelector('img[data-fx=\"draft-loop\"]')"
                ".style.opacity"), ('', '1'),
                '슬라이드 이탈 후 이미지가 숨겨져 있다')
            sigs = [e['sig'] for e in pg.evaluate('window.eduMotion.sigLog')]
            self.assertIn('fx-draft-loop', sigs, 'sigLog 에 fx-draft-loop 없음')
        finally:
            ctx.close()

    def test_loop_dblclick_settles(self):
        ctx, pg = self._page()
        try:
            pg.evaluate('deckGo(2)')
            pg.wait_for_timeout(900)
            pg.mouse.dblclick(1400, 540)          # 발표 완주 영역 더블클릭
            pg.wait_for_timeout(400)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 0,
                '완주 더블클릭 뒤 오버레이가 남았다')
            self.assertIn(pg.evaluate(
                "document.querySelector('img[data-fx=\"draft-loop\"]')"
                ".style.opacity"), ('', '1'),
                '완주 정착 뒤 이미지가 보이지 않는다')
            pg.wait_for_timeout(3000)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 0,
                '정착 뒤 순환이 다시 시작됐다')
            pg.evaluate('deckGo(3)')
            pg.evaluate('deckGo(2)')
            pg.wait_for_timeout(600)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 0,
                '완주된 장 재방문에서 캔버스가 생겼다')
        finally:
            ctx.close()

    def test_loop_static_modes_never_create_canvas(self):
        for kw in ({'reduced_motion': 'reduce'},):
            ctx, pg = self._page(**kw)
            try:
                pg.evaluate('deckGo(2)')
                pg.wait_for_timeout(1000)
                self.assertEqual(pg.evaluate(
                    "document.querySelectorAll('.ed-draft').length"), 0,
                    f'정적({kw})에서 캔버스가 생성됐다')
            finally:
                ctx.close()
        ctx, pg = self._page()
        try:
            pg.emulate_media(media='print')
            pg.evaluate('deckGo(2)')
            pg.wait_for_timeout(800)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 0,
                'print 에서 캔버스가 생성됐다')
            pg.emulate_media(media='screen')
            pg.evaluate("document.body.classList.add('st-self')")
            pg.evaluate('deckGo(3)')
            pg.evaluate('deckGo(2)')
            pg.wait_for_timeout(800)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 0,
                'self-study 에서 캔버스가 생성됐다')
        finally:
            ctx.close()

    def test_loop_tainted_canvas_degrades_to_image(self):
        ctx, pg = self._page()
        try:
            pg.evaluate("""()=>{
              CanvasRenderingContext2D.prototype.getImageData = function(){
                throw new DOMException('tainted canvas', 'SecurityError');};
              }""")
            pg.evaluate('deckGo(2)')
            pg.wait_for_timeout(1200)
            self.assertEqual(pg.evaluate(
                "document.querySelectorAll('.ed-draft').length"), 0,
                '오염 폴백에서 캔버스가 남았다')
            self.assertIn(pg.evaluate(
                "document.querySelector('img[data-fx=\"draft-loop\"]')"
                ".style.opacity"), ('', '1'),
                '오염 폴백에서 이미지가 보이지 않는다')
            sigs = [e['sig'] for e in pg.evaluate('window.eduMotion.sigLog')]
            self.assertIn('fx-draft-loop-degraded', sigs,
                          'sigLog 에 fx-draft-loop-degraded 없음')
        finally:
            ctx.close()


if __name__ == '__main__':
    unittest.main()
