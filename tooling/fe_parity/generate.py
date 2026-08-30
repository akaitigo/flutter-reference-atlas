#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate Flutter depth parity against the locked FE 18-axis semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tooling.non_regression.audit import audit, load_current  # noqa: E402


LOCK_PATH = ROOT / "definitive/fe-depth-reference.lock.json"
OUTPUT_PATH = ROOT / "atlas/definitive/flutter-depth-parity.json"


class ParityError(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def verify_reference(reference_root: Path, lock: dict[str, Any]) -> None:
    commit = subprocess.check_output(
        ["git", "rev-parse", f"{lock['commit']}^{{commit}}"], cwd=reference_root, text=True
    ).strip()
    if commit != lock["commit"]:
        raise ParityError("FE Depth Reference commitが一致しません")
    for item in lock["files"]:
        content = subprocess.check_output(
            ["git", "show", f"{commit}:{item['path']}"], cwd=reference_root
        )
        if sha256(content) != item["digest"]:
            raise ParityError(f"FE Depth Reference digestが一致しません: {item['path']}")


def check(check_id: str, passed: bool, observed: Any, evidence: list[str]) -> dict[str, Any]:
    return {"id": check_id, "status": "pass" if passed else "gap", "observed": observed, "evidence": evidence}


def axis(definition: dict[str, Any], checks: list[dict[str, Any]], gaps: list[str]) -> dict[str, Any]:
    pass_count = sum(item["status"] == "pass" for item in checks)
    status = "satisfied" if pass_count == len(checks) else "partial" if pass_count else "missing"
    return {**definition, "status": status, "checks": checks, "gaps": gaps}


def non_regression_errors(root: Path) -> list[str]:
    snapshot = load(root / "baseline/public-main-non-regression-v1.json")
    mappings = load(root / "migrations/non-regression-mappings.json")
    return audit(snapshot, load_current(root), mappings)


def generate(root: Path) -> dict[str, Any]:
    lock = load(root / "definitive/fe-depth-reference.lock.json")
    inventory = load(root / "atlas/definitive/surface-inventory.json")
    ledger = load(root / "atlas/definitive/gap-ledger.json")
    authority_extraction = load(root / "authority/extraction.snapshot.json")
    authority_body = load(root / "authority/body-inventory.snapshot.json")
    authority_review = load(root / "authority/review-queue.snapshot.json")
    authority_body_baseline = load(root / "baseline/authority-body-inventory-v1.json")
    authority_body_report = load(root / "evidence/artifacts/authority-body-non-regression-report.json")
    mastery_skill_eval = load(root / "evals/flutter-router.definitive-mastery-eval.json")
    agent_forward_eval = load(root / "evals/flutter-router.agent-forward-eval.json")
    scenario_proofs = load(root / "evidence/scenarios/index.json")
    integrated_traces = load(root / "evidence/scenarios/integrated/index.json")
    requirements = load(root / "definitive/requirements.json")
    observations = [item for entry in ledger["entries"] for item in entry["observations"] if item.get("verified")]
    artifact_use = Counter(item["artifact"] for item in observations)
    variants_by_surface = {entry["surface_id"]: len(entry["satisfied"]["variants"]) for entry in ledger["entries"]}
    profile_rows = sum(len(item["required_runtime_profiles"]) for item in requirements["surfaces"])
    covered_profile_rows = sum(len(entry["satisfied"]["runtime_profiles"]) for entry in ledger["entries"])
    source_count = sum(1 for line in (root / "sources.lock.yaml").read_text(encoding="utf-8").splitlines() if line.startswith("  - id: "))
    axes_by_id = {item["id"]: item for item in lock["axes"]}
    axes: list[dict[str, Any]] = []

    authority_summary = authority_extraction["summary"]
    reproduction_closed = (
        authority_summary["fetched_digest_matched"] == authority_summary["locked_sources"]
        and authority_summary["fetched_digest_stale"] == 0
        and authority_summary["fetch_failed"] == 0
        and authority_summary["fetch_deferred"] == 0
    )
    reference_edges_closed = (
        authority_summary["reference_edges_classified"] == authority_summary["candidate_surfaces"]
        and authority_summary["unclassified_reference_edges"] == 0
    )
    exhaustive = authority_summary["authority_text_surfaces_exhaustive"] is True
    queue_summary = authority_review["summary"]
    queue_complete = (
        queue_summary["queued_anchors"] == authority_body["summary"]["raw_anchors"]
        and queue_summary["pending_human"] + queue_summary["human_reviewed"] == queue_summary["queued_anchors"]
        and queue_summary["stale_document_holds"] == authority_body["summary"]["stale_documents"]
        and queue_summary["queue_count_as_semantic_surfaces"] is False
    )
    human_reviewed = queue_summary["queued_anchors"] > 0 and queue_summary["pending_human"] == 0 and queue_summary["stale_document_holds"] == 0
    axes.append(axis(axes_by_id["authority-body-digestion"], [
        check("authority.locked-sources", source_count == authority_summary["locked_sources"], f"{authority_summary['locked_sources']}/{source_count}", ["sources.lock.yaml", "authority/extraction.snapshot.json"]),
        check("authority.body-reproduction", reproduction_closed, f"{authority_summary['fetched_digest_matched']}/{authority_summary['locked_sources']} matched; {authority_summary['fetched_digest_stale']} stale; {authority_summary['fetch_failed']} failed; {authority_summary['fetch_deferred']} deferred", ["authority/extraction.snapshot.json", "authority/surfaces-draft"]),
        check("authority.reference-edge-candidates", reference_edges_closed, f"{authority_summary['reference_edges_classified']}/{authority_summary['candidate_surfaces']}; {authority_summary['locator_evaluations_deferred']} locator evaluations open", ["authority/extraction.snapshot.json", "authority/surfaces-draft"]),
        check("authority.body-anchor-inventory", False, f"{authority_body['summary']['matched_documents']}/{authority_body['summary']['unique_documents']} matched documents; {authority_body['summary']['raw_anchors']} raw anchors; {authority_body['summary']['pending_human_anchors']} pending-human", ["authority/body-inventory.snapshot.json", "authority/body-inventory-draft"]),
        check("authority.human-review-queue", queue_complete, f"{queue_summary['queued_anchors']}/{authority_body['summary']['raw_anchors']} anchors in {queue_summary['batches']} batches; {queue_summary['stale_document_holds']} stale holds", ["authority/review-queue.snapshot.json", "authority/review-queue-draft", "authority/reviews/decisions.json"]),
        check("authority.surface-exhaustiveness", exhaustive, exhaustive, ["authority/extraction.snapshot.json", "docs/DEFINITIVE_GATE_V2.md"]),
        check("authority.human-review", human_reviewed, f"{queue_summary['human_reviewed']}/{queue_summary['queued_anchors']}; {queue_summary['pending_human']} pending", ["authority/review-queue.snapshot.json", "authority/reviews/decisions.json"]),
    ], [
        f"既存{authority_summary['candidate_surfaces']} reference edge候補とAuthority本文全体のSurface Inventoryは別の母集団である。",
        f"{authority_body['summary']['unique_documents']} unique documentのraw anchor {authority_body['summary']['raw_anchors']}件をQueue化したが、{queue_summary['pending_human']}件は未判断でSemantic Surfaceへ未昇格。",
        f"stale={authority_summary['fetched_digest_stale']}、failed={authority_summary['fetch_failed']}、deferred={authority_summary['fetch_deferred']}、locator未評価={authority_summary['locator_evaluations_deferred']}、stale hold={queue_summary['stale_document_holds']}。",
        f"Authority本文全体exhaustive={str(exhaustive).lower()}、Human review={queue_summary['human_reviewed']}件。",
    ] ))

    multi_variant = sum(value >= 2 for value in variants_by_surface.values())
    axes.append(axis(axes_by_id["surface-atomic-behavior-variant"], [
        check("behavior.provisional-surface-map", inventory["surface_count"] > 0, inventory["surface_count"], ["definitive/requirements.json"]),
        check("behavior.multi-variant", multi_variant == inventory["surface_count"], f"{multi_variant}/{inventory['surface_count']}", ["atlas/definitive/gap-ledger.json"]),
        check("behavior.unique-target-claim", False, 0, ["migrations/definitive-v2.yaml"]),
    ], ["Provisional SurfaceをAuthority由来Atomic behaviorへ分解し、専用Target/Claimへ一対一接続していない。"] ))

    axes.append(axis(axes_by_id["real-runtime-lab"], [
        check("runtime.observed-profile-rows", covered_profile_rows == profile_rows, f"{covered_profile_rows}/{profile_rows}", ["atlas/definitive/gap-ledger.json"]),
        check("runtime.non-substitution", ledger["completion_semantics"]["static_fixture_substitutes_runtime"] is False, True, ["atlas/definitive/gap-ledger.json"]),
        check("runtime.source-harness-binding", len(observations) > 0, len(observations), ["evidence"]),
    ], ["iOS、実Device、macOS/Linux/Windows、GPU、支援技術等のrequired Profileが未閉包。"] ))

    scenario_map = {
        "scenario-normal": "normal", "scenario-boundary": "boundary", "scenario-refusal": "refusal",
        "scenario-failure": "failure", "scenario-recovery": "recovery", "scenario-migration": "migration",
        "scenario-operations": "operations", "scenario-security": "security", "scenario-performance": "performance",
        "scenario-compatibility": "compatibility",
    }
    for axis_id, scenario in scenario_map.items():
        summary = scenario_proofs["by_scenario"][scenario]
        axes.append(axis(axes_by_id[axis_id], [
            check(f"{axis_id}.dedicated-row", summary["rows"] == inventory["surface_count"], f"{summary['rows']}/{inventory['surface_count']}", ["evidence/scenarios/index.json", "evidence/scenarios/surfaces"]),
            check(f"{axis_id}.surface-specific-runtime", summary["surface_specific_runtime"] == inventory["surface_count"], f"{summary['surface_specific_runtime']}/{inventory['surface_count']}", ["evidence/scenarios/index.json", "evidence/scenarios/surfaces"]),
            check(f"{axis_id}.integrated-trace", integrated_traces["summary"]["passed"] == 10 and scenario_proofs["summary"]["integrated_trace_rows"] == scenario_proofs["summary"]["rows"], f"10/10 integrated; {scenario_proofs['summary']['integrated_trace_rows']}/{scenario_proofs['summary']['rows']} bound", ["evidence/scenarios/integrated/index.json", "evidence/scenarios/index.json"]),
            check(f"{axis_id}.authority-atomic-row", scenario_proofs["summary"]["authority_atomic_rows"] > 0 and scenario_proofs["summary"]["completion_eligible_rows"] > 0, f"authority={scenario_proofs['summary']['authority_atomic_rows']} completion={scenario_proofs['summary']['completion_eligible_rows']}", ["authority/reviews/decisions.json", "evidence/scenarios/index.json"]),
        ], [
            f"Surface固有Runtime Proofは{summary['surface_specific_runtime']}/{inventory['surface_count']}、明示gapは{summary['explicit_gaps']}件。",
            "統合Reference App Traceを全Surface固有Proofへ流用しない。",
            "Authority Human review完了までCompletion eligible rowは0。",
        ] ))

    tracked_logs = sorted(str(path.relative_to(root)) for path in (root / "evidence/artifacts").glob("*.log"))
    axes.append(axis(axes_by_id["artifact-trace"], [
        check("artifact.execution-log", bool(tracked_logs), len(tracked_logs), tracked_logs),
        check("artifact.visual-trace-build", False, 0, ["migrations/definitive-v2.yaml"]),
        check("artifact.unique-binding", all(count == 1 for count in artifact_use.values()) and bool(artifact_use), dict(artifact_use), ["definitive/runtime-observations.json"]),
    ], ["画面、frame/network/memory trace、build artifactおよびScenario専用bindingが未閉包。"] ))

    axes.append(axis(axes_by_id["integrated-reference-system"], [
        check("reference.app-exists", (root / "reference-systems/operations-workspace").is_dir(), True, ["reference-systems/operations-workspace"]),
        check("reference.scenario-manifest", (root / "integrations/reference-system/manifest.json").is_file(), 10, ["integrations/reference-system/manifest.json"]),
        check("reference.cross-behavior-proof", integrated_traces["summary"]["passed"] == 10, f"{integrated_traces['summary']['passed']}/10", ["evidence/scenarios/integrated/index.json", "evidence/scenarios/integrated"]),
        check("reference.authority-derived-scope", scenario_proofs["summary"]["completion_eligible_rows"] > 0, scenario_proofs["summary"]["completion_eligible_rows"], ["authority/reviews/decisions.json", "evidence/scenarios/index.json"]),
    ], ["統合Systemはbounded Cross-behavior Proofであり、Authority由来Atomic Surface completionではない。"] ))

    skill_cases = len(load(root / "evals/definitive_cases.json")["cases"])
    skill_summary = mastery_skill_eval["summary"]
    axes.append(axis(axes_by_id["skill-eval"], [
        check("skill.surface-routing", skill_cases > 0, skill_cases, ["evidence/artifacts/definitive-router-eval-report.json"]),
        check("skill.8-outcome-14-surface", skill_summary["matrix_cells"] == 112 and skill_summary["passed"] == 112, f"{skill_summary['passed']}/{skill_summary['matrix_cells']}", ["evals/flutter-router.definitive-mastery-eval.json", ".agents/skills/flutter-reference-router/references/mastery-contract.json"]),
        check("skill.boundary-cases", skill_summary["boundary_passed"] == skill_summary["boundary_cases"], f"{skill_summary['boundary_passed']}/{skill_summary['boundary_cases']}", ["evals/flutter-router.definitive-mastery-eval.json"]),
        check("skill.mastery-routing", skill_summary["mastery_routing_gaps"] == 0 and skill_summary["runtime_evidence_gap_cells"] == 0 and skill_summary["target_route_gaps"] == 0, f"{skill_summary['routed']}/{skill_summary['matrix_cells']} routed; {skill_summary['runtime_evidence_gap_cells']} runtime evidence gaps; {skill_summary['target_route_gaps']} target route gaps", ["evals/flutter-router.definitive-mastery-eval.json", "mastery.yaml", "coverage.yaml"]),
        check("skill.agent-execution", agent_forward_eval["status"] == "passed" and agent_forward_eval["summary"]["executed"] == agent_forward_eval["summary"]["planned"], f"{agent_forward_eval['summary']['executed']}/{agent_forward_eval['summary']['planned']}", ["evals/flutter-router.agent-forward-eval.json"]),
    ], [
        f"{skill_summary['mastery_routing_gaps']} Mastery routing cell、{skill_summary['runtime_evidence_gap_cells']} Runtime Evidence cell、{skill_summary['target_route_gaps']} Target routeが未閉包。",
        "112 cellは決定論Router contractであり、独立Agentによる実Project変更結果のForward Evalではない。",
    ] ))

    legal_files = ["LICENSE", "NOTICE", "third_party/manifest.yaml", "sbom.spdx.json", "provenance.yaml"]
    axes.append(axis(axes_by_id["rights-provenance"], [
        check("rights.automated", all((root / item).is_file() for item in legal_files), len(legal_files), legal_files),
        check("rights.human-review", False, 0, ["migrations/definitive-v2.yaml"]),
    ], ["第三者License義務、Brand/Similarity、Repository名の人手Reviewが未完。"] ))

    regression_errors = non_regression_errors(root)
    axes.append(axis(axes_by_id["non-regression-gate"], [
        check("non-regression.public-main", not regression_errors, len(regression_errors), ["baseline/public-main-non-regression-v1.json"]),
        check("non-regression.authority-anchor-floor", authority_body_report["status"] == "pass" and authority_body_report["baseline_anchors"] == sum(len(item["anchor_ids"]) for item in authority_body_baseline["documents"]), authority_body_report, ["baseline/authority-body-inventory-v1.json", "migrations/authority-body-inventory-v1.json", "evidence/artifacts/authority-body-non-regression-report.json"]),
        check("non-regression.ci", not regression_errors, len(regression_errors), [".github/workflows/ci.yml"]),
    ], regression_errors))

    statuses = Counter(item["status"] for item in axes)
    return {
        "schema_version": 1,
        "id": "flutter-depth-parity",
        "atlas_id": "flutter-reference-atlas",
        "coverage_epoch": inventory["coverage_epoch"],
        "status": "incomplete",
        "reference": {"lock": "definitive/fe-depth-reference.lock.json", "commit": lock["commit"]},
        "denominator_policy": {
            "source": "Flutter authority-derived subject surface inventory",
            "state": "provisional-unreviewed" if not exhaustive or not human_reviewed else "authority-reviewed",
            "provisional_surface_count": inventory["surface_count"],
            "authority_locked_sources": authority_summary["locked_sources"],
            "authority_candidate_reference_edges": authority_summary["candidate_surfaces"],
            "authority_text_surfaces_exhaustive": exhaustive,
            "authority_human_reviewed_surfaces": authority_summary["human_reviewed_surfaces"],
            "authority_unique_documents": authority_body["summary"]["unique_documents"],
            "authority_raw_anchors": authority_body["summary"]["raw_anchors"],
            "authority_pending_human_anchors": authority_body["summary"]["pending_human_anchors"],
            "raw_anchors_count_as_semantic_surfaces": False,
            "authority_review_batches": queue_summary["batches"],
            "authority_review_pending": queue_summary["pending_human"],
            "authority_human_decisions": queue_summary["decisions"],
            "authority_stale_document_holds": queue_summary["stale_document_holds"],
            "review_queue_count_as_semantic_surfaces": False,
            "definitive_skill_matrix_cells": skill_summary["matrix_cells"],
            "definitive_skill_matrix_passed": skill_summary["passed"],
            "definitive_skill_routing_gaps": skill_summary["mastery_routing_gaps"],
            "definitive_skill_runtime_evidence_gap_cells": skill_summary["runtime_evidence_gap_cells"],
            "definitive_skill_target_route_gaps": skill_summary["target_route_gaps"],
            "independent_agent_forward_executed": agent_forward_eval["summary"]["executed"],
            "skill_matrix_pass_implies_complete": False,
            "scenario_proof_rows": scenario_proofs["summary"]["rows"],
            "scenario_surface_runtime_rows": scenario_proofs["summary"]["surface_specific_runtime_rows"],
            "scenario_surface_runtime_gap_rows": scenario_proofs["summary"]["surface_runtime_gap_rows"],
            "scenario_integrated_trace_rows": scenario_proofs["summary"]["integrated_trace_rows"],
            "scenario_authority_atomic_rows": scenario_proofs["summary"]["authority_atomic_rows"],
            "scenario_completion_eligible_rows": scenario_proofs["summary"]["completion_eligible_rows"],
            "integrated_trace_substitutes_surface_proof": False,
            "transplant_fe_absolute_counts": False,
        },
        "core_v2_gate": {"state": "not-passed", "evidence": "evidence/history/core-v2-audit-attempt-2026-08-28.record.yaml"},
        "summary": {"axis_count": len(axes), "satisfied": statuses["satisfied"], "partial": statuses["partial"], "missing": statuses["missing"], "gap_zero": statuses["satisfied"] == len(axes), "definitive_candidate": False},
        "axes": axes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--check-reference", action="store_true")
    parser.add_argument("--reference-root", type=Path, default=ROOT.parent / "frontend-behavior-atlas")
    args = parser.parse_args()
    try:
        lock = load(LOCK_PATH)
        if args.check_reference:
            verify_reference(args.reference_root.resolve(), lock)
        value = generate(ROOT)
        data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.check:
            if not OUTPUT_PATH.is_file() or OUTPUT_PATH.read_text(encoding="utf-8") != data:
                raise ParityError(f"生成物が古いか欠落しています: {OUTPUT_PATH}")
        else:
            OUTPUT_PATH.write_text(data, encoding="utf-8")
    except (OSError, json.JSONDecodeError, subprocess.CalledProcessError, ParityError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    summary = value["summary"]
    print(f"Flutter Depth Parityを検証しました: axes={summary['axis_count']} satisfied={summary['satisfied']} partial={summary['partial']} missing={summary['missing']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
