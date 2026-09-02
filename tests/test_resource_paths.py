import unittest
from pathlib import Path

from PIL import Image as PILImage

from plugins.compose.luck import max_resize
from plugins.others import milkywayidle
from toogle.utils import pic_max_resize


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

    def test_pic_resize_works_with_current_pillow_resampling_api(self):
        image = PILImage.new("RGB", (800, 400), "white")

        resized = pic_max_resize(image, 300, 150)

        self.assertEqual(resized.size, (300, 150))

    def test_luck_pic_resize_works_with_current_pillow_resampling_api(self):
        landscape = PILImage.new("RGB", (800, 400), "white")
        portrait = PILImage.new("RGB", (400, 800), "white")

        self.assertEqual(max_resize(landscape, 300, 150).size, (300, 150))
        self.assertEqual(max_resize(portrait, 300, 150).size, (75, 150))


if __name__ == "__main__":
    unittest.main()
