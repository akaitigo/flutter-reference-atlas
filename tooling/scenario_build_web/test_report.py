# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tooling.scenario_build_web import report


class BuildWebSecurityReporterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]

    def inputs(self, raw: Path, fixture_root: Path | None = None) -> list[str]:
        log_root = fixture_root or self.root
        values = []
        modes = {
            "javascript": "debug-javascript-with-source-maps",
            "release-js": "release-javascript-csp-no-source-maps",
            "wasm": "release-wasm-no-source-maps",
        }
        for variant in report.VARIANTS:
            row = raw / variant
            row.mkdir(parents=True)
            artifact = (b"\x00asm" if variant == "wasm" else b"function main(){}") + b"x" * 100_000
            (row / "artifact.bin").write_bytes(artifact)
            (row / "index.html").write_text('<script src="flutter_bootstrap.js"></script>')
            (row / "observation.json").write_text('{"flutterView":true,"origin":"http://127.0.0.1:49152"}')
            (row / "platform-tree.json").write_text('{"accessibility":{"nodes":[{"role":"RootWebArea"}]},"dom_semantics":[]}')
            (row / "screen.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"p" * 1_000)
            (row / "build.log").write_text(f"build passed: {log_root}/tooling/input.dart   \n")
            (row / "chrome.log").write_text(f"chrome passed: {Path.home()}/Library/profile\n")
            (row / "mode.txt").write_text(modes[variant] + "\n")
            for kind, name in (("artifact", "artifact.bin"), ("index", "index.html"), ("observation", "observation.json"), ("tree", "platform-tree.json"), ("screen", "screen.png"), ("buildlog", "build.log"), ("chromelog", "chrome.log"), ("mode", "mode.txt")):
                values.append(f"{variant}={kind}={row / name}")
        return values

    def fixture(self, temp: Path) -> tuple[argparse.Namespace, Path]:
        fixture_root = temp / "repo"
        sdk_root = temp / "sdk"
        harness = fixture_root / "scripts/scenario-build-web-security-runtime.sh"
        source = fixture_root / "tooling/scenario_build_web/build_security_main.dart"
        reporter = fixture_root / "tooling/scenario_build_web/report.py"
        for path, contents in (
            (harness, "#!/bin/sh\n"),
            (source, "void main() {}\n"),
            (reporter, "# isolated reporter fixture\n"),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        source_bindings = []
        for relative, contents in (
            ("packages/flutter_tools/lib/src/commands/build_web.dart", b"isolated build web fixture\n"),
            ("packages/flutter_tools/lib/src/web/compile.dart", b"isolated web compiler fixture\n"),
        ):
            path = sdk_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
            source_bindings.append({"path": relative, "digest": report.digest(path)})
        proof = fixture_root / "evidence/scenarios/surfaces/build/web/security.proof.json"
        proof.parent.mkdir(parents=True, exist_ok=True)
        proof.write_text(json.dumps({"source_bindings": source_bindings}))
        args = argparse.Namespace(
            repo_root=fixture_root,
            output=temp / "runtime",
            sdk_root=sdk_root,
            harness=harness,
            source=source,
            started_at="2026-08-31T00:00:00Z",
            completed_at="2026-08-31T00:01:00Z",
            runtime_identity={"profile": "web-chrome", "runner_kind": "browser-runtime", "os": "macOS 26.0", "architecture": "arm64", "browser": "Google Chrome", "browser_version": "151", "physical_device": False},
            input=self.inputs(temp / "raw", fixture_root),
        )
        return args, reporter

    def test_publishes_all_web_build_variants(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root / ".tools") as temporary:
            temp = Path(temporary)
            args, reporter = self.fixture(temp)
            with mock.patch.object(report, "__file__", str(reporter)):
                report.publish(args)
            self.assertTrue((temp / "runtime/build/web/security/results.json").is_file())
            self.assertTrue((temp / "runtime/build/web/security/wasm/app.wasm").is_file())
            build_log = (temp / "runtime/build/web/security/javascript/build.log").read_text()
            chrome_log = (temp / "runtime/build/web/security/javascript/chrome.log").read_text()
            self.assertIn("<repo-root>/tooling/input.dart", build_log)
            self.assertIn("<home>/Library/profile", chrome_log)
            self.assertNotIn(str(Path.home()), build_log + chrome_log)
            self.assertFalse(any(line.endswith(" ") for line in build_log.splitlines()))

    def test_failed_generation_retains_prior_success(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root / ".tools") as temporary:
            temp = Path(temporary)
            args, reporter = self.fixture(temp)
            with mock.patch.object(report, "__file__", str(reporter)):
                report.publish(args)
            result = temp / "runtime/build/web/security/results.json"
            before = hashlib.sha256(result.read_bytes()).hexdigest()
            (temp / "raw/wasm/observation.json").write_text('{"flutterView":false,"title":"failure"}')
            with self.assertRaises(ValueError):
                with mock.patch.object(report, "__file__", str(reporter)):
                    report.publish(args)
            self.assertEqual(before, hashlib.sha256(result.read_bytes()).hexdigest())

    def test_isolated_source_lock_rejects_sdk_byte_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root / ".tools") as temporary:
            temp = Path(temporary)
            args, _ = self.fixture(temp)
            source = args.sdk_root / "packages/flutter_tools/lib/src/commands/build_web.dart"
            source.write_bytes(b"mutated host-independent fixture\n")
            with self.assertRaisesRegex(ValueError, "SDK Source binding mismatch"):
                report.source_contract(args.repo_root, args.sdk_root)


if __name__ == "__main__":
    unittest.main()
