#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate and verify the honest Core v2 migration adapters.

Core's root inventory and matrix schemas describe promotion-shaped documents;
they do not have a ``partial`` row state.  This adapter therefore keeps the
current provisional 54-surface / 540-scenario denominator intact, binds every
row to its real proof-or-gap document, and separately requires the raw Core
audit to stop on the first current coverage gap.  It never turns a gap into a
not-applicable row or a successful subject-definitive audit.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tooling.non_regression.audit import WorktreeReader, load_structured  # noqa: E402


SURFACE_SOURCE = "atlas/definitive/surface-inventory.json"
GAP_SOURCE = "atlas/definitive/gap-ledger.json"
SCENARIO_SOURCE = "evidence/scenarios/index.json"
AUTHORITY_QUEUE = "authority/review-queue.snapshot.json"
INVENTORY_OUTPUT = "surface.inventory.yaml"
MATRIX_OUTPUT = "verification.matrix.yaml"
DEPTH_OUTPUT = "depth.parity.yaml"
DEPTH_SOURCE = "atlas/definitive/flutter-depth-parity.json"
SKILL_EVAL_OUTPUT = "evals/flutter-router.definitive-skill-eval.json"
SKILL_ROUTER_OUTPUT = "evals/definitive-skill-router.json"
SKILL_SOURCE = "evals/flutter-router.definitive-mastery-eval.json"
FORWARD_EVAL_SOURCE = "evals/flutter-router.agent-forward-eval.json"
DEPTH_REFERENCE = "authority/FE_DEPTH_REFERENCE.json"
DEPTH_REFERENCE_LOCK = "definitive/core-v2-fe-depth-reference.lock.json"
DEPTH_REFERENCE_DIGEST = "sha256:2452696f9807b7d4a8ffb22b3ba37f079a25a34ac2370d78423445b96064582a"
EXPECTED_SURFACES = 54
EXPECTED_SCENARIOS = 10
EXPECTED_ROWS = 540
EXPECTED_RUNTIME_ROWS = 14
EXPECTED_GAP_ROWS = 526
GAP_TARGET = "skill.definitive-router"
GAP_CLAIM = "skill.definitive-routes-gaps"


class AdapterError(RuntimeError):
    pass


