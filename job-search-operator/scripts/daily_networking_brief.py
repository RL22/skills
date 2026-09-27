#!/usr/bin/env python3
"""Print a deterministic, draft-only daily networking brief.

Read-only: it never sends, posts, likes, comments, or writes any file.
"""

import argparse
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote_plus


DEFAULT_CONFIG = "~/.config/job-search-operator/config.yaml"
# Sibling skill in the same skills folder; override with JSB_LINKEDIN_SCOUT_CLI.
DEFAULT_SCOUT_CLI = str(Path(__file__).resolve().parents[2] / "linkedin-scout" / "scripts" / "cli.py")
SCOUT_CLI_ENV = "JSB_LINKEDIN_SCOUT_CLI"
ACTIVE_STATUSES = {
    "researching": 12, "networking": 26, "drafting": 26, "ready": 22,
    "applied": 10, "interviewing": 30, "offer": 30,
}
TERMINAL_STATUSES = {"rejected", "withdrawn", "closed", "archived"}
# Operator rule: wait 5-7 business days before a follow-up.
NUDGE_BUSINESS_DAYS = 5
PLACEHOLDERS = {"", "tbd", "never", "none", "n/a", "na", "-", "--", "?", "not yet"}

NETWORK_ALIASES = {
    "name": ["contact", "name"],
    "org": ["current organization", "organization", "org", "company"],
    "relationship": ["relationship"],
    "focus": ["focus"],
    "status": ["status"],
    "last_touch": ["last touch", "last contact"],
    "next_action": ["next action", "next step"],
}
PIPELINE_ALIASES = {
    "company": ["company"],
    "role": ["role"],
    "status": ["status"],
    "score": ["score"],
    "positioning": ["positioning"],
    "next_action": ["next action", "next step"],
    "follow_up": ["follow-up", "follow up", "followup"],
}

MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
DATE_IN_TEXT = re.compile(
    r"\b(\d{4}-\d{2}-\d{2})\b|\b((?:%s)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b" % MONTHS,
    re.IGNORECASE,
)


# ---------------------------------------------------------------- parsing

def strip_markup(text):
    """Remove markdown links, bold, italics markers, and backticks."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("`", "")
    return text.strip()


def split_row(line):
    """Split a markdown table row on unescaped pipes."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells = re.split(r"(?<!\\)\|", line)
    return [strip_markup(cell.replace("\\|", "|")) for cell in cells]


def parse_table(text, aliases, required):
    """Return rows (dicts keyed by canonical name) of the first matching table."""
    lines = text.splitlines()
    index = 0
    while index < len(lines) - 1:
        line = lines[index]
        if line.lstrip().startswith("|") and re.match(
            r"^\s*\|[\s:\-|]+\|?\s*$", lines[index + 1]
        ):
            headers = [h.lower() for h in split_row(line)]
            mapping = {}
            for key, names in aliases.items():
                for column, header in enumerate(headers):
                    if header in names:
                        mapping[key] = column
                        break
            end = index + 2
            rows = []
            while end < len(lines) and lines[end].lstrip().startswith("|"):
                cells = split_row(lines[end])
                rows.append({
                    key: (cells[column] if column < len(cells) else "")
                    for key, column in mapping.items()
                })
                end += 1
            if all(key in mapping for key in required):
                for row in rows:
                    for key in aliases:
                        row.setdefault(key, "")
                return rows
            index = end
        else:
            index += 1
    return []


def parse_date(text):
    """Parse a freeform date string; return date or None."""
    if text is None:
        return None
    value = strip_markup(text).strip()
    if value.lower() in PLACEHOLDERS:
        return None
    match = DATE_IN_TEXT.search(value)
    if not match:
        return None
    raw = match.group(1) or match.group(2)
    raw = re.sub(r"\s+", " ", raw.replace(",", ", ").replace(",  ", ", ")).strip()
    if match.group(1):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None
    word, rest = raw.split(" ", 1)
    word = word.rstrip(".")[:3].title()
    try:
        return datetime.strptime("%s %s" % (word, rest), "%b %d, %Y").date()
    except ValueError:
        return None


