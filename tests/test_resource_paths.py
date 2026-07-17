import unittest
from pathlib import Path

from plugins.others import milkywayidle


class ResourcePathTest(unittest.TestCase):
    def test_milkywayidle_data_stays_under_repository(self):
        project_root = Path(__file__).resolve().parents[1]
        expected = project_root / "data" / "milkywayidle"

        self.assertEqual(milkywayidle.DATA_DIR, expected)
        for path in (
            milkywayidle.API_DATA_PATH,
            milkywayidle.DB_DATA_PATH,
            milkywayidle.LEVEL_DATA_PATH,
            milkywayidle.TRANSLATE_FILE_PATH,
        ):
            self.assertEqual(path.parent, expected)


if __name__ == "__main__":
    unittest.main()
