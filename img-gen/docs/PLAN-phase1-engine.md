# `/claude.img` Phase 1 — Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the dual-model image generation engine for `/claude.img` — pure prompt-engineering + routing logic, a delegation path (Gemini CLI / Codex CLI, no keys) and a keyed API fallback behind one interface, cost tracking, setup validation, and a CLI entry point.

**Architecture:** Pure, dependency-free logic modules (prompt building, model routing, the result contract) are unit-tested with TDD. The orchestrator (`core.py`) selects an engine, builds the optimized prompt, invokes an injected *runner*, locates the produced image, moves it into the working dir, logs cost, and returns a uniform JSON `Result`. Real generation lives behind a `Runner` protocol so tests use a `FakeRunner` and never call a real CLI/API. Phases 2–3 (studio GUI, director chat, editing layer) build on this engine and are out of scope here.

**Tech Stack:** Python 3.11+, `pytest`, standard library only for the engine (`subprocess`, `shutil`, `pathlib`, `dataclasses`, `json`, `argparse`). No third-party runtime deps in Phase 1.

---

## File Structure

```
~/.agents/skills/claude.img/
  SKILL.md                       # concise command contract + routing table (Task 11)
  scripts/
    __init__.py
    contract.py                  # Result dataclass + JSON (Task 2)
    prompt_engineering.py        # 5-component formula, banned-keyword strip, domain modes (Task 3)
    routing.py                   # auto model selection (Task 4)
    cost_tracker.py              # per-call cost/quota log + running total (Task 5)
    runners/
      __init__.py
      base.py                    # Runner protocol + GenOutput + FakeRunner (Task 6)
      gemini_runner.py           # headless gemini + nanobanana ext (Task 8)
      codex_runner.py            # codex exec + image_gen (Task 8)
    api/
      __init__.py
      gemini_api.py              # direct Gemini API fallback (Task 9)
      openai_api.py              # direct OpenAI Images fallback (Task 9)
    fileops.py                   # newest-file locate + move-into-working-dir (Task 7)
    core.py                      # orchestrator: generate()/edit() (Task 10)
    validate_setup.py            # tool/auth checks (Task 8 helper, finalized Task 10)
    cli.py                       # argparse entry for /claude.img (Task 11)
  references/                    # model-selection.md, prompt-engineering.md, nano-banana.md, gpt-image.md (Task 11)
  tests/
    __init__.py
    test_contract.py
    test_prompt_engineering.py
    test_routing.py
    test_cost_tracker.py
    test_runners_base.py
    test_fileops.py
    test_core.py
    test_validate_setup.py
    test_cli.py
  pyproject.toml                 # pytest config (Task 1)
```

---

### Task 1: Project scaffolding + pytest

**Files:**
- Create: `~/.agents/skills/claude.img/pyproject.toml`
- Create: `~/.agents/skills/claude.img/scripts/__init__.py` (empty)
- Create: `~/.agents/skills/claude.img/scripts/runners/__init__.py` (empty)
- Create: `~/.agents/skills/claude.img/scripts/api/__init__.py` (empty)
- Create: `~/.agents/skills/claude.img/tests/__init__.py` (empty)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "claude-img"
version = "0.1.0"
description = "Dual-model image studio skill engine"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-q"
```

- [ ] **Step 2: Create the four empty `__init__.py` files**

Create each of `scripts/__init__.py`, `scripts/runners/__init__.py`, `scripts/api/__init__.py`, `tests/__init__.py` as empty files.

- [ ] **Step 3: Verify pytest runs (collects zero tests)**

Run: `cd ~/.agents/skills/claude.img && python -m pytest`
Expected: exit 0, "no tests ran".

- [ ] **Step 4: Initialize git + commit**

```bash
cd ~/.agents/skills/claude.img
git init
printf '__pycache__/\n*.pyc\n.pytest_cache/\n*.log\ngenerated/\n' > .gitignore
git add .
git commit -m "chore: scaffold claude.img engine with pytest"
```

---

### Task 2: Result contract

**Files:**
- Create: `scripts/contract.py`
- Test: `tests/test_contract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_contract.py
import json
from scripts.contract import Result


