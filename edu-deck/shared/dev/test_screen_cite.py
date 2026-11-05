"""P1-2 실물 화면 인용 계약: 조각 32 의 구조·정적 검사·렌더·출처 연결·이미지 예산을 검증한다.

계약(지시문 v3 P1-2):
  (a) 정적: .screen-cite 그림에 이미지가 없으면(빈 프레임) ERROR. 이미지는 base64 data: URI 여야 하고
      alt 는 화면의 요지를 말해야 한다(빈 alt·자리표시 ERROR).
  (b) 캡션 3요소(출처 .sc-src[data-src="Fxx"] · 조회일 .sc-date · 「이 화면이 증명하는 것」 요지 .sc-gist)
      중 어느 하나라도 없으면 ERROR.
  (c) 예산: 이미지 1장 ≤700KB 권장(초과 WARN), 덱 라스터 합계 1.5MB 이내(기존 규칙 — 초과 ERROR).
  (d) 조각 32-screen-cite.html 은 사용자 제공 이미지 전제의 호스트 컴포넌트다: 기본은 mapping 호스트,
      비교 변형(screens)은 compare-2 호스트. 신규 시그니처는 없다(지시문 P1-2 적용 파일에 motion.js 가 없다).
  (e) 렌더: 실물 화면 슬라이드에서 넘침 0 · 호스트의 기존 레시피가 발화한다(sigLog ≥1).
  (f) 출처: .sc-src data-src 는 verify_sources 인용 체계로 검증된다(research.md 에 없는 id ERROR ·
      참고 자료 등록 누락 ERROR). 캡션의 조회일은 「근거 없는 수치」 경고에서 제외된다.
"""
import sys
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build
from check_deck import RENDER_JS, Report, launch, static_checks
import os, tempfile
_TEST_OUT = Path(os.environ.get('EDU_DECK_TEST_OUT', str(Path(tempfile.gettempdir()) / 'edu-deck-dev-tests')))

OUT = _TEST_OUT / 'screen-cite'

# 로컬에서 프로그램 생성한 합성 PNG(웹 캡처 아님 — P1-2 픽스처 원칙). 24×14 막대 패턴 97B.
TINY_PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAOCAIAAAC6mkspAAAAK"
            "ElEQVR42mPQz99AFcQw+Az6//cHEL0o10NGpAoC0ahBowZRAw0+gwAvpcFnqKiKMwAAAABJRU5ErkJggg==")
NOTE = ('<aside class="notes">이 장에서는 실물 화면을 근거로 설명합니다. 화면의 어느 부분을 볼지 먼저 안내하고 '
        '캡션의 출처와 조회일을 짚어 줍니다. 화살표를 누르면 읽을 포인트가 차례로 나타납니다. '
        '화면에 없는 보충 사실은 말로만 전합니다. 끝나면 다음 장으로 넘어갑니다.</aside>')

GIST = '이 화면이 증명하는 것'
SC_SRC = '<span class="sc-src" data-src="F01"><b>example.go.kr</b>, 「안전점검 대시보드」</span>'


def cite_figure(img='', alt='대시보드에 점검 항목 완료 표시가 보이는 화면', src=TINY_PNG):
    """이미지 마크업만 갈아 끼우는 .screen-cite 그림. img=None 이면 빈 프레임, 문자열이면 그 태그를 그대로 쓴다."""
    if img is None:
        shot = ''
    elif img:
        shot = img
    else:
        shot = f'<img class="b-shot" src="{src}" alt="{alt}">'
    return ('<figure class="screen-cite f3">'
            '<div class="b-chrome"><span class="b-dots"><i></i><i></i><i></i></span>'
            '<span class="b-url">https://example.go.kr/dashboard</span></div>'
            f'<div class="b-view">{shot}</div>'
            '<figcaption class="sc-cap">'
            f'<p class="sc-line">{SC_SRC}<span class="sc-date">조회일 2026-11-03</span></p>'
            f'<p class="sc-gist"><b>{GIST}</b> — 점검 항목 전체가 완료 상태로 기록됩니다</p>'
            '</figcaption></figure>')


