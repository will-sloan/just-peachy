"""Read six-case native JSONL without importing a model; README_NATIVE_STREAM_MODELS_V1.md."""
import json
import math
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def review(path, frames):
    path = Path(path)
    require(path.stat().st_size <= 16*1024**2, 'Native output exceeds bound')
    rows = [json.loads(line, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            for line in path.read_text(encoding='utf-8').splitlines()]
    require(rows and rows[0].get('kind') == 'start', 'Missing start')
    start = rows.pop(0)
    require(start.get('schema') == 'n5-native-stream-smoke-v1', 'Wrong schema')
    for key, value in dict(frames=frames, push_frames=1280, sample_rate=16000,
                           gpu=-1, ctc_chunk=.16, ctc_left=1.92, ctc_right=1.92,
                           rnnt_right=1, stop_ms=800).items():
        require(start.get(key) == value, 'Configuration differs: '+key)
    cases = [('empty', 0), ('one_sample', 1), ('short_tail', 1281),
             ('saved_source', frames), ('saved_source_repeat', frames),
             ('saved_source_forced', frames)]
    signatures = {}; counts = []
    for name, length in cases:
        require(bool(rows), 'Missing case')
        opened = rows.pop(0)
        require(opened == dict(kind='case_start', case=name, frames=length), 'Case order/source differs')
        events = []; finals = []; previous = 0; finishing = False
        while rows and rows[0].get('kind') == 'event':
            event = rows.pop(0); sent = event.get('sent_frames')
            require(event.get('case') == name and type(sent) is int and previous <= sent <= length, 'Event source accounting differs')
            previous = sent
            require(type(event.get('is_final')) is bool, 'Final flag missing')
            phase = event.get('phase')
            require(phase in ('push', 'forced_endpoint', 'finish'), 'Unknown drain phase')
            require(not finishing or phase == 'finish', 'Push after finish')
            if phase == 'finish':
                finishing = True
                require(sent == length, 'Early finish')
            if phase == 'forced_endpoint':
                require(name == 'saved_source_forced' and sent == min(197440, length//2), 'Wrong forced endpoint')
            for key in ('audio_processed_seconds_raw', 'confidence_raw'):
                require(type(event.get(key)) in (int, float) and math.isfinite(event[key]), 'Invalid native number')
            hypothesis = event.get('hypothesis')
            require(isinstance(hypothesis, dict) and isinstance(hypothesis.get('text'), str), 'Missing transcript')
            words = hypothesis.get('words')
            require(isinstance(words, list) and len(words) <= 10000, 'Invalid native words')
            for word in words:
                require(isinstance(word.get('text'), str), 'Missing word text')
                for key in ('start_ms', 'end_ms'):
                    require(type(word.get(key)) in (int, float) and math.isfinite(word[key]), 'Invalid native offset')
            if event['is_final']: finals.append(hypothesis)
            events.append(event)
            require(len(events) <= 4000, 'Too many events')
        require(bool(rows), 'Missing stream closure')
        closed = rows.pop(0)
        require(closed == dict(kind='case_closed', case=name, sent_frames=length,
                events=len(events), finals=len(finals), forced_endpoint=name == 'saved_source_forced',
                stream_closed=True), 'Stream closure differs')
        signatures[name] = finals
        counts.append(dict(case=name, frames=length, events=len(events), finals=len(finals)))
    require(signatures['saved_source'] and signatures['saved_source'] == signatures['saved_source_repeat'],
            'Resident state text/word parity failed')
    require(rows == [dict(kind='result', status='PASS_NATIVE_STREAM_CONFORMANCE_ONLY', cases=6,
                         resident_state_parity=True, recognizer_closed=True, N4_accepted=False,
                         N5_complete=False, CM5_tested=False)], 'Missing exact closed terminal or trailing output')
    return dict(status='PASS_EMULATED_NATIVE_ASR_STREAM_ONLY', cases=counts,
                resident_state_parity=True, execution='QEMU_AARCH64_EMULATED',
                GUI_validated=False, CM5_tested=False, N4_accepted=False, N5_complete=False)
