# 실행 안내

## 1. 작업 경로

가족형 ZIP은 압축 해제 폴더, 단일 루트 ZIP은 `edu-deck/bundle/`로 이동한 상태를 아래 명령의 기준으로 삼습니다. `python3`는 해당 환경의 Python 3 실행 명령으로 바꿀 수 있습니다. 공백이 있는 경로는 따옴표로 감쌉니다. 자동 스킬 등록 없이도 에이전트에게 원본 `edu-deck/SKILL.md`를 읽게 할 수 있습니다.

```sh
python3 edu-deck/shared/scripts/env_check.py
```

이 명령은 네트워크 접속을 시도하며 종료 코드가 항상 0입니다. 각 항목의 결과를 읽으세요. 실제 화면 검사 가능 여부는 최종 검사기의 브라우저 실행으로 판단합니다.

## 2. 의존성

- **초기화·조립**: Python 3와 ZIP 내부 파일. Python 3.11에서 확인했습니다.
- **전체 HTML 검사**: `beautifulsoup4`(모듈 `bs4`), `lxml`, `Pillow`(모듈 `PIL`), `playwright`, 실제 실행 가능한 Chromium 또는 Chrome.
- **출처 확인**: 자료·네트워크 접근. PDF는 `pypdf` 또는 `pdftotext` 등 원본 스킬이 허용하는 경로.

설치가 필요하면 먼저 승인을 받으세요. 승인 후 격리 환경에서 사용할 수 있는 일반적인 명령 예시는 다음과 같습니다. 이 명령을 이미 실행했다고 간주하지 마세요. 브라우저 설치는 다운로드·디스크 사용이 발생하며 OS 라이브러리 또는 관리자의 도움이 필요할 수 있습니다.

```sh
python3 -m pip install beautifulsoup4 lxml Pillow playwright
python3 -m playwright install chromium
```

네트워크·설치가 제한된 환경에서는 실행할 수 있는 단계만 수행하고 나머지를 미실행으로 보고합니다. Python 실행만 가능하면 조립은 할 수 있어도 화면 검사는 못 할 수 있습니다.

## 3. 단일 덱

먼저 `edu-deck-solo/SKILL.md`의 요청 정리·조사·구성 절차를 따르고, 사용자가 요청하면 구성안을 승인받습니다. 아래는 명령 형태의 예시이며 교육 내용을 자동으로 완성하는 명령이 아닙니다. 새 작업 폴더를 사용하세요.

새 덱의 기본은 legacy 아키타입 경로입니다. `deck.json`에 `title`·`output`만 쓰고, `shared/assets/snippets/`와 `shared/references/layouts.md`를 참고해 `src/NN-이름.html`을 직접 작성합니다.

사용자가 리소스팩을 요청하거나 시안에서 골라 팩 경로로 갈 때만 아래 init으로 뼈대를 만듭니다.

```sh
python3 edu-deck/shared/scripts/resource_packs.py init ./my-deck --design editorial --flow problem --title "교육 제목"
```

생성된 `deck.json`과 `src/`를 실제 조사 내용으로 작성합니다. legacy 경로도 `deck.json`을 쓴 뒤부터는 같습니다. 제목·본문·도식·발표자 노트·평가 문제 등 원본 스킬의 기준을 충족해야 합니다. 초기 뼈대만 조립해 완성본으로 전달하지 마세요.

```sh
python3 edu-deck/shared/scripts/build_deck.py ./my-deck
python3 edu-deck/shared/scripts/check_deck.py ./my-deck/deck.html --json ./my-deck/check.json
```

결과 파일명은 `deck.json` 설정과 조립기 출력으로 확인하고, 다르면 검사 명령의 경로를 그 파일로 바꿉니다. 출처 검사·전체 화면/상호작용 점검 등 원본 스킬이 요구하는 나머지 검사도 수행합니다. `--no-render`는 전체 화면 검증을 대체하지 않습니다.

## 4. 시리즈

`edu-deck-series/SKILL.md`와 연결된 참조를 읽어 `series.json`과 편별 폴더를 작성하고 각 편을 검사합니다. 임의의 manifest 구조를 추측하지 마세요. 준비된 시리즈 작업 폴더를 조립합니다.

```sh
python3 edu-deck-series/scripts/build_series.py ./my-series --hub map --out ./my-series/portal.html
python3 edu-deck-series/scripts/check_series.py ./my-series/portal.html
```

`map`, `shelf`, `list` 목차를 지원합니다. 필수 포털 템플릿은 `edu-deck-series/dev/portal_template.html`에 포함됩니다. 개발 도구가 아니라 조립에 필요한 런타임 입력이므로 지우지 마세요.

## 5. 결과 전달

생성 HTML, 실제 검사 결과, 출처 확인 상태, 미실행 항목을 구분해 전달합니다. 첨부 ZIP을 읽을 수 없거나 Python이 없으면 초안·실행 안내까지만 제공하세요. 브라우저 검사가 막혔으면 HTML을 전달하더라도 **화면 검증 미완료**라고 밝혀야 합니다. 서비스 업로드·설치·외부 발행은 별도 승인 대상입니다.
