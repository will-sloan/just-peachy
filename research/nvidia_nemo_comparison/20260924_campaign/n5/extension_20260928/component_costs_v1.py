"""Bounded per-session call accounting. See README_COMPONENT_COSTS_V1.md."""
from copy import deepcopy
import threading
import time


KEYS = ('model_setup', 'diarizer_setup', 'diarizer_push', 'diarizer_finish',
        'embedding', 'asr_accept', 'asr_reset', 'asr_finish')


class CallCosts:
    """Measure call boundaries without retaining audio, outputs or exceptions."""
    def __init__(self, wall=time.perf_counter, cpu=time.thread_time):
        self._wall, self._cpu = wall, cpu
        self._lock = threading.Lock()
        self._rows = {key: dict(started=0, completed=0, errors=0,
            attempted_samples=0, successful_samples=0, wall_seconds=0.,
            calling_thread_cpu_seconds=0., output_frames=0, zero_output_calls=0)
            for key in KEYS}

    def call(self, key, function, *args, samples=0, **kwargs):
        if key not in self._rows or type(samples) is not int or samples < 0:
            raise ValueError('Unknown counter or invalid sample count')
        with self._lock:
            self._rows[key]['started'] += 1
            self._rows[key]['attempted_samples'] += samples
        wall, cpu = self._wall(), self._cpu()
        ok = False
        frames = None
        try:
            result = function(*args, **kwargs)
            if key in ('diarizer_push', 'diarizer_finish'):
                frames = len(result.probabilities)
            ok = True
            return result
        finally:
            elapsed_cpu, elapsed_wall = self._cpu()-cpu, self._wall()-wall
            with self._lock:
                row = self._rows[key]
                row['completed'] += 1
                row['errors'] += int(not ok)
                row['successful_samples'] += samples if ok else 0
                row['wall_seconds'] += max(0., elapsed_wall)
                row['calling_thread_cpu_seconds'] += max(0., elapsed_cpu)
                if frames is not None:
                    row['output_frames'] += frames
                    row['zero_output_calls'] += int(frames == 0)

    def snapshot(self):
        with self._lock:
            rows = deepcopy(self._rows)
        for row in rows.values():
            row['in_flight'] = row['started']-row['completed']
        return dict(schema='component-call-costs.v1', rows=rows,
            scope='Application call wall time; excludes journal waits, pacing, publication and counter-lock bookkeeping. Model setup is separate.',
            cpu_scope='Calling thread only; native worker thread CPU is not included.',
            setup_scope='model_setup includes ASR/E0 acquisition and stream creation; diarizer_setup includes D1 load or reset.',
            concurrency='Do not sum concurrent call wall times as session elapsed time.',
            embedding_samples='Sum of submitted overlapping query windows, not unique source audio.',
            complete_pipeline_cost=False)
