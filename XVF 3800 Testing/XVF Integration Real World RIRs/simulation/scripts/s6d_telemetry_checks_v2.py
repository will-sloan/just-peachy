"""Model-free real-pipe/fake-process checks; README_S6D_TELEMETRY_V2.md."""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time


def bind(p):
    p=Path(p).resolve();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)


def save(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)


class Process:
    """No process is launched. Kill/terminate are forbidden even in a fixture."""
    def __init__(self,pipe,code=0):self.stdout=pipe;self.code=code;self.pid=987654;self.termination_calls=0
    def poll(self):return self.code
    def wait(self,timeout):
        assert timeout==3 and self.code is not None
        return self.code
    def kill(self):self.termination_calls+=1;raise AssertionError('Termination forbidden')
    terminate=kill


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--saved-attempt',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    out=Path(a.output).resolve()
    if not out.is_relative_to(Path('G:/Just_Peachy_S6D').resolve()):raise ValueError('Fixtures must remain on G')
    out.mkdir(parents=True,exist_ok=False)
    source=Path(a.source).resolve();sys.path.insert(0,str(source.parent))
    spec=importlib.util.spec_from_file_location('reviewed_telemetry_v2',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    old=Path(a.saved_attempt)/'telemetry';samples={}
    for line in (old/'stdout.bin').read_bytes().splitlines():
        row=json.loads(line.decode('utf-8-sig'))
        if row.get('phase')=='measurement':samples.setdefault(row['command'],row)
    assert set(samples)==set(m.FIELDS)
    rows=[samples[n] for n in m.FIELDS]
    terminal=json.loads((old/'native/result.json').read_text(encoding='utf-8-sig'))
    terminal['per_field']=copy.deepcopy(terminal['per_field'])
    for n in m.FIELDS:terminal['per_field'][n]['count']=1
    inspection=json.loads((old/'native/command_map_inspection.json').read_text(encoding='utf-8-sig'))
    results=[]

    class Fixture:
        def __init__(self,name,code=0,native=None):
            self.root=out/name;self.root.mkdir();self.log=m.S6DQueuedTelemetryLogger(out,self.root,1)
            z=self.log;z.native_dir=self.root/'native';z.native_dir.mkdir();z.stop_file=self.root/'stop.request';z.start_ns=time.perf_counter_ns()
            z._stderr=(self.root/'stderr.bin').open('xb');z.identity=dict(pid=987654,creation_time=100.,parent_pid=123,fixture_only=True)
            z._exclusive('PROCESS_IDENTITY.json',z.identity);z._identity_persisted=True
            z.library_bindings=[dict(sha256=inspection[k]) for k in ('device_usb_sha256','command_map_sha256')]
            save(z.native_dir/'result.json',terminal if native is None else native);save(z.native_dir/'command_map_inspection.json',inspection)
            r,w=os.pipe();self.writer=os.fdopen(w,'wb',buffering=0);z._process=Process(os.fdopen(r,'rb',buffering=65536),code)
            z._reader=threading.Thread(target=z._read,daemon=True);z._reader.start()
        def emit(self,tail=None,close=True,raw=None):
            for row in rows:self.writer.write((json.dumps(row)+'\n').encode())
            if raw is not None:self.writer.write(raw)
            elif tail is not None:self.writer.write((json.dumps(tail)+'\n').encode())
            if close:self.writer.close()
        def settle(self):
            self.log._manage();assert self.log._done.is_set();assert self.log.wait(0) is not None
            assert (self.root/'result.json').is_file();assert self.log._process.termination_calls==0
            return self.log.result
        def close(self):
            if not self.writer.closed:self.writer.close()
            self.log._reader.join(3);assert not self.log._reader.is_alive()
            if not self.log._stderr.closed:self.log._stderr.close()
        def fail(self):
            r=self.settle();assert r['status']=='FAIL' and not r['control_owner_closed_proven'];return r

    def check(name,fn):
        start=time.perf_counter();fn();results.append(dict(name=name,status='PASS',elapsed_seconds=time.perf_counter()-start));print(name+' PASS',flush=True)

    def framed_without_eof():
        f=Fixture('terminal_without_eof');f.emit(terminal,close=False);r=f.settle()
        assert r['status']=='PASS' and r['control_owner_closed_proven'] and r['verified_native_terminal_frame'] and not r['actual_stdout_eof']
        actual=[json.loads(s) for s in (f.root/'received_telemetry.jsonl').read_text().splitlines()]
        assert len(actual)==14
        arrivals=[]
        for i,(expected,row) in enumerate(zip(rows,actual)):
            assert all(row[k]==v for k,v in expected.items())
            assert row['receipt_sequence']==i and row['host_response_end_monotonic_ns']==expected['response_end_monotonic_ns']
            assert type(row['host_line_arrival_monotonic_ns']) is int
            arrivals.append(row['host_line_arrival_monotonic_ns'])
        assert arrivals==sorted(arrivals);f.close()
    check('exact_rows_QPC_order_and_terminal_without_EOF',framed_without_eof)

    def failure(name,mutate=None,tail=True,raw=None,code=0):
        native=copy.deepcopy(terminal)
        if mutate:mutate(native)
        f=Fixture(name,code,native);f.emit(native if tail else None,raw=raw);f.fail();f.close()
    check('EOF_without_terminal_settles_failure',lambda:failure('missing_terminal',tail=False))
    check('received_count_mismatch',lambda:failure('counts',lambda n:n['per_field'][m.FIELDS[0]].update(count=2)))
    check('boolean_count_fails',lambda:failure('bool_count',lambda n:n['per_field'][m.FIELDS[0]].update(count=True)))
    check('missing_field_mismatch',lambda:failure('missing_field',lambda n:n['per_field'].pop(m.FIELDS[-1])))
    check('pending_true_fails',lambda:failure('pending',lambda n:n['pending_reads_at_exit'].__setitem__(0,True)))
    check('pending_wrong_type_fails',lambda:failure('pending_int',lambda n:n['pending_reads_at_exit'].__setitem__(0,0)))
    check('cleanup_wrong_type_fails',lambda:failure('cleanup_bool',lambda n:n.update(cleanup_return=False)))
    check('nonzero_exit_fails',lambda:failure('exit',code=1))
    check('malformed_json_fails',lambda:failure('malformed',raw=b'{broken}\n'))
    check('oversized_line_fails',lambda:failure('oversized',raw=b'x'*65537+b'\n'))
    check('unterminated_line_fails',lambda:failure('unterminated',raw=b'{"mode":"queued_distinct_reads"}'))

    def different_terminal():
        f=Fixture('different_terminal');different=copy.deepcopy(terminal);different['status']='FAIL';f.emit(different);f.fail();f.close()
    check('terminal_bound_native_equality',different_terminal)

    def missing_evidence():
        f=Fixture('missing_inspection');(f.log.native_dir/'command_map_inspection.json').unlink();f.emit(terminal);f.fail();f.close()
    check('missing_native_inspection_fails',missing_evidence)

    def identity_missing():
        f=Fixture('identity_missing');f.log.identity=None;f.emit(terminal);f.fail();f.close()
    check('missing_captured_process_identity_fails',identity_missing)

    def identity_unpersisted():
        f=Fixture('identity_unpersisted');f.log._identity_persisted=False;f.emit(terminal);f.fail();f.close()
    check('unpersisted_process_identity_fails',identity_unpersisted)

    def delayed_eof():
        f=Fixture('delayed_eof');f.emit(close=False);r=f.fail();original=(f.root/'result.json').read_bytes()
        assert not r['reader_io_closed'] and any('Reader still alive' in x for x in r['errors'])
        f.close();assert (f.root/'result.json').read_bytes()==original
        late=json.loads((f.root/'late_reader_closure.json').read_text());assert late['status']=='DIAGNOSTIC_ONLY_ORIGINAL_FAILURE_PRESERVED' and late['actual_stdout_eof'] and not late['recovery_or_playback_authorized']
    check('late_EOF_preserves_durable_failure',delayed_eof)

    def alive_timeout():
        f=Fixture('cooperative_timeout',code=None);f.log._stop_at=time.perf_counter()-9;f.emit(close=False);r=f.fail()
        assert not r['native_process_exited'] and not r['stderr_closed'] and not r['process_termination_issued']
        assert any('no termination issued' in x for x in r['errors'])
        f.close()
    check('original_stop_budget_no_termination',alive_timeout)

    def duration_timeout():
        f=Fixture('duration_timeout',code=None);f.log.start_ns=int((time.perf_counter()-22)*1e9);f.emit(close=False);f.fail()
        assert f.log.stop_file.read_text()=='cooperative_closure_deadline';f.close()
    check('original_duration_budget_cooperative_stop',duration_timeout)

    def persistence_failure():
        f=Fixture('persistence_failure');f.emit(terminal);f.log._reader.join(3)
        (f.root/'result.json').mkdir();f.log._manage();r=f.log.wait(0)
        assert r['status']=='FAIL' and r['terminal_receipt_persisted'] is False and not r['control_owner_closed_proven'];f.close()
    check('terminal_persistence_failure_returns_explicit_FAIL',persistence_failure)

    def stderr_failure():
        f=Fixture('stderr_failure');f.log._stderr.write(b'native error');f.emit(terminal);r=f.settle()
        assert r['status']=='FAIL' and r['stderr_bytes']>0;f.close()
    check('nonempty_stderr_prevents_scientific_PASS',stderr_failure)

    def startup(launch_fails=False):
        root=out/('launch_failure' if launch_fails else 'actual_start_mocked_child');dll=out/('dll_failure_fixture' if launch_fails else 'dll_fixture');dll.mkdir()
        for n in ('device_usb.dll','command_map.dll'):(dll/n).write_bytes(b'FIXTURE ONLY - NOT A DLL')
        original_popen=m.subprocess.Popen;original_psutil=m.psutil.Process;writers=[];calls=[]
        class Identity:
            def __init__(self,*args):pass
            def create_time(self):return 12345.25
        def fake_popen(argv,**kwargs):
            calls.append(dict(argv=argv,bufsize=kwargs['bufsize'],shell=kwargs['shell']))
            if launch_fails:raise OSError('Fixture launch failure')
            native=Path(argv[argv.index('-OutputDirectory')+1]);native.mkdir()
            save(native/'result.json',terminal)
            save(native/'command_map_inspection.json',{k:bind(dll/n)['sha256'] for k,n in [('device_usb_sha256','device_usb.dll'),('command_map_sha256','command_map.dll')]})
            r,w=os.pipe();p=Process(os.fdopen(r,'rb',buffering=kwargs['bufsize']))
            def write():
                with os.fdopen(w,'wb',buffering=0) as pipe:
                    for row in rows+[terminal]:pipe.write((json.dumps(row)+'\n').encode())
            thread=threading.Thread(target=write);thread.start();writers.append(thread);return p
        try:
            m.subprocess.Popen=fake_popen;m.psutil.Process=Identity
            z=m.S6DQueuedTelemetryLogger(dll,root,1).start();r=z.wait(5);assert r is not None
            if launch_fails:assert r['status']=='FAIL' and not r['control_owner_closed_proven'] and r['terminal_receipt_persisted']
            else:
                z._manager.join(3);assert r['status']=='PASS' and r['process_identity_persisted'] and r['reader_thread_closed']
                identity=json.loads((root/'PROCESS_IDENTITY.json').read_text());assert identity['pid']==987654 and identity['creation_time']==12345.25
                stages=[json.loads(x)['stage'] for x in (root/'lifecycle.jsonl').read_text().splitlines()]
                assert all(s in stages for s in ('START_REQUESTED','PROCESS_CREATED','PROCESS_EXITED','READER_FINISHED','MANAGER_SETTLING'))
            assert calls[0]['bufsize']==65536 and calls[0]['shell'] is False
        finally:
            m.subprocess.Popen=original_popen;m.psutil.Process=original_psutil
            for thread in writers:thread.join(3);assert not thread.is_alive()
    check('actual_start_records_identity_and_buffered_argv_without_process_launch',startup)
    check('Popen_failure_always_settles_durable_FAIL',lambda:startup(True))
    save(out/'RECEIPT.json',dict(status='PASS',checks=results,source=bind(source),fixture=bind(__file__),saved_native_result=bind(old/'native/result.json'),saved_stdout=bind(old/'stdout.bin'),processes_launched=0,hardware_calls=0,model_calls=0,scope='Real anonymous pipe fixtures with fake process status, not actual native process/hardware qualification. Saved packet payloads reused only as fixture inputs.'))
    print(str(out/'RECEIPT.json'))


if __name__=='__main__':main()
