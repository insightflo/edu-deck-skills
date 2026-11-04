#!/usr/bin/env python3
"""edu-deck-series 시리즈 검사기.

[파일 목적]
  build_series.py 로 만든 포털 HTML 을 정적(구조)·렌더(화면 넘침) 검사한다.
  편 하나의 규칙(아키타입·확인 문제·노트 분량 등)은 edu-deck-solo 의 check_deck.static_checks 를
  편마다 그대로 재사용하고, 여기서는 시리즈 고유 규칙(허브↔편 일치, id 접두, 목차 칩, 진도 엔진)을 본다.

[주요 흐름]
  1. 정적: <title>, 표식 잔여, id 중복, 아이콘 참조, 외부 자원, 허브 카드와 편 목록 일치,
     각 편 슬라이드에 목차 칩(.sr) 존재, window.EDU_STUDY 편 메타 일치.
  2. 편마다 check_deck.static_checks 재사용 — 편 안 슬라이드를 가짜 #stage 에 넣어 검사.
  3. 렌더: Chrome 으로 열어 시작 화면(목차) 확인, 각 편의 모든 장·단계를 window.deckGo(편,장,단계) 로
     방문하며 check_deck.RENDER_JS(선택자만 편 버전으로 바꿈)로 넘침·글자 크기·대비·겹침을 잰다.

[외부 연결]
  입력: 포털 HTML 경로. 필요: beautifulsoup4(정적), playwright + Chrome(화면).
  없으면 설치하지 않고 WARN(NOT_RUN) 으로 알린다. --json 으로 결과 저장.

[수정시 주의]
  check_deck.py 의 함수·RENDER_JS 를 가져다 쓴다(복사하지 않는다). shared 가 이동하면 경로를 함께 고친다.
"""
import argparse
import json
import re
import sys
from copy import deepcopy
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent            # edu-deck-series/scripts
SHARED_SCRIPTS = HERE.parent.parent / "edu-deck" / "shared" / "scripts"
sys.path.insert(0, str(SHARED_SCRIPTS))

from bs4 import BeautifulSoup  # noqa: E402

import check_deck  # noqa: E402

Report = check_deck.Report
MARKERS = ("{{", "/*CORE_CSS*/", "/*EXTRA_CSS*/", "<!--ICONS-->", "<!--HUB-->", "<!--EPISODES-->", "<!--STUDY_DATA-->", "/*STUDY_JS*/")


def ep_label(deck):
    return f'{deck.get("data-ep")}편({deck.get("data-label") or "라벨 없음"})'


