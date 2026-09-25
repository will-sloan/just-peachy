"""Actual Controller consumer/projection of sealed displays. README_CONTROLLER_PROJECTION.md."""
from copy import deepcopy
from contextlib import ExitStack,contextmanager
import json
import math
from pathlib import Path
import queue
import shutil
import threading
import time
from unittest.mock import patch

from common import bind,load,verify
from mode_galleries import backend_contract,load_prepared_gallery


@contextmanager
def forbid_inference():
    import onnxruntime
    from app.pipeline import ResidentModels
    from app.n2_models import N2ResidentModels
    from app.n3_models import N3ResidentModels
    def forbidden(*args,**kwargs):raise AssertionError('No model or enrollment acquisition in Controller projection')
    with ExitStack() as stack:
        stack.enter_context(patch.object(onnxruntime,'InferenceSession',side_effect=forbidden))
        for cls in (ResidentModels,N2ResidentModels,N3ResidentModels):
            for name in ('acquire','enrollment_models'):
                stack.enter_context(patch.object(cls,name,side_effect=forbidden))
        yield


def drain_commands(controller,timeout=10.):
    with controller.commands.all_tasks_done:
        done=controller.commands.all_tasks_done.wait_for(lambda:controller.commands.unfinished_tasks==0,timeout)
    if not done or controller.error:raise RuntimeError('Controller command failed: '+str(controller.error or 'timeout'))


class ResearchPeople:
    """Read-only E roster view, never written to the user's personal store."""
    def __init__(self,gallery,root,tap):
        self.root=Path(root);self.value=gallery;self.tap=tap
        self.rows=[] if gallery is None else [dict(id=i,name=n) for i,n in zip(gallery.ids,gallery.names)]
        self.preprocessing=getattr(gallery,'namespace',{}).get('preprocessing','mono-float32-16k-redimnet2-native-l2-v1')
    def list(self):return deepcopy(self.rows)
    def summaries(self,*args,**kwargs):return self.list()
    def gallery(self,route,selected_ids=None,**kwargs):
        if self.value is None or route.get('tap')!=self.tap or route.get('sample_rate')!=16000:
            raise ValueError('Research roster route has no matching gallery')
        if selected_ids is not None and (not selected_ids or set(selected_ids)!=set(self.value.ids)):
            raise ValueError('Selected roster differs from the fixed available references')
        return self.value


class ObservedDrainQueue(queue.Queue):
    """Observe after the actual consumer finishes an item, before its next get.

    Queue get/empty semantics are unchanged. All inputs are already sealed;
    there is no producer concurrency or pacing claim. No acknowledgement is
    reported until Controller._consume asks for its next event.
    """
    def __init__(self,observe,maximum=100000):
        super().__init__(maxsize=maximum)
        self.observe=observe;self.previous=None;self.delivered=self.observed=0
    def get(self,*args,**kwargs):
        if self.previous is not None:
            value=self.previous;self.previous=None
            self.observe(value,self.delivered-1);self.observed+=1
        value=super().get(*args,**kwargs)
        self.previous=value;self.delivered+=1
        return value
    def snapshot(self):
        return dict(replayed_sealed_events=True,delivered=self.delivered,observed_after_consume=self.observed,
            pending=self.qsize(),publication_latency_qualified=False)


def validate_display_history(replay):
    if (replay.get('schema')!='n4-modeled-catalog-mode-replay-v1'
            or replay.get('status')!='PASS_MODELED_MODE_APPLICATION_METHODS_ONLY'
            or replay.get('integrated_N4_cells')!=0 or replay.get('physical_widget_observed') is not False):
        raise ValueError('Require complete explicitly modeled mode-method output')
    rows=replay['display_events']
    if not rows or len(rows)>100000:raise ValueError('Bounded nonempty display history required')
    previous=-1.;session=None
    for event in rows:
        at=event['modeled_at_sec'];state,published=event['state_row'],event['published_row']
        if (event['event_type']!='s6d_display' or event['physical_widget_observed'] is not False
                or type(at) not in (int,float) or not math.isfinite(at) or at<previous
                or not published.get('caption_key') or not published.get('session_id')
                or state.get('text')!=published.get('text')):
            raise ValueError('Invalid display chronology or raw-word mutation')
        previous=at;session=session or published['session_id']
        if published['session_id']!=session:raise ValueError('Foreign display session')
        segments=published.get('segments')
        if segments and ''.join(s['raw_text'] for s in segments)!=published['text']:
            raise ValueError('Display fragments dropped raw words')
    return session


