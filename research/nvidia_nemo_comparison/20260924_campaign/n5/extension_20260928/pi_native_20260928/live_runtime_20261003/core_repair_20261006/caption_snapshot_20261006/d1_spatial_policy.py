"""D1 source-clock adapter over the pinned C079/C060 tracker. See README_IDENTITY_MODES.md.

Native activity chooses eligible contiguous waveform and coarse caption ownership.
The same S6C voice/spatial math as D0 associates that delivered embedding. Names
still pass through the separate model-bound resolver, without new calibration.
"""
from contextlib import nullcontext
from copy import deepcopy
import time

from identity_modes import finite

SPATIAL_MODES = frozenset(('spatial_assisted', 'strongly_spatial_assisted',
    'spatial_selected', 'strongly_spatial_selected'))


class SourceClockSpatialPolicy:
    def __init__(self, tracker, provider):
        if provider is None or not callable(getattr(provider, 'evidence_for_window', None)):
            raise ValueError('D1 spatial association requires the retained source-window beam/BMI provider')
        self.tracker, self.provider = tracker, provider
        self.calls, self.with_cue = 0, 0
        self.last = None

    def associate(self, native_decision, event):
        start, end, available = (event.get(k) for k in
            ('source_start_sec', 'source_end_sec', 'available_at_sec'))
        if not all(finite(v) for v in (start, end, available)) or not 0 <= start < end <= available+1e-8:
            raise ValueError('D1 spatial adapter requires actual arrived finite source-window evidence')
        # RecordedMotion's pinned guarded context supplies the historical pose;
        # live providers conservatively reject any older motion generation.
        source_context = getattr(self.provider, '_query', None)
        context = source_context(end) if source_context is not None else nullcontext(True)
        with context as source_ready:
            cue = self.provider.evidence_for_window(start, end, end) if source_ready else None
            if cue is not None and (not finite(cue.available_at_sec) or cue.available_at_sec > end):
                raise ValueError('Spatial provider exposed a cue delivered after the source window')
            result = self.tracker.update(event['vector'], start, end, end, spatial=cue,
                speech=event.get('speech') is True, overlap=event.get('overlap') is True,
                evidence_kind=event['evidence_kind'], clean_intervals=event['clean_intervals'],
                observation_id=event['event_id'])
        result['native_tracker_id'] = native_decision.get('tracker_id')
        result['native_activity_decision'] = deepcopy(native_decision)
        result['spatial_association'] = dict(schema='just-peachy.d1-source-spatial.v1',
            source_start_sec=start, source_end_sec=end, model_available_at_sec=available,
            model_delay_from_source_sec=available-end, tracker_policy_clock_sec=end,
            cue_available_at_sec=cue.available_at_sec if cue is not None else None,
            cue_age_on_source_clock_sec=end-cue.available_at_sec if cue is not None else None,
            cue_delivered=cue is not None, native_track_id=result['native_tracker_id'],
            shared_track_id=result.get('tracker_id'),
            clock_basis='source-window callback delivery; native model delay is separate',
            motion_generation_guard=True, current_position_claim=False,
            acoustic_synchronization_claim=False, voice_gate_retained=True,
            policy='actual pinned S6CTracker with effective C079/C060 configuration')
        self.calls += 1
        self.with_cue += int(cue is not None)
        self.last = deepcopy(result['spatial_association'])
        return result

    def snapshot(self):
        return dict(adapter='core_repair_d1_source_spatial_v1', calls=self.calls,
            delivered_cues=self.with_cue, last=deepcopy(self.last),
            motion_resets=getattr(self.tracker, 'location_resets', 0),
            tracker=self.tracker.snapshot(), calibrated_person_probability=False)


def make_policy(config, provider):
    from edge_speech_pipeline.research_tracking_v3 import S6CTracker
    from app.live_spatial import MotionFrameTracker
    tracker = S6CTracker(config)
    if getattr(provider, 'motion', None) is not None:
        tracker = MotionFrameTracker(tracker, provider.motion)
    return SourceClockSpatialPolicy(tracker, provider)


