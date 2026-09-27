"""cdp_interceptor.py - Node 2a of Q4 pipeline: Passive CDP Interceptor for LinkedIn Voyager API.

Captures and parses live LinkedIn Voyager GraphQL search responses directly
from Chrome DevTools Protocol network traffic without DOM scraping or browser injection.
Complies with mps-writing-for-agents (tight, typed, canonical single source of truth).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure local imports resolve whether executed as a script or imported as a package
_CURRENT_DIR = Path(__file__).resolve().parent
if str(_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(_CURRENT_DIR))

# Single Source of Truth (Requirement 1)
try:
    from schemas import (
        LinkedInContact,
        NetworkDegree,
        Post,
        canonicalize_linkedin_post_url,
        canonicalize_linkedin_url,
        extract_company_slug_from_url,
    )
except ImportError:
    from .schemas import (  # type: ignore[no-redef]
        LinkedInContact,
        NetworkDegree,
        Post,
        canonicalize_linkedin_post_url,
        canonicalize_linkedin_url,
        extract_company_slug_from_url,
    )

import websockets

logger = logging.getLogger("q4.cdp_interceptor")

# Maximum WebSocket frame size (50MB to handle large base64 CDP payloads)
_MAX_WS_MESSAGE_SIZE = 50 * 1024 * 1024


def normalize_degree(val: Any) -> NetworkDegree:
    """Normalize network distance indicators into strict NetworkDegree literals."""
    if not val:
        return "Unknown"
    val_str = str(val).strip().upper()
    if val_str in ("1ST", "1", "DISTANCE_1", "FIRST_DEGREE"):
        return "1st"
    if val_str in ("2ND", "2", "DISTANCE_2", "SECOND_DEGREE"):
        return "2nd"
    if val_str in ("3RD", "3RD+", "3", "DISTANCE_3", "THIRD_DEGREE", "OUT_OF_NETWORK"):
        return "3rd+"
    m = re.search(r"\b(1st|2nd|3rd(?:\+)?)\b", val_str, re.IGNORECASE)
    if m:
        deg = m.group(1).lower()
        return "3rd+" if deg in ("3rd", "3rd+") else deg  # type: ignore[return-value]
    return "Unknown"


def extract_company_from_headline(headline: str) -> Optional[str]:
    """Extract inferred employer from member headline patterns ('at X', '@ X', '| X')."""
    if not headline:
        return None
    # Pattern: at Company or @ Company
    m = re.search(r"(?:^|\s)(?:at|@)\s+([^,|·•\n\(\)]+)", headline, re.IGNORECASE)
    if m:
        comp = m.group(1).strip()
        comp = re.sub(r"[.,;]+$", "", comp).strip()
        if comp:
            return comp
    # Pattern: Role | Company
    if " | " in headline:
        parts = headline.split(" | ")
        if len(parts) >= 2:
            return parts[-1].strip()
    return None


def extract_mutuals(text: str) -> Tuple[int, List[str]]:
    """Parse mutual connection count and member name samples from text snippets."""
    if not text:
        return 0, []
    count = 0
    sample: List[str] = []

    # 1. Count extraction: e.g. "12 mutual connections" or "1 mutual connection"
    m_count = re.search(r"(\d+)\s+mutual\s+connection", text, re.IGNORECASE)
    if m_count:
        count = int(m_count.group(1))
    elif re.search(r"\bmutual\s+connection", text, re.IGNORECASE):
        count = 1

    # 2. Sample name extraction: e.g. ": Alice Smith, Bob Jones and 2 others"
    if ":" in text:
        after_colon = text.split(":", 1)[1].strip()
        cleaned = re.sub(r"\s+and\s+\d+\s+other[s]?", "", after_colon, flags=re.IGNORECASE)
        parts = re.split(r",\s*|\s+and\s+", cleaned)
        for p in parts:
            p_clean = p.strip()
            if p_clean and not re.search(r"^\d+\s+other", p_clean, re.IGNORECASE):
                sample.append(p_clean)

    return count, sample


def extract_mutual_info(entity: dict) -> Tuple[int, List[str]]:
    """Extract mutual connection count and sample list from entity insights."""
    mutual_count = 0
    mutual_sample: List[str] = []

    # Direct properties if present
    if isinstance(entity.get("mutualCount"), int):
        mutual_count = entity["mutualCount"]
    if isinstance(entity.get("mutualSample"), list):
        mutual_sample = [str(x) for x in entity["mutualSample"] if x]

    # Gather text candidates from insightsResolutionResults, insights, or socialProof
    candidates: List[str] = []
    raw_insights = entity.get("insightsResolutionResults") or entity.get("insights")
    if isinstance(raw_insights, list):
        for item in raw_insights:
            if isinstance(item, str):
                candidates.append(item)
            elif isinstance(item, dict):
                # simpleInsight -> title -> text
                si = item.get("simpleInsight")
                if isinstance(si, dict):
                    t = si.get("title")
                    if isinstance(t, dict) and "text" in t:
                        candidates.append(str(t["text"]))
                    elif isinstance(t, str):
                        candidates.append(t)
                # insight -> text -> text
                ins = item.get("insight")
                if isinstance(ins, dict):
                    t = ins.get("text")
                    if isinstance(t, dict) and "text" in t:
                        candidates.append(str(t["text"]))
                    elif isinstance(t, str):
                        candidates.append(t)
                # direct text/title
                for key in ("text", "title"):
                    val = item.get(key)
                    if isinstance(val, dict) and "text" in val:
                        candidates.append(str(val["text"]))
                    elif isinstance(val, str):
                        candidates.append(val)

    # Fallback to secondarySubtitle / summary if insights list was empty
    if not candidates:
        for field in ("secondarySubtitle", "summary"):
            val = entity.get(field)
            txt = val.get("text", "") if isinstance(val, dict) else (val or "")
            if isinstance(txt, str) and "mutual" in txt.lower():
                candidates.append(txt)

    for cand in candidates:
        cnt, smp = extract_mutuals(cand)
        if cnt > mutual_count:
            mutual_count = cnt
        for s in smp:
            if s not in mutual_sample:
                mutual_sample.append(s)

    return mutual_count, mutual_sample


def _extract_single_contact(entity: dict) -> Optional[LinkedInContact]:
    """Extract and validate a single LinkedInContact model from an entity result dict.

    Returns None if the entity is not a personal profile (e.g. company, school, job).
    """
    if not isinstance(entity, dict):
        return None

    # 1. Navigation URL & Profile URL validation
    nav_url = (
        entity.get("navigationUrl")
        or entity.get("targetUrl")
        or entity.get("url")
        or ""
    )
    if not nav_url and "publicIdentifier" in entity:
        nav_url = f"https://www.linkedin.com/in/{entity['publicIdentifier']}"

    if not nav_url:
        return None

    if nav_url.startswith("/in/"):
        nav_url = f"https://www.linkedin.com{nav_url}"

    clean_url = canonicalize_linkedin_url(nav_url)
    # Strictly filter out non-person entities (companies, groups, schools, jobs)
    if not clean_url or "/in/" not in clean_url:
        return None

    # 2. Name extraction from title
    title_val = entity.get("title")
    name_raw = title_val.get("text", "") if isinstance(title_val, dict) else (title_val or "")
    if not isinstance(name_raw, str):
        name_raw = str(name_raw)

    # Clean name: remove badge text or newlines often attached in Voyager titles
    name_clean = re.sub(r"[\n·•].*$", "", name_raw).strip()
    if not name_clean:
        # Fallback to secondary fields if available
        name_clean = (entity.get("actorTitle") or "").strip()
    if not name_clean:
        return None

    # 3. Headline from primarySubtitle or subtitle
    sub_val = entity.get("primarySubtitle") or entity.get("subtitle")
    headline = sub_val.get("text", "") if isinstance(sub_val, dict) else (sub_val or "")
    headline = headline.strip() if isinstance(headline, str) else ""

    # 4. Location from secondarySubtitle (excluding mutual connections text)
    sec_sub = entity.get("secondarySubtitle")
    sec_text = sec_sub.get("text", "") if isinstance(sec_sub, dict) else (sec_sub or "")
    location: Optional[str] = None
    if isinstance(sec_text, str) and sec_text.strip():
        sec_clean = sec_text.strip()
        if "mutual" not in sec_clean.lower():
            location = sec_clean
    if not location and "location" in entity:
        loc_val = entity["location"]
        location = loc_val.get("text", "") if isinstance(loc_val, dict) else str(loc_val)

    # 5. Network degree
    degree: NetworkDegree = "Unknown"
    badge = entity.get("badgeText")
    badge_text = badge.get("text") if isinstance(badge, dict) else badge
    if badge_text:
        degree = normalize_degree(badge_text)

    if degree == "Unknown":
        deg_field = entity.get("degree") or entity.get("networkDistance")
        if deg_field:
            degree = normalize_degree(deg_field)

    if degree == "Unknown":
        # Check raw title / subtitle for embedded degree badges like " · 2nd"
        for field in ("title", "primarySubtitle", "secondarySubtitle"):
            fv = entity.get(field)
            ft = fv.get("text") if isinstance(fv, dict) else fv
            if ft and isinstance(ft, str):
                d = normalize_degree(ft)
                if d != "Unknown":
                    degree = d
                    break

    # 6. Mutual connections count and sample
    mutual_count, mutual_sample = extract_mutual_info(entity)

    # 7. Current company
    company = entity.get("currentCompany") or entity.get("company")
    if isinstance(company, dict):
        company = company.get("name") or company.get("text")
    if not company and headline:
        company = extract_company_from_headline(headline)

    # 8. URN Identifier
    urn_id = (
        entity.get("trackingUrn")
        or entity.get("entityUrn")
        or entity.get("memberUrn")
        or entity.get("urn")
    )
    if not urn_id:
        handle = clean_url.rstrip("/").split("/in/")[-1]
        urn_id = f"urn:li:fsd_profile:{handle}"

    return LinkedInContact(
        urn_id=urn_id,
        name=name_clean,
        headline=headline,
        profile_url=clean_url,
        degree=degree,
        location=location,
        current_company=company,
        mutual_count=mutual_count,
        mutual_sample=mutual_sample,
        source="cdp_voyager_graphql",
    )


def _collect_entity_dicts(
    obj: Any,
    collected: List[dict],
    seen_ids: Set[int],
    seen_entity_ids: Set[int],
) -> None:
    """Recursively collect entityResult candidate dictionaries across Voyager JSON structures."""
    if id(obj) in seen_ids:
        return
    seen_ids.add(id(obj))

    if isinstance(obj, dict):
        # Match wrapper object containing entityResult
        if "entityResult" in obj and isinstance(obj["entityResult"], dict):
            ent = obj["entityResult"]
            if id(ent) not in seen_entity_ids:
                seen_entity_ids.add(id(ent))
                collected.append(ent)
        elif "EntityResult" in obj and isinstance(obj["EntityResult"], dict):
            ent = obj["EntityResult"]
            if id(ent) not in seen_entity_ids:
                seen_entity_ids.add(id(ent))
                collected.append(ent)
        # Match entity result dictionary directly (e.g. within included array or items)
        elif ("navigationUrl" in obj or "targetUrl" in obj) and "title" in obj:
            if id(obj) not in seen_entity_ids:
                seen_entity_ids.add(id(obj))
                collected.append(obj)

        for val in obj.values():
            _collect_entity_dicts(val, collected, seen_ids, seen_entity_ids)

    elif isinstance(obj, list):
        for item in obj:
            _collect_entity_dicts(item, collected, seen_ids, seen_entity_ids)


def parse_voyager_json(payload: dict) -> List[LinkedInContact]:
    """Parse Voyager GraphQL search cluster responses into structured LinkedInContact records.

    Traverses Voyager GraphQL payloads (including search clusters, nested item wrappers,
    and included model arrays), extracts title, subtitle, navigationUrl, degree, and mutuals,
    canonicalizes profile URLs, and deduplicates contacts.
    """
    if not isinstance(payload, dict):
        return []

    collected_dicts: List[dict] = []
    _collect_entity_dicts(
        obj=payload,
        collected=collected_dicts,
        seen_ids=set(),
        seen_entity_ids=set(),
    )

    contacts: List[LinkedInContact] = []
    seen_urls: Set[str] = set()

    for ent in collected_dicts:
        contact = _extract_single_contact(ent)
        if contact and contact.profile_url not in seen_urls:
            seen_urls.add(contact.profile_url)
            contacts.append(contact)

    return contacts


def _index_entities_by_urn(included: List[dict]) -> Dict[str, dict]:
    """Build an entityUrn -> entity dict index from a Voyager 'included' array.

    Feed payloads (company Posts tab / person Activity tab) normalize every referenced
    object into a flat 'included' list and cross-reference them via URN-string fields
    (e.g. '*socialDetail'). This index is the lookup table that resolves those refs.
    """
    index: Dict[str, dict] = {}
    if not isinstance(included, list):
        return index
    for item in included:
        if isinstance(item, dict):
            urn = item.get("entityUrn")
            if isinstance(urn, str) and urn:
                index[urn] = item
    return index


_HASHTAG_PATTERN = re.compile(r"#(\w+)")
_FEED_ACTIVITY_ID_PATTERN = re.compile(r"urn:li:activity:(\d+)")


def _extract_single_feed_post(update: dict, entity_index: Dict[str, dict]) -> Optional[Post]:
    """Build a single Post from one 'com.linkedin.voyager.dash.feed.Update' entity.

    Returns None if no post_id/post_url can be resolved (mirrors the None-on-failure
    convention used by _extract_single_contact). Every other field is best-effort:
    a malformed or missing sub-path never raises past this function.
    """
    if not isinstance(update, dict):
        return None

    # 1. post_id / post_url -- backendUrn is the reliable numeric activity id source;
    #    shareUrl (when present) is an already-canonical public permalink, preferred.
    backend_urn = ""
    try:
        backend_urn = update.get("metadata", {}).get("backendUrn", "") or ""
    except Exception:
        backend_urn = ""

    share_url = ""
    try:
        share_url = update.get("socialContent", {}).get("shareUrl", "") or ""
    except Exception:
        share_url = ""

    raw_post_url = ""
    if share_url:
        # Strip query params (utm_source etc.) before canonicalizing.
        raw_post_url = share_url.split("?", 1)[0]
    elif backend_urn:
        m = _FEED_ACTIVITY_ID_PATTERN.search(backend_urn)
        if m:
            raw_post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{m.group(1)}/"

    if not raw_post_url:
        return None

    try:
        clean_post_url = canonicalize_linkedin_post_url(raw_post_url)
    except Exception:
        return None
    if not clean_post_url:
        return None

    post_id = ""
    m_id = _FEED_ACTIVITY_ID_PATTERN.search(backend_urn) or _FEED_ACTIVITY_ID_PATTERN.search(clean_post_url)
    if m_id:
        post_id = m_id.group(1)
    if not post_id:
        return None

    # 2. author_name / author_type / author_id from the embedded actor dict.
    actor = update.get("actor") if isinstance(update.get("actor"), dict) else {}

    author_name = ""
    try:
        name_val = actor.get("name")
        author_name = name_val.get("text", "") if isinstance(name_val, dict) else (name_val or "")
        author_name = author_name.strip() if isinstance(author_name, str) else ""
    except Exception:
        author_name = ""
    if not author_name:
        return None

    action_target = ""
    try:
        action_target = actor.get("navigationContext", {}).get("actionTarget", "") or ""
    except Exception:
        action_target = ""

    actor_backend_urn = ""
    try:
        actor_backend_urn = actor.get("backendUrn", "") or ""
    except Exception:
        actor_backend_urn = ""

    author_type: str = "person"
    if "/in/" in action_target:
        author_type = "person"
    elif "/company/" in action_target:
        author_type = "company"
    elif actor_backend_urn.startswith("urn:li:member:"):
        author_type = "person"
    elif actor_backend_urn:
        author_type = "company"

    author_id: Optional[str] = None
    try:
        if author_type == "person":
            m_handle = re.search(r"/in/([^/?#]+)", action_target)
            if m_handle:
                author_id = f"urn:li:member:{m_handle.group(1)}"
            elif actor_backend_urn.startswith("urn:li:member:"):
                author_id = actor_backend_urn
        else:
            slug = extract_company_slug_from_url(action_target) if action_target else None
            if slug:
                author_id = slug
    except Exception:
        author_id = None

    # 3. text / hashtags
    text: Optional[str] = None
    try:
        commentary = update.get("commentary")
        if isinstance(commentary, dict):
            text_val = commentary.get("text")
            if isinstance(text_val, dict):
                t = text_val.get("text")
                text = t if isinstance(t, str) and t.strip() else None
    except Exception:
        text = None

    hashtags: List[str] = []
    if text:
        try:
            hashtags = _HASHTAG_PATTERN.findall(text)
        except Exception:
            hashtags = []

    # 4. like/comment/repost counts, resolved via two URN-ref hops through entity_index.
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    repost_count: Optional[int] = None
    try:
        social_detail_ref = update.get("*socialDetail")
        social_detail = entity_index.get(social_detail_ref) if isinstance(social_detail_ref, str) else None
        if isinstance(social_detail, dict):
            counts_ref = social_detail.get("*totalSocialActivityCounts")
            counts_entity = entity_index.get(counts_ref) if isinstance(counts_ref, str) else None
            if isinstance(counts_entity, dict):
                nl = counts_entity.get("numLikes")
                nc = counts_entity.get("numComments")
                ns = counts_entity.get("numShares")
                like_count = nl if isinstance(nl, int) else None
                comment_count = nc if isinstance(nc, int) else None
                repost_count = ns if isinstance(ns, int) else None
    except Exception:
        like_count = comment_count = repost_count = None

    # 5. posted_at -- no confirmed field in recon; check plausible spots defensively,
    #    leave None rather than guessing at an unverified field name.
    posted_at: Optional[str] = None
    try:
        metadata = update.get("metadata", {}) if isinstance(update.get("metadata"), dict) else {}
        for candidate_obj in (metadata, update):
            for key in ("createdAt", "publishedAt", "postedAt", "createdTime"):
                val = candidate_obj.get(key)
                if isinstance(val, (str, int)) and str(val).strip():
                    posted_at = str(val)
                    break
            if posted_at:
                break
    except Exception:
        posted_at = None

    try:
        return Post(
            post_id=post_id,
            post_url=clean_post_url,
            author_name=author_name,
            author_type=author_type,  # type: ignore[arg-type]
            author_id=author_id,
            text=text,
            hashtags=hashtags,
            posted_at=posted_at,
            like_count=like_count,
            comment_count=comment_count,
            repost_count=repost_count,
            source="cdp_voyager_graphql",
        )
    except Exception:
        return None


def parse_voyager_feed_json(payload: dict) -> List[Post]:
    """Parse Voyager feed GraphQL responses (company Posts tab / person Activity tab) into Posts.

    Both 'voyagerFeedDashOrganizationalPageUpdates' and 'voyagerFeedDashProfileUpdates'
    queries normalize into the identical 'included' entity schema, so this one parser
    covers both scopes. Scans 'included' directly for 'com.linkedin.voyager.dash.feed.Update'
    entities rather than walking the 'elements' URN list (those URN strings carry extra
    tuple-context that won't exact-match entityUrn), resolves cross-referenced social counts
    via the entityUrn index, and deduplicates by post_id.
    """
    if not isinstance(payload, dict):
        return []

    included = payload.get("included", [])
    if not isinstance(included, list):
        included = []

    entity_index = _index_entities_by_urn(included)

    posts: List[Post] = []
    seen_ids: Set[str] = set()

    for item in included:
        if not isinstance(item, dict):
            continue
        if item.get("$type") != "com.linkedin.voyager.dash.feed.Update":
            continue
        post = _extract_single_feed_post(item, entity_index)
        if post and post.post_id not in seen_ids:
            seen_ids.add(post.post_id)
            posts.append(post)

    return posts


async def capture_voyager_traffic(ws_url: str, timeout: float = 15.0) -> List[LinkedInContact]:
    """Passively listen to Chrome DevTools Protocol network traffic on a WebSocket endpoint.

    Subscribes to Network domain events, intercepts all responses matching '/voyager/api/',
    retrieves the raw response bodies via Network.getResponseBody, and parses all discovered
    LinkedIn contacts.

    Parameters:
        ws_url: CDP WebSocket debugger URL (e.g. 'ws://127.0.0.1:9222/devtools/page/...').
        timeout: Maximum duration in seconds to passively monitor network traffic.

    Returns:
        List of deduplicated LinkedInContact models parsed from intercepted Voyager responses.
    """
    contacts: List[LinkedInContact] = []
    seen_urls: Set[str] = set()

    # Message ID sequence tracker
    msg_id = 0

    def next_id() -> int:
        nonlocal msg_id
        msg_id += 1
        return msg_id

    pending_commands: Dict[int, asyncio.Future] = {}
    voyager_requests: Dict[str, str] = {}  # requestId -> url
    fetched_requests: Set[str] = set()
    in_flight_tasks: Set[asyncio.Task] = set()

    loop = asyncio.get_running_loop()

    try:
        async with websockets.connect(ws_url, max_size=_MAX_WS_MESSAGE_SIZE) as ws:
            # 1. Enable Network domain
            enable_id = next_id()
            enable_future = loop.create_future()
            pending_commands[enable_id] = enable_future
            await ws.send(json.dumps({"id": enable_id, "method": "Network.enable", "params": {}}))
            try:
                await asyncio.wait_for(enable_future, timeout=3.0)
            except Exception:
                pass
            finally:
                pending_commands.pop(enable_id, None)

            async def _fetch_body(req_id: str) -> None:
                """Fetch response body for a completed Voyager request and parse contacts."""
                cmd_id = next_id()
                fut = loop.create_future()
                pending_commands[cmd_id] = fut
                try:
                    await ws.send(
                        json.dumps({
                            "id": cmd_id,
                            "method": "Network.getResponseBody",
                            "params": {"requestId": req_id},
                        })
                    )
                    res = await asyncio.wait_for(fut, timeout=5.0)
                    body_raw = res.get("body", "")
                    if res.get("base64Encoded", False):
                        body_raw = base64.b64decode(body_raw).decode("utf-8", errors="replace")

                    if body_raw:
                        payload = json.loads(body_raw)
                        parsed = parse_voyager_json(payload)
                        for c in parsed:
                            if c.profile_url not in seen_urls:
                                seen_urls.add(c.profile_url)
                                contacts.append(c)
                except Exception as e:
                    logger.debug("Failed to fetch response body for req %s: %s", req_id, e)
                finally:
                    pending_commands.pop(cmd_id, None)

            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                remaining = timeout - (time.monotonic() - start_time)
                if remaining <= 0:
                    break

                try:
                    msg_raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 0.5))
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    break

                try:
                    msg = json.loads(msg_raw)
                except Exception:
                    continue

                # Command response handler
                if "id" in msg:
                    req_cmd_id = msg["id"]
                    if req_cmd_id in pending_commands:
                        f = pending_commands[req_cmd_id]
                        if not f.done():
                            if "error" in msg:
                                f.set_exception(RuntimeError(msg["error"].get("message", "CDP Error")))
                            else:
                                f.set_result(msg.get("result", {}))
                    continue

                # Event handler
                method = msg.get("method", "")
                params = msg.get("params", {})

                if method == "Network.responseReceived":
                    resp = params.get("response", {})
                    url = resp.get("url", "")
                    req_id = params.get("requestId", "")
                    if "/voyager/api/" in url and req_id:
                        voyager_requests[req_id] = url

                elif method == "Network.loadingFinished":
                    req_id = params.get("requestId", "")
                    if req_id in voyager_requests and req_id not in fetched_requests:
                        fetched_requests.add(req_id)
                        task = asyncio.create_task(_fetch_body(req_id))
                        in_flight_tasks.add(task)
                        task.add_done_callback(in_flight_tasks.discard)

            # Drain any requests that received responseReceived but no loadingFinished
            for req_id in list(voyager_requests.keys()):
                if req_id not in fetched_requests:
                    fetched_requests.add(req_id)
                    task = asyncio.create_task(_fetch_body(req_id))
                    in_flight_tasks.add(task)
                    task.add_done_callback(in_flight_tasks.discard)

            if in_flight_tasks:
                done, pending = await asyncio.wait(in_flight_tasks, timeout=3.0)
                for t in pending:
                    t.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

    except Exception as exc:
        logger.warning("CDP interception session closed or encountered error: %s", exc)
    finally:
        for fut in pending_commands.values():
            if not fut.done():
                fut.set_exception(ConnectionError("CDP WebSocket session ended"))
        pending_commands.clear()

    return contacts


async def capture_voyager_feed_traffic(ws_url: str, timeout: float = 15.0) -> List[Post]:
    """Passively listen to CDP network traffic and capture LinkedIn feed post data.

    Near-identical machinery to capture_voyager_traffic (websocket/pending_commands/
    in_flight_tasks), but scoped tighter: only intercepts '/voyager/api/graphql' requests
    whose queryId is 'voyagerFeedDashOrganizationalPageUpdates' (company Posts tab) or
    'voyagerFeedDashProfileUpdates' (person Activity tab) -- the two query names known to
    carry post data -- rather than the generic '/voyager/api/' firehose.

    Parameters:
        ws_url: CDP WebSocket debugger URL (e.g. 'ws://127.0.0.1:9222/devtools/page/...').
        timeout: Maximum duration in seconds to passively monitor network traffic.

    Returns:
        List of deduplicated Post models parsed from intercepted feed GraphQL responses.
    """
    posts: List[Post] = []
    seen_ids: Set[str] = set()

    msg_id = 0

    def next_id() -> int:
        nonlocal msg_id
        msg_id += 1
        return msg_id

    pending_commands: Dict[int, asyncio.Future] = {}
    feed_requests: Dict[str, str] = {}  # requestId -> url
    fetched_requests: Set[str] = set()
    in_flight_tasks: Set[asyncio.Task] = set()

    loop = asyncio.get_running_loop()

    def _is_feed_query_url(url: str) -> bool:
        if "/voyager/api/graphql" not in url:
            return False
        return (
            "queryId=voyagerFeedDashOrganizationalPageUpdates" in url
            or "queryId=voyagerFeedDashProfileUpdates" in url
        )

    try:
        async with websockets.connect(ws_url, max_size=_MAX_WS_MESSAGE_SIZE) as ws:
            # 1. Enable Network domain
            enable_id = next_id()
            enable_future = loop.create_future()
            pending_commands[enable_id] = enable_future
            await ws.send(json.dumps({"id": enable_id, "method": "Network.enable", "params": {}}))
            try:
                await asyncio.wait_for(enable_future, timeout=3.0)
            except Exception:
                pass
            finally:
                pending_commands.pop(enable_id, None)

            async def _fetch_body(req_id: str) -> None:
                """Fetch response body for a completed feed request and parse posts."""
                cmd_id = next_id()
                fut = loop.create_future()
                pending_commands[cmd_id] = fut
                try:
                    await ws.send(
                        json.dumps({
                            "id": cmd_id,
                            "method": "Network.getResponseBody",
                            "params": {"requestId": req_id},
                        })
                    )
                    res = await asyncio.wait_for(fut, timeout=5.0)
                    body_raw = res.get("body", "")
                    if res.get("base64Encoded", False):
                        body_raw = base64.b64decode(body_raw).decode("utf-8", errors="replace")

                    if body_raw:
                        payload = json.loads(body_raw)
                        parsed = parse_voyager_feed_json(payload)
                        for p in parsed:
                            if p.post_id not in seen_ids:
                                seen_ids.add(p.post_id)
                                posts.append(p)
                except Exception as e:
                    logger.debug("Failed to fetch feed response body for req %s: %s", req_id, e)
                finally:
                    pending_commands.pop(cmd_id, None)

            start_time = time.monotonic()
            while time.monotonic() - start_time < timeout:
                remaining = timeout - (time.monotonic() - start_time)
                if remaining <= 0:
                    break

                try:
                    msg_raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 0.5))
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    break

                try:
                    msg = json.loads(msg_raw)
                except Exception:
                    continue

                # Command response handler
                if "id" in msg:
                    req_cmd_id = msg["id"]
                    if req_cmd_id in pending_commands:
                        f = pending_commands[req_cmd_id]
                        if not f.done():
                            if "error" in msg:
                                f.set_exception(RuntimeError(msg["error"].get("message", "CDP Error")))
                            else:
                                f.set_result(msg.get("result", {}))
                    continue

                # Event handler
                method = msg.get("method", "")
                params = msg.get("params", {})

                if method == "Network.responseReceived":
                    resp = params.get("response", {})
                    url = resp.get("url", "")
                    req_id = params.get("requestId", "")
                    if req_id and _is_feed_query_url(url):
                        feed_requests[req_id] = url

                elif method == "Network.loadingFinished":
                    req_id = params.get("requestId", "")
                    if req_id in feed_requests and req_id not in fetched_requests:
                        fetched_requests.add(req_id)
                        task = asyncio.create_task(_fetch_body(req_id))
                        in_flight_tasks.add(task)
                        task.add_done_callback(in_flight_tasks.discard)

            # Drain any requests that received responseReceived but no loadingFinished
            for req_id in list(feed_requests.keys()):
                if req_id not in fetched_requests:
                    fetched_requests.add(req_id)
                    task = asyncio.create_task(_fetch_body(req_id))
                    in_flight_tasks.add(task)
                    task.add_done_callback(in_flight_tasks.discard)

            if in_flight_tasks:
                done, pending = await asyncio.wait(in_flight_tasks, timeout=3.0)
                for t in pending:
                    t.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

    except Exception as exc:
        logger.warning("CDP feed interception session closed or encountered error: %s", exc)
    finally:
        for fut in pending_commands.values():
            if not fut.done():
                fut.set_exception(ConnectionError("CDP WebSocket session ended"))
        pending_commands.clear()

    return posts


def get_ws_url(port: int = 9222, target_type: str = "page", url_filter: str = "linkedin.com") -> str:
    """Retrieve the active WebSocket debugger URL for a Chrome instance over HTTP /json."""
    req = urllib.request.Request(f"http://127.0.0.1:{port}/json")
    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            targets = json.loads(resp.read().decode("utf-8"))
            # Prioritize tab matching target URL filter
            for target in targets:
                if (
                    target.get("type") == target_type
                    and "webSocketDebuggerUrl" in target
                    and url_filter.lower() in target.get("url", "").lower()
                ):
                    return target["webSocketDebuggerUrl"]
            # Fallback to any matching target_type
            for target in targets:
                if target.get("type") == target_type and "webSocketDebuggerUrl" in target:
                    return target["webSocketDebuggerUrl"]
    except Exception as exc:
        raise ConnectionError(f"No browser listening on port {port}: {exc}") from exc
    raise RuntimeError(f"No active '{target_type}' target found on port {port}")


# ==============================================================================
# Standalone Verification Suite (Requirements 4 & 5 + Steering NETWORK.md Data)
# ==============================================================================

def _generate_synthetic_voyager_payload() -> dict:
    """Construct realistic synthetic Voyager GraphQL search response mirroring NETWORK.md targets.

    Includes:
    - Diana Prince (Larkspur, VP Growth Marketing & Operations) with mutual Peter Parker
    - Tony Stark (Verdant, Head of Growth Engineering) with mutual Nick Fury
    - Selina Kyle (Halyard, Talent at Halyard) with mutuals Jean Grey, Jim Gordon
    - Non-person company entity (Larkspur.ai) which must be filtered out
    """
    return {
        "data": {
            "searchDashClustersByAll": {
                "elements": [
                    {
                        "items": [
                            # 1. Target: Diana Prince @ Larkspur (hiring manager for Growth Marketing Eng)
                            {
                                "item": {
                                    "entityResult": {
                                        "trackingUrn": "urn:li:member:54321098",
                                        "entityUrn": "urn:li:fsd_profile:ACoAAB_DIANA_PRINCE",
                                        "title": {"text": "Diana Prince"},
                                        "primarySubtitle": {
                                            "text": "VP Growth Marketing & Operations at Larkspur"
                                        },
                                        "secondarySubtitle": {
                                            "text": "San Francisco, California, United States"
                                        },
                                        "navigationUrl": "https://www.linkedin.com/in/diana-prince?miniProfileUrn=urn%3Ali%3Afs_miniProfile%3AACoAAB_DIANA_PRINCE",
                                        "badgeText": {"text": "2nd"},
                                        "insightsResolutionResults": [
                                            {
                                                "simpleInsight": {
                                                    "title": {
                                                        "text": "1 mutual connection: Peter Parker"
                                                    }
                                                }
                                            }
                                        ],
                                    }
                                }
                            },
                            # 2. Target: Tony Stark @ Verdant (Head of Growth Engineering)
                            {
                                "item": {
                                    "entityResult": {
                                        "trackingUrn": "urn:li:member:76543210",
                                        "entityUrn": "urn:li:fsd_profile:ACoAAB_TONY_STARK",
                                        "title": {"text": "Tony Stark\n · 2nd"},
                                        "primarySubtitle": {
                                            "text": "Head of Growth Engineering @ Verdant"
                                        },
                                        "secondarySubtitle": {"text": "San Francisco Bay Area"},
                                        "navigationUrl": "https://www.linkedin.com/in/tony-stark-eng?trk=public_profile",
                                        "badgeText": {"text": "2nd"},
                                        "insightsResolutionResults": [
                                            {
                                                "simpleInsight": {
                                                    "title": {
                                                        "text": "2 mutual connections: Nick Fury and 1 other"
                                                    }
                                                }
                                            }
                                        ],
                                    }
                                }
                            },
                            # 3. Non-person company entity that MUST be filtered out
                            {
                                "item": {
                                    "entityResult": {
                                        "trackingUrn": "urn:li:company:887766",
                                        "title": {"text": "Larkspur"},
                                        "primarySubtitle": {
                                            "text": "Software Development • San Francisco, CA"
                                        },
                                        "navigationUrl": "https://www.linkedin.com/company/larkspur-ai",
                                    }
                                }
                            },
                        ]
                    }
                ]
            }
        },
        # 4. Target: Selina Kyle @ Halyard in normalized included models
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.search.EntityResultViewModel",
                "entityUrn": "urn:li:fsd_profile:ACoAAB_SELINA_KYLE",
                "title": {"text": "Selina Kyle"},
                "primarySubtitle": {"text": "Talent at Halyard"},
                "secondarySubtitle": {"text": "Alameda, California, United States"},
                "navigationUrl": "https://www.linkedin.com/in/selina-kyle/",
                "badgeText": {"text": "1st"},
                "insightsResolutionResults": [
                    {
                        "simpleInsight": {
                            "title": {
                                "text": "9 mutual connections: Jean Grey, Jim Gordon, and 7 others"
                            }
                        }
                    }
                ],
            }
        ],
    }


def test_parse_voyager_json() -> None:
    """Test parse_voyager_json produces valid LinkedInContact models with source='cdp_voyager_graphql'."""
    print("\n" + "=" * 65)
    print("TEST 1: parse_voyager_json with Realistic NETWORK.md Targets")
    print("=" * 65)

    payload = _generate_synthetic_voyager_payload()
    contacts = parse_voyager_json(payload)

    print(f"[*] Discovered {len(contacts)} contacts from Voyager payload (non-person company filtered out).")
    assert len(contacts) == 3, f"Expected exactly 3 contacts, got {len(contacts)}"

    # Map by name for clean assertions
    contact_map = {c.name: c for c in contacts}

    # 1. Diana Prince (Larkspur)
    assert "Diana Prince" in contact_map, "Diana Prince not extracted"
    c_diana = contact_map["Diana Prince"]
    print(f"  [✓] {c_diana.name:<15} | {c_diana.degree} | Company: {c_diana.current_company} | Mutuals: {c_diana.mutual_sample}")
    assert isinstance(c_diana, LinkedInContact), "c_diana is not a LinkedInContact model"
    assert c_diana.source == "cdp_voyager_graphql", f"Expected source='cdp_voyager_graphql', got {c_diana.source}"
    assert c_diana.profile_url == "https://www.linkedin.com/in/diana-prince", f"Profile URL canonicalization failed: {c_diana.profile_url}"
    assert c_diana.degree == "2nd", f"Degree mismatch: {c_diana.degree}"
    assert c_diana.current_company == "Larkspur", f"Company extraction failed: {c_diana.current_company}"
    assert c_diana.headline == "VP Growth Marketing & Operations at Larkspur"
    assert c_diana.location == "San Francisco, California, United States"
    assert c_diana.mutual_count == 1, f"Expected 1 mutual, got {c_diana.mutual_count}"
    assert c_diana.mutual_sample == ["Peter Parker"], f"Mutual sample mismatch: {c_diana.mutual_sample}"
    assert c_diana.urn_id == "urn:li:member:diana-prince"

    # 2. Tony Stark (Verdant)
    assert "Tony Stark" in contact_map, "Tony Stark not extracted"
    c_tony = contact_map["Tony Stark"]
    print(f"  [✓] {c_tony.name:<15} | {c_tony.degree} | Company: {c_tony.current_company} | Mutuals: {c_tony.mutual_sample}")
    assert isinstance(c_tony, LinkedInContact)
    assert c_tony.source == "cdp_voyager_graphql"
    assert c_tony.profile_url == "https://www.linkedin.com/in/tony-stark-eng", f"Profile URL canonicalization failed: {c_tony.profile_url}"
    assert c_tony.degree == "2nd", f"Degree mismatch: {c_tony.degree}"
    assert c_tony.current_company == "Verdant", f"Company extraction failed: {c_tony.current_company}"
    assert c_tony.headline == "Head of Growth Engineering @ Verdant"
    assert c_tony.location == "San Francisco Bay Area"
    assert c_tony.mutual_count == 2, f"Expected 2 mutuals, got {c_tony.mutual_count}"
    assert c_tony.mutual_sample == ["Nick Fury"], f"Mutual sample mismatch: {c_tony.mutual_sample}"
    assert c_tony.urn_id == "urn:li:member:tony-stark-eng"

    # 3. Selina Kyle (Halyard)
    assert "Selina Kyle" in contact_map, "Selina Kyle not extracted"
    c_selina = contact_map["Selina Kyle"]
    print(f"  [✓] {c_selina.name:<15} | {c_selina.degree} | Company: {c_selina.current_company} | Mutuals: {c_selina.mutual_sample}")
    assert isinstance(c_selina, LinkedInContact)
    assert c_selina.source == "cdp_voyager_graphql"
    assert c_selina.profile_url == "https://www.linkedin.com/in/selina-kyle", f"Profile URL canonicalization failed: {c_selina.profile_url}"
    assert c_selina.degree == "1st", f"Degree mismatch: {c_selina.degree}"
    assert c_selina.current_company == "Halyard", f"Company extraction failed: {c_selina.current_company}"
    assert c_selina.headline == "Talent at Halyard"
    assert c_selina.location == "Alameda, California, United States"
    assert c_selina.mutual_count == 9, f"Expected 9 mutuals, got {c_selina.mutual_count}"
    assert c_selina.mutual_sample == ["Jean Grey", "Jim Gordon"], f"Mutual sample mismatch: {c_selina.mutual_sample}"
    assert c_selina.urn_id == "urn:li:member:selina-kyle"

    print("[✓] All target contact models successfully verified with source='cdp_voyager_graphql'.")


async def test_capture_voyager_traffic() -> None:
    """Test capture_voyager_traffic over a mock CDP WebSocket server."""
    print("\n" + "=" * 65)
    print("TEST 2: capture_voyager_traffic with In-Memory Mock CDP Server")
    print("=" * 65)

    synthetic_body = json.dumps(_generate_synthetic_voyager_payload())

    async def mock_cdp_server(websocket: Any) -> None:
        async for raw_msg in websocket:
            cmd = json.loads(raw_msg)
            method = cmd.get("method")
            msg_id = cmd.get("id")

            if method == "Network.enable":
                # Confirm Network.enable
                await websocket.send(json.dumps({"id": msg_id, "result": {}}))
                # Simulate subsequent Voyager HTTP traffic push events
                await asyncio.sleep(0.05)
                await websocket.send(
                    json.dumps({
                        "method": "Network.responseReceived",
                        "params": {
                            "requestId": "mock-voyager-req-42",
                            "response": {
                                "url": "https://www.linkedin.com/voyager/api/graphql?queryId=searchDashClustersByAll",
                                "status": 200,
                            },
                        },
                    })
                )
                await asyncio.sleep(0.05)
                await websocket.send(
                    json.dumps({
                        "method": "Network.loadingFinished",
                        "params": {"requestId": "mock-voyager-req-42"},
                    })
                )

            elif method == "Network.getResponseBody":
                await websocket.send(
                    json.dumps({
                        "id": msg_id,
                        "result": {
                            "body": synthetic_body,
                            "base64Encoded": False,
                        },
                    })
                )

    # Launch ephemeral mock server on localhost:0
    async with websockets.serve(mock_cdp_server, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        mock_ws_url = f"ws://127.0.0.1:{port}"
        print(f"[*] Ephemeral mock CDP server listening on {mock_ws_url}")

        captured = await capture_voyager_traffic(mock_ws_url, timeout=1.5)

    print(f"[*] Successfully captured {len(captured)} contacts via mock CDP event stream.")
    assert len(captured) == 3, f"Expected 3 contacts, got {len(captured)}"
    for c in captured:
        assert isinstance(c, LinkedInContact)
        assert c.source == "cdp_voyager_graphql"

    print("[✓] CDP WebSocket interception and response body extraction verified.")


def main() -> None:
    test_parse_voyager_json()
    asyncio.run(test_capture_voyager_traffic())
    print("\n" + "=" * 65)
    print("COMPLETION CRITERION: Node 2a CDP Interceptor test suite PASS")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
