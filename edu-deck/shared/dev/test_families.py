"""Acceptance: P1 스타일 계열 — tokens·families·parts·빌더·검사기 계약.

[검사 항목]
1. classic 무변화: family 미지정 덱을 재빌드하면 <html> 에 data-family 가 없고,
   families.css 의 모든 규칙은 [data-family] 스코프 안이라 classic 렌더에 닿지 않는다.
   playwright+PIL+기준선 PNG 가 있으면 대표 장 픽셀까지 맞춘다(없으면 skip — 전수는 검증자가).
2. 계열 역할 완결성: families.css 의 각 [data-family] 블록이 SEMANTIC_ROLES 를 모두 덮고,
   블록 id 가 tone_router.FAMILIES 안이다.
3. 부품·studio 변형: parts.css 에 13종 .pt-* 기본 정의와 [data-family="studio"] 변형이 있다.
4. 빌드 스탬핑: family 덱은 <html data-family="…">, classic 덱은 속성 자체가 없다.
5. family+theme 오류: load_deck·build 양쪽에서 BuildError.
6. 매트릭스: build_matrix 에 family:studio 행이 있고 전 쌍이 통과다.
7. 프리셋 방어: style_preset --apply 가 non-classic 덱을 거부하고,
   preset-css 표식 CSS 가 계열 덱 조립에서 BuildError.

[실행] cd edu-deck/shared && python3 -m unittest dev.test_families -v
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

S = pathlib.Path(__file__).resolve().parents[1]        # edu-deck/shared
ROOT = S.parents[1]                                    # 저장소 루트
BUILD = S / 'scripts' / 'build_deck.py'
CHECK = S / 'scripts' / 'check_deck.py'
PRESET = S / 'scripts' / 'style_preset.py'
CSS = S / 'assets' / 'css'

sys.path.insert(0, str(S / 'scripts'))
import build_deck as bd   # noqa: E402
import check_deck as cd   # noqa: E402
import tone_router as tr  # noqa: E402

SLIDE = ('<section class="slide" data-archetype="statement">'
         '<div class="head"><h2 class="title">시험 장</h2></div>'
         '<p class="body">본문 문장입니다.</p><aside class="notes">노트</aside></section>')


def make_deck(tmp, cfg_extra=None, slide=None, extra_css=None):
    """임시 덱 폴더(deck.json + src/1장)를 만들고 경로를 돌려준다."""
    d = pathlib.Path(tmp)
    (d / 'src').mkdir(parents=True, exist_ok=True)
    (d / 'src' / '01.html').write_text(slide or SLIDE, encoding='utf-8')
    if extra_css:
        (d / 'src' / 'preset.css').write_text(extra_css, encoding='utf-8')
    cfg = {'title': '시험', 'output': 'out.html'}
    cfg.update(cfg_extra or {})
    (d / 'deck.json').write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')
    return d


def run_cli(script, *args):
    p = subprocess.run([sys.executable, str(script), *args],
                       capture_output=True, text=True, timeout=120)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


class TestClassicUnchanged(unittest.TestCase):
    """① classic 무변화 — family 미지정 덱은 계열 흔적이 렌더 계약에 새지 않는다."""

    def test_classic_build_has_no_family_attr(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_deck(tmp)
            title, name, study = bd.load_deck(d)
            out = d / name
            bd.build(title, sorted((d / 'src').glob('*.html')),
                     [d / 'src'], [S / 'assets/icons'], out, study=study)
            html = out.read_text(encoding='utf-8')
            root = re.search(r'<html\b[^>]*>', html)   # 문서 첫 <html …> 태그만 본다
            self.assertIsNotNone(root)
            self.assertNotIn('data-family', root.group(0),
                             'classic 덱 <html> 에 data-family 가 심어졌습니다')

    def test_family_rules_are_attribute_scoped(self):
        """families.css 의 선언 블록은 전부 [data-family="…"] 스코프 안이어야 한다 —
        속성 없는 classic 덱에는 어떤 규칙도 적용되지 않는다."""
        text = (CSS / 'families.css').read_text(encoding='utf-8')
        body = re.sub(r'/\*.*?\*/', '', text, flags=re.S)   # 주석을 빼고 셀렉터만 본다
        for sel in re.findall(r'([^{}]+)\{', body):
            sel = sel.strip()
            if not sel:
                continue
            self.assertIn('[data-family=', sel, f'스코프 밖 셀렉터: {sel}')

    def test_parts_base_is_token_driven(self):
        """parts.css 기본 정의는 레시피 토큰을 쓰고, 계열 변형은 [data-family] 스코프 안."""
        text = (CSS / 'parts.css').read_text(encoding='utf-8')
        for tok in ('--card-r', '--card-sh', '--card-bd', '--pill-r', '--tile-r',
                    '--node-r', '--win-r', '--arrow-w'):
            self.assertIn(f'var({tok}', text, f'{tok} 미사용')
        for sel in re.findall(r'([^{}]+)\{', re.sub(r'/\*.*?\*/', '', text, flags=re.S)):
            sel = sel.strip()
            if '[data-family' not in sel:
                self.assertRegex(sel, r'\.pt-', f'기본 정의는 .pt-* 여야 합니다: {sel}')

    def test_classic_pixel_sample(self):
        """기준선 PNG·playwright·PIL 이 있으면 대표 장 픽셀 diff.
        없으면 skip — 전 장 전수 비교는 리드 검증 스크립트가 담당한다."""
        try:
            from PIL import Image, ImageChops  # noqa: F401
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError:
            self.skipTest('playwright/PIL 없음 — 픽셀 샘플 생략')
        baseline = pathlib.Path('/Users/kwak/Projects/skills/edu-deck-skills/outputs/'
                                'dgate/20261123/design/baseline/base/s01.png')
        if not baseline.is_file():
            self.skipTest('기준선 PNG 없음 — 픽셀 샘플 생략')
        demo = ROOT / 'examples' / 'chart-edu-demo'
        if not (demo / 'deck.json').is_file():
            self.skipTest('비교용 예시 덱 없음')
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            d = pathlib.Path(tmp) / 'deck'
            shutil.copytree(demo, d)
            for f in d.glob('*.html'):
                f.unlink()
            title, name, study = bd.load_deck(d)
            out = d / name
            bd.build(title, sorted((d / 'src').glob('*.html')),
                     [S / 'assets/css', d / 'src'], [S / 'assets/icons', d / 'src'],
                     out, study=study)
            from playwright.sync_api import sync_playwright
            # 기준선은 scripts/capture_deck.py 방식(크롬 숨김 + deckGo(0,99) + viewport 캡처).
            HIDE = ("(() => { const s=document.createElement('style');"
                    " s.textContent='#progress,#dots,#counter,#help,.ed-toast,.ed-top,.ed-bot,"
                    ".ed-topbar,.ed-reader-nav,.ed-chrome-pop,.ed-help-modal{display:none!important}';"
                    " document.head.appendChild(s); })();")
            with sync_playwright() as pw:
                try:
                    browser = pw.chromium.launch(
                        executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
                except Exception:
                    browser = pw.chromium.launch(channel='chrome')
                pg = browser.new_page(viewport={'width': 1920, 'height': 1080})
                pg.goto(out.as_uri())
                pg.wait_for_timeout(1200)
                pg.evaluate(HIDE)
                pg.evaluate('window.deckGo(0, 99)')
                pg.wait_for_timeout(850)
                png = pathlib.Path(tmp) / 's01.png'
                pg.screenshot(path=str(png))
                browser.close()
            a = Image.open(baseline).convert('RGB')
            b = Image.open(png).convert('RGB')
            self.assertEqual(a.size, b.size)
            self.assertIsNone(ImageChops.difference(a, b).getbbox(),
                              'classic 표지가 기준선과 다릅니다')


class TestFamilyRoles(unittest.TestCase):
    """② 계열 역할 완결성 — 정의된 계열 블록은 15역할을 모두 덮는다."""

    def test_family_blocks_cover_semantic_roles(self):
        text = (CSS / 'families.css').read_text(encoding='utf-8')
        families, family_packs, family_darks, family_pack_darks = cd.parse_family_tokens(text)
        for fid, roles in families.items():
            self.assertIn(fid, tr.FAMILIES, f'families.css 에 모르는 계열: {fid}')
            missing = [k for k in cd.SEMANTIC_ROLES if k not in roles]
            self.assertFalse(missing, f'{fid} 블록에 역할 부족: {missing}')
        for fid, roles in family_packs.items():
            missing = [k for k in cd.SEMANTIC_ROLES if k not in roles]
            self.assertFalse(missing, f'{fid} 팩 스코프에 역할 부족: {missing}')
        for fid, roles in family_darks.items():
            self.assertIn(fid, families, f'{fid} 어두운 면인데 기본 블록이 없습니다')
            missing = [k for k in cd.SEMANTIC_ROLES if k not in roles]
            self.assertFalse(missing, f'{fid} 어두운 면에 역할 부족: {missing}')
        for fid, roles in family_pack_darks.items():
            self.assertIn(fid, families, f'{fid} 팩 어두운 면인데 기본 블록이 없습니다')
            missing = [k for k in cd.SEMANTIC_ROLES if k not in roles]
            self.assertFalse(missing, f'{fid} 팩 어두운 면에 역할 부족: {missing}')

    def test_three_family_blocks_exist(self):
        families, family_packs, family_darks, family_pack_darks = cd.parse_family_tokens(
            (CSS / 'families.css').read_text(encoding='utf-8'))
        for fid in ('studio', 'vivid', 'drawing'):
            self.assertIn(fid, families, f'{fid} 기본 블록 없음')
            self.assertIn(fid, family_packs, f'{fid} 팩 스코프 없음')
        self.assertIn('vivid', family_darks, 'vivid 어두운 면 블록 없음')
        self.assertIn('drawing', family_darks, 'drawing 어두운 면 블록 없음')
        self.assertIn('vivid', family_pack_darks, 'vivid 팩 어두운 면 블록 없음')


class TestParts(unittest.TestCase):
    """③ 부품 13종 + studio 변형 존재."""

    PARTS = ('pt-card', 'pt-pill', 'pt-tile', 'pt-win', 'pt-fig', 'pt-node', 'pt-note',
             'pt-waterfall', 'pt-table', 'pt-quiz', 'pt-check', 'pt-flow', 'pt-badge')

    def test_all_parts_defined(self):
        text = (CSS / 'parts.css').read_text(encoding='utf-8')
        for part in self.PARTS:
            self.assertRegex(text, rf'\.{part}\b', f'{part} 정의 없음')

    def test_studio_variants_exist(self):
        text = (CSS / 'parts.css').read_text(encoding='utf-8')
        scoped = set(re.findall(r'\[data-family="studio"\]\s*(\.\w[\w-]*)', text))
        for part in ('.pt-card', '.pt-pill', '.pt-tile', '.pt-win', '.pt-node'):
            self.assertIn(part, scoped, f'studio 변형 없음: {part}')

    def test_vivid_variants_exist(self):
        """P2a — vivid 변형: 메달·번호링·퀴즈·체크·흐름."""
        text = (CSS / 'parts.css').read_text(encoding='utf-8')
        scoped = set(re.findall(r'\[data-family="vivid"\]\s*(\.\w[\w-]*)', text))
        for part in ('.pt-pill', '.pt-tile', '.pt-medal', '.pt-numring',
                     '.pt-table', '.pt-quiz', '.pt-check', '.pt-arrow', '.pt-note'):
            self.assertIn(part, scoped, f'vivid 변형 없음: {part}')

    def test_drawing_variants_exist(self):
        """P2a — drawing 변형 + 이 계열 전용 부품 6종."""
        text = (CSS / 'parts.css').read_text(encoding='utf-8')
        scoped = set(re.findall(r'\[data-family="drawing"\]\s*(\.\w[\w-]*)', text))
        for part in ('.pt-card', '.pt-pill', '.pt-numring', '.pt-fig', '.pt-table',
                     '.pt-quiz', '.pt-check', '.pt-note', '.pt-arrow'):
            self.assertIn(part, scoped, f'drawing 변형 없음: {part}')
        for part in ('.pt-dim', '.pt-callout', '.pt-hangnum',
                     '.pt-stamp', '.pt-titleblock', '.pt-path'):
            self.assertIn(part, scoped, f'drawing 전용 부품 없음: {part}')

    def test_drawing_font_title_consumed(self):
        """--font-title 레시피는 drawing 계열이 .title/.big 에 실제로 소비한다."""
        text = (CSS / 'families.css').read_text(encoding='utf-8')
        m = re.search(r'\[data-family="drawing"\][^{]*\.title[^{]*\{([^}]*)\}', text)
        self.assertIsNotNone(m, 'drawing 제목 글꼴 소비 규칙이 없습니다')
        self.assertIn('var(--font-title)', m.group(1))
        self.assertIn('var(--title-weight)', m.group(1))


class TestBuildStamping(unittest.TestCase):
    """④ 빌드 스탬핑."""

    def test_family_deck_stamps_data_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_deck(tmp, {'family': 'studio'})
            title, name, study = bd.load_deck(d)
            out = d / name
            bd.build(title, sorted((d / 'src').glob('*.html')),
                     [d / 'src'], [S / 'assets/icons'], out,
                     study=study, family='studio')
            html = out.read_text(encoding='utf-8')
            root = re.search(r'<html\b[^>]*>', html)
            self.assertIsNotNone(root)
            self.assertIn('data-family="studio"', root.group(0))

    def test_load_deck_rejects_unknown_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_deck(tmp, {'family': 'neon'})
            with self.assertRaises(bd.BuildError):
                bd.load_deck(d)

    def test_drawing_deck_inlines_gowun_batang(self):
        """family=drawing 만 GowunBatang 등록용 @font-face 를 싣는다."""
        with tempfile.TemporaryDirectory() as tmp:
            d = make_deck(tmp, {'family': 'drawing'})
            title, name, study = bd.load_deck(d)
            out = d / name
            bd.build(title, sorted((d / 'src').glob('*.html')),
                     [d / 'src'], [S / 'assets/icons'], out,
                     study=study, family='drawing')
            html = out.read_text(encoding='utf-8')
            self.assertIn("font-family:'Gowun Batang'", html,
                          'drawing 덱에 GowunBatang @font-face 가 없습니다')
            # 등록용만 — 본문 스택을 덮는 font_css(family) 식 스택 재지정은 없어야 한다
            body = re.search(r"body,\s*\.slide,\s*\.pack\s*\{[^}]*font-family[^}]*\}", html)
            if body:
                self.assertNotIn('Gowun Batang', body.group(0),
                                 '본문 스택에 GowunBatang 이 들어갔습니다')

    def test_vivid_deck_has_no_gowun_batang(self):
        """vivid·studio·classic 덱에는 GowunBatang @font-face(글리프 인라인)가 없다.
        families.css 의 --font-title 토큰 문자열은 모든 덱에 실리므로 존재해도 된다 —
        계약은 글꼴 파일 자체(@font-face 등록)가 drawing 빌드에서만 싣는다는 것."""
        for fam in ('vivid', 'studio', None):
            with tempfile.TemporaryDirectory() as tmp:
                d = make_deck(tmp, {'family': fam} if fam else {})
                title, name, study = bd.load_deck(d)
                out = d / name
                bd.build(title, sorted((d / 'src').glob('*.html')),
                         [d / 'src'], [S / 'assets/icons'], out,
                         study=study, family=fam)
                html = out.read_text(encoding='utf-8')
                self.assertNotIn("@font-face{font-family:'Gowun Batang'", html,
                                 f'family={fam} 덱에 GowunBatang 글리프가 실렸습니다')


class TestFamilyThemeMutex(unittest.TestCase):
    """⑤ family+theme 오류 — load_deck 과 build 양쪽."""

    def test_load_deck_family_theme_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_deck(tmp, {'family': 'studio', 'theme': 'ocean'})
            with self.assertRaises(bd.BuildError):
                bd.load_deck(d)

    def test_build_family_theme_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_deck(tmp)
            srcs = sorted((d / 'src').glob('*.html'))
            with self.assertRaises(bd.BuildError):
                bd.build('t', srcs, [d / 'src'], [], d / 'o.html',
                         theme='ocean', family='studio')

    def test_family_resource_pack_allowed(self):
        """family+resource_pack 는 허용 — load_deck 단계에서 거부되지 않는다."""
        with tempfile.TemporaryDirectory() as tmp:
            d = make_deck(tmp, {'family': 'studio',
                                'resource_pack': {'design': 'lab', 'slides': []}})
            try:
                bd.load_deck(d)
            except bd.BuildError as e:
                if 'family' in str(e) or 'theme' in str(e):
                    self.fail(f'family+resource_pack 이 거부됐습니다: {e}')


class TestMatrixFamily(unittest.TestCase):
    """⑥ 매트릭스 family 행."""

    def _family_rows(self):
        base, packs = cd.parse_tokens(cd.TOKENS_CSS.read_text(encoding='utf-8'))
        families, family_packs, family_darks, family_pack_darks = cd.parse_family_tokens(
            cd.FAMILIES_CSS.read_text(encoding='utf-8'))
        return cd.build_matrix(base, packs, families=families, family_packs=family_packs,
                               family_darks=family_darks, family_pack_darks=family_pack_darks)

    def test_family_studio_rows_pass(self):
        fam_rows = [r for r in self._family_rows() if r['pack'] == 'family:studio']
        self.assertTrue(fam_rows, 'family:studio 행이 없습니다')
        bad = [r for r in fam_rows if not r['pass']]
        self.assertFalse(bad, f'family:studio 미달 행: {[(r["row"], r["ratio"]) for r in bad]}')

    def test_family_pack_scope_rows_exist(self):
        fam_pack_rows = [r for r in self._family_rows() if r['pack'] == 'family:studio.pack']
        self.assertTrue(fam_pack_rows, 'family:studio.pack 행이 없습니다')
        self.assertTrue(all(r['pass'] for r in fam_pack_rows))

    def test_family_env_rows_all_pass(self):
        """P2a — vivid·drawing 의 밝은/어두운/팩/팩어두운 환경 행이 전부 있고 통과다."""
        rows = self._family_rows()
        expected = ('family:vivid', 'family:vivid.dark', 'family:vivid.pack',
                    'family:vivid.pack.dark', 'family:drawing',
                    'family:drawing.dark', 'family:drawing.pack')
        for env in expected:
            env_rows = [r for r in rows if r['pack'] == env]
            self.assertTrue(env_rows, f'{env} 행이 없습니다')
            bad = [r for r in env_rows if not r['pass']]
            self.assertFalse(bad, f'{env} 미달 행: {[(r["row"], r["ratio"]) for r in bad]}')


class TestPresetGuard(unittest.TestCase):
    """⑦ classic 프리셋×studio 적용·조립 거부."""

    def test_apply_refused_on_family_deck(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_deck(tmp, {'family': 'studio'})
            code, out = run_cli(PRESET, '--apply', 'mono-swiss', '--deck', str(d))
            self.assertEqual(code, 2)
            self.assertFalse((d / 'src' / 'preset.css').exists(), '거부인데 파일이 생겼습니다')

    def test_apply_ok_on_classic_deck(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_deck(tmp)
            code, out = run_cli(PRESET, '--apply', 'mono-swiss', '--deck', str(d))
            self.assertEqual(code, 0, out)
            self.assertTrue((d / 'src' / 'preset.css').exists())

    def test_build_refuses_preset_marker_on_family_deck(self):
        preset_css = '/* preset.css — "모노 스위스" (mono-swiss) · preset-css 자동 생성물 */\n:root{--ink:#111}\n'
        with tempfile.TemporaryDirectory() as tmp:
            d = make_deck(tmp, {'family': 'studio'}, extra_css=preset_css)
            title, name, study = bd.load_deck(d)
            with self.assertRaises(bd.BuildError):
                bd.build(title, sorted((d / 'src').glob('*.html')),
                         [d / 'src'], [S / 'assets/icons'], d / name,
                         study=study, family='studio')

    def test_build_allows_preset_marker_on_classic_deck(self):
        preset_css = '/* preset.css — "모노 스위스" (mono-swiss) · preset-css 자동 생성물 */\n:root{--ink:#202b32}\n'
        with tempfile.TemporaryDirectory() as tmp:
            d = make_deck(tmp, extra_css=preset_css)
            title, name, study = bd.load_deck(d)
            bd.build(title, sorted((d / 'src').glob('*.html')),
                     [d / 'src'], [S / 'assets/icons'], d / name, study=study)


if __name__ == '__main__':
    unittest.main()
