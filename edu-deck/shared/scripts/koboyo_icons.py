#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Koboyo 손그림 IT 아이콘 가져오기 도우미.

[파일 목적]
  사용자가 내려받은 koboyo_gallery.html(손그림 IT 아이콘, koboyo.com/icons)에서
  덱이 실제로 쓰는 아이콘만 골라 <덱>/src/koboyo-icons.svg 로 심볼 단위 복사한다.
  라이브러리 원본은 스킬 폴더·배포물에 절대 복사하지 않는다(라이선스상
  컬렉션 재배포와 도구 번들이 금지되므로, 덱 단위 부분 사용만 허용한다).

[하위 명령]
  search QUERY... [--group G] [--limit 20] [--lib PATH]
      갤러리에서 아이콘을 찾는다. 모든 검색어가 data-search 에
      (대소문자 무시) 들어 있어야 한다. 한 줄에 slug·그룹·제목을 탭으로 출력.
  add DECK_DIR SLUG... [--lib PATH]
      심볼을 <덱>/src/koboyo-icons.svg 에 쓰거나 갱신한다(멱등).
      기존 심볼은 그대로 두고, 전체를 slug 순으로 정렬한다.
      모르는 slug 는 비슷한 후보 5개를 보여 주고 종료 코드 1.
      덱 하나에 심볼 40개 상한(초과 시 아무것도 쓰지 않고 종료 코드 1).
  list DECK_DIR
      덱 파일에 들어 있는 심볼(id·viewBox)을 본다.

[갤러리 파일 위치]
  --lib PATH > 환경변수 EDU_DECK_KOBOYO_LIB > ~/Downloads/koboyo_gallery.html
  파일이 없으면 종료 코드 2. 이 파일은 사용자가 직접 준비하는 자료이므로
  스킬이 대신 만들어 주거나 배포하지 않는다.

[갤러리 구조(기계 생성, 2026-11 기준)]
  <div class="card" data-group="그룹" data-search="slug 제목 키워드…">
    <svg class="ico" role="img" aria-label="slug" xmlns="…" fill="currentColor"
         aria-label="제목" viewBox="0 0 W H"><path d="…"/>…</svg>
  </div>
  aria-label 이 두 번씩 들어 있어 그대로는 올바른 XML 이 아니다. HTML 파서
  관습대로 첫 값을 slug 로 살리고, 둘째 값은 제목으로만 쓰며, 심볼 조립 때
  role·aria-label·xmlns 는 떼어 낸다. 조립 결과는 xml.dom.minidom 으로
  well-formed 를 검증한 뒤 기록한다.
