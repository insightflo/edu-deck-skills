#!/usr/bin/env python3
"""edu-deck-solo 덱 조립기.

[파일 목적]
  슬라이드 HTML 조각(src/*.html)과 스킬 공용 자산(셸, CSS, 아이콘)을 합쳐
  외부 파일이 하나도 필요 없는 단일 HTML 교육 덱을 만든다.

[주요 흐름]
  1. deck.json 에서 제목과 출력 파일 이름을 읽는다(선택 키 summary/glossary 는 자습 레이어용).
  2. assets/shell.html 의 표식 5곳을 채운다.
     제목 ← deck.json title / 추가 CSS ← assets/css/*.css + src/*.css
     아이콘 ← assets/icons/*.svg + src/*.svg 의 symbol·marker / 슬라이드 ← src/*.html (파일 이름순)
     자습 데이터(STUDY_DATA 주석) ← deck.json 의 summary/glossary (window.EDU_STUDY)
  3. 조각 규칙을 검사한다(슬라이드 section 필수, script 금지, 같은 폴더 안 아이콘 id 중복 금지).
  4. 결과 파일을 쓰고 경로·슬라이드 수·크기·남은 자리표시(«…») 수를 출력한다.

[외부 연결]
  입력: 덱 폴더(deck.json, src/), 공통 폴더(edu-deck/shared: assets/shell.html, assets/css, assets/icons, assets/snippets)
  출력: <덱 폴더>/<output> 또는 --gallery 일 때 <출력 폴더>/gallery.html
  다음 단계: scripts/check_deck.py 로 화면 검사

[수정시 주의]
  표식 문자열은 assets/shell.html 과 짝이다. 한쪽만 바꾸면 조립이 실패한다.
  표준 라이브러리만 쓴다(추가 설치 없이 어디서나 실행되도록).
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

from resource_packs import PackError, validate_selection

BASE = Path(__file__).resolve().parent.parent  # edu-deck/shared (공통 자산 폴더)
MARK_TITLE = "{{TITLE}}"
MARK_CSS = "/*EXTRA_CSS*/"
MARK_ICONS = "<!--ICONS-->"
MARK_SLIDES = "<!--SLIDES-->"
MARK_STUDY = "<!--STUDY_DATA-->"
PLACEHOLDER = "«"
ICON_ITEM = re.compile(r"<(symbol|marker)\b[^>]*>.*?</\1>", re.S)
ID_ATTR = re.compile(r'\bid="([^"]+)"')


def strip_comments(text: str) -> str:
    """HTML 주석을 지운 문자열. 자리표시 개수와 <script> 금지를 확인할 때 쓴다."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def read_utf8(path: Path, bom_ok: bool = False) -> str:
    """
    [목적] 덱 파일을 UTF-8 로 읽고, 다른 인코딩이면 파이썬 오류 대신 고칠 방법을 알려 준다.
    [입력] path: 읽을 파일, bom_ok: 메모장 등이 붙이는 BOM 을 허용할지(deck.json 용)
    [출력] 파일 내용 문자열. 읽을 수 없으면 BuildError
    [수정시 영향] 조각·CSS·아이콘·deck.json 읽기 전부가 이 함수를 쓴다.
    """
    try:
        return path.read_text(encoding="utf-8-sig" if bom_ok else "utf-8")
    except UnicodeDecodeError:
        raise BuildError(f"{path.name}: UTF-8 로 저장된 파일이 아닙니다. UTF-8 로 다시 저장하세요")


class BuildError(Exception):
    """조립을 멈춰야 하는 규칙 위반. 메시지는 사용자가 고칠 위치를 알 수 있게 쓴다."""


