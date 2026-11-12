#!/usr/bin/env python3
"""check_consulting.py — 컨설팅 덱 근거 대조 (references/evidence.md §2 스키마 원본)

작업 폴더의 evidence.json 원장을 화면(src/*.html)과 차트 모델(charts/*.json)과 대조한다.
등급은 references/quality-gates.md §0: FAIL=blocker(납품 불가) · WARN=warning(명시 후 납품).

  python3 check_consulting.py <작업 폴더>

검사:
  1. 스키마 — evidence.json 필수 필드·source_id/claim_id 유일성·kind/freshness 열거
  2. 출처 존재 — 화면 c-src·차트 모델 source.text 에 대응하는 sources 엔트리
  3. 가상 표기 — 모델 synthetic ↔ claims kind=synthetic · 화면 s-syn ↔ 원장 synthetic
  4. 수치 대조 — 차트 모델의 값(expectTotal·value·segments·points·cells·flows·low/high)
     이 대응 claim 의 value/original/statement/method 안 수치와 일치(쉼표·억/조 정규화).
     src HTML 의 텍스트 수치 ↔ 원장 매칭은 초기 버전 WARN 으로만.
  5. 기준일 — stale 출처를 쓰는데 화면·모델에 asOf(기준일)가 없으면 WARN

exit 0=PASS(warn 허용) · 1=FAIL 또는 evidence.json 없음/파싱 불가.
"""
import json
import re
import sys
from pathlib import Path

KINDS = {'fact', 'calculated', 'estimate', 'projection', 'synthetic', 'hypothesis'}
FRESH = {'current', 'aging', 'stale'}
SRC_REQ = ('source_id', 'title', 'locator', 'freshness')
CLM_REQ = ('claim_id', 'slide', 'statement', 'source_id', 'kind')

NUM_RE = re.compile(r'-?\d[\d,]*(?:\.\d+)?\s*(?:조|억|만|%|배)?')
DATE_RE = re.compile(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}')
TAG_RE = re.compile(r'<[^>]+>')


def norm_stem(stem):
    """'01-cost-bridge' → 'cost-bridge' — NN- 접두사를 떼고 대조 키로 쓴다.
    '05-x.flint.json' 의 stem 은 '05-x.flint' 이므로 .flint 꼬리도 뗀다."""
    return re.sub(r'^\d+-', '', stem.removesuffix('.flint'))


def numbers(text):
    """문자열 안 수치 후보 집합 — 쉼표 제거 + 억/조 환산 변형을 둘 다 넣는다."""
    out = set()
    for m in NUM_RE.finditer(DATE_RE.sub(' ', text or '')):
        tok = m.group(0)
        u = '조' if '조' in tok else '억' if '억' in tok else None
        try:
            v = float(re.sub(r'[^\d.\-]', '', tok.split(u)[0] if u else tok))
        except ValueError:
            continue
        out.add(round(v, 4))
        if u == '조':
            out.add(round(v * 10000, 4))
        if u == '억':
            out.add(round(v / 10000, 4))
    return out


def nums_close(v, pool):
    """|v| 가 pool 수치와 같은지 — 부호는 무시(원장은 양수로 적는 경우가 많다)."""
    return any(abs(abs(v) - abs(c)) <= max(0.005, abs(c) * 5e-4) for c in pool)


def chart_values(model):
    """차트 모델 안의 '주요 값' — 타입별 수치 필드를 전부 긁는다."""
    if model.get('engine') == 'flint':
        # flint 모델: flint.data.values 행의 수치 필드 전수(근거 대조 대상)
        rows = (((model.get('flint') or {}).get('data') or {}).get('values')) or []
        vals = []
        for r in rows:
            if isinstance(r, dict):
                for k, v in r.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        vals.append((f'values.{k}', v))
        return vals
    ch = model.get('chart', {})
    vals = []
    data = ch.get('data')
    if isinstance(data, list):
        for d in data:
            if not isinstance(d, dict):
                continue
            for k in ('value', 'low', 'high', 'x', 'y', 'total'):
                if isinstance(d.get(k), (int, float)):
                    vals.append((f'data.{k}', d[k]))
            for g in d.get('segments') or []:
                if isinstance(g, dict) and isinstance(g.get('value'), (int, float)):
                    vals.append(('segments.value', g['value']))
    elif isinstance(data, dict):
        for c in data.get('cells') or []:
            if isinstance(c, dict) and isinstance(c.get('v'), (int, float)):
                vals.append(('cells.v', c['v']))
        for f in data.get('flows') or []:
            if isinstance(f, dict) and isinstance(f.get('value'), (int, float)):
                vals.append(('flows.value', f['value']))
    for s in ch.get('series') or []:
        for v in s.get('points') or []:
            if isinstance(v, (int, float)):
                vals.append(('series.points', v))
    et = (ch.get('calc') or {}).get('expectTotal')
    if isinstance(et, (int, float)):
        vals.append(('calc.expectTotal', et))
    return vals


