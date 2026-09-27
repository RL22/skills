"""Tests for assemble_feed.py — deterministic Posts-tab assembly.

Stdlib unittest only — no pytest, no network. Run with:
    python3 -m unittest discover -s scripts/tests
from the skill root, or:
    python3 -m unittest tests.test_assemble_feed
from scripts/.
"""

import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import assemble_feed as af  # noqa: E402


def _scrape():
    """Two accounts: one with a clear 2σ outlier among a realistic baseline,
    one single-post account. (A handful of posts can't produce a 2σ outlier —
    population std is inflated by the outlier itself — so the baseline needs
    enough normal posts for the spike to actually clear the threshold.)"""
    baseline_posts = [
        {"text": f"boring post {i}", "url": f"https://x.com/g/{i}", "author": "Greg Isenberg",
         "date": "2026-06-15", "platform": "x", "score": 100 + i, "relevance": 0.1,
         "engagement": {"likes": 80 + i, "views": 1000 + i}}
        for i in range(9)
    ]
    viral = {"text": "VIRAL outlier post that crushed the baseline by a mile",
             "url": "https://x.com/g/v", "author": "Greg Isenberg", "date": "2026-06-16",
             "platform": "x", "score": 2000, "relevance": 0.9, "outlier": True,
             "engagement": {"likes": 1800, "views": 50000, "bookmarks": 200}}
    return {
        "results": {
            "x": {
                "gregisenberg": baseline_posts + [viral],
            },
            "youtube": {
                "@solo": [
                    {"text": "the only video", "url": "https://youtube.com/watch?v=1", "author": "Solo",
                     "date": "2026-06-14", "platform": "youtube", "score": 500, "relevance": 0.5,
                     "engagement": {"views": 5000, "likes": 300}},
                ]
            },
        },
        "errors": [],
    }


class TestAssembleFeed(unittest.TestCase):
    def test_carries_every_scraped_post(self):
        feed = af.assemble(_scrape())
        self.assertEqual(feed["meta"]["postCount"], 11)
        self.assertEqual(len(feed["posts"]), 11)

    def test_meta_counts(self):
        meta = af.assemble(_scrape(), recency="last 7 days")["meta"]
        self.assertEqual(meta["trackedAccountCount"], 2)
        self.assertEqual(meta["platformCount"], 2)
        self.assertEqual(set(meta["platforms"]), {"x", "youtube"})
        self.assertEqual(meta["outlierCount"], 1)
        self.assertEqual(meta["recencyWindow"], "last 7 days")

    def test_outlier_gets_zscore_and_why(self):
        posts = af.assemble(_scrape())["posts"]
        viral = next(p for p in posts if "VIRAL" in p["text"])
        self.assertIn("zScore", viral)
        self.assertGreater(viral["zScore"], 2.0)
        self.assertIn("why", viral)
        self.assertEqual(viral["performanceDirection"], "up")

    def test_non_outlier_has_no_zscore(self):
        posts = af.assemble(_scrape())["posts"]
        boring = next(p for p in posts if p["text"] == "boring post 0")
        self.assertNotIn("zScore", boring)

    def test_sortvalue_is_engagement_total(self):
        posts = af.assemble(_scrape())["posts"]
        viral = next(p for p in posts if "VIRAL" in p["text"])
        self.assertEqual(viral["sortValue"], 1800 + 50000 + 200)
        self.assertEqual(viral["engagement"]["total"], 52000)

    def test_required_fields_present(self):
        posts = af.assemble(_scrape())["posts"]
        for p in posts:
            for key in ("id", "text", "url", "handle", "displayName", "platform",
                        "engagement", "sortValue", "timestamp"):
                self.assertIn(key, p, f"{key} missing from {p['id']}")
        ids = [p["id"] for p in posts]
        self.assertEqual(len(ids), len(set(ids)), "post ids must be unique")

    def test_single_post_account_no_false_outlier(self):
        posts = af.assemble(_scrape())["posts"]
        solo = next(p for p in posts if p["platform"] == "youtube")
        self.assertNotIn("zScore", solo)

    def test_clip_text_truncates_on_word_boundary(self):
        out = af.clip_text("word " * 100, limit=50)
        self.assertLessEqual(len(out), 51)
        self.assertFalse(out.endswith("wor"))

    def test_handle_stripped_and_id_slugged(self):
        posts = af.assemble(_scrape())["posts"]
        yt = next(p for p in posts if p["platform"] == "youtube")
        self.assertEqual(yt["handle"], "solo")
        self.assertTrue(yt["id"].startswith("youtube_solo_"))

    def test_empty_results_handled(self):
        feed = af.assemble({"results": {}})
        self.assertEqual(feed["meta"]["postCount"], 0)
        self.assertEqual(feed["posts"], [])


if __name__ == "__main__":
    unittest.main()
