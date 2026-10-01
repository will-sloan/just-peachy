"""Bounded review coordinator; README_FIELD_TRANSFER_V3.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scope',required=True,type=Path)
    p.add_argument('--owner-receipt',required=True,type=Path)
    p.add_argument('--installed-release',required=True,type=Path)
    p.add_argument('--saved-root',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    owner=dict(pid=psutil.Process().pid,create_time=psutil.Process().create_time(),affinity=[14])
    with a.owner_receipt.open('x') as f:json.dump(owner,f)
    scope=json.loads(a.scope.read_bytes())
    if scope['maximum_output_bytes']!=2097152 or (datetime.fromisoformat(scope['expires_utc'])-datetime.now(timezone.utc)).total_seconds()<125:
        raise ValueError('Fresh2MiB host scope with125seconds remaining required')
    if a.output.exists():raise FileExistsError('Preserve previous review')
    command=[sys.executable,'-B',str(Path(__file__).with_name('verify_field_transfer_v2.py')),
             '--installed-release',str(a.installed_release),'--saved-root',str(a.saved_root),'--output',str(a.output)]
    r=subprocess.run(command,capture_output=True,timeout=120)
    for name,raw in [('STDOUT.txt',r.stdout),('STDERR.txt',r.stderr)]:
        if len(raw)>65536:raise ValueError('Review output envelope exceeded')
        with (a.output/name).open('xb') as f:f.write(raw)
    child=json.loads((a.output/'REGISTERED_OWNER.json').read_bytes())
    try:alive=abs(psutil.Process(child['pid']).create_time()-child['create_time'])<.001
    except psutil.NoSuchProcess:alive=False
    if alive:raise RuntimeError('Review child still active')
    with (a.output/'PROCESS_CLOSURE.json').open('x') as f:
        json.dump(dict(returncode=r.returncode,child=child,exact_alive=False,ended_utc=datetime.now(timezone.utc).isoformat()),f)
    print(json.dumps(dict(returncode=r.returncode,review=str(a.output),exact_child_closed=True)))
    return r.returncode

if __name__=='__main__':raise SystemExit(main())
