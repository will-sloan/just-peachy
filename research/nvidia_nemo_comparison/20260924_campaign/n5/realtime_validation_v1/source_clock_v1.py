"""Causal saved-source release schedules; see README_SOURCE_CLOCK_V1.md."""
import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import time


def natural(value, positive=False):
    if type(value) is not int or value < int(positive):
        raise ValueError('Expected an integer sample count')


def finite(value, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError('Expected a finite nonnegative duration or positive rate')


@dataclass(frozen=True)
class Release:
    start_sample: int
    end_sample: int
    deadline_seconds: float


def schedule(frames, sample_rate=16000, chunk_frames=1600, mode='paced', speed=1.0,
             jitter=(0.0, .020, .080, .200), burst_seconds=2.0):
    """Deadlines relative to stream start; never compress or alter source samples."""
    natural(frames); natural(sample_rate, True); natural(chunk_frames, True)
    finite(speed, True); finite(burst_seconds, True)
    if mode not in ('unpaced', 'paced', 'jitter', 'burst') or not jitter:
        raise ValueError('Unknown delivery mode or empty jitter pattern')
    for delay in jitter: finite(delay)
    previous = 0.0
    for index, start in enumerate(range(0, frames, chunk_frames)):
        end = min(start+chunk_frames, frames)
        source_end = end / sample_rate
        deadline = 0.0 if mode == 'unpaced' else source_end / speed
        if mode == 'jitter':
            deadline += jitter[index % len(jitter)]
        if mode == 'burst':
            deadline = math.ceil(source_end / burst_seconds) * burst_seconds / speed
        deadline = max(previous, deadline)
        previous = deadline
        yield Release(start, end, deadline)


def deliver(releases, consumer, *, clock=time.monotonic, sleep=time.sleep, cancelled=lambda: False):
    """Publish metadata at absolute deadlines; consumer owns queueing and saved PCM.

    This calls no audio API and no model. Slow consumer time is retained in
    actual availability rather than drifting future deadlines or hiding lateness.
    """
    origin = clock(); finite(origin)
    previous_end = 0; previous_deadline = 0.0; previous_clock = origin
    for item in releases:
        natural(item.start_sample); natural(item.end_sample)
        finite(item.deadline_seconds)
        if item.start_sample != previous_end or item.end_sample <= item.start_sample or item.deadline_seconds < previous_deadline:
            raise ValueError('Discontinuous source or deadline regression')
        due = origin + item.deadline_seconds
        while True:
            if cancelled(): return
            now = clock(); finite(now)
            if now < previous_clock: raise ValueError('Monotonic clock regressed')
            previous_clock = now
            if now >= due: break
            sleep(min(.05, due-now))
        # A consumer must be a bounded enqueue; blocking does not pause source time.
        consumer(item, now-origin)
        previous_end = item.end_sample; previous_deadline = item.deadline_seconds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames', type=int, required=True)
    parser.add_argument('--sample-rate', type=int, default=16000)
    parser.add_argument('--chunk-frames', type=int, default=1600)
    parser.add_argument('--mode', choices=('unpaced','paced','jitter','burst'), default='paced')
    parser.add_argument('--speed', type=float, default=1.0)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    if a.frames > 16000*3600 or a.chunk_frames < 160:
        raise ValueError('Planning CLI limited to one hour and at most 100 chunks/second at 16kHz')
    rows = list(schedule(a.frames, a.sample_rate, a.chunk_frames, a.mode, a.speed))
    if len(rows) > 360000: raise ValueError('Plan too large')
    data = dict(status='PLANNED_SOURCE_RELEASE_TIMES_NOT_MEASURED_RUNTIME',
                frames=a.frames, sample_rate=a.sample_rate, chunk_frames=a.chunk_frames,
                mode=a.mode, speed=a.speed, audio_read=False, model_run=False, CM5_tested=False,
                releases=[vars(r) for r in rows])
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, indent=2); stream.write('\n')


if __name__ == '__main__': main()
