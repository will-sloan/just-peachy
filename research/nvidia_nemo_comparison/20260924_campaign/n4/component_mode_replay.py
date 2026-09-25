"""Catalog-correct modeled naming/display integration. README_COMPONENT_MODES.md."""
from collections import Counter
from copy import deepcopy
import math

from common import load, verify
from component_presentation import ComponentPresentation
from component_s7_replay import (ReplayClock,S7ReplayPresentation,causal_commands,modeled_publication,drain,CONTRACT)
from component_d1_replay import d1_plan,activity_engine,CooperativeActivity
from mode_galleries import backend_contract,load_prepared_gallery,configure_actual_mode


class ModeReplay:
    """Fresh actual resolver and presentation state; distinct published displays."""
    def __init__(self,preparation,backend,mode,tap,namespace,session_id):
        from app.pipeline import effective_profile
        from edge_speech_pipeline.research_s6d import S6DSettings,build_s6d_scheduler,build_presentation_state
        from edge_speech_pipeline.research_s7_policy import ObservedClock
        verify(preparation); prepared=load(preparation['path']);verify(prepared['catalog'])
        self.contract=backend_contract(load(prepared['catalog']['path']),backend,mode)
        expected=prepared['encoders'][self.contract['encoder']]['conditions'][self.contract['gallery_condition']]['namespace']
        if namespace!=expected:raise ValueError('Component and gallery encoder namespaces differ')
        self.gallery,self.condition=load_prepared_gallery(preparation,self.contract)
        self.clock=ReplayClock();self.observed=ObservedClock(clock=self.clock);self.observed.set_origin(0.)
        self.profile=effective_profile('balanced',mode,tap)
        self.settings=S6DSettings(text_delivery=True,boundary_repair=True,max_display_rows=512).validate()
        self.presentation=S7ReplayPresentation(build_presentation_state(self.settings,s7=dict(
            mode=self.contract['presentation_mode'],session_id=session_id,ownership_mode='timestamped_spans_v3')))
        self.policy=[];self.native=[];self.displays=[];self.activity_engine=None
        self.dispatcher=build_s6d_scheduler(self.profile,self.gallery,None,self.emit_policy,self.settings,observed_clock=self.observed)
        try:self.harness=configure_actual_mode(self.dispatcher,self.observed,self.profile,self.gallery,self.contract)
        except BaseException:
            self.close();raise

    def display(self,shown):
        if shown is None:return
        if len(self.displays)>=100000:raise ValueError('Modeled display budget exceeded')
        annotator=self.harness.prototype_identity
        published=annotator.annotate_caption(shown) if annotator is not None else deepcopy(shown)
        if published.get('text')!=shown.get('text'):raise ValueError('Naming annotation changed raw words')
        self.displays.append(dict(event_type='s6d_display',modeled_at_sec=self.clock(),
            state_row=deepcopy(shown),published_row=deepcopy(published),physical_widget_observed=False))

    def revise(self,uid):
        if self.activity_engine is not None:
            self.activity_engine._revise_supported_spans(utterance_id=uid,blocking=False)

    def text(self,event):
        self.display(self.presentation.text(event));self.revise(event['utterance_id'])

    def formatting(self,component):self.display(self.presentation.formatting(component))

    def emit_policy(self,record):
        if len(self.policy)>=100000:raise ValueError('Mode policy output budget exceeded')
        payload=modeled_publication(record,at_sec=self.clock());self.policy.append(payload)
        if payload['event_type'] in ('transcript_partial','transcript_final','transcript_label_revision'):
            self.display(self.presentation.policy(payload))
        if payload['event_type'] in ('transcript_partial','transcript_final'):
            self.revise(payload.get('utterance_id'))

    def emit_native(self,kind,source,payload):
        if len(self.native)>=100000:raise ValueError('Mode native output budget exceeded')
        self.native.append(dict(event_type=kind,source_time_sec=source,payload=deepcopy(payload),modeled_publication_at_sec=self.clock()))
        if kind=='transcript_label_revision':
            self.display(ComponentPresentation.policy(self.presentation,dict(payload,event_type=kind)))

    def finish(self,execution):
        self.dispatcher.finish();snapshot=self.dispatcher.snapshot();worker=snapshot.pop('s6d_dispatch')
        if (snapshot['pending_events'] or not snapshot['closed'] or worker['thread_alive']
                or worker['error'] or worker['accepted']!=worker['completed']):
            raise RuntimeError('Mode replay worker/closure failed')
        return dict(schema='n4-modeled-catalog-mode-replay-v1',status='PASS_MODELED_MODE_APPLICATION_METHODS_ONLY',
            **deepcopy(CONTRACT),contract=self.contract,condition=self.condition,
            namespace=deepcopy(self.gallery.namespace) if hasattr(self.gallery,'namespace') else None,
            gallery_receipt=deepcopy(self.gallery.receipt) if self.gallery else None,
            native_clock_scope='D1 name-history/research-embedding host monotonic fields and compute costs are diagnostic only, outside modeled chronology',
            display_scope='actual annotate_caption on state output; modeled publication; no Controller label projection or widget receipt',
            commands=len(execution),execution=execution,policy_events=self.policy,native_events=self.native,
            native_event_counts=dict(Counter(r['event_type'] for r in self.native)),
            presentation=self.presentation.snapshot(),presentation_events=self.presentation.events,
            display_events=self.displays,policy_snapshot=snapshot,
            worker_counts={k:worker[k] for k in ('accepted','completed','error','thread_alive','closed')},
            actual_neural_inference_in_this_replay=False,D0_E1_association_scale='UNQUALIFIED_NOMINAL' if
            (self.contract['diarization'],self.contract['encoder'])==('D0','E1') else 'unchanged admitted profile')

    def close(self):
        if not self.dispatcher.worker.closed:
            try:self.dispatcher.worker.close(timeout=5.)
            except RuntimeError:
                if self.dispatcher.worker.thread.is_alive():raise


