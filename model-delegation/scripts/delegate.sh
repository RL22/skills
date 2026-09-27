#!/usr/bin/env bash
# delegate.sh - agent-agnostic model delegation router.
# Fronts claude / agy / codex with one routing, safety, digest and timeout policy.
# Works whichever CLI is driving; never delegates a task back to the driver.
set -uo pipefail

VERSION="1.4.0"
SELF="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROUTE_LOOKUP="$SCRIPT_DIR/route_lookup.py"

# ---------- exit codes (uniform across executors) ----------
EX_USAGE=2      # bad invocation
EX_EMPTY=3      # executor exited 0 with no output (usually quota/auth)
EX_NOEXEC=4     # required CLI not on PATH
EX_TIMEOUT=12   # wall-clock guard fired

die() { printf '%s: %s\n' "$SELF" "$1" >&2; exit "${2:-$EX_USAGE}"; }

# ---------- pre-flight task promotion helpers ----------
# read-only tasks (reason/review/search/bulk/cheap/media) sometimes get asked, in
# the free-form prompt, to persist a file - the sandbox rejects the write. Map each read
# task to its write-capable sibling so it can be promoted deterministically before execution.
escalate_target() {
  case "$1" in
    reason|review|audit)     echo implement ;;
    search|bulk|cheap|media) echo scaffold ;;
    *)                       echo "" ;;
  esac
}
# Pull filenames out of the prompt, but only ones preceded (within ~60 chars) by
# a write-intent verb - a bare filename mention ("read plan.md for context") must
# not be treated as a promised output, or every read task false-positives.
# NOTE: do not split on "." as a sentence delimiter - filenames contain literal
# dots (e.g. "test-escalation.md"), and splitting on "." shears the extension
# off the match before the regex ever sees it. Scan the whole string instead.
extract_candidate_files() {
  printf '%s' "$1" | tr '\n' ' ' | awk '
    {
      text = $0
      start = 1
      while (match(substr(text, start), /[A-Za-z0-9_.\/-]+\.[A-Za-z0-9]{1,8}|Makefile/)) {
        abs_start = start + RSTART - 1
        fname = substr(text, abs_start, RLENGTH)
        win_start = abs_start - 60; if (win_start < 1) win_start = 1
        window = tolower(substr(text, win_start, abs_start - win_start))
        gsub(/(do not|don\047t|dont|never)[[:space:]]+(write|save|create|persist|output)/, "", window)
        if (window ~ /(^|[[:space:][:punct:]])(write|save|create|persist|output)([[:space:][:punct:]]|$)/) print fname
        start = abs_start + RLENGTH
      }
    }' | sort -u
}
file_mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null; }

# ---------- routing table ----------
# Lives in routes.json next to this script (edit that, not this file), validated
# and resolved by route_lookup.py. v1.4.0+: this used to be a pipe-delimited
# ROUTES string parsed here with `IFS='|' read`, which meant three separate
# parsing sites (this file's --list loop, lookup_route(), and a hard-coded
# field-count assertion) had to be updated in lockstep for every new column,
# and a malformed row failed silently or off-by-one instead of loudly. The
# JSON file is schema-validated once, at load time, by route_lookup.py -
# see that script's module docstring for the exact field semantics (model
# pinning, effort inheritance, mode, and the fallback policy).
command -v python3 >/dev/null 2>&1 || die "python3 not found on PATH (required for route_lookup.py)" $EX_NOEXEC
[ -f "$ROUTE_LOOKUP" ] || die "route_lookup.py not found next to $SELF: $ROUTE_LOOKUP"

# WHICH IMAGE ROUTE: symbols and structure -> image-text (GPT). Light, matter and
# continuity -> image (Nano Banana). Legible copy, exact prices, geometric lines,
# grid alignment, numbered callouts are GPT's. Light bounce, fabric drape, skin and
# hair, multi-reference composition, character consistency are Nano Banana's.
# Full per-vertical matrix: references/image-routing.md.
#
# `image` pins gemini-3.1-pro-high on purpose. agy's generate_image inherits the
# SESSION model tier, so omitting --model silently served the NB2-lite default;
# naming the Pro model forces Nano Banana Pro (observed: ~725KB output vs ~118KB
# on the lite default for a comparable prompt).
#
# The codex routes still take no image model - codex owns that internally, and
# naming one fails. `image-alt` is the old name for `image-text`, kept as an alias.
# agy has a NATIVE `generate_image` tool (verified live - unprefixed in its tool
# list, works with NANOBANANA_API_KEY unset, so the installed nanobanana MCP
# extension is not what serves this route). codex generates through its own
# tooling into the isolated runtime cache, which is promoted into --dir.

