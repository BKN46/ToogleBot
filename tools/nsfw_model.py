"""Pinned FalconsAI ViT classifier, independent of bot state and transport."""

import hashlib
import io
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

MODEL_REPO = "onnx-community/nsfw_image_detection-ONNX"
MODEL_REVISION = "1ceb3c7fe1e9f3f2507e6df577437f23a9149fd5"
MODEL_FILE = "onnx/model_quantized.onnx"
MODEL_SHA256 = "d9afb1e057104e6cc8616d174f0f6a8b8b0389c839eea7d5efa4bdf1a77efd27"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / ".cache/nsfw/falconsai-int8.onnx"


def verify_model(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            "NSFW model missing; run uv run python -m tools.nsfw_check download"
        )
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != MODEL_SHA256:
        raise ValueError("NSFW model SHA-256 mismatch")


def preprocess(pic: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(pic)) as source:
        with ImageOps.exif_transpose(source) as oriented:
            with oriented.convert("RGB") as rgb:
                with rgb.resize((224, 224), Image.Resampling.BILINEAR) as resized:
                    pixels = np.asarray(resized, dtype=np.float32)
    # Match the pinned ViT processor, including resize rather than center crop.
    pixels = (pixels / np.float32(255.0) - np.float32(0.5)) / np.float32(0.5)
    return np.ascontiguousarray(pixels.transpose(2, 0, 1)[None])


class NsfwDetector:
    def __init__(self, path: Path = DEFAULT_MODEL_PATH, threads: int = 4):
        if not 1 <= threads <= 16:
            raise ValueError("NSFW_THREADS must be between 1 and 16")
        verify_model(path)
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        self.session = ort.InferenceSession(
            str(path), options, providers=["CPUExecutionProvider"]
        )
        self._lock = threading.Lock()
        self._scores: OrderedDict[str, float] = OrderedDict()

    def predict(self, pic: bytes, *, cache: bool = True) -> float:
        digest = hashlib.sha256(pic).hexdigest()
        # Serialize inference and deduplicate concurrent requests for the same image.
        with self._lock:
            if cache and digest in self._scores:
                self._scores.move_to_end(digest)
                return self._scores[digest]
            pixels = preprocess(pic)
            logits = np.asarray(
                self.session.run(["logits"], {"pixel_values": pixels})[0],
                dtype=np.float64,
            )
            if logits.shape != (1, 2) or not np.isfinite(logits).all():
                raise ValueError("Invalid NSFW model output")
            probabilities = np.exp(logits[0] - logits[0].max())
            score = float(probabilities[1] / probabilities.sum())
            if cache:
                self._scores[digest] = score
                if len(self._scores) > 256:
                    self._scores.popitem(last=False)
            return score
