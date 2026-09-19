"""Deterministic four-worker S4 development scene bank; see README_S4.md."""
import os
for _key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[_key]='1'
import argparse, concurrent.futures, copy, hashlib, math
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve, lfilter
from s4_common import *
from s4_geometry import source_label, ANGLE_POLICY

FS=16000

def rid(room,last,pose='F00',obstruction='CU',seat='S01'):
    return f'JPXVF_P1_R{room:02}_T01_D01_{seat}_{pose}_NAT_{obstruction}_R{last:02}'

def make_plan(source_manifest,rir_records):
    probes=[s for s in source_manifest['sources'] if s['split']=='development' and s['usage']=='probe']
    people=list(dict.fromkeys(s['identity'] for s in probes));assert len(people)==6
    sources={};cast={}
    for letter,person in zip('ABCDEF',people):
        cast[letter]=person
        clips=[s for s in probes if s['identity']==person]
        for n,s in enumerate(clips,1):sources[letter+str(n)]=s
    roles={'L':rid(6,12),'R':rid(6,4),'F':rid(6,1),'B':rid(6,7),
           'LC':rid(2,3,seat='S02'),'FC':rid(2,4,seat='S02'),
           'LR':rid(2,2,seat='S02'),'LL':rid(2,7,seat='S02'),
           'ML':rid(1,5),'MR':rid(1,1),'MD':rid(1,6),
           'MLU':rid(1,8,pose='UPR'),'MRU':rid(1,4,pose='UPR'),
           'KL':rid(5,2),'KR':rid(5,5),'KLO':rid(5,2,obstruction='C2'),'KRO':rid(5,5,obstruction='C2')}
    rirs={}
    for role,id_ in roles.items():
        row=rir_records[id_];g=copy.deepcopy(row['geometry'])
        assert row['can_proceed_to_hil_proof'] and row['capture_audit_pass'] and row['original_acquisition_status'] in ['PASS','REVIEW']
        assert 0<g['source_distance_m_effective']<=5 and 'Loeb' not in g['room_table']
        g['active_angle_label']=source_label(g['speaker_angle_deg_effective'])
        rirs[id_]={'run_id':id_,'geometry':g,'time_origin':row['time_origin'],'file':bind(row['output']['path'],row['output']['sha256']),
                   'frames':row['output']['frames'],'status':row['status'],'limitations':row['limitations'],'can_proceed_to_hil_proof':True}
    scenes=[]
    def scene(n,title,spec,family=None,relative_db=0,noise=None,coverage=None):
        segments=[]
        for label,role,at in spec:
            src=sources[label];r=rirs[roles[role]];start=round(at*FS)
            segments.append({'kind':'utterance','utterance_label':label,'source_id':src['source_id'],'speaker_key':src['identity'],
                'participant_id':label[0],'rir_id':r['run_id'],'source_start_sample':start,'source_stop_sample':start+src['samples'],
                'rir_expected_significant_onset_sample':start+800,'convolution_stop_sample':start+src['samples']+r['frames']-1,
                'transcript':src['transcript'],'transcript_sha256':src['transcript_sha256'],'whole_clip':True,'word_times':None,
                'activity_ranges_samples_estimated':[[a+start+800,b+start+800] for a,b in src['quality']['active_ranges_samples_estimated']],
                'reference_timing_scope':'Whole dry-file schedule; source activity is estimated, 50ms RIR convention retained; no exact phonetic/word timing'})
        if noise:
            role,start,stop,db=noise;r=rirs[roles[role]]
            segments.append({'kind':'synthetic_point_noise','source_id':f'S4_FAN_POINT_3800400_N{round((stop-start)*FS)}','rir_id':r['run_id'],
                'source_start_sample':round(start*FS),'source_stop_sample':round(stop*FS),
                'convolution_stop_sample':round(stop*FS)+r['frames']-1,'source_rms_dbfs':db,'source_rms_target_scope':'Before onset/offset fades; actual post-fade RMS separately measured',
                'noise_model':'Seeded AR(1) colored mono noise, coefficient0.96, 0.2s cosine onset/offset, own measured RIR; not diffuse HVAC',
                'seed':3800400,'noise_identity':'synthetic deterministic point source; no corpus recording'})
        used_rirs={s['rir_id'] for s in segments}
        if not used_rirs:used_rirs={roles['F']}
        groups={tuple(rirs[id_]['geometry'][k] for k in ['room_table','recorder_position','orientation','obstructed']) for id_ in used_rirs}
        assert len(groups)==1,'Incompatible receiver configuration'
        duration=max(24,math.ceil(max((s['convolution_stop_sample']/FS for s in segments),default=18)+5))
        assert duration<=60
        overlaps=[]
        speech=[s for s in segments if s['kind']=='utterance']
        for i,a in enumerate(speech):
            for b in speech[i+1:]:
                lo=max(a['source_start_sample'],b['source_start_sample']);hi=min(a['source_stop_sample'],b['source_stop_sample'])
                if hi>lo:overlaps.append({'start_sample':lo,'stop_sample':hi,'participants':[a['participant_id'],b['participant_id']],'scope':'Scheduled full-clip overlap; not exact phonetic overlap'})
        participants={s['participant_id']:s['speaker_key'] for s in speech};assert len(participants)==len(set(participants.values()))
        scenes.append({'case_id':f'S4_{n:02}','title':title,'split':'development','family_id':family or f'S4_{n:02}',
            'duration_s':duration,'sample_rate_hz':FS,'channels':['MIC0','MIC1','MIC2','MIC3'],
            'receiver_configuration':dict(zip(['room_table','recorder_position','orientation','obstructed'],next(iter(groups)))),
            'cast':participants,'segments':segments,'overlap_intervals':overlaps,'overlap_scoring_limited':bool(overlaps),
            'relative_source_level_db':relative_db,'relative_source_level_scalar':10**(relative_db/20),
            'coverage_note':coverage,'target_set':'all scheduled speech speakers retained in evaluation truth; no production focus selection',
            'transcript_valid':True,'estimated_activity_only_for_scoring':True,'fresh_device_and_H2_between_scenes':True})
    base=[('A1','L',3),('B1','R',11),('A2','L',21)]
    scene(1,'Common Voice A-B-A nominal',base,'ABA_LEVEL')
    scene(2,'Common Voice A-B-A quiet -6dB',base,'ABA_LEVEL',-6)
    scene(3,'Common Voice A-B-A louder +6dB',base,'ABA_LEVEL',6)
    scene(4,'Common Voice A-B-A swapped seats',[(a,{'L':'R','R':'L'}[r],t) for a,r,t in base],'ABA_LEVEL')
    scene(5,'A alone on right path',[('A1','R',3),('A2','R',12)],'SAME_RIGHT')
    scene(6,'B alone on right path',[('B1','R',3),('B2','R',13)],'SAME_RIGHT')
    # Full short utterances; no invented yes/no transcript or mid-word crop.
    scene(7,'Short complete replies, alternating contributors',[('E3','LR',3),('D1','LL',7),('E4','LR',11.3),('D2','LL',15.3)],coverage='Shortest eligible complete clips, 3.05-4.00s, not subsecond yes/no coverage')
    scene(8,'Long paused returning speaker',[('A3','L',3),('B3','R',14),('A4','L',30)],'PAUSED_RETURN')
    scene(9,'Same person relocates during silence',[('F1','L',3),('F2','R',17)],'RELOCATION')
    scene(10,'Partial overlap, B interrupts A',[('A2','L',3),('B1','R',6),('A3','L',16)],'OVERLAP_1')
    scene(11,'Partial overlap, reciprocal returns',[('C1','LR',3),('D3','LL',5),('D4','LL',14),('C2','LR',17)],'OVERLAP_2')
    scene(12,'Partial overlap at main table',[('E2','ML',3),('F3','MR',5),('E1','ML',16)],'OVERLAP_3')
    scene(13,'Close folded directions',[('C3','LC',3),('D2','FC',11),('C4','LC',19)],'FOLDED_SEPARATION',coverage='Measured path contrast: distance1.00/1.02m; direction and path/distance change together versus scene14')
    scene(14,'Separated folded directions',[('C3','LR',3),('D2','LL',11),('C4','LR',19)],'FOLDED_SEPARATION',coverage='Measured path contrast: distance0.80/0.76m; not an isolated angular-separation effect')
    scene(15,'Front-rear ambiguous sources',[('E1','F',3),('F1','B',11),('E2','F',21)],'FRONT_REAR')
    pair=[('A3','ML',3),('B2','MR',12),('A4','ML',21)]
    scene(16,'Matched main-table flat',pair,'POSE_PAIR')
    scene(17,'Matched main-table upright',[(a,r+'U',t) for a,r,t in pair],'POSE_PAIR')
    pair=[('C2','KL',3),('D3','KR',12),('C3','KL',21)]
    scene(18,'Matched kitchen clear',pair,'OBSTRUCTION_PAIR')
    scene(19,'Matched kitchen obstructed',[(a,r+'O',t) for a,r,t in pair],'OBSTRUCTION_PAIR')
    scene(20,'Near talker and distant competing talker',[('E2','ML',3),('F4','MD',6),('E3','ML',19)],'NEAR_DISTANT')
    scene(21,'Near talker plus distant point noise',[('E2','ML',3),('E3','ML',19)],'NEAR_NOISE',noise=('MD',2,25,-30))
    scene(22,'Digital silence',[],'NOISE_CONTROLS')
    scene(23,'Point noise only',[],'NOISE_CONTROLS',noise=('B',2,27,-30))
    scene(24,'Speech plus identical point noise',[('E4','L',3),('F4','R',11),('E1','L',20)],'NOISE_CONTROLS',noise=('B',2,27,-30))
    return scenes,sources,rirs,cast

