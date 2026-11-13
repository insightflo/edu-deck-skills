#!/usr/bin/env python3
"""파트 톤(P5) 계약 시험 — --tone-1..7 토큰·data-tone/data-part-tone 매핑·build 전파·대비.

[목적] ① tokens.css 에 --tone-1..7 이 있고 components.css 가 [data-tone]·[data-part-tone] 을
         --part-tone 으로 잇는다(dark·orange 장에서는 종이색 섞임으로 밝게).
       ② build_deck.propagate_part_tones 가 파트 구분 장의 data-tone 을 다음 구분 장 전까지
         data-part-tone 으로 퍼뜨리고, 톤 없는 구분 장에서 끊고, 저작자의 data-part-tone 은 존중하며,
         톤이 하나도 없으면 원문을 그대로 돌려준다.
       ③ 소비처(38-part-divider·core .eyebrow·02-agenda·구분 장 톤 선·색면)가 var(--part-tone,폴백)을 쓴다.
       ④ classic 테마에서 --tone-1..7 과 --paper 의 대비가 4.5:1 이상이다(본문 글자 수준).
       ⑤ P1 확장 회귀 — eyebrow 글자·아젠다 라벨·구분 장 6px 톤 선, P4 무드(색면·점 격자·선언 배너),
          톤 미지정 시 폴백색이 그대로 쓰인다.
[입력] shared/assets/css/*.css 원본 + build_deck.propagate_part_tones. 브라우저 없음.
[출력] 없음(단정문).
"""
import re
import sys
import unittest
from pathlib import Path

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
from build_deck import propagate_part_tones  # noqa: E402
import check_deck  # noqa: E402

TOKENS = (S / 'assets/css/tokens.css').read_text(encoding='utf-8')
COMPONENTS = (S / 'assets/css/components.css').read_text(encoding='utf-8')
CORE = (S / 'assets/css/core.css').read_text(encoding='utf-8')
AGENDA = (S / 'assets/snippets/02-agenda.html').read_text(encoding='utf-8')
DIVIDER = (S / 'assets/snippets/38-part-divider.html').read_text(encoding='utf-8')
VERDICT = (S / 'assets/snippets/53-verdict.html').read_text(encoding='utf-8')
THEMES = (S / 'assets/css/themes.css').read_text(encoding='utf-8')


def slides(*sections):
    return ''.join(sections)


class ToneTokens(unittest.TestCase):
    def test_seven_tones_defined(self):
        for n in range(1, 8):
            self.assertIn(f'--tone-{n}:', TOKENS, f'--tone-{n} 누락')

    def test_attr_mapping(self):
        for n in range(1, 8):
            self.assertIn(f'[data-part-tone="{n}"]', COMPONENTS)
            self.assertIn(f'[data-tone="{n}"]', COMPONENTS)
        self.assertIn(':is(.dark,.orange)', COMPONENTS,
                      '다크·주황 장에서는 톤을 밝게 섞어 쓴다')

    def test_consumers_three_places(self):
        self.assertIn('var(--part-tone,', DIVIDER, '파트 구분 강조')
        self.assertIn('.eyebrow::before', CORE)
        self.assertIn('var(--part-tone,currentColor)', CORE, '눈금 표시 막대')
        self.assertIn('var(--part-tone,', AGENDA, '아젠다 항목색')

    # ---------- P1 확장 소비 3곳 ----------
    def test_eyebrow_text_consumes_part_tone(self):
        # 점(::before)만이 아니라 eyebrow 글자 자체가 톤을 쓴다 — 미지정 시 --soft 폴백.
        self.assertIn('color:var(--part-tone,var(--soft))', CORE, 'eyebrow 글자색')

    def test_agenda_label_consumes_part_tone(self):
        # 점·번호만이 아니라 항목 라벨(.rm-h) 글자도 톤을 쓴다 — 미지정 시 --ink 폴백.
        self.assertIn('var(--part-tone,var(--ink))', AGENDA, '아젠다 라벨색')

    def test_divider_top_tone_line(self):
        # 파트 구분 장 위쪽 6px 톤 선 — 톤이 있을 때만(::before + data-part-tone 계약).
        sel = '.slide:is([data-archetype="part-divider"],[data-variant="part-divider"])[data-part-tone]::before'
        self.assertIn(sel, COMPONENTS, '구분 장 상단 톤 선 선택자')
        self.assertIn('height:6px;background:var(--part-tone)', COMPONENTS, '6px 톤 선')

    # ---------- P4 무드 장치 ----------
    def test_divider_tone_wash(self):
        # 라이트 파트 구분 장 배경을 톤 6% + 종이로 옅게 — 다크·주황은 제외.
        self.assertIn('color-mix(in srgb,var(--part-tone) 6%,var(--paper))', COMPONENTS, '톤 색면')
        self.assertIn(':not(.dark):not(.orange)', COMPONENTS, '전면 장은 색면 제외')

    def test_dots_bg_texture(self):
        # 점 격자 텍스처 — radial-gradient 점 패턴 전용(워시 그라데이트가 아니다).
        self.assertIn('.dots-bg{', COMPONENTS)
        self.assertIn('radial-gradient(circle,', COMPONENTS)

    def test_verdict_banner_variant(self):
        # 마무리 선언 배너 — data-variant="banner", 단색 색면, 그라데이션 없음.
        self.assertIn('data-variant="banner"', VERDICT)
        banner = VERDICT.split('data-variant="banner"', 1)[1].split('</section>')[0]
        self.assertNotIn('gradient', banner, '배너 색면에 그라데이션 금지')
        self.assertIn('background:var(--part-tone,var(--accent))', banner, '단색 색면(파트 톤 또는 accent)')

    # ---------- 계약: data-tone 미지정 시 폴백 그대로 ----------
    def test_untoned_fallbacks_unchanged(self):
        # 새 소비처가 모두 var(--part-tone,기존색) 꼴 — --part-tone 이 없으면 기존 색 그대로.
        for css, frag in ((CORE, 'var(--part-tone,var(--soft))'),
                          (CORE, 'var(--part-tone,currentColor)'),
                          (AGENDA, 'var(--part-tone,var(--ink))')):
            self.assertIn(frag, css)
        # 색면·톤 선은 data-part-tone 속성 자체가 없으면 선택되지 않는다(선택자 계약).
        self.assertIn('[data-part-tone]::before', COMPONENTS)
        self.assertIn('[data-part-tone]:not(.dark):not(.orange)', COMPONENTS)


