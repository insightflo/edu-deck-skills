#!/usr/bin/env python3
"""Strict, reproducible visual/motion evidence; never injects checker quiet CSS.

python3 dev/visual_motion_check.py --out /absolute/new/evidence
--quick checks source only; it is NOT the full E gate.
Frame screenshots use real WAAPI effects paused at explicit timeline positions.
rAF is sampled separately during live motion, without screenshots or DOM audits.
Contrast includes composited opacity and SVG text; gradient extrema are conservative.
Unknown backgrounds fail closed, rather than disappearing from the denominator.
"""

from __future__ import annotations
import argparse
import hashlib
import importlib
import json
import math
import re
import sys
import subprocess
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / "scripts"))
build = importlib.import_module("build_deck").build
launch = importlib.import_module("check_deck").launch

FRAMES = (0, 75, 150, 300, 500, 1200)
REPRESENTATIVES = ("cover", "timeline", "mechanism", "meter", "before-after", "quiz-ab")

AUDIT_JS = r"""(selector) => {
 const s=document.querySelector(selector||'.slide.active'), findings=[],texts=[];
 const sr=s.getBoundingClientRect(), canvas=document.createElement('canvas');canvas.width=canvas.height=1;
 const ctx=canvas.getContext('2d',{willReadFrequently:true});
 const rgba=value=>{if(!value||value==='none')return [0,0,0,0];ctx.clearRect(0,0,1,1);ctx.fillStyle=value;ctx.fillRect(0,0,1,1);const p=ctx.getImageData(0,0,1,1).data;return [p[0],p[1],p[2],p[3]/255];};
 const blend=(a,b,op=1)=>[0,1,2].map(i=>a[i]*a[3]*op+b[i]*(1-a[3]*op));
 const lum=c=>c.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
 const ratio=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
 const own=e=>[...e.childNodes].filter(n=>n.nodeType===3&&n.textContent.trim());
 const desc=e=>e.tagName.toLowerCase()+'.'+(e.getAttribute('class')||'').trim().replace(/\s+/g,'.');
 const visible=e=>{const c=getComputedStyle(e),r=e.getBoundingClientRect();return r.width>0&&r.height>0&&c.display!=='none'&&c.visibility==='visible'&&!e.closest('.notes,[aria-hidden="true"],.ed-number-reel');};
 const outside=(a,b)=>a.left<b.left-2||a.top<b.top-2||a.right>b.right+2||a.bottom>b.bottom+2;
 for(const e of s.querySelectorAll('*')) {
  if(!visible(e)||!own(e).length)continue;
  const c=getComputedStyle(e),rect=e.getBoundingClientRect(),text=own(e).map(n=>n.textContent.trim()).join(' ');
  const identity={target:desc(e),text:text.slice(0,100)};
  let alpha=1;const chain=[];
  for(let x=e;x;x=x.parentElement){chain.unshift(x);alpha*=Number(getComputedStyle(x).opacity);if(x===s)break;}
  if(alpha===0)continue;
  const ranges=own(e).flatMap(n=>{const r=document.createRange();r.selectNodeContents(n);return [...r.getClientRects()];});
  if(ranges.some(r=>outside(r,sr)))findings.push({kind:'overflow',...identity,rect:{left:rect.left,top:rect.top,right:rect.right,bottom:rect.bottom}});
  for(let x=e.parentElement;x&&x!==s;x=x.parentElement){const cs=getComputedStyle(x);if(/hidden|clip/.test(cs.overflowX+cs.overflowY)&&ranges.some(r=>outside(r,x.getBoundingClientRect()))){findings.push({kind:'clipped-text',...identity,container:desc(x)});break;}}
  let backgrounds=[[255,255,255]],unknown=false;
  for(const x of chain){const st=getComputedStyle(x),bg=rgba(st.backgroundColor);backgrounds=backgrounds.map(b=>blend(bg,b));
   if(st.backgroundImage!=='none'){
    const colors=st.backgroundImage.match(/rgba?\([^)]*\)|color\([^)]*\)/g)||[];
    if(!colors.length||/url\(/.test(st.backgroundImage))unknown=true;
    else backgrounds=backgrounds.flatMap(b=>colors.map(col=>blend(rgba(col),b))).slice(-32);
   }
  }
  // SVG fills are not CSS backgrounds: include enclosing rect/circle fills.
  if(e instanceof SVGTextElement){const svg=e.ownerSVGElement,cx=(rect.left+rect.right)/2,cy=(rect.top+rect.bottom)/2;
   for(const shape of svg.querySelectorAll('rect,circle,ellipse')){if(shape.compareDocumentPosition(e)&Node.DOCUMENT_POSITION_PRECEDING)continue;const r=shape.getBoundingClientRect(),st=getComputedStyle(shape);if(cx>=r.left&&cx<=r.right&&cy>=r.top&&cy<=r.bottom&&st.visibility==='visible'){const fill=rgba(st.fill);backgrounds=backgrounds.map(b=>blend(fill,b,Number(st.fillOpacity)*Number(st.opacity)));}}
  }
  let size=parseFloat(c.fontSize);if(e instanceof SVGElement&&e.getScreenCTM){const m=e.getScreenCTM();if(m)size*=Math.hypot(m.a,m.b);}
  else size*=sr.width/(s.offsetWidth||sr.width);
  if(size===0)continue;
  const fg=rgba(e instanceof SVGElement?c.fill:c.color);if(e instanceof SVGElement)fg[3]*=Number(c.fillOpacity);
  const need=size>=24||(size>=18.6667&&Number(c.fontWeight)>=700)?3:4.5;
  const base=Math.min(...backgrounds.map(bg=>ratio(blend(fg,bg),bg)));
  const actual=Math.min(...backgrounds.map(bg=>ratio(blend(fg,bg,alpha),bg)));
  const row={...identity,size,alpha,need,ratio:actual,baseRatio:base,foreground:fg,backgrounds};texts.push(row);
  if(unknown)findings.push({kind:'unmeasured-background',...identity});
  if(actual+1e-6<need)findings.push({kind:'contrast',...row});
 }
 // Explanatory connector strokes: thin graphics require 3:1, independently
 // of text size. Filled cards and decorative aria-hidden illustrations are not
 // automatically classified as essential UI boundaries.
 const graphics=[];
 for(const e of s.querySelectorAll('svg path,svg line,svg polyline')){
  const c=getComputedStyle(e),r=e.getBoundingClientRect();
  if(e.closest('defs,symbol,marker,[aria-hidden="true"],.notes')||c.visibility!=='visible'||c.display==='none'||(!r.width&&!r.height)||c.stroke==='none'||parseFloat(c.strokeWidth)===0)continue;
  const chain=[];let alpha=Number(c.strokeOpacity);for(let x=e;x;x=x.parentElement){chain.unshift(x);alpha*=Number(getComputedStyle(x).opacity);if(x===s)break;}
  if(!alpha)continue;
  let bg=[255,255,255],unknown=false;for(const x of chain){const st=getComputedStyle(x);bg=blend(rgba(st.backgroundColor),bg);if(st.backgroundImage!=='none')unknown=true;}
  const svg=e.ownerSVGElement,cx=(r.left+r.right)/2,cy=(r.top+r.bottom)/2;
  for(const shape of svg.querySelectorAll('rect,circle,ellipse')){if(shape.compareDocumentPosition(e)&Node.DOCUMENT_POSITION_PRECEDING)continue;const q=shape.getBoundingClientRect(),st=getComputedStyle(shape);if(cx>=q.left&&cx<=q.right&&cy>=q.top&&cy<=q.bottom&&st.visibility==='visible')bg=blend(rgba(st.fill),bg,Number(st.fillOpacity)*Number(st.opacity));}
  if(c.stroke.startsWith('url('))unknown=true;
  const row={target:desc(e),stroke:c.stroke,alpha,ratio:ratio(blend(rgba(c.stroke),bg,alpha),bg),background:bg,need:3};graphics.push(row);
  if(unknown)findings.push({kind:'unmeasured-graphic-background',...row});
  else if(row.ratio+1e-6<3)findings.push({kind:'graphic-contrast',...row});
 }
 const running=document.getAnimations().filter(a=>a.playState==='running').length;
 return {findings,texts,graphics,running,signature:s.dataset.motionSignature||null,slide:{width:sr.width,height:sr.height},pageWidth:document.documentElement.scrollWidth};
}"""

