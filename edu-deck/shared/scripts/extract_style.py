#!/usr/bin/env python3
"""extract_style.py — 소스 실측 기반 스타일 추출 → edu-deck preset.css 생성.

[파일 목적]
  README·마크다운·HTML/CSS·JSON·이미지 같은 소스 자료를 직접 계량해(실측) 그 자료의
  톤과 매너를 edu-deck 스타일 토큰 한 벌(preset.css)로 옮긴다. 참고 개념:
  소스가 정한 모습을 측정해 스타일을 끌어낸다는 'source-measured style extraction'
  (awesomezun/awesome-showreels, MIT — 개념만 참조하고 코드는 이 저장소에서 새로 작성).

[주요 흐름]
  1. --source 입력을 모은다: GitHub repo URL 이면 API 메타 + raw README 를 가져오고,
     로컬 폴더/파일은 확장자별로 스캔한다(.env*·키·인증서 등 비밀 파일, .git·
     node_modules 등은 제외). 네트워크가 없으면 --offline 또는 실패 시 건너뛴다.
  2. 문서를 계량한다: HTML/CSS 에서 hex 색(배경/글자/선/강조 맥락)·font-family·
     border-radius·font-size·box-shadow, Markdown 에서 코드블록/셸 명령/이모지/
     느낌표/수치/헤징/인용 비율, 이미지는 Pillow 가 있으면 주요 색(없으면 건너뜀).
     모든 관측에는 근거 ID(E1, E2, ...)를 붙인다.
  3. 톤 축 8개(energy·playful·technical·serious·warm·luxe·dark·data, 0..1)를
     실측 신호로 계산하고 각 축이 어떤 근거에서 나왔는지 기록한다.
  4. 색 팔레트를 만든다: 실측 색을 중성/유채색·밝기로 나눠 18개 토큰(style_preset.py
     의 COLOR_KEYS 와 동일)에 배정하고, 없는 자리는 기본값/파생값으로 채운 뒤
     ensure_contrast() 가 CONTRAST_GATES 16쌍과 check_deck 행렬 항목을 전부
     통과할 때까지 전경/배경을 밝기 방향으로 보정한다.
  5. 출력한다: preset.css(--deck 또는 --out-css)와 선택 보고물 — --board(qa/style-board.html),
     --json(qa/style-extract.json), --md(qa/style-extract.md).

[외부 연결]
  출력 CSS 는 style_preset.py 의 deck_css() 와 같은 마커·:root 토큰·.slide·
  .slide.dark 블록 계약을 따른다 — build_deck.py 가 src/*.css 로 자동 탑재하고
  check_deck.py 대비 행렬이 그대로 적용된다. 검증에는 style_preset.py 의
  CONTRAST_GATES·contrast_ratio·validate 를 같은 디렉터리에서 import 해 쓴다.
  표준 라이브러리만 쓰고 Pillow 는 선택(없으면 이미지 색 추출을 건너뛰고 경고).

[수정시 주의]
  토큰 이름·CSS 블록 구조를 바꾸면 style_preset.py·check_deck.py 계약이 깨진다.
  대비 보정 순서(밝은 배경 → 잉크 → 브랜드/강조 글자 → tint → 밤 무대)는 의존
  관계가 있으니 함부로 바꾸지 않는다. 축 공식은 휴리스틱이며 근거 ID 를 반드시 남긴다.
"""
from __future__ import annotations

import argparse
import collections
import colorsys
import datetime
import html as html_mod
import os
import json
import math
import pathlib
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from style_preset import (  # noqa: E402
    CONTRAST_GATES, THEMES as THEME_IDS, contrast_ratio, hex_to_rgb,
    rel_luminance, validate as validate_preset, write_generated,
)
from tone_router import THEMES as THEME_SIGNATURES  # noqa: E402

VERSION = "1.0.0"
MARKER = "preset-css"
AXES = ("energy", "playful", "technical", "serious", "warm", "luxe", "dark", "data")

# 스캔 대상 확장자. 이미지는 Pillow 가 있을 때만 픽셀을 읽는다(없으면 이름만 기록).
MD_EXT = {".md", ".markdown", ".mdx", ".txt"}
HTML_EXT = {".html", ".htm"}
CSS_EXT = {".css"}
DATA_EXT = {".json", ".yaml", ".yml", ".toml", ".xml"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
SVG_EXT = {".svg"}

# 비밀·머신 파일은 스캔하지 않는다(파일 이름 기준).
SECRET_RE = re.compile(
    r"(^|\.)(env|envrc|netrc|npmrc|pypirc|htpasswd|pem|key|p12|pfx|jks|keystore|kdbx)$"
    r"|(^|[._-])(secret|secrets|credential|credentials|token|apikey|api_key|passwd|password)([._-]|$)"
    r"|id_rsa|id_dsa|id_ecdsa|id_ed25519|\.ovpn$|\.asc$|\.gpg$",
    re.I,
)
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__",
    "dist", "build", "out", ".next", ".nuxt", ".cache", ".idea", ".vscode",
    "coverage", ".tox", ".pytest_cache", "site-packages", "vendor",
}
MAX_FILES = 600          # 한 폴더 스캔 상한
MAX_IMAGES = 60          # 이미지 상한
MAX_TEXT_BYTES = 512_000  # 텍스트 파일 1개 읽기 상한
FETCH_BYTES = 1_500_000   # URL fetch 상한
FETCH_TIMEOUT = 12

HEX6_RE = re.compile(r"#([0-9a-fA-F]{6})\b")
HEX_ANY_RE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
RGB_RE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})")
DECL_RE = re.compile(r"([\w-]+)\s*:\s*([^;{}]+)")
FENCE_RE = re.compile(r"```[\s\S]*?(?:```|$)")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿⬀-⯿️\U0001FB00-\U0001FBFF]"
)
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
GITHUB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
)
GITSSH_RE = re.compile(r"git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$")
META_THEME_RE = re.compile(
    r'<meta[^>]+name=["\']theme-color["\'][^>]+content=["\'](#[0-9a-fA-F]{3,8})'
    r"|<meta[^>]+content=['\"](#[0-9a-fA-F]{3,8})[\"'][^>]+name=[\"']theme-color",
    re.I,
)
SHELL_LINE_RE = re.compile(
    r"^\s*(?:\$|>|❯)\s*\w|^\s*(npm|npx|pnpm|yarn|pip|pip3|python3?|node|git|curl|wget|"
    r"brew|cargo|docker|kubectl|make|cd|export|chmod|apt|apt-get|brew|uv|poetry)\b"
)
FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;{}]+)", re.I)
FONT_SIZE_RE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", re.I)
RADIUS_RE = re.compile(r"border(?:-[a-z]+-)?radius\s*:\s*(\d+(?:\.\d+)?)px", re.I)
BORDER_W_RE = re.compile(r"border(?:-width)?\s*:\s*(\d+(?:\.\d+)?)px", re.I)
SHADOW_RE = re.compile(r"box-shadow\s*:\s*([^;{}]+)", re.I)

SERIF_HINTS = ("serif", "georgia", "times", "playfair", "garamond", "baskerville",
               "merriweather", "lora", "noto serif", "nanum myeongjo", "source serif",
               "libertinus", "crimson")
MONO_HINTS = ("mono", "courier", "consolas", "menlo", "jetbrains", "fira code",
              "source code", "cascadia", "ibm plex mono", "d2coding", "hack")

# 축 신호어 — 한국어·영어 혼합 문서에서 부분 문자열로 센다(tone_router 와 같은 방식).
WORDS = {
    "energy": (["차분", "천천", "정적", "독서"],
               ["지금", "바로", "빠르", "즉시", "간단", "쉽", "새로운", "new", "fast",
                "quick", "easy", "instantly", "just", "simply", "launch", "try"]),
    "playful": (["격식", "공식", "규정", "엄격"],
                ["재미", "놀이", "게임", "유쾌", "fun", "awesome", "cool", "magic",
                 "play", "amazing", "love it", "멋진", "신나는", "귀여운"]),
    "serious": (["놀이", "재미", "가벼운", "취미"],
                ["license", "compliance", "security", "vulnerability", "policy",
                 "terms", "privacy", "audit", "certified", "liability", "규정", "법",
                 "준수", "책임", "금지", "의무", "보안", "계약", "위반", "처벌"]),
    "warm": (["차가운", "단속"],
             ["welcome", "community", "thanks", "thank", "friendly", "together",
              "환영", "함께", "감사", "따뜻", "모두", "동료", "배려", "돌봄"]),
    "luxe": (["무료", "대충"],
             ["premium", "elegant", "crafted", "curated", "luxury", "refined",
              "고급", "정교", "세련", "품격", "큐레이션"]),
    "technical": (["마음", "태도", "문화"],
                  ["install", "usage", "api", "sdk", "cli", "config", "endpoint",
                   "schema", "function", "docker", "deploy", "build", "compile",
                   "설치", "사용법", "명령", "옵션", "인자", "환경변수", "설정"]),
    "data": (["이야기", "서사"],
             ["data", "metrics", "benchmark", "statistics", "analytics", "chart",
              "graph", "dataset", "수치", "지표", "데이터", "통계", "분석", "비율",
              "퍼센트", "%"]),
    "dark": (["라이트", "밝은"],
             ["dark mode", "dark-mode", "다크", "night", "어두운", "obsidian"]),
    "hedge": ([], ["maybe", "might", "could", "perhaps", "probably", "roughly",
                   "approximately", "around", "generally", "likely", "possibly",
                   "somewhat", "fairly", "아마", "대략", "정도", "수도", "것 같",
                   "보통", "다소", "어느 정도"]),
}

