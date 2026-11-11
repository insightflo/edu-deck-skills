# 스타일 프리셋 (style presets)

교육 덱·책의 **색과 모서리 한 벌**을 미리 정해 둔 폴더입니다. 레이아웃·모션·간격은
건드리지 않고, 엔진이 이미 쓰는 색 역할 토큰만 갈아 끼웁니다.

- 원본은 이 폴더의 `<id>.yaml` 입니다. CSS 는 `scripts/style_preset.py --apply` 가 만듭니다.
- `--apply` 는 덱의 `src/preset.css`(또는 책의 `pages/00-preset.css`)만 만들고, HTML 조각·
  `shell.html`·`pack-shell.html` 은 건드리지 않습니다.
- `build_deck.py` 는 `src/*.css` 를 자동으로 싣기 때문에, 파일이 생기면 그 덱은 바로 새 팔레트로 빌드됩니다.

## 16종

| id | 이름 | 장르 | 추천 테마 | 모서리·선 |
|---|---|---|---|---|
| `seoul-editorial` | 서울 에디토리얼 | 사내 보고·브랜드 가이드 | cobalt | 헤어라인, 반경 6/12/18 |
| `hanji-warm` | 한지 웜 | 문화·역사 교육 | cocoa | 헤어라인 |
| `nordic-slate` | 노르딕 슬레이트 | 리서치 요약·디자인 시스템 | graphite | 헤어라인 |
| `alpine-forest` | 알파인 포레스트 | 환경·지속가능성 | forest | 그림자 없음 |
| `blueprint-grid` | 블루프린트 그리드 | 아키텍처·설계 리뷰 | cobalt | 헤어라인 |
| `executive-navy` | 이그제큐티브 네이비 | 경영진 보고·이사회 | cobalt | 헤어라인 |
| `clinical-trust` | 클리니컬 트러스트 | 의료·임상·규정 준수 | ocean | 헤어라인 |
| `atelier-sand` | 아틀리에 샌드 | 워크숍·실습 | cocoa | 둥근 모서리 |
| `campus-chalk` | 캠퍼스 초크 | 강의·세미나 | forest | 그림자 없음 |
| `cyber-obsidian` | 사이버 옵시디언 | 보안·AI 기술 | midnight | 헤어라인 |
| `legal-charcoal` | 리걸 차콜 | 법무·계약·컴플라이언스 | graphite | 헤어라인 |
| `civic-ochre` | 시빅 오커 | 공공·정책 안내 | solar | 그림자 없음 |
| `pastel-studio` | 파스텔 스튜디오 | 온보딩·문화 소개 | berry | 둥근 모서리·옅은 그림자 |
| `mono-swiss` | 모노 스위스 | 타이포그래피·매니페스트 | graphite | 헤어라인, 최소 22px |
| `fintech-emerald` | 핀테크 에메랄드 | 금융·데이터 리터러시 | ocean | 헤어라인 |
| `museum-archive` | 뮤지엄 아카이브 | 아카이브·사례집 | cocoa | 헤어라인, 최소 22px |

`recommended_theme` 는 이 팔레트와 잘 맞는 **기존 테마 id**(`themes.css`)입니다. 프리셋을 쓰는
덱에는 `deck.json` 의 `theme` 키를 넣지 않습니다 — 두 색 체계가 같은 자리에서 싸웁니다.
테마가 필요한 다른 편과 나란히 둘 때만 참고값으로 씁니다.

## 토큰 이름표

YAML 의 이름과 엔진(tokens.css)의 이름이 1:1 이 아닙니다. 프리셋 CSS 는 **YAML 이름을 그대로
내보내고**, 별도 블록에서 엔진 이름으로 번역합니다.

| YAML (프리셋 CSS) | 뜻 | 엔진 토큰 |
|---|---|---|
| `paper` (`--bg`) | 슬라이드 바닥 | `--light` |
| `surface` (`--paper`) | 카드·표면 | `--paper` |
| `tint` (`--bg-2`) | 보조 채움 | `--chip` |
| `line` | 구분선 | `--line` |
| `ink` | 본문 | `--ink` |
| `ink-2` (`--soft`) | 보조 본문 | `--soft` |
| `ink-3` (`--mut`) | 캡션 | `--muted-num`(글자) — 엔진의 `--muted` 는 **옅은 선·면**이라 `--bg-2` 와 섞어 따로 만듭니다 |
| `brand` (`--blue`) | 주색 | `--blue` |
| `brand-text` (`--blue-text`) | 주색 글자 | `--blue-text` |
| `brand-tint` (`--blue-soft`) | 주색 연한 배경 | `--blue-soft` |
| `accent` | 강조 | `--accent` |
| `accent-text` | 강조 글자 | `--accent-text` |
| `accent-tint` (`--accent-soft`) | 강조 연한 배경 | `--accent-soft`, `--accent-light` |
| `night` / `night-2` / `night-line` | 밤 무대 바닥 / 밤 카드 / 밤 선 | `.slide.dark` 안에서 `--ink`·`--paper`·`--line` 자리를 대신함 |
| `on-night` / `on-night-2` | 밤 무대 본문 / 보조 글자 | `.slide.dark` 의 `color`·`--soft` |
| `radius-sm` / `-md` / `-lg` | 모서리 | `--r1` / `--r2` / `--r3` |

