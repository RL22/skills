#!/usr/bin/env python3
"""
test_q4_pipeline.py - Comprehensive End-to-End Regression Test Suite for Q4 Pipeline.
Tests all 4 components (CDP Sniffer, DOM Parser, Entity Matcher, DuckDB Engine)
and the Unified CLI against real pipeline roles and network data.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Add scripts to sys.path
TEST_DIR = Path(__file__).parent
SCRIPTS_DIR = TEST_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from schemas import (
    EducationItem,
    ExperienceItem,
    LinkedInContact,
    LinkedInProfileDetailed,
    canonicalize_linkedin_url,
)
from dom_parser import (
    parse_linkedin_search_html,
    parse_linkedin_profile_html,
    _MOCK_SEARCH_PAGE_HTML,
    _MOCK_PROFILE_PAGE_HTML,
)
from cdp_interceptor import parse_voyager_json, _generate_synthetic_voyager_payload
from entity_matcher import score_role, score_company, rank_and_filter_contacts, compute_composite_score
from pipeline_db import NetworkDatabase

CLI_PATH = str(SCRIPTS_DIR / "cli.py")


def test_schema_canonicalization():
    print("\n1. Testing Pydantic URL Canonicalization & Schema Contracts...")
    dirty_url = "www.linkedin.com/in/alex-smith-123?miniProfileUrn=urn%3Ali%3Afsd_profile%3AACoAAB11111&trk=people-guest/"
    clean_url = canonicalize_linkedin_url(dirty_url)
    assert clean_url == "https://www.linkedin.com/in/alex-smith-123", f"Unexpected URL: {clean_url}"

    contact = LinkedInContact(
        urn_id="urn:li:fsd_profile:12345",
        name="  Bruce Wayne  ",
        headline="Growth & Marketing Web Engineer @ Verdant",
        profile_url=dirty_url,
        degree="2nd",
        source="cdp_voyager_graphql",
    )
    assert contact.name == "Bruce Wayne"
    assert contact.profile_url == "https://www.linkedin.com/in/alex-smith-123"
    assert contact.urn_id == "urn:li:member:alex-smith-123"
    assert contact.degree == "2nd"
    assert contact.current_company == "Verdant"
    print("   ✓ Passed: Schema cleaned URL parameters, canonicalized URN, and extracted current company.")


def test_dom_parser_benchmark():
    print("\n2. Testing Selectolax DOM Parser Throughput (<10ms target)...")
    t0 = time.monotonic()
    contacts = parse_linkedin_search_html(_MOCK_SEARCH_PAGE_HTML)
    duration_ms = (time.monotonic() - t0) * 1000

    assert len(contacts) >= 4, f"Expected >= 4 contacts, got {len(contacts)}"
    assert duration_ms < 10.0, f"Benchmark failed: took {duration_ms:.2f}ms (target <10ms)"
    print(f"   ✓ Passed: Extracted {len(contacts)} contacts in {duration_ms:.2f}ms (<10ms target).")


def test_cdp_voyager_extraction():
    print("\n3. Testing Voyager GraphQL JSON Payload Extraction...")
    mock_payload = _generate_synthetic_voyager_payload()
    contacts = parse_voyager_json(mock_payload)
    assert len(contacts) >= 3, f"Expected >= 3 contacts, got {len(contacts)}"

    # Check that real targets were parsed
    names = [c.name for c in contacts]
    assert any("Diana Prince" in n for n in names), "Diana Prince missing from Voyager extraction!"
    assert any("Tony Stark" in n for n in names), "Tony Stark missing from Voyager extraction!"
    assert any("Selina Kyle" in n for n in names), "Selina Kyle missing from Voyager extraction!"

    diana = next(c for c in contacts if "Diana Prince" in c.name)
    assert diana.degree == "2nd"
    assert diana.source == "cdp_voyager_graphql"
    print(f"   ✓ Passed: Extracted {len(contacts)} contacts from Voyager GraphQL including {', '.join(names[:3])}.")


def test_entity_matcher_real_roles():
    print("\n4. Testing RapidFuzz Matcher Across Pipeline Target Roles (core-cv derived)...")
    from entity_matcher import derive_targets_from_core_cv
    titles = derive_targets_from_core_cv().get("role_titles") or ["Marketing Engineer", "Senior Web Developer"]
    companies = ["Umbra", "Zephyria AI", "Nexoria", "ComplyCore", "Selvane", "Hexlight", "Larkspur", "Halyard", "Verdant"]
    test_cases = [
        (co, [titles[i % len(titles)]], f"{titles[i % len(titles)]} @ {co}", 85.0)
        for i, co in enumerate(companies)
    ]

    for company, roles, candidate_hl, min_expected in test_cases:
        r_score = score_role(roles, candidate_hl)
        c_score = score_company(company, candidate_hl)
        combined = compute_composite_score(r_score, c_score)
        assert combined >= min_expected, f"Failed match for {company}: score={combined:.1f} < {min_expected}"

    print(f"   ✓ Passed: All {len(test_cases)} real pipeline role evaluations scored above thresholds.")


def test_company_only_filtering():
    print("\n5. Testing Company-Only Filtering (No Roles Specified)...")
    contacts = [
        LinkedInContact(
            urn_id="urn:li:member:diana-prince",
            name="Diana Prince",
            headline="VP Growth Marketing & Operations",
            profile_url="https://www.linkedin.com/in/diana-prince",
            current_company="Larkspur",
            degree="2nd",
        ),
        LinkedInContact(
            urn_id="urn:li:member:tony-stark",
            name="Tony Stark",
            headline="Head of Growth Engineering",
            profile_url="https://www.linkedin.com/in/tony-stark-eng",
            current_company="Verdant",
            degree="2nd",
        ),
    ]
    # Filter for Larkspur only with empty roles
    filtered = rank_and_filter_contacts(contacts, target_roles=[], target_company="Larkspur")
    assert len(filtered) == 1, f"Expected 1 Larkspur contact, got {len(filtered)}"
    assert filtered[0].name == "Diana Prince"
    print("   ✓ Passed: Company-only filtering retained company matches without dropping on empty roles.")


def test_cross_node_deduplication():
    print("\n6. Testing Cross-Node URN Deduplication in DuckDB...")
    with NetworkDatabase(db_path=":memory:") as db:
        # Same person with 2 different URN namespaces (DOM vs CDP)
        c1 = LinkedInContact(
            urn_id="urn:li:member:selinakyle",
            name="Selina Kyle",
            headline="Talent at Halyard",
            profile_url="https://www.linkedin.com/in/selinakyle",
            degree="1st",
            current_company="Halyard",
            source="dom_selectolax",
        )
        c2 = LinkedInContact(
            urn_id="urn:li:fsd_profile:ACoAAB_SELINA_KYLE",
            name="Selina Kyle",
            headline="Talent at Halyard (Updated)",
            profile_url="https://www.linkedin.com/in/selinakyle",
            degree="1st",
            current_company="Halyard",
            source="cdp_voyager_graphql",
        )
        db.upsert_contacts([c1])
        db.upsert_contacts([c2])

        results = db.query_contacts(company="Halyard")
        assert len(results) == 1, f"Expected exactly 1 deduplicated record, found {len(results)}"
        assert results[0].headline == "Talent at Halyard (Updated)"
        print("   ✓ Passed: Contacts with different URN schemes but identical profile_url deduplicated cleanly.")


def test_duckdb_persistence_and_markdown_sync():
    print("\n7. Testing DuckDB Persistence & NETWORK.md Synchronization...")
    network_md = TEST_DIR / "fixtures" / "network_sample.md"
    assert network_md.exists(), f"Missing {network_md}"

    with NetworkDatabase(db_path=":memory:") as db:
        count = db.sync_from_network_markdown(str(network_md))
        assert count == 12, f"Expected 12 contacts, got {count}"

        # Verify Larkspur cluster
        larkspur_contacts = db.query_contacts(company="Larkspur")
        assert len(larkspur_contacts) >= 1, f"Expected >= 1 Larkspur contact, got {len(larkspur_contacts)}"
        assert any("Peter Parker" in c.mutual_sample for c in larkspur_contacts), "Peter Parker mutual link missing!"

        # Verify Halyard cluster
        halyard_contacts = db.query_contacts(company="Halyard")
        assert any("Selina Kyle" in c.name for c in halyard_contacts), "Selina Kyle missing from Halyard!"

        # Verify Verdant cluster
        verdant_contacts = db.query_contacts(company="Verdant")
        assert any("Tony Stark" in c.name for c in verdant_contacts), "Tony Stark missing from Verdant!"

    print(f"   ✓ Passed: Successfully ingested {count} contacts into DuckDB and verified clusters (Larkspur, Halyard, Verdant).")


def test_cli_subcommands():
    print("\n8. Testing Unified CLI Subcommands (list, limit, sync-network)...")
    import tempfile

    fixture_md = str(TEST_DIR / "fixtures" / "network_sample.md")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_db = os.path.join(tmp_dir, "cli_test.duckdb")

        # Seed an isolated, disposable DuckDB from the bundled synthetic fixture
        # (never the user's real, persistent network database).
        res_sync = subprocess.run(
            [sys.executable, CLI_PATH, "sync-network", "--path", fixture_md, "--db", tmp_db],
            capture_output=True,
            text=True,
        )
        assert res_sync.returncode == 0, f"CLI sync-network failed: {res_sync.stderr}"

        res = subprocess.run(
            [sys.executable, CLI_PATH, "list", "--limit", "3", "--db", tmp_db], capture_output=True, text=True
        )
        assert res.returncode == 0, f"CLI list failed: {res.stderr}"
        assert "Found" in res.stdout, f"Unexpected CLI output: {res.stdout}"

        res_comp = subprocess.run(
            [sys.executable, CLI_PATH, "list", "--company", "Larkspur", "--db", tmp_db],
            capture_output=True,
            text=True,
        )
        assert res_comp.returncode == 0
        assert "Diana Prince" in res_comp.stdout
    print("   ✓ Passed: CLI subcommands (sync-network, list with --limit and --company) executed cleanly with exit code 0.")


def test_profile_parsing_selectolax():
    print("\n9. Testing Detailed Profile Parsing via Selectolax (<10ms target)...")
    t0 = time.monotonic()
    profile = parse_linkedin_profile_html(_MOCK_PROFILE_PAGE_HTML, profile_url_hint="https://www.linkedin.com/in/tony-stark-eng")
    duration_ms = (time.monotonic() - t0) * 1000

    assert profile.name == "Tony Stark", f"Unexpected name: {profile.name}"
    assert profile.degree == "2nd", f"Unexpected degree: {profile.degree}"
    assert profile.current_company == "Verdant", f"Unexpected company: {profile.current_company}"
    assert profile.location == "San Francisco Bay Area", f"Unexpected location: {profile.location}"
    assert profile.mutual_count == 2, f"Expected 2 mutuals, got {profile.mutual_count}"
    assert profile.mutual_sample == ["Nick Fury"], f"Unexpected mutuals: {profile.mutual_sample}"
    assert profile.about and "high-velocity growth" in profile.about
    assert len(profile.experience) == 2, f"Expected 2 positions, got {len(profile.experience)}"
    assert profile.experience[0].title == "Head of Growth Engineering"
    assert profile.experience[0].company == "Verdant"
    assert len(profile.education) == 1
    assert "Glasgow" in profile.education[0].school
    assert len(profile.skills) >= 4
    assert "Next.js" in profile.skills
    assert duration_ms < 10.0, f"Benchmark failed: {duration_ms:.2f}ms >= 10ms"
    print(f"   ✓ Passed: Parsed complete profile (Tony Stark) with experience, education, skills, and mutuals in {duration_ms:.2f}ms.")


def test_detailed_profile_db_persistence():
    print("\n10. Testing Detailed Profile Persistence & Serialization in DuckDB...")
    with NetworkDatabase(db_path=":memory:") as db:
        profile = LinkedInProfileDetailed(
            urn_id="urn:li:member:tony-stark",
            name="Tony Stark",
            headline="Head of Growth Engineering @ Verdant",
            profile_url="https://www.linkedin.com/in/tony-stark-eng",
            degree="2nd",
            current_company="Verdant",
            location="San Francisco Bay Area",
            mutual_count=2,
            mutual_sample=["Nick Fury"],
            about="Building high-velocity growth infrastructure.",
            experience=[
                ExperienceItem(title="Head of Growth Engineering", company="Verdant", date_range="Apr 2022 - Present", duration="2 yrs 6 mos")
            ],
            education=[
                EducationItem(school="University of Glasgow", degree="BSc Computing Science")
            ],
            skills=["Next.js", "Growth Engineering", "A/B Testing"],
            warmth_degree=5,
            contact_tier="BRIDGE",
        )
        db.upsert_detailed_profile(profile)

        # Retrieve and verify
        retrieved = db.get_detailed_profile("tony-stark-eng")
        assert retrieved is not None, "Failed to retrieve profile by handle!"
        assert retrieved.name == "Tony Stark"
        assert retrieved.about == "Building high-velocity growth infrastructure."
        assert len(retrieved.experience) == 1
        assert retrieved.experience[0].title == "Head of Growth Engineering"
        assert retrieved.experience[0].company == "Verdant"
        assert retrieved.experience[0].duration == "2 yrs 6 mos"
        assert len(retrieved.education) == 1
        assert len(retrieved.skills) == 3
        assert retrieved.warmth_degree == 5
        assert retrieved.contact_tier == "BRIDGE"
    print("   ✓ Passed: Successfully persisted and retrieved detailed profile with experience/education/skills JSON.")


def test_cli_inspect_subcommand():
    print("\n11. Testing Unified CLI 'inspect' Subcommand (--html and --json)...")
    # Write mock HTML to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(_MOCK_PROFILE_PAGE_HTML)
        temp_path = f.name

    try:
        # Test 1: CLI help
        res_help = subprocess.run([sys.executable, CLI_PATH, "inspect", "--help"], capture_output=True, text=True)
        assert res_help.returncode == 0, f"CLI inspect --help failed: {res_help.stderr}"
        assert "--experience" in res_help.stdout

        # Test 2: CLI inspect with --html and --json
        res_json = subprocess.run(
            [sys.executable, CLI_PATH, "inspect", "--html", temp_path, "--roles", "Growth Engineering", "--json", "--no-save"],
            capture_output=True,
            text=True,
        )
        assert res_json.returncode == 0, f"CLI inspect failed: {res_json.stderr}"
        import json
        # Filter lines for JSON start
        json_str = res_json.stdout[res_json.stdout.find("{") :]
        data = json.loads(json_str)
        assert data["name"] == "Tony Stark"
        assert data["current_company"] == "Verdant"
        assert len(data["experience"]) == 2
        assert data["role_match_score"] > 80.0
        assert data["contact_tier"] == "BRIDGE"
        print("   ✓ Passed: CLI inspect subcommand executed offline HTML analysis and emitted valid structured JSON.")
    finally:
        os.unlink(temp_path)


_LIVE_LAYOUT_NETWORK_MD = r"""# Job Search Network

