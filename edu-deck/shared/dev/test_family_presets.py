"""Acceptance: family presets — 계열 팔레트 프리셋(색 전용 템플릿) P3.

[검사 항목]
- 기존 16종 classic 프리셋의 생성 CSS(deck·book) 가 바이트 단위로 무변경인지 잠금 해시로 본다.
- 신규 계열 프리셋(studio-*·vivid-*·drawing-*) 이 유효하고 family 필드가 FAMILIES 안이다.
- 계열 생성물: `preset-css` + `family: <id>` 표식 존재, 반경·그림자·.slide.dark 미포함(색 전용).
- cmd_apply(): 같은 family 허용 / 불일치 거부(classic×studio·studio×vivid·studio×classic·
  family 프리셋×book·family 프리셋×deck.json 없는 덱).
- style_preset.py --verify 가 classic+계열 전수를 검사해 통과한다.

[실행] cd edu-deck/shared && python3 -m unittest dev.test_family_presets -v
[주의] 저장소 안에는 아무것도 쓰지 않는다(임시 폴더 사용). 브라우저·node 는 필요 없다.
"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

S = pathlib.Path(__file__).resolve().parents[1]        # edu-deck/shared
PRESETS = S / 'presets'
SCRIPT = S / 'scripts' / 'style_preset.py'

sys.path.insert(0, str(S / 'scripts'))
import style_preset as sp  # noqa: E402

# 기존 16종 classic 프리셋 생성물의 바이트 잠금 — P3 작업 전 실제 출력의 sha256 앞 16자.
# 새 계열 프리셋 추가가 이 값들을 바꾸면 안 된다(무변경 계약 증거).
CLASSIC_LOCK = {
    'alpine-forest':   ('8ba60dfcaaa314e5', '3499d03f26bd0cc3'),
    'atelier-sand':    ('21626dd74930403d', 'f333c7d1c231534b'),
    'blueprint-grid':  ('b7b06f6a4905bf4b', '65f6114f0144be28'),
    'campus-chalk':    ('c2dc6cebd40b092e', '89b328c820f707e2'),
    'civic-ochre':     ('9cf74dfab3acc95d', '98f41cff89508a13'),
    'clinical-trust':  ('73087f5f90c60ee1', '3dd01e194fef8505'),
    'cyber-obsidian':  ('ec2114803f8d35f4', '3a47f7b65ec5921e'),
    'executive-navy':  ('d863bc471eb98ac0', '0223692e6e056873'),
    'fintech-emerald': ('b105c77749a78622', '8aa0ba03ce8561bf'),
    'hanji-warm':      ('b1ecd5003060ea39', 'e3e6e216c8f97012'),
    'legal-charcoal':  ('5d651f88dccd8090', 'dd11762cc81a61fb'),
    'mono-swiss':      ('dd6b7f60aa82f23e', '729727a74296f21e'),
    'museum-archive':  ('a85de19487b9b8ef', 'ba41fd176c6fc03f'),
    'nordic-slate':    ('92586cb2ac2bc639', '86720f9999b0fedf'),
    'pastel-studio':   ('bbacd014ac170e57', '66aa03f26740dcf1'),
    'seoul-editorial': ('767fe3480158cf3c', '5cbb5d029a01b57e'),
}
FAMILY_IDS = {
    'studio-terracotta': 'studio', 'studio-verdant': 'studio',
    'vivid-cobalt': 'vivid', 'vivid-orchid': 'vivid',
    'drawing-sepia': 'drawing', 'drawing-graphite': 'drawing',
}
# 계열 프리셋 생성물에 없어야 할 것 — 모양은 계열(families.css·parts.css) 소유다.
COLOR_ONLY_BANNED = ('--r-sm', '--r-md', '--r-lg', '--r1', '--r2', '--r3',
                     '--shadow', '--preset-', 'radius', '.slide.dark')


def run_cli(*args):
    """CLI 실행 — (returncode, stdout+stderr)."""
    p = subprocess.run([sys.executable, str(SCRIPT), *args],
                       capture_output=True, text=True, timeout=120)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def make_deck(tmp, family_marker='__absent__', name='deck'):
    """임시 덱 폴더 — family_marker=None 이면 family 없는 deck.json, 'studio' 등이면 그 값."""
    deck = pathlib.Path(tmp) / name
    (deck / 'src').mkdir(parents=True)
    if family_marker != '__absent__':
        cfg = {'family': family_marker} if family_marker else {'title': 'classic-deck'}
        (deck / 'deck.json').write_text(json.dumps(cfg), encoding='utf-8')
    return deck


class TestClassicPresetsUnchanged(unittest.TestCase):
    """기존 16종의 생성 출력이 바이트 단위로 무변경인지 잠금 해시로 본다."""

    @classmethod
    def setUpClass(cls):
        cls.presets = sp.load_all(PRESETS)

    def test_classic_set_is_exactly_16(self):
        classic = {pid for pid, p in self.presets.items() if not p.get('family')}
        self.assertEqual(set(CLASSIC_LOCK), classic,
                         f'classic 집합이 바뀌었습니다: {sorted(classic ^ set(CLASSIC_LOCK))}')

    def test_deck_css_byte_locked(self):
        for pid, (deck_hash, _) in CLASSIC_LOCK.items():
            with self.subTest(preset=pid):
                got = hashlib.sha256(sp.deck_css(self.presets[pid]).encode()).hexdigest()[:16]
                self.assertEqual(deck_hash, got, f'{pid}: deck_css 출력이 바뀌었습니다')

    def test_book_css_byte_locked(self):
        for pid, (_, book_hash) in CLASSIC_LOCK.items():
            with self.subTest(preset=pid):
                got = hashlib.sha256(sp.book_css(self.presets[pid]).encode()).hexdigest()[:16]
                self.assertEqual(book_hash, got, f'{pid}: book_css 출력이 바뀌었습니다')

    def test_classic_output_has_no_family_marker(self):
        for pid, p in self.presets.items():
            if p.get('family'):
                continue
            with self.subTest(preset=pid):
                self.assertNotIn('family:', sp.deck_css(p), f'{pid}: family 표식이 섞였습니다')


class TestFamilyPresetSchema(unittest.TestCase):
    """신규 계열 프리셋이 계열 스키마에 맞는다."""

    @classmethod
    def setUpClass(cls):
        cls.presets = sp.load_all(PRESETS)
        cls.family = {pid: p for pid, p in cls.presets.items() if p.get('family')}

    def test_family_presets_exist_per_family(self):
        self.assertEqual(set(FAMILY_IDS), set(self.family),
                         f'계열 프리셋이 빠졌습니다: {sorted(set(FAMILY_IDS) - set(self.family))}')
        per_family = {f: 0 for f in sp.FAMILIES}
        for p in self.family.values():
            per_family[p['family']] += 1
        for fid, n in per_family.items():
            self.assertGreaterEqual(n, 1, f'{fid} 계열 프리셋이 없습니다')
            self.assertLessEqual(n, 2, f'{fid} 계열 프리셋이 2종을 넘습니다')

    def test_family_value_is_known(self):
        for pid, p in self.family.items():
            with self.subTest(preset=pid):
                self.assertIn(p['family'], sp.FAMILIES)
                self.assertEqual(FAMILY_IDS[pid], p['family'])
                self.assertEqual(FAMILY_IDS[pid], sp.preset_family(p))

    def test_family_presets_validate(self):
        for pid, p in self.family.items():
            with self.subTest(preset=pid):
                self.assertEqual([], sp.validate(p))

    def test_family_schema_relaxes_theme_and_shape(self):
        """계열 프리셋은 recommended_theme·반경·규칙을 요구하지 않는다(색 전용 계약)."""
        for pid, p in self.family.items():
            with self.subTest(preset=pid):
                self.assertNotIn('recommended_theme', p,
                                 f'{pid}: 계열 프리셋에 classic 전용 필드가 있습니다')
                self.assertFalse(sp.TEXT_KEYS and not str(p.get('intent', '')).strip())
                self.assertGreaterEqual(len(str(p['intent'])), 40)

    def test_family_rejects_bad_family_value(self):
        bad = dict(self.presets['studio-terracotta'])
        bad['family'] = 'neon'
        self.assertTrue(any('family' in m for m in sp.validate(bad)))

    def test_classic_presets_still_require_theme(self):
        p = self.presets['seoul-editorial']
        self.assertIsNone(p.get('family'))
        self.assertEqual('classic', sp.preset_family(p))
        self.assertIn(p['recommended_theme'], sp.THEMES)


class TestFamilyCssOutput(unittest.TestCase):
    """계열 생성물은 preset-css + family 표식을 남기고 색 역할만 덮어쓴다."""

    @classmethod
    def setUpClass(cls):
        cls.presets = sp.load_all(PRESETS)

    def test_family_marker_and_color_only(self):
        for pid, p in self.presets.items():
            if not p.get('family'):
                continue
            with self.subTest(preset=pid):
                css = sp.family_css(p)
                self.assertEqual(css.count('{'), css.count('}'), '중괄호 균형이 깨졌습니다')
                self.assertIn(sp.MARKER, css)
                self.assertIn(f"family: {p['family']}", css, 'family 표식이 없습니다')
                for banned in COLOR_ONLY_BANNED:
                    self.assertNotIn(banned, css, f'{pid}: 색 전용 계약 위반 — {banned}')
                # 색 역할은 모두 들어간다
                for token in ('--bg', '--bg-2', '--paper', '--ink', '--soft', '--mut', '--line',
                              '--blue', '--blue-text', '--blue-soft', '--accent',
                              '--accent-text', '--accent-soft', '--night', '--night-2',
                              '--night-line', '--on-night', '--on-night-2'):
                    self.assertIn(token + ':', css, f'{token} 이 없습니다')
                self.assertIn(':root{', css)
                self.assertIn('.slide{', css)

    def test_family_css_maps_values(self):
        p = self.presets['studio-terracotta']
        css = sp.family_css(p)
        for yaml_key, css_name in (('paper', '--bg'), ('surface', '--paper'),
                                   ('accent', '--accent'), ('night', '--night')):
            self.assertIn(f"{css_name}:{p['tokens'][yaml_key].lower()}", css)

    def test_family_css_deterministic(self):
        p = self.presets['vivid-cobalt']
        self.assertEqual(sp.family_css(p), sp.family_css(p))


class TestApplyFamilyMatching(unittest.TestCase):
    """cmd_apply() 가 프리셋 계열과 덱 family 의 일치를 적용 전에 검사한다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def _apply(self, preset_id, family_marker):
        self._n += 1
        deck = make_deck(self.tmp.name, family_marker, name=f'deck{self._n}')
        return run_cli('--apply', preset_id, '--deck', str(deck)) + (deck,)

    def test_match_is_allowed(self):
        for pid, fid in FAMILY_IDS.items():
            with self.subTest(preset=pid):
                code, out, deck = self._apply(pid, fid)
                self.assertEqual(0, code, out)
                css = (deck / 'src' / 'preset.css').read_text(encoding='utf-8')
                self.assertIn(f'family: {fid}', css)
                for banned in COLOR_ONLY_BANNED:
                    self.assertNotIn(banned, css)

    def test_family_preset_on_other_family_rejected(self):
        pairs = [('studio-terracotta', 'vivid'), ('vivid-cobalt', 'drawing'),
                 ('drawing-sepia', 'studio')]
        for pid, wrong_family in pairs:
            with self.subTest(preset=pid, deck_family=wrong_family):
                code, out, deck = self._apply(pid, wrong_family)
                self.assertEqual(2, code, out)
                self.assertFalse((deck / 'src' / 'preset.css').exists(), '거부인데 파일을 썼습니다')

    def test_family_preset_on_classic_deck_rejected(self):
        code, out, deck = self._apply('studio-terracotta', None)
        self.assertEqual(2, code, out)
        self.assertFalse((deck / 'src' / 'preset.css').exists())

    def test_family_preset_on_missing_deckjson_rejected(self):
        code, out, deck = self._apply('drawing-sepia', '__absent__')
        self.assertEqual(2, code, out)
        self.assertFalse((deck / 'src' / 'preset.css').exists())

    def test_classic_preset_on_family_deck_rejected(self):
        for fid in ('studio', 'vivid', 'drawing'):
            with self.subTest(deck_family=fid):
                code, out, deck = self._apply('seoul-editorial', fid)
                self.assertEqual(2, code, out)
                self.assertIn('classic', out)
                self.assertFalse((deck / 'src' / 'preset.css').exists())

    def test_classic_preset_on_classic_deck_still_allowed(self):
        code, out, deck = self._apply('seoul-editorial', None)
        self.assertEqual(0, code, out)
        css = (deck / 'src' / 'preset.css').read_text(encoding='utf-8')
        self.assertIn(sp.MARKER, css)
        self.assertIn('.slide.dark', css, 'classic 생성물의 밤 면 규칙이 빠졌습니다')

    def test_family_preset_on_book_rejected(self):
        book = pathlib.Path(self.tmp.name) / 'book'
        (book / 'pages').mkdir(parents=True)
        code, out = run_cli('--apply', 'vivid-orchid', '--book', str(book))
        self.assertEqual(2, code, out)
        self.assertFalse((book / 'pages' / '00-preset.css').exists())


class TestVerifyCoversAll(unittest.TestCase):
    def test_verify_passes_and_mentions_family_ids(self):
        code, out = run_cli('--verify')
        self.assertEqual(0, code, out)
        self.assertIn('PASS', out)
        for pid in FAMILY_IDS:
            self.assertIn(pid, out, f'--verify 가 {pid} 를 검사하지 않았습니다')


if __name__ == '__main__':
    unittest.main()
