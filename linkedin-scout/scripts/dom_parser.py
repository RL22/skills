"""
dom_parser.py - High-performance DOM parser for LinkedIn search results (Node 2b).
Complies with mps-writing-for-agents: tight, robust, typed, sub-5ms extraction.
"""

import re
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple
from selectolax.parser import HTMLParser, Node

# Ensure directory is on sys.path for robust standalone and package imports
_q4_dir = Path(__file__).resolve().parent
if str(_q4_dir) not in sys.path:
    sys.path.insert(0, str(_q4_dir))

try:
    from schemas import (
        Company,
        DMMessage,
        DMThread,
        EducationItem,
        ExperienceItem,
        JobPosting,
        LinkedInContact,
        LinkedInProfileDetailed,
        NetworkDegree,
        Post,
        canonicalize_linkedin_url,
        extract_company_slug_from_url,
        extract_job_id_from_url,
        extract_post_id_from_url,
        normalize_degree,
        parse_mutual_string,
    )
except ImportError:
    from .schemas import (
        Company,
        DMMessage,
        DMThread,
        EducationItem,
        ExperienceItem,
        JobPosting,
        LinkedInContact,
        LinkedInProfileDetailed,
        NetworkDegree,
        Post,
        canonicalize_linkedin_url,
        extract_company_slug_from_url,
        extract_job_id_from_url,
        extract_post_id_from_url,
        normalize_degree,
        parse_mutual_string,
    )


# Selectors for search card containers ordered by priority
_CONTAINER_SELECTORS = [
    "li.reusable-search__result-container",
    ".reusable-search__result-container",
    "div[data-chameleon-result-urn]",
    "div[data-view-name='search-entity-result-universal-template']",
    "div[role='listitem']",
    "div.entity-result",
]

_DEGREE_PATTERN = re.compile(r"\b(1st|2nd|3rd(?:\+)?)\b", re.IGNORECASE)
_MUTUAL_OTHER_PATTERN = re.compile(r"(\d+)\s+other", re.IGNORECASE)
_MUTUAL_TOTAL_PATTERN = re.compile(r"(\d+)\s+mutual\s+connection", re.IGNORECASE)
_MUTUAL_IS_PATTERN = re.compile(r"is\s+a\s+mutual\s+connection", re.IGNORECASE)
_COMPANY_AT_PATTERN = re.compile(
    r"(?:^|\s)(?:at|@)\s+([A-Za-z0-9][A-Za-z0-9&.,\'\- ]+?)(?=\s*[|•·\n\(\)]|\s+[-–—]\s+|$)",
    re.IGNORECASE,
)
_COMPANY_SNIPPET_PATTERN = re.compile(
    r"Current:\s*(?:.+?\s+(?:at|@)\s+|@\s*)([^•|\n,]+)", re.IGNORECASE
)

# Selectors for job search result card containers, ordered by priority. LinkedIn's job
# search markup churns often, so this list is intentionally liberal/defensive.
_JOB_CARD_SELECTORS = [
    "li.jobs-search-results__list-item",
    "div.job-card-container",
    "li[data-occludable-job-id]",
    "div[data-job-id]",
    "li.scaffold-layout__list-item",
    "div.base-card",
]

# Selectors for the job-criteria label/value list on a single job posting page
# (e.g. "Seniority level", "Employment type", "Job function", "Industries").
_JOB_CRITERIA_SELECTORS = [
    "ul.description__job-criteria-list li.description__job-criteria-item",
    "li.description__job-criteria-item",
    "ul[class*='job-criteria'] li",
]

_COMPACT_NUMBER_PATTERN = re.compile(r"([\d,.]+)\s*([KkMm])?\+?")
_EASY_APPLY_PATTERN = re.compile(r"easy\s*apply", re.IGNORECASE)
_APPLICANT_COUNT_PATTERN = re.compile(r"([\d,]+)\s*applicants?", re.IGNORECASE)
_EMPLOYEE_COUNT_PATTERN = re.compile(r"([\d,.]+[KkMm]?)\s+employees\s+on\s+LinkedIn", re.IGNORECASE)
_FOLLOWER_COUNT_PATTERN = re.compile(r"([\d,.]+[KkMm]?)\s+followers", re.IGNORECASE)
_SALARY_RANGE_PATTERN = re.compile(
    r"(?P<currency>[$€£])?\s*(?P<min>[\d,.]+)\s*(?P<min_suffix>[KkMm])?"
    r"\s*(?:-|–|—|to)\s*"
    r"(?P<currency2>[$€£])?\s*(?P<max>[\d,.]+)\s*(?P<max_suffix>[KkMm])?"
    r"(?:\s*/\s*(?:yr|year))?"
    r"(?:\s*/\s*(?P<interval>yr|year|hr|hour|mo|month|wk|week|day))?",
    re.IGNORECASE,
)
_SALARY_CURRENCY_MAP = {"$": "USD", "€": "EUR", "£": "GBP"}
_SALARY_INTERVAL_MAP = {
    "yr": "yearly", "year": "yearly",
    "mo": "monthly", "month": "monthly",
    "wk": "weekly", "week": "weekly",
    "day": "daily",
    "hr": "hourly", "hour": "hourly",
}

_WORKPLACE_TYPE_MAP = {
    "remote": "remote",
    "hybrid": "hybrid",
    "on-site": "onSite",
    "onsite": "onSite",
    "on site": "onSite",
}
_EMPLOYMENT_TYPE_MAP = {
    "full-time": "fullTime", "full time": "fullTime", "fulltime": "fullTime",
    "part-time": "partTime", "part time": "partTime", "parttime": "partTime",
    "contract": "contract",
    "temporary": "temporary",
    "volunteer": "volunteer",
    "internship": "internship",
    "other": "other",
}
_EXPERIENCE_LEVEL_MAP = {
    "internship": "internship",
    "entry level": "entryLevel", "entry-level": "entryLevel",
    "associate": "associate",
    "mid-senior level": "midSeniorLevel", "mid senior level": "midSeniorLevel",
    "director": "director",
    "executive": "executive",
}
_COMPANY_SIZE_BRACKETS = [
    "1-10", "11-50", "51-200", "201-500", "501-1000",
    "1001-5000", "5001-10000", "10001+",
]

# Selectors for feed "Update" post card containers, ordered by priority. Same card shape
# renders on the home feed, a company's Posts tab, and a person's Activity tab -- markup
# churns often, so this list is intentionally liberal/defensive.
_FEED_CARD_SELECTORS = [
    "div.feed-shared-update-v2",
    "div[data-urn*='activity']",
    "div.occludable-update",
    "div[data-id*='activity']",
]

_HASHTAG_PATTERN = re.compile(r"#(\w+)")

# Selectors for a messaging thread's outer container (used to locate data-thread-urn
# and to scope message-bubble search).
_MESSAGING_THREAD_CONTAINER_SELECTORS = [
    "div[data-thread-urn]",
    "section.msg-thread",
    "div.msg-thread",
    "div.msg-conversation-container",
]

# Selectors for individual message bubbles within an open conversation, ordered by priority.
_MESSAGE_BUBBLE_SELECTORS = [
    "li.msg-s-message-list__event",
    "div.msg-s-event-listitem",
    "li.msg-s-event-listitem",
]


def _find_card_nodes(parser: HTMLParser) -> List[Node]:
    """Locate search result card nodes using prioritized selector cascade."""
    for selector in _CONTAINER_SELECTORS:
        cards = parser.css(selector)
        if cards:
            return cards
    return []


def _extract_profile_url(card: Node) -> Optional[str]:
    """Extract and canonicalize LinkedIn profile URL from card."""
    link = card.css_first(
        "a.app-aware-link[href*='/in/'], "
        "span.entity-result__title-text a[href*='/in/'], "
        "a[data-test-app-aware-link][href*='/in/'], "
        "a[href*='/in/'], "
        "a[href*='linkedin.com/in/']"
    )
    if not link:
        return None

    raw_href = link.attributes.get("href", "")
    if not raw_href:
        return None

    if raw_href.startswith("/"):
        raw_href = f"https://www.linkedin.com{raw_href}"

    canonical = canonicalize_linkedin_url(raw_href)
    if not canonical or "/in/" not in canonical:
        return None

    return canonical


def _extract_urn_id(card: Node, profile_url: str) -> str:
    """Extract entity URN ID from element attributes or fall back to profile slug."""
    # Check card or descendant attributes
    urn = (
        card.attributes.get("data-chameleon-result-urn")
        or card.attributes.get("data-urn")
        or card.attributes.get("data-entity-urn")
    )
    if not urn:
        inner = card.css_first(
            "[data-chameleon-result-urn], [data-urn], [data-entity-urn]"
        )
        if inner:
            urn = (
                inner.attributes.get("data-chameleon-result-urn")
                or inner.attributes.get("data-urn")
                or inner.attributes.get("data-entity-urn")
            )

    if urn:
        return urn.strip()

    # Fallback to handle extracted from canonical URL
    if "/in/" in profile_url:
        handle = profile_url.split("/in/")[1].split("/")[0].split("?")[0].strip()
        if handle:
            return f"urn:li:member:{handle}"

    return f"urn:li:member:unknown_{abs(hash(profile_url))}"


def _extract_name(card: Node) -> str:
    """Extract display name, stripping accessibility artifacts and degree badges."""
    # Look for accessible text node inside title
    aria_node = card.css_first(
        ".entity-result__title-text span[aria-hidden='true'], "
        "a[href*='/in/'] div[id], "
        "a[href*='/in/'] span[aria-hidden='true'], "
        "[data-view-name*='title'] span[aria-hidden='true']"
    )
    if aria_node:
        name = aria_node.text(strip=True)
    else:
        title_node = card.css_first(
            ".entity-result__title-text a, "
            ".entity-result__title-text, "
            "a[href*='/in/']"
        )
        name = title_node.text(strip=True) if title_node else ""

    # Clean accessibility wrappers like "View Jane Doe’s profile"
    if "View " in name and "profile" in name:
        name = re.sub(
            r"View\s+(.*?)(?:’s|\'s)?\s+profile.*", r"\1", name, flags=re.IGNORECASE
        ).strip()

    # Strip trailing connection badges like "• 2nd" or "• 1st"
    name = re.sub(r"\s*[•·].*$", "", name).strip()
    return " ".join(name.split())