# ---------- defaults ----------
TASK=""; TO=""; DIR=""; MODEL=""; EFFORT=""; PROMPT=""
DIGEST=-1; DIGEST_EXPLICIT=-1; JSON=0; TIMEOUT=600; DRY=0
DIGEST_WARN=${DELEGATE_DIGEST_WARN:-6000}
AUTO_ESCALATE=${DELEGATE_AUTO_ESCALATE:-1}   # 1 = retry read-only write-rejections as the write-capable sibling task

usage() {
  cat <<EOF
$SELF v$VERSION - route a task to the right model, from any agent CLI.

USAGE
  $SELF --task <type> [options] "prompt"
  echo "prompt" | $SELF --task <type> [options]

TASKS
  search     live web + citations        -> agy   gemini-3.1-pro-high    (pinned)
  bulk       map/read a large tree       -> agy   gemini-3.7-flash-high  (digest on)
  cheap      trivial transforms          -> agy   gemini-3.7-flash-low
  media      audio/video/image           -> agy   gemini-3.7-flash-high
  scaffold   boilerplate, test gen       -> agy   gemini-3.7-flash-high  (writes)
  review     independent code review     -> codex gpt-5.6-sol            (read-only)
  reason     hard reasoning / skeptic    -> codex gpt-5.6-sol            (read-only)
  audit      deep reasoning / arch       -> claude claude-opus-4-6       (read-only)
  implement  code you won't hand-write   -> codex gpt-5.6-sol            (workspace-write)
  summarize  cheap bulk summarizing      -> claude claude-haiku-4-5      (digest on)
  draft      mid-tier drafting           -> claude claude-sonnet-5
  image      generate an image           -> agy   native generate_image  (writes a file)
  image-alt  generate an image (GPT)     -> codex own image tooling      (writes a file)

OPTIONS
  --to <agy|codex|claude>  override the routed executor
  --dir <path>             grant the executor a workspace (default: cwd for file tasks)
  --model <id>             override the routed model
  --effort <low|medium|high>  override the routed reasoning effort
  --digest / --no-digest   force the digest-only output contract on or off
  --json                   machine-readable envelope on stdout
  --timeout <sec>          wall-clock guard (default $TIMEOUT)
  --no-auto-escalate       disable the write-rejection auto-retry (see AUTO-ESCALATION)
  --dry-run                print the resolved command, run nothing
  --list                   print the routing matrix and exit
  -h, --help               this text

AUTO-PROMOTION
  Read-only tasks (reason, review, search, bulk, cheap, media) run in a sandbox
  that cannot write files. If the prompt asks one of them to save output to a
  file (e.g. "write the plan to plan.md"), $SELF deterministically promotes
  the task to its write-capable sibling (reason/review -> implement,
  search/bulk/cheap/media -> scaffold) before execution. Disable with
  --no-auto-escalate or DELEGATE_AUTO_ESCALATE=0 for pure analysis calls where
  no output should ever be written.

ENV
  DELEGATE_DRIVER          force driver identity (claude|codex|agy) instead of autodetect
  DELEGATE_DIGEST_WARN     chars before a dump-size warning (default 6000)
  DELEGATE_AUTO_ESCALATE   0 disables the write-rejection auto-retry (default 1)
  DELEGATE_<TASK>_MODEL    per-task model override, e.g. DELEGATE_REVIEW_MODEL=gpt-5.6-sol
  DELEGATE_<TASK>_EFFORT   per-task effort override, e.g. DELEGATE_BULK_EFFORT=low

Edit routes.json (next to this script) to change defaults permanently.
EOF
}

# ---------- arg parsing ----------
[ $# -eq 0 ] && { usage; exit $EX_USAGE; }
while [ $# -gt 0 ]; do
  case "$1" in
    --task)    TASK="${2:-}"; shift 2 ;;
    --to)      TO="${2:-}"; shift 2 ;;
    --dir)     DIR="${2:-}"; shift 2 ;;
    --model)   MODEL="${2:-}"; shift 2 ;;
    --effort)  EFFORT="${2:-}"; shift 2 ;;
    --no-digest) DIGEST=0; DIGEST_EXPLICIT=0; shift ;;
    --timeout) TIMEOUT="${2:-}"; shift 2 ;;
    --digest)  DIGEST=1; DIGEST_EXPLICIT=1; shift ;;
    --json)    JSON=1; shift ;;
    --no-auto-escalate) AUTO_ESCALATE=0; shift ;;
    --dry-run) DRY=1; shift ;;
    --list)    TASK="__list__"; shift ;;
    -h|--help) usage; exit 0 ;;
    --)        shift; PROMPT="$*"; break ;;
    -*)        die "unknown option: $1" ;;
    *)         PROMPT="${PROMPT:+$PROMPT }$1"; shift ;;
  esac
