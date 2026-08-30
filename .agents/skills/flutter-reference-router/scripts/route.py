#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import re
import unicodedata
from pathlib import Path


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).lower()


def keyword_matches(query: str, keyword: str) -> bool:
    keyword = normalize(keyword)
    if keyword == "同期":
        query = query.replace("非同期", "")
    if re.fullmatch(r"[a-z0-9_.+ -]+", keyword):
        return re.search(rf"(?<![a-z0-9_]){re.escape(keyword)}(?![a-z0-9_])", query) is not None
    return keyword in query


def qualifier_gaps(query: str, matches: list[dict[str, object]], policy: dict[str, object]) -> list[str]:
    gaps: list[str] = []
    flutter_versions = re.findall(r"flutter(?:\s+sdk)?(?:\s+version)?\s+(\d+\.\d+(?:\.\d+)?)", query)
    supported_versions = set(policy.get("baseline_versions", []))
    for version in flutter_versions:
        if version not in supported_versions:
            gaps.append(f"Flutter {version}は固定Baseline外です。")

    for qualifier in policy.get("uncovered_qualifiers", []):
        if keyword_matches(query, str(qualifier)):
            gaps.append(f"{qualifier}固有のCoverageとRuntime Evidenceは収録されていません。")

    publication_query = query.replace("release build", "")
    publication_requested = any(keyword_matches(publication_query, str(term)) for term in policy.get("publication_terms", []))
    publication_requested = publication_requested or re.search(r"\brelease\b", publication_query) is not None
    publication_requested = publication_requested or "リリース" in query
    if publication_requested:
        gaps.append("公開、配信、Store送信はPublication Coverage外です。")

    capabilities = {str(match["capability_id"]) for match in matches}
    runtime_requested = any(keyword_matches(query, str(term)) for term in policy.get("runtime_terms", []))
    source_contracts = set(policy.get("source_contract_capabilities", []))
    if runtime_requested and capabilities & source_contracts:
        gaps.append("Source Contractは実機Runtime Evidenceの代替ではありません。")
    if any(keyword_matches(query, str(term)) for term in policy.get("external_environment_terms", [])):
        gaps.append("外部Production・Staging・Hosting EnvironmentはCoverage Profile外です。")
    if any(keyword_matches(query, str(term)) for term in policy.get("hardware_runtime_terms", [])):
        gaps.append("実機・hardware-in-the-loop Runtime Evidenceは収録されていません。")
    generic_simulator_requested = any(
        keyword_matches(query, str(term)) for term in policy.get("generic_simulator_terms", [])
    )
    runner_qualified = any(
        keyword_matches(query, str(term))
        for term in policy.get("qualified_simulator_terms", [])
    )
    if generic_simulator_requested and not runner_qualified:
        gaps.append("Runner未指定のSimulator Evidenceはcoveredとして扱いません。")

    if "platform.ffi" in capabilities:
        requested_platforms = {name for name in ("windows", "linux", "android", "ios", "macos") if keyword_matches(query, name)}
        supported = set(policy.get("ffi_runtime_platforms", []))
        unsupported = sorted(requested_platforms - supported)
        if unsupported:
            gaps.append(f"FFI Runtime EvidenceがないPlatformです: {', '.join(unsupported)}")
    if "execution.container-lab" in capabilities and capabilities & {"quality.failure-recovery", "operations.runbooks"}:
        gaps.append("Container Profileと復旧・運用Labを結合したEvidenceは収録されていません。")
    if "product.state-lifecycle" in capabilities and any(term in query for term in ("migration", "移行")):
        gaps.append("状態管理Packageまたは方式間MigrationのEvidenceは収録されていません。")
    if "platform.channel-plugin" in capabilities and "plugin" in query:
        generic_contract = any(term in query for term in ("methodchannel", "platform channel", "plugin registration"))
        if not generic_contract:
            gaps.append("特定Pluginの実装・Runtime Evidenceは収録されていません。")
    return list(dict.fromkeys(gaps))


