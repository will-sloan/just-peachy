"""Focused host export allocation/closure checks. README_OWNED_EXPORT.md."""
import ast
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import owned_export as oe
from storage import SessionStore, StoragePolicy


class ExportTests(unittest.TestCase):
    def test_real_read_only_export_shared_lease_blocks_deletion(self):
        from storage import ActiveSessionError, StorageError
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();policy=StoragePolicy(reserve_bytes=0,reserve_fraction=0)
            writer=SessionStore(root/'recordings',policy)
            spool=writer.begin(dict(sample_rate=16000,duration_seconds=.01))
            spool.append_processed(0,struct.pack('<f',.25)*64);spool.stop(64);spool.keep()
            before=writer.read(spool.session_id)
            plain=SessionStore(writer.root,policy,read_only=True)
            with self.assertRaisesRegex(StorageError,'shared session lease'):
                plain.export([spool.session_id],root/'original-refusal.zip')
            plain.close()
            reader=oe.read_only_export_store(writer.root,policy)
            with reader._session_lease(spool.session_id,shared=True):
                reader.export([spool.session_id],root/'shared-read.zip')
                with self.assertRaises(ActiveSessionError):writer.delete(spool.session_id,confirm=True)
            self.assertEqual(writer.read(spool.session_id),before)
            with reader._db() as db:
                self.assertEqual(db.execute('PRAGMA query_only').fetchone()[0],1)
            self.assertTrue((root/'shared-read.zip').is_file());reader.close();writer.close()

    def test_large_export_plan_matches_store_and_keeps_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            store = SessionStore(root/'recordings', StoragePolicy(reserve_bytes=0,reserve_fraction=0))
            spool = store.begin(dict(sample_rate=16000,duration_seconds=.01,metadata_reserve_bytes=40*oe.MIB))
            spool.append_processed(0,struct.pack('<f',.25)*64)
            artifact=spool.directory/'work'/'fixture.bin'; artifact.parent.mkdir()
            with artifact.open('wb') as stream:
                for _ in range(34):stream.write(b'\0'*oe.MIB)
            store.register_artifact(spool.session_id,'work/fixture.bin')
            spool.stop(64);spool.keep();before=store.read(spool.session_id)
            destination=root/'selected.zip'
            reader=oe.read_only_export_store(store.root,store.policy)
            plan=oe.plan_export(reader,[spool.session_id],destination)
            self.assertGreater(plan['maximum_bytes'],32*oe.MIB)
            with patch.object(reader,'_capacity',wraps=reader._capacity) as capacity:
                reader.export([spool.session_id],destination)
            self.assertEqual(capacity.call_args_list[0].args[0],plan['maximum_bytes'])
            self.assertLess(destination.stat().st_size,plan['maximum_bytes'])
            self.assertEqual(store.read(spool.session_id),before)
            self.assertTrue(artifact.is_file());reader.close();store.close()

    def test_finite_file_cap_allows_plan_above_soft_but_refuses_hard(self):
        fake=types.SimpleNamespace(RLIM_INFINITY=-1)
        with patch.dict(sys.modules,resource=fake):
            self.assertEqual(oe.file_limit(40*oe.MIB,128*oe.MIB),40*oe.MIB)
            with self.assertRaisesRegex(ValueError,'finite file ceiling'):oe.file_limit(40*oe.MIB,32*oe.MIB)
            with self.assertRaisesRegex(ValueError,'finite file ceiling'):oe.file_limit(40*oe.MIB,-1)

    def test_missing_owner_deadline_reaps_only_direct_child(self):
        class Process:
            pid=4321;returncode=None;terminated=False;waited=False
            def poll(self):return self.returncode
            def terminate(self):self.terminated=True;self.returncode=-15
            def kill(self):raise AssertionError('Graceful direct child already reaped')
            def wait(self,timeout=0):self.waited=True;return self.returncode
        with tempfile.TemporaryDirectory() as temporary:
            task=oe.ExportTask.__new__(oe.ExportTask);task.directory=Path(temporary)
            task.child_directory=task.directory/'child';task.child_directory.mkdir()
            task.process=Process();task.owner=None;task.finished=False;task.result=None;task.error=None
            task.started=time.monotonic()-10;task.deadline=time.monotonic()+60
            task.cancelled=False;task.terminated=None;task.killed=False
            with patch.object(oe,'identity',return_value=None):result=task.poll()
            self.assertEqual(result['status'],'FAILED');self.assertTrue(task.process.terminated)
            self.assertTrue(task.process.waited)
            receipt=json.loads((task.directory/'CHILD_CLOSURE.json').read_bytes())
            self.assertTrue(receipt['direct_child_reaped']);self.assertTrue(receipt['exact_owner_gone'])
            self.assertFalse((task.directory/'EXPORT.json').exists())

    def test_external_v2_embeds_exact_shared_worker_and_08_wrapper(self):
        import launch_recording_export_action_v3 as external
        self.assertEqual(external.EXPORT_HELPER.encode(),Path(oe.__file__).read_bytes())
        package=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/package-preparation-e0bd8f7d7cb2429eaf260c87133ae29a/package')
        manifest=json.loads((package/'PACKAGE_MANIFEST.json').read_bytes())
        pin=next(row for row in manifest['files'] if row['path']=='launch_raw_qualification_action.py')
        raw=(package/pin['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),pin['sha256'])
        function=next(node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='wrapper_source')
        scope={};exec(compile(ast.Module(body=[function],type_ignores=[]),'<exact-frozen08-wrapper>','exec'),scope)
        compile(external.export_wrapper(scope['wrapper_source'],dict(budget={'maximum_output_bytes':64*oe.MIB})), '<derived-export-wrapper>','exec')

    def test_manager_exit_waits_for_export_closure(self):
        from launcher import Manager
        class Task:
            finished=False;cancelled=False
            def poll(self):return None
            def cancel(self):self.cancelled=True
        manager=Manager.__new__(Manager);manager.export_task=Task();manager.process=None
        manager.poll=lambda:None
        with self.assertRaisesRegex(RuntimeError,'owned export'):manager.close()
        self.assertTrue(manager.export_task.cancelled)


if __name__=='__main__':unittest.main()
