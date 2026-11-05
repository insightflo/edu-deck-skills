#!/usr/bin/env python3
"""요청 텍스트 → 리소스팩 디자인·학습 흐름 추천 라우터.

[파일 목적]
  새 덱·새 시리즈 편이 매번 같은 모양으로 나오는 문제를 막는다. 에이전트가 "기본값"으로
  한 경로만 타지 않도록, brief 텍스트(제목·청중·교육 뒤 할 수 있어야 하는 것)에서 신호를
  읽어 디자인 8종·흐름 8종에 점수를 매기고 후보 3종과 추천 1종을 낸다.

[주요 흐름]
  1. 제목(가중 2)·목표(1.5)·청중(1)·기타(1) 텍스트에서 신호어를 센다(DESIGN_SIGNALS/FLOW_SIGNALS).
  2. 신호가 약하거나 같은 점수면 제목 해시 기반의 작은 흔들림(JITTER)으로 순서를 돌린다.
     같은 입력은 항상 같은 결과(결정적)이고, 다른 주제는 다른 팩을 받는다. --seed 로 바꿀 수 있다.
  3. --recent 로 넘긴 최근 사용 디자인은 감점해 연속 반복을 줄인다.
  4. 후보 3종(서로 다른 디자인) + 추천 1종 + 흐름 1종 + 근거 문장을 JSON 으로 낸다.
     --emit-command 는 preview_pack.py make 명령 뼈대를 함께 출력한다.

[외부 연결]
  resource_packs.py 의 DESIGNS/FLOWS 와 같은 집합을 쓴다. 표준 라이브러리만 쓴다.
  결과는 추천일 뿐이며 사용자가 고르면 그 선택이 우선한다.

[수정시 주의]
  신호어 표의 ID 가 resource_packs.DESIGNS/FLOWS 와 어긋나면 route 가 즉시 실패한다.
  이 점수는 교육 효과 측정이 아니라 후보를 좁히는 휴리스틱이다. 근거 문장에 신호어를 그대로 밝힌다.
"""
import argparse
import hashlib
import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resource_packs import DESIGNS, FLOWS  # noqa: E402

FIELD_WEIGHT = {"title": 2.0, "outcomes": 1.5, "audience": 1.0, "extra": 1.0}
JITTER = 0.9      # 신호 한 개(가중 1)보다 작게: 신호가 있으면 신호가 이긴다
RECENT_PENALTY = 1.2  # 신호어 한 개보다 약하게: 강한 신호는 이기고, 신호가 약하거나 비슷할 때 반복만 끊는다

# 디자인별 신호어. 부분 문자열로 센다(한국어 활용형 대응).
DESIGN_SIGNALS = {
    "editorial": ["개념", "원리", "이해", "해설", "관점", "배경", "역사", "왜", "이유", "교양", "읽"],
    "lab": ["실험", "탐구", "관찰", "가설", "검증", "측정", "과학", "예측", "변화", "상태", "반응"],
    "field": ["현장", "절차", "안전", "점검", "매뉴얼", "작업", "설비", "장비", "순서", "따라", "응급"],
    "casebook": ["사례", "판단", "사건", "상황", "윤리", "위반", "법", "규정", "컴플라이언스", "개인정보", "분쟁"],
    "atlas": ["구조", "관계", "체계", "지도", "연결", "아키텍처", "구성", "계층", "시스템", "네트워크", "비율"],
    "workbook": ["학습지", "문제", "연습", "풀이", "실습", "기록", "직접", "워크북", "스스로", "자습", "숙제"],
    "briefing": ["데이터", "수치", "통계", "지표", "재무", "보고", "의사결정", "경영", "성과", "예산", "시장"],
    "seminar": ["토론", "대화", "질문", "세미나", "성찰", "철학", "공유", "의견", "인문", "독서"],
}

# 흐름별 신호어.
FLOW_SIGNALS = {
    "problem": ["문제", "해결", "개선", "대안", "불편", "혁신"],
    "case": ["사례", "판단", "상황", "윤리", "의사결정", "경계"],
    "follow": ["따라", "절차", "실습", "순서", "방법", "사용법", "설치", "설정", "작성법"],
    "inquiry": ["탐구", "실험", "관찰", "예측", "원리", "가설", "과학", "상태", "변화"],
    "compare": ["비교", "선택", "차이", "장단점", "대안", "vs", "비율"],
    "diagnose": ["오류", "진단", "원인", "장애", "트러블", "고장", "복구", "점검", "퀴즈", "오답"],
    "discussion": ["토론", "대화", "의견", "세미나", "성찰", "공유"],
    "project": ["프로젝트", "제작", "결과물", "만들", "기획", "발표 준비", "산출물"],
}

WEAK_REASON = "신호어가 약해 제목 기준으로 순서를 돌렸습니다(같은 제목은 항상 같은 결과)"


class RouterError(ValueError):
    """입력이 비어 있거나 집합이 어긋난 경우."""


