#!/usr/bin/env python3
"""edu-deck 덱 글 추출·되돌리기.

[파일 목적]
  덱 폴더의 슬라이드 조각(src/*.html)에서 화면 글과 발표자 노트를 뽑아
  qa/copy/copy.md 한 파일로 모은다. 말투 교정 스킬(red-pen·humanize-korean·
  im-human)이 고친 copy.md 를 --apply 로 src 에 되돌린다.

[주요 흐름]
  추출(기본): src/*.html 을 조립 순서(build_deck 자연 정렬)로 읽고, 문장 단위마다
    위치 태그 [파일:s번호|힌트] 를 붙여 copy.md 에 쓴다. 머리에는 파일별 sha256 을 남긴다.
    · 화면(s): section.slide 안의 보이는 문장 단위. aside.notes·script·style·pre·code·
      .code·.kbd·.chk-n·aria-hidden 은 제외. svg <text> 는 화면 글이므로 포함(svg>text 힌트).
    · 노트(n): aside.notes 안의 문장 단위.
  되돌리기(--apply): 고친 copy.md 를 읽어 원문과 다른 줄만 src 에 반영한다.
    · 파일 sha256 이 추출 때와 다르면 그 파일 줄은 전부 보류(추출 이후 src 를 손댄 흔적).
    · 화면 줄은 숫자·라틴 단어·「」제목·원번호(①)가 원문과 같아야 반영한다.
    · 사실 칩(.fact)·출처 목록(.src-list)·증거 지표(.stat)·소스 캡션(.sc-src) 줄과
      태그가 섞여 원문 매치가 안 되는 줄은 보류로 돌려 사람이 직접 반영한다.
    · 노트 줄은 문체 교정 범위가 넓으므로 보존 검사를 하지 않는다.
    태그·속성·구조는 바꾸지 않고, 원문 텍스트 조각만 같은 자리의 새 문장으로 바꾼다.
  결과: 바뀐 줄 수·보류 줄 수를 출력하고 qa/copy/apply-report.md 에 전/후를 남긴다.

[외부 연결]
  입력: <덱 폴더>/src/*.html, <덱 폴더>/qa/copy/copy.edited.md (--apply)
  출력: <덱 폴더>/qa/copy/copy.md, <덱 폴더>/qa/copy/apply-report.md
  절차 문서: references/copyedit.md · 다음 단계: build_deck.py 재조립 → check_deck.py 검사

[수정시 주의]
  위치 번호 sNN/nNN 은 파일 안 문장 단위의 문서 순서다. 단위 규칙(BLOCK_TAGS·
  SKIP 규칙)을 바꾸면 추출본과 되돌리기의 번호가 어긋나니 함께 고친다.
  되돌리기는 원문을 HTML 이스케이프한 정규식으로 파일 바이트를 부분 치환한다 —
  bs4 로 다시 직렬화하지 않는다(형식·주석·속성 순서를 보존하기 위해).
"""
import argparse
import hashlib
import html as html_mod
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_deck import natural_key, read_utf8  # noqa: E402

try:
    from bs4 import BeautifulSoup, Comment
except ImportError:
    BeautifulSoup, Comment = None, str

# 문장 단위로 묶는 태그. 이 태그 안의 텍스트(+인라인 자식 텍스트)가 한 줄이 된다.
# svg <text> 는 화면 글이라 단위다. 버튼은 확인 문제 보기·탭 버튼이라 각각 한 줄.
BLOCK_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "dt", "dd",
    "caption", "figcaption", "blockquote", "summary", "div", "section", "aside",
    "article", "header", "footer", "main", "nav", "address", "figure",
    "button", "label", "legend", "option", "output", "text",
}
# 화면 글이 아닌 것(노트는 따로 모은다). svg title·desc 는 접근성 메타라 제외.
SKIP_TAGS = {"script", "style", "pre", "code", "template", "title", "desc"}
SKIP_CLASSES = {"code", "kbd", "chk-n", "ph"}  # 코드 상자·키 캡·문제 번호·칸 자리표시
# 수치·이름·출처가 박힌 단위 — 편집하면 보류로 돌리고 힌트에 '보호' 를 붙인다.
PROTECT_CLASSES = {"fact", "src-list", "sc-src", "stat"}
# 화면 줄 보존 검사: 숫자·원번호·라틴 단어·「」제목은 원문과 같아야 한다.
KEEP_NUM = re.compile(r"\d+(?:[.,]\d+)*|[①-⑳]")
KEEP_LATIN = re.compile(r"[A-Za-z]+(?:[.'’\-][A-Za-z]+)*")
KEEP_QUOTE = re.compile(r"「[^」]*」")
LINE_RE = re.compile(r"^\s*-\s*\[([^\]:|]+):([sn])(\d+)(?:\|[^\]]*)?\]\s*(.*)$")
# 추출본 머리의 파일 해시 줄.
SHA_RE = re.compile(r"^# sha256 (\S+) = ([0-9a-f]{64})\s*$")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def soup_of(path):
    return BeautifulSoup(read_utf8(path), "html.parser")