def static_checks(html_text, soup, rep):
    """시리즈 고유 정적 규칙. 결과는 rep 에 쌓는다."""
    title = soup.find("title")
    if not title or not title.get_text(strip=True) or "{{" in title.get_text():
        rep.add("ERROR", None, "구조", "<title> 이 비었거나 표식이 남았습니다")
    for m in MARKERS:
        if m in html_text:
            rep.add("ERROR", None, "표식", f"채우지 못한 표식이 남았습니다: {m}")

    ids = {}
    for el in soup.find_all(id=True):
        ids[el["id"]] = ids.get(el["id"], 0) + 1
    for k, n in ids.items():
        if n > 1:
            rep.add("ERROR", None, "id 중복", f'id="{k}" 가 {n}번 있습니다')
    for el in soup.find_all(["use", "mpath"]):
        ref = el.get("href") or el.get("xlink:href") or ""
        if ref.startswith("#") and ref[1:] not in ids:
            rep.add("ERROR", None, "아이콘", f"{ref} 를 찾을 수 없습니다", target=ref)
    for ref in set(re.findall(r"url\(#([\w-]+)\)", html_text)):
        if ref not in ids:
            rep.add("ERROR", None, "참조", f"url(#{ref}) 대상이 없습니다", target=ref)

    for el in soup.find_all(["img", "script", "link", "iframe", "video", "audio", "source", "object", "embed"]):
        for attr in ("src", "href", "data"):
            val = el.get(attr)
            if val and check_deck.EXTERNAL.match(val):
                rep.add("ERROR", None, "외부 자원", f"<{el.name} {attr}=\"{val[:60]}\"> 외부 파일에 의존합니다", target=val)
    for css in [t.get_text() for t in soup.find_all("style")] + [el.get("style", "") for el in soup.find_all(style=True)]:
        for m in re.finditer(r"url\(\s*['\"]?((?:https?:)?//[^)'\"]+)|@import\s+[^;]+", css, re.I):
            rep.add("ERROR", None, "외부 자원", f"CSS 가 외부 자원을 부릅니다: {m.group(0)[:60]}", target=m.group(0))

    hub = soup.select_one("#hub")
    stage = soup.select_one("#stage")
    if not hub:
        rep.add("ERROR", None, "구조", "#hub 목차가 없습니다")
    if not stage:
        rep.add("ERROR", None, "구조", "#stage 무대가 없습니다")
    decks = soup.select("#stage > .deck")
    if len(decks) < 2:
        rep.add("ERROR", None, "구조", f"편(.deck)이 {len(decks)}개뿐입니다. 시리즈는 2편 이상부터입니다")
    for d in decks:
        if not (d.get("data-ep") or "").strip():
            rep.add("ERROR", None, "구조", "data-ep 가 비거나 없는 편이 있습니다")
        if not (d.get("data-label") or "").strip():
            rep.add("ERROR", None, "구조", f'편 {d.get("data-ep")} 의 data-label(편 라벨)이 비었습니다')
        slides = [s for s in d.find_all("section", class_="slide", recursive=False)]
        if not slides:
            rep.add("ERROR", None, "구조", f'편 {d.get("data-ep")} 에 슬라이드가 없습니다')
        for i, s in enumerate(slides, 1):
            if not s.find(class_="sr", recursive=False) and "sr" not in (s.get("class") or []):
                rep.add("WARN", i, "목차 칩", f"편 {d.get('data-ep')} {i}번째 슬라이드에 목차 칩(.sr)이 없습니다")

    if hub is not None and decks:
        hub_eps = [c.get("data-ep") for c in hub.select(".mn[data-ep], .books .bk[data-ep], .hub-table tr[data-ep]")]
        deck_eps = [d.get("data-ep") for d in decks]
        if sorted(hub_eps) != sorted(deck_eps) or len(hub_eps) != len(deck_eps):
            rep.add("ERROR", None, "허브 일치", f"목차 카드와 편 목록이 다릅니다 (목차={hub_eps}, 편={deck_eps})")
        if hub.select(".hub-reset") and not hub.select(".hub-total"):
            rep.add("WARN", None, "허브 일치", "기록 지우기는 있는데 진도 합계(.hub-total)가 없습니다")
        if not hub.select('[data-study="glossary"]'):
            rep.add("WARN", None, "허브 일치", "목차에 용어집 단추가 없습니다")

    m = re.search(r"window\.EDU_STUDY\s*=\s*(\{.*?\});?\s*</script>", html_text, flags=re.S)
    if not m:
        rep.add("ERROR", None, "자습 데이터", "window.EDU_STUDY 주입이 없습니다")
    else:
        try:
            study = json.loads(m.group(1).replace("<\\/", "</"))
            deck_eps = {str(d.get("data-ep")) for d in decks}
            meta_eps = {str(k) for k in (study.get("meta") or {})}
            if deck_eps and meta_eps != deck_eps:
                rep.add("ERROR", None, "자습 데이터", f"EDU_STUDY.meta 의 편 집합이 편 목록과 다릅니다 ({sorted(meta_eps)} vs {sorted(deck_eps)})")
            for ep in (study.get("summaries") or {}):
                if str(ep) not in deck_eps:
                    rep.add("ERROR", None, "자습 데이터", f"summaries 에 없는 편 번호가 있습니다: {ep}")
        except json.JSONDecodeError as e:
            rep.add("ERROR", None, "자습 데이터", f"EDU_STUDY JSON 파싱 실패: {e}")


