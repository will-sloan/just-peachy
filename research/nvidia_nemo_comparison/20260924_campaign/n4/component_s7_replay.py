"""Modeled causal D0/ASR replay through actual S7. README_COMPONENT_S7_REPLAY.md."""
from copy import deepcopy
import math

from component_presentation import ComponentPresentation

CLOCK_KIND = 'MODELED_S7_REPLAY_NOT_OBSERVED_CONTROLLER_OR_WIDGET'
CONTRACT = dict(
    clock_kind=CLOCK_KIND,
    source_epoch_sec=0.,
    admission='isolated component source-paced FIFO ready times',
    lane_tie_order=['speaker', 'asr', 'formatting'],
    policy_queue_delay_sec=0.,
    policy_compute_delay_sec=0.,
    publication_delay_sec=0.,
    assumptions='independent component FIFOs; synchronous policy drain per command; no contention model',
    inherited_observed_monotonic_and_gui_fields='MODELED_VALUES_AND_NATIVE_FIELD_NAMES_ONLY',
    first_visible_latency='UNAVAILABLE_MODELED_REPLAY',
    observed_Controller_parity=False,
    physical_widget_observed=False,
    integrated_N4_cells=0)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


class ReplayClock:
    """Only the owner moves time, after the real bounded policy worker drains."""
    def __init__(self):
        self.now = 0.

    def __call__(self):
        return self.now

    def set(self, value):
        if not finite(value) or value < self.now:
            raise ValueError('Modeled clock must be finite and monotone')
        self.now = float(value)


def causal_commands(asr, speaker, *, duration, formatting=(), max_commands=100000):
    """Validate complete reconstructed lanes, then merge without changing inputs.

    The D0 close argument can precede its unread partial tail. A close is
    scheduled after source delivery as a separate constraint, with its original
    ready value preserved. Finite watermarks retain source progress, not ready.
    """
    from edge_speech_pipeline.research_s7_policy import predictor_payload
    if not finite(duration) or duration <= 0 or type(max_commands) is not int or max_commands < 1:
        raise ValueError('Positive finite duration and command budget required')
    merged, ids, finals = [], set(), {}
    for priority, (lane, commands) in enumerate((('speaker', speaker), ('asr', asr))):
        last, watermark, closed = 0., 0., False
        if not commands:
            raise ValueError('Both complete lanes are required')
        for sequence, command in enumerate(commands):
            common = {'lane', 'operation', 'modeled_available_at_sec'}
            op = command.get('operation')
            allowed = common | ({'event'} if op == 'push' else {'lower_bound_sec', 'closed'})
            ready = command.get('modeled_available_at_sec')
            if (set(command) != allowed or command.get('lane') != lane or op not in ('push', 'advance')
                    or not finite(ready) or ready < last or closed):
                raise ValueError('Invalid, regressing or already closed lane command')
            last = ready
            execute = ready
            if op == 'push':
                event = predictor_payload(command['event'])
                if ((event['kind'] == 'asr') != (lane == 'asr') or event['available_at_sec'] != ready
                        or event['source_end_sec'] > duration or event['event_id'] in ids or ready < watermark
                        or event.get('receptive_end_sec', event['source_end_sec']) > ready):
                    raise ValueError('Duplicate, future, sealed or wrong-lane predictor event')
                ids.add(event['event_id'])
                if lane == 'asr':
                    uid = event['utterance_id']
                    if uid in finals:
                        raise ValueError('Raw observation after final')
                    if event['final']:
                        finals[uid] = event
            else:
                closed = command['closed']
                bound = command['lower_bound_sec']
                if type(closed) is not bool:
                    raise ValueError('Explicit closure flag required')
                if closed:
                    if bound is not None:
                        raise ValueError('Closure must retain the None source-bound sentinel')
                    execute = max(ready, duration)
                else:
                    if not finite(bound) or not watermark <= bound <= min(ready, duration):
                        raise ValueError('Source watermark is regressing or ahead of delivery')
                    watermark = bound
            merged.append(dict(command=deepcopy(command), execute_at_sec=execute,
                source_delivery_constraint_sec=duration if closed else None,
                priority=priority, lane_sequence=sequence))
        if not closed:
            raise ValueError('Lane is missing final closure')
    formatted, last_format = set(), 0.
    for sequence, component in enumerate(formatting):
        ready = component['modeled_available_at_sec']
        uid = component['utterance_id']
        final = finals.get(uid)
        if (final is None or uid in formatted or component['input_event_id'] != final['event_id']
                or component['raw_text'] != final['text'] or not finite(ready)
                or ready < max(last_format, final['available_at_sec'])):
            raise ValueError('Formatting must preserve ordered, exact raw-final parents')
        formatted.add(uid)
        last_format = ready
        merged.append(dict(command=dict(lane='formatting', operation='format', component=deepcopy(component)),
            execute_at_sec=ready, source_delivery_constraint_sec=None, priority=2, lane_sequence=sequence))
    if len(merged) > max_commands:
        raise ValueError('Replay command budget exceeded')
    merged.sort(key=lambda row: (row['execute_at_sec'], row['priority'], row['lane_sequence']))
    return merged


