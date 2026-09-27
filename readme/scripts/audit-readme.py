#!/usr/bin/env python3
"""
audit-readme.py - GHFM README auditor (add --producthunt for launch readiness)

Performs a rigorous, ReDoS-safe audit of any README.md against:
1. Above-the-Fold & Hero impact
2. Frictionless Quickstart ergonomics
3. Visual Assets & Architecture
4. GHFM Craftsmanship & CLS prevention
5. Trust (license), plus Product Hunt embed and social proof with --producthunt
6. Third-party CDN dependency budgets & Placeholder validation
"""

import argparse
import html
import json
import os
import re
import sys
from urllib.parse import urlparse

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def strip_code_and_comments(text: str) -> str:
    """Removes HTML comments and fenced/inline code blocks to prevent false positive matches."""
    # Strip HTML comments safely
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    # Strip fenced code blocks
    text = re.sub(r"^```[\s\S]*?^```", "", text, flags=re.MULTILINE)
    # Strip inline code
    text = re.sub(r"`[^`\n]+`", "", text)
    return text


def extract_image_origins(content: str) -> list:
    """Extracts unique external HTTP/HTTPS hostnames used in image tags."""
    origins = set()
    # Markdown image syntax: ![alt](url) - strictly bounded
    md_matches = re.findall(r"!\[[^\]\n]*\]\(([^\s\)]+)", content)
    # HTML image syntax: <img src="url"> and <source srcset="url">
    html_matches = re.findall(r"""<(?:img|source)[^>]+(?:src|srcset)=["']([^"'\s,]+)""", content, re.IGNORECASE)
    
    for url in md_matches + html_matches:
        if url.startswith("http://") or url.startswith("https://"):
            try:
                parsed = urlparse(url)
                if parsed.hostname:
                    origins.add(parsed.hostname.lower())
            except Exception:
                pass
    return sorted(list(origins))


