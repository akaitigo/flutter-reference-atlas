#!/usr/bin/env python3
"""Release候補ArtifactのProvenanceを実file digestから生成する。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ARTIFACTS = [
    ("evidence/artifacts/formal-local-closure-report.json", "test-report", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "dart-sdk-3.13.1", "local-runtime-inventory"], "tooling/evidence_capture/bin/capture.dart"),
    ("evidence/artifacts/container-conflict-report.json", "test-report", "Apache-2.0", ["dart-sdk-3.13.1", "dart-container-3.13.1"], "scripts/labs-container.sh"),
    ("evidence/artifacts/android-emulator-integration-report.json", "test-report", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "android-emulator-runtime-inventory"], "scripts/labs-simulator.sh"),
    ("evidence/artifacts/definitive-android-method-channel-report.json", "test-report", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "android-emulator-runtime-inventory"], "scripts/definitive-android-runtime.sh"),
    ("evidence/artifacts/definitive-android-method-channel.log", "capture", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "android-emulator-runtime-inventory"], "scripts/definitive-android-runtime.sh"),
    ("evidence/artifacts/definitive-web-chrome-report.json", "test-report", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "dart-sdk-3.13.1"], "scripts/definitive-web-runtime.sh"),
    ("evidence/artifacts/definitive-web-chrome-js.log", "capture", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "dart-sdk-3.13.1"], "scripts/definitive-web-runtime.sh"),
    ("evidence/artifacts/definitive-web-chrome-wasm.log", "capture", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "dart-sdk-3.13.1"], "scripts/definitive-web-runtime.sh"),
    ("evidence/artifacts/router-eval-report.json", "skill-eval", "Apache-2.0", ["reference-atlas-core-v1"], "evals/evaluate.py"),
    ("evals/flutter-router.skill-eval.json", "skill-eval", "Apache-2.0", ["reference-atlas-core-v1"], "evals/evaluate.py"),
    ("evidence/artifacts/definitive-router-eval-report.json", "skill-eval", "Apache-2.0", ["reference-atlas-core-v1", "flutter-sdk-3.47.1-macos-arm64"], "evals/evaluate_definitive.py"),
    ("evals/flutter-router.definitive-mastery-eval.json", "skill-eval", "Apache-2.0", ["reference-atlas-core-v1", "flutter-sdk-3.47.1-macos-arm64", "flutter-engine-3.47.1-deps", "dart-sdk-3.13.1", "devtools-2.60.0"], "evals/evaluate_mastery.py"),
    ("evals/flutter-router.agent-forward-eval.json", "skill-eval", "Apache-2.0", ["reference-atlas-core-v1"], "evals/evaluate_mastery.py"),
    (".agents/skills/flutter-reference-router/references/mastery-contract.json", "generated", "Apache-2.0", ["reference-atlas-core-v1"], "evals/evaluate_mastery.py"),
    ("integrations/reference-system/manifest.json", "document", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64"], "human-authored-reference-contract"),
    ("definitive/fe-reference-system.lock.json", "document", "Apache-2.0", ["reference-atlas-core-v1"], "human-authored-reference-lock"),
    ("evidence/scenarios/integrated/index.json", "test-report", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "dart-sdk-3.13.1"], "tooling/scenario_proof/capture_runtime.py"),
    ("evidence/scenarios/index.json", "generated", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "flutter-engine-3.47.1-deps", "dart-sdk-3.13.1", "devtools-2.60.0"], "tooling/scenario_proof/generate.py"),
    ("evidence/scenarios/closure-plan.json", "generated", "Apache-2.0", ["reference-atlas-core-v1", "flutter-sdk-3.47.1-macos-arm64"], "tooling/evidence_dependency/graph.py"),
    ("baseline/evidence-dependency-v1.json", "generated", "Apache-2.0", ["reference-atlas-core-v1"], "tooling/evidence_dependency/graph.py"),
    ("definitive/evidence-dependency-contract.json", "document", "Apache-2.0", ["reference-atlas-core-v1"], "human-authored-reference-contract"),
    ("baseline/public-surface-inventory.json", "generated", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "flutter-engine-3.47.1-deps", "dart-sdk-3.13.1", "devtools-2.60.0"], "tooling/surface_inventory/generate.py"),
    ("atlas/definitive/surface-inventory.json", "generated", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "flutter-engine-3.47.1-deps", "dart-sdk-3.13.1", "devtools-2.60.0"], "tooling/definitive_inventory/generate.py"),
    ("atlas/definitive/gap-ledger.json", "generated", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "flutter-engine-3.47.1-deps", "dart-sdk-3.13.1", "devtools-2.60.0"], "tooling/definitive_inventory/generate.py"),
    ("atlas/definitive/flutter-depth-parity.json", "generated", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "flutter-engine-3.47.1-deps", "dart-sdk-3.13.1", "devtools-2.60.0"], "tooling/fe_parity/generate.py"),
    ("authority/extraction.snapshot.json", "generated", "Apache-2.0", ["reference-atlas-core-v1", "flutter-sdk-3.47.1-macos-arm64", "flutter-release-manifest-macos", "flutter-engine-3.47.1-deps", "dart-sdk-3.13.1", "devtools-2.60.0", "flutter-3.47-release-notes", "dart-3.13-changelog", "flutter-widgets-api", "local-runtime-inventory", "android-emulator-runtime-inventory", "dart-container-3.13.1"], "tooling/authority_extraction/extract.py"),
    ("authority/body-inventory.snapshot.json", "generated", "Apache-2.0", ["reference-atlas-core-v1", "flutter-sdk-3.47.1-macos-arm64", "flutter-release-manifest-macos", "flutter-engine-3.47.1-deps", "dart-sdk-3.13.1", "devtools-2.60.0", "flutter-3.47-release-notes", "dart-3.13-changelog", "flutter-widgets-api", "local-runtime-inventory", "android-emulator-runtime-inventory", "dart-container-3.13.1"], "tooling/authority_extraction/body_inventory.py"),
    ("authority/review-queue.snapshot.json", "generated", "Apache-2.0", ["reference-atlas-core-v1", "flutter-sdk-3.47.1-macos-arm64", "flutter-release-manifest-macos", "flutter-engine-3.47.1-deps", "dart-sdk-3.13.1", "devtools-2.60.0", "flutter-3.47-release-notes", "dart-3.13-changelog", "flutter-widgets-api", "local-runtime-inventory", "android-emulator-runtime-inventory", "dart-container-3.13.1"], "tooling/authority_extraction/review_queue.py"),
    ("authority/reviews/decisions.json", "document", "Apache-2.0", ["reference-atlas-core-v1"], "human-authority-review"),
    ("baseline/authority-body-inventory-v1.json", "generated", "Apache-2.0", ["reference-atlas-core-v1"], "tooling/authority_extraction/body_baseline.py"),
    ("evidence/artifacts/authority-body-non-regression-report.json", "test-report", "Apache-2.0", ["reference-atlas-core-v1"], "tooling/authority_extraction/body_baseline.py"),
    ("baseline/public-main-non-regression-v1.json", "generated", "Apache-2.0", ["reference-atlas-core-v1"], "tooling/non_regression/audit.py"),
    ("environments/definitive/host-capabilities.json", "capture", "Apache-2.0", ["local-runtime-inventory"], "manual-host-audit"),
    ("sbom.spdx.json", "sbom", "CC0-1.0", ["flutter-sdk-3.47.1-macos-arm64", "dart-container-3.13.1", "reference-atlas-core-v1"], "tooling/generate_supply_chain.py"),
]


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def scenario_runtime_generator(path: Path) -> str:
    relative = path.as_posix()
    if "/build/web/security/" in relative:
        return "scripts/scenario-build-web-security-runtime.sh"
    if "/build/android/security/" in relative:
        return "scripts/scenario-build-android-security-runtime.sh"
    if "/platform/method-channel/" in relative:
        return "scripts/scenario-method-channel-runtime.sh"
    return "scripts/scenario-security-tranche-runtime.sh"


def render(root: Path) -> str:
    artifacts = []
    artifact_specs = list(ARTIFACTS)
    artifact_specs.extend(
        (str(path.relative_to(root)), "generated", "Apache-2.0", [path.stem], "tooling/authority_extraction/extract.py")
        for path in sorted((root / "authority/surfaces-draft").glob("*.json"))
    )
    artifact_specs.extend(
        (str(path.relative_to(root)), "generated", "Apache-2.0", json.loads(path.read_text(encoding="utf-8"))["source_ids"], "tooling/authority_extraction/body_inventory.py")
        for path in sorted((root / "authority/body-inventory-draft").glob("*.json"))
    )
    artifact_specs.extend(
        (str(path.relative_to(root)), "generated", "Apache-2.0", sorted({source_id for item in json.loads(path.read_text(encoding="utf-8"))["items"] for source_id in item["source_ids"]}), "tooling/authority_extraction/review_queue.py")
        for path in sorted((root / "authority/review-queue-draft").glob("*.json"))
    )
    artifact_specs.extend(
        (str(path.relative_to(root)), "test-report", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "dart-sdk-3.13.1"], "tooling/scenario_proof/capture_runtime.py")
        for path in sorted((root / "evidence/scenarios/integrated").glob("*.trace.json"))
    )
    artifact_specs.extend(
        (str(path.relative_to(root)), "generated", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "flutter-engine-3.47.1-deps", "dart-sdk-3.13.1", "devtools-2.60.0"], "tooling/scenario_proof/generate.py")
        for path in sorted((root / "evidence/scenarios/surfaces").rglob("*.proof.json"))
    )
    artifact_specs.extend(
        (
            str(path.relative_to(root)),
            "capture" if path.suffix in {".png", ".xml"} else "test-report",
            "Apache-2.0",
            ["flutter-sdk-3.47.1-macos-arm64", "android-emulator-runtime-inventory"],
            scenario_runtime_generator(path),
        )
        for path in sorted((root / "evidence/scenarios/runtime").rglob("*"))
        if path.is_file()
    )
    for relative, kind, license_id, source_ids, generator in artifact_specs:
        artifacts.append({
            "path": relative,
            "digest": digest(root / relative),
            "kind": kind,
            "license": license_id,
            "source_ids": source_ids,
            "generated_by": generator,
        })
    document = {
        "schema_version": 1,
        "atlas_id": "flutter-reference-atlas",
        "generated_at": "2026-08-28T07:20:00Z",
        "artifacts": artifacts,
    }
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "provenance.yaml"
    content = render(root)
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != content:
            print("provenance.yamlが現在のArtifact Digestと一致しません。")
            return 1
        print("Provenance検証済み")
        return 0
    output.write_text(content, encoding="utf-8")
    print(f"Provenance生成済み: {len(json.loads(content)['artifacts'])} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
