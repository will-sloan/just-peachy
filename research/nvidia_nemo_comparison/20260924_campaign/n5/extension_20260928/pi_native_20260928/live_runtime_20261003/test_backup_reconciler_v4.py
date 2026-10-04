"""Focused natural-EOF, retained-failure and cumulative-allocation checks; README_BACKUP_RECONCILER_V4.md."""
import builtins
import json
from pathlib import Path
import symtable
import tempfile
import types
import unittest
from unittest.mock import patch

import backup_external_common_v2 as common
import monitor_native_job as monitor
import reconcile_production_backup_external_v4 as target


class ReconcilerV4Tests(unittest.TestCase):
    def test_natural_ready_eof_publishes_independent_closure_without_mirror(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);phase=root/'snapshot-0001';receiver=monitor.Receiver(root,16384)
            owner=dict(pid=123,start_ticks=456,boot_id='fixture')
            def transport(command,payload,receiver,maximum):
                receiver.feed(dict(kind='OWNER',owner=owner))
                receiver.feed(dict(kind='STATUS',snapshot_ready=True,closed=False))
                return dict(natural_returncode=0,ssh_reaped=True)
            child=types.SimpleNamespace(pid=999,_handle=1,returncode=0,communicate=lambda timeout:(b'',b''))
            with patch.object(monitor,'phase',side_effect=transport),patch.object(target.subprocess,'Popen',return_value=child),patch.object(monitor,'process_creation',return_value=1234):
                actual=target.run_snapshot(monitor,common,b'pass',{},receiver,phase,dict(mode='ready'))
            proof=common.strict((phase/'SSH_CLOSURE.json').read_bytes())
            self.assertTrue(proof['utility_pid_absent_after_ssh']);self.assertTrue(proof['absence_check']['naturally_reaped'])
            self.assertEqual(common.strict((phase/'NATIVE_OWNER.json').read_bytes()),owner)
            self.assertEqual(actual.status['snapshot_ready'],True)
            self.assertFalse((root/'MIRROR_COMPLETE.json').exists())

    def test_transport_failure_is_preserved_and_phase_cap_refuses_before_write(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);receiver=monitor.Receiver(root,16384);phase=root/'snapshot-0001'
            with patch.object(monitor,'phase',side_effect=RuntimeError('transport fixture')):
                with self.assertRaisesRegex(RuntimeError,'transport fixture'):
                    target.run_snapshot(monitor,common,b'pass',{},receiver,phase,dict(mode='ready'))
            self.assertIn('transport fixture',common.strict((phase/'FAILURE.json').read_bytes())['error'])
            (phase/'large').write_bytes(b'x'*target.PHASE_BYTES)
            with self.assertRaisesRegex(ValueError,'before write'):target.publish_phase(common,phase/'REFUSED.json',{})
            self.assertFalse((phase/'REFUSED.json').exists())

    def test_prior_failure_cost_and_deadline_are_retained_and_payload_resume_refused(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);old=root/'production-backup-02-reconcile-01';old.mkdir();new=root/'production-backup-02-reconcile-02'
            job=common.encoded(dict(unit='jp-v29-production-backup-02.service',deadline_unix=1234))
            (old/'JOB.json').write_bytes(job);(old/'FAILURE.json').write_bytes(b'{}')
            (old/'REGISTERED_OWNER.json').write_bytes(common.encoded(dict(pid=2147483647,create_time=1,affinity=[14])))
            phase=old/'snapshot-0001';phase.mkdir();(phase/'NATIVE_OWNER.json').write_bytes(b'{}')
            before=sum(p.stat().st_size for p in old.rglob('*') if p.is_file())
            got=target.prior_attempt_usage(common,old,job,new)
            self.assertEqual(got['bytes'],before);self.assertEqual(got['phases'],1);self.assertEqual(got['original_deadline_unix'],1234)
            self.assertFalse(got['prior_utility_closure_reconstructed'])
            (old/'payload').mkdir()
            with self.assertRaisesRegex(ValueError,'pre-transfer'):target.prior_attempt_usage(common,old,job,new)

    def test_all_global_references_resolve_and_fixed_segment_plan_has_no_adaptive_state(self):
        source=Path(target.__file__).read_text();table=symtable.symtable(source,str(target.__file__),'exec')
        known=set(table.get_identifiers())|set(dir(builtins))|{'__file__','__name__'}
        missing=[]
        def walk(scope):
            for symbol in scope.get_symbols():
                if symbol.is_referenced() and symbol.is_global() and symbol.get_name() not in known:missing.append((scope.get_name(),symbol.get_name()))
            for child in scope.get_children():walk(child)
        walk(table);self.assertEqual(missing,[])
        self.assertNotIn('time.monotonic()-started',source)
        self.assertNotIn('chunk=min(',source)


if __name__=='__main__':unittest.main()
