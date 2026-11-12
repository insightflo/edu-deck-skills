# 차분한 무대: 디자인 토큰

기준 파일은 `assets/css/tokens.css`입니다. legacy와 새 팩은 같은 의미 토큰을 사용하며 팩별 값도 이 파일에서만 바꿉니다. 팔레트·시간 값을 컴포넌트에 직접 적지 않습니다.

## 색: 15개 역할

`ink` 본문/어두운 면 · `paper` 종이 · `light` 바탕 · `soft` 설명 · `line` 경계 · `accent` 행동 · `accent-text` 작은 강조 글 · `accent-light` 어두운 면의 강조 · `blue` 근거 · `blue-text` 작은 근거 글 · `blue-soft` 근거 면 · `success` 정답 · `danger` 오답/채점 · `muted` 어두운 면의 설명 · `chip` 보조 면.

모두 `--` 접두를 붙입니다. 기존 이름 `accent-deep`, `accent-soft`, `accent-chip`, `blue-light`, `muted-num`은 호환용 별칭이며 별도 색을 선언하지 않습니다. 투명한 면은 이 역할에 `color-mix()`를 적용합니다. 팩별 hue만 바꾸는 것이 아니라 기존 레이아웃·읽기 순서·도식 모티프를 함께 유지합니다.

정답은 색과 함께 글자/위치로 표시합니다. 본문 4.5:1, 큰 글자 3:1, 의미 있는 그래픽 3:1을 목표로 실제 합성 배경에서 검사합니다. 글자를 포함한 등장 효과와 오답 설명에 낮은 투명도를 적용하지 않습니다. 밝은 바탕의 연결선에는 `accent`·`blue`·`soft`를 쓰며, 밝은 면에 쓰는 채움색을 연결선 색으로 재사용하지 않습니다. 기존 검사기 통과는 전체 WCAG 적합성 선언이 아닙니다.

## 이름있는 테마 (legacy 전용)

`deck.json` 의 `"theme"` 키로 `classic`(기본, :root 그대로)과 `ocean` `cobalt` `forest` `solar` `berry` `cocoa` `graphite` `midnight` `mono` `brick` `honey` `mint` `violet` `coral` `olive` `espresso` 중 하나를 고릅니다. 각 테마는 `assets/css/themes.css` 의 `[data-theme="<id>"]` 블록에 15개 의미 역할 전부를 정의하며(일부만 덮으면 대비 매트릭스가 깨집니다), 반경 `r1~3`·모션 `m1~4`·간격 `s*`·튐 `e-spring` 비색 토큰도 테마의 shape 축값 lerp 로 함께 바꿉니다. 색은 테마로만 바뀌고 비색은 축으로만 바뀌어 대비 보장이 유지됩니다 — 새 테마를 만들면 `check_deck.py --contrast-matrix` 의 `theme:<id>` 행으로 같은 기준을 통과해야 합니다. `theme` 을 쓰지 않거나 `classic` 이면 어떤 속성도 심지 않아 기존 덱과 결과가 같습니다.

## 장르 스타일 프리셋 계층 (`presets/*.yaml`)

기본 8테마(`themes.css`)가 범용 색상 팔레트라면, `shared/presets/*.yaml`(16종 고유 프리셋)은 구체적인 발표·교육 장르(`intent`·`use`·`avoid`)와 세분화된 지면·표면·잉크·주색·강조·다크 무대 토큰(`paper/surface/tint/line/ink/ink-2/ink-3/brand/accent/night`)을 정의한 **장르 스타일 시트**입니다.
- 적용 경로: `python3 shared/scripts/style_preset.py --apply <preset-id> --deck <덱폴더>` 를 실행하면 `<덱폴더>/src/preset.css` 가 생성되어 `build_deck.py` 조립 시 `/*EXTRA_CSS*/` 로 자동 주입됩니다(`shell.html`·`check_deck.py` 무수정). `bookstyle-html` 플립북에도 `--book <북폴더>` 로 동일하게 적용할 수 있습니다.
- 자동 추천 연동: `scripts/tone_router.py` 실행 시 기존 `theme`·`cover`·`arc` 출력은 그대로 유지하면서, 6축(`AXES`) 거리 기반으로 선택적 오버레이 후보인 `"preset"` 추천 1종·후보 3종·근거 문장(축 근접+신호어)을 함께 반환합니다(`--recent-preset` 감점 지원, `PRESETS` id 는 `style_preset.py --list` 16종과 1:1 계약).
- 대비 검증: 모든 프리셋은 `style_preset.py --verify` 및 `dev/test_style_presets.py` 에서 전경/배경 핵심 쌍의 WCAG 4.5:1(본문/어두운 무대 주 텍스트는 7.0:1) 이상 대비를 통과해야 합니다. (개념 참조: shiraki.design — 재배포 금지로 원본 값·문구 미복제, 전수 자체 창작)

## 기하와 글꼴

