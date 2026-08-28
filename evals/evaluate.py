#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / "evals" / "cases.json").read_text(encoding="utf-8"))["cases"]
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
        results.append({"id": case["id"], "passed": passed, "actual": actual})
    passed_count = sum(result["passed"] for result in results)
    report = {
        "schema_version": 1,
        "total": len(results),
        "passed": passed_count,
        "pass_rate": passed_count / len(results),
        "results": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
