# -*- coding: utf-8 -*-
"""final_gate.py 3케이스 — 통과·차단(입력 변조/미검토)·실행불가."""
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "consulting-deck" / "checks"))
import final_gate as fg  # noqa: E402

SRC_DECK = ROOT / "examples" / "consulting-demo" / "it-cost"


def fresh_deck(tmp: Path) -> Path:
    d = tmp / "deck"
    d.mkdir()
    for name in ("deck.json", "src", "charts"):
        p = SRC_DECK / name
        if p.is_dir():
            shutil.copytree(p, d / name)
        elif p.is_file():
            shutil.copy2(p, d / name)
    return d


@unittest.skipUnless(SRC_DECK.is_dir(), "it-cost 데모 없음")
class TestFinalGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.deck = fresh_deck(self.tmp)

    def _review(self, deck: Path):
        out = deck / json.loads((deck / "deck.json").read_text())["output"]
        data = out.read_bytes() if out.is_file() else b""
        (deck / "qa").mkdir(exist_ok=True)
        (deck / "qa" / "human-review.json").write_text(json.dumps({
            "reviewer": "tester",
            "items": {i: True for i in fg.REVIEW_ITEMS},
            "open_items": [],
            "output_sha256": hashlib.sha256(data).hexdigest(),
        }), encoding="utf-8")

    def test_pass(self):
        self.assertEqual(fg.main(["check", str(self.deck)]), 0)
        self._review(self.deck)
        self.assertEqual(fg.main(["decide", str(self.deck)]), 0)

    def test_fail_tampered_and_unreviewed(self):
        self.assertEqual(fg.main(["check", str(self.deck)]), 0)
        # check 이후 입력 변조
        src = next((self.deck / "src").glob("*.html"))
        src.write_text(src.read_text(encoding="utf-8") + "<!--tamper-->", encoding="utf-8")
        self.assertEqual(fg.main(["decide", str(self.deck)]), 1)
        v = json.loads((self.deck / "qa" / "final-gate.json").read_text())
        self.assertEqual(v["verdict"], "FAIL")
        self.assertTrue(any("입력이 바뀌" in f for f in v["failures"]))
        self.assertTrue(any("사람 검토" in f for f in v["failures"]))

    def test_cannot_run(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        self.assertEqual(fg.main(["check", str(empty)]), 2)
        # decide without prior check → 실패(1)
        self._review(self.deck)
        self.assertEqual(fg.main(["decide", str(self.deck)]), 1)


if __name__ == "__main__":
    unittest.main()
