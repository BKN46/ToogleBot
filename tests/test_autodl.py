import asyncio
import unittest
from unittest.mock import Mock, patch

from configs import config
from plugins.autodl import AutoDL, AutoDLClient, AutoDLError, _json_text
from toogle.message import Group, Member, MessageChain
from toogle.message_handler import MessagePack


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self.payload


def make_pack(text: str, member_id: int = 200) -> MessagePack:
    return MessagePack(
        1,
        MessageChain.plain(text),
        Group(100, "fixture"),
        Member(member_id, "member"),
        None,
    )


class AutoDLClientTest(unittest.TestCase):
    def test_get_action_uses_query_parameter_and_redacts_snapshot(self):
        calls = []

        def requester(*args, **kwargs):
            calls.append((args, kwargs))
            return FakeResponse(
                {
                    "code": "Success",
                    "data": {"root_password": "secret", "jupyter_token": "token", "status": "running"},
                }
            )

        with patch.dict(config, {"AUTODL_API_TOKEN": "fixture-token"}, clear=False):
            client = AutoDLClient(requester=requester)
            snapshot = client.snapshot("pro-fixture")

        self.assertEqual(calls[0][0][:2], ("GET", "https://api.autodl.com/api/v1/dev/instance/pro/snapshot"))
        self.assertEqual(calls[0][1]["params"], {"instance_uuid": "pro-fixture"})
        self.assertEqual(calls[0][1]["json"], {"instance_uuid": "pro-fixture"})
        self.assertEqual(snapshot["status"], "running")
        self.assertNotIn("secret", _json_text(snapshot))
        self.assertNotIn('"token"', _json_text(snapshot))

    def test_non_success_code_is_not_treated_as_success(self):
        with patch.dict(config, {"AUTODL_API_TOKEN": "fixture-token"}, clear=False):
            client = AutoDLClient(requester=lambda *args, **kwargs: FakeResponse({"code": "BadRequest", "msg": "secret"}))
            with self.assertRaises(AutoDLError) as raised:
                client.status("pro-fixture")
        self.assertNotIn("secret", str(raised.exception))

    def test_all_documented_actions_use_expected_endpoints(self):
        calls = []

        def requester(method, url, **kwargs):
            calls.append((method, url, kwargs))
            return FakeResponse({"code": "Success", "data": None})

        create_body = {
            "gpu_spec_uuid": "v-48g",
            "image_uuid": "image-fixture",
            "req_gpu_amount": 1,
            "expand_system_disk_by_gb": 0,
            "cuda_v_from": 113,
        }
        with patch.dict(config, {"AUTODL_API_TOKEN": "fixture-token"}, clear=False):
            client = AutoDLClient(requester=requester)
            client.create(create_body)
            client.snapshot("pro-fixture")
            client.status("pro-fixture")
            client.list_instances()
            client.power_on("pro-fixture", "sleep 1")
            client.power_off("pro-fixture")
            client.release("pro-fixture")
            client.save_image("pro-fixture", "fixture image")
            client.list_images()

        self.assertEqual(
            [(method, url.removeprefix("https://api.autodl.com")) for method, url, _ in calls],
            [
                ("POST", "/api/v1/dev/instance/pro/create"),
                ("GET", "/api/v1/dev/instance/pro/snapshot"),
                ("GET", "/api/v1/dev/instance/pro/status"),
                ("POST", "/api/v1/dev/instance/pro/list"),
                ("POST", "/api/v1/dev/instance/pro/power_on"),
                ("POST", "/api/v1/dev/instance/pro/power_off"),
                ("POST", "/api/v1/dev/instance/pro/release"),
                ("POST", "/api/v1/dev/instance/pro/image/save"),
                ("POST", "/api/v1/dev/instance/pro/image/private/list"),
            ],
        )
        self.assertEqual(calls[4][2]["json"]["start_command"], "sleep 1")

    def test_create_validates_required_and_range_fields(self):
        client = AutoDLClient(requester=Mock())
        with self.assertRaises(AutoDLError):
            client.create({"gpu_spec_uuid": "v-48g"})
        with self.assertRaises(AutoDLError):
            client.create(
                {
                    "gpu_spec_uuid": "v-48g",
                    "image_uuid": "image-x",
                    "req_gpu_amount": 5,
                    "expand_system_disk_by_gb": 0,
                    "cuda_v_from": 113,
                }
            )


class AutoDLPluginTest(unittest.IsolatedAsyncioTestCase):
    async def test_non_admin_cannot_call_client(self):
        client = Mock()
        with patch("plugins.autodl.is_admin", return_value=False):
            result = await AutoDL(client).ret(make_pack(".autodl list"))
        client.list_instances.assert_not_called()
        self.assertTrue(result.asDisplay().endswith("无权限"))
        self.assertTrue(result.no_charge)

    async def test_admin_commands_are_offloaded_and_dispatch(self):
        client = Mock()
        client.list_instances.return_value = {
            "list": [{"uuid": "pro-fixture", "name": "demo", "status": "running", "gpu_spec_uuid": "v-48g"}]
        }
        with patch("plugins.autodl.is_admin", return_value=True):
            result = await AutoDL(client).ret(make_pack(".autodl list"))
        client.list_instances.assert_called_once_with(1, 20)
        self.assertIn("pro-fixture", result.asDisplay())

    async def test_release_requires_confirmation(self):
        client = Mock()
        with patch("plugins.autodl.is_admin", return_value=True):
            result = await AutoDL(client).ret(make_pack(".autodl release pro-fixture"))
        client.release.assert_not_called()
        self.assertIn("不可逆", result.asDisplay())
        self.assertTrue(result.no_interval)


if __name__ == "__main__":
    unittest.main()
