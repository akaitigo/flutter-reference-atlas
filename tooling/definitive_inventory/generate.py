#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Flutter Definitive Surface InventoryとGap Ledgerを固定SDKから生成する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCENARIOS = ("normal", "boundary", "rejection", "failure", "recovery")
RUNTIME_KINDS = {"runtime", "build-runtime", "device-runtime", "browser-runtime"}


class InventoryError(RuntimeError):
    pass


def runtime_profile_gaps(
    runtime_observations: list[dict[str, Any]],
    required_profiles: list[str],
    required_scenarios: list[str],
    minimum_variants: int,
    reference_app_required: bool,
) -> list[dict[str, str]]:
    """Require the scenario/variant/reference-app contract on every profile."""
    gaps: list[dict[str, str]] = []
    for profile in required_profiles:
        profile_observations = [
            item for item in runtime_observations if item.get("runtime_profile") == profile
        ]
        if not profile_observations:
            gaps.append({"kind": "runtime-profile", "id": profile})
        observed_scenarios = {item["scenario"] for item in profile_observations}
        for scenario in required_scenarios:
            if scenario not in observed_scenarios:
                gaps.append({"kind": "profile-scenario", "id": f"{profile}:{scenario}"})
        variants = {item["variant"] for item in profile_observations}
        if len(variants) < minimum_variants:
            gaps.append(
                {
                    "kind": "profile-variant",
                    "id": f"{profile}:{len(variants)}/{minimum_variants}",
                }
            )
        if reference_app_required and not any(
            item.get("reference_app") is True for item in profile_observations
        ):
            gaps.append({"kind": "profile-reference-app", "id": profile})
    return gaps


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InventoryError(f"JSONを読めません: {path}: {error}") from error
    if not isinstance(value, dict):
        raise InventoryError(f"JSON rootはobjectである必要があります: {path}")
    return value


