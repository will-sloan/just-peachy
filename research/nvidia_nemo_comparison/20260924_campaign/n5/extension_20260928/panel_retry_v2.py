"""One supervised extension retry with original N4 observation contracts. README_PANEL_RETRY_V2.md."""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import re
import shutil
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
N5 = HERE.parent
N4 = N5.parent/'n4'
LOCAL = N5.parents[4]/'local'
BASE = LOCAL/'n5/research-extension-20260928'
sys.path[:0] = [str(N4), str(N5)]
from common import audio_only, bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_slot import process_census, competitors
from window_guard import window, snapshot
from private_application_two_cpu_v1 import PrivateApplicationProcess


def require(ok, message):
    if not ok:
        raise ValueError(message)


def run_path(name):
    require(re.fullmatch('[a-z0-9-]+', name) is not None, 'Simple run name required')
    return BASE/name


def worker_owners(worker):
    values = [dict(pid=worker['pid'], create_time=worker['create_time'])]
    if worker.get('child_pid'):
        values.append(dict(pid=worker['child_pid'], create_time=worker['child_create_time']))
    return values


def check_bindings(a):
    require(a['schema'] == 'extension-n4-targeted-retry-v1', 'Wrong admission')
    for b in a['bindings']:
        verify(b)
    require(a['cpus'] == [4,14] and a['threads_per_model'] == 1 and a['GPU'] is False, 'Resource contract differs')
    require(a['contract']['encoder'] == 'E0' and a['contract']['diarization'] == 'D1'
            and a['contract']['mode'] == 'open_with_names', 'Wrong composition/mode')
    audio_only(a['job'])
    require(a['source']['schema'] == 'extended-panel-journal-v1', 'Wrong source')
    require(a['source']['retention_tests_passed'] == 8, 'Retention tests missing')
    window()
    return a


