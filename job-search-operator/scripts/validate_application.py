#!/usr/bin/env python3
"""Validate job applications against a canonical career profile."""

import argparse
from datetime import date
import json
import re
from pathlib import Path


REQUIRED_HEADINGS = (
    "Fit Assessment",
    "Cover Letter",
    "Tailored Resume",
    "Application Log",
)
REQUIRED_FIELDS = (
    "Target role",
    "Company",
    "Status",
    "Opportunity score",
    "Next action",
    "Follow-up date",
)
TOP_LEVEL_SINGLETON_LABELS = (
    *REQUIRED_FIELDS,
    "Job URL",
    "Location",
    "Work arrangement",
    "Source",
    "Date identified",
)
STRUCTURED_VALUE_LABELS = frozenset(
    (*REQUIRED_FIELDS,
     "Job URL",
     "Location",
     "Work arrangement",
     "Source",
     "Date identified",
     "Company metadata",
     "Role metadata",
     "Needs",
     "Business problem",
     "Hiring signals",
     "Fit",
     "Evidence",
     "Gaps",
     "Angle",
     "Decision",
     "Human moment",
     "Direction 1",
     "Direction 2",
     "Direction 3",
     "Selection question",
     "Voluntary detail invitation")
)
STRUCTURED_VALUE_LABELS_CASEFOLDED = frozenset(label.casefold() for label in STRUCTURED_VALUE_LABELS)
ROLE_RECORD = re.compile(
    r"(?m)^(#{1,6})[ \t]+([^|\r\n]+?)[ \t]*\|[ \t]*([^|\r\n]+?)"
    r"[ \t]*\|[ \t]*([^|\r\n]+?)[ \t]*$"
)
ROLE_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")
EMPLOYMENT_DATES = re.compile(
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December) \d{4}–(?:"
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December) \d{4}|Present)"
)
LOG_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
EXACT_SCORE = re.compile(r"\d+")
PROVISIONAL_SCORE = re.compile(r"(\d+)–(\d+) provisional; midpoint (\d+)")
USER_VERIFIED_HUMAN_MOMENT = re.compile(
    r"(?im)^\s*-\s+Human moment\s*:\s*User-verified\s+—\s*(.+?)\s*$"
)
# This character is deliberately not Markdown whitespace.  It records where a
# comment was removed so source tokens on either side cannot become syntax.
_COMMENT_BOUNDARY = "\ue000"
_RESERVED_PRIVATE_USE_RANGES = (
    (0xE000, 0xF8FF),
    (0xF0000, 0xFFFFD),
    (0x100000, 0x10FFFD),
)
UNRESOLVED_WORDS = frozenset({
    "tbd", "tbc", "todo", "to do", "pending", "awaiting", "not provided",
    "not available", "not supplied", "unknown", "na", "n a", "none", "null",
    "not applicable", "to be determined", "to be provided", "placeholder",
    "unavailable", "unspecified", "missing",
})
UNRESOLVED_QUALIFIER_PREFIX = re.compile(
    r"(?:tbd|tbc|todo|to do|to be (?:determined|provided)|pending|awaiting|"
    r"not (?:provided|available|supplied)|unknown|n a|na|none|null|"
    r"not applicable|placeholder|unavailable|unspecified|missing)(?:\b|\s)",
    re.IGNORECASE,
)
EXTENDED_PLACEHOLDER_MARKERS = frozenset({"tbd", "todo", "tbc"})
MISSING_FIELD_DESCRIPTOR_WORDS = frozenset({
    "application", "arrangement", "benefit", "benefits", "company", "compensation",
    "date", "deadline", "details", "eligibility", "employer", "interview", "job",
    "location", "name", "position", "recruiter", "role", "salary", "status", "terms",
    "title",
})
GENERIC_COMPANY_MARKER_LABELS = frozenset({
    "account", "agency", "business", "client", "company", "consulting", "firm",
    "organization", "services",
})
WORKFLOW_COMPLETION_VERBS = frozenset({
    "added", "approved", "arranged", "assigned", "built", "chosen",
    "clarified", "completed", "confirmed", "contacted", "created", "decided",
    "defined", "delivered", "determined", "discussed", "done", "drafted",
    "emailed", "filed", "filled", "finalized", "fixed", "notified", "posted",
    "prepared", "provided", "published", "revised", "reviewed", "scheduled",
    "selected", "sent", "shared", "submitted", "supplied", "updated", "verified",
    "written", "resolved", "addressed", "answered", "checked", "researched", "found", "given",
    "held", "left", "made", "paid", "read", "run", "seen", "set", "shown",
    "spoken", "taken", "told", "won",
})
COMPANY_MARKER_DESIGNATORS = frozenset({
    "agency", "bank", "capital", "co", "collective", "company", "consulting",
    "corp", "corporation", "design", "foundation", "group", "health", "holdings",
    "inc", "institute", "labs", "llc", "lp", "ltd", "media", "network", "partners",
    "plc", "services", "software", "solutions", "studios", "systems", "tech",
    "technologies", "technology", "ventures", "works",
})
COMPANY_DOMAIN = re.compile(
    r"(?i)^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
DISTINCTIVE_BRAND_TOKEN = re.compile(
    r"^(?:[A-Za-z]*\d[A-Za-z\d]*|[A-Za-z]*[a-z][A-Z][A-Za-z\d]*)$"
)
WEEKDAY_NAMES = frozenset({
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
})
MONTH_NAMES = frozenset({
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
})
TEMPORAL_PERIOD_WORDS = frozenset({
    "day", "days", "week", "weeks", "month", "months", "quarter", "quarters", "year",
    "years", "morning", "afternoon", "evening", "night", "weekend", "weekends",
})
TEMPORAL_EVENT_WORDS = frozenset({
    "interview", "meeting", "call", "review", "submission", "deadline",
})
REPEATED_CHARACTER_LOG_FILLER = re.compile(r"(?s)^([^\W_])\1{3,}$")


def _read_markdown(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ValueError(f"cannot read {path}: {error}") from error


def _contains_reserved_private_use_code_point(markdown):
    """Return whether Markdown uses an internal scanner-marker code point."""
    return any(
        start <= ord(character) <= end
        for character in markdown
        for start, end in _RESERVED_PRIVATE_USE_RANGES
    )


def _visible_markdown(markdown):
    """Blank fenced code and HTML comments without letting either alter the other's state.

    HTML comments are syntax only outside fenced code; fence delimiters are syntax
    only outside comments. Fenced content becomes spaces, while HTML-comment
    content is replaced by a non-whitespace boundary sentinel except for CR/LF
    bytes.  The sentinel is removed only from text after its surrounding
    structure has been recognized, so comments cannot manufacture Markdown
    syntax by joining their neighboring source tokens.
    """
    visible = list(markdown)
    fence_character = None
    fence_length = 0
    in_comment = False
    offset = 0

    def blank(start, end):
        for index in range(start, end):
            if visible[index] not in "\r\n":
                visible[index] = " "

    def delete(start, end):
        for index in range(start, end):
            if visible[index] not in "\r\n":
                visible[index] = ""

    def boundary(start, end):
        visible[start] = _COMMENT_BOUNDARY
        delete(start + 1, end)

    for line_match in re.finditer(r"[^\r\n]*(?:\r\n|\r|\n|$)", markdown):
        line = line_match.group()
        if not line:
            continue
        line_end = offset + len(line)
        content_end = line_end
        while content_end > offset and markdown[content_end - 1] in "\r\n":
            content_end -= 1
        content = markdown[offset:content_end]

        if fence_character is not None:
            blank(offset, line_end)
            closing = re.match(
                rf"^[ ]{{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*$", content
            )
            if closing:
                fence_character = None
                fence_length = 0
        elif not in_comment:
            opening = re.match(r"^[ ]{0,3}(`{3,}|~{3,})", content)
            if opening:
                fence_character = opening.group(1)[0]
                fence_length = len(opening.group(1))
                blank(offset, line_end)
            else:
                index = offset
                while index < content_end:
                    if not in_comment and markdown.startswith("<!--", index):
                        boundary(index, index + 4)
                        in_comment = True
                        index += 4
                    elif in_comment and markdown.startswith("-->", index):
                        boundary(index, index + 3)
                        in_comment = False
                        index += 3
                    elif in_comment:
                        delete(index, index + 1)
                        index += 1
                    else:
                        index += 1
        else:
            index = offset
            while index < content_end:
                if markdown.startswith("-->", index):
                    boundary(index, index + 3)
                    in_comment = False
                    index += 3
                else:
                    if in_comment:
                        delete(index, index + 1)
                    index += 1
        offset = line_end
    return "".join(visible)


def _semantic_text(value):
    """Remove comment boundaries only after structural parsing has succeeded."""
    return value.replace(_COMMENT_BOUNDARY, "")


def _display_text(value):
    """Render literal scanner-marker code points without leaking parser state."""
    return value.replace(_COMMENT_BOUNDARY, "U+E000")


def _structured_fields(markdown):
    """Yield valid source fields as ``(label, value, is_list_item)`` tuples."""
    for line in markdown.splitlines():
        match = re.fullmatch(r"[ \t]*(?:(-)[ \t]+)?(.+?)[ \t]*:[ \t]*(.*?)[ \t]*", line)
        if match:
            bullet, label, value = match.groups()
            yield _semantic_text(label).strip(), _semantic_text(value).strip(), bool(bullet)


def _headings(markdown):
    """Yield source-valid Markdown headings and their semantic text."""
    for match in re.finditer(r"(?m)^(#{1,6})[ \t]+(.*?)[ \t]*$", markdown):
        yield match, len(match.group(1)), _semantic_text(match.group(2)).strip()


def _field_value(markdown, name):
    return next((value for label, value, _ in _structured_fields(markdown)
                 if label.casefold() == name.casefold()), "")


def _field_values(markdown, name):
    return [value for label, value, _ in _structured_fields(markdown)
            if label.casefold() == name.casefold()]


def _top_level_metadata(markdown):
    """Return the record metadata before the first level-two section."""
    first_section = next((match for match, level, _ in _headings(markdown) if level == 2), None)
    return markdown[:first_section.start()] if first_section else markdown


def _canonical_roles(markdown):
    roles = {}
    for match in ROLE_RECORD.finditer(markdown):
        heading, title, employer, dates = match.groups()
        if len(heading) != 3:
            continue
        title, employer, dates = (_semantic_text(part).strip() for part in (title, employer, dates))
        if _has_valid_employment_dates(dates):
            roles.setdefault(employer.casefold(), set()).add((title, dates))
    return roles


def _role_records(markdown):
    """Return parsed role records with their Markdown heading level."""
    return [
        (len(match.group(1)), *(_semantic_text(part).strip() for part in match.groups()[1:]))
        for match in ROLE_RECORD.finditer(markdown)
    ]


def _role_heading_has_exact_components(line):
    """Return whether a Markdown role heading has exactly three nonempty fields."""
    match = ROLE_HEADING.fullmatch(line)
    return bool(match and len(match.group(2).split("|")) == 3 and all(
        _semantic_text(component).strip() for component in match.group(2).split("|")
    ))


def _malformed_role_headings(markdown):
    """Return pipe-containing headings that cannot be safely parsed as role records."""
    return [
        line for line in markdown.splitlines()
        if line.count("|") >= 2
        and ROLE_HEADING.fullmatch(line)
        and not _role_heading_has_exact_components(line)
    ]


def _has_valid_employment_dates(value):
    return bool(EMPLOYMENT_DATES.fullmatch(value.strip()))


def _section_content(markdown, heading):
    sections = _section_contents(markdown, heading)
    return sections[0] if sections else ""


def _section_contents(markdown, heading):
    """Return every real level-two section with this heading."""
    sections = []
    headings = list(_headings(markdown))
    for index, (match, level, text) in enumerate(headings):
        if level != 2 or text.casefold() != heading.casefold():
            continue
        following = next((candidate for candidate, candidate_level, _ in headings[index + 1:]
                          if candidate_level == 2), None)
        content_end = following.start() if following else len(markdown)
        sections.append(markdown[match.end():content_end].strip())
    return sections


def _canonical_history_role_records(markdown):
    """Return role-like headings inside Canonical Employment History at every level."""
    in_history = False
    records = []
    for line in markdown.splitlines():
        source_heading = re.fullmatch(r"(##)[ \t]+(.*?)[ \t]*", line)
        if (
            source_heading
            and _semantic_text(source_heading.group(2)).strip().casefold()
            == "canonical employment history"
        ):
            in_history = True
            continue
        if not in_history:
            continue
        match = ROLE_RECORD.fullmatch(line)
        if match:
            records.append(
                (len(match.group(1)), *(_semantic_text(part).strip() for part in match.groups()[1:]))
            )
            continue
        if re.match(r"^##[ \t]+", line):
            break
    return records


def _heading_levels(markdown, heading):
    return [
        level for _, level, text in _headings(markdown)
        if text.casefold() == heading.casefold()
    ]


def _resume_content(markdown):
    """Return every real resume block, including role records at every heading level."""
    blocks = []
    headings = list(_headings(markdown))
    for index, (start, level, text) in enumerate(headings):
        if level != 2 or text.casefold() != "tailored resume":
            continue
        end = next((match for match, candidate_level, candidate_text in headings[index + 1:]
                    if candidate_level == 2 and candidate_text.casefold() == "application log"), None)
        block_end = end.start() if end else len(markdown)
        blocks.append(markdown[start.end():block_end])
    return "\n".join(blocks)


def _has_log_entry(section):
    """Return whether a log table has a row with all required meaningful fields."""
    rows = []
    for line in section.splitlines():
        # Table grammar is source structure: comments may be semantic within a
        # cell, but cannot create a leading/trailing pipe or a delimiter run.
        match = re.fullmatch(r"[ \t]*\|([^\r\n|]*(?:\|[^\r\n|]*)+)\|[ \t]*", line)
        if not match:
            continue
        rows.append([cell.strip() for cell in match.group(1).split("|")])
    required_fields = {"date", "action", "result", "next step"}
    for index, row in enumerate(rows[:-1]):
        # A delimiter is entirely structural, so it cannot contain a comment
        # boundary.  Remove boundaries only after this recognition succeeds.
        rendered = "|" + "|".join(row) + "|"
        if not re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", rendered):
            continue
        headers = [_semantic_text(header).casefold() for header in rows[index - 1]] if index else []
        positions = {header: position for position, header in enumerate(headers)}
        if not required_fields.issubset(positions):
            continue
        for data_row in rows[index + 1:]:
            if all(positions[field] < len(data_row) for field in required_fields):
                values = {
                    field: _semantic_text(data_row[positions[field]]).strip()
                    for field in required_fields
                }
            else:
                continue
            if (
                _is_valid_log_date(values["date"])
                and all(_has_substantive_log_value(field, values[field])
                        for field in ("action", "result", "next step"))
            ):
                return True
    return False


def _has_user_verified_human_moment(section):
    """Return whether a completed letter records a non-placeholder user attestation."""
    for label, value, is_list_item in _structured_fields(section):
        if not is_list_item or label.casefold() != "human moment":
            continue
        match = re.fullmatch(r"User-verified\s+—\s*(.+?)\s*", value, flags=re.IGNORECASE)
        if match:
            return _has_substantive_text(match.group(1), minimum_words=3, minimum_characters=12)
    return False


def _is_placeholder_only(value):
    """Return whether a value is only a conventional unresolved placeholder."""
    normalized = value.strip()
    words = _placeholder_words(normalized)
    if not words:
        return True
    if re.fullmatch(r"(?s)\{\{.+?\}\}|\[[^\]]+\]", normalized):
        return True
    return words in UNRESOLVED_WORDS | {"u"} or bool(
        re.fullmatch(r"u (?:not provided|not available|not supplied|unknown|placeholder)", words)
    )


def _placeholder_words(value):
    """Normalize punctuation-separated placeholder wording without touching prose."""
    return " ".join(re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE))


def _has_credible_company_name_signal(value):
    """Recognize a whole-field company-name exception for marker-like tokens.

    A Company value may begin with TBD, TODO, or TBC only when the remainder
    looks like a brand: a non-generic organization noun, a domain, a
    distinctive mixed-case/digit token, or multiple title-shaped brand words.
    Known missing-field descriptors always make the value unresolved. This is
    deliberately a non-semantic shape heuristic, not proof that a name exists.
    """
    marker = re.match(r"(?is)^\s*(?:tbd|todo|tbc)(?=$|[^\w])", value)
    if not marker:
        return False
    remainder = value[marker.end():].strip()
    if not remainder:
        return False

    # ``TBC.com`` has no space after the marker; it is still a whole domain.
    compact_value = value.strip()
    if COMPANY_DOMAIN.fullmatch(compact_value) or COMPANY_DOMAIN.fullmatch(remainder):
        return True

    remainder_words = _placeholder_words(remainder).split()
    if not remainder_words or any(word in MISSING_FIELD_DESCRIPTOR_WORDS for word in remainder_words):
        return False
    if len(remainder_words) == 1:
        word = remainder_words[0]
        if word in GENERIC_COMPANY_MARKER_LABELS:
            return False
        legal_designator = re.fullmatch(r"[,\s]*([A-Za-z]+)\.?", remainder)
        return bool(
            legal_designator and legal_designator.group(1).casefold() in COMPANY_MARKER_DESIGNATORS
        ) or bool(DISTINCTIVE_BRAND_TOKEN.fullmatch(remainder))
    return all(_is_title_shaped_brand_token(token) for token in re.findall(r"\S+", remainder))


def _is_title_shaped_brand_token(token):
    """Return whether one whitespace-delimited company-name token looks brand-like."""
    token = token.strip(".,;:()[]{}'\"")
    return bool(re.fullmatch(
        r"(?:[A-Z][a-z]+(?:[-'][A-Z][a-z]+)*|[A-Za-z]*\d[A-Za-z\d]*|[A-Za-z]*[a-z][A-Z][A-Za-z\d]*)",
        token,
    ))


def _is_workflow_placeholder(value, label=None):
    """Recognize unresolved workflow text in the field where it appears.

    Leading TBD/TODO/TBC tokens are unresolved in every field except Company.
    The Company exception is deliberately structural rather than a global
    next-word allowlist; see ``_has_credible_company_name_signal``.
    """
    words = _placeholder_words(value).split()
    if not words:
        return False
    if words[0] in EXTENDED_PLACEHOLDER_MARKERS:
        return not (
            label and label.casefold() == "company"
            and _has_credible_company_name_signal(value)
        )
    if words[:2] == ["to", "do"]:
        return _is_immediate_to_do_deferral(value)
    return (
        words[:2] == ["to", "be"]
        and len(words) > 2
        and not (label and label.casefold() == "company")
        and _is_completion_participle(words[2])
    )


def _is_completion_participle(word):
    """Recognize completion-oriented past participles in a leading ``To be`` note."""
    return word in WORKFLOW_COMPLETION_VERBS


def _is_immediate_to_do_deferral(value):
    """Recognize temporal ``To do`` placeholders from whitespace token phrases.

    This intentionally examines only the words immediately after ``To do``.
    It therefore catches ``To do on Monday`` but not substantive prose such as
    ``To do more next week`` or the hyphenated word ``in-depth``.
    """
    tokens = [token.strip(".,;:!?()[]{}'\"").casefold() for token in re.findall(r"\S+", value)]
    if len(tokens) < 3 or tokens[:2] != ["to", "do"]:
        return False
    phrase = tokens[2:]
    first = phrase[0]
    if first in {"tonight", "tomorrow", "soon", "later", "asap"} | WEEKDAY_NAMES | MONTH_NAMES:
        return True
    if first in {"by", "before", "after", "when", "once"}:
        return len(phrase) > 1
    if first == "during":
        return len(phrase) > 1 and _starts_temporal_phrase(phrase[1:])
    if first == "within":
        return _starts_temporal_phrase(phrase[1:])
    if first in {"next", "this"}:
        return len(phrase) > 1 and phrase[1] in TEMPORAL_PERIOD_WORDS
    if first in {"at", "on", "in"}:
        return _starts_temporal_phrase(phrase[1:])
    return False


def _starts_temporal_phrase(tokens):
    """Return whether a token phrase begins with a concrete time reference."""
    if not tokens:
        return False
    first = tokens[0]
    if first in WEEKDAY_NAMES | MONTH_NAMES | TEMPORAL_PERIOD_WORDS | TEMPORAL_EVENT_WORDS:
        return True
    if first in {"next", "this"} and len(tokens) > 1:
        return tokens[1] in TEMPORAL_PERIOD_WORDS
    if first in {"a", "an", "the"} and len(tokens) > 1:
        return tokens[1] in TEMPORAL_PERIOD_WORDS | TEMPORAL_EVENT_WORDS
    return first.isdigit() and len(tokens) > 1 and tokens[1] in TEMPORAL_PERIOD_WORDS


def _is_unresolved_value(value, label=None):
    """Return whether a field value is an unresolved marker in a structured field."""
    if _is_placeholder_only(value):
        return True
    normalized = value.strip()
    if _is_workflow_placeholder(normalized, label):
        return True
    qualified_u = re.match(r"(?is)^u(?:[\s_]+|[^\w\s]+\s*)(.+)$", normalized)
    if qualified_u and _is_unresolved_qualifier(qualified_u.group(1)):
        return True
    return False


def _is_unresolved_qualifier(value):
    """Recognize unresolved qualifier phrases only after an explicit U marker."""
    words = _placeholder_words(value)
    return words in UNRESOLVED_WORDS or bool(UNRESOLVED_QUALIFIER_PREFIX.match(words))


def _has_substantive_text(value, minimum_words, minimum_characters):
    """Apply structural text minimums; this cannot prove a claim is true or useful."""
    if _is_unresolved_value(value):
        return False
    words = re.findall(r"[^\W_]+", value, flags=re.UNICODE)
    characters = "".join(words)
    return len(words) >= minimum_words and len(characters) >= minimum_characters


def _has_substantive_log_value(field, value):
    """Validate the concise narrative fields a log entry actually requires.

    A log's action, result, and next step can legitimately be brief (for
    example, "Sent", "No reply", or "Wait").  They still need enough text to
    rule out token filler, and must not be unresolved workflow placeholders.
    """
    if (
        field not in {"action", "result", "next step"}
        or _is_unresolved_value(value)
        or _is_repeated_character_log_filler(value)
    ):
        return False
    words = re.findall(r"[^\W_]+", value, flags=re.UNICODE)
    characters = "".join(words)
    return bool(words) and len(characters) >= 4


def _is_repeated_character_log_filler(value):
    """Reject repeated-character tokens even when separators disguise them."""
    normalized = "".join(re.findall(r"[^\W_]", value.casefold(), flags=re.UNICODE))
    return bool(REPEATED_CHARACTER_LOG_FILLER.fullmatch(normalized))


def _is_valid_log_date(value):
    if not LOG_DATE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _has_substantive_resume(section):
    """Require a multiword resume body detail, not just headings or token filler."""
    for line in section.splitlines():
        content = _semantic_text(re.sub(r"^\s*(?:[-*+]\s+)?", "", line)).strip()
        if not content or content.startswith("#"):
            continue
        if not re.fullmatch(r"[._—–-]+", content) and _has_substantive_text(
            content, minimum_words=2, minimum_characters=10
        ):
            return True
    return False


def _unresolved_structured_values(markdown):
    """Return known Markdown field/list labels whose values are still unknown.

    Only labels defined by the application record format count. This deliberately
    avoids treating placeholder words in narrative prose or arbitrary list notes
    as validation failures.
    """
    unresolved = []
    for label, value, _ in _structured_fields(markdown):
        if label.casefold() in STRUCTURED_VALUE_LABELS_CASEFOLDED and _is_unresolved_value(value, label):
            unresolved.append(label)
    return unresolved


def _has_incomplete_cover_letter_marker(section):
    """Recognize structured drafting state, not ordinary prose using the same words."""
    return bool(
        re.search(
            r"(?im)^\s*-\s+Status\s*:\s*(?:incomplete|awaiting|draft(?:ing)?)\b",
            section,
        )
    )


def _has_unresolved_marker(markdown):
    if re.search(r"\{\{.+?\}\}", markdown):
        return True
    reference_labels = {
        match.group(1).strip().casefold()
        for match in re.finditer(r"(?im)^\s*\[([^\]\n]+)\]:", markdown)
    }
    for match in re.finditer(r"\[[^\]\n]+\](?!\s*(?:\(|\[|:))", markdown):
        line_start = markdown.rfind("\n", 0, match.start()) + 1
        before_marker = markdown[line_start:match.start()]
        marker = match.group(0)[1:-1]
        if marker.strip().casefold() in reference_labels:
            continue
        if re.fullmatch(r"\s*(?:[xX])?\s*", marker) and re.fullmatch(
            r"\s*(?:>\s*)*[-*+]\s+", before_marker
        ):
            continue
        return True
    return False


def validate_application(application, profile):
    """Return errors and warnings found in an application Markdown file."""
    application_markdown = _read_markdown(application)
    profile_markdown = _read_markdown(profile)
    errors = []
    if _contains_reserved_private_use_code_point(application_markdown):
        errors.append("application contains reserved Unicode private-use code point")
    if _contains_reserved_private_use_code_point(profile_markdown):
        errors.append("canonical profile contains reserved Unicode private-use code point")
    if errors:
        return {"errors": errors, "warnings": []}

    application_text = _visible_markdown(application_markdown)
    profile_text = _visible_markdown(profile_markdown)
    metadata = _top_level_metadata(application_text)
    for heading in REQUIRED_HEADINGS:
        levels = _heading_levels(application_text, heading)
        level_two_count = levels.count(2)
        if not level_two_count:
            if levels:
                errors.append(f"required heading must use level two: {heading}")
            else:
                errors.append(f"missing required heading: {heading}")
        elif level_two_count > 1:
            errors.append(f"required heading must appear exactly once: {heading}")
        elif any(level != 2 for level in levels):
            errors.append(f"required heading must use level two: {heading}")
    for field in REQUIRED_FIELDS:
        if not _field_value(metadata, field):
            errors.append(f"missing required field: {field}")
    for label in TOP_LEVEL_SINGLETON_LABELS:
        if len(_field_values(metadata, label)) > 1:
            errors.append(f"top-level singleton metadata must appear exactly once: {label}")
    score = _field_value(metadata, "Opportunity score")
    provisional_match = PROVISIONAL_SCORE.fullmatch(score) if score else None
    if score and EXACT_SCORE.fullmatch(score):
        exact_score = int(score)
        if not 20 <= exact_score <= 100:
            errors.append("Opportunity score must be a whole number from 20–100 or a provisional range")
    elif provisional_match:
        lower, upper, midpoint = (int(value) for value in provisional_match.groups())
        if not (
            20 <= lower <= 100
            and 20 <= upper <= 100
            and lower <= upper
            and lower <= midpoint <= upper
            and midpoint * 2 == lower + upper
        ):
            errors.append(
                "provisional Opportunity score must use 20–100 bounds and an exact midpoint"
            )
    elif score:
        errors.append("Opportunity score must use an approved exact or provisional format")
    if _has_unresolved_marker(application_text):
        errors.append("unresolved marker in application")
    canonical_history = _section_content(profile_text, "Canonical Employment History")
    canonical_roles = _canonical_roles(canonical_history)
    canonical_role_records = _canonical_history_role_records(profile_text)
    if canonical_history and not canonical_roles:
        errors.append(
            "Canonical Employment History has entries but no parseable role headings; "
            "use a level-three heading formatted as Held Title | Employer | Month YYYY–Month YYYY"
        )
    if any(level != 3 for level, *_ in canonical_role_records):
        errors.append("Canonical Employment History role records must use level-three headings")
    if _malformed_role_headings(canonical_history):
        errors.append(
            "Canonical Employment History role records must contain exactly three pipe-separated components"
        )
    if any(not _has_valid_employment_dates(dates) for _, _, _, dates in canonical_role_records):
        errors.append(
            "Canonical Employment History role records must use Month YYYY–Month YYYY or Month YYYY–Present dates"
        )
    resume = _resume_content(application_text)
    if _malformed_role_headings(resume):
        errors.append("Tailored Resume role records must contain exactly three pipe-separated components")
    for level, title, employer, dates in _role_records(resume):
        if level != 3:
            errors.append("Tailored Resume role records must use level-three headings")
        if not _has_valid_employment_dates(dates):
            errors.append(
                "Tailored Resume role records must use Month YYYY–Month YYYY or Month YYYY–Present dates"
            )
        employer_key = employer.casefold()
        canonical_matches = canonical_roles.get(employer_key, set())
        if not canonical_matches:
            errors.append(
                f"{_display_text(title)} at {_display_text(employer_key)} is not in canonical employment history"
            )
        elif (title, dates) not in canonical_matches:
            expected = "; ".join(
                f"{canonical_title} | {canonical_dates}"
                for canonical_title, canonical_dates in sorted(canonical_matches)
            )
            errors.append(
                f"{_display_text(title)} at {_display_text(employer)} conflicts with canonical role "
                f"{_display_text(expected)}"
            )
    if _field_value(metadata, "Status").casefold() == "ready":
        for label in _unresolved_structured_values(application_text):
            errors.append(f"Ready application has unresolved placeholder in {label}")
        if not _has_substantive_resume(resume):
            errors.append("Ready application has an empty Tailored Resume")
        if not any(
            level == 3 and (title, dates) in canonical_roles.get(employer.casefold(), set())
            for level, title, employer, dates in _role_records(resume)
        ):
            errors.append(
                "Ready application requires at least one level-three canonical role record in Tailored Resume"
            )
        cover_letter = _section_content(application_text, "Cover Letter")
        if not cover_letter or _has_incomplete_cover_letter_marker(cover_letter):
            errors.append("Ready application has incomplete Cover Letter")
        if not _has_user_verified_human_moment(cover_letter):
            errors.append(
                "Ready application requires a non-placeholder user-verified Human moment record"
            )
        if not any(_has_log_entry(section) for section in _section_contents(application_text, "Application Log")):
            errors.append("Ready application has an empty Application Log")
    return {"errors": errors, "warnings": []}


def find_duplicates(applications_directory):
    """Return duplicate valid-source identities, skipping reserved-marker files."""
    directory = Path(applications_directory)
    if not directory.is_dir():
        raise ValueError(f"applications directory is not a directory: {directory}")
    identities = {}
    for path in sorted(directory.glob("*.md")):
        markdown = _read_markdown(path)
        if _contains_reserved_private_use_code_point(markdown):
            continue
        content = _visible_markdown(markdown)
        identity = (
            " ".join(_field_value(content, "Company").split()).casefold(),
            " ".join(_field_value(content, "Target role").split()).casefold(),
        )
        if all(identity):
            identities.setdefault(identity, []).append(str(path))
    return {
        " | ".join(_display_text(part) for part in identity): paths
        for identity, paths in identities.items() if len(paths) > 1
    }


def main(argv=None):
    """Validate an application and print JSON results."""
    parser = argparse.ArgumentParser()
    parser.add_argument("application")
    parser.add_argument("profile")
    parser.add_argument("--applications-dir")
    arguments = parser.parse_args(argv)
    try:
        result = validate_application(arguments.application, arguments.profile)
        if arguments.applications_dir:
            result["duplicates"] = find_duplicates(arguments.applications_dir)
            result["errors"].extend(
                f"duplicate application identity: {identity}"
                for identity in result["duplicates"]
            )
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
