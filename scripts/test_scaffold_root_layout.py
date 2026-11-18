#!/usr/bin/env python3
"""Split-layout (scaffold root != repo root) coverage for recursive-mode tools.

Covers the nested-repo layout from the wireguard-warp-restore run: the run
scaffold (owner of .recursive/) lives at a workspace root beside a nested
product clone.  recursive-lock and recursive-closeout used to crash with
`relative_to` tracebacks in this layout; these tests pin the fixed behavior.
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


phase_rules = load_module("recursive_phase_rules_layout_test", SCRIPTS / "recursive_phase_rules.py")


VALID_REQUIREMENTS = "\n".join(
    [
        "Run: `/.recursive/run/{run_id}/`",
        "Phase: `00 Requirements`",
        "Status: `DRAFT`",
        "Inputs:",
        "- `none`",
        "Outputs:",
        "- `/.recursive/run/{run_id}/00-requirements.md`",
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
        "- Nothing is out of scope for this smoke run.",
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


VALID_WORKTREE = "\n".join(
    [
        "Run: `/.recursive/run/{run_id}/`",
        "Phase: `00 Worktree Setup`",
        "Status: `DRAFT`",
        "Inputs:",
        "- `/.recursive/run/{run_id}/00-requirements.md`",
        "Outputs:",
        "- `/.recursive/run/{run_id}/00-worktree.md`",
        "Scope note: Records the isolated worktree and the executable diff basis.",
        "",
        "## TODO",
        "",
        "- [x] Set up the worktree and record the diff basis",
        "",
        "## Directory Selection",
        "",
        "- Location: `{worktree}`",
        "",
        "## Safety Verification",
        "",
        "- Verified the working tree is clean before creating the worktree.",
        "",
        "## Worktree Creation",
        "",
        "- Created the worktree on branch `recursive/{run_id}`.",
        "",
        "## Main Branch Protection",
        "",
        "- Main branch was not checked out in the worktree.",
        "",
        "## Project Setup",
        "",
        "- No additional project setup was required.",
        "",
        "## Test Baseline Verification",
        "",
        "- Baseline test command recorded for later phases: `none (fixture run)`.",
        "",
        "## Worktree Context",
        "",
        "- Product root: `{worktree}`",
        "",
        "## Diff Basis For Later Audits",
        "",
        "- Baseline type: `local commit`",
        "- Baseline reference: `{baseline}`",
        "- Comparison reference: `working-tree`",
        "- Normalized baseline: `{baseline}`",
        "- Normalized comparison: `working-tree`",
        "- Normalized diff command: `git diff --name-only {baseline}`",
        "",
        "## Traceability",
        "",
        "- Requirements traceability: R1 covered by this setup receipt.",
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


class ScaffoldRootHelperTests(unittest.TestCase):
    def test_resolve_scoped_path_routes_recursive_paths_to_scaffold_root(self) -> None:
        repo_root = Path("/fake/repo")
        scaffold_root = Path("/fake/scaffold")
        self.assertEqual(
            Path("/fake/scaffold/.recursive/run/x/03.md"),
            phase_rules.resolve_scoped_path(repo_root, ".recursive/run/x/03.md", scaffold_root),
        )
        self.assertEqual(
            Path("/fake/repo/src/lib.rs"),
            phase_rules.resolve_scoped_path(repo_root, "/src/lib.rs", scaffold_root),
        )
        self.assertEqual(
            Path("/fake/repo/src/lib.rs"),
            phase_rules.resolve_scoped_path(repo_root, "src/lib.rs"),
        )

    def test_display_repo_path_never_raises_outside_roots(self) -> None:
        with tempfile.TemporaryDirectory(prefix="display-path-") as temp:
            inside = Path(temp) / "a" / "file.txt"
            inside.parent.mkdir(parents=True)
            inside.write_text("x", encoding="utf-8")
            outside = Path(temp) / "b" / "elsewhere.txt"
            outside.parent.mkdir(parents=True)
            outside.write_text("y", encoding="utf-8")
            self.assertEqual("a/file.txt", phase_rules.display_repo_path(inside, Path(temp)))
            # Falls back to the absolute path instead of raising.
            self.assertTrue(phase_rules.display_repo_path(outside, Path(temp) / "a").startswith("/"))

    def test_display_repo_path_handles_symlinked_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="display-symlink-") as temp:
            real_root = Path(temp) / "real"
            (real_root / "run").mkdir(parents=True)
            target = real_root / "run" / "artifact.md"
            target.write_text("x", encoding="utf-8")
            link_root = Path(temp) / "link"
            link_root.symlink_to(real_root)
            # Lexical and resolved variants both resolve to a relative display.
            self.assertEqual("run/artifact.md", phase_rules.display_repo_path(target, link_root))
            self.assertEqual("run/artifact.md", phase_rules.display_repo_path(target, real_root))


class SplitLayoutToolTests(unittest.TestCase):
    """End-to-end runs against workspace scaffold + nested product clone."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="scaffold-root-test-"))
        self.workspace = self.temp_dir / "workspace"
        self.product = self.temp_dir / "product"
        self.product.mkdir()
        self.run_id = "split-layout-run"
        self.run_dir = self.workspace / ".recursive" / "run" / self.run_id
        self.run_dir.mkdir(parents=True)

        self._git(self.product, "init")
        self._git(self.product, "config", "user.name", "Split Tests")
        self._git(self.product, "config", "user.email", "split-tests@example.com")
        self._git(self.product, "commit", "--allow-empty", "-m", "baseline")
        self.baseline_commit = self._git(self.product, "rev-parse", "HEAD").stdout.strip()

        (self.run_dir / "00-requirements.md").write_text(
            VALID_REQUIREMENTS.format(run_id=self.run_id), encoding="utf-8", newline="\n"
        )
        (self.run_dir / "00-worktree.md").write_text(
            VALID_WORKTREE.format(run_id=self.run_id, baseline=self.baseline_commit, worktree=f".worktrees/{self.run_id}"),
            encoding="utf-8",
            newline="\n",
        )
        (self.workspace / ".recursive" / "run" / ".gitkeep").touch()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=True,
        )

    def _run(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def _scaffold_args(self) -> list[str]:
        return [
            "--repo-root", str(self.product),
            "--scaffold-root", str(self.workspace),
            "--run-id", self.run_id,
        ]

    def test_lock_succeeds_across_split_layout(self) -> None:
        result = self._run("recursive-lock.py", *self._scaffold_args(), "--artifact", "00-requirements.md")
        self.assertEqual(0, result.returncode, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self.assertIn("[OK] Locked", result.stdout)
        self.assertIn(".recursive/run/", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

        receipt = self.run_dir / "locks" / "00-requirements.receipt.json"
        self.assertTrue(receipt.exists())

        content = (self.run_dir / "00-requirements.md").read_text(encoding="utf-8")
        self.assertIn("Status: `LOCKED`", content)
        self.assertIn("LockHash:", content)

    def test_reopen_works_across_split_layout(self) -> None:
        self.assertEqual(
            0,
            self._run("recursive-lock.py", *self._scaffold_args(), "--artifact", "00-requirements.md").returncode,
        )
        result = self._run("recursive-lock.py", *self._scaffold_args(), "--artifact", "00-requirements.md", "--reopen")
        self.assertEqual(0, result.returncode, f"stderr:\n{result.stderr}")
        self.assertIn("Reopened .recursive/run/", result.stdout)
        content = (self.run_dir / "00-requirements.md").read_text(encoding="utf-8")
        self.assertIn("Status: `DRAFT`", content)

    def test_lint_and_verify_locks_accept_split_layout(self) -> None:
        lock_result = self._run("recursive-lock.py", *self._scaffold_args(), "--artifact", "00-requirements.md")
        self.assertEqual(0, lock_result.returncode, lock_result.stdout)
        lock_result = self._run("recursive-lock.py", *self._scaffold_args(), "--artifact", "00-worktree.md")
        self.assertEqual(0, lock_result.returncode, lock_result.stdout)

        lint_result = self._run("lint-recursive-run.py", *self._scaffold_args())
        self.assertEqual(0, lint_result.returncode, f"stdout:\n{lint_result.stdout}\nstderr:\n{lint_result.stderr}")
        self.assertIn("[OK] Lint passed", lint_result.stdout)

        verify_result = self._run("verify-locks.py", *self._scaffold_args())
        self.assertEqual(0, verify_result.returncode, f"stdout:\n{verify_result.stdout}\nstderr:\n{verify_result.stderr}")
        self.assertIn("All locks verified successfully", verify_result.stdout)

        status_result = self._run("recursive-status.py", *self._scaffold_args())
        self.assertEqual(0, status_result.returncode, f"stdout:\n{status_result.stdout}\nstderr:\n{status_result.stderr}")

    def test_missing_run_directory_prints_hint_instead_of_crashing(self) -> None:
        result = self._run(
            "recursive-lock.py",
            "--repo-root", str(self.product),
            "--run-id", "no-such-run",
            "--artifact", "00-requirements.md",
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("Run directory not found", result.stdout)
        self.assertIn("--scaffold-root", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_closeout_preview_log_may_live_in_product_repo(self) -> None:
        log = self.product / "preview.log"
        log.write_text("http://localhost:4173", encoding="utf-8")
        result = self._run(
            "recursive-closeout.py",
            *self._scaffold_args(),
            "--phase", "05",
            "--preview-log", "preview.log",
        )
        # Phase 05 scaffold requires upstream 02-to-be-plan.md which does not
        # exist yet; inputs may be empty and the scaffold should still write.
        self.assertEqual(0, result.returncode, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self.assertIn("[OK] Wrote closeout scaffold", result.stdout)
        self.assertIn("http://localhost:4173", (self.run_dir / "05-manual-qa.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
