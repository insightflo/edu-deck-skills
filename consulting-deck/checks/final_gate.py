#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""납품 게이트 — "전달된 HTML이 src/·deck.json과 일치하는가"를 보증한다.

ko-document-studio final_gate.py(© 2026 acc0mplish, MIT)의 설계를 축소 재작성했다(클린룸).
저쪽은 check/decide 2단계·엔진 지문·난수 정규화까지 겹친다. 우리는 build_deck이 결정적이므로
(동일 입력→동일 바이트, 실측 확인) 재빌드 바이트 대조만으로 재현성을 보증한다.

단계:
  check  <덱폴더>            입력 해시 스냅샷 + 임시 빌드 + check_deck → qa/build-check.json
  decide <덱폴더> [--html]   입력 재스냅샷 대조 + 재빌드 바이트 대조 + 사람 검토 결속
                             → qa/final-gate.json, 종료코드 0/1/2

NOT_GUARANTEED (이 게이트가 보증하지 않는 것 — 코드에 명시한다):
  - 시각·심미 품질(캡처·design-critique 별도)
  - 내용·수치의 정확성(verify_sources --fetch · check_consulting 원장 대조 별도)
  - 발표 시간·납품 일정
종료코드: 0 통과, 1 실패(검사상 결함), 2 실행 못 함(환경·입력 문제 — 통과 아님).
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REVIEW_ITEMS = ("내용 정확성", "시각 품질", "근거·출처", "계약 준수", "고객 요구 충족", "최종 승인")
EXCLUDE_DIRS = {"qa", "shots"}
NOT_GUARANTEED = ["시각·심미 품질", "내용·수치 정확성", "발표 시간·일정"]


def snapshot(deck: Path):
    """입력 전수 해시 — deck.json·src/·charts/·storyline.md 등 산출물·qa 외 전부."""
    files = {}
    for p in sorted(deck.rglob("*")):
        if not p.is_file() or p.is_symlink():
            if p.is_symlink():
                raise SystemExit(f"[실행 못 함] 심볼릭 링크는 허용하지 않습니다: {p}")
            continue
        rel = p.relative_to(deck).as_posix()
        if rel.split("/")[0] in EXCLUDE_DIRS:
            continue
        # deck.json이 가리키는 산출물(루트 *.html)은 입력이 아니라 결과라 제외
        if rel.endswith(".html") and "/" not in rel:
            continue
        files[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return files


def output_html(deck: Path) -> Path:
    name = json.loads((deck / "deck.json").read_text(encoding="utf-8-sig")).get("output", "")
    if not name:
        raise SystemExit("[실행 못 함] deck.json에 output이 없습니다")
    return deck / name


def build(deck: Path, scripts: Path) -> bytes:
    r = subprocess.run([sys.executable, str(scripts / "build_deck.py"), str(deck)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[실행 못 함] 빌드 실패: {r.stdout.strip()[:200]} {r.stderr.strip()[:200]}")
    return output_html(deck).read_bytes()


def cmd_check(deck: Path, scripts: Path):
    snap = snapshot(deck)
    html = build(deck, scripts)
    deck_result = subprocess.run([sys.executable, str(scripts / "check_deck.py"),
                                  str(output_html(deck))], capture_output=True, text=True)
    ok = deck_result.returncode == 0
    qa = deck / "qa"
    qa.mkdir(exist_ok=True)
    (qa / "build-check.json").write_text(json.dumps({
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inputs_sha256": snap,
        "output_sha256": hashlib.sha256(html).hexdigest(),
        "check_deck_pass": ok,
        "not_guaranteed": NOT_GUARANTEED,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"build-check: inputs={len(snap)}파일 check_deck={'PASS' if ok else 'FAIL'} → qa/build-check.json")
    return 0 if ok else 1


def cmd_decide(deck: Path, scripts: Path, delivered: Path | None):
    prev = json.loads((deck / "qa" / "build-check.json").read_text(encoding="utf-8")) \
        if (deck / "qa" / "build-check.json").is_file() else None
    snap = snapshot(deck)
    fails = []
    if prev is None:
        fails.append("qa/build-check.json이 없습니다 — check 단계를 먼저 실행하세요")
    elif prev.get("inputs_sha256") != snap:
        changed = sorted(set(snap) ^ set(prev["inputs_sha256"]) |
                         {k for k in snap if prev["inputs_sha256"].get(k) != snap[k]})
        fails.append(f"check 이후 입력이 바뀌었습니다: {', '.join(changed[:8])}")
    rebuilt = build(deck, scripts)
    target = delivered or output_html(deck)
    same = rebuilt == target.read_bytes() if target.is_file() else False
    if not same:
        fails.append(f"납품본이 재빌드와 다릅니다: {target.name}")
    review_path = deck / "qa" / "human-review.json"
    review_ok, review = False, {}
    if review_path.is_file():
        try:
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review_ok = (bool(review.get("reviewer"))
                         and all(review.get("items", {}).get(i) is True for i in REVIEW_ITEMS)
                         and review.get("open_items", []) == []
                         and review.get("output_sha256") == hashlib.sha256(target.read_bytes()).hexdigest())
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            review_ok = False
    if not review_ok:
        fails.append(f"사람 검토 결속 실패 — qa/human-review.json: 검토자·{len(REVIEW_ITEMS)}항목 true·"
                     f"open_items 비움·output_sha256 일치가 필요합니다")
    qa = deck / "qa"
    qa.mkdir(exist_ok=True)
    verdict = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "verdict": "PASS" if not fails else "FAIL", "failures": fails,
               "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None,
               "not_guaranteed": NOT_GUARANTEED}
    (qa / "final-gate.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"final-gate: {verdict['verdict']}" + ("" if not fails else "  " + " | ".join(fails)))
    return 0 if not fails else 1


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="납품 재현성 게이트 — build-check → decide")
    ap.add_argument("cmd", choices=["check", "decide"])
    ap.add_argument("deck_dir", help="deck.json·src/가 있는 덱 폴더")
    ap.add_argument("--html", help="decide: 대조할 납품본(기본 deck.json output)")
    args = ap.parse_args(argv)
    deck = Path(args.deck_dir)
    if not (deck / "deck.json").is_file() or not (deck / "src").is_dir():
        print("ERROR  deck.json·src/가 있는 덱 폴더를 주세요", file=sys.stderr)
        return 2
    scripts = Path(__file__).resolve().parent.parent.parent / "edu-deck" / "shared" / "scripts"
    if not (scripts / "build_deck.py").is_file():
        print(f"ERROR  build_deck.py를 찾을 수 없습니다: {scripts}", file=sys.stderr)
        return 2
    try:
        if args.cmd == "check":
            return cmd_check(deck, scripts)
        return cmd_decide(deck, scripts, Path(args.html) if args.html else None)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
