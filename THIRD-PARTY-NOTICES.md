# 제3자 고지 (Third-Party Notices)

## effective-html

이 저장소의 작성 지침 문서 `edu-deck/shared/references/diagrams.md`,
`edu-deck/shared/references/expression.md`, `edu-deck/shared/references/composition.md`,
`edu-deck/shared/references/MOTION_LIBRARY.md` 는
**effective-html** 스킬 묶음의 지침 일부를 참고·번역해 반영합니다.
수용한 관점: 도식 문법 선택표(질문→문법)와 "한 그림에 질문 하나", 도형 어휘의
기계적 반복(같은 둥근 상자+화살표) 경고, 위계를 색보다 위치·묶음·크기·여백으로
세우는 순서, 연속 동작의 인과성·정지 상태에서의 전체 이해, 팬·줌 자제, 필수
정보의 비호버 공개, 비교의 같은 속성 정렬.

effective-html 은 MIT 라이선스로 배포됩니다 (Copyright (c) 2026 plannotator).
라이선스 전문은 `licenses/EFFECTIVE-HTML-MIT.txt` 에 있습니다.

## 스타일 프리셋 개념 참조 (shiraki.design — 값·파일 미복제)

`edu-deck/shared/presets/` 및 `edu-deck/shared/scripts/style_preset.py` 의 스타일 프리셋 계층은
**shiraki.design** 스타일 명세의 구조적 개념(장르별 `intent / use / avoid` 분류 체계 및 `paper / surface / line / ink / brand / accent / night` 역할 토큰 스키마, WCAG 4.5:1 대비 보정 방법론)만 참조하여 설계했습니다.
원본 명세 및 내부 실험본은 재배포 금지 대상이므로 저장소에 포함하지 않으며, 수록된 16종 프리셋의 색상값·문구·식별자는 모두 본 저장소에서 독자적으로 새로 창작한 고유 자산입니다.

## ko-document-studio (코드 이식 — MIT)

다음 파일은 **ko-document-studio** (© 2026 acc0mplish, MIT) 에서 이식했습니다.
각 파일 머리에 출처 한 줄을 표기했습니다.

- `edu-deck/shared/scripts/diagram_lint.py` — `shared/diagram_lint.py` 이식 후 벤더 경로·리포트 계약 조정
- `edu-deck/shared/scripts/check_deck.py` 의 `DESIGN_LINT_JS` — `engines/ko-slide/assets/kit/deck.js` 의 designLint·skeletonOf 를 우리 DOM 계약으로 포팅
  (원 규칙 출처: huashu-design MIT, ppt-master MIT — `licenses/DESIGN-LINT-HUASHU-MIT.txt`, `licenses/DESIGN-LINT-PPT-MASTER-MIT.txt`)
- `bookstyle-html/tests/viewer_smoke.mjs` — `engines/ko-doc/tests/viewer_smoke.mjs` 를 우리 뷰어 셀렉터로 각색
- `bookstyle-html/scripts/preview.py` 의 `--release` 검사 — `engines/ko-doc/scripts/check_book.py` 의 규칙 개념을 우리 book.json 계약으로 재작성

라이선스 전문은 `licenses/KO-DOCUMENT-MIT.txt` 에 있습니다.
catalog·shiraki 파생물은 반입하지 않았습니다.

## svg-lint (벤더 바이트 사본 — MIT)

`edu-deck/shared/scripts/vendor/svg-lint/` 는
**bybit-exchange/svg-diagram** 저장소 `tools/svg-lint` 의 바이트 사본입니다
(커밋 c30c9e3, 취득·해시·제외 범위는 같은 디렉터리 `VENDOR.md`·`SHA256SUMS` 참조).
라이선스 전문은 `edu-deck/shared/scripts/vendor/svg-lint/LICENSE`
(사본: `licenses/SVG-LINT-MIT.txt`)에 있습니다.

## unslop (감사 기준 문서 — 개념만 사용)

