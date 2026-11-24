#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""themes.js 스타일 계열 미리보기(P2b-1, family-design.md §7) 시험.

[목적] ① ?family=studio → data-family 적용(+data-theme 제거, 상호배제)
       ② 테마 미리보기 전환 → data-family 제거 + data-theme 적용
       ③ 계열 미리보기 재전환 → data-theme 제거 + data-family 적용
       ④ 해제(reset) → 빌드 본래 data-theme·data-family 정확히 복원
       ⑤ preset-css 표식 <style> 이 있는 덱 → ?family= 무시·계열 미리보기 비활성
       ⑥ 기존 ?theme= 단독 미리보기 무변경
       부가: 저장 키 분리(edu-family-preview-)·저장 키 상호배제·재방문 복원·
       패널 계열 섹션·팩 덱 비활성.
[입력] 최소 HTML fixture(themes.js 인라인 + [data-theme] 블록 2종 + :root)를
       실제 Chromium(--headless --dump-dom)에서 실행하고 <html> 속성·드라이버 로그를 판독.
       별도 파이썬 의존성이 없어 어떤 python3 에서도 돈다.
[출력] 없음(단정문).
"""
import html as html_lib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

S = Path(__file__).resolve().parents[1]
JS = (S / 'assets/js/themes.js').read_text(encoding='utf-8')
OUT = Path(tempfile.mkdtemp(prefix='edu-fam-'))

# :root 가 있어야 themes.js 의 classic 항목이 만들어진다(없으면 스크립트 무동작).
CSS = (":root{--paper:#ffffff;--ink:#111111;--accent:#aa2211;--accent-light:#ffddcc}"
       '[data-theme="ocean"]{--paper:#eeeeff;--ink:#112233;--accent:#0066cc;--accent-light:#ccddff}'
       '[data-theme="mono"]{--paper:#ffffff;--ink:#000000;--accent:#444444;--accent-light:#eeeeee}')

CHROME_CANDIDATES = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    shutil.which('chrome'), shutil.which('chromium'), shutil.which('google-chrome'),
]
CHROME = next((c for c in CHROME_CANDIDATES if c and Path(c).is_file()), None)


def drv(body):
    """미리보기 호출 사슬 — s() 가 매 단계 <html> 속성쌍을 data-log 에 쌓는다.
    첫 항(log[0])은 themes.js 초기 적용(파라미터·저장 복원) 직후 상태다."""
    return ('(function(){var d=document.documentElement,L=[];'
            'function s(){L.push([d.getAttribute("data-theme"),d.getAttribute("data-family")])}s();'
            + body +
            'd.setAttribute("data-log",JSON.stringify(L));})();')


def make(name, html_attrs='', extra_style='', extra_head='', driver=''):
    html = ('<!doctype html><html lang="ko"' + html_attrs + '><head><meta charset="utf-8">'
            + extra_head + '<style>' + CSS + '</style>'
            + ('<style>' + extra_style + '</style>' if extra_style else '')
            + '</head><body><div id="stage"><section class="slide"></section></div>'
            + '<script>' + JS + '</script>'
            + ('<script>' + driver + '</script>' if driver else '')
            + '</body></html>')
    p = OUT / name
    p.write_text(html, encoding='utf-8')
    return p


def attr(tag, name):
    m = re.search(r'\b' + name + r'="([^"]*)"', tag)
    return html_lib.unescape(m.group(1)) if m else None


def dominfo(dom):
    m = re.search(r'<html\b[^>]*>', dom)
    tag = m.group(0) if m else ''
    log = json.loads(attr(tag, 'data-log') or '[]')
    return {'t': attr(tag, 'data-theme'), 'f': attr(tag, 'data-family'), 'log': log,
            'nfam': attr(tag, 'data-nfam'), 'nth': attr(tag, 'data-nth'),
            'api': attr(tag, 'data-api'), 'k1': attr(tag, 'data-k1'),
            'k2': attr(tag, 'data-k2'),
            'onf': attr(tag, 'data-onf'), 'ont': attr(tag, 'data-ont')}


class Case(unittest.TestCase):
    """Chromium + fixture 공유 베이스."""

    @classmethod
    def setUpClass(cls):
        if not CHROME:
            raise unittest.SkipTest('Chromium 바이너리를 찾지 못했다')
        cls.A = make('a.html', ' data-theme="ocean"')             # 테마 빌드 덱
        cls.ASEQ = make('a-seq.html', ' data-theme="ocean"', driver=drv(
            "eduThemePreview.family('studio');s();"
            "eduThemePreview.apply('mono');s();"
            "eduThemePreview.family('vivid');s();"
            "eduThemePreview.reset();s();"))
        cls.BSEQ = make('b-seq.html', ' data-family="studio"', driver=drv(
            "eduThemePreview.apply('mono');s();"
            "eduThemePreview.family('vivid');s();"
            "eduThemePreview.reset();s();"))
        cls.C = make('c.html', ' data-theme="ocean"',
                     extra_style='/* preset-css */\n:root{--paper:#f5f0e8}',
                     driver=drv(
            "eduThemePreview.family('studio');s();eduThemePreview.toggle();"
            "d.setAttribute('data-nfam',document.querySelectorAll('#edThemes [data-fam]').length);"
            "d.setAttribute('data-nth',document.querySelectorAll('#edThemes [data-th]').length);"
            "d.setAttribute('data-api',(eduThemePreview.families||[]).join(','));"))
        cls.APANEL = make('a-panel.html', ' data-theme="ocean"', driver=drv(
            "eduThemePreview.toggle();"
            "d.setAttribute('data-nfam',document.querySelectorAll("
            "'#edThemes [data-fam]:not([data-fam=classic])').length);"
            "document.querySelector('#edThemes [data-fam=studio]').click();s();"
            "d.setAttribute('data-onf',Array.from(document.querySelectorAll("
            "'#edThemes [data-fam].on')).map(function(x){return x.getAttribute('data-fam')}).join(','));"
            "d.setAttribute('data-ont',Array.from(document.querySelectorAll("
            "'#edThemes [data-th].on')).map(function(x){return x.getAttribute('data-th')}).join(','));"
            "document.querySelector('#edThemes [data-fam=classic]').click();s();"))
        cls.ASAVE = make('a-save.html', ' data-theme="ocean"', driver=drv(
            "eduThemePreview.family('vivid',true);s();"
            "d.setAttribute('data-k1',Object.keys(localStorage).sort().join('|'));"))
        # 같은 파일에서 계열 저장 → 테마 저장 연쇄 — 저장 키 상호배제는 같은
        # 파일의 두 키(edu-*-preview-a-xsave.html)를 겨냥해야 의미가 있다
        cls.AXSAVE = make('a-xsave.html', ' data-theme="ocean"', driver=drv(
            "eduThemePreview.family('vivid',true);s();"
            "d.setAttribute('data-k1',Object.keys(localStorage).sort().join('|'));"
            "eduThemePreview.apply('mono',true);s();"
            "d.setAttribute('data-k2',Object.keys(localStorage).sort().join('|'));"))
        cls.PACK = make('pack.html', driver=drv(
            "d.setAttribute('data-api',window.eduThemePreview?'1':'0');"),
            extra_head='<meta name="edu-deck-resource-pack" content="editorial">')
        cls._profiles = Path(tempfile.mkdtemp(prefix='edu-fam-prof-'))

    def _dump(self, fixture, query='', profile=''):
        prof = self._profiles / (profile or fixture.stem + re.sub(r'\W', '_', query))
        prof.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            [CHROME, '--headless', '--disable-gpu', '--no-first-run',
             '--no-default-browser-check', '--disable-extensions', '--mute-audio',
             '--no-sandbox', '--user-data-dir=' + str(prof), '--dump-dom',
             'file://' + str(fixture) + query],
            capture_output=True, text=True, timeout=90)
        self.assertEqual(0, r.returncode, 'Chromium 실행 실패: ' + r.stderr[-400:])
        self.assertIn('<html', r.stdout, 'DOM 덤프가 비어 있다: ' + r.stderr[-400:])
        return dominfo(r.stdout)


class TestFamilyParam(Case):
    """① ?family= 쿼리 미리보기."""

    def test_family_param_applies(self):
        a = self._dump(self.A, '?family=studio')
        self.assertEqual('studio', a['f'], '?family=studio 가 data-family 를 설정해야 한다')
        self.assertIsNone(a['t'], '계열 미리보기가 빌드 data-theme 을 제거해야 한다(상호배제)')

    def test_family_param_classic(self):
        a = self._dump(self.A, '?family=classic')
        self.assertIsNone(a['f'])
        self.assertIsNone(a['t'], '?family=classic 도 테마 속성을 제거한다(상호배제)')

    def test_family_param_invalid_ignored(self):
        a = self._dump(self.A, '?family=bogus')
        self.assertEqual('ocean', a['t'])
        self.assertIsNone(a['f'])

    def test_family_beats_theme_when_both(self):
        # 둘 다 오면 계열이 이긴다 — 상호배제에서 하나만 살아남아야 한다
        a = self._dump(self.A, '?theme=mono&family=vivid')
        self.assertEqual('vivid', a['f'])
        self.assertIsNone(a['t'])


class TestMutualExclusion(Case):
    """②③④ 전환·해제 사슬 — 한 덤프의 단계별 로그로 증명."""

    def test_sequence_theme_deck(self):
        a = self._dump(self.ASEQ)
        log = a['log']
        self.assertEqual(['ocean', None], log[0], '초기: 빌드 테마 그대로')
        self.assertEqual([None, 'studio'], log[1], '① 계열 ON → data-theme 제거+data-family')
        self.assertEqual(['mono', None], log[2], '② 테마 ON → data-family 제거+data-theme')
        self.assertEqual([None, 'vivid'], log[3], '③ 계열 재전환 → data-theme 제거+data-family')
        self.assertEqual(['ocean', None], log[4], '④ 해제 → origTheme 복원')

    def test_sequence_family_deck(self):
        # 계열 빌드 덱에서도 같은 상호배제와 origFamily 복원이 성립해야 한다
        a = self._dump(self.BSEQ)
        log = a['log']
        self.assertEqual([None, 'studio'], log[0], '초기: 빌드 계열 그대로')
        self.assertEqual(['mono', None], log[1], '테마 ON → 빌드 data-family 도 제거')
        self.assertEqual([None, 'vivid'], log[2], '계열 ON → data-theme 제거')
        self.assertEqual([None, 'studio'], log[3], '해제 → origFamily 복원')


class TestPresetDisabled(Case):
    """⑤ preset-css 표식 덱 — 계열 미리보기 비활성."""

    def test_preset_family_disabled(self):
        a = self._dump(self.C, '?family=studio')
        self.assertEqual(['ocean', None], a['log'][0], '프리셋 덱은 ?family= 를 무시한다')
        self.assertEqual(['ocean', None], a['log'][1], '프리셋 덱은 family() 호출도 무동작')
        self.assertEqual('0', a['nfam'], '패널에 계열 섹션이 없어야 한다')
        self.assertGreater(int(a['nth']), 0, '테마 섹션은 그대로 있어야 한다')
        self.assertEqual('', a['api'], 'families 목록이 비어 있어야 한다')


class TestThemeUnchanged(Case):
    """⑥ 기존 ?theme= 단독 미리보기 무변경."""

    def test_theme_param(self):
        a = self._dump(self.A, '?theme=mono')
        self.assertEqual('mono', a['t'])
        self.assertIsNone(a['f'])

    def test_theme_param_invalid(self):
        a = self._dump(self.A, '?theme=bogus')
        self.assertEqual('ocean', a['t'])
        self.assertIsNone(a['f'])

    def test_theme_saved_restored(self):
        # 1차 실행: 테마 저장 → 같은 프로필 재방문에서 edu-theme-preview- 키로 복원
        a = self._dump(self.AXSAVE, profile='tsave')
        self.assertIn('edu-theme-preview-a-xsave.html', a['k2'])
        a2 = self._dump(self.AXSAVE, profile='tsave')
        self.assertEqual(['mono', None], a2['log'][0],
                         '저장된 테마 미리보기가 재방문에서 복원돼야 한다')


class TestFamilyKey(Case):
    """저장 키 edu-family-preview-<파일명> 분리 + 저장 키 상호배제 + 복원."""

    def test_family_save_and_restore(self):
        a = self._dump(self.ASAVE, profile='fsave')
        self.assertEqual([None, 'vivid'], a['log'][1])
        self.assertIn('edu-family-preview-a-save.html', a['k1'])
        self.assertNotIn('edu-theme-preview-a-save.html', a['k1'])
        # 재방문: 저장된 계열 미리보기가 복원된다(테마 키와 별개 키)
        a2 = self._dump(self.ASAVE, profile='fsave')
        self.assertEqual([None, 'vivid'], a2['log'][0],
                         '저장된 계열 미리보기가 재방문에서 복원돼야 한다')

    def test_save_mutual_exclusion(self):
        # 같은 파일에서 계열 저장 → 테마 저장: 테마 키만 남고 계열 키는 지워진다
        a = self._dump(self.AXSAVE, profile='xsave')
        self.assertIn('edu-family-preview-a-xsave.html', a['k1'])
        self.assertEqual(['mono', None], a['log'][2])
        self.assertIn('edu-theme-preview-a-xsave.html', a['k2'])
        self.assertNotIn('edu-family-preview-a-xsave.html', a['k2'],
                         '테마 저장 시 계열 미리보기 키가 지워져야 한다(상호배제)')


class TestPanelAndPack(Case):
    """패널 계열 섹션 · 해제 행 · 팩 덱 비활성."""

    def test_panel_family_swatch_and_reset(self):
        a = self._dump(self.APANEL, '?themes=1')
        self.assertEqual('3', a['nfam'], '계열 스와치는 studio·vivid·drawing 3종(+기본 해제 행)')
        self.assertEqual([None, 'studio'], a['log'][1], '스튜디오 스와치 클릭 → 계열 적용')
        self.assertEqual('studio', a['onf'], '계열 미리보기 중 계열 항목만 on')
        self.assertEqual('', a['ont'], '계열 미리보기 중 테마 항목 선택 표시는 비어야 한다')
        self.assertEqual(['ocean', None], a['log'][2],
                         "패널 '기본 — 빌드 상태 복원(해제)' 행이 빌드 속성을 복원해야 한다")

    def test_pack_deck_disabled(self):
        a = self._dump(self.PACK, '?family=studio')
        self.assertEqual('0', a['api'], '팩 덱에서는 themes.js 가 무동작해야 한다')
        self.assertEqual([None, None], a['log'][0])


if __name__ == '__main__':
    unittest.main()
