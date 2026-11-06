#!/usr/bin/env python3
"""edu-deck-solo 덱 검사기.

[파일 목적]
  완성된 단일 HTML 덱이 형식 규칙을 지키는지, 실제 브라우저에서 글자가 넘치거나 잘리지 않는지 검사한다.
  사람이 눈으로 보기 전에 기계로 잡을 수 있는 결함(자리표시 남음, 외부 파일 의존, 빠진 아이콘,
  화면 밖으로 나간 글자, 상자 밖으로 흘러넘친 글자, 너무 작은 글자, 겹친 글자)을 먼저 걸러 낸다.

[주요 흐름]
  1. 정적 검사(BeautifulSoup): 슬라이드 구조·아키타입·발표자 노트·자리표시·외부 자원·아이콘 참조·id 중복·
     단계 값·사실 칩·분량·덱 흐름(순서 → … → 마무리).
  2. 화면 검사(Playwright + Chrome, 1920×1080): 모든 슬라이드의 모든 단계 상태마다
     화면 밖 넘침, 잘린 글자, 상자 밖 넘침, 글자 크기, 대비, 글자 겹침, 스크립트 오류를 잰다.
     1차 패스에서는 모션 시그니처 발화 기록(eduMotion.sigLog)도 읽어 무성 장을 WARN 로 보고한다.
  3. 선택: --sheets 로 슬라이드 축소판 모음 PNG, --shots 로 슬라이드별 원본 크기 PNG 를 만든다.
  4. 선택: --contrast-matrix 로 렌더와 별개로 tokens.css 의 색 대비를 기본+8팩 × 쌍 전수 채점한다.
  5. 결과 줄(ERROR/WARN/INFO)과 마지막 RESULT 줄을 출력하고 종료 코드로 알린다.

[외부 연결]
  입력: scripts/build_deck.py 가 만든 HTML. 엔진 계약(window.deckGo, 단계 속성)은 assets/shell.html.
  필요: beautifulsoup4(정적), playwright + Chrome(화면). 없으면 설치하지 않고 NOT_RUN 으로 알린다.
  종료 코드: 0 통과, 1 ERROR 있음, 2 사용법·파일·필수 모듈 문제, 3 정적 통과·화면 검사 못 함.

[수정시 주의]
  ARCHETYPES 목록은 references/layouts.md 와 SKILL.md 의 아키타입 표와 짝이다.
  화면 검사 기준(넘침 2px, 글자 18/20px, 대비 4.5/3.0)을 바꾸면 references/expression.md 의 규칙도 함께 고친다.
"""
import argparse
import base64
import io
import json
import re
import sys
from pathlib import Path

from resource_packs import PackError, validate_selection

try:
    from tone_router import ARCS
except ImportError:  # tone_router 없이 check_deck 만 단독 배포된 경우 arc 판정만 끈다
    ARCS = {}

ARCHETYPES = {
    "cover", "agenda", "timeline", "map", "mechanism", "traits-grid", "meter", "compare-2", "compare-table",
    "hub", "levels", "tile-grid", "sequence", "mapping", "mock-legend", "mock-options", "statement", "build-up",
    "frame-form", "before-after", "worked-example", "quiz-ab", "quiz-sort", "quiz-ox", "rules-dark", "checklist",
    "closing", "sources", "check", "stat-strip",
    # TASK-tools G3~G5: 도구·재료 확장 조각(33~36)
    "chart-bar", "chart-line", "explore", "detail-sheet",
    # TASK-stack: 구성도·업무 흐름 부품(37)
    "arch-flow",
    # TASK-miniflow-divider: 파트 구분지 계열(38)
    "part-divider",
    # TASK-quadrant-flash: 2×2 사분면(39)·플래시카드(40)
    "quadrant", "flashcards",
}
# TASK-figslots: 본문 장의 시각/텍스트/고정 형식 분류 — references/layouts.md '텍스트 나열' 절과 짝.
# 시각(도식·차트 03~14·18·31·33·34, 모형 15·16, 채팅 21, 구성도 37)과 .fig-slot·data-variant="fig" 은
# 나열 계산을 끊고, 고정 형식(cover·quiz·sources·closing·check·explore·detail-sheet·screen-cite= mapping 아키타입)은
# 연속열에서 빠진다(세지도 끊지도 않는다). 나머지 본문 계열은 텍스트로 센다.
# TASK-miniflow-divider: .vflow·.vpills(미니 흐름) 보유 장도 시각으로 센다(fig-slot 과 같은 취급).
VISUAL_ARCHS = {"timeline", "map", "mechanism", "traits-grid", "meter", "compare-2", "compare-table",
                "hub", "levels", "tile-grid", "sequence", "mapping", "build-up", "stat-strip",
                "chart-bar", "chart-line", "mock-legend", "mock-options", "worked-example", "arch-flow",
                "quadrant", "flashcards"}
FIXED_ARCHS = {"cover", "quiz-ab", "quiz-sort", "quiz-ox", "check", "sources", "closing",
               "explore", "detail-sheet", "part-divider"}
TEXT_RUN_MIN = 5  # 본문 장 연속열에서 텍스트 계열만 이 수 이상 이어지면 WARN
STAT_NUM_CLASS = "stat-num"          # 숫자 증거 띠 큰 숫자(numbers() 숫자 릴 대상)
STAT_BUDGETS = (12, 16)              # catalog.json 을 못 읽을 때의 폴백 예산(숫자, 라벨)
CITE_IMG_BUDGET = 700 * 1024         # 실물 화면 이미지 1장 권장(지시문 P1-2) — catalog screen_image_kb 우선
DECK_RASTER_BUDGET = 1536 * 1024     # 덱 라스터 합계 1.5MB(기존 규칙 — expression.md 6절) — catalog screen_total_mb 우선
DECK_FILE_BUDGET = 8 * 1024 * 1024   # 덱 파일 총 크기 권장 8MB(TASK-tools G6 — 임베드 폰트 포함, INFO 수준)
DATA_IMG = re.compile(r"data:image/[\w.+-]+;base64,([A-Za-z0-9+/=\s]+)")
STEP_ATTRS = ("data-step", "data-add", "data-only", "data-lit", "data-until")
# data-fx 효과(assets/js/motion.js 의 FX 표와 같은 기본 길이, ms). 장당 최종 종료 시각 3초 상한.
FX_KINDS = {"strike": 500, "stamp": 500, "mark": 800, "count": 800,
            "travel": 800, "block": 800, "type": 1500, "press": 300,
            # TASK-motions 공통 기법 5종 — weight-wave 는 wght 왕복×1.8 기준.
            "scatter-gather": 800, "slice-reveal": 800, "row-mask-rise": 500,
            "weight-wave": 900, "rack-focus": 500}
# 라틴 단어(내부 .-' 허용)가 공백으로 이어져 6개 이상 = 외국어 문장으로 본다.
FOREIGN_RUN = re.compile(
    r"[A-Za-z]+(?:[.,'\-’][A-Za-z]+)*(?:\s+[A-Za-z]+(?:[.,'\-’][A-Za-z]+)*){5,}")
FOREIGN_SKIP_TAGS = ("aside", "svg", "script", "style", "pre", "code")
FOREIGN_SKIP_CLASSES = ("code", "kbd", "fact", "sc-src", "b-url", "src-list")
# 말투 WARN: AI 티가 강한 표현이 한 장에 SLOP_MIN 번 이상 나오면 잡는다.
# 고정밀 소규모 집합 — copyedit.md 4절 내장 체크리스트와 같은 기준의 보조 신호.
# (표현, 발표자 노트도 함께 세는가) — 노트는 되어지·에 의해 같은 번역투만 본다.
SLOP_MIN = 4
SLOP_PATTERNS = (
    ("되어지", True),
    ("에 의해", True),
    ("하는 것이 중요합니다", False),
    ("혁신적", False),
    ("획기적", False),
    ("할 수 있습니다", False),
)
CARD_SEL = ".card, .ft, .sk-card, .opt, .qrow, .todo, .lv, .hrow, .tp, .mode"
EXTERNAL = re.compile(r"^\s*(https?:)?//", re.I)
PACK_META = "edu-deck-resource-pack"
# 카드 가로줄 판정: 같은 부모 아래 3개 이상이 가로로 늘어서면 텍스트 상자 나열로 읽힌다.
# .row·격자 클래스는 가로 배치, .col·stack 은 세로 쌓기라 제외한다(classes.md 의 배치 규약).
ROW_CONTAINER_CLASSES = {"row", "skg", "ft-grid", "rm",
                         "ed-hub", "ed-tree", "ed-compare", "ed-map", "ed-flow"}
COL_CONTAINER_CLASSES = {"col", "stack"}
CARD_ROW_EXEMPT = {"cover", "statement", "check", "sources", "closing", "checklist", "agenda"}


def is_card_row(parent):
    """부모가 카드·칸을 가로로 늘어놓는 배치(가로 flex·열 격자)인지 마크업만으로 추정한다."""
    classes = set(parent.get("class", []))
    if classes & COL_CONTAINER_CLASSES:
        return False
    if classes & ROW_CONTAINER_CLASSES:
        return True
    style = (parent.get("style") or "").replace(" ", "").lower()
    if "flex-direction:column" in style:
        return False
    return "grid-template-columns" in style or "display:flex" in style or "display:inline-flex" in style
# Transparent layout regions are real text boundaries too, even without borders/backgrounds.
PACK_CONTAINER_SEL = (
    ".editorial-lead, .editorial-story, .editorial-margin, .editorial-bottom, "
    ".lab-question, .lab-observation, .lab-evidence, .lab-next, "
    ".field-sign, .field-row, .casebook-narrative, .casebook-exhibit, .casebook-decision, "
    ".atlas-heading, .atlas-origin, .atlas-source, .atlas-destination, "
    ".workbook-read, .workbook-write, .workbook-reference, .workbook-answer, "
    ".briefing-thesis, .briefing-row, .seminar-floor, .seminar-preparation, "
    ".seminar-source, .seminar-invitation"
)


# ---------------------------------------------------------------- 결과 모음
# 취향 규칙 kind 집합 — 길이·개수·구성·권고 성격(TASK-free-mode G1 재분류표 C 부분).
# 이 kind 의 WARN 은 안전 가드가 아니므로 자유 모드 기본 실행에서 INFO 로 내리고 요약
# 한 줄만 보이며, --style 에서 기존 WARN 으로 보인다. ERROR 항목은 심각도가 바뀌지 않는다.
TASTE_KINDS = {
    "제목", "제목 줄 수", "단계", "분량", "말투", "목록", "카드", "카드 나열",
    "사실 칩", "증거 띠", "실물 화면", "확인 문제", "발표자 노트", "모션", "모션 길이",
    "외국어 문장", "흐름", "표지", "예상 시간", "시간 합계", "대본 분량", "시각 짝",
    "무성 장", "글자 크기", "글자 겹침",
}