def cite_slide(figure=None):
    """mapping 호스트 안 실물 화면 인용 시험 슬라이드."""
    return ('<section class="slide" data-archetype="mapping" style="gap:32px">'
            '<div class="head"><p class="eyebrow">시험</p><h2 class="title">실물 화면으로 확인합니다</h2></div>'
            '<div class="row" style="flex:1;min-height:0">'
            f'{figure if figure is not None else cite_figure()}'
            '<div class="col f2" style="gap:16px">'
            '<div class="card" data-step="1" style="padding:24px 32px;gap:0"><p class="label"><span class="mk">1</span> 볼 곳</p>'
            '<h3 style="font-size:34px">완료 표시</h3><p class="small">목록의 상태 칸을 봅니다</p></div>'
            '<div class="card" data-step="2" style="padding:24px 32px;gap:0"><p class="label" style="color:var(--blue)">'
            '<span class="mk" style="background:var(--blue)">2</span> 읽을 값</p>'
            '<h3 style="font-size:34px">조회일</h3><p class="small">캡션의 조회일과 맞춥니다</p></div>'
            '</div></div>' + NOTE + '</section>')


SOURCES = ('<section class="slide" data-archetype="sources"><div class="head"><p class="eyebrow">참고 자료</p>'
           '<h2 class="title">실물 화면의 근거</h2></div><ul class="src-list">'
           '<li data-src="F01"><span class="sid">F01</span><span><b>example.go.kr</b>, 「안전점검 대시보드」, 2026-11-03 — demo-screen.png</span></li>'
           '</ul>' + NOTE + '</section>')


def run_static(slides, allow_placeholders=False):
    html = ('<html><head><title>시험 덱</title></head><body><div id="stage">' + "\n".join(slides) + '</div></body></html>')
    # TASK-free-mode: 취향 규칙의 기존 심각도(WARN)를 검증하려면 --style 모드 리포트가 필요하다
    rep = Report(style=True)
    static_checks(html, _soup(html), rep, allow_placeholders=allow_placeholders)
    return rep


def _soup(html):
    from bs4 import BeautifulSoup
    try:
        import lxml  # noqa: F401
        return BeautifulSoup(html, 'lxml')
    except ImportError:
        return BeautifulSoup(html, 'html.parser')


def findings(rep, kind):
    return [it for it in rep.items if it['kind'] == kind]


def payload_url(chars):
    """예산 시험용 data URL — 페이로드 길이만 조절한다(디코딩 크기 = 약 3/4)."""
    return "data:image/png;base64," + "A" * chars


