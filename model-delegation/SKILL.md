---
name: model-delegation
description: Execute runtime cross-CLI subprocess calls via delegate.sh across agy (Gemini), codex (GPT), and claude (Claude). Routes high-volume reads, live web search, media understanding, and independent skeptic diff reviews to the best model CLI with sandboxing and digest formatting. Trigger on "delegate", "/model-delegation", "delegate to subagents", "with agents", "fan out", "launch subagent(s)", "launch a subagent", "ask Gemini", "ask GPT", "second opinion", "cross-model review", "map codebase with agy".
license: MIT
compatibility: Agent-agnostic CLI wrapper (requires agy, codex, or claude on PATH).
metadata:
  author: Sprintz
  version: "1.4.0"
  category: runtime-interoperability
---

# Model Delegation Engine (`scripts/delegate.sh`)

Route tasks to the optimal executor CLI (`agy`, `codex`, or `claude`) at runtime. The driver CLI retains judgement, architecture, and verification; delegated subprocesses execute high-volume reads, live web searches, perception, or independent skeptic reviews.

> **Phrasing note**: when the user says "delegate to subagents," "launch subagent(s)," or similar, that means *this* skill (`delegate.sh` cross-CLI routing) — not the generic in-app Agent/Task-spawning tool. Route through here by default.

```txt
driver (claude | codex | agy)
  └── scripts/delegate.sh --task <type> "prompt"
        ├── agy    → Gemini / Flash   (bulk · search · media · scaffold)
        ├── codex  → GPT / Sol        (review · reason · implement)
        └── claude → Claude / Haiku   (summarize · draft · fallback)
```

---

## Separation of Concerns Matrix

| System Layer | Owner | Role & Responsibility |
| :--- | :--- | :--- |
| **Policy Layer** | `AGENTS.md` | Single source of truth for Model Tier (0–3) semantics & Security Policy. Concrete provider/model mappings live in `routes.json` (Execution Layer), not here — see §4.1. |
| **Architecture Layer** | `/map-graph` | Deconstructs goals into DAG Nodes, State Schemas, Skeptic Loops, and Tier assignments. |
| **Execution Layer** | `/model-delegation` | Runs `scripts/delegate.sh` to execute cross-CLI calls with sandboxing, digests, and timeouts. |

---

## When to Delegate

Delegate when a task is **bulk, perceptual, or benefits from an independent model's review**. Do not delegate tiny inline edits—round-tripping overhead exceeds doing it inline.

| Delegate to Subprocess | Keep in Driver Session |
| :--- | :--- |
| Large codebase mapping / file tree scanning | Architectural decisions & component boundaries |
| Live web search with citations | Verifying facts & integrating findings |
| Audio / video / image understanding | Reconciling conflicting reviews |
| Independent skeptical review of staged diffs | Final call on merging or completing work |

---

## Usage Syntax

```bash
# Search & Bulk Tasks (agy / Gemini)
delegate --task search "dplyr 1.1.0 release notes with URLs and dates"
delegate --task bulk --dir ./src "Map the auth flow end to end"

# Independent Skeptic Review (codex / GPT)
delegate --task review --dir . "Review the staged diff for correctness. Be skeptical."
echo "$(git diff)" | delegate --task review

# Utilities
delegate --list                         # Print current routing table & fallback rules
delegate --task bulk --dry-run "..."    # Dry-run command resolution without executing
scripts/pre_release_check.sh            # Syntax, version, and mocked regression gate
```

---

## Task Capability Routing Table

Models are mapped to tasks by capability tier (tier semantics defined in `~/Sprintz/.agents/AGENTS.md` §4; concrete model bindings live only in `scripts/routes.json`). The table below is a human-readable snapshot for orientation — `routes.json` is the executed source of truth, so if this table and `delegate --list` ever disagree, trust `--list`. Specific model IDs resolve dynamically via `scripts/delegate.sh` or environment overrides (`DELEGATE_<TASK>_MODEL`).

| Task | Tier | Target Executor | Pinned Model | Default Effort | Safety & Sandbox Ceiling | Fallback |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `search` | 2 | `agy` (pinned) | `gemini-3.1-pro-high` | `high` | Sandboxed FS + Web Tools | stop |
| `bulk` | 1 | `agy` | `gemini-3.7-flash-high` | `high` | Sandboxed, Read-Only, **Digest On** | `claude`/`claude-haiku-4-5` |
| `cheap` | 1 | `agy` | `gemini-3.7-flash-low` | `low` | Sandboxed, Read-Only | `claude`/`claude-haiku-4-5` |
| `media` | 2 | `agy` | `gemini-3.7-flash-high` | `high` | Sandboxed, Read-Only | stop |
| `scaffold` | 2 | `agy` | `gemini-3.7-flash-high` | `medium` | Writes to `--dir` | stop |
| `review` | 3 | `codex` | `gpt-5.6-sol` | **`high`** | `--sandbox read-only` | stop |
| `reason` | 3 | `codex` | `gpt-5.6-sol` | **`high`** | `--sandbox read-only` | stop |
| `audit` | 3 | `claude` (pinned)| `claude-opus-5` | **`high`** | `--sandbox read-only` | stop |
| `implement` | 2 | `codex` | `gpt-5.6-sol` | `medium` | `--sandbox workspace-write` | stop |
| `summarize`| 1 | `claude` (pinned)| `claude-haiku-4-5` | `low` | No write tools, **Digest On** | stop |
| `draft` | 2 | `claude` (pinned)| `claude-sonnet-5` | `medium` | No write tools | stop |
| `image` | 2 | `agy` (pinned) | `gemini-3.1-pro-high` (Nano Banana Pro) | — | Writes an image file to `--dir` | stop |
| `image-text`| 2 | `codex` | Codex-internal image tooling | — | `--sandbox workspace-write` | stop |

