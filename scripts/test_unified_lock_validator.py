#!/usr/bin/env python3
"""Lint = dry-run lock: recursive-lock and lint-recursive-run share one validator.

Regression pins for the wireguard-warp-restore friction where artifacts that
linted clean failed at lock time because recursive-lock enforced STRICT-profile
checks the standalone lint skipped (singular STRICT_WORKFLOW_PROFILE vs plural
STRICT_WORKFLOW_PROFILES).
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
LINT_PATH = SCRIPTS / "lint-recursive-run.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


lint = load_module("unified_validator_lint", LINT_PATH)


def legacy_requirements_artifact(run_id: str) -> str:
    return "\n".join(
        [
            "Run: `/.recursive/run/{run_id}/`".format(run_id=run_id),
            "Phase: `00 Requirements`",
            "Status: `DRAFT`",
            "Inputs:",
            "- `none`",
            "Outputs:",
            "- `/.recursive/run/{run_id}/00-requirements.md`".format(run_id=run_id),
            "Scope note: Pins the requirement set for the run.",
            "",
            "## TODO",
            "",
            "- [x] Record requirements",
            "",
            "## Requirements",
            "",
            "- R1 | The product shall start.",
            "",
            "## Out of Scope",
            "",
            "- Nothing is out of scope.",
            "",
            "## Constraints",
            "",
            "- Keep the change minimal.",
            "",
            "## Coverage Gate",
            "",
            "Coverage: PASS",
            "",
            "## Approval Gate",
            "",
            "Approval: PASS",
            "",
        ]
    )


def mid_flight_artifact(run_id: str) -> str:
    """Structurally valid legacy draft with lock-only completion gaps."""
    return "\n".join(
        [
            "Run: `/.recursive/run/{run_id}/`".format(run_id=run_id),
            "Phase: `00 Requirements`",
            "Status: `DRAFT`",
            "Inputs:",
            "- `none`",
            "Outputs:",
            "- `/.recursive/run/{run_id}/00-requirements.md`".format(run_id=run_id),
            "Scope note: Work in progress draft.",
            "",
            "## TODO",
            "",
            "- [ ] Finish requirement capture",
            "",
            "## Requirements",
            "",
            "- R1 | The product shall start.",
            "",
            "## Out of Scope",
            "",
            "- Nothing is out of scope.",
            "",
            "## Constraints",
            "",
            "- Keep the change minimal.",
            "",
            "## Coverage Gate",
            "",
            "Coverage: FAIL",
            "",
            "## Approval Gate",
            "",
            "Approval: FAIL",
            "",
        ]
    )


def v2_root_cause_artifact(run_id: str, *, audit_gate: str) -> str:
    """Audited-phase artifact valid in every respect except the Audit gate."""

    def section(title: str, body: str) -> str:
        return f"## {title}\n\n{body}"

    audit_context = "\n".join(
        [
            "- Audit Execution Mode: self-audit",
            "- Subagent Availability: unavailable",
            "- Subagent Capability Probe: `No delegated audit tooling in this fixture environment.`",
            "- Delegation Decision Basis: `Fixture run keeps the audit self-performed.`",
            "- Audit Inputs Provided: run artifacts under `/.recursive/run/{run_id}/`".format(run_id=run_id),
        ]
    )
    diff_basis = "\n".join(
        [
            "- Baseline type: `local commit`",
            "- Baseline reference: `0123456789abcdef0123456789abcdef01234567`",
            "- Comparison reference: `working-tree`",
            "- Normalized baseline: `0123456789abcdef0123456789abcdef01234567`",
            "- Normalized comparison: `working-tree`",
            "- Normalized diff command: `git diff --name-only 0123456789abcdef0123456789abcdef01234567`",
        ]
    )
    requirement_completion = "\n".join(
        [
            "- R1 | Status: blocked | Rationale: Root cause analysis has not concluded yet. | Blocking Evidence: `/.recursive/run/{run_id}/00-requirements.md`".format(run_id=run_id),
        ]
    )
    sections = [
        section(
            "TODO",
            "\n".join(
                [
                    "- [x] Reproduce the failure",
                    "- [x] Trace the data flow",
                    "- [x] Record the root cause summary",
                ]
            ),
        ),
        section("Error Analysis", "- The failure originates in the startup path."),
        section("Reproduction Verification", "- Reproduced with the novice-runnable steps."),
        section("Recent Changes Analysis", "- No recent changes contributed to the failure."),
        section("Evidence Gathering (Multi-Layer if applicable)", "- Log evidence captured for the failing path."),
        section("Data Flow Trace", "- Data flows from the entrypoint into the failing module."),
        section("Pattern Analysis", "- Matches the known startup-order failure pattern."),
        section("Hypothesis Testing", "- Hypothesis confirmed by targeted reproduction."),
        section("Root Cause Summary", "- The root cause is the startup ordering defect."),
        section(
            "Audit Context",
            audit_context,
        ),
        section("Effective Inputs Re-read", "- `/.recursive/run/{run_id}/00-requirements.md`".format(run_id=run_id)),
        section("Earlier Phase Reconciliation", "- Reconciled against the locked Phase 0 artifacts."),
        section("Subagent Contribution Verification", "- No subagent work was delegated for this phase."),
        section("Worktree Diff Audit", diff_basis),
        section("Gaps Found", "- None; the analysis is complete."),
        section("Repair Work Performed", "- No repair was required at this phase."),
        section("Requirement Completion Status", requirement_completion),
        section("Prior Recursive Evidence Reviewed", "- None relevant because this is the first analysis phase of the run."),
        section("Audit Verdict", f"Audit: {audit_gate}"),
        section("Traceability", "- R1 | Root cause analysis covers the startup requirement."),
        section("Coverage Gate", "\nCoverage: PASS"),
        section("Approval Gate", "\nApproval: PASS"),
    ]
    header = "\n".join(
        [
            "Run: `/.recursive/run/{run_id}/`".format(run_id=run_id),
            "Phase: `01.5 Root Cause`",
            "Status: `DRAFT`",
            "Inputs:",
            "- `/.recursive/run/{run_id}/00-requirements.md`".format(run_id=run_id),
            "Outputs:",
            "- `/.recursive/run/{run_id}/01.5-root-cause.md`".format(run_id=run_id),
            "Scope note: Pins the root cause before planning.",
            "",
        ]
    )
    return header + "\n\n".join(sections) + "\n"


class UnifiedLockValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="unified-lock-validator-"))
        self.repo_root = self.temp_dir / "repo"
        self.run_id = "validator-run"
        self.run_dir = self.repo_root / ".recursive" / "run" / self.run_id
        self.run_dir.mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=str(self.repo_root), capture_output=True, check=True)

        # Strict-profile lint walks the memory plane; provide the skeleton.
        memory_root = self.repo_root / ".recursive" / "memory"
        memory_root.mkdir(parents=True, exist_ok=True)
        (memory_root / "skills").mkdir(parents=True, exist_ok=True)
        (memory_root / "MEMORY.md").write_text("# Memory\n", encoding="utf-8", newline="\n")
        (memory_root / "skills" / "SKILLS.md").write_text("# Skills\n", encoding="utf-8", newline="\n")
        for subdir in ("domains", "patterns", "incidents", "episodes", "archive", "skills/availability", "skills/usage", "skills/issues", "skills/patterns"):
            (memory_root / subdir).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), *args],
            text=True,
            capture_output=True,
            check=False,
            cwd=str(self.repo_root),
        )

    def _lock_args(self, artifact: str) -> list[str]:
        return ["--repo-root", ".", "--run-id", self.run_id, "--artifact", artifact]

    def test_mid_flight_draft_lints_clean_but_as_lock_and_lock_refuse(self) -> None:
        artifact = self.run_dir / "00-requirements.md"
        artifact.write_text(mid_flight_artifact(self.run_id), encoding="utf-8", newline="\n")

        default_lint = self._run("lint-recursive-run.py", "--repo-root", ".", "--run-id", self.run_id)
        self.assertEqual(
            0,
            default_lint.returncode,
            f"Mid-flight draft must lint clean by default:\n{default_lint.stdout}",
        )
        self.assertIn("[WARN]", default_lint.stdout)
        self.assertIn("Coverage gate must be PASS before locking", default_lint.stdout)
        self.assertIn("Unchecked TODO items remain: 1", default_lint.stdout)

        as_lock = self._run("lint-recursive-run.py", "--repo-root", ".", "--run-id", self.run_id, "--as-lock")
        self.assertNotEqual(0, as_lock.returncode)
        self.assertIn("Coverage gate must be PASS before locking", as_lock.stdout)
        self.assertIn("Unchecked TODO items remain: 1", as_lock.stdout)

        strict = self._run("lint-recursive-run.py", "--repo-root", ".", "--run-id", self.run_id, "--strict")
        self.assertNotEqual(0, strict.returncode)

        lock = self._run("recursive-lock.py", *self._lock_args("00-requirements.md"))
        self.assertNotEqual(0, lock.returncode)
        self.assertIn("Coverage gate must be PASS before locking", lock.stdout)
        self.assertIn("Unchecked TODO items remain: 1", lock.stdout)

    def test_lock_accepts_what_as_lock_lint_accepts(self) -> None:
        artifact = self.run_dir / "00-requirements.md"
        artifact.write_text(legacy_requirements_artifact(self.run_id), encoding="utf-8", newline="\n")

        as_lock = self._run("lint-recursive-run.py", "--repo-root", ".", "--run-id", self.run_id, "--as-lock")
        self.assertEqual(0, as_lock.returncode, as_lock.stdout)

        lock = self._run("recursive-lock.py", *self._lock_args("00-requirements.md"))
        self.assertEqual(0, lock.returncode, lock.stdout)
        self.assertIn("[OK] Locked", lock.stdout)

    def test_v2_run_audit_gate_enforced_by_both_tools(self) -> None:
        """The singular-vs-plural STRICT profile predicate divergence.

        Under recursive-mode-audit-v2, an audited phase without Audit: PASS must
        be refused by recursive-lock AND reported by lint --as-lock. The old
        recursive-lock used the singular profile constant and silently accepted
        this artifact after a clean lint.
        """
        requirements = legacy_requirements_artifact(self.run_id).replace(
            "Run: `/.recursive/run/",
            "Workflow version: recursive-mode-audit-v2\nRun: `/.recursive/run/",
        )
        (self.run_dir / "00-requirements.md").write_text(requirements, encoding="utf-8", newline="\n")
        artifact = self.run_dir / "01.5-root-cause.md"
        artifact.write_text(v2_root_cause_artifact(self.run_id, audit_gate="FAIL"), encoding="utf-8", newline="\n")

        prerequisites = self._run("recursive-lock.py", *self._lock_args("00-requirements.md"))
        self.assertEqual(0, prerequisites.returncode, prerequisites.stdout)

        lock = self._run("recursive-lock.py", *self._lock_args("01.5-root-cause.md"))
        self.assertNotEqual(0, lock.returncode, f"Lock must refuse without Audit: PASS:\n{lock.stdout}")
        self.assertIn("Audit gate must be PASS before locking this audited phase", lock.stdout)

        as_lock = self._run("lint-recursive-run.py", "--repo-root", ".", "--run-id", self.run_id, "--as-lock")
        self.assertNotEqual(0, as_lock.returncode)
        self.assertIn("Audit gate must be PASS before locking this audited phase", as_lock.stdout)

    def test_audit_pass_v2_artifact_passes_both_tools(self) -> None:
        requirements = legacy_requirements_artifact(self.run_id).replace(
            "Run: `/.recursive/run/",
            "Workflow version: recursive-mode-audit-v2\nRun: `/.recursive/run/",
        )
        (self.run_dir / "00-requirements.md").write_text(requirements, encoding="utf-8", newline="\n")
        artifact = self.run_dir / "01.5-root-cause.md"
        artifact.write_text(v2_root_cause_artifact(self.run_id, audit_gate="PASS"), encoding="utf-8", newline="\n")

        prerequisites = self._run("recursive-lock.py", *self._lock_args("00-requirements.md"))
        self.assertEqual(0, prerequisites.returncode, prerequisites.stdout)

        as_lock = self._run("lint-recursive-run.py", "--repo-root", ".", "--run-id", self.run_id, "--as-lock")
        self.assertEqual(0, as_lock.returncode, as_lock.stdout)

        lock = self._run("recursive-lock.py", *self._lock_args("01.5-root-cause.md"))
        self.assertEqual(0, lock.returncode, lock.stdout)

    def test_stale_lock_reported_in_as_lock_mode(self) -> None:
        artifact = self.run_dir / "00-requirements.md"
        artifact.write_text(legacy_requirements_artifact(self.run_id), encoding="utf-8", newline="\n")
        lock = self._run("recursive-lock.py", *self._lock_args("00-requirements.md"))
        self.assertEqual(0, lock.returncode, lock.stdout)

        content = artifact.read_text(encoding="utf-8").replace("Keep the change minimal.", "Keep the change minimal and audited.")
        artifact.write_text(content, encoding="utf-8", newline="\n")

        as_lock = self._run("lint-recursive-run.py", "--repo-root", ".", "--run-id", self.run_id, "--as-lock")
        self.assertNotEqual(0, as_lock.returncode)
        self.assertIn("LockHash no longer matches", as_lock.stdout)

        relock = self._run("recursive-lock.py", *self._lock_args("00-requirements.md"))
        self.assertNotEqual(0, relock.returncode)
        self.assertIn("already LOCKED but its lock metadata is invalid", relock.stdout)

    def test_collector_uses_plural_strict_profile_set(self) -> None:
        run_dir = self.run_dir
        artifact = run_dir / "01.5-root-cause.md"
        content = v2_root_cause_artifact(self.run_id, audit_gate="FAIL")
        artifact.write_text(content, encoding="utf-8", newline="\n")
        (run_dir / "00-requirements.md").write_text(legacy_requirements_artifact(self.run_id), encoding="utf-8", newline="\n")

        for profile in (lint.STRICT_WORKFLOW_PROFILE, lint.CURRENT_WORKFLOW_PROFILE):
            issues = lint.collect_lock_blockers(
                artifact,
                content,
                run_dir,
                self.repo_root,
                profile,
                ["R1"],
                None,
                None,
            )
            messages = {issue.message for issue in issues}
            self.assertIn(
                "Audit gate must be PASS before locking this audited phase",
                messages,
                f"profile {profile} must enforce the audit gate",
            )

        legacy_issues = lint.collect_lock_blockers(
            artifact,
            content,
            run_dir,
            self.repo_root,
            "legacy",
            ["R1"],
            None,
            None,
        )
        self.assertNotIn(
            "Audit gate must be PASS before locking this audited phase",
            {issue.message for issue in legacy_issues},
        )

    def test_is_lock_valid_for_lint_matches_lock_decision(self) -> None:
        artifact = self.run_dir / "00-requirements.md"
        artifact.write_text(legacy_requirements_artifact(self.run_id), encoding="utf-8", newline="\n")
        self.assertFalse(lint.is_lock_valid_for_lint(artifact, "legacy"))

        lock = self._run("recursive-lock.py", *self._lock_args("00-requirements.md"))
        self.assertEqual(0, lock.returncode, lock.stdout)
        self.assertTrue(lint.is_lock_valid_for_lint(artifact, "legacy", repo_root=self.repo_root, scaffold_root=self.repo_root))

        content = artifact.read_text(encoding="utf-8").replace("Keep the change minimal.", "Keep the change minimal and audited.")
        artifact.write_text(content, encoding="utf-8", newline="\n")
        self.assertFalse(lint.is_lock_valid_for_lint(artifact, "legacy", repo_root=self.repo_root, scaffold_root=self.repo_root))


if __name__ == "__main__":
    unittest.main()
