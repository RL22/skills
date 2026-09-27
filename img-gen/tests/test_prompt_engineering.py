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
