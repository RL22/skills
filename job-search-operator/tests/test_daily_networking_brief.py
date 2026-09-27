"""Behavioral tests for the daily networking brief."""

import contextlib
from datetime import date
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
SCRIPT_PATH = ROOT / "scripts" / "daily_networking_brief.py"
FIXTURES = Path(__file__).parent / "fixtures"
NETWORK = FIXTURES / "brief_network.md"
PIPELINE = FIXTURES / "brief_pipeline.md"
TODAY = date(2026, 9, 20)  # a Sunday


def load_module():
    spec = importlib.util.spec_from_file_location("daily_networking_brief", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


brief = load_module()


def contact(status="", last=None, next_action="", org="Acme", degree="2nd", **extra):
    row = {
        "name": "Test Person", "org": org, "relationship": "%s-degree" % degree,
        "focus": "", "status": status, "last_touch": "", "next_action": next_action,
        "last_touch_date": last, "degree": degree, "mutuals": [],
    }
    row.update(extra)
    return row


def fixture_ranked(today=TODAY):
    contacts = brief.load_contacts(brief.parse_table(
        NETWORK.read_text(), brief.NETWORK_ALIASES, ["name", "status"]))
    pipeline = brief.load_pipeline(brief.parse_table(
        PIPELINE.read_text(), brief.PIPELINE_ALIASES, ["company", "status"]))
    return contacts, pipeline, brief.rank_dms(contacts, pipeline, today)


def run_main(argv, cwd=None, env=None, real_queue=False):
    if not real_queue and not any(a in ("--no-queue", "--queue-json") for a in argv):
        argv = list(argv) + ["--no-queue"]  # keep tests off the real queue
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        with mock.patch.dict(os.environ, env or {}):
            code = brief.main(argv, cwd=cwd)
    return code, out.getvalue(), err.getvalue()


class ParsingTests(unittest.TestCase):
    def test_alias_headers_and_markup_are_mapped(self):
        rows = brief.parse_table(NETWORK.read_text(), brief.NETWORK_ALIASES, ["name", "status"])

        self.assertEqual(12, len(rows))
        self.assertEqual("Ada Norr", rows[0]["name"])
        self.assertEqual("Northwind Labs, Inc.", rows[0]["org"])
        self.assertEqual("Send two times", rows[6]["next_action"])
        self.assertEqual("Sep 1, 2026", rows[6]["last_touch"])

    def test_pipeline_alias_headers_map_next_step_and_follow_up(self):
        rows = brief.parse_table(PIPELINE.read_text(), brief.PIPELINE_ALIASES, ["company", "status"])

        self.assertEqual("Prep", rows[0]["next_action"])
        self.assertEqual("September 19, 2026", rows[0]["follow_up"])

    def test_escaped_pipes_stay_inside_a_cell(self):
        text = "## Contacts\n\n| Contact | Focus | Status |\n|---|---|---|\n| A | ECD \\| Head | x |\n"

        rows = brief.parse_table(text, brief.NETWORK_ALIASES, ["name"])

        self.assertEqual("ECD | Head", rows[0]["focus"])

    def test_degree_words_and_unknown(self):
        self.assertEqual("1st", brief.parse_degree("1st-degree LinkedIn connection"))
        self.assertEqual("1st", brief.parse_degree("First-degree connection"))
        self.assertEqual("2nd", brief.parse_degree("second degree"))
        self.assertEqual("3rd", brief.parse_degree("3rd+ connection"))
        self.assertEqual("unknown", brief.parse_degree("Recruiter"))

    def test_mutual_names_are_split_and_cleaned(self):
        names = brief.parse_mutuals("2nd-degree; SF, CA; mutuals: Pat Lee, Sam Roe (1st deg!), Al Wu +4 others")

        self.assertEqual(["Pat Lee", "Sam Roe", "Al Wu"], names)
        self.assertEqual(["X Y"], brief.parse_mutuals("2nd", "mutual: X Y"))
        self.assertEqual([], brief.parse_mutuals("2nd-degree; SF, CA"))

    def test_last_touch_formats_and_placeholders(self):
        self.assertEqual(date(2026, 9, 12), brief.parse_date("September 12, 2026"))
        self.assertEqual(date(2026, 9, 12), brief.parse_date("Sep 12, 2026"))
        self.assertEqual(date(2026, 9, 12), brief.parse_date("2026-09-12"))
        self.assertEqual(date(2026, 9, 12), brief.parse_date("Sept 12, 2026 (email)"))
        for value in ("TBD", "Never", "", "-", "sometime in spring", "May 2025"):
            self.assertIsNone(brief.parse_date(value), value)

    def test_unparseable_count_ignores_placeholders(self):
        self.assertFalse(brief.is_unparseable_touch("TBD"))
        self.assertFalse(brief.is_unparseable_touch("Never"))
        self.assertFalse(brief.is_unparseable_touch(""))
        self.assertTrue(brief.is_unparseable_touch("sometime in spring"))

    def test_clean_name_matching(self):
        self.assertTrue(brief.orgs_match("Vercel", "Vercel Inc"))
        self.assertTrue(brief.orgs_match("Contoso.ai", "Contoso AI"))
        self.assertTrue(brief.orgs_match("Triune Infomatics Inc.", "Triune Infomatics / Alameda County IT"))
        self.assertTrue(brief.orgs_match("Happen Bank", "Happen Bank (formerly LendingClub)"))
        self.assertFalse(brief.orgs_match("Vercel", "Versel"))

    def test_score_parsing(self):
        self.assertEqual(82, brief.parse_score("64-100 provisional; midpoint 82"))
        self.assertEqual(100, brief.parse_score("100"))
        self.assertEqual(82, brief.parse_score("64-100 provisional"))
        self.assertIsNone(brief.parse_score("U"))


class TouchLogicTests(unittest.TestCase):
    def test_business_days_skip_weekends(self):
        friday, monday, tuesday = date(2026, 9, 11), date(2026, 9, 14), date(2026, 9, 15)

        self.assertEqual(0, brief.business_days_between(friday, monday))
        self.assertEqual(1, brief.business_days_between(friday, tuesday))
        self.assertEqual(5, brief.business_days_between(friday, date(2026, 9, 21)))
        self.assertEqual(5, brief.business_days_between(date(2026, 9, 12), date(2026, 9, 21)))

    def test_status_state_classification(self):
        self.assertEqual("closed", brief.status_state("Role closed"))
        self.assertEqual("replied", brief.status_state("call booked"))
        self.assertEqual("sent", brief.status_state("Connection request sent"))
        self.assertEqual("drafted", brief.status_state("Outreach drafted"))
        self.assertEqual("drafted", brief.status_state("Message drafted; not sent"))
        self.assertEqual("none", brief.status_state("Not contacted"))

    def test_none_status_is_first_touch(self):
        self.assertEqual(("first_touch", None), brief.touch_type(contact("Not contacted"), TODAY))

    def test_drafted_is_send_drafted(self):
        self.assertEqual("send_drafted", brief.touch_type(contact("Outreach drafted"), TODAY)[0])

    def test_replied_needs_next_action_or_two_days(self):
        self.assertEqual("warm_follow_up", brief.touch_type(
            contact("call booked", next_action="Send times"), TODAY)[0])
        self.assertEqual("warm_follow_up", brief.touch_type(
            contact("call booked", last=date(2026, 9, 10)), TODAY)[0])
        self.assertEqual((None, None), brief.touch_type(
            contact("call booked", last=date(2026, 9, 19)), TODAY))

    def test_sent_transitions_nudge_1_nudge_2_escalate(self):
        last = date(2026, 9, 10)  # 6 business days before TODAY

        self.assertEqual("nudge_1", brief.touch_type(contact("Message sent", last=last), TODAY)[0])
        self.assertEqual("nudge_2", brief.touch_type(contact("Nudge 1 sent", last=last), TODAY)[0])
        self.assertEqual("nudge_2", brief.touch_type(contact("Touch 2 sent", last=last), TODAY)[0])
        self.assertEqual("escalate", brief.touch_type(contact("Nudge 2 sent", last=last), TODAY)[0])
        self.assertEqual("escalate", brief.touch_type(contact("Touch 3 sent", last=last), TODAY)[0])

    def test_sent_below_five_business_days_is_not_due(self):
        # Last touch Fri Sep 11: Mon-Fri Sep 14-18 = 5 business days -> due.
        self.assertEqual("nudge_1", brief.touch_type(
            contact("Message sent", last=date(2026, 9, 11)), TODAY)[0])
        # Last touch Mon Sep 14: Tue-Fri = 4 business days -> not due.
        self.assertEqual((None, 4), brief.touch_type(
            contact("Message sent", last=date(2026, 9, 14)), TODAY))

    def test_two_day_cooldown_beats_every_state(self):
        for status in ("Not contacted", "Outreach drafted", "Message sent", "call booked"):
            kind, _ = brief.touch_type(
                contact(status, last=date(2026, 9, 19), next_action="x"), TODAY)
            self.assertIsNone(kind, status)
        self.assertEqual("first_touch", brief.touch_type(
            contact("Not contacted", last=date(2026, 9, 18)), TODAY)[0])

    def test_closed_is_never_due(self):
        self.assertEqual((None, None), brief.touch_type(contact("Role closed, declined"), TODAY))


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.contacts, self.pipeline, self.ranked = fixture_ranked()
        self.by_name = {d["name"]: d for d in self.ranked}

    def test_closed_and_cooldown_contacts_are_excluded(self):
        self.assertNotIn("Hal Ivey", self.by_name)
        self.assertNotIn("Kai Lund", self.by_name)

    def test_terminal_only_org_excluded_unless_first_degree(self):
        self.assertNotIn("Di Kern", self.by_name)
        self.assertIn("Ed Foss", self.by_name)

    def test_first_degree_at_interviewing_org_outranks_third_at_researching(self):
        self.assertGreater(self.by_name["Ada Norr"]["score"], self.by_name["Ben Ost"]["score"])
        self.assertEqual("Interviewing", self.by_name["Ada Norr"]["pipeline_status"])
        self.assertEqual("Researching", self.by_name["Ben Ost"]["pipeline_status"])

    def test_exact_score_breakdown_for_vercel_contact(self):
        # Networking 26 + 2nd with 2 named mutuals 18 + first-touch nudge_1 22
        # + "Head of" authority 10 + no follow-up date 0 = 76; sent 6 business days.
        cy = self.by_name["Cy Vale"]

        self.assertEqual("nudge_1", cy["touch_type"])
        self.assertEqual(76, cy["score"])
        self.assertIn("Vercel Inc is Networking; 2nd degree via Pat Lee", cy["reason"])
        self.assertIn("13 business days since last touch, nudge 1 due", cy["reason"])

    def test_output_is_sorted_by_score_descending(self):
        scores = [d["score"] for d in self.ranked]

        self.assertEqual(sorted(scores, reverse=True), scores)

    def test_nudge_and_escalate_share_reference_angle_and_first_touch_uses_focus(self):
        self.assertEqual("Reference the earlier message; keep it short and easy to decline",
                         self.by_name["Cy Vale"]["angle"])
        self.assertEqual("escalate", self.by_name["Max Ruiz"]["touch_type"])
        self.assertIn("Open with their team's problem in Head of Engineering",
                      self.by_name["Ada Norr"]["angle"])
        self.assertEqual("Propose two concrete 15-minute slots", self.by_name["Gus Hale"]["angle"])

    def test_timing_bonus_when_pipeline_follow_up_is_within_three_days(self):
        # Northwind follow-up is Sep 19, one day before TODAY.
        self.assertEqual(30 + 25 + 14 + 10 + 10, self.by_name["Ada Norr"]["score"])

    def test_dm_limit_and_missing_optional_fields(self):
        code, out, _ = run_main(
            ["--network", str(NETWORK), "--pipeline", str(PIPELINE), "--no-posts",
             "--today", "2026-09-20", "--dm-limit", "2", "--json",
             "--config", "/nonexistent/config.yaml"])

        self.assertEqual(0, code)
        self.assertEqual(2, len(json.loads(out)["dms"]))


class PathDiscoveryTests(unittest.TestCase):
    def make_layout(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def write(self, path, text="x"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def config(self, root, workspace, **values):
        lines = ["workspace: %s" % workspace] + ["%s: %s" % kv for kv in values.items()]
        return self.write(root / "config.yaml", "\n".join(lines) + "\n")

    def resolve(self, explicit, config, cwd):
        return brief.resolve_file(
            "NETWORK", explicit, brief.read_config(config), "network_file",
            "NETWORK.md", True, cwd)

    def test_explicit_argument_wins_without_warning(self):
        root = self.make_layout()
        explicit = self.write(root / "mine.md")
        config = self.config(root, root / "ws", network_file="NETWORK.md")
        self.write(root / "ws" / "NETWORK.md")

        self.assertEqual((explicit, None), self.resolve(str(explicit), config, root / "cwd"))

    def test_fallback_order_workspace_then_shared_facts_then_cwd(self):
        root = self.make_layout()
        config = self.config(root, root / "ws", network_file="NETWORK.md")
        cwd = root / "cwd"
        cwd_file = self.write(cwd / "_shared_facts" / "NETWORK.md")

        path, warning = self.resolve(None, config, cwd)
        self.assertEqual(cwd_file, path)
        self.assertIn(str(root / "ws" / "NETWORK.md"), warning)
        self.assertIn(str(cwd_file), warning)

        shared = self.write(root / "ws" / "_shared_facts" / "NETWORK.md")
        path, warning = self.resolve(None, config, cwd)
        self.assertEqual(shared, path)
        self.assertIsNotNone(warning)

        direct = self.write(root / "ws" / "NETWORK.md")
        self.assertEqual((direct, None), self.resolve(None, config, cwd))

    def test_bad_explicit_falls_back_and_warns(self):
        root = self.make_layout()
        cwd_file = self.write(root / "_shared_facts" / "NETWORK.md")

        path, warning = self.resolve(str(root / "gone.md"), root / "no.yaml", root)

        self.assertEqual(cwd_file, path)
        self.assertIn("gone.md", warning)

    def test_pipeline_uses_cwd_readme_fallback(self):
        root = self.make_layout()
        readme = self.write(root / "README.md")

        path, warning = brief.resolve_file(
            "PIPELINE", None, {"workspace": str(root / "ws"), "pipeline_file": "README.md"},
            "pipeline_file", "README.md", False, root)

        self.assertEqual(readme, path)
        self.assertIn("PIPELINE", warning)

    def test_config_parser_reads_flat_lines(self):
        root = self.make_layout()
        config = self.write(root / "c.yaml", "# note\nworkspace: /a/b\nnetwork_file: 'N.md'\n")

        self.assertEqual({"workspace": "/a/b", "network_file": "N.md"}, brief.read_config(config))
        self.assertEqual({}, brief.read_config(root / "missing.yaml"))

    def test_main_exits_two_when_nothing_resolves(self):
        root = self.make_layout()

        code, out, err = run_main(["--config", str(root / "none.yaml"), "--no-posts"], cwd=root)

        self.assertEqual(2, code)
        self.assertEqual("", out)
        self.assertIn("could not locate", err)


class PostsTests(unittest.TestCase):
    def load(self, argv, env=None):
        args = brief.build_parser().parse_args(argv)
        with mock.patch.dict(os.environ, env or {}):
            return brief.load_posts(args)

    def test_flattened_and_nested_shapes_normalize_the_same(self):
        flat, warn_a = self.load(["--posts-json", str(FIXTURES / "brief_posts_flat.json")])
        nested, warn_b = self.load(["--posts-json", str(FIXTURES / "brief_posts_nested.json")])

        self.assertIsNone(warn_a)
        self.assertIsNone(warn_b)
        self.assertEqual("Pat Poster", flat[0]["author"])
        self.assertEqual(2.0, flat[0]["age_days"])
        self.assertEqual("growth, seo", flat[0]["hits"])
        self.assertEqual("Acme Page", nested[0]["author"])
        self.assertIsNone(nested[0]["age_days"])
        self.assertEqual("https://example.com/p/2", nested[0]["post_url"])

    def test_missing_cli_does_not_crash(self):
        posts, warning = self.load([], env={"JSB_LINKEDIN_SCOUT_CLI": "/nonexistent/cli.py"})

        self.assertEqual([], posts)
        self.assertIn("Posts unavailable", warning)

    def test_unparseable_posts_file_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("not json")

            posts, warning = self.load(["--posts-json", str(bad)])

        self.assertEqual([], posts)
        self.assertIn("Posts unavailable", warning)

    def test_failing_cli_warns_and_working_cli_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            failing = Path(tmp) / "fail.py"
            failing.write_text("import sys; sys.stderr.write('boom'); sys.exit(3)\n")
            good = Path(tmp) / "good.py"
            good.write_text("import sys; print('noise'); print('[{\"rank\": 1, \"author_name\": \"Z\"}]')\n")

            _, warning = self.load([], env={"JSB_LINKEDIN_SCOUT_CLI": str(failing)})
            posts, ok = self.load([], env={"JSB_LINKEDIN_SCOUT_CLI": str(good)})

        self.assertIn("exited 3", warning)
        self.assertIsNone(ok)
        self.assertEqual("Z", posts[0]["author"])


class ActionTests(unittest.TestCase):
    def actions(self, today, posts_loaded=False, pipeline=None):
        contacts, fixture_pipeline, ranked = fixture_ranked(today)
        return brief.build_actions(pipeline if pipeline is not None else fixture_pipeline,
                                   contacts, ranked, today, posts_loaded)

    def titles(self, items):
        return " | ".join(i["title"] for i in items)

    def test_count_is_between_three_and_five_and_fields_present(self):
        items = self.actions(TODAY, posts_loaded=True)

        self.assertTrue(3 <= len(items) <= 5)
        for item in items:
            self.assertEqual({"title", "why", "how", "est_minutes"}, set(item))

    def test_overdue_rows_come_first_most_overdue_first(self):
        items = self.actions(TODAY)

        self.assertIn("Fabrikam", items[0]["title"])
        self.assertTrue(items[0]["title"].startswith("Overdue follow-up"))

    def test_smart_comments_only_when_posts_loaded(self):
        self.assertIn("Smart comments", self.titles(self.actions(TODAY, posts_loaded=True)))
        self.assertNotIn("Smart comments", self.titles(self.actions(TODAY, posts_loaded=False)))

    def test_warm_before_applying_names_org_and_best_contact(self):
        items = self.actions(TODAY)
        warm = [i for i in items if i["title"].startswith("Warm up")]

        self.assertTrue(warm)
        self.assertIn("never apply cold", warm[0]["why"])

    def test_monday_adds_profile_freshness_and_friday_adds_pruning(self):
        # Only D, E, and F qualify, so G and H are reachable within the cap of 5.
        pipeline = brief.load_pipeline([
            {"company": "A", "role": "Web Engineer", "status": "Networking", "score": "80",
             "positioning": "", "next_action": "", "follow_up": ""}])
        monday = self.actions(date(2026, 9, 21), pipeline=pipeline)
        friday = self.actions(date(2026, 9, 18), pipeline=pipeline)
        tuesday = self.actions(date(2026, 9, 22), pipeline=pipeline)

        self.assertIn("Profile freshness", self.titles(monday))
        self.assertNotIn("Network pruning", self.titles(monday))
        self.assertIn("Network pruning", self.titles(friday))
        self.assertNotIn("Profile freshness", self.titles(tuesday))

    def test_fewer_than_three_fills_from_the_last_three(self):
        items = self.actions(date(2026, 9, 22), pipeline=[])

        self.assertEqual(3, len(items))
        self.assertIn("ICP coverage", self.titles(items))

    def test_fresh_requisition_urls_are_encoded_deduped_and_capped(self):
        pipeline = brief.load_pipeline([
            {"company": "A", "role": "Web Engineer (Remote)", "status": "Networking", "score": "", "positioning": "", "next_action": "", "follow_up": ""},
            {"company": "B", "role": "Web Engineer", "status": "Drafting", "score": "", "positioning": "", "next_action": "", "follow_up": ""},
            {"company": "C", "role": "Growth & SEO Lead", "status": "Networking", "score": "", "positioning": "", "next_action": "", "follow_up": ""},
        ])
        sweep = [i for i in self.actions(TODAY, pipeline=pipeline) if "Fresh-requisition" in i["title"]][0]

        self.assertEqual(1, sweep["how"].count("keywords=Web+Engineer&f_TPR=r14400"))
        self.assertIn("keywords=Growth+%26+SEO+Lead&f_TPR=r14400", sweep["how"])


def qitem(status="approved", target_type="dm", action_type="message",
          name="Ada Norr", draft="Hello there", **extra):
    item = {"action_id": "a1", "target_type": target_type, "target_id": "t",
            "target_url": None, "action_type": action_type, "reaction_type": None,
            "status": status, "rubric_score": 80.0, "draft_content": draft,
            "rationale": "", "created_at": "2026-09-17T00:00:00",
            "counterparty_name": name}
    item.update(extra)
    return item


def row(name, org, score, kind="first_touch"):
    return {"name": name, "organization": org, "score": score, "touch_type": kind}


class OrgCapTests(unittest.TestCase):
    def rows(self):
        return [row("A", "Hightouch", 90), row("B", "Hightouch", 80),
                row("C", "Hightouch", 70), row("D", "Other", 60), row("E", "Third", 50)]

    def names(self, rows):
        return [r["name"] for r in rows]

    def test_cap_holds_at_two_and_frees_slots_for_other_orgs(self):
        self.assertEqual(["A", "B", "D", "E"], self.names(brief.cap_per_org(self.rows(), 4, 2)))

    def test_fill_back_from_deferred_in_score_order(self):
        rows = self.rows() + [row("F", "Hightouch", 40)]

        self.assertEqual(["A", "B", "C", "D", "E"], self.names(brief.cap_per_org(rows, 5, 2)))
        self.assertEqual(["A", "B", "C", "D", "E", "F"],
                         self.names(brief.cap_per_org(rows, 6, 2)))

    def test_zero_disables_cap(self):
        self.assertEqual(["A", "B", "C"], self.names(brief.cap_per_org(self.rows(), 3, 0)))

    def test_clean_name_equivalence_counts_as_one_org(self):
        rows = [row("A", "Vanta", 90), row("B", "Vanta Inc", 80),
                row("C", "Vanta, Inc.", 70), row("D", "Other", 60)]

        self.assertEqual(["A", "B", "D"], self.names(brief.cap_per_org(rows, 3, 2)))

    def test_unknown_org_is_not_grouped(self):
        rows = [row(n, "unknown", 90 - i) for i, n in enumerate("ABC")]

        self.assertEqual(3, len(brief.cap_per_org(rows, 3, 2)))

    def test_flag_default_and_main_wiring(self):
        self.assertEqual(2, brief.build_parser().parse_args([]).max_per_org)
        base = ["--network", str(NETWORK), "--pipeline", str(PIPELINE), "--no-posts",
                "--today", "2026-09-20", "--json", "--config", "/nonexistent/config.yaml",
                "--dm-limit", "7"]
        _, out, _ = run_main(base + ["--max-per-org", "1"])
        dms = json.loads(out)["dms"]
        orgs = [brief.clean_name(d["organization"]) for d in dms]

        self.assertEqual(7, len(orgs))
        self.assertEqual(len(orgs), len(set(orgs)))
        _, out, _ = run_main(base + ["--max-per-org", "0"])
        self.assertEqual(7, len(json.loads(out)["dms"]))


class QueueTests(unittest.TestCase):
    BASE = ["--network", str(NETWORK), "--pipeline", str(PIPELINE), "--no-posts",
            "--today", "2026-09-20", "--json", "--config", "/nonexistent/config.yaml",
            "--dm-limit", "20", "--max-per-org", "0"]

    def run_queue(self, items, extra=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "q.json"
            path.write_text(json.dumps(items))
            code, out, _ = run_main(self.BASE + ["--queue-json", str(path)] + (extra or []))
        self.assertEqual(0, code)
        return json.loads(out)

    def find(self, data, name):
        return [d for d in data["dms"] if d["name"] == name]

    def test_approved_converts_contact_to_top_send_approved_without_duplicate(self):
        data = self.run_queue([qitem("approved", name="ada norr", draft="Hi Ada")])
        rows = self.find(data, "Ada Norr")

        self.assertEqual(1, len(rows))
        self.assertEqual("send_approved", rows[0]["touch_type"])
        self.assertEqual(100, rows[0]["score"])
        self.assertEqual("Hi Ada", rows[0]["draft"])
        self.assertEqual("Northwind Labs, Inc.", rows[0]["organization"])
        self.assertEqual(rows[0], data["dms"][0])
        self.assertIn("Approved draft waiting; send it yourself in your own browser",
                      rows[0]["reason"])
        self.assertEqual("Read the approved draft once more, then send manually",
                         rows[0]["angle"])

    def test_drafted_becomes_review_queued_keeping_computed_score(self):
        baseline = {d["name"]: d for d in fixture_ranked()[2]}["Cy Vale"]
        data = self.run_queue([qitem("drafted", name="Cy Vale")])
        rows = self.find(data, "Cy Vale")

        self.assertEqual(1, len(rows))
        self.assertEqual("review_queued", rows[0]["touch_type"])
        self.assertEqual(baseline["score"], rows[0]["score"])
        self.assertEqual("Drafted in the queue, awaiting your approve or reject",
                         rows[0]["reason"])

    def test_rejected_and_executed_leave_contact_unaffected(self):
        plain = self.run_queue([])
        for status in ("rejected", "executed"):
            data = self.run_queue([qitem(status, name="Cy Vale")])
            self.assertEqual(plain["dms"], data["dms"])

    def test_unknown_counterparty_still_lists(self):
        data = self.run_queue([qitem("approved", name="Nobody Known", draft="x")])
        rows = self.find(data, "Nobody Known")

        self.assertEqual("unknown", rows[0]["organization"])
        self.assertEqual("send_approved", rows[0]["touch_type"])
        self.assertEqual("Nobody Known", data["dms"][0]["name"])

    def test_post_items_do_not_appear_in_dm_list(self):
        data = self.run_queue([qitem("approved", target_type="post",
                                     action_type="comment", name="Tony Stark")])

        self.assertEqual([], self.find(data, "Tony Stark"))

    def test_markdown_truncates_draft_json_keeps_full(self):
        long = "word " * 100
        items = [qitem("approved", draft=long)]
        full = self.run_queue(items)["dms"][0]["draft"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "q.json"
            path.write_text(json.dumps(items))
            _, out, _ = run_main([a for a in self.BASE if a != "--json"]
                                 + ["--queue-json", str(path)])

        self.assertEqual(long, full)
        self.assertIn("send_approved", out)
        self.assertIn("...", out)
        self.assertNotIn(long.strip(), out)

    def test_queued_drafts_count_toward_org_cap(self):
        ranked = [row("Q1", "Vanta", 100, "send_approved"), row("Q2", "Vanta Inc", 100, "send_approved"),
                  row("C", "Vanta", 90), row("D", "Other", 50)]

        self.assertEqual(["Q1", "Q2", "D"], [r["name"] for r in brief.cap_per_org(ranked, 3, 2)])

    def test_missing_cli_warns_and_continues(self):
        _, out, _ = run_main(self.BASE, real_queue=True, env={"JSB_LINKEDIN_SCOUT_CLI": "/nonexistent/cli.py"})
        data = json.loads(out)

        self.assertTrue(any("engagement queue unavailable" in w for w in data["warnings"]))
        self.assertTrue(data["dms"])

    def test_bad_json_and_failing_and_hanging_cli_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.py"
            bad.write_text("print('not json')\n")
            fail = Path(tmp) / "fail.py"
            fail.write_text("import sys; sys.exit(2)\n")
            good = Path(tmp) / "good.py"
            good.write_text("import sys, json\n"
                            "assert sys.argv[1:3] == ['list-engagement', '--json']\n"
                            "print(json.dumps([%r]))\n" % qitem("approved"))
            for script in (bad, fail):
                _, out, _ = run_main(self.BASE, real_queue=True, env={"JSB_LINKEDIN_SCOUT_CLI": str(script)})
                self.assertTrue(any("engagement queue unavailable" in w
                                    for w in json.loads(out)["warnings"]))
            _, out, _ = run_main(self.BASE, real_queue=True, env={"JSB_LINKEDIN_SCOUT_CLI": str(good)})
            data = json.loads(out)
            self.assertEqual("send_approved", data["dms"][0]["touch_type"])
            self.assertFalse(any("queue" in w for w in data["warnings"]))
            args = brief.build_parser().parse_args([])
            with mock.patch.dict(os.environ, {"JSB_LINKEDIN_SCOUT_CLI": str(good)}), \
                    mock.patch.object(brief.subprocess, "run",
                                      side_effect=brief.subprocess.TimeoutExpired("x", 30)):
                items, warning = brief.load_queue(args)
            self.assertEqual([], items)
            self.assertIn("timed out", warning)

    def test_no_queue_skips_cli_and_warning(self):
        _, out, _ = run_main(self.BASE + ["--no-queue"],
                             env={"JSB_LINKEDIN_SCOUT_CLI": "/nonexistent/cli.py"})
        data = json.loads(out)

        self.assertFalse(any("queue" in w for w in data["warnings"]))

    def test_queue_json_parsing(self):
        args = brief.build_parser().parse_args(["--queue-json", "/nonexistent/q.json"])
        self.assertIn("engagement queue unavailable", brief.load_queue(args)[1])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "q.json"
            path.write_text(json.dumps([qitem(), "junk", 3]))
            items, warning = brief.load_queue(
                brief.build_parser().parse_args(["--queue-json", str(path)]))
            path.write_text('{"not": "a list"}')
            _, warning_dict = brief.load_queue(
                brief.build_parser().parse_args(["--queue-json", str(path)]))

        self.assertIsNone(warning)
        self.assertEqual(1, len(items))
        self.assertIn("engagement queue unavailable", warning_dict)

    def test_action_c_wording_by_queued_comment_count(self):
        contacts, pipeline, ranked = fixture_ranked()

        def c_action(count, status="drafted"):
            items = [qitem(status, target_type="post", action_type="comment")] * count
            items += [qitem("rejected", target_type="post", action_type="comment")]
            n = brief.queued_comment_count(items)
            acts = brief.build_actions(pipeline, contacts, ranked, TODAY, True, n)
            return [a for a in acts if "omment" in a["title"] or "omment" in a["how"]][0]

        self.assertIn("Draft 3 comments", c_action(0)["how"])
        self.assertIn("1 draft already queued; draft 2 more", c_action(1)["how"])
        self.assertIn("2 drafts already queued; draft 1 more", c_action(2)["how"])
        self.assertEqual("Review and approve your 3 queued comment drafts", c_action(3)["title"])
        self.assertEqual("Review and approve your 3 queued comment drafts",
                         c_action(3, "approved")["title"])
        self.assertNotIn("Smart comments", c_action(3)["title"])

    def test_output_has_no_em_or_en_dashes_with_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "q.json"
            path.write_text(json.dumps([qitem(draft="a \u2014 b \u2013 c")]))
            _, out, _ = run_main(self.BASE + ["--queue-json", str(path)])

        self.assertNotIn("\u2014", out)
        self.assertNotIn("\u2013", out)


class EndToEndTests(unittest.TestCase):
    def test_main_markdown_has_all_sections_and_exits_zero(self):
        code, out, _ = run_main(
            ["--network", str(NETWORK), "--pipeline", str(PIPELINE), "--no-posts",
             "--today", "2026-09-20", "--config", "/nonexistent/config.yaml"])

        self.assertEqual(0, code)
        self.assertIn("# Daily networking brief: 2026-09-20", out)
        self.assertIn("## 1. Posts to engage with", out)
        self.assertIn("## 2. Connections to DM today", out)
        self.assertIn("## 3. Extra networking actions", out)
        self.assertIn("## Data quality", out)
        self.assertIn("1 contact rows have a non-empty Last touch", out)
        self.assertTrue(out.rstrip().endswith("Draft-only: nothing was sent, posted, or logged."))
        self.assertNotIn("—", out)
        self.assertNotIn("–", out)

    def test_main_with_posts_json_renders_post_table(self):
        code, out, _ = run_main(
            ["--network", str(NETWORK), "--pipeline", str(PIPELINE),
             "--posts-json", str(FIXTURES / "brief_posts_flat.json"),
             "--today", "2026-09-20", "--config", "/nonexistent/config.yaml"])

        self.assertEqual(0, code)
        self.assertIn("Pat Poster", out)
        self.assertIn("12/3", out)
        self.assertIn("growth, seo", out)
        self.assertIn("A long post about growth engineering that runs well past seventy chara", out)

    def test_main_json_shape_and_missing_cli_warning(self):
        code, out, _ = run_main(
            ["--network", str(NETWORK), "--pipeline", str(PIPELINE), "--json",
             "--today", "2026-09-20", "--config", "/nonexistent/config.yaml"],
            env={"JSB_LINKEDIN_SCOUT_CLI": "/nonexistent/cli.py"})
        data = json.loads(out)

        self.assertEqual(0, code)
        self.assertEqual({"date", "posts", "dms", "actions", "warnings"}, set(data))
        self.assertEqual("2026-09-20", data["date"])
        self.assertEqual([], data["posts"])
        self.assertTrue(any("Posts unavailable" in w for w in data["warnings"]))

    def test_script_never_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = set(Path(tmp).iterdir())
            run_main(["--network", str(NETWORK), "--pipeline", str(PIPELINE), "--no-posts",
                      "--today", "2026-09-20"], cwd=tmp)

            self.assertEqual(before, set(Path(tmp).iterdir()))


if __name__ == "__main__":
    unittest.main()
