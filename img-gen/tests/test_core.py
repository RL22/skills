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
