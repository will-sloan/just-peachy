"""Actual application publication methods under a modeled clock. README_APPLICATION_PUBLICATION.md."""
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

from common import load,verify
from component_s7_replay import ReplayClock,causal_commands,drain,CONTRACT
from component_d1_replay import d1_plan,QueryJournal,CooperativeActivity
from mode_galleries import backend_contract,load_prepared_gallery
from controller_projection import forbid_inference

_CLOCK_OWNER=threading.Lock()


class ModuleClock:
    """Replace two module-local references, never the system/global time object."""
    def __init__(self,clock):self.perf_counter=clock
    def __getattr__(self,name):return getattr(time,name)


class ModeledSourceCursor:
    """Declared 100-ms source-speed delivery, including the exact final tail."""
    def __init__(self,clock,duration):self.clock=clock;self.duration=duration
    @property
    def duration_sec(self):
        now=self.clock()
        return self.duration if now>=self.duration else math.floor(now*10+1e-9)/10


class PublicationInbox:
    """Bounded synchronous observer at the actual PipelineEngine event put seam."""
    def __init__(self,owner):self.owner=owner;self.rows=[];self.bytes=0
    def put(self,event):
        p=deepcopy(event.payload);o=self.owner
        if (p['publication_sequence']!=len(self.rows)+1 or p['publication_monotonic_sec']!=o.clock()
                or p['session_id']!=o.session_id or p['publication_source_cursor_sec']>min(o.clock(),o.duration)):
            raise ValueError('Actual publication sequence, clock or session differs')
        row=dict(event_type=event.event_type,source_time_sec=event.source_time_sec,payload=p)
        self.bytes+=len(json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode())
        if len(self.rows)>=100000 or self.bytes>24*1024**2:raise ValueError('Publication trace budget exceeded')
        self.rows.append(row)
        if event.event_type=='s6d_display':
            state=next(r for r in o.engine._s6d_presentation.snapshot_rows() if r['caption_key']==p['caption_key'])
            if state['text']!=p['text']:raise ValueError('Actual display annotation changed raw words')
            o.displays.append(dict(event_type='s6d_display',modeled_at_sec=o.clock(),state_row=state,
                published_row=p,physical_widget_observed=False))


