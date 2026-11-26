---
name: keynote-3d
description: Use when the user wants a cinematic real-time 3D keynote, conference opening, product vision deck, stage presentation, WebGL camera choreography, volumetric lighting, or shader transitions rather than a study/document deck.
---

# keynote-3d

실시간 WebGL2 3D 장면, 카메라 안무, 키네틱 타이포, GLSL 전환을 사용하는 **무대 발표용 시네마틱 키노트**를 만든다. 결과물은 외부 런타임 URL이 없는 단일 오프라인 HTML이어야 한다.

## 언제 사용하는가

`keynote-3d`를 선택할 신호:

- “3D”, “WebGL”, “시네마틱”, “키노트”, “컨퍼런스 오프닝”, “무대 발표”, “카메라가 움직이는” 표현이 있다.
- 제품 비전, 전략 선언, 브랜드 스토리, 대형 화면 오프닝처럼 **감정적 몰입과 장면 전환**이 핵심이다.
- 조명, 소품, 입체 구조, 궤도, 부피 광원, particles, render-target transition이 필요하다.

`edu-deck`를 선택할 신호:

- 기술 교육, 보안 분석, 운영 매뉴얼, dense table, 코드, 정밀 아키텍처 도식, 퀴즈, 자습 진도가 필요하다.
- 독자가 글을 오래 읽고 복사·검색·인쇄해야 한다.
- 발표 무대보다 학습 완성도가 중요하다.

두 트랙을 한 파일에 섞지 않는다. 교육 본문은 `edu-deck`, 별도 3D 오프닝은 `keynote-3d`로 나누고, 필요하면 영상/GIF 같은 자산만 이동한다.

## 스토리보드 계약

각 장면은 다음 필드를 가진다.

```json
{
  "id": "lamp",
  "title": "Studio Desk Lamp",
  "enterWith": "portal-in",
  "cameraRig": {
    "type": "dolly",
    "beats": [
      {"from": [7.8, 4.2, 9.4], "to": [6.2, 3.5, 7.2], "target": [0, 1.15, 0], "fov": [46, 43]}
    ]
  },
  "beats": [
    {"duration": 7, "headline": "빛이 켜지는 순간", "sub": "부제", "points": ["근거 1"]}
  ],
  "notes": ["발표자 노트"]
}
```

필수 규칙:

- `id`는 안정된 소문자 slug, `title`은 사람이 읽는 장면명이다.
- `enterWith`는 `fade`, `wash`, `line`, `fold`, `portal-in` 중 하나다.
- `cameraRig.type`은 `orbit`, `dolly`, `crane`, `locked-off` 중 하나를 권장한다.
- `beats`는 장면당 보통 3개이며, 카메라 키와 텍스트 비트가 1:1로 맞아야 한다.
- `notes`는 화면 본문이 아니라 발표자가 말할 의도·주의점을 담는다.

## 오프라인 단일 HTML 계약

- 산출물은 한 파일이며 런타임 외부 URL/CDN/폰트/이미지/오디오 요청이 0건이어야 한다.
- 실시간 3D여야 한다. 2D 캔버스 그림을 quad에 붙여 3D처럼 보이게 하지 않는다.
- WebGL2 `#version 300 es`, perspective projection, 3D camera rig, directional + rim + spot lighting, 실제 3D geometry를 사용한다.
- 장면 전환은 이전 장면과 다음 장면을 각각 framebuffer/render target에 그린 뒤 GLSL로 두 텍스처를 합성한다.
- 지오메트리·파티클·오디오는 절차 생성을 기본으로 한다. 외부 자산은 라이선스가 확인된 경우만 vendoring한다.
- 텍스트는 접근성과 선명도를 위해 DOM overlay로 둘 수 있지만, 3D 장면 자체는 실제 WebGL2 geometry로 렌더링한다.
- `prefers-reduced-motion`이나 WebGL2 부재 시 정적 설명 fallback을 제공한다.

## 운영 계약

- URL 해시는 `#<scene>-<beat>` 1-based 형식이다. 예: `#2-2`.
- 공개 API: `window.ready`, `window.kn3d.go(scene, beat)`, `window.kn3d.next()`, `window.kn3d.prev()`, `window.kn3d.state()`.
- 입력: 좌/우 클릭, debounced wheel, `→`/`←`/`Space`/`O`/`N`/`M`/`A`/`F`/`.`/`?`.
- 음성/음향은 기본 OFF이며 `M` 토글로만 켠다. 자동 재생 정책을 우회하지 않는다.
- 크롬은 얇게 유지한다: 좌상단 장면 번호, 우상단 beat dots, 하단 2px progress, 우하단 mini controls.

## Playwright QA 게이트

대표 검증 URL은 `index.html?quick&headless=1` 또는 지시된 `index.html?headless=1`이다. `headless=1`에서는 `preserveDrawingBuffer: true`여야 한다.

최소 게이트:

1. headless Chrome을 `channel='chrome'`, `['--use-gl=angle','--use-angle=swiftshader','--enable-webgl']`, 1280×720으로 연다.
2. `pageerror` 0건, console error 0건, 외부 HTTP(S) 요청 0건이어야 한다.
3. `window.ready === true`가 10초 안에 충족되어야 한다. 좋은 샘플은 5초 미만이다.
4. WebGL2 context가 실제로 active여야 한다.
5. click, wheel, `#2-2` hash navigation이 각각 상태를 바꾸거나 정확한 장면/비트로 이동해야 한다.
6. 장면별 스크린샷이 검은 프레임이나 빈 프레임이 아니어야 한다.

Phase 1 대표 샘플은 `examples/phase1-sample/index.html`이며, QA 실행기는 `scripts/qa_capture.mjs`다.

## 작업 절차

1. 발표 목적과 청중을 한 줄로 정리한다.
2. 장면 3개 내외와 비트 구조를 스토리보드 계약으로 먼저 쓴다.
3. 장면마다 카메라 rig, 조명, 핵심 3D geometry, 전환 의미를 정한다.
4. 단일 HTML로 구현한다.
5. Playwright 게이트를 실행하고 실패를 고친다.
6. 스크린샷을 눈으로 확인한다. 조명 과잉, 텍스트 겹침, 섬광, 검은 프레임이면 수정한다.
7. 최종 보고에는 파일 경로, QA 명령, 통과/실패 증거, 스크린샷 경로를 남긴다.
