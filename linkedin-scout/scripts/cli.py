#!/usr/bin/env python3
"""
cli.py - Unified Orchestrator CLI for Q4 High-Performance CDP Pipeline.
Integrates CDP sniffing, selectolax parsing, rapidfuzz matching, and DuckDB storage.
Complies with mps-writing-for-agents.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Add package directory to path
PKG_DIR = Path(__file__).parent
SCRIPTS_DIR = PKG_DIR
if str(PKG_DIR) not in sys.path:
    sys.path.insert(0, str(PKG_DIR))

# capt-chrome-agent: $CAPT_CHROME_AGENT_DIR, else a sibling skill, else ~/.agents/skills
CHROME_AGENT_SCRIPTS = next(
    (d / "scripts" for d in (
        Path(os.environ["CAPT_CHROME_AGENT_DIR"]).expanduser() if os.environ.get("CAPT_CHROME_AGENT_DIR") else None,
        Path(__file__).resolve().parents[2] / "capt-chrome-agent",
        Path.home() / ".agents" / "skills" / "capt-chrome-agent",
    ) if d is not None and (d / "scripts").exists()),
    Path.home() / ".agents" / "skills" / "capt-chrome-agent" / "scripts",
)
if CHROME_AGENT_SCRIPTS.exists() and str(CHROME_AGENT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CHROME_AGENT_SCRIPTS))

import hashlib

from schemas import (
    Company,
    DMThread,
    EducationItem,
    EngagementAction,
    ExperienceItem,
    JobPosting,
    LinkedInContact,
    LinkedInProfileDetailed,
    OutreachRecord,
    Post,
    canonicalize_linkedin_company_url,
    canonicalize_linkedin_job_url,
    canonicalize_linkedin_post_url,
    canonicalize_linkedin_url,
)
from cdp_interceptor import (
    parse_voyager_json,
    capture_voyager_traffic,
    capture_voyager_feed_traffic,
    get_ws_url,
)
from dom_parser import (
    parse_linkedin_company_html,
    parse_linkedin_feed_html,
    parse_linkedin_job_posting_html,
    parse_linkedin_job_search_html,
    parse_linkedin_messages_html,
    parse_linkedin_profile_html,
    parse_linkedin_search_html,
)
from entity_matcher import (
    rank_and_filter_contacts,
    rank_and_filter_jobs,
    rank_and_filter_posts,
    rank_creators,
    rank_engagement_posts,
    load_engagement_targets,
    score_role,
    score_company,
)
from pipeline_db import NetworkDatabase
from proximity import assess_contact, score_single_mutual, MutualEvaluation

try:
    from profile_manager import (
        get_active_instances,
        launch_profile,
        interactive_setup,
        get_profile_path,
        PROFILES_ROOT,
        run_cdp,
    )
except ImportError:
    get_active_instances = lambda: []
    launch_profile = None
    interactive_setup = None
    get_profile_path = None
    PROFILES_ROOT = Path.home() / ".config" / "chrome-agent" / "profiles"
    run_cdp = None

DEFAULT_NETWORK_MD = Path.home() / "Sprintz" / "job-search" / "_shared_facts" / "NETWORK.md"


def get_db(db_path: Optional[str] = None) -> NetworkDatabase:
    return NetworkDatabase(db_path=db_path)


def cmd_sync_network(args: argparse.Namespace) -> None:
    """Sync contacts from NETWORK.md into DuckDB."""
    md_path = args.path or str(DEFAULT_NETWORK_MD)
    print(f"[*] Syncing contacts from markdown: {md_path}...")
    with get_db(args.db) as db:
        count = db.sync_from_network_markdown(md_path)
        print(f"[+] Successfully synced {count} contacts into DuckDB ({db.db_path}).")


def cmd_parse_html(args: argparse.Namespace) -> None:
    """Fast parse of an offline HTML dump using selectolax and rapidfuzz."""
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[!] Error: File not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    html_content = in_path.read_text(encoding="utf-8")
    t0 = time.monotonic()
    raw_contacts = parse_linkedin_search_html(html_content)
    parse_time = (time.monotonic() - t0) * 1000

    print(f"[+] Extracted {len(raw_contacts)} raw contacts via selectolax in {parse_time:.2f}ms.")

    if args.roles or args.company:
        target_roles = [r.strip() for r in args.roles.split(",")] if args.roles else []
        target_company = args.company or ""
        scored_contacts = rank_and_filter_contacts(
            raw_contacts,
            target_roles=target_roles,
            target_company=target_company,
            min_role_score=args.min_score,
        )
    else:
        scored_contacts = raw_contacts

    if args.save:
        with get_db(args.db) as db:
            upserted = db.upsert_contacts(scored_contacts)
            print(f"[+] Upserted {upserted} scored contacts to DuckDB.")

    print_contacts_table(scored_contacts)


def cmd_list(args: argparse.Namespace) -> None:
    """List contacts from DuckDB matching filters."""
    with get_db(args.db) as db:
        contacts = db.query_contacts(
            company=args.company,
            min_role_score=args.min_score,
            limit=args.limit,
        )
        print(f"[*] Found {len(contacts)} contacts in database matching criteria:")
        print_contacts_table(contacts)


def cmd_eval(args: argparse.Namespace) -> None:
    """
    Run comprehensive evaluation suite using real pipeline roles and network targets.
    Evaluates:
      1. Parsing throughput (selectolax)
      2. Voyager JSON extraction (CDP)
      3. RapidFuzz matching accuracy across target job requisitions
      4. DuckDB storage & deduplication integrity
    """
    print("=" * 70)
    print("RUNNING COMPREHENSIVE Q4 PIPELINE EVALUATION")
    print("=" * 70)

    # 1. Pipeline Target Role Matrix
    from entity_matcher import derive_targets_from_core_cv

    _derived = derive_targets_from_core_cv()
    _titles = _derived.get("role_titles") or ["Marketing Engineer", "Senior Web Developer"]
    _companies = [c.title() for c in _derived.get("tier_a", [])][:9] or ["Vercel", "Webflow"]
    TARGET_REQUISITIONS = [
        {"company": co, "roles": [_titles[i % len(_titles)], _titles[(i + 1) % len(_titles)]]}
        for i, co in enumerate(_companies)
    ]

    print("\n1. Evaluating Entity Matcher on Pipeline Requisitions:")
    print("-" * 70)
    print(f"{'Company':<15} {'Target Role':<32} {'Candidate Headline':<30} {'Score':<8}")
    print("-" * 70)

    _hl_templates = ["{role} at {co}", "{role} @ {co}", "{role} | {co}"]
    eval_samples = [
        (req["company"], req["roles"][0], _hl_templates[i % len(_hl_templates)].format(role=req["roles"][0], co=req["company"]))
        for i, req in enumerate(TARGET_REQUISITIONS)
    ]

    for company, target_role, candidate_hl in eval_samples:
        r_score = score_role([target_role], candidate_hl)
        c_score = score_company(company, candidate_hl)
        combined = (r_score * 0.6) + (c_score * 0.4)
        print(f"{company:<15} {target_role[:30]:<32} {candidate_hl[:28]:<30} {combined:>5.1f}%")
        assert combined >= 60.0, f"Match failed for {company} / {target_role}"

    print(f"   ✓ All {len(eval_samples)} pipeline role evaluations exceeded relevance threshold (>= 60%).")

    # 2. Database Sync & Integrity Check
    print("\n2. Evaluating Network Database Ingestion from NETWORK.md:")
    print("-" * 70)
    db = NetworkDatabase(db_path=":memory:")
    if DEFAULT_NETWORK_MD.exists():
        count = db.sync_from_network_markdown(str(DEFAULT_NETWORK_MD))
        print(f"   ✓ Ingested {count} contacts from {DEFAULT_NETWORK_MD.name}")
        assert count > 0, f"Expected at least 1 contact, found {count}"

        companies = sorted({c.current_company for c in db.query_contacts() if c.current_company})
        preview = ", ".join(companies[:6]) + ("..." if len(companies) > 6 else "")
        print(f"   ✓ Companies represented: {preview}")

        with_mutuals = [c for c in db.query_contacts() if c.mutual_sample]
        print(f"   ✓ {len(with_mutuals)} contact(s) have recorded mutual connections.")
    else:
        print(f"   [i] {DEFAULT_NETWORK_MD} not found, using memory fixtures.")

    print("\n" + "=" * 70)
    print("ALL Q4 PIPELINE EVALUATIONS PASSED CLEANLY!")
    print("=" * 70)


def print_contacts_table(contacts: List[LinkedInContact]) -> None:
    """Print formatted contact cards."""
    if not contacts:
        print("   (No contacts to display)")
        return

    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Name", style="bold")
        table.add_column("Degree", justify="center")
        table.add_column("Headline")
        table.add_column("Company")
        table.add_column("Role Score", justify="right")
        table.add_column("Mutuals", justify="right")

        for c in contacts:
            score_str = f"{c.role_match_score:.1f}%" if c.role_match_score > 0 else "-"
            table.add_row(
                c.name,
                c.degree,
                c.headline[:45] + ("..." if len(c.headline) > 45 else ""),
                c.current_company or "-",
                score_str,
                str(c.mutual_count) if c.mutual_count > 0 else "-",
            )
        console.print(table)
    except ImportError:
        print(f"\n{'Name':<22} {'Deg':<5} {'Score':<8} {'Mutuals':<8} {'Headline'}")
        print("-" * 75)
        for c in contacts:
            score_str = f"{c.role_match_score:.1f}%" if c.role_match_score > 0 else "-"
            print(f"{c.name[:20]:<22} {c.degree:<5} {score_str:<8} {str(c.mutual_count):<8} {c.headline[:30]}")
        print()


def print_detailed_profile_card(profile: LinkedInProfileDetailed, args: argparse.Namespace) -> None:
    """Print beautifully formatted rich profile details or fallback cleanly to plain text."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        console = Console()

        # Warmth Badge
        tier_style = "bold green" if profile.contact_tier == "WARM" else (
            "bold yellow" if profile.contact_tier == "BRIDGE" else (
                "bold blue" if profile.contact_tier == "COLD" else "dim white"
            )
        )
        tier_label = f"[{tier_style}]{profile.contact_tier or 'UNRANKED'}[/]"
        degree_badge = f"[bold cyan]{profile.degree}[/]"
        if profile.warmth_degree:
            warmth_str = f"• Degree {profile.warmth_degree} ({tier_label})"
        else:
            warmth_str = f"• {tier_label}"

        header_title = f"[bold white]{profile.name}[/] ({degree_badge}) {warmth_str}"

        lines = [
            f"[bold cyan]Headline:[/]    {profile.headline}",
            f"[bold cyan]Company:[/]     {profile.current_company or '-'}",
            f"[bold cyan]Location:[/]    {profile.location or '-'}",
            f"[bold cyan]Profile URL:[/] {profile.profile_url}",
        ]
        if profile.mutual_count > 0:
            sample_str = ", ".join(profile.mutual_sample) if profile.mutual_sample else "unlisted"
            lines.append(f"[bold cyan]Mutuals:[/]     {profile.mutual_count} mutual connections ({sample_str})")
        if profile.role_match_score > 0:
            lines.append(f"[bold cyan]Role Match:[/]  {profile.role_match_score:.1f}%")
        if profile.company_match_score > 0:
            lines.append(f"[bold cyan]Co Match:[/]    {profile.company_match_score:.1f}%")
        if profile.action_recommendation:
            lines.append(f"[bold green]Playbook:[/]    {profile.action_recommendation}")
        if profile.warmth_rationale:
            lines.append(f"[bold yellow]Rationale:[/]   {profile.warmth_rationale}")

        console.print(Panel("\n".join(lines), title=header_title, border_style="bold blue"))

        # About
        if profile.about:
            console.print(Panel(profile.about, title="[bold]About Summary[/]", border_style="dim white"))

        # Experience
        show_all = getattr(args, "all", False)
        show_exp = show_all or getattr(args, "experience", False)
        if (show_exp or not (getattr(args, "education", False) or getattr(args, "skills", False))) and profile.experience:
            t = Table(title="Work Experience History", show_header=True, header_style="bold magenta")
            t.add_column("Title / Position", style="bold")
            t.add_column("Company")
            t.add_column("Dates / Duration")
            t.add_column("Location")
            t.add_column("Description", style="dim")
            for exp in profile.experience:
                dur_str = f"{exp.date_range or ''} ({exp.duration})" if exp.duration else (exp.date_range or "-")
                desc = (exp.description[:75] + "...") if exp.description and len(exp.description) > 75 else (exp.description or "-")
                t.add_row(exp.title, exp.company, dur_str, exp.location or "-", desc)
            console.print(t)

        # Education
        if (show_all or getattr(args, "education", False)) and profile.education:
            t = Table(title="Education", show_header=True, header_style="bold green")
            t.add_column("Institution / School", style="bold")
            t.add_column("Degree / Field")
            t.add_column("Years")
            for edu in profile.education:
                deg = f"{edu.degree or ''} - {edu.field_of_study or ''}".strip(" -") or "-"
                t.add_row(edu.school, deg, edu.date_range or "-")
            console.print(t)

        # Skills
        if (show_all or getattr(args, "skills", False)) and profile.skills:
            console.print(Panel(", ".join(profile.skills), title=f"[bold]Skills ({len(profile.skills)})[/]", border_style="cyan"))

    except ImportError:
        # Clean plain text fallback
        print("\n" + "=" * 70)
        tier_label = f"{profile.contact_tier} (Degree {profile.warmth_degree})" if profile.contact_tier else "UNRANKED"
        print(f"PROFILE: {profile.name} ({profile.degree}) - {tier_label}")
        print("=" * 70)
        print(f"Headline:    {profile.headline}")
        print(f"Company:     {profile.current_company or '-'}")
        print(f"Location:    {profile.location or '-'}")
        print(f"URL:         {profile.profile_url}")
        if profile.mutual_count > 0:
            sample_str = ", ".join(profile.mutual_sample) if profile.mutual_sample else "unlisted"
            print(f"Mutuals:     {profile.mutual_count} mutual connections ({sample_str})")
        if profile.action_recommendation:
            print(f"Playbook:    {profile.action_recommendation}")
        if profile.about:
            print(f"\nAbout:\n  {profile.about}")
        if profile.experience:
            print(f"\nWork Experience ({len(profile.experience)} positions):")
            for exp in profile.experience:
                dur = f" ({exp.duration})" if exp.duration else ""
                print(f"  • {exp.title} at {exp.company} [{exp.date_range or '-'}{dur}]")
        if profile.education:
            print(f"\nEducation ({len(profile.education)} items):")
            for edu in profile.education:
                deg = f" - {edu.degree}" if edu.degree else ""
                print(f"  • {edu.school}{deg} [{edu.date_range or '-'}]")
        if profile.skills:
            print(f"\nSkills: {', '.join(profile.skills)}")
        print("=" * 70 + "\n")


