> **로드 시점**: 슬라이드에 아이콘을 넣을 때 (주제에 맞는 아이콘 id 찾기)

# 아이콘 목록

```html
<svg class="ico" aria-hidden="true"><use href="#i-hardhat"/></svg>          <!-- 56px 주황 -->
<svg class="ico" aria-hidden="true" style="color:var(--blue)"><use href="#i-info"/></svg>
<svg viewBox="0 0 100 100" width="80" height="80" aria-hidden="true"><use href="#i-sun" width="100" height="100"/></svg>
```

- 크기는 CSS width/height, 색은 `color` (모두 currentColor 선 아이콘, viewBox 0 0 100 100).
- 장식이므로 `aria-hidden="true"`. 뜻은 옆 글자로 전한다.
- 도식 화살촉 marker: `marker-end="url(#ah)"` 주황 · `#ahb` 파랑 · `#ahg` 회색 · `#ahk` 먹색 · `#ah-o` 주황 · `#ah-b` 파랑 · `#ah-n` 먹색.

| id | 그림 | 어울리는 뜻·검색어 |
|---|---|---|
| i-person | 사람 한 명 | 사람, 담당자, 직원, 고객, 나 |
| i-people | 두 사람 | 팀, 동료, 협력사, 청중, 함께 |
| i-robot | 로봇 얼굴 | 에이전트, 프로그램, 자동 실행자(사람과 구분) |
| i-org | 조직도 | 조직, 부서, 보고 체계, 결재선, 계층 |
| i-chat | 말풍선 | 대화, 질문, 메신저, 상담, 의견 |
| i-qbubble | 점선 물음 말풍선 | 다시 물어보기, 문의, 모르는 것, 확인 질문 |
| i-mail | 봉투 | 메일, 안내문 발송, 공지, 통지 |
| i-phone | 휴대전화 | 전화, 문자, 앱, 연락, 비상 연락 |
| i-megaphone | 확성기 | 공지, 알림, 홍보, 전파, 경보 |
| i-bell | 종 | 알림, 경보, 리마인더, 호출 |
| i-send | 종이비행기 | 보내기, 제출, 전송, 신고 |
| i-file | 문서 | 문서, 보고서, 공문, 자료 |
| i-doc-check | 체크 문서 | 승인 문서, 점검 완료, 확인서, 준수 |
| i-clipboard | 클립보드 | 점검표, 체크리스트, 업무 일지, 기록 |
| i-pdf | PDF 문서 | PDF, 지침서, 가이드북, 매뉴얼 |
| i-book | 펼친 책 | 지침, 규정집, 교육, 학습, 요령 |
| i-work | 톱니 문서 | 작업 지시, 처리, 자동 처리, 업무 |
| i-sheet | 표 | 엑셀, 표, 대장, 목록 정리 |
| i-list | 목록 | 목록, 항목, 순서, 목차 |
| i-chart | 막대그래프 | 통계, 실적, 비교, 수치 |
| i-trend | 오르는 선 | 증가, 추세, 개선, 성장 |
| i-slide | 화면 그래프 | 발표, 보고, 대시보드, 모니터 |
| i-folder | 폴더 | 자료 모음, 보관, 파일 서버, 문서함 |
| i-db | 원통 | 데이터베이스, 저장소, 기록 보관 |
| i-cal | 달력 | 일정, 날짜, 기한, 시행일 |
| i-cutoff | 달력 경계선 | 기준일, 마감, 기한 경과 |
| i-clock | 자명종 | 시간, 휴식 시간, 마감, 근무 시간 |
| i-stamp | 도장 | 결재, 승인, 날인, 확정 |
| i-signature | 서명 | 서명, 동의, 계약, 확인 |
| i-id-card | 신분증 | 신원, 출입증, 자격, 개인정보 |
| i-check | 동그라미 체크 | 완료, 정답, 확인, 준수 |
| i-x | 동그라미 엑스 | 오답, 금지, 실패, 취소 |
| i-ban | 금지 표시 | 금지, 사용 불가, 차단, 하지 말 것 |
| i-stop | 정지 팔각형 | 작업 중지, 멈춤, 중단 |
| i-warn | 경고 삼각형 | 주의, 위험, 경고, 사고 |
| i-info | 동그라미 i | 안내, 정보, 참고, 도움말 |
| i-question | 동그라미 물음 | 질문, 퀴즈, 모름, 궁금증 |
| i-shield | 체크 방패 | 보호, 보안, 안전, 예방 |
| i-lock | 자물쇠 | 잠금, 비밀번호, 접근 제한, 보안 |
| i-key | 열쇠 | 권한, 열쇠, 인증, 접근 |
| i-eye | 눈 | 보기, 감시, 확인, 관찰, 열람 |
| i-search | 돋보기 | 찾기, 검색, 조사, 점검 |
| i-gear | 톱니바퀴 | 설정, 장비, 시스템, 작동 원리 |
| i-tool | 렌치 | 정비, 수리, 공구, 조치 |
| i-ladder | 사다리 | 고소 작업, 사다리, 높은 곳 |
| i-hardhat | 안전모 | 안전, 현장, 건설, 보호구 |
| i-fire | 불꽃 | 화재, 열, 위험물, 긴급 |
| i-thermo | 온도계 | 온도, 체감온도, 폭염, 한파, 체온 |
| i-sun | 해 | 폭염, 햇볕, 낮, 야외 |
| i-water | 물방울 | 물, 수분 보충, 음료, 누수 |
| i-medical | 십자 | 응급, 의료, 보건, 구급함 |
| i-heart | 하트 | 건강, 생명, 배려, 복지 |
| i-hand | 손바닥 | 멈춤, 손 들기, 직접, 수작업 |
| i-bulb | 전구 | 아이디어, 핵심, 요령, 깨달음, 개념 |
| i-target | 과녁 | 목표, 정확, 겨냥, 핵심 |
| i-flag | 깃발 | 시작, 이정표, 목표 지점, 표시 |
| i-trophy | 트로피 | 성과, 우수 사례, 달성 |
| i-star | 별 | 중요, 추천, 즐겨찾기, 평가 |
| i-coin | 동전 | 비용, 돈, 요금, 예산 |
| i-money | 지폐 | 현금, 지급, 매출, 과태료 |
| i-calc | 계산기 | 계산, 검산, 합계, 세금 |
| i-scale | 저울 | 법, 공정, 판단, 균형, 비교 |
| i-building | 건물 | 회사, 기관, 본사, 사무실 |
| i-factory | 공장 | 공장, 제조, 생산, 사업장 |
| i-home | 집 | 집, 처음, 재택, 가정 |
| i-truck | 트럭 | 운송, 배송, 물류, 자재 반입 |
| i-car | 자동차 | 차량, 운전, 출장, 교통 |
| i-globe | 지구 | 세계, 인터넷, 해외, 공개 |
| i-link | 고리 | 연결, 링크, 연동, 관계 |
| i-plug | 플러그 | 연결, 전원, 연동, 붙이기 |
| i-cloud | 구름 | 클라우드, 온라인 저장, 날씨 |
| i-leaf | 잎 | 환경, 친환경, 자연, 성장 |
| i-camera | 카메라 | 사진, 기록, 증거, 촬영 |
| i-pin | 위치 핀 | 장소, 위치, 현장, 지도 |
| i-pencil | 연필 | 쓰기, 작성, 수정, 입력 |
| i-refresh | 순환 화살표 | 반복, 갱신, 다시 하기, 주기 |
| i-trash | 휴지통 | 삭제, 폐기, 파기, 정리 |
| i-graduation | 학사모 | 교육, 학습, 수료, 자격 |
| i-bolt | 번개 | 빠름, 전기, 즉시, 위험 전압 |
| i-wand | 요술봉 | 자동, 손쉬운 변환, 마법 같은 기능 |
| i-branch | 갈래 | 분기, 선택지, 경우의 수, 흐름 |
| i-window | 창 | 화면, 창, 한 번에 보이는 범위 |
| i-dice | 주사위 | 확률, 우연, 무작위, 매번 다름 |
| i-memory | 머리와 점 | 기억, 생각, 학습, 판단 |
| i-nn | 신경망 | 인공지능, 연결망, 모델 (AI 주제에만) |

