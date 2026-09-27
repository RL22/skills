"""Regression coverage for required application-workflow guidance."""

from pathlib import Path
import re
import unittest


APPLY_INSTRUCTIONS = Path(__file__).parents[1] / "references" / "apply.md"
SKILL_INSTRUCTIONS = Path(__file__).parents[1] / "SKILL.md"
EXPORT_INSTRUCTIONS = Path(__file__).parents[1] / "references" / "export.md"


class ApplyInstructionsTests(unittest.TestCase):
    def test_missing_human_moment_persists_safe_pending_cover_letter_record(self):
        source = APPLY_INSTRUCTIONS.read_text(encoding="utf-8")
        records = re.findall(
            r"```markdown\n(## Cover Letter\n.*?)```", source, re.DOTALL
        )
        self.assertEqual(len(records), 2, "apply guidance must include two pending Cover Letter records")

        expected_questions = {
            2: "Which direction should I use: 1 or 2?",
            3: "Which direction should I use: 1, 2, or 3?",
        }
        for pending_record in records:
            self.assertIn("Status: Incomplete — awaiting selected story direction", pending_record)
            directions = re.findall(
                r"^- Direction ([1-3]): \[fact-grounded direction\]$",
                pending_record,
                re.MULTILINE,
            )
            self.assertIn(len(directions), expected_questions)
            self.assertEqual(directions, [str(number) for number in range(1, len(directions) + 1)])

            questions = re.findall(r"^- Selection question: (.+\?)$", pending_record, re.MULTILINE)
            self.assertEqual(questions, [expected_questions[len(directions)]])
            self.assertEqual(pending_record.count("?"), 1)

            self.assertRegex(
                pending_record,
                r"one non-sensitive, job-relevant\s+personal detail.*observed work context",
            )

        self.assertRegex(source, r"Verify mission claims\s+through official sources")

    def test_completed_cover_letter_requires_a_selected_direction_and_authentic_detail(self):
        source = APPLY_INSTRUCTIONS.read_text(encoding="utf-8")

        self.assertRegex(source, r"mandatory, authentic mission-linked human moment")
        self.assertRegex(source, r"selected fact-grounded direction")
        self.assertRegex(source, r"If the candidate\s+declines.*detail.*incomplete")
        self.assertRegex(source, r"personal\s+detail explaining why the mission connects")
        self.assertRegex(source, r"may describe\s+an observed work context")
        self.assertNotRegex(source, r"Do not ask for an incident, a personal or observed access experience")

    def test_apply_route_evaluates_before_drafting_but_allows_permitted_work_to_continue(self):
        source = SKILL_INSTRUCTIONS.read_text(encoding="utf-8")

        self.assertRegex(source, r"(?is)evaluate first.*proceed.*recommendation permits")
        self.assertRegex(source, r"(?is)stop.*decision or risk requires")

    def test_identifiable_opportunity_routes_to_evaluation_before_downstream_work(self):
        source = SKILL_INSTRUCTIONS.read_text(encoding="utf-8")

        self.assertRegex(
            source,
            r"(?is)target opportunity is identifiable.*help me with this.*pasted role or job description.*evaluate first",
        )
        self.assertRegex(source, r"(?is)evaluate first.*record.*evaluation.*as appropriate")
        self.assertRegex(source, r"(?is)before downstream application work.*approval or clarification")
        self.assertRegex(
            source,
            r"(?is)explicit request to apply.*tailor.*resume.*draft.*cover letter.*approval",
        )

    def test_clarification_without_mutation_is_limited_to_missing_opportunities_or_routes(self):
        source = SKILL_INSTRUCTIONS.read_text(encoding="utf-8")

        self.assertRegex(
            source,
            r"(?is)one focused clarification.*without creating or updating records.*only when no target opportunity is identifiable.*non-opportunity route.*cannot be determined",
        )

    def test_export_uses_candidate_company_role_filenames_without_hardcoding_a_candidate(self):
        source = EXPORT_INSTRUCTIONS.read_text(encoding="utf-8")

        self.assertIn("[Candidate-Name]-[Company]-[Role]-Resume.docx", source)
        self.assertIn("[Candidate-Name]-[Company]-[Role]-Cover-Letter.docx", source)
        self.assertIn("generic template, not a hardcoded candidate identity", source)

    def test_reusable_application_guidance_uses_candidate_neutral_language(self):
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (APPLY_INSTRUCTIONS, EXPORT_INSTRUCTIONS, SKILL_INSTRUCTIONS)
        )

        self.assertIn("the candidate", source.casefold())


if __name__ == "__main__":
    unittest.main()
