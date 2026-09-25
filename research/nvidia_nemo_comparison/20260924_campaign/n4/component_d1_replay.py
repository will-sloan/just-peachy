"""Cooperative cached D1 application replay. See README_COMPONENT_D1_REPLAY.md."""
from collections import Counter
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import queue
import threading

from component_presentation import ComponentPresentation
from component_s7_replay import (ReplayClock, S7ReplayPresentation, causal_commands,
    modeled_publication, drain, CONTRACT)


def d1_plan(rows, wave, summary, namespace, session_id):
    """Require the strict native/query census before constructing any commands."""
    from app.n2_pipeline import ActivityTimeline
    from review_d1_components import scan_events
    scan = scan_events(rows, wave, summary, namespace, ActivityTimeline)
    groups, pending = [], None
    for row in rows:
        kind, payload = row['event_type'], row['payload']
        if kind == 'component_d1_dispatch':
            groups.append(dict(dispatch=deepcopy(payload), frames=None, queries=[], coverage=[]))
        elif kind == 'n2_diarization_frames':
            if payload['track_ids'] != [f'{session_id}:nemotron-slot-{slot}' for slot in range(8)]:
                raise ValueError('Foreign D1 native slot namespace')
            groups[-1]['frames'] = deepcopy(payload)
        elif kind == 'component_d1_embedding_call':
            pending = deepcopy(payload)
        elif kind == 'research_embedding':
            groups[-1]['queries'].append(dict(call=pending, event=deepcopy(payload)))
            pending = None
        elif kind == 'n2_exclusive_run_coverage':
            groups[-1]['coverage'].append(deepcopy(payload))
    commands = []
    for index, group in enumerate(groups):
        dispatch = group['dispatch']
        ready = dispatch['modeled_available_at_sec']
        if group['frames'] is not None:
            commands.append(dict(operation='activity', group=index, ready=ready))
            for query_index, query in enumerate(group['queries']):
                ready = query['event']['available_at_sec']
                commands.append(dict(operation='embedding', group=index, query=query_index, ready=ready))
        commands.append(dict(operation='advance', group=index, ready=ready,
            source=None if dispatch['operation']=='finish' else dispatch['input_samples']/16000))
    return dict(groups=groups, commands=commands, scan=scan)


class QueryJournal:
    """Exact rereads of delivered audio; no synthesis, concatenation or padding."""
    def __init__(self, wave):
        self.wave = wave
        self.delivered = 0
        self.last_read = None

    def read(self, first, count, *, wait_sec):
        if (wait_sec != 0 or type(first) is not int or type(count) is not int
                or not 0 <= first < first+count <= self.delivered):
            raise ValueError('Cached query asks for undelivered or invalid waveform support')
        self.last_read = (first, first+count)
        return self.wave[first:first+count]


