#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Flutter Atlasを決定論的にRouteします。")
    parser.add_argument("--mode", required=True, choices=["design", "implement", "diagnose", "recover", "migrate", "review"])
    parser.add_argument("--capability", required=True)
    parser.add_argument("--write-authorized", action="store_true")
    parser.add_argument("--publish-authorized", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[4]
    routes = json.loads((root / "evals" / "routes.json").read_text(encoding="utf-8"))
    query = args.capability.lower()
    selected = None
    for route in routes["routes"]:
        if any(keyword in query for keyword in route["keywords"]):
            selected = route
            break

    if selected is None:
        result = {
            "mode": args.mode,
            "coverage_gap": True,
            "message": "Coverageに一致するCapabilityがありません。存在する機能として扱いません。",
            "write_allowed": False,
            "publish_allowed": False,
            "write_authorized": bool(args.write_authorized),
            "publish_authorized": bool(args.publish_authorized),
        }
    else:
        result = {
            "mode": args.mode,
            "coverage_gap": selected["state"] != "covered",
            "capability_id": selected["capability_id"],
            "target_id": selected["target_id"],
            "state": selected["state"],
            "authority_ids": selected["authority_ids"],
            "lab_id": selected.get("lab_id"),
            "commands": selected.get("commands", []),
            "write_allowed": bool(args.write_authorized),
            "publish_allowed": False,
            "write_authorized": bool(args.write_authorized),
            "publish_authorized": bool(args.publish_authorized),
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