class Report:
    """검사 결과를 슬라이드별로 모으고, 같은 결함은 한 줄로 합친다(단계 번호만 덧붙임).

    style=False(기본)이면 TASTE_KINDS 의 WARN 을 INFO 로 내려 개별 줄 대신 요약 한 줄로
    보고하고, style=True(--style)이면 취향 규칙도 기존 WARN 심각도 그대로 출력한다.
    """

    def __init__(self, style=False):
        self.style = style       # True 이면 취향 규칙을 WARN 으로 유지(--style)
        self.items = []          # (sev, slide_no or None, kind, message)
        self._merge = {}         # (slide_no, kind, target) → item index
        self.slide_meta = {}     # slide_no → (archetype, title)
        self.slide_sigs = {}     # slide_no → 발화한 시그니처 목록(P0-2 무성 장 감사)

    def add(self, sev, slide_no, kind, message, target=None, step=None):
        taste = sev == "WARN" and kind in TASTE_KINDS
        if taste and not self.style:
            sev = "INFO"
        key = (slide_no, kind, target or message)
        if key in self._merge:
            i = self._merge[key]
            if step is not None and step not in self.items[i]["steps"]:
                self.items[i]["steps"].append(step)
            return
        self._merge[key] = len(self.items)
        self.items.append({"sev": sev, "slide": slide_no, "kind": kind, "message": message,
                           "steps": [] if step is None else [step], "taste": taste})

    def count(self, sev):
        return sum(1 for it in self.items if it["sev"] == sev)

    def lines(self):
        order = {"ERROR": 0, "WARN": 1, "INFO": 2}
        rows = [it for it in self.items if not (it.get("taste") and not self.style)]
        rows.sort(key=lambda it: (it["slide"] or 0, order[it["sev"]]))
        out = []
        for it in rows:
            where = ""
            if it["slide"]:
                arch, title = self.slide_meta.get(it["slide"], ("?", ""))
                where = f"[#{it['slide']} {arch} “{title[:20]}”] "
            steps = f" (단계 {','.join(map(str, sorted(it['steps'])))})" if it["steps"] else ""
            out.append(f"{it['sev']:<6} {where}{it['kind']}: {it['message']}{steps}")
        if not self.style:
            taste_items = [it for it in self.items if it.get("taste")]
            if taste_items:
                counts = {}
                for it in taste_items:
                    counts[it["kind"]] = counts.get(it["kind"], 0) + 1
                breakdown = "·".join(f"{k} {v}" for k, v in sorted(counts.items()))
                out.append(f"INFO   취향: {len(taste_items)}개 항목이 있습니다 ({breakdown}) — --style 로 상세 표시")
        return out


# ---------------------------------------------------------------- 정적 검사
try:
    from bs4 import Comment
except ImportError:  # main() 이 설치 안내와 함께 종료한다
    Comment = str


def text_of(node):
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)) if node else ""


def stat_budgets():
    """숫자 증거 띠 글자 예산(숫자, 라벨)을 packs/catalog.json content_budget 에서 읽는다.

    [목적] 예산의 정본은 catalog.json 이고 검사기는 소비만 한다(두 곳에 각각 두면 어긋난다).
    [출력] (stat_number, stat_label). catalog 을 못 읽으면 코드 폴백값(지시문 P1-1 예시 값)을 쓴다.
    """
    catalog = Path(__file__).resolve().parents[1] / "assets" / "packs" / "catalog.json"
    try:
        budget = json.loads(catalog.read_text(encoding="utf-8")).get("content_budget", {})
        return int(budget["stat_number"]), int(budget["stat_label"])
    except (OSError, ValueError, KeyError, TypeError):
        return STAT_BUDGETS


def cite_budgets():
    """실물 화면 이미지 예산(1장 bytes, 덱 합계 bytes)을 catalog content_budget 에서 읽는다.

    [목적] stat_budgets 와 같은 원칙 — 정본은 catalog.json(screen_image_kb·screen_total_mb, 단위가 이름에 있다).
    [출력] (1장 권장, 덱 합계). catalog 을 못 읽으면 코드 폴백값(700KB 권장 / 1.5MB 기존 규칙)을 쓴다.
    """
    catalog = Path(__file__).resolve().parents[1] / "assets" / "packs" / "catalog.json"
    try:
        budget = json.loads(catalog.read_text(encoding="utf-8")).get("content_budget", {})
        return int(budget["screen_image_kb"]) * 1024, int(round(float(budget["screen_total_mb"]) * 1024 * 1024))
    except (OSError, ValueError, KeyError, TypeError):
        return CITE_IMG_BUDGET, DECK_RASTER_BUDGET


def data_uri_bytes(payload):
    """base64 페이로드 문자열의 디코딩 크기(bytes). 못 풀면 None(예산 계산에서 뺀다)."""
    try:
        return len(base64.b64decode(re.sub(r"\s+", "", payload), validate=False))
    except (ValueError, TypeError):
        return None


def slide_title(sec):
    """기존 제목 선택자를 유지하고 팩 질문(.pack-prompt)을 제목으로 읽는다."""
    for sel in (".title", ".big", ".pack-prompt"):
        el = sec.select_one(sel)
        if el:
            return text_of(el)
    typed = sec.select_one("#cx-typed")
    return typed.get("data-text", "") if typed else ""


def is_pack_slide(sec):
    """Treat partial pack markup as an attempted pack, never as a legacy escape hatch."""
    classes = sec.get("class", [])
    return sec.has_attr("data-design") or "pack" in classes or any(c.startswith("pack-") for c in classes)


def pack_checks(soup, slides, rep):
    """Validate serialized builder selection and matching slide identities before opting out of legacy flow."""
    metadata = soup.find_all("meta", attrs={"name": PACK_META})
    pack_slides = [(i, sec) for i, sec in enumerate(slides, 1) if is_pack_slide(sec)]
    if not metadata and not pack_slides:
        return None
    if len(metadata) != 1 or metadata[0].parent is not soup.head:
        rep.add("ERROR", None, "리소스팩", f"head 안에 {PACK_META} 메타데이터가 정확히 1개 필요합니다")
        return None
    try:
        selection = validate_selection(json.loads(metadata[0].get("content", "")))
    except (ValueError, PackError) as exc:
        rep.add("ERROR", None, "리소스팩", f"잘못된 팩 메타데이터: {exc}")
        return None
    if not pack_slides:
        rep.add("ERROR", None, "리소스팩", "메타데이터는 있지만 팩 슬라이드가 없습니다")
        return None
    valid = True
    for i, sec in enumerate(slides, 1):
        classes = sec.get("class", [])
        designs = {c for c in classes if c.startswith("pack-")}
        if (sec.get("data-design") != selection["design"] or "pack" not in classes
                or designs != {"pack-" + selection["design"]}):
            rep.add("ERROR", i, "리소스팩", "data-design 및 pack/pack-{design} 클래스가 덱 디자인과 일치해야 합니다")
            valid = False
        if not text_of(sec.select_one(".pack-prompt")):
            rep.add("ERROR", i, "리소스팩", "팩 슬라이드에 비어 있지 않은 .pack-prompt 제목이 필요합니다")
            valid = False
    return selection if valid else None


