"""Pinned additive-epoch coordinator overlay. README_S6C_ORCHESTRATOR_SCAN_V4.md."""
from __future__ import annotations
import argparse
import importlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
from unittest.mock import patch
import hashlib
_reviewed_v3=Path(__file__).with_name('s6c_orchestrator_scan_v3.py')
if hashlib.sha256(_reviewed_v3.read_bytes()).hexdigest()!='436ae9a78319bf54710b3f1ac4a4d8a93034ba4030efda8817a2bdfeefd0d7e7':
    raise ValueError('Reviewed V3 source changed')
_prior_path=Path(__file__).with_name('s6c_orchestrator_scan_v2.py')
if hashlib.sha256(_prior_path.read_bytes()).hexdigest()!='eb83afe67c21ac1daa9c388d21471167500971bdc358a5fb557b7e4883d8a5ab':
    raise ValueError('Preserved reviewed V2 overlay utility bytes changed')
import s6c_orchestrator_scan_v2 as prior
if Path(prior.__file__).resolve()!=_prior_path.resolve():raise ValueError('V2 utility module resolution differs')

SIM=prior.SIM
REPORT=prior.REPORT
EDGE=prior.EDGE
SCHEMA='jp_s6c_coordinator_scan_overlay.v4'
TRUSTED_EPOCHS={
    'epoch2':'1f7f0e10186eb1187d05d9be258372d6dfbe39ec3741c2ce2976a2ca3d005cdb',
    'epoch4':'720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945',
    'epoch5':'676ead81afe85b5557494bd851e67f34799106a45976e8f7fa6e2e5900989cbc'}
binding=prior.binding
verified=prior.verified
check_file=prior.check_file
utc=prior.utc


def compatible_native(spec,original):
    for key in ('assets','versions','python','input_index','scene_manifest','state_policy'):
        if spec[key]!=original[key]:raise ValueError('Original native authority differs: '+key)
    def app_rows(value):
        root=Path(value['root'])/'app'
        return {str(Path(b['path']).relative_to(root)):b['sha256'] for b in value['execution_files'] if root in Path(b['path']).parents}
    if not app_rows(original) or app_rows(spec)!=app_rows(original):raise ValueError('Exact original APP inventory required')
    for name in ('s6c_execution.py','s6c_common.py'):
        rows=[b for b in spec['execution_files'] if Path(b['path']).name==name]
        originals=[b for b in original['execution_files'] if Path(b['path']).name==name]
        if len(rows)!=1 or len(originals)!=1 or any(rows[0][k]!=originals[0][k] for k in ('bytes','sha256')):
            raise ValueError('Entire original native worker/common module required: '+name)