def prepare(name, backend):
    import psutil
    own = identity(pin()); w = window(); output = run_path(name); pre = run_path(name+'-precheck')
    require(not output.exists() and not pre.exists(), 'Fresh output required')
    stem = 'a0' if backend == 'nemotron_hybrid' else 'a2'
    ref_binding = bind(LOCAL/f'n5/prepi-20260928/{stem}-costs-v2-REVIEW.json')
    ref = load(ref_binding['path'])
    require(ref['status'] == 'PASS_WINDOWS_CUMULATIVE_COSTS_FULL_FILE_PARITY', 'Current source not independently reviewed')
    parent_run = LOCAL/f'n5/prepi-20260928/{stem}-costs-v2'
    old = load(parent_run/'ADMISSION.json')
    require(old['backend_key'] == backend, 'Backend differs')
    sb = bind(BASE/'derivatives/panel-journal-v1/DERIVATIVE.json'); source = load(sb['path'])
    require(source['parent_source_receipt'] == old['source_receipt'], 'Source ancestry differs')
    release = Path(source['prototype'])
    plan_binding = bind(LOCAL/'n4/paced-plan-guarded-v2/PLAN.json'); plan = load(plan_binding['path'])
    row = next(r for r in plan['rows'] if r['contract']['backend_key'] == backend and r['job']['job_id'] == 'N2_S45_01_01_O0')
    job = audio_only(row['job']); contract = row['contract']
    require(job['audio_sha256'] == old['audio']['sha256'], 'Different source')
    gb = plan['context']['gallery_preparation']; verify(gb); gallery = load(gb['path']); verify(gallery['catalog'])
    catalog = bind(release/'config/backends.json')
    from panel_catalog_v1 import rebind_gallery
    gallery, catalog_proof = rebind_gallery(gallery, load(gallery['catalog']['path']), load(catalog['path']), catalog, backend, contract)
    # No new models or vectors are produced; pin the existing E0 payload used by this condition.
    profile = gallery['encoders']['E0']['conditions'][contract['gallery_condition']]
    gallery_binding = profile['condition']['gallery']; verify(gallery_binding)
    cap = 128*1024**2
    observed = snapshot(LOCAL, cap)
    census = process_census(LOCAL.parent)
    require(not competitors(census, [own,identity(psutil.Process().parent())]), 'Competing worker/helper')
    closed = worker_owners(load(LOCAL/'supervision/worker.json'))
    require(all(exact_process(o) is None for o in closed), 'Prior owner alive')
    pre.mkdir(); freeze(pre/'GALLERY.json',gallery); freeze(pre/'CENSUS.json',observed)
    files = [dict(path=str(release/k),**v) for k,v in source['files'].items()]
    code = [bind(p) for p in sorted(N4.glob('*.py'))]
    code += [bind(HERE/n) for n in ('panel_retry_v1.py','panel_retry_v2.py','panel_catalog_v1.py','build_panel_retry_v2.py','README_PANEL_RETRY_V2.md','build_panel_source_v1.py','README_PANEL_RETRY_V1.md','window_guard.py','WINDOW.json','GUARD_DERIVATION.json')]
    code += [bind(N5/'private_application_two_cpu_v1.py')]
    bindings = files+code+old['assets']+old['runtime_configs']+[old['audio'],old['acceptance'],sb,source['parent_source_receipt'],ref_binding,plan_binding,gb,gallery_binding,catalog]
    bindings = list({b['path']:b for b in bindings}.values())
    for b in bindings:
        verify(b)
    now = datetime.now(timezone.utc); expires = now+timedelta(seconds=600)
    require(expires < datetime.fromisoformat(w['checkpoint_utc']), 'Insufficient window')
    a = dict(schema='extension-n4-targeted-retry-v1', admitted_utc=now.isoformat(), expires_utc=expires.isoformat(),
        source=source, source_receipt=sb, release=str(release), bindings=bindings,
        catalog_rebinding=catalog_proof, original_plan=plan_binding, original_cell_id=row['cell_id'], backend=backend, job=job, contract=contract,
        gallery=bind(pre/'GALLERY.json'), runtimes=old['runtime_configs'], models_root=plan['context']['models_root'],
        census=bind(pre/'CENSUS.json'), output_cap_bytes=cap, closed_prior_owners=closed,
        cpus=[4,14], threads_per_model=1, GPU=False, process_census=census, N4_accepted=False)
    a['bindings'] += [a['gallery'], a['census']]
    freeze(pre/'CHECK.json',a)
    spec = pre/'worker.json'
    freeze(spec,dict(argv=[sys.executable,'-B',str(Path(__file__).resolve()),'host','--name',name],cwd=str(HERE)))
    sys.path.insert(0,str(N5.parent/'supervision'))
    import supervisor
    started = supervisor.start(LOCAL/'supervision',spec)
    freeze(pre/'STARTED.json',dict(supervisor=started,spec=bind(spec),check=bind(pre/'CHECK.json')))
    print(dict(status='DISPATCHED_NOT_ACCEPTED',name=name,supervisor=started))


def fast_guard(a, output):
    require(datetime.now(timezone.utc) < datetime.fromisoformat(a['expires_utc']), 'Admission expired')
    require(not (output/'CANCEL').exists(), 'Cancellation requested')
    for drive,gib in [('C',50),('G',75)]:
        require(shutil.disk_usage(drive+':/').free >= gib*1024**3, 'Free-space floor breached')
    total = 0
    for p in output.rglob('*'):
        try:
            if p.is_file(): total += p.stat().st_size
        except FileNotFoundError:
            pass
    require(total < a['output_cap_bytes'], 'Output reservation exceeded')


