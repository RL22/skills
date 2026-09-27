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
