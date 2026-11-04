#!/usr/bin/env python3
"""edu-deck-series 시리즈 조립기.

[파일 목적]
  여러 편의 슬라이드 조각(각 편은 solo 절차대로 만든 src/*.html + deck.json)과 series.json 을
  합쳐 외부 파일이 하나도 필요 없는 단일 HTML 시리즈 포털(목차 + 편 전체)을 만든다.

[주요 흐름]
  1. series.json 을 읽어 제목·허브 유형(map|shelf|list)·편 목록을 정한다.
  2. 각 편 폴더의 src/*.html 을 순서로 읽어 편 안의 id 에 e<편>- 접두를 붙인다(편끼리 id 가 겹치지 않게).
     공용 아이콘(#i-…)은 편 안에서 정의한 적이 없어 그대로 둔다.
  3. 각 슬라이드 머리에 목차 복귀 칩(.sr, 편 라벨)을 심는다.
  4. hub.type 에 맞춰 목차 DOM(경로/책장/목록)을 만든다.
  5. dev/portal_template.html 의 표식(TITLE, CORE_CSS, EXTRA_CSS, ICONS, HUB, EPISODES,
     STUDY_DATA, STUDY_JS)을 채운다. 자습 레이어는 shared assets/js/study.js 를 그대로 넣는다.

[외부 연결]
  입력: <폴더>/series.json, <폴더>/<편.folder>/{deck.json,src/*.html},
        shared 자산(shell.html, components.css, icons/*.svg, js/study.js)
  출력: <폴더>/<series.json output 또는 제목>.html

[사용법]
  python3 build_series.py <시리즈 폴더> [--hub map|shelf|list] [--out 결과.html]

[수정시 주의]
  편 조각은 solo 조립기(build_deck.py)와 같은 문법이다. 편마다 deck.json 이 있어
  편 하나만 단독 덱으로도 발행할 수 있다. 표식 이름을 바꾸면 portal_template.html 과 함께 고친다.
"""
import argparse
import json
import re
import sys
from html import escape
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent        # edu-deck-series
SHARED = SKILL_DIR.parent / "edu-deck" / "shared"          # 공통 자산(라우터 스킬 안)
TEMPLATE = SKILL_DIR / "dev" / "portal_template.html"

sys.path.insert(0, str(SHARED / "scripts"))
from resource_packs import PackError, validate_selection
from build_deck import collect_css
from visual_assets import common_css, motion_js

HUB_TYPES = ("map", "shelf", "list")


class BuildError(Exception):
    pass


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise BuildError(f"{path.name} 이(가) 없습니다: {path}")
    except json.JSONDecodeError as e:
        raise BuildError(f"{path.name} JSON 읽기 실패: {e}")


def frag_sort_key(p):
    m = re.match(r"^(\d+)", p.name)
    return (int(m.group(1)) if m else 10 ** 9, p.name)


# ---------------------------------------------------------------- 편 조각 전처리

def prefix_ids(html, ep):
    """편 안에서 정의한 id 에 e<편>- 접두를 붙이고, 그 id 를 가리키는 참조도 함께 바꾼다.

    공용 아이콘(#i-…)은 ICONS 꾸러미에서 정의되므로 편 안 정의 집합에 없어 영향받지 않는다.
    """
    defined = set(re.findall(r'id="([^"]+)"', html))
    if not defined:
        return html
    def rep_id(m):
        return f'id="e{ep}-{m.group(1)}"' if m.group(1) in defined else m.group(0)
    def rep_href(m):
        return f'{m.group(1)}#e{ep}-{m.group(2)}"' if m.group(2) in defined else m.group(0)
    html = re.sub(r'id="([^"]+)"', rep_id, html)
    html = re.sub(r'(href=")#([^"]+)"', rep_href, html)
    html = re.sub(r'(xlink:href=")#([^"]+)"', rep_href, html)
    html = re.sub(r'url\(#([\w-]+)\)', lambda m: f"url(#e{ep}-{m.group(1)})" if m.group(1) in defined else m.group(0), html)
    return html