def main():
    if len(sys.argv) != 2:
        print('usage: check_consulting.py <작업 폴더>', file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    errors, warns = [], []
    fail = lambda m: errors.append(m)
    warn = lambda m: warns.append(m)

    # ── 1. 스키마 ───────────────────────────────────────────────────
    ev_path = root / 'evidence.json'
    if not ev_path.exists():
        print(f'FAIL: evidence.json 없음 — {root} 에 근거 원장을 둔다(evidence.md §2)')
        print('RESULT errors=1')
        return 1
    try:
        ev = json.loads(ev_path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'FAIL: evidence.json 파싱 불가 — {e}')
        print('RESULT errors=1')
        return 1

    sources, claims = {}, {}
    for i, s in enumerate(ev.get('sources') or []):
        for k in SRC_REQ:
            if k not in s:
                fail(f'sources[{i}] 필수 필드 {k} 누락')
        sid = s.get('source_id')
        if sid in sources:
            fail(f'source_id 중복: {sid}')
        sources[sid] = s
        if s.get('freshness') not in FRESH:
            fail(f'sources[{i}].freshness "{s.get("freshness")}" — current|aging|stale 만 허용')
    for i, c in enumerate(ev.get('claims') or []):
        for k in CLM_REQ:
            if k not in c:
                fail(f'claims[{i}] 필수 필드 {k} 누락')
        cid = c.get('claim_id')
        if cid in claims:
            fail(f'claim_id 중복: {cid}')
        claims[cid] = c
        if c.get('kind') not in KINDS:
            fail(f'claims[{i}].kind "{c.get("kind")}" — {"|".join(sorted(KINDS))} 만 허용')
        if c.get('source_id') not in sources:
            fail(f'claims[{i}].source_id "{c.get("source_id")}" — sources 에 없는 출처 참조')

    # 슬라이드 키 → claim 묶음
    by_slide = {}
    for c in claims.values():
        by_slide.setdefault(norm_stem(str(c.get('slide', ''))), []).append(c)

    # 출처 매칭 풀 — title·publisher·locator 문자열 조각
    src_strings = []
    for s in sources.values():
        for k in ('title', 'publisher', 'locator'):
            if s.get(k):
                src_strings.append(str(s[k]))
    def src_match(text):
        t = str(text or '')
        return any(p and p in t for p in src_strings)

    src_dir, charts_dir = root / 'src', root / 'charts'
    htmls = sorted(src_dir.glob('*.html')) if src_dir.is_dir() else []
    models = sorted(charts_dir.glob('*.json')) if charts_dir.is_dir() else []

    # 표식 도식(data-lint="svg-diagram") 린트 — shared/scripts/diagram_lint.py.
    # 표식 없는 파일은 비용 0으로 건너뛴다.
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'edu-deck' / 'shared' / 'scripts'))
        from diagram_lint import check_diagrams

        class _LintRep:
            def __init__(self):
                self.errors, self.warnings, self.notes = [], [], []

        for hp in htmls:
            lr = _LintRep()
            check_diagrams(hp.read_text(encoding='utf-8'), root, lr)
            for m in lr.errors:
                fail(f'{hp.name}: 도식 {m}')
            for m in lr.warnings:
                warn(f'{hp.name}: 도식 {m}')
    except Exception as e:
        fail(f'도식 검사를 끝내지 못했습니다(내부 오류: {type(e).__name__})')

    # ── 2·3·4. 차트 모델 대조 ───────────────────────────────────────
    for mp in models:
        key = norm_stem(mp.stem)
        try:
            model = json.loads(mp.read_text(encoding='utf-8'))
        except Exception as e:
            fail(f'{mp.name}: JSON 파싱 불가 — {e}')
            continue
        ms = model.get('source') or {}
        mclaims = by_slide.get(key, [])
        synth_claims = [c for c in mclaims if c.get('kind') == 'synthetic']
        synthetic = ms.get('synthetic') is True
        # 3. 가상 표기 — 양방향
        if synthetic and not synth_claims:
            fail(f'{mp.name}: source.synthetic=true 인데 슬라이드 {key} 의 kind=synthetic claim 이 없다')
        if not synthetic and synth_claims:
            fail(f'{mp.name}: 모델은 실데이터인데 슬라이드 {key} 에 synthetic claim({synth_claims[0].get("claim_id")})이 있다')
        # 2. 출처 존재 — 실데이터 모델은 source.text 가 원장 출처와 대응해야 한다
        if not synthetic:
            if not mclaims:
                fail(f'{mp.name}: 슬라이드 {key} 에 대응하는 claim 이 없다 — 근거 없는 차트')
            if not src_match(ms.get('text')):
                fail(f'{mp.name}: source.text "{str(ms.get("text"))[:40]}…" — sources 어디에도 대응하지 않는다')
        # 4. 수치 대조 — 모델 주요 값이 대응 claim 수치 안에 있어야 한다
        pool = set()
        for c in mclaims:
            for k in ('value', 'original', 'statement', 'method'):
                pool |= numbers(c.get(k))
        if pool:
            bad = [f'{k}={v}' for k, v in chart_values(model) if not nums_close(v, pool)]
            if bad:
                fail(f'{mp.name}: 원장과 불일치 수치 {len(bad)}건 — {", ".join(bad[:6])}')
        # 5. 기준일 — stale 출처인데 asOf 없으면
        stale = any(sources.get(c.get('source_id'), {}).get('freshness') == 'stale' for c in mclaims)
        if stale and not ms.get('asOf'):
            warn(f'{mp.name}: stale 출처 사용 — source.asOf(기준일)를 모델에 표기하라')

    # ── 2·3·4·5. 화면(src/*.html) 대조 ──────────────────────────────
    for hp in htmls:
        key = norm_stem(hp.stem)
        text = hp.read_text(encoding='utf-8')
        mclaims = by_slide.get(key, [])
        has_syn = 's-syn' in text
        has_src = 'c-src' in text
        # 3. 가상 표기
        if has_syn and not any(c.get('kind') == 'synthetic' for c in mclaims):
            fail(f'{hp.name}: s-syn(가상 데이터 표기)이 있는데 슬라이드 {key} 의 synthetic claim 이 없다')
        # 2. 출처 존재 — c-src 가 있고 가상 표기가 아니면 원장 출처와 대응해야 한다
        m = re.search(r'Source:\s*([^<·]+)', text)
        if has_src and not has_syn and m and not src_match(m.group(1)):
            fail(f'{hp.name}: c-src "{m.group(1).strip()[:40]}…" — sources 어디에도 대응하지 않는다')
        # 4. 수치 대조(WARN 급) — 제목·m-v·표 셀의 큰 수치가 원장에 없으면 경고
        if mclaims:
            pool = set()
            for c in mclaims:
                for k in ('value', 'original', 'statement', 'method'):
                    pool |= numbers(c.get(k))
            plain = TAG_RE.sub(' ', text)
            big = {v for v in numbers(plain) if abs(v) >= 10 and abs(v) not in (1080, 1920) and not 1900 <= abs(v) <= 2100}
            unmatched = sorted(v for v in big if not nums_close(v, pool))
            if unmatched:
                warn(f'{hp.name}: 화면 수치 {len(unmatched)}건 원장 미대조 — {unmatched[:5]}')
        # 5. 기준일
        stale = any(sources.get(c.get('source_id'), {}).get('freshness') == 'stale' for c in mclaims)
        if stale and '기준' not in text:
            warn(f'{hp.name}: stale 출처 사용 — 출처 블록에 기준일을 표기하라')

    # claim 이 가리키는 슬라이드가 실제 없으면 WARN
    names = {norm_stem(p.stem) for p in htmls} | {norm_stem(p.stem) for p in models}
    for c in claims.values():
        if norm_stem(str(c.get('slide', ''))) not in names:
            warn(f'claim {c.get("claim_id")}: slide "{c.get("slide")}" — 대응 화면·모델 없음')

    for m in errors:
        print(f'FAIL  {m}')
    for m in warns:
        print(f'WARN  {m}')
    print(f'RESULT errors={len(errors)} warnings={len(warns)} slides={len(htmls)} charts={len(models)} claims={len(claims)}')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
