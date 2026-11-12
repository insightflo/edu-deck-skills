# test_theme_switch.py — 테마 미리보기 패널(themes.js + theme-switch.css)과
# 16종 테마 계약 검증. 실행: unittest discover 의 일부로 돈다.
import re,sys,unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'scripts'))
import tone_router

CSS=(BASE/'assets/css/themes.css').read_text(encoding='utf-8')
SH=(BASE/'assets/shell.html').read_text(encoding='utf-8')
PK=(BASE/'assets/pack-shell.html').read_text(encoding='utf-8')
JS=(BASE/'assets/js/themes.js').read_text(encoding='utf-8')
SW=(BASE/'assets/css/theme-switch.css').read_text(encoding='utf-8')

ROLES=['ink','paper','light','soft','line','accent','accent-text','accent-light',
       'blue','blue-text','blue-soft','success','danger','muted','chip']
SHAPES=['r1','r2','r3','m1','m2','m3','m4','e-spring']

class TestThemeCount(unittest.TestCase):
    def test_sixteen_legacy_themes(self):
        self.assertEqual(16,len(tone_router.THEME_CSS_IDS),
                         f'CSS 테마는 16종이어야 한다: {tone_router.THEME_CSS_IDS}')

class TestNewThemeBlocks(unittest.TestCase):
    def test_all_roles_and_shapes(self):
        for tid in tone_router.THEME_CSS_IDS:
            m=re.search(r'\[data-theme="%s"\]\{(.*?)\}'%re.escape(tid),CSS,re.S)
            self.assertIsNotNone(m,f'{tid} 블록 없음')
            body=m.group(1)
            for r in ROLES+SHAPES:
                self.assertIn('--'+r+':',body,f'{tid} --{r} 없음')
    def test_new_ids_absent_from_absorb(self):
        """신규 8종×15역할=120 헥스가 absorb 원본(yaml + all-themes.html
        __LIVE_THEMES 전체 헥스)과 겹치지 않는지 전수 검사."""
        absorb=Path(__file__).resolve().parents[3]/'workspace/absorb'
        vals=[]
        for tid in ['mono','brick','honey','mint','violet','coral','olive','espresso']:
            body=re.search(r'\[data-theme="%s"\]\{(.*?)\}'%tid,CSS,re.S).group(1)
            vals+=[h.lower() for h in re.findall(r'#[0-9a-fA-F]{6}\b',body)]
        self.assertEqual(120,len(vals))
        hexes=set(vals)
        src=set()
        for yf in absorb.rglob('*.yaml'):
            src|={h.lower() for h in re.findall(r'#[0-9a-fA-F]{6}\b',
                                              yf.read_text(encoding='utf-8'))}
        at=absorb/'all-themes.html'
        src|={h.lower() for h in re.findall(r'#[0-9a-fA-F]{6}\b',
                                          at.read_text(encoding='utf-8'))}
        hits=hexes&src
        self.assertFalse(hits,f'원본 헥스와 겹침: {sorted(hits)}')

class TestPreviewInjection(unittest.TestCase):
    def test_shell_has_switcher(self):
        for name,src in (('shell',SH),('pack-shell',PK)):
            self.assertIn('edThemes',src,f'{name} 에 패널 코드 없음')
            self.assertIn('edu-theme-preview-',src,f'{name} 에 localStorage 키 없음')
            self.assertIn('ed-th-item',src,f'{name} 에 패널 CSS 없음')
    def test_pack_deck_gate(self):
        self.assertIn('edu-deck-resource-pack',JS)
    def test_preview_contract(self):
        self.assertIn('removeAttribute',JS)
        self.assertIn("'themes'",JS)
        self.assertIn("'theme'",JS)
        self.assertIn('localStorage',JS)
        self.assertIn("==='t'",JS)          # 테마 토글 키는 T(ㅅ) — 도움말이 H 를 가져감
        self.assertIn("==='ㅅ'",JS)
        self.assertNotIn("==='h'",JS)
        self.assertNotIn("==='ㅗ'",JS)
    def test_hidden_surfaces(self):
        for sel in ['is-sheet','is-shot','st-printing','st-presenter','@media print']:
            self.assertIn(sel,SW,f'숨김 표면 {sel} 없음')

if __name__=='__main__':unittest.main()
