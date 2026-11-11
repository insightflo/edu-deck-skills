#!/usr/bin/env python3
"""style_preset.py — edu-deck 스타일 프리셋(색·모서리 한 벌) 목록·검증·적용.

[파일 목적]
  `shared/presets/<id>.yaml` 에 적어 둔 팔레트 한 벌을, 엔진이 이미 쓰는 색 역할
  이름(tokens.css 의 --paper·--light·--accent 계열)으로 번역해 덱의 CSS 파일로 깔아 준다.
  덱 조각(HTML)은 한 글자도 고치지 않고, shell.html 도 고치지 않는다 — build_deck.py 는
  `src/*.css` 를 이미 자동으로 싣기 때문에 `src/preset.css` 만 생기면 그대로 반영된다.

[주요 흐름]
  1. YAML 을 정규식/라인 파서로 읽는다(PyYAML 없이 표준 라이브러리만 쓴다).
  2. 필수 키·값 형식과 WCAG 대비 6계열(a~f)을 검사한다.
  3. --apply 로 덱(src/preset.css) 또는 책(pages/00-preset.css)에 CSS 를 만든다.

[주의]
  - 대비는 YAML 에 굳힌 hex 로만 판정한다. 렌더링 후 픽셀 대비는 check_deck.py 가 따로 잰다.
  - 생성물에는 [preset-css] 표식을 남긴다. 표식 없는 파일은 손으로 쓴 것으로 보고 덮어쓰지 않는다.
  - bookstyle-html 의 build_book.py 는 pages/*.css 를 자동 포함하지 않는다. --book 은 파일을
    만들고 포함 방법을 안내까지 한다(빌드 스크립트는 이 스킬이 건드리지 않는다).
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

PRESET_DIR = pathlib.Path(__file__).resolve().parent.parent / "presets"
MARKER = "preset-css"
THEMES = ("ocean", "cobalt", "forest", "berry", "cocoa", "graphite", "midnight", "solar")

# YAML 필수 토큰 — 순서가 --list/생성 CSS 의 출력 순서다. 값은 모두 "#rrggbb".
COLOR_KEYS = (
    "paper", "surface", "tint", "line",
    "ink", "ink-2", "ink-3",
    "brand", "brand-text", "brand-tint",
    "accent", "accent-text", "accent-tint",
    "night", "night-2", "night-line", "on-night", "on-night-2",
)
RADIUS_KEYS = ("radius-sm", "radius-md", "radius-lg")
RULE_KEYS = ("no-shadow", "hairline", "min-font")
TEXT_KEYS = ("id", "name", "genre", "recommended_theme", "intent", "use", "avoid")

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
PX_RE = re.compile(r"^(\d{1,3})px$")

# 대비 게이트 — (라벨, 전경, 배경, 기준). 기준은 WCAG 2.1 AA(본문)와 AAA(본문 잉크)를 섞은 우리 규칙.
CONTRAST_GATES = (
    ("a", "ink", "paper", 7.0), ("a", "ink", "surface", 7.0),
    ("b", "ink-2", "paper", 4.5), ("b", "ink-2", "surface", 4.5),
    ("c", "ink-3", "paper", 4.5), ("c", "ink-3", "surface", 4.5),
    ("d", "brand-text", "paper", 4.5), ("d", "brand-text", "surface", 4.5),
    ("d", "brand-text", "brand-tint", 4.5),
    ("e", "accent-text", "paper", 4.5), ("e", "accent-text", "surface", 4.5),
    ("e", "accent-text", "accent-tint", 4.5),
    ("f", "on-night", "night", 7.0), ("f", "on-night", "night-2", 4.5),
    ("f", "on-night-2", "night", 4.5), ("f", "on-night-2", "night-2", 4.5),
)


# ---------------------------------------------------------------- 색 계산
def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """'#rrggbb' → (r, g, b). 형식이 틀리면 ValueError — 검증 단계에서 먼저 걸러진다."""
    v = value.strip().lstrip("#")
    if len(v) != 6:
        raise ValueError(f"hex 형식이 아닙니다: {value}")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def rel_luminance(value: str) -> float:
    """WCAG 2.1 상대휘도. 감마 보정(0.03928 경계)을 그대로 따른다."""
    parts = []
    for c in hex_to_rgb(value):
        s = c / 255
        parts.append(s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4)
    r, g, b = parts
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    """두 색의 대비 비율(1.0~21.0). 순서는 상관없다."""
    la, lb = rel_luminance(fg), rel_luminance(bg)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


# ---------------------------------------------------------------- YAML 읽기
def _strip_comment(line: str) -> str:
    """따옴표 밖의 '#' 뒤를 잘라 낸다. 색값은 따옴표로 감싸 두므로 안전하다."""
    out, quote = [], ""
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (not out or out[-1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _scalar(raw: str):
    """스칼라 변환 — 따옴표 제거, true/false·정수 인식. 그 밖은 문자열 그대로."""
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v in ("true", "false"):
        return v == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def load_yaml_text(text: str) -> dict:
    """2단 깊이까지만 읽는 미니 YAML 파서.

    [입력] 프리셋 YAML 본문. 최상위 `key: value` 와 `section:` + 2칸 들여쓴 하위 키만 지원한다.
    [출력] {'tokens': {...}, 'rules': {...}, 'id': ...} 형태의 dict.
    [주의] 목록(-)·여러 줄 블록(|, >)·앵커는 지원하지 않는다. 프리셋 파일은 그 문법을 쓰지 않는다.
    """
    data: dict = {}
    section = None
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indented = line[0] in " \t"
        body = line.strip()
        key, sep, value = body.partition(":")
        if not sep:
            raise ValueError(f"YAML 형식이 아닙니다: {body!r}")
        key, value = key.strip(), value.strip()
        if indented:
            if not section:
                raise ValueError(f"들여쓴 키의 상위 절이 없습니다: {body!r}")
            data[section][key] = _scalar(value)
            continue
        if value:
            data[key] = _scalar(value)
            section = None
        else:
            section = key
            data[key] = {}
    return data


def load_preset(path: pathlib.Path) -> dict:
    """프리셋 파일 하나를 읽어 {'path','stem','tokens','rules',...} 로 돌려준다."""
    data = load_yaml_text(path.read_text(encoding="utf-8"))
    out = dict(data)
    out["path"] = path
    out["stem"] = path.stem
    out["tokens"] = dict(data.get("tokens") or {})
    out["rules"] = dict(data.get("rules") or {})
    return out


def load_all(folder: pathlib.Path | None = None) -> dict[str, dict]:
    """presets 폴더의 *.yaml 을 id 순으로 모두 읽는다. 파일이 없으면 빈 dict."""
    folder = pathlib.Path(folder or PRESET_DIR)
    return {p.stem: load_preset(p) for p in sorted(folder.glob("*.yaml"))}


# ---------------------------------------------------------------- 검증
def validate(preset: dict) -> list[str]:
    """한 프리셋의 필수 키·형식·대비를 검사해 문제 문자열 목록을 돌려준다(빈 목록 = 통과)."""
    bad: list[str] = []
    for key in TEXT_KEYS:
        if not str(preset.get(key, "")).strip():
            bad.append(f"{key} 값이 비었습니다")
    if preset.get("recommended_theme") not in THEMES:
        bad.append(f"recommended_theme 은 {'|'.join(THEMES)} 중 하나여야 합니다")
    if preset.get("id") != preset.get("stem"):
        bad.append(f"id({preset.get('id')})와 파일명({preset.get('stem')})이 다릅니다")
    tokens = preset["tokens"]
    for key in COLOR_KEYS:
        value = tokens.get(key)
        if not isinstance(value, str) or not HEX_RE.match(value):
            bad.append(f"tokens.{key} 는 '#rrggbb' 여야 합니다 (지금: {value!r})")
    for key in RADIUS_KEYS:
        value = tokens.get(key)
        m = PX_RE.match(str(value or ""))
        if not m or not 0 < int(m.group(1)) <= 96:
            bad.append(f"tokens.{key} 는 '1~96px' 여야 합니다 (지금: {value!r})")
    rules = preset["rules"]
    for key in RULE_KEYS:
        if key not in rules:
            bad.append(f"rules.{key} 가 없습니다")
    for key in ("no-shadow", "hairline"):
        if key in rules and not isinstance(rules[key], bool):
            bad.append(f"rules.{key} 는 true/false 여야 합니다")
    if "min-font" in rules and not (isinstance(rules["min-font"], int) and 12 <= rules["min-font"] <= 48):
        bad.append("rules.min-font 는 12~48 사이 정수여야 합니다")
    if bad:
        return bad
    for label, fg, bg, need in CONTRAST_GATES:
        got = contrast_ratio(tokens[fg], tokens[bg])
        if got + 1e-9 < need:
            bad.append(f"대비 {label} {fg} vs {bg} = {got:.2f} < {need}")
    return bad


def gate_summary(preset: dict) -> tuple[float, list[str]]:
    """가장 빠듯한 게이트의 여유 배수(실제/기준)와 실패 라벨을 돌려준다 — --list 요약용."""
    tokens, worst, failed = preset["tokens"], 9.9, []
    for label, fg, bg, need in CONTRAST_GATES:
        got = contrast_ratio(tokens[fg], tokens[bg])
        worst = min(worst, got / need)
        if got + 1e-9 < need:
            failed.append(f"{label}:{fg}/{bg}={got:.2f}")
    return worst, failed


# ---------------------------------------------------------------- CSS 만들기
def _tok(preset: dict, key: str) -> str:
    return preset["tokens"][key].lower()


def deck_css(preset: dict) -> str:
    """덱용 preset.css — :root 팔레트 + .slide 엔진 연결 + .slide.dark 밤 무대.

    [연결] tokens.css 는 `:root,.slide` 에서 --accent-soft 등을 color-mix 로 다시 계산한다.
           상속값은 직접 선언에 지므로, 장 안에서 쓰이는 파생 토큰은 .slide 블록에서 못 박는다.
    [영향] 이 파일을 src/ 에 두면 build_deck.py 가 자동으로 싣는다(HTML 수정 없음).
    """
    t = preset["tokens"]
    r = preset["rules"]
    lines = [
        f"/* preset.css — \"{preset['name']}\" ({preset['id']}) · {MARKER} 자동 생성물",
        "   [역할] 색과 모서리만 바꾼다. 배치·간격·모션은 엔진 그대로다.",
        "   [연결] :root 가 tokens.css 의 색 역할을 덮고, .slide 가 장마다 다시 계산되는",
        "          파생 토큰(--accent-soft·--light 등)을 이 프리셋 값으로 고정한다.",
        f"   [주의] 직접 고치지 않는다 — 원본은 shared/presets/{preset['id']}.yaml 이다.",
        "          다시 적용하면 이 파일은 통째로 덮어써진다. */",
        ":root{",
        f"  --bg:{_tok(preset, 'paper')};--bg-2:{_tok(preset, 'tint')};"
        f"--paper:{_tok(preset, 'surface')};--line:{_tok(preset, 'line')};",
        f"  --ink:{_tok(preset, 'ink')};--soft:{_tok(preset, 'ink-2')};--mut:{_tok(preset, 'ink-3')};",
        f"  --blue:{_tok(preset, 'brand')};--blue-text:{_tok(preset, 'brand-text')};"
        f"--blue-soft:{_tok(preset, 'brand-tint')};",
        f"  --accent:{_tok(preset, 'accent')};--accent-text:{_tok(preset, 'accent-text')};"
        f"--accent-soft:{_tok(preset, 'accent-tint')};",
        f"  --night:{_tok(preset, 'night')};--night-2:{_tok(preset, 'night-2')};"
        f"--night-line:{_tok(preset, 'night-line')};",
        f"  --on-night:{_tok(preset, 'on-night')};--on-night-2:{_tok(preset, 'on-night-2')};",
        f"  --r-sm:{t['radius-sm']};--r-md:{t['radius-md']};--r-lg:{t['radius-lg']};",
        f"  --preset-hairline:{1 if r['hairline'] else 0};"
        f"--preset-no-shadow:{1 if r['no-shadow'] else 0};--preset-min-font:{r['min-font']}px;",
        "}",
        ".slide{",
        "  --light:var(--bg);--chip:var(--bg-2);",
        "  /* 엔진의 --muted 는 글자가 아니라 '옅은 선·면'이고, 밤 장 안에서도 글자로 쓰인다.",
        "     그래서 캡션 잉크(--mut)를 그대로 넣지 않고, 옅은 바탕과 섞어 양쪽에서 읽히게 한다. */",
        "  --muted:color-mix(in srgb,var(--bg-2) 70%,var(--mut));",
        f"  --accent-light:{_tok(preset, 'accent-tint')};"
        f"--accent-soft:{_tok(preset, 'accent-tint')};",
        f"  --blue-light:{_tok(preset, 'ink-3')};",
        "  --r1:var(--r-sm);--r2:var(--r-md);--r3:var(--r-lg);",
    ]
    if r["no-shadow"]:
        lines.append("  --shadow-1:none;--shadow-2:none;")
    lines += [
        "}",
        "/* 밤 무대 — 엔진의 .dark 규칙은 --ink 를 바탕, --light 를 글자로 쓴다.",
        "   그래서 밤 장에서는 두 이름의 뜻을 밤 토큰으로 바꾸고, 안쪽 .dark·.callout·.pill 은",
        "   밤 토큰으로 다시 칠한다(그대로 두면 밝은 상자 위에 밝은 글자가 된다). */",
        ".slide.dark,.dark.slide{",
        "  background:var(--night);color:var(--on-night);",
        "  --ink:var(--on-night);--soft:var(--on-night-2);--muted:var(--on-night-2);",
        "  --line:var(--night-line);--paper:var(--night-2);--light:var(--night-2);",
        "}",
        ".slide.dark .dark,.dark.slide .dark{background:var(--night-2);color:var(--on-night)}",
        ".slide.dark .callout,.dark.slide .callout{background:var(--night-2);color:var(--on-night)}",
        ".slide.dark .pill,.dark.slide .pill{background:transparent;color:var(--on-night);"
        "border:2px solid var(--night-line)}",
        "",
    ]
    return "\n".join(lines)


def book_css(preset: dict) -> str:
    """책(bookstyle-html)용 오버레이 — book.css 의 토큰 이름으로 같은 팔레트를 옮긴다.

    [연결] book.css 는 --ink --sub --mute --line --bg --paper --tint --accent --accent2
           --navy --mint --stage 를 쓴다. 이름이 덱과 다르므로 표를 따라 옮긴다.
    [주의] build_book.py 는 pages/*.css 를 자동 포함하지 않는다 — 포함 방법은 안내를 출력한다.
    """
    t = preset["tokens"]
    night = _tok(preset, "night")
    lines = [
        f"/* 00-preset.css — \"{preset['name']}\" ({preset['id']}) · {MARKER} 자동 생성물",
        "   책 토큰 이름으로 옮긴 같은 팔레트다. book.css 뒤에 실어야 이긴다.",
        f"   [주의] 원본은 shared/presets/{preset['id']}.yaml 이다. 직접 고치지 않는다. */",
        ":root{",
        f"  --ink:{_tok(preset, 'ink')};--sub:{_tok(preset, 'ink-2')};--mute:{_tok(preset, 'ink-3')};",
        f"  --line:{_tok(preset, 'line')};--bg:{_tok(preset, 'paper')};"
        f"--paper:{_tok(preset, 'surface')};--tint:{_tok(preset, 'tint')};",
        f"  --accent:{_tok(preset, 'brand')};--accent2:{_tok(preset, 'accent')};",
        f"  --navy:{night};--mint:{_tok(preset, 'brand-tint')};",
        "  --stage:radial-gradient(1200px 700px at 50% 40%,"
        f"color-mix(in srgb,{night} 76%,{_tok(preset, 'on-night')}) 0%,"
        f"{night} 55%,color-mix(in srgb,{night} 66%,#000000) 100%);",
        "}",
        "",
    ]
    return "\n".join(lines)