def _extract_degree(card: Node) -> NetworkDegree:
    """Extract connection degree (1st, 2nd, 3rd+, or Unknown)."""
    badge = card.css_first(
        ".entity-result__badge-text, "
        ".dist-value, "
        "span[class*='badge-text'], "
        "span[class*='badge']"
    )
    text = badge.text(strip=True) if badge else ""

    if not text:
        title_node = card.css_first(".entity-result__title-text")
        text = title_node.text(strip=True) if title_node else ""

    if not text:
        # Fallback to card text search for degree
        text = card.text(separator=" ")

    match = _DEGREE_PATTERN.search(text)
    if match:
        deg = match.group(1).lower()
        if "1st" in deg:
            return "1st"
        if "2nd" in deg:
            return "2nd"
        if "3rd" in deg:
            return "3rd+"

    return "Unknown"


def _extract_headline_and_location(card: Node) -> Tuple[str, Optional[str]]:
    """Extract member headline and reported location."""
    sub_node = card.css_first(
        ".entity-result__primary-subtitle, "
        "div[data-anonymize='headline'], "
        ".entity-result__summary"
    )
    headline = " ".join(sub_node.text(strip=True).split()) if sub_node else ""

    loc_node = card.css_first(
        ".entity-result__secondary-subtitle, "
        "div[data-anonymize='location'], "
        ".entity-result__location"
    )
    location = " ".join(loc_node.text(strip=True).split()) if loc_node else None

    # Modern card markup fallback: inspect paragraphs
    if not headline:
        p_texts = [p.text(strip=True) for p in card.css("p") if p.text(strip=True)]
        content_ps = []
        for pt in p_texts:
            if "mutual connection" in pt.lower():
                continue
            if re.search(r"[•·]\s*(?:1st|2nd|3rd)", pt):
                continue
            if pt.lower().startswith("connect"):
                continue
            content_ps.append(pt)
        if content_ps:
            headline = content_ps[0]
            if len(content_ps) > 1 and not location:
                location = content_ps[1]

    if location == "":
        location = None

    return headline, location


def _infer_current_company(card: Node, headline: str) -> Optional[str]:
    """Infer current employer from summary insights or headline."""
    # Check snippet/insight text
    snippet_node = card.css_first(
        "p.entity-result__summary, div.entity-result__insights, div.entity-result__snippet"
    )
    if snippet_node:
        snippet_text = snippet_node.text(strip=True)
        sm = _COMPANY_SNIPPET_PATTERN.search(snippet_text)
        if sm:
            company = sm.group(1).strip().rstrip(".,-")
            if company and len(company) > 1:
                return company

    # Check headline for 'at Company' or '@ Company'
    if headline:
        hm = _COMPANY_AT_PATTERN.search(headline)
        if hm:
            company = hm.group(1).strip().rstrip(".,-")
            if company and len(company) > 1:
                return company

    return None


def _extract_mutual_connections(card: Node) -> Tuple[int, List[str]]:
    """Extract mutual connection count and names of sample mutuals."""
    insight_node = card.css_first(
        ".entity-result__simple-insight, "
        ".reusable-search__social-proof-insight, "
        "span.entity-result__simple-insight-text, "
        "div[class*='social-proof']"
    )
    if not insight_node:
        # Fallback to paragraph search in modern card markup
        for p in card.css("p"):
            txt = p.text(strip=True)
            if "mutual connection" in txt.lower():
                sample = [a.text(strip=True) for a in p.css("a") if a.text(strip=True)]
                if _MUTUAL_IS_PATTERN.search(txt):
                    if not sample:
                        lead_m = re.match(r"^(.+?)\s+is\s+a\s+mutual", txt, re.IGNORECASE)
                        if lead_m:
                            sample = [lead_m.group(1).strip()]
                    return max(len(sample), 1), sample
                other_match = _MUTUAL_OTHER_PATTERN.search(txt)
                if other_match:
                    other_count = int(other_match.group(1))
                    total_count = len(sample) + other_count if sample else other_count + 1
                    return total_count, sample
                total_match = _MUTUAL_TOTAL_PATTERN.search(txt)
                if total_match:
                    return int(total_match.group(1)), sample
                return max(len(sample), 1), sample
        return 0, []

    sample: List[str] = []
    # Query anchor tags and designated person name spans
    for elem in insight_node.css("a, span[data-anonymize='person-name'], button"):
        t = " ".join(elem.text(strip=True).split())
        if t and not re.search(r"\d+\s+other|mutual connection", t, re.IGNORECASE):
            sample.append(t)

    text = " ".join(insight_node.text(strip=True).split())

    # Case 1: "Alice Smith and 3 other mutual connections"
    other_match = _MUTUAL_OTHER_PATTERN.search(text)
    if other_match:
        other_count = int(other_match.group(1))
        if not sample:
            lead_m = re.match(r"^([^,]+?)\s+and\s+\d+\s+other", text, re.IGNORECASE)
            if lead_m:
                sample = [lead_m.group(1).strip()]
        total_count = len(sample) + other_count if sample else other_count + 1
        return total_count, sample

    # Case 2: "Alice Smith is a mutual connection"
    if _MUTUAL_IS_PATTERN.search(text):
        if not sample:
            lead_m = re.match(r"^(.+?)\s+is\s+a\s+mutual", text, re.IGNORECASE)
            if lead_m:
                sample = [lead_m.group(1).strip()]
        return max(len(sample), 1), sample

    # Case 3: "5 mutual connections"
    total_match = _MUTUAL_TOTAL_PATTERN.search(text)
    if total_match:
        return int(total_match.group(1)), sample

    # Fallback to count of samples if any
    return len(sample), sample


def parse_linkedin_search_html(html_content: str) -> List[LinkedInContact]:
    """
    Parse LinkedIn search result cards from raw HTML.

    Extracts:
      - name: clean display name
      - headline: professional headline
      - profile_url: canonical LinkedIn URL without tracking tokens
      - degree: connection distance ("1st", "2nd", "3rd+", "Unknown")
      - location: geographic region
      - current_company: inferred current employer
      - mutual_count & mutual_sample: shared connections
      - source: set to "dom_selectolax"

    Performance target: sub-5ms execution time for standard search pages.
    """
    if not html_content or not html_content.strip():
        return []

    parser = HTMLParser(html_content)
    card_nodes = _find_card_nodes(parser)
    if not card_nodes:
        return []

    contacts: List[LinkedInContact] = []
    seen_urls: set = set()

    for card in card_nodes:
        profile_url = _extract_profile_url(card)
        if not profile_url or profile_url in seen_urls:
            continue

        seen_urls.add(profile_url)
        name = _extract_name(card)
        if not name:
            continue

        urn_id = _extract_urn_id(card, profile_url)
        degree = _extract_degree(card)
        headline, location = _extract_headline_and_location(card)
        current_company = _infer_current_company(card, headline)
        mutual_count, mutual_sample = _extract_mutual_connections(card)

        contact = LinkedInContact(
            urn_id=urn_id,
            name=name,
            headline=headline,
            profile_url=profile_url,
            degree=degree,
            location=location,
            current_company=current_company,
            mutual_count=mutual_count,
            mutual_sample=mutual_sample,
            source="dom_selectolax",
        )
        contacts.append(contact)

    return contacts


