import hashlib
import io
import json
import threading
import time
from pathlib import Path

import bloom_filter
import imagehash

from PIL import UnidentifiedImageError, Image

from toogle.logger import logger
from tools.nsfw_model import NsfwDetector

PIC_BLOOM = bloom_filter.BloomFilter(max_elements=10**6, error_rate=0.01, filename='data/pic_bloom')
SFW_BLOOM = bloom_filter.BloomFilter(max_elements=10**6, error_rate=0.01, filename='data/sfw_bloom')
SHIT_BLOOM = bloom_filter.BloomFilter(max_elements=10**6, error_rate=0.001, filename='data/shit_bloom')
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHIT_PIC_EXEMPTIONS_PATH = PROJECT_ROOT / "data" / "not_shit_pics.json"
_SHIT_PIC_EXEMPTIONS: set[str] | None = None
_SHIT_PIC_EXEMPTIONS_LOCK = threading.RLock()
_NSFW_LOCK = threading.RLock()
_NSFW_DETECTOR = None
_NSFW_SETTINGS = None


def nsfw_thresholds() -> tuple[float, float]:
    from configs import config

    suggestive = float(config.get("NSFW_SUGGESTIVE_THRESHOLD", "0.1"))
    explicit = float(config.get("NSFW_THRESHOLD", "0.5"))
    if not 0 <= suggestive < explicit <= 1:
        raise ValueError("NSFW thresholds must satisfy 0 <= suggestive < explicit <= 1")
    return suggestive, explicit


def _load_shit_pic_exemptions() -> set[str]:
    global _SHIT_PIC_EXEMPTIONS
    if _SHIT_PIC_EXEMPTIONS is not None:
        return _SHIT_PIC_EXEMPTIONS
    try:
        raw = json.loads(SHIT_PIC_EXEMPTIONS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        raw = []
    if isinstance(raw, list):
        _SHIT_PIC_EXEMPTIONS = {str(item) for item in raw if str(item)}
    else:
        _SHIT_PIC_EXEMPTIONS = set()
    return _SHIT_PIC_EXEMPTIONS


def _save_shit_pic_exemptions(exemptions: set[str]) -> None:
    SHIT_PIC_EXEMPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = SHIT_PIC_EXEMPTIONS_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(sorted(exemptions), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(SHIT_PIC_EXEMPTIONS_PATH)


def detect_pic_nsfw(pic: bytes, output_repeat=False):
    global _NSFW_DETECTOR, _NSFW_SETTINGS
    from configs import config

    pic_md5 = hashlib.md5(pic).hexdigest()
    with _NSFW_LOCK:
        if pic_md5 in SFW_BLOOM:
            return (0.0, False) if output_repeat else 0.0
        repeat = pic_md5 in PIC_BLOOM
        path = Path(config.get("NSFW_MODEL_PATH", ".cache/nsfw/falconsai-int8.onnx"))
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        settings = (path, int(config.get("NSFW_THREADS", "4")))
        start_time = time.perf_counter()
        if _NSFW_DETECTOR is None or settings != _NSFW_SETTINGS:
            _NSFW_DETECTOR = NsfwDetector(*settings)
            _NSFW_SETTINGS = settings
        try:
            score = _NSFW_DETECTOR.predict(pic)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            score = -1
        if score >= 0:
            PIC_BLOOM.add(pic_md5)
        logger.info("Pic analysis done, nsfw score %.5f, use time %.2fms",
                    score, (time.perf_counter() - start_time) * 1000)
    if output_repeat:
        return score, repeat
    return score # type: ignore


def get_pic_average_hash(pic_bytes: bytes, size: int = 512, hash_size: int = 16) -> str:
    start_time = time.time()
    try:
        with Image.open(io.BytesIO(pic_bytes)) as source:
            with source.convert("RGB") as converted:
                with converted.resize(
                    (size, size), Image.Resampling.LANCZOS
                ) as resized:
                    hash_val = str(
                        imagehash.average_hash(resized, hash_size=hash_size)
                    )
    except Exception as exc:
        logger.error("get_pic_hash error: %s", exc)
        return ""
    use_time = (time.time() - start_time) * 1000
    logger.info("Pic hash done, use time %.2fms", use_time)
    return hash_val


def register_shit_pic(pic_bytes: bytes):
    if len(pic_bytes) > 5 * 1024 * 1024:
        return
    pic_md5 = get_pic_average_hash(pic_bytes)
    if not pic_md5:
        return
    with _SHIT_PIC_EXEMPTIONS_LOCK:
        exemptions = _load_shit_pic_exemptions()
        if pic_md5 in exemptions:
            exemptions.remove(pic_md5)
            _save_shit_pic_exemptions(exemptions)
        SHIT_BLOOM.add(pic_md5)


def unregister_shit_pic(pic_bytes: bytes):
    if len(pic_bytes) > 5 * 1024 * 1024:
        return
    pic_md5 = get_pic_average_hash(pic_bytes)
    if not pic_md5:
        return
    with _SHIT_PIC_EXEMPTIONS_LOCK:
        exemptions = _load_shit_pic_exemptions()
        if pic_md5 not in exemptions:
            exemptions.add(pic_md5)
            _save_shit_pic_exemptions(exemptions)


def is_shit_pic(pic_bytes: bytes):
    if len(pic_bytes) > 5 * 1024 * 1024:
        return False
    pic_md5 = get_pic_average_hash(pic_bytes)
    if not pic_md5:
        return False
    with _SHIT_PIC_EXEMPTIONS_LOCK:
        if pic_md5 in _load_shit_pic_exemptions():
            return False
    return pic_md5 in SHIT_BLOOM
