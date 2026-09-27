#!/usr/bin/env python3
"""
Calculate a weighted SkillFit score.

Usage:
  python scripts/score-skill.py \
    --fit 4 \
    --portability 3 \
    --quality 4 \
    --safety 5 \
    --maintainability 3 \
    --docs 4
"""

from __future__ import annotations

import argparse


WEIGHTS = {
    "fit": 25,
    "portability": 20,
    "quality": 20,
    "safety": 20,
    "maintainability": 10,
    "docs": 5,
}


def validate_score(value: str) -> int:
    try:
        score = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Score must be an integer between 1 and 5.") from exc

    if score < 1 or score > 5:
        raise argparse.ArgumentTypeError("Score must be between 1 and 5.")
    return score


def recommendation(score: float) -> str:
    if score >= 85:
        return "Adopt"
    if score >= 70:
        return "Adopt with edits"
    if score >= 55:
        return "Trial"
    if score >= 40:
        return "Fork / rewrite"
    return "Reject"


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate a weighted SkillFit score.")
    parser.add_argument("--fit", type=validate_score, required=True, help="User/workflow fit score, 1-5.")
    parser.add_argument("--portability", type=validate_score, required=True, help="Agent portability score, 1-5.")
    parser.add_argument("--quality", type=validate_score, required=True, help="Output quality score, 1-5.")
    parser.add_argument("--safety", type=validate_score, required=True, help="Safety/trust score, 1-5.")
    parser.add_argument("--maintainability", type=validate_score, required=True, help="Maintainability score, 1-5.")
    parser.add_argument("--docs", type=validate_score, required=True, help="Documentation score, 1-5.")

    args = parser.parse_args()

    scores = {
        "fit": args.fit,
        "portability": args.portability,
        "quality": args.quality,
        "safety": args.safety,
        "maintainability": args.maintainability,
        "docs": args.docs,
    }

    weighted = {
        key: (value / 5) * WEIGHTS[key]
        for key, value in scores.items()
    }

    total = sum(weighted.values())

    print("# SkillFit Score")
    print()
    print("| Category | Weight | Score | Weighted Total |")
    print("|---|---:|---:|---:|")

    labels = {
        "fit": "User / workflow fit",
        "portability": "Agent portability",
        "quality": "Output quality",
        "safety": "Safety / trust",
        "maintainability": "Maintainability",
        "docs": "Documentation",
    }

    for key in WEIGHTS:
        print(f"| {labels[key]} | {WEIGHTS[key]} | {scores[key]} | {weighted[key]:.1f} |")

    print()
    print(f"Final score: `{total:.1f}/100`")
    print(f"Recommendation: **{recommendation(total)}**")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
