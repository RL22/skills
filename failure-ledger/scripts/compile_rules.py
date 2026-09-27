#!/usr/bin/env python3
"""
compile_rules.py - Compile runtime tool failure ledger entries into hardened, positive rules.
Follows /mps-writing-for-agents:
  - Tight token economy
  - Positive phrasing (no elephant prohibitions)
  - Leading words: root-first, binary-probe, tight, ledger
"""

import argparse
import collections
import json
import os
import re
import subprocess
import sys

LEDGER_PATHS = [
    os.path.expanduser("~/.gemini/logs/universal-failures.jsonl"),
    os.path.expanduser("~/.gemini/logs/bash-failures.jsonl"),
    os.path.abspath(".agents/ledger/failures.jsonl"),
    os.path.abspath(".agents/runs/failures.jsonl")
]


def load_ledger(custom_path=None):
    paths = [custom_path] if custom_path else LEDGER_PATHS
    entries = []
    for path in paths:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            continue
    return entries


def probe_binary(name):
    """Zero-side-effect binary check."""
    try:
        res = subprocess.run(["command", "-v", name], capture_output=True, text=True, shell=True)
        return res.returncode == 0
    except Exception:
        return False


def synthesize_rules(entries):
    by_category = collections.defaultdict(list)
    for e in entries:
        cat = e.get("category", "GENERIC_TOOL_FAILURE")
        by_category[cat].append(e)

    rules = []

    # --- 1. File Writing Rules ---
    if "INVALID_ARTIFACT_METADATA" in by_category:
        rules.append(
            "- **Artifact Scope**: Supply `ArtifactMetadata` exclusively when writing to the active conversation brain directory. "
            "For standard project files, invoke `write_to_file` without artifact metadata parameters."
        )

    if "FILE_WRITE_EXISTING" in by_category:
        rules.append(
            "- **File Mutation**: Verify whether a target file already exists prior to invocation. "
            "Set `Overwrite: true` for wholesale file replacement, or invoke `replace_file_content` for surgical modifications."
        )

    # --- 2. File Editing Rules ---
    if "EDIT_TARGET_NOT_FOUND" in by_category:
        rules.append(
            "- **Precision Editing**: Invoke `view_file` on the target line range immediately before editing. "
            "Ensure `TargetContent` matches the exact whitespace, indentation, and line numbering of the file."
        )

    if "EDIT_MULTIPLE_MATCHES" in by_category:
        rules.append(
            "- **Edit Windowing**: Narrow `[StartLine, EndLine]` to encompass exactly one occurrence of `TargetContent`. "
            "Set `AllowMultiple: true` only when deliberately replacing every identical instance across the file."
        )

    # --- 3. File Viewing Rules ---
    if "VIEW_RANGE_EXCEEDED" in by_category:
        rules.append(
            "- **View Windowing**: Bound `view_file` queries to 800 lines maximum (`EndLine - StartLine < 800`). "
            "Slice larger files into sequential chunks using `StartLine` offsets."
        )

    # --- 4. Search & Discovery Rules ---
    if "SEARCH_TIMEOUT_BROAD" in by_category:
        rules.append(
            "- **Targeted Search**: Scope `grep_search` and `find_by_name` directly to the active project folder. "
            "Supply targeted `Includes` filters (e.g. `'*.ts'`, `'src/**'`) when searching deep trees to avoid timeouts."
        )

    # --- 5. Web & Network Access Rules ---
    if "WEB_ACCESS_BLOCKED" in by_category:
        rules.append(
            "- **Stealth Web Access**: When public endpoints or documentation pages block direct HTTP fetches with 403 or bot protection, "
            "re-route navigation through `/cloakbrowser`."
        )

    # --- 6. Shell & Binary Execution Rules ---
    if "MISSING_BINARY" in by_category:
        binaries = set()
        for e in by_category["MISSING_BINARY"]:
            m = re.search(r"Binary '([^']+)' was not found", e.get("actionableFix", "") or e.get("fix", ""))
            if m:
                binaries.add(m.group(1))
            else:
                cmd = str(e.get("args", {}).get("CommandLine", "") or e.get("command", "")).strip().split()
                if cmd:
                    binaries.add(cmd[0])
        for b in sorted(binaries):
            available = probe_binary(b)
            if not available:
                rules.append(
                    f"- **CLI Environment**: Binary `{b}` is uninstalled or absent from PATH. "
                    f"Use `command -v {b}` to verify presence; use project wrappers (e.g. `npm`, `npx`) or install prerequisites."
                )

    if "SANDBOX_SSH_RESTRICTION" in by_category:
        rules.append(
            "- **Git Remote Transport**: Sandboxed shells restrict port 22 SSH connections. "
            "Clone and push repositories exclusively over authenticated HTTPS (`https://github.com/...`)."
        )

    if "PYTHON_QUOTE_SYNTAX_ERROR" in by_category:
        rules.append(
            "- **Inline Scripting**: Shell parameter parsing corrupts nested quotes in multi-line `python3 -c` calls. "
            "Write multi-line Python logic to a temporary script file using `write_to_file` or heredoc before execution."
        )

    if "CWD_OR_MODULE_MISMATCH" in by_category:
        rules.append(
            "- **Working Directory Invariant**: Sub-packages isolate dependencies per folder. "
            "Verify current working directory context with `pwd` and check `package.json` before executing test or build scripts."
        )

    return rules


def main():
    parser = argparse.ArgumentParser(description="Compile universal failure ledger entries into positive rules.")
    parser.add_argument("--ledger", help="Path to specific failures.jsonl file", default=None)
    parser.add_argument("--output", help="Output format (markdown|json)", default="markdown")
    args = parser.parse_args()

    entries = load_ledger(args.ledger)
    if not entries:
        print("No logged failure entries found in ledger.", file=sys.stderr)
        return 0

    rules = synthesize_rules(entries)
    if args.output == "json":
        print(json.dumps({"total_failures": len(entries), "synthesized_rules": rules}, indent=2))
    else:
        print(f"### Synthesized Operational Guardrails ({len(entries)} events analyzed)\n")
        for r in rules:
            print(r)


if __name__ == "__main__":
    sys.exit(main())
