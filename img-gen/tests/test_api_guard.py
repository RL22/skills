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