def write_generated(path: pathlib.Path, text: str, force: bool = False) -> None:
    """생성물을 쓴다. 표식 없는 기존 파일은 손으로 쓴 것으로 보고 --force 없이는 거부한다."""
    if path.exists() and not force:
        head = path.read_text(encoding="utf-8", errors="replace")[:400]
        if MARKER not in head:
            raise FileExistsError(
                f"{path} 는 이 도구가 만든 파일이 아닙니다. 덮어쓰려면 --force 를 붙이세요."
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- CLI
def _w(text: str, width: int) -> str:
    """한글 2칸 계산으로 표를 맞춘다(터미널 정렬용)."""
    pad = width - sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)
    return text + " " * max(0, pad)


def cmd_list() -> int:
    presets = load_all()
    if not presets:
        print(f"FAIL   프리셋이 없습니다 — {PRESET_DIR}")
        return 1
    print(f"{_w('id', 18)}{_w('이름', 20)}{_w('장르', 26)}{_w('추천 테마', 12)}"
          f"{_w('주색', 9)}{_w('강조', 9)}{_w('최소', 6)}대비 여유")
    for pid, p in presets.items():
        t = p["tokens"]
        worst, failed = gate_summary(p)
        note = "실패 " + ", ".join(failed) if failed else f"×{worst:.2f}"
        print(f"{_w(pid, 18)}{_w(str(p.get('name', '')), 20)}{_w(str(p.get('genre', '')), 26)}"
              f"{_w(str(p.get('recommended_theme', '')), 12)}{_w(t.get('brand', '?'), 9)}"
              f"{_w(t.get('accent', '?'), 9)}{_w(str(p['rules'].get('min-font', '?')), 6)}{note}")
    print(f"\n프리셋 {len(presets)}종 · 검증은 --verify")
    return 0


