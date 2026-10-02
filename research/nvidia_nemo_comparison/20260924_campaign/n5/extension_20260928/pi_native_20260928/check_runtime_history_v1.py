"""Changed history consumer check; README_RUNTIME_HISTORY_CHECK_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,hashlib,json,os,sys,time
from pathlib import Path
from datetime import datetime,timezone
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('private','local','scope','output'):ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args();a.output.mkdir()
    me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    def save(name,value):
        raw=json.dumps(value,sort_keys=True,allow_nan=False).encode()
        if len(raw)>65536:raise ValueError('Compact check receipt')
        with (a.output/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if (a.output/name).read_bytes()!=raw:raise IOError('Receipt readback')
    save('REGISTERED_OWNER.json',owner)
    scope=json.loads(a.scope.read_bytes())
    def guard():
        if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Scope expiry')
    guard()
    from field_runtime_host_precheck_v2 import inspect
    pre,details=inspect(a.local,a.private,current_owner=owner,deadline=time.monotonic()+90,guard=guard)
    save('HOST_PRECHECK.json',pre)
    if pre['alive_owners']:raise RuntimeError('Another registered host owner active')
    pin=json.loads((a.scope.parent/'SOURCE_CLOSED_V127.json').read_bytes())['files']['field_runtime_history_v1.py']
    raw=Path(__file__).with_name('field_runtime_history_v1.py').read_bytes()
    if pin!=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()):raise ValueError('Backed reader changed')
    from field_runtime_history_v1 import history_open,history_reading
    release=a.private/'field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12'
    manifest=hashlib.sha256((release/'RELEASE_MANIFEST.json').read_bytes()).hexdigest()
    found=[]
    for label,root,audio in [('processed',a.private/'field-runtime-v14-offload03-v1',True),
                              ('off',a.private/'field-runtime-v16-offload02-v1',False)]:
        paths=sorted(root.rglob('conversation.json'))
        if len(paths)!=2:raise ValueError('Two complete independently copied conversations expected')
        folder=paths[0].parent
        raw=(folder/'conversation.json').read_bytes();metadata=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        result=history_open(release,manifest,folder,metadata,deadline=time.monotonic()+30)
        if result['audio_recorded'] is not audio or not result['read_only'] or result['capture_started'] or result['constructor_called']:
            raise AssertionError('Exact read-only selection')
        if label=='processed' and not result['rows']:raise AssertionError('Existing nonempty captions expected')
        found.append(dict(label=label,rows=len(result['rows']),files=len(result['member_pins']),
            member_manifest_sha256=hashlib.sha256(json.dumps(result['member_pins'],sort_keys=True).encode()).hexdigest(),audio=audio))
    rejects=0
    for bad_manifest,bad_meta in [('0'*64,metadata),(manifest,dict(bytes=metadata['bytes'],sha256='0'*64))]:
        try:history_open(release,bad_manifest,folder,bad_meta,deadline=time.monotonic()+30)
        except ValueError:rejects+=1
        else:raise AssertionError('Bad pin accepted')
    target=a.output/'must-not-exist'
    try:
        with history_reading():target.open('xb')
    except PermissionError:rejects+=1
    else:raise AssertionError('History writer accepted')
    if target.exists():raise AssertionError('Rejected write created a file')
    guard();save('RESULT.json',dict(status='CHANGED_INSTALLED_HISTORY_CONSUMER_PASS',positive_groups=found,rejections=rejects,
        native=False,gui=False,capture_started=False,model_loaded=False,source_files_unchanged=True))
    print(json.dumps(dict(status='CHANGED_INSTALLED_HISTORY_CONSUMER_PASS',groups=found,rejections=rejects)))
if __name__=='__main__':main()

