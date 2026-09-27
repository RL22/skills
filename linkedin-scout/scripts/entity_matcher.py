"""
entity_matcher.py - Node 2c Entity Matching Engine for the Q4 LinkedIn Sourcing Pipeline.
Complies with mps-writing-for-agents (canonical single source of truth, typed, deterministic).

Matches extracted LinkedIn contacts against target roles and company requisitions using:
- Single source of truth: schemas.LinkedInContact
- RapidFuzz C++ Levenshtein algorithms (token_set_ratio, partial_ratio, token_sort_ratio)
- Tech & sales role abbreviation / synonym expansion (SWE, SDE, AE, SE, EM, PM, etc.)
- Corporate entity and suffix normalization (Inc, LLC, Corp, Technologies, .ai, etc.)
- Leadership & hiring-manager prioritization (Head of, VP, Director, Lead, Manager)
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# Enable running both as a standalone script and as an imported module
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

try:
    from schemas import LinkedInContact, JobPosting, Post
except ImportError:
    from .schemas import LinkedInContact, JobPosting, Post

from rapidfuzz import fuzz, utils

# =====================================================================
# Canonical Knowledge Base: Role Abbreviations & Synonyms
# =====================================================================

ROLE_ABBREVIATIONS: dict[str, str] = {
    # Engineering & Technical IC
    "swe": "software engineer",
    "sde": "software engineer",
    "mle": "machine learning engineer",
    "sre": "site reliability engineer",
    "pe": "principal engineer",
    "de": "data engineer",
    "ds": "data scientist",
    "qa": "quality assurance engineer",
    "fe": "frontend engineer",
    "be": "backend engineer",
    "fs": "full stack engineer",
    "devops": "development operations engineer",
    "secops": "security operations engineer",
    # Leadership, Management & Hiring Authority
    "em": "engineering manager",
    "mngr": "manager",
    "mgr": "manager",
    "dir": "director",
    "vp": "vice president",
    "svp": "senior vice president",
    "evp": "executive vice president",
    "cto": "chief technology officer",
    "cmo": "chief marketing officer",
    "ceo": "chief executive officer",
    "coo": "chief operating officer",
    "cpo": "chief product officer",
    "cro": "chief revenue officer",
    # Product & Program
    "pm": "product manager",
    "tpm": "technical program manager",
    "pdm": "product manager",
    "pgm": "program manager",
    # Sales & Go-To-Market
    "ae": "account executive",
    "se": "solutions engineer",
    "tam": "technical account manager",
    "am": "account manager",
    "sdr": "sales development representative",
    "bdr": "business development representative",
    "csm": "customer success manager",
    # Seniority & Modifiers
    "sr": "senior",
    "jr": "junior",
    "eng": "engineer",
    "engr": "engineer",
    "dev": "developer",
    "tech": "technical",
}

# Corporate legal and descriptive suffixes to normalize
CORPORATE_SUFFIXES: set[str] = {
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "co",
    "company",
    "technologies",
    "technology",
    "tech",
    "platforms",
    "platform",
    "software",
    "systems",
    "solutions",
    "services",
    "holdings",
    "holding",
    "group",
    "enterprises",
    "enterprise",
    "labs",
    "lab",
    "ai",
    "io",
    "com",
    "gmbh",
    "plc",
    "sa",
    "ag",
    "bv",
    "nv",
}

# High-priority decision maker / team lead indicators
LEADERSHIP_INDICATORS: tuple[str, ...] = (
    "head of",
    "head",
    "vp",
    "vice president",
    "director",
    "engineering manager",
    "manager",
    "lead",
    "team lead",
    "chief",
    "founder",
    "co-founder",
    "partner",
    "principal",
    "hiring",
)


# =====================================================================
# Text Processing & Normalization Helpers
# =====================================================================

def expand_role_text(text: str) -> str:
    """
    Expand standard role abbreviations and acronyms in text.
    Handles word boundaries and case-insensitivity.
    """
    if not text:
        return ""

    def replace_word(match: re.Match) -> str:
        word = match.group(0).lower()
        return ROLE_ABBREVIATIONS.get(word, match.group(0))

    return re.sub(r"\b[A-Za-z]+\b", replace_word, text)


def clean_company_name(name: str) -> str:
    """
    Normalize company name by stripping domain extensions (.com, .ai, etc.),
    legal/corporate suffixes (LLC, Inc, Technologies, etc.), and non-alphanumeric noise.
    Ensures at least one core token remains.
    """
    if not name:
        return ""

    # Strip web domain extensions
    name = re.sub(r"\.(com|ai|io|net|org|co)\b", "", name, flags=re.IGNORECASE)
    # Replace punctuation with spaces
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    tokens = cleaned.split()

    # Strip known trailing corporate suffixes while retaining at least one token
    while len(tokens) > 1 and tokens[-1] in CORPORATE_SUFFIXES:
        tokens.pop()

    return " ".join(tokens)


def segment_text(text: str) -> List[str]:
    """
    Split LinkedIn headlines or candidate text into logical segments
    using common delimiters (| , • · – — - / : \n @ at).
    """
    if not text:
        return []
    # Split on common LinkedIn separators including hyphens, pipes, commas, colons, bullets, brackets
    raw_segments = re.split(r"[-@|•·–—/:\n,()[\]{}]|(?:\bat\b)|(?:\b@\b)", text)
    segments = [s.strip() for s in raw_segments if s and s.strip()]
    # Also include the complete text
    if text.strip() not in segments:
        segments.append(text.strip())
    return segments


# =====================================================================
# Core Scoring Functions
# =====================================================================

def _score_single_pair(target: str, candidate: str) -> float:
    """
    Compute a combined RapidFuzz similarity score between target and candidate string
    using token_set_ratio (50%), token_sort_ratio (30%), and partial_ratio (20%).
    """
    t_proc = utils.default_process(target)
    c_proc = utils.default_process(candidate)
    if not t_proc or not c_proc:
        return 0.0

    # RapidFuzz C++ Levenshtein ratios
    ts_ratio = fuzz.token_set_ratio(t_proc, c_proc)
    sort_ratio = fuzz.token_sort_ratio(t_proc, c_proc)
    part_ratio = fuzz.partial_ratio(t_proc, c_proc)

    # Weighted blend giving high weight to token coverage with order discipline
    return 0.50 * ts_ratio + 0.30 * sort_ratio + 0.20 * part_ratio


def score_role(target_roles: List[str], headline: str) -> float:
    """
    Returns a 0.0 to 100.0 relevance score matching headline against target roles.
    Expands acronyms (e.g. SWE -> Software Engineer, EM -> Engineering Manager)
    and evaluates both segmented and full headline context.
    """
    if not target_roles or not headline or not headline.strip():
        return 0.0

    expanded_headline = expand_role_text(headline)
    segments = segment_text(expanded_headline)
    # Also add raw segments in case abbreviations were literal
    raw_segments = segment_text(headline)
    all_segments = list(dict.fromkeys(segments + raw_segments))

    max_score = 0.0

    for role in target_roles:
        if not role or not role.strip():
            continue

        expanded_role = expand_role_text(role)
        role_variants = [expanded_role]
        if expanded_role.lower() != role.lower():
            role_variants.append(role)

        for r_var in role_variants:
            for seg in all_segments:
                score = _score_single_pair(r_var, seg)
                if score > max_score:
                    max_score = score

    return round(min(100.0, max(0.0, max_score)), 2)


def score_company(target_company: str, candidate_text: str) -> float:
    """
    Returns a 0.0 to 100.0 match score between target company and candidate text.
    Handles corporate entity suffixes (LLC, Inc, Technologies, etc.), domain stems,
    and guards against substring false positives (e.g. Meta vs Metadata, Apple vs Snapple).
    """
    if not target_company or not candidate_text:
        return 0.0

    t_clean = clean_company_name(target_company)
    if not t_clean:
        return 0.0

    t_tokens = t_clean.split()
    segments = segment_text(candidate_text)

    max_score = 0.0

    for seg in segments:
        c_clean = clean_company_name(seg)
        if not c_clean:
            continue

        # Exact normalized match
        if t_clean == c_clean:
            return 100.0

        ts_ratio = fuzz.token_set_ratio(t_clean, c_clean)
        sort_ratio = fuzz.token_sort_ratio(t_clean, c_clean)
        part_ratio = fuzz.partial_ratio(t_clean, c_clean)

        # False positive guard: partial_ratio shouldn't trigger on substring within unrelated words
        # (e.g. 'meta' in 'metadata', or 'apple' in 'snapple')
        all_tokens_present = all(
            re.search(r"\b" + re.escape(tok) + r"\b", c_clean) for tok in t_tokens
        )
        if not all_tokens_present and part_ratio > ts_ratio:
            part_ratio = ts_ratio

        combined = 0.50 * ts_ratio + 0.30 * sort_ratio + 0.20 * part_ratio
        if combined > max_score:
            max_score = combined

    return round(min(100.0, max(0.0, max_score)), 2)


# =====================================================================
# Contact Ranking & Filtering
# =====================================================================

def calculate_contact_priority(
    contact: LinkedInContact,
    target_company: str,
) -> float:
    """
    Calculates the combined ranking score for sorting contacts.
    Prioritizes:
    1. Role match relevance (55%)
    2. Company match relevance (45% if target company specified)
    3. Leadership / Hiring Manager bonus (+8.0 pts for decision makers)
    4. Network degree proximity (+3.0 for 1st degree, +1.5 for 2nd degree)
    5. Mutual connection density (+0.2 per mutual, capped at 2.0 pts)
    """
    if target_company and target_company.strip():
        base = 0.55 * contact.role_match_score + 0.45 * contact.company_match_score
    else:
        base = contact.role_match_score

    headline_lower = (contact.headline or "").lower()

    # Leadership / Hiring Manager boost: team leads, heads, managers, VPs, directors
    leadership_boost = 0.0
    if any(kw in headline_lower for kw in LEADERSHIP_INDICATORS):
        leadership_boost = 8.0

    # Network degree proximity boost
    degree_boost = 0.0
    if contact.degree == "1st":
        degree_boost = 3.0
    elif contact.degree == "2nd":
        degree_boost = 1.5

    # Mutual connection density boost
    mutual_boost = min((contact.mutual_count or 0) * 0.20, 2.0)

    return round(base + leadership_boost + degree_boost + mutual_boost, 2)


def compute_composite_score(role_score: float, company_score: float) -> float:
    """Canonical single source of truth for composite role & company matching score."""
    return (role_score * 0.6) + (company_score * 0.4)


def score_topic(target_topics: List[str], post_text: str, hashtags: List[str]) -> float:
    """Returns a 0.0-100.0 relevance score matching post text+hashtags against target topics."""
    if not target_topics:
        return 0.0
    combined = f"{post_text or ''} {' '.join(hashtags or [])}".strip()
    return score_role(target_topics, combined)


def score_author(target_names: List[str], author_name: str) -> float:
    """Returns a 0.0-100.0 fuzzy name-match score, best-of across target_names. No acronym expansion (names, not roles)."""
    if not target_names or not author_name:
        return 0.0
    return max((_score_single_pair(t, author_name) for t in target_names if t and t.strip()), default=0.0)


def _warmth_boost(tier: Optional[str]) -> float:
    """Author warmth tier boost, mirroring calculate_contact_priority's degree_boost weighting."""
    return {"WARM": 15.0, "BRIDGE": 8.0, "COLD": 2.0, "FROZEN": 0.0}.get(tier or "", 0.0)


