# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import hashlib
import tempfile
import unittest
from pathlib import Path

from tooling.scenario_build_web import report


class BuildWebSecurityReporterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]

    def inputs(self, raw: Path) -> list[str]:
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
            (row / "build.log").write_text(f"build passed: {self.root}/tooling/input.dart   \n")
            (row / "chrome.log").write_text(f"chrome passed: {Path.home()}/Library/profile\n")
            (row / "mode.txt").write_text(modes[variant] + "\n")
            for kind, name in (("artifact", "artifact.bin"), ("index", "index.html"), ("observation", "observation.json"), ("tree", "platform-tree.json"), ("screen", "screen.png"), ("buildlog", "build.log"), ("chromelog", "chrome.log"), ("mode", "mode.txt")):
                values.append(f"{variant}={kind}={row / name}")
        return values

    def args(self, output: Path, inputs: list[str]) -> argparse.Namespace:
        return argparse.Namespace(
            repo_root=self.root,
            output=output,
            sdk_root=self.root / ".tools/flutter-3.47.1/flutter",
            harness=self.root / "scripts/scenario-build-web-security-runtime.sh",
            source=self.root / "tooling/scenario_build_web/build_security_main.dart",
            started_at="2026-08-31T00:00:00Z",
            completed_at="2026-08-31T00:01:00Z",
            runtime_identity={"profile": "web-chrome", "runner_kind": "browser-runtime", "os": "macOS 26.0", "architecture": "arm64", "browser": "Google Chrome", "browser_version": "151", "physical_device": False},
            input=inputs,
        )

    def test_publishes_all_web_build_variants(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root / ".tools") as temporary:
            temp = Path(temporary)
            report.publish(self.args(temp / "runtime", self.inputs(temp / "raw")))
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
            inputs = self.inputs(temp / "raw")
            args = self.args(temp / "runtime", inputs)
            report.publish(args)
            result = temp / "runtime/build/web/security/results.json"
            before = hashlib.sha256(result.read_bytes()).hexdigest()
            (temp / "raw/wasm/observation.json").write_text('{"flutterView":false,"title":"failure"}')
            with self.assertRaises(ValueError):
                report.publish(args)
            self.assertEqual(before, hashlib.sha256(result.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