def inject_sr(html, label, title):
    """각 슬라이드 머리에 목차 복귀 칩(.sr)을 넣는다. 칩은 단추라서 발표 엔진이 슬라이드를 넘기지 않는다."""
    chip = (
        '<button class="sr" type="button">'
        f'<span class="sr-ep">{escape(label)}</span><span class="sr-t">{escape(title)}</span>'
        '<span class="sr-hint">· 목차 (Esc)</span></button>'
    )
    def rep(m):
        tag = m.group(1)
        if re.search(r'class="[^"]*\bslide\b', tag):
            return tag + chip
        return tag
    return re.sub(r'(<section\b[^>]*>)', rep, html)


def load_episode(base, spec, idx):
    """편 하나를 읽어 (편 번호, 라벨, 제목, 슬라이드 수, 합친 HTML, deck.json 데이터) 를 돌려준다."""
    folder = base / spec.get("folder", "")
    if not folder.is_dir():
        raise BuildError(f"{idx+1}번째 편 폴더가 없습니다: {spec.get('folder')!r} (series.json 의 episodes[].folder)")
    cfg_path = folder / "deck.json"
    cfg = read_json(cfg_path) if cfg_path.exists() else {}
    if "resource_pack" in cfg:
        try:
            cfg["resource_pack"] = validate_selection(cfg["resource_pack"])
        except PackError as exc:
            raise BuildError(f"{cfg_path}: {exc}") from exc
    frags = sorted((folder / "src").glob("*.html"), key=frag_sort_key) if (folder / "src").is_dir() else []
    if not frags:
        raise BuildError(f"편 조각이 없습니다: {folder/'src'} (*.html)")
    ep = str(spec.get("ep", idx))
    label = str(spec.get("label") or f"{ep}편")
    title = str(spec.get("title") or cfg.get("title") or label)
    parts = []
    for p in frags:
        t = p.read_text(encoding="utf-8")
        if "<script" in t.lower():
            raise BuildError(f"{p.name}: 슬라이드 조각에 <script> 가 있으면 안 됩니다")
        t = prefix_ids(t, ep)
        parts.append(inject_sr(t, label, title))
    return {
        "ep": ep, "label": label, "title": title,
        "sub": str(spec.get("sub") or ""), "tag": str(spec.get("tag") or ""),
        "met": str(spec.get("met") or ""), "color": str(spec.get("color") or "var(--blue)"),
        "count": len(frags), "html": "\n".join(parts), "cfg": cfg,
        "css": collect_css([folder / "src"]),
    }


# ---------------------------------------------------------------- 목차(허브) DOM

def hub_head(s):
    upd = f'<span class="hub-upd">{escape(s["updated"])} 수정</span>' if s.get("updated") else ""
    intro = f'<p class="hub-sub">{escape(s["intro"])}</p>' if s.get("intro") else ""
    return (
        '<div class="hub-canvas">\n'
        '<div class="cx-blob cx-b1" aria-hidden="true"></div><div class="cx-blob cx-b2" aria-hidden="true"></div>\n'
        '<div class="hub-head"><div class="hub-hl">\n'
        f'<p class="hub-eyebrow">{escape(s.get("eyebrow") or (s["title"] + " 시리즈"))}{upd}</p>\n'
        f'<h1 class="hub-title">{escape(s["title"])}</h1>\n{intro}</div>\n'
        '<div class="hub-hr"><div class="hub-tools">'
        '<button type="button" class="hub-btn" data-study="glossary">용어집</button>'
        '</div><div class="hub-stat"><span class="hub-total"></span>'
        '<button type="button" class="hub-reset">기록 지우기</button></div></div></div>\n'
    )


def mn_tile(e):
    met = f'<span class="mn-met">{escape(e["met"])}</span>' if e["met"] else ""
    return (
        f'<button type="button" class="mn" data-ep="{e["ep"]}" style="--c:{e["color"]}" '
        f'aria-label="{escape(e["label"])} {escape(e["title"])} 열기">'
        '<span class="mn-ring"><i></i></span>'
        f'<span class="mn-txt"><span class="mn-no">{escape(e["label"])}</span>'
        f'<span class="mn-title">{escape(e["title"])}</span></span>{met}'
        f'<span class="mn-cnt">{e["count"]}장</span><span class="mn-in">이어보기</span></button>'
    )


