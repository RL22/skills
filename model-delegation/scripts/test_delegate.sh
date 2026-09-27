#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROUTER="$SCRIPT_DIR/delegate.sh"
FIXTURES="$SCRIPT_DIR/tests/fixtures"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/delegate-tests.XXXXXX")"
RUNTIME_ROOT="$TEST_ROOT/runtime"
SOURCE_HOME="$TEST_ROOT/codex-home"
WORKDIR="$TEST_ROOT/work"
mkdir -p "$RUNTIME_ROOT" "$SOURCE_HOME/skills" "$SOURCE_HOME/rules" "$WORKDIR"
printf 'original-auth\n' > "$SOURCE_HOME/auth.json"
printf 'model = "test"\n' > "$SOURCE_HOME/config.toml"

cleanup() { rm -rf -- "$TEST_ROOT"; }
trap cleanup EXIT

PASS=0
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
pass() { PASS=$((PASS + 1)); printf 'ok %s - %s\n' "$PASS" "$1"; }
run_router() {
  PATH="$FIXTURES:$PATH" TMPDIR="$RUNTIME_ROOT" CODEX_HOME="$SOURCE_HOME" \
    DELEGATE_DRIVER=claude "$ROUTER" "$@"
}
assert_no_runtime() {
  local leaked
  leaked="$(find "$RUNTIME_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'delegate.*' -print -quit)"
  [ -z "$leaked" ] || fail "temporary runtime leaked: $leaked"
}

# 1. Mutable Codex inputs are private mode-0600 copies; static inputs are links.
OUT="$(MOCK_CODEX_CHECK_RUNTIME=1 run_router --task reason --no-auto-escalate --dir "$WORKDIR" runtime-check)" \
  || fail "isolated Codex runtime"
[ "$(cat "$SOURCE_HOME/auth.json")" = original-auth ] || fail "source auth was mutated"
[[ "$OUT" == *READ_ONLY* ]] || fail "runtime test did not reach executor"
assert_no_runtime
pass "isolated Codex runtime"

# 1b. An unusable inherited TMPDIR falls back and the private runtime is cleaned up.
BAD_TMPDIR="$TEST_ROOT/not-a-directory"
printf 'not a directory\n' > "$BAD_TMPDIR"
OUT="$(PATH="$FIXTURES:$PATH" TMPDIR="$BAD_TMPDIR" CODEX_HOME="$SOURCE_HOME" \
  DELEGATE_DRIVER=claude "$ROUTER" --task summarize unusable-tmpdir)" \
  || fail "unusable TMPDIR did not fall back"
[[ "$OUT" == *"CLAUDE_OK"* ]] || fail "fallback execution did not reach executor"
assert_no_runtime
pass "unusable inherited TMPDIR falls back and cleans up"

# 2. A sub-second image run selects the new non-empty artifact, not an older PNG.
printf 'old\n' > "$WORKDIR/old.png"
OUT="$(cd "$WORKDIR" && PATH="$FIXTURES:$PATH" TMPDIR="$RUNTIME_ROOT" \
  DELEGATE_DRIVER=codex "$ROUTER" --task image --dir "$WORKDIR" fast-image)" \
  || fail "image marker selection"
[[ "$OUT" == *"IMAGE: $WORKDIR/fast.png"* ]] || fail "new image was not selected"
assert_no_runtime
pass "image marker selection"

# 3. TERM cleanup exits 143 and removes the private runtime.
READY="$TEST_ROOT/signal-ready"
RELEASE="$TEST_ROOT/signal-release"
mkfifo "$READY" "$RELEASE"
set +e
PATH="$FIXTURES:$PATH" TMPDIR="$RUNTIME_ROOT" CODEX_HOME="$SOURCE_HOME" \
  DELEGATE_DRIVER=claude MOCK_CLAUDE_READY="$READY" MOCK_CLAUDE_RELEASE="$RELEASE" \
  "$ROUTER" --task summarize --timeout 5 signal-test >/dev/null 2>&1 &
ROUTER_PID=$!
IFS= read -r _ < "$READY"
kill -TERM "$ROUTER_PID"
printf 'release\n' > "$RELEASE"
wait "$ROUTER_PID"
RC=$?
set -e
[ "$RC" -eq 143 ] || fail "TERM returned $RC instead of 143"
assert_no_runtime
pass "signal cleanup terminates"

# 4. Empty executor failures retain their original status.
set +e
MOCK_CODEX_FAIL_RC=7 run_router --task reason --no-auto-escalate failure-test >/dev/null 2>&1
RC=$?
set -e
[ "$RC" -eq 7 ] || fail "executor failure returned $RC instead of 7"
assert_no_runtime
pass "executor failure status"

