"""Tests for backend selection wiring (env → platforms → pipeline).

Stdlib unittest + mock only; no network. Covers credential resolution priority,
registry mapping per backend, and that scrape_all routes through the Apify
fetchers (reaching run_actor_sync with the token) while skipping enrichment.
"""

import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # scripts/

from lib import env, pipeline, platforms  # noqa: E402
from lib import apify_fetchers as af  # noqa: E402

NOPATH = pathlib.Path("/nonexistent/.env")  # force env-var-only resolution


class ActiveBackendTest(unittest.TestCase):
    def test_apify_when_token_present(self):
        with mock.patch.dict(os.environ, {"APIFY_TOKEN": "tok"}, clear=True):
            self.assertEqual(env.active_backend(NOPATH), ("apify", "tok"))

    def test_none_when_no_credential(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(env.active_backend(NOPATH), (None, ""))


class RegistriesForTest(unittest.TestCase):
    def test_apify_profile_only(self):
        reg = platforms.registries_for("apify")
        self.assertIs(reg["profile"], af.PROFILE_FETCHERS)
        self.assertEqual(reg["post"], {})
        self.assertEqual(reg["comment"], {})
        self.assertEqual(reg["transcript"], {})
        # The tracked platforms are present on the Apify profile registry.
        self.assertEqual(set(reg["profile"]), {"x", "youtube", "linkedin"})

    def test_unknown_backend_raises(self):
        with self.assertRaises(ValueError):
            platforms.registries_for("nonexistent")


class ScrapeAllRoutingTest(unittest.TestCase):
    def test_apify_backend_routes_to_run_actor_sync_and_skips_enrichment(self):
        calls = {}

        def fake_run(actor_id, run_input, token):
            calls["actor"] = actor_id
            calls["token"] = token
            return [{
                "fullText": "hi", "url": "https://x.com/NASA/status/1",
                "author": {"userName": "NASA"}, "createdAt": "Thu Jun 18 16:15:01 +0000 2026",
                "likeCount": 5, "retweetCount": 1, "replyCount": 0,
                "quoteCount": 0, "bookmarkCount": 0, "viewCount": 9,
            }]

        with mock.patch.object(af.apify, "run_actor_sync", fake_run):
            results, errors = pipeline.scrape_all(
                {"x": ["NASA"]}, "TOK", since=None, backend="apify"
            )

        self.assertEqual(errors, [])
        self.assertEqual(calls["actor"], af.X_ACTOR)
        self.assertEqual(calls["token"], "TOK")  # credential threaded through
        posts = results["x"]["NASA"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["platform"], "x")
        # No comment/transcript registry for Apify v1 → no enrichment keys.
        self.assertNotIn("comments", posts[0])
        self.assertNotIn("transcript", posts[0])

    def test_unknown_platform_recorded_as_error(self):
        with mock.patch.object(af.apify, "run_actor_sync", lambda *a: []):
            results, errors = pipeline.scrape_all(
                {"myspace": ["tom"]}, "TOK", backend="apify"
            )
        self.assertTrue(any("Unknown platform" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
