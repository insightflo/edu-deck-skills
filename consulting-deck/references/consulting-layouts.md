> **소유 영역**: 컨설팅 덱의 배치 카탈로그 — 19 유형의 목적·수용량·만드는 법과 선택 규칙. 공통 조각·아키타입 목록은 `<base>/references/layouts.md`가, 판단 기준은 `<base>/references/authoring.md`가 소유한다.
> **로드 시점**: 작업 순서 5단계 — 장마다 배치를 고를 때. 카탈로그는 후보 재료지 지시가 아니다.

# 컨설팅 배치 카탈로그 (consulting-layouts)

## 0. 쓰는 법

- **커뮤니케이션 임무가 먼저다.** 장의 페이지 역할(storyline.md §7)을 정하고, 그 임무를 담는 최소 배치를 고른다.
- 수용량을 넘으면 **나눈다** — 글자를 줄이거나 여러 항목을 우겨넣는 게 아니라 장을 분할하거나 표·부록으로 보낸다. 다차원 원본을 히어로 숫자 3개로 축소하지 않는다.
- 저작은 `<base>/references/authoring.md`의 재료 4방식(그대로·변형·조합·새로 설계)을 따른다. 아래 "만드는 법"은 출발점 재료의 안내다.

## 1. 방향·요약 (덱의 문)

| # | 유형 | 목적 | 수용량 | 만드는 법 |
|---|---|---|---|---|
| 1 | Executive Cover | 과제·결정·기한을 문에 새긴다 | 주장 1 + 메타 2~3줄 | 표지 변형(`<base>/references/layouts.md`) — 은유 장치는 하나까지만 |
| 2 | Executive Summary | 통치 사상+인사이트 3~5+권고 2~4, 결론 요약 | 불릿 3~5, 수치 1~3 | c-glance(At-a-Glance 3불릿)·c-metrics·c-rule-rows. 본문 완성 뒤 마지막 제작(storyline.md §9) |

## 2. 문제 정의·분해

| # | 유형 | 목적 | 수용량 | 만드는 법 |
|---|---|---|---|---|
| 3 | SCQA/Problem Definition | 결정 질문·범위·성공 기준을 못 박는다 | S·C·Q 3블록 + 답 1 | 직접 설계(s-pair·stage 계열 조각 변형). 문제해결형에서만 |
| 4 | Issue/Hypothesis Tree | 질문을 증명 가능한 가지로 나눈다 | 2~4분지 × 2~3단계 | 도식 조각(diagrams.md)으로 직접 설계. 가지 수가 캔버스를 넘기면 축소가 아니라 구조 재검토 |
| 5 | Market Sizing | 시장 크기·성장을 단계로 쌓는다 | 구성 요소 3~6 | waterfall 차트(chart_gen) 또는 TAM-SAM-SOM 단계 조각 |

## 3. 정량 증거 — 차트가 주인공인 장

| # | 유형 | 목적 | 수용량 | 만드는 법 |
|---|---|---|---|---|
| 6 | Performance Dashboard | 핵심 지표의 현재 상태를 한눈에 | 지표 3~6 | c-metrics + 필요 시 소형 차트. 지표마다 기준·기간 표기 |
| 7 | Trend & Growth Drivers | 추이와 그 이유를 함께 | 계열 1~4 | line/area 차트(chart_gen) + 원인 주석(main1·sub2) |
| 8 | Comparison/Benchmark | 우리와 기준(경쟁·업계) 비교 | 항목 3~10 | ranked-bar-h·diverging-bar·표(c-table, rec 행 강조) |
| 9 | 2×2 Matrix | 두 축 위에서 선택지를 재배치한다 | 점 4~12 + 사분면 라벨 4 | matrix-2x2(chart_gen, targetQuadrant로 목표 사분면 틴트). 축 라벨·한계선 필수 |
| 10 | Competitive Positioning | 경쟁 구도·우리의 자리 | 경쟁자 3~8 | matrix-2x2 또는 scatter. 점 라벨 겹침 주의 |
| 11 | Value Driver/Waterfall | 값의 이동(증감·브리지)을 분해한다 | 드라이버 3~8 | waterfall(chart_gen, expectTotal 필수). contribution 분해도 이 유형 |
| 11-b | Chart + Sidecar | 증거(차트)와 시사점(읽을 것)을 한 장에 짝짓는다 | 차트 1 + 헤드라인 수치 1 + 불릿 ≤3 | chart_gen `canvas:"sidecar"` + `chart.sidecar` — 차트 68% + 시사점 칼럼 32%(`.c-sidecar`, 상단 3px accent 룰). 결론이 차트 안에 안 쓰이면 쓴다 — 제목·사이드카가 같은 주장을 말하게 |
| 11-c | Structure/Stacked Compare | 합계 차이와 구성 이동을 함께 본다 | 막대 2~6 × 세그먼트 ≤6 | stacked-bar(chart_gen) — `bridge:"total"`(총계 다리+변화율 캡슐) 또는 `bridge:"segment"`+`bridgeSegments`(선택 세그먼트 브래킷+합계) |