class PublicationReplay:
    """Real constructor/begin routing and emit chain; no session I/O or models.

    The sole suppressed instance method is _begin_session, whose model/file
    startup is outside this cached-method scope. The actual begin, transcript,
    scheduled-event, watermark, punctuation and all inherited emit methods run.
    """
    def __init__(self,*,duration,preparation,backend,mode,tap,namespace,session_id):
        if not math.isfinite(duration) or not 0<duration<=120 or not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}',session_id):
            raise ValueError('Finite independent scene and safe session identifier required')
        self.stack=ExitStack();self.closed=False;self.engine=None;self.displays=[];self.finals={};self.last={};self.formatted=set()
        if not _CLOCK_OWNER.acquire(blocking=False):raise RuntimeError('One publication clock owner per process')
        self.stack.callback(_CLOCK_OWNER.release)
        try:
            from app.pipeline import PrototypeEngine,effective_profile
            from app.n2_pipeline import N2Engine
            from app.n3_pipeline import N3IdentityEngine
            from app.paths import pipeline_config
            from edge_speech_pipeline import runtime,research_s7_presentation
            from edge_speech_pipeline.research_s7_policy import ObservedClock
            from edge_speech_pipeline.research_s6d import build_s6d_scheduler,build_presentation_state
            verify(preparation);prepared=load(preparation['path']);verify(prepared['catalog'])
            self.contract=backend_contract(load(prepared['catalog']['path']),backend,mode)
            expected=prepared['encoders'][self.contract['encoder']]['conditions'][self.contract['gallery_condition']]['namespace']
            if namespace!=expected:raise ValueError('Component encoder namespace differs')
            self.gallery,self.condition=load_prepared_gallery(preparation,self.contract)
            self.clock=ReplayClock();self.duration=duration;self.session_id=session_id
            self.stack.enter_context(forbid_inference())
            for module in (runtime,research_s7_presentation):
                self.stack.enter_context(patch.object(module,'time',ModuleClock(self.clock)))
            observed=ObservedClock(clock=self.clock);observed.set_origin(0.)
            self.profile=effective_profile('balanced',mode,tap)
            base={'PrototypeEngine':PrototypeEngine,'N2Engine':N2Engine,'N3IdentityEngine':N3IdentityEngine}[self.contract['engine']]
            # Constructor only needs these namespace metadata fields. No model API exists.
            metadata=SimpleNamespace(embedding=self.contract['encoder'],document={'embedding_namespace':namespace})
            kwargs=dict(diarization=self.contract['diarization']) if self.contract['uses_n2'] else {}
            engine=base(pipeline_config(Path('N4_METADATA_ONLY'),Path('NO_MODEL_PAYLOAD')),metadata,self.profile,self.gallery,mode,**kwargs)
            self.engine=engine;engine._session_dir=Path(session_id);engine._s7_observed_clock=observed
            engine._journal=ModeledSourceCursor(self.clock,duration);engine._started_monotonic=0.
            engine._s6d_presentation=build_presentation_state(engine._s6d,s7=dict(mode=self.contract['presentation_mode'],
                session_id=session_id,ownership_mode='timestamped_spans_v3'))
            self.inbox=PublicationInbox(self);engine.events=self.inbox
            engine._scheduler=build_s6d_scheduler(self.profile,self.gallery,None,engine._scheduled_event,engine._s6d,observed_clock=observed)
            def skip_session_io(kind):
                if kind!='prototype':raise ValueError('Unexpected session kind')
            engine._begin_session=skip_session_io
            engine.begin()
            self.startup_events=len(self.inbox.rows)
        except BaseException:
            self.close();raise

    def text(self,event):
        e=self.engine;uid=event['utterance_id']
        if uid in self.finals or event['event_id']!=f'asr:{e._research_asr_event_serial+1:08d}' or not re.fullmatch(r'utterance:\d{6}',uid):
            raise ValueError('Unexpected raw observation serial/utterance/finality')
        if event['available_at_sec']!=self.clock():raise ValueError('Raw observation not at its admitted modeled completion')
        e._research_utterance_start_sec=event['source_start_sec'];e._research_asr_available_sec=event['available_at_sec']
        offset=len(self.inbox.rows)
        e._transcript_event(event['text'],event['source_end_sec'],final=event['final'],utterance=int(uid.split(':')[1]),
            decode_ms=event['asr_decode_ms'],punctuation=event['punctuation'])
        actual=next(r['payload'] for r in self.inbox.rows[offset:] if r['event_type']=='research_asr_observation')
        if {k:actual.get(k) for k in event}!=event:raise ValueError('Actual transcript method differs from sealed ASR observation')
        self.last[uid]=deepcopy(event)
        if event['final']:self.finals[uid]=deepcopy(event)

    def formatting(self,component):
        uid=component['utterance_id'];parent=self.finals.get(uid)
        if parent is None or uid in self.formatted or component['input_event_id']!=parent['event_id'] or component['raw_text']!=parent['text']:
            raise ValueError('Formatting lost exact raw-final parent')
        punctuation=deepcopy(component['punctuation'])
        def punctuate(text):
            if text!=parent['text']:raise ValueError('Cached formatter received different words')
            return deepcopy(punctuation)
        self.engine._s6d_punctuate((SimpleNamespace(punctuate=punctuate),parent['text'],parent['source_end_sec'],int(uid.split(':')[1])))
        self.formatted.add(uid)

    def advance(self,lane,bound,ready):self.engine._scheduler_advance(lane,bound,ready)
    def barrier(self):drain(self.engine._scheduler)

    def finish(self,execution):
        self.engine._scheduler.finish();snapshot=self.engine._scheduler.snapshot();worker=snapshot.pop('s6d_dispatch')
        if worker['thread_alive'] or worker['error'] or worker['accepted']!=worker['completed'] or snapshot['pending_events'] or not snapshot['closed']:
            raise RuntimeError('Actual publication worker did not drain')
        state=self.engine._s6d_presentation;rows=state.snapshot_rows()
        if {r['utterance_id']:r['text'] for r in rows}!={k:v['text'] for k,v in self.last.items()}:
            raise ValueError('Actual publication lost raw words or evicted a caption')
        for row in rows:
            if row.get('segments') and ''.join(x['raw_text'] for x in row['segments'])!=row['text']:
                raise ValueError('Actual publication lost raw fragments')
        return dict(schema='n4-modeled-catalog-mode-replay-v1',status='PASS_MODELED_MODE_APPLICATION_METHODS_ONLY',
            **deepcopy(CONTRACT),contract=self.contract,condition=self.condition,commands=len(execution),execution=execution,
            display_events=self.displays,publication_events=self.inbox.rows,publication_counts=dict(Counter(r['event_type'] for r in self.inbox.rows)),
            presentation=dict(rows=rows,rejected=dict(state.rejected),raw_observations=len([r for r in self.inbox.rows if r['event_type']=='research_asr_observation']),
                final_utterances=len(self.finals),formatting_revisions=len(self.formatted)),policy_snapshot=snapshot,
            worker_counts={k:worker[k] for k in ('accepted','completed','error','thread_alive','closed')},
            publication_method_qualification='ACTUAL_METHODS_WITH_MODELED_MODULE_CLOCKS',
            clock_injection='runtime and research_s7_presentation module time references only; global time unchanged; restored after worker exit',
            omitted_paths=['real _begin_session/source/model/startup/journal-writer/GUI','D0 raw model diagnostics and ASR dispatch-cost diagnostics'],
            source_cursor_scope='MODELED 100-ms source-speed producer with exact final tail; not an observed producer',
            native_clock_scope='N2 name-history and noise-coordinator host times diagnostic only; excluded from modeled performance metrics',
            upstream_publication_parity=False,complete_Controller_parity=False,actual_neural_inference_in_this_replay=False,
            scope='Actual transcript/policy/watermark/formatting/display publication methods under explicit modeled clock; not complete source/inference/I-O trace or latency acceptance')

    def close(self):
        if self.closed:return
        try:
            if self.engine is not None and self.engine._scheduler is not None:
                worker=self.engine._scheduler.worker
                if not worker.closed:worker.close(timeout=5.)
                if worker.thread.is_alive():raise RuntimeError('Publication worker still active')
        finally:
            self.stack.close();self.closed=True