def parse_linkedin_profile_html(
    html_content: str,
    profile_url_hint: Optional[str] = None,
) -> LinkedInProfileDetailed:
    """
    High-performance extraction of a complete LinkedIn member profile from HTML using selectolax.

    Extracts:
      - Top Card: Full Name, Headline, Location, Degree ("1st", "2nd", "3rd+"), Current Company
      - About / Summary: Complete textual overview
      - Experience History: Chronological list of roles with company, dates, duration, location, bullets
      - Education: Institutions, degrees, fields of study, dates
      - Skills: Listed technical and domain skills
      - Mutual Connections: Total count and sample names

    Target execution time: sub-5ms.
    """
    parser = HTMLParser(html_content)

    # 1. Top Card: Name
    name = ""
    for sel in [
        "h1.text-heading-xlarge",
        "h1[data-anonymize='person-name']",
        "h1.top-card-layout__title",
        ".pv-top-card--list h1",
        "h1",
    ]:
        node = parser.css_first(sel)
        if node:
            t = " ".join(node.text(strip=True).split())
            if t and not re.search(r"search|sign in|join|linkedin", t, re.IGNORECASE):
                name = t
                break

    if not name:
        meta_title = parser.css_first("meta[property='og:title'], meta[name='title']")
        if meta_title:
            raw_title = meta_title.attributes.get("content", "")
            # e.g. "Tony Stark - Head of Growth Engineering - Verdant | LinkedIn"
            name = raw_title.split("-")[0].split("|")[0].strip()

    name = name or "LinkedIn Member"

    # 2. Headline
    headline = ""
    for sel in [
        "div.text-body-medium.break-words",
        "div.top-card-layout__headline",
        "h2.top-card-layout__headline",
        ".pv-text-details__left-panel div.text-body-medium",
        "div.text-body-medium",
    ]:
        node = parser.css_first(sel)
        if node:
            t = " ".join(node.text(strip=True).split())
            if t:
                headline = t
                break

    # 3. Location
    location = None
    for sel in [
        "span.text-body-small.inline.t-black--light.break-words",
        "span.top-card__subline-item",
        ".pv-text-details__left-panel span.text-body-small",
        "span.text-body-small.inline",
    ]:
        node = parser.css_first(sel)
        if node:
            t = " ".join(node.text(strip=True).split())
            if t and not re.search(r"connection|follower|contact info", t, re.IGNORECASE):
                location = t
                break

    # 4. Connection Degree
    degree_str = "Unknown"
    for sel in [
        "span.dist-value",
        "span[class*='dist-value']",
        "span.artdeco-hoverable-trigger",
        ".pv-top-card span[class*='badge']",
    ]:
        node = parser.css_first(sel)
        if node:
            t = node.text(strip=True)
            m = _DEGREE_PATTERN.search(t)
            if m:
                degree_str = m.group(1)
                break

    degree: NetworkDegree = normalize_degree(degree_str)

    # 5. Canonical Profile URL & URN ID
    profile_url = ""
    if profile_url_hint:
        try:
            profile_url = canonicalize_linkedin_url(profile_url_hint)
        except Exception:
            profile_url = profile_url_hint
    if not profile_url:
        meta_url = parser.css_first("meta[property='og:url'], link[rel='canonical']")
        if meta_url:
            raw_url = meta_url.attributes.get("content") or meta_url.attributes.get("href", "")
            try:
                profile_url = canonicalize_linkedin_url(raw_url)
            except Exception:
                pass
    if not profile_url:
        slug = re.sub(r"[^a-zA-Z0-9\-]+", "-", name.lower()).strip("-")
        profile_url = f"https://www.linkedin.com/in/{slug}"

    urn_id = f"urn:li:member:{re.sub(r'[^a-zA-Z0-9_-]+', '', name.lower())}"

    # 6. Mutual Connections
    mutual_count = 0
    mutual_sample: List[str] = []
    mutual_node = parser.css_first(
        "a[href*='facetNetwork'], a[href*='mutual'], .pv-member-badge, "
        "li.inline.t-24.font-normal a, div[class*='mutual']"
    )
    if mutual_node:
        t = mutual_node.text(strip=True)
        m_count, m_sample = parse_mutual_string(t)
        mutual_count = m_count
        mutual_sample = m_sample

    if mutual_count == 0:
        # Fallback text search across all anchors, spans, paragraphs for mutual connection phrasing
        for el in parser.css("span, a, p"):
            t = el.text(strip=True)
            if "mutual connection" in t.lower() or "mutual" in t.lower():
                m_count, m_sample = parse_mutual_string(t)
                if m_count > 0:
                    mutual_count = m_count
                    mutual_sample = m_sample
                    break

    # 7. About Section
    about_text: Optional[str] = None
    for sel in [
        "section#about div.inline-show-more-text",
        "section:has(#about) div.inline-show-more-text",
        "div#about ~ div div.inline-show-more-text",
        "section#about",
        "div[data-generated-suggestion-target='about']",
    ]:
        node = parser.css_first(sel)
        if node:
            # Extract aria-hidden spans if available
            aria_spans = node.css("span[aria-hidden='true']")
            if aria_spans:
                about_text = " ".join([s.text(strip=True) for s in aria_spans if s.text(strip=True)])
            else:
                about_text = " ".join(node.text(strip=True).split())
            if about_text:
                # Strip heading prefix if present
                about_text = re.sub(r"^About\s+", "", about_text, flags=re.IGNORECASE).strip()
                break

    # 8. Work Experience Section
    experience_list: List[ExperienceItem] = []
    exp_container = parser.css_first("section#experience, section:has(#experience), div#experience")
    if exp_container:
        exp_items = exp_container.css("ul.pvs-list > li") or exp_container.css("li.artdeco-list__item")
        for item in exp_items:
            # Check if this item has nested sub-roles (e.g. multi-position tenure at single company)
            sub_roles = item.css("ul.pvs-list > li")
            if sub_roles:
                # Parent has company name in top heading
                parent_spans = [
                    s.text(strip=True) for s in item.css("div.display-flex span[aria-hidden='true']") if s.text(strip=True)
                ]
                company_name = parent_spans[0] if parent_spans else ""
                for s_item in sub_roles:
                    lines = [s.text(strip=True) for s in s_item.css("span[aria-hidden='true']") if s.text(strip=True)]
                    if lines:
                        role_title = lines[0]
                        dates_str = lines[1] if len(lines) > 1 else None
                        desc_str = lines[-1] if len(lines) > 2 and len(lines[-1]) > 40 else None
                        date_range, duration = _split_dates_and_duration(dates_str)
                        experience_list.append(
                            ExperienceItem(
                                title=role_title,
                                company=company_name,
                                date_range=date_range,
                                duration=duration,
                                description=desc_str,
                            )
                        )
            else:
                lines = [s.text(strip=True) for s in item.css("span[aria-hidden='true']") if s.text(strip=True)]
                if lines:
                    role_title = lines[0]
                    comp_raw = lines[1] if len(lines) > 1 else ""
                    comp_clean = comp_raw.split("·")[0].strip() if comp_raw else ""
                    dates_raw = lines[2] if len(lines) > 2 else None
                    loc_raw = lines[3] if len(lines) > 3 and not (len(lines[3]) > 40) else None
                    desc_raw = lines[-1] if len(lines) >= 4 and len(lines[-1]) > 40 else None

                    date_range, duration = _split_dates_and_duration(dates_raw)
                    experience_list.append(
                        ExperienceItem(
                            title=role_title,
                            company=comp_clean or "Unknown",
                            date_range=date_range,
                            duration=duration,
                            location=loc_raw,
                            description=desc_raw,
                        )
                    )

    # 9. Education Section
    education_list: List[EducationItem] = []
    edu_container = parser.css_first("section#education, section:has(#education), div#education")
    if edu_container:
        edu_items = edu_container.css("ul.pvs-list > li") or edu_container.css("li.artdeco-list__item")
        for item in edu_items:
            lines = [s.text(strip=True) for s in item.css("span[aria-hidden='true']") if s.text(strip=True)]
            if lines:
                school = lines[0]
                degree_study = lines[1] if len(lines) > 1 else None
                dates = lines[2] if len(lines) > 2 else None
                education_list.append(
                    EducationItem(
                        school=school,
                        degree=degree_study,
                        date_range=dates,
                    )
                )

    # 10. Skills Section
    skills_list: List[str] = []
    skills_container = parser.css_first("section#skills, section:has(#skills), div#skills")
    if skills_container:
        skill_items = skills_container.css("ul.pvs-list > li") or skills_container.css("li.artdeco-list__item")
        for item in skill_items:
            skill_span = item.css_first("span[aria-hidden='true']")
            if skill_span:
                st = skill_span.text(strip=True)
                if st and st not in skills_list and len(st) < 60:
                    skills_list.append(st)

    # Current company inference
    current_company = None
    if experience_list and any("present" in (e.date_range or "").lower() for e in experience_list):
        for e in experience_list:
            if "present" in (e.date_range or "").lower():
                current_company = e.company
                break
    if not current_company:
        current_company = _infer_current_company(parser.body, headline)

    return LinkedInProfileDetailed(
        urn_id=urn_id,
        name=name,
        headline=headline,
        profile_url=profile_url,
        degree=degree,
        location=location,
        current_company=current_company,
        mutual_count=mutual_count,
        mutual_sample=mutual_sample,
        about=about_text,
        experience=experience_list,
        education=education_list,
        skills=skills_list,
        source="dom_selectolax",
    )


