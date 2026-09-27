#!/usr/bin/env bash
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
skill_name="$(basename "$skill_dir")"

targets=(
  "$HOME/.claude/skills/$skill_name"
  "$HOME/.config/opencode/skills/$skill_name"
  "$HOME/.config/opencode/skill/$skill_name"
)

echo "Canonical skill: $skill_dir"

for target in "${targets[@]}"; do
  parent="$(dirname "$target")"
  mkdir -p "$parent"
  if [ -L "$target" ]; then
    current="$(readlink "$target")"
    if [ "$current" = "$skill_dir" ]; then
      echo "exists: $target -> $skill_dir"
      continue
    fi
    echo "refusing: $target is a symlink to $current" >&2
    exit 2
  fi
  if [ -e "$target" ]; then
    echo "refusing: $target already exists and is not a symlink" >&2
    exit 2
  fi
  ln -s "$skill_dir" "$target"
  echo "created: $target -> $skill_dir"
done
