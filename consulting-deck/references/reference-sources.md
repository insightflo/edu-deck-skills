> **소유 영역**: 이 스킬이 이식한 오픈소스 개념의 내역과 출처 표기, 컨설팅 펌 공개 자료 분석의 근거, 접근 차단 기록, 인용·복제 경계.
> **로드 시점**: 근거 조사(2단계)에서 펌·공개 자료를 인용할 때, 라이선스·출처 표기가 필요할 때, 외부 자료를 재사용하려 할 때.

# 참고 소스와 복제 경계 (reference-sources)

## 1. 개념 이식 내역 — 오픈소스

### zairuilab/consulting-deck (Apache-2.0, v0.4.0, commit d25dd54)
PPTX 네이티브 생성 전용 스킬. **개념만 한국어로 재작성**해 이식했고, 원문 문장·JSON 레지스트리를 복사하지 않았다(Apache-2.0은 텍스트 복사 시에만 4조 조건이 붙는다 — 재작성은 의무 없음. 출처 표기는 신뢰 원칙).

| 이식 개념 | 우리 구현 |
|---|---|
| 차트 5층 스택(Answer/Measure/Evidence/Interpretation/Provenance) | `analytical-charts.md` §2 |
| 질문 기반 차트 선택 9계열+피할 것 | `analytical-charts.md` §3 |
| 주석 체계 4종·규칙(main 1+sub ≤2) | `analytical-charts.md` §5 + chart_gen annotations |
| 액션 타이틀·페이지 역할 8종·수평 논리 | `storyline.md` §6~8 |
| 서사 뼈대 4종·통치 사상 요건 | `storyline.md` §4~5 |
| 레이아웃 수용량·선택 규칙(45종 → 19종 서브셋) | `consulting-layouts.md` |
| 다양성 규칙(≥5 유형·동일 실루엣 3연속 금지) | `consulting-layouts.md` §6 |
| 품질 게이트 구조(blocker/warning/advisory) | `quality-gates.md` |
| 데이터 조정 체크리스트 12항 | `evidence.md` §6 |
| 증거 유형 5종+신선도 | `evidence.md` §3 |
| 시각 방향 4종·타이포·금지 패턴 | `consulting-design.md` |
| 문제해결형/자료종합형 분기(가설 트리 강요 금지) | `storyline.md` §1 |

미이식: PPTX 런타임 전부(네이티브 차트·어댑터·검사기·워크북 대사) — 산출물이 HTML이라 불필요. "편집 가능성" 게이트는 HTML 접근성·DOM 검증으로 치환했다.

### McKinsey Vizro (Apache-2.0, commit 146b932)
런타임 탑재 금지(Plotly.js 번들 불가 — 무의존 단일 HTML 원칙). 이식한 것: Visual Vocabulary의 질문 기반 차트 분류 체계(9카테고리)·선언적 구성 원칙(의도·데이터·인코딩↔렌더 분리 — charts.json이 그 구현)·범주형/순차형/발산형 3종 팔레트 구조. 차트 구현은 자체 SVG다.

### 출처 표기 형식
개념을 가져온 문서 하단에는 한 줄로 남긴다:
`개념 출처: zairuilab/consulting-deck(Apache-2.0, d25dd54) … 재작성` / 필요 시 `McKinsey Vizro(Apache-2.0, 146b932) …`.

## 2. 펌 공개 자료 분석 — 근거와 확보 범위

| 자료 | 접근 | 확보 |
|---|---|---|
| Bain, Global Private Equity Report 2026 (PDF 42p) | bain.cn 다운로드 + pdftotext | 전문. Figure 35개 전부 주장형 제목, 차트 전용 페이지 분리, Notes/Source 표준 블록 |
| BCG, AI Radar 2026 (웹 아티클) | 헤드리스 렌더 | 본문 13,397자. KEY TAKEAWAYS 박스, 세그먼트 프레임워크(15/70/15), 명령형 액션 5개 |
| Deloitte, Tech Trends 2026 KR (허브 페이지) | 헤드리스 렌더 | 헤딩 51개. 'A에서 B로' 전환형 부제, 5대 동력 번호 프레임워크, 총론→카드 2단 구조 |
| McKinsey MGI, 2025 in Charts | **전 경로 차단** | 스니펫뿐 — 7항목 분석은 "확인할 수 없습니다"로 기록(지어내지 않음) |

분석의 한계: 비전 검수 없이 텍스트 추출·DOM 구조 기반 분석이다(스크린샷은 참고 보관). 펌 패턴 9종 종합은 `consulting-design.md` §5에 번역돼 있다. 원본 PDF·덤프는 저장소에 반영하지 않는다.

## 3. 차단 기록 — 재시도 금지

McKinsey MGI 2025 in Charts: playwright→Akamai 403 · curl→연결 차단 · jina reader→403 · 공식 CDN PDF→timeout · GitHub 미러→404. **McKinsey 도메인 직접 수집은 재시도하지 않는다.** 필요하면 공식 발행물·2차 인용(출처 명시)으로 대신하고 근거 수준을 낮춰 적는다.

## 4. 인용·복제 경계

- 펌 자료에서 쓸 수 있는 것: 짧은 인용(제목·핵심 수치, 출처와 함께), 분석에서 얻은 **패턴의 번역**(`consulting-design.md` §5의 번역표).
- 쓸 수 없는 것: 문장 단위 이식, 로고·브랜드 자산, 페이지 레이아웃·차트의 모방 복제, 보호 템플릿. "비슷하게" 만들지 않는다 — 패턴은 우리 문법(토큰·조각·생성기)으로 재작성한다.
- 외부 수치를 화면에 쓰면 evidence.json 원장에 locator까지 남긴다(evidence.md §2). 원문 값·우리 계산·우리 해석을 한 덩어리로 섞지 않는다.
- 새 오픈소스·외부 자산을 이 스킬에 더하려면: 라이선스 확인(licenses/) → 개념 재작성 또는 조건부 복사 판정 → 이 문서에 내역 추가. 확인 전 것은 가져오지 않는다(저장소 공통 규칙).

## ztd-charts (2026-11-09 추가 — 디자인 값 참조)

- **대상**: https://charts.ztd.app/docs/examples/ · github.com/Junhan2/ztd-charts (MIT)
- **반영**: 예제 대시보드의 디자인 값을 실측해 컨설팅 차트 톤에 반영 — 단일 선명 액센트(#0b8fd8 계열) +
  비초점 트랙 그레이(#d5dae0/#9aa3ae) · 가는 실선 그리드(#e6e9ed) · 청람 잉크(#14171b) ·
  스택 세그먼트 종이색 분리선. `assets/consult.css` 신규 토큰(--grid·--track·--track-strong)과
  `charts/chart_gen.mjs` 비초점 fill/축선 두께로 구현.
- **경계**: 코드·컴포넌트 복사 없음(값·개념만). 분석 자료: /tmp/ztd/(캡처·토큰 덤프 — 세션 한시).
