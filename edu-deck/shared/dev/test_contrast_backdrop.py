#!/usr/bin/env python3
"""대비 배경 해석 회귀 시험: 불투명 카드 우선 + 이미지 배경 픽셀 샘플링.

[목적] TASK-contrast-fix G1~G4. 옛 backdrop() 은 조상 체인을 위에서 내려오며
       backgroundImage 를 만나면 즉시 null 을 돌려줘, 그라데이션 슬라이드 안
       불투명 카드 위의 연한 글자를 검사에서 빼먹었다. 새 해석은 (1) 글자에서 위로
       올라가며 첫 불투명 배경을 쓰고, (2) 글자와 불투명 배경 사이에 이미지·
       그라데이션이 끼면 렌더 픽셀을 샘플링해 최악 대비를 잰다.
[입력] 테스트 안 문자열 픽스처(스니펫에 넣지 않는다).
[출력] 없음(단정문). 실패는 배경 해석 퇴행·샘플링 불능·기존 규칙 붕괴다.
[주의] RENDER_JS 의 SAMPLE 항목(sev='SAMPLE')은 검사기가 요소 영역을 다시 찍어
       재야 하는 요청이다 — 이 테스트는 render_checks 와 같이
       check_deck.measure_img_contrast 로 각 항목을 해소한다.
"""
import sys
import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / 'scripts'))
import build_deck            # noqa: E402
import check_deck            # noqa: E402

NOTE = ('발표자 노트입니다. 화면의 구조와 대비 검사가 어떻게 잡히는지 설명하는 자리로, '
        '실제 수업에서 쓸 발표 내용에 해당하는 충분한 분량의 문장을 둡니다.')
QUIET = check_deck.QUIET_CSS

# 그라데이션 배경 슬라이드(밝은 → 어두운) — 글자는 카드 안/밖 둘로 나눈다
GRAD = 'linear-gradient(135deg, rgb(226,232,236) 0%, rgb(32,43,53) 55%, rgb(24,32,40) 100%)'

LIGHT_TXT = 'color:rgb(196,208,216)'   # 흰 카드 위 대비 ≈1.4 — 미달
DARK_TXT = 'color:rgb(34,44,54)'       # 흰 카드·밝은 그라데이션 위 대비 충분


def slide(body, arch='statement', extra=''):
    return (f'<section class="slide" data-archetype="{arch}" '
            f'style="background-image:{GRAD};position:relative;display:block;padding:128px{extra}">'
            + body + f'<aside class="notes">{NOTE}</aside></section>')


CARD = 'background:rgb(247,248,249);border-radius:16px;padding:40px;width:700px'


def mk_decks():
    """픽스처 → (이름, 표지아키타입, 본문 HTML) 목록."""
    light_card = slide(
        f'<div style="{CARD};position:absolute;left:160px;top:300px">'
        f'<p style="font-size:30px;{LIGHT_TXT}">흰 카드 위의 연한 글자</p></div>')
    dark_card = slide(
        f'<div style="{CARD};position:absolute;left:160px;top:300px">'
        f'<p style="font-size:30px;{DARK_TXT}">흰 카드 위의 진한 글자</p></div>')
    no_card_light = slide(
        f'<p style="position:absolute;left:160px;top:300px;font-size:30px;{LIGHT_TXT}">'
        '그라데이션 위의 연한 글자</p>')
    no_card_dark = slide(
        f'<p style="position:absolute;left:160px;top:300px;font-size:30px;{DARK_TXT}">'
        '그라데이션 밝은 쪽의 진한 글자</p>')
    half_card = (
        '<section class="slide" data-archetype="statement" '
        'style="background:rgb(28,39,51);position:relative;display:block">'
        '<div style="position:absolute;left:160px;top:300px;width:700px;padding:40px;'
        'border-radius:16px;background:rgba(255,255,255,0.6)">'
        '<p style="font-size:30px;color:rgb(150,160,168)">반투명 카드 위 연한 글자</p>'
        f'<aside class="notes">{NOTE}</aside></div></section>')
    dimmed = slide(
        f'<p style="position:absolute;left:160px;top:300px;font-size:30px;opacity:.5;{LIGHT_TXT}">'
        '불투명도 .5 라서 검사 제외</p>'
        '<svg style="position:absolute;left:160px;top:420px" width="400" height="80" viewBox="0 0 400 80">'
        f'<text x="0" y="40" font-size="30" fill="rgb(196,208,216)">SVG 글자는 대비 제외</text></svg>')
    cover_light = slide(
        f'<div style="{CARD};position:absolute;left:160px;top:300px">'
        f'<h1 class="cx-title" style="font-size:60px;{LIGHT_TXT}">표지 안 연한 제목</h1></div>',
        arch='cover', extra=';padding:0')
    return {
        'a_light_card': light_card, 'b_dark_card': dark_card,
        'c_light_nocard': no_card_light, 'c_dark_nocard': no_card_dark,
        'd_half_card': half_card, 'e_exclusions': dimmed,
        'f_cover': cover_light,
    }