def project_mode_result(replay,*,tap,preparation,n2_runtime,n3_runtime,data_root,record_history=True):
    """Run unchanged Controller construction, selection, switching and consumer.

    Upstream inference/publication are NOT run here: their sealed modeled
    displays enter the real consumer queue. Only the roster view and upstream
    completion marker are supplied by this replay harness. No global clock or
    application source is patched. Actual consumer host times are not latency.
    """
    from app.controller import Controller
    from app.backends import backend_catalog
    from app.pipeline import PrototypeEngine,effective_profile
    from app.n2_pipeline import N2Engine
    from app.n3_pipeline import N3IdentityEngine
    from edge_speech_pipeline.contracts import PipelineEvent
    session=validate_display_history(replay);verify(preparation);prepared=load(preparation['path'])
    verify(prepared['catalog']);contract=backend_contract(load(prepared['catalog']['path']),
        replay['contract']['backend_key'],replay['contract']['mode'])
    if contract!=replay['contract']:raise ValueError('Foreign catalog/mode result')
    gallery,condition=load_prepared_gallery(preparation,contract)
    if condition!=replay['condition']:raise ValueError('Replay gallery condition changed')
    data_root=Path(data_root)
    if data_root.exists():raise ValueError('Use a fresh isolated Controller data directory')
    # The Controller receives no weights at all. Selected adapter manifests are
    # the exact existing documents, but model acquisition is forbidden by caller.
    data_root.mkdir(parents=True,exist_ok=False)
    for binding,name in [(n2_runtime,'n2_runtime.json'),(n3_runtime,'n3_runtime.json')]:
        verify(binding);shutil.copyfile(binding['path'],data_root/name)
        if bind(data_root/name)['sha256']!=binding['sha256']:raise ValueError('Runtime metadata copy changed')
    controller=Controller(data_root,data_root/'NO_MODEL_PAYLOAD',saved_audio_only=True)
    outputs=[];expected={};consumed=None
    try:
        catalog=backend_catalog();entry=next(r for r in catalog if r['key']==contract['backend_key'])
        controller.select_backend(entry['id']);drain_commands(controller)
        controller.store=ResearchPeople(gallery,data_root/'read-only-research-roster',tap)
        ids=[p['id'] for p in controller.store.list()]
        selected=ids if contract['mode'] in ('selected_focus','selected_closed') else []
        # Tap comes from the caller's verified audio-only parent, never an ID guess.
        if tap not in ('O0','O1'):raise ValueError('Explicit verified source tap required for Controller projection')
        controller.switch(mode=contract['mode'],recipe='balanced',tap=tap,selected_ids=selected,strict=False)
        drain_commands(controller)
        if controller.settings.get('text_assistance',False) or controller.collect_references or controller.use_references:
            raise ValueError('Unexpected optional correction/adaptation state')
        profile=effective_profile('balanced',contract['mode'],tap)
        engine_type={'PrototypeEngine':PrototypeEngine,'N2Engine':N2Engine,'N3IdentityEngine':N3IdentityEngine}[contract['engine']]
        kwargs=dict(diarization=contract['diarization']) if contract['uses_n2'] else {}
        engine=engine_type(controller.config,controller.models,profile,gallery,contract['mode'],**kwargs)
        # Baseline research bridge has no live query counter. This downstream
        # replay performs zero queries; supplying that counter is instrumentation.
        if gallery is not None and not hasattr(gallery,'query_count'):gallery.query_count=0
        engine.mode_configuration=controller.mode_configuration(profile,gallery)
        engine._session_dir=data_root/'replayed-session';engine._session_dir.mkdir()
        engine._state='COMPLETED'
        engine._finalization_thread=threading.Thread(target=lambda:None,name='n4-sealed-display-input',daemon=True)
        engine._finalization_thread.start();engine._finalization_thread.join(5.)
        if engine._finalization_thread.is_alive():raise RuntimeError('Sealed-input marker did not finish')
        controller.engine=engine;controller.state='RUNNING';controller.source_kind='file'
        epoch=controller.epoch

        history_bytes=0
        def observe(event,index):
            nonlocal history_bytes
            row=event.payload;expected[row['caption_key']]=deepcopy(row)
            with controller.lock:actual=deepcopy(controller.rows)
            if set(actual)!=set(expected):raise ValueError('Controller lost or invented caption rows')
            for key,original in expected.items():
                if {k:actual[key].get(k) for k in original}!=original:
                    raise ValueError('Controller changed bound upstream display fields')
            snapshot=controller.snapshot();grouped={}
            for part in snapshot['rows']:
                grouped.setdefault(part['caption_key'],[]).append(part['raw_asr_text'])
                if part['visible'] is not True:raise ValueError('Primary replay hid a transcript fragment')
            if {k:''.join(v) for k,v in grouped.items()}!={k:r['text'] for k,r in expected.items()}:
                raise ValueError('Controller projection dropped or changed raw words')
            if snapshot['error']:raise RuntimeError(snapshot['error'])
            if record_history:
                recorded=dict(input_display_index=index,source_modeled_at_sec=replay['display_events'][index]['modeled_at_sec'],
                    controller_consumed_at_host_monotonic_sec=time.perf_counter(),rows=deepcopy(snapshot['rows']),
                    epoch=snapshot['epoch'],clock_scope='source modeled; host consumer stamp is replay execution only; no live latency')
                history_bytes+=len(json.dumps(recorded,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode())
                if history_bytes>24*1024**2:raise ValueError('Controller projection history exceeds 24-MiB bound')
                outputs.append(recorded)

        events=ObservedDrainQueue(observe)
        for row in replay['display_events']:
            events.put_nowait(PipelineEvent('s6d_display',row['published_row']['source_end_sec'],deepcopy(row['published_row'])))
        engine.events=events
        controller.consumer=threading.Thread(target=controller._consume,args=(engine,epoch),name='proto-caption-consumer',daemon=True)
        controller.consumer.start();controller.consumer.join(60.)
        if controller.consumer.is_alive():raise RuntimeError('Controller consumer did not drain within bound')
        if controller.error:raise RuntimeError('Controller consumer failed: '+controller.error)
        if (not events.empty() or events.observed!=len(replay['display_events'])
                or controller.metrics['completed_sessions']!=1 or controller.metrics['events_consumed']!=events.observed):
            raise ValueError('Incomplete Controller display-event census')
        consumed=controller.snapshot()
        closure=bind(engine.session_dir/'s6d_consumer_closure.json')
        if not load(closure['path'])['full_event_consumer_drained']:raise ValueError('Actual consumer closure missing')
        result=dict(schema='n4-actual-controller-display-projection-v1',status='PASS_ACTUAL_CONSUMER_AND_LABEL_PROJECTION_ONLY',
            contract=contract,tap=tap,condition=condition,display_inputs=events.observed,history=outputs,
            final_rows=deepcopy(consumed['rows']),controller_raw_rows=deepcopy(list(controller.rows.values())),
            actual_consumer_closure=closure,consumer_thread_alive=controller.consumer.is_alive(),
            model_loads={k:getattr(controller.models,k,0) for k in ('asr_loads','speaker_loads','streams')},
            output_defaults=deepcopy(controller.output_defaults),adaptation=consumed['adaptation'],
            inferred_audio=False,upstream_publication_parity=False,complete_Controller_parity=False,
            physical_widget_observed=False,integrated_N4_cells=0,
            scope='Sealed modeled displays through unchanged actual Controller consumer, epoch row handling and snapshot label/text projection; no upstream publication, inference, GUI or latency qualification')
    finally:
        controller.close();drain_commands(controller);controller.worker.join(10.)
        if controller.worker.is_alive() or not controller.closed:raise RuntimeError('Controller owner did not close')
    if any(result['model_loads'].values()):raise ValueError('Projection unexpectedly loaded a model')
    result['controller_closed']=True;result['controller_worker_alive']=False
    return result
