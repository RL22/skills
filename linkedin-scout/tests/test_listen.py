"""Tests for scripts/listen.py and the connection-post join. All people, handles and ids are invented.
No real network or browser: mock CDP websocket servers on localhost only."""

import argparse
import asyncio
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import websockets  # noqa: E402

import connections as C  # noqa: E402
import listen as L  # noqa: E402
from pipeline_db import NetworkDatabase  # noqa: E402

LINKEDIN_DIR = str(L.PROFILES_ROOT / "linkedin")


def feed_payload(items):
    """items: [(activity_id, author_name, actor_url, text, likes, comments, shares)]"""
    included = []
    for aid, name, url, text, nl, nc, ns in items:
        included += [
            {"$type": "com.linkedin.voyager.dash.feed.Update", "entityUrn": f"urn:li:fsd_update:{aid}",
             "metadata": {"backendUrn": f"urn:li:activity:{aid}"},
             "actor": {"name": {"text": name}, "navigationContext": {"actionTarget": url}},
             "commentary": {"text": {"text": text}}, "*socialDetail": f"urn:sd:{aid}"},
            {"entityUrn": f"urn:sd:{aid}", "*totalSocialActivityCounts": f"urn:c:{aid}"},
            {"entityUrn": f"urn:c:{aid}", "numLikes": nl, "numComments": nc, "numShares": ns},
        ]
    return {"included": included}


TAB1 = feed_payload([
    (1001, "Mara Voss", "https://www.linkedin.com/in/mara-voss", "Shipping #design systems", 10, 2, 1),
    (1002, "Mara Voss", "https://www.linkedin.com/in/mara-voss", "More thoughts", 5, 0, 0),
])
TAB2 = feed_payload([
    (1002, "Mara Voss", "https://www.linkedin.com/in/mara-voss", "More thoughts", 5, 0, 0),  # dup of tab 1
    (2001, "Larkspur Labs", "https://www.linkedin.com/company/larkspur-labs/", "We are hiring", 30, 4, 6),
])
TAB3 = feed_payload([
    (3001, "Tomas Rey", "https://www.linkedin.com/in/tomas-rey", "Hello", 1, 1, 1),
])


class MockCdp:
    """Mock CDP server. Routes by websocket path (/tab1, /tab2, ...); records every method received."""

    def __init__(self, payloads):
        self.payloads = payloads
        self.methods = []
        self.server = None
        self.port = None

    async def handler(self, ws):
        path = getattr(getattr(ws, "request", None), "path", None) or getattr(ws, "path", "/")
        payload = json.dumps(self.payloads[path.strip("/")])
        async for raw in ws:
            cmd = json.loads(raw)
            self.methods.append(cmd.get("method"))
            if cmd.get("method") == "Network.enable":
                await ws.send(json.dumps({"id": cmd["id"], "result": {}}))
                await asyncio.sleep(0.02)
                await ws.send(json.dumps({"method": "Network.responseReceived", "params": {
                    "requestId": "r1", "response": {"url": "https://www.linkedin.com/voyager/api/graphql?queryId=voyagerFeedDashProfileUpdates.abc", "status": 200}}}))
                await ws.send(json.dumps({"method": "Network.loadingFinished", "params": {"requestId": "r1"}}))
            elif cmd.get("method") == "Network.getResponseBody":
                await ws.send(json.dumps({"id": cmd["id"], "result": {"body": payload, "base64Encoded": False}}))
            else:
                await ws.send(json.dumps({"id": cmd.get("id"), "result": {}}))

    async def __aenter__(self):
        self.server = await websockets.serve(self.handler, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *a):
        self.server.close()
        await self.server.wait_closed()

    def ws(self, tab):
        return f"ws://127.0.0.1:{self.port}/{tab}"


def run_listen(list_targets, seconds=2.2, out=None):
    lines = [] if out is None else out
    st = asyncio.run(L.listen_feed(seconds, list_targets, poll_interval=0.3, heartbeat_interval=0.5,
                                   window=1.0, overlap=0.3, out=lines.append))
    return st, lines


