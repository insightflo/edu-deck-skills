#!/usr/bin/env python3
"""arch-si 재생성 — SI 실무형 P0 6유형 7장을 의미 모델(models/)만으로 다시 만든다.

[왜] arch-demo(6장)가 재현성 계약(regen --check)을 세웠고, SI 확장 예제도 같은 계약을
따른다. 5장은 arch_layout.mjs(확장 문법: kind r·zones kind/between/labelPos·aux·범례 자동),
2장(B1 Swimlane·B2 Sequence)은 arch_lanes.mjs(레인+빌드 시점 토큰 시뮬레이터)이 만든다.
[입력] models/*.json — 각 장의 의미 모델(coords 는 arch_layout 레이아웃 캐시).
[실행] python3 regen-si.py            # src/*.html 전부 + arch-si.html 빌드
       python3 regen-si.py --check    # 임시 출력과 현재 파일 비교(diff 수만 보고)
결정적(deterministic): 같은 models → 같은 바이트. 시간·난수·절대경로는 산출에 안 들어간다.
"""
import html
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent.parent / 'edu-deck/shared'
ARCH = SHARED / 'scripts/arch_layout.mjs'
LANES = SHARED / 'scripts/arch_lanes.mjs'
BUILD = SHARED / 'scripts/build_deck.py'


def esc(s):
    return html.escape(str(s), quote=True)


# 표지 — 스니펫 01-cover-blueprint(블루프린트 표지)을 모델로 채운다.
def render_cover(m):
    stages = ''.join(
        f'<text x="1700" y="{255 + i * 357}">{esc(s)}</text>'
        for i, s in enumerate(m['stages']))
    return f'''<!-- 표지(블루프린트 변형)
     모델: models/cover.json · 생성: python3 regen-si.py (스니펫 01-cover-blueprint 기반 템플릿)
     손으로 고치지 않는다. 모델을 고치고 다시 생성한다. -->
<section class="slide cx dark" data-archetype="cover" data-variant="blueprint" style="padding:0">

<svg aria-hidden="true" style="position:absolute;inset:0" viewBox="0 0 1920 1080">
<defs><pattern id="cov3-grid" width="64" height="64" patternUnits="userSpaceOnUse"><path d="M64 0H0V64" fill="none" stroke="var(--soft)" stroke-width="1.1" opacity=".3"/></pattern></defs>
<rect width="1920" height="1080" fill="url(#cov3-grid)"/>
<path d="M78 102h1720v870H78z" fill="none" stroke="var(--soft)" stroke-width="2" stroke-dasharray="9 11"/>
<line x1="78" y1="230" x2="1800" y2="230" stroke="var(--soft)" stroke-width="2"/>
<circle cx="1562" cy="558" r="315" fill="none" stroke="var(--soft)" stroke-width="2" stroke-dasharray="3 17"/>
<circle cx="1562" cy="558" r="235" fill="none" stroke="var(--line)" stroke-width="2"/>
<g>
<path d="M1295 386l327-144 269 157-341 155z" fill="var(--blue)" stroke="var(--blue-text)" stroke-width="4"/>
<path d="M1295 386v128l255 143V554z" fill="var(--ink)" stroke="var(--soft)" stroke-width="3"/>
<path d="M1550 554l341-155v119l-341 139z" fill="var(--ink)" stroke="var(--soft)" stroke-width="3"/>
<path d="M1240 587l331-140 272 157-334 158z" fill="var(--blue)" stroke="var(--blue-text)" stroke-width="4"/>
<path d="M1240 587v110l269 158V762z" fill="var(--ink)" stroke="var(--soft)" stroke-width="3"/>
<path d="M1509 762l334-158v99l-334 152z" fill="var(--ink)" stroke="var(--soft)" stroke-width="3"/>
<path d="M1190 769l309-136 264 154-305 142z" fill="var(--accent)" stroke="var(--accent-light)" stroke-width="4"/>
<path d="M1190 769v83l268 160v-83z" fill="var(--accent-text)" stroke="var(--accent-light)" stroke-width="3"/>
<path d="M1458 929l305-142v83l-305 142z" fill="var(--accent-text)" stroke="var(--accent-light)" stroke-width="3"/>
</g>
<circle cx="1562" cy="324" r="24" fill="var(--accent-light)"/><circle cx="1562" cy="558" r="24" fill="var(--light)"/><circle cx="1562" cy="748" r="24" fill="var(--accent-light)"/>
<path d="M1562 348v185m0 49v142" stroke="var(--muted)" stroke-width="4" stroke-dasharray="11 14"/>
<g fill="var(--muted)" font-size="31" font-weight="700">{stages}</g>
<path d="M1297 386l255 143 339-130" fill="none" stroke="var(--muted)" stroke-width="4" stroke-dasharray="8 10"/>
<g stroke="var(--soft)" stroke-width="3"><line x1="1095" y1="280" x2="1095" y2="913"/><line x1="1095" y1="913" x2="1149" y2="913"/></g>
</svg>
<p class="cx-eyebrow" style="position:absolute;left:126px;top:149px;font-size:27px;font-weight:800;letter-spacing:4px;color:var(--accent-light)">{esc(m['eyebrow'])}</p>
<div style="position:absolute;left:126px;top:351px;width:1050px">
<h1 class="cx-title" style="font-size:104px;line-height:1.17;letter-spacing:-5px;font-weight:900;color:var(--light)">{esc(m['title'])}</h1>
<p class="cx-sub" style="color:var(--muted);font-size:41px;margin-top:54px">{esc(m['sub'])}</p>
</div>
<p class="cover-date" style="z-index:3;left:125px;bottom:92px;color:var(--muted);font-size:26px">{esc(m['footer'])}</p>
<p style="position:absolute;right:126px;top:160px;font-size:24px;font-weight:800;color:var(--muted);margin:0;z-index:3">{esc(m['serial'])}</p>
<aside class="notes">{esc(m['notes'])}</aside>
</section>
'''


