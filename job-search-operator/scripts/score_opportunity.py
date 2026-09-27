#!/usr/bin/env python3
"""Calculate a weighted score for a job opportunity."""

import argparse
import json

WEIGHTS = (6, 5, 4, 3, 2)
CATEGORIES = ("fit", "access", "interest", "terms", "timing")


def score_opportunity(ratings):
    """Return a weighted score or range for opportunity ratings."""
    if len(ratings) != len(CATEGORIES):
        raise ValueError("exactly five ratings are required")

    normalized = []
    for category, value in zip(CATEGORIES, ratings):
        if isinstance(value, str) and value.upper() == "U":
            normalized.append("U")
        elif isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5:
            normalized.append(value)
        elif isinstance(value, str) and value in {"1", "2", "3", "4", "5"}:
            normalized.append(int(value))
        else:
            raise ValueError(f"{category} must be 1-5 or U")
    unknown = [
        category
        for category, value in zip(CATEGORIES, normalized)
        if value == "U"
    ]
    if not unknown:
        return {
            "kind": "exact",
            "score": sum(value * weight for value, weight in zip(normalized, WEIGHTS)),
            "unknown": [],
        }

    minimum = sum(
        (1 if value == "U" else value) * weight
        for value, weight in zip(normalized, WEIGHTS)
    )
    maximum = sum(
        (5 if value == "U" else value) * weight
        for value, weight in zip(normalized, WEIGHTS)
    )
    return {
        "kind": "provisional",
        "minimum": minimum,
        "maximum": maximum,
        "midpoint": (minimum + maximum) // 2,
        "unknown": unknown,
    }


def main():
    """Calculate and print an opportunity score from five CLI ratings."""
    parser = argparse.ArgumentParser()
    parser.add_argument("ratings", nargs=5)
    arguments = parser.parse_args()
    try:
        result = score_opportunity(arguments.ratings)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
