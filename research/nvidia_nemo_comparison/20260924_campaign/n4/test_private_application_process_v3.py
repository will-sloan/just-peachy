"""Real model-free Windows job/desktop tests. Use the guarded probe CLI."""
from pathlib import Path
import os
import sys
import time
import unittest

from common import bind, load
from metric_process import exact_process
from private_application_process_v3 import PrivateApplicationProcess

OUTPUT = None


class PrivateProcessTests(unittest.TestCase):
    def setUp(self):
        if OUTPUT is None: self.skipTest('Use probe_private_application_process_v3.py with a fresh private output')
        self.root = OUTPUT/self._testMethodName; self.root.mkdir()
        self.evidence = self.root/'fixture'; self.evidence.mkdir()
        self.child = None

    def tearDown(self):
        if self.child is not None and not self.child.closed: self.child.close(grace_seconds=0)

    def launch(self, mode):
        self.child = PrivateApplicationProcess(self.root/'lifetime', executable_binding=bind(sys.executable),
            script_binding=bind(Path(__file__).with_name('private_process_fixture_v3.py')),
            arguments=['--mode', mode, '--evidence', str(self.evidence), '--cancel', str(self.root/'lifetime/CANCEL')], cpu=14)
        self.child.spawn_suspended()
        return self.child

    def resume(self, mode):
        child = self.launch(mode); child.resume(lambda *args, **kwargs: None)
        self.wait_file(self.evidence/'started.json')
        return child

    def wait_file(self, path):
        until = time.monotonic()+8
        while not path.exists() and time.monotonic() < until: time.sleep(.025)
        self.assertTrue(path.exists(), str(path))
        # Fixture files are tiny; permit the writer to close before JSON inspection.
        until = time.monotonic()+1
        while True:
            try: return load(path)
            except (ValueError, PermissionError):
                if time.monotonic() >= until: raise
                time.sleep(.01)

    def assert_closed(self, child, *, forced, exit_code=None):
        row = child.receipt
        self.assertEqual(row['status'], 'OWNED_PROCESS_LIFETIME_CLOSED')
        self.assertTrue(row['job_empty_verified']); self.assertEqual(row['final_job']['active'], 0)
        self.assertEqual(row['forced'], forced)
        self.assertEqual(row['input_desktop_before'], row['input_desktop_after'])
        self.assertIsNone(exact_process(row['owner']))
        if exit_code is not None: self.assertEqual(row['root_exit_code'], exit_code)

    def assert_members(self, child, *expected):
        rows = child.members(); owners = {(r['pid'], r['create_time']) for r in expected}
        actual = {(r['pid'], r.get('create_time')) for r in rows}
        self.assertTrue(owners.issubset(actual))
        for row in rows:
            self.assertFalse(row.get('exited_during_observation', False))
            self.assertEqual(row['affinity'], [14])
            if (row['pid'], row['create_time']) not in owners:
                self.assertEqual(Path(row['executable']).resolve(), Path(os.environ['SystemRoot'], 'System32/conhost.exe').resolve())
        return rows

    def test_suspended_registration_then_private_tk(self):
        child = self.launch('normal'); time.sleep(.15)
        self.assertFalse((self.evidence/'started.json').exists())
        self.assertFalse(child.root_exited()); self.assertEqual(child.accounting()['active'], 1)
        observed = []
        def register(owner, **kwargs):
            self.assertFalse((self.evidence/'started.json').exists())
            self.assertEqual(owner, child.owner); observed.append(kwargs)
        child.resume(register); self.assertTrue(child.wait_empty(8))
        tk = self.wait_file(self.evidence/'tk.json')
        self.assertEqual(tk['desktop'], child.desktop_name); self.assertTrue(tk['created_and_destroyed'])
        self.assertEqual(len(observed), 1)
        child.close(); self.assert_closed(child, forced=False, exit_code=0)
        self.assertEqual(child.close(), child.receipt)

    def test_registration_failure_never_executes(self):
        child = self.launch('normal')
        def deny(*args, **kwargs): raise ValueError('Fixture admission denied')
        with self.assertRaisesRegex(ValueError, 'Fixture admission denied'): child.resume(deny)
        self.assertFalse((self.evidence/'started.json').exists())
        self.assert_closed(child, forced=True, exit_code=125)

    def test_child_exception_is_preserved(self):
        child = self.resume('error'); self.assertTrue(child.wait_empty(8))
        child.close(); self.assert_closed(child, forced=False, exit_code=1)

    def test_graceful_cancel(self):
        child = self.resume('cooperative'); child.close(grace_seconds=5)
        self.assertTrue(self.wait_file(self.evidence/'cancelled.json')['observed'])
        self.assert_closed(child, forced=False, exit_code=0)

    def test_stubborn_root_and_descendant_cleanup(self):
        child = self.resume('tree'); leaf = self.wait_file(self.evidence/'leaf/started.json')
        self.assertEqual(leaf['affinity'], [14]); members = self.assert_members(child, child.owner, leaf)
        self.assertEqual(child.accounting()['active'], len(members))
        child.close(grace_seconds=.1); self.assert_closed(child, forced=True, exit_code=125)
        self.assertIsNone(exact_process(leaf)); self.assertGreaterEqual(child.receipt['final_job']['total'], len(members))
        for owner in members: self.assertIsNone(exact_process(owner))

    def test_root_exit_does_not_hide_live_descendant(self):
        child = self.resume('orphan'); leaf = self.wait_file(self.evidence/'leaf/started.json')
        until = time.monotonic()+5
        while not child.root_exited() and time.monotonic() < until: time.sleep(.02)
        self.assertTrue(child.root_exited()); members = self.assert_members(child, leaf)
        self.assertEqual(child.accounting()['active'], len(members))
        self.assertFalse(child.wait_empty(.05))
        child.close(grace_seconds=.1); self.assert_closed(child, forced=True, exit_code=0)
        self.assertIsNone(exact_process(leaf))
        for owner in members: self.assertIsNone(exact_process(owner))

    def test_last_job_handle_closes_on_owner_death(self):
        child = self.resume('owner_death'); leaf = self.wait_file(self.evidence/'leaf/started.json')
        self.assertTrue(child.wait_empty(5), 'Nested leaf survived abrupt inner owner death')
        self.assertIsNone(exact_process(leaf)); child.close()
        self.assert_closed(child, forced=False, exit_code=23)
        self.assertGreaterEqual(child.receipt['final_job']['total'], 2)

    def test_invalid_input_refused_before_spawn(self):
        kwargs = dict(executable_binding=bind(sys.executable), script_binding=bind(Path(__file__).with_name('private_process_fixture_v3.py')))
        with self.assertRaises(ValueError): PrivateApplicationProcess(self.root/'bad', **kwargs, arguments=['bad\0argument'])
        with self.assertRaises(ValueError): PrivateApplicationProcess(self.root/'bad', **kwargs, cpu=0)
        stale = dict(kwargs['script_binding']); stale['sha256'] = '0'*64
        with self.assertRaises(ValueError): PrivateApplicationProcess(self.root/'bad', executable_binding=kwargs['executable_binding'], script_binding=stale)
        self.assertFalse((self.root/'bad').exists())
