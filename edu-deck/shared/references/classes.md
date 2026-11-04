> **로드 시점**: 슬라이드 HTML 조각을 쓸 때 (클래스 이름·단계 속성·모형 창 마크업 확인)

# 셸 클래스 사전

조각은 `assets/snippets/*.html` 을 복사해 고치는 것이 기본이다. 이 문서는 고칠 때 쓰는 이름표다.
아키타입 전용 클래스(rm-*, cmp, tok, cand, pb, tp, opt, qrow, ox, sk-*, ft …)는 조각 안의 예를 그대로 따른다.

## 슬라이드 뼈대

```html
<section class="slide" data-archetype="compare-2" data-variant="list" style="gap:32px">
  <div class="head"><p class="eyebrow">2. 우리 현장 · ② 규정</p><h2 class="title">휴식은 이렇게 정해져 있습니다</h2></div>
  … 본문 …
  <div class="callout" data-step="3"><b>정리하면</b> 2시간마다 20분, 그늘에서 쉽니다.</div>
  <aside class="notes">발표자 노트 110~450자 …</aside>
</section>
```

- `data-archetype` 필수(29종: references/layouts.md). 변형이 있으면 `data-variant`.
- 복습 대상이 되는 장은 `data-key="영문키"` 를 붙일 수 있다(확인 문제 `.chk` 의 `data-review` 와 짝 맺기).
- 발표·인쇄 슬라이드는 1920×1080, 안쪽 여백 128px, 세로 flex입니다. 좁은 화면에는 [반응형 읽기 배치](responsive.md)를 적용합니다. 간격은 8px 배수나 `--s*` 토큰으로 조정합니다. 색·반경·시간은 [DESIGN_TOKENS.md](DESIGN_TOKENS.md)를 따릅니다.
- 바탕: 기본(밝음) · `dark`(먹색) · `orange`(주황 전면). 가운데 정렬 `center`, 양끝 `between`.
- **조각에는 `<script>` 를 넣지 않는다.** 움직임은 단계 속성으로만 만든다.
- 각 슬라이드 끝에 `<aside class="notes">` 하나.

## 배치·글자

| 클래스 | 뜻 |
|---|---|
| `row` / `col` | 가로 flex(간격 32) / 세로 flex |
| `f1` `f2` `f3` | flex 비율 1·2·3 (예: 모형 `f3` + 설명 `f2`) |
| `card` | 카드(종이 바탕, 테두리, 둥근 모서리, 안쪽 40). `card h3` 44px |
| `body` 32px · `small` 28px · `label` 28px 굵은 주황 글 | 설명 글 |
| `ul.list` | 32px 목록(항목 3~5개) |
| `num` | 96px 주황 큰 번호 |
| `ico` | 56px 주황 아이콘 상자 |
| `pill` | 어두운 알약(마무리 요약) |
| `bar` | 160×12 주황 막대(마무리 위 장식) |
| `en` | 영어 용어를 작게: `손익계산서 <span class="en">Income Statement</span>` |
| `ex` | 회색 바탕 예문 상자(“…” 말하는 예) |
| `flow` + `arrow` | 가로 흐름 줄 + 주황 삼각 화살 |
| `callout` | 어두운 정리 띠, `<b>` 앞부분은 주황. 마지막 단계에 |
| `fact` | 파란 출처 칩: `<p class="fact" data-src="F03">고용노동부 보도자료(2025): 2시간마다 20분</p>` (여러 개 `data-src="F03,F04"`) |
| `qtag` | 파란 `퀴즈 N` 꼬리표(눈썹 자리) |
| `mk` | 주황 번호 원(40px). 모형 위 표시 ↔ `legend` 설명 |
| `legend` > `li` > `mk` + `h4` + `p` | 번호 설명 목록 |
| `hl` | 주황 테두리 강조(모형 안 요소) |
| `dash-flow` | 설명 흐름의 정적 점선. 셸이 필요한 순간에만 선/입자를 재생합니다(`<path class="dash-flow" stroke="var(--accent)" …/>`) |
| `todo` > `tbox` + `h4` + `p` | 누르면 체크되는 실천 항목 |

## 모형 창 `.win`

모든 모형은 창 틀 안에 넣는다. 안쪽 글은 20~26px.

