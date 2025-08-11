from contextlib import contextmanager
import os
import sys
from typing import Union
import requests

# from toogle.nonebot2_adapter import bot_exec

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
# sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# from toogle.nonebot2_adapter import bot_exec
from toogle.configs import config


http_path = lambda path: f"http://{config['MIRAI_HOST']}:{config['MIRAI_HTTP_PORT']}{path}"


def get_http_session():
    res = requests.post(http_path("/verify"), json={"verifyKey": config["VERIFY_KEY"]})
    try:
        return res.json()['session']
    except Exception as e:
        raise Exception(f"Failed to verify: {res.text}")
    

def bind_http_session(session_key, qq_id):
    data = {
        "sessionKey": session_key,
        "qq": int(qq_id),
    }
    res = requests.post(http_path("/bind"), json=data)
    if res.json()["code"] != 0:
        raise Exception(f"Failed to bind session: {res.text}")


def release_http_session(session_key, qq_id):
    data = {
        "sessionKey": session_key,
        "qq": int(qq_id),
    }
    res = requests.post(http_path("/release"), json=data)
    if res.json()["code"] != 0:
        raise Exception(f"Failed to bind session: {res.text}")

    
@contextmanager
def with_temp_verify(with_bind=False):
    session_key = get_http_session()
    if with_bind:
        bind_http_session(session_key, config["MIRAI_QQ"][0])
        yield session_key
        release_http_session(session_key, config["MIRAI_QQ"][0])
    else:
        yield session_key


def send_group_file(group, file_name, file: Union[str, bytes], upload_path=""):
    with with_temp_verify() as session_key:
        if isinstance(file, str):
            file = open(file, "rb").read()
        files = {
            "sessionKey": (None, session_key),
            "type": (None, "group"),
            "target": (None, int(group)),
            "path": (None, upload_path),
            "file": (file_name, file),
        }
        res = requests.post(http_path("/file/upload"), files=files)
        if res.json()["code"] != 0:
            raise Exception(f"Failed to send file: {res.text}")


def send_group_msg(group, msg):
    with with_temp_verify() as session_key:
        data = {
            "sessionKey": session_key,
            "target": int(group),
            "messageChain": msg,
        }
        res = requests.post(http_path("/sendGroupMessage"), json=data)
        if res.json()["code"] != 0:
            raise Exception(f"Failed to send message: {res.text}")


def recall_msg(target, msg_id, ignore_exception=False):
    with with_temp_verify() as session_key:
        data = {
            "sessionKey": session_key,
            "target": int(target),
            "messageId": int(msg_id),
        }
        res = requests.post(http_path("/recall"), json=data)
        if res.json()["code"] != 0:
            if res.json()["code"] == 10:
                return False
            if not ignore_exception:
                raise Exception(f"Failed to recall message: {res.text}")
            return False
        return True


def accept_group_invite(event_id, from_id, group_id, ignore_exception=False):
    with with_temp_verify() as session_key:
        data = {
            "sessionKey": session_key,
            "eventId": int(event_id),
            "fromId": int(from_id),
            "groupId": int(group_id),
            "operate": 0,
            "message": "",
        }
        res = requests.post(http_path("/resp/botInvitedJoinGroupRequestEvent"), json=data)
        if res.json()["code"] != 0:
            if res.json()["code"] == 10:
                return False
            if not ignore_exception:
                raise Exception(f"Failed to recall message: {res.text}")
            return False
        return True


def quit_group_chat(group_id, ignore_exception=False):
    with with_temp_verify() as session_key:
        data = {
            "sessionKey": session_key,
            "target": int(group_id),
        }
        res = requests.post(http_path("/quit"), json=data)
        if res.json()["code"] != 0:
            if res.json()["code"] == 10:
                return False
            if not ignore_exception:
                raise Exception(f"Failed to recall message: {res.text}")
            return False
        return True


def mute_member(target, member_id, mute_time, ignore_exception=False):
    with with_temp_verify() as session_key:
        data = {
            "sessionKey": session_key,
            "target": int(target),
            "memberId": int(member_id),
            "time": int(mute_time),
        }
        res = requests.post(http_path("/mute"), json=data)
        if res.json()["code"] != 0:
            if res.json()["code"] == 10:
                return False
            if not ignore_exception:
                raise Exception(f"Failed to recall message: {res.text}")
            return False
        return True


# async def send_group_nudge(group, target):
#     await bot_exec("send_nudge", target=int(target), subject=int(group), kind="Group")


def send_temp_message():
    pass
