"""Acceptance: 구성도·업무 흐름 부품(data-c="stack").

- stack_schema.py: 정상/비정상 data-d (형태 오류·칸 넘침·그룹 덮음·중첩·아이콘)
- build_deck.py: stack 있을 때만 kit 자산 주입, 없는 덱은 자산 0건
- Chromium: 37-arch-flow 8변형 완성 렌더 + stack-reveal 발화 + 재방문·감속·인쇄 정적 완결
- route 규칙: 무작위 격자 300개에서 화살표 경로가 끝점 아닌 노드 상자를 지나지 않는다
"""
import json, re, sys, unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import build, BuildError
from check_deck import launch
from stack_schema import check_data_d, StackSchemaError

OUT = Path('/tmp/edudeck-stack')
SRC = OUT / 'src'
SNIPPET = S / 'assets' / 'snippets' / '37-arch-flow.html'

NOTES = ('이 장에서는 구성도 부품의 등장과 완성 상태를 확인합니다. 발표 중에는 그룹·노드·화살표가 '
         '순서대로 나타나고 자습 모드에서는 최종 상태만 보입니다. 설명을 조금 더 덧붙여 길이를 맞춥니다.')


def sec(body, arch='arch-flow', variant='x'):
    return (f'<section class="slide" data-archetype="{arch}" data-variant="{variant}">'
            f'<div class="head"><p class="eyebrow">시험</p><h2 class="title">구성도 시험</h2></div>'
            f'{body}<aside class="notes">{NOTES}</aside></section>')


def dd(o):
    return json.dumps(o, ensure_ascii=False, separators=(',', ':'))


BASE = {
    'nodes': [
        {'id': 'a', 'name': '접수', 'icon': 'mail', 'row': 0, 'col': 0, 'role': '요청', 'badge': 1},
        {'id': 'b', 'name': '검토', 'icon': 'search', 'row': 0, 'col': 1, 'role': '확인', 'badge': 2},
        {'id': 'c', 'name': '완료', 'icon': 'circle-check', 'row': 0, 'col': 2, 'tone': 'brand'},
    ],
    'edges': [{'from': 'a', 'to': 'b'}, {'from': 'b', 'to': 'c', 'label': '통과'}],
    'groups': [{'id': 'g', 'label': '처리팀', 'nodes': ['a', 'b', 'c'], 'cols': [0, 2], 'tone': 'brand'}],
}


def stack_fig(o):
    return (f'<figure class="viz-fig"><div class="stack-fig" data-c="stack" role="img" '
            f"aria-label=\"시험 도식\" data-d='{dd(o)}'></div><figcaption>캡션</figcaption></figure>")


def build_deck(files, name):
    SRC.mkdir(parents=True, exist_ok=True)
    for p in SRC.glob('*.html'):
        p.unlink()
    for n, t in files.items():
        (SRC / n).write_text(t, encoding='utf-8')
    return build('구성도 시험', sorted(SRC.glob('*.html')), [S / 'assets' / 'css'],
                 [S / 'assets' / 'icons'], OUT / name)


