# flint 차트 모델 스키마 — `*.flint.json`

`flint_gen.mjs`의 입력 계약. chart_gen(`schema.md`)과 **병행 엔진**이다 — 대체가 아니라 선택제. 파일명 `charts/NN-이름.flint.json` 확장자가 regen.py의 디스패치 키다.

## 언제 flint를 쓰는가

- chart_gen 15종에 없는 유형(Gantt·Ridgeline·ECDF·Radar·Calendar Heatmap·Map·KPI Card·Slope·Bullet 등 vegalite 템플릿 39종)이 필요할 때.
- 시맨틱 타입(Amount·Percentage·Month·Rank 등 47종)이 정하는 자동 축·서식·0베이스라인·정렬을 쓰고 싶을 때.
- **순차 공개(data-fx 막대 성장 등)가 필요하면 chart_gen** — flint SVG는 정적이고 조각은 그림 전체 1단계로만 등장한다.
- 주류 유형(막대·꺾은선·히트맵 등)은 둘 다 된다 — 한 덱에서는 4단계에서 정한 엔진을 기본으로 하고 특수 유형만 다른 엔진으로 보충한다(혼합 허용, deck.json `charts.engine` 기록).

## 모델 구조

```jsonc
{
  "engine": "flint",                 // 필수 — 이 키가 디스패치를 결정한다
  "flintVersion": "1.0.1",           // 생성 시 설치 버전과 다르면 WARN(바이트 diff 가능)
  "theme": "consult",                // flint-theme.json presets 키만 허용 — 임의 theme_spec·hex 금지
  "slide": {
    "eyebrow": "비용 구조",           // 생략 시 "데이터"
    "title": "주장형 제목 — 필수",
    "notes": "발표 노트(권장)",
    "ariaLabel": "스크린리더용 차트 설명(생략 시 title)",
    "class": "consult-tech"           // 덱 방향 클래스(선택, theme 과 맞춘다)
  },
  "flint": {                          // ChartAssemblyInput 그대로
    "data": { "values": [ { "항목": "인프라", "금액": 48 } ] },   // 인라인 필수 — 근거 대조
    "semantic_types": { "항목": "Category", "금액": "Amount" },
    "chart_spec": {
      "chartType": "Bar Chart",       // 템플릿 표시명(39종)
      "encodings": { "x": { "field": "항목" }, "y": { "field": "금액" } },
      "title": "차트 내부 제목",
      "baseSize": { "width": 900, "height": 420 },   // 시작값 — 슬롯은 viewBox+CSS로 맞춘다
      "canvasSize": { "width": 1200, "height": 560 } // 상한 2000×1200
    }
  },
  "source": {                          // chart_gen과 동일 계약
    "text": "근거 원장·자료 이름",
    "asOf": "2026-11",                 // 기준일(권장)
    "note": "방법론·한계(선택)",
    "synthetic": true                  // 가상 데이터면 반드시 true — "가상 데이터" 표기 강제
  }
}
```

## 금지·제한

- `theme_spec`을 모델에 직접 쓰지 않는다 — `theme` 키만. 임의 hex·외부 테마 주입은 팔레트 허용목록 게이트가 FAIL시킨다.
- 최상위 키는 `engine·flintVersion·slide·flint·theme·source` 6개뿐.
- `data.values`는 인라인 배열 필수·10,000행 상한(근거는 evidence.json claim과 대조된다).
- 난수·시각 함수·외부 URL·`<script>`는 스키마 위반 — 결정성·단일 HTML 계약.
- 렌더 백엔드는 **vegalite 정적만**(인터랙티브·image-charts·echarts 경로 없음).

## 생성·검증

```bash
node consulting-deck/charts/flint_gen.mjs --in charts/05-x.flint.json -o src/05-x.html
node consulting-deck/charts/flint_gen.mjs --in charts/05-x.flint.json -o src/05-x.html --check   # 재생성 SAME 증명
python3 consulting-deck/charts/regen.py --check <덱폴더>          # .json/.flint.json 혼합 디스패치
```

validateChart가 먼저 돌고 오류는 메시지 그대로 FAIL. 산출 SVG는 무손실 삽입(후처리 없음). 색은 flint-theme.json allowlist 안, 폰트는 Pretendard(테마 주입, 덱 내장 폰트가 해석).
