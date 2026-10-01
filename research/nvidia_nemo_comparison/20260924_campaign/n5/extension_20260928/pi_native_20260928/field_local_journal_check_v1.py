"""Native metadata qualification only; README_FIELD_LOCAL_JOURNAL_V1.md."""
import os,sys,resource,signal,json
from pathlib import Path
os.sched_setaffinity(0,{3})
resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE,(33554432,)*2)
signal.alarm(20);sys.dont_write_bytecode=True
def ticks(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None
owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
print(json.dumps(dict(event='OWNER',owner=owner)),flush=True)
request=json.loads(sys.stdin.buffer.read(65537))
if set(request)!={'root','policy_sha256','operation','phase'}:raise ValueError('Exact request')
from field_local_release_files_v2 import Journal
from field_operator_session_ledger_v4 import identity,file_pin
root=Path(request['root']);phase=request['phase']
if phase not in ('create','reopen','fault','fenced'):raise ValueError('Known qualification phase')
def open_journal(create=False):
    return Journal(root,request['policy_sha256'],request['operation'],create=create)
if phase=='fenced':
    before=file_pin(root/'launches/launch-03/OWNER.json.pending')
    try:open_journal()
    except RuntimeError as e:
        if str(e)!='Preserved incomplete publication; no retry':raise
    else:raise AssertionError('Pending journal reopened')
    assert file_pin(root/'launches/launch-03/OWNER.json.pending')==before
    result=dict(phase=phase,pending_preserved=True,reopen_rejected=True,pending=before)
else:
    journal=open_journal(create=phase=='create')
    try:
        if phase in ('create','reopen'):
            n=1 if phase=='create' else 2
            before={p.relative_to(root).as_posix():file_pin(p) for p in (root/'launches').rglob('*.json')}
            journal.publish('launches/launch-%02d'%n,'OWNER',dict(owner=identity(),purpose='METADATA_QUALIFICATION_ONLY'))
            journal.publish('launches/launch-%02d'%n,'EXIT',dict(status='METADATA_WORK_FINISHED',capture=False,application_started=False))
            for rel,pin in before.items():assert file_pin(root/rel)==pin
            result=dict(phase=phase,launch=n,earlier_pins_preserved=before,files=journal.inspect()['launches/launch-%02d'%n])
        else:
            before={p.relative_to(root).as_posix():file_pin(p) for p in (root/'launches').rglob('*.json')}
            original=os.write;calls=[]
            def short_write(fd,data):
                calls.append(len(data))
                if len(calls)==1:return original(fd,data[:3])
                raise OSError('INJECTED_METADATA_WRITE_FAILURE')
            os.write=short_write
            try:
                try:journal.publish('launches/launch-03','OWNER',dict(owner=identity(),purpose='INJECTED_METADATA_FAILURE_ONLY'))
                except OSError as e:
                    if str(e)!='INJECTED_METADATA_WRITE_FAILURE':raise
                else:raise AssertionError('Injected write succeeded')
            finally:os.write=original
            pending=root/'launches/launch-03/OWNER.json.pending'
            assert journal.failed is True and pending.stat().st_size==3
            assert not (root/'launches/launch-03/OWNER.json').exists()
            # Read-only fault-latch check; never repeat the rejected mutation.
            try:journal.inspect()
            except RuntimeError as e:
                if str(e)!='Closed or fault-latched journal':raise
            else:raise AssertionError('Fault latch cleared')
            for rel,pin in before.items():assert file_pin(root/rel)==pin
            result=dict(phase=phase,injected_write_calls=calls,pending=file_pin(pending),fault_latched=True,earlier_pins_preserved=before)
    finally:journal.close()
    assert journal.fd is None
print(json.dumps(dict(event='RESULT',owner=owner,result=result)),flush=True)
