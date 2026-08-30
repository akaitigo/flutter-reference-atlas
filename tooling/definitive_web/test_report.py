import unittest

from tooling.definitive_web.report import observed_test_count, sanitized_log


class DefinitiveWebReportTest(unittest.TestCase):
    def test_extracts_final_flutter_test_count(self):
        self.assertEqual(observed_test_count("00:03 +5: All tests passed!\n"), 5)

    def test_missing_success_marker_is_zero(self):
        self.assertEqual(observed_test_count("00:03 +4 -1: failure\n"), 0)

    def test_sanitizes_repository_and_temporary_paths(self):
        value = sanitized_log(
            "loading /opt/build/flutter-reference-atlas/test/app_test.dart\n"
            "Generated wasm module '/opt/tmp/module.wasm' and JS init file '/opt/tmp/main.mjs'.\n"
        )
        self.assertNotIn("/opt/build", value)
        self.assertNotIn("/opt/tmp", value)
        self.assertIn("<repo-root>/test/app_test.dart", value)


if __name__ == "__main__":
    unittest.main()