def _engagement_boost(like_count: Optional[int], comment_count: Optional[int], repost_count: Optional[int]) -> float:
    """Small bonus for posts already drawing engagement -- signals a live, worthwhile thread. Capped."""
    total = (like_count or 0) + 3 * (comment_count or 0) + 5 * (repost_count or 0)
    return min(total * 0.02, 10.0)


def rank_and_filter_posts(
    posts: List[Post],
    target_topics: List[str],
    target_authors: Optional[List[str]] = None,
    min_topic_score: float = 40.0,
) -> List[Post]:
    """
    Update topic/author match scores on posts, filter by topic threshold, and rank descending
    by rubric priority (topic + author fit, plus warmth and live-engagement boosts).
    Mirrors rank_and_filter_contacts/rank_and_filter_jobs for the Post object.
    """
    has_target_topics = bool(target_topics and any(t.strip() for t in target_topics))
    target_authors = target_authors or []

    qualified: List[Tuple[float, Post]] = []

    for post in posts:
        post.topic_match_score = score_topic(target_topics, post.text or "", post.hashtags) if has_target_topics else 100.0
        post.author_match_score = score_author(target_authors, post.author_name) if target_authors else 0.0

        if has_target_topics and post.topic_match_score < min_topic_score:
            continue

        base = compute_composite_score(post.topic_match_score, post.author_match_score) if target_authors else post.topic_match_score
        priority = base + _warmth_boost(post.author_warmth_tier) + _engagement_boost(
            post.like_count, post.comment_count, post.repost_count
        )
        qualified.append((round(priority, 2), post))

    qualified.sort(key=lambda item: item[0], reverse=True)
    return [post for _, post in qualified]


def rank_and_filter_jobs(
    jobs: List[JobPosting],
    target_roles: List[str],
    target_company: str = "",
    min_role_score: float = 40.0,
    min_company_score: Optional[float] = None,
) -> List[JobPosting]:
    """
    Update role/company match scores on job postings, filter by thresholds, and rank
    descending by composite_score. Mirrors rank_and_filter_contacts for the JobPosting object.
    """
    has_target_roles = bool(target_roles and any(r.strip() for r in target_roles))
    has_target_company = bool(target_company and target_company.strip())
    effective_min_company = (
        min_company_score if min_company_score is not None else (60.0 if has_target_company else 0.0)
    )

    qualified: List[Tuple[float, JobPosting]] = []

    for job in jobs:
        job.role_match_score = score_role(target_roles, job.title or "") if has_target_roles else 100.0
        job.company_match_score = (
            score_company(target_company, job.company_name or "") if has_target_company else 100.0
        )

        if has_target_roles and job.role_match_score < min_role_score:
            continue
        if has_target_company and job.company_match_score < effective_min_company:
            continue

        priority = compute_composite_score(job.role_match_score, job.company_match_score)
        qualified.append((priority, job))

    qualified.sort(key=lambda item: item[0], reverse=True)
    return [job for _, job in qualified]


def rank_and_filter_contacts(
    contacts: List[LinkedInContact],
    target_roles: List[str],
    target_company: str,
    min_role_score: float = 40.0,
    min_company_score: Optional[float] = None,
) -> List[LinkedInContact]:
    """
    Update match scores, filter by thresholds, and rank candidate contacts.
    """
    has_target_roles = bool(target_roles and any(r.strip() for r in target_roles))
    has_target_company = bool(target_company and target_company.strip())
    effective_min_company = (
        min_company_score if min_company_score is not None else (60.0 if has_target_company else 0.0)
    )

    qualified_contacts: List[Tuple[float, LinkedInContact]] = []

    for contact in contacts:
        # 1. Update role match score
        if has_target_roles:
            contact.role_match_score = score_role(target_roles, contact.headline or "")
        else:
            contact.role_match_score = 100.0

        # 2. Update company match score
        if has_target_company:
            # Primary candidate text is current_company, fallback to headline
            if contact.current_company and contact.current_company.strip().lower() not in {
                "unknown",
                "none",
                "n/a",
                "",
            }:
                c_score = score_company(target_company, contact.current_company)
                # Check headline as well if current company was incomplete
                if c_score < 50.0 and contact.headline:
                    h_score = score_company(target_company, contact.headline)
                    is_past = bool(
                        re.search(
                            r"\b(ex|former|past|prev)\b.*?" + re.escape(clean_company_name(target_company)),
                            contact.headline,
                            re.IGNORECASE,
                        )
                    )
                    if h_score > c_score and not is_past:
                        c_score = h_score
            else:
                h_score = score_company(target_company, contact.headline or "")
                is_past = bool(
                    re.search(
                        r"\b(ex|former|past|prev)\b.*?" + re.escape(clean_company_name(target_company)),
                        contact.headline or "",
                        re.IGNORECASE,
                    )
                )
                c_score = 0.0 if is_past else h_score
            contact.company_match_score = c_score
        else:
            contact.company_match_score = 100.0

        # 3. Filter criteria
        if has_target_roles and contact.role_match_score < min_role_score:
            continue

        if has_target_company and contact.company_match_score < effective_min_company:
            continue

        # 4. Calculate total ranking priority score
        priority = calculate_contact_priority(contact, target_company)
        qualified_contacts.append((priority, contact))

    # Sort descending by priority score
    qualified_contacts.sort(key=lambda item: item[0], reverse=True)

    return [contact for _, contact in qualified_contacts]


# =====================================================================
# Post Engagement Scorer (0-100): alignment, author fit, recency, comment window, commentability
# =====================================================================

# FDE-free fallback only; the live lists come from derive_targets_from_core_cv().
DEFAULT_ENGAGEMENT_TARGETS: Dict[str, List[str]] = {
    "tier_a": ["vercel", "anthropic", "webflow", "vanta", "hightouch", "sierra", "harvey", "laurel", "netic", "zep"],
    "tier_b": [
        "claude", "claude code", "marketing engineer", "growth engineer", "web platform",
        "design system", "next.js", "nextjs", "headless cms", "sanity", "agent infrastructure", "ai agents",
        "mcp", "content systems", "developer experience",
    ],
    "tier_c": [
        "ai coding", "developer tools", "gtm engineer", "hiring", "we're hiring", "cms",
        "site performance", "web performance",
    ],
    "platform_terms": ["sanity", "webflow"],
    "target_company_slugs": [
        "vercel", "anthropicresearch", "anthropic", "vanta", "hightouch", "harvey-ai", "sierra", "laurel-ai", "webflow",
    ],
}

DEFAULT_ENGAGEMENT_TARGETS_PATH = "~/.config/chrome-agent/engagement_targets.json"

_ENGAGEMENT_WARMTH: Dict[str, float] = {"WARM": 1.0, "BRIDGE": 0.7, "COLD": 0.3, "FROZEN": 0.0}
_COMPANY_PAGE_AUTHOR_CAP = 0.6
_ENGAGEMENT_BAIT = re.compile(r"\b(giveaway|comment (below|\"?yes)|agree\?|like if|tag someone)", re.I)
_ANNOUNCEMENT = re.compile(
    r"(excited to announce|thrilled to (welcome|announce)|we['’]re hiring|we are hiring|"
    r"is now live|joining us at|join us)",
    re.I,
)


