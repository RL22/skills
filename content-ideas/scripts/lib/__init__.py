"""content-ideas scraper library.

Split into small, testable modules:

- apify          — Apify run-sync client (run an actor, return dataset items)
- apify_fetchers — per-platform profile fetchers (X, YouTube, LinkedIn) that
                   normalize actor output to the post contract
- log            — stderr progress (keeps stdout clean for JSON)
- dates          — date parsing/normalization helpers
- platforms      — selects the fetcher registries for the active backend
- scoring        — per-platform weighted engagement score
- relevance      — token-overlap relevance against content pillars
- analyze        — per-account baselines + outlier flags
- urls           — platform detection + handle extraction from a post URL
- env            — credential loading (env var > ~/.config/content/.env)
- pipeline       — orchestration (scrape_all, filter_since, fetch_urls)
"""
