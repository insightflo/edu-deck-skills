#!/usr/bin/env python3
"""capture_deck.py — 덱 전 장 최종 상태 캡처 (공통 심미 QA 도구 — 전 스킬 공용)

[왜] 공통 디자인 크리틱(references/design-critique.md §3~4)은 "실제 화면"을 요구한다.
     ArrowRight 는 단계만 넘기므로 슬라이드 단위 캡처가 나오지 않는다 — deckGo(i, 99)
     (=모션 완결 상태)로 장을 옮기고 크롬(진행바·점·쪽수·도움말·토스트)은 가린다.
[입력] capture_deck.py <덱.html 경로> <출력 폴더> [--width 1920] [--height 1080]
[출력] s01~sNN.png + revisit.png(앞 1장 갔다가 복귀) · 페이지에러 수 stdout.
      Chromium 실행기: 시스템 Chrome(executable_path) — 없으면 channel='chrome'.
[주의] 출력 폴더를 비우지 않는다(덮어쓰기). 재방문 게이트·축소 게이트가 필요하면
      --narrow 스위치로 1280×720 1장을 추가한다.
"""
import argparse
import pathlib
import sys

from playwright.sync_api import sync_playwright

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HIDE = """
(() => { const s=document.createElement('style');
 s.textContent='#progress,#dots,#counter,#help,.ed-toast{display:none!important}';
 document.head.appendChild(s); })();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('deck')
    ap.add_argument('out')
    ap.add_argument('--width', type=int, default=1920)
    ap.add_argument('--height', type=int, default=1080)
    ap.add_argument('--narrow', action='store_true', help='1280×720 축소 1장 추가')
    a = ap.parse_args()

    deck = pathlib.Path(a.deck).resolve()
    if not deck.exists():
        print(f'FAIL: 덱이 없습니다 — {deck}', file=sys.stderr)
        return 2
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(executable_path=CHROME)
        except Exception:
            b = p.chromium.launch(channel='chrome')
        pg = b.new_page(viewport={'width': a.width, 'height': a.height})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(deck.as_uri())
        pg.wait_for_timeout(1200)
        pg.evaluate(HIDE)
        n = pg.evaluate('window.deckInfo().count')
        for i in range(n):
            pg.evaluate(f'window.deckGo({i}, 99)')
            pg.wait_for_timeout(700)
            pg.screenshot(path=str(out / f's{i + 1:02d}.png'))
        if n > 1:
            pg.evaluate('window.deckGo(0, 99)')
            pg.wait_for_timeout(400)
            pg.evaluate(f'window.deckGo({n - 1}, 99)')
            pg.wait_for_timeout(900)
            pg.screenshot(path=str(out / 'revisit.png'))
        if a.narrow:
            pg.set_viewport_size({'width': 1280, 'height': 720})
            pg.wait_for_timeout(600)
            pg.screenshot(path=str(out / 'narrow.png'))
        print(f'OK slides={n} → {out}')
        print('pageerrors:', errs or 0)
        b.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
