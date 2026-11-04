# 차분한 무대: 디자인 토큰

기준 파일은 `assets/css/tokens.css`입니다. legacy와 새 팩은 같은 의미 토큰을 사용하며 팩별 값도 이 파일에서만 바꿉니다. 팔레트·시간 값을 컴포넌트에 직접 적지 않습니다.

## 색: 15개 역할

`ink` 본문/어두운 면 · `paper` 종이 · `light` 바탕 · `soft` 설명 · `line` 경계 · `accent` 행동 · `accent-text` 작은 강조 글 · `accent-light` 어두운 면의 강조 · `blue` 근거 · `blue-text` 작은 근거 글 · `blue-soft` 근거 면 · `success` 정답 · `danger` 오답/채점 · `muted` 어두운 면의 설명 · `chip` 보조 면.

모두 `--` 접두를 붙입니다. 기존 이름 `accent-deep`, `accent-soft`, `accent-chip`, `blue-light`, `muted-num`은 호환용 별칭이며 별도 색을 선언하지 않습니다. 투명한 면은 이 역할에 `color-mix()`를 적용합니다. 팩별 hue만 바꾸는 것이 아니라 기존 레이아웃·읽기 순서·도식 모티프를 함께 유지합니다.

정답은 색과 함께 글자/위치로 표시합니다. 본문 4.5:1, 큰 글자 3:1, 의미 있는 그래픽 3:1을 목표로 실제 합성 배경에서 검사합니다. 글자를 포함한 등장 효과와 오답 설명에 낮은 투명도를 적용하지 않습니다. 밝은 바탕의 연결선에는 `accent`·`blue`·`soft`를 쓰며, 밝은 면에 쓰는 채움색을 연결선 색으로 재사용하지 않습니다. 기존 검사기 통과는 전체 WCAG 적합성 선언이 아닙니다.

## 기하와 글꼴

- 간격: 8px 배수. 토큰 `s1/s2/s3/s4/s5/s6/s8/s10/s16` = 8/16/24/32/40/48/64/80/128px. SVG 좌표·글자 크기·인쇄용 mm/pt는 간격 토큰의 대상이 아닙니다.
- 모서리: `r1/r2/r3` = 8/16/24px. 원의 50%는 모서리 단계가 아닌 도형입니다.
- 그림자: `shadow-1`(국소 강조), `shadow-2`(겹치는 큰 면). 추가 그림자 금지.
- 선: 1px 또는 2px. SVG도 같은 굵기를 사용합니다.
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

기본 애니메이션 속성은 transform/opacity입니다. 승인 예외는 **제목의 6px 이하 blur, m2 이내**와 **국소 SVG stroke-dashoffset, m3 이내**뿐입니다. 숫자는 원본 문장을 바꾸지 않는 장식용 숫자 릴을 transform으로 움직입니다. 무한 루프·SMIL·캔버스 rAF 채점은 사용하지 않습니다. 60fps는 설계 목표이며 실제 측정 없이 보장하지 않습니다.

## 소유권과 재생성

`dev/port.py`가 두 셸을 생성합니다. 입력은 패키지 내부 `dev/*shell_template.html`, `assets/css/core.css`, `assets/css/{tokens,visual-motion,responsive}.css`, `assets/js/{motion,study,responsive}.js`, `assets/fonts/`뿐입니다. `assets/shell.html`과 `assets/pack-shell.html`을 직접 수정하지 않습니다. 포털은 `scripts/visual_assets.py`를 통해 같은 자원을 한 번 넣습니다. 예전 Downloads 원본은 이 경로에서 필요 없습니다.
