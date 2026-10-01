"""Actual runtime census/export SSH wrapper; README_FIELD_RUNTIME_EXPORT_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
from datetime import datetime,timezone
sys.dont_write_bytecode=True

CLOSURE=r'''import os,sys,resource,signal,json
from pathlib import Path
os.sched_setaffinity(0,{3})
resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
signal.alarm(10)
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
me=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
print(json.dumps(dict(utility_owner=me)),flush=True)
raw=sys.stdin.buffer.read(4097);assert 0<len(raw)<=4096
owners=json.loads(raw);assert type(owners) is list and 1<=len(owners)<=16
rows=[]
for who in owners:
 assert type(who) is dict and set(who)=={'pid','start_ticks','boot_id'}
 assert type(who['pid']) is int and who['pid']>0 and type(who['start_ticks']) is int and who['start_ticks']>0
 observed=ticks(who['pid']);assert who['boot_id']!=boot or observed!=who['start_ticks']
 rows.append(dict(owner=who,observed_start_ticks=observed,exact_alive=False))
print(json.dumps(dict(owners=rows,utility_owner=me)),flush=True)
'''

class Metadata:
    """Original independent 2MiB metadata, 1MiB failure and 512KiB closure groups."""
    def __init__(self,root,recordings):
        self.root=Path(root);self.root.mkdir()
        self.used={'metadata':0,'failure':0,'closure':0}
        self.caps={'metadata':2097152,'failure':1048576,'closure':524288}
        self.names={n:('metadata',cap) for n,cap in {
            'ADMISSION.json':262144,'REGISTERED_OWNER.json':512,'EARLY_OWNER.json':512,
            'PREFLIGHT.json':16384,'CENSUS_INDEX.json':65536,'RESULT.json':65536,
            'BACKUP.json':65536,'GRAPH.json':16384,'PARTITION_metadata.json':262144}.items()}
        for n in range(1,recordings+1):self.names['PARTITION_recording-%02d.json'%n]=('metadata',262144)
        for n in ('TRANSPORT.json','ERROR.json','STDERR.bin','STOP.json','STOP_STDOUT.bin','STOP_STDERR.bin'):
            self.names[n]=('failure',65536)
        for n in ('CLOSURE_PHASE.json','CLOSURE_STDOUT.bin','CLOSURE_STDERR.bin','UTILITY_ABSENCE.json',
                  'UTILITY_ABSENCE_STDOUT.bin','UTILITY_ABSENCE_STDERR.bin','NATIVE_CLOSURE.json','HOST_LOGICAL_CLOSURE.json'):
            self.names[n]=('closure',65536)
    def write(self,name,raw):
        if type(raw) is not bytes or name not in self.names:raise ValueError('Exact metadata slot')
        group,cap=self.names[name]
        if len(raw)>cap or self.used[group]+len(raw)>self.caps[group]:raise ValueError('Independent host metadata quota')
        self.used[group]+=len(raw)
        with (self.root/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short metadata write')
            stream.flush();os.fsync(stream.fileno())
        if (self.root/name).read_bytes()!=raw:raise OSError('Metadata readback')
    def json(self,name,value):
        self.write(name,json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--envelope',type=Path,required=True)
    ap.add_argument('--owner-receipt',type=Path,required=True)
    args=ap.parse_args();me=psutil.Process()
    owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    raw=json.dumps(owner,separators=(',',':')).encode()
    with args.owner_receipt.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    if args.owner_receipt.read_bytes()!=raw:raise OSError('Actual early host registration')
    from field_runtime_policy_v3 import validate,encoded,digest,timestamp,identity
    from field_runtime_auxiliary_v1 import analyze,strict_json
    from field_runtime_transport_v1 import run,TransportFailure
    from field_runtime_preservation_io_v1 import read_census,receive_files,limits
    from field_operator_broker_host_v2 import checked_pins,process_phase
    from field_host_budget_v1 import floors,real
    from field_operator_broker_streamed_mirror_v1 import ancestors
    from dispatch_b01_stack_v2 import SSH
    real(args.envelope)
    if args.envelope.stat().st_size>524288:raise ValueError('Bounded local envelope')
    envelope=json.loads(args.envelope.read_bytes())
    if type(envelope) is not dict or set(envelope)!={'request','modules','loader','host'}:raise ValueError('Exact host/native envelope')
    request=envelope['request'];modules=envelope['modules'];host=envelope['host'];admission=request['admission']
    fields={'output','destination','source_pins','coordinator_sha256','owner_precheck','owner_precheck_sha256',
            'maximum_metadata_bytes','expected_census','expected_census_sha256'}
    if type(host) is not dict or set(host)!=fields or host['maximum_metadata_bytes']!=3670016:
        raise ValueError('Exact original independent host groups')
    policy=validate(request['policy']);manifest=request['manifest'];bound=limits(policy)
    end=timestamp(admission['expires_utc']);now=datetime.now(timezone.utc)
    if not 150<=(end-now).total_seconds()<=600 or end>timestamp('2026-10-02T14:14:20+00:00'):
        raise ValueError('Full copy/closure reserve before current hard deadline')
    if digest(policy)!=admission['policy_sha256'] or digest(manifest)!=admission['manifest_sha256']:
        raise ValueError('Policy/manifest pins')
    if admission['mirror_maximum_bytes']!=bound['maximum_bytes']:raise ValueError('All independently reserved copies')
    phase=admission['phase'];unit=admission['unit']
    if phase not in ('census','export') or not re.fullmatch('jp-runtime-'+phase+r'-v[1-9][0-9]*[.]service',unit):
        raise ValueError('One exact dedicated read-only service')
    here=Path(__file__).absolute().parent
    pins=checked_pins(host['source_pins'])
    required={str(here/(n+'.py')) for n in (*modules,'field_runtime_auxiliary_v1','field_runtime_transport_v1',
        'field_local_manager_bootstrap_v1','field_operator_broker_host_v2','dispatch_b01_stack_v2','mirror_field_runtime_v1')}
    if not required<=pins or hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=host['coordinator_sha256']:
        raise ValueError('All actual coordinator/helper/native source pins')
    if any((here/(n+'.py')).read_bytes().decode()!=s for n,s in modules.items()):
        raise ValueError('Exact backed native source graph')
    if (here/'field_runtime_auxiliary_v1.py').read_bytes().decode()!=envelope['loader']:
        raise ValueError('Exact backed auxiliary loader')
    graph=analyze(modules,admission['module_sha256'])
    pre=Path(host['owner_precheck']);real(pre)
    if pre.stat().st_size>16384 or hashlib.sha256(pre.read_bytes()).hexdigest()!=host['owner_precheck_sha256']:
        raise ValueError('Compact independently pinned full host owner/lifetime inspection')
    preread=strict_json(pre.read_bytes())
    if set(preread)!={'schema','observed_utc','owner_paths_read','lifetime_paths_read','inventory_sha256','alive_owners'}:
        raise ValueError('Exact compact preread receipt')
    if preread['schema']!='just-peachy.runtime-host-precheck.v1' or preread['alive_owners']:
        raise ValueError('No other live owned host coordinator')
    if not 0<=(now-timestamp(preread['observed_utc'])).total_seconds()<=120:
        raise ValueError('Fresh preread before this dispatch')
    for name in ('owner_paths_read','lifetime_paths_read'):
        if type(preread[name]) is not int or preread[name]<1:raise ValueError('All owner/lifetime sources read')
    if not re.fullmatch('[0-9a-f]{64}',preread['inventory_sha256']):raise ValueError('Full preread digest')
    prior=None
    if phase=='export':
        p=Path(host['expected_census']);real(p)
        if p.stat().st_size>65536 or hashlib.sha256(p.read_bytes()).hexdigest()!=host['expected_census_sha256']:
            raise ValueError('Pinned independently completed census')
        prior=strict_json(p.read_bytes())
        if prior['status']!='CLOSED_RUNTIME_CENSUS' or prior['policy_sha256']!=digest(policy) or prior['global_manifest_sha256']!=request['expected_index_sha256']:
            raise ValueError('Actual prior complete census binding')
    elif host['expected_census'] is not None or host['expected_census_sha256'] is not None:
        raise ValueError('Census is independent of a caller-provided success hash')
    output=Path(host['output']).absolute();destination=Path(host['destination']).absolute()
    if destination!=output.with_name(output.name+'-mirror'):raise ValueError('One fresh sibling mirror destination')
    if output.exists() or destination.exists():raise ValueError('No consumed/failed output reuse')
    ancestors(output.parent);real(output.parent,True)
    floors(bound['maximum_bytes']+host['maximum_metadata_bytes'])
    payload=encoded({k:envelope[k] for k in ('request','modules','loader')})
    if len(payload)>262144:raise ValueError('Original framed request cap')
    store=Metadata(output,policy['allocation']['recordings'])
    store.json('REGISTERED_OWNER.json',owner);store.json('ADMISSION.json',dict(request=request,host=host))
    store.json('GRAPH.json',graph)
    bootstrap=(here/'field_local_manager_bootstrap_v1.py').read_bytes().decode()
    command=['systemd-run','--user','--unit='+unit,'--description=JustPeachy-runtime-'+phase,'--wait','--pipe','--quiet']
    for prop in ('CPUQuota=200%','AllowedCPUs=2-3','TasksMax=64','LimitAS=134217728','LimitSTACK=1048576',
                 'LimitFSIZE=0','LimitCORE=0','RuntimeMaxSec=90','TimeoutStopSec=10','Nice=10'):
        command+=['-p',prop]
    command+=['--setenv=OPENBLAS_NUM_THREADS=1','--setenv=OMP_NUM_THREADS=1','--setenv=CUDA_VISIBLE_DEVICES=',
              'taskset','-c','2,3','python3','-u','-B','-c',bootstrap,hashlib.sha256(payload).hexdigest()]
    stopped=False
    def guard():
        if datetime.now(timezone.utc)>=end:raise TimeoutError('Admission expired')
        floors()
    def persist_early(native):
        store.json('EARLY_OWNER.json',identity(native));return True
    def stop_owned():
        nonlocal stopped
        if stopped:return
        stopped=True
        value=process_phase(SSH+['systemctl --user stop --no-block '+unit],timeout=10,maximum=65536)
        out=value.pop('stdout');err=value.pop('stderr')
        store.write('STOP_STDOUT.bin',out);store.write('STOP_STDERR.bin',err);store.json('STOP.json',value)
    def clean_phase(value):
        return value['returncode']==0 and value['fault'] is None and not value['overflow'] and value['readers_joined'] and value['ssh_reaped']
    def verify_closed(native):
        identity(native)
        value=process_phase(SSH+['exec '+shlex.join(['python3','-u','-B','-c',CLOSURE])],
                            payload=encoded([native]),timeout=15,maximum=65536)
        out=value.pop('stdout');err=value.pop('stderr')
        store.write('CLOSURE_STDOUT.bin',out);store.write('CLOSURE_STDERR.bin',err);store.json('CLOSURE_PHASE.json',value)
        if not clean_phase(value):raise RuntimeError('Exact exporter closure utility failed')
        lines=out.splitlines()
        if len(lines)!=2:raise ValueError('Registered closure utility envelope')
        early=strict_json(lines[0]);closed=strict_json(lines[1])
        utility=identity(early['utility_owner'])
        if set(early)!={'utility_owner'} or closed['utility_owner']!=utility or closed['owners'][0]['owner']!=native or closed['owners'][0]['exact_alive'] is not False:
            raise ValueError('Actual closure identity mismatch')
        absence=process_phase(SSH+['test ! -e /proc/'+str(utility['pid'])],timeout=10,maximum=65536)
        out=absence.pop('stdout');err=absence.pop('stderr')
        store.write('UTILITY_ABSENCE_STDOUT.bin',out);store.write('UTILITY_ABSENCE_STDERR.bin',err);store.json('UTILITY_ABSENCE.json',absence)
        if not clean_phase(absence):raise RuntimeError('Closure utility exact absence required')
        closed['utility_pid_absent_after_ssh']=True;store.json('NATIVE_CLOSURE.json',closed)
        return True
    def consume(channel,native,close):
        ready=channel.json();store.json('PREFLIGHT.json',ready)
        if ready.get('owner')!=native or ready.get('source')!=policy['manager_root'] or ready.get('physical_closure_claimed') is not False:
            raise ValueError('Actual source/owner binding')
        if ready.get('type')=='NO_TARGET_ROOT':
            if phase!='census':raise ValueError('Absent export source')
            close()
            return dict(status='CLOSED_ABSENT_RUNTIME_CENSUS',policy_sha256=digest(policy),source=policy['manager_root'])
        if ready.get('type')!='READY' or ready.get('phase')!=phase:raise ValueError('Exact phase readiness')
        channel.send_json(dict(ack=native))
        expected=read_census(channel,policy,manifest,guard)
        for name,part in expected['plan']['partitions'].items():store.json('PARTITION_'+name+'.json',part)
        store.json('CENSUS_INDEX.json',dict(index=expected['plan']['index'],ownership=expected['ownership']))
        if phase=='census':
            close()
            return dict(status='CLOSED_RUNTIME_CENSUS',policy_sha256=digest(policy),
                global_manifest_sha256=expected['plan']['global_manifest_sha256'],files=expected['plan']['files'],
                source=policy['manager_root'],closed_utc=datetime.now(timezone.utc).isoformat())
        if expected['plan']['global_manifest_sha256']!=request['expected_index_sha256']:raise ValueError('Prior complete census drift')
        def source_closed():
            close();return True
        return receive_files(channel,destination,expected,policy,manifest,guard,source_closed)
    receipt=None;result=None;error=None
    try:
        result,receipt=run(SSH+['exec '+shlex.join(command)],payload,policy=policy,
            persist_early=persist_early,consume=consume,verify_closed=verify_closed,stop_owned=stop_owned,guard=guard)
        store.json('RESULT.json',result)
        if phase=='export':store.json('BACKUP.json',result)
    except TransportFailure as exc:
        receipt=exc.receipt;error=str(exc);store.json('ERROR.json',dict(error=error))
    finally:
        if receipt is not None:
            stderr=receipt.pop('stderr')
            store.write('STDERR.bin',stderr);store.json('TRANSPORT.json',receipt)
        store.json('HOST_LOGICAL_CLOSURE.json',dict(owner=owner,success=error is None and result is not None,
            transport_receipt_present=receipt is not None,physical_host_death_claimed=False))
    if error:raise RuntimeError(error)
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()

