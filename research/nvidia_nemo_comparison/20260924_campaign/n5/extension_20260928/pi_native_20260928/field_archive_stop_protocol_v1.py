"""Actual retained archive worker with changed Stop binding; README_FIELD_ARCHIVE_STOP_V1.md."""
import hashlib
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path
import field_archive_budget_v4 as publisher
from field_run_outputs_v1 import RunOutputs,allocation
from field_archive_stop_v1 import archive_class,ArchiveStopped
from field_sidecar_budget_v1 import GroupWriter,encoded


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(root,a):
    base=Path(a['installed_release'])
    for path,digest in a['archive_binding_files'].items():assert sha(path)==digest
    sys.path[:0]=[str(base),str(base/'vendor'),str(base/'native')]
    import app
    assert Path(app.__file__).resolve()==base/'app/__init__.py' and 'app.sessions' not in sys.modules
    source=root/'code/archive_stop_sessions_v1.py'
    spec=importlib.util.spec_from_file_location('app.sessions',source)
    sessions=importlib.util.module_from_spec(spec);sys.modules['app.sessions']=sessions;spec.loader.exec_module(sessions);app.sessions=sessions
    assert Path(sessions.__file__).resolve()==source and sessions.publish is publisher.publish
    original_epoch=sessions.EpochArchive
    limits=json.loads((base/'config/artifact_limits.json').read_text())
    policy=dict(archive_budget=publisher.validate(publisher.DEFAULT),artifact_limits=limits,
                quota_mib=512,free_floor_mib=5120,record_bytes=65536,resource_interval_sec=3600)
    receipts=root/'binding_receipts';receipts.mkdir()
    writer=GroupWriter(receipts,a['case_receipt_limits']);cases=[]
    checks=RunOutputs(root/'slot-checks')
    # Distinct reservations share one directory; no remapping or replacement.
    checks.publish('source','closure',encoded({'source_fixture':True}))
    checks.publish('transport','closure',encoded({'transport_fixture':True}))
    rejected=[]
    for label,producer,kind,raw in [('unknown-producer','archive/../source','closure',b'{}'),
            ('wrong-channel','archive','unknown',b'{}'),('own-slot-limit','archive','closure',b'x'*32769),
            ('unassigned-telemetry','archive','telemetry',b'{}\n')]:
        try:checks.publish(producer,kind,raw)
        except (ValueError,RuntimeError) as exc:rejected.append(dict(case=label,error=type(exc).__name__,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        else:raise AssertionError('Missing changed slot rejection')
    # Preserve the only rejected payload larger than the small receipt.
    writer.write('SLOT_REJECTED.bin',b'x'*32769)
    assert not (checks.root/'closure/archive.json').exists()
    writer.json('SLOT_CHECKS.json',dict(rejections=rejected,source_and_transport_exact=True,allocation=allocation()))
    for name in ['checkpoint-write-failure','late-detail-70k']:
        outputs=RunOutputs(root/(name+'-outputs'));stop=threading.Event();stop_calls=[]
        def request_stop():
            # Explicit source-stop Event fixture, not a hardware source/controller.
            stop_calls.append(dict(before_diagnostics=not any((outputs.root/'failure').glob('archive.*'))))
            stop.set()
        sessions.EpochArchive=archive_class(original_epoch,outputs,request_stop)
        original_write=publisher._write_block;calls=[]
        def changed_write(stream,raw):
            calls.append(dict(path=str(stream.name),bytes=len(raw)))
            return original_write(stream,raw[:3] if name=='checkpoint-write-failure' and len(calls)==2 else raw)
        publisher._write_block=changed_write
        archive=None;close_error=None
        try:
            archive=sessions.EpochArchive(root/name,dict(synthetic_no_capture=True),False,policy=policy)
            if name=='late-detail-70k':
                end=time.monotonic()+5
                while len(calls)<2:
                    if time.monotonic()>end:raise TimeoutError('Archive initial checkpoint')
                    time.sleep(.005)
                archive.metadata['late_detail']='L'*70000
                try:archive.close()
                except ArchiveStopped as exc:close_error=str(exc)
            else:
                assert stop.wait(5)
                try:archive.close()
                except ArchiveStopped as exc:close_error=str(exc)
            assert close_error and len(stop_calls)==1 and stop_calls[0]['before_diagnostics']
            assert stop.is_set() and archive.closed and not archive.thread.is_alive()
            closure=json.loads((outputs.root/'closure/archive.json').read_text())
            assert closure['worker_joined'] and closure['closed'] and not closure['logical_success']
            assert closure['source_samples']==closure['recorded_samples']==closure['accepted_items']==closure['completed_items']==0
            assert closure['pending_items']==closure['pending_bytes']==0
            if name=='checkpoint-write-failure':
                assert len(calls)==2 and (archive.path/'.epoch.json.pending').read_bytes()==b'{\n '
                assert json.loads((archive.path/'epoch.json').read_text())['state']=='OPEN'
                assert closure['publication_failure']['replaced'] is False
            else:
                detail=json.loads((archive.path/'checkpoint-detail.json').read_text())
                assert detail['late_detail']=='L'*70000
                assert (archive.path/'checkpoint-detail.json').stat().st_size>65536
                meta=json.loads((archive.path/'epoch.json').read_text())
                assert meta['state']=='PARTIAL' and meta['control_metadata_overflow'] and not meta['worker_alive']
                assert not list(archive.path.glob('*.pending')) and closure['publication_failure'] is None
            assert outputs.failures['archive']['stop_requested'] and outputs.failures['archive']['raw_retained'] and outputs.failures['archive']['receipt_retained']
            cases.append(dict(case=name,publisher_calls=calls,stop_calls=stop_calls,close_error=close_error,
                              closure=closure,archive_origin=str(source),audio=False))
        finally:
            if archive is not None and archive.thread.is_alive():
                archive.stop_event.set();archive.thread.join(10)
                assert not archive.thread.is_alive()
            publisher._write_block=original_write;sessions.EpochArchive=original_epoch
    assert not any(t.name=='proto-session-archive' for t in threading.enumerate())
    assert not list(root.rglob('*.wav')) and not list(root.rglob('*.f32le'))
    writer.json('ARCHIVE_BINDING_CASES.json',cases)
    result=dict(status='PASS_SHARED_SLOTS_AND_NATIVE_ARCHIVE_STOP_BINDING_ONLY',archive_cases=2,slot_rejections=4,
                live_source_stop_fixture=True,actual_controller=False,source_samples=0,models=False,capture=False,GUI=False,
                archive_workers_joined=True,partial_preserved=True,failed_publication_not_retried=True,
                shared_sidecar_reserved_bytes=allocation()['reserved_bytes'],whole_run_integrated=False)
    writer.json('BINDING_CLOSURE.json',result)
    return result
