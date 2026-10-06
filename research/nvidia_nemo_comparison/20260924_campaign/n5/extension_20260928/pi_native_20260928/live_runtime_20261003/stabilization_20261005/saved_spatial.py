"""Read-only kept-session spatial replay. See README_SAVED_SPATIAL.md."""
from bisect import bisect_right
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import threading
from types import SimpleNamespace

SCHEMA = 'just-peachy.source-aligned-spatial.v1'
FIELD_COUNTS = {'AEC_AZIMUTH_VALUES': 4, 'AEC_SPENERGY_VALUES': 4,
                'AUDIO_MGR_SELECTED_AZIMUTHS': 2}
RECORD_LIMIT = 4096
CHECKPOINT_INTERVAL = 128
CHECKPOINT_LIMIT = 65536


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate recorded spatial field')
            result[key] = value
        return result
    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('Nonfinite recorded JSON number')
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_float=number,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite recorded JSON')))


def _identity(path):
    info = path.stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _key(row):
    kind = row.get('kind')
    if kind == 'bmi270_pose':
        return row.get('at')
    if kind == 'xvf_observation':
        return row.get('control_completed_monotonic_sec')
    if kind == 'audio_clock_anchor':
        return row.get('model_sample_end')
    return None


class _Timeline:
    """One verification pass; bounded sparse offsets, never the full pose log."""
    def __init__(self, store, session_id, prefix, artifacts, byte_limit):
        self.prefix, self.files, self.points, self.counts = prefix, [], {}, {}
        relative = prefix+'.index.json'
        if relative not in artifacts:
            raise ValueError('Kept session has no completed '+prefix+' index')
        index_path = store._artifact_path(session_id, relative)
        if index_path.stat().st_size > RECORD_LIMIT:
            raise ValueError('Recorded spatial index exceeds its bound')
        index_raw = index_path.read_bytes()
        index = _strict(index_raw)
        expected = {'segment_count', 'segment_pattern', 'accepted_bytes', 'completed_bytes',
                    'error', 'refusal', 'complete'}
        if (type(index) is not dict or set(index) != expected or index['complete'] is not True
                or index['error'] is not None or index['refusal'] is not None
                or type(index['segment_count']) is not int or not 0 < index['segment_count'] <= 1024
                or type(index['completed_bytes']) is not int
                or not 0 < index['completed_bytes'] <= byte_limit
                or index['accepted_bytes'] != index['completed_bytes']
                or index['segment_pattern'] != Path(prefix).name+'.%06d'):
            raise ValueError('Incomplete or malformed recorded spatial writer')
        self.index_pin = (index_path, _identity(index_path), hashlib.sha256(index_raw).hexdigest())
        self.bytes = 0
        self.origin = None
        self.end = None
        self.last_keys = {}
        self.last_audio_end = 0
        for number in range(index['segment_count']):
            name = prefix+'.%06d' % number
            if name not in artifacts:
                raise ValueError('Spatial segment is not an owned session artifact')
            path = store._artifact_path(session_id, name)
            before = _identity(path)
            if before[2] != artifacts[name]['bytes'] or before[2] > 8*1024**2:
                raise ValueError('Recorded spatial segment extent differs')
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                while True:
                    offset = stream.tell()
                    raw = stream.readline(RECORD_LIMIT+1)
                    if not raw:
                        break
                    row = self._decode(raw)
                    digest.update(raw)
                    self.bytes += len(raw)
                    self._validate(row)
                    key = _key(row)
                    if key is not None:
                        kind = row['kind']
                        count = self.counts.get(kind, 0)
                        if count % CHECKPOINT_INTERVAL == 0:
                            points = self.points.setdefault(kind, [])
                            points.append((key, number, offset))
                            if sum(map(len, self.points.values())) > CHECKPOINT_LIMIT:
                                raise ValueError('Recorded spatial sparse-index allocation exhausted')
                        self.counts[kind] = count+1
            if _identity(path) != before:
                raise ValueError('Recorded spatial segment changed during verification')
            self.files.append((path, before, digest.hexdigest()))
        if self.bytes != index['completed_bytes']:
            raise ValueError('Recorded spatial completed byte count differs')
        declared = {name for name in artifacts if name.startswith(prefix+'.')}
        if declared != {prefix+'.index.json'} | {prefix+'.%06d' % n for n in range(len(self.files))}:
            raise ValueError('Unknown or incomplete recorded spatial segment')

    @staticmethod
    def _decode(raw):
        if len(raw) > RECORD_LIMIT or not raw.endswith(b'\n'):
            raise ValueError('Recorded spatial row exceeds its complete-line bound')
        row = _strict(raw)
        if (type(row) is not dict or row.get('schema') != SCHEMA
                or type(row.get('model_sample_rate')) is not int or row['model_sample_rate'] != 16000):
            raise ValueError('Recorded spatial schema/sample rate differs')
        return row

    def _validate(self, row):
        kind = row.get('kind')
        if kind not in ('bmi270_pose', 'xvf_observation', 'audio_clock_anchor',
                        'source_origin', 'reference_changed', 'audio_end_bound'):
            raise ValueError('Unknown recorded spatial observation')
        origin = row.get('source_epoch_monotonic_sec')
        if origin is not None and (not _finite(origin) or origin < 0):
            raise ValueError('Invalid recorded source origin')
        if origin is not None:
            if self.origin is not None and origin != self.origin:
                raise ValueError('Recorded source epoch changed within a session')
            self.origin = origin
        key = _key(row)
        if key is not None:
            if not _finite(key) or key < 0 or key <= self.last_keys.get(kind, -math.inf):
                raise ValueError('Recorded spatial clock is not strictly ordered')
            self.last_keys[kind] = key
        if kind == 'audio_clock_anchor':
            start, end, callback = (row.get(k) for k in
                ('model_start_sample', 'model_sample_end', 'audio_callback_monotonic_sec'))
            if (type(start) is not int or type(end) is not int or start != self.last_audio_end
                    or end <= start or not _finite(callback) or callback < 0
                    or callback <= getattr(self, 'last_callback', -math.inf)):
                raise ValueError('Recorded audio anchors are missing/reordered')
            self.last_audio_end, self.last_callback = end, callback
        elif kind == 'audio_end_bound':
            if self.end is not None or row.get('model_sample_end') != self.last_audio_end:
                raise ValueError('Recorded final audio bound differs')
            self.end = row['model_sample_end']
        elif kind == 'bmi270_pose':
            axis = row.get('axis_xy')
            axis_ok = (type(axis) in (list, tuple) and len(axis) == 2
                       and all(_finite(value) for value in axis))
            if (type(row.get('valid')) is not bool or type(row.get('frame_generation')) is not int
                    or type(row.get('unsafe_generation')) is not int
                    or row['frame_generation'] < 0 or row['unsafe_generation'] < 0
                    or not (axis_ok or (row['valid'] is False and axis is None))
                    or not _finite(row.get('yaw_deg'))
                    or not _finite(row.get('drift_allowance_deg'))
                    or row['drift_allowance_deg'] < 0
                    or row.get('absolute_heading_available') is not False
                    or row.get('absolute_translation_available') is not False):
                raise ValueError('Malformed/unqualified recorded BMI pose')
        elif kind == 'xvf_observation':
            command, values = row.get('command'), row.get('values')
            started, completed = row.get('control_started_monotonic_sec'), row.get('control_completed_monotonic_sec')
            if (command not in FIELD_COUNTS or type(values) is not list
                    or len(values) != FIELD_COUNTS[command]
                    or any(value is not None and not _finite(value) for value in values)
                    or not _finite(started) or not 0 <= started <= completed):
                raise ValueError('Malformed recorded XVF control observation')

    def rows(self, kind=None, after=None):
        number, offset = 0, 0
        if kind is not None and after is not None:
            points = self.points.get(kind, [])
            position = bisect_right(points, (after, math.inf, math.inf))-1
            if position >= 0:
                _, number, offset = points[position]
        for index in range(number, len(self.files)):
            path, before, digest = self.files[index]
            if _identity(path) != before:
                raise ValueError('Pinned recorded spatial file changed before query')
            with path.open('rb') as stream:
                stream.seek(offset if index == number else 0)
                while raw := stream.readline(RECORD_LIMIT+1):
                    row = self._decode(raw)
                    if kind is None or row['kind'] == kind:
                        yield row
            if _identity(path) != before:
                raise ValueError('Pinned recorded spatial file changed during query')

    def at_or_before(self, kind, key):
        result = None
        for row in self.rows(kind, key):
            if _key(row) > key:
                break
            result = row
        return result

    def verify_closed(self):
        for path, before, expected in [self.index_pin, *self.files]:
            if _identity(path) != before:
                raise ValueError('Recorded spatial source changed during replay')
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                while raw := stream.read(65536):
                    digest.update(raw)
            if digest.hexdigest() != expected or _identity(path) != before:
                raise ValueError('Recorded spatial source hash changed during replay')

    def receipt(self):
        return dict(prefix=self.prefix, bytes=self.bytes, rows=dict(self.counts),
                    sparse_checkpoints=sum(map(len, self.points.values())),
                    index_sha256=self.index_pin[2], segments=[dict(bytes=row[1][2], sha256=row[2]) for row in self.files])


