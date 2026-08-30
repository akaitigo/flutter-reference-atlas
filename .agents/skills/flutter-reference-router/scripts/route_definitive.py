#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Definitive Surface InventoryとGap Ledgerへ決定論的にRouteする。"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).lower()


def tokens(value: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9ぁ-んァ-ヶ一-龠]+", normalize(value))
        if len(token) >= 3
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    inventory = json.loads(
        (root / "atlas/definitive/surface-inventory.json").read_text(encoding="utf-8")
    )
    ledger = json.loads(
        (root / "atlas/definitive/gap-ledger.json").read_text(encoding="utf-8")
    )
    entries = {entry["surface_id"]: entry for entry in ledger["entries"]}
    query = normalize(args.query)
    query_tokens = tokens(query)
    ranked = []
    for surface in inventory["surfaces"]:
        corpus = " ".join(
            [
                surface["id"],
                surface["title"],
                surface["domain"],
                surface["capability"],
                *surface["required_runtime_profiles"],
            ]
        )
        corpus_normalized = normalize(corpus)
        matched = sorted(token for token in query_tokens if token in corpus_normalized)
        exact_id = surface["id"] in query
        score = len(matched) + (10 if exact_id else 0)
        if score >= 2 or exact_id:
            ranked.append((score, len(surface["id"]), surface["id"], matched, surface))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    if not ranked:
        print(
            json.dumps(
                {
                    "coverage_gap": True,
                    "message": "Definitive Surface Inventoryに一致しません。存在するCapabilityとして扱いません。",
                    "surface_id": None,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    _, _, _, matched, surface = ranked[0]
    entry = entries[surface["id"]]
    print(
        json.dumps(
            {
                "surface_id": surface["id"],
                "domain": surface["domain"],
                "state": entry["state"],
                "coverage_gap": entry["state"] != "closed",
                "matched_tokens": matched,
                "authority_ids": surface["authority_ids"],
                "required_runtime_profiles": surface["required_runtime_profiles"],
                "gaps": entry["gaps"],
                "observed_evidence_ids": sorted(
                    {item["evidence_id"] for item in entry["observations"]}
                ),
                "completion_claim_allowed": entry["state"] == "closed",
                "non_substitution": ledger["completion_semantics"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
