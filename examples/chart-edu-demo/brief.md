# 시제품: edu 덱 + 컨설팅 차트 킷 결합 실증

교육 덱(edu-deck legacy·자유 모드)이 consulting-deck/chart_gen.mjs 의 차트 조각을 재료로 쓸 수 있다는 것을 실물로 증명한다.
- 손저작 장(표지·읽기 원리·확인 퀴즈·체크리스트) + chart_gen 생성 장(워터폴·히트맵, class:"consult") 혼합.
- 차트는 교육용 가상 데이터 — source.synthetic:true 로 조각에 "가상 데이터" 표기가 자동으로 새겨진다.
- 생성은 덱 폴더 안에서만: `cd examples/chart-edu-demo && node ../../consulting-deck/charts/chart_gen.mjs --in charts/NN-*.json -o src/NN-*.html`.
- evidence.json 은 두지 않는다(근거 원장 게이트는 컨설팅 목적 전용).