def is_unparseable_touch(text):
    value = (text or "").strip()
    return value.lower() not in PLACEHOLDERS and parse_date(value) is None


DEGREE_WORDS = {"1st": "1st", "first": "1st", "2nd": "2nd", "second": "2nd",
                "3rd": "3rd", "third": "3rd"}


def parse_degree(text):
    """Return '1st', '2nd', '3rd', or 'unknown'."""
    match = re.search(r"\b(1st|2nd|3rd|first|second|third)\b", text or "", re.I)
    return DEGREE_WORDS[match.group(1).lower()] if match else "unknown"


def parse_mutuals(*texts):
    """Return named mutual connections found in the given texts."""
    names = []
    for text in texts:
        for match in re.finditer(r"mutuals?\s*:\s*([^;]*)", text or "", re.I):
            names.extend(match.group(1).split(","))
        for match in re.finditer(r"\d+\s+mutuals?\s*\(([^)]*)\)", text or "", re.I):
            names.extend(match.group(1).split(","))
    cleaned = []
    for name in names:
        name = re.sub(r"\(.*?\)", "", name)
        name = re.sub(r"\+\d+.*$", "", name).strip(" .")
        name = re.sub(r"^(and|etc)\s+", "", name).strip()
        if name and name.lower() not in {"etc", "others"} and name not in cleaned:
            cleaned.append(name)
    return cleaned


def parse_score(text):
    """Return a numeric score from freeform score text, or None."""
    value = text or ""
    match = re.search(r"midpoint\s+(\d+(?:\.\d+)?)", value, re.I)
    if match:
        return float(match.group(1))
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", value)]
    if not numbers:
        return None
    return sum(numbers[:2]) / len(numbers[:2]) if len(numbers) > 1 else numbers[0]


def normalize_status(text):
    """Map pipeline status text to a lowercase canonical status or ''."""
    word = re.match(r"[A-Za-z]+", (text or "").strip())
    return word.group(0).lower() if word else ""


def clean_name(name):
    """Lowercase, strip punctuation and Inc/LLC/AI suffix tokens."""
    value = re.sub(r"\(.*?\)", " ", (name or "").lower())
    value = re.sub(r"[^a-z0-9]+", " ", value)
    tokens = [t for t in value.split() if t not in {"inc", "llc", "ai"}]
    return " ".join(tokens)


def name_variants(name):
    parts = re.split(r"\s*/\s*|\s+via\s+", name or "", flags=re.I)
    variants = {clean_name(part) for part in parts}
    variants.add(clean_name(name))
    variants.discard("")
    return variants


def orgs_match(org, company):
    return bool(name_variants(org) & name_variants(company))


# ------------------------------------------------------------- date math

def business_days_between(start, today):
    """Count Mon-Fri days strictly after *start* and strictly before *today*."""
    count = 0
    day = start + timedelta(days=1)
    while day < today:
        if day.weekday() < 5:
            count += 1
        day += timedelta(days=1)
    return count


def status_state(status):
    """Classify Status text as closed, replied, sent, drafted, or none."""
    text = re.sub(r"\b(not sent|unsent)\b", "", (status or "").lower())
    if re.search(r"closed|declined|archived|do not contact|withdrawn", text):
        return "closed"
    if re.search(r"replied|booked|scheduled|confirmed|active contact|screen", text):
        return "replied"
    if re.search(r"sent|messaged|applied|connection request sent", text):
        return "sent"
    if re.search(r"drafted", text):
        return "drafted"
    return "none"


def touch_type(contact, today):
    """Return (touch_type or None, business_days or None)."""
    state = status_state(contact["status"])
    last = contact["last_touch_date"]
    if state == "closed":
        return None, None
    days_since = (today - last).days if last else None
    if days_since is not None and days_since < 2:
        return None, None
    if state == "none":
        return "first_touch", None
    if state == "drafted":
        return "send_drafted", None
    if state == "replied":
        if contact["next_action"].strip().lower() not in PLACEHOLDERS or (
            days_since is not None and days_since >= 2
        ):
            return "warm_follow_up", None
        return None, None
    reference = last
    if reference is None:
        found = [parse_date(m.group(0)) for m in DATE_IN_TEXT.finditer(contact["status"])]
        found = [d for d in found if d and d < today]
        reference = max(found) if found else None
    business = business_days_between(reference, today) if reference else None
    if business is not None and business < NUDGE_BUSINESS_DAYS:
        return None, business
    status = contact["status"].lower()
    if re.search(r"nudge\s*2|touch\s*3", status):
        return "escalate", business
    if re.search(r"nudge\s*1|touch\s*2", status):
        return "nudge_2", business
    return "nudge_1", business