_DEFAULT_CORE_CV_PATH = "~/Sprintz/jobs/job-search/_shared_facts/core-cv.md"
_DEFAULT_PIPELINE_PATH = "~/Sprintz/jobs/job-search/README.md"

_ACTIVE_STATUSES = frozenset(
    {"researching", "networking", "drafting", "ready", "applied", "interviewing", "offer"}
)

# Ultra-generic stack terms: never count as alignment on their own.
ENGAGEMENT_STOPLIST = frozenset(
    {"js", "javascript", "rest apis", "rest api", "node.js", "nodejs", "graphql", "react", "typescript",
     "tailwind css", "tailwind", "ci/cd", "github actions"}
)

# Martech names inside the Growth & Measurement line that count as distinctive (tier_b).
_MARTECH_NAMES = frozenset(
    {"segment", "onetrust", "hubspot", "marketo", "salesforce", "zoominfo", "optimizely", "mparticle", "6sense"}
)

_SENIORITY = re.compile(r"^(principal|senior|sr\.?|staff|lead|junior|jr\.?)\s+", re.I)


def _split_list(text: str) -> List[str]:
    return [t.strip() for t in text.split(",") if t.strip()]


def _parse_core_cv(text: str) -> Tuple[List[str], Dict[str, List[str]]]:
    """Return (role_titles, {capability label lowercased: [items]}) from core-cv markdown."""
    titles: List[str] = []
    m = re.search(r"^\*\*(.+?)\*\*\s*$", text, re.M)
    if m:
        titles += [t.strip() for t in m.group(1).split("|") if t.strip()]
    for tm in re.finditer(r"^###\s+\*\*(.+?)\*\*", text, re.M):
        titles.append(re.sub(r"\s*\([^)]*\)", "", tm.group(1)).strip())
    seen, uniq = set(), []
    for t in titles:
        if t and t.lower() not in seen:
            seen.add(t.lower())
            uniq.append(t)
    caps: Dict[str, List[str]] = {}
    for cm in re.finditer(r"^\s*-\s+\*\*(.+?):\*\*\s*(.+)$", text, re.M):
        caps[cm.group(1).strip().lower()] = _split_list(cm.group(2))
    return uniq, caps


def _parse_pipeline_companies(text: str) -> List[str]:
    """Clean company names of active-status rows in the pipeline markdown table."""
    names: List[str] = []
    ci = si = None
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        low = [c.lower() for c in cells]
        if "company" in low and "status" in low:
            ci, si = low.index("company"), low.index("status")
            continue
        if ci is None or si is None or len(cells) <= max(ci, si) or set(cells[0]) <= set("-: "):
            continue
        if cells[si].strip().lower() not in _ACTIVE_STATUSES:
            continue
        raw = cells[ci]
        parts = [raw]
        for f in re.findall(r"\(formerly\s+([^)]+)\)", raw, re.I):
            parts.append(f)
        parts = [re.sub(r"\([^)]*\)", "", p) for p in parts]
        for part in parts:
            for piece in part.split("/"):
                c = clean_company_name(piece.strip())
                if c:
                    names.append(c)
    return list(dict.fromkeys(names))


def derive_targets_from_core_cv(core_cv_path: Optional[str] = None, pipeline_path: Optional[str] = None) -> dict:
    """
    Derive engagement targets from the core CV and the job-search pipeline table.
    Paths: argument, else env JSB_CORE_CV / JSB_PIPELINE, else the Sprintz defaults.
    Same keys as DEFAULT_ENGAGEMENT_TARGETS plus role_titles. Any piece that cannot be
    parsed falls back to the FDE-free defaults; never raises.
    """
    out = {k: list(v) for k, v in DEFAULT_ENGAGEMENT_TARGETS.items()}
    out["role_titles"] = []
    cv_p = Path(os.path.expanduser(core_cv_path or os.environ.get("JSB_CORE_CV") or _DEFAULT_CORE_CV_PATH))
    pl_p = Path(os.path.expanduser(pipeline_path or os.environ.get("JSB_PIPELINE") or _DEFAULT_PIPELINE_PATH))

    try:
        titles, caps = _parse_core_cv(cv_p.read_text(encoding="utf-8"))
    except (OSError, ValueError, re.error):
        titles, caps = [], {}
    if titles:
        lowered = [t.lower() for t in titles]
        for t in list(lowered):
            stripped = _SENIORITY.sub("", t)
            if stripped and stripped != t:
                lowered.append(stripped)
        platforms = [x.lower() for x in caps.get("platforms & cms", [])]
        growth = [x.lower() for x in caps.get("growth & measurement", [])]
        web = [x.lower() for x in caps.get("web engineering", [])]
        quality = [x.lower() for x in caps.get("quality & delivery", [])]
        tier_b = lowered + platforms + [x for x in growth if x in _MARTECH_NAMES]
        tier_c = [x for x in growth if x not in _MARTECH_NAMES] + quality + web
        tier_c = [x for x in tier_c if x not in ENGAGEMENT_STOPLIST]
        tier_c += ["nextjs"] if "next.js" in tier_c else []
        tier_c.append("hiring")
        out["role_titles"] = titles
        out["platform_terms"] = list(dict.fromkeys(
            x for x in platforms + [g for g in growth if g in _MARTECH_NAMES] if x not in ENGAGEMENT_STOPLIST
        ))
        out["tier_b"] = list(dict.fromkeys(x for x in tier_b if x not in ENGAGEMENT_STOPLIST))
        out["tier_c"] = list(dict.fromkeys(tier_c))

    try:
        companies = _parse_pipeline_companies(pl_p.read_text(encoding="utf-8"))
    except (OSError, ValueError, re.error):
        companies = []
    if companies:
        out["tier_a"] = companies
        out["target_company_slugs"] = list(dict.fromkeys(re.sub(r"\s+", "-", c) for c in companies))
    return out


def load_engagement_targets(path: Optional[str] = None) -> dict:
    """
    Base = derive_targets_from_core_cv() (core-cv + pipeline; FDE-free defaults on failure),
    merged with the optional JSON override (default ~/.config/chrome-agent/engagement_targets.json).
    A missing or malformed override leaves the derived base. Never creates the file.
    """
    targets = derive_targets_from_core_cv()
    p = Path(os.path.expanduser(path or DEFAULT_ENGAGEMENT_TARGETS_PATH))
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return targets
    if not isinstance(data, dict):
        return targets
    for key, value in data.items():
        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            targets[key] = list(value)
    return targets


# Company names that are also plain English words: tier-A matching is case-sensitive for these
# (Title Case or ALL CAPS only, never lowercase).
GENERIC_COMPANY_NAMES = frozenset({"icon", "employ", "typeface", "snowflake", "samba", "aquent"})


def _keyword_hits(text: str, terms: Sequence[str], case_sensitive_terms: frozenset = frozenset()) -> List[str]:
    """Exact word-boundary keyword hits; case-insensitive except terms in case_sensitive_terms."""
    t = text or ""
    tl = t.lower()
    hits = []
    for k in terms:
        kl = k.lower()
        if kl in case_sensitive_terms:
            variants = {kl.title(), kl.upper()}
            found = any(re.search(r"(?<![A-Za-z0-9])" + re.escape(v) + r"(?![A-Za-z0-9])", t) for v in variants)
        else:
            found = re.search(r"(?<![a-z0-9])" + re.escape(kl) + r"(?![a-z0-9])", tl)
        if found:
            hits.append(k)
    return hits


_CLUSTER_ALIASES = {"nextjs": "next.js", "ab testing": "a/b testing", "a-b testing": "a/b testing",
                    "design system": "design systems", "web vitals": "core web vitals"}


def _cluster_key(hits: Sequence[str], targets: Optional[dict] = None) -> str:
    """
    Primary matched keyword, lowercased and alias-normalized. Priority (cluster only, not the score):
    platform/martech terms (targets["platform_terms"]), then tier-A companies, then remaining tier-B
    (role titles), then tier C. Without targets, the first hit wins.
    """
    if not hits:
        return ""
    if targets:
        low = {x.lower() for x in targets.get("platform_terms", [])}
        a = {x.lower() for x in targets.get("tier_a", [])}
        b = {x.lower() for x in targets.get("tier_b", [])}

        def rank(h: str) -> int:
            hl = h.lower()
            return 0 if hl in low else 1 if hl in a else 2 if hl in b else 3

        hits = sorted(hits, key=rank)  # stable: keeps tier order within a group
    k = hits[0].lower()
    return _CLUSTER_ALIASES.get(k, k)


def _post_alignment(text: str, targets: dict) -> Tuple[float, List[str]]:
    """Tiered alignment 0.0-1.0 (A=1.0, B=0.7, C=0.3, +0.1 per extra hit capped +0.2) and all matched keywords."""
    a = _keyword_hits(text, targets.get("tier_a", []), GENERIC_COMPANY_NAMES)
    b = _keyword_hits(text, targets.get("tier_b", []))
    c = _keyword_hits(text, targets.get("tier_c", []))
    base = 1.0 if a else 0.7 if b else 0.3 if c else 0.0
    if not base:
        return 0.0, []
    bonus = min(0.1 * (len(a) + len(b) + len(c) - 1), 0.2)
    return min(base + bonus, 1.0), a + b + c


