#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
from configs import config
from adapter.watchdog import watch_event_loop

from adapter import msg_queue
from adapter.http_request import upload_group_file
from adapter.server import main as server_main
from adapter.worker import process_loop, worker_shutdown, worker_start
from adapter.schedule import register_schedules
from adapter.post_process import on_shutdown
from toogle.index import load_plugins
from toogle.adapter import register_group_file_uploader
from toogle.scheduler import scheduler_shutdown, scheduler_start


async def main():
    msg_queue.reset_queues()
    register_group_file_uploader(upload_group_file)
    runtime_tasks = []
    try:
        load_plugins(strict_core=True)
        register_schedules()
        worker_start()
        scheduler_start()
        runtime_tasks = [
            asyncio.create_task(server_main(), name="napcat-server"),
            *[
                asyncio.create_task(process_loop(), name=f"message-dispatch-{index}")
                for index in range(max(1, int(config.get("MESSAGE_DISPATCHER_NUM", 4))))
            ],
            asyncio.create_task(
                watch_event_loop(max(10, int(config["EVENT_LOOP_TIMEOUT_SECONDS"]))),
                name="event-loop-watchdog",
            ),
        ]
        await asyncio.gather(*runtime_tasks)
    finally:
        for task in runtime_tasks:
            task.cancel()
        await asyncio.gather(*runtime_tasks, return_exceptions=True)
        scheduler_shutdown()
        await worker_shutdown()
        await on_shutdown()
        register_group_file_uploader(None)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