SEMANTICS_JS = r"""(selector)=>{
const s=document.querySelector(selector||'.slide.active');
return [...s.querySelectorAll('*')].filter(e=>!e.closest('.notes,[aria-hidden="true"],.ed-number-reel')&&getComputedStyle(e).display!=='none'&&getComputedStyle(e).visibility==='visible'&&e.getBoundingClientRect().width>0&&parseFloat(getComputedStyle(e).fontSize)>0).flatMap(e=>[...e.childNodes].filter(n=>n.nodeType===3&&n.textContent.trim()).map(n=>n.textContent.trim()));
}"""

LIVE_JS = r"""async ([index,step])=>{
 const deltas=[],times=[],start=performance.now();let prev;
 // The collector starts before the actual semantic state transition.
 const done=new Promise(resolve=>{function frame(t){times.push(t);if(prev!==undefined)deltas.push(t-prev);prev=t;if(t-start<1000)requestAnimationFrame(frame);else resolve();}requestAnimationFrame(frame);});
 deckGo(index,step);await done;return {deltas,times,elapsed:performance.now()-start};
}"""

OBSERVER_JS = r"""(()=>{window.__auditMotion=[];const original=Element.prototype.animate;
Element.prototype.animate=function(frames,options){window.__auditMotion.push({tag:this.tagName,cls:this.getAttribute('class'),frames,options});return original.call(this,frames,options);};})();"""


