"""참고 덱 슬라이드의 '구조'만 남기고 글자를 자리표시(«역할 ≤N자»)로 바꿔 아키타입 조각을 만드는 1회성 도구.

[파일 목적] 배치·클래스·단계 속성·SVG 도형은 그대로 두고 내용(문장·숫자·용어)은 모두 지운다.
[주요 흐름] 슬라이드 범위 추출 → 태그/글자 분리 → 조상 클래스로 글자 역할 판정 → 자리표시로 교체
  → AI 전용 아이콘을 일반 아이콘으로 교체 → data-archetype/variant 부여 → 머리 주석 → snippets/NN-id.html
[외부 연결] 입력: 참고 덱, ARCH 표(아래). 출력: edu-deck-solo/assets/snippets/*.html (자동 생성분만 덮어씀)
[수정시 주의] HAND 집합의 파일(손으로 쓴 조각)은 건드리지 않는다.
"""
import math, re, pathlib

import os, sys
_ref = os.environ.get("EDU_DECK_REF_DECK") or (sys.argv[1] if len(sys.argv) > 1 else "")
if not _ref or not pathlib.Path(_ref).is_file():
    sys.exit("원본 참고 덱 HTML 경로를 인자 또는 EDU_DECK_REF_DECK 환경변수로 지정하세요.")
REF = pathlib.Path(_ref)
OUT = pathlib.Path(__file__).resolve().parent.parent / "assets" / "snippets"
L = REF.read_text(encoding="utf-8").split("\n")

