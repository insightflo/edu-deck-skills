> **로드 시점**: 아키텍처·구성도 계열 도식을 만들기 전. "이 부품을 왜 쓰고 왜 안 쓰는가"의 판단 근거가 필요할 때. 저작 절차는 `architecture.md`, 그리기 문법은 `diagrams.md` 를 함께 본다.

# 아키텍처 도식 조사 출처 — 도입/미도입 근거 장부

두 조사(Stage 1-A 기존 부품·Dagre·Anime.js / Stage 1-B AntV·Networkify·디자인 레퍼런스)를 한 표로 합친 것이다.
**규칙: 여기 없는 부품을 새로 들이지 않는다.** 들이려면 이 표에 행을 추가하고 근거(라이선스·리비전·Proof)를 채운다.

## 1. 코드 부품

| Repository | Revision | License | Reusable source | Reuse strategy | Compatibility | Dependencies | Proof | Decision |
|---|---|---|---|---|---|---|---|---|
| `caru-ini/stack-diagram` | `1ed53e3` (2026-11-03) | MIT(코드) · SIL OFL 1.1(폰트) | `references/geometry.md`(기하 규칙) · `assets/template.html`(클래스 어휘) | 기하 규칙은 이미 `assets/kit/stack.js` 에 이식됨. 남은 어휘(광폭 노드·라벨 베일·범례)만 선별 이식 후보 | 브라우저 정적 HTML — 충돌 없음 | 원본은 Python·네트워크(아이콘)·Playwright 필요, 덱에는 불필요 | `assets/kit/stack.js`·`scripts/stack_schema.py` | **부분 채택** — 이식 완료분 유지, 추가 어휘는 별도 판단 |
| **기존 `stack.js` + `stack_schema.py`** | 현재 main | 저장소 자체 | 타일 64px·격자 3행×6열·노드 2~14·간선 ≤20·그룹 ≤5(1단) | **축 1**. `data-c="stack"` DOM 부품, 자체 `stack-reveal` 모션 | 계약 내장 | 0 | `dev/test_stack.py` | **유지·확장** |
| `dagrejs/dagre` | 배포 `@dagrejs/dagre@3.1.3` (npm 2026-10-24) — 옛 `dagre@0.8.5` 금지 | MIT | `dagre.layout()` — 노드 x,y + 간선 waypoint | **축 2**. **빌드 시점에만** 실행해 좌표를 `data-d` 에 굳힌다. 런타임 번들 0 | Node ≥18, 브라우저 무관 | `@dagrejs/graphlib@4.0.6`(MIT) — 빌드 전용 | PoC `dagre-poc/layout-out.json`(7노드 LR → 1986×362.5, 직교 waypoint) | **채택(빌드 시점 한정)** |
| `kieler/elkjs` | 0.12.1 | **EPL-2.0 OR GPL-3.0** | — | — | — | — | 라이선스 조항 확인 | **기각** — 상호주의. dagre 로 같은 역량 확보 |
| `juliangarnier/anime` | `animejs@4.5.0` | MIT | `createMotionPath`·`createDrawable`·`stagger`·`timeline` | — | 브라우저 | 0(자체완결), UMD 116KB | 엔진 코드 대조: 겹침 ≥90% | **기각** — 유일한 gap 은 `morphto`, 수요 불명 |
| `antvis/Infographic` | `5ae0d93` (2026-10-20) · npm `@antv/infographic@0.2.20` | MIT | ① 템플릿 이름 체계(276종 = 구조 41 × 아이템 28) ② 들여쓰기 DSL 문법 ③ 엣지 3겹(글로우·점선·코어) 아이디어 ④ `createRoundedPath` | **개념만.** 코드 미이식. 템플릿을 그대로 쓰지 않는다 | ❌ 직접 불가: 텍스트가 전부 `<foreignObject>` · SMIL 무한 반복 · 원격 폰트 CSS · 렌더 시점 아이콘 API(`www.weavefox.cn`) · 16:9 미대응(TB 191×693 / LR 1890×185) | A방식 시 UMD 849KB(gzip 278KB) + d3·linkedom·roughjs 등 12패키지 | `arch-audit/archpi/out/antv-*.svg` 6종 · `antv-methodA.png` | **보류(개념 참고)** |
| `urbanapp/networkify` | `13ce36f` (2026-09-08) | MIT (c) 2026 urbanapp — ⚠️ `src/assets/icons/*.png` 8장(564KB)은 **출처 표기 없음 → 복사 금지** | `src/geometry.js`(iso·getIsoPath) · `src/layout.js`(layoutNodes) | **축 3**. 두 파일의 알고리즘만 `scripts/iso_layout.mjs` 로 이식(§2 고지) | ⭕ 프레임워크 무관 순수 좌표 계산, 이미지·DOM 참조 0 | 0 (우리가 쓰는 두 파일은 import 0) | `scripts/iso_layout.mjs` · 데모 2장 | **채택(2파일)** |
| `antvis/G6` | npm 5.1.1 · GitHub 12,381★ | MIT | — | — | 팬·줌·드래그 중심 | unpacked 7.6MB(2,063파일) | 규모·용도 대조 | **기각** — `diagrams.md` 가 팬·줌을 금지. 40노드+ 조망도 요구 때만 재검토 |
| `antvis/X6` | npm 3.1.8 · GitHub 6,753★ | MIT | — | — | 동일 | unpacked 8.5MB | 동일 | **기각** |

