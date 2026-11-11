#!/usr/bin/env python3
"""bookstyle-html 빌드: 프로젝트 폴더(book.json + pages/*.html + img/)를 단일 HTML로 묶는다.

사용법
  python3 build_book.py <프로젝트 폴더> [-o 결과.html] [--check]
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import sys
from html import escape
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent / "assets" / "kit"
VERSION = "1.0.0"
PAGE_TYPES = {"cover", "toc", "article", "divider", "story", "evidence", "back", "blank"}
PLACEHOLDER_RE = re.compile(r"TODO|TBD|\{\{|lorem ipsum|여기에 입력", re.I)
IMG_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', re.I)


def die(msg: str, code: int = 1) -> None:
    print(f"[오류] {msg}", file=sys.stderr)
    sys.exit(code)


def load_config(project: Path) -> dict:
    path = project / "book.json"
    if not path.exists():
        die(f"{path} 가 없습니다. assets/template/book.json 을 복사해 시작하세요.")
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"book.json 을 읽지 못했습니다: {e}")
    for key in ("id", "title"):
        if not str(cfg.get(key, "")).strip():
            die(f"book.json 에 {key} 가 필요합니다.")
    return cfg


def load_pages(project: Path) -> list[str]:
    folder = project / "pages"
    single = project / "pages.html"
    if folder.is_dir():
        files = sorted(p for p in folder.glob("*.html") if p.is_file())
        if not files:
            die(f"{folder} 에 HTML 쪽이 없습니다.")
        return [p.read_text(encoding="utf-8").strip() for p in files]
    if single.exists():
        text = single.read_text(encoding="utf-8")
        parts = re.findall(r"<section\b[^>]*class=\"[^\"]*\bpage\b[\s\S]*?</section>", text)
        if not parts:
            die("pages.html 에서 <section class=\"page …\"> 를 찾지 못했습니다.")
        return parts
    die("pages/ 폴더 또는 pages.html 이 필요합니다.")


def embed_images(html: str, project: Path, report: list) -> str:
    def repl(m: re.Match) -> str:
        pre, src, post = m.group(1), m.group(2), m.group(3)
        if src.startswith(("data:", "http://", "https://", "//")):
            return m.group(0)
        path = (project / src).resolve()
        if not path.is_file():
            report.append(f"그림 파일이 없습니다: {src}")
            return m.group(0)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"{pre}data:{mime};base64,{b64}{post}"

    return IMG_SRC_RE.sub(repl, html)


def stamp_pages(pages: list[str], footer: str) -> list[str]:
    out = []
    for i, raw in enumerate(pages, 1):
        html = raw
        if not re.search(r"<section\b", html):
            die(f"{i}쪽: <section> 이 아닙니다.")
        typ = re.search(r'data-type="([^"]*)"', html)
        if typ and typ.group(1) not in PAGE_TYPES:
            die(f"{i}쪽: data-type=\"{typ.group(1)}\" 은 쓸 수 없습니다. {sorted(PAGE_TYPES)}")
        if 'class="' in html and "page" not in (re.search(r'class="([^"]*)"', html).group(1) if re.search(r'class="([^"]*)"', html) else ""):
            die(f"{i}쪽: class 에 page 가 없습니다.")
        if re.search(r'data-pno="[^"]*"', html):
            html = re.sub(r'data-pno="[^"]*"', f'data-pno="{i}"', html, count=1)
        else:
            html = re.sub(r"<section\b", f'<section data-pno="{i}"', html, count=1)
        # footer page number: last <span> inside .pg-foot
        def foot(m: re.Match) -> str:
            inner = m.group(1)
            spans = list(re.finditer(r"(<span\b[^>]*>)(.*?)(</span>)", inner, re.S))
            if len(spans) >= 2:
                last = spans[-1]
                inner = inner[: last.start()] + last.group(1) + str(i) + last.group(3)
            elif footer and len(spans) == 1:
                inner = f"<span>{escape(footer)}</span><span>{i}</span>"
            return f'<div class="pg-foot">{inner}</div>'

        if re.search(r'<div class="pg-foot">', html):
            html = re.sub(r'<div class="pg-foot">(.*?)</div>', foot, html, count=1, flags=re.S)
        out.append(html)
    return out


def lint(pages: list[str]) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    types, ids = [], []
    for i, html in enumerate(pages, 1):
        typ_m = re.search(r'data-type="([^"]*)"', html)
        typ = typ_m.group(1) if typ_m else ""
        types.append(typ)
        if not typ:
            errors.append(f"{i}쪽: data-type 이 없습니다.")
        if typ == "cover" and i != 1:
            warns.append(f"{i}쪽: 표지(cover)는 보통 1쪽에 둡니다.")
        if typ == "back" and i != len(pages):
            warns.append(f"{i}쪽: 뒤표지(back)는 보통 마지막에 둡니다.")
        if PLACEHOLDER_RE.search(re.sub(r"data:[^\"')\s]+", "", html)):  # 내장 그림 base64 는 검사에서 뺀다
            errors.append(f"{i}쪽: 자리 표시 글(TODO/TBD/{{{{)이 남아 있습니다.")
        # empty pc
        pc = re.search(r'<div class="pc">(.*?)</div>\s*(?:<div class="pg-foot"|</section>)', html, re.S)
        if typ in {"article", "story", "toc"} and pc and len(re.sub(r"<[^>]+>", "", pc.group(1)).strip()) < 8:
            errors.append(f"{i}쪽: 본문이 거의 비어 있습니다.")
        for im in re.finditer(r"<img\b[^>]*>", html, re.I):
            tag = im.group(0)
            if "src=" not in tag:
                errors.append(f"{i}쪽: src 없는 그림이 있습니다.")
            if not re.search(r'\balt="', tag):
                errors.append(f"{i}쪽: 그림에 alt 가 없습니다.")
        # figures need captions
        if re.search(r'class="(?:photo|b-figure)"', html) and not re.search(r"<figcaption\b", html):
            errors.append(f"{i}쪽: 사진·그림에 figcaption(출처·설명)이 없습니다.")
        if 'class="nophoto"' in html:
            warns.append(f"{i}쪽: 사진이 없는 빈 칸(.nophoto)이 있습니다. 도식이나 자료 그림으로 채우세요.")
        ids.append(re.search(r'data-id="([^"]*)"', html))
    if types and types[0] != "cover":
        warns.append("1쪽이 표지(cover)가 아닙니다.")
    # data-goto targets
    for i, html in enumerate(pages, 1):
        for g in re.finditer(r'data-goto="(\d+)"', html):
            n = int(g.group(1))
            if n < 1 or n > len(pages):
                errors.append(f"{i}쪽: data-goto=\"{n}\" 대상 쪽이 없습니다.")
    return errors, warns


def og_block(cfg: dict) -> str:
    og = cfg.get("og") or {}
    title = og.get("title") or cfg.get("title") or ""
    desc = og.get("description") or cfg.get("description") or cfg.get("subtitle") or ""
    url = og.get("url") or ""
    image = og.get("image") or ""
    tags = [
        f'<meta property="og:title" content="{escape(title, quote=True)}">',
        f'<meta property="og:description" content="{escape(desc, quote=True)}">',
        '<meta property="og:type" content="website">',
        '<meta name="twitter:card" content="summary_large_image">',
    ]
    if url:
        tags.append(f'<meta property="og:url" content="{escape(url, quote=True)}">')
        tags.append(f'<link rel="canonical" href="{escape(url, quote=True)}">')
    if image:
        tags.append(f'<meta property="og:image" content="{escape(image, quote=True)}">')
        tags.append(f'<meta name="twitter:image" content="{escape(image, quote=True)}">')
    if desc:
        tags.append(f'<meta name="description" content="{escape(desc, quote=True)}">')
    return "\n".join(tags)


def assemble(cfg: dict, pages: list[str]) -> str:
    shell = (KIT / "shell.html").read_text(encoding="utf-8")
    css = (KIT / "book.css").read_text(encoding="utf-8")
    js = (KIT / "viewer.js").read_text(encoding="utf-8")
    title = cfg["title"]
    brand = cfg.get("brand") or title
    n = len(pages)
    html = shell
    html = html.replace("TITLE_BLOCK", f"<title>{escape(title)}</title>")
    html = html.replace("OG_BLOCK", og_block(cfg))
    html = html.replace("CSS_BLOCK", css)
    html = html.replace("JS_BLOCK", js)
    html = html.replace("BRAND_BLOCK", escape(brand))
    html = html.replace("N_BLOCK", str(n))
    html = html.replace("PAGES_BLOCK", "\n".join(pages))
    html = html.replace("bookstyle-html/book 1.0.0", f"bookstyle-html/book {VERSION}")
    return html


def main() -> int:
    ap = argparse.ArgumentParser(description="bookstyle-html 프로젝트를 단일 HTML로 묶는다")
    ap.add_argument("project")
    ap.add_argument("-o", "--out")
    ap.add_argument("--check", action="store_true", help="묶지 않고 검사만")
    a = ap.parse_args()
    project = Path(a.project).resolve()
    if not project.is_dir():
        die(f"프로젝트 폴더가 없습니다: {project}")
    cfg = load_config(project)
    pages = load_pages(project)
    report: list[str] = []
    pages = [embed_images(p, project, report) for p in pages]
    pages = stamp_pages(pages, cfg.get("footer") or cfg.get("title") or "")
    errors, warns = lint(pages)
    errors.extend(report)
    for w in warns:
        print(f"[주의] {w}")
    for e in errors:
        print(f"[오류] {e}")
    if errors:
        return 1
    if a.check:
        print(f"검사 통과: {len(pages)}쪽")
        return 0
    html = assemble(cfg, pages)
    out = Path(a.out) if a.out else project / f"{cfg['id']}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"완료: {out} ({len(pages)}쪽, {out.stat().st_size // 1024}KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