def replay_d0_publication(asr,speaker,*,duration,formatting=(),**kwargs):
    commands=causal_commands(asr,speaker,duration=duration,formatting=formatting)
    context=PublicationReplay(duration=duration,**kwargs);execution=[]
    try:
        if context.contract['diarization']!='D0':raise ValueError('D0 publication requires D0 catalog path')
        for row in commands:
            context.clock.set(row['execute_at_sec']);c=row['command'];op,lane=c['operation'],c['lane']
            if op=='push':
                if lane=='asr':context.text(c['event'])
                else:context.engine._scheduler.push(c['event'],lane)
            elif op=='advance':context.advance(lane,math.inf if c['closed'] else c['lower_bound_sec'],c['modeled_available_at_sec'])
            else:context.formatting(c['component'])
            context.barrier();execution.append(dict(lane=lane,operation=op,modeled_at_sec=context.clock()))
        return context.finish(execution)
    finally:context.close()


def replay_d1_publication(asr,d1_rows,*,wave,summary,namespace,session_id,formatting=(),**kwargs):
    import numpy as np
    from edge_speech_pipeline.nemotron_diarization import DiarizationUpdate
    if wave.dtype!=np.float32 or wave.ndim!=1 or not np.isfinite(wave).all() or not 0<len(wave)<=120*16000:
        raise ValueError('Independent finite mono float32 saved audio required')
    duration=len(wave)/16000;plan=d1_plan(d1_rows,wave,summary,namespace,session_id)
    empty=[dict(lane='speaker',operation='advance',modeled_available_at_sec=duration,lower_bound_sec=None,closed=True)]
    commands=[r for r in causal_commands(asr,empty,duration=duration,formatting=formatting) if r['command']['lane']!='speaker']
    commands.extend(dict(command=dict(c,lane='d1'),execute_at_sec=c['ready'],priority=0,lane_sequence=i) for i,c in enumerate(plan['commands']))
    commands.sort(key=lambda r:(r['execute_at_sec'],r['priority'],r['lane_sequence']))
    if len(commands)>100000:raise ValueError('D1 publication command budget exceeded')
    context=PublicationReplay(duration=duration,namespace=namespace,session_id=session_id,**kwargs);activity=None;execution=[]
    try:
        if context.contract['diarization']!='D1':raise ValueError('D1 activity requires D1 catalog path')
        engine=context.engine;engine._identity_journal=QueryJournal(wave)
        activity=CooperativeActivity(engine,namespace,context.clock)
        for row in commands:
            context.clock.set(row['execute_at_sec']);c=row['command'];op=c['operation']
            if c['lane']=='d1':
                group=plan['groups'][c['group']];dispatch=group['dispatch']
                if op=='activity':
                    p=group['frames'];engine._identity_journal.delivered=dispatch['input_samples']
                    update=DiarizationUpdate(session_id,p['frame_start'],np.asarray(p['probabilities'],dtype=np.float32).reshape((-1,8)),
                        p['frame_step_sec'],p['audio_received_sec'],context.clock(),context.clock(),p['compute_sec'],p['is_final'],tuple(p['track_ids']),p['capacity_status'])
                    activity.begin(group,update)
                elif op=='embedding':activity.complete(c['query'])
                else:
                    if activity.phase!='idle':raise RuntimeError('D1 watermark before query completion')
                    context.advance('speaker',math.inf if c['source'] is None else c['source'],c['ready'])
            elif op=='push':context.text(c['event'])
            elif op=='advance':context.advance('asr',math.inf if c['closed'] else c['lower_bound_sec'],c['modeled_available_at_sec'])
            else:context.formatting(c['component'])
            context.barrier();execution.append(dict(lane=c['lane'],operation=op,modeled_at_sec=context.clock(),activity_phase=activity.phase))
        activity.close()
        actual=[r['payload'] for r in context.inbox.rows if r['event_type']=='research_embedding']
        expected=[q['event'] for g in plan['groups'] for q in g['queries']]
        fields=('event_id','source_start_sec','source_end_sec','available_at_sec','normalized_embedding','model_slot','tracker_id','model_namespace','clean_intervals','evidence_kind')
        if [{k:p[k] for k in fields} for p in actual]!=[{k:p[k] for k in fields} for p in expected]:raise ValueError('Actual D1 publication changed cached query geometry')
        coverage=[r['payload'] for r in context.inbox.rows if r['event_type']=='n2_exclusive_run_coverage']
        expected_coverage=[p for g in plan['groups'] for p in g['coverage']]
        if [{k:p[k] for k in e} for p,e in zip(coverage,expected_coverage)]!=expected_coverage or len(coverage)!=len(expected_coverage):
            raise ValueError('Actual D1 publication changed short-run coverage')
        result=context.finish(execution);result.update(scan=plan['scan'],embedding_calls=activity.calls,d1_worker_alive=activity.thread.is_alive())
        return result
    finally:
        if activity is not None and activity.thread.is_alive():activity.close()
        context.close()
