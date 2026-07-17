import requests

import configs

HOST = configs.config.get("HTTP_HOST", "127.0.0.1")
PORT = configs.config.get("HTTP_PORT", "3457")
TOKEN = configs.config.get("HTTP_TOKEN", "")


def bot_http(method="POST", path="/"):
    def decorator(func):
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
                timeout=(3, 10),
            )
            res.raise_for_status()
            return res.json()

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


@bot_http(method="POST", path="/upload_group_file")
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