class RecordedMotion:
    """Recorded causal pose lookup; identical retained cone/half-plane math."""
    def __init__(self, timeline, *, compensation):
        if type(compensation) is not bool:
            raise ValueError('Explicit recorded-pose replay compensation policy required')
        self.timeline, self.compensation = timeline, compensation
        self.at = timeline.origin
        self.cache = OrderedDict()
        self.lock = threading.RLock()

    def _pose(self, at):
        with self.lock:
            if at in self.cache:
                row = self.cache[at]
                self.cache.move_to_end(at)
            else:
                row = self.timeline.at_or_before('bmi270_pose', at)
                self.cache[at] = row
                while len(self.cache) > 128:
                    self.cache.popitem(last=False)
        return row if row and 0 <= at-row['at'] <= .15 else None

    def snapshot(self):
        row = self._pose(self.at)
        return dict(row or {}, enabled=True, hardware_opened=False, recorded=True,
                    valid=bool(row and row['valid']), compensation=self.compensation,
                    yaw_deg=row['yaw_deg'] if row else 0.,
                    state=row['state'] if row else 'RECORDED_GAP',
                    reason=row['reason'] if row else 'Missing or stale recorded BMI pose',
                    absolute_position_or_heading=False)

    def _eligible(self, at):
        row, current = self._pose(at), self.snapshot()
        if (not row or not row['valid'] or not current['valid']
                or any(row[key] != current.get(key) for key in ('frame_generation', 'unsafe_generation'))):
            return None
        return row

    def transform(self, angle, at):
        row = self._eligible(at)
        if row is None or angle is None:
            return None, 0.
        if not self.compensation:
            return angle, 1.
        from app.inertial_geometry import horizontal_candidates
        candidates = []
        for world in horizontal_candidates(angle, row['axis_xy']):
            if 5. <= world <= 175. and not any(abs(world-other) < 1e-6 for other in candidates):
                candidates.append(world)
        return ((candidates[0], math.exp(-row['drift_allowance_deg']/10.))
                if len(candidates) == 1 else (None, 0.))

    def to_device(self, angle, at):
        row = self._eligible(at)
        if row is None or not _finite(angle):
            return None
        if not self.compensation:
            return angle if 0 <= angle <= 180 else None
        theta = math.radians(angle)
        cosine = row['axis_xy'][0]*math.cos(theta)+row['axis_xy'][1]*math.sin(theta)
        return math.degrees(math.acos(max(-1., min(1., cosine))))


