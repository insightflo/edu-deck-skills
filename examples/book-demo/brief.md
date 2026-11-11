# book-demo · 제작 메모

인사이트북 양식(bookstyle-html)의 실물 예제. 600×820 쪽, 펼침 넘김 단일 HTML 8쪽.

## 대상·목적
- 읽는 사람: 사내에서 AI 에이전트(코드 리뷰·배치·자동화)를 도입·운영하는 개발 조직의 리드와 보안 담당.
- 목적: “권한을 얼마나 줄 것인가”를 도구 선택보다 먼저 정하게 한다. 위험 세 축 → 사례 한 쌍(이야기+근거) → 점검 일곱 항목.

## 사실 경계
- 표준·규정 이름은 실재하는 것만 썼다: OWASP Top 10 for LLM Applications(2025), NIST AI RMF 1.0, ISO/IEC 42001:2023, EU AI Act(Regulation (EU) 2024/1689).
- 사례(5쪽)와 수치(6쪽: 12→2, 0→100%, 3곳)는 **구성 예시**다. 실제 조직·측정값이 아니며 쪽 하단과 5·6쪽 바닥글에 그렇게 적었다.
- 외부 사진·로고·상표를 쓰지 않았다. 6쪽 그림은 도식(SVG)이다.

## 쪽 구성
| 쪽 | data-type | 내용 |
|---|---|---|
| 1 | cover | 제목·부제, 3 위험 축 / 4 통제 계층 / 7 점검 항목 |
| 2 | toc | 목차 5행 + 위험 축 6개 + 세 문장 주장 |
| 3 | article | 왜 지금 문제인가 — 챗봇/에이전트 비교, 위험 4카드, 인용 |
| 4 | divider | PART 01 · 권한 사고 시나리오 |
| 5 | story | 리뷰 에이전트가 12개 저장소를 읽을 수 있었다 (문제→해결, point) |
| 6 | evidence | 전후 개념도(SVG)·승인 지점 비교·KPI·통제 네 계층 |
| 7 | article(t-tint) | 점검표 7항목(.chk) + 선택 점수 |
| 8 | back | 마무리 문장 + 출처·발행 |

## 빌드·검증
```bash
python3 bookstyle-html/scripts/build_book.py examples/book-demo --check
python3 bookstyle-html/scripts/build_book.py examples/book-demo -o examples/book-demo/book-demo.html
python3 bookstyle-html/scripts/preview.py check examples/book-demo/book-demo.html
python3 bookstyle-html/scripts/preview.py shot examples/book-demo/book-demo.html -o <out> --pages 1,2,3,4,5,6,7,8
python3 bookstyle-html/scripts/preview.py view examples/book-demo/book-demo.html -o <out>/view.png
python3 bookstyle-html/scripts/og_image.py examples/book-demo/book-demo.html -o <out>/og.jpg
```
`book.json` 의 `og.url`·`og.image` 는 배포 주소가 정해질 때 채운다(지금은 비어 있어 OG 태그에 제목·설명만 들어간다).
