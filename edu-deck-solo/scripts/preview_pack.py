#!/usr/bin/env python3
"""edu-deck-solo 팩 시안 프리뷰 생성기 (지시문 P1-3).

[파일 목적]
  팩 후보 3종 × 2장(표지 + 대표 장)을 한 파일 preview.html 로 묶어 사용자가 눈으로 고르게 한다.
  말로 정의하기 어려운 취향을 세 시안 비교로 검증하는 품질 장치다. preview.html 은
  check_deck.py 경량 검사(정적 + 넘침)를 통과한 것만 사용자에게 제시한다.

[주요 흐름] (make)
  1. 후보 3종(팩 ID + 청중·수행 행동 근거)과 추천 1종, 표지·대표 장 내용을 받는다.
  2. 각 팩 template.html 의 {{TITLE}}…{{ACTION}} 여섯 토큰에 같은 내용을 넣어 세 디자인으로
     같은 콘텐츠를 보여 준다(비교가 목적이므로). 섹션 클래스 pack/pack-{design} 은
     pv/pv-{design} 으로 바꾸고 CSS 셀렉터도 같은 규칙으로 변환한다 — check_deck 의
     단일 팩 메타데이터 계약(덱 전체가 한 디자인)은 완성 덱용이므로 프리뷰가 충돌하지 않게 한다.
     내용 클래스(.pack-prompt 등)와 팩 CSS 본문은 그대로 써서 실물 팩 모습을 유지한다.
  3. 앞뒤로 안내 장(agenda)·선택 요청 장(closing)을 붙여 8장짜리 프리뷰 덱을 pack-shell.html 로 조립한다.
  4. check_deck.py 를 실행해 정적+넘침 검사를 통과해야 성공으로 보고한다(통과 못 하면 제시 금지).
[주요 흐름] (record)
  사용자 선택(또는 무응답 시 추천)을 deck.json 에 기록한다. 선택 자체는 resource_pack.design 에,
  선택 이유·후보·경로는 resource_pack_choice 키에 남긴다(resource_pack 객체는
  validate_selection 이 design/flow/activities 만 허용하므로 이유를 그 안에 넣지 않는다).

[외부 연결]
  입력: edu-deck/shared 의 pack-shell.html·packs/{design}/template.html·style.css·base.css·
  pack-runtime.css·css/tokens.css·packs/flows.json·packs/catalog.json, 선택 콘텐츠 JSON.
  게이트: edu-deck/shared/scripts/check_deck.py (서브프로세스). 정적만(--no-render)이거나
  화면만(--render-only) 돌리는 모드는 넘침이나 정적 검사를 통째로 건너뛰므로, 정적+넘침을
  모두 포함하는 최소 조합은 옵션 출력(--sheets/--shots) 없는 기본 실행이다.
  표준 라이브러리만 쓴다(설치 없이 어디서나 실행).

[수정시 주의]
  템플릿 토큰·이스케이프 계약은 scripts/resource_packs.py init 과 같다(값은 평문, 태그 금지).
  CSS 변환 규칙(.pack→.pv, .pack-{design}→.pv-{design})을 바꾸면 check_deck 의
  PACK_CONTAINER_SEL 박스 검사 대상(내용 클래스)과 어긋나지 않는지 확인한다.
"""
import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

SHARED = Path(__file__).resolve().parents[2] / "edu-deck" / "shared"  # 테스트가 덮어쓴다
sys.path.insert(0, str(SHARED / "scripts"))

from resource_packs import DESIGNS, FLOWS, PackError, load_flow, validate_selection  # noqa: E402

PREVIEW_NAME = "preview.html"
CANDIDATES_NAME = "preview-candidates.json"
CHECK_JSON = "qa/preview-check.json"
TOKEN_RE = re.compile(r"\{\{([A-Z_]+)\}\}")
DESIGN_ALT = "|".join(DESIGNS)
# check_deck 정적 검사 기준: 노트 110~450자, 제목 30자, 화면 글자 320자(composition.md 6절·expression.md 2절)
GUIDE_VISIBLE_BODY_MAX = 60  # 안내 장에 보이는 근거는 한 문장으로, 전문은 노트·JSON 에 남긴다

