"""Changed archive-record verification; README_FIELD_ARCHIVE_RECORDS_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from pathlib import Path
import json
import hashlib
import datetime
import importlib.util
import sys
import time
from types import SimpleNamespace

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True);p.add_argument('--source-tree',required=True);p.add_argument('--release',required=True)
    args=p.parse_args();out=Path(args.output);out.mkdir()
    me=psutil.Process()
    (out/'REGISTERED_OWNER.json').open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    from field_archive_records_v1 import archive_class,chunked_binary,pieces,LOGICAL_BYTES
    source=Path(args.source_tree);release=Path(args.release)
    sys.path.insert(0,str(release))
    spec=importlib.util.spec_from_file_location('app.sessions',Path(__file__).with_name('archive_stop_sessions_v1.py'))
    sessions=importlib.util.module_from_spec(spec);sys.modules['app.sessions']=sessions;spec.loader.exec_module(sessions)
    from app.app_bounded_artifacts_v1 import compact_records
    from field_archive_budget_v4 import DEFAULT
    sessions.CompactBinary=chunked_binary(sessions.CompactBinary)
    A=archive_class(sessions.EpochArchive)
    native=next(source.glob('data/sessions/*/events.jsonl'))
    events=[]
    with native.open('rb') as f:
        for line in f:
            row=json.loads(line);event=row.get('value',{})
            if event.get('event_type')=='n2_diarization_frames':events.append(event)
    assert len(events)==2
    archive=A(out/'epoch',{},False,policy=dict(archive_budget=DEFAULT,record_bytes=65536,free_floor_mib=5120))
    try:
        for v in events:
            archive.event(SimpleNamespace(event_type=v['event_type'],payload=v['payload'],
                source_time_sec=v.get('source_time_sec'),wall_time_utc=v.get('wall_time_utc'),schema_version=v.get('schema_version')))
        archive.queue.join()
    finally:archive.close()
    assert not archive.error and archive.closed and not archive.thread.is_alive()
    reopened=list(compact_records(out/'epoch/events.jsonl'))
    assert [v['payload'] for v in reopened]==[v['payload'] for v in events]
    checks=[]
    for v in events:
        p=v['payload'];checks.append(dict(rows=len(p['probabilities']),columns=sorted(set(map(len,p['probabilities']))),frame_start=p['frame_start'],
            is_final=p['is_final'],publication_sequence=p['publication_sequence'],
            payload_sha256=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()))
    rejected=[]
    for name,raw in [('logical_overflow',b'x'*(LOGICAL_BYTES+1)),('wrong_kind',json.dumps(dict(kind='unknown',payload='x'*70000)).encode()),
                     ('invalid_shape',json.dumps(dict(kind='n2_diarization_frames',payload=dict(probabilities=[[.2]*7]*2200,frame_start=0))).encode())]:
        try:pieces(raw,0)
        except ValueError:rejected.append(name)
        else:raise AssertionError(name)
    # Observe every physical archive event write, including a deliberate short write.
    class File:
        def __init__(self):self.maximum=0;self.received=0
        def write(self,data):
            self.maximum=max(self.maximum,len(data));n=min(len(data),12345);self.received+=n;return n
    file=File()
    class Binary:
        def __init__(self):self.sink=SimpleNamespace(file=file,bytes=0,write_ns=0)
    obj=chunked_binary(Binary)();obj.sink._write(b'x'*400000)
    assert file.maximum<=65536 and file.received==obj.sink.bytes==400000
    result=dict(status='PASS_CHANGED_ARCHIVE_RECORD_ROUNDTRIP_ONLY',events=checks,exact_payload_reconstruction=True,
        original_persisted_format=True,archive=archive.snapshot(),three_expected_rejects=rejected,
        partial_write_total=file.received,maximum_physical_write=file.maximum,
        model_source_gui_executed=False,closed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    assert sum(p.stat().st_size for p in out.rglob('*') if p.is_file())<600000
    (out/'RESULT.json').open('x').write(json.dumps(result))
    print(json.dumps(result))
if __name__=='__main__':main()
