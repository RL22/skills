#!/usr/bin/env python3
"""Typed loader/validator for delegate.sh's routing table (routes.json).

Replaces the old hand-rolled `IFS='|' read` bash parsing of a pipe-delimited
string. That approach required updating three separate parsing sites in
lockstep (the --list loop, lookup_route(), and a hard-coded field-count
assertion) every time a column was added, and a malformed row failed
silently or off-by-one rather than loudly. This script validates the whole
table against an explicit schema once, at load time, and exits nonzero with
a specific reason on any structural problem — the row and the missing/wrong
field, not a downstream bash arithmetic mismatch three call-frames away.

Output contracts (unchanged from the old bash implementation, so delegate.sh
did not need to change how it *consumes* a lookup — only how it's produced):

  --list            prints the same formatted table delegate.sh always printed.
  --task <name>     prints exactly 6 lines: executor[!], model, effort, mode,
                     digest (0|1), fallback ("stop" or "executor:model").
                     Exits 1 with nothing on stdout if the task is unknown.
"""
import json
import sys
from pathlib import Path

ROUTES_PATH = Path(__file__).resolve().parent / "routes.json"

REQUIRED_KEYS = {"task", "executor", "pinned", "model", "effort", "mode", "digest", "fallback", "tier"}
VALID_MODES = {"read", "write", "web", "image"}
VALID_EFFORTS = {"low", "medium", "high", None}
VALID_TIERS = {0, 1, 2, 3}


def die(msg: str) -> None:
    print(f"route_lookup.py: {msg}", file=sys.stderr)
    sys.exit(1)


def load_routes() -> list[dict]:
    try:
        raw = ROUTES_PATH.read_text()
    except OSError as e:
        die(f"could not read {ROUTES_PATH}: {e}")
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"{ROUTES_PATH} is not valid JSON: {e}")

    routes = doc.get("routes")
    if not isinstance(routes, list) or not routes:
        die(f"{ROUTES_PATH}: top-level \"routes\" must be a non-empty array")

    seen_tasks: set[str] = set()
    for i, r in enumerate(routes):
        where = f"routes[{i}]"
        if not isinstance(r, dict):
            die(f"{where}: entry must be an object")
        missing = REQUIRED_KEYS - r.keys()
        if missing:
            die(f"{where} (task={r.get('task', '?')!r}): missing required key(s): {sorted(missing)}")
        extra = r.keys() - REQUIRED_KEYS
        if extra:
            die(f"{where} (task={r['task']!r}): unknown key(s): {sorted(extra)}")

        if not isinstance(r["task"], str) or not r["task"]:
            die(f"{where}: \"task\" must be a non-empty string")
        if r["task"] in seen_tasks:
            die(f"{where}: duplicate task name {r['task']!r}")
        seen_tasks.add(r["task"])

        if r["executor"] not in ("agy", "codex", "claude"):
            die(f"{where} (task={r['task']!r}): \"executor\" must be agy/codex/claude, got {r['executor']!r}")
        if not isinstance(r["pinned"], bool):
            die(f"{where} (task={r['task']!r}): \"pinned\" must be a boolean")
        if r["model"] is not None and not isinstance(r["model"], str):
            die(f"{where} (task={r['task']!r}): \"model\" must be a string or null")
        if r["effort"] not in VALID_EFFORTS:
            die(f"{where} (task={r['task']!r}): \"effort\" must be low/medium/high/null, got {r['effort']!r}")
        if r["mode"] not in VALID_MODES:
            die(f"{where} (task={r['task']!r}): \"mode\" must be one of {sorted(VALID_MODES)}, got {r['mode']!r}")
        if not isinstance(r["digest"], bool):
            die(f"{where} (task={r['task']!r}): \"digest\" must be a boolean")
        if isinstance(r["tier"], bool) or r["tier"] not in VALID_TIERS:
            die(f"{where} (task={r['task']!r}): \"tier\" must be an integer 0-3, got {r['tier']!r}")

        fb = r["fallback"]
        if fb is not None:
            if not isinstance(fb, dict) or fb.keys() != {"executor", "model"}:
                die(f"{where} (task={r['task']!r}): \"fallback\" must be null or {{\"executor\", \"model\"}}")
            if fb["executor"] not in ("agy", "codex", "claude"):
                die(f"{where} (task={r['task']!r}): fallback.executor must be agy/codex/claude, got {fb['executor']!r}")
            if not isinstance(fb["model"], str) or not fb["model"]:
                die(f"{where} (task={r['task']!r}): fallback.model must be a non-empty string")

    return routes


def fmt_fallback(fb) -> str:
    return "stop" if fb is None else f"{fb['executor']}:{fb['model']}"


def cmd_list(routes: list[dict]) -> None:
    print(f"{'TASK':<10} {'TIER':<4} {'EXEC':<6} {'MODEL':<22} {'EFFORT':<7} {'MODE':<6} {'DIGEST':<6} FALLBACK")
    for r in routes:
        exec_col = r["executor"] + (" (pinned)" if r["pinned"] else "")
        model_col = r["model"] or "<inherit config>"
        effort_col = r["effort"] or ""
        digest_col = "yes" if r["digest"] else "no"
        print(f"{r['task']:<10} {r['tier']:<4} {exec_col:<6} {model_col:<22} {effort_col:<7} {r['mode']:<6} {digest_col:<6} {fmt_fallback(r['fallback'])}")


def cmd_task(routes: list[dict], task: str) -> None:
    for r in routes:
        if r["task"] != task:
            continue
        exec_out = r["executor"] + ("!" if r["pinned"] else "")
        print(exec_out)
        print(r["model"] or "")
        print(r["effort"] or "")
        print(r["mode"])
        print("1" if r["digest"] else "0")
        print(fmt_fallback(r["fallback"]))
        return
    sys.exit(1)  # unknown task: silent nonzero, matching the old lookup_route() contract


def main() -> None:
    routes = load_routes()
    if len(sys.argv) == 2 and sys.argv[1] == "--list":
        cmd_list(routes)
    elif len(sys.argv) == 3 and sys.argv[1] == "--task":
        cmd_task(routes, sys.argv[2])
    else:
        die("usage: route_lookup.py --list | --task <name>")


if __name__ == "__main__":
    main()
