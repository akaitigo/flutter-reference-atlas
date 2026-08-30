#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Evaluate the 8 Outcome x 14 Surface router contract without claiming completion."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tooling.non_regression.audit import WorktreeReader, load_structured  # noqa: E402

OUTPUT_PATH = ROOT / "evals/flutter-router.definitive-mastery-eval.json"
FORWARD_PATH = ROOT / "evals/flutter-router.agent-forward-eval.json"
CONTRACT_PATH = ROOT / ".agents/skills/flutter-reference-router/references/mastery-contract.json"
GENERATED_AT = "2026-08-28T00:00:00+09:00"

OUTCOME_EXECUTION = {
    "understand": {"mode": "review", "mutation_policy": "read-only", "required_output_fields": ["principle", "boundary", "coverage-state", "authority", "evidence"]},
    "choose": {"mode": "design", "mutation_policy": "read-only", "required_output_fields": ["primary-candidate", "alternatives", "tradeoffs", "constraints", "coverage-state"]},
    "build": {"mode": "implement", "mutation_policy": "explicit-authorization-required", "required_output_fields": ["target", "variant", "authorized-change-scope", "verification", "coverage-state"]},
    "verify": {"mode": "review", "mutation_policy": "read-only", "required_output_fields": ["oracle", "command", "runtime-profile", "artifact", "coverage-state"]},
    "operate": {"mode": "review", "mutation_policy": "read-only", "required_output_fields": ["lifecycle-owner", "telemetry", "runbook", "recovery", "evidence"]},
    "troubleshoot": {"mode": "diagnose", "mutation_policy": "read-only", "required_output_fields": ["reproduction", "failure-stage", "cause", "recovery-condition", "evidence"]},
    "evolve": {"mode": "migrate", "mutation_policy": "explicit-authorization-required", "required_output_fields": ["old-new-mapping", "compatibility", "migration-evidence", "non-regression", "rollback"]},
    "delegate": {"mode": "review", "mutation_policy": "explicit-authorization-required", "required_output_fields": ["target", "variant", "authorized-change-scope", "stop-condition", "independent-review"]},
}

# These are routing exemplars, not semantic equivalence claims. Each value is an
# existing capability whose Coverage target belongs to the named target set.
ROUTES_BY_SURFACE_SET = {
    "orientation-scope": {"baseline": "baseline.sdk-lock", "language-platform": "language.public-surface"},
    "foundations-mechanics": {"language-platform": "platform.channel-plugin", "execution": "execution.local-lab"},
    "architecture-design": {"product": "product.adaptive-workspace", "language-platform": "platform.channel-plugin"},
    "implementation-construction": {"product": "product.adaptive-workspace", "execution": "execution.android-emulator-lab"},
    "testing-verification": {"product": "product.state-lifecycle", "execution": "execution.local-lab", "quality": "quality.testing"},
    "failure-recovery": {"product": "product.state-lifecycle", "execution": "execution.container-lab", "quality": "quality.failure-recovery"},
    "operations-observability": {"product": "product.adaptive-workspace", "quality": "operations.runbooks"},
    "security-privacy-safety": {"product": "product.adaptive-workspace", "quality": "quality.security"},
    "performance-capacity-cost": {"product": "product.adaptive-workspace", "quality": "quality.performance"},
    "compatibility-integration": {"baseline": "baseline.sdk-lock", "language-platform": "platform.runner-matrix", "execution": "execution.android-emulator-lab"},
    "migration-evolution-deprecation": {"baseline": "baseline.sdk-lock", "language-platform": "language.public-surface", "quality": "operations.runbooks"},
    "decision-comparison": {"product": "product.state-lifecycle", "language-platform": "platform.channel-plugin", "quality": "quality.performance"},
    "provenance-rights": {"baseline": "baseline.sdk-lock", "quality": "operations.runbooks"},
    "agent-skill": {"skill": "skill.router"},
}

