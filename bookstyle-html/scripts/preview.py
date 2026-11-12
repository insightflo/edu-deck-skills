#!/usr/bin/env python3
"""bookstyle-html 미리보기·점검.

  python3 preview.py check <결과.html>     # 넘침·잘림·깨진 그림 0건이어야 함
  python3 preview.py check <결과.html> --release   # + 배포 게이트(외부 자원·alt·이미지 권리·TODO) 0건
  python3 preview.py sheet <결과.html> [-o 폴더]
  python3 preview.py shot  <결과.html> [-o 폴더] [--pages 1,2]
  python3 preview.py view  <결과.html>     # 1920×1080 화면을 가득 채운 뷰어 캡처(#p1)

크롬 경로: CHROME_PATH 가 있으면 그것을 먼저 쓴다. 없으면 macOS 기본 설치 경로를
먼저 보고, 그다음 리눅스 쪽 실행 이름(google-chrome 등)을 PATH 에서 찾는다.
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

PW, PH = 600, 820

# 절대 경로 후보: 존재 여부를 직접 확인한다. macOS 기본 설치가 첫 후보다.
CHROME_PATHS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    "/workspace/chrome-wrap.sh",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
)
# 실행 이름 후보: PATH 에서 찾는다(리눅스·brew 설치 등).
CHROME_NAMES = ("google-chrome", "chromium", "chromium-browser", "google-chrome-stable")


def chrome_bin() -> str:
    """캡처·검사에 쓸 크롬 실행 파일 경로를 정한다.

    우선순위: CHROME_PATH 환경변수 → macOS 앱 번들 절대 경로 → PATH 의 실행 이름.
    하나도 없으면 안내와 함께 종료한다(호출부는 캡처를 진행할 수 없다).
    """
    env = os.environ.get("CHROME_PATH")
    if env:
        return env
    for c in CHROME_PATHS:
        if Path(c).is_file() and os.access(c, os.X_OK):
            return c
    for c in CHROME_NAMES:
        found = shutil.which(c)
        if found:
            return found
    sys.exit("크롬을 찾지 못했습니다. CHROME_PATH 를 지정하세요.")


def serve(root: Path) -> tuple[int, threading.Thread, object]:
    os.chdir(root)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):  # noqa: ARG002
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return port, t, httpd


# headless Chrome on this box reports innerHeight ≈ windowHeight-87
HEADLESS_CHROME_Y_OFFSET = 0  # headless 창 크기 그대로 캡처(실제 화면 높이는 창보다 조금 작을 수 있음)

def run_chrome(url: str, out_png: Path, width: int, height: int, timeout: int = 60, *, viewport: bool = False) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    win_h = height + HEADLESS_CHROME_Y_OFFSET if viewport else height
    cmd = [
        chrome_bin(),
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        f"--window-size={width},{win_h}",
        "--virtual-time-budget=8000",
        f"--screenshot={out_png}",
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode or not out_png.exists():
        sys.stderr.write(r.stderr or r.stdout or "크롬 캡처 실패\n")
        sys.exit(1)
    if viewport:
        try:
            from PIL import Image
            im = Image.open(out_png)
            if im.size != (width, height):
                im.crop((0, 0, min(width, im.size[0]), min(height, im.size[1]))).save(out_png)
        except ImportError:
            pass


def run_chrome_dump(url: str, width: int, height: int) -> str:
    cmd = [
        chrome_bin(),
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        f"--window-size={width},{height}",
        "--virtual-time-budget=8000",
        "--dump-dom",
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if r.returncode:
        sys.stderr.write(r.stderr or "크롬 dump-dom 실패\n")
        sys.exit(1)
    return r.stdout


# ---------------------------------------------------------------- 배포 게이트 (--release)
# 개념 출처: ko-document-studio © 2026 acc0mplish, MIT — engines/ko-doc/scripts/check_book.py
# (외부 리소스·alt·경고도 실패) + build_book.py(assets[].rights·_todo 수집). 우리 계약으로 재작성.

_EXTERNAL_RE = re.compile(r'(?:src|href)\s*=\s*"((?:https?:)?//[^"]+)"', re.I)
_CSS_URL_RE = re.compile(r'url\(\s*["\']?((?:https?:)?//[^)"\']+)', re.I)
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.I)
_TODO_TEXT_RE = re.compile(r"TODO|TBD|\{\{|lorem ipsum|여기에 입력", re.I)
RIGHTS_OK = {"own", "licensed", "public", "permission"}


def _collect_todos(obj, path="root", out=None):
    """book.json 안의 _todo 메모를 전부 모은다(미해결 사실은 배포 때 보고)."""
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "_todo":
                out.append((path, str(v)))
            else:
                _collect_todos(v, f"{path}.{k}", out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _collect_todos(v, f"{path}[{i}]", out)
    return out


def release_static(html: Path) -> tuple[list[str], list[str], list[str]]:
    """배포 게이트 정적 검사 — (오류, 경고, 정보). --release 없이도 돌리되 심각도가 낮다.

    · 외부 자원: src/href·CSS url(http(s):/프로토콜 상대) → 외부 의존 금지
    · 그림: alt 없음 오류, 빈 alt 경고(bgimg 장식 제외)
    · 이미지 권리: book.json assets[] 의 rights 가 own/licensed/public/permission 밖이면 실패
    · TODO: book.json _todo 메모 + 결과 HTML 의 자리 표시 글 수집
    """
    errors, warns, notes = [], [], []
    text = html.read_text(encoding="utf-8")
    ext = _EXTERNAL_RE.findall(text)
    css_urls = _CSS_URL_RE.findall(text)
    ext = sorted(set(ext + [f"CSS url({u[:80]})" for u in css_urls]))
    if ext:
        errors.append("외부 자원: " + ", ".join(e[:80] for e in ext[:5]) + (" …" if len(ext) > 5 else ""))
    # 내용 그림은 #pages 안의 것만 본다 — 뷰어 크롬(라이트박스 등)의 동적 img 는 제외
    pm = re.search(r'<main id="pages".*?</main>', text, re.S)
    pages_html = pm.group(0) if pm else ""
    page_imgs = _IMG_TAG_RE.findall(pages_html)
    linked = [m for m in page_imgs if 'src="' in m and 'src="data:' not in m]
    for tag in page_imgs:
        src = (tag.split('src="')[1].split('"')[0] if 'src="' in tag else "?")[:60]
        if 'alt="' not in tag and "alt='" not in tag:
            errors.append(f"alt 속성 없는 이미지: {src}")
        elif 'alt=""' in tag and "bgimg" not in tag:
            warns.append(f"alt 가 빈 이미지(장식이 아니라면 설명 필요): {src}")
    if linked:
        errors.append(f"파일로 연결된 이미지 {len(linked)}개 — 배포본은 그림을 인라인(data:)으로 넣어야 합니다")
    hit = _TODO_TEXT_RE.search(re.sub(r"data:[^\"')\s]+", "", text))
    if hit:
        warns.append(f"자리 표시 글({hit.group(0)})이 결과물에 남아 있습니다")
    book = html.parent / "book.json"
    if book.is_file():
        try:
            data = json.loads(book.read_text(encoding="utf-8"))
            for i, a in enumerate(data.get("assets") or []):
                src = str((a or {}).get("src", f"assets[{i}]"))[:60]
                rights = (a or {}).get("rights")
                if rights not in RIGHTS_OK:
                    errors.append(f"이미지 권리 미확인: {src} — rights 를 own|licensed|public|permission 중 기록 (현재: {rights!r})")
            for path, memo in _collect_todos(data):
                warns.append(f"미해결 _todo {path}: {memo[:80]}")
        except (json.JSONDecodeError, OSError) as e:
            warns.append(f"book.json 을 읽지 못해 권리·TODO 를 확인하지 못했습니다: {e}")
    else:
        notes.append("book.json 이 없어 이미지 권리·_todo 를 확인하지 못했습니다")
    return errors, warns, notes


def cmd_check(html: Path, release: bool = False) -> int:
    if release:
        errors, warns, notes = release_static(html)
        for m in notes:
            print(f"[정보] {m}")
        for m in warns:
            print(f"[경고] {m}")
        for m in errors:
            print(f"[오류] {m}")
        if errors or warns:  # 배포 게이트는 경고도 실패다(상류 --release 계약)
            print(f"배포 검사 실패: 오류 {len(errors)} · 경고 {len(warns)}")
            return 1
        print("배포 검사 통과: 외부 자원·alt·이미지 권리·TODO 0건")
    port, _, httpd = serve(html.parent)
    try:
        url = f"http://127.0.0.1:{port}/{html.name}?check=1"
        dom = run_chrome_dump(url, PW + 40, PH * 2)
    finally:
        httpd.shutdown()
    start = dom.find('id="check-result"')
    if start < 0:
        print("[오류] 검사 결과를 찾지 못했습니다.", file=sys.stderr)
        return 1
    # find the script text
    i = dom.find(">", start) + 1
    j = dom.find("</script>", i)
    data = json.loads(dom[i:j])
    issues = 0
    for row in data.get("results", []):
        for it in row.get("issues") or []:
            issues += 1
            print(f"[오류] {row['page']}쪽({row.get('type')}) {it.get('kind')} {it.get('px', '')} {it.get('el') or it.get('src') or it.get('into') or ''}")
    if issues:
        print(f"검사 실패: {issues}건 / {data.get('pages')}쪽")
        return 1
    print(f"검사 통과: {data.get('pages')}쪽, 넘침 0건")
    return 0


def cmd_shot(html: Path, out: Path, pages: list[int] | None, kind: str) -> int:
    port, _, httpd = serve(html.parent)
    # `view`/`sheet` 는 폴더(기본 파일 이름) 또는 .png 파일 경로를 받는다.
    # 파일 경로를 주면 그 이름 그대로 저장해 스크립트 체인이 다루기 쉽게 한다.
    as_file = kind in {"view", "sheet"} and out.suffix.lower() == ".png"
    if as_file:
        out.parent.mkdir(parents=True, exist_ok=True)
        out_dir = out.parent
        view_name = out.name
    else:
        out.mkdir(parents=True, exist_ok=True)
        out_dir = out
        view_name = "view-p1.png" if kind == "view" else "sheet.png"
    try:
        if kind == "view":
            run_chrome(f"http://127.0.0.1:{port}/{html.name}#p1", out_dir / view_name, 1920, 1080, viewport=True)
            print(f"완료: {out_dir / view_name} (1920×1080 화면 가득 채운 표지)")
            return 0
        if kind == "sheet":
            run_chrome(f"http://127.0.0.1:{port}/{html.name}?sheet=6", out_dir / view_name, 1920, 1080, viewport=True)
            print(f"완료: {out_dir / view_name}")
            return 0
        # native page shots
        # count pages from file quickly
        text = html.read_text(encoding="utf-8")
        n = text.count('class="page')  # rough
        targets = pages or [1]
        for p in targets:
            run_chrome(
                f"http://127.0.0.1:{port}/{html.name}?shot={p}",
                out_dir / f"p{p:02d}.png",
                PW,
                PH,
            )
            print(f"완료: {out_dir / f'p{p:02d}.png'} (쪽 {p}, {PW}×{PH})")
    finally:
        httpd.shutdown()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("check", "sheet", "shot", "view"))
    ap.add_argument("html")
    ap.add_argument("-o", "--out", default=".")
    ap.add_argument("--pages", default="", help="쉼표로 구분한 쪽 번호(shot)")
    ap.add_argument("--release", action="store_true",
                    help="check 에 배포 게이트 추가 — 외부 자원·alt·이미지 권리(book.json assets[].rights)·TODO, 경고도 실패")
    a = ap.parse_args()
    html = Path(a.html).resolve()
    if not html.is_file():
        print(f"파일이 없습니다: {html}", file=sys.stderr)
        return 1
    if a.cmd == "check":
        return cmd_check(html, release=a.release)
    pages = [int(x) for x in a.pages.split(",") if x.strip()] if a.pages else None
    return cmd_shot(html, Path(a.out).resolve(), pages, a.cmd)


if __name__ == "__main__":
    sys.exit(main())
