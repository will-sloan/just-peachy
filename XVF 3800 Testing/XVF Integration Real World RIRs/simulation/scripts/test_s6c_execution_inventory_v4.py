"""Tiny metadata-only guards; README_S6C_EXECUTION_INVENTORY_V4.md."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import argparse,hashlib,json,tempfile
import s6c_execution_inventory_v4 as A


def fake(path,size=8):return dict(path=str(path),bytes=size,sha256='1'*64)


def fixture(root,change=None,complete=True):
    save=A.base.write_new
    owner=dict(pid=12345,creation_time=10.,argv=['python','worker'])
    pb=save(root/'MANIFEST.json',dict(fixture=True));plan=dict(schema=A.CANONICAL,execution_manifest={},report_root=str(root));spec=dict(gallery_index=None,execution_digest='fixture')
    source=dict(duration_sec=4/16000,duration_samples=4,pcm_sha256=dict(O0='1'*64,O1='1'*64));sb=save(root/'source.json',source)
    job=dict(job_id='cell',job_key='key',candidate_id='C071',case_id='case',asr_tap='O0',identity_tap='O0',repetition=1,source=sb,profile_row={'fixture':'exact','recipe_id':'N07'},profile_sha256='p',gallery=None,gallery_row=None,report_root=str(root/'job'),payload_root=str(root/'payload'))
    owner['argv']=A.expected_worker_argv(job,plan,pb)
    plan['jobs']=[job];folder=Path(job['report_root']);out=A.GUARDS['native_folder'](job);session=Path(job['payload_root'])/out.relative_to(folder)/'sessions/session1'
    journals={name:fake(session/name) for name in ('audio_spool.pcm16','identity_audio_spool.pcm16')}
    if change=='journal':journals['audio_spool.pcm16']['sha256']='2'*64
    final=dict(state='COMPLETED',finalization_error=None,live_lanes_at_finalization=[],resident_bundle_lease_retained=False,event_and_transcript_handles_closed=True)
    if change=='closure_error':final['finalization_error']='error'
    if change=='closure_missing':final.pop('finalization_error')
    if change=='closure_live':final['live_lanes_at_finalization']=['speaker']
    if change=='closure_writer':final['event_and_transcript_handles_closed']=False
    fb=save(session/'session_finalization_v3.json',final)
    native=dict(schema='s6c_continuous_paced_native.v1',status='COMPLETE',composition=sb,profile=job['profile_row'],owner=owner,source_duration_sec=source['duration_sec'],long_session_gallery_condition=None,gallery_index=None,resident_bundle_loads=1,resident_sessions_created=1,live_owned_lanes=[],hardware_invocations=0,final_telemetry=dict(asr_cursor_sec=source['duration_sec']),model_load_sec=.1,native_elapsed_sec=1.,total_observed_worker_sec=1.2,native_journals=journals,native_artifacts=[*journals.values(),fb],process_samples=fake(out/'PROCESS_SAMPLES.jsonl'),process_sample_count=1)
    for key,value in {'native_schema':('schema','wrong'),'native_profile':('profile',{}),'native_owner':('owner',dict(owner,pid=2)),'native_tail':('final_telemetry',dict(asr_cursor_sec=0)),'native_loads':('resident_bundle_loads',2),'native_time':('model_load_sec',True)}.items():
        if change==key:native[value[0]]=value[1]
    nb=save(out/'RESULT.json',native)
    cell=dict(schema='s6c-canonical-paced-cell-result.v1',status='COMPLETE',manifest=pb,job=job,owner=owner,source=sb,source_kind='CANONICAL_SINGLE_SCENE_PAIR',actual_execution_epoch='epoch4',execution_manifest={},source_offset_samples=0,inserted_gap_samples=0,original_native_function_unchanged=True,native_result=nb)
    for key,value in {'cell_epoch':('actual_execution_epoch','epoch6'),'cell_source':('source_kind','LONG'),'cell_gap':('inserted_gap_samples',1),'cell_profile':('job',{}),'cell_offset':('source_offset_samples',1)}.items():
        if change==key:cell[value[0]]=value[1]
    cb=save(folder/'CELL_RESULT.json',cell) if change!='failed_after_native' else None
    admission=dict(status='STARTED',owner=owner,manifest=pb,job=job,source=sb,source_kind='CANONICAL_SINGLE_SCENE_PAIR',actual_execution_epoch='epoch4',execution_manifest={})
    if change=='admission_owner':admission['owner']=dict(owner,pid=2)
    ab=save(folder/'CELL_ADMISSION.json',admission)
    launch=dict(job_key='key',manifest=pb,pid=owner['pid'],creation_time=owner['creation_time'],argv=owner['argv'])
    if change=='launch_argv':launch['argv']=['other']
    lb=save(folder/'LAUNCH.json',launch)
    outcome=dict(status='NATIVE_RETURNED',owner=owner,manifest=pb,job_key='key',native_result=nb,error=None,protected_functions_restored=True)
    if change=='failed_after_native':outcome.update(status='FAILED',error='fixture post-native headroom failure')
    if change=='outcome_error':outcome['error']='error'
    if change=='outcome_restored':outcome['protected_functions_restored']=False
    ob=save(folder/'CELL_OUTCOME.json',outcome)
    ext=fake(folder/'PROCESS_TREE_SAMPLES.jsonl');artifacts=[cb,nb,ext,ob,ab,lb]+native['native_artifacts']+[native['process_samples']]
    done=dict(status='COMPLETE',job_key='key',job_id='cell',all_owned_processes_closed=True,source_kind='CANONICAL_SINGLE_SCENE_PAIR',cell_result=cb,native_result=nb,artifacts=artifacts,owned_processes=[owner])
    for key,value in {'done_cell':('cell_result',{}),'done_native':('native_result',{}),'done_artifacts':('artifacts',artifacts[:-1]),'done_owner':('owned_processes',[]),'done_flag':('all_owned_processes_closed',False)}.items():
        if change==key:done[value[0]]=value[1]
    db=save(folder/'COMPLETE.json',done) if complete else None
    snapshot=root/'snap';snapshot.mkdir();reader=A.base.MetadataReader(snapshot)
    return reader,job,plan,pb,spec,db


def historical_fixture(root,change=None):
    save=A.base.write_new;job=dict(job_id='B36_case_O0_R1',job_key='hkey',profile_id='B36',recipe_id='R0',case_id='case',stream='O0',repetition=1,duration_sec=.5,input_pcm_sha256='1'*64,app_path='historical_app',profile=dict(profile_id='B36'),input=fake(root/'input.wav'))
    plan=dict(schema='s6c-historical-paced-b36.v1',output_root=str(root),driver=fake(A.HERE/'s6b_paced.py'),timeout_sec=720,historical_epoch={},historical_baseline_authority={})
    pb=save(root/'MANIFEST.json',dict(fixture=True));folder=root/'jobs'/job['job_id'];session=root/'native_session';launch=dict(pid=54321,creation_time=20.,job_key=job['job_key'],argv=A.expected_worker_argv(job,plan,pb))
    if change=='launch_override':launch['argv']+=['--mode','other']
    save(folder/'LAUNCH.json',launch)
    n=dict(status='COMPLETE',job_key=job['job_key'],pid=launch['pid'],creation_time=launch['creation_time'],native_pcm_exact=True,asr_cursor_complete=True,empty_gallery=True,hardware_calls=0,truth_passed_to_predictor=False,source_duration_sec=.5,session_dir=str(session),journal=fake(session/'audio_spool.pcm16',16000),events=fake(session/'events.jsonl'),display_events=fake(folder/'DISPLAY_EVENTS.json'),summary_binding=fake(session/'session_summary.json'))
    if change=='cursor':n['asr_cursor_complete']=False
    if change=='owner':n['pid']=54322
    if change=='journal':n['journal']['sha256']='2'*64
    nb=save(folder/'WORKER_RESULT.json',n)
    save(folder/'COMPLETE.json',dict(status='COMPLETE',job_key=job['job_key'],worker=n,all_owned_processes_closed=True,owned_processes=[dict(pid=n['pid'],creation_time=n['creation_time'])],artifacts=[nb,fake(folder/'PROCESS_SAMPLES.jsonl'),n['events'],n['journal'],n['display_events'],n['summary_binding']]))
    snap=root/'snap';snap.mkdir();return A.base.MetadataReader(snap),job,plan,pb,{}


def checks():
    count=A.checks()['checks'];failures=[]
    mutations=['journal','closure_error','closure_missing','closure_live','closure_writer','native_schema','native_profile','native_owner','native_tail','native_loads','native_time','cell_epoch','cell_source','cell_gap','cell_profile','cell_offset','admission_owner','launch_argv','outcome_error','outcome_restored','done_cell','done_native','done_artifacts','done_owner','done_flag']
    for change in [None,*mutations]:
        with tempfile.TemporaryDirectory(prefix='s6c_inventory_cell_') as tmp:
            reader,j,p,pb,s,db=fixture(Path(tmp),change)
            try:value=A.admit_complete_cell(reader,j,p,pb,s,state=lambda *a:dict(alive=False,state='FIXTURE_CLOSED'))
            except (ValueError,KeyError):
                if change is None:raise
                failures.append(change);count+=1
            else:
                assert change is None and value['complete_binding']==db;count+=1
                assert all(Path(r['source']['path']).suffix=='.json' for r in reader.sources);count+=1
                for state in (True,None):
                    try:A.admit_complete_cell(reader,j,p,pb,s,state=lambda *a:dict(alive=state))
                    except ValueError:count+=1
                    else:raise AssertionError('Unclosed owner admitted')
                # Exact index references are bookkeeping, not physical executions.
                for malformed in (False,True):
                    idx=dict(schema=A.CANONICAL,status='COMPLETE',manifest=pb,requested=1,completed=1,rows=[dict(job_id='cell',status='COMPLETE_REUSED',completion=db)])
                    if malformed:idx['rows']*=2
                    path=Path(tmp)/('bad_index.json' if malformed else 'PACED_INDEX.json');ib=A.base.write_new(path,idx)
                    try:A.admit_paced_index(reader,ib,p,pb)
                    except ValueError:
                        assert malformed;count+=1
                    else:assert not malformed;count+=1
    with tempfile.TemporaryDirectory(prefix='s6c_inventory_partial_') as tmp:
        reader,j,p,pb,s,db=fixture(Path(tmp),complete=False)
        with patch.object(A.v3,'process_state',return_value=dict(alive=False,state='FIXTURE_CLOSED')):
            row=A.collect_job(reader,j,p,pb,s)
        assert row['status']=='NATIVE_COMPLETE_OBSERVER_PARTIAL' and row['native_session_complete'] and row['source_composition_epoch'] is None;count+=1
    with tempfile.TemporaryDirectory(prefix='s6c_inventory_failed_outer_') as tmp:
        reader,j,p,pb,s,db=fixture(Path(tmp),'failed_after_native',complete=False)
        with patch.object(A.v3,'process_state',return_value=dict(alive=False,state='FIXTURE_CLOSED')):row=A.collect_job(reader,j,p,pb,s)
        assert row['status']=='FAILED_OUTER_NATIVE_COMPLETE' and row['native_session_complete'] and row['worker_model_bundle_loads']==1;count+=1
    for change in (None,'cursor','owner','journal','launch_override'):
        with tempfile.TemporaryDirectory(prefix='s6c_inventory_historical_') as tmp:
            values=historical_fixture(Path(tmp),change)
            try:
                with patch.object(A.v3,'process_state',return_value=dict(alive=False,state='FIXTURE_CLOSED')):row=A.collect_job(*values)
            except ValueError:assert change is not None;count+=1
            else:assert change is None and row['status']=='COMPLETE' and row['native_session_complete'] and row['epoch']=='S6B_epoch2';count+=1
    with tempfile.TemporaryDirectory(prefix='s6c_inventory_missing_launch_') as tmp:
        reader,j,p,pb,s,db=fixture(Path(tmp),'failed_after_native',complete=False)
        Path(j['report_root'],'LAUNCH.json').unlink()
        try:A.collect_job(reader,j,p,pb,s)
        except ValueError:count+=1
        else:raise AssertionError('Failure without launch called not-launched')
    # Metadata admission of the three real PREPARED manifests, no execution.
    admitted=[]
    paths=[A.REPORT/'paced_candidates/gate6_c071_c082_v1/MANIFEST.json',A.PAYLOAD/'paced_controls/controls_v1/MANIFEST.json',A.PAYLOAD/'paced_controls/b36_v1/MANIFEST.json']
    with tempfile.TemporaryDirectory(prefix='s6c_inventory_plans_') as tmp:
        reader=A.base.MetadataReader(Path(tmp))
        for path in paths:
            raw=path.read_bytes();b=A.base.binding(path,raw);plan,pb,spec=A.admit_plan(reader,b);admitted.append(dict(manifest=pb,schema=plan['schema'],jobs=len(plan['jobs'])));count+=1
            if plan['schema'] in A.HISTORICAL:
                mutations=[('epoch',None),('panel',None),('repeat',None),('input',None),('pcm',None),('duration',None),('gain',None),('app',None),('profile',None)]
                for kind,_ in mutations:
                    bad=deepcopy(plan)
                    if kind=='epoch':bad['historical_epoch']['sha256']='0'*64
                    elif kind=='panel':bad['cases'][0]='foreign'
                    elif kind=='repeat':bad['repeat_case_sets'][1]['case_ids'][0]='foreign'
                    else:
                        j=next((r for r in bad['jobs'] if r['profile_id']!='B00'),bad['jobs'][0])
                        if kind=='input':j['input']['sha256']='0'*64
                        elif kind=='pcm':j['input_pcm_sha256']='0'*64
                        elif kind=='duration':j['duration_sec']+=.25
                        elif kind=='gain':j['gain_context']=2.
                        elif kind=='app':j['app_path']='C:/other_app'
                        elif kind=='profile':j['profile']={'profile_id':j['profile_id']}
                        j.pop('job_key');j['job_key']=A.base.digest(j)
                    bad.pop('manifest_key');bad['manifest_key']=A.base.digest(bad)
                    class SemanticReader:
                        def read(self,path,expected=None):
                            return (bad,pb) if A.base.canonical(path)==A.base.canonical(pb['path']) else reader.read(path,expected)
                    try:A.admit_plan(SemanticReader(),pb)
                    except (ValueError,KeyError):count+=1
                    else:raise AssertionError('Self-consistent changed historical declaration admitted: '+kind)
        assert [r['jobs'] for r in admitted]==[24,80,40];count+=1
        spec,_=reader.read(A.REPORT/'EPOCH4_EXECUTION_MANIFEST.json')
        for candidate in ('C195','C196'):
            try:A.GUARDS['candidate_routes'](spec,[candidate])
            except ValueError:count+=1
            else:raise AssertionError('Unregistered epoch6 candidate admitted')
    prior=A.base.STAGING/'execution_inventory/before_paced_lineage_repairs_v1/SOURCE_INDEX.json'
    previous=A.REPORT/'execution_inventory/ADAPTER_V4_CHECKS_V2.json'
    return dict(status='PASS_MODEL_FREE',checks=count,rejected_semantic_mutations=failures,prepared_manifest_admission=admitted,prior_source_resolver=A.base.binding(prior,prior.read_bytes()),prior_check_receipt=A.base.binding(previous,previous.read_bytes()) if previous.exists() else None,scope='Only JSON fixtures and three prepared manifest/spec/input-index metadata chains. Historical adversarial fixtures override only the in-memory parsed declaration and recompute job/manifest digests; original bytes remain untouched. No paced/full inventory/model/payload run.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=checks();result['sources']=A.source_bindings()+[A.base.binding(__file__,Path(__file__).read_bytes())]
    print(json.dumps(A.base.write_new(args.output,result),indent=2))
