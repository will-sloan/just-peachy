"""Bounded metadata fixtures; README_S6C_EXECUTION_INVENTORY_V5.md."""
from pathlib import Path
from copy import deepcopy
import argparse,ast,hashlib,json,tempfile,types
import s6c_execution_inventory_v5 as A

def fake(path,bytes=8,sha='1'*64):return dict(path=str(path),bytes=bytes,sha256=sha)

def long_fixture(root,change=None):
    save=A.base.write_new;out=root/'payload/jobs/B36_CONTINUOUS_O0_R1';session=out/'sessions/one'
    job=dict(job_id='B36_CONTINUOUS_O0_R1',job_key='key',profile_id='B36',recipe_id='R0',case_id=None,stream='O0',repetition=1,app_path='exact/historical/app',profile=dict(profile_id='B36'),input=fake(root/'existing.wav'),input_pcm_sha256='a'*64,duration_sec=1827.426625)
    plan=dict(schema=A.LONG,report_root=str(root/'report'),output_root=str(root/'payload'),jobs=[job],historical_epoch=fake(root/'historical.json'),composition=fake(root/'composition.json'),source_kind='EXISTING_CONTINUOUS_COMPOSITION')
    pb=save(root/'manifest.json',dict(fixture=True));owner=dict(pid=999987,creation_time=10.);argv=A.long_argv(plan,pb);native_owner=dict(**owner,argv=argv)
    coordinator=dict(pid=999989,creation_time=12.,argv=['fixture-coordinator']);inv=root/'report/invocations/fixture'
    qb=fake(root/'quiet.json');lease=dict(kind='S6C_EXACT_HISTORICAL_B36_CONTINUOUS',**coordinator,manifest=pb,quiet_admission=qb)
    archived=save(inv/'QUIET_LEASE_RELEASED.json',lease);lb={**archived,'path':str(A.REPORT/'PACED_QUIET_OWNER.json')}
    ab0=save(inv/'ADMISSION.json',dict(status='STARTED',owner=coordinator,manifest=pb,quiet_admission=qb,quiet_lease=lb))
    save(inv/'CHILD_SPAWN.json',dict(status='POPEN_SUCCEEDED_IDENTITY_PENDING',pid=owner['pid'],creation_time=None,argv=argv,manifest=pb,job_key='key'))
    launch=dict(**owner,manifest=pb,job_key='key',argv=argv)
    if change=='argv_override':launch['argv']=argv+['--manifest','other']
    launchb=save(out/'LAUNCH.json',launch)
    admission=dict(schema=A.LONG,status='STARTED',owner=native_owner,manifest=pb,job=job,quiet_lease=lb,actual_execution_epoch='S6B_epoch2',historical_epoch=plan['historical_epoch'],source_composition_epoch='S6C_epoch2',composition=plan['composition'])
    if change=='admission_source':admission['composition']={}
    if change=='native_admission_wrong_lease':admission['quiet_lease']=fake(root/'other_lease.json')
    ab=save(out/'CONTINUOUS_ADMISSION.json',admission)
    n=dict(status='COMPLETE',job_key='key',**owner,created_utc='fixture',source_duration_sec=1827.426625,complete_pcm_samples=29238826,native_pcm_exact=True,asr_cursor_complete=True,
        journal=fake(session/'audio_spool.pcm16',58477652,'a'*64),empty_gallery=True,hardware_calls=0,truth_passed_to_predictor=False,numeric_pools={k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')},session_dir=str(session),events=fake(session/'events.jsonl'),summary_binding=fake(session/'session_summary.json'),display_events=fake(out/'DISPLAY_EVENTS.json'),
        summary=dict(telemetry=dict(asr_cursor_sec=1827.426625,source_duration_sec=1827.426625,audio_frames_dropped=0,portaudio_input_overflows=0,raw_capture_reserve_failures=0)),native_dispatch_delivery=dict(no_gaps_or_duplicates=True,starts_at_zero=True,ends_at_full_duration=True,exact_samples=True),baseline_dispatch_instrumentation_unavailable=False,full_worker_elapsed_sec=1829.,process_cpu_sec_at_end=20.,bundle_admission_sec=.1,event_counts=dict(transcript_final=2))
    if change=='native_pcm':n['journal']['sha256']='b'*64
    if change=='native_cursor':n['summary']['telemetry']['asr_cursor_sec']=0
    nb=save(out/'WORKER_RESULT.json',n)
    outcome=dict(schema=A.LONG_RESULT,status='NATIVE_COMPLETE',owner=native_owner,manifest=pb,job_key='key',native_result=nb,error=None,original_worker_function_unchanged=True,actual_execution_epoch='S6B_epoch2',historical_epoch=plan['historical_epoch'],source_composition_epoch='S6C_epoch2',composition=plan['composition'])
    if change=='outcome_epoch':outcome['actual_execution_epoch']='epoch4'
    if change=='failed_outcome_with_complete_result':outcome.update(status='FAILED',error='fixture post-native failure')
    ob=save(out/'CONTINUOUS_OUTCOME.json',outcome)
    own=[dict(**owner,alive=False,error=None)];trajectory=fake(out/'PROCESS_SAMPLES.jsonl');artifacts=[nb,ob,ab,launchb,trajectory,n['events'],n['journal'],n['display_events'],n['summary_binding']]
    result=dict(schema=A.LONG_RESULT,status='COMPLETE_NATIVE_AND_OWNED_CHILD_CLOSED',manifest=pb,job=job,owner=coordinator,native_owner=owner,native_result=nb,native_outcome=ob,source_kind='EXISTING_CONTINUOUS_COMPOSITION',actual_execution_epoch='S6B_epoch2',historical_epoch=plan['historical_epoch'],source_composition_epoch='S6C_epoch2',composition=plan['composition'],source_duration_sec=1827.426625,source_duration_samples=29238826,all_owned_processes_closed=True,original_worker_unchanged=True,periodic_process_samples=3,terminal_process_samples=1,process_samples=4,artifacts=artifacts,owned_processes=own,observer_stats={})
    if change=='outer_samples':result['process_samples']=3
    if change=='outer_artifacts':result['artifacts']=artifacts[:-1]
    if change=='outer_owner':result['native_owner']=dict(owner,pid=999988)
    if change=='outer_lineage':result['source_kind']='CANONICAL_SINGLE_SCENE_PAIR'
    rb=save(root/'report/RESULT.json',result)
    po=dict(schema=A.LONG,status='NATIVE_COMPLETE',owner=coordinator,manifest=pb,native_result=nb,continuous_result=rb,error=None,owned_processes=own)
    if change=='coordinator_native_binding':po['native_result']={}
    if change=='coordinator_omits_native_owner':po['owned_processes']=[]
    pob=save(inv/'NATIVE_OUTCOME.json',po)
    c=dict(schema=A.LONG,status='NATIVE_COMPLETE_QUIET_RELEASED',owner=coordinator,manifest=pb,pre_release_outcome=pob,continuous_result=rb,error=None,owned_processes=own,lease_release=dict(status='RELEASED',released=True,source=lb,archived_binding=archived))
    if change=='lease_flag':c['lease_release']['released']=False
    if change=='closure_result':c['continuous_result']={}
    if change=='named_complete_with_retained_lease':c['lease_release'].update(status='RETAINED_OWNED_CLOSURE_UNVERIFIED',released=False)
    if change=='coordinator_omits_native_owner':c['owned_processes']=[]
    save(inv/'CLOSURE.json',c)
    snap=root/'snap';snap.mkdir();reader=A.base.MetadataReader(snap)
    return reader,job,plan,pb,A.long_guards(reader)

def checks():
    done=[]
    def good(name):done.append(dict(name=name,status='PASS'))
    ns=A.compile_functions(A.HERE/'test_s6c_execution_inventory_v4.py',{'fake','fixture'},dict(A=A.S,Path=Path,deepcopy=deepcopy),{'s6c-canonical-paced-cell-result.v1':'s6c-paced-arrival-sentinel-cell-result.v1'})
    mutations=['journal','closure_error','closure_missing','closure_live','closure_writer','native_schema','native_profile','native_owner','native_tail','native_loads','native_time','cell_epoch','cell_source','cell_gap','cell_profile','cell_offset','admission_owner','launch_argv','outcome_error','outcome_restored','done_cell','done_native','done_artifacts','done_owner','done_flag']
    for change in [None,*mutations]:
        with tempfile.TemporaryDirectory() as d:
            reader,j,p,pb,s,db=ns['fixture'](Path(d),change)
            try:value=A.admit_complete_cell(reader,j,p,pb,s,state=lambda *a:dict(alive=False))
            except (ValueError,KeyError):
                if change is None:raise
                good('sentinel_reject_'+change)
            else:
                assert change is None and value['complete_binding']==db;good('sentinel_complete_chain')
                for state in (True,None):
                    try:A.admit_complete_cell(reader,j,p,pb,s,state=lambda *a:dict(alive=state))
                    except ValueError:good('sentinel_owner_'+str(state))
                    else:raise AssertionError('Unclosed sentinel admitted')
    for change in [None,'argv_override','admission_source','native_admission_wrong_lease','native_pcm','native_cursor','outcome_epoch','failed_outcome_with_complete_result','outer_samples','outer_artifacts','outer_owner','outer_lineage','coordinator_native_binding','coordinator_omits_native_owner','lease_flag','closure_result','named_complete_with_retained_lease']:
        with tempfile.TemporaryDirectory() as d:
            reader,j,p,pb,g=long_fixture(Path(d),change)
            try:row=A.admit_long_native(reader,p,pb,{},g);inv,owners,spawns=A.long_invocations(reader,p,pb)
            except (ValueError,KeyError):
                if change is None:raise
                good('continuous_reject_'+change)
            else:
                assert change is None and row['status']=='COMPLETE' and row['native_session_complete'] and row['source_composition_epoch']=='S6C_epoch2' and row['epoch']=='S6B_epoch2';good('continuous_complete_chain')
                rows=[];sessions={};assert A.v4.add_physical(rows,sessions,row) and not A.v4.add_physical(rows,sessions,deepcopy(row));good('continuous_exact_duplicate_not_new_attempt')
                unknown=A.unverified_spawn_row(p,pb,*spawns[0]);assert unknown['creation_time'] is None and not unknown['native_session_complete'] and unknown['process_state']['alive'] is None;good('successful_popen_unknown_creation_is_attempt_not_session')
                assert all(Path(x['source']['path']).suffix=='.json' for x in reader.sources);good('continuous_json_only_reads')
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);snap=root/'snapshot';snap.mkdir();reader=A.base.MetadataReader(snap)
        path=A.REPORT/'paced_arrival_sentinel/arrival_boundary_v1/MANIFEST.json';raw=path.read_bytes();b=A.base.binding(path,raw);assert b['sha256']=='92c5d2a8fa716400d253d0b18a8ff65d901698ef29762c2b07ae19687d5dc00d'
        plan,pb,spec=A.admit_plan(reader,b);assert len(plan['jobs'])==12;good('actual_prepared_sentinel_metadata')
        g=A.long_guards(reader);a=g['authorities']();assert a['entry']['profile']['tracker']['mode']=='original_common' and g['asset_bindings'](a['spec']);good('actual_long_historical_composition_metadata_only')
        long_path=A.REPORT/'long_b36/b36_o0_continuous_v1/MANIFEST.json';longb=A.base.binding(long_path,long_path.read_bytes());assert longb['sha256']=='0421d6479332282194feed991a0aa1759e2c7908197d74507675c91960f7a632';actual_long=A.admit_long(reader,longb);assert len(actual_long[0]['jobs'])==1 and actual_long[0]['jobs'][0]['stream']=='O0';good('actual_root_prepared_long_manifest_metadata_only')
        r,p=g['roots']('metadata_fixture_only');j=g['make_job'](a,'O0');j['job_key']=A.base.digest(j)
        fixture=dict(schema=A.LONG,status='PREPARED_NO_MODELS_STARTED',namespace='metadata_fixture_only',report_root=str(r),output_root=str(p),payload_root=str(p),actual_execution_epoch='S6B_epoch2',source_composition_epoch='S6C_epoch2',source_kind='EXISTING_CONTINUOUS_COMPOSITION',historical_epoch=a['epoch'],source_sealed_index=a['sealed'],b36_registry_entry=a['entry'],composition=a['composition_binding'],runtime_versions=a['spec']['runtime_versions'],resource_limits=g['LIMITS'],timeout_sec=g['TIMEOUT'],cleanup_max_sec=g['CLEANUP_MAX_SEC'],original_limits=g['LIMIT_NOTES'],worker_limit=1,inner_threads=1,deadline_utc=g['DEADLINE'].isoformat(),jobs=[j],driver=fake(A.HERE/'s6b_paced.py',sha='e755867e703bc6f4dc457db8ad6e98b078af8cf3abcf15fce8adf58efd10fcd9'),original_worker_ast_sha256='2ba2cac603b8302797a7b99b7c44f8f50a67b4692d1718e92391ea542a1f2d3f',sources=[A.base.binding(A.HERE/'s6c_long_b36_v1.py',(A.HERE/'s6c_long_b36_v1.py').read_bytes())])
        fixture['manifest_key']=A.base.digest(fixture)
        class SuppliedJSON:
            def __init__(self,value):self.value=value;self.binding=A.base.binding(r/'MANIFEST.json',json.dumps(value).encode())
            def read(self,path,binding=None):
                if Path(path)==r/'MANIFEST.json':
                    assert binding is None or binding==self.binding;return deepcopy(self.value),self.binding
                return reader.read(path,binding)
        supplied=SuppliedJSON(fixture);value=A.admit_long(supplied,supplied.binding);assert value[0]==fixture;good('in_memory_prospective_long_plan_no_manifest_written')
        for name,path,val in [('worker_ast',['original_worker_ast_sha256'],'0'*64),('native_epoch',['actual_execution_epoch'],'epoch4'),('composition',['source_composition_epoch'],'S6B_epoch2'),('cue',['jobs',0,'telemetry'],{}),('profile',['jobs',0,'profile','tracker','max_tracks'],16),('audio',['jobs',0,'input'],a['composition']['audio']['O1']),('duration',['jobs',0,'duration_sec'],45.),('timeout',['timeout_sec'],600.),('schema',['schema'],A.SENTINEL)]:
            mutated=deepcopy(fixture);target=mutated
            for key in path[:-1]:target=target[key]
            target[path[-1]]=val
            for job in mutated['jobs']:
                copy=dict(job);copy.pop('job_key');job['job_key']=A.base.digest(copy)
            mutated.pop('manifest_key');mutated['manifest_key']=A.base.digest(mutated);supplied=SuppliedJSON(mutated)
            try:A.admit_long(supplied,supplied.binding)
            except (ValueError,KeyError,TypeError):good('in_memory_long_rekeyed_reject_'+name)
            else:raise AssertionError('Rekeyed long declaration accepted: '+name)
    source=(A.HERE/'s6c_execution_inventory_v4.py').read_bytes();assert hashlib.sha256(source).hexdigest()==A.PINS['s6c_execution_inventory_v4.py'];good('held_v4_unchanged')
    assert A.v4.CANONICAL=='s6c-canonical-paired-paced.v1' and A.v4.admit_plan.__globals__['CANONICAL']==A.v4.CANONICAL;good('isolated_sentinel_globals_no_v4_mutation')
    return done

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();before=A.source_bindings();result=checks();assert A.source_bindings()==before
    held=A.base.SIM/'staging/s6c/20260910T123540Z/execution_inventory/v5_draft_source_checks_v1';prior=json.loads((held/'ADAPTER_V5_CHECKS_DRAFT_V1.json').read_bytes());resolver=[]
    for b in prior['sources']+[prior['test_source']]:
        path=held/Path(b['path']).name
        if path.exists():
            actual=A.base.binding(path,path.read_bytes());assert actual['sha256']==b['sha256'] and actual['bytes']==b['bytes'];resolver.append(dict(original=b,preserved=actual))
    held1=A.base.SIM/'staging/s6c/20260910T123540Z/execution_inventory/v5_before_status_repairs_v1';prior1=json.loads((held1/'ADAPTER_V5_CHECKS_V1.json').read_bytes());resolver1=[]
    for b in prior1['sources']+[prior1['test_source']]:
        path=held1/Path(b['path']).name
        if path.exists():
            actual=A.base.binding(path,path.read_bytes());assert actual['sha256']==b['sha256'] and actual['bytes']==b['bytes'];resolver1.append(dict(original=b,preserved=actual))
    held2=A.base.SIM/'staging/s6c/20260910T123540Z/execution_inventory/v5_before_cross_chain_repairs_v2';prior2=json.loads((held2/'ADAPTER_V5_CHECKS_V2.json').read_bytes());resolver2=[]
    for b in prior2['sources']+[prior2['test_source']]:
        path=held2/Path(b['path']).name
        if path.exists():
            actual=A.base.binding(path,path.read_bytes());assert actual['sha256']==b['sha256'] and actual['bytes']==b['bytes'];resolver2.append(dict(original=b,preserved=actual))
    held3=A.base.SIM/'staging/s6c/20260910T123540Z/execution_inventory/v5_before_actual_long_fixture_v3';prior3=json.loads((held3/'ADAPTER_V5_CHECKS_V3.json').read_bytes());test3=prior3['test_source'];actual3=A.base.binding(held3/Path(test3['path']).name,(held3/Path(test3['path']).name).read_bytes());assert actual3['sha256']==test3['sha256'] and actual3['bytes']==test3['bytes']
    b=A.base.write_new(a.output,dict(schema=A.SCHEMA,status='PASS_MODEL_FREE',checks=result,check_count=len(result),sources=before,test_source=A.base.binding(Path(__file__),Path(__file__).read_bytes()),sentinel_literal_substitutions=A.SENTINEL_REPLACEMENTS,preserved_draft_sources=resolver,preserved_v1_sources=resolver1,preserved_v2_sources=resolver2,preserved_v3_test=dict(original=test3,preserved=actual3),model_calls=0,full_inventory_runs=0,payload_reads=0,scope='Synthetic metadata chains and exact prepared sentinel/old historical composition metadata. No native result, PCM, events, trajectories or model bank scan.'))
    print(json.dumps(b))