def _post_age_hours(post_id: str, now: datetime) -> float:
    """Age in hours from the LinkedIn snowflake post_id; inf if the id is not numeric."""
    try:
        ms = int(post_id) >> 22
        posted = datetime.fromtimestamp(ms / 1000, timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return float("inf")
    return max((now - posted).total_seconds() / 3600, 0.0)


def _target_company_keys(targets: dict) -> set:
    """Normalized target company names derived from tier_a and target_company_slugs."""
    keys = set()
    for name in list(targets.get("tier_a", [])) + list(targets.get("target_company_slugs", [])):
        cleaned = clean_company_name(name)
        if cleaned:
            keys.add(cleaned)
    return keys


def _commentability(text: str) -> float:
    """Length tier (0 / 0.6 / 1.0), x0.3 for engagement bait, x0.6 for announcements."""
    n = len(text or "")
    s = 0.0 if n < 80 else 0.6 if n < 200 else 1.0
    if _ENGAGEMENT_BAIT.search(text or ""):
        s *= 0.3
    if _ANNOUNCEMENT.search(text or ""):
        s *= 0.6
    return s


def score_post_engagement(
    post: Post,
    contact_tier: Optional[str],
    creator_fit: float,
    is_target_employer: bool,
    targets: dict,
    now: Optional[datetime] = None,
) -> Tuple[float, dict]:
    """
    Returns (0-100 score, breakdown) for a post: Alignment 35 + Author fit 25 + Recency 20
    + Comment window 15 + Commentability 5. Zero alignment scores 0.0 (never surfaced).
    Company-page authors are capped at 0.6 author-fit; persons keep full fit and get 1.0
    when their author_id or employer is a target company.
    Breakdown keys: align, author, recency, window, commentability, hits, age_hours, cluster.
    """
    now = now or datetime.now(timezone.utc)
    text = post.text or ""
    align, hit_list = _post_alignment(text, targets)

    slugs = {s.lower() for s in targets.get("target_company_slugs", [])}
    is_target = bool(is_target_employer) or (post.author_id or "").lower() in slugs
    fit = max(_ENGAGEMENT_WARMTH.get(contact_tier or "", 0.0), creator_fit or 0.0)
    if is_target:
        fit = 1.0
    if post.author_type == "company":
        fit = min(fit, _COMPANY_PAGE_AUTHOR_CAP)

    age_h = _post_age_hours(post.post_id, now)
    recency = 0.5 ** (age_h / 48) if age_h <= 168 else 0.0

    x = math.log10((post.comment_count or 0) + 1)
    window = math.exp(-((x - 1.7) ** 2) / (2 * 0.6 ** 2))

    comm = _commentability(text)

    breakdown = {
        "align": 35 * align,
        "author": 25 * fit,
        "recency": 20 * recency,
        "window": 15 * window,
        "commentability": 5 * comm,
        "hits": hit_list,
        "age_hours": age_h,
        "cluster": _cluster_key(hit_list, targets),
    }
    if align == 0.0:
        return 0.0, breakdown
    total = breakdown["align"] + breakdown["author"] + breakdown["recency"] + breakdown["window"] + breakdown["commentability"]
    return round(total, 2), breakdown


def _creator_fit(posts: List[Post], targets: dict, min_posts: int) -> Dict[str, float]:
    by_author: Dict[str, List[float]] = defaultdict(list)
    for p in posts:
        by_author[p.author_name].append(_post_alignment(p.text or "", targets)[0])
    fits: Dict[str, float] = {}
    for name, vals in by_author.items():
        if len(vals) < min_posts:
            fits[name] = 0.0
        else:
            share = sum(1 for v in vals if v >= 0.7) / len(vals)
            fits[name] = min(share / 0.5, 1.0)
    return fits


def compute_creator_fit(posts: List[Post], targets: dict) -> Dict[str, float]:
    """
    Per author_name: share of that author's posts with alignment >= 0.7, needs >= 3 posts
    else 0.0, scaled so 50% aligned = 1.0, capped at 1.0.
    """
    return _creator_fit(posts, targets, 3)


def rank_engagement_posts(
    posts: List[Post],
    contacts: List[LinkedInContact],
    queued_target_ids: Sequence[str],
    targets: Optional[dict] = None,
    top_n: int = 10,
    max_age_days: int = 7,
    now: Optional[datetime] = None,
    max_company_pages: Optional[int] = 3,
    max_per_cluster: Optional[int] = 2,
    min_score: float = 50.0,
    fill_back: bool = False,
) -> List[Tuple[float, Post, dict]]:
    """
    Rank posts worth commenting on, descending by score_post_engagement. Collapses near-duplicate posts (keeping the
    highest scored), skips already-queued
    posts, zero-alignment posts, and posts older than max_age_days. At most 2 posts per
    author_name and at most max_company_pages posts with author_type == "company" in the first
    top_n results (None disables the page cap); min_score drops posts scoring below the floor before any cap, and fill-back never restores them (0 disables; may return fewer than top_n rows). max_per_cluster limits posts sharing a primary keyword cluster (None disables); extras are pushed below and deferred posts
    back-fill in score order if fewer than top_n qualify. Returns (score, post, breakdown).
    The caps are hard by default: posts deferred by the author, page, or cluster cap are never re-added, so the
    list may be shorter than top_n. Pass fill_back=True to append deferred (capped, still above-floor) posts in
    score order to reach top_n.
    """
    targets = targets or load_engagement_targets()
    now = now or datetime.now(timezone.utc)
    queued = set(queued_target_ids or [])
    creator = compute_creator_fit(posts, targets)
    company_keys = _target_company_keys(targets)
    by_name = {(c.name or "").strip().lower(): c for c in contacts}

    rows: List[Tuple[float, Post, dict]] = []
    for post in posts:
        if post.post_id in queued:
            continue
        contact = by_name.get(post.author_name.strip().lower())
        tier = contact.contact_tier if contact else None
        employer = clean_company_name(contact.current_company or "") if contact else ""
        is_target_emp = bool(employer) and employer in company_keys
        score, bd = score_post_engagement(
            post, tier, creator.get(post.author_name, 0.0), is_target_emp, targets, now
        )
        if score <= 0.0 or score < min_score or bd["age_hours"] > max_age_days * 24:
            continue
        rows.append((score, post, bd))

    rows.sort(key=lambda r: r[0], reverse=True)

    # Collapse near-duplicates (same author + same normalized first 120 chars; empty text needs same id).
    seen_keys: set = set()
    unique_rows: List[Tuple[float, Post, dict]] = []
    for row in rows:
        p = row[1]
        norm = re.sub(r"\s+", " ", (p.text or "").strip().lower())[:120]
        key = ((p.author_name or "").strip().lower(), norm if norm else "id:" + str(p.post_id))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_rows.append(row)
    rows = unique_rows

    selected: List[Tuple[float, Post, dict]] = []
    deferred: List[Tuple[float, Post, dict]] = []
    counts: Dict[str, int] = defaultdict(int)
    pages = 0
    clusters: Dict[str, int] = defaultdict(int)
    for row in rows:
        name = row[1].author_name
        is_page = row[1].author_type == "company"
        page_ok = not is_page or max_company_pages is None or pages < max_company_pages
        ck = row[2].get("cluster", "")
        cluster_ok = max_per_cluster is None or clusters[ck] < max_per_cluster
        if len(selected) < top_n and counts[name] < 2 and page_ok and cluster_ok:
            counts[name] += 1
            pages += is_page
            clusters[ck] += 1
            selected.append(row)
        else:
            deferred.append(row)
    return (selected + deferred)[:top_n] if fill_back else selected


def rank_creators(
    posts: List[Post],
    targets: Optional[dict] = None,
    min_posts: int = 3,
    top_n: int = 10,
) -> List[Tuple[str, float, int]]:
    """Rank authors by creator consistency. Returns (author_name, creator_fit, post_count) descending."""
    targets = targets or load_engagement_targets()
    counts: Dict[str, int] = defaultdict(int)
    for p in posts:
        counts[p.author_name] += 1
    fits = _creator_fit(posts, targets, min_posts)
    rows = [(n, fits[n], counts[n]) for n in fits if counts[n] >= min_posts]
    rows.sort(key=lambda r: (-r[1], -r[2], r[0]))
    return rows[:top_n]


# =====================================================================
# Standalone Test Suite & Verification Harness
# =====================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("RUNNING ENTITY MATCHER VERIFICATION HARNESS (Node 2c)")
    print("=" * 80)

    # -----------------------------------------------------------------
    # Suite 1: Tech & Sales Role Acronym & Synonym Matching
    # -----------------------------------------------------------------
    print("\n[Suite 1] Role Acronyms & Synonyms Matching...")
    role_cases = [
        # (target_roles, headline, min_expected_score, description)
        (
            ["Senior Marketing Engineer"],
            "Sr Marketing Engineer @ Palantir | Ex-Google",
            90.0,
            "Sr abbreviation vs Senior Marketing Engineer",
        ),
        (
            ["Sr Marketing Engineer"],
            "Senior Marketing Engineer @ Palantir",
            90.0,
            "Senior Marketing Engineer vs Sr abbreviation",
        ),
        (
            ["Software Engineer"],
            "Senior SWE II at Stripe",
            90.0,
            "Senior SWE II vs Software Engineer",
        ),
        (
            ["Account Executive"],
            "Enterprise AE - Cloud Infrastructure @ Snowflake",
            90.0,
            "Enterprise AE vs Account Executive",
        ),
        (
            ["Engineering Manager"],
            "EM - Growth & Platform @ Datadog",
            90.0,
            "EM vs Engineering Manager",
        ),
        (
            ["Solutions Engineer"],
            "Sr. SE @ HashiCorp",
            90.0,
            "Sr. SE vs Solutions Engineer",
        ),
        (
            ["Product Manager"],
            "Lead PM, Search & Discovery @ Figma",
            90.0,
            "Lead PM vs Product Manager",
        ),
        (
            ["Software Engineer"],
            "Staff SDE (Distributed Systems) @ Amazon",
            90.0,
            "Staff SDE vs Software Engineer",
        ),
    ]

    for targets, headline, min_score, desc in role_cases:
        actual_score = score_role(targets, headline)
        assert (
            actual_score >= min_score
        ), f"FAILED: {desc} -> Score {actual_score} < expected {min_score}"
        print(f"  ✓ PASS: {desc:<48} -> Score: {actual_score:.2f}")

    # Negative role test
    unrelated_score = score_role(["Senior Web Developer"], "Account Executive @ Palantir")
    assert unrelated_score < 35.0, f"FAILED: Unrelated role score too high: {unrelated_score}"
    print(f"  ✓ PASS: Unrelated role filter (Web Developer vs Account Executive) -> Score: {unrelated_score:.2f}")

    # -----------------------------------------------------------------
    # Suite 2: Company Normalization & Alias Variations
    # -----------------------------------------------------------------
    print("\n[Suite 2] Company Suffixes, Domain Stems & Alias Matching...")
    company_cases = [
        ("Palantir Technologies", "Palantir", 100.0, "Palantir Technologies vs Palantir"),
        ("Palantir", "Palantir Technologies", 100.0, "Palantir vs Palantir Technologies"),
        ("Google LLC", "Google", 100.0, "Google LLC vs Google"),
        ("Stripe", "Stripe, Inc.", 100.0, "Stripe vs Stripe, Inc."),
        ("Apple", "Apple Inc.", 100.0, "Apple vs Apple Inc."),
        ("Verdant", "Verdant Inc", 100.0, "Verdant vs Verdant Inc"),
        ("Zephyria AI", "Zephyria", 100.0, "Zephyria AI vs Zephyria"),
        ("Umbra", "Umbra AI", 100.0, "Umbra vs Umbra AI"),
        ("Halyard", "halyard.ai", 100.0, "Halyard vs halyard.ai"),
        ("Larkspur", "larkspur.ai", 100.0, "Larkspur vs larkspur.ai"),
        ("Selvane", "Selvane AI", 100.0, "Selvane vs Selvane AI"),
        ("Hexlight", "Hexlight Inc", 100.0, "Hexlight vs Hexlight Inc"),
        ("Snowflake", "Senior AE at Snowflake", 100.0, "Snowflake in headline context"),
    ]

    for target_comp, cand_text, min_score, desc in company_cases:
        c_score = score_company(target_comp, cand_text)
        assert (
            c_score >= min_score
        ), f"FAILED: {desc} -> Score {c_score} < expected {min_score}"
        print(f"  ✓ PASS: {desc:<48} -> Score: {c_score:.2f}")

    # False positive guards
    meta_fp = score_company("Meta", "Metadata Systems")
    assert meta_fp < 75.0, f"FAILED: False positive 'Meta' matched 'Metadata Systems' with {meta_fp}"
    print(f"  ✓ PASS: Guard against Meta vs Metadata Systems        -> Score: {meta_fp:.2f}")

    apple_fp = score_company("Apple", "Snapple Beverage Corp")
    assert apple_fp < 75.0, f"FAILED: False positive 'Apple' matched 'Snapple' with {apple_fp}"
    print(f"  ✓ PASS: Guard against Apple vs Snapple                -> Score: {apple_fp:.2f}")

    wrong_comp = score_company("Google", "Palantir Technologies")
    assert wrong_comp < 25.0, f"FAILED: Google vs Palantir scored too high: {wrong_comp}"
    print(f"  ✓ PASS: Different company check (Google vs Palantir)  -> Score: {wrong_comp:.2f}")

    # -----------------------------------------------------------------
    # Suite 3: Pipeline Requisitions & Role Matches
    # -----------------------------------------------------------------
    print("\n[Suite 3] Pipeline Requisitions & Role Matches from Job Search...")
    pipeline_evals = [
        (
            ["Engineering Manager, Web", "Head of Web Engineering"],
            "EM, Web Experience @ Umbra AI",
            85.0,
            "Umbra: EM, Web Experience",
        ),
        (
            ["Engineering Manager, Web", "Head of Web Engineering"],
            "Head of Web Engineering @ Umbra",
            100.0,
            "Umbra: Head of Web Engineering",
        ),
        (
            ["Solo Marketing Engineer / Agent Infrastructure"],
            "Marketing Engineer & Agent Infrastructure Lead @ Zephyria",
            85.0,
            "Zephyria: Marketing Engineer & Agent Infra Lead",
        ),
        (
            ["Founding Web Platform Engineer"],
            "Founding Engineer - Web Platform @ Nexoria",
            90.0,
            "Nexoria: Founding Engineer - Web Platform",
        ),
        (
            ["Senior Marketing Web Engineer"],
            "Senior Web Developer @ ComplyCore",
            60.0,
            "ComplyCore: Senior Web Developer",
        ),
        (
            ["Frontend Web Developer"],
            "Frontend Web Developer @ Selvane AI",
            100.0,
            "Selvane: Frontend Web Developer",
        ),
        (
            ["Senior Marketing Engineer", "Marketing Web Engineer"],
            "Sr Marketing Engineer @ Hexlight",
            90.0,
            "Hexlight: Sr Marketing Engineer",
        ),
        (
            ["Senior Web Developer"],
            "Sr Web Developer @ Larkspur",
            90.0,
            "Larkspur: Sr Web Developer",
        ),
        (
            ["Field Product Specialist"],
            "Field Product Specialist @ Halyard",
            100.0,
            "Halyard: Field Product Specialist",
        ),
        (
            ["Principal Marketing Engineer"],
            "Principal Marketing Engineer @ Verdant Inc",
            100.0,
            "Verdant: Principal Marketing Engineer",
        ),
    ]

    for targets, headline, min_score, desc in pipeline_evals:
        score = score_role(targets, headline)
        assert score >= min_score, f"FAILED: {desc} -> Score {score} < {min_score}"
        print(f"  ✓ PASS: {desc:<48} -> Score: {score:.2f}")

    # -----------------------------------------------------------------
    # Suite 4: End-to-End Ranking & Filtering with Fictional Test Fixture Data
    # -----------------------------------------------------------------
    print("\n[Suite 4] End-to-End Ranking & Decision Maker Prioritization (Fictional Contacts)...")

    # Fictional test fixtures modeled on a private contacts list. No real people or companies.
    real_network_contacts = [
        LinkedInContact(
            urn_id="urn:li:fsd_profile:ACoAA-diana-prince",
            name="Diana Prince",
            headline="Marketing Leader / VP Growth Marketing & Operations",
            profile_url="https://linkedin.com/in/diana-prince",
            degree="2nd",
            current_company="Larkspur",
            mutual_count=1,
            mutual_sample=["Peter Parker"],
        ),
        LinkedInContact(
            urn_id="urn:li:fsd_profile:ACoAA-tony-stark",
            name="Tony Stark",
            headline="Head of Growth Engineering @ Verdant",
            profile_url="https://linkedin.com/in/tony-stark-eng",
            degree="2nd",
            current_company="Verdant",
            mutual_count=1,
            mutual_sample=["Nick Fury"],
        ),
        LinkedInContact(
            urn_id="urn:li:fsd_profile:ACoAA-selina-kyle",
            name="Selina Kyle",
            headline="Talent at Halyard",
            profile_url="https://linkedin.com/in/selina-kyle",
            degree="1st",
            current_company="Halyard",
            mutual_count=9,
            mutual_sample=["Jean Grey", "Jim Gordon"],
        ),
        LinkedInContact(
            urn_id="urn:li:fsd_profile:ACoAA-natasha-romanoff",
            name="Natasha Romanoff",
            headline="Technical Talent @ Hexlight",
            profile_url="https://linkedin.com/in/natasha-romanoff",
            degree="2nd",
            current_company="Hexlight",
            mutual_count=2,
            mutual_sample=["Steve Rogers", "Bucky Barnes"],
        ),
        LinkedInContact(
            urn_id="urn:li:fsd_profile:ACoAA-peter-parker",
            name="Peter Parker",
            headline="Senior Weftly Developer / Designer",
            profile_url="https://linkedin.com/in/peter-parker-dev",
            degree="1st",
            current_company="Weftly",
            mutual_count=5,
            mutual_sample=["Diana Prince", "Lois Lane"],
        ),
        LinkedInContact(
            urn_id="urn:li:fsd_profile:ACoAA-clark-kent",
            name="Clark Kent",
            headline="Software Engineer at Verdant",
            profile_url="https://linkedin.com/in/clark-kent",
            degree="2nd",
            current_company="Verdant",
            mutual_count=1,
            mutual_sample=["Alfred Pennyworth"],
        ),
        LinkedInContact(
            urn_id="urn:li:fsd_profile:ACoAA-barbara-gordon",
            name="Barbara Gordon",
            headline="Demand Generation Manager @ larkspur.ai",
            profile_url="https://linkedin.com/in/barbara-gordon",
            degree="2nd",
            current_company="Larkspur",
            mutual_count=1,
            mutual_sample=["Aunt May"],
        ),
    ]

    # Test Scenario A: Verdant Site Engineer & Growth Engineering
    # Tony Stark (Head of Growth Engineering / Direct Hiring Lead) MUST rank #1 ahead of Clark Kent (IC Software Engineer)
    # and all non-Verdant contacts must be filtered out.
    print("  -> Scenario A: Verdant Site Engineer Requisition")
    verdant_ranked = rank_and_filter_contacts(
        contacts=real_network_contacts,
        target_roles=["Site Engineer", "Head of Growth Engineering"],
        target_company="Verdant",
        min_role_score=40.0,
    )

    assert len(verdant_ranked) >= 2, f"Expected at least 2 Verdant contacts, got {len(verdant_ranked)}"
    top_verdant = verdant_ranked[0]
    print(f"     Top Verdant Contact: {top_verdant.name} ({top_verdant.headline})")
    print(f"     Role Score: {top_verdant.role_match_score}, Company Score: {top_verdant.company_match_score}")
    assert (
        top_verdant.name == "Tony Stark"
    ), f"FAILED: Expected Tony Stark (Hiring Lead) at top, got {top_verdant.name}"
    assert (
        verdant_ranked[1].name == "Clark Kent"
    ), f"FAILED: Expected Clark Kent (IC) at #2, got {verdant_ranked[1].name}"
    print("     ✓ Verified: Tony Stark (Hiring Lead) sorted #1 above Clark Kent (IC).")

    # Test Scenario B: Larkspur Principal Growth Marketing Engineer
    # Diana Prince (VP Growth Marketing & Operations / Direct Hiring Manager) MUST rank #1
    print("  -> Scenario B: Larkspur Principal Growth Marketing Engineer Requisition")
    larkspur_ranked = rank_and_filter_contacts(
        contacts=real_network_contacts,
        target_roles=["Principal Growth Marketing Engineer", "VP Growth Marketing & Operations"],
        target_company="Larkspur",
        min_role_score=40.0,
    )

    assert len(larkspur_ranked) >= 1, f"Expected Larkspur contacts, got {len(larkspur_ranked)}"
    top_larkspur = larkspur_ranked[0]
    print(f"     Top Larkspur Contact: {top_larkspur.name} ({top_larkspur.headline})")
    print(f"     Role Score: {top_larkspur.role_match_score}, Company Score: {top_larkspur.company_match_score}")
    assert (
        top_larkspur.name == "Diana Prince"
    ), f"FAILED: Expected Diana Prince (Hiring Manager) at top, got {top_larkspur.name}"
    print("     ✓ Verified: Diana Prince (Direct Hiring Manager) sorted #1.")

    # Test Scenario C: Halyard Staff Web Engineer / Talent Recruiting
    print("  -> Scenario C: Halyard Staff Web Engineer / Talent Partner Requisition")
    halyard_ranked = rank_and_filter_contacts(
        contacts=real_network_contacts,
        target_roles=["Staff Web Engineer", "Talent", "Technical Recruiter"],
        target_company="Halyard",
        min_role_score=40.0,
    )

    assert len(halyard_ranked) >= 1, f"Expected Halyard contacts, got {len(halyard_ranked)}"
    top_halyard = halyard_ranked[0]
    print(f"     Top Halyard Contact: {top_halyard.name} ({top_halyard.headline})")
    print(f"     Role Score: {top_halyard.role_match_score}, Company Score: {top_halyard.company_match_score}")
    assert (
        top_halyard.name == "Selina Kyle"
    ), f"FAILED: Expected Selina Kyle at top, got {top_halyard.name}"
    print("     ✓ Verified: Selina Kyle (1st-degree Talent Partner) ranked and matched.")

    # Test Scenario D: Strict Filtering of Irrelevant Roles & Companies
    print("  -> Scenario D: Strict Filtering Verification")
    filtered_results = rank_and_filter_contacts(
        contacts=real_network_contacts,
        target_roles=["Principal Marketing Engineer"],
        target_company="Hexlight",
        min_role_score=40.0,
    )
    # Natasha Romanoff is at Hexlight, but role is Technical Talent (score < 40 for Principal Marketing Engineer)
    for c in filtered_results:
        assert c.company_match_score >= 35.0, f"Filtered candidate from wrong company: {c.name}"
        assert c.role_match_score >= 40.0, f"Candidate with low role score not filtered: {c.name}"
    print(f"     ✓ Verified: Strict role score threshold (>= 40.0) correctly pruned non-matches.")

    # -----------------------------------------------------------------
    # Suite 5: Post Engagement Scorer
    # -----------------------------------------------------------------
    print("\n[Suite 5] Post Engagement Scorer (rank_engagement_posts)...")
    from datetime import timedelta

    # Missing override file leaves the derived base untouched
    _base = derive_targets_from_core_cv()
    assert load_engagement_targets("/nonexistent/engagement_targets.json") == _base, "FAILED: missing override must return derived base"
    print("  ✓ PASS: load_engagement_targets returns derived base when override file missing")

    # Fixed fixture targets so scoring tests do not depend on the live core-cv/pipeline
    T = {
        "tier_a": ["vercel"],
        "tier_b": ["claude", "claude code"],
        "tier_c": ["cms", "hiring"],
        "target_company_slugs": ["vercel"],
    }

    _now = datetime.now(timezone.utc)
    _seq = [0]

    def _mk(text, age_days=1.0, author="Pat Author", atype="person", comments=50, author_id=None):
        _seq[0] += 1
        ms = int((_now - timedelta(days=age_days)).timestamp() * 1000) - _seq[0]
        pid = str(ms << 22)
        return Post(
            post_id=pid,
            post_url=f"https://www.linkedin.com/feed/update/urn:li:activity:{pid}/",
            author_name=author,
            author_type=atype,
            author_id=author_id,
            text=text,
            comment_count=comments,
            like_count=100,
        )

    pad = " We spent the quarter rebuilding how our team ships and here is what I would do differently next time around."

    def _sc(p, tier=None, cf=0.0, emp=False):
        return score_post_engagement(p, tier, cf, emp, T, _now)[0]

    sa = _sc(_mk("Notes on vercel deploys." + pad))
    sb = _sc(_mk("Notes on claude deploys." + pad))
    sc_ = _sc(_mk("Notes on cms deploys." + pad))
    assert sa > sb > sc_ > 0, f"FAILED: tier ordering {sa} {sb} {sc_}"
    print(f"  ✓ PASS: tier A > tier B > tier C ({sa:.1f} > {sb:.1f} > {sc_:.1f})")

    s1 = _sc(_mk("Notes on claude deploys." + pad, age_days=1))
    s6 = _sc(_mk("Notes on claude deploys." + pad, age_days=6))
    assert s6 < s1, f"FAILED: 6-day post {s6} not below 1-day post {s1}"
    print(f"  ✓ PASS: 6-day-old post scores lower than 1-day-old ({s6:.1f} < {s1:.1f})")

    sp = _sc(_mk("Notes on claude deploys." + pad), tier="WARM")
    sco = _sc(_mk("Notes on claude deploys." + pad, atype="company"), tier="WARM")
    assert sco < sp, f"FAILED: company page {sco} not below person {sp}"
    tp = _sc(_mk("Notes on claude deploys." + pad, atype="company", author_id="vercel"))
    assert tp <= sp, "FAILED: target company page must not beat a warm person"
    print(f"  ✓ PASS: company page scores lower than person ({sco:.1f} < {sp:.1f})")

    plain = score_post_engagement(_mk("Notes on claude deploys." + pad), None, 0.0, False, T, _now)[1]["commentability"]
    ann1 = score_post_engagement(_mk("Excited to announce our claude deploys." + pad), None, 0.0, False, T, _now)[1]["commentability"]
    ann2 = score_post_engagement(_mk("We're hiring for claude deploys." + pad), None, 0.0, False, T, _now)[1]["commentability"]
    assert abs(ann1 - plain * 0.6) < 1e-9 and abs(ann2 - plain * 0.6) < 1e-9, f"FAILED: announcement discount {plain} {ann1} {ann2}"
    print("  ✓ PASS: announcement phrases discount commentability x0.6 (2 phrases)")

    viral = _mk("Amazing sunrise run this morning, feeling grateful for the team and the community." + pad, comments=5000)
    assert _sc(viral) == 0.0
    r = rank_engagement_posts([viral], [], [], T, now=_now)
    assert r == [], "FAILED: zero-alignment viral post surfaced"
    print("  ✓ PASS: zero-alignment viral post excluded")

    multi = [_mk(f"Take {i} on claude code agents." + pad, author="Prolific Pat") for i in range(5)]
    others = [_mk(f"Other take {i} on claude." + pad, author=f"Other {i}", comments=5) for i in range(10)]
    ranked = rank_engagement_posts(multi + others, [], [], T, top_n=10, now=_now, max_per_cluster=None, min_score=0)
    per_author: dict = {}
    for _, p, _ in ranked:
        per_author[p.author_name] = per_author.get(p.author_name, 0) + 1
    assert len(ranked) == 10 and per_author["Prolific Pat"] <= 2, f"FAILED: diversity cap {per_author}"
    assert all(ranked[i][0] >= ranked[i + 1][0] for i in range(2)), "FAILED: head not sorted"
    print(f"  ✓ PASS: diversity cap holds ({per_author['Prolific Pat']} of 5 from one author in top 10)")

    # Company-page cap
    pages6 = [_mk("Page take on claude code agents." + pad, author=f"Page {i}", atype="company", comments=50 - i) for i in range(6)]
    people6 = [_mk("Person take on claude." + pad, author=f"Person {i}", comments=5 + i * 40) for i in range(7)]

    def _npages(rr):
        return sum(1 for _, p, _ in rr if p.author_type == "company")

    rk = rank_engagement_posts(pages6 + people6, [], [], T, top_n=10, now=_now, max_per_cluster=None, min_score=0)
    assert len(rk) == 10 and _npages(rk) <= 3, f"FAILED: page cap {_npages(rk)}"
    assert sum(1 for _, p, _ in rk if p.author_type == "person") == 7, "FAILED: freed slots not given to people"
    rk_off = rank_engagement_posts(pages6 + people6, [], [], T, top_n=10, now=_now, max_company_pages=None, max_per_cluster=None, min_score=0)
    assert _npages(rk_off) > 3, f"FAILED: None should disable page cap ({_npages(rk_off)})"
    rk4 = rank_engagement_posts(pages6 + people6[:4], [], [], T, top_n=10, now=_now, max_per_cluster=None, min_score=0, fill_back=True)
    rk4_hard = rank_engagement_posts(pages6 + people6[:4], [], [], T, top_n=10, now=_now, max_per_cluster=None, min_score=0)
    assert len(rk4_hard) == 7 and _npages(rk4_hard) == 3, f"FAILED: hard page cap ({len(rk4_hard)}, {_npages(rk4_hard)})"
    assert len(rk4) == 10 and _npages(rk4) == 6, f"FAILED: fill-back ({len(rk4)}, {_npages(rk4)})"
    assert all(p.author_type == "person" for _, p, _ in rk4[:4]) or _npages(rk4[:7]) <= 3, "FAILED: fill-back order"
    both = rank_engagement_posts(
        pages6 + [_mk(f"Take {i} on claude code agents." + pad, author="Prolific Pat") for i in range(4)] + people6,
        [], [], T, top_n=8, now=_now, max_per_cluster=None, min_score=0,
    )
    pa = sum(1 for _, p, _ in both if p.author_name == "Prolific Pat")
    assert _npages(both) <= 3 and pa <= 2 and len(both) == 8, f"FAILED: combined caps pages={_npages(both)} pat={pa}"
    print("  ✓ PASS: company-page cap (<=3 in top 10), None disables, fill-back, works with author cap")

    dupa = _mk("Notes on claude deploys and more." + pad, author="Dup Dana")
    dupb = _mk("  notes on CLAUDE deploys   and more." + pad, author="dup dana")
    rd = rank_engagement_posts([dupa, dupb], [], [], T, now=_now)
    assert len(rd) == 1, f"FAILED: duplicate collapse returned {len(rd)}"
    other = _mk("Notes on claude deploys and more." + pad, author="Someone Else")
    assert len(rank_engagement_posts([dupa, other], [], [], T, now=_now)) == 2, "FAILED: different authors collapsed"
    print("  ✓ PASS: near-duplicate posts (same author, same text prefix, different ids) collapse to one")

    G = {"tier_a": ["icon", "snowflake", "vercel"], "tier_b": [], "tier_c": [], "target_company_slugs": []}
    assert _post_alignment("Designing better UI icon sets and an icon font.", G)[0] == 0.0, "FAILED: lowercase icon matched"
    assert _post_alignment("Investors back ICON plc in a new round.", G)[0] > 0, "FAILED: ICON plc"
    assert _post_alignment("Snowflake announced a new feature.", G)[0] > 0, "FAILED: Snowflake"
    assert _post_alignment("Every snowflake is unique.", G)[0] == 0.0, "FAILED: lowercase snowflake matched"
    assert _post_alignment("notes on VERCEL and vercel", G)[0] > 0, "FAILED: non-generic name must stay case-insensitive"
    print("  ✓ PASS: generic company names are case-sensitive in tier A (icon no, ICON yes, Snowflake yes, snowflake no)")

    # Topic-cluster cap
    hub = [_mk(f"Big news {i} from hubspot today." + pad, author=f"Hub Author {i}", comments=50) for i in range(5)]
    _kw = ["vercel", "webflow", "anthropic", "claude", "sanity"]
    oth = [_mk(f"Take {i} on {_kw[i % 5]} this week." + pad, author=f"Other Author {i}", comments=15) for i in range(10)]
    Tc = {"tier_a": ["vercel", "hubspot", "webflow", "anthropic"], "tier_b": ["claude", "sanity"],
          "tier_c": ["cms"], "target_company_slugs": []}

    def _nh(rr):
        return sum(1 for _, _, b in rr if b["cluster"] == "hubspot")

    rc = rank_engagement_posts(hub + oth, [], [], Tc, top_n=10, now=_now)
    assert len(rc) == 10 and _nh(rc) <= 2, f"FAILED: cluster cap, hubspot={_nh(rc)}"
    roff = rank_engagement_posts(hub + oth, [], [], Tc, top_n=10, now=_now, max_per_cluster=None, min_score=0)
    assert _nh(roff) == 5, f"FAILED: None should disable cluster cap ({_nh(roff)})"
    print(f"  ✓ PASS: cluster cap limits a 5-author HubSpot burst to {_nh(rc)} of 10; None disables ({_nh(roff)})")
    fb = rank_engagement_posts(hub + oth[:3], [], [], Tc, top_n=8, now=_now, fill_back=True)
    hard = rank_engagement_posts(hub + oth[:3], [], [], Tc, top_n=8, now=_now)
    assert _nh(hard) == 2 and len(hard) == 5, f"FAILED: hard cluster cap {len(hard)} {_nh(hard)}"
    assert len(fb) == 8 and _nh(fb) == 5 and _nh(fb[:5]) <= 2, f"FAILED: cluster fill-back {len(fb)} {_nh(fb)}"
    print("  ✓ PASS: cluster fill-back returns deferred posts after capped ones when few other-cluster posts exist")
    assert _cluster_key(["NextJS"]) == _cluster_key(["next.js"]) == "next.js"
    assert _cluster_key(["AB testing"]) == _cluster_key(["a/b testing"]) == "a/b testing"
    assert score_post_engagement(_mk("Shipping nextjs apps." + pad), None, 0.0, False, dict(T, tier_c=["nextjs"]), _now)[1]["cluster"] == "next.js"
    print("  ✓ PASS: alias spellings share one cluster; breakdown carries cluster")
    vpage = _mk("Vercel ships things." + pad, author="Vercel", atype="company", comments=60)
    vperson = _mk("Loving vercel this week." + pad, author="Guillermo R", comments=61)
    assert score_post_engagement(vpage, None, 0.0, False, T, _now)[1]["cluster"] == score_post_engagement(vperson, None, 0.0, False, T, _now)[1]["cluster"] == "vercel"
    print("  ✓ PASS: company page and person posts about one company share a cluster")
    mixed = (
        [_mk(f"Page {i} on hubspot news." + pad, author=f"HubPage {i}", atype="company", comments=50 + i) for i in range(4)]
        + [_mk(f"Pat post {i} about hubspot." + pad, author="Prolific Pat", comments=45 + i) for i in range(3)]
        + [_mk(f"Vercel person take {i}." + pad, author=f"V Person {i}", comments=40 + i) for i in range(4)]
        + [_mk(f"Claude person take {i} on claude code." + pad, author=f"C Person {i}", comments=30 + i) for i in range(6)]
        + [_mk(f"Claude page take {i} on claude code." + pad, author=f"CPage {i}", atype="company", comments=20 + i) for i in range(4)]
    )
    mr = rank_engagement_posts(mixed, [], [], Tc, top_n=6, now=_now)
    cl: dict = {}
    au: dict = {}
    for _, p, b in mr:
        cl[b["cluster"]] = cl.get(b["cluster"], 0) + 1
        au[p.author_name] = au.get(p.author_name, 0) + 1
    assert len(mr) == 6 and max(cl.values()) <= 2 and max(au.values()) <= 2 and _npages(mr) <= 3, f"FAILED: combined caps {cl} {au} {_npages(mr)}"
    print(f"  ✓ PASS: cluster, author and company-page caps hold together ({cl}, pages={_npages(mr)})")

    qp = _mk("Notes on vercel deploys." + pad, author="Queued Quinn")
    assert rank_engagement_posts([qp], [], [], T, now=_now, min_score=0)
    assert rank_engagement_posts([qp], [], [qp.post_id], T, now=_now) == []
    print("  ✓ PASS: already-queued post excluded")

    old = _mk("Notes on vercel deploys." + pad, age_days=8, author="Old Olive")
    assert rank_engagement_posts([old], [], [], T, now=_now) == []
    print("  ✓ PASS: post older than 7 days excluded")

    # Score floor: bracket the floor around a post's actual score so the test does not depend on constants.
    fp = _mk("Notes on vercel deploys and what we shipped." + pad, author="Floor Fern", comments=40)
    fs = rank_engagement_posts([fp], [], [], T, now=_now, min_score=0)[0][0]
    assert rank_engagement_posts([fp], [], [], T, now=_now, min_score=fs + 0.01) == [], "FAILED: post below floor kept"
    assert len(rank_engagement_posts([fp], [], [], T, now=_now, min_score=fs - 0.01)) == 1, "FAILED: post above floor dropped"
    assert len(rank_engagement_posts([fp], [], [], T, now=_now, min_score=0)) == 1, "FAILED: floor 0 must disable"
    assert rank_engagement_posts([fp], [], [], T, now=_now, min_score=fs + 0.01, fill_back=True) == [], "FAILED: fill-back resurrected a sub-floor post"
    print("  ✓ PASS: score floor excludes sub-floor posts, 0 disables, fill-back never resurrects them")

    # Hard caps by default: deferred posts are not re-added unless fill_back=True.
    hub2 = [_mk(f"News {i} from hubspot today." + pad, author=f"Hub Two {i}", comments=50) for i in range(4)]
    Th = {"tier_a": ["hubspot"], "tier_b": [], "tier_c": [], "target_company_slugs": []}
    hard2 = rank_engagement_posts(hub2, [], [], Th, top_n=10, now=_now, min_score=0)
    assert len(hard2) == 2, f"FAILED: hard cluster cap returned {len(hard2)}"
    soft2 = rank_engagement_posts(hub2, [], [], Th, top_n=10, now=_now, min_score=0, fill_back=True)
    assert len(soft2) == 4, f"FAILED: fill_back=True returned {len(soft2)}"
    print("  ✓ PASS: caps are hard by default (2 of 4 same-cluster posts), fill_back=True restores them")

    # Cluster key priority: platform term > tier-A company > role title > tier C.
    Tp = {"tier_a": ["microsoft", "vercel"], "tier_b": ["hubspot", "senior web developer"], "tier_c": ["cms"],
          "platform_terms": ["hubspot"], "target_company_slugs": []}
    def _cl(text):
        rr = rank_engagement_posts([_mk(text + pad, author="Cluster Cass")], [], [], Tp, now=_now, min_score=0)
        return rr[0][2]["cluster"]
    assert _cl("HubSpot and Microsoft announce a partnership.") == "hubspot", "FAILED: platform term must outrank company"
    Tn = dict(Tp); Tn["platform_terms"] = []
    rn = rank_engagement_posts([_mk("HubSpot and Microsoft announce a partnership." + pad, author="Cluster Cass")], [], [], Tn, now=_now, min_score=0)
    assert rn[0][2]["cluster"] == "microsoft", "FAILED: without platform_terms the company wins"
    assert _cl("A senior web developer joins Vercel this week.") == "vercel", "FAILED: company must outrank role title"
    assert _cl("Hiring a senior web developer for a cms migration.") == "senior web developer", "FAILED: role title must outrank tier C"
    print("  ✓ PASS: cluster key priority is platform term, tier-A company, role title, tier C")

    # -----------------------------------------------------------------
    # Suite 6: derive_targets_from_core_cv (temporary invented files)
    # -----------------------------------------------------------------
    print("\n[Suite 6] derive_targets_from_core_cv...")
    import tempfile

    _cv = """# Test Person
**Growth Wizard | Site Builder**

## Capabilities & Technical Stack
- **Web Engineering:** Next.js, React, JS, Node.js, design systems
- **Platforms & CMS:** Sanity, Contentful
- **Growth & Measurement:** CRO, Segment, GA4
- **Quality & Delivery:** Playwright, CI/CD, Lighthouse

### **Chief Widget Officer**, Acme
### **Senior Gadget Developer (Freelance)**, Beta
### **Chief Widget Officer**, Gamma
"""
    _pl = """| Company | Role | Status | Score |
|---|---|---:|---:|
| Zorbex | Widget Lead | Networking | 90 |
| Quillon (formerly Oldquill) | Dev | Applied | 80 |
| Deadco Inc | Dev | Rejected | 70 |
| Gonecorp | Dev | Withdrawn | 60 |
| Shutco | Dev | Closed | 50 |
| Oldco | Dev | Archived | 40 |
"""
    with tempfile.TemporaryDirectory() as _d:
        _cvp, _plp = Path(_d, "cv.md"), Path(_d, "pipe.md")
        _cvp.write_text(_cv, encoding="utf-8")
        _plp.write_text(_pl, encoding="utf-8")
        D = derive_targets_from_core_cv(str(_cvp), str(_plp))
        assert D["role_titles"] == ["Growth Wizard", "Site Builder", "Chief Widget Officer", "Senior Gadget Developer"], D["role_titles"]
        assert "chief widget officer" in D["tier_b"] and "sanity" in D["tier_b"] and "segment" in D["tier_b"], D["tier_b"]
        print("  ✓ PASS: headline and experience titles parsed, deduplicated, freelance tag stripped")
        assert set(D) >= {"tier_a", "tier_b", "tier_c", "target_company_slugs", "role_titles"}
        assert {"cro", "ga4", "playwright", "lighthouse", "next.js", "design systems", "hiring"} <= set(D["tier_c"]), D["tier_c"]
        for bad in ("react", "js", "node.js", "ci/cd"):
            assert bad not in D["tier_c"] and bad not in D["tier_b"], f"FAILED: stoplisted {bad} leaked"
        print("  ✓ PASS: stoplisted generic terms never appear in tier_b or tier_c")
        assert D["tier_a"] == ["zorbex", "quillon", "oldquill"], D["tier_a"]
        for dead in ("deadco", "gonecorp", "shutco", "oldco"):
            assert dead not in D["tier_a"] and dead not in D["target_company_slugs"]
        assert "zorbex" in D["target_company_slugs"]
        print("  ✓ PASS: active companies in tier_a, terminal-status companies excluded")

        _fb = {k: v for k, v in DEFAULT_ENGAGEMENT_TARGETS.items()}
        for _bad in ("/nonexistent/cv.md", str(Path(_d))):  # missing file, directory (unreadable)
            F = derive_targets_from_core_cv(_bad, _bad)
            assert all(F[k] == _fb[k] for k in _fb) and F["role_titles"] == [], "FAILED: fallback"
        _junk = Path(_d, "junk.md")
        _junk.write_bytes(b"\xff\xfe not markdown \x00 | | |")
        F = derive_targets_from_core_cv(str(_junk), str(_junk))
        assert all(F[k] == _fb[k] for k in _fb), "FAILED: malformed fallback"
        assert not any("forward deployed" in t or "fde" == t for t in F["tier_b"] + F["tier_c"])
        print("  ✓ PASS: missing, unreadable and malformed files fall back without raising (FDE-free)")

        os.environ["JSB_CORE_CV"], os.environ["JSB_PIPELINE"] = str(_cvp), str(_plp)
        try:
            E = derive_targets_from_core_cv()
            assert E == D, "FAILED: env override not honored"
            assert load_engagement_targets("/nonexistent/x.json")["tier_a"] == ["zorbex", "quillon", "oldquill"]
        finally:
            os.environ.pop("JSB_CORE_CV", None)
            os.environ.pop("JSB_PIPELINE", None)
        print("  ✓ PASS: JSB_CORE_CV / JSB_PIPELINE env override works and feeds load_engagement_targets")

    # -----------------------------------------------------------------
    # Suite 7: Real-name leak guard — invented company names in the
    # pipeline_evals fixture (Suite 3) must never coincide with a real
    # company from the job-search pipeline or CV. Bit us twice before:
    # two prior private employer names each leaked in as "invented"
    # test data and had to be caught and renamed by hand.
    # -----------------------------------------------------------------
    print("\n[Suite 7] Real-name leak guard...")
    try:
        _harness_src = Path(__file__).read_text(encoding="utf-8")
        _start = _harness_src.index("    pipeline_evals = [")
        _end = _harness_src.index("\n    for targets, headline, min_score, desc in pipeline_evals:")
        _harness_src = _harness_src[_start:_end]

        _real_names: set = set()
        try:
            for _line in Path(os.path.expanduser(_DEFAULT_PIPELINE_PATH)).read_text(encoding="utf-8").splitlines():
                _m = re.match(r"\|\s*([^|]+?)\s*\|", _line)
                if _m and _m.group(1) not in ("Company", "---"):
                    _real_names.add(_m.group(1).split(" / ")[0].split(" (")[0].strip())
        except OSError:
            pass
        try:
            for _line in Path(os.path.expanduser(_DEFAULT_CORE_CV_PATH)).read_text(encoding="utf-8").splitlines():
                _m = re.match(r"###\s+\*\*.+\*\*,\s*(.+)$", _line.strip())
                if _m:
                    _real_names.add(_m.group(1).strip())
        except OSError:
            pass

        _GENERIC = {"acme", "beta", "gamma"}  # short generic words too common to flag reliably
        _leaked = sorted(
            n for n in _real_names
            if len(n) > 2 and n.lower() not in _GENERIC
            and re.search(r"\b" + re.escape(n) + r"\b", _harness_src, re.IGNORECASE)
        )
        assert not _leaked, f"FAILED: real name(s) leaked into test fixtures: {_leaked}"
        print(f"  ✓ PASS: none of {len(_real_names)} real pipeline/CV names found in fixture data")
    except FileNotFoundError:
        print("  - SKIPPED: pipeline/CV files not found (not running on Rodney's machine)")

    print("\n" + "=" * 80)
    print("ALL TEST SUITES PASSED! Node 2c Entity Matcher is fully verified and ready.")
    print("=" * 80)
