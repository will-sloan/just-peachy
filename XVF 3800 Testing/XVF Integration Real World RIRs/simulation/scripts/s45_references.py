"""Optional isolated enrollment-reference inputs; never captures/enrolls/scores. README_S45_REFERENCES.md."""
from __future__ import annotations
import argparse, collections, copy, hashlib, json, math, os
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve
from s45_common import BANK, PAYLOAD, SIM, bind, save, read, now
from s45_sources import gain_for, normalize, text_group
from s4_geometry import source_label

FS=16000
MANIFEST=BANK/'REFERENCE_SCENE_MANIFEST.json'
PLAN=BANK/'REFERENCE_SOURCE_PLAN.json'
SOURCE_PATH=SIM/'staging/s45_sources/SOURCE_AND_SPLIT_MANIFEST.json'
RIR_PATH=SIM/'rir_library/v1/RIR_MANIFEST.json'
RIR_HASH='468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546'
EXCLUDED='JPXVF_P1_R02_T01_D01_S02_F00_NAT_CU_R13'
GROUP_KEYS=['room_table','recorder_position','orientation','obstructed']

def content_key(value):return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()

def reference_eligible(source):
    return source['split']=='development' and source['usage']=='enrollment_reference' and source['whole_clip'] and 2<=source['duration_sec']<=10

def convolution_samples(dry,kernel,gain):
    assert dry.ndim==1 and kernel.ndim==2 and kernel.shape[1]==4
    return np.column_stack([fftconvolve(dry*gain,kernel[:,channel]) for channel in range(4)])

def required_duration(source_samples,rir_frames):
    stop=3*FS+source_samples+rir_frames-1
    duration=max(20,math.ceil(stop/FS+5))
    if duration>25:raise ValueError('Reference would exceed optional25s bound')
    return duration,stop

