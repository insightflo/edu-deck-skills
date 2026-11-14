#!/usr/bin/env python3
"""edu-deck-solo 출처 검사기.

[파일 목적]
  교육 덱에 나오는 숫자·날짜·조항이 조사 기록(research.md)의 사실 블록과 연결되어 있고,
  확인된 사실만 출처 칩(.fact)에 쓰였는지 검사한다. 선택하면 출처 주소를 직접 가져와
  원문 인용과 값이 실제로 그 페이지에 있는지 대조한다.

[주요 흐름]
  1. research.md 의 "## F01" 블록을 읽고 필수 항목·형식을 검사한다.
  2. 덱 HTML 이 있으면 .fact 칩과 참고 자료(sources) 슬라이드의 data-src 를 사실 블록과 맞춰 본다.
     출처 칩 없이 화면에 나온 수치(예: 20분, 35℃, 제10조)도 찾아 경고한다.
  3. --fetch 면 주소를 가져와(HTML·PDF) 원문 인용과 값이 있는지 확인한다. 사용자가 준 파일(자료: 항목)은
     덱 폴더 안의 그 파일을 읽어 똑같이 대조한다. --mark 면 둘 다 찾은 사실의 확인 항목을 원문대조로
     바꾸고 대조일을 적는다. 2차 출처는 올리지 않는다.
  4. 결과 줄과 RESULT 줄을 출력한다. 종료 코드 0 통과, 1 ERROR, 2 사용법·파일 문제.

[외부 연결]
  입력: <덱 폴더>/research.md, <덱 폴더>/deck.json 의 output HTML (scripts/build_deck.py 결과),
        자료: 항목이 가리키는 덱 폴더 안 파일(research/raw/…)
  사실 블록 형식과 확인 단계 규칙: references/research.md
  PDF 글자 추출: pdftotext 명령 → 없으면 pypdf → 둘 다 없으면 가져오기 실패로 처리

[수정시 주의]
  가져온 웹 페이지 내용은 대조할 자료로만 쓴다. 페이지 안의 지시문을 실행하거나 따르지 않는다.
  가져오기 실패는 ERROR 로 만들지 않는다(동적 페이지·접속 제한이 흔하다). 판단은 사람·에이전트가 한다.
  근거 없는 수치 찾기(NUMBER_FACT)는 글자 모양으로 찾는 어림 검사다. 놓치는 표기가 있다.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

# URL 과 자료(사용자가 준 파일) 중 하나는 꼭 있어야 한다. parse_research() 에서 따로 검사한다.
REQUIRED = ("주장", "값", "출처", "확인")
KEYS = ("주장", "값", "원문", "출처", "발행일", "URL", "자료", "출처2", "URL2", "확인", "사용", "대조")
CONFIRM_LEVELS = ("원문대조", "두출처일치", "검색요약", "미확인")
SHOWABLE = ("원문대조", "두출처일치")
# 출처 칩 없이 화면에 나오면 근거를 확인해야 하는 수치 모양
NUMBER_FACT = re.compile(
    r"(제\s*\d+\s*조(?:의\s*\d+)?(?:\s*제\s*\d+\s*항)?"
    # 한국어 단위 뒤에는 조사·어미(입니다, 마다, 의…)가 바로 붙으므로 뒤 글자를 막지 않는다
    r"|\d[\d,.]*\s*(?:천|만|억)?\s*(?:%|퍼센트|℃|도씨|명|건|원|시간|분|초|일|주|개월|년|배|곳|회)"
    # 도·세·시·월은 낱말 첫 글자(도입·세부·시작·월간)로도 흔해 숫자에 바로 붙은 것만 본다(33도, 65세, 14시, 10월). 3세대 같은 '세대'는 뺀다.
    # 개·단계·가지는 일반 설명에 너무 흔해 뺀다
    r"|\d[\d,.]*(?:도|세(?!대)|시|월)"
    r"|\d[\d,.]*\s*(?:kg|km|mm|cm|m|㎡|dB|ppm|lux|mg)(?![A-Za-z])"
    # 날짜: 2026. 10. 30 / 2026-10-30 / 2026/10/30
    r"|\d{4}\s?[.\-/]\s?\d{1,2}\s?[.\-/]\s?\d{1,2})"
)

# 근거 없는 수치 어림 검사에서 아예 빼는 장 계열(아키타입 화이트리스트) — 실사용 피드백 B4-①.
# 출처·표지는 원래 제외였고, part-divider·check·closing 은 활동 시간·운영 표기("활동 5분",
# "산출물 1곳")가 주를 이루는 장이라 어림 경고를 내지 않는다. 칩·참고 자료 검사는 그대로 한다.
LOOSE_SKIP_ARCHS = {"sources", "cover", "part-divider", "check", "closing"}
# 메타·키커 줄(eyebrow·kicker·이름에 meta 가 들어가는 클래스) 안의 수치는 장 운영 정보다 —
# "대상 교육 · 25–30분 · 22장", "구글 내부 사례 4종"(실사용 피드백 B4).
LOOSE_META = re.compile(r"kicker|eyebrow|meta", re.I)
# 같은 문맥 블록에 '예시'·'가상' 마커가 있으면 그 수치는 예시 값이다(실사용 피드백 B4-②).
LOOSE_EXAMPLE = ("예시", "가상")
LOOSE_BLOCK = ("p", "li", "dt", "dd", "td", "th", "figcaption", "blockquote",
               "h1", "h2", "h3", "h4", "h5", "h6", "summary", "button", "label")


def loose_exempt(t, sec):
    """어림 수치 스캔에서 빼는 글자 노드인가 (실사용 피드백 B4).
    ① 칩을 단 구성 요소 안의 수치 — 노드를 품은 장 최상위 블록에 .fact 칩이 있으면
       그 출처 표시의 일부(보조 라벨·단위)로 본다. .win 제외와 같은 구조 완화다.
    ② eyebrow·kicker·*meta* 줄의 수치 — 장 운영 정보(대상·분량·구성 수).
    ③ 같은 문맥 블록에 '예시'·'가상' 마커가 있는 수치 — 저작자가 예시 값이라 밝힌 것."""
    e = t.parent
    while e is not None and e is not sec:
        if e.parent is sec:
            if e.select_one(".fact"):
                return True
            break
        e = e.parent
    if t.find_parent(class_=LOOSE_META):
        return True
    blk = t.find_parent(LOOSE_BLOCK)
    return blk is not None and any(m in blk.get_text() for m in LOOSE_EXAMPLE)


class Out:
    """결과 줄 모음. sev 는 ERROR / WARN / INFO."""

    def __init__(self):
        self.rows = []

    def add(self, sev, where, msg):
        self.rows.append((sev, where, msg))

    def count(self, sev):
        return sum(1 for r in self.rows if r[0] == sev)


def clean_value(v: str) -> str:
    """마크다운 링크·꺾쇠·굵게 표시를 걷어 낸 값. 검색 에이전트가 링크 형식으로 적는 경우가 많다."""
    v = re.sub(r"\[([^\]]*)\]\((https?://[^)]+)\)", r"\1 \2", v)
    v = re.sub(r"\*\*|__|`", "", v)
    return v.strip().strip("<>").strip()


def parse_research(path: Path, out: Out):
    """
    [목적] research.md 의 사실 블록을 읽어 사전으로 만든다.
    [입력] research.md 경로, 결과 모음
    [출력] {"F01": {"주장": …, …, "_line": 줄 번호}, …}
    [연결] check_html(), fetch_and_compare() 가 이 사전을 쓴다.
    [주의] "## 조사 메모" 같은 F 로 시작하지 않는 제목은 사실 블록이 아니므로 건너뛴다.
    [수정시 영향] 항목 이름(주장·값…)을 바꾸면 references/research.md 의 양식과 기존 덱이 모두 어긋난다.
    """
    facts, cur = {}, None
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"^##\s+(F\d{2,3})\s*$", line.strip())
        if m:
            fid = m.group(1)
            if fid in facts:
                out.add("ERROR", fid, f"사실 id 가 두 번 나옵니다 ({no}번째 줄)")
            cur = facts.setdefault(fid, {"_line": no})
            continue
        if line.startswith("## ") or line.startswith("# "):
            cur = None
            continue
        if cur is None:
            continue
        # 출처2·URL2 처럼 끝에 숫자 하나가 붙는 항목 이름도 읽는다
        m = re.match(r"^\s*-\s*([가-힣A-Za-z]+\d?)\s*:\s*(.*)$", line)
        if m and m.group(1) in KEYS:
            cur[m.group(1)] = clean_value(m.group(2))
    for fid, f in facts.items():
        for k in REQUIRED:
            if not f.get(k):
                out.add("ERROR", fid, f"'{k}' 항목이 비었습니다 (research.md {f['_line']}번째 줄 블록)")
        lvl = f.get("확인", "")
        if lvl and lvl not in CONFIRM_LEVELS:
            out.add("ERROR", fid, f"확인 '{lvl}' 은 {'/'.join(CONFIRM_LEVELS)} 중 하나여야 합니다")
        url = f.get("URL", "")
        urls = re.findall(r"https?://\S+", url)
        if url and not urls:
            out.add("ERROR", fid, f"URL 형식이 아닙니다: {url[:60]}")
        f["_url"] = urls[0].rstrip(".,);」") if urls else ""
        f["_file"] = local_file(path.parent, f.get("자료", ""), fid, out)
        if not url and not f.get("자료"):
            out.add("ERROR", fid, "'URL' 또는 '자료' 항목이 필요합니다 (웹 주소, 또는 덱 폴더 안 파일 research/raw/…)")
        d = f.get("발행일", "미상") or "미상"
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}|\d{4}-\d{2}|\d{4}|미상", d):
            out.add("ERROR", fid, f"발행일 '{d}' 은 YYYY-MM-DD / YYYY-MM / YYYY / 미상 중 하나로 씁니다")
        if lvl == "원문대조" and not f.get("원문"):
            out.add("WARN", fid, "원문대조인데 원문 인용이 없습니다")
        if lvl == "원문대조" and not f.get("대조"):
            out.add("ERROR", fid, "원문대조에는 '대조:' 줄(언제·어떻게 원문을 확인했는지)이 필요합니다")
        if lvl == "두출처일치":
            u2 = re.findall(r"https?://\S+", f.get("URL2", ""))
            if not f.get("출처2") or not u2:
                out.add("ERROR", fid, "두출처일치에는 서로 다른 두 번째 출처(출처2, URL2)가 필요합니다")
            elif f["_url"] and u2[0].split("/")[2] == f["_url"].split("/")[2]:
                out.add("WARN", fid, "두 출처의 주소가 같은 사이트입니다. 독립된 출처인지 확인하세요")
    if not facts:
        out.add("WARN", "-", "research.md 에 사실 블록(## F01)이 없습니다")
    return facts


def local_file(deck_dir: Path, value: str, fid: str, out: Out) -> str:
    """
    [목적] '자료:' 항목(사용자가 준 파일)을 덱 폴더 안의 실제 파일 경로로 바꾼다.
    [입력] 덱 폴더(research.md 가 있는 폴더), 항목 값(예: research/raw/안전규정.pdf p.12), 사실 id, 결과 모음
    [출력] 파일 절대 경로 문자열. 값이 없거나 문제가 있으면 "" (문제는 ERROR 로 남긴다)
    [주의] 덱 폴더 밖 파일은 받지 않는다. 덱을 다른 곳으로 옮기거나 다시 검사할 때 근거가 사라지지 않게 하려는 것이다.
           끝의 쪽 표시(p.12, p.3-4, 12쪽)는 사람이 찾아보라고 쓰는 것이라 대조는 파일 전체로 한다.
    """
    if not value:
        return ""
    rel = re.sub(r"\s+(?:p\.?\s*\d[\d\-~,]*|\d+\s*쪽)\s*$", "", value).strip()
    base = deck_dir.resolve()
    p = (base / rel).resolve()
    if p != base and base not in p.parents:
        out.add("ERROR", fid, f"자료 파일은 덱 폴더 안(research/raw/)에 둡니다: {rel[:60]}")
        return ""
    if not p.is_file():
        out.add("ERROR", fid, f"자료 파일이 없습니다: {rel[:60]}")
        return ""
    return str(p)


def norm(s: str) -> str:
    """대조용 정규화: 따옴표·공백·일부 문장부호를 지운다(띄어쓰기 차이로 놓치지 않게)."""
    s = re.sub(r"[“”\"'‘’「」『』\s·・,]", "", s or "")
    return s.replace("～", "~").lower()


def check_html(html_path: Path, facts, out: Out):
    """
    [목적] 덱 HTML 의 출처 칩·참고 자료 목록·근거 없는 수치를 사실 블록과 맞춰 본다.
    [입력] 덱 HTML 경로, 사실 사전, 결과 모음
    [출력] 칩이 인용한 사실 id 집합
    [연결] 칩 표기 규칙은 references/classes.md 의 .fact, 참고 자료 슬라이드는 assets/snippets/28-sources.html.
    [주의] 모형 창(.win) 안의 숫자는 예시용 가상 값이라 근거 없는 수치 경고에서 뺀다.
    """
    try:
        from bs4 import BeautifulSoup, Comment
    except ImportError:
        out.add("ERROR", "-", "beautifulsoup4 가 필요합니다 (설치 안내: pip install beautifulsoup4)")
        return set()
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    slides = soup.select("#stage > section.slide")
    cited, chip_text = set(), {}
    for n, sec in enumerate(slides, 1):
        # P1-1: 숫자 증거 띠 지표(.stat)도 출처 칩과 같은 사실 id 체계(data-src)로 검증한다.
        # P1-2: 실물 화면 인용의 출처 캡션(.sc-src)도 같은 체계로 검증한다(이미지 자체는 alt 로 요지를 말한다).
        for chip in sec.select(".fact, .stat-strip .stat, .screen-cite .sc-src"):
            ids = [x.strip() for x in (chip.get("data-src") or "").split(",") if x.strip()]
            text = chip.get_text(" ", strip=True)
            if not ids:
                out.add("WARN", f"#{n}", f"출처 id 없는 칩: “{text[:30]}”")
            for fid in ids:
                cited.add(fid)
                chip_text.setdefault(fid, []).append(text)
                if fid not in facts:
                    out.add("ERROR", f"#{n}", f"칩이 research.md 에 없는 {fid} 를 인용합니다")
                    continue
                lvl = facts[fid].get("확인", "")
                if lvl not in SHOWABLE:
                    out.add("ERROR", fid, f"#{n} 칩에 쓰였지만 확인 단계가 '{lvl}' 입니다 (원문대조·두출처일치만 화면에 씁니다)")
                if "(2차)" in facts[fid].get("출처", ""):
                    out.add("ERROR", fid, f"#{n} 칩이 2차 출처를 인용합니다. 2차 출처는 노트에만 씁니다. 공식 원문을 찾아 바꾸세요")
        if sec.get("data-archetype") in LOOSE_SKIP_ARCHS:
            continue
        # 칩 밖에 나온 수치 중 같은 슬라이드의 어떤 칩에도 없는 것 → 근거 확인 필요
        chips = " ".join(norm(c.get_text(" ", strip=True)) for c in sec.select(".fact"))
        texts = []
        for t in sec.find_all(string=True):
            if (isinstance(t, Comment) or t.find_parent(["aside", "script", "style"])
                    or t.find_parent(class_="win") or t.find_parent(class_="fact")
                    or t.find_parent(class_="stat-strip") or t.find_parent(class_="screen-cite")
                    or loose_exempt(t, sec)):
                continue
            texts.append(t)
        found = sorted(set(m.group(0).strip() for m in NUMBER_FACT.finditer(" ".join(texts))))
        loose = [x for x in found if norm(x) not in chips]
        if loose:
            out.add("WARN", f"#{n}", f"출처 칩 없는 수치: {', '.join(loose[:6])} — 근거가 있는 사실이면 칩을 달고, 예시 값이면 '예시'라고 밝히세요")
    listed = {}
    for sec in [s for s in slides if s.get("data-archetype") == "sources"]:
        for li in sec.select("[data-src]"):
            for fid in [x.strip() for x in li["data-src"].split(",") if x.strip()]:
                listed[fid] = li
    for fid in sorted(cited):
        if fid in facts and fid not in listed:
            out.add("ERROR", fid, "칩에 쓰였지만 참고 자료 슬라이드에 없습니다")
        if fid in facts and facts[fid].get("값"):
            v = norm(facts[fid]["값"])
            if v and not any(v in norm(t) for t in chip_text.get(fid, [])):
                out.add("WARN", fid, f"값 '{facts[fid]['값'][:30]}' 이 칩 글자에 그대로 없습니다 (숫자를 바꿔 쓰지 않았는지 확인)")
    for fid, li in listed.items():
        if fid not in facts:
            out.add("ERROR", fid, "참고 자료 슬라이드에 있지만 research.md 에 없습니다")
            continue
        if fid not in cited and (facts[fid].get("사용") or "-").strip() in ("-", "없음", ""):
            out.add("WARN", fid, "참고 자료 슬라이드에만 있고 칩·사용 기록이 없습니다")
        host = re.sub(r"^https?://(www\.)?", "", facts[fid].get("_url", "")).split("/")[0]
        blob = li.get_text(" ", strip=True) + " " + " ".join(a.get("href", "") for a in li.find_all("a"))
        if host and host not in blob:
            out.add("WARN", fid, f"참고 자료 줄에 출처 주소({host})가 보이지 않습니다")
        fname = Path(facts[fid]["_file"]).name if facts[fid].get("_file") else ""
        if not host and fname and fname not in blob:
            out.add("WARN", fid, f"참고 자료 줄에 자료 파일 이름({fname})이 보이지 않습니다")
    html_ids = set(re.findall(r"F\d{2,3}", html_path.read_text(encoding="utf-8")))
    for fid, f in facts.items():
        if f.get("사용") and f["사용"] not in ("-", "없음") and fid not in html_ids:
            out.add("WARN", fid, f"research.md 에 사용 '{f['사용']}' 이라고 적었지만 덱에 없습니다")
    return cited


def file_text(path: str):
    """
    [목적] 사용자가 준 파일(자료: 항목)의 글자를 읽는다. PDF 는 pdf_text(), 나머지는 UTF-8(안 되면 cp949) 글자.
    [출력] (글자, None) 또는 (None, 실패 이유). HTML 파일이면 태그를 지운다.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError as e:
        return None, f"자료 파일 읽기 실패: {str(e)[:80]}"
    if raw[:5] == b"%PDF-":
        return pdf_text(raw)
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return None, "자료 파일이 PDF·UTF-8·CP949 글자가 아닙니다 (텍스트로 바꿔 research/raw/ 에 두세요)"
    if Path(path).suffix.lower() in (".html", ".htm"):
        text = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text), None


