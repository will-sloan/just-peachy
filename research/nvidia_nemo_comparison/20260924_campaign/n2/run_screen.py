"""Checkpointed real Windows Controller factorial screen. See README.md."""
from __future__ import annotations
import argparse
from dataclasses import replace
from datetime import datetime,timezone
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import traceback
import uuid

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'data'))
from run_baseline_screen import digest,stable_hash,source_bindings,bounded_commands,binding
from configure import configure
from io_utils import atomic,IO_VERSION


class Recorder:
    """Ordered bounded audit delivery off the ASR and speaker producer threads."""
    def __init__(self,directory,session_id,encoder,gallery_index=None):
        self.directory=directory;self.session_id=session_id;self.error=None;self.max_depth=0
        self.accepted=self.completed=0;self.queue=queue.Queue(4096);self.observer=None
        if gallery_index:
            sys.path.insert(0,str(HERE/'evaluation'))
            from runtime_observer import RuntimeGalleryObserver
            self.observer=RuntimeGalleryObserver(encoder,gallery_index,directory/'galleries',session_id)
        self.thread=threading.Thread(target=self._run,name='n2-evaluation-recorder',daemon=True)
        self.thread.start()

    def event(self,kind,source,payload):
        wanted={'n2_diarization_binding','n2_diarization_frames','research_embedding',
            'research_embedding_admission','research_segmentation','speaker_decision','identity_decision',
            's6d_text_ready','s6d_display','transcript_partial','transcript_final','transcript_label_revision',
            's6d_punctuation_revision','research_asr_dispatch','research_asr_tail_dispatch','research_asr_reset',
            'research_asr_drain','n2_window_admission','n2_exclusive_run_coverage','source_started','fatal','failure'}
        if kind not in wanted:return
        if self.error:raise RuntimeError('Evaluation recorder failed: '+self.error)
        try:self.queue.put_nowait((kind,source,deepcopy(payload)))
        except queue.Full as exc:raise RuntimeError('Bounded evaluation recorder exhausted') from exc
        self.accepted+=1;self.max_depth=max(self.max_depth,self.queue.qsize())

    def _run(self):
        try:
            with (self.directory/'RUNTIME_EVENTS.jsonl').open('x',encoding='utf-8',buffering=65536) as stream:
                while True:
                    item=self.queue.get()
                    try:
                        if item is None:break
                        kind,source,payload=item
                        stream.write(json.dumps(dict(event_type=kind,source_sec=source,payload=payload),allow_nan=False,separators=(',',':'))+'\n')
                        if self.observer:self.observer.event(kind,source,payload)
                        self.completed+=1
                    finally:self.queue.task_done()
        except BaseException as exc:self.error=repr(exc)

    def finish(self,rows):
        self.queue.put(None,timeout=10);self.thread.join(60)
        if self.thread.is_alive() or self.error or self.accepted!=self.completed:
            raise RuntimeError('Recorder failed to drain: '+str(self.error))
        result=dict(accepted=self.accepted,completed=self.completed,max_depth=self.max_depth)
        if self.observer:result['galleries']=self.observer.finish(rows)
        return result


