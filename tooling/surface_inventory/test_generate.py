# SPDX-License-Identifier: Apache-2.0

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("generate.py")
SPEC = importlib.util.spec_from_file_location("surface_inventory_generate", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SurfaceInventoryTest(unittest.TestCase):
    def test_directives_are_unique_and_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.dart"
            source.write_text(
                "export 'z.dart';\npart 'body.dart';\nexport 'a.dart' show PublicType;\nexport 'z.dart';\n",
                encoding="utf-8",
            )
            self.assertEqual(MODULE.read_directives(source, "export"), ["a.dart", "z.dart"])
            self.assertEqual(MODULE.read_directives(source, "part"), ["body.dart"])

    def test_dart_inventory_excludes_private_libraries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / MODULE.DART_LIBRARIES
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "vm_common": {"libraries": {"core": {}, "_internal": {}}},
                        "dartdevc": {
                            "libraries": {
                                "html": {},
                                "html_common": {},
                                "core": {},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            inventory = MODULE.dart_inventory(root)
            self.assertEqual(inventory["library_count"], 2)
            self.assertEqual(
                inventory["libraries"],
                [
                    {"id": "dart:core", "platform_sections": ["dartdevc", "vm_common"]},
                    {"id": "dart:html", "platform_sections": ["dartdevc"]},
                ],
            )

    def test_baseline_parser_keeps_nested_sections_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.yaml"
            path.write_text(
                "flutter:\n  version: 3.47.1\n  channel: stable\ndart:\n  version: 3.13.1\n",
                encoding="utf-8",
            )
            self.assertEqual(
                MODULE.read_baseline(path),
                {
                    "flutter": {"version": "3.47.1", "channel": "stable"},
                    "dart": {"version": "3.13.1"},
                },
            )


if __name__ == "__main__":
    unittest.main()