## 2. Networkify 이식 고지 (MIT 의무)

`scripts/iso_layout.mjs` 상단 주석에 같은 내용을 넣었다. 파일을 옮기거나 고칠 때 이 절도 함께 갱신한다.

- 원본: https://github.com/urbanapp/networkify · 리비전 `13ce36fdaf7dae5954a8cf9a2ed3aaa85d17bf31`
- 이식한 것: `iso()`(격자→화면 투영) · `getIsoPath()`(대각+축 혼합 연결선) · `layoutNodes()`(BFS 계층 배치)
- 바꾼 것:
  1. `TILE_W/TILE_H/ICON_SZ` 상수를 장비 치수에서 유도하도록 매개변수화(원본 220/130/90)
  2. `layoutNodes` 의 셀 중심 `+0.5` 스냅 제거 — 정수 격자를 유지해야 영역 계산이 단순해진다
  3. 다중 컴포넌트를 대각 띠로 이어붙이지 않고 세로 밴드로 분리
  4. 좌표 기저를 화면에 맞춰 회전(`col = 2u+v, row = v-2u`) — 원본은 형제가 오른쪽 아래로 흘러내렸다
  5. 캔버스 렌더러·PNG 아이콘·에디터·220ms 트윈은 이식하지 않음
- 새로 쓴 것: 3면 상자·상태 배지·영역 경계·라벨 칩·연결선 오프셋·SVG 방출 전체

## 3. 디자인 레퍼런스 (자산 아님 — 판단 기준)

