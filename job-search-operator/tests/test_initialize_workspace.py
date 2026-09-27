"""Behavioral tests for the safe job-search workspace initializer."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "initialize_workspace.py"
ASSETS_DIRECTORY = Path(__file__).parents[1] / "assets"


def load_initialize_module():
    spec = importlib.util.spec_from_file_location("initialize_workspace", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class InitializeWorkspaceTests(unittest.TestCase):
    def test_initialization_creates_the_five_workspace_files(self):
        initialize_workspace = load_initialize_module()

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "job-search-workspace"

            result = initialize_workspace.initialize_workspace(target)

            files = sorted(
                path.relative_to(target).as_posix()
                for path in target.rglob("*")
                if path.is_file()
            )
            self.assertEqual(
                [
                    "CAREER_FACTS.md",
                    "NETWORK.md",
                    "POSITIONING_LOG.md",
                    "README.md",
                    "applications/APPLICATION_TEMPLATE.md",
                ],
                files,
            )
            self.assertEqual(str(target.resolve()), result["workspace"])
            self.assertEqual(files, sorted(result["created"]))
            self.assertEqual([], result["preserved"])

    def test_existing_career_facts_are_preserved_and_reported(self):
        initialize_workspace = load_initialize_module()

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "job-search-workspace"
            target.mkdir()
            career_facts = target / "CAREER_FACTS.md"
            career_facts.write_text("Personal career facts\n", encoding="utf-8")

            result = initialize_workspace.initialize_workspace(target)

            self.assertEqual("Personal career facts\n", career_facts.read_text(encoding="utf-8"))
            self.assertIn("CAREER_FACTS.md", result["preserved"])
            self.assertNotIn("CAREER_FACTS.md", result["created"])

    def test_existing_target_symlink_is_rejected_without_writing_its_target(self):
        initialize_workspace = load_initialize_module()

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "job-search-workspace"
            external_directory = Path(directory).resolve() / "external"
            external_directory.mkdir()
            target.symlink_to(external_directory, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "unsafe target"):
                initialize_workspace.initialize_workspace(target)

            self.assertEqual([], list(external_directory.iterdir()))

    def test_dangling_destination_symlink_is_preserved_without_writing_its_target(self):
        initialize_workspace = load_initialize_module()

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "job-search-workspace"
            target.mkdir()
            career_facts = target / "CAREER_FACTS.md"
            link_target = target / "do-not-create-this-file"
            career_facts.symlink_to(link_target)

            result = initialize_workspace.initialize_workspace(target)

            self.assertTrue(career_facts.is_symlink())
            self.assertFalse(link_target.exists())
            self.assertIn("CAREER_FACTS.md", result["preserved"])
            self.assertNotIn("CAREER_FACTS.md", result["created"])

    def test_symlinked_applications_directory_is_rejected_without_external_write(self):
        initialize_workspace = load_initialize_module()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "job-search-workspace"
            target.mkdir()
            external_directory = root / "external"
            external_directory.mkdir()
            (target / "applications").symlink_to(external_directory, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "unsafe target"):
                initialize_workspace.initialize_workspace(target)

            self.assertEqual([], list(external_directory.iterdir()))

    def test_create_time_collision_preserves_the_race_winner(self):
        initialize_workspace = load_initialize_module()

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "job-search-workspace"
            readme = target / "README.md"
            original_open = initialize_workspace.os.open

            def create_race_winner(path, flags, mode=0o777, *, dir_fd=None):
                if path == "README.md" and dir_fd is not None:
                    readme.parent.mkdir(parents=True, exist_ok=True)
                    readme.write_text("race winner\n", encoding="utf-8")
                return original_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(initialize_workspace.os, "open", side_effect=create_race_winner):
                result = initialize_workspace.initialize_workspace(target)

            self.assertEqual("race winner\n", readme.read_text(encoding="utf-8"))
            self.assertIn("README.md", result["preserved"])
            self.assertNotIn("README.md", result["created"])

    def test_workspace_swap_after_directory_open_cannot_write_to_external_directory(self):
        initialize_workspace = load_initialize_module()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "job-search-workspace"
            target.mkdir()
            original_workspace = root / "pinned-workspace"
            external_directory = root / "external"
            external_directory.mkdir()
            original_open = initialize_workspace.os.open
            swapped = False

            def open_then_swap(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal swapped
                descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
                if path == target.name and flags & initialize_workspace.os.O_DIRECTORY:
                    target.rename(original_workspace)
                    target.symlink_to(external_directory, target_is_directory=True)
                    swapped = True
                return descriptor

            with mock.patch.object(initialize_workspace.os, "open", side_effect=open_then_swap):
                initialize_workspace.initialize_workspace(target)

            self.assertTrue(swapped)
            self.assertEqual([], list(external_directory.iterdir()))
            self.assertTrue((original_workspace / "README.md").is_file())

    def test_intermediate_parent_swap_during_traversal_cannot_write_externally(self):
        initialize_workspace = load_initialize_module()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            intermediate = root / "intermediate"
            intermediate.mkdir()
            target = intermediate / "job-search-workspace"
            original_intermediate = root / "pinned-intermediate"
            external_parent = root / "external"
            external_parent.mkdir()
            original_open = initialize_workspace.os.open
            swapped = False

            def open_then_swap(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal swapped
                descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
                if path == "intermediate" and flags & initialize_workspace.os.O_DIRECTORY:
                    intermediate.rename(original_intermediate)
                    intermediate.symlink_to(external_parent, target_is_directory=True)
                    swapped = True
                return descriptor

            with mock.patch.object(initialize_workspace.os, "open", side_effect=open_then_swap):
                initialize_workspace.initialize_workspace(target)

            self.assertTrue(swapped)
            self.assertEqual([], list(external_parent.iterdir()))
            self.assertTrue((original_intermediate / "job-search-workspace" / "README.md").is_file())

    def test_intermediate_swap_after_validation_cannot_retarget_workspace(self):
        initialize_workspace = load_initialize_module()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            intermediate = root / "intermediate"
            intermediate.mkdir()
            target = intermediate / "job-search-workspace"
            original_intermediate = root / "original-intermediate"
            external_parent = root / "external"
            external_parent.mkdir()
            original_reject = initialize_workspace.reject_symlink_components
            swapped = False

            def validate_then_swap(path):
                nonlocal swapped
                original_reject(path)
                if Path(path) == target and not swapped:
                    intermediate.rename(original_intermediate)
                    intermediate.symlink_to(external_parent, target_is_directory=True)
                    swapped = True

            with mock.patch.object(
                initialize_workspace,
                "reject_symlink_components",
                side_effect=validate_then_swap,
            ):
                with self.assertRaisesRegex(ValueError, "unsafe target"):
                    initialize_workspace.initialize_workspace(target)

            self.assertTrue(swapped)
            self.assertEqual([], list(external_parent.iterdir()))

    def test_home_directory_is_rejected_as_an_unsafe_target(self):
        initialize_workspace = load_initialize_module()

        with self.assertRaisesRegex(ValueError, "unsafe target"):
            initialize_workspace.initialize_workspace(Path.home())

    def test_symlink_loop_target_has_a_clean_unsafe_target_cli_error(self):
        with tempfile.TemporaryDirectory() as directory:
            loop = Path(directory).resolve() / "loop"
            loop.symlink_to(loop)

            completed = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(loop)],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(0, completed.returncode)
            self.assertIn("unsafe target", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)

    def test_descendant_of_symlink_loop_is_rejected_cleanly(self):
        initialize_workspace = load_initialize_module()

        with tempfile.TemporaryDirectory() as directory:
            loop = Path(directory).resolve() / "loop"
            loop.symlink_to(loop)
            target = loop / "workspace"

            with self.assertRaisesRegex(ValueError, "unsafe target"):
                initialize_workspace.initialize_workspace(target)

            completed = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(target)],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(0, completed.returncode)
            self.assertIn("unsafe target", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)

    def test_second_run_preserves_all_workspace_files(self):
        initialize_workspace = load_initialize_module()

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "job-search-workspace"
            initialize_workspace.initialize_workspace(target)

            result = initialize_workspace.initialize_workspace(target)

            self.assertEqual([], result["created"])
            self.assertEqual(
                [
                    "README.md",
                    "CAREER_FACTS.md",
                    "NETWORK.md",
                    "POSITIONING_LOG.md",
                    "applications/APPLICATION_TEMPLATE.md",
                ],
                result["preserved"],
            )

    def test_assets_do_not_include_candidate_specific_terms(self):
        private_terms = (
            "sprintz",
            "pendo",
            "carrot",
            "kiddom",
            "andersen",
            "revel",
            "510-305",
            "rl22",
            "rodlew",
        )

        asset_text = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in sorted(ASSETS_DIRECTORY.glob("*-template.md"))
        )

        for private_term in private_terms:
            with self.subTest(private_term=private_term):
                self.assertNotIn(private_term, asset_text)


if __name__ == "__main__":
    unittest.main()
