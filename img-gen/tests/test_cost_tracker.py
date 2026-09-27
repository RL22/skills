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
