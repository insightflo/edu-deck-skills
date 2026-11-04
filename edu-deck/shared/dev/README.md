# edu-deck 자산 개발·검증

덱 저작은 이웃 `edu-deck-solo/SKILL.md`·`edu-deck-series/SKILL.md`를 따릅니다. 이 폴더는 공통 자산을 고치는 사람용입니다.

## 소유권

- `shell_template.html`·`pack_shell_template.html`: 발표 엔진과 다섯 공개 빌드 표식.
- `assets/css/core.css`·`components.css`: legacy 정적 배치.
- `assets/css/tokens.css`·`visual-motion.css`: 두 경로 공통 시각 체계.
- `assets/js/motion.js`: 시그니처·SVG 채점·전환·취소 처리·`data-fx` 저작 효과 한 곳.
- `assets/js/patterns.js`: `.code` 복사·`.tabs`·`.faq`·`.pin-shot` 핀·`.go` 이동 등 저작 패턴 동작 한 곳(`motion_js()`가 motion.js 뒤에 이어 붙여 같은 마커로 주입).
- `assets/css/responsive.css`·`assets/js/responsive.js`: [화면 크기별 읽기 계약](../references/responsive.md). 좁은 화면의 1920 배치 축소 스택·터치 탐색·가로 맞춤 모드(`ed-slidefit`)·탭으로 여는 줌 뷰어·세로 폰 안내.
- `assets/js/viewer.js`·`assets/css/viewer.css`: 검색 대화상자(Ctrl+K·Cmd+K·/), 목차 대화상자(O·ㅐ·버튼), `data-fit` 제목 줄임, 스크립트 실패 연속 보기(`ed-js`/`ed-ready`/`ed-fail`), 발표자 창 껍데기.
- `assets/js/talk.js`: `deck.json`의 `talk`가 있을 때만 동작하는 발표 모드. T(ㅅ)·R(ㄱ) 타이머, N 패널 누적 표시, V(ㅍ) 발표자 창과 BroadcastChannel·storage 동기화.
- `assets/js/study.js`: 자습·인쇄·용어집·퀴즈 상태. 모션 상태를 중복 소유하지 않습니다.
- `assets/fonts/`: 수정하지 않은 Pretendard 원본과 OFL. 빌드 시 CSS data URL 및 라이선스 전문으로 포함합니다.
- `scripts/visual_assets.py`: 공통 시각 자원을 조립합니다. 시리즈 조립기도 같은 함수를 사용합니다.

```bash
python3 dev/port.py
```

이 명령은 패키지 내부 파일만 읽어 `assets/shell.html`과 `assets/pack-shell.html`을 다시 씁니다. Downloads 원본·네트워크·설치가 필요 없습니다. 생성된 셸을 직접 수정하지 마세요.

## 검사

```bash
python3 -m unittest discover -s dev -p 'test_*py'
python3 dev/fill_test.py <새-폴더>
python3 scripts/build_deck.py <새-폴더>
python3 scripts/check_deck.py <새-폴더>/filltest.html --json <새-폴더>/check.json
python3 dev/test_pack_browser.py <새-64조합폴더>
python3 dev/test_pack_browser.py <새-상호작용폴더> --interactions-from <64조합폴더>
python3 dev/test_responsive.py --out <새-반응형검사폴더>
python3 dev/test_responsive_interactions.py <반응형검사폴더>
python3 dev/test_visual_motion_check.py
python3 dev/visual_motion_check.py --out <새-시각검사폴더>
```

`fill_test.py`는 32 조각·57 변형의 최대 글자수 시험입니다. 실제 강의가 아니므로 흐름·분량·시각 짝 경고는 별도로 해석합니다. `test_visual_motion.py`는 실제 브라우저에서 시그니처·단계 재생·정적 모드·폰트·폴백을 확인합니다. 이 검사는 독립 미학 심사나 프레임 성능 측정을 대신하지 않습니다.

