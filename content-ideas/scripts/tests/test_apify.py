"""Tests for the Apify run-sync client (lib/apify.py).

Stdlib unittest + mock only — no pytest, no network. Run with:
    python3 -m unittest discover -s scripts/tests
from the skill root, or:
    python3 -m unittest tests.test_apify
from scripts/.
"""

import json
import pathlib
import sys
import unittest
import urllib.error
import warnings
from unittest import mock

# CPython 3.14 surfaces a spurious ResourceWarning when a test-built HTTPError is
# GC'd at shutdown; our client never reads the error body. Test-only suppression.
warnings.filterwarnings("ignore", category=ResourceWarning)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # scripts/

from lib import apify  # noqa: E402


class FakeResp:
    """Minimal context-manager stand-in for an http response."""

    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(code):
    return urllib.error.HTTPError("http://x", code, "err", {}, None)


class RunActorSyncTest(unittest.TestCase):
    def test_success_returns_dataset_list_and_builds_request(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = req.data
            captured["timeout"] = timeout
            return FakeResp([{"id": 1}, {"id": 2}])

        with mock.patch.object(apify.urllib.request, "urlopen", fake_urlopen):
            out = apify.run_actor_sync(
                "apidojo/tweet-scraper", {"twitterHandles": ["x"]}, "TOK", timeout=42
            )

        self.assertEqual(out, [{"id": 1}, {"id": 2}])
        # Actor id encoded with '~', correct endpoint, token in query.
        self.assertIn("/v2/acts/apidojo~tweet-scraper/run-sync-get-dataset-items", captured["url"])
        self.assertIn("token=TOK", captured["url"])
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(json.loads(captured["body"]), {"twitterHandles": ["x"]})
        self.assertEqual(captured["timeout"], 42)

    def test_no_token_short_circuits(self):
        with mock.patch.object(apify.urllib.request, "urlopen") as m:
            self.assertEqual(apify.run_actor_sync("a/b", {}, ""), [])
            m.assert_not_called()

    def test_object_response_treated_as_error(self):
        with mock.patch.object(
            apify.urllib.request, "urlopen", lambda req, timeout=None: FakeResp({"error": "nope"})
        ):
            self.assertEqual(apify.run_actor_sync("a/b", {}, "TOK"), [])

    def test_terminal_4xx_does_not_retry(self):
        calls = {"n": 0}

        def fake_urlopen(req, timeout=None):
            calls["n"] += 1
            raise _http_error(400)

        with mock.patch.object(apify.urllib.request, "urlopen", fake_urlopen):
            self.assertEqual(apify.run_actor_sync("a/b", {}, "TOK"), [])
        self.assertEqual(calls["n"], 1)

    def test_429_retries_then_succeeds(self):
        responses = [_http_error(429), FakeResp([{"ok": True}])]

        def fake_urlopen(req, timeout=None):
            r = responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        with mock.patch.object(apify.urllib.request, "urlopen", fake_urlopen), \
                mock.patch.object(apify.time, "sleep"):
            out = apify.run_actor_sync("a/b", {}, "TOK")
        self.assertEqual(out, [{"ok": True}])

    def test_gives_up_after_max_retries(self):
        def always_429(req, timeout=None):
            raise _http_error(429)

        with mock.patch.object(apify.urllib.request, "urlopen", always_429), \
                mock.patch.object(apify.time, "sleep"):
            self.assertEqual(apify.run_actor_sync("a/b", {}, "TOK"), [])


if __name__ == "__main__":
    unittest.main()
