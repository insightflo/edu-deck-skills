#!/usr/bin/env python3
"""flint-theme.json 계약 시험 — 스키마·토큰값 일치·텍스트 대비·허용목록 자기일관성.

flint 설치와 무관하게 돌리는 단위 시험이다(실 렌더 통합은 test_flint_model.py 의 skip 케이스).
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
THEME = ROOT / 'consulting-deck' / 'charts' / 'flint-theme.json'
CSS = ROOT / 'consulting-deck' / 'assets' / 'consult.css'
ENV = ROOT / 'consulting-deck' / 'charts' / 'flint_env.py'

HEX_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def css_tokens(text, selector):
    """`.slide.consult{ … }` 블록 안 --토큰: hex 맵."""
    m = re.search(re.escape(selector) + r'[^{]*\{(.*?)\}', text, re.S)
    return {k: v for k, v in re.findall(r'(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})', m.group(1))} if m else {}


def lum(hexc):
    c = [int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def all_hexes(obj):
    if isinstance(obj, str):
        return [obj] if HEX_RE.match(obj) else []
    if isinstance(obj, dict):
        return [h for v in obj.values() for h in all_hexes(v)]
    if isinstance(obj, list):
        return [h for v in obj for h in all_hexes(v)]
    return []


class ThemeFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.theme = json.loads(THEME.read_text(encoding='utf-8'))
        cls.css = CSS.read_text(encoding='utf-8')
        cls.presets = cls.theme['presets']

    def test_presets_exist_and_extend(self):
        self.assertEqual(set(self.presets), {'consult', 'consult-tech'})
        for k, p in self.presets.items():
            self.assertEqual(p.get('extends'), 'mckinsey', k)
            self.assertIn('ink', p)
            self.assertIn('type', p)

    def test_text_and_surface_contrast_45(self):
        for k, p in self.presets.items():
            canvas = p['ink']['surface']['canvas']
            for role, hx in p['ink']['text'].items():
                self.assertGreaterEqual(ratio(hx, canvas), 4.5, f'{k} text.{role} {hx} vs {canvas}')

    def test_ink_matches_consult_css_tokens(self):
        """테마 잉크는 consult.css 토큰값 그대로 — SSOT 우발 이탈 차단."""
        base = css_tokens(self.css, '.slide.consult')
        tech = css_tokens(self.css, '.slide.consult-tech')
        c, t = self.presets['consult'], self.presets['consult-tech']
        self.assertEqual(c['ink']['text']['primary'], base['--ink'])
        self.assertEqual(c['ink']['text']['secondary'], base['--soft'])
        self.assertEqual(c['ink']['surface']['canvas'], base['--paper'])
        self.assertEqual(c['ink']['series']['single'], base['--accent'])
        self.assertEqual(c['ink']['structure']['grid'], base['--grid'])
        self.assertEqual(t['ink']['text']['primary'], tech['--ink'])
        self.assertEqual(t['ink']['surface']['canvas'], tech['--paper'])
        self.assertEqual(t['ink']['series']['single'], tech['--accent'])

    def test_allowlist_covers_theme_hexes(self):
        """테마가 선언한 모든 hex는 allowlist 안 — 누수 검사가 자기 발등을 찌지 않게."""
        for k, p in self.presets.items():
            allow = {h.lower() for h in self.theme['allowlist'][k]}
            declared = {h.lower() for h in all_hexes(p)}
            stray = declared - allow
            self.assertFalse(stray, f'{k} 테마 선언색이 allowlist 밖: {sorted(stray)}')

    def test_allowlist_format(self):
        for k, lst in self.theme['allowlist'].items():
            for h in lst:
                self.assertRegex(h, HEX_RE, f'{k} 잘못된 hex: {h}')

    def test_pretendard_in_type_roles(self):
        """Pretendard 계약은 테마 type 주입으로 지킨다 — headline은 두 프리셋 모두 Pretendard."""
        for k, p in self.presets.items():
            fams = [r.get('family', '') for r in p['type'].values() if isinstance(r, dict)]
            self.assertTrue(any('Pretendard' in f for f in fams), f'{k} Pretendard 가족 없음')
            self.assertIn('Pretendard', p['type']['headline']['family'], k)

    def test_env_pin_versions(self):
        src = ENV.read_text(encoding='utf-8')
        for pkg, ver in {'flint-chart': '1.0.1', 'vega': '6.4.0', 'vega-lite': '6.5.0'}.items():
            self.assertIn(f'"{pkg}": "{ver}"', src, f'{pkg} 핀 버전이 flint_env.py에 없다')


if __name__ == '__main__':
    unittest.main()