class StaticScreenCiteTest(unittest.TestCase):
    """(a)(b)(c) 빈 프레임·alt·캡션 3요소·예산의 정적 계약."""

    def test_empty_frame_without_image_is_error(self):
        rep = run_static([cite_slide(figure=cite_figure(img=None)), SOURCES])
        errs = findings(rep, '실물 화면')
        self.assertTrue(errs, rep.lines())
        self.assertEqual(errs[0]['sev'], 'ERROR')
        self.assertIn('빈 프레임', errs[0]['message'])
        self.assertEqual(rep.count('ERROR'), 1, rep.lines())

    def test_img_without_src_is_empty_frame_error(self):
        broken = cite_figure(img='<img class="b-shot" alt="화면 요지">')
        rep = run_static([cite_slide(figure=broken), SOURCES])
        errs = [it for it in findings(rep, '실물 화면') if '빈 프레임' not in it['message']]
        self.assertTrue(errs, rep.lines())

    def test_external_or_file_src_is_error(self):
        for src in ('screen.png', 'images/shot.jpg'):
            rep = run_static([cite_slide(figure=cite_figure(src=src)), SOURCES])
            errs = [it for it in findings(rep, '실물 화면') if 'data:' in it['message'] or 'base64' in it['message']]
            self.assertTrue(errs, f'src={src}: ' + "\n".join(rep.lines()))

    def test_missing_or_placeholder_alt_is_error(self):
        for alt in ('', '«이 화면의 요지 한 줄 ≤40자»'):
            fig = cite_figure(img='', alt=alt) if alt == '' else cite_figure(alt=alt)
            rep = run_static([cite_slide(figure=fig), SOURCES])
            errs = [it for it in findings(rep, '실물 화면') if 'alt' in it['message']]
            self.assertTrue(errs, f'alt={alt[:16]}…: ' + "\n".join(rep.lines()))
            self.assertEqual(errs[0]['sev'], 'ERROR')

    def test_caption_three_parts_required(self):
        for cls, what in (('.sc-src', '출처'), ('.sc-date', '조회일'), ('.sc-gist', '요지')):
            fig = cite_figure().replace(f'<p class="sc-line">', f'<p class="sc-line sc-broken" data-missing="{cls[1:]}">')
            # 요소 자체를 지운다: sc-line 에서 해당 자손 제거
            import re as _re
            fig = _re.sub(rf'<span class="{cls[1:]}"[^>]*>.*?</span>', '', fig) if cls != '.sc-gist' \
                else _re.sub(rf'<p class="sc-gist">.*?</p>', '', fig, flags=_re.S)
            rep = run_static([cite_slide(figure=fig), SOURCES])
            errs = [it for it in findings(rep, '실물 화면') if what in it['message'] and '캡션' in it['message']]
            self.assertTrue(errs, f'{cls} 제거: ' + "\n".join(rep.lines()))
            self.assertEqual(errs[0]['sev'], 'ERROR')

    def test_missing_data_src_is_error(self):
        import re as _re
        fig = _re.sub(r' data-src="F01"', '', cite_figure())
        rep = run_static([cite_slide(figure=fig), SOURCES])
        errs = [it for it in findings(rep, '실물 화면') if 'data-src' in it['message']]
        self.assertTrue(errs, rep.lines())
        self.assertEqual(errs[0]['sev'], 'ERROR')

    def test_bad_data_src_format_is_error(self):
        fig = cite_figure().replace('data-src="F01"', 'data-src="대시보드"')
        rep = run_static([cite_slide(figure=fig), SOURCES])
        errs = [it for it in findings(rep, '실물 화면') if 'Fxx' in it['message']]
        self.assertTrue(errs, rep.lines())

    def test_good_cite_has_no_cite_findings(self):
        rep = run_static([cite_slide(), SOURCES])
        self.assertEqual(findings(rep, '실물 화면'), [], rep.lines())
        self.assertEqual(rep.count('ERROR'), 0, rep.lines())

    def test_placeholder_snippet_passes_in_gallery_mode(self):
        """갤러리 검사(--allow-placeholders)에서는 자리표시 src·alt 를 허용한다."""
        ph = cite_figure(src='«사용자가 제공한 화면 이미지(data:image/…;base64,…)»',
                         alt='«이 화면의 요지 한 줄 ≤40자»')
        rep = run_static([cite_slide(figure=ph), SOURCES], allow_placeholders=True)
        self.assertEqual([it for it in findings(rep, '실물 화면') if '빈 프레임' in it['message']], [], rep.lines())
        self.assertEqual([it for it in findings(rep, '실물 화면') if 'alt' in it['message']], [], rep.lines())

    def test_image_over_700kb_warns_but_total_under_budget(self):
        big = payload_url(960_000)  # 디코딩 ≈ 720,000B > 700KB(716,800B), 합계는 1.5MB 안
        rep = run_static([cite_slide(figure=cite_figure(src=big)), SOURCES])
        warns = [it for it in findings(rep, '실물 화면') if it['sev'] == 'WARN' and '700KB' in it['message']]
        self.assertTrue(warns, rep.lines())
        self.assertEqual(rep.count('ERROR'), 0, rep.lines())
        self.assertEqual(findings(rep, '라스터 예산'), [])

    def test_deck_raster_total_over_1_5mb_is_error(self):
        huge = payload_url(2_400_000)  # 디코딩 ≈ 1,800,000B > 1.5MB(1,572,864B)
        rep = run_static([cite_slide(figure=cite_figure(src=huge)), SOURCES])
        errs = findings(rep, '라스터 예산')
        self.assertTrue(errs, rep.lines())
        self.assertEqual(errs[0]['sev'], 'ERROR')
        self.assertIn('1.5MB', errs[0]['message'])


class SnippetMarkupTest(unittest.TestCase):
    """(d) 조각 32 파일의 구조 계약 — 호스트 아키타입 안 컴포넌트."""

    @classmethod
    def setUpClass(cls):
        import re
        cls.text = (S / 'assets/snippets/32-screen-cite.html').read_text(encoding='utf-8')
        cls.body = re.sub(r'<!--.*?-->', '', cls.text, flags=re.S)
        cls.soup = _soup('<html><body><div id="stage">' + cls.body + '</div></body></html>')
        cls.sections = cls.soup.select('section.slide')

    def test_two_host_sections(self):
        archs = [(s.get('data-archetype'), s.get('data-variant')) for s in self.sections]
        self.assertIn(('mapping', None), archs)
        self.assertIn(('compare-2', 'screens'), archs)

    def test_every_figure_has_full_placeholder_contract(self):
        figs = self.soup.select('.screen-cite')
        self.assertGreaterEqual(len(figs), 3)  # 기본 1 + 비교 2
        for fig in figs:
            img = fig.select_one('img.b-shot')
            self.assertIsNotNone(img, '이미지 없는 빈 조각이면 안 된다')
            self.assertIn('사용자가 제공한', img.get('src', ''))
            self.assertRegex(img.get('alt', ''), r'^«이 화면의 요지')
            self.assertRegex(fig.select_one('.sc-src').get('data-src', ''), r'^«F\d{2,3}»$')
            for cls in ('.sc-src', '.sc-date', '.sc-gist'):
                el = fig.select_one(cls)
                self.assertIsNotNone(el, f'{cls} 필요')
                self.assertTrue(el.get_text(strip=True))

    def test_user_image_rule_is_documented(self):
        self.assertIn('사용자가 제공한', self.text)
        self.assertIn('캡처', self.text)  # 웹 캡처 금지 문구
        self.assertIn('빈', self.text)    # 빈 프레임 금지 문구


