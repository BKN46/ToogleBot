import io
import tempfile
import threading
import unittest
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import numpy as np
from PIL import Image, UnidentifiedImageError

from tools.nsfw_model import NsfwDetector, preprocess, verify_model


def image_bytes(color="white", mode="RGB"):
    with Image.new(mode, (80, 40), color) as image:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()


class NsfwModelTest(unittest.TestCase):
    def detector(self, logits):
        detector = object.__new__(NsfwDetector)
        detector._lock = threading.Lock()
        detector._scores = OrderedDict()
        detector.session = Mock()
        detector.session.run.return_value = [np.array([logits])]
        return detector

    def test_preprocess_shape_channels_and_normalization(self):
        tensor = preprocess(image_bytes("red"))
        self.assertEqual(tensor.shape, (1, 3, 224, 224))
        self.assertEqual(tensor.dtype, np.float32)
        self.assertTrue(tensor.flags.c_contiguous)
        np.testing.assert_array_equal(tensor[0, :, 0, 0], [1, -1, -1])
        for mode in ("L", "RGBA", "P"):
            self.assertEqual(preprocess(image_bytes(mode=mode)).shape, tensor.shape)

    def test_invalid_input_does_not_produce_safe_score(self):
        detector = self.detector([0, 1])
        with self.assertRaises(UnidentifiedImageError):
            detector.predict(b"invalid")
        detector.session.run.assert_not_called()
        self.assertFalse(detector._scores)

    def test_softmax_uses_nsfw_label_one_and_is_stable(self):
        detector = self.detector([1000, 1002])
        self.assertAlmostEqual(detector.predict(image_bytes()), 0.8807970779)
        detector = self.detector([1002, 1000])
        self.assertAlmostEqual(detector.predict(image_bytes()), 0.1192029220)

    def test_invalid_model_output_is_not_cached(self):
        for logits in ([float("nan"), 0], [0, float("inf")], [0, 1, 2]):
            detector = self.detector(logits)
            with self.assertRaises(ValueError):
                detector.predict(image_bytes())
            self.assertFalse(detector._scores)

    def test_concurrent_duplicate_only_infers_once(self):
        detector = self.detector([0, 1])
        data = image_bytes()
        with ThreadPoolExecutor(max_workers=4) as pool:
            scores = list(pool.map(detector.predict, [data] * 8))
        self.assertEqual(len(set(scores)), 1)
        detector.session.run.assert_called_once()
        detector.predict(data, cache=False)
        self.assertEqual(detector.session.run.call_count, 2)

    def test_cache_is_bounded_and_evicts_oldest(self):
        detector = self.detector([0, 1])
        first = image_bytes((0, 0, 0))
        for index in range(257):
            detector.predict(image_bytes((index % 256, index // 256, 0)))
        self.assertEqual(len(detector._scores), 256)
        detector.predict(first)
        self.assertEqual(detector.session.run.call_count, 258)

    def test_missing_and_corrupt_weights_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.onnx"
            with self.assertRaises(FileNotFoundError):
                verify_model(path)
            path.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verify_model(path)
