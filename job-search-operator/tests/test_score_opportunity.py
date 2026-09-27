"""Behavioral tests for the opportunity score calculator."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "score_opportunity.py"


def load_score_module():
    spec = importlib.util.spec_from_file_location("score_opportunity", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ScoreOpportunityTests(unittest.TestCase):
    def test_fully_known_ratings_return_an_exact_weighted_score(self):
        score_opportunity = load_score_module()

        result = score_opportunity.score_opportunity([5, 4, 5, 3, 4])

        self.assertEqual({"kind": "exact", "score": 87, "unknown": []}, result)

    def test_unknown_ratings_return_their_range_and_categories(self):
        score_opportunity = load_score_module()

        result = score_opportunity.score_opportunity([5, 4, 5, "U", "U"])

        self.assertEqual(
            {
                "kind": "provisional",
                "minimum": 75,
                "maximum": 95,
                "midpoint": 85,
                "unknown": ["terms", "timing"],
            },
            result,
        )

    def test_invalid_rating_identifies_its_category(self):
        score_opportunity = load_score_module()

        with self.assertRaisesRegex(ValueError, "access must be 1-5 or U"):
            score_opportunity.score_opportunity([5, 0, 5, 3, 4])

    def test_cli_prints_sorted_json(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "5", "4", "5", "u", "U"],
            check=True,
            capture_output=True,
            text=True,
        )
        expected = {
            "kind": "provisional",
            "minimum": 75,
            "maximum": 95,
            "midpoint": 85,
            "unknown": ["terms", "timing"],
        }

        self.assertEqual(json.dumps(expected, sort_keys=True), completed.stdout.strip())

    def test_cli_reports_invalid_ratings_without_a_traceback(self):
        cases = (
            (["5", "0", "5", "3", "4"], "access must be 1-5 or U"),
            (["5", "4", "invalid", "3", "4"], "interest must be 1-5 or U"),
        )

        for ratings, expected_error in cases:
            with self.subTest(ratings=ratings):
                completed = subprocess.run(
                    [sys.executable, str(SCRIPT_PATH), *ratings],
                    capture_output=True,
                    text=True,
                )

                self.assertNotEqual(0, completed.returncode)
                self.assertIn(expected_error, completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
