"""Behavioral tests for application validation."""

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "validate_application.py"
FIXTURES_DIRECTORY = Path(__file__).parent / "fixtures"


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_application", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ValidateApplicationTests(unittest.TestCase):
    def test_role_records_do_not_consume_following_lines_as_components(self):
        validator = load_validator_module()
        malformed_multiline_heading = (
            "### Senior Web Developer | Example Corp\n"
            "continued employment note | October 2016–February 2020\n"
        )

        self.assertEqual([], validator._role_records(malformed_multiline_heading))
        self.assertEqual(
            [], validator._malformed_role_headings("### General Assembly | San Francisco, California\n")
        )

    def test_qualified_u_rejects_unresolved_qualifier_phrases_but_not_normal_prose(self):
        validator = load_validator_module()

        for value in ("U — TBD later", "U / unknown reason", "U: not provided yet"):
            with self.subTest(value=value):
                self.assertTrue(validator._is_unresolved_value(value))
        self.assertFalse(validator._is_unresolved_value("TBC Bank", label="Company"))
        for value in ("To do more for users is the goal",):
            with self.subTest(value=value):
                self.assertFalse(validator._is_unresolved_value(value))

    def test_direct_workflow_placeholders_require_a_workflow_qualifier(self):
        validator = load_validator_module()

        for value in (
            "TBD after confirmation", "TBC pending review", "TODO later",
            "To do once approved", "To be confirmed after the interview",
        ):
            with self.subTest(value=value):
                self.assertTrue(validator._is_unresolved_value(value))
        self.assertFalse(validator._is_unresolved_value("TBC Bank", label="Company"))
        for value in ("To do more for users is the goal",):
            with self.subTest(value=value):
                self.assertFalse(validator._is_unresolved_value(value))

    def test_direct_placeholder_markers_and_workflow_verbs_handle_punctuation_safely(self):
        validator = load_validator_module()

        for value in (
            "TODO: fix the cover letter", "TBD (pending review)", "TBD; pending review",
            "TBC: pending review", "TBC; awaiting approval",
            "To be discussed after review", "To be finalized once the panel decides",
            "To be approved after the interview",
        ):
            with self.subTest(value=value):
                self.assertTrue(validator._is_unresolved_value(value))
        self.assertFalse(validator._is_unresolved_value("TBC Bank", label="Company"))
        for value in ("To do more for users is the goal",):
            with self.subTest(value=value):
                self.assertFalse(validator._is_unresolved_value(value))

    def test_leading_markers_are_unresolved_except_for_credible_company_names(self):
        validator = load_validator_module()

        for value in (
            "TBD", "TODO", "TBC", "TODO revise the cover letter",
            "TODO complete the application", "TBD compensation", "TBD role",
            "TBC interview date", "TBC location",
        ):
            with self.subTest(value=value):
                self.assertTrue(validator._is_unresolved_value(value))
        for value in ("TBD Health", "TODO Group", "TBC.com", "TBC, Inc.", "TBC Bank"):
            with self.subTest(value=value):
                self.assertFalse(validator._is_unresolved_value(value, label="Company"))
                self.assertTrue(validator._is_unresolved_value(value, label="Next action"))
        for value in ("TBD compensation", "TBD role", "TBC interview date", "TBC location"):
            with self.subTest(company_value=value):
                self.assertTrue(validator._is_unresolved_value(value, label="Company"))

    def test_company_marker_names_require_a_complete_proper_name_or_domain(self):
        validator = load_validator_module()

        for value in (
            "TBD Health", "TBD Labs", "TODO Group", "TODO Studios",
            "TBC Bank", "TBC LLC", "TBC Ltd.", "TBC Corporation",
            "TBC, Inc.", "TBC.com", "TBC.ai",
        ):
            with self.subTest(credible_company=value):
                self.assertFalse(validator._is_unresolved_value(value, label="Company"))

        for value in (
            "TBD Health benefits", "TODO Group interview", "TBC Bank details",
            "TBC, Inc. compensation", "TBC.com salary",
        ):
            with self.subTest(missing_company=value):
                self.assertTrue(validator._is_unresolved_value(value, label="Company"))

    def test_company_marker_names_allow_credible_brand_forms_but_reject_descriptors_regardless_of_case(self):
        validator = load_validator_module()

        for value in ("TBD 3M", "TODO eBay", "TBC monday.com"):
            with self.subTest(credible_company=value):
                self.assertFalse(validator._is_unresolved_value(value, label="Company"))

        for value in ("TBD Health Benefits", "TBC Bank Details", "TODO Employer Name"):
            with self.subTest(missing_company=value):
                self.assertTrue(validator._is_unresolved_value(value, label="Company"))

    def test_company_marker_exception_requires_one_complete_brand_shape(self):
        validator = load_validator_module()

        for value in (
            "TBD Health", "TODO Ventures", "TBC Technologies", "TBD Co.",
            "TODO, Inc.", "TBC LLC", "TBD example.com", "TODO 3M", "TBC eBay",
        ):
            with self.subTest(credible_company=value):
                self.assertFalse(validator._is_unresolved_value(value, label="Company"))

        for value in (
            "TBD after confirmation", "TODO pending review", "TBC awaiting review",
            "TODO revise the cover letter", "TBD fix the application",
            "TBC complete instructions", "TBD unknown", "TODO to be confirmed",
            "TBC organization", "TBD client", "TODO business", "TBC firm", "TBD account",
            "TBC Bank Details", "TODO eBay interview", "TBD 3M role",
        ):
            with self.subTest(unresolved_company=value):
                self.assertTrue(validator._is_unresolved_value(value, label="Company"))

    def test_company_marker_grammar_rejects_generic_labels_but_allows_distinctive_multiword_brands(self):
        validator = load_validator_module()

        for value in (
            "TBD Company", "TODO Company", "TBC Agency", "TBD Services", "TODO Consulting",
        ):
            with self.subTest(generic_company=value):
                self.assertTrue(validator._is_unresolved_value(value, label="Company"))

        for value in (
            "TBD General Assembly", "TBC Acme Labs", "TODO Foo Bank", "TBC Health Systems",
            "TBD OpenAI",
        ):
            with self.subTest(credible_company=value):
                self.assertFalse(validator._is_unresolved_value(value, label="Company"))

        for value in ("TBD General Assembly role", "TBC Acme Labs interview"):
            with self.subTest(missing_descriptor=value):
                self.assertTrue(validator._is_unresolved_value(value, label="Company"))

    def test_to_be_completion_markers_allow_optional_punctuation(self):
        validator = load_validator_module()

        for value in (
            "To be updated after review",
            "To be verified after the user responds with details",
            "To be (confirmed) after review",
            "To be clarified after the hiring manager replies",
            "To be added once the team approves it",
            "To be filled in later",
            "To be revised after review",
        ):
            with self.subTest(value=value):
                self.assertTrue(validator._is_unresolved_value(value))
        self.assertFalse(validator._is_unresolved_value("To Be Coffee", label="Company"))

    def test_passive_to_be_and_deferred_to_do_placeholders_do_not_require_extra_context(self):
        validator = load_validator_module()

        for value in (
            "To be confirmed", "To be updated.", "To be discussed!",
            "To be finalized", "To be completed", "To be decided", "To be scheduled",
            "To be submitted", "To be added", "To be clarified", "To be filled",
            "To be revised", "To be provided", "To be verified", "To be determined",
            "To be supplied", "To be reviewed", "To be resolved", "To be defined",
            "To be selected", "To be chosen",
            "To do next week", "To do later", "To do after review",
            "To do before submission", "To do when approved",
        ):
            with self.subTest(value=value):
                self.assertTrue(validator._is_unresolved_value(value))

        self.assertFalse(validator._is_unresolved_value("To do more for users"))

    def test_workflow_completion_and_temporal_deferral_detection_uses_the_leading_grammar(self):
        validator = load_validator_module()

        for value in (
            "To be done", "To be fixed", "To be sent", "To be written",
            "To be drafted", "To be assigned", "To be arranged", "To be contacted",
        ):
            with self.subTest(passive_completion=value):
                self.assertTrue(validator._is_unresolved_value(value))

        for value in (
            "To do tomorrow", "To do soon", "To do later", "To do next week",
            "To do by Friday", "To do before submission", "To do after review",
            "To do when approved", "To do once confirmed", "To do ASAP",
        ):
            with self.subTest(temporal_deferral=value):
                self.assertTrue(validator._is_unresolved_value(value))

        self.assertFalse(validator._is_unresolved_value("To do more for users next week"))

    def test_workflow_grammar_catches_broad_passives_and_immediate_to_do_deferrals(self):
        validator = load_validator_module()

        for value in (
            "To be addressed", "To be checked", "To be answered", "To be researched",
            "To be done", "To be sent", "To be written",
        ):
            with self.subTest(passive_completion=value):
                self.assertTrue(validator._is_unresolved_value(value))

        for value in ("To do on Monday", "To do in August", "To do this week"):
            with self.subTest(temporal_deferral=value):
                self.assertTrue(validator._is_unresolved_value(value))

        self.assertFalse(validator._is_unresolved_value("To do more for users"))

    def test_workflow_grammar_uses_explicit_completion_verbs_and_temporal_token_phrases(self):
        validator = load_validator_module()

        for value in (
            "To be found", "To be set", "To be paid", "To be given", "To be held",
            "To be left", "To be done", "To be sent", "To be written",
        ):
            with self.subTest(completion_verb=value):
                self.assertTrue(validator._is_unresolved_value(value))

        for value in (
            "To do Monday", "To do tonight", "To do during August", "To do within a week",
            "To do at the interview", "To do on Friday", "To do in August",
        ):
            with self.subTest(temporal_deferral=value):
                self.assertTrue(validator._is_unresolved_value(value))

        for value in (
            "To be excited about helping users is meaningful",
            "To be focused on accessibility is important",
            "To do this well requires care",
            "To do in-depth research before applying",
            "To do more for users next week",
        ):
            with self.subTest(ordinary_prose=value):
                self.assertFalse(validator._is_unresolved_value(value))

        self.assertFalse(validator._is_unresolved_value("To Be United", label="Company"))

    def test_qualified_u_accepts_punctuation_separators_without_rejecting_words(self):
        validator = load_validator_module()

        for value in ("U; pending", "U!unknown", "U=missing", "U… unavailable"):
            with self.subTest(value=value):
                self.assertTrue(validator._is_unresolved_value(value))
        for value in ("U.S. accessibility", "U-Haul", "U-shaped forms"):
            with self.subTest(value=value):
                self.assertFalse(validator._is_unresolved_value(value))

    def test_ready_application_rejects_token_sized_resume_human_moment_and_log_details(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace("Led product and web initiatives.", "- abc")
        source = source.replace("Built web applications for customers.", "- xx")
        source = source.replace(
            "User-verified — I saw a community team lose time to an inaccessible web form.",
            "User-verified — abc",
        )
        source = source.replace(
            "| 2026-07-31 | Prepared application materials | Candidate | Materials ready for review | Confirm submission decision |",
            "| 2026-07-31 | abc | Candidate | xx | abc |",
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "token-sized-details.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        errors = "\n".join(result["errors"])
        self.assertIn("Ready application has an empty Tailored Resume", errors)
        self.assertIn("non-placeholder user-verified Human moment", errors)
        self.assertIn("Ready application has an empty Application Log", errors)

    def test_valid_application_has_no_errors(self):
        validator = load_validator_module()

        result = validator.validate_application(
            FIXTURES_DIRECTORY / "valid_acme_web_lead.md",
            FIXTURES_DIRECTORY / "valid_profile.md",
        )

        self.assertEqual([], result["errors"])

    def test_ready_application_rejects_unknown_employer_and_role(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace(
            "Senior Web Developer | Example Corp | October 2016–February 2020",
            "Chief Wizard | Fabricated LLC | January 1990–Present",
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertTrue(any("not in canonical employment history" in error for error in result["errors"]))

    def test_ready_application_rejects_role_records_at_any_heading_level(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            for level in (2, 4):
                with self.subTest(heading_level=level):
                    application = Path(directory) / f"role-level-{level}.md"
                    application.write_text(
                        source.replace(
                            "### Senior Web Developer | Example Corp | October 2016–February 2020",
                            f"{'#' * level} Chief Wizard | Fabricated LLC | January 1990–Present",
                        ),
                        encoding="utf-8",
                    )
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )
                    self.assertTrue(
                        any("not in canonical employment history" in error for error in result["errors"])
                    )

    def test_non_provisional_score_must_be_an_integer_in_range(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace("75–95 provisional; midpoint 85", "banana")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn(
            "Opportunity score must use an approved exact or provisional format",
            result["errors"],
        )

    def test_ready_application_rejects_incomplete_cover_letter_and_empty_log(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = re.sub(
            r"(?ms)^## Cover Letter\n.*?(?=^## Tailored Resume)",
            "## Cover Letter\n\n- Status: Incomplete — awaiting selected story direction\n\n",
            source,
        )
        source = re.sub(
            r"(?ms)^## Application Log\n.*\Z",
            "## Application Log\n\n| Date | Action |\n| --- | --- |\n",
            source,
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        errors = "\n".join(result["errors"])
        self.assertIn("Ready application has incomplete Cover Letter", errors)
        self.assertIn("Ready application has an empty Application Log", errors)

    def test_ready_application_requires_a_user_verified_human_moment_record(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        cases = {
            "generic": source.replace(
                "- Human moment: User-verified — I saw a community team lose time to an inaccessible web form.\n\n",
                "",
            ),
            "selected-direction-only": source.replace(
                "- Human moment: User-verified — I saw a community team lose time to an inaccessible web form.\n\n",
                "",
            ).replace("Dear Acme hiring team,",
                "- Status: Complete — selected direction 1\n\nDear Acme hiring team,",
            ),
            "placeholder": source.replace(
                "User-verified — I saw a community team lose time to an inaccessible web form.",
                "User-verified — {{user-verified detail}}",
            ),
        }

        with tempfile.TemporaryDirectory() as directory:
            for name, application_text in cases.items():
                with self.subTest(letter=name):
                    application = Path(directory) / f"{name}.md"
                    application.write_text(application_text, encoding="utf-8")
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )
                    self.assertIn(
                        "Ready application requires a non-placeholder user-verified Human moment record",
                        result["errors"],
                    )

    def test_ready_application_accepts_an_explicit_user_verified_human_moment_record(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertEqual([], result["errors"])

    def test_ready_application_requires_human_moment_as_an_exact_list_record(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace(
            "- Human moment: User-verified — I saw a community team lose time to an inaccessible web form.",
            "Human moment: User-verified — I saw a community team lose time to an inaccessible web form.",
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn(
            "Ready application requires a non-placeholder user-verified Human moment record",
            result["errors"],
        )

    def test_ready_application_rejects_extended_human_moment_placeholder(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace(
            "User-verified — I saw a community team lose time to an inaccessible web form.",
            "User-verified — TBD after the user provides it",
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn(
            "Ready application requires a non-placeholder user-verified Human moment record",
            result["errors"],
        )

    def test_ready_application_rejects_direct_workflow_placeholders_in_each_required_context(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = {
            "structured-field": (
                source.replace(
                    "- Next action: Send tailored application to the hiring manager.",
                    "- Next action: TODO revise the cover letter",
                ),
                "Ready application has unresolved placeholder in Next action",
            ),
            "follow-up-date": (
                source.replace("- Follow-up date: 2026-08-07", "- Follow-up date: TBD confirm timing"),
                "Ready application has unresolved placeholder in Follow-up date",
            ),
            "resume": (
                re.sub(
                    r"(?ms)^## Tailored Resume\n.*?(?=^## Application Log)",
                    "## Tailored Resume\n\nTODO complete the tailored resume\n\n",
                    source,
                ),
                "Ready application has an empty Tailored Resume",
            ),
            "log": (
                source.replace(
                    "Prepared application materials", "TBC update after review",
                ),
                "Ready application has an empty Application Log",
            ),
            "human-attestation": (
                source.replace(
                    "User-verified — I saw a community team lose time to an inaccessible web form.",
                    "User-verified — TODO complete the attestation",
                ),
                "Ready application requires a non-placeholder user-verified Human moment record",
            ),
        }

        with tempfile.TemporaryDirectory() as directory:
            for name, (application_text, expected_error) in cases.items():
                with self.subTest(context=name):
                    application = Path(directory) / f"workflow-{name}.md"
                    application.write_text(application_text, encoding="utf-8")
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )
                    self.assertIn(expected_error, result["errors"])

    def test_ready_application_limits_marker_like_company_names_to_credible_signals(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            for index, company in enumerate(("TBD Health", "TODO Group", "TBC Bank", "TBC.com", "TBC, Inc.")):
                with self.subTest(credible_company=company):
                    application = Path(directory) / f"credible-company-{index}.md"
                    application.write_text(
                        source.replace("- Company: Acme", f"- Company: {company}"), encoding="utf-8"
                    )
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )
                    self.assertNotIn("Ready application has unresolved placeholder in Company", result["errors"])

            for index, company in enumerate(("TBD compensation", "TBD role", "TBC interview date", "TBC location")):
                with self.subTest(missing_company=company):
                    application = Path(directory) / f"missing-company-{index}.md"
                    application.write_text(
                        source.replace("- Company: Acme", f"- Company: {company}"), encoding="utf-8"
                    )
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )
                    self.assertIn("Ready application has unresolved placeholder in Company", result["errors"])

    def test_ready_application_rejects_structured_unresolved_metadata_and_cover_letter_values(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = {
            "follow-up-date": (
                source.replace("- Follow-up date: 2026-08-07", "- Follow-up date: TBD"),
                "Follow-up date",
            ),
            "cover-letter-status": (
                source.replace(
                    "- Human moment: User-verified — I saw a community team lose time to an inaccessible web form.",
                    "- Status: TBD\n- Human moment: User-verified — I saw a community team lose time to an inaccessible web form.",
                ),
                "Status",
            ),
        }

        with tempfile.TemporaryDirectory() as directory:
            for name, (application_text, label) in cases.items():
                with self.subTest(value=name):
                    application = Path(directory) / f"{name}.md"
                    application.write_text(application_text, encoding="utf-8")
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )

                    self.assertIn(
                        f"Ready application has unresolved placeholder in {label}", result["errors"]
                    )

    def test_ready_application_rejects_u_and_other_unresolved_required_metadata(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = {
            "company": ("- Company: Acme", "- Company: U", "Company"),
            "target-role": ("- Target role: Web Lead", "- Target role: TBD", "Target role"),
            "next-action": (
                "- Next action: Send tailored application to the hiring manager.",
                "- Next action: U",
                "Next action",
            ),
        }

        with tempfile.TemporaryDirectory() as directory:
            for name, (old, new, label) in cases.items():
                with self.subTest(value=name):
                    application = Path(directory) / f"{name}.md"
                    application.write_text(source.replace(old, new), encoding="utf-8")
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )

                    self.assertIn(
                        f"Ready application has unresolved placeholder in {label}", result["errors"]
                    )

    def test_ready_application_rejects_placeholder_only_human_moment_attestations(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = ("U", "TBD", "N/A", "[user-verified detail]", "{{user-verified detail}}")

        with tempfile.TemporaryDirectory() as directory:
            for index, placeholder in enumerate(cases):
                with self.subTest(placeholder=placeholder):
                    application = Path(directory) / f"human-moment-{index}.md"
                    application.write_text(
                        re.sub(
                            r"(?m)^- Human moment: User-verified — .+$",
                            f"- Human moment: User-verified — {placeholder}",
                            source,
                        ),
                        encoding="utf-8",
                    )
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )

                    self.assertIn(
                        "Ready application requires a non-placeholder user-verified Human moment record",
                        result["errors"],
                    )

    def test_ready_application_rejects_normalized_placeholder_bypasses(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = {
            "company-non-provided": (
                source.replace("- Company: Acme", "- Company: U — not provided"),
                FIXTURES_DIRECTORY / "valid_profile.md",
                "Ready application has unresolved placeholder in Company",
            ),
            "company-punctuation": (
                source.replace("- Company: Acme", "- Company: -"),
                FIXTURES_DIRECTORY / "valid_profile.md",
                "Ready application has unresolved placeholder in Company",
            ),
            "follow-up-ellipsis": (
                source.replace("- Follow-up date: 2026-08-07", "- Follow-up date: ..."),
                FIXTURES_DIRECTORY / "valid_profile.md",
                "Ready application has unresolved placeholder in Follow-up date",
            ),
            "human-moment-non-provided": (
                source.replace(
                    "User-verified — I saw a community team lose time to an inaccessible web form.",
                    "User-verified — U — not provided",
                ),
                FIXTURES_DIRECTORY / "valid_profile.md",
                "Ready application requires a non-placeholder user-verified Human moment record",
            ),
            "human-moment-punctuation": (
                source.replace(
                    "User-verified — I saw a community team lose time to an inaccessible web form.",
                    "User-verified — -",
                ),
                FIXTURES_DIRECTORY / "valid_profile.md",
                "Ready application requires a non-placeholder user-verified Human moment record",
            ),
            "human-moment-placeholder": (
                source.replace(
                    "User-verified — I saw a community team lose time to an inaccessible web form.",
                    "User-verified — placeholder",
                ),
                FIXTURES_DIRECTORY / "valid_profile.md",
                "Ready application requires a non-placeholder user-verified Human moment record",
            ),
            "log-all-dashes": (
                source.replace(
                    "| 2026-07-31 | Prepared application materials | Candidate | Materials ready for review | Confirm submission decision |",
                    "| - | - | Candidate | - | - |",
                ),
                FIXTURES_DIRECTORY / "valid_profile.md",
                "Ready application has an empty Application Log",
            ),
            "log-all-ellipses": (
                source.replace(
                    "| 2026-07-31 | Prepared application materials | Candidate | Materials ready for review | Confirm submission decision |",
                    "| ... | ... | Candidate | ... | ... |",
                ),
                FIXTURES_DIRECTORY / "valid_profile.md",
                "Ready application has an empty Application Log",
            ),
            "resume-placeholder": (
                re.sub(
                    r"(?ms)^## Tailored Resume\n.*?(?=^## Application Log)",
                    "## Tailored Resume\n\nplaceholder\n\n",
                    source,
                ),
                FIXTURES_DIRECTORY / "valid_profile.md",
                "Ready application has an empty Tailored Resume",
            ),
            "resume-without-canonical-role": (
                re.sub(
                    r"(?ms)^## Tailored Resume\n.*?(?=^## Application Log)",
                    "## Tailored Resume\n\n### Summary\n\nExperienced web delivery leader.\n\n",
                    source,
                ),
                FIXTURES_DIRECTORY / "valid_profile.md",
                "Ready application requires at least one level-three canonical role record in Tailored Resume",
            ),
            "canonical-role-wrong-level": (
                source,
                Path(__file__).parent / "fixtures" / "profile_role_at_level_four.md",
                "Canonical Employment History has entries but no parseable role headings",
            ),
        }

        with tempfile.TemporaryDirectory() as directory:
            for name, (application_text, profile, expected_error) in cases.items():
                with self.subTest(case=name):
                    application = Path(directory) / f"{name}.md"
                    application.write_text(application_text, encoding="utf-8")
                    result = validator.validate_application(application, profile)
                    self.assertTrue(
                        any(expected_error in error for error in result["errors"]),
                        result["errors"],
                    )

    def test_ready_application_rejects_placeholder_application_log_cells(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = {
            "date": "U | Prepared application materials | Candidate | Materials ready for review | Confirm submission decision",
            "action": "2026-07-31 | TBD | Candidate | Materials ready for review | Confirm submission decision",
            "result": "2026-07-31 | Prepared application materials | Candidate | U | Confirm submission decision",
            "next-step": "2026-07-31 | Prepared application materials | Candidate | Materials ready for review | TBD",
        }

        with tempfile.TemporaryDirectory() as directory:
            for name, row in cases.items():
                with self.subTest(cell=name):
                    application = Path(directory) / f"log-{name}.md"
                    application.write_text(
                        re.sub(
                            r"(?m)^\| 2026-07-31 \|.*$", f"| {row} |", source
                        ),
                        encoding="utf-8",
                    )
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )

                    self.assertIn("Ready application has an empty Application Log", result["errors"])

    def test_ready_application_rejects_leading_u_placeholders_with_qualifiers(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = {
            "structured-field": (
                source.replace("- Company: Acme", "- Company: U — pending confirmation"),
                "Ready application has unresolved placeholder in Company",
            ),
            "log-cell": (
                source.replace(
                    "| 2026-07-31 | Prepared application materials | Candidate | Materials ready for review | Confirm submission decision |",
                    "| 2026-07-31 | U (unavailable) | Candidate | Materials ready for review | Confirm submission decision |",
                ),
                "Ready application has an empty Application Log",
            ),
            "human-moment": (
                source.replace(
                    "User-verified — I saw a community team lose time to an inaccessible web form.",
                    "User-verified — U - pending",
                ),
                "Ready application requires a non-placeholder user-verified Human moment record",
            ),
        }

        with tempfile.TemporaryDirectory() as directory:
            for name, (application_text, expected_error) in cases.items():
                with self.subTest(value=name):
                    application = Path(directory) / f"leading-u-{name}.md"
                    application.write_text(application_text, encoding="utf-8")
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )

                    self.assertIn(expected_error, result["errors"])

    def test_ready_application_rejects_compact_qualified_u_placeholders(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        compact_values = ("U—pending", "U-TBD", "U—unavailable", "U-pending")
        cases = {
            "structured-field": (
                lambda value: source.replace("- Company: Acme", f"- Company: {value}"),
                "Ready application has unresolved placeholder in Company",
            ),
            "log-cell": (
                lambda value: source.replace(
                    "| 2026-07-31 | Prepared application materials | Candidate | Materials ready for review | Confirm submission decision |",
                    f"| 2026-07-31 | {value} | Candidate | Materials ready for review | Confirm submission decision |",
                ),
                "Ready application has an empty Application Log",
            ),
            "human-moment": (
                lambda value: source.replace(
                    "User-verified — I saw a community team lose time to an inaccessible web form.",
                    f"User-verified — {value}",
                ),
                "Ready application requires a non-placeholder user-verified Human moment record",
            ),
        }

        with tempfile.TemporaryDirectory() as directory:
            for location, (build_application, expected_error) in cases.items():
                for value in compact_values:
                    with self.subTest(location=location, value=value):
                        application = Path(directory) / f"compact-u-{location}-{value}.md"
                        application.write_text(build_application(value), encoding="utf-8")
                        result = validator.validate_application(
                            application, FIXTURES_DIRECTORY / "valid_profile.md"
                        )

                        self.assertIn(expected_error, result["errors"])

    def test_ready_application_allows_hyphenated_u_words(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace("- Company: Acme", "- Company: U-Haul")
        source = source.replace(
            "| 2026-07-31 | Prepared application materials | Candidate | Materials ready for review | Confirm submission decision |",
            "| 2026-07-31 | Unblocked application materials | Candidate | Materials ready for review | Confirm submission decision |",
        )
        source = source.replace(
            "User-verified — I saw a community team lose time to an inaccessible web form.",
            "User-verified — U-shaped forms motivated my accessibility work.",
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "legitimate-u-values.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertEqual([], result["errors"])

    def test_ready_application_rejects_empty_or_non_substantive_tailored_resume(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = ("", "- U\n", "### Summary\n\nTBD\n")

        with tempfile.TemporaryDirectory() as directory:
            for index, resume in enumerate(cases):
                with self.subTest(resume=resume):
                    application = Path(directory) / f"resume-{index}.md"
                    application.write_text(
                        re.sub(
                            r"(?ms)^## Tailored Resume\n.*?(?=^## Application Log)",
                            f"## Tailored Resume\n\n{resume}\n",
                            source,
                        ),
                        encoding="utf-8",
                    )
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )

                    self.assertIn("Ready application has an empty Tailored Resume", result["errors"])

    def test_role_records_must_use_level_three_headings_but_are_checked_at_every_level(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = {
            "matching-wrong-level": (
                "#### Senior Web Developer | Example Corp | October 2016–February 2020",
                "Tailored Resume role records must use level-three headings",
            ),
            "fabricated-wrong-level": (
                "#### Chief Wizard | Fabricated LLC | January 1990–Present",
                "Chief Wizard at fabricated llc is not in canonical employment history",
            ),
        }

        with tempfile.TemporaryDirectory() as directory:
            for name, (role, expected_error) in cases.items():
                with self.subTest(role=name):
                    application = Path(directory) / f"role-{name}.md"
                    application.write_text(
                        source.replace(
                            "### Senior Web Developer | Example Corp | October 2016–February 2020", role
                        ),
                        encoding="utf-8",
                    )
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )

                    self.assertIn(expected_error, result["errors"])

    def test_top_level_singleton_metadata_cannot_bypass_ready_validation(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = {
            "Status": source.replace("- Status: Ready", "- Status: Drafting\n- Status: Ready"),
            "Company": source.replace("- Company: Acme", "- Company: Acme\n- Company: Other Acme"),
            "Job URL": source.replace(
                "- Follow-up date: 2026-08-07",
                "- Follow-up date: 2026-08-07\n- Job URL: https://example.com/one\n- Job URL: https://example.com/two",
            ),
        }

        with tempfile.TemporaryDirectory() as directory:
            for label, application_text in cases.items():
                with self.subTest(field=label):
                    application = Path(directory) / f"singleton-{label.casefold().replace(' ', '-')}.md"
                    application.write_text(application_text, encoding="utf-8")
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )

                    self.assertIn(
                        f"top-level singleton metadata must appear exactly once: {label}",
                        result["errors"],
                    )

    def test_ready_application_allows_unresolved_words_in_ordinary_prose_and_unrecognized_lists(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace(
            "I would welcome the opportunity to lead your web work.",
            "I would not leave TBD items in the final application.\n\n- Note: TBD means the team's delivery process needs attention.",
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertEqual([], result["errors"])

    def test_ready_application_allows_ordinary_prose_with_incomplete_word(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace(
            "I would welcome the opportunity to lead your web work.",
            "I would welcome the opportunity to make an incomplete process more reliable.",
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertEqual([], result["errors"])

    def test_required_heading_must_be_a_level_two_heading(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace("## Application Log", "# Application Log")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn("required heading must use level two: Application Log", result["errors"])

    def test_duplicate_required_heading_at_the_wrong_level_is_rejected(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace("## Application Log", "# Application Log\n\n## Application Log")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn("required heading must use level two: Application Log", result["errors"])

    def test_duplicate_required_heading_at_the_correct_level_is_rejected(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace("## Application Log", "## Application Log\n\n## Application Log")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn("required heading must appear exactly once: Application Log", result["errors"])

    def test_fenced_fake_application_content_does_not_satisfy_validation(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(f"```markdown\n{source}\n```\n", encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn("missing required heading: Cover Letter", result["errors"])
        self.assertIn("missing required field: Status", result["errors"])

    def test_tab_indented_fake_closer_keeps_ready_content_inside_the_fence(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(f"```markdown\n\t```\n{source}\n```\n", encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn("missing required heading: Cover Letter", result["errors"])
        self.assertIn("missing required field: Status", result["errors"])

    def test_html_commented_metadata_and_headings_do_not_satisfy_requirements(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(f"<!--\n{source}\n-->\n", encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn("missing required field: Status", result["errors"])
        self.assertIn("missing required heading: Cover Letter", result["errors"])

    def test_ready_application_rejects_commented_substantive_sections(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = re.sub(
            r"(?ms)(^## Cover Letter\n)(.*?)(?=^## Tailored Resume)",
            r"\1<!--\n\2-->\n",
            source,
        )
        source = re.sub(
            r"(?ms)(^## Tailored Resume\n)(.*?)(?=^## Application Log)",
            r"\1<!--\n\2-->\n",
            source,
        )
        source = re.sub(r"(?ms)(^## Application Log\n)(.*)\Z", r"\1<!--\n\2-->\n", source)

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        errors = "\n".join(result["errors"])
        self.assertIn("Ready application has an empty Tailored Resume", errors)
        self.assertIn("non-placeholder user-verified Human moment", errors)
        self.assertIn("Ready application has an empty Application Log", errors)

    def test_html_commented_canonical_roles_do_not_become_facts(self):
        validator = load_validator_module()
        profile = (FIXTURES_DIRECTORY / "valid_profile.md").read_text(encoding="utf-8")
        profile = re.sub(
            r"(?ms)(## Canonical Employment History\n)(.*)\Z", r"\1<!--\n\2-->\n", profile
        )

        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "profile.md"
            profile_path.write_text(profile, encoding="utf-8")
            result = validator.validate_application(
                FIXTURES_DIRECTORY / "valid_acme_web_lead.md", profile_path
            )

        self.assertTrue(any("not in canonical employment history" in error for error in result["errors"]))

    def test_visible_content_adjacent_to_html_comments_still_parses(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace("- Company: Acme", "- Company: Acme<!-- internal -->")
        source = source.replace("## Cover Letter", "<!-- old draft -->\n## Cover<!-- internal --> Letter<!-- reviewed -->")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertEqual([], result["errors"])

    def test_inline_html_comments_are_semantically_deleted_without_changing_line_endings(self):
        validator = load_validator_module()
        markdown = "Ac<!-- internal -->me\r\n## Cover<!-- old\nheading --> Letter\n"

        visible = validator._visible_markdown(markdown)
        self.assertEqual(
            "Acme\r\n## Cover\n Letter\n",
            validator._semantic_text(visible),
        )
        self.assertIn(validator._COMMENT_BOUNDARY, visible)

    def test_required_heading_with_an_inline_html_comment_is_recognized(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace("## Cover Letter", "## Cover<!-- internal --> Letter")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertNotIn("missing required heading: Cover Letter", result["errors"])

    def test_comments_cannot_manufacture_required_heading_syntax(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        for fabricated in ("#<!-- --># Cover Letter", "##<!-- --> Cover Letter"):
            with self.subTest(fabricated=fabricated), tempfile.TemporaryDirectory() as directory:
                application = Path(directory) / "application.md"
                application.write_text(source.replace("## Cover Letter", fabricated), encoding="utf-8")
                result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

            self.assertIn("missing required heading: Cover Letter", result["errors"])

    def test_comment_before_line_start_heading_cannot_manufacture_structure(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace("## Cover Letter", "<!-- internal -->## Cover Letter")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn("missing required heading: Cover Letter", result["errors"])

    def test_comment_cannot_manufacture_user_verified_list_field(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace("- Human moment: User-verified", "-<!-- internal --> Human moment: User-verified")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertTrue(any("Human moment" in error for error in result["errors"]))

    def test_comment_before_indented_list_field_cannot_manufacture_structure(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace("- Human moment: User-verified", "  <!-- internal -->- Human moment: User-verified")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertTrue(any("Human moment" in error for error in result["errors"]))

    def test_comment_before_table_marker_cannot_manufacture_log_row(self):
        validator = load_validator_module()
        table = (
            "<!-- internal -->| Date | Action | Result | Next step |\n"
            "| --- | --- | --- | --- |\n"
            "| 2026-07-31 | Submitted application | Confirmation received | Await reply |\n"
        )

        self.assertFalse(validator._has_log_entry(validator._visible_markdown(table)))

    def test_application_log_table_structure_is_validated_before_comment_boundaries_are_semantic(self):
        validator = load_validator_module()
        header = "| Date | Action | Result | Next step |\n"
        entry = "| 2026-07-31 | Submitted application | Confirmation received | Await reply |\n"

        for delimiter in (
            "|<!-- gap --> --- | --- | --- | --- |\n",
            "| --<!-- gap -->- | --- | --- | --- |\n",
            "| --- <!-- gap -->| --- | --- | --- |\n",
        ):
            with self.subTest(delimiter=delimiter):
                self.assertFalse(
                    validator._has_log_entry(validator._visible_markdown(header + delimiter + entry))
                )

        semantic_entry = (
            "| 2026-07-31 | Sub<!-- reviewed -->mitted application | "
            "Confirmation received | Await reply |\n"
        )
        self.assertTrue(
            validator._has_log_entry(
                validator._visible_markdown(header + "| --- | --- | --- | --- |\n" + semantic_entry)
            )
        )

    def test_inline_comment_text_remains_semantic_in_profile_role_parsing(self):
        validator = load_validator_module()
        profile = (FIXTURES_DIRECTORY / "valid_profile.md").read_text(encoding="utf-8")
        profile = profile.replace("Founder | Example Studio", "Fou<!-- internal -->nder | Example Studio")

        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "profile.md"
            profile_path.write_text(profile, encoding="utf-8")
            result = validator.validate_application(
                FIXTURES_DIRECTORY / "valid_acme_web_lead.md", profile_path
            )

        self.assertEqual([], result["errors"])

    def test_reserved_private_use_code_points_are_rejected_in_applications_without_leaking_markers(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        for code_point in ("\ue000", "\ue001", "\U000f0000", "\U0010fffd"):
            with self.subTest(code_point=ord(code_point)):
                with tempfile.TemporaryDirectory() as directory:
                    application = Path(directory) / "application.md"
                    application.write_text(source.replace("## Cover Letter", f"## {code_point}Cover Letter"), encoding="utf-8")
                    result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

                self.assertIn("application contains reserved Unicode private-use code point", result["errors"])
                self.assertNotIn(code_point, "\n".join(result["errors"]))

    def test_reserved_private_use_code_points_are_rejected_in_canonical_profiles_without_leaking_markers(self):
        validator = load_validator_module()
        profile = (FIXTURES_DIRECTORY / "valid_profile.md").read_text(encoding="utf-8")

        for code_point in ("\ue000", "\ue001"):
            with self.subTest(code_point=ord(code_point)):
                with tempfile.TemporaryDirectory() as directory:
                    profile_path = Path(directory) / "profile.md"
                    profile_path.write_text(
                        profile.replace("Senior Web Developer | Example Corp", f"{code_point}Senior Web Developer | Example Corp"),
                        encoding="utf-8",
                    )
                    result = validator.validate_application(
                        FIXTURES_DIRECTORY / "valid_acme_web_lead.md", profile_path
                    )

                self.assertIn("canonical profile contains reserved Unicode private-use code point", result["errors"])
                self.assertNotIn(code_point, "\n".join(result["errors"]))

    def test_multiline_and_unclosed_html_comments_are_semantically_deleted_without_changing_line_endings(self):
        validator = load_validator_module()
        markdown = (
            "visible before\n"
            "<!-- hidden\n```markdown\n## Fake Heading\n```\n-->\n"
            "visible after\n"
            "<!-- hidden through end\n## Also Fake\n"
        )

        visible = validator._visible_markdown(markdown)
        self.assertEqual(
            "visible before\n\n\n\n\n\nvisible after\n\n\n",
            validator._semantic_text(visible),
        )

    def test_fenced_literal_unclosed_comment_does_not_hide_later_markdown(self):
        validator = load_validator_module()
        markdown = "```markdown\n<!-- literal code\n```\n## Visible\n"

        visible = validator._visible_markdown(markdown)

        self.assertEqual(" " * 11 + "\n" + " " * 17 + "\n" + " " * 3 + "\n## Visible\n", visible)

    def test_unclosed_fence_is_blank_through_end_of_file(self):
        validator = load_validator_module()
        markdown = "before\n~~~python\n## Literal through EOF"

        visible = validator._visible_markdown(markdown)

        self.assertEqual("before\n" + " " * 9 + "\n" + " " * 22, visible)

    def test_fence_indentation_accepts_only_zero_to_three_ascii_spaces(self):
        validator = load_validator_module()

        for fence in ("```", "~~~"):
            for indent in ("", " ", "  ", "   "):
                with self.subTest(fence=fence, indent=repr(indent)):
                    markdown = f"{indent}{fence}markdown\n## Literal\n{indent}{fence}\n## Visible\n"
                    visible = validator._visible_markdown(markdown)

                    self.assertNotIn("## Literal", visible)
                    self.assertTrue(visible.endswith("## Visible\n"))

        for invalid_indent in ("\t", "\f", "\v", "\u00a0"):
            with self.subTest(invalid_opening_indent=repr(invalid_indent)):
                markdown = f"{invalid_indent}```markdown\n## Visible\n"

                self.assertEqual(markdown, validator._visible_markdown(markdown))

            with self.subTest(invalid_closing_indent=repr(invalid_indent)):
                markdown = (
                    "```markdown\n"
                    "## Hidden before fake closer\n"
                    f"{invalid_indent}```\n"
                    "## Hidden after fake closer\n"
                    "```\n"
                    "## Visible\n"
                )
                visible = validator._visible_markdown(markdown)

                self.assertNotIn("## Hidden before fake closer", visible)
                self.assertNotIn("## Hidden after fake closer", visible)
                self.assertTrue(visible.endswith("## Visible\n"))

    def test_fence_closer_allows_only_ascii_space_or_tab_trailing_whitespace(self):
        validator = load_validator_module()

        for trailing_whitespace in ("", " ", "\t", " \t "):
            with self.subTest(valid_trailing_whitespace=repr(trailing_whitespace)):
                markdown = f"```\r\n## Hidden\r\n```{trailing_whitespace}\r\n## Visible\r\n"
                visible = validator._visible_markdown(markdown)

                self.assertNotIn("## Hidden", visible)
                self.assertTrue(visible.endswith("## Visible\r\n"))
                self.assertEqual(markdown.count("\r\n"), visible.count("\r\n"))

        for invalid_trailing_whitespace in ("\f", "\v", "\u00a0"):
            with self.subTest(invalid_trailing_whitespace=repr(invalid_trailing_whitespace)):
                markdown = (
                    "```\n"
                    "## Hidden before fake closer\n"
                    f"```{invalid_trailing_whitespace}\n"
                    "## Hidden after fake closer\n"
                    "```\n"
                    "## Visible\n"
                )
                visible = validator._visible_markdown(markdown)

                self.assertNotIn("## Hidden before fake closer", visible)
                self.assertNotIn("## Hidden after fake closer", visible)
                self.assertTrue(visible.endswith("## Visible\n"))

    def test_comment_fences_are_literal_and_crlf_boundaries_are_preserved(self):
        validator = load_validator_module()
        markdown = "<!--\r\n```markdown\r\n## Fake\r\n```\r\n-->\r\n## Visible\r\n"

        visible = validator._visible_markdown(markdown)

        self.assertEqual(markdown.count("\r\n"), visible.count("\r\n"))
        self.assertEqual(markdown.count("\n"), visible.count("\n"))
        self.assertTrue(visible.endswith("## Visible\r\n"))
        self.assertNotIn("## Fake", visible)

    def test_composition_aware_scanner_is_used_for_application_and_profile(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        profile = (FIXTURES_DIRECTORY / "valid_profile.md").read_text(encoding="utf-8")
        literal_code = "```markdown\n<!-- unclosed literal comment\n```\n"

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            profile_path = Path(directory) / "profile.md"
            application.write_text(literal_code + source, encoding="utf-8")
            profile_path.write_text(literal_code + profile, encoding="utf-8")
            result = validator.validate_application(application, profile_path)

        self.assertEqual([], result["errors"])

    def test_composition_aware_scanner_is_used_for_duplicate_parsing(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        literal_code = "```markdown\n<!-- unclosed literal comment\n```\n"

        with tempfile.TemporaryDirectory() as directory:
            applications = Path(directory)
            for name in ("one.md", "two.md"):
                (applications / name).write_text(literal_code + source, encoding="utf-8")

            duplicates = validator.find_duplicates(applications)

        self.assertIn("acme | web lead", duplicates)

    def test_fenced_html_comments_cannot_create_visible_structure(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = "```markdown\n<!--\n## Fake Heading\n-->\n```\n" + source

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertEqual([], result["errors"])

    def test_later_real_resume_section_cannot_hide_a_fabricated_role(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source += "\n## Tailored Resume\n\n### Chief Wizard | Fabricated LLC | January 1990–Present\n"

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertTrue(any("not in canonical employment history" in error for error in result["errors"]))

    def test_application_log_blank_table_rows_do_not_count_as_entries(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = re.sub(
            r"(?ms)^## Application Log\n.*\Z",
            "## Application Log\n\n| Date | Action | Owner | Result | Next step |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| | | | | |\n",
            source,
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn("Ready application has an empty Application Log", result["errors"])

    def test_ready_application_requires_meaningful_application_log_fields(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = re.sub(
            r"(?ms)^## Application Log\n.*\Z",
            "## Application Log\n\n| Date | Action | Owner | Result | Next step |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| note | | | | |\n",
            source,
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn("Ready application has an empty Application Log", result["errors"])

    def test_drafting_and_researching_records_can_remain_partial(self):
        validator = load_validator_module()
        source = """# Acme - Web Lead

- Target role: Web Lead
- Company: Acme
- Status: {status}
- Opportunity score: 87
- Next action: Draft materials.
- Follow-up date: TBD

## Fit Assessment

In progress.

## Cover Letter

- Status: TBD

## Tailored Resume

## Application Log
"""

        with tempfile.TemporaryDirectory() as directory:
            for status in ("Drafting", "Researching"):
                with self.subTest(status=status):
                    application = Path(directory) / f"{status}.md"
                    application.write_text(source.format(status=status), encoding="utf-8")
                    result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")
                    self.assertEqual([], result["errors"])

    def test_invalid_application_reports_required_content_and_canonical_conflicts(self):
        validator = load_validator_module()

        result = validator.validate_application(
            FIXTURES_DIRECTORY / "invalid_acme_web_lead.md",
            FIXTURES_DIRECTORY / "valid_profile.md",
        )

        errors = "\n".join(result["errors"])
        self.assertIn("missing required heading: Cover Letter", errors)
        self.assertIn("missing required heading: Application Log", errors)
        self.assertIn("missing required field: Follow-up date", errors)
        self.assertIn("unresolved marker", errors)
        self.assertIn("provisional", errors)
        self.assertIn("conflicts with canonical role", errors)

    def test_duplicate_identity_is_reported_across_markdown_files(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            applications = Path(directory)
            (applications / "first.md").write_text(source, encoding="utf-8")
            (applications / "second.md").write_text(source, encoding="utf-8")

            duplicates = validator.find_duplicates(applications)

        self.assertEqual(["acme | web lead"], list(duplicates))
        self.assertEqual(2, len(duplicates["acme | web lead"]))

    def test_duplicate_identity_ignores_inline_html_comment_content(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        commented = source.replace("- Company: Acme", "- Company: Ac<!-- internal -->me").replace(
            "- Target role: Web Lead", "- Target role: Web<!-- approved --> Lead"
        )

        with tempfile.TemporaryDirectory() as directory:
            applications = Path(directory)
            (applications / "first.md").write_text(source, encoding="utf-8")
            (applications / "second.md").write_text(commented, encoding="utf-8")

            duplicates = validator.find_duplicates(applications)

        self.assertEqual(["acme | web lead"], list(duplicates))

    def test_duplicate_detection_skips_files_with_reserved_private_use_code_points(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            applications = Path(directory)
            (applications / "plain-one.md").write_text(source, encoding="utf-8")
            (applications / "plain-two.md").write_text(source, encoding="utf-8")
            for name, code_point in (("reserved-e000.md", "\ue000"), ("reserved-e001.md", "\ue001")):
                (applications / name).write_text(
                    source.replace("- Company: Acme", f"- Company: {code_point}Acme"),
                    encoding="utf-8",
                )

            duplicates = validator.find_duplicates(applications)

        self.assertEqual(["acme | web lead"], list(duplicates))
        self.assertEqual(2, len(duplicates["acme | web lead"]))
        self.assertNotIn("\ue000", "\n".join(duplicates))
        self.assertNotIn("\ue001", "\n".join(duplicates))

    def test_markdown_links_are_not_unresolved_markers(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source + "\nSee [Acme careers](https://example.com/jobs).\n", encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertFalse(any("unresolved marker" in error for error in result["errors"]))

    def test_template_marker_is_reported_as_unresolved(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source + "\n{{candidate_name}}\n", encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertTrue(any("unresolved marker" in error for error in result["errors"]))

    def test_markdown_task_lists_and_reference_links_are_not_unresolved_markers(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source += (
            "\n- [ ] Review materials\n- [x] Submitted\n"
            "> - [ ] Review outreach\n> - [x] Sent outreach\n"
            "[Acme]\n\n[acme]: https://example.com/jobs\n"
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "application.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertFalse(any("unresolved marker" in error for error in result["errors"]))

    def test_duplicate_identity_is_case_insensitive(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        differently_cased = source.replace("Web Lead", "WEB lead").replace("Acme", "ACME")

        with tempfile.TemporaryDirectory() as directory:
            applications = Path(directory)
            (applications / "first.md").write_text(source, encoding="utf-8")
            (applications / "second.md").write_text(differently_cased, encoding="utf-8")
            duplicates = validator.find_duplicates(applications)

        self.assertEqual(["acme | web lead"], list(duplicates))

    def test_duplicate_identity_collapses_ascii_whitespace_runs(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        spaced = source.replace("- Target role: Web Lead", "- Target role:  Web   Lead  ").replace(
            "- Company: Acme", "- Company:  Acme   Corporation  "
        )
        source = source.replace("- Target role: Web Lead", "- Target role: Web Lead").replace(
            "- Company: Acme", "- Company: Acme Corporation"
        )

        with tempfile.TemporaryDirectory() as directory:
            applications = Path(directory)
            (applications / "first.md").write_text(source, encoding="utf-8")
            (applications / "second.md").write_text(spaced, encoding="utf-8")

            duplicates = validator.find_duplicates(applications)

        self.assertEqual(["acme corporation | web lead"], list(duplicates))

    def test_duplicate_identity_collapses_unicode_whitespace_runs(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        unicode_spaced = source.replace("- Target role: Web Lead", "- Target role: Web\u2003Lead").replace(
            "- Company: Acme", "- Company: Acme\u00a0Corporation"
        )
        source = source.replace("- Target role: Web Lead", "- Target role: Web Lead").replace(
            "- Company: Acme", "- Company: Acme Corporation"
        )

        with tempfile.TemporaryDirectory() as directory:
            applications = Path(directory)
            (applications / "first.md").write_text(source, encoding="utf-8")
            (applications / "second.md").write_text(unicode_spaced, encoding="utf-8")

            duplicates = validator.find_duplicates(applications)

        self.assertEqual(["acme corporation | web lead"], list(duplicates))

    def test_title_only_and_dates_only_canonical_conflicts_are_reported(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = {
            "title": source.replace("Senior Web Developer", "Web Developer"),
            "dates": source.replace("October 2016–February 2020", "October 2016–January 2020"),
        }

        with tempfile.TemporaryDirectory() as directory:
            for name, application_text in cases.items():
                with self.subTest(conflict=name):
                    application = Path(directory) / f"{name}.md"
                    application.write_text(application_text, encoding="utf-8")
                    result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")
                    self.assertTrue(
                        any("conflicts with canonical role" in error for error in result["errors"])
                    )

    def test_multiple_canonical_roles_at_one_employer_allow_matching_earlier_role(self):
        validator = load_validator_module()
        application = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        profile = (FIXTURES_DIRECTORY / "valid_profile.md").read_text(encoding="utf-8")
        profile += "\n### Staff Web Developer | Example Corp | March 2020–June 2023\n"

        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "profile.md"
            profile_path.write_text(profile, encoding="utf-8")
            result = validator.validate_application(
                FIXTURES_DIRECTORY / "valid_acme_web_lead.md", profile_path
            )

        self.assertEqual([], result["errors"])

    def test_multiple_canonical_roles_at_one_employer_reject_mismatched_role(self):
        validator = load_validator_module()
        application = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        application = application.replace("Senior Web Developer", "Web Developer")
        profile = (FIXTURES_DIRECTORY / "valid_profile.md").read_text(encoding="utf-8")
        profile += "\n### Staff Web Developer | Example Corp | March 2020–June 2023\n"

        with tempfile.TemporaryDirectory() as directory:
            application_path = Path(directory) / "application.md"
            profile_path = Path(directory) / "profile.md"
            application_path.write_text(application, encoding="utf-8")
            profile_path.write_text(profile, encoding="utf-8")
            result = validator.validate_application(application_path, profile_path)

        self.assertTrue(any("conflicts with canonical role" in error for error in result["errors"]))

    def test_profile_rejects_role_like_canonical_headings_outside_level_three(self):
        validator = load_validator_module()
        profile = (FIXTURES_DIRECTORY / "valid_profile.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            for level in (1, 2, 4):
                with self.subTest(heading_level=level):
                    profile_path = Path(directory) / f"profile-level-{level}.md"
                    profile_path.write_text(
                        profile
                        + f"\n{'#' * level} Staff Web Developer | Example Corp | March 2020–June 2023\n",
                        encoding="utf-8",
                    )
                    result = validator.validate_application(
                        FIXTURES_DIRECTORY / "valid_acme_web_lead.md", profile_path
                    )

                    self.assertIn(
                        "Canonical Employment History role records must use level-three headings",
                        result["errors"],
                    )

    def test_provisional_scores_reject_invalid_bounds_and_midpoints(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = {
            "bounds": "- Opportunity score: 19–101 provisional; midpoint 60",
            "calculator-minimum": "- Opportunity score: 0–100 provisional; midpoint 50",
            "reversed": "- Opportunity score: 95–75 provisional; midpoint 85",
            "outside": "- Opportunity score: 75–95 provisional; midpoint 96",
            "not-average": "- Opportunity score: 75–95 provisional; midpoint 84",
        }

        with tempfile.TemporaryDirectory() as directory:
            for name, score in cases.items():
                with self.subTest(score=name):
                    application = Path(directory) / f"{name}.md"
                    application.write_text(
                        re.sub(r"(?m)^- Opportunity score:.*$", score, source), encoding="utf-8"
                    )
                    result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")
                    self.assertIn(
                        "provisional Opportunity score must use 20–100 bounds and an exact midpoint",
                        result["errors"],
                    )

    def test_opportunity_score_requires_an_approved_full_format(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        cases = {
            "exact-trailing-garbage": "- Opportunity score: 87 approved",
            "provisional-trailing-garbage": "- Opportunity score: 75–95 provisional; midpoint 85 approved",
            "provisional-missing-semicolon": "- Opportunity score: 75–95 provisional midpoint 85",
        }

        with tempfile.TemporaryDirectory() as directory:
            for name, score in cases.items():
                with self.subTest(score=name):
                    application = Path(directory) / f"{name}.md"
                    application.write_text(
                        re.sub(r"(?m)^- Opportunity score:.*$", score, source), encoding="utf-8"
                    )
                    result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")
                    self.assertIn(
                        "Opportunity score must use an approved exact or provisional format",
                        result["errors"],
                    )

    def test_unparseable_nonblank_canonical_history_is_actionable_error(self):
        validator = load_validator_module()
        profile = "# Career Facts\n\n## Canonical Employment History\n\nExample Corp, Senior Web Developer\n\n## Education\n"

        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "profile.md"
            profile_path.write_text(profile, encoding="utf-8")
            result = validator.validate_application(
                FIXTURES_DIRECTORY / "valid_acme_web_lead.md", profile_path
            )

        self.assertTrue(any("Canonical Employment History" in error for error in result["errors"]))

    def test_career_template_with_malformed_history_reports_unparseable_error(self):
        validator = load_validator_module()
        career_template = (
            Path(__file__).parents[1] / "assets" / "career-facts-template.md"
        ).read_text(encoding="utf-8")
        profile = career_template.replace(
            "{{canonical_employment_history}}", "Example Corp, Senior Web Developer"
        )

        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "profile.md"
            profile_path.write_text(profile, encoding="utf-8")
            result = validator.validate_application(
                FIXTURES_DIRECTORY / "valid_acme_web_lead.md", profile_path
            )

        self.assertTrue(any("Canonical Employment History" in error for error in result["errors"]))

    def test_cli_returns_json_and_nonzero_for_validation_errors(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                str(FIXTURES_DIRECTORY / "invalid_acme_web_lead.md"),
                str(FIXTURES_DIRECTORY / "valid_profile.md"),
            ],
            capture_output=True,
            text=True,
        )

        self.assertEqual(1, completed.returncode)
        self.assertIn("missing required heading: Cover Letter", json.loads(completed.stdout)["errors"])
        self.assertEqual("", completed.stderr)

    def test_cli_reports_missing_files_cleanly(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "missing-application.md", "missing-profile.md"],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(0, completed.returncode)
        self.assertIn("cannot read missing-application.md", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_cli_reports_invalid_or_missing_arguments_cleanly(self):
        cases = (
            [],
            [str(FIXTURES_DIRECTORY / "valid_acme_web_lead.md")],
            ["--applications-dir", "not-a-directory", "application.md", "profile.md"],
        )

        for arguments in cases:
            with self.subTest(arguments=arguments):
                completed = subprocess.run(
                    [sys.executable, str(SCRIPT_PATH), *arguments],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(0, completed.returncode)
                self.assertNotIn("Traceback", completed.stderr)

    def test_cli_reports_duplicates_as_json_errors_and_returns_nonzero(self):
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            applications = Path(directory)
            (applications / "first.md").write_text(source, encoding="utf-8")
            (applications / "second.md").write_text(source, encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(FIXTURES_DIRECTORY / "valid_acme_web_lead.md"),
                    str(FIXTURES_DIRECTORY / "valid_profile.md"),
                    "--applications-dir",
                    str(applications),
                ],
                capture_output=True,
                text=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(1, completed.returncode)
        self.assertIn("acme | web lead", result["duplicates"])
        self.assertTrue(any("duplicate application identity" in error for error in result["errors"]))

    def test_ready_application_rejects_all_structured_qualified_u_separators(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            for index, value in enumerate((
                "U pending", "U-pending", "U: pending", "U/TBD", "U.pending", "U_pending", "U (missing)",
                "U, pending", "U?missing",
            )):
                with self.subTest(value=value):
                    application = Path(directory) / f"qualified-u-{index}.md"
                    application.write_text(
                        source.replace("- Company: Acme", f"- Company: {value}"), encoding="utf-8"
                    )
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )
                    self.assertIn(
                        "Ready application has unresolved placeholder in Company", result["errors"]
                    )

    def test_ready_application_allows_concise_meaningful_log_values(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace(
            "| 2026-07-31 | Prepared application materials | Candidate | Materials ready for review | Confirm submission decision |",
            "| 2026-07-31 | Sent | Candidate | No reply | Wait |",
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "concise-log.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertEqual([], result["errors"])

    def test_ready_application_rejects_obvious_repeated_character_log_filler(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            for index, value in enumerate(("xxxx", "yyyy", "zzzz")):
                with self.subTest(value=value):
                    application = Path(directory) / f"repeated-log-filler-{index}.md"
                    application.write_text(
                        source.replace(
                            "| 2026-07-31 | Prepared application materials | Candidate | Materials ready for review | Confirm submission decision |",
                            f"| 2026-07-31 | {value} | Candidate | No reply | Wait |",
                        ),
                        encoding="utf-8",
                    )
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )

                    self.assertIn("Ready application has an empty Application Log", result["errors"])

    def test_ready_application_rejects_separator_obscured_repeated_character_log_filler(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            for index, value in enumerate(("xxxx.", "x x x x", "x-x-x-x", "y y y y", "z-z-z-z")):
                with self.subTest(value=value):
                    application = Path(directory) / f"separated-log-filler-{index}.md"
                    application.write_text(
                        source.replace(
                            "| 2026-07-31 | Prepared application materials | Candidate | Materials ready for review | Confirm submission decision |",
                            f"| 2026-07-31 | {value} | Candidate | No reply | Wait |",
                        ),
                        encoding="utf-8",
                    )
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )

                    self.assertIn("Ready application has an empty Application Log", result["errors"])

    def test_ready_application_allows_legitimate_placeholder_vocabulary_in_values_and_prose(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        source = source.replace("- Company: Acme", "- Company: Unknown Worlds Entertainment")
        source = source.replace(
            "Prepared application materials", "Pending Coffee planning",
        ).replace(
            "I would welcome the opportunity to lead your web work.",
            "None of our users should face unnecessary friction. Missing labels can block access. "
            "U.S. accessibility work and U-Haul or U-shaped form examples informed my approach.",
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "legitimate-vocabulary.md"
            application.write_text(source, encoding="utf-8")
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertEqual([], result["errors"])

    def test_ready_application_requires_role_and_body_in_tailored_resume(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        resume = "### Founder | Example Studio | July 2023–Present\n\n"

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "heading-only-resume.md"
            application.write_text(
                re.sub(
                    r"(?ms)^## Tailored Resume\n.*?(?=^## Application Log)",
                    f"## Tailored Resume\n\n{resume}",
                    source,
                ),
                encoding="utf-8",
            )
            result = validator.validate_application(application, FIXTURES_DIRECTORY / "valid_profile.md")

        self.assertIn("Ready application has an empty Tailored Resume", result["errors"])

    def test_ready_application_requires_valid_date_and_substantive_log_fields(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        attacks = (
            "| note | Prepared application materials | Candidate | Materials ready | Submit |",
            "| 2026-07-31 | x | Candidate | Materials ready | Submit |",
            "| 2026-07-31 | Sent | Candidate | x | Submit |",
            "| 2026-07-31 | Sent | Candidate | Done | x |",
        )

        with tempfile.TemporaryDirectory() as directory:
            for index, row in enumerate(attacks):
                with self.subTest(row=row):
                    application = Path(directory) / f"weak-log-{index}.md"
                    application.write_text(
                        re.sub(r"(?m)^\| 2026-07-31 \|.*$", row, source), encoding="utf-8"
                    )
                    result = validator.validate_application(
                        application, FIXTURES_DIRECTORY / "valid_profile.md"
                    )
                    self.assertIn("Ready application has an empty Application Log", result["errors"])

    def test_role_headings_reject_extra_components_and_malformed_dates(self):
        validator = load_validator_module()
        source = (FIXTURES_DIRECTORY / "valid_acme_web_lead.md").read_text(encoding="utf-8")
        application_text = source.replace(
            "### Founder | Example Studio | July 2023–Present",
            "### Founder | Example Studio | July 2023–Present | extra",
        )
        profile_text = (FIXTURES_DIRECTORY / "valid_profile.md").read_text(encoding="utf-8").replace(
            "### Founder | Example Studio | July 2023–Present",
            "### Founder | Example Studio | July 2023 through Present",
        ).replace(
            "### Senior Web Developer | Example Corp | October 2016–February 2020",
            "### Senior Web Developer | Example Corp | October 2016–February 2020 | extra",
        )

        with tempfile.TemporaryDirectory() as directory:
            application = Path(directory) / "extra-role-component.md"
            profile = Path(directory) / "malformed-date-profile.md"
            application.write_text(application_text, encoding="utf-8")
            profile.write_text(profile_text, encoding="utf-8")
            result = validator.validate_application(application, profile)

        errors = "\n".join(result["errors"])
        self.assertIn("Tailored Resume role records must contain exactly three pipe-separated components", errors)
        self.assertIn("Canonical Employment History role records must contain exactly three pipe-separated components", errors)
        self.assertIn("Canonical Employment History role records must use Month YYYY–Month YYYY or Month YYYY–Present dates", errors)


if __name__ == "__main__":
    unittest.main()
