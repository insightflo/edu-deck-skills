"""check_deck.py 가 일부러 넣은 결함을 잡는지 확인하는 시험.

[목적] 정상 덱 1개 + 결함 하나씩 넣은 덱 여러 개를 만들어 check_deck 결과(종료 코드, 결함 종류)를 표로 낸다.
[출력] edu-deck-workspace/defects/<이름>/ 덱들, 표준 출력에 기대 → 실제 표
"""
import json, pathlib, re, shutil, subprocess

import sys, tempfile
ROOT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(tempfile.gettempdir()) / "edu-deck-defects"
SKILL = pathlib.Path(__file__).resolve().parent.parent
# 정상 노트는 문서 기준(110~450자) 안에 든다
NOTE = "<aside class=\"notes\">" + ("이 장에서는 화면의 두 카드를 차례로 설명합니다. 화살표를 누를 때마다 하나씩 나옵니다. "
                                   "먼저 청중에게 지금은 어떻게 하고 있는지 물어본 뒤 첫 카드를 보여 주세요. "
                                   "시간이 모자라면 둘째 카드는 짧게 넘깁니다. 끝나면 다음 장으로 넘어갑니다.") + "</aside>"
SHORT_NOTE = "<aside class=\"notes\">" + "이 장에서는 화면의 두 카드를 차례로 설명합니다. 화살표를 누를 때마다 하나씩 나옵니다. 끝나면 다음 장으로 넘어갑니다." + "</aside>"


def slide(arch, body, title="시험 슬라이드입니다", notes=NOTE, extra=""):
    return (f'<section class="slide" data-archetype="{arch}"{extra}><div class="head"><p class="eyebrow">시험</p>'
            f'<h2 class="title">{title}</h2></div>{body}{notes}</section>')


GOOD_CARD = '<div class="row"><div class="card f1" data-step="1"><h3>첫째</h3><p class="body">설명입니다.</p></div><div class="card f1" data-step="2"><h3>둘째</h3><p class="body">설명입니다.</p></div></div>'
BASE = [
    slide("agenda", GOOD_CARD, "오늘 다룰 두 가지"),
    slide("compare-2", GOOD_CARD),
    '<section class="slide dark center" data-archetype="closing"><h2 class="big">마무리합니다</h2>' + NOTE + "</section>",
]

CASES = {
    "good": ([], 0, []),
    "overflow": ([slide("compare-2", '<div class="card" style="width:2400px"><h3>넓은 카드</h3></div>')], 1, ["화면 밖 넘침"]),
    "win-clipped": ([slide("worked-example", '<div class="win" style="height:300px"><div class="win-bar"><i></i><i></i><i></i><span class="wt">창</span></div><div class="win-body"><div class="doc">' + "".join(f"<p>줄 {i} 입니다 내용이 많습니다</p>" for i in range(14)) + "</div></div></div>")], 1, ["잘린 글자"]),
    "box-overflow": ([slide("compare-2", '<div class="card" style="height:160px;overflow:visible"><h3>제목</h3><p class="body">' + "넘치는 글입니다 " * 30 + "</p></div>")], 1, ["상자 밖 넘침"]),
    "tiny-text": ([slide("compare-2", '<div class="card"><p style="font-size:16px">작은 글자</p></div>')], 1, ["글자 크기"]),
    "no-notes": ([slide("compare-2", GOOD_CARD, notes="")], 1, ["발표자 노트"]),
    "placeholder": ([slide("compare-2", GOOD_CARD, title="«제목: 한 문장 ≤20자»")], 1, ["자리표시"]),
    "external-img": ([slide("compare-2", '<img src="https://example.com/a.png" alt="">')], 1, ["외부 자원"]),
    "unknown-arch": ([slide("fancy-thing", GOOD_CARD)], 1, ["아키타입"]),
    "missing-icon": ([slide("compare-2", '<svg class="ico" aria-hidden="true"><use href="#i-unicorn"/></svg>')], 1, ["아이콘"]),
    "fact-no-sources": ([slide("compare-2", '<p class="fact" data-src="F01">출처 칩</p>')], 1, ["참고 자료"]),
    "long-list": ([slide("compare-2", "<ul class=\"list\">" + "".join(f"<li>항목 {i}</li>" for i in range(8)) + "</ul>")], 0, ["목록"]),
    "low-contrast": ([slide("compare-2", '<div class="card"><p class="body" style="color:#C9C3B8">흐린 글자입니다</p></div>')], 0, ["대비"]),
    "bad-step": ([slide("compare-2", '<div class="card" data-step="x"><h3>단계</h3></div>')], 1, ["단계 값"]),
    # 아래 셋은 WARN 기준(노트 110자, 단계 7개, 제목 30자)을 잰다. 종료 코드는 0 이어야 한다
    "short-notes": ([slide("compare-2", GOOD_CARD, notes=SHORT_NOTE)], 0, ["발표자 노트"]),
    "many-steps": ([slide("compare-2", '<div class="row">' + "".join(f'<div class="card f1" data-step="{k}"><h3>{k}</h3></div>' for k in range(1, 9)) + "</div>")], 0, ["단계"]),
    "long-title": ([slide("compare-2", GOOD_CARD, title="제목이 서른 자를 넘으면 검사기가 경고를 띄워서 알려 줍니다")], 0, ["제목"]),
}

if ROOT.exists():
    shutil.rmtree(ROOT)
rows = []
for name, (extra, want_code, want_kinds) in CASES.items():
    d = ROOT / name
    (d / "src").mkdir(parents=True)
    slides = BASE[:2] + extra + BASE[2:]
    for i, s in enumerate(slides, 1):
        (d / "src" / f"{i:02d}.html").write_text(s, encoding="utf-8")
    (d / "deck.json").write_text(json.dumps({"title": name, "output": "deck.html"}), encoding="utf-8")
    b = subprocess.run(["python3", str(SKILL / "scripts/build_deck.py"), str(d)], capture_output=True, text=True)
    if b.returncode:
        rows.append((name, want_code, "build:" + b.stderr.strip()[:60], want_kinds, []))
        continue
    r = subprocess.run(["python3", str(SKILL / "scripts/check_deck.py"), str(d / "deck.html"), "--json", str(d / "check.json")],
                       capture_output=True, text=True)
    data = json.loads((d / "check.json").read_text(encoding="utf-8"))
    kinds = sorted({f["kind"] for f in data["deck"]} | {f["kind"] for s in data["slides"] for f in s["findings"]})
    rows.append((name, want_code, r.returncode, want_kinds, kinds))

ok_all = True
for name, want, got, wk, kinds in rows:
    ok = (got == want) and all(k in kinds for k in wk)
    ok_all &= ok
    print(f"{'OK ' if ok else 'BAD'} {name:16s} exit want={want} got={got}  want={wk} got={kinds}")
print("ALL OK" if ok_all else "SOME FAILED")
