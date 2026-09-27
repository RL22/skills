"""
schemas.py - Single source of truth for Q4 pipeline data contracts.
Complies with mps-writing-for-agents (exhaustive, typed, canonical).
"""

import re
from datetime import datetime, timezone
from typing import List, Literal, Optional, Tuple
from urllib.parse import urlparse, urlunparse
from pydantic import BaseModel, Field, field_validator, model_validator

NetworkDegree = Literal["1st", "2nd", "3rd+", "Unknown"]
ExtractionSource = Literal["cdp_voyager_graphql", "dom_selectolax"]
OutreachStatus = Literal["discovered", "drafted", "connected", "messaged", "replied", "archived"]
ContactTier = Literal["WARM", "BRIDGE", "COLD", "FROZEN"]
WarmthDegree = Literal[1, 2, 3, 4, 5, 6, 7]
AudienceCategory = Literal["engineering_leader", "recruiter_talent", "peer_engineer", "executive"]

# Job/company vocab aligned with linkedin-cli's search filter enums and JobSpy's JobType,
# so downstream tools can pass the same literal strings without a translation layer.
EmploymentType = Literal[
    "fullTime", "partTime", "contract", "temporary", "volunteer", "internship", "other"
]
ExperienceLevel = Literal[
    "internship", "entryLevel", "associate", "midSeniorLevel", "director", "executive"
]
WorkplaceType = Literal["onSite", "remote", "hybrid", "Unknown"]
DatePostedFilter = Literal["anyTime", "past24Hours", "pastWeek", "pastMonth"]
CompensationInterval = Literal["yearly", "monthly", "weekly", "daily", "hourly"]
CompanySize = Literal[
    "1-10", "11-50", "51-200", "201-500", "501-1000",
    "1001-5000", "5001-10000", "10001+", "Unknown",
]
ApplicationStatus = Literal[
    "discovered", "evaluating", "applying", "applied",
    "interviewing", "offer", "rejected", "withdrawn", "archived",
]

# Engagement vocab. ReactionType matches LinkedIn's six reactions 1:1 (linkedin-cli's
# `post react --type` confirms this exact set). ActionStatus never reaches "executed" via
# this codebase -- publish stays human-gated; the queue only ever produces "drafted".
AuthorType = Literal["person", "company"]
ReactionType = Literal["like", "celebrate", "support", "love", "insightful", "funny"]
EngagementActionType = Literal["like", "comment", "repost", "post", "message"]
ActionStatus = Literal["drafted", "approved", "rejected", "executed"]

_JOB_ID_PATTERN = re.compile(r"/jobs/view/(?:[^/?#]*-)?(\d+)")
_COMPANY_SLUG_PATTERN = re.compile(r"/company/([^/?#]+)")
_ACTIVITY_ID_PATTERN = re.compile(r"urn:li:activity:(\d+)|/activity[:-](\d+)")

_DEGREE_PATTERN = re.compile(r"\b(1st|2nd|3rd(?:\+)?)\b", re.IGNORECASE)
_COMPANY_AT_PATTERN = re.compile(r"(?:\bat\b|@)\s*([^|•·\n,]+)", re.IGNORECASE)
_PAST_INDICATOR_PATTERN = re.compile(r"\b(?:ex|former|past|prev)\b", re.IGNORECASE)
_MUTUAL_COUNT_PATTERN = re.compile(r"(\d+)\s+other\s+mutual", re.IGNORECASE)
_MUTUAL_TOTAL_PATTERN = re.compile(r"(\d+)\s+mutual", re.IGNORECASE)


def canonicalize_linkedin_url(url: str) -> str:
    """Robustly normalize LinkedIn profile URLs to standard https://www.linkedin.com/in/{handle}."""
    if not url:
        return ""
    clean = url.strip()
    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean.lstrip("/")

    parsed = urlparse(clean)
    host = (parsed.netloc or "").lower()
    # Fail-closed domain validation: must be linkedin.com or subdomain
    if host and host != "linkedin.com" and not host.endswith(".linkedin.com"):
        raise ValueError(f"Invalid host for LinkedIn profile URL: {host}")

    netloc = "www.linkedin.com"
    path = parsed.path.rstrip("/")
    if not re.search(r"^/(in|pub)/", path):
        # Support relative or path-only handles e.g. /johndoe -> /in/johndoe
        if re.match(r"^/[a-zA-Z0-9_\-]+$", path):
            path = f"/in{path}"
    # Normalize multiple slashes
    path = re.sub(r"/+", "/", path)
    return urlunparse(("https", netloc, path, "", "", ""))


