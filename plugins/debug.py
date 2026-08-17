import asyncio
import base64
import json
import random
import time
from collections import deque
from pathlib import Path
from typing import Any, Optional

import a2s
import requests

from configs import config
from plugins.gpt import gpt_censor
from plugins.others.weibo import get_comments, get_save_old_otaku
from toogle.adapter import bot_send_message
from toogle.economy import give_balance
from toogle.logger import logger
from toogle.message import AtAll, ForwardMessage, Image, MessageChain, Plain
from toogle.message_handler import MessageHandler, MessagePack, WaitCommandHandler
from toogle.utils import is_admin, modify_json_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _configured_int_set(key: str) -> set[int]:
    raw = config.get(key, [])
    if isinstance(raw, str):
        raw = [item.strip() for item in raw.split(",") if item.strip()]
    if not isinstance(raw, (list, tuple, set)):
        return set()
    result: set[int] = set()
    for item in raw:
        try:
            result.add(int(item))
        except (TypeError, ValueError):
            continue
    return result


class DebugPlugin(MessageHandler):
    name = "调试用插件"
    trigger = r"^send_debug"
    readme = "管理员：send_debug，抓取近 24 小时指定微博内容"
    thread_limit = True
    admin_only = True

    async def ret(self, message: MessagePack):
        if not is_admin(message.member.id):
            return MessageChain.plain("无权限")
        res = []
        try:
            info = await asyncio.to_thread(
                get_save_old_otaku,
                time_limit=time.time() - 3600 * 24,
            )
        except Exception as exc:
            logger.warning("Debug Weibo request failed: %s", type(exc).__name__)
            return MessageChain.plain("微博请求失败")
        if not info:
            return None
        for create_time, msg, pic_url_list, detail_page, comments, key_info in info:
            res.append(
                MessageChain.create(
                    [
                        Plain(f"{key_info}\n{create_time}\n"),
                        Plain(f"{msg}\n{detail_page}"),
                    ]
                    + [Image(url=url) for url in pic_url_list]
                )
            )
            res.append(
                MessageChain.create(
                    [Plain(f"{comments[0]}条评论:\n\n" + "\n\n".join(comments[1]))]
                )
            )
        return ForwardMessage.get_quick_forward_message(
            res,
            people_name="拯救大龄单身二次元",
        )


class DebugPlugin2(MessageHandler):
    name = "调试用插件2"
    trigger = r"^看眼评论$"
    readme = "管理员：看眼评论，读取指定微博评论"
    thread_limit = True
    admin_only = True

    async def ret(self, message: MessagePack):
        res = []
        try:
            comments = await asyncio.to_thread(
                get_comments,
                1855501681,
                5126368613110753,
                limit=50,
                refresh_cookie=True,
                time_order=True,
            )
        except Exception as exc:
            logger.warning("Debug comment request failed: %s", type(exc).__name__)
            return MessageChain.plain("评论请求失败")
        res.append(MessageChain.plain(f"{comments[0]}条评论:\n\n"))
        for cmt in comments[1]:
            res.append(MessageChain.plain(cmt))
        return ForwardMessage.get_quick_forward_message(
            res,
            people_name="拯救大龄单身二次元",
        )


class RecallDebugPlugin(MessageHandler):
    name = "撤回debug"
    trigger = r"^自动撤回统计$"
    readme = "管理员：自动撤回统计"
    thread_limit = True
    admin_only = True
    recall_log_path = PROJECT_ROOT / "log" / "recall.log"

    async def ret(self, message: MessagePack):
        def read_total() -> int:
            if not self.recall_log_path.is_file():
                return 0
            total = 0
            with self.recall_log_path.open("r", encoding="utf-8") as log_file:
                for line in log_file:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 3:
                        continue
                    try:
                        total += int(parts[2])
                    except ValueError:
                        continue
            return total

        total = await asyncio.to_thread(read_total)
        if total <= 0:
            return MessageChain.plain("暂无撤回统计数据")

        with modify_json_file("debug_cnt") as d:
            false_judge = int(d.get("错判", 0))
            miss_judge = int(d.get("漏判", 0))
            miss_send = int(d.get("漏发", 0))

        precision = max(0, total - false_judge) / total
        recall = max(0, total - miss_judge) / total
        f1 = 0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)

        return MessageChain.plain(
            f"总撤回图片数: {total}\n"
            f"漏发数: {miss_send} ({miss_send / total * 100:.2f}%)\n"
            f"错判数: {false_judge}\n"
            f"漏判数: {miss_judge}\n"
            f"准确率: {precision:.2f}\n"
            f"召回率: {recall:.2f}\n"
            f"F1: {f1:.2f}"
        )


