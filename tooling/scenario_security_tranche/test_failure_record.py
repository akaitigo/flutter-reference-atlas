# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from tooling.scenario_security_tranche import failure_record


class FailureRecordTest(unittest.TestCase):
    def test_post_marker_timeout_is_sanitized_and_never_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "raw/runtime.log"
            log.parent.mkdir(parents=True)
            log.write_text(
                "ATLAS_CAPTURE_READY:input.focus-traversal:ordered-traversal\n"
                f"source={root}/private.dart\n"
                "runner did not terminate\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(
                phase="post-marker-timeout",
                run_id="run-test",
                surface="input.focus-traversal",
                variant="ordered-traversal",
                exit_code=143,
                device_id="emulator-5554",
                os_version="16",
                api_level=36,
                architecture="arm64-v8a",
                source_digest="source-digest",
                harness_digest="harness-digest",
                log=log,
                repo_root=root,
            )
            record = failure_record.build_record(args)
            encoded = json.dumps(record)
            self.assertEqual(record["status"], "failed")
            self.assertEqual(record["phase"], "post-marker-timeout")
            self.assertFalse(record["published"])
            self.assertTrue(record["prior_success_evidence_retained"])
            self.assertEqual(record["retries"], 0)
            self.assertNotIn(str(root), encoded)
            self.assertIn("<repo-root>", encoded)

    def test_unknown_phase_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "runtime.log"
            log.write_text("failed\n", encoding="utf-8")
            args = argparse.Namespace(
                phase="success",
                run_id="run-test",
                surface="input.text-ime",
                variant="bidi-rejection",
                exit_code=0,
                device_id="emulator-5554",
                os_version="16",
                api_level=36,
                architecture="arm64-v8a",
                source_digest="source-digest",
                harness_digest="harness-digest",
                log=log,
                repo_root=root,
            )
            with self.assertRaises(ValueError):
                failure_record.build_record(args)


if __name__ == "__main__":
    unittest.main()
