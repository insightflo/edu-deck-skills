# PPT 경로 시각 자산 브리지 (ppt-visual-bridge)

> **소유**: PPT(PPTX) 요청이 ppt-master 스킬로 넘어갈 때, 이 저장소의 시각 자산(차트·도식·아이콘·스타일)이
> 실제로 결과물에 들어가게 하는 연결 계약. ppt-master 본체는 무수정 사본이라 이 문서를 모른다 —
> **에이전트가 이 문서를 읽고 자재를 만들어 가져간다.**
> **왜**: brandme 세션(2026-11-13) — PPT 1~2차는 템플릿 기본값만 써서 "없어 보인다"는 사용자 평가를 받았고,
> 3차에서 도식·차트 자산을 수작업으로 넣고 나서야 만족했다. 자산은 충분하다; 연결이 없었을 뿐.

## 원칙

1. **템플릿 기본값에 안주하지 않는다.** ppt-master 자체 템플릿만 쓴 PPT는 이 저장소의 기대치 미달이다.
   표지·대표 장(핵심 메시지 장)은 아래 자산으로 차별화한다.
2. **편집 가능성 vs 정교함**: 나중에 손으로 고칠 도형·단순 차트는 ppt-master 네이티브(도형·데이터 차트)로,
   정교한 컨설팅 차트·아키텍처 도식은 우리 생성기로 만들어 PNG 로 삽입한다.
3. **대표 샘플 승인 전에 시각 자산이 실물로 들어가 있어야 한다.** 승인 받는 샘플(표지+핵심 1~2장)이
   이미 자산을 쓰고 있어야 전체 제작도 그대로 이어받는다.

## 자산 → PPT 결합 경로

### 1. 컨설팅 차트 15종 — `consulting-deck/charts/chart_gen.mjs`
waterfall·diverging-bar·heatmap·matrix-2x2·tornado·sankey·pareto·bullet·dumbbell·slope·waffle 등.
```bash
node consulting-deck/charts/chart_gen.mjs --in MODEL.json --svg-only > chart.svg
python3 edu-deck/shared/scripts/svg2png.py chart.svg chart.png --width 1200 \
  --css consulting-deck/assets/consult.css --scope "slide consult"
```
의미 모델 스키마: `consulting-deck/charts/schema.md`·예제 `charts/examples/*.json`.
방향(4종: consult·dense·editorial·tech)에 따라 `--scope "slide consult-tech"` 등으로 갈아끼운다.

### 2. 아키텍처 도식 — `edu-deck/shared/scripts/arch_layout.mjs`·`iso_layout.mjs`
시맨틱 JSON → SVG(레이어·중첩 존·버스·HA 쌍·아이소). 저작 계약: `references/architecture.md`.
```bash
python3 edu-deck/shared/scripts/svg2png.py arch.svg arch.png --width 1600 \
  --css edu-deck/shared/assets/css/tokens.css \
  --css edu-deck/shared/assets/css/components.css --scope "slide"
```

### 3. 덱 도식 계열에서 발췌 — `edu-deck/shared/assets/snippets/`
이미 만든 HTML 덱의 장(`src/*.html`)에서 `<svg class="dg">`를 그대로 떼어 변환한다(52계열 재사용).
CSS 는 그 덱이 쓰던 tokens/components/sheets 와 같은 조합으로 준다(위와 동일 형식).

### 4. 아이콘 — lucide(`scripts/fetch_lucide.py` 산출물)·SI 장비 `assets/icons/si.svg`
currentColor 로 그리므로 색은 주입 CSS 로 지정한다(예: 임시 파일 `icon.css`에 `#wrap{color:#111822}` 한 줄).
```bash
python3 edu-deck/shared/scripts/svg2png.py icon.svg icon.png --scale 2 --css icon.css
```

### 5. 스타일 파레트 — `edu-deck/shared/assets/style-sheets/` 12종 + `presets/` 16종
색·서체·밀도 성격을 읽어 ppt-master 슬라이드 마스터의 색·글꼴·도형 반경에 옮긴다(한 덱 한 스타일).
PNG 로 내보내는 게 아니라 값 참조용이다.

## svg2png 규약

- `--width N`(권장 — viewBox 비율로 배율 자동) 또는 `--scale`(기본 2).
- 배경: 기본 투명. 종이 위 얹을 그림이면 `--bg '#F7F4EE'` 등.
- 덱 문맥 CSS 변수(`var(--ink)` 등)는 `--css`(토큰 파일)+`--scope`(스코프 클래스)로 해결한다.
  컨설팅 자산은 `--scope "slide consult"`, edu-deck 계열은 `--scope "slide"`.
- 덱 안(HTML)에서는 이 도구를 쓰지 않는다 — SVG 인라인이 계약이다. 이 도구는 덱 밖 반출 전용.
