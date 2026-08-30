import os
import tempfile
import unittest
from pathlib import Path

from tooling.scenario_proof.atomic_publish import atomic_publish_directory


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class AtomicPublishTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / "integrated"
        self.output.mkdir()
        (self.output / "index.json").write_text("old-index", encoding="utf-8")
        (self.output / "old-only.trace.json").write_text("old-trace", encoding="utf-8")
        self.previous = snapshot(self.output)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def validate_exact(staging: Path) -> None:
        files = {path.name for path in staging.iterdir() if path.is_file()}
        if files != {"index.json", "new.trace.json"}:
            raise ValueError(f"partial or mixed bundle: {sorted(files)}")

    @staticmethod
    def build_complete(staging: Path) -> None:
        (staging / "new.trace.json").write_text("new-trace", encoding="utf-8")
        (staging / "index.json").write_text("new-index", encoding="utf-8")

    def test_success_replaces_whole_directory_without_old_new_mixture(self):
        atomic_publish_directory(self.output, self.build_complete, self.validate_exact)
        self.assertEqual(snapshot(self.output), {"index.json": b"new-index", "new.trace.json": b"new-trace"})

    def test_failed_run_does_not_erase_prior_success(self):
        def fail_after_partial_write(staging: Path) -> None:
            (staging / "new.trace.json").write_text("partial", encoding="utf-8")
            raise RuntimeError("run failed")

        with self.assertRaisesRegex(RuntimeError, "run failed"):
            atomic_publish_directory(self.output, fail_after_partial_write, self.validate_exact)
        self.assertEqual(snapshot(self.output), self.previous)

    def test_partial_staging_is_rejected_without_overwrite(self):
        def build_partial(staging: Path) -> None:
            (staging / "new.trace.json").write_text("partial", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "partial or mixed bundle"):
            atomic_publish_directory(self.output, build_partial, self.validate_exact)
        self.assertEqual(snapshot(self.output), self.previous)

    def test_swap_failure_removes_partial_new_output_and_rolls_back(self):
        def fail_new_directory_swap(source: Path, destination: Path) -> None:
            if source.name.startswith(".integrated.staging-"):
                destination.mkdir()
                (destination / "partial-new.trace.json").write_text("partial-new", encoding="utf-8")
                raise OSError("injected swap failure")
            os.rename(source, destination)

        with self.assertRaisesRegex(OSError, "injected swap failure"):
            atomic_publish_directory(self.output, self.build_complete, self.validate_exact, rename=fail_new_directory_swap)
        self.assertEqual(snapshot(self.output), self.previous)
        self.assertEqual([path for path in self.root.iterdir() if path.name.startswith(".integrated.")], [])


if __name__ == "__main__":
    unittest.main()