## Contacts

| Contact | Current organization | Relationship | Focus | Status | Last touch | Next action |
|---|---|---|---|---|---|---|
| Ada Quill | Fernwick | 2nd-degree LinkedIn connection; SF Bay Area; mutual: Bo Marlowe | Talent Partner | Not contacted | Never | Send connection request |
| Bo Marlowe | Fernwick | 1st-degree LinkedIn connection | Design lead | Applied online; awaiting reply | September 12, 2026 | Follow up \| ping again |
| Cy Thorne | Ostrava Labs | Recruiter | Web roles | Prior inbound | TBD | None |

## Relationship Workflow

1. Not a table.

## Contact Details

### Ada Quill
- **Company shown:** Fernwick
- **Current headline:** Talent Partner @ Fernwick
- **Location:** Portland, Oregon
- **LinkedIn:** [linkedin.com/in/ada-quill-1a2b](https://www.linkedin.com/in/ada-quill-1a2b/)
- **Phone:** 5550100199 (Home)
- **Email:** ada.private@example.com
- **Birthday:** March 3

### Dee Ransom
- **Company:** Kestrel Works
- **Current role:** Head of Growth
- **Relationship:** 2nd-degree LinkedIn connection
- **LinkedIn:** [linkedin.com/in/dee-ransom](https://www.linkedin.com/in/dee-ransom/)
- **Email:** dee.private@example.com
"""


def test_network_live_layout_sync():
    print("\n12. Testing NETWORK.md live layout (## Contacts / ## Contact Details, 7 columns)...")
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        md = Path(tmp) / "NETWORK.md"
        md.write_text(_LIVE_LAYOUT_NETWORK_MD, encoding="utf-8")

        with NetworkDatabase(db_path=":memory:") as db:
            # 3 table rows + 1 detail-only person (Dee Ransom)
            assert db.sync_from_network_markdown(str(md)) == 4
            assert db.count_contacts() == 4

            fern = db.query_contacts(company="Fernwick")
            ada = [c for c in fern if c.name == "Ada Quill"][0]
            assert ada.profile_url.endswith("/in/ada-quill-1a2b"), ada.profile_url
            assert ada.location == "Portland, Oregon"
            assert ada.degree == "2nd" and ada.mutual_sample == ["Bo Marlowe"]

            # Columns are mapped by header: Status is col 4 (not 5), Last touch col 5.
            bo = [c for c in fern if c.name == "Bo Marlowe"][0]
            rec = db.get_outreach_record(bo.urn_id)
            assert rec.last_touch == "September 12, 2026"
            assert rec.status == "messaged", rec.status
            assert "Next action: Follow up | ping again" in rec.connection_note
            assert db.get_outreach_record(ada.urn_id).last_touch == "Never"

            # No orphaned outreach rows; detail-only person is ingested
            orphans = db.conn.execute(
                "SELECT COUNT(*) FROM outreach_records o LEFT JOIN contacts c "
                "ON c.urn_id = o.contact_urn WHERE c.urn_id IS NULL"
            ).fetchone()[0]
            assert orphans == 0
            dee = db.query_contacts(company="Kestrel Works")[0]
            assert db.get_outreach_record(dee.urn_id).status == "discovered"

            # PII from detail blocks never lands in the DB
            dump = " ".join(
                str(v)
                for t in ("contacts", "outreach_records")
                for row in db.conn.execute(f"SELECT * FROM {t}").fetchall()
                for v in row
            )
            for secret in ("5550100199", "example.com", "March 3", "private@"):
                assert secret not in dump, f"leaked {secret!r}"

            # Idempotent re-sync
            assert db.sync_from_network_markdown(str(md)) == 4
            assert db.count_contacts() == 4 and db.count_outreach_records() == 4

    print("   ✓ Passed: header-mapped 7-col table, last_touch stored, no orphans, no PII copied.")


def main():
    print("=" * 70)
    print("STARTING Q4 PIPELINE AUTOMATED REGRESSION TEST SUITE")
    print("=" * 70)

    test_schema_canonicalization()
    test_dom_parser_benchmark()
    test_cdp_voyager_extraction()
    test_entity_matcher_real_roles()
    test_company_only_filtering()
    test_cross_node_deduplication()
    test_duckdb_persistence_and_markdown_sync()
    test_cli_subcommands()
    test_profile_parsing_selectolax()
    test_detailed_profile_db_persistence()
    test_cli_inspect_subcommand()
    test_network_live_layout_sync()

    print("\n" + "=" * 70)
    print("   ALL 12 Q4 PIPELINE REGRESSION TESTS PASSED CLEANLY!   ")
    print("=" * 70)


if __name__ == "__main__":
    main()
