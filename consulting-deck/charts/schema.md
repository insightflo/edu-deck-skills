# charts.json 스키마 — chart_gen.mjs 입력 모델 (초안)

선언적 차트 모델: **원본 데이터·계산·분석 질문·강조·주석·출처를 분리**해 보존하고,
`chart_gen.mjs`가 이 모델만으로 완성된 슬라이드 조각(`section.slide` + 인라인 `svg.dg`)
을 빌드 시점에 굽는다. 산출물에는 레이아웃 엔진이 남지 않는다(런타임 의존 0).

```
consulting-deck/charts/chart_gen.mjs --in MODEL.json -o src/NN-이름.html
```

## 최상위 구조

| 키 | 필수 | 내용 |
|---|---|---|
| `slide` | ● | `{ eyebrow, title, notes, ariaLabel }` — 슬라이드 문자열 |
| `chart` | ● | 차트 정의(아래) |
| `source` | ● | `{ text, asOf, note?, synthetic }` — 출처·방법론·가상 표기 |

## slide

| 키 | 필수 | 규칙 |
|---|---|---|
| `title` | ● | 주장형 제목 한 문장 — `h2.title`로 그대로 방출 |
| `eyebrow` | | 생략 시 `«단위» · «기간»`으로 자동 합성 |
| `notes` | 권장 | 발표 노트 → `aside.notes` |
| `ariaLabel` | | 생략 시 `«type» — «question»`으로 합성 |
| `class` | | 슬라이드 클래스 — `section.slide`에 덧붙는다(덱 로컬 테마 훅, 예: `"consult"`) |

## chart

| 키 | 필수 | 규칙 |
|---|---|---|
| `type` | ● | `waterfall` · `ranked-bar-h` · `diverging-bar` |
| `question` | ● | 이 차트가 답하는 분석 질문 — 조각 주석과 aria 폴백에 남는다 |
| `measure.unit` | ● | 값의 단위(%, 억 원, 명 …) — 막대 라벨엔 붙이지 않고 eyebrow·SVG 좌상단 `(단위: …)`에 표시 |
| `measure.period` | | 기간(FY25, 2026 상반기 …) |
| `measure.axisBreak` | waterfall | 숫자 — 축 생략 하한값. `0 < axisBreak < 최소누적`이면 그 값으로 생략 구간을 정하고, 범위 밖이면 WARN 후 자동 규칙으로 돌아간다. 생략 활성 시 증감 막대는 18px 가시 하한을 적용한다(상단 누적 위치는 실값 유지, 라벨은 실측치) |
| `data[]` | ● | `{ label, value, kind?, oneoff? }` — label 은 유일·비어있으면 안 됨, value 는 유한 숫자, `oneoff:true`는 delta 전용(아래) |
| `highlight[]` | | 강조할 label — data 에 없는 label 은 FAIL |
| `annotations[]` | | `{ label, on, kind:"main"|"sub" }` — **main 최대 1 · sub 최대 2** 초과 FAIL, `on` 은 실존 label |
| `calc.expectTotal` | waterfall ● | 시작(base)+증감(delta) 합계의 주장값 — 불일치 시 FAIL |

### data[].kind (waterfall 만 의미 있음)

| kind | 의미 | 위치 규칙 |
|---|---|---|
| `base` | 시작 전액 막대 — `var(--ink)`(k-solid-n) | 첫 항목만 |
| `delta` | 부유 증감 막대 — 기본 `var(--blue)`(k-solid-b) · highlight면 `var(--accent)` | 중간 항목 |
| `total` | 최종 전액 막대 — `var(--ink)`(k-solid-n) + 숫자 count-up | 마지막 항목만 |

kind 생략 시 위치로 추론한다(첫=base, 끝=total, 중간=delta). 명시하면 위치 규칙과 일치해야 한다.

- `data[].oneoff: true` (delta 전용): 일회성 요인 막대 — `fill: var(--muted)` + `stroke: var(--soft)`로 반복 delta와 시각 분리. base·total에 붙이면 무시.

### 축 생략(axis break)

waterfall의 시작 막대가 최대값의 60% 이상이면 증감 막대가 너무 낮아지므로 스케일을 자동 생략한다.