DEFINITIVE_SURFACE_BY_CAPABILITY = {
    "baseline.sdk-lock": "migration.sdk-api",
    "language.public-surface": "framework.binding-scheduling",
    "platform.channel-plugin": "platform.method-channel",
    "execution.local-lab": "testing.unit-widget",
    "product.adaptive-workspace": "navigation.imperative",
    "execution.android-emulator-lab": "testing.integration-device",
    "product.state-lifecycle": "state.change-notifier",
    "quality.testing": "testing.unit-widget",
    "execution.container-lab": "failure.framework-errors",
    "quality.failure-recovery": "failure.framework-errors",
    "operations.runbooks": "operations.logging-crash-diagnostics",
    "quality.security": "security.input-data-boundary",
    "quality.performance": "performance.frame-jank",
    "platform.runner-matrix": "build.android",
    "skill.router": "testing.unit-widget",
}


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def file_binding(relative: str) -> dict[str, Any]:
    data = (ROOT / relative).read_bytes()
    return {"path": relative, "digest": digest_bytes(data), "bytes": len(data)}


def load_json(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def run_router(mode: str, query: str, *, authorize: bool = False, mutation_requested: bool = False, authority_decision: bool = False, stale_relock: bool = False) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / ".agents/skills/flutter-reference-router/scripts/route.py"), "--mode", mode, "--capability", query]
    if authorize:
        command.append("--write-authorized")
    if mutation_requested:
        command.append("--mutation-requested")
    if authority_decision:
        command.append("--authority-semantic-decision")
    if stale_relock:
        command.append("--stale-source-relock")
    return json.loads(subprocess.check_output(command, text=True))


def choose_query(route: dict[str, Any]) -> str:
    return sorted(route["keywords"], key=lambda value: (-len(value.replace(" ", "")), value))[0]


def evidence_records() -> dict[str, dict[str, Any]]:
    result = {}
    reader = WorktreeReader(ROOT)
    for relative in reader.paths("evidence"):
        if relative.endswith(".evidence.yaml"):
            record = load_structured(reader, relative)
            result[record["id"]] = {"record": record, **file_binding(relative)}
    return result


def authority_bindings(authority_ids: list[str]) -> list[dict[str, Any]]:
    bindings = []
    for authority_id in sorted(set(authority_ids)):
        relative = f"authority/surfaces-draft/{authority_id}.json"
        artifact = load_json(relative)
        bindings.append({
            "id": authority_id,
            "url": artifact["source_url"],
            "locked_digest": artifact["locked_source_digest"],
            "fetch_status": artifact["fetch"]["status"],
            "artifact": file_binding(relative),
        })
    return bindings


def runtime_bindings(entry: dict[str, Any]) -> list[dict[str, Any]]:
    bindings = []
    for observation in entry["observations"]:
        if observation["evidence_kind"] == "source-contract":
            continue
        relative = observation["artifact"]
        actual = file_binding(relative)
        if actual["digest"] != observation["artifact_digest"]:
            raise RuntimeError(f"Runtime artifact digest drift: {relative}")
        bindings.append({
            "runtime_profile": observation["runtime_profile"], "variant": observation["variant"],
            "scenario": observation["scenario"], "evidence_kind": observation["evidence_kind"],
            "evidence_id": observation["evidence_id"], "artifact": actual,
            "reference_app": observation["reference_app"], "verified": observation["verified"],
        })
    return bindings


