"""Model-free S6B actual-cache and native/replay validation. README_S6B_VALIDATION.md.

Never alters authoritative evidence. Fault injection uses verified temporary
copies under S6B staging. No model session, hardware, or truth-based predictor
is created. Run this live validator against an immutable execution epoch.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
for _pool_key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_pool_key]='1'
import numpy as np

SIM=Path(os.environ.get('JP_S6B_SIM',Path(__file__).resolve().parents[1])).resolve()
RUN='20260909T230840Z'
REPORT=SIM/'reports/S6B'/RUN
STAGING=SIM/'staging/s6b'/RUN/'validation'
ARTIFACTS=('evidence','vectors','events','summary','full_journal')
EVENT_PARITY_EXCLUSIONS=('compute_finished_elapsed_sec','modeled_available_at_sec',
                         'release_watermark_lower_bound_sec','release_after_all_lanes_closed')
IDENTITY_MUTATIONS=(
    ('execution_digest',None),('recipe_id',None),('audio_sha256',None),('audio_bytes',None),
    ('input_gain',('input','gain')),('prior_gain_flag',('input','already_gained')),
    ('asr_dispatch',('asr','journal_read_ms')),('asr_search',('asr','decoding_method')),
    ('endpoint',('asr','endpoint_rule2_silence_sec')),('segmentation_hop',('segmentation','hop_sec')),
    ('segmentation_policy',('segmentation','post_policy')),('embedding_window',('embedding','window_sec')),
    ('embedding_hop',('embedding','hop_sec')),('embedding_rms_policy',('embedding','rms_policy')),
    ('embedding_evidence_policy',('embedding','evidence_policy')),('numeric_thread_config',('runtime','speaker_threads')),
    ('cue_routing',('xvf','mode')),('scheduler_evidence_expiry',('scheduler','evidence_expiry_sec')),
)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def binding(path):
    p=Path(path).resolve();return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def save(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def now():return datetime.now(timezone.utc).isoformat()


def load_api(manifest):
    spec=read(manifest);root=Path(spec['root']).resolve()
    if np.__version__!=spec['runtime_versions']['numpy'] or sys.version!=spec['runtime_versions']['python']:
        raise ValueError('Exact native/replay numeric parity requires the epoch Python/NumPy runtime; use repository .edge-speech-env/python.exe')
    os.environ['JP_S6B_SIM']=str(SIM)
    for row in spec['execution_files']:
        if sha(row['path'])!=row['sha256']:raise ValueError('Frozen execution file changed: '+row['path'])
    sys.path.insert(0,str(root/'scripts'))
    execution=importlib.import_module('s6b_execution');replay=importlib.import_module('s6b_replay')
    for module in (execution,replay):
        if Path(module.__file__).resolve().parent!=root/'scripts':raise ValueError('Validation imported a live runner instead of frozen epoch')
    common=importlib.import_module('s6b_common')
    if Path(common.__file__).resolve().parent!=root/'scripts':raise ValueError('Common cache API did not come from frozen epoch')
    for key in ('input_index','gain_index','effective_profile_registry','challenge_panel','recipe_registry','scene_manifest'):
        common.bind(spec[key]['path'],spec[key]['sha256'])
    return spec,execution,replay,replay.api(spec),common


def alter(value):
    if type(value) is bool:return not value
    if isinstance(value,(int,float)):return value+(.125 if isinstance(value,float) else 1)
    return str(value)+'_CHANGED_FOR_CACHE_REJECTION'


def cache_checks(spec,execution,common,job,recipe,main,alternate):
    """An actual successful cache hit followed by 28 isolated rejection fixtures."""
    original_hit=execution.verify_cached(job)
    if original_hit is None:raise ValueError('The actual pilot job is not cached')
    receipt=read(Path(job['folder'])/'run_receipt.json');results=[]
    STAGING.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cache_',dir=STAGING) as directory:
        root=Path(directory).resolve()
        if not root.is_relative_to(STAGING.resolve()):raise ValueError('Temporary fault target escaped staging')
        copied=deepcopy(receipt);copy_job=deepcopy(job);copy_job['folder']=str(root)
        original_bytes={}
        for key in ARTIFACTS:
            dest=root/(key+'.blob');shutil.copy2(receipt[key]['path'],dest)
            copied[key]=common.bind(dest);original_bytes[key]=dest.read_bytes()
        common.save(root/'run_receipt.json',copied)
        assert execution.verify_cached(copy_job)['status']=='COMPLETE_REUSED'

        def reject(name,call):
            try:call()
            except (ValueError,RuntimeError,FileNotFoundError) as exc:
                results.append({'name':name,'status':'PASS','rejection_type':type(exc).__name__})
            else:results.append({'name':name,'status':'FAIL','reason':'changed dependency was accepted'})

        for name,path in IDENTITY_MUTATIONS:
            changed_spec=deepcopy(spec);changed_recipe=deepcopy(recipe);changed_main=deepcopy(main);changed_alternate=deepcopy(alternate)
            selected=changed_alternate[main['case_id'],main['stream']] if recipe.get('gain_variant')=='minus3' else changed_main
            if name=='execution_digest':changed_spec['execution_digest']='f'*64 if spec['execution_digest']!='f'*64 else 'e'*64
            elif name=='recipe_id':changed_recipe['recipe_id']+='_DIFFERENT'
            elif name=='audio_sha256':selected['audio']['sha256']='0'*64
            elif name=='audio_bytes':selected['audio']['bytes']+=1
            else:
                section,field=path;changed_recipe['profile'][section][field]=alter(changed_recipe['profile'][section][field])
            changed=execution.make_job(changed_spec,changed_recipe,changed_main,changed_alternate);changed['folder']=str(root)
            assert changed['job_key']!=job['job_key'],name+' failed to participate in cache identity'
            reject('identity:'+name,lambda changed=changed:execution.verify_cached(changed))
        for key in ARTIFACTS:
            target=Path(copied[key]['path']);stat=target.stat();data=bytearray(original_bytes[key])
            if not data:raise ValueError('Cannot exercise changed-byte fixture on an empty artifact')
            data[len(data)//2]^=1;target.write_bytes(data)
            os.utime(target,ns=(stat.st_atime_ns,stat.st_mtime_ns))
            assert target.stat().st_size==stat.st_size and target.stat().st_mtime_ns==stat.st_mtime_ns
            reject('same_size_old_mtime_changed_bytes:'+key,lambda:execution.verify_cached(copy_job))
            target.write_bytes(original_bytes[key]);os.utime(target,ns=(stat.st_atime_ns,stat.st_mtime_ns))
            assert execution.verify_cached(copy_job)['status']=='COMPLETE_REUSED'
        for key in ARTIFACTS:
            target=Path(copied[key]['path']);target.unlink()
            reject('missing_artifact:'+key,lambda:execution.verify_cached(copy_job))
            target.write_bytes(original_bytes[key])
            assert execution.verify_cached(copy_job)['status']=='COMPLETE_REUSED'
    assert len(results)==28
    return {'status':'PASS' if all(r['status']=='PASS' for r in results) else 'FAIL','actual_cache_hit':original_hit,
            'fault_fixtures':28,'rows':results,'all_faults_on_temporary_copies':True,'authoritative_evidence_unchanged':True}


def clean_record(row):
    # Native lane sealing is batched; offline replay seals at each arrival.
    # Keep semantic availability, report release diagnostics separately below.
    return {k:v for k,v in row.items() if k not in EVENT_PARITY_EXCLUSIONS}


def native_parity(receipt,evidence,vectors,profile,provider,replay,classes):
    actual=replay.run_scheduler(profile,provider,evidence,vectors,classes)
    events=[json.loads(line) for line in Path(receipt['events']['path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    native_decisions=[e['payload']['decision'] for e in events if e['event_type']=='speaker_decision']
    native_raw_transcripts=[e['payload'] for e in events if e['event_type'].startswith('transcript_')]
    native_transcripts=[clean_record(p) for p in native_raw_transcripts]
    differences=[]
    if native_decisions!=actual['decisions']:differences.append('speaker_decisions')
    if native_transcripts!=[clean_record(p) for p in actual['transcript_events']]:differences.append('transcript_events')
    path=Path(receipt['session_dir'])/'latest_labelled_transcript.jsonl'
    native_rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    def finals(label):
        return [dict(utterance_index=str(r['utterance_id']),text=r['text'],speaker=r[label] or 'Unknown',
            source_cursor_s=r['source_end_sec'],source_start_sec=r['source_start_sec'],
            first_display_time=r['first_display_time'],first_final_time=r['first_final_time'],latest_label_time=r['latest_label_time']) for r in native_rows if r.get('is_final')]
    for key,label in (('final_transcripts_first','first_final_label'),('final_transcripts_latest','latest_label'),('final_transcripts_first_display','first_display_label')):
        if finals(label)!=actual[key]:differences.append(key)
    return {'status':'PASS' if not differences else 'FAIL','differences':differences,'decisions':len(native_decisions),
            'transcript_events':len(native_transcripts),'finals':len(native_rows),'native_latest_transcript':binding(path),
            'event_semantic_parity_exclusions':list(EVENT_PARITY_EXCLUSIONS),
            'native_vs_replay_release_diagnostic_differences':sum(any(n.get(k)!=r.get(k) for k in EVENT_PARITY_EXCLUSIONS[2:])
                 for n,r in zip(native_raw_transcripts,actual['transcript_events'])),
            'release_diagnostic_scope':'Native batched lane watermarks versus immediately sealed offline observation arrivals; not claimed equal or used as physical latency.',
            'wall_costs_excluded_from_value_parity':True,'source_and_modeled_availability_not_excluded':True},actual


def truncate_evidence(evidence,vectors,cutoff):
    result=deepcopy(evidence);mask=[i for i,f in enumerate(evidence['features']) if f['available_at_sec']<=cutoff]
    result['features']=[deepcopy(evidence['features'][i]) for i in mask]
    result['segmentation']=[deepcopy(r) for r in evidence['segmentation'] if r['available_at_sec']<=cutoff]
    result['asr_observations']=[deepcopy(r) for r in evidence['asr_observations'] if r['available_at_sec']<=cutoff]
    return result,vectors[mask]


def causal_checks(evidence,vectors,profile,provider,replay,classes,full):
    arrivals=[r['available_at_sec'] for r in replay.scheduler_inputs(evidence,vectors)]
    if not arrivals:return {'status':'NOT_EXERCISED','reason':'no admitted observations'}
    cutoff=sorted(arrivals)[len(arrivals)//2]
    short,short_vectors=truncate_evidence(evidence,vectors,cutoff)
    prefix=replay.run_scheduler(profile,provider,short,short_vectors,classes)
    expected_decisions=[r for r in full['decisions'] if r['available_at_sec']<=cutoff]
    expected_transcripts=[r for r in full['transcript_events'] if r['available_at_sec']<=cutoff]
    checks={'future_prefix_decisions':prefix['decisions']==expected_decisions,
            'future_prefix_transcripts':[clean_record(r) for r in prefix['transcript_events']]==[clean_record(r) for r in expected_transcripts]}
    renamed=deepcopy(short);renamed['case_id']='UNTRUSTED_RENAME';renamed['room']='NOT_PREDICTOR_INPUT';renamed['true_schedule']=[{'speaker':'DIFFERENT'}]
    for row in renamed['features']:row['true_speaker']='RENAMED';row['true_azimuth']=-999
    rename_result=replay.run_scheduler(profile,provider,renamed,short_vectors,classes)
    checks['truth_metadata_rename']=rename_result['decisions']==prefix['decisions'] and rename_result['transcript_events']==prefix['transcript_events']
    return {'status':'PASS' if all(checks.values()) else 'FAIL','cutoff_sec':cutoff,'checks':checks}


def tracker_parents_and_schema(evidence,vectors,classes,observation_provider):
    from edge_speech_pipeline.research_tracking_v2 import S6BTrackingConfig,SPATIAL_ONLY,MODES
    Profile,Provider,Tracker,Scheduler=classes
    selected=list(zip(evidence['features'],vectors))[:64]
    def run(config,rows,provider=observation_provider):
        tracker=Tracker(config);out=[]
        for row,vector in rows:
            observation=provider.evidence(row['source_start_sec'],row['available_at_sec']) if config.cues_enabled else None
            out.append(tracker.update(vector,row['source_start_sec'],row['source_end_sec'],row['available_at_sec'],spatial=observation,
                                      speech=row.get('speech',True),overlap=row.get('overlap',False)))
        return out
    baseline=run(S6BTrackingConfig(),selected);checks={}
    for mode in sorted(SPATIAL_ONLY):
        for flag in (None,'sensor_quarantine_enabled','update_escrow_enabled'):
            cfg=S6BTrackingConfig(mode=mode,**({flag:True} if flag else {}))
            checks['cue_disabled:'+mode+':'+str(flag)]=run(cfg,selected)==baseline
    for mode in ('bayes','hsmm','global_assignment','dual_memory','multiprototype','quarantine','delay_graph'):
        parent=S6BTrackingConfig(mode=mode)
        checks['structural_parent:'+mode]=run(parent,selected)==run(replace(parent,sensor_quarantine_enabled=True,update_escrow_enabled=True),selected)
    for mode in MODES:
        cfg=S6BTrackingConfig(mode=mode,max_tracks=256 if mode=='original_common' else 16,
                             cues_enabled=mode not in ('original_common','one_person','all_unknown','voice'))
        cut=len(selected)//2
        checks['all_mode_prefix:'+mode]=run(cfg,selected[:cut])==run(cfg,selected)[:cut]
    STAGING.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='schema_',dir=STAGING) as directory:
        root=Path(directory).resolve();assert root.is_relative_to(STAGING.resolve())
        path=root/'forbidden_truth.jsonl';path.write_text(json.dumps({'available_at_sec':1.,'angle_deg':20.,'reliability':1.,'valid':True,'true_speaker':'ORACLE'})+'\n',encoding='utf-8')
        try:Provider(path)
        except ValueError:checks['provider_rejects_truth_schema']=True
        else:checks['provider_rejects_truth_schema']=False
        future_path=root/'future_only_append.jsonl'
        original=Path(observation_provider.path).read_text(encoding='utf-8-sig')
        future=max([f['available_at_sec'] for f,_ in selected]+[stamp for stamp,_ in observation_provider.rows])+100.
        future_path.write_text(original.rstrip()+'\n'+json.dumps({'available_at_sec':future,'source_end_sec':future,'angle_deg':179.,'energy':1.,'reliability':1.,'valid':True})+'\n',encoding='utf-8')
        changed_provider=Provider(future_path)
        for mode in sorted(SPATIAL_ONLY):
            cfg=S6BTrackingConfig(mode=mode,cues_enabled=True)
            checks['future_cue_append:'+mode]=run(cfg,selected)==run(cfg,selected,changed_provider)
    return {'status':'PASS' if all(checks.values()) else 'FAIL','actual_cached_features':len(selected),'checks':checks}


def run(manifest,index_path,output_name='ACTUAL_PILOT_VALIDATION.json'):
    started=time.perf_counter();spec,execution,replay,classes,common=load_api(manifest)
    index=read(index_path);rows=index.get('rows',[])
    completed=[r for r in rows if str(r.get('status','')).startswith('COMPLETE')]
    if not completed:raise ValueError('Actual completed pilot rows are required')
    mains={(r['case_id'],r['stream']):r for r in read(spec['input_index']['path'])['rows']}
    alternate={(r['case_id'],r['stream']):r for r in read(spec['gain_index']['path'])['rows']}
    recipes={r['recipe_id']:r for r in spec['recipes']};Profile,Provider,_,_=classes
    results=[];cache=None;parent_checks=None
    for row in completed:
        main=mains[row['case_id'],row['stream']];recipe=recipes[row['recipe_id']]
        job=execution.make_job(spec,recipe,main,alternate);hit=execution.verify_cached(job)
        if hit is None:raise ValueError('Index row lacks exact actual cache hit')
        receipt=read(Path(job['folder'])/'run_receipt.json')
        if row.get('receipt'):common.bind(row['receipt']['path'],row['receipt']['sha256'])
        e=read(receipt['evidence']['path']);common.bind(e['vectors']['path'],e['vectors']['sha256'])
        with np.load(e['vectors']['path'],allow_pickle=False) as archive:vectors=archive['vectors'].copy()
        if vectors.shape!=(len(e['features']),192):raise ValueError('Feature/vector shape mismatch')
        profile=Profile.from_dict(recipe['profile']);provider=None
        if profile.tracker.cues_enabled:
            common.bind(main['telemetry']['path'],main['telemetry']['sha256']);provider=Provider(Path(main['telemetry']['path']))
        parity,full=native_parity(receipt,e,vectors,profile,provider,replay,classes)
        causal=causal_checks(e,vectors,profile,provider,replay,classes,full)
        results.append({'case_id':row['case_id'],'stream':row['stream'],'recipe_id':row['recipe_id'],
                        'status':'PASS' if parity['status']=='PASS' and causal['status'] in ('PASS','NOT_EXERCISED') else 'FAIL',
                        'native_parity':parity,'causality':causal,'actual_receipt':binding(Path(job['folder'])/'run_receipt.json')})
        if cache is None:cache=cache_checks(spec,execution,common,job,recipe,main,alternate)
        if parent_checks is None and len(vectors):
            common.bind(main['telemetry']['path'],main['telemetry']['sha256'])
            parent_checks=tracker_parents_and_schema(e,vectors,classes,Provider(Path(main['telemetry']['path'])))
    failures=[r for r in results if r['status']=='FAIL']
    result={'schema':'jp_s6b_actual_pilot_validation_v1','created_utc':now(),
            'status':'PASS' if not failures and cache['status']=='PASS' and parent_checks and parent_checks['status']=='PASS' else 'FAIL',
            'population':'Every completed row in the supplied native pilot index; not an all-bank result',
            'index_population_complete':index.get('status')=='COMPLETE','actual_rows_checked':len(results),
            'native_replay_rows':results,'cache_rejection_checks':cache,'same_code_parent_and_schema':parent_checks,
            'execution_manifest':binding(manifest),'native_index':binding(index_path),'validator_code':binding(__file__),
            'elapsed_sec':time.perf_counter()-started,'neural_calls':0,'hardware_invocations':0,
            'faults_used_authoritative_evidence':False}
    if Path(output_name).name!=output_name or not output_name.endswith('.json'):raise ValueError('Output name must be a JSON filename within validation reports')
    save(REPORT/'validation'/output_name,result)
    return {k:result[k] for k in ('status','actual_rows_checked','index_population_complete','elapsed_sec','neural_calls')}


def prepare():
    plan={'schema':'jp_s6b_validation_plan_v1','status':'READY_FOR_ACTUAL_PILOT','created_utc':now(),
          'identity_dependencies':[name for name,_ in IDENTITY_MUTATIONS],
          'same_size_old_mtime_changed_byte_artifacts':list(ARTIFACTS),'missing_artifacts':list(ARTIFACTS),
          'planned_rejection_fixtures':len(IDENTITY_MUTATIONS)+2*len(ARTIFACTS),
          'actual_checks':['canonical native/replay decisions','all transcript events','first-display/first-final/latest final transcripts',
                           'prefix/future invariance','metadata rename','same-code cue-off parents','strict provider schema'],
          'neural_or_hardware_execution':False,'validator_code':binding(__file__)}
    save(REPORT/'validation/VALIDATION_PLAN.json',plan);return plan


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('prepare','run'))
    parser.add_argument('--epoch',default='epoch2');parser.add_argument('--manifest',type=Path);parser.add_argument('--neural-index',type=Path)
    parser.add_argument('--output-name',default='ACTUAL_PILOT_VALIDATION.json')
    args=parser.parse_args()
    manifest=args.manifest or REPORT/(args.epoch.upper()+'_EXECUTION_MANIFEST.json')
    index=args.neural_index or REPORT/args.epoch/'PILOT_NEURAL_INDEX.json'
    result=prepare() if args.mode=='prepare' else run(manifest,index,args.output_name)
    print(json.dumps(result,indent=2));raise SystemExit(1 if result['status']=='FAIL' else 0)


if __name__=='__main__':main()
