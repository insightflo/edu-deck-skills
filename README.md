# edu-deck skills — 프롬프트 하나로 한국어 교육 자료

에이전트 스킬 묶음입니다. "○○ 교육자료 만들어줘" 한 줄이면 조사→구성→저작→검증까지 거쳐 **브라우저에서 바로 쓰는 단일 HTML 교육 덱**을 만듭니다. 퀴즈·학습지·발표 덱·사례 교육 무엇이든, 발표자 노트·자습 모드·인쇄·출처 검증까지 갖춘 상태로 나옵니다.

![데모](docs/demo-quiz.gif)

## 1. 예시 4종 — 실물

모두 이 저장소의 스킬로 만든 완성 덱입니다(`examples/` 폴더에 저작 과정 파일 포함).

| 예시 | 대상 | 무엇을 보여주나 | 열어보기 |
|---|---|---|---|
| 물질의 상태 변화 단원 퀴즈 | 중1 과학 | 가이드 모드·OX/4택/분류 퀴즈 혼합·다시 보기 연결 | [examples/states-quiz](examples/states-quiz/물질의상태변화-단원평가퀴즈-교육자료.html) |
| 비와 비율 학습지 | 초6 수학 | 리소스팩(workbook)·읽는 면/해보는 면·인쇄 학습지 | [examples/ratio-worksheet](examples/ratio-worksheet/비와-비율-학습지.html) |
| 개인정보 보호 기본 | 전 직원 | 발표 덱(talk)·발표 타이머·대본 노트·20분 | [examples/privacy-talk](examples/privacy-talk/개인정보-보호-기본-교육자료.html) |
| 사고 사례로 배우는 현장 안전 | 신규 입사자 | 리소스팩(casebook)·사례 기록 문법·공개 통계 출처 | [examples/safety-casebook](examples/safety-casebook/사고-사례-현장-안전-교육자료.html) |

![예시 4종](docs/demo-variety.gif)

50초 소개 영상: [docs/brag.mp4](docs/brag.mp4)

## 2. 완성 덱 하나에 들어있는 것

- **단일 HTML, 외부 의존성 0** — 파일 하나를 브라우저로 열면 끝. 폰트(Pretendard)도 안에 들어있습니다.
- **발표자 노트**(N) — 장마다 60자 이상 노트. 자습·인쇄 본문이 됩니다.
- **자습 모드**(S) — 발표용 화면을 학습자용 본문으로 바꿉니다.
- **인쇄**(P) — 단계·해설이 모두 전개된 상태로 종이에 그대로.
- **확인 문제·퀴즈** — 틀리면 해설과 다시 보기 장으로 되돌립니다.
- **출처 검증** — 화면의 숫자마다 사실 ID. 원문 대조·두 출처 일치를 검사기가 확인합니다.
- **검색(Ctrl+K·/)·목차(O)·용어집(G)·발표 타이머(T·R)**, 단계 공개(→), 축소 화면 반응형, `prefers-reduced-motion` 존중.

## 3. 다양성 — 같은 문법, 다른 인상

- **legacy 경로**: 테마 8종 × 흐름(arc) 5종 × 표지(직접 설계 기본 + 카탈로그 7종), 장 배치 아키타입 32종 64변형, 모션 시그니처 7종.
- **리소스팩 경로**: 설계 8종(workbook·casebook·field·editorial·lab·atlas·briefing·seminar) × 학습 흐름 8종 — 팩마다 배치 문법 자체가 다릅니다.
- **표지 3안 비교** — 표지는 방향 3안을 실제로 만들어 캡처로 비교하고 1안을 채택합니다.
- **디자인 판단 기준**(`design.md`) — 위계·강조·밀도·리듬의 판단 테스트(회색조·2초·곁눈). 장마다 리듬(앵커·밀집·숨고르기)을 계획합니다.

## 4. 사용법

에이전트(pi·Claude Code·Codex 등 스킬을 이해하는 실행기)의 스킬 폴더에 이 저장소를 클론하면 끝입니다.

```bash
git clone https://github.com/insightflo/edu-deck-skills.git ~/.pi/agent/skills/edu-deck-skills
# 또는 Claude Code: git clone … ~/.claude/skills/edu-deck-skills
```

이후 에이전트에게 이렇게 요청하면 `edu-deck` 진입 스킬이 규모를 판별해 알맞은 하위 스킬로 보냅니다.

- "신입 직원용 개인정보 보호 교육자료 만들어줘" → `edu-deck-solo` (한 주제 한 덱)
- "안전 교육 6편 시리즈로 만들어, 진도 관리되게" → `edu-deck-series` (시리즈 + 포털)

자유·가이드 두 저작 모드가 있습니다. 기본은 자유 모드(에이전트가 배치를 직접 설계), 막히거나 지시받으면 가이드 문서를 따릅니다. 모델 이름으로 갈리지 않습니다.

## 5. 검증 — 검사기가 품질을 담당

`check_deck.py`가 완성 덱을 정적+렌더 검사합니다. 규칙은 두 층으로 나뉩니다.

- **안전 가드(ERROR)** — 깨진 참조·외부 자원·대비(4.5:1/3:1)·글자 18px 미만·노트 부재·계약 위반. 이걸 통과해야 완성입니다.
- **취향(INFO)** — 제목 길이·구성 반복·밀도 같은 취향 항목. `--style`을 주면 경고(WARN) 상세로 올라갑니다. 사람이 읽고 판단합니다.

저장소 자체 회귀: 단위 테스트 213개(렌더 포함, skip 1), 리소스팹 브라우저 64/64 조합, 대비 매트릭스 238셀.

```bash
cd edu-deck/shared
EDU_DECK_TEST_DECK=../../examples/states-quiz/물질의상태변화-단원평가퀴즈-교육자료.html \
  python3 -m unittest discover -s dev -p 'test_*py'   # Ran 213 tests OK
python3 scripts/check_deck.py ../../examples/states-quiz/물질의상태변화-단원평가퀴즈-교육자료.html   # 기본: 안전 가드
python3 scripts/check_deck.py --style <덱.html>   # 취향 상세
```

## 6. 구조

```
edu-deck/          진입(라우터) 스킬 + 공통: 셸·모션 엔진·조각 32종·아이콘·팩 8종·검사·조립 도구
edu-deck-solo/     한 주제 한 덱 — brief → 조사 → outline → 저작 → 검사
edu-deck-series/   여러 편 시리즈 + 목차 포털·진도·같은 편 복습
examples/          실물 예시 4종(저작 과정 포함)
docs/              데모 GIF·소개 영상·소셜카드
```

## 7. 라이선스·크레딧

- 코드·문서: [Apache-2.0](LICENSE)
- 폰트: [Pretendard](https://github.com/orioncactus/pretendard) — [OFL-1.1](edu-deck/shared/assets/fonts/OFL.txt), 각 덱 HTML에 임베드
- 디자인 판단 문서의 골격과 장 리듬 개념은 [ppt-master](https://github.com/hugohe3/ppt-master)(MIT)의 craft 규칙을, 판단 테스트·절제 원리는 better-web-ui 스킬 모음을 슬라이드에 맞게 각용해 직접 작성했습니다(`edu-deck/shared/references/design.md` 머리말에 표기).
