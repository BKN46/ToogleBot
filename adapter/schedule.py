from toogle.index import get_schedule_plugins
from toogle.scheduler import native_scheduler, reload_manual_scheduler


def register_schedules() -> None:
    plugins = get_schedule_plugins()
    expected_code_jobs = {plugin.job_id for plugin in plugins}

    for plugin in plugins:
        plugin.register()

    for job in native_scheduler.get_jobs():
        if job.id.startswith("code:") and job.id not in expected_code_jobs:
            native_scheduler.remove_job(job.id)

    reload_manual_scheduler()
