# -*- coding: utf-8 -*-
"""verify_sources --quotes / --ban (kodoc round2 9번 이식) 테스트."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import verify_sources as vs  # noqa: E402

DECK_HTML = """<!doctype html><html><body><div id="stage">
<section class="slide"><h2>명령 실습</h2>
<div class="code"><div class="code-head"><span>터미널</span><button class="code-copy">복사</button></div>
<pre><span class="p">$ </span>devin run --mode check\n<span class="out">done</span></pre></div></section>
<section class="slide"><p>구 명칭 OldTeam</p></section>
</div></body></html>"""

RESEARCH = """F01
- 주장: x
- 값: v
- 출처: 파일
- 확인: 미확인
"""


class TestQuotesBan(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.html = self.tmp / "deck.html"
        self.html.write_text(DECK_HTML, encoding="utf-8")
        self.research = self.tmp / "research.md"
        self.research.write_text(RESEARCH, encoding="utf-8")
        (self.tmp / "deck.json").write_text(json.dumps({"output": "deck.html"}), encoding="utf-8")

    def _run(self, argv):
        return vs.main([str(self.tmp)] + argv)

    def test_quotes_match_and_missing(self):
        # 일치하는 것: .code pre 안에 그대로 있음 (research 원문에도)
        self.research.write_text(RESEARCH + "devin run --mode check\n", encoding="utf-8")
        q = self.tmp / "q.json"
        q.write_text(json.dumps({"명령": "devin run --mode check"}, ensure_ascii=False), encoding="utf-8")
        rc = self._run(["--quotes", str(q)])
        self.assertEqual(rc, 0)
        # 원문에는 없는 글 → 불일치 ERROR
        q.write_text(json.dumps({"틀린글": "devin run --mode check 완전 다름"}, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self._run(["--quotes", str(q)]), 1)
        # 원문엔 있지만 덱에 안 실린 글 → 빠짐 ERROR
        q.write_text(json.dumps({"빠진글": "x"}, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self._run(["--quotes", str(q)]), 1)

    def test_quotes_needs_html_and_src(self):
        # quotes 파일이 없으면 실행 불가(2)
        self.assertEqual(self._run(["--quotes", str(self.tmp / "없음.json")]), 2)
        # deck.json 없는 폴더 → HTML 미결정으로 ERROR(1)
        (self.tmp / "deck.json").unlink()
        q = self.tmp / "q.json"
        q.write_text('{"a": "b"}', encoding="utf-8")
        self.assertEqual(self._run(["--quotes", str(q)]), 1)
        (self.tmp / "deck.json").write_text(json.dumps({"output": "deck.html"}), encoding="utf-8")

    def test_ban_word(self):
        deck = self.tmp / "deck.json"
        deck.write_text(json.dumps({"output": "deck.html"}), encoding="utf-8")
        # 'OldTeam'이 2번 장에 남음 → ERROR
        self.assertEqual(self._run(["--ban", "OldTeam"]), 1)
        # 없는 낱말 → 통과
        self.assertEqual(self._run(["--ban", "NoSuchWord"]), 0)


if __name__ == "__main__":
    unittest.main()