def noise_source(seg):
    n=seg['source_stop_sample']-seg['source_start_sample'];rng=np.random.default_rng(seg['seed'])
    x=lfilter([1],[1,-.96],rng.standard_normal(n))
    x*=10**(seg['source_rms_dbfs']/20)/np.sqrt(np.mean(x*x))
    ramp=.5-.5*np.cos(np.linspace(0,np.pi,3200));x[:3200]*=ramp;x[-3200:]*=ramp[::-1]
    return x

def synthesize(scene,sources,rirs,policy):
    out=np.zeros((round(scene['duration_s']*FS),4),np.float64)
    for seg in scene['segments']:
        if seg['kind']=='utterance':
            src=sources[seg['source_id']];x,fs=sf.read(src['decoded_16k_binding']['path'],dtype='float64');assert fs==FS and x.ndim==1
            x=x*policy['source_scalars'][seg['source_id']]['scalar']*scene['relative_source_level_scalar']
        else:
            x=noise_source(seg)
        h,rate=sf.read(rirs[seg['rir_id']]['file']['path'],dtype='float64',always_2d=True);assert rate==FS and h.shape[1]==4
        a=seg['source_start_sample']
        for j in range(4):
            y=fftconvolve(x,h[:,j]);assert a+len(y)<=len(out);out[a:a+len(y),j]+=y
    out*=policy.get('common_bank_headroom_scalar',1.)
    return out