def _split_dates_and_duration(raw_str: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Helper to partition 'Apr 2022 - Present · 2 yrs 6 mos' into date_range and duration."""
    if not raw_str:
        return None, None
    if "·" in raw_str:
        parts = raw_str.split("·", 1)
        return parts[0].strip(), parts[1].strip()
    return raw_str.strip(), None


def _parse_compact_number(text: Optional[str]) -> Optional[int]:
    """Parse LinkedIn's compact number formats ('45,231', '1.2M', '3K') into an int."""
    if not text:
        return None
    try:
        cleaned = text.strip().replace(",", "")
        match = _COMPACT_NUMBER_PATTERN.search(cleaned)
        if not match:
            return None
        raw_num, suffix = match.group(1), match.group(2)
        if not raw_num:
            return None
        num = float(raw_num)
        if suffix:
            suffix = suffix.upper()
            if suffix == "K":
                num *= 1_000
            elif suffix == "M":
                num *= 1_000_000
        return int(round(num))
    except Exception:
        return None


def _map_workplace_type(text: str) -> Optional[str]:
    """Fuzzy-map free text (badge/insight copy) to a WorkplaceType literal."""
    if not text:
        return None
    t = text.lower()
    for key, val in _WORKPLACE_TYPE_MAP.items():
        if key in t:
            return val
    return None


def _map_employment_type(text: Optional[str]) -> Optional[str]:
    """Fuzzy-map a LinkedIn employment-type label to an EmploymentType literal."""
    if not text:
        return None
    t = " ".join(text.strip().lower().split())
    for key, val in _EMPLOYMENT_TYPE_MAP.items():
        if key in t:
            return val
    return None


def _map_experience_level(text: Optional[str]) -> Optional[str]:
    """Fuzzy-map a LinkedIn seniority label to an ExperienceLevel literal."""
    if not text:
        return None
    t = " ".join(text.strip().lower().split())
    for key, val in _EXPERIENCE_LEVEL_MAP.items():
        if key in t:
            return val
    return None


def _map_company_size(text: Optional[str]) -> Optional[str]:
    """Fuzzy-map a LinkedIn 'X employees' string to a CompanySize bracket literal."""
    if not text:
        return None
    try:
        t = text.lower().replace(",", "")
        t = re.sub(r"employees?", "", t).strip()
        t_compact = t.replace("-", "").replace(" ", "")
        for bracket in _COMPANY_SIZE_BRACKETS:
            bracket_compact = bracket.replace("-", "")
            if bracket_compact in t_compact:
                return bracket
        m_range = re.search(r"(\d+)\s*-\s*(\d+)", t)
        if m_range:
            candidate = f"{m_range.group(1)}-{m_range.group(2)}"
            if candidate in _COMPANY_SIZE_BRACKETS:
                return candidate
        m_plus = re.search(r"(\d+)\s*\+", t)
        if m_plus and m_plus.group(1) == "10001":
            return "10001+"
        if t.strip():
            return "Unknown"
    except Exception:
        return None
    return None


def _parse_salary_range(text: Optional[str]) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """Best-effort parse of a LinkedIn salary string (e.g. '$120K/yr - $150K/yr') into
    (salary_min, salary_max, currency, interval). Returns all-None on failure."""
    if not text:
        return None, None, None, None
    try:
        # Resolve the interval first (e.g. "/yr", "/hr") from anywhere in the string, then
        # strip those fragments out so the range regex only has to deal with the two amounts.
        interval = None
        low = text.lower()
        for key, val in _SALARY_INTERVAL_MAP.items():
            if re.search(rf"/\s*{key}\b", low):
                interval = val
                break
        cleaned = re.sub(r"/\s*(?:yr|year|hr|hour|mo|month|wk|week|day)s?\b", "", text, flags=re.IGNORECASE)

        match = _SALARY_RANGE_PATTERN.search(cleaned)
        if not match:
            return None, None, None, None

        def _to_amount(raw: Optional[str], suffix: Optional[str]) -> Optional[float]:
            if not raw:
                return None
            val = float(raw.replace(",", ""))
            if suffix and suffix.upper() == "K":
                val *= 1_000
            elif suffix and suffix.upper() == "M":
                val *= 1_000_000
            return val

        salary_min = _to_amount(match.group("min"), match.group("min_suffix"))
        salary_max = _to_amount(match.group("max"), match.group("max_suffix"))
        if salary_min is None and salary_max is None:
            return None, None, None, None

        currency_symbol = match.group("currency") or match.group("currency2")
        currency = _SALARY_CURRENCY_MAP.get(currency_symbol) if currency_symbol else None

        if not interval:
            for key, val in _SALARY_INTERVAL_MAP.items():
                if re.search(rf"\b{key}\b", low):
                    interval = val
                    break

        return salary_min, salary_max, currency, interval
    except Exception:
        return None, None, None, None


def _find_job_card_nodes(parser: HTMLParser) -> List[Node]:
    """Locate job search result card nodes using a prioritized selector cascade."""
    for selector in _JOB_CARD_SELECTORS:
        try:
            cards = parser.css(selector)
        except Exception:
            cards = []
        if cards:
            return cards
    return []


def _extract_job_link(card: Node) -> Optional[Node]:
    """Locate the primary anchor for a job search card."""
    return card.css_first(
        "a[href*='/jobs/view/'], "
        "a.job-card-list__title, "
        "a.job-card-container__link, "
        "a.base-card__full-link, "
        "a[data-control-id]"
    )


def _extract_job_card_url(card: Node, link: Optional[Node]) -> Optional[str]:
    """Extract the raw job posting URL from a search card."""
    if not link:
        return None
    href = link.attributes.get("href", "")
    if not href:
        return None
    if href.startswith("/"):
        href = f"https://www.linkedin.com{href}"
    return href


def _extract_job_card_title(card: Node, link: Optional[Node]) -> str:
    """Extract the job title text from a search card."""
    for sel in [
        "a.job-card-list__title span[aria-hidden='true']",
        "a.job-card-list__title strong",
        ".job-card-list__title",
        "h3.base-search-card__title",
        "span[aria-hidden='true']",
    ]:
        node = card.css_first(sel)
        if node:
            t = " ".join(node.text(strip=True).split())
            if t:
                return t
    if link:
        t = " ".join(link.text(strip=True).split())
        if t:
            return t
    return ""


def _extract_job_card_company(card: Node) -> str:
    """Extract the hiring company display name from a search card."""
    for sel in [
        ".job-card-container__primary-description",
        ".job-card-container__company-name",
        "a.job-card-container__company-name",
        "h4.base-search-card__subtitle",
        ".artdeco-entity-lockup__subtitle",
        "span.job-card-container__company-name",
    ]:
        node = card.css_first(sel)
        if node:
            t = " ".join(node.text(strip=True).split())
            if t:
                return t
    return ""

def _extract_job_card_location(card: Node) -> Optional[str]:
    """Extract the posted location from a search card."""
    for sel in [
        ".job-card-container__metadata-item",
        "ul.job-card-container__metadata li",
        "span.job-search-card__location",
        ".job-card-container__metadata-wrapper",
    ]:
        node = card.css_first(sel)
        if node:
            t = " ".join(node.text(strip=True).split())
            if t:
                return t
    return None


def parse_linkedin_job_search_html(html_content: str) -> List[JobPosting]:
    """
    Parse LinkedIn job search result cards from raw HTML (/jobs/search/...).

    Extracts the lightweight card fields only:
      - title, job_url, company_name, location
      - workplace_type / easy_apply / date_posted when present in card metadata
    Fields only derivable from a full posting (description, salary, seniority,
    industries, skills) are left None/empty.
    """
    if not html_content or not html_content.strip():
        return []

    parser = HTMLParser(html_content)
    card_nodes = _find_job_card_nodes(parser)
    if not card_nodes:
        return []

    postings: List[JobPosting] = []
    seen_urls: set = set()

    for card in card_nodes:
        try:
            link = _extract_job_link(card)
            raw_url = _extract_job_card_url(card, link)
            if not raw_url:
                continue

            title = _extract_job_card_title(card, link)
            if not title:
                continue

            job_id = extract_job_id_from_url(raw_url) or f"unknown_{abs(hash(raw_url))}"
            if job_id in seen_urls:
                continue
            seen_urls.add(job_id)

            company_name = _extract_job_card_company(card) or "Unknown"
            location = _extract_job_card_location(card)

            card_text = card.text(separator=" ")
            workplace_type = _map_workplace_type(card_text)
            easy_apply = True if _EASY_APPLY_PATTERN.search(card_text) else None

            date_posted = None
            time_node = card.css_first("time")
            if time_node:
                date_posted = (
                    time_node.attributes.get("datetime")
                    or time_node.text(strip=True)
                    or None
                )

            posting = JobPosting(
                job_id=job_id,
                title=title,
                company_name=company_name,
                job_url=raw_url,
                location=location,
                workplace_type=workplace_type,
                easy_apply=easy_apply,
                date_posted=date_posted,
                source="dom_selectolax",
            )
            postings.append(posting)
        except Exception:
            continue

    return postings


def _extract_job_criteria(parser: HTMLParser) -> dict:
    """Generically parse the job-criteria label/value list into a lowercase-keyed dict."""
    criteria: dict = {}
    items: List[Node] = []
    for sel in _JOB_CRITERIA_SELECTORS:
        try:
            items = parser.css(sel)
        except Exception:
            items = []
        if items:
            break

    for item in items:
        try:
            label_node = item.css_first(
                "h3, .description__job-criteria-subheader, dt, span.description__job-criteria-subheader"
            )
            value_node = item.css_first(
                "span.description__job-criteria-text, dd, span:not(.description__job-criteria-subheader)"
            )
            label = label_node.text(strip=True) if label_node else ""
            value = value_node.text(strip=True) if value_node else ""
            if not label:
                continue
            criteria[label.strip().lower()] = value.strip()
        except Exception:
            continue

    return criteria


def parse_linkedin_job_posting_html(
    html_content: str,
    job_url_hint: Optional[str] = None,
) -> Optional[JobPosting]:
    """
    Parse a single LinkedIn job posting detail page (/jobs/view/{id}/) into a rich JobPosting.

    Extracts title, company (+company_id when resolvable), location, description,
    applicant_count, date_posted, easy_apply, salary range (best-effort), and the
    job-criteria list (seniority -> experience_level, employment type, job function,
    industries). Returns None if no job title/container can be found at all.
    """
    if not html_content or not html_content.strip():
        return None

    parser = HTMLParser(html_content)

    # 1. Title
    title = ""
    for sel in [
        "h1.top-card-layout__title",
        "h1.job-details-jobs-unified-top-card__job-title",
        "h1.jobs-unified-top-card__job-title",
        "h1.t-24",
        "h1",
    ]:
        node = parser.css_first(sel)
        if node:
            t = " ".join(node.text(strip=True).split())
            if t:
                title = t
                break

    if not title:
        meta_title = parser.css_first("meta[property='og:title'], meta[name='title']")
        if meta_title:
            raw_title = meta_title.attributes.get("content", "")
            title = raw_title.split("|")[0].strip()

    if not title:
        return None

    # 2. Company name + company link (for company_id)
    company_link = parser.css_first(
        "a.topcard__org-name-link, "
        "a.jobs-unified-top-card__company-name, "
        "span.jobs-unified-top-card__company-name a, "
        "a[href*='/company/']"
    )
    company_name = ""
    if company_link:
        company_name = " ".join(company_link.text(strip=True).split())
    if not company_name:
        for sel in [
            ".jobs-unified-top-card__company-name",
            "span.topcard__flavor",
            ".job-details-jobs-unified-top-card__company-name",
        ]:
            node = parser.css_first(sel)
            if node:
                t = " ".join(node.text(strip=True).split())
                if t:
                    company_name = t
                    break
    company_name = company_name or "Unknown"

    company_id = None
    if company_link:
        href = company_link.attributes.get("href", "")
        if href:
            try:
                company_id = extract_company_slug_from_url(href)
            except Exception:
                company_id = None

    # 3. Location
    location = None
    for sel in [
        "span.topcard__flavor--bullet",
        "span.jobs-unified-top-card__bullet",
        ".job-details-jobs-unified-top-card__primary-description-container",
        ".topcard__flavor-row span",
    ]:
        node = parser.css_first(sel)
        if node:
            t = " ".join(node.text(strip=True).split())
            if t:
                location = t
                break

    # 4. Job URL
    job_url = job_url_hint
    if not job_url:
        meta_url = parser.css_first("meta[property='og:url'], link[rel='canonical']")
        if meta_url:
            job_url = meta_url.attributes.get("content") or meta_url.attributes.get("href")
    if not job_url:
        job_url = "https://www.linkedin.com/jobs/view/0/"

    job_id = extract_job_id_from_url(job_url) or f"unknown_{abs(hash(job_url))}"

    # 5. Description
    description = None
    for sel in [
        "div.description__text",
        "div.jobs-description__content",
        "div.jobs-box__html-content",
        "section.description",
        "div[class*='jobs-description']",
    ]:
        node = parser.css_first(sel)
        if node:
            aria_spans = node.css("span[aria-hidden='true']")
            if aria_spans:
                description = " ".join(s.text(strip=True) for s in aria_spans if s.text(strip=True))
            else:
                description = " ".join(node.text(strip=True).split())
            if description:
                break

    # 6. Applicant count
    applicant_count = None
    for sel in [
        "span.num-applicants__caption",
        "span.jobs-unified-top-card__applicant-count",
        "figcaption.num-applicants__caption",
    ]:
        node = parser.css_first(sel)
        if node:
            m = _APPLICANT_COUNT_PATTERN.search(node.text(strip=True))
            if m:
                applicant_count = _parse_compact_number(m.group(1))
                break
    if applicant_count is None:
        m = _APPLICANT_COUNT_PATTERN.search(parser.body.text(separator=" ") if parser.body else "")
        if m:
            applicant_count = _parse_compact_number(m.group(1))

    # 7. Date posted
    date_posted = None
    time_node = parser.css_first("span.posted-time-ago__text, time")
    if time_node:
        date_posted = time_node.attributes.get("datetime") or time_node.text(strip=True) or None

    # 8. Easy apply
    body_text = parser.body.text(separator=" ") if parser.body else ""
    easy_apply = True if _EASY_APPLY_PATTERN.search(body_text) else None

    # 9. Salary (best-effort)
    salary_min = salary_max = None
    salary_currency = salary_interval = None
    for sel in [
        ".job-details-jobs-unified-top-card__job-insight",
        "span.salary",
        "div.compensation__salary",
    ]:
        node = parser.css_first(sel)
        if node:
            t = node.text(strip=True)
            if "$" in t or "€" in t or "£" in t:
                salary_min, salary_max, salary_currency, salary_interval = _parse_salary_range(t)
                if salary_min is not None or salary_max is not None:
                    break

    # 10. Job criteria list (seniority, employment type, job function, industries)
    criteria = _extract_job_criteria(parser)
    experience_level = _map_experience_level(criteria.get("seniority level"))
    employment_type = _map_employment_type(criteria.get("employment type"))
    job_function = criteria.get("job function") or None
    industries_raw = criteria.get("industries")
    industries = (
        [s.strip() for s in industries_raw.split(",") if s.strip()] if industries_raw else []
    )

    try:
        return JobPosting(
            job_id=job_id,
            title=title,
            company_name=company_name,
            company_id=company_id,
            job_url=job_url,
            location=location,
            employment_type=employment_type,
            experience_level=experience_level,
            job_function=job_function,
            industries=industries,
            date_posted=date_posted,
            applicant_count=applicant_count,
            easy_apply=easy_apply,
            description=description,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            salary_interval=salary_interval,
            source="dom_selectolax",
        )
    except Exception:
        return None


def _extract_definition_pairs(parser: HTMLParser) -> dict:
    """Generically extract label -> value text from dt/dd-style definition pairs
    used on LinkedIn's company About page overview."""
    pairs: dict = {}
    try:
        for dt in parser.css("dt"):
            label = dt.text(strip=True)
            if not label:
                continue
            dd = dt.next
            hops = 0
            while dd is not None and getattr(dd, "tag", None) != "dd" and hops < 5:
                dd = dd.next
                hops += 1
            if dd is not None and getattr(dd, "tag", None) == "dd":
                pairs[label.strip().lower()] = " ".join(dd.text(strip=True).split())
    except Exception:
        pass

    # Fallback: LinkedIn also renders "Label\nValue" pairs inside generic
    # definition-term/definition-text wrapper divs.
    try:
        for term in parser.css(
            "div.org-page-details__definition-term, dt.org-page-details__definition-term"
        ):
            label = term.text(strip=True)
            if not label or label.lower() in pairs:
                continue
            sib = term.next
            hops = 0
            while sib is not None and hops < 5:
                if getattr(sib, "tag", None) in (
                    "div",
                    "dd",
                ) and "definition-text" in (sib.attributes.get("class") or ""):
                    pairs[label.strip().lower()] = " ".join(sib.text(strip=True).split())
                    break
                sib = sib.next
                hops += 1
    except Exception:
        pass

    return pairs


def parse_linkedin_company_html(
    html_content: str,
    company_url_hint: Optional[str] = None,
) -> Optional[Company]:
    """
    Parse a LinkedIn company About/overview page (/company/{slug}/about/ or /company/{slug}/).

    Extracts name, website, industry, company_size, employee_count, follower_count,
    headquarters, founded, description, specialties, and logo_url. Returns None if no
    company name can be found.
    """
    if not html_content or not html_content.strip():
        return None

    parser = HTMLParser(html_content)

    # 1. Name
    name = ""
    for sel in [
        "h1.org-top-card-summary__title",
        "h1.top-card-layout__title",
        "h1[data-test-id='org-name']",
        "h1.org-top-card-summary__title-text",
        "h1",
    ]:
        node = parser.css_first(sel)
        if node:
            t = " ".join(node.text(strip=True).split())
            if t:
                name = t
                break

    if not name:
        meta_title = parser.css_first("meta[property='og:title'], meta[name='title']")
        if meta_title:
            raw_title = meta_title.attributes.get("content", "")
            name = raw_title.split("|")[0].strip()

    if not name:
        return None

    # 2. Company URL
    company_url = company_url_hint
    if not company_url:
        meta_url = parser.css_first("meta[property='og:url'], link[rel='canonical']")
        if meta_url:
            company_url = meta_url.attributes.get("content") or meta_url.attributes.get("href")
    if not company_url:
        slug = re.sub(r"[^a-zA-Z0-9\-]+", "-", name.lower()).strip("-")
        company_url = f"https://www.linkedin.com/company/{slug}/"

    company_id = extract_company_slug_from_url(company_url) or ""

    # 3. Definition pairs (About overview grid: Website, Industry, Company size, HQ, Founded, Specialties)
    pairs = _extract_definition_pairs(parser)

    # 4. Website
    website = None
    website_val = pairs.get("website")
    if website_val:
        website = website_val
    else:
        for sel in [
            "a.org-top-card-primary-actions__action[href^='http']",
            "a[data-tracking-control-name*='website']",
        ]:
            node = parser.css_first(sel)
            if node:
                href = node.attributes.get("href")
                if href and "linkedin.com" not in href:
                    website = href
                    break

    # 5. Industry
    industry = pairs.get("industry")
    if not industry:
        node = parser.css_first(
            "div.org-top-card-summary-info-list__info-item, "
            "span.org-top-card-summary-info-list__info-item"
        )
        if node:
            t = " ".join(node.text(strip=True).split())
            if t and "employee" not in t.lower() and "follower" not in t.lower():
                industry = t

    # 6. Company size
    company_size = _map_company_size(pairs.get("company size"))

    # 7. Employee / follower counts (page-wide regex search, best-effort)
    body_text = parser.body.text(separator=" ") if parser.body else ""
    employee_count = None
    m_emp = _EMPLOYEE_COUNT_PATTERN.search(body_text)
    if m_emp:
        employee_count = _parse_compact_number(m_emp.group(1))

    follower_count = None
    m_fol = _FOLLOWER_COUNT_PATTERN.search(body_text)
    if m_fol:
        follower_count = _parse_compact_number(m_fol.group(1))

    # 8. Headquarters / Founded
    headquarters = pairs.get("headquarters")
    founded = pairs.get("founded")

    # 9. Description
    description = None
    for sel in [
        "p.org-about-us-organization-description__text",
        "section.org-about-module p",
        "p[data-test-id='about-us__description']",
        "div.org-about-us-organization-description",
    ]:
        node = parser.css_first(sel)
        if node:
            t = " ".join(node.text(strip=True).split())
            if t:
                description = t
                break

    # 10. Specialties
    specialties: List[str] = []
    specialties_raw = pairs.get("specialties")
    if specialties_raw:
        specialties = [s.strip() for s in specialties_raw.split(",") if s.strip()]

    # 11. Logo
    logo_url = None
    for sel in [
        "img.org-top-card-primary-content__logo",
        "img.artdeco-entity-image",
        "img[class*='logo']",
    ]:
        node = parser.css_first(sel)
        if node:
            src = node.attributes.get("src")
            if src:
                logo_url = src
                break

    try:
        return Company(
            company_id=company_id or "unknown",
            name=name,
            company_url=company_url,
            website=website,
            industry=industry,
            company_size=company_size,
            employee_count=employee_count,
            follower_count=follower_count,
            headquarters=headquarters,
            founded=founded,
            description=description,
            specialties=specialties,
            logo_url=logo_url,
            source="dom_selectolax",
        )
    except Exception:
        return None


def _find_feed_card_nodes(parser: HTMLParser) -> List[Node]:
    """Locate feed 'Update' post card nodes using a prioritized selector cascade."""
    for selector in _FEED_CARD_SELECTORS:
        try:
            cards = parser.css(selector)
        except Exception:
            cards = []
        if cards:
            return cards
    return []


def _extract_feed_post_url(card: Node) -> Optional[str]:
    """Resolve a raw post URL from a feed card's data-urn attribute or a /feed/update/ anchor."""
    for attr_name in ("data-urn", "data-id"):
        urn = card.attributes.get(attr_name)
        if urn and "activity" in urn:
            return f"https://www.linkedin.com/feed/update/{urn}/"

    inner = card.css_first("[data-urn*='activity'], [data-id*='activity']")
    if inner:
        urn = inner.attributes.get("data-urn") or inner.attributes.get("data-id")
        if urn and "activity" in urn:
            return f"https://www.linkedin.com/feed/update/{urn}/"

    link = card.css_first("a[href*='/feed/update/']")
    if link:
        href = link.attributes.get("href", "")
        if href:
            if href.startswith("/"):
                href = f"https://www.linkedin.com{href}"
            return href

    return None


def _extract_feed_author(card: Node) -> Tuple[str, str, Optional[str]]:
    """Extract (author_name, author_type, author_id) from a feed card's actor block."""
    company_link = card.css_first(
        "a.update-components-actor__meta-link[href*='/company/'], "
        "a[data-view-name='feed-actor-name'][href*='/company/'], "
        "a[href*='/company/']"
    )
    if company_link:
        name_node = company_link.css_first("span[aria-hidden='true']") or company_link
        author_name = " ".join(name_node.text(strip=True).split())
        author_name = re.sub(r"\s*[•·].*$", "", author_name).strip()
        href = company_link.attributes.get("href", "")
        author_id = None
        if href:
            if href.startswith("/"):
                href = f"https://www.linkedin.com{href}"
            try:
                author_id = extract_company_slug_from_url(href)
            except Exception:
                author_id = None
        if author_name:
            return author_name, "company", author_id

    person_link = card.css_first(
        "a.update-components-actor__meta-link[href*='/in/'], "
        "a[data-view-name='feed-actor-name'][href*='/in/'], "
        "span.feed-shared-actor__name a[href*='/in/'], "
        "a[href*='/in/']"
    )
    if person_link:
        name_node = person_link.css_first("span[aria-hidden='true']") or person_link
        author_name = " ".join(name_node.text(strip=True).split())
        author_name = re.sub(r"\s*[•·].*$", "", author_name).strip()
        href = person_link.attributes.get("href", "")
        author_id = None
        if href:
            if href.startswith("/"):
                href = f"https://www.linkedin.com{href}"
            try:
                canonical = canonicalize_linkedin_url(href)
                if canonical and "/in/" in canonical:
                    handle = canonical.split("/in/")[1].split("/")[0]
                    if handle:
                        author_id = f"urn:li:member:{handle}"
            except Exception:
                author_id = None
        if author_name:
            return author_name, "person", author_id

    # Last-resort: generic actor name node with no resolvable href.
    name_node = card.css_first(
        "span.feed-shared-actor__name, "
        "span.update-components-actor__name, "
        "span[aria-hidden='true']"
    )
    if name_node:
        author_name = " ".join(name_node.text(strip=True).split())
        if author_name:
            return author_name, "person", None

    return "", "person", None


def _extract_feed_text(card: Node) -> Optional[str]:
    """Extract rendered post body text (may be truncated with '...more')."""
    for sel in [
        "div.feed-shared-text",
        "span.break-words",
        "div.feed-shared-update-v2__description",
        "div[data-view-name='feed-full-update-text']",
    ]:
        node = card.css_first(sel)
        if node:
            aria_spans = node.css("span[aria-hidden='true']")
            if aria_spans:
                text = " ".join(s.text(strip=True) for s in aria_spans if s.text(strip=True))
            else:
                text = " ".join(node.text(strip=True).split())
            if text:
                text = re.sub(r"\.\.\.\s*more\s*$", "", text, flags=re.IGNORECASE).strip()
                return text or None
    return None


def _extract_feed_posted_at(card: Node) -> Optional[str]:
    """Extract the time-ago label rendered near the post author."""
    for sel in [
        "span.feed-shared-actor__sub-description",
        "span.update-components-actor__sub-description",
        "time",
    ]:
        node = card.css_first(sel)
        if node:
            if node.tag == "time":
                t = node.attributes.get("datetime") or node.text(strip=True)
            else:
                aria = node.css_first("span[aria-hidden='true']")
                t = aria.text(strip=True) if aria else node.text(strip=True)
            t = " ".join((t or "").split())
            # Strip trailing " • Edited" / visibility icons text if present.
            t = re.sub(r"\s*[•·]\s*Edited.*$", "", t, flags=re.IGNORECASE).strip()
            if t:
                return t
    return None


def _extract_feed_counts(card: Node) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Extract (like_count, comment_count, repost_count) from the social-counts block."""
    like_count = comment_count = repost_count = None

    counts_node = card.css_first(
        "div.social-details-social-counts, "
        "ul.social-details-social-counts, "
        "div[class*='social-counts']"
    )
    if not counts_node:
        return None, None, None

    for el in counts_node.css("span, button, li"):
        label = " ".join(
            (el.attributes.get("aria-label") or el.text(strip=True) or "").split()
        )
        if not label:
            continue
        low = label.lower()
        if re.search(r"repost|share", low):
            val = _parse_compact_number(label)
            if val is not None:
                repost_count = val
        elif re.search(r"comment", low):
            val = _parse_compact_number(label)
            if val is not None:
                comment_count = val
        elif re.search(r"reaction|like", low):
            val = _parse_compact_number(label)
            if val is not None:
                like_count = val

    return like_count, comment_count, repost_count


def parse_linkedin_feed_html(html_content: str) -> List[Post]:
    """
    Parse LinkedIn feed 'Update' post cards from raw HTML.

    Works against the home feed (/feed/), a company's Posts tab
    (/company/{slug}/posts/), and a person's Activity tab (/in/{handle}/recent-activity/) --
    all three render the same feed-shared-update card structure.

    Extracts post_url/post_id, author_name/author_type/author_id, text, hashtags,
    posted_at, and engagement counts (like/comment/repost). Cards where no post_url/activity
    id can be resolved are skipped -- unidentifiable posts are never included.
    """
    if not html_content or not html_content.strip():
        return []

    parser = HTMLParser(html_content)
    card_nodes = _find_feed_card_nodes(parser)
    if not card_nodes:
        return []

    posts: List[Post] = []
    seen_ids: set = set()

    for card in card_nodes:
        try:
            raw_url = _extract_feed_post_url(card)
            if not raw_url:
                continue

            post_id = extract_post_id_from_url(raw_url)
            if not post_id:
                continue
            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)

            author_name, author_type, author_id = _extract_feed_author(card)
            if not author_name:
                continue

            text = _extract_feed_text(card)
            hashtags = _HASHTAG_PATTERN.findall(text) if text else []
            posted_at = _extract_feed_posted_at(card)
            like_count, comment_count, repost_count = _extract_feed_counts(card)

            post = Post(
                post_id=post_id,
                post_url=raw_url,
                author_name=author_name,
                author_type=author_type,
                author_id=author_id,
                text=text,
                hashtags=hashtags,
                posted_at=posted_at,
                like_count=like_count,
                comment_count=comment_count,
                repost_count=repost_count,
                source="dom_selectolax",
            )
            posts.append(post)
        except Exception:
            continue

    return posts


def _extract_thread_container(parser: HTMLParser) -> Optional[Node]:
    """Locate the outer messaging-thread container node, if present."""
    for selector in _MESSAGING_THREAD_CONTAINER_SELECTORS:
        try:
            node = parser.css_first(selector)
        except Exception:
            node = None
        if node:
            return node
    return None


def _extract_thread_participant(
    parser: HTMLParser, container: Optional[Node]
) -> Tuple[str, Optional[str]]:
    """Extract (participant_name, participant_url) from the conversation header."""
    scope = container if container is not None else parser.root

    name_node = None
    for sel in [
        "h2.msg-entity-lockup__entity-title",
        "h2[class*='entity-lockup__entity-title']",
        "h2.msg-thread__link-to-profile",
        "a.msg-thread__link-to-profile span[aria-hidden='true']",
        "h1",
    ]:
        node = (scope.css_first(sel) if scope is not None else None) or parser.css_first(sel)
        if node:
            t = " ".join(node.text(strip=True).split())
            if t:
                name_node = node
                participant_name = t
                break
    else:
        participant_name = ""

    if not name_node:
        return "", None

    participant_url = None
    profile_link = (
        scope.css_first("a[href*='/in/']") if scope is not None else None
    ) or parser.css_first("a[href*='/in/']")
    if profile_link:
        href = profile_link.attributes.get("href", "")
        if href:
            if href.startswith("/"):
                href = f"https://www.linkedin.com{href}"
            try:
                participant_url = canonicalize_linkedin_url(href)
            except Exception:
                participant_url = href

    return participant_name, participant_url


def _extract_thread_id(container: Optional[Node], participant_url: Optional[str]) -> str:
    """Resolve thread_id from a data-thread-urn attribute, or fall back to a hash."""
    if container is not None:
        urn = container.attributes.get("data-thread-urn") or container.attributes.get("data-thread-id")
        if urn:
            return urn.strip()
    if participant_url:
        return f"thread_hash_{abs(hash(participant_url))}"
    return f"thread_hash_{abs(hash('unknown'))}"


def _extract_thread_unread_count(container: Optional[Node], parser: HTMLParser) -> int:
    """Extract unread message badge count, defaulting to 0."""
    scope = container if container is not None else parser.root
    node = (
        scope.css_first(
            "span.msg-conversation-listitem__unread-count, "
            "span[class*='unread-count']"
        )
        if scope is not None
        else None
    ) or parser.css_first(
        "span.msg-conversation-listitem__unread-count, span[class*='unread-count']"
    )
    if node:
        val = _parse_compact_number(node.text(strip=True))
        if val is not None:
            return val
    return 0


def _find_message_bubble_nodes(parser: HTMLParser, container: Optional[Node]) -> List[Node]:
    """Locate individual message bubble nodes, scoped to the thread container when present."""
    scope = container if container is not None else parser.root
    for selector in _MESSAGE_BUBBLE_SELECTORS:
        try:
            bubbles = scope.css(selector) if scope is not None else []
        except Exception:
            bubbles = []
        if not bubbles:
            try:
                bubbles = parser.css(selector)
            except Exception:
                bubbles = []
        if bubbles:
            return bubbles
    return []


def _extract_message_sender(bubble: Node, participant_name: str) -> str:
    """Infer the sender's display name for a single message bubble."""
    name_node = bubble.css_first(
        "span.msg-s-message-group__name, "
        "span[class*='message-group__name'], "
        "h3.msg-s-message-group__name"
    )
    if name_node:
        t = " ".join(name_node.text(strip=True).split())
        if t:
            return t

    classes = bubble.attributes.get("class") or ""
    if "--other" in classes:
        return participant_name or "Unknown"
    if "--own" in classes or "--self" in classes:
        return "You"

    return participant_name or "Unknown"


def _extract_message_text(bubble: Node) -> str:
    """Extract a single message bubble's body text."""
    for sel in [
        "p.msg-s-event-listitem__body",
        "div.msg-s-event-listitem__body",
        "p[class*='event-listitem__body']",
    ]:
        node = bubble.css_first(sel)
        if node:
            t = " ".join(node.text(strip=True).split())
            if t:
                return t
    return ""


def _extract_message_timestamp(bubble: Node) -> Optional[str]:
    """Extract a single message bubble's timestamp label, if rendered."""
    node = bubble.css_first(
        "time, span.msg-s-message-group__timestamp, time[class*='timestamp']"
    )
    if node:
        t = node.attributes.get("datetime") or node.text(strip=True)
        t = " ".join((t or "").split())
        if t:
            return t
    return None


def parse_linkedin_messages_html(
    html_content: str, thread_url_hint: Optional[str] = None
) -> Optional[DMThread]:
    """
    Parse a single open LinkedIn messaging conversation page/panel
    (/messaging/thread/{id}/) into a normalized DMThread.

    Extracts participant_name/participant_url from the conversation header, thread_id
    from a data-thread-urn attribute (falling back to a hash of participant_url),
    unread_count, last_message_at, and each visible message bubble as a DMMessage in
    DOM order (oldest-to-newest, matching LinkedIn's natural render order). Returns
    None if no participant_name/thread container can be found at all.
    """
    if not html_content or not html_content.strip():
        return None

    parser = HTMLParser(html_content)
    container = _extract_thread_container(parser)

    participant_name, participant_url = _extract_thread_participant(parser, container)
    if not participant_name and container is None:
        return None
    if not participant_name:
        return None

    if not participant_url and thread_url_hint:
        try:
            participant_url = canonicalize_linkedin_url(thread_url_hint)
        except Exception:
            participant_url = None

    thread_id = _extract_thread_id(container, participant_url)
    unread_count = _extract_thread_unread_count(container, parser)

    messages: List[DMMessage] = []
    for bubble in _find_message_bubble_nodes(parser, container):
        try:
            text = _extract_message_text(bubble)
            if not text:
                continue
            sender_name = _extract_message_sender(bubble, participant_name)
            sent_at = _extract_message_timestamp(bubble)
            messages.append(DMMessage(sender_name=sender_name, text=text, sent_at=sent_at))
        except Exception:
            continue

    last_message_at = messages[-1].sent_at if messages else None

    try:
        return DMThread(
            thread_id=thread_id,
            participant_name=participant_name,
            participant_id=None,
            participant_url=participant_url,
            messages=messages,
            unread_count=unread_count,
            last_message_at=last_message_at,
            source="dom_selectolax",
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Standalone Benchmark & Self-Verification
# ---------------------------------------------------------------------------


_MOCK_SEARCH_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>LinkedIn Search</title></head>
<body>
<div class="search-results-container">
  <ul class="reusable-search__entity-result-list">
    <!-- Card 1: 2nd degree with named mutual connections and explicit company insight -->
    <li class="reusable-search__result-container">
      <div class="entity-result" data-chameleon-result-urn="urn:li:fsd_profile:ACoAAB11111">
        <div class="entity-result__item">
          <div class="entity-result__title-text">
            <a class="app-aware-link" href="https://www.linkedin.com/in/alex-smith-123?miniProfileUrn=urn%3Ali%3Afsd_profile%3AACoAAB11111&trk=people-guest">
              <span dir="ltr"><span aria-hidden="true">Alex Smith</span><span class="visually-hidden">View Alex Smith’s profile</span></span>
            </a>
            <span class="entity-result__badge-text"><span aria-hidden="true">• 2nd</span></span>
          </div>
          <div class="entity-result__primary-subtitle">Engineering Manager at Scale AI</div>
          <div class="entity-result__secondary-subtitle">San Francisco Bay Area</div>
          <p class="entity-result__summary">Current: Engineering Manager at Scale AI</p>
          <div class="entity-result__simple-insight">
            <span class="entity-result__simple-insight-text">
              <a href="https://www.linkedin.com/in/sarah-connor">Sarah Connor</a> and 3 other mutual connections
            </span>
          </div>
        </div>
      </div>
    </li>

    <!-- Card 2: 1st degree, no mutuals, @ company in headline -->
    <li class="reusable-search__result-container">
      <div class="entity-result" data-chameleon-result-urn="urn:li:fsd_profile:ACoAAB22222">
        <div class="entity-result__item">
          <div class="entity-result__title-text">
            <a class="app-aware-link" href="https://www.linkedin.com/in/beatrice-vane?trackingId=98765">
              <span dir="ltr"><span aria-hidden="true">Beatrice Vane</span><span class="visually-hidden">View Beatrice Vane’s profile</span></span>
            </a>
            <span class="entity-result__badge-text"><span aria-hidden="true">• 1st</span></span>
          </div>
          <div class="entity-result__primary-subtitle">Staff Infrastructure Engineer @ Google | Cloud Spanner</div>
          <div class="entity-result__secondary-subtitle">New York, NY</div>
        </div>
      </div>
    </li>

    <!-- Card 3: 3rd+ degree, numeric mutuals without names -->
    <li class="reusable-search__result-container">
      <div class="entity-result" data-chameleon-result-urn="urn:li:fsd_profile:ACoAAB33333">
        <div class="entity-result__item">
          <div class="entity-result__title-text">
            <a class="app-aware-link" href="https://www.linkedin.com/in/charles-xavier-phd/">
              <span dir="ltr"><span aria-hidden="true">Charles Xavier</span><span class="visually-hidden">View Charles Xavier’s profile</span></span>
            </a>
            <span class="entity-result__badge-text"><span aria-hidden="true">• 3rd+</span></span>
          </div>
          <div class="entity-result__primary-subtitle">Founder & Principal Researcher at Cerebro Labs</div>
          <div class="entity-result__secondary-subtitle">Westchester, NY</div>
          <div class="entity-result__simple-insight">
            <span class="entity-result__simple-insight-text">8 mutual connections</span>
          </div>
        </div>
      </div>
    </li>

    <!-- Card 4: Single mutual connection link -->
    <li class="reusable-search__result-container">
      <div class="entity-result" data-chameleon-result-urn="urn:li:fsd_profile:ACoAAB44444">
        <div class="entity-result__item">
          <div class="entity-result__title-text">
            <a class="app-aware-link" href="https://www.linkedin.com/in/diana-prince/">
              <span dir="ltr"><span aria-hidden="true">Diana Prince</span><span class="visually-hidden">View Diana Prince’s profile</span></span>
            </a>
            <span class="entity-result__badge-text"><span aria-hidden="true">• 2nd</span></span>
          </div>
          <div class="entity-result__primary-subtitle">VP of Security at Themyscira Tech</div>
          <div class="entity-result__secondary-subtitle">Washington DC-Baltimore Area</div>
          <div class="entity-result__simple-insight">
            <span class="entity-result__simple-insight-text">
              <a href="/in/clark-kent">Clark Kent</a> is a mutual connection
            </span>
          </div>
        </div>
      </div>
    </li>

    <!-- Card 5: Multiple named mutual connections -->
    <li class="reusable-search__result-container">
      <div class="entity-result" data-chameleon-result-urn="urn:li:fsd_profile:ACoAAB55555">
        <div class="entity-result__item">
          <div class="entity-result__title-text">
            <a class="app-aware-link" href="https://www.linkedin.com/in/edward-elric-alchemist">
              <span dir="ltr"><span aria-hidden="true">Edward Elric</span><span class="visually-hidden">View Edward Elric’s profile</span></span>
            </a>
            <span class="entity-result__badge-text"><span aria-hidden="true">• 2nd</span></span>
          </div>
          <div class="entity-result__primary-subtitle">Research Scientist at Amestris Corp</div>
          <div class="entity-result__secondary-subtitle">Seattle, WA</div>
          <div class="entity-result__simple-insight">
            <span class="entity-result__simple-insight-text">
              <a href="/in/alphonse-e">Alphonse Elric</a>, <a href="/in/winry-r">Winry Rockbell</a>, and 14 other mutual connections
            </span>
          </div>
        </div>
      </div>
    </li>

    <!-- Card 6: Non-person card (e.g. Promoted Ad or Company) - should be skipped cleanly -->
    <li class="reusable-search__result-container">
      <div class="entity-result">
        <div class="entity-result__item">
          <div class="entity-result__title-text">
            <a class="app-aware-link" href="https://www.linkedin.com/company/acme-corp">
              <span>Acme Corporation (Company)</span>
            </a>
          </div>
          <div class="entity-result__primary-subtitle">Enterprise Software • 10,000+ employees</div>
        </div>
      </div>
    </li>
  </ul>
</div>
</body>
</html>
"""

_MOCK_PROFILE_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Tony Stark - Head of Growth Engineering - Verdant | LinkedIn</title>
  <meta property="og:url" content="https://www.linkedin.com/in/tony-stark-eng" />
</head>
<body>
  <div class="pv-top-card">
    <h1 class="text-heading-xlarge inline t-24 v-align-middle break-words">Tony Stark</h1>
    <span class="dist-value">2nd</span>
    <div class="text-body-medium break-words">Head of Growth Engineering @ Verdant (Direct Hiring Lead)</div>
    <span class="text-body-small inline t-black--light break-words">San Francisco Bay Area</span>
    <ul class="pv-top-card--list pv-top-card--list-bullet">
      <li class="inline t-24 font-normal">
        <a href="https://www.linkedin.com/search/results/people/?facetNetwork=['S']">
          <span>Nick Fury and 1 other mutual connection</span>
        </a>
      </li>
    </ul>
  </div>

  <section id="about">
    <h2>About</h2>
    <div class="inline-show-more-text">
      <span aria-hidden="true">Building high-velocity growth infrastructure and edge rendering platforms at Verdant. Former Lead at Skyscanner and ASOS.</span>
    </div>
  </section>

  <section id="experience">
    <h2>Experience</h2>
    <ul class="pvs-list">
      <li class="artdeco-list__item">
        <div class="display-flex align-items-center"><span aria-hidden="true">Head of Growth Engineering</span></div>
        <span class="t-14 t-normal"><span aria-hidden="true">Verdant · Full-time</span></span>
        <span class="t-14 t-normal t-black--light"><span aria-hidden="true">Apr 2022 - Present · 2 yrs 6 mos</span></span>
        <span class="t-14 t-normal t-black--light"><span aria-hidden="true">San Francisco, California, United States</span></span>
        <div class="inline-show-more-text"><span aria-hidden="true">Directing growth platform engineering, v0 integration, and experiments.</span></div>
      </li>
      <li class="artdeco-list__item">
        <div class="display-flex align-items-center"><span aria-hidden="true">Engineering Lead</span></div>
        <span class="t-14 t-normal"><span aria-hidden="true">Skyscanner</span></span>
        <span class="t-14 t-normal t-black--light"><span aria-hidden="true">Jan 2018 - Mar 2022 · 4 yrs 3 mos</span></span>
        <span class="t-14 t-normal t-black--light"><span aria-hidden="true">London, United Kingdom</span></span>
      </li>
    </ul>
  </section>

  <section id="education">
    <h2>Education</h2>
    <ul class="pvs-list">
      <li class="artdeco-list__item">
        <div class="display-flex align-items-center"><span aria-hidden="true">University of Glasgow</span></div>
        <span class="t-14 t-normal"><span aria-hidden="true">BSc (Hons), Computing Science</span></span>
        <span class="t-14 t-normal t-black--light"><span aria-hidden="true">2006 - 2010</span></span>
      </li>
    </ul>
  </section>

  <section id="skills">
    <h2>Skills</h2>
    <ul class="pvs-list">
      <li class="artdeco-list__item"><span aria-hidden="true">Next.js</span></li>
      <li class="artdeco-list__item"><span aria-hidden="true">Growth Engineering</span></li>
      <li class="artdeco-list__item"><span aria-hidden="true">A/B Testing</span></li>
      <li class="artdeco-list__item"><span aria-hidden="true">TypeScript</span></li>
    </ul>
  </section>
</body>
</html>
"""


def _run_benchmark() -> None:
    """Execute standalone verification suite and performance benchmark."""
    print("=" * 60)
    print("Running DOM Parser (Node 2b) Verification & Benchmark Suite")
    print("=" * 60)

    # 1. Functional Verification: Search Page
    contacts = parse_linkedin_search_html(_MOCK_SEARCH_PAGE_HTML)
    assert len(contacts) == 5, f"Expected 5 parsed contacts (excluding company card), got {len(contacts)}"

    c1 = contacts[0]
    assert c1.name == "Alex Smith", f"Expected 'Alex Smith', got '{c1.name}'"
    assert c1.degree == "2nd", f"Expected '2nd', got '{c1.degree}'"
    assert c1.profile_url == "https://www.linkedin.com/in/alex-smith-123", f"Unexpected URL: {c1.profile_url}"
    assert c1.urn_id == "urn:li:member:alex-smith-123", f"Unexpected URN: {c1.urn_id}"
    assert c1.current_company == "Scale AI", f"Expected 'Scale AI', got '{c1.current_company}'"
    assert c1.location == "San Francisco Bay Area", f"Unexpected location: {c1.location}"
    assert c1.mutual_count == 4, f"Expected 4 mutuals (1 + 3), got {c1.mutual_count}"
    assert c1.mutual_sample == ["Sarah Connor"], f"Unexpected mutual sample: {c1.mutual_sample}"
    assert c1.source == "dom_selectolax", f"Expected 'dom_selectolax', got '{c1.source}'"

    c2 = contacts[1]
    assert c2.name == "Beatrice Vane", f"Expected 'Beatrice Vane', got '{c2.name}'"
    assert c2.degree == "1st", f"Expected '1st', got '{c2.degree}'"
    assert c2.profile_url == "https://www.linkedin.com/in/beatrice-vane", f"Unexpected URL: {c2.profile_url}"
    assert c2.current_company == "Google", f"Expected 'Google', got '{c2.current_company}'"
    assert c2.mutual_count == 0, f"Expected 0 mutuals, got {c2.mutual_count}"

    c3 = contacts[2]
    assert c3.name == "Charles Xavier", f"Expected 'Charles Xavier', got '{c3.name}'"
    assert c3.degree == "3rd+", f"Expected '3rd+', got '{c3.degree}'"
    assert c3.mutual_count == 8, f"Expected 8 mutuals, got {c3.mutual_count}"
    assert c3.mutual_sample == [], f"Expected empty sample, got {c3.mutual_sample}"

    c4 = contacts[3]
    assert c4.name == "Diana Prince", f"Expected 'Diana Prince', got '{c4.name}'"
    assert c4.mutual_count == 1, f"Expected 1 mutual, got {c4.mutual_count}"
    assert c4.mutual_sample == ["Clark Kent"], f"Unexpected mutual sample: {c4.mutual_sample}"

    c5 = contacts[4]
    assert c5.name == "Edward Elric", f"Expected 'Edward Elric', got '{c5.name}'"
    assert c5.mutual_count == 16, f"Expected 16 mutuals (2 + 14), got {c5.mutual_count}"
    assert c5.mutual_sample == ["Alphonse Elric", "Winry Rockbell"], f"Unexpected sample: {c5.mutual_sample}"

    print("Search page functional assertions PASSED (all 5 contacts validated).")

    # 2. Functional Verification: Profile Page
    profile = parse_linkedin_profile_html(_MOCK_PROFILE_PAGE_HTML, profile_url_hint="https://www.linkedin.com/in/tony-stark-eng")
    assert profile.name == "Tony Stark", f"Expected 'Tony Stark', got '{profile.name}'"
    assert profile.degree == "2nd", f"Expected '2nd', got '{profile.degree}'"
    assert profile.current_company == "Verdant", f"Expected 'Verdant', got '{profile.current_company}'"
    assert profile.location == "San Francisco Bay Area", f"Unexpected location: {profile.location}"
    assert profile.mutual_count == 2, f"Expected 2 mutuals, got {profile.mutual_count}"
    assert profile.mutual_sample == ["Nick Fury"], f"Unexpected mutual sample: {profile.mutual_sample}"
    assert profile.about and "high-velocity growth" in profile.about, f"Unexpected about: {profile.about}"
    assert len(profile.experience) == 2, f"Expected 2 experience items, got {len(profile.experience)}"
    assert profile.experience[0].title == "Head of Growth Engineering"
    assert profile.experience[0].company == "Verdant"
    assert profile.experience[0].date_range == "Apr 2022 - Present"
    assert profile.experience[0].duration == "2 yrs 6 mos"
    assert len(profile.education) == 1, f"Expected 1 education item, got {len(profile.education)}"
    assert profile.education[0].school == "University of Glasgow"
    assert len(profile.skills) >= 4, f"Expected >= 4 skills, got {len(profile.skills)}"
    assert "Next.js" in profile.skills

    print("Profile page functional assertions PASSED (all sections validated).")

    # 3. Performance Benchmark (Search + Profile)
    iterations = 100
    start_time = time.perf_counter()
    for _ in range(iterations):
        _ = parse_linkedin_search_html(_MOCK_SEARCH_PAGE_HTML)
    elapsed_total_ms = (time.perf_counter() - start_time) * 1000.0
    avg_per_page_ms = elapsed_total_ms / iterations

    p_start_time = time.perf_counter()
    for _ in range(iterations):
        _ = parse_linkedin_profile_html(_MOCK_PROFILE_PAGE_HTML)
    p_elapsed_total_ms = (time.perf_counter() - p_start_time) * 1000.0
    p_avg_per_page_ms = p_elapsed_total_ms / iterations

    print(f"\nPerformance Benchmark ({iterations} iterations):")
    print(f"  Search Parser Avg:   {avg_per_page_ms:.3f} ms/page ({iterations / (elapsed_total_ms / 1000.0):.1f} pages/sec)")
    print(f"  Profile Parser Avg:  {p_avg_per_page_ms:.3f} ms/page ({iterations / (p_elapsed_total_ms / 1000.0):.1f} pages/sec)")

    # Hard criterion check: must be < 10ms (and target < 5ms)
    assert avg_per_page_ms < 10.0, f"Search benchmark failed: {avg_per_page_ms:.3f}ms >= 10.0ms threshold"
    assert p_avg_per_page_ms < 10.0, f"Profile benchmark failed: {p_avg_per_page_ms:.3f}ms >= 10.0ms threshold"
    print(f"\n[PASS] Completion Criterion Met: Search ({avg_per_page_ms:.3f} ms) & Profile ({p_avg_per_page_ms:.3f} ms) strictly < 10.0 ms.")
    print("=" * 60)


if __name__ == "__main__":
    _run_benchmark()

