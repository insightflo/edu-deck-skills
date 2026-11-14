#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실사용 피드백 회귀 시험 (TASK-shell-feedback: A1·B3·B4).

[목적] ① A1 — 팩 덱의 비활성 장이 compact(좁은 화면)·인쇄에서 가로 방향으로 붕괴하던
       것: responsive.css 의 compact 규칙과 print 규칙이 .slide 에 세로 방향을 주고,
       생성된 두 셸에 실리며, 브라우저에서 전 장이 세로로 쌓인다.
       ② B3 — '텍스트 나열' WARN 이 img·figure·svg·data-visual 를 시각 계열로 인정해
       저작자가 그린 시각 장을 텍스트로 오인하지 않는다(아이콘 svg 는 제외).
       ③ B4 — verify_sources '출처 칩 없는 수치' 가 활동 장( part-divider·check·closing ),
       메타·키커 줄, 칩을 단 구성 요소 안의 보조 수치, '예시'·'가상' 표시 수치를 오탐하지
       않고, 일반 본문의 근거 없는 수치는 계속 WARN 한다.
[입력] 정적 조각 fixture + 임시 덱 HTML + 실제 Chromium.
[출력] 없음(단정문).
"""
import sys
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
import check_deck              # noqa: E402
import verify_sources as vs    # noqa: E402
from build_deck import build   # noqa: E402

OUT = Path(tempfile.mkdtemp(prefix='edu-shfb-'))
NOTE = ('시험 장의 발표 노트입니다. 실사용 피드백 회귀 계약을 확인하는 안내 문구로, '
        '자습 모드에서는 이 화면 그대로 읽습니다.')


def tsec(body, arch=None, extra=''):
    a = f' data-archetype="{arch}"' if arch else ''
    return f'<section class="slide"{a}{extra}>{body}<aside class="notes">{NOTE}</aside></section>'


def run_static(sections):
    html = ('<!doctype html><html lang="ko"><head><title>t</title></head><body>'
            '<div id="stage">' + ''.join(sections) + '</div></body></html>')
    rep = check_deck.Report()
    check_deck.static_checks(html, BeautifulSoup(html, 'html.parser'), rep, False)
    return rep


def text_run_warns(rep):
    return [it for it in rep.items if it['kind'] == '텍스트 나열']


TEXT = '<h2 class="title">본문</h2><p>설명 문단입니다.</p>'


class TestA1CompactPrint(unittest.TestCase):
    """A1 — compact·print 에서 팩 덱 비활성 장의 세로 방향."""

    def test_responsive_css_rules(self):
        css = (S / 'assets' / 'css' / 'responsive.css').read_text(encoding='utf-8')
        # compact: 비활성 장에도 column 방향
        m = css.split('html.ed-compact #stage .slide{', 1)
        self.assertEqual(len(m), 2, 'compact .slide 규칙이 없다')
        self.assertIn('flex-direction:column', m[1].split('}')[0])
        # print: 전 장 column 방향
        self.assertIn('.slide{flex-direction:column!important}', css)

    def test_shells_carry_rules(self):
        for name in ('shell.html', 'pack-shell.html'):
            with self.subTest(shell=name):
                text = (S / 'assets' / name).read_text(encoding='utf-8')
                self.assertIn('.slide{flex-direction:column!important}', text,
                              f'{name} 인쇄 세로 규칙 없음 — port.py 재생성 필요')
                m = text.split('html.ed-compact #stage .slide{', 1)
                self.assertEqual(len(m), 2)
                self.assertIn('flex-direction:column', m[1].split('}')[0])


class TestA1Browser(unittest.TestCase):
    """A1 — 실제 렌더: 팩 덱 760px compact·인쇄에서 전 장이 세로로 쌓인다."""

    @classmethod
    def setUpClass(cls):
        src = OUT / 'src'
        src.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(3):
            p = src / f'{i:02d}.html'
            p.write_text(
                '<section class="slide pack pack-editorial" data-design="editorial">'
                f'<p class="pack-kicker">시험 {i}</p><h1 class="pack-prompt">장 {i}</h1>'
                '<div class="pack-body"><p>한 단락</p><p>두 단락</p><p>세 단락</p></div>'
                f'<aside class="notes">{NOTE}</aside></section>', encoding='utf-8')
            paths.append(p)
        cls.html = OUT / 'pack-deck.html'
        build('팩 compact 시험', paths, [S / 'assets/css'], [S / 'assets/icons'],
              cls.html, resource_pack={'design': 'editorial', 'flow': 'problem'})
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(channel='chrome')

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()

    def _page(self):
        pg = self._browser.new_context(
            viewport={'width': 760, 'height': 900}).new_page()
        pg.goto('file://' + str(self.html))
        pg.wait_for_selector('html.ed-compact .slide.active', timeout=10000)
        return pg

    def _slide_dirs(self, pg):
        return pg.evaluate(
            "[...document.querySelectorAll('#stage>.slide')]"
            ".map(s=>getComputedStyle(s).flexDirection)")

    def test_compact_stacks_vertically(self):
        pg = self._page()
        pg.wait_for_timeout(300)
        dirs = self._slide_dirs(pg)
        self.assertEqual(dirs, ['column'] * 3,
                         'compact 비활성 장이 가로 방향으로 붕괴했다')
        tops = pg.evaluate(
            "[...document.querySelectorAll('#stage>.slide')]"
            ".map(s=>s.getBoundingClientRect().top)")
        self.assertEqual(tops, sorted(tops), '장이 위에서 아래로 쌓여야 한다')
        self.assertGreater(tops[-1], tops[0], '세 장이 겹치지 않고 나란히 세로 배치된다')
        pg.context.close()

    def test_print_column(self):
        pg = self._page()
        pg.emulate_media(media='print')
        pg.wait_for_timeout(400)
        dirs = self._slide_dirs(pg)
        self.assertEqual(dirs, ['column'] * 3, '인쇄에서 장이 가로 방향으로 붕괴했다')
        pg.context.close()


class TestB3TextRun(unittest.TestCase):
    """B3 — 텍스트 나열 판정이 실제 시각 마크업을 인정한다."""

    def test_true_text_run_warns(self):
        rep = run_static([tsec(TEXT) for _ in range(6)])
        self.assertTrue(text_run_warns(rep), '텍스트만 6장 연속인데 WARN 이 안 떴다')

    def test_figure_breaks_run(self):
        secs = [tsec(TEXT) for _ in range(3)]
        secs.append(tsec(TEXT + '<figure><div class="gd-box">그림</div></figure>'))
        secs += [tsec(TEXT) for _ in range(3)]
        self.assertFalse(text_run_warns(run_static(secs)), 'figure 장이 시각 계열로 안 잡혔다')

    def test_img_breaks_run(self):
        secs = [tsec(TEXT) for _ in range(3)]
        secs.append(tsec(TEXT + '<img src="data:," alt="실물 화면">'))
        secs += [tsec(TEXT) for _ in range(3)]
        self.assertFalse(text_run_warns(run_static(secs)), 'img 장이 시각 계열로 안 잡혔다')

    def test_svg_breaks_run(self):
        secs = [tsec(TEXT) for _ in range(3)]
        secs.append(tsec(TEXT + '<svg viewBox="0 0 10 10" role="img" '
                              'aria-label="도식"><circle r="4"/></svg>'))
        secs += [tsec(TEXT) for _ in range(3)]
        self.assertFalse(text_run_warns(run_static(secs)), 'svg 장이 시각 계열로 안 잡혔다')

    def test_icon_svg_does_not_count(self):
        # 장식 아이콘(svg.ico·aria-hidden)은 시각 계열이 아니다 — 텍스트 나열 계약 유지
        secs = [tsec(TEXT) for _ in range(3)]
        secs.append(tsec(TEXT + '<svg class="ico" viewBox="0 0 24 24"><path d="M0 0h4v4z"/></svg>'
                               '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M0 0h4v4z"/></svg>'))
        secs += [tsec(TEXT) for _ in range(3)]
        self.assertTrue(text_run_warns(run_static(secs)),
                        '아이콘 svg 가 연속열을 끊으면 안 된다')

    def test_data_visual_breaks_run(self):
        # 저작자 선언 — 자손 요소의 data-visual
        secs = [tsec(TEXT) for _ in range(3)]
        secs.append(tsec(TEXT + '<div data-visual="process-flow">글 상자들</div>'))
        secs += [tsec(TEXT) for _ in range(3)]
        self.assertFalse(text_run_warns(run_static(secs)),
                         'data-visual 요소가 시각 계열로 안 잡혔다')
        # 장 자체의 data-visual
        secs = [tsec(TEXT) for _ in range(3)]
        secs.append(tsec(TEXT, extra=' data-visual="hero"'))
        secs += [tsec(TEXT) for _ in range(3)]
        self.assertFalse(text_run_warns(run_static(secs)),
                         '장의 data-visual 속성이 시각 계열로 안 잡혔다')


FACTS = {"F01": {"확인": "원문대조", "출처": "https://example.com/doc",
                 "주장": "billed once per request", "값": "1회"}}


class TestB4LooseNumbers(unittest.TestCase):
    """B4 — 근거 없는 수치 어림 검사의 오탐 완화와 정상 유지."""

    def _loose(self, *sections):
        html = ('<!doctype html><html lang="ko"><head><title>t</title></head><body>'
                '<div id="stage">' + ''.join(sections) + '</div></body></html>')
        p = OUT / 'deck-b4.html'
        p.write_text(html, encoding='utf-8')
        out = vs.Out()
        vs.check_html(p, FACTS, out)
        return [(w, m) for sev, w, m in out.rows
                if sev == 'WARN' and '출처 칩 없는 수치' in m]

    def test_ops_archetypes_exempt(self):
        # part-divider·check·closing 의 활동·운영 수치는 어림 검사를 생략한다
        for arch in ('part-divider', 'check', 'closing'):
            with self.subTest(arch=arch):
                warns = self._loose(
                    tsec('<p>이 단계는 활동 5분 · 산출물 1곳 · 발표 30초로 진행합니다.</p>',
                         arch=arch))
                self.assertFalse(warns, f'{arch} 장의 운영 수치가 오탐됐다: {warns}')

    def test_example_marker_exempt(self):
        # '예시' 마커가 같은 문맥 블록에 있으면 예시 값이다
        warns = self._loose(
            tsec('<p>예시 질문: "청결 상태 — 0 깨끗 / 1 부분 오염 / 2 주요 오염"</p>'))
        self.assertFalse(warns, f'예시 표시 수치가 오탐됐다: {warns}')
        # '가상' 마커
        warns = self._loose(tsec('<p>가상 데이터 — 전환율 40% · 비용 5배</p>'))
        self.assertFalse(warns, f'가상 표시 수치가 오탐됐다: {warns}')

    def test_chipped_component_exempt(self):
        # 수치가 .fact 칩을 품은 장 최상위 구성 요소 안에 있으면 그 출처 표시의 일부다
        warns = self._loose(tsec(
            '<div><div><span class="v">입력 1회</span><span>약 5배</span>'
            '<p class="fact" data-src="F01">billed once per request</p></div></div>'))
        self.assertFalse(warns, f'칩을 단 구성 요소 안의 수치가 오탐됐다: {warns}')

    def test_meta_line_exempt(self):
        # kicker·eyebrow·*meta* 줄의 수치는 장 운영 정보다
        warns = self._loose(
            tsec('<p class="pack-kicker">이미 쓰는 팀들 · 내부 사례 4종</p>'
                 '<div><p>본문 문장입니다.</p></div>'),
            tsec('<div class="cv-meta"><span>대상 교육 · 25–30분 · 22장</span></div>'),
            tsec('<p class="eyebrow">파트 3 · 활동 10분</p>'))
        self.assertFalse(warns, f'메타·키커 줄의 수치가 오탐됐다: {warns}')

    def test_unsourced_body_number_still_warns(self):
        # 회귀: 일반 본문의 근거 없는 수치는 계속 WARN
        warns = self._loose(tsec('<div><p>지연을 40% 줄였습니다.</p></div>'))
        self.assertTrue(warns, '근거 없는 본문 수치가 WARN 을 안 냈다')
        # 칩이 다른 구성 요소에만 있으면 이 수치는 묶이지 않는다
        warns = self._loose(tsec(
            '<div><p>매출이 5배 늘었습니다.</p></div>'
            '<footer><p class="fact" data-src="F01">unrelated fact</p></footer>'))
        self.assertTrue(warns, '칩과 무관한 본문 수치가 WARN 을 안 냈다')


if __name__ == '__main__':
    unittest.main()