# ------------------------------------------------------------- DM ranking

DUE_POINTS = {"warm_follow_up": 25, "nudge_1": 22, "nudge_2": 20,
              "send_drafted": 18, "first_touch": 14, "escalate": 12}


def load_contacts(rows):
    contacts = []
    for row in rows:
        contact = dict(row)
        contact["last_touch_date"] = parse_date(row["last_touch"])
        contact["degree"] = parse_degree(row["relationship"])
        contact["mutuals"] = parse_mutuals(row["relationship"], row["focus"])
        contacts.append(contact)
    return contacts


def load_pipeline(rows):
    pipeline = []
    for row in rows:
        entry = dict(row)
        entry["state"] = normalize_status(row["status"])
        entry["follow_up_date"] = parse_date(row["follow_up"])
        entry["score_value"] = parse_score(row["score"])
        pipeline.append(entry)
    return pipeline


def pipeline_rows_for(org, pipeline):
    return [p for p in pipeline if orgs_match(org, p["company"])]


def authority_points(text):
    if re.search(r"\b(vp|director|head of|hiring manager|manager|lead|leader|"
                 r"founder|co-founder|cto|chief)\b", text, re.I):
        return 10
    if re.search(r"recruit\w*|talent|sourcer", text, re.I):
        return 6
    return 4


def angle_for(kind, contact):
    if kind == "first_touch":
        topic = contact["focus"].strip() or contact["org"]
        return ("Open with their team's problem in %s, no job ask, aim at a "
                "15-minute discovery call" % topic)
    if kind == "warm_follow_up":
        return "Propose two concrete 15-minute slots"
    if kind == "send_drafted":
        return "Review the existing draft, tighten it, and send it after approval"
    return "Reference the earlier message; keep it short and easy to decline"


def score_contact(contact, pipeline, today, kind, business):
    """Build one scored DM row for *contact* with touch type *kind*."""
    rows = pipeline_rows_for(contact["org"], pipeline)
    active = [r for r in rows if r["state"] in ACTIVE_STATUSES]
    best = max(active, key=lambda r: ACTIVE_STATUSES[r["state"]], default=None)
    linkage = ACTIVE_STATUSES[best["state"]] if best else 0
    degree = contact["degree"]
    if degree == "1st":
        relationship = 25
    elif degree == "2nd":
        relationship = 14 + min(6, 2 * len(contact["mutuals"]))
    elif degree == "3rd":
        relationship = 6
    else:
        relationship = 8
    authority = authority_points(contact["focus"] + " " + contact["relationship"])
    timing = 0
    for row in active:
        if row["follow_up_date"] and abs((row["follow_up_date"] - today).days) <= 3:
            timing = 10
    score = linkage + relationship + DUE_POINTS[kind] + authority + timing
    pipe_status = best["status"] if best else (
        rows[0]["status"] if rows else "not in pipeline")
    pipe_status = normalize_status(pipe_status).title() or pipe_status
    parts = ["%s is %s" % (contact["org"], pipe_status if rows else "not in the pipeline")]
    via = ""
    if degree == "2nd" and contact["mutuals"]:
        via = " via " + contact["mutuals"][0]
    parts.append("%s degree%s" % (degree, via))
    if kind in {"nudge_1", "nudge_2", "escalate"}:
        label = {"nudge_1": "nudge 1 due", "nudge_2": "nudge 2 due",
                 "escalate": "escalate to the department hiring manager or archive"}[kind]
        if business is None:
            parts.append("last touch unknown, %s" % label)
        else:
            parts.append("%d business days since last touch, %s" % (business, label))
    elif kind == "first_touch":
        parts.append("no prior touch, first touch due")
    elif kind == "send_drafted":
        parts.append("a draft is waiting to be sent")
    else:
        parts.append("they replied, follow up")
    return {
        "name": contact["name"],
        "organization": contact["org"],
        "degree": degree,
        "touch_type": kind,
        "score": min(100, score),
        "reason": "; ".join(parts),
        "pipeline_status": pipe_status,
        "last_touch": contact["last_touch_date"].isoformat()
        if contact["last_touch_date"] else None,
        "next_action": contact["next_action"],
        "angle": angle_for(kind, contact),
    }


