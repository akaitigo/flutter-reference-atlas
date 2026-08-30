#!/usr/bin/env python3
"""固定Lockから第三者ManifestとSPDX 2.3 SBOMを生成する。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


APACHE_PACKAGES = {"clock", "fake_async", "material_color_utilities", "webdriver"}
SKIP_SDK_PACKAGES = {
    "atlas_runtime_probe",
    "flutter",
    "flutter_driver",
    "flutter_test",
    "fuchsia_remote_debug_protocol",
    "integration_test",
    "sky_engine",
}


def locked_pub_packages(lock: str) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lock.splitlines():
        match = re.match(r"^  ([a-zA-Z0-9_]+):$", line)
        if match:
            if current and current["name"] not in SKIP_SDK_PACKAGES and "version" in current:
                packages.append(current)
            current = {"name": match.group(1)}
            continue
        if current is None:
            continue
        checksum = re.match(r'^      sha256: "?([a-f0-9]{64})"?$', line)
        version = re.match(r'^    version: "?([^"\s]+)"?$', line)
        if checksum:
            current["sha256"] = checksum.group(1)
        elif version:
            current["version"] = version.group(1)
    if current and current["name"] not in SKIP_SDK_PACKAGES and "version" in current:
        packages.append(current)
    return packages


def license_for(name: str) -> str:
    return "Apache-2.0" if name in APACHE_PACKAGES else "BSD-3-Clause"


def make_documents(root: Path) -> tuple[str, str]:
    lock = (root / "reference-systems/operations-workspace/pubspec.lock").read_text(encoding="utf-8")
    pub_packages = locked_pub_packages(lock)
    artifacts = [
        {"id":"flutter-sdk", "name":"Flutter SDK", "kind":"source", "version":"3.47.1", "source":"https://github.com/flutter/flutter/tree/6655482ec06e547f90abf8ae7590466f4415978d", "license":"BSD-3-Clause", "redistribution":"link-only"},
        {"id":"dart-container", "name":"Dart SDK container image", "kind":"source", "version":"3.13.1-sdk", "source":"https://hub.docker.com/_/dart", "license":"BSD-3-Clause", "redistribution":"metadata-only"},
        {"id":"go-yaml-v3", "name":"gopkg.in/yaml.v3", "kind":"go-module", "version":"v3.0.1", "source":"https://gopkg.in/yaml.v3", "license":"MIT AND Apache-2.0", "redistribution":"allowed"},
        {"id":"actions-checkout", "name":"actions/checkout", "kind":"github-action", "version":"v4", "source":"https://github.com/actions/checkout", "license":"MIT", "redistribution":"link-only"},
        {"id":"actions-setup-go", "name":"actions/setup-go", "kind":"github-action", "version":"v5", "source":"https://github.com/actions/setup-go", "license":"MIT", "redistribution":"link-only"},
        {"id":"subosito-flutter-action", "name":"subosito/flutter-action", "kind":"github-action", "version":"v2", "source":"https://github.com/subosito/flutter-action", "license":"MIT", "redistribution":"link-only"},
        {"id":"frontend-depth-reference", "name":"FE Depth Reference v1", "kind":"source", "version":"4a0b2df8e2091a963bd0e0e1bbccef9c84b49a45", "source":"https://github.com/akaitigo/frontend-behavior-atlas/blob/4a0b2df8e2091a963bd0e0e1bbccef9c84b49a45/FE_DEPTH_REFERENCE.json", "license":"Apache-2.0", "redistribution":"allowed"},
    ]
    for package in pub_packages:
        name, version = package["name"], package["version"]
        artifacts.append({
            "id": f"pub-{name.replace('_', '-')}", "name": name, "kind": "source", "version": version,
            "source": f"https://pub.dev/packages/{name}/versions/{version}",
            "license": license_for(name), "redistribution": "allowed",
        })
    third_party = {"schema_version": 1, "artifacts": artifacts}

    sbom_artifacts = [artifact for artifact in artifacts if artifact["kind"] == "go-module"]
    packages = [{
        "name":"flutter-reference-atlas", "SPDXID":"SPDXRef-Package-Atlas", "versionInfo":"1.0.0",
        "downloadLocation":"https://github.com/akaitigo/flutter-reference-atlas", "filesAnalyzed":False,
        "licenseConcluded":"Apache-2.0", "licenseDeclared":"Apache-2.0", "copyrightText":"Copyright 2026 akaitigo",
    }]
    for index, artifact in enumerate(sbom_artifacts, start=1):
        package = {
            "name": artifact["name"], "SPDXID": f"SPDXRef-Package-{index}", "versionInfo": artifact["version"].removeprefix("v"),
            "downloadLocation": artifact["source"], "filesAnalyzed": False,
            "licenseConcluded": artifact["license"], "licenseDeclared": artifact["license"], "copyrightText": "Copyright respective contributors",
        }
        pub_match = next((item for item in pub_packages if item["name"] == artifact["name"]), None)
        if pub_match and "sha256" in pub_match:
            package["checksums"] = [{"algorithm":"SHA256", "checksumValue":pub_match["sha256"]}]
        packages.append(package)
    sbom = {
        "spdxVersion":"SPDX-2.3", "dataLicense":"CC0-1.0", "SPDXID":"SPDXRef-DOCUMENT",
        "name":"flutter-reference-atlas-v1.0.0-complete",
        "documentNamespace":"https://github.com/akaitigo/flutter-reference-atlas/sbom/v1.0.0/2026-08-28",
        "creationInfo":{"created":"2026-08-28T07:15:00Z", "creators":["Tool: tooling/generate_supply_chain.py"]},
        "documentDescribes":["SPDXRef-Package-Atlas"], "packages":packages,
        "relationships":[{"spdxElementId":"SPDXRef-DOCUMENT", "relationshipType":"DESCRIBES", "relatedSpdxElement":"SPDXRef-Package-Atlas"}] + [
            {"spdxElementId":"SPDXRef-Package-Atlas", "relationshipType":"DEPENDS_ON", "relatedSpdxElement":f"SPDXRef-Package-{index}"}
            for index in range(1, len(sbom_artifacts) + 1)
        ],
    }
    return (
        json.dumps(third_party, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        json.dumps(sbom, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    third_party, sbom = make_documents(root)
    outputs = {root / "third_party/manifest.yaml": third_party, root / "sbom.spdx.json": sbom}
    if args.check:
        mismatches = [path for path, content in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
        if mismatches:
            for path in mismatches:
                print(f"Supply Chain生成物が正本と一致しません: {path.relative_to(root)}")
            return 1
        print("Supply Chain生成物検証済み")
        return 0
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"Supply Chain生成済み: third-party={len(json.loads(third_party)['artifacts'])} packages={len(json.loads(sbom)['packages'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
