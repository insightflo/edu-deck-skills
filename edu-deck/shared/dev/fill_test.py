"""글자 한도(≤N자)가 실제로 넘치지 않는지 확인하는 시험 덱 생성기.

[목적] 모든 조각의 자리표시를 '한도만큼 꽉 찬' 한국어 채움 글자로 바꿔 덱을 만든다.
  check_deck.py 화면 검사에서 넘침·잘림이 나오면 그 자리의 한도 N 이 너무 크다는 뜻이다.
[출력] 인자 폴더(기본 /tmp/edu-deck-filltest)에 deck.json, src/*.html
"""
import pathlib, re, shutil, json

import sys, tempfile
SNIP = pathlib.Path(__file__).resolve().parent.parent / "assets" / "snippets"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(tempfile.gettempdir()) / "edu-deck-filltest"
SYL = "가나다라마바사아자차카타파하거너더러머버서어저처커터허고노도로모보소오조초"
# P1-2 실물 화면 자리 채움용 합성 PNG(웹 캡처 아님 — 프로그램 생성 픽스처, 24×14·97B).
# 예산 안쪽 크기라 채움 시험의 라스터 합계 검사도 그대로 통과한다.
TINY_PNG_DATA = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAOCAIAAAC6mkspAAAAKE"
                 "lEQVR42mPQz99AFcQw+Az6//cHEL0o10NGpAoC0ahBowZRAw0+gwAvpcFnqKiKMwAAAABJRU5ErkJggg==")


def filler(n: int, seed: int) -> str:
    """n자(공백 포함) 한국어 채움 글. 3~4자마다 띄어 써서 실제 문장처럼 줄바꿈되게 한다."""
    out, k = [], seed
    while len("".join(out)) < n:
        w = 3 + (k % 2)
        out.append("".join(SYL[(k + i) % len(SYL)] for i in range(w)))
        out.append(" ")
        k += 7
    return "".join(out)[:n].rstrip() or "가"


if OUT.exists():
    shutil.rmtree(OUT)
(OUT / "src").mkdir(parents=True)
seed = 0
for p in sorted(SNIP.glob("*.html")):
    t = re.sub(r"<!--.*?-->", "", p.read_text(encoding="utf-8"), flags=re.S)

    def rep(m):
        global seed
        seed += 1
        body = m.group(1)
        if body.startswith("발표자 노트"):
            return filler(150, seed)
        if body.startswith("사용자가 제공한"):
            # 실물 화면 이미지 자리는 로컬 생성 합성 PNG data URL 로 채운다(P1-2 픽스처 원칙).
            return TINY_PNG_DATA
        if body.startswith("숫자"):
            # 숫자 필드는 숫자 모양으로 채워야 실제 폭을 잰다(한글 채움은 숫자 폭의 약 1.8배). «숫자 ≤12자» 참고.
            nm2 = re.search(r"≤(\d+)자", body)
            return "1234567890"[: int(nm2.group(1))] if nm2 and int(nm2.group(1)) <= 10 else "9" * (int(nm2.group(1)) if nm2 else 6)
        if body.startswith("https://") or "원문 주소" in body:
            return "https://www.law.go.kr/"
        if re.fullmatch(r"F\d+", body):
            return body
        nm = re.search(r"≤(\d+)자", body)
        if nm:
            return filler(int(nm.group(1)), seed)
        if body in ("값",):
            return "12"
        if body == "발행일":
            return "2026-10-30"
        return filler(6, seed)
    t = re.sub(r"«([^»]*)»", rep, t)
    # 아키타입별 조각 파일을 한 장씩 나눈다 (sources 슬라이드는 마무리 앞에 두기 위해 이름 조정)
    secs = re.findall(r"<section\b.*?</section>", t, flags=re.S)
    for i, s in enumerate(secs, 1):
        (OUT / "src" / f"{p.stem}-{i}.html").write_text(s + "\n", encoding="utf-8")
(OUT / "deck.json").write_text(json.dumps({"title": "채움 시험", "output": "filltest.html"}, ensure_ascii=False), encoding="utf-8")
print("slides:", len(list((OUT / "src").glob("*.html"))))
