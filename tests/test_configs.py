import tempfile
import unittest
from pathlib import Path

import configs


class ConfigTest(unittest.TestCase):
    def test_load_config_preserves_equals_and_parses_lists_safely(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / ".env"
            path.write_text(
                "# comment\nTOKEN=part=part\nIDS=[\"100\", \"200\"]\n",
                encoding="utf-8",
            )
            loaded = configs.load_config(path)
        self.assertEqual(loaded["TOKEN"], "part=part")
        self.assertEqual(loaded["IDS"], ["100", "200"])

    def test_reload_updates_existing_config_object(self):
        original = dict(configs.config)
        reference = configs.config
        try:
            with tempfile.TemporaryDirectory() as tempdir:
                path = Path(tempdir) / ".env"
                path.write_text("VALUE=updated\n", encoding="utf-8")
                configs.reload_config(path)
            self.assertIs(configs.config, reference)
            self.assertEqual(reference, {"VALUE": "updated"})
        finally:
            configs.config.clear()
            configs.config.update(original)


if __name__ == "__main__":
    unittest.main()