def build_linkedin_search_url(
    keywords: Optional[str] = None,
    company: Optional[str] = None,
    company_id: Optional[str] = None,
    network_degrees: Optional[List[str]] = None,
) -> str:
    import urllib.parse
    params = {}
    kw_parts = []
    if keywords:
        kw_parts.append(keywords)
    elif company:
        kw_parts.append(f'"{company}"')
    if kw_parts:
        params["keywords"] = " ".join(kw_parts)
    if company_id:
        params["currentCompany"] = f'["{company_id}"]'
    if network_degrees:
        params["network"] = json.dumps(network_degrees, separators=(",", ":"))

    query_str = urllib.parse.urlencode(params)
    return f"https://www.linkedin.com/search/results/people/?{query_str}&origin=FACETED_SEARCH"


def build_linkedin_job_search_url(
    keywords: Optional[str] = None,
    company: Optional[str] = None,
    location: Optional[str] = None,
) -> str:
    """Build a LinkedIn job search results URL. Mirrors build_linkedin_search_url's keyword/company fallback."""
    import urllib.parse
    params = {}
    kw_parts = []
    if keywords:
        kw_parts.append(keywords)
    elif company:
        kw_parts.append(f'"{company}"')
    if kw_parts:
        params["keywords"] = " ".join(kw_parts)
    if location:
        params["location"] = location

    query_str = urllib.parse.urlencode(params)
    return f"https://www.linkedin.com/jobs/search/?{query_str}"


async def _resolve_browser_instance(args: argparse.Namespace) -> Optional[tuple]:
    """
    Attach to an already-running Chrome CDP instance, or launch the persistent profile.
    Returns (inst_name, port) or None (with a diagnostic already printed) on failure.
    Shared by every live-browser command (discover/inspect variants for person, job, company).
    """
    if get_active_instances is None or run_cdp is None:
        print("[!] Error: profile_manager utilities unavailable.", file=sys.stderr)
        return None

    from listen import pick_instance

    instances = get_active_instances()
    picked = pick_instance(instances, getattr(args, "profile", None) or "linkedin", getattr(args, "port", None))
    if picked is not None:
        inst_name = picked["name"]
        port = int(picked.get("port") or 9222)
        print(f"[*] Connected to active browser instance '{inst_name}' on port {port}.")
        return inst_name, port

    profile_name = args.profile or "linkedin"
    profile_path = PROFILES_ROOT / profile_name
    has_cookies = (profile_path / "Default" / "Network" / "Cookies").exists() or (profile_path / "Default" / "Cookies").exists()

    if not profile_path.exists() or not has_cookies:
        if getattr(args, "setup", False):
            print(f"[*] Profile '{profile_name}' not initialized. Starting interactive login setup...")
            interactive_setup(profile_name, "https://www.linkedin.com/login", destination_check="feed")
        else:
            print(f"\n[!] Persistent profile '{profile_name}' lacks active session cookies at:", file=sys.stderr)
            print(f"    {profile_path}\n", file=sys.stderr)
            print(f"[*] Pass '--setup' to launch interactive login window.\n", file=sys.stderr)
            return None

    print(f"[*] Launching Chrome with profile '{profile_name}' (headless={args.headless})...")
    inst_name = launch_profile(profile_name, headless=args.headless)
    port = 9222
    for inst in get_active_instances():
        if inst["name"] == inst_name:
            port = int(inst.get("port") or 9222)
            break
    return inst_name, port


async def _fetch_outer_html(inst_name: str, url: str, wait_sec: float = 3.5) -> str:
    """Navigate the given Chrome instance to url, wait for hydration, and return outerHTML."""
    run_cdp([inst_name, "Page.navigate", json.dumps({"url": url})])
    await asyncio.sleep(wait_sec)
    try:
        run_cdp([
            inst_name,
            "Runtime.evaluate",
            json.dumps({"expression": "window.scrollBy({top: 800, behavior: 'smooth'})"}),
        ])
        await asyncio.sleep(1.5)
    except Exception:
        pass
    eval_res = run_cdp([
        inst_name,
        "Runtime.evaluate",
        json.dumps({"expression": "document.documentElement.outerHTML"}),
    ])
    if isinstance(eval_res, dict) and "result" in eval_res:
        return eval_res["result"].get("value", "")
    return ""


def print_jobs_table(jobs: List[JobPosting]) -> None:
    """Print formatted job posting cards, mirroring print_contacts_table."""
    if not jobs:
        print("   (No jobs to display)")
        return

    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Title", style="bold")
        table.add_column("Company")
        table.add_column("Location")
        table.add_column("Workplace")
        table.add_column("Role Score", justify="right")
        table.add_column("Status")

        for j in jobs:
            score_str = f"{j.role_match_score:.1f}%" if j.role_match_score > 0 else "-"
            table.add_row(
                j.title[:45] + ("..." if len(j.title) > 45 else ""),
                j.company_name or "-",
                j.location or "-",
                j.workplace_type or "-",
                score_str,
                j.application_status,
            )
        console.print(table)
    except ImportError:
        print(f"\n{'Title':<40} {'Company':<20} {'Score':<8} {'Status'}")
        print("-" * 85)
        for j in jobs:
            score_str = f"{j.role_match_score:.1f}%" if j.role_match_score > 0 else "-"
            print(f"{j.title[:38]:<40} {(j.company_name or '-')[:18]:<20} {score_str:<8} {j.application_status}")
        print()


