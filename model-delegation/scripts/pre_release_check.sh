#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

bash -n "$SCRIPT_DIR/delegate.sh"
bash -n "$SCRIPT_DIR/test_delegate.sh"
for fixture in "$SCRIPT_DIR"/tests/fixtures/*; do
  bash -n "$fixture"
done

SCRIPT_VERSION="$(sed -n 's/^VERSION="\([^"]*\)"/\1/p' "$SCRIPT_DIR/delegate.sh")"
SKILL_VERSION="$(sed -n 's/^  version: "\([^"]*\)"/\1/p' "$SKILL_DIR/SKILL.md")"
[ -n "$SCRIPT_VERSION" ] && [ "$SCRIPT_VERSION" = "$SKILL_VERSION" ] \
  || { printf 'version mismatch: script=%s skill=%s\n' "$SCRIPT_VERSION" "$SKILL_VERSION" >&2; exit 1; }

"$SCRIPT_DIR/test_delegate.sh"
printf 'PRE-RELEASE PASS: model-delegation v%s\n' "$SCRIPT_VERSION"
