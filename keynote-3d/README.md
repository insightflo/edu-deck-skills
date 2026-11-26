# keynote-3d

시네마틱 실시간 3D 키노트를 단일 오프라인 HTML로 만드는 스킬 스캐폴드입니다. Phase 1은 순수 WebGL2 엔진 방식의 대표 샘플과 Playwright 검증 경로를 포함합니다.

## edu-deck과의 경계

- `keynote-3d`: 컨퍼런스 오프닝, 제품 비전 발표, 무대용 스토리텔링, 카메라 안무와 3D 조명이 핵심인 자료
- `edu-deck`: 기술 교육, 보안 분석, 운영 문서, dense table/diagram, 퀴즈와 자습 진도가 필요한 자료

두 트랙은 한 파일에 섞지 않습니다.

## 현재 구조

```text
keynote-3d/
  SKILL.md
  README.md
  examples/phase1-sample/index.html
  scripts/qa_capture.mjs
  scripts/package.json
```

`examples/phase1-sample/index.html`은 외부 런타임 URL이 없는 단독 파일입니다. 3개 장면 × 3개 비트, WebGL2 `#version 300 es`, 실제 3D geometry, instanced rendering, directional/rim/spot lighting, volumetric cone, framebuffer GLSL transition, hash/click/wheel/keyboard navigation을 포함합니다.

## QA 실행

```bash
cd keynote-3d/scripts
npm install --no-audit --no-fund
K3D_SHOT_DIR=<스크린샷-출력-폴더> node qa_capture.mjs
```

검증 조건:

- `pageerror` 0건
- 외부 HTTP(S) runtime request 0건
- WebGL2 active
- `window.ready === true` 10초 미만
- click, wheel, `#2-2` hash navigation 동작
- 장면 1/2/3 스크린샷 생성

`node_modules/`는 로컬 검증용이며 커밋하지 않습니다.