def canonical_digest(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def resolve_sources(sdk_root: Path, patterns: list[str]) -> list[dict[str, str]]:
    paths: dict[str, Path] = {}
    for pattern in patterns:
        matches = [path for path in sdk_root.glob(pattern) if path.is_file()]
        if not matches:
            raise InventoryError(f"SDK Source patternが0件です: {pattern}")
        for path in matches:
            relative = path.relative_to(sdk_root).as_posix()
            paths[relative] = path
    return [
        {"path": relative, "digest": digest_file(paths[relative])}
        for relative in sorted(paths)
    ]


def collect_evidence_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    for path in sorted((root / "evidence").glob("*.evidence.yaml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("id: "):
                ids.add(line.removeprefix("id: ").strip())
                break
    return ids


def validate_requirements(document: dict[str, Any]) -> list[dict[str, Any]]:
    if document.get("schema_version") != 2:
        raise InventoryError("requirements.schema_versionは2である必要があります")
    surfaces = document.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise InventoryError("surfacesが空です")
    known: set[str] = set()
    for surface in surfaces:
        surface_id = surface.get("id")
        if not isinstance(surface_id, str) or surface_id in known:
            raise InventoryError(f"Surface IDが不正または重複しています: {surface_id}")
        known.add(surface_id)
        if not surface.get("source_globs"):
            raise InventoryError(f"Surface {surface_id}にsource_globsがありません")
        profiles = surface.get("required_runtime_profiles")
        if not isinstance(profiles, list) or not profiles:
            raise InventoryError(f"Surface {surface_id}にrequired_runtime_profilesがありません")
        scenarios = surface.get("required_scenarios", list(SCENARIOS))
        unknown = sorted(set(scenarios) - set(SCENARIOS))
        if unknown:
            raise InventoryError(f"Surface {surface_id}のScenarioが不正です: {unknown}")
        if int(surface.get("minimum_variants", 2)) < 2:
            raise InventoryError(f"Surface {surface_id}の比較Variantは2以上必要です")
    return surfaces


def read_atlas_status(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("status: "):
            return line.removeprefix("status: ").strip()
    raise InventoryError("atlas.yamlにstatusがありません")


def collect_authority_ids(path: Path) -> set[str]:
    result: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- id: "):
            result.add(stripped.removeprefix("- id: ").strip())
    return result


def generate(root: Path, sdk_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    requirements_path = root / "definitive/requirements.json"
    observations_path = root / "definitive/runtime-observations.json"
    requirements = load_json(requirements_path)
    observations_doc = load_json(observations_path)
    surfaces = validate_requirements(requirements)
    known_ids = {surface["id"] for surface in surfaces}
    evidence_ids = collect_evidence_ids(root)
    skill_eval_by_surface: dict[str, list[str]] = {}
    skill_eval_path = root / "evidence/artifacts/definitive-router-eval-report.json"
    if skill_eval_path.is_file():
        skill_eval = load_json(skill_eval_path)
        for result in skill_eval.get("results", []):
            actual = result.get("actual", {})
            surface_id = actual.get("surface_id")
            if result.get("passed") is True and surface_id in known_ids:
                skill_eval_by_surface.setdefault(surface_id, []).append(result["id"])
    authority_ids = collect_authority_ids(root / "sources.lock.yaml")
    for surface in surfaces:
        unknown_authorities = sorted(set(surface["authority_ids"]) - authority_ids)
        if unknown_authorities:
            raise InventoryError(
                f"Surface {surface['id']}が未知Authorityを参照しています: {unknown_authorities}"
            )

    observations_by_surface: dict[str, list[dict[str, Any]]] = {key: [] for key in known_ids}
    for observation in observations_doc.get("observations", []):
        surface_id = observation.get("surface_id")
        if surface_id not in known_ids:
            raise InventoryError(f"Observationが未知Surfaceを参照しています: {surface_id}")
        if observation.get("scenario") not in SCENARIOS:
            raise InventoryError(f"ObservationのScenarioが不正です: {observation}")
        evidence_id = observation.get("evidence_id")
        if evidence_id not in evidence_ids:
            raise InventoryError(f"Observationが未知Evidenceを参照しています: {evidence_id}")
        artifact_path = root / str(observation.get("artifact"))
        if not artifact_path.is_file():
            raise InventoryError(f"Observation Artifactがありません: {artifact_path}")
        normalized = dict(observation)
        normalized["artifact_digest"] = digest_file(artifact_path)
        observations_by_surface[surface_id].append(normalized)

    inventory_surfaces: list[dict[str, Any]] = []
    ledger_entries: list[dict[str, Any]] = []
    for definition in surfaces:
        surface_id = definition["id"]
        sources = resolve_sources(sdk_root, definition["source_globs"])
        required_scenarios = definition.get("required_scenarios", list(SCENARIOS))
        required_profiles = definition["required_runtime_profiles"]
        minimum_variants = int(definition.get("minimum_variants", 2))
        observations = observations_by_surface[surface_id]
        runtime_observations = [
            item
            for item in observations
            if item.get("verified") is True and item.get("evidence_kind") in RUNTIME_KINDS
        ]
        satisfied_scenarios = sorted({item["scenario"] for item in runtime_observations})
        satisfied_profiles = sorted({item["runtime_profile"] for item in runtime_observations})
        variants = sorted({item["variant"] for item in runtime_observations})
        reference_integrated = any(item.get("reference_app") is True for item in runtime_observations)
        skill_eval_ids = sorted(
            set(skill_eval_by_surface.get(surface_id, []))
            | {
                item["skill_eval_id"]
                for item in runtime_observations
                if isinstance(item.get("skill_eval_id"), str) and item["skill_eval_id"]
            }
        )

        gaps: list[dict[str, str]] = []
        for scenario in required_scenarios:
            if scenario not in satisfied_scenarios:
                gaps.append({"kind": "scenario", "id": scenario})
        gaps.extend(
            runtime_profile_gaps(
                runtime_observations,
                required_profiles,
                required_scenarios,
                minimum_variants,
                definition.get("reference_app_required", True),
            )
        )
        if definition.get("reference_app_required", True) and not reference_integrated:
            gaps.append({"kind": "reference-app", "id": "integration"})
        if definition.get("skill_eval_required", True) and not skill_eval_ids:
            gaps.append({"kind": "skill-eval", "id": "surface-routing"})

        inventory_surfaces.append(
            {
                "id": surface_id,
                "title": definition["title"],
                "domain": definition["domain"],
                "capability": definition["capability"],
                "authority_ids": definition["authority_ids"],
                "sdk_sources": sources,
                "sdk_source_set_digest": canonical_digest(sources),
                "required_scenarios": required_scenarios,
                "required_runtime_profiles": required_profiles,
                "minimum_variants": minimum_variants,
                "reference_app_required": definition.get("reference_app_required", True),
                "skill_eval_required": definition.get("skill_eval_required", True),
            }
        )
        ledger_entries.append(
            {
                "surface_id": surface_id,
                "state": "closed" if not gaps else "open",
                "observations": sorted(
                    observations,
                    key=lambda item: (
                        item["runtime_profile"], item["scenario"], item["variant"]
                    ),
                ),
                "satisfied": {
                    "scenarios": satisfied_scenarios,
                    "runtime_profiles": satisfied_profiles,
                    "variants": variants,
                    "reference_app": reference_integrated,
                    "skill_eval_ids": skill_eval_ids,
                },
                "gaps": gaps,
            }
        )

    open_entries = [entry for entry in ledger_entries if entry["state"] == "open"]
    inventory = {
        "schema_version": 2,
        "atlas_id": "flutter-reference-atlas",
        "coverage_epoch": requirements["coverage_epoch"],
        "flutter_version": requirements["flutter_version"],
        "derivation": {
            "requirements": "definitive/requirements.json",
            "runtime_observations": "definitive/runtime-observations.json",
            "sdk_root_kind": "version-locked-local-source",
        },
        "surface_count": len(inventory_surfaces),
        "surfaces": inventory_surfaces,
    }
    ledger = {
        "schema_version": 2,
        "atlas_id": "flutter-reference-atlas",
        "coverage_epoch": requirements["coverage_epoch"],
        "completion_semantics": {
            "static_fixture_substitutes_runtime": False,
            "other_platform_substitutes_required_profile": False,
            "infeasible_counts_as_closed": False,
            "required_scenarios": list(SCENARIOS),
        },
        "summary": {
            "surface_count": len(ledger_entries),
            "closed": len(ledger_entries) - len(open_entries),
            "open": len(open_entries),
            "definitive_status": "incomplete" if open_entries else "complete-candidate",
        },
        "entries": ledger_entries,
    }
    atlas_status = read_atlas_status(root / "atlas.yaml")
    if open_entries and atlas_status != "incomplete":
        raise InventoryError(
            f"Definitive Gapが{len(open_entries)}件ある間はatlas statusをincompleteにしてください: {atlas_status}"
        )
    if not open_entries and atlas_status == "complete":
        raise InventoryError("Definitive Closure後も新Certificate発行前はstatus=incompleteを維持してください")
    return inventory, ledger


def write_or_check(path: Path, value: dict[str, Any], check: bool) -> None:
    data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if check:
        actual = path.read_text(encoding="utf-8") if path.is_file() else ""
        if actual != data:
            raise InventoryError(f"生成物が古いか欠落しています: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--sdk-root", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        inventory, ledger = generate(root, args.sdk_root.resolve())
        write_or_check(root / "atlas/definitive/surface-inventory.json", inventory, args.check)
        write_or_check(root / "atlas/definitive/gap-ledger.json", ledger, args.check)
    except (InventoryError, OSError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    print(
        f"Definitive Inventoryを検証しました: surfaces={inventory['surface_count']} "
        f"closed={ledger['summary']['closed']} open={ledger['summary']['open']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