def sources_and_paths():
    source_manifest=read(SOURCE_PATH);people={p['identity']:p for p in source_manifest['people'] if p['split']=='development'}
    assert len(people)==34
    candidates=[copy.deepcopy(s) for s in source_manifest['sources'] if reference_eligible(s)]
    legacy_inputs=[]
    # Exactly one original unused S4 enrollment candidate was separately
    # authorized, preserving the conceptual enrollment role and original bytes.
    missing=[pid for pid in people if not any(s['identity']==pid for s in candidates)]
    for pid in missing:
        if pid!='CV_0ec4d6799c8c83a9a047':continue
        oldroot=SIM/'scene_bank/s4_v2_20260909T002140Z';old=read(oldroot/'SOURCE_AND_SPLIT_MANIFEST.json')
        old_scenes=read(oldroot/'SCENE_MANIFEST.json')
        used={seg['source_id'] for scene in old_scenes['scenes'] for seg in scene['segments'] if seg['kind']=='utterance'}
        rows=[s for s in old['sources'] if s['identity']==pid and s['split']=='development' and s['usage']=='enrollment_candidate_not_S4_probe']
        assert len(rows)==1 and rows[0]['source_id'] not in used
        source=copy.deepcopy(rows[0]);original_usage=source['usage'];gain=gain_for(source['quality'])
        source.update(usage='enrollment_reference',historical_development_reuse=True,historical_original_usage=original_usage,
            historical_role_unchanged='Unused S4 enrollment candidate remains enrollment-reference, never a probe',
            transcript_normalized=normalize(source['transcript']),preparation_gain=gain,preparation_gain_db=20*math.log10(gain),
            postgain_peak_fs=source['quality']['peak']*gain,quality_partition='self_reported_60plus_real_recording',
            parent_book=None,prompt_group=text_group(source['transcript']),role_frozen_before_QC=True,
            rights={'license_id':'CC0','license_binding':old['license_binding'],'no_contributor_identification':True,
                    'attribution':'Mozilla Common Voice '+source['release'],'future_training_automatic_clearance':False},
            gain_provenance='Computed from unchanged S4 active statistics using the frozen S4 formula; this unused enrollment clip had no prior rendered scalar.')
        assert reference_eligible(source)
        candidates.append(source)
        legacy_inputs=[bind(oldroot/'SOURCE_AND_SPLIT_MANIFEST.json'),bind(oldroot/'SCENE_MANIFEST.json'),bind(oldroot/'SOURCE_LEVEL_POLICY.json')]
    selected=[];gaps=[]
    for pid in sorted(people):
        eligible=sorted([s for s in candidates if s['identity']==pid],key=lambda s:content_key(['S45_REFERENCE',s['source_id']]))
        if not eligible:gaps.append({'identity':pid,'reason':'No eligible unused enrollment-reference clip; probes/reserve never substituted'});continue
        selected.append(eligible[0])
    # Parent/prompt and exact-byte separation from every main-bank probe,
    # including the separately authorized legacy development probes.
    probes=[s for s in source_manifest['sources'] if s['usage']=='probe']
    legacy=SIM/'staging/s45_sources/LEGACY_DEVELOPMENT_PROBES.json'
    if legacy.exists():probes+=read(legacy)['sources']
    probe_hashes={s['source_binding']['sha256'] for s in probes};probe_pcm={s['decoded_pcm_sha256'] for s in probes}
    for source in selected:
        assert source['source_binding']['sha256'] not in probe_hashes and source['decoded_pcm_sha256'] not in probe_pcm
        for field in ['source_binding','decoded_16k_binding']:bind(source[field]['path'],source[field]['sha256'])
    bind(RIR_PATH,RIR_HASH);paths=[]
    for row in read(RIR_PATH)['records']:
        g=row['geometry']
        if not row['can_proceed_to_hil_proof'] or row['run_id']==EXCLUDED or g['room_table']=='Upper Loeb':continue
        if g['orientation']!='FLAT' or g['obstructed'] or not 0<g['source_distance_m_effective']<=2:continue
        assert row['capture_audit_pass'] and row['original_acquisition_status'] in ['PASS','REVIEW']
        g=copy.deepcopy(g);g['active_angle_label']=source_label(g['speaker_angle_deg_effective'])
        paths.append({'run_id':row['run_id'],'geometry':g,'time_origin':row['time_origin'],'file':row['output'],'frames':row['output']['frames'],
                      'status':row['status'],'limitations':row['limitations'],'can_proceed_to_hil_proof':True})
    byroom=collections.defaultdict(list)
    for path in paths:byroom[path['geometry']['room_table']].append(path)
    rooms=sorted(byroom,key=lambda name:(name!='Arise Kitchen Main Table',name))
    for room in rooms:byroom[room].sort(key=lambda r:r['run_id'])
    assert len(rooms)==4
    assigned=[]
    for i,source in enumerate(selected):
        room=rooms[i%len(rooms)];path=byroom[room][(i//len(rooms))%len(byroom[room])]
        assigned.append((source,path))
    return assigned,gaps,legacy_inputs

def build_plan():
    assigned,gaps,legacy_inputs=sources_and_paths();scenes=[];sources={};rirs={}
    for i,(source,path) in enumerate(assigned,1):
        source_id=source['source_id'];sid=source['identity'];case_id=f'S45_REF_{i:02}';start=3*FS
        duration,convolution_stop=required_duration(source['samples'],path['frames'])
        gain=source['preparation_gain'];assert source['source_gain_applied']==1 and 0<gain<=10**(12/20)
        segment={'kind':'utterance','source_id':source_id,'speaker_key':sid,'participant_id':'A','dataset':source['dataset'],
            'quality_partition':source['quality_partition'],'source_start_sample':start,'source_stop_sample':start+source['samples'],
            'convolution_stop_sample':convolution_stop,'rir_expected_significant_onset_sample':start+800,'rir_id':path['run_id'],
            'transcript':source['transcript'],'transcript_normalized':source['transcript_normalized'],'transcript_sha256':source['transcript_sha256'],
            'whole_clip':True,'word_times':None,'source_crop_samples':[0,source['samples']],
            'timing_provenance':'Whole unused enrollment-reference; estimated source activity and retained measured RIR time convention',
            'preparation_gain_scalar':gain,'relative_source_db':0,'relative_source_scalar':1,
            'activity_ranges_samples_estimated':[[start+800+a,start+800+b] for a,b in source['quality']['active_ranges_samples_estimated']],
            'role':'enrollment_reference_only','source_split':'development','source_usage':'enrollment_reference'}
        reference={'source_id':source_id,'participant_id':'A','transcript':source['transcript'],'start_sample':start,
                   'stop_sample':start+source['samples'],'role':'enrollment_reference_only'}
        scenes.append({'case_id':case_id,'family_id':'REFERENCE','family':'Optional isolated naming-reference inputs',
            'title':'Isolated unused enrollment reference '+sid,'split':'development','reserve_stratum':'development',
            'source_partition':'development','duration_s':duration,'sample_rate_hz':FS,'channels':['MIC0','MIC1','MIC2','MIC3'],
            'receiver_configuration':{key:path['geometry'][key] for key in GROUP_KEYS},'cast':{'A':sid},'segments':[segment],
            'snr_reference_segments':[],'noise_policy':None,'overlap_intervals':[],'overlap_scoring_limited':False,
            'all_speaker_references':[reference],'target_references':[reference],'background_references':[],
            'all_speaker_reference_complete':True,'transcript_valid':True,'task_scoring_allowed':False,
            'enrollment_executed':False,'optional_capture':True,'capture_state':'PENDING_OPTIONAL_CAPTURE',
            'excluded_from_240_canonical_count':True,'capture_after_all_240_only':True,'captured':False,
            'prepared_tail_after_convolution_s':duration-convolution_stop/FS,
            'coverage_limitations':['Reference preparation is not completed physical capture or naming accuracy.',
                'Optional capture remains subject to global pass/playback/deadline budget; no reserve enrollment.']})
        sources[source_id]=source;rirs[path['run_id']]=path
    result={'schema':'jp_s45_reference_plan_v1','created_utc':now(),'source_manifest_binding':bind(SOURCE_PATH),
        'legacy_source_inputs':legacy_inputs,'rir_manifest_binding':bind(RIR_PATH,RIR_HASH),'scenes':scenes,
        'selected_sources':sources,'selected_rirs':rirs,'gaps':gaps,'reference_code':bind(__file__),
        'selection_policy':'One unused development enrollment-reference per identity, content-key order; original unused S4 candidate reused only for authorized missing identity.',
        'headroom_policy':'One shared scalar min(1,0.25/max_reference_bank_peak) for all optional references; no per-mic/source/RIR normalization',
        'physical_execution_order':'Only after240 canonical scenes; pending references are optional and never counted as canonical completion.',
        'task_scoring_allowed':False,'enrollment_executed':False}
    result['plan_key']=content_key({'scenes':scenes,'source_inputs':[(s['source_id'],s['source_binding']['sha256'],s['preparation_gain']) for s in sources.values()],
                                  'rir_inputs':[(r['run_id'],r['file']['sha256']) for r in rirs.values()]})
    return result

def render(scene,sources,rirs):
    seg=scene['segments'][0];source=sources[seg['source_id']];path=rirs[seg['rir_id']]
    dry,fs=sf.read(source['decoded_16k_binding']['path'],dtype='float64');assert fs==FS and len(dry)==source['samples']
    kernel,rate=sf.read(path['file']['path'],dtype='float64',always_2d=True);assert rate==FS and len(kernel)==path['frames']
    convolved=convolution_samples(dry,kernel,seg['preparation_gain_scalar'])
    result=np.zeros((round(scene['duration_s']*FS),4),dtype=np.float64)
    start=seg['source_start_sample'];result[start:start+len(convolved)]=convolved
    assert np.isfinite(result).all() and scene['duration_s']-seg['convolution_stop_sample']/FS>=5
    return result

def verify():
    result=read(MANIFEST);assert result['validation']['status']=='PASS'
    bind(SOURCE_PATH,result['source_manifest_binding']['sha256']);bind(__file__,result['reference_code']['sha256']);bind(RIR_PATH,RIR_HASH)
    for source in result['selected_sources'].values():
        assert reference_eligible(source)
        for field in ['source_binding','decoded_16k_binding']:bind(source[field]['path'],source[field]['sha256'])
    for path in result['selected_rirs'].values():bind(path['file']['path'],path['file']['sha256'])
    for scene in result['scenes']:
        bind(scene['canonical_audio']['path'],scene['canonical_audio']['sha256'])
        assert scene['excluded_from_240_canonical_count'] and not scene['task_scoring_allowed'] and not scene['enrollment_executed']
    print(json.dumps({'status':'PASS','manifest':str(MANIFEST),'optional_references':len(result['scenes']),
                      'prepared_seconds':sum(s['duration_s'] for s in result['scenes']),'captured_by_this_script':0,'enrolled':0,'gaps':result['gaps']}))

def prepare():
    if MANIFEST.exists():verify();return
    plan=build_plan();BANK.mkdir(parents=True,exist_ok=True)
    if PLAN.exists():assert read(PLAN)['plan_key']==plan['plan_key'],'Frozen optional reference plan changed'
    else:save(PLAN,plan)
    plan=read(PLAN);sources=plan['selected_sources'];rirs=plan['selected_rirs'];first={}
    for path in rirs.values():bind(path['file']['path'],path['file']['sha256'])
    for scene in plan['scenes']:
        x=render(scene,sources,rirs)
        first[scene['case_id']]={'peak':float(np.max(np.abs(x))),'sha256':hashlib.sha256(x.tobytes()).hexdigest()}
    maximum=max(r['peak'] for r in first.values());assert maximum>0
    scalar=min(1,.25/maximum);dest=PAYLOAD/'canonical_references';dest.mkdir(parents=True,exist_ok=True)
    for scene in plan['scenes']:
        x=render(scene,sources,rirs);assert hashlib.sha256(x.tobytes()).hexdigest()==first[scene['case_id']]['sha256']
        y=(x*scalar).astype('float32');assert np.max(np.abs(y))<=.2500001
        path=dest/(scene['case_id']+'.wav')
        if path.exists():
            prior,rate=sf.read(path,dtype='float32',always_2d=True);assert rate==FS and np.array_equal(prior,y)
        else:
            temporary=path.with_suffix('.pending');sf.write(temporary,y,FS,format='WAV',subtype='FLOAT');os.replace(temporary,path)
        scene.update(canonical_audio=bind(path),canonical_peak_fs=float(np.max(np.abs(y))),common_family_headroom_scalar=scalar,
                     unscaled_peak_fs=first[scene['case_id']]['peak'],deterministic_second_render_exact=True)
    validation={'status':'PASS','planned_development_identities':34,'eligible_reference_identities':len(plan['scenes']),
        'prepared_reference_scenes':len(plan['scenes']),'captured_by_this_script':0,'reserve_sources':0,'probe_sources':0,
        'new_unused_enrollment_clips':sum(not s.get('historical_development_reuse',False) for s in sources.values()),
        'historical_unused_S4_enrollment_clips':sum(s.get('historical_development_reuse',False) for s in sources.values()),
        'prepared_audio_s':sum(s['duration_s'] for s in plan['scenes']),'shared_reference_headroom_scalar':scalar,
        'maximum_peak_fs':max(s['canonical_peak_fs'] for s in plan['scenes']),'outside_240_canonical_bank':True,
        'enrollment_or_H2_scoring_executed':False,'deterministic_second_render_exact':len(plan['scenes'])}
    save(MANIFEST,{**plan,'schema':'jp_s45_reference_scene_manifest_v1','prepared_utc':now(),'validation':validation,
                  'source_plan_binding':bind(PLAN)})
    print(json.dumps(validation,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true')
    verify() if parser.parse_args().verify else prepare()