```html
<div class="win f3">
  <div class="win-bar"><i></i><i></i><i></i><span class="wt">창 제목</span></div>
  <div class="win-body"> …아래 변형 중 하나… </div>
</div>
```

| 변형 | 마크업 |
|---|---|
| 채팅 | `<div class="main"><div class="msgs"><div class="u">요청</div><div class="a"><span class="av">AI</span><div class="at"><p>답</p></div></div></div><div class="input"><span class="ph">안내</span><span class="model">선택</span><span class="send">↑</span></div></div>` (왼쪽 메뉴 `side`, 첨부 `filechip`, 폴더 `folder`) |
| 문서 | `<div class="doc"><p class="doc-title">작업중지 안내</p><div class="doc-meta"><span>문서번호 …</span><span>2026. 7. 1</span></div><p>본문</p><p><span class="hl-line">강조 줄</span></p><p class="bad-line">틀린 줄(취소선)</p><div class="doc-sign"><span>현장소장</span><span class="stamp">승인</span></div></div>` |
| 표 | `<div class="xl-wrap"><div class="xl-formula"><b>fx</b><span>=SUM(C2:C5)</span></div><table class="xl"><thead><tr><th></th><th>A</th>…</tr></thead><tbody><tr class="hd"><th>1</th><td>열 이름</td>…</tr><tr><th>2</th><td>값</td><td class="n">12</td><td class="hot">강조</td><td class="bad">오류</td></tr></tbody></table></div>` |
| 입력 양식 | `<div class="fm"><div class="fm-row"><label>칸 이름</label><span class="fm-in">값</span></div><div class="fm-row"><label>…</label><span class="fm-in ph">비어 있음</span></div><div class="fm-check"><span class="cb on"></span>확인 항목</div><div class="fm-btns"><span class="btn">취소</span><span class="btn primary">제출</span></div></div>` (`fm-in hot` 강조, `btn go` 주황) |
| 메일 | `<div class="mail"><div class="mail-h"><p class="subj">제목</p><p><b>보낸 사람</b>…</p><p><b>받는 사람</b>…</p></div><div class="mail-b"><p>본문</p></div></div>` |
| 단체방 | `<div class="msgr"><div class="mg"><span class="who">반장</span><p>메시지</p></div><div class="mg me"><p>내 답장</p><span class="tm">14:05</span></div></div>` |

- 모형 안 글이 넘치면 검사기가 "잘린 글자" ERROR 를 낸다. 줄 수를 줄이거나 글을 짧게 쓴다.
- 모형 안 이름·숫자는 가상 값. 근거 있는 사실처럼 보이면 "예시"라고 밝힌다.

## 단계 속성

| 속성 | 동작 | 예 |
|---|---|---|
| `data-step="2"` | 2단계부터 보임(나타날 때 튀어나옴) | `<div class="card" data-step="2">` |
| `data-add="1"` | 1단계부터 보이고 1단계에서 주황 형광 | `<span class="add" data-add="1">, 그늘에서</span>` |
| `data-only="3"` | 3단계에서만 보임 | `<span data-only="0">?</span><span data-only="3">정답</span>` |
| `data-lit="2"` | 2단계부터 `.lit` (정답·강조 칸) | `<div class="opt right" data-lit="2">` |
| `data-until="1"` | 1단계까지만 보임 | `<span class="fm-in ph" data-until="1">` |

- 값은 0 이상의 정수. 슬라이드의 단계 수 = 가장 큰 값.
- `.lit` 에 모양이 바뀌는 것은 정해져 있다: `opt.right`(파란 정답 칸)·`opt.wrong`(흐려짐), `pb`(요청 틀 칩), `tp`(입력 줄), `pi`(계획 체크), `seg`(SVG 칸), `cand.top`(1위 막대). `card`·`win` 에 `data-lit` 를 붙여도 아무 변화가 없다. 카드 강조는 `data-step` 으로 나타나게 한다.
- 말풍선 `.a`는 내용이 읽히는 최종 상태로 작성합니다. 설명 장면의 등장은 공통 모션 엔진이 담당하며 별도 대기/생각 중 루프를 넣지 않습니다.
- 엔진: `window.deckGo(i, step)`, `window.deckInfo()`. 주소 `#5` 로 5번 슬라이드 바로 열기.

## 확인 문제 `.chk` (아키타입 check)

