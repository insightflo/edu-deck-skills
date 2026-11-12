# svg-diagram (벤더 사본)

- 원격 URL: https://github.com/bybit-exchange/svg-diagram.git
- 커밋 해시: c30c9e3bc9a70f2b77b60c7ea27157de3a88d81a
- 트리 해시 (`git rev-parse HEAD:tools/svg-lint`): 130dd53d4d21976c5c046f2f1eeadb2db7525855
- 취득일: 2026-11-01
- 원본 LICENSE: 원천 저장소 루트 `LICENSE` (MIT, Copyright (c) 2026 bybit-exchange). 사본: `LICENSE` (이 디렉터리)

## 복사 범위

- `LICENSE`
- `SKILL.md` → 사본 파일명은 `SKILL.upstream.md` (아래 "로컬 수정" 참조)
- `tools/svg-lint/bin/`, `tools/svg-lint/lib/`, `tools/svg-lint/README.md`

복사 파일 수: 28 (LICENSE 1 + SKILL.upstream.md 1 + tools/svg-lint 26).

## 제외 범위

- `tools/svg-lint/test/` (벤더 테스트·픽스처)
- `gallery/`, `assets/house-style.svg`
- `package.json`
- 루트 `README.md`

제외 사유: 계획 A1 (벤더 범위 최소화). 빌드 시점에 테스트 코드와 갤러리 자산은 필요하지 않다.

## 로컬 수정

유일한 편차: 파일명만 변경한다 — 원천 `SKILL.md` → 사본 `SKILL.upstream.md`. 사유: 슬라이드·문서 엔진의 "진입은 SKILL.md 하나뿐" 불변식(`work/tests/test_suite.py` 의 test_single_skill_entry)과 스킬 로더가 중첩 `SKILL.md` 를 별개 스킬로 오인하는 것을 막기 위함. 내용은 원천과 바이트 동일하다 (`cmp` 로 대조, 무출력 = 동일).

원천 대조 기준: 원천 추출물의 `SKILL.md` ↔ 이 사본의 `SKILL.upstream.md`. 그 밖의 파일은 원천 커밋의 바이트와 동일하다 (`diff -rq` 로 원천 추출물과 대조, 무출력). 원천 저장소 안의 파일명은 `SKILL.md` 그대로다.

## 재현 명령

```
git -C /tmp/svgd archive c30c9e3bc9a70f2b77b60c7ea27157de3a88d81a tools/svg-lint LICENSE SKILL.md | tar -x -C <빈 디렉터리>
# 이후 <빈 디렉터리>/tools/svg-lint/test 삭제
```

원천 저장소는 읽기 전용으로만 접근한다 (`git archive`, `git rev-parse`). 벤더 코드는 실행하지 않고 복사만 한다.

## 사용처

이 사본은 `ko-slide` / `ko-doc` 빌드가 `shared/diagram_lint.py` 를 통해 `tools/svg-lint/bin/svg-lint.mjs` 를 호출하는 데 쓴다.

## 무결성

`SHA256SUMS` (이 디렉터리 기준 상대경로) 로 전 파일을 검증한다: `cd <이 디렉터리> && sha256sum -c SHA256SUMS`.