def per_ep_static(html_text, soup, rep):
    """편마다 check_deck.static_checks 를 재사용해 solo 와 같은 규칙으로 검사한다."""
    ok = True
    icons = "".join(str(s) for s in soup.select("#stage > svg"))   # 공용 아이콘 꾸러미(가짜 무대에도 넣는다)
    for original in soup.select("#stage > .deck"):
        d = deepcopy(original)
        slides = [s for s in d.find_all("section", class_="slide", recursive=False)]
        if not slides:
            continue
        # .sr 칩은 포털이 심은 것이라 편 검사에서는 뗀다(solo 원고 규칙과 같은 상태로 본다)
        for s in slides:
            sr = s.find(class_="sr", recursive=False)
            if sr:
                sr = sr.extract()
        ep = d.get("data-ep")
        pack_meta = ('<meta name="edu-deck-resource-pack" content="' + escape(d['data-resource-pack'], quote=True) + '">') if d.has_attr('data-resource-pack') else ''
        pseudo = BeautifulSoup("<html><head><title>" + escape(d.get("data-title") or "") + "</title>" + pack_meta + "</head>"
                               '<body>' + icons + '<div id="stage">' + "".join(str(s) for s in slides) + "</div></body></html>", "html.parser")
        sub = Report()
        try:
            check_deck.static_checks(str(pseudo), pseudo, sub, allow_placeholders=False)
        except Exception as e:  # 검사기 오류는 시리즈 검사 에러로
            rep.add("ERROR", None, "검사기", f"편 {ep} 정적 검사 중 멈췄습니다: {e}")
            ok = False
            continue
        for it in sub.items:
            no = it["slide"]
            arch, ttl = sub.slide_meta.get(no, ("?", "?"))
            rep.add(it["sev"], None, it["kind"], f"[{ep_label(d)} {no}번째 장({arch})] {it['message']}", target=ttl[:30])
        if sub.count("ERROR"):
            ok = False
    return ok


RENDER_JS_SERIES = check_deck.RENDER_JS.replace(
    "([idx]) => {", "([ep, idx]) => {"
).replace(
    "document.querySelectorAll('#stage > .slide')[idx]",
    "document.querySelectorAll('#stage > .deck[data-ep=\"' + ep + '\"] > .slide')[idx]"
)


