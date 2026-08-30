#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import subprocess
import sys
from pathlib import Path


# 公開済みv1評価Artifactのshapeは非後退baselineである。Routerが追加の
# fail-closed診断を返しても、この既存Artifactには新Fieldを混入させない。
BASELINE_ACTUAL_FIELDS = (
    "authority_ids",
    "capability_id",
    "commands",
    "coverage_gap",
    "gap_reasons",
    "lab_id",
    "matched_capabilities",
    "message",
    "mode",
    "publish_allowed",
    "publish_authorized",
    "state",
    "target_id",
    "write_allowed",
    "write_authorized",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Flutter Router Skillを評価します。")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skill-eval-output", type=Path)
    parser.add_argument("--generated-at", default="2026-08-28T07:10:00Z")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cases = []
    for name in ("cases.json", "forward_cases.json"):
        cases.extend(json.loads((root / "evals" / name).read_text(encoding="utf-8"))["cases"])
    router = root / ".agents" / "skills" / "flutter-reference-router" / "scripts" / "route.py"
    results = []
    for case in cases:
        command = [sys.executable, str(router), "--mode", case["mode"], "--capability", case["capability"]]
        if case["write"]:
            command.append("--write-authorized")
        if case["publish"]:
            command.append("--publish-authorized")
        actual = json.loads(subprocess.check_output(command, text=True))
        passed = (
            actual.get("capability_id") == case["expected_capability"]
            and actual["coverage_gap"] == case["expect_gap"]
            and actual["write_allowed"] == case.get("expect_write", case["write"])
            and actual["publish_allowed"] == case.get("expect_publish", case["publish"])
            and actual["write_authorized"] == case["write"]
            and actual["publish_authorized"] == case["publish"]
        )
        baseline_actual = {key: actual[key] for key in BASELINE_ACTUAL_FIELDS if key in actual}
        results.append({"id": case["id"], "passed": passed, "actual": baseline_actual})
    passed_count = sum(result["passed"] for result in results)
    report = {
        "schema_version": 1,
        "total": len(results),
        "passed": passed_count,
        "pass_rate": passed_count / len(results),
        "results": results,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.skill_eval_output:
        categories = {
            "routing": ["route-design-ui", "route-navigation", "route-platform-channel"],
            "near-neighbor": ["reject-nearby-tech", "avoid-async-sync-substring", "app-version-is-not-sdk"],
            "coverage-gap": ["reject-uncovered-package", "reject-windows-ffi-runtime", "reject-new-flutter-version"],
            "lifecycle": ["route-implement-state", "route-failure", "fwd-12-bloc-migration"],
            "authority": ["route-public-surface", "route-migrate-sdk", "route-review-container"],
            "execution": ["route-local", "route-android-emulator-covered", "route-diagnose-simulator", "fwd-09-matrix-surface"],
            "authorization": ["publication-boundary", "reject-hardware-in-the-loop", "fwd-19-infeasible-write-gate", "fwd-20-design-publish-gate"],
            "security": ["route-security", "fwd-05-firebase-plugin", "fwd-18-review-write-gate"],
        }
        by_id = {result["id"]: result for result in results}
        summary_cases = []
        for category, ids in categories.items():
            category_passed = all(by_id[id]["passed"] for id in ids)
            summary_cases.append(
                {
                    "id": f"router.{category}",
                    "category": category,
                    "result": "pass" if category_passed else "fail",
                    "assertion": f"代表Case {', '.join(ids)} が期待するRoute、Gap、権限境界へ一致する。",
                    "evidence_ids": ["skill.router-eval.2026-08-28"],
                }
            )
        skill_eval = {
            "schema_version": 1,
            "id": "flutter.router.skill-eval.2026-08-28",
            "atlas_id": "flutter-reference-atlas",
            "atlas_release": "v1.0.0",
            "skill_id": "flutter-reference-router",
            "generated_at": args.generated_at,
            "cases": summary_cases,
        }
        args.skill_eval_output.parent.mkdir(parents=True, exist_ok=True)
        args.skill_eval_output.write_text(
            json.dumps(skill_eval, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
