"""Optional external reference input. No EQ, normalization or audio scaling.

Start and finish must run on the same owner thread. Callback samples and timing
are buffered in bounded preallocated storage; only a closed stream is archived.
"""
import copy
import json
import math
from pathlib import Path
import re
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

from .core import devices, now, sha, write_json
from .playback import _ComApartment, STATUS_NAMES

MAX_CALIBRATION_BYTES = 10 * 1024 * 1024
RAIL_THRESHOLD = 1 - 2 ** -15
BINDING_KEYS = ('device_name', 'hostapi_name', 'channel', 'sample_rate_hz',
                'microphone_model', 'microphone_serial', 'interface_gain_note')


def reference_endpoint_problem(device, inventory=None):
    """Pure endpoint policy; does not query devices or open a stream."""
    if device.get('max_input_channels', 0) < 1:
        return 'Selected endpoint has no input channels'
    name = str(device.get('name', ''))
    if re.search(r'sound\s+mapper|primary\s+sound|^default\b', name, re.I):
        return 'Select a named reference microphone, not a Windows default mapper'
    if re.search(r'xvf|xmos|echo.*\(\s*x', name, re.I):
        return 'The XVF endpoint cannot also be the external reference microphone'
    if device.get('is_loopback') or re.search(r'loopback|stereo\s+mix|what\s+u\s+hear|wave\s+out\s+mix', name, re.I):
        return 'Select a physical microphone input, not a loopback or speaker mix'
    return None


def _text(value, name, default=None):
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(name + ' must be text')
    return value.strip() or default


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(name + ' must be finite and positive')
    return float(value)


def _calibration_path(value, record=False):
    value = _text(value, 'Calibration path')
    if value is None:
        return None
    try:
        path = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError('Calibration file is unavailable: ' + str(error)) from error
    allowed = {'.json'} if record else {'.txt', '.csv', '.json', '.cal'}
    if not path.is_file() or path.suffix.lower() not in allowed:
        raise ValueError('Calibration must be a supported regular file')
    if path.stat().st_size > MAX_CALIBRATION_BYTES:
        raise ValueError('Calibration file exceeds 10 MB')
    return str(path)


