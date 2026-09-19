"""Synthetic/file-only preparation fixtures; README_S6D_PHYSICAL_PREPARATION.md."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import tempfile
import time
import threading
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from s6d_capture_supervisor_bridge_v1 import CaptureProtocol,binding,load,save,restoration_proof,completion_proof,matching_identity
from s6d_capture_transport import quantize,input_qa,timing
from s6d_qualification_diagnostics_v1 import pair_diagnostics,tail_support
import s6d_capture_supervisor_bridge_v1 as bridge_module


def check():
    tests={}
    def fails(fn):
        try:fn();return False
        except (ValueError,KeyError,FileNotFoundError):return True
    identity=dict(run_id='fixture_run',job_id='fixture_job',child_run_id='fixture_child',pid=os.getpid(),creation_time=time.time()-20,admission_unix=time.time()-10)
    tests['identity_exact']=matching_identity(identity,identity)
    for key in ('run_id','job_id','child_run_id','pid','creation_time'):
        bad=dict(identity);bad[key]=bad[key]+1 if isinstance(bad[key],(float,int)) else 'wrong';tests['reject_identity_'+key]=not matching_identity(bad,identity)
    with tempfile.TemporaryDirectory(prefix='s6d_bridge_fixture_') as td:
        root=Path(td);batch=root/'hardware_batches'/'fixture_batch';batch.mkdir(parents=True)
        owner=dict(pid=identity['pid'],acquired_utc=datetime.now(timezone.utc).isoformat())
        restore=dict(status='PASS',exact_recorded_configuration_match=True,telemetry_process_closed=True,hardware_lease_released=True,audio_handles_closed=True)
        save(batch/'owner_acquired.json',owner,True);save(batch/'restoration.json',restore,True)
        ledger=dict(passes=[],batches={batch.name:dict(owner=binding(batch/'owner_acquired.json'),restoration=binding(batch/'restoration.json'))})
        tests['bound_current_restore_accepted']=all(restoration_proof(batch,ledger,identity)['checks'].values())
        tests['no_ledger_binding_no_restore']=fails(lambda:restoration_proof(batch,dict(batches={}),identity))
        tests['wrong_owner_pid_no_restore']=fails(lambda:restoration_proof(batch,ledger,dict(identity,pid=999999)))
        tests['reused_pid_old_acquisition_rejected']=fails(lambda:restoration_proof(batch,ledger,dict(identity,admission_unix=time.time()+5)))
        save(batch/'restoration.json',dict(restore,telemetry_process_closed=False))
        tests['mutated_receipt_hash_rejected']=fails(lambda:restoration_proof(batch,ledger,identity))
        ledger['batches'][batch.name]['restoration']=binding(batch/'restoration.json')
        tests['unclosed_telemetry_no_restore']=fails(lambda:restoration_proof(batch,ledger,identity))
        for key in ('exact_recorded_configuration_match','hardware_lease_released','audio_handles_closed','status'):
            bad=dict(restore);bad[key]='FAIL' if key=='status' else False;save(batch/'restoration.json',bad)
            ledger['batches'][batch.name]['restoration']=binding(batch/'restoration.json');tests['restore_requires_'+key]=fails(lambda:restoration_proof(batch,ledger,identity))
        save(batch/'restoration.json',restore);ledger['batches'][batch.name]['restoration']=binding(batch/'restoration.json')
        pbound=dict(path='fixture_plan',sha256='p');abound=dict(path='fixture_authorization',sha256='a')
        save(batch/'admission.json',dict(plan=pbound,authorization=abound,attempt_ids=['a1']),True)
        result=root/'case_result.json';save(result,dict(attempt=dict(attempt_id='a1'),transport_integrity_status='PASS',level_screen=dict(status='LIMITED'),physical_stream_identity_qualification='NOT_YET_QUALIFIED',processed_source_tail_qualification='PENDING'),True)
        ledger['passes']=[dict(batch=batch.name,attempt_id='a1',status='PASS',result=binding(result),charged_playback_s=12.3413125)]
        summary=dict(status='COMPLETE_CAPTURE_BATCH',executed_source_bytes_unchanged_after_batch=True,completed_attempts=[binding(result)]);save(batch/'SUMMARY.json',summary,True)
        proof=completion_proof(batch,ledger,['a1'],identity,pbound,abound)
        tests['LIMITED_level_preserved_not_hidden']=proof['results'][0]['level_status']=='LIMITED'
        tests['pending_physical_identity_preserved']=proof['results'][0]['stream_identity_status']=='NOT_YET_QUALIFIED'
        tests['wrong_plan_cannot_complete']=fails(lambda:completion_proof(batch,ledger,['a1'],identity,dict(pbound,sha256='wrong'),abound))
        tests['wrong_attempt_cannot_complete']=fails(lambda:completion_proof(batch,ledger,['a2'],identity,pbound,abound))
        save(batch/'SUMMARY.json',dict(summary,executed_source_bytes_unchanged_after_batch=False))
        tests['mutated_source_epoch_cannot_complete']=fails(lambda:completion_proof(batch,ledger,['a1'],identity,pbound,abound))
        save(root/'physical_ledger.json',ledger,True)
        paths={k:root/(k+'.json') for k in ('heartbeat','completion','stop','restoration')}
        protocol=CaptureProtocol(identity,paths,root,batch.name,root/'payload',[])
        protocol.progress();count=protocol.progress_count;protocol.heartbeat();protocol.heartbeat();protocol.progress()
        tests['heartbeat_and_poll_not_fake_progress']=protocol.progress_count==count
        tests['wrong_stop_not_forwarded']=not protocol.forward_stop(dict(identity,child_run_id='wrong')) and not (root/'STOP_REQUEST.json').exists()
        tests['right_stop_forwarded']=protocol.forward_stop(dict(identity,reason='fixture')) and load(root/'STOP_REQUEST.json')['reason']=='fixture'
        protocol.forward_stop(dict(identity,reason='new'))
        tests['existing_owner_stop_not_overwritten']=load(root/'STOP_REQUEST.json')['reason']=='fixture'
        (root/'physical_ledger.json').write_text('{',encoding='utf-8');protocol.progress()
        tests['partial_ledger_does_not_advance_progress']=protocol.progress_count==count
        scan=CaptureProtocol(identity,paths,root,'scan',root/'payload',[dict(case_id='c',profile='P_MAIN6',attempt_id='x')])
        calls=[];original_exists=Path.exists
        def scan_exists(path):
            calls.append(str(path))
            if path.name=='configuration.json':scan.closed.set()
            return False
        with patch.object(Path,'exists',scan_exists):scan.progress()
        tests['progress_scan_honors_close_between_entries']=len(calls)<=3 and scan.checkpoint_count==0
        relay=CaptureProtocol(identity,paths,root/'relay','relay',root/'payload',[])
        with patch.object(bridge_module,'save',side_effect=PermissionError('persistent synthetic relay failure')):relay.forward_stop(dict(identity,reason='fixture'))
        tests['relay_write_failure_still_sets_shared_event']=relay.stop.is_set() and relay.stop_delivery['event_set']
        tests['relay_failure_not_claimed_delivered']=not relay.stop_delivery['file_relay_delivered'] and relay.stop_delivery['file_relay_unresolved'] and bool(relay.stop_delivery['errors'])
        observer=CaptureProtocol(identity,paths,root/'observer','observer',root/'payload',[])
        with patch.object(observer,'progress',side_effect=RuntimeError('synthetic observer error')),patch.object(bridge_module,'save',side_effect=PermissionError('synthetic relay failure')):observer.observe()
        tests['observer_failure_and_undelivered_file_recorded']=observer.stop.is_set() and len(observer.errors)>=2 and observer.stop_delivery['file_relay_unresolved']
        original_replace=os.replace;replace_calls=[]
        def retry_replace(src,dst):
            replace_calls.append(str(src))
            if len(replace_calls)<=2:raise PermissionError('synthetic transient Windows sharing lock')
            return original_replace(src,dst)
        with patch.object(bridge_module.os,'replace',retry_replace):save(root/'atomic.json',dict(value=1))
        tests['atomic_replace_transient_retried']=len(replace_calls)==3 and load(root/'atomic.json')['value']==1
        with patch.object(bridge_module.os,'replace',side_effect=PermissionError('persistent lock')) as replacement:
            try:save(root/'persistent.json',dict(value=1))
            except PermissionError:tests['atomic_replace_persistent_fail_closed']=replacement.call_count==6 and not (root/'persistent.json').exists()
            else:tests['atomic_replace_persistent_fail_closed']=False
    # Exercise the real wrapper orchestration with an in-memory owner double.
    # The fake owner only creates temporary receipts; hardware imports are absent.
    for behavior in ('success','raise_before_owner','raise_after_restoration','late_stop_after_join','late_stop_before_publish'):
        with tempfile.TemporaryDirectory(prefix='s6d_bridge_execute_fixture_') as td:
            root=Path(td);owner_path=root/'owner.py';owner_path.write_text('# fixture-only owner binding\n',encoding='utf-8')
            plan_path=root/'plan.json';authorization_path=root/'authorization_fixture.json'
            save(plan_path,dict(report_root=str(root/'report'),payload_root=str(root/'payload'),attempts=[dict(attempt_id='a1',case_id='case1',profile='P_MAIN6')]),True)
            save(authorization_path,dict(scope='TEMPORARY_FIXTURE_NOT_EXECUTION_AUTHORITY'),True)
            def fake_execute(plan_path,authorization_path,batch_id,attempt_ids,external_stop_event=None):
                tests['actual_bridge_passes_shared_event_'+behavior]=isinstance(external_stop_event,threading.Event)
                if behavior=='raise_before_owner':raise RuntimeError('Synthetic failure before ownership')
                batch=root/'report'/'hardware_batches'/batch_id;batch.mkdir(parents=True)
                save(batch/'owner_acquired.json',dict(pid=os.getpid(),acquired_utc=datetime.now(timezone.utc).isoformat()),True)
                save(batch/'restoration.json',dict(status='PASS',exact_recorded_configuration_match=True,telemetry_process_closed=True,hardware_lease_released=True,audio_handles_closed=True),True)
                save(batch/'admission.json',dict(plan=binding(plan_path),authorization=binding(authorization_path),attempt_ids=attempt_ids),True)
                result=root/'case_result.json';save(result,dict(attempt=dict(attempt_id='a1'),transport_integrity_status='PASS',level_screen=dict(status='LIMITED'),physical_stream_identity_qualification='PENDING'),True)
                save(batch/'SUMMARY.json',dict(status='COMPLETE_CAPTURE_BATCH',executed_source_bytes_unchanged_after_batch=True,completed_attempts=[binding(result)]),True)
                save(root/'report'/'physical_ledger.json',dict(passes=[dict(batch=batch_id,attempt_id='a1',status='PASS',result=binding(result))],batches={batch_id:dict(owner=binding(batch/'owner_acquired.json'),restoration=binding(batch/'restoration.json'))}),True)
                if behavior=='raise_after_restoration':raise RuntimeError('Synthetic late owner error with valid cleanup')
            fake_owner=SimpleNamespace(validate_plan=lambda *args:None,execute=fake_execute)
            env=dict(S6D_RUN_ID='synthetic_run',S6D_JOB_ID='synthetic_job',S6D_CHILD_RUN_ID='synthetic_child',
                S6D_HEARTBEAT_PATH=str(root/'protocol/HEARTBEAT.json'),S6D_COMPLETION_PATH=str(root/'protocol/COMPLETE.json'),
                S6D_STOP_REQUEST_PATH=str(root/'protocol/STOP_REQUEST.json'),S6D_RESTORATION_PATH=str(root/'protocol/RESTORATION.json'))
            spec=SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module:None))
            original_close=CaptureProtocol.close;latest={};original_save=bridge_module.save
            def close_hook(protocol):
                original_close(protocol);latest['identity']=protocol.identity
                if behavior=='late_stop_after_join':original_save(protocol.paths['stop'],dict(protocol.identity,reason='late_stop_after_join'),True)
            def save_hook(path,value,*args,**kwargs):
                if behavior=='late_stop_before_publish' and Path(path)==Path(env['S6D_COMPLETION_PATH']):original_save(env['S6D_STOP_REQUEST_PATH'],dict(latest['identity'],reason='late_stop_before_publish'),True)
                return original_save(path,value,*args,**kwargs)
            with patch.dict(os.environ,env),patch.object(bridge_module.importlib.util,'spec_from_file_location',return_value=spec),patch.object(bridge_module.importlib.util,'module_from_spec',return_value=fake_owner),patch.object(CaptureProtocol,'close',close_hook),patch.object(bridge_module,'save',save_hook):
                result=bridge_module.execute(owner_path,binding(owner_path)['sha256'],plan_path,binding(plan_path)['sha256'],authorization_path,binding(authorization_path)['sha256'],'freshbatch',['a1'])
            if behavior=='success':
                tests['mock_execute_complete_after_bound_restore']=result['status']=='COMPLETE' and load(env['S6D_RESTORATION_PATH'])['verified'] is True
                tests['mock_execute_LIMITED_survives']=result['semantic_checks']['results'][0]['level_status']=='LIMITED'
            elif behavior=='raise_before_owner':tests['mock_execute_no_owner_no_fabricated_restore']=result['status']=='FAILED' and not Path(env['S6D_RESTORATION_PATH']).exists() and not Path(env['S6D_COMPLETION_PATH']).exists()
            elif behavior=='raise_after_restoration':tests['mock_execute_late_error_restores_but_not_complete']=result['status']=='FAILED' and Path(env['S6D_RESTORATION_PATH']).exists() and not Path(env['S6D_COMPLETION_PATH']).exists()
            else:tests['matching_'+behavior+'_no_COMPLETE']=result['status']=='FAILED' and Path(env['S6D_RESTORATION_PATH']).exists() and not Path(env['S6D_COMPLETION_PATH']).exists() and result['stop_delivery']['event_set']
            tests['mock_execute_observer_closed_'+behavior]=result['protocol_observer_closed']
    rng=np.random.default_rng(7042);mic=rng.uniform(-.02,.02,(4096,4));q=quantize(mic)
    delayed=np.pad(q,((127,31),(0,0)));delayed[:,:2]=432
    qa=input_qa(delayed,q)
    tests['QA_one_common_four_mic_lag']=qa['status']=='PASS' and qa['capture_minus_source_offset_samples']==127
    tests['QA_swapped_route_rejected']=input_qa(delayed[:,[0,1,3,2,4,5]],q)['status']=='FAIL'
    tests['QA_duplicated_route_rejected']=input_qa(delayed[:,[0,1,2,2,4,5]],q)['status']=='FAIL'
    tests['QA_lost_tail_rejected']=input_qa(delayed[:-100],q)['status']=='FAIL'
    six=rng.normal(size=(4096,6));second=np.pad(six,((71,11),(0,0)));diag=pair_diagnostics(six,second,128)
    tests['pair_single_shared_lag']=diag['common_offset_samples']==71 and all(abs(r['cosine_correlation']-1)<1e-12 for r in diag['channels'])
    scaled=pair_diagnostics(six,np.pad(six*.5,((71,11),(0,0))),128)
    tests['pair_does_not_normalize_level_difference']='COMMON_STREAM_LEVEL_DIFFERENCE_OVER_3DB' in scaled['review_flags'] and scaled['audio_modified'] is False
    independent=second.copy();independent[:,2]=np.roll(independent[:,2],13)
    tests['independent_channel_shift_not_repaired']=any(r['cosine_correlation']<.90 for r in pair_diagnostics(six,independent,128)['channels'])
    tests['silent_pair_unidentifiable']=pair_diagnostics(np.zeros((200,6)),np.zeros((210,6)))['common_offset_samples'] is None
    tests['source_tail_extent_retained']=tail_support(mic,np.zeros((4300,6)),127,0)['status']=='PASS_EXTENT_ONLY'
    tests['source_tail_extent_missing_rejected']=tail_support(mic,np.zeros((4200,6)),127,0)['status']=='FAIL_SOURCE_EXTENT'
    tests['unknown_latency_not_invented']=tail_support(mic,np.zeros((4300,6)),None)['status']=='UNKNOWN_LATENCY'
    tests['continuous_guard_charge_exact']=timing(900)['carrier_seconds']==904 and timing(900)['charged_playback_seconds']==904.3413125
    assert all(tests.values()),{k:v for k,v in tests.items() if not v}
    return dict(status='PASS_MODEL_FREE',checks=tests,passed=len(tests),hardware_calls=0,audio_streams_opened=0,vendor_DLL_calls=0,model_calls=0,
        scope='Synthetic arrays and temporary file receipts only; no physical route or restoration performed')


def check_prepared(result_path):
    import soundfile as sf
    from s6d_physical_prepare_v1 import fingerprints
    data=load(result_path);tests={};inputs={row['input_id']:row for row in data['inputs']};arrays={}
    for name,row in inputs.items():
        binding(row['audio']['path'],row['audio']['sha256']);x,rate=sf.read(row['audio']['path'],dtype='float32',always_2d=True);arrays[name]=x
        tests[name+'_actual_format_fingerprints']=rate==16000 and x.shape[1]==4 and len(x)/16000==row['source_seconds'] and fingerprints(x)==row['fingerprints']
        tests[name+'_quantizable_without_gain_change']=np.isfinite(x).all() and np.max(np.abs(x))<1 and quantize(x).shape==(len(x),6)
    for row in data['C_sources']:binding(row['audio']['path'],row['audio']['sha256'])
    tests['all30_original_C_source_bytes_bound']=len(data['C_sources'])==30 and all(row['role']=='C' for row in data['C_sources'])
    q=quantize(arrays['tagged_C_sentinel']);simulated_capture=np.pad(q,((173,48000),(0,0)));simulated_capture[:,:2]=900
    result=input_qa(simulated_capture,q)
    tests['actual_sentinel_exact_fourMIC_at_one_delay']=result['status']=='PASS' and result['capture_minus_source_offset_samples']==173
    tests['actual_sentinel_duplicate_corruption_rejected']=input_qa(simulated_capture[:,[0,1,2,2,4,5]],q)['status']=='FAIL'
    tests['source_swap_input_is_distinct']=not np.array_equal(arrays['C_overlap'],arrays['C_overlap_source_swap'])
    tests['silence_input_is_exact_zero']=not np.any(arrays['digital_silence'])
    tests['calibration_equal_clock_tail']=arrays['C30_calibration_R04'].shape==arrays['C30_calibration_R12'].shape
    budget=data['forecast'];tests['complete_plan_plus_optional_reserve_within_both_limits']=budget['including_optional_reserve']['attempts']<=480 and budget['including_optional_reserve']['charged_seconds']<=21600
    assert all(tests.values()),{k:v for k,v in tests.items() if not v}
    return dict(status='PASS_PREPARED_FILE_CHECKS',prepared_result=binding(result_path),checks={k:bool(v) for k,v in tests.items()},passed=len(tests),hardware_calls=0,model_calls=0,audio_streams_opened=0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--prepared-result',type=Path);a=p.parse_args();result=check()
    if a.prepared_result:result['prepared_file_checks']=check_prepared(a.prepared_result)
    save(a.output,result,True);print(json.dumps(result,indent=2),flush=True)
