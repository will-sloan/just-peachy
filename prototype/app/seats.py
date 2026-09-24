"""Session-only seating assumptions on existing causal XVF cues. See README_SEATS.md."""
from copy import deepcopy
import math
import threading
import time
import uuid

from .beam_diagnostics import native_angle_degrees
from .live_spatial import LiveSpatialProvider, ANGLE, ENERGY, SELECTED, RECEIPT_LIMIT

DEFAULT_TOLERANCE = 25.  # Retained C079/C060 direction_match_deg, not RIR uncertainty.
MAPPING = 'XMOS v3.2.1 radians; linear folded 0=MIC3, 180=MIC0; S6A selected processed index 0; callback delivery bound, DSP time unknown'


def validate_layout(rows, people=None):
    if not isinstance(rows, list) or len(rows) > 16:
        raise ValueError('Use at most 16 assigned seats')
    result = []; seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - {'person_id', 'angle_deg', 'tolerance_deg'}:
            raise ValueError('Unexpected seat fields')
        pid = row.get('person_id'); angle = row.get('angle_deg'); tolerance = row.get('tolerance_deg', DEFAULT_TOLERANCE)
        if not isinstance(pid, str) or not pid or pid in seen or (people is not None and pid not in people):
            raise ValueError('Seat person must be an existing, unique UUID')
        for value, lo, hi in ((angle, 0., 180.), (tolerance, 1., 45.)):
            if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError('Seat angle must be 0–180 degrees; tolerance 1–45 degrees')
        result.append(dict(person_id=pid, angle_deg=float(angle), tolerance_deg=float(tolerance))); seen.add(pid)
    return result


def collisions(rows):
    return [dict(person_ids=[a['person_id'], b['person_id']],
                 projected_same=abs(a['angle_deg']-b['angle_deg']) < 1e-9,
                 overlap_deg=[max(0., a['angle_deg']-a['tolerance_deg'], b['angle_deg']-b['tolerance_deg']),
                              min(180., a['angle_deg']+a['tolerance_deg'], b['angle_deg']+b['tolerance_deg'])])
            for i, a in enumerate(rows) for b in rows[i+1:]
            if abs(a['angle_deg']-b['angle_deg']) <= a['tolerance_deg']+b['tolerance_deg']]


class StubMotionService:
    """Explicit events only. No configured sensor, GPIO, automatic motion or yaw claim."""
    def __init__(self, callback): self.callback = callback
    def moved(self, reason='manual_tablet_moved'):
        self.callback(reason)


class SeatSession:
    def __init__(self, rows=None, *, strength='soft', acknowledged=False, clock=time.perf_counter):
        self.lock = threading.RLock(); self.clock = clock
        self.rows = validate_layout(rows or [])
        if strength not in ('soft', 'strong'): raise ValueError('Use soft or strong retained spatial settings')
        if collisions(self.rows) and not acknowledged:
            raise ValueError('Resolve overlapping projected regions or explicitly accept ambiguous outcomes')
        self.strength = strength; self.acknowledged = acknowledged
        self.session_id = str(uuid.uuid4()); self.revision = 1; self.released = {}
        self.valid = bool(self.rows); self.anchor_at = clock(); self.reason = 'manual_apply_at_current_location' if self.rows else 're_anchor_required'
        self.motion = StubMotionService(self.invalidate)

    def invalidate(self, reason='manual_tablet_moved'):
        with self.lock:
            self.valid = False; self.revision += 1; self.reason = str(reason)

    def release(self, ids, reason):
        with self.lock:
            for pid in ids:self.released[pid] = str(reason)

    def snapshot(self):
        with self.lock:
            return dict(rows=deepcopy(self.rows), strength=self.strength, valid=self.valid,
                        session_id=self.session_id, revision=self.revision, anchor_monotonic=self.anchor_at,
                        reason=self.reason, collisions=collisions(self.rows), ambiguous_acknowledged=self.acknowledged,
                        released=deepcopy(self.released), mapping=MAPPING, front_back_ambiguous=True, seat_is_identity_proof=False,
                        motion_service='manual/stub; no physical sensor configured')


class SeatSpatialProvider(LiveSpatialProvider):
    def __init__(self, *args, seats, **kwargs):
        super().__init__(*args, **kwargs); self.seats = seats; self.retain_native = True

    def evidence_for_window(self, start, end, available):
        if not self.seats.snapshot()['valid']: return None
        return super().evidence_for_window(start, end, available)

    def seat_evidence(self, start, end, available):
        """Same causal cue, with stricter speech/multiplicity checks for seat naming."""
        cue = self.evidence_for_window(start, end, available)
        detail = dict(valid=False, reason='no_fresh_direction', mapping=MAPPING)
        if cue is None: return None, detail
        with self._lock:
            row = next((r for r in reversed(self._history) if r['observation'].sequence == cue.sequence), None)
            fields = deepcopy(row.get('native_fields', {})) if row else {}
        detail.update(native_fields=fields, angle_deg=cue.angle_deg, reliability=cue.reliability,
                      cue_age_sec=available-cue.available_at_sec, sequence=cue.sequence,
                      mapped_audio_end_sec=row['mapped_end'], received_monotonic=row['received'],
                      callback_monotonic=row['callback'], receipt_delay_sec=row['delay'])
        if row['received'] < self.seats.snapshot()['anchor_monotonic']:
            detail['reason'] = 'cue_predates_anchor'; return None, detail
        energies, bearings = fields.get(ENERGY), fields.get(ANGLE)
        if not all(f and self._recent_row(f, row['received'], RECEIPT_LIMIT) for f in (energies, bearings)):
            detail['reason'] = 'missing_fresh_beam_energy_or_angles'; return None, detail
        angles = [native_angle_degrees(v) for v in bearings['values']]
        detail['native_degrees'] = {ANGLE: angles, SELECTED: [native_angle_degrees(v) for v in fields[SELECTED]['values']]}
        if self.motion is not None:
            angles = [self.motion.transform(angle, bearings['completed'])[0] for angle in angles]
            detail['relative_front_degrees'] = angles
        active = [i for i in (0, 1) if angles[i] is not None and type(energies['values'][i]) in (int, float)
                  and math.isfinite(energies['values'][i]) and energies['values'][i] > 0]
        detail['active_fixed_beams'] = active
        if not active:
            detail['reason'] = 'no_fixed_beam_speech_energy'; return None, detail
        if len(active) == 2 and abs(angles[0]-angles[1]) > self.config.direction_match_deg:
            detail['reason'] = 'multiple_active_bearings_ambiguous'; return None, detail
        if min(abs(cue.angle_deg-angles[i]) for i in active) > self.config.direction_match_deg:
            detail['reason'] = 'processed_direction_energy_mismatch'; return None, detail
        detail.update(valid=True, reason='fresh_processed_direction_and_speech_energy')
        return cue, detail

    def invalidate_positions(self):
        with self._lock:
            self._pending.clear(); self._history.clear(); self._positions.clear(); self._speech = None

    def snapshot(self):
        result = super().snapshot(); result['seating'] = self.seats.snapshot()
        if not result['seating']['valid']:
            result['associations']=[];result['message']='Seat anchor invalid: re-anchor at this location. Captions continue.'
        result['names_are_voice_matches'] = False
        result['association_warning'] = 'Seat assumptions and hybrid voice matches are separately marked; angles never verify identity'
        return result