def extract_handle_from_url(url: str) -> Optional[str]:
    """Extract public handle from canonical LinkedIn profile URL."""
    clean_url = canonicalize_linkedin_url(url)
    m = re.search(r"/in/([^/?#]+)", clean_url, re.IGNORECASE)
    return m.group(1).lower() if m else None


def canonicalize_linkedin_job_url(url: str) -> str:
    """Normalize LinkedIn job URLs to https://www.linkedin.com/jobs/view/{id}/."""
    if not url:
        return ""
    clean = url.strip()
    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean.lstrip("/")

    parsed = urlparse(clean)
    host = (parsed.netloc or "").lower()
    if host and host != "linkedin.com" and not host.endswith(".linkedin.com"):
        raise ValueError(f"Invalid host for LinkedIn job URL: {host}")

    m = _JOB_ID_PATTERN.search(parsed.path)
    if m:
        return urlunparse(("https", "www.linkedin.com", f"/jobs/view/{m.group(1)}/", "", "", ""))
    # Fall back to a cleaned version of whatever path was supplied (e.g. a currentJobId query param).
    m_qs = re.search(r"currentJobId=(\d+)", parsed.query)
    if m_qs:
        return urlunparse(("https", "www.linkedin.com", f"/jobs/view/{m_qs.group(1)}/", "", "", ""))
    path = re.sub(r"/+", "/", parsed.path.rstrip("/"))
    return urlunparse(("https", "www.linkedin.com", path, "", "", ""))


def extract_job_id_from_url(url: str) -> Optional[str]:
    """Extract the numeric LinkedIn job posting ID from a job URL."""
    clean_url = canonicalize_linkedin_job_url(url)
    m = _JOB_ID_PATTERN.search(clean_url)
    return m.group(1) if m else None


def canonicalize_linkedin_company_url(url: str) -> str:
    """Normalize LinkedIn company URLs to https://www.linkedin.com/company/{slug}/."""
    if not url:
        return ""
    clean = url.strip()
    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean.lstrip("/")

    parsed = urlparse(clean)
    host = (parsed.netloc or "").lower()
    if host and host != "linkedin.com" and not host.endswith(".linkedin.com"):
        raise ValueError(f"Invalid host for LinkedIn company URL: {host}")

    m = _COMPANY_SLUG_PATTERN.search(parsed.path)
    if m:
        return urlunparse(("https", "www.linkedin.com", f"/company/{m.group(1).rstrip('/')}/", "", "", ""))
    path = re.sub(r"/+", "/", parsed.path.rstrip("/"))
    if re.match(r"^/[a-zA-Z0-9_\-]+$", path):
        path = f"/company{path}"
    return urlunparse(("https", "www.linkedin.com", path, "", "", ""))


def extract_company_slug_from_url(url: str) -> Optional[str]:
    """Extract the company slug from a canonical LinkedIn company URL."""
    clean_url = canonicalize_linkedin_company_url(url)
    m = _COMPANY_SLUG_PATTERN.search(clean_url)
    return m.group(1).lower() if m else None


def canonicalize_linkedin_post_url(url: str) -> str:
    """Normalize LinkedIn post URLs to https://www.linkedin.com/feed/update/urn:li:activity:{id}/."""
    if not url:
        return ""
    clean = url.strip()
    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean.lstrip("/")

    parsed = urlparse(clean)
    host = (parsed.netloc or "").lower()
    if host and host != "linkedin.com" and not host.endswith(".linkedin.com"):
        raise ValueError(f"Invalid host for LinkedIn post URL: {host}")

    m = _ACTIVITY_ID_PATTERN.search(parsed.path) or _ACTIVITY_ID_PATTERN.search(clean)
    if m:
        activity_id = m.group(1) or m.group(2)
        return urlunparse(
            ("https", "www.linkedin.com", f"/feed/update/urn:li:activity:{activity_id}/", "", "", "")
        )
    path = re.sub(r"/+", "/", parsed.path.rstrip("/"))
    return urlunparse(("https", "www.linkedin.com", path, "", "", ""))