`image-alt` is a retained alias for `image-text`.

**Fallback is deliberately narrow.** Only `bulk` and `cheap` — tasks whose output is *consumed*, not judged — get a real fallback; everything whose output is trusted as a verdict (`review`, `reason`, `audit`) or that mutates a workspace (`implement`, `scaffold`) stays `stop`-only. See § Fallback Policy below.

### Choosing between the two image routes

**Symbols and structure → `image-text`. Light, matter and continuity → `image`.**

| Reach for `image-text` (GPT Image) | Reach for `image` (Nano Banana Pro) |
| :--- | :--- |
| Legible copy, headers, body text | Ambient light bounce, complex lighting |
| Exact prices, slogans, chart keys | Fabric drape, wood grain, skin and hair |
| Geometric lines, floorplans, blueprints | Photoreal humans and products |
| Multi-column grids, data tables, icon alignment | Merging several reference images into one scene |
| Numbered callouts, exploded technical views | Character consistency across sequential frames |
| Stylized 3D and fantasy typography | Stylized organic brand artwork |

GPT Image is **not** a fallback — it is the primary choice for 8 of the 14 tasks in the
full matrix, which is why the route is `image-text` and not `image-alt`. When a prompt
wants both (photoreal storefront *with* a legible sign), pick by which failure is worse;
garbled text usually fails harder than flatter light, so lean `image-text`.

Per-vertical matrix (interior design, UI/UX, advertising, entertainment, technical media)
and the model-tier mechanics: [`references/image-routing.md`](references/image-routing.md).

> **`image` pins its model on purpose.** agy's `generate_image` inherits the *session*
> model tier, so omitting `--model` silently serves the NB2-lite default. The route pins
> `gemini-3.1-pro-high` to force Nano Banana Pro. Removing that pin is a quiet quality
> regression with no error.

---

## Subprocess Execution Rules

1. **Driver Rerouting Guard**: Never delegate a task back to the CLI driver.
   - If `codex` is driving, Tier 3 reasoning tasks (`review`, `reason`) automatically reroute to `claude` with **`claude-opus-4-6`**.
   - If `agy` is driving, `bulk` and `cheap` tasks automatically reroute to `claude` (`haiku`/`sonnet`).
   - If `claude` is driving, `review` and `reason` tasks automatically reroute to `codex` (`gpt-5.6-sol`).