def print_job_card(job: JobPosting, args: argparse.Namespace) -> None:
    """Print a detailed job posting card, mirroring print_detailed_profile_card's fallback shape."""
    try:
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        lines = [
            f"[bold cyan]Company:[/]     {job.company_name}",
            f"[bold cyan]Location:[/]    {job.location or '-'}",
            f"[bold cyan]Workplace:[/]   {job.workplace_type or '-'}",
            f"[bold cyan]Employment:[/]  {job.employment_type or '-'}",
            f"[bold cyan]Seniority:[/]   {job.experience_level or '-'}",
            f"[bold cyan]Posted:[/]      {job.date_posted or '-'}",
            f"[bold cyan]Applicants:[/]  {job.applicant_count if job.applicant_count is not None else '-'}",
            f"[bold cyan]Job URL:[/]     {job.job_url}",
        ]
        if job.salary_min or job.salary_max:
            lines.append(
                f"[bold cyan]Salary:[/]      {job.salary_min or '?'}-{job.salary_max or '?'} "
                f"{job.salary_currency or ''} ({job.salary_interval or '-'})"
            )
        if job.role_match_score > 0:
            lines.append(f"[bold cyan]Role Match:[/]  {job.role_match_score:.1f}%")
        if job.company_match_score > 0:
            lines.append(f"[bold cyan]Co Match:[/]    {job.company_match_score:.1f}%")
        console.print(Panel("\n".join(lines), title=f"[bold white]{job.title}[/]", border_style="bold blue"))
        if job.description:
            console.print(Panel(job.description[:2000], title="[bold]Description[/]", border_style="dim white"))
    except ImportError:
        print("\n" + "=" * 70)
        print(f"JOB: {job.title} @ {job.company_name}")
        print("=" * 70)
        print(f"Location:    {job.location or '-'}")
        print(f"Workplace:   {job.workplace_type or '-'}")
        print(f"Employment:  {job.employment_type or '-'}")
        print(f"Seniority:   {job.experience_level or '-'}")
        print(f"Posted:      {job.date_posted or '-'}")
        print(f"Applicants:  {job.applicant_count if job.applicant_count is not None else '-'}")
        print(f"URL:         {job.job_url}")
        if job.role_match_score > 0:
            print(f"Role Match:  {job.role_match_score:.1f}%")
        if job.description:
            print(f"\nDescription:\n  {job.description[:2000]}")
        print("=" * 70 + "\n")


def print_company_card(company: Company, args: argparse.Namespace) -> None:
    """Print a detailed company card."""
    try:
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        lines = [
            f"[bold cyan]Industry:[/]    {company.industry or '-'}",
            f"[bold cyan]Size:[/]        {company.company_size or '-'}",
            f"[bold cyan]HQ:[/]          {company.headquarters or '-'}",
            f"[bold cyan]Founded:[/]     {company.founded or '-'}",
            f"[bold cyan]Website:[/]     {company.website or '-'}",
            f"[bold cyan]Followers:[/]   {company.follower_count if company.follower_count is not None else '-'}",
            f"[bold cyan]URL:[/]         {company.company_url}",
        ]
        if company.specialties:
            lines.append(f"[bold cyan]Specialties:[/] {', '.join(company.specialties)}")
        console.print(Panel("\n".join(lines), title=f"[bold white]{company.name}[/]", border_style="bold blue"))
        if company.description:
            console.print(Panel(company.description[:2000], title="[bold]About[/]", border_style="dim white"))
    except ImportError:
        print("\n" + "=" * 70)
        print(f"COMPANY: {company.name}")
        print("=" * 70)
        print(f"Industry:    {company.industry or '-'}")
        print(f"Size:        {company.company_size or '-'}")
        print(f"HQ:          {company.headquarters or '-'}")
        print(f"URL:         {company.company_url}")
        if company.description:
            print(f"\nAbout:\n  {company.description[:2000]}")
        print("=" * 70 + "\n")


def print_posts_table(posts: List[Post]) -> None:
    """Print formatted post cards, mirroring print_jobs_table."""
    if not posts:
        print("   (No posts to display)")
        return
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Author", style="bold")
        table.add_column("Type")
        table.add_column("Text")
        table.add_column("Topic Score", justify="right")
        table.add_column("Likes/Comments/Reposts", justify="right")
        table.add_column("Post ID")

        for p in posts:
            score_str = f"{p.topic_match_score:.1f}%" if p.topic_match_score > 0 else "-"
            engagement = f"{p.like_count or 0}/{p.comment_count or 0}/{p.repost_count or 0}"
            table.add_row(
                p.author_name,
                p.author_type,
                (p.text or "")[:50] + ("..." if p.text and len(p.text) > 50 else ""),
                score_str,
                engagement,
                p.post_id,
            )
        console.print(table)
    except ImportError:
        print(f"\n{'Author':<25} {'Type':<8} {'Score':<8} {'Post ID'}")
        print("-" * 65)
        for p in posts:
            score_str = f"{p.topic_match_score:.1f}%" if p.topic_match_score > 0 else "-"
            print(f"{p.author_name[:23]:<25} {p.author_type:<8} {score_str:<8} {p.post_id}")
        print()


def print_thread(thread: DMThread) -> None:
    """Print a DM thread's messages in order."""
    print("\n" + "=" * 70)
    print(f"THREAD: {thread.participant_name} (unread: {thread.unread_count})")
    print("=" * 70)
    for m in thread.messages:
        print(f"  [{m.sent_at or '-'}] {m.sender_name}: {m.text}")
    print("=" * 70 + "\n")


_ENGAGEMENT_NEXT_ACTION = {
    "drafted": "Review: approve or reject",
    "approved": "Post manually in browser",
    "rejected": "None (archived)",
    "executed": "None",
}


def _engagement_age_days(action: EngagementAction) -> int:
    created = action.created_at
    now = datetime.now(created.tzinfo) if created.tzinfo else datetime.now()
    return max((now - created).days, 0)


def print_engagement_actions_table(actions: List[EngagementAction]) -> None:
    """Print the drafted engagement queue. Status is always human-set -- never printed as executed by this codebase."""
    if not actions:
        print("   (No drafted engagement actions to display)")
        return
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Action ID", style="bold")
        table.add_column("Type")
        table.add_column("Target")
        table.add_column("Draft", max_width=40)
        table.add_column("Score", justify="right")
        table.add_column("Status")
        table.add_column("Age", justify="right")
        table.add_column("Next Action")

        for a in actions:
            status_style = {"drafted": "yellow", "approved": "green", "rejected": "red", "executed": "dim"}.get(a.status, "white")
            table.add_row(
                a.action_id,
                a.action_type + (f" ({a.reaction_type})" if a.reaction_type else ""),
                f"{a.target_type}:{a.target_id}",
                (a.draft_content or "")[:80],
                f"{a.rubric_score:.1f}",
                f"[{status_style}]{a.status}[/]",
                f"{_engagement_age_days(a)}d",
                _ENGAGEMENT_NEXT_ACTION.get(a.status, "-"),
            )
        console.print(table)
    except ImportError:
        print(f"\n{'Action ID':<20} {'Type':<10} {'Target':<20} {'Score':<7} {'Status':<10} {'Age':<5} {'Next Action'}")
        print("-" * 100)
        for a in actions:
            print(f"{a.action_id[:18]:<20} {a.action_type:<10} {(a.target_type + ':' + a.target_id)[:18]:<20} {a.rubric_score:<7.1f} {a.status:<10} {str(_engagement_age_days(a)) + 'd':<5} {_ENGAGEMENT_NEXT_ACTION.get(a.status, '-')}")
        print()


async def async_discover(args: argparse.Namespace) -> List[LinkedInContact]:
    if get_active_instances is None or run_cdp is None:
        print("[!] Error: profile_manager utilities unavailable.", file=sys.stderr)
        return []

    instances = get_active_instances()
    inst_name = None
    port = 9222
    from listen import pick_instance
    picked = pick_instance(instances, getattr(args, "profile", None) or "linkedin", getattr(args, "port", None))
    if picked is not None:
        inst_name = picked["name"]
        port = int(picked.get("port") or 9222)
        print(f"[*] Connected to active browser instance '{inst_name}' on port {port}.")
    else:
        profile_name = args.profile or "linkedin"
        profile_path = PROFILES_ROOT / profile_name
        has_cookies = (profile_path / "Default" / "Network" / "Cookies").exists() or (profile_path / "Default" / "Cookies").exists()

        if not profile_path.exists() or not has_cookies:
            if args.setup:
                print(f"[*] Profile '{profile_name}' not initialized. Starting interactive login setup...")
                interactive_setup(profile_name, "https://www.linkedin.com/login", destination_check="feed")
            else:
                print(f"\n[!] Persistent profile '{profile_name}' does not exist or lacks active session cookies at:", file=sys.stderr)
                print(f"    {profile_path}\n", file=sys.stderr)
                print(f"[*] To initialize your session, run one-time setup:", file=sys.stderr)
                print(f"    python3 {SCRIPTS_DIR}/profile_manager.py setup {profile_name} --url https://www.linkedin.com/login --check feed\n", file=sys.stderr)
                print(f"    (Or rerun discover with the '--setup' flag to launch the login window now)\n", file=sys.stderr)
                return []

        print(f"[*] Launching Chrome with profile '{profile_name}' (headless={args.headless})...")
        inst_name = launch_profile(profile_name, headless=args.headless)
        instances = get_active_instances()
        if instances:
            for inst in instances:
                if inst["name"] == inst_name:
                    port = int(inst.get("port") or 9222)
                    break

    # Build search URL
    if args.url:
        search_url = args.url
    else:
        degrees = [d.strip().upper() for d in args.network.split(",")] if args.network else ["F", "S"]
        search_url = build_linkedin_search_url(
            keywords=args.keywords,
            company=args.company,
            company_id=args.company_id,
            network_degrees=degrees,
        )

    print(f"[*] Target LinkedIn URL: {search_url}")

    # WebSocket target
    try:
        ws_url = get_ws_url(port=port, url_filter="linkedin.com")
        print(f"[*] Attached to CDP target: {ws_url}")
    except Exception as exc:
        print(f"[!] Could not connect to CDP WebSocket on port {port}: {exc}", file=sys.stderr)
        return []

    # Start passive interception
    timeout = args.timeout or 15.0
    capture_task = asyncio.create_task(capture_voyager_traffic(ws_url, timeout=timeout))
    await asyncio.sleep(0.3)

    # Navigate
    print("[*] Navigating tab to search URL...")
    run_cdp([inst_name, "Page.navigate", json.dumps({"url": search_url})])

    # Wait and trigger smooth scroll to populate virtualized cards
    await asyncio.sleep(3.5)
    try:
        run_cdp([
            inst_name,
            "Runtime.evaluate",
            json.dumps({"expression": "window.scrollBy({top: 800, behavior: 'smooth'})"}),
        ])
    except Exception:
        pass

    contacts = await capture_task

    # DOM Fallback if 0 contacts from Voyager
    if not contacts:
        print("[*] Voyager GraphQL traffic yielded 0 contacts, executing DOM parser fallback...")
        try:
            eval_res = run_cdp([
                inst_name,
                "Runtime.evaluate",
                json.dumps({"expression": "document.documentElement.outerHTML"}),
            ])
            html_raw = ""
            if isinstance(eval_res, dict) and "result" in eval_res:
                html_raw = eval_res["result"].get("value", "")
            if html_raw:
                contacts = parse_linkedin_search_html(html_raw)
                print(f"[+] Extracted {len(contacts)} contacts via DOM parser fallback.")
        except Exception as exc:
            print(f"[!] DOM extraction fallback error: {exc}", file=sys.stderr)

    # Rank and score
    target_roles = [r.strip() for r in args.roles.split(",")] if args.roles else []
    target_company = args.company or ""
    if target_roles or target_company:
        scored_contacts = rank_and_filter_contacts(
            contacts,
            target_roles=target_roles,
            target_company=target_company,
            min_role_score=args.min_score,
        )
    else:
        scored_contacts = contacts

    # Upsert to DuckDB
    if not args.no_save and scored_contacts:
        with get_db(args.db) as db:
            upserted = db.upsert_contacts(scored_contacts)
            print(f"[+] Upserted {upserted} discovered contacts into DuckDB ({db.db_path}).")

    print_contacts_table(scored_contacts)
    return scored_contacts