class SchemaTests(unittest.TestCase):
    def good(self, **over):
        o = json.loads(dd(BASE))
        o.update(over)
        return dd(o)

    def test_valid(self):
        self.assertEqual(check_data_d(dd(BASE)), [])

    def test_minimal(self):
        o = {'nodes': [{'id': 'a', 'name': '가', 'row': 0, 'col': 0},
                       {'id': 'b', 'name': '나', 'row': 1, 'col': 0}],
             'edges': [{'from': 'a', 'to': 'b'}]}
        self.assertEqual(check_data_d(dd(o)), [])

    def test_malformed_json(self):
        with self.assertRaises(StackSchemaError):
            check_data_d('{bad')

    def test_single_quote_rejected(self):
        with self.assertRaises(StackSchemaError):
            check_data_d(dd(BASE) + "'")

    def test_duplicate_cell(self):
        o = self.good()
        d = json.loads(o); d['nodes'][1]['col'] = 0
        with self.assertRaises(StackSchemaError):
            check_data_d(dd(d))

    def test_row_col_bounds(self):
        for bad in [{'row': 3}, {'col': 6}, {'row': -1}]:
            d = json.loads(dd(BASE)); d['nodes'][0].update(bad)
            with self.assertRaises(StackSchemaError, msg=str(bad)):
                check_data_d(dd(d))

    def test_grid_overflow_warns(self):
        # 칸 폭을 넘는 글자는 오류가 아니라 '줄여 그림' 경고
        d = {'nodes': [{'id': 'a', 'name': '아주아주긴이름의노드입니다열다섯자', 'row': 0, 'col': 0},
                       {'id': 'b', 'name': '나', 'row': 0, 'col': 1}]}
        w = check_data_d(dd(d))
        self.assertTrue(any('줄' in x for x in w), w)

    def test_node_count_limits(self):
        for n, ok in ((1, False), (2, True), (14, True), (15, False)):
            d = {'nodes': [{'id': f'n{i}', 'name': f'n{i}', 'row': i // 6 % 3, 'col': i % 6}
                           for i in range(n)]}
            if ok:
                self.assertIsInstance(check_data_d(dd(d)), list)
            else:
                with self.assertRaises(StackSchemaError, msg=f'n={n}'):
                    check_data_d(dd(d))

    def test_edge_count_limit(self):
        d = json.loads(dd(BASE))
        d['edges'] = [{'from': 'a', 'to': 'b'}] * 21
        with self.assertRaises(StackSchemaError):
            check_data_d(dd(d))

    def test_edge_unknown_node(self):
        d = json.loads(dd(BASE))
        d['edges'].append({'from': 'a', 'to': 'zzz'})
        with self.assertRaises(StackSchemaError):
            check_data_d(dd(d))

    def test_group_cover_error(self):
        # 그룹 상자가 멤버가 아닌 노드를 덮는 배치는 오류
        d = {'nodes': [{'id': 'a', 'name': '가', 'row': 0, 'col': 0},
                       {'id': 'b', 'name': '나', 'row': 0, 'col': 1},
                       {'id': 'x', 'name': '덮', 'row': 0, 'col': 2}],
             'groups': [{'id': 'g', 'label': '팀', 'nodes': ['a', 'b'], 'cols': [0, 2]}]}
        with self.assertRaises(StackSchemaError):
            check_data_d(dd(d))

    def test_group_rect_required(self):
        # 선언 cols 밖에 멤버가 있으면 직사각 상자가 깨진다 — 오류
        d = {'nodes': [{'id': 'a', 'name': '가', 'row': 0, 'col': 0},
                       {'id': 'b', 'name': '나', 'row': 0, 'col': 3}],
             'groups': [{'id': 'g', 'label': '팀', 'nodes': ['a', 'b'], 'cols': [0, 1]}]}
        with self.assertRaises(StackSchemaError):
            check_data_d(dd(d))
        # cols 형태 자체가 어긋나도 오류
        d['groups'][0]['cols'] = [4, 1]
        with self.assertRaises(StackSchemaError):
            check_data_d(dd(d))

    def test_group_nesting_one_level(self):
        d = {'nodes': [{'id': 'a', 'name': '가', 'row': 0, 'col': 0},
                       {'id': 'b', 'name': '나', 'row': 0, 'col': 1},
                       {'id': 'c', 'name': '다', 'row': 1, 'col': 0}],
             'groups': [{'id': 'g1', 'label': '바깥', 'nodes': ['a', 'b', 'c'], 'cols': [0, 1]},
                        {'id': 'g2', 'label': '중간', 'nodes': ['a', 'b'], 'parent': 'g1'},
                        {'id': 'g3', 'label': '안쪽', 'nodes': ['a'], 'parent': 'g2'}]}
        with self.assertRaises(StackSchemaError):
            check_data_d(dd(d))

    def test_bad_icon(self):
        d = json.loads(dd(BASE)); d['nodes'][0]['icon'] = 'not-an-icon'
        with self.assertRaises(StackSchemaError):
            check_data_d(dd(d))

    def test_bad_tone_kind(self):
        d = json.loads(dd(BASE)); d['nodes'][0]['tone'] = 'neon'
        with self.assertRaises(StackSchemaError):
            check_data_d(dd(d))
        d = json.loads(dd(BASE)); d['edges'][0]['kind'] = 'neon'
        with self.assertRaises(StackSchemaError):
            check_data_d(dd(d))

    def test_group_count_limit(self):
        d = json.loads(dd(BASE))
        d['groups'] = [{'id': f'g{i}', 'label': f'g{i}', 'nodes': ['a'], 'cols': [0, 0]}
                       for i in range(6)]
        with self.assertRaises(StackSchemaError):
            check_data_d(dd(d))


class InjectionTests(unittest.TestCase):
    def test_injected_when_used(self):
        build_deck({'01.html': sec(stack_fig(BASE))}, 'with-stack.html')
        t = (OUT / 'with-stack.html').read_text(encoding='utf-8')
        self.assertIn('ppt-stack-icons', t)
        self.assertIn('window.PPTStack', t)
        self.assertIn('.stack-fig', t)

    def test_absent_when_unused(self):
        build_deck({'01.html': sec('<p class="big">도식 없는 장</p>', arch='statement')}, 'no-stack.html')
        t = (OUT / 'no-stack.html').read_text(encoding='utf-8')
        for k in ('ppt-stack-icons', 'window.PPTStack', 'stack-fig', 'PPTStack'):
            self.assertNotIn(k, t)

    def test_bad_data_d_fails_build(self):
        bad = json.loads(dd(BASE)); bad['nodes'][0]['row'] = 9
        with self.assertRaises(BuildError):
            build_deck({'01.html': sec(stack_fig(bad))}, 'bad.html')

    def test_snippet_schema_all_pass(self):
        t = SNIPPET.read_text(encoding='utf-8')
        ds = re.findall(r"data-d='([^']*)'", t)
        self.assertEqual(len(ds), 8)
        for d in ds:
            self.assertEqual(check_data_d(d), [])

    def test_snippet_variants(self):
        t = SNIPPET.read_text(encoding='utf-8')
        vs = re.findall(r'data-archetype="arch-flow" data-variant="([^"]+)"', t)
        self.assertEqual(sorted(vs),
                         ['decision', 'hub', 'lanes', 'layers', 'link', 'parallel', 'state', 'steps'])
        for v in re.findall(r'<section.*?</section>', t, re.S):
            self.assertIn('viz-fig', v)
            self.assertIn('figcaption', v)
            self.assertIn('aside class="notes"', v)
            self.assertNotIn('data-step', v)


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_deck({}, 'render.html')
        secs = re.findall(r'<section.*?</section>', SNIPPET.read_text(encoding='utf-8'), re.S)
        for i, s in enumerate(secs):
            (SRC / f'{i + 1:02d}.html').write_text(s, encoding='utf-8')
        build('구성도 시험', sorted(SRC.glob('*.html')), [S / 'assets' / 'css'],
              [S / 'assets' / 'icons'], OUT / 'render.html')
        cls.url = (OUT / 'render.html').resolve().as_uri()
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def page(self, **kw):
        pg = self.browser.new_context(viewport={'width': 1920, 'height': 1080}, **kw).new_page()
        pg.goto(self.url)
        pg.wait_for_timeout(400)
        return pg

    def test_all_variants_completed(self):
        pg = self.page()
        for i in range(8):
            pg.evaluate(f'window.deckGo({i})')
            pg.wait_for_timeout(1800)
            r = pg.evaluate('''() => {const s=document.querySelector('#stage>.slide.active .stack-fig');
                return {nodes:s.querySelectorAll('.sf-node').length, edges:s.querySelectorAll('.sf-edge').length,
                        svg:!!s.querySelector('svg'), ready:s.classList.contains('is-ready')}}''')
            self.assertTrue(r['svg'] and r['ready'] and r['nodes'] >= 2, f'slide {i + 1}: {r}')
        pg.close()

    def test_sig_and_no_replay(self):
        pg = self.page()
        pg.evaluate('window.deckGo(0)')
        pg.wait_for_timeout(1600)
        sigs = pg.evaluate('window.eduMotion.sigLog.filter(e=>e.sig==="stack-reveal").length')
        self.assertGreaterEqual(sigs, 1)
        pg.evaluate('window.deckGo(1)')
        pg.wait_for_timeout(300)
        pg.evaluate('window.deckGo(0)')
        pg.wait_for_timeout(400)
        r = pg.evaluate('''() => {const s=document.querySelectorAll('.stack-fig')[0];
            return {done:s.classList.contains('is-done'), play:s.classList.contains('is-play'),
                    sigs:window.eduMotion.sigLog.filter(e=>e.sig==="stack-reveal"&&e.slide===0).length,
                    anims:document.getAnimations().length}}''')
        self.assertTrue(r['done'] and not r['play'] and r['sigs'] == 1, r)
        pg.close()

    def test_reduced_complete(self):
        pg = self.page(reduced_motion='reduce')
        r = pg.evaluate('''() => {const s=document.querySelectorAll('.stack-fig')[0];
            return {nodes:s.querySelectorAll('.sf-node').length, anims:document.getAnimations().length,
                    done:s.classList.contains('is-done')}}''')
        self.assertEqual(r['anims'], 0)
        self.assertGreaterEqual(r['nodes'], 2)
        pg.close()

    def test_print_complete(self):
        pg = self.page()
        pg.emulate_media(media='print')
        pg.wait_for_timeout(300)
        r = pg.evaluate('''() => {const s=document.querySelectorAll('.stack-fig')[0];
            return {nodes:s.querySelectorAll('.sf-node').length, play:s.classList.contains('is-play'),
                    anims:document.getAnimations().length}}''')
        self.assertGreaterEqual(r['nodes'], 2)
        self.assertFalse(r['play'])
        pg.close()

    def test_route_300_grids(self):
        pg = self.page()
        r = pg.evaluate(r'''() => {
          const C = window.PPTStack; if (!C) return {err: 'no PPTStack'};
          let seed = 20261106;
          const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
          let cases = 0, violations = [];
          const segHit = (p, q, R) => {           // 직교 선분이 상자 내부를 지나는가
            if (p[0] === q[0]) {                  // 세로
              const x = p[0]; if (x <= R.x0 || x >= R.x1) return false;
              const lo = Math.min(p[1], q[1]), hi = Math.max(p[1], q[1]);
              return hi > R.y0 && lo < R.y1;
            }
            const y = p[1]; if (y <= R.y0 || y >= R.y1) return false;
            const lo = Math.min(p[0], q[0]), hi = Math.max(p[0], q[0]);
            return hi > R.x0 && lo < R.x1;
          };
          for (let k = 0; k < 300; k++) {
            const cells = [];
            for (let r0 = 0; r0 < 3; r0++) for (let c0 = 0; c0 < 6; c0++) cells.push([r0, c0]);
            const nn = 2 + Math.floor(rnd() * 13);
            const nodes = [];
            for (let i = 0; i < nn; i++) {
              const j = Math.floor(rnd() * cells.length), [r0, c0] = cells.splice(j, 1)[0];
              nodes.push({id: 'n' + i, name: 'n' + i, row: r0, col: c0});
            }
            const ne = Math.min(20, 1 + Math.floor(rnd() * (nn * (nn - 1))));
            const edges = [], used = new Set();
            for (let i = 0; i < ne; i++) {
              const a = Math.floor(rnd() * nn), b = Math.floor(rnd() * nn);
              if (a === b || used.has(a + '-' + b)) continue;
              used.add(a + '-' + b); edges.push({from: 'n' + a, to: 'n' + b});
            }
            const o = {nodes, edges};
            const g = C.geometry(o), at = (r0, c0) => nodes.find(n => n.row === r0 && n.col === c0);
            const rect = n => ({x0: n.cx - C.consts.BW / 2, y0: n.top, x1: n.cx + C.consts.BW / 2, y1: n.top + C.consts.BH});
            for (const e of edges) {
              const a = g.N[e.from], b = g.N[e.to];
              const rev = edges.some(x => x.from === e.to && x.to === e.from);
              const fwd = a.row < b.row || (a.row === b.row && a.col < b.col);
              const {pts} = C.route(a, b, at, rev ? (fwd ? -9 : 9) : 0);
              for (const n of Object.values(g.N)) {
                if (n === a || n === b) continue;
                const R = rect(n);
                for (let i = 0; i + 1 < pts.length; i++)
                  if (segHit(pts[i], pts[i + 1], R)) { violations.push({k, e, n: n.id, i}); break; }
              }
            }
            cases++;
          }
          return {cases, violations: violations.length, sample: violations.slice(0, 3)};
        }''')
        self.assertEqual(r.get('cases'), 300, r)
        self.assertEqual(r.get('violations'), 0, r)
        pg.close()


if __name__ == '__main__':
    unittest.main()
