#!/usr/bin/env python3
"""Build all 64 real pack combinations and run the unchanged browser checker.

Outputs are QA fixtures, not finished training material. Only speaker notes are
replaced with explicitly labelled realistic sample notes; generated slide bodies
are retained. Re-run into a new output directory to preserve previous evidence.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import shutil

from bs4 import BeautifulSoup

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / 'scripts'))
from resource_packs import DESIGNS, FLOWS


def command(args, log):
    result = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f'{log}: exit {result.returncode}')


def combination(root, pair):
    design, flow = pair
    out = root / f'{design}-{flow}'
    command([SHARED / 'scripts/resource_packs.py', 'init', out,
             '--design', design, '--flow', flow, '--title', '근거를 확인하고 업무에 적용하기'],
            root / f'{design}-{flow}-init.log')
    for source in sorted((out / 'src').glob('*.html')):
        soup = BeautifulSoup(source.read_text(), 'html.parser')
        prompt = soup.select_one('.pack-prompt').get_text(' ', strip=True)
        body = soup.select_one('.pack-body').get_text(' ', strip=True)
        notes = ('[갤러리 검증용 예시 설명] ' + prompt + ' 먼저 자신의 업무에서 비슷한 상황을 떠올려 보세요. '
                 + body + ' 예를 들어 요청을 처리하기 전에 요청자, 필요한 자료, 완료 조건을 따로 적어 봅니다. '
                 '자료에서 직접 확인한 사실과 아직 확인하지 못한 추측을 구분하세요. 짝과 답을 비교한 뒤 '
                 '선택한 이유를 한 문장으로 설명하고, 근거가 부족한 부분은 다음 확인 항목으로 남깁니다.')
        assert 110 <= len(notes) <= 450, len(notes)
        soup.select_one('.notes').string = notes
        source.write_text(str(soup))
    command([SHARED / 'scripts/build_deck.py', out], out / 'build.log')
    args = [SHARED / 'scripts/check_deck.py', out / 'deck.html', '--json', out / 'check.json']
    if flow == 'problem':
        args += ['--sheets', out / 'sheets', '--shots', out / 'shots']
    result = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)
    (out / 'check.log').write_text(result.stdout + result.stderr)
    data = json.loads((out / 'check.json').read_text())
    row = {'design': design, 'flow': flow, 'exit': result.returncode,
           **{key: data[key] for key in ('result', 'errors', 'warnings', 'render')},
           'slides': len(data['slides'])}
    print(json.dumps(row), flush=True)
    return row


def matrix(root):
    root.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda pair: combination(root, pair),
                             [(d, f) for d in DESIGNS for f in FLOWS]))
    (root / 'matrix.json').write_text(json.dumps(rows, indent=2))
    from PIL import Image, ImageDraw
    sheet = Image.new('RGB', (1440, 4 * 435), '#dddddd')
    draw = ImageDraw.Draw(sheet)
    for i, design in enumerate(DESIGNS):
        x, y = (i % 2) * 720, (i // 2) * 435
        draw.text((x + 12, y + 8), design, fill='#222222')
        image = Image.open(root / f'{design}-problem/shots/slide-01.png')
        sheet.paste(image.resize((720, 405)), (x, y + 30))
    sheet.save(root / 'eight-designs.png')
    return int(any(r['exit'] or r['render'] != 'RUN' or r['errors'] or r['warnings'] for r in rows))


def interactions(root, matrix_root):
    """Exercise actual quiz/study runtime in every design, with motion on/off."""
    from playwright.sync_api import sync_playwright
    from check_deck import launch, RENDER_JS, QUIET_CSS
    root.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        browser = launch(pw)
        for design in DESIGNS:
            out = root / design
            shutil.copytree(matrix_root / f'{design}-problem', out)
            note = ('[상호작용 검증용 예시 설명] 업무 요청을 처리하기 전에 자료의 작성자와 기준 날짜를 확인합니다. '
                    '자료에 직접 적힌 사실과 자신의 해석을 분리하면 잘못된 결정을 줄일 수 있습니다. '
                    '이 문제에서는 먼저 오답을 선택해 해설을 읽고 다시 풀어 보세요. 정답을 선택한 다음에는 '
                    '자신의 실제 업무에서 확인할 근거를 한 가지 적고 동료에게 그 이유를 설명해 보세요.')
            fixture = f'''<section class="slide pack pack-{design}" data-design="{design}">
<p class="pack-kicker">상호작용 예제</p><h1 class="pack-prompt">근거를 확인하는 첫 행동은 무엇인가요?</h1>
<p class="pack-body" data-step="1">사실과 추측을 구분한 뒤 답을 선택하세요.</p>
<div class="chk"><p class="chk-q"><span class="chk-n">1</span>업무 자료를 받으면 무엇부터 하나요?</p>
<div class="chk-opts"><button class="chk-o">제목만 보고 결론을 내립니다.</button>
<button class="chk-o" data-ok>작성자와 기준 날짜를 확인합니다.</button></div>
<p class="chk-why">누가 언제 만든 자료인지 확인해야 지금 판단에 쓸 수 있는지 알 수 있습니다.</p></div>
<aside class="notes">{note}</aside></section>'''
            (out / 'src/99-interaction.html').write_text(fixture)
            command([SHARED / 'scripts/build_deck.py', out], out / 'interaction-build.log')
            command([SHARED / 'scripts/check_deck.py', out / 'deck.html', '--json', out / 'interaction-check.json'], out / 'interaction-check.log')
            report = json.loads((out / 'interaction-check.json').read_text())
            assert report['render'] == 'RUN' and report['warnings'] == 0 and report['errors'] == 0, report
            for reduced in (False, True):
                ctx = browser.new_context(viewport={'width': 1920, 'height': 1080},
                                          reduced_motion='reduce' if reduced else 'no-preference')
                page = ctx.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto((out / 'deck.html').as_uri())
                page.evaluate('localStorage.clear()')
                page.reload()
                page.keyboard.press('End')
                assert page.evaluate('deckInfo().slide') == 5
                assert page.evaluate('deckInfo().step') == 0
                page.keyboard.press('ArrowRight')
                assert page.evaluate('deckInfo().step') == 1
                page.keyboard.press('ArrowLeft')
                assert page.evaluate('deckInfo().step') == 0
                page.keyboard.press('ArrowRight')
                page.evaluate('''() => { window.motionSamples = []; window.motionTimer = setInterval(() => {
                    const mark = document.querySelector('.active .ed-mark canvas');
                    if (mark) window.motionSamples.push(mark._edProgress ?? 0);
                }, 50); }''')
                page.locator('.active .chk-o').first.click()
                assert page.locator('.active .chk-ng .chk-msg').is_visible()
                assert '아직' in page.locator('.active .chk-msg').inner_text()
                page.wait_for_timeout(1400)
                samples = page.evaluate('() => {clearInterval(window.motionTimer); return window.motionSamples;}')
                mark = page.locator('.active .ed-mark canvas')
                assert mark.count() == 1
                assert mark.evaluate('''(c)=>{const x=c.getContext('2d'),d=x.getImageData(0,0,c.width,c.height).data;
                    let n=0;for(let i=3;i<d.length;i+=40){if(d[i])n++;}return n>200;}''')
                if reduced:
                    assert all(value == 1 for value in samples), samples
                else:
                    assert len(set(samples)) > 2, samples
                assert mark.evaluate('(c)=>c._edProgress===1')
                page.screenshot(path=str(out / ('wrong-reduced.png' if reduced else 'wrong-crayon.png')))
                page.locator('.active .chk-again').click()
                assert page.locator('.active .chk-done').count() == 0
                assert page.locator('.active .ed-mark').count() == 0
                assert page.locator('.active .chk-o').first.is_enabled()
                page.locator('.active .chk-o[data-ok]').click()
                assert page.locator('.active .chk-ok .chk-msg').inner_text() == '맞았습니다.'
                page.wait_for_timeout(1400)
                page.add_style_tag(content=QUIET_CSS)
                findings = page.evaluate(RENDER_JS, [5, True])
                assert not findings, findings
                page.screenshot(path=str(out / ('correct-reduced.png' if reduced else 'correct-crayon.png')))
                # Presentation shortcuts belong to the page, not the quiz button.
                page.evaluate('document.activeElement.blur()')
                page.keyboard.press('n')
                assert page.locator('#notes').is_visible()
                assert note in page.locator('#notesText').inner_text()
                page.keyboard.press('n')
                assert not page.locator('#notes').is_visible()
                page.keyboard.press('s')
                assert page.locator('.st-panel').is_visible()
                assert '상호작용 검증용' in page.locator('.st-pb').inner_text()
                page.screenshot(path=str(out / ('study-reduced.png' if reduced else 'study.png')))
                page.keyboard.press('s')
                assert not page.locator('.st-panel').is_visible()
                page.keyboard.press('Home')
                assert page.evaluate('deckInfo().slide') == 0
                page.keyboard.press('ArrowRight')
                expected = 0 if design == 'workbook' else 1
                assert page.evaluate('deckInfo().slide') == expected
                assert not errors, errors
                results.append({'design': design, 'reduced_motion': reduced,
                                'quiz_wrong_retry_correct': 'PASS', 'semantic_canvas_mark': 'PASS',
                                'motion_distinct_frames': len(set(samples)),
                                'keyboard_steps_navigation': 'PASS', 'notes_study': 'PASS',
                                'graded_layout': 'PASS', 'errors': errors})
                (root / 'interactions.json').write_text(json.dumps(results, indent=2))
                ctx.close()
        browser.close()
    return 0


def keyboard_activation(root, deck):
    """Independent negative regression: focused native quiz buttons must activate."""
    from playwright.sync_api import sync_playwright
    from check_deck import launch
    root.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        browser = launch(pw)
        for key in ('Enter', 'Space'):
            ctx = browser.new_context(viewport={'width': 1920, 'height': 1080})
            page = ctx.new_page()
            page.goto(deck.as_uri())
            page.evaluate('localStorage.clear()')
            page.reload()
            page.evaluate('deckGo(5,1)')
            page.locator('.active .chk-o[data-ok]').focus()
            page.keyboard.press(key)
            page.wait_for_timeout(200)
            passed = page.locator('.active .chk-ok').count() == 1
            results.append({'key': key, 'result': 'PASS' if passed else 'FAIL',
                            'expected': 'focused correct answer is graded',
                            'actual_graded_count': page.locator('.active .chk-done').count(),
                            'deckInfo': page.evaluate('deckInfo()')})
            page.screenshot(path=str(root / f'keyboard-{key}.png'))
            ctx.close()
        ctx = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = ctx.new_page()
        page.goto(deck.as_uri())
        # Removing the native-control guard must fail these real DOM probes.
        controls = {
            'button-child': '<button><span tabindex="0">button</span></button>',
            'link-child': '<a href="#"><span tabindex="0">link</span></a>',
            'input': '<input value="text">',
            'textarea': '<textarea>text</textarea>',
            'select': '<select><option>A</option><option>B</option></select>',
            'summary': '<details><summary>details</summary>body</details>',
            'editable-child': '<div contenteditable="true"><span tabindex="0">text</span></div>',
        }
        for name, html in controls.items():
            page.evaluate('deckGo(5,0)')
            page.evaluate('''html => {
                document.getElementById('keyboard-probe')?.remove();
                const box = document.createElement('div'); box.id = 'keyboard-probe';
                box.innerHTML = html; document.querySelector('.active').append(box);
                box.querySelector('span,input,textarea,select,summary,button,a').focus();
            }''', html)
            for key in ('Enter', ' ', 'ArrowRight', 'Home', 'End', 'Backspace'):
                result = page.evaluate('''key => {
                    const e = new KeyboardEvent('keydown', {key, bubbles:true, cancelable:true});
                    document.activeElement.dispatchEvent(e);
                    return {prevented:e.defaultPrevented, info:deckInfo()};
                }''', key)
                passed = not result['prevented'] and result['info']['slide'] == 5 and result['info']['step'] == 0
                results.append({'control': name, 'key': key, 'result': 'PASS' if passed else 'FAIL', **result})
        page.evaluate("document.getElementById('keyboard-probe').remove(); document.activeElement.blur(); deckGo(5,0)")
        page.keyboard.press('Space')
        step_ok = page.evaluate('deckInfo().step') == 1
        page.keyboard.press('Home')
        home_ok = page.evaluate('deckInfo().slide') == 0
        page.keyboard.press('End')
        end_ok = page.evaluate('deckInfo().slide') == 5
        results.append({'control': 'page', 'result': 'PASS' if step_ok and home_ok and end_ok else 'FAIL',
                        'space_step': step_ok, 'home': home_ok, 'end': end_ok})
        ctx.close()
        browser.close()
    (root / 'keyboard-activation.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
    return int(any(row['result'] != 'PASS' for row in results))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--interactions-from', type=Path)
    parser.add_argument('--keyboard-activation-from', type=Path,
                        help='Built six-slide interaction deck; nonzero exit if Enter/Space cannot grade')
    args = parser.parse_args()
    if args.keyboard_activation_from:
        sys.exit(keyboard_activation(args.output.resolve(), args.keyboard_activation_from.resolve()))
    sys.exit(interactions(args.output.resolve(), args.interactions_from.resolve())
             if args.interactions_from else matrix(args.output.resolve()))