def source_findings(name: str, text: str) -> list[dict[str, Any]]:
    """Canonical declarations are excluded by the caller, never by color value."""
    text = re.sub(r"/\*.*?\*/|<!--.*?-->", "", text, flags=re.S)
    findings: list[dict[str, Any]] = []
    for match in re.finditer(r"#[0-9a-fA-F]{3,8}\b", text):
        findings.append(
            {
                "kind": "non-token-color",
                "file": name,
                "value": match.group(),
                "line": text[: match.start()].count("\n") + 1,
            }
        )
    for match in re.finditer(
        r"\b(?:animation|transition)(?:-(?:duration|delay|timing-function))?\s*:\s*([^;}]+)",
        text,
    ):
        value = match.group(1)
        if re.search(
            r"(?<![\w-])(?:\d*\.)?\d+m?s\b|\b(?:ease(?:-in|-out|-in-out)?|linear)\b|cubic-bezier\(",
            value,
        ):
            findings.append(
                {"kind": "non-token-motion", "file": name, "value": value.strip()}
            )
    if re.search(r"<animate(?:Motion|Transform)?\b", text):
        findings.append({"kind": "unowned-smil", "file": name})
    return findings


def source_audit() -> dict[str, Any]:
    paths: list[Path] = []
    for folder in ("css", "js", "snippets", "icons", "packs"):
        paths.extend(
            p
            for p in (SHARED / "assets" / folder).rglob("*")
            if p.suffix in (".css", ".html", ".svg", ".js")
        )
    paths.extend(
        [
            SHARED / "dev/shell_template.html",
            SHARED / "dev/pack_shell_template.html",
            SHARED.parent.parent / "edu-deck-series/dev/portal_template.html",
        ]
    )
    rows, findings = [], []
    for path in sorted(set(paths)):
        text = path.read_text()
        name = str(path.relative_to(SHARED.parent.parent))
        if path == SHARED / "assets/css/tokens.css":
            # Only canonical color declarations are legal here, not arbitrary rules.
            cleaned = re.sub(r"--[\w-]+\s*:\s*#[0-9a-fA-F]{3,8}\b", "", text)
        else:
            cleaned = text
        findings.extend(source_findings(name, cleaned))
        rows.append(
            {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
    return {"files": rows, "findings": findings}


def inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((SHARED / "assets/snippets").glob("*.html")):
        for variant, section in enumerate(
            BeautifulSoup(path.read_text(), "html.parser").select("section.slide")
        ):
            steps = [
                int(value)
                for e in [section, *section.select("*")]
                for a in (
                    "data-step",
                    "data-add",
                    "data-only",
                    "data-lit",
                    "data-until",
                )
                if isinstance(value := e.get(a), str) and value.isdigit()
            ]
            rows.append(
                {
                    "index": len(rows),
                    "family": path.name,
                    "variant": variant,
                    "archetype": section.get("data-archetype"),
                    "max_step": max(steps, default=0),
                }
            )
    return rows


def dump(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def frame_sheet(images: list[tuple[str, Path]], target: Path, columns: int = 4) -> None:
    width, height = 480, 300
    sheet = Image.new(
        "RGB", (columns * width, math.ceil(len(images) / columns) * height), "white"
    )
    draw = ImageDraw.Draw(sheet)
    for i, (label, path) in enumerate(images):
        x, y = i % columns * width, i // columns * height
        draw.text((x + 8, y + 8), label, fill="black")
        with Image.open(path) as image:
            image.thumbnail((width, 270))
            sheet.paste(image, (x, y + 30))
    sheet.save(target)


def motion_findings(
    records: list[dict[str, Any]], tokens: dict[str, Any]
) -> list[dict[str, Any]]:
    failures = []
    allowed = {
        "transform",
        "opacity",
        "filter",
        "strokeDashoffset",
        "offset",
        "easing",
        "composite",
    }
    for record in records:
        opts = record["options"]
        reason = []
        if opts["duration"] not in tokens["durations"]:
            reason.append("duration")
        if opts["easing"] not in tokens["easings"]:
            reason.append("easing")
        delay = opts.get("delay", 0)
        if (
            abs(
                delay / (tokens["durations"][0] / 8)
                - round(delay / (tokens["durations"][0] / 8))
            )
            > 1e-6
        ):
            reason.append("delay")
        for frame in record["frames"]:
            if set(frame) - allowed:
                reason.append("property")
            if "filter" in frame and (
                opts["duration"] > 300
                or not re.fullmatch(r"blur\([0-6]px\)", frame["filter"])
            ):
                reason.append("blur-exception")
            if "strokeDashoffset" in frame and opts["duration"] > 500:
                reason.append("stroke-exception")
        if reason:
            failures.append(
                {"kind": "runtime-motion", "reason": reason, "record": record}
            )
    return failures


def run(out: Path, quick: bool = False, only: list[int] | None = None) -> int:
    out.mkdir(parents=True, exist_ok=True)
    source = source_audit()
    dump(out / "source-audit.json", source)
    rows = inventory()
    dump(out / "inventory.json", rows)
    if quick:
        print(
            json.dumps(
                {
                    "mode": "source-only",
                    "files": len(source["files"]),
                    "findings": len(source["findings"]),
                }
            )
        )
        return int(bool(source["findings"]))
    if (
        len(rows) != 57
        or len({r["family"] for r in rows}) != 32
        or len({r["archetype"] for r in rows}) != 30
    ):
        raise RuntimeError("Inventory changed: review coverage explicitly")
    deck = out / "gallery.html"
    # Raw «instruction ≤N» placeholders exceed their own allowed content length.
    # Use the existing maximum-length authoring fixture, without editing snippets.
    fixture = out / "filled"
    if fixture.exists():
        raise FileExistsError("Use a fresh output directory; preserve prior evidence")
    subprocess.run(
        [sys.executable, str(SHARED / "dev/fill_test.py"), str(fixture)], check=True
    )
    build(
        "Visual motion — maximum-length 57 variants",
        sorted((fixture / "src").glob("*.html")),
        [SHARED / "assets/css"],
        [SHARED / "assets/icons"],
        deck,
    )
    captures = out / "frames"
    captures.mkdir(exist_ok=True)
    static_dir = out / "static"
    static_dir.mkdir(exist_ok=True)
    coverage, failures, raf, sheets, modes = [], list(source["findings"]), [], [], []
    selected = rows if only is None else [r for r in rows if r["index"] in only]
    expected = {}
    with sync_playwright() as pw:
        browser = launch(pw)
        page = browser.new_page(
            viewport={"width": 1920, "height": 1080}, reduced_motion="no-preference"
        )
        page.add_init_script(OBSERVER_JS)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(deck.as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(1300)
        tokens = page.evaluate(
            """()=>{const c=getComputedStyle(document.documentElement);return {durations:['m1','m2','m3','m4'].map(k=>parseFloat(c.getPropertyValue('--'+k))),easings:['e-out','e-spring','e-inout'].map(k=>c.getPropertyValue('--'+k).trim())};}"""
        )
        for row in selected:
            i = row["index"]
            page.evaluate("i=>deckGo((i+1)%deckInfo().count,0)", i)
            page.wait_for_timeout(900)
            for step in range(row["max_step"] + 1):
                page.evaluate("a=>deckGo(a[0],a[1])", [i, step])
                page.evaluate(
                    "()=>{window.__frameAnimations=document.getAnimations();for(const a of __frameAnimations){a.pause();a.currentTime=0;}}"
                )
                samples = []
                for ms in FRAMES:
                    page.evaluate(
                        "ms=>{for(const a of __frameAnimations)a.currentTime=ms;}", ms
                    )
                    result = page.evaluate(AUDIT_JS)
                    file = captures / f"{i:02d}-step{step:02d}-{ms:04d}.png"
                    page.screenshot(path=str(file))
                    sample = {"ms": ms, "file": str(file.relative_to(out)), **result}
                    samples.append(sample)
                    failures.extend(
                        {"slide": i, "step": step, "ms": ms, **f}
                        for f in result["findings"]
                    )
                page.evaluate(
                    "()=>{for(const a of __frameAnimations){try{a.finish()}catch{a.cancel()}}}"
                )
                page.evaluate("()=>new Promise(r=>requestAnimationFrame(r))")
                expected[(i, step)] = page.evaluate(SEMANTICS_JS)
                coverage.append({**row, "step": step, "samples": samples})
                if not samples[-1]["signature"]:
                    failures.append({"kind": "missing-signature", "slide": i})
                if step == row["max_step"]:
                    sheets.append(
                        (
                            f"{i + 1:02d} {row['family']} / {row['archetype']}",
                            captures / f"{i:02d}-step{step:02d}-1200.png",
                        )
                    )
            print(f"frames {i + 1}/57 {row['archetype']}", flush=True)
            dump(out / "coverage.json", coverage)
        records = page.evaluate("window.__auditMotion")
        dump(out / "runtime-motion.json", records)
        failures.extend(motion_findings(records, tokens))
        # Every semantic step must remain complete and future answers must stay hidden.
        for mode in ("reduced", "study"):
            page.emulate_media(
                reduced_motion="reduce" if mode == "reduced" else "no-preference"
            )
            if mode == "study":
                page.keyboard.press("s")
            for row in selected:
                for step in range(row["max_step"] + 1):
                    page.evaluate("a=>deckGo(a[0],a[1])", [row["index"], step])
                    page.evaluate(
                        "()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"
                    )
                    result = page.evaluate(AUDIT_JS)
                    text = page.evaluate(SEMANTICS_JS)
                    match = text == expected[(row["index"], step)]
                    modes.append(
                        {
                            "mode": mode,
                            "slide": row["index"],
                            "step": step,
                            "semantic_match": match,
                            **result,
                        }
                    )
                    if not match or result["running"]:
                        failures.append(
                            {
                                "kind": "static-incomplete",
                                "mode": mode,
                                "slide": row["index"],
                                "step": step,
                                "running": result["running"],
                                "match": match,
                            }
                        )
                    failures.extend(
                        {"mode": mode, "slide": row["index"], "step": step, **f}
                        for f in result["findings"]
                    )
                    if step == row["max_step"]:
                        page.screenshot(
                            path=str(static_dir / f"{mode}-{row['index']:02d}.png")
                        )
            if mode == "study":
                page.keyboard.press("s")
        page.emulate_media(media="print")
        page.evaluate('dispatchEvent(new Event("beforeprint"))')
        for row in selected:
            selector = f"#stage>.slide:nth-of-type({row['index'] + 1})"
            result = page.evaluate(AUDIT_JS, selector)
            text = page.evaluate(SEMANTICS_JS, selector)
            match = text == expected[(row["index"], row["max_step"])]
            modes.append(
                {
                    "mode": "print",
                    "slide": row["index"],
                    "semantic_match": match,
                    **result,
                }
            )
            if not match or result["running"]:
                failures.append(
                    {
                        "kind": "static-incomplete",
                        "mode": "print",
                        "slide": row["index"],
                        "match": match,
                        "running": result["running"],
                    }
                )
            failures.extend(
                {"mode": "print", "slide": row["index"], **f}
                for f in result["findings"]
            )
            page.locator(selector).screenshot(
                path=str(static_dir / f"print-{row['index']:02d}.png")
            )
        page.emulate_media(media="screen")
        page.evaluate('dispatchEvent(new Event("afterprint"))')
        dump(out / "static-modes.json", modes)
        dump(out / "browser-errors.json", errors)
        if errors:
            failures.append({"kind": "browser-errors", "errors": errors})
        page.close()
        # A separate page, no observer, no DOM audit or screenshots in measurement.
        perf = browser.new_page(
            viewport={"width": 1920, "height": 1080}, reduced_motion="no-preference"
        )
        perf.goto(deck.as_uri())
        perf.evaluate("document.fonts.ready")
        perf.wait_for_timeout(1300)
        for row in selected:
            perf.evaluate("i=>deckGo((i+1)%deckInfo().count,0)", row["index"])
            perf.wait_for_timeout(900)
            for step in range(row["max_step"] + 1):
                sample = perf.evaluate(LIVE_JS, [row["index"], step])
                d = sample["deltas"]
                missed = sum(max(0, round(v / (1000 / 60)) - 1) for v in d)
                raf.append(
                    {
                        "slide": row["index"],
                        "step": step,
                        **sample,
                        "target_hz": 60,
                        "frames": len(d),
                        "intervals_over_25ms": sum(v > 25 for v in d),
                        "estimated_missed_60hz_frames": missed,
                        "max_ms": max(d, default=0),
                        "mean_ms": sum(d) / len(d) if d else None,
                    }
                )
            dump(out / "raf-60hz.json", raf)
        browser.close()
    frame_sheet(sheets, out / "all-archetypes.png")
    for arch in REPRESENTATIVES:
        representative = next((r for r in selected if r["archetype"] == arch), None)
        if representative:
            step = min(1, representative["max_step"])
            frame_sheet(
                [
                    (
                        f"{arch} step {step} / {ms}ms",
                        captures
                        / f"{representative['index']:02d}-step{step:02d}-{ms:04d}.png",
                    )
                    for ms in FRAMES
                ],
                out / f"after-{arch}.png",
                3,
            )
    dump(out / "findings.json", failures)
    summary = {
        "result": "FAIL" if failures else "PASS",
        "scope": "partial" if only is not None else "full",
        "families": len({r["family"] for r in selected}),
        "variants": len(selected),
        "identities": len({r["archetype"] for r in selected}),
        "steps": len(coverage),
        "frame_captures": len(coverage) * len(FRAMES),
        "static_states": len(modes),
        "raf_runs": len(raf),
        "findings": len(failures),
        "findings_by_kind": {
            k: sum(f["kind"] == k for f in failures)
            for k in sorted({f["kind"] for f in failures})
        },
        "capture_method": "WAAPI pause/currentTime; separate live rAF",
        "quiet_css": False,
        "limitations": [
            "Gradient extrema are conservative, not pixel-level backgrounds.",
            "Text/geometry audit is not full WCAG conformance or independent teaching review.",
            "Physical devices and non-Chromium browsers NOT_RUN.",
        ],
    }
    dump(out / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument(
        "--slides", help="Diagnostic zero-based indices; marks report partial"
    )
    args = parser.parse_args()
    sys.exit(
        run(
            args.out.resolve(),
            args.quick,
            [int(x) for x in args.slides.split(",")] if args.slides else None,
        )
    )