RESEARCH = """# 조사 기록: 실물 화면 인용 단위 시험
기준일: 2026-11-03 · 청중: 단위 시험

## F01
- 주장: 안전점검 대시보드 화면에 점검 항목 완료 표시가 기록된다.
- 값: 안전점검 대시보드
- 원문: "안전점검 대시보드 — 점검 항목 전체 완료"
- 출처: example.go.kr, 「안전점검 대시보드」
- 발행일: 2026-11-01
- 자료: research/raw/demo-screen.png
- 확인: 원문대조
- 대조: 2026-11-03 로컬 생성 합성 PNG 원본과 대조(웹 캡처 아님 — P1-2 픽스처 원칙)
"""


class VerifySourcesScreenCiteTest(unittest.TestCase):
    """(f) .screen-cite .sc-src data-src ↔ research.md·참고 자료 연결."""

    @classmethod
    def setUpClass(cls):
        import verify_sources as vs
        cls.vs = vs
        cls.dir = OUT / 'refs'
        cls.dir.mkdir(parents=True, exist_ok=True)
        (cls.dir / 'research.md').write_text(RESEARCH, encoding='utf-8')
        # 자료 파일도 로컬 생성 합성 PNG(웹 캡처 아님 — P1-2 픽스처 원칙). research.md 자료: 항목이 가리킨다.
        import base64
        raw_dir = cls.dir / 'research' / 'raw'
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / 'demo-screen.png').write_bytes(base64.b64decode(TINY_PNG.split(',', 1)[1]))
        html = ('<html><head><title>시험 덱</title></head><body><div id="stage">'
                + cite_slide() + SOURCES + '</div></body></html>')
        (cls.dir / 'deck.html').write_text(html, encoding='utf-8')

    def test_cite_ids_resolve_and_list(self):
        out = self.vs.Out()
        facts = self.vs.parse_research(self.dir / 'research.md', out)
        cited = self.vs.check_html(self.dir / 'deck.html', facts, out)
        self.assertEqual(cited, {'F01'})
        self.assertEqual(out.count('ERROR'), 0, out.rows)

    def test_unknown_cite_id_is_error(self):
        import re as _re
        bad = _re.sub(r'data-src="F01"', 'data-src="F99"', cite_slide())
        (self.dir / 'deck.html').write_text(
            '<html><head><title>시험 덱</title></head><body><div id="stage">' + bad + SOURCES + '</div></body></html>',
            encoding='utf-8')
        out = self.vs.Out()
        facts = self.vs.parse_research(self.dir / 'research.md', out)
        self.vs.check_html(self.dir / 'deck.html', facts, out)
        errs = [msg for sev, _, msg in out.rows if sev == 'ERROR' and 'F99' in msg]
        self.assertTrue(errs, out.rows)

    def test_caption_lookup_date_is_not_a_loose_number(self):
        """캡션의 조회일 날짜는 data-src 로 뒷받침되므로 「출처 칩 없는 수치」 경고를 내지 않는다."""
        out = self.vs.Out()
        facts = self.vs.parse_research(self.dir / 'research.md', out)
        self.vs.check_html(self.dir / 'deck.html', facts, out)
        loose = [msg for sev, _, msg in out.rows if '출처 칩 없는 수치' in msg]
        self.assertEqual(loose, [], out.rows)


