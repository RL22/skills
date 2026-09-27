#!/usr/bin/env python3
"""Tests for `cli.py list-engagement --json` (machine-readable engagement queue)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline_db import NetworkDatabase
from schemas import DMThread, EngagementAction, Post

KEYS = {
    "action_id", "target_type", "target_id", "target_url", "action_type", "reaction_type",
    "status", "rubric_score", "draft_content", "rationale", "created_at", "counterparty_name",
}


class ListEngagementJsonTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "t.duckdb")
        db = NetworkDatabase(db_path=self.db_path)
        db.upsert_dm_thread(DMThread(thread_id="thr1", participant_name="Dana DM"))
        db.upsert_posts([Post(post_id="7000000000000000001",
                              post_url="https://www.linkedin.com/feed/update/urn:li:activity:7000000000000000001/",
                              author_name="Paula Post", text="hello")])
        db.upsert_engagement_action(EngagementAction(
            action_id="a_dm", target_type="dm", target_id="thr1", action_type="message",
            draft_content="hi", rubric_score=50.0, rationale="r"))
        db.upsert_engagement_action(EngagementAction(
            action_id="a_post", target_type="post", target_id="7000000000000000001",
            action_type="comment", draft_content="nice", rubric_score=70.0, status="approved"))
        db.upsert_engagement_action(EngagementAction(
            action_id="a_missing", target_type="post", target_id="999", action_type="like",
            reaction_type="insightful", rubric_score=10.0))
        db.close()

    def run_cli(self, *extra):
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "cli.py"), "list-engagement", "--json", "--db", self.db_path, *extra],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_keys_and_counterparties(self):
        rows = {r["action_id"]: r for r in self.run_cli()}
        self.assertEqual(set(rows), {"a_dm", "a_post", "a_missing"})
        for r in rows.values():
            self.assertEqual(set(r), KEYS)
        self.assertEqual(rows["a_dm"]["counterparty_name"], "Dana DM")
        self.assertEqual(rows["a_post"]["counterparty_name"], "Paula Post")
        self.assertIsNone(rows["a_missing"]["counterparty_name"])
        self.assertEqual(rows["a_missing"]["reaction_type"], "insightful")
        self.assertIsInstance(rows["a_dm"]["created_at"], str)

    def test_status_filter(self):
        rows = self.run_cli("--status", "approved")
        self.assertEqual([r["action_id"] for r in rows], ["a_post"])
        self.assertEqual(self.run_cli("--status", "rejected"), [])

    def test_other_filters(self):
        self.assertEqual({r["action_id"] for r in self.run_cli("--target-type", "dm")}, {"a_dm"})
        self.assertEqual({r["action_id"] for r in self.run_cli("--min-score", "60")}, {"a_post"})
        self.assertEqual(len(self.run_cli("--limit", "1")), 1)


if __name__ == "__main__":
    unittest.main()