`visual_motion_check.py`는 같은 최대 길이 시험 원고의 57변형·232단계를 검사합니다. 0/75/150/300/500/1200ms의 실제 WAAPI 효과를 멈춰 프레임을 저장하고, 글자·연결선 대비와 잘림, 토큰 밖 값, 현재 단계의 reduced-motion/자습·마지막 단계의 인쇄 완결을 확인합니다. rAF(브라우저 화면 갱신 콜백)는 별도 페이지에서 캡처·DOM 검사 없이 실제 모션을 재생하며 측정합니다. 결과는 `summary.json`, `coverage.json`, `static-modes.json`, `raf-60hz.json`, `all-archetypes.png`에 남습니다. 실패는 종료 코드 1입니다.

`--quick`은 소스 토큰 검사만 수행하며 전체 통과를 뜻하지 않습니다. `--slides 0,2`도 부분 진단입니다. 자리표시 안내 문구 자체는 글자 한도를 넘으므로 전체 검사는 기존 `fill_test.py`로 한도를 채운 원고를 만듭니다. 배경 그라디언트는 색 끝값을 보수적으로 검사하며, 장식이 아닌 SVG 연결선의 대비도 별도로 기록합니다. 모든 UI의 WCAG 적합성·학습 효과·실제 기기 성능은 이 자동 검사만으로 보증하지 않습니다.

`make_snippets.py`는 과거 기준 덱에서 조각을 옮긴 역사적 도구입니다. 원본 파일이 필요하며 현재 조각을 덮어쓸 수 있으므로 일반 빌드나 새 모션 재생성에 호출하지 않습니다. `make_icons.py`·`defect_test.py`는 아이콘 생성·결함 탐지 시험용입니다. `crayon-reference.html`은 과거 캔버스 기법 참고 자료로, 현재 런타임에 포함하지 않습니다. 다만 그 입자·필압·손속 알고리즘은 런타임 `assets/js/motion.js`의 `mark()`가 이식해 씁니다.

## Changelog

### 뷰어·발표 모드·가로 맞춤(phase 2)

- 뷰어: `/`·Ctrl+K·Cmd+K 검색 대화상자(제목·아이브로·본문 색인, ↑↓·Enter 이동, Escape 닫기), `O`·`ㅐ`·버튼 목차 대화상자(아이브로 묶음·현재 장 표시), 상단 막대의 검색·목차 버튼. 입력 칸에서는 단축키를 가로채지 않습니다.
- `data-fit`(빈 값=1줄, `data-fit="2"`=2줄): 제목 글자를 기본의 80%까지만 줄여 맞추고, 넘치면 check_deck이 WARN. 슬라이드 전환·크기 변화·글꼴 준비 때 다시 잽니다.
- 스크립트 부재·초기화 실패: 첫 스크립트가 `ed-js`를 찍고 엔진이 `ed-ready`, 3초 초과·예외·`window.onerror`는 `ed-fail`. 실패·no-JS에서는 모든 슬라이드가 최종 상태로 페이지 너비에 맞춰 세로로 쌓이고 안내줄이 뜹니다.
- 발표 모드(`deck.json`의 `talk`): T(ㅅ) 타이머 시작·일시정지, R(ㄱ) 초기화, 상단 시계에 경과/계획 누적·지연 시 `--danger`. N 패널 머리에 이 장 `data-sec`와 "~mm:ss까지". V(ㅍ) 발표자 창(현재·다음 장 정지 미리보기·노트·타이머·이전/다음), BroadcastChannel+storage 양방향 동기화, 팝업 차단 시 토스트. `talk` 없는 덱에는 발표 UI·경고가 없습니다.
- `check_deck` 발표 전용 WARN: `data-sec` 누락, 합계와 `talk.total` ±10% 초과, 노트가 `data-sec×rate/60×1.1`(한글 음절+영숫자 단어) 초과, 1줄 넘는 제목.
- `build_deck --notes OUT.md`: 장마다 번호·제목·`data-sec`·누적·대본 읽기 어림 초·노트 본문의 리허설 시트.
- 가로 맞춤: 가로 방향이고 width≥960·height≥540이면 `ed-slidefit`(1920 무대 축소+터치 내비·스와이프). 그 외 ≤1199px은 세로 읽기 유지. `?view=slide`/`?view=scroll` 강제. 회전 시 장·단계·퀴즈 상태 보존. 맞춤 모드에서 아래 내비 높이만큼 무대 축소·재중앙.
- 읽기 모드에서 인라인 `top`·`margin:auto`가 남긴 겹침 수정: `[data-ed-layout]`의 `inset:auto`에 `!important`, 자동 마진 요소는 `data-ed-autom`으로 표시해 상하 마진 0.
- 시험: `dev/test_viewer.py`(검색·목차·폴백·data-fit·모드 클래스), `dev/test_talk.py`(타이머·노트 머리·발표자 동기화·정지 미리보기·경고·리허설 시트). `test_responsive.py`는 가로 맞춤 모드에서만 본문 글자 하한 검사를 면제(무대 축소가 본래 동작), 페이지 넘침 검사는 유지.

