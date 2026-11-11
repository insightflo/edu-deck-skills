"""Acceptance: style presets — 팔레트 16종 · WCAG 게이트 · --apply 산출 CSS.

[검사 항목]
- 구성: 프리셋이 16종 이상 있고, 요구된 16개 id 가 모두 있다. id = 파일명.
- 중복 금지: workspace/absorb/style-presets·style-theme 의 파일명·내용과 겹치지 않는다
  (해당 폴더가 없으면 skip — 저장소 밖 작업물이므로 있을 때만 본다).
- 계약: 필수 키·hex 형식·radius px·추천 테마 화이트리스트·min-font 범위.
- 대비: WCAG 2.1 상대휘도로 a~f 16쌍을 전수 계산해 기준(4.5 / 잉크·밤 7.0) 이상인지 본다.
  테스트가 자체 공식을 다시 구현해 검증기(style_preset)와 독립적으로 계산한다.
- 산출물: --apply 가 만든 CSS 가 괄호 균형을 이루고, 필수 토큰·:root·.slide·.slide.dark 를
  담고 있으며, 외부 자원(url·@import·http)을 부르지 않는다.
- 안전: 표식 없는 기존 파일은 거부(exit 2), --force 로만 덮어쓴다. 같은 입력 2회 → 같은 바이트.
- 책: --book 은 pages/00-preset.css 를 만들고 --navy/--stage 브리지를 담는다.

[실행] cd edu-deck/shared && python3 -m unittest dev.test_style_presets -v
[주의] 저장소 안에는 아무것도 쓰지 않는다(임시 폴더 사용). 브라우저·node 는 필요 없다.
"""
import hashlib
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

S = pathlib.Path(__file__).resolve().parents[1]        # edu-deck/shared
ROOT = S.parents[1]                                    # 저장소 루트
PRESETS = S / 'presets'
SCRIPT = S / 'scripts' / 'style_preset.py'
ABSORB = ROOT / 'workspace' / 'absorb'

sys.path.insert(0, str(S / 'scripts'))
import style_preset as sp  # noqa: E402  (경로 설정 뒤에 읽는다)

REQUIRED_IDS = {
    'seoul-editorial', 'hanji-warm', 'nordic-slate', 'alpine-forest', 'blueprint-grid',
    'executive-navy', 'clinical-trust', 'atelier-sand', 'campus-chalk', 'cyber-obsidian',
    'legal-charcoal', 'civic-ochre', 'pastel-studio', 'mono-swiss', 'fintech-emerald',
    'museum-archive',
}
DECK_TOKENS = ('--bg', '--bg-2', '--paper', '--ink', '--soft', '--mut', '--line',
               '--blue', '--blue-text', '--blue-soft', '--accent', '--accent-text',
               '--accent-soft', '--r-sm', '--r-md', '--r-lg')


def run_cli(*args, cwd=None):
    """CLI 실행 — (returncode, stdout+stderr). argparse 오류까지 한 줄로 모은다."""
    p = subprocess.run([sys.executable, str(SCRIPT), *args],
                       capture_output=True, text=True, timeout=120, cwd=cwd)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


class TestPresetFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.presets = sp.load_all(PRESETS)

    def test_at_least_required_ids(self):
        self.assertGreaterEqual(len(self.presets), 16, '프리셋이 16종 미만입니다')
        missing = REQUIRED_IDS - set(self.presets)
        self.assertFalse(missing, f'요구된 프리셋이 없습니다: {sorted(missing)}')

    def test_id_matches_filename(self):
        for stem, p in self.presets.items():
            self.assertEqual(stem, p['id'], f'{stem}: id 와 파일명이 다릅니다')

    def test_required_keys_and_formats(self):
        for pid, p in self.presets.items():
            with self.subTest(preset=pid):
                self.assertEqual([], sp.validate(p))

    def test_intent_use_avoid_are_sentences(self):
        """의도·용도·회피는 사람이 읽는 문장이어야 한다 — 세 단어짜리 태그로 끝내지 않는다."""
        for pid, p in self.presets.items():
            with self.subTest(preset=pid):
                self.assertGreaterEqual(len(str(p['intent'])), 40, 'intent 가 너무 짧습니다')
                self.assertGreaterEqual(len(str(p['use'])), 15, 'use 가 너무 짧습니다')
                self.assertGreaterEqual(len(str(p['avoid'])), 15, 'avoid 가 너무 짧습니다')
                self.assertIn('다', str(p['intent']), 'intent 는 완결된 문장이어야 합니다')

    def test_recommended_theme_is_known(self):
        known = set(sp.THEMES)
        for pid, p in self.presets.items():
            with self.subTest(preset=pid):
                self.assertIn(p['recommended_theme'], known)