class CooperativeActivity:
    """Execute unchanged N2Engine._accept_activity, yielding inside cached embed.

    The worker retains the actual engine RLock while embed waits. ASR therefore
    publishes independently and the actual nonblocking span-revision method
    behaves as it does while the speaker worker is busy. Only the owner advances
    the injected clock; each worker transition ends at a finite barrier.
    """
    def __init__(self, engine, namespace, clock):
        self.engine, self.namespace, self.clock = engine, namespace, clock
        self.tasks = queue.Queue(maxsize=1)
        self.condition = threading.Condition()
        self.phase = 'idle'
        self.boundary = 0
        self.error = None
        self.abort = False
        self.permit = False
        self.group = None
        self.query_index = 0
        self.last_embed_ms = 0.
        self.calls = 0
        self.thread = threading.Thread(target=self._run, name='n4-cached-d1-activity', daemon=True)
        self.thread.start()

    def _wait(self, boundary):
        with self.condition:
            done = self.condition.wait_for(lambda:self.boundary > boundary or self.error is not None, timeout=5.)
            if not done or self.error:
                raise RuntimeError('Cached D1 worker failed: '+(self.error or 'boundary timeout'))

    def begin(self, group, update):
        with self.condition:
            if self.phase != 'idle' or self.error:
                raise RuntimeError('Prior D1 update is still active')
            self.phase, self.group, self.query_index = 'running', group, 0
            boundary = self.boundary
        self.tasks.put_nowait(update)
        self._wait(boundary)

    def complete(self, query_index):
        with self.condition:
            if (self.phase != 'query_wait' or query_index != self.query_index
                    or self.clock() != self.group['queries'][query_index]['event']['available_at_sec']):
                raise ValueError('Embedding completion has no matching ready query')
            self.phase, self.permit = 'running', True
            boundary = self.boundary
            self.condition.notify_all()
        self._wait(boundary)

    def embed(self, waveform):
        import numpy as np
        if self.query_index >= len(self.group['queries']):
            raise ValueError('Actual D1 selected an unrecorded query')
        q = self.group['queries'][self.query_index]
        event, call = q['event'], q['call']
        support = (round(event['source_start_sec']*16000), round(event['source_end_sec']*16000))
        if (self.engine._identity_journal.last_read != support or len(waveform) != call['samples']
                or hashlib.sha256(waveform.astype('<f4').tobytes()).hexdigest() != call['waveform_sha256']
                or self.clock() > event['available_at_sec']):
            raise ValueError('Actual D1 query differs from sealed waveform/clock')
        with self.condition:
            self.phase = 'query_wait'
            self.boundary += 1
            self.condition.notify_all()
            if not self.condition.wait_for(lambda:self.permit or self.abort, timeout=5.):
                raise RuntimeError('Owner did not resolve cached D1 query within bounded wait')
            if self.abort:
                raise RuntimeError('Cached D1 replay aborted')
            self.permit = False
        self.last_embed_ms = event['compute_ms']
        self.calls += 1
        self.query_index += 1
        return np.asarray(event['normalized_embedding'], dtype=np.float32)

    def _run(self):
        from app.n2_pipeline import N2Engine
        while True:
            update = self.tasks.get()
            try:
                if update is None:
                    return
                N2Engine._accept_activity(self.engine, update, self)
                if self.query_index != len(self.group['queries']):
                    raise ValueError('Actual D1 omitted a sealed query')
                with self.condition:
                    self.phase = 'idle'
                    self.boundary += 1
                    self.condition.notify_all()
            except BaseException as exc:
                with self.condition:
                    self.error = repr(exc)
                    self.condition.notify_all()
            finally:
                self.tasks.task_done()

    def close(self):
        with self.condition:
            self.abort = True
            self.condition.notify_all()
        self.tasks.put(None, timeout=5.)
        self.thread.join(5.)
        if self.thread.is_alive():
            raise RuntimeError('Cached D1 worker did not exit')


def activity_engine(presentation, observed_clock, session_id, wave, emit):
    """Initialize only the state required by unchanged activity/span methods."""
    from app.n2_pipeline import N2Engine, ActivityTimeline
    from app.n2_identity import N2NameMap

    class Engine(N2Engine):
        def __init__(self):
            self._n2_lock = threading.RLock()
            self._n2_timeline = ActivityTimeline()
            self._n2_names, self._n2_name_history = {}, {}
            self._n2_last_query, self._n2_span_signatures, self._n2_associations = {}, {}, {}
            self._n2_reported_runs, self._n2_admitted_runs = set(), set()
            self._n2_embedding_serial = self._n2_revision = self._n2_short_run_count = 0
            self._n2_short_run_sec, self._n2_reported_run_end = 0., -1.
            self._s6d_presentation = presentation.state
            self._s7_observed_clock = observed_clock
            self._session_dir = Path(session_id)
            self._identity_journal = QueryJournal(wave)
            self.mode = 'anonymous_conversation'
            self.n2_name_map = N2NameMap(None)

        def _emit(self, kind, source, payload):
            emit(kind, source, payload)

    return Engine()