# 5-6. Escalation emits one truthful JSON envelope and preserves explicit choices.
rm -f "$WORKDIR/notes.md"
OUT="$(MOCK_CODEX_DELAY=1 run_router --task reason --to codex --model custom-model \
  --effort low --digest --json --timeout 10 --dir "$WORKDIR" \
  'Analyze and save the result to notes.md')" || fail "structured escalation"
printf '%s' "$OUT" | python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["success"] is True
assert d["task"] == "implement"
assert d["executor"] == "codex"
assert d["model"] == "custom-model"
assert d["escalated_from"] == "reason"
assert d["fallback_used"] is False
assert d["duration_seconds"] >= 1
r=d["text"]
assert "IMPLEMENT" in r and "model_reasoning_effort=low" in r
assert "model=custom-model" in r and "OUTPUT CONTRACT" in r
assert "\"success\"" not in r
' || fail "escalation JSON or override preservation"
[ -s "$WORKDIR/notes.md" ] || fail "escalated write was not persisted"
assert_no_runtime
pass "structured escalation and overrides"

# 8. Evaluated fallback: a bulk task's primary (agy) failure retries once on the
#    declared fallback (claude), and the JSON envelope reports who actually served it.
OUT="$(MOCK_AGY_FAIL_RC=5 PATH="$FIXTURES:$PATH" TMPDIR="$RUNTIME_ROOT" \
  DELEGATE_DRIVER=codex "$ROUTER" --task bulk --json --dir "$WORKDIR" fallback-test \
  2>"$TEST_ROOT/fallback.err")" || fail "fallback did not recover"
printf '%s' "$OUT" | python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["success"] is True
assert d["executor"] == "claude"
assert d["model"] == "claude-haiku-4-5"
assert d["fallback_used"] is True
assert "CLAUDE_OK" in d["text"]
' || fail "fallback JSON envelope"
grep -q "falling back once to claude/claude-haiku-4-5" "$TEST_ROOT/fallback.err" \
  || fail "fallback was not logged"
assert_no_runtime
pass "evaluated fallback recovers a failed bulk task"

# 9. A stop-only task (review) never retries on a different executor - same failure
#    shape as before, now also expressed as a JSON failure envelope under --json.
set +e
OUT="$(MOCK_CODEX_FAIL_RC=9 PATH="$FIXTURES:$PATH" TMPDIR="$RUNTIME_ROOT" \
  CODEX_HOME="$SOURCE_HOME" DELEGATE_DRIVER=claude "$ROUTER" --task review \
  --no-auto-escalate --json --dir "$WORKDIR" stop-only-test 2>"$TEST_ROOT/stop.err")"
RC=$?
set -e
[ "$RC" -eq 9 ] || fail "stop-only task returned $RC instead of 9"
printf '%s' "$OUT" | python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["success"] is False
assert d["executor"] == "codex"
assert d["fallback_used"] is False
assert d["text"] is None
assert d["error"]
' || fail "failure JSON envelope"
grep -q "falling back" "$TEST_ROOT/stop.err" && fail "stop-only task must never fall back"
assert_no_runtime
pass "stop-only task fails without a fallback attempt, JSON failure envelope"

# 10. The self-delegation guard also applies to the fallback target: when the
#     declared fallback executor equals the driver, no fallback attempt is made.
set +e
OUT="$(MOCK_AGY_FAIL_RC=5 PATH="$FIXTURES:$PATH" TMPDIR="$RUNTIME_ROOT" \
  DELEGATE_DRIVER=claude "$ROUTER" --task cheap --to agy --json --dir "$WORKDIR" \
  self-fallback-test 2>"$TEST_ROOT/self.err")"
RC=$?
set -e
[ "$RC" -eq 5 ] || fail "blocked self-fallback returned $RC instead of 5 (agy's own exit code, unfallen-back)"
grep -q "falling back" "$TEST_ROOT/self.err" && fail "fallback should have been blocked by the self-delegation guard"
assert_no_runtime
pass "fallback respects the self-delegation guard"

# 12. Success on the primary attempt never touches the fallback executor.
OUT="$(PATH="$FIXTURES:$PATH" TMPDIR="$RUNTIME_ROOT" DELEGATE_DRIVER=codex \
  "$ROUTER" --task bulk --json --dir "$WORKDIR" no-fallback-needed)" || fail "bulk primary success"
