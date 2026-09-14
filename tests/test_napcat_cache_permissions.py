import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class CachePermissionsTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("setfacl") and shutil.which("xvfb-run"), "requires ACL and Xvfb tools")
    def test_launcher_preserves_existing_cache_acl(self):
        launcher = Path(__file__).resolve().parents[1] / "tools/start_napcat_main.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ, NAPCAT_MAIN_ACCOUNT="12345",
                       NAPCAT_MAIN_WORKDIR=str(root / "work"),
                       NAPCAT_MAIN_QQ_DATA_DIR=str(root / "qq"),
                       NAPCAT_QQ_BIN="/bin/true", NAPCAT_HTTP_HOST="127.0.0.1",
                       NAPCAT_WS_HOST="127.0.0.1", NAPCAT_HTTP_PORT="54398",
                       NAPCAT_WS_PORT="54399", NAPCAT_HTTP_TOKEN="fixture",
                       NAPCAT_WS_TOKEN="fixture")
            subprocess.run(["bash", str(launcher)], env=env, check=True, capture_output=True, timeout=15)
            cache = root / "work/cache"
            self.assertEqual(cache.stat().st_mode & 0o777, 0o700)
            subprocess.run(["setfacl", "-m", "u:65534:x,m::x", str(cache)], check=True)
            before = subprocess.check_output(["getfacl", "-cp", str(cache)])
            for _ in range(2):
                subprocess.run(["bash", str(launcher)], env=env, check=True, capture_output=True, timeout=15)
                self.assertEqual(subprocess.check_output(["getfacl", "-cp", str(cache)]), before)
            self.assertEqual((root / "work/config").stat().st_mode & 0o777, 0o700)
