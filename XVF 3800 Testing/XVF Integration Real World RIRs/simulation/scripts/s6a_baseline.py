"""Single coordinator for missing exact-B0 outputs. README_S6A.md."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import psutil
from s6a_common import *
from s4_h2_run import fixed_gain_copy, completed_session
from s45_h2_run import verify_native_completion, analyze_s45

def same_process(pid,creation):
    try:return abs(psutil.Process(pid).create_time()-creation)<.001
    except psutil.NoSuchProcess:return False

def verify(job):
    rp=Path(job['report_dir'])/'run_receipt.json'
    if not rp.exists():return False
    wrapper=read(rp)
    if wrapper.get('status')!='COMPLETE':return False
    assert wrapper['job_key']==job['job_key'] and wrapper['identity']==job['identity']
    native,_,_=native_receipt(rp)
    assert native['raw_audio']==job['raw_audio'] and native['adapter']['gain_scalar']==job['gain']
    for field in ('metrics_binding','events_binding','session_summary_binding'):bind(native[field]['path'],native[field]['sha256'])
    adapter=native['adapter']['output_binding'];bind(adapter['path'],adapter['sha256'])
    verify_native_completion(Path(native['session_dir']),Path(adapter['path']))
    summary=read(native['session_summary_binding']['path'])
    for key in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures'):
        assert key in summary['telemetry'] and summary['telemetry'][key]==0
    return True

def attempt(job,scene,number,progress):
    folder=Path(job['report_dir'])/('attempt_'+str(number)); payload=Path(job['payload_root'])/('attempt_'+str(number))
    assert not folder.exists() and not payload.exists(),'Preserve existing attempt'
    folder.mkdir(parents=True);payload.mkdir(parents=True)
    root=payload/'empty_data';root.mkdir();adapter_path=payload/'fixed_gain_input.wav'
    bind(job['raw_audio']['path'],job['raw_audio']['sha256'])
    adapter=fixed_gain_copy(job['raw_audio']['path'],adapter_path,job['gain'])
    argv=[str(EDGE_PYTHON),str(SIM/'scripts/s6a_baseline_entry.py'),'file',str(adapter_path),'--accelerated']
    env=single_thread_env();env['EDGE_SPEECH_DATA_ROOT']=str(root);env.pop('EDGE_SPEECH_ASSET_ROOT',None)
    receipt={'schema':'jp_s6a_baseline_attempt_v1','status':'STARTED','case_id':job['case_id'],'stream':job['stream'],
        'job_key':job['job_key'],'identity':job['identity'],'attempt_number':number,'created_utc':now(),
        'raw_audio':job['raw_audio'],'adapter':adapter,'argv':argv,'cwd':str(H2),'isolated_data_root':str(root),
        'initial_profile_files':0,'labels_or_transcripts_sent_to_model':False,'input_provenance':job['input_provenance'],
        'analysis_provenance':job['analysis_provenance'],'baseline_snapshot':str(SNAPSHOT)}
    rp=folder/'attempt_receipt.json';save(rp,receipt);started=time.monotonic();process=None;creation=None;peak_private=0;peak_rss=0
    try:
        with (folder/'stdout.jsonl').open('wb') as stdout,(folder/'stderr.txt').open('wb') as stderr:
            process=subprocess.Popen(argv,cwd=H2,env=env,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            creation=psutil.Process(process.pid).create_time()
            receipt.update(owned_process_pid=process.pid,owned_process_creation_time=creation);save(rp,receipt)
            save(REPORT/'owned_baseline_child.json',{'pid':process.pid,'creation_time':creation,'argv':argv,'started_utc':now()})
            while process.poll() is None:
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:pass
                if time.monotonic()-started>300:raise TimeoutError('Native baseline 300s timeout')
                if process.poll() is None and same_process(process.pid,creation):
                    tree=[psutil.Process(process.pid)]+psutil.Process(process.pid).children(recursive=True)
                    samples=[]
                    for proc in tree:
                        mem=proc.memory_info();samples.append({'pid':proc.pid,'creation_time':proc.create_time(),'rss':mem.rss,
                            'private':getattr(mem,'private',None),'wset':getattr(mem,'wset',None),'shared_pages_measured':False})
                    private=sum(v['private'] or 0 for v in samples);rss=sum(v['rss'] for v in samples)
                    peak_private=max(peak_private,private);peak_rss=max(peak_rss,rss)
                    with (REPORT/'baseline_resource_samples.jsonl').open('a',encoding='utf-8') as f:
                        f.write(json.dumps({'utc':now(),'case_id':job['case_id'],'stream':job['stream'],'processes':samples,
                            'sum_private_bytes':private,'sum_rss_upper_bound_bytes':rss,'available_ram_bytes':psutil.virtual_memory().available})+'\n')
                    assert private<40*2**30 and psutil.virtual_memory().available>=8*2**30,'RAM cap'
        receipt['exit_code']=process.returncode;receipt['model_wall_s']=time.monotonic()-started
        assert process.returncode==0,'Native child failed'
        session=completed_session(root);assert session is not None,'Missing native complete session'
        completion=verify_native_completion(session,adapter_path)
        summary=read(session/'session_summary.json')
        for key in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures'):
            assert key in summary['telemetry'] and summary['telemetry'][key]==0
        metrics=analyze_s45(session,scene,adapter_path,job['alignment'],kind='outputs')
        metrics['reference_scope'].pop('reserve_task_scored',None)
        metrics['reference_scope'].update(s6_all240_authorized=True,historical_split=scene['split'])
        metrics.update(case_id=job['case_id'],stream=job['stream'],kind='outputs',raw_output_rail_samples=adapter['source_rail_samples'],fixed_host_gain=job['gain'])
        save(folder/'metrics.json',metrics)
        receipt.update(status='COMPLETE',session_dir=str(session),completed_utc=now(),completion_evidence=completion,
            metrics_binding=bind(folder/'metrics.json'),session_summary_binding=bind(session/'session_summary.json'),events_binding=bind(session/'events.jsonl'),
            model_success_has_internal_asset_validation=True,audio_duration_s=adapter['duration_s'])
    except BaseException as exc:
        receipt.update(status='FAILED',error=repr(exc),ended_utc=now(),model_wall_s=time.monotonic()-started)
        if isinstance(exc,(KeyboardInterrupt,SystemExit)):raise
    finally:
        if process is not None and process.poll() is None:
            if creation is not None and same_process(process.pid,creation):
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    if same_process(process.pid,creation):process.kill();process.wait(timeout=10)
            elif creation is None:
                # Popen owns the exact Windows process handle, never a recycled PID.
                process.terminate();process.wait(timeout=10)
                receipt['creation_probe_failure_cleanup']='exact Popen Windows process handle'
        receipt.update(owned_child_alive=bool(process and process.poll() is None),peak_private_bytes=peak_private,
                       peak_sum_rss_upper_bound_bytes=peak_rss,resource_shared_pages_separately_measured=False)
        save(rp,receipt);save(REPORT/'owned_baseline_child.json',{'pid':None,'last_child':receipt.get('owned_process_pid'),'closed_utc':now()})
    return receipt

def run(max_new=None):
    import msvcrt
    preparation=read(REPORT/'PREPARATION_RECEIPT.json')
    for key in ('jobs','contract'):bind(preparation[key]['path'],preparation[key]['sha256'])
    contract=read(REPORT/'execution_contract.json')
    for row in contract['code']:bind(row['path'],row['sha256'])
    for row in contract['snapshot']:bind(row['snapshot'],row['sha256'])
    scenes={s['case_id']:s for s in manifest()['scenes']};jobs=read(REPORT/'JOB_MANIFEST.json')['jobs']
    guard=AllBankGuard(list(scenes.values()),'baseline');new_count=0;failed=[];model_seconds=0
    with (REPORT/'baseline_coordinator.lock').open('a+b') as lease:
        lease.seek(0)
        if not lease.read(1):lease.write(b'0');lease.flush()
        lease.seek(0);msvcrt.locking(lease.fileno(),msvcrt.LK_NBLCK,1)
        save(REPORT/'baseline_coordinator.json',{'pid':os.getpid(),'creation_time':psutil.Process().create_time(),'started_utc':now()})
        try:
            with Progress('B0_BASELINE',480) as progress:
                for job in jobs:
                    scene=guard.require(job['case_id'],'baseline_job')
                    progress.detail={'case_id':job['case_id'],'stream':job['stream'],'fresh_complete':new_count,'failed':len(failed),'fresh_model_seconds':model_seconds}
                    if verify(job):progress.done+=1;continue
                    if not launch_allowed() or (max_new is not None and new_count>=max_new):break
                    if (REPORT/'STOP_REQUEST.json').exists():break
                    resources(scan=new_count%12==0)
                    if job['level_gate']=='QUARANTINED_GROSS_SATURATION':failed.append({'case_id':job['case_id'],'stream':job['stream'],'reason':'gross saturation'});continue
                    folder=Path(job['report_dir']);attempts=[read(p) for p in sorted(folder.glob('attempt_*/attempt_receipt.json'))]
                    for previous in attempts:
                        if previous.get('owned_process_pid') and same_process(previous['owned_process_pid'],previous['owned_process_creation_time']):
                            raise RuntimeError('Previous exact owned child still running')
                    completed=next((r for r in attempts if r['status']=='COMPLETE'),None)
                    if completed:
                        save(folder/'run_receipt.json',completed);assert verify(job);progress.done+=1;continue
                    result=None
                    for number in range(len(attempts)+1,3):
                        result=attempt(job,scene,number,progress);model_seconds+=result.get('model_wall_s',0)
                        if result['status']=='COMPLETE':
                            save(folder/'run_receipt.json',result);new_count+=1;progress.done+=1;break
                    if result is None or result['status']!='COMPLETE':
                        failed.append({'case_id':job['case_id'],'stream':job['stream'],'attempts':len(attempts)+(1 if result else 0)})
                        if len(failed)>=2:raise RuntimeError('Two exhausted jobs require diagnosis')
                save(REPORT/'BASELINE_EXECUTION_RECEIPT.json',{'status':'COMPLETE' if progress.done==480 else 'PARTIAL_RESUMABLE',
                    'utc':now(),'requested':480,'complete':progress.done,'fresh_this_invocation':new_count,'fresh_model_seconds':model_seconds,
                    'failed':failed,'hardware_invocations':0,'one_baseline_child':True})
        finally:
            guard.flush()
            save(REPORT/'BASELINE_CLEANUP.json',{'utc':now(),'coordinator_pid':os.getpid(),'creation_time':psutil.Process().create_time(),
                'child_registry':read(REPORT/'owned_baseline_child.json') if (REPORT/'owned_baseline_child.json').exists() else {},
                'hardware_invocations':0,'no_unrelated_process_changes':True})
            lease.seek(0);msvcrt.locking(lease.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--max-new',type=int)
    run(parser.parse_args().max_new)