# CSS 프로퍼티 이름 → 색 맥락. 앞에서 먼저 맞는 규칙이 이긴다.
PROP_KIND = (
    (re.compile(r"(background|bg|surface|paper|canvas|stage)", re.I), "bg"),
    (re.compile(r"(theme-color|brand|accent|primary|link|highlight|fill|tint)", re.I), "accent"),
    (re.compile(r"(border|outline|line|stroke|rule|divider)", re.I), "line"),
    (re.compile(r"(^|[-_])(color|ink|text|fg|foreground|on-)", re.I), "text"),
)
KIND_W = {"bg": 2.5, "text": 2.5, "line": 2.0, "accent": 3.0,
          "img": 1.5, "prose": 0.5, "other": 0.7}

DEFAULTS = {
    "paper": "#fafaf7", "surface": "#ffffff", "tint": "#f0eee7", "line": "#c7c2b4",
    "ink": "#1a1c1e", "ink-2": "#3f4448", "ink-3": "#585d61",
    "brand": "#2b5d75", "brand-text": "#2b5d75", "brand-tint": "#e3edf1",
    "accent": "#b3462f", "accent-text": "#b3462f", "accent-tint": "#f6e3de",
    "night": "#14171a", "night-2": "#1f2427", "night-line": "#4a4f52",
    "on-night": "#ecead9", "on-night-2": "#b4b5b0",
}


# ---------------------------------------------------------------- 근거 기록
class Evidence:
    """관측 하나에 E1, E2, ... 식 근거 ID 를 붙인다. 축·토큰이 어떤 근거를 썼는지 추적용."""

    def __init__(self):
        self.rows: list[dict] = []

    def add(self, kind: str, source: str, detail: str) -> str:
        eid = f"E{len(self.rows) + 1}"
        self.rows.append({"id": eid, "kind": kind, "source": source, "detail": detail})
        return eid


# ---------------------------------------------------------------- 색 유틸
def hex_norm(value: str) -> str | None:
    """#rgb/#rrggbb/#rrggbbaa → '#rrggbb' 소문자. 못 읽으면 None."""
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    if len(v) == 8:
        v = v[:6]
    if len(v) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", v):
        return None
    return "#" + v.lower()


def rgb_to_hex(r: float, g: float, b: float) -> str:
    c = lambda v: f"{int(round(max(0, min(255, v)))):02x}"
    return f"#{c(r)}{c(g)}{c(b)}"


def mix(hex1: str, hex2: str, t: float) -> str:
    """hex1 → hex2 방향으로 t(0..1) 만큼 섞은 색."""
    a, b = hex_to_rgb(hex1), hex_to_rgb(hex2)
    return rgb_to_hex(*(a[i] + (b[i] - a[i]) * t for i in range(3)))


def hsl(hexv: str) -> tuple[float, float, float]:
    r, g, b = (c / 255 for c in hex_to_rgb(hexv))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s, l


def sat_of(hexv: str) -> float:
    return hsl(hexv)[1]


def chroma_of(hexv: str) -> float:
    """HSV 채도 (max-min)/max — HSL 채도는 밝은 색에서 부풀어 중성 지면을 유채색으로
    오분류하므로, 중성/유채 판별에는 이 값을 쓴다(회색·크림·지면 톤 = 낮은 값)."""
    r, g, b = hex_to_rgb(hexv)
    return (max(r, g, b) - min(r, g, b)) / max(1, max(r, g, b))


def is_neutral(hexv: str) -> bool:
    """무채색 계열 — 지면·잉크·선 후보로 쓸 수 있는 색. 거의 검정(<0.06)이나
    거의 흰색(>0.96)은 채도가 불안정해 보여도 중성으로 취급한다."""
    return chroma_of(hexv) < 0.15 or lum_of(hexv) < 0.06 or lum_of(hexv) > 0.96


def is_chroma(hexv: str) -> bool:
    """유채색 계열 — brand/accent 색상 가족 후보. 너무 밝은 크림색(≥0.95 휘도)이나
    거의 검정(<0.06)은 색상 신호가 아니라 글자·지면이므로 제외한다."""
    return chroma_of(hexv) >= 0.15 and 0.06 <= lum_of(hexv) <= 0.96


def lum_of(hexv: str) -> float:
    return rel_luminance(hexv)


def hue_dist(h1: float, h2: float) -> float:
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def rotate_hue(hexv: str, deg: float) -> str:
    r, g, b = (c / 255 for c in hex_to_rgb(hexv))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    r2, g2, b2 = colorsys.hls_to_rgb((h * 360 + deg) % 360 / 360, l, s)
    return rgb_to_hex(r2 * 255, g2 * 255, b2 * 255)


def reach_ratio(color: str, bg: str, need: float, darker: bool) -> tuple[str, float]:
    """color 를 검정(darker)또는 흰색 방향으로 섞어 bg 대비 need 를 넘기는 최소 변경을 찾는다.

    [출력] (새 색, 섞은 비율). 24회 이분 탐색 후에도 못 넘기면 가장 가까운 값을 돌려준다.
    """
    target = "#000000" if darker else "#ffffff"
    if contrast_ratio(color, bg) >= need:
        return color, 0.0
    lo, hi, best, best_t = 0.0, 1.0, mix(color, target, 1.0), 1.0
    for _ in range(24):
        mid = (lo + hi) / 2
        cand = mix(color, target, mid)
        if contrast_ratio(cand, bg) >= need:
            hi, best, best_t = mid, cand, mid
        else:
            lo = mid
    return best, best_t


# ---------------------------------------------------------------- 소스 수집
def classify_name(name: str) -> str | None:
    ext = pathlib.Path(name).suffix.lower()
    if ext in MD_EXT:
        return "markdown"
    if ext in HTML_EXT:
        return "html"
    if ext in CSS_EXT:
        return "css"
    if ext in DATA_EXT:
        return "data"
    if ext in SVG_EXT:
        return "svg"
    if ext in IMG_EXT:
        return "image"
    return None


def is_secret(path: pathlib.Path) -> bool:
    return bool(SECRET_RE.search(path.name))


def read_text(path: pathlib.Path, warnings: list[str]) -> str | None:
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            warnings.append(f"{path.name}: {MAX_TEXT_BYTES // 1000}KB 초과 — 앞부분만 읽습니다")
            return path.read_text(encoding="utf-8", errors="replace")[:MAX_TEXT_BYTES]
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        warnings.append(f"{path}: 읽기 실패 ({e})")
        return None


def scan_folder(root: pathlib.Path, docs: list, images: list, ev: Evidence,
                warnings: list[str]) -> None:
    """폴더를 재귀 스캔해 문서와 이미지를 모은다. 비밀 파일·머신 디렉터리·상한 적용."""
    n_files = 0
    skipped_secret = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")]
        for fn in sorted(filenames):
            if n_files >= MAX_FILES:
                warnings.append(f"{root}: 파일 {MAX_FILES}개 상한 — 나머지 건너뜀")
                return
            p = pathlib.Path(dirpath) / fn
            if is_secret(p):
                skipped_secret += 1
                continue
            kind = classify_name(fn)
            if kind is None:
                continue
            n_files += 1
            if kind == "image":
                if len(images) < MAX_IMAGES:
                    images.append(p)
                continue
            text = read_text(p, warnings)
            if text is not None:
                docs.append({"kind": kind, "name": str(p), "text": text})
    if skipped_secret:
        ev.add("scan", str(root), f"비밀 패턴 파일 {skipped_secret}개 제외")


