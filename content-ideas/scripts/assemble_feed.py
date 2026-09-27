#!/usr/bin/env python3
"""assemble_feed.py — deterministic Posts-tab builder.

Turns `scrape.py` profile-mode output (`{"results": {platform: {handle: [post]}},
"errors": [...]}`) into the `meta` + `posts` half of `feed-data.json` with **zero
model involvement**. Every scraped post becomes a feed post — no engagement gate,
no cherry-picking — so the feed carries the full scrape, not the handful a model
chose to retype. The model is then responsible for the **Ideas** tab only.

Every field the model used to hand-write is already computed upstream by
`scrape.py` / `analyze.py`:
  - score / relevance / baseline / outlier  → analyze.py
  - performance / performanceDirection       → derived from baseline here
  - zScore / why                             → recomputed per-account here
  - timestamp / sortValue / engagement / handle / platform / url → straight
    from the scraped post.
The text summary is a deterministic clip of the post text.

Usage:
    # scrape.py output on stdin -> feed-data.json fragment on stdout
    python3 scrape.py '{...}' --pillars '...' | python3 assemble_feed.py > feed-data.json

    # explicit file in, merge into an existing feed-data.json (preserves ideas)
    python3 assemble_feed.py scrape.json --out research/2026-06-18/feed-data.json

    # record the recency window in meta
    python3 assemble_feed.py scrape.json --days 7 --since 2026-06-11 --run-date 2026-06-18

Output: a JSON object `{"meta": {...}, "posts": [...], "ideas": [...]}`. `ideas`
is preserved from an existing `--out` file if present, else an empty list for the
model to fill.
"""

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Match analyze.py so the deterministic outlier flag here agrees with the scrape.
OUTLIER_THRESHOLD = 2.0  # z-score units above the account mean
TEXT_CLIP = 280          # max chars for the card summary


def engagement_total(engagement):
    """Sum the numeric engagement metrics (mirrors pipeline.total_engagement)."""
    if not isinstance(engagement, dict):
        return 0
    return sum(v for v in engagement.values() if isinstance(v, (int, float)))


def clip_text(text, limit=TEXT_CLIP):
    """Collapse whitespace and trim to ~1-3 sentences without cutting mid-word."""
    if not text:
        return ""
    collapsed = re.sub(r"\s+", " ", str(text)).strip()
    if len(collapsed) <= limit:
        return collapsed
    window = collapsed[: limit + 1]
    # Prefer a sentence boundary; fall back to the last word boundary.
    cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    if cut >= limit * 0.5:
        return window[: cut + 1].strip()
    cut = window.rfind(" ")
    if cut <= 0:
        cut = limit
    return collapsed[:cut].rstrip() + "…"


def _post_score(post):
    """The engagement score analyze.py set, or a fallback total if absent."""
    score = post.get("score")
    if isinstance(score, (int, float)):
        return score
    return engagement_total(post.get("engagement"))