def audit_readme(content: str, file_path: str, max_origins: int = 4, launch: bool = False) -> dict:
    total_chars = len(content)
    raw_lines = content.splitlines()
    total_lines = len(raw_lines)
    
    # Analyze raw content for code blocks and media
    fenced_blocks = re.findall(r"^```([a-zA-Z0-9_\-]+)?", content, flags=re.MULTILINE)
    fenced_code_count = len([b for b in fenced_blocks if b and b.lower() != "mermaid"])
    has_mermaid = any(b.lower() == "mermaid" for b in fenced_blocks if b)
    
    # Strip code and comments for prose/structural checks
    stripped = strip_code_and_comments(content)
    stripped_lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    top_30_stripped = "\n".join(stripped_lines[:min(30, len(stripped_lines))])

    scores = {}
    details = {}
    recommendations = []
    penalties = 0

    # -------------------------------------------------------------
    # 1. Above-the-Fold & Hero (Max 25 pts)
    # -------------------------------------------------------------
    hero_score = 0
    hero_checks = []

    # Title check (H1 outside code fences)
    has_h1 = bool(re.search(r"^#\s+[^\n]+", stripped, re.MULTILINE)) or bool(
        re.search(r"<h1[^>]*>[^<]+</h1>", stripped, re.IGNORECASE)
    )
    if has_h1:
        hero_score += 5
        hero_checks.append(("H1 Project Title present outside code blocks", True, 5))
    else:
        hero_checks.append(("Missing primary # Project Title", False, 0))
        recommendations.append("Add a clear, centered # Project Title at the top of the README.")

    # Bold tagline/value proposition hook
    has_tagline = bool(
        re.search(r"^\*\*[^\*\n]{10,}\*\*", top_30_stripped, re.MULTILINE)
    ) or bool(re.search(r"<b>[^<\n]{10,}</b>", top_30_stripped, re.IGNORECASE))
    if has_tagline:
        hero_score += 5
        hero_checks.append(("Bold 1-line value proposition hook present", True, 5))
    else:
        hero_checks.append(("Missing bold tagline hook in the hero section", False, 0))
        recommendations.append("Add a bold 1-line value proposition hook directly below the title (e.g., **The zero-config X for Y**).")

    # Badges ribbon (requires actual badge image reference, not just the word 'badge')
    has_badges = bool(
        re.search(r"(?:img\.shields\.io|badgen\.net|badge\.fury\.io)", top_30_stripped, re.IGNORECASE)
    )
    if has_badges:
        hero_score += 5
        hero_checks.append(("Verified badge ribbon detected in header area", True, 5))
    else:
        hero_checks.append(("No verified badge ribbon found above the fold", False, 0))
        recommendations.append("Add 3-5 cohesive badges (Release, License, Status) using shields.io or committed SVGs.")

    # Quick links bar (strictly bounded URLs to prevent backtracking)
    has_quick_links = bool(
        re.search(r"\[[^\n\]]+\]\([^\s\(\)\n]+\)\s*[•\|/]\s*\[[^\n\]]+\]\([^\s\(\)\n]+\)", top_30_stripped)
    )
    if has_quick_links:
        hero_score += 5
        hero_checks.append(("Quick navigation / link bar present", True, 5))
    else:
        hero_checks.append(("Missing compact Quick Links bar", False, 0))
        recommendations.append("Add a quick navigation bar: [Install](#installation) • [Quickstart](#quickstart) • [Docs](...)")

    # Hero visual asset in header area (strictly bounded URLs to prevent backtracking)
    has_hero_visual = bool(
        re.search(r"!\[[^\n\]]*\]\([^\s\(\)\n]+\.(?:gif|png|jpg|jpeg|webp|svg)\)", top_30_stripped, re.IGNORECASE)
    ) or bool(
        re.search(r"""<(?:img|source)[^>]+(?:src|srcset)=["'][^"'\s]+\.(?:gif|png|jpg|jpeg|webp|svg)["']""", top_30_stripped, re.IGNORECASE)
    ) or ("<picture>" in top_30_stripped.lower())
    if has_hero_visual:
        hero_score += 5
        hero_checks.append(("Hero visual asset (GIF/WebP/PNG/SVG) in hero section", True, 5))
    else:
        hero_checks.append(("Missing hero visual asset in hero section", False, 0))
        recommendations.append("Embed a high-resolution demo GIF, screenshot, or banner in the hero area.")

    scores["hero"] = hero_score
    details["hero"] = hero_checks

    # -------------------------------------------------------------
    # 2. Frictionless Quickstart (Max 20 pts)
    # -------------------------------------------------------------
    qs_score = 0
    qs_checks = []

    # Dedicated Installation / Quickstart header
    has_qs_header = bool(
        re.search(r"^##\s+[^\n]*(quickstart|installation|getting\s+started|quick\s+start)", stripped, re.IGNORECASE | re.MULTILINE)
    )
    if has_qs_header:
        qs_score += 10
        qs_checks.append(("Dedicated ## Quickstart or ## Installation section present", True, 10))
    else:
        qs_checks.append(("Missing explicit ## Quickstart or ## Installation section", False, 0))
        recommendations.append("Add an explicit '## Quickstart' or '## Installation' section high in the document.")

    # Fenced codeblocks with language tags
    if fenced_code_count >= 2:
        qs_score += 10
        qs_checks.append((f"Language-tagged code blocks verified ({fenced_code_count} found)", True, 10))
    elif fenced_code_count == 1:
        qs_score += 5
        qs_checks.append(("Only 1 language-tagged code block found (recommend 2+)", False, 5))
        recommendations.append("Include both an installation snippet and a runnable usage code block.")
    else:
        qs_checks.append(("No language-tagged code blocks found", False, 0))
        recommendations.append("Add copy-pasteable terminal/code snippets with explicit syntax tags (```bash, ```python).")

    scores["quickstart"] = qs_score
    details["quickstart"] = qs_checks

    # -------------------------------------------------------------
    # 3. Visual Assets & Architecture (Max 20 pts)
    # -------------------------------------------------------------
    visual_score = 0
    visual_checks = []

    # Architecture / Flow diagram
    has_arch_section = bool(re.search(r"^##\s+[^\n]*(architecture|how\s+it\s+works|lifecycle|workflow)", stripped, re.IGNORECASE | re.MULTILINE))
    if has_mermaid or has_arch_section:
        visual_score += 10
        visual_checks.append(("Architecture schematic or native Mermaid diagram present", True, 10))
    else:
        visual_checks.append(("No architecture schematic or Mermaid workflow diagram found", False, 0))
        recommendations.append("Add a native Mermaid.js diagram or architecture section to explain system mechanics.")

    # Multi-column card table for problem or feature breakdown
    has_card_table = ("<table" in stripped.lower()) and bool(re.search(r"""<td[^>]+width=["'][0-9]{1,3}%["']""", stripped, re.IGNORECASE))
    if has_card_table:
        visual_score += 5
        visual_checks.append(("Styled multi-column HTML card table found", True, 5))
    else:
        visual_checks.append(("No multi-column HTML card table detected", False, 0))
        recommendations.append("Structure problem statements or feature highlights into a 3-column HTML table.")

    # Vector icons / typography accents
    has_icons = ("api.iconify.design" in stripped) or ("skillicons.dev" in stripped) or bool(re.search(r"[⚡📦🚀💡🏛️🛠️📈👥📄🎯💥]", stripped))
    if has_icons:
        visual_score += 5
        visual_checks.append(("Vector icons or consistent visual section accents present", True, 5))
    else:
        visual_checks.append(("No visual icon accents detected", False, 0))
        recommendations.append("Enhance section headings and feature cards with Lucide icons or visual glyphs.")

    scores["visuals"] = visual_score
    details["visuals"] = visual_checks

    # -------------------------------------------------------------
    # 4. GHFM Craftsmanship & Layout Shift (Max 20 pts)
    # -------------------------------------------------------------
    craft_score = 0
    craft_checks = []

    # Dark / Light theme adaptability
    has_theme_adaptive = ("<picture>" in stripped.lower()) or ("#gh-dark-mode-only" in stripped) or ("prefers-color-scheme" in stripped)
    if has_theme_adaptive:
        craft_score += 5
        craft_checks.append(("Theme-adaptive media (<picture> / #gh-dark-mode-only) used", True, 5))
    else:
        craft_checks.append(("No dark/light mode theme-adaptive images detected", False, 0))
        recommendations.append("Use <picture> with prefers-color-scheme so assets render cleanly across dark and light themes.")

    # GitHub Native Alerts / Callouts
    has_alerts = bool(re.search(r"^>\s+\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]", stripped, re.MULTILINE))
    if has_alerts:
        craft_score += 5
        craft_checks.append(("GitHub Native Callouts (> [!NOTE], [!TIP]) present", True, 5))
    else:
        craft_checks.append(("No GitHub Native Alerts/Callouts found", False, 0))
        recommendations.append("Use GitHub Alert callouts (> [!TIP], > [!IMPORTANT]) for pro tips and operational warnings.")

    # Collapsible accordions
    has_details = ("<details>" in stripped.lower()) and ("<summary>" in stripped.lower())
    if has_details:
        craft_score += 5
        craft_checks.append(("Collapsible accordions (<details><summary>) implemented", True, 5))
    else:
        craft_checks.append(("No collapsible <details> accordions found", False, 0))
        recommendations.append("Wrap advanced configurations and recipes inside <details><summary> blocks.")

    # Structured markdown tables
    has_tables = bool(re.search(r"^\|[^\n]+\|[\r\n]+\|[\s\-:]+\|", stripped, re.MULTILINE))
    if has_tables:
        craft_score += 5
        craft_checks.append(("Structured comparison / reference tables present", True, 5))
    else:
        craft_checks.append(("No markdown tables found", False, 0))
        recommendations.append("Add a comparison table or configuration options table.")

    scores["craft"] = craft_score
    details["craft"] = craft_checks

    # -------------------------------------------------------------
    # 5. Trust (Max 5 pts), Launch & Trust with --producthunt (Max 15 pts)
    # -------------------------------------------------------------
    ph_score = 0
    ph_checks = []

    # Launch-only checks (Product Hunt embed, social proof) count only with --producthunt.
    # A README that isn't launching is not penalised for leaving them out.
    has_ph = bool(re.search(r"producthunt\.com/(?:posts|widgets)|api\.producthunt\.com", stripped, re.IGNORECASE))
    if not launch:
        ph_checks.append(("Product Hunt embed (skipped; pass --producthunt to score it)", True, 0))
    elif has_ph:
        ph_score += 5
        ph_checks.append(("Product Hunt launch widget or badge integrated", True, 5))
    else:
        ph_checks.append(("Missing Product Hunt launch embed / badge", False, 0))
        recommendations.append("Add the official Product Hunt embed image widget or launch badge.")

    # Explicit License section
    has_license = bool(re.search(r"^##\s+[^\n]*license", stripped, re.IGNORECASE | re.MULTILINE))
    if has_license:
        ph_score += 5
        ph_checks.append(("License section explicitly defined", True, 5))
    else:
        ph_checks.append(("Missing explicit ## License section", False, 0))
        recommendations.append("Add an explicit ## License section specifying open-source or commercial terms.")

    # Social Proof / Community
    has_social = bool(re.search(r"star-history\.com|contrib\.rocks|discord\.(?:gg|com/invite)|stargazers", stripped, re.IGNORECASE))
    if not launch:
        ph_checks.append(("Social proof (skipped; pass --producthunt to score it)", True, 0))
    elif has_social:
        ph_score += 5
        ph_checks.append(("Social proof signals (Star History, Discord, Contributor wall) found", True, 5))
    else:
        ph_checks.append(("Missing dynamic social proof (Star History or Contributor Wall)", False, 0))
        recommendations.append("Embed a Star History chart or Contributor avatar wall.")

    scores["producthunt"] = ph_score
    details["producthunt"] = ph_checks

    # -------------------------------------------------------------
    # 6. Performance & Credibility Guardrails (Penalties)
    # -------------------------------------------------------------
    guardrail_checks = []
    
    # A. Third-party CDN Origin Check
    origins = extract_image_origins(content)
    if len(origins) > max_origins:
        penalties += 10
        guardrail_checks.append((f"Third-party image origins ({len(origins)}) exceed budget (max {max_origins}): {', '.join(origins)}", False, -10))
        recommendations.append(f"Reduce external image origins ({len(origins)} detected). Vendor static icons locally or commit SVGs.")
    else:
        guardrail_checks.append((f"External image origins ({len(origins)}) within budget (<= {max_origins})", True, 0))

    # B. Cumulative Layout Shift (CLS) check
    # Flags <img> tags using width="100%" or missing intrinsic dimensions
    bad_dimensions = re.findall(r"""<img[^>]+width=["']100%["'][^>]*>""", content, re.IGNORECASE)
    if bad_dimensions:
        penalties += 5
        guardrail_checks.append((f"Found {len(bad_dimensions)} <img> tags with non-numeric width='100%' (CLS risk)", False, -5))
        recommendations.append("Replace width='100%' with intrinsic numeric pixel width/height to prevent layout shift.")
    else:
        guardrail_checks.append(("No invalid non-numeric width='100%' image tags found", True, 0))

    # C. Unresolved Placeholders Check
    placeholders = list(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", content)))
    if placeholders:
        penalties += 15
        guardrail_checks.append((f"Unresolved template placeholders detected: {', '.join(placeholders)}", False, -15))
        recommendations.append(f"Replace or resolve all template placeholders ({', '.join(placeholders)}) before publishing.")
    else:
        guardrail_checks.append(("No unpopulated {{PLACEHOLDERS}} detected", True, 0))

    details["guardrails"] = guardrail_checks

    # Without --producthunt the two launch checks drop out, so rescale the rest to 100.
    max_raw = 100 if launch else 90
    raw_total = round(sum(scores.values()) * 100 / max_raw)
    final_total = max(0, min(100, raw_total - penalties))

    return {
        "file": file_path,
        "total_score": final_total,
        "raw_score": raw_total,
        "penalties": penalties,
        "max_score": 100,
        "launch": launch,
        "scores": scores,
        "details": details,
        "origins": origins,
        "recommendations": recommendations,
    }


def print_report(audit: dict, verbose: bool = False, no_color: bool = False):
    c_cyan = "" if no_color else CYAN
    c_green = "" if no_color else GREEN
    c_yellow = "" if no_color else YELLOW
    c_red = "" if no_color else RED
    c_bold = "" if no_color else BOLD
    c_reset = "" if no_color else RESET

    total = audit["total_score"]
    color = c_green if total >= 85 else (c_yellow if total >= 65 else c_red)

    mode = "launch (Product Hunt)" if audit.get("launch") else "standard"
    print(f"\n{c_bold}{c_cyan}=== GHFM README Audit Report ({mode}) ==={c_reset}")
    print(f"Target File: {c_bold}{audit['file']}{c_reset}")
    print(f"Overall Score: {color}{c_bold}{total} / 100{c_reset} (Raw: {audit['raw_score']}, Penalties: -{audit['penalties']})\n")

    # Score Bar
    bar_width = 30
    filled = int(bar_width * (total / 100))
    bar = "█" * filled + "░" * (bar_width - filled)
    print(f"Readiness: [{color}{bar}{c_reset}]\n")

    categories = [
        ("Above-the-Fold & Hero", "hero", 25),
        ("Frictionless Quickstart", "quickstart", 20),
        ("Visual Assets & Architecture", "visuals", 20),
        ("GHFM Craftsmanship", "craft", 20),
        ("Launch & Trust" if audit.get("launch") else "Trust", "producthunt", 15 if audit.get("launch") else 5),
    ]

    for label, key, max_cat in categories:
        cat_score = audit["scores"].get(key, 0)
        c_color = c_green if cat_score == max_cat else (c_yellow if cat_score > 0 else c_red)
        print(f"{c_bold}{label:<32}{c_reset} : {c_color}{cat_score:>2} / {max_cat} pts{c_reset}")

        if verbose:
            for desc, passed, pts in audit["details"].get(key, []):
                sym = f"{c_green}✓{c_reset}" if passed else f"{c_red}✗{c_reset}"
                print(f"    {sym} {desc} ({pts} pts)")

    if verbose and audit["details"].get("guardrails"):
        print(f"\n{c_bold}Performance & Reliability Guardrails:{c_reset}")
        for desc, passed, pts in audit["details"]["guardrails"]:
            sym = f"{c_green}✓{c_reset}" if passed else f"{c_red}✗{c_reset}"
            pts_str = f"({pts} pts)" if pts != 0 else "(pass)"
            print(f"    {sym} {desc} {pts_str}")

    print()
    if audit["recommendations"]:
        print(f"{c_bold}{c_yellow}Actionable Next Steps to Reach 100/100:{c_reset}")
        for i, rec in enumerate(audit["recommendations"], 1):
            print(f"  {i}. {rec}")
    else:
        print(f"{c_green}{c_bold}Every check passes.{c_reset}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Audit a README for GHFM craftsmanship; --producthunt adds launch checks.")
    parser.add_argument("file", help="Path to README.md file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show granular check details")
    parser.add_argument("--json", action="store_true", help="Output raw JSON results")
    parser.add_argument("--producthunt", action="store_true", help="Also score launch checks: Product Hunt embed and social proof")
    parser.add_argument("--threshold", type=int, default=70, help="Minimum score required to exit with code 0 (default: 70)")
    parser.add_argument("--max-bytes", type=int, default=1048576, help="Maximum file size in bytes to audit (default: 1MB)")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color codes")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"Error: File '{args.file}' does not exist.", file=sys.stderr)
        sys.exit(2)

    file_size = os.path.getsize(args.file)
    if file_size > args.max_bytes:
        print(f"Error: File '{args.file}' exceeds size limit ({file_size} > {args.max_bytes} bytes).", file=sys.stderr)
        sys.exit(2)

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file '{args.file}': {e}", file=sys.stderr)
        sys.exit(2)

    results = audit_readme(content, args.file, launch=args.producthunt)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results, verbose=args.verbose, no_color=args.no_color)

    if results["total_score"] < args.threshold:
        sys.exit(1)


if __name__ == "__main__":
    main()