def write_contract(mastery: dict[str, Any]) -> None:
    contract = {
        "schema_version": 1, "atlas_id": "flutter-reference-atlas", "source": "mastery.yaml",
        "outcomes": mastery["outcomes"], "surfaces": mastery["surfaces"],
        "outcome_execution_contracts": OUTCOME_EXECUTION,
        "routing_exemplars": ROUTES_BY_SURFACE_SET,
        "completion_semantics": {
            "matrix_pass_implies_atlas_complete": False,
            "routing_gap_is_reported_not_filled": True,
            "independent_agent_forward_eval_required": True,
        },
    }
    CONTRACT_PATH.write_text(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_forward_state() -> dict[str, Any]:
    value = {
        "schema_version": 1,
        "id": "flutter-router.independent-agent-forward-eval.v1",
        "atlas_id": "flutter-reference-atlas",
        "generated_at": GENERATED_AT,
        "status": "not-executed-required",
        "semantic_scope": "independent-agent-project-change-forward-eval",
        "independent_agent": False,
        "completion_blocking": True,
        "deterministic_router_matrix_substitutes_forward_eval": False,
        "required_artifacts": ["agent-transcript", "isolated-worktree-diff", "executed-tests", "runtime-artifacts", "independent-oracle-review"],
        "planned_cases": [
            {"id": "agent-forward.build-reference-app", "outcome": "build", "status": "not-executed"},
            {"id": "agent-forward.troubleshoot-platform-recovery", "outcome": "troubleshoot", "status": "not-executed"},
            {"id": "agent-forward.evolve-sdk-migration", "outcome": "evolve", "status": "not-executed"},
            {"id": "agent-forward.delegate-review", "outcome": "delegate", "status": "not-executed"},
        ],
        "summary": {"planned": 4, "executed": 0, "passed": 0, "failed": 0},
        "reason": "独立Agentによる隔離Project変更と独立Oracle Reviewはこの実行では行っていない。",
    }
    FORWARD_PATH.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def generate() -> dict[str, Any]:
    reader = WorktreeReader(ROOT)
    mastery = load_structured(reader, "mastery.yaml")
    coverage = load_structured(reader, "coverage.yaml")
    routes_doc = load_json("evals/routes.json")
    inventory = load_json("atlas/definitive/surface-inventory.json")
    ledger = load_json("atlas/definitive/gap-ledger.json")
    review_queue = load_json("authority/review-queue.snapshot.json")
    write_contract(mastery)
    forward_state = write_forward_state()
    routes = routes_doc["routes"]
    route_by_capability = {route["capability_id"]: route for route in routes}
    target_by_id = {target["id"]: target for target in coverage["targets"]}
    surface_by_id = {surface["id"]: surface for surface in inventory["surfaces"]}
    entry_by_id = {entry["surface_id"]: entry for entry in ledger["entries"]}
    evidence_by_id = evidence_records()
    matrix = []
    for outcome in mastery["outcomes"]:
        execution = OUTCOME_EXECUTION[outcome["id"]]
        for mastery_surface in mastery["surfaces"]:
            cell_id = f"skill.{outcome['id']}.{mastery_surface['id']}"
            intersection = [target_set for target_set in mastery_surface["target_sets"] if target_set in outcome["target_sets"]]
            choices = ROUTES_BY_SURFACE_SET[mastery_surface["id"]]
            target_set = next((candidate for candidate in intersection if candidate in choices), None)
            if target_set is None:
                matrix.append({
                    "id": cell_id, "outcome": outcome["id"], "mastery_surface": mastery_surface["id"],
                    "mode": execution["mode"], "mutation_policy": execution["mutation_policy"],
                    "required_deliverables": mastery_surface["required_deliverables"], "required_output_fields": execution["required_output_fields"],
                    "support_status": "mastery-routing-gap", "routing_gaps": ["mastery-target-set-intersection-or-exemplar-missing"],
                    "target_binding": None, "definitive_surface_binding": None, "authority_bindings": [], "sdk_source_bindings": [],
                    "platform_runtime_evidence": [], "variant_bindings": [],
                    "assertions": {"identity": True, "routing_gap_fail_closed": True, "mutation_boundary": True, "no_invented_binding": True},
                    "result": "pass",
                })
                continue
            capability_id = choices[target_set]
            route = route_by_capability[capability_id]
            target = target_by_id[route["target_id"]]
            authorize = execution["mutation_policy"] == "explicit-authorization-required"
            actual = run_router(execution["mode"], choose_query(route), authorize=authorize, mutation_requested=authorize)
            definitive_surface_id = DEFINITIVE_SURFACE_BY_CAPABILITY[capability_id]
            definitive_surface = surface_by_id[definitive_surface_id]
            entry = entry_by_id[definitive_surface_id]
            runtime = runtime_bindings(entry)
            variants = sorted({item["variant"] for item in runtime})
            profiles = sorted({item["runtime_profile"] for item in runtime})
            all_authority_ids = sorted(set(actual.get("authority_ids", [])) | set(definitive_surface["authority_ids"]))
            authority = authority_bindings(all_authority_ids)
            evidence = [evidence_by_id[evidence_id] for evidence_id in target["evidence_ids"] if evidence_id in evidence_by_id]
            routing_gaps = []
            if target["state"] != "covered":
                routing_gaps.append(f"target-state:{target['state']}")
            if entry["state"] != "closed":
                routing_gaps.append(f"definitive-surface-state:{entry['state']}")
            if not runtime:
                routing_gaps.append("platform-runtime-evidence-unavailable")
            mutation_ok = (
                actual["mutation_policy"] == execution["mutation_policy"]
                and actual["write_authorized"] is authorize
                and not actual["blocked_reasons"]
                and actual["mutation_status"] == ("authorized-for-request-scope" if authorize else "read-only")
            )
            assertions = {
                "identity": actual.get("capability_id") == capability_id and actual.get("target_id") == target["id"],
                "target_state": actual.get("state") == target["state"] and target["target_set"] == target_set,
                "mutation_boundary": mutation_ok,
                "authority_binding": bool(authority) and all(re.fullmatch(r"sha256:[a-f0-9]{64}", item["locked_digest"]) for item in authority),
                "source_binding": bool(definitive_surface["sdk_sources"]) and all(re.fullmatch(r"sha256:[a-f0-9]{64}", item["digest"]) for item in definitive_surface["sdk_sources"]),
                "runtime_binding": all(item["verified"] and item["artifact"]["digest"] for item in runtime),
                "variant_binding": variants == sorted(entry["satisfied"]["variants"]),
                "platform_profile_binding": profiles == sorted(entry["satisfied"]["runtime_profiles"]),
                "target_evidence_binding": len(evidence) == len(target["evidence_ids"]),
                "stop_conditions": all(condition in actual["stop_conditions"] for condition in ("coverage-gap", "unauthorized-mutation", "external-human-authority-decision-required", "stale-source-relock-explicit-procedure-required", "ambiguous-or-unknown-query")),
                "completion_fail_closed": entry["state"] == "closed" or actual.get("publish_allowed") is False,
            }
            matrix.append({
                "id": cell_id, "outcome": outcome["id"], "mastery_surface": mastery_surface["id"], "mode": execution["mode"],
                "mutation_policy": execution["mutation_policy"], "required_deliverables": mastery_surface["required_deliverables"],
                "required_output_fields": execution["required_output_fields"], "support_status": "routed-with-gaps" if routing_gaps else "routed",
                "routing_gaps": routing_gaps, "router_result": actual,
                "target_binding": {"id": target["id"], "target_set": target["target_set"], "state": target["state"], "requirement": target["requirement"], "claim_ids": target["claim_ids"], "evidence_ids": target["evidence_ids"], "evidence_bindings": evidence},
                "definitive_surface_binding": {"id": definitive_surface_id, "state": entry["state"], "required_runtime_profiles": definitive_surface["required_runtime_profiles"], "gaps": entry["gaps"]},
                "authority_bindings": authority, "sdk_source_bindings": definitive_surface["sdk_sources"],
                "platform_runtime_evidence": runtime, "variant_bindings": variants,
                "assertions": assertions, "result": "pass" if all(assertions.values()) else "fail",
            })
    boundary_specs = [
        ("boundary.ambiguous", run_router("design", "framework internal rendering pipeline"), "coverage-gap", None),
        ("boundary.unknown", run_router("review", "quantum hologram telepathy interface"), "coverage-gap", None),
        ("boundary.unauthorized-build", run_router("implement", "adaptive ui"), "blocked", "unauthorized-mutation"),
        ("boundary.human-authority", run_router("review", "public surface", authority_decision=True), "blocked", "external-human-authority-decision-required"),
        ("boundary.stale-relock", run_router("migrate", "sdk migration", authorize=True, stale_relock=True), "blocked", "stale-source-relock-explicit-procedure-required"),
    ]
    boundary_cases = []
    for case_id, actual, expected_status, expected_reason in boundary_specs:
        passed = actual["status"] == expected_status and actual["write_allowed"] is False and (expected_reason is None or expected_reason in actual["blocked_reasons"])
        boundary_cases.append({"id": case_id, "expected_status": expected_status, "expected_blocked_reason": expected_reason, "actual": actual, "result": "pass" if passed else "fail"})
    target_cases = []
    routes_by_target = {route["target_id"]: route for route in routes}
    for target in coverage["targets"]:
        route = routes_by_target.get(target["id"])
        assertions = {
            "state_known": target["state"] in {"covered", "partial", "infeasible", "excluded"},
            "route_state_consistent": route is None or route["state"] == target["state"],
            "evidence_ids_resolve": all(evidence_id in evidence_by_id for evidence_id in target["evidence_ids"]),
        }
        target_cases.append({
            "id": target["id"], "target_set": target["target_set"], "state": target["state"], "requirement": target["requirement"],
            "route_available": route is not None, "route_capability_id": route["capability_id"] if route else None,
            "claim_ids": target["claim_ids"], "evidence_ids": target["evidence_ids"], "assertions": assertions,
            "result": "pass" if all(assertions.values()) else "fail",
        })
    source_files = [
        "evals/evaluate_mastery.py", "evals/test_mastery_eval.py", ".agents/skills/flutter-reference-router/scripts/route.py",
        ".agents/skills/flutter-reference-router/SKILL.md", ".agents/skills/flutter-reference-router/references/mastery-contract.json",
        "mastery.yaml", "coverage.yaml", "atlas/definitive/surface-inventory.json", "atlas/definitive/gap-ledger.json",
        "authority/review-queue.snapshot.json", "evals/flutter-router.agent-forward-eval.json",
    ]
    source_bindings = {relative: file_binding(relative) for relative in source_files}
    failed_matrix = sum(item["result"] != "pass" for item in matrix)
    failed_boundary = sum(item["result"] != "pass" for item in boundary_cases)
    failed_targets = sum(item["result"] != "pass" for item in target_cases)
    mastery_routing_gaps = sum(item["support_status"] == "mastery-routing-gap" for item in matrix)
    runtime_gap_cells = sum("platform-runtime-evidence-unavailable" in item["routing_gaps"] for item in matrix)
    target_route_gaps = sum(not item["route_available"] for item in target_cases)
    state_counts = Counter(item["state"] for item in target_cases)
    artifact = {
        "schema_version": 1, "id": "flutter-router.definitive-mastery-v1", "atlas_id": "flutter-reference-atlas",
        "generated_at": GENERATED_AT,
        "status": "incomplete-skill-and-forward-eval-gaps" if mastery_routing_gaps or runtime_gap_cells or target_route_gaps or forward_state["summary"]["executed"] == 0 else "evaluated-not-completion-certificate",
        "semantic_scope": "deterministic-router-contract-not-independent-agent-forward-eval",
        "source_bindings": source_bindings,
        "summary": {
            "outcomes": len(mastery["outcomes"]), "surfaces": len(mastery["surfaces"]), "matrix_cells": len(matrix),
            "passed": len(matrix) - failed_matrix, "failed": failed_matrix,
            "routed": len(matrix) - mastery_routing_gaps, "mastery_routing_gaps": mastery_routing_gaps,
            "runtime_evidence_gap_cells": runtime_gap_cells,
            "boundary_cases": len(boundary_cases), "boundary_passed": len(boundary_cases) - failed_boundary, "boundary_failed": failed_boundary,
            "targets": len(target_cases), "target_states": dict(sorted(state_counts.items())),
            "target_state_cases_passed": len(target_cases) - failed_targets, "target_route_gaps": target_route_gaps,
            "independent_agent_forward_planned": forward_state["summary"]["planned"], "independent_agent_forward_executed": forward_state["summary"]["executed"],
        },
        "completion_limits": [
            "Matrix passはRouter、binding、権限、Gap報告契約のpassであり、Target completeを意味しない。",
            f"{mastery_routing_gaps} Mastery cellはtarget_setまたはrouting exemplarがなくfail closedである。",
            f"{runtime_gap_cells} routed cellはPlatform Runtime EvidenceがなくGapを保持する。",
            f"全{len(target_cases)} Target stateを記録したが、{target_route_gaps} Targetは専用Router routeを持たない。",
            "独立Agentによる実Project変更結果のForward Evalは未実施である。",
            f"Authority human reviewは{review_queue['summary']['human_reviewed']}/{review_queue['summary']['queued_anchors']}で、stale holdは{review_queue['summary']['stale_document_holds']}件である。",
        ],
        "matrix": matrix, "boundary_cases": boundary_cases, "target_state_cases": target_cases,
        "independent_agent_forward_eval": {"path": "evals/flutter-router.agent-forward-eval.json", "status": forward_state["status"], "completion_blocking": True},
    }
    OUTPUT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if len(matrix) != 112 or failed_matrix or failed_boundary or failed_targets:
        raise RuntimeError(f"Definitive Mastery Skill Eval failed: cells={len(matrix)} matrix={failed_matrix} boundary={failed_boundary} targets={failed_targets}")
    return artifact


def main() -> int:
    try:
        artifact = generate()
    except (OSError, json.JSONDecodeError, subprocess.CalledProcessError, RuntimeError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    summary = artifact["summary"]
    print(f"Definitive Mastery Skill Eval: matrix={summary['passed']}/{summary['matrix_cells']} routed={summary['routed']} routing_gaps={summary['mastery_routing_gaps']} boundary={summary['boundary_passed']}/{summary['boundary_cases']} targets={summary['target_state_cases_passed']}/{summary['targets']} agent_forward={summary['independent_agent_forward_executed']}/{summary['independent_agent_forward_planned']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
