# SIFT Evaluation Process

SIFT means **Skill Inspection & Fit Testing**.

## Process Steps

When evaluating a candidate skill, follow these steps:

1. **Identify**: Identify the candidate skill source or folder.
2. **Profile**: Create or infer a lightweight user profile. A skill is only good relative to a user, workflow, agent stack, and risk profile. Use `assets/user-profile.md` as the template. If user details are missing, make reasonable assumptions and clearly list them.
3. **Inspect Structure**: Inspect the skill structure.
4. **Review**: Review `SKILL.md` frontmatter and core instructions.
5. **Check Assets**: Check optional `scripts/`, `references/`, and `assets/`.
6. **Score**: Score the skill using the SkillFit scorecard (`references/skillfit-scorecard.md`).
7. **Decide**: Recommend one decision:
   - Adopt
   - Adopt with edits
   - Trial
   - Fork / rewrite
   - Reject
8. **Report**: Produce an evaluation report using `assets/evaluation-report.md`.

## SIFT Dimensions

| Letter | Dimension | Core Question |
|---|---|---|
| **S** | Suitability | Does this skill solve a real recurring workflow for this user? |
| **I** | Interoperability | Can this skill work across the user’s agent stack? |
| **F** | Fidelity | Does this skill produce reliable, high-quality outputs? |
| **T** | Trust | Is this skill safe, inspectable, and maintainable? |