def load_json(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def yaml_document(value: dict[str, Any]) -> str:
    """Emit the small JSON-compatible YAML subset used by the Core schemas."""

    lines: list[str] = []

    def emit(item: Any, indent: int, key: str | None = None) -> None:
        prefix = " " * indent
        if isinstance(item, dict):
            if key is not None:
                if not item:
                    lines.append(f"{prefix}{key}: {{}}")
                    return
                lines.append(f"{prefix}{key}:")
                indent += 2
                prefix = " " * indent
            for child_key, child in item.items():
                if isinstance(child, (dict, list)):
                    emit(child, indent, child_key)
                else:
                    lines.append(f"{prefix}{child_key}: {yaml_scalar(child)}")
            return
        if isinstance(item, list):
            if key is not None:
                if not item:
                    lines.append(f"{prefix}{key}: []")
                    return
                lines.append(f"{prefix}{key}:")
                indent += 2
            for child in item:
                prefix = " " * indent
                if isinstance(child, dict):
                    first_key = next(iter(child))
                    first_value = child[first_key]
                    lines.append(f"{prefix}- {first_key}: {yaml_scalar(first_value)}")
                    for child_key, child_value in list(child.items())[1:]:
                        if isinstance(child_value, (dict, list)):
                            emit(child_value, indent + 2, child_key)
                        else:
                            lines.append(
                                f"{' ' * (indent + 2)}{child_key}: {yaml_scalar(child_value)}"
                            )
                else:
                    lines.append(f"{prefix}- {yaml_scalar(child)}")
            return
        raise AdapterError(f"unsupported YAML value: {type(item).__name__}")

    emit(value, 0)
    return "\n".join(lines) + "\n"


def artifact_id(source_id: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", source_id.lower()).strip("-")
    if not value:
        raise AdapterError(f"Authority artifact IDを導出できません: {source_id}")
    return value


def dotted_fragment(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not result:
        raise AdapterError(f"dotted ID fragmentを導出できません: {value}")
    return result


def core_surfaces(surface_id: str) -> list[str]:
    prefix = surface_id.split(".", 1)[0]
    mapping = {
        "framework": ["foundations-mechanics", "architecture-design"],
        "rendering": ["foundations-mechanics", "performance-capacity-cost"],
        "input": ["implementation-construction", "testing-verification"],
        "navigation": ["architecture-design", "implementation-construction"],
        "state": ["architecture-design", "implementation-construction"],
        "accessibility": ["security-privacy-safety", "testing-verification"],
        "localization": ["compatibility-integration", "testing-verification"],
        "network": ["compatibility-integration", "security-privacy-safety"],
        "storage": ["failure-recovery", "security-privacy-safety"],
        "platform": ["compatibility-integration", "implementation-construction"],
        "background": ["operations-observability", "failure-recovery"],
        "testing": ["testing-verification"],
        "build": ["compatibility-integration", "operations-observability"],
        "release": ["provenance-rights", "operations-observability"],
        "performance": ["performance-capacity-cost"],
        "memory": ["performance-capacity-cost", "failure-recovery"],
        "security": ["security-privacy-safety"],
        "failure": ["failure-recovery"],
        "migration": ["migration-evolution-deprecation"],
        "devtools": ["operations-observability", "testing-verification"],
        "operations": ["operations-observability", "failure-recovery"],
    }
    if prefix not in mapping:
        raise AdapterError(f"Core Surface mappingがありません: {surface_id}")
    return mapping[prefix]


def core_profile(runtime_profile: str) -> str:
    if "simulator" in runtime_profile or "emulator" in runtime_profile:
        return "simulator"
    if "device" in runtime_profile:
        return "hardware-in-the-loop"
    if runtime_profile.startswith(("linux-", "windows-")):
        return "vm"
    if runtime_profile.startswith("container"):
        return "container"
    return "local"


def coverage_context() -> tuple[dict[str, dict[str, Any]], set[str], str]:
    coverage = load_structured(WorktreeReader(ROOT), "coverage.yaml")
    targets = {item["id"]: item for item in coverage["targets"]}
    claims = {path.stem.removesuffix(".claim") for path in (ROOT / "claims").glob("*.claim.json")}
    return targets, claims, coverage["authority_lock_digest"]


def target_binding(
    entry: dict[str, Any], targets: dict[str, dict[str, Any]], claims: set[str]
) -> tuple[str, str]:
    evidence_ids = sorted({item["evidence_id"] for item in entry["observations"]})
    for evidence_id in evidence_ids:
        candidates = sorted(
            (
                target
                for target in targets.values()
                if evidence_id in target.get("evidence_ids", [])
            ),
            key=lambda target: target["id"],
        )
        for target in candidates:
            for claim_id in target.get("claim_ids", []):
                if claim_id in claims:
                    return target["id"], claim_id
    if GAP_TARGET not in targets or GAP_CLAIM not in claims:
        raise AdapterError("planned/partial Surface用の実在Gap Target/Claimがありません")
    if targets[GAP_TARGET]["state"] != "partial":
        raise AdapterError("Gap Targetはpartialを維持する必要があります")
    return GAP_TARGET, GAP_CLAIM


def source_truth() -> tuple[
    dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]
]:
    inventory = load_json(SURFACE_SOURCE)
    ledger = load_json(GAP_SOURCE)
    index = load_json(SCENARIO_SOURCE)
    queue = load_json(AUTHORITY_QUEUE)
    surfaces = {item["id"]: item for item in inventory["surfaces"]}
    gaps = {item["surface_id"]: item for item in ledger["entries"]}
    rows = {item["id"]: item for item in index["files"]}
    if inventory["surface_count"] != EXPECTED_SURFACES or len(surfaces) != EXPECTED_SURFACES:
        raise AdapterError("provisional Surface denominatorは54件である必要があります")
    if set(gaps) != set(surfaces) or ledger["summary"] != {
        "closed": 0,
        "definitive_status": "incomplete",
        "open": EXPECTED_SURFACES,
        "surface_count": EXPECTED_SURFACES,
    }:
        raise AdapterError("Gap Ledgerは54 Surfaceすべてをopenで保持する必要があります")
    if len(rows) != EXPECTED_ROWS:
        raise AdapterError("Scenario denominatorは540 rowである必要があります")
    if len({(item["surface_id"], item["scenario"]) for item in rows.values()}) != EXPECTED_ROWS:
        raise AdapterError("Surface+Scenario rowが重複しています")
    statuses = [item["status"] for item in rows.values()]
    if statuses.count("surface-runtime-proof") != EXPECTED_RUNTIME_ROWS:
        raise AdapterError("実Runtime rowは14件を維持する必要があります")
    if statuses.count("surface-scenario-gap") != EXPECTED_GAP_ROWS:
        raise AdapterError("Scenario gapは526件を維持する必要があります")
    summary = index["summary"]
    if summary["rows"] != EXPECTED_ROWS or summary["completion_eligible_rows"] != 0:
        raise AdapterError("540 denominatorをCompletion eligibleへ昇格できません")
    if queue["summary"]["pending_human"] != 74 or queue["summary"]["human_reviewed"] != 0:
        raise AdapterError("Authority Human Reviewの74件pendingを維持する必要があります")
    return inventory, gaps, rows, queue


def build_documents() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    inventory, gaps, rows, _ = source_truth()
    reference_lock = load_json(DEPTH_REFERENCE_LOCK)
    if reference_lock["digest"] != DEPTH_REFERENCE_DIGEST:
        raise AdapterError("Core v2 FE Depth Reference lock digestが固定値と一致しません")
    if sha256_file(ROOT / DEPTH_REFERENCE) != DEPTH_REFERENCE_DIGEST:
        raise AdapterError("Core v2 FE Depth Reference bytesが固定commitと一致しません")
    targets, claims, authority_lock_digest = coverage_context()
    source_lock = load_structured(WorktreeReader(ROOT), "sources.lock.yaml")

    artifact_records: list[dict[str, Any]] = []
    artifact_ids: dict[str, str] = {}
    for source in source_lock["sources"]:
        source_id = source["id"]
        path = f"authority/surfaces-draft/{source_id}.json"
        full = ROOT / path
        if not full.is_file():
            raise AdapterError(f"Authority candidate artifactがありません: {path}")
        candidate = load_json(path)
        if candidate["source_id"] != source_id:
            raise AdapterError(f"Authority candidate Source IDが一致しません: {path}")
        candidate_id = artifact_id(source_id)
        if candidate_id in artifact_ids.values():
            raise AdapterError(f"Authority artifact IDが衝突しました: {candidate_id}")
        artifact_ids[source_id] = candidate_id
        artifact_records.append(
            {
                "id": candidate_id,
                "source_id": source_id,
                "path": path,
                "digest": sha256_file(full),
            }
        )

    items: list[dict[str, Any]] = []
    for surface in inventory["surfaces"]:
        surface_id = surface["id"]
        entry = gaps[surface_id]
        target_id, claim_id = target_binding(entry, targets, claims)
        proof_rows = [
            load_json(item["path"])
            for item in rows.values()
            if item["surface_id"] == surface_id
        ]
        variants = sorted(
            {
                variant
                for proof in proof_rows
                for variant in (
                    proof["dedicated_runtime"].get("declared_variants", [])
                    + proof["dedicated_runtime"].get("baseline_variants", [])
                )
            }
        )
        authority_id = surface["authority_ids"][0]
        locator = (
            surface.get("sdk_sources", [{}])[0].get("path")
            or f"authority/surfaces-draft/{authority_id}.json#candidate-surfaces"
        )
        observation_ids = sorted({item["evidence_id"] for item in entry["observations"]})
        evidence_clause = (
            "実Observation " + ", ".join(observation_ids) + " があるが"
            if observation_ids
            else "実Surface Observationは未取得で"
        )
        item: dict[str, Any] = {
            "id": f"inventory.{surface_id}",
            "authority_artifact_id": artifact_ids[authority_id],
            "authority_surface_id": surface_id,
            "locator": locator,
            "kind": "capability",
            "capability_id": surface_id,
            "behavior_id": surface_id,
            "target_id": target_id,
            "title": surface["title"],
            "surface_ids": core_surfaces(surface_id),
            "classification": "included",
            "rationale": (
                f"既存provisional denominatorに含むSurfaceで、{evidence_clause}"
                f"Gap {len(entry['gaps'])}件を保持する。Authority Human Reviewと専用Target/Claimが"
                "閉じるまではCompletion対象外とする。"
            ),
            "claim_ids": [claim_id],
        }
        if variants:
            item["variant_ids"] = [
                f"{surface_id}.variant.{dotted_fragment(variant)}" for variant in variants
            ]
        items.append(item)

    inventory_doc = {
        "schema_version": 2,
        "atlas_id": inventory["atlas_id"],
        "epoch": inventory["coverage_epoch"],
        "authority_lock_digest": authority_lock_digest,
        "authority_artifacts": artifact_records,
        "items": items,
    }

    matrix_rows: list[dict[str, Any]] = []
    surface_by_id = {item["id"]: item for item in inventory["surfaces"]}
    for row in rows.values():
        proof = load_json(row["path"])
        if proof["id"] != row["id"] or sha256_file(ROOT / row["path"]) != row["digest"]:
            raise AdapterError(f"Scenario Proof bindingが一致しません: {row['path']}")
        if proof["status"] != row["status"]:
            raise AdapterError(f"Scenario Proof statusが一致しません: {row['path']}")
        runtime_profile = surface_by_id[row["surface_id"]]["required_runtime_profiles"][0]
        status_clause = (
            "専用実Runtime Proofは存在するがAuthority atomic bindingが未完了"
            if row["status"] == "surface-runtime-proof"
            else "専用実Runtime Proofが未完了でGap Artifactとして保持"
        )
        matrix_rows.append(
            {
                "behavior_id": row["surface_id"],
                "scenario": row["scenario"],
                "applicability": "required",
                "rationale": (
                    f"{row['path']}へ接続し、{status_clause}する。"
                    "他Scenarioや統合Traceによる代替、not-applicableへの退避は行わない。"
                ),
                "proof_obligation_id": row["id"],
                "evidence_ids": [row["id"]],
                "execution_requirement": (
                    "platform" if core_profile(runtime_profile) in {"simulator", "vm", "hardware-in-the-loop"}
                    else "runtime"
                ),
                "profile": core_profile(runtime_profile),
            }
        )

    matrix_doc = {
        "schema_version": 2,
        "atlas_id": inventory["atlas_id"],
        "epoch": inventory["coverage_epoch"],
        "rows": matrix_rows,
    }
    depth_source = load_json(DEPTH_SOURCE)
    depth_rows: list[dict[str, Any]] = []
    for axis in depth_source["axes"]:
        satisfied = axis["status"] == "satisfied"
        gap_count = 0 if satisfied else max(1, len(axis["gaps"]))
        row: dict[str, Any] = {
            "behavior_id": GAP_TARGET,
            "variant_id": f"{GAP_TARGET}.provisional",
            "axis": axis["id"],
            "status": "satisfied" if satisfied else "gap",
            "gap_count": gap_count,
            "proof_id": "proof.non-regression-gate" if satisfied else None,
            "oracle": (
                "公開main baselineのTarget・Claim・Proof・Evidence・Source・Skill・CI floorが縮小していない。"
                if satisfied else None
            ),
            "evidence_ids": ["baseline.public-main-non-regression-v1"] if satisfied else [],
            "artifact_uri": "baseline/public-main-non-regression-v1.json" if satisfied else None,
            "trace_id": "trace.non-regression-gate" if satisfied else None,
            "rationale": (
                "既存非後退監査がpassし、公開main baselineの縮小を機械的に拒否する。"
                if satisfied else " / ".join(axis["gaps"])
            ),
        }
        depth_rows.append(row)
    depth_doc = {
        "schema_version": 2,
        "atlas_id": inventory["atlas_id"],
        "epoch": inventory["coverage_epoch"],
        "completion_status": "incomplete",
        "reference": {
            "id": "fe-depth-reference-v1",
            "path": "authority/FE_DEPTH_REFERENCE.json",
            "digest": DEPTH_REFERENCE_DIGEST,
            "repository": "frontend-behavior-atlas",
            "commit": "4a0b2df8e2091a963bd0e0e1bbccef9c84b49a45",
            "status_at_commit": "incomplete",
        },
        "denominator_policy": {
            "source": "authority-derived-subject-surface-inventory",
            "transplant_absolute_counts": False,
        },
        "rows": depth_rows,
    }
    skill_source = load_json(SKILL_SOURCE)
    forward_source = load_json(FORWARD_EVAL_SOURCE)
    skill_cases = []
    for cell in skill_source["matrix"]:
        skill_cases.append(
            {
                "id": cell["id"],
                "result": cell["result"],
                "outcome_ids": [cell["outcome"]],
                "surface_ids": [cell["mastery_surface"]],
                "gap_behavior": bool(cell["routing_gaps"]),
                "authorization_boundary": bool(cell["assertions"]["mutation_boundary"]),
                "assertion": (
                    f"{cell['outcome']} Outcomeと{cell['mastery_surface']} SurfaceのRoute、"
                    "Gap、Authority、Runtime、mutation境界を既存Mastery Eval結果へ照合する。"
                ),
            }
        )
    skill_eval_doc = {
        "schema_version": 2,
        "id": "flutter-router.definitive-skill-eval",
        "atlas_id": inventory["atlas_id"],
        "atlas_release": "v1.0.0",
        "skill_id": "flutter-reference-router",
        "generated_at": skill_source["generated_at"],
        "cases": skill_cases,
    }

    allowed_cell_keys = {
        "id", "status", "outcome", "surface", "mode", "query", "pattern_id",
        "target_id", "target_set", "target_set_allowed", "coverage_state",
        "coverage_disposition", "required_deliverables", "required_output_fields",
        "mutation_policy", "mutation_status", "blocked_reasons", "stop_conditions",
        "acceptance_criteria", "implementation_bindings", "source_bindings",
        "evidence_bindings", "evidence_records", "expected_pattern_id", "expected",
        "assertions", "support_status", "variant_ids", "authority_item_ids",
        "runtime_evidence_bindings", "result",
    }

    def filtered_cell(value: dict[str, Any]) -> dict[str, Any]:
        return {key: value[key] for key in value if key in allowed_cell_keys}

    router_cells: list[dict[str, Any]] = []
    for cell in skill_source["matrix"]:
        route = cell.get("router_result") or {
            "status": "mastery-routing-gap",
            "mutation_status": "read-only",
            "blocked_reasons": cell["routing_gaps"],
            "stop_conditions": ["coverage-gap", "ambiguous-or-unknown-query"],
            "state": "unrouted",
            "target_id": None,
            "capability_id": None,
        }
        target = cell.get("target_binding") or {}
        surface_binding = cell.get("definitive_surface_binding") or {}
        runtime_bindings = []
        seen_runtime_bindings: set[tuple[str, str, str]] = set()
        for item in cell["platform_runtime_evidence"]:
            binding_key = (
                item["evidence_id"], item["artifact"]["path"], item["artifact"]["digest"]
            )
            if binding_key in seen_runtime_bindings:
                continue
            seen_runtime_bindings.add(binding_key)
            runtime_bindings.append(
                {
                    "evidence_id": binding_key[0],
                    "path": binding_key[1],
                    "digest": binding_key[2],
                }
            )
        converted = {
            "id": cell["id"],
            "status": cell["support_status"],
            "outcome": cell["outcome"],
            "surface": cell["mastery_surface"],
            "mode": cell["mode"],
            "query": f"{cell['outcome']}:{cell['mastery_surface']} のFlutter Routeを評価する",
            "pattern_id": route.get("capability_id"),
            "target_id": route.get("target_id"),
            "target_set": target.get("target_set"),
            "target_set_allowed": target.get("target_set") is not None,
            "coverage_state": route.get("state", "unrouted"),
            "coverage_disposition": "gap-retained" if cell["routing_gaps"] else "routed",
            "required_deliverables": cell["required_deliverables"],
            "required_output_fields": cell["required_output_fields"],
            "mutation_policy": cell["mutation_policy"],
            "mutation_status": route["mutation_status"],
            "blocked_reasons": route["blocked_reasons"] + cell["routing_gaps"],
            "stop_conditions": route["stop_conditions"],
            "assertions": cell["assertions"],
            "support_status": cell["support_status"],
            "variant_ids": [
                f"{surface_binding['id']}.variant.{dotted_fragment(item)}"
                for item in cell["variant_bindings"]
                if isinstance(item, str) and surface_binding.get("id")
            ],
            "authority_item_ids": sorted(
                {
                    dotted_fragment(binding["id"])
                    for binding in cell["authority_bindings"]
                    if binding.get("id")
                }
            ),
            "runtime_evidence_bindings": runtime_bindings,
            "result": cell["result"],
        }
        router_cells.append(filtered_cell(converted))

    boundary_cells = []
    for cell in skill_source["boundary_cases"]:
        actual = cell["actual"]
        boundary_cells.append(
            {
                "id": cell["id"],
                "status": actual["status"],
                "outcome": "boundary",
                "surface": "agent-skill",
                "mode": actual["mode"],
                "query": f"{cell['id']} のfail-closed境界を評価する",
                "coverage_state": "gap" if actual["coverage_gap"] else "covered",
                "coverage_disposition": actual["status"],
                "required_deliverables": ["boundary-decision"],
                "required_output_fields": ["status", "blocked-reasons", "stop-conditions"],
                "mutation_policy": actual["mutation_policy"],
                "mutation_status": actual["mutation_status"],
                "blocked_reasons": actual["blocked_reasons"] + actual["gap_reasons"],
                "stop_conditions": actual["stop_conditions"],
                "support_status": "boundary-verified",
                "result": cell["result"],
            }
        )
    summary = skill_source["summary"]
    skill_router_doc = {
        "schema_version": 1,
        "id": "flutter-router.definitive-skill-router",
        "atlas_id": inventory["atlas_id"],
        "generated_at": skill_source["generated_at"],
        "status": "incomplete-mastery-routing-gaps",
        "semantic_scope": skill_source["semantic_scope"],
        "source_bindings": skill_source["source_bindings"],
        "summary": {
            "outcomes": summary["outcomes"],
            "surfaces": summary["surfaces"],
            "matrix_cells": summary["matrix_cells"],
            "passed": summary["passed"],
            "failed": summary["failed"],
            "routed": summary["routed"],
            "mastery_routing_gaps": summary["mastery_routing_gaps"],
            "partial_coverage_cells": summary["runtime_evidence_gap_cells"],
            "boundary_cases": summary["boundary_cases"],
            "boundary_passed": summary["boundary_passed"],
            "boundary_failed": summary["boundary_failed"],
        },
        "matrix": router_cells,
        "boundary_cases": boundary_cells,
        "completion_limits": skill_source["completion_limits"],
        "forward_eval": {
            "status": "not-run",
            "cases": forward_source["summary"]["planned"],
            "passed": forward_source["summary"]["passed"],
            "failed": forward_source["summary"]["failed"],
            "artifact_path": FORWARD_EVAL_SOURCE,
            "artifact_digest": sha256_file(ROOT / FORWARD_EVAL_SOURCE),
        },
    }
    validate_documents(inventory_doc, matrix_doc, depth_doc, skill_eval_doc, skill_router_doc)
    return inventory_doc, matrix_doc, depth_doc, skill_eval_doc, skill_router_doc


def validate_documents(
    inventory_doc: dict[str, Any], matrix_doc: dict[str, Any], depth_doc: dict[str, Any],
    skill_eval_doc: dict[str, Any], skill_router_doc: dict[str, Any],
) -> None:
    source_inventory, gaps, source_rows, _ = source_truth()
    targets, claims, authority_lock_digest = coverage_context()
    source_surface_ids = {item["id"] for item in source_inventory["surfaces"]}
    item_surface_ids = {item["behavior_id"] for item in inventory_doc["items"]}
    if item_surface_ids != source_surface_ids or len(inventory_doc["items"]) != EXPECTED_SURFACES:
        raise AdapterError("root Surface Inventoryが54 Surfaceを一対一で保持していません")
    if inventory_doc["authority_lock_digest"] != authority_lock_digest:
        raise AdapterError("root Surface InventoryのAuthority Lock Digestが一致しません")
    for item in inventory_doc["items"]:
        if item["target_id"] not in targets:
            raise AdapterError(f"架空Targetは禁止です: {item['target_id']}")
        if len(item["claim_ids"]) != 1 or item["claim_ids"][0] not in claims:
            raise AdapterError(f"架空または集約不明Claimは禁止です: {item['behavior_id']}")
        if gaps[item["behavior_id"]]["state"] != "open":
            raise AdapterError(f"既存Gapを閉じた扱いにできません: {item['behavior_id']}")

    matrix_by_key = {(item["behavior_id"], item["scenario"]): item for item in matrix_doc["rows"]}
    if len(matrix_doc["rows"]) != EXPECTED_ROWS or len(matrix_by_key) != EXPECTED_ROWS:
        raise AdapterError("root Verification Matrixは540 rowを一対一で保持する必要があります")
    for source_row in source_rows.values():
        key = (source_row["surface_id"], source_row["scenario"])
        row = matrix_by_key.get(key)
        if row is None:
            raise AdapterError(f"Matrix rowがありません: {key}")
        if row["applicability"] != "required":
            raise AdapterError(f"既存Gapをnot-applicableへ退避できません: {key}")
        if row["proof_obligation_id"] != source_row["id"] or row["evidence_ids"] != [source_row["id"]]:
            raise AdapterError(f"Matrix rowは実在Scenario Proof IDへ接続する必要があります: {key}")
    depth_source = load_json(DEPTH_SOURCE)
    depth_by_axis = {item["axis"]: item for item in depth_doc["rows"]}
    if len(depth_by_axis) != 18 or set(depth_by_axis) != {item["id"] for item in depth_source["axes"]}:
        raise AdapterError("Depth adapterは18軸を一対一で保持する必要があります")
    if depth_doc["completion_status"] != "incomplete":
        raise AdapterError("17 partial軸が残るためDepthをparityへ昇格できません")
    for axis in depth_source["axes"]:
        expected_status = "satisfied" if axis["status"] == "satisfied" else "gap"
        if depth_by_axis[axis["id"]]["status"] != expected_status:
            raise AdapterError(f"Depth axis状態がSourceと一致しません: {axis['id']}")
    skill_source = load_json(SKILL_SOURCE)
    if len(skill_eval_doc["cases"]) != 112 or any(
        item["result"] != "pass" for item in skill_eval_doc["cases"]
    ):
        raise AdapterError("Skill Evalは既存112 matrix cellの結果を一対一で保持する必要があります")
    if skill_router_doc["summary"]["mastery_routing_gaps"] != 30:
        raise AdapterError("Skill Routerの30 routing gapを維持する必要があります")
    if skill_router_doc["status"] == "subject-skill-ready":
        raise AdapterError("routing/Runtime/Forward Eval Gapが残るSkillをreadyへ昇格できません")
    if skill_router_doc["forward_eval"]["status"] != "not-run" or skill_source["summary"]["independent_agent_forward_executed"] != 0:
        raise AdapterError("独立Agent Forward Eval未実施を維持する必要があります")


def expected_promotion_gap() -> str:
    coverage = load_structured(WorktreeReader(ROOT), "coverage.yaml")
    for target in coverage["targets"]:
        if target["requirement"] == "required" and target["state"] != "covered":
            return (
                "subject-definitiveではrequired Targetをcoveredにする必要があります: "
                f"{target['id']} state={target['state']}"
            )
    raise AdapterError("期待するrequired Target Gapがありません。raw promotion auditへ切替が必要です")


def validate_expected_audit(returncode: int, output: str, expected: str) -> None:
    if returncode == 0:
        raise AdapterError("incomplete状態でraw Subject Definitive auditが成功してはいけません")
    if expected not in output:
        raise AdapterError(
            "raw Subject Definitive auditが期待する現在Gapで停止しません: "
            f"expected={expected!r} output={output.strip()!r}"
        )


def audit_incomplete(atlas_bin: str) -> None:
    for relative in (
        INVENTORY_OUTPUT, MATRIX_OUTPUT, DEPTH_OUTPUT, SKILL_EVAL_OUTPUT,
        SKILL_ROUTER_OUTPUT,
    ):
        result = subprocess.run(
            [atlas_bin, "validate", relative], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            raise AdapterError(f"Core v2 Schema検証に失敗しました: {relative}: {result.stdout.strip()}")
    result = subprocess.run(
        [atlas_bin, "audit", ".", "--gate", "definitive"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    expected = expected_promotion_gap()
    validate_expected_audit(result.returncode, result.stdout, expected)
    print(
        "Core v2 incomplete migration監査済み: "
        f"surfaces={EXPECTED_SURFACES} rows={EXPECTED_ROWS} runtime={EXPECTED_RUNTIME_ROWS} "
        f"gaps={EXPECTED_GAP_ROWS} promotion_block={expected}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--audit-incomplete", action="store_true")
    parser.add_argument("--atlas-bin", default=".tools/bin/atlas-v2")
    args = parser.parse_args()
    try:
        inventory, matrix, depth, skill_eval, skill_router = build_documents()
        expected = {
            INVENTORY_OUTPUT: yaml_document(inventory),
            MATRIX_OUTPUT: yaml_document(matrix),
            DEPTH_OUTPUT: yaml_document(depth),
            SKILL_EVAL_OUTPUT: json.dumps(
                skill_eval, ensure_ascii=False, indent=2, sort_keys=True
            ) + "\n",
            SKILL_ROUTER_OUTPUT: json.dumps(
                skill_router, ensure_ascii=False, indent=2, sort_keys=True
            ) + "\n",
        }
        if args.write:
            for relative, text in expected.items():
                (ROOT / relative).write_text(text, encoding="utf-8")
        if args.check or args.audit_incomplete:
            for relative, text in expected.items():
                path = ROOT / relative
                if not path.is_file() or path.read_text(encoding="utf-8") != text:
                    raise AdapterError(f"Core v2 root adapterが生成結果と一致しません: {relative}")
        if args.audit_incomplete:
            audit_incomplete(args.atlas_bin)
        elif args.check:
            print(
                "Core v2 root adapter検証済み: "
                f"surfaces={EXPECTED_SURFACES} rows={EXPECTED_ROWS} "
                f"runtime={EXPECTED_RUNTIME_ROWS} gaps={EXPECTED_GAP_ROWS}"
            )
        elif not args.write:
            parser.error("--write、--check、--audit-incompleteのいずれかが必要です")
        return 0
    except (AdapterError, FileNotFoundError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"Core v2 root adapterエラー: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
