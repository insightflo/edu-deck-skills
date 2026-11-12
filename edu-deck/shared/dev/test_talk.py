"""Acceptance: talk mode — X/R timer, notes header plan, V presenter view + 2-way sync,
static talk warnings, build --notes rehearsal sheet, non-talk decks stay clean.

Builds a 4-slide talk deck (data-sec 45+60+45+30=180, talk.total=200) and the same deck
without talk config into /tmp, then drives real Chromium (channel='chrome').
"""
import json, subprocess, sys, unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build, write_notes, rehearsal_rows
from check_deck import launch, Report, talk_checks

OUT = Path('/tmp/edudeck-talk')
SRC = OUT / 'src'
NOTES = '이 장의 핵심을 차근차근 설명합니다. '
SECS = [45, 60, 45, 30]
TALK = {'total': 200, 'rate': 300}


def slide(i, title, sec, notes=NOTES):
    arch = 'cover' if i == 1 else 'statement'
    inner = (f'<div class="cx-inner"><p class="cx-eyebrow">시험</p><h2 class="cx-title">{title}</h2></div>'
             if arch == 'cover' else
             f'<div class="head"><p class="eyebrow">시험</p><h2 class="title">{title}</h2></div>'
             f'<p class="body" style="font-size:30px">본문 {i}.</p>')
    return (f'<section class="slide" data-archetype="{arch}" data-sec="{sec}">{inner}'
            f'<aside class="notes">{notes}</aside></section>')


