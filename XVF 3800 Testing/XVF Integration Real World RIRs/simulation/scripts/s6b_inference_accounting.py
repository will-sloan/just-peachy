"""Read-only native/replay accounting. See README_S6B_INFERENCE_ACCOUNTING.md."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid
import psutil

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6B/20260909T230840Z'


def utc():return datetime.now(timezone.utc).isoformat()
def snapshot(path):
    path=Path(path).resolve()
    for attempt in range(20):
        try:before=path.stat();raw=path.read_bytes();after=path.stat()
        except PermissionError:
            if attempt==19:raise
            time.sleep(.05);continue
        if (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns) and len(raw)==after.st_size:
            try:return json.loads(raw.decode('utf-8-sig')),dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),raw
            except json.JSONDecodeError:
                if attempt==19:raise
        time.sleep(.05)
    raise ValueError('No stable JSON snapshot: '+str(path))
def file_binding(path):
    path=Path(path).resolve();raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    for attempt in range(20):
        try:os.replace(tmp,path);return
        except PermissionError:
            if attempt==19:raise
            time.sleep(.1)
def process_alive(pid,created):
    try:return abs(psutil.Process(int(pid)).create_time()-float(created))<.001
    except psutil.Error:return False
def logical(row):return (row['recipe_id'],row['case_id'],row['stream'])
def physical(row):return (row['job_key'],row['pid'],row['creation_time'],row['started_utc'])
def validate_epoch_receipt(row,execution_digest,complete_only=False):
    permitted={'COMPLETE'} if complete_only else {'STARTED','FAILED','COMPLETE'}
    if row['status'] not in permitted or row['identity']['execution_digest']!=execution_digest:raise ValueError('Native receipt status/epoch mismatch')
def cumulative_loads(rows):
    maximum={}
    for row in rows:
        value=row.get('resident_bundle_load_count')
        if value is None:continue
        if not isinstance(value,int) or value<0:raise ValueError('Invalid cumulative resident load counter')
        key=(row['pid'],row['creation_time']);maximum[key]=max(maximum.get(key,0),value)
    return maximum
def aggregate(rows):
    rows=list(rows);operations=Counter()
    for row in rows:operations.update(row.get('actual_neural_counts',{}))
    def total(field):
        values=[float(r[field]) for r in rows if field in r]
        if not all(math.isfinite(v) and v>=0 for v in values):raise ValueError('Invalid accounting cost '+field)
        return dict(total=sum(values),observed_receipts=len(values),missing_receipts=len(rows)-len(values))
    return dict(receipts=len(rows),completed=sum(r['status']=='COMPLETE' for r in rows),status_counts=dict(Counter(r['status'] for r in rows)),
        observed_native_operation_events=dict(operations),audio_duration_sec=total('audio_duration_sec'),
        inclusive_session_wall_sec=total('full_engine_wall_sec'),full_process_cpu_sec=total('full_process_cpu_sec'),
        nested_resident_admission_check_wall_sec=total('initial_or_changed_recipe_model_load_sec'))


def admission_audit(report,spec,read):
    admission=read(report/'FULL_CONFIRMATION_ADMISSION.json');recipes=admission['recipes']
    inputs=read(spec['input_index']['path']);all_cases={r['case_id'] for r in inputs['rows']};taps={r['stream'] for r in inputs['rows']}
    if taps!={'O0','O1'} or len(inputs['rows'])!=len(all_cases)*2 or {(r['case_id'],r['stream']) for r in inputs['rows']}!={(c,t) for c in all_cases for t in taps}:raise ValueError('Full input pair coverage differs')
    challenge=read(spec['challenge_panel']['path']);challenge_cases=set(challenge['case_ids'])
    registry=read(spec['effective_profile_registry']['path'])['profiles'];mapping={r['profile_id']:r for r in registry}
    base_profiles={r['profile_id'] for r in registry if r['recipe_id'] in {'R0','HISTORICAL_B0'}}
    added=set(admission['profiles_to_add'])
    if added&base_profiles or len(added)!=len(admission['profiles_to_add']):raise ValueError('Added profiles duplicated')
    if any(mapping[p]['recipe_id'] not in recipes for p in added):raise ValueError('Added profile lacks admitted recipe')
    if len(set(recipes))!=len(recipes):raise ValueError('Duplicate admitted recipe')
    prior_r0=read(admission['R0_index_path'],admission['R0_index_sha256'])
    prior_challenge=read(report/spec['epoch']/'CHALLENGE_NEURAL_INDEX.json')
    for index in (prior_r0,prior_challenge):
        if index['status']!='COMPLETE' or index['completed']!=index['requested'] or len(index['rows'])!=index['completed']:raise ValueError('Prior reuse index incomplete')
        if len({logical(r) for r in index['rows']})!=len(index['rows']):raise ValueError('Duplicate prior native index rows')
    expected={(recipe,c,tap) for recipe in recipes for c in all_cases for tap in taps}
    challenge_reuse={logical(r) for r in prior_challenge['rows'] if r['recipe_id'] in recipes}
    r0_reuse={logical(r) for r in prior_r0['rows']}
    if challenge_reuse!={(r,c,t) for r in recipes for c in challenge_cases for t in taps}:raise ValueError('Prior challenge reuse coverage differs')
    if r0_reuse!={('R0',c,t) for c in all_cases for t in taps}:raise ValueError('R0 extension was not full both-tap coverage')
    already=challenge_reuse|r0_reuse
    computed=dict(total_full_native_outputs=len(expected),prior_challenge_outputs_reused=len(challenge_reuse),
        prior_R0_extension_outputs_reused=len(r0_reuse-challenge_reuse),new_native_outputs=len(expected-already),
        total_full_profiles=len(base_profiles|added),total_predictions=len(base_profiles|added)*len(all_cases)*len(taps))
    mismatches={k:dict(declared=admission.get(k),computed=v) for k,v in computed.items() if admission.get(k)!=v}
    if mismatches:raise ValueError('Full admission arithmetic mismatch: '+json.dumps(mismatches))
    if admission['worker_ceiling']!=4:raise ValueError('Unexpected worker ceiling')
    lower=float(admission['estimated_new_wall_sec_lower']);upper=float(admission['estimated_new_wall_sec_upper'])
    if not 0<lower<=upper or not math.isfinite(upper):raise ValueError('Invalid prospective engineering estimate range')
    decision_review=file_binding(admission['independent_review_path'])
    if decision_review['sha256']!=admission['independent_review_sha256']:raise ValueError('Admission decision review binding changed')
    # Preserve the exact admitted bytes independently of future mutable pointers.
    source=report/'FULL_CONFIRMATION_ADMISSION.json';_,binding,raw=snapshot(source)
    if read.bindings[str(source.resolve())]['sha256']!=binding['sha256']:raise ValueError('Admission changed during audit')
    return dict(status='PASS',computed=computed,recipes=recipes,base_profile_count=len(base_profiles),added_profiles=sorted(added),
        expected_full_profiles=sorted(base_profiles|added),scene_count=len(all_cases),challenge_scene_count=len(challenge_cases),taps=sorted(taps),
        reuse_union=len(already),decision_review=decision_review,prospective_engineering_estimate_sec=[lower,upper],scope='Arithmetic and exact prior native index coverage; admission is not a statement that new jobs completed'),expected,already,raw


def run(args):
    started=utc();dependencies={};receipt_bindings=[]
    def read(path,expected=None):
        value,b,_=snapshot(path)
        if expected is not None and b['sha256']!=expected:raise ValueError('Supplied SHA mismatch: '+str(path))
        old=dependencies.get(b['path'])
        if old is not None and old!=b:raise ValueError('Repeated source changed: '+b['path'])
        dependencies[b['path']]=b;return value
    read.bindings=dependencies
    spec=read(args.report/(args.epoch.upper()+'_EXECUTION_MANIFEST.json'))
    if spec['epoch']!=args.epoch:raise ValueError('Epoch mismatch')
    for key in ('input_index','challenge_panel','effective_profile_registry'):read(spec[key]['path'],spec[key]['sha256'])
    admission,expected,already,admission_raw=admission_audit(args.report,spec,read)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');out=args.report/'inference_accounting'/('audit_'+stamp)
    out.mkdir(parents=True,exist_ok=False)
    preserved=out/'FULL_CONFIRMATION_ADMISSION_SNAPSHOT.json';preserved.write_bytes(admission_raw)
    payload=Path('G:/Just_Peachy_S6B')/args.report.name/args.epoch/'neural'
    runs={};attempts={};physical_rows={};logical_physical=defaultdict(set);missing_pair=[]
    for path in sorted(payload.rglob('run_receipt.json')):
        row,b,_=snapshot(path);receipt_bindings.append(b)
        validate_epoch_receipt(row,spec['execution_digest'],complete_only=True)
        key=logical(row)
        if key in runs and runs[key]['job_key']!=row['job_key']:raise ValueError('Conflicting native logical job')
        runs[key]=row;physical_rows[physical(row)]=row;logical_physical[key].add(physical(row))
        if not path.with_name('attempt_receipt.json').exists():missing_pair.append(str(path))
    for path in sorted(payload.rglob('attempt_receipt.json')):
        row,b,_=snapshot(path);receipt_bindings.append(b);pk=physical(row)
        validate_epoch_receipt(row,spec['execution_digest'])
        attempts[pk]=row;logical_physical[logical(row)].add(pk)
        if pk not in physical_rows or physical_rows[pk]['status']!='COMPLETE':physical_rows[pk]=row
    native_invocations=[];operation_refs=Counter();index_refs=set();fresh_refs=set()
    for folder in sorted((args.report/args.epoch/'invocations').iterdir()):
        if not folder.is_dir() or not (folder/'coordinator.json').exists():continue
        coordinator=read(folder/'coordinator.json');alive=process_alive(coordinator['pid'],coordinator['creation_time'])
        completed=read(folder/'completion.json') if (folder/'completion.json').exists() else None
        rows=completed['rows'] if completed is not None else read(folder/'rows.json')['rows'] if (folder/'rows.json').exists() else []
        cleanup=read(folder/'cleanup.json') if (folder/'cleanup.json').exists() else None
        counts=Counter(r['status'] for r in rows);operation_refs.update(counts)
        for row in rows:
            key=(row['recipe_id'],row['case_id'],row['stream']);index_refs.add(key)
            if row['status']=='COMPLETE':fresh_refs.add(key)
        native_invocations.append(dict(invocation=folder.name,pid=coordinator['pid'],creation_time=coordinator['creation_time'],alive=alive,
            recorded_row_counts=dict(counts),recorded_rows=len(rows),requested=completed.get('requested') if completed else None,
            completion_status=completed.get('status') if completed else None,cleanup_present=cleanup is not None,
            classification='ACTIVE' if alive else 'CLOSED_WITH_COMPLETION_RECEIPT' if completed else 'CLOSED_WITHOUT_COMPLETION_RECEIPT',
            note='Missing completion may be coordinator/status persistence fault, not failed neural audio; consult fault ledger'))
    indexes=[];prediction_files={};prediction_references=0;auxiliary_indexes=[];auxiliary_files={}
    primary_prediction_root=(args.report/args.epoch/'predictions').resolve()
    for path in sorted(args.report.glob('*PREDICTION_INDEX.json')):
        index=read(path)
        if index.get('epoch') not in {None,args.epoch}:continue
        rows=index['rows'];keys=[(r['profile_id'],r['case_id'],r['stream']) for r in rows]
        if len(keys)!=len(set(keys)):raise ValueError('Duplicate prediction rows in one index')
        primary_flags={Path(r['result']['path']).resolve().is_relative_to(primary_prediction_root) for r in rows}
        if len(primary_flags)!=1:raise ValueError('Index mixes primary and auxiliary prediction namespaces')
        if primary_flags=={False}:
            for row in rows:
                key=str(Path(row['result']['path']).resolve());prior=auxiliary_files.get(key)
                if prior is not None and prior!=row['result']:raise ValueError('Conflicting auxiliary prediction file binding')
                auxiliary_files[key]=row['result']
            auxiliary_indexes.append(dict(path=str(path),status=index['status'],row_count=len(rows),panel=index.get('panel'),
                scope='Separate validation materializations outside the authoritative epoch prediction namespace; not primary campaign cache conflicts'))
            continue
        for row in rows:
            key=(row['profile_id'],row['case_id'],row['stream']);prior=prediction_files.get(key)
            if prior is not None and prior['result']!=row['result']:raise ValueError('Conflicting indexed prediction bytes')
            prediction_files[key]=row
        prediction_references+=len(rows)
        indexes.append(dict(path=str(path),status=index['status'],requested=index['requested'],completed=index['completed'],row_count=len(rows),
            profiles=len(index['profiles']),scene_count=len(index['case_ids']),reported_model_free_invocation_elapsed_sec=index.get('elapsed_sec')))
    recipes=defaultdict(list)
    for row in runs.values():recipes[row['recipe_id']].append(row)
    loads=cumulative_loads(physical_rows.values());workers=[]
    for (pid,created),value in sorted(loads.items()):
        rows=[r for r in physical_rows.values() if (r['pid'],r['creation_time'])==(pid,created)]
        workers.append(dict(pid=pid,creation_time=created,alive=process_alive(pid,created),observed_cumulative_bundle_loads=value,
            physical_receipts=len(rows),recipes=sorted({r['recipe_id'] for r in rows})))
    full_complete=set(runs)&expected;missing=expected-set(runs)
    report=dict(schema='s6b-inference-accounting.v1',status='FULL_NATIVE_COMPLETE' if not missing else 'PARTIAL_RUNNING_SNAPSHOT',
        observation_started_utc=started,observation_finished_utc=utc(),admission=admission,admission_snapshot=file_binding(preserved),
        complete_full_native_outputs=len(full_complete),expected_full_native_outputs=len(expected),
        completed_new_since_admission=len(full_complete-already),prior_admitted_reuse_available=len(full_complete&already),
        missing_full_jobs=[dict(recipe_id=r,case_id=c,stream=t) for r,c,t in sorted(missing)],
        unique_completed_native_recipe_scene_tap_jobs=len(runs),physical_attempts_observed=len(physical_rows),
        physical_attempt_costs=aggregate(physical_rows.values()),successful_unique_native_costs=aggregate(runs.values()),
        per_recipe={r:aggregate(rows) for r,rows in sorted(recipes.items())},
        repeated_logical_attempts=[dict(recipe_id=k[0],case_id=k[1],stream=k[2],physical_attempt_count=len(v)) for k,v in logical_physical.items() if len(v)>1],
        complete_run_without_attempt_pair=missing_pair,
        resident_models=dict(observed_bundle_loads=sum(loads.values()),worker_count_with_counter=len(loads),workers=workers,
            semantics='Per-worker PID+creation-time maximum cumulative load count; never sum the counter over scenes. Missing/pre-receipt loads are unobserved.'),
        native_invocations=native_invocations,recorded_invocation_row_references=dict(operation_refs),
        unique_logical_jobs_referenced_by_invocations=len(index_refs),
        complete_native_jobs_without_recorded_fresh_invocation_row=[dict(recipe_id=r,case_id=c,stream=t) for r,c,t in sorted(set(runs)-fresh_refs)],
        fresh_invocation_rows_outside_initial_complete_receipt_inventory=[dict(recipe_id=r,case_id=c,stream=t) for r,c,t in sorted(fresh_refs-set(runs))],
        replay=dict(indexes=indexes,total_index_row_references=prediction_references,unique_indexed_prediction_outputs=len(prediction_files),
            auxiliary_validation_indexes=auxiliary_indexes,unique_auxiliary_validation_prediction_files=len(auxiliary_files),
            duplicate_cross_index_references=prediction_references-len(prediction_files),
            historical_B00_predictions=sum(k[0]=='B00' for k in prediction_files),
            actual_neural_feature_derived_predictions=sum(k[0]!='B00' for k in prediction_files),
            unique_recipe_scene_tap_sources_referenced=len({(r['recipe_id'],r['case_id'],r['stream']) for k,r in prediction_files.items() if k[0]!='B00'}),
            semantics='Indexed materialized outputs and repeated index references, not a count of model calls or replay cache hits. Replay does not record every execution/reuse separately. Active unindexed files are excluded.'),
        receipt_bindings=receipt_bindings,metadata_bindings=list(dependencies.values()),auditor=file_binding(__file__),
        model_free_fixture_checks=fixtures(),
        scope='Authoritative epoch2 native receipt accounting plus supplied completed/current prediction indexes. Historical B00 is reused S6A evidence; component smoke and future paced cells are separate. No heavyweight audio/vector/model/event-log files are opened.',
        limitations=['Live snapshots span a bounded read interval; newly completed files can appear after enumeration.','COMPLETE native operation event counts are observable API dispatch records, not hidden Sherpa forward-step counts.','Full engine wall includes nested resident admission; never add admission time again. Lane model timings are not summed into elapsed latency.','Coordinator failures can preserve complete audio receipts; closed-without-completion is not classified as model failure.','No source-byte tamper guard for heavyweight artifacts is replaced by this accounting; frozen execution and prediction guards remain authoritative.'])
    fault=args.report/'EXECUTION_FAULT_LEDGER.md'
    if fault.exists():report['fault_ledger']=file_binding(fault)
    save(out/'INFERENCE_ACCOUNTING.json',report)
    lines=['# S6B native and replay accounting','',f"Status: {report['status']}. Observed {len(full_complete)}/{len(expected)} admitted full-native outputs; {len(full_complete-already)} new since admission.",'',
        f"Admission verified: {admission['computed']['total_full_native_outputs']} native outputs = {admission['reuse_union']} reusable + {admission['computed']['new_native_outputs']} new. {admission['computed']['total_full_profiles']} profiles imply {admission['computed']['total_predictions']} full predictions, not that many neural executions.",'',
        f"Across epoch2: {len(runs)} unique completed native recipe/scene/tap jobs; {len(physical_rows)} recorded physical attempts. {sum(loads.values())} cumulative resident-bundle loads across {len(loads)} observed worker identities.",'',
        f"Prediction indexes reference {prediction_references} rows but {len(prediction_files)} unique outputs. Cross-index duplicates are reference reuse; model-free replay cache-hit executions are not separately logged.",'',
        'Native costs are summed once per unique successful job, with physical-attempt costs separately available. Inclusive session wall, CPU, operation counts and nested admission time remain distinct. No CM5 speed or memory claim follows.','',
        'Read the JSON scope and limitations. It binds every inspected compact receipt and metadata snapshot, preserves the admitted bytes, and reports missing jobs explicitly. It does not substitute for native artifact integrity or completed scoring.']
    (out/'INFERENCE_ACCOUNTING.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    save(args.report/'inference_accounting/LATEST.json',dict(status=report['status'],report=file_binding(out/'INFERENCE_ACCOUNTING.json'),summary=file_binding(out/'INFERENCE_ACCOUNTING.md')))
    return dict(status=report['status'],full_native_complete=len(full_complete),full_native_expected=len(expected),unique_epoch_native=len(runs),physical_attempts=len(physical_rows),resident_loads=sum(loads.values()),report=str(out/'INFERENCE_ACCOUNTING.json'))


def fixtures():
    rows=[dict(pid=1,creation_time=10,resident_bundle_load_count=x) for x in (1,1,2)]+[dict(pid=1,creation_time=20,resident_bundle_load_count=1)]
    assert sum(cumulative_loads(rows).values())==3
    a={('R0',c,t) for c in range(240) for t in ('O0','O1')}
    challenge={(r,c,t) for r in ('R0','R1','R5','R5_CUES','R7','R0_FULL_RMS') for c in range(44) for t in ('O0','O1')}
    full={(r,c,t) for r in ('R0','R1','R5','R5_CUES','R7','R0_FULL_RMS') for c in range(240) for t in ('O0','O1')}
    assert len(challenge)==528 and len(a-challenge)==392 and len(a|challenge)==920 and len(full-(a|challenge))==1960
    row=dict(job_key='k',pid=1,creation_time=1,started_utc='now',recipe_id='R0',case_id='c',stream='O0',status='COMPLETE',full_engine_wall_sec=5.,full_process_cpu_sec=8.,initial_or_changed_recipe_model_load_sec=2.)
    assert len({physical(row),physical(dict(row))})==1 and aggregate([row])['inclusive_session_wall_sec']['total']==5
    assert len({physical(row),physical(row|{'pid':2})})==2
    try:validate_epoch_receipt(dict(status='STARTED',identity=dict(execution_digest='foreign')),'current')
    except ValueError:pass
    else:raise AssertionError('Foreign attempt epoch admitted')
    return dict(status='PASS',fixtures=['cumulative loads deduplicate scenes and distinguish reused PID creation time','full/challenge/R0-extension union arithmetic','attempt/run receipt copies are one physical execution','distinct physical worker attempts remain distinct','inclusive wall not inflated by nested load','foreign attempt epoch rejected'],neural_models_started=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,default=REPORT);p.add_argument('--epoch',default='epoch2');p.add_argument('--test',action='store_true')
    args=p.parse_args();print(json.dumps(fixtures() if args.test else run(args),indent=2))