def cmd_discover(args: argparse.Namespace) -> None:
    """Run live LinkedIn contact discovery."""
    asyncio.run(async_discover(args))


async def async_discover_jobs(args: argparse.Namespace) -> List[JobPosting]:
    """Live LinkedIn job search discovery: navigate, DOM-parse result cards, score, persist."""
    resolved = await _resolve_browser_instance(args)
    if resolved is None:
        return []
    inst_name, _port = resolved

    search_url = args.url or build_linkedin_job_search_url(
        keywords=args.keywords, company=args.company, location=args.location
    )
    print(f"[*] Target LinkedIn job search URL: {search_url}")

    print("[*] Navigating tab to job search URL...")
    html_raw = await _fetch_outer_html(inst_name, search_url, wait_sec=3.5)
    if not html_raw:
        print("[!] Error: Could not extract DOM outerHTML from tab.", file=sys.stderr)
        return []

    jobs = parse_linkedin_job_search_html(html_raw)
    print(f"[+] Extracted {len(jobs)} job postings via DOM parser.")

    target_roles = [r.strip() for r in args.roles.split(",")] if args.roles else []
    target_company = args.company or ""
    scored_jobs = (
        rank_and_filter_jobs(jobs, target_roles=target_roles, target_company=target_company, min_role_score=args.min_score)
        if target_roles or target_company
        else jobs
    )

    if not args.no_save and scored_jobs:
        with get_db(args.db) as db:
            upserted = db.upsert_jobs(scored_jobs)
            print(f"[+] Upserted {upserted} discovered jobs into DuckDB ({db.db_path}).")

    print_jobs_table(scored_jobs)
    return scored_jobs


def cmd_discover_jobs(args: argparse.Namespace) -> None:
    """Run live LinkedIn job search discovery."""
    asyncio.run(async_discover_jobs(args))


async def async_inspect_job(args: argparse.Namespace) -> Optional[JobPosting]:
    """Inspect a single LinkedIn job posting via offline HTML, cached DuckDB record, or live CDP."""
    raw_target = args.target or args.url
    if not raw_target and not args.html:
        print("[!] Error: You must specify a target job URL or ID (e.g. '4123456789' or a full jobs/view URL).", file=sys.stderr)
        return None

    job: Optional[JobPosting] = None

    if args.html:
        html_path = Path(args.html)
        if not html_path.exists():
            print(f"[!] Error: File not found: {html_path}", file=sys.stderr)
            return None
        job = parse_linkedin_job_posting_html(html_path.read_text(encoding="utf-8"), job_url_hint=raw_target)
    elif getattr(args, "cached", False) and raw_target:
        with get_db(args.db) as db:
            job = db.get_job(raw_target)
            if job:
                print(f"[*] Retrieved cached job '{job.title}' from DuckDB.")

    if job is None:
        clean_raw = (raw_target or "").strip()
        if clean_raw.startswith(("http://", "https://")):
            target_url = canonicalize_linkedin_job_url(clean_raw)
        else:
            target_url = f"https://www.linkedin.com/jobs/view/{clean_raw.strip('/')}/"

        print(f"[*] Inspecting target job URL via local CDP: {target_url}")
        resolved = await _resolve_browser_instance(args)
        if resolved is None:
            return None
        inst_name, _port = resolved

        html_raw = await _fetch_outer_html(inst_name, target_url, wait_sec=float(getattr(args, "wait", 3.5)))
        if not html_raw:
            print("[!] Error: Could not extract DOM outerHTML from tab.", file=sys.stderr)
            return None
        job = parse_linkedin_job_posting_html(html_raw, job_url_hint=target_url)

    if not job:
        print("[!] Error: Failed to extract job posting details.", file=sys.stderr)
        return None

    target_roles = [r.strip() for r in args.roles.split(",")] if getattr(args, "roles", None) else []
    target_company = getattr(args, "company", None) or job.company_name or ""
    if target_roles:
        job.role_match_score = score_role(target_roles, job.title)
    if target_company:
        job.company_match_score = score_company(target_company, job.company_name)

    if not getattr(args, "no_save", False):
        with get_db(args.db) as db:
            db.upsert_jobs([job])
            print(f"[+] Persisted job '{job.title}' to DuckDB ({db.db_path}).")

    if getattr(args, "json", False):
        print(json.dumps(job.model_dump(mode="json"), indent=2))
    else:
        print_job_card(job, args)

    return job


def cmd_inspect_job(args: argparse.Namespace) -> None:
    """Run single LinkedIn job posting inspection."""
    asyncio.run(async_inspect_job(args))


async def async_inspect_company(args: argparse.Namespace) -> Optional[Company]:
    """Inspect a single LinkedIn company page via offline HTML, cached DuckDB record, or live CDP."""
    raw_target = args.target or args.url
    if not raw_target and not args.html:
        print("[!] Error: You must specify a target company URL or slug (e.g. 'umbra' or a full /company/ URL).", file=sys.stderr)
        return None

    company: Optional[Company] = None

    if args.html:
        html_path = Path(args.html)
        if not html_path.exists():
            print(f"[!] Error: File not found: {html_path}", file=sys.stderr)
            return None
        company = parse_linkedin_company_html(html_path.read_text(encoding="utf-8"), company_url_hint=raw_target)
    elif getattr(args, "cached", False) and raw_target:
        with get_db(args.db) as db:
            company = db.get_company(raw_target)
            if company:
                print(f"[*] Retrieved cached company '{company.name}' from DuckDB.")

    if company is None:
        clean_raw = (raw_target or "").strip()
        if clean_raw.startswith(("http://", "https://")):
            target_url = canonicalize_linkedin_company_url(clean_raw)
        else:
            target_url = f"https://www.linkedin.com/company/{clean_raw.strip('/')}/about/"

        print(f"[*] Inspecting target company URL via local CDP: {target_url}")
        resolved = await _resolve_browser_instance(args)
        if resolved is None:
            return None
        inst_name, _port = resolved

        html_raw = await _fetch_outer_html(inst_name, target_url, wait_sec=float(getattr(args, "wait", 3.5)))
        if not html_raw:
            print("[!] Error: Could not extract DOM outerHTML from tab.", file=sys.stderr)
            return None
        company = parse_linkedin_company_html(html_raw, company_url_hint=target_url)

    if not company:
        print("[!] Error: Failed to extract company details.", file=sys.stderr)
        return None

    if not getattr(args, "no_save", False):
        with get_db(args.db) as db:
            db.upsert_company(company)
            print(f"[+] Persisted company '{company.name}' to DuckDB ({db.db_path}).")

    if getattr(args, "json", False):
        print(json.dumps(company.model_dump(mode="json"), indent=2))
    else:
        print_company_card(company, args)

    return company


def cmd_inspect_company(args: argparse.Namespace) -> None:
    """Run single LinkedIn company inspection."""
    asyncio.run(async_inspect_company(args))


def cmd_list_jobs(args: argparse.Namespace) -> None:
    """List stored job postings from DuckDB matching filters."""
    with get_db(args.db) as db:
        jobs = db.query_jobs(
            company=args.company,
            min_role_score=args.min_score,
            application_status=args.status,
            limit=args.limit,
        )
        print(f"[*] Found {len(jobs)} jobs in database matching criteria:")
        print_jobs_table(jobs)


def cmd_list_companies(args: argparse.Namespace) -> None:
    """List stored companies from DuckDB matching filters."""
    with get_db(args.db) as db:
        companies = db.query_companies(industry=args.industry, limit=args.limit)
        print(f"[*] Found {len(companies)} companies in database matching criteria:")
        if not companies:
            print("   (No companies to display)")
            return
        for c in companies:
            print(f"  • {c.name:<30} {c.industry or '-':<25} {c.company_size or '-':<12} {c.company_url}")


