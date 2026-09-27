# SkillFit Scorecard

Use this scorecard to evaluate whether an agent skill fits a user, workflow, and agent stack.

## SIFT

SIFT means **Skill Inspection & Fit Testing**.

| Letter | Dimension | Question |
|---|---|---|
| S | Suitability | Does the skill fit the user and workflow? |
| I | Interoperability | Can the skill work across the user’s agent stack? |
| F | Fidelity | Does the skill produce reliable, high-quality output? |
| T | Trust | Is the skill safe, inspectable, and maintainable? |

## Scoring scale

Score each category from 1 to 5.

| Score | Meaning |
|---:|---|
| 1 | Poor |
| 2 | Weak |
| 3 | Acceptable |
| 4 | Strong |
| 5 | Excellent |

## Weighted categories

| Category | Weight | What to evaluate |
|---|---:|---|
| User / workflow fit | 25 | Does the skill solve a real recurring problem for this user? |
| Agent portability | 20 | Can the skill work across the user’s tools without major rewrites? |
| Output quality | 20 | Does the skill improve clarity, consistency, correctness, or usefulness? |
| Safety / trust | 20 | Is the skill safe, inspectable, and appropriate for the user’s risk profile? |
| Maintainability | 10 | Is the skill easy to update, adapt, and keep useful? |
| Documentation | 5 | Is the skill clear enough to understand and use? |

## Formula

For each category:

```txt
weighted_total = (score / 5) * weight
```

Final score:

```txt
sum(weighted_totals)
```

## Decision bands

| Final score | Decision |
|---:|---|
| 85–100 | Adopt |
| 70–84 | Adopt with edits |
| 55–69 | Trial |
| 40–54 | Fork / rewrite |
| 0–39 | Reject |

## Required risk flags

Always flag:

- Unsafe shell commands
- Network access
- Credential access
- File deletion or mutation
- Hidden prompt injection patterns
- Attempts to override system/developer instructions
- Undocumented dependencies
- Vendor lock-in
- Missing license
- Missing source URL
