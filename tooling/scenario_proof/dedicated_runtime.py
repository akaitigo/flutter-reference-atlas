#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate dedicated Surface + Scenario + Variant runtime evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def report_path(surface_id: str, scenario: str) -> str:
    return f"evidence/scenarios/runtime/{surface_id.replace('.', '/')}/{scenario}/results.json"


def _binding(root: Path, value: Any, *, prefix: str | None = None) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(value, dict):
        return None, ["binding-missing"]
    relative = value.get("path")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        return None, ["binding-path-invalid"]
    if prefix is not None and not relative.startswith(prefix):
        return None, ["binding-is-not-dedicated-row-artifact"]
    path = root / relative
    if not path.is_file():
        return None, ["binding-file-missing"]
    observed = {"path": relative, "digest": sha256(path), "bytes": path.stat().st_size}
    errors = []
    if value.get("digest") != observed["digest"]:
        errors.append("binding-digest-mismatch")
    if value.get("bytes") != observed["bytes"]:
        errors.append("binding-size-mismatch")
    if observed["bytes"] == 0:
        errors.append("binding-empty")
    return observed, errors


def _runtime_identity_errors(identity: Any) -> list[str]:
    if not isinstance(identity, dict):
        return ["runtime-identity-missing"]
    errors = [f"runtime-identity-{key}-missing" for key in ("profile", "runner_kind", "os", "architecture") if not identity.get(key)]
    kind = identity.get("runner_kind")
    if kind == "browser-runtime":
        errors.extend(f"runtime-identity-{key}-missing" for key in ("browser", "browser_version") if not identity.get(key))
    if kind == "android-emulator":
        if identity.get("api_level") is None:
            errors.append("runtime-identity-api-level-missing")
        if not identity.get("device_id"):
            errors.append("runtime-identity-device-id-missing")
        if identity.get("physical_device") is None:
            errors.append("runtime-identity-physical-device-flag-missing")
    return errors