printf '%s' "$OUT" | python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["success"] is True
assert d["executor"] == "agy"
assert d["fallback_used"] is False
' || fail "primary success must not report fallback_used"
assert_no_runtime
pass "successful primary never invokes fallback"

# 13. Rule 1's self-delegation reroute is gated to judgment tasks (review/reason/
#     audit) - bulk/cheap/etc. are normal fan-out, not self-delegation, so a bulk
#     task run by its own matching driver (DRIVER=agy, bulk's own default
#     executor) must NOT be rerouted even though EXEC == DRIVER. When that
#     un-rerouted primary fails, the ordinary fallback (declared claude/haiku)
#     still applies normally - this is a plain fallback, not a dedup case.
set +e
OUT="$(MOCK_AGY_FAIL_RC=6 PATH="$FIXTURES:$PATH" TMPDIR="$RUNTIME_ROOT" \
  DELEGATE_DRIVER=agy "$ROUTER" --task bulk --no-auto-escalate --json --dir "$WORKDIR" \
  same-executor-test 2>"$TEST_ROOT/samex.err")"
RC=$?
set -e
[ "$RC" -eq 0 ] || fail "same-executor bulk case returned $RC instead of 0 (recovered via fallback)"
printf '%s' "$OUT" | python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d["executor"] == "claude"
assert d["model"] == "claude-haiku-4-5"
assert d["fallback_used"] is True
assert "CLAUDE_OK" in d["text"]
' || fail "un-rerouted bulk primary must recover via the ordinary fallback"
grep -q "rerouted" "$TEST_ROOT/samex.err" && fail "bulk is not a judgment task - rule 1 must not reroute it"
grep -q "falling back once to claude/claude-haiku-4-5" "$TEST_ROOT/samex.err" \
  || fail "ordinary fallback must still fire when the primary was never rerouted"
assert_no_runtime
pass "rule 1's self-delegation reroute does not apply to non-judgment tasks like bulk"

# 14. Malformed options and clearly foreign model ids fail before execution.
assert_usage_error() {
  local label="$1"; shift
  set +e
  run_router "$@" >/dev/null 2>&1
  local rc=$?
  set -e
  [ "$rc" -eq 2 ] || fail "$label returned $rc instead of 2"
}
assert_usage_error "invalid executor" --task reason --to llama validation
assert_usage_error "invalid effort" --task reason --effort extreme validation
assert_usage_error "invalid timeout" --task reason --timeout 0 validation
assert_usage_error "invalid directory" --task reason --dir "$TEST_ROOT/missing" validation
assert_usage_error "foreign model" --task reason --to codex --model claude-opus validation
assert_usage_error "Codex image model" --task image-text --model gpt-image validation
assert_no_runtime
pass "argument and model validation"

# 15. route_lookup.py validates routes.json structurally at load time: a
#     missing required field fails loudly with the specific row, not a
#     downstream field-count mismatch three call-frames away.
LOOKUP="$SCRIPT_DIR/route_lookup.py"
BROKEN_ROUTES="$TEST_ROOT/routes-missing-field.json"
python3 -c '
import json
with open("'"$SCRIPT_DIR"'/routes.json") as f:
    doc = json.load(f)
del doc["routes"][0]["fallback"]
with open("'"$BROKEN_ROUTES"'", "w") as f:
    json.dump(doc, f)
'
set +e
ERR="$(python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
import route_lookup
route_lookup.ROUTES_PATH = __import__('pathlib').Path('$BROKEN_ROUTES')
route_lookup.main()
" --list 2>&1)"
RC=$?
set -e
[ "$RC" -ne 0 ] || fail "malformed routes.json (missing field) did not fail"
[[ "$ERR" == *"missing required key"* ]] || fail "malformed routes.json error did not name the missing key: $ERR"
[[ "$ERR" == *"fallback"* ]] || fail "malformed routes.json error did not name the specific field: $ERR"
pass "route_lookup.py rejects a structurally malformed routes.json"

# 16. The real, shipped routes.json actually validates and round-trips through
#     both output contracts route_lookup.py promises (--list and --task).
python3 "$LOOKUP" --list >/dev/null || fail "shipped routes.json failed --list"
OUT="$(python3 "$LOOKUP" --task bulk)" || fail "shipped routes.json failed --task bulk"
[ "$(printf '%s\n' "$OUT" | wc -l | tr -d ' ')" -eq 6 ] || fail "route_lookup.py --task must emit exactly 6 lines"
pass "shipped routes.json validates and both output contracts hold"

printf 'PASS: %s regression groups\n' "$PASS"
