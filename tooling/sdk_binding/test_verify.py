# SPDX-License-Identifier: Apache-2.0

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("verify.py")
SPEC = importlib.util.spec_from_file_location("sdk_binding_verify", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SdkBindingTest(unittest.TestCase):
    def test_rejects_empty_sdk_root(self) -> None:
        with self.assertRaisesRegex(MODULE.BindingError, "空"):
            MODULE.normalize_sdk_root("   ")

    def test_rejects_missing_sdk_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            with self.assertRaisesRegex(MODULE.BindingError, "存在"):
                MODULE.validate_root_shape(missing)

    def test_rejects_wrong_sdk_root_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wrong = Path(directory)
            (wrong / "bin").mkdir()
            with self.assertRaisesRegex(MODULE.BindingError, "必須path"):
                MODULE.validate_root_shape(wrong)

    def test_rejects_wrong_sdk_version(self) -> None:
        actual = {
            "flutter_version": "3.48.0",
            "framework_revision": "wrong",
            "metadata_digests": {"DEPS": "sha256:wrong"},
        }
        expected = {
            "flutter_version": "3.47.1",
            "framework_revision": "6655482ec06e547f90abf8ae7590466f4415978d",
            "metadata_digests": {"DEPS": "sha256:expected"},
        }
        with self.assertRaisesRegex(MODULE.BindingError, "version/revision"):
            MODULE.validate_verified_metadata(actual, expected)

    def test_rejects_missing_source_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(MODULE.BindingError, "0件"):
                MODULE.collect_source_set(
                    root, ["packages/flutter/lib/src/widgets/framework.dart"]
                )

    def test_source_digest_changes_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "packages/flutter/lib/src/widgets/framework.dart"
            source.parent.mkdir(parents=True)
            source.write_text("first", encoding="utf-8")
            first = MODULE.collect_source_set(
                root, ["packages/flutter/lib/src/widgets/framework.dart"]
            )
            source.write_text("second", encoding="utf-8")
            second = MODULE.collect_source_set(
                root, ["packages/flutter/lib/src/widgets/framework.dart"]
            )
            self.assertNotEqual(first, second)
            self.assertNotEqual(
                MODULE.canonical_digest(first), MODULE.canonical_digest(second)
            )


if __name__ == "__main__":
    unittest.main()
