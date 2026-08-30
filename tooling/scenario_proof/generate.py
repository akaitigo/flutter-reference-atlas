#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate dedicated Flutter Surface x Scenario proofs without overclaiming closure."""

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

from tooling.non_regression.audit import WorktreeReader, load_structured  # noqa: E402
from tooling.scenario_proof.dedicated_runtime import evaluate_dedicated_runtime  # noqa: E402

SCENARIOS = ("normal", "boundary", "refusal", "failure", "recovery", "migration", "operations", "security", "performance", "compatibility")
RUNTIME_KINDS = {"runtime", "build-runtime", "device-runtime", "browser-runtime"}
OUTPUT_ROOT = ROOT / "evidence/scenarios/surfaces"
INDEX_PATH = ROOT / "evidence/scenarios/index.json"
GENERATED_AT = "2026-08-28T00:00:00+09:00"
REFERENCE_LOCK = ROOT / "definitive/fe-reference-system.lock.json"


class ScenarioProofError(RuntimeError):
    pass


def load_json(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def file_binding(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    return {"path": relative, "digest": digest(path), "bytes": path.stat().st_size}


def verify_reference(reference_root: Path) -> None:
    lock = json.loads(REFERENCE_LOCK.read_text(encoding="utf-8"))
    commit = subprocess.check_output(
        ["git", "rev-parse", f"{lock['commit']}^{{commit}}"], cwd=reference_root, text=True
    ).strip()
    if commit != lock["commit"]:
        raise ScenarioProofError("FE Reference System commitが一致しません")
    for item in lock["files"]:
        content = subprocess.check_output(
            ["git", "show", f"{commit}:{item['path']}"], cwd=reference_root
        )
        observed = "sha256:" + hashlib.sha256(content).hexdigest()
        if observed != item["digest"]:
            raise ScenarioProofError(f"FE Reference System digestが一致しません: {item['path']}")


def scenario_for_observation(value: str) -> str:
    return "refusal" if value == "rejection" else value


def evidence_records() -> dict[str, dict[str, Any]]:
    reader = WorktreeReader(ROOT)
    records = {}
    for relative in reader.paths("evidence"):
        if relative.endswith(".evidence.yaml"):
            record = load_structured(reader, relative)
            records[record["id"]] = {"path": relative, "record": record}
    return records


def runtime_identity(record: dict[str, Any], report: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    environment = dict(record.get("environment", {}))
    runner = report.get("runner") or report.get("inventory", {}).get("runner") or {}
    identity = {
        "profile": report.get("profile") or environment.get("profile"),
        "runner_kind": runner.get("kind") or environment.get("runner_kind"),
        "browser": runner.get("browser") or environment.get("browser"),
        "browser_version": runner.get("browser_version") or environment.get("browser_version"),
        "os": runner.get("os_version") or environment.get("os"),
        "architecture": runner.get("architecture") or environment.get("architecture"),
        "api_level": runner.get("api_level") or environment.get("api_level"),
        "device_id": runner.get("device_id") or environment.get("device_id"),
        "physical_device": runner.get("physical_device", environment.get("physical_device")),
    }
    kind = identity["runner_kind"]
    gaps = []
    if not identity["profile"]:
        gaps.append("runtime-profile")
    if kind == "browser-runtime" or identity["profile"] == "web-chrome":
        if not identity["browser"]:
            gaps.append("browser-name")
        if not identity["browser_version"]:
            gaps.append("browser-version")
        if not identity["os"]:
            gaps.append("os")
        if not identity["architecture"]:
            gaps.append("architecture")
    elif kind == "android-emulator" or identity["profile"] in {"android-emulator", "simulator"}:
        if identity["api_level"] is None:
            gaps.append("api-level")
        if not identity["device_id"]:
            gaps.append("device-id")
        if identity["physical_device"] is None:
            gaps.append("physical-device-flag")
    else:
        if not kind:
            gaps.append("runner-kind")
        if not identity["os"]:
            gaps.append("os")
        if not identity["architecture"]:
            gaps.append("architecture")
    return identity, gaps


def observation_binding(surface_id: str, observation: dict[str, Any], records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    record_entry = records.get(observation["evidence_id"])
    if not record_entry:
        raise ScenarioProofError(f"Evidence recordがありません: {observation['evidence_id']}")
    record = record_entry["record"]
    artifact_relative = observation["artifact"]
    artifact = file_binding(artifact_relative)
    if artifact["digest"] != observation.get("artifact_digest"):
        raise ScenarioProofError(f"Observation Artifact digest drift: {artifact_relative}")
    report = load_json(artifact_relative)
    harness_relative = record.get("harness_path")
    harness = file_binding(harness_relative) if isinstance(harness_relative, str) and (ROOT / harness_relative).is_file() else None
    harness_matches = harness is not None and harness["digest"] == record.get("harness_digest")
    identity, identity_gaps = runtime_identity(record, report)
    report_surface = report.get("surface_id")
    surface_specific = observation.get("reference_app") is not True or report_surface == surface_id
    real_runtime = observation.get("verified") is True and observation.get("evidence_kind") in RUNTIME_KINDS
    legacy_candidate = real_runtime and surface_specific and not identity_gaps and harness_matches
    return {
        "runtime_profile": observation["runtime_profile"],
        "variant": observation["variant"],
        "evidence_kind": observation["evidence_kind"],
        "evidence_id": observation["evidence_id"],
        "evidence_record": file_binding(record_entry["path"]),
        "source_contract_only": observation.get("evidence_kind") == "source-contract",
        "reference_app_observation": observation.get("reference_app") is True,
        "surface_specific": surface_specific,
        "real_runtime": real_runtime,
        "real_runtime_identity": not identity_gaps,
        "runtime_identity": identity,
        "runtime_identity_gaps": identity_gaps,
        "harness_binding": harness,
        "harness_digest_matches_record": harness_matches,
        "artifact_binding": artifact,
        "legacy_runtime_candidate": legacy_candidate,
        "eligible_surface_runtime_proof": False,
        "dedicated_surface_scenario_report_required": True,
    }


def expected_documents() -> tuple[dict[str, Any], dict[str, str]]:
    inventory = load_json("atlas/definitive/surface-inventory.json")
    ledger = load_json("atlas/definitive/gap-ledger.json")
    ledger_by_surface = {entry["surface_id"]: entry for entry in ledger["entries"]}
    records = evidence_records()
    integrated = load_json("evidence/scenarios/integrated/index.json")
    manifest = load_json("integrations/reference-system/manifest.json")
    review = load_json("authority/review-queue.snapshot.json")
    if integrated["summary"] != {"scenarios": 10, "passed": 10, "failed": 0, "dedicated_trace_artifacts": 10, "completion_eligible": 0}:
        raise ScenarioProofError("統合Trace summaryが10 Scenario契約と一致しません")
    run_id = integrated.get("run_id")
    if not isinstance(run_id, str) or not run_id.startswith("sha256:"):
        raise ScenarioProofError("統合Trace bundleのrun_idがありません")
    if integrated.get("retention_contract") != {
        "failed_run": "retain-prior-success",
        "partial_overwrite_allowed": False,
        "publish_on": "full-run-passed",
        "swap": "staged-directory-rename-with-rollback",
    }:
        raise ScenarioProofError("統合Trace bundleの原子的保存契約が不正です")
    trace_by_scenario = {item["scenario"]: item for item in integrated["files"]}
    manifest_by_scenario = {item["id"]: item for item in manifest["scenarios"]}
    if tuple(trace_by_scenario) != SCENARIOS or tuple(manifest_by_scenario) != SCENARIOS:
        raise ScenarioProofError("統合TraceまたはManifestのScenario順序が不正です")
    if review["summary"]["human_reviewed"] != 0:
        raise ScenarioProofError("Human-reviewed Authority bindingの昇格実装が必要です")

    documents: dict[str, str] = {}
    proofs = []
    files = []
    for surface in inventory["surfaces"]:
        surface_id = surface["id"]
        for scenario in SCENARIOS:
            entry = ledger_by_surface[surface_id]
            mapped = [
                observation_binding(surface_id, item, records)
                for item in entry["observations"]
                if scenario_for_observation(item["scenario"]) == scenario
            ]
            dedicated = evaluate_dedicated_runtime(
                ROOT,
                surface_id=surface_id,
                scenario=scenario,
                baseline_variants=entry["satisfied"]["variants"],
                minimum_variants=surface["minimum_variants"],
                source_set_digest=surface["sdk_source_set_digest"],
            )
            closed = dedicated["closed"]
            trace_entry = trace_by_scenario[scenario]
            trace_path = trace_entry["path"]
            trace = load_json(trace_path)
            trace_binding = file_binding(trace_path)
            if trace_binding["digest"] != trace_entry["digest"] or trace["scenario"] != scenario or trace.get("run_id") != run_id or trace_entry.get("run_id") != run_id:
                raise ScenarioProofError(f"統合Trace binding drift: {scenario}")
            mapping = manifest_by_scenario[scenario]
            gaps = []
            if not mapped:
                gaps.append("このSurfaceに当該ScenarioのRuntime Observationがない。")
            if mapped:
                gaps.append("既存Observationまたは別Capture metadataは専用Surface+Scenario Runtime Proofへ流用しない。")
            gaps.extend(f"専用Runtime契約未達: {item}" for item in dedicated["errors"])
            if surface_id not in mapping["surface_ids"]:
                gaps.append("統合Reference Appの当該ScenarioへこのSurfaceは直接Mappingされていない。")
            if any(item["reference_app_observation"] and not item["surface_specific"] for item in mapped):
                gaps.append("統合App EvidenceをSurface固有Runtime Proofへ流用しない。")
            gaps.append("Authority由来Atomic behaviorのHuman reviewが未完了でCompletion対象外。")
            status = "surface-runtime-proof" if closed else "surface-runtime-contract-gap" if dedicated["report_present"] else "surface-scenario-gap"
            proof = {
                "schema_version": 1,
                "id": f"proof.surface.{surface_id}.{scenario}",
                "atlas_id": "flutter-reference-atlas",
                "generated_at": GENERATED_AT,
                "behavior_scope": "provisional-flutter-surface-not-authority-atomic",
                "surface_id": surface_id,
                "surface_title": surface["title"],
                "domain": surface["domain"],
                "scenario": scenario,
                "status": status,
                "source_bindings": surface["sdk_sources"],
                "source_set_digest": surface["sdk_source_set_digest"],
                "authority_lock_ids": surface["authority_ids"],
                "authority_atomic_binding": None,
                "surface_evidence": mapped,
                "dedicated_runtime": dedicated,
                "integrated_reference": {
                    "manifest": "integrations/reference-system/manifest.json",
                    "trace": trace_binding,
                    "surface_mapped": surface_id in mapping["surface_ids"],
                    "runtime_boundaries": mapping["runtime_boundaries"],
                    "assertions": mapping["assertions"],
                    "status": trace["status"],
                    "runtime_identity": trace["runtime_identity"],
                },
                "closure": {
                    "dedicated_row": True,
                    "dedicated_artifact": True,
                    "surface_specific_evidence": closed,
                    "dedicated_surface_scenario_runtime": closed,
                    "all_variants_driven": dedicated["all_variants_driven"],
                    "retry_zero": dedicated["retry_zero"],
                    "trace_artifact_per_variant": dedicated["trace_artifact_per_variant"],
                    "screenshot_artifact_per_variant": dedicated["screenshot_artifact_per_variant"],
                    "trace_streams_per_variant": dedicated["trace_streams_per_variant"],
                    "oracle_per_variant": dedicated["oracle_per_variant"],
                    "source_harness_digest_bound": dedicated["source_harness_digest_bound"],
                    "real_platform_runtime_identity": dedicated["runtime_identity_complete"],
                    "integrated_runtime_trace": True,
                    "authority_atomic_binding": False,
                    "completion_eligible": False,
                },
                "gaps": gaps,
            }
            relative = f"evidence/scenarios/surfaces/{surface_id.replace('.', '/')}/{scenario}.proof.json"
            content = json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            documents[relative] = content
            proofs.append(proof)
            files.append({"id": proof["id"], "surface_id": surface_id, "scenario": scenario, "path": relative, "digest": "sha256:" + hashlib.sha256(content.encode()).hexdigest(), "status": status})

    by_scenario = {}
    for scenario in SCENARIOS:
        rows = [item for item in proofs if item["scenario"] == scenario]
        by_scenario[scenario] = {
            "rows": len(rows),
            "surface_specific_runtime": sum(item["closure"]["surface_specific_evidence"] for item in rows),
            "dedicated_runtime_closure": sum(item["closure"]["dedicated_surface_scenario_runtime"] for item in rows),
            "legacy_observation_rows": sum(bool(item["surface_evidence"]) for item in rows),
            "integrated_surface_mapped": sum(item["integrated_reference"]["surface_mapped"] for item in rows),
            "explicit_gaps": sum(not item["closure"]["surface_specific_evidence"] for item in rows),
        }
    statuses = Counter(item["status"] for item in proofs)
    source_files = [
        "tooling/scenario_proof/generate.py",
        "tooling/scenario_proof/dedicated_runtime.py",
        "tooling/scenario_proof/test_generate.py",
        "integrations/reference-system/manifest.json",
        "evidence/scenarios/integrated/index.json",
        "atlas/definitive/surface-inventory.json",
        "atlas/definitive/gap-ledger.json",
        "authority/review-queue.snapshot.json",
    ]
    index = {
        "schema_version": 1,
        "id": "flutter-surface-scenario-proof-matrix-v1",
        "atlas_id": "flutter-reference-atlas",
        "generated_at": GENERATED_AT,
        "status": "incomplete-authority-atomic-and-surface-runtime-closure",
        "denominator": f"{inventory['surface_count']}-provisional-flutter-surfaces-x-10-scenarios-not-authority-atomic",
        "source_digests": {item: digest(ROOT / item) for item in source_files},
        "summary": {
            "surfaces": inventory["surface_count"],
            "scenarios": 10,
            "rows": len(proofs),
            "dedicated_artifacts": len(files),
            "surface_specific_runtime_rows": sum(item["closure"]["surface_specific_evidence"] for item in proofs),
            "dedicated_runtime_rows": sum(item["closure"]["dedicated_surface_scenario_runtime"] for item in proofs),
            "legacy_observation_rows": sum(bool(item["surface_evidence"]) for item in proofs),
            "surface_runtime_gap_rows": sum(not item["closure"]["surface_specific_evidence"] for item in proofs),
            "integrated_trace_rows": sum(item["closure"]["integrated_runtime_trace"] for item in proofs),
            "authority_atomic_rows": 0,
            "completion_eligible_rows": 0,
            "status_counts": dict(sorted(statuses.items())),
        },
        "by_scenario": by_scenario,
        "files": files,
        "completion_limits": [
            "54 Surfaceはprovisional inventoryでありAuthority由来Atomic behavior denominatorではない。",
            "統合Reference Appの10 Traceを全Surface固有Runtime Proofとして流用しない。",
            "実Platform identity、Source、Harness、Artifactが揃わないrowは明示gapを維持する。",
            "Surface+Scenarioの全Variantをretry 0で駆動し、各Variantの専用Trace、Artifact、Oracleを持つReportだけがgapを閉じる。",
            "統合App Trace、既存Observation、別CaptureのRuntime metadataを専用Reportへ流用しない。",
            "Authority Human review完了までCompletion eligible rowは0を維持する。",
        ],
    }
    return index, documents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--check-reference", action="store_true")
    parser.add_argument("--reference-root", type=Path, default=ROOT.parent / "frontend-behavior-atlas")
    args = parser.parse_args()
    try:
        if args.check_reference:
            verify_reference(args.reference_root.resolve())
        index, documents = expected_documents()
        index_content = json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.check:
            expected_paths = set(documents)
            actual_paths = {
                str(path.relative_to(ROOT))
                for path in OUTPUT_ROOT.rglob("*.proof.json")
            } if OUTPUT_ROOT.is_dir() else set()
            if actual_paths != expected_paths:
                raise ScenarioProofError(f"Scenario Proof file set drift: actual={len(actual_paths)} expected={len(expected_paths)}")
            for relative, content in documents.items():
                if (ROOT / relative).read_text(encoding="utf-8") != content:
                    raise ScenarioProofError(f"Scenario Proof drift: {relative}")
            if not INDEX_PATH.is_file() or INDEX_PATH.read_text(encoding="utf-8") != index_content:
                raise ScenarioProofError("Scenario Proof index drift")
        else:
            for relative, content in documents.items():
                path = ROOT / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
            INDEX_PATH.write_text(index_content, encoding="utf-8")
    except (OSError, json.JSONDecodeError, subprocess.CalledProcessError, ScenarioProofError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    summary = index["summary"]
    print(f"Flutter Scenario Proofを検証しました: rows={summary['rows']} surface_runtime={summary['surface_specific_runtime_rows']} gaps={summary['surface_runtime_gap_rows']} integrated={summary['integrated_trace_rows']} authority_atomic={summary['authority_atomic_rows']} completion_eligible={summary['completion_eligible_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
