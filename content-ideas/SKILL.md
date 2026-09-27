---
name: content-ideas
version: "2.4.0"
description: >
  Your For You page for content creators. Scrapes tracked competitors across
  social media platforms, scores what's performing, and turns it into actionable, differentiated content ideas backed
  by real engagement data. Use this whenever the user wants competitor/creator
  research, a content feed or "for you" page, trending-topic ideas in their
  niche, to see what's working on social, to track what creators are posting,
  or to generate video/post briefs from what's performing — even if they don't
  say "find ideas." First run walks through setup.
argument-hint: "[topic filter]"
user-invocable: true
allowed-tools: Bash, Read, Write, AskUserQuestion
metadata:
  requires:
    env:
      - APIFY_TOKEN
    bins:
      - python3
---

# content-ideas

Your For You page. Scrapes every platform where your tracked creators publish,
scores what's performing, and turns it into content ideas you can act on.
Designed to run daily — each run creates a dated feed under `$CONTENT_HOME/research/`.

The output is a single self-contained HTML page (two tabs: **Posts** — one
sortable, filterable feed merging tracked-account posts and discovered niche
outliers — and **Ideas**) that you can open in a browser, react to, and
keep. Reactions are captured for future personalization.

## Resolve the skill directory

Everything this skill runs lives under its own folder. The skill installs the
same way on Claude Code and Codex, so resolve `SKILL_DIR` against both plugin
caches (and a plain repo checkout) once, before anything else:

```bash
# 1) Codex plugin cache, or a repo cloned into ~/.codex/skills/ (latest wins on upgrade).
SKILL_DIR="$(ls -d "$HOME/.codex/plugins/cache/"*/content-ideas/*/skills/content-ideas/ "$HOME/.codex/skills/"*/skills/content-ideas/ 2>/dev/null | sort -V | tail -1)"
SKILL_DIR="${SKILL_DIR%/}"

# 2) Claude Code plugin cache.
if [ -z "$SKILL_DIR" ] || [ ! -f "$SKILL_DIR/scripts/scrape.py" ]; then
  CLAUDE_ROOT="$(ls -d "$HOME/.claude/plugins/cache/content-ideas/content-ideas/"*/ 2>/dev/null | sort -V | tail -1)"
  CLAUDE_ROOT="${CLAUDE_ROOT%/}"
  [ -n "$CLAUDE_ROOT" ] && [ -f "$CLAUDE_ROOT/skills/content-ideas/scripts/scrape.py" ] && SKILL_DIR="$CLAUDE_ROOT/skills/content-ideas"
fi

# 3) Plugin root passed by the host, or a repo checkout / local dev.
if [ -z "$SKILL_DIR" ] || [ ! -f "$SKILL_DIR/scripts/scrape.py" ]; then
  for dir in "${CLAUDE_PLUGIN_ROOT:-}/skills/content-ideas" "${CLAUDE_PLUGIN_ROOT:-}" "${GEMINI_EXTENSION_DIR:-}/skills/content-ideas" "./skills/content-ideas" "."; do
    [ -n "$dir" ] && [ -f "$dir/scripts/scrape.py" ] && SKILL_DIR="$dir" && break
  done
fi

echo "$SKILL_DIR"
```

If you can already see this file's path, just use its directory. The scripts
you'll call are `$SKILL_DIR/scripts/scrape.py` (fetch + score),
`$SKILL_DIR/scripts/assemble_feed.py` (deterministic Posts tab), and
`$SKILL_DIR/scripts/generate_feed.py` (render). The renderer template is
`$SKILL_DIR/assets/for-you-template.html` (the generator finds it automatically).

## Resolve the content home

All persistent files this skill reads and writes — the `brand/` profile and the
dated `research/` runs — live under one stable base, **never** the current
working directory. The skill runs daily and is invoked from anywhere, so the
base must be the same every time or it loses the profile and the run history.
Resolve it once and capture the concrete path:

```bash
CONTENT_HOME="${CONTENT_HOME:-$HOME/Documents/Content}"
mkdir -p "$CONTENT_HOME/brand" "$CONTENT_HOME/research"
echo "$CONTENT_HOME"
```

