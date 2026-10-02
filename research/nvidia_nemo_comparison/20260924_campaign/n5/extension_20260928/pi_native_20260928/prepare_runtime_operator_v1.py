"""Create a finite PC batch-renewal scope; README_RUNTIME_OPERATOR_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,hashlib,json,os,shutil
from datetime import datetime,timedelta,timezone
from pathlib import Path

INSTALL_RESERVE=3307886087
COPY_RESERVE=1485771104+4194304
METADATA_RESERVE=4194304
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('private','work','sources','previous-install','output','scope'):
        p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--version',type=int,required=True)
    p.add_argument('--plan',action='store_true')
    a=p.parse_args()
    a.output.mkdir()
    me=psutil.Process()
    def save(n,v):
        raw=(json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        if len(raw)>65536:raise ValueError('Operator metadata bound')
        with (a.output/n).open('xb') as f:
            if f.write(raw)!=len(raw):raise OSError('Short write')
            f.flush();os.fsync(f.fileno())
        if (a.output/n).read_bytes()!=raw:raise IOError('Operator metadata readback')
    save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    if a.work.resolve()!=a.private.resolve()/'deployable-runtime-resume-v1':raise ValueError('Prepared workstation receipt directory')
    if a.scope.parent.resolve()!=a.work.resolve() or a.output.parent.resolve()!=a.work.resolve():raise ValueError('Accounted output paths')
    if a.previous_install.parent.resolve()!=a.private.resolve():raise ValueError('Previous installation location')
    result=json.loads((a.previous_install/'RESULT.json').read_bytes())
    previous=int(result['root'].rsplit('v',1)[1])
    if not 24<=a.version<=9999 or a.version<=previous:raise ValueError('Fresh higher version24..9999')
    release=(a.previous_install/'RELEASE.json').read_bytes()
    if hashlib.sha256(release).hexdigest()!=result['policy_sha256']:raise ValueError('Previous policy pin')
    for q in (a.private/f'field-runtime-v{a.version}-install',a.scope,a.work/f'install-inspection-v{10000+a.version}',a.private/f'field-runtime-v{previous}-batch-preservation-v{a.version}'):
        if q.exists() or q.is_symlink():raise FileExistsError(str(q))
    names=('preserve_runtime_batch_v1.py','inspect_runtime_reprovision_v1.py','provision_field_runtime_v1.py','field_runtime_reprovision_v1.py')
    pins={}
    receipt=json.loads((a.work/'SOURCE_CLOSED_V157.json').read_bytes())['files']
    for n in names:
        raw=(a.sources/n).read_bytes()
        pin=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if pin!=receipt[n]:raise ValueError('Verified operator source changed: '+n)
        pins[n]=pin
    # New full reservations are prospective. Existing files are never deleted or
    # credited as unused; individual native phases independently census/admit.
    full=INSTALL_RESERVE+COPY_RESERVE+METADATA_RESERVE
    floors={}
    for d,gib in (('C:/',50),('G:/',75)):
        free=shutil.disk_usage(d).free;floors[d]=free
        if free<gib*1024**3+full:raise RuntimeError('Complete new operation reserve: '+d)
    used=sum(q.stat().st_size for q in a.work.rglob('*') if q.is_file())
    now=datetime.now(timezone.utc)
    plan=dict(schema='just-peachy.operator-renewal.v1',previous_version=previous,version=a.version,
        existing_host_work_bytes=used,new_host_metadata_reserved_bytes=METADATA_RESERVE,
        independent_previous_batch_copy_reserved_bytes=COPY_RESERVE,
        independent_new_install_reserved_bytes=INSTALL_RESERVE,
        new_combined_reservation_bytes=full,free_bytes=floors,source_pins=pins,
        maximum_seconds=600,plan_only=a.plan,
        no_deletion_or_replenishment=True,native_dispatched=False)
    save('PLAN.json',plan)
    if not a.plan:
        used=sum(q.stat().st_size for q in a.work.rglob('*') if q.is_file())
        scope=dict(issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=600)).isoformat(),
            maximum_bytes=used+METADATA_RESERVE,existing_bytes=used,
            incremental_reserved_bytes=METADATA_RESERVE,
            purpose='Explicit user batch renewal; preserve, independently inspect and freshly provision',
            operator_plan_sha256=hashlib.sha256((a.output/'PLAN.json').read_bytes()).hexdigest(),
            original_runtime_caps_unchanged=True,automatic_replenishment=False,failed_deleted_unused_credit=False)
        raw=(json.dumps(scope,sort_keys=True,indent=2)+'\n').encode()
        with a.scope.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if a.scope.read_bytes()!=raw:raise IOError('Scope readback')
    print(json.dumps(dict(status='PLAN_ONLY_NO_PI_CONTACT' if a.plan else 'FINITE_RENEWAL_SCOPE_READY',version=a.version,reserved_bytes=full)))
if __name__=='__main__':main()