class CounterPlugin(MessageHandler):
    name = "调试计数器"
    trigger = r"^记录 (.+?) \d+$"
    readme = "管理员：记录 <错判|漏判|漏发> <数量>"
    thread_limit = True
    admin_only = True

    async def ret(self, message: MessagePack):
        content = message.message.asDisplay()

        name, num = content.split()[-2], int(content.split()[-1])
        if name not in ["错判", "漏判", "漏发"]:
            return MessageChain.plain("只能记录[错判]、[漏判]或[漏发]")

        with modify_json_file("debug_cnt") as d:
            if name not in d:
                d[name] = 0
            d[name] += num

        return MessageChain.plain(f"{name} 计数器: {d[name]}")


class DarkstarServerPing(MessageHandler):
    name = "Stormworks暗星服务器状态查询"
    trigger = r"^暗星$"
    readme = "Stormworks暗星服务器状态查询"
    interval = 10

    async def ret(self, message: MessagePack) -> MessageChain:
        host = str(config.get("DARKSTAR_SERVER_HOST", "")).strip()
        configured_port = str(config.get("DARKSTAR_SERVER_PORT", "")).strip()
        if not host or not configured_port:
            return MessageChain.plain("暗星服务器未配置", no_interval=True)
        try:
            port = int(configured_port)
        except ValueError:
            return MessageChain.plain("暗星服务器配置无效", no_interval=True)
        try:
            a2s_info = await asyncio.to_thread(
                a2s.info,
                (host, port),
                timeout=3,
                encoding="utf8",
            )
        except Exception:
            return MessageChain.plain("暗星服务器请求错误", no_interval=True)

        text = (
            "暗星服务器当前状态\n"
            f"人数：{a2s_info.player_count}/{a2s_info.max_players}\n"
            f"北京延迟：{a2s_info.ping * 1000:.2f}ms"
        )
        return MessageChain.plain(text)


class WitsAndWagers(MessageHandler):
    name = "猜来猜趣简化版"
    trigger = r"^/clcq"
    readme = "/clcq 随机出题；/clcq <编号> 查看答案"
    question_path = PROJECT_ROOT / "data" / "wnw.data"

    async def ret(self, message: MessagePack) -> MessageChain:
        try:
            lines = await asyncio.to_thread(
                self.question_path.read_text,
                encoding="utf-8",
            )
        except OSError:
            return MessageChain.plain("猜来猜趣题库不可用")
        data = lines.splitlines()
        question_count = len(data) // 2
        if question_count == 0:
            return MessageChain.plain("猜来猜趣题库为空")

        cmd = message.message.asDisplay().strip()
        if cmd == "/clcq":
            random_index = random.randrange(question_count)
            if not bot_send_message(
                message,
                f"问题{random_index}:\n{data[random_index * 2]}",
            ):
                return MessageChain.plain("题目发送失败")
            try:
                delay = max(0.0, float(config.get("WNW_ANSWER_DELAY_SECONDS", 90)))
            except (TypeError, ValueError):
                delay = 90
            await asyncio.sleep(delay)
            return MessageChain.plain(
                f"问题{random_index}答案:\n{data[random_index * 2 + 1]}"
            )

        try:
            index = int(cmd.split(maxsplit=1)[1])
            if index < 0 or index >= question_count:
                raise IndexError
            return MessageChain.plain(f"问题{index}答案:\n{data[index * 2 + 1]}")
        except (IndexError, ValueError):
            return MessageChain.plain("参数错误")