def modeled_publication(record, *, at_sec, origin=0.):
    """Invoke the actual publication expiry check; returned clocks are modeled."""
    from edge_speech_pipeline.research_s7_policy import publication_freshness
    if origin != 0. or not finite(at_sec):
        raise ValueError('Require the explicit zero-origin modeled clock')
    result = deepcopy(record)
    if result.get('source_epoch_monotonic_sec') != origin:
        raise ValueError('Foreign S7 source epoch')
    result.update(publication_freshness(result, origin, at_sec))
    result['publication_monotonic_sec'] = at_sec
    return result


class S7ReplayPresentation(ComponentPresentation):
    """Separate adapter retaining native S7 freshness fields under modeled scope."""
    def policy(self, record):
        if record.get('event_type') not in ('transcript_partial', 'transcript_final', 'transcript_label_revision'):
            raise ValueError('Require actual caption-policy output')
        if record.get('utterance_id') not in self.last_text:
            raise ValueError('Policy cannot precede independent raw text publication')
        available = record['observed_publication_at_sec']
        if (not finite(available) or available < self.now or available < record['source_end_sec']
                or self.serial >= self.max_events or record.get('source_epoch_monotonic_sec') != 0.
                or record.get('publication_monotonic_sec') != available
                or record.get('session_id', self.state.session_id) != self.state.session_id):
            raise ValueError('Noncausal or foreign modeled S7 publication')
        self.now = available
        self.serial += 1
        payload = deepcopy(record)
        payload.update(session_id=self.state.session_id, publication_sequence=self.serial)
        shown = self.state.consume(payload['event_type'], payload, now=available)
        self.events.append(dict(kind=payload['event_type'], input=payload, modeled_available_at_sec=available,
            clock_kind=CLOCK_KIND, presentation=deepcopy(shown), physical_widget_observed=False))
        return shown

    def snapshot(self):
        return {**super().snapshot(), **deepcopy(CONTRACT)}


def drain(dispatcher, timeout=5.):
    """A finite worker barrier, not a sleep/poll loop or synthetic worker."""
    worker = dispatcher.worker
    with worker.queue.all_tasks_done:
        completed = worker.queue.all_tasks_done.wait_for(lambda: worker.queue.unfinished_tasks == 0, timeout)
    if not completed or worker.error or worker.accepted != worker.completed:
        raise RuntimeError(f'S7 policy worker did not complete: {worker.error or "timeout/count mismatch"}')


