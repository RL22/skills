---
name: failure-ledger
description: Extract root causes from the runtime failure ledger and transcripts, compile positive rules into AGENTS.md, and prevent recurring execution errors. Trigger on 'learning from the last run', 'post-mortem', 'audit failures', 'analyze errors', or /failure-ledger.
---

# Failure Ledger & Rule Compiler

Post-mortem engine that converts execution failures into positive, durable operational rules. It ingests the runtime failure ledger, isolates the causal divergence using binary probes, and compiles hardened behavioral rules directly into `AGENTS.md`.

## Information Hierarchy

1. **Steps**: In-file sequence for processing runtime failures.
2. **Reference**: In-file taxonomy of failure modes and rule compilation patterns.
3. **Disclosed Reference**: Runtime failure ledger at `.agents/ledger/failures.jsonl` and session transcripts at `<appDataDir>/brain/<conversation-id>/.system_generated/logs/transcript.jsonl`.

---

## Core Leading Words

- **ledger**: The persistent, append-only record of command failures, exit codes, and tool errors logged at `.agents/ledger/failures.jsonl`.
- **root-first**: Tracing execution divergence back to environmental invariants and preconditions before evaluating command syntax.
- **binary-probe**: A zero-side-effect, single-variable probe (e.g. `which tool`, `test -f <path>`, `<command> --help`) that splits the hypothesis space in half.
- **tight**: A fast, deterministic loop with immediate checkable feedback and zero cognitive noise.

---

## Execution Steps

Execute these steps in strict sequence. Every step must meet its completion criterion before advancing.

### 1. Ingest the Ledger and Context

Locate and read the active failure ledger:
- Check `.agents/ledger/failures.jsonl`.
- If missing or empty, parse recent tool execution errors from the conversation transcript or execution history.
- Collate each failure into a chronological chain: tool name, exact command/arguments, exit code, and error output.

> **Completion Criterion**: Every logged tool failure in the current or previous run is cataloged with its raw command, exit code, and captured stderr.

### 2. Isolate Root Divergence via Binary Probes

For each cataloged failure, identify the divergence between model assumption and environment reality:
- Apply a **root-first** inspection: determine whether the failure stems from an environment invariant (missing path, dependency, permission, shell configuration) or invocation syntax (invalid flags, bad quoting, shell parameter expansion).
- Execute a **tight** **binary-probe** for each unverified assumption:
  - Verify binary presence: `command -v <tool>`
  - Verify filesystem path: `test -e <path> && echo "FOUND" || echo "MISSING"`
  - Verify flag compatibility: `<tool> --help 2>&1 | grep -E -- '<flag>'`
- Record the exact environmental truth revealed by the probe.

> **Completion Criterion**: The root divergence for every failure is validated against an observable environmental source of truth; zero speculative explanations remain.

### 3. Synthesize Positive Behavioral Rules

Translate each verified root cause into a compact rule. Enforce **positive phrasing**:
- Formulate the rule as a direct operational posture: state what the agent *must do*, never what it must avoid.
- Run `python3 scripts/compile_rules.py` to auto-aggregate ledger categories and draft candidate rules.
- Anchor the instruction with a **leading word** (`tight`, `root-first`, `binary-probe`, `ledger`).
- Strip all elephant-in-the-room negations (eliminate "never", "do not", "avoid", "don't").
- Prune all no-ops: discard general advice that pretrained models follow by default. Keep only project-specific, tool-specific, or shell-specific invariants.

*Pattern Examples*:
- Weak / Negative: "Don't run commands with unescaped curly braces in zsh or it will error with no matches found."
- Positive & Tight: "Quote wildcard and brace arguments in zsh strings: wrap all `{pattern}` and glob expansions in single quotes."
- Weak / Negative: "Don't guess flags when tools fail."
- Positive & Tight: "Run `<tool> --help` to confirm valid arguments before modifying command flags on failed invocations."

> **Completion Criterion**: Every synthesized rule is phrased as a positive action, fits within 1-2 lines, contains at least one recognized leading word or tool invariant, and contains zero negative prohibitions.

### 4. Compile to AGENTS.md and Clear Ledger

Persist the synthesized rules into the workspace's behavioral layer:
- Open `AGENTS.md` (or create it at the workspace root if absent).
- Locate or create the `## Operational Guardrails` or `## Execution Rules` section.
- Insert the new rules, deduplicating against existing rules.
- Maintain minimal context load: prune outdated, redundant, or superseded instructions.
- Archive or truncate processed entries in `.agents/ledger/failures.jsonl` to reset the circuit breaker.

> **Completion Criterion**: `AGENTS.md` contains the updated positive rules; duplicate entries are eliminated; `.agents/ledger/failures.jsonl` is archived or cleared; git diff confirms clean integration.

---

## Reference: Failure Taxonomy

When diagnosing ledger entries, categorize against this flat peer-set:

| Class | Root Cause | Binary Probe | Target Positive Rule |
| :--- | :--- | :--- | :--- |
| **Shell & CLI** | Missing binary, zsh expansion, or sandbox SSH | `command -v <bin>` / HTTPS test | Probe binary availability; route git over HTTPS; quote brace patterns. |
| **File Mutation** | ArtifactMetadata outside brain dir or existing file | `test -f <path>` | Omit ArtifactMetadata on project files; use Overwrite: true for replacements. |
| **Precision Edit** | TargetContent missing or drifted line range | `view_file` on target lines | Re-read line range with view_file; match exact whitespace before replacement. |
| **Search Scope** | Grep/Find timeout on broad home directory | `pwd` / check directory tree | Scope searches directly to project directories; provide targeted Includes. |
| **Web & Network** | Endpoint 403 or anti-bot challenge | `curl -I <url>` | Route blocked URL extraction through /cloakbrowser runtime per user policy. |