"""
import argparse
import difflib
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
import xml.dom.minidom

ID_PREFIX = "kb-"
OUT_NAME = "koboyo-icons.svg"
MAX_SYMBOLS = 40
DEFAULT_LIB = os.path.join("~", "Downloads", "koboyo_gallery.html")
HEADER = ("<!-- Koboyo hand-drawn icons (koboyo.com/icons, free license; "
          "덱에 쓰는 아이콘만 복사) -->")

# 원시 시작 태그 문자열에서 속성을 다시 뽑는 정규식. [이유] html.parser 는
# 속성 이름을 소문자로 바꿔 전달하므로 대소문자를 지켜야 하는 viewBox 등은
# get_starttag_text() 원문에서 직접 읽어야 한다.
_ATTR = re.compile(
    r'([A-Za-z_:][-\w:.]*)'        # 1: 이름(대소문자 보존)
    r'(?:\s*=\s*'
    r'"([^"]*)"'                   # 2: 값(겹따옴표)
    r"|'([^']*)'"                  # 3: 값(홑따옴표)
    r'|([^\s"\'=<>`]+)'            # 4: 값(따옴표 없음)
    r')?')
_SYMBOL = re.compile(r"<symbol\b[^>]*>.*?</symbol>", re.S)


def esc_attr(value):
    """문자열을 XML 속성값용으로 이스케이프한다."""
    return (value.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))


def esc_text(value):
    """문자열을 XML 텍스트 노드용으로 이스케이프한다."""
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_raw_tag(raw):
    """원시 시작 태그 문자열을 (태그 이름, 스스로 닫힘, [(이름, 값)…])로 푼다.

    [주의] 값은 따옴표를 벗겨 돌려주고, 원래 속성 순서·이름 대소문자를 유지한다.
    """
    body = raw[1:]
    end = body.rfind(">")
    if end >= 0:
        body = body[:end]
    selfclose = False
    stripped = body.rstrip()
    if stripped.endswith("/"):
        selfclose = True
        body = stripped[:-1]
    name_match = re.match(r"\s*([A-Za-z_][-\w:.]*)", body)
    if not name_match:
        return "", selfclose, []
    attrs = []
    rest = body[name_match.end():]
    for found in _ATTR.finditer(rest):
        value = ""
        for group in found.groups()[1:]:
            if group is not None:
                value = group
                break
        attrs.append((found.group(1), value))
    return name_match.group(1), selfclose, attrs


def child_xml(raw, selfclose):
    """svg 안의 자식 시작 태그를 정리된 XML 조각으로 다시 쓴다.

    [이유] 갤러리 svg 는 HTML 문서 안에 있어 xmlns 등이 섞일 수 있고,
    같은 이름의 속성이 반복되면 XML 이 아니게 된다. 첫 속성만 살리고
    나머지는 버린다(HTML 파서 관습과 같다).
    """
    tag, _, attrs = parse_raw_tag(raw)
    seen = set()
    parts = []
    for name, value in attrs:
        low = name.lower()
        if low in seen or low in ("xmlns", "xmlns:xlink"):
            continue
        seen.add(low)
        parts.append(' %s="%s"' % (name, esc_attr(value)))
    tail = "/>" if selfclose else ">"
    return "<%s%s%s" % (tag, "".join(parts), tail)


class _GalleryParser(HTMLParser):
    """div.card 단위로 그룹·검색어·svg 내용을 모은다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.icons = []
        self._card = None
        self._in_svg = False
        self._stack = []
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "div" and self._card is None:
            classes = next((v for n, v in attrs if n == "class"), "").split()
            if "card" in classes:
                self._card = {"group": "", "search": "", "slug": "",
                              "title": "", "viewbox": "", "children": None}
                for name, value in attrs:
                    if name == "data-group" and value:
                        self._card["group"] = value
                    elif name == "data-search" and value:
                        self._card["search"] = value
                return
        if self._card is not None and tag == "svg" and not self._in_svg:
            raw = self.get_starttag_text() or ""
            parsed = parse_raw_tag(raw)
            labels = [v for n, v in parsed[2] if n.lower() == "aria-label"]
            viewbox = next((v for n, v in parsed[2] if n == "viewBox"),
                           next((v for n, v in parsed[2]
                                 if n.lower() == "viewbox"), ""))
            self._card["viewbox"] = viewbox
            self._card["slug"] = (labels[0] if labels
                                  else self._card["search"].split(" ")[0])
            self._card["title"] = labels[1] if len(labels) > 1 else ""
            self._in_svg = True
            self._stack = []
            self._parts = []
            return
        if self._in_svg:
            self._parts.append(child_xml(self.get_starttag_text() or "", False))
            self._stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if not self._in_svg:
            return
        if tag == "svg" and not self._stack:
            self._finish_svg()  # 혹시 <svg/> 꼴이면 바로 닫는다
            return
        self._parts.append(child_xml(self.get_starttag_text() or "", True))

    def handle_data(self, data):
        if self._in_svg and data.strip():
            self._parts.append(esc_text(data))

    def handle_endtag(self, tag):
        if not self._in_svg:
            return
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
            self._parts.append("</%s>" % tag)
        elif tag == "svg" and not self._stack:
            self._finish_svg()

    def _finish_svg(self):
        card = self._card
        card["children"] = "".join(self._parts).strip()
        if card["slug"] and card["children"]:
            self.icons.append(card)
        self._card = None
        self._in_svg = False
        self._stack = []
        self._parts = []

    def close(self):
        super().close()
        if self._in_svg:  # 파일이 svg 닫기 없이 끝나는 만약에 대비
            self._finish_svg()


def resolve_lib(explicit=None):
    """갤러리 파일 경로를 정한다(--lib > EDU_DECK_KOBOYO_LIB > 기본 경로).

    [출력] 찾으면 실제 경로, 없으면 None.
    [주의] --lib 로 직접 지정한 파일이 없으면 다른 후보로 조용히 넘어가지
    않는다(사용자가 가리킨 파일이 없다는 뜻이므로 need_lib 이 종료 코드 2).
    """
    if explicit:
        path = os.path.expanduser(explicit)
        return path if os.path.isfile(path) else None
    for candidate in (os.environ.get("EDU_DECK_KOBOYO_LIB"), DEFAULT_LIB):
        if not candidate:
            continue
        path = os.path.expanduser(candidate)
        if os.path.isfile(path):
            return path
    return None