done

if [ "$TASK" = "__list__" ]; then
  python3 "$ROUTE_LOOKUP" --list
  exit $?
fi

[ -n "$TASK" ] || die "--task is required (see --list)"
case "$TO" in ''|agy|codex|claude) : ;; *) die "--to must be agy, codex, or claude" ;; esac
case "$EFFORT" in ''|low|medium|high) : ;; *) die "--effort must be low, medium, or high" ;; esac
case "$TIMEOUT" in ''|*[!0-9]*) die "--timeout must be a positive integer" ;; esac
[ "$TIMEOUT" -gt 0 ] 2>/dev/null || die "--timeout must be a positive integer"
[ -z "$DIR" ] || [ -d "$DIR" ] || die "--dir is not a directory: $DIR"
# prompt from stdin when not given as an argument
if [ -z "$PROMPT" ]; then
  [ -t 0 ] && die "no prompt given (argument or stdin)"
  PROMPT="$(cat)"
fi
[ -n "$PROMPT" ] || die "empty prompt"
ORIG_PROMPT="$PROMPT"   # snapshot before --digest/image wrap it, for escalation file-scanning

# ---------- driver detection (never delegate to yourself) ----------
detect_driver() {
  [ -n "${DELEGATE_DRIVER:-}" ] && { echo "$DELEGATE_DRIVER"; return; }
  [ -n "${CLAUDECODE:-}" ] && { echo claude; return; }
  [ -n "${CODEX_HOME:-}${CODEX_SANDBOX:-}${CODEX_THREAD_ID:-}" ] && { echo codex; return; }
  [ -n "${AGY_SESSION:-}${ANTIGRAVITY_CLI:-}" ] && { echo agy; return; }
  echo unknown
}
DRIVER="$(detect_driver)"

# ---------- routing (resolved from routes.json by route_lookup.py) ----------
mapfile -t _R < <(python3 "$ROUTE_LOOKUP" --task "$TASK") || die "unknown task: $TASK (see --list)"
[ "${#_R[@]}" -eq 6 ] || die "unknown task: $TASK (see --list)"
EXEC="${_R[0]}"; DEF_MODEL="${_R[1]}"; DEF_EFFORT="${_R[2]}"; MODE="${_R[3]}"
# A trailing "!" on the executor pins it: never reroute, even when it matches the
# driver. Used for intra-vendor tier downshifts (Opus driving -> Haiku executing),
# which are a different model and so are not self-delegation.
NOREROUTE=0
case "$EXEC" in *!) EXEC="${EXEC%!}"; NOREROUTE=1 ;; esac
[ "$DIGEST" -eq -1 ] && DIGEST="${_R[4]:-0}"
FALLBACK="${_R[5]:-stop}"
FB_EXEC=""; FB_MODEL=""
if [ "$FALLBACK" != stop ]; then
  FB_EXEC="${FALLBACK%%:*}"; FB_MODEL="${FALLBACK#*:}"
  [ -n "$FB_EXEC" ] && [ -n "$FB_MODEL" ] && [ "$FB_EXEC" != "$FALLBACK" ] \
    || die "malformed fallback route for task $TASK: $FALLBACK"
fi

# per-task env overrides: DELEGATE_<TASK>_MODEL / DELEGATE_<TASK>_EFFORT
_UT="$(printf '%s' "$TASK" | tr '[:lower:]-' '[:upper:]_')"
eval "_EM=\${DELEGATE_${_UT}_MODEL:-}"; eval "_EF=\${DELEGATE_${_UT}_EFFORT:-}"
[ -n "$_EM" ] && DEF_MODEL="$_EM"
[ -n "$_EF" ] && DEF_EFFORT="$_EF"

MODEL_EXPLICIT="$MODEL"
EFFORT_EXPLICIT="$EFFORT"
TO_EXPLICIT="$TO"
[ -n "$TO" ] && EXEC="$TO"