def account_stats(posts):
    """Mean and population std of the engagement scores for one account."""
    scores = [_post_score(p) for p in posts]
    if not scores:
        return 0.0, 0.0
    mean = sum(scores) / len(scores)
    if len(scores) < 2:
        return mean, 0.0
    var = sum((s - mean) ** 2 for s in scores) / len(scores)
    return mean, math.sqrt(var)


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def build_post(post, platform, handle, idx, mean, std):
    """Map one scraped post to the feed `posts[]` shape the template consumes."""
    handle = str(handle).lstrip("@")
    author = post.get("author") or handle
    engagement = post.get("engagement") if isinstance(post.get("engagement"), dict) else {}
    total = engagement_total(engagement)
    score = _post_score(post)

    feed_post = {
        "id": f"{platform}_{_slug(handle)}_{idx}",
        "text": clip_text(post.get("text")),
        "url": post.get("url") or "",
        "handle": handle,
        "displayName": author,
        "platform": platform,
        "engagement": dict(engagement, total=total),
        "sortValue": total,
        "relevance": post.get("relevance"),
    }

    timestamp = post.get("date")
    if timestamp:
        feed_post["timestamp"] = timestamp

    # baseline = Nx the account mean -> performance string + direction.
    baseline = round(score / mean, 1) if mean > 0 else 0
    if baseline > 0:
        pct = round((baseline - 1) * 100)
        feed_post["performance"] = f"{'+' if pct >= 0 else ''}{pct}% vs baseline"
        if pct > 0:
            feed_post["performanceDirection"] = "up"

    # Statistical outlier (2σ): the discovered-niche signal. Carries z + a why.
    z = (score - mean) / std if std > 0 else 0.0
    is_outlier = bool(post.get("outlier")) or (std > 0 and z > OUTLIER_THRESHOLD)
    if is_outlier:
        feed_post["zScore"] = round(z, 1)
        baseline_txt = f"{baseline}×" if baseline else "well above"
        feed_post["why"] = f"{baseline_txt} the account's typical engagement (z {z:.1f})"

    return feed_post, is_outlier


def assemble(scrape, run_date=None, recency=None):
    """Build {meta, posts} from scrape.py profile-mode output."""
    results = scrape.get("results") or {}
    posts = []
    outlier_count = 0
    tracked_accounts = 0
    platforms_with_posts = []

    for platform, handles in results.items():
        if not isinstance(handles, dict):
            continue
        platform_has_posts = False
        for handle, account_posts in handles.items():
            tracked_accounts += 1
            account_posts = account_posts or []
            mean, std = account_stats(account_posts)
            for idx, post in enumerate(account_posts):
                feed_post, is_outlier = build_post(post, platform, handle, idx, mean, std)
                posts.append(feed_post)
                outlier_count += int(is_outlier)
                platform_has_posts = True
        if platform_has_posts:
            platforms_with_posts.append(platform)

    meta = {
        "runDate": run_date or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": platforms_with_posts,
        "platformCount": len(platforms_with_posts),
        "postCount": len(posts),
        "outlierCount": outlier_count,
        "trackedAccountCount": tracked_accounts,
    }
    if recency:
        meta["recencyWindow"] = recency

    return {"meta": meta, "posts": posts}


def _recency_window(days, since):
    if not days:
        return None
    if since:
        return f"since {since} (last {days}d cap)"
    return f"last {days} days"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Deterministically build the Posts tab of feed-data.json")
    parser.add_argument("scrape", nargs="?", type=Path,
                        help="scrape.py JSON output (default: stdin)")
    parser.add_argument("--out", type=Path, default=None,
                        help="Write feed-data.json here, preserving any existing ideas (default: stdout)")
    parser.add_argument("--run-date", default=None, help="meta.runDate (default: now, ISO 8601 Z)")
    parser.add_argument("--days", type=int, default=None, help="Recency window size, for meta.recencyWindow")
    parser.add_argument("--since", default=None, help="Recency cursor, for meta.recencyWindow")
    args = parser.parse_args(argv)

    raw = args.scrape.read_text() if args.scrape else sys.stdin.read()
    try:
        scrape = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: input is not valid JSON: {e}", file=sys.stderr)
        return 1
    if scrape.get("error"):
        print(f"Error: scrape failed: {scrape['error']}", file=sys.stderr)
        return 1

    feed = assemble(scrape, run_date=args.run_date, recency=_recency_window(args.days, args.since))

    # Preserve a model-written Ideas tab when merging into an existing file.
    ideas = []
    if args.out and args.out.exists():
        try:
            existing = json.loads(args.out.read_text())
            ideas = existing.get("ideas", []) or []
        except (json.JSONDecodeError, OSError):
            pass
    feed["ideas"] = ideas

    output = json.dumps(feed, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n")
        print(f"[assemble_feed] {feed['meta']['postCount']} posts "
              f"({feed['meta']['outlierCount']} outliers) -> {args.out}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