class SavedSpatialViews:
    """Provider API used by the restored engine, with no current hardware access."""
    historical_source_evidence = True
    def __init__(self, source_root, session_id, tracker_config, *, enabled=True,
                 seats=None, compensation=True):
        from storage import SessionStore
        from app.live_spatial import LiveSpatialProvider
        from app.seats import SeatSpatialProvider
        self.store = SessionStore(source_root, read_only=True)
        self.lease = None
        self.closed = False
        self.closure_error = None
        self.source_verified = False
        self.lock = threading.RLock()
        self.cursor = 0
        self.replay_origin = None
        self.seats, self.session_id = seats, session_id
        self.queries = self.replayed_anchors = self.replayed_beams = self.reference_losses = 0
        try:
            self.lease = self.store._session_lease(session_id, shared=True)
            metadata = self.store.read(session_id)
            if metadata.get('status') != 'kept' or metadata['spec']['sample_rate'] != 16000:
                raise ValueError('Saved spatial replay requires a kept mono16k session')
            self.frames = metadata['processed_samples']
            self.metadata_sha256 = hashlib.sha256(json.dumps(metadata, sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            artifacts = {}
            for row in self.store._artifacts(session_id):
                artifacts[row['path']] = row
                if len(artifacts) > 4096:
                    raise ValueError('Recording artifact catalogue exceeds replay bound')
            maximum = metadata['spec']['metadata_reserve_bytes']
            if type(maximum) is not int or not 0 < maximum <= 2**31:
                raise ValueError('Finite recorded metadata allocation required')
            self.poses = _Timeline(self.store, session_id, 'work/motion/orientation.jsonl', artifacts, maximum)
            self.beams = _Timeline(self.store, session_id, 'work/spatial/beam_angles.jsonl', artifacts, maximum)
            if (self.poses.end != self.frames or self.poses.last_audio_end != self.frames
                    or self.poses.origin is None or self.beams.origin != self.poses.origin
                    or not self.poses.counts.get('bmi270_pose')
                    or not self.beams.counts.get('xvf_observation')
                    or self.poses.bytes+self.beams.bytes > maximum):
                raise ValueError('Recorded spatial/audio sample or epoch binding is incomplete')
            self.origin = self.current_clock = self.poses.origin
            self.motion = RecordedMotion(self.poses, compensation=compensation)
            provider = SeatSpatialProvider if seats is not None else LiveSpatialProvider
            arguments = dict(seats=seats) if seats is not None else {}
            self.primary = provider('O0', tracker_config, enabled=enabled, display=True,
                                    clock=lambda:self.current_clock, motion=self.motion, **arguments)
            self.device = LiveSpatialProvider('O0', tracker_config, enabled=False, display=True,
                                             clock=lambda:self.current_clock, motion=None)
            self.primary.bind_origin(self.origin)
            self.device.bind_origin(self.origin)
            diagnostic = SimpleNamespace(snapshot=lambda:dict(state='RUNNING', recorded=True))
            self.primary.live = self.device.live = SimpleNamespace(beam_diagnostics=diagnostic)
            if seats is not None:
                # The operator applies this layout to the original recording's
                # reference, never to the tablet's present physical orientation.
                with seats.lock:
                    seats.anchor_at = self.origin
                    seats.reason = 'manual_layout_for_recorded_array_reference'
            self.anchor_iter = self.poses.rows('audio_clock_anchor')
            self.beam_iter = self.beams.rows('xvf_observation')
            self.next_anchor = next(self.anchor_iter, None)
            self.next_beam = next(self.beam_iter, None)
            self.reference = None
        except BaseException:
            self.close(verify=False)
            raise

    def __getattr__(self, name):
        primary = self.__dict__.get('primary')
        if primary is None:
            raise AttributeError(name)
        return getattr(primary, name)

    def bind_origin(self, origin):
        if not _finite(origin) or origin < 0 or self.replay_origin is not None:
            raise ValueError('Saved replay host epoch must be bound once')
        self.replay_origin = origin

    def advance_samples(self, end):
        """Call BEFORE append exposes these saved audio samples to model readers."""
        if type(end) is not int or not self.cursor <= end <= self.frames or self.closed:
            raise ValueError('Saved spatial cursor must follow its exact recording')
        with self.lock:
            while self.next_anchor is not None and self.next_anchor['model_sample_end'] <= end:
                anchor = self.next_anchor
                callback = anchor['audio_callback_monotonic_sec']
                self.current_clock = self.motion.at = callback
                pose = self.motion.snapshot()
                reference = (pose.get('frame_generation'), pose.get('unsafe_generation'))
                if self.reference is not None and reference != self.reference:
                    self.reference_losses += 1
                    self.invalidate_positions()
                    if self.seats is not None:
                        self.seats.invalidate('recorded_motion_reference_or_safety_changed')
                if pose['valid']:
                    self.reference = reference
                while self.next_beam is not None and self.next_beam['control_completed_monotonic_sec'] <= callback:
                    row = self.next_beam
                    for view in (self.primary, self.device):
                        view.receive(row['command'], row['values'], row['control_started_monotonic_sec'],
                                     row['control_completed_monotonic_sec'])
                    self.replayed_beams += 1
                    self.next_beam = next(self.beam_iter, None)
                block = SimpleNamespace(callback_perf_counter_ns=round(callback*1e9),
                    model_start_sample=anchor['model_start_sample'],
                    audio=range(anchor['model_sample_end']-anchor['model_start_sample']))
                for view in (self.primary, self.device):
                    old_sequence = view._sequence
                    view.advance_audio(block)
                    # The callback is an original delivery availability bound.
                    # Saved playback maps that bound to its authoritative sample
                    # end; it does not infer the DSP's acoustic measurement time.
                    for row in view._history:
                        if row['observation'].sequence > old_sequence:
                            row['recorded_callback_offset_sec'] = row['observation'].available_at_sec
                            row['observation'] = replace(row['observation'],
                                available_at_sec=anchor['model_sample_end']/16000)
                self.replayed_anchors += 1
                self.next_anchor = next(self.anchor_iter, None)
            self.cursor = end

    @contextmanager
    def _query(self, source_end):
        if not _finite(source_end) or not 0 <= source_end <= self.cursor/16000+1e-9:
            yield False
            return
        with self.lock:
            anchor = self.poses.at_or_before('audio_clock_anchor', math.floor(source_end*16000+1e-6))
            prior = self.motion.at
            try:
                if anchor is not None:
                    self.motion.at = anchor['audio_callback_monotonic_sec']
                self.queries += 1
                yield anchor is not None
            finally:
                self.motion.at = prior

    def evidence(self, start, end):
        return self.evidence_for_window(start, end, end)

    def evidence_for_window(self, start, end, available):
        with self._query(end) as ready:
            return self.primary.evidence_for_window(start, end, available) if ready else None

    def seat_evidence(self, start, end, available):
        if self.seats is None:
            return None, dict(valid=False, reason='no_recorded_seat_layout')
        with self._query(end) as ready:
            return (self.primary.seat_evidence(start, end, available) if ready else
                    (None, dict(valid=False, reason='recorded_audio_anchor_gap')))

    def seat_evidence_for_source(self, start, end):
        cue, detail = self.seat_evidence(start, end, end)
        return cue, dict(detail, historical_source_window=True,
            clock_basis='recorded callback delivery mapped to authoritative sample end',
            recorded_session_id=self.session_id, recorded_metadata_sha256=self.metadata_sha256,
            recorded_current_sensor_used=False, dsp_acoustic_timestamp_available=False,
            recorded_model_sample_window=[math.floor(start*16000), math.floor(end*16000)],
            pose_index_sha256=self.poses.index_pin[2], beam_index_sha256=self.beams.index_pin[2])

    def observe_decision(self, payload):
        with self._query(payload.get('source_end_sec')) as ready:
            if ready:
                self.primary.observe_decision(payload)
                self.device.observe_decision(payload)

    def observe_segmentation(self, payload):
        self.primary.observe_segmentation(payload)
        self.device.observe_segmentation(payload)

    def invalidate_positions(self):
        self.primary.invalidate_positions()
        self.device.invalidate_positions()

    def display_snapshot(self):
        with self.lock:
            primary, device = self.primary.snapshot(), self.device.snapshot()
            return dict(device, motion=primary.get('motion'), seating=primary.get('seating'),
                associations=primary.get('associations', []), recorded=True,
                # The retained snapshot already projects association bearings
                # back onto the recorded device axis for the GUI arrows.
                association_reference_frame='device',
                recorded_association_frame='relative_array_reference_at_recording',
                names_are_voice_matches=self.seats is None, association_is_estimated=True,
                replay_source_sample=self.cursor,
                message='Recorded beam/BMI replay; current tablet orientation is not used')

    def receipt(self):
        return dict(schema='just-peachy.saved-spatial-replay.v1', session_id=self.session_id,
            metadata_sha256=self.metadata_sha256, processed_samples=self.frames,
            source_epoch_monotonic_sec=self.origin, current_motion_used=False,
            recorded_axis_compensation=self.motion.compensation,
            dsp_acoustic_timestamp_available=False, absolute_translation_available=False,
            interpolation='none; latest causal pose <=150ms and first later original audio callback',
            callback_alignment='original callback availability mapped to recorded model sample end',
            pose_source=self.poses.receipt(), beam_source=self.beams.receipt(),
            replayed_anchors=self.replayed_anchors, replayed_beams=self.replayed_beams,
            source_queries=self.queries, recorded_reference_losses=self.reference_losses)

    def close(self, *, verify=True):
        if self.closed:
            if self.closure_error is not None:
                raise self.closure_error
            if verify and not self.source_verified:
                raise ValueError('Saved spatial source was closed without final verification')
            return True
        self.closed = True
        errors = []
        try:
            for name in ('anchor_iter', 'beam_iter'):
                iterator = getattr(self, name, None)
                if iterator is not None:
                    iterator.close()
            if verify:
                for name in ('poses', 'beams'):
                    timeline = getattr(self, name, None)
                    if timeline is not None:
                        timeline.verify_closed()
                metadata = self.store.read(self.session_id)
                digest = hashlib.sha256(json.dumps(metadata, sort_keys=True,
                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()
                if digest != self.metadata_sha256:
                    raise ValueError('Kept source metadata changed during spatial replay')
                self.source_verified = True
        except BaseException as exc:
            errors.append(exc)
        if self.lease is not None:
            try:
                self.lease.close()
                self.lease = None
            except BaseException as exc:
                errors.append(exc)
        try:
            self.store.close()
        except BaseException as exc:
            errors.append(exc)
        if errors:
            self.closure_error = errors[0]
            raise self.closure_error
        return True