class PickInstanceTests(unittest.TestCase):
    INSTS = [{"name": "other-01", "port": 9223}, {"name": "scripts-01", "port": "59212"}]
    REG = {"other-01": {"user_data_dir": "/tmp/chrome-agent/session-x"},
           "scripts-01": {"user_data_dir": LINKEDIN_DIR}}

    def test_explicit_port_wins(self):
        got = L.pick_instance(self.INSTS, port=9223, registry=self.REG)
        self.assertEqual(got["name"], "other-01")

    def test_profile_match_preferred_over_first(self):
        self.assertEqual(L.pick_instance(self.INSTS, registry=self.REG)["name"], "scripts-01")

    def test_ps_fallback_when_not_in_registry(self):
        ps = [f"/Applications/Google Chrome --remote-debugging-port=59212 --user-data-dir={LINKEDIN_DIR} --no-first-run"]
        self.assertEqual(L.pick_instance(self.INSTS, registry={}, ps_lines=ps)["name"], "scripts-01")

    def test_fallback_warns_and_returns_first(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            got = L.pick_instance(self.INSTS, profile="linkedin", registry={"other-01": {"user_data_dir": "/tmp/a"}}, ps_lines=[])
        self.assertEqual(got["name"], "other-01")
        self.assertIn("other-01", err.getvalue())
        self.assertIn("may not be logged in", err.getvalue())

    def test_no_instances(self):
        self.assertIsNone(L.pick_instance([], registry={}))


def make_db(path, conns=(), posts=()):
    db = C.open_db(path)
    if conns:
        C.upsert_connections(db, [C._make_connection(name=n, profile_url=u, company=co) for n, u, co in conns])
    if posts:
        db.upsert_posts(list(posts))
    return db


def mk_post(aid, author, author_id, likes=0, comments=0, reposts=0, atype="person"):
    return L.build_post_from_paste(
        f"https://www.linkedin.com/feed/update/urn:li:activity:{aid}/", author, "t",
        author_handle=None, author_type=atype, likes=likes, comments=comments, reposts=reposts,
    ).model_copy(update={"author_id": author_id})


class JoinTests(unittest.TestCase):
    def test_handle_join_case_insensitive_and_company_slug(self):
        db = make_db(":memory:",
                     conns=[("Mara Voss", "https://www.linkedin.com/in/mara-voss", "Larkspur Labs"),
                            ("Tomas Rey", "https://www.linkedin.com/in/tomas-rey", "Halyard"),
                            ("Ines Ko", "https://www.linkedin.com/in/ines-ko", None)],
                     posts=[mk_post(1, "Mara Voss", "urn:li:member:MARA-VOSS", 10, 2, 0),
                            mk_post(2, "Mara Voss", "urn:li:member:mara-voss", 4, 0, 0),
                            mk_post(3, "Larkspur Labs", "larkspur-labs", 20, 0, 0, atype="company")])
        rows = {r["name"]: r for r in C.connections_with_posts(db=db)}
        mara = rows["Mara Voss"]
        self.assertEqual((mara["own_posts"], mara["company_posts"], mara["posts"]), (2, 1, 3))
        self.assertEqual(mara["total_engagement"], 36)
        self.assertEqual(mara["avg_engagement"], 12.0)
        self.assertEqual(rows["Tomas Rey"]["posts"], 0)
        self.assertEqual(rows["Ines Ko"]["posts"], 0)
        db.close()

    def test_handle_helpers(self):
        self.assertEqual(C.connection_handle("https://www.linkedin.com/in/Mara-Voss/"), "mara-voss")
        self.assertEqual(C.author_handle("urn:li:member:Mara-Voss"), "mara-voss")
        self.assertIsNone(C.author_handle("larkspur-labs"))


class AddPostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "t.duckdb")

    def tearDown(self):
        self.tmp.cleanup()

    def ns(self, **kw):
        base = dict(url="https://www.linkedin.com/posts/mara-voss_shipping-design-activity-7000000000000000001-AbCd",
                    author="Mara Voss", author_handle=None, author_type="person", text="Hello #Design and #ux #design",
                    text_file=None, likes=7, comments=1, reposts=0, db=self.db_path)
        base.update(kw)
        return argparse.Namespace(**base)

    def run_cmd(self, **kw):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            L.cmd_add_post(self.ns(**kw))
        return out.getvalue()

    def test_valid_permalink_handle_hashtags_and_connection_match(self):
        db = make_db(self.db_path, conns=[("Mara Voss", "https://www.linkedin.com/in/mara-voss", None)])
        db.close()
        out = self.run_cmd()
        self.assertIn("7000000000000000001", out)
        self.assertIn("matches stored connection: Mara Voss", out)
        with NetworkDatabase(self.db_path) as db:
            p = db.get_post("7000000000000000001")
        self.assertEqual(p.author_id, "urn:li:member:mara-voss")
        self.assertEqual(p.hashtags, ["Design", "ux", "design"])
        self.assertEqual(p.source, "dom_selectolax")
        self.assertEqual(p.like_count, 7)

    def test_urn_url_no_match(self):
        out = self.run_cmd(url="https://www.linkedin.com/feed/update/urn:li:activity:7000000000000000002/",
                           author_handle="Tomas-Rey")
        self.assertIn("does not match", out)
        with NetworkDatabase(self.db_path) as db:
            self.assertEqual(db.get_post("7000000000000000002").author_id, "urn:li:member:tomas-rey")

    def test_missing_activity_id_exits_2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            self.run_cmd(url="https://www.linkedin.com/in/mara-voss/")
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("activity id", err.getvalue())

    def test_stdin_and_text_file(self):
        with mock.patch("sys.stdin", io.StringIO("from stdin #one")):
            self.run_cmd(text="-")
        with NetworkDatabase(self.db_path) as db:
            self.assertEqual(db.get_post("7000000000000000001").hashtags, ["one"])
        f = Path(self.tmp.name) / "p.txt"
        f.write_text("from file #two\n")
        self.run_cmd(text=None, text_file=str(f), url="https://www.linkedin.com/feed/update/urn:li:activity:7000000000000000003/")
        with NetworkDatabase(self.db_path) as db:
            self.assertEqual(db.get_post("7000000000000000003").text, "from file #two")

    def test_idempotent(self):
        self.run_cmd()
        self.run_cmd(likes=9)
        with NetworkDatabase(self.db_path) as db:
            n = db.conn.execute("SELECT count(*) FROM posts").fetchone()[0]
            self.assertEqual(n, 1)
            self.assertEqual(db.get_post("7000000000000000001").like_count, 9)

    def test_company_author_uses_slug(self):
        p = L.build_post_from_paste("urn:li:activity:55", "Larkspur Labs", "x", "larkspur-labs", "company")
        self.assertEqual(p.author_id, "larkspur-labs")