def _jitter(title, key, seed):
    """제목·키·시드에서 0..JITTER 사이 결정적 수를 만든다."""
    digest = hashlib.sha256(f"{seed}|{title}|{key}".encode("utf-8")).digest()
    return (int.from_bytes(digest[:4], "big") / 0xFFFFFFFF) * JITTER


def _count(signals, fields):
    """필드별 신호어 적중을 가중 합산하고 적중한 단어를 모은다."""
    score, hits = 0.0, []
    for word in signals:
        for name, text in fields.items():
            if text and word in text:
                score += FIELD_WEIGHT[name]
                if word not in hits:
                    hits.append(word)
    return score, hits


def route(title, outcomes="", audience="", extra="", recent=(), seed="0"):
    """디자인·흐름 점수를 계산해 후보 3종·추천·흐름을 반환한다."""
    if not (title or "").strip():
        raise RouterError("title 이 비어 있습니다")
    if set(DESIGN_SIGNALS) != set(DESIGNS) or set(FLOW_SIGNALS) != set(FLOWS):
        raise RouterError("신호어 표의 ID 가 resource_packs.DESIGNS/FLOWS 와 다릅니다")
    bad = [r for r in recent if r not in DESIGNS]
    if bad:
        raise RouterError(f"--recent 에 알 수 없는 디자인: {', '.join(bad)}")
    fields = {"title": title, "outcomes": outcomes, "audience": audience, "extra": extra}

    rows = []
    for design in DESIGNS:
        base, hits = _count(DESIGN_SIGNALS[design], fields)
        penalty = RECENT_PENALTY if design in recent else 0.0
        total = base + _jitter(title, design, seed) - penalty
        rows.append({"design": design, "score": round(total, 3), "signals": hits,
                     "recent_penalty": bool(penalty)})
    rows.sort(key=lambda r: (-r["score"], r["design"]))
    top = rows[:3]
    for row in top:
        row["because"] = ("신호어: " + ", ".join(row["signals"])) if row["signals"] else WEAK_REASON
        if row["recent_penalty"]:
            row["because"] += " (최근 사용 팩이라 감점)"

    flow_rows = []
    for flow in FLOWS:
        base, hits = _count(FLOW_SIGNALS[flow], fields)
        flow_rows.append({"flow": flow, "score": round(base + _jitter(title, "flow:" + flow, seed), 3),
                          "signals": hits})
    flow_rows.sort(key=lambda r: (-r["score"], r["flow"]))
    return {
        "title": title,
        "seed": seed,
        "recommend": top[0]["design"],
        "candidates": [{"design": r["design"], "score": r["score"], "because": r["because"]} for r in top],
        "flow": flow_rows[0]["flow"],
        "flow_signals": flow_rows[0]["signals"],
        "flow_runner_up": flow_rows[1]["flow"],
        "weak_signal": all(not r["signals"] for r in top),
    }


def preview_command(result, folder="<작업 폴더>"):
    """preview_pack.py make 명령 뼈대를 만든다(<solo> 경로는 호출자가 채운다)."""
    head = "python3 <solo>/scripts/preview_pack.py make"  # 경로 자리표시자는 인용하지 않는다
    parts = [folder, "--title", result["title"]]
    for cand in result["candidates"]:
        parts += ["--pack", cand["design"], "--because", cand["because"]]
    parts += ["--recommend", result["recommend"], "--flow", result["flow"]]
    return head + " " + " ".join(shlex.quote(p) for p in parts)


def main(argv=None):
    ap = argparse.ArgumentParser(description="요청 텍스트로 리소스팩 후보 3종·추천·흐름을 계산한다")
    ap.add_argument("--title", required=True, help="덱 제목 또는 주제")
    ap.add_argument("--outcomes", default="", help="교육 뒤 청중이 할 수 있어야 하는 것(문장 이어 붙임)")
    ap.add_argument("--audience", default="", help="청중 설명")
    ap.add_argument("--extra", default="", help="그 밖의 요청 문장(형식·분위기 요청 등)")
    ap.add_argument("--recent", action="append", default=[], metavar="ID",
                    help="최근 쓴 디자인(감점, 여러 번 가능). 시리즈 연속 제작 때 쓴다")
    ap.add_argument("--seed", default="0", help="같은 입력으로 다른 변주를 원할 때 바꾼다")
    ap.add_argument("--emit-command", action="store_true", help="preview_pack.py make 명령 뼈대도 출력")
    ap.add_argument("--folder", default="<작업 폴더>")
    args = ap.parse_args(argv)
    try:
        result = route(args.title, args.outcomes, args.audience, args.extra, args.recent, args.seed)
    except RouterError as e:
        print(f"ERROR  {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.emit_command:
        print("\n# 프리뷰 명령(<solo> 를 실제 edu-deck-solo 폴더로 바꿔 실행)")
        print(preview_command(result, args.folder))
    return 0


if __name__ == "__main__":
    sys.exit(main())