def rank_dms(contacts, pipeline, today):
    """Return every due contact, scored and sorted (highest first)."""
    ranked = []
    for contact in contacts:
        kind, business = touch_type(contact, today)
        if kind is None:
            continue
        rows = pipeline_rows_for(contact["org"], pipeline)
        active = [r for r in rows if r["state"] in ACTIVE_STATUSES]
        if rows and not active and contact["degree"] != "1st":
            continue
        ranked.append(score_contact(contact, pipeline, today, kind, business))
    ranked.sort(key=lambda d: (-d["score"], d["name"]))
    return ranked


# ------------------------------------------------------- engagement queue

APPROVED_SCORE = 100
QUEUE_TIMEOUT = 30
DRAFT_MARKDOWN_CHARS = 300


def normalize_queue(data):
    """Return the well-formed queue objects from a decoded JSON list."""
    if isinstance(data, dict):
        for key in ("items", "actions", "results"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError("expected a JSON list of queue items")
    return [item for item in data if isinstance(item, dict)]


def load_queue(args):
    """Return (items, warning). Never raises."""
    try:
        if args.queue_json:
            data = json_from_output(Path(args.queue_json).expanduser().read_text())
        else:
            cli = Path(os.environ.get(SCOUT_CLI_ENV) or DEFAULT_SCOUT_CLI).expanduser()
            if not cli.exists():
                return [], "engagement queue unavailable: linkedin-scout CLI not found at %s" % cli
            command = [sys.executable, str(cli), "list-engagement", "--json"]
            if args.db:
                command += ["--db", args.db]
            done = subprocess.run(command, capture_output=True, text=True,
                                  timeout=QUEUE_TIMEOUT)
            if done.returncode != 0:
                detail = (done.stderr or done.stdout).strip().splitlines()
                return [], "engagement queue unavailable: list-engagement exited %d%s" % (
                    done.returncode, ": " + detail[-1][:120] if detail else "")
            data = json_from_output(done.stdout)
        return normalize_queue(data), None
    except subprocess.TimeoutExpired:
        return [], "engagement queue unavailable: list-engagement timed out after %ds" % QUEUE_TIMEOUT
    except (OSError, ValueError) as error:
        return [], "engagement queue unavailable: %s" % str(error)[:120]


def queued_comment_count(items):
    """Count post-comment drafts waiting in drafted or approved status."""
    return sum(1 for i in items
               if i.get("target_type") == "post" and i.get("action_type") == "comment"
               and i.get("status") in {"drafted", "approved"})


def apply_queue(ranked, contacts, pipeline, items, today):
    """Let queue state override computed touch rows; returns a new sorted list."""
    wanted = {}  # lowercase name -> (status, item); approved beats drafted
    for item in items:
        if (item.get("target_type") != "dm" or item.get("action_type") != "message"
                or item.get("status") not in {"approved", "drafted"}):
            continue
        name = (item.get("counterparty_name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key not in wanted or (item["status"] == "approved"
                                 and wanted[key]["status"] != "approved"):
            wanted[key] = item
    if not wanted:
        return ranked
    by_name = {c["name"].strip().lower(): c for c in contacts}
    rows = {d["name"].strip().lower(): d for d in ranked}
    result = [d for d in ranked if d["name"].strip().lower() not in wanted]
    for key, item in wanted.items():
        base = rows.get(key)
        if base is None:
            person = by_name.get(key)
            if person is None:
                person = {"name": item["counterparty_name"].strip(), "org": "unknown",
                          "relationship": "", "focus": "", "status": "",
                          "last_touch": "", "next_action": "", "last_touch_date": None,
                          "degree": "unknown", "mutuals": []}
            base = score_contact(person, pipeline, today, "send_drafted", None)
        row = dict(base)
        draft = item.get("draft_content") or ""
        if item["status"] == "approved":
            row.update(touch_type="send_approved", score=APPROVED_SCORE,
                       reason="Approved draft waiting; send it yourself in your own browser",
                       angle="Read the approved draft once more, then send manually")
        else:
            row.update(touch_type="review_queued",
                       reason="Drafted in the queue, awaiting your approve or reject",
                       angle="Review the queued draft, then approve or reject it")
        row["draft"] = draft
        result.append(row)
    result.sort(key=lambda d: (-d["score"], d["name"]))
    return result


def cap_per_org(ranked, limit, max_per_org):
    """Pick up to *limit* rows with at most *max_per_org* per organization."""
    limit = max(0, limit)
    if max_per_org <= 0:
        return ranked[:limit]
    groups = []  # [variants, count]
    chosen, deferred = [], []
    for row in ranked:
        if len(chosen) >= limit:
            break
        org = row["organization"]
        variants = name_variants(org)
        if not variants or clean_name(org) == "unknown":
            chosen.append(row)
            continue
        group = next((g for g in groups if g[0] & variants), None)
        if group is None:
            group = [set(), 0]
            groups.append(group)
        group[0] |= variants
        if group[1] < max_per_org:
            group[1] += 1
            chosen.append(row)
        else:
            deferred.append(row)
    for row in deferred:
        if len(chosen) >= limit:
            break
        chosen.append(row)
    chosen.sort(key=lambda d: (-d["score"], d["name"]))
    return chosen


# ---------------------------------------------------------------- actions

def action(title, why, how, minutes):
    return {"title": title, "why": why, "how": how, "est_minutes": minutes}


def build_actions(pipeline, contacts, ranked, today, posts_loaded, queued_comments=0):
    """Choose 3-5 daily actions in fixed priority order A-H."""
    candidates = []  # (letter, [actions])

    overdue = [p for p in pipeline
               if p["follow_up_date"] and p["follow_up_date"] <= today
               and p["state"] not in TERMINAL_STATUSES and p["state"]]
    overdue.sort(key=lambda p: p["follow_up_date"])
    candidates.append(("A", [action(
        "Overdue follow-up: %s (%s)" % (p["company"], p["role"]),
        "Two-nudge ghosting protocol: one short nudge, then escalate or archive",
        "Follow-up was due %s. Next action on file: %s"
        % (p["follow_up_date"].isoformat(), p["next_action"] or "none"),
        10) for p in overdue[:2]]))

    warm = []
    for row in pipeline:
        if row["state"] not in {"drafting", "ready"}:
            continue
        recent = any(
            orgs_match(c["org"], row["company"]) and c["last_touch_date"]
            and 0 <= (today - c["last_touch_date"]).days <= 14
            for c in contacts)
        if recent:
            continue
        best = next((d for d in ranked if orgs_match(d["organization"], row["company"])), None)
        who = ("best ranked contact: %s (%s)" % (best["name"], best["touch_type"])
               if best else "no ranked contact yet, find one first")
        warm.append(action(
            "Warm up %s before applying" % row["company"],
            "65% of jobs fill off public boards; never apply cold",
            "Touch one contact at %s before submitting the %s application; %s"
            % (row["company"], row["role"], who),
            15))
    candidates.append(("B", warm[:2]))

    if queued_comments >= 3:
        comments = [action(
            "Review and approve your %d queued comment drafts" % queued_comments,
            "Drafts already waiting in the queue; do not ask for duplicates",
            "Open the engagement queue, read each comment draft, then approve or "
            "reject it and post the approved ones yourself",
            10)]
    elif posts_loaded:
        how = ("Draft 3 comments on the top-ranked posts (persons before pages) and "
               "queue them with linkedin-scout queue-engagement for review")
        if queued_comments:
            how = ("%d draft%s already queued; draft %d more on the top-ranked posts "
                   "(persons before pages) and queue them with linkedin-scout "
                   "queue-engagement for review"
                   % (queued_comments, "" if queued_comments == 1 else "s",
                      3 - queued_comments))
        comments = [action("Smart comments on top-ranked posts",
                           "One good comment reaches more people than posting", how, 20)]
    else:
        comments = []
    candidates.append(("C", comments))

    audit = [p for p in pipeline if p["state"] in {"interviewing", "networking"}
             and p["score_value"] is not None]
    audit.sort(key=lambda p: (-p["score_value"], p["company"]))
    candidates.append(("D", [action(
        "Proactive audit: %s" % audit[0]["company"],
        "Playbook section 4: arrive with a finding, not a request",
        "Spend 30 minutes auditing %s's public site or product surface and "
        "write 3 findings you could send the hiring manager" % audit[0]["company"],
        30)] if audit else []))

    roles = []
    for row in pipeline:
        if row["state"] in {"networking", "drafting"}:
            role = re.sub(r"\s*\(.*?\)", "", row["role"]).strip()
            if role and role.lower() not in {r.lower() for r in roles}:
                roles.append(role)
    urls = ["https://www.linkedin.com/jobs/search/?keywords=%s&f_TPR=r14400"
            % quote_plus(role) for role in roles[:3]]
    candidates.append(("E", [action(
        "Fresh-requisition sweep (past 4 hours)",
        "Early applicants get seen; apply where the hiring manager can be reached",
        "Check: %s. Apply on the company careers page rather than Easy Apply, "
        "and message the hiring manager the same day" % " ; ".join(urls),
        15)] if urls else []))

    companies = {clean_name(p["company"]) for p in pipeline if clean_name(p["company"])}
    icp = action(
        "ICP coverage: %d of 40-50 target accounts" % len(companies),
        "Reach comes from a wide, named target list of accounts",
        "Add 3 target accounts and name the VP or Director who owns the problem "
        "(current count %d against the 40-50 account target)" % len(companies),
        20)
    candidates.append(("F", [icp] if len(companies) < 40 else []))

    fresh = action(
        "Profile freshness micro-edit",
        "Recruiter 'active in last 7 days' filters favor recently updated profiles",
        "Make one micro-edit to your headline or a skill so recruiter "
        "'active in last 7 days' filters keep showing you",
        5)
    candidates.append(("G", [fresh] if today.weekday() == 0 else []))

    prune = action(
        "Network pruning",
        "A focused network keeps the feed and inbound relevant to the 2026 targets",
        "Remove or archive 5 legacy connections that do not serve the 2026 target list",
        10)
    candidates.append(("H", [prune] if today.weekday() == 4 else []))

    chosen = []
    for _, items in candidates:
        for item in items:
            if len(chosen) < 5:
                chosen.append(item)
    if len(chosen) < 3:
        for fallback in (icp, fresh, prune):
            if len(chosen) >= 3:
                break
            if fallback not in chosen:
                chosen.append(fallback)
    return chosen


# ------------------------------------------------------------------ posts

def flatten_post(item):
    flat = dict(item) if isinstance(item, dict) else {}
    nested = flat.pop("post", None)
    if isinstance(nested, dict):
        for key, value in nested.items():
            flat.setdefault(key, value)
    return flat


def normalize_posts(data):
    if isinstance(data, dict):
        for key in ("posts", "results", "ranked"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError("expected a JSON list of ranked posts")
    posts = []
    for position, item in enumerate(data, 1):
        flat = flatten_post(item)
        breakdown = flat.get("breakdown") or {}
        hits = breakdown.get("hits")
        if isinstance(hits, (list, tuple)):
            hits = ", ".join(str(h) for h in hits)
        age_hours = breakdown.get("age_hours")
        posts.append({
            "rank": flat.get("rank", position),
            "score": flat.get("score"),
            "author": flat.get("author_name") or flat.get("author") or "?",
            "author_type": flat.get("author_type"),
            "age_days": round(age_hours / 24, 1) if isinstance(age_hours, (int, float)) else None,
            "likes": flat.get("like_count"),
            "comments": flat.get("comment_count"),
            "hits": hits if hits not in (None, 0, "") else "",
            "text": flat.get("text") or "",
            "post_url": flat.get("post_url") or "",
        })
    return posts


def json_from_output(text):
    try:
        return json.loads(text)
    except ValueError:
        start = min((i for i in (text.find("["), text.find("{")) if i >= 0), default=-1)
        if start < 0:
            raise
        return json.loads(text[start:])


def load_posts(args):
    """Return (posts, warning). Never raises."""
    try:
        if args.posts_json:
            data = json_from_output(Path(args.posts_json).expanduser().read_text())
        else:
            cli = Path(os.environ.get(SCOUT_CLI_ENV) or DEFAULT_SCOUT_CLI).expanduser()
            if not cli.exists():
                return [], "Posts unavailable: linkedin-scout CLI not found at %s" % cli
            command = [sys.executable, str(cli), "rank-posts", "--json",
                       "--top", str(args.top_posts)]
            if args.db:
                command += ["--db", args.db]
            done = subprocess.run(command, capture_output=True, text=True, timeout=60)
            if done.returncode != 0:
                detail = (done.stderr or done.stdout).strip().splitlines()
                return [], "Posts unavailable: rank-posts exited %d%s" % (
                    done.returncode, ": " + detail[-1][:120] if detail else "")
            data = json_from_output(done.stdout)
        return normalize_posts(data)[: args.top_posts], None
    except subprocess.TimeoutExpired:
        return [], "Posts unavailable: rank-posts timed out after 60s"
    except (OSError, ValueError) as error:
        return [], "Posts unavailable: %s" % str(error)[:120]


# ------------------------------------------------------------ path lookup

def read_config(path):
    values = {}
    try:
        text = Path(path).expanduser().read_text()
    except OSError:
        return values
    for line in text.splitlines():
        line = line.split(" #")[0].strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def resolve_file(label, explicit, config, workspace_key, fallback_name, shared_first, cwd):
    """Return (path or None, warning or None)."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    workspace = config.get("workspace")
    configured = config.get(workspace_key)
    if workspace and configured:
        base = Path(workspace).expanduser()
        candidates.append(base / configured)
        if shared_first:
            candidates.append(base / "_shared_facts" / configured)
    if shared_first:
        candidates.append(cwd / "_shared_facts" / fallback_name)
    else:
        candidates.append(cwd / fallback_name)
    for position, candidate in enumerate(candidates):
        if candidate.is_file():
            if position == 0:
                return candidate, None
            return candidate, "%s: first choice %s not found, using fallback %s" % (
                label, candidates[0], candidate)
    return None, None


# ----------------------------------------------------------------- output

def scrub(text):
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text)
    text = re.sub(r"(?<!\d)(?:\+\d[\d\-. ()]{8,}\d|\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4})(?!\d)",
                  "[number]", text)
    return text.replace("\u2014", "-").replace("\u2013", "-")


def cell(value):
    return str(value if value is not None else "").replace("|", "/").replace("\n", " ").strip()


def render_markdown(report):
    out = ["# Daily networking brief: %s" % report["date"], ""]
    out += ["## 1. Posts to engage with", ""]
    if report["posts_skipped"]:
        out.append("Skipped (--no-posts).")
    elif not report["posts"]:
        out.append("No ranked posts available.")
    else:
        out.append("| Rank | Score | Author | Age (days) | Likes/Comments | Keywords | Text | URL |")
        out.append("|---|---|---|---|---|---|---|---|")
        for post in report["posts"]:
            age = post["age_days"] if post["age_days"] is not None else "?"
            out.append("| %s | %s | %s | %s | %s/%s | %s | %s | %s |" % tuple(
                cell(v) for v in (
                    post["rank"], post["score"], post["author"], age,
                    post["likes"] if post["likes"] is not None else "?",
                    post["comments"] if post["comments"] is not None else "?",
                    post["hits"], post["text"][:70], post["post_url"])))
    out += ["", "## 2. Connections to DM today", ""]
    if not report["dms"]:
        out.append("No contacts are due today.")
    else:
        out.append("| Name | Org | Degree | Touch | Score | Reason | Angle |")
        out.append("|---|---|---|---|---|---|---|")
        for dm in report["dms"]:
            out.append("| " + " | ".join(cell(dm[k]) for k in (
                "name", "organization", "degree", "touch_type", "score",
                "reason", "angle")) + " |")
        drafts = [dm for dm in report["dms"] if dm.get("draft")]
        if drafts:
            out += ["", "Queued drafts (nothing is sent by this script):", ""]
            for dm in drafts:
                text = dm["draft"]
                if len(text) > DRAFT_MARKDOWN_CHARS:
                    text = text[:DRAFT_MARKDOWN_CHARS].rstrip() + "..."
                out.append("- %s (%s): %s" % (dm["name"], dm["touch_type"], cell(text)))
    out += ["", "## 3. Extra networking actions", ""]
    for number, item in enumerate(report["actions"], 1):
        out.append("%d. **%s** (%d min)" % (number, item["title"], item["est_minutes"]))
        out.append("   - Why: %s" % item["why"])
        out.append("   - How: %s" % item["how"])
    if report["warnings"]:
        out += ["", "## Data quality", ""]
        out += ["- %s" % w for w in report["warnings"]]
    out += ["", "Draft-only: nothing was sent, posted, or logged."]
    return "\n".join(out)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network")
    parser.add_argument("--pipeline")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--today", type=date.fromisoformat, default=None)
    parser.add_argument("--dm-limit", type=int, default=8)
    parser.add_argument("--top-posts", type=int, default=10)
    parser.add_argument("--posts-json")
    parser.add_argument("--no-posts", action="store_true")
    parser.add_argument("--max-per-org", type=int, default=2)
    parser.add_argument("--queue-json")
    parser.add_argument("--no-queue", action="store_true")
    parser.add_argument("--db")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv=None, cwd=None):
    """Build and print the brief. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    today = args.today or date.today()
    cwd = Path(cwd) if cwd else Path.cwd()
    config = read_config(args.config)
    warnings = []

    network_path, warn = resolve_file(
        "NETWORK", args.network, config, "network_file", "NETWORK.md", True, cwd)
    if warn:
        warnings.append(warn)
    pipeline_path, warn = resolve_file(
        "PIPELINE", args.pipeline, config, "pipeline_file", "README.md", False, cwd)
    if warn:
        warnings.append(warn)
    if network_path is None or pipeline_path is None:
        missing = [n for n, p in (("NETWORK", network_path), ("PIPELINE", pipeline_path)) if p is None]
        print("error: could not locate %s file; pass --network/--pipeline or set "
              "workspace in %s" % (" and ".join(missing), args.config), file=sys.stderr)
        return 2

    net_rows = parse_table(network_path.read_text(), NETWORK_ALIASES, ["name", "status"])
    pipe_rows = parse_table(pipeline_path.read_text(), PIPELINE_ALIASES, ["company", "status"])
    contacts = load_contacts(net_rows)
    pipeline = load_pipeline(pipe_rows)
    if not contacts:
        warnings.append("No contact rows parsed from %s" % network_path)
    if not pipeline:
        warnings.append("No pipeline rows parsed from %s" % pipeline_path)
    bad = sum(1 for c in contacts if is_unparseable_touch(c["last_touch"]))
    if bad:
        warnings.append("%d contact rows have a non-empty Last touch that could not be parsed as a date" % bad)

    posts, posts_loaded = [], False
    if not args.no_posts:
        posts, warn = load_posts(args)
        posts_loaded = warn is None and bool(posts)
        if warn:
            warnings.append(warn)

    queue = []
    if not args.no_queue:
        queue, warn = load_queue(args)
        if warn:
            warnings.append(warn)

    ranked = apply_queue(rank_dms(contacts, pipeline, today), contacts, pipeline,
                         queue, today)
    report = {
        "date": today.isoformat(),
        "posts": posts,
        "posts_skipped": args.no_posts,
        "dms": cap_per_org(ranked, args.dm_limit, args.max_per_org),
        "actions": build_actions(pipeline, contacts, ranked, today, posts_loaded,
                                 queued_comment_count(queue)),
        "warnings": warnings,
    }
    if args.json:
        payload = {k: report[k] for k in ("date", "posts", "dms", "actions", "warnings")}
        print(scrub(json.dumps(payload, indent=2, ensure_ascii=False)))
    else:
        print(scrub(render_markdown(report)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
