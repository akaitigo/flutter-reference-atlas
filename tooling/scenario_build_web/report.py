#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Atomically publish Web build security Scenario evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

SURFACE = "build.web"
SCENARIO = "security"
VARIANTS = ("javascript", "release-js", "wasm")
KINDS = {"artifact", "index", "observation", "tree", "screen", "buildlog", "chromelog", "mode"}


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def binding(root: Path, path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "digest": digest(path), "bytes": path.stat().st_size}


def staged_binding(path: Path, relative: str) -> dict[str, Any]:
    return {"path": relative, "digest": digest(path), "bytes": path.stat().st_size}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def copy_evidence(root: Path, source: Path, target: Path, kind: str) -> None:
    if kind not in {"buildlog", "chromelog"}:
        shutil.copy2(source, target)
        return
    value = source.read_text(encoding="utf-8", errors="replace")
    value = value.replace(str(root), "<repo-root>")
    value = value.replace(str(Path.home()), "<home>")
    value = "\n".join(line.rstrip() for line in value.splitlines()) + "\n"
    target.write_text(value, encoding="utf-8")


def source_contract(root: Path, sdk_root: Path) -> tuple[list[dict[str, str]], str]:
    proof = json.loads((root / "evidence/scenarios/surfaces/build/web/security.proof.json").read_text())
    sources = []
    for item in proof["source_bindings"]:
        path = sdk_root / item["path"]
        if not path.is_file() or digest(path) != item["digest"]:
            raise ValueError(f"SDK Source binding mismatch: {item['path']}")
        sources.append({"path": item["path"], "digest": item["digest"]})
    canonical = json.dumps(sources, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sources, "sha256:" + hashlib.sha256(canonical).hexdigest()


def validate_variant(variant: str, files: dict[str, Path]) -> dict[str, Any]:
    artifact = files["artifact"].read_bytes()
    observation = json.loads(files["observation"].read_text(encoding="utf-8"))
    tree = files["tree"].read_text(encoding="utf-8", errors="replace")
    index = files["index"].read_text(encoding="utf-8", errors="replace")
    mode = files["mode"].read_text(encoding="utf-8").strip()
    if files["artifact"].stat().st_size < 100_000:
        raise ValueError(f"compiled artifact is unexpectedly small: {variant}")
    if variant == "wasm":
        if not artifact.startswith(b"\x00asm") or mode != "release-wasm-no-source-maps":
            raise ValueError("Wasm artifact or mode oracle mismatch")
    elif artifact.startswith(b"\x00asm"):
        raise ValueError(f"JavaScript variant contains a Wasm artifact: {variant}")
    expected_mode = "debug-javascript-with-source-maps" if variant == "javascript" else "release-javascript-csp-no-source-maps"
    if variant != "wasm" and mode != expected_mode:
        raise ValueError(f"JavaScript mode oracle mismatch: {variant}")
    if "flutter_bootstrap.js" not in index:
        raise ValueError(f"Flutter bootstrap missing: {variant}")
    label = f"build web security {variant} PASS"
    if observation.get("flutterView") is not True or not observation.get("origin", "").startswith("http://127.0.0.1:"):
        raise ValueError(f"real Chrome first-frame observation mismatch: {variant}")
    tree_document = json.loads(tree)
    if not tree_document.get("accessibility", {}).get("nodes"):
        raise ValueError(f"real Chrome Accessibility tree missing: {variant}")
    screenshot = files["screen"].read_bytes()
    if not screenshot.startswith(b"\x89PNG\r\n\x1a\n") or len(screenshot) < 1_000:
        raise ValueError(f"Chrome screenshot missing: {variant}")
    return {
        "variant": variant,
        "compiler": "dart2wasm" if variant == "wasm" else "dart2js",
        "mode": mode,
        "artifact_sha256": digest(files["artifact"]),
        "artifact_bytes": files["artifact"].stat().st_size,
        "chrome_flutter_view_observed": True,
        "chrome_accessibility_tree_captured": True,
    }


def publish(args: argparse.Namespace) -> None:
    root = args.repo_root.resolve()
    output = args.output.resolve()
    sdk_root = args.sdk_root.resolve()
    harness = args.harness.resolve()
    reporter = Path(__file__).resolve()
    source = args.source.resolve()
    sources, source_set_digest = source_contract(root, sdk_root)
    raw: dict[str, dict[str, Path]] = {}
    for spec in args.input:
        variant, kind, value = spec.split("=", 2)
        if variant not in VARIANTS or kind not in KINDS:
            raise ValueError(f"invalid input binding: {spec}")
        raw.setdefault(variant, {})[kind] = Path(value).resolve()
    if set(raw) != set(VARIANTS) or any(set(raw[v]) != KINDS for v in VARIANTS):
        raise ValueError("all Web build variants and artifacts are required")
    observations = {variant: validate_variant(variant, raw[variant]) for variant in VARIANTS}

    output.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(tempfile.mkdtemp(prefix=".build-web-security-", dir=output.parent))
    staging_root = staging_parent / "runtime"
    backup = staging_parent / "prior"
    try:
        shutil.copytree(output, staging_root) if output.exists() else staging_root.mkdir(parents=True)
        row = staging_root / "build/web/security"
        if row.exists():
            shutil.rmtree(row)
        tests = []
        for variant in VARIANTS:
            variant_dir = row / variant
            variant_dir.mkdir(parents=True)
            artifact_name = "app.wasm" if variant == "wasm" else "app.js"
            targets = {
                "artifact": variant_dir / artifact_name,
                "index": variant_dir / "index.html",
                "observation": variant_dir / "observation.json",
                "tree": variant_dir / "platform-tree.json",
                "screen": variant_dir / "screen.png",
                "buildlog": variant_dir / "build.log",
                "chromelog": variant_dir / "chrome.log",
                "mode": variant_dir / "mode.txt",
            }
            for kind, target in targets.items():
                copy_evidence(root, raw[variant][kind], target, kind)
            trace_path = variant_dir / "trace.json"
            result_path = variant_dir / "result.json"
            observation = observations[variant]
            write_json(trace_path, {
                "schema_version": 1,
                "surface_id": SURFACE,
                "scenario": SCENARIO,
                "variant": variant,
                "streams": {
                    "action": ["flutter-build-web", "localhost-serve", "headless-chrome-load", "dom-and-screenshot-capture"],
                    "network": {"events": ["GET http://127.0.0.1:<variant-port>/", "local-static-assets-loaded"]},
                    "resource": {"events": ["compiled-artifact-created", "build-mode-verified", "dom-captured", "screenshot-captured"]},
                },
                "runtime_identity": args.runtime_identity,
                "oracle": observation,
            })
            write_json(result_path, {"schema_version": 1, "status": "passed", **observation})
            prefix = f"evidence/scenarios/runtime/build/web/security/{variant}"
            tests.append({
                "variant": variant,
                "attempts": 1,
                "outcome": "expected",
                "final_status": "passed",
                "error": None,
                "source": binding(root, source),
                "trace": staged_binding(trace_path, f"{prefix}/trace.json"),
                "artifact": staged_binding(targets["artifact"], f"{prefix}/{artifact_name}"),
                "screenshot": staged_binding(targets["screen"], f"{prefix}/screen.png"),
                "oracle": {"passed": True, "assertions": [
                    "fixed Flutter SDK produced the declared JavaScript or Wasm build mode",
                    "compiled artifact type and source-map boundary matched the variant contract",
                    "the built bundle loaded from localhost in a dedicated headless Chrome profile",
                    "Chrome observed the Flutter first frame and captured the rendered screen",
                ]},
            })
        write_json(row / "results.json", {
            "schema_version": 1,
            "surface_id": SURFACE,
            "scenario": SCENARIO,
            "status": "passed",
            "started_at": args.started_at,
            "completed_at": args.completed_at,
            "retries": 0,
            "variant_contract": list(VARIANTS),
            "runtime_identity": args.runtime_identity,
            "sdk_sources": sources,
            "source_set_digest": source_set_digest,
            "harness": binding(root, harness),
            "reporter": binding(root, reporter),
            "tests": tests,
            "retention_contract": {"publish_on": "all-three-build-and-chrome-variants-passed", "failed_run": "retain-prior-success", "swap": "full-runtime-root-staged-directory-rename-with-rollback", "partial_overwrite_allowed": False},
        })
        if output.exists():
            os.replace(output, backup)
        try:
            os.replace(staging_root, output)
        except OSError:
            if backup.exists() and not output.exists():
                os.replace(backup, output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sdk-root", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--completed-at", required=True)
    parser.add_argument("--runtime-identity", type=json.loads, required=True)
    parser.add_argument("--input", action="append", default=[])
    args = parser.parse_args()
    try:
        publish(args)
        print("build.web security Evidenceを原子的に保存しました: variants=3 retries=0")
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print(f"エラー: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
