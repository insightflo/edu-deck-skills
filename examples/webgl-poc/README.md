# WebGL2 프레젠테이션 엔진 POC

`index.html` 하나만 여는 오프라인 POC입니다. 외부 CDN·이미지·오디오 파일이 없고, 순수 WebGL2 + GLSL 300 es + Canvas 2D + Web Audio API만 사용합니다.

## 구조

- 단일 `<canvas id="stage">`가 전체 무대입니다.
- Canvas 2D가 1920×1080 장면 텍스처를 실시간 생성하고, WebGL2 프래그먼트 셰이더가 `uTexA`/`uTexB`를 `uProgress`, `uDir`, `uTx`, `uTime`으로 합성합니다.
- 전환 ID 0~9: fade, fold, wash, flaps, slam, daybreak, line, tear, portal-in, portal-out. 출력은 ACES 톤매핑과 미세 비네팅을 거칩니다.
- 장면 데이터는 5개 장면 × 3비트(총 15비트)입니다. 시작 시 `warmAll()`이 셰이더 컴파일과 5개 장면 썸네일 준비를 마친 뒤 `window.ready = true`를 설정합니다.
- WebGL2가 없으면 Canvas 2D 폴백으로 장면을 렌더링합니다.

## 단축키

| 키 | 동작 |
|---|---|
| `→` / `Space` | 다음 비트 |
| `←` | 이전 비트 |
| `N` | 발표자 노트 패널 |
| `O` | 5개 장면 썸네일 개요 |
| `M` | 음소거 토글 |
| `A` | 자동 재생 |
| `F` | 전체화면 |
| `.` | 블랙 화면 |
| `0`~`9` | 해당 전환 효과로 즉시 이동 테스트 |

첫 키 입력 또는 클릭에서 `AudioContext.resume()`을 시도합니다. 사운드는 파일 없이 오실레이터, `BiquadFilterNode`, 절차적 impulse를 사용하는 `ConvolverNode`로 합성됩니다.

## URL 해시와 자동화 훅

- 해시 형식: `#<장면id>-<비트>` 또는 `#<1-based 장면 번호>-<비트>` — 예: `#lamp-1`, `#shader-2`, `#3-2`
- `hashchange` 즉시 해당 상태로 점프합니다.
- `?quick` — 전환/비트 애니메이션을 즉시 정착합니다.
- `?headless=1` — `preserveDrawingBuffer: true`로 WebGL2 컨텍스트를 생성합니다. `navigator.webdriver`가 true여도 같은 경로를 사용합니다.
- `window.webglDeck` 디버그 API: `state()`, `goto(scene, beat)`, `next()`, `prev()`, `setTransition(tx)`, `warmAll()`, `scenes`

## 검증

브라우저에서 직접 열거나, 저장소 루트에서 task 문서에 있는 Playwright 스크립트를 실행합니다. 핵심 확인은 `window.ready === true`, `#3-2` 해시 점프 후 `state().sceneIndex === 2 && state().beatIndex === 1`, `.` 키의 `body.blackout` 토글입니다.

파일 크기 제한은 60KB이며, 이 POC는 그보다 작은 단일 HTML로 유지합니다.