```html
<div class="chk" data-review="heat-index">
  <p class="chk-q"><span class="chk-n">1</span>체감온도 31℃면 어느 단계인가요?</p>
  <div class="chk-opts">
    <button class="chk-o">주의 단계입니다</button><button class="chk-o" data-ok>경고 단계입니다</button>
  </div>
  <p class="chk-why">체감온도 31℃부터는 폭염특보 기준 경고 단계입니다. 33℃부터 위험 단계입니다.</p>
</div>
```

- `chk` 상자 / `chk-q` 질문(번호는 `chk-n`) / `chk-o` 보기 단추(정답에만 `data-ok`) / `chk-why` 해설.
- 단추는 셸 스크립트가 받는다: 누르면 정답·고른 답 표시, 해설 공개, `chk-go`(다시 보기)·`chk-again`(다시 풀기) 단추가 생긴다. 조각에 단추 동작을 넣지 않는다.
- `data-review` ↔ 대상 장의 `data-key` 가 같아야 "○장 다시 보기"가 나온다. 열쇠는 짧은 영문(예: `heat-index`).

## 자습 레이어 (셸이 만드는 것 — 원고에 쓰지 않는다)

S(자습 모드)·P(인쇄: 한 장 요약·발표 대본)·G(용어집)는 셸 스크립트가 슬라이드 마크업(`aside.notes`, closing/rules-dark 장, `.chk`)과 deck.json 선택 키에서 자동으로 만든다. 이 클래스들(`st-…`, `chk-fb` 등)을 조각에 직접 쓰지 않는다.

## 아이콘

`<svg class="ico" aria-hidden="true"><use href="#i-hardhat"/></svg>` — 목록은 `references/icons.md`.

SVG 도식의 화살표 머리는 아이콘 묶음에 들어 있는 표식을 쓴다: `<path d="…" marker-end="url(#ah)"/>`. `ah` 주황 · `ahb` 파랑 · `ahg` 회색 · `ahk` 먹색. 양쪽 화살은 `marker-start` 도 같은 id 를 쓴다(자동으로 뒤집힌다).

색·기하·글꼴은 [DESIGN_TOKENS.md](DESIGN_TOKENS.md), 문장과 크기는 `expression.md`가 기준입니다.

## 공통 설명 도식

legacy와 팩 모두 `assets/css/visual-motion.css`의 아래 공통 어휘를 사용할 수 있습니다. `components.css`의 기존 클래스와 같은 토큰을 쓰지만 팩에 legacy 전체 CSS를 섞지는 않습니다.

| 종류 | 구조 | 뜻 |
|---|---|---|
| 흐름 | `.ed-diagram.ed-flow > .ed-node + svg.ed-connector` | 입력→처리→결과 |
| 계층 | `.ed-diagram.ed-tree > .ed-root + .ed-node` | 상위와 하위 |
| 관계 | `.ed-diagram.ed-hub > .ed-node + .ed-center + .ed-node` | 중심과 연결 대상 |
| 비교 | `.ed-diagram.ed-compare > .ed-node` 두 개 | 같은 기준의 전/후·A/B |
| 지도 | `.ed-diagram.ed-map > .ed-node` | 점 격자 안 개념 위치 |
| 장면 | `.ed-diagram.ed-scene > header + .ed-message + .ed-message.ed-reply` | 문서·채팅·화면 모형 |

선은 인라인 SVG `path`로 그립니다. `.ed-pipe`를 붙이면 mechanism에서 흐름 입자 대상이 됩니다. SVG에 한 문장 `aria-label`을 붙이고 노드에는 실제 개념 이름을 씁니다. 꺾은선·격자가 통계처럼 오해되지 않게 수치가 아닌 관계임을 밝힙니다. 도식에 CSS 애니메이션을 직접 넣지 않습니다. `.ed-icon-color`는 소량의 임팩트 아이콘용이며 설명 도식을 대체하지 않습니다.

### SVG 도형·글자 클래스(k-*)

직접 그리는 개념 도식(맞춤 SVG 일러스트)의 공통 채움·선·글자 클래스입니다. `visual-motion.css`에 있어 legacy와 팩 덱 모두 씁니다. 색은 의미 토큰(`--accent`, `--blue`, `--ink` 등)만 쓰며 고정 색을 넣지 않습니다.