def child(name, phase):
    import psutil
    output = run_path(name); a = check_bindings(load(output/'ADMISSION.json'))
    who = identity(psutil.Process()); registered = load(output/(phase+'-OWNER.json'))
    require(who == registered['owner'] and exact_process(a['owner']) is not None
            and psutil.Process().ppid() == a['owner']['pid'] and psutil.Process().cpu_affinity() == [4,14], 'Child identity/affinity differs')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
    release = Path(a['release']); sys.path[:0] = [str(release),str(release/'vendor'),str(release.parent)]
    from paced_application_cell_v2 import ApplicationCell
    root = output/phase; root.mkdir(); cell = None; error = None; result = None
    with (root/'stdout.log').open('x',encoding='utf-8') as out, (root/'stderr.log').open('x',encoding='utf-8') as err:
        sys.stdout=out; sys.stderr=err
        try:
            fast_guard(a,output)
            cell = ApplicationCell(root/'cell',a['job'],a['contract'])
            kwargs = dict(source=release,models_root=Path(a['models_root']),runtimes=a['runtimes'],gallery_preparation=a['gallery'])
            if phase == 'prestart':
                from controller_projection import forbid_inference
                with forbid_inference():
                    cell.prepare(**kwargs)
                    require(cell.c.engine is None and cell.c.consumer is None and not cell.started, 'Prestart ran inference')
            else:
                cell.prepare(**kwargs)
                def check(*args):
                    require(exact_process(a['owner']) is not None, 'Coordinator absent')
                    fast_guard(a,output)
                cell.run_source(admission_check=check)
        except BaseException as exc:
            error = type(exc).__name__+': '+str(exc)[:2000]
            traceback.print_exc()
        finally:
            if cell is not None:
                try:
                    result=cell.close()
                    if cell.engine is not None:
                        freeze(root/'TELEMETRY.json',cell.engine.telemetry())
                except BaseException as exc:
                    error=(error or '')+'; close: '+repr(exc); traceback.print_exc()
            expected = 'PREPARED_ONLY_CLOSED' if phase=='prestart' else 'CELL_WITH_SOURCE_DELIVERY_CLOSED_REQUIRES_REVIEW'
            okay = error is None and result is not None and result['status'] == expected
            freeze(root/'RESULT.json',dict(status='COLLECTED_REQUIRES_REVIEW' if okay else 'FAILED_PRESERVED',
                phase=phase,owner=who,error=error,cell_result=bind(root/'cell/RESULT.json') if (root/'cell/RESULT.json').exists() else None,
                N4_accepted=False,integrated_N4_cells=0))
    return int(not okay)


def host(name):
    import psutil
    own = identity(pin()); output=run_path(name); pre=run_path(name+'-precheck')
    require(not output.exists(), 'Fresh output required')
    a=check_bindings(load(pre/'CHECK.json'))
    require(0 <= (datetime.now(timezone.utc)-datetime.fromisoformat(a['admitted_utc'])).total_seconds() < 120, 'Stale admission')
    require(all(exact_process(o) is None for o in a['closed_prior_owners']), 'Prior owner revived')
    for _ in range(50):
        worker=load(LOCAL/'supervision/worker.json')
        if worker.get('child_pid') == own['pid'] and worker.get('child_create_time') == own['create_time']: break
        time.sleep(.1)
    require(worker.get('child_pid') == own['pid'] and worker.get('child_create_time') == own['create_time'], 'Unsupervised coordinator')
    require(exact_process(worker_owners(worker)[0]) is not None, 'Supervisor absent')
    require(load(LOCAL/'supervision/worker_spec.json')['argv'] == psutil.Process().cmdline(), 'Supervisor argv differs')
    output.mkdir(); a.update(owner=own,supervisor=worker,precheck=bind(pre/'CHECK.json'))
    freeze(output/'ADMISSION.json',a); phases=[]; error=None
    try:
        for phase in ('prestart','infer'):
            fast_guard(a,output)
            proc=PrivateApplicationProcess(output/(phase+'-lifetime'),executable_binding=bind(sys.executable),script_binding=bind(__file__),cpu=(4,14))
            proc.argv=[sys.executable,'-B',str(Path(__file__).resolve()),'child','--name',name,'--phase',phase]
            with proc:
                proc.spawn_suspended()
                proc.resume(lambda who,**values:freeze(output/(phase+'-OWNER.json'),dict(owner=who,**values)))
                began=time.monotonic()
                while not proc.root_exited():
                    require(time.monotonic()-began < 270,'Child lifetime exceeded')
                    fast_guard(a,output);time.sleep(1)
            phases.append(dict(phase=phase,result=bind(output/phase/'RESULT.json'),lifetime=bind(proc.output/'LIFETIME.json')))
            r=load(output/phase/'RESULT.json'); life=proc.receipt
            require(r['status']=='COLLECTED_REQUIRES_REVIEW' and life['forced'] is False
                    and life['root_exit_code']==0 and life['job_empty_verified'] is True, 'Cell or lifetime failed')
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc)
    for b in a['bindings']:verify(b)
    freeze(output/'RESULT.json',dict(status='COLLECTED_TARGETED_RETRY_REQUIRES_REVIEW' if error is None else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),phases=phases,error=error,
        N4_accepted=False,N5_complete=False,CM5_tested=False,integrated_N4_cells=0))
    return int(error is not None)