def render_checks(path, rep, sheets_dir, shots_dir):
    """브라우저로 목차 시작·편 이동·모든 장 렌더를 검사한다."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        rep.add("WARN", None, "화면 검사", "playwright 가 없어 화면 검사를 못 했습니다 (설치 안내: pip install playwright)")
        return False
    url = Path(path).resolve().as_uri()
    stage = "start"
    try:
        with sync_playwright() as pw:
            browser = check_deck.launch(pw)
            stage = "measure"
            errors = []
            ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = ctx.new_page()
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url)
            page.wait_for_timeout(600)
            info = page.evaluate("window.seriesInfo ? window.seriesInfo() : null")
            if not info or not isinstance(info.get("decks"), list):
                rep.add("ERROR", None, "엔진", "window.seriesInfo 가 없습니다 (시리즈 엔진 미주입)")
                browser.close()
                return True
            eps = [str(e) for e in info["decks"]]
            if info.get("mode") != "hub":
                rep.add("ERROR", None, "엔진", "열자마자 목차(hub) 화면이어야 합니다")
            if not page.evaluate("document.body.classList.contains('in-hub')"):
                rep.add("ERROR", None, "엔진", "body.in-hub 가 붙지 않았습니다")
            if sheets_dir or shots_dir:
                shot_dir = Path(sheets_dir) if sheets_dir else None
                if shot_dir:
                    shot_dir.mkdir(parents=True, exist_ok=True)
                    (shot_dir / "hub.png").write_bytes(page.screenshot())
            page.wait_for_timeout(200)
            ctx.close()
            for e in dict.fromkeys(errors):
                rep.add("ERROR", None, "스크립트 오류", e[:200])
            # 2차: 측정
            ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, reduced_motion="reduce")
            page = ctx.new_page()
            page.on("pageerror", lambda e: rep.add("ERROR", None, "스크립트 오류", str(e)[:200]))
            page.goto(url)
            page.add_style_tag(content=check_deck.QUIET_CSS)
            page.wait_for_timeout(400)
            for ep in eps:
                total = page.evaluate(f"(window.deckGo({ep!r},0), window.deckInfo().count)")
                if not total:
                    rep.add("ERROR", None, "엔진", f"편 {ep} 을 열 수 없습니다 (deckGo 실패)")
                    continue
                for n in range(1, total + 1):
                    info = page.evaluate(f"(window.deckGo({ep!r},{n - 1},0), window.deckInfo())")
                    top = info.get("maxStep")
                    top = int(top) if isinstance(top, (int, float)) and top == top else 0
                    for s in range(top + 1):
                        page.evaluate(f"window.deckGo({ep!r},{n - 1},{s})")
                        for f in page.evaluate(RENDER_JS_SERIES, [ep, n - 1]):
                            where = f"[{ep}편 {n}번째 장]"
                            rep.add(f["sev"], None, f["kind"], f"{where} {f['msg']}", target=f.get("target"), step=s)
                if shots_dir:
                    Path(shots_dir).mkdir(parents=True, exist_ok=True)
                    page.evaluate(f"window.deckGo({ep!r},{total - 1})")
                    (Path(shots_dir) / f"ep{ep}-last.png").write_bytes(page.screenshot())
            browser.close()
    except Exception as e:
        if stage == "start":
            rep.add("WARN", None, "화면 검사", f"브라우저를 시작하지 못했습니다: {str(e).splitlines()[0][:160]}")
            return False
        rep.add("ERROR", None, "검사기 오류", f"화면 검사 중 멈췄습니다(검사기 문제일 수 있음): {str(e).splitlines()[0][:160]}")
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description="edu-deck-series: 시리즈 포털 검사기")
    ap.add_argument("html", help="build_series.py 로 만든 포털 HTML")
    ap.add_argument("--json", help="검사 결과 JSON 저장 경로")
    ap.add_argument("--sheets", help="목차 화면 PNG 저장 폴더")
    ap.add_argument("--shots", help="편 마지막 장 PNG 저장 폴더")
    ap.add_argument("--no-render", action="store_true", help="화면 검사 건너뛰기(정적만)")
    args = ap.parse_args(argv)

    path = Path(args.html)
    if not path.exists():
        print(f"ERROR  파일이 없습니다: {path}", file=sys.stderr)
        return 1
    html_text = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")
    rep = Report()
    static_checks(html_text, soup, rep)
    per_ep_static(html_text, soup, rep)
    render = "NOT_RUN"
    if not args.no_render:
        render = "RUN" if render_checks(path, rep, args.sheets, args.shots) else "NOT_RUN"
    n_err, n_warn = rep.count("ERROR"), rep.count("WARN")
    slides_total = len(soup.select("#stage .deck > .slide"))
    for line in rep.lines():
        print(line)
    result = "PASS" if n_err == 0 else "FAIL"
    print(f"RESULT: {result}  errors={n_err} warnings={n_warn} render={render} eps={len(soup.select('#stage > .deck'))} slides={slides_total}")
    if args.json:
        out = {"result": result, "errors": n_err, "warnings": n_warn, "render": render,
               "items": [{"sev": i["sev"], "slide": i["slide"], "kind": i["kind"], "message": i["message"]} for i in rep.items]}
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if n_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