PREVIEW_CSS = """
/* ---- preview_pack.py 안내 장(closing·agenda) 전용 ---- */
.slide.pv-guide{gap:28px}
.pv-guide-head{border-top:2px solid var(--ink);padding-top:24px}
.pv-cands{list-style:none;margin:0;padding:0;display:grid;gap:20px}
.pv-cand{display:grid;grid-template-columns:72px 1fr;gap:24px;align-items:start;
  border:2px solid var(--line);border-radius:var(--r2);padding:24px 28px;background:var(--paper)}
.pv-chip{font-size:30px;font-weight:900;color:var(--paper);background:var(--accent);
  width:64px;height:64px;border-radius:var(--r2);display:flex;align-items:center;justify-content:center}
.pv-cand b{font-size:29px;font-weight:750;display:block;margin-bottom:8px}
.pv-cand .pack-body{font-size:27px;line-height:1.5}
.pv-tag{font-size:21px;font-weight:700;font-style:normal;color:var(--paper);background:var(--accent);
  border-radius:var(--r1);padding:2px 12px;margin-left:12px;vertical-align:middle}
.pv-swatches{width:100%;height:56px;display:block}
.pv-help{font-size:26px;line-height:1.5;color:var(--soft)}
"""


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class PreviewError(ValueError):
    """프리뷰를 만들 수 없는 입력 오류. 사용자가 고칠 위치를 알 수 있게 쓴다."""


# ---------------------------------------------------------------- 입력 정리
def parse_packs(pack_flags, because_flags):
    """--pack ID --because 근거 쌍을 (design, reason) 목록으로 검증한다."""
    if len(pack_flags) != len(because_flags):
        raise PreviewError("--pack 과 --because 는 쌍으로, 후보 3종만 넣으세요")
    if len(pack_flags) != 3:
        raise PreviewError(f"팩 후보는 정확히 3종이어야 합니다 (지금 {len(pack_flags)}종)")
    out, seen = [], set()
    for design, reason in zip(pack_flags, because_flags):
        if design not in DESIGNS:
            raise PreviewError(f"알 수 없는 팩: {design} (가능: {', '.join(DESIGNS)})")
        if design in seen:
            raise PreviewError(f"팩 후보가 중복되었습니다: {design}")
        seen.add(design)
        reason = reason.strip()
        if not reason:
            raise PreviewError(f"{design} 후보의 근거(--because)가 비었습니다")
        out.append((design, reason))
    return out


def first_sentence(text: str, limit: int = GUIDE_VISIBLE_BODY_MAX) -> str:
    """안내 장에 보일 근거 한 문장. 전문은 노트·preview-candidates.json 에 남긴다."""
    text = re.sub(r"\s+", " ", text).strip()
    cut = re.search(r"[.?!]", text)
    head = text[:cut.end()] if cut else text
    return head if len(head) <= limit else head[: limit - 1] + "…"


def load_content(path):
    """--content JSON(cover/rep 각 prompt·body·evidence·action 선택 키)을 읽는다."""
    if not path:
        return {"cover": {}, "rep": {}}
    try:
        data = json.loads(read_utf8(Path(path)))
    except (OSError, json.JSONDecodeError) as e:
        raise PreviewError(f"--content 파일을 읽을 수 없습니다: {e}")
    content = {}
    for key in ("cover", "rep"):
        block = data.get(key, {}) if isinstance(data, dict) else {}
        if not isinstance(block, dict):
            raise PreviewError(f"--content 의 '{key}' 은 객체여야 합니다")
        content[key] = {k: v for k, v in block.items()
                        if k in ("prompt", "body", "evidence", "action") and isinstance(v, str)}
    return content


# ---------------------------------------------------------------- 슬라이드 조립
def substitute_tokens(template: str, values: dict) -> str:
    """{{TOKEN}} 여섯 자리를 이스케이프된 평문으로 채운다(resource_packs.init 과 같은 계약)."""
    def replace(match):
        key = match.group(1)
        return html.escape(values[key]) if key in values else match.group(0)
    rendered = TOKEN_RE.sub(replace, template)
    left = TOKEN_RE.search(rendered)
    if left:
        raise PreviewError(f"템플릿 토큰 {left.group(0)} 에 넣을 값이 없습니다")
    return rendered


