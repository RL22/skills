"""connections.py - Read-only ingest of the viewer's LinkedIn 1st-degree connections.

Recon finding (2026-09): /mynetwork/invite-connect/connections/ is NOT backed by a
/voyager/api/ GraphQL query. It is a server-driven UI (SDUI/RSC) page: the first 10 cards are
server-rendered, then infinite scroll POSTs
  /flagship-web/rsc-action/actions/pagination?sduiid=com.linkedin.sdui.pagers.mynetwork.connectionsList
which returns an RSC "flight" text body (10 cards per response). Cards render into the DOM with
componentkey="ConnectionCard_<n>-<handle>" and carry name, headline and "Connected on <Month D, YYYY>".
The lazy pager only fires when the tab is visible (visibilityState == "visible"), so the capture
brings its own dedicated tab to front (Page.bringToFront; no page interaction).

Capture strategy: passively read the DOM after each human-paced scroll for name/headline/date, and
passively read the pagination + document network bodies for the member URN (ACoAA...). A Voyager
included[]-style parser is kept as well (parse_voyager_connections_json) for any legacy/other
surface that returns normalized connection entities.

STRICTLY READ-ONLY: navigate, scroll, read. Never click or type. Stops on authwall/login/checkpoint/
captcha or HTTP 429/999.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import random
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

_CURRENT_DIR = Path(__file__).resolve().parent
if str(_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(_CURRENT_DIR))
# capt-chrome-agent: $CAPT_CHROME_AGENT_DIR, else a sibling skill, else ~/.agents/skills
_CHROME_AGENT_SCRIPTS = next(
    (d / "scripts" for d in (
        Path(os.environ["CAPT_CHROME_AGENT_DIR"]).expanduser() if os.environ.get("CAPT_CHROME_AGENT_DIR") else None,
        _CURRENT_DIR.parent.parent / "capt-chrome-agent",
        Path.home() / ".agents" / "skills" / "capt-chrome-agent",
    ) if d is not None and (d / "scripts").exists()),
    Path.home() / ".agents" / "skills" / "capt-chrome-agent" / "scripts",
)
if _CHROME_AGENT_SCRIPTS.exists() and str(_CHROME_AGENT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_CHROME_AGENT_SCRIPTS))

from pydantic import Field, model_validator

from schemas import (
    LinkedInContact,
    canonicalize_linkedin_url,
    extract_company_from_headline,
)
from pipeline_db import DEFAULT_DB_PATH, NetworkDatabase

CONNECTIONS_URL = "https://www.linkedin.com/mynetwork/invite-connect/connections/"
FEED_URL = "https://www.linkedin.com/feed/"
FORBIDDEN_INSTANCES = {"rl22.github.io-01"}
SOURCE_TAG = "cdp_rsc_dom"

_BLOCK_URL_RE = re.compile(r"/(authwall|login|checkpoint|uas/|challenge|captcha)", re.IGNORECASE)
_BLOCK_TITLE_RE = re.compile(r"security verification|security check|sign in|log in|let.s do a quick", re.IGNORECASE)
_CONNECTED_ON_RE = re.compile(r"connected\s+on\s+([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", re.IGNORECASE)
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


# ==============================================================================
# Model
# ==============================================================================

class Connection(LinkedInContact):
    """A 1st-degree connection. degree is always '1st'."""

    connected_at: Optional[datetime] = Field(default=None, description="When the connection was made (UTC)")
    connected_at_text: Optional[str] = Field(default=None, description="Raw 'Connected on ...' text as shown")
    member_urn: Optional[str] = Field(default=None, description="urn:li:fsd_profile:ACoAA... when observed")
    source: str = Field(default=SOURCE_TAG, description="Extraction channel")  # type: ignore[assignment]

    @model_validator(mode="after")
    def _force_first_degree(self) -> "Connection":
        self.degree = "1st"
        return self


def parse_connected_at(text: Optional[str]) -> Optional[datetime]:
    """Parse 'Connected on September 16, 2026' into a UTC datetime; None for relative/unknown text."""
    if not text:
        return None
    m = _CONNECTED_ON_RE.search(text)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    if not month:
        return None
    try:
        return datetime(int(m.group(3)), month, int(m.group(2)), tzinfo=timezone.utc)
    except ValueError:
        return None


def _make_connection(
    *,
    name: Any,
    profile_url: Any,
    headline: Any = "",
    company: Any = None,
    location: Any = None,
    connected_at: Optional[datetime] = None,
    connected_at_text: Optional[str] = None,
    member_urn: Optional[str] = None,
) -> Optional[Connection]:
    """Build a Connection; None if name or profile_url unusable."""
    try:
        name_s = re.sub(r"\s+", " ", str(name or "")).strip()
        if not name_s or not profile_url:
            return None
        url = canonicalize_linkedin_url(str(profile_url))
        if "/in/" not in url:
            return None
        headline_s = re.sub(r"\s+", " ", str(headline or "")).strip()
        comp = str(company).strip() if company else None
        if not comp and headline_s:
            comp = extract_company_from_headline(headline_s)
        handle = url.rstrip("/").split("/in/")[-1]
        return Connection(
            urn_id=f"urn:li:member:{handle}",
            name=name_s,
            headline=headline_s,
            profile_url=url,
            location=(str(location).strip() or None) if location else None,
            current_company=comp or None,
            connected_at=connected_at,
            connected_at_text=connected_at_text,
            member_urn=member_urn,
        )
    except Exception:
        return None


# ==============================================================================
# Parsers
# ==============================================================================

def _text(v: Any) -> str:
    if isinstance(v, dict):
        v = v.get("text", "")
    return v.strip() if isinstance(v, str) else ""


def _epoch_to_dt(v: Any) -> Optional[datetime]:
    try:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        secs = v / 1000.0 if v > 10_000_000_000 else float(v)
        return datetime.fromtimestamp(secs, tz=timezone.utc)
    except Exception:
        return None


def parse_voyager_connections_json(payload: dict) -> List[Connection]:
    """Parse a normalized Voyager payload (elements + `included`, URN cross-references).

    Connection entities ('...relationships...Connection' or anything with a connected-member ref)
    point at profile entities via URN strings ('*connectedMemberResolutionResult', 'connectedMember').
    Non-connection entities (companies, posts, ...) are ignored. Per-field failures yield None/blank;
    duplicates collapse on canonical profile_url.
    """
    if not isinstance(payload, dict):
        return []
    included = payload.get("included")
    if not isinstance(included, list):
        data = payload.get("data")
        included = data.get("included") if isinstance(data, dict) else None
    if not isinstance(included, list):
        return []

    index: Dict[str, dict] = {}
    for item in included:
        if isinstance(item, dict) and isinstance(item.get("entityUrn"), str):
            index[item["entityUrn"]] = item

    out: List[Connection] = []
    seen: set = set()
    for item in included:
        if not isinstance(item, dict):
            continue
        try:
            ref = (
                item.get("*connectedMemberResolutionResult")
                or item.get("*connectedMember")
                or item.get("connectedMember")
                or item.get("connectedMemberResolutionResult")
            )
            typ = str(item.get("$type", ""))
            if ref is None and not ("relationships" in typ and typ.endswith("Connection")):
                continue
            prof = ref if isinstance(ref, dict) else index.get(ref) if isinstance(ref, str) else None
            if not isinstance(prof, dict):
                continue

            first = _text(prof.get("firstName"))
            last = _text(prof.get("lastName"))
            name = (first + " " + last).strip() or _text(prof.get("name"))
            pub = prof.get("publicIdentifier")
            url = f"https://www.linkedin.com/in/{pub}" if isinstance(pub, str) and pub else None
            if not url:
                continue
            headline = ""
            try:
                headline = _text(prof.get("headline"))
            except Exception:
                headline = ""
            location = None
            try:
                geo = prof.get("geoLocation") or prof.get("location")
                location = _text(geo) or None
            except Exception:
                location = None
            company = None
            try:
                company = _text(prof.get("currentCompany")) or None
            except Exception:
                company = None
            connected_at = None
            try:
                connected_at = _epoch_to_dt(item.get("createdAt"))
            except Exception:
                connected_at = None
            urn = None
            try:
                e = prof.get("entityUrn")
                urn = e if isinstance(e, str) and "ACoAA" in e else None
            except Exception:
                urn = None

            conn = _make_connection(
                name=name, profile_url=url, headline=headline, company=company,
                location=location, connected_at=connected_at,
                connected_at_text=None, member_urn=urn,
            )
            if conn and conn.profile_url not in seen:
                seen.add(conn.profile_url)
                out.append(conn)
        except Exception:
            continue
    return out


def parse_dom_cards(cards: List[dict]) -> List[Connection]:
    """Build Connections from DOM card dicts: {key, href, lines:[name, headline..., 'Connected on ...', 'Message']}."""
    out: List[Connection] = []
    seen: set = set()
    for card in cards or []:
        try:
            lines = [str(x).strip() for x in card.get("lines", []) if str(x).strip()]
            lines = [x for x in lines if x.lower() not in ("message", "send message")]
            if not lines:
                continue
            name = lines[0]
            connected_line = next((x for x in lines[1:] if x.lower().startswith("connected")), None)
            body = [x for x in lines[1:] if x != connected_line]
            headline = " ".join(body[:1]) if body else ""
            href = card.get("href")
            if not href:
                key = str(card.get("key", ""))
                m = re.match(r"ConnectionCard_\d+-(.+)$", key)
                href = f"https://www.linkedin.com/in/{m.group(1)}" if m else None
            conn = _make_connection(
                name=name, profile_url=href, headline=headline,
                connected_at=parse_connected_at(connected_line),
                connected_at_text=connected_line,
            )
            if conn and conn.profile_url not in seen:
                seen.add(conn.profile_url)
                out.append(conn)
        except Exception:
            continue
    return out


_CARD_KEY_RE = re.compile(r"ConnectionCard_\d+-([^\"\\\s]+)")
_ACO_RE = re.compile(r"(?:fsd_profile(?:%3A|:))(ACoAA[\w-]+)")


def extract_member_urns(text: str) -> Dict[str, str]:
    """Map lowercased profile handle -> 'urn:li:fsd_profile:ACoAA...' from an RSC flight body.

    Cards are laid out sequentially; the ACoAA id in the compose-message URL sits inside the
    span from a card key's first occurrence to the next distinct card key.
    """
    result: Dict[str, str] = {}
    if not isinstance(text, str) or not text:
        return result
    firsts: List[Tuple[int, str]] = []
    seen: set = set()
    for m in _CARD_KEY_RE.finditer(text):
        h = unquote(m.group(1)).lower()
        if h not in seen:
            seen.add(h)
            firsts.append((m.start(), h))
    for i, (start, handle) in enumerate(firsts):
        end = firsts[i + 1][0] if i + 1 < len(firsts) else len(text)
        m = _ACO_RE.search(text, start, end)
        if m:
            result[handle] = f"urn:li:fsd_profile:{m.group(1)}"
    return result


def detect_block_url(url: str, title: str = "") -> Optional[str]:
    """Return a block reason if the URL/title looks like an authwall/login/checkpoint/captcha page."""
    path = urlparse(url or "").path
    if _BLOCK_URL_RE.search(path):
        return f"blocked page: {path}"
    if title and _BLOCK_TITLE_RE.search(title) and "/mynetwork/" not in path:
        return f"blocked page title: {title[:60]}"
    return None


# ==============================================================================
# Store
# ==============================================================================

SCHEMA_CONNECTIONS = """
CREATE TABLE IF NOT EXISTS connections (
    profile_url VARCHAR PRIMARY KEY,
    urn_id VARCHAR,
    name VARCHAR NOT NULL,
    headline VARCHAR,
    current_company VARCHAR,
    location VARCHAR,
    connected_at TIMESTAMP,
    connected_at_text VARCHAR,
    first_seen_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    source VARCHAR
)
"""


def _naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


_COMPANY_SUFFIX_RE = re.compile(
    r"(?:[,\s]+(?:inc|llc|ltd|corp|corporation|co|gmbh|plc|incorporated|limited)\.?"
    r"|\.(?:com|io|ai|co|app|dev|net|org))\s*$",
    re.IGNORECASE,
)


def normalize_company(name: Optional[str]) -> Optional[str]:
    """Canonicalize a company name: 'Pendo.io' / 'Pendo, Inc.' -> 'Pendo'. Raw headline is never touched."""
    if not name:
        return None
    s = re.sub(r"\s+", " ", str(name)).strip(" \t-|,.;:")
    for _ in range(4):
        n = _COMPANY_SUFFIX_RE.sub("", s).strip(" \t-|,.;:")
        if n == s or not n:
            break
        s = n
    s = re.sub(r"^the\s+", "", s, flags=re.IGNORECASE) if len(s) > 4 else s
    return s or None


def ensure_schema(conn: Any) -> None:
    """Create/extend our own connections table (segments/queries hold JSON lists of provenance)."""
    conn.execute(SCHEMA_CONNECTIONS)
    conn.execute("ALTER TABLE connections ADD COLUMN IF NOT EXISTS segments VARCHAR")
    conn.execute("ALTER TABLE connections ADD COLUMN IF NOT EXISTS queries VARCHAR")


def merge_provenance(existing: Optional[str], new: List[str]) -> str:
    """Union a JSON-list string with new items; order-stable, idempotent."""
    try:
        cur = json.loads(existing) if existing else []
    except Exception:
        cur = []
    if not isinstance(cur, list):
        cur = []
    for item in new:
        if item and item not in cur:
            cur.append(item)
    return json.dumps(cur)


def record_search_hits(
    db: NetworkDatabase, conns: List[Connection], segment: str, query: str
) -> Tuple[int, int]:
    """Store search hits (degree already confirmed 1st by the parser) and merge provenance.

    Returns (new_rows, already_known). Existing connected_at is kept (upsert COALESCEs);
    new rows keep connected_at NULL unless the page supplied one.
    """
    if not conns:
        return 0, 0
    urls = list({c.profile_url for c in conns})
    ph = ",".join("?" * len(urls))
    known = {
        r[0]: (r[1], r[2])
        for r in db.conn.execute(
            f"SELECT profile_url, segments, queries FROM connections WHERE profile_url IN ({ph})", urls
        ).fetchall()
    }
    upsert_connections(db, conns)
    for u in urls:
        seg, qs = known.get(u, (None, None))
        db.conn.execute(
            "UPDATE connections SET segments = ?, queries = ? WHERE profile_url = ?",
            [merge_provenance(seg, [segment]), merge_provenance(qs, [query]), u],
        )
    return len(urls) - len(known), len(known)


def open_db(db_path: Optional[str] = None, max_wait: float = 60.0) -> NetworkDatabase:
    """Open NetworkDatabase, retrying with backoff on DuckDB file-lock conflicts (up to max_wait s)."""
    deadline = time.monotonic() + max_wait
    delay = 0.5
    while True:
        try:
            db = NetworkDatabase(db_path=db_path)
            ensure_schema(db.conn)
            return db
        except Exception as exc:
            msg = str(exc).lower()
            locked = "lock" in msg or "conflicting" in msg or "could not set" in msg
            if not locked or time.monotonic() + delay > deadline:
                raise
            print(f"[!] DB locked, retrying in {delay:.1f}s ...", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 8.0)


def upsert_connections(db: NetworkDatabase, conns: List[Connection]) -> Tuple[int, int]:
    """Idempotently store connections (+ mirror into contacts). Returns (connections_upserted, contacts_upserted).

    first_seen_at is preserved on conflict; last_seen_at always advances. connected_at fields only
    overwrite when the new value is non-null.
    """
    if not conns:
        return 0, 0
    deduped: Dict[str, Connection] = {}
    for c in conns:
        deduped[c.profile_url] = c
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = [
        (
            c.profile_url,
            c.member_urn or c.urn_id,
            c.name,
            c.headline,
            normalize_company(c.current_company),
            c.location,
            _naive_utc(c.connected_at),
            c.connected_at_text,
            now,
            now,
            c.source,
        )
        for c in deduped.values()
    ]
    db.conn.executemany(
        """
        INSERT INTO connections (profile_url, urn_id, name, headline, current_company, location,
                                 connected_at, connected_at_text, first_seen_at, last_seen_at, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (profile_url) DO UPDATE SET
            urn_id = COALESCE(EXCLUDED.urn_id, connections.urn_id),
            name = EXCLUDED.name,
            headline = EXCLUDED.headline,
            current_company = EXCLUDED.current_company,
            location = COALESCE(EXCLUDED.location, connections.location),
            connected_at = COALESCE(EXCLUDED.connected_at, connections.connected_at),
            connected_at_text = COALESCE(EXCLUDED.connected_at_text, connections.connected_at_text),
            last_seen_at = EXCLUDED.last_seen_at,
            source = COALESCE(connections.source, EXCLUDED.source)
        """,
        rows,
    )

    # Mirror into contacts without clobbering scores/mutuals that upsert_contacts would reset.
    contact_objs: List[LinkedInContact] = []
    urls = list(deduped.keys())
    existing: Dict[str, tuple] = {}
    for i in range(0, len(urls), 500):
        chunk = urls[i:i + 500]
        ph = ",".join("?" * len(chunk))
        for r in db.conn.execute(
            f"SELECT profile_url, role_match_score, company_match_score, mutual_count, mutual_sample, "
            f"location, current_company FROM contacts WHERE profile_url IN ({ph})",
            chunk,
        ).fetchall():
            existing[r[0]] = r
    for c in deduped.values():
        ex = existing.get(c.profile_url)
        try:
            sample = json.loads(ex[4]) if ex and ex[4] else []
        except Exception:
            sample = []
        contact_objs.append(
            LinkedInContact(
                urn_id=c.urn_id,
                name=c.name,
                headline=c.headline,
                profile_url=c.profile_url,
                degree="1st",
                location=c.location or (ex[5] if ex else None),
                current_company=c.current_company or (ex[6] if ex else None),
                mutual_count=int(ex[3] or 0) if ex else 0,
                mutual_sample=sample if isinstance(sample, list) else [],
                role_match_score=float(ex[1] or 0.0) if ex else 0.0,
                company_match_score=float(ex[2] or 0.0) if ex else 0.0,
                source="dom_selectolax",
            )
        )
    n_contacts = db.upsert_contacts(contact_objs)
    return len(rows), n_contacts


def list_connection_rows(
    db: NetworkDatabase, company: Optional[str] = None, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Return stored connections newest-connected first as plain dicts."""
    q = (
        "SELECT profile_url, urn_id, name, headline, current_company, location, connected_at, "
        "connected_at_text, first_seen_at, last_seen_at, source FROM connections"
    )
    params: list = []
    if company and company.strip():
        q += " WHERE current_company ILIKE ?"
        params.append(f"%{company.strip()}%")
    q += " ORDER BY connected_at DESC NULLS LAST, name ASC"
    if limit and int(limit) > 0:
        q += " LIMIT ?"
        params.append(int(limit))
    cols = ["profile_url", "urn_id", "name", "headline", "current_company", "location", "connected_at",
            "connected_at_text", "first_seen_at", "last_seen_at", "source"]
    rows = []
    for r in db.conn.execute(q, params).fetchall():
        d = dict(zip(cols, r))
        for k in ("connected_at", "first_seen_at", "last_seen_at"):
            if isinstance(d[k], datetime):
                d[k] = d[k].isoformat()
        rows.append(d)
    return rows


# ==============================================================================
# Capture
# ==============================================================================

@dataclass
class CaptureResult:
    connections: List[Connection] = field(default_factory=list)
    stop_reason: str = ""
    reported_total: Optional[int] = None
    scrolls: int = 0
    elapsed_sec: float = 0.0
    urns_seen: int = 0
    pagination_responses: int = 0
    notes: List[str] = field(default_factory=list)


_EXTRACT_JS = r"""
(() => {
  const seen = new Set(); const cards = [];
  for (const c of document.querySelectorAll('[componentkey^="ConnectionCard_"]')) {
    const key = c.getAttribute('componentkey');
    if (seen.has(key)) continue; seen.add(key);
    const a = c.querySelector('a[href*="/in/"]');
    cards.push({key, href: a ? a.href : null,
                lines: c.innerText.split('\n').map(s => s.trim()).filter(Boolean)});
  }
  const m = document.body.innerText.match(/([\d,]+)\s+connections?\b/i);
  return JSON.stringify({href: location.href, title: document.title, vis: document.visibilityState,
                         total: m ? parseInt(m[1].replace(/,/g, ''), 10) : null, cards});
})()
"""

_SCROLL_JS = (
    "(() => { const m = document.querySelector('main'); if (m) m.scrollTop = m.scrollHeight; "
    "window.scrollTo(0, document.documentElement.scrollHeight); return true; })()"
)


class _Cdp:
    """Minimal single-reader CDP client over one page websocket."""

    def __init__(self, ws: Any) -> None:
        self.ws = ws
        self.mid = 0
        self.pending: Dict[int, asyncio.Future] = {}
        self.handlers: List[Callable[[dict], None]] = []
        self.closed = False
        self._task = asyncio.create_task(self._reader())

    async def _reader(self) -> None:
        try:
            async for raw in self.ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if "id" in msg:
                    fut = self.pending.pop(msg["id"], None)
                    if fut and not fut.done():
                        if "error" in msg:
                            fut.set_exception(RuntimeError(msg["error"].get("message", "CDP error")))
                        else:
                            fut.set_result(msg.get("result", {}))
                else:
                    for h in self.handlers:
                        try:
                            h(msg)
                        except Exception:
                            pass
        except Exception:
            pass
        finally:
            self.closed = True
            for f in self.pending.values():
                if not f.done():
                    f.set_exception(ConnectionError("CDP websocket closed"))
            self.pending.clear()

    async def call(self, method: str, params: Optional[dict] = None, timeout: float = 15.0) -> dict:
        self.mid += 1
        mid = self.mid
        fut = asyncio.get_running_loop().create_future()
        self.pending[mid] = fut
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        return await asyncio.wait_for(fut, timeout=timeout)

    async def eval(self, expr: str) -> Any:
        res = await self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        return res.get("result", {}).get("value")

    def stop(self) -> None:
        self._task.cancel()


async def _connect_ws(ws_url: str) -> Any:
    import websockets
    last: Optional[Exception] = None
    for attempt in range(2):
        try:
            return await websockets.connect(ws_url, max_size=80 * 1024 * 1024)
        except Exception as exc:  # Chrome rejects rapid handshakes with HTTP 500
            last = exc
            await asyncio.sleep(2.0)
    raise ConnectionError(f"CDP websocket connect failed after retry: {last}")


async def capture_connections(
    ws_url: str,
    inst_name: str,
    max_connections: int = 3000,
    max_minutes: float = 20.0,
    on_checkpoint: Optional[Callable[[List[Connection]], None]] = None,
    checkpoint_every: int = 100,
    min_wait: float = 2.0,
    max_wait: float = 5.0,
    no_new_limit: int = 3,
    log: Callable[[str], None] = lambda s: print(s, file=sys.stderr),
) -> CaptureResult:
    """Human-paced, read-only capture of the connections list on one dedicated tab.

    Stops on: no_new_limit consecutive scrolls without new connections, max_connections,
    max_minutes, all reported connections captured, or any block signal (authwall/login/
    checkpoint/captcha URL, HTTP 429/999). Checkpoints unsaved connections every `checkpoint_every`
    via on_checkpoint and flushes the remainder on exit (including errors/interrupts).
    """
    min_wait = max(2.0, float(min_wait))  # never faster than 2s
    max_wait = max(min_wait, float(max_wait))
    res = CaptureResult()
    started = time.monotonic()
    deadline = started + max_minutes * 60.0

    seen: Dict[str, Connection] = {}
    unsaved: List[Connection] = []
    urn_map: Dict[str, str] = {}
    interesting: Dict[str, str] = {}
    fetched: set = set()
    tasks: set = set()
    state: Dict[str, Any] = {"block": None}

    ws = await _connect_ws(ws_url)
    cdp = _Cdp(ws)

    def is_pagination(url: str) -> bool:
        return "rsc-action/actions/pagination" in url and "connectionsList" in url

    def add_new(conns: List[Connection]) -> int:
        n = 0
        for c in conns:
            if c.profile_url not in seen:
                seen[c.profile_url] = c
                unsaved.append(c)
                n += 1
        return n

    async def fetch_body(rid: str, url: str) -> None:
        try:
            r = await cdp.call("Network.getResponseBody", {"requestId": rid}, timeout=10)
            body = r.get("body", "") or ""
            if r.get("base64Encoded"):
                body = base64.b64decode(body).decode("utf-8", errors="replace")
            if not body:
                return
            if "/voyager/api/" in url:
                try:
                    add_new(parse_voyager_connections_json(json.loads(body)))
                except Exception:
                    pass
            else:
                urn_map.update(extract_member_urns(body))
                if is_pagination(url):
                    res.pagination_responses += 1
        except Exception:
            pass

    def on_event(msg: dict) -> None:
        method = msg.get("method")
        p = msg.get("params", {})
        if method == "Network.responseReceived":
            r = p.get("response", {})
            url = r.get("url", "")
            status = int(r.get("status", 0) or 0)
            host = urlparse(url).netloc
            if host.endswith("linkedin.com") and p.get("type") in ("Document", "XHR", "Fetch"):
                if status in (429, 999):
                    state["block"] = f"HTTP {status} from {urlparse(url).path[:60]}"
                elif status in (401, 403) and is_pagination(url):
                    state["block"] = f"HTTP {status} on connections pagination"
            rid = p.get("requestId")
            if rid and (is_pagination(url) or "/mynetwork/invite-connect/connections" in url
                        or ("/voyager/api/" in url and "onnection" in url)):
                interesting[rid] = url
        elif method == "Network.loadingFinished":
            rid = p.get("requestId")
            if rid in interesting and rid not in fetched:
                fetched.add(rid)
                t = asyncio.create_task(fetch_body(rid, interesting[rid]))
                tasks.add(t)
                t.add_done_callback(tasks.discard)
        elif method == "Page.frameNavigated":
            fr = p.get("frame", {})
            if not fr.get("parentId"):
                reason = detect_block_url(fr.get("url", ""))
                if reason:
                    state["block"] = reason

    cdp.handlers.append(on_event)

    def flush(force: bool = False) -> None:
        if not unsaved or on_checkpoint is None:
            return
        if force or len(unsaved) >= checkpoint_every:
            for c in unsaved:
                u = urn_map.get(c.profile_url.rstrip("/").split("/in/")[-1].lower())
                if u:
                    c.member_urn = u
            batch = list(unsaved)
            unsaved.clear()
            on_checkpoint(batch)
            log(f"[*] checkpoint: saved {len(batch)} (total captured {len(seen)})")

    try:
        await cdp.call("Network.enable")
        await cdp.call("Page.enable")
        # The connections pager only fires when the tab is visible.
        await cdp.call("Page.bringToFront")

        # 1. auth check on the feed
        await cdp.call("Page.navigate", {"url": FEED_URL})
        await asyncio.sleep(4.0)
        info = json.loads(await cdp.eval("JSON.stringify({href: location.href, title: document.title})") or "{}")
        reason = state["block"] or detect_block_url(info.get("href", ""), info.get("title", ""))
        if reason:
            res.stop_reason = f"BLOCKED (auth check): {reason}"
            return res
        log(f"[*] auth ok: {urlparse(info.get('href', '')).path}")
        await asyncio.sleep(random.uniform(1.5, 2.5))

        # 2. connections page
        await cdp.call("Page.navigate", {"url": CONNECTIONS_URL})
        await asyncio.sleep(6.0)

        no_new = 0
        hidden_streak = 0
        while True:
            raw = await cdp.eval(_EXTRACT_JS)
            data = json.loads(raw) if raw else {}
            reason = state["block"] or detect_block_url(data.get("href", ""), data.get("title", ""))
            if reason:
                res.stop_reason = f"BLOCKED: {reason}"
                break
            if data.get("total") and not res.reported_total:
                res.reported_total = data["total"]
            new = add_new(parse_dom_cards(data.get("cards", [])))
            if data.get("vis") != "visible":
                # The lazy pager only fires in a visible tab (another session may have taken focus).
                # A hidden tab is not evidence that the list ended, so do not count it as "no new".
                hidden_streak += 1
                if hidden_streak > 8:
                    res.stop_reason = "tab stayed hidden (pager cannot load)"
                    break
                await cdp.call("Page.bringToFront")
                await asyncio.sleep(random.uniform(min_wait, max_wait))
                continue
            hidden_streak = 0
            if new:
                no_new = 0
            else:
                no_new += 1
            flush()
            log(f"[*] scroll {res.scrolls}: +{new} new, total {len(seen)}"
                f"{'/' + str(res.reported_total) if res.reported_total else ''}")

            if len(seen) >= max_connections:
                res.stop_reason = f"max_connections cap ({max_connections})"
                break
            if res.reported_total and len(seen) >= res.reported_total:
                res.stop_reason = "captured all reported connections"
                break
            if no_new >= no_new_limit:
                res.stop_reason = f"{no_new_limit} consecutive scrolls with no new connections"
                break
            if time.monotonic() >= deadline:
                res.stop_reason = f"time cap ({max_minutes} min)"
                break
            if cdp.closed:
                res.stop_reason = "CDP websocket closed"
                break

            await cdp.call("Page.bringToFront")
            await cdp.eval(_SCROLL_JS)
            res.scrolls += 1
            await asyncio.sleep(random.uniform(min_wait, max_wait))

        # let any in-flight body fetches finish, then apply URNs
        if tasks:
            await asyncio.wait(list(tasks), timeout=5.0)
    except (KeyboardInterrupt, asyncio.CancelledError):
        res.stop_reason = res.stop_reason or "interrupted"
        raise
    except Exception as exc:
        res.stop_reason = res.stop_reason or f"error: {exc}"
        res.notes.append(str(exc))
    finally:
        try:
            for c in seen.values():
                u = urn_map.get(c.profile_url.rstrip("/").split("/in/")[-1].lower())
                if u:
                    c.member_urn = u
            flush(force=True)
        finally:
            res.connections = list(seen.values())
            res.urns_seen = len(urn_map)
            res.elapsed_sec = time.monotonic() - started
            cdp.stop()
            try:
                await ws.close()
            except Exception:
                pass
    return res


# ==============================================================================
# Browser instance / tab selection (never touches other sessions' instances)
# ==============================================================================

def resolve_linkedin_instance(profile: str = "linkedin") -> Tuple[str, int]:
    """Return (inst_name, port) for the authenticated 'linkedin' profile instance only."""
    from profile_manager import get_active_instances, launch_profile, get_profile_path

    profile_dir = str(get_profile_path(profile).resolve())
    registry: Dict[str, Any] = {}
    try:
        registry = json.loads(Path("/tmp/chrome-agent/registry.json").read_text())
    except Exception:
        pass
    for inst in get_active_instances():
        name = inst.get("name")
        if name in FORBIDDEN_INSTANCES:
            continue
        if registry.get(name, {}).get("user_data_dir") == profile_dir:
            return name, int(inst["port"])
    inst_name = launch_profile(profile, headless=False)
    for inst in get_active_instances():
        if inst["name"] == inst_name and inst_name not in FORBIDDEN_INSTANCES:
            return inst_name, int(inst["port"])
    raise RuntimeError(f"Could not locate a running '{profile}' profile instance")


def pick_tab_ws_url(port: int) -> Tuple[str, Optional[str]]:
    """Choose one dedicated tab: an existing blank tab, else open a new one. Returns (ws_url, created_id)."""
    def _json(path: str, method: str = "GET") -> Any:
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    for t in _json("/json"):
        if t.get("type") == "page" and t.get("url", "") in ("chrome://newtab/", "about:blank") and t.get("webSocketDebuggerUrl"):
            return t["webSocketDebuggerUrl"], None
    t = _json("/json/new?about:blank", method="PUT")
    return t["webSocketDebuggerUrl"], t.get("id")


# ==============================================================================
# CLI handlers (wired into cli.py as `ingest-connections` / `list-connections`)
# ==============================================================================

# ==============================================================================
# Search plan (offline). Live search is gated until recon + a results parser exist.
# ==============================================================================

SEARCH_PARSER_READY = False  # flip only after recon of the results payload and user approval
SEGMENTS = ("S1", "S2", "S3", "S4")
STATUS_ORDER = ["interviewing", "networking", "drafting", "ready", "applied", "researching"]
S4_TITLES = ["VP Marketing", "Head of Growth", "Director Marketing Technology", "Head of Web", "CMO", "Founder"]
_FALLBACK_ROLES = ["Marketing Engineer", "Growth Engineer", "Senior Web Developer", "Marketing Web Leader"]
_FALLBACK_PLATFORMS = ["Webflow", "HubSpot", "Marketo", "Sanity", "Contentful"]
SEARCH_BASE = "https://www.linkedin.com/search/results/people/"


def build_search_url(keywords: str, page: int = 1) -> str:
    """People search restricted to 1st-degree (network F). Page 1 carries no &page param."""
    from urllib.parse import quote
    url = f"{SEARCH_BASE}?keywords={quote(keywords)}&network=%5B%22F%22%5D&origin=FACETED_SEARCH"
    return url if page <= 1 else f"{url}&page={page}"


def pipeline_company_order(pipeline_path: Optional[str] = None) -> List[str]:
    """Active pipeline companies ordered Interviewing, Networking, Drafting, Ready, Applied, Researching."""
    try:
        import entity_matcher as em
        path = Path(os.path.expanduser(pipeline_path or em._DEFAULT_PIPELINE_PATH))
        text = path.read_text(encoding="utf-8")
        ci = si = None
        by_status: Dict[str, List[str]] = {s: [] for s in STATUS_ORDER}
        for line in text.splitlines():
            if not line.lstrip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            low = [c.lower() for c in cells]
            if "company" in low and "status" in low:
                ci, si = low.index("company"), low.index("status")
                continue
            if ci is None or si is None or len(cells) <= max(ci, si):
                continue
            status = low[si]
            if status not in by_status:
                continue
            one_row = f"| Company | Status |\n|---|---|\n| {cells[ci]} | {status} |"
            by_status[status] += em._parse_pipeline_companies(one_row)
        return list(dict.fromkeys(c for s in STATUS_ORDER for c in by_status[s]))
    except Exception:
        return []


def load_plan_targets(core_cv_path: Optional[str] = None, pipeline_path: Optional[str] = None) -> Dict[str, List[str]]:
    """Derive query inputs from the core CV + pipeline via entity_matcher (read-only); fall back gracefully."""
    roles: List[str] = []
    platforms: List[str] = []
    companies: List[str] = []
    try:
        import entity_matcher as em
        t = em.derive_targets_from_core_cv(core_cv_path, pipeline_path)
        roles = list(t.get("role_titles") or [])
        platforms = list(t.get("platform_terms") or [])
        companies = list(t.get("tier_a") or [])
    except Exception:
        pass
    ordered = pipeline_company_order(pipeline_path)
    if ordered:
        companies = ordered
    return {
        "S1": roles or list(_FALLBACK_ROLES),
        "S2": [p.title() if p.islower() else p for p in platforms] or list(_FALLBACK_PLATFORMS),
        "S3": companies,
        "S4": list(S4_TITLES),
    }


def build_query_plan(
    segment: str = "all",
    max_pages: int = 3,
    max_requests: int = 60,
    targets: Optional[Dict[str, List[str]]] = None,
) -> List[Dict[str, Any]]:
    """Ordered page-load requests. Page 1 of every query first, then page 2, ... capped at max_requests.

    Each item: {segment, query, page, url}. Later pages are conditional at run time (stop when a page
    returns <10 rows or no new rows), so the plan is an upper bound.
    """
    seg = str(segment or "all").upper()
    chosen = list(SEGMENTS) if seg == "ALL" else [seg]
    bad = [s for s in chosen if s not in SEGMENTS]
    if bad:
        raise ValueError(f"unknown segment {bad}; use S1|S2|S3|S4|all")
    targets = targets if targets is not None else load_plan_targets()
    queries: List[Tuple[str, str]] = []
    seen: set = set()
    for s in chosen:
        for q in targets.get(s, []):
            key = (s, q.strip().lower())
            if q.strip() and key not in seen:
                seen.add(key)
                queries.append((s, q.strip()))
    plan: List[Dict[str, Any]] = []
    for page in range(1, max(1, int(max_pages)) + 1):
        for s, q in queries:
            if len(plan) >= int(max_requests):
                return plan
            plan.append({"segment": s, "query": q, "page": page, "url": build_search_url(q, page)})
    return plan


def cmd_search_connections(args: argparse.Namespace) -> None:
    """Query-driven read of people search filtered to 1st-degree. --dry-run prints the plan only."""
    plan = build_query_plan(args.segment, args.max_pages, args.max_requests)
    if args.dry_run:
        by_seg: Dict[str, int] = {}
        for p in plan:
            by_seg[p["segment"]] = by_seg.get(p["segment"], 0) + 1
        print(f"[*] Query plan: {len(plan)} page loads (cap {args.max_requests}); per segment {by_seg}")
        for i, p in enumerate(plan, 1):
            print(f"{i:>3} {p['segment']} p{p['page']} {p['query']!r}\n      {p['url']}")
        print("[*] --dry-run: no browser opened, no network calls made.")
        return
    if not SEARCH_PARSER_READY:
        print("[!] search-connections live run is disabled: the recon step for the people-search results "
              "payload has not been done or approved, so no results parser exists. Nothing was loaded. "
              "Use --dry-run to inspect the plan.", file=sys.stderr)
        sys.exit(3)
    print("[!] live search path not implemented", file=sys.stderr)
    sys.exit(3)


# ==============================================================================
# Connection <-> post join (by profile handle / company slug; read-only)
# ==============================================================================

def connection_handle(profile_url: Optional[str]) -> Optional[str]:
    """Lowercased public handle from a connections.profile_url (/in/{handle})."""
    m = re.search(r"/in/([^/?#]+)", profile_url or "", re.IGNORECASE)
    return unquote(m.group(1)).lower() if m else None


def author_handle(author_id: Optional[str]) -> Optional[str]:
    """Lowercased handle from a post author_id of the form urn:li:member:{handle}."""
    m = re.match(r"urn:li:member:(.+)$", (author_id or "").strip(), re.IGNORECASE)
    return m.group(1).lower() if m else None


def _slug_key(text: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _company_keys(name: Optional[str]) -> set:
    keys = {_slug_key(name), _slug_key(normalize_company(name))}
    keys.discard("")
    return keys


def _engagement(row: Dict[str, Any]) -> int:
    return sum(int(row.get(k) or 0) for k in ("like_count", "comment_count", "repost_count"))


def connections_with_posts(
    db_path: Optional[str] = None, company: Optional[str] = None, db: Optional[NetworkDatabase] = None
) -> List[Dict[str, Any]]:
    """Per connection: stored post counts and engagement, joined by handle (person authors,
    case-insensitive) and by company slug (company authors vs the connection's current_company).
    Sorted by post count desc, then name. Pass an open `db` to reuse it (e.g. :memory:)."""
    own = db is None
    if own:
        db = open_db(db_path)
    try:
        ensure_schema(db.conn)
        conns = list_connection_rows(db, company=company)
        cols = ["author_type", "author_id", "like_count", "comment_count", "repost_count"]
        posts = [dict(zip(cols, r)) for r in db.conn.execute(
            "SELECT author_type, author_id, like_count, comment_count, repost_count FROM posts").fetchall()]
    finally:
        if own:
            db.close()
    by_handle: Dict[str, List[int]] = {}
    by_slug: Dict[str, List[int]] = {}
    for p in posts:
        eng = _engagement(p)
        if p["author_type"] == "company":
            k = _slug_key(p["author_id"])
            if k:
                by_slug.setdefault(k, []).append(eng)
        else:
            h = author_handle(p["author_id"])
            if h:
                by_handle.setdefault(h, []).append(eng)
    out: List[Dict[str, Any]] = []
    for c in conns:
        handle = connection_handle(c["profile_url"])
        own_e = by_handle.get(handle or "", [])
        comp_e: List[int] = []
        for k in _company_keys(c["current_company"]):
            comp_e = by_slug.get(k, [])
            if comp_e:
                break
        allp = own_e + comp_e
        out.append({
            "name": c["name"], "profile_url": c["profile_url"], "handle": handle,
            "current_company": c["current_company"],
            "posts": len(allp), "own_posts": len(own_e), "company_posts": len(comp_e),
            "total_engagement": sum(allp),
            "avg_engagement": round(sum(allp) / len(allp), 1) if allp else 0.0,
        })
    out.sort(key=lambda r: (-r["posts"], (r["name"] or "").lower()))
    return out


def _summarize(conns: List[Connection]) -> str:
    n = len(conns)
    dated = sum(1 for c in conns if c.connected_at)
    comp = sum(1 for c in conns if c.current_company)
    return f"{n} connections, {dated} with connected-at, {comp} with company"


def cmd_ingest_connections(args: argparse.Namespace) -> None:
    """Read-only ingest of 1st-degree connections into DuckDB (or parse-only with --dry-run)."""
    inst_name, port = resolve_linkedin_instance(getattr(args, "profile", None) or "linkedin")
    print(f"[*] Using instance '{inst_name}' on port {port}", file=sys.stderr)
    ws_url, created = pick_tab_ws_url(port)
    time.sleep(1.5)

    db: Optional[NetworkDatabase] = None
    stored = {"n": 0}
    if not args.dry_run:
        db = open_db(args.db)

        def checkpoint(batch: List[Connection]) -> None:
            upsert_connections(db, batch)  # type: ignore[arg-type]
            stored["n"] += len(batch)
    else:
        checkpoint = None  # type: ignore[assignment]

    try:
        result = asyncio.run(
            capture_connections(
                ws_url, inst_name,
                max_connections=args.max, max_minutes=args.max_minutes,
                on_checkpoint=checkpoint,
            )
        )
    finally:
        if db is not None:
            db.close()

    print(f"[+] Stop reason: {result.stop_reason}")
    print(f"[+] {_summarize(result.connections)}; reported total {result.reported_total}; "
          f"urns seen {result.urns_seen}; scrolls {result.scrolls}; {result.elapsed_sec:.0f}s")
    if args.dry_run:
        print("[*] --dry-run: nothing written.")
    else:
        print(f"[+] Upserted {stored['n']} connections (and mirrored into contacts).")
    if result.stop_reason.startswith("BLOCKED"):
        sys.exit(2)


def cmd_list_connections(args: argparse.Namespace) -> None:
    """List stored connections (--json for machine-readable output)."""
    if getattr(args, "with_posts", False):
        rows = connections_with_posts(args.db, company=args.company)
        if args.limit and int(args.limit) > 0:
            rows = rows[: int(args.limit)]
        if args.json:
            print(json.dumps(rows, indent=2, default=str))
            return
        print(f"{'NAME':<28} {'COMPANY':<24} {'OWN':>4} {'EMPLOYER PAGE':>13}")
        for r in rows:
            print(f"{(r['name'] or '')[:27]:<28} {(r['current_company'] or '')[:23]:<24} "
                  f"{r['own_posts']:>4} {r['company_posts']:>13}")
        print(f"\n{len(rows)} connections, {sum(1 for r in rows if r['own_posts'])} with posts of their own "
              f"(employer-page posts are shown separately and are not theirs)")
        return
    with open_db(args.db) as db:
        rows = list_connection_rows(db, company=args.company, limit=args.limit)
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return
    print(f"{'NAME':<28} {'COMPANY':<24} {'CONNECTED':<12} HEADLINE")
    for r in rows:
        ca = (r["connected_at"] or "")[:10]
        print(f"{(r['name'] or '')[:27]:<28} {(r['current_company'] or '')[:23]:<24} {ca:<12} {(r['headline'] or '')[:60]}")
    print(f"\n{len(rows)} connections")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Read-only LinkedIn connections ingest")
    sub = ap.add_subparsers(dest="action", required=True)
    a = sub.add_parser("ingest-connections")
    a.add_argument("--db", default=None)
    a.add_argument("--max", type=int, default=3000)
    a.add_argument("--max-minutes", type=float, default=20.0)
    a.add_argument("--profile", default="linkedin")
    a.add_argument("--dry-run", action="store_true")
    b = sub.add_parser("list-connections")
    b.add_argument("--db", default=None)
    b.add_argument("--company", default=None)
    b.add_argument("--limit", type=int, default=50)
    b.add_argument("--json", action="store_true")
    ns = ap.parse_args()
    (cmd_ingest_connections if ns.action == "ingest-connections" else cmd_list_connections)(ns)
