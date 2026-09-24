"""Receipt-bound live adapter for the existing S6C tracker; see README_SPATIAL.md.

No geometry truth, new inference or acoustic timestamp calibration. Numerical
fusion reuses S6A selected-processed cues for both taps and S6C tracker gates.
"""
from collections import deque, OrderedDict
from copy import deepcopy
import math
import threading
import time

from .beam_diagnostics import BEAMS, FIELD_COUNTS, native_angle_degrees
from edge_speech_pipeline.research_profiles import DeliveredSpatialObservation

ANGLE = 'AEC_AZIMUTH_VALUES'
ENERGY = 'AEC_SPENERGY_VALUES'
SELECTED = 'AUDIO_MGR_SELECTED_AZIMUTHS'
RECEIPT_LIMIT = .25  # Existing S4/S6A freshness and transaction contract.
DISPLAY_LIMIT = .75  # Existing S6D direction display age.


def motion_reference(snapshot):
    return (snapshot.get('frame_generation'), snapshot.get('unsafe_generation')) if snapshot else None


class MotionFrameTracker:
    """Clear only spatial memory on the tracker dispatcher, never the sensor thread.

    Retains the existing C079/C060 voice tracks, prototypes and identity rules.
    A new frame cannot be compared to old-frame track bearings or quarantine.
    """
    def __init__(self, target, motion):
        self.target, self.motion = target, motion
        self.reference = motion_reference(motion.snapshot())
        self.location_resets = 0

    def __getattr__(self, name): return getattr(self.target, name)

    def update(self, *args, **kwargs):
        reference = motion_reference(self.motion.snapshot())
        if reference != self.reference:
            for track in list(self.target.tracks)+list(self.target.archive.values()):
                track.location = None; track.location_at = -math.inf
            for key, value in dict(pending_angle=None, pending_since=0., pending_last=-math.inf,
                    last_cue_stamp=-math.inf, last_cue_sequence=None, innovation=0.,
                    innovation_anchor=None, innovation_alarm=False, sensor_credit=1.,
                    contradictions=0, recovery=0, quarantine_at=-math.inf, last_cue_audit_end=-math.inf).items():
                setattr(self.target, key, value)
            self.reference = reference; self.location_resets += 1
            kwargs['spatial'] = None  # A cue obtained before this transition cannot cross it.
        return self.target.update(*args, **kwargs)