# (번호, 아키타입, [(변형, 참고 슬라이드 시작 줄)], 언제 쓰나, 단계 설명)
ARCH = [
 (1, "cover", [("", 353)], "표지. 교육 이름·제목(바로 표시)·핵심어 3~4개·부제·날짜. 가운데·궤도 아이콘을 주제에 맞게 바꾼다.", "단계 없음"),
 (2, "agenda", [("", 400)], "순서. 파트 3~5개를 '학습자 질문'으로 보여 준다. 파트 수가 다르면 rm-col 을 빼거나 더하고 .rm 의 열 수를 맞춘다.", "파트마다 1단계, 마지막 단계에 정리 문장"),
 (3, "timeline", [("", 440)], "변화의 흐름. 시점 3~4개의 사건으로 '왜 지금 배우나'를 보여 준다(큰 그림 파트 첫 장). 5개 이상이면 두 장으로 나눈다.", "시점 묶음별 1단계"),
 (4, "map", [("", 475)], "한 장 구조도. 구성 요소에 ①②③④ 번호를 붙이고, 뒤의 요소별 슬라이드가 같은 번호를 이어 쓴다.", "요소별 1단계"),
 (5, "mechanism", [("", 521)], "작동 원리. 입력 → 처리 → 결과 후보(막대)를 단계로 풀어 보여 준다.", "처리 단계별, 마지막에 1등 막대 강조(data-lit)"),
 (6, "traits-grid", [("", 548)], "성질·특징 2×2 또는 4줄. 아이콘 + 제목 + 설명 + 출처 칩.", "특징별 1단계"),
 (7, "meter", [("", 560)], "정해진 전체를 나눠 쓰는 개념(한도·구성비·예산·시간 배분). 누적 막대 + 설명 카드.", "구간을 하나씩 채움"),
 (8, "compare-2", [("flow", 582), ("diagram", 660), ("list", 808), ("choose", 902)],
  "두 가지 비교. flow=두 흐름 도식, diagram=연결 도식+설명 카드, list=카드 둘 목록, choose=언제 무엇을 고를지.", "왼쪽 → 오른쪽 → 정리"),
 (9, "compare-table", [("", 617)], "항목별 A/B 비교 표(행 3~5개).", "행마다 1단계"),
 (10, "hub", [("", 633)], "가운데 중심 + 둘레 구성 요소(고리 조각) + 오른쪽 설명 줄.", "요소별 1단계, 고리 조각이 함께 켜짐(data-lit)"),
 (11, "levels", [("", 704)], "수준·단계가 올라가는 구조(1→4, 막대가 길어짐).", "수준별 1단계"),
 (12, "tile-grid", [("cards", 729), ("features", 791), ("icons", 1157)],
  "기능·사례 묶음. cards=3×2 큰 카드, features=4×2 작은 칸, icons=아이콘 카드 3×2.", "행 단위 또는 0단계"),
 (13, "sequence", [("", 744)], "주체(사람·부서·시스템) 사이 주고받는 순서. 세로 레인 + 번호 + 반복 상자.", "주고받기 한 번에 1단계"),
 (14, "mapping", [("", 766)], "앞의 구조(①②③)를 우리 도구·제도에 대응. 왼쪽 모형 창 + 오른쪽 번호 카드.", "번호별 1단계"),
 (15, "mock-legend", [("tour", 829), ("cases", 1312)], "실제 화면 둘러보기. 화면 위 주황 번호 ↔ 오른쪽 설명.", "번호별 1단계"),
 (16, "mock-options", [("", 868)], "화면 + 선택지(모드·방식) 설명. 무엇을 고르면 어떻게 되는지.", "선택지별 1단계"),
 (17, "statement", [("orange", 947)], "파트를 여는 핵심 문장 한 줄(주황 전면). 공식 출처가 있으면 아래에 칩.", "단계 없음"),
 (18, "build-up", [("", 956)], "요소를 하나씩 더할수록 결과가 좋아지는 시연(data-add 로 덧붙인 문구 강조).", "요소 하나 = 1단계"),
 (19, "frame-form", [("form", 1011), ("rules", 921)], "요청·작업 틀(항목을 채우면 완성되는 양식) / rules=문서형 규칙과 판정.", "항목별 1단계"),
 (20, "before-after", [("mocks", 1040), ("stacks", 1090), ("fix", 1117), ("cross-check", 1365)],
  "전후 비교. mocks=같은 일의 나쁜/좋은 결과 화면, stacks=쌓는 순서·양 비교, fix=한 번에 끝 / 고쳐서 다시, cross-check=두 곳에 확인.", "전 → 후 → 정리"),
 (21, "worked-example", [("chat-points", 1184), ("chat-table", 1205), ("chat-steps", 1226), ("chat-file", 1250),
                          ("chat-diagram", 1267), ("tips", 993), ("outputs", 1071), ("schedule", 1290), ("chat-only", 1346)],
  "실제 업무 예시: 실제 요청/입력 + 결과 모형 + 포인트. chat-* 는 대화형 도구 화면이다. 대화형 도구가 아닌 주제는 22번 조각(문서·표·양식·메일·메신저 모형)을 쓴다.", "요청 → 결과 → 포인트"),
 (23, "quiz-ab", [("", 1146)], "둘 중 더 나은 것 고르기. 정답 공개는 data-lit.", "1단계: 정답 공개"),
 (24, "quiz-sort", [("", 1171)], "상황 4~5개를 두 분류로 나누기.", "줄마다 답 공개"),
 (25, "quiz-ox", [("", 1334)], "O/X 판단 + 이유 한 줄.", "줄마다 답 공개"),
 (26, "rules-dark", [("", 1394)], "꼭 지킬 3가지(어두운 배경). 위험·확인 파트의 끝.", "규칙별 1단계"),
 (27, "checklist", [("", 1405)], "이번 주 실천 3~4개. 발표 중 눌러서 체크할 수 있다.", "항목별 1단계"),
 (29, "closing", [("", 1417)], "마무리: 행동 한 문장 + 요약 알약 3개 + 질문 받기. 알약은 3파트의 틀을 다시 부른다.", "단계 없음"),
]

