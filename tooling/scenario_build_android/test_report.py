# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def fixture(self, temp: Path) -> tuple[argparse.Namespace, Path]:
        fixture_root = temp / "repo"
        sdk_root = temp / "sdk"
        harness = fixture_root / "scripts/scenario-build-android-security-runtime.sh"
        source = fixture_root / "tooling/scenario_build_android/build_security_main.dart"
        reporter = fixture_root / "tooling/scenario_build_android/report.py"
        for path, contents in (
            (harness, "#!/bin/sh\n"),
            (source, "void main() {}\n"),
            (reporter, "# isolated reporter fixture\n"),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        source_bindings = []
        for relative, contents in (
            ("packages/flutter_tools/lib/src/commands/build_apk.dart", b"isolated build apk fixture\n"),
            ("packages/flutter_tools/templates/app/android.tmpl/gradle.properties.tmpl", b"isolated gradle fixture\n"),
        ):
            path = sdk_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
            source_bindings.append({"path": relative, "digest": report.digest(path)})
        proof = fixture_root / "evidence/scenarios/surfaces/build/android/security.proof.json"
        proof.parent.mkdir(parents=True, exist_ok=True)
        proof.write_text(json.dumps({"source_bindings": source_bindings}))
        args = argparse.Namespace(
            repo_root=fixture_root, output=temp / "runtime", sdk_root=sdk_root,
            harness=harness,
            source=source,
            started_at="2026-08-31T00:00:00Z", completed_at="2026-08-31T00:01:00Z",
            runtime_identity={"profile": "android-emulator", "runner_kind": "android-emulator", "os": "Android 16", "architecture": "arm64-v8a", "api_level": 36, "device_id": "emulator-5554", "physical_device": False},
            input=self.inputs(temp / "raw"),
        )
        return args, reporter

    def test_publishes_both_build_variants(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root / ".tools") as temporary:
            temp = Path(temporary)
            args, reporter = self.fixture(temp)
            with mock.patch.object(report, "__file__", str(reporter)):
                report.publish(args)
            result = temp / "runtime/build/android/security/results.json"
            self.assertTrue(result.is_file())
            self.assertTrue((temp / "runtime/build/android/security/release-apk/app.apk").is_file())

    def test_failed_generation_retains_prior_success(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root / ".tools") as temporary:
            temp = Path(temporary)
            args, reporter = self.fixture(temp)
            with mock.patch.object(report, "__file__", str(reporter)):
                report.publish(args)
            result = temp / "runtime/build/android/security/results.json"
            before = hashlib.sha256(result.read_bytes()).hexdigest()
            (temp / "raw/release-apk/platform-tree.xml").write_text("<hierarchy/>")
            with self.assertRaises(ValueError):
                with mock.patch.object(report, "__file__", str(reporter)):
                    report.publish(args)
            self.assertEqual(before, hashlib.sha256(result.read_bytes()).hexdigest())

    def test_isolated_source_lock_rejects_sdk_byte_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=self.root / ".tools") as temporary:
            temp = Path(temporary)
            args, _ = self.fixture(temp)
            source = args.sdk_root / "packages/flutter_tools/lib/src/commands/build_apk.dart"
            source.write_bytes(b"mutated host-independent fixture\n")
            with self.assertRaisesRegex(ValueError, "SDK Source binding mismatch"):
                report.source_contract(args.repo_root, args.sdk_root)


if __name__ == "__main__":
    unittest.main()
