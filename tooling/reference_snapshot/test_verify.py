# SPDX-License-Identifier: Apache-2.0

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tooling.reference_snapshot.verify import (
    ReferenceSnapshotError,
    canonical_manifest,
    verify_snapshot,
)


class ReferenceSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        content = b"locked reference\n"
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        self.lock = {
            "repository": "https://example.invalid/reference",
            "commit": "a" * 40,
            "files": [{"path": "docs/reference.txt", "digest": digest}],
        }
        path = self.root / "docs/reference.txt"
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        (self.root / "SNAPSHOT.json").write_text(
            json.dumps(canonical_manifest(self.lock), indent=2) + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_snapshot_passes(self):
        verify_snapshot(self.root, self.lock)

    def test_content_drift_is_rejected(self):
        (self.root / "docs/reference.txt").write_text("drift\n", encoding="utf-8")
        with self.assertRaisesRegex(ReferenceSnapshotError, "digest"):
            verify_snapshot(self.root, self.lock)

    def test_commit_retarget_is_rejected(self):
        manifest = canonical_manifest(self.lock)
        manifest["commit"] = "b" * 40
        (self.root / "SNAPSHOT.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ReferenceSnapshotError, "commit/file lock"):
            verify_snapshot(self.root, self.lock)

    def test_missing_or_extra_file_is_rejected(self):
        (self.root / "extra.txt").write_text("extra\n", encoding="utf-8")
        with self.assertRaisesRegex(ReferenceSnapshotError, "file set"):
            verify_snapshot(self.root, self.lock)

    def test_lock_digest_retarget_is_rejected(self):
        lock = copy.deepcopy(self.lock)
        lock["files"][0]["digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ReferenceSnapshotError, "commit/file lock"):
            verify_snapshot(self.root, lock)


if __name__ == "__main__":
    unittest.main()