def replay_d0_anonymous(asr, speaker, *, duration, profile, session_id, formatting=(), max_commands=100000):
    """D0/E0 anonymous application policy, with real tracker, dispatcher and spans.

    This intentionally narrow first adapter does not stand in for N2NameMap,
    D1 activity/name/history association, a named mode, or Controller parity.
    Callers verify sealed component/source bindings before calling this API.
    """
    from edge_speech_pipeline.research_s6d import S6DSettings, build_presentation_state, build_s6d_scheduler
    from edge_speech_pipeline.research_s7_policy import ObservedClock
    if (profile.identity.mode != 'none' or profile.xvf.mode not in ('off', 'none', 'disabled')
            or profile.profile_id not in ('PROTO1_balanced_anonymous_conversation_O0', 'PROTO1_balanced_anonymous_conversation_O1')):
        raise ValueError('Only the exact balanced anonymous D0/E0 profile is supported')
    commands = causal_commands(asr, speaker, duration=duration, formatting=formatting, max_commands=max_commands)
    clock = ReplayClock()
    observed = ObservedClock(clock=clock)
    observed.set_origin(0.)
    settings = S6DSettings(text_delivery=True, boundary_repair=True, max_display_rows=512).validate()
    presentation = S7ReplayPresentation(build_presentation_state(settings, s7=dict(
        mode='M1', session_id=session_id, ownership_mode='timestamped_spans_v3')))
    outputs, execution = [], []

    def emitted(record):
        if len(outputs) >= max_commands:
            raise ValueError('Policy output budget exceeded')
        payload = modeled_publication(record, at_sec=clock())
        outputs.append(dict(clock_kind=CLOCK_KIND, native_record=payload))
        if payload['event_type'] in ('transcript_partial', 'transcript_final', 'transcript_label_revision'):
            presentation.policy(payload)

    dispatcher = build_s6d_scheduler(profile, None, None, emitted, settings, observed_clock=observed)
    try:
        for row in commands:
            clock.set(row['execute_at_sec'])
            command = row['command']
            op, lane = command['operation'], command['lane']
            if op == 'push':
                if lane == 'asr':
                    presentation.text(command['event'])
                dispatcher.push(command['event'], lane)
            elif op == 'advance':
                dispatcher.advance({lane: math.inf if command['closed'] else command['lower_bound_sec']})
            else:
                presentation.formatting(command['component'])
            drain(dispatcher)
            execution.append(dict(lane=lane, operation=op, lane_sequence=row['lane_sequence'],
                execute_at_sec=clock(), original_component_ready_at_sec=command.get('modeled_available_at_sec'),
                source_delivery_constraint_sec=row['source_delivery_constraint_sec'],
                source_watermark_sec=command.get('lower_bound_sec'), closed=command.get('closed'),
                input_event_id=command.get('event', {}).get('event_id'), emitted_total=len(outputs),
                pending_events=len(dispatcher.scheduler._heap)))
        dispatcher.finish()
        snapshot = dispatcher.snapshot()
        if snapshot['pending_events'] or not snapshot['closed']:
            raise RuntimeError('S7 replay did not fully close')
        # submit_at_admission uses the injected epoch, while worker age uses
        # perf_counter. The mixed-clock age is invalid and must never escape.
        telemetry = snapshot.pop('s6d_dispatch')
        counts = {key:telemetry[key] for key in ('accepted','completed','max_depth','error','thread_alive','closed')}
        if counts['accepted'] != counts['completed'] or counts['thread_alive'] or counts['error']:
            raise RuntimeError('Actual policy worker cleanup/count check failed')
        return dict(schema='n4-modeled-s7-d0-anonymous-v1', **deepcopy(CONTRACT),
            status='PASS_MODELED_POLICY_REPLAY_ONLY', command_count=len(commands),
            raw_event_count=presentation.text_serial, policy_event_count=len(outputs),
            execution=execution, policy=outputs, policy_snapshot=snapshot,
            presentation=presentation.snapshot(), presentation_events=presentation.events,
            worker_counts=counts, worker_age='UNAVAILABLE_MIXED_NATIVE_AND_INJECTED_CLOCKS',
            native_policy_cost_fields='diagnostic host execution costs, excluded from modeled chronology')
    finally:
        if not dispatcher.worker.closed:
            try:
                dispatcher.worker.close(timeout=5.)
            except RuntimeError:
                if dispatcher.worker.thread.is_alive():
                    raise
