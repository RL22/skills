"""Tests for scripts/connections.py. All people, handles and URNs below are invented."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import connections as C  # noqa: E402
from pipeline_db import NetworkDatabase  # noqa: E402
from schemas import LinkedInContact  # noqa: E402


def voyager_payload() -> dict:
    def prof(i, first, last, headline, pub):
        d = {
            "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
            "entityUrn": f"urn:li:fsd_profile:ACoAATEST{i:04d}",
            "firstName": first, "lastName": last, "publicIdentifier": pub,
        }
        if headline is not None:
            d["headline"] = headline
        return d

    def conn(i, created):
        d = {
            "$type": "com.linkedin.voyager.dash.relationships.Connection",
            "entityUrn": f"urn:li:fsd_connection:X{i}",
            "*connectedMemberResolutionResult": f"urn:li:fsd_profile:ACoAATEST{i:04d}",
        }
        if created is not None:
            d["createdAt"] = created
        return d

    return {
        "data": {"data": {"relationshipsDashConnectionsByConnectedTime": {"*elements": []}}},
        "included": [
            prof(1, "Ada", "Testcase", "Head of Growth at Examplewidgets", "ada-testcase"),
            prof(2, "Bo", "Fixture", None, "bo-fixture"),                       # missing headline
            prof(3, "Cy", "Mockson", "Founder | Mockco", "cy-mockson"),
            prof(4, "Dee", "Dupe", "Engineer @ Dupeco", "dee-dupe"),
            conn(1, 1_700_000_000_000),
            conn(2, None),                                                       # missing connected-at
            conn(3, 1_690_000_000_000),
            conn(4, 1_680_000_000_000),
            conn(4, 1_680_000_000_000),                                          # duplicate entry
            {"$type": "com.linkedin.voyager.dash.organization.Company",          # non-connection
             "entityUrn": "urn:li:fsd_company:1", "name": "Examplewidgets"},
            {"$type": "com.linkedin.voyager.dash.feed.Update", "entityUrn": "urn:li:activity:1"},
            {"$type": "com.linkedin.voyager.dash.relationships.Connection",      # dangling ref
             "entityUrn": "urn:li:fsd_connection:X9",
             "*connectedMemberResolutionResult": "urn:li:fsd_profile:ACoAAMISSING"},
        ],
    }


class VoyagerParserTest(unittest.TestCase):
    def setUp(self):
        self.out = {c.name: c for c in C.parse_voyager_connections_json(voyager_payload())}

    def test_count_and_dedupe(self):
        self.assertEqual(set(self.out), {"Ada Testcase", "Bo Fixture", "Cy Mockson", "Dee Dupe"})

    def test_fields(self):
        ada = self.out["Ada Testcase"]
        self.assertEqual(ada.degree, "1st")
        self.assertEqual(ada.profile_url, "https://www.linkedin.com/in/ada-testcase")
        self.assertEqual(ada.current_company, "Examplewidgets")  # derived from headline
        self.assertEqual(ada.member_urn, "urn:li:fsd_profile:ACoAATEST0001")
        self.assertEqual(ada.connected_at, datetime.fromtimestamp(1_700_000_000, tz=timezone.utc))
        self.assertIsInstance(ada, LinkedInContact)

    def test_missing_headline_and_date(self):
        bo = self.out["Bo Fixture"]
        self.assertEqual(bo.headline, "")
        self.assertIsNone(bo.current_company)
        self.assertIsNone(bo.connected_at)

    def test_garbage_input(self):
        self.assertEqual(C.parse_voyager_connections_json({}), [])
        self.assertEqual(C.parse_voyager_connections_json({"included": "nope"}), [])
        self.assertEqual(C.parse_voyager_connections_json(None), [])  # type: ignore[arg-type]


class DomParserTest(unittest.TestCase):
    def cards(self):
        return [
            {"key": "ConnectionCard_20-ada-testcase", "href": "https://www.linkedin.com/in/ada-testcase/?trk=x",
             "lines": ["Ada Testcase", "Head of Growth @ Examplewidgets", "Connected on September 16, 2026", "Message"]},
            {"key": "ConnectionCard_20-bo-fixture", "href": "https://www.linkedin.com/in/bo-fixture/",
             "lines": ["Bo Fixture", "Connected on January 2, 2020", "Message"]},                # no headline
            {"key": "ConnectionCard_20-cy-mockson", "href": None,
             "lines": ["Cy Mockson", "Founder", "Connected 3 weeks ago", "Message"]},           # href from key, relative text
            {"key": "ConnectionCard_20-ada-testcase", "href": "https://www.linkedin.com/in/ada-testcase/",
             "lines": ["Ada Testcase", "Head of Growth @ Examplewidgets", "Connected on September 16, 2026"]},  # dupe
            {"key": "junk", "href": "https://www.linkedin.com/company/foo/", "lines": ["Foo Inc"]},  # non-person
            {"key": "empty", "href": "https://www.linkedin.com/in/x/", "lines": []},
        ]

    def test_parse(self):
        out = {c.name: c for c in C.parse_dom_cards(self.cards())}
        self.assertEqual(set(out), {"Ada Testcase", "Bo Fixture", "Cy Mockson"})
        ada = out["Ada Testcase"]
        self.assertEqual(ada.profile_url, "https://www.linkedin.com/in/ada-testcase")
        self.assertEqual(ada.current_company, "Examplewidgets")
        self.assertEqual(ada.connected_at, datetime(2026, 9, 16, tzinfo=timezone.utc))
        self.assertEqual(ada.connected_at_text, "Connected on September 16, 2026")
        self.assertEqual(out["Bo Fixture"].headline, "")
        cy = out["Cy Mockson"]
        self.assertIsNone(cy.connected_at)
        self.assertEqual(cy.connected_at_text, "Connected 3 weeks ago")
        self.assertEqual(cy.profile_url, "https://www.linkedin.com/in/cy-mockson")

    def test_parse_connected_at(self):
        self.assertIsNone(C.parse_connected_at(None))
        self.assertIsNone(C.parse_connected_at("Connected on Smarch 40, 2020"))
        self.assertEqual(C.parse_connected_at("Connected on March 1, 2021"), datetime(2021, 3, 1, tzinfo=timezone.utc))


class RscAndBlockTest(unittest.TestCase):
    def test_member_urns(self):
        text = (
            'x ConnectionCard_20-ada-testcase y "url":"/messaging/compose/?profileUrn=urn%3Ali%3Afsd_profile%3AACoAAFAKE0001&z" '
            'ConnectionCard_20-ada-testcase again '
            'ConnectionCard_20-bo-fixture q "profileUrn=urn%3Ali%3Afsd_profile%3AACoAAFAKE0002" '
            'ConnectionCard_20-cy-mockson no urn here'
        )
        m = C.extract_member_urns(text)
        self.assertEqual(m["ada-testcase"], "urn:li:fsd_profile:ACoAAFAKE0001")
        self.assertEqual(m["bo-fixture"], "urn:li:fsd_profile:ACoAAFAKE0002")
        self.assertNotIn("cy-mockson", m)
        self.assertEqual(C.extract_member_urns(""), {})

    def test_block_detection(self):
        self.assertIsNotNone(C.detect_block_url("https://www.linkedin.com/authwall?trk=x"))
        self.assertIsNotNone(C.detect_block_url("https://www.linkedin.com/login"))
        self.assertIsNotNone(C.detect_block_url("https://www.linkedin.com/checkpoint/challenge/abc"))
        self.assertIsNone(C.detect_block_url("https://www.linkedin.com/feed/", "Feed | LinkedIn"))
        self.assertIsNone(C.detect_block_url(C.CONNECTIONS_URL, "Connections | LinkedIn"))


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "t.duckdb")

    def conns(self):
        return C.parse_dom_cards(DomParserTest().cards())

    def test_idempotent_upsert(self):
        with C.open_db(self.db_path) as db:
            C.upsert_connections(db, self.conns())
            first = {r["profile_url"]: r for r in C.list_connection_rows(db)}
            C.upsert_connections(db, self.conns())
            second = {r["profile_url"]: r for r in C.list_connection_rows(db)}
            self.assertEqual(len(first), 3)
            self.assertEqual(set(first), set(second))
            for url, r in second.items():
                self.assertEqual(r["first_seen_at"], first[url]["first_seen_at"])
                self.assertGreaterEqual(r["last_seen_at"], first[url]["last_seen_at"])
            self.assertEqual(db.conn.execute("SELECT COUNT(*) FROM connections").fetchone()[0], 3)
            self.assertEqual(db.conn.execute("SELECT COUNT(*) FROM contacts WHERE degree='1st'").fetchone()[0], 3)

    def test_null_date_does_not_erase_existing(self):
        with C.open_db(self.db_path) as db:
            C.upsert_connections(db, self.conns())
            again = C.parse_dom_cards([{"key": "k", "href": "https://www.linkedin.com/in/ada-testcase/",
                                        "lines": ["Ada Testcase", "Head of Growth @ Examplewidgets"]}])
            C.upsert_connections(db, again)
            ada = [r for r in C.list_connection_rows(db) if r["name"] == "Ada Testcase"][0]
            self.assertTrue(ada["connected_at"].startswith("2026-09-16"))

    def test_existing_contact_scores_preserved(self):
        with C.open_db(self.db_path) as db:
            db.upsert_contacts([LinkedInContact(
                urn_id="urn:li:member:ada-testcase", name="Ada Testcase", headline="old",
                profile_url="https://www.linkedin.com/in/ada-testcase", degree="2nd",
                role_match_score=77.0, company_match_score=55.0, mutual_count=4, mutual_sample=["Q"],
                source="dom_selectolax")])
            C.upsert_connections(db, self.conns())
            row = db.conn.execute(
                "SELECT degree, role_match_score, company_match_score, mutual_count FROM contacts "
                "WHERE profile_url='https://www.linkedin.com/in/ada-testcase'").fetchone()
            self.assertEqual(row, ("1st", 77.0, 55.0, 4))

    def test_memory_db_and_company_filter(self):
        with C.open_db(":memory:") as db:
            C.upsert_connections(db, self.conns())
            rows = C.list_connection_rows(db, company="examplewid")
            self.assertEqual([r["name"] for r in rows], ["Ada Testcase"])
            self.assertEqual(len(C.list_connection_rows(db, limit=2)), 2)


class ListCliJsonTest(unittest.TestCase):
    def test_list_json_parseable(self):
        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "t.duckdb")
        with C.open_db(db_path) as db:
            C.upsert_connections(db, C.parse_dom_cards(DomParserTest().cards()))
        r = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "cli.py"), "list-connections", "--json", "--db", db_path],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = json.loads(r.stdout)
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            set(rows[0]),
            {"profile_url", "urn_id", "name", "headline", "current_company", "location", "connected_at",
             "connected_at_text", "first_seen_at", "last_seen_at", "source"},
        )
        r2 = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "cli.py"), "list-connections", "--json", "--db", db_path,
             "--company", "nomatch"], capture_output=True, text=True)
        self.assertEqual(json.loads(r2.stdout), [])


class CompanyNormalizationTest(unittest.TestCase):
    def test_variants(self):
        n = C.normalize_company
        self.assertEqual(n("Pendo"), "Pendo")
        self.assertEqual(n("Pendo.io"), "Pendo")
        self.assertEqual(n("Examplewidgets, Inc."), "Examplewidgets")
        self.assertEqual(n("Mockco LLC"), "Mockco")
        self.assertEqual(n("Fakeco Ltd"), "Fakeco")
        self.assertEqual(n("Dupeco Corp."), "Dupeco")
        self.assertEqual(n("Stubly.com"), "Stubly")
        self.assertEqual(n("  Acme   Labs "), "Acme Labs")
        self.assertIsNone(n(None))
        self.assertIsNone(n(""))

    def test_written_normalized_headline_raw(self):
        cards = [{"key": "k", "href": "https://www.linkedin.com/in/ada-testcase/",
                  "lines": ["Ada Testcase", "Growth Lead at Pendo.io", "Connected on May 1, 2024"]}]
        with C.open_db(":memory:") as db:
            C.upsert_connections(db, C.parse_dom_cards(cards))
            r = C.list_connection_rows(db)[0]
            self.assertEqual(r["current_company"], "Pendo")
            self.assertEqual(r["headline"], "Growth Lead at Pendo.io")


class ProvenanceTest(unittest.TestCase):
    def test_merge_idempotent(self):
        a = C.merge_provenance(None, ["S1"])
        b = C.merge_provenance(a, ["S1", "S3"])
        self.assertEqual(json.loads(b), ["S1", "S3"])
        self.assertEqual(C.merge_provenance(b, ["S3"]), b)
        self.assertEqual(json.loads(C.merge_provenance("garbage", ["S2"])), ["S2"])

    def test_record_search_hits(self):
        base = C.parse_dom_cards([{"key": "k", "href": "https://www.linkedin.com/in/ada-testcase/",
                                   "lines": ["Ada Testcase", "Head of Growth at Examplewidgets",
                                             "Connected on May 1, 2024"]}])
        hits = C.parse_dom_cards([
            {"key": "a", "href": "https://www.linkedin.com/in/ada-testcase/", "lines": ["Ada Testcase", "Head of Growth at Examplewidgets"]},
            {"key": "b", "href": "https://www.linkedin.com/in/bo-fixture/", "lines": ["Bo Fixture", "Founder at Mockco"]},
        ])
        with C.open_db(":memory:") as db:
            C.upsert_connections(db, base)
            self.assertEqual(C.record_search_hits(db, hits, "S1", "marketing engineer"), (1, 1))
            self.assertEqual(C.record_search_hits(db, hits, "S1", "marketing engineer"), (0, 2))
            self.assertEqual(C.record_search_hits(db, hits, "S3", "mockco"), (0, 2))
            rows = {r["name"]: r for r in C.list_connection_rows(db)}
            self.assertEqual(db.conn.execute("SELECT COUNT(*) FROM connections").fetchone()[0], 2)
            ada = db.conn.execute(
                "SELECT segments, queries FROM connections WHERE name='Ada Testcase'").fetchone()
            self.assertEqual(json.loads(ada[0]), ["S1", "S3"])
            self.assertEqual(json.loads(ada[1]), ["marketing engineer", "mockco"])
            self.assertTrue(rows["Ada Testcase"]["connected_at"].startswith("2024-05-01"))  # kept
            self.assertIsNone(rows["Bo Fixture"]["connected_at"])                           # new: null
            self.assertEqual(rows["Ada Testcase"]["source"], "cdp_rsc_dom")


class QueryPlanTest(unittest.TestCase):
    T = {"S1": ["Marketing Engineer", "Growth Engineer"], "S2": ["Webflow"],
         "S3": ["Acmeco", "Initech"], "S4": ["CMO"]}

    def test_url(self):
        u = C.build_search_url("marketing engineer", 1)
        self.assertIn("keywords=marketing%20engineer", u)
        self.assertIn("network=%5B%22F%22%5D", u)
        self.assertNotIn("page=", u)
        self.assertTrue(C.build_search_url("x", 3).endswith("&page=3"))

    def test_segments_and_order(self):
        plan = C.build_query_plan("all", 1, 60, self.T)
        self.assertEqual([p["segment"] for p in plan], ["S1", "S1", "S2", "S3", "S3", "S4"])
        self.assertEqual([p["query"] for p in plan if p["segment"] == "S3"], ["Acmeco", "Initech"])
        self.assertEqual({p["segment"] for p in C.build_query_plan("S2", 3, 60, self.T)}, {"S2"})
        self.assertEqual({p["segment"] for p in C.build_query_plan("s4", 1, 60, self.T)}, {"S4"})
        with self.assertRaises(ValueError):
            C.build_query_plan("S9", 1, 60, self.T)

    def test_pages_first_and_caps(self):
        plan = C.build_query_plan("all", 3, 60, self.T)
        self.assertEqual(len(plan), 18)
        self.assertEqual([p["page"] for p in plan[:6]], [1] * 6)
        self.assertEqual(len(C.build_query_plan("all", 3, 4, self.T)), 4)

    def test_pipeline_order(self):
        md = ("| Company | Status |\n|---|---|\n| Zed Co | Researching |\n| Bee Inc | Interviewing |\n"
              "| Cee Corp | Networking |\n| Dee | Rejected |\n")
        p = os.path.join(tempfile.mkdtemp(), "README.md")
        Path(p).write_text(md)
        order = C.pipeline_company_order(p)
        self.assertEqual(len(order), 3)
        self.assertEqual([o.lower().split()[0] for o in order], ["bee", "cee", "zed"])

    def test_dry_run_no_browser(self):
        import argparse
        import io
        from contextlib import redirect_stdout

        def boom(*a, **k):
            raise AssertionError("browser touched")
        old = (C.resolve_linkedin_instance, C.pick_tab_ws_url, C.load_plan_targets)
        C.resolve_linkedin_instance = C.pick_tab_ws_url = boom
        C.load_plan_targets = lambda *a, **k: self.T
        try:
            ns = argparse.Namespace(segment="all", max_pages=1, max_requests=60, dry_run=True, profile="linkedin", db=None)
            buf = io.StringIO()
            with redirect_stdout(buf):
                C.cmd_search_connections(ns)
            self.assertIn("no browser opened", buf.getvalue())
            self.assertIn("network=%5B%22F%22%5D", buf.getvalue())
            ns.dry_run = False
            with self.assertRaises(SystemExit) as cm:
                C.cmd_search_connections(ns)
            self.assertEqual(cm.exception.code, 3)
        finally:
            C.resolve_linkedin_instance, C.pick_tab_ws_url, C.load_plan_targets = old


if __name__ == "__main__":
    unittest.main()