def extract_post_id_from_url(url: str) -> Optional[str]:
    """Extract the numeric LinkedIn activity ID from a post URL."""
    clean_url = canonicalize_linkedin_post_url(url)
    m = _ACTIVITY_ID_PATTERN.search(clean_url)
    return (m.group(1) or m.group(2)) if m else None


def normalize_degree(deg_str: Optional[str]) -> NetworkDegree:
    """Canonicalize degree string into typed NetworkDegree."""
    if not deg_str:
        return "Unknown"
    m = _DEGREE_PATTERN.search(deg_str)
    if m:
        val = m.group(1).lower()
        if "1st" in val:
            return "1st"
        if "2nd" in val:
            return "2nd"
        if "3rd" in val:
            return "3rd+"
    return "Unknown"


def extract_company_from_headline(headline: str) -> Optional[str]:
    """Infer current employer from headline syntax, guarding against past-employer prefixes."""
    if not headline:
        return None
    m = _COMPANY_AT_PATTERN.search(headline)
    if m:
        comp = m.group(1).strip().rstrip(".,-")
        # Check if preceded by past-employer indicator
        prefix = headline[:m.start()]
        if not _PAST_INDICATOR_PATTERN.search(prefix) and len(comp) > 1:
            return comp
    return None


def parse_mutual_string(text: str) -> Tuple[int, List[str]]:
    """Extract mutual connection count and names from social proof string."""
    if not text or not text.strip():
        return 0, []

    sample: List[str] = []
    # Check for leading person names
    m_lead = re.match(r"^([A-Z][a-zA-Z\s.'-]+?)\s+(?:and|,|is)", text.strip())
    if m_lead and not re.search(r"\d+|mutual", m_lead.group(1), re.IGNORECASE):
        sample.append(m_lead.group(1).strip())

    # Case 1: "X and Y other mutual connections"
    m_other = _MUTUAL_COUNT_PATTERN.search(text)
    if m_other:
        other_cnt = int(m_other.group(1))
        return other_cnt + len(sample), sample

    # Case 2: "X mutual connections"
    m_total = _MUTUAL_TOTAL_PATTERN.search(text)
    if m_total:
        return int(m_total.group(1)), sample

    # Case 3: "X is a mutual connection"
    if "is a mutual connection" in text.lower():
        return max(len(sample), 1), sample

    return len(sample), sample