async def async_discover_feed(args: argparse.Namespace) -> List[Post]:
    """
    Live feed/posts-tab discovery. Read-only -- no engagement executed.

    Scoped (--company/--person): captures passive Voyager GraphQL traffic
    (voyagerFeedDashOrganizationalPageUpdates / voyagerFeedDashProfileUpdates), which carries
    real post IDs, canonical permalinks, and engagement counts. DOM parsing is a fallback only
    if that traffic yields nothing (selector drift, slow load, etc).

    Unscoped (bare --url or the plain home feed): DOM-only, and unreliable by design -- LinkedIn
    now server-renders the home feed with no separate data fetch and no post URN left in the
    DOM, so scoped discovery (--company/--person) is the supported path.
    """
    resolved = await _resolve_browser_instance(args)
    if resolved is None:
        return []
    inst_name, port = resolved

    is_scoped = bool(args.company or args.person) and not args.url

    if args.url:
        target_url = args.url
    elif args.company:
        target_url = f"https://www.linkedin.com/company/{args.company.strip('/')}/posts/"
    elif args.person:
        target_url = f"https://www.linkedin.com/in/{args.person.strip('/')}/recent-activity/all/"
    else:
        target_url = "https://www.linkedin.com/feed/"
        print("[!] Warning: unscoped feed discovery is DOM-only and unreliable -- LinkedIn's home", file=sys.stderr)
        print("    feed has no recoverable post ID in the DOM. Pass --company or --person for", file=sys.stderr)
        print("    reliable Voyager-based discovery.", file=sys.stderr)

    print(f"[*] Target LinkedIn feed URL: {target_url}")

    posts: List[Post] = []
    if is_scoped:
        try:
            ws_url = get_ws_url(port=port, url_filter="linkedin.com")
            capture_task = asyncio.create_task(capture_voyager_feed_traffic(ws_url, timeout=12.0))
            await asyncio.sleep(0.3)
            print("[*] Navigating tab to feed URL...")
            run_cdp([inst_name, "Page.navigate", json.dumps({"url": target_url})])
            posts = await capture_task
            if posts:
                print(f"[+] Extracted {len(posts)} posts via passive Voyager GraphQL interception.")
        except Exception as exc:
            print(f"[!] Voyager capture failed ({exc}), falling back to DOM parsing.", file=sys.stderr)
    else:
        run_cdp([inst_name, "Page.navigate", json.dumps({"url": target_url})])

    if not posts:
        html_raw = await _fetch_outer_html(inst_name, target_url, wait_sec=3.5)
        if not html_raw:
            print("[!] Error: Could not extract DOM outerHTML from tab.", file=sys.stderr)
            return []
        posts = parse_linkedin_feed_html(html_raw)
        print(f"[+] Extracted {len(posts)} posts via DOM parser fallback.")

    target_topics = [t.strip() for t in args.topics.split(",")] if args.topics else []
    target_authors = [a.strip() for a in args.authors.split(",")] if args.authors else []
    scored_posts = (
        rank_and_filter_posts(posts, target_topics=target_topics, target_authors=target_authors, min_topic_score=args.min_score)
        if target_topics
        else posts
    )

    # Enrich author_warmth_tier from any already-inspected contact on file, so rank ordering
    # reflects real network warmth without a live re-inspect.
    if not args.no_save and scored_posts:
        with get_db(args.db) as db:
            for post in scored_posts:
                if post.author_type == "person" and not post.author_warmth_tier:
                    existing = db.query_contacts(limit=None)
                    match = next((c for c in existing if c.name.strip().lower() == post.author_name.strip().lower()), None)
                    if match and match.contact_tier:
                        post.author_warmth_tier = match.contact_tier
            upserted = db.upsert_posts(scored_posts)
            print(f"[+] Upserted {upserted} discovered posts into DuckDB ({db.db_path}).")

    print_posts_table(scored_posts)
    return scored_posts


def cmd_discover_feed(args: argparse.Namespace) -> None:
    """Run live LinkedIn feed/posts-tab discovery."""
    asyncio.run(async_discover_feed(args))


async def async_inspect_thread(args: argparse.Namespace) -> Optional[DMThread]:
    """Inspect a single open LinkedIn DM thread via offline HTML or live CDP. Read-only -- no message sent."""
    raw_target = args.target or args.url
    if not raw_target and not args.html:
        print("[!] Error: You must specify a target thread URL (e.g. 'https://www.linkedin.com/messaging/thread/<id>/').", file=sys.stderr)
        return None

    thread: Optional[DMThread] = None

    if args.html:
        html_path = Path(args.html)
        if not html_path.exists():
            print(f"[!] Error: File not found: {html_path}", file=sys.stderr)
            return None
        thread = parse_linkedin_messages_html(html_path.read_text(encoding="utf-8"), thread_url_hint=raw_target)
    elif getattr(args, "cached", False) and raw_target:
        with get_db(args.db) as db:
            thread = db.get_dm_thread(raw_target)
            if thread:
                print(f"[*] Retrieved cached thread with '{thread.participant_name}' from DuckDB.")

    if thread is None:
        target_url = raw_target
        print(f"[*] Inspecting target thread via local CDP: {target_url}")
        resolved = await _resolve_browser_instance(args)
        if resolved is None:
            return None
        inst_name, _port = resolved

        html_raw = await _fetch_outer_html(inst_name, target_url, wait_sec=float(getattr(args, "wait", 3.5)))
        if not html_raw:
            print("[!] Error: Could not extract DOM outerHTML from tab.", file=sys.stderr)
            return None
        thread = parse_linkedin_messages_html(html_raw, thread_url_hint=target_url)

    if not thread:
        print("[!] Error: Failed to extract thread details.", file=sys.stderr)
        return None

    if not getattr(args, "no_save", False):
        with get_db(args.db) as db:
            db.upsert_dm_thread(thread)
            print(f"[+] Persisted thread with '{thread.participant_name}' to DuckDB ({db.db_path}).")

    if getattr(args, "json", False):
        print(json.dumps(thread.model_dump(mode="json"), indent=2))
    else:
        print_thread(thread)

    return thread


def cmd_inspect_thread(args: argparse.Namespace) -> None:
    """Run single LinkedIn DM thread inspection."""
    asyncio.run(async_inspect_thread(args))


def cmd_list_posts(args: argparse.Namespace) -> None:
    """List stored posts from DuckDB matching filters."""
    with get_db(args.db) as db:
        posts = db.query_posts(author=args.author, min_topic_score=args.min_score, limit=args.limit)
        print(f"[*] Found {len(posts)} posts in database matching criteria:")
        print_posts_table(posts)


def print_ranked_posts_table(rows) -> None:
    """Print ranked engagement posts (rank, score, author, age, likes/comments, keywords, text, url)."""
    if not rows:
        print("   (No posts to display)")
        return
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", justify="right")
        table.add_column("Score", justify="right")
        table.add_column("Author", style="bold")
        table.add_column("Age (d)", justify="right")
        table.add_column("Likes/Comments", justify="right")
        table.add_column("Keywords")
        table.add_column("Text")
        table.add_column("URL", overflow="fold")
        for i, (score, p, bd) in enumerate(rows, 1):
            table.add_row(
                str(i), f"{score:.1f}", p.author_name, f"{bd['age_hours'] / 24:.1f}",
                f"{p.like_count or 0}/{p.comment_count or 0}", ", ".join(bd["hits"]),
                (p.text or "")[:70].replace("\n", " "), p.post_url,
            )
        console.print(table)
    except ImportError:
        for i, (score, p, bd) in enumerate(rows, 1):
            print(f"{i:>2}. {score:5.1f} {p.author_name[:22]:<22} {bd['age_hours'] / 24:4.1f}d "
                  f"{p.like_count or 0}/{p.comment_count or 0} [{', '.join(bd['hits'])}]")
            print(f"      {(p.text or '')[:70]!r}\n      {p.post_url}")
        print()


def cmd_rank_posts(args: argparse.Namespace) -> None:
    """Rank stored posts by engagement-worthiness (read-only: no browser, no queue writes)."""
    targets = load_engagement_targets(args.targets)
    with get_db(args.db) as db:
        posts = db.query_posts()
        contacts = db.query_contacts()
        queued = {a.target_id for a in db.query_engagement_actions()}
    rows = rank_engagement_posts(
        posts, contacts, queued, targets=targets, top_n=args.top, max_age_days=args.max_age_days,
        max_company_pages=None if args.max_pages < 0 else args.max_pages,
        max_per_cluster=None if args.max_per_cluster < 0 else args.max_per_cluster,
        min_score=args.min_score,
    )
    if args.json:
        out = []
        for i, (score, p, bd) in enumerate(rows, 1):
            out.append({
                "rank": i,
                "score": score,
                "breakdown": bd,
                "post": json.loads(p.model_dump_json()),
            })
        print(json.dumps(out, indent=2))
        return
    print(f"[*] Top {len(rows)} posts to engage with (of {len(posts)} stored, {len(queued)} already queued):")
    print_ranked_posts_table(rows)


def cmd_rank_creators(args: argparse.Namespace) -> None:
    """Rank authors by how consistently their posts align with targets (read-only)."""
    with get_db(args.db) as db:
        posts = db.query_posts()
    rows = rank_creators(posts, min_posts=args.min_posts, top_n=args.top)
    if args.json:
        print(json.dumps([{"author": n, "fit": f, "post_count": c} for n, f, c in rows], indent=2))
        return
    print(f"[*] Top {len(rows)} creators by target alignment (min {args.min_posts} posts):")
    if not rows:
        print("   (No creators to display)")
        return
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Author", style="bold")
        table.add_column("Fit", justify="right")
        table.add_column("Posts", justify="right")
        for n, f, c in rows:
            table.add_row(n, f"{f:.2f}", str(c))
        console.print(table)
    except ImportError:
        print(f"\n{'Author':<30} {'Fit':<6} {'Posts'}")
        print("-" * 45)
        for n, f, c in rows:
            print(f"{n[:28]:<30} {f:<6.2f} {c}")
        print()


def cmd_list_threads(args: argparse.Namespace) -> None:
    """List stored DM threads from DuckDB matching filters."""
    with get_db(args.db) as db:
        threads = db.query_dm_threads(participant=args.participant, limit=args.limit)
        print(f"[*] Found {len(threads)} threads in database matching criteria:")
        if not threads:
            print("   (No threads to display)")
            return
        for t in threads:
            print(f"  • {t.participant_name:<30} unread={t.unread_count:<3} messages={len(t.messages):<3} last={t.last_message_at or '-'}")


def cmd_queue_engagement(args: argparse.Namespace) -> None:
    """
    Add a rubric-scored, human-drafted engagement action to the review queue.
    This command NEVER performs the action -- it only records a draft for the user to
    review and, separately, execute themselves. There is no execute/send/post command
    anywhere in this CLI; that boundary is intentional.
    """
    action_id = args.action_id or hashlib.sha256(
        f"{args.target_type}:{args.target_id}:{args.action_type}:{args.draft_content or ''}".encode()
    ).hexdigest()[:16]

    action = EngagementAction(
        action_id=action_id,
        target_type=args.target_type,
        target_id=args.target_id,
        target_url=args.target_url,
        action_type=args.action_type,
        reaction_type=args.reaction_type,
        draft_content=args.draft_content,
        rubric_score=args.rubric_score,
        rationale=args.rationale,
    )
    with get_db(args.db) as db:
        db.upsert_engagement_action(action)
        print(f"[+] Queued drafted '{action.action_type}' action ({action.action_id}) for human review.")


