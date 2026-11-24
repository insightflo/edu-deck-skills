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
# series.json 의 family 허용값 — classic 은 '계열을 고르지 않음'과 같은 뜻이라 명시해도 된다.
SERIES_FAMILIES = ("studio", "vivid", "drawing", "classic")


def deck_families():
    """편 deck.json 의 family 허용값 — tone_router.FAMILIES(P1)와 같은 집합.

    통합 전 스냅샷(tone_router 에 FAMILIES 가 아직 없는 상태)에서도 동작하도록
    없으면 설계 명세의 동일 값으로 폴백한다. classic 은 deck.json 에서 값으로 쓸 수 없다
    (family 미지정이 곧 classic).
    """
    try:
        from tone_router import FAMILIES
        return tuple(FAMILIES)
    except Exception:
        return ("studio", "vivid", "drawing")


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


def load_episode(base, spec, idx, series_family="classic"):
    """편 하나를 읽어 (편 번호, 라벨, 제목, 슬라이드 수, 합친 HTML, deck.json 데이터) 를 돌려준다.

    series_family: 시리즈가 요구하는 계열 — 편 deck.json 의 family 와 다르면 거부한다
    (한 시리즈 한 계열, family-design.md §10 ①).
    """
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
    if cfg.get("theme") is not None:
        from tone_router import THEMES
        if not isinstance(cfg["theme"], str) or cfg["theme"] not in THEMES:
            raise BuildError(f"{cfg_path}: 'theme' 은 다음 중 하나입니다: {', '.join(THEMES)}")
        if "resource_pack" in cfg:
            raise BuildError(f"{cfg_path}: 'theme' 은 legacy 경로 전용입니다 (resource_pack 과 함께 쓸 수 없습니다)")
    if cfg.get("family") is not None:
        family = cfg["family"]
        if not isinstance(family, str) or family not in deck_families():
            raise BuildError(f"{cfg_path}: 'family' 은 다음 중 하나입니다: {', '.join(deck_families())}")
        if cfg.get("theme") is not None:
            raise BuildError(f"{cfg_path}: 'theme' 은 classic 경로 전용입니다 (family 와 함께 쓸 수 없습니다)")
    # 한 시리즈 한 계열: 편의 유효 계열(family 미지정 = classic)이 시리즈 계열과 같아야 한다.
    ep_family = cfg.get("family") or "classic"
    if ep_family != series_family:
        raise BuildError(
            f"{cfg_path}: 편 계열 '{ep_family}' 이(가) 시리즈 계열 '{series_family}' 과 다릅니다 "
            "(한 시리즈에는 한 계열만 — series.json 의 family 와 맞추세요)")
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
    ep_css = collect_css([folder / "src"])
    # 프리셋/계열 불일치 방어(P1): classic 프리셋 생성물(preset-css 표식, 계열 표식 없음)이
    # 계열 편의 src/ 에 있으면 거부한다 — 편 덱을 단독 조립할 때와 같은 규칙.
    if cfg.get("family") is not None and "preset-css" in ep_css:
        m = re.search(r"preset-css[^\n]*?family\s*=\s*\"?([\w-]+)", ep_css)
        if (m.group(1) if m else "classic") != cfg["family"]:
            raise BuildError(
                f"{cfg_path}: classic 전용 프리셋 CSS(src 의 preset-css 생성물)는 "
                f"family '{cfg['family']}' 편에 쓸 수 없습니다")
    return {
        "ep": ep, "label": label, "title": title,
        "sub": str(spec.get("sub") or ""), "tag": str(spec.get("tag") or ""),
        "met": str(spec.get("met") or ""), "color": str(spec.get("color") or "var(--blue)"),
        "count": len(frags), "html": "\n".join(parts), "cfg": cfg,
        "css": ep_css,
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


def drawing_font_css():
    """drawing 계열용 GowunBatang @font-face 등록 블록만 만든다(본문 스택 덮어쓰기 없음).

    §4.3: 제목만 'Gowun Batang', 본문·숫자는 Pretendard — font_css() 는 body/.slide/.pack
    스택까지 덮어쓰므로 쓸 수 없다. visual_assets 에 등록 전용 함수(P2a font_face_css)가
    있으면 그것을 쓰고, 없으면 font_css() 산출물에서 라이선스 주석 + @font-face 블록만
    추출하는 안전 폴백을 쓴다(이 worktree 에는 아직 등록 함수가 없다).
    """
    import visual_assets
    reg = getattr(visual_assets, "font_face_css", None) or getattr(visual_assets, "register_font_face_css", None)
    if reg is not None:
        return reg("gowun-batang")
    css = visual_assets.font_css("gowun-batang")
    head, _, rest = css.partition("@font-face")
    m = re.match(r"\s*(\{[^}]*\})", rest)      # 첫 블록이 @font-face — 뒤의 본문 덮어쓰기는 버린다
    if not m:
        raise BuildError("font_css('gowun-batang') 에서 @font-face 블록을 찾지 못했습니다")
    return head + "@font-face" + m.group(1) + "\n"


def load_assets(eps, series_family="classic"):
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
    # drawing 계열: 편 덱이 build_deck 를 거치지 않으므로 GowunBatang @font-face 등록을
    # 이 경로(load_assets)에서 조건부 인라인한다(§10). 포털 허브 제목도 이 글꼴을 쓴다.
    if series_family == "drawing":
        css += '\n' + drawing_font_css()
    study = motion_js() + '\n' + (SHARED / "assets" / "js" / "study.js").read_text(encoding="utf-8")
    if "</script" in study:
        raise BuildError("study.js 안에 </script> 가 있어 인라인 주입이 불가능합니다")
    return css, comp, icons, study


# ---------------------------------------------------------------- 조립

def assemble(base, hub_override=None, out_override=None):
    s = read_json(base / "series.json")
    if not str(s.get("title") or "").strip():
        raise BuildError("series.json 의 title 이 비었습니다")
    # 시리즈 계열(선택): 미지정·'classic' 이면 classic. 한 시리즈 한 계열(§10) —
    # 각 편 deck.json 의 유효 계열과의 일치는 load_episode 에서 거부한다.
    series_family = s.get("family")
    if series_family is not None and (not isinstance(series_family, str) or series_family not in SERIES_FAMILIES):
        raise BuildError(f"series.json 의 'family' 는 다음 중 하나입니다: {', '.join(SERIES_FAMILIES)}")
    series_family = series_family or "classic"
    specs = s.get("episodes") or []
    if len(specs) < 2:
        raise BuildError(f"시리즈는 편이 2개 이상이어야 합니다 (지금 {len(specs)}개). 한 편이면 edu-deck-solo 로 단일 덱을 만드세요")
    eps = [load_episode(base, spec, i, series_family) for i, spec in enumerate(specs)]
    ids = [e["ep"] for e in eps]
    if len(set(ids)) != len(ids):
        raise BuildError(f"편 번호(ep) 가 겹칩니다: {ids}")
    hub_type = hub_override or (s.get("hub") or {}).get("type") or "map"
    s.setdefault("hub", {})["type"] = hub_type
    hub = build_hub(s, eps)

    for index, e in enumerate(eps):
        pack = e["cfg"].get("resource_pack")
        e["pack_attr"] = (' data-resource-pack="' + escape(json.dumps(pack, ensure_ascii=False), quote=True) + '"') if pack else ''
        # legacy 편 테마: themes.css 의 [data-theme] 블록이 이 편 요소 아래로만 상속된다.
        theme = e["cfg"].get("theme")
        e["theme_attr"] = f' data-theme="{escape(theme, quote=True)}"' if theme and theme != "classic" else ''
        # 3단 검증 ② 결과물 흔적: 완성 HTML 만으로 각 편 계열을 재확인할 수 있게 래퍼에 남긴다.
        # classic(family 미지정) 편은 심지 않는다 — check_series 는 '표식 없음'을 classic 으로 읽는다.
        e["family_attr"] = f' data-ep-family="{escape(e["cfg"]["family"], quote=True)}"' if e["cfg"].get("family") else ''
    decks = "\n".join(
        f'<div class="deck" id="series-episode-{index}"{e["pack_attr"]}{e["theme_attr"]} data-ep="{e["ep"]}"'
        f'{e["family_attr"]} data-label="{escape(e["label"])}" '
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

    css, comp, icons, study = load_assets(eps, series_family)
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
    # 포털 루트 계열 표식(§10 ②): classic 은 심지 않는다 — 속성 없는 포털이 곧 classic.
    # 스킨 CSS 는 [data-family] 선택자라 속성이 없으면 한 줄도 적용되지 않는다(렌더 동일).
    if series_family != "classic":
        out_html, n = re.subn(r'<html\b([^>]*)>', rf'<html\1 data-family="{series_family}">', out_html, count=1)
        if n != 1:
            raise BuildError("portal_template.html 의 <html> 태그에 data-family 를 심지 못했습니다")
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