def _validate_record(path, config):
    with Path(path).open('rb') as handle:
        raw = handle.read(MAX_CALIBRATION_BYTES + 1)
    if len(raw) > MAX_CALIBRATION_BYTES:
        raise ValueError('Calibration record exceeds 10 MB')
    record = json.loads(raw.decode('utf-8-sig'),
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite calibration record')))
    if not isinstance(record, dict) or not isinstance(record.get('input_configuration'), dict):
        raise ValueError('Calibration record needs its input_configuration binding')
    scale = _positive(record.get('pa_per_fs'), 'Calibration record sensitivity')
    if config['sensitivity_pa_per_fs'] is None or not math.isclose(scale, config['sensitivity_pa_per_fs'], rel_tol=1e-9, abs_tol=0):
        raise ValueError('Explicit sensitivity must match the selected calibration record')
    for key in BINDING_KEYS:
        if key not in record['input_configuration'] or record['input_configuration'][key] != config.get(key):
            raise ValueError('Calibration record does not match current ' + key)


def validate_reference(config, inventory=None):
    """Validate explicit input identity and calibration binding before capture."""
    if config is None:
        return {'enabled': False}
    if not isinstance(config, dict):
        raise ValueError('Reference configuration must be an object')
    enabled = config.get('enabled', False)
    if not isinstance(enabled, bool):
        raise ValueError('Reference enabled must be true or false')
    if not enabled:
        return {'enabled': False}
    c = copy.deepcopy(config)
    index = c.get('device_index')
    channel = c.get('channel', 1)
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise ValueError('Select an explicit reference input')
    if isinstance(channel, bool) or not isinstance(channel, int) or not 1 <= channel <= 8:
        raise ValueError('Reference channel must be a 1-based integer from 1 to 8')
    rate = c.get('sample_rate_hz', 48000)
    if isinstance(rate, bool) or rate != 48000:
        raise ValueError('Reference capture requires 48000 Hz')
    duration = _positive(c.get('duration_seconds', 330), 'Reference duration bound')
    if duration > 330:
        raise ValueError('Reference duration bound cannot exceed 330 seconds')
    name = _text(c.get('device_name'), 'Reference input name')
    host = _text(c.get('hostapi_name'), 'Reference host API')
    if name is None or host is None:
        raise ValueError('Reference input name and host API must identify the selected endpoint')
    c.update(enabled=True, channel=channel, sample_rate_hz=48000, duration_seconds=duration,
             device_name=name, hostapi_name=host, microphone_model=_text(c.get('microphone_model'), 'Microphone model', 'Unknown (user not supplied)'))
    for key in ('microphone_serial', 'interface_gain_note', 'placement_note'):
        c[key] = _text(c.get(key), key)
    sensitivity = c.get('sensitivity_pa_per_fs')
    c['sensitivity_pa_per_fs'] = None if sensitivity is None else _positive(sensitivity, 'Sensitivity')
    c['calibration_file_path'] = _calibration_path(c.get('calibration_file_path'))
    c['calibration_record'] = _calibration_path(c.get('calibration_record'), record=True)
    if c['calibration_record']:
        _validate_record(c['calibration_record'], c)
    inventory = devices() if inventory is None else inventory
    matches = [d for d in inventory if d.get('index') == index]
    if len(matches) != 1:
        raise ValueError('Reference input index is unavailable or ambiguous')
    device = matches[0]
    problem = reference_endpoint_problem(device, inventory)
    if problem:
        raise ValueError(problem)
    if device.get('name') != name or device.get('hostapi_name') != host:
        raise ValueError('Reference endpoint changed; refresh and select it again')
    if channel > device['max_input_channels']:
        raise ValueError('Selected reference channel is outside this endpoint')
    c['opened_channels'] = channel
    return c


def _selected_quality(samples, rate):
    count = len(samples)
    finite_count = nonzero = near_rail = 0
    total = squares = 0.0
    low, high = math.inf, -math.inf
    for at in range(0, count, 262144):
        block = np.asarray(samples[at:at + 262144], dtype=np.float64)
        valid = block[np.isfinite(block)]
        finite_count += len(valid)
        if len(valid):
            total += float(valid.sum()); squares += float(np.dot(valid, valid))
            low = min(low, float(valid.min())); high = max(high, float(valid.max()))
            nonzero += int(np.count_nonzero(valid))
            near_rail += int(np.count_nonzero(np.abs(valid) >= RAIL_THRESHOLD))
    mean = total / finite_count if finite_count else None
    rms = math.sqrt(squares / finite_count) if finite_count else None
    ac_rms = math.sqrt(max(0, squares / finite_count - mean * mean)) if finite_count else None
    zero_windows = sum(not np.any(samples[at:at + rate]) for at in range(0, count - rate + 1, rate))
    return {'frames': count, 'finite_samples': finite_count, 'nonfinite_samples': count - finite_count,
            'nonzero_samples': nonzero, 'varies': bool(finite_count and high > low),
            'minimum_fs': low if finite_count else None, 'maximum_fs': high if finite_count else None,
            'peak_abs_fs': max(abs(low), abs(high)) if finite_count else None,
            'mean_fs': mean, 'rms_fs': rms, 'ac_rms_fs': ac_rms,
            'near_full_scale_samples': near_rail, 'near_full_scale_threshold_fs': RAIL_THRESHOLD,
            'fully_zero_one_second_windows': int(zero_windows),
            'rail_scope': 'Conservative near-full-scale check; native ADC bit depth is not inferred from float32 storage'}


def estimate_sensitivity(samples, rate, known_spl_db, frequency_hz):
    """Derive an unverified user-calibrator scale from a stable mono window.

    Broadband RMS after DC removal is used for analysis only. Original audio is
    never modified. Caller must establish level, physical coupling and gain.
    """
    rate = _positive(rate, 'Sample rate')
    if isinstance(known_spl_db, bool) or not isinstance(known_spl_db, (int, float)) or not math.isfinite(known_spl_db) or not 40 <= known_spl_db <= 140:
        raise ValueError('Known calibrator level must be supplied between 40 and 140 dB SPL')
    frequency_hz = _positive(frequency_hz, 'Calibrator frequency')
    if not 20 <= frequency_hz <= 20000 or frequency_hz >= rate / 2:
        raise ValueError('Calibrator frequency must be 20–20000 Hz and below Nyquist')
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim != 1 or len(x) / rate < 2 or not np.isfinite(x).all():
        raise ValueError('Use a finite mono calibration window at least two seconds long')
    if np.max(np.abs(x)) >= RAIL_THRESHOLD:
        raise ValueError('Calibration tone reaches digital full scale; reduce input gain')
    dc = float(x.mean()); centered = x - dc
    rms = float(np.sqrt(np.mean(centered * centered)))
    if not math.isfinite(rms) or rms <= 0:
        raise ValueError('Calibration recording is zero or constant')
    window_frames = int(round(rate))
    level_windows = []
    for at in range(0, len(x) - window_frames + 1, window_frames):
        window = x[at:at + window_frames]
        level_windows.append(float(np.sqrt(np.mean((window - window.mean()) ** 2))))
    if len(level_windows) < 2 or min(level_windows) <= 0:
        raise ValueError('Calibration needs two nonzero one-second level windows')
    level_spread_db = 20 * math.log10(max(level_windows) / min(level_windows))
    if level_spread_db > .5:
        raise ValueError('Calibrator level is unstable: one-second AC RMS spread exceeds 0.5 dB')
    power = np.abs(np.fft.rfft(centered * np.hanning(len(x)))) ** 2
    power[0] = 0
    frequencies = np.fft.rfftfreq(len(x), 1 / rate)
    peak_frequency = float(frequencies[int(np.argmax(power))])
    if abs(peak_frequency - frequency_hz) > frequency_hz * .02:
        raise ValueError('Dominant frequency does not match the specified calibrator within 2%')
    width = max(frequency_hz * .02, 2 * rate / len(x))
    tonal_fraction = float(power[np.abs(frequencies - frequency_hz) <= width].sum() / power.sum())
    if tonal_fraction < .8:
        raise ValueError('Calibration window is not dominated by a stable calibrator tone')
    pascals = 20e-6 * 10 ** (known_spl_db / 20)
    scale = pascals / rms
    return {'pa_per_fs': scale, 'db_spl_at_rms_1': 20 * math.log10(scale / 20e-6),
            'known_spl_db': float(known_spl_db), 'frequency_hz': frequency_hz,
            'dominant_frequency_hz': peak_frequency, 'tonal_power_fraction': tonal_fraction,
            'duration_seconds': len(x) / rate, 'sample_rate_hz': rate,
            'one_second_ac_rms_fs': level_windows, 'one_second_level_spread_db': level_spread_db,
            'maximum_allowed_one_second_level_spread_db': .5,
            'rms_fs': rms, 'rms_basis': 'Broadband AC RMS after removing the window mean; analysis only',
            'dc_mean_fs': dc, 'peak_abs_fs': float(np.max(np.abs(x))),
            'physical_calibrator_and_coupling_verified': False,
            'provenance': 'User-supplied calibrator level and input gain; bind to the exact microphone/interface/channel/settings',
            'frequency_response_correction_applied': False}


class ReferenceCapture:
    def __init__(self, folder, config, stop):
        self.folder = Path(folder); self.config = copy.deepcopy(config); self.stop = stop
        self.ready = threading.Event(); self.finished = threading.Event()
        self._stream = None; self._com = None; self._result = None
        self._data = None; self._records = None; self._count = 0; self._callbacks = 0
        self._owner = None; self._started = False; self._owns_folder = False
        self._error = None; self._callback_error = None; self._limit_reached = False
        self._cancelled = False; self._start_ns = None; self._end_ns = None
        self._receipt = {}; self._calibration = {}

    def _snapshot_calibration(self):
        self._calibration = {'frequency_response_applied': False, 'sensitivity_applied_to_audio': False,
                             'sensitivity_pa_per_fs': self.config.get('sensitivity_pa_per_fs'),
                             'sensitivity_provenance': 'User-supplied, physically unverified', 'files': []}
        for key, name in [('calibration_file_path', 'frequency_response_original'), ('calibration_record', 'calibration_record_original')]:
            if not self.config.get(key):
                continue
            source = Path(self.config[key]); target = self.folder / 'calibration' / (name + source.suffix.lower())
            target.parent.mkdir(exist_ok=True)
            copied = 0
            with source.open('rb') as incoming, target.open('xb') as outgoing:
                for block in iter(lambda: incoming.read(1048576), b''):
                    copied += len(block)
                    if copied > MAX_CALIBRATION_BYTES:
                        raise ValueError('Calibration file grew beyond 10 MB during snapshot')
                    outgoing.write(block)
            if key == 'calibration_record':
                _validate_record(target, self.config)
            self._calibration['files'].append({'kind': key, 'original_path': str(source),
                'snapshot_path': target.relative_to(self.folder).as_posix(), 'sha256': sha(target), 'bytes': copied})
        (self.folder / 'calibration').mkdir(exist_ok=True)
        write_json(self.folder / 'calibration' / 'provenance.json', self._calibration)

    def _callback(self, indata, frames, timing, status):
        try:
            if self._callbacks >= len(self._records):
                raise RuntimeError('Reference callback receipt capacity exceeded')
            if frames <= 0 or indata.shape != (frames, self.config['opened_channels']):
                raise ValueError('Unexpected reference input buffer shape')
            take = min(frames, len(self._data) - self._count)
            row = self._records[self._callbacks]
            row['first_frame'] = self._count; row['received_frames'] = frames; row['retained_frames'] = take
            row['host_monotonic_ns'] = time.perf_counter_ns()
            row['input_adc_time_s'] = timing.inputBufferAdcTime; row['current_time_s'] = timing.currentTime
            row['status_mask'] = sum(1 << bit for bit, name in enumerate(STATUS_NAMES) if getattr(status, name))
            self._data[self._count:self._count + take] = indata[:take]
            self._count += take; self._callbacks += 1
            self._cancelled = self._cancelled or self.stop.is_set()
            self._limit_reached = self._count >= len(self._data)
            if take:
                self.ready.set()
        except BaseException as error:
            self._callback_error = repr(error)
            raise sd.CallbackAbort
        if self._cancelled or self._limit_reached:
            raise sd.CallbackStop

    def start(self):
        if self._owner is not None:
            raise RuntimeError('Reference capture was already started')
        self._owner = threading.get_ident()
        try:
            self.config = validate_reference(self.config)
            if not self.config['enabled']:
                self.ready.set(); return self
            self.folder.mkdir(parents=True, exist_ok=False); self._owns_folder = True
            write_json(self.folder / 'configuration.json', self.config)
            self._snapshot_calibration()
            frames = math.ceil(self.config['duration_seconds'] * 48000)
            self._data = np.empty((frames, self.config['opened_channels']), dtype=np.float32)
            capacity = 1024 + math.ceil(self.config['duration_seconds'] * 2000)
            self._records = np.zeros(capacity, dtype=[('first_frame', 'i8'), ('received_frames', 'i8'),
                ('retained_frames', 'i8'), ('host_monotonic_ns', 'i8'), ('input_adc_time_s', 'f8'),
                ('current_time_s', 'f8'), ('status_mask', 'u1')])
            self._com = _ComApartment(self._receipt); self._com.open()
            sd.check_input_settings(device=self.config['device_index'], channels=self.config['opened_channels'],
                                    samplerate=48000, dtype='float32')
            self._stream = sd.InputStream(device=self.config['device_index'], channels=self.config['opened_channels'],
                samplerate=48000, dtype='float32', latency=.15, blocksize=0, callback=self._callback,
                finished_callback=self.finished.set)
            self._receipt.update(actual_stream_latency_s=float(self._stream.latency),
                actual_channels=int(self._stream.channels), actual_sample_rate_hz=float(self._stream.samplerate))
            if self._receipt['actual_channels'] != self.config['opened_channels'] or self._receipt['actual_sample_rate_hz'] != 48000:
                raise RuntimeError('Reference stream configuration does not match its request')
            self._start_ns = time.perf_counter_ns(); self._receipt['start_utc'] = now()
            self._stream.start(); self._started = True
            return self
        except BaseException as error:
            self._error = repr(error)
            raise

    def wait_ready(self, timeout=2):
        timeout = float(timeout)
        if not math.isfinite(timeout) or not 0 <= timeout <= 5:
            raise ValueError('Reference readiness wait must be between 0 and 5 seconds')
        return self.ready.wait(timeout)

    def finish(self):
        if self._result is not None:
            return self._result
        if self._owner is not None and self._owner != threading.get_ident():
            return {'status': 'FAIL', 'stream_closed': False, 'frames': self._count,
                    'quality': {}, 'error': 'Reference finish must run on its start thread'}
        errors = [v for v in (self._error, self._callback_error) if v]
        closed = self._stream is None
        if self._stream is not None:
            try:
                if self._started and self._stream.active:
                    self._stream.stop(ignore_errors=False)
            except BaseException as error:
                errors.append('stop: ' + repr(error))
            try:
                self._stream.close(ignore_errors=False); closed = True
            except BaseException as error:
                errors.append('close: ' + repr(error))
        self._end_ns = time.perf_counter_ns()
        if closed and self._com is not None:
            try:
                self._com.close()
            except BaseException as error:
                errors.append('COM cleanup: ' + repr(error))
        enabled = bool(self.config and self.config.get('enabled'))
        result = {'status': 'FAIL', 'enabled': enabled, 'stream_closed': closed, 'frames': self._count,
                  'start_monotonic_ns': self._start_ns, 'end_monotonic_ns': self._end_ns,
                  'quality': {}, 'error': '; '.join(errors) or None}
        if not closed:
            result['error'] = result['error'] or 'Reference stream did not close; evidence cannot be finalized'
            self._result = result; return result
        if not enabled:
            result['status'] = 'PASS' if not errors else 'FAIL'
            self._result = result; return result
        if not self._owns_folder:
            result['error'] = result['error'] or 'Reference capture never owned an evidence folder'
            self._result = result; return result
        rows = []
        for record in ([] if self._records is None else self._records[:self._callbacks]):
            row = {name: record[name].item() for name in self._records.dtype.names}
            row['status_flags'] = [name for bit, name in enumerate(STATUS_NAMES) if row['status_mask'] & (1 << bit)]
            for key in ('input_adc_time_s', 'current_time_s'):
                if not math.isfinite(row[key]): row[key] = None
            rows.append(row)
        flags = [row for row in rows if row['status_mask']]
        try:
            selected = self._data[:self._count, self.config['channel'] - 1] if self._data is not None else np.empty(0, np.float32)
            quality = _selected_quality(selected, 48000)
            quality.update(callback_status_events=flags, callback_error=self._callback_error,
                duration_bound_reached=self._limit_reached, stop_requested=self._cancelled or self.stop.is_set(),
                quality_applies_to_selected_channel_only=True, selected_channel_1based=self.config['channel'])
            quality['checks'] = {'nonempty': self._count > 0, 'all_finite': quality['nonfinite_samples'] == 0,
                'nonzero': quality['nonzero_samples'] > 0, 'varies': quality['varies'],
                'not_near_full_scale': quality['near_full_scale_samples'] == 0,
                'no_zero_one_second_windows': quality['fully_zero_one_second_windows'] == 0,
                'callback_clean': not flags and not self._callback_error, 'within_duration_bound': not self._limit_reached,
                'not_cancelled': not quality['stop_requested']}
            sensitivity = self.config.get('sensitivity_pa_per_fs')
            quality['user_scale_estimated_spl_db'] = (20 * math.log10(quality['ac_rms_fs'] * sensitivity / 20e-6)
                if sensitivity and quality['ac_rms_fs'] else None)
            quality['absolute_spl_calibration_verified'] = False
            result['quality'] = quality
            result['status'] = 'PASS' if all(quality['checks'].values()) and not errors else 'FAIL'
            if self._count:
                sf.write(self.folder / 'reference_original.wav', self._data[:self._count], 48000, subtype='FLOAT')
                sf.write(self.folder / 'selected_reference.wav', selected, 48000, subtype='FLOAT')
                result['original_audio'] = {'path': 'reference_original.wav', 'sha256': sha(self.folder / 'reference_original.wav')}
                result['selected_audio'] = {'path': 'selected_reference.wav', 'sha256': sha(self.folder / 'selected_reference.wav')}
            metadata = {**self._receipt, 'configuration': self.config, 'frames': self._count,
                'start_monotonic_ns': self._start_ns, 'end_monotonic_ns': self._end_ns, 'stream_closed': closed,
                'callback_count': self._callbacks, 'callback_times': rows,
                'first_callback_monotonic_ns': rows[0]['host_monotonic_ns'] if rows else None,
                'last_callback_monotonic_ns': rows[-1]['host_monotonic_ns'] if rows else None,
                'original_audio_channels': self.config['opened_channels'], 'selected_channel_1based': self.config['channel'],
                'audio_semantics': 'Original float32 values for every opened endpoint channel; selected file is an exact channel extraction',
                'sample_rate_scope': 'Host stream rate; does not prove ADC clock synchronization or native conversion bit depth',
                'calibration': self._calibration, 'timing_scope': 'Host callback/stream bounds and PortAudio ADC estimates; not calibrated acoustic alignment',
                'error': result['error']}
            write_json(self.folder / 'capture.json', metadata)
            write_json(self.folder / 'quality.json', quality)
        except BaseException as error:
            result['status'] = 'FAIL'; result['error'] = '; '.join(errors + ['archive: ' + repr(error)])
        self._data = None; self._records = None
        self._result = result
        return result
