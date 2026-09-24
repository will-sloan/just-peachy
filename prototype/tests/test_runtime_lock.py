"""Crash/reboot ownership regression checks; see release_tools/README_STARTUP.md."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from release_tools.runtime_lock import RuntimeLock, boot_id
from release_tools.release import update_boundary


class RuntimeLockTests(unittest.TestCase):
    def test_live_owner_blocks_app_and_updater(self):
        with tempfile.TemporaryDirectory() as d:
            owner = RuntimeLock(d, 'application')
            try:
                with self.assertRaises(FileExistsError): RuntimeLock(d, 'application')
                with self.assertRaises(RuntimeError):
                    with update_boundary(d): pass
            finally: owner.close()
            with update_boundary(d):
                with self.assertRaises(FileExistsError): RuntimeLock(d, 'application')

    def test_uncertain_and_legacy_live_records_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'runtime.lock'
            for value in ('', '{', json.dumps({'pid': os.getpid(), 'token': 'legacy'})):
                path.write_text(value)
                with self.assertRaises(FileExistsError): RuntimeLock(d, 'application')
                self.assertEqual(path.read_text(), value)

    @unittest.skipUnless(sys.platform == 'linux', 'Linux recovery policy')
    def test_previous_boot_with_reused_pid(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'runtime.lock').write_text(json.dumps({'pid':os.getpid(), 'boot_id':'previous-boot'}))
            owner = RuntimeLock(d, 'application')
            self.assertEqual(json.loads(owner.path.read_text())['boot_id'], boot_id())
            owner.close()

    @unittest.skipUnless(sys.platform == 'linux', 'Linux recovery policy')
    def test_crash_recovery_and_simultaneous_contenders(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
            code = 'from release_tools.runtime_lock import RuntimeLock; import os,sys; x=RuntimeLock(sys.argv[1],"application"); os._exit(0)'
            subprocess.run([sys.executable,'-c',code,d],env=env,check=True)
            self.assertTrue((Path(d)/'runtime.lock').exists())
            code = ('from release_tools.runtime_lock import RuntimeLock; import sys; '
                    'x=RuntimeLock(sys.argv[1],"application"); print("owned",flush=True); sys.stdin.read(); x.close()')
            children = [subprocess.Popen([sys.executable,'-c',code,d], env=env,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
            try:
                outputs = [p.stdout.readline().strip() for p in children]
                self.assertEqual(outputs.count('owned'), 1)
            finally:
                for p in children: p.communicate(timeout=10)
            self.assertFalse((Path(d)/'runtime.lock').exists())


if __name__ == '__main__': unittest.main()
