---
name: linkedin-scout
description: Automated LinkedIn discovery of people, job postings, companies, feed posts, and DM threads via passive CDP Voyager GraphQL sniffing, Selectolax DOM extraction, RapidFuzz scoring, and DuckDB persistence. Use for finding 1st/2nd degree connections, inspecting a job posting, researching a hiring company, scoring role/company fit, or drafting engagement (comments, reactions, reposts, posts, messages) for human review.
---

# LinkedIn Scout (`linkedin-scout`)

High-performance, anti-bot-resilient LinkedIn network discovery and contact prospecting engine. Combines passive Chrome DevTools Protocol (CDP) network interception, sub-5ms C-engine DOM parsing (`selectolax`), Levenshtein entity resolution (`rapidfuzz`), and embedded relational storage (`duckdb`).

Interacts with system Chrome via the `capt-chrome-agent` substrate and its persistent authenticated profile manager. `capt-chrome-agent` is a separate skill and is **not included in this repo**; install it next to this skill or set `CAPT_CHROME_AGENT_DIR` (see [Prerequisites](#prerequisites--browser-integration)).

All paths below are relative to this skill's folder.

---

## Capabilities & Architecture

```
┌────────────────────────────────────────────────────────┐
│ Layer 2: Domain Engine (linkedin-scout)                │
│ - Schemas: Pydantic v2 (LinkedInContact, JobPosting,   │
│   Company, Post, DMThread, EngagementAction,           │
│   SearchCluster)                                       │
│ - Extraction: Passive Voyager GraphQL + Selectolax DOM │
│ - Entity Matcher: RapidFuzz C++ role/company scoring   │
│ - Database: DuckDB network persistence & deduplication │
│ - CLI: Unified entrypoint (`cli.py`)                   │
└───────────────────────────┬────────────────────────────┘
                            │ drives / attaches via CDP
                            ▼
┌────────────────────────────────────────────────────────┐
│ Layer 1: Substrate (capt-chrome-agent, separate skill) │
│ - Persistent Profiles (~/.config/chrome-agent/profiles)│
│ - Chrome CDP WebSocket Server (port 9222/9224)         │
│ - Anti-bot safe navigation                             │
└────────────────────────────────────────────────────────┘
```

1. **Passive Voyager GraphQL Interception (`cdp_interceptor.py`)**:
   - Subscribes to CDP `Network.responseReceived` matching `/voyager/api/graphql`.
   - Reads response bodies directly from Chrome internal memory buffer via `Network.getResponseBody`.
   - Generates **zero outbound network requests**, bypassing Cloudflare and Akamai bot-detection heuristics.
   - Feed posts use a separate, narrower capture (`capture_voyager_feed_traffic`) scoped to `voyagerFeedDashOrganizationalPageUpdates` (company Posts tab) and `voyagerFeedDashProfileUpdates` (person Activity tab) -- both carry real post IDs, canonical permalinks, and engagement counts. **The plain home feed (`/feed/`) is out of scope**: LinkedIn server-renders it with no separate data fetch and no post URN left in the DOM, so `discover-feed` without `--company`/`--person` falls back to unreliable DOM parsing. Always scope with `--company` or `--person`.

2. **Sub-5ms Selectolax DOM Fallback (`dom_parser.py`)**:
   - Parses modern LinkedIn search card markup (`div[role="listitem"]` and classic containers) in **~1.2 ms/page**.
   - Extracts name, degree (`1st`, `2nd`, `3rd+`), canonical profile URL, location, and mutual connection samples.

3. **C++ RapidFuzz Entity Resolution (`entity_matcher.py`)**:
   - Composite scoring: 0.6 * role + 0.4 * company.
   - Technical & sales acronym expansion (`SWE`, `SDE`, `EM`, `AE`, `SE`, `PM`).
   - Guarded against past-employer false positives (`ex-`, `former`, `previously`).

4. **Embedded DuckDB Storage (`pipeline_db.py`)**:
   - Default database: `~/.config/chrome-agent/job_search_network.duckdb`.
   - Six tables, one per first-class object: `contacts` (PK `urn_id`), `jobs` (PK `job_id`), `companies` (PK `company_id`), `posts` (PK `post_id`), `dm_threads` (PK `thread_id`), `engagement_actions` (PK `action_id`).
   - Automatic cross-namespace deduplication on canonical `profile_url` / `job_url` / `company_url` / `post_url`.
   - Two-way sync with Markdown network dossiers (`_shared_facts/NETWORK.md`).

5. **Engagement is discovery-and-drafting only -- never execution.** `discover-feed`/`inspect-thread` are read-only (same passive/DOM extraction as every other object here). `queue-engagement` only ever writes `status="drafted"`; `review-engagement` only accepts `approved`/`rejected`. **No command anywhere in this CLI posts, likes, comments, reposts, or sends a message** -- nothing in the codebase transitions a record to `executed`. Publishing stays 100% manual: the human reviews the queue and performs the action themselves, in their own browser session. This mirrors `job-search-operator`'s outreach rule (draft only, never send) and exists because LinkedIn's User Agreement explicitly prohibits bot-driven posting/liking/commenting/messaging.

6. **Strategy Reference: Algorithm Recency & Feed Dynamics**:
   - For post selection heuristics (target 4 to 48 hours), initial velocity windows ("Golden Hour"), comment distribution loops, and cannibalization guardrails, see [`references/algorithm-recency.md`](references/algorithm-recency.md).

---

## CLI Command Reference

The unified CLI is `scripts/cli.py`:

```bash
# Alias for quick access
alias linkedin-scout="python3 /path/to/linkedin-scout/scripts/cli.py"
```

### 1. Live Contact Discovery (`discover`)
Navigates active Chrome to canned search queries, intercepts live Voyager GraphQL / DOM cards, scores matches, and saves directly to DuckDB:

```bash
# Discover 1st & 2nd degree connections for target company & roles:
python3 scripts/cli.py discover \
  --company "Umbra" \
  --roles "Engineering Manager, Web,Head of Web Engineering" \
  --network F,S

# Discover with custom search keywords:
python3 scripts/cli.py discover \
  --keywords "Zephyria" \
  --roles "Solo Marketing Engineer,Agent Infrastructure Lead" \
  --network F,S

# Direct URL capture:
python3 scripts/cli.py discover \
  --url "https://www.linkedin.com/search/results/people/?keywords=Verdant&network=%5B%22F%22%2C%22S%22%5D" \
  --roles "Marketing Engineer,Senior Web Developer"
```

### 2. Detailed Profile Inspection (`inspect`)
Inspect an individual LinkedIn profile (local equivalent of `linkedin-cli`'s `person fetch`), extracting complete career history (work experience, education, skills, about summary, mutual bridges), computing Warmth Rubric degrees (1–7), and persisting enriched dossiers to DuckDB:

```bash
# Inspect a profile by handle or URL:
python3 scripts/cli.py inspect tony-stark-eng --all

# Inspect with target roles for RapidFuzz role fit scoring & warmth tiering:
python3 scripts/cli.py inspect "https://www.linkedin.com/in/tony-stark-eng" \
  --roles "Head of Growth Engineering,Site Engineer" \
  --experience

# Output structured JSON for agent pipelines:
python3 scripts/cli.py inspect tony-stark-eng --json

# Read previously saved profile from local DuckDB without browser launch:
python3 scripts/cli.py inspect tony-stark-eng --cached --all
```

### 3. Query Stored Network Contacts (`list`)
Filter and inspect contacts stored in DuckDB:

```bash
# List all contacts at a company:
python3 scripts/cli.py list --company "Verdant" --limit 15

# Filter by minimum role match score:
python3 scripts/cli.py list --company "Umbra" --min-score 50.0
```

### 4. Sync Markdown Network Dossiers (`sync-network`)
Ingest or refresh contacts from `_shared_facts/NETWORK.md` into DuckDB:

```bash
python3 scripts/cli.py sync-network
```

### 5. Fast Parse Offline HTML Dumps (`parse-html`)
Parse raw saved LinkedIn search HTML offline without a running browser:

```bash
python3 scripts/cli.py parse-html /tmp/search_dump.html \
  --company "Hexlight" \
  --roles "Senior Marketing Engineer,Web Engineer" \
  --save
```

### 6. Run Automated Evaluation Suite (`eval`)
Benchmark parsing speeds and evaluate matching accuracy across active pipeline roles:

```bash
python3 scripts/cli.py eval
```

### 7. Live Job Search Discovery (`discover-jobs`)
Navigates active Chrome to a job search results page, DOM-parses posting cards, scores role/company fit, and saves to DuckDB:

```bash
# Discover open roles at a target company:
python3 scripts/cli.py discover-jobs \
  --company "Verdant" \
  --roles "Principal Marketing Engineer,Head of Growth Engineering"

# Discover by keywords + location:
python3 scripts/cli.py discover-jobs \
  --keywords "Marketing Engineer" --location "Remote"
```

### 8. Detailed Job Posting Inspection (`inspect-job`)
Inspect a single job posting (local equivalent of `linkedin-cli`'s `jobs fetch`), extracting description, seniority, employment type, salary range, and applicant count, and computing role/company match scores:

```bash
# Inspect by job ID or full URL:
python3 scripts/cli.py inspect-job 4123456789 \
  --roles "Senior Web Developer" --company "Verdant"

# Output structured JSON for agent pipelines:
python3 scripts/cli.py inspect-job 4123456789 --json

# Read previously saved posting from local DuckDB without browser launch:
python3 scripts/cli.py inspect-job 4123456789 --cached
```

### 9. Detailed Company Inspection (`inspect-company`)
Inspect a company's LinkedIn About page (local equivalent of `linkedin-cli`'s `company fetch`), extracting industry, size, HQ, founding year, and description:

```bash
# Inspect by slug or full URL:
python3 scripts/cli.py inspect-company umbra

# Read previously saved company from local DuckDB without browser launch:
python3 scripts/cli.py inspect-company umbra --cached
```

### 10. Query Stored Job Postings (`list-jobs`)
Filter job postings stored in DuckDB:

```bash
# List open roles at a company above a role-fit threshold:
python3 scripts/cli.py list-jobs --company "Umbra" --min-score 50.0

# Filter by pipeline stage:
python3 scripts/cli.py list-jobs --status applied
```

### 11. Query Stored Companies (`list-companies`)
Filter companies stored in DuckDB:

```bash
python3 scripts/cli.py list-companies --industry "Artificial Intelligence"
```

### 12. Live Feed Discovery (`discover-feed`)
Read-only: scoped to a company's Posts tab or a person's Activity tab, captures real posts via passive Voyager GraphQL interception (real post IDs, canonical permalinks, engagement counts), DOM parsing as fallback only. Scores topic/author fit. Does not like, comment, or repost anything. Always pass `--company` or `--person` -- the bare home feed has no reliable extraction path (see Architecture note 1).

```bash
# Scope to a company's Posts tab, scored against target topics:
python3 scripts/cli.py discover-feed \
  --company "verdant" --topics "Marketing Engineering,Design Systems"

# Scope to a person's Activity tab:
python3 scripts/cli.py discover-feed --person "tony-stark-eng"
```

### 13. Detailed DM Thread Inspection (`inspect-thread`)
Read-only: reads an already-open conversation (messages the browser has already loaded). Does not send anything.

```bash
python3 scripts/cli.py inspect-thread \
  "https://www.linkedin.com/messaging/thread/<thread-id>/"

# Read previously saved thread from local DuckDB without browser launch:
python3 scripts/cli.py inspect-thread <thread-id> --cached
```

### 14. Query Stored Posts (`list-posts`)
```bash
python3 scripts/cli.py list-posts --author "Tony Stark" --min-score 50.0
```

### 15. Query Stored DM Threads (`list-threads`)
```bash
python3 scripts/cli.py list-threads --participant "Tony Stark"
```

### 16. Draft an Engagement Action (`queue-engagement`)
Records a rubric-scored draft for human review. Always writes `status="drafted"` -- this command cannot post, like, comment, repost, or send a message; it only saves text for you to act on yourself:

```bash
python3 scripts/cli.py queue-engagement \
  --target-type post --target-id 7123456789 \
  --action-type comment \
  --draft-content "Strong take on marketing engineering staffing at Verdant -- curious how you're balancing it against platform work." \
  --rubric-score 87.5 --rationale "WARM author, on-topic, live thread"
```

### 17. Review the Drafted Engagement Queue (`list-engagement`)
```bash
python3 scripts/cli.py list-engagement --status drafted --min-score 70.0
```

### 18. Approve or Reject a Drafted Action (`review-engagement`)
Records your decision only -- approving does not post it. Performing the comment/like/repost/message in your own browser remains a separate, manual step:

```bash
python3 scripts/cli.py review-engagement <action-id> --status approved
```

### 19. Passive Feed Listener (`listen-feed`)
Read-only and hands-off: you browse company Posts tabs and person Activity tabs in your own visible Chrome window; the command only listens (never navigates, clicks, or scrolls), re-checks for new linkedin.com tabs every 3 seconds, saves posts to DuckDB, and prints which of your connections now have post data. Works for company Posts tabs and person Activity tabs, not the home feed. Attaches to the instance running the `linkedin` profile (override with `--port`).

```bash
# Start the listener, then browse the profiles' activity pages yourself:
python3 scripts/cli.py listen-feed --seconds 180
```

### 20. Store a Pasted Post (`add-post`)
Builds a post from a URL you copied (must contain an activity id) plus its text and counts; idempotent by post ID. Author handle is taken from a `/posts/{handle}_` permalink when `--author-handle` is omitted.

```bash
python3 scripts/cli.py add-post \
  --url "https://www.linkedin.com/feed/update/urn:li:activity:7000000000000000000/" \
  --author "Tony Stark" --author-handle tony-stark-eng --text-file post.txt --likes 42 --comments 5
pbpaste | python3 scripts/cli.py add-post --url "<permalink>" --author "Tony Stark" --text -
```

### 21. Connections With Post Data (`list-connections --with-posts`)
Joins stored posts to stored connections by profile handle (person authors) and company slug (company authors): post count and average engagement per connection.

```bash
python3 scripts/cli.py list-connections --with-posts --limit 20 --json
```

---

## Prerequisites & Browser Integration

`linkedin-scout` uses the authenticated Chrome profile managed by `capt-chrome-agent`, a separate skill that is **not bundled in this repo**. The CLI looks for it in this order:

1. `$CAPT_CHROME_AGENT_DIR`
2. A sibling skill folder (`../capt-chrome-agent`)
3. `~/.agents/skills/capt-chrome-agent`

Below, `$CAPT_CHROME_AGENT_DIR` stands for wherever it lives:

1. **Check or Initialize Profile**:
   ```bash
   python3 "$CAPT_CHROME_AGENT_DIR"/scripts/profile_manager.py list
   ```
2. **One-Time Authentication**:
   If unauthenticated, run the interactive setup flow once:
   ```bash
   python3 "$CAPT_CHROME_AGENT_DIR"/scripts/profile_manager.py setup linkedin \
     --url "https://www.linkedin.com/login" \
     --check "feed"
   ```
   All future `discover` and `inspect` commands run automatically using this saved profile.

---

## Verification & Test Suite

Run the full end-to-end regression test suite:

```bash
python3 tests/test_linkedin_scout.py
```
*Target benchmark*: 11/11 tests passing in sub-5ms.

