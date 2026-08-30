import unittest

from tooling.definitive_android.report import sanitized_log


class DefinitiveAndroidReportTest(unittest.TestCase):
    def test_sanitizes_repository_and_temporary_paths(self):
        value = sanitized_log(
            "loading /opt/build/flutter-reference-atlas/integration_test/app.dart\n"
            "temporary /var/folders/a/b/flutter_tools/output\n"
        )
        self.assertNotIn("/opt/build", value)
        self.assertNotIn("/var/folders", value)
        self.assertIn("<repo-root>/integration_test/app.dart", value)


if __name__ == "__main__":
    unittest.main()