### data-fx 효과·저작 패턴

- `data-fx="이름"` 여덟 저작 효과(strike·stamp·mark·count·travel·block·type·press)와 `data-fx-at` 지연. 드러나는 순간에 한 번만, 정적 모드·지난 단계에서는 최종 상태만.
- `.stamp.ok/.stamp.no`·`.kbd` 시각과 `.code`·`.tabs`·`.faq`·`.pin-shot`+`.pin-list`·`.go[data-go][data-tab]` 패턴을 공통 CSS·`patterns.js`로 추가.
- `check_deck` 신규 규칙: 모르는 data-fx(ERROR)·fx+crayon 중복·장당 효과 3초 초과(WARN)·`.pin-shot` 이미지 없음·외부 주소(ERROR)·외국어 문장(WARN).
- 셸의 클릭·키 넘김 무시 목록에 패턴 선택자 추가. 조각은 `snippets/patterns/`에 부분 조각으로 분리.
- 시험: `dev/test_fx_patterns.py`(실제 Chromium, 임시 덱).

### 시각·모션 검증 마감

- 채점 표시 SVG를 일반 반응형 크기 규칙에서 제외해 답안 높이를 유지합니다.
- 아키타입 시그니처의 글자 등장은 투명도 대신 위치·크기 변화를 사용하고, 새 말풍선에는 핀 확대 동작을 적용하지 않습니다.
- 표지·오답·도식의 대비와 아바타 줄바꿈을 보강했습니다. 정답·단계·노트 내용은 유지합니다.
- 전체 단계 프레임·정적 모드·연결선 대비·실측 프레임 로그 검사와 실패 탐지 대조 시험을 추가했습니다.

### 반응형 보기

- solo classic·pack·series 공통 세로 읽기, 16px 이상 본문, 44px 터치 탐색과 안전 영역.
- 허브 3종·카드·장면 모형 재배치, SVG 도식의 화면 폭 맞춤과 단계별 줄바꿈 글자 목록.
- 좁은 화면의 배경 클릭·스와이프 넘김 중단, 회전 상태 보존, 데스크톱·인쇄 계약 유지.
- 실제 기기·다른 브라우저 검증은 자동 Chromium 검사와 구분해서 보고.

### 시각·모션 통합

- 15색 의미 체계, 임베드 Pretendard+OFL, 3반경·2그림자·8px 간격.
- 29 실행 시그니처와 팩 어댑터, 방향성 전환, 단계 재생, 정적 완결 처리.
- 독립 무한 루프·SMIL·캔버스 채점을 공통 엔진의 유한 효과와 SVG 표시로 교체.
- 시리즈 `deckstep` 연결, 텍스트 전용 본문 경고, 공통 설명 도식·팩 모티프.
- `port.py`를 오프라인 재생성 경로로 전환. 역사적 ZIP은 변경하지 않음.

