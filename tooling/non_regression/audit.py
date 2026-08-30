#!/usr/bin/env python3
"""Public-main non-regression baseline generator and auditor.

The snapshot is generated from an immutable Git commit, never from the working
tree.  The audit permits additions, but rejects weakening or removal of the
published contract.  Intentional replacement must be declared separately and
carry both migration evidence and an equal-or-stronger proof reference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # GitHub runnerで追加pip installを要求しないGo fallback
    yaml = None


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT = ROOT / "baseline" / "public-main-non-regression-v1.json"
DEFAULT_MAPPINGS = ROOT / "migrations" / "non-regression-mappings.json"


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


class GitReader:
    def __init__(self, root: Path, ref: str):
        self.root = root
        self.ref = ref
        self.commit = self._run("rev-parse", f"{ref}^{{commit}}").strip()

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.root, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return result.stdout

    def bytes(self, path: str) -> bytes:
        result = subprocess.run(
            ["git", "show", f"{self.commit}:{path}"], cwd=self.root,
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return result.stdout

    def text(self, path: str) -> str:
        return self.bytes(path).decode("utf-8")

    def paths(self, prefix: str = "") -> list[str]:
        args = ["ls-tree", "-r", "--name-only", self.commit]
        if prefix:
            args.extend(["--", prefix])
        return [line for line in self._run(*args).splitlines() if line]


class WorktreeReader:
    def __init__(self, root: Path):
        self.root = root

    def bytes(self, path: str) -> bytes:
        return (self.root / path).read_bytes()

    def text(self, path: str) -> str:
        return (self.root / path).read_text(encoding="utf-8")

    def paths(self, prefix: str = "") -> list[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        if base.is_file():
            return [prefix]
        return sorted(str(path.relative_to(self.root)) for path in base.rglob("*") if path.is_file())


def load_structured(reader: GitReader | WorktreeReader, path: str) -> Any:
    text = reader.text(path)
    if path.endswith(".json"):
        return json.loads(text)
    if yaml is not None:
        return yaml.safe_load(text)
    go_environment = os.environ.copy()
    go_environment["GOCACHE"] = str(ROOT / ".tools" / "go-build")
    result = subprocess.run(
        ["go", "run", "./tooling/non_regression/yaml_to_json"],
        cwd=ROOT, input=text, text=True, check=True,
        env=go_environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return json.loads(result.stdout)


def by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items}


def normalize_ci(document: dict[str, Any]) -> dict[str, Any]:
    jobs: dict[str, Any] = {}
    for job_id, job in document.get("jobs", {}).items():
        steps = []
        for step in job.get("steps", []):
            steps.append({key: step[key] for key in ("name", "uses", "run", "with") if key in step})
        jobs[job_id] = {
            "runs-on": job.get("runs-on"),
            "strategy": job.get("strategy"),
            "steps": steps,
        }
    return jobs


TEST_PATTERNS = (
    re.compile(r"\btestWidgets\s*\(\s*['\"]([^'\"]+)"),
    re.compile(r"\btest\s*\(\s*['\"]([^'\"]+)"),
    re.compile(r"^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(", re.MULTILINE),
    re.compile(r"^\s*func\s+(Test[A-Za-z0-9_]+)\s*\(", re.MULTILINE),
)
ASSERTION_PATTERNS = (
    re.compile(r"\bexpect(?:Later)?\s*\("),
    re.compile(r"\bassert\s+"),
    re.compile(r"\bt\.(?:Fatalf?|Errorf?|FailNow|Fail)\s*\("),
    re.compile(r"\brequire\s*\("),
)


def test_metric(text: str) -> dict[str, Any] | None:
    names: list[str] = []
    for pattern in TEST_PATTERNS:
        names.extend(pattern.findall(text))
    assertion_count = sum(len(pattern.findall(text)) for pattern in ASSERTION_PATTERNS)
    if not names and assertion_count == 0:
        return None
    return {
        "test_names": sorted(set(names)),
        "test_declaration_count": len(names),
        "assertion_count": assertion_count,
    }


def collect_test_metrics(reader: GitReader | WorktreeReader) -> dict[str, Any]:
    roots = ("labs", "reference-systems", "tooling", "evals", "scripts")
    extensions = (".dart", ".py", ".go", ".sh")
    metrics: dict[str, Any] = {}
    for root in roots:
        for path in reader.paths(root):
            if not path.endswith(extensions):
                continue
            metric = test_metric(reader.text(path))
            if metric:
                metrics[path] = metric
    return metrics


def collect_evidence(reader: GitReader | WorktreeReader) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence: dict[str, Any] = {}
    artifacts: dict[str, Any] = {}
    for path in reader.paths("evidence"):
        if not path.endswith(".evidence.yaml"):
            continue
        record = load_structured(reader, path)
        record_id = record["id"]
        evidence[record_id] = {"path": path, "record": record}
        artifact = record.get("artifact")
        if artifact:
            artifact_path = artifact["uri"]
            content = reader.bytes(artifact_path)
            artifacts[artifact_path] = {
                "digest": sha256_bytes(content),
                "size_bytes": len(content),
                "evidence_id": record_id,
            }
    return evidence, artifacts


def build_snapshot(reader: GitReader) -> dict[str, Any]:
    coverage = load_structured(reader, "coverage.yaml")
    labs = load_structured(reader, "labs/index.json")
    claims = load_structured(reader, "atlas/claims/index.json")
    proofs = load_structured(reader, "atlas/proof-obligations/index.json")
    capabilities = load_structured(reader, "atlas/capabilities/index.json")
    sources = load_structured(reader, "sources.lock.yaml")
    skill_cases = load_structured(reader, "evals/cases.json")
    forward_cases = load_structured(reader, "evals/forward_cases.json")
    skill_eval = load_structured(reader, "evals/flutter-router.skill-eval.json")
    atlas = load_structured(reader, "atlas.yaml")
    evidence, artifacts = collect_evidence(reader)
    return {
        "schema_version": 1,
        "policy": "public-main-non-regression-v1",
        "baseline_commit": reader.commit,
        "baseline_tree": reader._run("rev-parse", f"{reader.commit}^{{tree}}").strip(),
        "atlas_id": atlas["id"],
        "version_and_scope_floor": {
            "coverage_epoch": atlas["coverage"]["epoch"],
            "scope_statement": atlas["scope"]["statement"],
            "required_profiles": atlas["completion"]["required_profiles"],
            "sdk_baseline": load_structured(reader, "baseline/flutter-3.47.1.yaml"),
        },
        "target_sets": by_id(coverage["target_sets"]),
        "targets": by_id(coverage["targets"]),
        "labs": by_id(labs["labs"]),
        "tests": by_id(labs["tests"]),
        "capabilities": by_id(capabilities["capabilities"]),
        "claims": by_id(claims["claims"]),
        "proof_obligations": by_id(proofs["proof_obligations"]),
        "evidence": evidence,
        "artifacts": artifacts,
        "sources": by_id(sources["sources"]),
        "skill_cases": by_id(skill_cases["cases"]),
        "skill_forward_cases": by_id(forward_cases["cases"]),
        "skill_eval_cases": by_id(skill_eval["cases"]),
        "ci_jobs": normalize_ci(load_structured(reader, ".github/workflows/ci.yml")),
        "test_metrics": collect_test_metrics(reader),
    }


def load_current(root: Path) -> dict[str, Any]:
    reader = WorktreeReader(root)
    coverage = load_structured(reader, "coverage.yaml")
    labs = load_structured(reader, "labs/index.json")
    claims = load_structured(reader, "atlas/claims/index.json")
    proofs = load_structured(reader, "atlas/proof-obligations/index.json")
    capabilities = load_structured(reader, "atlas/capabilities/index.json")
    sources = load_structured(reader, "sources.lock.yaml")
    skill_cases = load_structured(reader, "evals/cases.json")
    forward_cases = load_structured(reader, "evals/forward_cases.json")
    skill_eval = load_structured(reader, "evals/flutter-router.skill-eval.json")
    atlas = load_structured(reader, "atlas.yaml")
    evidence, artifacts = collect_evidence(reader)
    return {
        "atlas_id": atlas["id"],
        "version_and_scope_floor": {
            "coverage_epoch": atlas["coverage"]["epoch"],
            "scope_statement": atlas["scope"]["statement"],
            "required_profiles": atlas["completion"]["required_profiles"],
            "sdk_baseline": load_structured(reader, "baseline/flutter-3.47.1.yaml"),
        },
        "target_sets": by_id(coverage["target_sets"]),
        "targets": by_id(coverage["targets"]),
        "labs": by_id(labs["labs"]),
        "tests": by_id(labs["tests"]),
        "capabilities": by_id(capabilities["capabilities"]),
        "claims": by_id(claims["claims"]),
        "proof_obligations": by_id(proofs["proof_obligations"]),
        "evidence": evidence,
        "artifacts": artifacts,
        "sources": by_id(sources["sources"]),
        "skill_cases": by_id(skill_cases["cases"]),
        "skill_forward_cases": by_id(forward_cases["cases"]),
        "skill_eval_cases": by_id(skill_eval["cases"]),
        "ci_jobs": normalize_ci(load_structured(reader, ".github/workflows/ci.yml")),
        "test_metrics": collect_test_metrics(reader),
    }


def mapping_for(mappings: list[dict[str, Any]], entity_type: str, old_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in mappings if item.get("entity_type") == entity_type and item.get("old_id") == old_id),
        None,
    )


def replacement_is_valid(mapping: dict[str, Any] | None, current: dict[str, Any]) -> bool:
    if not mapping:
        return False
    required = ("new_ids", "rationale", "migration_evidence_ids", "equivalent_or_stronger_proof_ids")
    if any(not mapping.get(key) for key in required):
        return False
    return (
        all(item in current.get(mapping["entity_type"], {}) for item in mapping["new_ids"])
        and all(item in current["evidence"] for item in mapping["migration_evidence_ids"])
        and all(item in current["proof_obligations"] for item in mapping["equivalent_or_stronger_proof_ids"])
    )


def compare_exact_entity_map(
    name: str, baseline: dict[str, Any], current: dict[str, Any],
    current_document: dict[str, Any], mappings: list[dict[str, Any]], errors: list[str],
) -> None:
    for entity_id, expected in baseline.items():
        actual = current.get(entity_id)
        if actual is None:
            mapping = mapping_for(mappings, name, entity_id)
            if not replacement_is_valid(mapping, current_document):
                errors.append(f"{name}:{entity_id}: baseline ID missing without valid migration mapping")
            continue
        if actual != expected:
            errors.append(f"{name}:{entity_id}: published contract changed")


def audit(snapshot: dict[str, Any], current: dict[str, Any], mappings_doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    mappings = mappings_doc.get("mappings", [])
    if current["atlas_id"] != snapshot["atlas_id"]:
        errors.append("atlas_id changed")

    floor = snapshot["version_and_scope_floor"]
    actual_floor = current["version_and_scope_floor"]
    for key in ("coverage_epoch", "scope_statement", "sdk_baseline"):
        if actual_floor[key] != floor[key]:
            errors.append(f"version_and_scope_floor:{key}: published value changed")
    if not set(floor["required_profiles"]).issubset(actual_floor["required_profiles"]):
        errors.append("version_and_scope_floor:required_profiles: published profile removed")

    compare_exact_entity_map("target_sets", snapshot["target_sets"], current["target_sets"], current, mappings, errors)

    for target_id, expected in snapshot["targets"].items():
        actual = current["targets"].get(target_id)
        if actual is None:
            mapping = mapping_for(mappings, "targets", target_id)
            if not replacement_is_valid(mapping, current):
                errors.append(f"targets:{target_id}: baseline ID missing without valid migration mapping")
            continue
        for key in ("target_set", "kind", "requirement"):
            if actual.get(key) != expected.get(key):
                errors.append(f"targets:{target_id}:{key}: published value changed")
        if expected.get("state") == "covered" and actual.get("state") != "covered":
            errors.append(f"targets:{target_id}: covered state was weakened to {actual.get('state')}")
        if expected.get("state") == "infeasible" and actual.get("state") not in ("infeasible", "covered"):
            errors.append(f"targets:{target_id}: infeasible state was hidden or weakened")
        for key in ("claim_ids", "evidence_ids"):
            if not set(expected.get(key, [])).issubset(actual.get(key, [])):
                errors.append(f"targets:{target_id}:{key}: published connection removed")

    for name in (
        "labs", "tests", "capabilities", "claims", "proof_obligations", "evidence",
        "artifacts", "sources", "skill_cases", "skill_forward_cases", "skill_eval_cases",
    ):
        compare_exact_entity_map(name, snapshot[name], current[name], current, mappings, errors)

    for job_id, expected in snapshot["ci_jobs"].items():
        actual = current["ci_jobs"].get(job_id)
        if actual is None:
            errors.append(f"ci_jobs:{job_id}: published job removed")
            continue
        if actual.get("runs-on") != expected.get("runs-on") or actual.get("strategy") != expected.get("strategy"):
            errors.append(f"ci_jobs:{job_id}: runner or matrix changed")
        actual_steps = actual.get("steps", [])
        position = 0
        for step in expected.get("steps", []):
            try:
                position = actual_steps.index(step, position) + 1
            except ValueError:
                errors.append(f"ci_jobs:{job_id}: published step removed, changed, or reordered: {step}")

    for path, expected in snapshot["test_metrics"].items():
        actual = current["test_metrics"].get(path)
        if actual is None:
            errors.append(f"test_metrics:{path}: test/assertion-bearing file removed")
            continue
        if actual["test_declaration_count"] < expected["test_declaration_count"]:
            errors.append(f"test_metrics:{path}: test declaration count decreased")
        if actual["assertion_count"] < expected["assertion_count"]:
            errors.append(f"test_metrics:{path}: assertion count decreased")
        if not set(expected["test_names"]).issubset(actual["test_names"]):
            errors.append(f"test_metrics:{path}: published test name removed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-ref", default="origin/main")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--mappings", type=Path, default=DEFAULT_MAPPINGS)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check-snapshot", action="store_true")
    args = parser.parse_args()

    if args.write:
        snapshot = build_snapshot(GitReader(ROOT, args.baseline_ref))
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.snapshot.relative_to(ROOT)} from {snapshot['baseline_commit']}")
        return 0

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    if args.check_snapshot:
        regenerated = build_snapshot(GitReader(ROOT, snapshot["baseline_commit"]))
        if regenerated != snapshot:
            print("NON-REGRESSION FAIL: baseline snapshot does not match its immutable commit", file=sys.stderr)
            return 1
    mappings = json.loads(args.mappings.read_text(encoding="utf-8"))
    current = load_current(ROOT)
    errors = audit(snapshot, current, mappings)
    if errors:
        print(f"NON-REGRESSION FAIL ({len(errors)} violation(s))", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        "NON-REGRESSION PASS "
        f"baseline={snapshot['baseline_commit']} "
        f"targets={len(snapshot['targets'])} claims={len(snapshot['claims'])} "
        f"proofs={len(snapshot['proof_obligations'])} evidence={len(snapshot['evidence'])} "
        f"sources={len(snapshot['sources'])} skill_cases="
        f"{len(snapshot['skill_cases']) + len(snapshot['skill_forward_cases'])} "
        f"ci_jobs={len(snapshot['ci_jobs'])} test_files={len(snapshot['test_metrics'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