def retag_section(rendered: str, design: str, archetype) -> str:
    """섹션 태그를 프리뷰용으로 바꾼다: 클래스 pack→pv, data-design 제거, 아키타입 지정.

    check_deck 의 리소스팩 계약은 '덱 전체가 한 디자인'을 요구하므로, 세 디자인을 함께 보는
    프리뷰는 팩 경로가 아닌 일반 슬라이드로 검사받는다. 내용 클래스(.pack-*)는 그대로 둬서
    팩 CSS·렌더 박스 검사 대상이 실물 팩과 같게 유지한다. archetype=None 이면
    템플릿이 원래 가진 data-archetype(실물 팩 덱과 같은 값)을 그대로 쓴다.
    """
    m = re.search(r"<section\b[^>]*>", rendered)
    if not m:
        raise PreviewError("팩 템플릿에 <section> 이 없습니다")
    tag = m.group(0)
    classes = []
    for cls in re.findall(r'([\w-]+)', re.search(r'class="([^"]*)"', tag).group(1)):
        if cls == "pack":
            cls = "pv"
        elif cls == f"pack-{design}":
            cls = f"pv-{design}"
        classes.append(cls)
    new_tag = re.sub(r'\s*data-design="[^"]*"', "", tag)
    if archetype is not None:
        if 'data-archetype="' in new_tag:
            new_tag = re.sub(r'data-archetype="[^"]*"', f'data-archetype="{archetype}"', new_tag, count=1)
        else:
            new_tag = new_tag[:-1] + f' data-archetype="{archetype}">'
    new_tag = re.sub(r'class="[^"]*"', 'class="' + " ".join(classes) + '"', new_tag, count=1)
    return rendered[:m.start()] + new_tag + rendered[m.end():]


def append_note(rendered: str, extra_lines):
    """템플릿 노트 뒤에 후보 근거를 덧붙인다(노트 110~450자 권장에 맞춘다)."""
    addition = "\n".join(extra_lines)
    if addition:
        addition += "\n"
    return re.sub(r"(?s)(<aside class=\"notes\">.*?)(</aside>)",
                  lambda m: m.group(1) + html.escape(addition), rendered, count=1)


def pack_slide(design, archetype, kicker, values, reason, recommend_note):
    """팩 템플릿 한 장을 프리뷰 슬라이드로 렌더한다."""
    template = read_utf8(SHARED / "assets" / "packs" / design / "template.html")
    rendered = substitute_tokens(template, {**values, "KICKER": kicker})
    rendered = retag_section(rendered, design, archetype)
    note_lines = ["", f"후보 근거: {reason}"] + ([recommend_note] if recommend_note else [])
    return append_note(rendered, note_lines)


# ---------------------------------------------------------------- 안내 장
def guide_agenda_slide(title, candidates, recommend, design_meta):
    """선택 안내 장: 후보 3종·근거 한 문장·추천 표시·색 견본을 한 화면에 둔다."""
    sw = []
    for idx, (letter, (design, _)) in enumerate(zip("ABC", candidates)):
        accent = design_meta[design].get("accent", "#333333")
        x = idx * 640
        sw.append(f'<rect x="{x}" y="8" width="600" height="40" rx="8" fill="{accent}"/>'
                  f'<text x="{x + 24}" y="38" font-size="28" font-weight="700" '
                  f'fill="#fffdf8">{letter} · {html.escape(design)}</text>')
    items = []
    for letter, (design, reason) in zip("ABC", candidates):
        tag = '<em class="pv-tag">추천</em>' if design == recommend else ""
        name = html.escape(design_meta[design]["name"])
        items.append(
            f'<li class="pv-cand"><span class="pv-chip">{letter}</span>'
            f'<div><b>{letter} · {html.escape(design)} · {name}{tag}</b>'
            f'<p class="pack-body">{html.escape(first_sentence(reason))}</p></div></li>')
    note = ("프리뷰 안내 장입니다. 세 후보 팩을 같은 내용의 표지와 대표 장으로 나란히 보여 드립니다. "
            + " ".join(f"{d} 근거: {r}" for d, r in candidates)
            + f" 추천 후보는 {recommend} 입니다. 사용자가 고르면 그 팩으로, 무응답이면 추천 후보로 진행합니다.")
    return f"""<section class="slide pv pv-guide" data-archetype="agenda">
  <header class="pack-topline"><p class="pack-topic">{html.escape(title)}</p><span class="pack-mark">PACK PREVIEW</span></header>
  <div class="pv-guide-head"><p class="pack-kicker">팩 시안 선택</p>
    <h1 class="pack-prompt">세 후보 중 어느 모습으로 만들까요?</h1></div>
  <svg class="pv-swatches" viewBox="0 0 1920 56" role="img" aria-label="후보 팩 강조색 견본">{''.join(sw)}</svg>
  <ul class="pv-cands">{''.join(items)}</ul>
  <footer class="pack-footer pack-hint">→ · ← 로 여섯 장을 돌아보고 팩 이름이나 A/B/C 로 답해 주세요.</footer>
  <aside class="notes">{html.escape(note)}</aside>
</section>"""


