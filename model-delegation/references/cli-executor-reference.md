# Routing matrix — reference

Verified 2026-08-13 on macOS (darwin 25.5.0).

## Executor inventory

| CLI | Version | Headless | Model flag | Sandbox flag |
|---|---|---|---|---|
| `claude` | 2.1.204 | `-p` | `--model` | `--permission-mode`, `--allowedTools`/`--disallowedTools` |
| `agy` | 1.1.11 | `-p` / `--print` | `--model` | `--sandbox`, `--dangerously-skip-permissions` |
| `codex` | 0.147.0 | `exec` | `-c model=` | `-s/--sandbox read-only\|workspace-write\|danger-full-access` |

`agy --print-timeout` self-bounds at 5m; the `gtimeout` guard in the router is the
backstop for a hard hang, not the primary limit.

The router rejects malformed executor, effort, timeout, and directory options before
launch. Explicit model validation is conservative: it rejects known foreign provider
ids while allowing unknown ids so newly released models do not require a router update.

## Models available to agy

Confirmed from a live `agy models` call:

```
gemini-3.7-flash-high/medium/low
gemini-3.6-flash-high/medium/low
gemini-3.5-flash-high/medium/low
gemini-3.1-pro-high/low
claude-sonnet-4-6 · claude-opus-4-6-thinking
gpt-oss-120b-medium
```

**agy cannot substitute for codex.** The only GPT it exposes on this plan is
`gpt-oss-120b-medium` — open weights, not the Codex model. That is why the router
keeps a separate codex path rather than routing everything through `agy --model`.

`gemini-3.7-flash-high` is live on this plan and configured for all high-throughput Flash tasks.

## Safety ceilings, and why

`~/.codex/config.toml` on this machine sets `approval_policy = "never"` and
`sandbox_mode = "danger-full-access"`. That is a reasonable posture when a human is
driving interactively. It is not reasonable for a delegated call, where the prompt
may have been shaped by a web page or repo the driver just read.

The router passes `--sandbox` explicitly on every codex invocation, so a delegated
call can never inherit full access. Interactive codex is unaffected.

Nested Codex calls also require an isolated runtime home. `codex exec --ephemeral`
does not by itself suppress initialization of `$CODEX_HOME/state_5.sqlite`; under a
Codex driver's parent sandbox that database is read-only, so the child can fail before
model startup. The router creates a mode-0700 temporary home, copies mutable
`auth.json` and `config.toml` with mode 0600, links static `skills` and `rules`, passes
`--ephemeral`, and removes the runtime on exit. Per-run stderr lives in the same
directory, avoiding collisions between concurrent delegations.

For agy:

- `--sandbox` is the API-level filesystem floor. Prompt-level tool restrictions are
  advisory; the sandbox is not.
- Web/search tools require approval bypass in headless mode, so `search` combines
  `--dangerously-skip-permissions` (tool approval) with `--sandbox` (fs confinement).
  Bypass without the sandbox is never issued.
- Write tasks (`scaffold`) need a grant. Either a `write_file(<dir>)` entry under
  `permissions.allow` in `~/.gemini/antigravity-cli/settings.json` — the narrower
  option, recursive beneath `<dir>` — or the bypass flag. An ungranted write can
  leave the workspace untouched while the run still reports success, so verify with
  `git status` and run write tasks on a branch.

## Resolved: codex model pin (2026-08-08)

`codex-cli 0.143.0` could not serve `gpt-5.6-sol`, which `config.toml` pins globally,
and returned `400 invalid_request_error` on every CLI invocation — delegated or not.
Fixed by upgrading to 0.147.0.

**Codex is installed via npm, not brew.** `/opt/homebrew/bin/codex` is a symlink into
`../lib/node_modules/@openai/codex/bin/codex.js`, so `brew upgrade codex` fails with
"Cask 'codex' is not installed". Upgrade with:

```bash
npm install -g @openai/codex@latest
```

Every route in `routes.json` pins its model explicitly, codex included — what runs
is what is written there, with no dependency on `config.toml` drifting underneath.

The tradeoff to remember: a pinned id needs review when a vendor moves. That is exactly
what the 0.143.0 failure above was. If a codex route starts returning
`400 invalid_request_error`, check the pinned id against `codex` first.

## Reasoning effort per executor

| Executor | Mechanism |
|---|---|
| `codex` | `-c model_reasoning_effort=<low\|medium\|high>` |
| `claude` | `--effort <level>` |
| `agy` | no flag — effort is the model-id suffix, so the router rewrites `-high`/`-medium`/`-low` |

`~/.codex/config.toml` sets `model_reasoning_effort = "medium"` globally. Inheriting that on
a `reason` or `review` delegation defeats the purpose of delegating, so the router
overrides to `high` on those two paths and leaves interactive Codex alone.

`agy` example: `scaffold` is `gemini-3.6-flash-high` at `medium` effort, which resolves to
`gemini-3.6-flash-medium`. Only ids already carrying a suffix are rewritten.

## Image generation

**No Claude model generates images.** Anthropic ships vision (image *input* — 2576px,
pixel-accurate coordinates on Opus 5) but no image *output* model at any tier. `agy models`
on this plan also lists no image models. So image generation does not run through either
executor's normal model path:

| Route | Mechanism | Artifact |
|---|---|---|
| `image` | agy's **native** `generate_image` tool — no API key, no MCP extension | written under `--dir` |
| `image-text` / `image-alt` | `codex exec --ephemeral` — Codex image tooling | promoted from the private runtime cache into `--dir` |

Neither takes `--model`; naming an image model id on either fails. This is why `routes.json`
leaves both `model` fields `null` despite the pin-everything rule.

**Verified live 2026-08-08:** `agy --dangerously-skip-permissions --add-dir <dir> -p "Use the
generate_image tool …"` produced a 1024×1024 PNG with `NANOBANANA_API_KEY` **unset**.
`generate_image` appears unprefixed in agy's tool list, so it is native — the installed
`nanobanana` MCP extension at `~/.gemini/antigravity-cli/plugins/nanobanana` is **not**
what serves this route (agy's `settings.json` has an empty `mcpServers`).

`~/.agents/skills/claude.img` was migrated to this same invocation on 2026-08-08; its
`gemini_runner.py` previously shelled out to the retired `gemini` binary and hung.

## Driver detection

| Driver | Marker |
|---|---|
| claude | `CLAUDECODE=1` |
| codex | `CODEX_HOME` / `CODEX_SANDBOX` / `CODEX_THREAD_ID` |
| agy | `AGY_SESSION` / `ANTIGRAVITY_CLI` |

Override with `DELEGATE_DRIVER=<name>`. Detection failing open (`unknown`) only
disables the self-delegation guard; routing still works.

The codex and agy markers are inferred, not confirmed against a live session of
either. Verify by running `env | grep -iE '^(CODEX|AGY)'` from inside each and
correcting `detect_driver()` if they differ.
