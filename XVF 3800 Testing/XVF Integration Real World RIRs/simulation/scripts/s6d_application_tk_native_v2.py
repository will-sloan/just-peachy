"""Owned native/Tk multi-view harness; see README_S6D_APPLICATION_TK_NATIVE_V2.md."""
from __future__ import annotations
import argparse
from collections import deque
from copy import deepcopy
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import shutil
import sys
import threading
import time


def binding(path):
    path=Path(path).resolve();h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1048576),b''):h.update(part)
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':h.hexdigest()}


def read_bound(value):
    if binding(value['path'])!=value:raise ValueError('Changed bound file: '+value['path'])
    return json.loads(Path(value['path']).read_text(encoding='utf-8-sig'))


def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'


SEMANTIC=('utterance_id','text','display_text','label','known_profile_id','naming_state','visible','visibility_state','final','revision_count','source_start_sec','source_end_sec')


class CausalInbox:
    """Instrumented bounded inbox: retain every causal input instead of partial coalescing.

    Native GUI probes explicitly declare this additional load. The original app
    source and its ordinary inbox remain unchanged outside this owned harness.
    """
    def __init__(self,capacity,clock=time.perf_counter):
        self.capacity=capacity;self.rows=queue.Queue(capacity);self.clock=clock
        self.accepted=self.consumed=self.max_depth=0;self.max_age=0.;self.lock=threading.Lock()
    def put(self,event):
        with self.lock:
            try:self.rows.put_nowait((self.clock(),event))
            except queue.Full as exc:raise RuntimeError('Causal native inbox full; fail rather than omit an event') from exc
            self.accepted+=1;self.max_depth=max(self.max_depth,self.rows.qsize())
    def get(self,block=True,timeout=None):
        stamp,event=self.rows.get(block=block,timeout=timeout);now=self.clock()
        with self.lock:self.consumed+=1;self.max_age=max(self.max_age,now-stamp)
        event.payload['consumer_monotonic_sec']=now;event.payload['consumer_queue_age_sec']=now-stamp
        return event
    def empty(self):return self.rows.empty()
    def qsize(self):return self.rows.qsize()
    def snapshot(self):
        with self.lock:
            return dict(depth=self.rows.qsize(),capacity=self.capacity,accepted=self.accepted,consumed=self.consumed,
                coalesced_obsolete_ui_partials=0,max_depth=self.max_depth,max_age_sec=self.max_age,oldest_age_sec=None,
                instrumentation='every native event retained; ordinary app coalescing disabled only for this GUI probe')


class LiveFanout:
    """One causal dispatcher; independent presentation state and bounded inbox per view."""
    def __init__(self,views,event_factory,clock=time.perf_counter):
        self.views=views;self.event_factory=event_factory;self.clock=clock
        self.digest=hashlib.sha256();self.count=0;self.pending_t0=deque();self.t0_comparisons=0
        self.source_origin=None;self.last_sequence=0;self.terminal=False

    def accept(self,event):
        row=event.to_jsonable();kind=row['event_type'];p=row['payload'];stamp=p.get('publication_sequence')
        if type(stamp) is not int or stamp<=self.last_sequence:raise ValueError('Native publication sequence is not strictly increasing')
        self.last_sequence=stamp;raw=canonical(row);self.digest.update(raw);self.count+=1
        if kind=='source_started':
            if self.source_origin is not None:raise ValueError('Duplicate native source origin')
            self.source_origin=p['pilot_publication_monotonic_sec']
        if kind=='s6d_display':
            if not self.pending_t0:raise ValueError('Unmatched native T0 display')
            expected=self.pending_t0.popleft()
            if any(expected.get(k)!=p.get(k) for k in SEMANTIC):raise ValueError('Shared-stream T0 differs from actual engine T0 presentation')
            self.t0_comparisons+=1
        for view in self.views:
            view['input_digest'].update(raw);view['input_count']+=1
            shown=view['presentation'].consume(kind,deepcopy(p),now=self.clock())
            if kind!='s6d_display':
                view['inbox'].put(deepcopy(event));view['forwarded']+=1
            if shown is not None:
                if view['name']=='T0':
                    if len(self.pending_t0)>=4096:raise RuntimeError('Bounded T0 comparison backlog exhausted')
                    self.pending_t0.append(deepcopy(shown))
                shown.update(publication_monotonic_sec=self.clock(),session_id=p['session_id'],
                    source_native_publication_monotonic_sec=p['pilot_publication_monotonic_sec'],
                    source_native_publication_sequence=stamp,view_id=view['name'],
                    causal_view_input_count=view['input_count'])
                view['inbox'].put(self.event_factory('s6d_display',row['source_time_sec'],shown));view['forwarded']+=1
        return {**row,'actual_consumed_monotonic_sec':self.clock()}

    def complete(self):
        errors=[]
        if self.pending_t0:errors.append('Native T0 comparator has pending display rows')
        for v in self.views:
            snap=v['inbox'].snapshot()
            if v['input_count']!=self.count or v['input_digest'].hexdigest()!=self.digest.hexdigest():errors.append('View event-order binding differs: '+v['name'])
            if snap['depth'] or snap['consumed']+snap['coalesced_obsolete_ui_partials']!=v['forwarded']:errors.append('View inbox not fully consumed/coalesced: '+v['name'])
            if not v.get('consumer_closed'):errors.append('View did not close: '+v['name'])
        return errors


