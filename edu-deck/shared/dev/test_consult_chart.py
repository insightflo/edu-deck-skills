"""Acceptance: chart_gen.mjs — 컨설팅 차트 생성기(waterfall · ranked-bar-h · diverging-bar).

[검사 항목]
- 결정성: 같은 모델 → 같은 바이트(2회 실행). 레이아웃·정렬에 시간·난수·로캘이 없다는 증거.
- 계산 가드: waterfall 시작+증감 합계가 calc.expectTotal 과 다르면 exit 1 — 수치-주장
  불일치를 사람 검토가 아니라 생성 시점에 막는다(이 스킬의 핵심 안전 장치).
- 출처 계약: source.text·synthetic 누락은 exit 1. synthetic:true 면 "가상 데이터"가
  출처 블록에 강제로 새겨진다.
- 주석·강조 계약: main 2개 이상·sub 3개 이상, highlight/on 이 data 에 없는 label 은 exit 1.
- 산출 조각: script·SMIL·CSS 애니메이션 0 · data-step 존재 · k-* 클래스/var(--…)만 ·
  출처 블록 항상 존재 · 모션은 엔진 속성(data-step/.wf/data-fx/data-count)뿐.

[실행] cd edu-deck/shared && python3 -m unittest dev.test_consult_chart -v
[주의] node 18+ 가 PATH 에 있어야 한다(없으면 skip). 저장소에는 아무것도 쓰지 않는다(임시 폴더 사용).
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

S = Path(__file__).resolve().parents[1]      # edu-deck/shared
ROOT = S.parents[1]                          # 저장소 루트
GEN = ROOT / 'consulting-deck' / 'charts' / 'chart_gen.mjs'
EX = ROOT / 'consulting-deck' / 'charts' / 'examples'
WF = EX / 'wf-it-cost.json'
RB = EX / 'rb-ai-gap.json'
DB = EX / 'db-cost-yoy.json'
ST = EX / 'st-cost-mix.json'
LN = EX / 'ln-margin-trend.json'
SC = EX / 'sc-practice.json'
HM = EX / 'hm-usage.json'
MX = EX / 'mx-portfolio.json'
TN = EX / 'tn-sensitivity.json'
SK = EX / 'sk-budget.json'
PA = EX / 'pa-defect.json'
P3A = [ST, LN, SC, HM, MX, TN, SK, PA]
NODE = shutil.which('node')


def run(model_path, out=None, extra=()):
    """생성기 실행 — (returncode, stdout+stderr). out 이 있으면 그 파일에 쓴다."""
    cmd = [NODE, str(GEN), '--in', str(model_path)]
    if out:
        cmd += ['-o', str(out)]
    cmd += list(extra)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return p.returncode, (p.stdout + p.stderr)


@unittest.skipUnless(NODE, 'node 없음')
class ConsultChartTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='edudeck-cchart-'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _mutate(self, src, fn, name):
        model = json.loads(Path(src).read_text(encoding='utf-8'))
        fn(model)
        p = self.tmp / name
        p.write_text(json.dumps(model, ensure_ascii=False), encoding='utf-8')
        return p

    # ── 결정성 ──────────────────────────────────────────────────────
    def test_three_types_deterministic(self):
        for src in (WF, RB, DB):
            a, b = self.tmp / (src.stem + 'a.html'), self.tmp / (src.stem + 'b.html')
            for f in (a, b):
                code, log = run(src, f)
                self.assertEqual(code, 0, log)
            self.assertEqual(a.read_bytes(), b.read_bytes(), f'{src.name}: 두 실행 결과가 다르다')

    # ── 계산 가드 ───────────────────────────────────────────────────
    def test_waterfall_sum_mismatch_rejected(self):
        def bad(m):
            m['chart']['calc']['expectTotal'] = 900
        p = self._mutate(WF, bad, 'sum.json')
        code, log = run(p, self.tmp / 'sum.html')
        self.assertEqual(code, 1)
        self.assertIn('합계 불일치', log)
        self.assertIn('expectTotal', log)

    def test_waterfall_total_value_mismatch_rejected(self):
        def bad(m):
            m['chart']['data'][-1]['value'] = 880
        p = self._mutate(WF, bad, 'tot.json')
        code, log = run(p, self.tmp / 'tot.html')
        self.assertEqual(code, 1)
        self.assertIn('누적', log)

    # ── 출처 계약 ───────────────────────────────────────────────────
    def test_missing_source_rejected(self):
        def bad(m):
            del m['source']
        p = self._mutate(RB, bad, 'nosrc.json')
        code, log = run(p, self.tmp / 'nosrc.html')
        self.assertEqual(code, 1)
        self.assertIn('source.text', log)

    def test_missing_synthetic_rejected(self):
        def bad(m):
            del m['source']['synthetic']
        p = self._mutate(RB, bad, 'nosyn.json')
        code, log = run(p, self.tmp / 'nosyn.html')
        self.assertEqual(code, 1)
        self.assertIn('synthetic', log)

    def test_synthetic_flag_forces_marker(self):
        out = self.tmp / 'wf.html'
        code, log = run(WF, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('가상 데이터', html)
        self.assertIn('Source:', html)
        # synthetic:false 는 표기 없이 통과해야 한다
        p = self._mutate(WF, lambda m: m['source'].__setitem__('synthetic', False), 'real.json')
        out2 = self.tmp / 'real.html'
        code, log = run(p, out2)
        self.assertEqual(code, 0, log)
        self.assertNotIn('가상 데이터', out2.read_text(encoding='utf-8'))

    # ── 주석·강조 계약 ──────────────────────────────────────────────
    def test_annotation_overflow_rejected(self):
        def bad(m):
            m['chart']['annotations'].append({'label': '둘째 핵심', 'on': '툴 통합', 'kind': 'main'})
        p = self._mutate(WF, bad, 'ann.json')
        code, log = run(p, self.tmp / 'ann.html')
        self.assertEqual(code, 1)
        self.assertIn('annotations 초과', log)

    def test_annotation_unknown_target_rejected(self):
        def bad(m):
            m['chart']['annotations'][0]['on'] = '없는항목'
        p = self._mutate(WF, bad, 'annon.json')
        code, log = run(p, self.tmp / 'annon.html')
        self.assertEqual(code, 1)
        self.assertIn('없는항목', log)

    def test_highlight_unknown_label_rejected(self):
        def bad(m):
            m['chart']['highlight'].append('없는항목')
        p = self._mutate(RB, bad, 'hl.json')
        code, log = run(p, self.tmp / 'hl.html')
        self.assertEqual(code, 1)
        self.assertIn('없는항목', log)

    # ── 스키마 필수·범위 ────────────────────────────────────────────
    def test_missing_question_rejected(self):
        def bad(m):
            del m['chart']['question']
        p = self._mutate(RB, bad, 'noq.json')
        code, log = run(p, self.tmp / 'noq.html')
        self.assertEqual(code, 1)
        self.assertIn('question', log)

    def test_data_count_out_of_range_rejected(self):
        def bad(m):
            m['chart']['data'] = m['chart']['data'][:2]
        p = self._mutate(RB, bad, 'few.json')
        code, log = run(p, self.tmp / 'few.html')
        self.assertEqual(code, 1)
        self.assertIn('범위', log)

    def test_ranked_negative_rejected(self):
        def bad(m):
            m['chart']['data'][0]['value'] = -3
        p = self._mutate(RB, bad, 'neg.json')
        code, log = run(p, self.tmp / 'neg.html')
        self.assertEqual(code, 1)
        self.assertIn('diverging-bar', log)

    # ── 산출 조각 계약 ──────────────────────────────────────────────
    def test_fragment_contract(self):
        for src in (WF, RB, DB):
            out = self.tmp / (src.stem + '-frag.html')
            code, log = run(src, out)
            self.assertEqual(code, 0, log)
            html = out.read_text(encoding='utf-8')
            for bad in ('<script', '<animate', '@keyframes', 'requestAnimationFrame', 'http://', 'https://'):
                self.assertNotIn(bad, html, f'{src.name}: {bad} 발견')
            self.assertIn('data-step=', html, f'{src.name}: data-step 없음')
            self.assertIn('<aside class="notes">', html)
            self.assertIn('class="dg"', html)
            self.assertIn('Source:', html, f'{src.name}: 출처 블록 없음')
            self.assertIn('class="c-src"', html, f'{src.name}: c-src 출처 블록 없음')
            self.assertNotIn('<p class="small"', html, f'{src.name}: 구형 p.small 출처 블록 잔존')
            # 색은 토큰만 — hex 색 코드 금지
            self.assertIsNone(re.search(r'#[0-9a-fA-F]{3,8}\b', html), f'{src.name}: hex 색 발견')
            # 모션은 엔진 속성뿐
            attrs = set(re.findall(r'\bdata-[a-z-]+', html))
            self.assertTrue(attrs <= {'data-archetype', 'data-variant', 'data-step', 'data-fx', 'data-count'},
                            f'{src.name}: 예상 밖 속성 {attrs}')

    # ── 타입별 형태 ─────────────────────────────────────────────────
    def test_waterfall_structure(self):
        out = self.tmp / 'wf-struct.html'
        code, log = run(WF, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('data-archetype="waterfall"', html)
        self.assertEqual(html.count('class="wf"'), 6, '항목 수만큼 .wf 단계 그룹')
        self.assertIn('data-count', html, '최종 합계는 count-up')
        self.assertIn('k-solid-n', html, 'total 막대는 k-solid-n')
        self.assertIn('−140', html, '증감 라벨은 부호 포함')
        self.assertIn('「핵심」', html, 'main 주석 표식')

    def test_ranked_sorted_and_highlight(self):
        out = self.tmp / 'rb-struct.html'
        code, log = run(RB, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('data-variant="ranked"', html)
        # 값 내림차순 — 첫 단계 그룹의 항목이 최대값 62
        first = re.search(r'<g data-step="1">.*?</g>', html, re.S).group(0)
        self.assertIn('업무 재설계 병행', first)
        self.assertIn('>62<', first)
        self.assertIn('var(--accent)', first, 'highlight 는 초점색')
        self.assertIn('data-fx="bar-grow"', html)

    def test_diverging_directions(self):
        out = self.tmp / 'db-struct.html'
        code, log = run(DB, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('data-variant="diverging"', html)
        self.assertIn('transform-origin:left center', html, '양수 막대는 왼쪽 고정 성장')
        self.assertIn('transform-origin:right center', html, '음수 막대는 오른쪽(0축) 고정 성장')
        self.assertIn('+11.8', html)
        self.assertIn('−5.4', html)

    # ── 축 생략(axis break) ─────────────────────────────────────────
    def test_axis_break_auto(self):
        # base(1240) 가 max 의 100% ≥60% — 자동 축 생략으로 증감 막대가 전부 18px 이상
        out = self.tmp / 'wf-brk.html'
        code, log = run(WF, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        # 증감 막대 = 파랑/초점색/회색 fill(base·total 의 k-solid-n 제외)
        delta_heights = [float(h) for h, attrs in
                         re.findall(r'<rect[^>]*height="([\d.]+)"([^>]*)>', html)
                         if 'k-solid-b' in attrs or 'var(--accent)' in attrs or 'var(--muted)' in attrs]
        self.assertEqual(len(delta_heights), 4)
        self.assertTrue(all(h >= 18 for h in delta_heights),
                        f'증감 막대 {delta_heights} — 축 생략 후에도 18px 미만')
        self.assertEqual(html.count('class="axis-brk"'), 2, 'base·total 막대에 축 생략 마크 2쌍')

    def test_axis_break_explicit(self):
        # axisBreak=800 명시 — sc=360/440 → -140 막대는 114.55px
        p = self._mutate(WF, lambda m: m['chart']['measure'].__setitem__('axisBreak', 800), 'brk800.json')
        out = self.tmp / 'brk800.html'
        code, log = run(p, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('height="114.55"', html, 'axisBreak 명시 스케일 미적용')
        # 범위 밖 명시(≥최소누적)는 무시+경고
        p2 = self._mutate(WF, lambda m: m['chart']['measure'].__setitem__('axisBreak', 5000), 'brkX.json')
        code, log = run(p2, self.tmp / 'brkX.html')
        self.assertEqual(code, 0, log)

    def test_axis_break_min_bar_floor(self):
        # 생략 활성 시 작은 증감 막대도 18px 가시 하한 — 상단 누적 위치는 실값 유지
        # (-15억 막대는 스케일상 13px — 클램프가 없으면 실패해야 한다)
        def mk(m):
            m['chart']['measure']['axisBreak'] = 830
            m['chart']['data'].insert(4, {'label': '사무용 소액', 'value': -15, 'kind': 'delta'})
            m['chart']['calc']['expectTotal'] = 875
            m['chart']['data'][-1]['value'] = 875
        p = self._mutate(WF, mk, 'brk830.json')
        out = self.tmp / 'brk830.html'
        code, log = run(p, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        hs = [float(h) for h in __import__('re').findall(r'height="([0-9.]+)"', html)]
        self.assertTrue(all(h >= 18 for h in hs), f'18px 미만 막대: {hs}')

    # ── 막대 역할별 색 분리 ─────────────────────────────────────────
    def test_role_colors(self):
        out = self.tmp / 'wf-col.html'
        code, log = run(WF, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertGreaterEqual(html.count('class="k-solid-n"'), 2, 'base·total 은 잉크(k-solid-n)')
        self.assertIn('class="k-solid-b"', html, '일반 증감은 파랑(k-solid-b)')
        self.assertIn('fill="var(--accent)"', html, 'highlight 증감은 초점색')
        self.assertRegex(html, r'fill="var\(--muted\)" stroke="var\(--soft\)"', 'oneoff 증감은 회색+테두리')

    # ── 단위·출처 마크업 ────────────────────────────────────────────
    def test_unit_label_all_types(self):
        for src in (WF, RB, DB):
            out = self.tmp / (src.stem + '-unit.html')
            code, log = run(src, out)
            self.assertEqual(code, 0, log)
            self.assertIn('(단위:', out.read_text(encoding='utf-8'), f'{src.name}: 단위 표기 없음')

    def test_source_block_markup(self):
        out = self.tmp / 'wf-src.html'
        code, log = run(WF, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('<p class="c-note" data-step="6"><b>방법론·한계</b>', html)
        self.assertIn('<div class="c-src" data-step="6">', html)
        self.assertIn('<p class="s-syn">가상 데이터</p>', html)
        # synthetic:false → s-syn 없음 · note 없으면 c-note 없음
        def real(m):
            m['source']['synthetic'] = False
            del m['source']['note']
        p = self._mutate(WF, real, 'real2.json')
        out2 = self.tmp / 'real2.html'
        code, log = run(p, out2)
        self.assertEqual(code, 0, log)
        h2 = out2.read_text(encoding='utf-8')
        self.assertNotIn('s-syn', h2)
        self.assertNotIn('c-note', h2)
        self.assertIn('c-src', h2)

    # ── 주석 위치(겹침 없음) ────────────────────────────────────────
    def test_annotations_clear_of_axis_labels(self):
        out = self.tmp / 'wf-ann.html'
        code, log = run(WF, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        # waterfall: 항목 라벨 y=508 — 주석 라인은 ±10px 안에 들어오면 안 된다
        ann_ys = [float(y) for y in re.findall(r'<text x="[\d.]+" y="([\d.]+)"[^>]*>「', html)]
        self.assertTrue(ann_ys, 'waterfall 주석 없음')
        for y in ann_ys:
            self.assertFalse(498 < y < 518, f'주석 y={y} 가 항목 라벨(508)과 겹침')
        # 리더선 — 주석마다 점선 var(--accent) 세로선
        self.assertGreaterEqual(html.count('stroke="var(--accent)" stroke-width="2"'), len(ann_ys) - 1)

    def test_ranked_mixed_annotations(self):
        # rb 예시: main 은 인라인 불가 → 막대 아래(행 가산), sub 2개는 수치 뒤 인라인
        out = self.tmp / 'rb-ann.html'
        code, log = run(RB, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('「핵심」 재설계 유무가 성과를 7배 가른다', html)   # 아래 배치는 원문 유지(넓은 폭)
        self.assertIn('「참고」 목표 연동 시 전환율 2배', html)
        # 주석 y 가 다른 항목 라벨 y 와 겹치지 않는지 — 그룹별 비교
        groups = re.findall(r'<g data-step="\d+">(.*?)</g>', html, re.S)
        name_ys = []
        ann_positions = []   # (자기 그룹 name_y, 주석 y)
        for g in groups:
            ny2 = re.search(r'<text x="300" y="([\d.]+)"', g)
            name_y = float(ny2.group(1)) if ny2 else None
            if name_y is not None:
                name_ys.append(name_y)
            for ay in re.findall(r'<text[^>]*y="([\d.]+)"[^>]*>「', g):
                ann_positions.append((name_y, float(ay)))
        for name_y, ay in ann_positions:
            others = {y for y in name_ys if y != name_y}
            for y in others:
                self.assertNotAlmostEqual(ay, y, delta=10,
                                          msg=f'주석 y={ay} 가 다른 항목 라벨 y={y} 와 겹침')

    # ── Phase 3a: 8타입 공통 계약 ───────────────────────────────────
    def test_p3a_eight_types_deterministic(self):
        for src in P3A:
            o1, o2 = self.tmp / (src.stem + 'a.html'), self.tmp / (src.stem + 'b.html')
            code, log = run(src, o1)
            self.assertEqual(code, 0, f'{src.name}: {log}')
            code, log = run(src, o2)
            self.assertEqual(code, 0, f'{src.name}: {log}')
            self.assertEqual(o1.read_bytes(), o2.read_bytes(), f'{src.name}: 비결정적 출력')
            html = o1.read_text(encoding='utf-8')
            for bad in ('<script', '<animate', '@keyframes', 'requestAnimationFrame'):
                self.assertNotIn(bad, html, f'{src.name}: {bad}')
            self.assertIn('data-step=', html, f'{src.name}: data-step 없음')
            self.assertIn('class="c-src"', html, f'{src.name}: 출처 블록 없음')
            self.assertIn('(단위:', html, f'{src.name}: 단위 표기 없음')
            self.assertIsNone(re.search(r'#[0-9a-fA-F]{3,8}\b', html), f'{src.name}: hex 색')

    # ── stacked-bar ─────────────────────────────────────────────────
    def test_stacked_total_mismatch_rejected(self):
        def bad(m):
            m['chart']['data'][0]['total'] = 999
        p = self._mutate(ST, bad, 'st-bad.json')
        code, log = run(p, self.tmp / 'st-bad.html')
        self.assertEqual(code, 1)
        self.assertIn('세그먼트 합', log)

    def test_stacked_structure(self):
        out = self.tmp / 'st-ok.html'
        code, log = run(ST, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('data-variant="stacked"', html)
        self.assertIn('fill="var(--muted)"', html, 'oneoff 세그먼트 회색 없음')
        self.assertIn('var(--accent)', html, 'highlight 세그먼트 없음')
        self.assertGreaterEqual(html.count('opacity="'), 3, '농도 순환 세그먼트 부족')

    # ── line ────────────────────────────────────────────────────────
    def test_line_series_len_mismatch_rejected(self):
        def bad(m):
            m['chart']['series'][0]['points'] = [1, 2, 3]
        p = self._mutate(LN, bad, 'ln-bad.json')
        code, log = run(p, self.tmp / 'ln-bad.html')
        self.assertEqual(code, 1)
        self.assertIn('points 수', log)

    def test_line_structure(self):
        out = self.tmp / 'ln-ok.html'
        code, log = run(LN, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('data-variant="line"', html)
        self.assertIn('opacity=".14"', html, 'fill 계열 면적 없음')
        self.assertIn('stroke="var(--accent)"', html, 'highlight 계열 초점색 없음')

    # ── scatter ─────────────────────────────────────────────────────
    def test_scatter_axis_label_required(self):
        def bad(m):
            del m['chart']['measure']['x']
        p = self._mutate(SC, bad, 'sc-bad.json')
        code, log = run(p, self.tmp / 'sc-bad.html')
        self.assertEqual(code, 1)
        self.assertIn('measure.x', log)

    def test_scatter_structure(self):
        out = self.tmp / 'sc-ok.html'
        code, log = run(SC, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('data-variant="scatter"', html)
        self.assertGreaterEqual(html.count('<circle'), 9, '점 수 부족')

    # ── heatmap ─────────────────────────────────────────────────────
    def test_heatmap_bad_cell_ref_rejected(self):
        def bad(m):
            m['chart']['data']['cells'][0]['r'] = 9
        p = self._mutate(HM, bad, 'hm-bad.json')
        code, log = run(p, self.tmp / 'hm-bad.html')
        self.assertEqual(code, 1)
        self.assertIn('r,c 참조 불가', log)

    def test_heatmap_structure(self):
        out = self.tmp / 'hm-ok.html'
        code, log = run(HM, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('data-variant="matrix"', html)
        self.assertIn('color-mix', html, 'color-mix 농도 없음')
        self.assertIn('var(--accent)', html, 'highlight 행/열 초점 없음')

    # ── matrix-2x2 ──────────────────────────────────────────────────
    def test_matrix_axes_required(self):
        def bad(m):
            del m['chart']['axes']
        p = self._mutate(MX, bad, 'mx-bad.json')
        code, log = run(p, self.tmp / 'mx-bad.html')
        self.assertEqual(code, 1)
        self.assertIn('chart.axes', log)

    def test_matrix_structure(self):
        out = self.tmp / 'mx-ok.html'
        code, log = run(MX, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('data-variant="matrix-2x2"', html)
        self.assertIn('집중 육성', html, '사분면 라벨 없음')

    # ── tornado ─────────────────────────────────────────────────────
    def test_tornado_low_ge_high_rejected(self):
        def bad(m):
            m['chart']['data'][0]['low'] = 300
        p = self._mutate(TN, bad, 'tn-bad.json')
        code, log = run(p, self.tmp / 'tn-bad.html')
        self.assertEqual(code, 1)
        self.assertIn('low', log)

    def test_tornado_sorted_by_range(self):
        out = self.tmp / 'tn-ok.html'
        code, log = run(TN, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        first = html.find('판매 단가')
        second = html.find('판매 물량')
        self.assertTrue(0 < first < second, '범위 내림차순 정렬 아님')
        self.assertIn('−210', html)

    # ── sankey ──────────────────────────────────────────────────────
    def test_sankey_bad_flow_ref_rejected(self):
        def bad(m):
            m['chart']['data']['flows'][0]['to'] = 'nowhere'
        p = self._mutate(SK, bad, 'sk-bad.json')
        code, log = run(p, self.tmp / 'sk-bad.html')
        self.assertEqual(code, 1)
        self.assertIn("nodes 에 없는 id", log)

    def test_sankey_structure(self):
        out = self.tmp / 'sk-ok.html'
        code, log = run(SK, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('data-variant="data"', html)
        self.assertGreaterEqual(html.count(' Z" fill='), 6, '흐름 밴드 부족')
        self.assertIn('class="k-solid-n"', html, '중간 노드 남색 없음')

    # ── pareto ──────────────────────────────────────────────────────
    def test_pareto_ratio_sum_rejected(self):
        def bad(m):
            m['chart']['measure']['unit'] = '%'
        p = self._mutate(PA, bad, 'pa-bad.json')
        code, log = run(p, self.tmp / 'pa-bad.html')
        self.assertEqual(code, 1)
        self.assertIn('비율 모드', log)

    def test_pareto_structure(self):
        out = self.tmp / 'pa-ok.html'
        code, log = run(PA, out)
        self.assertEqual(code, 0, log)
        html = out.read_text(encoding='utf-8')
        self.assertIn('data-variant="pareto"', html)
        self.assertIn('100%', html, '누적 100% 라벨 없음')
        self.assertIn('80%', html, '80% 임계선 라벨 없음')
        self.assertIn('transform-origin:center bottom', html)

    # ── slide.class ─────────────────────────────────────────────────
    def test_slide_class(self):
        def add(m):
            m['slide']['class'] = 'consult'
        p = self._mutate(RB, add, 'cls.json')
        out = self.tmp / 'cls.html'
        code, log = run(p, out)
        self.assertEqual(code, 0, log)
        self.assertIn('<section class="slide consult"', out.read_text(encoding='utf-8'))

    # ── --check 계약 ────────────────────────────────────────────────
    def test_check_byte_compare(self):
        out = self.tmp / 'chk.html'
        code, log = run(WF, out)
        self.assertEqual(code, 0, log)
        code, log = run(WF, out, ['--check'])
        self.assertEqual(code, 0, log)
        self.assertIn('SAME', log)
        out.write_text(out.read_text() + 'x', encoding='utf-8')
        code, log = run(WF, out, ['--check'])
        self.assertEqual(code, 1)
        self.assertIn('DIFF', log)


if __name__ == '__main__':
    unittest.main()
