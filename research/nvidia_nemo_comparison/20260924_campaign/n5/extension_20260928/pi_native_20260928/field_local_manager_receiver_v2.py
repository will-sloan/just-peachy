"""Actual manager census/export transport. README_FINAL_MANAGER_COPY_V1.md."""
import hashlib
import json
import re
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from field_host_budget_v1 import HostStore, encoded, floors
from field_local_manager_transport_v1 import run, TransportFailure
from field_local_manager_owners_v1 import key
from field_operator_broker_host_v2 import process_phase

MANAGER_LIMITS={'metadata':(786432,262144,24),'failure':(131072,65536,8),'closure':(65536,32768,8)}
CLOSURE_LIMITS={'metadata':(65536,16384,24),'failure':(65536,32768,8),'closure':(65536,32768,8)}
# Master832KiB + broker1408KiB + manager1216KiB + closure448KiB:
# 3904KiB + four lock bytes, strictly below the original4MiB host metadata.
METADATA_PARTITION=dict(master=851969,broker=1441793,manager=1245185,closure=458753)
assert sum(METADATA_PARTITION.values()) < 4194304

CLOSURE_SOURCE=r"""
import os,sys,json,struct,resource,signal
from pathlib import Path
os.sched_setaffinity(0,{3})
resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE,(0,)*2)
signal.alarm(10)
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
def frame(v):
 raw=json.dumps(v,separators=(',',':')).encode()
 if len(raw)>16384:raise ValueError('Closure frame')
 sys.stdout.buffer.write(struct.pack('!I',len(raw))+raw);sys.stdout.buffer.flush()
frame(dict(early_owner=owner))
def exact(n):
 out=bytearray()
 while len(out)<n:
  v=sys.stdin.buffer.read(n-len(out))
  if not v:raise EOFError('Closure input')
  out.extend(v)
 return bytes(out)
n=struct.unpack('!I',exact(4))[0]
if not 1<=n<=16384:raise ValueError('Closure input ceiling')
rows=json.loads(exact(n))
frame(dict(type='HELLO',owner=owner))
if type(rows) is not list or not 1<=len(rows)<=8:raise ValueError('Exact bounded owner list')
for row in rows:
 if type(row) is not dict or set(row)!={'pid','start_ticks','boot_id'}:raise ValueError('Owner fields')
 if any(type(row[k]) is not int or row[k]<=0 for k in ('pid','start_ticks')):raise ValueError('Owner integers')
 if type(row['boot_id']) is not str or len(row['boot_id'])!=36:raise ValueError('Boot identity')
 if row['boot_id']==boot and ticks(row['pid'])==row['start_ticks']:raise RuntimeError('Exact owner remains alive')
frame(dict(type='CLOSED',owners=rows,utility_owner=owner))
"""

def clean(receipt):
    return {k:v for k,v in receipt.items() if k!='stderr'}

def command(ssh,unit,source,payload_sha):
    if not re.fullmatch(r'jp-field-manager-(census|export)-v[1-9][0-9]*[.]service',unit):
        raise ValueError('Exact export unit')
    argv=['systemd-run','--user','--unit='+unit,'--description=JustPeachy-manager-export',
          '--wait','--pipe','--quiet']
    for prop in ('CPUQuota=200%','AllowedCPUs=2,3','TasksMax=64','LimitAS=134217728',
                 'LimitSTACK=1048576','LimitFSIZE=0','LimitCORE=0','RuntimeMaxSec=90',
                 'TimeoutStopSec=10','Nice=10'):
        argv+=['-p',prop]
    argv+=['--setenv=OPENBLAS_NUM_THREADS=1','--setenv=OMP_NUM_THREADS=1',
           '--setenv=CUDA_VISIBLE_DEVICES=','python3','-u','-B','-c',source,payload_sha]
    return ssh+['exec '+shlex.join(argv)]