def cmd_verify() -> int:
    presets = load_all()
    if not presets:
        print(f"FAIL   프리셋이 없습니다 — {PRESET_DIR}")
        return 1
    total_bad = 0
    for pid, p in presets.items():
        bad = validate(p)
        worst, _ = gate_summary(p)
        if bad:
            total_bad += len(bad)
            print(f"FAIL   {pid}")
            for line in bad:
                print(f"       - {line}")
        else:
            print(f"OK     {pid:18s} 대비 16쌍 · 최소 여유 ×{worst:.2f}")
    if total_bad:
        print(f"\nFAIL   프리셋 {len(presets)}종 중 문제 {total_bad}건")
        return 1
    print(f"\nPASS   프리셋 {len(presets)}종 · 필수 키 {len(COLOR_KEYS) + len(RADIUS_KEYS)}개 · "
          f"대비 게이트 {len(CONTRAST_GATES)}쌍 전수 통과 (a~f, 최소 4.5:1 · 잉크 7.0:1)")
    return 0


def _pick(args) -> tuple[pathlib.Path, str]:
    """--deck / --book 중 하나를 (출력경로, 모드) 로 해석한다. 둘 다/둘 다 없음은 사용법 오류."""
    if bool(args.deck) == bool(args.book):
        raise SystemExit("ERROR   --deck <덱폴더> 또는 --book <책폴더> 중 하나만 지정하세요")
    if args.deck:
        return pathlib.Path(args.deck).resolve() / "src" / "preset.css", "deck"
    return pathlib.Path(args.book).resolve() / "pages" / "00-preset.css", "book"


