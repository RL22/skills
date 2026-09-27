---
name: elg-engine
description: Generate authentic quintuple-perspective social posts (builder, gtm, talent, visionary, product) from git diffs, PRDs, and changelogs with anti-cringe filtering and comment-first link delivery. Use when converting code commits, PRDs, or releases into high-signal Employee-Led Growth posts without corporate hype.
author: Rodney Lewis
license: Apache-2.0
---

# ELG Perspective Engine (`elg-engine`)

Open-standard Agent Skill for Employee-Led Growth (ELG). Translates raw engineering commits, pull requests, PRDs, and changelogs into authentic, peer-to-peer social posts across five distinct role perspectives while eliminating corporate hype and protecting against the social algorithm link penalty.

---

## 1. Trigger Conditions

Activate this skill whenever:
- User asks to turn a **git diff**, **pull request**, or **commit log** into a social post or release announcement.
- User provides a **PRD**, **RFC**, or **technical specification** and asks for angles or launch content.
- User asks to "generate angles", "write social posts for this release", "create builder/gtm/talent post", or mentions `/angles` / `/link`.
- User asks to sanitize or run an **anti-cringe filter** on a draft post.
- User needs comment-first link attribution (`go.company.com/e/:member`) to protect social algorithm reach.

---

## 2. The Three Anti-Patterns Solved

1. **The Corporate Cringe Penalty:** Traditional advocacy prompts generate robotic corporate cheerleading ("thrilled to announce", "supercharged game-changer"). This destroys employee credibility with peers and triggers feed spam filters.
2. **The Algorithm Link Penalty:** Modern social algorithms (LinkedIn, X) penalize posts with external links by 40% to 60%. External links MUST be stripped from the `post_body` and delivered exclusively in `first_comment`.
3. **The Blank Screen Problem:** Engineers ship complex systems but do not know how to frame their technical decisions for peers. This skill extracts trade-offs, metrics, and failure stories directly from artifacts.

---

## 3. The 5 Role Perspectives

For any technical milestone or release, derive up to five distinct role perspectives:

### 1. `builder` (Engineering & Architecture)
- **Voice:** Staff Engineer chatting over coffee. Direct, technical, humble, transparent about trade-offs.
- **Focus:** System architecture, database migrations, concurrency bottlenecks, latency reductions, what broke in staging, and what didn't break in prod.
- **Rules:** No corporate fluff. Use specific technical nouns (Postgres WAL, edge redirects, Tokio worker pools).

### 2. `gtm` (Sales, Solutions & Marketing)
- **Voice:** High-empathy commercial operator.
- **Focus:** Real customer business pain eliminated, operational metrics improved, why legacy tools were painful.
- **Rules:** Never list feature bullet points. Focus on the before/after operational state of the customer.

### 3. `talent` (Recruiting & Team Culture)
- **Voice:** Team builder showcasing engineering autonomy.
- **Focus:** Team velocity in action, how decisions are made, engineering culture, paired with specific open engineering roles.
- **Rules:** No generic "we're hiring!" posts. Anchor hiring requests to the hard problem just solved.

### 4. `visionary` (Founder, Exec & Category Narrative)
- **Voice:** Category creator with a strong point of view.
- **Focus:** Industry macro shifts, why this category is evolving, contrarian thesis on software or AI, long-term direction.
- **Rules:** Avoid generic visionary cliches. Anchor predictions in concrete developer and market behavior.

### 5. `product` (Product Management & UX Design)
- **Voice:** Product craft specialist obsessed with user friction.
- **Focus:** User interaction design decisions, why previous workflows felt clunky, usability trade-offs, how the user's daily workflow changes.
- **Rules:** Explain the design compromise honestly. Highlight the friction that was removed.

---

## 4. Anti-Cringe Filter Rules

Every draft must pass through these constraints:

1. **Forbidden Emojis:** Strip rocket (🚀), fire (🔥), party popper (🎉), flexing bicep (💪), and trending graph (📈).
2. **Banned Hype Words:** Strip "game-changer", "supercharge", "delve", "harness", "foster", "empower", "plethora", "synergy", "seamless", "bespoke", "revolutionary", "thrilled to announce", "excited to share".
3. **No Rhetorical Question Openers:** Ban "Have you ever wondered...?", "Are you tired of...?", "What if I told you...?". Open directly with an observation, a metric, or a strong claim.
4. **Length Budget:** 150 to 300 words (900 to 2,000 characters). Short, scannable paragraphs with single line breaks.
5. **Strict Link Separation:** 
   - `post_body`: Strictly 100% link-free.
   - `first_comment`: Delivers the link formatted as: `Link to docs/repo: https://go.company.com/e/:member?url=<destination>`.

---

## 5. Output Format Schema

Always return drafts in this structured format:

```markdown
### [Role Name] Perspective

**Post Draft (Link-Free Body):**
[Authentic 150-300 word post with raw trade-offs, metrics, and zero external URLs]

**First Comment (Attributed Link):**
👉 Link to the implementation / docs: https://go.company.com/e/:member?url=<target_url>
```