def replay_d1_anonymous(asr, d1_rows, *, wave, summary, namespace, profile, session_id, formatting=()):
    """Run actual activity/query/name/span code with sealed vectors, E0 or E1.

    Only anonymous mode is admitted. Named/closed/selected display annotations
    and measured Controller timing need their own integration qualification.
    """
    import numpy as np
    from edge_speech_pipeline.nemotron_diarization import DiarizationUpdate
    from edge_speech_pipeline.research_s6d import S6DSettings, build_s6d_scheduler, build_presentation_state
    from edge_speech_pipeline.research_s7_policy import ObservedClock
    if (profile.identity.mode != 'none' or profile.xvf.mode not in ('off','none','disabled')
            or profile.profile_id not in ('PROTO1_balanced_anonymous_conversation_O0','PROTO1_balanced_anonymous_conversation_O1')):
        raise ValueError('Require Balanced anonymous application profile')
    if wave.dtype != np.float32 or wave.ndim != 1 or not np.isfinite(wave).all() or not 0 < len(wave) <= 120*16000:
        raise ValueError('Require finite independent mono float32 audio <=120 seconds')
    plan = d1_plan(d1_rows, wave, summary, namespace, session_id)
    duration = len(wave)/16000
    # Use the already-tested ASR/formatting validator, discarding its placeholder
    # speaker closure; real D1 source watermarks below replace that placeholder.
    empty_lane = [dict(lane='speaker',operation='advance',modeled_available_at_sec=duration,lower_bound_sec=None,closed=True)]
    commands = [r for r in causal_commands(asr, empty_lane, duration=duration, formatting=formatting)
        if r['command']['lane'] != 'speaker']
    for sequence, command in enumerate(plan['commands']):
        commands.append(dict(command=dict(command,lane='d1'),execute_at_sec=command['ready'],
            priority=0,lane_sequence=sequence))
    commands.sort(key=lambda r:(r['execute_at_sec'],r['priority'],r['lane_sequence']))
    if len(commands) > 100000:
        raise ValueError('D1 joint command budget exceeded')
    clock = ReplayClock(); observed = ObservedClock(clock=clock); observed.set_origin(0.)
    settings = S6DSettings(text_delivery=True,boundary_repair=True,max_display_rows=512)
    presentation = S7ReplayPresentation(build_presentation_state(settings,s7=dict(
        mode='M1',session_id=session_id,ownership_mode='timestamped_spans_v3')))
    native_outputs, policy_outputs, execution = [], [], []

    def emitted_native(kind, source, payload):
        if len(native_outputs) >= 100000:
            raise ValueError('D1 native replay output budget exceeded')
        native_outputs.append(dict(event_type=kind,source_time_sec=source,payload=deepcopy(payload),
            modeled_publication_at_sec=clock(),
            clock_scope='modeled except research_embedding.available_at_monotonic is diagnostic host execution only'))
        if kind == 'transcript_label_revision':
            # N2's own historical caption annotations are not S7 freshness
            # records. Retain their exact target revision/span IDs and scope.
            ComponentPresentation.policy(presentation,dict(payload,event_type=kind))

    engine = activity_engine(presentation,observed,session_id,wave,emitted_native)

    def emitted_policy(record):
        if len(policy_outputs) >= 100000:
            raise ValueError('D1 S7 output budget exceeded')
        payload = modeled_publication(record,at_sec=clock())
        policy_outputs.append(payload)
        if payload['event_type'] in ('transcript_partial','transcript_final','transcript_label_revision'):
            presentation.policy(payload)
        if payload['event_type'] in ('transcript_partial','transcript_final'):
            engine._revise_supported_spans(utterance_id=payload.get('utterance_id'),blocking=False)

    dispatcher = build_s6d_scheduler(profile,None,None,emitted_policy,settings,observed_clock=observed)
    activity = CooperativeActivity(engine,namespace,clock)
    try:
        for row in commands:
            clock.set(row['execute_at_sec'])
            c = row['command']; op = c['operation']
            if c['lane'] == 'd1':
                group = plan['groups'][c['group']]; dispatch = group['dispatch']
                if op == 'activity':
                    p = group['frames']; probabilities = np.asarray(p['probabilities'],dtype=np.float32).reshape((-1,8))
                    engine._identity_journal.delivered = dispatch['input_samples']
                    update = DiarizationUpdate(session_id,p['frame_start'],probabilities,p['frame_step_sec'],
                        p['audio_received_sec'],clock(),clock(),p['compute_sec'],p['is_final'],tuple(p['track_ids']),p['capacity_status'])
                    activity.begin(group,update)
                elif op == 'embedding':
                    activity.complete(c['query'])
                else:
                    if activity.phase != 'idle':
                        raise RuntimeError('D1 watermark precedes activity/name/span completion')
                    engine._identity_journal.delivered = dispatch['input_samples']
                    dispatcher.advance({'speaker':math.inf if c['source'] is None else c['source']})
            elif op == 'push':
                presentation.text(c['event'])
                engine._revise_supported_spans(utterance_id=c['event']['utterance_id'],blocking=False)
                dispatcher.push(c['event'],'asr')
            elif op == 'advance':
                dispatcher.advance({'asr':math.inf if c['closed'] else c['lower_bound_sec']})
            else:
                presentation.formatting(c['component'])
            drain(dispatcher)
            execution.append(dict(lane=c['lane'],operation=op,modeled_at_sec=clock(),
                activity_phase=activity.phase,native_outputs=len(native_outputs),policy_outputs=len(policy_outputs)))
        dispatcher.finish()
        activity.close()
        actual_queries = [r['payload'] for r in native_outputs if r['event_type']=='research_embedding']
        expected_queries = [q['event'] for g in plan['groups'] for q in g['queries']]
        fields = ('event_id','source_start_sec','source_end_sec','available_at_sec','normalized_embedding',
                  'model_slot','tracker_id','model_namespace','clean_intervals','evidence_kind')
        if [{k:p[k] for k in fields} for p in actual_queries] != [{k:p[k] for k in fields} for p in expected_queries]:
            raise ValueError('Actual N2Engine query replay differs from sealed component')
        coverage = [r['payload'] for r in native_outputs if r['event_type']=='n2_exclusive_run_coverage']
        if coverage != [p for g in plan['groups'] for p in g['coverage']]:
            raise ValueError('Actual N2Engine lost short or unqueried native runs')
        snapshot = dispatcher.snapshot(); worker = snapshot.pop('s6d_dispatch')
        if snapshot['pending_events'] or not snapshot['closed'] or activity.error:
            raise RuntimeError('Incomplete D1 replay closure')
        return dict(schema='n4-modeled-d1-anonymous-replay-v1',status='PASS_MODELED_D1_APPLICATION_METHODS_ONLY',
            **deepcopy(CONTRACT),d1_lock_model='actual RLock held during cooperative cached embed; independent raw text',
            d1_host_clock_scope='name-history/research-embedding monotonic stamps and naming compute are diagnostic host values; not modeled evidence age or live latency',
            commands=len(commands),scan=plan['scan'],embedding_calls=activity.calls,
            native_event_counts=dict(Counter(r['event_type'] for r in native_outputs)),
            native_events=native_outputs,policy_events=policy_outputs,execution=execution,
            presentation=presentation.snapshot(),presentation_events=presentation.events,
            policy_snapshot=snapshot,name_map=engine.n2_name_map.snapshot(),
            worker_counts={k:worker[k] for k in ('accepted','completed','error','thread_alive','closed')},
            d1_worker_alive=activity.thread.is_alive(),actual_neural_inference_in_this_replay=False)
    finally:
        if activity.thread.is_alive(): activity.close()
        if not dispatcher.worker.closed:
            try: dispatcher.worker.close(timeout=5.)
            except RuntimeError:
                if dispatcher.worker.thread.is_alive(): raise
