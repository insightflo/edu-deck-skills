# edu-deck-skills 작업 안내

한국어 교육 덱(단일 HTML) 스킬 묶음 저장소. 진입은 `edu-deck/SKILL.md`, 공통 자산은 `edu-deck/shared/`.

## 규칙
- 생성 셸 `shared/assets/shell.html`·`pack-shell.html` 은 직접 고치지 않는다. `python3 shared/dev/port.py` 로만 재생성.
- 클래스·속성 계약(data-step/add/only/lit/until, .chk, aside.notes, st-* 클래스, localStorage 키, window.EDU_STUDY/deckGo/deckInfo)은 다른 모듈이 의존하므로 함부로 바꾸지 않는다.
- `dist/`, `workspace/`, `shared/--help/`, `TASK-*.md`, 캐시는 gitignore 대상. 작업 산출물·덱 결과물은 저장소 밖(`EDU_DECK_OUTPUT_DIR` 또는 `./outputs`)에 둔다.
- 외부 자산 복사 금지: 라이선스 확인 전 것은 가져오지 않는다(effective-html 은 MIT, licenses/ 참조). Koboyo 갤러리는 스킬 밖 파일만 쓰고 덱에 쓰는 아이콘만 복사.

## 검사
```bash
cd edu-deck/shared
EDU_DECK_TEST_DECK=<실덱경로> python3 -m unittest discover -s dev -p 'test_*py'   # 160개
python3 dev/test_pack_browser.py <아웃풋폴더>    # 64/64
python3 scripts/build_deck.py <덱폴더> && python3 scripts/check_deck.py <결과.html>
```

## 현재 상태(2026-11-05)
- 클린룸 재작성 캠페인 완료(엔진·CSS·스니펫 28종·자습 계층; 커밋 1c2d281→aab1a7f).
- 다양성 개편 완료: legacy 테마 8종(`assets/css/themes.css`, deck.json `theme`)·표지 변형 6종·arc 5종·`scripts/tone_router.py`, 팩 라우터 `scripts/pack_router.py`. 새 덱 기본은 팩, legacy는 요청하거나 팩에 없는 조각이 필요할 때. 회귀: unittest 187(skip 1) + pack 64/64.
- 대기: GitHub 공개(insightflo/edu-deck-skills), 예시 3종 재생성, 배포 zip 재생성(dist 낡음). 한계: 테마는 색·그림자·반경만 바꾸고 장 배치는 같음.
- 작업자: Devin 은 항상 1개만. 추가 작업자는 pi(glm-zcode/glm-5.3-flash, max).
- 위임: Devin 우선(이 폴더는 devin 신뢰 경로 등록됨), pi 는 조율·검증. herdr 사용: `hc run --name <이름> --bg devin --permission-mode dangerous` + `hc send` 로 지시.
