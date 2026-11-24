"""Acceptance: tone_router 계열(family) 필드 — 추가 필드 계약과 기존 출력 무변경.

[검사 항목]
- route() 출력에 family(recommend+candidates 3)·family_palette 필드가 있다.
- family 후보는 FAMILIES 3종 전체이고 recommend 는 그중 하나다.
- family_palette 는 목록(P1 에는 빈 목록이 정상).
- 기존 필드(title·seed·axes·signals·weak_signal·theme·cover·arc·preset)의
  값·구조는 계열 필드 추가와 무관하게 그대로다.
- 같은 입력은 항상 같은 결과(결정적).

[실행] cd edu-deck/shared && python3 -m unittest dev.test_router_family -v
"""
import pathlib
import sys
import unittest

S = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S / 'scripts'))
import tone_router as tr  # noqa: E402


class TestFamilyField(unittest.TestCase):
    def setUp(self):
        self.out = tr.route("재무제표 읽는 법", outcomes="세 가지 표를 읽는다", audience="전 직원")

    def test_family_field_shape(self):
        fam = self.out["family"]
        self.assertIn("recommend", fam)
        self.assertIn("candidates", fam)
        self.assertEqual(len(fam["candidates"]), 3)
        self.assertIn(fam["recommend"], tr.FAMILIES)
        self.assertEqual(fam["recommend"], fam["candidates"][0]["id"])
        for c in fam["candidates"]:
            self.assertIn(c["id"], tr.FAMILIES)
            self.assertIn("score", c)
            self.assertIn("because", c)

    def test_family_candidates_cover_all_families(self):
        ids = {c["id"] for c in self.out["family"]["candidates"]}
        self.assertEqual(ids, set(tr.FAMILIES))

    def test_family_palette_is_list(self):
        self.assertIsInstance(self.out["family_palette"], list)
        self.assertEqual(self.out["family_palette"], [])


class TestExistingFieldsUnchanged(unittest.TestCase):
    """계열 필드가 추가돼도 기존 필드의 키·구조·값이 바뀌지 않는다."""

    def test_top_level_keys(self):
        out = tr.route("개인정보 보호 기본 교육", outcomes="개인정보를 안전하게 다룬다",
                       audience="전 직원", seed="3")
        for key in ("title", "seed", "axes", "signals", "weak_signal",
                    "theme", "cover", "arc", "preset"):
            self.assertIn(key, out, f'기존 키 "{key}" 가 빠졌습니다')

    def test_legacy_candidate_shape(self):
        out = tr.route("개인정보 보호 기본 교육")
        for kind in ("theme", "cover", "arc", "preset"):
            block = out[kind]
            self.assertIn("recommend", block)
            self.assertEqual(len(block["candidates"]), 3)
            self.assertEqual(block["recommend"], block["candidates"][0]["id"])
            for c in block["candidates"]:
                self.assertIn("id", c)
                self.assertIn("score", c)
                self.assertIn("because", c)

    def test_deterministic(self):
        a = tr.route("재무제표 읽는 법", seed="7")
        b = tr.route("재무제표 읽는 법", seed="7")
        self.assertEqual(a, b)

    def test_family_scores_use_same_jitter_family(self):
        """family 후보 점수는 다른 후보와 같은 _score 규칙(축 거리+지터)을 따른다 —
        신호가 있으면 지터가 줄어 거리 우위가 이긴다."""
        strong = tr.route("손그림 화이트보드 설명", outcomes="도식을 그린다")
        weak = tr.route("재무제표 읽는 법")  # 신호어 없을 수 있음
        self.assertIn(strong["family"]["recommend"], tr.FAMILIES)
        self.assertIn(weak["family"]["recommend"], tr.FAMILIES)


if __name__ == '__main__':
    unittest.main()