def revise_spatial_caption_spans(engine, utterance_id=None, blocking=True):
    """Pinned D1 coarse-span revision contract with the actual shared track ID.

The native singleton activity boundary gate is unchanged. Source-overlapping
delivered embeddings alone can supply shared track/name fields. Mixed native
activity remains unavailable; no majority vote or word boundary is invented.
"""
    if getattr(engine, '_s6d_presentation', None) is None:
        return
    if not engine._n2_lock.acquire(blocking=blocking):
        return
    try:
        from d1_caption_snapshot import selected_identity_rows
        for row in selected_identity_rows(engine._s6d_presentation, utterance_id):
            if utterance_id is not None and row['utterance_id'] != utterance_id:
                continue
            groups = {}
            for span in row.get('word_spans', []):
                a, b = span['source_start_sec'], span['source_end_sec']
                key = (span['id'], row['text_revision_id'])
                if b < engine._n2_timeline.end-engine._n2_timeline.reserve_sec and key in engine._n2_span_signatures:
                    continue
                association = engine._n2_associations.get((a,b))
                if association is None:
                    association = engine._n2_timeline.associate(a,b)
                    if association is not None:
                        engine._n2_associations[(a,b)] = association
                if association is None:
                    continue
                slot = association['slot']
                native_track = f'{engine._session_dir.name}:nemotron-slot-{slot}' if slot is not None else None
                mapped = engine.n2_name_map.source_assignment(native_track, a, b) if native_track is not None else None
                track = mapped['track_id'] if mapped is not None else None
                anonymous = ('Speaker_'+str(track)) if track is not None else 'Unknown'
                name = mapped or {}
                label = name.get('display_label') or 'Unknown'
                signature = (track, label, name.get('profile_id'), name.get('naming_state'), association['reason'])
                if engine._n2_span_signatures.get(key) == signature:
                    continue
                engine._n2_span_signatures[key] = signature
                groups.setdefault((a,b,signature), dict(ids=[], association=association, name=name,
                    native_track=native_track, anonymous=anonymous))['ids'].append(span['id'])
            for (a,b,signature), group in groups.items():
                engine._n2_revision += 1
                track, label, pid, state, reason = signature
                name = group['name']
                now = engine._s7_observed_clock.relative()
                payload = dict(event_id=f'n2-caption:{engine._n2_revision:08d}', utterance_id=row['utterance_id'],
                    target_text_revision_id=row['text_revision_id'], target_span_ids=group['ids'],
                    source_start_sec=a, source_end_sec=b, target_source_start_sec=row['source_start_sec'],
                    target_source_end_sec=row['source_end_sec'], available_at_sec=now, latest_label_time=now,
                    identity_version=engine._n2_revision, latest_label=label, replacement_tracker_id=track,
                    latest_anonymous_label=group['anonymous'], latest_known_profile_id=pid,
                    latest_known_name=name.get('name'), latest_naming_state=state or 'unknown',
                    evidence_ids=[name['event_id']] if name else [], association=group['association'],
                    native_tracker_id=group['native_track'], association_reason=reason,
                    timing_kind='ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT', changes_raw_words=False,
                    name_evidence_end_sec=name.get('source_end_sec'),
                    publication_freshness='historical_caption_annotation_only',
                    shared_spatial_policy='C079/C060 source-window S6CTracker; native activity remains boundary gate')
                engine._emit('transcript_label_revision', b, payload)
        if len(engine._n2_span_signatures) > 16384:
            retained = {(s['id'], r['text_revision_id']) for r in selected_identity_rows(engine._s6d_presentation) for s in r.get('word_spans', [])}
            engine._n2_span_signatures = {k:v for k,v in engine._n2_span_signatures.items() if k in retained}
        if len(engine._n2_associations) > 16384:
            floor = engine._n2_timeline.end-engine._n2_timeline.reserve_sec
            engine._n2_associations = {k:v for k,v in engine._n2_associations.items() if k[1] >= floor}
    finally:
        engine._n2_lock.release()