def skip_reason(node):
    """텍스트 노드가 화면 추출 대상 밖인 이유. 대상이면 None."""
    p = node.parent
    while p is not None and getattr(p, "name", None):
        if p.name in SKIP_TAGS:
            return "tag"
        if set(p.get("class") or ()) & SKIP_CLASSES:
            return "class"
        if (p.get("aria-hidden") or "") == "true":
            return "hidden"
        p = p.parent
    return None


def owner_of(node):
    """텍스트 노드의 문장 단위(가장 가까운 BLOCK_TAGS 조상)."""
    p = node.parent
    while p is not None and getattr(p, "name", None):
        if p.name in BLOCK_TAGS:
            return p
        p = p.parent
    return None


def el_hint(el):
    """단위 힌트: 태그.주요클래스 (svg 는 svg> 접두)."""
    cls = "." + ".".join(el.get("class") or []) if el.get("class") else ""
    return ("svg>" if el.find_parent("svg") else "") + el.name + cls


def slide_title(sec):
    """장 제목: check_deck.slide_title 과 같은 선택자 순서."""
    for sel in (".title", ".big", ".pack-prompt"):
        el = sec.select_one(sel)
        if el and el.get_text(strip=True):
            return re.sub(r"\s+", " ", el.get_text(" ", strip=True))
    for tag in ("h1", "h2"):
        el = sec.find(tag)
        if el and el.get_text(strip=True):
            return re.sub(r"\s+", " ", el.get_text(" ", strip=True))
    return "(제목 없음)"


def norm_text(nodes):
    """텍스트 노드들을 한 줄 정규화 문자열로(공백 하나로 붙인다)."""
    return re.sub(r"\s+", " ", " ".join(str(n).strip() for n in nodes)).strip()


def file_units(path):
    """
    [목적] 조각 파일의 문장 단위를 문서 순서로 모은다.
    [출력] (장 목록, 단위 목록). 장 = (슬라이드 제목, 그 장의 단위 목록).
      단위 = {key,bucket,hint,text,protected,svg,mixed,nodes,el}
      key 는 파일 안 번호(s01…화면 / n01…노트)로 apply 의 위치 태그와 짝이다.
    [주의] mixed 는 소유 텍스트 노드 사이에 태그가 끼어 있는 단위 — 원문이 한 덩어리로
      파일에 없으므로 되돌리기에서 보류 처리한다.
    """
    soup = soup_of(path)
    units, slides = [], []
    owned = {}          # id(el) → unit
    counters = {"s": 0, "n": 0}
    for sec in soup.find_all("section", class_="slide"):
        sec_units = []
        for node in sec.find_all(string=True):
            if Comment is not str and isinstance(node, Comment):
                continue
            if not str(node).strip() or skip_reason(node):
                continue
            svg = node.find_parent("svg") is not None
            if svg and node.find_parent("text") is None:
                continue  # svg title·desc 등 글자 아닌 텍스트
            owner = owner_of(node)
            if owner is None:
                continue
            in_notes = ((owner.name == "aside" and "notes" in (owner.get("class") or []))
                        or owner.find_parent("aside", class_="notes"))
            bucket = "n" if in_notes else "s"
            uid = id(owner)
            if uid not in owned:
                counters[bucket] += 1
                protected = bool(
                    owner.find_parent(class_=lambda c: c and bool(set(c.split()) & PROTECT_CLASSES))
                    or set(owner.get("class") or ()) & PROTECT_CLASSES)
                unit = {"key": f"{bucket}{counters[bucket]:02d}", "bucket": bucket,
                        "hint": el_hint(owner), "nodes": [], "svg": svg,
                        "protected": protected, "mixed": False, "el": owner}
                owned[uid] = unit
                units.append(unit)
                sec_units.append(unit)
            owned[uid]["nodes"].append(node)
        slides.append((slide_title(sec), sec_units))
    for unit in units:
        unit["text"] = norm_text(unit["nodes"])
        # 소유 텍스트 노드 사이에 태그가 끼어 있으면 원문이 파일에 한 덩어리로 없다.
        seen, gap = False, False
        owned_set = {id(n) for n in unit["nodes"]}
        for d in unit["el"].descendants:
            if getattr(d, "name", None):      # 태그
                if seen:
                    gap = True
            elif id(d) in owned_set:          # 소유 텍스트 노드
                if gap:
                    unit["mixed"] = True
                    break
                seen = True
    return slides, units