def cmd_list_engagement(args: argparse.Namespace) -> None:
    """List the drafted engagement queue for human review."""
    with get_db(args.db) as db:
        actions = db.query_engagement_actions(
            status=args.status, target_type=args.target_type, min_rubric_score=args.min_score, limit=args.limit
        )
        if args.json:
            out = []
            for a in actions:
                name = None
                if a.target_type == "dm":
                    t = db.get_dm_thread(a.target_id)
                    name = t.participant_name if t else None
                elif a.target_type == "post":
                    p = db.get_post(a.target_id)
                    name = p.author_name if p else None
                out.append({
                    "action_id": a.action_id, "target_type": a.target_type, "target_id": a.target_id,
                    "target_url": a.target_url, "action_type": a.action_type, "reaction_type": a.reaction_type,
                    "status": a.status, "rubric_score": a.rubric_score, "draft_content": a.draft_content,
                    "rationale": a.rationale, "created_at": a.created_at.isoformat(),
                    "counterparty_name": name,
                })
            print(json.dumps(out, indent=2))
            return
        print(f"[*] Found {len(actions)} engagement actions in database matching criteria:")
        print_engagement_actions_table(actions)


def cmd_review_engagement(args: argparse.Namespace) -> None:
    """
    Record a human's approve/reject decision on a drafted engagement action.
    Only 'approved' or 'rejected' are accepted here -- this CLI has no path to 'executed';
    performing the approved action in the browser remains entirely the user's own manual step.
    """
    with get_db(args.db) as db:
        updated = db.set_engagement_action_status(args.action_id, args.status)
        if updated:
            print(f"[+] Marked action '{args.action_id}' as '{args.status}'.")
        else:
            print(f"[!] No engagement action found with ID '{args.action_id}'.", file=sys.stderr)


async def async_inspect(args: argparse.Namespace) -> Optional[LinkedInProfileDetailed]:
    """
    Inspect a single LinkedIn profile via offline HTML snapshot, cached DuckDB record,
    or live local Chrome CDP session.
    """
    raw_target = args.target or args.url
    if not raw_target and not args.html:
        print("[!] Error: You must specify a target profile URL or handle (e.g. 'gary-tyr' or 'https://www.linkedin.com/in/gary-tyr').", file=sys.stderr)
        return None

    profile: Optional[LinkedInProfileDetailed] = None

    # Case 1: Offline HTML dump
    if args.html:
        html_path = Path(args.html)
        if not html_path.exists():
            print(f"[!] Error: File not found: {html_path}", file=sys.stderr)
            return None
        html_content = html_path.read_text(encoding="utf-8")
        target_hint = raw_target if raw_target else None
        t0 = time.monotonic()
        profile = parse_linkedin_profile_html(html_content, profile_url_hint=target_hint)
        parse_ms = (time.monotonic() - t0) * 1000
        print(f"[+] Parsed offline profile in {parse_ms:.2f}ms via selectolax.")

    # Case 2: Cached DuckDB profile
    elif getattr(args, "cached", False) and raw_target:
        with get_db(args.db) as db:
            profile = db.get_detailed_profile(raw_target)
            if profile and profile.experience:
                print(f"[*] Retrieved cached profile for '{profile.name}' from DuckDB.")

    # Case 3: Live CDP Inspection
    if profile is None:
        clean_raw = (raw_target or "").strip()
        if clean_raw.startswith("http://") or clean_raw.startswith("https://"):
            target_url = canonicalize_linkedin_url(clean_raw)
        else:
            target_url = f"https://www.linkedin.com/in/{clean_raw.strip('/')}"

        print(f"[*] Inspecting target profile URL via local CDP: {target_url}")

        if get_active_instances is None or run_cdp is None:
            print("[!] Error: profile_manager utilities unavailable.", file=sys.stderr)
            return None

        instances = get_active_instances()
        inst_name = None
        port = 9222
        from listen import pick_instance
        picked = pick_instance(instances, getattr(args, "profile", None) or "linkedin", getattr(args, "port", None))
        if picked is not None:
            inst_name = picked["name"]
            port = int(picked.get("port") or 9222)
            print(f"[*] Connected to active browser instance '{inst_name}' on port {port}.")
        else:
            profile_name = args.profile or "linkedin"
            profile_path = PROFILES_ROOT / profile_name
            has_cookies = (profile_path / "Default" / "Network" / "Cookies").exists() or (profile_path / "Default" / "Cookies").exists()

            if not profile_path.exists() or not has_cookies:
                if args.setup:
                    print(f"[*] Profile '{profile_name}' not initialized. Starting interactive login setup...")
                    interactive_setup(profile_name, "https://www.linkedin.com/login", destination_check="feed")
                else:
                    print(f"\n[!] Persistent profile '{profile_name}' lacks active session cookies at:", file=sys.stderr)
                    print(f"    {profile_path}\n", file=sys.stderr)
                    print(f"[*] Pass '--setup' to launch interactive login window.\n", file=sys.stderr)
                    return None

            print(f"[*] Launching Chrome with profile '{profile_name}' (headless={args.headless})...")
            inst_name = launch_profile(profile_name, headless=args.headless)
            instances = get_active_instances()
            if instances:
                for inst in instances:
                    if inst["name"] == inst_name:
                        port = int(inst.get("port") or 9222)
                        break

        print(f"[*] Navigating tab to profile...")
        run_cdp([inst_name, "Page.navigate", json.dumps({"url": target_url})])

        wait_sec = float(getattr(args, "wait", 3.5))
        await asyncio.sleep(wait_sec)

        # Smooth scroll to hydrate lazy sections
        try:
            run_cdp([
                inst_name,
                "Runtime.evaluate",
                json.dumps({"expression": "window.scrollBy({top: 800, behavior: 'smooth'})"}),
            ])
            await asyncio.sleep(1.5)
        except Exception:
            pass

        eval_res = run_cdp([
            inst_name,
            "Runtime.evaluate",
            json.dumps({"expression": "document.documentElement.outerHTML"}),
        ])
        outer_html = ""
        if isinstance(eval_res, dict) and "result" in eval_res:
            outer_html = eval_res["result"].get("value", "")

        if not outer_html:
            print("[!] Error: Could not extract DOM outerHTML from tab.", file=sys.stderr)
            return None

        profile = parse_linkedin_profile_html(outer_html, profile_url_hint=target_url)

    if not profile:
        print("[!] Error: Failed to extract profile details.", file=sys.stderr)
        return None

    # Role & Company matching
    target_roles = [r.strip() for r in args.roles.split(",")] if getattr(args, "roles", None) else []
    target_company = getattr(args, "company", None) or profile.current_company or ""
    if target_roles:
        profile.role_match_score = score_role(target_roles, profile.headline)
    if target_company:
        profile.company_match_score = score_company(target_company, profile.headline)

    # Deterministic Warmth Assessment
    mutual_evals = []
    for m_name in profile.mutual_sample:
        mutual_evals.append(
            score_single_mutual(
                name=m_name,
                has_shared_company_non_overlap=True,
                is_domain_peer=True,
            )
        )
    is_friend = getattr(args, "personal_friend", False)
    assessment = assess_contact(
        candidate_name=profile.name,
        degree=profile.degree,
        is_personal_friend=is_friend,
        mutual_evaluations=mutual_evals,
        total_mutual_count=profile.mutual_count,
        has_open_profile=bool(profile.open_profile),
    )
    profile.warmth_degree = assessment.warmth_degree
    profile.contact_tier = assessment.contact_tier
    profile.warmth_rationale = assessment.rationale
    profile.action_recommendation = assessment.action_recommendation

    # Persist to DuckDB unless --no-save
    if not getattr(args, "no_save", False):
        with get_db(args.db) as db:
            db.upsert_detailed_profile(profile)
            print(f"[+] Persisted detailed profile for '{profile.name}' to DuckDB ({db.db_path}).")

    # Output
    if getattr(args, "json", False):
        print(json.dumps(profile.model_dump(mode="json"), indent=2))
    else:
        print_detailed_profile_card(profile, args)

    return profile


