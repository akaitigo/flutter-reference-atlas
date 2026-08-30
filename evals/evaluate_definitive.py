#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/artifacts/definitive-router-eval-report.json"),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / "evals/definitive_cases.json").read_text(encoding="utf-8"))["cases"]
    router = root / ".agents/skills/flutter-reference-router/scripts/route_definitive.py"
    results = []
    for case in cases:
        actual = json.loads(
            subprocess.check_output(
                [sys.executable, str(router), "--query", case["query"]], text=True
            )
        )
        gaps = actual.get("gaps", [])
        expected_gap = case["expected_gap_kind"] is None or any(
            gap == {"kind": case["expected_gap_kind"], "id": case["expected_gap_id"]}
            for gap in gaps
        )
        passed = (
            actual.get("surface_id") == case["expected_surface"]
            and actual.get("coverage_gap") is True
            and actual.get("completion_claim_allowed", False) is False
            and expected_gap
        )
        results.append({"id": case["id"], "passed": passed, "actual": actual})
    passed_count = sum(item["passed"] for item in results)
    report = {
        "schema_version": 2,
        "atlas_id": "flutter-reference-atlas",
        "skill_id": "flutter-reference-router",
        "surface_inventory": "atlas/definitive/surface-inventory.json",
        "gap_ledger": "atlas/definitive/gap-ledger.json",
        "total": len(results),
        "passed": passed_count,
        "pass_rate": passed_count / len(results),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Definitive Router Eval: {passed_count}/{len(results)}")
    return 0 if passed_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