밤 장 주의: 엔진의 `.dark` 는 `background:var(--ink); color:var(--light)` 로 **이름의 뜻을 뒤집어**
쓰는 규칙입니다. 프리셋은 밤 장에서 `--ink`·`--light` 자체를 밤 토큰으로 바꾸고, 그 때문에 깨지는
안쪽 `.dark`·`.callout`·`.pill` 세 가지만 밤 토큰으로 다시 칠합니다.

## 대비 게이트

`--verify` 가 16종 전부에 대해 WCAG 2.1 상대휘도 공식으로 아래를 전수 계산합니다.

| 계열 | 조건 |
|---|---|
| a | `ink` vs `paper`·`surface` ≥ **7.0** |
| b | `ink-2` vs `paper`·`surface` ≥ 4.5 |
| c | `ink-3` vs `paper`·`surface` ≥ 4.5 |
| d | `brand-text` vs `paper`·`surface`·`brand-tint` ≥ 4.5 |
| e | `accent-text` vs `paper`·`surface`·`accent-tint` ≥ 4.5 |
| f | `on-night` vs `night`·`night-2` ≥ **7.0** / `on-night-2` vs `night`·`night-2` ≥ 4.5 |

미달 프리셋은 `--apply` 단계에서 거부됩니다(파일을 만들지 않음). 게이트를 통과해도 렌더 결과의
픽셀 대비는 `check_deck.py` 가 따로 잽니다 — 둘 다 통과해야 완료입니다.

## 사용법

```bash
cd edu-deck/shared/scripts
python3 style_preset.py --list                 # 16종 표(대비 여유 배수 포함)
python3 style_preset.py --verify               # 필수 키 + 대비 16쌍 전수 검사
python3 style_preset.py --apply seoul-editorial --deck ../../../examples/preset-demo
python3 style_preset.py --apply mono-swiss --book ../../../examples/book-demo
```

- `--apply ... --deck <폴더>` → `<폴더>/src/preset.css`
- `--apply ... --book <폴더>` → `<폴더>/pages/00-preset.css`
- 생성물 머리에 `preset-css` 표식이 있습니다. 표식 없는 파일은 손으로 쓴 것으로 보고 덮어쓰지
  않습니다(`--force` 로만 통과).

### 책(bookstyle-html) 쪽 한계

`build_book.py` 는 `pages/*.css` 를 자동으로 싣지 않습니다(쪽 조각 `*.html` 만 묶습니다).
`--apply --book` 은 오버레이 CSS 를 만들고 **어디에 붙여야 하는지까지 출력**합니다. 빌더를
고치는 일은 이 스킬의 범위 밖이라 하지 않았습니다.

## 저작 원칙

- 이 팔레트는 **우리 고유 자산**입니다. 외부에서 받은 프리셋 파일의 색값·문구·파일명을 옮기지
  않았고, 참고한 것은 "토큰을 의미 역할로 나눈다 / intent·use·avoid 로 용도를 적는다 / WCAG 로
  대비를 보정한다"는 **구조와 방법**뿐입니다.
- hex 는 손으로 고른 뒤 대비 계산으로 명도만 보정해 굳혔습니다. 값을 바꾸면 `--verify` 를 다시
  돌리십시오.

## 검증

```bash
cd edu-deck/shared && python3 -m unittest dev.test_style_presets -v
```

테스트는 16종 존재·필수 키·대비 16쌍·`--apply` 산출 CSS 유효성·덮어쓰기 가드·재적용 동일성,
그리고 외부 흡수 폴더(`workspace/absorb/style-presets`, `style-theme`)와 파일명·내용이 겹치지
않는지를 확인합니다. 실물 검증은 `examples/preset-demo`(빌드→`check_deck.py`→`capture_deck.py`)입니다.