| 클래스 | 뜻 |
|---|---|
| `k-frame` | 점선 밝은 틀(큰 개념 상자·묶음 외곽) |
| `k-blue` | 파랑 연면+파랑 선(개념 원·면) |
| `k-orange` | 주황 연면+주황 선(강조 개념 면) |
| `k-paper` | 종이 면+연한 선(도식 안 카드) |
| `k-gray` | 회색 면+연한 선(비활성·배경 면) |
| `k-solid-o` / `k-solid-b` / `k-solid-n` | 꽉 찬 주황·파랑·먹색 면(번호 원·강조 블록) |
| `k-ln-o` / `k-ln-b` | 굵기 5 주황·파랑 흐름 선(둥근 끝·이음) |
| `k-ln-n` | 굵기 4 먹색 선(구조·외곽선) |
| `k-ln-g` | 굵기 3 회색 점선(보조·예정 경로) |
| `k-t-hero` | 도식 안 48px 굵은 큰 글자 |
| `k-t-tag` | 도식 안 22px 보조 라벨(회색) |
| `k-t-w` | 어두운 면 위 종이색 글자 |
| `k-t-o` / `k-t-b` | 주황·파랑 강조 글자 |
| `k-note` | 점선 표기 칩 — `<p class="k-note">가상 예시</p>` · `개념도 · 측정값 아님`(사실 칩 `.fact`와 구분) |

도식 화살촉은 아이콘 묶음의 표식을 씁니다: `marker-end="url(#ah-o)"`(주황) · `url(#ah-b)`(파랑) · `url(#ah-n)`(먹색). 기존 `ah`(주황) · `ahb`(파랑) · `ahg`(회색) · `ahk`(먹색)도 그대로 씁니다. 흐름선은 `class="dash-flow k-ln-o"` 처럼 겹쳐 씁니다.

## 접근성·장식

- 장식 요소(배경 원, 뒤에 깔린 카드, 점 연결망)는 `aria-hidden="true"`.
- 도식 SVG 에는 `aria-label="한 문장 설명"`.
- 글자 20px 미만 금지. 작은 주황 글은 `var(--accent-text)`.

## 덱 전용 스타일

- 덱 폴더 `src/*.css` 는 조립 때 맨 뒤에 붙는다. 회사 색은 `:root{--accent:…;--accent-text:…}` 처럼 토큰만 덮어쓴다.
- 한 장에만 필요한 조정은 그 요소의 `style="…"` 로 한다. 셸의 핵심 클래스(slide head eyebrow title card callout fact win mk notes step-hide gone pop lit new)는 다시 정의하지 않는다.

## 채점 크레파스 모션 (`data-crayon`)

기존 저작 속성은 유지하며 렌더링은 공통 모션 엔진이 맡습니다. 클래스·속성만 쓰며 조각에 스크립트를 넣지 않습니다. 표시는 표시 대상마다 `.ed-mark` 래퍼 안에 만든 캔버스가 그립니다 — 입자 알갱이·필압 프로파일·손속 이징은 `dev/crayon-reference.html`의 승인된 기법을 공통 엔진으로 옮긴 것입니다.

| 표시 | 값 | 기본색 | 모양 |
|---|---|---|---|
| 채점 동그라미 | `data-crayon="circle"` | 빨강 | 요소를 한 바퀴 휘감아 돈다(마지막 꼬리가 휙 빠진다) |
| 체크 | `data-crayon="check"` | 파랑 | 짧은 내리획 뒤 위로 뻗는 꺾인 확인 선 |
| 밑줄 | `data-crayon="underline"` | 빨강 | 문구 아래 곡선 |
| 강조 | `data-crayon="highlight"` | 강조색 | 문구 가운데를 가로지르는 형광 밴드(두 번 칠한다) |

