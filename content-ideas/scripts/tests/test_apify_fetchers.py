"""Tests for the Apify per-platform normalizers (lib/apify_fetchers.py).

Fixtures are minimal items using the *real* actor field names captured from live
runs 2026-06-18. We mock apify.run_actor_sync so there's no network, and assert
both the actor input we build and the normalized post — including that the
engagement keys exactly match what lib/scoring.py reads per platform.
"""

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # scripts/

from lib import apify_fetchers as af  # noqa: E402
from lib import scoring  # noqa: E402

# Engagement keys lib/scoring.py actually reads, per platform.
SCORER_KEYS = {
    "x": {"likes", "reposts", "replies", "quotes", "bookmarks"},
    "youtube": {"views", "likes", "comments"},
    "linkedin": {"likes", "comments", "shares"},
}

X_ITEM = {
    "fullText": "summer solstice", "url": "https://x.com/NASA/status/1",
    "author": {"userName": "NASA"}, "createdAt": "Thu Jun 18 16:15:01 +0000 2026",
    "likeCount": 4922, "retweetCount": 1101, "replyCount": 245, "quoteCount": 53,
    "bookmarkCount": 198, "viewCount": 236165,
}
YT_ITEM = {
    "title": "WWDC 2026", "url": "https://www.youtube.com/watch?v=_gCXmKjDecU",
    "channelName": "Marques Brownlee", "date": "2026-06-09T05:48:41.000Z",
    "viewCount": 3912031, "likes": 112000, "commentsCount": 4200,
    "duration": "11:30", "text": "video description here",
}
LI_ITEM = {
    "content": "New Azure milestone.", "linkedinUrl": "https://www.linkedin.com/posts/satyanadella_x-activity-1",
    "author": {"name": "Satya Nadella", "publicIdentifier": "satyanadella"},
    "postedAt": {"date": "2026-06-16T23:01:08.318Z", "timestamp": 1781650868318},
    "engagement": {"likes": 1673, "comments": 117, "shares": 137},
}


class NormalizeContractTest(unittest.TestCase):
    def _run(self, fetch, handle, item):
        captured = {}

        def fake(actor_id, run_input, token):
            captured["actor"] = actor_id
            captured["input"] = run_input
            captured["token"] = token
            return [item]

        with mock.patch.object(af.apify, "run_actor_sync", fake):
            posts = fetch(handle, "TOK")
        self.assertEqual(len(posts), 1)
        return posts[0], captured

    def _assert_contract(self, post, platform):
        self.assertEqual(set(post.keys()) >= {"text", "url", "author", "date", "platform", "engagement"}, True)
        self.assertEqual(post["platform"], platform)
        # Every key the scorer reads is present and an int.
        for key in SCORER_KEYS[platform]:
            self.assertIn(key, post["engagement"], f"{platform} missing engagement.{key}")
            self.assertIsInstance(post["engagement"][key], int)
        # The normalized post actually scores without error.
        self.assertIsInstance(scoring.score_engagement(post), (int, float))

    def test_x(self):
        post, cap = self._run(af.x_fetch_profile, "NASA", X_ITEM)
        self.assertEqual(cap["actor"], af.X_ACTOR)
        self.assertEqual(cap["input"]["startUrls"], ["https://twitter.com/NASA"])
        self._assert_contract(post, "x")
        self.assertEqual(post["author"], "NASA")
        self.assertEqual(post["date"], "2026-06-18")
        self.assertEqual(post["engagement"]["likes"], 4922)
        self.assertEqual(post["engagement"]["reposts"], 1101)

    def test_youtube(self):
        post, cap = self._run(af.yt_fetch_profile, "@mkbhd", YT_ITEM)
        self.assertEqual(cap["actor"], af.YT_ACTOR)
        self.assertEqual(cap["input"]["startUrls"], [{"url": "https://www.youtube.com/@mkbhd/videos"}])
        self._assert_contract(post, "youtube")
        self.assertEqual(post["author"], "Marques Brownlee")
        self.assertEqual(post["date"], "2026-06-09")
        self.assertEqual(post["engagement"], {"views": 3912031, "likes": 112000, "comments": 4200})

    def test_linkedin(self):
        post, cap = self._run(af.li_fetch_profile, "satyanadella", LI_ITEM)
        self.assertEqual(cap["actor"], af.LI_ACTOR)
        self.assertEqual(cap["input"]["targetUrls"], ["https://www.linkedin.com/in/satyanadella/"])
        self._assert_contract(post, "linkedin")
        self.assertEqual(post["author"], "Satya Nadella")
        self.assertEqual(post["date"], "2026-06-16")
        self.assertEqual(post["engagement"], {"likes": 1673, "comments": 117, "shares": 137})

    def test_linkedin_company_and_url_targets(self):
        captured = {}

        def fake(actor_id, run_input, token):
            captured.setdefault("urls", []).append(run_input["targetUrls"][0])
            return []

        with mock.patch.object(af.apify, "run_actor_sync", fake):
            af.li_fetch_profile("company/microsoft", "TOK")
            af.li_fetch_profile("https://www.linkedin.com/in/custom/", "TOK")
        self.assertEqual(captured["urls"], [
            "https://www.linkedin.com/company/microsoft/",
            "https://www.linkedin.com/in/custom/",
        ])


class SentinelAndGuardTest(unittest.TestCase):
    def test_noresults_sentinel_dropped(self):
        with mock.patch.object(af.apify, "run_actor_sync", lambda *a: [{"noResults": True}]):
            self.assertEqual(af.x_fetch_profile("NASA", "TOK"), [])

    def test_missing_counts_become_zero(self):
        with mock.patch.object(af.apify, "run_actor_sync", lambda *a: [{"linkedinUrl": "u"}]):
            post = af.li_fetch_profile("u", "TOK")[0]
        self.assertEqual(post["engagement"], {"likes": 0, "comments": 0, "shares": 0})
        self.assertIsNone(post["date"])

    def test_youtube_url_handle_passthrough(self):
        captured = {}

        def fake(actor_id, run_input, token):
            captured["input"] = run_input
            return []

        with mock.patch.object(af.apify, "run_actor_sync", fake):
            af.yt_fetch_profile("https://www.youtube.com/@mkbhd/videos", "TOK")
        self.assertEqual(captured["input"]["startUrls"], [{"url": "https://www.youtube.com/@mkbhd/videos"}])


if __name__ == "__main__":
    unittest.main()
