"""Integer live capture extent and independent host bounds; see README_LIVE_TIMING.md."""
from collections import deque
import math

NATIVE_RATE = 48000
MODEL_RATE = 16000
DECIMATION = NATIVE_RATE // MODEL_RATE


class LiveTimingError(RuntimeError):
    def __init__(self, check, evidence):
        self.check, self.evidence = check, evidence
        super().__init__('LIVE_SOURCE_TIMING: '+check)


class CaptureTimeline:
    """One immutable stream-start bound; never anchor on callback arrival jitter.

    Native sample zero is the first admitted frame after counted route priming.
    Stream.start's entry bounds the earliest start of that stream's frame count.
    ADC timestamps and reported latency remain diagnostics, not substituted
    feasibility bounds. An actual input gap/clock inconsistency still fails.
    """
    def __init__(self, metadata, first):
        self.start_ns = metadata.get('stream_start_perf_counter_ns')
        self.priming = getattr(first, 'priming_native_frames', None)
        self.epoch = first.epoch
        if (type(self.start_ns) is not int or self.start_ns <= 0
                or type(self.priming) is not int or self.priming < 0):
            raise LiveTimingError('missing stream-start/sample-origin binding',
                {'stream_start_perf_counter_ns':self.start_ns,'priming_native_frames':self.priming})
        if metadata.get('priming_status_events', 0):
            raise LiveTimingError('priming discontinuity prevents stream/sample clock binding',
                {'priming_status_events':metadata['priming_status_events']})
        self.native_end = self.model_end = 0
        self.last_callback_ns = self.start_ns
        self.rows = deque(maxlen=64)
        self.blocks = 0
        self.max_native_lead_ns = None
        # A causal factor-3 decimator emits native indices 0,3,6,... . Its last
        # output's exclusive model interval can extend two native ticks past
        # the last required input tick. Account for that exact representation
        # offset, separately from FIR group delay or physical latency.
        self.native_origin = self.start_ns/1e9 + self.priming/NATIVE_RATE
        self.origin = self.native_origin - (DECIMATION-1)/NATIVE_RATE

    def metadata(self):
        return dict(source_clock_method='stream_start_counted_native_frames',
            source_clock_confidence='stream_feasibility_lower_bound_not_acoustic_capture_time',
            stream_start_perf_counter_ns=self.start_ns, priming_native_frames=self.priming,
            native_source_epoch_perf_sec=self.native_origin,
            model_interval_lead_native_frames=DECIMATION-1,
            source_epoch_monotonic_sec=self.origin,
            reported_latency_role='diagnostic_only_not_a_hard_input_age_bound',
            host_clock_mapping='explicit_perf_counter_stream_start_and_callback',
            epoch=self.epoch)

    def accept(self, block, now_ns):
        callback = block.callback_perf_counter_ns
        n, start, model_start = block.native_frames, block.native_start_frame, block.model_start_sample
        model_end = model_start + len(block.audio)
        native_end = start + n
        current=getattr(block,'callback_current_time_seconds',None)
        row = dict(block=self.blocks, epoch=block.epoch, native_start_frame=start,
            native_end_frame=native_end, model_start_sample=model_start, model_end_sample=model_end,
            callback_perf_counter_ns=callback, consumer_perf_counter_ns=now_ns,
            adc_time_seconds=block.adc_time_seconds if math.isfinite(block.adc_time_seconds) else None,
            callback_current_time_seconds=current if isinstance(current,(int,float)) and math.isfinite(current) else None,
            resampler_delay_seconds=block.resampler_delay_seconds)
        def fail(check):
            row['failed_check']=check
            self.rows.append(row)
            raise LiveTimingError(check, dict(row))
        if block.epoch != self.epoch or block.priming_native_frames != self.priming:
            fail('stale epoch or changed priming origin')
        if any(type(v) is not int for v in (n,start,model_start,callback,now_ns)) or n <= 0:
            fail('invalid integer sample/timestamp extent')
        if start != self.native_end or model_start != self.model_end:
            fail('noncontiguous native/model sample extent')
        if model_end != (native_end+DECIMATION-1)//DECIMATION:
            fail('converted sample extent disagrees with causal decimator phase')
        if callback < self.last_callback_ns or now_ns < callback:
            fail('callback/consumer host clock mismatch')
        # Integer comparison: no rounded float timeline, tolerance, clamping,
        # inferred ADC clock offset, or consumer delay may conceal an overrun.
        lead = ((self.priming+native_end)*1_000_000_000
                - (callback-self.start_ns)*NATIVE_RATE)
        row['native_lead_ns']=lead/NATIVE_RATE
        if lead > 0:
            fail('native source support is ahead of stream-start frame bound')
        self.native_end, self.model_end = native_end, model_end
        self.last_callback_ns = callback
        self.blocks += 1
        self.rows.append(row)
        self.max_native_lead_ns = max(-math.inf if self.max_native_lead_ns is None else self.max_native_lead_ns, lead/NATIVE_RATE)
        return row

    def snapshot(self):
        return {**self.metadata(), 'blocks':self.blocks, 'native_frames_accepted':self.native_end,
            'model_samples_accepted':self.model_end, 'max_native_lead_ns':self.max_native_lead_ns,
            'recent_blocks':list(self.rows), 'recent_blocks_bound':self.rows.maxlen}
