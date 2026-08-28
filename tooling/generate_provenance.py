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
    ("evidence/artifacts/router-eval-report.json", "skill-eval", "Apache-2.0", ["reference-atlas-core-v1"], "evals/evaluate.py"),
    ("evals/flutter-router.skill-eval.json", "skill-eval", "Apache-2.0", ["reference-atlas-core-v1"], "evals/evaluate.py"),
    ("baseline/public-surface-inventory.json", "generated", "Apache-2.0", ["flutter-sdk-3.47.1-macos-arm64", "flutter-engine-3.47.1-deps", "dart-sdk-3.13.1", "devtools-2.60.0"], "tooling/surface_inventory/generate.py"),
    ("sbom.spdx.json", "sbom", "CC0-1.0", ["flutter-sdk-3.47.1-macos-arm64", "dart-container-3.13.1", "reference-atlas-core-v1"], "tooling/generate_supply_chain.py"),
]


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def render(root: Path) -> str:
    artifacts = []
    for relative, kind, license_id, source_ids, generator in ARTIFACTS:
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
    print(f"Provenance生成済み: {len(ARTIFACTS)} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