class Propagation(unittest.TestCase):
    def test_propagates_until_next_divider(self):
        html = slides(
            '<section class="slide" data-archetype="cover"></section>',
            '<section class="slide dark" data-archetype="part-divider" data-tone="3"><p>1</p></section>',
            '<section class="slide" data-archetype="statement"><p>a</p></section>',
            '<section class="slide" data-archetype="statement"><p>b</p></section>',
            '<section class="slide dark" data-archetype="part-divider" data-tone="5"><p>2</p></section>',
            '<section class="slide" data-archetype="statement"><p>c</p></section>')
        out = propagate_part_tones(html)
        self.assertEqual(out.count('data-part-tone="3"'), 3, '파트1 구분 장 자신 + 본문 2장')
        self.assertEqual(out.count('data-part-tone="5"'), 2, '파트2 구분 장 자신 + 본문 1장')
        # 구분 장 자신의 data-tone 은 건드리지 않는다
        self.assertIn('data-tone="3"', out)
        self.assertIn('data-tone="5"', out)

    def test_toneless_divider_breaks_chain(self):
        html = slides(
            '<section class="slide dark" data-archetype="part-divider" data-tone="2"><p>1</p></section>',
            '<section class="slide" data-archetype="statement"><p>a</p></section>',
            '<section class="slide dark" data-archetype="part-divider"><p>2</p></section>',
            '<section class="slide" data-archetype="statement"><p>b</p></section>')
        out = propagate_part_tones(html)
        # 파트1 구분 장 자신 + 본문 a 만 톤을 갖고, 톤 없는 구분 장과 그 뒤 본문 b 는 없다
        self.assertEqual(out.count('data-part-tone='), 2, '톤 없는 구분 장에서 전파가 끊긴다')
        self.assertNotIn('data-part-tone', out.split('<p>b</p>')[0].rsplit('<section', 1)[1])

    def test_author_part_tone_respected(self):
        html = slides(
            '<section class="slide dark" data-archetype="part-divider" data-tone="2"><p>1</p></section>',
            '<section class="slide" data-archetype="statement" data-part-tone="7"><p>a</p></section>',
            '<section class="slide" data-archetype="statement"><p>b</p></section>')
        out = propagate_part_tones(html)
        self.assertIn('data-part-tone="7"', out, '저작자가 단 톤은 유지')
        self.assertEqual(out.count('data-part-tone="2"'), 2, '구분 장 자신 + 나머지는 전파 값')

    def test_no_tone_anywhere_returns_unchanged(self):
        html = slides(
            '<section class="slide" data-archetype="cover"></section>',
            '<section class="slide dark" data-archetype="part-divider"><p>1</p></section>',
            '<section class="slide" data-archetype="statement"><p>a</p></section>')
        self.assertEqual(propagate_part_tones(html), html)

    def test_variant_attr_also_recognized(self):
        html = slides(
            '<section class="slide dark" data-archetype="mapping" data-variant="part-divider" data-tone="4"><p>1</p></section>',
            '<section class="slide" data-archetype="statement"><p>a</p></section>')
        out = propagate_part_tones(html)
        self.assertIn('data-part-tone="4"', out)


class ToneContrast(unittest.TestCase):
    """classic 테마에서 파트 톤이 --paper 위 4.5:1 이상인지 — check_deck 의 색 해석기로 직접 잰다."""

    @classmethod
    def setUpClass(cls):
        # parse_tokens 는 첫 :root 블록만 읽는다 — 톤 블록까지 전부 모으고,
        # 값 안의 var(--x) 참조가 풀리도록 '--' 접두 키도 함께 둔다.
        env = {}
        for body in re.findall(r":root\{([^}]*)\}", TOKENS, re.S):
            for k, v in re.findall(r"--([\w-]+)\s*:\s*([^;]+)", body):
                env[k.strip()] = v.strip()
        env.update(check_deck.parse_theme_tokens(THEMES).get('classic', {}))
        env.update({'--' + k: v for k, v in list(env.items())})
        cls.env = env

    def test_all_tones_meet_4_5(self):
        paper = check_deck.parse_color_value('var(--paper)', self.env)
        self.assertIsNotNone(paper)
        for n in range(1, 8):
            tone = check_deck.parse_color_value(f'var(--tone-{n})', self.env)
            self.assertIsNotNone(tone, f'--tone-{n} 해석 실패')
            r = check_deck.contrast_ratio(tone, paper)
            self.assertGreaterEqual(r, 4.5, f'--tone-{n} 대비 {r:.2f} < 4.5')


if __name__ == '__main__':
    unittest.main()