class TestContrastGates(unittest.TestCase):
    """검증기와 별개로 공식을 다시 구현해 16쌍을 전수 채점한다(자기 검증 금지)."""

    @staticmethod
    def _lum(hex_color):
        out = []
        for i in (1, 3, 5):
            c = int(hex_color[i:i + 2], 16) / 255
            out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]

    def ratio(self, a, b):
        la, lb = sorted((self._lum(a), self._lum(b)), reverse=True)
        return (la + 0.05) / (lb + 0.05)

    def test_all_six_gate_families(self):
        presets = sp.load_all(PRESETS)
        self.assertTrue(presets, '프리셋을 읽지 못했습니다')
        cases = [
            ('a', 'ink', 'paper', 7.0), ('a', 'ink', 'surface', 7.0),
            ('b', 'ink-2', 'paper', 4.5), ('b', 'ink-2', 'surface', 4.5),
            ('c', 'ink-3', 'paper', 4.5), ('c', 'ink-3', 'surface', 4.5),
            ('d', 'brand-text', 'paper', 4.5), ('d', 'brand-text', 'surface', 4.5),
            ('d', 'brand-text', 'brand-tint', 4.5),
            ('e', 'accent-text', 'paper', 4.5), ('e', 'accent-text', 'surface', 4.5),
            ('e', 'accent-text', 'accent-tint', 4.5),
            ('f', 'on-night', 'night', 7.0), ('f', 'on-night', 'night-2', 4.5),
            ('f', 'on-night-2', 'night', 4.5), ('f', 'on-night-2', 'night-2', 4.5),
        ]
        for pid, p in presets.items():
            t = p['tokens']
            for label, fg, bg, need in cases:
                with self.subTest(preset=pid, gate=label, pair=f'{fg}/{bg}'):
                    got = self.ratio(t[fg], t[bg])
                    self.assertGreaterEqual(
                        round(got + 1e-9, 4), need,
                        f'{pid} {label} {fg} vs {bg} = {got:.2f} < {need}')

    def test_verify_cli_passes(self):
        code, out = run_cli('--verify')
        self.assertEqual(0, code, out)
        self.assertIn('PASS', out)

    def test_list_cli_shows_every_preset(self):
        code, out = run_cli('--list')
        self.assertEqual(0, code, out)
        for pid in REQUIRED_IDS:
            self.assertIn(pid, out)


class TestNoCopyFromAbsorbed(unittest.TestCase):
    """흡수 작업물과 파일명·내용이 겹치지 않는다 — 라이선스 경계의 자동 증거."""

    def _digests(self, folder):
        return {hashlib.sha256(p.read_bytes()).hexdigest(): p.name
                for p in folder.rglob('*') if p.is_file()}

    def test_no_same_filename(self):
        for folder in (ABSORB / 'style-presets', ABSORB / 'style-theme'):
            if not folder.is_dir():
                self.skipTest(f'{folder} 가 없습니다(저장소 밖 작업물)')
            foreign = {p.stem.lower() for p in folder.glob('*.yaml')}
            mine = {p.stem.lower() for p in PRESETS.glob('*.yaml')}
            self.assertFalse(mine & foreign, f'겹치는 파일명: {sorted(mine & foreign)}')

    def test_no_identical_content(self):
        ours = self._digests(PRESETS)
        for folder in (ABSORB / 'style-presets', ABSORB / 'style-theme'):
            if not folder.is_dir():
                self.skipTest(f'{folder} 가 없습니다(저장소 밖 작업물)')
            theirs = self._digests(folder)
            same = {ours[h] for h in set(ours) & set(theirs)}
            self.assertFalse(same, f'복제된 파일: {sorted(same)}')

    def test_no_foreign_hex_bundle(self):
        """한 프리셋의 hex 6개 이상이 흡수 파일 하나와 그대로 겹치면 복제로 본다."""
        for folder in (ABSORB / 'style-presets', ABSORB / 'style-theme'):
            if not folder.is_dir():
                self.skipTest(f'{folder} 가 없습니다(저장소 외부 작업물)')
            foreign = []
            for p in folder.glob('*.yaml'):
                text = p.read_text(encoding='utf-8', errors='replace').lower()
                foreign.append((p.name, set(sp.re.findall(r'#[0-9a-f]{6}', text))))
            for _, mine in sp.load_all(PRESETS).items():
                myset = {v.lower() for k, v in mine['tokens'].items() if str(v).startswith('#')}
                for name, theirset in foreign:
                    shared = myset & theirset
                    self.assertLess(len(shared), 6, f'{mine["id"]} ↔ {name} 색 {len(shared)}개 중복')


