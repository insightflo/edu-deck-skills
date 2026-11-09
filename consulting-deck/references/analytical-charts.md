> **소유 영역**: 분석 차트의 선택(질문 기반), 5층 구조, 주석·색·출처·모션 계약. 모델 문법·타입별 검증 규칙의 원본은 `charts/schema.md`다 — 이 문서와 충돌하면 schema.md가 이긴다.
> **로드 시점**: 작업 순서 4단계(차트 모델 작성). 수치의 근거 형식은 `evidence.md`를 함께 본다.

# 분석 차트 킷 (analytical-charts)

## 1. 대원칙 — 차트는 모델에서만 나온다

- 화면에 들어가는 분석 차트는 **charts/*.json 모델 → chart_gen.mjs → src 조각** 경로로만 만든다. 조각 HTML에 수치를 직접 타이핑하지 않는다(수치-주장 불일치를 구조적으로 막는 장치다).
- 생성기가 검증한다: 합계(expectTotal)·출처 필수·가상 표기(synthetic)·주석 개수(main 1+sub 2)·highlight 실존·데이터 수 범위. FAIL은 exit 1 — 검증을 꺼서 통과시키지 않는다.
- 같은 모델은 같은 바이트를 낸다. `regen.py --check`로 재생성 계약을 확인한다.

## 2. 5층 구조 — 차트 장은 다섯 층이 다 있어야 완성이다

| 층 | 무엇 | 모델 키 |
|---|---|---|
| ① Answer | 결론형 제목 — 차트가 답하는 주장 한 문장 | `slide.title`(주장형) |
| ② Measure | 지표·단위·기간 — 독자의 눈금 맞추기 | `measure.unit`·`measure.period` → eyebrow·SVG 좌상단 |
| ③ Evidence | 데이터 관계를 보존하는 차트 본체 | `chart.type`·`data` |
| ④ Interpretation | 갭·변곡·임계를 짚는 직접 주석 | `annotations`(main 1+sub 2) |
| ⑤ Provenance | 출처·방법론·가상 표기 | `source`(text·asOf·note·synthetic) → c-note·c-src·s-syn |

한 층이라도 비면 미완성이다. 특히 ④가 없는 차트는 "여기 데이터 있습니다"일 뿐 주장이 아니다.

## 3. 질문 기반 선택표 — 차트 종류는 분석 질문이 고른다

| 계열 | 분석 질문 | 쓰는 타입(chart_gen) | 피할 것 |
|---|---|---|---|
| 편차(Deviation) | 기준선에서 얼마나 벗어났나 | `diverging-bar` | 기준선 자체가 메시지인데 무성의한 묶음 막대 |
| 순위(Ranking) | 무엇이 크고 어디에 있나 | `ranked-bar-h` | 값 정렬 안 된 막대, 소수 항목에 꺾은선 |
| 시간(Time) | 기간에 따라 무엇이 어떻게 변하나 | `line`(area는 fill 옵션) | 계열 4개 초과, 기간 선택의 근거 없는 잘라내기 |
| 구성(Part-to-whole) | 무엇이 전체를 이루고 변화를 주도하나 | `stacked-bar`·`pareto`·`waterfall` | 5조각 넘는 도넛·파이, 분모 숨기기 |
| 크기(Magnitude) | 세어진 항목끼리 크기 비교 | `ranked-bar-h`·`stacked-bar` | 계산 비율로 실물 크기를 흐리는 것 |
| 분포(Distribution) | 값들이 어떻게 퍼져 있나 | `scatter`·`heatmap` | 표본 크기 없는 분포 해석 |
| 상관(Correlation) | 두 변수는 어떤 관계인가 | `scatter`(버블=size) | 상관을 인과처럼 쓰기 — 인과 주장엔 별도 근거 |
| 흐름(Flow) | 어디서 어디로 얼마나 이동하나 | `sankey` | 노드 8개 초과의 뒤엉킴 |
| 민감도(Sensitivity) | 어떤 가정이 결론을 흔드나 | `tornado` | 대칭 축 없는 비교 |
| 매트릭스(Matrix) | 두 축의 조합에서 무엇을 고르나 | `matrix-2x2`·`heatmap` | 의미 없는 축(모든 점이 한 사분면) |

- **공간(Spatial) 계열은 이 킷 범위 밖**이다 — 지리 패턴이 필요하면 Architecture Kit·도식 조각으로 직접 설계하고 그 한계를 밝힌다.
- 타입별 데이터 계약·검증 규칙은 `charts/schema.md`가 원본이다. contribution 분해는 waterfall의 kind 구성으로 표현한다.
- 타입이 부족하면 생성기를 확장한다(schema.md 계약 유지). **수치가 있는 차트를 손으로 그리는 것으로 우회하지 않는다.**

## 4. 복잡 차트 정당화 — 단순한 것이 먼저다

- 복잡한 형태는 단순 차트가 결론에 필요한 관계를 파괴할 때만 쓴다: waterfall은 브리지 자체가 메시지일 때, 버블은 위치와 크기가 모두 결정 관련일 때, sankey는 이동량이 주제일 때.
- **10초 시험**: 발표자가 차트를 10초 익히고 모든 인코딩(색·크기·위치가 무엇을 뜻하는지)을 설명하지 못하면 단순화하거나 나눈다.
- 계열 5개 이상, 범주 10개 이상은 기본적으로 분할 대상이다(스몰 멀티플·부록 표).

## 5. 주석 — 해석이 차트 위로 올라온다

- 네 가지 종류: **직접 라벨**(값을 범례 대신 그 자리에) · **델타 라벨**(+44%p처럼 변화량) · **구조 가이드**(임계선·평균선·구간 음영) · **해석 콜아웃**(한 문장 결론 — 모델 `annotations` main).
- 규칙: 주석은 증거에 붙인다(빈 여백 장식이 아니다) · main 1 + sub ≤ 2 · 동사와 비교가 들어가야 한다("증가"보다 "3년 연속 증가해 2배") · 이미 보이는 값의 반복 금지 · 리더선 교차 금지.
- 모션 계약: 주석은 참조 항목과 같은 data-step 그룹에서 공개된다.

## 6. 색 — 역할 토큰만

- **focus+context가 기본**: 초점 1개는 `var(--accent)`, 비교·근거는 `var(--blue)`, 맥락은 `var(--muted)`. 포화색은 강조 1종만.
- 순차(heatmap)는 단일 색조 농도로 — 무지개 스케일 금지. 발산(±)은 음수 accent·양수 blue의 생성기 규칙을 따른다.
- semantic red/green은 실제 부정/긍정에만. "우리 회사=파랑, 경쟁사=빨강" 같은 편의 배정으로 긍정/부정 착시를 만들지 않는다.
- 생성기 출력에는 hex가 없다 — `var(--…)` 토큰만. 덱 로컬 테마가 토큰 값을 정한다(consulting-design.md).

## 7. 축·스케일 — 왜곡 금지가 서사보다 앞선다

- 축 생략(waterfall axis break)은 생성기 표식(사선 2개)과 함께, **수치 라벨은 실측치 그대로**. 생략으로 서사를 과장하지 않는다.
- y축 0 기준이 메시지를 바꾼다면 그 차트는 0 기준으로 그리고 주석으로 비율을 말한다.
- %는 분모를, 지수는 기준점을, 통화는 환율·기준일을 방법론 노트에 남긴다(evidence.md §4).

## 8. 출처·방법론 블록

- 모든 차트 장 하단: `Source: … · 기준 …`(c-src). 방법론·한계가 있으면 한 줄 위에(c-note). 가상 데이터면 `s-syn` "가상 데이터" 표기까지 — 생성기가 모델에서 자동 방출하니 모델을 정홝히 채운다.
- 출처·방법론이 없는 차트는 검증 FAIL이다. "Source: 자체 분석"도 계산 근거를 evidence.json에 남겨야 한다.

## 9. 모션 — 주장 뒷받침만

- 계약은 엔진 속성뿐: `data-step` 순차(워터폴 시작→드라이버→최종, 막대·계열·행 단계)·`.wf` cascade·`data-fx="bar-grow"`·`data-count` 수치 카운트업. script·SMIL·CSS 애니메이션은 0.
- 모션은 서사 순서를 따른다: 제목(주장) → 차트(증거) → 주석(해석) → 출처. 이 순서가 깨지면 단계를 다시 나눈다.
- 쓸 수 있는 계열 목록은 `<base>/references/MOTION_LIBRARY.md`를 따른다. 슬라이드별 독립 런타임을 추가하지 않는다.

## 10. 워크플로우 정리

```bash
# 1. 모델 작성: charts/NN-이름.json (schema.md 문법)
# 2. 조각 생성
node consulting-deck/charts/chart_gen.mjs --in charts/NN-이름.json -o src/NN-이름.html
# 3. 재생성 검사(전체 차트)
python3 consulting-deck/charts/regen.py --check <작업 폴더>
```

모델의 `question` 필드에 그 차트가 답하는 분석 질문을 남긴다 — 선택표(§3)의 질문과 짝이 되는지 스토리라인 검토 때 다시 본다.

---
개념 출처: zairuilab/consulting-deck(Apache-2.0, d25dd54)의 5층 스택·주석 체계·색 패턴과 McKinsey Vizro(Apache-2.0, 146b932) Visual Vocabulary의 질문 기반 분류를 재작성했다.