class LiveSpatialProvider:
    def __init__(self, tap, tracker_config, *, enabled=False, display=False, clock=time.perf_counter, motion=None):
        self.tap, self.config = tap, tracker_config
        self.enabled, self.display, self.clock = bool(enabled), bool(display), clock
        self.origin = None; self.live = None; self._lock = threading.RLock(); self.retain_native = False
        self.motion = motion
        self._pending = deque(maxlen=256); self._history = deque(maxlen=1024)
        self._fields = {}; self._positions = OrderedDict(); self._speech = None
        self._last_received = -math.inf; self._last_audio = -1.; self._sequence = 0
        self._counts = dict(receipts=0, rejected_receipts=0, pending_overflow=0,
                            mapped_cues=0, valid_cues=0, queries=0, eligible_queries=0,
                            future_or_stale_queries=0, associations=0)
        self._last_gate = 'Waiting for live XVF telemetry'
        self._latest_track = None

    def attach(self, live):
        self.live = live
        live.spatial_observer = self.receive
        live.spatial_fast = self.enabled or self.display

    def bind_origin(self, origin):
        with self._lock:
            if self.origin is not None or not math.isfinite(origin):
                raise ValueError('Live spatial epoch must be bound once')
            self.origin = float(origin)

    def set_display(self, enabled):
        self.display = bool(enabled)
        diagnostic = getattr(self.live, 'beam_diagnostics', None)
        if diagnostic is not None:
            diagnostic.set_fast(self.enabled or self.display)

    def receive(self, command, values, started, completed):
        """Runs on the telemetry worker, not PortAudio or a model thread."""
        with self._lock:
            if (command not in FIELD_COUNTS or len(values) != FIELD_COUNTS[command]
                    or not all(math.isfinite(v) for v in (started, completed))
                    or completed < started or completed < self._last_received):
                self._counts['rejected_receipts'] += 1
                return
            self._last_received = completed
            self._counts['receipts'] += 1
            if len(self._pending) == self._pending.maxlen:
                self._counts['pending_overflow'] += 1
            self._pending.append((command, tuple(values), float(started), float(completed)))

    def advance_audio(self, block):
        """Map delivered telemetry to its first containing/later real callback.

        This is the retained S6A host-to-callback delivery rule. The callback's
        sample end is an availability bound, not a claimed DSP receptive span.
        """
        stamp = getattr(block, 'callback_perf_counter_ns', None)
        if stamp is None or self.origin is None:
            return
        callback = stamp/1e9
        sample_end = (block.model_start_sample+len(block.audio))/16000
        with self._lock:
            if sample_end <= self._last_audio:
                return
            self._last_audio = sample_end
            while self._pending and self._pending[0][3] <= callback:
                command, values, started, completed = self._pending.popleft()
                self._fields[command] = dict(values=values, started=started, completed=completed)
                if command != SELECTED:
                    continue
                self._sequence += 1
                angle, automatic = (native_angle_degrees(value) for value in values)
                energy_row = self._fields.get(ENERGY)
                energy = None
                if energy_row and self._recent_row(energy_row, completed, RECEIPT_LIMIT):
                    candidate = energy_row['values'][3]
                    if isinstance(candidate, (int, float)) and math.isfinite(candidate):
                        energy = float(candidate)
                delay = callback-completed
                reliability = 1. if automatic is None or angle is None else max(.2, 1.-abs(angle-automatic)/90.)
                reliability *= max(0., 1.-delay/RECEIPT_LIMIT)
                valid = (angle is not None and completed-started <= RECEIPT_LIMIT
                         and delay <= RECEIPT_LIMIT and (energy is None or energy > 0))
                reference = None
                if self.motion is not None:
                    reference = motion_reference(self.motion.snapshot())
                    angle, weight = self.motion.transform(angle, completed)
                    reliability *= weight
                    valid = (valid and angle is not None and weight > 0
                             and reference == motion_reference(self.motion.snapshot()))
                observation = DeliveredSpatialObservation(angle_deg=angle,
                    available_at_sec=callback-self.origin, energy=energy,
                    reliability=reliability, valid=valid, sequence=self._sequence)
                self._history.append(dict(observation=observation, mapped_end=sample_end,
                    received=completed, callback=callback, delay=delay,
                    motion_reference=reference,
                    **({'native_fields':deepcopy(self._fields)} if self.retain_native else {})))
                self._counts['mapped_cues'] += 1
                self._counts['valid_cues'] += int(valid)

    @staticmethod
    def _recent_row(row, now, limit):
        return (0 <= now-row['completed'] <= limit
                and 0 <= row['completed']-row['started'] <= RECEIPT_LIMIT)

    def evidence(self, source_start_sec, source_end_sec):
        return self.evidence_for_window(source_start_sec, source_end_sec, source_end_sec)

    def evidence_for_window(self, source_start_sec, source_end_sec, available_at_sec):
        with self._lock:
            self._counts['queries'] += 1
            max_age = self.config.direction_max_age_sec
            # Search past audio support only; later inference cannot borrow a
            # fresh angle received after the window it is trying to identify.
            row = next((r for r in reversed(self._history)
                        if r['mapped_end'] <= source_end_sec+1e-9
                        and r['observation'].available_at_sec <= available_at_sec), None)
            observation = row['observation'] if row else None
            diagnostic = getattr(self.live, 'beam_diagnostics', None)
            connected = diagnostic is None or diagnostic.snapshot().get('state') in ('WAITING', 'RUNNING')
            motion = self.motion.snapshot() if self.motion is not None else None
            motion_ready = motion is None or (motion.get('valid') is True
                and row is not None and row.get('motion_reference') == motion_reference(motion))
            valid = bool(motion_ready and connected and row and row['mapped_end'] >= source_start_sec
                and source_end_sec-row['mapped_end'] <= max_age
                and observation.valid
                and 0 <= available_at_sec-observation.available_at_sec <= max_age
                and observation.reliability >= self.config.minimum_spatial_reliability)
            if valid:
                self._counts['eligible_queries'] += 1
                self._last_gate = 'Recent cue eligible; existing voice/location tracker decides its weight'
                return observation
            self._counts['future_or_stale_queries'] += 1
            self._last_gate = 'Voice only: no eligible, fresh cue for this audio window'
            return None

    def observe_segmentation(self, payload):
        if self.origin is None:
            return
        end = payload.get('source_end_sec')
        if isinstance(end, (int, float)) and math.isfinite(end):
            with self._lock:
                self._speech = dict(end=end, speech=payload.get('speech') is True,
                                    overlap=payload.get('overlap') is True)

    def observe_decision(self, payload):
        """Project actual voice decisions; angle never creates a name here."""
        if self.origin is None:
            return
        decision = payload.get('decision', payload)
        track = decision.get('tracker_id')
        start, end = payload.get('source_start_sec'), payload.get('source_end_sec')
        now = payload.get('input_available_at_sec', payload.get('available_at_sec'))
        if track is None or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (start, end, now)):
            return
        if decision.get('reason') == 'audio_gate_reject' or not decision.get('clean_intervals'):
            return
        # Match the same causal audio span even in ordinary voice-only modes.
        reference = motion_reference(self.motion.snapshot()) if self.motion is not None else None
        observation = self.evidence_for_window(start, end, now)
        if observation is None:
            return
        cue = decision.get('cue', {})
        seat = (decision.get('identity') or {}).get('seat')
        if self.enabled and not seat and (cue.get('qualified_bearing_deg') is None or cue.get('reliability', 0) <= 0):
            return
        identity = decision.get('identity') or {}
        profile = identity.get('known_profile_id') if identity.get('naming_state') == 'confirmed' else None
        name_now = payload.get('available_at_sec',now) if seat else now
        name_stamp = identity.get('name_evidence_available_at_sec') if seat else now if identity.get('query_executed') else identity.get('name_evidence_available_at_sec')
        if not isinstance(name_stamp, (int, float)) or not 0 <= name_now-name_stamp <= 2.:
            profile = None  # Existing S6D bounded name age; no angle refresh.
        name = identity.get('known_name') if profile else None
        label = name or decision.get('anonymous_label') or 'Unknown'
        if seat and identity.get('assignment') == 'seat_assumed' and name:label += ' · seat assumed'
        if label == 'Unknown':
            return
        with self._lock:
            if self.motion is not None and reference != motion_reference(self.motion.snapshot()): return
            old = self._positions.get(track)
            bearing = observation.angle_deg
            # Display position uses the same existing location update/decay
            # constants. It is a projection; it never feeds tracker learning.
            if old is not None and old.get('motion_reference') == reference:
                alpha = self.config.location_learning_rate
                bearing = (1-alpha)*old['angle_deg']+alpha*bearing
            self._positions[track] = dict(track_id=track, label=label, profile_id=profile,
                angle_deg=bearing, source_end_sec=end, available_at_sec=now,
                name_evidence_at=name_stamp,
                observed_host=self.clock(), reliability=observation.reliability,
                assignment=identity.get('assignment'), seat_assumption=identity.get('assignment')=='seat_assumed',
                estimated=True, association_status='estimated', observation_sequence=observation.sequence)
            self._positions[track]['motion_reference'] = reference
            self._positions.move_to_end(track)
            while len(self._positions) > self.config.max_tracks:
                self._positions.popitem(last=False)
            self._counts['associations'] += 1
            self._latest_track = track

    def invalidate_positions(self):
        with self._lock:
            self._pending.clear(); self._history.clear(); self._positions.clear(); self._speech = None

    def snapshot(self):
        now = self.clock()
        diagnostic = getattr(self.live, 'beam_diagnostics', None)
        raw = diagnostic.snapshot() if diagnostic else {'state':'OFF', 'arrows':[]}
        motion = self.motion.snapshot() if self.motion is not None else None
        active = raw.get('state') in ('RUNNING', 'WAITING') and (motion is None or motion['valid'])
        with self._lock:
            fields, positions = deepcopy(self._fields), deepcopy(list(self._positions.values()))
            speech, counters, message = deepcopy(self._speech), dict(self._counts), self._last_gate
            latest_track = self._latest_track
        relative = now-self.origin if self.origin is not None else None
        speech_fresh = bool(active and speech and relative is not None
                            and 0 <= relative-speech['end'] <= DISPLAY_LIMIT)
        speaking = bool(speech_fresh and speech['speech'] and not speech['overlap'])
        energies = fields.get(ENERGY)
        energy_recent = energies is not None and self._recent_row(energies, now, DISPLAY_LIMIT)
        selected_id = 'selected_auto' if self.tap == 'O0' else 'processed_output'
        arrows = []
        for beam in BEAMS:
            field = fields.get(beam['field'])
            if not field:
                continue
            angle = native_angle_degrees(field['values'][beam['index']])
            age = now-field['completed']
            if angle is None or age < 0 or age > self.config.position_decay_sec:
                continue
            energy_index = beam['index'] if beam['field'] == ANGLE else 3
            energy = energies['values'][energy_index] if energy_recent else None
            fresh = active and self._recent_row(field, now, DISPLAY_LIMIT)
            if self.motion is not None:
                angle, _ = self.motion.transform(angle, field['completed'])
                if angle is None: continue
            arrows.append({**beam, 'angle_deg':angle, 'age_sec':age, 'fresh':fresh,
                           'selected':beam['id'] == selected_id, 'energy':energy,
                           'speech':speaking if fresh and beam['id'] == selected_id else False})
        associations = []
        for row in positions:
            age = relative-row['source_end_sec'] if relative is not None else math.inf
            if (not active or age < 0 or age > self.config.position_decay_sec
                    or row.get('motion_reference') != motion_reference(motion)):
                continue
            fresh = speaking and age <= DISPLAY_LIMIT and row['track_id'] == latest_track
            if row.get('profile_id') and relative-row['name_evidence_at'] > 2.:
                row.update(label='Speaker_'+str(row['track_id']), profile_id=None)
            row.update(age_sec=age, fresh=fresh, speaking=fresh,
                       reliability=row['reliability']*math.exp(-age/self.config.position_decay_sec),
                       association_status='estimated_current' if fresh else 'last_known')
            associations.append(row)
        selected = next((r for r in arrows if r['selected'] and r['fresh']), None)
        if motion is not None:
            message = ('Relative front-side frame · yaw %.1f°' % motion['yaw_deg']) if motion['valid'] else motion['reason']
        return dict(state=raw.get('state', 'OFF'), message=message, motion=motion,
            coordinate_frame='relative_anchor_front_assumed' if motion and motion['compensation'] else 'device',
            fusion_enabled=self.enabled, counters=counters, arrows=arrows,
            associations=associations[-self.config.max_tracks:], speech=speaking,
            speech_known=speech_fresh, energy=selected.get('energy') if selected else None,
            selected_angle_deg=selected['angle_deg'] if selected else None,
            stale_after_seconds=DISPLAY_LIMIT, position_decay_seconds=self.config.position_decay_sec,
            cue_mapping='S6A selected-processed for both taps; actual callback delivery mapping; DSP time unknown',
            names_are_voice_matches=True, association_is_estimated=True)
