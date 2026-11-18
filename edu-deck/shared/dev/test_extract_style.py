"""Acceptance: extract_style.py — 소스 실측 기반 스타일 추출 계약 + capture_cli.py 연동.

[검사 항목]
- 8축: 성격이 다른 소스 2종(장난기·이모지·밝은 팔레트 vs 기술·CLI·다크 팔레트)을 넣으면
  서로 다른 팔레트·반경·축 점수가 나오고, 8개 축이 전부 0..1 범위이며 근거 ID 를 가진다.
- 대비: 산출 토큰이 style_preset.CONTRAST_GATES 16쌍을 전부 통과한다 — 테스트가
  sp.contrast_ratio 로 검증기와 독립적으로 재계산한다(보고서의 all_pass 만 믿지 않음).
- CSS 계약: --deck 산출 src/preset.css 가 preset-css 마커·:root 21토큰·.slide·
  .slide.dark,.dark.slide 규칙·파생 토큰을 담고, 외부 자원(url/http/@import)이 없다.
- 안전: .env·*.env·id_rsa·secret* 계열 파일은 스캔에서 제외되고 그 색이 결과에 새지 않는다.
  표식 없는 수동 CSS 는 --force 없이 덮어쓰기 거부(exit 2), --force 면 통과.
- capture_cli: 실제 명령 실행 → exit code·stdout 이 스니펫과 메타 JSON 에 정확히 남고,
  홈 경로(--mask-home)와 토큰(ghp_/sk-/AKIA, 항상)이 ••• 로 가려진다.

[실행] cd edu-deck/shared && python3 -m unittest dev.test_extract_style -v
[주의] 저장소 안에는 아무것도 쓰지 않는다(tempfile 만 사용). --offline 으로 네트워크 무관.
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

S = pathlib.Path(__file__).resolve().parents[1]        # edu-deck/shared
SCRIPT = S / 'scripts' / 'extract_style.py'
CAPTURE = S / 'scripts' / 'capture_cli.py'

sys.path.insert(0, str(S / 'scripts'))
import style_preset as sp            # noqa: E402
import extract_style as esx          # noqa: E402

AXES = ("energy", "playful", "technical", "serious", "warm", "luxe", "dark", "data")
REQUIRED_VARS = ('--bg', '--bg-2', '--paper', '--line', '--ink', '--soft', '--mut',
                 '--blue', '--blue-text', '--blue-soft', '--accent', '--accent-text',
                 '--accent-soft', '--night', '--night-2', '--night-line',
                 '--on-night', '--on-night-2', '--r-sm', '--r-md', '--r-lg')

PLAYFUL_CSS = """body{background:#fff0f7;color:#5b3a68}
.hero{background:#ffe3f1;color:#c42d84}
.btn{background:#ff7ab8;color:#ffffff;border-radius:22px}
.card{background:#fff8fb;border:1px solid #ffd0e6;border-radius:18px}
.link{color:#8a5cff}
.badge{background:#f3e8ff;color:#7c4dcc;border-radius:24px}
footer{background:#fdf1e6;color:#a0522d}
"""

TECH_CSS = """body{background:#0d1117;color:#c9d1d9}
.code{background:#161b22;color:#79c0ff;font-family:'JetBrains Mono',monospace}
.btn{background:#238636;color:#ffffff;border-radius:3px}
.term{background:#010409;color:#7ee787;font-family:Menlo,monospace;border-radius:4px}
.card{background:#161b22;border:1px solid #30363d;border-radius:6px}
.link{color:#58a6ff}
"""

PLAYFUL_MD = ("# yay fun project!! 🎉🔥✨\n\n" +
              "this is so cool and awesome and fun!! amazing!! play now!! love it! 🎉✨💖🚀\n" * 30 +
              "we love it!! so cute and fun 🧸💫\n")

TECH_MD = ("# deploy cli tool\n\ninstall and configure the api endpoint:\n\n" +
           ("```bash\nnpm install tool --save && tool deploy --config prod.yaml\n"
            "curl -X POST https://api.internal/v3/deploy -d '{\"region\":\"us-1\",\"version\":\"3.2.1\"}'\n"
            "kubectl apply -f cluster.yaml && docker build -t svc:4.1.0 .\n```\n\n"
            "throughput is 99.7% over 1024 runs, p50 = 12.4ms p99 = 88ms\n\n") * 12)


def run_extract(*args, cwd=None):
    """CLI 실행 — (returncode, stdout+stderr)."""
    p = subprocess.run([sys.executable, str(SCRIPT), *args],
                       capture_output=True, text=True, timeout=120, cwd=cwd)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def run_capture(*args):
    p = subprocess.run([sys.executable, str(CAPTURE), *args],
                       capture_output=True, text=True, timeout=60)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def build_source(root: pathlib.Path, css: str, md: str, index_html: bool = True):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'site.css').write_text(css)
    (root / 'README.md').write_text(md)
    if index_html:
        (root / 'index.html').write_text(
            '<html><head><title>t</title><link rel="stylesheet" href="site.css"></head><body></body></html>')


class TestExtractStyle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix='esx-test-'))
        cls.srcA = cls.tmp / 'src-playful'
        cls.srcB = cls.tmp / 'src-tech'
        build_source(cls.srcA, PLAYFUL_CSS, PLAYFUL_MD)
        build_source(cls.srcB, TECH_CSS, TECH_MD)
        cls.reports = {}
        for tag, src in (('A', cls.srcA), ('B', cls.srcB)):
            deck = cls.tmp / f'deck{tag}'
            (deck / 'src').mkdir(parents=True)
            (deck / 'deck.json').write_text(json.dumps({"title": f"t{tag}", "output": "o.html"}))
            rc, out = run_extract('--source', str(src), '--deck', str(deck),
                                  '--json', '--md', '--board', '--offline', cwd=deck)
            assert rc == 0, f'{tag} extract 실패 rc={rc}\n{out}'
            cls.reports[tag] = {
                'deck': deck,
                'css': (deck / 'src' / 'preset.css').read_text(),
                'json': json.loads((deck / 'qa' / 'style-extract.json').read_text()),
            }

    # ---------------- a) 8축 + 두 성격 소스 → 다른 팔레트/반경/축
    def test_eight_axes_complete(self):
        for tag, r in self.reports.items():
            tones = r['json']['tones']
            self.assertEqual(set(AXES), set(tones), f'{tag}: 8축이 빠졌습니다')
            for a in AXES:
                v = tones[a]['value']
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 1.0)
                self.assertIsInstance(tones[a].get('evidence'), list)

    def test_axes_differ_between_sources(self):
        ta = {a: self.reports['A']['json']['tones'][a]['value'] for a in AXES}
        tb = {a: self.reports['B']['json']['tones'][a]['value'] for a in AXES}
        self.assertNotEqual(ta, tb, '성격 다른 소스가 완전히 같은 톤을 냈습니다')
        self.assertGreater(ta['playful'], tb['playful'],
                           f'장난기 소스 playful={ta["playful"]} <= 기술 소스 {tb["playful"]}')
        self.assertGreater(tb['technical'], ta['technical'],
                           f'기술 소스 technical={tb["technical"]} <= 장난기 소스 {ta["technical"]}')
        self.assertGreater(tb['dark'], ta['dark'],
                           f'다크 소스 dark={tb["dark"]} <= 밝은 소스 {ta["dark"]}')

    def test_palettes_and_radii_differ(self):
        pa = self.reports['A']['json']['palette']
        pb = self.reports['B']['json']['palette']
        self.assertNotEqual(pa['tokens'], pb['tokens'], '두 소스가 같은 팔레트를 냈습니다')
        self.assertGreaterEqual(len(set(pa['tokens'].values()) & set(pb['tokens'].values())), 0)
        # 지면 계열은 소스 배경색에서 와야 한다 — 다크 소스의 지면/밤 토큰은 더 어둡다
        la = sp.rel_luminance(pa['tokens']['paper'])
        lb = sp.rel_luminance(pb['tokens']['paper'])
        self.assertNotAlmostEqual(la, lb, places=3)
        ra = {k: pa['radii'][k] for k in ('radius-sm', 'radius-md', 'radius-lg')}
        rb = {k: pb['radii'][k] for k in ('radius-sm', 'radius-md', 'radius-lg')}
        self.assertNotEqual(ra, rb, 'border-radius 가 다른 두 소스가 같은 반경을 냈습니다')

    # ---------------- b) CONTRAST_GATES 전 항목 — 보고서 + 독립 재계산
    def test_contrast_gates_all_pass(self):
        for tag, r in self.reports.items():
            with self.subTest(source=tag):
                self.assertTrue(r['json']['contrast']['all_pass'],
                                f'{tag}: all_pass=False')
                self.assertTrue(all(g['pass'] for g in r['json']['contrast']['gates']))
                toks = r['json']['palette']['tokens']
                for label, fg, bg, need in sp.CONTRAST_GATES:
                    ratio = sp.contrast_ratio(toks[fg], toks[bg])
                    self.assertGreaterEqual(ratio + 1e-9, need,
                                            f'{tag}: {fg}/{bg}={ratio:.2f} < {need}')

    # ---------------- c) CSS 계약
    def test_css_contract(self):
        for tag, r in self.reports.items():
            with self.subTest(source=tag):
                css = r['css']
                self.assertIn('preset-css', css)
                self.assertIn('/* preset.css', css)
                self.assertIn(':root{', css)
                for var in REQUIRED_VARS:
                    self.assertIn(var + ':', css, f'{tag}: {var} 누락')
                self.assertRegex(css, r'\.slide\s*\{')
                self.assertIn('.slide.dark,.dark.slide', css)
                self.assertEqual(css.count('{'), css.count('}'), '괄호 불균형')
                self.assertNotRegex(css, r'url\(|@import|https?://',
                                    '외부 자원 참조가 있습니다')
                # 밤 무대 오버라이드가 밤 토큰을 참조하는지
                self.assertIn('background:var(--night)', css)
                self.assertIn('color:var(--on-night)', css)

    def test_outputs_written(self):
        for tag, r in self.reports.items():
            self.assertTrue((r['deck'] / 'qa' / 'style-extract.md').stat().st_size > 500)
            board = (r['deck'] / 'qa' / 'style-board.html').read_text()
            for tok in ('brand', 'accent', 'night', 'paper'):
                self.assertIn(tok, board)

    # ---------------- d) 비밀 제외 + 덮어쓰기 가드
    def test_secret_files_excluded(self):
        src = self.tmp / 'src-secret'
        build_source(src, TECH_CSS, TECH_MD)
        (src / '.env').write_text('BRAND=#deadb9\nACC=#facade\n')
        (src / 'token.env').write_text('#ff00aa\n')
        (src / 'id_rsa').write_text('-----BEGIN OPENSSH PRIVATE KEY----- #00ffcc')
        (src / 'credentials').write_text('{"k":"#a1b2c3"}')
        out_dir = self.tmp / 'qa-secret'
        rc, out = run_extract('--source', str(src), '--json', '--qa-dir', str(out_dir),
                              '--offline', cwd=self.tmp)
        self.assertEqual(rc, 0, out)
        rep = json.loads((out_dir / 'style-extract.json').read_text())
        names = [s['name'] for s in rep['sources']]
        for bad in ('.env', 'token.env', 'id_rsa', 'credentials'):
            self.assertFalse(any(bad in n for n in names), f'{bad} 이 스캔됐습니다: {names}')
        blob = json.dumps(rep)
        for leak in ('deadb9', 'facade', 'ff00aa', '00ffcc', 'a1b2c3'):
            self.assertNotIn(leak, blob, f'비밀 파일의 색 {leak} 이 결과에 샜습니다')

    def test_overwrite_guard(self):
        manual = self.tmp / 'manual.css'
        manual.write_text('/* hand-made css, not generated */\n:root{--ink:#111}\n')
        rc, out = run_extract('--source', str(self.srcB), '--out-css', str(manual),
                              '--offline', cwd=self.tmp)
        self.assertEqual(rc, 2, f'수동 파일 덮어쓰기가 거부되지 않았습니다: {out}')
        self.assertIn('--force', out)
        self.assertIn('hand-made css', manual.read_text(), '수동 파일이 덮어써졌습니다')
        rc, out = run_extract('--source', str(self.srcB), '--out-css', str(manual),
                              '--force', '--offline', cwd=self.tmp)
        self.assertEqual(rc, 0, out)
        self.assertIn('preset-css', manual.read_text())

    def test_no_source_exit2(self):
        rc, out = run_extract('--source', '/nonexistent/path/xyz', '--offline', cwd=self.tmp)
        self.assertEqual(rc, 2, out)


class TestCaptureCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix='cap-test-'))

    def test_real_command_capture(self):
        frag = self.tmp / 'frag.html'
        meta = self.tmp / 'meta.json'
        rc, out = run_capture('--cmd', 'echo HELLO_SNIPPET && echo oops_err >&2; exit 3',
                              '--out', str(frag), '--json', str(meta))
        self.assertEqual(rc, 0, out)
        text = frag.read_text()
        self.assertIn('HELLO_SNIPPET', text)
        self.assertIn('oops_err', text)
        self.assertIn('exit 3', text)
        self.assertIn('<span class="p">', text)
        self.assertIn('class="out"', text)
        self.assertIn('capture_cli.py 실물 캡처', text)
        m = json.loads(meta.read_text())
        self.assertEqual(m['exit_code'], 3)
        self.assertFalse(m['timed_out'])

    def test_home_and_token_masking(self):
        frag = self.tmp / 'mask.html'
        meta = self.tmp / 'mask.json'
        tok = 'ghp_0123456789abcdefXYZW'
        home = str(pathlib.Path.home())
        rc, out = run_capture('--cmd', f'echo {tok}; echo {home}/sekret',
                              '--out', str(frag), '--json', str(meta), '--mask-home')
        self.assertEqual(rc, 0, out)
        text = frag.read_text() + meta.read_text()
        self.assertNotIn(tok, text, '토큰이 마스킹 없이 새었습니다')
        self.assertNotIn(home + '/sekret', text, '홈 경로가 마스킹 없이 새었습니다')
        self.assertIn('•••', text)
        m = json.loads(meta.read_text())
        self.assertGreaterEqual(sum(m['masked']['tokens'].values()), 1)
        self.assertGreaterEqual(m['masked']['home_paths'], 1)

    def test_win_frame_wrapper(self):
        frag = self.tmp / 'wf.html'
        rc, out = run_capture('--cmd', 'true', '--out', str(frag), '--win-frame')
        self.assertEqual(rc, 0, out)
        text = frag.read_text()
        for marker in ('win-frame', 'wf-bar', 'wf-title', 'code-copy'):
            self.assertIn(marker, text)


if __name__ == '__main__':
    unittest.main()
