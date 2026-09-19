"""Continuous host endurance and chronological state replay. README_S6C_LONG_SESSION.md."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import sys
import threading
import time
import traceback
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
from s6c_common import REPORT,PAYLOAD,S6B,admit_work,bind,digest,read,save,utc,verified
from s6c_native_prefix import load_epoch,pcm


def source_bindings():
    names=('s6c_long_session.py','README_S6C_LONG_SESSION.md','s6c_native_prefix.py','s6c_common.py')
    return [bind(Path(__file__).with_name(n)) for n in names]


def import_epoch(spec):
    sys.path.insert(0,str(Path(spec['root'])/'app'))
    from edge_speech_pipeline.research_profiles import ResearchProfile,JsonSpatialProvider
    from edge_speech_pipeline.research_scheduler_v3 import build_s6c_policy
    return ResearchProfile,JsonSpatialProvider,build_s6c_policy


def choose_profile(spec,candidate,asr_tap,identity_tap):
    rows=[r for r in spec['profiles'] if (r['candidate_id'],r['asr_tap'],r['identity_tap'])==(candidate,asr_tap,identity_tap)]
    if len(rows)!=1:raise ValueError('One exact registered candidate/route is required')
    return rows[0]


def fixed_gallery_row(index,binding,candidate):
    eligible=[r for r in index['rows'] if r['manifest']==binding and r['case_id'] is None
        and r['gallery_condition'] in ('FIXED_ROTATION_A','FIXED_ROTATION_B')
        and r['gallery_condition']==candidate['gallery_condition'] and r['enrollment_tier']==candidate['enrollment_tier']]
    if len(eligible)!=1:raise ValueError('Exact registered candidate fixed A/B condition and tier required; no scene-conditional gallery or roster override')
    return eligible[0]


def timeline(rows,minutes,gap_sec,family_by_case):
    if not 30<=minutes<=60 or not 1<=gap_sec<=60:raise ValueError('30..60 minutes and1..60 seconds declared silence required')
    pairs={}
    for r in rows:pairs.setdefault(r['case_id'],{})[r['stream']]=r
    if set(family_by_case)!=set(pairs):raise ValueError('Complete canonical family membership required for source composition')
    families={}
    for case in sorted(pairs):families.setdefault(family_by_case[case],[]).append(case)
    order=[case for group in itertools.zip_longest(*(families[k] for k in sorted(families))) for case in group if case is not None]
    sequence=[];cursor=0
    for case in order:
        pair=pairs[case]
        if set(pair)!={'O0','O1'} or pair['O0']['duration_sec']!=pair['O1']['duration_sec']:raise ValueError('Incomplete equal-origin tap pair')
        samples=round(pair['O0']['duration_sec']*16000)
        if sequence:cursor+=round(gap_sec*16000)
        sequence.append(dict(index=len(sequence),case_id=case,family_id=family_by_case[case],start_sample=cursor,end_sample=cursor+samples,samples=samples,
            gap_before_samples=round(gap_sec*16000) if sequence else 0,inputs={k:pair[k]['audio'] for k in pair},
            pcm_sha256={k:pair[k]['audio_pcm_sha256'] for k in pair},telemetry=pair['O0']['telemetry']))
        cursor+=samples
        if cursor>=minutes*60*16000:break
    if cursor<minutes*60*16000:raise ValueError('Not enough distinct complete cases; repetition and trimming are forbidden')
    return sequence,cursor


def prepare(args):
    import numpy as np
    import soundfile as sf
    epoch_path=REPORT/(args.epoch.upper()+'_EXECUTION_MANIFEST.json');spec=load_epoch(epoch_path)
    root=REPORT/'long_session'/args.version;payload=PAYLOAD/'long_session'/args.version
    if root.exists() or payload.exists():raise ValueError('Fresh long-session namespace required')
    rows=verified(spec['input_index'])['rows'];bank=verified(spec['scene_manifest'])
    family_by_case={r['case_id']:r['family_id'] for r in bank['scenes']}
    sequence,total=timeline(rows,args.minutes,args.gap_sec,family_by_case)
    admit_work(full=False);root.mkdir(parents=True);payload.mkdir(parents=True)
    pcm_hashes={};audio={}
    for tap in ('O0','O1'):
        path=payload/(tap+'_continuous.wav');h=hashlib.sha256()
        with sf.SoundFile(path,mode='x',samplerate=16000,channels=1,subtype='PCM_16',format='WAV') as destination:
            for item in sequence:
                binding=item['inputs'][tap];bind(binding['path'],binding['sha256'])
                if sf.info(binding['path']).subtype!='PCM_16':raise ValueError('Prepared once-gained source must be native PCM16')
                wave,rate=sf.read(binding['path'],dtype='int16',always_2d=True)
                if rate!=16000 or wave.shape!=(item['samples'],1):raise ValueError('Whole native PCM input shape differs')
                raw=wave[:,0].astype('<i2').tobytes()
                if hashlib.sha256(raw).hexdigest()!=item['pcm_sha256'][tap]:raise ValueError('Historical PCM input differs')
                if item['gap_before_samples']:
                    silence=np.zeros(item['gap_before_samples'],dtype=np.int16);destination.write(silence);h.update(silence.astype('<i2').tobytes())
                destination.write(wave);h.update(raw)
        info=sf.info(path)
        if info.frames!=total:raise ValueError('Concatenated file frame count differs')
        audio[tap]=bind(path);pcm_hashes[tap]=h.hexdigest()
    # Add an ordinal offset, not a fresh sequence assignment: original duplicate
    # or backwards packet sequence relations within a source remain unchanged.
    telemetry=[];sequence_offset=0;cue_sources=[]
    for item in sequence:
        b=item['telemetry'];bind(b['path'],b['sha256']);cue_sources.append(b)
        packets=[json.loads(line) for line in Path(b['path']).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        base=item['start_sample']/16000
        original_sequences=[p['sequence'] for p in packets if p.get('sequence') is not None]
        if any(type(s) is not int for s in original_sequences):raise ValueError('Actual packet sequences must be integer or null')
        piece_sequence_offset=sequence_offset-min(0,min(original_sequences,default=0))
        for packet in packets:
            allowed={'angle_deg','available_at_sec','energy','reliability','valid','sequence','source_start_sec','source_end_sec'}
            if set(packet)-allowed:raise ValueError('Only sanitized actual cue fields may enter continuous provider')
            p=deepcopy(packet)
            for k in ('available_at_sec','source_start_sec','source_end_sec'):
                if k in p:p[k]+=base
            if p.get('sequence') is not None:
                p['sequence']+=piece_sequence_offset
            telemetry.append(p)
        if original_sequences:sequence_offset=max(original_sequences)+piece_sequence_offset+1
    cue_path=payload/'continuous_cues.jsonl'
    with cue_path.open('x',encoding='utf-8') as f:
        for p in telemetry:f.write(json.dumps(p,allow_nan=False,separators=(',',':'))+'\n')
        f.flush();os.fsync(f.fileno())
    _,Provider,_=import_epoch(spec);provider=Provider(cue_path)
    manifest=dict(schema='s6c_long_session_composition.v1',status='PREPARED',created_utc=utc(),epoch=bind(epoch_path),
        driver_sources=source_bindings(),input_index=spec['input_index'],scene_manifest=spec['scene_manifest'],gallery_index=spec.get('gallery_index'),sequence=sequence,source_count=len(sequence),
        duration_samples=total,duration_sec=total/16000,target_minimum_minutes=args.minutes,between_scene_silence_sec=args.gap_sec,
        audio=audio,pcm_sha256=pcm_hashes,telemetry=bind(cue_path),cue_sources=cue_sources,delivered_cue_rows=len(provider.rows),
        payload_root=str(payload),report_root=str(root),source_selection='Prospectively fixed family round-robin: sorted family IDs and sorted case IDs within family; each whole case once until minimum duration, no outcome selection or source trim. Earlier canonical-order variant was previewed only, never composed or executed.',
        scope='Continuous host file only. Inputs concatenate independently reset real XVF captures; hidden XVF adaptive state is not continuous. Original within-scene gaps/fault relations retained; explicit digital silence between cases.',
        predictor_inputs='Only corresponding prepared audio, sanitized shifted cue packets and explicit isolated gallery if selected. Composition case IDs and scorer truth never enter runtime.',
        no_new_gain=True,no_rir_or_physical_playback=True)
    save(root/'COMPOSITION.json',manifest,immutable=True);return bind(root/'COMPOSITION.json')


def shift_event(original,offset,prefix):
    row=deepcopy(original)
    for key in ('source_start_sec','source_end_sec','receptive_start_sec','receptive_end_sec','available_at_sec'):
        if key in row:row[key]+=offset
    for key in ('event_id','observation_id','utterance_id'):
        if key in row:row[key]=prefix+str(row[key])
    if 'clean_intervals' in row:row['clean_intervals']=[[a+offset,b+offset] for a,b in row['clean_intervals']]
    return row


def record_sample(handle,value):
    handle.write(json.dumps(value,allow_nan=False,separators=(',',':'))+'\n');handle.flush()


def load_composition(args,assets=False):
    p=REPORT/'long_session'/args.version/'COMPOSITION.json';m=read(p)
    for b in m['driver_sources']:bind(b['path'],b['sha256'])
    bind(m['epoch']['path'],m['epoch']['sha256']);spec=load_epoch(m['epoch']['path'],assets=assets)
    for b in m['audio'].values():bind(b['path'],b['sha256'])
    bind(m['telemetry']['path'],m['telemetry']['sha256'])
    return m,spec,bind(p)


def chronological(args):
    """One continuous policy over genuine historical R0 neural observations."""
    import numpy as np
    m,spec,composition=load_composition(args)
    row=choose_profile(spec,args.candidate,args.asr_tap,args.identity_tap)
    if row['recipe_id']!='N00' or row['gallery_condition']!='NONE' or args.asr_tap!=args.identity_tap:
        raise ValueError('Historical R0 chronological replay requires explicit N00 same-tap/no-gallery candidate')
    Profile,Provider,build=import_epoch(spec);profile=Profile.from_dict(row['profile'])
    authority_binding=bind(S6B/'LOCAL_ARTIFACT_INDEX.json','2ce021fccd0cff0d60d699c2a56e541949fd1348bf529b6f12ba8ca796336c8e')
    authority=verified(authority_binding)
    def sealed_binding(path):
        rows=[b for b in authority['artifacts'] if Path(b['path']).resolve()==Path(path).resolve()]
        if len(rows)!=1:raise ValueError('Historical input must occur once in sealed S6B artifact index')
        b=rows[0];bind(b['path'],b['sha256']);return b
    source_index=args.native_index or S6B/'epoch2/FULL_ALL_NEURAL_INDEX.json'
    source_binding=sealed_binding(source_index);index=verified(source_binding)
    if index['status']!='COMPLETE':raise ValueError('Complete immutable source index required')
    lookup={(r['case_id'],r['stream']):r for r in index['rows'] if r['recipe_id']=='R0'}
    historical_binding=sealed_binding(S6B/'EPOCH2_EXECUTION_MANIFEST.json');historical=verified(historical_binding)
    expected_profile=next(r['profile'] for r in historical['recipes'] if r['recipe_id']=='R0')
    if {a['component_id']:a['sha256'] for a in historical['assets']}!={a['component_id']:a['sha256'] for a in spec['assets']}:
        raise ValueError('Historical neural weights differ from admitted S6C weights')
    replay_path=Path(spec['root'])/'scripts/s6c_replay.py'
    module_spec=importlib.util.spec_from_file_location('s6c_long_frozen_replay',replay_path)
    replay=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(replay)
    inputs=[];receipts=[]
    for item in m['sequence']:
        src=lookup[item['case_id'],args.identity_tap]
        evidence,vectors,b=replay.load_evidence(src['receipt']['path'],expected_epoch_digest=historical['execution_digest'],
            expected_audio=item['inputs'][args.identity_tap],expected_receipt=src['receipt'])
        if evidence['identity']['profile']!=expected_profile:raise ValueError('N00 source is not exact original R0 profile')
        local=replay.scheduler_inputs(evidence,vectors)
        inputs.extend(shift_event(e,item['start_sample']/16000,f'piece:{item["index"]:04d}:') for e in local)
        receipts.append(b)
    provider=Provider(Path(m['telemetry']['path'])) if profile.tracker.cues_enabled else None
    policy=build(profile,spatial_provider=provider)
    out=Path(m['report_root'])/'chronological'/args.candidate/(args.asr_tap+'_'+args.identity_tap)
    if out.exists():raise ValueError('Chronological output exists; preserve it')
    out.mkdir(parents=True);counts=Counter();state_rows=[];started=time.perf_counter()
    with (out/'EVENTS.jsonl').open('x',encoding='utf-8') as f:
        ordered=sorted(inputs,key=lambda r:(r['available_at_sec'],{'segmentation':0,'embedding':1,'asr':2}[r['kind']],r['event_id']))
        for instant,group in itertools.groupby(ordered,key=lambda r:r['available_at_sec']):
            events=[]
            for event in group:events.extend(policy.push(event,'asr' if event['kind']=='asr' else 'speaker'))
            bound=math.nextafter(instant,math.inf);events.extend(policy.advance({'speaker':bound,'asr':bound}))
            for event in events:
                record_sample(f,event);counts[event['event_type']]+=1
            if not state_rows or instant-state_rows[-1]['available_at_sec']>=30:
                state_rows.append(dict(available_at_sec=instant,**policy.tracker.snapshot()['counts']))
        for event in policy.finish():record_sample(f,event);counts[event['event_type']]+=1
        os.fsync(f.fileno())
    snapshot=policy.snapshot();save(out/'SNAPSHOT.json',dict(scheduler=snapshot,tracker=policy.tracker.snapshot()),immutable=True)
    result=dict(schema='s6c_chronological_genuine_evidence.v1',status='COMPLETE',created_utc=utc(),composition=composition,
        profile=row,source_index=source_binding,historical_authority=authority_binding,historical_epoch=historical_binding,native_sources=receipts,source_neural_recipe='Actual R0 independent-scene observations; .5s historical lane explicitly mature API role, not long-window inference.',
        events=bind(out/'EVENTS.jsonl'),snapshot=bind(out/'SNAPSHOT.json'),counts=dict(counts),state_trajectory=state_rows,
        elapsed_sec=time.perf_counter()-started,observations=len(inputs),neural_invocations=0,
        scope='One uninterrupted shared host policy over shifted genuine captured evidence, preserving local observation timing/support and neural-reset boundaries. Inter-scene silence has no invented neural events. No continuous-neural/XVF or correct-identity claim.')
    save(out/'RESULT.json',result,immutable=True);return bind(out/'RESULT.json')


def process_sample(process):
    import psutil
    complete=True;errors=[];items=[process]
    try:items+=process.children(recursive=True)
    except psutil.Error as exc:complete=False;errors.append(repr(exc))
    rows=[]
    for p in items:
        try:
            memory=p.memory_full_info();cpu=p.cpu_times();io=p.io_counters()
            rows.append(dict(pid=p.pid,creation_time=p.create_time(),rss_bytes=memory.rss,
                private_resident_uss_bytes=getattr(memory,'uss',None),windows_private_commit_bytes=getattr(memory,'private',None),
                threads=p.num_threads(),cpu_sec=cpu.user+cpu.system,write_bytes=io.write_bytes))
        except psutil.Error as exc:complete=False;errors.append(repr(exc))
    def total(key):return sum(r[key] for r in rows) if complete and rows and all(r[key] is not None for r in rows) else None
    return dict(processes=rows,complete_process_tree=complete,errors=errors,rss_sum_upper_bound_bytes=total('rss_bytes'),
        private_resident_uss_bytes=total('private_resident_uss_bytes'),windows_private_commit_bytes=total('windows_private_commit_bytes'),
        cpu_sec=total('cpu_sec'),write_bytes=total('write_bytes'),available_ram_bytes=psutil.virtual_memory().available,
        pss_bytes=None,shared_resident_unique_bytes=None)


def native(args):
    """Exactly one uninterrupted real-time native session for an admitted profile."""
    import psutil
    m,spec,composition=load_composition(args,assets=True)
    row=choose_profile(spec,args.candidate,args.asr_tap,args.identity_tap)
    Profile,Provider,_=import_epoch(spec);profile=Profile.from_dict(row['profile'])
    from edge_speech_pipeline.config import PipelineConfig,AssetSpec
    from edge_speech_pipeline.models import ResidentModelBundle
    from edge_speech_pipeline.runtime import PipelineEngine
    from edge_speech_pipeline.research_identity_v3 import ResearchGallery
    if row['cue_condition'] not in ('CUES_OFF','REAL_ALIGNED_CUES'):raise ValueError('Long native runner only supports observed cues or explicit cue off')
    if (profile.identity.mode=='post_association')!=(args.gallery is not None):raise ValueError('Naming requires an explicit fixed isolated long-session gallery; none rejects one')
    gallery_row=None
    if args.gallery:
        if not spec.get('gallery_index'):raise ValueError('Frozen epoch gallery registry required')
        gallery_index=verified(spec['gallery_index']);gallery_binding=bind(args.gallery)
        gallery_row=fixed_gallery_row(gallery_index,gallery_binding,row)
    condition=(gallery_row['gallery_condition']+'_tier'+str(gallery_row['enrollment_tier'])) if gallery_row else 'NONE'
    out=Path(m['report_root'])/'native'/args.candidate/(args.asr_tap+'_'+args.identity_tap)/condition
    payload=Path(m['payload_root'])/'native'/args.candidate/(args.asr_tap+'_'+args.identity_tap)/condition
    if out.exists() or payload.exists():raise ValueError('Native long attempt namespace already exists')
    resources=admit_work(full=False);out.mkdir(parents=True);payload.mkdir(parents=True)
    process=psutil.Process();owner=dict(pid=process.pid,creation_time=process.create_time(),argv=process.cmdline())
    save(out/'STARTED.json',dict(status='STARTED',owner=owner,utc=utc(),composition=composition,profile=row,
        resources=resources,driver_sources=source_bindings(),gallery=bind(args.gallery) if args.gallery else None),immutable=True)
    started=time.perf_counter();engine=None;counts=Counter();samples=0;native_started=None;bundle=None
    try:
        assets=tuple(AssetSpec(a['component_id'],Path(a['path']),a['sha256'],a['deployment_relative_path']) for a in spec['assets'])
        base=PipelineConfig(assets=assets,session_root=payload/'sessions',profile_root=payload/'unused_profiles')
        config=profile.apply(base);load_started=time.perf_counter();bundle=ResidentModelBundle(config);model_load_sec=time.perf_counter()-load_started
        gallery=ResearchGallery(args.gallery,config.asset('redimnet2_b2_fp32').sha256,profile.identity.max_gallery_profiles) if args.gallery else None
        provider=Provider(Path(m['telemetry']['path'])) if row['cue_condition']=='REAL_ALIGNED_CUES' else None
        engine=PipelineEngine(base,research_profile=profile,model_bundle=bundle,research_gallery=gallery,spatial_provider=provider)
        native_started=time.perf_counter();session=engine.start_paired_files(Path(m['audio'][args.asr_tap]['path']),Path(m['audio'][args.identity_tap]['path']),realtime=True,accelerated_factor=0)
        last_sample=last_beat=-1.;deadline=native_started+m['duration_sec']+profile.runtime.lane_drain_timeout_sec+120.
        with (out/'PROCESS_SAMPLES.jsonl').open('x',encoding='utf-8') as sample_file:
            while True:
                while not engine.events.empty():
                    event=engine.events.get();counts[event.event_type]+=1
                elapsed=time.perf_counter()-native_started
                if elapsed-last_sample>=2. or engine.state in ('COMPLETED','FAILED'):
                    telemetry=engine.telemetry()
                    value=dict(phase='periodic',utc=utc(),elapsed_from_native_launch_sec=elapsed,state=engine.state,process=process_sample(process),
                        telemetry=telemetry,event_counts=dict(counts),native_event_log_bytes=(session/'events.jsonl').stat().st_size,
                        event_queue_backlog=engine.events.qsize())
                    record_sample(sample_file,value);samples+=1;last_sample=elapsed
                if elapsed-last_beat>=20:
                    print(json.dumps(dict(phase='CONTINUOUS_PACED',owner=owner,elapsed_sec=elapsed,state=engine.state,
                        source_sec=engine.telemetry()['source_duration_sec'],asr_cursor_sec=engine.telemetry().get('asr_cursor_sec'),
                        speaker_cursor_sec=engine.telemetry().get('speaker_cursor_sec')),allow_nan=False),flush=True);last_beat=elapsed
                if engine.state in ('COMPLETED','FAILED'):break
                if time.perf_counter()>deadline or (REPORT/'STOP_REQUEST.json').exists():
                    engine.stop();raise TimeoutError('Long native bounded deadline or explicit STOP_REQUEST')
                time.sleep(.1)
            os.fsync(sample_file.fileno())
        engine.wait_for_completion(profile.runtime.lane_drain_timeout_sec+30.)
        # COMPLETED may become visible immediately before the final writer emits
        # closure/tail events. Join it, then observe the terminal queue/sample.
        while not engine.events.empty():
            event=engine.events.get();counts[event.event_type]+=1
        with (out/'PROCESS_SAMPLES.jsonl').open('a',encoding='utf-8') as sample_file:
            record_sample(sample_file,dict(phase='terminal_after_finalization',utc=utc(),
                elapsed_from_native_launch_sec=time.perf_counter()-native_started,state=engine.state,process=process_sample(process),
                telemetry=engine.telemetry(),event_counts=dict(counts),native_event_log_bytes=(session/'events.jsonl').stat().st_size,
                event_queue_backlog=engine.events.qsize()))
            os.fsync(sample_file.fileno());samples+=1
        closure=read(session/'session_finalization_v3.json')
        if closure['state']!='COMPLETED' or closure['live_lanes_at_finalization'] or closure['resident_bundle_lease_retained'] or not closure['event_and_transcript_handles_closed']:
            raise RuntimeError('Long native closure not complete')
        if engine.telemetry()['asr_cursor_sec']!=m['duration_sec']:raise RuntimeError('Continuous ASR cursor did not reach complete input')
        journals={}
        for name,tap in (('audio_spool.pcm16',args.asr_tap),('identity_audio_spool.pcm16',args.identity_tap)):
            b=bind(session/name,m['pcm_sha256'][tap])
            if b['bytes']!=2*m['duration_samples']:raise RuntimeError('Continuous full paired journal mismatch')
            journals[name]=b
        outputs=[bind(p) for p in session.iterdir() if p.is_file()]
        result=dict(schema='s6c_continuous_paced_native.v1',status='COMPLETE',created_utc=utc(),owner=owner,composition=composition,
            profile=row,long_session_gallery_condition=gallery_row,gallery_index=spec.get('gallery_index'),model_load_sec=model_load_sec,native_elapsed_sec=time.perf_counter()-native_started,
            total_observed_worker_sec=time.perf_counter()-started,resident_bundle_loads=1,resident_sessions_created=bundle.sessions_created,
            source_duration_sec=m['duration_sec'],native_journals=journals,native_artifacts=outputs,
            process_samples=bind(out/'PROCESS_SAMPLES.jsonl'),process_sample_count=samples,event_counts=dict(counts),
            final_telemetry=engine.telemetry(),gallery_load_receipt=gallery.receipt if gallery else None,
            live_owned_lanes=[t.name for t in threading.enumerate() if t.name.startswith(('edge-','s6c-')) and t.is_alive()],
            hardware_invocations=0,scope='One real-time host session over synthetic concatenation of reset physical captures. Source block-before-sleep convention remains; sampled resource/backlog values are not continuous maxima or phonetic/CM5 latency. Missing process fields stay unavailable.')
        if result['live_owned_lanes']:raise RuntimeError('Owned lanes remain alive after closure')
        save(out/'RESULT.json',result,immutable=True);return bind(out/'RESULT.json')
    except Exception as exc:
        if engine is not None and engine.state not in ('COMPLETED','FAILED','IDLE'):
            engine.stop()
            try:engine.wait_for_completion(30.)
            except Exception:pass
        save(out/'FAILURE.json',dict(status='FAILED',utc=utc(),error=repr(exc),traceback=traceback.format_exc(),owner=owner,
            engine_state=engine.state if engine else None,elapsed_sec=time.perf_counter()-started),immutable=True)
        raise


def fixtures(args):
    import numpy as np
    import soundfile as sf
    import tempfile
    spec=load_epoch(REPORT/(args.epoch.upper()+'_EXECUTION_MANIFEST.json'));import_epoch(spec)
    from edge_speech_pipeline.research_tracking_v3 import S6CTracker,S6CTrackingConfig
    result=[]
    # Constructed 192D hypotheses are labeled fixtures, never empirical people.
    for capacity in (16,32,64,128,256):
        config=S6CTrackingConfig.from_mapping(dict(mode='old_voice_gate',max_tracks=capacity,lifecycle_policy='retire_archive',archive_capacity=32))
        tracker=S6CTracker(config);last_lifetime=0;peak=0
        for i in range(1400):
            start=i*31.;vector=np.zeros(192,np.float32);vector[i%192]=1.
            row=tracker.update(vector,start,start+.5,start+.51,evidence_kind='mature',clean_intervals=[[start,start+.5]],observation_id='fixture:'+str(i))
            counts=row['lifecycle_counts'];peak=max(peak,counts['live'])
            if counts['live']>capacity or counts['archive']>32 or counts['lifetime_external_ids']<last_lifetime:
                raise AssertionError('Finite lifecycle bound/monotonic ID failure')
            last_lifetime=counts['lifetime_external_ids']
        snapshot=tracker.snapshot()
        if snapshot['counts']['cumulative_retirements']<1000 or snapshot['counts']['lifetime_external_ids']<1000:
            raise AssertionError('Fixture did not exercise retirement/reallocation')
        result.append(dict(capacity=capacity,observations=1400,synthetic_elapsed_sec=1400*31.,counts=snapshot['counts'],peak_live=peak,state_bytes=snapshot['state_bytes']))
    local=dict(kind='embedding',event_id='a',observation_id='a',source_start_sec=1.,source_end_sec=1.5,receptive_start_sec=1.,receptive_end_sec=1.5,
        available_at_sec=1.6,clean_intervals=[[1.1,1.4]])
    shifted=shift_event(local,10.,'x:')
    if shifted['source_end_sec']-shifted['source_start_sec']!=.5 or shifted['available_at_sec']!=11.6 or local['event_id']!='a':raise AssertionError('Chronological support/identity shift corrupted input')
    binding=dict(path='fixture',bytes=1,sha256='fixture')
    roster=dict(manifest=binding,case_id=None,gallery_condition='FIXED_ROTATION_A',enrollment_tier=15)
    fixed_gallery_row(dict(rows=[roster]),binding,roster)
    try:fixed_gallery_row(dict(rows=[roster]),binding,{**roster,'gallery_condition':'FIXED_ROTATION_B'})
    except ValueError:pass
    else:raise AssertionError('Different registered gallery condition was accepted')
    fake=[]
    for case in ('a1','a2','b1','b2'):
        for tap in ('O0','O1'):fake.append(dict(case_id=case,stream=tap,duration_sec=1000.,audio={},audio_pcm_sha256='fixture',telemetry={}))
    chosen,total=timeline(fake,30.,2.,dict(a1='A',a2='A',b1='B',b2='B'))
    if [r['case_id'] for r in chosen]!=['a1','b1'] or total!=2002*16000:raise AssertionError('Family round-robin selection differs')
    with tempfile.TemporaryDirectory(prefix='s6c_long_wav_') as temp:
        target=Path(temp)/'fixture.wav'
        with sf.SoundFile(target,mode='x',samplerate=16000,channels=1,subtype='PCM_16',format='WAV') as f:f.write(np.array([-32768,0,32767],np.int16))
        actual,rate=sf.read(target,dtype='int16')
        if rate!=16000 or actual.tolist()!=[-32768,0,32767]:raise AssertionError('Whole PCM writer changes endpoint samples')
    output=REPORT/'long_session'/(args.version+'_FIXTURES.json')
    receipt=dict(schema='s6c_long_state_model_free_checks.v1',status='PASS',created_utc=utc(),sources=source_bindings(),epoch=bind(REPORT/(args.epoch.upper()+'_EXECUTION_MANIFEST.json')),
        capacities=result,shift_test='PASS',exact_gallery_condition_test='PASS',family_round_robin_test='PASS',pcm_writer_test='PASS',neural_invocations=0,scope='Constructed vectors and long time intervals; proves finite storage/reallocation guards on tested inputs, not real speaker accuracy or actual sustained CPU/memory behavior.')
    save(output,receipt,immutable=True);return bind(output)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=('prepare','fixtures','chronological','native'),required=True)
    p.add_argument('--epoch',default='epoch2');p.add_argument('--version',default='v1');p.add_argument('--minutes',type=float,default=30.)
    p.add_argument('--gap-sec',type=float,default=2.);p.add_argument('--candidate',default='C001');p.add_argument('--asr-tap',choices=('O0','O1'),default='O0')
    p.add_argument('--identity-tap',choices=('O0','O1'),default='O0');p.add_argument('--native-index',type=Path);p.add_argument('--gallery',type=Path)
    a=p.parse_args()
    if not a.version.replace('_','').isalnum():p.error('Simple unique version name required')
    function={'prepare':prepare,'fixtures':fixtures,'chronological':chronological,'native':native}[a.mode]
    print(json.dumps(function(a),indent=2,allow_nan=False),flush=True)


if __name__=='__main__':main()