- 발동: 자동 — `base.value / max(전체 값·누적) >= 0.6` · 명시 — `measure.axisBreak`(위 표).
- 스케일: 생략 하한 `brk`부터 최대값까지를 플롯 높이에 선형 대응 → **증감 막대 최소 18px** 보장. total이 brk 아래면 기준선 아래 스텁으로 표시.
- 표기: base·total 막대 하단에 사선 2개(`stroke="var(--line)"`)의 표준 축 생략 마크. **수치 라벨은 실제 값 그대로**(압축 스케일 반영 안 함).

### 타입별 데이터 수·추가 규칙

| type | data 수 | 추가 규칙 |
|---|---|---|
| `waterfall` | 3~8 | `calc.expectTotal` 필수. `base.value + Σdelta.value ≠ expectTotal` → FAIL · 마지막 `total.value ≠ 누적` → FAIL · 누적<0 → WARN |
| `ranked-bar-h` | 3~10 | `value < 0` → FAIL(음수 순위는 diverging-bar). 출력은 value 내림차순·label 오름차순 정렬 |
| `diverging-bar` | 3~9 | 부호가 한쪽뿐이면 WARN(0축 발산 무의미 — ranked-bar-h 권고). 입력 순서 유지 |

## source

| 키 | 필수 | 규칙 |
|---|---|---|
| `text` | ● | 출처 문자열 — 없으면 FAIL(근거 없는 수치 금지) |
| `asOf` | 권장 | 기준일 — 없으면 WARN |
| `note` | | 방법론·한계 한 줄 — 있으면 출처 아래 둘째 줄로 방출 |
| `synthetic` | ● | `true`/`false` 명시 필수 — `true`면 출처 블록에 "가상 데이터" 강제 표기 |

## 출력 계약

- `<section class="slide[ class추가]" data-archetype="waterfall|chart-bar" data-variant="bridge|ranked|diverging">`
  + `div.head(eyebrow+h2.title)` + `svg.dg(viewBox 1560×H)` + 출처 블록 `div.c-src` + `aside.notes`.
- SVG 좌상단에 `(단위: «unit»)` 표기(k-t-tag). 색은 `var(--…)` 토큰만(hex 0).
  막대 색: waterfall — base·total `var(--ink)` · delta `var(--blue)` · highlight `var(--accent)` · oneoff `var(--muted)`+`var(--soft)` 테두리.
  ranked — highlight 주황(var(--accent))·나머지 파랑(var(--blue)), diverging — 음수 주황·양수 파랑.
- 출처 블록(단계 마지막에 함께 발화):
  ```html
  <p class="c-note" data-step="n"><b>방법론·한계</b> — …</p>   <!-- source.note 있을 때만 -->
  <div class="c-src" data-step="n">
    <p>Source: … · 기준 …</p>
    <p class="s-syn">가상 데이터</p>                            <!-- source.synthetic 일 때만 -->
  </div>
  ```
  **덱 로컬 CSS가 `c-note`·`c-src`·`s-syn` 3클래스를 정의해야 한다**(생성 조각엔 스타일이 없다).
- 모션은 엔진 속성만: `data-step` 단계 그룹 · waterfall `.wf`(cascade) · bar `data-fx="bar-grow"`
  (transform-box:fill-box 로 방향별 기준 고정) · total 수치 `data-count`. script·SMIL·CSS 애니메이션 0.
- 단계 구성: waterfall 시작(1)→증감 순차(2~n-1)→최종(n) · ranked·diverging 막대당 1단계.
- 주석은 참조 항목(`on`)의 단계 그룹 안에 「핵심」(main, 24px)·「참고」(sub, 20px) 표식으로 붙는다.
  - waterfall: 항목 폭 안 2줄까지 절사 — 연결선 위 빈 공간 또는 항목 라벨 아래, `var(--accent)` 점선 리더로 막대와 연결.
  - ranked·diverging: 수치 오른쪽(음수는 왼쪽)에 인라인 — 공간이 모자라면 막대 아래로 내려 행 높이를 가산. 어떤 경우든 다른 행 라벨과 겹치지 않는다.

## 재생성 계약

- 같은 모델 → 같은 바이트(시간·난수·로캘 의존 함수 없음). `--check`는 -o 파일과 바이트 비교로 diff 시 exit 1.
- 검증 FAIL 은 모두 exit 1: 스키마 필수 누락 · 합계 불일치 · 출처/synthetic 누락 · 주석 초과 ·
  highlight/on 미해결 참조 · 데이터 수 범위 이탈 · 음수(ranked) · label 중복.
- 예시: `consulting-deck/charts/examples/` — `wf-it-cost`(waterfall) · `rb-ai-gap`(ranked) · `db-cost-yoy`(diverging).
