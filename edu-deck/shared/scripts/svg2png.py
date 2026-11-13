#!/usr/bin/env python3
"""svg2png.py — SVG 파일을 PNG 로 변환한다 (PPT(PPTX) 등 덱 밖으로 시각 자산을 내보낼 때).

[왜] 우리 도식·차트 자산(chart_gen.mjs·arch_layout.mjs·iso_layout.mjs·lucide 아이콘)은
     SVG 로 나온다. ppt-master 처럼 덱 밖 도구는 SVG 를 직접 못 쓰는 경우가 많다 —
     PNG 로 내보내 삽입한다. 덱 안(HTML)에서는 이 도구를 쓰지 않는다(SVG 그대로가 계약).
[입력] svg2png.py <in.svg> [<out.png>] [--scale 2] [--width N] [--bg CSS색|transparent]
[출력] PNG 파일 경로. 기본 배율 2(선명도), --width 를 주면 viewBox 비율로 배율 자동.
[의존] playwright(이미 검사·캡처에 쓰는 의존 — 새 설치 불요). Chromium 실행기는
       시스템 Chrome → playwright 캐시 순서로 찾는다.
"""
import argparse
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def svg_size(text: str):
    """width/height 또는 viewBox 에서 (w, h) 를 얻는다."""
    m = re.search(r'<svg\b[^>]*>', text)
    if not m:
        raise SystemExit("ERROR: <svg> 태그가 없습니다")
    tag = m.group(0)
    w = re.search(r'\bwidth="([\d.]+)', tag)
    h = re.search(r'\bheight="([\d.]+)', tag)
    if w and h:
        return float(w.group(1)), float(h.group(1))
    vb = re.search(r'viewBox="([\d.\s,-]+)"', tag)
    if vb:
        p = [float(x) for x in re.split(r"[,\s]+", vb.group(1).strip()) if x]
        if len(p) == 4:
            return p[2] or 1.0, p[3] or 1.0
    return 960.0, 540.0  # 마지막 수단 — 화면 캡처 폭 기준


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--width", type=float)
    ap.add_argument("--bg", default="transparent", help="CSS 색 또는 transparent(기본)")
    ap.add_argument("--css", action="append", default=[],
                    help="함께 주입할 CSS 파일(토큰 정의 등 — 반복 가능). 덱 문맥 없는 SVG 의 var(--…) 해결용")
    ap.add_argument("--scope", default="",
                    help="랩 div 에 붙일 클래스(예: 'slide consult') — 토큰이 .slide.* 스코프 안에 정의된 자산용")
    a = ap.parse_args()

    src = pathlib.Path(a.svg)
    if not src.is_file():
        raise SystemExit(f"ERROR: {src} 없음")
    text = src.read_text(encoding="utf-8")
    w, h = svg_size(text)
    scale = (a.width / w) if a.width else a.scale
    out = pathlib.Path(a.out) if a.out else src.with_suffix(".png")

    css = "\n".join(pathlib.Path(c).read_text(encoding="utf-8") for c in a.css)
    # viewBox 만 있는 svg 의 기본 300x150 방지 — 명시 치수를 명시적으로 준다
    head = (
        "<!doctype html><meta charset='utf-8'><style>"
        "html,body{margin:0;padding:0;background:transparent}"
        "#wrap{display:inline-block;line-height:0}"
        f"#wrap svg{{width:{w:g}px;height:{h:g}px}}"
        + css + "</style>"
    )
    html = head + f'<div id="wrap" class="{a.scope}">{text}</div>'
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(executable_path=CHROME)
        except Exception:
            browser = p.chromium.launch(channel="chrome")
        pg = browser.new_page(
            viewport={"width": max(64, int(w)), "height": max(64, int(h))},
            device_scale_factor=scale,
        )
        pg.set_content(html)
        el = pg.locator("#wrap")
        el.screenshot(path=str(out), omit_background=(a.bg == "transparent"))
        browser.close()
    print(f"OK {out} {int(w*scale)}x{int(h*scale)} bg={a.bg}")


if __name__ == "__main__":
    sys.exit(main())
