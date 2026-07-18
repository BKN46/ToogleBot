from functools import wraps
from typing import Any

import requests

import configs

HOST = configs.config.get("HTTP_HOST", "127.0.0.1")
PORT = configs.config.get("HTTP_PORT", "3457")
TOKEN = configs.config.get("HTTP_TOKEN", "")


class NapCatHttpActionError(RuntimeError):
    pass


def _require_success(payload: Any, path: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise NapCatHttpActionError(f"NapCat action {path} returned a non-object")
    if payload.get("status") != "ok" or payload.get("retcode") != 0:
        message = payload.get("message") or payload.get("wording") or "unknown error"
        raise NapCatHttpActionError(
            f"NapCat action {path} failed: retcode={payload.get('retcode')!r}, "
            f"message={message!r}"
        )
    return payload


def bot_http(method="POST", path="/", timeout=(3, 10)):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            url = f"http://{HOST}:{PORT}{path}"
            data = func(*args, **kwargs) or {}
            header = {
                "Authorization": f"Bearer {TOKEN}"
            }
            res = requests.request(
                method,
                url,
                headers=header,
                json=data,
                timeout=timeout,
            )
            res.raise_for_status()
            return _require_success(res.json(), path)

        return wrapper

    return decorator


@bot_http(method="POST", path="/set_group_leave")
def quit_group(group_id: int, is_dismiss=False):
    return {
        "group_id": str(group_id),
        "is_dismiss": is_dismiss,
    }


@bot_http(method="POST", path="/set_group_ban")
def mute_member(group_id: int, user_id: int, duration: int):
    return {
        "group_id": str(group_id),
        "user_id": str(user_id),
        "duration": duration
    }


@bot_http(method="POST", path="/upload_group_file", timeout=(3, 120))
def upload_group_file(group_id: int, file_name: str, file_path: str):
    return {
        "group_id": str(group_id),
        "file": file_path,
        "name": file_name
    }


@bot_http(method="POST", path="/delete_msg")
def recall_msg(message_id: int):
    return {
        "message_id": str(message_id)
    }


@bot_http(method="POST", path="/get_forward_msg")
def get_forward_msg(message_id: str):
    return {
        "message_id": message_id
    }


@bot_http(method="POST", path="/get_group_msg_history")
def get_group_msg_history(group_id: str, message_seq: int, count=20):
    return {
        "group_id": group_id,
        "message_seq": message_seq,
        "count": count
    }
