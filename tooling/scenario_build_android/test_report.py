# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import hashlib
import tempfile
import unittest
from pathlib import Path

from tooling.scenario_build_android import report


class BuildAndroidSecurityReporterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]

    def inputs(self, raw: Path) -> list[str]:
        values = []
        for variant in report.VARIANTS:
            row = raw / variant
            row.mkdir(parents=True)
            (row / "app.apk").write_bytes(b"APK" + b"x" * 1_000_000)
            debug = ' android:debuggable="true"' if variant == "debug-apk-install" else ""
            (row / "manifest.xml").write_text(f'<manifest><application{debug}/></manifest>')
            (row / "signing.txt").write_text("Signer #1 certificate SHA-256 digest: 00\n")
            (row / "screen.png").write_bytes(b"\x89PNG\r\n\x1a\nproof")
            (row / "platform-tree.xml").write_text(
                f'<hierarchy><node content-desc="build android security {variant} PASS"/></hierarchy>'
            )
            for kind, name in (
                ("apk", "app.apk"), ("manifest", "manifest.xml"), ("signing", "signing.txt"),
                ("screen", "screen.png"), ("tree", "platform-tree.xml"),
            ):
                values.append(f"{variant}={kind}={row / name}")
        return values

    def args(self, output: Path, inputs: list[str]) -> argparse.Namespace:
        return argparse.Namespace(
            repo_root=self.root, output=output, sdk_root=self.root / ".tools/flutter-3.47.1/flutter",
            harness=self.root / "scripts/scenario-build-android-security-runtime.sh",
            source=self.root / "tooling/scenario_build_android/build_security_main.dart",
            started_at="2026-08-31T00:00:00Z", completed_at="2026-08-31T00:01:00Z",
            runtime_identity={"profile": "android-emulator", "runner_kind": "android-emulator", "os": "Android 16", "architecture": "arm64-v8a", "api_level": 36, "device_id": "emulator-5554", "physical_device": False},
            input=inputs,
        )

    def test_publishes_both_build_variants(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root / ".tools") as temporary:
            temp = Path(temporary)
            report.publish(self.args(temp / "runtime", self.inputs(temp / "raw")))
            result = temp / "runtime/build/android/security/results.json"
            self.assertTrue(result.is_file())
            self.assertTrue((temp / "runtime/build/android/security/release-apk/app.apk").is_file())

    def test_failed_generation_retains_prior_success(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root / ".tools") as temporary:
            temp = Path(temporary)
            inputs = self.inputs(temp / "raw")
            args = self.args(temp / "runtime", inputs)
            report.publish(args)
            result = temp / "runtime/build/android/security/results.json"
            before = hashlib.sha256(result.read_bytes()).hexdigest()
            (temp / "raw/release-apk/platform-tree.xml").write_text("<hierarchy/>")
            with self.assertRaises(ValueError):
                report.publish(args)
            self.assertEqual(before, hashlib.sha256(result.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