def main() -> int:
    parser = argparse.ArgumentParser(description="Flutter Atlasを決定論的にRouteします。")
    parser.add_argument("--mode", required=True, choices=["design", "implement", "diagnose", "recover", "migrate", "review"])
    parser.add_argument("--capability", required=True)
    parser.add_argument("--write-authorized", action="store_true")
    parser.add_argument("--publish-authorized", action="store_true")
    parser.add_argument("--mutation-requested", action="store_true")
    parser.add_argument("--authority-semantic-decision", action="store_true")
    parser.add_argument("--stale-source-relock", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[4]
    routes = json.loads((root / "evals" / "routes.json").read_text(encoding="utf-8"))
    query = normalize(args.capability)
    ranked = []
    for index, route in enumerate(routes["routes"]):
        matched_keywords = [keyword for keyword in route["keywords"] if keyword_matches(query, keyword)]
        if matched_keywords:
            specificity = max(len(normalize(keyword).replace(" ", "")) for keyword in matched_keywords)
            safety = 1 if route["state"] != "covered" else 0
            priority = int(route.get("priority", 0))
            if route["capability_id"] == "baseline.sdk-lock" and any(
                keyword in {"sdk migration", "flutter sdk version", "flutter version", "3.47.1", "sdk移行", "sdkバージョン"}
                for keyword in matched_keywords
            ):
                priority = 40
            ranked.append((safety, priority, specificity, -index, route, matched_keywords))
    ranked.sort(reverse=True, key=lambda item: (item[0], item[1], item[2], item[3]))
    matches = [item[4] for item in ranked]
    ambiguous_capabilities = []
    if ranked:
        top_rank = ranked[0][:3]
        ambiguous_capabilities = sorted({
            str(item[4]["capability_id"])
            for item in ranked
            if item[:3] == top_rank
        })
    composable_capability_sets = {
        frozenset({"platform.desktop", "platform.ffi"}),
    }
    ambiguous = len(ambiguous_capabilities) > 1 and frozenset(ambiguous_capabilities) not in composable_capability_sets
    selected = matches[0] if matches and not ambiguous else None
    gaps = qualifier_gaps(query, matches, routes.get("policy", {}))
    gaps.extend(
        f"{match['capability_id']}のCoverage stateは{match['state']}です。"
        for match in matches
        if match["state"] != "covered"
    )
    gaps = list(dict.fromkeys(gaps))

    if ambiguous:
        result = {
            "status": "coverage-gap",
            "mode": args.mode,
            "coverage_gap": True,
            "message": "複数Capabilityが同順位です。対象Surfaceまたは制約を追加するまで実行しません。",
            "write_allowed": False,
            "publish_allowed": False,
            "write_authorized": bool(args.write_authorized),
            "publish_authorized": bool(args.publish_authorized),
            "gap_reasons": ["曖昧なQueryを単一Capabilityとして扱いません。"],
            "matched_capabilities": ambiguous_capabilities,
        }
    elif selected is None:
        result = {
            "status": "coverage-gap",
            "mode": args.mode,
            "coverage_gap": True,
            "message": "Coverageに一致するCapabilityがありません。存在する機能として扱いません。",
            "write_allowed": False,
            "publish_allowed": False,
            "write_authorized": bool(args.write_authorized),
            "publish_authorized": bool(args.publish_authorized),
            "gap_reasons": ["Coverageに一致するCapabilityがありません。"],
            "matched_capabilities": [],
        }
    else:
        commands = list(dict.fromkeys(command for match in matches for command in match.get("commands", [])))
        result = {
            "status": "coverage-gap" if gaps else "routed",
            "mode": args.mode,
            "coverage_gap": bool(gaps),
            "capability_id": selected["capability_id"],
            "target_id": selected["target_id"],
            "state": selected["state"],
            "authority_ids": selected["authority_ids"],
            "lab_id": selected.get("lab_id"),
            "commands": commands,
            "gap_reasons": gaps,
            "matched_capabilities": [match["capability_id"] for match in matches],
            "write_allowed": bool(
                args.write_authorized
                and args.mode in {"implement", "recover", "migrate"}
                and not gaps
            ),
            "publish_allowed": False,
            "write_authorized": bool(args.write_authorized),
            "publish_authorized": bool(args.publish_authorized),
        }
    mutation_requested = args.mutation_requested or args.mode in {"implement", "recover", "migrate"}
    blocked_reasons = []
    if mutation_requested and not args.write_authorized:
        blocked_reasons.append("unauthorized-mutation")
    if args.authority_semantic_decision:
        blocked_reasons.append("external-human-authority-decision-required")
    if args.stale_source_relock:
        blocked_reasons.append("stale-source-relock-explicit-procedure-required")
    if blocked_reasons:
        result["status"] = "blocked"
        result["write_allowed"] = False
    result["blocked_reasons"] = blocked_reasons
    result["mutation_policy"] = "explicit-authorization-required" if mutation_requested else "read-only"
    result["mutation_status"] = "blocked" if blocked_reasons else "authorized-for-request-scope" if mutation_requested else "read-only"
    result["stop_conditions"] = [
        "coverage-gap",
        "unauthorized-mutation",
        "external-human-authority-decision-required",
        "stale-source-relock-explicit-procedure-required",
        "ambiguous-or-unknown-query",
    ]
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
