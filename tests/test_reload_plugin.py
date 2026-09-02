import unittest
from types import SimpleNamespace
from unittest.mock import patch

from plugins.admin import ReloadPlugins
from toogle.message import Group, Member, MessageChain
from toogle.message_handler import MessagePack


def make_pack(member_id: int = 200) -> MessagePack:
    return MessagePack(
        id=1,
        message=MessageChain.plain(".reload"),
        group=Group(100, "fixture"),
        member=Member(member_id, "member"),
        quote=None,
    )


class ReloadPluginsTest(unittest.IsolatedAsyncioTestCase):
    def test_command_is_exact_and_admin_only(self):
        plugin = ReloadPlugins()
        self.assertEqual(plugin.trigger, r"^\.reload$")
        self.assertTrue(plugin.admin_only)
        self.assertTrue(plugin.is_trigger(".reload"))
        self.assertFalse(plugin.is_trigger(".reload admin"))

    async def test_non_admin_cannot_refresh(self):
        with patch("plugins.admin.is_admin", return_value=False), patch(
            "toogle.index.reload_plugins"
        ) as reload_plugins:
            result = await ReloadPlugins().ret(make_pack())

        self.assertIsNone(result)
        reload_plugins.assert_not_called()

    async def test_admin_refreshes_config_registry_and_schedules(self):
        report = SimpleNamespace(disabled=["disabled"], failed=[], duration_ms=1.0)
        calls = []

        with patch("plugins.admin.is_admin", return_value=True), patch(
            "configs.reload_config", side_effect=lambda: calls.append("config")
        ), patch(
            "toogle.index.reload_plugins",
            side_effect=lambda strict_core: calls.append("registry") or report,
        ), patch(
            "toogle.index.get_export_plugins", return_value=(1, 2, 3)
        ), patch(
            "toogle.index.get_active_plugins", return_value=(1,)
        ), patch(
            "toogle.index.get_schedule_plugins", return_value=(1, 2)
        ), patch(
            "adapter.schedule.register_schedules",
            side_effect=lambda: calls.append("schedules"),
        ):
            result = await ReloadPlugins().ret(make_pack())

        self.assertEqual(calls, ["config", "registry", "schedules"])
        self.assertIn("普通插件：3", result.asDisplay())
        self.assertIn("主动插件：1", result.asDisplay())
        self.assertIn("定时插件：2", result.asDisplay())
        self.assertIn("禁用插件：1", result.asDisplay())

    async def test_refresh_failure_returns_safe_error(self):
        with patch("plugins.admin.is_admin", return_value=True), patch(
            "configs.reload_config", side_effect=ValueError("fixture secret")
        ):
            result = await ReloadPlugins().ret(make_pack())

        self.assertIn("插件刷新失败", result.asDisplay())
        self.assertNotIn("fixture secret", result.asDisplay())
        self.assertTrue(result.no_charge)
        self.assertTrue(result.no_interval)

    async def test_schedule_failure_reports_registry_was_refreshed(self):
        report = SimpleNamespace(disabled=[], failed=[], duration_ms=1.0)
        with patch("plugins.admin.is_admin", return_value=True), patch(
            "configs.reload_config"
        ), patch(
            "toogle.index.reload_plugins", return_value=report
        ), patch(
            "toogle.index.get_export_plugins", return_value=()
        ), patch(
            "toogle.index.get_active_plugins", return_value=()
        ), patch(
            "toogle.index.get_schedule_plugins", return_value=()
        ), patch(
            "adapter.schedule.register_schedules", side_effect=RuntimeError("fixture")
        ):
            result = await ReloadPlugins().ret(make_pack())

        self.assertIn("registry 已刷新", result.asDisplay())
        self.assertIn("定时任务同步失败", result.asDisplay())
        self.assertTrue(result.no_interval)


if __name__ == "__main__":
    unittest.main()
