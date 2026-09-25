"""Reconstruct sealed ASR lane commands. See README_COMPONENT_COMMANDS.md."""
from copy import deepcopy
import math


def asr_commands(rows, *, variant, duration):
    """Recover actual push/watermark order, retaining modeled compute separately.

    Baseline advances after full dispatch/reset; its partial tail advances only
    on closure. Native A1/A2/A3 advance after each complete feed/publish call,
    including the short tail, then close after drain. Formatting is separate.
    """
    if variant not in ('A0', 'A1', 'A2', 'A3') or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Explicit variant and real source duration required')
    commands = []
    pending = None
    drain = None
    serial = 0
    last_time = 0.
    last_source = 0.
    formatting_started = False

    def append(op, available, **payload):
        nonlocal last_time
        if type(available) not in (int, float) or not math.isfinite(available) or available < last_time:
            raise ValueError('ASR command availability regressed')
        last_time = available
        commands.append(dict(lane='asr', operation=op, modeled_available_at_sec=available, **payload))

    def finish_pending():
        nonlocal pending
        if pending is not None:
            append('advance', pending['modeled_available_at_sec'], lower_bound_sec=pending['source_end_sec'], closed=False)
            pending = None

    for row in rows:
        kind, p = row['event_type'], row['payload']
        if kind == 'component_final_punctuation':
            formatting_started = True
            continue
        if formatting_started:
            raise ValueError('Raw ASR event after separate formatting phase')
        if kind == 'research_asr_dispatch':
            if drain is not None: raise ValueError('ASR dispatch after drain')
            if variant == 'A0' and pending is not None:
                raise ValueError('Missing baseline full-dispatch watermark evidence')
            finish_pending()
            end, start = p['source_end_sec'], p['source_start_sec']
            if abs(start-last_source) > 1e-7 or not start < end <= duration or p['modeled_available_at_sec'] < end:
                raise ValueError('ASR dispatch source discontinuity')
            pending = p
            last_source = end
        elif kind == 'research_asr_full_dispatch_cost':
            if variant != 'A0' or pending is None or p['source_end_sec'] != pending['source_end_sec']:
                raise ValueError('Unexpected baseline full-dispatch completion')
            append('advance', p['modeled_available_at_sec'], lower_bound_sec=p['source_end_sec'], closed=False)
            pending = None
        elif kind == 'research_asr_tail_dispatch':
            if variant != 'A0' or pending is not None or drain is not None:
                raise ValueError('Unexpected baseline partial tail')
            if abs(p['source_start_sec']-last_source) > 1e-7 or p['source_end_sec'] != duration:
                raise ValueError('Baseline tail source discontinuity')
            last_source = duration
        elif kind == 'research_asr_drain':
            if drain is not None or abs(last_source-duration) > 1e-7 or p['source_end_sec'] != duration:
                raise ValueError('Missing real source or duplicate drain')
            if variant == 'A0' and pending is not None:
                raise ValueError('Baseline full-dispatch completion missing at drain')
            finish_pending()
            drain = p
        elif kind == 'research_asr_observation':
            serial += 1
            if (p['event_id'] != f'asr:{serial:08d}' or p['kind'] != 'asr'
                    or not 0 <= p['source_start_sec'] <= p['source_end_sec'] <= last_source
                    or p['available_at_sec'] < p['source_end_sec']):
                raise ValueError('ASR observation census or source support differs')
            append('push', p['available_at_sec'], event=deepcopy(p))
    if drain is None or pending is not None:
        raise ValueError('Complete ASR dispatch/drain evidence required')
    append('advance', drain['modeled_available_at_sec'], lower_bound_sec=None, closed=True)
    return commands


def d0_commands(rows, *, duration, hop=.25):
    """Recover the unchanged fixed-cadence D0 predictor pushes and watermarks.

    Both admission rejections and accepted vectors are needed: the final event
    in each dispatch binds its lane-ready time even if no vector was produced.
    The unanalyzed short tail produces no invented model call or prediction.
    """
    if not math.isfinite(duration) or duration <= 0 or hop != .25:
        raise ValueError('Require the admitted D0 duration and fixed 250-ms hop')
    commands, end, ready, seg_serial, vector_serial = [], 0., 0., 0, 0
    roles = set()
    waiting = None
    required_push = ('kind','event_id','observation_id','source_start_sec','source_end_sec',
        'receptive_start_sec','receptive_end_sec','available_at_sec','speech','overlap',
        'evidence_kind','clean_intervals','rms','clipping_fraction','clean_fraction')

    def complete_dispatch():
        if roles != {'short','mature'} or waiting is not None:
            raise ValueError('Incomplete D0 admission/vector census at dispatch')
        commands.append(dict(lane='speaker', operation='advance', modeled_available_at_sec=ready,
            lower_bound_sec=end, closed=False))

    for row in rows:
        kind, p = row['event_type'], row['payload']
        if kind not in ('research_segmentation','research_embedding_admission','research_embedding'):
            raise ValueError('Unexpected D0 sealed component event')
        source = p['source_end_sec']
        if source != end:
            if end: complete_dispatch()
            if abs(source-end-hop) > 1e-7 or source > duration:
                raise ValueError('D0 source dispatch discontinuity')
            end, roles = source, set()
        stamp = p['modeled_available_at_sec']
        if not math.isfinite(stamp) or stamp < source or stamp < ready:
            raise ValueError('D0 modeled clock regressed')
        ready = stamp
        if kind == 'research_segmentation':
            if roles or waiting is not None:
                raise ValueError('D0 segmentation after query admission')
            seg_serial += 1
            event = dict(kind='segmentation', event_id=f'seg:{seg_serial:08d}',
                source_start_sec=p['source_start_sec'], source_end_sec=source,
                available_at_sec=ready, speech=p['speech'], overlap=p['overlap'])
            commands.append(dict(lane='speaker', operation='push', modeled_available_at_sec=ready, event=event))
        elif kind == 'research_embedding_admission':
            role = p['evidence_kind']
            if role not in ('short','mature') or role in roles or waiting is not None:
                raise ValueError('D0 duplicate role or missing admitted vector')
            roles.add(role)
            waiting = role if p['admitted'] else None
        else:
            vector_serial += 1
            if waiting != p['evidence_kind'] or p['event_id'] != f'embedding:{vector_serial:08d}':
                raise ValueError('D0 vector does not match its actual admission')
            event = {k:deepcopy(p[k]) for k in required_push}
            event['vector'] = deepcopy(p['normalized_embedding'])
            commands.append(dict(lane='speaker', operation='push', modeled_available_at_sec=ready, event=event))
            waiting = None
    if end: complete_dispatch()
    if abs(end-math.floor(duration/hop)*hop) > 1e-7:
        raise ValueError('Missing complete D0 dispatches')
    commands.append(dict(lane='speaker', operation='advance', modeled_available_at_sec=ready,
        lower_bound_sec=None, closed=True))
    return commands