class PoliticsOrNot(MessageHandler):
    name = "政治内容检测调试"
    trigger = r"^这个政不政"
    readme = "管理员：这个政不政 <内容>"
    thread_limit = True
    admin_only = True

    async def ret(self, message: MessagePack):
        message_content = message.message.asDisplay()[5:].strip()
        if not message_content:
            return MessageChain.plain("没有内容")
        try:
            score, content, _ = await asyncio.to_thread(gpt_censor, [message_content])
            return MessageChain.plain(
                f"分数: {score}, 敏感内容: {content}",
                quote=message.as_quote(),
            )
        except Exception as exc:
            logger.warning("Debug censor request failed: %s", type(exc).__name__)
            return MessageChain.plain("内容检测失败", quote=message.as_quote())


class AsyncDebug(MessageHandler):
    name = "异步等待测试"
    trigger = r"^async$"
    readme = "管理员：等待同一群成员发送 11111"
    admin_only = True

    async def ret(self, message: MessagePack) -> MessageChain | None:
        if not is_admin(message.member.id):
            return MessageChain.plain("无权限")
        if message.message_type != "group":
            return MessageChain.plain("仅支持群聊")
        start_time = time.time()
        if not bot_send_message(message, "测试消息"):
            return MessageChain.plain("测试消息发送失败")
        wait_handler = WaitCommandHandler(
            message.group.id,
            message.member.id,
            r"11111",
            start_time=start_time,
            timeout=5,
        )
        ret = await wait_handler.run()
        if ret:
            return MessageChain.plain(ret.message.asDisplay())
        else:
            return MessageChain.plain("超时")


class ToogleWorldDebug(MessageHandler):
    name = "ToogleWorld日志调试"
    trigger = r"^toogleworlddebug$"
    readme = "管理员：读取 ToogleWorld 日志最后 20 行"
    admin_only = True

    async def ret(self, message: MessagePack) -> MessageChain | None:
        if not is_admin(message.member.id):
            return MessageChain.plain("无权限")
        configured_path = str(config.get("TOOGLEWORLD_LOG_PATH", "")).strip()
        if not configured_path:
            return MessageChain.plain("未配置 ToogleWorld 日志路径")
        log_path = Path(configured_path).expanduser()

        def read_tail() -> str:
            with log_path.open("r", encoding="utf-8", errors="replace") as log_file:
                return "".join(deque(log_file, maxlen=20))

        try:
            content = await asyncio.to_thread(read_tail)
        except OSError:
            return MessageChain.plain("ToogleWorld 日志不可用")
        return MessageChain.plain(content or "ToogleWorld 日志为空")


class gbLuckyPocket(MessageHandler):
    name = "gb红包"
    trigger = r"^(发gb红包|领gb红包)"
    readme = "管理员发gb红包 <总量> <数量> <留言>；群成员领gb红包"

    async def ret(self, message: MessagePack) -> MessageChain | None:
        msg = message.message.asDisplay()
        if message.message_type != "group":
            return MessageChain.plain("GB红包仅支持群聊")
        group_id = str(message.group.id)
        if msg.startswith("发gb红包"):
            if not is_admin(message.member.id):
                return MessageChain.plain("无权限")
            try:
                _, total, num, m = msg.split(" ", 3)
                total = int(total)
                num = int(num)

                if total <= 0 or num <= 0:
                    return MessageChain.plain("总量和数量必须为正整数")
                if total < num:
                    return MessageChain.plain(f"总量 {total} 小于数量 {num}")

                points = sorted(random.sample(range(1, total), num - 1))
                points = [0] + points + [total]
                pockets = [points[i + 1] - points[i] for i in range(num)]

                with modify_json_file("gbLuckyPocket") as f:
                    f[group_id] = {
                        "index": 0,
                        "msg": m,
                        "members": [],
                        "member_ids": [],
                        "pockets": pockets,
                    }

                return MessageChain.create(
                    [AtAll(), Plain(f"发gb了！\n{m}\n输入'领gb红包'来领取！")]
                )
            except (TypeError, ValueError):
                return MessageChain.plain("格式：发gb红包 <总量> <数量> <留言>")
        else:
            with modify_json_file("gbLuckyPocket") as f:
                if group_id not in f:
                    return
                data = f[group_id]
                index = int(data.get("index", 0))
                pockets = data.get("pockets") or []
                if index >= len(pockets):
                    return
                member_id = str(message.member.id)
                member_name = message.member.name or member_id
                member_ids = data.setdefault("member_ids", [])
                members = data.setdefault("members", [])
                if member_id in {str(item) for item in member_ids} or member_name in {
                    item[0] for item in members if isinstance(item, (list, tuple)) and item
                }:
                    return MessageChain.plain("你已经领过了", quote=message.as_quote())

                amount = pockets[index]
                data["index"] += 1
                member_ids.append(member_id)
                members.append([member_name, amount])
                finished = data["index"] >= len(pockets)
                luckiest_member = max(members, key=lambda item: item[1]) if finished else None
                pocket_message = str(data.get("msg") or "")

            await asyncio.to_thread(give_balance, message.member.id, amount)
            claim = MessageChain.plain(
                f"{pocket_message}\n你领取了 {amount} GB",
                quote=message.as_quote(),
            )
            if not finished:
                return claim
            if not bot_send_message(message, claim):
                return MessageChain.plain("红包领取成功，但领取消息发送失败")
            return MessageChain.create([
                AtAll(),
                Plain(
                    f"{pocket_message}\nGB红包已被领完～\n"
                    f"运气王是 {luckiest_member[0]} ({luckiest_member[1]} GB)"
                ),
            ])


