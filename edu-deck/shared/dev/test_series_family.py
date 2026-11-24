#!/usr/bin/env python3
"""시리즈 계열(family) — build_series 표식·거부 + check_series 재검사·NOT_RUN 차단 시험 (P2b).

[목적] family-design.md §10·§11 계약을 고정한다:
       ① series.json family 허용값 검증(studio·vivid·drawing·classic), 편 deck.json family 와
          시리즈 계열 불일치 거부, family+theme 병용 거부.
       ② 결과물 표식 — <html data-family>(classic 은 미심음), 편 래퍼 data-ep-family.
       ③ check_series 재검사 — 표식 변조·불일치는 ERROR.
       ④ 계열 포털은 렌더 필수 — --no-render·브라우저 기동 실패(render=NOT_RUN)면 FAIL.
          classic 은 NOT_RUN 이어도 종전대로 PASS(무변화).
[입력] 임시 폴더에 만드는 최소 2편 시리즈. 브라우저 없음.
[출력] 없음(단정문). check_series.main 은 stdout 캡처로 RESULT·종료 코드를 본다.
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from bs4 import BeautifulSoup

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
sys.path.insert(0, str(S.parents[1] / 'edu-deck-series' / 'scripts'))
import build_series  # noqa: E402
import check_series  # noqa: E402

SLIDE = (
    '<section class="slide" data-archetype="statement" data-sec="90">'
    '<div class="head"><h2 class="title">시험 제목</h2></div>'
    '<p class="body">본문 문장입니다.</p>'
    '<aside class="notes">' + '노트 내용입니다. ' * 30 + '</aside></section>'
)


def write_series(root, series_family=None, ep_family=None, ep_theme=None):
    """최소 2편 시리즈를 root 에 쓴다. 반환: series.json dict."""
    eps = []
    for i in range(2):
        folder = root / f'ep{i}'
        (folder / 'src').mkdir(parents=True, exist_ok=True)
        (folder / 'src' / '01-a.html').write_text(SLIDE, encoding='utf-8')
        cfg = {'title': f'편{i}', 'output': 'x.html'}
        if ep_family is not None:
            cfg['family'] = ep_family
        if ep_theme is not None:
            cfg['theme'] = ep_theme
        (folder / 'deck.json').write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')
        eps.append({'ep': str(i), 'folder': f'ep{i}', 'label': f'{i+1}편', 'title': f'편{i}'})
    s = {'title': '시험 시리즈', 'output': 'out.html', 'episodes': eps}
    if series_family is not None:
        s['family'] = series_family
    (root / 'series.json').write_text(json.dumps(s, ensure_ascii=False), encoding='utf-8')
    return s


def run_main(*argv):
    """check_series.main 을 stdout 캡처와 함께 돌려 (종료 코드, 출력) 를 돌려준다."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = check_series.main(list(argv))
    return code, buf.getvalue()


