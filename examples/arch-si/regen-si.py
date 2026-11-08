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
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent.parent / 'edu-deck/shared'
ARCH = SHARED / 'scripts/arch_layout.mjs'
LANES = SHARED / 'scripts/arch_lanes.mjs'
BUILD = SHARED / 'scripts/build_deck.py'

# 덱 순서 = 파일 이름 정렬(A1 개요→상세→A2→A3→B1→B2→C1). (출력 조각, 모델, 생성기)
SLIDES = [
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