def cmd_apply(args) -> int:
    presets = load_all()
    preset = presets.get(args.apply)
    if preset is None:
        print(f"ERROR   '{args.apply}' 프리셋이 없습니다. --list 로 id 를 확인하세요.", file=sys.stderr)
        return 2
    bad = validate(preset)
    if bad:
        print(f"ERROR   '{args.apply}' 프리셋이 검증을 통과하지 못합니다:", file=sys.stderr)
        for line in bad:
            print(f"        - {line}", file=sys.stderr)
        return 2
    out, mode = _pick(args)
    text = deck_css(preset) if mode == "deck" else book_css(preset)
    try:
        write_generated(out, text, force=args.force)
    except FileExistsError as e:
        print(f"ERROR   {e}", file=sys.stderr)
        return 2
    print(f"OK     {preset['id']} → {out}")
    if mode == "deck":
        print("       build_deck.py 가 src/*.css 를 자동으로 싣습니다 — HTML 수정 없음")
    else:
        print("       책 빌더는 pages/*.css 를 자동 포함하지 않습니다. build_book.py 로 묶은 뒤")
        print("       결과 HTML 의 book.css <style> 뒤에 이 블록을 붙이거나, 페이지 조각의 <style> 로 옮기세요.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="edu-deck 스타일 프리셋 — 목록·검증·적용",
        epilog="예: style_preset.py --apply seoul-editorial --deck examples/preset-demo",
    )
    ap.add_argument("--list", action="store_true", help="프리셋 표 출력")
    ap.add_argument("--verify", action="store_true", help="전 프리셋 필수 키·대비 전수 검사")
    ap.add_argument("--apply", metavar="ID", help="프리셋을 덱/책에 적용(CSS 생성)")
    ap.add_argument("--deck", metavar="DIR", help="덱 폴더(src/preset.css 생성)")
    ap.add_argument("--book", metavar="DIR", help="책 폴더(pages/00-preset.css 생성)")
    ap.add_argument("--force", action="store_true", help="이 도구가 만든 파일이 아니어도 덮어쓴다")
    args = ap.parse_args(argv)

    if args.list:
        return cmd_list()
    if args.verify:
        return cmd_verify()
    if args.apply:
        return cmd_apply(args)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