def hub_map(s, eps):
    groups = (s.get("hub") or {}).get("groups") or []
    by_ep = {e["ep"]: e for e in eps}
    rows = []
    if groups:
        used = []
        for g in groups:
            used += [str(x) for x in g.get("eps", [])]
        missing = [e["ep"] for e in eps if e["ep"] not in used]
        dup = {x for x in used if used.count(x) > 1}
        unknown = [x for x in used if x not in by_ep]
        if missing or dup or unknown:
            raise BuildError(
                "hub.groups 의 eps 가 편 목록과 맞지 않습니다 "
                f"(빠진 편={missing}, 중복={sorted(dup)}, 없는 편={unknown})"
            )
        ordered = [str(x) for x in used]
    else:
        ordered = [e["ep"] for e in eps]
        groups = [{"name": "", "title": "", "eps": ordered}]
    for g in groups:
        sh = ""
        if g.get("name") or g.get("title"):
            nm = f'<span>{escape(g["name"])}</span>' if g.get("name") else ""
            sh = f'<p class="map-sh">{nm}{escape(g.get("title") or "")}</p>'
        tiles = "".join(mn_tile(by_ep[str(x)]) for x in g.get("eps", []))
        rows.append(f'<div class="map-g">{sh}<div class="map-row">{tiles}</div></div>')
    return hub_head(s) + '<div class="hub-body"><div class="map">\n' + "\n".join(rows) + '\n</div></div>\n</div>\n'


def hub_shelf(s, eps):
    books = []
    prev_tag = None
    for e in eps:
        if prev_tag is not None and e["tag"] != prev_tag:
            books.append('<span class="shelf-gap" aria-hidden="true"><span>기초</span><i></i><span>심화</span></span>')
        prev_tag = e["tag"]
        h = 330 + min(e["count"], 45) * 3
        books.append(
            f'<button type="button" class="bk" data-ep="{e["ep"]}" style="--c:{e["color"]};--h:{h}px" '
            f'aria-label="{escape(e["label"])} {escape(e["title"])} 열기">'
            f'<span class="bk-no">{escape(e["label"])}</span><span class="bk-title">{escape(e["title"])}</span>'
            '<span class="bk-prog" aria-hidden="true"><i></i></span><span class="bk-fin" aria-hidden="true">완독</span></button>'
        )
    first = eps[0]
    body = (
        '<div class="hub-body"><div class="shelf"><div class="books">\n' + "\n".join(books) + '\n</div>'
        '<div class="plank" aria-hidden="true"></div>\n'
        f'<div class="pv" data-ep="{first["ep"]}" style="--c:{first["color"]}">'
        f'<div class="pv-thumb" aria-hidden="true"><span class="pv-tno">{escape(first["label"])}</span></div>'
        '<div class="pv-main"><div class="pv-top"><span class="pv-no"></span><span class="pv-tag"></span><span class="pv-met"></span></div>'
        '<p class="pv-title"></p><p class="pv-sub"></p>'
        '<div class="pv-prog"><span class="pv-bar"><i></i></span><span class="pv-meta"></span></div>'
        '<div class="pv-btns"><button class="pv-open" type="button">처음부터 보기</button>'
        '<button class="pv-resume" type="button" hidden>이어보기</button></div>'
        '<div class="pv-print">'
        '<button type="button" class="pv-pbtn" data-study="print-summary">한 장 요약 인쇄</button>'
        '<button type="button" class="pv-pbtn" data-study="print-script">발표 대본 인쇄</button>'
        '</div></div></div></div></div>\n'
    )
    return hub_head(s) + body + "</div>\n"


def hub_list(s, eps):
    rows = []
    for e in eps:
        rows.append(
            f'<tr data-ep="{e["ep"]}" tabindex="0" role="button" aria-label="{escape(e["label"])} {escape(e["title"])} 열기">'
            f'<td class="lt-no" style="--c:{e["color"]}">{escape(e["label"])}</td>'
            f'<td class="lt-t">{escape(e["title"])}</td>'
            f'<td class="lt-s">{escape(e["sub"])}</td>'
            f'<td class="lt-n">{e["count"]}장</td>'
            '<td class="lt-p"><span class="lt-bar" aria-hidden="true"><i></i></span><span class="lt-tx">미시작</span></td>'
            '<td class="lt-go"><button type="button" class="lt-open">열기</button></td></tr>'
        )
    return (
        hub_head(s)
        + '<div class="hub-body"><table class="hub-table">'
        + '<thead><tr><th>편</th><th>제목</th><th>소개</th><th>분량</th><th>진도</th><th></th></tr></thead><tbody>\n'
        + "\n".join(rows) + "\n</tbody></table></div>\n</div>\n"
    )


