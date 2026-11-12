# 출처: ko-document-studio © 2026 acc0mplish, MIT — shared/diagram_lint.py 이식 후 벤더 경로·리포트 계약 조정
"""도식(SVG) 린트 어댑터: 벤더 svg-lint(Node)를 부르고 결과를 빌드의 [오류]·[주의]로 옮긴다.

규칙(계획 §5.5·§15 K2)
  - 덱은 표식 `data-lint="svg-diagram"` 이 시작 태그에 있는 인라인 <svg> 만 검사한다. 표식 없는 svg 는 건드리지 않는다.
  - 린트 필터는 정확히 3개(font-stack, palette-conformance, light-bg-fallback). group-box 는 palette-conformance 의 code 다.
  - 린트 내부 실패(check-crashed·model-crashed, 시간 초과, 실행 불가, 읽을 수 없는 출력)는 [오류](fail-closed).
    Node 부재만 [주의] 1줄이다. 표식 도식이 있는데 어댑터 내부 예외로 검사가 끝나지 못하면 [오류](fail-closed, 이미 모은 [오류]는 보존).
    도식 자체 검사(ours/*)만 고장나면 [주의] 1줄로 격리하고 린트는 계속한다.
  - 파이썬 표준 라이브러리만 쓴다. node 는 벤더 사본의 절대경로로만 실행한다(shell=False, 입력은 항상 절대경로).

공개 함수: node_path, extract_marked_svgs, check_path, run_lint, map_result, check_diagrams, check_files.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

LINT_JS = str(Path(__file__).resolve().parent / "vendor" / "svg-lint" / "tools" / "svg-lint" / "bin" / "svg-lint.mjs")
# 필터 = "우리 집 규격"과 다른 상류(SKILL.upstream.md) 하우스 규칙만 뺀다 — 기계 결함
# 검사(arrow-marker 경로 검사·xml-escaping·panels·document-model·font-family)는 유지한다.
# 상류도 같은 이유로 font-stack·palette-conformance·light-bg-fallback 을 걸렀다.
# - font-stack/palette-conformance: 상류 글꼴·HEX 팔레트 규격. 우리는 class 글꼴과 var(--토큰)
#   (토큰 계약은 아래 _palette_tokens 자체 검사가 본다).
# - light-bg-fallback: 상류 인쇄 규격. 우리 도식은 덱 테마를 따른다.
# - box-height·block-spacing·baseline-offset·viewbox-clipping: 상류 기하 공식
#   (상자 높이=font-size×3, 간격 25~30px, 베이스라인 0.35 보정, 마진 규칙). 우리 SI 도식은
#   더 조밀한 자체 기하라 규칙이 다르다. 실제 클리핑·넘침은 check_deck 화면 검사가
#   브라우저 실측 폰트로 잡는다(정적 추정보다 강한 계약).
# - overlap: 상류는 "선 위 라벨"을 결함으로 본다. 우리는 paint-order halo(.t-q)로
#   선 위 라벨을 정식으로 지원하고, 읽기 불가한 겹침은 화면 검사 대비·겹침 규칙이 잡는다.
# - text-overflow: 상류는 모든 라벨이 "상자 안"에 있어야 한다. 우리는 뱃지 옆 명칭
#   (k-t-spec 콜아웃)·차트 축 주석처럼 상자 밖 라벨이 정식 문법이라, 상자 모델 추정이
#   전부 오탐이다. 실제 잘림·넘침은 화면 검사가 실측으로 잡는다.
# - connector-geometry: 상류 연결선은 직교 스텝만 허용한다. 우리 차트 추세선·아이소
#   연결선은 대각이 정상이라 라인 종류를 구별 못 하는 검사가 오탐을 낸다.
FILTERED_CHECKS = frozenset({
    "font-stack", "palette-conformance", "light-bg-fallback",
    "box-height", "block-spacing", "baseline-offset", "viewbox-clipping",
    "overlap", "text-overflow", "connector-geometry",
})
# 화살촉 <marker> "정의" 대상 규칙은 상류 마커 규격(크기 8/12/16·orient="auto"·markerUnits
# 선언)이다. 우리 화살촉은 공유 스프라이트(icons/*.svg, auto-start-reverse)라 규격이
# 다르고, 사본 주입 defs 만이 이 규칙에 걸린다 — 경로 측 마커 검사(참조·기하)는 유지.
SUPPRESSED_CODES = frozenset({
    "arrow-marker/marker-units-missing", "arrow-marker/marker-orient-missing",
    "arrow-marker/marker-size-off-spec", "arrow-marker/marker-too-small-for-stroke",
})
INTERNAL_CODES = frozenset({"check-crashed", "model-crashed"})  # 린트가 "검사가 안 돌았다"고 알리는 code → [오류]
ALLOWED_WARN = frozenset()  # "check/code" 허용 목록. 사유 없는 허용 금지: 비어 있어야 "0건" 이다
OPT_IN_ATTR = 'data-lint="svg-diagram"'  # 시작 태그에만 인정(파서가 속성 이름·값으로 비교한다)
_OPT_IN = ("data-lint", "svg-diagram")
SUFFIX = ".diagram.svg"
LINT_TIMEOUT_S = 60
MAX_BYTES = 500_000  # 한 번의 린트 실행 입력 상한(파일·도식 하나, 묶음 합계). 린트 시간이 요소 수에 2차로 늘어 500KB≈17–19초, 1MB>60초 (evidence/p2b-report.md 실측)
MIN_DISPLAY_PX = 24
INFO_TAG = "[주의]"

_VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"})
_WHITE = frozenset({"#fff", "#ffffff", "white", "rgb(255,255,255)"})
_XMLNS = "http://www.w3.org/2000/svg"


@dataclass
class LintRun:
    rc: int
    data: dict | None
    stderr: str = ""
    timed_out: bool = False


@dataclass(frozen=True)
class Rec:
    """매핑 결과 한 줄. line 은 도식(svg 파일) 안의 줄(1부터), 0 은 줄 없음."""
    sev: str  # "error" | "warning" | "info"
    path: str
    line: int
    text: str


@dataclass(frozen=True)
class Mark:
    line: int   # 시작 태그가 있는 슬라이드 HTML 의 줄(1부터)
    text: str
    dark: bool  # 조상 중에 is-dark 가 있다
    xmlns: bool = False  # 시작 태그에 xmlns 속성이 이미 있다(파서가 읽은 속성으로 판정)


# ---------------------------------------------------------------- 표식 svg 추출

class _HtmlScan(HTMLParser):
    """슬라이드 HTML 을 훑어 표식 svg(깊이로 짝지음)와 그 줄·어두운 장 여부를 모은다."""

    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=True)
        self.text = text
        self._starts = [0] + [m.end() for m in re.finditer("\n", text)]
        self.stack: list[tuple[str, bool, dict | None]] = []
        self._pos: dict[str, list[int]] = {}  # 태그명 → 스택 안 위치(오름차순). 짝 없는 닫는 태그를 선형 탐색 없이 판정한다
        self.dark = 0
        self.open_marked = 0
        self.marks: list[Mark] = []
        self.unclosed: list[int] = []

    def _offset(self) -> int:
        line, col = self.getpos()
        return self._starts[line - 1] + col

    def _end_of_tag(self, start: int) -> int:
        end = self.text.find(">", start)
        return len(self.text) if end < 0 else end + 1

    @staticmethod
    def _is_marked(attrs) -> bool:
        return any((k, v) == _OPT_IN for k, v in attrs)

    def _frame(self, attrs) -> dict:
        return {"start": self._offset(), "line": self.getpos()[0], "marked": self._is_marked(attrs),
                "dark": self.dark > 0, "nested": self.open_marked > 0, "xmlns": any(k == "xmlns" for k, _v in attrs)}

    def handle_starttag(self, tag, attrs):
        if tag in _VOID_TAGS:
            return
        cls = (dict(attrs).get("class") or "").split()
        is_dark = "is-dark" in cls
        frame = self._frame(attrs) if tag == "svg" else None
        if frame and frame["marked"]:
            self.open_marked += 1
        self._pos.setdefault(tag, []).append(len(self.stack))
        self.stack.append((tag, is_dark, frame))
        if is_dark:
            self.dark += 1

    def handle_startendtag(self, tag, attrs):
        if tag == "svg" and self._is_marked(attrs):
            fr = self._frame(attrs)
            if not fr["nested"]:
                self.marks.append(Mark(fr["line"], self.text[fr["start"]:self._end_of_tag(fr["start"])], fr["dark"], fr["xmlns"]))

    def handle_endtag(self, tag):
        positions = self._pos.get(tag)
        if not positions:
            return  # 짝 없는 닫는 태그
        idx = positions[-1]
        popped = self.stack[idx:]
        del self.stack[idx:]
        for t, _d, _f in popped:
            self._pos[t].pop()  # 빠진 항목은 각 태그 목록의 맨 뒤에 있다(위치가 오름차순이므로)
        for n, (t, is_dark, fr) in enumerate(popped):
            if is_dark:
                self.dark -= 1
            if fr is None:
                continue
            if fr["marked"]:
                self.open_marked -= 1
            if n == 0 and tag == "svg":
                if fr["marked"] and not fr["nested"]:
                    end = self._end_of_tag(self._offset())
                    self.marks.append(Mark(fr["line"], self.text[fr["start"]:end], fr["dark"], fr["xmlns"]))
            elif fr["marked"] and not fr["nested"]:
                self.unclosed.append(fr["line"])  # 안쪽 svg 가 닫히지 않은 채 바깥 요소가 닫혔다

    def finish(self) -> "_HtmlScan":
        self.close()
        for _t, _d, fr in self.stack:
            if fr is not None and fr["marked"] and not fr["nested"]:
                self.unclosed.append(fr["line"])
        self.stack.clear()
        self.unclosed.sort()
        return self


def _scan_html(html: str) -> _HtmlScan:
    s = _HtmlScan(html)
    s.feed(html)
    return s.finish()


def extract_marked_svgs(html: str) -> list[tuple[int, str]]:
    """표식이 시작 태그에 있는 <svg> 만 (시작 줄 1부터, svg 텍스트) 로 돌려준다. 짝이 맞는 것만."""
    return [(m.line, m.text) for m in _scan_html(html).marks]


# ---------------------------------------------------------------- 경로 검사

def node_path() -> str | None:
    found = shutil.which("node")
    return os.path.abspath(found) if found else None


def check_path(p: Path, root: Path | None) -> str | None:
    """검사할 수 없는 사유(없으면 None). 사유가 있는 파일은 린트에 넘기지 않는다. FIFO·장치는 열지 않는다."""
    p = Path(p)
    try:
        if not os.path.lexists(p):
            return "파일이 없습니다"
        if os.path.islink(p):
            return "심볼릭 링크는 검사하지 않습니다"
        st = os.stat(p)
        if not stat.S_ISREG(st.st_mode):
            return "일반 파일이 아닙니다(FIFO·장치)"
        if root is not None:
            try:
                p.resolve().relative_to(Path(root).resolve())
            except ValueError:
                return "프로젝트 밖 파일입니다"
        if st.st_size > MAX_BYTES:
            return f"도식이 너무 큽니다(검사 불가): {st.st_size:,}바이트 > {MAX_BYTES:,}바이트"
    except (OSError, RuntimeError, ValueError) as exc:
        return f"파일 상태를 읽지 못했습니다({type(exc).__name__})"
    return None


# ---------------------------------------------------------------- 린트 실행

def _valid_shape(data) -> bool:
    return (isinstance(data, dict) and isinstance(data.get("files"), list)
            and all(isinstance(f, dict) and isinstance(f.get("findings"), list) for f in data["files"]))


def run_lint(abs_paths: list[str], node: str) -> LintRun:
    """svg-lint --json 을 한 번 실행한다. stdout 이 비어 있지 않으면 rc 와 무관하게 JSON 을 읽는다(K-1)."""
    for p in abs_paths:
        if not os.path.isabs(p):
            raise ValueError(f"절대경로만 린트에 넘길 수 있습니다: {p!r}")  # '-' 로 시작하는 파일명이 옵션이 되는 것을 막는다
    env = {k: v for k, v in os.environ.items() if k not in ("NODE_OPTIONS", "NODE_PATH")}  # 환경 변수로 코드 주입 차단
    cwd = tempfile.mkdtemp(prefix="svd-lint-cwd-")
    try:
        cp = subprocess.run([node, LINT_JS, "--json", *abs_paths], cwd=cwd, capture_output=True,
                            timeout=LINT_TIMEOUT_S, shell=False, env=env)
    except subprocess.TimeoutExpired:
        return LintRun(rc=-1, data=None, timed_out=True)
    except (OSError, ValueError) as exc:
        return LintRun(rc=-1, data=None, stderr=f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
    out = cp.stdout.decode("utf-8", errors="replace")
    err = cp.stderr.decode("utf-8", errors="replace")
    data = None
    if out.strip():
        try:
            data = json.loads(out)
        except ValueError:
            data = None
        if not _valid_shape(data):
            data = None
    return LintRun(rc=cp.returncode, data=data, stderr=err)


# ---------------------------------------------------------------- 결과 매핑

def _one_line(text: str, requested: list[str] | None = None, limit: int = 300) -> str:
    for p in requested or ():
        text = text.replace(p, os.path.basename(p))  # 임시 경로가 메시지에 새지 않게
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return first[:limit]


def _records(run: LintRun, requested: list[str]) -> tuple[list[Rec], int]:
    recs: list[Rec] = []
    filtered = 0
    if run.timed_out:
        why = f"도식 검사 시간이 초과되었습니다({LINT_TIMEOUT_S}초). 도식을 줄이거나 나누세요"
        return [Rec("error", p, 0, why) for p in requested], 0
    if run.data is None:
        tail = _one_line(run.stderr, requested)
        if run.rc == 2:
            why = f"도식 검사를 끝내지 못했습니다(svg-lint 종료 2): {tail}"
        elif run.rc == -1:
            why = f"도식 검사를 실행하지 못했습니다(node 실행 실패): {tail}"
        else:
            why = f"도식 검사 결과를 얻지 못했습니다(svg-lint 종료 {run.rc}): {tail}"
        return [Rec("error", p, 0, why.rstrip(": ")) for p in requested], 0
    by_file = {f.get("file"): f.get("findings") or [] for f in run.data["files"]}
    for path in requested:
        if path not in by_file:
            recs.append(Rec("error", path, 0, "검사하지 못함(읽기 실패)"))
            continue
        for f in by_file[path]:
            if not isinstance(f, dict):
                recs.append(Rec("error", path, 0, "검사 결과 항목을 해석하지 못했습니다"))
                continue
            check, code = str(f.get("check", "?")), str(f.get("code", "?"))
            sev = f.get("severity")
            msg = " ".join(str(f.get("message", "")).split())
            line = f.get("line")
            line = line if isinstance(line, int) and not isinstance(line, bool) and line >= 1 else 1
            tag = f"[{check}/{code}]"
            if code in INTERNAL_CODES:  # 필터보다 먼저: 필터 대상 check 가 고장나도 [오류]로 남긴다
                recs.append(Rec("error", path, line, f"{tag} 검사 도구 오류: {msg}"))
            elif check in FILTERED_CHECKS or f"{check}/{code}" in SUPPRESSED_CODES:
                filtered += 1
            elif sev == "error":
                recs.append(Rec("error", path, line, f"{tag} {msg}"))
            elif sev == "warning":
                recs.append(Rec("info" if f"{check}/{code}" in ALLOWED_WARN else "warning", path, line, f"{tag} {msg}"))
            else:
                recs.append(Rec("error", path, line, f"{tag} 알 수 없는 심각도 {sev!r}: {msg}"))
    return recs, filtered


def _render(rec: Rec, mode: str, line_of: dict[str, int] | None) -> str:
    if mode == "inline":
        base = (line_of or {}).get(rec.path, 1)
        return f"{base + (rec.line - 1 if rec.line else 0)}행: {rec.text}"  # 슬라이드 HTML 기준 줄. build_deck.relocate 가 파일:줄 로 바꾼다
    name = os.path.basename(rec.path)
    return f"{name}:{rec.line}: {rec.text}" if rec.line else f"{name}: {rec.text}"  # 독립 파일은 'N행:' 접두를 쓰지 않는다


def map_result(run: LintRun, requested: list[str], line_of: dict[str, int] | None, *,
               mode: str = "inline") -> tuple[list[str], list[str], list[str], int]:
    """(오류, 주의, 정보, 필터로 제외한 건수). 필터 3개는 건수만 센다."""
    if mode not in ("inline", "file"):
        raise ValueError(mode)
    recs, filtered = _records(run, requested)
    out = {"error": [], "warning": [], "info": []}
    for rec in recs:
        out[rec.sev].append(_render(rec, mode, line_of))
    return out["error"], out["warning"], out["info"], filtered


# ---------------------------------------------------------------- 자체 검사 (린트와 별개, [주의])

class _SvgScan(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root: dict | None = None
        self.rects: list[tuple[int, dict]] = []
        self.texts: list[tuple[int, dict]] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        line = self.getpos()[0]
        if tag == "svg" and self.root is None:
            self.root = a
        elif tag == "rect":
            self.rects.append((line, a))
        elif tag in ("text", "tspan"):
            self.texts.append((line, a))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


_NUM_MAX_LEN = 32  # 속성 값 길이 상한: 이보다 길면 숫자로 읽지 않는다(적대 입력의 역추적·float 변환 비용 차단)
_NUM_RE = re.compile(r"\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*(?:px)?\s*")


def _num(value: str | None) -> float | None:
    v = value or ""
    if len(v) > _NUM_MAX_LEN:
        return None
    m = _NUM_RE.fullmatch(v)
    return float(m.group(1)) if m else None


def _style(a: dict) -> dict:
    out = {}
    for part in (a.get("style") or "").split(";"):
        k, sep, v = part.partition(":")
        if sep:
            out[k.strip().lower()] = v.strip()
    return out


def _prop(a: dict, name: str) -> str | None:
    return _style(a).get(name, a.get(name))  # CSS(style)가 표현 속성보다 이긴다


def _viewbox(root: dict) -> tuple[float, float, float, float] | None:
    parts = re.split(r"[\s,]+", (root.get("viewbox") or "").strip())
    try:
        vb = tuple(float(x) for x in parts)
    except ValueError:
        return None
    return vb if len(vb) == 4 and vb[2] > 0 and vb[3] > 0 else None


def _is_white(fill: str | None) -> bool:
    f = re.sub(r"\s+", "", (fill or "").lower())
    return f in _WHITE or re.match(r"var\(--paper\b", f) is not None


def _covers(a: dict, vb: tuple[float, float, float, float]) -> bool:
    x, y = _num(a.get("x", "0")), _num(a.get("y", "0"))
    w = vb[2] if (a.get("width") or "").strip() == "100%" else _num(a.get("width"))
    h = vb[3] if (a.get("height") or "").strip() == "100%" else _num(a.get("height"))
    if None in (x, y, w, h):
        return False
    tol = 1.0
    return x <= vb[0] + tol and y <= vb[1] + tol and x + w >= vb[0] + vb[2] - tol and y + h >= vb[1] + vb[3] - tol


def _fmt_px(v: float) -> str:
    return f"{round(v, 2):g}"


def _add_unit(units: list[str], raw: str) -> None:
    m = re.search(r"[A-Za-z%]+\s*$", raw)
    unit = m.group(0).strip() if m else raw[:12]
    if unit not in units:
        units.append(unit)


def own_checks(svg_text: str, *, dark: bool) -> list[tuple[int, str]]:
    """(svg 안의 줄, "[ours/code] 메시지") 목록. 모두 [주의]."""
    scan = _SvgScan()
    scan.feed(svg_text)
    scan.close()
    root = scan.root or {}
    vb = _viewbox(root)
    found: list[tuple[int, str]] = []
    if dark and vb is not None:
        for line, a in scan.rects:
            if _covers(a, vb) and _is_white(_prop(a, "fill")):
                found.append((line, "[ours/dark-cover-white-bg] 어두운 장의 도식에 흰 바탕이 있습니다(표지 흰 바탕 생략 규칙)"))
                break  # 도식마다 1건
    width_raw = (root.get("width") or "").strip()
    width = _num(width_raw)
    if vb is not None and (width or width_raw):
        scale = width / vb[2] if width else None
        width_bad = bool(width_raw) and width is None  # %·em 등: 표시 폭을 알 수 없다
        groups: dict[float, list[int]] = {}
        units: list[str] = []
        unknown_line = 0
        for line, a in scan.texts:
            raw = (_prop(a, "font-size") or "").strip()
            size = _num(raw)
            if size is None:
                if raw:  # 해석 불가 단위는 무음 통과하지 않고 [주의] 로 보고한다
                    _add_unit(units, raw)
                    unknown_line = unknown_line or line
                continue
            if width_bad and not unknown_line:
                unknown_line = line
            if scale is None:
                continue
            shown = round(size * scale, 2)
            if shown < MIN_DISPLAY_PX:
                groups.setdefault(shown, []).append(line)
        if width_bad and unknown_line:
            _add_unit(units, width_raw)
        if units or (width_bad and unknown_line):
            found.append((unknown_line, f"[ours/min-display-text] 표시 글자 크기를 확인하지 못함(단위: {', '.join(units)})"))
        for shown, lines in sorted(groups.items()):
            more = f" — 같은 크기 {len(lines)}곳" if len(lines) > 1 else ""
            found.append((lines[0], f"[ours/min-display-text] 표시 글자 {_fmt_px(shown)}px({MIN_DISPLAY_PX}px 미만){more}"))
    found.extend(_palette_tokens(svg_text))
    return found


# 팔레트는 우리 토큰으로 매핑한다: 생성기 산출은 var(--토큰) 참조가 원칙이고,
# 벤더 팔레트(lib/palette.mjs)는 상류 도식 규격이라 우리 덱에는 맞지 않아
# palette-conformance 는 필터(FILTERED_CHECKS)로 두고 여기서 토큰 계약을 검사한다.
_TOKEN_COLORS = re.compile(r"^(?:none|currentColor|transparent|inherit|var\([^)]*\)|url\(#[^)]*\))$", re.I)
_COLOR_ATTR = re.compile(r'\b(?:fill|stroke|stop-color|flood-color)\s*=\s*"([^"]*)"')


def _palette_tokens(svg_text: str) -> list[tuple[int, str]]:
    """fill/stroke 계열 속성의 리터럴 색을 [주의]로 보고한다 — var(--토큰)·none·currentColor·url(#ref)만 허용."""
    found: list[tuple[int, str]] = []
    seen: set[str] = set()
    for ln, line in enumerate(svg_text.split("\n"), 1):
        for raw in _COLOR_ATTR.findall(line):
            v = raw.strip()
            if not v or _TOKEN_COLORS.match(v):
                continue
            if v not in seen:
                seen.add(v)
                found.append((ln, f"[ours/palette-token] 리터럴 색 \"{v[:24]}\" — var(--토큰) 참조를 쓴다"))
            if len(found) >= 3:
                return found
    return found


# ---------------------------------------------------------------- 덱 (인라인 도식)

def _with_xmlns(svg: str, has_xmlns: bool) -> str:
    """독립 파일로 린트하므로 xmlns 가 없으면 시작 태그에 더한다(줄 번호는 바뀌지 않는다)."""
    m = re.match(r"<svg\b", svg, re.I)
    if has_xmlns or not m:
        return svg
    return svg[:m.end()] + f' xmlns="{_XMLNS}"' + svg[m.end():]


# 우리 도식은 글자 크기를 CSS 클래스로 준다(.t-l{26px} 등). 벤더 문서모델은
# font-size 속성만 읽고 없으면 12px 로 가정해 연쇄 오측정이 나므로, 린트용
# 사본에는 우리 CSS 에서 읽은 클래스→px 실측값을 속성으로 심는다(덱 출력 무수정).
_CSS_DIRS = (
    Path(__file__).resolve().parent.parent / "assets" / "css",
)
_ICON_DIRS = (
    Path(__file__).resolve().parent.parent / "assets" / "icons",
)
_CLASS_PX: dict[str, float] | None = None
_MARKER_DEFS: str | None = None


def _marker_defs() -> str:
    """아이콘 스프라이트의 <marker> 정의 — 덱에서는 전역 defs 로 해석되지만,
    린트용 분리 사본에는 없어 dangling 오탐이 나므로 사본에 심는다."""
    global _MARKER_DEFS
    if _MARKER_DEFS is None:
        out: list[str] = []
        for d in _ICON_DIRS:
            for f in sorted(d.glob("*.svg")):
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                out.extend(m.group(0) for m in re.finditer(r"<marker\b.*?</marker>|<marker\b[^>]*/>", text, re.S))
        _MARKER_DEFS = "<defs>" + "".join(out) + "</defs>" if out else ""
    return _MARKER_DEFS


def _class_px() -> dict[str, float]:
    global _CLASS_PX
    if _CLASS_PX is None:
        table: dict[str, float] = {}
        for d in _CSS_DIRS:
            for css in sorted(d.glob("*.css")):
                try:
                    text = css.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for m in re.finditer(r"\.([A-Za-z][\w-]*)\s*(?:[^{}]*)\{\s*font-size:\s*([\d.]+)px", text):
                    table.setdefault(m.group(1), float(m.group(2)))
        _CLASS_PX = table
    return _CLASS_PX


_TEXT_TAG = re.compile(r"<text\b[^>]*>", re.I)
_CLASS_ATTR = re.compile(r'class\s*=\s*"([^"]*)"')


def _with_measurements(svg: str) -> str:
    """린트 사본에만 font-size 속성(class→px)·width(viewBox 폭)을 심는다."""
    table = _class_px()

    def fix_text(m: re.Match) -> str:
        tag = m.group(0)
        if "font-size" in tag:
            return tag
        cls = _CLASS_ATTR.search(tag)
        if not cls:
            return tag
        px = next((table[c] for c in cls.group(1).split() if c in table), None)
        if px is None:
            return tag
        return tag[:-1] + f' font-size="{px:g}">'

    svg = _TEXT_TAG.sub(fix_text, svg)
    m = re.match(r"<svg\b[^>]*>", svg, re.I)
    if m and "width" not in m.group(0):
        vb = re.search(r'viewBox\s*=\s*"([^"]+)"', m.group(0))
        if vb:
            parts = vb.group(1).split()
            if len(parts) == 4:
                svg = svg[:m.end() - 1] + f' width="{float(parts[2]):g}"' + svg[m.end() - 1:]
    defs = _marker_defs()
    if defs:
        end = svg.find(">", svg.find("<svg"))
        if end != -1:
            svg = svg[: end + 1] + defs + svg[end + 1:]
    return svg


def _size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0  # 검사 직후 사라진 파일: 크기는 몰라도 린트가 "검사하지 못함" [오류]로 올린다


def _chunks(items: list[tuple[str, int]]) -> list[list[str]]:
    """파일 크기 합이 MAX_BYTES 이하가 되도록 묶는다. 한 번의 린트 실행 시간을 실측 범위 안에 둔다."""
    out: list[list[str]] = []
    cur: list[str] = []
    total = 0
    for path, size in items:
        if cur and total + size > MAX_BYTES:
            out.append(cur)
            cur, total = [], 0
        cur.append(path)
        total += size
    if cur:
        out.append(cur)
    return out


def _unfinished(exc: BaseException) -> str:
    return f"도식 검사를 끝내지 못했습니다(내부 오류: {type(exc).__name__})"


def _check_diagrams(slides_html: str, rep) -> None:
    if not re.search(r"data-lint", slides_html, re.I):
        return  # 표식 글자가 아예 없는 덱: 파서도 돌리지 않는다(기존 덱 출력 불변·비용 0)
    scan = _scan_html(slides_html)
    for line in scan.unclosed:
        rep.errors.append(f'{line}행: 표식 도식(data-lint="svg-diagram")의 닫는 태그 </svg> 를 찾지 못했습니다.')
    marks = scan.marks
    if not marks:
        return  # 표식이 없으면 아무것도 출력하지 않는다
    ours: list[str] = []
    big: set[int] = set()
    for i, mk in enumerate(marks):
        if len(mk.text.encode("utf-8", errors="replace")) > MAX_BYTES:
            big.add(i)
            continue
        try:
            for ln, text in own_checks(mk.text, dark=mk.dark):
                ours.append(f"{mk.line + ln - 1}행: {text}")
        except Exception as exc:  # noqa: BLE001 - 자체 검사 고장이 린트(게이트) 실행을 막지 않게 한다
            ours.append(f"{mk.line}행: 도식 자체 검사를 건너뜀(내부 오류): {type(exc).__name__}")
    for i in sorted(big):  # 크기 초과는 Node 없이도 [오류]다(Node 분기보다 앞)
        mk = marks[i]
        rep.errors.append(f"{mk.line}행: 도식이 너무 큽니다(검사 불가): {len(mk.text.encode('utf-8', errors='replace')):,}바이트 > {MAX_BYTES:,}바이트")
    node = node_path()
    if node is None:
        rep.warnings.append(f"도식 검사를 건너뜀: Node.js를 찾지 못했습니다(표식 도식 {len(marks)}곳).")
        rep.warnings.extend(ours)
        return
    tmp = None
    try:
        tmp = tempfile.mkdtemp(prefix="svd-lint-")
        line_of: dict[str, int] = {}
        sized: list[tuple[str, int]] = []
        for i, mk in enumerate(marks):
            if i in big:
                continue
            p = Path(tmp) / f"slide-{i + 1}.svg"
            p.write_bytes(_with_measurements(_with_xmlns(mk.text, mk.xmlns)).encode("utf-8", errors="replace"))
            reason = check_path(p, None)
            if reason:
                rep.errors.append(f"{mk.line}행: {reason}")
                continue
            line_of[str(p)] = mk.line
            sized.append((str(p), p.stat().st_size))
        filtered = 0
        for chunk in _chunks(sized):
            errors, warnings, infos, n = map_result(run_lint(chunk, node), chunk, line_of, mode="inline")
            rep.errors.extend(errors)
            rep.warnings.extend(warnings)
            rep.notes.extend(infos)
            filtered += n
        if filtered:
            rep.notes.append(f"도식 규칙 필터로 {filtered}건 제외")
    except Exception as exc:  # noqa: BLE001 - 표식 도식이 있는데 검사가 끝나지 못했다: 조용히 통과시키지 않는다(fail-closed)
        rep.errors.append(_unfinished(exc))  # 이미 모은 린트 [오류]는 그대로 남는다
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
    rep.warnings.extend(ours)


def check_diagrams(slides_html: str, project: Path, rep, *, sources=None) -> None:
    """덱의 표식 도식을 검사해 rep.errors·warnings·notes 에 더한다. build_deck.validate() 가 relocate 이전에 부른다.

    project·sources 는 호출 규약을 맞추려고 받는다(줄 번호의 파일:줄 변환은 validate() 의 relocate 가 한다).
    표식 도식이 있는데 어댑터 내부 예외로 검사가 끝나지 못하면 [오류] 1건(빌드는 멈추지 않고 게이트가 막는다). 린트가 낸 [오류]는 그대로 남는다.
    표식이 없으면 _check_diagrams 가 예외를 낼 코드에 닿지 않고 무출력으로 끝난다(예외는 표식 판독 중에만 가능 — 이 경우도 [오류]).
    """
    try:
        _check_diagrams(slides_html, rep)
    except Exception as exc:  # noqa: BLE001 - 빌드를 멈추지 않되 침묵하지 않는다
        rep.errors.append(_unfinished(exc))


# ---------------------------------------------------------------- 독립 파일 (ko-doc)

def _file_label(name: str, line: int) -> str:
    return f"{name}:{line}" if line else name


def _check_files(paths: list[Path], root: Path | None, diag) -> None:
    ok: list[str] = []
    for p in paths:
        ap = Path(os.path.abspath(p))  # resolve() 가 아니다: 심볼릭 링크를 따라가면 check_path 가 못 본다
        reason = check_path(ap, root)
        if reason:
            diag.err(ap.name, reason)
        else:
            ok.append(str(ap))
    if not ok:
        return
    # 책(ko-doc) 경로는 24px 최소 글자 규칙(ours/min-display-text)을 실행하지 않는다(§19 E19-1, A5·Q2).
    node = node_path()
    if node is None:
        diag.info("도식", f"{INFO_TAG} 도식 검사를 건너뜀: Node.js를 찾지 못했습니다(독립 도식 {len(ok)}개).")
        return
    sized = [(p, _size(p)) for p in ok]
    filtered = 0
    for chunk in _chunks(sized):
        recs, n = _records(run_lint(chunk, node), chunk)
        filtered += n
        for rec in recs:
            label = _file_label(os.path.basename(rec.path), rec.line)
            if rec.sev == "error":
                diag.err(label, rec.text)
            else:  # [주의] 는 정보 줄로: diag.warn 은 쓰지 않는다(release 정책)
                diag.info(label, f"{INFO_TAG} {rec.text}" if rec.sev == "warning" else rec.text)
    if filtered:
        diag.info("도식", f"도식 규칙 필터로 {filtered}건 제외")


def check_files(paths: list[Path], root: Path | None, diag) -> None:
    """독립 *.diagram.svg 를 검사한다. [오류] → diag.err, [주의] 와 자체 검사 → diag.info('[주의] …').

    Diag 가 '{path}: {msg}' 로 붙이므로 path 에 '파일명:줄' 을 넣어 최종 줄이 '파일명:줄: [check/code] …' 가 된다.
    """
    paths = list(paths)
    if not paths:
        return
    try:
        _check_files(paths, root, diag)
    except Exception as exc:  # noqa: BLE001 - 독립 도식이 있는데 검사가 끝나지 못했다: [오류](fail-closed)
        diag.err("도식", _unfinished(exc))