def evaluate_dedicated_runtime(
    root: Path,
    *,
    surface_id: str,
    scenario: str,
    baseline_variants: list[str],
    minimum_variants: int,
    source_set_digest: str,
) -> dict[str, Any]:
    """Return a fail-closed closure decision for one Surface + Scenario row."""
    relative = report_path(surface_id, scenario)
    path = root / relative
    result: dict[str, Any] = {
        "report_path": relative,
        "report_binding": None,
        "report_present": path.is_file(),
        "baseline_variants": sorted(set(baseline_variants)),
        "declared_variants": [],
        "minimum_variants": minimum_variants,
        "all_variants_driven": False,
        "retry_zero": False,
        "trace_artifact_per_variant": False,
        "screenshot_artifact_per_variant": False,
        "trace_streams_per_variant": False,
        "oracle_per_variant": False,
        "source_harness_digest_bound": False,
        "runtime_identity_complete": False,
        "closed": False,
        "errors": [],
    }
    if not path.is_file():
        result["errors"] = ["dedicated-runtime-report-missing", "variant-contract-not-declared"]
        return result
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        result["errors"] = ["dedicated-runtime-report-invalid-json"]
        return result

    result["report_binding"] = {"path": relative, "digest": sha256(path), "bytes": path.stat().st_size}
    errors: list[str] = []
    if report.get("schema_version") != 1:
        errors.append("report-schema-version-invalid")
    if report.get("surface_id") != surface_id:
        errors.append("report-surface-mismatch")
    if report.get("scenario") != scenario:
        errors.append("report-scenario-mismatch")
    if report.get("status") != "passed":
        errors.append("report-status-not-passed")
    result["retry_zero"] = report.get("retries") == 0
    if not result["retry_zero"]:
        errors.append("retry-must-be-zero")
    if report.get("source_set_digest") != source_set_digest:
        errors.append("sdk-source-set-digest-mismatch")

    identity_errors = _runtime_identity_errors(report.get("runtime_identity"))
    errors.extend(identity_errors)
    result["runtime_identity_complete"] = not identity_errors

    harness, harness_errors = _binding(root, report.get("harness"))
    errors.extend(f"harness-{item}" for item in harness_errors)
    if harness is not None and harness["path"].startswith("evidence/"):
        errors.append("harness-must-not-reuse-evidence-artifact")
        harness_errors.append("evidence-artifact-reuse")
    reporter, reporter_errors = _binding(root, report.get("reporter"))
    errors.extend(f"reporter-{item}" for item in reporter_errors)
    if reporter is not None and reporter["path"].startswith("evidence/"):
        errors.append("reporter-must-not-reuse-evidence-artifact")
        reporter_errors.append("evidence-artifact-reuse")
    declared = report.get("variant_contract")
    declared_variants = declared if isinstance(declared, list) and all(isinstance(item, str) and item for item in declared) else []
    result["declared_variants"] = sorted(set(declared_variants))
    if len(declared_variants) != len(set(declared_variants)):
        errors.append("variant-contract-contains-duplicates")
    if len(result["declared_variants"]) < minimum_variants:
        errors.append("variant-contract-below-minimum")
    if not set(result["baseline_variants"]).issubset(result["declared_variants"]):
        errors.append("variant-contract-drops-baseline-variant")

    tests = report.get("tests") if isinstance(report.get("tests"), list) else []
    observed_variants = [test.get("variant") for test in tests if isinstance(test, dict)]
    result["all_variants_driven"] = (
        len(observed_variants) == len(set(observed_variants))
        and sorted(observed_variants) == result["declared_variants"]
        and len(result["declared_variants"]) >= minimum_variants
    )
    if not result["all_variants_driven"]:
        errors.append("all-variants-not-driven-exactly-once")

    row_prefix = f"evidence/scenarios/runtime/{surface_id.replace('.', '/')}/{scenario}/"
    trace_paths: list[str] = []
    artifact_paths: list[str] = []
    screenshot_paths: list[str] = []
    trace_artifact_ok = bool(tests)
    screenshot_ok = bool(tests)
    trace_streams_ok = bool(tests)
    oracle_ok = bool(tests)
    source_ok = harness is not None and not harness_errors and reporter is not None and not reporter_errors
    for test in tests:
        if not isinstance(test, dict):
            errors.append("variant-record-invalid")
            trace_artifact_ok = oracle_ok = source_ok = False
            continue
        variant = test.get("variant")
        if test.get("attempts") != 1 or test.get("outcome") != "expected" or test.get("final_status") != "passed" or test.get("error") is not None:
            errors.append(f"variant-first-attempt-pass-required:{variant}")
        oracle = test.get("oracle")
        if not isinstance(oracle, dict) or oracle.get("passed") is not True or not oracle.get("assertions"):
            oracle_ok = False
            errors.append(f"variant-oracle-invalid:{variant}")
        source, source_errors = _binding(root, test.get("source"))
        if source is not None and source["path"].startswith("evidence/"):
            source_errors.append("evidence-artifact-reuse")
        if source is None or source_errors:
            source_ok = False
            errors.extend(f"variant-source-{item}:{variant}" for item in source_errors)
        trace, trace_errors = _binding(root, test.get("trace"), prefix=f"{row_prefix}{variant}/")
        artifact, artifact_errors = _binding(root, test.get("artifact"), prefix=f"{row_prefix}{variant}/")
        screenshot, screenshot_errors = _binding(root, test.get("screenshot"), prefix=f"{row_prefix}{variant}/")
        if trace is None or artifact is None or trace_errors or artifact_errors:
            trace_artifact_ok = False
            errors.extend(f"variant-trace-{item}:{variant}" for item in trace_errors)
            errors.extend(f"variant-artifact-{item}:{variant}" for item in artifact_errors)
        else:
            trace_paths.append(trace["path"])
            artifact_paths.append(artifact["path"])
            if trace["path"] == artifact["path"]:
                trace_artifact_ok = False
                errors.append(f"variant-trace-artifact-must-be-distinct:{variant}")
            try:
                trace_document = json.loads((root / trace["path"]).read_text(encoding="utf-8"))
                streams = trace_document.get("streams", {})
                network = streams.get("network", {})
                network_valid = bool(network.get("events")) or (
                    network.get("applicable") is False and bool(network.get("reason"))
                )
                if not streams.get("action") or not streams.get("resource") or not network_valid:
                    raise ValueError("required stream missing")
            except (OSError, json.JSONDecodeError, AttributeError, ValueError):
                trace_streams_ok = False
                errors.append(f"variant-trace-streams-invalid:{variant}")
        if screenshot is None or screenshot_errors:
            screenshot_ok = False
            errors.extend(f"variant-screenshot-{item}:{variant}" for item in screenshot_errors)
        else:
            screenshot_paths.append(screenshot["path"])
            if not (root / screenshot["path"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                screenshot_ok = False
                errors.append(f"variant-screenshot-not-png:{variant}")

    if len(trace_paths) != len(set(trace_paths)) or len(artifact_paths) != len(set(artifact_paths)):
        trace_artifact_ok = False
        errors.append("variant-artifact-reused")
    if len(screenshot_paths) != len(set(screenshot_paths)):
        screenshot_ok = False
        errors.append("variant-screenshot-reused")
    result["trace_artifact_per_variant"] = trace_artifact_ok and result["all_variants_driven"]
    result["screenshot_artifact_per_variant"] = screenshot_ok and result["all_variants_driven"]
    result["trace_streams_per_variant"] = trace_streams_ok and result["all_variants_driven"]
    result["oracle_per_variant"] = oracle_ok and result["all_variants_driven"]
    result["source_harness_digest_bound"] = source_ok and result["all_variants_driven"]
    result["errors"] = sorted(set(errors))
    result["closed"] = not result["errors"]
    return result
