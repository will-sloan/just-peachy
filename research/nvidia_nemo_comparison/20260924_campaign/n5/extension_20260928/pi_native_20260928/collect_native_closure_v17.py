"""Read-only closure census. See README_FINAL_MANAGER_INTEGRATION_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import json
import hashlib
from pathlib import Path
import shutil
import sys
import psutil
from dispatch_geometry_v2 import remote, PRIVATE, LOCAL, REMOTE


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--version', type=int, required=True)
    p.add_argument('--resource-policy',type=Path,required=True)
    p.add_argument('--policy-sha256',required=True)
    p.add_argument('--census',type=Path,required=True)
    p.add_argument('--owner-receipt',type=Path,required=True)
    args = p.parse_args()
    assert args.version > 0
    psutil.Process().cpu_affinity([14])
    with args.owner_receipt.open('x') as f:json.dump(dict(pid=psutil.Process().pid,create_time=psutil.Process().create_time(),affinity=[14]),f)
    raw=args.resource_policy.read_bytes();assert hashlib.sha256(raw).hexdigest()==args.policy_sha256
    policy=json.loads(raw);assert policy['schema']=='just-peachy.live-measured-resource-policy.v1'
    assert policy['scope_root'].endswith('/field-transfer-ui-v2') and policy['combined_request_bytes']==297706584
    census=json.loads(args.census.read_bytes())
    paths = [PRIVATE/f'NATIVE_{kind}_V{args.version}.json' for kind in ('CLOSURE', 'RESOURCES')]
    assert not any(path.exists() for path in paths), 'Preserve existing receipts'
    worker = json.loads((LOCAL/'supervision/worker.json').read_text())
    assert worker['status'] == 'COMPLETED'
    host_owners = []
    for pid_key, time_key in [('pid', 'create_time'), ('child_pid', 'child_create_time')]:
        try:
            observed = psutil.Process(worker[pid_key]).create_time()
        except psutil.NoSuchProcess:
            observed = None
        assert observed is None or abs(observed-worker[time_key]) > .001
        host_owners.append(dict(pid=worker[pid_key], create_time=worker[time_key], observed_create_time=observed, exact_alive=False))
    isolated_export_owners=[]
    for path in PRIVATE.glob('d1-onnx-*/supervision/worker.json'):
        record=json.loads(path.read_text())
        owners=[dict(pid=record[k],create_time=record[t]) for k,t in [('pid','create_time'),('child_pid','child_create_time')] if record.get(k) is not None]
        for name in ['MODEL_OWNER.json','REGISTERED_OWNER.json']:
            f=path.parent.parent/name
            if f.exists():
                o=json.loads(f.read_text());owners.append(o.get('owner',o))
        for o in owners:
            try:observed=psutil.Process(o['pid']).create_time()
            except psutil.NoSuchProcess:observed=None
            assert observed is None or abs(observed-o['create_time'])>.001
            isolated_export_owners.append(dict(path=str(path),owner=o,observed_create_time=observed,exact_alive=False))
    def registered_remote(code):
        from field_operator_broker_host_v2 import ssh_phase
        response=ssh_phase(['python3','-B','-'],payload=code.encode(),timeout=60,maximum=262144)
        stdout=response.pop('stdout');stderr=response.pop('stderr')
        stem=args.owner_receipt.parent/('NATIVE_COLLECTOR_V%d'%args.version)
        Path(str(stem)+'_STDOUT.bin').open('xb').write(stdout)
        Path(str(stem)+'_STDERR.bin').open('xb').write(stderr)
        Path(str(stem)+'_PHASE.json').open('x').write(json.dumps(response))
        lines=stderr.splitlines()
        if lines:
            first=json.loads(lines[0])
            Path(str(stem)+'_OWNER.json').open('x').write(json.dumps(first['utility_owner']))
        if response['returncode'] or response['fault'] is not None:
            raise RuntimeError('Preserved bounded registered native census failure')
        assert len(lines)==1 and response['readers_joined'] and response['ssh_reaped']
        value=json.loads(stdout);assert value['utility_owner']==first['utility_owner']
        return value
    x = registered_remote('ROOT='+repr(REMOTE)+'\n'+r'''
import os,json,hashlib,subprocess,shutil,fcntl,resource,signal
from pathlib import Path
from datetime import datetime,timezone
os.sched_setaffinity(0,{3});r=Path(ROOT)
resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE,(0,)*2)
signal.alarm(45)
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
utility_owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
import sys
print(json.dumps(dict(utility_owner=utility_owner)),file=sys.stderr,flush=True)
assert boot=='892ed9fa-e39c-48af-8653-eae5e123daad'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
owners=[];nonidentity_closures=[]
for p in sorted(r.rglob('*OWNER*.json')):
 o=json.loads(p.read_text())
 if p.name=='OWNERSHIP_CLOSURE.json':
  SCHEMA={'borrowed','outer_released','controller_closed','worker_joined','pending_commands'}
  assert set(o)==SCHEMA and o['outer_released'] is True
  assert type(o['controller_closed']) is bool and type(o['worker_joined']) is bool
  assert type(o['borrowed']) is dict and set(o['borrowed'])=={'opened','closed'}
  assert all(type(v) is int and 0<=v<=1 for v in o['borrowed'].values()) and o['borrowed']['closed']<=o['borrowed']['opened']
  assert o['pending_commands'] is None or type(o['pending_commands']) is int and o['pending_commands']>=0
  nonidentity_closures.append(dict(path=str(p),sha256=sha(p),receipt=o))
  continue
 if p.relative_to(r).as_posix() in {
  'field-local-release-v1/launches/launch-01/OWNER.json',
  'field-local-release-v1/launches/launch-02/OWNER.json'}:
  expected={
   'launch-01':'6fe6f5b378e2ef6c66f89b8cf32cb75c93f7f7216a4e1454d1bacb2030707fbe',
   'launch-02':'2c3dbd0f2c4c6a9e80499346a4fac8a306865ea759849786993850fe4e65bc15'}
  assert sha(p)==expected[p.parent.name]
  assert set(o)=={'owner','policy_sha256','slot','utc','purpose'}
  assert o['policy_sha256']=='d8600a564dc41641ab799b1f64dc977a9ef719c8c3a45847d00cd6a5023dd454'
  assert o['slot']=='launches/'+p.parent.name and o['purpose']=='METADATA_QUALIFICATION_ONLY'
  o=o['owner'];assert set(o)=={'boot_id','pid','start_ticks'}
  assert type(o['pid']) is int and type(o['start_ticks']) is int
 t=ticks(o['pid']);assert not(o['boot_id']==boot and t==o['start_ticks'])
 owners.append(dict(path=str(p),owner=o,observed_start_ticks=t,exact_alive=False))
units=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True)
assert not units.strip() and ticks(1008)==476 and ticks(1124)==514
install=sha(Path.home()/'JustPeachy/install/current.json');config=sha(Path.home()/'JustPeachy/data/live_config.json')
assert install=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
assert config=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
capture=Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip();assert capture=='closed'
for lock in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with lock.open('r+b') as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
swap={k:int(v) for k,v in (l.split() for l in Path('/proc/vmstat').read_text().splitlines()) if k in ['pswpin','pswpout']}
utility_owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
print(json.dumps(dict(utility_owner=utility_owner,checked_utc=datetime.now(timezone.utc).isoformat(),boot_id=boot,owners=owners,nonidentity_closures=nonidentity_closures,units=units,original_app=[dict(pid=1008,start_ticks=476),dict(pid=1124,start_ticks=514)],install_sha256=install,live_config_sha256=config,capture=capture,hardware_lease_free=True,research_lease_free=True,available_ram_bytes=available,target_free_bytes=shutil.disk_usage(r).free,target_bytes=int(subprocess.check_output(['du','-sb',str(r)],text=True).split()[0]),swap=swap,page_size=os.sysconf('SC_PAGE_SIZE'),temperature_c=int(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000,throttle=subprocess.check_output(['vcgencmd','get_throttled'],text=True).strip())))
''')
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from window_guard import payload_inventory
    used = 0
    for relative in ['n5/prepi-20260928', 'releases/prepi-shutdown-v1', 'n5/listening-examples-v1', 'n5/research-extension-20260928']:
        inv = payload_inventory(LOCAL/relative)
        assert not inv['errors'] and not inv['reparse_not_traversed']
        used += inv['total_logical_bytes']
    free = {drive: shutil.disk_usage(drive+'/').free for drive in ['C:', 'G:']}
    resources = dict(checked_utc=x['checked_utc'],host_window_bytes=used,target_bytes=x['target_bytes'],combined_bytes=used+x['target_bytes'],cap_bytes=json.loads((Path(__file__).parent.parent/'WINDOW_V5.json').read_text())['maximum_new_output_bytes'],host_free_bytes=free,all_owned_native_identities_closed=len(x['owners']),host_supervisor_closed=True,host_owners=host_owners,isolated_export_owners=isolated_export_owners)
    assert free['C:'] >= 50*1024**3 and free['G:'] >= 75*1024**3
    resources['original_cap_bytes']=resources['cap_bytes']
    resources['cap_bytes']=policy['combined_output_cap_bytes']
    resources['payload_bytes']=census['calculation']['existing_bytes']+census['calculation']['retained_reservations_bytes']+x['target_bytes']+max(0,used-census['calculation']['window_used_bytes'])
    resources['payload_cap_bytes']=policy['total_payload_cap_bytes']
    resources['resource_policy_sha256']=args.policy_sha256
    assert resources['combined_bytes']<resources['cap_bytes'] and resources['payload_bytes']<resources['payload_cap_bytes']
    import subprocess
    from dispatch_b01_stack_v2 import SSH
    assert subprocess.run(SSH+['test ! -e /proc/'+str(x['utility_owner']['pid'])],timeout=10).returncode==0
    x['utility_pid_absent_after_ssh']=True
    for path, data in zip(paths, [x, resources]):
        with path.open('x', encoding='utf-8') as f: json.dump(data, f, indent=2)
    print(json.dumps(resources))


if __name__ == '__main__':
    main()
