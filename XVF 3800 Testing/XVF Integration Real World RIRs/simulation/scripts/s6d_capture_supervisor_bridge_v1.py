"""Same-process capture V4 protocol bridge; README_S6D_PHYSICAL_PREPARATION.md."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid
import psutil

sys.dont_write_bytecode=True


def utc():return datetime.now(timezone.utc).isoformat()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def binding(path,expected=None):
    p=Path(path).resolve();a=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    b=p.stat()
    if (a.st_size,a.st_mtime_ns)!=(b.st_size,b.st_mtime_ns) or expected is not None and h.hexdigest()!=expected:raise ValueError('Changed source binding: '+str(p))
    return dict(path=str(p),bytes=b.st_size,sha256=h.hexdigest())


def save(path,value,exclusive=False,before_publish=None):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_name(p.name+'.'+str(os.getpid())+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
        for attempt in range(6):
            try:
                if before_publish is not None:before_publish()
                if exclusive:
                    if p.exists():raise FileExistsError(str(p))
                    os.rename(temp,p) # Windows rename does not overwrite an existing destination.
                else:os.replace(temp,p)
                return
            except PermissionError:
                if attempt==5:raise
                time.sleep(min(.02*2**attempt,.25))
    finally:
        if temp.exists():
            try:temp.unlink()
            except PermissionError:pass # A named temporary receipt may remain; never publish partial JSON.


def matching_identity(value,identity):
    try:return all(value.get(k)==identity[k] for k in ('run_id','job_id','child_run_id','pid')) and abs(value.get('creation_time',0)-identity['creation_time'])<.001
    except (TypeError,ValueError):return False


def restoration_proof(batch_dir,ledger,identity):
    """Only actual bound owner evidence can yield supervisor RESTORED."""
    acquired=Path(batch_dir)/'owner_acquired.json';restored=Path(batch_dir)/'restoration.json'
    owner=load(acquired);value=load(restored);closed=ledger.get('batches',{}).get(Path(batch_dir).name)
    if owner.get('pid')!=identity['pid'] or not closed:raise ValueError('Owner identity or closed ledger binding absent')
    acquired_unix=datetime.fromisoformat(owner['acquired_utc'].replace('Z','+00:00')).timestamp()
    if acquired_unix<identity.get('admission_unix',identity['creation_time']):raise ValueError('Stale owner receipt predates this process admission')
    for key,path in (('owner',acquired),('restoration',restored)):
        b=closed[key]
        if Path(b['path']).resolve()!=path.resolve():raise ValueError('Restoration ledger points to another owner')
        binding(path,b['sha256'])
    checks=dict(owner_same_process=True,exact_configuration_match=value.get('exact_recorded_configuration_match') is True,
        restoration_pass=value.get('status')=='PASS',telemetry_closed=value.get('telemetry_process_closed') is True,
        hardware_lease_released=value.get('hardware_lease_released') is True,
        audio_closed_or_no_playback=value.get('audio_handles_closed') is True or
            value.get('scope')=='No setters or playback occurred under this owner' and not any(r.get('batch')==Path(batch_dir).name for r in ledger.get('passes',[])))
    if not all(checks.values()):raise ValueError('Actual capture restoration did not pass: '+repr(checks))
    return dict(owner=binding(acquired),restoration=binding(restored),checks=checks,scope=value.get('scope'))


def completion_proof(batch_dir,ledger,attempt_ids,identity,plan_binding,authorization_binding):
    restored=restoration_proof(batch_dir,ledger,identity);summary=load(Path(batch_dir)/'SUMMARY.json');admission=load(Path(batch_dir)/'admission.json')
    if summary.get('status')!='COMPLETE_CAPTURE_BATCH' or summary.get('executed_source_bytes_unchanged_after_batch') is not True:
        raise ValueError('Capture batch/source epoch incomplete')
    if admission!=dict(plan=plan_binding,authorization=authorization_binding,attempt_ids=attempt_ids):raise ValueError('Owner admission differs from exact wrapper inputs')
    rows=[r for r in ledger['passes'] if r.get('batch')==Path(batch_dir).name]
    if len(rows)!=len(attempt_ids) or {r['attempt_id'] for r in rows}!=set(attempt_ids):raise ValueError('Physical ledger batch count differs')
    results=[]
    for row in rows:
        if row['status']!='PASS':raise ValueError('An attempt did not pass transport integrity')
        result_binding=row['result'];binding(result_binding['path'],result_binding['sha256']);result=load(result_binding['path'])
        if result.get('transport_integrity_status')!='PASS' or result['attempt']['attempt_id']!=row['attempt_id']:raise ValueError('Physical result identity/integrity mismatch')
        results.append(dict(result=result_binding,level_status=result.get('level_screen',{}).get('status'),
            stream_identity_status=result.get('physical_stream_identity_qualification'),processed_tail_status=result.get('processed_source_tail_qualification')))
    if sorted(x['sha256'] for x in summary['completed_attempts'])!=sorted(x['result']['sha256'] for x in results):raise ValueError('Summary result set differs')
    return dict(restoration=restored,summary=binding(Path(batch_dir)/'SUMMARY.json'),results=results,attempt_count=len(results),
        scope='Capture transport and actual restoration only; LIMITED levels and pending route/tail qualification remain explicit')


class CaptureProtocol:
    def __init__(self,identity,protocol_paths,report_root,batch,payload_root,attempts,heartbeat_s=5.):
        self.identity=identity;self.paths={k:Path(v) for k,v in protocol_paths.items()};self.report=Path(report_root);self.batch=batch
        self.payload=Path(payload_root);self.attempts=attempts;self.heartbeat_s=heartbeat_s
        self.closed=threading.Event();self.stop=threading.Event();self.errors=[];self.status='RUNNING';self.progress_count=0;self.checkpoint_count=0
        self.latest={};self.signature=None;self.thread=threading.Thread(target=self.observe,name='s6d-capture-protocol',daemon=True)
        self.stop_delivery=dict(event_set=False,file_relay_delivered=False,file_relay_unresolved=False,errors=[])

    def forward_stop(self,request):
        if not matching_identity(request,self.identity):return False
        self.stop.set();self.stop_delivery['event_set']=True;target=self.report/'STOP_REQUEST.json'
        try:
            if not target.exists():
                try:save(target,dict(schema='s6d-owner-stop.v1',**self.identity,request='STOP_AND_RESTORE',reason=request.get('reason'),created_utc=utc()),True)
                except FileExistsError:pass
            self.stop_delivery['file_relay_delivered']=target.exists()
            self.stop_delivery['file_relay_unresolved']=not self.stop_delivery['file_relay_delivered']
        except BaseException as exc:
            self.stop_delivery['file_relay_unresolved']=True;self.stop_delivery['errors'].append(repr(exc))
            self.errors.append('STOP file relay failed; in-memory stop event set: '+repr(exc))
        return True

    def final_stop_check(self):
        if self.paths['stop'].exists():
            try:self.forward_stop(load(self.paths['stop']))
            except (json.JSONDecodeError,PermissionError) as exc:
                self.stop.set();self.stop_delivery['event_set']=True;self.stop_delivery['file_relay_unresolved']=True
                self.errors.append('Unresolved STOP document during finalization: '+repr(exc))
        if self.stop.is_set() or self.errors:raise RuntimeError('STOP or unresolved protocol error prevents COMPLETE')

    def progress(self):
        if self.closed.is_set() or self.stop.is_set():return
        ledger_path=self.report/'physical_ledger.json';rows=[]
        if ledger_path.exists():
            try:rows=[r for r in load(ledger_path).get('passes',[]) if r.get('batch')==self.batch]
            except (json.JSONDecodeError,PermissionError):return # Atomic writer retry on next cycle; partial content is not progress.
        files=[]
        for attempt in self.attempts:
            if self.closed.is_set() or self.stop.is_set():return
            folder=self.payload/'beam_bank'/attempt['case_id']/attempt['profile']/attempt['attempt_id']
            for relative in ('input_packed.pcm24','configuration.json','native_packed.wav','capture_metadata.json','telemetry/received_telemetry.jsonl','telemetry/native/transactions.tsv','case_result.json'):
                if self.closed.is_set() or self.stop.is_set():return
                p=folder/relative
                if p.exists():
                    stat=p.stat();files.append((attempt['attempt_id'],relative,stat.st_size,stat.st_mtime_ns))
        batch_dir=self.report/'hardware_batches'/self.batch
        stages=[]
        for name in ('owner_acquired.json','initial_state.json','restoration.json','SUMMARY.json'):
            if self.closed.is_set() or self.stop.is_set():return
            if (batch_dir/name).exists():stages.append(name)
        signature=(tuple((r.get('attempt_id'),r.get('status')) for r in rows),tuple(files),tuple(stages))
        if signature!=self.signature:
            self.progress_count+=1;self.signature=signature
        self.checkpoint_count+=1
        self.latest=dict(ledger_attempts=len(rows),closed_attempts=sum(r.get('status') in ('PASS','FAIL') for r in rows),
            charged_playback_seconds=sum(r.get('charged_playback_s',0) for r in rows),owner_artifacts_present=stages,
            native_pcm_file_bytes=sum(f[2] for f in files if f[1]=='native_packed.wav'),
            telemetry_file_bytes=sum(f[2] for f in files if f[1].startswith('telemetry/')),
            observed_file_count=len(files),interpretation='Durable file/ledger progress, not source cursor, acoustic time or heartbeat count')

    def heartbeat(self):
        save(self.paths['heartbeat'],dict(**self.identity,utc=utc(),status=self.status,progress_count=self.progress_count,
            checkpoint_count=self.checkpoint_count,progress=self.latest,queue_age_s=None,stop_requested=self.stop.is_set(),stop_delivery=self.stop_delivery,errors=self.errors))

    def observe(self):
        next_heartbeat=0.;next_progress=0.
        try:
            while not self.closed.is_set():
                if self.paths['stop'].exists():
                    try:self.forward_stop(load(self.paths['stop']))
                    except (json.JSONDecodeError,PermissionError):pass
                now=time.monotonic()
                if now>=next_progress:self.progress();next_progress=now+1.
                if now>=next_heartbeat:self.heartbeat();next_heartbeat=now+self.heartbeat_s
                self.closed.wait(.1)
        except BaseException as exc:
            self.errors.append(repr(exc));self.forward_stop(dict(self.identity,reason='Protocol observer failure; restore owned hardware'))

    def close(self):
        self.closed.set();self.thread.join(3)
        if self.thread.is_alive():raise RuntimeError('Capture protocol observer did not close')


def execute(owner_path,owner_sha256,plan_path,plan_sha256,authorization_path,authorization_sha256,batch,attempt_ids):
    owner_binding=binding(owner_path,owner_sha256);plan_binding=binding(plan_path,plan_sha256);authorization_binding=binding(authorization_path,authorization_sha256)
    plan=load(plan_path)
    identity=dict(run_id=os.environ['S6D_RUN_ID'],job_id=os.environ['S6D_JOB_ID'],child_run_id=os.environ['S6D_CHILD_RUN_ID'],
        pid=os.getpid(),creation_time=psutil.Process().create_time(),admission_unix=time.time())
    paths={key:os.environ[env] for key,env in (('heartbeat','S6D_HEARTBEAT_PATH'),('completion','S6D_COMPLETION_PATH'),('stop','S6D_STOP_REQUEST_PATH'),('restoration','S6D_RESTORATION_PATH'))}
    if any(Path(paths[k]).exists() for k in ('heartbeat','completion','restoration')):raise ValueError('Fresh protocol outputs required')
    if not batch or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in batch):raise ValueError('Safe batch ID required')
    if (Path(plan['report_root'])/'hardware_batches'/batch).exists():raise ValueError('Fresh owner batch required; prior receipts cannot prove this admission')
    selected=[a for a in plan['attempts'] if a['attempt_id'] in attempt_ids]
    if len(selected)!=len(attempt_ids) or len(set(attempt_ids))!=len(attempt_ids):raise ValueError('Exact unique attempts required')
    # This is the original maintained SIM/scripts location, verified against V3;
    # the review snapshot has different relative roots and is not an execution root.
    sys.path.insert(0,str(Path(owner_binding['path']).parent))
    spec=importlib.util.spec_from_file_location('s6d_capture_owner_bound',owner_binding['path']);owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
    owner.validate_plan(Path(plan_path),Path(authorization_path)) # Pure admission, no device/audio imports.
    bridge=CaptureProtocol(identity,paths,plan['report_root'],batch,plan['payload_root'],selected);bridge.thread.start()
    failure=None;proof=None;restore=None
    try:
        owner.execute(Path(plan_path),Path(authorization_path),batch,attempt_ids,external_stop_event=bridge.stop)
        ledger=load(Path(plan['report_root'])/'physical_ledger.json')
        proof=completion_proof(Path(plan['report_root'])/'hardware_batches'/batch,ledger,attempt_ids,identity,plan_binding,authorization_binding)
        if bridge.stop.is_set() or bridge.errors:raise RuntimeError('STOP or protocol observer error prevents COMPLETE')
    except BaseException as exc:failure=repr(exc)
    finally:
        try:bridge.close()
        except BaseException as exc:failure=failure or repr(exc)
        try:bridge.final_stop_check()
        except BaseException as exc:failure=failure or repr(exc)
        try:
            ledger=load(Path(plan['report_root'])/'physical_ledger.json')
            restore=restoration_proof(Path(plan['report_root'])/'hardware_batches'/batch,ledger,identity)
            save(paths['restoration'],dict(**identity,status='RESTORED',verified=True,created_utc=utc(),proof=restore),True)
        except BaseException as exc:failure=failure or 'Restoration proof: '+repr(exc)
        bridge.status='FAILED' if failure else 'FINALIZING';bridge.heartbeat()
    result=dict(**identity,status='FAILED' if failure else 'COMPLETE',created_utc=utc(),failure=failure,plan=plan_binding,authorization=authorization_binding,owner=owner_binding,
        wrapper=binding(__file__),capture_same_process=True,semantic_checks=proof,restoration=restore,
        protocol_observer_closed=not bridge.thread.is_alive(),protocol_observer_errors=bridge.errors,progress_count=bridge.progress_count,
        stop_delivery=bridge.stop_delivery,shared_stop_event_hook=True,
        physical_qualification_complete=False,scope='Only named capture integrity and exact owned restoration; no aggregate S6D acceptance')
    if failure is None:
        try:save(paths['completion'],result,True,before_publish=bridge.final_stop_check)
        except BaseException as exc:
            failure=repr(exc);result.update(status='FAILED',failure=failure,stop_delivery=bridge.stop_delivery,protocol_observer_errors=bridge.errors)
    if failure is not None:save(Path(paths['completion']).with_name('CAPTURE_BRIDGE_FAILURE.json'),result,True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for field in ('owner','plan','authorization'):p.add_argument('--'+field,type=Path,required=True);p.add_argument('--'+field+'-sha256',required=True)
    p.add_argument('--batch',required=True);p.add_argument('--attempt-ids',nargs='+',required=True);a=p.parse_args()
    result=execute(a.owner,a.owner_sha256,a.plan,a.plan_sha256,a.authorization,a.authorization_sha256,a.batch,a.attempt_ids)
    print(json.dumps(dict(status=result['status'],failure=result['failure'],attempts=len(a.attempt_ids))),flush=True)
    raise SystemExit(0 if result['status']=='COMPLETE' else 2)