HAND = {"22-worked-artifact.html", "28-sources.html", "30-check.html"}  # 손으로 쓴 조각: 이 도구가 덮어쓰지 않는다
ICON_SWAP = {"i-nn": "i-bulb", "i-memory": "i-book", "i-dice": "i-question", "i-window": "i-list",
             "i-cutoff": "i-cal", "i-wand": "i-star", "i-plug": "i-link", "i-db": "i-folder"}

ROLE = [  # (클래스 또는 태그, 역할 이름) — 가까운 조상부터 찾는다
 ("notes", None), ("cx-eyebrow", "교육 이름"), ("cx-sub", "부제 한 문장"), ("cx-badge", "표지 배지(선택)"),
 ("cover-date", "날짜 YYYY. MM. DD"), ("cx-tokens", "핵심어"), ("eyebrow", "파트 표시"), ("qtag", "퀴즈 번호"),
 ("badge", "표시"), ("title", "제목: 한 문장"), ("big", "핵심 문장"), ("b", "강조 앞부분"), ("callout", "정리 문장"),
 ("fact", "출처 칩: 발행처「문서」(연도) 값"), ("pill", "요약 알약"), ("rm-h", "파트 이름"), ("rm-q", "학습자 질문"),
 ("t-year", "시점"), ("t-h", "도식 큰 글씨"), ("t-s", "도식 작은 글씨"), ("t-l", "도식 라벨"), ("t-q", "말풍선"),
 ("t-mile", "작은 표시"), ("t-seg", "고리 라벨"), ("wt", "창 제목"), ("u", "요청 말풍선"), ("at", "결과/답변"),
 ("ph", "입력칸 안내"), ("model", "선택 표시"), ("brand", "앱 이름"), ("sec", "메뉴 구분"), ("item", "메뉴 항목"),
 ("newchat", "버튼"), ("verdict", "판정 한 줄"), ("en", "영문 용어"), ("label", "라벨"), ("h3", "카드 제목"),
 ("h4", "항목 제목"), ("li", "목록 항목"), ("th", "표 머리"), ("td", "표 칸"), ("body", "설명"), ("small", "설명"),
 ("p", "문구"), ("span", "짧은 문구"),
]
KEEP = re.compile(r"^[\s\d·→←↓↑…:,.()\-–—+%/①②③④⑤⑥✓✗×?!\"“”'‘’«»]*$|^(?:[A-Z]|[OX]|0\d|\d{1,2})$")
VOID = {"br", "img", "input", "hr", "meta", "link", "source", "wbr"}
NUMBERING = {"mk", "num", "rm-num", "qn", "t-badge", "key", "ox", "t-segn", "sid", "badge", "qtag"}
PUNCT = re.compile(r"^[\s·→←↓↑…:,.()\-–—+/✓✗×?!\"“”'‘’]*$")
RENAME = {"ctx-wrap": "meter-wrap", "ctx-top": "meter-top", "ctx-use": "meter-use", "ctx-bar": "meter-bar",
          "ctx-axis": "meter-axis", "seg-c": "meter-seg", "c1": "meter-c1", "c2": "meter-c2", "c3": "meter-c3",
          "c4": "meter-c4", "c5": "meter-c5"}
SVG_SHAPES = {"path", "line", "polyline", "polygon", "circle", "rect", "ellipse"}


def rename_classes(tag, part):
    def fix(m):
        toks = m.group(1).split()
        toks = [RENAME.get(t, t) for t in toks]
        if tag in SVG_SHAPES:
            toks = ["dash-flow" if t == "flow" else t for t in toks]
        if "sb" in toks and "doc" in toks:
            toks = ["file" if t == "doc" else t for t in toks]
        return 'class="' + " ".join(toks) + '"'
    return re.sub(r'class="([^"]*)"', fix, part)


def role_for(stack):
    for name, role in ROLE:
        for tag, classes in reversed(stack):
            if name == tag or name in classes:
                return role
    return "문구"


