import subprocess
import sys
from pathlib import Path
from scripts.cli import parse_args


def test_cli_runs_as_script_from_any_cwd(tmp_path):
    # Regression (Task 12): `python scripts/cli.py` from an unrelated cwd must
    # resolve `import scripts.*`. 'studio' exits early, so no generation/quota.
    cli = Path(__file__).resolve().parent.parent / "scripts" / "cli.py"
    proc = subprocess.run(
        [sys.executable, str(cli), "studio"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "later phase" in proc.stdout


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
