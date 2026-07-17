import importlib
import inspect
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Literal

from configs import config
from toogle.adapter import PluginWrapper
from toogle.logger import logger
from toogle.message_handler import ActiveHandler, MessageHandler
from toogle.scheduler import ScheduleModule


PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugins"
CORE_PLUGIN_MODULES = {"meta", "basic"}
NOT_INCLUDE_LIST: list[str] = []

export_plugins: list[PluginWrapper] = []
active_plugins: list[ActiveHandler] = []
schedule_plugins: list[ScheduleModule] = []
plugin_list: list[str] = []


@dataclass(frozen=True)
class PluginLoadIssue:
    module: str
    stage: Literal["import", "construct"]
    error: str
    plugin: str = ""


@dataclass
class PluginLoadReport:
    loaded: list[str] = field(default_factory=list)
    disabled: list[str] = field(default_factory=list)
    failed: list[PluginLoadIssue] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def core_failures(self) -> list[PluginLoadIssue]:
        return [
            issue
            for issue in self.failed
            if issue.module.rsplit(".", 1)[-1] in CORE_PLUGIN_MODULES
        ]


class PluginLoadError(RuntimeError):
    def __init__(self, report: PluginLoadReport) -> None:
        self.report = report
        detail = ", ".join(
            f"{issue.module}:{issue.plugin or issue.stage}={issue.error}"
            for issue in report.core_failures
        )
        super().__init__(f"core plugin loading failed: {detail}")


@dataclass
class _RegistryBuild:
    normal: list[PluginWrapper] = field(default_factory=list)
    active: list[ActiveHandler] = field(default_factory=list)
    scheduled: list[ScheduleModule] = field(default_factory=list)


last_load_report = PluginLoadReport()


def discover_plugin_modules(plugin_dir: Path = PLUGIN_DIR) -> list[str]:
    excluded = {Path(item).stem for item in NOT_INCLUDE_LIST}
    return [
        path.stem
        for path in sorted(plugin_dir.glob("*.py"), key=lambda item: item.name)
        if path.name != "__init__.py" and path.stem not in excluded
    ]


def _load_plugin_module(module_name: str, reload_module: bool) -> ModuleType:
    qualified_name = f"plugins.{module_name}"
    if reload_module and qualified_name in sys.modules:
        return importlib.reload(sys.modules[qualified_name])
    return importlib.import_module(qualified_name)


def _plugin_identifier(plugin_class: type) -> str:
    return f"{plugin_class.__module__}.{plugin_class.__qualname__}"


def _class_kind(plugin_class: type) -> str | None:
    if plugin_class is not MessageHandler and issubclass(plugin_class, MessageHandler):
        return "normal"
    if plugin_class is not ActiveHandler and issubclass(plugin_class, ActiveHandler):
        return "active"
    if plugin_class is not ScheduleModule and issubclass(plugin_class, ScheduleModule):
        return "scheduled"
    return None


def _collect_module_plugins(
    module: ModuleType,
    registry: _RegistryBuild,
    report: PluginLoadReport,
    seen: set[str],
) -> None:
    disabled = set(config.get("DISABLED_MODULE", []))
    for _, candidate in sorted(vars(module).items(), key=lambda item: item[0]):
        if not inspect.isclass(candidate) or candidate.__module__ != module.__name__:
            continue

        kind = _class_kind(candidate)
        if kind is None:
            continue

        identifier = _plugin_identifier(candidate)
        if identifier in seen:
            continue
        seen.add(identifier)

        if candidate.__name__ in disabled:
            report.disabled.append(identifier)
            continue

        try:
            if kind == "normal":
                registry.normal.append(PluginWrapper(candidate))
            elif kind == "active":
                registry.active.append(candidate())
            else:
                scheduled = candidate()
                registry.scheduled.append(scheduled)
                if scheduled.trigger:
                    registry.normal.append(PluginWrapper(candidate))
        except Exception as exc:
            report.failed.append(
                PluginLoadIssue(
                    module=module.__name__,
                    plugin=identifier,
                    stage="construct",
                    error=repr(exc),
                )
            )
            continue

        report.loaded.append(f"{kind}:{identifier}")


def _build_registry(reload_modules: bool) -> tuple[_RegistryBuild, PluginLoadReport]:
    started = time.monotonic()
    registry = _RegistryBuild()
    report = PluginLoadReport()
    seen: set[str] = set()

    modules = discover_plugin_modules()
    plugin_list[:] = [f"{name}.py" for name in modules]
    for module_name in modules:
        qualified_name = f"plugins.{module_name}"
        try:
            module = _load_plugin_module(module_name, reload_modules)
        except Exception as exc:
            report.failed.append(
                PluginLoadIssue(
                    module=qualified_name,
                    stage="import",
                    error=repr(exc),
                )
            )
            continue
        _collect_module_plugins(module, registry, report, seen)

    report.duration_ms = (time.monotonic() - started) * 1000
    return registry, report


def _publish_registry(registry: _RegistryBuild) -> None:
    export_plugins[:] = registry.normal
    active_plugins[:] = registry.active
    schedule_plugins[:] = registry.scheduled


def _log_report(report: PluginLoadReport, registry: _RegistryBuild) -> None:
    logger.info(
        "Plugin registry loaded: normal=%d active=%d scheduled=%d disabled=%d "
        "failed=%d duration=%.2fms",
        len(registry.normal),
        len(registry.active),
        len(registry.scheduled),
        len(report.disabled),
        len(report.failed),
        report.duration_ms,
    )
    for issue in report.failed:
        logger.error(
            "Plugin load failed: module=%s plugin=%s stage=%s error=%s",
            issue.module,
            issue.plugin or "-",
            issue.stage,
            issue.error,
        )


def load_plugins(strict_core: bool = True) -> PluginLoadReport:
    return _replace_registry(reload_modules=False, strict_core=strict_core)


def reload_plugins(strict_core: bool = True) -> PluginLoadReport:
    return _replace_registry(reload_modules=True, strict_core=strict_core)


def _replace_registry(
    reload_modules: bool,
    strict_core: bool,
) -> PluginLoadReport:
    global last_load_report
    registry, report = _build_registry(reload_modules)
    last_load_report = report
    if strict_core and report.core_failures:
        _log_report(report, registry)
        raise PluginLoadError(report)
    _publish_registry(registry)
    _log_report(report, registry)
    return report


def get_export_plugins() -> tuple[PluginWrapper, ...]:
    return tuple(export_plugins)


def get_active_plugins() -> tuple[ActiveHandler, ...]:
    return tuple(active_plugins)


def get_schedule_plugins() -> tuple[ScheduleModule, ...]:
    return tuple(schedule_plugins)


def reload_designated_export_module(
    plugin_name: str,
    module_name: str = "",
) -> PluginLoadReport:
    report = reload_plugins(strict_core=True)
    qualified_module = f"plugins.{Path(plugin_name).stem}"
    if module_name and not any(
        item.endswith(f".{module_name}") and qualified_module in item
        for item in report.loaded
    ):
        raise LookupError(
            f"plugin class {module_name!r} was not loaded from {qualified_module}"
        )
    return report