def worker(job):
    scene,sources,rirs,policy,mode=job;x=synthesize(scene,sources,rirs,policy)
    if mode=='measure':return {'case_id':scene['case_id'],'peak':float(np.max(np.abs(x)))}
    x32=x.astype(np.float32);again=synthesize(scene,sources,rirs,policy).astype(np.float32)
    assert np.array_equal(x32,again),'Regeneration changed samples'
    assert np.isfinite(x32).all() and np.max(np.abs(x32))<=.250001
    path=BANK/'wav'/(scene['case_id']+'_mic4.wav');path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        previous,fs=sf.read(path,dtype='float32',always_2d=True)
        if fs!=FS or not np.array_equal(previous,x32):
            # Only reached through explicit pre-capture review refresh. Keep the
            # superseded draft bytes and bind a distinct reviewed filename.
            path=path.with_name(scene['case_id']+'_mic4_review_'+hashlib.sha256(x32.tobytes()).hexdigest()[:12]+'.wav')
            if path.exists():
                previous,fs=sf.read(path,dtype='float32',always_2d=True);assert fs==FS and np.array_equal(previous,x32)
            else:sf.write(path,x32,FS,subtype='FLOAT')
    else:sf.write(path,x32,FS,subtype='FLOAT')
    check,fs=sf.read(path,dtype='float32',always_2d=True);assert np.array_equal(check,x32)
    return {'case_id':scene['case_id'],'canonical_audio':bind(path),'peak_fs':float(np.max(np.abs(x32))),
        'per_mic_rms_dbfs':[float(20*np.log10(v)) if v>0 else None for v in np.sqrt(np.mean(x32.astype(float)**2,axis=0))],
        'pcm_sha256':hashlib.sha256(x32.astype('<f4').tobytes()).hexdigest(),
        'validation':{'finite':True,'headroom':True,'float32_roundtrip':True,'regenerated_identical':True,'no_per_mic_gain':True}}

