> **로드 시점**: 아키텍처·구성도·배포도 장을 만들 때. 어떤 축(부품)을 쓸지 정하고, 시맨틱 JSON 을 쓰고, 모션을 고르는 절차가 여기 있다. 그리기 문법 자체는 `diagrams.md`, 부품 도입 근거는 `architecture-sources.md`.

# 아키텍처 도식 — 3축 저작 가이드

아키텍처 그림은 **세 가지 방식(축)** 으로 그린다. 셋은 서로 다른 부품이고, 한 그림에는 하나만 쓴다.
공통 원칙: 그림의 내용을 **시맨틱 JSON** 으로 먼저 적고, 그 JSON 을 축이 소비한다. 좌표를 손으로 찍지 않는다.
축과 별개로 **유형별 생성기**가 있다 — 업무 절차(레인)·호출 순서·As-Is/To-Be 대조는 축이 아니라 `arch_lanes` 가 그린다(§1-2).

---

## 1. 어느 축을 쓰나 (숫자로 판단)

| 조건 | ① stack (격자) | ② stack + dagre 좌표 | ③ iso 생성기 |
|---|---|---|---|
| 부품 | `div.stack-fig[data-c="stack"]` | 같은 부품 + `layout:"abs"` | `figure.fig-slot > svg.dg` (생성기 산출) |
| 노드 수 | 2~14 | 8~20 | **3~7** |
| 깊이 | 3단(행 0~2) | 좌→우 6랭크 / 위→아래 4랭크 | 4~5레벨 |
| C4 뷰 | Component, 일부 Container | Container·Component | **Context·Container·Deployment** |
| 라벨 | 이름 ≤8자·역할 ≤11자·간선 ≤7자 | 노드 폭 176px 고정 | 26px 라벨, 12자 내외 |
| 모션 | `stack-reveal`(부품 소유) | `stack-reveal` + draw/입자 | `arch-trace` 시그니처 |
| 언제 쓰나 | 노드가 적고 격자에 자연스럽게 앉는다 | 격자 상한을 넘거나 교차가 많다 | 배치·공간·경계가 요점이다 |

**판단 순서**
1. 노드 ≤14 이고 3행×6열에 앉는다 → ①
2. 아니고 20 이하 → ②
3. 뷰가 Context/Deployment 이거나 "어디에 놓여 있나"가 질문 → ③
4. 어느 축으로도 안 되면 **장을 나눈다.** 축을 억지로 늘리거나 노드를 줄여 밀도를 깨지 않는다.

한 `figure` 안에서 축을 섞지 않는다 — `k-*`/`.tile`/`.ed-diagram`/`svg.dg` 는 서로 다른 어휘다.

### 1-2. 유형 → 생성기 (SI 확장)

축은 "좌표를 누가 정하나", 생성기는 "그 유형을 어떤 문법으로 굽나"다. **한 장에 생성기 하나.**

| SI 유형 | 생성기 | 핵심 문법 | 상한 |
|---|---|---|---|
| A1 종합 · A2 3계층 · A3 연계 | `arch_layout.mjs` | dagre 좌표 · `kind b/r/g` · `zones member/trust` · `between` | 노드 ≤20 · 링크 ≤12 |
| B1 업무 절차(레인) | `arch_lanes.mjs` (`view:"process"`) | 레인 밴드 · 원/사각/마름모/시스템 · 게이트 분기 · 반려 루프 | 링크 ≤12(하드) · 레인 3~4·행 2 권장 |
| B2 호출 순서 | `arch_lanes.mjs` (`view:"sequence"`) | 생명선(polyline) · 호출 실선/응답 점선 · 활성 구간 | 메시지 ≤12(하드) · 액터 4~5 권장 |
| C1 논리 · C2 물리 인프라 | `arch_layout.mjs` | 포트 라벨(논리) / 구간·회선 종류(물리) | 노드 ≤12 · 링크 ≤12 |
| D1 As-Is/To-Be | `arch_lanes.mjs` (`view:"compare"`) | 좌표 고정 격자 · 4상태(유지·신규·변경·제거) | 열 ≤5 · 링크 ≤12 |
| 배치·공간(랙·DC·DR 사이트) | `iso_layout.mjs` | 등측 투영 · 장비 도형 · uv 좌표 | 노드 ≤7 · 링크 ≤12 |