def convert(block: str) -> str:
    out, stack = [], []
    parts = re.split(r"(<[^>]+>)", block)
    for part in parts:
        if part.startswith("<"):
            m = re.match(r"</?\s*([a-zA-Z0-9-]+)", part)
            tag = m.group(1).lower() if m else ""
            if part.startswith("</"):
                while stack and stack.pop()[0] != tag:
                    pass
            elif not (part.endswith("/>") or tag in VOID or part.startswith("<!")):
                cm = re.search(r'class="([^"]*)"', part)
                stack.append((tag, set(cm.group(1).split()) if cm else set()))
            part = rename_classes(tag, part)
            if tag == "p" and re.search(r'class="[^"]*\bfact\b', part) and "data-src" not in part:
                part = part.replace('class="', 'data-src="«F01»" class="', 1)
            part = re.sub(r'aria-label="[^"]*"', 'aria-label="«그림 설명»"', part)
            part = re.sub(r'data-text="[^"]*"', 'data-text="«표지 제목 ≤12자»"', part)
            for a, b in ICON_SWAP.items():
                part = part.replace(f'href="#{a}"', f'href="#{b}"')
            out.append(part)
            continue
        text = part.strip()
        if not text or PUNCT.match(text):
            out.append(part)
            continue
        in_numbering = any(c & NUMBERING for _, c in stack[-2:])
        if in_numbering and re.fullmatch(r"0?\d{1,2}|[A-E]|[OX]|[①-⑨]", text):
            out.append(part)
            continue
        role = role_for(stack)
        if role and re.fullmatch(r"[\d\s.,:/%~\-+]+", text):
            role = "값" if role not in ("날짜 YYYY. MM. DD", "시점") else role
        if role is None:  # 발표자 노트
            out.append("«발표자 노트 110~450자: 화면 설명 → 진행 지시(→ 누를 때마다…) → 화면에 없는 보충 사실과 출처 → 다음 장 연결»")
            continue
        lead = part[: len(part) - len(part.lstrip())]
        tail = part[len(part.rstrip()):]
        if any(tag == "svg" for tag, _ in stack):
            # 도식 글자는 줄바꿈이 안 되므로 원래 길이를 그대로 한도로 쓰고, 자리표시도 짧게 쓴다
            out.append(f"{lead}«≤{max(2, len(text))}자»{tail}")
        else:
            n = max(4, math.ceil(len(text) * 1.2))
            if role == "제목: 한 문장":
                n = min(n, 30)          # 제목은 32자를 넘기면 검사 경고. 2줄 이내 유지

            if role == "핵심 문장":
                n = min(n, 17)          # 큰 문장(96px)은 한 줄 17자 안팎, 두 줄까지
            out.append(f"{lead}«{role} ≤{n}자»{tail}")
    return "".join(out)


def slide_at(line_no: int) -> str:
    s = line_no - 1
    assert L[s].lstrip().startswith("<section"), (line_no, L[s][:60])
    e = s
    while "</section>" not in L[e]:
        e += 1
    return "\n".join(L[s:e + 1])


def tag_section(block: str, arch: str, variant: str) -> str:
    attrs = f' data-archetype="{arch}"' + (f' data-variant="{variant}"' if variant else "")
    return re.sub(r'(<section\b[^>]*?class="[^"]*")', lambda m: m.group(1) + attrs, block, count=1)


def decorate_cover(block: str) -> str:
    """표지 장식(번짐 원, 점 연결망)은 화면 읽기 프로그램이 건너뛰도록 aria-hidden 을 붙인다."""
    block = re.sub(r'<div class="cx-blob ([^"]+)"></div>', r'<div class="cx-blob \1" aria-hidden="true"></div>', block)
    # 참고 덱은 제목을 스크립트 안에 적어 data-text 속성이 없다(convert 의 data-text 치환이 맞을 곳이 없음).
    # 셸 표지 스크립트는 #cx-typed 의 data-text 만 읽으므로 자리표시를 여기서 넣는다.
    block = block.replace('<span id="cx-typed"></span>', '<span id="cx-typed" data-text="«표지 제목 ≤12자»"></span>')
    return block.replace('<canvas id="cx-net"', '<canvas id="cx-net" aria-hidden="true"')


