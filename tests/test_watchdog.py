import subprocess
import sys
import unittest


class WatchdogTest(unittest.TestCase):
    def test_blocked_loop_exits_process(self):
        result = subprocess.run([
            sys.executable, "-c",
            "import asyncio,time; from adapter.watchdog import watch_event_loop\n"
            "async def main():\n"
            " asyncio.create_task(watch_event_loop(0.1))\n"
            " await asyncio.sleep(0.01)\n"
            " time.sleep(10)\n"
            "asyncio.run(main())"
        ], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"watchdog timeout", result.stderr)