인자는 생성기마다 다르다 — `arch_layout <모델.json> -o <산출>`(위치 인자·`--coords`) · `iso_layout --in <scene.json> --out <svg>` · `arch_lanes --in <모델.json> -o <산출>`(`--tokens`·`--check`). `arch_lanes` 의 `view` 는 **모델 안**에 적는다(플래그 아님).

`arch_lanes` 는 **업무 절차·순서·대조** 전용이다. 구성 요소를 나열하는 그림(시스템 구성도)에 쓰지 않는다 — 레인·시간 축이 없으면 그냥 카드 목록이 된다.

---

## 2. 시맨틱 JSON

스타일(색·글꼴·반경·모션 이름)은 **여기 들어가지 않는다.** 축과 표현층이 정한다.
기존 `data-d` 는 이 모델의 **부분집합**이다 — 지금 쓰는 덱은 그대로 유효하고, 새 키는 전부 선택이다.

```jsonc
{
  "version": 1,
  "view": "context|container|component|deployment|dynamic",
  "layout": "grid|abs|iso",              // 기본 grid = 현행 stack
  "nodes": [{
    "id": "gw",                    // 필수·유일
    "name": "API GW",              // 필수
    "role": "라우팅",               // 선택
    "icon": "server",              // Lucide 101종 또는 null
    "tone": "plain|brand|dark|accent",
    "kind": "service|datastore|queue|gateway|client|external|actor|network|compute|storage|security",
    "tech": "Nginx",               // C4 container 의 technology
    "state": "ok|busy|warn|down|standby",
    "size": "sm|md|lg",            // IBM 노드 계층 환산
    "detail": "인증 전 구간",        // size=lg 보조 텍스트
    "parent": "grp-core",
    "row": 0, "col": 1,            // layout=grid
    "x": 412, "y": 180,            // layout=abs/iso
    "badge": 3, "step": 2          // 순서 배지 · 등장 단계
  }],
  "edges": [{
    "from": "web", "to": "gw", "label": "HTTPS",
    "kind": "main|sub|dash",       // 굵기·스타일
    "protocol": "http|https|grpc|sql|amqp|tcp|tls|s3|dns|null",
    "direction": "forward|both|reverse",
    "channel": 0,                  // 0=요청, 1=응답 → 병렬 오프셋
    "state": "ok|degraded|down",
    "waypoints": [{ "x": 0, "y": 0 }],   // layout=abs
    "step": 2
  }],
  "groups": [{ "id": "core", "label": "코어", "icon": "box", "tone": "plain",
               "kind": "zone|rack|region|az|vpc|subnet|cluster",
               "nodes": ["gw"], "parent": null, "cols": [0,4] }],
  "boundaries": [{ "id": "trust", "label": "신뢰 경계", "style": "dashed", "sides": ["pub","priv"] }],
  "states": [{ "node": "db", "at": 3, "state": "down" }],
  "steps": [{ "n": 1, "focus": ["web"], "motion": "structure-reveal" }]
}
```

### 검증 규칙
- 모르는 키 → **WARN**(빌드 계속). 기존 덱을 깨지 않기 위한 것이다.
- 중복 id·끊긴 참조·축별 상한 초과·`layout:"abs"` 인데 좌표 없음 → **ERROR**.
- 축별 상한: grid 노드 2~14·간선 ≤20·그룹 ≤5 / abs 노드 ≤20·간선 ≤28 / iso 노드 ≤7·간선 ≤12.
- 모든 문자열은 작은따옴표를 쓸 수 없다(`data-d` 속성 제약).

---

## 3. 축 ① — stack (격자)

가장 싸고 안전한 기본값. `assets/kit/stack.js` 가 격자 배치·직각 라우팅·등장을 모두 소유한다.

```html
<figure class="viz-fig">
  <div class="stack-fig" data-c="stack" role="img" aria-label="한 문장 설명"
       data-d='{"nodes":[{"id":"a","name":"API","icon":"server","row":0,"col":0}],
                "edges":[{"from":"a","to":"b"}]}'></div>
  <figcaption>가상 예시</figcaption>
</figure>
```

