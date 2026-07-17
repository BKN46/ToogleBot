import asyncio
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import toogle.index as registry
from plugins.meta import GetHelp
from toogle.adapter import PluginWrapper
from toogle.message import ForwardMessage, Group, Member, MessageChain
from toogle.message_handler import MessageHandler, MessagePack


class PluginRegistryTest(unittest.TestCase):
    def test_discovery_is_sorted_and_top_level_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "zeta.py").touch()
            (root / "alpha.py").touch()
            (root / "__init__.py").touch()
            (root / "nested").mkdir()
            (root / "nested" / "ignored.py").touch()
            self.assertEqual(
                registry.discover_plugin_modules(root),
                ["alpha", "zeta"],
            )

    def test_only_collects_classes_defined_by_module(self):
        module = types.ModuleType("plugins.registry_fixture")

        class LocalPlugin(MessageHandler):
            pass

        class ImportedPlugin(MessageHandler):
            pass

        LocalPlugin.__module__ = module.__name__
        ImportedPlugin.__module__ = "plugins.somewhere_else"
        module.LocalPlugin = LocalPlugin
        module.ImportedPlugin = ImportedPlugin

        built = registry._RegistryBuild()
        report = registry.PluginLoadReport()
        registry._collect_module_plugins(module, built, report, set())

        self.assertEqual(
            [wrapper.plugin_class for wrapper in built.normal],
            [LocalPlugin],
        )
        self.assertFalse(report.failed)

    def test_constructor_failure_is_isolated(self):
        module = types.ModuleType("plugins.broken_fixture")

        class BrokenPlugin(MessageHandler):
            def __init__(self):
                raise RuntimeError("broken constructor")

        class HealthyPlugin(MessageHandler):
            pass

        BrokenPlugin.__module__ = module.__name__
        HealthyPlugin.__module__ = module.__name__
        module.BrokenPlugin = BrokenPlugin
        module.HealthyPlugin = HealthyPlugin

        built = registry._RegistryBuild()
        report = registry.PluginLoadReport()
        registry._collect_module_plugins(module, built, report, set())

        self.assertEqual(len(built.normal), 1)
        self.assertIs(built.normal[0].plugin_class, HealthyPlugin)
        self.assertEqual(len(report.failed), 1)
        self.assertEqual(report.failed[0].stage, "construct")

    def test_core_failure_keeps_previous_registry(self):
        sentinel = object()
        previous = list(registry.export_plugins)
        registry.export_plugins[:] = [sentinel]  # type: ignore[list-item]
        try:
            with patch.object(registry, "discover_plugin_modules", return_value=["meta"]), patch.object(
                registry,
                "_load_plugin_module",
                side_effect=RuntimeError("meta failed"),
            ):
                with self.assertRaises(registry.PluginLoadError):
                    registry.load_plugins(strict_core=True)
            self.assertEqual(registry.export_plugins, [sentinel])
        finally:
            registry.export_plugins[:] = previous

    def test_help_reads_current_registry_provider(self):
        class FixturePlugin(MessageHandler):
            name = "fixture"
            trigger = r"^fixture$"
            readme = "fixture plugin"

        message = MessagePack(
            1,
            MessageChain.plain("/help"),
            Group(100, "group"),
            Member(200, "member"),
            None,
        )
        with patch.object(
            registry,
            "get_export_plugins",
            return_value=(PluginWrapper(FixturePlugin),),
        ):
            result = asyncio.run(GetHelp().ret(message))
        self.assertIsInstance(result.root[0], ForwardMessage)


if __name__ == "__main__":
    unittest.main()
