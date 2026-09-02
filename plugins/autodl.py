"""管理员使用的 AutoDL 容器实例 Pro API 插件。

The API client is deliberately kept independent from the message layer so its
request/response handling can be tested without a live AutoDL account.
"""

from __future__ import annotations

import asyncio
import json
import re
import shlex
from collections.abc import Callable, Mapping
from typing import Any, Optional

import requests

from configs import config
from toogle.logger import logger
from toogle.message import MessageChain
from toogle.message_handler import MessageHandler, MessagePack
from toogle.utils import is_admin


AUTODL_DEFAULT_BASE_URL = "https://api.autodl.com"
AUTODL_TIMEOUT = (5, 30)
_INSTANCE_UUID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "token",
    "secret",
    "credential",
    "private_key",
    "access_key",
)


class AutoDLError(RuntimeError):
    """An expected AutoDL configuration, transport, or API error."""


def _redact(value: Any, key: str = "") -> Any:
    """Remove credentials from API data before it can reach a chat message."""

    key_lower = key.lower()
    if any(part in key_lower for part in _SENSITIVE_KEY_PARTS):
        return "[已隐藏]"
    if isinstance(value, Mapping):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _json_text(value: Any, *, limit: int = 3500) -> str:
    rendered = json.dumps(_redact(value), ensure_ascii=False, indent=2, default=str)
    if len(rendered) > limit:
        return rendered[: limit - 16] + "\n...[已截断]"
    return rendered


def _non_empty(value: Any, field: str, *, max_length: int = 256) -> str:
    if not isinstance(value, str):
        raise AutoDLError(f"{field} 必须是文本")
    result = value.strip()
    if not result:
        raise AutoDLError(f"{field} 不能为空")
    if len(result) > max_length:
        raise AutoDLError(f"{field} 过长")
    return result


def _instance_uuid(value: Any) -> str:
    result = _non_empty(value, "instance_uuid", max_length=128)
    if not _INSTANCE_UUID_RE.fullmatch(result):
        raise AutoDLError("instance_uuid 格式无效")
    return result


