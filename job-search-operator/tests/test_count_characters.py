"""Behavioral tests for the LinkedIn note character counter."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "count_characters.py"


def load_count_module():
    spec = importlib.util.spec_from_file_location("count_characters", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CountCharactersTests(unittest.TestCase):
    def test_character_count_uses_unicode_code_points(self):
        count_characters = load_count_module()

        self.assertEqual(4, count_characters.character_count("Hi 👋"))

    def test_within_limit_is_inclusive_at_the_200_character_boundary(self):
        count_characters = load_count_module()

        self.assertTrue(count_characters.within_limit("a" * 199))
        self.assertTrue(count_characters.within_limit("a" * 200))
        self.assertFalse(count_characters.within_limit("a" * 201))

    def test_cli_reports_count_and_validates_only_when_requested(self):
        at_limit = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "a" * 200],
            check=True,
            capture_output=True,
            text=True,
        )
        over_limit_without_validation = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "a" * 201],
            capture_output=True,
            text=True,
        )
        over_limit_with_validation = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "a" * 201, "--validate"],
            capture_output=True,
            text=True,
        )

        self.assertEqual("200/200 OK", at_limit.stdout.strip())
        self.assertEqual(0, over_limit_without_validation.returncode)
        self.assertEqual("201/200 OVER", over_limit_without_validation.stdout.strip())
        self.assertEqual(1, over_limit_with_validation.returncode)
        self.assertEqual("201/200 OVER", over_limit_with_validation.stdout.strip())

    def test_cli_rejects_negative_limits_without_a_traceback(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "note", "--limit", "-1"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(2, completed.returncode)
        self.assertIn("limit must be non-negative", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
