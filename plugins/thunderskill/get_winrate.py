import os
import io
import csv
import datetime
import json
import math
import threading
import time
from pathlib import Path
from typing import Tuple

import requests
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

from toogle.utils import text2img
from toogle.logger import logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]
save_path = PROJECT_ROOT / "data" / "wt"

SOURCE_ROOT = "https://raw.githubusercontent.com/ControlNet/wt-data-project.data/master"
SOURCE_ROOTS = (
    "https://ghfast.top/" + SOURCE_ROOT,
    "https://gh-proxy.com/" + SOURCE_ROOT,
    SOURCE_ROOT,
)
metajson_url = SOURCE_ROOT + "/metadata.json"
data_path = SOURCE_ROOT + "/joined/"
full_data_url = SOURCE_ROOT + "/rb_ranks_1.csv"
font_path = str(PROJECT_ROOT / "tools" / "fonts" / "DejaVuSansMono-Bold.ttf")
REQUEST_TIMEOUT = (5, 15)
DOWNLOAD_DEADLINE_SECONDS = 45
MAX_DOWNLOAD_BYTES = 120 * 1024 * 1024
CACHE_MAX_AGE_DAYS = 7
_CACHE_LOCK = threading.Lock()

proxies = { "http": None, "https": None}


class WinRateDataError(ValueError):
    pass


def _fetch_text(relative_path, validate):
    for root in SOURCE_ROOTS:
        response = None
        started = time.monotonic()
        try:
            response = requests.get(
                f"{root}/{relative_path}",
                proxies=proxies,
                timeout=REQUEST_TIMEOUT,
                stream=True,
            )
            response.raise_for_status()
            chunks = []
            size = 0
            for chunk in response.iter_content(256 * 1024):
                size += len(chunk)
                if size > MAX_DOWNLOAD_BYTES:
                    raise WinRateDataError("Win-rate download exceeds size limit")
                if time.monotonic() - started > DOWNLOAD_DEADLINE_SECONDS:
                    raise requests.Timeout("Win-rate download exceeded deadline")
                chunks.append(chunk)
            raw = b"".join(chunks).decode("utf-8-sig")
            validate(raw)
            logger.info("Win-rate data fetched: source=%s file=%s bytes=%s", root, relative_path, size)
            return raw
        except (requests.RequestException, ValueError) as exc:
            logger.warning(
                "Win-rate source failed: source=%s file=%s error_type=%s",
                root, relative_path, type(exc).__name__,
            )
        finally:
            if response is not None:
                response.close()
    raise WinRateDataError("All win-rate data sources failed")


def _metadata_date(raw):
    metadata = json.loads(raw)
    if not isinstance(metadata, list) or not metadata:
        raise WinRateDataError("Empty or invalid win-rate metadata")
    try:
        return max(datetime.date.fromisoformat(item["date"]) for item in metadata).isoformat()
    except (KeyError, TypeError, ValueError) as exc:
        raise WinRateDataError("Invalid win-rate date") from exc


def _latest_date():
    return _metadata_date(_fetch_text("metadata.json", _metadata_date))