def run(refresh_before_capture=False):
    if (BANK/'SCENE_MANIFEST.json').exists():
        old=read(BANK/'SCENE_MANIFEST.json')
        if not refresh_before_capture:
            for b in old['code_bindings']:bind(b['path'],b['sha256'])
            bind(old['source_manifest_input']['path'],old['source_manifest_input']['sha256'])
            bind(old['source_level_policy']['path'],old['source_level_policy']['sha256'])
            for scene in old['scenes']:bind(scene['canonical_audio']['path'],scene['canonical_audio']['sha256'])
            for r in old['selected_rirs']:bind(r['file']['path'],r['file']['sha256'])
            print('Compatible frozen bank verified; policies/manifests retained without rewriting.');return
        ledger=REPORT/'physical_ledger.json'
        assert not ledger.exists() or not read(ledger)['passes'],'Review refresh forbidden after physical playback'
        archive=BANK/('pre_review_archive_'+now().replace(':','').replace('+','_'));archive.mkdir()
        for p in BANK.glob('*.json'):shutil.copy2(p,archive/p.name)
    source_path=SIM/'staging/s4_sources/SOURCE_AND_SPLIT_MANIFEST.json';source=read(source_path)
    records={r['run_id']:r for r in read(SIM/'rir_library/v1/RIR_MANIFEST.json')['records']}
    scenes,selected,rirs,cast=make_plan(source,records)
    sources={s['source_id']:s for s in source['sources'] if s['split']=='development' and s['usage']=='probe'}
    # The dry policy is decided from the bounded source shortlist before any XVF/H2 outputs.
    policy={'schema':'s4_source_level_v1','frozen_utc':now(),'target_active_rms_dbfs':-24,'maximum_boost_db':12,
        'source_peak_cap_fs':.5,'active_estimator':source['sources'][0]['quality']['estimator'],
        'active_window_samples':320,'active_window_scope':'Full original clip, 20ms frame RMS, threshold=max(p95 frame RMS *10^(-25/20),10^(-50/20)); estimated preparation/scoring activity only',
        'rule':'min(10^(-24/20)/active_rms,0.5/source_peak); reject requested RMS boost >12dB; apply once to dry source before convolution',
        'resampler':source['resampler'],'source_scalars':{},'rir_normalization':False,'per_mic_normalization':False,
        'additional_distance_gain':False,'additional_acquisition_gain_delay':False,'second_reverberation':False,
        'common_bank_headroom_scalar':1.,'headroom_rule':'One attenuation-only scalar across the entire bank including matched variants, max four-mic peak0.25FS',
        'level_scope':'Numerical relative source drive; not calibrated acoustic SPL','S3_PCM_times_0_25':'Historical S3 fixtures only, not applied to this source cohort'}
    for id_,src in sources.items():
        bind(src['source_binding']['path'],src['source_binding']['sha256']);bind(src['decoded_16k_binding']['path'],src['decoded_16k_binding']['sha256'])
        assert hashlib.sha256(src['transcript'].encode()).hexdigest()==src['transcript_sha256']
        requested=10**(-24/20)/src['quality']['active_rms'];assert 20*np.log10(requested)<=12
        gain=min(requested,.5/src['quality']['peak']);policy['source_scalars'][id_]={'scalar':gain,'gain_db':float(20*np.log10(gain)),'active_rms_before':src['quality']['active_rms'],'active_rms_after':src['quality']['active_rms']*gain,'source_peak_after':src['quality']['peak']*gain}
    check_storage();BANK.mkdir(parents=True,exist_ok=True)
    with Progress('rendering',48) as progress, concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        peaks=[]
        for result in pool.map(worker,[(s,sources,rirs,policy,'measure') for s in scenes]):peaks.append(result['peak']);progress.done+=1;progress.case=result['case_id']
        policy['common_bank_headroom_scalar']=min(1.,.25/max(peaks));policy['unattenuated_peak_fs']=max(peaks)
        for target in [BANK,REPORT]:save(target/'SOURCE_LEVEL_POLICY.json',policy)
        outputs=[]
        for result in pool.map(worker,[(s,sources,rirs,policy,'render') for s in scenes]):outputs.append(result);progress.done+=1;progress.case=result['case_id']
    for s,o in zip(scenes,outputs):assert s['case_id']==o['case_id'];s.update(o)
    for c in scenes:
        for s in c['segments']:
            if s['kind']=='synthetic_point_noise':
                dry=noise_source(s);s['dry_noise_float64_sha256']=hashlib.sha256(dry.astype('<f8').tobytes()).hexdigest()
                s['actual_post_fade_rms_dbfs']=float(20*np.log10(np.sqrt(np.mean(dry*dry))))
    noise_only=[]
    for c in scenes[22:24]:
        q=copy.deepcopy(c);q['segments']=[s for s in q['segments'] if s['kind']=='synthetic_point_noise']
        noise_only.append(synthesize(q,sources,rirs,policy).astype('<f4'))
    assert np.array_equal(*noise_only),'Noise23/24 component mismatch'
    used=sorted({s['source_id'] for c in scenes for s in c['segments'] if s['kind']=='utterance'})
    dev_ids={s['identity'] for s in sources.values()};reserve_ids={s['identity'] for s in source['sources'] if s['split']=='downstream_reserve'}
    assert not dev_ids&reserve_ids
    probe_hash={s['source_binding']['sha256'] for s in sources.values()};other_hash={s['source_binding']['sha256'] for s in source['sources'] if s['usage']!='probe'};assert not probe_hash&other_hash
    source=copy.deepcopy(source);source['actual_S4_contribution']={'unique_probe_utterances_used':len(used),'used_source_ids':used,
        'development_contributors':len(dev_ids),'common_voice_fraction_of_used_utterances':1.,'other_datasets_used':[],
        'total_scheduled_utterance_instances':sum(s['kind']=='utterance' for c in scenes for s in c['segments']),
        'total_scheduled_dry_speech_s':sum((s['source_stop_sample']-s['source_start_sample'])/FS for c in scenes for s in c['segments'] if s['kind']=='utterance')}
    source['frozen_level_policy']=str(BANK/'SOURCE_LEVEL_POLICY.json')
    manifest={'schema':'s4_scene_bank_v2','run_id':RUN_ID,'frozen_utc':now(),'source_manifest_input':bind(source_path),'source_level_policy':bind(BANK/'SOURCE_LEVEL_POLICY.json'),
        'angle_policy':ANGLE_POLICY,'rir_library_manifest_sha256':'468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546',
        'selected_rirs':list(rirs.values()),'cast':cast,'scenes':scenes,'canonical_scene_count':24,
        'room_split':{'development':sorted({s['receiver_configuration']['room_table'] for s in scenes}),'downstream_reserve':['Upper Loeb'],
        'reserve_limit':'Upper Loeb already examined in RIR processing; not an unseen test of RIR extraction','all_pose_obstruction_variants_grouped_for_split':True},
        'validation':{'status':'PASS','scenes':24,'identity_uniqueness':True,'same_receiver_per_scene':True,'no_excluded_RIR':True,'all_distances_le_5m':True,
        'source_split_disjoint':True,'probe_enrollment_bytes_disjoint':True,'transcript_hash_binding':True,'time_origin_50ms_retained':True,'all_reproducible_float32':True,
        'noise23_24_component_identical':True,'noise23_24_float32_sha256':hashlib.sha256(noise_only[0].tobytes()).hexdigest()},
        'code_bindings':[bind(Path(__file__)),bind(SIM/'scripts/s4_geometry.py')],'render_workers':4,'inner_numerical_threads':1}
    for target in [BANK,REPORT]:
        save(target/'SOURCE_AND_SPLIT_MANIFEST.json',source);save(target/'SCENE_MANIFEST.json',manifest);save(target/'ANGLE_LABEL_POLICY.json',ANGLE_POLICY)
    save(REPORT/'scene_validation.json',manifest['validation'])
    print(json.dumps({'scenes':24,'duration_s':sum(s['duration_s'] for s in scenes),'source_contribution':source['actual_S4_contribution'],'peak':max(s['peak_fs'] for s in scenes),'headroom_scalar':policy['common_bank_headroom_scalar']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--refresh-before-capture',action='store_true');a=p.parse_args();run(a.refresh_before_capture)