def need_lib(explicit=None):
    """갤러리 경로를 돌려주거나, 없으면 안내와 함께 종료 코드 2 로 끝낸다."""
    path = resolve_lib(explicit)
    if path:
        return path
    tried = [c for c in (explicit, os.environ.get("EDU_DECK_KOBOYO_LIB"),
                         DEFAULT_LIB) if c]
    if explicit:
        print("ERROR  --lib 로 지정한 갤러리 파일이 없습니다: %s"
              % os.path.expanduser(explicit), file=sys.stderr)
    else:
        print("ERROR  Koboyo 아이콘 갤러리 파일을 찾을 수 없습니다.", file=sys.stderr)
    print("       이 파일은 스킬에 포함되지 않은 사용자 제공 자료이므로"
          " 스킬이 대신 배포하지 않습니다.", file=sys.stderr)
    print("       koboyo.com/icons 에서 내려받은 갤러리 HTML을 준비한 뒤"
          " --lib <경로> 로 지정하거나 환경변수 EDU_DECK_KOBOYO_LIB 를"
          " 설정하세요.", file=sys.stderr)
    print("       확인한 경로: %s" % ", ".join(
        os.path.expanduser(c) for c in tried), file=sys.stderr)
    sys.exit(2)


def load_gallery(path):
    """갤러리 HTML을 읽어 slug → 카드 정보 사전으로 바꾼다.

    [주의] slug 가 겹치면 첫 카드를 살린다(현재 갤러리는 1669개 모두 유일).
    """
    parser = _GalleryParser()
    try:
        parser.feed(Path(path).read_text(encoding="utf-8-sig"))
        parser.close()
    except OSError as exc:
        print("ERROR  갤러리 파일을 읽을 수 없습니다: %s (%s)"
              % (path, exc), file=sys.stderr)
        sys.exit(2)
    icons = {}
    for card in parser.icons:
        icons.setdefault(card["slug"], card)
    return icons


def symbol_xml(slug, card):
    """카드 하나를 <symbol id="kb-…" viewBox="…" fill="currentColor"> 로 조립.

    [주의] role·aria-label·xmlns 는 심볼에 옮기지 않고, 자식 요소는
    중복 속성을 정리한 XML 조각을 그대로 쓴다. 색은 currentColor 를 따른다.
    """
    return ('<symbol id="%s%s" viewBox="%s" fill="currentColor">%s</symbol>'
            % (ID_PREFIX, slug, esc_attr(card["viewbox"]), card["children"]))


def load_existing(path):
    """기존 koboyo-icons.svg 의 심볼 블록을 {slug: 원문}으로 읽는다(멱등용)."""
    path = Path(path)
    if not path.is_file():
        return {}
    blocks = {}
    for found in _SYMBOL.finditer(path.read_text(encoding="utf-8")):
        block = found.group(0)
        id_found = re.search(r'\bid="([^"]+)"', block[:block.index(">")])
        if id_found and id_found.group(1).startswith(ID_PREFIX):
            blocks[id_found.group(1)[len(ID_PREFIX):]] = block.strip()
    return blocks


def write_icon_file(path, symbols):
    """정렬된 심볼 목록을 숨김 svg 로 기록하기 전에 XML 검증을 통과시킨다."""
    lines = [HEADER, '<svg xmlns="http://www.w3.org/2000/svg"'
                    ' style="display:none">', "  <defs>"]
    lines += ["    " + s for s in symbols]
    lines += ["  </defs>", "</svg>"]
    text = "\n".join(lines) + "\n"
    xml.dom.minidom.parseString(text)  # 중복 속성 등이 남으면 여기서 멈춘다
    Path(path).write_text(text, encoding="utf-8")


def cmd_search(args):
    """search: 모든 검색어가 data-search 에 들어 있는 카드를 찾아 출력한다."""
    icons = load_gallery(need_lib(args.lib))
    words = [w.lower() for w in args.query]
    hits = []
    for card in icons.values():
        if args.group and card["group"] != args.group:
            continue
        hay = card["search"].lower()
        if all(word in hay for word in words):
            hits.append(card)
    hits.sort(key=lambda card: card["slug"])
    limit = max(args.limit, 0)
    for card in hits[:limit]:
        print("%s\t%s\t%s" % (card["slug"], card["group"], card["title"]))
    if len(hits) > limit:
        print("(나머지 %d개 생략 — --limit 로 조정)"
              % (len(hits) - limit), file=sys.stderr)
    elif not hits:
        print("검색 결과가 없습니다: %s" % " ".join(args.query), file=sys.stderr)
    return 0