Throughout this guide every `brand/...` and `research/...` path is relative to
`$CONTENT_HOME` (so `brand/profile.md` means `$CONTENT_HOME/brand/profile.md`).
**Use the printed absolute path for every Read/Write of those files** — the
file tools don't expand shell variables, so writing a bare `brand/profile.md`
would land it in the wrong directory. (Credentials stay separate, in
`~/.config/content/.env`.) The scrape/generate scripts read `CONTENT_HOME`
themselves, so a relative `research/{today}` passed to them resolves here too.

---

## Step 0: First-run setup

**Run this before anything else, even if the user gave a topic.** Detect first
run by checking whether `~/.config/content/.env` exists and contains
`SETUP_COMPLETE=true`. Check silently. If it's already set up, skip to Step 1.

### 0a. Welcome + API token

Setup has three quick parts: an API token, **your** profile (built from your own
channels), and the competitors you want to track. Only the token is required —
the rest the skill bootstraps for you and you can refine any time. Nothing to
install; one Apify token covers every platform — X, Instagram, TikTok, YouTube,
and LinkedIn.

Show this as a normal message, then call `AskUserQuestion` (don't repeat the
welcome inside the modal):

> I turn your social presence into a daily For You feed: I build a profile from
> your own channels, track the competitors you pick, and surface what's
> performing as content ideas backed by real engagement. I just need an Apify
> API token (one token covers every platform; Apify's free plan includes monthly
> usage credit, no card).

`AskUserQuestion` — "Add your Apify API token?"
- Open the Apify Console to grab a token
- I'll paste a token now
- Skip for now

