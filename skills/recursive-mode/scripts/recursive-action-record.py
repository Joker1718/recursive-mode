#!/usr/bin/env python3
"""
Generate a phase-aware recursive-mode subagent action record.

Front-end over recursive-subagent-action.py: given `--phase X`, it resolves the
canonical phase label, pre-fills the upstream artifacts and addenda the phase
is expected to re-read, computes the current artifact content hash, and
summarizes the run's diff basis — eliminating the most error-prone authoring in
the delegated-review workflow. Extra flags pass straight through to the
canonical record schema.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_module(name: str, filename: str):
    module_path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


phase_rules = load_module("recursive_phase_rules", "recursive_phase_rules.py")
lint = load_module("recursive_mode_lint", "lint-recursive-run.py")
subagent_action = load_module("recursive_subagent_action", "recursive-subagent-action.py")

# canonical label per artifact file name; everything else is passed through.
_PHASE_TABLE: dict[str, str] = {
    "00-requirements.md": "00 Requirements",
    "00-worktree.md": "00 Worktree Setup",
    "01-as-is.md": "01 AS-IS Analysis",
    "01.5-root-cause.md": "01.5 Root Cause",
    "02-to-be-plan.md": "02 TO-BE Plan",
    "03-implementation-summary.md": "03 Implementation",
    "03.5-code-review.md": "03.5 Code Review",
    "04-test-summary.md": "04 Test Summary",
    "05-manual-qa.md": "05 Manual QA",
    "06-decisions-update.md": "06 Decisions Update",
    "07-state-update.md": "07 State Update",
    "08-memory-impact.md": "08 Memory Impact",
}

PHASE_ALIASES: dict[str, tuple[str, str]] = {}
for _artifact, _label in _PHASE_TABLE.items():
    _aliases = {
        _artifact,
        _artifact[:-3] if _artifact.endswith(".md") else _artifact,
        _artifact.replace(".md", ""),
        _label.lower(),
        _label,
        _label.replace(" ", "-").lower(),
    }
    # Numeric phase key ("01.5", "04"); "00" is ambiguous between
    # 00-requirements and 00-worktree, so it is intentionally not aliased.
    _prefix_match = re.match(r"^(\d+(?:\.\d+)?)-", _artifact)
    if _prefix_match and not _prefix_match.group(1).startswith("00"):
        _aliases.add(_prefix_match.group(1))
    # Descriptive suffix alias ("requirements", "as-is", "to-be-plan", ...).
    _suffix = _artifact.split("-", 1)[1] if "-" in _artifact else ""
    if _suffix and _suffix not in {alias for alias in PHASE_ALIASES}:
        _aliases.add(_suffix)
        _aliases.add(_suffix[:-3] if _suffix.endswith(".md") else _suffix)
    for _alias in _aliases:
        PHASE_ALIASES.setdefault(_alias, (_artifact, _label))


def resolve_phase(raw_phase: str) -> tuple[str, str]:
    compact = raw_phase.strip()
    if not compact:
        raise ValueError("Phase is required")
    entry = PHASE_ALIASES.get(compact) or PHASE_ALIASES.get(compact.lower()) or PHASE_ALIASES.get(compact.lower().replace(" ", "-"))
    if entry is None:
        raise ValueError(
            f"Unsupported phase: {raw_phase}. Use an artifact name (e.g. 01.5-root-cause.md), a phase key (e.g. 01.5), or a label (e.g. '01.5 Root Cause')."
        )
    return entry


def summarize_diff_basis(run_dir: Path) -> str:
    diff_basis = lint.get_run_diff_basis(run_dir)
    baseline = diff_basis.get("normalized_baseline")
    comparison = diff_basis.get("normalized_comparison")
    command = diff_basis.get("normalized_diff_command")
    parts = []
    if baseline:
        parts.append(f"baseline {baseline}")
    if comparison:
        parts.append(f"comparison {comparison}")
    if command:
        parts.append(f"via `{command}`")
    if parts:
        return "Run diff basis: " + ", ".join(parts) + ". See /.recursive/run/" + run_dir.name + "/00-worktree.md for the full record."
    return "See /.recursive/run/" + run_dir.name + "/00-worktree.md for the normalized diff basis used."


def default_audit_questions(phase_label: str, purpose: str) -> list[str]:
    return [
        f"Phase {phase_label}: {purpose}",
        "Cite the exact upstream artifacts, diff scope, and evidence used for every claim.",
        "End with an explicit verdict and any unresolved risks.",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a phase-aware recursive-mode subagent action record (pre-fills upstream artifacts, addenda, and diff basis)."
    )
    parser.add_argument("--repo-root", default=".", help="Git repository root whose diff is audited.")
    parser.add_argument(
        "--scaffold-root",
        default="",
        help="Directory that owns .recursive/ (default: --repo-root). Set this when the run scaffold lives outside the git repo.",
    )
    parser.add_argument("--run-id", required=True, help="Run ID under .recursive/run/.")
    parser.add_argument("--phase", required=True, help="Phase to record: artifact name (01.5-root-cause.md), phase key (01.5), or label ('01.5 Root Cause').")
    parser.add_argument("--subagent-id", required=True, help="Subagent identifier.")
    parser.add_argument("--purpose", required=True, help="Invocation purpose.")
    parser.add_argument("--execution-mode", default="review", help="Execution mode, e.g. review, audit, implementer (default: review).")
    parser.add_argument("--review-bundle", default="", help="Repo-relative review bundle path if used.")
    parser.add_argument("--no-auto-upstream", action="store_true", help="Disable automatic upstream artifact and addenda discovery for the phase.")
    parser.add_argument("--output-name", default="", help="Optional action record filename under subagents/.")
    parser.add_argument("--code-ref", action="append", default=[], help="Repo-relative code reference path.")
    parser.add_argument("--memory-ref", action="append", default=[], help="Repo-relative memory doc path.")
    parser.add_argument("--audit-question", action="append", default=[], help="Extra audit/task question (appended to the phase defaults).")
    parser.add_argument("--action-taken", action="append", default=[], help="Concrete delegated action taken by the subagent.")
    parser.add_argument("--created-file", action="append", default=[], help="Repo-relative created file path.")
    parser.add_argument("--modified-file", action="append", default=[], help="Repo-relative modified file path.")
    parser.add_argument("--reviewed-file", action="append", default=[], help="Repo-relative reviewed file path.")
    parser.add_argument("--untouched-file", action="append", default=[], help="Repo-relative relevant but untouched file path.")
    parser.add_argument("--artifact-read", action="append", default=[], help="Repo-relative recursive artifact read by the subagent.")
    parser.add_argument("--artifact-updated", action="append", default=[], help="Repo-relative recursive artifact updated by the subagent.")
    parser.add_argument("--evidence-used", action="append", default=[], help="Repo-relative evidence path used by the subagent.")
    parser.add_argument("--finding", action="append", default=[], help="Claimed finding or unresolved point.")
    parser.add_argument("--verification-path", action="append", default=[], help="Repo-relative file or artifact path the controller should inspect first.")
    parser.add_argument("--verification-item", action="append", default=[], help="Main-agent verification handoff item.")
    parser.add_argument("--upstream-artifact", action="append", default=[], help="Extra upstream artifact path (added to the auto-discovered set).")
    parser.add_argument("--addendum", action="append", default=[], help="Extra addendum path (added to the auto-discovered set).")
    parser.add_argument("--diff-basis", default="", help="Explicit diff basis summary override.")
    parser.add_argument(
        "--router-used", default="", help="Router identifier used for delegated dispatch, e.g. recursive-router."
    )
    parser.add_argument("--routed-role", default="", help="Canonical routed role resolved for this action.")
    parser.add_argument("--routed-cli", default="", help="Resolved external CLI id if any.")
    parser.add_argument("--routed-model", default="", help="Resolved model id if any.")
    parser.add_argument("--routing-config-path", default="", help="Repo-relative routing policy path.")
    parser.add_argument("--routing-discovery-path", default="", help="Repo-relative routing discovery path.")
    parser.add_argument("--routing-resolution-basis", default="", help="Short explanation of how the route was resolved.")
    parser.add_argument("--routing-fallback-reason", default="", help="Why execution fell back from routed delegation, if applicable.")
    parser.add_argument("--cli-probe-summary", default="", help="Compact CLI probe summary for the action record.")
    parser.add_argument("--prompt-bundle-path", default="", help="Repo-relative routed prompt bundle path if used.")
    parser.add_argument("--invocation-exit-code", default="", help="External CLI invocation exit code if applicable.")
    parser.add_argument("--output-capture-path", action="append", default=[], help="Repo-relative captured output path from the routed CLI.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    scaffold_root = phase_rules.resolve_scaffold_root(repo_root, args.scaffold_root)
    run_dir = phase_rules.run_dir_under_scaffold_root(scaffold_root, args.run_id)
    if not run_dir.exists():
        print(f"[FAIL] Run directory not found: {run_dir}")
        print(f"       Scaffold root: {scaffold_root}")
        print("       Pass --scaffold-root if .recursive/ lives outside --repo-root.")
        return 1

    try:
        artifact_name, phase_label = resolve_phase(args.phase)
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        return 1

    upstream: list[str] = []
    addenda: list[str] = []
    if not args.no_auto_upstream:
        run_prefix = f".recursive/run/{run_dir.name}/"
        upstream = [f"{run_prefix}{name}" for name in lint.get_phase_expected_input_artifact_names(artifact_name, run_dir)]
        addenda = list(lint.get_expected_effective_input_addenda_paths(run_dir, artifact_name))
    upstream.extend(value for value in args.upstream_artifact if value.strip())
    addenda.extend(value for value in args.addendum if value.strip())

    current_artifact_path = run_dir / artifact_name
    artifact_path_arg = f".recursive/run/{run_dir.name}/{artifact_name}" if current_artifact_path.exists() else ""

    questions = default_audit_questions(phase_label, args.purpose.strip())
    questions.extend(value for value in args.audit_question if value.strip())

    record_args = argparse.Namespace(
        repo_root=args.repo_root,
        scaffold_root=args.scaffold_root,
        run_id=args.run_id,
        subagent_id=args.subagent_id,
        phase=phase_label,
        purpose=args.purpose,
        execution_mode=args.execution_mode,
        artifact_path=artifact_path_arg,
        upstream_artifact=upstream,
        addendum=addenda,
        review_bundle=args.review_bundle,
        diff_basis=args.diff_basis or summarize_diff_basis(run_dir),
        code_ref=args.code_ref,
        memory_ref=args.memory_ref,
        audit_question=questions,
        action_taken=args.action_taken,
        created_file=args.created_file,
        modified_file=args.modified_file,
        reviewed_file=args.reviewed_file,
        untouched_file=args.untouched_file,
        artifact_read=args.artifact_read,
        artifact_updated=args.artifact_updated,
        evidence_used=args.evidence_used,
        finding=args.finding,
        verification_path=args.verification_path,
        verification_item=args.verification_item,
        router_used=args.router_used,
        routed_role=args.routed_role,
        routed_cli=args.routed_cli,
        routed_model=args.routed_model,
        routing_config_path=args.routing_config_path,
        routing_discovery_path=args.routing_discovery_path,
        routing_resolution_basis=args.routing_resolution_basis,
        routing_fallback_reason=args.routing_fallback_reason,
        cli_probe_summary=args.cli_probe_summary,
        prompt_bundle_path=args.prompt_bundle_path,
        invocation_exit_code=args.invocation_exit_code,
        output_capture_path=args.output_capture_path,
        output_name=args.output_name,
    )

    artifact_hash = ""
    if artifact_path_arg:
        artifact_hash = subagent_action.content_sha256(current_artifact_path.read_text(encoding="utf-8"))

    subagents_dir = run_dir / "subagents"
    subagents_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output_name = args.output_name.strip()
    if not output_name:
        output_name = f"{timestamp.replace(':', '').replace('-', '')}-{subagent_action.slugify(args.subagent_id)}-action.md"
    if not output_name.lower().endswith(".md"):
        output_name = f"{output_name}.md"
    output_path = subagents_dir / output_name
    output_rel = phase_rules.display_repo_path(output_path, scaffold_root, repo_root)

    lines = subagent_action.build_action_record_lines(record_args, output_rel, artifact_hash, timestamp)
    output_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")

    print(f"[OK] Wrote phase-aware subagent action record: /{output_rel}")
    print(f"Phase: {phase_label}")
    print(f"Auto-discovered upstream artifacts: {len(upstream)}")
    print(f"Auto-discovered addenda: {len(addenda)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