- 간격: 8px 배수. 토큰 `s1/s2/s3/s4/s5/s6/s8/s10/s16` = 8/16/24/32/40/48/64/80/128px. SVG 좌표·글자 크기·인쇄용 mm/pt는 간격 토큰의 대상이 아닙니다.
- 모서리: `r1/r2/r3` = 8/16/24px. 원의 50%는 모서리 단계가 아닌 도형입니다.
- **중첩 반경(동심원) 규칙**: 요소 안에 요소를 넣을 때(카드 안 카드·모형 창 안 요소·패널 안 버튼) 안쪽 반경은 `바깥 반경 − (안쪽까지의 거리)` 로 맞춘다 — 동심원이 어긋나면 모서리가 촌스러워진다. 구체적으로:
  - 기본 공식: `안쪽 r = max(바닥값, 바깥 r − padding − border 굵기)`. 테두리가 없으면 border 항은 0.
  - **테두리도 뺀다**: border가 있는 면은 반경에서 border 굵기까지 감산해야 곡선이 이어진다.
  - **알약(캡슐)은 높이 ÷ 2**: `border-radius: 999px` 를 쓰지 않는다 — 높이의 절반 값으로 쓰면 인쇄·확대에서 일그러지지 않는다.
  - **포커스 링·테두리 겹침은 더한다**: 바깥으로 두르는 링(focus ring·외곽 강조선)은 바깥 반경에 링 오프셋을 **더한** 값으로 쓴다(빼지 않는다).
  - **바닥값**: 감산 결과가 0 이하로 내려가면(안쪽 여백이 바깥 반경보다 큼) 바닥값(권장 4px)으로 클램프하고, 바깥이 각진(r=0) 면은 안쪽도 0으로 전파한다. 바닥에 걸렸으면 수학값 대신 광학 판단 — 아주 작은 안쪽 요소는 아예 각지게(0) 두는 게 더 깔끔할 수 있다.
- 그림자: `shadow-1`(국소 강조), `shadow-2`(겹치는 큰 면). 추가 그림자 금지.
- 선: 1px 또는 2px. SVG도 같은 굵기를 사용합니다. 선 굵기 층위는 3단계 — 의미 경계 2px(인식 필수)·장식선 1px·헤어라인 0.5~1px(구분 보조). 아이콘은 본문 행 높이(.body 32px~제목 72px) 안에서 끝내고, 아이콘 상자가 아이콘보다 먼저 보이면 상자를 없앤다(glm-vs-ours §4-8).
- 본문·일반 제목 굵기는 800 이하. 표지 제목·대형 숫자만 900 허용.
- Pretendard Variable v1.3.9 원본 WOFF2를 HTML의 `@font-face`에 base64로 넣습니다. 외부 로딩·설치가 없습니다. 글꼴 2,057,688 bytes, base64 2,743,584 bytes이며 라스터 이미지 예산과 별개입니다.
- 원본: https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/packages/pretendard/dist/web/variable/woff2/PretendardVariable.woff2
- Git blob SHA1: `49c54b5152a184a243e85f7281ed338b6569987e`. `assets/fonts/OFL.txt`의 저작권과 OFL 1.1 전문을 모든 출력 HTML에 포함합니다. 글꼴을 수정하거나 서브셋하지 않습니다.

## 시간과 곡선

| 토큰 | 값 | 용도 |
|---|---|---|
| m1 | 150ms | 짧은 피드백, 지연 계산의 단위 |
| m2 | 300ms | 오답 피드백, 제한된 글자 blur |
| m3 | 500ms | 장 전환·설명 요소·SVG 선 |
| m4 | 800ms | 표지·흐름 입자·수치 릴 |
| e-out | cubic-bezier(.16,1,.3,1) | 등장·정렬 |
| e-spring | cubic-bezier(.34,1.28,.64,1) | 제한된 오버슈트 |
| e-inout | cubic-bezier(.65,0,.35,1) | 연결·선·상태 전환 |

JS는 CSS의 계산된 값을 읽습니다. 요소 지연은 `min(index,6) × m1/4`, 제목 글자 지연은 `min(index,16) × m1/8`입니다. 새 시간 상수가 아닙니다. 도움말 숨김·알림 수명은 움직임 시간이 아니라 UI 표시 시간입니다.

기본 애니메이션 속성은 transform/opacity입니다. 승인 예외는 **제목의 6px 이하 blur, m2 이내**와 **국소 SVG stroke-dashoffset, m3 이내**, 그리고 공통 기법 4건 — **`slice-reveal`·`blinds`의 `clip-path`(m4 이내)·`rack-focus`의 `filter: blur()`(m3 이내·채점 순간 한정)·`weight-wave`의 `font-variation-settings` wght(m3×1.8+글자당 60ms·제목/핵심 어구 한정)** 입니다. 숫자는 원본 문장을 바꾸지 않는 장식용 숫자 릴을 transform으로 움직입니다. 무한 루프·SMIL·캔버스 rAF 채점은 사용하지 않습니다. 60fps는 설계 목표이며 실제 측정 없이 보장하지 않습니다.

## 상·하단 크롬 막대

`.ed-top`(44px)·`.ed-bot`(48px)은 무대 위 고정 오버레이이며 15역할 토큰만으로 합성합니다 — 배경 `color-mix(in srgb,var(--ink) 88%,transparent)`·글자 `var(--paper)`·보조 글 `paper 75%`·선 `paper 18%`·호버 `paper 16%`·진행 채움 `accent-light`·지난 장 `paper 55%`. 자동 숨김은 `m2`/`e-out` 페이드이고 `prefers-reduced-motion`이면 즉시입니다. 이 비율들은 `check_deck.py --contrast-matrix`의 `chrome-*` 행(글자 4.5:1·채움 3:1)으로 테마·팩·프리셋 전수를 검사하므로 임의 변경 금지입니다.

## 소유권과 재생성

`dev/port.py`가 두 셸을 생성합니다. 입력은 패키지 내부 `dev/*shell_template.html`, `assets/css/{core,tokens,themes,visual-motion,responsive,viewer,theme-switch}.css`, `assets/js/{responsive,motion,patterns,viewer,talk,sheet,themes,study}.js`, `assets/fonts/`뿐입니다. `assets/shell.html`과 `assets/pack-shell.html`을 직접 수정하지 않습니다. 포털은 `scripts/visual_assets.py`를 통해 같은 자원을 한 번 넣습니다. 예전 Downloads 원본은 이 경로에서 필요 없습니다.
