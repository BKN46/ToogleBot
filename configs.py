import ast
from pathlib import Path
from typing import Any

import toogle.logger as logger


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / ".env"
CONFIG_DEFAULTS: dict[str, Any] = {
    "DOUBAO_IMAGE_MODEL": "doubao-seedream-5-0-260128",
    "DOUBAO_VIDEO_MODEL": "doubao-seedance-1-5-pro-251215",
    "ONLY_READ": [],
    "TOOGLEPICGEN_GROUP_LIST": [],
    "WNW_ANSWER_DELAY_SECONDS": "90",
}
config: dict[str, Any] = {}


def parse_value(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"invalid list configuration: {value!r}") from exc
        if not isinstance(parsed, list):
            raise ValueError(f"configuration is not a list: {value!r}")
        return parsed
    return value


def load_config(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"invalid config line {line_number}: missing '='")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid config line {line_number}: empty key")
        loaded[key] = parse_value(value)
    return loaded


def reload_config(path: Path = DEFAULT_CONFIG_PATH) -> None:
    loaded = {**CONFIG_DEFAULTS, **load_config(path)}
    config.clear()
    config.update(loaded)
    if "proxies" in globals():
        proxies.update(
            http=config.get("REQUEST_PROXY_HTTP", ""),
            https=config.get("REQUEST_PROXY_HTTPS", ""),
        )


reload_config()

proxies = {
    "http": config.get("REQUEST_PROXY_HTTP", ""),
    "https": config.get("REQUEST_PROXY_HTTPS", ""),
}

key_check = {
    "NovelAISecret": "NovelAI作图相关功能",
    "GPTSecret": "GPT相关功能",
    "GPTModel": "GPT相关功能",
    "GPTUrl": "GPT相关功能",
    "BLACK_LIST": "黑名单",
    "GROUP_LIST": "每日新闻",
    "DISABLED_MODULE": "禁用功能",
    "WT_DATAMINE_GIT": "战雷拆包数据库查询功能",
    "SCRIPING_ANT_TOKEN": "涉及Cloudflare反反爬功能",
    "REQUEST_PROXY_HTTP": "部分需翻墙功能",
    "REQUEST_PROXY_HTTPS": "部分需翻墙功能",
    "DOUBAO_API_KEY": "豆包图片/视频生成功能",
    "HEALTHCARE_GROUP_LIST": "提肛喝水小助手",
    "HISTORY_SAVE_PATH": "消息记录持久化路径",
}

for key, description in key_check.items():
    if key not in config:
        logger.warning(".env 中不包含 %s 项，将导致无法正常使用%s", key, description)
