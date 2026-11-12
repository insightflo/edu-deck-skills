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
| `type` | ● | `waterfall` · `ranked-bar-h` · `diverging-bar` · `stacked-bar` · `line` · `scatter` · `heatmap` · `matrix-2x2` · `tornado` · `sankey` · `pareto` |
| `question` | ● | 이 차트가 답하는 분석 질문 — 조각 주석과 aria 폴백에 남는다 |
| `measure.unit` | ● | 값의 단위(%, 억 원, 명 …) — 막대 라벨엔 붙이지 않고 eyebrow·SVG 좌상단 `(단위: …)`에 표시 |
| `measure.period` | | 기간(FY25, 2026 상반기 …) |
| `measure.x` · `measure.y` | scatter · matrix-2x2 ● | 축 라벨 — 없으면 FAIL(좌표 차트는 축이 없으면 읽을 수 없다) |
| `measure.axisBreak` | waterfall | 숫자 — 축 생략 하한값. `0 < axisBreak < 최소누적`이면 그 값으로 생략 구간을 정하고, 범위 밖이면 WARN 후 자동 규칙으로 돌아간다. 생략 활성 시 증감 막대는 18px 가시 하한을 적용한다(상단 누적 위치는 실값 유지, 라벨은 실측치) |
| `canvas` | | `full`(기본) \| `sidecar` — `sidecar`면 차트 캔버스를 화면 약 68% 폭으로 굽는다(`chart.sidecar`와 짝, 아래). 불일치 시 WARN |
| `sidecar` | | `{k?, v, unit?, h?, bullets[]}` — 차트 우측의 시사점 칼럼(`.c-sidecar` 방출). `v`=헤드라인 수치 필수 · bullets 1~3개(초과 FAIL) · `k` 생략 시 `시사점` |
| `bridge` | stacked-bar | `total` \| `segment` — 두 막대 사이 다리. `total`=첫↔끝 총계를 계단 점선+캡슐 변화율(%, Δ절대값)로. `segment`=끝 막대의 선택 세그먼트에 브래킷+합계·비중 |
| `bridgeSegments` | stacked-bar | 세그먼트 name 배열 — `bridge:"segment"`의 대상(name 해석 실패 → FAIL) |
| `targetQuadrant` | matrix-2x2 | `tr`\|`tl`\|`br`\|`bl` — 목표 사분면을 옅은 초점색 틴트+굵은 라벨로 표시(값은 위치: 우상·좌상·우하·좌하) |
| `endDelta` | line | `true` — 마지막 눈금에서 계열 1·2의 끝점 사이를 점선 세로 브리지+`Δ값·배수` 라벨로 잇는다(계열 ≥2 필요). 사이드카 결합 시 문장 주석 대신 쓰는 수치 기호 |
| `data` | ● | 행 배열(대부분 타입) 또는 객체 — heatmap `{rows,cols,cells}` · sankey `{nodes,flows}` (아래 타입별 표) |
| `series[]` | line ● | `[{name, points:[v…], fill?}]` — points 수 = data 수, 계열 최대 4, `fill:true`는 면적 변형 |
| `axes` | matrix-2x2 ● | `{x:{min,max,label}, y:{min,max,label}}` — 사분면 축 범위 |
| `quadrants` | matrix-2x2 | `{nw,ne,sw,se}` — 사분면 라벨 4귀퉁이 |
| `highlight[]` | | 강조할 label — data 에 없는 label 은 FAIL(타입별 참조 대상은 아래 표) |
| `annotations[]` | | `{ label, on, kind:"main"|"sub" }` — **main 최대 1 · sub 최대 2** 초과 FAIL, `on` 은 실존 label |
| `calc.expectTotal` | waterfall · pareto | waterfall: 시작+증감 합계 주장값 — 불일치 FAIL · pareto: 명시 총합 |

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

### 타입별 데이터 수·형태·추가 규칙

