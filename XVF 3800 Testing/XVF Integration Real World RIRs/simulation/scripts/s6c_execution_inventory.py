"""Read-only execution accounting; see README_S6C_EXECUTION_INVENTORY.md."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import psutil

SIM=Path(__file__).resolve().parents[1]
RUN='20260910T123540Z'
REPORT=SIM/'reports/S6C'/RUN
PAYLOAD=Path('G:/Just_Peachy_S6C')/RUN
STAGING=SIM/'staging/s6c'/RUN
MAX_METADATA_BYTES=64*2**20


def utc():return datetime.now(timezone.utc).isoformat()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def canonical(path):return str(Path(path).resolve())
def binding(path,raw):return dict(path=canonical(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write_new(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,indent=2,allow_nan=False);handle.write('\n');handle.flush();os.fsync(handle.fileno())
    return binding(path,path.read_bytes())
def csv_new(path,rows,fields):
    with Path(path).open('x',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for row in rows:writer.writerow({k:json.dumps(row[k],sort_keys=True) if isinstance(row.get(k),(dict,list)) else row.get(k) for k in fields})
    return binding(path,Path(path).read_bytes())
def process_state(pid,created):
    if pid is None or created is None:return dict(state='UNAVAILABLE',alive=None)
    try:
        actual=psutil.Process(int(pid)).create_time()
        return dict(state='ALIVE_SAME_IDENTITY' if abs(actual-float(created))<.001 else 'CLOSED_PID_REUSED',alive=abs(actual-float(created))<.001)
    except psutil.NoSuchProcess:return dict(state='CLOSED_NO_SUCH_PROCESS',alive=False)
    except psutil.Error as exc:return dict(state='INSPECTION_UNAVAILABLE',alive=None,error=type(exc).__name__)
def walk_bindings(value):
    if isinstance(value,dict):
        if isinstance(value.get('path'),str) and re.fullmatch('[0-9a-f]{64}',str(value.get('sha256',''))):
            item={k:value[k] for k in ('path','sha256','bytes') if k in value}
            nested=value.get('binding')
            if 'bytes' not in item and isinstance(nested,dict) and nested.get('path')==item['path'] and nested.get('sha256')==item['sha256'] and 'bytes' in nested:item['bytes']=nested['bytes']
            yield item
        else:
            for child in value.values():yield from walk_bindings(child)
    elif isinstance(value,list):
        for child in value:yield from walk_bindings(child)


class MetadataReader:
    """One bounded read per path; exact consumed bytes remain in this snapshot."""
    def __init__(self,output):self.output=Path(output);self.cache={};self.sources=[];self.failures=[]
    def read(self,path,expected=None):
        path=Path(path).resolve();key=str(path)
        if key not in self.cache:
            last=None
            for attempt in range(21):
                raw=None
                try:
                    before=path.stat()
                    if before.st_size>MAX_METADATA_BYTES:raise ValueError('Metadata exceeds explicit64MiB read limit')
                    raw=path.read_bytes();after=path.stat()
                    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise RuntimeError('Metadata changed during read')
                    value=json.loads(raw.decode('utf-8-sig'));b=binding(path,raw)
                    target=self.output/'metadata_snapshots'/(b['sha256']+'.json');target.parent.mkdir(exist_ok=True)
                    if not target.exists():target.write_bytes(raw)
                    preserved=binding(target,raw);self.sources.append(dict(source=b,preserved=preserved,read_utc=utc()))
                    self.cache[key]=(value,b);break
                except (PermissionError,json.JSONDecodeError,UnicodeDecodeError,RuntimeError) as exc:
                    last=exc
                    if attempt==20:
                        if raw is not None:
                            b=binding(path,raw);target=self.output/'rejected_metadata'/(b['sha256']+'.bin');target.parent.mkdir(exist_ok=True)
                            if not target.exists():target.write_bytes(raw)
                            self.failures.append(dict(source=b,preserved=binding(target,raw),error=repr(exc)))
                        raise
                    time.sleep(.05)
            else:raise last
        value,b=self.cache[key]
        if expected and (b['sha256']!=expected['sha256'] or ('bytes' in expected and b['bytes']!=expected['bytes']) or canonical(expected['path'])!=key):raise ValueError('Metadata source binding mismatch: '+key)
        return value,b


class DeclaredBindings:
    def __init__(self):self.rows={};self.conflicts=[]
    def add(self,value,source,role):
        for item in walk_bindings(value):
            key=(canonical(item['path']),item['sha256'])
            if 'bytes' in item and (not isinstance(item['bytes'],int) or item['bytes']<0):raise ValueError('Invalid declared byte count')
            old=self.rows.get(key)
            if old and old['binding'].get('bytes')!=item.get('bytes'):raise ValueError('Conflicting bytes for identical payload binding')
            if old is None:self.rows[key]=dict(binding=item,roles=set(),sources={})
            row=self.rows[key];row['roles'].add(role);row['sources'][source['sha256']]=source
    def export(self):
        return [dict(binding=r['binding'],roles=sorted(r['roles']),source_receipts=list(r['sources'].values()),verification='DECLARED_BY_EXACT_METADATA_NOT_PAYLOAD_REHASHED') for _,r in sorted(self.rows.items())]


def attempt_key(row):
    for field in ('pid','creation_time','started_utc','job_key'):
        if row.get(field) is None:raise ValueError('Native attempt lacks exact physical identity: '+field)
    return digest([row['pid'],row['creation_time'],row['started_utc'],row['job_key']])
def validate_native(row,specs):
    if row.get('status') not in ('STARTED','RUNNING','FAILED','COMPLETE'):raise ValueError('Unknown native receipt status')
    identity=row['identity'];epoch=identity['execution_digest']
    if epoch not in specs or digest(identity)!=row['job_key']:raise ValueError('Foreign epoch or invalid job identity')
    if row['execution_mode'] not in ('NEW_NATIVE_INFERENCE','PACED_NATIVE'):raise ValueError('Not an actual native receipt route')
    if row['status']=='COMPLETE' and not row.get('session_dir'):raise ValueError('Complete native receipt has no actual session')
    attempt_key(row)
    return specs[epoch]
def merge_attempt(group,row,source):
    if attempt_key(group['row'])!=attempt_key(row):raise ValueError('Different physical attempts cannot merge')
    old=group['row']
    if old.get('session_dir') and row.get('session_dir') and canonical(old['session_dir'])!=canonical(row['session_dir']):raise ValueError('Conflicting sessions for one physical attempt')
    for key in ('candidate_id','case_id','recipe_id','asr_tap','identity_tap','identity'):
        if old[key]!=row[key]:raise ValueError('Conflicting paired native receipt metadata')
    if old['status']=='COMPLETE' and row['status']=='COMPLETE':
        for key in ('events','evidence','vectors','actual_counts','worker_model_bundle_loads'):
            if old.get(key)!=row.get(key):raise ValueError('Conflicting completed physical evidence')
    rank={'STARTED':0,'RUNNING':1,'FAILED':2,'COMPLETE':3}
    if rank[row['status']]>rank[old['status']]:group['row']=row
    group['sources'][source['sha256']+source['path']]=source
def inference_key(row):
    identity=row['identity'];profile=identity['profile']
    state_driven=profile['embedding']['cadence_policy']=='uncertainty' or profile['embedding']['cadence_cues_enabled'] or profile['xvf']['mode'] in ('endpoint_only','both')
    settings=profile if state_driven else {k:profile[k] for k in ('input','asr','segmentation','embedding','punctuation','runtime')}
    return digest(dict(execution_digest=identity['execution_digest'],settings=settings,asr=identity['asr_audio'],speaker=identity['identity_audio'],
        state_driven=state_driven,telemetry=identity.get('telemetry') if state_driven else None,gallery=identity.get('gallery') if state_driven else None,realtime=identity['realtime']))
def payloads(row):
    return {k:row[k] for k in ('evidence','vectors','events','summary','journals','finalization','display_events','summary_binding','journal') if k in row}
def count_bytes(value):
    rows={(canonical(b['path']),b['sha256']):b.get('bytes') for b in walk_bindings(value)}
    return sum(v for v in rows.values() if v is not None),sum(v is None for v in rows.values())
def normalize_native(group,specs,worker_observations):
    row=group['row'];spec=specs[row['identity']['execution_digest']];session=row.get('session_dir')
    status_source=None
    if not session:
        for observation,b in worker_observations:
            if observation.get('job_key')==row['job_key'] and observation.get('started_utc')==row['started_utc'] and observation.get('pid')==row['pid'] and observation.get('creation_time')==row['creation_time'] and observation.get('session_dir'):
                session=observation['session_dir'];status_source=b;break
    outputs=payloads(row);size,missing=count_bytes(outputs);pstate=process_state(row['pid'],row['creation_time'])
    counter=row.get('worker_model_bundle_loads')
    if counter is not None and (not isinstance(counter,int) or counter<0):raise ValueError('Invalid cumulative model load count')
    loaded=row.get('gallery_load_receipts',[]);gallery=row['identity'].get('gallery')
    return dict(physical_id=attempt_key(row),branch='S6C_EPOCH_NATIVE',status=row['status'],epoch=spec['epoch'],candidate_id=row['candidate_id'],profile_id=row['identity']['profile']['profile_id'],
        recipe_id=row['recipe_id'],case_id=row['case_id'],asr_tap=row['asr_tap'],identity_tap=row['identity_tap'],execution_mode=row['execution_mode'],
        job_key=row['job_key'],inference_dependency_key=inference_key(row),pid=row['pid'],creation_time=row['creation_time'],process_state=pstate,
        session_dir=session,session_evidence='COMPLETE_NATIVE_RECEIPT' if row['status']=='COMPLETE' else 'OBSERVED_WORKER_STATUS' if status_source else 'NOT_RECORDED',worker_status_binding=status_source,
        started_utc=row['started_utc'],finished_utc=row.get('finished_utc'),elapsed_sec=row.get('elapsed_sec'),native_elapsed_sec=row.get('native_elapsed_sec'),
        process_cpu_sec=row.get('process_cpu_sec'),audio_duration_sec=row.get('audio_duration_sec'),rss_end_bytes=row.get('rss_end_bytes'),
        actual_counts=row.get('actual_counts'),worker_model_bundle_loads=counter,bundle_admission_sec=row.get('bundle_admission_sec'),
        gallery_manifest=gallery,gallery_cache_hit=row.get('gallery_cache_hit'),gallery_admission_sec=row.get('gallery_admission_sec'),gallery_load_receipts=loaded,
        real_gallery_load_observed=bool(gallery) and row.get('gallery_cache_hit') is False and bool(loaded),
        source_asr=row['identity']['asr_audio'],source_identity=row['identity']['identity_audio'],telemetry=row['identity'].get('telemetry'),
        execution_digest=row['identity']['execution_digest'],epoch_manifest=spec['_binding'],profile_sha256=digest(row['identity']['profile']),
        output_bindings=outputs,declared_output_bytes=size if outputs else None,bindings_missing_byte_counts=missing,
        receipt_bindings=list(group['sources'].values()),error=row.get('error'),hardware_invocations=row.get('hardware_invocations'),
        oracle_like=row.get('reference_truth_sent_to_predictor'),cue_condition=row.get('cue_condition'),gallery_condition=row['identity'].get('gallery_condition'),enrollment_tier=row['identity'].get('enrollment_tier'))


def summarize(rows):
    events=Counter();loads={};gallery=set()
    for row in rows:
        if row.get('actual_counts') is not None:
            if any(type(v) is not int or v<0 for v in row['actual_counts'].values()):raise ValueError('Invalid operation-event counter')
            events.update(row['actual_counts'])
        if row.get('worker_model_bundle_loads') is not None:
            if type(row['worker_model_bundle_loads']) is not int or row['worker_model_bundle_loads']<0:raise ValueError('Invalid cumulative resident counter')
            key=(row['pid'],row['creation_time']);loads[key]=max(loads.get(key,0),row['worker_model_bundle_loads'])
        if row.get('real_gallery_load_observed'):gallery.add((row['pid'],row['creation_time'],row['gallery_manifest']['sha256']))
    def total(field):
        values=[r[field] for r in rows if r.get(field) is not None]
        if any(not isinstance(v,(float,int)) or not math.isfinite(v) or v<0 for v in values):raise ValueError('Invalid numeric accounting field '+field)
        return dict(total=sum(values) if values else None,observed_rows=len(values),unavailable_rows=len(rows)-len(values))
    return dict(physical_attempts=len(rows),complete=sum(r['status']=='COMPLETE' for r in rows),status_counts=dict(Counter(r['status'] for r in rows)),
        confirmed_session_paths=len({canonical(r['session_dir']) for r in rows if r.get('session_dir')}),
        attempts_without_session_path=sum(not r.get('session_dir') for r in rows),
        unique_job_keys=len({r['job_key'] for r in rows if r.get('job_key')}),unique_conservative_inference_dependencies=len({r['inference_dependency_key'] for r in rows if r.get('inference_dependency_key')}),
        observed_event_counts=dict(events),event_counts_unavailable_rows=sum(r.get('actual_counts') is None for r in rows),
        cumulative_worker_bundle_loads_observed=sum(loads.values()),workers_with_load_counter=len(loads),observed_distinct_worker_gallery_loads=len(gallery),
        elapsed_sec=total('elapsed_sec'),native_elapsed_sec=total('native_elapsed_sec'),process_cpu_sec=total('process_cpu_sec'),audio_duration_sec=total('audio_duration_sec'),
        nested_bundle_admission_sec=total('bundle_admission_sec'),nested_gallery_admission_sec=total('gallery_admission_sec'),
        declared_output_bytes_before_cross_row_dedup=total('declared_output_bytes'))


def prediction_class(path,index):
    if 'fixture' in path.name.lower() or any('SYNTHETIC' in str(r.get('error','')) for r in index.get('rows',[])):return 'SYNTHETIC_FIXTURE_EXCLUDED'
    return 'DECLARED_PREDICTION_INDEX'
def prediction_route(row):
    parts=Path(row.get('result',{}).get('path','')).parts
    if 'policy_predictions' in parts:return 'POLICY_ONLY_FROM_S6C_NATIVE_EVIDENCE'
    if 'native_predictions' in parts:return 'NATIVE_OBSERVATION_PROJECTION_NO_NEW_INFERENCE'
    if row.get('recipe_id')=='N00' and 'predictions' in parts:return 'POLICY_ONLY_FROM_HISTORICAL_S6B_FEATURES'
    return 'UNCLASSIFIED_INDEXED_OUTPUT'


def reference_coverage(references,physical_rows):
    observed={(canonical(b['path']),b['sha256']) for row in physical_rows for b in row['receipt_bindings']}
    unseen=sorted(references-observed)
    return dict(unique_reference_bindings=len(references),present_in_receipt_snapshot=len(references&observed),
        not_in_receipt_snapshot=[dict(path=p,sha256=h) for p,h in unseen],
        scope='Index reads follow receipt enumeration. Missing members may have completed later in the read interval or be outside the enumerated namespace; they are not silently added to physical counts or called failed.')


def closure_scope(owners,orphan_sessions=(),unaccounted_references=()):
    flags=[]
    alive=sum(o['process_state']['alive'] is True for o in owners);unknown=sum(o['process_state']['alive'] is None for o in owners)
    if unknown:flags.append(dict(kind='PROCESS_CLOSURE_UNVERIFIED',owner_observations=unknown))
    if orphan_sessions:flags.append(dict(kind='UNMATCHED_NATIVE_SESSION_DIRECTORIES',count=len(orphan_sessions)))
    if unaccounted_references:flags.append(dict(kind='NATIVE_INDEX_REFERENCES_OUTSIDE_RECEIPT_ENUMERATION',count=len(unaccounted_references)))
    return dict(status='ACTIVE' if alive else 'CLOSURE_UNVERIFIED' if flags else 'CLOSED',alive_owner_observations=alive,
        unavailable_owner_observations=unknown,flags=flags,scope='All observed owner/process branches; closed is only an observation-window state, never whole-study completion.')


def owner_identity_summary(owners):
    groups=defaultdict(list)
    for owner in owners:groups[owner['pid'],owner['creation_time']].append(owner)
    rows=[]
    for (pid,created),items in groups.items():
        states=[x['process_state']['alive'] for x in items]
        value=True if any(x is True for x in states) else None if any(x is None for x in states) else False
        rows.append(dict(pid=pid,creation_time=created,branches=sorted({x['branch'] for x in items}),observations=len(items),
            process_state=dict(alive=value,state='ANY_ACTIVE_DURING_OBSERVATION' if value else 'UNVERIFIED_DURING_OBSERVATION' if value is None else 'ALL_OBSERVED_CLOSED'),
            binding_scope='Exact sources reside in the bound physical, worker, invocation and auxiliary tables; this compact identity summary does not duplicate every receipt.'))
    return rows


def collect(args):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',args.version):raise ValueError('Simple new snapshot version required')
    out=REPORT/'execution_inventory'/args.version;out.mkdir(parents=True,exist_ok=False)
    source_snapshots=[]
    for path in (Path(__file__),Path(__file__).with_name('README_S6C_EXECUTION_INVENTORY.md')):
        raw=path.read_bytes();target=out/'source_snapshots'/path.name;target.parent.mkdir(exist_ok=True);target.write_bytes(raw)
        source_snapshots.append(dict(source=binding(path,raw),snapshot=binding(target,raw)))
    reader=MetadataReader(out);declared=DeclaredBindings();issues=[];started=utc()
    def read(path,expected=None):
        value,b=reader.read(path,expected);return value,b
    def safe_read(path,expected=None):
        try:return read(path,expected)
        except (OSError,ValueError,RuntimeError) as exc:issues.append(dict(path=str(path),error=repr(exc)));return None,None
    specs={};epochs=[]
    for path in sorted(REPORT.glob('EPOCH*_EXECUTION_MANIFEST.json')):
        spec,b=read(path)
        if spec['execution_digest']!=digest({k:spec[k] for k in ('execution_files','assets','versions','state_policy')}):raise ValueError('Epoch source graph digest invalid')
        if spec['execution_digest'] in specs:raise ValueError('Ambiguous epoch digest')
        spec['_binding']=b;specs[spec['execution_digest']]=spec;epochs.append(dict(epoch=spec['epoch'],manifest=b,execution_digest=spec['execution_digest']))
        declared.add(spec['execution_files'],b,'EPOCH_CODE');declared.add(spec['assets'],b,'MODEL_ASSET');declared.add(spec['input_index'],b,'HISTORICAL_INPUT_AUTHORITY')
    receipt_paths=[];session_paths=set();paced_manifests=[]
    enumeration_start=utc()
    for base,dirs,files in os.walk(PAYLOAD):
        relative=Path(base).relative_to(PAYLOAD)
        if not relative.parts:dirs[:]=[d for d in dirs if d not in ('enrollment','source_inventory')]
        dirs[:]=[d for d in dirs if d not in ('predictions','native_predictions','policy_predictions','__pycache__','metadata_snapshots')]
        if 'session_summary.json' in files or 'session_finalization_v3.json' in files:session_paths.add(canonical(base))
        for name in ('run_receipt.json','attempt_receipt.json'):
            if name in files:receipt_paths.append(Path(base)/name)
        if 'MANIFEST.json' in files and 'paced_controls' in relative.parts:paced_manifests.append(Path(base)/'MANIFEST.json')
    enumeration_end=utc()
    faults=[]
    for path in sorted((REPORT/'diagnosed_attempts').rglob('*.json')):
        value,b=safe_read(path)
        if value is None:continue
        faults.append(dict(binding=b,status=value.get('status'),cause=value.get('cause',value.get('error')),scope='Preserved diagnosis; not itself a native execution'))
        for item in walk_bindings(value):
            if Path(item['path']).name in ('run_receipt.json','attempt_receipt.json'):
                _,_=safe_read(item['path'],item);receipt_paths.append(Path(item['path']))
    workers=[];observations=[]
    for path in sorted(REPORT.glob('epoch*/workers/*.json')):
        row,b=safe_read(path)
        if row is None:continue
        observations.append((row,b));workers.append(dict(source=b,pid=row.get('pid'),creation_time=row.get('creation_time'),recorded_status=row.get('status'),
            phase=row.get('phase'),session_dir=row.get('session_dir'),job_key=row.get('job_key'),process_state=process_state(row.get('pid'),row.get('creation_time'))))
    groups={};rejected=[]
    for path in sorted(set(receipt_paths)):
        row,b=safe_read(path)
        if row is None:continue
        try:
            spec=validate_native(row,specs)
            if path.name=='run_receipt.json' and row['status']!='COMPLETE':raise ValueError('Noncomplete immutable run receipt')
            key=attempt_key(row)
            if key not in groups:groups[key]=dict(row=row,sources={})
            merge_attempt(groups[key],row,b)
            declared.add(payloads(row),b,'NATIVE_OUTPUT');declared.add(row['identity'],b,'NATIVE_INPUT_OR_GALLERY')
        except (KeyError,ValueError) as exc:rejected.append(dict(source=b,error=repr(exc)))
    rows=[normalize_native(group,specs,observations) for group in groups.values()]
    bysession={}
    for row in rows:
        if row['session_dir']:
            key=canonical(row['session_dir'])
            if key in bysession and bysession[key]!=row['physical_id']:raise ValueError('One native session assigned to multiple physical attempts')
            bysession[key]=row['physical_id']
    invocations=[];native_refs=Counter();native_ref_bindings=set()
    for path in sorted(REPORT.glob('epoch*/invocations/*/owner.json')):
        owner,b=safe_read(path)
        if owner is None:continue
        if owner.get('execution_manifest'):safe_read(owner['execution_manifest']['path'],owner['execution_manifest'])
        folder=path.parent;completion,cb=safe_read(folder/'completion.json') if (folder/'completion.json').exists() else (None,None)
        records,rb=(completion,cb) if completion else safe_read(folder/'rows.json') if (folder/'rows.json').exists() else ({'rows':[]},None)
        closure,kb=safe_read(folder/'closure.json') if (folder/'closure.json').exists() else (None,None)
        selected=records.get('rows',[]) if records else [];counts=Counter(x.get('status','UNSPECIFIED') for x in selected);native_refs.update(counts)
        for row in selected:
            if row.get('receipt'):
                native_ref_bindings.add((canonical(row['receipt']['path']),row['receipt']['sha256']));declared.add(row['receipt'],rb or b,'NATIVE_INDEX_REFERENCE')
        invocations.append(dict(owner=b,completion=cb,rows_source=rb,closure=kb,pid=owner['pid'],creation_time=owner['creation_time'],
            process_state=process_state(owner['pid'],owner['creation_time']),requested=(completion or {}).get('requested'),
            reported_completed=(completion or {}).get('completed'),reported_status=(completion or {}).get('status'),
            recorded_row_references=len(selected),row_status_counts=dict(counts),worker_pool_joined=(completion or {}).get('worker_pool_joined'),
            stage=(completion or {}).get('stage'),jobs=owner.get('jobs'),error=(completion or {}).get('error')))
    prediction_indexes=[];prediction_outputs={};reference_count=0;synthetic=[]
    for path in sorted(REPORT.glob('epoch*/*PREDICTION_INDEX.json')):
        index,b=safe_read(path)
        if index is None:continue
        classification=prediction_class(path,index)
        if classification=='SYNTHETIC_FIXTURE_EXCLUDED':synthetic.append(dict(binding=b,status=index.get('status'),row_count=len(index.get('rows',[])),classification=classification));continue
        keys=[];routes=Counter();statuses=Counter()
        for row in index.get('rows',[]):
            keys.append((row.get('candidate_id'),row.get('case_id'),row.get('stream'),row.get('identity_tap')));statuses[row.get('status','UNSPECIFIED')]+=1
            if row.get('result'):
                result=row['result'];key=(canonical(result['path']),result['sha256']);route=prediction_route(row);routes[route]+=1;reference_count+=1
                old=prediction_outputs.get(key)
                if old and old['route']!=route:raise ValueError('Conflicting indexed output route')
                prediction_outputs[key]=dict(binding=result,route=route);declared.add(result,b,'PREDICTION_OUTPUT_NOT_NEW_INFERENCE')
        if len(keys)!=len(set(keys)):issues.append(dict(path=str(path),error='Duplicate logical rows inside one prediction index'))
        prediction_indexes.append(dict(binding=b,status=index.get('status'),requested=index.get('requested'),completed=index.get('completed'),
            rows=len(index.get('rows',[])),row_status_counts=dict(statuses),output_reference_routes=dict(routes),source_indices=index.get('source_indices'),
            scope='Index/materialization references only; these are not physical model executions or an inventory of every policy replay invocation'))
    auxiliary=collect_auxiliary(reader,declared,issues,rows,bysession,paced_manifests)
    orphan_sessions=sorted(session_paths-set(bysession))
    repeated=defaultdict(list)
    for row in rows:
        if row.get('job_key'):repeated[row['job_key']].append(row['physical_id'])
    grouped=[]
    for key in sorted({(r['branch'],r.get('epoch'),r.get('recipe_id'),r.get('candidate_id'),r.get('asr_tap'),r.get('identity_tap'),r['status']) for r in rows},key=str):
        subset=[r for r in rows if (r['branch'],r.get('epoch'),r.get('recipe_id'),r.get('candidate_id'),r.get('asr_tap'),r.get('identity_tap'),r['status'])==key]
        s=summarize(subset);grouped.append(dict(zip(('branch','epoch','recipe_id','candidate_id','asr_tap','identity_tap','status'),key))|dict(physical_attempts=len(subset),confirmed_sessions=s['confirmed_session_paths'],audio_sec=s['audio_duration_sec']['total'],audio_duration_observed=s['audio_duration_sec']['observed_rows'],embedding_events=s['observed_event_counts'].get('research_embedding'),segmentation_events=s['observed_event_counts'].get('research_segmentation')))
    table=csv_new(out/'PHYSICAL_EXECUTIONS.csv',rows,['physical_id','branch','status','epoch','candidate_id','profile_id','recipe_id','case_id','asr_tap','identity_tap','execution_mode','job_key','inference_dependency_key','pid','creation_time','process_state','session_dir','session_evidence','started_utc','finished_utc','elapsed_sec','native_elapsed_sec','process_cpu_sec','audio_duration_sec','rss_end_bytes','worker_model_bundle_loads','bundle_admission_sec','gallery_cache_hit','gallery_admission_sec','real_gallery_load_observed','actual_counts','declared_output_bytes','error'])
    compact=csv_new(out/'EXECUTION_SUMMARY.csv',grouped,['branch','epoch','recipe_id','candidate_id','asr_tap','identity_tap','status','physical_attempts','confirmed_sessions','audio_sec','audio_duration_observed','embedding_events','segmentation_events'])
    rows_binding=write_new(out/'PHYSICAL_EXECUTIONS.json',rows);declared_rows=declared.export();catalog=write_new(out/'DECLARED_ARTIFACT_BINDINGS.json',declared_rows)
    metadata=write_new(out/'METADATA_SOURCES.json',dict(read_sources=reader.sources,read_failures=reader.failures))
    branch_summaries={branch:summarize([r for r in rows if r['branch']==branch]) for branch in sorted({r['branch'] for r in rows})}
    all_worker_loads={}
    for row in rows:
        if row.get('worker_model_bundle_loads') is not None:
            k=f"{row['pid']}:{row['creation_time']}";all_worker_loads[k]=max(all_worker_loads.get(k,0),row['worker_model_bundle_loads'])
    bytes_by_role={}
    for role in sorted({role for row in declared_rows for role in row['roles']}):
        selected=[r['binding'] for r in declared_rows if role in r['roles']]
        bytes_by_role[role]=dict(unique_path_hash_bindings=len(selected),declared_bytes=sum(r.get('bytes',0) for r in selected),missing_byte_counts=sum('bytes' not in r for r in selected))
    owners=[dict(branch='EPOCH_WORKER',pid=w['pid'],creation_time=w['creation_time'],process_state=w['process_state'],source=w['source']) for w in workers]
    owners.extend(dict(branch='EPOCH_COORDINATOR',pid=w['pid'],creation_time=w['creation_time'],process_state=w['process_state'],source=w['owner']) for w in invocations)
    owners.extend(dict(branch=r['branch'],pid=r['pid'],creation_time=r['creation_time'],process_state=r['process_state'],sources=r['receipt_bindings']) for r in rows)
    owners.extend(auxiliary['owner_observations'])
    owners=owner_identity_summary(owners)
    reference_accounting=reference_coverage(native_ref_bindings,rows);closure=closure_scope(owners,orphan_sessions,reference_accounting['not_in_receipt_snapshot'])
    status={'ACTIVE':'PARTIAL_ACTIVE_STUDY_SNAPSHOT','CLOSURE_UNVERIFIED':'CLOSURE_UNVERIFIED_SNAPSHOT','CLOSED':'CLOSED_AT_OBSERVATION_NOT_STUDY_COMPLETION'}[closure['status']]
    report=dict(schema='s6c-execution-inventory.v1',status=status,process_closure=closure,owner_identity_summary=owners,
        audit_status='PASS_WITH_SCOPE_LIMITS' if not issues and not rejected and not closure['flags'] else 'INCOMPLETE_WITH_FLAGS',observation_started_utc=started,observation_finished_utc=utc(),
        enumeration_interval=dict(started_utc=enumeration_start,finished_utc=enumeration_end),epochs=epochs,branch_summaries=branch_summaries,
        complete_native_sessions_observed=len({canonical(r['session_dir']) for r in rows if r['status']=='COMPLETE' and r.get('session_dir')}),
        unique_physical_attempts_observed=len(rows),native_attempts_without_session_evidence=sum(not r.get('session_dir') for r in rows),
        unfinished_attempts=[dict(physical_id=r['physical_id'],status=r['status'],process_state=r['process_state'],session_dir=r.get('session_dir'),receipt_bindings=r['receipt_bindings']) for r in rows if r['status'] in ('STARTED','RUNNING')],
        repeated_exact_job_identities=[dict(job_key=k,physical_attempts=v) for k,v in repeated.items() if len(v)>1],
        observed_worker_bundle_load_maxima=all_worker_loads,workers=workers,native_invocations=invocations,
        worker_bundle_counter_scope='Epoch and future long native receipt counters only; prefix bundle1 and enrollment SpeakerModels1 are separately recorded auxiliary namespaces, not silently omitted or added as identical classes.',
        native_index_row_references=dict(native_refs),unique_native_receipt_references=len(native_ref_bindings),
        native_index_reference_coverage=reference_accounting,
        worker_observations_outside_receipt_enumeration=[dict(source=b,pid=w.get('pid'),creation_time=w.get('creation_time'),job_key=w.get('job_key'),session_dir=w.get('session_dir'),status=w.get('status'))
            for w,b in observations if w.get('started_utc') and w.get('job_key') and attempt_key(w) not in groups],
        prediction_indexes=prediction_indexes,prediction_index_output_references=reference_count,unique_indexed_prediction_outputs=len(prediction_outputs),
        repeated_prediction_index_references=reference_count-len(prediction_outputs),unique_prediction_outputs_by_route=dict(Counter(r['route'] for r in prediction_outputs.values())),
        synthetic_fixture_indexes_excluded=synthetic,auxiliary=auxiliary,unmatched_session_directories=orphan_sessions,
        preserved_fault_resolvers=faults,rejected_native_receipts=rejected,issues=issues,
        declared_bytes_by_role=bytes_by_role,byte_scope='Deduplicated within each role by path/hash; roles can overlap and must not be added. These are declared representation sizes, not a full current disk-usage measurement.',
        outputs=dict(physical_csv=table,compact_csv=compact,physical_json=rows_binding,declared_artifact_bindings=catalog,metadata_sources=metadata),
        code=binding(__file__,Path(__file__).read_bytes()),readme=binding(Path(__file__).with_name('README_S6C_EXECUTION_INVENTORY.md'),Path(__file__).with_name('README_S6C_EXECUTION_INVENTORY.md').read_bytes()),source_snapshots=source_snapshots,
        limits=['A bounded read interval is not a transaction: new receipts may appear after enumeration; current absent completion is not zero or a failed model.',
            'Attempt/session identity counts physical executions; exact job keys and conservative inference groups are dependency counts, never substituted for physical executions.',
            'The conservative inference key retains the exact execution epoch and all state-driven profile/cue/gallery dependencies. It is descriptive grouping, not authorization for a new cache substitution.',
            'Counters are recorded API events, not hidden neural forward-step counts. Nested model/gallery admission and concurrent lane timings must not be added to elapsed runtime.',
            'Per-worker cumulative model load counters use a maximum across observed receipts. Loads before missing/failed receipts can remain unobserved. Gallery load counters count distinct worker/manifest admissions, not repeated loaded_elapsed_sec provenance.',
            'Closed receipt hashes and bytes bind payload transitively; this collector never opens audio, vectors, weights, prediction payloads or full event logs and does not replace their existing validators.',
            'All consumed metadata bytes are preserved by hash. Mutable source paths can later change; use METADATA_SOURCES exact snapshot resolver.',
            'Prediction indexes can repeat references or describe separate policy materializations; neither means a new model execution. Synthetic fixture indexes are explicitly excluded.',
            'Unknown process inspection stays unavailable. No observer resource samples or desktop result qualify CM5.',
            'This inventory does not declare the whole S6C research/accuracy/paced/HIL requirement complete. Future long and paced branches remain unobserved until their actual receipts exist.'])
    for saved in source_snapshots:
        if binding(saved['source']['path'],Path(saved['source']['path']).read_bytes())!=saved['source']:raise ValueError('Collector source changed during snapshot')
    final=write_new(out/'EXECUTION_INVENTORY.json',report)
    return dict(status=report['status'],audit_status=report['audit_status'],snapshot=final,physical_rows=len(rows),complete_sessions=report['complete_native_sessions_observed'],issues=len(issues)+len(rejected),accounting_boundary_flags=closure['flags'],metadata_bytes=sum(s['source']['bytes'] for s in reader.sources),model_calls=0)


def collect_auxiliary(reader,declared,issues,rows,bysession,paced_manifests):
    result={'owner_observations':[]}
    enrollment=REPORT/'enrollment/ENROLLMENT_COMPLETION.json'
    if enrollment.exists():
        value,b=reader.read(enrollment);plan,pb=reader.read(value['plan']['path'],value['plan']);declared.add(plan,pb,'ENROLLMENT_SOURCE_MODEL_CODE');declared.add(value['outputs'],b,'ENROLLMENT_OUTPUT')
        result['enrollment']=dict(status=value['status'],receipt=b,plan=pb,owner=value['owner'],process_state=process_state(value['owner']['pid'],value['owner']['creation_time']),
            actual_embedding_calls=value['actual_embedding_calls_this_process'],cache_hits=value['cache_hits_this_process'],model_loads=value['model_loads_this_process'],
            C_window_queries=value['C_window_queries'],native_templates=value['native_templates'],Q_embedding_calls=value['Q_embedding_calls'],
            interpretation='Separate actual E/C embedding process; cache hits are not new embeddings; no Q inference or full-pipeline native session is claimed.')
        result['owner_observations'].append(dict(branch='ENROLLMENT',pid=value['owner']['pid'],creation_time=value['owner']['creation_time'],process_state=result['enrollment']['process_state'],source=b))
    else:result['enrollment']=dict(status='NOT_OBSERVED')
    prefix=[]
    for path in sorted((REPORT/'native_prefix').glob('*/STARTED.json')):
        start,sb=reader.read(path);owner=start['owner']
        result['owner_observations'].append(dict(branch='NATIVE_PREFIX_OWNER',pid=owner['pid'],creation_time=owner['creation_time'],process_state=process_state(owner['pid'],owner['creation_time']),source=sb))
    for path in sorted((REPORT/'native_prefix').glob('*/RESULT.json')):
        value,b=reader.read(path)
        if value.get('schema')!='s6c_actual_native_prefix_result.v1':continue
        if value.get('status')!='PASS':raise ValueError('Native-prefix result does not claim a completed proof')
        manifest,mb=reader.read(value['manifest']['path'],value['manifest']);declared.add(manifest,mb,'PREFIX_INPUT_CODE');owner=value['owner']
        for item in value['run_receipts']:
            row,rb=reader.read(item['path'],item);session=canonical(Path(row['summary']['path']).parent);physical=digest(['native_prefix',session,owner['pid'],owner['creation_time']])
            if row.get('status')!='COMPLETE':raise ValueError('Prefix receipt not complete')
            if session in bysession:raise ValueError('Prefix session duplicated in other native branch')
            bysession[session]=physical;declared.add(payloads(row)|{'closure':row['closure']},rb,'PREFIX_NATIVE_OUTPUT')
            size,missing=count_bytes(payloads(row)|{'closure':row['closure']})
            rows.append(dict(physical_id=physical,branch='ACTUAL_NATIVE_PREFIX_DIAGNOSTIC',status=row['status'],epoch=Path(manifest['epoch']['path']).stem,
                candidate_id=manifest['candidate_id'],profile_id=manifest['profile']['profile_id'],recipe_id='PREFIX_DIAGNOSTIC',case_id=manifest['case_id'],asr_tap=manifest['profile']['input']['asr_tap'],identity_tap=manifest['profile']['input']['identity_tap'],
                execution_mode='ACTUAL_NATIVE_CHANGED_FUTURE_DIAGNOSTIC',job_key=None,inference_dependency_key=None,pid=owner['pid'],creation_time=owner['creation_time'],process_state=process_state(owner['pid'],owner['creation_time']),
                session_dir=session,session_evidence='BOUND_NATIVE_PREFIX_RECEIPT',started_utc=None,finished_utc=None,elapsed_sec=None,native_elapsed_sec=row['native_elapsed_sec'],process_cpu_sec=row['process_cpu_sec'],audio_duration_sec=manifest['duration_sec'],
                worker_model_bundle_loads=None,bundle_admission_sec=None,gallery_manifest=None,gallery_cache_hit=None,gallery_admission_sec=None,real_gallery_load_observed=False,
                actual_counts={'research_embedding':row['short_embeddings']+row['mature_embeddings'],'research_segmentation':row['segmentation_calls'],'research_asr_observation':row['raw_asr_observations']},
                output_bindings=payloads(row)|{'closure':row['closure']},declared_output_bytes=size,bindings_missing_byte_counts=missing,receipt_bindings=[rb],error=None))
        prefix.append(dict(result=b,manifest=mb,neural_sessions=value['neural_sessions'],model_bundle_loads=value['model_bundle_loads'],owner=owner,
            interpretation='Real original/changed-future native sessions; common-availability replay and numerical helper checks are separate model-free diagnostics.'))
    result['native_prefix']=prefix
    paced=[]
    for path in sorted(paced_manifests):
        plan,pb=reader.read(path);output=Path(plan['output_root']);counts=Counter()
        if plan.get('schema')!='s6c-historical-paced-controls.v1':issues.append(dict(path=str(path),error='Unrecognized paced manifest schema'));continue
        declared.add(plan['dependencies'],pb,'PACED_CONTROL_DEPENDENCY')
        for launch_path in sorted((output/'invocations').glob('*/LAUNCH.json')):
            launch,lb=reader.read(launch_path)
            result['owner_observations'].append(dict(branch='PACED_CONTROL_COORDINATOR',pid=launch['pid'],creation_time=launch['creation_time'],process_state=process_state(launch['pid'],launch['creation_time']),source=lb))
        for job in plan['jobs']:
            folder=output/'jobs'/job['job_id'];target=folder/'WORKER_RESULT.json'
            if not target.exists():
                if (folder/'LAUNCH.json').exists():
                    launch,lb=reader.read(folder/'LAUNCH.json')
                    if launch['job_key']!=job['job_key']:raise ValueError('Paced incomplete launch identity mismatch')
                    result['owner_observations'].append(dict(branch='PACED_CONTROL_INCOMPLETE_WORKER',pid=launch['pid'],creation_time=launch['creation_time'],process_state=process_state(launch['pid'],launch['creation_time']),source=lb))
                    counts['LAUNCHED_WITHOUT_WORKER_RESULT']+=1
                else:counts['NOT_LAUNCHED']+=1
                continue
            worker,wb=reader.read(target)
            if worker['job_key']!=job['job_key']:raise ValueError('Paced worker identity mismatch')
            session=canonical(worker['session_dir']);physical=digest(['paced',session,worker['pid'],worker['creation_time']])
            if session in bysession:raise ValueError('Paced session duplicated elsewhere')
            bysession[session]=physical;counts[worker['status']]+=1;declared.add(payloads(worker),wb,'PACED_NATIVE_OUTPUT');size,missing=count_bytes(payloads(worker))
            observer_binding=None
            if (folder/'COMPLETE.json').exists():_,observer_binding=reader.read(folder/'COMPLETE.json')
            rows.append(dict(physical_id=physical,branch='HISTORICAL_PACED_CONTROL',status=worker['status'],epoch='HISTORICAL_CONTROL',candidate_id=job['profile_id'],profile_id=job['profile_id'],recipe_id=job['recipe_id'],case_id=job['case_id'],asr_tap=job['stream'],identity_tap=job['stream'],
                execution_mode='PACED_NATIVE_HISTORICAL_UNCHANGED',job_key=job['job_key'],inference_dependency_key=None,pid=worker['pid'],creation_time=worker['creation_time'],process_state=process_state(worker['pid'],worker['creation_time']),session_dir=session,session_evidence='BOUND_PACED_WORKER_RESULT',
                started_utc=worker.get('source_started_wall_time_utc'),finished_utc=worker.get('created_utc'),elapsed_sec=worker.get('full_worker_elapsed_sec'),native_elapsed_sec=None,process_cpu_sec=worker.get('process_cpu_sec_at_end'),audio_duration_sec=worker['source_duration_sec'],
                worker_model_bundle_loads=None,bundle_admission_sec=worker.get('bundle_admission_sec'),gallery_manifest=None,gallery_cache_hit=None,gallery_admission_sec=None,real_gallery_load_observed=False,actual_counts=worker.get('event_counts'),output_bindings=payloads(worker),declared_output_bytes=size,bindings_missing_byte_counts=missing,
                receipt_bindings=[wb],observer_completion=observer_binding,error=None,model_load_scope='Original worker exposes admission time, not a cumulative bundle-count measurement.'))
        paced.append(dict(manifest=pb,requested_cells=len(plan['jobs']),observed_status_counts=dict(counts),source_minutes=plan['total_audio_sec']/60))
    result['historical_paced_controls']=paced
    long_runs=[]
    for started_path in sorted((REPORT/'long_session').glob('*/native/*/*/*/STARTED.json')):
        start,sb=reader.read(started_path);owner=start['owner'];folder=started_path.parent;profile=start['profile'];composition,cb=reader.read(start['composition']['path'],start['composition'])
        declared.add(start,sb,'LONG_NATIVE_SOURCE_CODE');declared.add(composition,cb,'LONG_NATIVE_COMPOSITION')
        physical=digest(['long_native',str(folder),owner['pid'],owner['creation_time'],start['utc']]);value=None;vb=None;status='STARTED';outputs={};session=None
        if (folder/'RESULT.json').exists():
            value,vb=reader.read(folder/'RESULT.json')
            if value.get('schema')!='s6c_continuous_paced_native.v1' or value.get('status')!='COMPLETE' or value['owner']!=owner or value['profile']!=profile or value['composition']!=start['composition']:raise ValueError('Wrong actual long native result')
            if value['live_owned_lanes'] or value['resident_sessions_created']!=1:raise ValueError('Long native session/closure scope differs')
            outputs=dict(native_artifacts=value['native_artifacts'],journals=value['native_journals'],process_samples=value['process_samples'])
            sessions={canonical(Path(b['path']).parent) for b in value['native_journals'].values()}
            if len(sessions)!=1:raise ValueError('Long native journals span different sessions')
            session=sessions.pop();status='COMPLETE'
            if session in bysession:raise ValueError('Long session duplicated elsewhere')
            bysession[session]=physical;declared.add(outputs,vb,'LONG_NATIVE_OUTPUT')
        elif (folder/'FAILURE.json').exists():
            value,vb=reader.read(folder/'FAILURE.json')
            if value.get('status')!='FAILED' or value['owner']!=owner:raise ValueError('Wrong long native failure owner/status')
            status='FAILED'
        size,missing=count_bytes(outputs)
        rows.append(dict(physical_id=physical,branch='CONTINUOUS_HOST_PACED_NATIVE',status=status,epoch=Path(composition['epoch']['path']).stem,candidate_id=profile['candidate_id'],profile_id=profile['profile']['profile_id'],recipe_id=profile['recipe_id'],case_id=None,
            asr_tap=profile['asr_tap'],identity_tap=profile['identity_tap'],execution_mode='CONTINUOUS_NATIVE_SYNTHETIC_CONCATENATION',job_key=None,inference_dependency_key=None,pid=owner['pid'],creation_time=owner['creation_time'],process_state=process_state(owner['pid'],owner['creation_time']),
            session_dir=session,session_evidence='COMPLETE_LONG_NATIVE_RECEIPT' if session else 'NOT_RECORDED',started_utc=start['utc'],finished_utc=(value or {}).get('created_utc',(value or {}).get('utc')),elapsed_sec=(value or {}).get('total_observed_worker_sec',(value or {}).get('elapsed_sec')),native_elapsed_sec=(value or {}).get('native_elapsed_sec'),process_cpu_sec=None,
            audio_duration_sec=(value or {}).get('source_duration_sec'),worker_model_bundle_loads=(value or {}).get('resident_bundle_loads'),bundle_admission_sec=(value or {}).get('model_load_sec'),gallery_manifest=start.get('gallery'),gallery_cache_hit=False if start.get('gallery') and status=='COMPLETE' else None,
            gallery_admission_sec=None,real_gallery_load_observed=bool(start.get('gallery')) and bool((value or {}).get('gallery_load_receipt')),actual_counts=(value or {}).get('event_counts'),output_bindings=outputs,declared_output_bytes=size if outputs else None,bindings_missing_byte_counts=missing,receipt_bindings=[sb]+([vb] if vb else []),error=(value or {}).get('error')))
        long_runs.append(dict(started=sb,result_or_failure=vb,status=status,physical_id=physical,composition=cb))
    result['long_native']=dict(status='OBSERVED' if long_runs else 'NOT_OBSERVED_YET',runs=long_runs,scope='Only the actual continuous native schema is counted. Chronological/model-free lifecycle outputs are excluded. Host concatenation is not continuous physical XVF state or HIL.')
    result['hil']=dict(status='NO_ACTUAL_HIL_RECEIPT_OBSERVED_OR_ADAPTER_ADMITTED',scope='No hardware execution is inferred from prepared composition files, host sessions or reused physical captures.')
    return result


def checks():
    from copy import deepcopy
    from unittest.mock import patch
    import tempfile
    profile=dict(profile_id='C1',input={},asr={},segmentation={},embedding=dict(cadence_policy='fixed',cadence_cues_enabled=False),punctuation={},runtime={},xvf=dict(mode='none'))
    identity=dict(execution_digest='epoch',profile=profile,asr_audio={},identity_audio={},realtime=False)
    row=dict(pid=12,creation_time=1.,started_utc='2026-09-10T00:00:00Z',job_key=digest(identity),identity=identity,status='COMPLETE',session_dir='G:/s1',execution_mode='NEW_NATIVE_INFERENCE',candidate_id='C1',case_id='case',recipe_id='R',asr_tap='O0',identity_tap='O0',worker_model_bundle_loads=2,actual_counts={'research_embedding':3})
    specs={'epoch':dict(epoch='epoch')};validate_native(row,specs);count=1
    group=dict(row=row,sources={});merge_attempt(group,deepcopy(row),dict(path='a',sha256='a'));merge_attempt(group,deepcopy(row),dict(path='b',sha256='a'));assert len(group['sources'])==2;count+=1
    other=row|{'pid':13,'session_dir':'G:/s2'};assert attempt_key(other)!=attempt_key(row) and other['job_key']==row['job_key'];count+=1
    bad=row|{'session_dir':'G:/different'}
    try:merge_attempt(group,bad,dict(path='c',sha256='b'))
    except ValueError:count+=1
    else:raise AssertionError('Different session merged')
    for change in [{'job_key':'bad'},{'status':'COMPLETE_REUSED'},{'session_dir':None},{'creation_time':None}]:
        try:validate_native(row|change,specs)
        except ValueError:count+=1
        else:raise AssertionError('Invalid native receipt admitted')
    try:validate_native(row,{})
    except ValueError:count+=1
    else:raise AssertionError('Foreign epoch admitted')
    simple=dict(physical_id='1',status='COMPLETE',session_dir='G:/s1',pid=12,creation_time=1,worker_model_bundle_loads=2,actual_counts={'research_embedding':3})
    aggregate=summarize([simple,simple|{'physical_id':'2','session_dir':'G:/s2','worker_model_bundle_loads':3}]);assert aggregate['cumulative_worker_bundle_loads_observed']==3 and aggregate['observed_event_counts']['research_embedding']==6;count+=1
    assert prediction_class(Path('guard_fixture_INDEX.json'),{})=='SYNTHETIC_FIXTURE_EXCLUDED';count+=1
    for p,recipe,expected in [('G:/policy_predictions/x.gz','N1','POLICY_ONLY_FROM_S6C_NATIVE_EVIDENCE'),('G:/native_predictions/x.gz','N1','NATIVE_OBSERVATION_PROJECTION_NO_NEW_INFERENCE'),('G:/predictions/x.gz','N00','POLICY_ONLY_FROM_HISTORICAL_S6B_FEATURES')]:
        assert prediction_route(dict(result=dict(path=p),recipe_id=recipe))==expected;count+=1
    with patch.object(psutil,'Process',side_effect=psutil.AccessDenied(1)):assert process_state(1,1)['alive'] is None;count+=1
    with patch.object(psutil,'Process',side_effect=psutil.NoSuchProcess(1)):assert process_state(1,1)['alive'] is False;count+=1
    with tempfile.TemporaryDirectory(prefix='inventory_checks_',dir=STAGING) as temporary:
        root=Path(temporary);assert root.resolve().parent==STAGING.resolve();(root/'out').mkdir();path=root/'mutable.json';path.write_text('{"n":1}',encoding='utf-8')
        reader=MetadataReader(root/'out');old,b=reader.read(path);path.write_text('{"n":2}',encoding='utf-8');again,_=reader.read(path);assert old==again=={'n':1};count+=1
        preserved=reader.sources[0]['preserved'];assert Path(preserved['path']).read_bytes()==b'{"n":1}';count+=1
        try:reader.read(path,b|{'sha256':'f'*64})
        except ValueError:count+=1
        else:raise AssertionError('Wrong binding accepted')
        original_stat=path.stat();path.write_text('{"n":3}',encoding='utf-8');os.utime(path,ns=(original_stat.st_atime_ns,original_stat.st_mtime_ns));(root/'out2').mkdir()
        try:MetadataReader(root/'out2').read(path,b)
        except ValueError:count+=1
        else:raise AssertionError('Changed bytes at old mtime admitted')
    fixed=inference_key(row);new=deepcopy(row);new['identity']['profile']['profile_id']='C2';assert inference_key(new)==fixed;count+=1
    new['identity']['profile']['embedding']['cadence_policy']='uncertainty';full=inference_key(new);new['identity']['gallery']={'sha256':'new'};assert inference_key(new)!=full;count+=1
    declared=dict(path='G:/model',sha256='a'*64,binding=dict(path='G:/model',sha256='a'*64,bytes=100))
    assert list(walk_bindings(declared))[0]['bytes']==100;count+=1
    for change in ({'worker_model_bundle_loads':-1},{'actual_counts':{'research_embedding':-1}}):
        try:summarize([simple|change])
        except ValueError:count+=1
        else:raise AssertionError('Invalid operation/load count admitted')
    assert summarize([simple])['elapsed_sec']==dict(total=None,observed_rows=0,unavailable_rows=1);count+=1
    refs={(canonical('G:/one.json'),'a'*64),(canonical('G:/later.json'),'b'*64)}
    coverage=reference_coverage(refs,[dict(receipt_bindings=[dict(path='G:/one.json',sha256='a'*64)])]);assert coverage['present_in_receipt_snapshot']==1 and len(coverage['not_in_receipt_snapshot'])==1;count+=1
    owner=lambda branch,value:dict(branch=branch,process_state=dict(alive=value))
    for owners,orphans,refs,expected in [([owner('old_epoch',False)],[],[],'CLOSED'),([owner('unknown_only',None)],[],[],'CLOSURE_UNVERIFIED'),
        ([owner('old_epoch',False),owner('current_long',True)],[],[],'ACTIVE'),([owner('current_prefix',True),owner('unknown',None)],[],[],'ACTIVE'),
        ([owner('closed',False)],['G:/orphan'],[],'CLOSURE_UNVERIFIED'),([owner('closed',False)],[],['later_receipt'],'CLOSURE_UNVERIFIED')]:
        assert closure_scope(owners,orphans,refs)['status']==expected;count+=1
    values=owner_identity_summary([owner('closed',False)|{'pid':1,'creation_time':1},owner('unknown',None)|{'pid':1,'creation_time':1}]);assert len(values)==1 and values[0]['process_state']['alive'] is None;count+=1
    return dict(status='PASS',checks=count,model_calls=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('collect','checks'));parser.add_argument('--version')
    args=parser.parse_args()
    if args.action=='collect' and not args.version:parser.error('collect requires a new immutable --version')
    print(json.dumps(collect(args) if args.action=='collect' else checks(),indent=2))
