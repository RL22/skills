#!/usr/bin/env python3
"""listen.py - passive, read-only feed listening, instance selection, and pasted-post ingest.

Nothing here navigates, clicks, types, scrolls, or evaluates script in a page. The listener
only reads the debugger's HTTP /json target list (a GET) and attaches the existing passive
capture_voyager_feed_traffic (Network.enable + Network.getResponseBody) to linkedin.com tabs
the user is browsing themselves.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from cdp_interceptor import capture_voyager_feed_traffic  # noqa: E402
from schemas import Post  # noqa: E402

PROFILES_ROOT = Path.home() / ".config" / "chrome-agent" / "profiles"
REGISTRY_PATH = Path("/tmp/chrome-agent/registry.json")
LISTEN_REMINDER = "Listening only. Browse the pages yourself; nothing is clicked or navigated."


# ==============================================================================
# Piece 2: instance selection
# ==============================================================================

def _load_registry(path: Path = REGISTRY_PATH) -> Dict[str, Any]:
    """chrome-agent's registry: {instance_name: {port, pid, user_data_dir, ...}}."""
    try:
        data = json.loads(Path(path).read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _ps_lines() -> List[str]:
    """Local process command lines (read-only `ps`); [] if unavailable."""
    try:
        return subprocess.run(["ps", "-axo", "command="], capture_output=True, text=True, timeout=5).stdout.splitlines()
    except Exception:
        return []


def _int_port(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _user_data_dir_for(inst: Dict[str, Any], registry: Dict[str, Any], ps_lines: Optional[List[str]]) -> Optional[str]:
    """Profile dir an instance runs with. chrome-agent's registry is authoritative (Chrome may be
    launched with --remote-debugging-port=0, so `ps` cannot show the port); `ps` matching the
    debugging port is the fallback."""
    meta = registry.get(inst.get("name") or "")
    if isinstance(meta, dict) and meta.get("user_data_dir"):
        return str(meta["user_data_dir"])
    port = _int_port(inst.get("port"))
    if port is not None:
        lines = ps_lines if ps_lines is not None else _ps_lines()
        needle = f"--remote-debugging-port={port}"
        for line in lines:
            if needle in line.split() and "--type=" not in line:
                m = re.search(r"--user-data-dir=(.+?)(?=\s--|$)", line)
                if m:
                    return m.group(1).strip()
    return None


def _is_profile_dir(user_data_dir: Optional[str], profile: str) -> bool:
    if not user_data_dir:
        return False
    try:
        return Path(user_data_dir).resolve() == (PROFILES_ROOT / profile).resolve()
    except Exception:
        return False


def pick_instance(
    instances: List[Dict[str, Any]],
    profile: str = "linkedin",
    port: Optional[int] = None,
    registry: Optional[Dict[str, Any]] = None,
    ps_lines: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Choose the browser instance to attach to.

    1. An explicit `port` wins (matched against the instance list; if it is not listed, a
       synthetic {"name": "port-N", "port": N} is returned).
    2. Else the instance whose Chrome runs with --user-data-dir ~/.config/chrome-agent/profiles/<profile>.
    3. Else the first instance, with a warning that it may not be logged in.
    Returns None when there are no instances and no explicit port.
    """
    if port is not None:
        for inst in instances:
            if _int_port(inst.get("port")) == int(port):
                return inst
        return {"name": f"port-{int(port)}", "port": int(port)}
    if not instances:
        return None
    if registry is None:
        registry = _load_registry()
    for inst in instances:
        if _is_profile_dir(_user_data_dir_for(inst, registry, ps_lines), profile):
            return inst
    first = instances[0]
    print(
        f"[!] Warning: no running instance uses profile '{profile}'. Falling back to "
        f"'{first.get('name')}' (port {first.get('port')}); it may not be logged in to LinkedIn.",
        file=sys.stderr,
    )
    return first


# ==============================================================================
# Piece 1: passive listener
# ==============================================================================

def list_linkedin_targets(port: int, timeout: float = 2.0) -> List[Dict[str, str]]:
    """GET http://127.0.0.1:{port}/json -> linkedin.com page targets [{id, url, ws_url}]."""
    with urllib.request.urlopen(f"http://127.0.0.1:{int(port)}/json", timeout=timeout) as resp:
        targets = json.loads(resp.read().decode("utf-8"))
    out = []
    for t in targets:
        if t.get("type") == "page" and t.get("webSocketDebuggerUrl") and "linkedin.com" in (t.get("url") or "").lower():
            out.append({"id": t.get("id") or t["webSocketDebuggerUrl"], "url": t.get("url", ""), "ws_url": t["webSocketDebuggerUrl"]})
    return out


class ListenState:
    def __init__(self) -> None:
        self.posts: Dict[str, Post] = {}
        self.tabs_seen: List[str] = []

    def add(self, posts: List[Post]) -> None:
        for p in posts:
            self.posts.setdefault(p.post_id, p)

    def authors(self) -> int:
        return len({(p.author_type, p.author_id or p.author_name) for p in self.posts.values()})


async def listen_feed(
    seconds: float,
    list_targets: Callable[[], List[Dict[str, str]]],
    state: Optional[ListenState] = None,
    poll_interval: float = 3.0,
    heartbeat_interval: float = 5.0,
    window: float = 10.0,
    overlap: float = 2.0,
    capture: Callable[..., Any] = capture_voyager_feed_traffic,
    out: Callable[[str], None] = print,
) -> ListenState:
    """Listen passively on every linkedin.com page target for `seconds`; re-poll targets every
    `poll_interval` so tabs opened later are picked up. capture_voyager_feed_traffic returns only
    when its window ends, so each tab gets overlapping `window`-second captures (deduped by
    post_id) to keep results and the heartbeat fresh without gaps."""
    state = state or ListenState()
    deadline = time.monotonic() + seconds
    tab_tasks: Dict[str, asyncio.Task] = {}
    windows: set = set()

    def on_done(task: asyncio.Task) -> None:
        windows.discard(task)
        if not task.cancelled() and task.exception() is None:
            state.add(task.result() or [])

    async def tab_loop(ws_url: str) -> None:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            span = min(window, remaining)
            task = asyncio.create_task(capture(ws_url, timeout=span))
            windows.add(task)
            task.add_done_callback(on_done)
            if span >= remaining:
                return
            await asyncio.sleep(max(span - overlap, 0.05))

    last_beat = time.monotonic()
    try:
        while time.monotonic() < deadline:
            try:
                targets = await asyncio.get_running_loop().run_in_executor(None, list_targets)
            except Exception as exc:
                targets = []
                out(f"[!] Could not read target list ({exc}); will retry.")
            live = {t["id"] for t in targets}
            for t in targets:
                if t["id"] not in tab_tasks:
                    tab_tasks[t["id"]] = asyncio.create_task(tab_loop(t["ws_url"]))
                    state.tabs_seen.append(t["id"])
                    out(f"[*] Listening on tab: {t['url'][:90]}")
            for tid in [k for k in tab_tasks if k not in live]:
                tab_tasks.pop(tid).cancel()  # tab closed; in-flight windows finish on their own
            wake = min(poll_interval, max(deadline - time.monotonic(), 0))
            while wake > 0:
                step = min(wake, max(heartbeat_interval - (time.monotonic() - last_beat), 0.01), 0.25)
                await asyncio.sleep(step)
                wake -= step
                if time.monotonic() - last_beat >= heartbeat_interval:
                    out(f"listening, {len(state.posts)} posts so far")
                    last_beat = time.monotonic()
    finally:
        for task in tab_tasks.values():
            task.cancel()
        if windows:
            await asyncio.gather(*list(windows), return_exceptions=True)
    return state


def summarize(state: ListenState, db: Any, out: Callable[[str], None] = print) -> None:
    from connections import connections_with_posts

    out(f"[+] Captured {len(state.posts)} posts from {state.authors()} distinct authors "
        f"across {len(state.tabs_seen)} tab(s).")
    all_rows = connections_with_posts(db=db)
    rows = [r for r in all_rows if r["own_posts"]]
    employer_only = [r for r in all_rows if r["company_posts"] and not r["own_posts"]]
    if not rows:
        out("[*] None of your stored connections have posts of their own yet.")
    else:
        out(f"[+] {len(rows)} of your connections have posts of their own:")
        out(f"    {'NAME':<28} {'OWN POSTS':>9} {'EMPLOYER PAGE':>13}")
        for r in rows:
            out(f"    {(r['name'] or '')[:27]:<28} {r['own_posts']:>9} {r['company_posts']:>13}")
    if employer_only:
        out(f"[*] {len(employer_only)} more only match a stored post by their employer's company page "
            f"(not their own posts, so not counted).")


def cmd_listen_feed(args: argparse.Namespace) -> None:
    from connections import open_db

    port = args.port
    if port is None:
        try:
            from profile_manager import get_active_instances
        except ImportError:
            get_active_instances = lambda: []  # noqa: E731
        inst = pick_instance(get_active_instances(), profile=args.profile)
        if inst is None:
            print("[!] No running browser instance found. Open your LinkedIn Chrome first.", file=sys.stderr)
            sys.exit(1)
        port = int(inst.get("port") or 9222)
        print(f"[*] Using browser instance '{inst.get('name')}' on port {port}.")
    print(LISTEN_REMINDER)
    state = ListenState()
    try:
        asyncio.run(listen_feed(args.seconds, lambda: list_linkedin_targets(port), state))
    except KeyboardInterrupt:
        print("\n[*] Interrupted; saving what was captured.")
    db = open_db(args.db)
    try:
        n = db.upsert_posts(list(state.posts.values()))
        print(f"[+] Upserted {n} posts into {db.db_path}.")
        summarize(state, db)
    finally:
        db.close()


# ==============================================================================
# Piece 3: add-post
# ==============================================================================

_ACTIVITY_RE = re.compile(r"urn:li:activity:(\d+)|activity-(\d+)")
_POSTS_HANDLE_RE = re.compile(r"/posts/([^_/?#]+)_", re.IGNORECASE)
_HASHTAG_RE = re.compile(r"#(\w+)")


def build_post_from_paste(
    url: str,
    author: str,
    text: str,
    author_handle: Optional[str] = None,
    author_type: str = "person",
    likes: Optional[int] = None,
    comments: Optional[int] = None,
    reposts: Optional[int] = None,
) -> Post:
    """Build a Post from pasted data. Raises ValueError if the URL has no activity id."""
    m = _ACTIVITY_RE.search(url or "")
    if not m:
        raise ValueError("URL has no activity id (expected urn:li:activity:N or a /posts/..._activity-N permalink)")
    activity_id = m.group(1) or m.group(2)
    handle = (author_handle or "").strip().strip("/").lower() or None
    if handle is None and author_type == "person":
        mh = _POSTS_HANDLE_RE.search(url)
        handle = mh.group(1).lower() if mh else None
    author_id = None
    if handle:
        author_id = f"urn:li:member:{handle}" if author_type == "person" else handle
    tags: List[str] = []
    for t in _HASHTAG_RE.findall(text or ""):
        if t not in tags:
            tags.append(t)
    return Post(
        post_id=activity_id,
        post_url=f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/",
        author_name=author,
        author_type=author_type,  # type: ignore[arg-type]
        author_id=author_id,
        text=text or None,
        hashtags=tags,
        like_count=likes,
        comment_count=comments,
        repost_count=reposts,
    )


def _read_text_arg(args: argparse.Namespace) -> str:
    if args.text_file:
        return Path(args.text_file).read_text(encoding="utf-8")
    if args.text == "-":
        return sys.stdin.read()
    return args.text or ""


def cmd_add_post(args: argparse.Namespace) -> None:
    from connections import connections_with_posts, open_db

    text = _read_text_arg(args).strip()
    try:
        post = build_post_from_paste(
            args.url, args.author, text, args.author_handle, args.author_type,
            args.likes, args.comments, args.reposts,
        )
    except ValueError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        sys.exit(2)
    db = open_db(args.db)
    try:
        db.upsert_posts([post])
        stored = db.get_post(post.post_id)
        matched = [r for r in connections_with_posts(db=db)
                   if r["posts"] and _row_matches_author(r, post)]
    finally:
        db.close()
    print(f"[+] Stored post_id {stored.post_id if stored else post.post_id} ({post.post_url})")
    if matched:
        print(f"[+] Author matches stored connection: {matched[0]['name']} ({matched[0]['profile_url']})")
    else:
        print("[*] Author does not match a stored connection.")


def _row_matches_author(row: Dict[str, Any], post: Post) -> bool:
    from connections import author_handle as _ah, _slug_key
    if post.author_type == "person":
        h = _ah(post.author_id)
        return bool(h) and row.get("handle") == h and row["own_posts"] > 0
    return row["company_posts"] > 0 and bool(_slug_key(post.author_id))


def add_parsers(subparsers: Any) -> None:
    """Register listen-feed and add-post (called from cli.py main())."""
    lp = subparsers.add_parser(
        "listen-feed",
        help="Passively pool post data from tabs you browse yourself (read-only)",
        description=("Listens on your visible Chrome's linkedin.com tabs and captures feed post data as you browse. "
                     "Never navigates, clicks, or scrolls. Works for company Posts tabs and person Activity tabs, "
                     "not the home feed."),
    )
    lp.add_argument("--seconds", type=float, default=180.0, help="How long to listen (default: 180)")
    lp.add_argument("--port", type=int, default=None, help="Debugger port (default: auto-pick the profile's instance)")
    lp.add_argument("--profile", default="linkedin", help="Chrome profile name (default: 'linkedin')")
    lp.add_argument("--db", default=None, help="DuckDB database path")

    ap = subparsers.add_parser("add-post", help="Store a pasted post (URL, author, text, counts) by hand")
    ap.add_argument("--url", required=True, help="Post URL (urn:li:activity:N or /posts/..._activity-N permalink)")
    ap.add_argument("--author", required=True, help="Author display name")
    ap.add_argument("--author-handle", default=None, help="Author profile handle or company slug")
    ap.add_argument("--author-type", choices=["person", "company"], default="person")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="Post text; use '-' to read stdin")
    src.add_argument("--text-file", help="Path to a file holding the post text")
    ap.add_argument("--likes", type=int, default=None)
    ap.add_argument("--comments", type=int, default=None)
    ap.add_argument("--reposts", type=int, default=None)
    ap.add_argument("--db", default=None, help="DuckDB database path")