def find_src(deck_dir):
    """덱 폴더의 src/*.html 을 조립 순서로 돌려준다."""
    src = deck_dir / "src"
    if not src.is_dir():
        return []
    return sorted(src.glob("*.html"), key=natural_key)


def deck_title(deck_dir):
    try:
        cfg = json.loads(read_utf8(deck_dir / "deck.json", bom_ok=True))
        return cfg.get("title") or deck_dir.name
    except (OSError, ValueError, KeyError):
        return deck_dir.name


# ---------------------------------------------------------------- 추출
def cmd_extract(deck_dir):
    """src/*.html → qa/copy/copy.md. 출력 경로와 줄 수를 출력한다."""
    files = find_src(deck_dir)
    if not files:
        print(f"ERROR  {deck_dir}/src 에 슬라이드 조각(*.html)이 없습니다", file=sys.stderr)
        return 1
    out_dir = deck_dir / "qa" / "copy"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "copy.md"
    lines = [
        "# copy.md — 화면 글·노트 교정 추출본",
        f"# 덱: {deck_title(deck_dir)}",
        "# 규칙: '- [파일:번호|힌트] 내용' 줄의 내용만 고친다. 위치 태그·# 머리줄·## 장 제목은 바꾸지 않는다.",
        "# 힌트 '보호' = 사실 칩·출처·증거 지표 — 수치·이름 수정 금지(고치면 보류로 돌아온다).",
        "# 되돌리기: 이 파일을 copy.edited.md 로 저장한 뒤",
        "#   python3 <base>/scripts/extract_copy.py <덱 폴더> --apply qa/copy/copy.edited.md",
    ]
    for f in files:
        lines.append(f"# sha256 {f.name} = {sha256(f)}")
    n_screen = n_notes = slide_no = 0
    for f in files:
        slides, _units = file_units(f)
        for title, sec_units in slides:
            slide_no += 1
            s_units = [u for u in sec_units if u["bucket"] == "s"]
            n_units = [u for u in sec_units if u["bucket"] == "n"]
            lines.append("")
            lines.append(f"## {slide_no:02d} {f.name} — {title}")
            lines.append("### 화면")
            if not s_units:
                lines.append("- (화면 글 없음)")
            for u in s_units:
                protect = "·보호" if u["protected"] else ""
                lines.append(f"- [{f.name}:{u['key']}|{u['hint']}{protect}] {u['text']}")
            lines.append("### 노트")
            if not n_units:
                lines.append("- (노트 없음)")
            for u in n_units:
                lines.append(f"- [{f.name}:{u['key']}|{u['hint']}] {u['text']}")
            n_screen += len(s_units)
            n_notes += len(n_units)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK     {out}  slides={len(files)}  화면 {n_screen}줄 · 노트 {n_notes}줄")
    return 0


# ---------------------------------------------------------------- 되돌리기
# 원문에 엔티티로 적혀 있을 수 있는 글자들 — 되돌리기 때 그 글자 또는 아무 엔티티에나 매치.
SPECIAL_CHARS = set("&<>\"'’‘“”—–·…→←↑↓\u00a0")
ENT = r"&[#A-Za-z0-9]+;"


def raw_flex(text):
    """파싱된 문장 → 파일 원문 정규식(공백·엔티티 허용). 매치 1곳일 때만 치환한다."""
    out = []
    for ch in text:
        if ch.isspace():
            out.append("(\\s|" + ENT + ")+")
        elif ch in SPECIAL_CHARS:
            out.append("(" + re.escape(ch) + "|" + ENT + ")")
        else:
            out.append(re.escape(ch))
    return re.compile("".join(out))


def kept_ok(orig, new):
    """화면 줄 보존 검사: 숫자·원번호·라틴 단어·「」제목이 원문과 같은 순서로 같아야 True."""
    return all(rx.findall(orig) == rx.findall(new) for rx in (KEEP_NUM, KEEP_LATIN, KEEP_QUOTE))


def parse_md(path):
    """copy.md 계열 파싱 → ({파일명: sha256}, [(파일명, key, 텍스트), ...])."""
    hashes, rows = {}, []
    for ln in read_utf8(path).splitlines():
        m = SHA_RE.match(ln)
        if m:
            hashes[m.group(1)] = m.group(2)
            continue
        m = LINE_RE.match(ln)
        if m:
            rows.append((m.group(1), f"{m.group(2)}{m.group(3)}", m.group(4).rstrip()))
    return hashes, rows