class LinkedInContact(BaseModel):
    """Normalized structured contact record representing a discovered LinkedIn entity."""

    urn_id: str = Field(min_length=1, description="Unique URN or member identifier (e.g. URN or public handle)")
    name: str = Field(min_length=1, description="Full display name of the contact")
    headline: str = Field(default="", description="Member professional headline / job title")
    profile_url: str = Field(description="Cleaned canonical public LinkedIn profile URL")
    degree: NetworkDegree = Field(default="Unknown", description="Degree of connection to viewer")
    location: Optional[str] = Field(default=None, description="Reported geographic location")
    current_company: Optional[str] = Field(default=None, description="Inferred or parsed current employer")
    mutual_count: int = Field(default=0, ge=0, description="Total number of mutual connections")
    mutual_sample: List[str] = Field(default_factory=list, description="Names of sample mutual connections")
    role_match_score: float = Field(default=0.0, ge=0.0, le=100.0, description="RapidFuzz match score (0-100) vs target role")
    company_match_score: float = Field(default=0.0, ge=0.0, le=100.0, description="RapidFuzz match score (0-100) vs target company")
    warmth_degree: Optional[WarmthDegree] = Field(default=None, description="1-7 rubric access grading degree")
    contact_tier: Optional[ContactTier] = Field(default=None, description="Operational triage action tier (WARM, BRIDGE, COLD, FROZEN)")
    open_profile: Optional[bool] = Field(default=None, description="True if member has Open Profile enabled (free InMail)")
    source: ExtractionSource = Field(default="dom_selectolax", description="Underlying pipeline extraction channel")
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of discovery")

    @field_validator("profile_url", mode="before")
    @classmethod
    def clean_url(cls, v: str) -> str:
        return canonicalize_linkedin_url(v)

    @field_validator("name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("degree", mode="before")
    @classmethod
    def validate_degree(cls, v: Optional[str]) -> NetworkDegree:
        return normalize_degree(v)

    @model_validator(mode="after")
    def canonicalize_urn_and_company(self) -> "LinkedInContact":
        # Unify URN ID by handle whenever public handle exists
        handle = extract_handle_from_url(self.profile_url)
        if handle and (not self.urn_id or self.urn_id.startswith(("urn:li:person:", "urn:li:member:", "urn:li:fsd_profile:"))):
            self.urn_id = f"urn:li:member:{handle}"

        # Fallback company inference from headline if missing
        if not self.current_company and self.headline:
            inferred = extract_company_from_headline(self.headline)
            if inferred:
                self.current_company = inferred
        return self


class SearchCluster(BaseModel):
    """Encapsulates a search cluster execution query and its returned contacts."""

    query_company: str
    query_role: Optional[str] = None
    network_filter: List[str] = Field(default_factory=lambda: ["F", "S"])
    total_results_count: int = 0
    contacts: List[LinkedInContact] = Field(default_factory=list)


class OutreachRecord(BaseModel):
    """State tracking for a target contact through the outreach lifecycle."""

    contact_urn: str
    company_slug: str
    status: OutreachStatus = "discovered"
    connection_note: Optional[str] = None
    sequence_draft: Optional[str] = None
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_touch: Optional[str] = None


class ExperienceItem(BaseModel):
    """Structured work experience record from a LinkedIn profile."""

    title: str = Field(description="Position or job title")
    company: str = Field(description="Employing company or organization")
    date_range: Optional[str] = Field(default=None, description="Employment duration or start/end dates")
    duration: Optional[str] = Field(default=None, description="Tenure length e.g. '2 yrs 4 mos'")
    location: Optional[str] = Field(default=None, description="Job location")
    description: Optional[str] = Field(default=None, description="Role summary, responsibilities, or bullet points")


class EducationItem(BaseModel):
    """Structured education record from a LinkedIn profile."""

    school: str = Field(description="Institution / school name")
    degree: Optional[str] = Field(default=None, description="Degree earned e.g. B.S., M.S.")
    field_of_study: Optional[str] = Field(default=None, description="Major / focus area")
    date_range: Optional[str] = Field(default=None, description="Years attended")


class LinkedInProfileDetailed(LinkedInContact):
    """Comprehensive single-profile record with career history, education, skills, and about summary."""

    about: Optional[str] = Field(default=None, description="Full profile about / summary section")
    experience: List[ExperienceItem] = Field(default_factory=list, description="Chronological work experience history")
    education: List[EducationItem] = Field(default_factory=list, description="Education history")
    skills: List[str] = Field(default_factory=list, description="Skills listed on member profile")
    languages: List[str] = Field(default_factory=list, description="Languages listed on member profile")
    recent_posts: List[str] = Field(default_factory=list, description="Recent post or activity snippets")
    warmth_rationale: Optional[str] = Field(default=None, description="Deterministic warmth degree rationale")
    action_recommendation: Optional[str] = Field(default=None, description="Recommended tier-specific outreach action")


class Company(BaseModel):
    """Normalized structured LinkedIn company page record. First-class object, not a contact's headline string."""

    company_id: str = Field(min_length=1, description="Company slug or URN (e.g. 'acme' or urn:li:company:...)")
    name: str = Field(min_length=1, description="Company display name")
    company_url: str = Field(description="Cleaned canonical public LinkedIn company page URL")
    website: Optional[str] = Field(default=None, description="Company's external website URL")
    industry: Optional[str] = Field(default=None, description="Primary industry classification")
    company_size: Optional[CompanySize] = Field(default=None, description="LinkedIn employee-count bracket")
    employee_count: Optional[int] = Field(default=None, ge=0, description="On-LinkedIn employee count, if shown")
    follower_count: Optional[int] = Field(default=None, ge=0, description="LinkedIn follower count")
    headquarters: Optional[str] = Field(default=None, description="Headquarters location")
    founded: Optional[str] = Field(default=None, description="Year founded")
    description: Optional[str] = Field(default=None, description="Company 'About' summary")
    specialties: List[str] = Field(default_factory=list, description="Listed specialties/tags")
    logo_url: Optional[str] = Field(default=None, description="Company logo image URL")
    source: ExtractionSource = Field(default="dom_selectolax", description="Underlying pipeline extraction channel")
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of discovery")

    @field_validator("company_url", mode="before")
    @classmethod
    def clean_company_url(cls, v: str) -> str:
        return canonicalize_linkedin_company_url(v)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name_whitespace(cls, v: str) -> str:
        return (v or "").strip()

    @model_validator(mode="after")
    def canonicalize_company_id(self) -> "Company":
        slug = extract_company_slug_from_url(self.company_url)
        if slug and (not self.company_id or self.company_id.startswith("urn:li:company:")):
            self.company_id = slug
        return self


class JobPosting(BaseModel):
    """Normalized structured LinkedIn job posting record. First-class object, distinct from the hiring company or any contact."""

    job_id: str = Field(min_length=1, description="Numeric LinkedIn job posting ID")
    title: str = Field(min_length=1, description="Job title as posted")
    company_name: str = Field(min_length=1, description="Hiring company display name")
    company_id: Optional[str] = Field(default=None, description="Linked Company.company_id when resolvable")
    job_url: str = Field(description="Cleaned canonical public LinkedIn job posting URL")
    location: Optional[str] = Field(default=None, description="Posted job location")
    workplace_type: Optional[WorkplaceType] = Field(default=None, description="On-site, remote, or hybrid")
    employment_type: Optional[EmploymentType] = Field(default=None, description="Full-time, contract, internship, etc.")
    experience_level: Optional[ExperienceLevel] = Field(default=None, description="Seniority level as posted")
    job_function: Optional[str] = Field(default=None, description="LinkedIn job function taxonomy label")
    industries: List[str] = Field(default_factory=list, description="Industries listed in job criteria")
    date_posted: Optional[str] = Field(default=None, description="Posting date or relative string (e.g. '2 weeks ago')")
    applicant_count: Optional[int] = Field(default=None, ge=0, description="Reported applicant count")
    easy_apply: Optional[bool] = Field(default=None, description="True if LinkedIn Easy Apply is offered")
    description: Optional[str] = Field(default=None, description="Full job description text")
    salary_min: Optional[float] = Field(default=None, ge=0, description="Minimum posted compensation amount")
    salary_max: Optional[float] = Field(default=None, ge=0, description="Maximum posted compensation amount")
    salary_currency: Optional[str] = Field(default=None, description="Compensation currency code (e.g. 'USD')")
    salary_interval: Optional[CompensationInterval] = Field(default=None, description="Compensation cadence")
    skills: List[str] = Field(default_factory=list, description="Skills listed on the posting, when shown")
    role_match_score: float = Field(default=0.0, ge=0.0, le=100.0, description="RapidFuzz match score (0-100) vs target roles")
    company_match_score: float = Field(default=0.0, ge=0.0, le=100.0, description="RapidFuzz match score (0-100) vs target company")
    application_status: ApplicationStatus = Field(default="discovered", description="Pipeline stage for this posting")
    source: ExtractionSource = Field(default="dom_selectolax", description="Underlying pipeline extraction channel")
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of discovery")

    @field_validator("job_url", mode="before")
    @classmethod
    def clean_job_url(cls, v: str) -> str:
        return canonicalize_linkedin_job_url(v)

    @field_validator("title", "company_name", mode="before")
    @classmethod
    def strip_job_whitespace(cls, v: str) -> str:
        return (v or "").strip()

    @model_validator(mode="after")
    def canonicalize_job_id(self) -> "JobPosting":
        extracted = extract_job_id_from_url(self.job_url)
        if extracted:
            self.job_id = extracted
        return self


class Post(BaseModel):
    """Normalized LinkedIn feed post. Discovery/scoring object only -- no create/like/comment execution here."""

    post_id: str = Field(min_length=1, description="Numeric LinkedIn activity ID")
    post_url: str = Field(description="Cleaned canonical public LinkedIn post URL")
    author_name: str = Field(min_length=1, description="Post author display name")
    author_type: AuthorType = Field(default="person", description="Whether the author is a person or a company page")
    author_id: Optional[str] = Field(default=None, description="Linked LinkedInContact.urn_id or Company.company_id when resolvable")
    text: Optional[str] = Field(default=None, description="Post body text")
    hashtags: List[str] = Field(default_factory=list, description="Hashtags parsed from post text")
    posted_at: Optional[str] = Field(default=None, description="Posting date or relative string (e.g. '3d')")
    like_count: Optional[int] = Field(default=None, ge=0, description="Reported like/reaction count")
    comment_count: Optional[int] = Field(default=None, ge=0, description="Reported comment count")
    repost_count: Optional[int] = Field(default=None, ge=0, description="Reported repost count")
    topic_match_score: float = Field(default=0.0, ge=0.0, le=100.0, description="RapidFuzz match score (0-100) vs target topics")
    author_match_score: float = Field(default=0.0, ge=0.0, le=100.0, description="RapidFuzz match score (0-100) vs target people/companies")
    author_warmth_tier: Optional[ContactTier] = Field(default=None, description="Warmth tier of author when author is a known contact")
    source: ExtractionSource = Field(default="dom_selectolax", description="Underlying pipeline extraction channel")
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of discovery")

    @field_validator("post_url", mode="before")
    @classmethod
    def clean_post_url(cls, v: str) -> str:
        return canonicalize_linkedin_post_url(v)

    @field_validator("author_name", mode="before")
    @classmethod
    def strip_author_whitespace(cls, v: str) -> str:
        return (v or "").strip()

    @model_validator(mode="after")
    def canonicalize_post_id(self) -> "Post":
        extracted = extract_post_id_from_url(self.post_url)
        if extracted:
            self.post_id = extracted
        return self


class DMMessage(BaseModel):
    """Single message within a DM thread."""

    sender_name: str = Field(min_length=1, description="Display name of the message sender")
    text: str = Field(default="", description="Message body text")
    sent_at: Optional[str] = Field(default=None, description="Send timestamp or relative string")


class DMThread(BaseModel):
    """Normalized LinkedIn DM conversation thread. Discovery object only -- no send execution here."""

    thread_id: str = Field(min_length=1, description="Conversation/thread URN or ID")
    participant_name: str = Field(min_length=1, description="Display name of the other participant")
    participant_id: Optional[str] = Field(default=None, description="Linked LinkedInContact.urn_id when resolvable")
    participant_url: Optional[str] = Field(default=None, description="Participant's profile URL")
    messages: List[DMMessage] = Field(default_factory=list, description="Messages already loaded/visible in this thread")
    unread_count: int = Field(default=0, ge=0, description="Unread message count for this thread")
    last_message_at: Optional[str] = Field(default=None, description="Timestamp of most recent message")
    source: ExtractionSource = Field(default="dom_selectolax", description="Underlying pipeline extraction channel")
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of discovery")

    @field_validator("participant_url", mode="before")
    @classmethod
    def clean_participant_url(cls, v: Optional[str]) -> Optional[str]:
        return canonicalize_linkedin_url(v) if v else v


class EngagementAction(BaseModel):
    """
    A rubric-scored, drafted engagement action awaiting human review. This is the entire
    write-side surface of the engagement pipeline: it only ever produces drafts. Nothing in
    this codebase transitions a record to "executed" -- publish/send/like/comment/repost
    stays 100% human-gated, performed by the user in their own browser session.
    """

    action_id: str = Field(min_length=1, description="Stable ID for this drafted action (e.g. hash of target + action_type)")
    target_type: Literal["post", "dm"] = Field(description="What kind of object this action targets")
    target_id: str = Field(min_length=1, description="Post.post_id or DMThread.thread_id being acted on")
    target_url: Optional[str] = Field(default=None, description="Canonical URL of the target, for human execution")
    action_type: EngagementActionType = Field(description="like, comment, repost, post (new), or message")
    reaction_type: Optional[ReactionType] = Field(default=None, description="Set only when action_type == 'like'")
    draft_content: Optional[str] = Field(default=None, description="Drafted comment/post/message text for human review")
    rubric_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Composite rubric score driving prioritization")
    rationale: Optional[str] = Field(default=None, description="Human-readable reason this action was suggested and scored")
    status: ActionStatus = Field(default="drafted", description="drafted -> approved/rejected by the user; never auto-executed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp the draft was generated")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp of last status change")

