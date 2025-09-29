import hashlib
import tempfile
import time

import nonebot
import bloom_filter
import imagehash

from PIL import UnidentifiedImageError, Image

PIC_BLOOM = bloom_filter.BloomFilter(max_elements=10**6, error_rate=0.01, filename='data/pic_bloom')
SFW_BLOOM = bloom_filter.BloomFilter(max_elements=10**6, error_rate=0.01, filename='data/sfw_bloom')
SHIT_BLOOM = bloom_filter.BloomFilter(max_elements=10**6, error_rate=0.001, filename='data/shit_bloom')

def detect_pic_nsfw(pic: bytes, output_repeat=False):
    pic_md5 = hashlib.md5(pic).hexdigest()
    if pic_md5 in SFW_BLOOM:
        if output_repeat:
            return -1, False
        return -1
    repeat = pic_md5 in PIC_BLOOM
    PIC_BLOOM.add(pic_md5)

    import opennsfw2
    # temp file path
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(pic)
        pic_path = f.name
        try:
            start_time = time.time()
            score = opennsfw2.predict_image(pic_path)
            use_time = (time.time() - start_time) * 1000
            nonebot.logger.info(f"Pic analysis done, nsfw score {score:.5f}, use time {use_time:.2f}ms") # type: ignore
        except UnidentifiedImageError as e:
            score = -1
    if output_repeat:
        return score, repeat
    return score # type: ignore


def get_pic_average_hash(pic_bytes: bytes, size: int = 512, hash_size: int = 16) -> str:
    start_time = time.time()
    try:
        with tempfile.NamedTemporaryFile(delete=False) as img_file:
            img_file.write(pic_bytes)
            img_file.flush()
            img_file.seek(0)
            img = Image.open(img_file.name)
            img = img.convert('RGB')
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            hash_val = str(imagehash.average_hash(img, hash_size=hash_size))
    except Exception as e:
        nonebot.logger.error(f"get_pic_hash error: {e}") # type: ignore
        return ""
    use_time = (time.time() - start_time) * 1000
    nonebot.logger.info(f"Pic hash done, use time {use_time:.2f}ms") # type: ignore
    return hash_val


def regist_shit_pic(pic_bytes: bytes):
    if len(pic_bytes) > 5 * 1024 * 1024:
        return
    pic_md5 = get_pic_average_hash(pic_bytes)
    SHIT_BLOOM.add(pic_md5)


def is_shit_pic(pic_bytes: bytes):
    if len(pic_bytes) > 5 * 1024 * 1024:
        return False
    pic_md5 = get_pic_average_hash(pic_bytes)
    return pic_md5 in SHIT_BLOOM