| 출처 | 확인한 문구·상태 | 쓰는 방식 |
|---|---|---|
| **IBM Design Language — Technical diagrams** (`ibm.com/design/language/infographics/technical-diagrams/design`, 2026-11-05 갱신) | 노드 bullet/small/large 3계층(large 만 중첩) · 커넥터 기본 직각 라우팅 · **색만으로 의미 전달 금지 + 범례 항상** · 아이콘 24/16px · 8px 그리드 · 노드 기본 높이 48 · 외곽 1px · 반경 8px · 라이트 테마 주색=외곽·커넥터/보조색=채움 전용 · 노드 단색 · 3:1 이상 대비 · 인스턴스는 2겹 오프셋 + `(n)` | **규칙만 환산 적용**(§4). 스타터킷(.ai)·Figma 라이브러리는 IBM 브랜드 자산이므로 복사하지 않는다 |
| **C4 model** (`c4model.com`) | 사이트·예시 도해 = **CC BY 4.0**. 모델 자체는 표기법(자유 사용) | 뷰 이름과 계층 개념만 차용. 도해를 복제하지 않는다 |
| **Microsoft Azure architecture icons** (`learn.microsoft.com/en-us/azure/architecture/icons/`) | "Microsoft permits the use of these icons in architectural diagrams, **training materials**, or documentation. You can copy, distribute, and display the icons only for the permitted use unless granted explicit permission by Microsoft." | **선택 자산.** 교육자료가 허용 목록에 명시된 유일한 벤더. 허용 범위 밖 사용·아이콘 단독 배포 금지 |
| **AWS architecture icons** (`aws.amazon.com/architecture/icons/`) | "We allow customers and partners to use these toolkits and assets to create architecture diagrams… You can also put icons in materials like whitepapers, presentations, data sheets, and posters." (패키지에 Terms of Use 별도) | **보류** — 패키지 내부 Terms of Use 원문 미확인. 확인 전 사용 금지 |
| **Google Cloud icons** (`cloud.google.com/icons`) | 아이콘 ZIP 만 제공, **사용 조건 문구 없음(미확인)** | **제외** — 기본 미사용 |
| 범용 아이콘 | `assets/kit/vendor/lucide-subset.json` 101종 (Lucide, ISC) | **기본값.** 브랜드 마크 금지 |

### 브랜드 아이콘 3원칙
1. 기본은 범용(자체 아이소 장비 + Lucide). 브랜드는 그 교육이 그 클라우드를 가르칠 때만.
2. 아이콘을 변형·재색칠·부분 복제하지 않는다. 벤더 후원으로 오인될 배치를 만들지 않는다.
3. 브랜드 아이콘을 쓰는 장은 캡션에 출처를 적는다.

## 4. IBM 규칙 → 덱 환산 (근거 있는 값만)

| IBM | IBM 값 | 덱 값 | 이유 |
|---|---|---|---|
| 노드 주 라벨 | 14/18 semibold | 26px / 700 (`t-l`) | 투사 거리 — 덱 본문 24~28px 의 하위 |
| 노드 보조 | 14/18 regular | 22px / 400 (`t-mile`) | |
| 커넥터 라벨 | 12/16 regular | 24px / 700 + 종이 halo (`t-q`) | 18px 미만은 검사기 ERROR |
| 아이콘 | 노드 24 · 배지 16 | 노드 28 · 배지 20 | 같은 1.2배 |
| 그리드·반경 | 8px · 8px | `--s1` · `--r1`(8px), 칩 9px | 기존 토큰 유지 |
| 외곽선 | 1px | 2~3px (`k-blue` 3px) | 투사 시 1px 은 사라진다 |
| 색 | 주색=외곽·커넥터 / 보조색=채움 전용 / 노드 단색 | `--blue` · `--blue-soft` · 한 노드 두 색 금지 | 대비 검사기 승계 |
| 아트보드 | 1584 / 1312 / 1080, 16:9 | **1664 고정** | 현행 `diagrams.md` 계약 |
| 인스턴스 복제 | 오프셋 2겹 + `(n)` | 동일 | `data-replica` |

## 5. 미결 (이 표에 남겨 둔다)

| # | 항목 | 상태 |
|---|---|---|
| 1 | AWS 아이콘 패키지 내부 Terms of Use | 미확인 — 원문 확인 전 사용 금지 |
| 2 | GCP 아이콘 사용 조건 | 미확인 — 기본 미사용 |
| 3 | AntV 를 B방식(빌드 시 SVG 추출)으로 후처리할 비용 | 미실험 — `foreignObject`→`<text>` 변환에 텍스트 측정이 필요 |
| 4 | 아이소 계열 라벨 밀도 상한 | 7노드까지 실측 확인, 8노드 이상은 미시험 |
