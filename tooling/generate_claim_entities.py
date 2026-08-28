#!/usr/bin/env python3
"""Canonical claim indexからCore v1 Claim実体を決定論的に生成する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def render(claim: dict[str, object], atlas_id: str) -> str:
    acceptance = str(claim["acceptance"])
    entity = {
        "schema_version": 1,
        "id": claim["id"],
        "atlas_id": atlas_id,
        "capability_id": claim["capability_id"],
        "statement": f"Flutter技術実証として次の観測可能な主張を固定する。{acceptance}",
        "status": "accepted",
        "source_ids": claim["authority_ids"],
        "proof_obligations": [
            {
                "id": claim["proof_obligation_id"],
                "statement": f"Lab {claim['lab_id']} とTest {claim['test_id']}で主張を反証可能に検査する。",
                "acceptance_criteria": [acceptance],
            }
        ],
    }
    return json.dumps(entity, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source = json.loads((root / "atlas/claims/index.json").read_text(encoding="utf-8"))
    output_dir = root / "claims"
    expected: dict[Path, str] = {}
    for claim in source["claims"]:
        path = output_dir / f"{claim['id']}.claim.json"
        expected[path] = render(claim, source["atlas_id"])

    stale = set(output_dir.glob("*.claim.json")) - set(expected) if output_dir.exists() else set()
    mismatches = [path for path, content in expected.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
    if args.check:
        if stale or mismatches:
            for path in sorted(stale | set(mismatches)):
                print(f"Claim実体が正本と一致しません: {path.relative_to(root)}")
            return 1
        print(f"Claim実体検証済み: {len(expected)}件")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    for path in stale:
        path.unlink()
    for path, content in expected.items():
        path.write_text(content, encoding="utf-8")
    print(f"Claim実体生成済み: {len(expected)}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