| type | 수·형태 | 추가 규칙 | 주석·강조 `on` |
|---|---|---|---|
| `waterfall` | 3~8 `{label,value,kind?,oneoff?}` | `calc.expectTotal` 필수. `base.value + Σdelta ≠ expectTotal` → FAIL · 마지막 total ≠ 누적 → FAIL · 누적<0 → WARN | 항목 label |
| `ranked-bar-h` | 3~10 `{label,value}` | `value < 0` → FAIL(음수 순위는 diverging-bar). 출력은 value 내림차순·label 오름차순 | 항목 label |
| `diverging-bar` | 3~9 `{label,value}` | 부호가 한쪽뿐이면 WARN — 입력 순서 유지 | 항목 label |
| `stacked-bar` | 2~6 `{label,segments:[{name,value,oneoff?}],total?}` | 세그먼트 ≤6·이름 ≤6종·양수만. `total` 명시 시 `Σsegments ≠ total` → FAIL. 세그먼트 색은 이름별 농도 램프(강조 name 은 `--accent`), 범례는 테두리 있는 스와치. `bridge` 옵션으로 총계·세그먼트 다리 | 막대 label · 세그먼트 name |
| `line` | x 3~12 `{label}` + `series` | 계열 1~4 · points 수 ≠ x 수 → FAIL. x 라벨은 슬롯 초과 시 −38° 회전 | x label · series name |
| `scatter` | 4~30 `{x,y,label?,size?}` | `measure.x·y` 필수 · `size>0`(버블 반경 √비례). 무명 점은 step1 배경 | 점 label |
| `heatmap` | `data:{rows,cols,cells:[{r,c,v}]}` | 행·열 각 2~8 · cells 4~64 · r,c 중복/범위 밖 → FAIL · 빠진 셀은 빈 칸(점선 테두리). 색은 `color-mix(var(--blue) pct)` 단일 hue · 강조 행/열은 `--accent` hue. 범례는 min→max 그라디언트 바 | 행·열 label |
| `matrix-2x2` | 4~12 `{label,x,y,highlight?}` | `axes` 필수 · 범위 밖 점은 경계로 이동+WARN · `targetQuadrant`로 목표 사분면 틴트. 단계 압축: 축(1)→비초점 점 일괄(2)→초점 점+주석(3) | 점 label |
| `tornado` | 3~8 `{label,low,high,base?}` | `low ≥ high` → FAIL · 대칭축 ±max(|low|,|high|) · 출력은 범위(high−low) 내림차순 | 항목 label |
| `sankey` | `data:{nodes:[{id,label?}],flows:[{from,to,value}]}` | 노드 3~12 · flows 2~18 · from/to 미존재·자기순환·순환 그래프·value≤0 → FAIL. 열은 최장 경로 깊이, 밴드 두께=값 비례 | 노드 label |
| `pareto` | 4~10 `{label,value}` | `value ≤ 0` → FAIL · 단위 `%`면 합계≈100(비율 모드) · `calc.expectTotal` 있으면 합계 검증 | 항목 label |
| `bullet` | 2~8 `{label,value,target}` | `value`/`target` 숫자·음수 → FAIL. 트랙 전폭 위 값 막대 + 목표 세로선, 목표 초과는 `--accent` | 항목 label |
| `dumbbell` | 2~8 `{label,before,after}` | `before`/`after` 숫자. 빈 원=이전·찬 원=이후 + Δ 자동 표기(값-값 스케일은 공통 범위) | 항목 label |
| `slope` | 3~10 `{label,before,after}` | `before`/`after` 숫자. 최대 \|Δ\| 항목만 `--accent` 강조, 나머지는 muted | 항목 label |
| `waffle` | 2~5 `{label,value}` | `value` 0~100 · 합계≈100 아니면 FAIL(10×10 칸=100%). 0은 0칸 | 항목 label |

**gauge(반원 게이지)는 만들지 않는다** — 스니펫 `07-meter` 가 이미 커버한다(중복 방지, kodoc round2 8번 판정).

**contribution/decomposition 차트는 별도 타입이 아니다** — waterfall의 `kind` 구성으로 표현한다
(base→delta→delta… 로 매출→비용→이익 분해). 구성 요소의 마지막을 `total`로 두면
`expectTotal` 검증이 그대로 적용된다.

