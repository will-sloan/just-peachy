"""Two bounded native file runs with explicitly SYNTHETIC angle fixtures.

See README_SPATIAL_INTEGRATION.md. No microphone, hardware or user profiles.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timezone
import hashlib
import math
from pathlib import Path
import queue
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
import soundfile as sf
from app.paths import atomic_json, default_models_root, pipeline_config, sha256
from app.people import PersonalGallery
from app.pipeline import PrototypeEngine, ResidentModels, SPATIAL_PARENTS, effective_profile
from edge_speech_pipeline.research_profiles import DeliveredSpatialObservation


class SyntheticAngleReplay:
    """Declared 8 Hz / 70-degree sensor fixture on the paced file source clock.

    Records exist independently of model query timing. Delayed computation
    never refreshes their source or delivery timestamps. This is not hardware
    telemetry, an acoustic calibration, or a source-direction truth label.
    """
    def __init__(self,duration):
        self.origin=None
        self.records=[DeliveredSpatialObservation(angle_deg=70.,available_at_sec=i/8+.01,
            energy=1.,reliability=.9,valid=True,sequence=i,
            source_start_sec=i/8,source_end_sec=i/8) for i in range(1,int(duration*8)+1)]
        self.ends=[r.source_end_sec for r in self.records]
        self.calls=self.returned=self.legacy_calls=0
        self.sha256=None

    def bind_origin(self,origin):
        if self.origin is not None:raise ValueError('Fixture origin already bound')
        self.origin=origin

    def evidence(self,start,now):
        self.legacy_calls+=1
        raise AssertionError('Spatial integration must use the source-window provider hook')

    def evidence_for_window(self,start,end,now):
        self.calls+=1
        if self.origin is None:raise AssertionError('Native source clock was not bound')
        if now>time.perf_counter()-self.origin+1e-6:
            raise AssertionError('Predictor requested unavailable future fixture evidence')
        index=bisect_right(self.ends,end)-1
        while index>=0:
            row=self.records[index]
            if row.source_end_sec<start:return None
            if row.available_at_sec<=now:
                self.returned+=1
                return row
            index-=1
        return None


def run_mode(mode,wav,config,models,gallery):
    duration=sf.info(wav).duration
    provider=SyntheticAngleReplay(duration)
    profile=effective_profile('balanced',mode,'O0')
    engine=PrototypeEngine(config,models,profile,gallery,mode,spatial_provider=provider)
    counts=Counter();cue_reasons=Counter();qualified=0;lineage=Counter()
    started=time.perf_counter();deadline=started+90.
    try:
        engine.start_prepared_file(wav)
        while True:
            if time.perf_counter()>deadline:raise TimeoutError('Bounded native run exceeded90s')
            try:
                event=engine.events.get(timeout=.1)
                counts[event.event_type]+=1
                if event.event_type=='speaker_decision':
                    decision=event.payload.get('decision',event.payload)
                    cue=decision.get('cue',{})
                    cue_reasons[cue.get('reason','no_cue_record')]+=1
                    qualified+=int(cue.get('qualified_bearing_deg') is not None)
                    lineage.update(row['event'] for row in decision.get('lineage',[]))
            except queue.Empty:pass
            watcher=engine._finalization_thread
            if watcher is not None and not watcher.is_alive() and engine.events.empty():break
        engine.wait_for_completion(10)
        engine.record_s6d_consumer_closure('PROTO1 bounded synthetic-angle native integration check; event queue drained')
        if engine.state!='COMPLETED':raise AssertionError('Native pipeline did not complete: '+engine.state)
        if counts['fatal']:raise AssertionError('Native pipeline emitted a fatal error')
        if provider.calls==0 or provider.returned==0 or qualified==0:
            raise AssertionError('No qualified synthetic cue reached the native tracker; do not relax freshness')
        return {'mode':mode,'state':engine.state,'status':'PASS','source_seconds':duration,
            'wall_seconds':round(time.perf_counter()-started,3),'event_counts':dict(counts),
            'provider_window_calls':provider.calls,'provider_records_returned':provider.returned,
            'provider_legacy_calls':provider.legacy_calls,'qualified_tracker_cues':qualified,
            'cue_reasons':dict(cue_reasons),'tracker_lineage_counts':dict(lineage),
            'session_path':str(engine.session_dir),'model_loads_after_run':{
                'asr':models.asr_loads,'speaker':models.speaker_loads,'streams':models.streams}}
    except BaseException:
        try:engine.stop()
        finally:
            try:engine.wait_for_completion(15)
            except Exception:pass
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wav',type=Path,required=True,help='Existing already-gained mono16k PCM16 WAV')
    parser.add_argument('--data-root',type=Path,required=True,help='Fresh private directory outside the prototype')
    parser.add_argument('--models',type=Path,default=default_models_root())
    parser.add_argument('--start-sec',type=float,default=0.)
    parser.add_argument('--seconds',type=float,default=12.,help='Bounded 4..12 second contiguous copy')
    args=parser.parse_args()
    if not math.isfinite(args.seconds) or not 4<=args.seconds<=12:
        parser.error('--seconds must be in [4,12]')
    if not math.isfinite(args.start_sec) or args.start_sec<0:parser.error('--start-sec must be nonnegative')
    root=args.data_root.resolve()
    if root==ROOT or ROOT in root.parents:parser.error('--data-root must be outside the application')
    if root.exists():parser.error('--data-root must be fresh; existing evidence is not overwritten')
    source=args.wav.resolve(strict=True)
    info=sf.info(source)
    if (info.samplerate,info.channels,info.subtype)!=(16000,1,'PCM_16'):
        parser.error('--wav must already be mono16k PCM16, without conversion or gain')
    start=round(args.start_sec*16000);frames=round(args.seconds*16000)
    if start+frames>info.frames:parser.error('Requested contiguous span exceeds the existing WAV')
    root.mkdir(parents=True,exist_ok=False)
    summary={'schema':'proto1_native_spatial_fixture.v1','status':'RUNNING',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'telemetry_kind':'SYNTHETIC_FIXED_70_DEGREE_8HZ_FIXTURE_NOT_HARDWARE',
        'hardware_opened':False,'user_profile_store_opened':False,'native_runs':[],
        'source':{'path':str(source),'sha256':sha256(source),'source_frames':info.frames,
                  'sample_rate':16000,'copy_start_sample':start,'copy_frames':frames},
        'source_code_sha256':{str(p.relative_to(ROOT)):sha256(p) for p in (
            Path(__file__).resolve(),ROOT/'app/pipeline.py',
            ROOT/'vendor/edge_speech_pipeline/research_scheduler_v3.py')},
        'scope':'Runtime wiring/model reuse only; no spatial accuracy, enrollment accuracy, beam alignment or field-performance claim.'}
    receipt=root/'SPATIAL_INTEGRATION_CHECK.json'
    atomic_json(receipt,summary)
    try:
        with sf.SoundFile(source) as handle:
            handle.seek(start);samples=handle.read(frames,dtype='int16')
        wav=root/'existing_speech_contiguous_copy.wav'
        sf.write(wav,samples,16000,subtype='PCM_16')
        summary['copy']={'path':str(wav),'sha256':sha256(wav),'sample_sha256':hashlib.sha256(samples.tobytes()).hexdigest()}
        config=pipeline_config(root,args.models)
        gallery=PersonalGallery([],config.asset('redimnet2_b2_fp32').sha256,
            {'source':'explicit_empty_synthetic_integration_gallery','tap':'O0','sample_rate':16000})
        models=ResidentModels()
        for mode in SPATIAL_PARENTS:
            summary['native_runs'].append(run_mode(mode,wav,config,models,gallery))
            atomic_json(receipt,summary)
        if (models.asr_loads,models.speaker_loads,models.streams)!=(1,1,2):
            raise AssertionError('Native model sessions were unnecessarily reloaded between spatial modes')
        summary.update(status='PASS',shared_model_loads={'asr':models.asr_loads,'speaker':models.speaker_loads,
            'streams':models.streams},empty_gallery=True)
    except Exception as exc:
        summary.update(status='FAIL',error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        atomic_json(receipt,summary)
        print(str(receipt),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
