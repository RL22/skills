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
