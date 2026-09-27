"""
pipeline_db.py - Node 2d Database Storage Architect for Q4 LinkedIn Pipeline.
Complies with mps-writing-for-agents (clean, tight, robust, single source of truth).
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import unquote

import duckdb

try:
    from .schemas import (
        Company,
        ContactTier,
        DMMessage,
        DMThread,
        EducationItem,
        EngagementAction,
        ExperienceItem,
        ExtractionSource,
        JobPosting,
        LinkedInContact,
        LinkedInProfileDetailed,
        NetworkDegree,
        OutreachRecord,
        OutreachStatus,
        Post,
        WarmthDegree,
        canonicalize_linkedin_url,
        extract_company_slug_from_url,
        extract_job_id_from_url,
        extract_post_id_from_url,
    )
except (ImportError, ValueError):
    import sys

    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from schemas import (
        Company,
        ContactTier,
        DMMessage,
        DMThread,
        EducationItem,
        EngagementAction,
        ExperienceItem,
        ExtractionSource,
        JobPosting,
        LinkedInContact,
        LinkedInProfileDetailed,
        NetworkDegree,
        OutreachRecord,
        OutreachStatus,
        Post,
        WarmthDegree,
        canonicalize_linkedin_url,
        extract_company_slug_from_url,
        extract_job_id_from_url,
        extract_post_id_from_url,
    )

DEFAULT_DB_PATH = os.path.expanduser("~/.config/chrome-agent/job_search_network.duckdb")

SCHEMA_CONTACTS = """
CREATE TABLE IF NOT EXISTS contacts (
    urn_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    headline VARCHAR,
    profile_url VARCHAR,
    degree VARCHAR,
    location VARCHAR,
    current_company VARCHAR,
    mutual_count INTEGER DEFAULT 0,
    mutual_sample VARCHAR,
    role_match_score DOUBLE DEFAULT 0.0,
    company_match_score DOUBLE DEFAULT 0.0,
    source VARCHAR,
    discovered_at TIMESTAMP,
    updated_at TIMESTAMP
);
"""

SCHEMA_OUTREACH_RECORDS = """
CREATE TABLE IF NOT EXISTS outreach_records (
    contact_urn VARCHAR PRIMARY KEY,
    company_slug VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    connection_note VARCHAR,
    sequence_draft VARCHAR,
    last_updated TIMESTAMP,
    last_touch TEXT
);
"""

SCHEMA_JOBS = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    company_name VARCHAR NOT NULL,
    company_id VARCHAR,
    job_url VARCHAR,
    location VARCHAR,
    workplace_type VARCHAR,
    employment_type VARCHAR,
    experience_level VARCHAR,
    job_function VARCHAR,
    industries VARCHAR,
    date_posted VARCHAR,
    applicant_count INTEGER,
    easy_apply BOOLEAN,
    description VARCHAR,
    salary_min DOUBLE,
    salary_max DOUBLE,
    salary_currency VARCHAR,
    salary_interval VARCHAR,
    skills VARCHAR,
    role_match_score DOUBLE DEFAULT 0.0,
    company_match_score DOUBLE DEFAULT 0.0,
    application_status VARCHAR DEFAULT 'discovered',
    source VARCHAR,
    discovered_at TIMESTAMP,
    updated_at TIMESTAMP
);
"""

SCHEMA_COMPANIES = """
CREATE TABLE IF NOT EXISTS companies (
    company_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    company_url VARCHAR,
    website VARCHAR,
    industry VARCHAR,
    company_size VARCHAR,
    employee_count INTEGER,
    follower_count INTEGER,
    headquarters VARCHAR,
    founded VARCHAR,
    description VARCHAR,
    specialties VARCHAR,
    logo_url VARCHAR,
    source VARCHAR,
    discovered_at TIMESTAMP,
    updated_at TIMESTAMP
);
"""

SCHEMA_POSTS = """
CREATE TABLE IF NOT EXISTS posts (
    post_id VARCHAR PRIMARY KEY,
    post_url VARCHAR,
    author_name VARCHAR NOT NULL,
    author_type VARCHAR,
    author_id VARCHAR,
    text VARCHAR,
    hashtags VARCHAR,
    posted_at VARCHAR,
    like_count INTEGER,
    comment_count INTEGER,
    repost_count INTEGER,
    topic_match_score DOUBLE DEFAULT 0.0,
    author_match_score DOUBLE DEFAULT 0.0,
    author_warmth_tier VARCHAR,
    source VARCHAR,
    discovered_at TIMESTAMP,
    updated_at TIMESTAMP
);
"""

SCHEMA_DM_THREADS = """
CREATE TABLE IF NOT EXISTS dm_threads (
    thread_id VARCHAR PRIMARY KEY,
    participant_name VARCHAR NOT NULL,
    participant_id VARCHAR,
    participant_url VARCHAR,
    messages VARCHAR,
    unread_count INTEGER DEFAULT 0,
    last_message_at VARCHAR,
    source VARCHAR,
    discovered_at TIMESTAMP,
    updated_at TIMESTAMP
);
"""

SCHEMA_ENGAGEMENT_ACTIONS = """
CREATE TABLE IF NOT EXISTS engagement_actions (
    action_id VARCHAR PRIMARY KEY,
    target_type VARCHAR NOT NULL,
    target_id VARCHAR NOT NULL,
    target_url VARCHAR,
    action_type VARCHAR NOT NULL,
    reaction_type VARCHAR,
    draft_content VARCHAR,
    rubric_score DOUBLE DEFAULT 0.0,
    rationale VARCHAR,
    status VARCHAR DEFAULT 'drafted',
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
"""

INDICES = """
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(current_company);
CREATE INDEX IF NOT EXISTS idx_contacts_role_score ON contacts(role_match_score);
CREATE INDEX IF NOT EXISTS idx_outreach_company ON outreach_records(company_slug);
CREATE INDEX IF NOT EXISTS idx_jobs_company_name ON jobs(company_name);
CREATE INDEX IF NOT EXISTS idx_jobs_role_score ON jobs(role_match_score);
CREATE INDEX IF NOT EXISTS idx_jobs_application_status ON jobs(application_status);
CREATE INDEX IF NOT EXISTS idx_companies_industry ON companies(industry);
CREATE INDEX IF NOT EXISTS idx_posts_author_name ON posts(author_name);
CREATE INDEX IF NOT EXISTS idx_posts_topic_score ON posts(topic_match_score);
CREATE INDEX IF NOT EXISTS idx_dm_threads_participant ON dm_threads(participant_name);
CREATE INDEX IF NOT EXISTS idx_engagement_actions_status ON engagement_actions(status);
CREATE INDEX IF NOT EXISTS idx_engagement_actions_target_type ON engagement_actions(target_type);
"""


def _deserialize_mutual_sample(val: Optional[str]) -> List[str]:
    """Parse mutual connection sample safely from JSON or comma-separated string."""
    if not val:
        return []
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
    return [x.strip() for x in val.split(",") if x.strip()]