## source

| 키 | 필수 | 규칙 |
|---|---|---|
| `text` | ● | 출처 문자열 — 없으면 FAIL(근거 없는 수치 금지) |
| `asOf` | 권장 | 기준일 — 없으면 WARN |
| `note` | | 방법론·한계 한 줄 — 있으면 출처 아래 둘째 줄로 방출 |
| `synthetic` | ● | `true`/`false` 명시 필수 — `true`면 출처 블록에 "가상 데이터" 강제 표기 |

## 출력 계약

- `<section class="slide[ class추가]" data-archetype="waterfall|chart-bar|chart-line|heatmap-grid|quadrant|sankey-flow" data-variant="…">` — 타입→archetype·variant 는 생성기의 TYPES 표가 원본이다.
  + `div.head(eyebrow+h2.title)` + `svg.dg(viewBox 1560×H, sidecar 캔버스는 1040×H)` + 출처 블록 `div.c-src` + `aside.notes`.
- 사이드카(`canvas:"sidecar"` + `chart.sidecar`) 시 본문은 `.c-sidecar` 그리드로 방출된다:
  ```html
  <div class="c-sidecar">
    <div class="c-sidecar-main"><svg class="dg" viewBox="0 0 1040 H">…</svg></div>
    <aside class="c-sidecar-panel" data-step="n">
      <p class="sc-k">시사점</p><p class="sc-v">«v»<small>«unit»</small></p>
      <p class="sc-h">«h»</p>
      <ul><li>…</li></ul>                    <!-- bullets 1~3 -->
    </aside>
  </div>
  ```
  **덱 로컬 CSS가 `c-sidecar` 계열 클래스를 정의해야 한다**(consult.css 참조). 출처·노트는 사이드카 밖, 단계 마지막에 그대로 둔다.
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
- 주석은 참조 항목(`on`)의 단계 그룹 안에 캡슐 배지 「핵심」(main)·「참고」(sub) + 본문으로 붙는다 — 배지는 main=초점색·sub=중립 칩, 필요 시 `var(--accent)` 점선 리더로 항목과 연결.
  - waterfall: 항목 폭 안 2줄까지 절사 — 연결선 위 빈 공간 또는 항목 라벨 아래.
  - ranked·diverging: 수치 오른쪽(음수는 왼쪽)에 인라인 — 공간이 모자라면 막대 아래로 내려 행 높이를 가산. 어떤 경우든 다른 행 라벨과 겹치지 않는다.
  - heatmap: 행·열 주석을 격자 아래 주석 레인에 순차 누적 — 같은 단계에 두 블록이 나란히 서지 않아 수평 충돌을 원천 제거. 범례는 우상단(단위 태그 행).
  - matrix-2x2: 라벨은 점 근처 후보 6자리(우→좌→우상→좌상→하→상) 중 충돌 없는 첫 자리 — 못 찾으면 아래 레인으로만 밀고 점→라벨 헤어라인 리더. 주석도 라벨 아래 레인.
  - **역할 분리(사이드카 결합 시)**: `canvas:"sidecar"`면 문장형 `annotations`는 사이드카 bullets 로 옮기고 차트 안에는 `endDelta`·`targetQuadrant`·highlight 같은 수치·기호만 남긴다(중복 방지·재크리틱 Blocker-2).

## 재생성 계약

- 같은 모델 → 같은 바이트(시간·난수·로캘 의존 함수 없음). `--check`는 -o 파일과 바이트 비교로 diff 시 exit 1.
- 검증 FAIL 은 모두 exit 1: 스키마 필수 누락 · 합계 불일치 · 출처/synthetic 누락 · 주석 초과 ·
  highlight/on 미해결 참조 · 데이터 수 범위 이탈 · 음수(ranked) · label 중복.
- 예시: `consulting-deck/charts/examples/` — `wf-it-cost`(waterfall) · `rb-ai-gap`(ranked) · `db-cost-yoy`(diverging).