def guide_closing_slide(title, candidates, recommend, design_meta):
    """선택 요청 장: 답하는 방법과 무응답 시 추천 진행 규칙을 안내한다."""
    roster = " · ".join(f"{l} {d}({design_meta[d]['name']})" for l, (d, _) in zip("ABC", candidates))
    body = (f"후보: {roster}. 팩 이름이나 A/B/C 로 답해 주세요. "
            f"답이 없으면 추천 후보 {recommend}({design_meta[recommend]['name']})로 진행하고 근거를 보고합니다.")
    note = ("선택 요청 장입니다. 사용자 선택은 preview_pack.py record 로 deck.json 의 resource_pack.design 에 기록하고, "
            "선택 이유·후보·추천 경위는 resource_pack_choice 키에 남깁니다. 무응답으로 추천으로 진행할 때도 같은 형식으로 기록합니다.")
    return f"""<section class="slide pv pv-guide" data-archetype="closing">
  <header class="pack-topline"><p class="pack-topic">{html.escape(title)}</p><span class="pack-mark">PACK PREVIEW</span></header>
  <div class="pv-guide-head"><p class="pack-kicker">선택</p>
    <h1 class="pack-prompt">어느 팩으로 만들까요?</h1></div>
  <p class="pack-body">{html.escape(body)}</p>
  <footer class="pack-footer pack-hint">선택과 이유는 deck.json(resource_pack · resource_pack_choice)에 기록됩니다.</footer>
  <aside class="notes">{html.escape(note)}</aside>
</section>"""


# ---------------------------------------------------------------- CSS·셸 조립
def transform_css(css: str) -> str:
    """섹션 클래스 변환에 맞춰 CSS 셀렉터를 바꾼다. 내용 클래스(.pack-prompt 등)는 건드리지 않는다."""
    css = re.sub(r"\.pack-(%s)(?![\w-])" % DESIGN_ALT, r".pv-\1", css)
    return re.sub(r"\.pack(?![\w-])", ".pv", css)


def pack_token_overrides(designs):
    """tokens.css 에서 선택한 팩의 색 오버라이드만 뽑아 pv 클래스로 바꾼다."""
    tokens = read_utf8(SHARED / "assets" / "css" / "tokens.css")
    blocks = []
    for design in designs:
        m = re.search(r"\.slide\.pack-%s\{[^}]*\}" % design, tokens)
        if m:
            blocks.append(m.group(0))
    return transform_css("\n".join(blocks))


def collect_css(designs):
    """팩 런타임·공용 기본·선택 팩 스타일·토큰 오버라이드·안내 장 CSS를 한 덩어로 묶는다."""
    assets = SHARED / "assets"
    parts = [assets / "css" / "pack-runtime.css", assets / "packs" / "base.css"]
    parts += [assets / "packs" / d / "style.css" for d in designs]
    css = "\n".join(f"/* ---- {p.name}({p.parent.name}) ---- */\n" + transform_css(read_utf8(p)) for p in parts)
    return css + "\n/* ---- pack token overrides (tokens.css) ---- */\n" + pack_token_overrides(designs) + PREVIEW_CSS


def assemble(title, slides_html, css):
    """pack-shell.html 표식 5곳을 채운다(표식 계약은 build_deck.MARK_* 와 같은 문자열)."""
    shell = read_utf8(SHARED / "assets" / "pack-shell.html")
    fills = {"{{TITLE}}": html.escape(f"{title} — 팩 시안 프리뷰"),
             "/*EXTRA_CSS*/": css,
             "<!--ICONS-->": "",
             "<!--SLIDES-->": slides_html,
             "<!--STUDY_DATA-->": ""}
    for mark, value in fills.items():
        if shell.count(mark) != 1:
            raise PreviewError(f"셸 표식 '{mark}' 이 정확히 1번 있어야 합니다")
        shell = shell.replace(mark, value)
    return shell


def stage_values(flow_data, stage_no):
    """대표 장으로 쓸 흐름 단계 값을 꺼낸다(resource_packs.init 과 같은 형태)."""
    stages = flow_data["stages"]
    if not 1 <= stage_no <= len(stages):
        raise PreviewError(f"--stage {stage_no} 범위 밖(1~{len(stages)})")
    stage = stages[stage_no - 1]
    if isinstance(stage, str):
        stage = {"title": stage}
    return stage