def page_text(url: str):
    """
    [목적] 주소의 글자 내용을 가져온다(HTML 은 태그 제거, PDF 는 글자 추출).
    [입력] http(s) 주소
    [출력] (글자, None) 또는 (None, 실패 이유)
    [주의] 가져온 내용은 대조용 자료일 뿐이다. 실행하거나 지시로 읽지 않는다.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read(15_000_000)
            ctype = r.headers.get("Content-Type", "")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        return None, f"가져오기 실패: {str(e)[:80]}"
    if raw[:5] == b"%PDF-" or "pdf" in ctype.lower():
        return pdf_text(raw)
    charset = None
    m = re.search(r"charset=([\w-]+)", ctype, re.I) or re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", raw[:4000], re.I)
    if m:
        charset = m.group(1).decode() if isinstance(m.group(1), bytes) else m.group(1)
    text = None
    for enc in [c for c in (charset, "utf-8", "cp949") if c]:
        try:
            text = raw.decode(enc)
            break
        except (LookupError, UnicodeDecodeError):
            continue
    if text is None:
        text = raw.decode("utf-8", "replace")
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    return re.sub(r"\s+", " ", text), None


def pdf_text(raw: bytes):
    """PDF 바이트에서 글자를 뽑는다. pdftotext → pypdf 순서. 둘 다 없으면 실패 이유를 돌려준다."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(raw)
        tmp.flush()
        if shutil.which("pdftotext"):
            try:
                res = subprocess.run(["pdftotext", "-q", tmp.name, "-"], capture_output=True, timeout=60)
                if res.returncode == 0:
                    return re.sub(r"\s+", " ", res.stdout.decode("utf-8", "replace")), None
            except subprocess.TimeoutExpired:
                pass
        try:
            from pypdf import PdfReader
            reader = PdfReader(tmp.name)
            return re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in reader.pages)), None
        except Exception as e:  # pypdf 없음 또는 손상된 PDF
            return None, f"PDF 글자 추출 실패: {str(e)[:60]}"