## 4. 선택·실행 — 결정과 움직임

| # | 유형 | 목적 | 수용량 | 만드는 법 |
|---|---|---|---|---|
| 12 | Options & Trade-offs | 대안을 기준으로 비교해 고른다 | 대안 2~4 × 기준 3~5 | c-table(평가 기준×대안, 권고 행 rec 강조) + 결론 라인 |
| 13 | Prioritization | 후보를 영향·난이도로 줄 세운다 | 이니셔티브 5~12 | matrix-2x2(영향×실행 난이도) 또는 ranked 표 |
| 14 | Operating Model/Architecture | 목표 조직·시스템 구조를 그린다 | 컴포넌트 3~6 | Architecture Kit(`<base>/references/architecture.md`) — 레인·레이어·아이소 계열 |
| 15 | Transformation Roadmap | 단계·워크스트림·이정표를 짠다 | 워크스트림 3~5 × 기간 3~6 | 로드맵 도식 조각 + swinlane/lanes 계열. 90일/분기 경계 표기 |
| 16 | Initiative Portfolio | 실행 과제 묶음과 상태·주체 | 과제 4~10 | c-table 또는 c-rule-rows(레이블 열+본문 열의 헤어라인 목록, `.rr.hot`로 초점 행) — 면 채움 카드 그리드는 지양 |
| 17 | Risk & Mitigation | 위험과 완화 대책을 짝지운다 | 위험 4~8 | 표(위험×영향×완화×주체) — 위험마다 완화가 빈칸이면 안 됨 |

## 5. 마감·부록

| # | 유형 | 목적 | 수용량 | 만드는 법 |
|---|---|---|---|---|
| 18 | Recommendation/Decision | 권고를 명령형으로 못 박고 결정을 요청한다 | 권고 3~5 + 결정 요청 1~3 | c-do(권고 블록) + c-rule-rows(결정 요청 목록 — 항목마다 주체·근거를 한 줄씩). 진단으로 끝내지 않는다 |
| 19 | Appendix/Evidence | 원본·상세를 본문 흐름 밖에 보관한다 | 장 당 표 4~12행×3~8열 | 표·전시 조각. 페이지 번호·원장 ID를 남겨 소환 가능하게 |

## 6. 선택 규칙

1. **임무 → 최소 배치.** 역할(prove)이면 정량 증거군(6~11), 역할(decide)이면 12·18. 임무 없는 장은 만들지 않는다.
2. **수용량 초과 = 분할.** 축소·글자 축소로 해결하려 하지 않는다. 부록(19)으로 넘겨도 된다.
3. **배치 다양성**: 7~9장이면 서로 다른 유형 5개 이상, 10~15장이면 7개 이상. 같은 실루엣(예: 표 3연속, 막대 3연속)을 3장 연속 쓰지 않는다. 증명 장(prove)과 종합 장(assert·compare)을 교대로 놓는다.
4. **히어로 주장 배치는 절제.** 큰 숫자 1개+한 문장 유형의 장은 덱에서 1~2장(Exec Summary·핵심 발견)까지만.
5. **2×2·플라이휠·퍼널은 구조가 실재할 때만.** 축에 의미 있는 변화가 없으면 2×2는 목록일 뿐이다.
6. **같은 그리드 정렬.** 대안 비교·로드맵처럼 같은 종류의 장은 덱 전체에서 같은 골격을 쓴다.
7. **면 채움 카드 대신 룰.** 목록·묶음 장은 헤어라인과 컬럼으로 짠다 — c-glance(상단 잉크 룰 3열)·c-rule-rows(룰 행 목록)·c-sonw(좌측 룰 2칸). 면을 칠하는 곳은 추천 행·권고 블록(c-do)처럼 결정 지점뿐이다.
8. **차트 장은 증거+시사점 짝.** "그래서 무엇인가"가 제목에 담기지 않는 차트 장은 사이드카(11-b)로 시사점 칼럼을 붙인다 — 사이드카는 덱당 2~4장, 모든 차트 장에 걸지 않는다(걸면 같은 실루엣 연속 위반).

## 7. 고정 템플릿 금지

이 카탈로그는 배치의 역할과 수용량을 정할 뿐, 시각 결과를 강제하지 않는다. 각 유형의 실제 모양은 재료 4방식(`<base>/references/authoring.md` §3)으로 내용에 맞게 만든다 — 스니펫 변형, chart_gen 조각, Architecture Kit 결합, `src/` 직접 설계. 카탈로그 유형 이름을 화면에 표기할 필요는 없다.

---
개념 출처: zairuilab/consulting-deck(Apache-2.0, d25dd54)의 레이아웃 수용량·선택 규칙(45종 중 과제 §4.2의 19종 서브셋)을 재작성했다.