class RenderScreenCiteTest(unittest.TestCase):
    """(e) 호스트 레시피 발화·넘침 0 의 렌더 계약(Playwright)."""

    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True, exist_ok=True)
        cover = ('<section class="slide cx" data-archetype="cover" id="cover" style="padding:0">'
                 '<div aria-hidden="true" class="cx-blob cx-b1"></div>'
                 '<div class="cx-text" style="top:200px;position:absolute"><p class="cx-eyebrow">실물 화면 교육</p>'
                 '<h1 class="cx-title" style="font-size:104px">실물 화면으로 가르칩니다</h1>'
                 '<p class="cx-sub">제공받은 화면을 근거로 설명하는 방법을 익힙니다</p></div>'
                 '<p class="cover-date" style="z-index:3">2026. 11. 03</p>' + NOTE + '</section>')
        agenda = ('<section class="slide" data-archetype="agenda" style="gap:32px">'
                  '<div class="head"><p class="eyebrow">순서</p><h2 class="title">오늘 순서</h2></div>'
                  '<p class="body">실물 화면 인용과 비교 방법을 배웁니다.</p>' + NOTE + '</section>')
        compare = ('<section class="slide" data-archetype="compare-2" data-variant="screens" style="gap:32px">'
                   '<div class="head"><p class="eyebrow">시험</p><h2 class="title">두 화면을 비교합니다</h2></div>'
                   '<div class="row" style="flex:1;min-height:0">'
                   f'<figure class="card screen-cite f1" data-step="1" style="padding:24px">{cite_figure()}</figure>'
                   f'<figure class="card screen-cite f1" data-step="2" style="padding:24px">{cite_figure()}</figure>'
                   '</div><div class="callout" data-step="3">같은 화면을 조건을 바꿔 다시 봅니다</div>'
                   + NOTE + '</section>')
        closing = ('<section class="slide dark center" data-archetype="closing"><div class="bar"></div>'
                   '<h2 class="big">실물 화면으로 증명합니다</h2>' + NOTE + '</section>')
        src = OUT / 'src'
        src.mkdir(parents=True, exist_ok=True)
        for name, html in [('01-cover.html', cover), ('02-agenda.html', agenda),
                           ('03-cite.html', cite_slide()), ('04-compare.html', compare),
                           ('05-sources.html', SOURCES), ('06-closing.html', closing)]:
            (src / name).write_text(html + '\n', encoding='utf-8')
        build('screen cite contracts', sorted(src.glob('*.html')),
              [S / 'assets/css'], [S / 'assets/icons'], OUT / 'screen-cite.html')
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def idx(self, p, arch, variant=None):
        return p.evaluate(
            '([a,v])=>[...document.querySelectorAll("#stage>.slide")].findIndex(s=>s.dataset.archetype===a&&(v===null||s.dataset.variant===v))',
            [arch, variant])

    def test_host_signatures_fire_on_cite_slides(self):
        p = self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        self.addCleanup(p.close)
        page = p.new_page()
        page.goto((OUT / 'screen-cite.html').as_uri())
        page.evaluate('document.fonts.ready')
        page.wait_for_timeout(80)
        i = self.idx(page, 'mapping')
        page.evaluate(f'deckGo({i},0)')
        page.wait_for_timeout(60)
        sigs = {e['sig'] for e in page.evaluate('()=>window.eduMotion.sigLog') if e['slide'] == i}
        self.assertIn('paired-connection', sigs, 'mapping 호스트가 기존 레시피를 발화해야 한다')
        j = self.idx(page, 'compare-2', 'screens')
        page.evaluate(f'deckGo({j},0)')
        page.wait_for_timeout(60)
        sigs2 = {e['sig'] for e in page.evaluate('()=>window.eduMotion.sigLog') if e['slide'] == j}
        self.assertIn('opposed-faces', sigs2, 'compare-2 비교 변형이 opposed-faces 를 발화해야 한다')

    def test_render_probe_reports_no_overflow_on_cite_slides(self):
        p = self.browser.new_context(viewport={'width': 1920, 'height': 1080}, reduced_motion='reduce')
        self.addCleanup(p.close)
        page = p.new_page()
        page.goto((OUT / 'screen-cite.html').as_uri())
        page.add_style_tag(content='*,*::before,*::after{animation-duration:0s!important;transition-duration:0s!important}'
                                   '#help,#counter,#dots,#progress{display:none!important}')
        for arch, variant, steps in (('mapping', None, 2), ('compare-2', 'screens', 3)):
            i = self.idx(page, arch, variant)
            for s in range(steps + 1):
                page.evaluate(f'deckGo({i},{s})')
                out = page.evaluate(RENDER_JS, [i])
                self.assertEqual(out, [], f'{arch}/{variant} 단계 {s}: {out}')


if __name__ == '__main__':
    unittest.main()