- 색 바꾸기: `data-crayon-color="red|yellow|blue"` (red→--danger, blue→--blue, yellow→--accent). 예: `<span data-crayon="underline" data-crayon-color="blue">핵심 문구</span>`
- 자동 채점(직접 붙이지 않는다): 확인 문제(check)에서 정답 단추가 공개되면 빨간 동그라미, quiz-ab 에서 정답 칸(`.opt.right`)이 단계로 켜지면 빨간 동그라미가 저절로 그려진다.
- 끄기: 슬라이드에 `data-crayon="off"` 를 붙이면 그 장은 자동·수동 표시가 모두 꺼진다. “다시 풀기”를 누르면 동그라미도 지워진다.
- 그려지는 시점: 장·단계 공개 때 경로를 따라 그립니다. 획마다 고정 시간(동그라미 750ms·체크 560ms·밑줄 600ms·강조 900ms)과 손속 이징을 씁니다. 이미 본 단계로 되돌아가면 다시 재생하지 않고 완성된 표시를 즉시 보입니다.
- reduced-motion·인쇄·자습에서는 완성된 획을 캔버스에 즉시 그립니다. 정답 글자는 별도로 유지합니다. 상세 계약은 [MOTION_LIBRARY.md](MOTION_LIBRARY.md)를 따릅니다.
- 권장 사용처: quiz·check 정답 공개(자동), worked-example·statement 의 핵심 문구 밑줄·형광펜. **남용 금지 — 슬라이드당 1~2개** (한 장에 4개 이상은 채점이 아니라 낙서다. 자동 채점 표시는 이 한도 밖). 밝은 바탕에만 자연스럽다(어두운 장 캔버스·rules-dark 는 피한다).
- 형광 강조는 `data-fx="mark"` (셸 덮개) 와 `data-crayon="highlight"` (캔버스 낙서) 두 가지다 — 다른 그림이므로 한 요소에 함께 쓰지 않는다(check_deck WARN). 효과 쪽 규칙은 아래 "강조 효과" 절과 [MOTION_LIBRARY.md](MOTION_LIBRARY.md) 에 있다.

## 강조 효과 (`data-fx`)

요소에 `data-fx="<이름>"` 을 하나 붙이면 셸이 보이게 되는 순간 한 번 재생한다. 이름 8종·속성·발화 규칙·사용 원칙은 [MOTION_LIBRARY.md](MOTION_LIBRARY.md) 의 "강조 효과 data-fx" 절을 따른다. 조각 예는 `assets/snippets/patterns/fx.html`.

| 클래스 | 모양 | 짝짓는 효과 |
|---|---|---|
| `.stamp` · `.stamp.ok` · `.stamp.no` | 판정 도장 원(지름 76px, -12도 기울임). `.ok` 초록(--success), `.no` 빨강(--danger) | `data-fx="stamp"` |
| `.kbd` | 키보드 키 모양(테두리 2px + 아래 5px 두껍게) | `data-fx="press"` |

- 덮개(`.ed-fx-strike`·`.ed-fx-mark`)와 글자 조각(`.ed-fx-ch`)은 엔진이 재생 때 만드는 것이라 조각에 직접 쓰지 않는다.
- `.stamp`·`.kbd`·부품 스타일은 공통 CSS 라 팩·시리즈 덱에서도 같은 모양으로 보인다.

## 가르치는 부품

부품 조각은 `assets/snippets/patterns/*.html` 에 있다. 슬라이드(아키타입 변형)가 아니라 호스트 아키타입 본문 안에 붙여 넣는 부분이다. 부품 안의 클릭·키 입력은 장 진행을 넘기지 않는다(복사·탭·핀을 눌러도 다음 장으로 가지 않는다).

| 부품 | 구조 | 동작 |
|---|---|---|
| `.code` | `.code > .code-head`(`span` 이름표 + `button.code-copy`) + `pre` | 복사 단추가 명령을 클립보드에 옮긴다. `pre` 안의 `.p`(프롬프트)·`.out`(출력)·`.c`(주석) span 은 복사에서 빠진다 — 명령만 복사된다. `.ph` 는 바꿔 넣을 자리 표시. 단추는 1.5초 "복사됨". `pre` 는 들여쓰지 않는다 |
| `.tabs` | `.tabs > .tab-bar > button` ↔ `.tab-pane` 1:1 | 첫 탭이 기본. 클릭·←/→·Home/End 로 전환하고 role·aria 는 셸이 채운다. 인쇄·자습·움직임 줄이기(정적 모드)에서는 모든 패널이 탭 이름(`.tab-pane-label`)과 함께 펼쳐 보인다 |
| `.faq` | `.faq > details > summary`(질문) + `p`(답) | 네이티브 details 토글. 정적 모드에서는 전부 펼쳐진다. 첫 항목을 미리 열어 두려면 `<details open>` |
| `.pin-shot` + `.pin-list` | `.pin-shot > .pin-frame > img` + `button.pin[data-k]`(left·top 은 이미지 기준 %) ↔ 같은 장 `.pin-list li[data-k]` | 같은 `data-k` 짝이 마우스·포커스·클릭 때 함께 `.on` 이 된다. 핀에 `data-step` 을 붙이면 그 단계에 나타난다. 이미지는 사용자 제공 base64 `data:` URI 만 — 없거나 외부 주소면 check_deck ERROR |
| `.go` | `button.go[data-go="N"][data-tab="M"]` | N번 장으로 가서 M번 탭을 열어 준다 |