class Talk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SRC.mkdir(parents=True, exist_ok=True)
        titles = ['첫 장', '둘째 장', '셋째 장', '마지막 장']
        srcs = []
        for i, (t, sec) in enumerate(zip(titles, SECS), 1):
            p = SRC / f'{i:02d}-s.html'
            p.write_text(slide(i, t, sec), encoding='utf-8')
            srcs.append(p)
        cls.html = OUT / 'talk.html'
        build('발표 시험', srcs, [S / 'assets/css'], [S / 'assets/icons'],
              cls.html, study={'talk': dict(TALK)})
        cls.html_plain = OUT / 'plain.html'
        build('일반 덱', srcs, [S / 'assets/css'], [S / 'assets/icons'], cls.html_plain)
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def page(self, url=None, reduced=True):
        c = self.browser.new_context(viewport={'width': 1920, 'height': 1080},
                                     reduced_motion='reduce' if reduced else 'no-preference')
        self.addCleanup(c.close)
        p = c.new_page()
        p.goto(url or self.html.as_uri())
        p.evaluate('document.fonts.ready')
        return p

    def clock(self, p):
        return p.evaluate("document.getElementById('ed-clock').textContent")

    # ---------- D1 타이머 ----------
    def test_timer_keys(self):
        p = self.page()
        self.assertTrue(p.evaluate("document.documentElement.classList.contains('ed-talk')"))
        self.assertEqual(self.clock(p).replace(' ', ''), '0:00/0:45')  # 첫 장 누적 45초
        p.keyboard.press('x')
        self.assertTrue(p.evaluate("document.getElementById('ed-clock').classList.contains('is-run')"))
        p.wait_for_timeout(1300)
        self.assertNotEqual(self.clock(p).split('/')[0].strip(), '0:00')
        p.keyboard.press('x')
        self.assertFalse(p.evaluate("document.getElementById('ed-clock').classList.contains('is-run')"))
        p.keyboard.press('r')
        self.assertEqual(self.clock(p).split('/')[0].strip(), '0:00')

    # ---------- D2 노트 패널 머리 ----------
    def test_notes_header_plan(self):
        p = self.page()
        p.keyboard.press('n')
        h = p.evaluate("document.querySelector('#notes .h').textContent")
        self.assertIn('이 장 45초', h)
        self.assertIn('~0:45까지', h)
        p.evaluate('deckGo(1,0)')  # 둘째 장: 이 장 60초, 누적 105초=1:45
        h = p.evaluate("document.querySelector('#notes .h').textContent")
        self.assertIn('이 장 60초', h)
        self.assertIn('~1:45까지', h)

    # ---------- D3 발표자 보기 ----------
    def test_presenter_sync_both_ways(self):
        p = self.page(reduced=False)  # 움직임 켠 상태에서도 발표자 창은 정적이어야 한다
        with p.context.expect_page() as pop_info:
            p.keyboard.press('v')
        pop = pop_info.value
        self.addCleanup(pop.close)
        pop.wait_for_load_state('load')
        self.assertIn('presenter', pop.url)
        pop.wait_for_timeout(500)
        st = pop.evaluate("""()=>({pres:document.body.classList.contains('st-presenter'),
          dom:!!document.querySelector('.ed-pres'),
          clock:!!document.querySelector('.ed-pres-clock .t'),
          anims:document.getAnimations().filter(a=>a.playState==='running').length});""")
        self.assertTrue(st['pres'])
        self.assertTrue(st['dom'])
        self.assertTrue(st['clock'])
        self.assertEqual(st['anims'], 0, 'presenter window must stay static')
        # 본창 → 발표자창
        p.evaluate('deckGo(2,0)')
        for _ in range(40):
            if pop.evaluate('deckInfo().slide') == 2:
                break
            pop.wait_for_timeout(100)
        self.assertEqual(pop.evaluate('deckInfo().slide'), 2)
        self.assertIn('3 / 4장', pop.evaluate("document.querySelector('.ed-pres-cur').textContent"))
        # 발표자창 → 본창
        pop.click('.ed-pres-row .ed-pbtn >> nth=1')  # '다음 →'
        for _ in range(40):
            if p.evaluate('deckInfo().slide') == 3:
                break
            pop.wait_for_timeout(100)
        self.assertEqual(p.evaluate('deckInfo().slide'), 3)
        self.assertEqual(pop.evaluate('deckInfo().slide'), 3)

    # ---------- 비발표 덱은 발표 UI 없음 ----------
    def test_non_talk_deck_has_no_talk_ui(self):
        p = self.page(url=self.html_plain.as_uri())
        self.assertFalse(p.evaluate("document.documentElement.classList.contains('ed-talk')"))
        # 기능 없는 덱은 타이머 버튼이 DOM 에 아예 없다(도구 띠 노출 계약)
        self.assertIsNone(p.evaluate("document.getElementById('ed-clock')"))
        self.assertNotIn('X 타이머', p.evaluate("document.getElementById('help').textContent"))
        p.keyboard.press('x')
        p.wait_for_timeout(300)
        self.assertIsNone(p.evaluate("document.getElementById('ed-clock')"))
        h = p.evaluate("document.querySelector('#notes .h').textContent")
        self.assertNotIn('이 장', h)

    # ---------- D5 정적 경고 ----------
    def test_talk_warnings(self):
        # 변형 덱: 2번 장 data-sec 누락, 노트 과다, total 불일치
        bad = OUT / 'bad'
        bad.mkdir(exist_ok=True)
        long_notes = NOTES * 30  # 45초 분량(148음절×1.1)을 훨씬 넘김
        files = [
            slide(1, '첫 장', 45),
            slide(2, '둘째 장', 0).replace('data-sec="0"', ''),  # data-sec 없음
            slide(3, '셋째 장', 45, long_notes),
        ]
        srcs = []
        for i, h in enumerate(files, 1):
            f = bad / f'{i:02d}.html'
            f.write_text(h, encoding='utf-8')
            srcs.append(f)
        out = bad / 'bad.html'
        build('경고 시험', srcs, [S / 'assets/css'], [S / 'assets/icons'],
              out, study={'talk': {'total': 1200, 'rate': 300}})
        soup = BeautifulSoup(out.read_text(encoding='utf-8'), 'html.parser')
        rep = Report()
        talk_checks(out.read_text(encoding='utf-8'), soup.select('#stage>.slide'), rep)
        kinds = [it['kind'] for it in rep.items]
        msgs = ' '.join(it['message'] for it in rep.items)
        self.assertIn('예상 시간', kinds)
        self.assertIn('시간 합계', kinds)
        self.assertIn('대본 분량', kinds)
        # 비발표 덱: 같은 조각이라도 경고 없음
        rep2 = Report()
        plain_text = self.html_plain.read_text(encoding='utf-8')
        soup2 = BeautifulSoup(plain_text, 'html.parser')
        talk_checks(plain_text, soup2.select('#stage>.slide'), rep2)
        self.assertEqual(rep2.items, [])

    # ---------- build --notes ----------
    def test_notes_sheet(self):
        d = OUT / 'deckdir'
        (d / 'src').mkdir(parents=True, exist_ok=True)
        (d / 'deck.json').write_text(json.dumps(
            {'title': '발표 시험', 'output': 'talk.html', 'talk': dict(TALK)},
            ensure_ascii=False), encoding='utf-8')
        for i, (t, sec) in enumerate(zip(['첫 장', '둘째 장'], SECS[:2]), 1):
            (d / 'src' / f'{i:02d}-s.html').write_text(slide(i, t, sec), encoding='utf-8')
        md = d / 'notes.md'
        rc = subprocess.run([sys.executable, str(S / 'scripts' / 'build_deck.py'),
                             str(d), '--notes', str(md)],
                            capture_output=True, text=True, timeout=120)
        self.assertEqual(rc.returncode, 0, rc.stderr)
        txt = md.read_text(encoding='utf-8')
        self.assertIn('## 1. 첫 장', txt)
        self.assertIn('## 2. 둘째 장', txt)
        self.assertIn('예정 45초', txt)
        self.assertIn('예정 60초', txt)
        self.assertIn('누적 0:45', txt)
        self.assertIn('누적 1:45', txt)
        self.assertIn('대본 읽기 어림', txt)
        self.assertIn('목표 시간 3:20', txt)
        self.assertIn(NOTES.strip(), txt)


if __name__ == '__main__':
    unittest.main()
