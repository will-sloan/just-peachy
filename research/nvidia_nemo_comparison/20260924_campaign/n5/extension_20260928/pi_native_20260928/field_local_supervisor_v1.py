"""Bounded native journal phases and gate link; README_FIELD_LOCAL_SUPERVISOR_V1.md."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
sys.dont_write_bytecode=True

def validate_binding(value):
    from field_local_release_plan_v1 import validate_research_operation
    if type(value) is not dict or set(value)!={'schema','root','release_sha256','manifest_sha256','recording_slot','launch_slot','operation'}:
        raise ValueError('Exact local gate binding')
    if value['schema']!='just-peachy.local-gate-binding.v1':raise ValueError('Gate binding schema')
    import re
    root=Path(value['root'])
    campaign=Path.home()/'JustPeachy/research/nemotron-20260928'
    if str(root)!=value['root'] or root.parent!=campaign or not re.fullmatch(r'field-local-release-v[1-9][0-9]*',root.name):
        raise ValueError('Canonical finite release root')
    for key in ('release_sha256','manifest_sha256'):
        if type(value[key]) is not str or not re.fullmatch('[0-9a-f]{64}',value[key]):raise ValueError('Exact capsule/policy digest')
    if type(value['recording_slot']) is not str or not re.fullmatch(r'recording-0[1-4]',value['recording_slot']):
        raise ValueError('Exact recording slot')
    if type(value['launch_slot']) is not str or not re.fullmatch(r'launch-(0[1-9]|1[0-6])',value['launch_slot']):
        raise ValueError('Exact launch slot')
    validate_research_operation(value['operation'])
    return value

def _open(binding,create=False):
    from field_local_release_files_v4 import Journal
    b=validate_binding(binding)
    journal=Journal(b['root'],b['release_sha256'],b['operation'],create=create)
    try:
        if journal.release['release_manifest_sha256']!=b['manifest_sha256']:
            raise ValueError('Exact manager capsule binding')
        if b['launch_slot'] not in journal.plan['launch_slots'] or b['recording_slot'] not in journal.plan['recording_slots']:
            raise ValueError('Actually allocated manager slots')
        return journal
    except BaseException:
        journal.close();raise

def _owner(journal,binding,purpose):
    from field_operator_session_ledger_v4 import identity
    return journal.publish('launches/'+binding['launch_slot'],'OWNER',dict(owner=identity(),purpose=purpose))

def _exit(journal,binding,status):
    # Intent written by a living owner. The next process must prove actual death.
    return journal.publish('launches/'+binding['launch_slot'],'EXIT',dict(status=status,exit_is_intent=True))

class GateLink:
    """Open only in the actual external gate; STARTED precedes its app ACK."""
    def __init__(self,binding,source,source_policy_sha256):
        from field_operator_session_ledger_v4 import identity
        self.binding=validate_binding(binding);self.journal=None;self.started_once=False
        journal=_open(self.binding);self.journal=journal
        try:
            slot=self.binding['recording_slot']
            expected=journal.release['recording_roots'][journal.plan['recording_slots'].index(slot)]
            if str(Path(source))!=expected:raise ValueError('Manager-bound source root')
            actual=journal._binding(slot)
            if actual['policy_sha256']!=source_policy_sha256:
                raise ValueError('Manager-bound actual one-slot source policy')
            from field_local_release_files_v4 import read
            policy=read(Path(source)/'RELEASE.json',65536)
            if not (datetime.fromisoformat(journal.operation['issued_utc'])<=datetime.fromisoformat(policy['issued_utc']) and
                    datetime.fromisoformat(policy['expires_utc'])<=datetime.fromisoformat(journal.operation['expires_utc'])):
                raise ValueError('Source lifetime must fit the manager operation')
            if read(Path(source)/'broker/GATE_OWNER.json',16384)!=identity():
                raise ValueError('Only the actual recorded gate may hold this link')
            _owner(journal,self.binding,'LOCAL_GATE_BEFORE_ACK')
        except BaseException:
            journal.close();self.journal=None;raise

    def started(self):
        if self.journal is None or self.started_once:raise RuntimeError('Once-only gate registration')
        self.started_once=True
        return self.journal.recording_started(self.binding['recording_slot'])

    def close(self,status):
        journal=self.journal
        if journal is None:return
        self.journal=None
        try:
            if not journal.failed:
                _exit(journal,self.binding,status)
        finally:journal.close()

def phase(binding,name):
    # Each mutating phase is one fresh process, never reuse an old owner.
    if name not in ('reserve','finish','reopen'):raise ValueError('Exact supervisor phase')
    b=validate_binding(binding)
    journal=_open(b,create=name=='reserve')
    try:
        if name=='reopen':
            observed=journal.inspect()
            rows=observed['recordings/'+b['recording_slot']]
            if set(rows)!={'RESERVED','STARTED','CLOSED','BACKUP'}:
                raise RuntimeError('Read-only reopen requires complete certified recording')
            return dict(status='VERIFIED_REOPEN',recording_slot=b['recording_slot'],native_recovery=False)
        _owner(journal,b,'LOCAL_'+name.upper())
        if name=='reserve':
            from field_local_release_plan_v1 import next_recording
            observed=journal.inspect()
            records={slot:observed['recordings/'+slot] for slot in journal.plan['recording_slots']}
            if next_recording(journal.plan,records)!=b['recording_slot']:raise ValueError('Exact next recording before reservation')
            value=journal.reserve_recording()
            if value['slot']!=b['recording_slot']:raise ValueError('Requested next slot differs')
            status='RESERVED_SOURCE_ABSENT'
        else:
            journal.recording_closed(b['recording_slot'])
            journal.backup_recording(b['recording_slot'])
            value=dict(slot=b['recording_slot'])
            status='ACTUAL_CLOSED_AND_LOCAL_BACKED'
        _exit(journal,b,status)
        return dict(status=status,recording=value,exit_is_intent=True,native_recovery=False)
    finally:journal.close()

def main():
    # This entry is injected/launched only by a fresh reviewed dispatcher.
    # Its first native identity is emitted before project reads/imports.
    import resource,signal
    os.sched_setaffinity(0,{3})
    resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
    resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(33554432,)*2)
    signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(150)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    print(json.dumps(dict(type='OWNER',owner=dict(pid=os.getpid(),boot_id=boot,start_ticks=ticks))),flush=True)
    try:
        raw=sys.stdin.buffer.read(65537)
        if len(raw)>65536:raise ValueError('Bounded supervisor request')
        from field_live_layout_v3 import finite_json
        request=finite_json(raw)
        if type(request) is not dict or set(request)!={'phase','binding'}:raise ValueError('Exact phase request')
        result=phase(request['binding'],request['phase'])
        print(json.dumps(dict(type='RESULT',result=result)),flush=True)
        return 0
    except BaseException as exc:
        print(json.dumps(dict(type='FAILURE',error=type(exc).__name__+': '+str(exc)[:1024])),flush=True)
        return 1

if __name__=='__main__':raise SystemExit(main())
