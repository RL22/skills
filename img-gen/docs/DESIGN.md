# `/claude.img` — Dual-Model Image Studio Skill — Design Spec

**Status:** Approved design (pre-implementation)
**Date:** 2026-06-04
**Author:** Rodney Lewis (with Claude)
**Canonical location:** `~/.agents/skills/claude.img/`
**Supersedes:** the `banana` skill (AgriciDaniel/banana-claude), evaluated via SkillVault SIFT (scored 67/100 — Trial)

---

## 1. Overview

`/claude.img` is a portable, dual-model image generation, direction, and editing skill. It generates images with **two models**:

- **Nano Banana** (`gemini-2.5-flash-image`) — via the Gemini CLI nanobanana extension
- **GPT Image 2** (`gpt-image-2`) — via the Codex CLI native `image_gen` tool

It exposes three front doors onto one shared engine: an **agent command** (`/claude.img …`), a **local browser studio** (prompt box + director chat + editing layer), and the underlying **CLI/scripts**. Every path calls the same core functions with an identical signature and identical JSON return, so switching model or surface is a one-argument change.

The skill keeps the genuinely good parts of `banana` (prompt-engineering discipline, domain modes, presets, cost logging, success validation) while fixing its two structural flaws: Claude-only lock-in and plaintext credential storage.

## 2. Goals

- **Portable** across Claude Code, Antigravity, and Codex (no MCP, no agent-specific binaries required beyond the CLIs the user already runs).
- **Zero credential management by default** — generations run on the user's existing Codex OAuth and Gemini CLI auth.
- **Two models, one contract** — structurally identical invocation; model is a single argument.
- **Cost-disciplined** — cheapest viable path by default; expensive escalations are deliberate.
- **Self-serve studio** — a barebones local GUI to prompt, direct, and lightly edit images without spending agent/session tokens.
- **Lives with the skill** — spec, references, scripts, and assets all under `~/.agents/skills/claude.img/`.

## 3. Non-Goals

- Not a full image editor (Photoshop/GIMP replacement). The editing layer is intentionally tiny.
- Not a hosted/multi-user web app. The studio binds to localhost only, single user.
- No account system, no cloud storage, no telemetry.
- Not a video generation skill (out of scope for v1).

## 4. Background — why this exists

The `banana` SIFT evaluation surfaced a high-craft skill with two disqualifying issues for this user's stack:

1. **Claude-lock-in** — wired an MCP into `~/.claude/settings.json`; would not port to Antigravity/Codex (the user's stated priority).
2. **Plaintext credentials** — wrote `GOOGLE_AI_API_KEY` unencrypted into the settings file.

This design keeps banana's prompt-engineering IP and discards its delivery mechanism.

## 5. Architecture

### 5.1 One engine, three front doors

```
/claude.img {model?} {prompt?} ─→ Agent (full creative-director craft) ─┐
/claude.img studio ────────────→ Local GUI (prompt box + director chat) ├─→ core.py
[browser editing layer] ───────────────────────────────────────────────┘     │
                                                                              ▼
                                                         ┌─ delegation path (default, no keys) ─┐
                                                         │   gemini_runner.py → headless gemini  │
                                                         │   codex_runner.py  → codex exec       │
                                                         └─ direct-API path (fallback, keyed) ───┘
                                                             gemini_api.py / openai_api.py
                                                                              │
                                                  locate output → move to working dir → return JSON
```

### 5.2 Dual generation path

Per the approved decision, **both** paths ship in v1 and are switchable per call (CLI flag / studio toggle / config default):

**A. Delegation path (default, zero-key):**
- `gemini_runner.py` spawns a **silent headless** `gemini` subprocess invoking the nanobanana extension's `/generate` (or `/edit`) custom command. Uses existing Gemini CLI auth. Model env: `NANOBANANA_MODEL=gemini-2.5-flash-image`.
- `codex_runner.py` spawns `codex exec` (headless) using the native `image_gen` tool. Uses Codex OAuth/subscription — no API key. Codex writes to `~/.codex/generated_images/`.
- Each runner then **locates the produced file and moves/copies it into the working directory** (or the studio gallery dir), returning the standard JSON contract.

**B. Direct-API path (fallback, keyed):**
- `gemini_api.py` calls the Gemini API directly (`GEMINI_API_KEY`).
- `openai_api.py` calls the OpenAI Images API / Codex `scripts/image_gen.py` style path (`OPENAI_API_KEY`).
- Faster and more deterministic; used for the studio's high-frequency iteration or when delegation is unavailable.

**Selection precedence (per call):** explicit flag → studio toggle → config default (`delegation`) → automatic fallback to direct-API if the required CLI is missing/unauthed and a key is present.

### 5.3 Shared core contract

```
core.generate(model, prompt, mode, quality, size, count, path="delegation") -> Result
core.edit(model, image, instruction, mask=None, path="delegation")        -> Result

Result (JSON): { "path": str, "model": str, "prompt": str,
                 "settings": {...}, "cost": {...}, "engine": "delegation|api" }
```

Both runners and both API adapters implement the same interface; only output-location logic differs.

## 6. Components

| Component | File(s) | Purpose |
|---|---|---|
| Engine core | `scripts/core.py` | Dispatch, shared prompt-engineering (5-component formula, banned-keyword strip, domain modes), param mapping, routing |
| Gemini delegation | `scripts/gemini_runner.py` | Headless `gemini` + nanobanana extension |
| Codex delegation | `scripts/codex_runner.py` | `codex exec` + native `image_gen` (gpt-image-2) |
| Gemini API fallback | `scripts/gemini_api.py` | Direct Gemini API (keyed) |
| OpenAI API fallback | `scripts/openai_api.py` | Direct OpenAI Images API (keyed) |
| Edit | `scripts/edit.py` | Mask-directed + instruction edits via either model |
| Batch | `scripts/batch.py` | N variations with rotated components |
| Presets | `scripts/presets.py` | Brand/style preset CRUD |
| Cost tracker | `scripts/cost_tracker.py` | Per-call cost/quota logging |
| Studio server | `scripts/serve.py` | stdlib `http.server`, localhost-only, serves GUI + `/generate` `/edit` endpoints |
| Setup validation | `scripts/validate_setup.py` | Checks `gemini` + nanobanana ext, `codex`, optional keys |
| Studio UI | `assets/studio.html` | Vanilla JS: prompt box, director chat, editing canvas, gallery |
| Routing ref | `references/model-selection.md` | Auto-route table + decision logic |
| Prompt ref | `references/prompt-engineering.md` | Shared formula + per-model dialects |
| Model refs | `references/nano-banana.md`, `references/gpt-image.md` | Model-specific params, sizes, quality tiers |
| Presets/cost refs | `references/presets.md`, `references/cost-tracking.md` | Carried from banana, adapted |

## 7. Invocation contract

```
/claude.img {model?} {prompt?}        model ∈ gemini | gpt   (omit = auto)
/claude.img studio                    launch local GUI, open browser, step out
/claude.img edit <path> <instruction> edit existing image
/claude.img batch <idea> [N]          N variations
/claude.img preset [list|create|show|delete]
/claude.img inspire [category]        curated prompt database
```

Optional flags: `--engine delegation|api`, `--quality`, `--size`, `--count`, `--mode <domain>`.

| You provide | Skill does |
|---|---|
| model + prompt | optimize prompt in that model's dialect → generate |
| prompt only | recommend best-fit model + one-line why → confirm → generate |
| model only | AskUserQuestion to elicit goal (use case, style, key elements) → optimize → generate |
| neither | ask goal first → recommend model → generate |

## 8. Model routing

`references/model-selection.md` + auto-route logic. Default `auto` announces its choice out loud (teachable, not magic).

| Task signal | Default model | Why |
|---|---|---|
| Text *in* image (posters, UI, logos w/ words, infographics) | **GPT Image 2** | >99% text accuracy, composition planning |
| Transparent background / precise size | **GPT Image 2** | Native transparency + fixed sizes |
| Edit / inpaint / character consistency | **Nano Banana** | Strong region/identity retention |
| Fast, cheap iteration / batch | **Nano Banana** | Faster, cheaper |
| Multi-turn director chat | **Nano Banana** | Session consistency |
| Tiebreak (both fit) | **Nano Banana** | Cost-aware default |

## 9. Studio GUI

Single `assets/studio.html` (vanilla JS, no build step), served by `serve.py` (stdlib, localhost-only). Once launched, the agent steps out — iteration happens in the browser at ≈0 session tokens.

**Panels:**
1. **Prompt box** — natural-language intent + model toggle (Gemini/GPT/Auto) + domain dropdown + quality/size/count. Returns image + final optimized prompt + cost.
2. **Director chat** (toggle) — multi-turn directing; keeps creative context (subject/style/preset). Backed by a **persistent CLI session** (delegation) or a cheap text model (API path) for prompt reasoning.
3. **Editing layer** — see §10.
4. **Gallery** — reads the output dir; click → edit/iterate. Running cost total in the corner.

**Safety:** localhost bind only; credentials never leave the server process; never sent to the browser.

## 10. Editing layer (tiny)

Three tiers, cheapest first:

1. **Local canvas ($0, no model)** — crop, rotate/flip, brightness/contrast/saturation, resize/aspect. Pure client HTML5 canvas, no deps. Export → gallery.
2. **Mask-directed AI edit** — brush a region + instruction → `core.edit(model, image, mask, instruction)`; only the masked area is regenerated (cheaper than full regen). Default-route edits to Nano Banana; GPT Image 2 when text/precise masks involved.
3. **Compose / drag-in** — drag an image onto the canvas as an edit base or style/character reference. No cost until generate.

## 11. Cost discipline

- **Cheapest viable tier + single image** by default; hi-res / `quality:high` / batch-N require explicit escalation.
- **Subscription cost model** by default (delegation uses existing Codex/Gemini auth — incremental images effectively included for this user).
- **Progressive disclosure** — `SKILL.md` carries the routing table + command contract inline (zero reference reads for the decision); load only the chosen model's reference + matched domain mode.
- **Studio runs outside the agent loop** (≈0 session tokens); director chat uses a persistent session / cheap model; editing prefers masked partial edits over full regen.

## 12. Trust & safety (improvements over banana)

- **No MCP, no settings-file mutation** → portable across the trifecta.
- **No keys by default** (delegation). When the API fallback is used, keys come from `GEMINI_API_KEY` / `OPENAI_API_KEY` **env vars** — never written to settings, never sent to the browser.
- **Localhost-only** studio bind.
- **Pinned dependency/CLI expectations**; `validate_setup.py` verifies presence + auth before use.
- **File-existence validation** before claiming success (kept from banana).

## 13. Directory structure

```
~/.agents/skills/claude.img/
  SKILL.md                      # concise: routing table + command contract inline
  docs/
    DESIGN.md                   # this file
  references/
    model-selection.md
    prompt-engineering.md
    nano-banana.md
    gpt-image.md
    presets.md
    cost-tracking.md
  scripts/
    core.py
    gemini_runner.py  codex_runner.py
    gemini_api.py     openai_api.py
    edit.py  batch.py  presets.py  cost_tracker.py
    serve.py  validate_setup.py
  assets/
    studio.html
```

## 14. Build phases (one spec, incremental delivery)

- **Phase 1 — Engine.** `core.py`, both delegation runners, both API fallbacks, routing, `cost_tracker.py`, `validate_setup.py`, `SKILL.md`, references. Usable from the agent command.
- **Phase 2 — Studio.** `serve.py` + `studio.html` prompt box + gallery; `/claude.img studio`.
- **Phase 3 — Direct + editing.** Director chat panel + editing layer (local canvas, mask-inpaint, drag-in compose).

## 15. Dependencies & setup

- **Required (delegation):** Gemini CLI + `nanobanana` extension installed and authed; Codex CLI installed and authed.
- **Optional (API fallback):** `GEMINI_API_KEY`, `OPENAI_API_KEY` in env; Python image libs (e.g. `pillow`) for local file handling.
- **Studio:** Python 3 stdlib only (no extra server deps).
- `validate_setup.py` reports what's present and which paths are available.

## 16. Open questions / risks

> **Phase 1 live verification (Task 12) resolved several of these — see notes.**

1. **Headless determinism** — CONFIRMED real: agent-mediated delegation is slower and non-deterministic. Observed live: Nano Banana hit a quota cap mid-run and the Gemini agent auto-failed-over to another engine to still deliver a file. Mitigated by the keyed fallback.
2. **Output-file location** — RESOLVED. Gemini/nanobanana saves into the **cwd** (or `./nanobanana-output/`); Codex saves into `~/.codex/generated_images/<session-uuid>/ig_*.png` (nested). Runners now run with `cwd=working_dir`, scan the right locations (codex recursively), and move the newest artifact into the working dir.
3. **Invocation flags** — RESOLVED (live). Gemini headless needs `--yolo --skip-trust` + `GEMINI_CLI_TRUST_WORKSPACE=true`, and must drive the MCP tool **directly** (the `/generate` slash command's sandboxed sub-agent cannot reach it). Codex needs `--skip-git-repo-check` and `stdin=DEVNULL`.
4. **Mask support via delegation** — still open: confirm nanobanana edit and Codex `image_gen` accept masks headlessly; if not, route masked edits through the API path. (Editing layer is Phase 3.)
5. **CLI/version drift** — extension/CLI updates may change command surface; `validate_setup.py` should fail loudly with guidance.
6. **Model IDs/pricing** — RESOLVED. Nano Banana = `gemini-3.1-flash-image-preview` (extension-managed; do not force a stale id); GPT Image 2 = `gpt-image-2`. Per-image pricing N/A on the subscription delegation path (cost logged as `$0.0`, source = subscription).
6. **Git** — RESOLVED: per-skill repo model. `claude.img` gets its own `git init` (plan Task 1) for portability/publishing, and is registered as a **submodule** in a top-level backup repo at `~/.agents/skills/` (which also pins the existing nested repos: `html-slides`, `power-design`, `squirrelscan`). Note: submodules pin versions, not content — true off-machine backup requires a remote + push per repo.
7. **Command name with a dot** — `/claude.img` is the user's chosen name, but skill/command identifiers are conventionally kebab-case and a `.` may not be a valid slash-command identifier in every host (Claude Code, Antigravity, Codex). Implementation must verify the dot is accepted across the trifecta; if not, fall back to an alias (e.g. directory `claude-img` / command `/claude-img`) while keeping `/claude.img` as the display name.

## 17. References

- OpenAI Codex CLI features — https://developers.openai.com/codex/cli/features
- gpt-image-2 announcement — https://community.openai.com/t/introducing-gpt-image-2-available-today-in-the-api-and-codex/1379479
- Gemini CLI headless mode — https://google-gemini.github.io/gemini-cli/docs/cli/headless.html
- Gemini CLI nanobanana extension — https://github.com/gemini-cli-extensions/nanobanana
- Nano Banana image generation (Gemini API) — https://ai.google.dev/gemini-api/docs/image-generation
- Source skill (banana) — https://github.com/AgriciDaniel/banana-claude/tree/main/skills/banana
