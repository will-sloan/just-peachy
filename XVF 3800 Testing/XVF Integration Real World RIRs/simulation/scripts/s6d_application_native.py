"""Predeclare/freeze and run one bounded S6D native cell. See README_S6D_APPLICATION.md."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time

SIM=Path(__file__).resolve().parents[1]
REPO=SIM.parents[2]
APP=REPO/'Software Validation from Datasets/Evaluation Tool/app/edge_speech_pipeline'
S6C=SIM/'reports/S6C/20260910T123540Z'


def bind(path):
    path=Path(path).resolve();h=hashlib.sha256()
    with path.open('rb') as handle:
        for part in iter(lambda:handle.read(1024*1024),b''):
            h.update(part)
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':h.hexdigest()}


def read(binding):
    path=Path(binding['path'])
    if bind(path)!=binding:
        raise ValueError('Source changed: '+str(path))
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path,value):
    with Path(path).open('x',encoding='utf-8') as handle:
        json.dump(value,handle,indent=2,allow_nan=False);handle.write('\n')


def plan(directory,payload):
    directory.mkdir(parents=True,exist_ok=False)
    if payload.exists():
        raise ValueError('Use a fresh proposed payload root')
    epoch_binding=bind(S6C/'EPOCH4_EXECUTION_MANIFEST.json');epoch=read(epoch_binding)
    inputs=read(epoch['input_index'])['rows']
    gallery_index_binding=bind(S6C/'RESEARCH_GALLERY_INDEX.json');gallery_index=read(gallery_index_binding)
    frozen=directory/'source/edge_speech_pipeline';frozen.mkdir(parents=True)
    files=[]
    for source in sorted(APP.iterdir()):
        if source.suffix in {'.py','.md'}:
            shutil.copy2(source,frozen/source.name);files.append(bind(frozen/source.name))
    helper_dir=directory/'helpers';helper_dir.mkdir()
    for source in (Path(__file__),Path(__file__).with_name('README_S6D_APPLICATION.md')):
        shutil.copy2(source,helper_dir/source.name)
    jobs=[]
    for candidate,scenes,variants in [('C065',['S45_01_06','S45_08_07'],['original','delivery_repair']),
            ('C088',['S45_01_06','S45_08_07'],['original','delivery_only','delivery_repair']),
            ('C105',['S45_08_07'],['original','delivery_repair'])]:
        p=next(r for r in epoch['profiles'] if r['candidate_id']==candidate and r['asr_tap']==r['identity_tap']=='O0')
        profile=read(p['profile_binding'])
        gallery=next(r['manifest'] for r in gallery_index['rows'] if r['gallery_condition']==p['gallery_condition'] and
            r['enrollment_tier']==15 and r['case_id'] is None) if candidate!='C065' else None
        if gallery and len(read(gallery)['profiles'])!=15:
            raise ValueError('Original A15 gallery required')
        for case in scenes:
            inp=next(r for r in inputs if r['case_id']==case and r['stream']=='O0')
            if bind(inp['audio']['path'])!=inp['audio']:
                raise ValueError('Prepared audio changed')
            for variant in variants:
                settings=None if variant=='original' else {'schema_version':'edge-s6d.v1','text_delivery':True,
                    'boundary_repair':variant=='delivery_repair','transcript_mode':'T0','direction_mode':'V0'}
                key=f'{candidate}_{case}_{variant}'
                jobs.append({'job_id':key,'candidate':candidate,'scene_id':case,'variant':variant,
                    'profile':profile,'profile_binding':p['profile_binding'],'gallery':gallery,
                    'telemetry':inp['telemetry'] if candidate=='C105' else None,'audio':inp['audio'],
                    'audio_duration_sec':inp['duration_sec'],'settings':settings,'output':str(payload/key)})
    result={'schema':'s6d-native-pilot.v1','status':'PREDECLARED_NOT_EXECUTED','created_utc':datetime.now(timezone.utc).isoformat(),
        'purpose':'12-cell paced diagnostic screener; no full-bank/finalist/CM5 acceptance',
        'source_root':str(frozen.parent),'execution_files':files,'prior_epoch':epoch_binding,'gallery_index':gallery_index_binding,
        'assets':epoch['assets'],'payload_root':str(payload),'jobs':jobs,'job_count':len(jobs),
        'source_audio_total_sec':sum(x['audio_duration_sec'] for x in jobs),
        'timing_goals':{'paired_naming_additional_first_text_p50_sec':.10,'paired_naming_additional_first_text_p95_sec':.25,
            'p99_and_never_emitted_required':True,'label_display_only_raw_words_identical':True},
        'limits':{'serial_jobs':True,'cell_timeout_sec':180.,'resource_sample_sec':.25,'cpu_threads_each':1,
            'minimum_c_free_gib':50.,'minimum_g_free_gib':75.,'max_new_payload_gib':40.,'no_audio_playback':True},
        'helper':bind(helper_dir/Path(__file__).name),'readme':bind(helper_dir/'README_S6D_APPLICATION.md'),
        'planner':bind(__file__),
        'default_promoted':False,'hardware_started':False,'model_jobs_started':0}
    write(directory/'MANIFEST.json',result)
    print(json.dumps({'manifest':bind(directory/'MANIFEST.json'),'jobs':len(jobs),'source_seconds':result['source_audio_total_sec']}))


def run_one(manifest_path,job_id,checkpoint=None):
    """Execute one bound cell; cooperative callback uses keyword engine/telemetry/job/output."""
    manifest=read(bind(manifest_path));job=next(r for r in manifest['jobs'] if r['job_id']==job_id)
    if bind(__file__)!=manifest['helper']:
        raise ValueError('Execute the exact frozen helper bound by this manifest')
    for source in manifest['execution_files']:
        if bind(source['path'])!=source:
            raise ValueError('Frozen application source changed')
    read(job['profile_binding'])
    if bind(job['audio']['path'])!=job['audio']:
        raise ValueError('Prepared waveform changed')
    for drive,floor in [('C:/',50.),('G:/',75.)]:
        if shutil.disk_usage(drive).free/1024**3<floor:
            raise RuntimeError('Declared disk reserve unavailable')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key]='1'
    sys.dont_write_bytecode=True;sys.path.insert(0,manifest['source_root'])
    cfg=importlib.import_module('edge_speech_pipeline.config')
    profiles=importlib.import_module('edge_speech_pipeline.research_profiles')
    runtime=importlib.import_module('edge_speech_pipeline.runtime')
    s6d=importlib.import_module('edge_speech_pipeline.research_s6d')
    for module in (cfg,profiles,runtime,s6d):
        if Path(module.__file__).resolve().parent != Path(manifest['source_root'])/'edge_speech_pipeline':
            raise RuntimeError('Application module was imported from another source epoch')
    assets=tuple(cfg.AssetSpec(r['component_id'],Path(r['path']),r['sha256'],r['deployment_relative_path']) for r in manifest['assets'])
    output=Path(job['output']);output.mkdir(parents=True,exist_ok=False)
    profile=profiles.ResearchProfile.from_dict(job['profile'])
    base=cfg.PipelineConfig(assets=assets,session_root=output/'sessions',profile_root=output/'empty_private_profiles')
    effective=profile.apply(base)
    if any(getattr(effective,k)!=1 for k in ('asr_threads','speaker_threads','punctuation_threads')):
        raise ValueError('Predeclared single CPU threads required')
    if job['telemetry'] and bind(job['telemetry']['path'])!=job['telemetry']:
        raise ValueError('Bound telemetry changed')
    if job['gallery']:
        read(job['gallery'])
    provider=profiles.JsonSpatialProvider(job['telemetry']['path']) if job['telemetry'] else None
    settings=s6d.S6DSettings(**job['settings']) if job['settings'] else None
    class InstrumentedEngine(runtime.PipelineEngine):
        def _emit(self,event_type,source_sec,payload):
            return super()._emit(event_type,source_sec,{**payload,'pilot_publication_monotonic_sec':time.perf_counter()})
    engine=InstrumentedEngine(base,research_profile=profile,spatial_provider=provider,
        research_gallery=job['gallery']['path'] if job['gallery'] else None,s6d_settings=settings)
    return execute_cell(engine,job,manifest,manifest_path,output,checkpoint)


def completion_errors(engine,telemetry):
    """Fail closed on worker/consumer/finalizer leaks, including apparently COMPLETED state."""
    errors=[]
    if engine.state!='COMPLETED':errors.append('native session did not complete')
    if not engine.events.empty():errors.append('event consumer not drained')
    if engine._finalization_thread is None or engine._finalization_thread.is_alive():
        errors.append('finalization thread not joined')
    for worker in getattr(engine,'_threads',()):
        if worker.is_alive():errors.append('live engine worker: '+worker.name)
    if telemetry.get('live_lanes_at_finalization') or telemetry.get('bundle_retained_due_live_lanes'):
        errors.append('lane or bundle lease retained')
    for name,row in (telemetry.get('s6d') or {}).items():
        if name=='event_consumer':
            if row is None or row.get('depth')!=0:errors.append('S6D event consumer depth not zero')
        elif name in {'journal','punctuation','policy'} and row is not None:
            if row.get('error') or row.get('depth')!=0 or row.get('thread_alive') is not False or row.get('closed') is not True or row.get('accepted')!=row.get('completed'):
                errors.append('S6D worker not successfully drained: '+name)
    return errors


def execute_cell(engine,job,manifest,manifest_path,output,checkpoint=None):
    """Shared actual execution loop; fake engines can verify stop/drain without neural work."""
    job_id=job['job_id'];settings=job['settings']
    import psutil
    process=psutil.Process();stopped=threading.Event();observer_errors=[]
    sample_path=output/'resources.jsonl'
    def observe():
        last=time.perf_counter();last_progress=0.
        try:
            with sample_path.open('x',encoding='utf-8',buffering=1) as handle:
                while not stopped.is_set():
                    now=time.perf_counter();mem=process.memory_full_info();telemetry=engine.telemetry()
                    descendants=process.children(recursive=True)
                    payload={'monotonic_sec':now,'sampling_gap_sec':now-last,'rss':mem.rss,'uss':getattr(mem,'uss',None),
                        'cpu_percent':process.cpu_percent(),'threads':process.num_threads(),'telemetry':telemetry,
                        'process_tree_pids':[process.pid]+[p.pid for p in descendants],
                        'process_tree_rss':mem.rss+sum(p.memory_info().rss for p in descendants)}
                    handle.write(json.dumps(payload,allow_nan=False)+'\n');last=now
                    if now-last_progress>=5.:
                        progress={'schema':'s6d-native-progress.v1','job_id':job_id,'pid':process.pid,'process_create_time':process.create_time(),
                            'utc':datetime.now(timezone.utc).isoformat(),'stage':engine.state,'done_source_sec':telemetry.get('asr_cursor_sec',0.),
                            'total_source_sec':job['audio_duration_sec'],'source_admitted_sec':telemetry.get('source_duration_sec',0.),
                            'elapsed_sec':telemetry.get('elapsed_wall_sec'),'queues':telemetry.get('s6d'),
                            'error':None,'output':str(output)}
                        tmp=output/'progress.tmp';tmp.write_text(json.dumps(progress,allow_nan=False),encoding='utf-8')
                        os.replace(tmp,output/'progress.json');last_progress=now
                    stopped.wait(.25)
        except BaseException as exc:
            observer_errors.append(repr(exc))
    watcher=threading.Thread(target=observe,name='s6d-resource-observer',daemon=True);watcher.start()
    events=[];started=time.perf_counter();failure=None
    def checked_checkpoint():
        if checkpoint is not None:
            checkpoint(engine=engine,telemetry=engine.telemetry(),job=job,output=output)
    try:
        checked_checkpoint()
        session=engine.start_file(Path(job['audio']['path']),realtime=True)
        checked_checkpoint()
        with (output/'consumer_events.jsonl').open('x',encoding='utf-8',buffering=1) as handle:
            while True:
                checked_checkpoint()
                while not engine.events.empty():
                    event=engine.events.get();row=event.to_jsonable()
                    row['actual_consumed_monotonic_sec']=time.perf_counter()
                    handle.write(json.dumps(row)+'\n')
                    if event.event_type in {'s6d_text_ready','transcript_partial','transcript_final'}:
                        events.append(row)
                writer=engine._finalization_thread
                if writer is not None and not writer.is_alive() and engine.events.empty():
                    break
                if time.perf_counter()-started>manifest['limits']['cell_timeout_sec']:
                    engine.stop();raise TimeoutError('Predeclared native cell timeout')
                time.sleep(.01)
        engine.wait_for_completion(60.)
        errors=completion_errors(engine,engine.telemetry())
        if errors:raise RuntimeError('; '.join(errors))
        if settings:
            engine.record_s6d_consumer_closure('S6D native pilot actual event consumer')
    except BaseException as exc:
        failure=repr(exc)
        engine.stop()
        try:engine.wait_for_completion(60.)
        except Exception:pass
    finally:
        stopped.set();watcher.join(3.)
    if observer_errors:
        failure=failure or 'Resource observer failed: '+repr(observer_errors)
    if watcher.is_alive():
        failure=failure or 'Resource observer did not join'
    final_telemetry=engine.telemetry()
    drain_errors=completion_errors(engine,final_telemetry)
    if drain_errors:failure=failure or '; '.join(drain_errors)
    result={'schema':'s6d-native-cell.v1','status':'COMPLETE' if failure is None else 'FAILED','job':job,
        'manifest':bind(manifest_path),'helper':bind(__file__),'pid':os.getpid(),'process_create_time':process.create_time(),
        'elapsed_sec':time.perf_counter()-started,'failure':failure,'telemetry':final_telemetry,
        'resource_observer_closed':not watcher.is_alive(),'session_dir':str(engine.session_dir),
        'observer_errors':observer_errors,'completion_errors':drain_errors,
        'event_consumer_drained':engine.events.empty(),'first_text_records':events,
        'native_tested':failure is None,'gui_tested':False,'physical_tested':False,'cm5_tested':False}
    write(output/'RESULT.json',result)
    print(json.dumps({'status':result['status'],'result':bind(output/'RESULT.json'),'elapsed_sec':result['elapsed_sec']}))
    if failure:
        raise RuntimeError(failure)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('plan');p.add_argument('--directory',type=Path,required=True);p.add_argument('--payload',type=Path,required=True)
    p=commands.add_parser('run-one');p.add_argument('--manifest',type=Path,required=True);p.add_argument('--job-id',required=True)
    args=parser.parse_args()
    plan(args.directory,args.payload) if args.command=='plan' else run_one(args.manifest,args.job_id)