2. **Sandbox Enforcement**: Codex invocations explicitly pass `--sandbox` ceilings so subprocess calls never inherit interactive `danger-full-access` permissions. They also use `--ephemeral` with a private writable runtime home. Mutable auth and config files are copied into that home; skills and rules are linked as static inputs.
3. **Digest Discipline**: High-volume tasks (`bulk`, `summarize`) turn on `--digest` to enforce a 400-word findings contract, preventing context bloat.
4. **No Double-Backgrounding**: If the calling tool already has a background/async execution mode (e.g. a `run_in_background` flag), use *that* — do not also append a trailing `&` to the `delegate.sh` command. Backgrounding twice returns control to the caller as soon as the outer shell forks, before `delegate.sh`'s own subprocess (`agy`/`codex`/`claude`) finishes; the outer wrapper then exits 0 immediately, and the still-running executor process is orphaned and typically killed with the parent shell, silently — producing a 0-byte log and no output file, with no error surfaced. If backgrounding manually via shell (no tool-level async mode available), background the whole command once, e.g. `nohup delegate.sh --task reason ... > out.log 2>&1 &`, and confirm completion by checking the log/output file exists and is non-empty — do not trust a `0` exit code from the launcher alone.
5. **`reason`/`review`/`audit` Cannot Write Files (now auto-promoting)**: All are pinned `--sandbox read-only` (see routing table). If the prompt asks the executor to save output to a file (e.g. "write the plan to `plan.md`"), `delegate.sh` detects this intent before execution and deterministically promotes the task to its write-capable sibling (`implement` or `scaffold`).
6. **Fallback Policy** (v1.3.0+): a route's `fallback` column (`--list` shows it) is `stop` for almost every task — a hard failure (empty output, or the `--timeout` wall-clock guard) surfaces as-is, with no retry. `bulk` and `cheap` are the exception: on a hard failure they retry exactly once on the declared `<executor>:<model>` fallback, logged to stderr (`falling back once to claude/claude-haiku-4-5`). The fallback never triggers on a usage error (bad flags, missing model), never chains (the fallback target has no fallback of its own), never fires if it would just repeat the identical executor+model the primary attempt already used (this can happen when rule 1's self-delegation reroute lands the primary on the same CLI the fallback would have used), and is skipped — falling straight through to the original failure — when the fallback executor equals the current driver, per the same self-delegation guard as rule 1. An auto-promoted task (rule 5) always drops its origin task's fallback — a promoted call now writes to `--dir`, and a mutating call is stop-only regardless of what its read-only origin declared. This intentionally does **not** cover `review`/`reason`/`audit`/`implement`: those tasks' output is trusted as a verdict or a diff, and a second model silently standing in for a failed one is a correctness risk, not a convenience — that failure should surface to the driver, not be masked. That boundary lives in `routes.json`, the same place every other routing decision lives — nothing stops an edit from giving `review` a fallback, exactly as nothing stops an edit from giving it `low` effort; `routes.json` is deliberately data, not a hard-coded policy.
   One retry is "one executor switch," not "the fallback CLI is invoked at most once" — the pre-existing moderation-retry (this section's sibling mechanism, unrelated to fallback) still applies independently within *each* attempt, so a moderation-blocked fallback response gets the same single in-place retry a moderation-blocked primary would.
7. **Normalized JSON Envelope** (v1.3.0+): `--json` now emits the identical 9-key shape for every *execution* outcome — `{success, executor, model, task, duration_seconds, text, escalated_from, fallback_used, error}` (`text` was `response` before v1.3.0 — that key was renamed, not aliased). On a clean success `text` holds the reply and `error` is `null`. On any nonzero exit — a hard failure (empty output, `EX_TIMEOUT`) or an executor that exited nonzero with partial output — `error` holds a short excerpt of the executor's stderr; `text` is `null` only for the hard-failure case, since partial output is still real output. `fallback_used` is `true` only when rule 6's retry actually ran. **Scope boundary**: this covers everything that reaches an executor. A *usage* error (bad `--to`/`--effort`/`--dir`, unknown task, a missing CLI on `PATH`) fails via `die()` before there's a call to describe, and still exits with plain stderr text and no JSON, exactly as before v1.3.0 — the envelope answers "what did the model do," not "was this invocation well-formed."
8. **Routing table storage** (v1.4.0+): the routing table moved from a pipe-delimited `ROUTES` string parsed inline with `IFS='|' read` to `routes.json` (schema: task/executor/pinned/model/effort/mode/digest/fallback), validated once at load time by `route_lookup.py` — a missing field, wrong type, or duplicate task name fails immediately with the specific row and reason, not a downstream `[ "${#_R[@]}" -eq N ]` count mismatch. `delegate.sh` shells out to `route_lookup.py --list` / `--task <name>` for every lookup; both commands' output contracts are unchanged from the old bash implementation, so nothing that calls `delegate.sh` needed to change. `route_lookup.py` is stdlib-only Python (`json`, `sys`, `pathlib`) — no new dependency, since `python3` was already required for the JSON envelope (rule 7). Edit `routes.json`, not `route_lookup.py` or the bash routing block, for any table change.

---

## Pre-flight Auto-Promotion (Orchestration Layer)

`delegate.sh` evaluates read-only tasks before execution. If the prompt requires file writes, it promotes the task to a write-capable sibling automatically. This deterministic pre-flight check eliminates the redundancy of running a model only to have its sandbox reject the write and requiring a second retry.

**How it detects write intent**: Before routing a read-only task (`reason`, `review`, `search`, `bulk`, `cheap`, `media`), `delegate.sh` scans the prompt for filenames preceded by a write-intent verb ("write," "save," "creat-," "persist," "output") within ~60 characters — not just any filename mention, so "read `plan.md` for context" never false-positives. If write intent is found, it immediately promotes the task to its write-capable sibling:

| Read task | Promotes to | Executor |
| :--- | :--- | :--- |
| `reason`, `review` | `implement` | codex (workspace-write) |
| `search`, `bulk`, `cheap`, `media` | `scaffold` | agy (write) |
| `summarize`, `draft` (claude) | *(none configured)* | driver must write the file itself from the returned text |

The promoted run is noted on stderr before execution, so it's always visible which task is actually running.

Explicit executor, model, effort, digest, timeout, and JSON choices survive the promotion. JSON reports the executor/model/task that performed the write, total duration, and `escalated_from`.

**Turning it off**: `--no-auto-escalate` per call, or `DELEGATE_AUTO_ESCALATE=0` globally, for cases where a read-only task must never write under any circumstance (e.g. a security review that should hard-fail rather than silently escalate into a write-enabled sandbox).

---

## References & Assets

- `scripts/delegate.sh` — Universal bash wrapper for cross-CLI execution.
- `scripts/test_delegate.sh` — Mocked regression suite; calls no model APIs.
- `scripts/pre_release_check.sh` — Pre-release gate for syntax, version alignment, and regressions.
- `references/cli-executor-reference.md` — CLI flag inventory (`claude`, `agy`, `codex`) and sandbox verification notes.