class Build(unittest.TestCase):
    """① 계열 검증·거부와 ② 결과물 표식."""

    def test_family_marks_stamped(self):
        for fam in ('studio', 'vivid', 'drawing'):
            with self.subTest(fam=fam), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_series(root, series_family=fam, ep_family=fam)
                out = root / 'out.html'
                build_series.assemble(root, out_override=out)
                soup = BeautifulSoup(out.read_text(encoding='utf-8'), 'html.parser')
                self.assertEqual(soup.html.get('data-family'), fam)
                self.assertEqual(
                    [d.get('data-ep-family') for d in soup.select('#stage > .deck')],
                    [fam, fam])

    def test_drawing_inlines_gowun_batang(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_series(root, series_family='drawing', ep_family='drawing')
            out = root / 'out.html'
            build_series.assemble(root, out_override=out)
            html = out.read_text(encoding='utf-8')
            self.assertIn('Gowun Batang', html)

    def test_series_family_rejects_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_series(root, series_family='neon', ep_family='studio')
            with self.assertRaises(build_series.BuildError):
                build_series.assemble(root, out_override=root / 'out.html')

    def test_ep_family_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_series(root, series_family='studio', ep_family='vivid')
            with self.assertRaises(build_series.BuildError):
                build_series.assemble(root, out_override=root / 'out.html')
            # 편이 family 없으면(=classic) 계열 시리즈와도 불일치
            write_series(root, series_family='studio')
            with self.assertRaises(build_series.BuildError):
                build_series.assemble(root, out_override=root / 'out.html')

    def test_family_and_theme_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_series(root, series_family='studio', ep_family='studio', ep_theme='ocean')
            with self.assertRaises(build_series.BuildError):
                build_series.assemble(root, out_override=root / 'out.html')

    def test_ep_family_rejects_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_series(root, ep_family='neon')
            with self.assertRaises(build_series.BuildError):
                build_series.assemble(root, out_override=root / 'out.html')

    def test_classic_output_unchanged(self):
        """classic(미지정·'classic' 명시 모두): 루트·래퍼에 계열 표식이 없다."""
        for sfam in (None, 'classic'):
            with self.subTest(series_family=sfam), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_series(root, series_family=sfam)
                out = root / 'out.html'
                build_series.assemble(root, out_override=out)
                soup = BeautifulSoup(out.read_text(encoding='utf-8'), 'html.parser')
                self.assertIsNone(soup.html.get('data-family'))
                self.assertEqual(
                    [d.get('data-ep-family') for d in soup.select('#stage > .deck')],
                    [None, None])


class Recheck(unittest.TestCase):
    """③ check_series 결과물 재검사 — 변조·불일치는 ERROR."""

    def build(self, root, fam='studio'):
        write_series(root, series_family=fam, ep_family=fam)
        out = root / 'out.html'
        build_series.assemble(root, out_override=out)
        return out.read_text(encoding='utf-8')

    def errors(self, html):
        rep = check_series.Report()
        check_series.static_checks(html, BeautifulSoup(html, 'html.parser'), rep)
        return [i['message'] for i in rep.items if i['sev'] == 'ERROR']

    def test_clean_portal_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.errors(self.build(Path(tmp))), [])

    def test_tampered_ep_family_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = self.build(Path(tmp))
            tampered = html.replace('data-ep-family="studio"', 'data-ep-family="vivid"', 1)
            errs = self.errors(tampered)
            self.assertTrue(any('계열' in m for m in errs), errs)

    def test_bogus_ep_family_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = self.build(Path(tmp))
            tampered = html.replace('data-ep-family="studio"', 'data-ep-family="neon"', 1)
            errs = self.errors(tampered)
            self.assertTrue(any('계열' in m for m in errs), errs)

    def test_removed_ep_family_errors(self):
        """계열 포털에서 편 표식 삭제도 변조로 잡는다(없음=classic ≠ studio)."""
        with tempfile.TemporaryDirectory() as tmp:
            html = self.build(Path(tmp))
            tampered = html.replace(' data-ep-family="studio"', '', 1)
            errs = self.errors(tampered)
            self.assertTrue(any('계열' in m for m in errs), errs)

    def test_bogus_root_family_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = self.build(Path(tmp))
            tampered = html.replace('data-family="studio"', 'data-family="neon"', 1)
            errs = self.errors(tampered)
            self.assertTrue(any('계열' in m for m in errs), errs)


class RenderGate(unittest.TestCase):
    """④ 계열 포털 렌더 필수 — NOT_RUN 이면 FAIL, classic 은 PASS."""

    def build(self, root, fam=None):
        write_series(root, series_family=fam, ep_family=fam)
        out = root / 'out.html'
        build_series.assemble(root, out_override=out)
        return out

    def test_family_no_render_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.build(Path(tmp), 'studio')
            code, printed = run_main(str(out), '--no-render')
            self.assertEqual(code, 1, printed)
            self.assertIn('계열 검증', printed)
            self.assertIn('RESULT: FAIL', printed)

    def test_family_browser_fail_fails(self):
        """브라우저 기동 실패(render_checks NOT_RUN 경로)도 FAIL — 통과 우회 불가."""
        with tempfile.TemporaryDirectory() as tmp:
            out = self.build(Path(tmp), 'vivid')
            with mock.patch.object(check_series.check_deck, 'launch',
                                   side_effect=RuntimeError('no browser')):
                code, printed = run_main(str(out))
            self.assertEqual(code, 1, printed)
            self.assertIn('계열 검증', printed)
            self.assertIn('RESULT: FAIL', printed)

    def test_classic_no_render_still_passes(self):
        """classic 포털은 NOT_RUN 이어도 종전대로 ERROR 없으면 PASS."""
        with tempfile.TemporaryDirectory() as tmp:
            out = self.build(Path(tmp))
            code, printed = run_main(str(out), '--no-render')
            self.assertEqual(code, 0, printed)
            self.assertIn('RESULT: PASS', printed)
            self.assertIn('render=NOT_RUN', printed)


if __name__ == '__main__':
    unittest.main()