- 상한: 노드 2~14 · 간선 ≤20 · 그룹 ≤5(1단) · 행 0~2 · 열 0~5 · 칸 중복 금지
- 글자 예산: 이름 ≤8자(170px) · 역할 ≤11자 · 간선 라벨 ≤7자(104px) · 그룹 ≤6자
- 모션: `stack-reveal`(부품이 직접 `eduMotion.sigLog` 에 기록). `data-step` 을 도식 내부에 쓰지 않는다.

---

## 4. 축 ② — dagre 좌표 (중대형)

좌표 계산만 빌드 시점으로 옮긴다. DOM·CSS·라우팅·검사는 축 ①과 완전히 같다.

1. 빌드가 `@dagrejs/dagre@3.1.3` 으로 배치 → 노드 중심 `x,y` + 간선 `waypoints` 를 `data-d` 에 기록
2. `layout:"abs"` 를 함께 적는다
3. 결과 HTML 에는 **좌표만** 남는다 — 런타임 의존 0

```jsonc
{ "layout": "abs",
  "nodes": [{ "id": "web", "name": "웹", "x": 128, "y": 182 }],
  "edges": [{ "from": "web", "to": "api", "waypoints": [{ "x": 301, "y": 182 }] }] }
```

- 폭 예산: 좌→우 6랭크까지(노드 176px + 간격 ≤108). 위→아래는 4랭크. 넘으면 경계 기준으로 장을 나눈다.
- `channel` 을 쓰지 않으면 같은 노드 쌍의 병렬 간선이 겹친다(현재 `stack.js` 한계).
- dagre 는 **빌드 도구**다. `deck` 산출물에 스크립트를 넣지 않는다.

---

## 4-b. `arch_layout` 확장 문법 (SI 조사 이후)

`scripts/arch_layout.mjs` 입력 JSON 이 넓어졌다. 전부 **선택**이고, 없으면 예전 동작 그대로다.

| 키 | 값 | 뜻 |
|---|---|---|
| `edges[].kind` | `b` 동기 · `o` 이벤트 · `g` 보조·연계 · **`r` 응답** | `r` = 회색 점선(`8 8`) + open 화살촉(`ah-open`). 호출/응답 쌍은 `b`+`r` |
| `edges[].aux` | `true` | 단계 속성이 없는 **정적 보조선**. 항상 보인다. 노드를 우회하는 직교 경로로 그린다 |
| `hints[]` | `[{from,to,minlen?,weight?}]` | 배치 전용 보이지 않는 간선 — 그리지도, draw 예산에도 들지 않는다. 비멤버 노드(예: 외부기관)가 멤버 존 사각형에 들어앉는 위상 왜곡을 hint 로 랭크를 밀어 해소한다(2026-11-10 크리틱 반영) |
| `layout.edgesep` | px(기본 0) | 같은 노드 쌍의 병렬 간선(요청/응답) 벌어짐 — 점선이 실선에 붙어 이중선처럼 읽히는 것을 막는다 |
| `zones[].kind` | `member` · `trust` | `member` = 소속(면색 띠 `k-paper`) · `trust`/미지정 = 신뢰 경계(`k-frame` 점선) |
| `zones[].between` | `[존A, 존B]` | 멤버 대신 **두 존 사이의 경계선**(점선 polyline + 라벨). 라벨 글자받이가 선 구간에 걸치면 선을 라벨 위·아래로 쪼개 글자 관통을 막는다 |
| `zones[].labelPos` | `top` · `bottom` | 띠 라벨 위치 — 상단 띠와 선 라벨이 부딪힐 때 `bottom` |
| `zones[].pad` | `{top,bottom,side}` | 존 여백 덮어쓰기(기본 top 56 · side 24 · bottom 24) |
| `states[].text` | 칩 문구 | 상태 칩 글자를 역할 문구(예 `Active·운영`)로 구분 — 노드 초기 칩은 `node.stateText`. 글자 폭은 노드 폭 안에 들어가게 잡는다 |
| `layout.chipAvoid` | `true` | 라벨 칩끼리의 충돌까지 회피(옵트인). 칩이 **다른 엣지 선·화살촉·다른 칩의 글자 중심**을 덮는 것은 옵션 없이도 항상 회피한다 |
| `legend[]` | `{kind,label}` 또는 `{fam,label}` | 선 어휘 + 노드 색 의미(예 주황=경계 장비) 범례. 생략 시 사용 kind 2종 이상이면 자동 유도 |
| `handover` | `{title, points:[{t,d}]}` | 우측 인수인계 카드 열 — 도식 1392px + 카드 260px 2단. 도식이 작고 여백이 남는 장의 리듬 변주용(svg 글자 18px 하한 유지 폭) |

