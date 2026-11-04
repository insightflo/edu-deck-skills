"""Negative controls for the auditor: bad color/timing, clipped text and low contrast."""

import importlib
import unittest
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
audit = importlib.import_module("visual_motion_check")
source_findings, AUDIT_JS, launch = audit.source_findings, audit.AUDIT_JS, audit.launch


class AuditControls(unittest.TestCase):
    def test_raw_colors_and_motion_fail(self):
        findings = source_findings(
            "fixture.css", ".x{color:#abc;transition:opacity 125ms ease}"
        )
        self.assertEqual(
            {f["kind"] for f in findings}, {"non-token-color", "non-token-motion"}
        )

    def test_token_references_pass(self):
        self.assertEqual(
            source_findings(
                "fixture.css",
                ".x{color:var(--ink);transition:opacity var(--m2) var(--e-out)}",
            ),
            [],
        )

    def test_browser_negative_controls(self):
        with sync_playwright() as pw:
            browser = launch(pw)
            page = browser.new_page(viewport={"width": 800, "height": 600})
            page.set_content(
                """<style>body{margin:0}.slide{width:800px;height:600px;background:white;color:black;position:relative}p{font:16px Arial;margin:0}.bad{color:white}.clip{position:absolute;left:790px;white-space:nowrap}</style><section class="slide active"><p>Readable text</p><p class="bad">Invisible text</p><p class="clip">Outside slide</p><svg width="100" height="50"><path d="M0 10 L100 10" stroke="white" stroke-width="2"/></svg></section>"""
            )
            result = page.evaluate(AUDIT_JS)
            self.assertTrue(
                any(
                    f["kind"] == "contrast" and f["text"] == "Invisible text"
                    for f in result["findings"]
                )
            )
            self.assertTrue(
                any(
                    f["kind"] == "overflow" and f["text"] == "Outside slide"
                    for f in result["findings"]
                )
            )
            self.assertTrue(
                any(f["kind"] == "graphic-contrast" for f in result["findings"])
            )
            good = next(x for x in result["texts"] if x["text"] == "Readable text")
            self.assertAlmostEqual(good["ratio"], 21, places=2)
            browser.close()


if __name__ == "__main__":
    unittest.main()
