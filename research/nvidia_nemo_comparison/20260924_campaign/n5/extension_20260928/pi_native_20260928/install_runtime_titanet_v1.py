"""Install the existing three TitaNet artifacts; README_RUNTIME_TITANET_INSTALL_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,hashlib,json,os,re,shlex,shutil,sys,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
MIB=1024**2
TOTAL=88696429
ALLOCATION=dict(target_bytes=TOTAL+MIB,host_bytes=2*TOTAL+4*MIB,combined_bytes=3*TOTAL+5*MIB)

def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(v):return hashlib.sha256(v).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('local','private','assets','prior-closure','inspection','output','scope'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--version',type=int,required=True)
    a=ap.parse_args()
    if a.version<1 or a.output.parent!=a.private:raise ValueError('New private installation output required')
    a.output.mkdir()
    me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    def put(name,raw):
        if type(raw) is not bytes or len(raw)>262144:raise ValueError('Metadata cap')
        with (a.output/name).open('xb') as f:
            if f.write(raw)!=len(raw):raise OSError('Short metadata write')
            f.flush();os.fsync(f.fileno())
        if (a.output/name).read_bytes()!=raw:raise IOError('Metadata readback')
    def save(name,v):put(name,encoded(v))
    save('REGISTERED_OWNER.json',owner)
    scope=json.loads(a.scope.read_bytes())
    last=[0.]
    def guard():
        if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Preparation scope expired')
        if datetime.now(timezone.utc)>=datetime(2026,10,2,14,14,20,tzinfo=timezone.utc):raise TimeoutError('User deadline')
        if time.monotonic()-last[0]<2:return
        last[0]=time.monotonic()
        for drive,floor in [('C:/',50*1024**3),('G:/',75*1024**3)]:
            if shutil.disk_usage(drive).free<floor+ALLOCATION['host_bytes']:raise RuntimeError('Full host reserve')
        if sum(p.stat().st_size for p in a.output.rglob('*') if p.is_file())>ALLOCATION['host_bytes']:raise RuntimeError('Independent host allocation')
    guard()
    from field_runtime_host_precheck_v2 import inspect
    pre,details=inspect(a.local,a.private,current_owner=owner,deadline=time.monotonic()+100,guard=guard)
    save('HOST_PRECHECK.json',pre);save('HOST_PRECHECK_DETAILS.json',details)
    if pre['alive_owners']:raise RuntimeError('Other registered host owner remains alive')
    from field_runtime_profiles_v1 import verify_titanet
    assets=verify_titanet(a.assets,deadline=time.monotonic()+60,guard=guard)
    rows={r['name']:{k:r[k] for k in ('bytes','sha256')} for r in assets['files']}
    if sum(r['bytes'] for r in rows.values())!=TOTAL:raise ValueError('Exact prior asset export')
    # Existing census implementation, no obsolete window/admission invocation.
    sys.path.insert(0,str(Path(__file__).parent.parent))
    from window_guard import payload_inventory
    inventory=payload_inventory(a.local)
    if inventory['errors']:raise RuntimeError('Incomplete host payload census')
    prior=json.loads((a.local/'n5/d1-anonymous-lifecycle-parent-v4/ADMISSION.json').read_bytes())['census']
    old_census_raw=Path(prior['path']).read_bytes()
    if sha(old_census_raw)!=prior['sha256']:raise ValueError('Historical reparse inventory pin')
    retained=json.loads(old_census_raw)['inventory']['reparse_not_traversed']
    if set(inventory['reparse_not_traversed'])!=set(retained):raise ValueError('New unreviewed reparse paths')
    used=0
    for rel in ('n5/prepi-20260928','releases/prepi-shutdown-v1','n5/listening-examples-v1','n5/research-extension-20260928'):
        item=payload_inventory(a.local/rel)
        if item['errors'] or item['reparse_not_traversed']:raise ValueError('Output inventory incomplete')
        used+=item['total_logical_bytes']
    observed=json.loads((a.inspection/'RESULT.json').read_bytes())
    baseline=dict(boot_id=observed['boot_id'],
        owners=[{k:r[k] for k in ('pid','start_ticks','boot_id')} for r in observed['current_project_processes']
                if 'launch_current.py' in r['cmdline'] or '/main.py ' in r['cmdline']],
        config_pins={r['path']:r['sha256'] for r in observed['files']})
    if len(baseline['owners'])!=2:raise ValueError('Exact actual current baseline pair')
    accounting=dict(host_window_bytes=used,host_payload_bytes=inventory['total_logical_bytes'],target_bytes=observed['target_bytes'])
    # Prospective measured allowance; no old WINDOW or closed policy is changed.
    margin=8*MIB
    accounting['combined_cap']=((used+observed['target_bytes']+ALLOCATION['combined_bytes']+margin+MIB-1)//MIB)*MIB
    accounting['payload_cap']=((inventory['total_logical_bytes']+2684354560+observed['target_bytes']+ALLOCATION['combined_bytes']+margin+MIB-1)//MIB)*MIB
    save('HOST_CENSUS.json',dict(utc=datetime.now(timezone.utc).isoformat(),accounting=accounting,allocation=ALLOCATION,
        retained_reservations_bytes=2684354560,inventory_sha256=sha(encoded(inventory)),reparse_paths_unchanged=True,
        original_window_unchanged=True,physical_bytes_credited=0))
    # Back up and independently restore the exact prior export before deployment.
    for label in ('assets-backup','assets-restore'):
        destination=a.output/label;destination.mkdir()
        for name,row in rows.items():
            source=a.assets/name;before=source.stat();count=0;h=hashlib.sha256()
            with source.open('rb') as f,(destination/name).open('xb') as g:
                while True:
                    guard();block=f.read(16384)
                    if not block:break
                    if g.write(block)!=len(block):raise OSError('Short host asset copy')
                    h.update(block);count+=len(block)
                g.flush();os.fsync(g.fileno())
            after=source.stat()
            if (before.st_ino,before.st_mtime_ns,before.st_size)!=(after.st_ino,after.st_mtime_ns,after.st_size):raise RuntimeError('Source changed')
            if count!=row['bytes'] or h.hexdigest()!=row['sha256']:raise IOError('Asset copy mismatch')
            with (destination/name).open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=row['sha256']:raise IOError('Independent host readback')
    save('SOURCE_ASSET_BACKUP.json',dict(files=rows,copies=['assets-backup','assets-restore'],exact_independent_readbacks=True))
    old=json.loads(a.prior_closure.read_bytes());identities={}
    for row in old['owners']+old['additional_registered_owners']:
        v={k:row['owner'][k] for k in ('pid','start_ticks','boot_id')}
        identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    for v in [old['utility_owner']]+[json.loads(p.read_bytes()) for p in a.inspection.parent.glob('install-inspection-v*/NATIVE_OWNER.json')]:
        identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    if len(identities)>1024:raise ValueError('Prior owner cap')
    historical={row['path'].split('/nemotron-20260928/',1)[1]:row['owner'] for row in old['owners']
        if set(row['owner'])!={'pid','start_ticks','boot_id'}}
    nested={
      'field-local-release-v1/launches/launch-01/OWNER.json':dict(sha256='6fe6f5b378e2ef6c66f89b8cf32cb75c93f7f7216a4e1454d1bacb2030707fbe',policy_sha256='d8600a564dc41641ab799b1f64dc977a9ef719c8c3a45847d00cd6a5023dd454',slot='launches/launch-01',purpose='METADATA_QUALIFICATION_ONLY'),
      'field-local-release-v1/launches/launch-02/OWNER.json':dict(sha256='2c3dbd0f2c4c6a9e80499346a4fac8a306865ea759849786993850fe4e65bc15',policy_sha256='d8600a564dc41641ab799b1f64dc977a9ef719c8c3a45847d00cd6a5023dd454',slot='launches/launch-02',purpose='METADATA_QUALIFICATION_ONLY')}
    tree=ast.parse((Path(__file__).parent/'collect_native_closure_v19.py').read_text(encoding='utf-8'))
    constants=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 'NEW_NESTED=' in n.value]
    if len(constants)!=1:raise ValueError('Historical collector constant')
    assignment=next(n for n in ast.parse(constants[0]).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NEW_NESTED' for t in n.targets))
    for path,row in ast.literal_eval(assignment.value).items():
        nested[path]={**row,'policy_sha256':'f39a8b7dbedbebed1492687d42d5648ac033dbba0d02a4a46537175e1fa40d9c'}
    now=datetime.now(timezone.utc);expiry=min(now+timedelta(seconds=600),datetime.fromisoformat(scope['expires_utc']))
    if (expiry-now).total_seconds()<180:raise TimeoutError('Complete install/closure reserve')
    unit='jp-titanet-assets-v'+str(a.version)
    request=dict(schema='just-peachy.titanet-asset-install.v1',root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/runtime-titanet-v'+str(a.version),
        unit=unit,issued_utc=now.isoformat(),expires_utc=expiry.isoformat(),files=rows,allocation=ALLOCATION,accounting=accounting,
        prior=list(identities.values()),historical=historical,nested=nested,baseline=baseline)
    payload=encoded(request);put('ADMISSION.json',payload)
    code=(Path(__file__).parent/'field_runtime_asset_native_v1.py').read_bytes()
    compile(code,'<asset-installer>','exec')
    save('SOURCE_PIN.json',dict(bytes=len(code),sha256=sha(code)))
    from dispatch_b01_stack_v2 import SSH
    from field_operator_broker_host_v2 import process_phase,ssh_phase
    from field_local_manager_transport_v1 import run,TransportFailure
    argv=['systemd-run','--user','--quiet','--wait','--pipe','--collect','--unit='+unit,
        '--property=Description=JustPeachyTitaNetAssets','--property=AllowedCPUs=2-3','--property=CPUQuota=200%',
        '--property=TasksMax=64','--property=RuntimeMaxSec=90','--property=TimeoutStopSec=10',
        '--property=LimitAS=134217728','--property=LimitSTACK=1048576','--property=LimitFSIZE=94371840',
        '/usr/bin/python3','-u','-B','-c',code.decode(),sha(payload)]
    def persist(v):save('NATIVE_OWNER.json',v);return True
    def stop():
        result=process_phase(SSH+['systemctl --user stop --no-block '+unit],timeout=10,maximum=16384)
        result.pop('stdout');result.pop('stderr');save('STOP_PHASE.json',result)
    def closed(v):
        native="import os,json,resource,signal\nfrom pathlib import Path\nos.sched_setaffinity(0,{3})\nresource.setrlimit(resource.RLIMIT_AS,(134217728,)*2);resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2);resource.setrlimit(resource.RLIMIT_FSIZE,(0,0));signal.alarm(10)\ndef ticks(pid):\n try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])\n except FileNotFoundError:return None\nboot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()\nme=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)\nprint(json.dumps(dict(utility_owner=me)),file=__import__('sys').stderr,flush=True)\nassert boot!=old['boot_id'] or ticks(old['pid'])!=old['start_ticks']\nprint(json.dumps(dict(owner=old,exact_alive=False,utility_owner=me)))"
        result=ssh_phase(['/usr/bin/python3','-u','-B','-'],payload=('old='+repr(v)+'\n'+native).encode(),timeout=15,maximum=16384)
        out=result.pop('stdout');err=result.pop('stderr');put('CLOSURE_STDOUT.bin',out);put('CLOSURE_STDERR.bin',err);save('CLOSURE_PHASE.json',result)
        helper=json.loads(err.splitlines()[0])['utility_owner'];save('CLOSURE_OWNER.json',helper)
        if result['returncode'] or result['fault'] or not result['readers_joined'] or not result['ssh_reaped']:raise RuntimeError('Independent exact closure failed')
        final=process_phase(SSH+['test ! -e /proc/'+str(helper['pid'])],timeout=10,maximum=16384)
        fout=final.pop('stdout');ferr=final.pop('stderr');put('CLOSURE_FINAL_STDOUT.bin',fout);put('CLOSURE_FINAL_STDERR.bin',ferr);save('CLOSURE_FINAL_PHASE.json',final)
        if final['returncode'] or final['fault'] or not final['readers_joined'] or not final['ssh_reaped']:raise RuntimeError('Closure helper absence failed')
        save('NATIVE_CLOSURE.json',dict(owner=v,utility_owner=helper,exact_owner_dead=True,utility_pid_absent=True));return True
    def consume(channel,v,close):
        for name,row in sorted(rows.items()):
            h=hashlib.sha256();count=0
            with (a.output/'assets-restore'/name).open('rb') as f:
                while True:
                    guard();block=f.read(262144)
                    if not block:break
                    channel.send(block);h.update(block);count+=len(block)
            if count!=row['bytes'] or h.hexdigest()!=row['sha256']:raise RuntimeError('Transport source changed')
        value=channel.json()
        if set(value)!={'type','result'} or value['type']!='INSTALLED' or value['result']['owner']!=v or value['result']['files']!=rows:raise ValueError('Exact installed response')
        save('INSTALLED_PENDING_CLOSURE.json',value['result']);close();return value['result']
    try:
        result,receipt=run(SSH+['exec '+shlex.join(argv)],payload,persist_early=persist,consume=consume,
            verify_closed=closed,stop_owned=stop,guard=guard,timeout=105)
    except TransportFailure as exc:
        receipt=exc.receipt;put('STDERR.bin',receipt.pop('stderr'));save('TRANSPORT_FAILURE.json',receipt);raise
    put('STDERR.bin',receipt.pop('stderr'));save('TRANSPORT.json',receipt)
    save('RESULT.json',result)
    save('BACKUP.json',dict(target_files=rows,independent_host_copies=['assets-backup','assets-restore'],native_full_readbacks=True,
        native_owner_closed=True,source_backup_before_dispatch=True,model_execution=False))
    print(json.dumps(dict(status='EXACT_TITANET_ASSETS_INSTALLED',files=len(rows),bytes=TOTAL,root=request['root'],model_execution=False)))

if __name__=='__main__':main()

