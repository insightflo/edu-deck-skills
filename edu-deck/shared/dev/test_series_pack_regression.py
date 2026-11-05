#!/usr/bin/env python3
"""Probe copied series portals without modifying sample decks; failures exit nonzero.

Usage: python3 test_series_pack_regression.py <folder containing map/shelf/list.html>
The mixed fixture has existing episodes 0–2 and a six-slide pack episode 3.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_deck import launch
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def run(root):
    rows = []
    def record(hub, name, passed, detail=None):
        rows.append({'hub': hub, 'test': name, 'result': 'PASS' if passed else 'FAIL', 'detail': detail})
        (root / 'runtime-regression.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    with sync_playwright() as pw:
        browser = launch(pw)
        for hub in ('map', 'shelf', 'list'):
            ctx = browser.new_context(viewport={'width':1920, 'height':1080}, reduced_motion='reduce')
            page = ctx.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto((root / f'{hub}.html').as_uri())
            page.evaluate('localStorage.clear()')
            page.reload()
            record(hub, 'hub-start', page.evaluate('seriesInfo().mode') == 'hub')
            record(hub, 'actual-direct-DOM-contract', page.locator('iframe').count() == 0 and page.locator('#stage > .deck').count() == 4)
            selector = {'map':'.mn', 'shelf':'.bk', 'list':'.lt-open'}[hub]
            try:
                page.locator('#hub ' + selector).first.click(timeout=3000)
                record(hub, 'hub-pointer-open', True)
            except PlaywrightTimeout as error:
                record(hub, 'hub-pointer-open', False, str(error))
                page.screenshot(path=str(root / f'{hub}-pointer-blocked.png'))
                # Keep testing independent contracts after recording the real failure.
                page.locator('#hub ' + selector).first.focus()
                page.keyboard.press('Enter')
            record(hub, 'hub-open-existing-episode', page.evaluate('deckInfo().ep') == '0')
            page.evaluate('document.activeElement.blur(); deckGo("0",1,0)')
            before = page.evaluate('deckInfo()')
            page.keyboard.press('ArrowRight')
            after = page.evaluate('deckInfo()')
            record(hub, 'existing-page-navigation', after['step'] > before['step'] or after['slide'] > before['slide'])
            page.evaluate('deckGo("0",2,0)')
            page.keyboard.press('s')
            record(hub, 'existing-study', page.locator('.st-panel').is_visible() and bool(page.locator('.st-pb').inner_text().strip()))
            page.keyboard.press('s')
            page.keyboard.press('n')
            record(hub, 'existing-notes', page.locator('#notes').is_visible() and bool(page.locator('#notesText').inner_text().strip()))
            page.keyboard.press('n')
            page.keyboard.press('Escape')
            record(hub, 'escape-hub', page.evaluate('seriesInfo().mode') == 'hub')
            seen = page.evaluate('JSON.parse(localStorage.getItem("edeck-ser-seen-0"))')
            record(hub, 'progress-storage', 2 in seen and page.evaluate('localStorage.getItem("edeck-ser-pos-0")') == '2', seen)
            page.reload()
            page.locator('#hub ' + selector).first.focus()
            page.keyboard.press('Enter')
            record(hub, 'resume-after-reload', page.evaluate('deckInfo().slide') == 2)
            page.locator('.deck.on .active .sr').click()
            record(hub, 'return-chip', page.evaluate('seriesInfo().mode') == 'hub')
            page.locator('[data-study="glossary"]').first.click()
            record(hub, 'hub-glossary', page.locator('#st-gloss').is_visible())
            page.keyboard.press('Escape')
            page.evaluate('deckGo("3",0,0); document.activeElement.blur()')
            font = page.locator('.deck.on .active .pack-body').evaluate('el=>getComputedStyle(el).fontSize')
            record(hub, 'pack-design-loaded', float(font.removesuffix('px')) >= 18, {'fontSize':font})
            page.screenshot(path=str(root / f'{hub}-pack-first.png'))
            page.evaluate('deckGo("3",5,1)')
            page.locator('.deck.on .active .chk-o[data-ok]').focus()
            page.keyboard.press('Enter')
            record(hub, 'pack-native-keyboard-quiz', page.locator('.deck.on .active .chk-ok').count() == 1)
            page.locator('.deck.on .active .chk-again').click()
            page.locator('.deck.on .active .chk-o[data-ok]').focus()
            page.keyboard.press('Space')
            record(hub, 'pack-space-keyboard-quiz', page.locator('.deck.on .active .chk-ok').count() == 1)
            page.locator('.deck.on .active .chk-again').click()
            page.locator('.deck.on .active .chk-o[data-ok]').click()
            record(hub, 'pack-pointer-quiz', page.locator('.deck.on .active .chk-ok').count() == 1)
            page.evaluate('document.activeElement.blur()')
            page.keyboard.press('s')
            record(hub, 'pack-study', page.locator('.st-panel').is_visible() and '상호작용 검증용' in page.locator('.st-pb').inner_text())
            page.screenshot(path=str(root / f'{hub}-pack-study.png'))
            page.keyboard.press('s')
            page.reload()
            # The contract restores summary storage, not disabled quiz DOM state.
            page.keyboard.press('s')
            record(hub, 'pack-quiz-summary-restored', page.evaluate('deckInfo().ep') == '3' and page.locator('.st-chk').inner_text() == '확인 문제 1/1 맞음')
            page.keyboard.press('s')
            page.keyboard.press('Escape')
            page.locator('.hub-reset').click()
            record(hub, 'reset-requires-confirmation', page.evaluate('localStorage.getItem("edeck-ser-seen-0")') is not None)
            page.locator('.hub-reset').click()
            record(hub, 'reset-storage', page.evaluate('localStorage.getItem("edeck-ser-seen-0")') is None and page.evaluate('localStorage.getItem("edeck-ser-seen-3")') is None)
            page.evaluate('deckGo("3",5,1)')
            record(hub, 'reset-clears-quiz', page.locator('.deck.on .active .chk-done').count() == 0)
            record(hub, 'no-pageerrors', not errors, errors)
            ctx.close()
        browser.close()
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return int(any(row['result'] == 'FAIL' for row in rows))


def integration():
    """Real builds: reject invalid selections atomically; isolate two packs + legacy."""
    import os, shutil
    import tempfile
    from bs4 import BeautifulSoup
    scripts = Path(__file__).resolve().parents[3] / 'edu-deck-series' / 'scripts'
    sys.path.insert(0, str(scripts))
    import build_series
    import check_series
    here = Path(__file__).resolve()
    default = next((base / 'edu-deck-workspace/resource-pack-verification' for base in (here.parents[4], here.parents[3])
                    if (base / 'edu-deck-workspace/resource-pack-verification/regression/series').is_dir()), None)
    source = Path(os.environ.get('EDU_DECK_REGRESSION_FIXTURES', '')) if os.environ.get('EDU_DECK_REGRESSION_FIXTURES') else default
    if not source or not (source / 'regression/series').is_dir():
        raise SystemExit('회귀 픽스처 폴더가 없습니다. EDU_DECK_REGRESSION_FIXTURES 로 resource-pack-verification 폴더를 지정하세요. (픽스처는 개인 작업 환경 자산이라 저장소에 없음)')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, src in [('legacy', source / 'regression/series/ep0-기초'),
                          ('editorial', source / 'interactions/editorial'),
                          ('lab', source / 'interactions/lab')]:
            shutil.copytree(src, root / name)
        cfg = {'title':'Regression', 'episodes':[{'ep':i, 'folder':name} for i,name in enumerate(('legacy','editorial','lab'))]}
        (root/'series.json').write_text(json.dumps(cfg))
        out = root/'result.html'
        original = (root/'lab/deck.json').read_text()
        for bad in (None, {}, {'design':'../lab','flow':'problem'}, {'design':'lab','flow':'bad'},
                    {'design':'lab','flow':'problem','activities':['case','case']}):
            deck = json.loads(original); deck['resource_pack'] = bad
            (root/'lab/deck.json').write_text(json.dumps(deck)); out.write_text('KEEP')
            try:
                build_series.assemble(root, out_override=out)
            except build_series.BuildError:
                pass
            else:
                raise AssertionError(f'invalid selection accepted: {bad}')
            assert out.read_text() == 'KEEP'
        (root/'lab/deck.json').write_text(original)
        # Nested media stays nested; same selector deliberately differs per episode.
        for name, color in [('editorial','rgb(1, 2, 3)'), ('lab','rgb(4, 5, 6)')]:
            (root/name/'src/probe.css').write_text('@media screen { @supports (display: grid) { .pack-body { color: '+color+'; } } }')
        build_series.assemble(root, out_override=out)
        soup = BeautifulSoup(out.read_text(), 'html.parser')
        before = str(soup)
        rep = check_series.Report(); check_series.per_ep_static(out.read_text(), soup, rep)
        assert rep.count('ERROR') == 0, rep.items
        assert str(soup) == before, 'checker mutated the portal DOM'
        with sync_playwright() as pw:
            browser = launch(pw); page = browser.new_page()
            page.goto(out.as_uri())
            for ep, color in [(1,'rgb(1, 2, 3)'),(2,'rgb(4, 5, 6)'),(1,'rgb(1, 2, 3)')]:
                page.evaluate('(ep)=>deckGo(String(ep),0,0)', ep)
                assert page.locator('.deck.on .active .pack-body').evaluate('e=>getComputedStyle(e).color') == color
                assert page.locator('.deck.on .active').evaluate('e=>getComputedStyle(e).display') == 'flex'
            page.evaluate('deckGo("0",0,0)')
            assert page.locator('.deck.on .active').evaluate('e=>getComputedStyle(e).getPropertyValue("--pack-sans")') == ''
            # 혼합 포털의 계약(build_series: 공통 토큰은 전역, 레거시 표현은 팩 래퍼에서 끝): 레거시 편도
            # 가족 공통 의미 토큰 tokens.css :root(--ink #202b32)로 표시된다. 팩 토큰 누수만을 막는다(--pack-sans '').
            assert page.locator('.deck.on .active').evaluate('e=>getComputedStyle(e).getPropertyValue("--ink")') == '#202b32'
            browser.close()
        # All-pack path must work with no legacy shell/components/icons installed.
        assets = root/'shared/assets'; assets.mkdir(parents=True)
        for rel in ('css/pack-runtime.css','packs','js/study.js'):
            src = build_series.SHARED/'assets'/rel; dst = assets/rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir(): shutil.copytree(src,dst)
            else: shutil.copy2(src,dst)
        cfg['episodes'] = cfg['episodes'][1:]
        (root/'series.json').write_text(json.dumps(cfg))
        old = build_series.SHARED
        try:
            build_series.SHARED = root/'shared'
            build_series.assemble(root, out_override=out)
        finally:
            build_series.SHARED = old
    print('PASS integration: invalid/atomic, metadata, nested CSS, navigation isolation, independent assets')
    return 0


if __name__ == '__main__':
    sys.exit(integration() if sys.argv[1] == '--integration' else run(Path(sys.argv[1]).resolve()))