def replay_d0_mode(asr,speaker,*,duration,preparation,backend,mode,tap,namespace,session_id,formatting=()):
    commands=causal_commands(asr,speaker,duration=duration,formatting=formatting)
    context=ModeReplay(preparation,backend,mode,tap,namespace,session_id);execution=[]
    try:
        if context.contract['diarization']!='D0':raise ValueError('D0 commands require actual D0 catalog route')
        for row in commands:
            context.clock.set(row['execute_at_sec']);c=row['command'];op,lane=c['operation'],c['lane']
            if op=='push':
                if lane=='asr':context.text(c['event'])
                context.dispatcher.push(c['event'],lane)
            elif op=='advance':context.dispatcher.advance({lane:math.inf if c['closed'] else c['lower_bound_sec']})
            else:context.formatting(c['component'])
            drain(context.dispatcher)
            execution.append(dict(lane=lane,operation=op,lane_sequence=row['lane_sequence'],modeled_at_sec=context.clock(),
                original_component_ready_at_sec=c.get('modeled_available_at_sec'),
                source_delivery_constraint_sec=row['source_delivery_constraint_sec'],source_watermark_sec=c.get('lower_bound_sec'),
                closed=c.get('closed'),pending_events=len(context.dispatcher.scheduler._heap)))
        return context.finish(execution)
    finally:context.close()


def replay_d1_mode(asr,d1_rows,*,wave,summary,namespace,preparation,backend,mode,tap,session_id,formatting=()):
    import numpy as np
    from edge_speech_pipeline.nemotron_diarization import DiarizationUpdate
    if wave.dtype!=np.float32 or wave.ndim!=1 or not np.isfinite(wave).all() or not 0<len(wave)<=120*16000:
        raise ValueError('Require independent finite mono float32 audio <=120 seconds')
    plan=d1_plan(d1_rows,wave,summary,namespace,session_id);duration=len(wave)/16000
    empty=[dict(lane='speaker',operation='advance',modeled_available_at_sec=duration,lower_bound_sec=None,closed=True)]
    commands=[r for r in causal_commands(asr,empty,duration=duration,formatting=formatting) if r['command']['lane']!='speaker']
    commands.extend(dict(command=dict(c,lane='d1'),execute_at_sec=c['ready'],priority=0,lane_sequence=i) for i,c in enumerate(plan['commands']))
    commands.sort(key=lambda r:(r['execute_at_sec'],r['priority'],r['lane_sequence']))
    if len(commands)>100000:raise ValueError('D1 command budget exceeded')
    context=ModeReplay(preparation,backend,mode,tap,namespace,session_id);activity=None;execution=[]
    try:
        if context.contract['diarization']!='D1':raise ValueError('D1 activity requires actual D1 catalog route')
        engine=activity_engine(context.presentation,context.observed,session_id,wave,context.emit_native)
        engine.mode=mode;engine.n2_name_map=context.harness.n2_name_map;context.activity_engine=engine
        activity=CooperativeActivity(engine,namespace,context.clock)
        for row in commands:
            context.clock.set(row['execute_at_sec']);c=row['command'];op=c['operation']
            if c['lane']=='d1':
                group=plan['groups'][c['group']];dispatch=group['dispatch']
                if op=='activity':
                    p=group['frames'];engine._identity_journal.delivered=dispatch['input_samples']
                    update=DiarizationUpdate(session_id,p['frame_start'],np.asarray(p['probabilities'],dtype=np.float32).reshape((-1,8)),
                        p['frame_step_sec'],p['audio_received_sec'],context.clock(),context.clock(),p['compute_sec'],
                        p['is_final'],tuple(p['track_ids']),p['capacity_status'])
                    activity.begin(group,update)
                elif op=='embedding':activity.complete(c['query'])
                else:
                    if activity.phase!='idle':raise RuntimeError('D1 watermark precedes activity/name completion')
                    engine._identity_journal.delivered=dispatch['input_samples']
                    context.dispatcher.advance({'speaker':math.inf if c['source'] is None else c['source']})
            elif op=='push':context.text(c['event']);context.dispatcher.push(c['event'],'asr')
            elif op=='advance':context.dispatcher.advance({'asr':math.inf if c['closed'] else c['lower_bound_sec']})
            else:context.formatting(c['component'])
            drain(context.dispatcher)
            execution.append(dict(lane=c['lane'],operation=op,modeled_at_sec=context.clock(),activity_phase=activity.phase))
        activity.close()
        actual=[r['payload'] for r in context.native if r['event_type']=='research_embedding']
        expected=[q['event'] for g in plan['groups'] for q in g['queries']]
        fields=('event_id','source_start_sec','source_end_sec','available_at_sec','normalized_embedding',
                'model_slot','tracker_id','model_namespace','clean_intervals','evidence_kind')
        if [{k:p[k] for k in fields} for p in actual]!=[{k:p[k] for k in fields} for p in expected]:
            raise ValueError('Mode changed actual D1 query selection or namespace')
        if [r['payload'] for r in context.native if r['event_type']=='n2_exclusive_run_coverage']!=[p for g in plan['groups'] for p in g['coverage']]:
            raise ValueError('Mode changed D1 unqueried/short-run coverage')
        result=context.finish(execution)
        result.update(scan=plan['scan'],embedding_calls=activity.calls,d1_worker_alive=activity.thread.is_alive(),
            name_map=engine.n2_name_map.snapshot())
        return result
    finally:
        if activity is not None and activity.thread.is_alive():activity.close()
        context.close()