def static_checks(html_text, soup, rep, allow_placeholders):
    """
    [목적] 브라우저 없이 HTML 구조만으로 판단할 수 있는 규칙을 검사한다.
    [입력] 원문 HTML 문자열, 파싱 결과, Report, 자리표시 허용 여부(갤러리 검사용)
    [출력] 슬라이드 목록(section 요소). 결과는 rep 에 쌓인다.
    [연결] main() 이 화면 검사 전에 호출한다. 슬라이드 번호와 제목은 rep.slide_meta 로 화면 검사와 공유한다.
    [주의] 덱 흐름 규칙(순서 슬라이드, 퀴즈, 마무리)은 WARN 이다. 짧은 덱이나 특수 목적 덱에서는 의도일 수 있다.
    [수정시 영향] ERROR 로 올리면 기존 덱이 갑자기 실패할 수 있으니 SKILL.md 의 완료 기준과 맞춘다.
    """
    stage = soup.select_one("#stage")
    slides = stage.find_all("section", class_="slide", recursive=False) if stage else []
    if not slides:
        rep.add("ERROR", None, "구조", "#stage 아래 section.slide 가 없습니다")
        return []
    title_tag = soup.find("title")
    if not title_tag or not title_tag.get_text(strip=True) or "{{" in title_tag.get_text():
        rep.add("ERROR", None, "구조", "<title> 이 비었거나 표식이 남았습니다")

    no_comments = re.sub(r"<!--.*?-->", "", html_text, flags=re.S)
    if not allow_placeholders and "«" in no_comments:
        n = len(re.findall(r"«[^»]*»", no_comments))
        rep.add("ERROR", None, "자리표시", f"«…» 자리표시 {n}개가 남았습니다")

    ids = {}
    for el in soup.find_all(id=True):
        ids[el["id"]] = ids.get(el["id"], 0) + 1
    for k, n in ids.items():
        if n > 1:
            rep.add("ERROR", None, "id 중복", f"id=\"{k}\" 가 {n}번 있습니다")
    for el in soup.find_all(["use", "mpath"]):
        ref = el.get("href") or el.get("xlink:href") or ""
        if ref.startswith("#") and ref[1:] not in ids:
            rep.add("ERROR", None, "아이콘", f"{ref} 를 찾을 수 없습니다 (아이콘 id 확인: references/icons.md)", target=ref)
    for ref in set(re.findall(r"url\(#([\w-]+)\)", no_comments)):
        if ref not in ids:
            rep.add("ERROR", None, "참조", f"url(#{ref}) 대상이 없습니다", target=ref)

    sources = [s for s in slides if s.get("data-archetype") == "sources"]
    for el in soup.find_all(["img", "script", "link", "iframe", "video", "audio", "source", "object", "embed", "image", "a"]):
        for attr in ("src", "href", "xlink:href", "data"):
            val = el.get(attr)
            if not val or not EXTERNAL.match(val):
                continue
            if el.name == "a" and any(el in s.descendants for s in sources):
                continue
            rep.add("ERROR", None, "외부 자원", f"<{el.name} {attr}=\"{val[:60]}\"> 외부 파일에 의존합니다", target=val)
    for css in [t.get_text() for t in soup.find_all("style")] + [el.get("style", "") for el in soup.find_all(style=True)]:
        for m in re.finditer(r"url\(\s*['\"]?((?:https?:)?//[^)'\"]+)|@import\s+[^;]+", css, re.I):
            rep.add("ERROR", None, "외부 자원", f"CSS 가 외부 자원을 부릅니다: {m.group(0)[:60]}", target=m.group(0))

    pack = pack_checks(soup, slides, rep)
    archs = []
    slide_kinds = []  # TASK-figslots 텍스트 나열 계산용: 'visual'·'fixed'·'text'
    for i, sec in enumerate(slides, 1):
        arch = sec.get("data-archetype", "")
        title = slide_title(sec)
        rep.slide_meta[i] = (arch or ("pack-" + pack["design"] if pack and is_pack_slide(sec) else "?"), title)
        archs.append(arch)
        if arch in FIXED_ARCHS:  # 고정 형식은 아키타입으로 확정 — 내부 시각 요소가 있어도 연속열에서 뺀다
            slide_kinds.append("fixed")
        elif arch in VISUAL_ARCHS or sec.get("data-variant") == "fig" or sec.select_one(".fig-slot, .vflow, .vpills"):
            slide_kinds.append("visual")
        else:
            slide_kinds.append("text")
        # Heuristic warning, not evidence of instructional effectiveness. Recognize
        # explanatory structure, not decorative icons or arbitrary data attributes.
        visual = sec.select_one('svg:not(.ico):not([aria-hidden="true"]), svg[role="img"][aria-label], .ed-diagram, .win, .meter-bar, .cmp, .rm, .lv, .todo, .opt, .qrow, .chk, .src-list, .atlas-map, .briefing-ledger, .casebook-file, .field-protocol, .lab-cycle, .seminar-turns, .workbook-answer, .stat-strip, .screen-cite, .vflow, .vpills')
        if arch not in {'cover', 'statement', 'quiz-ab', 'quiz-sort', 'quiz-ox', 'check', 'sources', 'closing'} and not visual:
            rep.add('WARN', i, '시각 짝', '텍스트 전용 본문입니다. 개념·비유·예시에 설명 도식, 일러스트 또는 장면 모형을 짝지으세요.')
        if not arch and not (pack and is_pack_slide(sec)):
            rep.add("INFO", i, "아키타입", "data-archetype 없음 — 엔진이 자동 배정합니다 (기본 statement, .chk 있으면 check)")
        elif arch and arch not in ARCHETYPES:
            rep.add("ERROR", i, "아키타입", f"알 수 없는 data-archetype=\"{arch}\"")
        if sec.find("script"):
            rep.add("ERROR", i, "스크립트", "슬라이드 안에 <script> 가 있습니다")
        # 구성도·업무 흐름(data-c="stack"): 읽기 계약(role/aria-label)과 데이터 형식 검사.
        # 형태 오류는 ERROR, 칸 넘침은 WARN — 규칙의 주인은 scripts/stack_schema.py 다.
        for el in sec.select('[data-c="stack"]'):
            if el.get("role") != "img" or not el.get("aria-label"):
                rep.add("ERROR", i, "구성도", "data-c=\"stack\" 에 role=\"img\" 와 aria-label(도식 요지)이 필요합니다", target=".stack-fig")
            raw = el.get("data-d", "")
            try:
                from stack_schema import check_data_d, StackSchemaError
                for w in check_data_d(raw):
                    rep.add("WARN", i, "구성도", w, target=el.get("data-variant") or ".stack-fig")
            except StackSchemaError as exc:
                rep.add("ERROR", i, "구성도", str(exc), target=".stack-fig")
        # 그림 자리(figure.fig-slot): 배치가 준 빈 그림 칸 — 저작자가 diagrams.md 문법의 svg.dg 로 채운다.
        # 빈 슬롯·«…» 자리표시 잔류·svg 읽기 계약 위반은 텍스트 자리(«…»)와 같은 ERROR 취급.
        for fig in sec.select("figure.fig-slot"):
            svg = fig.find("svg")
            if svg is None or not svg.find(True):
                rep.add("ERROR", i, "그림 자리",
                        "fig-slot 이 비었습니다 — diagrams.md 문법의 svg.dg 로 채우세요", target=".fig-slot")
                continue
            if svg.get("role") != "img" or not svg.get("aria-label"):
                rep.add("ERROR", i, "그림 자리",
                        "fig-slot 안 svg.dg 에 role=\"img\"·aria-label(도식 요지)이 필요합니다",
                        target=".fig-slot svg")
            if "«" in fig.get_text() and not allow_placeholders:
                rep.add("ERROR", i, "그림 자리",
                        "fig-slot 에 «…» 자리표시가 남았습니다 — 주제에 맞는 도식으로 다시 그리세요",
                        target=".fig-slot")
        # TASK-cover-rework: 표지 그림 자리(.cover-art) — 주제 비특정 장식 자리. 자리표시 그림(«…»)이
        # 남으면 텍스트 자리와 같은 ERROR 취급(갤러리 검사는 --allow-placeholders 에서만 묵음).
        if arch == "cover":
            for art in sec.select(".cover-art"):
                if "«" in art.get_text() and not allow_placeholders:
                    rep.add("ERROR", i, "표지 그림",
                            "cover-art 에 자리표시 그림이 남았습니다 — «그림: …» 안내를 지우고 주제에 맞게 다시 그리세요",
                            target=".cover-art")
        # TASK-quadrant-flash 최소 계약: 사분면은 축 라벨 2개(.qax-x·.qax-y), 플래시카드는 카드 3장 이상
        # + 카드마다 앞면 .fc-front·뒷면 .fc-back 짝. 부족하면 배치 의도가 깨진 것 — WARN(검사 남발 금지).
        if arch == "quadrant" and len(sec.select(".qax")) < 2:
            rep.add("WARN", i, "사분면", "quadrant 장에 축 라벨(.qax)이 2개 미만입니다 — 두 축의 기준을 적으세요",
                    target=".quad")
        if arch == "flashcards":
            fcs = sec.select(".fc")
            if len(fcs) < 3:
                rep.add("WARN", i, "플래시카드", "flashcards 장에 카드(.fc)가 3장 미만입니다 — 반복 학습 묶음을 채우세요",
                        target=".fcards")
            if any(not c.select_one(".fc-front") or not c.select_one(".fc-back") for c in fcs):
                rep.add("WARN", i, "플래시카드", "앞면(.fc-front) 또는 뒷면(.fc-back)이 빠진 카드가 있습니다",
                        target=".fc")
        # 확인 문제(check): 보기를 눌러 답하는 장. 마크업 규칙은 references/layouts.md 의 check 항
        if arch == "check":
            chks = sec.select(".chk")
            if not chks:
                rep.add("ERROR", i, "확인 문제", ".chk 확인 문제 상자가 없습니다")
            for c in chks:
                if not c.select_one(".chk-q"):
                    rep.add("ERROR", i, "확인 문제", ".chk 에 질문(.chk-q)이 없습니다")
                if not c.select_one(".chk-why"):
                    rep.add("ERROR", i, "확인 문제", ".chk 에 해설(.chk-why)이 없습니다")
                opts = c.select(".chk-o")
                if len(opts) < 2:
                    rep.add("ERROR", i, "확인 문제", f"보기(.chk-o)가 {len(opts)}개뿐입니다 (2개 이상)")
                elif len(opts) not in (2, 4):
                    rep.add("WARN", i, "확인 문제", f"보기가 {len(opts)}개입니다 (2줄 배치라 2 또는 4개가 원칙)")
                n_ok = len([o for o in opts if o.has_attr("data-ok")])
                if n_ok != 1:
                    rep.add("ERROR", i, "확인 문제", f"정답 표시(data-ok)가 {n_ok}개입니다 (정확히 1개)")
        notes = sec.select_one("aside.notes")
        nlen = len(text_of(notes))
        # 기준은 references/composition.md 6절(노트 110~450자)과 expression.md 2절(제목 30자)
        if allow_placeholders and notes and "«" in text_of(notes):
            pass  # 갤러리 검사: 노트가 아직 «발표자 노트 …» 자리표시라 길이를 재지 않는다
        elif not notes or nlen < 60:
            rep.add("ERROR", i, "발표자 노트", f"노트가 없거나 너무 짧습니다 ({nlen}자 < 60자)")
        elif nlen < 110:
            rep.add("WARN", i, "발표자 노트", f"노트가 짧습니다 ({nlen}자 < 110자). 진행 지시·보충 설명을 더하세요")
        elif nlen > 450:
            rep.add("WARN", i, "발표자 노트", f"노트가 깁니다 ({nlen}자 > 450자). 발표 중 읽기 어렵습니다")
        if len(title) > 30:
            rep.add("WARN", i, "제목", f"제목이 깁니다 ({len(title)}자 > 30자)")
        steps = []
        for attr in STEP_ATTRS:
            for el in sec.find_all(attrs={attr: True}):
                v = el.get(attr, "")
                if not re.fullmatch(r"\d+", v):
                    rep.add("ERROR", i, "단계 값", f"{attr}=\"{v}\" 는 0 이상의 정수여야 합니다", target=f"{attr}={v}")
                else:
                    steps.append(int(v))
        max_step = max(steps) if steps else 0
        if max_step > 7:
            rep.add("WARN", i, "단계", f"단계가 {max_step}개입니다 (7개 이하)")
        callout = sec.select_one(".callout[data-step]")
        if callout and re.fullmatch(r"\d+", callout["data-step"]) and int(callout["data-step"]) < max_step:
            rep.add("WARN", i, "단계", "정리 문장(.callout)은 마지막 단계에 보여 주는 것이 원칙입니다")
        visible = []
        for t in sec.find_all(string=True):
            if isinstance(t, Comment) or t.find_parent(["aside", "svg", "script", "style"]) or t.find_parent(class_="win"):
                continue
            if t.strip():
                visible.append(t.strip())
        vlen = len(re.sub(r"\s+", "", "".join(visible)))
        if vlen > 320 and arch != "sources":
            rep.add("WARN", i, "분량", f"화면 글자가 많습니다 ({vlen}자 > 320자). 한 장 한 메시지로 나누세요")
        # 말투: 한 장의 화면 글에 AI 티 표현이 SLOP_MIN 번 이상 반복되면 잡는다(WARN).
        # 노트는 번역투 피동(되어지·에 의해)만 합산한다 — copyedit.md 4절과 같은 기준.
        vtext = " ".join(visible)
        ntext = text_of(notes)
        for pat, in_notes in SLOP_PATTERNS:
            cnt = vtext.count(pat) + (ntext.count(pat) if in_notes else 0)
            if cnt >= SLOP_MIN:
                rep.add("WARN", i, "말투",
                        f"'{pat}' 표현이 이 장에 {cnt}번 나옵니다 — copyedit.md 의 말투 교정 절차를 거치세요",
                        target=pat)
        for lst in sec.find_all(["ul", "ol"]):
            if lst.find_parent("aside") or "src-list" in (lst.get("class") or []):
                continue
            n = len(lst.find_all("li", recursive=False))
            if n > 6:
                rep.add("WARN", i, "목록", f"목록 항목이 {n}개입니다 (6개 이하)")
        ncards = len(sec.select(CARD_SEL))
        if ncards > 8:
            rep.add("WARN", i, "카드", f"카드·칸이 {ncards}개입니다 (8개 이하)")
        # 카드·칸 가로줄: 같은 부모 아래 3개 이상이 가로로 늘어서면 텍스트 상자 나열로 읽힌다.
        # 개념의 관계는 aria-label 을 단 도식(svg)으로 보여 주는 것이 원칙이다.
        # 세로 쌓기(.col·stack 등)와 면제 아키타입(기존 '시각 짝' 면제 + checklist·agenda)은 잡지 않는다.
        if not arch.startswith("quiz-") and arch not in CARD_ROW_EXEMPT:
            rows = {}
            for el in sec.select(CARD_SEL):
                rows.setdefault(el.parent, []).append(el)
            if any(len(items) >= 3 and is_card_row(parent) for parent, items in rows.items()):
                if not sec.select_one('svg[aria-label]:not(.ico):not([aria-hidden="true"])'):
                    rep.add("WARN", i, "카드 나열",
                            "카드·칸이 가로줄로만 나열됐습니다 — 개념의 관계는 aria-label 을 단 도식(svg)으로 보여 주세요")
        for f in sec.select(".fact"):
            if not f.get("data-src"):
                rep.add("WARN", i, "사실 칩", "출처 id(data-src)가 없는 .fact 칩이 있습니다", target=text_of(f)[:30])
        # 숫자 증거 띠(P1-1): 지표마다 data-src 사실 id 필수·3~6개·catalog 예산. 정본 예산은 stat_budgets().
        budgets = stat_budgets()
        for band in sec.select(".stat-strip"):
            stats = band.select(".stat")
            if not 3 <= len(stats) <= 6:
                rep.add("ERROR", i, "증거 띠", f"지표(.stat)가 {len(stats)}개입니다 (3~6개)")
            for st in stats:
                sid = (st.get("data-src") or "").strip()
                if not sid:
                    rep.add("ERROR", i, "증거 띠", "지표에 data-src(사실 id)가 없습니다", target=text_of(st)[:24])
                elif not re.fullmatch(r"F\d{2,3}", sid.strip("«»")):
                    rep.add("ERROR", i, "증거 띠", f'data-src="{sid[:20]}" 는 Fxx 사실 id 형식이 아닙니다 (research.md ## F01 블록)', target=sid[:20])
                num, lab = st.select_one(f".{STAT_NUM_CLASS}"), st.select_one(".stat-label")
                if num is None or lab is None:
                    rep.add("ERROR", i, "증거 띠", "지표에 .stat-num[data-count] 큰 숫자와 .stat-label 라벨이 모두 필요합니다", target=text_of(st)[:24])
                    continue
                if len(text_of(num)) > budgets[0]:
                    rep.add("WARN", i, "증거 띠", f"숫자가 깁니다 ({len(text_of(num))}자 > {budgets[0]}자). catalog content_budget stat_number 참고", target=text_of(num)[:20])
                if len(text_of(lab)) > budgets[1]:
                    rep.add("WARN", i, "증거 띠", f"라벨이 깁니다 ({len(text_of(lab))}자 > {budgets[1]}자). catalog content_budget stat_label 참고", target=text_of(lab)[:20])
        # 실물 화면 인용(P1-2): .screen-cite 그림은 사용자가 제공한 이미지를 전제로 한다. 빈 프레임 ·
        # alt 요지 없음 · 캡션 3요소 누땍 · data-src 없음 · data: 아님 = ERROR, 1장 700KB 초과 = WARN(권장).
        cite_img, _deck_raster = cite_budgets()
        for fig in sec.select(".screen-cite"):
            img = fig.select_one("img")
            if img is None:
                rep.add("ERROR", i, "실물 화면", "이미지가 없는 빈 프레임입니다 — 사용자가 제공한 화면 이미지가 없으면 이 조각을 쓰지 않습니다",
                        target=text_of(fig.select_one(".sc-src") or fig)[:24])
            else:
                alt = (img.get("alt") or "").strip()
                if not alt or ("«" in alt and not allow_placeholders):
                    rep.add("ERROR", i, "실물 화면", "이미지 alt 가 비었거나 자리표시입니다 — 화면이 무엇을 보여 주는지 요지를 한 줄로 씁니다", target=alt[:24])
                src = (img.get("src") or "").strip()
                if src.startswith("data:image/"):
                    size = data_uri_bytes(DATA_IMG.match(src).group(1)) if DATA_IMG.match(src) else None
                    if size is not None and size > cite_img:
                        rep.add("WARN", i, "실물 화면", f"이미지가 큽니다 ({size // 1024}KB > {cite_img // 1024}KB 권장). 700KB 이하로 다시 저장하세요", target=alt[:20])
                elif "«" in src and allow_placeholders:
                    pass  # 갤러리 검사: 조각 원문의 «사용자가 제공한 화면 이미지…» 자리표시
                elif not src or "«" in src:
                    rep.add("ERROR", i, "실물 화면", "img src 가 비었거나 자리표시입니다 — 사용자가 제공한 화면 이미지를 base64 data: URI 로 넣습니다")
                else:
                    rep.add("ERROR", i, "실물 화면", "이미지는 base64 data: URI 로 덱 안에 넣어야 합니다 (외부·파일 의존 금지)", target=src[:40])
            cap_where = {(".sc-src", "출처(도메인·문서명)"), (".sc-date", "조회일"), (".sc-gist", "「이 화면이 증명하는 것」 요지")}
            for cls, what in cap_where:
                el = fig.select_one(cls)
                if el is None or not text_of(el):
                    rep.add("ERROR", i, "실물 화면", f"캡션 3요소 중 {what}({cls})가 없습니다")
            src_el = fig.select_one(".sc-src")
            sid = (src_el.get("data-src") or "").strip() if src_el is not None else ""
            if not sid:
                rep.add("ERROR", i, "실물 화면", "출처 캡션(.sc-src)에 data-src(사실 id)가 없습니다 (research.md ## F01 블록)")
            elif not re.fullmatch(r"F\d{2,3}", sid.strip("«»")):
                rep.add("ERROR", i, "실물 화면", f'data-src="{sid[:20]}" 는 Fxx 사실 id 형식이 아닙니다 (research.md ## F01 블록)', target=sid[:20])
        # SVG 차트(TASK-tools G3): 수치는 사실 칩과 같은 규칙 — .chart 안에 data-src 사실 id 가
        # 하나 이상 있어야 하고, 붙은 id 는 Fxx 형식이어야 한다(증거 띠·실물 화면과 같은 안전 가드).
        for ch in sec.select(".chart"):
            sids = [(el.get("data-src") or "").strip() for el in ch.select("[data-src]")]
            if ch.get("data-src"):
                sids.insert(0, ch.get("data-src").strip())
            if not sids:
                rep.add("ERROR", i, "차트", "차트 수치에 data-src(사실 id)가 없습니다 — .chart 또는 계열 요소에 research.md Fxx id 를 단니다")
            for sid in sids:
                if not re.fullmatch(r"F\d{2,3}", sid.strip("«»")):
                    rep.add("ERROR", i, "차트", f'data-src="{sid[:20]}" 는 Fxx 사실 id 형식이 아닙니다 (research.md ## F01 블록)', target=sid[:20])
        # 화면 핀(.pin-shot): 실물 화면과 같은 규칙 — 사용자 제공 이미지(base64 data:)가 전제다.
        for fig in sec.select(".pin-shot"):
            img = fig.select_one("img")
            src = (img.get("src") or "").strip() if img else ""
            if img is None:
                rep.add("ERROR", i, "화면 핀", ".pin-shot 에 화면 이미지(img)가 없습니다 — 사용자가 제공한 화면 이미지가 없으면 이 패턴을 쓰지 않습니다")
            elif not src.startswith("data:image/"):
                rep.add("ERROR", i, "화면 핀", ".pin-shot 이미지는 base64 data: URI 여야 합니다 (외부·파일 의존 금지)", target=src[:40] or "img")
        # 모션 효과(data-fx): 모르는 이름은 ERROR, 크레파스 중복은 WARN, 장당 최종 종료 3초 상한.
        fx_end = 0.0
        for el in sec.select("[data-fx]"):
            name = (el.get("data-fx") or "").strip()
            if name not in FX_KINDS:
                rep.add("ERROR", i, "모션",
                        f'알 수 없는 data-fx="{name}" 입니다 (가능: {", ".join(sorted(FX_KINDS))})',
                        target=name or "data-fx")
                continue
            at_v = el.get("data-fx-at", "")
            at = 0.0
            if at_v != "":
                if re.fullmatch(r"\d+(?:\.\d+)?", str(at_v)):
                    at = min(2000.0, float(at_v))
                else:
                    rep.add("WARN", i, "모션", f'data-fx-at="{at_v}" 는 0~2000ms 숫자여야 합니다', target=name)
            if el.has_attr("data-crayon"):
                rep.add("WARN", i, "모션", "한 요소에 data-fx 와 data-crayon 이 함께 있습니다 (한 요소 한 효과)", target=name)
            fx_end = max(fx_end, at + FX_KINDS[name])
        if fx_end > 3000:
            rep.add("WARN", i, "모션 길이", f"data-fx 효과가 {fx_end:g}ms 까지 이어집니다 (3000ms 안에 끝내세요)")
        # 외국어 문장: 보이는 본문 텍스트에 라틴 단어가 6개 이상 연속되면 한국어 옮김을 권한다.
        # 코드 상자(pre/code/.code), 키(.kbd), 출처 칩(.fact·.sc-src), 주소창(.b-url), SVG·노트는 제외.
        for t in sec.find_all(string=True):
            if isinstance(t, Comment):
                continue
            if t.find_parent(FOREIGN_SKIP_TAGS) or t.find_parent(class_=list(FOREIGN_SKIP_CLASSES)):
                continue
            hit = FOREIGN_RUN.search(str(t))
            if hit:
                rep.add("WARN", i, "외국어 문장",
                        "외국어 문장은 한국어로 옮겨 싣고 이름·약어·코드만 원어로 둡니다",
                        target=hit.group(0)[:40])
                break

    # TASK-figslots 텍스트 나열 WARN: 고정 형식 장(cover·quiz·sources·closing·check·explore·
    # detail-sheet)을 뺀 본문 장 연속열에서 텍스트 계열만 TEXT_RUN_MIN 장 이상이면 경고.
    # 시각 계열(도식·차트·모형·채팅·구성도·fig 변형·.fig-slot)은 연속열을 끊는다.
    run = []
    for idx, kind in enumerate(slide_kinds, 1):
        if kind == "text":
            run.append(idx)
        elif kind == "visual":
            if len(run) >= TEXT_RUN_MIN:
                rep.add("WARN", run[0], "텍스트 나열",
                        f"본문 장이 텍스트 계열만 {len(run)}장 연속입니다(장 {run[0]}~{run[-1]}) — 시각 계열(도식·모형·채팅·구성도·fig 변형)을 섞으세요")
            run = []
        # fixed: 본문 장이 아니므로 연속 계산에서 뺀다(세지도 끊지도 않는다)
    if len(run) >= TEXT_RUN_MIN:
        rep.add("WARN", run[0], "텍스트 나열",
                f"본문 장이 텍스트 계열만 {len(run)}장 연속입니다(장 {run[0]}~{run[-1]}) — 시각 계열(도식·모형·채팅·구성도·fig 변형)을 섞으세요")

    # 덱 라스터 합계 예산(기존 규칙 — expression.md 6절, 지시문 P1-2 로 체커 이행): 모든 data: 이미지의
    # 디코딩 크기를 합한다. 조각 안 SVG·폰트는 해당하지 않는다(임베드 폰트는 예산과 별개).
    per_img, deck_raster = cite_budgets()
    total = sum(size for m in DATA_IMG.finditer(html_text) if (size := data_uri_bytes(m.group(1))) is not None)
    if total > deck_raster:
        rep.add("ERROR", None, "라스터 예산", f"덱 안 data: 이미지 합계가 {total // 1024}KB 입니다 (기준 {deck_raster // 1024}KB = 1.5MB). 이미지를 줄이거나 장을 나누세요")

    if (soup.select(".fact[data-src]") or soup.select(".stat-strip .stat[data-src]")
            or soup.select(".screen-cite .sc-src[data-src]")
            or soup.select(".chart[data-src], .chart [data-src]")) and not sources:
        rep.add("ERROR", None, "참고 자료", ".fact 칩·숫자 증거 띠·실물 화면 인용·차트 사실 연결이 있는데 참고 자료(sources) 슬라이드가 없습니다")
    # 덱 크기 예산(TASK-tools G6): 임베드 폰트 포함 출력 전체가 8MB 를 넘으면 정보성으로 알린다.
    size_bytes = len(html_text.encode("utf-8"))
    if size_bytes > DECK_FILE_BUDGET:
        rep.add("INFO", None, "덱 크기",
                f"출력 파일이 {size_bytes // 1024 // 1024}MB 입니다 ({DECK_FILE_BUDGET // 1024 // 1024}MB 권장 초과 — 폰트·이미지를 줄이세요)")
    # 확인 문제 복습 연결: data-key 장을 하나라도 썼으면 data-review 키가 모두 맞는지 본다(못 찾으면 다시 보기 버튼이 안 나온다)
    keys = {s.get("data-key") for s in slides if s.get("data-key")}
    if keys:
        for i, sec in enumerate(slides, 1):
            for c in sec.select('.chk[data-review]'):
                k = c.get("data-review")
                if k not in keys:
                    rep.add("WARN", i, "확인 문제", f'data-review="{k}" 에 맞는 data-key 장이 없습니다', target=k)
    # 팩은 검증된 학습 흐름을 따른다. 공통 품질 검사는 위에서 그대로 수행한다.
    if pack:
        return slides
    # legacy 줄거리(arc): deck.json arc → 조립기가 심은 meta. 지정 덱은 arc 의 opens
    # 아키타입으로 시작해야 하고, 미지정 덱은 기존 agenda 규칙을 그대로 적용한다.
    arc_m = re.search(r'<meta\s+name="edu-deck-arc"\s+content="([^"]+)"', html_text)
    arc = arc_m.group(1) if arc_m else None
    body = [a for a in archs if a != "cover"]
    if arc is not None:
        if not ARCS:
            rep.add("WARN", None, "흐름", f"arc '{arc}' 를 검사할 수 없습니다 (tone_router 미설치)")
        elif arc not in ARCS:
            rep.add("WARN", None, "흐름", f"알 수 없는 arc '{arc}' 입니다 (가능: {', '.join(ARCS)})")
        elif body and body[0] not in ARCS[arc]["opens"]:
            rep.add("WARN", None, "흐름",
                    f"arc '{arc}' 는 표지 다음이 {' · '.join(ARCS[arc]['opens'])} 여야 합니다 (지금: {body[0]})")
    elif body and body[0] != "agenda":
        rep.add("WARN", None, "흐름", "표지 다음 슬라이드가 순서(agenda)가 아닙니다")
    if archs and archs[-1] != "closing":
        rep.add("WARN", None, "흐름", "마지막 슬라이드가 마무리(closing)가 아닙니다 (참고 자료는 마무리 바로 앞)")
    if len(slides) >= 15 and not any(a.startswith("quiz-") for a in archs):
        rep.add("WARN", None, "흐름", "15장 이상인데 퀴즈(quiz-*)가 없습니다")
    run = 1
    for i in range(1, len(archs)):
        run = run + 1 if archs[i] == archs[i - 1] and archs[i] != "worked-example" else 1
        if run == 4:
            rep.add("WARN", i + 1, "흐름", f"같은 아키타입 '{archs[i]}' 이 4장 넘게 이어집니다")
    talk_checks(html_text, slides, rep)
    # 직접 설계 표지(data-variant="custom"/"custom-…") 계약 — layouts.md "표지 직접 설계 계약".
    # 카탈로그 id(orbit·split·…)에는 적용하지 않는다.
    for i, s in enumerate(slides, 1):
        v = (s.get("data-variant") or "")
        if s.get("data-archetype") != "cover" or not (v == "custom" or v.startswith("custom-")):
            continue
        if not s.select_one(".cx-title"):
            rep.add("WARN", i, "표지", "직접 설계 표지의 제목은 .cx-title 안에 둡니다 (제목 맞춤·장 전환 계약)")
        for el in s.select("[style], [fill], [stroke]"):
            for attr in ("style", "fill", "stroke"):
                val = el.get(attr) or ""
                m = re.search(r"#[0-9a-fA-F]{3,8}\b", val)
                if m:
                    rep.add("WARN", i, "표지",
                            f"직접 설계 표지는 색을 var(--…) 토큰으로 씁니다 (하드코딩 {m.group(0)})")
                    break
    return slides


