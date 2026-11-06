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
EDU_DECK_TEST_DECK=<실덱경로> python3 -m unittest discover -s dev -p 'test_*py'   # 354개
python3 dev/test_pack_browser.py <아웃풋폴더>    # 64/64
python3 scripts/build_deck.py <덱폴더> && python3 scripts/check_deck.py <결과.html>
```

## 현재 상태(2026-11-07)
- 클린룸 재작성 캠페인 완료(엔진·CSS·스니펫 28종·자습 계층; 커밋 1c2d281→aab1a7f).
- 다양성 개편 완료: legacy 테마 9종(`assets/css/themes.css`, deck.json `theme`, 기본 classic 포함)·표지 변형 16종·arc 6종(기본 standard 포함)·`scripts/tone_router.py`, 팩 라우터 `scripts/pack_router.py`. 새 덱은 만들기 전에 팩/legacy 중 하나를 에이전트가 판단해 정한다(기본값 없음, 애매하면 사용자에게 한 번 묻는다. 규칙: `edu-deck/SKILL.md` "경로 결정"). 한 덱에 두 경로를 섞을 수 없다.
- 자유 모드 완료(커밋 07779cb): 기본은 자유 모드 — 조각·팩 템플릿·arc 메뉴·아키타입 표는 참고 예시이고 지시가 아니다. 재료 사용 4방식(그대로·변형·조합·새로 작성)·작업 덱 src 수정 권한·품질 판단 기준은 `shared/references/authoring.md` 한 곳에 있다. `check_deck.py`는 안전 가드(깨짐·접근성·계약)만 ERROR로 막고 취향 규칙은 INFO(`--style`에서 WARN 상세). `data-archetype` 없는 장도 허용(엔진 자동 배정). 가이드 모드는 세 경로(고침 3회 실패 자동 폴백·지시·위임)로만 진입한다(규칙: `edu-deck/SKILL.md` "자유 모드와 가이드 모드").
- design-craft(문서만): `references/design.md` 신규(디자인 판단 기준 — 회상 색인→판단→경계 골격, ppt-master·better-web-ui 원리 각용), outline 표 두 곳에 리듬 열(앵커·밀집·숨고르기) 추가, 표지 직접 설계에 방향 3안 비교 절차 추가(`edu-deck-solo/SKILL.md` 34·82·121행).
- 회귀 기준선: unittest **354**(skip 1) + pack_browser **64/64** PASS. contrast-matrix 238셀 PASS.
- 대기: GitHub 공개(insightflo/edu-deck-skills), 예시 3종 재생성, 배포 zip 재생성(dist 낡음). 한계: 테마는 색·그림자·반경만 바꾸고 장 배치는 같음.
- 작업자: Devin 은 항상 1개만. 추가 작업자는 pi(glm-zcode/glm-5.3-flash, max).
- 위임: Devin 우선(이 폴더는 devin 신뢰 경로 등록됨), pi 는 조율·검증. herdr 사용: `hc run --name <이름> --bg devin --permission-mode dangerous` + `hc send` 로 지시.