class TooglePicGen(MessageHandler):
    name = "TooglePicGen"
    trigger = r"^土狗生图"
    readme = "土狗生图 <描述>，可附参考图片"

    async def ret(self, message: MessagePack) -> MessageChain | None:
        allowed_groups = _configured_int_set("TOOGLEPICGEN_GROUP_LIST")
        if message.group.id not in allowed_groups and not is_admin(message.member.id):
            if not allowed_groups:
                return MessageChain.plain("生图可用群未配置")
            return MessageChain.plain("只有指定群能够使用")

        pic_prompt = "".join(
            str(item) for item in message.message.get(Plain)
        ).replace("土狗生图", "").strip()
        if not pic_prompt:
            return MessageChain.plain("请输入生图描述", quote=message.as_quote())
        try:
            pic_refer = await asyncio.to_thread(
                lambda: [item.getBase64() for item in message.message.get(Image)]
            )
        except Exception as exc:
            logger.warning("TooglePicGen reference image failed: %s", type(exc).__name__)
            return MessageChain.plain("参考图片读取失败", quote=message.as_quote())

        if not bot_send_message(
            message,
            MessageChain.create([message.as_quote(), Plain("正在生成中")])
        ):
            return MessageChain.plain("生成状态发送失败", quote=message.as_quote())

        start_time = time.time()
        try:
            res = await asyncio.to_thread(
                TooglePicGen.run_generation_until_done,
                pic_prompt,
                reference_image_base64_list=pic_refer,
                interval=15,
                request_timeout=600,
                timeout=3600,
            )
            image_base64 = TooglePicGen.parse_generation_result_image_base64(res)
        except Exception as exc:
            logger.warning("TooglePicGen request failed: %s", type(exc).__name__)
            return MessageChain.plain("图片生成失败", quote=message.as_quote())

        res_img = Image(base64=image_base64)
        use_time = time.time() - start_time
        return MessageChain([
            message.as_quote(),
            res_img,
            Plain(f"用时 {use_time:.2f}sec"),
        ])

    REQUEST_TIMEOUT_SECONDS = 60
    POLL_INTERVAL_SECONDS = 5
    POLL_TIMEOUT_SECONDS = 1800

    @staticmethod
    def auth_headers(token: Optional[str] = None) -> dict[str, str]:
        actual_token = str(
            token
            if token is not None
            else config.get("TOOGLEPICGEN_ACCESS_TOKEN", "")
        ).strip()
        if not actual_token:
            raise RuntimeError("Missing TOOGLEPICGEN_ACCESS_TOKEN")
        return {
            "Authorization": f"Bearer {actual_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def api_base_url(base_url: Optional[str] = None) -> str:
        actual_base_url = str(
            base_url
            if base_url is not None
            else config.get("TOOGLEPICGEN_BASE_URL", "")
        ).strip()
        if not actual_base_url:
            raise RuntimeError("Missing TOOGLEPICGEN_BASE_URL")
        return actual_base_url.rstrip("/")


    @staticmethod
    def _strip_data_url_prefix(value: str) -> tuple[bytes, str]:
        cleaned = value.strip()
        mime_type = "image/png"
        if cleaned.startswith("data:") and ";base64," in cleaned:
            prefix, b64 = cleaned.split(";base64,", 1)
            mime_type = prefix[5:] or mime_type
            cleaned = b64
        return base64.b64decode(cleaned), mime_type


    @staticmethod
    def submit_generation(
        prompt: str,
        *,
        reference_image_base64_list: Optional[list[str]] = None,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        actual_base_url = TooglePicGen.api_base_url(base_url)
        submit_url = f"{actual_base_url}/api/generations"
        if reference_image_base64_list:
            multipart_headers = {
                "Authorization": TooglePicGen.auth_headers(token)["Authorization"]
            }
            files = []
            for index, item in enumerate(reference_image_base64_list, start=1):
                raw, mime_type = TooglePicGen._strip_data_url_prefix(item)
                extension = {
                    "image/png": ".png",
                    "image/jpeg": ".jpg",
                    "image/webp": ".webp",
                    "image/gif": ".gif",
                }.get(mime_type, ".bin")
                files.append(
                    (
                        "reference_images",
                        (f"reference_{index}{extension}", raw, mime_type),
                    )
                )
            response = requests.post(
                submit_url,
                headers=multipart_headers,
                data={"description": prompt},
                files=files,
                timeout=timeout,
            )
        else:
            response = requests.post(
                submit_url,
                headers=TooglePicGen.auth_headers(token),
                json={"description": prompt},
                timeout=timeout,
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Submit response must be a JSON object.")
        return payload


    @staticmethod
    def poll_generation_job(
        generation_job_id: str,
        *,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        interval: int = POLL_INTERVAL_SECONDS,
        request_timeout: int = REQUEST_TIMEOUT_SECONDS,
        timeout: int = POLL_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        actual_base_url = TooglePicGen.api_base_url(base_url)
        poll_url = f"{actual_base_url}/api/generation-jobs/{generation_job_id}"
        deadline = time.time() + timeout

        while True:
            if time.time() > deadline:
                raise TimeoutError(f"Polling timed out after {timeout} seconds.")

            response = requests.get(
                poll_url,
                headers=TooglePicGen.auth_headers(token),
                timeout=request_timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("Poll response must be a JSON object.")

            status = str(payload.get("status", "")).strip().lower()
            if status in {"completed", "failed"}:
                return payload

            time.sleep(interval)


    @staticmethod
    def run_generation_until_done(
        prompt: str,
        *,
        reference_image_base64_list: Optional[list[str]] = None,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        interval: int = POLL_INTERVAL_SECONDS,
        request_timeout: int = REQUEST_TIMEOUT_SECONDS,
        timeout: int = POLL_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        accepted = TooglePicGen.submit_generation(
            prompt,
            reference_image_base64_list=reference_image_base64_list,
            base_url=base_url,
            token=token,
            timeout=request_timeout,
        )
        generation_job_id = str(accepted.get("generation_job_id", "")).strip()
        if not generation_job_id:
            raise RuntimeError(
                f"Missing generation_job_id in submit response: {json.dumps(accepted, ensure_ascii=False)}"
            )
        return TooglePicGen.poll_generation_job(
            generation_job_id,
            base_url=base_url,
            token=token,
            interval=interval,
            request_timeout=request_timeout,
            timeout=timeout,
        )


    @staticmethod
    def parse_generation_result_image_base64(payload: dict[str, Any]) -> str:
        generation_job_id = str(payload.get("generation_job_id", "")).strip()
        status = str(payload.get("status", "")).strip().lower()
        job_label = f"Generation job {generation_job_id}" if generation_job_id else "Generation job"

        if status == "failed":
            error = str(payload.get("error") or "unknown error").strip()
            raise RuntimeError(f"{job_label} failed: {error}")
        if status != "completed":
            raise RuntimeError(f"{job_label} is not completed: status={status or 'unknown'}")

        result_data_url = str(payload.get("result_data_url") or "").strip()
        if not result_data_url:
            raise RuntimeError(f"{job_label} completed but did not return result_data_url.")

        if result_data_url.startswith("data:") and ";base64," in result_data_url:
            _, image_base64 = result_data_url.split(";base64,", 1)
        else:
            image_base64 = result_data_url

        image_base64 = image_base64.strip()
        if not image_base64:
            raise RuntimeError(f"{job_label} completed but image base64 is empty.")
        return image_base64