## 주제 전용 아이콘 추가

- 덱 폴더 `src/icons.svg` 에 `<symbol id="i-이름" viewBox="0 0 100 100">…</symbol>` 를 넣으면 조립 때 합쳐진다.
- 같은 문법: `fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"`, 가장자리 여백 8~12, 작은 채움은 `fill="currentColor"`.
- 기존 id 와 겹치면 조립이 멈춘다. 이모지·외부 이미지로 대신하지 않는다.

## 손그림 IT 아이콘(Koboyo, 선택)

- 언제: IT·개발·데이터·보안 주제의 설명 도식·카드에서 손그림 느낌이 주제와 맞을 때. 기본 선 아이콘(`i-…`)과 한 장에 섞지 않는다.
- 라이브러리 원본(사용자가 내려받은 koboyo_gallery.html)은 스킬 폴더·배포물에 절대 넣지 않는다. 헬퍼가 외부 경로에서 읽어 덱에 쓰는 아이콘만 `src/koboyo-icons.svg` 로 심볼 단위 복사한다(id 접두사 `kb-`).
- 갤러리 경로: `--lib PATH` > 환경변수 `EDU_DECK_KOBOYO_LIB` > `~/Downloads/koboyo_gallery.html`. 파일이 없으면 종료 코드 2.

```bash
python3 scripts/koboyo_icons.py search 'api endpoint' --limit 10   # slug·그룹·제목 출력
python3 scripts/koboyo_icons.py search 'token' --group security
python3 scripts/koboyo_icons.py add <덱 폴더> api-endpoint sql-file  # 덱 src/koboyo-icons.svg 에 추가
python3 scripts/koboyo_icons.py list <덱 폴더>                     # 들어간 심볼 확인
```

- 슬라이드에서는 `<svg class="ico" aria-hidden="true"><use href="#kb-slug"/></svg>`. 색은 `color`(currentColor)를 따르고, 크기는 `.ico` 규칙을 따른다. viewBox가 정사각형이 아니어도 가로세로비를 유지한 채 들어맞춤된다.
- 덱 하나에 심볼 40개 상한. 없는 slug 는 비슷한 후보 5개를 보여 주고 멈춘다.
- 라이선스(koboyo.com/icons): 문서·프레젠테이션·다이어그램에서 개인·상업적 사용 가능, 재색칠·수정 가능, 출처 표기 불필요. 금지: 라이브러리 전체(또는 상당 부분)를 컬렉션으로 재배포, 아이콘을 골라 담거나 추출·내려받게 하는 앱·도구에 번들.
