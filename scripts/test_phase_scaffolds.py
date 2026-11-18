#!/usr/bin/env python3
"""Scaffolds for every artifact: closeout phases 0-8 and the phase-aware
recursive-action-record helper.

Pins the wireguard-warp-restore friction fix: recursive-closeout previously
covered only Phases 4-8, leaving Phases 0-3 artifacts, subagent action records,
and review bundles to be authored blind against lint rules.
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


lint = load_module("phase_scaffolds_lint", SCRIPTS / "lint-recursive-run.py")
closeout = load_module("phase_scaffolds_closeout", SCRIPTS / "recursive-closeout.py")
action_record = load_module("phase_scaffolds_action_record", SCRIPTS / "recursive-action-record.py")

PHASE_KEYS = ["00R", "00W", "01", "01.5", "02", "03", "03.5", "04", "05", "06", "07", "08"]


class PhaseAliasTests(unittest.TestCase):
    def test_closeout_resolves_all_phase_keys(self) -> None:
        for key in PHASE_KEYS:
            self.assertEqual(key, closeout.resolve_phase_key(key), key)

    def test_closeout_resolves_artifact_names_and_labels(self) -> None:
        self.assertEqual("01.5", closeout.resolve_phase_key("01.5-root-cause.md"))
        self.assertEqual("03.5", closeout.resolve_phase_key("Code-Review"))
        self.assertEqual("00R", closeout.resolve_phase_key("requirements"))
        self.assertEqual("00W", closeout.resolve_phase_key("00-worktree"))
        self.assertEqual("08", closeout.resolve_phase_key("08-memory-impact.md"))

    def test_action_record_resolves_phases(self) -> None:
        self.assertEqual(("01.5-root-cause.md", "01.5 Root Cause"), action_record.resolve_phase("01.5"))
        self.assertEqual(("01.5-root-cause.md", "01.5 Root Cause"), action_record.resolve_phase("01.5-root-cause.md"))
        self.assertEqual(("04-test-summary.md", "04 Test Summary"), action_record.resolve_phase("04 Test Summary"))
        self.assertEqual(("02-to-be-plan.md", "02 TO-BE Plan"), action_record.resolve_phase("to-be-plan"))
        with self.assertRaises(ValueError):
            action_record.resolve_phase("00")  # ambiguous between requirements and worktree
        with self.assertRaises(ValueError):
            action_record.resolve_phase("99")


class CloseoutScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="phase-scaffolds-"))
        self.repo_root = self.temp_dir / "repo"
        self.run_id = "scaffold-run"
        self.run_dir = self.repo_root / ".recursive" / "run" / self.run_id
        self.run_dir.mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=str(self.repo_root), capture_output=True, check=True)

        # Scaffolding the late phases switches the run to the memory-phase8
        # profile, whose lint walks the memory plane; provide the skeleton.
        memory_root = self.repo_root / ".recursive" / "memory"
        memory_root.mkdir(parents=True, exist_ok=True)
        (memory_root / "skills").mkdir(parents=True, exist_ok=True)
        (memory_root / "MEMORY.md").write_text("# Memory\n", encoding="utf-8", newline="\n")
        (memory_root / "skills" / "SKILLS.md").write_text("# Skills\n", encoding="utf-8", newline="\n")
        for subdir in ("domains", "patterns", "incidents", "episodes", "archive", "skills/availability", "skills/usage", "skills/issues", "skills/patterns"):
            (memory_root / subdir).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _scaffold(self, phase: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable, str(SCRIPTS / "recursive-closeout.py"),
                "--repo-root", str(self.repo_root),
                "--run-id", self.run_id,
                "--phase", phase,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_every_phase_scaffolds_all_required_sections(self) -> None:
        for key in PHASE_KEYS:
            file_name = closeout.PHASE_CONFIG[key]["file_name"]
            result = self._scaffold(key)
            self.assertEqual(0, result.returncode, f"phase {key}: {result.stdout}{result.stderr}")
            artifact = self.run_dir / file_name
            self.assertTrue(artifact.exists(), f"phase {key} did not write {file_name}")

            content = artifact.read_text(encoding="utf-8")
            workflow_profile = lint.get_workflow_profile(self.run_dir)
            for heading in lint.get_artifact_required_sections(file_name, workflow_profile):
                self.assertIn(f"## {heading}", content, f"phase {key} scaffold is missing ## {heading}")
            for field in ("Run:", "Phase:", "Status:", "Inputs:", "Outputs:", "Scope note:"):
                self.assertIn(field, content, f"phase {key} scaffold header is missing {field}")

    def test_phase_scaffold_sequence_lints_clean_of_structure_failures(self) -> None:
        """Scaffold every phase in order; the only lint FAILs must be
        phase-sequence violations (inherent to draft scaffolds), never missing
        sections, missing fields, or untraceable requirements."""
        for key in PHASE_KEYS:
            result = self._scaffold(key)
            self.assertEqual(0, result.returncode, f"phase {key}: {result.stdout}{result.stderr}")

        lint_result = subprocess.run(
            [sys.executable, str(SCRIPTS / "lint-recursive-run.py"), "--repo-root", str(self.repo_root), "--run-id", self.run_id],
            text=True,
            capture_output=True,
            check=False,
        )
        non_sequence = [
            line
            for line in lint_result.stdout.splitlines()
            if line.startswith("[FAIL]")
            and "Phase-sequence violation" not in line
            and line != "[FAIL] Lint failed"
        ]
        self.assertEqual(
            [],
            non_sequence,
            "scaffolds must be lint-aligned on first write:\n" + "\n".join(non_sequence),
        )

    def test_phase_03_scaffold_carries_strict_tdd_schema(self) -> None:
        result = self._scaffold("03")
        self.assertEqual(0, result.returncode, result.stdout)
        content = (self.run_dir / "03-implementation-summary.md").read_text(encoding="utf-8")
        self.assertIn("- TDD Mode: strict", content)
        self.assertIn("- RED Evidence:", content)
        self.assertIn("- GREEN Evidence:", content)
        self.assertIn(f".recursive/run/{self.run_id}/evidence/logs/red/", content)
        self.assertIn(f".recursive/run/{self.run_id}/evidence/logs/green/", content)
        self.assertTrue((self.run_dir / "evidence" / "logs" / "red").is_dir())
        self.assertTrue((self.run_dir / "evidence" / "logs" / "green").is_dir())

    def test_phase_03_5_scaffold_carries_review_bundle_metadata(self) -> None:
        result = self._scaffold("03.5")
        self.assertEqual(0, result.returncode, result.stdout)
        content = (self.run_dir / "03.5-code-review.md").read_text(encoding="utf-8")
        self.assertIn("- Review Bundle Path: `", content)
        self.assertIn(f".recursive/run/{self.run_id}/evidence/review-bundles/", content)
        self.assertIn("recursive-review-bundle.py", content)

    def test_phase_00_worktree_scaffold_carries_executable_diff_basis_fields(self) -> None:
        result = self._scaffold("00W")
        self.assertEqual(0, result.returncode, result.stdout)
        content = (self.run_dir / "00-worktree.md").read_text(encoding="utf-8")
        for field in ("Baseline type:", "Baseline reference:", "Comparison reference:", "Normalized baseline:", "Normalized comparison:", "Normalized diff command:"):
            self.assertIn(f"- {field}", content)


class ActionRecordHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="action-record-helper-"))
        self.repo_root = self.temp_dir / "repo"
        self.run_id = "record-run"
        self.run_dir = self.repo_root / ".recursive" / "run" / self.run_id
        self.run_dir.mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=str(self.repo_root), capture_output=True, check=True)
        (self.run_dir / "01-as-is.md").write_text(
            "\n".join(
                [
                    "Run: `/.recursive/run/%s/`" % self.run_id,
                    "Phase: `01 AS-IS Analysis`",
                    "Status: `DRAFT`",
                    "Inputs:",
                    "- `none`",
                    "Outputs:",
                    "- `/.recursive/run/%s/01-as-is.md`" % self.run_id,
                    "Scope note: Fixture artifact for action record discovery.",
                ]
            ),
            encoding="utf-8",
            newline="\n",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable, str(SCRIPTS / "recursive-action-record.py"),
                "--repo-root", str(self.repo_root),
                "--run-id", self.run_id,
                "--subagent-id", "analyst-1",
                "--purpose", "Trace the startup failure",
                *extra,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_phase_aware_record_prefills_upstream_and_label(self) -> None:
        result = self._run("--phase", "01.5")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("Phase: 01.5 Root Cause", result.stdout)
        self.assertIn("Auto-discovered upstream artifacts: 1", result.stdout)

        records = sorted((self.run_dir / "subagents").glob("*.md"))
        self.assertEqual(1, len(records))
        content = records[0].read_text(encoding="utf-8")
        self.assertIn("- Phase: `01.5 Root Cause`", content)
        self.assertIn("- `/.recursive/run/%s/01-as-is.md`" % self.run_id, content)
        self.assertIn("- Phase 01.5 Root Cause: Trace the startup failure", content)
        # Same canonical schema as recursive-subagent-action.py
        self.assertIn("# Subagent Action Record", content)
        self.assertIn("## Claimed File Impact", content)
        self.assertIn("## Verification Handoff", content)

    def test_record_uses_same_schema_module_as_canonical_cli(self) -> None:
        """Schema parity: the helper delegates to recursive-subagent-action."""
        self.assertEqual(
            action_record.subagent_action.__file__,
            str(SCRIPTS / "recursive-subagent-action.py"),
        )

    def test_no_auto_upstream_disables_discovery(self) -> None:
        result = self._run("--phase", "01.5", "--no-auto-upstream")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("Auto-discovered upstream artifacts: 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