class ContrastBackdrop(unittest.TestCase):
    """렌더 패스 — 슬라이드별 픽스처 덱을 만들고 SAMPLE 해소까지 수행한다."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='edu-contrast-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.out = Path(cls.tmp.name)
        cls.pw = sync_playwright().start()
        cls.addClassCleanup(cls.pw.stop)
        cls.browser = check_deck.launch(cls.pw)
        cls.addClassCleanup(cls.browser.close)
        cls.decks = {}
        tail = ('<section class="slide" data-archetype="closing"><h1>마무리</h1>'
                f'<aside class="notes">{NOTE}</aside></section>')
        for name, first in mk_decks().items():
            d = cls.out / name
            (d / 'src').mkdir(parents=True)
            (d / 'deck.json').write_text('{"title":"대비 시험","output":"result.html"}', encoding='utf-8')
            (d / 'src' / '01.html').write_text(first, encoding='utf-8')
            (d / 'src' / '02.html').write_text(tail, encoding='utf-8')
            build_deck.build('대비 시험', sorted((d / 'src').glob('*.html')),
                             [SHARED / 'assets' / 'css'], [SHARED / 'assets' / 'icons'], d / 'result.html')
            cls.decks[name] = d / 'result.html'

    def page(self):
        ctx = self.browser.new_context(viewport={'width': 1920, 'height': 1080},
                                       reduced_motion='reduce')
        self.addCleanup(ctx.close)
        return ctx.new_page()

    def contrast_errors(self, name, slide=0):
        """render_checks 와 같은 순서: RENDER_JS 항목 + SAMPLE 픽셀 샘플링 해소."""
        p = self.page()
        p.goto(self.decks[name].as_uri())
        p.add_style_tag(content=QUIET)
        p.evaluate(check_deck.DECKINFO_POLYFILL)
        items = []
        info = p.evaluate('window.deckInfo()')
        top = int(info.get('maxStep') or 0)
        for s in range(top + 1):
            p.evaluate(f'window.deckGo({slide}, {s})')
            for f in p.evaluate(check_deck.RENDER_JS, [slide]):
                if f['sev'] == 'SAMPLE':
                    ratio = check_deck.measure_img_contrast(p, slide, f)
                    if ratio is not None and ratio < f['need']:
                        items.append({'sev': 'ERROR', 'kind': '대비',
                                      'msg': f"{f['target']} 대비 {ratio:.2f} (기준 {f['need']})",
                                      'target': f['target']})
                    continue
                items.append(f)
        return [i for i in items if i['sev'] == 'ERROR' and i['kind'] == '대비']

    # (a) 그라데이션 슬라이드 + 불투명 흰 카드 + 연한 글자 → 카드가 배경 → ERROR
    def test_opaque_card_light_text_errors(self):
        errs = self.contrast_errors('a_light_card')
        self.assertTrue(errs, '불투명 카드 위 연한 글자가 잡히지 않음(구멍 재현)')

    # (b) 같은 구조 + 충분히 진한 글자 → ERROR 없음
    def test_opaque_card_dark_text_passes(self):
        self.assertEqual(self.contrast_errors('b_dark_card'), [])

    # (c) 투명 카드(없음): 그라데이션 위 연한 글자 → 샘플링 ERROR, 진한 글자 → 없음
    def test_gradient_light_text_sampled_error(self):
        self.assertTrue(self.contrast_errors('c_light_nocard'),
                        '그라데이션 위 연한 글자를 픽셀 샘플링으로 못 잡음')

    def test_gradient_dark_text_sampled_pass(self):
        self.assertEqual(self.contrast_errors('c_dark_nocard'), [])

    # (d) 반투명 카드(alpha .6) 위 연한 글자 → 합성(렌더) 배경으로 판정 → ERROR
    def test_half_transparent_card_errors(self):
        self.assertTrue(self.contrast_errors('d_half_card'))

    # (e) 기존 제외 규칙 유지: 불투명도 0.6 미만 글자·SVG 글자는 대비 검사 대상이 아님
    def test_existing_exclusions_kept(self):
        self.assertEqual(self.contrast_errors('e_exclusions'), [])

    # (f) 표지(cover) 안 글자도 같은 규칙 — 카드 위 연한 제목 → ERROR
    def test_cover_text_same_rule(self):
        self.assertTrue(self.contrast_errors('f_cover'))


if __name__ == '__main__':
    unittest.main()
