"""Capture unchanged application ASR loops, without UI. README_ASR_BANK.md."""
from collections import Counter
import json
import math
import time
from types import SimpleNamespace


class SequentialJournal:
    """Expose only requested forward chunks to the real streaming loop."""
    def __init__(self, samples):
        self.samples=samples;self.committed_samples=len(samples);self.finished=True
        self.duration_sec=len(samples)/16000;self.delivered_samples=0;self.reads=0
    def read(self, cursor, size):
        if cursor!=self.delivered_samples or type(size) is not int or size<=0:
            raise ValueError('Only forward source reads are admitted')
        block=self.samples[cursor:cursor+size]
        self.delivered_samples+=len(block);self.reads+=bool(len(block))
        return block


class _ASRSink:
    def __init__(self):self.events=[]
    def push(self, event, lane):
        if lane!='asr' or event['kind']!='asr':raise ValueError('Unexpected non-ASR predictor input')
        self.events.append(event)


class _PunctuationQueue:
    def __init__(self, capture):self.capture=capture;self.jobs=[]
    def submit(self, job):
        if len(self.jobs)>=4096:raise ValueError('Punctuation job budget exceeded')
        self.jobs.append((job,self.capture._research_asr_event_serial,self.capture._research_asr_available_sec))
    def finish(self):
        """Same final-only formatting calls/order, explicit separate model clock.

        Execution is delayed until ASR closure for isolated component collection.
        The resulting modeled queue time is never an observed UI completion time.
        """
        ready=0.
        for (asr,text,end,utterance),serial,submitted in self.jobs:
            start=time.perf_counter();result=asr.punctuate(text);finished=time.perf_counter()
            ready=max(ready,submitted)+(finished-start)
            self.capture._emit('component_final_punctuation',end,dict(utterance_id=f'utterance:{utterance:06d}',
                input_event_id=f'asr:{serial:08d}',raw_text=text,punctuation=result,
                modeled_available_at_sec=ready,modeled_asr_submission_at_sec=submitted,
                actual_call_started_elapsed_sec=start-self.capture._started_monotonic,
                actual_call_finished_elapsed_sec=finished-self.capture._started_monotonic,
                execution='actual formatting calls after isolated ASR closure; not observed app queue timing'))


def capture_type(pipeline_engine):
    """Reuse frozen _transcript_event/_publish_final and both real lane methods."""
    class Capture(pipeline_engine):
        def __init__(self, profile, config, wave, log, binding=None):
            if (config.sample_rate!=16000 or config.input_gain!=1. or config.asr_threads!=1
                    or config.punctuation_threads!=1 or profile.xvf.mode not in ('off','none','disabled')):
                raise ValueError('Nominal single-thread mono16k once-gained nonspatial ASR required')
            self.config=config;self._research_profile=profile;self.log=log
            self._journal=SequentialJournal(wave);self._state='RUNNING';self.error=None
            self._research_v2=self._research_v3=True;self._scheduler=_ASRSink()
            self._research_asr_available_sec=0.;self._research_utterance_start_sec=0.
            self._research_asr_event_serial=0;self._started_monotonic=time.perf_counter()
            self._s7_trace=None;self._s6d=None;self._s6d_punctuation=_PunctuationQueue(self)
            self.resident=SimpleNamespace(asr_document=binding)
            self._telemetry={};self.counts=Counter();self.watermarks=[]
        def _emit(self, kind, source, payload):
            if sum(self.counts.values())>=100000:raise ValueError('ASR event budget exceeded')
            self.log.write(json.dumps(dict(event_type=kind,source_time_sec=source,payload=payload),
                ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
            self.counts[kind]+=1
        def _fail(self, error):
            self.error=error;self._state='FAILED'
        def _scheduler_advance(self, lane, source, available):
            if lane!='asr':raise ValueError('Unexpected speaker dependency')
            self.watermarks.append(dict(source=None if math.isinf(source) else source,
                closed=math.isinf(source),modeled_available=available))
        def finish_capture(self):
            if self.error is not None:raise RuntimeError(self.error)
            if (self._journal.delivered_samples!=self._journal.committed_samples
                    or not self.watermarks or not self.watermarks[-1]['closed']
                    or self._telemetry.get('asr_cursor_sec')!=self._journal.duration_sec):
                raise ValueError('ASR source census or lane closure failed')
            self._s6d_punctuation.finish()
            observations=self._scheduler.events;seen=set();finals=[]
            for event in observations:
                uid=event['utterance_id']
                if uid in seen:raise ValueError('ASR observation after its final')
                if event['final']:seen.add(uid);finals.append(event['text'])
            return dict(input_samples=self._journal.delivered_samples,source_reads=self._journal.reads,
                event_counts=dict(self.counts),predictor_observations=len(observations),final_utterances=finals,
                raw_final_text=' '.join(t.strip() for t in finals if t.strip()),telemetry=self._telemetry,
                punctuation_calls=len(self._s6d_punctuation.jobs),closed_watermark=self.watermarks[-1],
                observed_live_latency_qualified=False,integrated_N4_cells=0)
    return Capture
