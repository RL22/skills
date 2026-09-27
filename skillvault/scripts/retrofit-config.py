#!/usr/bin/env python3
"""
RETRO: Reusable Extraction & Tool-agnostic Reorganization.

Scans the filesystem for skills, extensions, and plugins outside of the central vault,
and categorizes them based on their agent-specificity and complexity.
"""

import argparse
from pathlib import Path

AGENT_KEYWORDS = ["claude", "codex", "gemini", "cursor", "opencode", "@workspace", "antigravity", "chatgpt"]
COMPLEX_KEYWORDS = ["npm run", "yarn", "pnpm", "docker", "make install"]

def analyze_skill(skill_dir: Path) -> dict:
    # Read all common text files to find keywords
    text_files = (
        list(skill_dir.glob("**/*.md")) + 
        list(skill_dir.glob("**/*.py")) + 
        list(skill_dir.glob("**/*.txt")) + 
        list(skill_dir.glob("**/*.json"))
    )
    
    found_agent_keywords = set()
    found_complex_keywords = set()
    
    for f in text_files:
        if not f.is_file():
            continue
        try:
            content = f.read_text(encoding="utf-8").lower()
            for kw in AGENT_KEYWORDS:
                if kw in content:
                    found_agent_keywords.add(kw)
            for kw in COMPLEX_KEYWORDS:
                if kw in content:
                    found_complex_keywords.add(kw)
        except Exception:
            pass
            
    # Heuristic for categorizing the skill
    if not found_agent_keywords and not found_complex_keywords:
        return {"category": "safe to migrate", "reasons": []}
    elif found_agent_keywords and not found_complex_keywords:
        reasons = [f"Remove agent-specific references: {', '.join(found_agent_keywords)}"]
        return {"category": "adaptable", "reasons": reasons}
    else:
        # If it has complex keywords, it probably should stay as is
        reasons = [f"Complex dependencies found: {', '.join(found_complex_keywords)}"]
        if found_agent_keywords:
             reasons.append(f"Agent-specific references: {', '.join(found_agent_keywords)}")
        return {"category": "stays as is", "reasons": reasons}

def is_valid_skill_dir(d: Path) -> bool:
    # A valid skill dir should contain at least one instructional/code file
    for ext in ["*.md", "*.py", "*.txt", "*.sh", "*.json"]:
        if any(f.is_file() for f in d.glob(ext)):
            return True
    return False

def scan_for_skills(root: Path) -> list[Path]:
    skills = []
    
    # 1. Find all directories containing a SKILL.md
    for skill_file in root.glob("**/SKILL.md"):
        if skill_file.parent not in skills and ".agents/skills" not in str(skill_file):
            skills.append(skill_file.parent)
        
    # 2. Find folders inside known extension/plugin directories
    # We look for folders inside generic skill/plugin directories (e.g. .claude/skills/*)
    target_dirs = ["skills", "plugins", "extensions", "rules"]
    for t in target_dirs:
        for match in root.glob(f"**/{t}/*"):
            if match.is_dir() and match not in skills and match.name != ".git" and ".agents/skills" not in str(match):
                # Ensure it's not just an empty structural folder
                if is_valid_skill_dir(match):
                    skills.append(match)
                
    return sorted(list(set(skills)))

def print_plan(root: Path):
    skills = scan_for_skills(root)
    
    safe = []
    adaptable = []
    stays = []
    
    for s in skills:
        res = analyze_skill(s)
        if res["category"] == "safe to migrate":
            safe.append((s, res))
        elif res["category"] == "adaptable":
            adaptable.append((s, res))
        else:
            stays.append((s, res))
            
    print("# SkillVault RETRO Migration Plan\n")
    print(f"Scanned path: `{root}`\n")
    
    print("## safe to migrate:")
    if not safe:
        print("- None found")
    for s, res in safe:
        try:
            rel = s.relative_to(root)
        except ValueError:
            rel = s
        print(f"- `{rel}`")
        
    print("\n## adaptable:")
    if not adaptable:
        print("- None found")
    for s, res in adaptable:
        try:
            rel = s.relative_to(root)
        except ValueError:
            rel = s
        print(f"- `{rel}`")
        for r in res["reasons"]:
            print(f"  - Adaptation: {r}")
            
    print("\n## stays as is:")
    if not stays:
        print("- None found")
    for s, res in stays:
        try:
            rel = s.relative_to(root)
        except ValueError:
            rel = s
        print(f"- `{rel}`")
        for r in res["reasons"]:
            print(f"  - Reason: {r}")
            
    print("\n*Note: Never apply these recommendations without human approval.*")
    
    print("\n## Recommended Next Steps")
    print("1. Review safe to migrate candidates.")
    print("2. Move approved safe skills into `~/.agents/skills`.")
    print("3. Adapt the adaptable skills by stripping agent-specific logic.")
    print("4. Leave 'stays as is' skills untouched.")

def main():
    parser = argparse.ArgumentParser(description="RETRO migration helper for SkillVault.")
    parser.add_argument("command", choices=["plan", "scan"], help="Scan for skills and propose migrations.")
    parser.add_argument("path", help="Project or home directory to scan.")
    args = parser.parse_args()
    
    root = Path(args.path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        import sys
        print(f"ERROR: Not a directory: {root}", file=sys.stderr)
        return 1
        
    print_plan(root)
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