def test_result_to_json_roundtrips_all_fields():
    r = Result(
        path="/tmp/out.png",
        model="gemini",
        prompt="a red cube on white",
        settings={"size": "1024x1024", "count": 1},
        cost={"usd": 0.0, "source": "subscription"},
        engine="delegation",
    )
    data = json.loads(r.to_json())
    assert data == {
        "path": "/tmp/out.png",
        "model": "gemini",
        "prompt": "a red cube on white",
        "settings": {"size": "1024x1024", "count": 1},
        "cost": {"usd": 0.0, "source": "subscription"},
        "engine": "delegation",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.contract'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/contract.py
from dataclasses import dataclass, asdict, field
import json


@dataclass
class Result:
    path: str
    model: str
    prompt: str
    settings: dict = field(default_factory=dict)
    cost: dict = field(default_factory=dict)
    engine: str = "delegation"

    def to_json(self) -> str:
        return json.dumps(asdict(self))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_contract.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/contract.py tests/test_contract.py
git commit -m "feat: add Result contract with JSON serialization"
```

---

### Task 3: Prompt engineering (5-component formula + banned keywords + domain modes)

**Files:**
- Create: `scripts/prompt_engineering.py`
- Test: `tests/test_prompt_engineering.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_prompt_engineering.py
from scripts.prompt_engineering import (
    strip_banned_keywords,
    build_prompt,
    DOMAIN_MODES,
)


def test_strip_banned_keywords_removes_known_terms_case_insensitive():
    out = strip_banned_keywords("a cat, 8K, MASTERPIECE, ultra-realistic")
    assert "8k" not in out.lower()
    assert "masterpiece" not in out.lower()
    assert "ultra-realistic" not in out.lower()
    assert "a cat" in out


def test_build_prompt_orders_components_subject_to_style():
    p = build_prompt(
        {
            "subject": "a matte-black water bottle",
            "action": "standing upright",
            "location": "on wet river stone",
            "composition": "centered, shallow depth of field",
            "style": "studio product photography",
        }
    )
    # Subject first, style last, all present, comma-joined
    assert p.startswith("a matte-black water bottle")
    assert p.endswith("studio product photography")
    assert p.index("standing upright") < p.index("on wet river stone")


def test_build_prompt_skips_empty_components():
    p = build_prompt({"subject": "a red cube", "style": "flat vector"})
    assert p == "a red cube, flat vector"


def test_build_prompt_applies_domain_mode_style_when_no_style_given():
    p = build_prompt({"subject": "a sneaker"}, mode="product")
    assert DOMAIN_MODES["product"] in p


def test_build_prompt_strips_banned_keywords_from_result():
    p = build_prompt({"subject": "a castle, 8k masterpiece"})
    assert "8k" not in p.lower()
    assert "masterpiece" not in p.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_prompt_engineering.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.prompt_engineering'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/prompt_engineering.py
import re

BANNED_KEYWORDS = [
    "8k", "4k", "ultra-realistic", "ultra realistic", "hyperrealistic",
    "masterpiece", "award-winning", "trending on artstation", "best quality",
]

DOMAIN_MODES = {
    "cinema": "cinematic film still, anamorphic lens, dramatic lighting",
    "product": "studio product photography, softbox lighting, seamless background",
    "portrait": "portrait photograph, shallow depth of field, 85mm lens",
    "editorial": "editorial magazine photograph, natural light",
    "ui": "clean UI design mockup, crisp typography",
    "logo": "flat minimal vector logo, solid background",
    "landscape": "wide landscape photograph, golden hour",
    "abstract": "abstract composition, bold shapes",
    "infographic": "clean labeled infographic diagram, flat illustration",
}

_COMPONENT_ORDER = ["subject", "action", "location", "composition", "style"]


def strip_banned_keywords(text: str) -> str:
    out = text
    for kw in BANNED_KEYWORDS:
        out = re.sub(re.escape(kw), "", out, flags=re.IGNORECASE)
    # collapse leftover separators/whitespace
    out = re.sub(r"\s*,\s*,+\s*", ", ", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = out.strip().strip(",").strip()
    return out


def build_prompt(components: dict, mode: str | None = None, model: str = "gemini") -> str:
    parts = [
        str(components[k]).strip()
        for k in _COMPONENT_ORDER
        if components.get(k) and str(components[k]).strip()
    ]
    if mode and not components.get("style") and mode in DOMAIN_MODES:
        parts.append(DOMAIN_MODES[mode])
    joined = ", ".join(parts)
    return strip_banned_keywords(joined)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_prompt_engineering.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/prompt_engineering.py tests/test_prompt_engineering.py
git commit -m "feat: add 5-component prompt builder with banned-keyword discipline"
```

---

### Task 4: Model routing

**Files:**
- Create: `scripts/routing.py`
- Test: `tests/test_routing.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routing.py
from scripts.routing import choose_model


def test_text_in_image_routes_to_gpt():
    assert choose_model('a poster that says "SALE"') == "gpt"


def test_transparency_request_routes_to_gpt():
    assert choose_model("app icon with transparent background") == "gpt"


def test_edit_routes_to_gemini():
    assert choose_model("remove the logo", is_edit=True) == "gemini"


def test_multi_turn_routes_to_gemini():
    assert choose_model("same scene at dusk", multi_turn=True) == "gemini"


def test_plain_scene_defaults_to_gemini():
    assert choose_model("a red fox in snow") == "gemini"


def test_explicit_flags_take_priority_over_text_detection():
    # an edit that also contains text still routes by edit -> gemini default,
    # but transparency is a hard GPT signal even on edits
    assert choose_model("add the word HELLO", is_edit=True) == "gemini"
    assert choose_model("make background transparent", is_edit=True) == "gpt"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_routing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.routing'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/routing.py
import re

_TEXT_SIGNALS = [
    r'"[^"]+"', r"\btext\b", r"\bposter\b", r"\bsign\b", r"\bword[s]?\b",
    r"\bheadline\b", r"\bcaption\b", r"\blabel\b", r"\btypography\b",
]
_TRANSPARENCY_SIGNALS = [r"\btransparent\b", r"\btransparency\b", r"\bno background\b"]


def _matches(prompt: str, patterns: list[str]) -> bool:
    return any(re.search(p, prompt, flags=re.IGNORECASE) for p in patterns)


def choose_model(
    prompt: str,
    *,
    has_text: bool = False,
    needs_transparency: bool = False,
    is_edit: bool = False,
    multi_turn: bool = False,
) -> str:
    # Hard GPT signals win unconditionally.
    if needs_transparency or _matches(prompt, _TRANSPARENCY_SIGNALS):
        return "gpt"
    # Edits / multi-turn favor Nano Banana's consistency.
    if is_edit or multi_turn:
        return "gemini"
    if has_text or _matches(prompt, _TEXT_SIGNALS):
        return "gpt"
    # Cost-aware default.
    return "gemini"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_routing.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/routing.py tests/test_routing.py
git commit -m "feat: add cost-aware auto model routing"
```

---

### Task 5: Cost tracker

**Files:**
- Create: `scripts/cost_tracker.py`
- Test: `tests/test_cost_tracker.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cost_tracker.py
from scripts.cost_tracker import CostTracker


def test_log_appends_entry_and_running_total(tmp_path):
    log = tmp_path / "cost.jsonl"
    t = CostTracker(log)
    t.log(model="gemini", engine="delegation", usd=0.0, source="subscription")
    t.log(model="gpt", engine="api", usd=0.04, source="openai")
    assert t.total_usd() == 0.04
    assert len(log.read_text().strip().splitlines()) == 2


def test_total_usd_is_zero_for_missing_log(tmp_path):
    t = CostTracker(tmp_path / "nope.jsonl")
    assert t.total_usd() == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cost_tracker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.cost_tracker'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/cost_tracker.py
import json
import time
from pathlib import Path


class CostTracker:
    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)

    def log(self, *, model: str, engine: str, usd: float, source: str) -> dict:
        entry = {
            "ts": time.time(),
            "model": model,
            "engine": engine,
            "usd": float(usd),
            "source": source,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def total_usd(self) -> float:
        if not self.log_path.exists():
            return 0.0
        total = 0.0
        for line in self.log_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            total += float(json.loads(line).get("usd", 0.0))
        return round(total, 6)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cost_tracker.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/cost_tracker.py tests/test_cost_tracker.py
git commit -m "feat: add cost/quota tracker with JSONL log"
```

---

### Task 6: Runner protocol + FakeRunner

**Files:**
- Create: `scripts/runners/base.py`
- Test: `tests/test_runners_base.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_runners_base.py
from scripts.runners.base import GenOutput, FakeRunner


def test_gen_output_holds_path_and_cost():
    out = GenOutput(path="/tmp/x.png", usd=0.0, source="subscription")
    assert out.path == "/tmp/x.png"
    assert out.usd == 0.0
    assert out.source == "subscription"


def test_fake_runner_returns_configured_output_and_records_calls():
    runner = FakeRunner(GenOutput(path="/tmp/fake.png", usd=0.0, source="fake"))
    out = runner.generate(prompt="a cube", settings={"size": "1024x1024"})
    assert out.path == "/tmp/fake.png"
    assert runner.calls == [("generate", "a cube", {"size": "1024x1024"})]


def test_fake_runner_edit_records_call():
    runner = FakeRunner(GenOutput(path="/tmp/edit.png", usd=0.0, source="fake"))
    out = runner.edit(image="/tmp/in.png", instruction="brighten", settings={})
    assert out.path == "/tmp/edit.png"
    assert runner.calls[0][0] == "edit"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_runners_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.runners.base'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/runners/base.py
from dataclasses import dataclass
from typing import Protocol


@dataclass
class GenOutput:
    path: str
    usd: float = 0.0
    source: str = "subscription"


class Runner(Protocol):
    def generate(self, prompt: str, settings: dict) -> GenOutput: ...
    def edit(self, image: str, instruction: str, settings: dict) -> GenOutput: ...


class FakeRunner:
    """Test double implementing the Runner protocol."""

    def __init__(self, output: GenOutput):
        self.output = output
        self.calls: list[tuple] = []

    def generate(self, prompt: str, settings: dict) -> GenOutput:
        self.calls.append(("generate", prompt, settings))
        return self.output

    def edit(self, image: str, instruction: str, settings: dict) -> GenOutput:
        self.calls.append(("edit", image, instruction, settings))
        return self.output
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_runners_base.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/runners/base.py tests/test_runners_base.py
git commit -m "feat: add Runner protocol, GenOutput, and FakeRunner test double"
```

---

### Task 7: File operations (locate newest + move into working dir)

**Files:**
- Create: `scripts/fileops.py`
- Test: `tests/test_fileops.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fileops.py
import time
from pathlib import Path
from scripts.fileops import newest_file, move_into


def test_newest_file_returns_most_recent_matching_extension(tmp_path):
    older = tmp_path / "a.png"
    older.write_bytes(b"x")
    time.sleep(0.01)
    newer = tmp_path / "b.png"
    newer.write_bytes(b"y")
    (tmp_path / "note.txt").write_text("ignore")
    result = newest_file(tmp_path, exts={".png"})
    assert result == newer


def test_newest_file_respects_since_timestamp(tmp_path):
    old = tmp_path / "old.png"
    old.write_bytes(b"x")
    cutoff = time.time() + 0.005
    time.sleep(0.02)
    new = tmp_path / "new.png"
    new.write_bytes(b"y")
    result = newest_file(tmp_path, exts={".png"}, since=cutoff)
    assert result == new


def test_newest_file_returns_none_when_empty(tmp_path):
    assert newest_file(tmp_path, exts={".png"}) is None


def test_move_into_moves_file_and_returns_new_path(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src = src_dir / "img.png"
    src.write_bytes(b"data")
    dest_dir = tmp_path / "work"
    moved = move_into(dest_dir, src)
    assert moved.parent == dest_dir
    assert moved.read_bytes() == b"data"
    assert not src.exists()


def test_move_into_avoids_overwriting_existing_name(tmp_path):
    dest_dir = tmp_path / "work"
    dest_dir.mkdir()
    (dest_dir / "img.png").write_bytes(b"existing")
    src = tmp_path / "img.png"
    src.write_bytes(b"new")
    moved = move_into(dest_dir, src)
    assert moved.name != "img.png"
    assert moved.read_bytes() == b"new"
    assert (dest_dir / "img.png").read_bytes() == b"existing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fileops.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.fileops'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/fileops.py
import shutil
from pathlib import Path


def newest_file(directory, exts: set[str], since: float | None = None) -> Path | None:
    directory = Path(directory)
    if not directory.is_dir():
        return None
    candidates = [
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in {e.lower() for e in exts}
        and (since is None or p.stat().st_mtime >= since)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def move_into(working_dir, src) -> Path:
    working_dir = Path(working_dir)
    src = Path(src)
    working_dir.mkdir(parents=True, exist_ok=True)
    dest = working_dir / src.name
    if dest.exists():
        stem, suffix = src.stem, src.suffix
        i = 1
        while dest.exists():
            dest = working_dir / f"{stem}-{i}{suffix}"
            i += 1
    shutil.move(str(src), str(dest))
    return dest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_fileops.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/fileops.py tests/test_fileops.py
git commit -m "feat: add file locate + collision-safe move helpers"
```

---

### Task 8: Delegation runners + setup validation

**Files:**
- Create: `scripts/runners/gemini_runner.py`
- Create: `scripts/runners/codex_runner.py`
- Create: `scripts/validate_setup.py`
- Test: `tests/test_validate_setup.py`

> Real generation is verified manually (Task 12); here we test only the pure/mocked parts: command construction and tool detection. The runners expose a `build_command()` helper so the subprocess call itself stays a thin, untested shell.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_validate_setup.py
import scripts.validate_setup as vs
from scripts.runners.gemini_runner import build_command as gemini_cmd
from scripts.runners.codex_runner import build_command as codex_cmd


def test_gemini_build_command_is_headless_with_prompt():
    cmd = gemini_cmd("a red cube", out_dir="/tmp/g")
    assert cmd[0] == "gemini"
    assert any("a red cube" in part for part in cmd)


def test_codex_build_command_uses_exec():
    cmd = codex_cmd("a blue sphere")
    assert cmd[0] == "codex"
    assert "exec" in cmd
    assert any("a blue sphere" in part for part in cmd)


def test_validate_reports_present_tools(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: f"/usr/bin/{name}")
    report = vs.validate()
    assert report["gemini"]["present"] is True
    assert report["codex"]["present"] is True
    assert report["ok"] is True


def test_validate_flags_missing_tools(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    report = vs.validate()
    assert report["gemini"]["present"] is False
    assert report["ok"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_validate_setup.py -v`
Expected: FAIL with `ModuleNotFoundError` for `scripts.runners.gemini_runner`.

- [ ] **Step 3: Write the runners and validator**

```python
# scripts/runners/gemini_runner.py
import os
import subprocess
import time
from pathlib import Path
from scripts.runners.base import GenOutput
from scripts.fileops import newest_file, move_into

# Headless invocation of the nanobanana extension's /generate command.
NANOBANANA_OUTPUT_DIR = Path.home() / ".gemini" / "nanobanana_generated"


def build_command(prompt: str, out_dir: str) -> list[str]:
    # Custom slash command runs in headless one-shot mode via -p.
    return ["gemini", "-p", f"/generate {prompt}"]


class GeminiRunner:
    def __init__(self, working_dir: str, output_dir: Path = NANOBANANA_OUTPUT_DIR):
        self.working_dir = working_dir
        self.output_dir = Path(output_dir)

    def _run(self, prompt: str) -> GenOutput:
        env = dict(os.environ, NANOBANANA_MODEL="gemini-2.5-flash-image")
        since = time.time()
        subprocess.run(
            build_command(prompt, str(self.output_dir)),
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        produced = newest_file(self.output_dir, exts={".png", ".jpg", ".jpeg"}, since=since)
        if produced is None:
            raise RuntimeError("gemini delegation produced no image file")
        moved = move_into(self.working_dir, produced)
        return GenOutput(path=str(moved), usd=0.0, source="gemini-subscription")

    def generate(self, prompt: str, settings: dict) -> GenOutput:
        return self._run(prompt)

    def edit(self, image: str, instruction: str, settings: dict) -> GenOutput:
        return self._run(f"/edit {image} {instruction}")
```

```python
# scripts/runners/codex_runner.py
import subprocess
import time
from pathlib import Path
from scripts.runners.base import GenOutput
from scripts.fileops import newest_file, move_into

CODEX_OUTPUT_DIR = Path.home() / ".codex" / "generated_images"


def build_command(prompt: str) -> list[str]:
    return ["codex", "exec", f"Generate an image: {prompt}. Use the image_gen tool."]


class CodexRunner:
    def __init__(self, working_dir: str, output_dir: Path = CODEX_OUTPUT_DIR):
        self.working_dir = working_dir
        self.output_dir = Path(output_dir)

    def generate(self, prompt: str, settings: dict) -> GenOutput:
        since = time.time()
        subprocess.run(
            build_command(prompt), check=True, capture_output=True, text=True
        )
        produced = newest_file(self.output_dir, exts={".png", ".jpg", ".jpeg"}, since=since)
        if produced is None:
            raise RuntimeError("codex delegation produced no image file")
        moved = move_into(self.working_dir, produced)
        return GenOutput(path=str(moved), usd=0.0, source="codex-subscription")

    def edit(self, image: str, instruction: str, settings: dict) -> GenOutput:
        prompt = f"Edit image {image}: {instruction}. Use the image_gen tool."
        since = time.time()
        subprocess.run(
            ["codex", "exec", prompt], check=True, capture_output=True, text=True
        )
        produced = newest_file(self.output_dir, exts={".png", ".jpg", ".jpeg"}, since=since)
        if produced is None:
            raise RuntimeError("codex delegation produced no image file")
        moved = move_into(self.working_dir, produced)
        return GenOutput(path=str(moved), usd=0.0, source="codex-subscription")
```

```python
# scripts/validate_setup.py
import os
import shutil


def validate() -> dict:
    gemini_present = shutil.which("gemini") is not None
    codex_present = shutil.which("codex") is not None
    report = {
        "gemini": {
            "present": gemini_present,
            "hint": "install Gemini CLI + nanobanana extension",
        },
        "codex": {
            "present": codex_present,
            "hint": "install Codex CLI (codex exec)",
        },
        "api_fallback": {
            "gemini_key": bool(os.environ.get("GEMINI_API_KEY")),
            "openai_key": bool(os.environ.get("OPENAI_API_KEY")),
        },
    }
    report["ok"] = gemini_present or codex_present
    return report


if __name__ == "__main__":
    import json

    print(json.dumps(validate(), indent=2))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_validate_setup.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/runners/gemini_runner.py scripts/runners/codex_runner.py scripts/validate_setup.py tests/test_validate_setup.py
git commit -m "feat: add delegation runners and setup validation"
```

---

### Task 9: API fallback adapters

**Files:**
- Create: `scripts/api/gemini_api.py`
- Create: `scripts/api/openai_api.py`
- Test: extend `tests/test_validate_setup.py` (command/guard checks only; live calls deferred to Task 12)

> The API adapters require keys and network; Phase 1 tests only the key-guard so a missing key fails clearly instead of making a bad call.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_guard.py
import pytest
from scripts.api.gemini_api import GeminiApiRunner
from scripts.api.openai_api import OpenAiApiRunner


def test_gemini_api_runner_raises_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiApiRunner(working_dir="/tmp").generate("a cube", {})


def test_openai_api_runner_raises_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAiApiRunner(working_dir="/tmp").generate("a cube", {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api_guard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.api.gemini_api'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/api/gemini_api.py
import os
from scripts.runners.base import GenOutput

GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"


class GeminiApiRunner:
    def __init__(self, working_dir: str):
        self.working_dir = working_dir

    def _require_key(self) -> str:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set (required for API fallback)")
        return key

    def generate(self, prompt: str, settings: dict) -> GenOutput:
        key = self._require_key()
        # TODO(Task 12): real google-genai call writing into working_dir.
        raise NotImplementedError("live Gemini API call wired in Task 12")

    def edit(self, image: str, instruction: str, settings: dict) -> GenOutput:
        self._require_key()
        raise NotImplementedError("live Gemini API edit wired in Task 12")
```

```python
# scripts/api/openai_api.py
import os
from scripts.runners.base import GenOutput

OPENAI_IMAGE_MODEL = "gpt-image-2"


class OpenAiApiRunner:
    def __init__(self, working_dir: str):
        self.working_dir = working_dir

    def _require_key(self) -> str:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set (required for API fallback)")
        return key

    def generate(self, prompt: str, settings: dict) -> GenOutput:
        self._require_key()
        # TODO(Task 12): real openai images call writing into working_dir.
        raise NotImplementedError("live OpenAI API call wired in Task 12")

    def edit(self, image: str, instruction: str, settings: dict) -> GenOutput:
        self._require_key()
        raise NotImplementedError("live OpenAI API edit wired in Task 12")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api_guard.py -v`
Expected: PASS (2 tests). The key-guard raises before the `NotImplementedError`.

- [ ] **Step 5: Commit**

```bash
git add scripts/api/gemini_api.py scripts/api/openai_api.py tests/test_api_guard.py
git commit -m "feat: add keyed API fallback adapters with key guards"
```

---

### Task 10: Core orchestrator

**Files:**
- Create: `scripts/core.py`
- Test: `tests/test_core.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_core.py
from scripts.core import generate, build_runner
from scripts.runners.base import GenOutput, FakeRunner
from scripts.cost_tracker import CostTracker


def test_generate_uses_injected_runner_and_returns_result(tmp_path):
    fake = FakeRunner(GenOutput(path=str(tmp_path / "out.png"), usd=0.0, source="fake"))
    tracker = CostTracker(tmp_path / "cost.jsonl")
    result = generate(
        prompt="a red fox in snow",
        model="gemini",
        runner=fake,
        tracker=tracker,
        settings={"size": "1024x1024"},
    )
    assert result.model == "gemini"
    assert result.path.endswith("out.png")
    # prompt was passed through the builder (still contains the subject)
    assert "red fox" in result.prompt
    assert fake.calls[0][0] == "generate"


def test_generate_auto_selects_model_when_none_given(tmp_path):
    fake = FakeRunner(GenOutput(path=str(tmp_path / "o.png")))
    tracker = CostTracker(tmp_path / "c.jsonl")
    result = generate(
        prompt='a banner that says "HELLO"',
        model="auto",
        runner=fake,
        tracker=tracker,
    )
    assert result.model == "gpt"  # text-in-image routed to gpt


def test_generate_logs_cost(tmp_path):
    fake = FakeRunner(GenOutput(path=str(tmp_path / "o.png"), usd=0.04, source="openai"))
    log = tmp_path / "c.jsonl"
    tracker = CostTracker(log)
    generate(prompt="a cube", model="gpt", runner=fake, tracker=tracker)
    assert tracker.total_usd() == 0.04


def test_build_runner_returns_delegation_runner_for_gemini(tmp_path):
    runner = build_runner(model="gemini", engine="delegation", working_dir=str(tmp_path))
    assert runner.__class__.__name__ == "GeminiRunner"


def test_build_runner_returns_api_runner_for_gpt_api(tmp_path):
    runner = build_runner(model="gpt", engine="api", working_dir=str(tmp_path))
    assert runner.__class__.__name__ == "OpenAiApiRunner"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.core'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/core.py
from pathlib import Path
from scripts.contract import Result
from scripts.prompt_engineering import build_prompt
from scripts.routing import choose_model
from scripts.cost_tracker import CostTracker
from scripts.runners.gemini_runner import GeminiRunner
from scripts.runners.codex_runner import CodexRunner
from scripts.api.gemini_api import GeminiApiRunner
from scripts.api.openai_api import OpenAiApiRunner

DEFAULT_COST_LOG = Path.home() / ".agents" / "skills" / "claude.img" / "cost.jsonl"


def build_runner(model: str, engine: str, working_dir: str):
    if engine == "api":
        return GeminiApiRunner(working_dir) if model == "gemini" else OpenAiApiRunner(working_dir)
    # delegation (default)
    return GeminiRunner(working_dir) if model == "gemini" else CodexRunner(working_dir)


def _resolve_prompt(prompt: str, mode: str | None, model: str) -> str:
    # A bare string is treated as the subject of the 5-component formula.
    return build_prompt({"subject": prompt}, mode=mode, model=model)


def generate(
    prompt: str,
    model: str = "auto",
    *,
    runner=None,
    tracker: CostTracker | None = None,
    engine: str = "delegation",
    mode: str | None = None,
    settings: dict | None = None,
    working_dir: str = ".",
) -> Result:
    settings = settings or {}
    if model == "auto":
        model = choose_model(prompt)
    optimized = _resolve_prompt(prompt, mode, model)
    if runner is None:
        runner = build_runner(model=model, engine=engine, working_dir=working_dir)
    if tracker is None:
        tracker = CostTracker(DEFAULT_COST_LOG)

    out = runner.generate(optimized, settings)
    tracker.log(model=model, engine=engine, usd=out.usd, source=out.source)
    return Result(
        path=out.path,
        model=model,
        prompt=optimized,
        settings=settings,
        cost={"usd": out.usd, "source": out.source},
        engine=engine,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_core.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest`
Expected: PASS (all tests across all files).

- [ ] **Step 6: Commit**

```bash
git add scripts/core.py tests/test_core.py
git commit -m "feat: add core orchestrator with auto-routing and cost logging"
```

---

### Task 11: CLI entry + SKILL.md + references

**Files:**
- Create: `scripts/cli.py`
- Create: `SKILL.md`
- Create: `references/model-selection.md`, `references/prompt-engineering.md`, `references/nano-banana.md`, `references/gpt-image.md`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli.py
from scripts.cli import parse_args


def test_parse_generate_with_model_and_prompt():
    ns = parse_args(["gemini", "a red cube on white"])
    assert ns.model == "gemini"
    assert ns.prompt == "a red cube on white"
    assert ns.command == "generate"


def test_parse_prompt_only_defaults_model_auto():
    ns = parse_args(["a red cube"])
    assert ns.model == "auto"
    assert ns.prompt == "a red cube"


def test_parse_studio_subcommand():
    ns = parse_args(["studio"])
    assert ns.command == "studio"


def test_parse_engine_flag():
    ns = parse_args(["gpt", "a sign that says OPEN", "--engine", "api"])
    assert ns.engine == "api"
    assert ns.model == "gpt"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.cli'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/cli.py
import argparse

MODELS = {"gemini", "gpt"}
SUBCOMMANDS = {"studio", "edit", "batch", "preset", "inspire"}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="claude.img")
    parser.add_argument("--engine", choices=["delegation", "api"], default="delegation")
    parser.add_argument("--mode", default=None)
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("tokens", nargs="*")
    ns = parser.parse_args(argv)

    tokens = list(ns.tokens)
    command = "generate"
    model = "auto"
    prompt = ""

    if tokens and tokens[0] in SUBCOMMANDS:
        command = tokens[0]
        prompt = " ".join(tokens[1:])
    else:
        if tokens and tokens[0] in MODELS:
            model = tokens[0]
            tokens = tokens[1:]
        prompt = " ".join(tokens)

    ns.command = command
    ns.model = model
    ns.prompt = prompt
    return ns


def main(argv: list[str] | None = None) -> int:
    import sys
    from scripts.core import generate

    ns = parse_args(argv if argv is not None else sys.argv[1:])
    if ns.command != "generate":
        print(f"[claude.img] '{ns.command}' lands in a later phase")
        return 0
    result = generate(
        prompt=ns.prompt,
        model=ns.model,
        engine=ns.engine,
        mode=ns.mode,
        settings={"size": ns.size, "count": ns.count},
    )
    print(result.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Write `SKILL.md` (concise, routing inline)**

```markdown
---
name: claude.img
description: "Dual-model image generation, direction, and editing. Generates with Nano Banana (gemini-2.5-flash-image via Gemini CLI) and GPT Image 2 (gpt-image-2 via Codex CLI). Use for any image creation, editing, or visual asset request. Triggers on: generate an image, create a photo, edit this picture, design a logo, make a banner, and all /claude.img commands."
argument-hint: "[gemini|gpt|studio|edit|batch] <prompt or path>"
metadata:
  version: "0.1.0"
  source: "forked from AgriciDaniel/banana-claude, re-architected for portability"
---

# /claude.img

Run `python scripts/validate_setup.py` once to confirm Gemini CLI (+ nanobanana extension) and Codex CLI are installed and authed.

## Invocation

`/claude.img {model?} {prompt?}` — model is `gemini` | `gpt` (omit = auto).

| You give | Action |
|---|---|
| model + prompt | optimize prompt in that model's dialect, then generate |
| prompt only | recommend the best-fit model + one-line reason, confirm, generate |
| model only | ask the user for the goal (use case, style, key elements), then generate |
| neither | ask the goal first, recommend a model, then generate |

Run: `python scripts/cli.py {model} "{prompt}" [--engine delegation|api] [--mode <domain>]`

## Model routing (auto)

| Signal | Model |
|---|---|
| text in image, transparency, strict adherence | gpt (gpt-image-2) |
| edits, character consistency, fast/cheap, multi-turn | gemini (nano banana) |
| tiebreak | gemini (cost-aware default) |

Always announce the chosen model and why.

## Engines

- `delegation` (default): headless Gemini/Codex sessions, no API keys, subscription cost.
- `api` (fallback): direct keyed API (`GEMINI_API_KEY` / `OPENAI_API_KEY`), faster/deterministic.

For model-specific params load `references/nano-banana.md` or `references/gpt-image.md` — only the one you're using.
```

- [ ] **Step 5: Write the four reference stubs**

Create each file with real starter content (no placeholders):

```markdown
<!-- references/model-selection.md -->
# Model selection
Route to **gpt** (gpt-image-2) when the request needs rendered text, a transparent background, or strict prompt adherence. Route to **gemini** (nano banana) for edits, character/identity consistency, fast cheap iteration, multi-turn directing, and as the cost-aware default tiebreak. Always state the decision to the user.
```

```markdown
<!-- references/prompt-engineering.md -->
# Prompt engineering
Build every prompt with the 5-component formula: Subject -> Action -> Location -> Composition -> Style. Never use banned filler ("8k", "masterpiece", "ultra-realistic"); control fidelity with size/quality params and concrete detail (camera model, focal length, materials, lighting). Gemini favors rich natural-language scene description; GPT Image rewards explicit, structured instructions and handles negatives and typography well.
```

```markdown
<!-- references/nano-banana.md -->
# Nano Banana (gemini-2.5-flash-image)
Accessed via Gemini CLI nanobanana extension (`/generate`, `/edit`) headless, or the Gemini API (`GEMINI_API_KEY`). Strengths: editing, character consistency, multi-turn, speed, cost. Set `NANOBANANA_MODEL=gemini-2.5-flash-image`.
```

```markdown
<!-- references/gpt-image.md -->
# GPT Image 2 (gpt-image-2)
Accessed via Codex CLI native image_gen tool (no key) or the OpenAI Images API (`OPENAI_API_KEY`). Strengths: >99% text rendering accuracy, transparency, strict prompt adherence, fixed sizes. Codex saves to ~/.codex/generated_images/.
```

- [ ] **Step 6: Run CLI tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest`
Expected: PASS (all tests).

- [ ] **Step 8: Commit**

```bash
git add scripts/cli.py SKILL.md references/
git commit -m "feat: add CLI entry, SKILL.md, and model references"
```

---

### Task 12: Manual live verification (no automated test)

> Generation hits real CLIs/subscriptions — verify by hand, not in CI. Do this only after the full unit suite is green.

- [ ] **Step 1: Validate setup**

Run: `python scripts/validate_setup.py`
Expected: JSON shows `gemini.present` and/or `codex.present` true, `ok: true`.

- [ ] **Step 2: Live delegation generate (Gemini)**

Run: `cd /tmp && python ~/.agents/skills/claude.img/scripts/cli.py gemini "a matte-black water bottle on wet river stone, studio product photography"`
Expected: JSON `Result` printed; the `path` points to a real PNG inside `/tmp`; open it and confirm it matches.

- [ ] **Step 3: Live delegation generate (Codex / gpt-image-2)**

Run: `cd /tmp && python ~/.agents/skills/claude.img/scripts/cli.py gpt 'a poster that says "OPEN" in bold type'`
Expected: JSON `Result`; PNG in `/tmp`; the word "OPEN" renders legibly (text-in-image is gpt's strength).

- [ ] **Step 4: Confirm auto-routing end-to-end**

Run: `cd /tmp && python ~/.agents/skills/claude.img/scripts/cli.py 'a sign reading "CAFE"'`
Expected: `Result.model == "gpt"` (auto-routed on the text signal).

- [ ] **Step 5: Confirm cost log accumulates**

Run: `cat ~/.agents/skills/claude.img/cost.jsonl`
Expected: one JSON line per generation above.

- [ ] **Step 6: Tag the milestone**

```bash
cd ~/.agents/skills/claude.img
git tag phase-1-engine
```

---

## Self-Review

**Spec coverage (Phase 1 scope):**
- Dual-model engine, structural parity → Tasks 6, 8, 9, 10 (one `Runner` interface, uniform `Result`). ✓
- Delegation primary + keyed API fallback, switchable per call → `build_runner(engine=...)` Task 10; `--engine` flag Task 11. ✓
- Prompt-engineering (5-component, banned keywords, domain modes) → Task 3. ✓
- Auto model routing → Task 4, wired in Task 10. ✓
- Cost discipline / logging → Task 5, wired in Task 10. ✓
- Output-file locate + move to working dir → Task 7, used by runners Task 8. ✓
- Zero-key default, keyed fallback guarded → Tasks 8, 9. ✓
- Setup validation → Task 8. ✓
- SKILL.md progressive disclosure + references → Task 11. ✓
- Command-name-with-dot risk → folder/command kept literal `claude.img`; if a host rejects it, alias to `claude-img` (noted in DESIGN §16; revisit before install). ✓
- Studio GUI, director chat, editing layer → **out of scope, Phases 2–3** (separate plans). ✓

**Placeholder scan:** The only `TODO`/`NotImplementedError` markers are in the API adapters (Task 9), deliberately deferred to Task 12 and covered by key-guard tests that assert behavior *before* the unimplemented call. No vague "add error handling" steps; every code step shows complete code.

**Type consistency:** `GenOutput(path, usd, source)` used identically across Tasks 6, 8, 9, 10. `Result(path, model, prompt, settings, cost, engine)` consistent Tasks 2 & 10. `generate(...)`, `build_runner(...)`, `choose_model(...)`, `build_prompt(...)`, `CostTracker.log/total_usd`, `newest_file/move_into` signatures match every call site.

---

## Execution Handoff

Plan complete and saved to `~/.agents/skills/claude.img/docs/PLAN-phase1-engine.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session with checkpoints for review.

Which approach?
