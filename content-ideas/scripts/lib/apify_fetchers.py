"""Apify backend: per-platform profile fetchers.

Each `fetch_profile(handle, token)` runs the platform's Apify actor for one
handle and normalizes the dataset items into the engine's post contract, so
scoring/relevance/analyze/feed all consume one uniform shape:

    {text, url, author, date:"YYYY-MM-DD"|None, platform, engagement{…}}

Engagement keys per platform are exactly the ones lib/scoring.py reads.

Tracked platforms: X, YouTube, LinkedIn. (Instagram + TikTok were verified live
2026-06-18 but deferred — see Backlog B4 in the build plan for restore snippets.)

v1 scope: profile fetching for the daily feed. Single-post (URL mode), comments,
and transcripts are not implemented on this backend yet and degrade to None/[]
so the feed never breaks. Field mappings verified against live actor output
2026-06-18 (apidojo/tweet-scraper, streamers/youtube-scraper,
harvestapi/linkedin-profile-posts).
"""

from . import apify, dates

# Recent posts pulled per handle. Each handle is one actor run (v1), so this also
# caps per-run cost; the pipeline still enforces the recency window afterwards.
DEFAULT_LIMIT = 15

X_ACTOR = "apidojo/tweet-scraper"
YT_ACTOR = "streamers/youtube-scraper"
LI_ACTOR = "harvestapi/linkedin-profile-posts"


def _iso_date(value):
    """An ISO8601 string ('2026-06-18T…') → 'YYYY-MM-DD', or None."""
    return (value or "")[:10] or None


def _int(value):
    """Coerce an actor count to int, treating None/garbage as 0."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _items(raw):
    """Drop non-dicts and actor sentinels (e.g. {'noResults': true})."""
    return [i for i in raw if isinstance(i, dict) and not i.get("noResults") and not i.get("error")]


# ── X / Twitter ──────────────────────────────────────────────────────────────
def _x_normalize(item):
    author = (item.get("author") or {}).get("userName") or ""
    return {
        "text": item.get("fullText") or item.get("text") or "",
        "url": item.get("url") or "",
        "author": author,
        "date": dates.parse_x_date(item.get("createdAt")),
        "platform": "x",
        "engagement": {
            "likes": _int(item.get("likeCount")),
            "reposts": _int(item.get("retweetCount")),
            "replies": _int(item.get("replyCount")),
            "quotes": _int(item.get("quoteCount")),
            "bookmarks": _int(item.get("bookmarkCount")),
            "views": _int(item.get("viewCount")),
        },
    }


def x_fetch_profile(handle, token, limit=DEFAULT_LIMIT):
    raw = apify.run_actor_sync(X_ACTOR, {
        "startUrls": [f"https://twitter.com/{handle.lstrip('@')}"],
        "maxItems": limit,
        "sort": "Latest",
    }, token)
    return [_x_normalize(i) for i in _items(raw)]


# ── YouTube ──────────────────────────────────────────────────────────────────
def _yt_channel_url(handle):
    """Build a channel /videos URL from a handle, @handle, or full URL."""
    h = handle.strip()
    if h.startswith("http"):
        return h.rstrip("/") + ("" if h.rstrip("/").endswith("/videos") else "/videos")
    return f"https://www.youtube.com/@{h.lstrip('@')}/videos"


def _yt_normalize(item, handle):
    return {
        "text": item.get("title") or "",
        "url": item.get("url") or "",
        "author": item.get("channelName") or handle,
        "date": _iso_date(item.get("date")),
        "platform": "youtube",
        "engagement": {
            "views": _int(item.get("viewCount")),
            "likes": _int(item.get("likes")),
            "comments": _int(item.get("commentsCount")),
        },
        "duration": item.get("duration"),
        "description": item.get("text") or "",
    }


def yt_fetch_profile(handle, token, limit=DEFAULT_LIMIT):
    raw = apify.run_actor_sync(YT_ACTOR, {
        "startUrls": [{"url": _yt_channel_url(handle)}],
        "maxResults": limit,
        "maxResultsShorts": 0,
        "maxResultStreams": 0,
    }, token)
    return [_yt_normalize(i, handle) for i in _items(raw)]


# ── LinkedIn ─────────────────────────────────────────────────────────────────
def _li_target_url(handle):
    """Build a LinkedIn target URL from a handle, `company/<slug>`, or full URL."""
    h = handle.strip()
    if h.startswith("http"):
        return h
    if h.startswith("company/"):
        return f"https://www.linkedin.com/{h.rstrip('/')}/"
    return f"https://www.linkedin.com/in/{h.lstrip('@')}/"


def _li_normalize(item, handle):
    author = item.get("author") or {}
    posted = item.get("postedAt") or {}
    eng = item.get("engagement") or {}
    return {
        "text": item.get("content") or "",
        "url": item.get("linkedinUrl") or "",
        "author": author.get("name") or author.get("publicIdentifier") or handle,
        "date": _iso_date(posted.get("date")),
        "platform": "linkedin",
        "engagement": {
            "likes": _int(eng.get("likes")),       # total reactions
            "comments": _int(eng.get("comments")),
            "shares": _int(eng.get("shares")),
        },
    }


def li_fetch_profile(handle, token, limit=DEFAULT_LIMIT):
    raw = apify.run_actor_sync(LI_ACTOR, {
        "targetUrls": [_li_target_url(handle)],
        "maxPosts": limit,
        "maxReactions": 0,
        "maxComments": 0,
    }, token)
    return [_li_normalize(i, handle) for i in _items(raw)]


# Registry consumed by lib/platforms.py when the Apify backend is active.
PROFILE_FETCHERS = {
    "x": x_fetch_profile,
    "youtube": yt_fetch_profile,
    "linkedin": li_fetch_profile,
}