**주의 3개 (실측)**
- `aux` 는 **생성기 예산(링크 ≤12)에서 제외**된다(비-aux만 계수). 런타임 단계 draw는 새로 드러난 `g[data-step]` 내 경로만 그리므로 aux 는 단계에 애니메이션되지 않는다. 단, 장 진입 직후(아무 단계도 열리기 전)의 초기 draw 는 '그 순간 보이는 경로' 순서로 최대 12개를 긋는다 — 항시 표시인 aux 가 여기 포함될 수 있으나 최종 상태는 항상 전부 표시다.
- `kind:"g"` 의 화살촉은 `ahg`(범용 회색)로, 정의는 `assets/icons/base.svg` 에 있다(`extra.svg` 의 `ah-o/ah-b/ah-n/ah-open` 과 다른 파일 — 마커가 "없다"고 오독하지 말 것. 빌드가 전체 아이콘을 수집해 덱에 넣는다).
- 존은 **1단**(중첩 없음). 두 사이트가 같은 랭크에 걸치면 존 상자가 겹친다 — 회선 순서를 바꿔 사이트를 순차 랭크로 밀어낸다(예: `코어-본사 → FW-센터 → 코어-센터`).

---

## 5. 축 ③ — 아이소메트릭 생성기

> **용도 제한 — 물리·배치 전용.** 아이소는 랙·전산실·DR 사이트처럼 "어디에 놓였나"가 요점일 때 쓴다.
> 논리 구성(무엇이 무엇에 닿나 · 포트 · 신뢰 경계)은 `arch_layout` 2D 로 그린다. 이유: ①노드 7개 상한이라 DMZ 9노드를 못 담는다 ②장비 형상이 의미를 먹어 "연결 가능성"이 "실선 회선"처럼 읽힌다 ③포트·경계 라벨 자리가 없다.
> C1(논리)과 C2(물리)를 한 장에 섞지 않는다 — 선의 뜻이 다르다(연결 가능성 vs 실제 회선).

`scripts/iso_layout.mjs` — 시맨틱 JSON → `svg.dg` 한 장. Node 18+ 표준 모듈만 쓴다(패키지 0).

```bash
node edu-deck/shared/scripts/iso_layout.mjs --in scene.json --out fig.svg
node edu-deck/shared/scripts/iso_layout.mjs --kinds     # 장비 10종과 치수
node edu-deck/shared/scripts/iso_layout.mjs --help      # 입력 형식·계약·종료 코드
```

그림을 손으로 고치지 않는다. **JSON 을 고치고 다시 돌린다** — 같은 입력이면 같은 바이트가 나온다.

### 장비 세트 (코드 생성 도형, 브랜드 로고 없음)
`server1u` · `server2u` · `rack` · `storage` · `switch` · `router` · `firewall` · `lb` · `cloud` · `dc`

- 상태: `ok`(초록 LED) · `busy`(주황 LED) · `warn`(마름모 배지) · `down`(삼각 배지 + 점선 외곽) · `standby`(빈 원 배지)
- **색만으로 구분하지 않는다** — 예외 상태에는 항상 도형 배지가 붙는다.
- 면은 한 색의 3단 불투명도(상판 18% / 오른면 58% / 왼면 82%) — 한 노드에 두 색을 쓰지 않는다(IBM 규칙).

### 좌표는 (u,v) 로 적는다
아이소 화면 기저는 **가로 u = 화면 수평**, **세로 v = 레벨**이다. 내부 변환은 `col = 2u + v`, `row = v - 2u`.
JSON 에 `col`/`row` 를 직접 써야 할 때도 이 식으로 옮겨 적으면 형제가 정확히 수평으로 앉는다.

