import scripts.validate_setup as vs
from scripts.runners.gemini_runner import build_command as gemini_cmd
from scripts.runners.codex_runner import build_command as codex_cmd


def test_gemini_build_command_is_headless_with_prompt():
    cmd = gemini_cmd("a red cube", out_dir="/tmp/g")
    # Runs on agy since 2026-08-08; the `gemini` CLI was retired in the June 2026
    # Antigravity cutover and hung with no output.
    assert cmd[0] == "agy"
    assert any("a red cube" in part for part in cmd)
    # agy's generate_image is a native tool, but headless tool calls still need
    # auto-approval, and the workspace is granted with --add-dir (agy has no
    # --skip-trust). The retired gemini flags must not reappear.
    assert "--dangerously-skip-permissions" in cmd
    assert "--add-dir" in cmd and "/tmp/g" in cmd
    assert "-p" in cmd
    assert "--yolo" not in cmd
    assert "--skip-trust" not in cmd
    assert not any("/generate" in part for part in cmd)


def test_codex_build_command_uses_exec():
    cmd = codex_cmd("a blue sphere")
    assert cmd[0] == "codex"
    assert "exec" in cmd
    assert any("a blue sphere" in part for part in cmd)
    # Verified live: codex exec needs --skip-git-repo-check outside a git repo.
    assert "--skip-git-repo-check" in cmd


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