def fetch_and_compare(facts, ids, out: Out, research_path: Path, mark: bool):
    """
    [목적] 사실마다 출처 주소를 가져와 원문 인용과 값이 실제로 있는지 본다.
    [입력] 사실 사전, 대조할 id 목록, 결과 모음, research.md 경로, --mark 여부
    [출력] (가져온 수, 시도한 수). --mark 면 원문과 값을 모두 찾은 사실의 확인을 원문대조로 고쳐 쓴다.
    [주의] 인용이 "…" 로 끊긴 경우 조각마다(8자 이상) 찾는다. 동적 페이지는 글자가 없어 미확인으로 남는다.
           자료: 파일이 있으면 URL 보다 그 파일과 먼저 대조한다(사용자가 준 원본). (2차) 출처는 대조가 맞아도 원문대조로 올리지 않는다.
    [수정시 영향] 판정을 느슨하게 하면 확인되지 않은 숫자가 화면에 나갈 수 있다.
    """
    fetched, tried, upgrade = 0, 0, []
    for fid in sorted(ids):
        f = facts.get(fid)
        if not f or not (f.get("_url") or f.get("_file")):
            continue
        tried += 1
        text, err = file_text(f["_file"]) if f.get("_file") else page_text(f["_url"])
        if err:
            out.add("WARN", fid, err)
            continue
        fetched += 1
        body = norm(text)
        quote = f.get("원문", "")
        pieces = [norm(p) for p in re.split(r"…|\.\.\.", quote) if len(norm(p)) >= 8]
        quote_ok = bool(pieces) and all(p in body for p in pieces)
        value_ok = bool(norm(f.get("값", ""))) and norm(f["값"]) in body
        if quote_ok and value_ok:
            out.add("INFO", fid, "원문 확인됨 (인용과 값 모두 페이지에 있음)")
            if mark and f.get("확인") in ("검색요약", "미확인"):
                if "(2차)" in f.get("출처", ""):
                    out.add("WARN", fid, "2차 출처라 원문대조로 올리지 않았습니다. 공식 출처를 찾아 바꾸세요")
                else:
                    upgrade.append(fid)
        elif quote_ok:
            out.add("WARN", fid, "인용은 있으나 값이 페이지에 그대로 없습니다 (값 표기를 원문과 맞추세요)")
        else:
            out.add("WARN", fid, "원문 미확인 (동적 페이지·다른 판일 수 있음. 다른 주소나 두 번째 출처로 확인)")
    if upgrade:
        lines = research_path.read_text(encoding="utf-8").splitlines()
        cur, today = None, date.today().isoformat()
        for i, line in enumerate(lines):
            m = re.match(r"^##\s+(F\d{2,3})\s*$", line.strip())
            if m:
                cur = m.group(1)
            elif cur in upgrade and re.match(r"^\s*-\s*확인\s*:", line):
                lines[i] = "- 확인: 원문대조"
                lines.insert(i + 1, f"- 대조: {today} verify_sources.py --fetch (인용·값 일치)")
                cur = None
        research_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out.add("INFO", "-", f"확인을 원문대조로 바꿨습니다: {', '.join(upgrade)}")
    return fetched, tried