def get_winrate_v():
    wt_winrate_v = "wt_winrate_v"

    date_date = _latest_date()
    data_url = data_path + f"{date_date}.csv"
    file_name = wt_winrate_v + "_" + date_date
    save_path.mkdir(parents=True, exist_ok=True)
    wr_list = [x for x in os.listdir(save_path) if x.startswith(wt_winrate_v)]
    if file_name not in wr_list:
        # print("Downloading")
        for x in wr_list:
            os.remove(os.path.join(save_path, x))
        res = requests.get(data_url, proxies=proxies, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
        (save_path / file_name).write_bytes(res.content)
    return (save_path / file_name).read_text(encoding="utf-8"), date_date


def _get_current_winrate_n():
    date = _latest_date()
    path = save_path / f"wt_winrate_n_{date}"
    with _CACHE_LOCK:
        if path.is_file():
            raw = path.read_text(encoding="utf-8")
            try:
                _parse_winrate_n(raw, date)
                return raw, date
            except WinRateDataError:
                pass  # Replace an invalid cache only after a valid download.
        raw = _fetch_text("rb_ranks_1.csv", lambda text: _parse_winrate_n(text, date))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_text(raw, encoding="utf-8")
        temporary_path.replace(path)
        return raw, date


def get_winrate_n():
    try:
        return _get_current_winrate_n()
    except (requests.RequestException, WinRateDataError):
        oldest = (datetime.date.today() - datetime.timedelta(days=CACHE_MAX_AGE_DAYS)).isoformat()
        today = datetime.date.today().isoformat()
        for path in sorted(save_path.glob("wt_winrate_n_*"), reverse=True):
            date = path.name.removeprefix("wt_winrate_n_")
            try:
                if datetime.date.fromisoformat(date).isoformat() != date or not oldest <= date <= today:
                    continue
                raw = path.read_text(encoding="utf-8")
                _parse_winrate_n(raw, date)
            except (OSError, ValueError):
                continue
            logger.warning("Win-rate sources unavailable; using cached data dated %s", date)
            return raw, date
        raise


def parse_winrate_n():
    raw, date = get_winrate_n()
    return _parse_winrate_n(raw, date), date


def _parse_winrate_n(raw, date):
    reader = csv.DictReader(io.StringIO(raw))
    required = {"nation", "cls", "date", "rb_lower_br", "rb_battles_sum", "rb_win_rate"}
    if not required.issubset(reader.fieldnames or []):
        raise WinRateDataError("Invalid win-rate CSV header")
    wr_dict = {}
    for row in reader:
        if row["cls"] != "Ground_vehicles" or row["date"] != date:
            continue
        try:
            br = float(row["rb_lower_br"])
            battles = float(row["rb_battles_sum"])
            rate = float(row["rb_win_rate"])
            if not all(math.isfinite(value) for value in (br, battles, rate)):
                raise ValueError("Non-finite win-rate value")
            if not row["nation"] or battles < 0 or not 0 <= rate <= 100:
                raise ValueError("Win-rate value out of range")
        except (TypeError, ValueError) as exc:
            raise WinRateDataError("Invalid win-rate CSV value") from exc
        wr_dict.setdefault(row["nation"], {})[row["rb_lower_br"]] = {
            'num': row["rb_battles_sum"],
            'wr': row["rb_win_rate"]
        }
    if not wr_dict:
        raise WinRateDataError("No ground realistic data for the latest date")
    return wr_dict


def draw_winrate_n_text():
    res, date = parse_winrate_n()
    whitespace = 10
    output_text = f"{date + ' Realistic Battle':^{whitespace * (len(res) + 1)}}\n\n" + " " * whitespace
    rank_dict = {}
    for nation, nation_data in res.items():
        output_text += f"{nation:^{whitespace}}"
        for rank, res_data in nation_data.items():
            if rank not in rank_dict:
                rank_dict[rank] = {}
            rank_dict[rank][nation] = res_data
    output_text += f"\n\n"

    rank_list = sorted([(k, v) for k, v in rank_dict.items()], key=lambda x: float(x[0]), reverse=True)
    for rank, rank_data in rank_list:
        output_text += f"{rank:^{whitespace}}"
        for nation, nation_data in rank_data.items():
            output_text += f"{float(nation_data['wr']):^{whitespace}.2f}"
        output_text += "\n"
        output_text += " " * whitespace
        for nation, nation_data in rank_data.items():
            output_text += f"{int(float(nation_data['num'])):^{whitespace}}"
        output_text += "\n \n"

    # print(output_text)
    return text2img(
        output_text,
        font_path=font_path,
        word_size=15,
        max_size=(2000, 8000),
        font_height_adjust=4,
    )


def color_gradient(
    c1: Tuple[int, int, int],
    c2: Tuple[int, int, int],
    v: float,
    mid_c: Tuple[int, int, int] = (255, 255, 255),
) -> Tuple[int, int, int]:
    if v < 0:
        return c1
    elif v > 1:
        return c2
    elif v <= 0.5:
        return (
            int(c1[0] + (mid_c[0] - c1[0]) * v * 2),
            int(c1[1] + (mid_c[1] - c1[1]) * v * 2),
            int(c1[2] + (mid_c[2] - c1[2]) * v * 2),
        )
    else:
        return (
            int(c2[0] + (mid_c[0] - c2[0]) * (1 - v) * 2),
            int(c2[1] + (mid_c[1] - c2[1]) * (1 - v) * 2),
            int(c2[2] + (mid_c[2] - c2[2]) * (1 - v) * 2),
        )


def draw_winrate_n():
    res, date = parse_winrate_n()
    whitespace = 10
    font_size = 15
    block_width, block_height = 100, 20
    font = PIL.ImageFont.truetype(font_path, font_size)
    rank_count = len({rank for nation_data in res.values() for rank in nation_data})
    
    gen_image = PIL.Image.new(
        "RGBA",
        ((len(res) + 2) * block_width + 70, 90 + rank_count * block_height * 3),
        (255, 255, 255),
    )
    draw = PIL.ImageDraw.Draw(gen_image)
    draw.text(
        (block_width, 20),
        date + ' Ground Realistic Battle',
        (10, 10, 10),
        font=font,
    )
    
    rank_dict = {}
    tmp_x = block_width * 2
    for nation, nation_data in res.items():
        draw.text(
            (tmp_x, 50),
            nation,
            (10, 10, 10),
            font=font,
        )
        tmp_x += block_width
        for rank, res_data in nation_data.items():
            if rank not in rank_dict:
                rank_dict[rank] = {}
            rank_dict[rank][nation] = res_data

    rank_list = sorted([(k, v) for k, v in rank_dict.items()], key=lambda x: float(x[0]), reverse=True)

    tmp_x, tmp_y = block_width, 70
    for rank, rank_data in rank_list:
        tmp_x = block_width
        draw.text(
            (tmp_x, tmp_y),
            f"{rank}",
            (10, 10, 10),
            font=font,
        )
        tmp_x += block_width
        for nation, nation_data in rank_data.items():
            wr = float(nation_data['wr'])
            color = color_gradient(
                (255, 0, 0),
                (0, 255, 0),
                # math.sqrt(wr / 100) if wr > 50 else math.pow(wr / 100, 2)
                ((wr - 10) / 90)
            )
            if wr == 0:
                color = (130, 130, 130)
            draw.rectangle(
                (tmp_x, tmp_y, tmp_x + block_width, tmp_y + block_height * 2),
                fill = color,
            )
            draw.text(
                (tmp_x, tmp_y),
                f"{wr:.2f}",
                (10, 10, 10),
                font=font,
            )
            tmp_x += block_width
        tmp_x = block_width * 2
        tmp_y += block_height
        for nation, nation_data in rank_data.items():
            draw.text(
                (tmp_x, tmp_y),
                f"{int(float(nation_data['num']))}",
                (10, 10, 10),
                font=font,
            )
            tmp_x += block_width
        tmp_y += block_height * 2

    img_bytes = io.BytesIO()
    gen_image.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


if __name__ == "__main__":
    # draw_winrate_n()
    import io
    import time
    start_time = time.time()
    pic = draw_winrate_n()
    open('data/test.jpg', 'wb').write(pic)
    print(f"use time: {time.time() - start_time:.4f}")