def natural_key(path: Path):
    """파일 이름 안의 숫자를 숫자로 비교해 2-x.html 이 10-x.html 보다 앞에 오게 한다."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", path.name)]


def collect_css(dirs):
    """
    [목적] 공용·덱 CSS 파일을 순서대로 이어 붙인다.
    [입력] CSS가 들어 있는 폴더 목록(앞쪽이 먼저). 없는 폴더는 건너뛴다.
    [출력] 파일 이름 주석이 붙은 CSS 문자열
    [연결] build() 가 셸의 추가 CSS 표식에 넣는다. 뒤에 오는 덱 CSS가 공용 규칙을 덮어쓸 수 있다.
    [수정시 영향] 순서를 바꾸면 덱의 색·글자 덮어쓰기가 먹지 않을 수 있다.
    """
    parts = []
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.css"), key=natural_key):
            # Pack runtime is loaded explicitly, never into an existing legacy deck.
            if f.name in {"pack-runtime.css", "core.css", "tokens.css", "visual-motion.css", "responsive.css", "viewer.css"}:
                continue
            parts.append(f"/* ---- {f.name} ---- */\n" + read_utf8(f))
    return "\n".join(parts)


def collect_icons(dirs, warnings):
    """
    [목적] 아이콘 파일들에서 <symbol>·<marker>만 뽑아 숨겨진 svg 하나로 합친다.
    [입력] svg 파일이 있는 폴더 목록, 경고를 모을 리스트
    [출력] <svg ...><defs>…</defs></svg> 문자열 (아이콘이 없으면 빈 문자열)
    [연결] 슬라이드의 <use href="#i-…"> 가 이 id를 가리킨다. check_deck.py 가 빠진 id를 검사한다.
    [주의] 같은 폴더 안에서 id가 두 번 나오면 어느 그림이 쓰일지 알 수 없으므로 오류로 멈춘다.
        다른 폴더(공용 → 덱 전용 순)의 같은 id는 뒤 폴더가 덮어쓴다. 덱이 공용 아이콘을
        자기 팔레트로 다시 정의할 수 있게 css_dirs 와 같은 우선 규칙을 따른다.
    [수정시 영향] svg 전체를 복사하도록 바꾸면 주석·스크립트 같은 불필요한 내용이 들어갈 수 있다.
    """
    items, seen = [], {}
    found_dir = False
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.svg"), key=natural_key):
            found_dir = True
            text = read_utf8(f)
            for m in ICON_ITEM.finditer(text):
                item = m.group(0)
                idm = ID_ATTR.search(item[: item.index(">")])
                if not idm:
                    raise BuildError(f"{f}: id 없는 <{m.group(1)}> 가 있습니다")
                iid = idm.group(1)
                prev = seen.get(iid)
                if prev is not None:
                    if prev[0] == d:
                        raise BuildError(f"아이콘 id 중복: '{iid}' ({prev[1]} 와 {f.name})")
                    items[prev[2]] = item
                    seen[iid] = (d, f.name, prev[2])
                else:
                    seen[iid] = (d, f.name, len(items))
                    items.append(item)
    if not found_dir:
        warnings.append("아이콘 파일을 찾지 못했습니다. <use href> 아이콘은 보이지 않습니다.")
    if not items:
        return ""
    return ('<svg aria-hidden="true" style="position:absolute;width:0;height:0;overflow:hidden"><defs>\n'
            + "\n".join(items) + "\n</defs></svg>")


def collect_slides(files):
    """
    [목적] 슬라이드 조각을 검사하고 이어 붙인다.
    [입력] 조각 파일 경로 목록(이미 정렬된 순서)
    [출력] (이어 붙인 HTML, 슬라이드 개수)
    [주의] 조각 안의 <script> 는 금지한다. 동작은 셸 엔진의 단계 속성으로만 만든다.
    [수정시 영향] 검사를 풀면 덱마다 다른 스크립트가 섞여 엔진·검사기와 충돌할 수 있다.
    """
    parts, count = [], 0
    for f in files:
        text = read_utf8(f)
        n = len(re.findall(r'<section\b[^>]*\bclass="slide[\s"]', text))
        if n == 0:
            raise BuildError(f'{f.name}: <section class="slide …"> 로 시작하는 슬라이드가 없습니다')
        # [이유] 조각 머리 주석의 사용 안내에 "<script> 금지" 같은 글이 있어도 오류로 보지 않도록 주석을 지우고 찾는다
        if re.search(r"<script\b", strip_comments(text), re.I):
            raise BuildError(f"{f.name}: 슬라이드 조각에는 <script> 를 넣을 수 없습니다")
        count += n
        parts.append(f"<!-- ==== {f.name} ==== -->\n" + text.strip() + "\n")
    return "\n".join(parts), count


def build(title, slide_files, css_dirs, icon_dirs, out_path, study=None, resource_pack=None):
    """
    [목적] 셸에 제목·CSS·아이콘·슬라이드를 채워 단일 HTML 파일을 쓴다.
    [입력] 제목, 슬라이드 조각 목록, CSS 폴더 목록, 아이콘 폴더 목록, 출력 경로,
      study=deck.json 의 선택 키 summary/glossary (자습 레이어 window.EDU_STUDY 로 주입)
    [출력] (슬라이드 수, 바이트 수, 자리표시 개수, 자리표시가 남은 파일 목록, 경고 목록)
    [연결] main() 의 덱 조립과 갤러리 조립이 함께 쓴다.
    [수정시 영향] 표식 치환 순서를 바꾸면 조각 안에 표식과 같은 글자가 있을 때 잘못 치환될 수 있다.
      그래서 슬라이드를 맨 마지막에 넣는다.
    """
    warnings = []
    assets = BASE / "assets"
    if resource_pack is not None:
        try:
            pack = validate_selection(resource_pack)
        except PackError as exc:
            raise BuildError(str(exc)) from exc
        shell_path = assets / "pack-shell.html"
        required = [assets / "css" / "pack-runtime.css", assets / "packs" / "base.css",
                    assets / "packs" / pack["design"] / "style.css"]
        for path in [shell_path, *required]:
            if not path.is_file():
                raise BuildError(f"필수 리소스팩 자산이 없습니다: {path}")
        css = "\n".join(read_utf8(path) for path in required) + "\n" + collect_css(css_dirs)
    else:
        shell_path = assets / "shell.html"
        css = collect_css(css_dirs)
    shell = read_utf8(shell_path)
    for mark in (MARK_TITLE, MARK_CSS, MARK_ICONS, MARK_SLIDES, MARK_STUDY):
        if shell.count(mark) != 1:
            raise BuildError(f"셸 표식 '{mark}' 이 정확히 1번 있어야 합니다 ({shell_path})")
    slides_html, count = collect_slides(slide_files)
    study_html = ""
    if study:
        # </ 가 들어오면 <script> 가 닫히므로 안전하게 이스케이프한다
        study_html = ('<script>window.EDU_STUDY='
                      + json.dumps(study, ensure_ascii=False).replace("</", "<\\/") + ';</script>')
    out = shell.replace(MARK_TITLE, html.escape(title))
    out = out.replace(MARK_CSS, css)
    out = out.replace(MARK_ICONS, collect_icons(icon_dirs, warnings))
    out = out.replace(MARK_STUDY, study_html)
    out = out.replace(MARK_SLIDES, slides_html)
    if resource_pack is not None:
        metadata = html.escape(json.dumps(pack, ensure_ascii=False), quote=True)
        out = out.replace('</head>', f'<meta name="edu-deck-resource-pack" content="{metadata}">\n</head>', 1)
    # 조각 머리 주석 안의 설명 글자는 세지 않는다(화면에 나오지 않으므로)
    holders = len(re.findall(r"«[^»]*»", strip_comments(slides_html)))
    holder_files = [f.name for f in slide_files if PLACEHOLDER in strip_comments(read_utf8(f))]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out, encoding="utf-8")
    return count, len(out.encode("utf-8")), holders, holder_files, warnings


SLIDE_TAG = re.compile(r'<section\b[^>]*\bclass="slide[\s"][^>]*>', re.S)


def syllable_count(text: str) -> int:
    """읽기 어림 단위: 한글 음절 글자 수 + 한글 아닌 낱말 수."""
    return len(re.findall(r"[가-힯]", text)) + len(re.findall(r"[A-Za-z0-9]+", text))


def strip_tags(fragment: str) -> str:
    return re.sub(r"<[^>]+>", "", fragment)


def rehearsal_rows(files):
    """조각마다 (제목, data-sec, 노트 본문) 를 뽑는다. 표준 라이브러리만 쓴다."""
    rows = []
    for f in files:
        text = strip_comments(read_utf8(f))
        for m in SLIDE_TAG.finditer(text):
            close = text.find("</section>", m.end())
            seg = text[m.end(): close if close > 0 else len(text)]
            attrs = m.group(0)
            sm = re.search(r'data-sec="([0-9.]+)"', attrs)
            sec = float(sm.group(1)) if sm else None
            tm = re.search(r'class="[^"]*\btitle\b[^"]*"[^>]*>(.*?)</', seg, re.S)
            title = strip_tags(tm.group(1)).strip() if tm else ""
            if not title:
                hm = re.search(r"<h[12][^>]*>(.*?)</h[12]>", seg, re.S)
                title = strip_tags(hm.group(1)).strip() if hm else "(제목 없음)"
            nm = re.search(r'<aside\b[^>]*class="[^"]*\bnotes\b[^"]*"[^>]*>(.*?)</aside>', seg, re.S | re.I)
            notes = re.sub(r"\s+", " ", strip_tags(nm.group(1)).strip()) if nm else ""
            rows.append((title, sec, notes))
    return rows


def write_notes(files, out_md, talk):
    """장마다 번호·제목·예정 초·누적·대본 읽기 어림 초·노트를 마크다운으로 쓴다."""
    rate = (talk or {}).get("rate", 300) or 300
    rows = rehearsal_rows(files)
    acc = 0.0
    lines = ["# 발표 리허설 시트", ""]
    total = (talk or {}).get("total")
    if total:
        t = int(total)
        lines.append(f"- 목표 시간 {t // 60}:{t % 60:02d} · 읽기 속도 {rate}음절/분")
        lines.append("")
    for i, (title, sec, notes) in enumerate(rows, 1):
        acc += sec or 0
        est = round(syllable_count(notes) * 60 / rate) if notes else 0
        m, s = int(acc) // 60, int(acc) % 60
        lines.append(f"## {i}. {title}")
        lines.append(f"- 예정 {int(sec) if sec is not None else '미정'}초 · 누적 {m}:{s:02d} · 대본 읽기 어림 {est}초")
        lines.append("")
        lines.append(notes if notes else "(노트 없음)")
        lines.append("")
    Path(out_md).write_text("\n".join(lines), encoding="utf-8")


def load_deck(deck_dir: Path):
    """deck.json 을 읽고 필수 키(title, output)를 확인한다. output 은 덱 폴더 안의 .html 파일 이름이어야 한다."""
    cfg_path = deck_dir / "deck.json"
    if not cfg_path.is_file():
        raise BuildError(f"{cfg_path} 가 없습니다. 예: {{\"title\": \"폭염 안전 교육\", \"output\": \"폭염-교육자료.html\"}}")
    try:
        cfg = json.loads(read_utf8(cfg_path, bom_ok=True))
    except json.JSONDecodeError as e:
        raise BuildError(f"deck.json 형식 오류: {e}")
    if not isinstance(cfg, dict):
        raise BuildError("deck.json 은 객체여야 합니다")
    if "resource_pack" in cfg:
        try:
            validate_selection(cfg["resource_pack"])
        except PackError as exc:
            raise BuildError(str(exc)) from exc
    for key in ("title", "output"):
        if not isinstance(cfg.get(key), str) or not cfg[key].strip():
            raise BuildError(f"deck.json 에 '{key}' 문자열이 필요합니다")
    name = cfg["output"].strip()
    if "/" in name or "\\" in name or not name.endswith(".html"):
        raise BuildError("deck.json 'output' 은 폴더 없이 .html 파일 이름만 씁니다")
    # 선택 키: 자습 레이어(한 장 요약·용어집)와 발표 타이머(talk)가 읽는다. 형태만 확인하고 내용은 각 문서가 안내한다.
    study = {}
    for key in ("summary", "glossary"):
        if key in cfg and cfg[key] is not None:
            if not isinstance(cfg[key], (dict if key == "summary" else list)):
                raise BuildError(f"deck.json '{key}' 은 {'객체' if key == 'summary' else '배열'}여야 합니다")
            study[key] = cfg[key]
    if cfg.get("talk") is not None:
        if not isinstance(cfg["talk"], dict):
            raise BuildError("deck.json 'talk' 은 객체여야 합니다(예: {\"total\":300,\"rate\":300})")
        study["talk"] = cfg["talk"]
    return cfg["title"].strip(), name, study


def main(argv=None):
    """
    [목적] 명령줄 진입점. 덱 조립(기본)과 아키타입 갤러리 조립(--gallery)을 고른다.
    [입력] argv: [덱 폴더] 또는 [--gallery 출력 폴더]
    [출력] 종료 코드 0 성공(경고 있을 수 있음), 1 규칙 위반, 2 사용법 오류
    [연결] SKILL.md 의 조립 단계에서 호출한다.
    """
    ap = argparse.ArgumentParser(description="edu-deck-solo 슬라이드 조각을 단일 HTML 덱으로 조립합니다.")
    ap.add_argument("deck_dir", nargs="?", help="deck.json 과 src/ 가 있는 덱 폴더")
    ap.add_argument("--gallery", metavar="OUT_DIR", help="assets/snippets 전체를 OUT_DIR/gallery.html 로 조립")
    ap.add_argument("--notes", metavar="OUT.md", help="장별 발표 리허설 시트(번호·제목·예정·누적·대본 어림·노트)를 OUT.md 로 씁니다")
    args = ap.parse_args(argv)
    if bool(args.deck_dir) == bool(args.gallery):
        ap.print_usage(sys.stderr)
        print("덱 폴더 또는 --gallery 중 하나만 지정하세요.", file=sys.stderr)
        return 2
    try:
        if args.gallery:
            files = sorted((BASE / "assets" / "snippets").glob("*.html"), key=natural_key)
            if not files:
                raise BuildError("assets/snippets 에 조각이 없습니다")
            out_path = Path(args.gallery).resolve() / "gallery.html"
            result = build("edu-deck-solo 아키타입 갤러리", files,
                           [BASE / "assets" / "css"], [BASE / "assets" / "icons"], out_path)
        else:
            deck_dir = Path(args.deck_dir).resolve()
            title, name, study = load_deck(deck_dir)
            src = deck_dir / "src"
            files = sorted(src.glob("*.html"), key=natural_key) if src.is_dir() else []
            if not files:
                raise BuildError(f"{src} 에 슬라이드 조각(*.html)이 없습니다")
            out_path = deck_dir / name
            cfg = json.loads(read_utf8(deck_dir / "deck.json", bom_ok=True))
            pack = cfg.get("resource_pack")
            css_dirs = [src] if pack is not None else [BASE / "assets" / "css", src]
            # 팩 덱도 공용 아이콘 묶음을 쓸 수 있다(레거시 CSS 는 섞지 않되 아이콘은 허용)
            icon_dirs = [BASE / "assets" / "icons", src]
            result = build(title, files, css_dirs, icon_dirs, out_path,
                           study=study, resource_pack=pack)
            if args.notes:
                write_notes(files, args.notes, cfg.get("talk") or study.get("talk"))
    except (BuildError, OSError) as e:
        print(f"ERROR  {e}", file=sys.stderr)
        return 1
    count, size, holders, holder_files, warnings = result
    for w in warnings:
        print(f"WARN   {w}")
    if holders and not args.gallery:
        print(f"WARN   자리표시 «…» {holders}개가 남았습니다: {', '.join(holder_files)}")
    print(f"OK     {out_path}  slides={count}  bytes={size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
