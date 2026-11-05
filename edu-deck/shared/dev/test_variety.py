#!/usr/bin/env python3
"""legacy 다양성 회귀 시험: tone_router 결정적 라우팅 + arc 인지 검사 + 테마/표지 계약.

[목적] TASK-variety-overhaul G4·G7: 같은 주제는 같은 추천(결정적), 서로 다른 주제는
       서로 다른 추천(다양성)이어야 한다. arc 지정 덱의 흐름 규칙도 함께 잠근다.
[입력] 과제 §6 고정 주제 8개. 표지·테마는 실제 자산 파일과 교차 확인한다.
[출력] 없음(단정문). 실패는 라우팅 다양성 붕괴·계약 위반이다.
[주의] 추천 '값' 자체는 해시·시그니처 조정으로 바뀔 수 있다. 이 시험은 다양성·
       결정성·계약만 잠근다 — 특정 주제가 특정 테마를 받는다고 단정하지 않는다.
"""
import html
import importlib
import json
from pathlib import Path
import sys
import unittest

from bs4 import BeautifulSoup

SHARED = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARED / 'scripts'))
import tone_router  # noqa: E402
checker = importlib.import_module('check_deck')

SNIPPETS = SHARED / 'assets' / 'snippets'
THEMES_CSS = SHARED / 'assets' / 'css' / 'themes.css'
NOTES = '노트 ' + '설명 문장입니다. ' * 12

# TASK §6 고정 주제 (제목, 교육 뒤 할 수 있어야 하는 것, 청중)
TOPICS = [
    ("비와 비율 학습지", "문제를 단계별로 풀 수 있다", "초등 저학년 학생"),
    ("물질의 상태 변화 단원 퀴즈", "상태 변화를 설명하고 퀴즈를 푼다", "초등 학생"),
    ("개인정보 보호 기본", "개인정보 처리 규정을 지킨다", "전 직원"),
    ("폭염 작업 안전", "폭염 위험을 알고 안전 수칙을 지킨다", "현장 작업자"),
    ("재무제표 읽는 법", "재무제표의 구조를 읽는다", "비전공 직원"),
    ("신입 온보딩", "회사 문화와 도구를 익힌다", "신입 직원"),
    ("고객 응대 사례 판단", "응대 사례의 옳고 그름을 판단한다", "고객 상담 직원"),
    ("신규 전자결재 시스템 사용법", "전자결재를 상신한다", "전 직원"),
]


def slide(arch, extra=''):
    return f'<section class="slide" data-archetype="{arch}" {extra}><h1>제목</h1><aside class="notes">{NOTES}</aside></section>'


def document(slides_html, arc=None):
    meta = f'<meta name="edu-deck-arc" content="{html.escape(arc, quote=True)}">' if arc else ''
    return f'<html><head><title>교육</title>{meta}</head><body><div id="stage">{slides_html}</div></body></html>'


def flow_warnings(text):
    rep = checker.Report()
    checker.static_checks(text, BeautifulSoup(text, 'html.parser'), rep, False)
    return [i for i in rep.items if i['kind'] == '흐름']


class TestRouterDeterminism(unittest.TestCase):
    """같은 입력 → 같은 출력. 씨앗을 바꾸면 출력이 바뀔 수 있다(강제 아님)."""

    def test_same_input_same_output(self):
        for topic in TOPICS:
            r1 = tone_router.route(*topic)
            r2 = tone_router.route(*topic)
            self.assertEqual(r1, r2, topic[0])

    def test_seed_changes_are_deterministic_too(self):
        for topic in TOPICS:
            r1 = tone_router.route(*topic, seed='99')
            r2 = tone_router.route(*topic, seed='99')
            self.assertEqual(r1, r2)

    def test_axes_in_unit_interval(self):
        for topic in TOPICS:
            ax = tone_router.route(*topic)['axes']
            self.assertEqual(set(ax), set(tone_router.AXES))
            for name, v in ax.items():
                self.assertGreaterEqual(v, 0.0, name)
                self.assertLessEqual(v, 1.0, name)

    def test_candidates_valid_and_distinct(self):
        tables = {'theme': tone_router.THEMES, 'cover': tone_router.COVERS, 'arc': tone_router.ARCS}
        for topic in TOPICS:
            r = tone_router.route(*topic)
            for kind, table in tables.items():
                cands = r[kind]['candidates']
                self.assertEqual(len(cands), 3)
                ids = [c['id'] for c in cands]
                self.assertEqual(len(set(ids)), 3)
                self.assertTrue(all(i in table for i in ids), (kind, ids))
                self.assertEqual(r[kind]['recommend'], ids[0])
                self.assertTrue(all(c['because'] for c in cands))

    def test_reject_empty_title_and_bad_recent(self):
        with self.assertRaises(tone_router.RouterError):
            tone_router.route('')
        with self.assertRaises(tone_router.RouterError):
            tone_router.route('제목', recent_theme=['nope'])


