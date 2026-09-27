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