def talk_config(html_text):
    """window.EDU_STUDY 에 담긴 talk 설정을 읽는다. 없거나 객체가 아니면 None."""
    m = re.search(r"window\.EDU_STUDY\s*=\s*(\{.*?\})\s*;", html_text, re.S)
    if not m:
        return None
    try:
        study = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None
    talk = study.get("talk") if isinstance(study, dict) else None
    return talk if isinstance(talk, dict) else None


def talk_checks(html_text, slides, rep):
    """발표 덱(deck.json talk)만의 정적 경고: data-sec 누락·합계 어긋남·대본 분량."""
    talk = talk_config(html_text)
    if not talk:
        return
    secs, missing = [], []
    for i, s in enumerate(slides, 1):
        v = s.get("data-sec")
        try:
            secs.append(float(v))
        except (TypeError, ValueError):
            secs.append(0.0)
            missing.append(i)
    for i in missing:
        rep.add("WARN", i, "예상 시간", "발표 덱 슬라이드에 data-sec(예상 초)가 없습니다")
    total = talk.get("total")
    if isinstance(total, (int, float)) and total > 0:
        ssum = sum(secs)
        if abs(ssum - total) > 0.1 * total:
            rep.add("WARN", None, "시간 합계",
                    f"data-sec 합계 {ssum:.0f}초가 목표 {total:.0f}초보다 {abs(ssum - total):.0f}초 어긋납니다 (허용 ±10%)")
    rate = talk.get("rate", 300) or 300
    for i, s in enumerate(slides, 1):
        if secs[i - 1] <= 0:
            continue
        n = s.select_one(".notes")
        if not n:
            continue
        t = n.get_text()
        cnt = len(re.findall(r"[가-힯]", t)) + len(re.findall(r"[A-Za-z0-9]+", t))
        allowed = secs[i - 1] * rate / 60 * 1.1
        if cnt > allowed:
            rep.add("WARN", i, "대본 분량",
                    f"노트 {cnt}음절·단어가 예정 {secs[i - 1]:.0f}초 분량(약 {allowed:.0f})을 넘습니다")


