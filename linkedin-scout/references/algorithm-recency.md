# LinkedIn Feed Algorithm: Recency, Velocity, and Engagement Dynamics

Reference guide for agents discovering, ranking, and drafting LinkedIn engagement.

## 1. Post Selection Heuristics (When Scouting Posts)

When selecting target posts for commenting via `linkedin-scout`:

- **Target Window (4 to 48 hours):** Prioritize posts published between 4 and 48 hours ago. These posts have cleared the initial quality filter and carry proven organic distribution.
- **Avoid Cold Outliers (>72 hours):** Posts older than 3 days have completed their primary distribution cycle unless actively sustained by high-velocity debates.
- **Avoid Zero-Signal Fresh Posts (<30 minutes):** Posts under 30 minutes old lack engagement signals to indicate whether LinkedIn will throttle or distribute them.

## 2. The Initial Velocity Gate (The "Golden Hour")

LinkedIn uses early engagement velocity to test content before wider routing:

- **Cohort Sampling:** Upon publishing, the post displays to a test sample (roughly 5% to 10% of immediate connections).
- **Evaluation Window:** The first 60 to 90 minutes determine feed expansion.
- **Scored Actions:** Dwell time (pauses in feed scroll) and substantive comments (>15 words) carry higher ranking weight than reactions (likes).
- **Secondary Routing:** Posts clearing velocity thresholds expand into second- and third-degree feeds.

## 3. Decay Curve vs. Knowledge Relevance

LinkedIn does not use a pure chronological decay model:

- **Relevance Scoring:** LinkedIn NLP models categorize posts by professional domain and topical authority.
- **Extended Half-Life:** Relevant, high-dwell technical posts maintain active feed distribution for 48 to 72 hours, and up to 14 days when discussion continues.
- **Topical Affinity:** Engagement signals override chronological age if the viewer has high interaction affinity with the topic or author.

## 4. Comment-Driven Distribution Mechanics

Leaving comments expands reach through specific algorithmic behaviors:

- **Feed Surfacing:** A substantive comment pushes the original post into the feeds of the commenter's network with the label: `[Name] commented on this`.
- **The Two-Hour Reply Loop:** Author replies within 2 hours double the active interaction count and signal conversation freshness to the feed ranking engine.
- **Piggybacking High-Reach Threads:** Adding high-signal commentary to verified high-performing posts (10+ comments) puts the commenter's profile before all second-wave readers.

## 5. Account Cadence and Cannibalization Guardrails

When planning original posts and engagement sessions:

- **24-Hour Spacing Rule:** Keep an 18 to 24-hour buffer between original posts. Publishing two posts in under 18 hours causes feed self-competition, where LinkedIn throttles the earlier post to test the newer one.
- **Pre-Post Warm-up:** Spend 10 to 15 minutes leaving 3 to 5 thoughtful comments on targeted creators before publishing original content. This sets active session state.
- **Recruiter Search Freshness:** For inbound recruiter discovery, LinkedIn Recruiter includes an explicit filter: `Active in the last 7 days`. Taking active actions weekly maintains top ranking in recruiter search candidate lists.