| 원하는 것 | 적는 법 |
|---|---|
| 레벨 L 의 형제 i (가운데 0) | `u = i`, `v = L` → `col = 2i + L`, `row = L - 2i` |
| 영역(경계) 바닥면 | `"uv": [u0, v0, u1, v1]` |
| 영역을 소속 노드에서 자동 계산 | `"nodes": [...]` (pad 기본 0.5) |

`col`/`row` 를 하나도 안 주면 BFS 자동 배치가 돈다(밴드형). 정확한 배치가 필요하면 명시한다.

### 예산
- 노드 ≤7, 간선 ≤12(생성기가 경고), `viewBox` 높이 ≤840(넘으면 경고)
- 링크 1개 = `<path>` 1개 — 장식은 `polygon`/`polyline`/`rect`/`circle` 만 쓴다
- 입자는 `flow:true` 링크 최대 3개
- 생성기가 경고를 내면 그림을 키우지 말고 **장을 나누거나 노드를 줄인다**

---

## 6. 모션 레시피 10종

`play()` 는 슬라이드의 `data-archetype` 레시피가 없으면 **아무것도 하지 않는다.** 아이소 장은 `data-archetype="arch-diagram"`(= `arch-trace`) 을 반드시 단다.

| # | 이름 | 저작 | 엔진이 하는 일 | 정적 완결 |
|---|---|---|---|---|
| 1 | Structure Reveal | `g[data-step="1..5"]` 로 묶음 | `move` 스태거(≤12) + `draw` | 마지막 단계 = 완성 그림 |
| 2 | Packet Flow | 링크 `class="dash-flow k-ln-b"` | `draw` 뒤 `particles()`(≤3) | 점선만 남는다 |
| 3 | Request / Response | 요청 `dash-flow`, 응답 일반선 + 역방향 `d` | `draw` 2회, 요청에만 입자 | 두 선 모두 표시 |
| 4 | Event (발행→구독) | 중심에서 N개 링크를 **같은 `data-step`** | `draw` 스태거(≤4) = 동시성 | 전 링크 표시 |
| 5 | Fan-out / Fan-in | 4번 + 다음 단계에 수렴 링크 | 동일 | 동일 |
| 6 | Replication | 원본 + `data-replica="1"`(+12,10) + `"2"`(+24,20), 이름 `(3)` | `move` 스태거 | 3겹 정적 표시 |
| 7 | Failover | 정상 칩 `data-until="k"` / 장애 칩 `data-step="k+1"` **교체** | `paintSlide` 가 `gone`/`step-hide` 토글 | 마지막 칩이 남는다 |
| 8 | Trust Boundary | 경계 도형 `g[data-step="k"]`, 내부 노드는 `k+1` | 경계 그룹 `move` | 경계·노드 모두 표시 |
| 9 | Focus | `data-lit="k"` | 모션 없음 — `.lit` 클래스만 | 동일(정적) |
| 10 | Isometric Activity | 아이소 링크 `dash-flow` + 상태 칩 교체 | `arch-trace` → `draw` + `particles` | 완성 그림 |

### 예산 (넘으면 조용히 잘린다)
- `draw()` — 슬라이드의 `path`/`line` 을 **문서 순서로 12개**만
- `particles()` — `.dash-flow` **3개**
- `move` 스태거 — 대상 **12개**
- `data-fx` 효과 — 슬라이드당 **3000ms** 안에 종료
- `stack-reveal` 길이 = `150 + N×80 + E×110 + 700` ms (14노드·20간선이면 약 4.2초)

### 새 시그니처를 만들지 않는다
레시피는 `assets/js/motion.js` 의 `recipes` 표에 있다. 새 이름을 추가하려면
(가) 기존 레시피로 표현이 안 되는 **관계**가 있어야 하고 (나) `MOTION_LIBRARY.md` 에 한 줄을 더해야 한다.
셸(`shell.html`)은 직접 고치지 않고 `python3 shared/dev/port.py` 로 재생성한다.

---

## 7. 계약 (이 9개를 어기면 덱이 깨지거나 검사기가 막는다)