# ---------------------------------------------------------------- 색 대비 매트릭스
"""토큰 합성 전수 채점(렌더와 별개). 지시문 P0-1: 8팩 × 최소 점검 쌍을 tokens.css 만으로 계산한다."""

PACK_ORDER = ("atlas", "briefing", "casebook", "editorial", "field", "lab", "seminar", "workbook")
TOKENS_CSS = Path(__file__).resolve().parents[1] / "assets" / "css" / "tokens.css"
THEMES_CSS = Path(__file__).resolve().parents[1] / "assets" / "css" / "themes.css"
SEMANTIC_ROLES = ("ink", "paper", "light", "soft", "line", "accent", "accent-text", "accent-light",
                  "blue", "blue-text", "blue-soft", "success", "danger", "muted", "chip")
# (행 키, 전경 토큰, 배경 토큰, 기준, 라벨). 기준: 본문 4.5 / 큰 글자(≥24px 또는 ≥18.66px bold)·
# 의미 있는 그래픽·경계 3.0. muted-on-dark·accent-light-on-dark 은 rules-dark 스니펫의 실제 쓰임
# (.dark .body 32px · .dark .small 28px · .num 96px · .eyebrow 28px/700 = 모두 큰 글자)이라 3.0.
# line-boundary 는 카드·보기(.card/.opt/.qrow…) 외곽선이 배경 paper 과의 유일한 구분이라 3.0.
MATRIX_ROWS = (
    ("body-ink", "ink", "paper", 4.5, "본문"),
    ("body-soft", "soft", "paper", 4.5, "본문(보조)"),
    ("accent-text-small", "accent-text", "paper", 4.5, "작은 강조 글"),
    ("accent-text-large", "accent-text", "paper", 3.0, "큰 글자(t2 2톤 제목)"),
    ("accent-large", "accent", "paper", 3.0, "큰 글자"),
    ("blue-text-body", "blue-text", "paper", 4.5, "본문"),
    ("blue-text-on-blue-soft", "blue-text", "blue-soft", 4.5, "본문(blue-soft 면)"),
    ("muted-on-dark", "muted", "ink", 3.0, "어두운 면 큰 글자(rules-dark)"),
    ("accent-light-on-dark", "accent-light", "ink", 3.0, "어두운 면 강조(rules-dark)"),
    ("success-on-paper", "success", "paper", 4.5, "상태 글"),
    ("danger-on-paper", "danger", "paper", 4.5, "상태 글"),
    ("success-on-light", "success", "light", 4.5, "상태 글(light 면)"),
    ("danger-on-light", "danger", "light", 4.5, "상태 글(light 면)"),
    ("line-boundary", "line", "paper", 3.0, "의미 있는 경계"),
)
_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_VAR_RE = re.compile(r"^var\(\s*(--[\w-]+)\s*\)$")
_MIX_RE = re.compile(r"^color-mix\(\s*in\s+srgb\s*,\s*(.+?)\s+(\d+(?:\.\d+)?)%\s*,\s*(.+?)\s*\)$")


def hex_to_rgb(value):
    """'#202b32'·'#abc' 형식을 (r,g,b) 로. 다른 형식은 None."""
    m = _HEX_RE.match(value.strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def blend(fg, bg, a):
    """불투명 배경 위 알파 a 전경의 sRGB 합성(간단 알파 블렌딩)."""
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3))


def rel_luminance(rgb):
    """WCAG 상대 휘도. rgb 는 0~255."""
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2])


def contrast_ratio(fg, bg):
    la, lb = rel_luminance(fg), rel_luminance(bg)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def parse_color_value(value, env, _seen=None):
    """tokens.css 색 값(hex·var() 참조·color-mix)을 sRGB 단색으로 푼다. 못 풀면 None.

    [목적] 매트릭스 채점에 필요한 최소 문법만 지원한다(그라디언트·색 함수 밖은 없다고 본다).
    [입력] CSS 값 문자열과 토큰 환경(--이름 → 원본 값). _seen 은 var() 순환 방지용.
    """
    value = value.strip()
    seen = _seen or set()
    rgb = hex_to_rgb(value)
    if rgb:
        return rgb
    m = _VAR_RE.match(value)
    if m:
        name = m.group(1)
        if name in seen or name not in env:
            return None
        return parse_color_value(env[name], env, seen | {name})
    m = _MIX_RE.match(value)
    if m:
        fg = parse_color_value(m.group(1), env, seen)
        bg = parse_color_value(m.group(3), env, seen)
        if fg is None or bg is None:
            return None
        return blend(fg, bg, float(m.group(2)) / 100)
    return None


def parse_tokens(css_text):
    """tokens.css 텍스트에서 :root 선언과 .slide.pack-* 오버라이드를 원본 값 문자열로 나눈다.

    ':root,.slide{...}' 공유 블록은 color-mix 파생이라 매트릭스 쌍에 불필요하고,
    ':root{' 단독 블록만 잡는 정귀식으로 자연히 제외된다.
    """
    base, packs = {}, {p: {} for p in PACK_ORDER}
    root = re.search(r":root\{([^}]*)\}", css_text, re.S)
    if root:
        # 선언이 세미콜론 없이 블록 끝나는 경우(팩 라인의 마지막 --light 등)도 잡는다.
        base = {k: v.strip() for k, v in re.findall(r"--([\w-]+)\s*:\s*([^;]+)", root.group(1))}
    for pack, body in re.findall(r"\.slide\.pack-(\w+)\{([^}]*)\}", css_text, re.S):
        if pack in packs:
            packs[pack] = {k: v.strip() for k, v in re.findall(r"--([\w-]+)\s*:\s*([^;]+)", body)}
    return base, packs


def rgb_to_hex(rgb):
    return "#" + "".join(f"{round(max(0, min(255, v))):02x}" for v in rgb)


def parse_theme_tokens(css_text):
    """themes.css 의 [data-theme="…"] 블록을 테마 id → {역할: 값} 사전으로 나눈다."""
    themes = {}
    for tid, body in re.findall(r'\[data-theme="([\w-]+)"\]\s*\{([^}]*)\}', css_text, re.S):
        themes[tid] = {k: v.strip() for k, v in re.findall(r"--([\w-]+)\s*:\s*([^;]+)", body)}
    return themes


def build_matrix(base, packs, themes=None):
    """기본(:root) + 8팩 + legacy 테마 환경마다 MATRIX_ROWS 전 쌍을 sRGB 합성해 채점한다.

    [출력] 행 dict 목록: pack,row,fg,bg,fg_hex,bg_hex,label,need,ratio,pass.
    팩 환경은 :root 값을 덮어쓴 팩 오버라이드 4개(accent,accent-text,paper,light)만 반영하고,
    테마 환경은 [data-theme] 블록의 15역할 덮어쓰기를 반영한다(행 이름 'theme:<id>').
    """
    rows = []
    theme_ids = tuple(themes) if themes else ()
    for pack in ("base",) + PACK_ORDER + tuple(f"theme:{t}" for t in theme_ids):
        env = dict(base)
        if pack.startswith("theme:"):
            env.update(themes[pack[6:]])
        elif pack != "base":
            env.update(packs.get(pack, {}))
        for key, fg, bg, need, label in MATRIX_ROWS:
            fr = parse_color_value(env.get(fg, ""), env)
            br = parse_color_value(env.get(bg, ""), env)
            if fr is None or br is None:
                rows.append({"pack": pack, "row": key, "fg": fg, "bg": bg, "fg_hex": "?", "bg_hex": "?",
                             "label": label, "need": need, "ratio": 0.0, "pass": False})
                continue
            ratio = contrast_ratio(fr, br)
            rows.append({"pack": pack, "row": key, "fg": fg, "bg": bg,
                         "fg_hex": rgb_to_hex(fr), "bg_hex": rgb_to_hex(br),
                         "label": label, "need": need, "ratio": round(ratio, 2), "pass": ratio >= need})
    return rows


