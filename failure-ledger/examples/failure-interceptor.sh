#!/usr/bin/env bash
# Failure Interceptor & Ledger Hook
# Standard POSIX bash script for Tier 1 Runtime Interception

set -euo pipefail

MODE="${1:-post}"
INPUT_JSON=$(cat)

LEDGER_DIR=".agents/ledger"
LEDGER_FILE="${LEDGER_DIR}/failures.jsonl"
STATE_FILE="${LEDGER_DIR}/.consecutive_failures"

mkdir -p "${LEDGER_DIR}"

if [[ ! -f "${STATE_FILE}" ]]; then
  echo "0" > "${STATE_FILE}"
fi

CONSECUTIVE=$(cat "${STATE_FILE}" 2>/dev/null || echo "0")

if [[ "${MODE}" == "pre" ]]; then
  # Check consecutive failure threshold
  if [[ "${CONSECUTIVE}" -ge 2 ]]; then
    # Deny further blind retries and shock the model into running a binary probe
    cat <<EOF
{
  "decision": "deny",
  "reason": "Thrash Breaker Engaged: 2 consecutive execution failures logged in ${LEDGER_FILE}. Isolate environmental preconditions with a zero-side-effect binary-probe before executing further commands."
}
EOF
    exit 0
  fi
  # Allow normal execution
  cat <<EOF
{
  "decision": "allow"
}
EOF
  exit 0
fi

if [[ "${MODE}" == "post" ]]; then
  # Check if tool execution resulted in an error
  HAS_ERROR=$(python3 -c "
import sys, json
try:
    d = json.loads('''${INPUT_JSON}''')
    print('yes' if d.get('error') else 'no')
except:
    print('no')
" 2>/dev/null || echo "no")

  if [[ "${HAS_ERROR}" == "yes" ]]; then
    CONSECUTIVE=$((CONSECUTIVE + 1))
    echo "${CONSECUTIVE}" > "${STATE_FILE}"

    # Append failure entry to ledger
    python3 -c "
import sys, json, time
try:
    payload = json.loads('''${INPUT_JSON}''')
    entry = {
        'timestamp': int(time.time()),
        'stepIdx': payload.get('stepIdx'),
        'error': payload.get('error'),
        'toolCall': payload.get('toolCall', {})
    }
    with open('${LEDGER_FILE}', 'a') as f:
        f.write(json.dumps(entry) + '\n')
except Exception as e:
    pass
" 2>/dev/null || true
  else
    # Success resets consecutive failure counter
    echo "0" > "${STATE_FILE}"
  fi

  # PostToolUse contract expects empty JSON object
  echo "{}"
  exit 0
fi
