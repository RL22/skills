#!/usr/bin/env python3
"""
Inspect an Agent Skill folder and print a compact review summary.

Usage:
  python scripts/inspect-skill.py /path/to/skill

This script is intentionally dependency-free.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def read_text(path: Path, limit: int = 20000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except Exception as exc:
        return f"[ERROR reading file: {exc}]"


def extract_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    raw = parts[1].strip()
    body = parts[2].strip()
    data: dict[str, str] = {}

    current_key = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z0-9_-]+:", line):
            key, value = line.split(":", 1)
            current_key = key.strip()
            data[current_key] = value.strip().strip('"').strip("'")
        elif current_key:
            data[current_key] += "\n" + line

    return data, body


def count_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except Exception:
        return 0


def list_files(root: Path) -> list[str]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append(str(path.relative_to(root)))
    return files


def risk_scan(files: list[str], root: Path) -> list[str]:
    risky_patterns = [
        "rm -rf",
        "sudo ",
        "curl ",
        "wget ",
        "chmod 777",
        "eval(",
        "exec(",
        "subprocess",
        "os.system",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "password",
        "secret",
        "token",
        "ignore previous",
        "bypass",
    ]

    flags = []
    for rel in files:
        path = root / rel
        if path.suffix.lower() not in [".md", ".py", ".sh", ".js", ".ts", ".json", ".yaml", ".yml", ".txt"]:
            continue
        text = read_text(path, limit=50000).lower()
        for pattern in risky_patterns:
            if pattern.lower() in text:
                flags.append(f"{rel}: found `{pattern}`")
    return flags


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/inspect-skill.py /path/to/skill", file=sys.stderr)
        return 2

    root = Path(sys.argv[1]).expanduser().resolve()

    if not root.exists() or not root.is_dir():
        print(f"ERROR: Not a directory: {root}", file=sys.stderr)
        return 1

    skill_md = root / "SKILL.md"
    files = list_files(root)

    print("# Skill Inspection Summary")
    print()
    print(f"Path: `{root}`")
    print(f"Directory name: `{root.name}`")
    print()

    print("## Structure")
    print()
    print(f"- Has SKILL.md: {'yes' if skill_md.exists() else 'no'}")
    print(f"- Has scripts/: {'yes' if (root / 'scripts').is_dir() else 'no'}")
    print(f"- Has references/: {'yes' if (root / 'references').is_dir() else 'no'}")
    print(f"- Has assets/: {'yes' if (root / 'assets').is_dir() else 'no'}")
    print(f"- Total files: {len(files)}")
    print()

    if not skill_md.exists():
        print("ERROR: Missing required SKILL.md")
        return 1

    text = read_text(skill_md)
    frontmatter, body = extract_frontmatter(text)

    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")

    print("## Frontmatter")
    print()
    print(f"- name: `{name or 'MISSING'}`")
    print(f"- description present: {'yes' if description else 'no'}")
    print(f"- license: `{frontmatter.get('license', 'not specified')}`")
    print(f"- compatibility: `{frontmatter.get('compatibility', 'not specified')}`")
    print()

    print("## Spec Checks")
    print()
    print(f"- Name matches directory: {'yes' if name == root.name else 'no'}")
    print(f"- Name format valid: {'yes' if NAME_RE.match(name or '') else 'no'}")
    print(f"- Description length: {len(description)} chars")
    print(f"- SKILL.md lines: {count_lines(skill_md)}")
    print()

    print("## Files")
    print()
    for rel in files:
        print(f"- {rel}")
    print()

    flags = risk_scan(files, root)
    print("## Risk Flags")
    print()
    if flags:
        for flag in flags:
            print(f"- {flag}")
    else:
        print("- No obvious risk flags found by simple scan.")
    print()

    print("## Suggested Next Step")
    print()
    print("Use this summary with the SkillFit scorecard to evaluate user fit, portability, output quality, safety, maintainability, and documentation.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