# 요약 — 스니펫 27-checklist(card-columns 변형)을 6항목 3×2 로 확장한 템플릿.
def render_summary(m):
    def todo(item, step):
        return (f'<div class="todo" data-step="{step}" style="flex:1;flex-direction:column;align-items:flex-start">'
                f'<div class="col" style="gap:6px;flex:1"><h4 style="font-size:28px">{esc(item["t"])}</h4>'
                f'<p style="font-size:22px">{esc(item["d"])}</p></div>'
                f'<span class="tbox" aria-label="확인 표시"></span></div>')
    rows = []
    for r in range(0, len(m['items']), 3):
        cells = ''.join(todo(it, i + 1) for i, it in enumerate(m['items'][r:r + 3]))
        rows.append(f'  <div class="row" style="flex:1;min-height:0;gap:18px;align-items:stretch">{cells}</div>')
    body = '\n'.join(rows)
    return f'''<!-- 인수인계 체크리스트(요약)
     모델: models/summary.json · 생성: python3 regen-si.py (스니펫 27-checklist 기반 템플릿)
     손으로 고치지 않는다. 모델을 고치고 다시 생성한다. -->
<section class="slide" data-archetype="checklist" data-variant="card-columns" style="gap:26px">
  <div class="head"><p class="eyebrow">{esc(m['eyebrow'])}</p><h2 class="title">{esc(m['title'])}</h2></div>
{body}
  <p class="small">{esc(m['small'])}</p>
  <aside class="notes">{esc(m['notes'])}</aside>
</section>
'''


# 덱 순서 = 파일 이름 정렬(표지 → A1 개요→상세→A2→A3 → B1~B3 → C1~C3·D1 → 요약). (출력 조각, 모델, 생성기)
SLIDES = [
    ('00-cover.html',       'cover.json',           'cover'),
    ('a1a-overview.html',   'a1a-overview.json',   'arch'),
    ('a1b-detail.html',     'a1b-detail.json',     'arch'),
    ('a2-3tier.html',       'a2-3tier.json',       'arch'),
    ('a3-integration.html', 'a3-integration.json', 'arch'),
    ('b1-swimlane.html',    'b1-swimlane.json',    'lanes'),
    ('b2-sequence.html',    'b2-sequence.json',    'lanes'),
    ('b3-batch.html',       'b3-batch.json',       'arch'),
    ('c1-dmz.html',         'c1-dmz.json',         'arch'),
    ('c2-physical.html',    'c2-physical.json',    'arch'),
    ('c3-dr.html',          'c3-dr.json',          'arch'),
    ('d1-astobe.html',      'd1-astobe.json',      'lanes'),
    ('zz-summary.html',     'summary.json',        'summary'),
]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"생성 실패: {' '.join(str(c) for c in cmd)}\n{r.stderr.strip()}")
    if r.stderr.strip():
        sys.stderr.write(f"  {r.stderr.strip()}\n")


def build(out_dir):
    out_dir = Path(out_dir)
    (out_dir / 'src').mkdir(parents=True, exist_ok=True)
    for name, model, kind in SLIDES:
        if kind in ('cover', 'summary'):
            m = json.loads((HERE / 'models' / model).read_text(encoding='utf-8'))
            body = render_cover(m) if kind == 'cover' else render_summary(m)
            (out_dir / 'src' / name).write_text(body, encoding='utf-8')
            print(f"[src] {name}")
            continue
        gen = ARCH if kind == 'arch' else LANES
        cmd = (['node', str(gen)] +
               ([str(HERE / 'models' / model)] if kind == 'arch' else ['--in', str(HERE / 'models' / model)]) +
               ['-o', str(out_dir / 'src' / name)])
        if kind == 'arch':  # 레이아웃 캐시는 커밋 본과 같은 자리에 둔다
            coords = HERE / 'models' / model.replace('.json', '.coords.json')
            if coords.exists():
                cmd += ['--coords', str(coords)]
        run(cmd)
        print(f"[src] {name}")


def main():
    if '--check' in sys.argv:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            build(td)
            diff = 0
            for name, _, _ in SLIDES:
                a = (HERE / 'src' / name).read_bytes()
                b = (Path(td) / 'src' / name).read_bytes()
                if a != b:
                    diff += 1
                    print(f"DIFF {name}: 현재 {len(a)}B vs 재생성 {len(b)}B")
            print(f"--check: {len(SLIDES) - diff}/{len(SLIDES)} 동일, diff={diff}")
            raise SystemExit(1 if diff else 0)
    build(HERE)
    r = subprocess.run([sys.executable, str(BUILD), str(HERE)],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        raise SystemExit(f"덱 빌드 실패\n{r.stderr.strip()}")


if __name__ == '__main__':
    main()
