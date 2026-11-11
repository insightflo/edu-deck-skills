# 페이지·블록 패턴

모든 쪽은 `<section class="page …" data-type="…">` 이다. 빌드가 `data-pno` 와 바닥글 쪽 번호를 다시 매긴다. 사례 색은 쪽 스타일에 `--c:#2B59FF` 처럼 준다.

## 쪽 종류 (`data-type`)

### cover — 표지
`class="page pg-cover"`. 어두운 바탕, 큰 제목(`h1` + `em` 그라데이션), 부제 `.sub`, 하단 `.nums`(큰 숫자)와 `.meta`. 배경 사진이 있으면 `<img class="bgimg">` + `.shade`. 표지에 책 제목을 쓰는 것은 이 양식의 기본이다(강의 슬라이드 표지 규칙과 다르다).

### toc — 목차
`.eyebrow` + `.h1` + `.toc-sec` 안의 `.toc-row`(`.n` 번호, `.t` 제목, `.p` 쪽)에 `data-goto="N"`. 사례가 많으면 `.grp` + `.toc-cases` / `.toc-case`.

### article — 본문
`pg-article`, 선택적으로 `t-tint`(옅은 바탕) 또는 `t-dark`(네이비). 골격은 `.eyebrow` · `.h1` · `.lead` · 아래 블록 · `.pg-foot`.

### divider — 부 시작
`pg-divider`. `.bg` 그라데이션, 큰 숫자 `.big`, `.pn`(PART 01), `h2`, 설명 `.d`, 하단 `.list`에 `data-goto`.

### story — 사례 이야기
`pg-story`, `--c` 로 강조색. `.cs-top`(No, `.badge`, `.chip`, `.field`) → `.org` → `h2` → `.svc` → `.flow`(.prob / .sol) → `.funcs` → 하단 `.point`( `data-dock="point"` ).

### evidence — 사례 근거
`pg-evidence`, 같은 `--c` 와 `data-id`. `.ev-hd` → 사진 `.photos.n1|.n2` > `.photo`(`data-zoom`, `figcaption`) 또는 개념도 `.b-figure` → `.ba` 전후 비교(`.btext` 또는 `.brow` 막대) → `.kpis` → `.tags` → 선택 `.cs-links`( `data-dock="links"` ).

### back — 뒤표지
`pg-back`. 짧은 선언 `h3` + `.ed`(편집·출처·발행).

### blank — 빈 노트 쪽
면맞춤용. `.memo` + `.lines`. 내용을 채울 수 있으면 쓰지 않는다.

## 본문 블록 (article 안에서)

| 클래스 | 쓰임 |
|---|---|
| `.b-heading` | 구간 소제목. `small` 로 보조 설명 |
| `.b-text` | 짧은 본문 단락 |
| `.b-bullets` | 점 목록 |
| `.b-compare` | 이전/이후 두 칸 + 가운데 화살표. 강조 칸은 `.col.hi` |
| `.b-levels` | 단계 막대. 각 `.lv` 에 `height` 와 배경색 |
| `.b-quote` | 인용. 본문 + `span` 출처·해설 |
| `.b-stats` | 큰 숫자 칸. `--n` 으로 열 수 |
| `.b-donut` | 도넛 + `.legend` |
| `.b-bars` | 가로 막대 |
| `.b-cards` | 2열 카드. `--c` 로 강조. 원본은 카드 왼쪽 4px 색 선을 쓴다 |
| `.b-highlights` | 임팩트 숫자 그리드(특히 `t-dark`) |
| `.b-caselist` | 사례 목록 행 |
| `.b-steps` | 번호 단계 |
| `.b-road` | 화살표로 이어진 로드맵. 마지막 칸이 강조 |
| `.b-checks` + `.chk` | 누르는 체크리스트. 점수는 `[data-role=score]` |
| `.b-take` | 시사점 목록 |
| `.b-links` | 참고 링크 2열 |
| `.b-note` | 짧은 주의 상자 |
| `.b-figure` | 그림. `--fh` 높이, `figcaption` 필수 |

이동은 `data-goto="쪽번호"`, 그림 확대는 `data-zoom="1"`. 바닥 고정 요소는 `data-dock` 이름을 준다(검사기가 본문과 겹치는지 본다).