- 핀 짝은 같은 장 안에서 맞춘다. 그림·목록 배치 자체는 호스트 아키타입이 정한다.

## 뷰어 도구

검색·목차·제목 맞춤·엔진 준비 표시는 공통 `assets/js/viewer.js`, 발표 덱 도구는 `assets/js/talk.js` 가 셸에서 만든다. 조각에 넣을 UI 는 없고 저작 때 쓰는 것은 아래 키와 속성뿐이다. 시리즈에서는 열린 편 기준으로 동작하고 허브 화면에서는 목차를 숨긴다. 입력 칸에 글자를 쓰는 동안에는 단축키가 동작하지 않는다.

| 키 | 동작 |
|---|---|
| → · ↓ · Space · Enter · PageDown | 다음(한 단계씩; 세로 읽기는 다음 장) |
| ← · ↑ · Backspace · PageUp | 이전(세로 읽기는 이전 장) |
| Home · End | 첫 장 · 마지막 장 |
| F | 전체화면 |
| N | 발표자 노트 |
| S · P · G | 자습 모드 · 인쇄 · 용어집 |
| Esc | 검색·목차·인쇄·자습 창 닫기(시리즈 허브 복귀) |
| Ctrl+K · Cmd+K · / | 슬라이드 검색 |
| O · ㅐ | 목차 |
| T · R · V (talk 덱만) | 타이머 시작·멈춤 · 타이머 처음부터 · 발표자 보기 |

- 검색은 제목·eyebrow·보이는 글자를 찾는다. 노트·대본·스타일·SVG 글자·숨은 보조물은 찾지 않는다. ↑↓ 로 고르고 Enter 로 이동한다. Esc 로 닫을 때는 키가 엔진(장 넘김)으로 새지 않게 막는다.
- 목차는 eyebrow 끼리 묶어 보여 주고 현재 장을 표시한다. 항목 클릭으로 이동한다.
- 세로 읽기(≤1199px, slide-fit 제외)에서는 장 본문 탭이 줌 뷰어를 연다: 현재 공개 단계 그대로의 장을 화면에 맞춰 보여 주고, 두 번 탭·핀치로 확대, ‹ › 로 이웃 장, `닫기`·Esc·뒤로가기로 닫는다. 버튼·`.chk`·탭·코드·핀 등 조작 요소 위의 탭은 열지 않는다. 세로 폰에서는 "가로로 돌리면 더 크게 보입니다" 안내가 세션당 한 번 뜬다.

### 제목 한 줄 맞춤 (`data-fit`)

제목(`.title`)이 지정 줄 수를 넘으면 베이스 크기의 80%(20% 축소)까지 줄여 맞춘다. `data-fit` 은 1줄, `data-fit="2"` 는 2줄 허용이다. 장을 넘길 때·창 크기가 바뀔 때·글꼴 준비 후·모드가 바뀔 때 다시 잰다. 세로 읽기도 같은 1920 배치라 같은 값으로 잰다. 축소 한도까지 줄여도 넘치면 check_deck 이 `제목 줄 수` 경고를 낸다.

### 엔진 실패 대비

셸 첫 스크립트가 `html.ed-js` 를 붙이고, 엔진 초기화가 끝나면 `ed-ready`, 실패하거나 3초 안에 준비되지 않으면 `ed-fail` 을 붙인다. JavaScript 가 꺼졌거나 실패했을 때(일부 미리보기 앱 포함)는 모든 장을 마지막 단계가 펼쳐진 모습으로 폭에 맞춰 위에서 아래로 이어 보여 주고, "브라우저에서 열면 넘기기·자습이 동작합니다" 안내를 한 줄 보인다. 화면 내용은 그대로 읽힌다.

발표 덱(deck.json `talk`)의 타이머·발표자 보기 운용은 [발표 덱(talk 모드)](talk.md) 을 따른다.
