#!/usr/bin/env python3
"""요청 텍스트 → legacy 테마·표지 변형·줄거리(arc)·스타일 프리셋 추천 라우터.

[파일 목적]
  resource_pack 을 쓰지 않는 legacy 경로 덱이 매번 같은 팔레트·같은 표지·같은 줄거리로
  나오는 문제를 막는다. brief 텍스트(제목·청중·교육 뒤 할 수 있어야 하는 것)에서
  톤 축 6개를 계산하고, 축과 후보별 시그니처의 거리로 테마·표지·arc 및 선택적 오버레이인
  스타일 프리셋(shared/presets/*.yaml 16종)을 고른다.

[주요 흐름]
  1. 제목(가중 2)·목표(1.5)·청중(1)·기타(1) 텍스트에서 축 신호어를 센다(AXIS_SIGNALS).
     축마다 위쪽 단어와 아래쪽 단어가 따로 있어 0..1 연속값으로 환산한다(AXES 순서).
  2. 후보별 점수 = 축 시그니처와의 가중 거리(가까울수록 높음) + 제목 해시 지터(JITTER)
     − 최근 사용 감점(RECENT_PENALTY). 같은 입력은 항상 같은 결과(결정적)이고
     다른 변주가 필요하면 --seed 를 바꾼다.
  3. 테마·표지·arc·프리셋 각각 후보 3종 + 추천 1종 + 근거 문장을 JSON 으로 낸다.

[외부 연결]
  THEMES 의 id 는 assets/css/themes.css 의 [data-theme="…"] 블록과 1:1 이다
  ('classic' 만 블록이 없다 — 기본 :root 그대로). COVERS 의 id 는
  assets/snippets/01-cover*.html 의 data-variant, ARCS 의 opens 는
  check_deck.py 의 arc 인지 흐름 규칙이 쓴다. PRESETS 의 id 는
  shared/presets/*.yaml (style_preset.py --list) 16종과 1:1 이다.
  build_deck.py·build_series.py 도 같은 목록으로 deck.json 의 theme·arc 를 검증한다. 표준 라이브러리만 쓴다.

[수정시 주의]
  테마를 추가하면 themes.css 에 15 의미 역할 전부를 정의한 블록을 함께 둔다
  (일부만 덮으면 대비 매트릭스가 깨진다). shape 시그니처(round/motion/density/spring)는
  themes.css 블록 안 비색 토큰(r*, m*, s*, e-spring)의 lerp 입력이므로 두 곳을 함께 고른다.
  프리셋을 추가·삭제하면 shared/presets/*.yaml 과 PRESETS 를 함께 맞춘다.
  이 점수는 교육 효과 측정이 아니라 후보를 좁히는 휴리스틱이다. 근거 문장에 신호어를 밝힌다.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

FIELD_WEIGHT = {"title": 2.0, "outcomes": 1.5, "audience": 1.0, "extra": 1.0}
JITTER = 0.9       # 신호 한 개(가중 1)보다 작게: 신호가 있으면 신호가 이긴다
RECENT_PENALTY = 1.2
AXIS_STEP = 0.22   # 신호어 한 개(가중 1)가 축을 움직이는 폭

# 톤 축 6개: (아래쪽 신호어, 위쪽 신호어). 값 = 0.5 + STEP × (위 점수 − 아래 점수), 0..1.
AXES = ("energy", "playful", "technical", "serious", "warm", "formal")
AXIS_SIGNALS = {
    "energy":    (["강의", "이론", "강연", "독서", "차분", "듣기"],
                  ["활동", "실습", "워크숍", "참여", "게임", "퀴즈", "도전", "역할", "발표", "토론", "현장", "즉시", "빠르", "단원 평가", "단원평가"]),
    "playful":   (["격식", "공식", "엄격", "진지", "보고", "감사", "규정", "법", "컴플라이언스", "처벌"],
                  ["게임", "재미", "놀이", "캐릭터", "유쾌", "가볍", "친근", "챌린지", "스티커", "이벤트", "퀴즈"]),
    "technical": (["마음", "태도", "문화", "소통", "리더십", "감정", "철학", "인문", "가치"],
                  ["시스템", "기술", "코드", "데이터", "수치", "구조", "원리", "공식", "절차", "매뉴얼", "사양", "분석", "지표", "계산", "비율", "물질", "상태", "장비", "설정", "사용법", "학습지", "전자결재"]),
    "serious":   (["놀이", "재미", "취미", "이벤트", "축제", "가벼운"],
                  ["안전", "사고", "위험", "법", "규정", "위반", "벌금", "처벌", "개인정보", "보안", "감사", "재해", "응급", "금지", "의무", "폭염", "보호"]),
    "warm":      (["규정", "처벌", "감사", "평가", "감점", "단속", "차가운"],
                  ["환영", "온보딩", "신입", "응대", "고객", "배려", "상담", "돌봄", "복지", "인사", "따뜻", "격려", "멘토", "동료", "사례"]),
    "formal":    (["캐주얼", "가볍게", "편하게", "자유", "비공식", "수다"],
                  ["보고", "공식", "임원", "경영", "재무", "회계", "감사", "규정", "정책", "품의", "결재", "문서", "공문", "조례", "회의"]),
}

# 테마 시그니처. axes = 축 위치(0..1), shape = 비색 토큰 lerp 입력(themes.css 와 짝).
#   shape: round=r1 2+12x / r2 8+16x / r3 12+24x, motion=m1 80+140x / m2 180+240x / m3 300+400x / m4 500+600x,
#          density=간격 배율(0→×0.75, 0.5→×1.0, 1→×1.25), spring=e-spring y1 1.05+0.45x.
THEMES = {
    "classic":  {"axes": {"energy": .4, "playful": .3, "technical": .4, "serious": .4, "warm": .5, "formal": .5},
                 "shape": {"round": .5, "motion": .5, "density": .5, "spring": .5}},
    "ocean":    {"axes": {"energy": .5, "playful": .4, "technical": .7, "serious": .4, "warm": .3, "formal": .6},
                 "shape": {"round": .55, "motion": .45, "density": .5, "spring": .5}},
    "cobalt":   {"axes": {"energy": .3, "playful": .2, "technical": .8, "serious": .7, "warm": .2, "formal": .8},
                 "shape": {"round": .15, "motion": .35, "density": .25, "spring": .2}},
    "forest":   {"axes": {"energy": .5, "playful": .5, "technical": .3, "serious": .3, "warm": .6, "formal": .4},
                 "shape": {"round": .7, "motion": .55, "density": .5, "spring": .6}},
    "solar":    {"axes": {"energy": .9, "playful": .7, "technical": .3, "serious": .3, "warm": .8, "formal": .3},
                 "shape": {"round": .85, "motion": .75, "density": .85, "spring": .9}},
    "berry":    {"axes": {"energy": .6, "playful": .6, "technical": .3, "serious": .4, "warm": .7, "formal": .4},
                 "shape": {"round": .75, "motion": .65, "density": .5, "spring": .8}},
    "cocoa":    {"axes": {"energy": .4, "playful": .3, "technical": .4, "serious": .5, "warm": .8, "formal": .6},
                 "shape": {"round": .3, "motion": .4, "density": .85, "spring": .3}},
    "graphite": {"axes": {"energy": .3, "playful": .2, "technical": .8, "serious": .7, "warm": .4, "formal": .8},
                 "shape": {"round": .2, "motion": .3, "density": .15, "spring": .15}},
    "midnight": {"axes": {"energy": .4, "playful": .3, "technical": .6, "serious": .8, "warm": .3, "formal": .9},
                 "shape": {"round": .4, "motion": .5, "density": .85, "spring": .4}},
    "mono":     {"axes": {"energy": .2, "playful": .1, "technical": .6, "serious": .8, "warm": .2, "formal": .8},
                 "shape": {"round": .1, "motion": .25, "density": .2, "spring": .1}},
    "brick":    {"axes": {"energy": .3, "playful": .3, "technical": .3, "serious": .5, "warm": .8, "formal": .7},
                 "shape": {"round": .25, "motion": .4, "density": .6, "spring": .3}},
    "honey":    {"axes": {"energy": .6, "playful": .6, "technical": .2, "serious": .3, "warm": .85, "formal": .3},
                 "shape": {"round": .5, "motion": .55, "density": .5, "spring": .6}},
    "mint":     {"axes": {"energy": .7, "playful": .7, "technical": .3, "serious": .2, "warm": .6, "formal": .25},
                 "shape": {"round": .8, "motion": .7, "density": .6, "spring": .8}},
    "violet":   {"axes": {"energy": .4, "playful": .5, "technical": .4, "serious": .4, "warm": .5, "formal": .5},
                 "shape": {"round": .6, "motion": .5, "density": .5, "spring": .6}},
    "coral":    {"axes": {"energy": .6, "playful": .65, "technical": .2, "serious": .25, "warm": .9, "formal": .3},
                 "shape": {"round": .7, "motion": .6, "density": .5, "spring": .7}},
    "olive":    {"axes": {"energy": .45, "playful": .35, "technical": .5, "serious": .5, "warm": .55, "formal": .5},
                 "shape": {"round": .45, "motion": .45, "density": .6, "spring": .45}},
    "espresso": {"axes": {"energy": .35, "playful": .3, "technical": .5, "serious": .7, "warm": .7, "formal": .8},
                 "shape": {"round": .4, "motion": .5, "density": .85, "spring": .4}},
}
# classic 만 CSS 블록이 없다(속성 미지정 시 :root 그대로). 나머지 id = themes.css 블록.
THEME_CSS_IDS = tuple(t for t in THEMES if t != "classic")

# 표지 변형 시그니처. id = assets/snippets/01-cover*.html 의 data-variant.
# 직접 설계 표지는 data-variant="custom" 또는 "custom-<짧은이름>" 을 쓴다 — 카탈로그
# id 가 아니므로 COVERS 에 넣지 않는다(TASK-cover-custom G3). 폴백은 COVERS 만 고른다.
COVER_CUSTOM = "custom"  # "custom" 또는 "custom-…" 접두로 시작하는 값 모두 직접 설계
COVERS = {
    "split":   {"axes": {"energy": .4, "playful": .3, "technical": .6, "serious": .5, "warm": .4, "formal": .8}},
    "center":  {"axes": {"energy": .3, "playful": .2, "technical": .4, "serious": .6, "warm": .4, "formal": .8}},
    "bigstat": {"axes": {"energy": .8, "playful": .6, "technical": .7, "serious": .4, "warm": .4, "formal": .5}},
    "diagram": {"axes": {"energy": .5, "playful": .4, "technical": .8, "serious": .4, "warm": .4, "formal": .6}},
    "stripes": {"axes": {"energy": .6, "playful": .7, "technical": .4, "serious": .3, "warm": .5, "formal": .4}},
    "mosaic":  {"axes": {"energy": .6, "playful": .6, "technical": .5, "serious": .3, "warm": .6, "formal": .4}},
    # TASK-cover-rework: 사용자 시안 10종 등재(manifest 권장 맥락 → 축 매핑)
    "editorial-lab":   {"axes": {"energy": .4, "playful": .3, "technical": .5, "serious": .6, "warm": .5, "formal": .7}},
    "bold-poster":     {"axes": {"energy": .9, "playful": .7, "technical": .3, "serious": .2, "warm": .5, "formal": .2}},
    "blueprint":       {"axes": {"energy": .4, "playful": .3, "technical": .9, "serious": .5, "warm": .3, "formal": .6}},
    "monograph":       {"axes": {"energy": .2, "playful": .2, "technical": .3, "serious": .8, "warm": .5, "formal": .9}},
    "learning-path":   {"axes": {"energy": .6, "playful": .6, "technical": .4, "serious": .3, "warm": .7, "formal": .4}},
    "paper-collage":   {"axes": {"energy": .7, "playful": .9, "technical": .2, "serious": .2, "warm": .8, "formal": .2}},
    "workbook-notes":  {"axes": {"energy": .5, "playful": .7, "technical": .4, "serious": .3, "warm": .7, "formal": .3}},
    "future-portal":   {"axes": {"energy": .7, "playful": .4, "technical": .7, "serious": .6, "warm": .4, "formal": .5}},
    "bauhaus":         {"axes": {"energy": .6, "playful": .7, "technical": .5, "serious": .4, "warm": .4, "formal": .5}},
    "modular-cards":   {"axes": {"energy": .5, "playful": .4, "technical": .7, "serious": .5, "warm": .4, "formal": .6}},
}

# 줄거리(arc) 시그니처와 첫 장 규칙. opens = 표지 다음에 올 수 있는 아키타입(check_deck 흐름 규칙).
ARCS = {
    "standard":   {"opens": ("agenda",),
                   "axes": {"energy": .5, "playful": .3, "technical": .5, "serious": .5, "warm": .5, "formal": .5}},
    "hook":       {"opens": ("statement",),
                   "axes": {"energy": .8, "playful": .4, "technical": .4, "serious": .7, "warm": .4, "formal": .5}},
    "case-first": {"opens": ("worked-example", "mock-legend", "before-after"),
                   "axes": {"energy": .5, "playful": .4, "technical": .3, "serious": .4, "warm": .9, "formal": .4}},
    "warmup":     {"opens": ("quiz-ox", "quiz-ab", "quiz-sort", "check"),
                   "axes": {"energy": .7, "playful": .8, "technical": .55, "serious": .2, "warm": .5, "formal": .3}},
    "follow":     {"opens": ("sequence", "build-up", "frame-form", "mock-legend"),
                   "axes": {"energy": .4, "playful": .3, "technical": .9, "serious": .5, "warm": .4, "formal": .6}},
    "contrast":   {"opens": ("before-after", "compare-2", "compare-table"),
                   "axes": {"energy": .5, "playful": .4, "technical": .55, "serious": .5, "warm": .4, "formal": .5}},
}

# 스타일 프리셋 시그니처. id = shared/presets/*.yaml (style_preset.py --list) 16종과 1:1.
# 각 프리셋의 genre·intent·use·avoid 를 6축(AXES) 위치로 매핑한다(선택적 오버레이 제안).
PRESETS = {
    "alpine-forest":   {"axes": {"energy": .65, "playful": .35, "technical": .45, "serious": .7,  "warm": .55, "formal": .55}},
    "atelier-sand":    {"axes": {"energy": .75, "playful": .7,  "technical": .35, "serious": .25, "warm": .75, "formal": .3}},
    "blueprint-grid":  {"axes": {"energy": .35, "playful": .2,  "technical": .95, "serious": .65, "warm": .2,  "formal": .75}},
    "campus-chalk":    {"axes": {"energy": .45, "playful": .55, "technical": .55, "serious": .35, "warm": .65, "formal": .4}},
    "civic-ochre":     {"axes": {"energy": .6,  "playful": .45, "technical": .5,  "serious": .55, "warm": .65, "formal": .65}},
    "clinical-trust":  {"axes": {"energy": .4,  "playful": .15, "technical": .8,  "serious": .9,  "warm": .35, "formal": .8}},
    "cyber-obsidian":  {"axes": {"energy": .6,  "playful": .3,  "technical": .9,  "serious": .85, "warm": .2,  "formal": .65}},
    "executive-navy":  {"axes": {"energy": .35, "playful": .15, "technical": .65, "serious": .8,  "warm": .25, "formal": .95}},
    "fintech-emerald": {"axes": {"energy": .45, "playful": .25, "technical": .85, "serious": .65, "warm": .3,  "formal": .85}},
    "hanji-warm":      {"axes": {"energy": .3,  "playful": .35, "technical": .25, "serious": .45, "warm": .85, "formal": .55}},
    "legal-charcoal":  {"axes": {"energy": .25, "playful": .1,  "technical": .6,  "serious": .95, "warm": .2,  "formal": .95}},
    "mono-swiss":      {"axes": {"energy": .4,  "playful": .3,  "technical": .5,  "serious": .6,  "warm": .3,  "formal": .75}},
    "museum-archive":  {"axes": {"energy": .35, "playful": .25, "technical": .4,  "serious": .55, "warm": .7,  "formal": .7}},
    "nordic-slate":    {"axes": {"energy": .35, "playful": .25, "technical": .75, "serious": .55, "warm": .35, "formal": .7}},
    "pastel-studio":   {"axes": {"energy": .6,  "playful": .65, "technical": .3,  "serious": .3,  "warm": .9,  "formal": .35}},
    "seoul-editorial": {"axes": {"energy": .45, "playful": .35, "technical": .4,  "serious": .55, "warm": .6,  "formal": .8}},
}

WEAK_REASON = "톤 신호어가 약해 제목 기준으로 순서를 돌렸습니다(같은 제목은 항상 같은 결과)"


class RouterError(ValueError):
    """입력이 비어 있거나 후보 집합이 어긋난 경우."""


def _jitter(title, key, seed):
    """제목·키·시드에서 0..JITTER 사이 결정적 수를 만든다."""
    digest = hashlib.sha256(f"{seed}|{title}|{key}".encode("utf-8")).digest()
    return (int.from_bytes(digest[:4], "big") / 0xFFFFFFFF) * JITTER


def _count(words, fields):
    """필드별 신호어 적중을 가중 합산하고 적중한 단어를 모은다."""
    score, hits = 0.0, []
    for word in words:
        for name, text in fields.items():
            if text and word in text:
                score += FIELD_WEIGHT[name]
                if word not in hits:
                    hits.append(word)
    return score, hits


def axes(title, outcomes="", audience="", extra=""):
    """요청 텍스트에서 톤 축 6개(0..1)를 계산한다. 축 신호어가 하나도 없으면 0.5."""
    fields = {"title": title, "outcomes": outcomes, "audience": audience, "extra": extra}
    out, hits = {}, {}
    for name in AXES:
        lo, hi = AXIS_SIGNALS[name]
        lo_score, lo_hits = _count(lo, fields)
        hi_score, hi_hits = _count(hi, fields)
        out[name] = round(min(1.0, max(0.0, 0.5 + AXIS_STEP * (hi_score - lo_score))), 3)
        hits[name] = {"hi": hi_hits, "lo": lo_hits}
    return out, hits


def _score(table, ax, title, kind, recent, seed, jit_scale=1.0):
    """후보별 축 거리 점수 + 지터 − 최근 감점. 축 거리는 전체 폭 6 의 역수로 환산한다.
    jit_scale: 신호가 있으면 지터를 줄여 거리 우위가 이기게 하고(0.25),
    신호가 없을 때만(1.0) 제목 해시가 순서를 돌린다."""
    rows = []
    for key, spec in table.items():
        dist = sum(abs(ax[a] - spec["axes"][a]) for a in AXES)
        total = (len(AXES) - dist) + _jitter(title, f"{kind}:{key}", seed) * jit_scale
        penalty = RECENT_PENALTY if key in recent else 0.0
        rows.append({"id": key, "score": round(total - penalty, 3), "recent_penalty": bool(penalty)})
    rows.sort(key=lambda r: (-r["score"], r["id"]))
    return rows


def route(title, outcomes="", audience="", extra="", seed="0",
          recent_theme=(), recent_cover=(), recent_arc=(), recent_preset=()):
    """축을 계산해 테마·표지·arc·스타일 프리셋 후보 3종·추천을 반환한다."""
    if not (title or "").strip():
        raise RouterError("title 이 비어 있습니다")
    for label, table, recent in (
        ("theme", THEMES, recent_theme),
        ("cover", COVERS, recent_cover),
        ("arc", ARCS, recent_arc),
        ("preset", PRESETS, recent_preset),
    ):
        bad = [r for r in recent if r not in table]
        if bad:
            raise RouterError(f"--recent-{label} 에 알 수 없는 id: {', '.join(bad)}")
    ax, hits = axes(title, outcomes, audience, extra)
    signal_words = sorted({w for h in hits.values() for pair in h.values() for w in pair})
    result = {"title": title, "seed": seed, "axes": ax, "signals": signal_words,
              "weak_signal": not signal_words}
    jit_scale = 1.0 if not signal_words else 0.25
    for kind, table in (("theme", THEMES), ("cover", COVERS), ("arc", ARCS)):
        recent = {"theme": recent_theme, "cover": recent_cover, "arc": recent_arc}[kind]
        rows = _score(table, ax, title, kind, recent, seed, jit_scale)
        top = rows[:3]
        for row in top:
            near = sorted(AXES, key=lambda a: abs(ax[a] - table[row["id"]]["axes"][a]))[:3]
            row["because"] = (f"축 근접: {', '.join(near)}" +
                              (" (최근 사용이라 감점)" if row["recent_penalty"] else ""))
        result[kind] = {"recommend": top[0]["id"],
                        "candidates": [{"id": r["id"], "score": r["score"], "because": r["because"]} for r in top]}
    preset_rows = _score(PRESETS, ax, title, "preset", recent_preset, seed, jit_scale)
    preset_top = preset_rows[:3]
    sig_note = f" · 신호어: {', '.join(signal_words)}" if signal_words else " · 신호어 없음(제목 해시)"
    for row in preset_top:
        near = sorted(AXES, key=lambda a: abs(ax[a] - PRESETS[row["id"]]["axes"][a]))[:3]
        row["because"] = (f"선택적 오버레이 제안 — 축 근접: {', '.join(near)}{sig_note}" +
                          (" (최근 사용이라 감점)" if row["recent_penalty"] else ""))
    result["preset"] = {"recommend": preset_top[0]["id"],
                        "candidates": [{"id": r["id"], "score": r["score"], "because": r["because"]} for r in preset_top]}
    if not signal_words:
        result["note"] = WEAK_REASON
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="요청 텍스트로 legacy 테마·표지·arc·스타일 프리셋 후보 3종·추천을 계산한다")
    ap.add_argument("--title", required=True, help="덱 제목 또는 주제")
    ap.add_argument("--outcomes", default="", help="교육 뒤 청중이 할 수 있어야 하는 것(문장 이어 붙임)")
    ap.add_argument("--audience", default="", help="청중 설명")
    ap.add_argument("--extra", default="", help="그 밖의 요청 문장(형식·분위기 요청 등)")
    ap.add_argument("--recent-theme", action="append", default=[], metavar="ID", help="최근 쓴 테마(감점)")
    ap.add_argument("--recent-cover", action="append", default=[], metavar="ID", help="최근 쓴 표지 변형(감점)")
    ap.add_argument("--recent-arc", action="append", default=[], metavar="ID", help="최근 쓴 arc(감점)")
    ap.add_argument("--recent-preset", action="append", default=[], metavar="ID", help="최근 쓴 스타일 프리셋(감점)")
    ap.add_argument("--seed", default="0", help="같은 입력으로 다른 변주를 원할 때 바꾼다")
    args = ap.parse_args(argv)
    try:
        result = route(args.title, args.outcomes, args.audience, args.extra, args.seed,
                       args.recent_theme, args.recent_cover, args.recent_arc, args.recent_preset)
    except RouterError as e:
        print(f"ERROR  {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