class ViewFacade:
    def __init__(self,engine,view,fanout):self.actual=engine;self.view=view;self.fanout=fanout;self._s6d=view['settings'];self.events=view['inbox']
    def __getattr__(self,name):
        if name=='_finalization_thread':
            writer=self.actual._finalization_thread
            if writer is None:return None
            outer=self
            class ClosureGate:
                def is_alive(self):return not outer.fanout.terminal or writer.is_alive()
            return ClosureGate()
        return getattr(self.actual,name)
    def record_s6d_consumer_closure(self,consumer):
        if self.fanout.terminal and self.events.empty():self.view['consumer_closed']=True


class GalleryScoreSpy:
    """Observe each actual gallery.score invocation without changing its output."""
    def __init__(self,gallery,capacity=16384,clock=time.perf_counter):
        self.gallery=gallery;self.capacity=capacity;self.clock=clock;self.rows=[];self.original=gallery.score;self.lock=threading.Lock()
    def score(self,vector):
        started=self.clock();scores=self.original(vector);finished=self.clock()
        with self.lock:
            if len(self.rows)>=self.capacity:raise RuntimeError('Gallery observation capacity exhausted')
            self.rows.append(dict(query_index=len(self.rows)+1,started_monotonic_sec=started,finished_monotonic_sec=finished,
                vector_sha256=hashlib.sha256(vector.tobytes()).hexdigest(),scores=deepcopy(scores)))
        return scores
    def install(self):self.gallery.score=self.score
    def restore(self):self.gallery.score=self.original


def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def run_one(manifest_path,job_id,checkpoint=None):
    """Supervisor entry. No device playback; Tk belongs only to this new worker process."""
    manifest_bound=binding(manifest_path);manifest=read_bound(manifest_bound)
    if manifest['helper']!=binding(__file__):raise ValueError('Execute the exact frozen GUI helper')
    job=next(j for j in manifest['jobs'] if j['job_id']==job_id)
    for b in manifest['execution_files']+manifest['support_files']:
        if binding(b['path'])!=b:raise ValueError('Execution source changed')
    if read_bound(job['profile_binding'])!=job['profile']:raise ValueError('Inline profile differs')
    if job['gallery']:read_bound(job['gallery'])
    for drive,minimum in [('C:/',50),('G:/',75)]:
        if shutil.disk_usage(drive).free<minimum*1024**3:raise RuntimeError('Disk floor not satisfied')
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    sys.dont_write_bytecode=True;sys.path.insert(0,manifest['source_root'])
    cfg=importlib.import_module('edge_speech_pipeline.config');profiles=importlib.import_module('edge_speech_pipeline.research_profiles')
    runtime=importlib.import_module('edge_speech_pipeline.runtime');s6d=importlib.import_module('edge_speech_pipeline.research_s6d');gui=importlib.import_module('edge_speech_pipeline.gui');contracts=importlib.import_module('edge_speech_pipeline.contracts')
    for module in (cfg,profiles,runtime,s6d,gui,contracts):
        if Path(module.__file__).resolve().parent!=Path(manifest['source_root'])/'edge_speech_pipeline':raise ValueError('Wrong imported source epoch')
    evidence=load_module(manifest['evidence_helper']['path'],'s6d_tk_evidence')
    sourceproof=evidence.pcm_proof(job['audio']['path'],job['audio'])
    if job.get('expected_identity_frames')!=job['expected_frames'] or sourceproof['frames']!=job['expected_frames'] or sourceproof['sha256']!=job['audio_pcm_sha256']:raise ValueError('Source PCM differs')
    import psutil
    process=psutil.Process();allowed=process.cpu_affinity();cpus=manifest['limits'].get('cpu_affinity')
    if not isinstance(cpus,list) or not 1<=len(cpus)<=4 or len(set(cpus))!=len(cpus) or any(type(x) is not int or x not in allowed for x in cpus):raise ValueError('Root-bound available affinity of1..4 CPUs required')
    process.cpu_affinity(cpus)
    output=Path(job['output']);output.mkdir(parents=True,exist_ok=False)
    base=cfg.PipelineConfig(assets=tuple(cfg.AssetSpec(x['component_id'],Path(x['path']),x['sha256'],x['deployment_relative_path']) for x in manifest['assets']),session_root=output/'sessions',profile_root=output/'empty_private_profiles')
    profile=profiles.ResearchProfile.from_dict(job['profile'])
    if any(getattr(profile.apply(base),k)!=1 for k in ('asr_threads','speaker_threads','punctuation_threads')):raise ValueError('Single inner pools required')
    class Engine(runtime.PipelineEngine):
        def _emit(self,event_type,source_sec,payload):
            if self._s6d is not None and not isinstance(self.events,CausalInbox):
                if not self.events.empty():raise RuntimeError('Causal observer must install before first session event')
                self.events=CausalInbox(self._s6d.queue_capacity)
            return super()._emit(event_type,source_sec,{**payload,'pilot_publication_monotonic_sec':time.perf_counter()})
    engine=Engine(base,research_profile=profile,research_gallery=job['gallery']['path'] if job['gallery'] else None,s6d_settings=s6d.S6DSettings(**job['settings']))
    return execute_gui(engine,job,manifest,manifest_bound,output,sourceproof,evidence,s6d,gui,contracts.PipelineEvent,checkpoint,process)