`workspace/unslop-audit.md` 에 기록된 AI-slop 시각 감사는
**unslop** (Damir Sokolovsky, https://heydamir.design/unslop) 의
`SKILL.md`·`references/signs.md` 를 평가 기준으로 삼아 수행했습니다.
이번 수정(gradient text·hue 채움·glow·glass·대문자 라벨·과도 굵기/자간 제거)은
그 기준에 따른 것이며, 원본 코드·문구를 저장소에 포함하지 않았습니다.

unslop 은 CC BY 4.0 으로 공개됩니다 (© Damir Sokolovsky).

## flint-chart (도구 의존 — MIT, 저장소 밖 설치)

컨설팅 덱의 선택적 차트 엔진으로 **flint-chart 1.0.1** (© Microsoft Corporation, MIT)
`renderSvg()` 정적 SVG 경로를 사용합니다. vegalite 백엔드 렌더에는
**vega 6.4.0**(BSD-3-Clause)·**vega-lite 6.5.0**(BSD-3-Clause)이 함께 필요합니다.
`flint-chart-mcp`(MIT)는 저작 보조용 선택 도구입니다.

- 설치는 저장소 밖 머신 로컬(`~/.edu-deck/flint/`, `flint_env.py install`) — 저장소에 npm 바이트 사본을 두지 않습니다.
- 저장소 안의 연결 파일: `consulting-deck/charts/flint_env.py`(감지·설치·상태) · `flint-package.json`(버전 핀) · `flint_gen.mjs`(정적 SVG → 조각) · `flint-theme.json`(테마 SSOT) · `flint-schema.md`(모델 계약). 생성기·스키마·테마 값은 우리 계약으로 새로 작성했으며 flint 소스를 복제하지 않았습니다.
- 라이선스 전문: `licenses/FLINT-CHART-MIT.txt` (flint-chart·flint-chart-mcp), `licenses/VEGA-BSD-3-CLAUSE.txt`, `licenses/VEGA-LITE-BSD-3-CLAUSE.txt`.

## codex-ppt-skill (스타일 자산 사본 — MIT)

`edu-deck/shared/assets/style-sheets/` 안의 12종 스타일 명세(중문 `.md`)·미리보기 PNG 는
**ningzimu/codex-ppt-skill** (© 2026 ningzimu) 저장소 `references/`·`assets/style-previews/` 의 사본입니다.
스킬 폴더 자체는 장 전체를 생성 이미지로 만드는 비편집 방식이라 "편집 가능한 최종 PPTX" 요구에
맞지 않아 채택하지 않았습니다(편집 가능 경로는 아래 ppt-master).

edu-deck 의 승인 게이트(구성안 승인·대표 샘플 승인)와 "한 덱 한 스타일" 절은
`docs/workflow-gates-and-progress.md` 의 절차 개념만 참조해 우리말로 재작성했으며,
원문 문구를 복제하지 않았습니다.

라이선스 전문은 `licenses/CODEX-PPT-SKILL-MIT.txt` 에 있습니다.

## ppt-master (스킬 폴더 바이트 사본 — MIT)

`ppt-master/` 는 **hugohe3/ppt-master** (© 2025-2026 Hugo He, v6.9.0) 저장소
`skills/ppt-master/` 의 사본입니다(파일 헤더·저작권 보존, 내용 무수정).
네이티브 DrawingML PPTX 생성 경로이며, `edu-deck/shared/references/design.md` 의
"회상 색인 → 판단 → 경계" 골격과 장 리듬 개념도 이 프로젝트의 craft 규칙을
슬라이드에 맞게 각용해 직접 작성한 것입니다(design.md 머리말 표기 참조).
라이선스 전문은 `licenses/PPT-MASTER-MIT.txt` 에 있습니다.

## line-art-animation (스킬 폴더 바이트 사본 — MIT)

`line-art-animation/` 는 **JDhruv14/line-art-animation** (© 2026 JDhruv14, v0.1.0,
MIT) 저장소의 사본입니다(`.git` 제외 전 파일 무수정 — SKILL.md·lib 4종 TS·references 6종·
examples 2종(walker·village)·scripts 3종·media). 얇은 잉크 선 일러스트 애니메이션
(걷는 인물·마을 씬·하루 흐름) 라이브러리이며, 의존성 없는 `lib/*.ts` 4파일과
Vite+TypeScript 예시로 구성됩니다. 라우팅: edu-deck 0단계 "라인아트/손그림 장면" →
`../line-art-animation/SKILL.md`.
라이선스 전문은 `licenses/LINE-ART-ANIMATION-MIT.txt` 에 있습니다.

## technical-reveal (개념 참조 — 코드 미복사, MIT)

`data-fx="draft"`(래스터 이미지가 도면처럼 재구성되며 등장하는 공통 모션 기법)은
**technical-reveal** (© 2026 Shiv, MIT — `workspace/refs/technical-reveal`, 라이선스 전문
`licenses/TECHNICAL-REVEAL-MIT.txt`) 의 "하나의 이미지를 CAD 도면으로 다시 그린 뒤 실물을
공개한다"는 시각 개념만 참조해 클린룸으로 재작성했습니다.
원본의 코드·문장·팔레트·React/DialKit/녹화·PNG 수출 도구는 흡수하지 않았고,
다운스케일 분석·가장자리 플롯·치수 주석·크로스페이드 공개는 모두 우리
토큰(`--soft`/`--line`/`--accent`)과 2400ms 모션 예산으로 새로 구현했습니다
(구현: `edu-deck/shared/assets/js/motion.js`, 분석: `workspace/absorb/tech-reveal-analysis.md`).

### draft v2·draft-loop 2차 개념 참조 (2026-11-13)

`draft` v2(윤곽 체인 플롯·구성선·플로터 헤드·브러시 마스크 리빌)와
`draft-loop`(표지 순환 변형)는 위 개념을 더 깊게 구현한 제3자 파생 덱
`~/Downloads/loop-cover-deck.html`(technical-reveal 계열, 2026-11-13 사용자 제공)의
**행동 개념만** 추가 참조해 클린룸으로 작성했습니다(코드·팔레트·식별자 0복사,
소스 코드 미열람 — 분석: `workspace/absorb/loop-cover-analysis.md`).
Sobel·NMS·히스테레시스·RDP·3점 원 피팅은 표준 알고리즘이며 색은 덱 토큰만
사용합니다. 근원 라이선스는 위 technical-reveal MIT 기록을 따릅니다.