class TestRouterDiversity(unittest.TestCase):
    """§6 고정 주제 8개의 추천이 게이트 다양성을 넘는지."""

    def test_diversity_gates(self):
        recs = [tone_router.route(*t) for t in TOPICS]
        themes = {r['theme']['recommend'] for r in recs}
        covers = {r['cover']['recommend'] for r in recs}
        arcs = {r['arc']['recommend'] for r in recs}
        self.assertGreaterEqual(len(themes), 5, sorted(themes))
        self.assertGreaterEqual(len(covers), 4, sorted(covers))
        self.assertGreaterEqual(len(arcs), 4, sorted(arcs))
        # 후보까지 포함하면 더 넓게 퍼져야 한다(지터가 후보를 돌린다)
        self.assertGreaterEqual(len({c['id'] for r in recs for c in r['theme']['candidates']}), 6)

    def test_weak_signal_flag_and_note(self):
        r = tone_router.route('무제 교육', '', '')
        self.assertTrue(r['weak_signal'])
        self.assertIn('note', r)
        strong = tone_router.route(*TOPICS[3])
        self.assertFalse(strong['weak_signal'])
        self.assertNotIn('note', strong)


class TestArcAwareFlow(unittest.TestCase):
    """arc 지정 덱은 opens 규칙, 미지정 덱은 기존 agenda 규칙, 알 수 없는 arc 는 명시적 경고."""

    def test_no_arc_keeps_agenda_rule(self):
        warns = flow_warnings(document(slide('cover') + slide('statement')))
        self.assertTrue(any('순서(agenda)' in i['message'] for i in warns), warns)

    def test_no_arc_agenda_passes(self):
        warns = flow_warnings(document(slide('cover') + slide('agenda') + slide('closing')))
        self.assertFalse([i for i in warns if 'agenda' in i['message']], warns)

    def test_arc_opening_accepted(self):
        warns = flow_warnings(document(slide('cover') + slide('statement') + slide('closing'), arc='hook'))
        self.assertFalse([i for i in warns if 'arc' in i['message'] or 'agenda' in i['message']], warns)

    def test_arc_opening_mismatch_warns(self):
        warns = flow_warnings(document(slide('cover') + slide('agenda') + slide('closing'), arc='warmup'))
        self.assertTrue(any("arc 'warmup'" in i['message'] for i in warns), warns)

    def test_unknown_arc_warns(self):
        warns = flow_warnings(document(slide('cover') + slide('agenda'), arc='nonsense'))
        self.assertTrue(any('알 수 없는 arc' in i['message'] for i in warns), warns)

    def test_every_arc_opening_passes(self):
        for arc_id, spec in tone_router.ARCS.items():
            for opening in spec['opens']:
                warns = flow_warnings(document(slide('cover') + slide(opening) + slide('closing'), arc=arc_id))
                self.assertFalse([i for i in warns if i['kind'] == '흐름' and 'arc' in i['message']],
                                 (arc_id, opening, warns))


class TestAssetContracts(unittest.TestCase):
    """라우터 표 ↔ 실제 자산의 교차 계약: themes.css 블록·표지 변형 파일·아크 opens 아키타입."""

    def test_themes_css_matches_router_ids(self):
        parsed = checker.parse_theme_tokens(THEMES_CSS.read_text(encoding='utf-8'))
        self.assertEqual(set(parsed), set(tone_router.THEME_CSS_IDS))
        for tid, roles in parsed.items():
            for role in checker.SEMANTIC_ROLES:
                self.assertIn(role, roles, f'{tid} --{role}')

    def test_theme_matrix_rows_exist(self):
        base, packs = checker.parse_tokens(
            (SHARED / 'assets' / 'css' / 'tokens.css').read_text(encoding='utf-8'))
        themes = checker.parse_theme_tokens(THEMES_CSS.read_text(encoding='utf-8'))
        rows = checker.build_matrix(base, packs, themes)
        theme_rows = [r for r in rows if r['pack'].startswith('theme:')]
        self.assertEqual(len(theme_rows), len(themes) * len(checker.MATRIX_ROWS))
        self.assertTrue(all(r['pass'] for r in rows), [r for r in rows if not r['pass']])

    def test_cover_snippets_exist_with_contract(self):
        found = {}
        for f in SNIPPETS.glob('01-cover*.html'):
            text = f.read_text(encoding='utf-8')
            m = __import__('re').search(r'data-variant="([\w-]+)"', text)
            vid = m.group(1) if m else 'orbit'
            found[vid] = text
            self.assertIn('id="cx-typed"', text, f.name)
            self.assertIn('data-text=', text, f.name)
            self.assertIn('data-archetype="cover"', text, f.name)
            self.assertIn('«', text, f.name)
        for vid in tone_router.COVERS:
            self.assertIn(vid, found, vid)
        self.assertGreaterEqual(len(found), 6)

    def test_arc_openings_are_known_archetypes(self):
        for arc_id, spec in tone_router.ARCS.items():
            self.assertGreaterEqual(len(spec['opens']), 1)
            for opening in spec['opens']:
                self.assertIn(opening, checker.ARCHETYPES, (arc_id, opening))


if __name__ == '__main__':
    unittest.main()