def review(name):
    pin(); output=run_path(name); rb=bind(output/'RESULT.json'); r=load(rb['path']); verify(r['admission']); a=check_bindings(load(r['admission']['path']))
    owners=worker_owners(a['supervisor'])+[a['owner']]
    for p in output.glob('*-OWNER.json'):owners.append(load(p)['owner'])
    require(all(exact_process(o) is None for o in owners),'Exact owner remains')
    result=dict(status='FAILED_PRESERVED',result=rb,admission=r['admission'],closed_exact_owners=owners,
                original_cell_id=a['original_cell_id'],N4_accepted=False,N5_complete=False,CM5_tested=False,integrated_N4_cells=0)
    try:
        require(r['status']=='COLLECTED_TARGETED_RETRY_REQUIRES_REVIEW','Collection failed')
        require([p['phase'] for p in r['phases']]==['prestart','infer'],'Missing phase')
        for phase in r['phases']:
            verify(phase['result']);verify(phase['lifetime']);v=load(phase['result']['path']);life=load(phase['lifetime']['path'])
            require(v['status']=='COLLECTED_REQUIRES_REVIEW' and v['error'] is None,'Child failed')
            require(life['status']=='OWNED_PROCESS_LIFETIME_CLOSED' and life['forced'] is False and life['root_exit_code']==0
                    and life['job_empty_verified'] is True and life['observed_members_exited'] is True,'Unclosed application')
            verify(v['cell_result']);c=load(v['cell_result']['path'])
            require(c['controller_closed'] is True and c['controller_worker_exited'] is True and not c['errors'],'Controller closure failed')
        cell=output/'infer/cell'
        from application_closure_v2 import validate_complete
        from application_delivery import review_files
        from review_native_journal import inspect, require_complete
        engine=load(cell/'ENGINE_CLOSURE.json');archive=load(cell/'ARCHIVE_INTEGRITY.json')
        result['closure']=validate_complete(engine,archive)
        result['delivery']=review_files(cell,a['job'],a['contract'],[bind(Path(a['release'])/p) for p in ('app/pipeline.py','app/buffers.py')])
        result['native_journal']=require_complete(inspect(Path(engine['session']),job=a['job']))
        result['telemetry']=bind(output/'infer/TELEMETRY.json')
        result['status']='PASS_TARGETED_APPLICATION_STRUCTURE_ONLY'
        result['scope']='Original N4 observation contracts on the current source; semantic accuracy, complete timing and panel population review remain required.'
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
    for b in a['bindings']:verify(b)
    freeze(BASE/(name+'-REVIEW.json'),result)
    print(dict(status=result['status'],error=result.get('error'),output=str(BASE/(name+'-REVIEW.json'))))
    return int(result['status']=='FAILED_PRESERVED')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','host','child','review']);p.add_argument('--name',required=True)
    p.add_argument('--backend',choices=['nemotron_hybrid','nemotron_600m']);p.add_argument('--phase',choices=['prestart','infer'])
    args=p.parse_args()
    if args.action=='prepare':
        require(args.backend is not None,'Backend required');prepare(args.name,args.backend)
    elif args.action=='host':raise SystemExit(host(args.name))
    elif args.action=='child':
        require(args.phase is not None,'Phase required');raise SystemExit(child(args.name,args.phase))
    else:raise SystemExit(review(args.name))