def load_native(epoch='epoch5'):
    prior.bind_environment()
    if epoch not in TRUSTED_EPOCHS:raise ValueError('Execution epoch lacks explicit reviewed SHA admission')
    spec_binding=binding(REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json'))
    original_binding=binding(REPORT/'EPOCH2_EXECUTION_MANIFEST.json')
    if spec_binding['sha256']!=TRUSTED_EPOCHS[epoch] or original_binding['sha256']!=TRUSTED_EPOCHS['epoch2']:
        raise ValueError('Pinned execution manifest differs')
    spec=verified(spec_binding);original=verified(original_binding)
    if spec['epoch']!=epoch or Path(spec['root']).resolve()!=SIM/'staging/s6c/20260910T123540Z'/epoch:
        raise ValueError('Execution namespace differs')
    compatible_native(spec,original)
    reference4_binding=binding(REPORT/'EPOCH4_EXECUTION_MANIFEST.json')
    if reference4_binding['sha256']!=TRUSTED_EPOCHS['epoch4']:raise ValueError('Pinned epoch4 reference differs')
    reference4=verified(reference4_binding);compatible_native(spec,reference4)
    for item in reference4['execution_files']:check_file(item)
    if Path(sys.executable).resolve()!=EDGE.resolve() or sys.version!=spec['python']:raise ValueError('Exact EDGE interpreter required')
    if any(prior.package_version(k)!=v for k,v in spec['versions'].items()):raise ValueError('Native package version changed')
    for item in spec['execution_files']+original['execution_files']:check_file(item)
    for item in spec['assets']:
        if binding(item['path'])['sha256']!=item['sha256']:raise ValueError('Frozen asset bytes changed')
    scripts=Path(spec['root'])/'scripts'
    if any(name in sys.modules for name in ('s6c_common','s6c_execution')):raise ValueError('Native modules preloaded before admission')
    sys.path.insert(0,str(scripts))
    common=importlib.import_module('s6c_common');execution=importlib.import_module('s6c_execution')
    if Path(common.__file__).resolve()!=scripts/'s6c_common.py' or Path(execution.__file__).resolve()!=scripts/'s6c_execution.py':
        raise ValueError('Native module source resolution differs')
    if common.SIM.resolve()!=SIM or common.REPORT.resolve()!=REPORT or common.PAYLOAD.resolve()!=Path('G:/Just_Peachy_S6C/20260910T123540Z').resolve():
        raise ValueError('Explicit workspace paths differ')
    if execution.SIM!=common.SIM or execution.REPORT!=common.REPORT or execution.PAYLOAD!=common.PAYLOAD:
        raise ValueError('Execution/common workspace mismatch')
    if spec['execution_digest']!=common.digest({k:spec[k] for k in ('execution_files','assets','versions','state_policy')}):
        raise ValueError('Execution digest differs')
    registry=verified(spec['effective_profile_registry'])
    if registry['status']!='VALIDATED_REAL_V3_API' or spec['profiles']!=registry['profiles']:raise ValueError('Embedded profile registry differs')
    return spec_binding,spec,common,execution


def invocation_dirs(epoch):
    root=REPORT/epoch/'invocations'
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []


def closed_identity(item,process_factory):
    import psutil
    if type(item.get('pid')) is not int or item['pid']<=0 or type(item.get('creation_time')) not in (int,float) or not math.isfinite(item['creation_time']) or item['creation_time']<=0:
        raise ValueError('Recorded process identity incomplete')
    alive=False
    try:alive=abs(process_factory(item['pid']).create_time()-item['creation_time'])<.01
    except psutil.NoSuchProcess:pass
    if alive:raise ValueError('Prior owned process is still alive: '+str(item))
    return dict(pid=item['pid'],creation_time=item['creation_time'],alive=False)


def prior_invocations(common):
    import psutil
    rows=[]
    # Include every epoch invocation namespace, not only the selected native
    # epoch. Epoch3 may have no invocations; nonexistent roots are not created.
    roots=sorted(p for p in REPORT.iterdir() if p.is_dir() and p.name.startswith('epoch') and p.name[5:].isdigit())
    for root in roots:
        for folder in invocation_dirs(root.name):
            owner=common.read(folder/'owner.json');closure=common.read(folder/'closure.json');common.read(folder/'completion.json')
            identities=[{k:owner[k] for k in ('pid','creation_time')},*closure['remaining_owned_children']]
            states=[closed_identity(item,psutil.Process) for item in identities]
            rows.append(dict(epoch=root.name,directory=str(folder),artifacts=[binding(p) for p in sorted(folder.iterdir()) if p.is_file()],
                verified_closed_process_identities=states,scope='Recorded invocation owner/remaining-child identities only, plus original native pool joining; not a census of every historical process.'))
    return rows


def source_rows():
    names=('s6c_orchestrator_scan_v4.py','README_S6C_ORCHESTRATOR_SCAN_V4.md','s6c_orchestrator_scan_v3.py','README_S6C_ORCHESTRATOR_SCAN_V3.md','s6c_orchestrator_scan_v2.py',
        'README_S6C_ORCHESTRATOR_SCAN_V2.md','s6c_admission_fast_v1.py','README_S6C_ADMISSION_FAST_V1.md')
    return [binding(Path(__file__).with_name(n)) for n in names]


def validate_manifest(manifest,spec_binding,spec,workers):
    prior.validate_workers(workers)
    if manifest['execution_manifest']!=spec_binding or manifest['epoch']!=spec['epoch']:raise ValueError('Job manifest epoch binding differs')
    jobs=manifest['jobs']
    if not jobs or len(jobs)!=manifest['requested'] or len({j['job_key'] for j in jobs})!=len(jobs):raise ValueError('Empty, duplicate or incomplete job grid')
    if any(j['realtime'] for j in jobs) and workers!=1:raise ValueError('Paced jobs require one quiet worker')


def validate_name(name):
    if not isinstance(name,str) or not name or not name.replace('_','').isalnum():raise ValueError('Simple unique orchestration name required')


def prepare(args):
    validate_name(args.name)
    spec_binding,spec,common,execution=load_native(args.epoch);prior.load_fast()
    jobs_path=Path(args.jobs).resolve();manifest=common.read(jobs_path)
    validate_manifest(manifest,spec_binding,spec,args.workers)
    folder=REPORT/'orchestration'/args.name
    if folder.exists():raise ValueError('Fresh orchestration namespace required')
    # Original run() revalidates every job/input and current resource admission
    # before models; prepare binds the reviewable exact manifest without calls.
    value=dict(schema=SCHEMA,status='PREPARED_FOR_REVIEW',utc=utc(),native_epoch=spec_binding,jobs=binding(jobs_path),workers=args.workers,
        sources=source_rows(),original_native_authority=binding(REPORT/'EPOCH2_EXECUTION_MANIFEST.json'),
        scan_fixtures=binding(REPORT/'orchestration_review/SCANDIR_FIXTURES_v1.json'),
        scan_benchmark=binding(REPORT/'orchestration_review/SCANDIR_BENCHMARK_v1.json'),
        native_execution_epoch=spec['epoch'],orchestration_epoch=args.name,report_root=str(folder),hardware_invocations=0,
        explicit_native_environment=dict(JP_S6C_SIM=str(SIM),REPORT=str(common.REPORT),PAYLOAD=str(common.PAYLOAD)),
        intended_mutation='Parent coordinator common.tree_bytes only, using unchanged reviewed exact scanner; spawned native children import original modules.',
        invariants='Exact original APP/worker/common/assets/environment. Native identities, model factory/state, pool, owned cleanup, input verification, source scans, caps, reserves and stop/deadline logic are unchanged.',
        closure_precondition='At run admission, all recorded prior invocation owners/remaining children across epochs must be closed; preparation may occur while another epoch runs.')
    common.save(folder/'ADMISSION.json',value,immutable=True);return binding(folder/'ADMISSION.json')


def run(args):
    import psutil
    ab=binding(args.admission);admission=verified(ab)
    if admission['schema']!=SCHEMA or admission['status']!='PREPARED_FOR_REVIEW':raise ValueError('Prepared V3 admission required')
    if admission['sources']!=source_rows():raise ValueError('Reviewed wrapper/dependency sources changed')
    for b in admission['sources']:check_file(b)
    verified(admission['scan_fixtures']);verified(admission['scan_benchmark'])
    sb,spec,common,execution=load_native(admission['native_execution_epoch'])
    if admission['native_epoch']!=sb or admission['original_native_authority']!=binding(REPORT/'EPOCH2_EXECUTION_MANIFEST.json'):
        raise ValueError('Native admission authority differs')
    manifest=verified(admission['jobs']);validate_manifest(manifest,sb,spec,admission['workers'])
    folder=Path(admission['report_root']).resolve()
    if (REPORT/'orchestration').resolve() not in folder.parents or folder/'ADMISSION.json'!=Path(args.admission).resolve():raise ValueError('Report namespace differs')
    if (folder/'STARTED.json').exists():raise ValueError('Preserve existing attempt and prepare a fresh orchestration name')
    previous=prior_invocations(common);fast=prior.load_fast();process=psutil.Process()
    owner=dict(pid=process.pid,creation_time=process.create_time(),argv=process.cmdline())
    before={p.name for p in invocation_dirs(spec['epoch'])}
    common.save(folder/'STARTED.json',dict(schema=SCHEMA,status='RUNNING',utc=utc(),owner=owner,admission=ab,prior_invocations=previous,
        source_scope='Pinned additive native epoch with original epoch2 worker/common/APP semantics; coordinator-only exact current scan overlay.'),immutable=True)
    started=time.perf_counter();failure=None;result=None
    try:
        with prior.coordinator_patch(common,execution,fast):
            result=execution.run(sb['path'],admission['jobs']['path'],admission['workers'])
        return result
    except Exception as exc:
        failure=dict(error=repr(exc),traceback=traceback.format_exc());raise
    finally:
        new=[dict(path=str(p),artifacts=[binding(f) for f in sorted(p.iterdir()) if f.is_file()]) for p in invocation_dirs(spec['epoch']) if p.name not in before]
        children=[dict(pid=p.pid,creation_time=p.create_time()) for p in process.children(recursive=True)]
        common.save(folder/'CLOSURE.json',dict(schema=SCHEMA,status='CLOSED_WITH_FAILURE' if failure else 'CLOSED',utc=utc(),owner=owner,admission=ab,
            elapsed_sec=time.perf_counter()-started,result=result,failure=failure,original_native_invocations=new,remaining_owned_children=children,
            original_common_scanner_restored=common.tree_bytes.__module__=='s6c_common',
            scope='Original native run owns worker joining. Wrapper never clears stop markers or terminates unrelated processes. Owner exit requires external verification.'),immutable=True)


def fixtures(args):
    from copy import deepcopy
    import psutil
    sb,spec,common,execution=load_native(args.epoch);fast=prior.load_fast();checks=[]
    original=verified(binding(REPORT/'EPOCH2_EXECUTION_MANIFEST.json'))
    compatible_native(spec,original);checks.append('actual additive epoch exact original APP worker common models environment')
    for field in ('assets','versions','python','input_index','scene_manifest','state_policy'):
        changed=deepcopy(spec);changed[field]='changed'
        try:compatible_native(changed,original)
        except ValueError:checks.append('reject changed '+field)
        else:raise AssertionError(field)
    for name in ('s6c_execution.py','s6c_common.py'):
        changed=deepcopy(spec);next(b for b in changed['execution_files'] if Path(b['path']).name==name)['sha256']='0'*64
        try:compatible_native(changed,original)
        except ValueError:checks.append('reject whole module drift '+name)
        else:raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='s6c_overlay3_') as temp:
        root=Path(temp);(root/'file').write_bytes(b'abcd');old=common.tree_bytes;worker=execution.worker_job
        with prior.coordinator_patch(common,execution,fast):
            assert common.tree_bytes(root)==4 and execution.worker_job is worker
        assert common.tree_bytes is old;checks.append('parent scanner-only override and restoration')
        try:
            with prior.coordinator_patch(common,execution,fast):raise RuntimeError('fixture')
        except RuntimeError:pass
        assert common.tree_bytes is old and execution.worker_job is worker;checks.append('exception restores native worker and scanner')
        with patch.dict(globals(),REPORT=root):assert invocation_dirs('epoch4')==[]
        checks.append('absent target invocation directory is empty without creation')
        # Separate synthetic invocation namespaces with complete local records;
        # use the current PID with an explicitly different creation time to
        # prove recorded identity closure without relying on a guessed dead PID.
        identity=dict(pid=os.getpid(),creation_time=psutil.Process().create_time()-100.)
        for ep in ('epoch1','epoch2'):
            folder=root/ep/'invocations/fixture';folder.mkdir(parents=True)
            (folder/'owner.json').write_text(json.dumps(identity),encoding='utf-8')
            (folder/'closure.json').write_text(json.dumps(dict(remaining_owned_children=[])),encoding='utf-8')
            (folder/'completion.json').write_text('{}',encoding='utf-8')
        with patch.dict(globals(),REPORT=root):
            previous=prior_invocations(common)
            assert len(previous)==2 and {r['epoch'] for r in previous}=={'epoch1','epoch2'}
            checks.append('all prior epoch namespaces bound with closed recorded identities')
            (root/'epoch2/invocations/fixture/closure.json').unlink()
            try:prior_invocations(common)
            except FileNotFoundError:checks.append('missing prior closure fails before run')
            else:raise AssertionError('Incomplete closure accepted')
    current=dict(pid=os.getpid(),creation_time=psutil.Process().create_time())
    try:closed_identity(current,psutil.Process)
    except ValueError:checks.append('live recorded owner rejects')
    else:raise AssertionError('Live owner accepted')
    reused=dict(current,creation_time=current['creation_time']-100.)
    assert closed_identity(reused,psutil.Process)['alive'] is False;checks.append('PID creation time separates reuse')
    for value in (True,float('nan'),float('inf'),-1,0):
        try:closed_identity(dict(pid=os.getpid(),creation_time=value),psutil.Process)
        except ValueError:checks.append('invalid finite process creation identity rejected')
        else:raise AssertionError('Invalid process identity accepted')
    for name in ('../escape','sub/folder','C:/absolute','',None):
        try:validate_name(name)
        except ValueError:checks.append('invalid orchestration name rejected before prepare')
        else:raise AssertionError('Unsafe namespace accepted')
    fake=dict(execution_manifest=sb,epoch=spec['epoch'],requested=1,jobs=[dict(job_key='fixture',realtime=False)])
    validate_manifest(fake,sb,spec,4);checks.append('exact nonpaced manifest admission')
    for changed,workers in [(dict(fake,epoch='wrong'),4),(dict(fake,requested=2),4),
        (dict(fake,requested=2,jobs=fake['jobs']*2),4),(dict(fake,jobs=[dict(job_key='fixture',realtime=True)]),2),(fake,True)]:
        try:validate_manifest(changed,sb,spec,workers)
        except ValueError:checks.append('bad epoch count duplicate pace or worker guard')
        else:raise AssertionError('Bad manifest admitted')
    code="import sys,json;sys.path.insert(0,sys.argv[1]);import s6c_common,s6c_execution;print(json.dumps({'common':s6c_common.__file__,'worker':s6c_execution.worker_job.__code__.co_filename,'scanner':s6c_common.tree_bytes.__module__}))"
    child=prior.subprocess.run([str(EDGE),'-c',code,str(Path(spec['root'])/'scripts')],capture_output=True,text=True,check=True,timeout=30)
    loaded=json.loads(child.stdout)
    assert Path(loaded['common']).resolve()==Path(common.__file__).resolve() and Path(loaded['worker']).resolve()==Path(execution.__file__).resolve() and loaded['scanner']=='s6c_common'
    checks.append('fresh child imports original target native modules and original scanner')
    data=dict(schema=SCHEMA,status='PASS',utc=utc(),sources=source_rows(),native_epoch=sb,checks=checks,child_import=loaded,neural_invocations=0,
        scope='Source hashes, module imports and isolated guards only. No original run, pool or model factory called.')
    target=REPORT/'orchestration_review'/('ORCHESTRATOR_SCAN_FIXTURES_'+args.name+'.json')
    common.save(target,data,immutable=True);return binding(target)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','run','test'))
    p.add_argument('--epoch',choices=tuple(TRUSTED_EPOCHS),default='epoch5');p.add_argument('--jobs',type=Path);p.add_argument('--workers',type=int,default=4)
    p.add_argument('--name',default='scan_v4');p.add_argument('--admission',type=Path);args=p.parse_args()
    try:validate_name(args.name)
    except ValueError as exc:p.error(str(exc))
    if args.mode=='prepare' and args.jobs is None:p.error('prepare requires --jobs')
    if args.mode=='run' and args.admission is None:p.error('run requires --admission')
    print(json.dumps({'prepare':prepare,'run':run,'test':fixtures}[args.mode](args),indent=2,allow_nan=False),flush=True)

if __name__=='__main__':main()