### 세로 읽기 = 스크롤 연속 읽기

- `ed-compact`(≤1199px, 맞춘 한 장 보기 제외)에서 모든 장이 한 줄 스크롤로 이어지고, 단계는 요소가 화면 85% 선을 넘을 때 자동으로 열립니다. 한 번 열린 단계는 위로 돌려도 닫히지 않습니다.
- 현재 장은 화면에 가장 넓게 보이는 장(번호·진행·해시·노트·자습이 따라감). 이전/다음·화살표 키·검색·목차·해시는 장 단위로 이동하고, 회전은 읽던 장 머리를 유지합니다.
- 글자 있는 SVG 도식은 좌우 이동 대신 항상 화면 폭에 맞추고 단계별 글자 목록은 유지합니다. 표·모형 창·도식 행도 폭에 맞추고, 코드 블록만 안쪽 가로 스크롤을 둡니다. 데스크톱·맞춘 한 장·인쇄의 단계별 넘김은 그대로입니다.

### 세로 읽기 = 원본 배치 축소(재배치 폐기)

- `ed-compact`는 더 이상 장 안을 재배치하지 않습니다. 모든 장이 원래 1920×1080 배치 그대로 `transform: scale(무대폭/1920)`(`--ed-s`)로 축소되어 세로로 쌓이고, 배치 의미(도식 연결·지시 관계·시선 흐름)가 보존됩니다. 행→열 재배치·카드 격자·16px 글꼴 바닥·`data-ed-layout`/`data-ed-autom` 초기화·`.ed-diagram-labels` 도식 글자 목록을 모두 제거했습니다.
- 읽기 보조는 스크롤 단계 공개(85% 선, 열림 유지)와 줌 뷰어입니다. 장 본문 탭 → `.ed-zoom`(role=dialog)에 현재 공개 단계 그대로의 읽기 전용 복제를 화면 맞춤으로 열고, 한 손가락 이동·핀치·두 번 탭(1×↔2.5×)·‹ › 이웃 장·닫기/Esc/뒤로가기를 지원합니다. 버튼·`.chk`·탭·코드·핀 등 조작 요소 위의 탭은 열지 않습니다. 세로 폰에서는 "가로로 돌리면 더 크게 보입니다" 안내가 `sessionStorage`로 세션당 한 번 뜹니다.
- 폰 가로(높이 ≤500px)는 같은 축소 스택이며 탐색줄은 상태줄+버튼 한 줄 가로 스크롤로 유지합니다.
- 가로 높이 맞춤: 배율 `--ed-s`는 `min(무대 폭/1920, 사용 높이/1080)` — 사용 높이는 위쪽 막대 아래~탐색줄 위 사이 실측 띈 높이 − 간격(8px×2). 가로 휴대폰에서는 장 하나가 화면 크롬 사이에 통째로 들어오고, 높이 기준으로 좁아진 폭은 `--ed-x`로 가로 가운데 둡니다(가로 넘침 없음). 장 머리 맞춤 오프셋도 실측 위쪽 막대 아래+8px로 둡니다.
- 시험: `test_responsive.py`는 글꼴 하한 대신 장 폭≤뷰포트이며(폭=뷰포트 또는 높이=사용 높이, ±2px)·가로 넘침 없음·폭별 정규화 배치가 1920 기준 1% 안으로 같은지를 확인하고, `test_responsive_interactions.py`는 스크롤 공개·줌 뷰어(탭·두 번 탭·이전/다음·닫기)·`.chk` 탭 미열림·안내 세션 한 번·`ed-diagram-labels` 부재·844×390/390×844에서 다음 점프 후 장 상자가 위쪽 막대~탐색줄 사이에 온전히 드는지를 확인합니다.

시각 감사·전체 64조합 재검사·독립 두 관점 리뷰 결과는 작업별 검증 보고서에서 확인해야 합니다. 이 변경 기록 자체는 PASS 증거가 아닙니다.
