#!/usr/bin/env python3
"""Count characters in LinkedIn connection notes."""

import argparse


def character_count(text):
    """Return the number of Unicode code points in *text*."""
    return len(text)


def within_limit(text, limit=200):
    """Return whether *text* has no more than *limit* code points."""
    return character_count(text) <= limit


def non_negative_limit(value):
    """Parse a non-negative integer limit for argparse."""
    try:
        limit = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("limit must be an integer") from error
    if limit < 0:
        raise argparse.ArgumentTypeError("limit must be non-negative")
    return limit


def main():
    """Print a note's character count and optionally validate its limit."""
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--limit", type=non_negative_limit, default=200)
    parser.add_argument("--validate", action="store_true")
    arguments = parser.parse_args()

    count = character_count(arguments.text)
    is_within_limit = within_limit(arguments.text, arguments.limit)
    status = "OK" if is_within_limit else "OVER"
    print(f"{count}/{arguments.limit} {status}")
    return 0 if is_within_limit or not arguments.validate else 1


if __name__ == "__main__":
    raise SystemExit(main())
