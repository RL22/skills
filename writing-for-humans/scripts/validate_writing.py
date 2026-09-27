#!/usr/bin/env python3
"""Conservative Markdown prose validator for Sprintz writing rules."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    path: str
    line: int | None
    message: str
    text: str
    suggestion: str


BANNED_WORDS = (
    "delve", "leverage", "harness", "foster", "cultivate", "empower",
    "supercharge", "streamline", "utilize", "revolutionize", "unlock",
    "landscape", "tapestry", "beacon", "testament", "game-changer",
    "synergy", "paradigm", "plethora", "seamless", "multifaceted",
    "comprehensive", "robust", "bespoke", "innovative", "cutting-edge",
    "bleeding-edge",
)
BANNED_PHRASES = (
    "in today's fast-paced world",
    "in the realm of",
    "at its core",
    "it's not just x, it's y",
    "a double-edged sword",
    "in conclusion",
)
HYPE_ADJECTIVES = (
    "revolutionary", "groundbreaking", "transformative", "effortless",
    "world-class", "best-in-class", "game-changing", "unprecedented",
    "incredible", "amazing",
)
THROAT_CLEARING = re.compile(
    r"^(sure|absolutely|of course|certainly|in this article|today we will|"
    r"let's dive|let us dive|welcome to)\b", re.IGNORECASE
)
STRONG_CLAIM = re.compile(
    r"\b(always|never|guarantee(?:d)?|best|only|will|can|"
    r"increase(?:s|d)?|improve(?:s|d)?|reduce(?:s|d)?|save(?:s|d)?)\b",
    re.IGNORECASE,
)
EVIDENCE = re.compile(
    r"(\d|%|\baccording to\b|\bsource(?:d)?\b|\bmeasured\b|\bverified\b|"
    r"\btested\b|\bobserved\b|\bdata\b|\bstudy\b|\brecord\b|\bartifact\b)",
    re.IGNORECASE,
)
CLAIM_TYPE_LABEL = re.compile(
    r"\b(fact|inference|recommendation|anecdote|hypothesis|we recommend|"
    r"we observed|our observation|in my experience)\b", re.IGNORECASE
)
THESIS_SIGNAL = re.compile(
    r"\b(the point is|the answer is|the problem is|the thesis is|"
    r"we recommend|you should|this means|the fix is|the goal is)\b",
    re.IGNORECASE,
)
CANONICAL_MARKER = re.compile(
    r"<!--\s*canonical-terms\s*:\s*(.*?)-->", re.IGNORECASE
)
CANONICAL_ALIASES = {
    "founder": ("entrepreneur", "business owner"),
    "customer": ("client", "user", "buyer"),
    "workflow": ("process", "pipeline"),
    "website": ("site", "web presence"),
}
SHAME_LANGUAGE = re.compile(
    r"\b(lazy|loser|weak|stupid|low-intelligence|pathetic|"
    r"if you disagree|you don't really want)\b", re.IGNORECASE
)
NOMINALIZATION = re.compile(
    r"\b[A-Za-z]+(?:tion|ment|ance|ence|ity|ness|ship)\b"
)
WORD = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“‘])")


def prose_lines(text: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    in_fence = False
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if stripped.startswith((chr(96) * 3, "~~~")):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith(">"):
            continue
        if stripped.startswith("<!--"):
            continue
        result.append((number, raw))
    return result


def clean_line(line: str) -> str:
    line = re.sub(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+", "", line)
    line = re.sub(r"^\s{0,3}#{1,6}\s+", "", line)
    return line.strip()


def words(text: str) -> int:
    return len(WORD.findall(text))


def split_sentences(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for number, raw in lines:
        for sentence in SENTENCE.split(clean_line(raw)):
            sentence = sentence.strip()
            if sentence:
                result.append((number, sentence))
    return result


def make_finding(
    rule: str, severity: str, path: Path, line: int | None,
    message: str, text: str, suggestion: str,
) -> Finding:
    return Finding(rule, severity, str(path), line, message, text[:240], suggestion)


def check_file(path: Path) -> list[Finding]:
    source = path.read_text(encoding="utf-8")
    visible = [(n, clean_line(line)) for n, line in prose_lines(source)]
    visible = [(n, line) for n, line in visible if line]
    findings: list[Finding] = []

    for number, line in visible:
        for term in BANNED_WORDS:
            if re.search(rf"\b{re.escape(term)}\b", line, re.IGNORECASE):
                findings.append(make_finding(
                    "W001", "warning", path, number,
                    f"Banned or inflated vocabulary: {term}", line,
                    "Replace it with a specific action, object, result, or metric.",
                ))
        for phrase in BANNED_PHRASES:
            if phrase.casefold() in line.casefold():
                findings.append(make_finding(
                    "W002", "warning", path, number,
                    f"Banned cliché or rhetorical construction: {phrase}", line,
                    "State the problem, trade-off, conclusion, or action directly.",
                ))
        if "!" in line:
            findings.append(make_finding(
                "W005", "warning", path, number,
                "Exclamation point in ordinary prose", line,
                "Use a period or let the sentence carry its own force.",
            ))
        for adjective in HYPE_ADJECTIVES:
            if re.search(rf"\b{re.escape(adjective)}\b", line, re.IGNORECASE):
                findings.append(make_finding(
                    "W010", "warning", path, number,
                    f"Unsupported hype adjective: {adjective}", line,
                    "Replace it with evidence, a mechanism, or a measurable outcome.",
                ))
        if SHAME_LANGUAGE.search(line):
            findings.append(make_finding(
                "W016", "review", path, number,
                "Possible shame or psychological invalidation", line,
                "Diagnose the behavior without humiliating the reader.",
            ))
        if STRONG_CLAIM.search(line) and not EVIDENCE.search(line):
            findings.append(make_finding(
                "W011", "review", path, number,
                "Strong claim has no nearby evidence marker", line,
                "Add a source, metric, artifact, observation, or label it as an inference.",
            ))
            if not CLAIM_TYPE_LABEL.search(line):
                findings.append(make_finding(
                    "W012", "review", path, number,
                    "Material claim is not labeled by claim type", line,
                    "Label it as a fact, inference, recommendation, anecdote, or hypothesis when the distinction matters.",
                ))

    if len(visible) >= 8:
        opening_count = max(1, (len(visible) + 4) // 5)
        opening = visible[:opening_count]
        later = visible[opening_count:]
        if (
            not any(THESIS_SIGNAL.search(line) for _, line in opening)
            and any(STRONG_CLAIM.search(line) for _, line in later)
        ):
            findings.append(make_finding(
                "W014", "review", path, later[0][0],
                "Thesis or primary answer may appear after the opening 20 percent",
                later[0][1],
                "State the thesis, answer, or action in the opening fifth of the piece.",
            ))

    canonical = CANONICAL_MARKER.search(source)
    if canonical:
        terms = {
            item.strip().casefold()
            for item in canonical.group(1).split(",")
            if item.strip()
        }
        for term in terms:
            for alias in CANONICAL_ALIASES.get(term, ()):
                match = re.search(rf"\b{re.escape(alias)}\b", source, re.IGNORECASE)
                if match and re.search(rf"\b{re.escape(term)}\b", source, re.IGNORECASE):
                    findings.append(make_finding(
                        "W013", "review", path, None,
                        f"Possible synonym drift: canonical term '{term}' shifts to '{alias}'",
                        match.group(0),
                        f"Reuse '{term}' or explicitly define the distinction before switching terms.",
                    ))

    if visible and THROAT_CLEARING.search(visible[0][1]):
        findings.append(make_finding(
            "W003", "warning", path, visible[0][0],
            "Throat-clearing opening", visible[0][1],
            "Open with the reader's problem, thesis, or next action.",
        ))

    dash_count = source.count("—") + source.count("–")
    if dash_count > 2:
        findings.append(make_finding(
            "W004", "warning", path, None,
            f"Em-dash usage exceeds 2 ({dash_count} found)", "",
            "Prefer periods, commas, colons, or parentheses.",
        ))

    sentence_list = split_sentences(prose_lines(source))
    for number, sentence in sentence_list:
        count = words(sentence)
        if count > 45:
            findings.append(make_finding(
                "W006", "warning", path, number,
                f"Sentence is {count} words; review above 45", sentence,
                "Split it unless the length carries necessary causality or nuance.",
            ))

    for index in range(len(sentence_list) - 4):
        window = sentence_list[index:index + 5]
        lengths = [words(sentence) for _, sentence in window]
        if max(lengths) - min(lengths) <= 5:
            findings.append(make_finding(
                "W007", "info", path, window[-1][0],
                "Five consecutive sentences have near-uniform length",
                " | ".join(sentence for _, sentence in window),
                "Create contrast with a short claim, fuller explanation, or fragment.",
            ))
            break

    for paragraph in re.split(r"\n\s*\n", source):
        paragraph_lines = prose_lines(paragraph)
        if not paragraph_lines:
            continue
        paragraph_text = " ".join(clean_line(line) for _, line in paragraph_lines)
        count = words(paragraph_text)
        has_structure = (
            len(paragraph_lines) > 1
            or bool(re.search(r"^\s*(?:[-*+]|\d+[.)])\s+", paragraph, re.MULTILINE))
        )
        if count > 120 and not has_structure:
            findings.append(make_finding(
                "W008", "info", path, paragraph_lines[0][0],
                f"Paragraph is {count} words without a structural break",
                paragraph_text,
                "Add a subheading, list, example, or split the paragraph.",
            ))
        nominalizations = NOMINALIZATION.findall(paragraph_text)
        if count >= 40 and len(nominalizations) >= 5 and len(nominalizations) / count > 0.08:
            findings.append(make_finding(
                "W009", "info", path, paragraph_lines[0][0],
                f"High nominalization density ({len(nominalizations)} candidates)",
                paragraph_text,
                "Put the actor in the subject and the action in an active verb.",
            ))

    maximal = re.compile(
        r"\b(fix your entire life|change everything|transform your life|"
        r"guaranteed success|achieve anything|works for everyone)\b",
        re.IGNORECASE,
    )
    for number, line in visible:
        match = maximal.search(line)
        if match:
            findings.append(make_finding(
                "W015", "review", path, number,
                f"Maximal promise: {match.group(0)}", line,
                "Narrow the promise to a credible outcome and time boundary.",
            ))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit JSON findings")
    parser.add_argument(
        "--strict", action="store_true",
        help="Exit 1 for warnings and review findings",
    )
    args = parser.parse_args()

    findings: list[Finding] = []
    for path in args.paths:
        if not path.is_file():
            print(f"error: file not found: {path}", file=sys.stderr)
            return 2
        findings.extend(check_file(path))

    if args.json:
        print(json.dumps([asdict(item) for item in findings], indent=2, ensure_ascii=False))
    else:
        for item in findings:
            location = f"{item.path}:{item.line}" if item.line else item.path
            print(f"{item.rule} [{item.severity}] {location} — {item.message}")
            if item.text:
                print(f"  matched: {item.text}")
            print(f"  revise:  {item.suggestion}")

    if not findings:
        return 0
    return 1 if args.strict or any(item.severity == "error" for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