def session(output,closure_output,owner,admission,modules,loader,bootstrap,ssh,*,lifecycle_refresh):
    """One full census then export, with separate bounded closure publications.

    Caller supplies actual fresh admission/source pins, complete prior-owner
    review and full617760944-byte joint reservation. No allowance is issued.
    lifecycle_refresh is the reviewed read-only current-baseline inspector;
    it must return an actual fresh observation, never a retimestamped receipt.
    """
    from field_local_auxiliary_v1 import analyze
    from field_local_manager_owners_v1 import lifecycle
    from field_local_manager_ssh_mirror_v2 import receive
    from field_local_manager_tree_v1 import validate
    a=dict(admission)
    end=datetime.fromisoformat(a['expires_utc'])
    if end>datetime.fromisoformat('2026-10-01T16:14:58+00:00'):
        raise ValueError('Effective user deadline')
    if not 220<=(end-datetime.now(timezone.utc)).total_seconds()<=600:
        raise ValueError('Two phases plus closure/backup reserve')
    binding=a['manager_binding'];policy=validate(binding)
    if policy['allocation']['combined_request_bytes']!=617760944 or a['mirror_maximum_bytes']!=155669036:
        raise ValueError('Full original independent allocation')
    analyze(modules,a['module_sha256'])
    floors(policy['allocation']['host_maximum_bytes'])
    store=HostStore(output,MANAGER_LIMITS).create({'ADMISSION.json':encoded(a),'REGISTERED_OWNER.json':encoded(owner)})
    closure_store=HostStore(closure_output,CLOSURE_LIMITS).create({'REGISTERED_OWNER.json':encoded(owner)})
    receipts=[];observed=[];early=[];result=None
    def guard():
        if datetime.now(timezone.utc)>=end:raise TimeoutError('Joint operation expired')
        floors()
    def closure(remote_owner,index):
        slot=('JOB_ENVELOPE.json','PREFLIGHT.json')[index]
        def persist(utility):
            closure_store.json(slot,dict(utility_owner=utility,checking=remote_owner))
            observed.append(utility)
            return True
        def absent(utility):
            # No new Python owner: this bounded shell only checks exact PID
            # absence after natural reap; reuse of that PID conservatively fails.
            r=process_phase(ssh+['test ! -e /proc/'+str(utility['pid'])],timeout=10,maximum=4096)
            if r['returncode'] or r['fault'] or not r['readers_joined'] or not r['ssh_reaped']:
                raise RuntimeError('Closure utility absence unproved')
            receipts.append(dict(phase='utility-absence',**{k:v for k,v in r.items() if k not in ('stdout','stderr')},
                                 stdout_hex=r['stdout'].hex(),stderr_hex=r['stderr'].hex()))
            return True
        def consume(channel,utility,close):
            value=channel.json()
            if value!=dict(type='CLOSED',owners=[remote_owner],utility_owner=utility):
                raise ValueError('Exact closure result')
            close()
            return value
        value,r=run(ssh+['exec python3 -u -B -c '+shlex.quote(CLOSURE_SOURCE)],
                    encoded([remote_owner]),persist_early=persist,consume=consume,
                    verify_closed=absent,stop_owned=lambda:None,guard=guard,timeout=20)
        receipts.append(dict(phase='exact-closure',**clean(r)))
        closure_store.write(('worker.raw','coordinator.raw')[index],r['stderr'])
        closure_store.json(('worker-closure.json','coordinator-closure.json')[index],value)
        return True
    tree=None
    try:
        for index,phase in enumerate(('census','export')):
            life=lifecycle_refresh()
            life_sha=hashlib.sha256(encoded_canonical(life)).hexdigest()
            lifecycle(life,life_sha)
            a.update(phase=phase,lifecycle=life,lifecycle_sha256=life_sha,
                     unit=admission['unit'].replace('-census-','-'+phase+'-'))
            request=dict(admission=a,files=None if tree is None else tree['files'])
            payload=encoded_canonical(dict(request=request,modules=modules,loader=loader))
            if len(payload)>262144:raise ValueError('Original bootstrap request ceiling')
            def persist(remote):
                if remote['boot_id']!=life['boot_id']:raise ValueError('Exporter current boot')
                early.append(remote)
                store.json(('JOB_ENVELOPE.json','PREFLIGHT.json')[index],dict(early_owner=remote,phase=phase))
                return True
            def consume(channel,remote,close):
                value=channel.json()
                if value.get('owner')!=remote or value.get('source')!=policy['root']:
                    raise ValueError('Exact exporter source/owner')
                if phase=='census':
                    if value.get('type') not in ('CENSUS','NO_TARGET_ROOT'):raise ValueError('Census frame')
                    close()
                    store.json('CENSUS.json',value)
                    return value
                if value.get('type')!='READY':raise ValueError('Export readiness')
                store.json('REVIEW.json',value)
                channel.send_json(dict(ack=remote))
                return receive(store,Path(output).with_name(Path(output).name+'-mirror'),channel,tree['files'],
                    deadline=time.monotonic()+100,maximum_bytes=a['mirror_maximum_bytes'],
                    verify_process_closed=close,source_label=policy['root'],manager_binding=binding)
            def stop():
                process_phase(ssh+['systemctl --user stop --no-block '+a['unit']],timeout=10,maximum=4096)
            result,r=run(command(ssh,a['unit'],bootstrap,hashlib.sha256(payload).hexdigest()),payload,
                         persist_early=persist,consume=consume,verify_closed=lambda o:closure(o,index),
                         stop_owned=stop,guard=guard,timeout=105)
            receipts.append(dict(phase=phase,**clean(r)))
            store.write(('worker.raw','coordinator.raw')[index],r['stderr'])
            if phase=='census':
                tree=result
                if tree['type']=='NO_TARGET_ROOT':break
        final=dict(status='NO_TARGET_ROOT' if tree['type']=='NO_TARGET_ROOT' else 'EXACT_MANAGER_PC_COPY',
                   result=result if tree['type']!='NO_TARGET_ROOT' else None,
                   actual_export_owners=early,closure_utility_owners=observed,
                   transports=receipts,production_qualified=False)
        store.json('RESULT.json',final)
        return final
    except TransportFailure as exc:
        # Preserve bounded raw failure even if the native side stopped before
        # READY. An absent BACKUP remains absent; partial tree is never deleted.
        store.failure('review',exc.receipt['stderr'],exc)
        store.json('review-closure.json',dict(transport=clean(exc.receipt),early_owners=early,
                                            utility_owners=observed,backup_certified=False))
        raise

def encoded_canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