def fix_slide(arch: str, variant: str, block: str) -> str:
    """참고 덱 그대로면 검사 기준에 걸리는 부분만 고친다(배치는 그대로)."""
    if arch == "agenda":  # 주황 번호 글자 대비 2.7 → 진한 주황
        block = re.sub(r'(<p class="rm-num" style="color:)#E8772E', r'\1#C8601F', block)
    if arch == "compare-2" and variant == "diagram":  # 도식 축소로 글자가 18px 아래로 내려가는 것을 막음
        block = block.replace('viewBox="0 0 740 330" style="height:250px"', 'viewBox="0 0 740 330" style="height:300px"')
        # 도식을 키운 만큼 글 한도를 줄인다(카드 안 세로 공간이 고정이라 두 줄 설명 + 한 줄 칩까지만)
        block = block.replace("값 ≤74자»", "값 ≤30자»").replace("값 ≤34자»", "값 ≤30자»")
        block = block.replace("«라벨 ≤46자»", "«라벨 ≤30자»").replace("«설명 ≤68자»", "«설명 ≤44자»").replace("«설명 ≤62자»", "«설명 ≤44자»")
        # 뒤에 깔린 카드 두 장은 앞 카드에 가려지는 장식이다
        block = block.replace('<g class="sk" transform=', '<g class="sk" aria-hidden="true" transform=')
    if arch == "closing":  # 두 줄 합쳐 30자 안쪽(제목 길이 검사 32자 기준)
        block = re.sub(r"«핵심 문장 ≤\d+자»", "«핵심 문장 ≤14자»", block)
    return block


written = []
for num, arch, variants, when, steps in ARCH:
    secs = []
    for variant, line in variants:
        sec = fix_slide(arch, variant, tag_section(convert(slide_at(line)), arch, variant))
        secs.append(decorate_cover(sec) if arch == "cover" else sec)
    if arch == "statement":  # 어두운 변형: 위험·규칙 파트를 여는 문장
        dark = secs[0].replace('class="slide orange center"', 'class="slide dark center"').replace('data-variant="orange"', 'data-variant="dark"')
        secs.append(dark)
    vnames = ", ".join(v or "기본" for v, _ in variants) + (", dark" if arch == "statement" else "")
    head = (f"<!--\n  아키타입 {arch} (변형: {vnames})\n  언제: {when}\n  단계: {steps}\n"
            f"  쓰는 법: 필요한 section 하나만 복사해 덱 src/NN-이름.html 로 저장하고 겹꺾쇠 자리표시를 모두 실제 내용으로 바꾼다.\n"
            f"  자리표시 안의 ≤N자 는 이 배치에서 넘치지 않는 최대 글자 수다(공백 포함). 항목 수를 바꾸면 check_deck.py 로 넘침을 확인한다.\n"
            f"  배치 설명: references/layouts.md · 클래스: references/classes.md\n-->\n")
    path = OUT / f"{num:02d}-{arch}.html"
    path.write_text(head + "\n\n".join(secs) + "\n", encoding="utf-8")
    written.append((path.name, len(secs)))

leak = []
for p in OUT.glob("*.html"):
    if p.name in HAND:
        continue
    t = p.read_text(encoding="utf-8")
    body = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    txt = re.sub(r"<[^>]+>|«[^»]*»", " ", body)
    words = [w for w in re.findall(r"[가-힣A-Za-z]{2,}", txt)]
    if words:
        leak.append((p.name, sorted(set(words))[:20]))
print(written)
print("remaining words (possible content leak):", leak)
