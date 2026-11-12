#!/usr/bin/env python3
"""regen.py — 컨설팅 차트 모델 재생성 (arch-demo/regen.py 계약과 동일)

  python3 regen.py <작업 폴더>            charts/*.json·*.flint.json 전부 → src/ 덮어쓰기
  python3 regen.py --check <작업 폴더>    재생성 결과와 기존 파일 바이트 비교 — diff/실패 시 exit 1

디스패치는 모델 확장자로 한다: *.flint.json → flint_gen.mjs(flint 설치 필요),
나머지 *.json → chart_gen.mjs. 모델 파일명 → 조각 경로 규칙(SKILL.md 4단계):
charts/NN-이름.(flint.)json → src/NN-이름.html. 같은 이름이 없으면
src/*-<stem>.html(NN- 접두사 변형)을 사전 순 첫 번째로 쓴다.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

GEN = Path(__file__).resolve().parent / 'chart_gen.mjs'
FGEN = Path(__file__).resolve().parent / 'flint_gen.mjs'


def model_stem(model):
    """charts/05-x.flint.json → 05-x · charts/05-x.json → 05-x"""
    name = model.name
    return name[:-len('.flint.json')] if name.endswith('.flint.json') else model.stem


def slide_path(root, stem):
    src = root / 'src'
    exact = src / f'{stem}.html'
    if exact.exists():
        return exact
    cand = sorted(src.glob(f'*-{stem}.html'))
    return cand[0] if cand else exact


def regenerate(root, model, tmp):
    stem = model_stem(model)
    out = slide_path(root, stem)
    tmp_out = Path(tmp) / (stem + '.html')
    gen = FGEN if model.name.endswith('.flint.json') else GEN
    p = subprocess.run(
        ['node', str(gen), '--in', str(model), '-o', str(tmp_out), '--quiet'],
        capture_output=True, text=True)
    if p.returncode != 0:
        return out, None, (p.stderr or p.stdout).strip().splitlines()[-1] if (p.stderr or p.stdout).strip() else '생성 실패'
    return out, tmp_out.read_bytes(), None


def main():
    argv = sys.argv[1:]
    check = '--check' in argv
    argv = [a for a in argv if a != '--check']
    if not argv:
        print('usage: regen.py [--check] <작업 폴더>')
        return 2
    root = Path(argv[0])
    charts = root / 'charts'
    if not charts.is_dir():
        print(f'FAIL: charts/ 폴더 없음 — {root}')
        return 1
    models = sorted(charts.glob('*.json'))
    if not models:
        print(f'FAIL: {charts} 에 차트 모델이 없다')
        return 1
    (root / 'src').mkdir(exist_ok=True)

    same = diff = failed = 0
    engines = {'chart_gen': 0, 'flint': 0}
    with tempfile.TemporaryDirectory(prefix='cregen-') as tmp:
        for model in models:
            engines['flint' if model.name.endswith('.flint.json') else 'chart_gen'] += 1
            out, body, err = regenerate(root, model, tmp)
            rel = out.relative_to(root)
            if err:
                failed += 1
                print(f'FAIL  {model.name} → {rel} — {err}')
                continue
            if check:
                prev = out.read_bytes() if out.exists() else None
                if prev == body:
                    same += 1
                    print(f'SAME  {model.name} → {rel}')
                else:
                    diff += 1
                    print(f'DIFF  {model.name} → {rel}' + (' (없음 → 새로 만듦)' if prev is None else ''))
            else:
                out.write_bytes(body)
                same += 1
                print(f'OK    {model.name} → {rel}')
    tally = ' · '.join(f'{k}={v}' for k, v in engines.items() if v)
    print(f'RESULT {"same" if check else "written"}={same} diff={diff} failed={failed} total={len(models)} ({tally})')
    return 1 if (diff or failed) else 0


if __name__ == '__main__':
    sys.exit(main())