def build_hub(s, eps):
    t = (s.get("hub") or {}).get("type") or "map"
    if t not in HUB_TYPES:
        raise BuildError(f'hub.type 이 "{t}" 입니다. map·shelf·list 중 하나여야 합니다')
    if t == "map":
        return hub_map(s, eps)
    if t == "shelf":
        return hub_shelf(s, eps)
    return hub_list(s, eps)


# ---------------------------------------------------------------- 공용 자산

def load_core_css():
    """shell.html 의 핵심 CSS(토큰·기본 클래스·자습 CSS) — EXTRA_CSS 표식 앞의 style 블록 두 개."""
    html = (SHARED / "assets" / "shell.html").read_text(encoding="utf-8")
    blocks = re.findall(r"<style>(.*?)</style>", html, flags=re.S)
    extra = [i for i, b in enumerate(blocks) if "/*EXTRA_CSS*/" in b]
    if not extra:
        raise BuildError("shared/assets/shell.html 에 /*EXTRA_CSS*/ 표식이 없습니다")
    # Common tokens/font/motion are global; legacy presentation CSS stops at pack wrappers.
    core = (SHARED / 'assets/css/core.css').read_text(encoding='utf-8')
    return core + '\n' + '\n'.join(b for i, b in enumerate(blocks) if 0 < i < extra[0]).strip()


def scoped_css(css, selector):
    """Native CSS scope preserves nested media/supports/keyframes without parsing braces.

    Pack :root tokens belong to the episode root, not the portal document.
    Installed packs use :root only for these token declarations.
    """
    return f'@scope ({selector}) {{\n' + css.replace(':root{', ':scope{') + '\n}'


def load_assets(eps):
    legacy = any("resource_pack" not in e["cfg"] for e in eps)
    assets = SHARED / "assets"
    runtime = (assets / "css" / "pack-runtime.css").read_text(encoding="utf-8") if any("resource_pack" in e["cfg"] for e in eps) else ""
    if legacy:
        # Stop legacy selectors at pack wrappers; pack runtime supplies their defaults.
        css = '@scope (:root) to (.deck[data-resource-pack]) {\n' + load_core_css().replace(':root{', ':scope{') + '\n}'
        comp = '@scope (:root) to (.deck[data-resource-pack]) {\n' + (assets / "css" / "components.css").read_text(encoding="utf-8") + '\n}'
        icons = "\n".join((assets / "icons" / f).read_text(encoding="utf-8") for f in ("base.svg", "extra.svg"))
    else:
        css, comp, icons = runtime, "", ""
    for index, e in enumerate(eps):
        pack = e["cfg"].get("resource_pack")
        local = e["css"]
        if pack:
            local = runtime + '\n' + (assets / "packs" / "base.css").read_text(encoding="utf-8") + '\n' + (assets / "packs" / pack["design"] / "style.css").read_text(encoding="utf-8") + '\n' + local
        if local:
            comp += '\n' + scoped_css(local, f'#series-episode-{index}')
    css = css + '\n' + common_css()
    study = motion_js() + '\n' + (SHARED / "assets" / "js" / "study.js").read_text(encoding="utf-8")
    if "</script" in study:
        raise BuildError("study.js 안에 </script> 가 있어 인라인 주입이 불가능합니다")
    return css, comp, icons, study


# ---------------------------------------------------------------- 조립

