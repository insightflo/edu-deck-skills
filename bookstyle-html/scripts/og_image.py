#!/usr/bin/env python3
"""카카오톡 미리보기용 대표 그림(1200×675 JPG).

표지(1쪽)를 600×820으로 찍은 뒤, 책 양식의 어두운 무대(#0a0f22) 위에 올려
1200×675 로 맞춘다. 표지가 세로라서 양옆에 무대색이 남는다.

  python3 scripts/og_image.py <결과.html> -o <사이트>/og/<slug>.jpg
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    try:
        from PIL import Image
    except ImportError:
        print("Pillow 가 필요합니다: pip install pillow", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            [sys.executable, str(HERE / "preview.py"), "shot", a.html, "-o", tmp, "--pages", "1"],
            capture_output=True,
            text=True,
        )
        shot = Path(tmp) / "p01.png"
        if r.returncode or not shot.exists():
            sys.stderr.write(r.stderr or r.stdout or "표지 캡처 실패\n")
            return 1
        cover = Image.open(shot).convert("RGB")
    canvas = Image.new("RGB", (1200, 675), (10, 15, 34))
    # fit cover into 675 height, keep aspect
    w, h = cover.size
    nh = 675
    nw = int(w * (nh / h))
    cover = cover.resize((nw, nh), Image.LANCZOS)
    x = (1200 - nw) // 2
    canvas.paste(cover, (x, 0))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    for q in (88, 82, 76, 70, 62):
        buf = io.BytesIO()
        canvas.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        if buf.tell() <= 300_000:
            break
    out.write_bytes(buf.getvalue())
    print(f"완료: {out} (1200×675, {buf.tell() // 1024}KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