def execute_gui(engine,job,manifest,manifest_bound,output,sourceproof,evidence,s6d,gui,event_factory,checkpoint,process):
    import tkinter as tk
    views=[]
    for entry in job['views']:
        settings=s6d.S6DSettings(**entry['settings']).validate()
        views.append(dict(name=entry['name'],settings=settings,presentation=s6d.PresentationState(settings),inbox=s6d.EventInbox(settings.queue_capacity),input_digest=hashlib.sha256(),input_count=0,forwarded=0,consumer_closed=False))
    fanout=LiveFanout(views,event_factory);failures=[];startup_done=threading.Event();observer_stop=threading.Event();observer_errors=[];windows=[]
    origin=time.perf_counter();root=None;consumer=None;spy=None;setup_error=None
    closing=threading.Event();cleanup_errors=[];cleanup_steps=[]
    def fail(exc):
        if not failures:failures.append(repr(exc))
        engine.stop()
    class Window(gui.EdgeSpeechWindow):
        def _refresh_devices(self):self.devices=[]
        def _refresh_profiles(self):pass
        def _run_background(self,*a,**kw):raise RuntimeError('Harness owns startup; interactive work disabled')
        def _close(self):fail(RuntimeError('Owned GUI close requested before completion'))
        def _record_s6d_gui(self,row):
            if self._s6d_render_handle is None:
                path=output/'views'/self.engine.view['name'];path.mkdir(parents=True,exist_ok=True)
                self._s6d_render_handle=(path/'s6d_gui_render.jsonl').open('x',encoding='utf-8',buffering=1)
            trigger={}
            if 'utterance_id' in row:
                payload=self.s6d_rows[row['utterance_id']]
                fields=('session_id','source_native_publication_sequence','source_native_publication_monotonic_sec','causal_view_input_count')
                if any(payload.get(k) is None for k in fields):raise ValueError('Rendered utterance lacks exact native trigger metadata')
                trigger={k:payload[k] for k in fields}
                trigger.update(display_payload=dict(payload),causal_input_count=payload['causal_view_input_count'])
            widget_text=self.transcript.get('1.0','end-1c')
            row={**row,**trigger,'view_id':self.engine.view['name'],'source_started_monotonic_sec':fanout.source_origin,
                'actual_callback_monotonic_sec':time.perf_counter(),'widget_text':widget_text,
                'widget_text_sha256':hashlib.sha256(widget_text.encode()).hexdigest(),
                'clock_scope':'owned actual Tk command/callback; no physical scanout',
                'dispatcher_frontier_input_count':self.engine.view['input_count']}
            self._s6d_render_handle.write(json.dumps(row,allow_nan=False)+'\n')
    def checked():
        if checkpoint:checkpoint(engine=engine,telemetry=engine.telemetry(),job=job,output=output)
    def startup():
        try:
            checked()
            if closing.is_set():raise RuntimeError('Owned GUI closed before startup')
            engine.start_file(Path(job['audio']['path']),realtime=True)
            if closing.is_set():raise RuntimeError('Owned GUI closed during startup')
            checked()
        except BaseException as exc:fail(exc)
        finally:startup_done.set()
    def observe():
        last=time.perf_counter();last_progress=0.
        try:
            with (output/'resources.jsonl').open('x',encoding='utf-8',buffering=1) as f:
                while not observer_stop.is_set():
                    now=time.perf_counter();mem=process.memory_full_info();tel=engine.telemetry()
                    f.write(json.dumps(dict(monotonic_sec=now,sampling_gap_sec=now-last,rss=mem.rss,uss=getattr(mem,'uss',None),cpu_percent=process.cpu_percent(),threads=process.num_threads(),telemetry=tel,view_queues={v['name']:v['inbox'].snapshot() for v in views}),allow_nan=False)+'\n');last=now
                    if now-last_progress>=5:
                        progress=dict(schema='s6d-native-progress.v1',job_id=job['job_id'],pid=process.pid,process_create_time=process.create_time(),stage=engine.state,done_source_sec=tel.get('asr_cursor_sec',0.),total_source_sec=job['audio_duration_sec'],source_admitted_sec=tel.get('source_duration_sec',0.),output=str(output))
                        temp=output/'progress.tmp';temp.write_text(json.dumps(progress),encoding='utf-8');os.replace(temp,output/'progress.json');last_progress=now
                    observer_stop.wait(.25)
        except BaseException as exc:observer_errors.append(repr(exc));fail(exc)
    starter=threading.Thread(target=startup,name='s6d-owned-tk-start',daemon=True);watcher=threading.Thread(target=observe,name='s6d-owned-tk-resources',daemon=True)
    def pump():
        try:
            if not failures:checked()
            # Bound callback work; all committed events remain in the bounded native queue/journal.
            for _ in range(256):
                if engine.events.empty():break
                row=fanout.accept(engine.events.get());consumer.write(json.dumps(row,allow_nan=False)+'\n')
            writer=engine._finalization_thread
            ended=startup_done.is_set() and writer is not None and not writer.is_alive() and engine.events.empty()
            if ended:fanout.terminal=True
            if ended and all(v['consumer_closed'] and v['inbox'].empty() for v in views):root.quit();return
            if startup_done.is_set() and writer is None and failures:root.quit();return
            elapsed=time.perf_counter()-origin
            if elapsed>manifest['limits']['cell_timeout_sec']:fail(TimeoutError('Declared GUI native deadline'))
            if elapsed>manifest['limits']['cell_timeout_sec']+75:root.quit();return
        except BaseException as exc:fail(exc)
        root.after(10,pump)
    def cleanup(label,action):
        try:action();cleanup_steps.append(dict(resource=label,closed=True))
        except BaseException as exc:cleanup_errors.append(dict(resource=label,error=repr(exc)))
    try:
        root=tk.Tk()
        consumer=(output/'consumer_events.jsonl').open('x',encoding='utf-8',buffering=1)
        spy=GalleryScoreSpy(engine._research_gallery) if engine._research_gallery is not None else None
        if spy:spy.install()
        for i,v in enumerate(views):
            surface=root if i==0 else tk.Toplevel(root)
            # Retain the object before __init__ so partial constructor resources are owned.
            w=Window.__new__(Window);windows.append(w)
            Window.__init__(w,surface,engine.config,engine=ViewFacade(engine,v,fanout))
            surface.title('S6D native view '+v['name'])
        root.report_callback_exception=lambda *exc:fail(RuntimeError('Tk callback failed: '+repr(exc)))
        watcher.start();starter.start();root.after(0,pump);root.mainloop()
    except BaseException as exc:
        setup_error=repr(exc)
        raise
    finally:
        closing.set();observer_stop.set()
        if not fanout.terminal:cleanup('engine_stop',engine.stop)
        if starter.ident is not None:cleanup('startup_join',lambda:starter.join(3))
        # A start already in progress can become active after the first stop.
        if not fanout.terminal and starter.ident is not None:cleanup('engine_stop_after_startup',engine.stop)
        if watcher.ident is not None:cleanup('observer_join',lambda:watcher.join(3))
        if consumer is not None:cleanup('consumer_file',consumer.close)
        render_handles=[]
        for i,w in enumerate(windows):
            handle=getattr(w,'_s6d_render_handle',None)
            if handle is not None:
                render_handles.append(handle);cleanup('view_render_file_'+str(i),handle.close)
                if handle.closed:w._s6d_render_handle=None
        if root is not None:cleanup('tk_root',root.destroy)
        if spy is not None:cleanup('gallery_spy',spy.restore)
        closure=dict(schema='s6d-owned-gui-resource-closure.v2',setup_or_loop_error=setup_error,
            root_acquired=root is not None,root_destroyed=any(x['resource']=='tk_root' for x in cleanup_steps),
            consumer_acquired=consumer is not None,consumer_closed=consumer is None or consumer.closed,
            gallery_spy_acquired=spy is not None,gallery_spy_restored=spy is None or any(x['resource']=='gallery_spy' for x in cleanup_steps),
            render_files_closed=all(h.closed for h in render_handles),startup_thread_started=starter.ident is not None,
            startup_thread_alive=starter.is_alive(),observer_thread_started=watcher.ident is not None,
            observer_thread_alive=watcher.is_alive(),cleanup_steps=cleanup_steps,cleanup_errors=cleanup_errors,
            no_session_completion_claim=True)
        closure['resources_closed']=not cleanup_errors and not starter.is_alive() and not watcher.is_alive() and closure['consumer_closed'] and closure['render_files_closed']
        try:write_new(output/'OWNED_RESOURCE_CLOSURE.json',closure)
        except BaseException as exc:
            cleanup_errors.append(dict(resource='cleanup_receipt',error=repr(exc)))
            if setup_error is None:raise
        failures.extend('Owned resource cleanup failed: '+repr(x) for x in cleanup_errors)
    if spy:write_new(output/'actual_gallery_queries.json',dict(gallery=job['gallery'],actual_score_calls=len(spy.rows),queries=spy.rows,selection_consumers_issued_queries=False,call_scope='Each actual gallery.score invocation; center and current vectors may produce two calls per identity query'))
    errors=fanout.complete()
    if starter.is_alive():errors.append('Startup worker not joined')
    if watcher.is_alive() or observer_errors:errors.append('Resource observer not closed cleanly')
    if errors:failures.extend(errors)
    if not failures:
        engine.wait_for_completion(60.);engine.record_s6d_consumer_closure('Owned Tk live causal views: all view queues drained')
    result=dict(schema='s6d-native-cell.v1',status='COMPLETE' if not failures else 'FAILED',failure='; '.join(failures) if failures else None,job=job,manifest=manifest_bound,helper=binding(__file__),pid=process.pid,process_create_time=process.create_time(),telemetry=engine.telemetry(),elapsed_sec=time.perf_counter()-origin,resource_observer_closed=not watcher.is_alive(),observer_errors=observer_errors,owned_resource_closure=binding(output/'OWNED_RESOURCE_CLOSURE.json'),completion_errors=errors,event_consumer_drained=engine.events.empty(),session_dir=str(engine.session_dir),native_tested=not failures,gui_tested=not failures,physical_tested=False,cm5_tested=False,source_event_count=fanout.count,source_event_order_sha256=fanout.digest.hexdigest(),native_T0_semantic_comparisons=fanout.t0_comparisons,views=[dict(name=v['name'],input_count=v['input_count'],input_order_sha256=v['input_digest'].hexdigest(),forwarded=v['forwarded'],queue=v['inbox'].snapshot(),consumer_closed=v['consumer_closed']) for v in views],capability_scope='online causal presentation views over one actual native stream; actual Tk widget commands, not independent T1/T2 engine runs or physical scanout')
    if not failures:
        session=engine.session_dir
        final=json.loads((session/'session_finalization_v3.json').read_text());closure=json.loads((session/'s6d_consumer_closure.json').read_text())
        proofs=dict(source=sourceproof,asr=binding(session/'audio_spool.pcm16'),identity=binding(session/'identity_audio_spool.pcm16'))
        errors=evidence.validate_completion(result,job,final,proofs,closure)
        try:result['dispatch_proof']=evidence.validate_dispatch(evidence.stream(output/'consumer_events.jsonl'),job['expected_frames'])
        except BaseException as exc:errors.append(repr(exc))
        if errors:result.update(status='FAILED',failure='; '.join(errors),completion_errors=errors,native_tested=False,gui_tested=False)
    write_new(output/'RESULT.json',result)
    if result['failure']:raise RuntimeError(result['failure'])
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--job-id',required=True)
    a=p.parse_args();run_one(a.manifest,a.job_id)