class ListenTests(unittest.TestCase):
    def test_aggregation_dedupe_and_no_page_control(self):
        async def go():
            async with MockCdp({"tab1": TAB1, "tab2": TAB2}) as srv:
                targets = [{"id": "t1", "url": "https://www.linkedin.com/in/mara-voss/recent-activity/all/", "ws_url": srv.ws("tab1")},
                           {"id": "t2", "url": "https://www.linkedin.com/company/larkspur-labs/posts/", "ws_url": srv.ws("tab2")}]
                lines = []
                st = await L.listen_feed(2.2, lambda: targets, poll_interval=0.3, heartbeat_interval=0.5,
                                         window=1.0, overlap=0.3, out=lines.append)
                return st, lines, srv.methods
        st, lines, methods = asyncio.run(go())
        self.assertEqual(sorted(st.posts), ["1001", "1002", "2001"])
        self.assertEqual(st.authors(), 2)
        self.assertTrue(any("listening," in ln and "posts so far" in ln for ln in lines))
        self.assertTrue(methods)
        self.assertLessEqual(set(methods), {"Network.enable", "Network.getResponseBody"})
        for m in methods:
            self.assertFalse(m.startswith(("Page.", "Input.", "Runtime.", "Emulation.")), m)

    def test_repoll_picks_up_tab_opened_mid_run(self):
        async def go():
            async with MockCdp({"tab1": TAB1, "tab3": TAB3}) as srv:
                base = [{"id": "t1", "url": "https://www.linkedin.com/in/mara-voss/", "ws_url": srv.ws("tab1")}]
                late = {"id": "t3", "url": "https://www.linkedin.com/in/tomas-rey/", "ws_url": srv.ws("tab3")}
                t0 = time.monotonic()

                def targets():
                    return base + ([late] if time.monotonic() - t0 > 0.9 else [])
                st = await L.listen_feed(2.5, targets, poll_interval=0.3, heartbeat_interval=0.5,
                                         window=1.0, overlap=0.3, out=lambda s: None)
                return st, srv.methods
        st, methods = asyncio.run(go())
        self.assertIn("3001", st.posts)
        self.assertIn("t3", st.tabs_seen)
        self.assertLessEqual(set(methods), {"Network.enable", "Network.getResponseBody"})

    def test_list_linkedin_targets_filters_pages(self):
        body = json.dumps([
            {"id": "a", "type": "page", "url": "https://www.linkedin.com/in/x/", "webSocketDebuggerUrl": "ws://h/a"},
            {"id": "b", "type": "page", "url": "https://example.org/", "webSocketDebuggerUrl": "ws://h/b"},
            {"id": "c", "type": "service_worker", "url": "https://www.linkedin.com/sw", "webSocketDebuggerUrl": "ws://h/c"},
        ]).encode()
        seen = []

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(("GET", self.path))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            got = L.list_linkedin_targets(srv.server_address[1])
        finally:
            srv.shutdown()
        self.assertEqual([t["id"] for t in got], ["a"])
        self.assertEqual(seen, [("GET", "/json")])

    def test_summary_lists_connections_with_post_data(self):
        db = make_db(":memory:", conns=[("Mara Voss", "https://www.linkedin.com/in/mara-voss", None),
                                        ("Ines Ko", "https://www.linkedin.com/in/ines-ko", None)])
        st = L.ListenState()
        p = mk_post(1001, "Mara Voss", "urn:li:member:mara-voss", 10, 2, 1)
        st.add([p])
        db.upsert_posts([p])
        lines = []
        L.summarize(st, db, out=lines.append)
        text = "\n".join(lines)
        self.assertIn("1 posts from 1 distinct authors", text)
        self.assertIn("Mara Voss", text)
        self.assertNotIn("Ines Ko", text)
        db.close()


if __name__ == "__main__":
    unittest.main()