def run(args):
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='' if args.device=='cpu' else '0'
    import psutil
    process=psutil.Process()
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    process.cpu_affinity([args.cpu])
    source=args.source.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    if output==source or source in output.parents:raise ValueError('Private output must be outside application source')
    sys.path[:0]=[str(source),str(source/'vendor')]
    from app.controller import Controller
    from app.backends import backend_catalog
    from app.pipeline import ResidentModels
    from app.n2_models import N2ResidentModels
    from app.n2_identity import N2Gallery
    from app.paths import atomic_json
    sys.path.insert(0,str(HERE.parent/'supervision'))
    from supervisor import lock,disk_reserves,read
    with lock(output/'runner.lock'):
        manifest=json.loads(args.manifest.read_text())
        frozen=source_bindings(source)
        runtime_binding=json.loads(configure(output/'runtime-binding',args.local,args.device).read_text())
        settings=dict(schema='n2-controller-screen-v1',combination=args.combination,profile=args.profile,
            source_bindings=frozen,manifest=binding(args.manifest),runtime=sys.version,
            saved_audio_only=True,threads=dict(asr=1,speaker=1,punctuation=1),gain=1.,
            source_delivery='absolute source speed',independent_scene_state=True,
            labels='anonymous main frontend plus online matched gallery observers' if args.galleries else 'no gallery',
            galleries=binding(args.galleries) if args.galleries else None,runner_sha256=digest(__file__),
            setup_sha256=digest(HERE/'configure.py'),runtime_binding=runtime_binding,
            observer_sha256=digest(HERE/'evaluation/runtime_observer.py'),
            helper_sha256=digest(HERE.parent/'data/run_baseline_screen.py'),
            native_device=runtime_binding['native_device'],io_version=IO_VERSION,io_helper_sha256=digest(HERE/'io_utils.py'),
            supervisor_sha256=digest(HERE.parent/'supervision/supervisor.py'))
        contract=stable_hash(settings);admission=output/'ADMISSION.json'
        if admission.exists() and json.loads(admission.read_text())['contract_sha256']!=contract:
            raise ValueError('Output admission changed; use a new output directory')
        atomic(admission,dict(contract_sha256=contract,contract=settings))
        complete={};failed={};started=time.perf_counter();resident=None;unsafe_cleanup=False
        for job in manifest['jobs'][:args.limit or None]:
            allowed={'job_id','audio_path','audio_sha256','frames','sample_rate_hz','gain','reset_between_scenes','tap'}
            if set(job)!=allowed or job['gain']!=1 or job['sample_rate_hz']!=16000 or not job['reset_between_scenes']:
                raise ValueError('Audio-only runtime firewall failed')
            if not all(c.isalnum() or c in '_-' for c in job['job_id']):raise ValueError('Unsafe job ID')
            key=stable_hash(dict(contract=contract,job=job));cell=output/'cells'/job['job_id']
            checkpoint=cell/'CHECKPOINT.json'
            if checkpoint.exists():
                previous=json.loads(checkpoint.read_text())
                if previous['cache_key']!=key:raise ValueError('Cell key changed')
                if previous['status']=='COMPLETE':
                    if digest(previous['result']['path'])!=previous['result']['sha256']:raise ValueError('Result changed')
                    cached=json.loads(Path(previous['result']['path']).read_text())
                    for evidence in cached.get('evidence',[]):
                        path=Path(evidence['path'])
                        if path.stat().st_size!=evidence['bytes'] or digest(path)!=evidence['sha256']:
                            raise ValueError('Completed cell evidence changed: '+str(path))
                    complete[job['job_id']]=previous['result']['path'];continue
                if not args.retry_failed:failed[job['job_id']]=previous['result']['path'];continue
            attempt=cell/('attempt_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:6])
            attempt.mkdir(parents=True)
            c=None;engine=None;recorder=None;cell_started=time.perf_counter();cpu_start=sum(process.cpu_times()[:2]);samples=[]
            result=dict(job_id=job['job_id'],combination=args.combination,profile=args.profile,status='FAILED',cache_key=key,
                attempt=str(attempt),audio=job,physical_latency='NOT_MEASURED',native_device=runtime_binding['native_device'],
                resource_scope='Windows '+args.device+' screening process; not isolated, Pi or total 2GB system qualification')
            try:
                _,low=disk_reserves(read(args.local.parent/'supervision/campaign.json'))
                if low:raise RuntimeError('Disk reserve breached: '+str(low))
                if digest(job['audio_path'])!=job['audio_sha256']:raise ValueError('Audio changed')
                if source_bindings(source)!=frozen:raise ValueError('Source changed during run')
                runtime=configure(attempt/'data',args.local,args.device)
                document=json.loads(runtime.read_text());document['streaming_profile']=args.profile
                atomic_json(runtime,document)
                c=Controller(attempt/'data',args.models,saved_audio_only=True)
                c.config=replace(c.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
                D,E=args.combination.split('_')
                if args.combination!='D0_E0':
                    wanted={('D1','E0'):'nemotron_hybrid',('D0','E1'):'titanet',('D1','E1'):'nemotron_titanet'}[(D,E)]
                    c.select_backend(next(row['id'] for row in backend_catalog() if row['key']==wanted));bounded_commands(c)
                    c.models.document['streaming_profile']=args.profile
                else:
                    # Original native D0/E0 models, tracker and window admission;
                    # N2 wrapper only attaches the declared evaluation observer.
                    c._n2_components=dict(diarization='D0',embedding='E0')
                if resident is None:resident=c.models
                else:c.models=resident
                def factory(session_id):
                    nonlocal recorder
                    recorder=Recorder(attempt,session_id,E,args.galleries)
                    return recorder
                c.n2_observer_factory=factory
                c.switch(mode='anonymous_conversation',recipe='balanced',tap=job['tap'],strict=False);bounded_commands(c)
                c.start_file(job['audio_path']);bounded_commands(c);engine=c.engine
                (engine.session_dir/'PINNED').touch()
                last=-10.
                while c.state in ('RUNNING','STARTING','STOPPING'):
                    elapsed=time.perf_counter()-cell_started
                    if elapsed>job['frames']/16000*8+180:raise TimeoutError('Controller cell exceeded timeout')
                    if elapsed-last>=2.:
                        last=elapsed;samples.append(dict(elapsed_sec=elapsed,rss_bytes=process.memory_info().rss,
                            cpu_seconds=sum(process.cpu_times()[:2])-cpu_start,source_samples=engine._journal.committed_samples))
                        atomic(output/'PROGRESS.json',dict(status='RUNNING',completed=len(complete),failed=len(failed),total=len(manifest['jobs']),
                            active=job['job_id'],elapsed_seconds=time.perf_counter()-started,pid=os.getpid()))
                    time.sleep(.1)
                snapshot=c.snapshot();rows=snapshot['rows']
                recorder_receipt=recorder.finish(rows);recorder=None
                archive=getattr(engine,'archive',None)
                archive_receipt=archive.snapshot() if archive is not None else None
                if archive_receipt is not None:
                    archive_receipt.update(accepted_items=archive.accepted,completed_items=archive.completed)
                checks=dict(stopped=c.state=='STOPPED',no_error=not c.error,
                    all_samples=engine._journal.committed_samples==job['frames'],
                    drained=all(w.accepted==w.completed and not w.error for w in engine.text_writers),
                    archive_complete=bool(archive_receipt and not archive_receipt['archive_error'] and not archive_receipt['loss']
                        and archive_receipt['closed'] and not archive_receipt['worker_alive']
                        and archive_receipt['source_samples']==job['frames']
                        and archive_receipt['accepted_items']==archive_receipt['completed_items']
                        and archive_receipt['queue_items']==0 and archive_receipt['queue_bytes']==0))
                atomic(attempt/'FINAL_SNAPSHOT.json',snapshot);atomic(attempt/'PROCESS_SAMPLES.json',samples)
                result.update(status='COMPLETE' if all(checks.values()) else 'FAILED',checks=checks,error=c.error,
                    rows=len(rows),session=str(engine.session_dir),telemetry=engine.telemetry(),recorder=recorder_receipt,archive=archive_receipt,
                    peak_sampled_rss_bytes=max((r['rss_bytes'] for r in samples),default=None),
                    cpu_seconds=sum(process.cpu_times()[:2])-cpu_start)
            except BaseException as exc:result.update(error=repr(exc),traceback=traceback.format_exc())
            finally:
                if c is not None:
                    if result['status']=='COMPLETE':
                        # Completed producer/consumer drainage is checked above.
                        # Retain immutable weights only; every next scene creates
                        # a new engine/Sherpa stream/Nemotron stream and gallery.
                        c.models=ResidentModels()
                    try:
                        c.close();deadline=time.monotonic()+130
                        while c.commands.unfinished_tasks:
                            if time.monotonic()>deadline:raise TimeoutError('Controller close command did not finish')
                            time.sleep(.05)
                        c.worker.join(10)
                        if not c.closed or c.worker.is_alive():raise RuntimeError('Controller did not release its owned lanes')
                    except BaseException as exc:
                        unsafe_cleanup=True
                        result.update(status='FAILED',cleanup_error=repr(exc),ownership_retained_until_process_exit=True)
                    if result['status']!='COMPLETE' and not unsafe_cleanup:
                        if hasattr(resident,'close'):resident.close()
                        resident=None
                if recorder is not None and not unsafe_cleanup:
                    try:recorder.finish([])
                    except BaseException as exc:result['recorder_error']=repr(exc)
                result['elapsed_seconds']=time.perf_counter()-cell_started
                result['evidence']=[] if unsafe_cleanup else [binding(p) for p in attempt.rglob('*.json*') if p!=attempt/'RESULT.json']
                atomic(attempt/'RESULT.json',result)
                atomic(checkpoint,dict(status=result['status'],cache_key=key,result=binding(attempt/'RESULT.json')))
            (complete if result['status']=='COMPLETE' else failed)[job['job_id']]=str(attempt/'RESULT.json')
            if unsafe_cleanup or result['status']!='COMPLETE' and args.stop_on_failure:break
        status='COMPLETE' if len(complete)==len(manifest['jobs']) and not failed else 'FAILED' if failed else 'PARTIAL'
        if not unsafe_cleanup and hasattr(resident,'close'):resident.close()
        index=dict(status=status,completed=complete,failed=failed,total=len(manifest['jobs']),elapsed_seconds=time.perf_counter()-started,contract_sha256=contract)
        atomic(output/'RESULT_INDEX.json',index)
        atomic(output/'PROGRESS.json',dict(index,completed=len(complete),failed=len(failed)))
        print(json.dumps(dict(status=status,completed=len(complete),failed=len(failed),output=str(output))))
        return int(bool(failed))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--galleries',type=Path)
    parser.add_argument('--combination',choices=['D0_E0','D1_E0','D0_E1','D1_E1'],required=True)
    parser.add_argument('--profile',choices=['low_latency','very_low_latency','ultra_low_latency'],default='low_latency')
    parser.add_argument('--models',type=Path,default=Path('C:/Users/amiri/JustPeachy/shared/models'))
    parser.add_argument('--local',type=Path,default=Path('G:/Just_Peachy_N1/20260924_campaign/local/n2'))
    parser.add_argument('--cpu',type=int,default=6);parser.add_argument('--limit',type=int)
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    parser.add_argument('--retry-failed',action='store_true');parser.add_argument('--stop-on-failure',action='store_true')
    raise SystemExit(run(parser.parse_args()))
