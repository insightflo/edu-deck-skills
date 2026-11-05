#!/usr/bin/env python3
"""자유 모드 검사 회귀 시험: 취향 INFO/`--style`·아키타입 선택화·정적 완결.

[목적] TASK-free-mode G2~G4. (1) 취향 규칙(길이·개수·구성)은 기본 실행에서 INFO 요약으로
       내리고 `--style` 에서 기존 WARN 으로 보인다. RESULT 줄은 errors/warnings 앞부분을
       깨지 않고 info= 를 뒤에 붙인다. (2) data-archetype 없는 자유 장은 ERROR 가 아니라
       INFO — 엔진 자동 배정이 정식 경로다. (3) 자유 장의 단계 요소가 인쇄(print 미디어)·
       자습(S)·prefers-reduced-motion 에서 지금까지 드러난 모든 단계를 정적으로 보인다.
[입력] 테스트 안 문자열 픽스처(스니펫에 넣지 않는다).
[출력] 없음(단정문). 실패는 심각도 정책 퇴행·정적 완결 붕괴다.
[주의] 정적 완결은 shell_template 의 matchMedia('print') 폴백에 의존한다 —
       beforeprint 를 보내지 않는 헤드리스 에뮬레이션에서도 모든 장을 마지막 단계로 펼친다.
"""
import io
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / 'scripts'))
import build_deck            # noqa: E402
import check_deck            # noqa: E402

NOTE = ('발표자 노트입니다. 자유 모드 검사가 무엇을 보고 무엇을 보지 않는지 설명하는 '
        '자리로, 발표 중에 읽을 수 있는 분량의 안내 문장을 둡니다.')


def sec(body, arch=None, extra=''):
    a = f' data-archetype="{arch}"' if arch else ''
    return f'<section class="slide"{a}{extra}>{body}<aside class="notes">{NOTE}</aside></section>'


def static(html):
    soup = BeautifulSoup(html, 'html.parser')
    rep = check_deck.Report()
    check_deck.static_checks(html, soup, rep, False)
    return rep


def doc(*sections):
    body = ''.join(sections)
    return (f'<!doctype html><html><head><title>t</title></head><body>'
            f'<div id="stage">{body}</div></body></html>')


def build(title, sections, out_dir):
    d = Path(out_dir)
    (d / 'src').mkdir(parents=True, exist_ok=True)
    (d / 'deck.json').write_text('{"title":"%s","output":"result.html"}' % title, encoding='utf-8')
    for i, s in enumerate(sections, 1):
        (d / 'src' / f'{i:02d}.html').write_text(s, encoding='utf-8')
    build_deck.build(title, sorted((d / 'src').glob('*.html')),
                     [SHARED / 'assets' / 'css'], [SHARED / 'assets' / 'icons'], d / 'result.html')
    return d / 'result.html'