def cmd_apply(deck_dir, edited_path):
    """편집본 copy.edited.md → src 반영. 반환 0=정상 종료(보류 포함)."""
    edited = Path(edited_path)
    if not edited.is_absolute():
        edited = deck_dir / edited
    if not edited.is_file():
        print(f"ERROR  편집본이 없습니다: {edited}", file=sys.stderr)
        return 2
    hashes, rows = parse_md(edited)
    # 파일 단위 재추출 — 추출본 key 와 같은 규칙으로 번호를 다시 매긴다.
    files = find_src(deck_dir)
    if not files:
        print(f"ERROR  {deck_dir}/src 에 슬라이드 조각(*.html)이 없습니다", file=sys.stderr)
        return 2
    units_of, raw_of = {}, {}
    for f in files:
        _, units = file_units(f)
        units_of[f.name] = {u["key"]: u for u in units}
        raw_of[f.name] = read_utf8(f)
    # 추출 이후 손댄 파일은 그 파일의 모든 편집을 보류한다.
    stale = {name for name, h in hashes.items()
             if (deck_dir / "src" / name).is_file() and sha256(deck_dir / "src" / name) != h}
    changed, deferred = [], []
    for fname, key, new_text in rows:
        loc = f"{fname}:{key}"
        unit = units_of.get(fname, {}).get(key)
        if unit is None:
            deferred.append((loc, "위치 태그가 추출본과 다름", "", new_text))
            continue
        orig = unit["text"]
        if new_text == orig:
            continue
        why = None
        if fname in stale:
            why = "추출 후 src 파일이 바뀜(sha256 불일치)"
        elif unit["protected"]:
            why = "보호 단위 — 사실 칩·출처·지표는 수동 반영"
        elif unit["mixed"]:
            why = "태그가 섞인 단위 — 수동 반영"
        elif unit["bucket"] == "s" and not kept_ok(orig, new_text):
            why = "숫자·라틴 단어·「」제목이 원문과 다름"
        if why:
            deferred.append((loc, why, orig, new_text))
            continue
        rx = raw_flex(orig)
        hits = list(rx.finditer(raw_of[fname]))
        if len(hits) != 1:
            deferred.append((loc, f"원문 매치 {len(hits)}곳 — 수동 반영", orig, new_text))
            continue
        safe = html_mod.escape(new_text, quote=False)
        raw_of[fname] = raw_of[fname][:hits[0].start()] + safe + raw_of[fname][hits[0].end():]
        changed.append((loc, unit["hint"], orig, new_text))
    for name, raw in raw_of.items():
        p = deck_dir / "src" / name
        if p.read_text(encoding="utf-8") != raw:
            p.write_text(raw, encoding="utf-8")
    out_dir = deck_dir / "qa" / "copy"
    out_dir.mkdir(parents=True, exist_ok=True)
    rp = out_dir / "apply-report.md"
    lines = ["# apply-report.md — 되돌리기 결과",
             f"# 바뀐 줄 {len(changed)} · 보류 {len(deferred)}", "", "## 바뀐 줄"]
    for loc, hint, before, after in changed:
        lines += [f"### {loc} ({hint})", f"- 전: {before}", f"- 후: {after}", ""]
    lines.append("## 보류")
    for loc, why, before, after in deferred:
        lines += [f"### {loc} — {why}", f"- 전: {before}", f"- 후(보류): {after}", ""]
    rp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK     {rp}  changed={len(changed)}  보류={len(deferred)}")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="덱 src 조각에서 화면 글·노트를 qa/copy/copy.md 로 추출하거나, "
                    "교정본(--apply)을 src 에 되돌린다.")
    ap.add_argument("deck", help="덱 폴더(src/·deck.json 이 있는 곳)")
    ap.add_argument("--apply", metavar="EDITED.md",
                    help="교정이 끝난 copy.edited.md — 매칭되는 문장만 src 에 되돌린다")
    args = ap.parse_args()
    if BeautifulSoup is None:
        print("ERROR  bs4(BeautifulSoup)이 필요합니다 — check_deck.py 와 같은 의존성", file=sys.stderr)
        return 2
    deck_dir = Path(args.deck).resolve()
    if not deck_dir.is_dir():
        print(f"ERROR  덱 폴더가 없습니다: {deck_dir}", file=sys.stderr)
        return 2
    if args.apply:
        return cmd_apply(deck_dir, args.apply)
    return cmd_extract(deck_dir)


if __name__ == "__main__":
    sys.exit(main())