def _slugify(text: str) -> str:
    """Normalize a name or string to a URL-safe ASCII slug."""
    s = unquote(text or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _normalize_network_degree(deg_str: Optional[str]) -> NetworkDegree:
    """Map informal degree mentions to canonical NetworkDegree enum."""
    t = (deg_str or "").lower()
    if "1st" in t or "first" in t:
        return "1st"
    if "2nd" in t or "second" in t:
        return "2nd"
    if "3rd" in t or "third" in t:
        return "3rd+"
    return "Unknown"


def _normalize_outreach_status(status_str: Optional[str]) -> OutreachStatus:
    """Map raw status descriptions to canonical OutreachStatus."""
    s = (status_str or "").lower()
    if any(w in s for w in ["closed", "declined", "archived", "re-pitching"]):
        return "archived"
    if any(
        w in s
        for w in [
            "screen",
            "replied",
            "booked",
            "active contact",
            "confirmed",
            "scheduled",
            "touch 2",
        ]
    ):
        return "replied"
    if any(w in s for w in ["sent", "messaged", "applied", "email sent"]):
        return "messaged"
    if any(w in s for w in ["connection request sent", "connected"]):
        return "connected"
    if any(w in s for w in ["drafted", "deferred"]):
        return "drafted"
    return "discovered"


def _parse_mutuals_from_text(text: str):
    """Extract mutual count and sample names from freeform markdown notes."""
    count = 0
    sample: List[str] = []
    m = re.search(r"(\d+)\s+mutual", text, flags=re.IGNORECASE)
    if m:
        count = int(m.group(1))

    # Match parenthesized lists: (Jean Grey, Jim Gordon, etc.)
    m_sample = re.search(
        r"mutual(?:s|\s+connections)?\s*\(([^)]+)\)", text, flags=re.IGNORECASE
    )
    if m_sample:
        raw = m_sample.group(1).split(",")
        sample = [
            n.strip()
            for n in raw
            if n.strip() and not n.strip().lower().startswith("etc")
        ]
    else:
        # Match colon list: mutuals: Peter Parker, Nick Fury
        m_mut = re.search(r"mutuals?:\s*([^\n;]+)", text, flags=re.IGNORECASE)
        if m_mut:
            raw = m_mut.group(1).split(",")
            sample = [
                n.strip() for n in raw if n.strip() and not n.strip().startswith("+")
            ]
            if count == 0:
                count = len(sample)
    return count, sample


class NetworkDatabase:
    """
    Embedded DuckDB storage architect for discovered LinkedIn contacts and outreach state.
    Provides idempotent upserts, RapidFuzz score querying, and bi-directional markdown sync.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        if self.db_path != ":memory:" and not self.db_path.startswith(":memory:"):
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            os.makedirs(db_dir, exist_ok=True)

        self.conn = duckdb.connect(self.db_path)
        self._init_tables()

    def __enter__(self) -> "NetworkDatabase":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _init_tables(self) -> None:
        """Create target tables and query indices if they do not already exist."""
        self.conn.execute(SCHEMA_CONTACTS)
        self.conn.execute(SCHEMA_OUTREACH_RECORDS)
        self.conn.execute(SCHEMA_JOBS)
        self.conn.execute(SCHEMA_COMPANIES)
        self.conn.execute(SCHEMA_POSTS)
        self.conn.execute(SCHEMA_DM_THREADS)
        self.conn.execute(SCHEMA_ENGAGEMENT_ACTIONS)
        for stmt in INDICES.strip().split(";"):
            stmt_clean = stmt.strip()
            if stmt_clean:
                try:
                    self.conn.execute(stmt_clean)
                except Exception:
                    pass

        # Idempotently migrate/extend contacts table schema for detailed profile fields
        for col_def in [
            "about VARCHAR",
            "experience_json VARCHAR",
            "education_json VARCHAR",
            "skills_json VARCHAR",
            "warmth_degree INTEGER",
            "contact_tier VARCHAR",
        ]:
            try:
                self.conn.execute(f"ALTER TABLE contacts ADD COLUMN IF NOT EXISTS {col_def}")
            except Exception:
                pass

        # Same idempotent migration for outreach_records (last_touch added after v1)
        try:
            self.conn.execute(
                "ALTER TABLE outreach_records ADD COLUMN IF NOT EXISTS last_touch TEXT"
            )
        except Exception:
            pass

    def upsert_contacts(self, contacts: List[LinkedInContact]) -> int:
        """
        Upsert a batch of LinkedIn contacts idempotently.
        Handles conflicts on urn_id by updating all mutable columns and setting updated_at.
        Deduplicates against existing profile_url to prevent URN namespace splits.
        Returns the count of contacts upserted.
        """
        if not contacts:
            return 0

        # Deduplicate within batch keeping latest entry
        deduped: dict[str, LinkedInContact] = {}
        for c in contacts:
            deduped[c.urn_id] = c

        # Cross-reference existing profile_urls in database to prevent URN splits
        for c in list(deduped.values()):
            if c.profile_url:
                existing = self.conn.execute(
                    "SELECT urn_id FROM contacts WHERE profile_url = ?", [c.profile_url]
                ).fetchone()
                if existing and existing[0] != c.urn_id:
                    c.urn_id = existing[0]

        now = datetime.now(timezone.utc)
        rows = [
            (
                c.urn_id,
                c.name,
                c.headline,
                c.profile_url,
                c.degree,
                c.location,
                c.current_company,
                c.mutual_count,
                json.dumps(c.mutual_sample),
                c.role_match_score,
                c.company_match_score,
                c.source,
                c.discovered_at,
                now,
            )
            for c in deduped.values()
        ]

        query = """
            INSERT INTO contacts (
                urn_id, name, headline, profile_url, degree, location,
                current_company, mutual_count, mutual_sample, role_match_score,
                company_match_score, source, discovered_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (urn_id) DO UPDATE SET
                name = EXCLUDED.name,
                headline = EXCLUDED.headline,
                profile_url = EXCLUDED.profile_url,
                degree = EXCLUDED.degree,
                location = EXCLUDED.location,
                current_company = EXCLUDED.current_company,
                mutual_count = EXCLUDED.mutual_count,
                mutual_sample = EXCLUDED.mutual_sample,
                role_match_score = EXCLUDED.role_match_score,
                company_match_score = EXCLUDED.company_match_score,
                source = EXCLUDED.source,
                updated_at = EXCLUDED.updated_at
        """
        self.conn.executemany(query, rows)
        return len(rows)

    def query_contacts(
        self,
        company: Optional[str] = None,
        min_role_score: float = 0.0,
        limit: Optional[int] = None,
    ) -> List[LinkedInContact]:
        """
        Query contacts matching optional company pattern and minimum role match score.
        Results are ordered by role_match_score DESC, company_match_score DESC, name ASC.
        """
        query = """
            SELECT urn_id, name, headline, profile_url, degree, location,
                   current_company, mutual_count, mutual_sample, role_match_score,
                   company_match_score, source, discovered_at
            FROM contacts
            WHERE role_match_score >= ?
        """
        params: list = [float(min_role_score)]

        if company and company.strip():
            query += " AND current_company ILIKE ?"
            params.append(f"%{company.strip()}%")

        query += " ORDER BY role_match_score DESC, company_match_score DESC, name ASC"

        if limit is not None and int(limit) > 0:
            query += " LIMIT ?"
            params.append(int(limit))

        rows = self.conn.execute(query, params).fetchall()
        results: List[LinkedInContact] = []
        for row in rows:
            sample = _deserialize_mutual_sample(row[8])
            degree = row[4] if row[4] in ("1st", "2nd", "3rd+", "Unknown") else "Unknown"
            source = (
                row[11]
                if row[11] in ("cdp_voyager_graphql", "dom_selectolax")
                else "dom_selectolax"
            )
            discovered = row[12]
            if isinstance(discovered, str):
                discovered = datetime.fromisoformat(discovered)

            results.append(
                LinkedInContact(
                    urn_id=row[0],
                    name=row[1],
                    headline=row[2] or "",
                    profile_url=row[3] or "",
                    degree=degree,
                    location=row[5],
                    current_company=row[6],
                    mutual_count=int(row[7] or 0),
                    mutual_sample=sample,
                    role_match_score=float(row[9] or 0.0),
                    company_match_score=float(row[10] or 0.0),
                    source=source,
                    discovered_at=discovered,
                )
            )
        return results

    def get_contact(self, urn_id: str) -> Optional[LinkedInContact]:
        """Fetch a single contact by primary key urn_id."""
        row = self.conn.execute(
            """
            SELECT urn_id, name, headline, profile_url, degree, location,
                   current_company, mutual_count, mutual_sample, role_match_score,
                   company_match_score, source, discovered_at
            FROM contacts
            WHERE urn_id = ?
            """,
            [urn_id],
        ).fetchone()
        if not row:
            return None

        sample = _deserialize_mutual_sample(row[8])
        degree = row[4] if row[4] in ("1st", "2nd", "3rd+", "Unknown") else "Unknown"
        source = (
            row[11]
            if row[11] in ("cdp_voyager_graphql", "dom_selectolax")
            else "dom_selectolax"
        )
        discovered = row[12]
        if isinstance(discovered, str):
            discovered = datetime.fromisoformat(discovered)

        return LinkedInContact(
            urn_id=row[0],
            name=row[1],
            headline=row[2] or "",
            profile_url=row[3] or "",
            degree=degree,
            location=row[5],
            current_company=row[6],
            mutual_count=int(row[7] or 0),
            mutual_sample=sample,
            role_match_score=float(row[9] or 0.0),
            company_match_score=float(row[10] or 0.0),
            source=source,
            discovered_at=discovered,
        )

    def upsert_detailed_profile(self, profile: LinkedInProfileDetailed) -> None:
        """Upsert a detailed profile including full work experience, education, skills, and about sections."""
        # 1. Upsert base contact columns
        self.upsert_contacts([profile])

        # 2. Serialize rich fields
        exp_json = json.dumps([e.model_dump() for e in profile.experience]) if profile.experience else None
        edu_json = json.dumps([e.model_dump() for e in profile.education]) if profile.education else None
        skills_json = json.dumps(profile.skills) if profile.skills else None

        now = datetime.now(timezone.utc)
        self.conn.execute(
            """
            UPDATE contacts
            SET about = COALESCE(?, about),
                experience_json = COALESCE(?, experience_json),
                education_json = COALESCE(?, education_json),
                skills_json = COALESCE(?, skills_json),
                warmth_degree = COALESCE(?, warmth_degree),
                contact_tier = COALESCE(?, contact_tier),
                updated_at = ?
            WHERE urn_id = ? OR profile_url = ?
            """,
            [
                profile.about,
                exp_json,
                edu_json,
                skills_json,
                profile.warmth_degree,
                profile.contact_tier,
                now,
                profile.urn_id,
                profile.profile_url,
            ],
        )

    def get_detailed_profile(self, target: str) -> Optional[LinkedInProfileDetailed]:
        """Fetch a detailed profile by urn_id, profile_url, or public handle."""
        clean_target = target.strip()
        row = self.conn.execute(
            """
            SELECT urn_id, name, headline, profile_url, degree, location,
                   current_company, mutual_count, mutual_sample, role_match_score,
                   company_match_score, source, discovered_at, about,
                   experience_json, education_json, skills_json, warmth_degree, contact_tier
            FROM contacts
            WHERE urn_id = ? OR profile_url = ? OR profile_url ILIKE ? OR urn_id ILIKE ?
            LIMIT 1
            """,
            [clean_target, clean_target, f"%{clean_target.strip('/')}%", f"%{clean_target.strip('/')}%"],
        ).fetchone()

        if not row:
            return None

        sample = _deserialize_mutual_sample(row[8])
        degree = row[4] if row[4] in ("1st", "2nd", "3rd+", "Unknown") else "Unknown"
        source = (
            row[11]
            if row[11] in ("cdp_voyager_graphql", "dom_selectolax")
            else "dom_selectolax"
        )
        discovered = row[12]
        if isinstance(discovered, str):
            discovered = datetime.fromisoformat(discovered)

        # Deserialize rich fields
        experience: List[ExperienceItem] = []
        if row[14]:
            try:
                raw_exp = json.loads(row[14])
                if isinstance(raw_exp, list):
                    experience = [ExperienceItem(**item) for item in raw_exp]
            except Exception:
                pass

        education: List[EducationItem] = []
        if row[15]:
            try:
                raw_edu = json.loads(row[15])
                if isinstance(raw_edu, list):
                    education = [EducationItem(**item) for item in raw_edu]
            except Exception:
                pass

        skills: List[str] = []
        if row[16]:
            try:
                raw_sk = json.loads(row[16])
                if isinstance(raw_sk, list):
                    skills = [str(x) for x in raw_sk]
            except Exception:
                pass

        return LinkedInProfileDetailed(
            urn_id=row[0],
            name=row[1],
            headline=row[2] or "",
            profile_url=row[3] or "",
            degree=degree,
            location=row[5],
            current_company=row[6],
            mutual_count=int(row[7] or 0),
            mutual_sample=sample,
            role_match_score=float(row[9] or 0.0),
            company_match_score=float(row[10] or 0.0),
            source=source,
            discovered_at=discovered,
            about=row[13],
            experience=experience,
            education=education,
            skills=skills,
            warmth_degree=row[17],
            contact_tier=row[18],
        )

    def upsert_jobs(self, jobs: List[JobPosting]) -> int:
        """
        Upsert a batch of LinkedIn job postings idempotently.
        Handles conflicts on job_id by updating all mutable columns and setting updated_at.
        Returns the count of jobs upserted.
        """
        if not jobs:
            return 0

        # Deduplicate within batch keeping latest entry
        deduped: dict[str, JobPosting] = {}
        for j in jobs:
            deduped[j.job_id] = j

        now = datetime.now(timezone.utc)
        rows = [
            (
                j.job_id,
                j.title,
                j.company_name,
                j.company_id,
                j.job_url,
                j.location,
                j.workplace_type,
                j.employment_type,
                j.experience_level,
                j.job_function,
                json.dumps(j.industries),
                j.date_posted,
                j.applicant_count,
                j.easy_apply,
                j.description,
                j.salary_min,
                j.salary_max,
                j.salary_currency,
                j.salary_interval,
                json.dumps(j.skills),
                j.role_match_score,
                j.company_match_score,
                j.application_status,
                j.source,
                j.discovered_at,
                now,
            )
            for j in deduped.values()
        ]

        query = """
            INSERT INTO jobs (
                job_id, title, company_name, company_id, job_url, location,
                workplace_type, employment_type, experience_level, job_function,
                industries, date_posted, applicant_count, easy_apply, description,
                salary_min, salary_max, salary_currency, salary_interval, skills,
                role_match_score, company_match_score, application_status, source,
                discovered_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (job_id) DO UPDATE SET
                title = EXCLUDED.title,
                company_name = EXCLUDED.company_name,
                company_id = EXCLUDED.company_id,
                job_url = EXCLUDED.job_url,
                location = EXCLUDED.location,
                workplace_type = EXCLUDED.workplace_type,
                employment_type = EXCLUDED.employment_type,
                experience_level = EXCLUDED.experience_level,
                job_function = EXCLUDED.job_function,
                industries = EXCLUDED.industries,
                date_posted = EXCLUDED.date_posted,
                applicant_count = EXCLUDED.applicant_count,
                easy_apply = EXCLUDED.easy_apply,
                description = EXCLUDED.description,
                salary_min = EXCLUDED.salary_min,
                salary_max = EXCLUDED.salary_max,
                salary_currency = EXCLUDED.salary_currency,
                salary_interval = EXCLUDED.salary_interval,
                skills = EXCLUDED.skills,
                role_match_score = EXCLUDED.role_match_score,
                company_match_score = EXCLUDED.company_match_score,
                application_status = EXCLUDED.application_status,
                source = EXCLUDED.source,
                updated_at = EXCLUDED.updated_at
        """
        self.conn.executemany(query, rows)
        return len(rows)

    @staticmethod
    def _row_to_job_posting(row: tuple) -> JobPosting:
        """Build a JobPosting from a jobs table row in canonical column order."""
        try:
            industries = json.loads(row[10]) if row[10] else []
        except Exception:
            industries = []
        try:
            skills = json.loads(row[19]) if row[19] else []
        except Exception:
            skills = []

        discovered = row[24]
        if isinstance(discovered, str):
            discovered = datetime.fromisoformat(discovered)

        return JobPosting(
            job_id=row[0],
            title=row[1],
            company_name=row[2],
            company_id=row[3],
            job_url=row[4] or "",
            location=row[5],
            workplace_type=row[6],
            employment_type=row[7],
            experience_level=row[8],
            job_function=row[9],
            industries=industries,
            date_posted=row[11],
            applicant_count=row[12],
            easy_apply=row[13],
            description=row[14],
            salary_min=row[15],
            salary_max=row[16],
            salary_currency=row[17],
            salary_interval=row[18],
            skills=skills,
            role_match_score=float(row[20] or 0.0),
            company_match_score=float(row[21] or 0.0),
            application_status=row[22] or "discovered",
            source=row[23] or "dom_selectolax",
            discovered_at=discovered,
        )

    _JOB_SELECT_COLUMNS = """
            job_id, title, company_name, company_id, job_url, location,
            workplace_type, employment_type, experience_level, job_function,
            industries, date_posted, applicant_count, easy_apply, description,
            salary_min, salary_max, salary_currency, salary_interval, skills,
            role_match_score, company_match_score, application_status, source,
            discovered_at
    """

    def query_jobs(
        self,
        company: Optional[str] = None,
        min_role_score: float = 0.0,
        application_status: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[JobPosting]:
        """
        Query jobs matching optional company pattern, minimum role match score, and status.
        Results are ordered by role_match_score DESC, company_match_score DESC, title ASC.
        """
        query = f"""
            SELECT {self._JOB_SELECT_COLUMNS}
            FROM jobs
            WHERE role_match_score >= ?
        """
        params: list = [float(min_role_score)]

        if company and company.strip():
            query += " AND company_name ILIKE ?"
            params.append(f"%{company.strip()}%")

        if application_status and application_status.strip():
            query += " AND application_status = ?"
            params.append(application_status.strip())

        query += " ORDER BY role_match_score DESC, company_match_score DESC, title ASC"

        if limit is not None and int(limit) > 0:
            query += " LIMIT ?"
            params.append(int(limit))

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_job_posting(row) for row in rows]

    def get_job(self, job_id_or_url: str) -> Optional[JobPosting]:
        """Fetch a single job posting by job_id or job URL (raw ID or full LinkedIn URL)."""
        clean_target = (job_id_or_url or "").strip()
        try:
            job_id = extract_job_id_from_url(clean_target) or clean_target
        except ValueError:
            job_id = clean_target
        row = self.conn.execute(
            f"""
            SELECT {self._JOB_SELECT_COLUMNS}
            FROM jobs
            WHERE job_id = ? OR job_id = ?
            """,
            [clean_target, job_id],
        ).fetchone()
        if not row:
            return None
        return self._row_to_job_posting(row)

    def upsert_company(self, company: Company) -> None:
        """Upsert a single company record, updating all mutable columns on conflict."""
        now = datetime.now(timezone.utc)
        query = """
            INSERT INTO companies (
                company_id, name, company_url, website, industry, company_size,
                employee_count, follower_count, headquarters, founded, description,
                specialties, logo_url, source, discovered_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (company_id) DO UPDATE SET
                name = EXCLUDED.name,
                company_url = EXCLUDED.company_url,
                website = EXCLUDED.website,
                industry = EXCLUDED.industry,
                company_size = EXCLUDED.company_size,
                employee_count = EXCLUDED.employee_count,
                follower_count = EXCLUDED.follower_count,
                headquarters = EXCLUDED.headquarters,
                founded = EXCLUDED.founded,
                description = EXCLUDED.description,
                specialties = EXCLUDED.specialties,
                logo_url = EXCLUDED.logo_url,
                source = EXCLUDED.source,
                updated_at = EXCLUDED.updated_at
        """
        self.conn.execute(
            query,
            [
                company.company_id,
                company.name,
                company.company_url,
                company.website,
                company.industry,
                company.company_size,
                company.employee_count,
                company.follower_count,
                company.headquarters,
                company.founded,
                company.description,
                json.dumps(company.specialties),
                company.logo_url,
                company.source,
                company.discovered_at,
                now,
            ],
        )

    @staticmethod
    def _row_to_company(row: tuple) -> Company:
        """Build a Company from a companies table row in canonical column order."""
        try:
            specialties = json.loads(row[11]) if row[11] else []
        except Exception:
            specialties = []

        discovered = row[14]
        if isinstance(discovered, str):
            discovered = datetime.fromisoformat(discovered)

        return Company(
            company_id=row[0],
            name=row[1],
            company_url=row[2] or "",
            website=row[3],
            industry=row[4],
            company_size=row[5],
            employee_count=row[6],
            follower_count=row[7],
            headquarters=row[8],
            founded=row[9],
            description=row[10],
            specialties=specialties,
            logo_url=row[12],
            source=row[13] or "dom_selectolax",
            discovered_at=discovered,
        )

    _COMPANY_SELECT_COLUMNS = """
            company_id, name, company_url, website, industry, company_size,
            employee_count, follower_count, headquarters, founded, description,
            specialties, logo_url, source, discovered_at
    """

    def query_companies(
        self,
        industry: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Company]:
        """Query companies matching an optional industry pattern, ordered by name ASC."""
        query = f"SELECT {self._COMPANY_SELECT_COLUMNS} FROM companies WHERE 1=1"
        params: list = []

        if industry and industry.strip():
            query += " AND industry ILIKE ?"
            params.append(f"%{industry.strip()}%")

        query += " ORDER BY name ASC"

        if limit is not None and int(limit) > 0:
            query += " LIMIT ?"
            params.append(int(limit))

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_company(row) for row in rows]

    def get_company(self, company_id_or_url: str) -> Optional[Company]:
        """Fetch a single company by company_id or company URL (raw slug or full LinkedIn URL)."""
        clean_target = (company_id_or_url or "").strip()
        try:
            slug = extract_company_slug_from_url(clean_target) or clean_target
        except ValueError:
            slug = clean_target
        row = self.conn.execute(
            f"""
            SELECT {self._COMPANY_SELECT_COLUMNS}
            FROM companies
            WHERE company_id = ? OR company_id = ? OR company_url ILIKE ?
            """,
            [clean_target, slug, f"%{slug}%"],
        ).fetchone()
        if not row:
            return None
        return self._row_to_company(row)

    def upsert_posts(self, posts: List[Post]) -> int:
        """
        Upsert a batch of LinkedIn posts idempotently.
        Handles conflicts on post_id by updating all mutable columns and setting updated_at.
        Returns the count of posts upserted.
        """
        if not posts:
            return 0

        # Deduplicate within batch keeping latest entry
        deduped: dict[str, Post] = {}
        for p in posts:
            deduped[p.post_id] = p

        now = datetime.now(timezone.utc)
        rows = [
            (
                p.post_id,
                p.post_url,
                p.author_name,
                p.author_type,
                p.author_id,
                p.text,
                json.dumps(p.hashtags),
                p.posted_at,
                p.like_count,
                p.comment_count,
                p.repost_count,
                p.topic_match_score,
                p.author_match_score,
                p.author_warmth_tier,
                p.source,
                p.discovered_at,
                now,
            )
            for p in deduped.values()
        ]

        query = """
            INSERT INTO posts (
                post_id, post_url, author_name, author_type, author_id, text,
                hashtags, posted_at, like_count, comment_count, repost_count,
                topic_match_score, author_match_score, author_warmth_tier, source,
                discovered_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (post_id) DO UPDATE SET
                post_url = EXCLUDED.post_url,
                author_name = EXCLUDED.author_name,
                author_type = EXCLUDED.author_type,
                author_id = EXCLUDED.author_id,
                text = EXCLUDED.text,
                hashtags = EXCLUDED.hashtags,
                posted_at = EXCLUDED.posted_at,
                like_count = EXCLUDED.like_count,
                comment_count = EXCLUDED.comment_count,
                repost_count = EXCLUDED.repost_count,
                topic_match_score = EXCLUDED.topic_match_score,
                author_match_score = EXCLUDED.author_match_score,
                author_warmth_tier = EXCLUDED.author_warmth_tier,
                source = EXCLUDED.source,
                updated_at = EXCLUDED.updated_at
        """
        self.conn.executemany(query, rows)
        return len(rows)

    @staticmethod
    def _row_to_post(row: tuple) -> Post:
        """Build a Post from a posts table row in canonical column order."""
        try:
            hashtags = json.loads(row[6]) if row[6] else []
        except Exception:
            hashtags = []

        discovered = row[15]
        if isinstance(discovered, str):
            discovered = datetime.fromisoformat(discovered)

        return Post(
            post_id=row[0],
            post_url=row[1] or "",
            author_name=row[2],
            author_type=row[3] or "person",
            author_id=row[4],
            text=row[5],
            hashtags=hashtags,
            posted_at=row[7],
            like_count=row[8],
            comment_count=row[9],
            repost_count=row[10],
            topic_match_score=float(row[11] or 0.0),
            author_match_score=float(row[12] or 0.0),
            author_warmth_tier=row[13],
            source=row[14] or "dom_selectolax",
            discovered_at=discovered,
        )

    _POST_SELECT_COLUMNS = """
            post_id, post_url, author_name, author_type, author_id, text,
            hashtags, posted_at, like_count, comment_count, repost_count,
            topic_match_score, author_match_score, author_warmth_tier, source,
            discovered_at
    """

    def query_posts(
        self,
        author: Optional[str] = None,
        min_topic_score: float = 0.0,
        limit: Optional[int] = None,
    ) -> List[Post]:
        """
        Query posts matching optional author pattern and minimum topic match score.
        Results are ordered by topic_match_score DESC, author_match_score DESC, discovered_at DESC.
        """
        query = f"""
            SELECT {self._POST_SELECT_COLUMNS}
            FROM posts
            WHERE topic_match_score >= ?
        """
        params: list = [float(min_topic_score)]

        if author and author.strip():
            query += " AND author_name ILIKE ?"
            params.append(f"%{author.strip()}%")

        query += " ORDER BY topic_match_score DESC, author_match_score DESC, discovered_at DESC"

        if limit is not None and int(limit) > 0:
            query += " LIMIT ?"
            params.append(int(limit))

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_post(row) for row in rows]

    def get_post(self, post_id_or_url: str) -> Optional[Post]:
        """Fetch a single post by post_id or post URL (raw ID or full LinkedIn URL)."""
        clean_target = (post_id_or_url or "").strip()
        try:
            post_id = extract_post_id_from_url(clean_target) or clean_target
        except ValueError:
            post_id = clean_target
        row = self.conn.execute(
            f"""
            SELECT {self._POST_SELECT_COLUMNS}
            FROM posts
            WHERE post_id = ? OR post_id = ?
            """,
            [clean_target, post_id],
        ).fetchone()
        if not row:
            return None
        return self._row_to_post(row)

    def upsert_dm_thread(self, thread: DMThread) -> None:
        """Upsert a single DM thread record, serializing messages to JSON and updating on conflict."""
        now = datetime.now(timezone.utc)
        query = """
            INSERT INTO dm_threads (
                thread_id, participant_name, participant_id, participant_url,
                messages, unread_count, last_message_at, source, discovered_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (thread_id) DO UPDATE SET
                participant_name = EXCLUDED.participant_name,
                participant_id = EXCLUDED.participant_id,
                participant_url = EXCLUDED.participant_url,
                messages = EXCLUDED.messages,
                unread_count = EXCLUDED.unread_count,
                last_message_at = EXCLUDED.last_message_at,
                source = EXCLUDED.source,
                updated_at = EXCLUDED.updated_at
        """
        self.conn.execute(
            query,
            [
                thread.thread_id,
                thread.participant_name,
                thread.participant_id,
                thread.participant_url,
                json.dumps([m.model_dump() for m in thread.messages]),
                thread.unread_count,
                thread.last_message_at,
                thread.source,
                thread.discovered_at,
                now,
            ],
        )

    @staticmethod
    def _row_to_dm_thread(row: tuple) -> DMThread:
        """Build a DMThread from a dm_threads table row in canonical column order."""
        messages: List[DMMessage] = []
        if row[4]:
            try:
                raw_msgs = json.loads(row[4])
                if isinstance(raw_msgs, list):
                    messages = [DMMessage(**m) for m in raw_msgs]
            except Exception:
                pass

        discovered = row[8]
        if isinstance(discovered, str):
            discovered = datetime.fromisoformat(discovered)

        return DMThread(
            thread_id=row[0],
            participant_name=row[1],
            participant_id=row[2],
            participant_url=row[3],
            messages=messages,
            unread_count=int(row[5] or 0),
            last_message_at=row[6],
            source=row[7] or "dom_selectolax",
            discovered_at=discovered,
        )

    _DM_THREAD_SELECT_COLUMNS = """
            thread_id, participant_name, participant_id, participant_url,
            messages, unread_count, last_message_at, source, discovered_at
    """

    def get_dm_thread(self, thread_id: str) -> Optional[DMThread]:
        """Fetch a single DM thread by primary key thread_id, deserializing messages JSON."""
        row = self.conn.execute(
            f"""
            SELECT {self._DM_THREAD_SELECT_COLUMNS}
            FROM dm_threads
            WHERE thread_id = ?
            """,
            [thread_id],
        ).fetchone()
        if not row:
            return None
        return self._row_to_dm_thread(row)

    def query_dm_threads(
        self,
        participant: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[DMThread]:
        """Query DM threads matching an optional participant name pattern, ordered by discovered_at DESC."""
        query = f"SELECT {self._DM_THREAD_SELECT_COLUMNS} FROM dm_threads WHERE 1=1"
        params: list = []

        if participant and participant.strip():
            query += " AND participant_name ILIKE ?"
            params.append(f"%{participant.strip()}%")

        query += " ORDER BY discovered_at DESC"

        if limit is not None and int(limit) > 0:
            query += " LIMIT ?"
            params.append(int(limit))

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_dm_thread(row) for row in rows]

    def upsert_engagement_action(self, action: EngagementAction) -> None:
        """Upsert a single drafted engagement action, updating mutable columns and bumping updated_at on conflict."""
        now = datetime.now(timezone.utc)
        query = """
            INSERT INTO engagement_actions (
                action_id, target_type, target_id, target_url, action_type,
                reaction_type, draft_content, rubric_score, rationale, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (action_id) DO UPDATE SET
                target_type = EXCLUDED.target_type,
                target_id = EXCLUDED.target_id,
                target_url = EXCLUDED.target_url,
                action_type = EXCLUDED.action_type,
                reaction_type = EXCLUDED.reaction_type,
                draft_content = EXCLUDED.draft_content,
                rubric_score = EXCLUDED.rubric_score,
                rationale = EXCLUDED.rationale,
                status = EXCLUDED.status,
                updated_at = EXCLUDED.updated_at
        """
        self.conn.execute(
            query,
            [
                action.action_id,
                action.target_type,
                action.target_id,
                action.target_url,
                action.action_type,
                action.reaction_type,
                action.draft_content,
                action.rubric_score,
                action.rationale,
                action.status,
                action.created_at,
                action.updated_at or now,
            ],
        )

    @staticmethod
    def _row_to_engagement_action(row: tuple) -> EngagementAction:
        """Build an EngagementAction from an engagement_actions table row in canonical column order."""
        created = row[10]
        if isinstance(created, str):
            created = datetime.fromisoformat(created)

        updated = row[11]
        if isinstance(updated, str):
            updated = datetime.fromisoformat(updated)

        return EngagementAction(
            action_id=row[0],
            target_type=row[1],
            target_id=row[2],
            target_url=row[3],
            action_type=row[4],
            reaction_type=row[5],
            draft_content=row[6],
            rubric_score=float(row[7] or 0.0),
            rationale=row[8],
            status=row[9] or "drafted",
            created_at=created,
            updated_at=updated,
        )

    _ENGAGEMENT_ACTION_SELECT_COLUMNS = """
            action_id, target_type, target_id, target_url, action_type,
            reaction_type, draft_content, rubric_score, rationale, status,
            created_at, updated_at
    """

    def query_engagement_actions(
        self,
        status: Optional[str] = None,
        target_type: Optional[str] = None,
        min_rubric_score: float = 0.0,
        limit: Optional[int] = None,
    ) -> List[EngagementAction]:
        """
        Query drafted engagement actions with optional status/target_type filters and minimum rubric score.
        Results are ordered by rubric_score DESC.
        """
        query = f"""
            SELECT {self._ENGAGEMENT_ACTION_SELECT_COLUMNS}
            FROM engagement_actions
            WHERE rubric_score >= ?
        """
        params: list = [float(min_rubric_score)]

        if status and status.strip():
            query += " AND status = ?"
            params.append(status.strip())

        if target_type and target_type.strip():
            query += " AND target_type = ?"
            params.append(target_type.strip())

        query += " ORDER BY rubric_score DESC"

        if limit is not None and int(limit) > 0:
            query += " LIMIT ?"
            params.append(int(limit))

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_engagement_action(row) for row in rows]

    def set_engagement_action_status(self, action_id: str, status: str) -> bool:
        """
        Update an engagement action's status -- this is how a human approves/rejects a drafted
        action after review. Must only ever be called with a status the human chose, never
        invoked autonomously by this codebase.
        Returns True if a matching action_id was updated, False if not found.
        """
        now = datetime.now(timezone.utc)
        existing = self.conn.execute(
            "SELECT action_id FROM engagement_actions WHERE action_id = ?", [action_id]
        ).fetchone()
        if not existing:
            return False
        self.conn.execute(
            "UPDATE engagement_actions SET status = ?, updated_at = ? WHERE action_id = ?",
            [status, now, action_id],
        )
        return True

    def update_outreach_status(
        self,
        contact_urn: str,
        company_slug: str,
        status: str,
        note: Optional[str] = None,
        sequence_draft: Optional[str] = None,
        last_touch: Optional[str] = None,
    ) -> OutreachRecord:
        """
        Record or transition the outreach status of a contact.
        Preserves existing note and draft if new values are omitted.
        """
        now = datetime.now(timezone.utc)
        clean_slug = _slugify(company_slug) or company_slug
        norm_status = _normalize_outreach_status(status)

        query = """
            INSERT INTO outreach_records (
                contact_urn, company_slug, status, connection_note, sequence_draft, last_updated,
                last_touch
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (contact_urn) DO UPDATE SET
                company_slug = EXCLUDED.company_slug,
                status = EXCLUDED.status,
                connection_note = COALESCE(EXCLUDED.connection_note, outreach_records.connection_note),
                sequence_draft = COALESCE(EXCLUDED.sequence_draft, outreach_records.sequence_draft),
                last_updated = EXCLUDED.last_updated,
                last_touch = COALESCE(EXCLUDED.last_touch, outreach_records.last_touch)
        """
        self.conn.execute(
            query,
            [contact_urn, clean_slug, norm_status, note, sequence_draft, now, last_touch],
        )

        row = self.conn.execute(
            """
            SELECT contact_urn, company_slug, status, connection_note, sequence_draft, last_updated,
                   last_touch
            FROM outreach_records
            WHERE contact_urn = ?
            """,
            [contact_urn],
        ).fetchone()

        last_updated = row[5]
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)

        return OutreachRecord(
            contact_urn=row[0],
            company_slug=row[1],
            status=row[2],
            connection_note=row[3],
            sequence_draft=row[4],
            last_updated=last_updated,
            last_touch=row[6],
        )

    def get_outreach_record(self, contact_urn: str) -> Optional[OutreachRecord]:
        """Fetch outreach status record for a given contact URN."""
        row = self.conn.execute(
            """
            SELECT contact_urn, company_slug, status, connection_note, sequence_draft, last_updated,
                   last_touch
            FROM outreach_records
            WHERE contact_urn = ?
            """,
            [contact_urn],
        ).fetchone()
        if not row:
            return None

        last_updated = row[5]
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)

        return OutreachRecord(
            contact_urn=row[0],
            company_slug=row[1],
            status=row[2],
            connection_note=row[3],
            sequence_draft=row[4],
            last_updated=last_updated,
            last_touch=row[6],
        )

    def count_contacts(self) -> int:
        """Return total number of contacts stored in the database."""
        row = self.conn.execute("SELECT COUNT(*) FROM contacts").fetchone()
        return int(row[0]) if row else 0

    def count_outreach_records(self) -> int:
        """Return total number of outreach records stored in the database."""
        row = self.conn.execute("SELECT COUNT(*) FROM outreach_records").fetchone()
        return int(row[0]) if row else 0

    # Header aliases (lowercased) -> canonical column key for the network table.
    _NETWORK_COLUMN_ALIASES = {
        "contact": "name",
        "name": "name",
        "organization": "company",
        "current organization": "company",
        "company": "company",
        "relationship": "relationship",
        "last contact": "last_touch",
        "last touch": "last_touch",
        "next step": "next_action",
        "next action": "next_action",
        "status": "status",
    }
    # Positional fallback when a table has no recognizable header row (legacy 6-col layout).
    _NETWORK_LEGACY_LAYOUT = [
        "name", "company", "relationship", "last_touch", "next_action", "status",
    ]

    @staticmethod
    def _split_markdown_sections(content: str) -> dict[str, str]:
        """Map lowercased `## Heading` text -> section body (up to the next `## `)."""
        sections: dict[str, str] = {}
        parts = re.split(r"^##[ \t]+(?!#)(.+?)[ \t]*$", content, flags=re.MULTILINE)
        # parts = [preamble, heading1, body1, heading2, body2, ...]
        for i in range(1, len(parts) - 1, 2):
            sections.setdefault(parts[i].strip().lower(), parts[i + 1])
        return sections

    @staticmethod
    def _split_table_row(line: str) -> List[str]:
        # Preserve escaped pipes \| in markdown table columns
        escaped = line.strip().replace(r"\|", "__ESCAPED_PIPE__")
        return [c.replace("__ESCAPED_PIPE__", "|").strip() for c in escaped.split("|")[1:-1]]

    @staticmethod
    def _scrub_contact_pii(text: Optional[str]) -> Optional[str]:
        """Drop emails and phone numbers from free text lifted out of Contact Details."""
        if not text:
            return text
        text = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "", text)
        text = re.sub(r"(?<![\w/])\+?\d[\d\s().-]{8,}\d(?![\w/])", "", text)
        return re.sub(r"\s{2,}", " ", text).strip()

    def sync_from_network_markdown(self, markdown_path: str) -> int:
        """
        Ingest contacts and outreach statuses from _shared_facts/NETWORK.md into DuckDB.

        Accepts either heading set:
          table:   `## Tracker` or `## Contacts`
          details: `## Contact Records` or `## Contact Details`
        Table columns are resolved by header name (see _NETWORK_COLUMN_ALIASES), so
        6- and 7-column layouts both work. Only public profile fields (URL, location,
        headline, company, relationship) are read from detail blocks; phone numbers,
        birthdays and emails are never copied.
        """
        full_path = os.path.expanduser(markdown_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Network markdown file not found: {full_path}")

        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        sections = self._split_markdown_sections(content)

        # Step 1: Parse Contact Details/Records for enriched metadata (URLs, location, role)
        details: dict[str, dict] = {}
        details_text = next(
            (sections[h] for h in ("contact records", "contact details") if h in sections),
            None,
        )
        if details_text:
            subsections = re.findall(
                r"^###\s+([^\n]+)\n(.*?)(?=\n###|\Z)",
                details_text,
                flags=re.MULTILINE | re.DOTALL,
            )
            for raw_title, body in subsections:
                title = raw_title.strip()
                if "—" in title:  # Skip templates
                    continue
                url_m = re.search(r"(https://www\.linkedin\.com/in/[^\s\)\"']+)", body)
                loc_m = re.search(r"\*\*Location:\*\*\s*([^\n]+)", body)
                role_m = re.search(
                    r"\*\*(?:Current headline|Current role):\*\*\s*([^\n]+)", body
                )
                comp_m = re.search(r"\*\*(?:Company|Company shown):\*\*\s*([^\n]+)", body)
                rel_m = re.search(r"\*\*Relationship:\*\*\s*([^\n]+)", body)

                def _field(m):
                    return self._scrub_contact_pii(m.group(1).strip()) if m else None

                details[title.lower()] = {
                    "original_title": title,
                    "url": canonicalize_linkedin_url(url_m.group(1)) if url_m else None,
                    "location": _field(loc_m),
                    "headline": _field(role_m),
                    "company": _field(comp_m),
                    "relationship": _field(rel_m),
                }

        # (contact, company_slug, status, note, last_touch). The contact object is kept
        # (not its urn) because upsert_contacts may remap contact.urn_id onto an existing
        # row with the same profile_url; outreach must key against the final id.
        outreach_to_sync: List[tuple] = []
        contacts_to_upsert: List[LinkedInContact] = []
        seen_urns = set()

        # Step 2: Parse the contacts table (## Tracker / ## Contacts)
        table_text = next(
            (sections[h] for h in ("tracker", "contacts") if h in sections), ""
        )
        colmap: Optional[dict[str, int]] = None
        for line in table_text.splitlines():
            line_str = line.strip()
            if not line_str.startswith("|"):
                continue
            cols = self._split_table_row(line_str)
            # Skip the markdown separator row (e.g. "| --- | --- |"), spaced or not.
            if cols and all(re.fullmatch(r":?-{2,}:?", c) for c in cols):
                continue
            if colmap is None:
                header = {
                    self._NETWORK_COLUMN_ALIASES[c.lower()]: i
                    for i, c in reversed(list(enumerate(cols)))
                    if c.lower() in self._NETWORK_COLUMN_ALIASES
                }
                if "name" in header:
                    colmap = header
                    continue
                colmap = {k: i for i, k in enumerate(self._NETWORK_LEGACY_LAYOUT)}

            def cell(key: str) -> str:
                i = colmap.get(key)
                return cols[i] if i is not None and i < len(cols) else ""

            name = cell("name")
            company = cell("company")
            rel = cell("relationship")
            action_raw = cell("next_action")
            status_raw = cell("status")
            last_touch_raw = cell("last_touch")
            if not (name and (company or rel)):
                continue

            # Find matching details section if available
            matched_detail = None
            for d_name, d_val in details.items():
                # Exclude group headings from fuzzy name matching
                if " & " in d_name or " and " in d_name:
                    continue
                if d_name in name.lower() or name.lower() in d_name:
                    matched_detail = d_val
                    break

            degree = _normalize_network_degree(rel)
            m_count, m_sample = _parse_mutuals_from_text(rel)

            profile_url = ""
            if matched_detail and matched_detail.get("url"):
                profile_url = matched_detail["url"]

            if profile_url:
                slug = profile_url.rstrip("/").split("/")[-1]
            else:
                slug = _slugify(name)
            urn_id = f"urn:li:person:{slug}"

            location = None
            if matched_detail and matched_detail.get("location"):
                location = matched_detail["location"]
            else:
                loc_m = re.search(r"(?:SF Bay Area|[A-Z][a-zA-Z\s]+,\s*[A-Z]{2})", rel)
                if loc_m:
                    location = loc_m.group(0).strip()

            headline = (
                matched_detail.get("headline")
                if (matched_detail and matched_detail.get("headline"))
                else rel
            )

            contact = LinkedInContact(
                urn_id=urn_id,
                name=name,
                headline=headline or "",
                profile_url=profile_url,
                degree=degree,
                location=location,
                current_company=company,
                mutual_count=m_count,
                mutual_sample=m_sample,
                role_match_score=0.0,
                company_match_score=0.0,
                source="dom_selectolax",
            )
            # LinkedInContact canonicalizes urn_id from profile_url when a handle is
            # present (see schemas.py), so use contact.urn_id from here on.
            contacts_to_upsert.append(contact)
            seen_urns.add(contact.urn_id)

            norm_status = _normalize_outreach_status(status_raw)
            note_parts = [
                p
                for p in [
                    status_raw.strip(),
                    f"Next action: {action_raw.strip()}"
                    if action_raw.strip() and action_raw != "None"
                    else None,
                ]
                if p
            ]
            outreach_to_sync.append(
                (
                    contact,
                    _slugify(company) or company.lower(),
                    norm_status,
                    " | ".join(note_parts) if note_parts else None,
                    last_touch_raw or None,
                )
            )

        # Step 3: Parse standalone individual entries from Contact Details not in the table
        for d_key, d_val in details.items():
            # Skip multi-person group headers
            if " & " in d_key or " and " in d_key:
                continue

            orig_title = d_val["original_title"]
            url = d_val.get("url") or ""
            slug = url.rstrip("/").split("/")[-1] if url else _slugify(orig_title)
            urn_id = f"urn:li:person:{slug}"

            company = d_val.get("company")
            if not company:
                if "webflow" in (d_val.get("relationship") or "").lower():
                    company = "Webflow Community"
                else:
                    company = "Network Connector"

            degree = _normalize_network_degree(d_val.get("relationship"))
            headline = d_val.get("headline") or d_val.get("relationship") or ""

            contact = LinkedInContact(
                urn_id=urn_id,
                name=orig_title,
                headline=headline,
                profile_url=url,
                degree=degree,
                location=d_val.get("location"),
                current_company=company,
                mutual_count=0,
                mutual_sample=[],
                source="dom_selectolax",
            )

            # Compare using the canonicalized id so entries already captured from the
            # table aren't duplicated here.
            if contact.urn_id not in seen_urns:
                contacts_to_upsert.append(contact)
                seen_urns.add(contact.urn_id)
                outreach_to_sync.append(
                    (
                        contact,
                        _slugify(company),
                        "discovered",
                        f"Parsed from detailed section: {headline[:80]}",
                        None,
                    )
                )

        # Perform idempotent upserts to DuckDB (may remap contact.urn_id in place)
        total_upserted = self.upsert_contacts(contacts_to_upsert)

        # Record outreach statuses against the final, post-upsert contact ids
        for contact, co_slug, status_val, note_val, touch_val in outreach_to_sync:
            self._rekey_legacy_outreach(contact.urn_id)
            self.update_outreach_status(
                contact_urn=contact.urn_id,
                company_slug=co_slug,
                status=status_val,
                note=note_val,
                last_touch=touch_val,
            )

        return total_upserted

    def _rekey_legacy_outreach(self, urn_id: str) -> None:
        """
        Older syncs keyed outreach_records as `urn:li:person:<handle>` (and with
        un-lowercased handles) while contacts are stored as `urn:li:member:<handle>`,
        orphaning those rows. Move such a row onto the canonical id so its note and
        draft survive, unless a canonical row already exists.
        """
        tail = urn_id.rsplit(":", 1)[-1].lower()
        row = self.conn.execute(
            "SELECT 1 FROM outreach_records WHERE contact_urn = ?", [urn_id]
        ).fetchone()
        if row:
            return
        legacy = self.conn.execute(
            """
            SELECT contact_urn FROM outreach_records
            WHERE lower(contact_urn) = ? OR lower(contact_urn) = ?
            """,
            [f"urn:li:person:{tail}", f"urn:li:member:{tail}"],
        ).fetchone()
        if legacy:
            self.conn.execute(
                "UPDATE outreach_records SET contact_urn = ? WHERE contact_urn = ?",
                [urn_id, legacy[0]],
            )

    def close(self) -> None:
        """Close connection to DuckDB."""
        if hasattr(self, "conn") and self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    print("======================================================================")
    print("  Q4 Pipeline Node 2d: NetworkDatabase Standalone Verification Test   ")
    print("======================================================================")

    # -------------------------------------------------------------------------
    # Test Phase 1: Database Creation & Table Initialization
    # -------------------------------------------------------------------------
    print("\n[Phase 1] Initializing in-memory DuckDB and verifying schema...")
    db = NetworkDatabase(":memory:")
    assert db.count_contacts() == 0, "Contacts table must initially be empty"
    assert db.count_outreach_records() == 0, "Outreach records must initially be empty"
    print("  ✓ contacts and outreach_records tables initialized successfully.")


    # -------------------------------------------------------------------------
    # Test Phase 2: Upserting Mock Contacts
    # -------------------------------------------------------------------------
    print("\n[Phase 2] Upserting mock LinkedInContact objects...")
    mock1 = LinkedInContact(
        urn_id="urn:li:person:selina-kyle-mock",
        name="Selina Kyle",
        headline="Talent at Halyard",
        profile_url="https://www.linkedin.com/in/selina-kyle-mock",
        degree="1st",
        location="Alameda, CA",
        current_company="Halyard",
        mutual_count=9,
        mutual_sample=["Jean Grey", "Jim Gordon"],
        role_match_score=95.0,
        company_match_score=98.0,
        source="dom_selectolax",
    )
    mock2 = LinkedInContact(
        urn_id="urn:li:person:tony-stark-mock",
        name="Tony Stark",
        headline="Head of Growth Engineering @ Verdant",
        profile_url="https://www.linkedin.com/in/tony-stark-mock",
        degree="2nd",
        location="United States",
        current_company="Verdant",
        mutual_count=1,
        mutual_sample=["Nick Fury"],
        role_match_score=88.0,
        company_match_score=92.0,
        source="cdp_voyager_graphql",
    )
    mock3 = LinkedInContact(
        urn_id="urn:li:person:diana-prince-mock",
        name="Diana Prince",
        headline="VP Growth Marketing & Operations @ Larkspur",
        profile_url="https://www.linkedin.com/in/diana-prince-mock",
        degree="2nd",
        location="San Francisco, CA",
        current_company="Larkspur",
        mutual_count=1,
        mutual_sample=["Peter Parker"],
        role_match_score=75.0,
        company_match_score=85.0,
        source="dom_selectolax",
    )

    upserted_count = db.upsert_contacts([mock1, mock2, mock3])
    assert upserted_count == 3, f"Expected 3 contacts upserted, got {upserted_count}"
    assert db.count_contacts() == 3, "Database count mismatch after mock insert"
    print(f"  ✓ Upserted {upserted_count} mock contacts successfully.")

    # -------------------------------------------------------------------------
    # Test Phase 3: Querying Contacts by Company and Match Scores
    # -------------------------------------------------------------------------
    print("\n[Phase 3] Querying contacts by company and score filters...")
    halyard_results = db.query_contacts(company="Halyard")
    assert len(halyard_results) == 1, "Expected 1 Halyard mock contact"
    assert halyard_results[0].name == "Selina Kyle"
    assert halyard_results[0].mutual_sample == ["Jean Grey", "Jim Gordon"]

    high_role_matches = db.query_contacts(min_role_score=80.0)
    assert len(high_role_matches) == 2, f"Expected 2 matches >= 80, got {len(high_role_matches)}"
    assert high_role_matches[0].urn_id == "urn:li:member:selina-kyle-mock"
    assert high_role_matches[1].urn_id == "urn:li:member:tony-stark-mock"
    print("  ✓ Company filter and descending score ordering verified.")

    # -------------------------------------------------------------------------
    # Test Phase 4: Conflict Handling & Deduplication
    # -------------------------------------------------------------------------
    print("\n[Phase 4] Verifying idempotency and conflict resolution on re-insert...")
    mock1_updated = LinkedInContact(
        urn_id="urn:li:person:selina-kyle-mock",
        name="Selina Kyle",
        headline="Director of Talent Acquisition @ Halyard",
        profile_url="https://www.linkedin.com/in/selina-kyle-mock",
        degree="1st",
        location="Alameda, CA",
        current_company="Halyard",
        mutual_count=14,
        mutual_sample=["Jean Grey", "Jim Gordon", "Wanda Maximoff"],
        role_match_score=99.5,
        company_match_score=99.0,
        source="cdp_voyager_graphql",
    )
    db.upsert_contacts([mock1_updated])
    assert db.count_contacts() == 3, "Duplicate record inserted! Count should remain 3."

    selina_check = db.get_contact("urn:li:member:selina-kyle-mock")
    assert selina_check is not None
    assert selina_check.headline == "Director of Talent Acquisition @ Halyard"
    assert selina_check.role_match_score == 99.5
    assert selina_check.mutual_count == 14
    assert len(selina_check.mutual_sample) == 3
    print("  ✓ Idempotency verified: existing record updated in place without row duplication.")

    # -------------------------------------------------------------------------
    # Test Phase 5: Outreach State Transitions & Note Preservation
    # -------------------------------------------------------------------------
    print("\n[Phase 5] Testing outreach status transitions...")
    rec1 = db.update_outreach_status(
        contact_urn="urn:li:member:selina-kyle-mock",
        company_slug="halyard",
        status="drafted",
        note="Initial intro referencing Alameda local proximity",
    )
    assert rec1.status == "drafted"
    assert rec1.connection_note == "Initial intro referencing Alameda local proximity"

    # Advance state to connected without supplying note -> previous note must be preserved
    rec2 = db.update_outreach_status(
        contact_urn="urn:li:member:selina-kyle-mock",
        company_slug="halyard",
        status="connected",
    )
    assert rec2.status == "connected"
    assert rec2.connection_note == "Initial intro referencing Alameda local proximity"
    print("  ✓ Outreach transition verified: status advanced to 'connected' with prior note preserved.")

    # -------------------------------------------------------------------------
    # Test Phase 6: Live Sync & Verification from bundled synthetic fixture
    # -------------------------------------------------------------------------
    network_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "tests", "fixtures", "network_sample.md"
    )
    print(f"\n[Phase 6] Live sync against bundled fixture: {network_file}...")
    assert os.path.exists(network_file), f"Critical fixture file missing: {network_file}"

    # Use a fresh, dedicated database to test pure live ingestion without mock pollution
    live_db = NetworkDatabase(":memory:")
    synced_count = live_db.sync_from_network_markdown(network_file)
    print(f"  ✓ Synced {synced_count} contacts from network_sample.md into DuckDB.")
    assert synced_count == 12, f"Expected 12 contacts from network_sample.md, got {synced_count}"

    # Verify key network contacts parsed with correct fields:
    # 1. Selina Kyle (@ Halyard)
    selina = [c for c in live_db.query_contacts(company="Halyard") if "Selina" in c.name]
    assert len(selina) == 1, f"Expected exactly 1 Selina Kyle under Halyard, got {len(selina)}"
    s = selina[0]
    assert s.degree == "1st", f"Expected Selina Kyle degree 1st, got {s.degree}"
    assert "Alameda" in (s.location or ""), f"Expected Alameda location, got {s.location}"
    assert s.mutual_count >= 9, f"Expected >= 9 mutuals, got {s.mutual_count}"
    assert "Jean Grey" in s.mutual_sample, "Jean Grey missing from mutual sample"
    assert s.profile_url == "https://www.linkedin.com/in/selina-kyle"
    print(f"  ✓ 1. Selina Kyle: {s.current_company} | {s.degree} | {s.location} | {s.mutual_count} mutuals: {s.mutual_sample}")

    # 2. Diana Prince (@ Larkspur)
    diana = [c for c in live_db.query_contacts(company="Larkspur") if "Diana" in c.name]
    assert len(diana) == 1, f"Expected exactly 1 Diana Prince under Larkspur, got {len(diana)}"
    d = diana[0]
    assert d.degree == "2nd", f"Expected Diana Prince degree 2nd, got {d.degree}"
    assert "San Francisco" in (d.location or ""), f"Expected San Francisco location, got {d.location}"
    assert "Peter Parker" in d.mutual_sample, "Peter Parker missing from mutual sample"
    assert d.profile_url == "https://www.linkedin.com/in/diana-prince"
    print(f"  ✓ 2. Diana Prince: {d.current_company} | {d.degree} | {d.location} | mutuals: {d.mutual_sample}")

    # 3. Tony Stark (@ Verdant)
    tony = [c for c in live_db.query_contacts(company="Verdant") if "Tony" in c.name]
    assert len(tony) == 1, f"Expected exactly 1 Tony Stark under Verdant, got {len(tony)}"
    t = tony[0]
    assert t.degree == "2nd", f"Expected Tony Stark degree 2nd, got {t.degree}"
    assert "Growth Engineering" in t.headline, "Tony Stark headline mismatch"
    assert "Nick Fury" in t.mutual_sample, "Nick Fury missing from mutual sample"
    assert t.profile_url == "https://www.linkedin.com/in/tony-stark-eng"
    print(f"  ✓ 3. Tony Stark: {t.current_company} | {t.degree} | {t.headline} | mutuals: {t.mutual_sample}")

    # 4. Victor Stone (@ Halyard)
    victor = [c for c in live_db.query_contacts(company="Halyard") if "Victor" in c.name]
    assert len(victor) == 1, f"Expected 1 Victor Stone, got {len(victor)}"
    v = victor[0]
    assert v.degree == "2nd"
    assert "Berkeley" in (v.location or "")
    print(f"  ✓ 4. Victor Stone: {v.current_company} | {v.degree} | {v.location} | {v.headline}")

    # 5. Natasha Romanoff (@ Hexlight)
    natasha = [c for c in live_db.query_contacts(company="Hexlight") if "Natasha" in c.name]
    assert len(natasha) == 1, f"Expected 1 Natasha Romanoff contact, got {len(natasha)}"
    n = natasha[0]
    assert n.degree == "2nd", f"Expected Natasha Romanoff degree 2nd, got {n.degree}"
    assert "Steve Rogers" in n.mutual_sample, "Steve Rogers missing from mutual sample"
    print(f"  ✓ 5. Natasha Romanoff: {n.current_company} | {n.degree} | mutuals: {n.mutual_sample}")

    # 6. Bruce Banner (@ Hexlight) - Escaped pipe in Next-step column test
    bruce = [c for c in live_db.query_contacts(company="Hexlight") if "Bruce Banner" in c.name]
    assert len(bruce) == 1, "Bruce Banner must be present under Hexlight"
    b = bruce[0]
    assert "Head of Brand" in b.headline, f"Headline pipe parsing truncated headline: {b.headline}"
    assert "Scott Lang" in b.mutual_sample, "Scott Lang missing from mutual sample"
    print(f"  ✓ 6. Bruce Banner: {b.current_company} | {b.degree} | headline: '{b.headline}'")

    # 7. Peter Parker (@ Weftly)
    peter = [c for c in live_db.query_contacts() if "Peter Parker" in c.name]
    assert len(peter) == 1, "Peter Parker must be present"
    p = peter[0]
    assert "peter-parker" in p.profile_url, f"Expected profile URL for Peter Parker, got {p.profile_url}"
    print(f"  ✓ 7. Peter Parker: {p.name} | URL: {p.profile_url} | {p.current_company}")

    # 8. Evercourt (Casey Jones + Danny Torrance) - multi-contact company query
    evercourt_contacts = live_db.query_contacts(company="Evercourt")
    assert len(evercourt_contacts) == 2, f"Expected 2 Evercourt contacts, got {len(evercourt_contacts)}"
    print(f"  ✓ 8. Evercourt: {len(evercourt_contacts)} contacts verified: {[c.name for c in evercourt_contacts]}")

    # 9. Table cell escaped-pipe handling did not corrupt neighboring columns
    assert b.degree == "1st", "Escaped pipe in Next-step column corrupted column alignment"
    print("  ✓ 9. Escaped-pipe table cell parsing verified: column alignment preserved.")

    # -------------------------------------------------------------------------
    # Test Phase 7: Real Pipeline Company Queries & Target Roles
    # (Umbra, Zephyria, Larkspur, Verdant, Halyard, Hexlight)
    # -------------------------------------------------------------------------
    print("\n[Phase 7] Verifying queries across all 6 fictional pipeline companies & target roles...")

    # Enrich the existing Pepper Potts contact (discovered via markdown sync) with
    # additional pipeline-specific detail, simulating a follow-up Voyager GraphQL capture.
    pepper_contact = LinkedInContact(
        urn_id="urn:li:member:pepper-potts",
        name="Pepper Potts",
        headline="Head of Frontend & Marketing Web @ Umbra",
        profile_url="https://www.linkedin.com/in/pepper-potts",
        degree="2nd",
        location="San Francisco, CA",
        current_company="Umbra",
        mutual_count=3,
        mutual_sample=["Nick Fury", "Peter Parker"],
        role_match_score=94.0,
        company_match_score=97.0,
        source="cdp_voyager_graphql",
    )
    live_db.upsert_contacts([pepper_contact])
    live_db.update_outreach_status(
        contact_urn=pepper_contact.urn_id,
        company_slug="umbra",
        status="discovered",
        note="Engineering Manager, Marketing Web req (umbra.com & umbra-app.com)",
    )

    pipeline_targets = {
        "Umbra": {"min_count": 1, "target_role": "Engineering Manager, Marketing Web"},
        "Zephyria": {"min_count": 1, "target_role": "Marketing Engineer / Marketing Manager"},
        "Larkspur": {"min_count": 1, "target_role": "Principal Growth Marketing Engineer"},
        "Verdant": {"min_count": 1, "target_role": "Site Engineer / Growth Engineering"},
        "Halyard": {"min_count": 2, "target_role": "Staff Web Engineer / Marketing Engineer"},
        "Hexlight": {"min_count": 2, "target_role": "Web Engineer"},
    }

    for co_name, spec in pipeline_targets.items():
        co_contacts = live_db.query_contacts(company=co_name)
        assert len(co_contacts) >= spec["min_count"], (
            f"Expected >={spec['min_count']} contacts for {co_name}, found {len(co_contacts)}"
        )
        print(
            f"  ✓ Company '{co_name}': {len(co_contacts)} contacts verified | Target: {spec['target_role']}"
        )

    # -------------------------------------------------------------------------
    # Test Phase 8: Outreach Status Tracking Verification on Pipeline Contacts
    # -------------------------------------------------------------------------
    print("\n[Phase 8] Verifying outreach status records populated from markdown & pipeline...")
    # Amanda Waller (Selvane) -> Screen booked -> replied
    amanda_record = live_db.get_outreach_record("urn:li:member:amanda-waller")
    assert amanda_record is not None, "Outreach record for Amanda Waller must exist"
    assert amanda_record.status == "replied", f"Expected 'replied' status for Amanda Waller, got {amanda_record.status}"
    assert "Recruiter screen booked" in (amanda_record.connection_note or "")

    # Danny Rand (Zephyria) -> Email sent -> messaged
    danny_rand_record = live_db.get_outreach_record("urn:li:member:danny-rand")
    assert danny_rand_record is not None, "Outreach record for Danny Rand must exist"
    assert danny_rand_record.status == "messaged", f"Expected 'messaged' status for Danny Rand, got {danny_rand_record.status}"

    # Casey Jones (Evercourt) -> Role closed -> archived
    casey_record = live_db.get_outreach_record("urn:li:member:casey-jones")
    assert casey_record is not None
    assert casey_record.status == "archived", f"Expected 'archived' status for Casey Jones, got {casey_record.status}"

    # Danny Torrance (Evercourt) -> Outreach drafted -> drafted
    danny_torrance_record = live_db.get_outreach_record("urn:li:member:danny-torrance")
    assert danny_torrance_record is not None
    assert danny_torrance_record.status == "drafted", f"Expected 'drafted' status for Danny Torrance, got {danny_torrance_record.status}"

    # Pepper Potts (Umbra) -> newly enriched -> discovered
    pepper_record = live_db.get_outreach_record(pepper_contact.urn_id)
    assert pepper_record is not None
    assert pepper_record.status == "discovered"
    print("  ✓ Outreach lifecycle verified across states: replied, messaged, archived, drafted, discovered.")

    # -------------------------------------------------------------------------
    # Test Phase 9: Re-sync Idempotency Verification
    # -------------------------------------------------------------------------
    print("\n[Phase 9] Verifying re-sync idempotency...")
    total_before = live_db.count_contacts()
    live_db.sync_from_network_markdown(network_file)
    total_after = live_db.count_contacts()
    assert total_before == total_after, f"Sync not idempotent: count changed from {total_before} to {total_after}"
    print(f"  ✓ Re-sync idempotency confirmed: {total_after} contacts in DB unchanged.")

    # Clean shutdown
    db.close()
    live_db.close()
    print("\n======================================================================")
    print("  COMPLETION CRITERIA: ALL 9 EVALUATION PHASES PASSED WITH ZERO ERRORS")
    print("======================================================================")