If they pick "Open the Apify Console", run
`open https://console.apify.com/settings/integrations`, then ask them to paste
the token. When the user pastes a token, write `~/.config/content/.env` (create
dirs; append, don't clobber other keys):

```
APIFY_TOKEN={token}
SETUP_COMPLETE=true
```

If they skip, write only `SETUP_COMPLETE=true`.

### 0b. Manual alternative

If they'd rather configure by hand, tell them to add those two lines to
`~/.config/content/.env`. Offer to write the file if they paste the key here.

### 0c. Build your brand profile

This is what personalizes everything: ideas get framed against *your* niche,
pillars, and goal, and checked against what you've already posted. Build it from
the user's own presence rather than a long questionnaire.

Ask for their own channels (`AskUserQuestion`: "Set up your profile now?" →
**I'll share my handles** / **Skip — I'll add it later**). When they share
handles — free-form across any platforms (`@me` on X, a YouTube channel, a
TikTok, etc.) — normalize them into the `{platform: [handle]}` shape and scrape
them like competitors, but over a much wider window (`--days 90`, the max) so
you characterize their work from a full quarter, not just recent posts:

```bash
python3 "$SKILL_DIR/scripts/scrape.py" \
  '{"x": ["me"], "youtube": ["@mychannel"]}' \
  --pillars "" --days 90
```

From the returned posts (plus comments/transcripts), draft the profile:
- **Niche, Audience, Voice Notes** — infer from recurring topics, framing, tone.
- **Content Pillars** — the 3–5 themes their posts actually cluster into. These
  drive `--pillars` on every future run, so get them right.
- **My Social Profiles** — handle, follower count, bio, and a one-line content-
  style note per platform, taken from the scrape.
- **Target Platforms / Research Channels** — the platforms they're active on.
- **Search Terms** — concrete keywords from their top topics.

Two things you can't scrape — **ask** (`AskUserQuestion`), then fold the answers in:
- **Content Goal** — why they post (lead gen / awareness / growth / thought
  leadership / selling…), where they drive traffic, and what they're promoting.
- **Pillar confirmation** — show the 3–5 pillars you inferred and let them
  edit or confirm before writing.

Write `brand/profile.md` per the schema in `FILE-SCHEMAS.md`. If the scrape
returned enough of their own posts, also write an initial `brand/my-content.md`
(performance summary, what's working, topics covered, and audience requests
distilled from their comments) — this powers anti-cannibalization and the "your
audience is asking for" banner from day one.

**If they skipped** (or there's no API key yet to scrape with), don't block:
build a minimal `brand/profile.md` from a 2–3 question Q&A (niche, rough
pillars, goal), note that re-running setup with a key auto-enriches it, and move
on.

### 0d. Track competitors

Ask who they want to track (`AskUserQuestion`: list them now / skip and use an
example). If they list handles, create `brand/tracked-accounts/{platform}.md`
files per the schema in the plugin's `FILE-SCHEMAS.md`. If they skip, run a
small example so they see the shape, and tell them they can add real
competitors later.

**End of first-run setup.** Then continue with the user's original request.

---

## Step 1: Load context

### 1a. Ingest the previous run's feedback into taste memory

Before anything else, fold the **last** run's reactions into your memory — this
is what makes each run better than the one before. List the dated subfolders of
`$CONTENT_HOME/research/` (`YYYY-MM-DD`) and take the most recent one. If it has a
`feedback.json`, read it and distill each entry in `reviews[]` (▲ "more like
this" / ▼ "less" / a note) into the *generalizable* taste signal, not the
one-off:

- "▲ on three contrarian takes in the user's niche" → "gravitates toward
  contrarian takes"; "▼ on listicles" → "listicle formats don't land." A
  note often states the reason directly — use it.
- **Record these to your project memory** (the auto-memory you maintain) as the
  user's content taste — the same place 1b recalls from. Update an existing
  taste note rather than duplicating it; let a single ▼ inform, not override, an
  established preference. Don't record one-off reactions with no pattern,
  anything already obvious from `brand/profile.md`, or post/run specifics (those
  live in `research/`). Taste only.

If there's no prior dated folder, no `feedback.json`, or no reactions in it,
skip silently. If auto-memory isn't available in this environment, skip too —
the reactions stay in `feedback.json` for whenever it is. (The current run's
reactions are ingested by the *next* run, the same way — there's no end-of-run
distillation step.)

### 1b. Recall taste and load brand context

Read whatever brand context exists (all optional — degrade gracefully):
- `brand/profile.md` — niche, pillars, search terms, content goal, audience
- `brand/tracked-accounts/*.md` — tracked creators per platform
- `brand/my-content.md` — the user's own content performance + audience requests

**Recall the user's content taste from your memory.** This skill stores an
evolving taste profile in your project memory (the auto-memory you maintain). Before generating ideas, recall what you know about what this
user gravitates toward — preferred topics, formats, angles, creators they keep
saving, and what doesn't land for them. If relevant taste signals are already
surfaced in context, use them; if not and memory is available, look for taste
notes tagged for this skill. This is the single most important personalization
input: engagement metrics measure what *audiences* like, taste memory measures
what *this user* likes. If auto-memory isn't available, fall back to engagement
signals alone (and to `brand/my-content.md` if present).

If there are no tracked accounts and no topic filter, ask for handles or a
topic before scraping.

### 1c. Refresh your own content (`my-content.md`)

Before generating ideas, bring `brand/my-content.md` up to date — this is the
per-run counterpart to the one-time build in Step 0c, and it's what keeps
anti-cannibalization and the "your audience is asking for" banner honest as the
user keeps posting. (`my-content.md` is declared *updated each run* in
`FILE-SCHEMAS.md`; this is the step that does it.)

Take the user's own handles from the `## My Social Profiles` section of the
`brand/profile.md` you just loaded, normalize them into the `{platform: [handle]}`
shape, and re-scrape them over a window wide enough to catch their own cadence
(`--days 30` — a creator's own posts are sparser than the merged competitor
feed, but keep it "recent," not the 90-day profile build from Step 0c):

```bash
python3 "$SKILL_DIR/scripts/scrape.py" \
  '{"x": ["me"], "youtube": ["@mychannel"]}' \
  --pillars "<pillars from profile.md>" --days 30
```

The scraper already pulls comments on the top posts, so the returned data
carries the audience replies you need. Rewrite `brand/my-content.md` from it per
the schema in `FILE-SCHEMAS.md` (performance summary, what's working / not,
topics covered, and audience requests distilled from the comments) — it's
replaced, not appended. Use this fresh version, not the copy you read in 1b, for
the rest of the run.

**Best-effort — never block the feed.** If `profile.md` has no own handles (the
user skipped profile setup), or the scrape returns nothing or errors, keep the
existing `my-content.md` and continue. This refresh is an enrichment, not a gate.

---

## Step 2: Create the daily run folder

List existing dated subfolders of `$CONTENT_HOME/research/` (`YYYY-MM-DD`). The most recent
one that is **not** today is the last-run date — pass it as `--since` in Step 3
so the scrape only keeps posts on/after that day. If there are no prior dated
folders, there's no `--since`.

Either way, the scraper enforces a **recency window** so the daily feed never
surfaces stale posts: by default it keeps only the **last 7 days** (`--days`).
`--since` can only *narrow* that window, never widen it — so first runs and
long-gap runs are both bounded to a week by default. (The script's hard cap is
90 days; for the daily feed keep it tight — a month at most. The 90-day window
is for one-off profile builds in Step 0c, not the daily feed.)

Create `$CONTENT_HOME/research/{today}/`.

**If `$CONTENT_HOME/research/{today}/feed-data.json` already exists**, ask whether to:
- **Refresh** — re-pull and rebuild (reuse the same `--since` / `--days`)
- **Expand** — widen the window: drop `--since` and/or raise `--days` (keep the
  feed within ~30 days) when the user wants more than the last week
- **View** — just (re)open the existing feed (skip to Step 6)

---

## Step 3: Scrape competitors

Build a JSON object mapping each platform to its tracked handles. Pass content
pillars (from `brand/profile.md`, or the user's niche/topic) via `--pillars` so
the script scores relevance, and the last-run date via `--since`. Leave `--days`
at its default (7) unless the user asks for a wider window, then raise it (max
31).

```bash
python3 "$SKILL_DIR/scripts/scrape.py" \
  '{"x": ["h1","h2"], "instagram": ["h3"], "youtube": ["@h4"]}' \
  --pillars "<the user's content pillars>" \
  --since 2026-04-15 \
  --days 7 \
  > "$CONTENT_HOME/research/{today}/scrape.json"
```

**Save the scrape JSON to `research/{today}/scrape.json`** (the redirect above) —
`assemble_feed.py` reads it in Step 6 to build the Posts tab deterministically, so
the scrape must be persisted, not just read into context.

Tell the user this takes a few minutes; progress streams to stderr. The script
fetches all accounts in parallel, **drops anything outside the recency window**,
scores engagement and relevance, flags outliers, and pulls comments/transcripts
on top posts. It returns:

```json
{ "results": { "x": { "h1": [ {post}, ... ] } }, "errors": [] }
```

Each post has `text`, `url`, `author`, `date`, `platform`, `engagement`,
`score` (weighted), `relevance` (0–1 vs pillars), `baseline` (Nx the account
average), `outlier` (bool), and — on top posts — `comments` / `transcript`.

**On errors:** report which accounts failed and proceed with what came back.

### Ad-hoc: fetch specific posts by URL

When the user hands you specific post URLs (a competitor's viral post, a link
they saw), use URL mode instead of profile mode. It returns a flat `[post]`
array with the same shape:

```bash
python3 "$SKILL_DIR/scripts/scrape.py" urls "https://x.com/u/status/1" "https://www.tiktok.com/@u/video/2" --pillars "..."
```

---

## Step 4: Review the scored data

The script pre-computes `score`, `baseline`, `relevance`, and `outlier`.
Identify the top-performing posts and the topics/themes/angles driving
engagement — especially high-relevance ones. This is the raw material for the
Ideas tab.

---

## Step 5: Build the feed

Two tabs. Everything shown has proven engagement. Build a `FEED_DATA` object
and write it (Step 6). Field-by-field structure is in the plugin's
`FILE-SCHEMAS.md` (`feed-data.json`).

**Tab 1 — Posts.** *You do **not** build this tab.* `assemble_feed.py` turns the
saved `scrape.json` directly into the `posts[]` array (and the `meta` block) in
Step 6 — deterministically, carrying **every** scraped post (no engagement gate,
no cherry-picking), with `performance`/`performanceDirection`, `zScore`/`why`,
`timestamp`, `sortValue`, and `engagement` all computed from the already-scored
scrape. Hand-writing `posts[]` would silently drop most of the feed, so don't.
Your only job in Step 5 is **Tab 2 (Ideas)**.

**Tab 2 — Ideas.** The one place you editorialize (label it as AI suggestion).
Generate up to 10 ideas. Each idea **must** conform to the `FeedIdea` contract
below — this is what the OS consumer reads to sync ideas into the Supabase
`ideas` table and render them. Fields not listed here are ignored by the
consumer.

### FeedIdea schema (ideas[] item)

```json
{
  "title": "<short idea headline — REQUIRED, must be non-empty>",
  "concept": "<the idea itself: what to make and why it works, 1–3 sentences>",
  "funnel": "<tofu | mofu | bofu | null>",
  "sourceUrl": "<URL of the competitor post that is the primary evidence, or null>",
  "pastCoverage": "<one sentence: prior coverage by this user on this topic, or null if not covered>",
  "brief": {
    "whyNow": "<why this is timely — engagement data, trend signal, audience demand, or taste pattern>",
    "differentiator": "<specific reason the user's version is better/different from what competitors posted>",
    "suggestedHook": "<a real opening line the user could speak or write, not a description of a hook>",
    "howToAction": "<concrete production note: format, length, platform-specific treatment>",
    "repurposeAs": ["<short | newsletter | thread | carousel | youtube | etc.>"]
  }
}
```

Field notes:
- **`title`** — the short scannable headline shown in the feed card. REQUIRED
  and non-empty. Write a specific, opinionated title (not a topic label).
- **`concept`** — 1–3 sentences: what the video/post is, the angle, and what
  makes it worth making. Becomes the note body when synced.
- **`funnel`** — lowercase `tofu`, `mofu`, or `bofu` only. Anything else
  (including uppercase `TOFU`) is dropped by the consumer — always lowercase.
- **`sourceUrl`** — the URL of the competitor post or outlier that is the
  evidence backing this idea. Use `null` if the idea comes from own-audience
  demand with no specific competitor post.
- **`pastCoverage`** — from `brand/my-content.md`. One sentence noting prior
  user coverage and the differentiator, e.g. "Covered as a broad overview on
  2025-11; this goes deeper on X." Use `null` if not previously covered.
- **`brief.whyNow`** — cite specific data: engagement numbers, recency, a
  competitor posting N times in a week, an audience comment quote.
- **`brief.differentiator`** — expertise depth, unique access, or contrarian
  take (see `references/content-strategy.md` for criteria).
- **`brief.suggestedHook`** — a real opening line, not "start with a bold
  claim." The user should be able to read it out loud.
- **`brief.howToAction`** — format, approximate length, platform treatment,
  CTA aligned to the user's content goal.
- **`brief.repurposeAs`** — array of format/platform strings, e.g.
  `["short", "newsletter", "thread"]`. Use `[]` if no repurposing applies.

**Concrete example:**

```json
{
  "title": "Why your AI agent keeps hallucinating tool calls — and how to fix it",
  "concept": "Three competitors posted about AI agents this week but all framed it as 'just use better prompts.' The real fix is structured output + retry logic, which none of them showed. Walk through the actual implementation.",
  "funnel": "mofu",
  "sourceUrl": "https://x.com/somedev/status/1234567890",
  "pastCoverage": "Covered AI agents broadly in Jan 2026; this focuses specifically on the tool-call failure mode not addressed there.",
  "brief": {
    "whyNow": "Two competitor posts on this topic hit 3–5× baseline engagement this week, signaling active audience demand. The gap in their coverage (no implementation detail) is the opening.",
    "differentiator": "You've debugged this exact failure mode in production client work — you can show real logs and the retry wrapper, not a toy demo.",
    "suggestedHook": "I spent three hours last Tuesday staring at an AI agent that kept calling the wrong tool. Here's exactly what was happening and the 12-line fix.",
    "howToAction": "YouTube tutorial 8–12 min with screen recording of the bug + fix. Add a code snippet in the description. CTA: DM me 'AGENT' for the retry wrapper snippet.",
    "repurposeAs": ["short", "thread", "newsletter"]
  }
}
```

For the generative craft — turning a topic into a differentiated title and
concept, writing hooks, classifying funnel stage (TOFU/MOFU/BOFU), aligning
CTAs, repurposing across platforms, and producing a full brief — **read
`references/content-strategy.md`**. The short version to keep in mind while
building this tab:

- **Make YOUR version, never repackage.** A good title/concept answers at least
  one of: what do you know the original creator doesn't (expertise), what have
  you done the audience hasn't seen (access), or where do you disagree
  (contrarian)?
- **Anti-cannibalization.** When `brand/my-content.md` exists, don't re-pitch a
  topic the user already covered unless the concept has a genuine differentiator
  (more depth, different format, an update, a response to feedback). Record it
  in `pastCoverage` explicitly.
- **Own-audience demand wins.** Requests from the user's own audience
  (`brand/my-content.md`) outrank competitor signals — foreground them in
  `brief.whyNow`.
- **Taste memory biases selection.** An idea that aligns with the taste signals
  you recalled in Step 1 (topics/formats the user gravitates toward) is a
  stronger pick than one justified by engagement alone — worth calling out in
  `brief.whyNow` ("this fits a pattern you keep coming back to"). Deprioritize
  anything that matches a recorded "doesn't land" signal.

---

## Step 6: Write and open the feed

The feed data at `$CONTENT_HOME/research/{today}/feed-data.json` is a JSON object
with keys `meta`, `posts`, `ideas`. Build it in two steps:

**6a. Assemble the Posts tab deterministically.** Run `assemble_feed.py` on the
saved scrape — it writes `meta` + the full `posts[]` and seeds an empty `ideas`
list (preserving `ideas` if the file already exists, so it's safe to re-run):

```bash
python3 "$SKILL_DIR/scripts/assemble_feed.py" \
  "$CONTENT_HOME/research/{today}/scrape.json" \
  --run-date "$(date -u +%FT%TZ)" --days 7 --since 2026-04-15 \
  --out "$CONTENT_HOME/research/{today}/feed-data.json"
```

**6b. Add the Ideas tab.** Read the `feed-data.json` you just wrote and set its
`ideas` key to the Ideas array you built in Step 5 (`meta` and `posts` stay as
`assemble_feed.py` produced them — don't touch them). Write the file back.

Do **not** write HTML yourself; the generator embeds this JSON into the
template.

Then render it. Default to the live server (lets the user react to items, which
saves to `feedback.json` for future personalization):

```bash
python3 "$SKILL_DIR/scripts/generate_feed.py" "$CONTENT_HOME/research/{today}"
```

This starts a local server and **automatically opens the feed in the user's
default browser**. Still hand the user the `http://localhost:<port>` URL the
command prints, so they can reopen it if the tab closes. (Pass `--no-browser` to
suppress the auto-open; the URL is printed either way.) The command runs in the
foreground until the user stops it with Ctrl+C, so run it in the background if
you need to keep working.

In a headless/no-display environment, write a self-contained file instead and
point the user at it (the page lets them download their reactions):

```bash
python3 "$SKILL_DIR/scripts/generate_feed.py" "$CONTENT_HOME/research/{today}" --static
# → $CONTENT_HOME/research/{today}/for-you.html
```

Then present a short text summary (post count, how many are outliers, a couple
of standout posts) and the page location.

---

## Step 7: Offer next steps

The user reacts to the feed in the browser; their reactions save to
`research/{today}/feedback.json` on their own — automatically in server mode,
or via the page's download button in static mode. There's no "done" signal and
nothing for you to read or distill now: the file just accumulates reactions,
and the **next** run folds them into taste memory at Step 1a. This keeps the
workflow simple and, crucially, captures reactions the user makes after this
conversation has ended.

Offer to: dig deeper on any idea, add/remove tracked accounts, or rerun with a
different topic focus.

---

## Notes

- **Reactions / feedback → taste memory.** The feed page lets the user mark
  items (▲ more like this / ▼ less / a note) across both tabs. In server
  mode these save to `research/{date}/feedback.json` automatically as the user
  clicks; in static mode the user downloads that file into the run folder. The
  file is just an accumulating list of reactions — no status, no submit step.
  The **next** run reads the previous run's `feedback.json` at Step 1a and
  distills it into your project memory so future runs are personalized — there
  is no taste *file*; taste lives in auto-memory.
- **No API token = no run.** Profile mode requires `APIFY_TOKEN` — every platform
  goes through Apify actors. If the token is missing, the script returns an error;
  stop and show setup instructions rather than inventing data.