def make_preview(folder, title, flow, stage_no, candidates, recommend, content, gate_args=None):
    """preview.html·preview-candidates.json 을 만들고 경량 검사(정적+넘침) 게이트를 돌린다.

    gate_args: 게이트에 쓸 check_deck 인자(기본 없음 = 정적+화면 모두). 단위 테스트가
    --no-render 로 정적 게이트만 돌릴 때 쓴다. 게이트는 check_deck 종료 코드 0(RESULT PASS)을
    요구하고, 3(화면 검사 못 함)도 '넘침을 증명 못 했다'로 실패 처리한다 — 통과분만 제시한다.
    """
    catalog = json.loads(read_utf8(SHARED / "assets" / "packs" / "catalog.json"))
    meta = {d["id"]: d for d in catalog["designs"]}
    tokens_css = read_utf8(SHARED / "assets" / "css" / "tokens.css")
    design_meta = {}
    for design, _ in candidates:
        override = re.search(r"\.slide\.pack-%s\{([^}]*)\}" % design, tokens_css)
        accent = "#333333"
        if override:
            m = re.search(r"--accent:\s*(#[0-9a-fA-F]{3,8})", override.group(1))
            if m:
                accent = m.group(1)
        design_meta[design] = {"name": meta[design]["name"], "accent": accent}
    flow_data = load_flow(SHARED / "assets" / "packs", flow)
    stage = stage_values(flow_data, stage_no)
    designs = [d for d, _ in candidates]

    cover_defaults = {"PROMPT": title,
                      "BODY": stage.get("body", title) or title,
                      "EVIDENCE": stage.get("evidence", ""),
                      "ACTION": stage.get("action", "")}
    cover_values = {**{k: v for k, v in cover_defaults.items() if v},
                    **{k.upper(): v for k, v in content["cover"].items()}}
    rep_values = {"PROMPT": stage.get("prompt", title), "BODY": stage.get("body", ""),
                  "EVIDENCE": stage.get("evidence", ""), "ACTION": stage.get("action", ""),
                  **{k.upper(): v for k, v in content["rep"].items()}}

    slides = [guide_agenda_slide(title, candidates, recommend, design_meta)]
    for design, reason in candidates:
        recommend_note = f"추천 후보입니다(무응답 시 이 팩으로 진행)." if design == recommend else ""
        values = {"TITLE": title, **cover_values}
        slides.append(pack_slide(design, "cover", f"표지 · {design_meta[design]['name']}",
                                 values, reason, recommend_note))
        values = {"TITLE": title, **rep_values}
        slides.append(pack_slide(design, None, f"대표 장 · {stage.get('title', flow)}",
                                 values, reason, recommend_note))
    slides.append(guide_closing_slide(title, candidates, recommend, design_meta))

    html_text = assemble(title, "\n".join(slides), collect_css(designs))
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    preview = folder / PREVIEW_NAME
    preview.write_text(html_text, encoding="utf-8")

    spec = {"title": title, "flow": flow, "representative_stage": stage_no,
            "recommend": recommend,
            "candidates": [{"design": d, "reason": r} for d, r in candidates]}
    (folder / CANDIDATES_NAME).write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ok, result_line = run_gate(preview, folder, gate_args or [])
    return ok, result_line, preview


