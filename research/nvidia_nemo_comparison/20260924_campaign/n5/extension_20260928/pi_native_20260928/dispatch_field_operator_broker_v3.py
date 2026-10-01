"""Native broker qualification component; README_FIELD_OPERATOR_BROKER_QUALIFICATION_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import time
sys.dont_write_bytecode=True

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--owner-receipt',type=Path,required=True)
    args=parser.parse_args()
    me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    raw=json.dumps(owner,separators=(',',':')).encode()
    if len(raw)>512:raise ValueError('Early owner slot')
    with args.owner_receipt.open('xb') as f:f.write(raw);f.flush()
    if args.owner_receipt.read_bytes()!=raw:raise IOError('Owner readback')
    from field_host_budget_v1 import HostStore,encoded,floors
    from field_operator_broker_host_v2 import digest,checked_pins,ssh_phase,closed_owners,process_phase
    from field_operator_session_plan_v3 import validate_policy,encoded as canonical
    from field_owner_binding_v1 import pack,decode
    from mirror_field_operator_broker_v2 import MODULES
    here=Path(__file__).absolute().parent
    if args.plan.stat().st_size>1048576:raise ValueError('Plan ceiling')
    plan=json.loads(args.plan.read_bytes());policy=validate_policy(plan['policy'])
    end=datetime.fromisoformat(policy['expires_utc'])
    remaining=lambda:(end-datetime.now(timezone.utc)).total_seconds()
    if not 590<=remaining()<=600 or policy['allocation']['count']!=2:
        raise ValueError('Fresh two-session batch including backup')
    if policy['allocation']['combined_request_bytes']!=604981424:
        raise ValueError('Full independent two-session allocation')
    pins=checked_pins(plan['host_pins'])
    mandatory=(*MODULES,'dispatch_field_operator_broker_v3','mirror_field_operator_broker_v2',
        'field_operator_broker_host_v2','field_operator_broker_initialize_v1','field_operator_broker_census_v2',
        'dispatch_b01_stack_v2','dispatch_geometry_v2')
    if not {str(here/(n+'.py')) for n in mandatory}.issubset(pins) or digest(__file__)!=plan['coordinator_sha256']:
        raise ValueError('All dispatch/receiver/census/helper pins')
    census=Path(plan['census'])
    if str(census) not in pins or time.time()-census.stat().st_mtime>900:raise ValueError('Fresh pinned census')
    for old in plan['prior_host_owners']:
        try:created=psutil.Process(old['pid']).create_time()
        except psutil.NoSuchProcess:created=None
        if created is not None and abs(created-old['create_time'])<.001:raise RuntimeError('Prior healthy coordinator remains')
    request_path=Path(plan['initializer_request'])
    if str(request_path) not in pins or request_path.stat().st_size>4*1024**2:raise ValueError('Pinned initializer request')
    request=json.loads(request_path.read_bytes())
    if request['policy']!=policy or hashlib.sha256(canonical(request['manifest'])).hexdigest()!=policy['release_manifest_sha256']:
        raise ValueError('Whole request policy/manifest')
    config=json.loads(base64.b64decode(request['files']['broker/CONFIG.json'],validate=True))
    root=policy['root'];policy_sha=hashlib.sha256(canonical(policy)).hexdigest()
    python=plan['python']
    if python!='/home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python':
        raise ValueError('Pinned installed Python')
    output=Path(plan['output']).absolute()
    if args.owner_receipt.absolute()!=output.parent/'DISPATCH_EARLY_OWNER.json':
        raise ValueError('Reserved early owner location')
    floors(policy['allocation']['host_maximum_bytes'])
    store=HostStore(output).create({'ADMISSION.json':encoded(plan),'REGISTERED_OWNER.json':encoded(owner)})
    initialized=None;gate=None;tree=None;backup=None;fault=None;stage_owner=None
    success=False;closures=[];census_phase=None
    def good(phase):
        return phase['returncode']==0 and not phase['fault'] and not phase['overflow'] and phase['readers_joined'] and phase['ssh_reaped']
    def clean_phase(phase):
        return {k:v for k,v in phase.items() if k not in ('stdout','stderr')}
    def lines(raw):
        return [json.loads(line) for line in raw.splitlines() if line]
    try:
        source=(here/'field_operator_broker_initialize_v1.py').read_text(encoding='utf-8')
        initialized=ssh_phase([python,'-u','-B','-c',source],payload=canonical(request)+b'\n',timeout=35,maximum=16384)
        store.json('PREFLIGHT.json',dict(phase=clean_phase(initialized),
            stdout_base64=base64.b64encode(initialized['stdout']).decode(),stderr_base64=base64.b64encode(initialized['stderr']).decode()))
        rows=lines(initialized['stdout'])
        if rows and set(rows[0])=={'owner'}:stage_owner=rows[0]['owner']
        if stage_owner is not None:
            observation=closed_owners([stage_owner]);closures.append(observation['utility_owner'])
            store.json('JOB_ENVELOPE.json',dict(stage_closure=observation))
        if not good(initialized) or len(rows)!=2 or rows[1]['owner']!=stage_owner or rows[1]['policy_sha256']!=policy_sha or rows[1]['readback_exact'] is not True:
            raise RuntimeError('Initializer failed; preserve partial root')
        if remaining()<570:raise TimeoutError('Native gate fresh full deadline')
        # 250s host watch +35s Stop leaves >=260s for census/export/closure.
        store.json('LAUNCH.json',dict(root=root,policy_sha256=policy_sha,unit='jp-'+Path(root).name,
            native_gate='field_operator_broker_gate_v4.py',host_wait_seconds=250,cleanup_backup_reserve_seconds=260))
        gate=ssh_phase([python,'-u','-B',root+'/code/field_operator_broker_gate_v4.py',
            '--root',root,'--policy-sha256',policy_sha],timeout=250,stop_unit='jp-'+Path(root).name)
        store.write('worker.raw',gate['stdout']);store.write('coordinator.raw',gate['stderr'])
        if not good(gate):fault='Native gate failed or host boundary reached'
    except BaseException as exc:
        fault=type(exc).__name__+': '+str(exc)[:2048]
    # Closed-tree backup also runs after a failed gate. No claimed success is needed.
    try:
        if initialized is not None:
            if remaining()<260:raise TimeoutError('Census plus full backup reserve exhausted')
            partial=None
            if gate is None and stage_owner is not None:
                from field_operator_broker_partial_v1 import validate
                members={row['path']:row['bytes'] for row in request['manifest']['files']}
                members.update({'RELEASE.json':len(canonical(policy)),'broker/MANIFEST.json':len(canonical(request['manifest'])),
                    'broker/STAGE_OWNER.json':16384})
                partial=dict(source_root=root,policy_sha256=policy_sha,initializer_owner=stage_owner,members=members)
                validate(partial)
            source=(here/'field_operator_broker_census_v2.py').read_text(encoding='utf-8')
            source+='\nprint(json.dumps(collect('+repr(root)+','+repr(policy)+','+repr(policy_sha)+','+repr([stage_owner] if stage_owner else [])+','+repr(partial)+')),flush=True)\n'
            census_phase=ssh_phase([python,'-u','-B','-c',source],timeout=35)
            store.write('review.raw',census_phase['stderr'])
            rows=lines(census_phase['stdout'])
            if rows and set(rows[0])=={'utility_owner'}:
                utility=rows[0]['utility_owner'];observation=closed_owners([utility])
                closures.extend([utility,observation['utility_owner']])
                store.json('worker-closure.json',observation)
            if not good(census_phase) or len(rows)!=2:raise RuntimeError('Closed census failed')
            tree=rows[1];store.json('CENSUS.json',tree)
            if tree['status']=='NO_TARGET_ROOT':
                backup=dict(status='NO_TARGET_PAYLOAD_CREATED',capture_closed=tree['capture_closed'])
            elif tree['status']=='PARTIAL_INITIALIZATION':
                raise RuntimeError('Missing external initializer identity; preserve unresolved tree')
            else:
                if remaining()<180:raise TimeoutError('Receiver full backup reserve')
                manifest_path=output/'metadata/CENSUS.json'
                receiver=here/'mirror_field_operator_broker_v2.py'
                def pin(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=digest(p))
                needed=[here/(n+'.py') for n in (*MODULES,'field_operator_broker_host_v2','mirror_field_operator_broker_v2','dispatch_b01_stack_v2','dispatch_geometry_v2')]
                needed.append(manifest_path)
                admission=dict(expires_utc=policy['expires_utc'],pi_readonly_export=True,capture=False,
                    host_affinity=[14],session_count=2,maximum_host_output_bytes=policy['allocation']['target_maximum_bytes']+4*1024**2,
                    mirror_maximum_bytes=policy['allocation']['target_maximum_bytes'],target_payload_writes=False,
                    output=str(output.with_name(output.name+'-backup')),manifest=str(manifest_path),input_pins=[pin(p) for p in needed],
                    module_sha256={n:hashlib.sha256((here/(n+'.py')).read_text(encoding='utf-8').encode()).hexdigest() for n in MODULES},
                    coordinator_sha256=digest(receiver),boot_id=policy['boot_id'],source_relative=Path(root).name,
                    export_unit=plan['export_unit'],policy_sha256=policy_sha,partial_initializer=partial,policy=policy,
                    install_sha256=config['baseline']['install_sha256'],live_config_sha256=config['baseline']['live_config_sha256'],
                    closed_owners=pack(decode(config['preflight_pi_owners'])+closures),live_owners=tree['owners'])
                store.json('REVIEW.json',admission)
                phase=process_phase([sys.executable,'-B',str(receiver),'--admission',str(output/'metadata/REVIEW.json'),
                    '--output',admission['output'],'--owner-receipt',str(output.parent/'MIRROR_EARLY_OWNER.json')],
                    timeout=150,maximum=16384)
                backup=dict(phase=clean_phase(phase),stdout_base64=base64.b64encode(phase['stdout']).decode(),
                    stderr_base64=base64.b64encode(phase['stderr']).decode())
                # Reaped local receiver and exact fresh owner before accepting its receipt.
                early=json.loads((output.parent/'MIRROR_EARLY_OWNER.json').read_bytes())
                try:created=psutil.Process(early['pid']).create_time()
                except psutil.NoSuchProcess:created=None
                if created is not None and abs(created-early['create_time'])<.001:raise RuntimeError('Receiver coordinator remains')
                backup['coordinator_exact_dead']=True;backup['coordinator_owner']=early
                if not good(phase):raise RuntimeError('Full-tree receiver failed')
                if not (Path(admission['output'])/'metadata/BACKUP.json').is_file():raise RuntimeError('Missing exact backup receipt')
                success=fault is None and gate is not None and good(gate) and tree.get('gate',{}).get('logical_success') is True
    except BaseException as exc:
        fault=(fault+'; ' if fault else '')+type(exc).__name__+': '+str(exc)[:2048]
    result=dict(logical_success=success,failure=fault,stage_owner=stage_owner,
        gate_phase=None if gate is None else clean_phase(gate),census_phase=None if census_phase is None else clean_phase(census_phase),
        target_status=None if tree is None else tree['status'],backup=backup,
        accepted_field_runtime=False,two_sessions_qualified=False,remaining_seconds=remaining())
    store.json('RESULT.json',result)
    store.json('coordinator-closure.json',dict(owner=owner,work_complete=True,logical_success=success,
        own_ssh_phases_reaped=all(p is None or p['ssh_reaped'] for p in (initialized,gate,census_phase)),
        completed_before_policy_expiry=remaining()>0))
    print(json.dumps(dict(logical_success=success,failure=fault,target_status=result['target_status'],
        backup_status=None if backup is None else backup.get('status','RECEIVER_ATTEMPTED'))))
    return int(not success)
if __name__=='__main__':raise SystemExit(main())