def fetch_json(url: str, warnings: list[str]) -> dict | None:
    req = urllib.request.Request(url, headers={
        "User-Agent": "edu-deck-extract-style/1.0",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
            return json.loads(r.read(FETCH_BYTES).decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        warnings.append(f"{url}: 가져오기 실패 ({e})")
        return None


def fetch_text(url: str, warnings: list[str] | None = None) -> str | None:
    """URL 텍스트를 가져온다. warnings=None 이면 실패를 조용히 None 으로 돌린다(후보 탐색용)."""
    req = urllib.request.Request(url, headers={"User-Agent": "edu-deck-extract-style/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
            return r.read(FETCH_BYTES).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        if warnings is not None:
            warnings.append(f"{url}: 가져오기 실패 ({e})")
        return None


def fetch_github(owner: str, repo: str, docs: list, metas: list, ev: Evidence,
                 warnings: list[str], offline: bool) -> None:
    """GitHub repo 의 API 메타데이터와 README 를 문서로 넣는다."""
    spec = f"{owner}/{repo}"
    if offline:
        warnings.append(f"github:{spec}: --offline — 건너뜁니다")
        return
    meta = fetch_json(f"https://api.github.com/repos/{spec}", warnings)
    branch = "main"
    if meta:
        metas.append({"spec": spec, "meta": meta})
        branch = meta.get("default_branch") or "main"
        ev.add("github", spec, f"repo 메타 — 언어 {meta.get('language')}, "
                             f"토픽 {', '.join(meta.get('topics') or []) or '없음'}, "
                             f"star {meta.get('stargazers_count')}")
    for name in ("README.md", "readme.md", "README.ko.md", "README.rst", "README"):
        text = fetch_text(f"https://raw.githubusercontent.com/{spec}/{branch}/{name}")
        if text:
            docs.append({"kind": "markdown", "name": f"github:{spec}/{name}", "text": text})
            ev.add("github", spec, f"{name} {len(text):,}자 ({branch} 브랜치)")
            return
    warnings.append(f"github:{spec}: README 를 찾지 못했습니다({branch} 브랜치)")


def gather_sources(source_args: list, offline: bool, ev: Evidence,
                   warnings: list[str]) -> tuple[list, list, list]:
    """--source 인자를 문서·이미지·GitHub 메타로 해석한다."""
    docs, images, metas = [], [], []
    flat = [s for group in source_args for s in group]
    for raw in flat:
        s = raw.strip()
        if not s:
            continue
        m = GITHUB_RE.match(s) or GITSSH_RE.match(s)
        if m:
            fetch_github(m.group(1), m.group(2).removesuffix(".git"),
                         docs, metas, ev, warnings, offline)
            continue
        if re.match(r"https?://", s):
            if offline:
                warnings.append(f"{s}: --offline — 건너뜁니다")
                continue
            text = fetch_text(s, warnings)
            if text:
                kind = "html" if "<" in text[:4000] and (">" in text[:4000]) else "markdown"
                docs.append({"kind": kind, "name": s, "text": text})
                ev.add("url", s, f"{kind} 문서 {len(text):,}자")
            continue
        p = pathlib.Path(s).expanduser()
        if p.is_dir():
            before = len(docs) + len(images)
            scan_folder(p, docs, images, ev, warnings)
            ev.add("scan", str(p), f"폴더 스캔 — 문서·데이터 {len(docs) + len(images) - before}개")
        elif p.is_file():
            if is_secret(p):
                warnings.append(f"{p}: 비밀 파일 패턴 — 건너뜁니다")
                continue
            kind = classify_name(p.name)
            if kind == "image":
                images.append(p)
            elif kind:
                text = read_text(p, warnings)
                if text is not None:
                    docs.append({"kind": kind, "name": str(p), "text": text})
            else:
                warnings.append(f"{p}: 지원하지 않는 확장자 — 건너뜁니다")
        else:
            warnings.append(f"{s}: 파일/폴더/URL 로 해석할 수 없습니다 — 건너뜁니다")
    return docs, images, metas


# ---------------------------------------------------------------- 문서 계량
def _iter_css_decls(text: str):
    """CSS·HTML·SVG 텍스트에서 'prop: value' 선언을 흘려준다(주석 제거 후)."""
    body = re.sub(r"/\*[\s\S]*?\*/", "", text)
    for m in DECL_RE.finditer(body):
        yield m.group(1).strip().lower(), m.group(2).strip()


def measure_colors(doc: dict, colors: dict, ev: Evidence) -> None:
    """한 문서의 색 관측을 colors 테이블에 누적한다.

    colors[hex][kind] += 가중치. kind 는 bg/text/line/accent/img/prose/other.
    """
    name, kind, text = doc["name"], doc["kind"], doc["text"]
    counts: dict[str, int] = {}
    if kind in ("css", "html", "svg"):
        for prop, value in _iter_css_decls(text):
            ckind = "other"
            for rx, k in PROP_KIND:
                if rx.search(prop):
                    ckind = k
                    break
            for hm in HEX_ANY_RE.finditer(value):
                hexv = hex_norm(hm.group(0))
                if hexv:
                    colors[hexv][ckind] += KIND_W[ckind]
                    counts[ckind] = counts.get(ckind, 0) + 1
            for rm in RGB_RE.finditer(value):
                hexv = rgb_to_hex(*(min(255, int(g)) for g in rm.groups()))
                colors[hexv][ckind] += KIND_W[ckind]
                counts[ckind] = counts.get(ckind, 0) + 1
        if kind == "svg":
            # SVG 프레젠테이션 속성(fill/stroke="...")은 선언 문법 밖이라 따로 잡는다.
            for am in re.finditer(r'(fill|stroke)\s*=\s*"(#[0-9a-fA-F]{3,8})"', text):
                hexv = hex_norm(am.group(2))
                if hexv:
                    ck = "accent" if am.group(1) == "fill" else "line"
                    colors[hexv][ck] += KIND_W[ck]
                    counts[ck] = counts.get(ck, 0) + 1
        if kind == "html":
            for tm in META_THEME_RE.finditer(text):
                hexv = hex_norm(tm.group(1) or tm.group(2))
                if hexv:
                    colors[hexv]["accent"] += 6.0
                    ev.add("color", name, f"meta theme-color {hexv} — 주색 후보(강한 신호)")
    else:
        # 마크다운·데이터 파일의 본문 hex 는 '프로젝트 색'이 아닐 수 있어 가중치를 낮춘다.
        prose = FENCE_RE.sub(" ", text)
        for hm in HEX_ANY_RE.finditer(prose):
            hexv = hex_norm(hm.group(0))
            if hexv:
                colors[hexv]["prose"] += KIND_W["prose"]
                counts["prose"] = counts.get("prose", 0) + 1
        if kind == "data":
            # "accent": "#abc" 같은 키-값 쌍이면 키 이름으로 맥락을 다시 분류한다.
            for km in re.finditer(r'"([^"\n]*?(?:color|accent|brand|primary|background|bg|'
                                  r'text|ink|border|line)[^"\n]*?)"\s*:\s*"(#[0-9a-fA-F]{3,8})"',
                                  text, re.I):
                hexv = hex_norm(km.group(2))
                if not hexv:
                    continue
                key = km.group(1)
                ck = "other"
                for rx, k in PROP_KIND:
                    if rx.search(key):
                        ck = k
                        break
                colors[hexv][ck] += 1.5
                counts[ck] = counts.get(ck, 0) + 1
    if counts:
        summary = "·".join(f"{k} {v}" for k, v in sorted(counts.items()))
        ev.add("color", name, f"hex 관측 {sum(counts.values())}개 ({summary})")


def measure_typography(doc: dict, fonts: dict, radii: list, sizes: list,
                       borders: list, shadow: list) -> None:
    """font-family·font-size·border-radius·border 두께·box-shadow 를 모은다."""
    text = doc["text"]
    for fm in FONT_FAMILY_RE.finditer(text):
        stack = fm.group(1).split("@")[0]
        for fam in stack.split(","):
            fam = fam.strip().strip("\"' ").lower()
            if fam and not fam.startswith(("var(", "inherit", "initial")):
                fonts[fam] = fonts.get(fam, 0) + 1
                break  # 스택의 첫 가족만 대표로 센다
    sizes.extend(float(m.group(1)) for m in FONT_SIZE_RE.finditer(text))
    radii.extend(float(m.group(1)) for m in RADIUS_RE.finditer(text))
    borders.extend(float(m.group(1)) for m in BORDER_W_RE.finditer(text))
    if SHADOW_RE.search(text) and not re.search(r"box-shadow\s*:\s*none", text):
        shadow.append(doc["name"])


def measure_markdown(text: str) -> dict:
    """마크다운 한 문서의 문체 계량치. 코드블록은 산출물 신호, 나머지(산문)는 문체 신호."""
    total = max(1, len(text))
    code_blocks = FENCE_RE.findall(text)
    code_chars = sum(len(b) for b in code_blocks)
    shell = sum(1 for b in code_blocks for ln in b.splitlines() if SHELL_LINE_RE.match(ln))
    prose = FENCE_RE.sub(" ", text)
    prose = INLINE_CODE_RE.sub(" ", prose)
    words = max(1, len(prose.split()))
    low = prose.lower()
    m = {
        "chars": total,
        "code_share": code_chars / total,
        "code_blocks": len(code_blocks),
        "shell_cmds": shell,
        "table_rows": len(re.findall(r"(?m)^\s*\|.*\|\s*$", prose)),
        "quote_share": sum(len(q) for q in re.findall(r"(?m)^\s*>.*$", prose)) / total,
        "exclaim_per_1k": prose.count("!") / words * 1000,
        "emoji_per_1k": len(EMOJI_RE.findall(prose)) / words * 1000,
        "number_per_100w": len(NUM_RE.findall(prose)) / words * 100,
        "words": words,
    }
    for cat, (lo, hi) in WORDS.items():
        m[f"w_{cat}_hi"] = sum(low.count(w.lower()) for w in hi)
        m[f"w_{cat}_lo"] = sum(low.count(w.lower()) for w in lo)
    return m


def pool_metrics(md_docs: list) -> dict:
    """문서별 계량을 글자 수 가중으로 합산한다."""
    agg = {k: 0.0 for k in ("code_share", "quote_share", "exclaim_per_1k",
                            "emoji_per_1k", "number_per_100w")}
    counts = {k: 0 for k in ("code_blocks", "shell_cmds", "table_rows", "chars", "words")}
    wsum = {k: 0.0 for k in WORDS}
    wsum.update({f"{k}_lo": 0.0 for k in WORDS})
    for m in md_docs:
        w = m["chars"]
        for k in agg:
            agg[k] += m[k] * w
        for k in counts:
            counts[k] += m[k]
        for cat in WORDS:
            wsum[cat] += m[f"w_{cat}_hi"]
            wsum[f"{cat}_lo"] += m[f"w_{cat}_lo"]
    total = max(1, counts["chars"])
    out = {k: v / total for k, v in agg.items()}
    out.update(counts)
    for cat in WORDS:
        out[f"w_{cat}_hi"], out[f"w_{cat}_lo"] = wsum[cat], wsum[f"{cat}_lo"]
    out["hedge_per_1k"] = out["w_hedge_hi"] / max(1, counts["words"]) * 1000
    return out


def measure_images(images: list, colors: dict, ev: Evidence,
                   warnings: list[str]) -> dict:
    """Pillow 가 있으면 이미지별 주요 색과 평균 휘도를 모은다. 없으면 건너뛴다."""
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        if images:
            warnings.append(f"Pillow 없음 — 이미지 {len(images)}개의 색 추출을 건너뜁니다")
        return {"count": len(images), "analyzed": 0, "dark_share": 0.0}
    dark = 0
    for p in images:
        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                im.thumbnail((72, 72))
                px = list(im.getdata())
                lum = sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in px) / (255 * len(px))
                if lum < 0.30:
                    dark += 1
                q = im.quantize(colors=5)
                pal = q.getpalette()
                ranked = sorted(q.getcolors() or [], reverse=True)
                tops = []
                for count, idx in ranked[:3]:
                    hexv = rgb_to_hex(pal[idx * 3], pal[idx * 3 + 1], pal[idx * 3 + 2])
                    colors[hexv]["img"] += KIND_W["img"] * (count / max(1, ranked[0][0]))
                    tops.append(f"{hexv}×{count}")
                ev.add("image", str(p), f"주요색 {' '.join(tops)} · 평균휘도 {lum:.2f}")
        except Exception as e:  # 손상된 이미지는 경고만
            warnings.append(f"{p.name}: 이미지 읽기 실패 ({e})")
    return {"count": len(images), "analyzed": len(images),
            "dark_share": dark / max(1, len(images))}


# ---------------------------------------------------------------- 톤 축
def compute_axes(pool: dict, palette_signals: dict, fonts: dict, metas: list,
                 ev: Evidence, evids: dict) -> dict:
    """실측 신호 → 8축 0..1. 각 축의 기여 신호와 근거 ID 를 함께 돌려준다."""
    tones: dict[str, dict] = {}
    m = pool

    def axis(name: str, signals: list[tuple[float, str | None]]) -> None:
        value = min(1.0, max(0.0, 0.5 + sum(w for w, _ in signals)))
        tones[name] = {"value": round(value, 3),
                       "evidence": sorted({e for _, e in signals if e})}

    axis("energy", [
        (min(0.30, m["exclaim_per_1k"] * 0.05), evids.get("exclaim")),
        (min(0.18, m["emoji_per_1k"] * 0.08), evids.get("emoji")),
        (0.12 if m["w_energy_hi"] >= 3 else 0.0, evids.get("words")),
        (-0.10 if m["w_energy_lo"] >= 2 else 0.0, evids.get("words")),
        (-0.15 if m["hedge_per_1k"] >= 5 else 0.0, evids.get("hedge")),
    ])
    axis("playful", [
        (min(0.35, m["emoji_per_1k"] * 0.15), evids.get("emoji")),
        (min(0.15, m["exclaim_per_1k"] * 0.025), evids.get("exclaim")),
        (0.12 if m["w_playful_hi"] >= 3 else 0.0, evids.get("words")),
        (0.10 if palette_signals.get("radius_median", 0) >= 12 else 0.0, evids.get("radius")),
        (-0.15 if m["w_serious_hi"] >= 5 else 0.0, evids.get("words")),
        (-0.12 if palette_signals.get("sat_median", 1) < 0.08 else 0.0, evids.get("palette")),
    ])
    axis("technical", [
        (min(0.40, m["code_share"] * 1.4), evids.get("code")),
        (0.10 if m["shell_cmds"] >= 3 else 0.0, evids.get("shell")),
        (min(0.18, m["w_technical_hi"] * 0.02), evids.get("words")),
        (0.12 if palette_signals.get("mono_font") else 0.0, evids.get("font")),
        (0.10 if metas and metas[0]["meta"].get("language") else 0.0, evids.get("github")),
        (-0.10 if m["w_technical_lo"] >= 3 else 0.0, evids.get("words")),
    ])
    axis("serious", [
        (min(0.30, m["w_serious_hi"] * 0.03), evids.get("words")),
        (0.12 if m["hedge_per_1k"] >= 4 else 0.0, evids.get("hedge")),
        (0.10 if m["emoji_per_1k"] < 0.05 else -0.20 if m["emoji_per_1k"] > 3 else 0.0,
         evids.get("emoji")),
        (0.08 if palette_signals.get("sat_median", 1) < 0.15 else 0.0, evids.get("palette")),
        (-0.12 if m["w_playful_hi"] >= 5 else 0.0, evids.get("words")),
    ])
    axis("warm", [
        (min(0.35, palette_signals.get("warm_hue_share", 0) * 0.7), evids.get("palette")),
        (min(0.18, m["w_warm_hi"] * 0.03), evids.get("words")),
        (0.08 if palette_signals.get("radius_median", 0) >= 10 else 0.0, evids.get("radius")),
        (-0.20 if palette_signals.get("cool_hue_share", 0) > 0.6 else 0.0, evids.get("palette")),
        (-0.15 if palette_signals.get("gray_share", 0) > 0.7 else 0.0, evids.get("palette")),
    ])
    axis("luxe", [
        (0.18 if palette_signals.get("serif_font") else 0.0, evids.get("font")),
        (0.15 if palette_signals.get("dark_bg_share", 0) > 0.3 else 0.0, evids.get("palette")),
        (0.12 if palette_signals.get("hue_families", 9) <= 3 else 0.0, evids.get("palette")),
        (min(0.15, m["w_luxe_hi"] * 0.03), evids.get("words")),
        (0.08 if palette_signals.get("hairline") else 0.0, evids.get("border")),
        (-0.20 if m["emoji_per_1k"] > 3 else 0.0, evids.get("emoji")),
    ])
    axis("dark", [
        (min(0.50, palette_signals.get("dark_bg_share", 0) * 0.9), evids.get("palette")),
        (min(0.20, palette_signals.get("img_dark_share", 0) * 0.4), evids.get("image")),
        (0.10 if m["w_dark_hi"] >= 2 else 0.0, evids.get("words")),
        (-0.35 if palette_signals.get("light_bg_share", 0) > 0.8 else 0.0, evids.get("palette")),
    ])
    axis("data", [
        (min(0.28, m["number_per_100w"] * 0.05), evids.get("numbers")),
        (min(0.18, m["table_rows"] * 0.015), evids.get("table")),
        (min(0.20, m["w_data_hi"] * 0.025), evids.get("words")),
        (0.10 if palette_signals.get("data_files", 0) >= 2 else 0.0, evids.get("datafiles")),
    ])
    return tones


# ---------------------------------------------------------------- 팔레트
def palette_signals(colors: dict, radii: list, fonts: dict, borders: list,
                    shadow: list, data_files: int, img_stats: dict) -> dict:
    """축 계산과 팔레트 배정에 쓰는 색·형태 요약 신호."""
    chroma = [(h, w) for h, w in colors.items() if is_chroma(h)]

    def share(pred, bag=None):
        bag = bag if bag is not None else [(h, w) for h, w in colors.items()]
        tot = sum(sum(w.values()) for _, w in bag) or 1
        return sum(sum(w.values()) for h, w in bag if pred(h)) / tot

    hue_fams = set()
    for hexv, w in chroma:
        if sum(w.values()) >= 1.0:
            hue_fams.add(round(hsl(hexv)[0] / 30))
    bg_weighted = [(h, w) for h, w in colors.items()
                   if w.get("bg", 0) + w.get("img", 0) > 0]
    serif = any(any(h in f for h in SERIF_HINTS) for f in fonts)
    mono = any(any(h in f for h in MONO_HINTS) for f in fonts)
    return {
        "radius_median": percentile(radii, 50),
        "hairline": bool(borders) and percentile(borders, 50) <= 1.5,
        "has_shadow": bool(shadow),
        "serif_font": serif, "mono_font": mono,
        "sat_median": percentile([chroma_of(h) for h, _ in colors.items()], 50) if colors else 0.0,
        "warm_hue_share": share(lambda h: 10 <= hsl(h)[0] <= 70, chroma),
        "cool_hue_share": share(lambda h: 180 <= hsl(h)[0] <= 260, chroma),
        "gray_share": share(lambda h: chroma_of(h) < 0.15),
        "dark_bg_share": share(lambda h: lum_of(h) < 0.18, bg_weighted),
        "light_bg_share": share(lambda h: lum_of(h) > 0.80, bg_weighted),
        "hue_families": len(hue_fams),
        "img_dark_share": img_stats.get("dark_share", 0.0),
        "data_files": data_files,
    }


def percentile(values, pct: float) -> float:
    if not values:
        return 0.0
    vs = sorted(values)
    k = (len(vs) - 1) * pct / 100
    lo = math.floor(k)
    return vs[lo] + (vs[min(lo + 1, len(vs) - 1)] - vs[lo]) * (k - lo)


def _top_color(cands: list[tuple[str, dict]], prefer=("bg", "text")) -> str | None:
    """(hex, 가중치 dict) 목록에서 총 가중치 최대 색. prefer 맥락은 ×1.6 보너스."""
    best, best_w = None, -1.0
    for hexv, w in cands:
        total = sum(w.values()) + 0.6 * sum(w.get(k, 0) for k in prefer)
        if total > best_w:
            best, best_w = hexv, total
    return best


def derive_palette(colors: dict, tones: dict, ev: Evidence, evids: dict) -> tuple[dict, dict, dict]:
    """실측 색 → 18개 토큰 + 반경 3개 + 규칙 3개.

    [배정] 무채색(is_neutral)에서 지면·선·잉크, 유채색(is_chroma)은 색상 가족
    (30° 버킷)별로 묶어 최대 가족→brand, 다음 가족(색상거리 ≥60°)→accent.
    못 채운 자리는 DEFAULTS 나 잉크↔지면 혼합으로 파생한다.
    [출력] (tokens, radii, rules) — 보정은 ensure_contrast() 가 마무리한다.
    """
    tokens = dict(DEFAULTS)
    tok_ev: dict[str, list[str]] = {k: [] for k in tokens}
    neutrals = [(h, w) for h, w in colors.items() if is_neutral(h)]
    chroma = [(h, w) for h, w in colors.items() if is_chroma(h)]

    # 지면 — 밝은 중성 가운데 bg 맥락 가중치가 가장 큰 색을 paper 로.
    papers = [c for c in neutrals if lum_of(c[0]) > 0.85]
    if papers:
        pick = _top_color(papers, ("bg", "img")) or max(papers, key=lambda c: lum_of(c[0]))[0]
        tokens["paper"] = pick
        tok_ev["paper"].append(ev.add("assign", "palette", f"가장 밝은 중성 지면 후보 {pick}"))
        tokens["surface"] = "#ffffff"
        tints = [c for c in neutrals if c[0] != pick and 0.70 < lum_of(c[0]) < 0.96]
        if tints:
            tokens["tint"] = _top_color(tints, ("bg", "img", "line")) or tints[0][0]
            tok_ev["tint"].append(ev.add("assign", "palette", f"보조 채움 실측 {tokens['tint']}"))
    # 잉크 — text 맥락이 있는 어두운 중성 우선, 잉크→보조→캡션 순서로 밝아지는 사다리.
    darks = sorted((c for c in neutrals if lum_of(c[0]) < 0.35), key=lambda c: lum_of(c[0]))
    if darks:
        ink_cands = [c for c in darks if c[1].get("text", 0) > 0] or darks
        tokens["ink"] = _top_color(ink_cands[:6], ("text",)) or darks[0][0]
        tok_ev["ink"].append(ev.add("assign", "palette", f"가장 어두운 글자 후보 {tokens['ink']}"))
        rest = [c for c in ink_cands
                if c[0] != tokens["ink"] and lum_of(c[0]) > lum_of(tokens["ink"])]
        if rest:
            tokens["ink-2"] = _top_color(rest, ("text",)) or rest[0][0]
            rest2 = [c for c in rest
                     if c[0] != tokens["ink-2"] and lum_of(c[0]) > lum_of(tokens["ink-2"])]
            if rest2:
                tokens["ink-3"] = _top_color(rest2, ("text",)) or rest2[0][0]
            else:
                tokens["ink-3"] = mix(tokens["ink-2"], tokens["paper"], 0.28)
        else:
            tokens["ink-2"] = mix(tokens["ink"], tokens["paper"], 0.32)
            tokens["ink-3"] = mix(tokens["ink-2"], tokens["paper"], 0.28)
    else:
        tokens["ink-2"] = mix(tokens["ink"], tokens["paper"], 0.32)
        tokens["ink-3"] = mix(tokens["ink-2"], tokens["paper"], 0.28)
    if "tint" not in tok_ev or not tok_ev["tint"]:
        tokens["tint"] = mix(tokens["paper"], tokens["ink"], 0.055)
    line_cands = [c for c in neutrals if 0.30 < lum_of(c[0]) < 0.90 and c[1].get("line", 0) > 0]
    if line_cands:
        tokens["line"] = _top_color(line_cands, ("line",)) or tokens["line"]
        tok_ev["line"].append(ev.add("assign", "palette", f"경계선 실측 {tokens['line']}"))
    elif papers or darks:
        tokens["line"] = mix(tokens["ink"], tokens["paper"], 0.48)

    # 유채색 → 색상 가족(30° 버킷)으로 brand/accent
    fams: dict[int, list[tuple[str, dict]]] = {}
    for hexv, w in chroma:
        fams.setdefault(round(hsl(hexv)[0] / 30) % 12, []).append((hexv, w))
    fam_sorted = sorted(fams.items(), key=lambda kv: -sum(sum(w.values()) for _, w in kv[1]))
    if fam_sorted:
        fam_h, fam_colors = fam_sorted[0]
        brand = _top_color(fam_colors, ("accent", "text")) or fam_colors[0][0]
        tokens["brand"] = tokens["brand-text"] = brand
        tokens["brand-tint"] = mix(brand, "#ffffff", 0.86)
        tok_ev["brand"].append(ev.add(
            "assign", "palette", f"최대 유채색 가족(색상 {fam_h * 30}°±) 대표 {brand}"))
        accent = None
        for fh2, cols in fam_sorted[1:]:
            if hue_dist(fh2 * 30, fam_h * 30) >= 60:
                accent = _top_color(cols, ("accent", "text")) or cols[0][0]
                break
        if accent is None:
            accent = rotate_hue(brand, 160)
            ev.add("assign", "palette", f"두 번째 색상 가족 없음 — 주색 보색 {accent} 유도")
        tokens["accent"] = tokens["accent-text"] = accent
        tokens["accent-tint"] = mix(accent, "#ffffff", 0.86)
        tok_ev["accent"].append(ev.add("assign", "palette", f"강조색 {accent}"))

    # 밤 무대 — 가장 어두운 배경 계열 또는 주색을 섞은 짙은색
    dark_bg = [c for c in colors.items()
               if lum_of(c[0]) < 0.18 and (c[1].get("bg", 0) + c[1].get("img", 0)) > 0]
    if dark_bg:
        tokens["night"] = _top_color(dark_bg, ("bg", "img")) or darks and darks[0][0] or tokens["night"]
        tok_ev["night"].append(ev.add("assign", "palette", f"어두운 배경 실측 {tokens['night']}"))
    elif tokens.get("brand"):
        tokens["night"] = mix("#101216", tokens["brand"], 0.18)
        tok_ev["night"].append(ev.add("assign", "palette", "어두운 배경 실측 없음 — 주색 섞은 밤"))
    tokens["night-2"] = mix(tokens["night"], "#ffffff", 0.10)
    tokens["night-line"] = mix(tokens["night"], "#ffffff", 0.30)
    light_text = [c for c in neutrals if lum_of(c[0]) > 0.88]
    tokens["on-night"] = (_top_color(light_text, ("text", "img")) or "#ecead9") if light_text else "#ecead9"
    tokens["on-night-2"] = mix(tokens["on-night"], tokens["night"], 0.30)

    # 반경 — 실측 백분위, 없으면 playful 축으로 유도
    return tokens, tok_ev, {}


def derive_radii_rules(radii_meas: list, borders: list, shadow: list, sizes: list,
                       tones: dict, files_kind: dict, ev: Evidence, evids: dict):
    """모서리 3종과 규칙 3종(no-shadow·hairline·min-font)."""
    if radii_meas:
        md = round(min(24, max(2, percentile(radii_meas, 50))))
        sm = round(min(md, max(1, percentile(radii_meas, 25))))
        lg = round(max(md, min(48, percentile(radii_meas, 75))))
        ev.add("radius", "sources", f"border-radius 실측 {len(radii_meas)}개 → {sm}/{md}/{lg}px")
    else:
        playful = tones["playful"]["value"]
        md = round(4 + 10 * playful)
        sm, lg = max(2, round(md * 0.5)), min(96, round(md * 1.6))
        ev.add("radius", "axes", f"실측 없음 — playful {playful:.2f} → {sm}/{md}/{lg}px")
    hairline = bool(borders) and percentile(borders, 50) <= 1.5
    if not borders:
        hairline = (tones["serious"]["value"] + tones["technical"]["value"]
                    + tones["luxe"]["value"]) / 3 >= 0.55
    no_shadow = (not shadow) and (tones["luxe"]["value"] >= 0.6
                                  or tones["serious"]["value"] >= 0.6
                                  or files_kind.get("css", 0) == 0)
    min_font = round(min(48, max(12, percentile(sizes, 10)))) if sizes else 20
    return {"radius-sm": f"{sm}px", "radius-md": f"{md}px", "radius-lg": f"{lg}px"}, {
        "no-shadow": bool(no_shadow), "hairline": bool(hairline), "min-font": min_font}


# ---------------------------------------------------------------- 대비 보정
def ensure_contrast(tokens: dict, ev: Evidence) -> list[dict]:
    """CONTRAST_GATES + check_deck 행렬 항목을 전부 통과하도록 토큰을 밝기 방향으로 보정한다.

    [순서] ① 지면 밝기 확보 ② 잉크 3종 ③ tint·line ④ brand/accent 글자 ⑤ tint 면
    ⑥ 강조 본색 ≥3 ⑦ 밤 무대. 각 단계가 앞 단계 결과 위에 서므로 순서를 바꾸지 않는다.
    [출력] 보정 기록 [{token, from, to, reason}] — 보고서에 그대로 남긴다.
    """
    log: list[dict] = []

    def note(tok, old, reason):
        if old != tokens[tok]:
            log.append({"token": tok, "from": old, "to": tokens[tok], "reason": reason})

    def fix_fg(tok: str, bgs: list[str], need: float, lighten=False):
        for _ in range(10):
            worst = min(bgs, key=lambda b: contrast_ratio(tokens[tok], tokens[b]))
            if contrast_ratio(tokens[tok], tokens[worst]) >= need - 1e-9:
                return
            old = tokens[tok]
            darker = lum_of(tokens[tok]) < lum_of(tokens[worst])
            if lighten:
                darker = False
            tokens[tok], _ = reach_ratio(tokens[tok], tokens[worst], need,
                                         darker=darker and not lighten)
        note(tok, old, f"{'밝게' if lighten else '어둡게'} — {tok}/{bgs} ≥{need}")

    # ① 지면 — 어두운 지면이 들어오면 흰색 쪽으로 끌어올린다(덱은 밝은 지면 계약).
    for tok in ("paper", "surface", "tint"):
        floor = 0.86 if tok != "tint" else 0.78
        old = tokens[tok]
        for _ in range(10):
            if lum_of(tokens[tok]) >= floor:
                break
            tokens[tok] = mix(tokens[tok], "#ffffff", 0.35)
        note(tok, old, f"지면 휘도 ≥{floor}")

    # ② 잉크 — 본문·보조·캡션 순으로 게이트(a~c).
    for tok, need in (("ink", 7.0), ("ink-2", 4.5), ("ink-3", 4.5)):
        fix_fg(tok, ["paper", "surface"], need)

    # ③ tint·line — 게이트엔 없지만 본문 잉크·경계 식별용으로 소프트 보정.
    old = tokens["tint"]
    for _ in range(8):
        if contrast_ratio(tokens["ink"], tokens["tint"]) >= 4.5:
            break
        tokens["tint"] = mix(tokens["tint"], "#ffffff", 0.18)
    note("tint", old, "ink/tint ≥4.5 (칩 위 본문)")
    old = tokens["line"]
    for _ in range(8):
        if contrast_ratio(tokens["line"], tokens["paper"]) >= 3.0:
            break
        tokens["line"] = mix(tokens["line"], "#000000", 0.20)
    note("line", old, "line/paper ≥3.0 (의미 있는 경계)")

    # ④⑤ 글자색 → tint 면 순서로 (글자가 먼저 어두워진 뒤 tint 를 밝힌다).
    for fg, tint, need in (("brand-text", "brand-tint", 4.5),
                           ("accent-text", "accent-tint", 4.5)):
        fix_fg(fg, ["paper", "surface", tint], need)
        old = tokens[tint]
        for _ in range(10):
            if contrast_ratio(tokens[fg], tokens[tint]) >= need - 1e-9:
                break
            tokens[tint] = mix(tokens[tint], "#ffffff", 0.20)
        note(tint, old, f"{fg}/{tint} ≥{need}")
        fix_fg(fg, ["paper", "surface", tint], need)

    # ⑥ 강조 본색은 '큰 글자·그래픽' 기준 ≥3.0 만 맞춘다.
    fix_fg("accent", ["paper", "surface"], 3.0)
    fix_fg("brand", ["paper", "surface"], 3.0)

    # ⑦ 밤 무대 — on-night 를 위해 night 자체를 충분히 어둡게.
    old = tokens["night"]
    for _ in range(10):
        if contrast_ratio(tokens["on-night"], tokens["night"]) >= 7.0 - 1e-9:
            break
        tokens["night"] = mix(tokens["night"], "#000000", 0.22)
    note("night", old, "on-night/night ≥7.0 (밤 바닥을 더 어둡게)")
    if lum_of(tokens["night-2"]) <= lum_of(tokens["night"]) + 0.01:
        old = tokens["night-2"]
        tokens["night-2"] = mix(tokens["night"], "#ffffff", 0.10)
        note("night-2", old, "밤 카드는 밤 바닥보다 밝게")
    fix_fg("on-night", ["night"], 7.0, lighten=True)
    fix_fg("on-night", ["night-2"], 4.5, lighten=True)
    fix_fg("on-night-2", ["night", "night-2"], 4.5, lighten=True)
    if lum_of(tokens["on-night-2"]) >= lum_of(tokens["on-night"]) - 1e-9:
        old = tokens["on-night-2"]
        tokens["on-night-2"] = mix(tokens["night"], tokens["on-night"], 0.74)
        note("on-night-2", old, "밤 보조 글자는 밤 본문보다 어둡게")
    return log


def extra_checks(tokens: dict) -> list[dict]:
    """CONTRAST_GATES 밖에서 check_deck 행렬이 재는 프리셋 관련 쌍."""
    muted = mix(tokens["tint"], tokens["ink-3"], 0.30)
    rows = [
        ("accent", "paper", 3.0, "큰 글자·그래픽"),
        ("line", "paper", 3.0, "의미 있는 경계"),
        ("muted:derived", "ink", 3.0, "어두운 면 위 옅은 선·면"),
        ("accent-tint", "ink", 3.0, "어두운 면 위 강조 tint"),
        ("ink", "tint", 4.5, "칩 위 본문"),
    ]
    out = []
    for fg, bg, need, label in rows:
        fv = muted if fg == "muted:derived" else tokens[fg]
        r = contrast_ratio(fv, tokens[bg])
        out.append({"fg": fg, "bg": bg, "need": need, "label": label,
                    "ratio": round(r, 2), "pass": r + 1e-9 >= need})
    return out


def gate_report(tokens: dict) -> tuple[list[dict], bool]:
    rows = [{"label": l, "fg": f, "bg": b, "need": n,
             "ratio": round(contrast_ratio(tokens[f], tokens[b]), 2),
             "pass": contrast_ratio(tokens[f], tokens[b]) + 1e-9 >= n}
            for l, f, b, n in CONTRAST_GATES]
    return rows + extra_checks(tokens), all(r["pass"] for r in rows)


def recommended_theme(tones: dict) -> str:
    """톤 축을 tone_router 6축에 매핑해 허용 테마 8종 중 가장 가까운 id 를 고른다."""
    ax = {a: tones[a]["value"] for a in AXES}
    mapped = {"energy": ax["energy"], "playful": ax["playful"],
              "technical": ax["technical"], "serious": ax["serious"],
              "warm": ax["warm"], "formal": max(ax["serious"], ax["luxe"] * 0.8)}
    best, best_d = "ocean", 99.0
    for tid in THEME_IDS:
        sig = THEME_SIGNATURES[tid]["axes"]
        d = sum(abs(mapped[a] - sig[a]) for a in mapped)
        if d < best_d:
            best, best_d = tid, d
    return best


# ---------------------------------------------------------------- CSS 출력
def deck_css(tokens: dict, rules: dict, radii: dict, name: str, src_note: str) -> str:
    """preset.css — style_preset.deck_css() 와 같은 블록 구조(계약), 출처 표기만 다르다.

    [계약] /* preset-css */ 마커·:root 18+3+3 토큰·.slide 파생 고정·.slide.dark 밤 무대.
    """
    t = tokens
    lines = [
        f"/* preset.css — \"{name}\" · {MARKER} 자동 생성물 (extract_style.py)",
        "   [역할] 색과 모서리만 바꾼다. 배치·간격·모션은 엔진 그대로다.",
        "   [연결] :root 가 tokens.css 의 색 역할을 덮고, .slide 가 장마다 다시 계산되는",
        "          파생 토큰(--accent-soft·--light 등)을 이 팔레트 값으로 고정한다.",
        f"   [출처] {src_note}",
        "          다시 실행하면 이 파일은 통째로 덮어써진다. */",
        ":root{",
        f"  --bg:{t['paper']};--bg-2:{t['tint']};--paper:{t['surface']};--line:{t['line']};",
        f"  --ink:{t['ink']};--soft:{t['ink-2']};--mut:{t['ink-3']};",
        f"  --blue:{t['brand']};--blue-text:{t['brand-text']};--blue-soft:{t['brand-tint']};",
        f"  --accent:{t['accent']};--accent-text:{t['accent-text']};--accent-soft:{t['accent-tint']};",
        f"  --night:{t['night']};--night-2:{t['night-2']};--night-line:{t['night-line']};",
        f"  --on-night:{t['on-night']};--on-night-2:{t['on-night-2']};",
        f"  --r-sm:{radii['radius-sm']};--r-md:{radii['radius-md']};--r-lg:{radii['radius-lg']};",
        f"  --preset-hairline:{1 if rules['hairline'] else 0};"
        f"--preset-no-shadow:{1 if rules['no-shadow'] else 0};"
        f"--preset-min-font:{rules['min-font']}px;",
        "}",
        ".slide{",
        "  --light:var(--bg);--chip:var(--bg-2);",
        "  /* 엔진의 --muted 는 글자가 아니라 '옅은 선·면'이고, 밤 장 안에서도 글자로 쓰인다.",
        "     그래서 캡션 잉크(--mut)를 그대로 넣지 않고, 옅은 바탕과 섞어 양쪽에서 읽히게 한다. */",
        "  --muted:color-mix(in srgb,var(--bg-2) 70%,var(--mut));",
        f"  --accent-light:{t['accent-tint']};--accent-soft:{t['accent-tint']};",
        f"  --blue-light:{t['ink-3']};",
        "  --r1:var(--r-sm);--r2:var(--r-md);--r3:var(--r-lg);",
    ]
    if rules["no-shadow"]:
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


# ---------------------------------------------------------------- 보고 산출물
def write_json(path: pathlib.Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_md(path: pathlib.Path, rep: dict) -> None:
    t, tones = rep["palette"]["tokens"], rep["tones"]
    L = [f"# 스타일 추출 보고 — {rep['name']}",
         "",
         f"extract_style.py {VERSION} · {rep['generated_at']} · 소스 {len(rep['sources'])}개",
         "",
         "## 소스",
         *[f"- `{s['name']}` ({s['kind']})" for s in rep["sources"]],
         ""]
    if rep.get("github"):
        L += ["## GitHub 메타"]
        for g in rep["github"]:
            meta = g["meta"]
            L.append(f"- `{g['spec']}` — 언어 {meta.get('language')}, "
                     f"토픽 {', '.join(meta.get('topics') or []) or '없음'}, "
                     f"star {meta.get('stargazers_count')}")
        L.append("")
    L += ["## 문체 계량(마크다운 합산)", "",
          "| 지표 | 값 |", "|---|---|"]
    m = rep["metrics"]
    for k, label in (("code_share", "코드블록 비율"), ("shell_cmds", "셸 명령 수"),
                     ("emoji_per_1k", "이모지 /1k"), ("exclaim_per_1k", "느낌표 /1k"),
                     ("number_per_100w", "수치 /100단어"), ("hedge_per_1k", "헤징 /1k"),
                     ("quote_share", "인용 비율"), ("table_rows", "표 행 수")):
        v = m.get(k, 0)
        L.append(f"| {label} | {v:.3f} |" if isinstance(v, float) else f"| {label} | {v} |")
    L += ["", "## 톤 축 (0..1)", "", "| 축 | 값 | 근거 |", "|---|---|---|"]
    for a in AXES:
        v = tones[a]
        L.append(f"| {a} | {'█' * round(v['value'] * 10):10s} {v['value']:.2f} "
                 f"| {', '.join(v['evidence']) or '—'} |")
    L += ["", "## 팔레트", "", "| 토큰 | 값 | 비고 |", "|---|---|---|"]
    adj = {a["token"]: a for a in rep["palette"]["adjustments"]}
    for k, v in t.items():
        note = f"보정 {adj[k]['from']}→{v} ({adj[k]['reason']})" if k in adj else ""
        L.append(f"| {k} | `{v}` | {note} |")
    r = rep["palette"]["radii"]
    L += [f"| radius | {r['radius-sm']}/{r['radius-md']}/{r['radius-lg']} | |"]
    ru = rep["palette"]["rules"]
    L += [f"| rules | shadow={'없음' if ru['no-shadow'] else '있음'} · "
          f"hairline={'예' if ru['hairline'] else '아니오'} · min-font {ru['min-font']}px | |",
          "", "## 대비 게이트", "", "| 쌍 | 전경 | 배경 | 비율 | 기준 | 판정 |",
          "|---|---|---|---|---|---|"]
    for g in rep["contrast"]["gates"]:
        L.append(f"| {g.get('label', 'extra')} | {g['fg']} | {g['bg']} | {g['ratio']} "
                 f"| {g['need']} | {'통과' if g['pass'] else '**미달**'} |")
    if rep["fonts"]:
        L += ["", "## 관측 폰트(상위)",
              *[f"- `{f}` ×{c}" for f, c in rep["fonts"][:8]]]
    L += ["", "## 근거 목록",
          *[f"- **{e['id']}** [{e['kind']}] {e['source']} — {e['detail']}"
            for e in rep["evidence"]]]
    if rep["warnings"]:
        L += ["", "## 경고", *[f"- {w}" for w in rep["warnings"]]]
    L += ["", f"추천 legacy 테마(참고): `{rep['recommended_theme']}` — 프리셋과 같이 쓰지 않습니다.",
          "다음 단계: `python3 shared/scripts/build_deck.py <덱>` → "
          "`python3 shared/scripts/check_deck.py <결과.html>`", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8")


def write_board(path: pathlib.Path, rep: dict) -> None:
    """style-board.html — 팔레트·축·게이트·가벼운/어두운 목업을 한 장에 보여 주는 독립 HTML."""
    t, tones = rep["palette"]["tokens"], rep["tones"]
    esc = html_mod.escape
    swatches = "".join(
        f'<div class="sw"><div class="chip" style="background:{v}"></div>'
        f'<div class="swname">{esc(k)}</div><div class="swhex">{v}</div></div>'
        for k, v in t.items())
    bars = "".join(
        f'<div class="axis"><span class="axname">{a}</span>'
        f'<span class="axbar"><i style="width:{tones[a]["value"] * 100:.0f}%"></i></span>'
        f'<span class="axval">{tones[a]["value"]:.2f}</span></div>'
        for a in AXES)
    gates = "".join(
        f'<tr class="{"ok" if g["pass"] else "bad"}"><td>{esc(str(g.get("label", "extra")))}</td>'
        f'<td><i class="dot" style="background:{esc(str(g["fg"])) if g["fg"].startswith("#") else "var(--ink)"}"></i>{esc(g["fg"])}</td>'
        f'<td>{esc(g["bg"])}</td><td>{g["ratio"]}</td><td>{g["need"]}</td>'
        f'<td>{"통과" if g["pass"] else "미달"}</td></tr>'
        for g in rep["contrast"]["gates"])
    evs = "".join(f'<li><b>{e["id"]}</b> [{esc(e["kind"])}] {esc(e["source"])} — {esc(e["detail"])}</li>'
                  for e in rep["evidence"][:60])
    srcs = ", ".join(esc(s["name"]) for s in rep["sources"][:8])
    if len(rep["sources"]) > 8:
        srcs += f" 외 {len(rep['sources']) - 8}"
    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>style board — {esc(rep['name'])}</title>
<style>
body{{margin:0;background:#f4f3ef;color:#1a1c1e;font:14px/1.6 -apple-system,'Pretendard',sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:40px 28px}}
h1{{font-size:26px;margin:0 0 4px}}h2{{font-size:16px;margin:34px 0 12px;border-bottom:1px solid #ddd;padding-bottom:6px}}
.meta{{color:#666;font-size:13px}}.srcs{{color:#666;font-size:12px;margin-top:6px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px}}
.sw{{background:#fff;border:1px solid #e2e0d8;border-radius:10px;overflow:hidden}}
.sw .chip{{height:52px}}.swname{{padding:6px 10px 0;font-weight:700;font-size:12px}}
.swhex{{padding:0 10px 8px;color:#777;font-size:11px;font-family:ui-monospace,monospace}}
.axis{{display:flex;align-items:center;gap:10px;margin:5px 0}}
.axname{{width:86px;font-size:12px;font-weight:700;text-align:right}}
.axbar{{flex:1;height:10px;background:#e7e5dc;border-radius:5px;overflow:hidden}}
.axbar i{{display:block;height:100%;background:{t['brand']};border-radius:5px}}
.axval{{width:38px;font-size:12px;color:#666}}
.mocks{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.mock{{border-radius:{rep['palette']['radii']['radius-md']};padding:34px 30px;min-height:190px}}
.mock.light{{background:{t['paper']};border:1px solid {t['line']};color:{t['ink']}}}
.mock .kick{{font-size:11px;letter-spacing:2px;font-weight:800;color:{t['accent-text']}}}
.mock h3{{margin:8px 0 8px;font-size:24px;color:{t['ink']}}}
.mock.light .body{{color:{t['ink-2']}}}.mock .cap{{color:{t['ink-3']};font-size:12px;margin-top:14px}}
.mock .chip2{{display:inline-block;background:{t['tint']};color:{t['ink-2']};border-radius:{rep['palette']['radii']['radius-sm']};padding:3px 10px;font-size:12px;margin-top:12px}}
.mock .acc{{height:5px;width:52px;background:{t['accent']};border-radius:3px;margin-top:14px}}
.mock .brandline{{color:{t['brand-text']};font-weight:700}}
.mock.dark{{background:{t['night']};color:{t['on-night']};border:1px solid {t['night-line']}}}
.mock.dark h3{{color:{t['on-night']}}}
.mock.dark .body{{color:{t['on-night-2']}}}
.mock.dark .pill{{display:inline-block;border:2px solid {t['night-line']};color:{t['on-night']};border-radius:99px;padding:3px 12px;font-size:12px;margin-top:12px}}
.mock.dark .card{{background:{t['night-2']};border-radius:{rep['palette']['radii']['radius-sm']};padding:10px 14px;margin-top:12px;color:{t['on-night-2']};font-size:12px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}
td,th{{border-bottom:1px solid #e4e2da;padding:5px 8px;text-align:left}}
tr.bad td{{color:#b23b2e;font-weight:700}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px;border:1px solid #0002}}
ol.ev{{font-size:12px;color:#555;columns:2;column-gap:30px}}
.note{{font-size:12px;color:#777;margin-top:30px}}
</style></head><body><div class="wrap">
<h1>style board — {esc(rep['name'])}</h1>
<div class="meta">extract_style.py {VERSION} · {esc(rep['generated_at'])} ·
추천 테마 <b>{esc(rep['recommended_theme'])}</b>(참고, 같이 쓰지 않음)</div>
<div class="srcs">소스: {srcs}</div>
<h2>팔레트 {len(t)}토큰</h2><div class="grid">{swatches}</div>
<h2>톤 축</h2>{bars}
<h2>장 모의 — 밝은 / 밤 무대</h2><div class="mocks">
<div class="mock light"><div class="kick">EXTRACTED STYLE</div><h3>제목은 이렇게 보입니다</h3>
<div class="body">본문 잉크와 보조 잉크의 결이 실측 팔레트로 결정됩니다.
<span class="brandline">주색 글자</span>는 이런 색입니다.</div>
<span class="chip2">칩·보조 면</span><div class="acc"></div>
<div class="cap">캡션·각주는 세 번째 잉크 — 경계선 색과 함께</div></div>
<div class="mock dark"><div class="kick">DARK STAGE</div><h3>밤 장 표지</h3>
<div class="body">밤 무대 본문·보조 글자입니다.</div>
<div class="card">밤 카드(night-2) 위의 텍스트</div>
<span class="pill">pill</span></div>
</div>
<h2>대비 게이트 {len(rep['contrast']['gates'])}쌍 — 전부 통과={rep['contrast']['all_pass']}</h2>
<table><tr><th>구분</th><th>전경</th><th>배경</th><th>비율</th><th>기준</th><th>판정</th></tr>{gates}</table>
<h2>근거</h2><ol class="ev">{evs}</ol>
<div class="note">/* preset-css */ · extract_style.py 가 소스 실측으로 생성 —
규칙: shadow={'없음' if rep['palette']['rules']['no-shadow'] else '있음'} ·
hairline={'예' if rep['palette']['rules']['hairline'] else '아니오'} ·
min-font {rep['palette']['rules']['min-font']}px ·
반경 {rep['palette']['radii']['radius-sm']}/{rep['palette']['radii']['radius-md']}/{rep['palette']['radii']['radius-lg']}</div>
</div></body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------- 메인
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="소스(URL·파일·폴더)를 실측해 edu-deck preset.css 와 스타일 보고를 만든다",
        epilog="예: extract_style.py --source README.md ./site --deck my-deck --board --md --json")
    ap.add_argument("--source", action="append", nargs="+", required=True, metavar="SRC",
                    help="GitHub repo URL·일반 URL·파일·폴더 (여러 개 가능)")
    ap.add_argument("--deck", metavar="DIR", help="덱 폴더 — src/preset.css · qa/ 가 여기 생긴다")
    ap.add_argument("--out-css", metavar="PATH", help="CSS 출력 경로 (기본 <deck>/src/preset.css,"
                                                    " --deck 없으면 <qa>/style-preset.css)")
    ap.add_argument("--qa-dir", metavar="DIR", help="보고물 폴더 (기본 <deck>/qa 또는 ./qa)")
    ap.add_argument("--board", action="store_true", help="qa/style-board.html 생성")
    ap.add_argument("--json", dest="json_out", action="store_true",
                    help="qa/style-extract.json 생성")
    ap.add_argument("--md", dest="md_out", action="store_true",
                    help="qa/style-extract.md 생성")
    ap.add_argument("--name", metavar="NAME", help="팔레트 표시 이름 (기본: 소스에서 유도)")
    ap.add_argument("--offline", action="store_true", help="네트워크 fetch 를 하지 않는다")
    ap.add_argument("--force", action="store_true",
                    help="이 도구가 만든 파일이 아니어도 덮어쓴다")
    args = ap.parse_args(argv)

    ev = Evidence()
    warnings: list[str] = []
    docs, images, metas = gather_sources(args.source, args.offline, ev, warnings)
    if not docs and not images and not metas:
        print("ERROR   분석할 소스가 없습니다 — --source 를 확인하세요", file=sys.stderr)
        for w in warnings:
            print(f"WARN    {w}", file=sys.stderr)
        return 2

    # ---------------------------------------------------------- 계량
    colors: dict[str, dict] = collections.defaultdict(lambda: collections.defaultdict(float))
    fonts: dict[str, int] = {}
    radii_meas, sizes, borders, shadow = [], [], [], []
    md_pool_docs, files_kind = [], {}
    for doc in docs:
        files_kind[doc["kind"]] = files_kind.get(doc["kind"], 0) + 1
        measure_colors(doc, colors, ev)
        if doc["kind"] in ("css", "html"):
            measure_typography(doc, fonts, radii_meas, sizes, borders, shadow)
        if doc["kind"] == "markdown":
            md_pool_docs.append(measure_markdown(doc["text"]))
        if doc["kind"] == "svg":
            measure_typography(doc, fonts, radii_meas, sizes, borders, shadow)
    pool = pool_metrics(md_pool_docs) if md_pool_docs else {
        "code_share": 0.0, "quote_share": 0.0, "exclaim_per_1k": 0.0, "emoji_per_1k": 0.0,
        "number_per_100w": 0.0, "code_blocks": 0, "shell_cmds": 0, "table_rows": 0,
        "chars": 0, "words": 0, "hedge_per_1k": 0.0,
        **{f"w_{c}_hi": 0.0 for c in WORDS}, **{f"w_{c}_lo": 0.0 for c in WORDS}}
    for hexv in list(colors):
        colors[hexv]["_total"] = sum(colors[hexv].values())
    img_stats = measure_images(images, colors, ev, warnings)

    eid_metrics = {}
    if md_pool_docs:
        eid_metrics["code"] = ev.add("metric", "markdown",
                                     f"코드블록 {pool['code_share']:.1%} · 셸 명령 {pool['shell_cmds']}개")
        eid_metrics["emoji"] = ev.add("metric", "markdown", f"이모지 {pool['emoji_per_1k']:.2f}/1k 단어")
        eid_metrics["exclaim"] = ev.add("metric", "markdown", f"느낌표 {pool['exclaim_per_1k']:.2f}/1k 단어")
        eid_metrics["numbers"] = ev.add("metric", "markdown", f"수치 {pool['number_per_100w']:.2f}/100단어")
        eid_metrics["hedge"] = ev.add("metric", "markdown", f"헤징 {pool['hedge_per_1k']:.2f}/1k 단어")
        eid_metrics["table"] = ev.add("metric", "markdown", f"표 {pool['table_rows']}행 · 인용 {pool['quote_share']:.1%}")
        eid_metrics["words"] = ev.add("metric", "markdown", f"신호어 집계({pool['words']}단어)")
        eid_metrics["shell"] = eid_metrics["code"]
    if fonts:
        top = sorted(fonts.items(), key=lambda kv: -kv[1])[:6]
        eid_metrics["font"] = ev.add("metric", "typography",
                                     "font-family: " + ", ".join(f"{f}×{c}" for f, c in top))
    if radii_meas:
        eid_metrics["radius"] = ev.add("metric", "typography",
                                       f"border-radius 중앙값 {percentile(radii_meas, 50):.0f}px ×{len(radii_meas)}")
    if borders:
        eid_metrics["border"] = ev.add("metric", "typography",
                                       f"border 두께 중앙값 {percentile(borders, 50):.1f}px")
    if colors:
        eid_metrics["palette"] = ev.add("metric", "colors", f"고유 색 {len(colors)}개 관측")
    if files_kind.get("data"):
        eid_metrics["datafiles"] = ev.add("metric", "files", f"데이터 파일 {files_kind['data']}개")
    if metas:
        eid_metrics["github"] = ev.add("metric", "github", f"repo {len(metas)}개 메타")
    if img_stats.get("analyzed"):
        eid_metrics["image"] = ev.add("metric", "images",
                                      f"이미지 {img_stats['analyzed']}개 · 어두운 비율 {img_stats['dark_share']:.0%}")

    signals = palette_signals(colors, radii_meas, fonts, borders, shadow,
                              files_kind.get("data", 0), img_stats)
    tones = compute_axes(pool, signals, fonts, metas, ev, eid_metrics)

    # ---------------------------------------------------------- 팔레트 + 보정
    tokens, tok_ev, _ = derive_palette(colors, tones, ev, eid_metrics)
    radii, rules = derive_radii_rules(radii_meas, borders, shadow, sizes,
                                      tones, files_kind, ev, eid_metrics)
    adjustments = ensure_contrast(tokens, ev)
    gates, all_pass = gate_report(tokens)
    theme = recommended_theme(tones)

    flat_sources = [s for g in args.source for s in g]
    if args.name:
        name = args.name
    elif metas:
        name = metas[0]["spec"].split("/")[-1]
    else:
        first = pathlib.Path(flat_sources[0]).expanduser()
        name = first.stem
        if name.lower() in ("readme", "index", "license", "changelog", "docs"):
            name = first.resolve().parent.name or name
        name = name or "extracted"
    src_note = "소스: " + ", ".join(flat_sources[:6]) + (" …" if len(flat_sources) > 6 else "")

    # style_preset.validate — 같은 스키마로 만든 가상 프리셋을 최종 점검
    virtual = {"id": "extracted", "stem": "extracted", "name": name,
               "genre": "소스 실측 추출",
               "recommended_theme": theme,
               "intent": "소스 자료에서 실측한 색·글자·문체 신호를 edu-deck 토큰으로 옮긴 팔레트입니다.",
               "use": f"톤 축 상위: {', '.join(sorted(AXES, key=lambda a: -tones[a]['value'])[:3])}",
               "avoid": "실측 대상이 아닌 다른 브랜드의 자료에는 다시 추출하세요.",
               "tokens": {**tokens, **radii}, "rules": rules}
    bad = validate_preset(virtual)
    if bad:
        warnings.extend(f"validate: {b}" for b in bad)

    # ---------------------------------------------------------- 출력 경로
    deck_dir = pathlib.Path(args.deck).resolve() if args.deck else None
    qa_dir = (pathlib.Path(args.qa_dir).resolve() if args.qa_dir
              else deck_dir / "qa" if deck_dir else pathlib.Path.cwd() / "qa")
    css_path = (pathlib.Path(args.out_css).resolve() if args.out_css
                else deck_dir / "src" / "preset.css" if deck_dir
                else qa_dir / "style-preset.css")
    if deck_dir and not (deck_dir / "deck.json").exists():
        warnings.append(f"{deck_dir}: deck.json 이 없습니다 — 덱 폴더가 맞는지 확인하세요")

    report = {
        "tool": "extract_style.py", "version": VERSION, "marker": MARKER,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "name": name,
        "sources": [{"name": d["name"], "kind": d["kind"]} for d in docs]
                   + [{"name": str(p), "kind": "image"} for p in images],
        "github": metas,
        "metrics": pool,
        "signals": signals,
        "tones": tones,
        "fonts": sorted(fonts.items(), key=lambda kv: -kv[1])[:12],
        "palette": {"tokens": tokens, "radii": radii, "rules": rules,
                    "token_evidence": tok_ev, "adjustments": adjustments},
        "recommended_theme": theme,
        "contrast": {"gates": gates, "all_pass": all_pass},
        "evidence": ev.rows,
        "warnings": warnings,
    }

    written = []
    css_text = deck_css(tokens, rules, radii, name, src_note)
    try:
        write_generated(css_path, css_text, force=args.force)
        written.append(str(css_path))
    except FileExistsError as e:
        print(f"ERROR   {e}", file=sys.stderr)
        return 2
    if args.json_out:
        write_json(qa_dir / "style-extract.json", report)
        written.append(str(qa_dir / "style-extract.json"))
    if args.md_out:
        write_md(qa_dir / "style-extract.md", report)
        written.append(str(qa_dir / "style-extract.md"))
    if args.board:
        write_board(qa_dir / "style-board.html", report)
        written.append(str(qa_dir / "style-board.html"))

    # ---------------------------------------------------------- 요약 출력
    top3 = sorted(AXES, key=lambda a: -tones[a]["value"])[:3]
    print(f"OK      소스 {len(report['sources'])}개 분석 — 톤 상위: "
          + ", ".join(f"{a} {tones[a]['value']:.2f}" for a in top3))
    print(f"OK      대비 게이트 {len(gates)}쌍 "
          f"{'전부 통과' if all_pass else '— 미달 있음(보고서 확인)'}")
    if not all_pass:
        for g in gates:
            if not g["pass"]:
                print(f"WARN    대비 미달 {g['fg']}/{g['bg']} = {g['ratio']} < {g['need']}")
    for w in warnings:
        print(f"WARN    {w}")
    for w in written:
        print(f"OK      {w}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