def run_gate(preview: Path, folder: Path, extra_args):
    """check_deck 경량 검사. 정적+넘침을 모두 담는 최소 인자 조합은 옵션 없는 기본 실행이다."""
    checker = SHARED / "scripts" / "check_deck.py"
    json_out = folder / CHECK_JSON
    cmd = [sys.executable, str(checker), str(preview), "--json", str(json_out), *extra_args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    result_line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT:")), proc.stdout.strip()[-200:])
    if proc.returncode != 0:
        print(proc.stdout)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        print(f"ERROR  경량 검사 미통과({proc.returncode}) — preview.html 을 사용자에게 제시하지 않습니다. 고칠 것은 슬라이드다.",
              file=sys.stderr)
        return False, result_line
    print(proc.stdout.strip())
    return True, result_line


# ---------------------------------------------------------------- 선택 기록
def record_choice(folder, design, reason, by, recommended):
    """deck.json 에 선택을 기록한다. resource_pack.design = 선택, resource_pack_choice = 근거·후보.

    resource_pack 객체는 build_deck·resource_packs 의 validate_selection 계약상
    design/flow/activities 키만 허용하므로, 이유는 형제 키 resource_pack_choice 에 남긴다.
    """
    deck_path = Path(folder) / "deck.json"
    if not deck_path.is_file():
        raise PreviewError(f"{deck_path} 이 없습니다. resource_packs.py init 으로 먼저 만드세요")
    cfg = json.loads(read_utf8(deck_path))
    pack = cfg.get("resource_pack")
    if not isinstance(pack, dict):
        raise PreviewError("deck.json.resource_pack 이 없습니다. 팩 시안 선택은 새 팩 덱(4단계 init 뒤)에 기록합니다")
    pack["design"] = design
    try:
        cfg["resource_pack"] = validate_selection(pack)
    except PackError as e:
        raise PreviewError(f"선택 후 resource_pack 이 무효입니다: {e}")
    candidates = []
    cand_path = Path(folder) / CANDIDATES_NAME
    if cand_path.is_file():
        spec = json.loads(read_utf8(cand_path))
        candidates = [{"design": c["design"], "reason": c["reason"]} for c in spec.get("candidates", [])]
    if by == "default" and not recommended:
        raise PreviewError("무응답 추천 진행(--by default)은 --recommended(추천 팩)와 함께 알립니다")
    cfg["resource_pack_choice"] = {
        "design": design,
        "reason": reason,
        "by": by,
        **({"recommended": recommended} if recommended else {}),
        **({"candidates": candidates} if candidates else {}),
        "preview": PREVIEW_NAME,
    }
    deck_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return deck_path


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="팩 후보 3종 프리뷰(preview.html) 생성·기록 (지시문 P1-3)")
    sub = ap.add_subparsers(dest="command", required=True)
    mk = sub.add_parser("make", help="후보 3종 × 2장 preview.html 생성 + 경량 검사 게이트")
    mk.add_argument("folder", help="작업 폴더(preview.html·qa/ 가 만들어진다)")
    mk.add_argument("--title", required=True, help="덱 제목(표지 PROMPT 로도 쓴다)")
    mk.add_argument("--pack", action="append", default=[], metavar="ID", help="후보 팩 ID (3번 반복)")
    mk.add_argument("--because", action="append", default=[], metavar="TEXT",
                    help="바로 앞 --pack 후보의 청중·수행 행동 근거 (3번 반복)")
    mk.add_argument("--recommend", required=True, help="추천 팩 ID (무응답 시 진행)")
    mk.add_argument("--flow", default="problem", choices=FLOWS, help="대표 장으로 보여 줄 흐름(기본 problem)")
    mk.add_argument("--stage", type=int, default=3, metavar="N", help="대표 장 흐름 단계 번호(기본 3)")
    mk.add_argument("--content", metavar="FILE",
                    help="표지·대표 장 내용 JSON {cover:{prompt,body,evidence,action}, rep:{…}} (없으면 흐름 초안값)")
    rc = sub.add_parser("record", help="사용자 선택(또는 추천 진행)을 deck.json 에 기록")
    rc.add_argument("folder", help="덱 작업 폴더(deck.json 이 있는 곳)")
    rc.add_argument("--design", required=True, choices=DESIGNS, help="선택된 팩")
    rc.add_argument("--reason", required=True, help="선택 이유(무응답 추천이면 추천 근거)")
    rc.add_argument("--by", choices=["user", "default"], default="user",
                    help="user=사용자가 골랐다, default=무응답으로 추천 진행했다")
    rc.add_argument("--recommended", help="무응답 추천 진행 시 추천했던 팩(--by default 필수)")
    args = ap.parse_args(argv)
    try:
        if args.command == "make":
            candidates = parse_packs(args.pack, args.because)
            if args.recommend not in {d for d, _ in candidates}:
                raise PreviewError(f"--recommend {args.recommend} 은 후보 3종 안에 있어야 합니다")
            content = load_content(args.content)
            ok, _, preview = make_preview(args.folder, args.title, args.flow, args.stage,
                                          candidates, args.recommend, content)
            if not ok:
                return 1
            print(f"OK     {preview} — 후보 {len(candidates)}종 × 2장, 경량 검사(정적+넘침) 통과. 사용자에게 제시하세요.")
            return 0
        record_choice(args.folder, args.design, args.reason, args.by, args.recommended)
    except (PreviewError, PackError, OSError) as e:
        print(f"ERROR  {e}", file=sys.stderr)
        return 1
    print(f"OK     {Path(args.folder) / 'deck.json'} — resource_pack.design={args.design}, "
          f"resource_pack_choice.by={args.by}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
