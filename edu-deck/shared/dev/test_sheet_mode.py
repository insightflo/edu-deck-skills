"""저자 검수 뷰어 모드(?sheet 접촉판·?shot 한 장 캡처) 계약.
URL 파라미터가 없으면 아무 일도 하지 않는다(정상 덱 불변). 파라미터가 있으면:
- ?sheet — 전 장 3단 그리드(1/3 축소)·번호표·단계 전개(정적 완결). ?sheet=N(2~6)은 단 수.
- ?shot=N — N번 장(0 시작)만 활성, 크롬 숨김.
"""
import re, shutil, sys, unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build
from check_deck import launch

SRC = Path('/tmp/sheet-test')
OUT = SRC / 'out'


def build_deck():
    if SRC.exists():
        shutil.rmtree(SRC)
    (SRC / 'src').mkdir(parents=True)
    files = ['03-timeline.html', '21-worked-example.html', '30-check.html']
    k = 0
    for f in files:
        txt = (S / 'assets' / 'snippets' / f).read_text(encoding='utf-8')
        for sec in re.findall(r'<section[^>]*class="slide[^"]*"[^>]*>.*?</section>', txt, re.S):
            k += 1
            (SRC / 'src' / f'{k:02d}.html').write_text(sec, encoding='utf-8')
            if k >= 6:
                break
        if k >= 6:
            break
    build('sheet 시험', sorted((SRC / 'src').glob('*.html')), [S / 'assets' / 'css'],
          [S / 'assets' / 'icons'], OUT / 'deck.html')


class SheetShot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_deck()
        cls.url = (OUT / 'deck.html').resolve().as_uri()
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def page(self, query=''):
        ctx = self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        pg = ctx.new_page()
        pg.goto(self.url + query)
        pg.wait_for_timeout(500)
        self.addCleanup(ctx.close)
        return pg

    def test_no_param_untouched(self):
        pg = self.page()
        r = pg.evaluate('''() => ({sheet: document.documentElement.classList.contains('is-sheet'),
          shot: document.documentElement.classList.contains('is-shot'),
          visible: [...document.querySelectorAll('#stage>.slide')].filter(s => getComputedStyle(s).display !== 'none').length})''')
        self.assertFalse(r['sheet'] or r['shot'])
        self.assertEqual(r['visible'], 1)

    def test_sheet_shows_all_slides_grid_with_numbers(self):
        pg = self.page('?sheet')
        r = pg.evaluate('''() => {
          const slides = [...document.querySelectorAll('#stage>.slide')];
          const stage = getComputedStyle(document.getElementById('stage'));
          return {sheet: document.documentElement.classList.contains('is-sheet'),
                  grid: stage.display === 'grid',
                  cols: stage.gridTemplateColumns.split(' ').length,
                  visible: slides.filter(s => getComputedStyle(s).display !== 'none').length,
                  total: slides.length,
                  tag: slides.length ? getComputedStyle(slides[2], '::after').content : '',
                  stepHideVisible: [...document.querySelectorAll('.step-hide')].every(e => getComputedStyle(e).visibility === 'visible')};}''')
        self.assertTrue(r['sheet'] and r['grid'])
        self.assertEqual(r['visible'], r['total'])
        self.assertGreaterEqual(r['total'], 5)
        self.assertEqual(r['cols'], 3)
        self.assertIn('counter(sheet-n)', r['tag'])  # 번호표 위 -- counter 값 자체는 렌더링에서만 전개된다(캡처로 육안 확인)
        self.assertTrue(r['stepHideVisible'])
        pg.close()

    def test_sheet_columns_param(self):
        pg = self.page('?sheet=5')
        r = pg.evaluate('''() => ({cols: getComputedStyle(document.getElementById('stage')).gridTemplateColumns.split(' ').length,
          v: getComputedStyle(document.documentElement).getPropertyValue('--sheet-cols').trim()})''')
        self.assertEqual((r['cols'], r['v']), (5, '5'))
        pg.close()

    def test_shot_isolates_slide(self):
        pg = self.page('?shot=2')
        r = pg.evaluate('''() => ({shot: document.documentElement.classList.contains('is-shot'),
          idx: [...document.querySelectorAll('#stage>.slide')].findIndex(s => s.classList.contains('active')),
          chromeHidden: getComputedStyle(document.getElementById('progress')).display === 'none'
            && getComputedStyle(document.getElementById('dots')).display === 'none'})''')
        self.assertTrue(r['shot'])
        self.assertEqual(r['idx'], 2)
        self.assertTrue(r['chromeHidden'])
        pg.close()

    def test_pack_shell_carries_rules(self):
        shell = (S / 'assets' / 'pack-shell.html').read_text(encoding='utf-8')
        legacy = (S / 'assets' / 'shell.html').read_text(encoding='utf-8')
        for needle in ('is-sheet', 'sheet.js' if 'sheet.js' in legacy else 'st-sheet'):
            self.assertIn(needle, legacy)
            self.assertIn(needle, shell)


if __name__ == '__main__':
    unittest.main()
