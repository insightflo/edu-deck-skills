# bookstyle-html: 자료 → 화면을 가득 채우는 플립북 HTML

첨부된 인사이트북(ko-doc-studio 책 양식, 600×820 쪽, 펼침 넘김)의 구조와 색·블록을 옮긴 스킬이다. **원본과 다른 점 하나**: 책 프레임이 화면을 가득 채운다. 위아래 여백을 남기던 무대와 0.96 축소는 쓰지 않는다. 상단 막대와 하단 조작은 책 위에 겹치고, 잠시 후 사라진다. 표지·뒤표지처럼 한 장만 보일 때는 그 한 장이 화면을 채우고, 두 쪽 펼침은 짧은 변에 맞춰 커진다.

원본의 기관명·사진·수치는 키트에 넣지 않았다. 샘플은 중립 주제 「작은 팀의 지식 노트」(8쪽)다.

- **모습**: 흰 종이 쪽(600×820), Pretendard, 파란 강조(#2B59FF)와 민트 포인트, 어두운 남색 무대. 표지·뒤표지는 네이비 위 큰 제목. 본문은 흰 바탕, 필요하면 틴트·다크 쪽.
- **구성**: 표지 → 목차 → 본문 → 부 표지 → 사례는 이야기+근거 한 쌍 → 정리 → 뒤표지.
- **뷰어**: 넓은 화면은 펼침 책장 넘김, 휴대폰·세로는 한 장씩. 키·클릭·스와이프, 목차, 전체화면, 인쇄(읽는 사람용).
- **결과물**: HTML 한 파일. **PDF 파일은 만들지 않는다.** 뷰어의 PDF 단추는 읽는 사람이 인쇄할 때만 쓴다.

## 하우스 규칙

1. **책 프레임은 화면을 가득 채운다.** 스테이지를 `inset:0` 으로 두고, 축소 여유(0.96/0.97)를 두지 않는다. 키트의 `viewer.js`·`book.css`를 그대로 쓴다. 예전처럼 책 주위에 큰 남색 테두리를 남기지 않는다.
2. **반응형은 기본.** 좁거나 세로 화면은 한 장 모드. 조작은 화면을 밀어내지 않고 겹친다.
3. **링크 미리보기(OG).** 배포할 책은 `book.json` 의 `og` 에 절대 URL을 넣고, 1쪽으로 1200×675 JPG를 만든다.
4. **글보다 도식.** 한 쪽에 글을 가득 채우지 말고, 비교·단계·숫자·흐름 블록이나 개념도로 보이게 한다. 빈 사진 칸(`.nophoto`)은 도식이나 원문 그림으로 채운다.
5. **원문 그림은 키우고 캡션.** 사진·도식에는 `figcaption` 에 출처를 쓴다. 없는 현장 사진을 지어내지 않는다.
6. **사실은 원문 그대로.** 숫자·이름·인용·URL을 바꾸지 않는다. 샘플 템플릿의 수치는 구성 예시일 뿐이다.
7. **HTML만.** 이 스킬로 PDF 파일을 만들어 넘기지 않는다.
8. **이 양식은 책이다.** 표지에 제목을 크게 쓴다. 강의 슬라이드 스킬의 “표지에 책 제목 금지”는 여기 적용하지 않는다. 인용 상자·카드의 왼쪽 강조 선은 원본 책 양식 그대로 둔다.
9. **원본 내용·상표를 새 책에 쓰지 않는다.**

## 스킬 폴더

이 GUIDE.md 가 있는 폴더를 `$SKILL_DIR` 라고 부른다.

| 경로 | 내용 |
|---|---|
| `references/writing.md` | 자료를 쪽으로 나누는 법 |
| `references/patterns.md` | 쪽 종류 8가지와 본문 블록 |
| `references/components.md` | 색 토큰, 뷰어, book.json, 주소 모드 |
| `assets/template/` | 샘플 8쪽 프로젝트 |
| `assets/kit/` | `book.css`, `viewer.js`, `shell.html` |
| `scripts/build_book.py` | 검사 후 HTML 한 파일로 묶기 |
| `scripts/preview.py` | `check` · `sheet` · `shot` · `view`(1920×1080 화면 가득 채운 표지) |
| `scripts/og_image.py` | 1쪽으로 1200×675 JPG |

필요한 것: python3, 미리보기·OG에는 크롬, OG에는 Pillow. 크롬은 `CHROME_PATH` 가 있으면 그것을 쓰고, 없으면 macOS 기본 설치 경로(`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`)를 먼저 본 뒤 PATH 의 `google-chrome`·`chromium`·`chromium-browser` 를 찾는다. 아래 예시의 `CHROME_PATH=/workspace/chrome-wrap.sh` 는 샌드박스 상자 기준이므로, 로컬 macOS 에서는 그 환경변수를 빼고 실행한다.

## 작업 순서

### 1. 자료를 끝까지 읽고 구성을 짠다
`references/writing.md` 를 따른다.

### 2. 프로젝트 폴더를 만든다
```bash
cp -r "$SKILL_DIR/assets/template" ./<이름>-book
```
`book.json` 의 `id`·`title`·`subtitle`·`brand`·`footer`·`og` 를 바꾸고, `pages/*.html` 을 자료로 다시 쓴다. 샘플 문장·예시 숫자는 지운다.

### 3. 빌드한다
```bash
python3 "$SKILL_DIR/scripts/build_book.py" ./<이름>-book -o ./<이름>-book/<이름>-book.html
python3 "$SKILL_DIR/scripts/build_book.py" ./<이름>-book --check
```
`[오류]` 가 있으면 묶지 않는다. `[주의]` 도 0건으로 만든다.

### 4. 눈으로 점검한다
```bash
CHROME_PATH=/workspace/chrome-wrap.sh python3 "$SKILL_DIR/scripts/preview.py" check ./<이름>-book/<이름>-book.html
CHROME_PATH=/workspace/chrome-wrap.sh python3 "$SKILL_DIR/scripts/preview.py" view  ./<이름>-book/<이름>-book.html -o ./<이름>-book/shots
CHROME_PATH=/workspace/chrome-wrap.sh python3 "$SKILL_DIR/scripts/preview.py" shot  ./<이름>-book/<이름>-book.html -o ./<이름>-book/shots --pages 1,2,3
```
`view` 캡처에서 책이 화면 높이(또는 너비)를 가득 채우는지 확인한다. 위아래에 두꺼운 남색 띠가 남으면 키트 CSS/JS가 아닌 옛 뷰어가 들어간 것이다.

크롬이 90초에서 멈추면 `--no-sandbox` 가 있는 래퍼를 쓴다. 공식 미리보기가 멈추면 `python3 -m http.server` 와 `google-chrome --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --hide-scrollbars --window-size=1920,1080 --virtual-time-budget=8000 --screenshot=... http://127.0.0.1:<port>/<파일>#p1` 로 본다.

### 5. 배포한다
`og_image.py` 로 `https://deck.soverin.cloud/og/<id>.jpg` 를 만들고, `book.json` 의 `og.url`·`og.image` 를 절대 주소로 맞춘 뒤 다시 빌드한다. `/workspace/deck-site/` 에 HTML과 og 그림을 넣고 목록(`index.html`)에 카드를 추가한 다음, 기존 파일을 유지한 채 `/workspace/site.zip` 을 만들어 `python3 /workspace/deploy_deck.py` 로 올린다. 배포는 사이트 전체를 덮어쓰므로 기존 강의안을 빼지 않는다. 올린 뒤 책 URL·OG·목록·기존 책 두 개가 200 인지, 카카오톡 User-Agent 로 og:image 가 보이는지 확인한다.

## 원본에서 바꾼 스케일 규칙
원본 `fit()` 은 `#stage` 를 위 50px·아래 68px 잘라 두고 `stage * 0.96 / 0.97` 로 축소했다. 이 키트는 스테이지를 화면 전체(`inset:0`)로 두고, 지금 보이는 책 너비(한 장 600 또는 펼침 1200)와 높이 820에 맞춰 `scale = min(viewportW / W, viewportH / 820)` 만 쓴다. 쪽의 글자 크기·여백은 600×820 좌표 그대로 두고, 화면에서만 확대한다.