def cmd_add(args):
    """add: 덱 src/koboyo-icons.svg 에 심볼을 추가·갱신한다(멱등)."""
    icons = load_gallery(need_lib(args.lib))
    unknown = [slug for slug in dict.fromkeys(args.slugs) if slug not in icons]
    if unknown:
        names = sorted(icons)
        for slug in unknown:
            near = difflib.get_close_matches(slug, names, n=5)
            print("ERROR  사용할 수 없는 slug '%s': 갤러리에 없습니다. "
                  "비슷한 후보: %s" % (slug, ", ".join(near) if near else "(없음)"),
                  file=sys.stderr)
        print("       search 명령으로 정확한 slug 를 찾아보세요.", file=sys.stderr)
        return 1
    out = Path(args.deck_dir) / "src" / OUT_NAME
    existing = load_existing(out)
    added = [slug for slug in dict.fromkeys(args.slugs) if slug not in existing]
    if len(existing) + len(added) > MAX_SYMBOLS:
        print("ERROR  덱 하나의 koboyo 심볼은 최대 %d개입니다(현재 %d개, 추가 요청 %d개)."
              " 덱 주제에 꼭 필요한 아이콘만 고르세요."
              % (MAX_SYMBOLS, len(existing), len(added)), file=sys.stderr)
        return 1
    merged = dict(existing)
    for slug in added:
        merged[slug] = symbol_xml(slug, icons[slug])
    out.parent.mkdir(parents=True, exist_ok=True)
    write_icon_file(out, [merged[slug] for slug in sorted(merged)])
    print("OK     %s  symbols=%d (added=%d, kept=%d)"
          % (out, len(merged), len(added), len(merged) - len(added)))
    print('       슬라이드에서: <svg class="ico" aria-hidden="true">'
          '<use href="#%sSLUG"/></svg>' % ID_PREFIX)
    return 0


def cmd_list(args):
    """list: 덱에 들어 있는 koboyo 심볼(id·viewBox)을 본다."""
    out = Path(args.deck_dir) / "src" / OUT_NAME
    if not out.is_file():
        print("ERROR  %s 이(가) 없습니다. add 명령으로 먼저 아이콘을 넣으세요."
              % out, file=sys.stderr)
        return 1
    existing = load_existing(out)
    print("%s  symbols=%d" % (out, len(existing)))
    for slug in sorted(existing):
        viewbox = re.search(r'viewBox="([^"]*)"', existing[slug])
        print("  %s%s\t%s" % (ID_PREFIX, slug,
                              viewbox.group(1) if viewbox else ""))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Koboyo 손그림 IT 아이콘을 덱에 골라 담는 도우미"
                    "(라이브러리 원본은 스킬 밖에 둔다).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_search = sub.add_parser(
        "search", help="갤러리에서 아이콘 검색(slug·그룹·제목 출력)")
    p_search.add_argument("query", nargs="+",
                          help="검색어(모든 단어가 data-search 에 있어야 함)")
    p_search.add_argument("--group", help="이 그룹으로 제한"
                          "(ai data dev file interface security status sysdesign tech)")
    p_search.add_argument("--limit", type=int, default=20,
                          help="최대 결과 수(기본 20)")
    p_search.add_argument("--lib", help="갤러리 HTML 경로"
                          "(기본: ~/Downloads/koboyo_gallery.html)")
    p_search.set_defaults(func=cmd_search)
    p_add = sub.add_parser("add", help="덱 src/koboyo-icons.svg 에 심볼 추가")
    p_add.add_argument("deck_dir", help="덱 폴더(deck.json 이 있는 곳)")
    p_add.add_argument("slugs", nargs="+", help="추가할 slug 목록")
    p_add.add_argument("--lib", help="갤러리 HTML 경로")
    p_add.set_defaults(func=cmd_add)
    p_list = sub.add_parser("list", help="덱에 들어 있는 심볼 목록")
    p_list.add_argument("deck_dir", help="덱 폴더")
    p_list.set_defaults(func=cmd_list)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