def matrix_markdown(rows):
    """매트릭스 수치표를 납품용 markdown 으로. 판정은 '통과'/'미달 N.NN:1 부족'."""
    lines = ["# 색 대비 매트릭스 — 토큰 합성 전수 채점",
             "",
             "기준: 본문 ≥4.5:1 · 큰 글자(≥24px 또는 ≥18.66px bold)·의미 있는 그래픽·경계 ≥3:1 (WCAG 1.4.3/1.4.11)",
             "",
             "base = 팩 오버라이드 없는 :root 값(구형 덱). .slide.pack-* = 8팩 오버라이드 반영 값, theme:* = legacy 테마(themes.css) 15역할 반영 값.",
             "",
             "| 팩 | 행 | 전경 | 배경 | 전경색 | 배경색 | 비율 | 기준 | 판정 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        verdict = "통과" if r["pass"] else f"미달 ({r['ratio']:.2f}:1 < {r['need']}:1)"
        lines.append(f"| {r['pack']} | {r['row']} | {r['fg']} | {r['bg']} | {r['fg_hex']} | {r['bg_hex']} "
                     f"| {r['ratio']:.2f} | {r['need']}:1 | {verdict} |")
    return "\n".join(lines) + "\n"


def contrast_matrix_main(args):
    """--contrast-matrix 진입점. 브라우저 없이 토큰만으로 매트릭스를 채점한다.

    [입력] args.tokens(기본 shared/assets/css/tokens.css), args.matrix_dir(증거 저장 폴더, 선택)
    [출력] 결과 줄 + RESULT 줄. 위반 행은 ERROR 로 보고하고 종료 코드 1(수정 의무 신호).
    """
    tokens = Path(args.tokens) if args.tokens else TOKENS_CSS
    if not tokens.is_file():
        print(f"ERROR  tokens.css 가 없습니다: {tokens}", file=sys.stderr)
        return 2
    base, packs = parse_tokens(tokens.read_text(encoding="utf-8"))
    missing = [k for k in SEMANTIC_ROLES if k not in base]
    if missing:
        print(f"ERROR  :root 에 의미 역할 토큰이 없습니다: {', '.join('--' + k for k in missing)}", file=sys.stderr)
        return 2
    themes_path = Path(getattr(args, "themes", None) or THEMES_CSS)
    themes = {}
    theme_errors = []
    if themes_path.is_file():
        themes = parse_theme_tokens(themes_path.read_text(encoding="utf-8"))
        for tid, roles in themes.items():
            short = [k for k in SEMANTIC_ROLES if k not in roles]
            if short:
                theme_errors.append(
                    f"테마 '{tid}' 에 의미 역할 토큰이 빠졌습니다: {', '.join('--' + k for k in short)}")
    for msg in theme_errors:
        print(f"ERROR  {msg}", file=sys.stderr)
    if theme_errors:
        return 1
    rows = build_matrix(base, packs, themes)
    rep = Report()
    for r in rows:
        if not r["pass"]:
            rep.add("ERROR", None, "대비 매트릭스",
                    f"{r['pack']} {r['fg']}/{r['bg']} ({r['label']}) {r['ratio']:.2f}:1 < 기준 {r['need']}:1",
                    target=f"{r['pack']}:{r['row']}")
    if args.matrix_dir:
        out = Path(args.matrix_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "matrix-table.json").write_text(
            json.dumps({"tokens": str(tokens), "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "matrix-table.md").write_text(matrix_markdown(rows), encoding="utf-8")
        rep.add("INFO", None, "대비 매트릭스", f"수치표 {len(rows)}셀 저장 → {out.resolve()}")
    for line in rep.lines():
        print(line)
    errors = rep.count("ERROR")
    print(f"RESULT: {'FAIL' if errors else 'PASS'}  errors={errors} warnings={rep.count('WARN')} "
          f"render=SKIPPED matrix={len(rows)}셀")
    return 1 if errors else 0


# ---------------------------------------------------------------- 화면 검사
RENDER_JS = r"""
([idx]) => {
  const slide = document.querySelectorAll('#stage > .slide')[idx];
  const SR = slide.getBoundingClientRect();
  const T = 2, out = [];
  const cover = !slide.matches('.pack, [data-design]') &&
    (slide.id === 'cover' || slide.dataset.archetype === 'cover');
  // 표지 면제는 '장식'에만 준다: aria-hidden 아래는 decor() 가 이미 걸러내므로 여기서는
  // 글자 노드가 전혀 없는 요소(SVG 도형·배경 패널·띠)만 면제다. 제목·배지·날짜 등 글자를
  // 담은 표지 요소는 일반 장과 같은 규칙으로 검사한다(TASK-cover-custom G1).
  const coverFree = (e) => cover && !(e.textContent || '').trim();
  const S = new Map();
  const svgBoxes = new Map();
  const st = (e) => { let c = S.get(e); if (!c) { c = getComputedStyle(e); S.set(e, c); } return c; };
  const short = (e) => (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 18);
  const desc = (e) => {
    let s = e.tagName.toLowerCase();
    const cls = (e.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).slice(0, 2);
    if (cls.length) s += '.' + cls.join('.');
    const t = short(e); if (t) s += ' “' + t + '”';
    return s;
  };
  const decor = (e) => !!e.closest('[aria-hidden="true"], .notes');
  const shown = (e) => { if (!e.getClientRects().length) return false; const v = st(e).visibility; return v !== 'hidden' && v !== 'collapse'; };
  const ownText = (e) => { for (const n of e.childNodes) if (n.nodeType === 3 && n.textContent.trim()) return true; return false; };
  const positioned = (e, stop) => { for (let x = e; x && x !== stop && x !== slide; x = x.parentElement) { const p = st(x).position; if (p === 'absolute' || p === 'fixed') return true; } return false; };
  const color = (s) => { const m = /rgba?\(([^)]+)\)/.exec(s || ''); if (!m) return null; const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(parseFloat); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const opac = (e) => { let o = 1; for (let x = e; x && x !== slide.parentElement; x = x.parentElement) o *= parseFloat(st(x).opacity); return o; };
  const isBox = (e) => {
    if (e === slide || e instanceof SVGElement) return false;
    const c = st(e); if (c.display === 'inline' || c.display === 'contents') return false;
    if (e.closest('.slide.pack') && e.matches('__PACK_CONTAINERS__')) return true;
    const bg = color(c.backgroundColor);
    if ((bg && bg[3] > 0.05) || c.backgroundImage !== 'none') return true;
    return ['Top', 'Right', 'Bottom', 'Left'].some(k => parseFloat(c['border' + k + 'Width']) > 0 && c['border' + k + 'Style'] !== 'none');
  };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const blend = (fg, bg, a) => [0, 1, 2].map(i => fg[i] * a + bg[i] * (1 - a));
  const backdrop = (e) => {
    // 글자 요소에서 위(조상)로 올라가며 첫 불투명 배경(alpha≥.99)을 배경으로 쓴다 —
    // 불투명 카드가 중간에 있으면 슬라이드의 그라데이션보다 그 카드가 배경이다(TASK-contrast-fix G1).
    // 그 사이에 배경 이미지·그라데이션이 끼어 있으면(글자가 이미지 위에 있음) 'img' 를 돌려
    // 호출부가 렌더 픽셀 샘플링으로 잰다(G2). 불투명 층이 없으면 흰 바탕 위 반투명 층만 합성한다.
    const layers = [];
    for (let x = e; x; x = x.parentElement) {
      const c = st(x);
      if (c.backgroundImage !== 'none') return 'img';
      const b = color(c.backgroundColor);
      if (b && b[3] > 0) layers.push(b);
      if (b && b[3] >= 0.99) break;
      if (x === slide) break;
    }
    let bg = [255, 255, 255];
    for (let i = layers.length - 1; i >= 0; i--) bg = blend(layers[i], bg, layers[i][3]);
    return bg;
  };
  const out_of = (r, b, t) => r.left < b.left - t || r.top < b.top - t || r.right > b.right + t || r.bottom > b.bottom + t;
  // 도식 상자 후보: svg 별로 보이는 <rect> 의 화면상자를 한 번만 계산해 두고 같은 svg 의 여러 글자가 나눠 쓴다.
  // 칠하지 않는 rect(fill·stroke 모두 없음·투명)는 눈에 보이는 상자가 아니므로 후보에서 뺀다.
  const rectsOf = (svg) => {
    let a = svgBoxes.get(svg);
    if (a) return a;
    a = [];
    for (const rc of svg.querySelectorAll('rect')) {
      if (decor(rc) || !shown(rc)) continue;
      const cc = st(rc);
      if ((cc.fill === 'none' || opac(rc) < 0.05) && (cc.stroke === 'none' || parseFloat(cc.strokeWidth) === 0)) continue;
      const q = rc.getBoundingClientRect();
      if (q.width && q.height) a.push(q);
    }
    svgBoxes.set(svg, a);
    return a;
  };

  const texts = [];
  const els = slide.querySelectorAll('*');
  for (let ei = 0; ei < els.length; ei++) {
    const e = els[ei];
    if (decor(e) || !shown(e)) continue;
    const r = e.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    const c = st(e);
    if (!coverFree(e) && out_of(r, SR, T)) out.push({sev: 'ERROR', kind: '화면 밖 넘침', target: desc(e), msg: desc(e) + ' 가 슬라이드 밖으로 나갑니다'});
    if (!coverFree(e) && e !== slide && !(e instanceof SVGElement) && /hidden|clip|auto|scroll/.test(c.overflowX + c.overflowY)
        && (e.scrollHeight > e.clientHeight + T || e.scrollWidth > e.clientWidth + T)) {
      for (const d of e.querySelectorAll('*')) {
        if (!ownText(d) || decor(d) || !shown(d)) continue;
        const dr = d.getBoundingClientRect();
        if (dr.width && out_of(dr, r, T)) { out.push({sev: 'ERROR', kind: '잘린 글자', target: desc(e), msg: desc(e) + ' 안의 ' + desc(d) + ' 가 잘립니다'}); break; }
      }
    }
    if (!ownText(e)) continue;
    const op = opac(e); if (op < 0.05) continue;
    let fs = parseFloat(c.fontSize);
    if (e instanceof SVGElement && e.getScreenCTM) { const m = e.getScreenCTM(); if (m) fs *= Math.hypot(m.c, m.d) || 1; }
    if (fs === 0) continue;
    if (fs < 18) out.push({sev: 'ERROR', kind: '글자 크기', target: desc(e), msg: desc(e) + ' ' + fs.toFixed(1) + 'px (18px 미만)'});
    else if (fs < 20) out.push({sev: 'WARN', kind: '글자 크기', target: desc(e), msg: desc(e) + ' ' + fs.toFixed(1) + 'px (20px 미만)'});
    const pos = positioned(e, null);
    if (!coverFree(e) && !pos) {
      let box = null; for (let x = e.parentElement; x && x !== slide; x = x.parentElement) { if (isBox(x)) { box = x; break; } }
      if (box && !positioned(e, box)) {
        const br = box.getBoundingClientRect();
        for (const lr of e.getClientRects()) if (lr.width && out_of(lr, br, 3)) { out.push({sev: 'ERROR', kind: '상자 밖 넘침', target: desc(e), msg: desc(e) + ' 가 ' + desc(box).split(' ')[0] + ' 상자 밖으로 흘러넘칩니다'}); break; }
      }
    }
    // 대비: 모든 단계에서 잰다(지시문 P0-1 — 슬라이드×단계 전수). 불투명도 0.6 미만(틀린 답 흐리기 등)은
    // 의도한 비활성 표시라서 뺀다(WCAG 1.4.3 비활성 구성 요소 예외). 모형 창(.win) 안은 남의 화면을 흉내 낸
    // 것이라 기준을 3.0 으로 둔다. 배경은 조상 체인의 알파·color-mix 를 브라우저 계산값으로 합성해 최종 단색으로 잰다.
    if (op >= 0.6 && !(e instanceof SVGElement)) {
      const fg = color(c.color), bg = backdrop(e);
      const need = (fs >= 24 || (fs >= 18.66 && parseInt(c.fontWeight) >= 700) || e.closest('.win')) ? 3.0 : 4.5;
      if (fg && bg === 'img') {
        // 글자가 배경 이미지·그라데이션 위에 있다 — 여기서는 못 재므로 영역·색을 넘기고
        // 호출부(Python)가 글자를 숨긴 채 그린 픽셀을 샘플링해 최악 대비를 잰다(TASK-contrast-fix G2).
        out.push({sev: 'SAMPLE', kind: '대비', target: desc(e), i: ei,
                  rect: {x: r.left + (window.scrollX || 0), y: r.top + (window.scrollY || 0),
                         w: r.width, h: r.height},
                  fg: fg, op: op, need: need, msg: ''});
      } else if (fg && bg) {
        const f = blend(fg, bg, fg[3] * op);
        const L1 = lum(f), L2 = lum(bg), ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
        if (ratio < need) out.push({sev: 'ERROR', kind: '대비', target: desc(e), msg: desc(e) + ' 대비 ' + ratio.toFixed(2) + ' (기준 ' + need + ')'});
      }
    }
    if (!coverFree(e) && e instanceof SVGTextElement && e.ownerSVGElement && !e.closest('defs, symbol, marker')) {
      const svg = e.ownerSVGElement;
      const sr = svg.getBoundingClientRect();
      if (out_of(r, sr, 4)) out.push({sev: 'ERROR', kind: '도식 밖 글자', target: desc(e), msg: desc(e) + ' 가 도식(svg) 영역 밖으로 나갑니다'});
      // SVG 글자 넘침: 글자 앵커점(text-anchor 위치, 세로는 중앙)을 담는 같은 svg 안의 가장 작은 <rect> 를
      // 상자로 보고, 글자 상자가 그 상자보다 2px 넘게 나가면 ERROR 다. 앵커점이 어떤 rect 에도 닿지 않으면
      // 글자가 상자에 담긴 게 아니라 나란히 그린 것이므로 검사하지 않는다.
      if (r.width && r.height) {
        const ta = st(e).textAnchor;
        const ax = ta === 'middle' ? (r.left + r.right) / 2 : ta === 'end' ? r.right : r.left, ay = (r.top + r.bottom) / 2;
        let box = null, area = Infinity;
        for (const q of rectsOf(svg)) {
          if (q.width * q.height >= area) continue;
          if (ax < q.left || ax > q.right || ay < q.top || ay > q.bottom) continue;
          box = q; area = q.width * q.height;
        }
        if (box && out_of(r, box, T)) out.push({sev: 'ERROR', kind: 'SVG 글자 넘침', target: desc(e), msg: desc(e) + ' 가 상자(rect) 밖으로 나갑니다'});
      }
    }
    if (!coverFree(e) && !pos) texts.push({e, rects: [...e.getClientRects()].filter(q => q.width > 1 && q.height > 1)});
  }
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const a = texts[i], b = texts[j];
    if (a.e.contains(b.e) || b.e.contains(a.e)) continue;
    let hit = false;
    for (const p of a.rects) { for (const q of b.rects) {
      const w = Math.min(p.right, q.right) - Math.max(p.left, q.left), h = Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top);
      if (w > 0 && h > 0 && w * h > 0.3 * Math.min(p.width * p.height, q.width * q.height)) { hit = true; break; }
    } if (hit) break; }
    if (hit) out.push({sev: 'WARN', kind: '글자 겹침', target: desc(a.e) + '|' + desc(b.e), msg: desc(a.e) + ' 와 ' + desc(b.e) + ' 가 겹칩니다'});
  }
  // 구성도(data-c="stack"): 도식 높이 상한 600px — 자연 높이가 넘으면 max-height 로 줄여 그린다(WARN).
  for (const host of slide.querySelectorAll('[data-c="stack"]')) {
    const sv = host.querySelector('svg');
    if (!sv || !sv.viewBox || !sv.viewBox.baseVal) continue;
    const r = sv.getBoundingClientRect(), vb = sv.viewBox.baseVal;
    if (r.height > 600 + T) out.push({sev: 'ERROR', kind: '도식 높이', target: '.stack-fig', msg: '구성도 도식이 600px 를 넘게 그려졌습니다'});
    else if (vb.height && vb.width && r.width && vb.height * (r.width / vb.width) > 600 + T)
      out.push({sev: 'WARN', kind: '도식 높이', target: '.stack-fig', msg: '구성도 도식 자연 높이가 600px 를 넘어 줄여 그립니다'});
  }
  return out;
}
""".replace('__PACK_CONTAINERS__', PACK_CONTAINER_SEL)

# 참고 덱처럼 deckInfo 가 없는 구형 엔진을 비교 검사할 때만 쓰는 대용 함수
DECKINFO_POLYFILL = r"""
() => {
  if (typeof window.deckGo !== 'function') return 'none';
  if (typeof window.deckInfo === 'function') return 'native';
  window.deckInfo = function () {
    var s = [].slice.call(document.querySelectorAll('#stage > .slide'));
    var cur = s.findIndex(function (x) { return x.classList.contains('active'); }), m = 0;
    s[Math.max(cur, 0)].querySelectorAll('[data-step],[data-add],[data-only],[data-lit],[data-until]').forEach(function (e) {
      ['step', 'add', 'only', 'lit', 'until'].forEach(function (a) { if (e.dataset[a] !== undefined) m = Math.max(m, +e.dataset[a]); });
    });
    return {slide: cur, step: null, maxStep: m, count: s.length};
  };
  return 'polyfill';
}
"""

QUIET_CSS = ("*,*::before,*::after{animation-duration:0s!important;animation-delay:0s!important;"
             "transition-duration:0s!important;transition-delay:0s!important}"
             "#help,#counter,#dots,#progress{display:none!important}")

# 제목 줄 수 측정: data-fit 축소 후에도 목표 줄 수를 넘는지, 발표 덱 제목이 1줄을 넘는지.
TITLE_JS = r"""
([idx]) => {
  const s = document.querySelectorAll('#stage > .slide')[idx];
  if (!s || document.documentElement.classList.contains('ed-compact')) return [];
  const t = s.querySelector('.title');
  if (!t) return [];
  const cs = getComputedStyle(t);
  const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.15;
  const lines = Math.round(t.offsetHeight / Math.max(1, lh));
  const fit = t.hasAttribute('data-fit');
  const need = fit ? (parseInt(t.getAttribute('data-fit'), 10) || 1) : 1;
  return [{fit: fit, lines: lines, need: need,
           text: (t.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40)}];
}
"""


def parse_slide_filter(spec, total):
    """'3,5-7' 형식을 1부터 시작하는 슬라이드 번호 집합으로 바꾼다. 비어 있으면 전체."""
    if not spec:
        return set(range(1, total + 1))
    chosen = set()
    for part in spec.split(","):
        part = part.strip()
        if re.fullmatch(r"\d+-\d+", part):
            a, b = map(int, part.split("-"))
            chosen.update(range(a, b + 1))
        elif part.isdigit():
            chosen.add(int(part))
    return {n for n in chosen if 1 <= n <= total}


def launch(pw):
    """번들 Chromium 을 먼저 쓰고, 없으면 설치된 Chrome 을 쓴다(이 맥에서는 Chrome 만 동작)."""
    errors = []
    for kwargs in ({}, {"channel": "chrome"}):
        try:
            return pw.chromium.launch(**kwargs)
        except Exception as e:  # 브라우저 실행 파일 없음 등
            errors.append(str(e).splitlines()[0])
    raise RuntimeError("브라우저를 띄우지 못했습니다: " + " / ".join(errors))


_HIDE_TEXT_JS = """([si, i, on]) => {
  if (on && !document.getElementById('edu-hide-txt-css')) {
    const s = document.createElement('style'); s.id = 'edu-hide-txt-css';
    s.textContent = '.edu-hide-txt,.edu-hide-txt *,.edu-hide-txt *::before,.edu-hide-txt *::after{color:transparent!important;text-shadow:none!important;-webkit-text-stroke-color:transparent!important;border-color:transparent!important;outline-color:transparent!important;box-shadow:none!important;fill:transparent!important;stroke:transparent!important}.edu-hide-txt::before,.edu-hide-txt::after,.edu-hide-txt .edu-hide-empty{visibility:hidden!important}';
    document.head.appendChild(s);
  }
  const sl = document.querySelectorAll('#stage > .slide')[si];
  const e = sl && sl.querySelectorAll('*')[i];
  if (!e) return;
  e.classList.toggle('edu-hide-txt', on);
  if (on) e.querySelectorAll('*').forEach(k => { if (!(k.textContent || '').trim()) k.classList.add('edu-hide-empty'); });
  else e.querySelectorAll('.edu-hide-empty').forEach(k => k.classList.remove('edu-hide-empty'));
}"""


def _lum(c):
    """RENDER_JS lum 과 같은 WCAG 상대휘도(0~1). c = (r, g, b) 0~255."""
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def measure_img_contrast(page, slide_idx, item):
    """배경 이미지·그라데이션 위 글자의 대비를 렌더 픽셀 샘플링으로 잰다(TASK-contrast-fix G2).

    [목적] backdrop() 이 'img' 를 돌려준 글자 = 글자와 가장 가까운 불투명 배경 사이에 이미지·
      그라데이션이 끼어 있는 경우. DOM 색만으로는 배경을 못 재므로, 글자를 잠시 투명하게
      숨긴 상태로 요소 영역을 찍어 픽셀을 잰다.
    [입력] page(해당 장·단계가 그려진 Playwright 페이지), 슬라이드 인덱스, SAMPLE 항목
      (i: 슬라이드 안 요소 순번, rect: 문서 좌표, fg:[r,g,b,a], op: 불투명도, need: 기준)
    [출력] 최악 대비 비율(float) — 글자색과 휘도 차가 가장 작은 샘플 픽셀을 배경으로 한 값.
      Pillow 부재·스크린샷 실패·화면 밖 영역이면 None(호출부가 건너뜀 수를 세어 INFO 로 남긴다).
    [주의] 숨김은 .edu-hide-txt 클래스 토글로 하며, 글자뿐 아니라 요소 자신의 테두리·윤곽선·
      그림자·의사요소(::before/::after)·무글자 자손(아이콘·캐럿 등)도 함께 숨긴다 — 이들은
      글자 뒤 배경이 아니라 전경 장식이라 픽셀 샘플에 섞이면 오탐이 난다. 측정 뒤 반드시 되돌린다.
      샘플은 요소당 최대 24×24 격자다.
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    r = item["rect"]
    x, y = max(0.0, float(r["x"])), max(0.0, float(r["y"]))
    w, h = min(float(r["w"]), 1920.0 - x), min(float(r["h"]), 1080.0 - y)
    if w < 1 or h < 1:
        return None
    try:
        page.evaluate(_HIDE_TEXT_JS, [slide_idx, item["i"], True])
        png = page.screenshot(clip={"x": x, "y": y, "width": w, "height": h})
    except Exception:
        return None
    finally:
        try:
            page.evaluate(_HIDE_TEXT_JS, [slide_idx, item["i"], False])
        except Exception:
            pass
    try:
        img = Image.open(io.BytesIO(png)).convert("RGB")
    except Exception:
        return None
    iw, ih = img.size
    gx, gy = min(24, iw), min(24, ih)
    fg = item["fg"]
    fa = fg[3] * float(item.get("op", 1))
    worst = None
    for iy in range(gy):
        for ix in range(gx):
            px = img.getpixel((ix * (iw - 1) // max(gx - 1, 1), iy * (ih - 1) // max(gy - 1, 1)))
            f = (fg[0] * fa + px[0] * (1 - fa), fg[1] * fa + px[1] * (1 - fa), fg[2] * fa + px[2] * (1 - fa))
            l1, l2 = _lum(f), _lum(px)
            ratio = (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)
            if worst is None or ratio < worst:
                worst = ratio
    return worst


def render_checks(path, rep, slide_filter, sheets_dir, shots_dir):
    """
    [목적] 실제 브라우저에서 모든 슬라이드·단계 상태를 그려 보고 화면 결함을 잰다.
    [입력] HTML 경로, Report, 검사할 슬라이드 번호 문자열, 축소판 모음/원본 PNG 출력 폴더(없으면 None)
    [출력] True(실행함) / False(Playwright 나 브라우저가 없어 못 함). 결함은 rep 에 쌓인다.
    [연결] 엔진의 window.deckGo(i, step) 와 window.deckInfo() 를 쓴다(assets/shell.html).
    [주의] 1차 실행(움직임 켬)으로 스크립트 오류를 모으고 eduMotion.sigLog 에서 장별 발화 시그니처를
      수집해 무성 장(발화 0건)을 WARN 로 보고한다. 2차 실행(움직임 줄임 + 전환 0초)으로 측정한다.
      전환 효과가 남아 있으면 상자 위치가 중간값으로 잡혀 넘침을 놓치거나 잘못 보고한다.
      대비 검사(4.5/3.0)는 2차 패스의 모든 단계에서 잰다(2026-11-03 지시문 P0-1: 마지막 단계 한정 폐지·ERROR 승격).
    [수정시 영향] 뷰포트를 1920×1080 이 아닌 값으로 바꾸면 무대가 축소되어 px 기준이 모두 틀어진다.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        rep.add("WARN", None, "화면 검사", "playwright 가 없어 화면 검사를 못 했습니다 (설치 안내: pip install playwright)")
        return False
    url = Path(path).resolve().as_uri()
    stage = "start"  # 브라우저를 띄우기 전 실패 = 환경 문제(NOT_RUN), 띄운 뒤 실패 = 검사기 오류(ERROR)
    try:
        with sync_playwright() as pw:
            browser = launch(pw)
            stage = "measure"
            errors = []
            # 1차: 움직임을 켠 상태로 열어 스크립트 오류를 모은다
            ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = ctx.new_page()
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url)
            page.wait_for_timeout(600)
            engine = page.evaluate(DECKINFO_POLYFILL)
            if engine == "none":
                rep.add("ERROR", None, "엔진", "window.deckGo 가 없습니다 (assets/shell.html 로 조립했는지 확인)")
                browser.close()
                return True
            if engine == "polyfill":
                rep.add("INFO", None, "엔진", "deckInfo 가 없는 구형 엔진이라 대용 함수로 검사했습니다")
            total = page.evaluate("window.deckInfo().count")
            # P0-2 무성 장 감사: 1차 패스(모션 켬)에서 장마다 eduMotion.sigLog 를 읽어
            # 발화 시그니처를 모은다. 발화 0건 장은 아래에서 WARN 으로 보고한다.
            auditable = page.evaluate("!!(window.eduMotion && Array.isArray(window.eduMotion.sigLog))")
            fired = {}
            for i in range(total):
                page.evaluate(f"window.deckGo({i})")
                if auditable:
                    for e in page.evaluate("() => window.eduMotion.sigLog"):
                        fired.setdefault(e["slide"], set()).add(e["sig"])
            page.wait_for_timeout(300)
            ctx.close()
            for e in dict.fromkeys(errors):
                rep.add("ERROR", None, "스크립트 오류", e[:200])
            if auditable:
                for n in range(1, total + 1):
                    sigs = sorted(fired.get(n - 1, ()))
                    rep.slide_sigs[n] = sigs
                    if not sigs:
                        rep.add("WARN", n, "무성 장", "발화한 모션 시그니처가 없습니다 — 레지스트리 배정 또는 보이는 발화 대상을 확인하세요")
                spoken = sum(1 for v in rep.slide_sigs.values() if v)
                rep.add("INFO", None, "무성 장", f"{total}장 중 {spoken}장이 시그니처를 발화했습니다")
            else:
                rep.add("INFO", None, "무성 장", "eduMotion.sigLog 가 없어 무성 장 감사를 건너뜁니다 (구형 셸)")
            # 2차: 측정
            ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, reduced_motion="reduce")
            page = ctx.new_page()
            page.on("pageerror", lambda e: rep.add("ERROR", None, "스크립트 오류", str(e)[:200]))
            page.goto(url)
            page.add_style_tag(content=QUIET_CSS)
            page.evaluate(DECKINFO_POLYFILL)
            chosen = parse_slide_filter(slide_filter, total)
            talk = page.evaluate("((window.EDU_STUDY||{}).talk)||null")
            img_skipped = 0
            for n in sorted(chosen):
                info = page.evaluate(f"(window.deckGo({n - 1}, 0), window.deckInfo())")
                # 단계 값이 정수가 아니면 엔진이 NaN·실수를 돌려준다. 정적 검사가 이미 ERROR 로 알렸으니 0단계만 잰다
                top = info.get("maxStep")
                top = int(top) if isinstance(top, (int, float)) and top == top else 0
                info["maxStep"] = top
                for s in range(top + 1):
                    page.evaluate(f"window.deckGo({n - 1}, {s})")
                    for f in page.evaluate(RENDER_JS, [n - 1]):
                        if f["sev"] == "SAMPLE":
                            # 배경 이미지·그라데이션 위 글자 — 같은 단계가 그려진 상태에서 픽셀 샘플링
                            ratio = measure_img_contrast(page, n - 1, f)
                            if ratio is None:
                                img_skipped += 1
                            elif ratio < f["need"]:
                                rep.add("ERROR", n, "대비",
                                        f"{f['target']} 대비 {ratio:.2f} (기준 {f['need']}, 이미지 배경 픽셀 샘플)",
                                        target=f["target"], step=s)
                            continue
                        rep.add(f["sev"], n, f["kind"], f["msg"], target=f["target"], step=s)
                    if s == 0:
                        for t in page.evaluate(TITLE_JS, [n - 1]):
                            if t["fit"] and t["lines"] > t["need"]:
                                rep.add("WARN", n, "제목 줄 수",
                                        f"data-fit 제목이 {t['need']}줄로 줄지 않습니다 (측정 {t['lines']}줄, 최대 20% 축소 한도)",
                                        target=t["text"])
                            elif talk and not t["fit"] and t["lines"] > 1:
                                rep.add("WARN", n, "제목 줄 수",
                                        f"발표 덱 제목이 {t['lines']}줄입니다 (1줄 원칙). data-fit 을 검토하세요",
                                        target=t["text"])
            if img_skipped:
                rep.add("INFO", None, "대비", f"배경 이미지 위 글자 {img_skipped}개는 측정하지 못함 (스크린샷 불가 환경)")
            if sheets_dir or shots_dir:
                capture(page, sorted(chosen), rep, sheets_dir, shots_dir)
            browser.close()
    except Exception as e:  # Playwright 드라이버 고장, 브라우저 충돌, 검사 스크립트 오류 등
        if stage == "start":
            rep.add("WARN", None, "화면 검사", f"브라우저를 시작하지 못했습니다: {str(e).splitlines()[0][:160]}")
            return False
        rep.add("ERROR", None, "검사기 오류", f"화면 검사 중 멈췄습니다(덱이 아니라 검사기 문제일 수 있음): {str(e).splitlines()[0][:160]}")
    return True


def capture(page, numbers, rep, sheets_dir, shots_dir):
    """
    [목적] 슬라이드를 마지막 단계 상태로 찍어 사람이 한눈에 볼 수 있는 이미지를 만든다.
    [입력] 측정용 page, 슬라이드 번호 목록, Report, 축소판 모음 폴더, 원본 크기 폴더
    [출력] sheet-01.png …(3열×4행, 칸마다 480×270) / slide-01.png …(1920×1080). 경로를 INFO 로 남긴다.
    [주의] Pillow 가 없으면 축소판 모음은 건너뛰고 원본 PNG 만 만든다.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        Image = None
        if sheets_dir:
            rep.add("WARN", None, "축소판", "Pillow 가 없어 축소판 모음을 만들지 못했습니다")
    shots = []
    for n in numbers:
        page.evaluate(f"window.deckGo({n - 1})")
        png = page.screenshot()
        if shots_dir:
            Path(shots_dir).mkdir(parents=True, exist_ok=True)
            p = Path(shots_dir) / f"slide-{n:02d}.png"
            p.write_bytes(png)
        shots.append((n, png))
    if shots_dir:
        rep.add("INFO", None, "원본 PNG", f"{len(shots)}장 → {Path(shots_dir).resolve()}")
    if not sheets_dir or Image is None:
        return
    Path(sheets_dir).mkdir(parents=True, exist_ok=True)
    tw, th, cols, rows, pad = 480, 270, 3, 4, 12
    for k in range(0, len(shots), cols * rows):
        chunk = shots[k:k + cols * rows]
        sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + pad + 22) + pad), (40, 44, 52))
        draw = ImageDraw.Draw(sheet)
        for j, (n, png) in enumerate(chunk):
            img = Image.open(io.BytesIO(png)).convert("RGB").resize((tw, th), Image.LANCZOS)
            x = pad + (j % cols) * (tw + pad)
            y = pad + (j // cols) * (th + pad + 22)
            sheet.paste(img, (x, y + 22))
            arch = rep.slide_meta.get(n, ("?", ""))[0]
            draw.text((x, y + 4), f"#{n}  {arch}", fill=(230, 230, 230))
        p = Path(sheets_dir) / f"sheet-{k // (cols * rows) + 1:02d}.png"
        sheet.save(p)
        rep.add("INFO", None, "축소판", str(p.resolve()), target=str(p))


def main(argv=None):
    """
    [목적] 명령줄 진입점. 정적 검사 → 화면 검사 → 출력 → 종료 코드.
    [입력] argv (덱 HTML 경로와 선택 옵션)
    [출력] 표준 출력의 결과 줄, 선택적으로 JSON 파일. 종료 코드 0/1/2/3.
    [연결] SKILL.md 의 검사 단계와 완료 기준이 이 종료 코드를 쓴다.
    """
    ap = argparse.ArgumentParser(description="edu-deck-solo 덱 HTML 을 정적·화면 검사합니다.")
    ap.add_argument("deck", nargs="?", help="검사할 덱 HTML 파일 (--contrast-matrix 단독 실행일 때는 생략)")
    ap.add_argument("--sheets", metavar="DIR", help="축소판 모음 PNG(3×4) 출력 폴더")
    ap.add_argument("--shots", metavar="DIR", help="슬라이드별 1920×1080 PNG 출력 폴더")
    ap.add_argument("--slides", metavar="LIST", help="화면 검사·촬영할 슬라이드 번호 (예: 3,5-7)")
    ap.add_argument("--json", metavar="FILE", help="결과 JSON 저장 경로")
    ap.add_argument("--no-render", action="store_true", help="화면 검사를 하지 않음")
    ap.add_argument("--render-only", action="store_true", help="정적 검사를 하지 않음 (다른 형식의 덱 비교용)")
    ap.add_argument("--allow-placeholders", action="store_true", help="«…» 자리표시 허용 (갤러리 검사용)")
    ap.add_argument("--style", action="store_true",
                    help="취향 규칙(길이·개수·구성)을 INFO 요약 대신 기존 WARN 으로 상세 보고")
    ap.add_argument("--contrast-matrix", action="store_true",
                    help="덱 검사 대신 토큰 대비 매트릭스를 채점한다 (기본+8팩 × 쌍 전수, 브라우저 불필요)")
    ap.add_argument("--matrix-dir", metavar="DIR", help="매트릭스 모드에서 matrix-table.md/.json 저장 폴더")
    ap.add_argument("--tokens", metavar="FILE", help="매트릭스에 쓸 tokens.css 경로 (기본: shared/assets/css/tokens.css)")
    ap.add_argument("--themes", metavar="FILE", help="매트릭스에 쓸 themes.css 경로 (기본: shared/assets/css/themes.css)")
    args = ap.parse_args(argv)
    if args.contrast_matrix:
        return contrast_matrix_main(args)
    if not args.deck:
        ap.error("덱 HTML 경로가 필요합니다 (토큰 매트릭스만 실행하려면 --contrast-matrix)")
    path = Path(args.deck)
    if not path.is_file():
        print(f"ERROR  파일이 없습니다: {path}", file=sys.stderr)
        return 2
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("ERROR  beautifulsoup4 가 필요합니다 (설치 안내: pip install beautifulsoup4)", file=sys.stderr)
        return 2
    html_text = path.read_text(encoding="utf-8")
    try:
        import lxml  # noqa: F401
        soup = BeautifulSoup(html_text, "lxml")
    except ImportError:
        soup = BeautifulSoup(html_text, "html.parser")
    rep = Report(style=args.style)
    if args.render_only:
        stage = soup.select_one("#stage")
        for i, sec in enumerate(stage.find_all("section", class_="slide", recursive=False) if stage else [], 1):
            rep.slide_meta[i] = (sec.get("data-archetype", "?"), slide_title(sec))
    else:
        static_checks(html_text, soup, rep, args.allow_placeholders)
    render = "SKIPPED"
    if not args.no_render:
        render = "RUN" if render_checks(path, rep, args.slides, args.sheets, args.shots) else "NOT_RUN"
    for line in rep.lines():
        print(line)
    errors, warnings = rep.count("ERROR"), rep.count("WARN")
    result = "FAIL" if errors else "PASS"
    infos = rep.count("INFO")
    print(f"RESULT: {result}  errors={errors} warnings={warnings} info={infos} render={render} slides={len(rep.slide_meta)}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        slides = [{"n": n, "archetype": a, "title": t, "sigs": rep.slide_sigs.get(n, []),
                   "findings": [it for it in rep.items if it["slide"] == n]} for n, (a, t) in sorted(rep.slide_meta.items())]
        Path(args.json).write_text(json.dumps({"result": result, "errors": errors, "warnings": warnings, "info": infos, "render": render,
                                               "deck": [it for it in rep.items if not it["slide"]], "slides": slides},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    if errors:
        return 1
    return 3 if render == "NOT_RUN" else 0


if __name__ == "__main__":
    sys.exit(main())
