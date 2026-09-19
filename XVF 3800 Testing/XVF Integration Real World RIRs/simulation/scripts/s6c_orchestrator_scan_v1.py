"""Coordinator-only exact scan overlay. See README_S6C_ORCHESTRATOR_SCAN_V1.md."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import importlib
import importlib.util
from importlib.metadata import version as package_version
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime,timezone
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
EDGE=SIM.parents[2]/'.edge-speech-env/python.exe'
EPOCH_SHA='1f7f0e10186eb1187d05d9be258372d6dfbe39ec3741c2ce2976a2ca3d005cdb'
FAST_SHA='f7259056cd66d9d031e71b0f319844b2e7aaa798951e538ca0a45160ddcc0166'
SCHEMA='jp_s6c_coordinator_scan_overlay.v1'


def utc():return datetime.now(timezone.utc).isoformat()


def binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def verified(item):
    raw=Path(item['path']).read_bytes()
    if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Changed admitted file: '+item['path'])
    return json.loads(raw)


def check_file(item):
    if binding(item['path'])!=item:raise ValueError('Changed admitted source: '+item['path'])


def validate_workers(value):
    if type(value) is not int or not 1<=value<=4:raise ValueError('One to four workers required')


def load_native():
    spec_binding=binding(REPORT/'EPOCH2_EXECUTION_MANIFEST.json')
    if spec_binding['sha256']!=EPOCH_SHA:raise ValueError('Exact unchanged native epoch2 is required')
    spec=verified(spec_binding)
    if Path(sys.executable).resolve()!=EDGE.resolve() or sys.version!=spec['python']:raise ValueError('Use exact epoch EDGE interpreter')
    if any(package_version(k)!=v for k,v in spec['versions'].items()):raise ValueError('Native package version changed')
    for item in spec['execution_files']:check_file(item)
    for item in spec['assets']:
        if binding(item['path'])['sha256']!=item['sha256']:raise ValueError('Frozen asset bytes changed')
    scripts=Path(spec['root'])/'scripts'
    if any(name in sys.modules for name in ('s6c_common','s6c_execution')):raise ValueError('Native modules were preloaded before source admission')
    sys.path.insert(0,str(scripts))
    common=importlib.import_module('s6c_common');execution=importlib.import_module('s6c_execution')
    if Path(common.__file__).resolve()!=scripts/'s6c_common.py' or Path(execution.__file__).resolve()!=scripts/'s6c_execution.py':
        raise ValueError('Native modules did not resolve to exact frozen sources')
    return spec_binding,spec,common,execution


def load_fast():
    path=Path(__file__).with_name('s6c_admission_fast_v1.py')
    if binding(path)['sha256']!=FAST_SHA:raise ValueError('Reviewed exact scanner source differs')
    module_spec=importlib.util.spec_from_file_location('s6c_reviewed_fast_scan',path)
    module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
    return module


@contextmanager
def coordinator_patch(common,execution,fast):
    names=('worker_init','worker_job','extract','validate_job','verify_job','run','make_job','job_identity')
    protected={name:getattr(execution,name) for name in names}
    original=common.tree_bytes
    if execution.admit_work is not common.admit_work or execution.resources is not common.resources or common.resources.__globals__ is not common.__dict__:
        raise ValueError('Unexpected frozen admission/global function contract')
    if original.__module__!='s6c_common' or Path(original.__code__.co_filename).resolve()!=Path(common.__file__).resolve():
        raise ValueError('Original scanner function was already replaced')
    common.tree_bytes=fast.tree_bytes
    try:yield
    finally:
        common.tree_bytes=original
        if any(getattr(execution,name) is not value for name,value in protected.items()):raise RuntimeError('Protected frozen execution function changed')


def source_rows():
    return [binding(Path(__file__).with_name(name)) for name in ('s6c_orchestrator_scan_v1.py','README_S6C_ORCHESTRATOR_SCAN_V1.md','s6c_admission_fast_v1.py','README_S6C_ADMISSION_FAST_V1.md')]


def prior_invocations(common):
    import psutil
    root=REPORT/'epoch2/invocations';rows=[]
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():continue
        owner=common.read(folder/'owner.json');closure=common.read(folder/'closure.json')
        common.read(folder/'completion.json')
        identities=[{k:owner[k] for k in ('pid','creation_time')},*closure['remaining_owned_children']]
        states=[]
        for item in identities:
            alive=False
            try:alive=abs(psutil.Process(item['pid']).create_time()-item['creation_time'])<.01
            except psutil.NoSuchProcess:pass
            if alive:raise ValueError('A prior epoch2 invocation/process is still alive: '+str(item))
            states.append(dict(**item,alive=False))
        rows.append(dict(directory=str(folder),artifacts=[binding(p) for p in sorted(folder.iterdir()) if p.is_file()],
            verified_closed_process_identities=states,
            scope='Every prior epoch2 invocation file is bound. Historical active_records may remain after graceful join; actual owner/recorded remaining process identities must be closed.'))
    return rows


def prepare(args):
    spec_binding,spec,common,execution=load_native();validate_workers(args.workers);load_fast()
    jobs_path=Path(args.jobs).resolve();manifest=common.read(jobs_path)
    if manifest['execution_manifest']!=spec_binding or manifest['epoch']!='epoch2':raise ValueError('Jobs must bind exact unchanged native epoch2')
    if len(manifest['jobs'])!=manifest['requested'] or len({j['job_key'] for j in manifest['jobs']})!=len(manifest['jobs']):raise ValueError('Invalid or duplicate native jobs')
    if any(j['realtime'] for j in manifest['jobs']) and args.workers!=1:raise ValueError('Paced jobs require one worker')
    folder=REPORT/'orchestration'/args.name
    if folder.exists():raise ValueError('Fresh named orchestration namespace required')
    value=dict(schema=SCHEMA,status='PREPARED_FOR_REVIEW',utc=utc(),native_epoch=spec_binding,jobs=binding(jobs_path),workers=args.workers,
        sources=source_rows(),scan_fixtures=binding(REPORT/'orchestration_review/SCANDIR_FIXTURES_v1.json'),
        scan_benchmark=binding(REPORT/'orchestration_review/SCANDIR_BENCHMARK_v1.json'),
        intended_mutation='Coordinator process only: frozen s6c_common.tree_bytes points to separately bound exact scandir implementation during unchanged frozen run().',
        invariants='Original worker_init/worker_job/extract/validate_job/verify_job/ProcessPool code, every source/model hash, identity, reservation, free-space/RAM/stop/deadline check and native state remains unchanged.',
        native_execution_epoch='epoch2',orchestration_epoch=args.name,report_root=str(folder),hardware_invocations=0)
    common.save(folder/'ADMISSION.json',value,immutable=True)
    return binding(folder/'ADMISSION.json')


def run(args):
    import psutil
    admission_binding=binding(args.admission);admission=verified(admission_binding)
    if admission['schema']!=SCHEMA or admission['status']!='PREPARED_FOR_REVIEW':raise ValueError('Prepared exact overlay admission required')
    if admission['sources']!=source_rows():raise ValueError('Reviewed wrapper/scanner/README sources changed')
    for item in admission['sources']:check_file(item)
    verified(admission['scan_fixtures']);verified(admission['scan_benchmark'])
    validate_workers(admission['workers'])
    spec_binding,spec,common,execution=load_native()
    if admission['native_epoch']!=spec_binding:raise ValueError('Admitted native epoch differs')
    manifest=verified(admission['jobs'])
    if manifest['execution_manifest']!=spec_binding or manifest['epoch']!='epoch2':raise ValueError('Admitted job manifest native identity differs')
    if any(j['realtime'] for j in manifest['jobs']) and admission['workers']!=1:raise ValueError('Paced jobs require one worker')
    folder=Path(admission['report_root']).resolve()
    if (REPORT/'orchestration').resolve() not in folder.parents or folder/'ADMISSION.json'!=Path(args.admission).resolve():raise ValueError('Overlay report namespace differs')
    if (folder/'STARTED.json').exists():raise ValueError('Preserve the existing orchestration attempt; prepare a fresh version')
    previous=prior_invocations(common);fast=load_fast();process=psutil.Process()
    owner=dict(pid=process.pid,creation_time=process.create_time(),argv=process.cmdline())
    before_dirs={p.name for p in (REPORT/'epoch2/invocations').iterdir() if p.is_dir()}
    common.save(folder/'STARTED.json',dict(schema=SCHEMA,status='RUNNING',utc=utc(),owner=owner,admission=admission_binding,
        prior_invocations=previous,source_scope='Original frozen native epoch2 run with coordinator-only storage enumeration overlay. Worker spawn resolves frozen original modules from first sys.path entry.'),immutable=True)
    started=time.perf_counter();failure=None;result=None
    try:
        with coordinator_patch(common,execution,fast):
            result=execution.run(admission['native_epoch']['path'],admission['jobs']['path'],admission['workers'])
        return result
    except Exception as exc:
        failure=dict(error=repr(exc),traceback=traceback.format_exc());raise
    finally:
        after_dirs=[p for p in (REPORT/'epoch2/invocations').iterdir() if p.is_dir() and p.name not in before_dirs]
        new_invocations=[dict(path=str(p),artifacts=[binding(f) for f in sorted(p.iterdir()) if f.is_file()]) for p in after_dirs]
        children=[dict(pid=p.pid,creation_time=p.create_time()) for p in process.children(recursive=True)]
        common.save(folder/'CLOSURE.json',dict(schema=SCHEMA,status='CLOSED_WITH_FAILURE' if failure else 'CLOSED',utc=utc(),owner=owner,
            admission=admission_binding,elapsed_sec=time.perf_counter()-started,result=result,failure=failure,
            original_native_invocations=new_invocations,remaining_owned_children=children,
            original_common_scanner_restored=common.tree_bytes.__module__=='s6c_common',
            scope='Original run owns worker joining and durable receipts. This wrapper does not terminate unrelated processes or clear stop markers. Current owner exit is verified externally.'),immutable=True)


def fixtures(args):
    spec_binding,spec,common,execution=load_native();fast=load_fast();checks=[]
    original=common.tree_bytes;worker=execution.worker_job
    with tempfile.TemporaryDirectory(prefix='s6c_overlay_') as temp:
        root=Path(temp);(root/'x').write_bytes(b'abc')
        with coordinator_patch(common,execution,fast):
            assert common.tree_bytes(root)==3 and execution.worker_job is worker
            assert execution.admit_work.__globals__['tree_bytes'] is fast.tree_bytes
        assert common.tree_bytes is original;checks.append('only coordinator common scanner changes and restores')
        try:
            with coordinator_patch(common,execution,fast):raise RuntimeError('fixture exception')
        except RuntimeError:pass
        assert common.tree_bytes is original and execution.worker_job is worker;checks.append('exception restores scanner and preserves worker function')
        item=binding(root/'x');(root/'x').write_bytes(b'changed')
        try:check_file(item)
        except ValueError:checks.append('same-path changed source bytes rejected')
        else:raise AssertionError('Changed source accepted')
    for value in (0,5,True):
        try:validate_workers(value)
        except ValueError:pass
        else:raise AssertionError('Invalid worker cap accepted')
    checks.append('worker cap and bool guard')
    code="import sys,json;sys.path.insert(0,sys.argv[1]);import s6c_common,s6c_execution;print(json.dumps({'common':s6c_common.__file__,'scanner_module':s6c_common.tree_bytes.__module__,'worker':s6c_execution.worker_job.__code__.co_filename}))"
    child=subprocess.run([str(EDGE),'-c',code,str(Path(spec['root'])/'scripts')],capture_output=True,text=True,check=True,timeout=30)
    loaded=json.loads(child.stdout)
    assert loaded['scanner_module']=='s6c_common' and Path(loaded['common']).resolve()==Path(common.__file__).resolve() and Path(loaded['worker']).resolve()==Path(execution.__file__).resolve()
    checks.append('fresh child imports original frozen scanner and worker sources')
    target=REPORT/'orchestration_review'/('ORCHESTRATOR_SCAN_FIXTURES_'+args.name+'.json')
    common.save(target,dict(schema=SCHEMA,status='PASS',utc=utc(),sources=source_rows(),native_epoch=spec_binding,checks=checks,
        child_import=loaded,neural_invocations=0,scope='Model-free module/admission guards only; no original run() or ProcessPool/model call.'),immutable=True)
    return binding(target)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('prepare','run','test'));p.add_argument('--jobs',type=Path);p.add_argument('--workers',type=int,default=4)
    p.add_argument('--name',default='scan_v1');p.add_argument('--admission',type=Path)
    args=p.parse_args()
    if not args.name.replace('_','').isalnum():p.error('Simple unique orchestration name required')
    if args.mode=='prepare' and args.jobs is None:p.error('prepare requires --jobs')
    if args.mode=='run' and args.admission is None:p.error('run requires --admission')
    print(json.dumps({'prepare':prepare,'run':run,'test':fixtures}[args.mode](args),indent=2,allow_nan=False),flush=True)


if __name__=='__main__':main()