def assemble(base, hub_override=None, out_override=None):
    s = read_json(base / "series.json")
    if not str(s.get("title") or "").strip():
        raise BuildError("series.json 의 title 이 비었습니다")
    specs = s.get("episodes") or []
    if len(specs) < 2:
        raise BuildError(f"시리즈는 편이 2개 이상이어야 합니다 (지금 {len(specs)}개). 한 편이면 edu-deck-solo 로 단일 덱을 만드세요")
    eps = [load_episode(base, spec, i) for i, spec in enumerate(specs)]
    ids = [e["ep"] for e in eps]
    if len(set(ids)) != len(ids):
        raise BuildError(f"편 번호(ep) 가 겹칩니다: {ids}")
    hub_type = hub_override or (s.get("hub") or {}).get("type") or "map"
    s.setdefault("hub", {})["type"] = hub_type
    hub = build_hub(s, eps)

    for index, e in enumerate(eps):
        pack = e["cfg"].get("resource_pack")
        e["pack_attr"] = (' data-resource-pack="' + escape(json.dumps(pack, ensure_ascii=False), quote=True) + '"') if pack else ''
    decks = "\n".join(
        f'<div class="deck" id="series-episode-{index}"{e["pack_attr"]} data-ep="{e["ep"]}" data-label="{escape(e["label"])}" '
        f'data-title="{escape(e["title"])}" data-tag="{escape(e["tag"])}" data-met="{escape(e["met"])}" '
        f'data-sub="{escape(e["sub"])}" data-color="{e["color"]}">\n{e["html"]}\n</div>'
        for index, e in enumerate(eps)
    )

    # 자습 데이터: 편별 요약 + 시리즈 용어집(편 용어집 합침, 편 태그 부착) + 편 정보
    summaries = {}
    for e, spec in zip(eps, specs):
        sm = spec.get("summary") or e["cfg"].get("summary")
        if sm and isinstance(sm, dict):
            summaries[e["ep"]] = sm
    glossary = [dict(g) for g in (s.get("glossary") or []) if isinstance(g, dict) and g.get("term")]
    for e in eps:
        for g in (e["cfg"].get("glossary") or []):
            if isinstance(g, dict) and g.get("term"):
                g2 = dict(g)
                g2.setdefault("ep", e["ep"])
                glossary.append(g2)
    meta = {e["ep"]: {"label": e["label"], "title": e["title"]} for e in eps}
    study_data = {"summaries": summaries, "glossary": glossary, "meta": meta}
    data_js = "window.EDU_STUDY = " + json.dumps(study_data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";"

    css, comp, icons, study = load_assets(eps)
    tpl = TEMPLATE.read_text(encoding="utf-8")
    for marker in ("{{TITLE}}", "/*CORE_CSS*/", "/*EXTRA_CSS*/", "<!--ICONS-->", "<!--HUB-->", "<!--EPISODES-->", "<!--STUDY_DATA-->", "/*STUDY_JS*/"):
        if marker not in tpl:
            raise BuildError(f"portal_template.html 에 표식 {marker} 이(가) 없습니다")
    out_html = (
        tpl.replace("{{TITLE}}", escape(s["title"]))
        .replace("/*CORE_CSS*/", css)
        .replace("/*EXTRA_CSS*/", comp)
        .replace("<!--ICONS-->", icons)
        .replace("<!--HUB-->", hub)
        .replace("<!--EPISODES-->", decks)
        .replace("<!--STUDY_DATA-->", "<script>\n" + data_js + "\n</script>")
        .replace("/*STUDY_JS*/", study)
    )
    for marker in ("{{", "/*CORE_CSS*/", "/*EXTRA_CSS*/", "<!--ICONS-->", "<!--HUB-->", "<!--EPISODES-->", "<!--STUDY_DATA-->", "/*STUDY_JS*/"):
        if marker in out_html:
            raise BuildError(f"채우지 못한 표식이 남았습니다: {marker}")

    out = Path(out_override) if out_override else base / str(s.get("output") or f'{s["title"]}.html')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(out_html, encoding="utf-8")
    return out, eps, hub_type


def main(argv=None):
    ap = argparse.ArgumentParser(description="edu-deck-series: 시리즈 포털 조립기")
    ap.add_argument("folder", help="series.json 이 있는 작업 폴더")
    ap.add_argument("--hub", choices=HUB_TYPES, help="목차 유형 지정(series.json 덮어씀)")
    ap.add_argument("--out", help="결과 HTML 경로(기본: 작업 폴더 안)")
    args = ap.parse_args(argv)
    try:
        out, eps, hub_type = assemble(Path(args.folder), args.hub, args.out)
    except (BuildError, OSError) as e:
        print(f"ERROR  {e}", file=sys.stderr)
        return 1
    total = sum(e["count"] for e in eps)
    print(f"OK     {out}")
    print(f"       hub={hub_type}")
    for e in eps:
        print(f"       {e['ep']}편 «{e['label']} {e['title']}» {e['count']}장")
    print(f"       총 {len(eps)}편 {total}장  bytes={out.stat().st_size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