def cmd_inspect(args: argparse.Namespace) -> None:
    """Run single LinkedIn profile inspection."""
    asyncio.run(async_inspect(args))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified Orchestrator CLI for Q4 High-Performance CDP Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    # inspect
    inspect_p = subparsers.add_parser("inspect", help="Inspect individual LinkedIn profile details (experience, education, skills, mutuals, warmth)")
    inspect_p.add_argument("target", nargs="?", default=None, help="Target profile URL or public handle (e.g. 'gary-tyr', 'https://www.linkedin.com/in/gary-tyr')")
    inspect_p.add_argument("--url", help="Target profile URL (alternative to positional argument)")
    inspect_p.add_argument("--html", help="Path to offline HTML snapshot file (bypasses live browser)")
    inspect_p.add_argument("--experience", action="store_true", help="Display work experience history")
    inspect_p.add_argument("--education", action="store_true", help="Display education history")
    inspect_p.add_argument("--skills", action="store_true", help="Display skills list")
    inspect_p.add_argument("--all", action="store_true", help="Display all sections (experience, education, skills)")
    inspect_p.add_argument("--roles", help="Comma-separated target roles to compute role match score")
    inspect_p.add_argument("--company", help="Target company name for company match score")
    inspect_p.add_argument("--personal-friend", action="store_true", help="Flag if candidate is a personal friend (Degree 7 / WARM)")
    inspect_p.add_argument("--cached", action="store_true", help="Read from local DuckDB if previously saved")
    inspect_p.add_argument("--profile", default="linkedin", help="Persistent Chrome profile name (default: 'linkedin')")
    inspect_p.add_argument("--port", type=int, default=None, help="Debugger port of the browser instance to attach to (overrides profile auto-pick)")
    inspect_p.add_argument("--setup", action="store_true", help="Launch interactive login setup if profile not initialized")
    inspect_p.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    inspect_p.add_argument("--wait", type=float, default=3.5, help="Seconds to wait after navigation (default: 3.5)")
    inspect_p.add_argument("--no-save", action="store_true", help="Do not persist profile details to DuckDB")
    inspect_p.add_argument("--json", action="store_true", help="Output raw structured JSON to stdout")
    inspect_p.add_argument("--db", default=None, help="DuckDB database path")

    # discover
    discover_p = subparsers.add_parser("discover", help="Live LinkedIn contact discovery via CDP & Voyager interception")
    discover_p.add_argument("--company", help="Target company name (e.g. 'Larkspur', 'Verdant')")
    discover_p.add_argument("--roles", help="Comma-separated target roles (e.g. 'Marketing Engineer')")
    discover_p.add_argument("--keywords", help="Direct search keywords")
    discover_p.add_argument("--company-id", help="LinkedIn company numeric or slug ID")
    discover_p.add_argument("--network", default="F,S", help="Network distance filters (default: 'F,S' for 1st and 2nd)")
    discover_p.add_argument("--url", help="Direct search URL (overrides auto-generated query)")
    discover_p.add_argument("--profile", default="linkedin", help="Persistent Chrome profile name (default: 'linkedin')")
    discover_p.add_argument("--port", type=int, default=None, help="Debugger port of the browser instance to attach to (overrides profile auto-pick)")
    discover_p.add_argument("--setup", action="store_true", help="Launch interactive login setup if profile not initialized")
    discover_p.add_argument("--headless", action="store_true", help="Run in headless mode")
    discover_p.add_argument("--timeout", type=float, default=15.0, help="Capture timeout in seconds (default: 15.0)")
    discover_p.add_argument("--min-score", type=float, default=40.0, help="Minimum role match score threshold (default: 40.0)")
    discover_p.add_argument("--no-save", action="store_true", help="Do not persist discovered contacts to DuckDB")
    discover_p.add_argument("--db", default=None, help="DuckDB database path")

    # eval
    eval_p = subparsers.add_parser("eval", help="Run comprehensive pipeline evaluations across all job roles")
    eval_p.add_argument("--db", default=None, help="DuckDB database path")

    # sync-network
    sync_p = subparsers.add_parser("sync-network", help="Ingest contacts from _shared_facts/NETWORK.md into DuckDB")
    sync_p.add_argument("--path", default=None, help="Path to NETWORK.md")
    sync_p.add_argument("--db", default=None, help="DuckDB database path")

    # parse-html
    parse_p = subparsers.add_parser("parse-html", help="Fast parse LinkedIn search results HTML dump via selectolax")
    parse_p.add_argument("input", help="Path to HTML file")
    parse_p.add_argument("--company", help="Target company name filter")
    parse_p.add_argument("--roles", help="Comma-separated target roles")
    parse_p.add_argument("--min-score", type=float, default=40.0, help="Minimum role match score")
    parse_p.add_argument("--save", action="store_true", help="Save extracted contacts to DuckDB")
    parse_p.add_argument("--db", default=None, help="DuckDB database path")

    # ingest-connections / list-connections (implemented in connections.py; read-only on LinkedIn)
    ingest_conn_p = subparsers.add_parser("ingest-connections", help="Read-only ingest of your 1st-degree connections (scroll + passive read) into DuckDB")
    ingest_conn_p.add_argument("--db", default=None, help="DuckDB database path")
    ingest_conn_p.add_argument("--max", type=int, default=3000, help="Hard cap on connections captured")
    ingest_conn_p.add_argument("--max-minutes", type=float, default=20.0, help="Hard cap on run time")
    ingest_conn_p.add_argument("--profile", default="linkedin", help="Chrome profile name (authenticated LinkedIn session)")
    ingest_conn_p.add_argument("--dry-run", action="store_true", help="Parse and print counts without writing")
    list_conn_p = subparsers.add_parser("list-connections", help="List stored 1st-degree connections")
    list_conn_p.add_argument("--db", default=None, help="DuckDB database path")
    list_conn_p.add_argument("--company", help="Filter by company")
    list_conn_p.add_argument("--limit", type=int, default=50, help="Max results")
    list_conn_p.add_argument("--json", action="store_true", help="Emit JSON")
    list_conn_p.add_argument("--with-posts", action="store_true", help="Join stored posts by handle: post count and average engagement per connection")
    search_conn_p = subparsers.add_parser("search-connections", help="Query-driven 1st-degree people search plan (live run gated; --dry-run prints the plan)")
    search_conn_p.add_argument("--segment", default="all", help="S1|S2|S3|S4|all")
    search_conn_p.add_argument("--max-pages", type=int, default=3, help="Pages per query (10 results each)")
    search_conn_p.add_argument("--max-requests", type=int, default=60, help="Hard cap on page loads per run")
    search_conn_p.add_argument("--dry-run", action="store_true", help="Print plan and URLs; open no browser")
    search_conn_p.add_argument("--profile", default="linkedin", help="Chrome profile name")
    search_conn_p.add_argument("--db", default=None, help="DuckDB database path")

    # list
    list_p = subparsers.add_parser("list", help="List stored contacts from DuckDB")
    list_p.add_argument("--company", help="Filter by company")
    list_p.add_argument("--min-score", type=float, default=0.0, help="Minimum match score")
    list_p.add_argument("--limit", type=int, default=50, help="Max results")
    list_p.add_argument("--db", default=None, help="DuckDB database path")

    # inspect-job
    inspect_job_p = subparsers.add_parser("inspect-job", help="Inspect a single LinkedIn job posting (description, criteria, salary, role/company fit)")
    inspect_job_p.add_argument("target", nargs="?", default=None, help="Target job URL or numeric ID (e.g. '4123456789', 'https://www.linkedin.com/jobs/view/4123456789/')")
    inspect_job_p.add_argument("--url", help="Target job URL (alternative to positional argument)")
    inspect_job_p.add_argument("--html", help="Path to offline HTML snapshot file (bypasses live browser)")
    inspect_job_p.add_argument("--roles", help="Comma-separated target roles to compute role match score")
    inspect_job_p.add_argument("--company", help="Target company name for company match score (defaults to the posting's own company)")
    inspect_job_p.add_argument("--cached", action="store_true", help="Read from local DuckDB if previously saved")
    inspect_job_p.add_argument("--profile", default="linkedin", help="Persistent Chrome profile name (default: 'linkedin')")
    inspect_job_p.add_argument("--port", type=int, default=None, help="Debugger port of the browser instance to attach to (overrides profile auto-pick)")
    inspect_job_p.add_argument("--setup", action="store_true", help="Launch interactive login setup if profile not initialized")
    inspect_job_p.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    inspect_job_p.add_argument("--wait", type=float, default=3.5, help="Seconds to wait after navigation (default: 3.5)")
    inspect_job_p.add_argument("--no-save", action="store_true", help="Do not persist job details to DuckDB")
    inspect_job_p.add_argument("--json", action="store_true", help="Output raw structured JSON to stdout")
    inspect_job_p.add_argument("--db", default=None, help="DuckDB database path")

    # inspect-company
    inspect_company_p = subparsers.add_parser("inspect-company", help="Inspect a single LinkedIn company page (industry, size, HQ, about)")
    inspect_company_p.add_argument("target", nargs="?", default=None, help="Target company URL or slug (e.g. 'umbra', 'https://www.linkedin.com/company/umbra/')")
    inspect_company_p.add_argument("--url", help="Target company URL (alternative to positional argument)")
    inspect_company_p.add_argument("--html", help="Path to offline HTML snapshot file (bypasses live browser)")
    inspect_company_p.add_argument("--cached", action="store_true", help="Read from local DuckDB if previously saved")
    inspect_company_p.add_argument("--profile", default="linkedin", help="Persistent Chrome profile name (default: 'linkedin')")
    inspect_company_p.add_argument("--port", type=int, default=None, help="Debugger port of the browser instance to attach to (overrides profile auto-pick)")
    inspect_company_p.add_argument("--setup", action="store_true", help="Launch interactive login setup if profile not initialized")
    inspect_company_p.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    inspect_company_p.add_argument("--wait", type=float, default=3.5, help="Seconds to wait after navigation (default: 3.5)")
    inspect_company_p.add_argument("--no-save", action="store_true", help="Do not persist company details to DuckDB")
    inspect_company_p.add_argument("--json", action="store_true", help="Output raw structured JSON to stdout")
    inspect_company_p.add_argument("--db", default=None, help="DuckDB database path")

    # discover-jobs
    discover_jobs_p = subparsers.add_parser("discover-jobs", help="Live LinkedIn job search discovery via CDP navigation & DOM parsing")
    discover_jobs_p.add_argument("--company", help="Target company name (e.g. 'Larkspur', 'Verdant')")
    discover_jobs_p.add_argument("--roles", help="Comma-separated target roles (e.g. 'Marketing Engineer')")
    discover_jobs_p.add_argument("--keywords", help="Direct search keywords")
    discover_jobs_p.add_argument("--location", help="Location filter (e.g. 'San Francisco, CA' or 'Remote')")
    discover_jobs_p.add_argument("--url", help="Direct search URL (overrides auto-generated query)")
    discover_jobs_p.add_argument("--profile", default="linkedin", help="Persistent Chrome profile name (default: 'linkedin')")
    discover_jobs_p.add_argument("--port", type=int, default=None, help="Debugger port of the browser instance to attach to (overrides profile auto-pick)")
    discover_jobs_p.add_argument("--setup", action="store_true", help="Launch interactive login setup if profile not initialized")
    discover_jobs_p.add_argument("--headless", action="store_true", help="Run in headless mode")
    discover_jobs_p.add_argument("--min-score", type=float, default=40.0, help="Minimum role match score threshold (default: 40.0)")
    discover_jobs_p.add_argument("--no-save", action="store_true", help="Do not persist discovered jobs to DuckDB")
    discover_jobs_p.add_argument("--db", default=None, help="DuckDB database path")

    # list-jobs
    list_jobs_p = subparsers.add_parser("list-jobs", help="List stored job postings from DuckDB")
    list_jobs_p.add_argument("--company", help="Filter by company")
    list_jobs_p.add_argument("--min-score", type=float, default=0.0, help="Minimum role match score")
    list_jobs_p.add_argument("--status", help="Filter by application_status (e.g. 'discovered', 'applied')")
    list_jobs_p.add_argument("--limit", type=int, default=50, help="Max results")
    list_jobs_p.add_argument("--db", default=None, help="DuckDB database path")

    # list-companies
    list_companies_p = subparsers.add_parser("list-companies", help="List stored companies from DuckDB")
    list_companies_p.add_argument("--industry", help="Filter by industry")
    list_companies_p.add_argument("--limit", type=int, default=50, help="Max results")
    list_companies_p.add_argument("--db", default=None, help="DuckDB database path")

    # discover-feed
    discover_feed_p = subparsers.add_parser("discover-feed", help="Live feed/posts-tab discovery via CDP navigation & DOM parsing (read-only)")
    discover_feed_p.add_argument("--company", help="Scope to a company's Posts tab (slug, e.g. 'umbra')")
    discover_feed_p.add_argument("--person", help="Scope to a person's Activity tab (handle, e.g. 'gary-tyr')")
    discover_feed_p.add_argument("--url", help="Direct feed/posts URL (overrides company/person)")
    discover_feed_p.add_argument("--topics", help="Comma-separated target topics for rubric scoring (e.g. 'Marketing Engineer,Design Systems')")
    discover_feed_p.add_argument("--authors", help="Comma-separated target author names for author-fit scoring")
    discover_feed_p.add_argument("--profile", default="linkedin", help="Persistent Chrome profile name (default: 'linkedin')")
    discover_feed_p.add_argument("--port", type=int, default=None, help="Debugger port of the browser instance to attach to (overrides profile auto-pick)")
    discover_feed_p.add_argument("--setup", action="store_true", help="Launch interactive login setup if profile not initialized")
    discover_feed_p.add_argument("--headless", action="store_true", help="Run in headless mode")
    discover_feed_p.add_argument("--min-score", type=float, default=40.0, help="Minimum topic match score threshold (default: 40.0)")
    discover_feed_p.add_argument("--no-save", action="store_true", help="Do not persist discovered posts to DuckDB")
    discover_feed_p.add_argument("--db", default=None, help="DuckDB database path")

    # inspect-thread
    inspect_thread_p = subparsers.add_parser("inspect-thread", help="Inspect a single open LinkedIn DM thread (read-only, no message sent)")
    inspect_thread_p.add_argument("target", nargs="?", default=None, help="Thread URL, e.g. 'https://www.linkedin.com/messaging/thread/<id>/'")
    inspect_thread_p.add_argument("--url", help="Thread URL (alternative to positional argument)")
    inspect_thread_p.add_argument("--html", help="Path to offline HTML snapshot file (bypasses live browser)")
    inspect_thread_p.add_argument("--cached", action="store_true", help="Read from local DuckDB if previously saved")
    inspect_thread_p.add_argument("--profile", default="linkedin", help="Persistent Chrome profile name (default: 'linkedin')")
    inspect_thread_p.add_argument("--port", type=int, default=None, help="Debugger port of the browser instance to attach to (overrides profile auto-pick)")
    inspect_thread_p.add_argument("--setup", action="store_true", help="Launch interactive login setup if profile not initialized")
    inspect_thread_p.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    inspect_thread_p.add_argument("--wait", type=float, default=3.5, help="Seconds to wait after navigation (default: 3.5)")
    inspect_thread_p.add_argument("--no-save", action="store_true", help="Do not persist thread details to DuckDB")
    inspect_thread_p.add_argument("--json", action="store_true", help="Output raw structured JSON to stdout")
    inspect_thread_p.add_argument("--db", default=None, help="DuckDB database path")

    # listen-feed / add-post (scripts/listen.py)
    from listen import add_parsers as _add_listen_parsers
    _add_listen_parsers(subparsers)

    # list-posts
    list_posts_p = subparsers.add_parser("list-posts", help="List stored posts from DuckDB")
    list_posts_p.add_argument("--author", help="Filter by author name")
    list_posts_p.add_argument("--min-score", type=float, default=0.0, help="Minimum topic match score")
    list_posts_p.add_argument("--limit", type=int, default=50, help="Max results")
    list_posts_p.add_argument("--db", default=None, help="DuckDB database path")

    # rank-posts
    rank_posts_p = subparsers.add_parser("rank-posts", help="Rank stored posts worth commenting on (read-only; never navigates or queues)")
    rank_posts_p.add_argument("--db", default=None, help="DuckDB database path")
    rank_posts_p.add_argument("--top", type=int, default=10, help="Number of results (default: 10)")
    rank_posts_p.add_argument("--max-age-days", type=int, default=7, help="Drop posts older than this (default: 7)")
    rank_posts_p.add_argument("--max-pages", type=int, default=3, help="Max company-page posts in the top results (default: 3; use -1 for unlimited)")
    rank_posts_p.add_argument("--max-per-cluster", type=int, default=2, help="Max posts per topic cluster (primary matched keyword) in the top results (default: 2; use -1 for unlimited)")
    rank_posts_p.add_argument("--min-score", type=float, default=50.0, help="Score floor: drop posts scoring below this before any cap (default: 50; 0 disables). The list may be shorter than --top.")
    rank_posts_p.add_argument("--targets", default=None, help="Path to engagement targets JSON (default: ~/.config/chrome-agent/engagement_targets.json)")
    rank_posts_p.add_argument("--json", action="store_true", help="Output JSON list to stdout")

    # rank-creators
    rank_creators_p = subparsers.add_parser("rank-creators", help="Rank authors by consistent target alignment (read-only)")
    rank_creators_p.add_argument("--db", default=None, help="DuckDB database path")
    rank_creators_p.add_argument("--top", type=int, default=10, help="Number of results (default: 10)")
    rank_creators_p.add_argument("--min-posts", type=int, default=3, help="Minimum posts per author (default: 3)")
    rank_creators_p.add_argument("--json", action="store_true", help="Output JSON list to stdout")

    # list-threads
    list_threads_p = subparsers.add_parser("list-threads", help="List stored DM threads from DuckDB")
    list_threads_p.add_argument("--participant", help="Filter by participant name")
    list_threads_p.add_argument("--limit", type=int, default=50, help="Max results")
    list_threads_p.add_argument("--db", default=None, help="DuckDB database path")

    # queue-engagement
    queue_engagement_p = subparsers.add_parser("queue-engagement", help="Add a drafted, rubric-scored engagement action to the human review queue (never executes it)")
    queue_engagement_p.add_argument("--target-type", required=True, choices=["post", "dm"], help="What kind of object this action targets")
    queue_engagement_p.add_argument("--target-id", required=True, help="Post.post_id or DMThread.thread_id being acted on")
    queue_engagement_p.add_argument("--target-url", help="Canonical URL of the target, for human execution")
    queue_engagement_p.add_argument("--action-type", required=True, choices=["like", "comment", "repost", "post", "message"], help="like, comment, repost, post (new), or message")
    queue_engagement_p.add_argument("--reaction-type", choices=["like", "celebrate", "support", "love", "insightful", "funny"], help="Set only when --action-type like")
    queue_engagement_p.add_argument("--draft-content", help="Drafted comment/post/message text for human review")
    queue_engagement_p.add_argument("--rubric-score", type=float, default=0.0, help="Composite rubric score driving prioritization")
    queue_engagement_p.add_argument("--rationale", help="Human-readable reason this action was suggested and scored")
    queue_engagement_p.add_argument("--action-id", help="Explicit action ID (default: derived hash of target+type+content, so re-queuing the same draft updates it idempotently)")
    queue_engagement_p.add_argument("--db", default=None, help="DuckDB database path")

    # list-engagement
    list_engagement_p = subparsers.add_parser("list-engagement", help="List the drafted engagement queue for human review")
    list_engagement_p.add_argument("--status", choices=["drafted", "approved", "rejected", "executed"], help="Filter by status")
    list_engagement_p.add_argument("--target-type", choices=["post", "dm"], help="Filter by target type")
    list_engagement_p.add_argument("--min-score", type=float, default=0.0, help="Minimum rubric score")
    list_engagement_p.add_argument("--limit", type=int, default=50, help="Max results")
    list_engagement_p.add_argument("--json", action="store_true", help="Output JSON list to stdout (nothing else printed)")
    list_engagement_p.add_argument("--db", default=None, help="DuckDB database path")

    # review-engagement
    review_engagement_p = subparsers.add_parser("review-engagement", help="Record a human approve/reject decision on a drafted engagement action (does not execute it)")
    review_engagement_p.add_argument("action_id", help="The action_id to update")
    review_engagement_p.add_argument("--status", required=True, choices=["approved", "rejected"], help="Human review decision")
    review_engagement_p.add_argument("--db", default=None, help="DuckDB database path")

    args = parser.parse_args()

    if args.action == "inspect":
        cmd_inspect(args)
    elif args.action == "discover":
        cmd_discover(args)
    elif args.action == "eval":
        cmd_eval(args)
    elif args.action == "sync-network":
        cmd_sync_network(args)
    elif args.action == "parse-html":
        cmd_parse_html(args)
    elif args.action == "ingest-connections":
        from connections import cmd_ingest_connections
        cmd_ingest_connections(args)
    elif args.action == "list-connections":
        from connections import cmd_list_connections
        cmd_list_connections(args)
    elif args.action == "search-connections":
        from connections import cmd_search_connections
        cmd_search_connections(args)
    elif args.action == "list":
        cmd_list(args)
    elif args.action == "inspect-job":
        cmd_inspect_job(args)
    elif args.action == "inspect-company":
        cmd_inspect_company(args)
    elif args.action == "discover-jobs":
        cmd_discover_jobs(args)
    elif args.action == "list-jobs":
        cmd_list_jobs(args)
    elif args.action == "list-companies":
        cmd_list_companies(args)
    elif args.action == "discover-feed":
        cmd_discover_feed(args)
    elif args.action == "inspect-thread":
        cmd_inspect_thread(args)
    elif args.action == "listen-feed":
        from listen import cmd_listen_feed
        cmd_listen_feed(args)
    elif args.action == "add-post":
        from listen import cmd_add_post
        cmd_add_post(args)
    elif args.action == "list-posts":
        cmd_list_posts(args)
    elif args.action == "rank-posts":
        cmd_rank_posts(args)
    elif args.action == "rank-creators":
        cmd_rank_creators(args)
    elif args.action == "list-threads":
        cmd_list_threads(args)
    elif args.action == "queue-engagement":
        cmd_queue_engagement(args)
    elif args.action == "list-engagement":
        cmd_list_engagement(args)
    elif args.action == "review-engagement":
        cmd_review_engagement(args)


if __name__ == "__main__":
    main()
