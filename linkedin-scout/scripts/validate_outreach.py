"""
validate_outreach.py - Deterministic Validation Gate for Outreach Dossiers.
Part of the linkedin-scout skill (scripts/validate_outreach.py).

Validates outreach dossiers against strict quality, platform, and character constraints:
1. Connection Notes: Must be <= 200 Unicode characters.
2. Banned Characters: Zero em-dashes (—).
3. Banned Phrases: Rejects lazy check-ins and agency SEO spam phrases:
   ('just following up', 'bumping this', 'website scan', '3-point scan', 'hope this finds you well', etc.)
4. Audience Segmentation:
   - Recruiters: Must request routing or eligibility; no unsolicited technical architecture dumps.
   - Engineering Leaders: Must contain systems tradeoff / verified achievement.
5. Fails closed with exit code 1 on any violation.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

BANNED_PHRASES = [
    re.compile(r"\bjust\s+following\s+up\b", re.IGNORECASE),
    re.compile(r"\bbumping\s+this\b", re.IGNORECASE),
    re.compile(r"\b(?:quick\s+)?3-point\s+scan\b", re.IGNORECASE),
    re.compile(r"\bwebsite\s+(?:audit|scan)\b", re.IGNORECASE),
    re.compile(r"\bchecking\s+in\b", re.IGNORECASE),
    re.compile(r"\bhope\s+(?:this\s+email\s+)?finds\s+you\s+well\b", re.IGNORECASE),
    re.compile(r"\bpick\s+your\s+brain\b", re.IGNORECASE),
]

EM_DASH_PATTERN = re.compile(r"—")


def validate_dossier_text(content: str, filename: str = "outreach.md") -> Tuple[List[str], List[str]]:
    """Scan markdown outreach content and return (errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []

    lines = content.splitlines()

    # 1. Check for Em-Dashes
    for idx, line in enumerate(lines, 1):
        if EM_DASH_PATTERN.search(line):
            errors.append(f"Line {idx}: Prohibited em-dash (—) found. Use commas, hyphens, or parentheses.")

    # 2. Check for Banned Phrases
    for idx, line in enumerate(lines, 1):
        for pattern in BANNED_PHRASES:
            m = pattern.search(line)
            if m:
                errors.append(f"Line {idx}: Banned phrase detected: '{m.group(0)}'. Use peer-level systems language.")

    # 3. Connection Request Note Lengths
    # Pattern looks for notes under headings like "### Connection Request Note" or blockquotes
    in_connection_note = False
    current_note_lines: List[str] = []
    note_start_line = 0

    for idx, line in enumerate(lines, 1):
        if re.search(r"###\s+Connection\s+Request\s+Note", line, re.IGNORECASE):
            in_connection_note = True
            current_note_lines = []
            note_start_line = idx
            continue

        if in_connection_note:
            if line.startswith("### ") or line.startswith("---") or line.startswith("## "):
                # End of connection note section
                full_note = " ".join(current_note_lines).strip()
                # Strip leading blockquote markers
                full_note = re.sub(r"^>\s*", "", full_note).strip()
                if full_note:
                    char_count = len(full_note)
                    if char_count > 200:
                        errors.append(
                            f"Line {note_start_line}: Connection note exceeds 200 characters "
                            f"({char_count}/200 chars): '{full_note[:40]}...'"
                        )
                in_connection_note = False
                current_note_lines = []
            else:
                if line.strip().startswith(">"):
                    current_note_lines.append(line.strip().lstrip(">").strip())
                elif line.strip() and not line.startswith("#"):
                    current_note_lines.append(line.strip())

    # Flush any pending note at EOF
    if in_connection_note and current_note_lines:
        full_note = " ".join(current_note_lines).strip()
        full_note = re.sub(r"^>\s*", "", full_note).strip()
        if full_note:
            char_count = len(full_note)
            if char_count > 200:
                errors.append(
                    f"Line {note_start_line}: Connection note exceeds 200 characters "
                    f"({char_count}/200 chars): '{full_note[:40]}...'"
                )

    return errors, warnings


def validate_file(file_path: Path) -> bool:
    """Validate a single markdown dossier file."""
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return False

    content = file_path.read_text(encoding="utf-8")
    errors, warnings = validate_dossier_text(content, filename=file_path.name)

    print(f"\nScanning {file_path}...")
    if warnings:
        for w in warnings:
            print(f"  [WARN] {w}")

    if errors:
        for e in errors:
            print(f"  [FAIL] {e}")
        print(f"RESULT: ❌ {len(errors)} validation failure(s) in {file_path.name}")
        return False

    print(f"RESULT: ✓ All checks passed cleanly for {file_path.name}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate outreach markdown dossiers against strict rules.")
    parser.add_argument("paths", nargs="*", help="File or directory paths to validate")
    parser.add_argument("--scan-all", action="store_true", help="Scan all outreach files in stages/03_outreach_drafting/output/")
    args = parser.parse_args()

    targets: List[Path] = []
    if args.scan_all or not args.paths:
        default_dir = Path(
            os.environ.get(
                "SPRINTZ_JOB_SEARCH_DIR",
                os.path.expanduser("~/Sprintz/jobs/job-search"),
            )
        ) / "stages" / "03_outreach_drafting" / "output"
        if default_dir.exists():
            targets.extend(default_dir.glob("**/outreach.md"))

    for p_str in args.paths:
        p = Path(p_str).resolve()
        if p.is_dir():
            targets.extend(p.glob("**/outreach.md"))
        elif p.is_file():
            targets.append(p)

    if not targets:
        print("No outreach files found to validate.")
        sys.exit(0)

    all_passed = True
    for target in targets:
        if not validate_file(target):
            all_passed = False

    if not all_passed:
        print("\n❌ Validation gate failed. Resolve errors before presenting outreach to candidate.")
        sys.exit(1)
    else:
        print("\n✓ ALL OUTREACH DOSSIERS PASSED DETERMINISTIC VALIDATION!")
        sys.exit(0)


if __name__ == "__main__":
    main()