# self-delegation guard: only judgment/verdict tasks are guarded against being
# graded by the same model that authored the work. A driver launching a
# same-CLI subagent to *do* non-adversarial work (bulk, cheap, media, scaffold,
# implement, ...) is normal fan-out, not self-delegation, so it is left alone.
JUDGE_TASK=0
case "$TASK" in
  review|reason|audit) JUDGE_TASK=1 ;;
esac

if [ "$EXEC" = "$DRIVER" ] && [ -z "$TO" ] && [ "$NOREROUTE" -eq 0 ] && [ "$JUDGE_TASK" -eq 1 ]; then
  case "$DRIVER" in
    agy)    EXEC=codex;  DEF_MODEL="" ;;
    codex)  EXEC=claude; DEF_MODEL=claude-opus-4-6 ;;
    claude) EXEC=codex;  DEF_MODEL=gpt-5.6-sol ;;
  esac
  printf '%s: driver is %s; rerouted skeptic task %s -> %s (judgment must come from a distinct model)\n' \
    "$SELF" "$DRIVER" "$TASK" "$EXEC" >&2
fi
# a --to override can land a foreign model id on an executor; normalize per executor
case "$EXEC" in
  claude) case "$DEF_MODEL" in ''|gpt*|gemini*) DEF_MODEL=claude-sonnet-5 ;; esac ;;
  codex)  case "$DEF_MODEL" in gemini*|sonnet|opus*) DEF_MODEL="" ;; esac ;;
  agy)    case "$DEF_MODEL" in ''|gpt-5*|sonnet|opus*) DEF_MODEL=gemini-3.7-flash-high ;; esac ;;
esac
MODEL="${MODEL:-$DEF_MODEL}"
EFFORT="${EFFORT:-$DEF_EFFORT}"

# Reject only model ids that are unambiguously foreign to the chosen executor.
# Unknown ids remain allowed so newly released models do not require a router update.
if [ -n "$MODEL_EXPLICIT" ]; then
  case "$EXEC:$MODEL_EXPLICIT" in
    claude:gpt*|claude:gemini*)
      die "model '$MODEL_EXPLICIT' is incompatible with executor claude" ;;
    codex:gemini*|codex:claude*|codex:sonnet|codex:sonnet-*|codex:opus*|codex:haiku*)
      die "model '$MODEL_EXPLICIT' is incompatible with executor codex" ;;
    agy:gpt-5*|agy:claude*|agy:sonnet|agy:sonnet-*|agy:opus*|agy:haiku*)
      die "model '$MODEL_EXPLICIT' is incompatible with executor agy" ;;
  esac
  if [ "$EXEC" = codex ] && [ "$MODE" = image ]; then
    die "Codex image routes choose their image model internally; omit --model"
  fi
fi

# agy has no effort flag - effort lives in the model id suffix, so rewrite it
if [ "$EXEC" = agy ] && [ -n "$EFFORT" ]; then
  case "$MODEL" in *-high|*-medium|*-low) MODEL="${MODEL%-*}-${EFFORT}" ;; esac
fi

command -v "$EXEC" >/dev/null 2>&1 || die "$EXEC not found on PATH" $EX_NOEXEC

# ---------- pre-flight task promotion (deterministic) ----------
# Read-only tasks cannot write files. We scan the prompt after routing resolution.
# If it explicitly asks to write a file, we elevate the sandbox to its write-capable
# sibling's mode, preserving the original executor and model semantics.
CANDIDATES=()
if [ "$AUTO_ESCALATE" -eq 1 ] && [ "$MODE" != write ] && [ "$MODE" != image ]; then
  _TARGET="$(escalate_target "$TASK")"
  if [ -n "$_TARGET" ]; then
    mapfile -t CANDIDATES < <(extract_candidate_files "$ORIG_PROMPT")
    if [ "${#CANDIDATES[@]}" -gt 0 ]; then
      printf '%s: read-only task %s asked to write [%s]; promoting sandbox mode before execution\n' \
        "$SELF" "$TASK" "${CANDIDATES[*]}" >&2
      ESCALATED_FROM="$TASK"
      TASK="$_TARGET"
      MODE="write"
      # FB_EXEC/FB_MODEL were resolved for the pre-escalation task (bulk/cheap's own
      # fallback), not this one. A promoted task now writes to the caller's --dir, and
      # a mutating task must be stop-only regardless of what its read-only origin
      # declared - never let auto-escalation smuggle a write-mode call into a fallback.
      FB_EXEC=""; FB_MODEL=""
    fi
  fi
fi

