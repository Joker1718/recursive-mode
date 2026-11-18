#!/usr/bin/env python3
"""Schema-typed path-field parsing and the --explain-field diagnostic.

Pins the wireguard-warp-restore friction: the old extractor treated any
backticked token containing "/" or "." as a path that must exist, so prose in
path fields (parentheticals, "none required.", URLs) produced repeated false
failures, and the only way to see what the extractor did was to fail lint.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "recursive-mode" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


lint = load_module("path_fields_lint", SCRIPTS / "lint-recursive-run.py")


class ClassifyPathTokenTests(unittest.TestCase):
    def test_real_paths_are_kept(self) -> None:
        for token in ("src/lib.rs", "04-test-summary.md", ".recursive/run/x/y.md", "/abs-ish/path file.txt" if False else "src/app/main.tsx", "package.json"):
            self.assertEqual("path", lint.classify_path_token(token).decision, token)

    def test_none_style_markers_are_skipped(self) -> None:
        for token in ("none", "None.", "N/A", "n/a.", "(none required)", "none required.", "TBD", "no changes."):
            decision = lint.classify_path_token(token)
            self.assertEqual("skipped", decision.decision, token)
            self.assertIn("none-style", decision.reason, token)

    def test_parentheticals_are_skipped_as_prose(self) -> None:
        for token in ("(update before locking)", "(see 00-requirements.md)", "see notes below", "populate the owned changed files before locking"):
            decision = lint.classify_path_token(token)
            self.assertEqual("skipped", decision.decision, token)
            self.assertIn("prose", decision.reason, token)

    def test_urls_emails_and_versions_are_skipped(self) -> None:
        self.assertEqual("skipped", lint.classify_path_token("https://github.com/example/repo").decision)
        self.assertEqual("skipped", lint.classify_path_token("ci@example.com").decision)
        self.assertEqual("skipped", lint.classify_path_token("v1.2.3").decision)
        self.assertEqual("skipped", lint.classify_path_token("3.5").decision)

    def test_git_commands_and_placeholders_are_skipped(self) -> None:
        self.assertEqual("skipped", lint.classify_path_token("git diff --name-only abc123").decision)
        self.assertEqual("skipped", lint.classify_path_token("<update-before-locking>").decision)

    def test_multi_path_span_without_prose_is_kept(self) -> None:
        decision = lint.classify_path_token("src/lib.rs tests/lib.rs")
        self.assertEqual("path", decision.decision)


class ExtractorBehaviorTests(unittest.TestCase):
    def test_field_value_with_prose_and_real_path_keeps_only_the_path(self) -> None:
        value = "implemented in `src/lib.rs` (see 00-requirements.md for the requirement text)"
        self.assertEqual({"src/lib.rs"}, lint.extract_paths_from_text(value))

    def test_none_required_value_extracts_nothing(self) -> None:
        self.assertEqual(set(), lint.extract_paths_from_field_value("none required."))
        self.assertEqual(set(), lint.extract_paths_from_text("`None.`"))

    def test_bare_list_without_backticks_still_parses(self) -> None:
        self.assertEqual({"src/lib.rs", "src/main.rs"}, lint.extract_paths_from_field_value("src/lib.rs, src/main.rs"))

    def test_nonexistent_real_path_is_still_reported(self) -> None:
        # The classifier only removes prose false positives; genuinely missing
        # paths must still fail existence checks.
        self.assertIn("src/does-not-exist/lib.rs", lint.extract_paths_from_text("`src/does-not-exist/lib.rs`"))


class ExplainFieldCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="explain-field-"))
        self.repo_root = self.temp_dir / "repo"
        self.run_id = "explain-run"
        self.run_dir = self.repo_root / ".recursive" / "run" / self.run_id
        self.run_dir.mkdir(parents=True)
        (self.run_dir / "03-implementation-summary.md").write_text(
            "\n".join(
                [
                    "Run: `/.recursive/run/%s/`" % self.run_id,
                    "Phase: `03 Implementation`",
                    "Status: `DRAFT`",
                    "Inputs:",
                    "- `none`",
                    "Outputs:",
                    "- `/.recursive/run/%s/03-implementation-summary.md`" % self.run_id,
                    "Scope note: Fixture for the explain-field diagnostic.",
                    "",
                    "## TODO",
                    "",
                    "- [x] Record changes",
                    "",
                    "## Changes Applied",
                    "",
                    "- `src/lib.rs` | startup fix",
                    "",
                    "## Implementation Evidence",
                    "",
                    "- Implementation Evidence:",
                    "  - `src/lib.rs`",
                    "  - `https://ci.example.com/build/123`",
                    "  - `(see 00-requirements.md)`",
                    "  - `none required.`",
                ]
            ),
            encoding="utf-8",
            newline="\n",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "lint-recursive-run.py"), "--repo-root", str(self.repo_root), "--run-id", self.run_id, *extra],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_explain_field_shows_token_decisions(self) -> None:
        result = self._run("--explain-field", "Implementation Evidence")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("[PATH]    src/lib.rs", result.stdout)
        self.assertIn("[SKIPPED] https://ci.example.com/build/123  (URL)", result.stdout)
        self.assertIn("[SKIPPED] see 00-requirements.md  (prose sentence, not a path)", result.stdout)
        self.assertIn("[SKIPPED] none required  (none-style marker)", result.stdout)
        self.assertIn("Extracted path set (1):", result.stdout)
        self.assertIn("- src/lib.rs", result.stdout)

    def test_explain_field_scoped_to_one_artifact(self) -> None:
        result = self._run("--explain-field", "Inputs", "--artifact", "03-implementation-summary.md")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("[SKIPPED] none  (none-style marker)", result.stdout)
        self.assertIn("Extracted path set (0):", result.stdout)

    def test_explain_field_missing_field_fails_clearly(self) -> None:
        result = self._run("--explain-field", "Not A Field")
        self.assertEqual(1, result.returncode)
        self.assertIn("was not found in any artifact in scope", result.stdout)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
