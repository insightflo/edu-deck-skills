#!/usr/bin/env python3
"""직접 설계 표지(custom) 회귀 시험: 면제 좁힘·계약·data-variant 수용·모션 안전.

[목적] TASK-cover-custom G1·G3·G4·G6. 표지 화면 면제를 '글자 없는 장식'으로 좁혔으므로
       (a) 계약을 지킨 직접 설계 표지는 ERROR 0, (b) 슬라이드 밖 제목은 ERROR,
       (c) 16px 글자는 ERROR, (d) aria-hidden 장식은 면제 유지, (e) 카탈로그 7종은
       새 규칙에서도 ERROR 0, (f) custom/custom-* 수용, (g) 콘솔 오류 0.
[입력] 테스트 안 문자열 픽스처(snippets 에 넣지 않는다) + 카탈로그 01-cover*.html.
[출력] 없음(단정문). 실패는 면제 범위 퇴행·계약 위반·모션 깨짐이다.
[주의] RENDER_JS 는 움직임 줄임 + QUIET_CSS(전환 0초)에서 잰다 — check_deck.render_checks
       와 같은 조건. 콘솔 오류는 움직임 켠 상태에서 모은다(같은 1차 패스).
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / 'scripts'))
import build_deck            # noqa: E402
import check_deck            # noqa: E402
import tone_router           # noqa: E402

SNIPPETS = SHARED / 'assets' / 'snippets'
NOTE = ('발표자 노트입니다. 표지를 보여 주며 오늘 교육의 목적과 대상을 소개하고, '
        '화면의 제목과 핵심어를 짚은 뒤 다음 장의 순서 안내로 자연스럽게 이어갑니다.')
QUIET = check_deck.QUIET_CSS

COVER_OK = f'''<section class="slide cx" data-archetype="cover" data-variant="custom" id="cover"
    style="position:relative;overflow:hidden">
  <p class="cx-eyebrow" style="position:absolute;left:160px;top:220px;font-size:26px;color:var(--accent-light)">우리 회사</p>
  <h1 class="cx-title" style="position:absolute;left:160px;top:320px;width:1100px;font-size:96px;line-height:1.2;color:var(--ink)">직접 설계 표지</h1>
  <p class="cx-tokens" style="position:absolute;left:160px;top:560px;font-size:32px;color:var(--soft)"><span>핵심 하나</span> · <span>핵심 둘</span></p>
  <p style="position:absolute;left:160px;top:640px;font-size:24px;color:var(--muted)">부제 한 문장을 적는 자리입니다</p>
  <div aria-hidden="true" style="position:absolute;right:-120px;top:120px;width:520px;height:520px;border-radius:50%;background:var(--accent-light);opacity:.18"></div>
  <div aria-hidden="true" style="position:absolute;right:140px;top:280px;width:240px;height:240px;border-radius:var(--r3);background:var(--accent)"></div>
  <p style="position:absolute;left:160px;bottom:120px;font-size:22px;color:var(--muted)">2026. 03. 10</p>
  <aside class="notes">{NOTE}</aside>
</section>'''

COVER_OVERFLOW = COVER_OK.replace(
    'class="cx-title" style="position:absolute;left:160px;top:320px;width:1100px;font-size:96px;line-height:1.2',
    'class="cx-title" style="position:absolute;left:1500px;top:320px;white-space:nowrap;font-size:96px;line-height:1.2')

COVER_TINY = COVER_OK.replace(
    '<p style="position:absolute;left:160px;top:640px;font-size:24px;color:var(--muted)">',
    '<p style="position:absolute;left:160px;top:640px;font-size:16px;color:var(--muted)">')

COVER_HEX = COVER_OK.replace(
    'class="cx-eyebrow" style="position:absolute;left:160px;top:220px;font-size:26px;color:var(--accent-light)"',
    'class="cx-eyebrow" style="position:absolute;left:160px;top:220px;font-size:26px;color:#e8843c"')

COVER_NO_TITLE = COVER_OK.replace('class="cx-title"', 'class="cx-head"')

SLIDE = '<section class="slide" data-archetype="{a}"><h1>{t}</h1><aside class="notes">' + NOTE + '</aside></section>'
AGENDA = SLIDE.format(a='agenda', t='오늘의 순서')
CLOSING = SLIDE.format(a='closing', t='마무리')


def doc(slides):
    return ('<html><head><title>교육</title></head><body><div id="stage">'
            + ''.join(slides) + '</div></body></html>')


def static_items(text):
    rep = check_deck.Report()
    check_deck.static_checks(text, BeautifulSoup(text, 'html.parser'), rep, False)
    return rep.items


class CoverCustomRender(unittest.TestCase):
    """브라우저 렌더 검사 — 한 브라우저를 공유하고 장마다 RENDER_JS 를 평가한다."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='edu-cover-custom-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.out = Path(cls.tmp.name)
        cls.pw = sync_playwright().start()
        cls.addClassCleanup(cls.pw.stop)
        cls.browser = check_deck.launch(cls.pw)
        cls.addClassCleanup(cls.browser.close)
        cls.decks = {}
        for name, cover in (
            ('ok', COVER_OK), ('overflow', COVER_OVERFLOW), ('tiny', COVER_TINY),
            ('hex', COVER_HEX), ('notitle', COVER_NO_TITLE),
        ):
            cls.decks[name] = cls.write_deck(name, [cover, AGENDA, CLOSING])
        cls.decks['customx'] = cls.write_deck(
            'customx', [COVER_OK.replace('data-variant="custom"', 'data-variant="custom-grid"'),
                        AGENDA, CLOSING])

    @classmethod
    def write_deck(cls, name, slides):
        d = cls.out / name
        (d / 'src').mkdir(parents=True)
        (d / 'deck.json').write_text('{"title":"표지 시험","output":"result.html"}', encoding='utf-8')
        for i, s in enumerate(slides, 1):
            (d / 'src' / f'{i:02d}.html').write_text(s, encoding='utf-8')
        build_deck.build('표지 시험', sorted((d / 'src').glob('*.html')),
                         [SHARED / 'assets' / 'css'], [SHARED / 'assets' / 'icons'], d / 'result.html')
        return d / 'result.html'

    def page(self, reduced=True):
        ctx = self.browser.new_context(viewport={'width': 1920, 'height': 1080},
                                       reduced_motion='reduce' if reduced else 'no-preference')
        self.addCleanup(ctx.close)
        return ctx.new_page()

    def render_items(self, path, slide=0):
        """check_deck.render_checks 의 2차 패스와 같은 조건에서 RENDER_JS 를 평가한다."""
        p = self.page()
        p.goto(path.as_uri())
        p.add_style_tag(content=QUIET)
        top = p.evaluate('window.deckInfo().maxStep') or 0
        items = []
        for s in range(int(top) + 1):
            p.evaluate(f'window.deckGo({slide}, {s})')
            items += p.evaluate(check_deck.RENDER_JS, [slide])
        return items

    def errors(self, items):
        return [i for i in items if i['sev'] == 'ERROR']

    # (a) 계약을 지킨 직접 설계 표지 → ERROR 0
    def test_contract_valid_cover_passes(self):
        self.assertEqual(self.errors(self.render_items(self.decks['ok'])), [])

    # (b) 제목이 슬라이드 오른쪽으로 넘치는 표지 → 화면 밖 넘침 ERROR
    def test_overflowing_title_is_error(self):
        items = self.errors(self.render_items(self.decks['overflow']))
        self.assertTrue(any(i['kind'] == '화면 밖 넘침' and 'cx-title' in i['target'] for i in items), items)

    # (c) 16px 글자 표지 → 글자 크기 ERROR
    def test_tiny_text_is_error(self):
        items = self.errors(self.render_items(self.decks['tiny']))
        self.assertTrue(any(i['kind'] == '글자 크기' and '18px 미만' in i['msg'] for i in items), items)

    # (d) 캔버스 밖 aria-hidden 장식 → 면제 유지(ERROR 없음)
    def test_aria_hidden_decoration_offscreen_allowed(self):
        items = self.errors(self.render_items(self.decks['ok']))
        self.assertFalse([i for i in items if i['kind'] == '화면 밖 넘침'], items)

    # (e) 카탈로그 7종이 새 규칙에서도 ERROR 0 — 자리표시는 실덱처럼 짧은 문구로 채운다
    def test_catalog_covers_pass_new_rule(self):
        fills = {
            '«교육 이름 ≤10자»': '우리 회사', '«표지 제목 ≤12자»': '핵심 제목',
            '«부제 한 문장 ≤29자»': '오늘 배울 것을 한 문장으로',
            '«날짜 YYYY. MM. DD ≤15자»': '2026. 03. 10', '«표지 배지(선택) ≤27자»': '3월 정기 교육',
            '«핵심어 ≤4자»': '핵심', '«핵심어 ≤5자»': '핵심어',
        }
        for f in sorted(SNIPPETS.glob('01-cover*.html')):
            with self.subTest(cover=f.name):
                text = f.read_text(encoding='utf-8')
                for k, v in fills.items():
                    text = text.replace(k, v)
                text = re.sub(r'«[^»]*»', '핵심', text)
                deck = self.write_deck('cat-' + f.stem, [text, AGENDA, CLOSING])
                self.assertEqual(self.errors(self.render_items(deck)), [], f.name)

    # (f) data-variant="custom"·"custom-*" 가 빌드·검사에서 수용된다
    def test_custom_variant_accepted(self):
        for name in ('ok', 'customx'):
            with self.subTest(deck=name):
                text = self.decks[name].read_text(encoding='utf-8')
                bad = [i for i in static_items(text)
                       if i['sev'] == 'ERROR']
                self.assertEqual(bad, [])
                warns = [i for i in static_items(text)
                         if i['kind'] == '표지']
                self.assertEqual(warns, [])
        self.assertNotIn('custom', tone_router.COVERS)
        self.assertEqual(tone_router.COVER_CUSTOM, 'custom')

    # 계약 위반: 하드코딩 hex 색 → WARN (직접 설계 표지만. 카탈로그에는 적용 안 함)
    def test_hardcoded_hex_warns(self):
        text = self.decks['hex'].read_text(encoding='utf-8')
        warns = [i for i in static_items(text) if i['kind'] == '표지' and 'var(--' in i['message']]
        self.assertTrue(warns)
        cat = (SNIPPETS / '01-cover.html').read_text(encoding='utf-8')
        self.assertEqual([i for i in static_items(doc([cat, AGENDA, CLOSING])) if i['kind'] == '표지'], [])

    # 계약 위반: .cx-title 없는 직접 설계 표지 → WARN
    def test_missing_cx_title_warns(self):
        text = self.decks['notitle'].read_text(encoding='utf-8')
        warns = [i for i in static_items(text) if i['kind'] == '표지' and 'cx-title' in i['message']]
        self.assertTrue(warns)

    # (g) .cx-title 만 있는 표지에서 모션 진입·장 전환 시 콘솔 오류 0 (움직임 켠 1차 패스)
    def test_motion_no_console_errors(self):
        errors = []
        p = self.page(reduced=False)
        p.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        p.on('pageerror', lambda e: errors.append(str(e)))
        p.goto(self.decks['ok'].as_uri())
        p.wait_for_timeout(400)
        n = p.evaluate('window.deckInfo().count')
        for i in range(n):
            p.evaluate(f'window.deckGo({i})')
            p.wait_for_timeout(120)
        p.evaluate('window.deckGo(0)')
        p.wait_for_timeout(200)
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