# ---------- isolated runtime ----------
# A nested `codex exec --ephemeral` still opens CODEX_HOME/state_5.sqlite. When
# the driver is Codex, the parent sandbox exposes that database read-only and the
# child fails before it can contact the model. Give every live call a private
# runtime directory; Codex gets a writable shadow home with private auth/config
# copies and links to static skills/rules. The directory also owns stderr, so concurrent
# delegate calls cannot overwrite one another's diagnostics.
DELEGATE_RUN_DIR=""
CODEX_RUNTIME_DIR=""
CODEX_CONFIG_ROOT="${CODEX_HOME:-$HOME/.codex}"
cleanup_runtime() {
  local runtime="$DELEGATE_RUN_DIR"
  DELEGATE_RUN_DIR=""
  [ -n "$runtime" ] && [ -d "$runtime" ] && rm -rf -- "$runtime"
}
make_runtime_dir() {
  local base dir
  local -a candidates=()

  [ -n "${TMPDIR:-}" ] && candidates+=("${TMPDIR}")
  candidates+=(/var/tmp /tmp)

  for base in "${candidates[@]}"; do
    case "$base" in
      /*) ;;
      *) continue ;;
    esac
    [ -d "$base" ] || continue

    dir="$(
      umask 077
      mktemp -d "${base%/}/delegate.XXXXXX" 2>/dev/null
    )" || continue
    [ -d "$dir" ] || continue

    if ! chmod 700 "$dir" 2>/dev/null; then
      rmdir "$dir" 2>/dev/null || :
      continue
    fi

    printf '%s\n' "$dir"
    return 0
  done

  return 1
}
terminate_runtime() {
  local status="$1"
  trap - EXIT HUP INT TERM
  cleanup_runtime
  exit "$status"
}
if [ "$DRY" -eq 1 ]; then
  DELEGATE_RUN_DIR="<runtime>"
else
  DELEGATE_RUN_DIR="$(make_runtime_dir)" \
    || die "could not create isolated runtime directory"
  chmod 700 "$DELEGATE_RUN_DIR" || { cleanup_runtime; die "could not secure isolated runtime directory"; }
  trap cleanup_runtime EXIT
  trap 'terminate_runtime 129' HUP
  trap 'terminate_runtime 130' INT
  trap 'terminate_runtime 143' TERM
fi
ERR_FILE="$DELEGATE_RUN_DIR/stderr"

# ---------- image instruction ----------
# An image task needs an explicit tool instruction, not a bare subject line: handed
# the raw prompt, agy answers in prose and writes nothing. Verified the hard way -
# a --dry-run only proves the command was built, never that it generated anything.
if [ "$MODE" = image ]; then
  PROMPT="Use the generate_image tool to create exactly one image. Save the image file into the current working directory. Do not reply with a description instead of calling the tool.

---

${PROMPT}"
fi

# ---------- output contract ----------
if [ "$DIGEST" -eq 1 ]; then
  PROMPT="$PROMPT

OUTPUT CONTRACT: reply with a compressed digest only - findings with file:line
references, no file dumps, no restating the prompt. Hard cap ~400 words."
fi

# ---------- wall-clock guard ----------
GUARD=""
if command -v gtimeout >/dev/null 2>&1; then GUARD="gtimeout $TIMEOUT"
elif command -v timeout >/dev/null 2>&1; then GUARD="timeout $TIMEOUT"
else printf '%s: warning - no timeout/gtimeout; running unguarded\n' "$SELF" >&2; fi

# ---------- build the executor command ----------
# A function, not inline, so a fallback retry (EXEC/MODEL reassigned) can rebuild
# CMD for the new executor without duplicating this ~60-line case statement.
WORKDIR="${DIR:-$PWD}"
build_cmd() {
CMD=()
case "$EXEC" in
  agy)
    # image mode MUST pass --model: generate_image inherits the session model tier,
    # so an unset model silently serves the NB2-lite default instead of Pro.
    CMD=(agy --model "$MODEL" --add-dir "$WORKDIR")
    case "$MODE" in
      read)  CMD+=(--sandbox) ;;
      web)   CMD+=(--sandbox --dangerously-skip-permissions) ;;  # web tools need approval bypass; sandbox keeps the fs floor
      write) CMD+=(--dangerously-skip-permissions) ;;            # run on a branch; verify with git status
      image) CMD+=(--dangerously-skip-permissions) ;;            # tool call approval + writes the image file
    esac
    CMD+=(--print "$PROMPT")
    ;;
  codex)
    # per-task ceiling - never inherits danger-full-access from ~/.codex/config.toml
    case "$MODE" in
      read|web)    SBX=read-only ;;
      write|image) SBX=workspace-write ;;   # image generation writes a file
    esac
    # Pass the resolved route model explicitly; image routes intentionally leave it empty.
    # --cd is what makes --dir mean anything here. Without it codex runs in the
    # caller's cwd, so an `implement` task reported success while writing its file
    # somewhere the caller never looked.
    CODEX_RUNTIME_DIR="$DELEGATE_RUN_DIR/codex-home"
    if [ "$DRY" -eq 0 ]; then
      mkdir -p "$CODEX_RUNTIME_DIR" || die "could not create isolated Codex runtime"
      for item in auth.json config.toml; do
        if [ -f "$CODEX_CONFIG_ROOT/$item" ]; then
          cp "$CODEX_CONFIG_ROOT/$item" "$CODEX_RUNTIME_DIR/$item" \
            || die "could not isolate Codex $item"
          chmod 600 "$CODEX_RUNTIME_DIR/$item" \
            || die "could not protect isolated Codex $item"
        fi
      done
      for item in skills rules; do
        if [ -e "$CODEX_CONFIG_ROOT/$item" ]; then
          ln -s "$CODEX_CONFIG_ROOT/$item" "$CODEX_RUNTIME_DIR/$item" \
            || die "could not link Codex $item"
        fi
      done
    fi
    CMD=(env "CODEX_HOME=$CODEX_RUNTIME_DIR" codex exec --ephemeral \
      --sandbox "$SBX" --skip-git-repo-check --cd "$WORKDIR")
    # config.toml sets model_reasoning_effort=low globally; that is right for interactive
    # use and wrong for a `reason`/`review` delegation, so raise it per task.
    [ -n "$EFFORT" ] && CMD+=(-c model_reasoning_effort="$EFFORT")
    [ -n "$MODEL" ] && CMD+=(-c model="$MODEL")
    CMD+=(-)
    ;;
  claude)
    # Anthropic ships no image-generation model - fail loud rather than let a
    # --to claude override silently produce a text description of a picture.
    [ "$MODE" = image ] && die "claude cannot generate images; use --task image (agy) or image-alt (codex)"
    CMD=(claude -p --model "$MODEL" --add-dir "$WORKDIR")
    [ -n "$EFFORT" ] && CMD+=(--effort "$EFFORT")
    case "$MODE" in
      read|web) CMD+=(--disallowedTools "Write Edit NotebookEdit") ;;
      write)    CMD+=(--permission-mode acceptEdits) ;;
    esac
    ;;
  *) die "unknown executor: $EXEC" ;;
esac
}
build_cmd

if [ "$DRY" -eq 1 ]; then
  printf 'driver=%s executor=%s model=%s mode=%s timeout=%s\n' "$DRIVER" "$EXEC" "$MODEL" "$MODE" "$TIMEOUT"
  printf 'cmd: %s%s\n' "${GUARD:+$GUARD }" "${CMD[*]}"
  exit 0
fi

# ---------- run (with an optional one-shot evaluated fallback) ----------
IMAGE_MARKER=""
if [ "$MODE" = image ]; then
  IMAGE_MARKER="$DELEGATE_RUN_DIR/image-start"
  : > "$IMAGE_MARKER" || die "could not create image-run marker"
fi
run_once() {
  RETRIES=0
  while :; do
    if [ "$EXEC" = agy ]; then
      OUT="$($GUARD "${CMD[@]}" 2>"$ERR_FILE" </dev/null)"; RC=$?
    else
      OUT="$(printf '%s' "$PROMPT" | $GUARD "${CMD[@]}" 2>"$ERR_FILE")"; RC=$?
    fi
    if [ "$RC" -ne 0 ] && [ "$RETRIES" -eq 0 ] && grep -q "moderation_blocked" "$ERR_FILE" 2>/dev/null && grep -q "output" "$ERR_FILE" 2>/dev/null; then
      RETRIES=1
      continue
    fi
    break
  done
}
START=$(date +%s)
run_once
FALLBACK_USED=0
PRIMARY_EXEC="$EXEC"; PRIMARY_MODEL="$MODEL"
# Fallback triggers on exactly the two failure shapes classified below (timeout,
# empty output) - never on a usage error, and never for image mode (the artifact-
# promotion logic below assumes a single attempt). One retry only: FB_EXEC is
# never itself given a fallback, so this cannot chain or loop.
if [ "$MODE" != image ] && [ -n "$FB_EXEC" ]; then
  FAILED=0
  [ "$RC" -eq 124 ] && FAILED=1
  [ -z "${OUT//[[:space:]]/}" ] && FAILED=1
  # Fallback only ever applies to bulk/cheap (non-judgment, output-is-consumed
  # tasks - see routes.json), so landing on the driver's own CLI here is normal
  # fan-out, not self-delegation; rule 1's judge-only guard doesn't apply. Still
  # skip if the fallback target is identical to the primary attempt's
  # executor+model (e.g. an explicit --to already matches the declared
  # fallback) - retrying that would just repeat the identical failing call.
  # Also skip if the fallback executor is the driver itself - same
  # self-delegation guard as rule 1, applied to the fallback path.
  if [ "$FAILED" -eq 1 ] \
     && { [ "$FB_EXEC" != "$PRIMARY_EXEC" ] || [ "$FB_MODEL" != "$PRIMARY_MODEL" ]; } \
     && [ "$FB_EXEC" != "$DRIVER" ] \
     && command -v "$FB_EXEC" >/dev/null 2>&1; then
    printf '%s: %s failed on %s (rc=%s); falling back once to %s/%s\n' \
      "$SELF" "$TASK" "$PRIMARY_EXEC" "$RC" "$FB_EXEC" "$FB_MODEL" >&2
    EXEC="$FB_EXEC"; MODEL="$FB_MODEL"
    if [ "$EXEC" = agy ] && [ -n "$EFFORT" ]; then
      case "$MODEL" in *-high|*-medium|*-low) : ;; *) MODEL="${MODEL}-${EFFORT}" ;; esac
    fi
    build_cmd
    run_once
    FALLBACK_USED=1
  fi
fi
DUR=$(( $(date +%s) - START ))

# ---------- normalized failure envelope (--json only; text output is unchanged) ----------
# Successful calls have always had a structured --json contract; failures previously
# just dumped raw stderr even under --json, so a caller parsing JSON had nothing to
# parse on the failure path. Same field names as the success envelope below, with
# text always null and error carrying what stderr already printed.
error_excerpt() {
  local errsum
  errsum="$(grep -iE 'error|denied|limit|quota|auth|refus' "$ERR_FILE" 2>/dev/null | tail -5)"
  [ -n "$errsum" ] || errsum="$(tail -10 "$ERR_FILE" 2>/dev/null)"
  printf '%s' "$errsum"
}
emit_json_failure() {
  local code="$1"
  error_excerpt | python3 -c 'import json,sys
e,m,t,d,efrom,fb = sys.argv[1:7]
print(json.dumps({"success": False,"executor":e,"model":m,"task":t,
                  "duration_seconds":int(d),"text":None,
                  "escalated_from":efrom or None,
                  "fallback_used": fb == "1",
                  "error":sys.stdin.read().strip() or None}))' \
    "$EXEC" "$MODEL" "$TASK" "$DUR" "${ESCALATED_FROM:-}" "$FALLBACK_USED"
  exit "$code"
}

# ---------- classify ----------
if [ "$RC" -eq 124 ]; then
  printf '%s: TIMEOUT after %ss on %s\n' "$SELF" "$TIMEOUT" "$EXEC" >&2
  [ "$JSON" -eq 1 ] && emit_json_failure $EX_TIMEOUT
  exit $EX_TIMEOUT
fi
# ---------- image artifacts ----------
# An image run's real output is a file, not stdout. Locate what it produced and
# report the path, so an empty-ish stdout isn't mistaken for a failed run.
if [ "$MODE" = image ] && [ "$RC" -eq 0 ]; then
  # Always prefer the copy in --dir. Codex may first write into its private runtime
  # cache; promote that artifact before cleanup so every reported path remains valid.
  find_img() {
    local root="$1" depth="${2:-2}" candidate newest="" newest_mtime=-1 mtime
    [ -d "$root" ] || return 0
    while IFS= read -r -d '' candidate; do
      [ -s "$candidate" ] || continue
      mtime="$(file_mtime "$candidate")" || continue
      if [ "$mtime" -gt "$newest_mtime" ] \
         || { [ "$mtime" -eq "$newest_mtime" ] && [[ "$candidate" > "$newest" ]]; }; then
        newest="$candidate"
        newest_mtime="$mtime"
      fi
    done < <(find "$root" -maxdepth "$depth" -type f -newer "$IMAGE_MARKER" \
      \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' \) \
      -print0 2>/dev/null)
    printf '%s' "$newest"
  }
  ART="$(find_img "$WORKDIR")"
  ART_SRC="--dir"
  if [ -z "$ART" ] && [ "$EXEC" = codex ]; then
    ART="$(find_img "$CODEX_RUNTIME_DIR/generated_images" 3)"
    if [ -n "$ART" ]; then
      # The private runtime is removed on exit, so promote its image cache into
      # the requested workspace before reporting a path to the caller.
      RUNTIME_ART="$ART"
      ART="$WORKDIR/delegate-image-${START}-$$.${RUNTIME_ART##*.}"
      cp "$RUNTIME_ART" "$ART" || die "could not promote generated image into --dir"
      [ -s "$ART" ] || die "promoted image is empty"
    else
      ART="$(find_img "$CODEX_CONFIG_ROOT/generated_images" 3)"
      ART_SRC="codex cache"
    fi
  fi
  if [ -n "$ART" ]; then
    if [ "$ART_SRC" = "--dir" ]; then
      printf '%s: image written: %s\n' "$SELF" "$ART" >&2
    else
      printf '%s: image written: %s (nothing landed in --dir; this is the %s)\n' \
        "$SELF" "$ART" "$ART_SRC" >&2
    fi
    OUT="${OUT}${OUT:+
}IMAGE: $ART"
  else
    printf '%s: %s reported success but no image file was found\n' "$SELF" "$EXEC" >&2
    exit $EX_EMPTY
  fi
fi

if [ -z "${OUT//[[:space:]]/}" ]; then
  # never fail silently - an empty reply is useless without the executor's reason,
  # whether it exited 0 (quota/auth) or non-zero (upstream error)
  if [ "$RC" -eq 0 ]; then
    printf '%s: %s exited 0 with no output (quota or auth?). stderr:\n' "$SELF" "$EXEC" >&2
  else
    printf '%s: %s failed (rc=%s) with no output. stderr:\n' "$SELF" "$EXEC" "$RC" >&2
  fi
  grep -iE 'error|denied|limit|quota|auth|refus' "$ERR_FILE" | tail -5 >&2 || tail -10 "$ERR_FILE" >&2
  if [ "$JSON" -eq 1 ]; then
    [ "$RC" -eq 0 ] && emit_json_failure $EX_EMPTY
    emit_json_failure "$RC"
  fi
  [ "$RC" -eq 0 ] && exit $EX_EMPTY
  exit "$RC"
fi

# ---------- post-run artifact check ----------
# If the task was promoted to write mode because the prompt promised to write files,
# verify that it actually did. If no candidate file was written, fail the job.
if [ -n "${ESCALATED_FROM:-}" ] && [ "$RC" -eq 0 ] && [ "${#CANDIDATES[@]}" -gt 0 ]; then
  UNWRITTEN=1
  for f in "${CANDIDATES[@]}"; do
    fp="$f"; case "$f" in /*) : ;; *) fp="$WORKDIR/$f" ;; esac
    if [ -e "$fp" ]; then
      mt="$(file_mtime "$fp")"
      [ -n "$mt" ] && [ "$mt" -ge "$START" ] && UNWRITTEN=0
    fi
  done
  if [ "$UNWRITTEN" -eq 1 ]; then
    printf '%s: %s reported success but named output [%s] was not written\n' \
      "$SELF" "$TASK" "${CANDIDATES[*]}" >&2
    exit $EX_EMPTY
  fi
fi

if [ "$DIGEST" -eq 1 ] && [ "${#OUT}" -gt "$DIGEST_WARN" ]; then
  printf '%s: warning - digest requested but reply is %s chars (dump-sized)\n' "$SELF" "${#OUT}" >&2
fi

if [ "$JSON" -eq 1 ]; then
  # RC can be nonzero here with nonempty OUT (an executor that wrote partial output
  # before exiting nonzero) - populate error in that case too, so success:false never
  # ships with error:null. Only a clean RC=0 gets a null error.
  JSON_ERR=""
  [ "$RC" -eq 0 ] || JSON_ERR="$(error_excerpt)"
  printf '%s' "$OUT" | python3 -c 'import json,sys
e,m,t,d,rc,efrom,fb,err = sys.argv[1:9]
print(json.dumps({"success": rc=="0","executor":e,"model":m,"task":t,
                  "duration_seconds":int(d),"text":sys.stdin.read(),
                  "escalated_from":efrom or None,
                  "fallback_used": fb == "1","error":err.strip() or None}))' \
    "$EXEC" "$MODEL" "$TASK" "$DUR" "$RC" "${ESCALATED_FROM:-}" "$FALLBACK_USED" "$JSON_ERR"
else
  printf '%s\n' "$OUT"
fi
exit "$RC"