def run_cli(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = check_deck.main(list(argv))
    return code, buf.getvalue()


class SeverityPolicy(unittest.TestCase):
    """G2 — 취향은 기본 INFO 요약, --style 에서 WARN. RESULT 앞부분 계약 유지."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='edu-free-')
        cls.addClassCleanup(cls.tmp.cleanup)
        # 취향 위반 픽스처: 30자 넘는 제목 + 목록 7개 — 안전 가드 위반은 없음
        long_title = '이 제목은 서른 글자를 넘기 위해 아주 길게 쓴 자유 장의 제목입니다'
        cls.deck = build('취향 시험', [
            sec(f'<h1 class="title">{long_title}</h1><ol><li>1</li><li>2</li><li>3</li>'
                '<li>4</li><li>5</li><li>6</li><li>7</li></ol>'),
            sec('<h1>마무리</h1><p>끝</p>', arch='closing'),
        ], Path(cls.tmp.name) / 'taste')

    # 기본 실행: 취향은 WARN 이 아니라 INFO 요약 한 줄
    def test_taste_is_info_summary_by_default(self):
        code, out = run_cli(str(self.deck), '--no-render')
        warn_lines = [l for l in out.splitlines() if l.startswith('WARN')]
        self.assertEqual(warn_lines, [], f'기본 실행에 WARN 줄이 남았습니다: {warn_lines}')
        self.assertTrue(any(l.startswith('INFO') and '취향:' in l for l in out.splitlines()),
                        '취향 요약 INFO 줄이 없습니다')

    # --style: 취향이 기존 심각도(WARN)로 개별 출력
    def test_style_flag_restores_warn_lines(self):
        code, out = run_cli(str(self.deck), '--no-render', '--style')
        warn_lines = [l for l in out.splitlines() if l.startswith('WARN')]
        self.assertTrue(any('제목' in l for l in warn_lines), f'제목 WARN 이 없습니다: {out}')
        self.assertTrue(any('목록' in l for l in warn_lines), f'목록 WARN 이 없습니다: {out}')
        self.assertFalse(any('취향:' in l for l in out.splitlines()), '--style 에 요약 줄이 남았습니다')

    # RESULT 줄: errors=N warnings=N 앞부분 유지 + info=N 추가
    def test_result_line_format(self):
        _, out = run_cli(str(self.deck), '--no-render')
        m = re.search(r'RESULT: (PASS|FAIL)  errors=(\d+) warnings=(\d+) info=(\d+) ', out)
        self.assertIsNotNone(m, f'RESULT 형식이 다릅니다: {out.splitlines()[-1]}')
        self.assertEqual(m.group(2), '0')
        self.assertEqual(m.group(3), '0')   # 기본은 취향이 INFO 라 warnings=0
        self.assertGreater(int(m.group(4)), 0)
        _, out2 = run_cli(str(self.deck), '--no-render', '--style')
        m2 = re.search(r'RESULT: (PASS|FAIL)  errors=(\d+) warnings=(\d+) info=(\d+) ', out2)
        self.assertIsNotNone(m2)
        self.assertGreater(int(m2.group(3)), 0)   # --style 은 warnings>0

    # 안전 가드 ERROR 는 기본·--style 모두 그대로
    def test_safety_errors_unchanged(self):
        bad = static(doc(sec('<h1>깨짐</h1><script>alert(1)</script>')))
        self.assertTrue(any(i['sev'] == 'ERROR' and i['kind'] == '스크립트' for i in bad.items))
        styled = check_deck.Report(style=True)
        check_deck.static_checks(doc(sec('<h1>깨짐</h1><script>alert(1)</script>')),
                                 BeautifulSoup(doc(sec('<h1>깨짐</h1><script>alert(1)</script>')), 'html.parser'),
                                 styled, False)
        self.assertTrue(any(i['sev'] == 'ERROR' and i['kind'] == '스크립트' for i in styled.items))


class ArchetypeOptional(unittest.TestCase):
    """G3 — data-archetype 없는 장은 ERROR 가 아니라 INFO. check 계약은 선언 장만."""

    def test_missing_archetype_is_info_not_error(self):
        rep = static(doc(sec('<h1>자유 장</h1><p>내용</p>')))
        arch_items = [i for i in rep.items if i['kind'] == '아키타입']
        self.assertTrue(any(i['sev'] == 'INFO' for i in arch_items),
                        f'아키타입 INFO 가 없습니다: {arch_items}')
        self.assertFalse(any(i['sev'] == 'ERROR' and i['kind'] == '아키타입' for i in rep.items))

    def test_unknown_archetype_still_error(self):
        rep = static(doc(sec('<h1>오타</h1>', arch='statment')))
        self.assertTrue(any(i['sev'] == 'ERROR' and i['kind'] == '아키타입' for i in rep.items))

    def test_chk_contract_only_when_check_declared(self):
        # 선언 없이 .chk 마크업을 쓴 자유 장 → 확인 문제 계약 ERROR 없음
        free_chk = sec('<h1>자유 퀴즈</h1><div class="chk"><p class="chk-q">질문</p>'
                       '<p class="chk-why">해설</p><p class="chk-o" data-ok>답</p>'
                       '<p class="chk-o">오답</p></div>')
        rep = static(doc(free_chk))
        self.assertFalse(any(i['kind'] == '확인 문제' and i['sev'] == 'ERROR' for i in rep.items))
        # arch="check" 선언 장에 .chk 없음 → ERROR 유지
        rep2 = static(doc(sec('<h1>선언 퀴즈</h1><p>내용</p>', arch='check')))
        self.assertTrue(any(i['kind'] == '확인 문제' and i['sev'] == 'ERROR' for i in rep2.items))


class StaticCompleteness(unittest.TestCase):
    """G4 — 자유 장이 인쇄·자습·reduced-motion 에서 드러난 단계를 정적으로 보인다."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='edu-free-static-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.deck = build('정적 완결', [
            sec('<h1>자유 장</h1>'
                '<p data-step="1" style="font-size:30px">첫 단계</p>'
                '<p data-step="2" style="font-size:30px">둘째 단계</p>'
                '<p data-add="1" style="font-size:30px">추가 블록</p>'
                '<p data-only="2" style="font-size:30px">둘째 단계 전용</p>'),
            sec('<h1>마무리</h1><p>끝</p>', arch='closing'),
        ], Path(cls.tmp.name) / 'static')
        cls.pw = sync_playwright().start()
        cls.addClassCleanup(cls.pw.stop)
        cls.browser = check_deck.launch(cls.pw)
        cls.addClassCleanup(cls.browser.close)

    def page(self, **ctx_kw):
        ctx = self.browser.new_context(viewport={'width': 1920, 'height': 1080}, **ctx_kw)
        self.addCleanup(ctx.close)
        p = ctx.new_page()
        p.goto(self.deck.as_uri())
        return p

    @staticmethod
    def hidden_steps(p):
        """현재 화면에서 보이지 않는 단계 요소 목록(진단 메시지용)."""
        return p.evaluate("""() => [...document.querySelectorAll('[data-step],[data-add],[data-only],[data-until]')]
            .filter(e => getComputedStyle(e).visibility === 'hidden' || getComputedStyle(e).display === 'none')
            .map(e => e.textContent)""")

    # 인쇄 미디어: 모든 장이 마지막 단계로 펼쳐져 단계 요소가 전부 보인다
    def test_print_media_expands_all_steps(self):
        p = self.page()
        p.evaluate('window.deckGo(0, 0)')
        self.assertTrue(self.hidden_steps(p), '비교 기준: step 0 에서 숨은 요소가 있어야 한다')
        p.emulate_media(media='print')
        p.wait_for_timeout(120)
        self.assertEqual(self.hidden_steps(p), [], '인쇄 미디어에서 숨은 단계 요소가 남았습니다')

    # reduced-motion: 마지막 단계까지 드러낸 요소는 전부 정적으로 보인다
    def test_reduced_motion_shows_revealed_steps(self):
        p = self.page(reduced_motion='reduce')
        p.evaluate('window.deckGo(0)')
        self.assertEqual(self.hidden_steps(p), [], 'reduced-motion 에서 드러난 단계가 안 보입니다')

    # 자습(S): st-self 가 켜져도 드러난 단계는 그대로 보인다
    def test_self_study_shows_revealed_steps(self):
        p = self.page()
        p.evaluate('window.deckGo(0)')
        p.keyboard.press('s')
        p.wait_for_timeout(120)
        self.assertTrue(p.evaluate("document.body.classList.contains('st-self')"),
                        'S 키로 자습 모드가 켜지지 않았습니다')
        self.assertEqual(self.hidden_steps(p), [], '자습 모드에서 드러난 단계가 안 보입니다')


if __name__ == '__main__':
    unittest.main()