def _page(value: Any, field: str, *, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise AutoDLError(f"{field} 必须是整数") from exc
    if result < 1 or result > 10000:
        raise AutoDLError(f"{field} 必须在 1 到 10000 之间")
    return result


class AutoDLClient:
    """Small synchronous client for the documented container instance API."""

    def __init__(
        self,
        *,
        requester: Optional[Callable[..., Any]] = None,
        timeout: tuple[float, float] = AUTODL_TIMEOUT,
    ) -> None:
        self.requester = requester or requests.request
        self.timeout = timeout

    @property
    def base_url(self) -> str:
        configured = str(config.get("AUTODL_API_BASE_URL", AUTODL_DEFAULT_BASE_URL)).strip()
        return (configured or AUTODL_DEFAULT_BASE_URL).rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[Mapping[str, Any]] = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        token = str(config.get("AUTODL_API_TOKEN", "")).strip()
        if not token:
            raise AutoDLError("AutoDL 未配置 AUTODL_API_TOKEN")
        headers = {
            "Accept": "application/json",
            "Authorization": token,
            "Content-Type": "application/json",
        }
        try:
            response = self.requester(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                params=dict(params) if params else None,
                json=dict(body) if body is not None else None,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise AutoDLError("AutoDL 网络请求失败") from exc
        except (TypeError, ValueError) as exc:
            raise AutoDLError("AutoDL 返回了无效响应") from exc

        if not isinstance(payload, Mapping):
            raise AutoDLError("AutoDL 返回了无效响应")
        if payload.get("code") != "Success":
            # Do not include msg: API errors can contain request data or secrets.
            raise AutoDLError(f"AutoDL 请求失败 (code={payload.get('code', 'unknown')})")
        return payload.get("data")

    def create(self, body: Mapping[str, Any]) -> Any:
        if not isinstance(body, Mapping):
            raise AutoDLError("创建参数必须是 JSON 对象")
        required_text = ("gpu_spec_uuid", "image_uuid")
        for field in required_text:
            _non_empty(body.get(field), field, max_length=128)
        try:
            gpu_amount = int(body.get("req_gpu_amount"))
            disk_size = int(body.get("expand_system_disk_by_gb"))
            cuda_version = int(body.get("cuda_v_from"))
        except (TypeError, ValueError) as exc:
            raise AutoDLError("req_gpu_amount、expand_system_disk_by_gb、cuda_v_from 必须是整数") from exc
        if not 1 <= gpu_amount <= 4:
            raise AutoDLError("req_gpu_amount 必须在 1 到 4 之间")
        if not 0 <= disk_size <= 500:
            raise AutoDLError("expand_system_disk_by_gb 必须在 0 到 500 之间")
        if cuda_version < 0:
            raise AutoDLError("cuda_v_from 不能为负数")

        clean = dict(body)
        clean["req_gpu_amount"] = gpu_amount
        clean["expand_system_disk_by_gb"] = disk_size
        clean["cuda_v_from"] = cuda_version
        if "data_center_list" in clean:
            centers = clean["data_center_list"]
            if not isinstance(centers, list) or any(not isinstance(item, str) for item in centers):
                raise AutoDLError("data_center_list 必须是字符串数组")
        for field in ("gpu_spec_uuid", "image_uuid", "instance_name", "start_command"):
            if field in clean and clean[field] is not None:
                clean[field] = _non_empty(clean[field], field, max_length=512)
        return self._request("POST", "/api/v1/dev/instance/pro/create", body=clean)

    def list_instances(self, page_index: Any = 1, page_size: Any = 20) -> Any:
        body = {
            "page_index": _page(page_index, "page_index", default=1),
            "page_size": _page(page_size, "page_size", default=20),
        }
        return self._request("POST", "/api/v1/dev/instance/pro/list", body=body)

    def status(self, instance_uuid: str) -> Any:
        instance_uuid = _instance_uuid(instance_uuid)
        return self._request(
            "GET",
            "/api/v1/dev/instance/pro/status",
            body={"instance_uuid": instance_uuid},
            params={"instance_uuid": instance_uuid},
        )

    def snapshot(self, instance_uuid: str) -> Any:
        instance_uuid = _instance_uuid(instance_uuid)
        return self._request(
            "GET",
            "/api/v1/dev/instance/pro/snapshot",
            body={"instance_uuid": instance_uuid},
            params={"instance_uuid": instance_uuid},
        )

    def power_on(self, instance_uuid: str, start_command: Optional[str] = None) -> Any:
        body: dict[str, Any] = {
            "instance_uuid": _instance_uuid(instance_uuid),
            "payload": "gpu",
        }
        if start_command:
            body["start_command"] = _non_empty(start_command, "start_command", max_length=512)
        return self._request("POST", "/api/v1/dev/instance/pro/power_on", body=body)

    def power_off(self, instance_uuid: str) -> Any:
        return self._request(
            "POST",
            "/api/v1/dev/instance/pro/power_off",
            body={"instance_uuid": _instance_uuid(instance_uuid)},
        )

    def release(self, instance_uuid: str) -> Any:
        return self._request(
            "POST",
            "/api/v1/dev/instance/pro/release",
            body={"instance_uuid": _instance_uuid(instance_uuid)},
        )

    def save_image(self, instance_uuid: str, image_name: str) -> Any:
        return self._request(
            "POST",
            "/api/v1/dev/instance/pro/image/save",
            body={
                "instance_uuid": _instance_uuid(instance_uuid),
                "image_name": _non_empty(image_name, "image_name", max_length=128),
            },
        )

    def list_images(self, page_index: Any = 1, page_size: Any = 20) -> Any:
        body = {
            "page_index": _page(page_index, "page_index", default=1),
            "page_size": _page(page_size, "page_size", default=20),
        }
        return self._request(
            "POST",
            "/api/v1/dev/instance/pro/image/private/list",
            body=body,
        )


def _help_text() -> str:
    return (
        "AutoDL 管理命令：\n"
        ".autodl list [页码] [每页数量]\n"
        ".autodl status <实例ID>\n"
        ".autodl snapshot <实例ID>\n"
        ".autodl create <JSON对象>\n"
        ".autodl on <实例ID> [开机命令]\n"
        ".autodl off <实例ID>\n"
        ".autodl release <实例ID> CONFIRM\n"
        ".autodl save-image <实例ID> <镜像名>\n"
        ".autodl images [页码] [每页数量]\n"
        "创建 JSON 至少包含 gpu_spec_uuid、image_uuid、cuda_v_from、"
        "req_gpu_amount、expand_system_disk_by_gb。"
    )


def _format_instances(data: Any) -> str:
    if not isinstance(data, Mapping):
        return _json_text(data)
    items = data.get("list", [])
    if not isinstance(items, list) or not items:
        return "实例列表为空"
    lines = ["实例列表："]
    for item in items[:50]:
        if not isinstance(item, Mapping):
            continue
        lines.append(
            " | ".join(
                [
                    str(item.get("uuid", "-")),
                    str(item.get("name", "-")),
                    f"状态={item.get('status', '-')}",
                    f"GPU={item.get('gpu_spec_uuid', '-')}",
                    f"区域={item.get('region_name') or item.get('region_sign', '-')}",
                ]
            )
        )
    return "\n".join(lines)


def _format_images(data: Any) -> str:
    if not isinstance(data, Mapping):
        return _json_text(data)
    items = data.get("list", [])
    if not isinstance(items, list) or not items:
        return "私有镜像列表为空"
    lines = ["私有镜像列表："]
    for item in items[:50]:
        if not isinstance(item, Mapping):
            continue
        lines.append(
            f"{item.get('image_uuid', '-')} | {item.get('name', '-')} | "
            f"状态={item.get('status', '-')} | 大小={item.get('image_size', '-')}"
        )
    return "\n".join(lines)


class AutoDL(MessageHandler):
    name = "AutoDL实例管理"
    trigger = r"^\.autodl(?:\s|$)"
    readme = "管理员：创建、查询、开关机、释放 AutoDL 容器实例和管理私有镜像"
    admin_only = True
    ignore_quote = True
    thread_limit = True

    def __init__(self, client: Optional[AutoDLClient] = None) -> None:
        self.client = client or AutoDLClient()

    @staticmethod
    def _reply(message: MessagePack, text: str, *, error: bool = False) -> MessageChain:
        return MessageChain.plain(
            text,
            quote=message.as_quote(),
            no_charge=error,
            no_interval=error,
        )

    def _dispatch(self, command: str) -> str:
        parts = command.split(maxsplit=1)
        operation = parts[0].lower() if parts else "help"
        args = parts[1].strip() if len(parts) > 1 else ""
        if operation in {"help", "?"}:
            return _help_text()
        if operation == "list":
            values = shlex.split(args) if args else []
            if len(values) > 2:
                raise AutoDLError("list 参数过多")
            return _format_instances(self.client.list_instances(*(values or [1, 20])))
        if operation in {"images", "image-list"}:
            values = shlex.split(args) if args else []
            if len(values) > 2:
                raise AutoDLError("images 参数过多")
            return _format_images(self.client.list_images(*(values or [1, 20])))
        if operation in {"status", "snapshot", "off", "release"}:
            values = shlex.split(args) if args else []
            if not values:
                raise AutoDLError(f"{operation} 需要实例 ID")
            if operation == "status":
                if len(values) != 1:
                    raise AutoDLError("用法：.autodl status <实例ID>")
                return f"实例状态：{self.client.status(values[0])}"
            if operation == "snapshot":
                if len(values) != 1:
                    raise AutoDLError("用法：.autodl snapshot <实例ID>")
                return _json_text(self.client.snapshot(values[0]))
            if operation == "off":
                if len(values) != 1:
                    raise AutoDLError("用法：.autodl off <实例ID>")
                self.client.power_off(values[0])
                return f"实例 {values[0]} 已提交关机请求"
            if len(values) != 2 or values[1] != "CONFIRM":
                raise AutoDLError("释放实例是不可逆操作，请使用 `.autodl release <实例ID> CONFIRM`")
            self.client.release(values[0])
            return f"实例 {values[0]} 已提交释放请求"
        if operation == "on":
            instance_id, separator, start_command = args.partition(" ")
            if not instance_id:
                raise AutoDLError("用法：.autodl on <实例ID> [开机命令]")
            self.client.power_on(instance_id, start_command.strip() if separator else None)
            return f"实例 {instance_id} 已提交开机请求"
        if operation in {"save-image", "save_image"}:
            values = shlex.split(args) if args else []
            if len(values) < 2:
                raise AutoDLError("用法：.autodl save-image <实例ID> <镜像名>")
            self.client.save_image(values[0], " ".join(values[1:]))
            return f"实例 {values[0]} 已提交保存镜像请求"
        if operation == "create":
            if not args:
                raise AutoDLError("用法：.autodl create <JSON对象>")
            try:
                body = json.loads(args)
            except json.JSONDecodeError as exc:
                raise AutoDLError("create 参数必须是合法 JSON 对象") from exc
            if not isinstance(body, Mapping):
                raise AutoDLError("create 参数必须是 JSON 对象")
            instance_id = self.client.create(body)
            return f"实例创建成功：{instance_id}"
        raise AutoDLError(f"未知操作：{operation}\n{_help_text()}")

    async def ret(self, message: MessagePack) -> Optional[MessageChain]:
        if not is_admin(message.member.id):
            return self._reply(message, "无权限", error=True)
        content = message.message.asDisplay().strip()
        command = content[len(".autodl") :].strip()
        try:
            result = await asyncio.to_thread(self._dispatch, command)
        except AutoDLError as exc:
            return self._reply(message, str(exc), error=True)
        except Exception:
            logger.exception("AutoDL plugin failed")
            return self._reply(message, "AutoDL 请求失败，请稍后查看日志", error=True)
        return self._reply(message, result)
