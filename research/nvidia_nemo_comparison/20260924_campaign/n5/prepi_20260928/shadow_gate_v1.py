"""Non-destructive causal energy diagnostics. See README_SHADOW.md."""
import hashlib
import math
import time

import numpy as np


class ShadowGate:
    """Observe delivered PCM; never return a replacement block or a skip command.

    G01 exact-zero, G02 -55 dBFS and G03 -45 dBFS proposals use a 300 ms
    initial guard and 300 ms trailing guard. Thresholds are frozen diagnostics,
    not a speech detector. No future block or final transcript enters decisions.
    """

    def __init__(self, sample_rate=16000, guard_samples=4800):
        if sample_rate != 16000 or type(guard_samples) is not int or guard_samples < 0:
            raise ValueError('Expected 16 kHz and nonnegative integer guard')
        self.rate = sample_rate
        self.guard = guard_samples
        self.samples = 0
        self.blocks = 0
        self.pcm_hash = hashlib.sha256()
        self.cost_seconds = 0.0
        self.rows = []
        self.methods = {name: dict(retain_until=guard_samples, proposed_samples=0,
                                  low_energy_samples=0, current_pause=0, pauses=[])
                        for name in ('G01', 'G02', 'G03')}

    def observe(self, block):
        before = time.perf_counter()
        values = np.asarray(block)
        if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
            raise ValueError('Nonempty finite mono block required')
        if len(values) > 320 or np.max(np.abs(values)) > 1.0:
            raise ValueError('Expected at most 20 ms normalized source PCM')
        # Source is PCM16 decoded exactly by SoundFile; reject lossy input.
        pcm = np.rint(values.astype(np.float64) * 32768)
        if (pcm < -32768).any() or (pcm > 32767).any() or not np.array_equal(pcm / 32768, values):
            raise ValueError('Source must be exactly representable PCM16')
        pcm_bytes = pcm.astype('<i2').tobytes()
        self.pcm_hash.update(pcm_bytes)
        start, end = self.samples, self.samples + len(values)
        rms = float(np.sqrt(np.mean(values.astype(np.float64) ** 2)))
        dbfs = 20 * math.log10(rms) if rms else None
        quiet = dict(G01=not np.any(values), G02=rms < 10 ** (-55 / 20),
                     G03=rms < 10 ** (-45 / 20))
        proposed = {}
        for name, state in self.methods.items():
            if quiet[name]:
                state['low_energy_samples'] += len(values)
                state['current_pause'] += len(values)
            else:
                if state['current_pause']:
                    state['pauses'].append(state['current_pause'])
                    state['current_pause'] = 0
                state['retain_until'] = end + self.guard
            # Partial guard overlap retains the entire block; never round toward skip.
            proposed[name] = bool(quiet[name] and start >= state['retain_until'])
            if proposed[name]:
                state['proposed_samples'] += len(values)
        self.rows.append(dict(start_sample=start, end_sample=end, rms_dbfs=dbfs,
                              proposed_skip=proposed, actually_skipped=False))
        self.samples = end
        self.blocks += 1
        self.cost_seconds += time.perf_counter() - before

    def report(self):
        methods = {}
        for name, state in self.methods.items():
            pauses = state['pauses'] + ([state['current_pause']] if state['current_pause'] else [])
            methods[name] = dict(proposed_skip_samples=state['proposed_samples'],
                                 proposed_skip_fraction=state['proposed_samples'] / self.samples if self.samples else 0,
                                 below_threshold_samples=state['low_energy_samples'],
                                 above_threshold_duty_cycle=1 - state['low_energy_samples'] / self.samples if self.samples else None,
                                 below_threshold_runs_samples=pauses)
        return dict(status='SHADOW_ONLY_ALL_AUDIO_RETAINED', samples=self.samples,
                    sample_rate=self.rate, blocks=self.blocks, source_pcm_sha256=self.pcm_hash.hexdigest(),
                    initial_and_trailing_guard_samples=self.guard, observer_wall_seconds=self.cost_seconds,
                    actually_skipped_samples=0, proposed_methods=methods, rows=list(self.rows),
                    speech_truth_used=False, ASR_cues_used=False, applied_gate_qualified=False,
                    scope='Energy duty cycle is not speech duty cycle; proposals are not measured inference savings')


def install(pipeline_module):
    """Instrument only saved FileSource journal appends in an isolated test process.

    Original arrays reach the original journal first. Errors fail the diagnostic
    run instead of silently disabling observations. All other journal operations
    delegate unchanged. This installs no production gate or microphone hook.
    """
    original = pipeline_module.FileSource
    observers = []

    class JournalProxy:
        def __init__(self, journal, observer):
            self.journal, self.observer = journal, observer

        def append(self, block):
            result = self.journal.append(block)
            self.observer.observe(block)
            return result

        def __getattr__(self, name):
            return getattr(self.journal, name)

    class ObservedFileSource(original):
        def start(self):
            observer = ShadowGate()
            observers.append(observer)
            self.journal = JournalProxy(self.journal, observer)
            return super().start()

    pipeline_module.FileSource = ObservedFileSource
    return observers