| # | 계약 | 이유 |
|---|---|---|
| 1 | 링크 1개 = `<path>` 1개. 글로우는 `filter:drop-shadow` | `draw()` 가 path 12개만 그린다 |
| 2 | 장식은 `polygon`/`polyline`/`rect`/`circle` 만 | `path`·`line` 은 draw 예산을 먹는다 |
| 3 | 입자는 `.dash-flow` 링크 3개까지 | `particles()` 상한 |
| 4 | 화살촉은 `marker-end="url(#ah-b)"` | 엔진이 도착까지 화살촉을 떼어 둔다 |
| 5 | 단계는 `g[data-step]`·`data-until`·`data-only`·`data-lit` 만 | 새 속성을 만들면 엔진이 모른다 |
| 6 | `viewBox` 폭 1664, 글자는 20px 이상 클래스(`t-*`·`k-t-*`)만 | 18px 미만 ERROR, 고정 px 는 대비 검사 밖 |
| 7 | SMIL·CSS 애니메이션·`<script>` 금지 | 정적 완결이 계약이다 |
| 8 | `rect[rx]` 는 셸이 16px 로 강제 — 다르면 `style="rx:9px"` | CSS 우선순위 |
| 9 | 색은 `var(--…)` 토큰만, 한 노드에 두 색 금지 | 대비 매트릭스·색약 접근성 |

`data-lit` 은 **팩 덱에서만** 스타일이 있다(일반 `.lit` 규칙이 `pack-runtime.css` 에만 있음). 클래식 덱에서 "켜짐" 강조가 필요하면 `data-step` 누적이나 `data-only` 교체를 쓴다 — `data-lit` 은 class 만 붙고 아무것도 그리지 않는다.

---

## 8. 만든 뒤 확인

1. `node scripts/iso_layout.mjs --in scene.json --out fig.svg` — 경고 0 확인(경고가 있으면 장을 나눈다)
2. 같은 명령을 두 번 실행해 `diff` 0 (재현성)
3. `python3 scripts/build_deck.py <덱폴더>` → `python3 scripts/check_deck.py <결과.html>`
4. 화면에서 단계별로 넘겨 보며 ① 라벨이 칩 밖으로 안 나가는지 ② 링크 라벨이 노드를 덮지 않는지 ③ 마지막 단계가 완성 그림인지 본다
5. `?sheet` 축소판으로 전 장에서 이 장만 밀도가 다른지 확인
6. 아키텍처 장이 주인공인 덱은 `design-critique.md`의 독립 크리틱을 돈다 — 보조 렌즈: 구조·관계·동작 순서가 도식에서 읽히는가(레인·레이어·화살표 방향의 일관성)

### 8-2. 재현성 계약 (예제 덱)
- **모델이 저장소 안에 완결**되어야 한다. 장면·좌표·문구는 `examples/<덱>/models/*.json` 에 두고 생성 명령을 산출 파일 주석에 남긴다. 저장소 밖 조립기를 가리키는 주석은 금지(2026-11-08 이전 04·06 데모가 그 결함이었다).
- `regen*.py --check` 는 **모델 → src 재생성 결과가 현재 파일과 같은지** 본다(다르면 실패). 생성기를 고친 뒤에는 반드시 `--check` 로 회귀를 잡는다.
- `arch_lanes.mjs --check` · `iso_layout`/`arch_layout` 2회 실행 `diff 0` — 난수·시간·절대경로를 산출에 넣지 않는다.
- `--coords` 는 **출력 전용**이다(좌표 재입력 경로 없음). "같은 좌표 2장"이 필요하면 `arch_lanes` 의 `view:"compare"` 모델을 쓴다.

## 9. 데모

| 장 | 축 | 스타일 | 모션 | 크기 |
|---|---|---|---|---|
| 아이소 데이터센터 (Deployment) | ③ | isometric | 1 → 2 | `svg` 11.0KB · viewBox 1664×782 |
| 하이브리드 클라우드 (Context) | ③ | isometric + security | 1 → 8 → 2 | `svg` 8.1KB · viewBox 1664×793 |

두 장 모두 `check_deck.py` **PASS(errors=0)** · 발화 시그니처 `arch-trace` · 정적 완결 확인.

SI 확장 예제는 `examples/arch-si/` 에 유형별로 있다(A1 종합 개요·상세, A2 3계층, A3 연계, B1 레인, B2 시퀀스, B3 배치, C1 DMZ 논리, C2 물리, C3 DR, D1 대조 — 표지·인수인계 체크리스트 포함 13장). 각 산출 파일 머리 주석에 모델 경로와 생성 명령이 있다.