class TestApplyDeck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preset = sp.load_all(PRESETS)['seoul-editorial']

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.deck = pathlib.Path(self.tmp.name) / 'deck'
        (self.deck / 'src').mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_generated_css_contract(self):
        code, out = run_cli('--apply', 'seoul-editorial', '--deck', str(self.deck))
        self.assertEqual(0, code, out)
        css = (self.deck / 'src' / 'preset.css').read_text(encoding='utf-8')
        self.assertEqual(css.count('{'), css.count('}'), '중괄호 균형이 깨졌습니다')
        for token in DECK_TOKENS + ('--night', '--on-night', '--night-2', '--night-line',
                                    '--on-night-2', '--preset-min-font'):
            self.assertIn(token + ':', css, f'{token} 이 없습니다')
        self.assertIn(':root{', css)
        self.assertIn('.slide{', css)
        self.assertIn('.slide.dark', css)
        self.assertIn(sp.MARKER, css)
        self.assertEqual(self.preset['tokens']['paper'].lower(), self._value(css, '--bg'))
        self.assertEqual(self.preset['tokens']['surface'].lower(), self._value(css, '--paper'))
        self.assertEqual(self.preset['tokens']['accent'].lower(), self._value(css, '--accent'))
        self.assertEqual(self.preset['tokens']['radius-lg'], self._value(css, '--r-lg'))

    @staticmethod
    def _value(css, name):
        m = re.search(re.escape(name) + r':([^;}]+)', css)
        return m.group(1).strip() if m else None

    def test_no_external_resources(self):
        run_cli('--apply', 'mono-swiss', '--deck', str(self.deck))
        css = (self.deck / 'src' / 'preset.css').read_text(encoding='utf-8')
        for bad in ('url(', '@import', 'http://', 'https://', '<script'):
            self.assertNotIn(bad, css, f'외부 자원 참조: {bad}')

    def test_reapply_is_byte_identical(self):
        run_cli('--apply', 'seoul-editorial', '--deck', str(self.deck))
        first = (self.deck / 'src' / 'preset.css').read_bytes()
        code, out = run_cli('--apply', 'seoul-editorial', '--deck', str(self.deck))
        self.assertEqual(0, code, out)
        self.assertEqual(first, (self.deck / 'src' / 'preset.css').read_bytes())

    def test_handwritten_file_is_protected(self):
        target = self.deck / 'src' / 'preset.css'
        target.write_text('/* 손으로 쓴 파일 */\n.slide{--bg:#fff}\n', encoding='utf-8')
        code, out = run_cli('--apply', 'seoul-editorial', '--deck', str(self.deck))
        self.assertEqual(2, code, out)
        self.assertIn('--force', out)
        self.assertIn('손으로 쓴 파일', target.read_text(encoding='utf-8'), '덮어썼습니다')
        code, out = run_cli('--apply', 'seoul-editorial', '--deck', str(self.deck), '--force')
        self.assertEqual(0, code, out)
        self.assertIn(sp.MARKER, target.read_text(encoding='utf-8'))

    def test_unknown_id_fails_cleanly(self):
        code, out = run_cli('--apply', 'no-such-preset', '--deck', str(self.deck))
        self.assertEqual(2, code, out)
        self.assertFalse((self.deck / 'src' / 'preset.css').exists())

    def test_requires_exactly_one_target(self):
        code, out = run_cli('--apply', 'seoul-editorial')
        self.assertNotEqual(0, code)
        self.assertIn('--deck', out)


class TestApplyBook(unittest.TestCase):
    def test_book_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = pathlib.Path(tmp) / 'book'
            (book / 'pages').mkdir(parents=True)
            code, out = run_cli('--apply', 'museum-archive', '--book', str(book))
            self.assertEqual(0, code, out)
            css = (book / 'pages' / '00-preset.css').read_text(encoding='utf-8')
            self.assertEqual(css.count('{'), css.count('}'))
            preset = sp.load_all(PRESETS)['museum-archive']
            for token in ('--ink', '--sub', '--mute', '--line', '--bg', '--paper',
                          '--tint', '--accent', '--accent2', '--navy', '--mint', '--stage'):
                self.assertIn(token + ':', css, f'{token} 이 없습니다')
            self.assertIn(preset['tokens']['ink'].lower(), css)
            self.assertIn('pages', out + ' ')  # 포함 방법 안내가 출력된다
            self.assertNotIn('url(', css)


class TestParser(unittest.TestCase):
    def test_quoted_hash_survives(self):
        data = sp.load_yaml_text('tokens:\n  paper: "#fbfaf6"  # 바닥\nrules:\n  no-shadow: true\n')
        self.assertEqual('#fbfaf6', data['tokens']['paper'])
        self.assertIs(True, data['rules']['no-shadow'])

    def test_bool_and_int(self):
        data = sp.load_yaml_text('rules:\n  hairline: false\n  min-font: 20\n')
        self.assertIs(False, data['rules']['hairline'])
        self.assertEqual(20, data['rules']['min-font'])

    def test_bad_indent_raises(self):
        with self.assertRaises(ValueError):
            sp.load_yaml_text('  paper: "#ffffff"\n')


if __name__ == '__main__':
    unittest.main()
