import hashlib
import io
import json
import tempfile
import threading
import time
from pathlib import Path

import bloom_filter
import imagehash

from PIL import UnidentifiedImageError, Image

from toogle.logger import logger

PIC_BLOOM = bloom_filter.BloomFilter(max_elements=10**6, error_rate=0.01, filename='data/pic_bloom')
SFW_BLOOM = bloom_filter.BloomFilter(max_elements=10**6, error_rate=0.01, filename='data/sfw_bloom')
SHIT_BLOOM = bloom_filter.BloomFilter(max_elements=10**6, error_rate=0.001, filename='data/shit_bloom')
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHIT_PIC_EXEMPTIONS_PATH = PROJECT_ROOT / "data" / "not_shit_pics.json"
_SHIT_PIC_EXEMPTIONS: set[str] | None = None
_SHIT_PIC_EXEMPTIONS_LOCK = threading.RLock()


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
    pic_md5 = hashlib.md5(pic).hexdigest()
    if pic_md5 in SFW_BLOOM:
        if output_repeat:
            return -1, False
        return -1
    repeat = pic_md5 in PIC_BLOOM
    PIC_BLOOM.add(pic_md5)

    import opennsfw2
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(pic)
        pic_path = f.name
    try:
        start_time = time.time()
        score = opennsfw2.predict_image(pic_path)
        use_time = (time.time() - start_time) * 1000
        logger.info(
            "Pic analysis done, nsfw score %.5f, use time %.2fms",
            score,
            use_time,
        )
    except UnidentifiedImageError:
        score = -1
    finally:
        Path(pic_path).unlink(missing_ok=True)
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
