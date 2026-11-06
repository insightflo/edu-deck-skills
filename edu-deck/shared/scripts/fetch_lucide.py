#!/usr/bin/env python3
"""Lucide 아이콘 사본 갱신 — 네트워크가 있을 때만 실행한다.

산출: assets/kit/vendor/lucide-subset.json — {icons, library, license, version}.
icons 는 이름 → 내부 요소 문자열(24×24 viewBox 기준, stroke 는 CSS 가 준다).

사용: python3 scripts/fetch_lucide.py [--version 1.69.0] [--icons a b c ...]
ICONS 목록은 스니펫·팩이 쓰는 이름 전체다. 사본 밖 이름은 stack_schema.py 가
형태 오류로 잡으므로 목록에 없는 아이콘을 쓰려면 여기에 먼저 추가한다.
"""
import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "assets" / "kit" / "vendor" / "lucide-subset.json"

# 사본에 담는 아이콘 — assets/kit/vendor/lucide-subset.json 의 이름과 반드시 같다.
# 선 아이콘만. 브랜드 로고·상표 마크는 두지 않는다.
ICONS = [
    "archive", "arrow-down", "arrow-left", "arrow-right", "arrow-up", "award", "bell",
    "book-open", "bot", "box", "brain", "briefcase", "building", "building-2", "calendar",
    "camera", "chart-column", "chart-line", "chart-pie", "check", "circle-check",
    "circle-x", "clipboard-check", "clipboard-list", "clock", "cloud", "code", "cpu",
    "credit-card", "database", "download", "eye", "file", "file-check", "file-search",
    "file-signature", "file-text", "filter", "flag", "folder", "gavel", "git-branch",
    "globe", "graduation-cap", "handshake", "hard-drive", "heart", "house", "key",
    "laptop", "layers", "layout-dashboard", "lightbulb", "link", "list-checks", "lock",
    "mail", "map-pin", "message-square", "messages-square", "mic", "monitor", "network",
    "package", "pencil", "phone", "printer", "qr-code", "receipt", "refresh-cw", "repeat",
    "rocket", "scale", "scan-search", "search", "send", "server", "settings", "share-2",
    "shield-check", "smartphone", "sparkles", "star", "store", "tablet", "target",
    "terminal", "thumbs-up", "trash-2", "trending-up", "triangle-alert", "truck", "upload",
    "user", "user-round", "users", "wallet", "wifi", "workflow", "wrench", "zap",
]

INNER = re.compile(r'^<svg\b[^>]*>(.*)</svg>\s*$', re.S)


def fetch(version):
    url = f"https://github.com/lucide-icons/lucide/releases/download/{version}/lucide-static-{version}.zip"
    try:
        with urlopen(url, timeout=60) as r:
            data = r.read()
    except Exception as e:
        sys.exit(f"내려받기 실패({url}): {e}\n네트워크 없이는 기존 사본을 그대로 쓴다 — 이 스크립트는 생략 가능하다.")
    icons = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = {n.rsplit("/", 1)[-1]: n for n in z.namelist() if n.endswith(".svg")}
        for want in ICONS:
            path = names.get(f"{want}.svg")
            if not path:
                sys.exit(f"사본 안에 {want}.svg 없음 — ICONS 목록을 확인한다")
            m = INNER.match(z.read(path).decode("utf-8").strip())
            if not m:
                sys.exit(f"{want}.svg 형태가 예상과 다르다")
            icons[want] = m.group(1).strip()
    return {"icons": icons, "library": "lucide-static",
            "license": "ISC (https://lucide.dev/license)", "version": version}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.69.0")
    ap.add_argument("--icons", nargs="*", default=None,
                    help="이 이름들만 담는다(기본: ICONS 목록 전체)")
    a = ap.parse_args()
    global ICONS
    if a.icons:
        ICONS = a.icons
    o = fetch(a.version)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(o, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"OK {OUT} — {len(o['icons'])}개 아이콘, lucide-static {a.version}")


if __name__ == "__main__":
    main()