# ── 글자 그대로 대조(--quotes)·금지어(--ban) ────────────────────────────────
# ko-document-studio verify_source.py(© 2026 acc0mplish, MIT)의 설계를 우리 마크업 계약으로 재작성했다.
# 저쪽은 section.ag-slide 기준, 우리는 #stage > .slide. "덱에 실렸는가" 판정 대상은
# 코드 상자(.code pre — .p·.out·.c·.ph span은 복사에서 빠지므로 제외)와 복사 단추 텍스트다.


def squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text)


def first_mismatch(probe: str, src: str) -> int:
    """probe의 앞부분이 src 안에 남아 있는 최장 길이 — 이진탐색."""
    lo, hi = 0, len(probe)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if probe[:mid] in src:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _deck_text(html_path: Path):
    """(장 번호→화면 글자 집계, 복사 대상 글자) — 스크립트·노트·뷰어 크롬은 뺀다."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    for sel in ("script", "style", "aside.notes", ".ed-top", ".ed-bot", ".ed-reader-nav",
                ".ed-zoom-hint", "#help", "[hidden]", ".sr-only"):
        for el in soup.select(sel):
            el.decompose()
    slides, code = {}, []
    for n, sec in enumerate(soup.select("#stage > .slide"), 1):
        slides[str(n)] = sec.get_text()
    for pre in soup.select(".code pre"):
        for el in pre.select(".p, .out, .c, .ph"):
            el.decompose()
        code.append(pre.get_text())
    return slides, "".join(code)


def check_quotes(quotes: dict, src_text: str, html_path: Path, out: Out):
    """축자 글이 ①원문에 있는가 ②덱의 코드·복사 대상에 그대로 실렸는가 이중 검사."""
    slides, code_text = _deck_text(html_path)
    src = squeeze(src_text)
    screen = squeeze(code_text)
    ok = 0
    for name, text in quotes.items():
        probe = squeeze(text)
        if probe not in src:
            at = first_mismatch(probe, src)
            pos = src.find(probe[:at]) + at if at else src.find(probe[:4])
            out.add("ERROR", "quotes", f"“{name}” 원문과 {at}글자까지 일치 — 덱: {probe[at:at+30]} | 원문: {src[max(pos,0):max(pos,0)+30]}")
        elif probe not in screen:
            out.add("ERROR", "quotes", f"“{name}” 원문에는 있지만 덱의 코드 상자에 그대로 실리지 않았습니다")
        else:
            ok += 1
    out.add("INFO", "quotes", f"글자 그대로 대조: {ok}/{len(quotes)} 일치")


def check_ban(words: list, html_path: Path, out: Out):
    """지우기로 한 낱말이 덱 HTML(메타·설정 포함 raw)과 화면 글자에 남았는지 검사."""
    slides, _ = _deck_text(html_path)
    raw = html_path.read_text(encoding="utf-8")
    import html as _html
    plain = _html.unescape(raw)
    for word in words:
        n = plain.count(word)
        where = [sid for sid, t in slides.items() if word in t]
        if n:
            out.add("ERROR", "ban", f"'{word}': HTML {n}곳, 장 {', '.join('#'+s for s in where) or '(메타·설정)'}")
        else:
            out.add("INFO", "ban", f"'{word}': HTML 0곳")


def main(argv=None):
    """
    [목적] 명령줄 진입점. 덱 폴더 방식과 파일 지정 방식을 모두 받는다.
    [입력] <덱 폴더> 또는 --research FILE [--html FILE], 선택 --fetch --all --mark --json
    [출력] 결과 줄과 RESULT 줄, 종료 코드 0/1/2
    [연결] SKILL.md 의 조사 단계(슬라이드 쓰기 전 --fetch --all --mark)와 검사 단계(--fetch)에서 쓴다.
    """
    ap = argparse.ArgumentParser(description="research.md 사실 블록과 덱의 출처 칩을 검사합니다.")
    ap.add_argument("deck_dir", nargs="?", help="deck.json·research.md 가 있는 덱 폴더")
    ap.add_argument("--research", help="research.md 경로 (덱 폴더 대신)")
    ap.add_argument("--html", help="덱 HTML 경로 (덱 폴더 대신)")
    ap.add_argument("--fetch", action="store_true", help="출처 주소를 가져와 원문 대조")
    ap.add_argument("--all", action="store_true", help="--fetch 때 칩에 안 쓴 사실까지 모두 대조")
    ap.add_argument("--mark", action="store_true", help="인용·값이 모두 확인된 사실의 확인을 원문대조로 고쳐 씀")
    ap.add_argument("--quotes", help='글자 그대로 옮길 글 {"이름": "글"} JSON 파일 — 덱의 .code 상자와 이중 대조')
    ap.add_argument("--quotes-src", help="--quotes 원문 대조 파일(미지정 시 research.md)")
    ap.add_argument("--ban", action="append", default=[], help="덱에 남아 있으면 안 되는 낱말(반복 가능)")
    ap.add_argument("--json", help="결과 JSON 저장 경로")
    args = ap.parse_args(argv)
    if args.deck_dir:
        d = Path(args.deck_dir)
        research = d / "research.md"
        html = None
        cfg = d / "deck.json"
        # deck.json 이 없으면 아직 조립 전(2단계 조사)이라 research.md 만 본다.
        # deck.json 이 있는데 결과 HTML 이 없으면 덱을 검사한 것처럼 통과시키지 않는다.
        if cfg.is_file():
            try:
                name = json.loads(cfg.read_text(encoding="utf-8-sig")).get("output", "")
            except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
                print(f"ERROR  deck.json 을 읽을 수 없습니다: {str(e)[:80]}", file=sys.stderr)
                return 2
            if not name or not (d / name).is_file():
                print(f"ERROR  deck.json 의 결과 파일이 없습니다: {d / (name or '?')} — build_deck.py 로 먼저 조립하세요. "
                      f"조립 전에 조사 기록만 보려면 --research {research} 를 쓰세요", file=sys.stderr)
                return 2
            html = d / name
    elif args.research:
        research, html = Path(args.research), Path(args.html) if args.html else None
    else:
        ap.print_usage(sys.stderr)
        return 2
    if not research.is_file():
        print(f"ERROR  research.md 가 없습니다: {research}", file=sys.stderr)
        return 2
    if html is not None and not html.is_file():
        print(f"ERROR  덱 HTML 이 없습니다: {html}", file=sys.stderr)
        return 2
    out = Out()
    facts = parse_research(research, out)
    cited = set()
    if html:
        cited = check_html(html, facts, out)
    else:
        out.add("INFO", "-", "덱 HTML 없이 research.md 만 검사했습니다")
    fetched = tried = 0
    if args.fetch:
        ids = set(facts) if (args.all or not html) else cited
        fetched, tried = fetch_and_compare(facts, ids, out, research, args.mark)
    if args.quotes:
        if not html:
            out.add("ERROR", "quotes", "--quotes 는 덱 HTML 이 필요합니다(--html 또는 deck.json 결과)")
        else:
            try:
                qmap = json.loads(Path(args.quotes).read_text(encoding="utf-8-sig"))
                qsrc = Path(args.quotes_src) if args.quotes_src else research
                if not isinstance(qmap, dict):
                    raise ValueError("quotes JSON은 객체여야 합니다")
                if not qsrc.is_file():
                    raise FileNotFoundError(qsrc)
                check_quotes(qmap, qsrc.read_text(encoding="utf-8-sig"), html, out)
            except (OSError, ValueError) as e:
                print(f"ERROR  --quotes 처리 실패: {str(e)[:100]}", file=sys.stderr)
                return 2
    if args.ban:
        if not html:
            out.add("ERROR", "ban", "--ban 은 덱 HTML 이 필요합니다(--html 또는 deck.json 결과)")
        else:
            check_ban(args.ban, html, out)
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    for sev, where, msg in sorted(out.rows, key=lambda r: (order[r[0]], r[1])):
        print(f"{sev:<6} [{where}] {msg}")
    e, w = out.count("ERROR"), out.count("WARN")
    print(f"RESULT: {'FAIL' if e else 'PASS'}  errors={e} warnings={w} facts={len(facts)} cited={len(cited)} fetched={fetched}/{tried}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps({"errors": e, "warnings": w, "rows": out.rows,
                                               "facts": {k: {kk: vv for kk, vv in v.items() if not kk.startswith('_')} for k, v in facts.items()}},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if e else 0


if __name__ == "__main__":
    sys.exit(main())
