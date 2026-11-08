#!/usr/bin/env python3
"""arch-demo 재생성 — 의미 모델(models/)만으로 src/ 조각 6장과 demo6.html을 다시 만든다.

[왜] 이전에는 아이소메트릭 2장(04·06)이 저장소 밖 조립기(/tmp 의 assemble.py)와
장면 JSON 으로 만들어져, 저장소만으로는 재생할 수 없었다. 이제 모델 전부가
models/ 안에 있고, 조립 규칙도 이 파일 하나면 충분하다.

[입력] models/*.json — dagre 4장(arch_layout.mjs 입력) + 아이소 2장(iso_layout.mjs
입력, `slide` 블록에 표제·캡션·노트 내장).
[실행] python3 regen.py            # src/*.html 전부 + demo6.html
       python3 regen.py --check    # 임시 출력과 현재 파일 비교(diff 수만 보고)
결정적(deterministic): 같은 models → 같은 바이트. 시간·난수·절대경로는 산출에 안 들어간다.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SHARED = REPO / 'edu-deck/shared'
DAGRE = SHARED / 'scripts/arch_layout.mjs'
ISO = SHARED / 'scripts/iso_layout.mjs'
BUILD = SHARED / 'scripts/build_deck.py'

# 덱 순서 = 장 번호. (출력 조각, 모델, 생성기)
SLIDES = [
    ('01-microservices.html', '01-microservices.json', 'dagre'),
    ('02-layered.html',       '02-layered.json',       'dagre'),
    ('03-topology.html',      '03-topology.json',      'dagre'),
    ('04-iso-dc.html',        'dc.scene.json',         'iso'),
    ('05-ha.html',            '04-ha.json',            'dagre'),
    ('06-iso-hybrid.html',    'hybrid.scene.json',     'iso'),
]

ISO_TMPL = """<!-- {title}
     계열: arch-diagram(아이소메트릭) · 데이터: models/{scene} · 그림: fig/{fig}
     생성: python3 regen.py — 손으로 고치지 않는다. -->
<section class="slide" data-archetype="arch-diagram" style="gap:20px">
  <div class="head"><p class="eyebrow">{eyebrow}</p><h2 class="title">{title}</h2></div>
  <figure class="fig-slot">
{svg}
    <figcaption>{caption}</figcaption>
  </figure>
  <aside class="notes">{notes}</aside>
</section>
"""


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"생성 실패: {' '.join(str(c) for c in cmd)}\n{r.stderr.strip()}")
    if r.stderr.strip():
        sys.stderr.write(f"  {r.stderr.strip()}\n")


def build(out_dir):
    out_dir = Path(out_dir)
    (out_dir / 'src').mkdir(parents=True, exist_ok=True)
    (out_dir / 'fig').mkdir(parents=True, exist_ok=True)
    for name, model, kind in SLIDES:
        if kind == 'dagre':
            run(['node', str(DAGRE), str(HERE / 'models' / model),
                 '-o', str(out_dir / 'src' / name)])
        else:
            scene = json.loads((HERE / 'models' / model).read_text(encoding='utf-8'))
            s = scene['slide']
            fig = name.replace('.html', '.svg')
            run(['node', str(ISO), '--in', str(HERE / 'models' / model),
                 '--out', str(out_dir / 'fig' / fig)])
            svg = (out_dir / 'fig' / fig).read_text(encoding='utf-8').strip()
            (out_dir / 'src' / name).write_text(
                ISO_TMPL.format(title=s['title'], scene=model, fig=fig,
                                eyebrow=s['eyebrow'], svg=svg,
                                caption=s['caption'], notes=s['notes']),
                encoding='utf-8')
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
            print(f"--check: {len(SLIDES) - diff}/6 동일, diff={diff}")
        return
    build(HERE)
    r = subprocess.run([sys.executable, str(BUILD), str(HERE)],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        raise SystemExit(f"덱 빌드 실패\n{r.stderr.strip()}")


if __name__ == '__main__':
    main()
