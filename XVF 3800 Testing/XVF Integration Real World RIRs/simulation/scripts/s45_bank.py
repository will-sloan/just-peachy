"""Frozen 240-scene expansion, deterministic four-worker renderer. README_S45_BANK.md."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
import argparse, collections, concurrent.futures, copy, csv, math
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve
from s45_common import *
from s4_geometry import source_label, lab_to_native_deg

FS=16000
SOURCE_PATH=SIM/'staging/s45_sources/SOURCE_AND_SPLIT_MANIFEST.json'
NOISE_PATH=SIM/'staging/s45_noise/NOISE_CATALOG.json'
GROUP_KEYS=['room_table','recorder_position','orientation','obstructed']
EXCLUDED='JPXVF_P1_R02_T01_D01_S02_F00_NAT_CU_R13'

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False,default=str).encode()).hexdigest()
def group(r):return tuple(r['geometry'][k] for k in GROUP_KEYS)
def coordinates(r):return (r['geometry']['speaker_angle_deg_effective'],r['geometry']['source_distance_m_effective'])

def load_rirs():
    original=read(SIM/'rir_library/v1/RIR_MANIFEST.json');out={}
    assert len(original['records'])==121
    for row in original['records']:
        if not row['can_proceed_to_hil_proof'] or row['run_id']==EXCLUDED:continue
        assert row['capture_audit_pass'] and row['original_acquisition_status'] in ['PASS','REVIEW']
        g=copy.deepcopy(row['geometry']);assert 0<g['source_distance_m_effective']<=5
        g['active_angle_label']=source_label(g['speaker_angle_deg_effective'])
        out[row['run_id']]={'run_id':row['run_id'],'geometry':g,'time_origin':row['time_origin'],'file':row['output'],'frames':row['output']['frames'],'status':row['status'],'limitations':row['limitations'],'can_proceed_to_hil_proof':True}
    assert len(out)==120
    return out

class CastAllocator:
    def __init__(self,sources):
        self.sources={s['source_id']:s for s in sources};self.people=collections.defaultdict(list)
        self.used=collections.Counter();self.clip_used=collections.Counter()
        for s in sources:
            if s['usage'] not in ['probe','reserve_probe']:continue
            if s['duration_s']>10:continue
            self.people[(s['split'],s['dataset'],s['identity'])].append(s)
        self.corpora=sorted({k[1] for k in self.people})
    def cast(self,partition,index,n):
        corp=self.corpora[index%len(self.corpora)]
        candidates=[k for k in self.people if k[0]==partition and k[1]==corp]
        assert candidates,'Missing eligible source partition '+str((partition,corp))
        n=min(n,len(candidates))
        selected=sorted(candidates,key=lambda k:(self.used[k],k))[:n]
        for k in selected:self.used[k]+=1
        return selected
    def clip(self,key,short=False):
        rows=self.people[key]
        # Credible whole short clips only; no waveform/ASR-driven transcript cropping.
        if short:rows=sorted(rows,key=lambda s:(s['duration_s'],self.clip_used[s['source_id']],s['source_id']))[:min(3,len(rows))]
        else:
            moderate=[s for s in rows if 2<=s['duration_s']<=7]
            if moderate:rows=moderate
        s=min(rows,key=lambda s:(self.clip_used[s['source_id']],s['source_id']))
        self.clip_used[s['source_id']]+=1;return s

def build_plan(sm,nm,rirs):
    sources=copy.deepcopy(sm['sources'])
    assert {s['dataset'] for s in sources}<={'CMU ARCTIC','HiFiTTS','Common Voice'},'Only user-approved speech corpora'
    legacy=SIM/'staging/s45_sources/LEGACY_DEVELOPMENT_PROBES.json'
    if legacy.exists():sources+=copy.deepcopy(read(legacy)['sources'])
    for source in sources:source['duration_s']=source['samples']/FS
    allocator=CastAllocator(sources)
    allgroups=collections.defaultdict(list)
    for r in rirs.values():allgroups[group(r)].append(r)
    for key in allgroups:allgroups[key].sort(key=lambda r:r['run_id'])
    flat=[g for g in sorted(allgroups) if g[2]=='FLAT' and not g[3] and len(allgroups[g])>=3]
    regular=[g for g in flat if g[0]!='Upper Loeb'];upper=[g for g in flat if g[0]=='Upper Loeb']
    assert regular and upper
    noise=nm.get('prepared_segments',[])
    assert noise,'No verified real-noise segments available; preserve pending dependent plan'
    prepared={r['noise_id']:r for r in noise}
    scenes=[];pair_cache={};speech_lookup={s['source_id']:s for s in sources}
    with (PACK/'SCENE_PLAN.csv').open(encoding='utf-8-sig',newline='') as handle:alloc=list(csv.DictReader(handle))
    def choose_noise(part,index,count=1,instrumental=False,strict=False,environmental=False):
        candidates=[r for r in noise if r['split']==part]
        if environmental:
            preferred=[r for r in candidates if r['category'] in ['stationary_appliance_noise','transient_event_noise']]
            candidates=preferred or [r for r in candidates if r['category']=='environmental_ambience']
            assert candidates,'No metadata-supported environmental noise for F10 '+part
        if strict:
            candidates=[r for r in candidates if r['strict_nonspeech_eligible']]
            assert candidates,'No documented speech-free noise parent in '+part
        if instrumental:
            chosen=[r for r in candidates if 'music' in r['category'].lower() or 'instrument' in r['category'].lower()]
            if chosen:candidates=chosen
        assert candidates
        # All available parents receive deterministic use; never task-score filtering.
        candidates=sorted(candidates,key=lambda r:r['noise_id'])
        return [candidates[(index+j)%len(candidates)] for j in range(min(count,len(candidates)))]
    for family in alloc:
        fid=family['family_id'];fn=int(fid[1:]);dev=int(family['development'])
        strata=['development']*dev+['new_source_reserve']*int(family['new_source_reserve'])+['upper_loeb_acoustic_reserve']*int(family['upper_loeb_acoustic_reserve'])+['joint_reserve']*int(family['joint_reserve'])
        assert len(strata)==20
        for i,stratum in enumerate(strata):
            case_id=f'S45_{fn:02}_{i+1:02}';split='development' if stratum=='development' else 'reserve'
            source_partition='downstream_reserve' if stratum in ['new_source_reserve','joint_reserve'] else 'development'
            noise_partition='reserve' if source_partition=='downstream_reserve' else 'development'
            isupper=stratum in ['upper_loeb_acoustic_reserve','joint_reserve']
            available=upper if isupper else regular
            g=available[(fn+i)%len(available)]
            if fn==8:g=[x for x in regular if (x[0],x[1],x[2],True) in allgroups][i%2]
            if fn==9:g=[x for x in regular if max(coordinates(r)[1] for r in allgroups[x])>=3][i%3]
            paths=allgroups[g]
            ordered=sorted(paths,key=lambda r:lab_to_native_deg(coordinates(r)[0]))
            positions=[ordered[-1],ordered[0],ordered[len(ordered)//2]]
            if fn==9:positions=[min(paths,key=lambda r:coordinates(r)[1]),max(paths,key=lambda r:coordinates(r)[1]),ordered[-1]]
            if fn==5:
                combinations=[(a,b) for ai,a in enumerate(paths) for b in paths[ai+1:]]
                distance=lambda p:abs(lab_to_native_deg(coordinates(p[0])[0])-lab_to_native_deg(coordinates(p[1])[0]))
                p=min(combinations,key=distance) if i%2==0 else max(combinations,key=distance)
                positions=[p[0],p[1],ordered[len(ordered)//2]]
                if i>=16:
                    possible=[p for p in combinations if abs((coordinates(p[0])[0]-coordinates(p[1])[0]+180)%360-180)>100]
                    if possible:positions=list(min(possible,key=distance))+[ordered[len(ordered)//2]]
            within=strata[:i].count(stratum)
            # Paired conditions are cloned before any measured output, preserving source schedule.
            paired=fn in [5,7,8] or (fn==12 and (stratum=='development' and within<14 or strata.count(stratum)%2==0))
            matched_triple=fn in [1,10] and stratum=='development'
            group_index=within//3 if matched_triple else within//2
            pair_key=(fid,stratum,group_index)
            clone=matched_triple and within%3>0 or paired and within%2==1
            if clone:
                scene=copy.deepcopy(pair_cache[pair_key]);scene['case_id']=case_id
                scene['matched_pair_id']=fid+'_'+stratum+'_'+str(within//2) if paired else None
                if fn==1:
                    level=[-6,0,6][within%3]
                    for seg in scene['segments']:seg['relative_source_db']=level;seg['relative_source_scalar']=10**(level/20)
                    scene['title']='Matched source-level control '+str(level)+' dB'
                elif fn==10:
                    snr=[20,10,0][within%3];scene['noise_policy']['snr_db']=snr
                    scene['title']='Matched localized environmental noise '+str(snr)+' dB SNR'
                elif fn in [5,7,8]:
                    oldg=tuple(scene['receiver_configuration'][k] for k in GROUP_KEYS)
                    newg=oldg if fn==5 else (oldg[0],oldg[1],'UPRIGHT',oldg[3]) if fn==7 else (oldg[0],oldg[1],oldg[2],True)
                    assert newg in allgroups
                    mapping={coordinates(r):r for r in allgroups[newg]}
                    spatial_order=sorted(allgroups[newg],key=lambda r:lab_to_native_deg(coordinates(r)[0]))
                    for seg in scene['segments']:
                        replacement=(spatial_order[0] if seg.get('participant_id')=='A' else spatial_order[-1]) if fn==5 else mapping[coordinates(rirs[seg['rir_id']])];seg['rir_id']=replacement['run_id'];seg['convolution_stop_sample']=seg['source_stop_sample']+replacement['frames']-1
                    scene['receiver_configuration']=dict(zip(GROUP_KEYS,newg));scene['title']+=' / separated measured paths' if fn==5 else ' / upright' if fn==7 else ' / obstructed'
                else:
                    scene['segments']=copy.deepcopy(scene['snr_reference_segments'])+scene['segments'];scene['title']='Paired speech with identical real-noise component';scene['cast']={s['participant_id']:s['speaker_key'] for s in scene['segments'] if s['kind']=='utterance'}
                scenes.append(scene);continue
            n=1 if fn==1 else 3 if fn==2 and i%2==1 or fn==11 and i%3==0 else 2
            castkeys=allocator.cast(source_partition,fn+within//3 if matched_triple else fn+i,n)
            if fn in [1,3]:turns=[0]*3 if fn==1 else [j%len(castkeys) for j in range(6)]
            elif fn==2:turns=[0,1,0] if i%2==0 else [0,1,2 if len(castkeys)>2 else 0,0]
            elif fn==6:turns=[0,1,0]
            elif fn==11:turns=[0,1,2 if len(castkeys)>2 else 0,0]
            else:turns=[0,1,0]
            segs=[];cursor=3.;known={};clip_sequence=[]
            for ti,person in enumerate(turns):
                key=castkeys[person];src=allocator.clip(key,short=fn==3);clip_sequence.append(src)
                if fn==4 and ti==1:at=max(3.2,segs[0]['source_stop_sample']/FS-min(2.,src['duration_s']*.5))
                elif fn==9 and ti==1:
                    ta,tb=max(segs[0]['activity_ranges_samples_estimated'],key=lambda p:p[1]-p[0])
                    ba,bb=max(src['quality']['active_ranges_samples_estimated'],key=lambda p:p[1]-p[0])
                    at=max(1.,((ta+tb-ba-bb)/2-800)/FS)
                elif fn==11 and i%3==0 and ti in [1,2]:at=4.+ti*.7
                else:at=cursor
                path=positions[person%len(positions)]
                if fn==6 and ti==2:path=positions[1]
                start=round(at*FS);stop=start+src['samples'];label=chr(65+person);known[label]=key[2]
                relative_db=[-6,0,6][i%3] if fn==1 else (-6 if fn==9 and person==1 and i%2 else 0)
                segs.append({'kind':'utterance','source_id':src['source_id'],'speaker_key':key[2],'participant_id':label,'dataset':src['dataset'],'quality_partition':src.get('quality_partition'),'source_start_sample':start,'source_stop_sample':stop,'convolution_stop_sample':stop+path['frames']-1,'rir_expected_significant_onset_sample':start+800,'rir_id':path['run_id'],'transcript':src['transcript'],'transcript_normalized':src['transcript_normalized'],'transcript_sha256':hashlib.sha256(src['transcript'].encode()).hexdigest(),'whole_clip':True,'word_times':None,'source_crop_samples':[0,src['samples']],'timing_provenance':'native whole clip; estimated activity, no exact phonetic timing','preparation_gain_scalar':src['preparation_gain']['scalar'] if isinstance(src['preparation_gain'],dict) else src['preparation_gain'],'relative_source_db':relative_db,'relative_source_scalar':10**(relative_db/20),'activity_ranges_samples_estimated':[[start+800+a,start+800+b] for a,b in src['quality']['active_ranges_samples_estimated']],'role':'background_talker' if fn in [9,11] and person else 'target_or_conversation','source_split':source_partition})
                cursor=max(cursor,stop/FS)+(8 if fn==6 and ti==1 else .25 if fn==3 else 2.)
            duration=max(45,math.ceil(max(s['convolution_stop_sample'] for s in segs)/FS+5))
            if fn==6 and i in [0,5,10]:
                segs[-1]['source_start_sample']+=40*FS;segs[-1]['source_stop_sample']+=40*FS;segs[-1]['convolution_stop_sample']+=40*FS;segs[-1]['rir_expected_significant_onset_sample']+=40*FS
                segs[-1]['activity_ranges_samples_estimated']=[[a+40*FS,b+40*FS] for a,b in segs[-1]['activity_ranges_samples_estimated']];duration=100
            assert duration<=60 or fn==6 and duration==100
            speech=copy.deepcopy(segs);noise_segs=[];noise_mode=None
            if fn in [10,11,12] and not (fn==11 and i%3==0):
                count=3 if fn==11 and i%3==1 else 1
                selected_noise=choose_noise(noise_partition,(fn-10)*20+i,count,fn==11 and i%3==2,strict=fn==12,environmental=fn==10)
                for ni,ns in enumerate(selected_noise):
                    start=2*FS;take=min(ns['samples'],round((duration-7)*FS));path=positions[(ni+1)%len(positions)]
                    noise_segs.append({'kind':'real_noise','source_id':ns['noise_id'],'parent_id':ns['parent_id'],'rir_id':path['run_id'],'source_start_sample':start,'source_stop_sample':start+take,'source_crop_samples':[0,take],'convolution_stop_sample':start+take+path['frames']-1,'speech_content':ns['speech_content'],'strict_nonspeech_eligible':ns['strict_nonspeech_eligible'],'category':ns['category'],'source_split':noise_partition,'role':'environmental_interference'})
                noise_mode={'snr_db':[20,10,0][i%3],'reference':'Mean target-speech energy over MIC0..3 on estimated target-active windows; same windows for interferer; one shared four-channel noise scalar','component_seed':450000+fn*100+i,'model':'Measured-path multipoint proxy' if count>1 else 'Measured-path localized source; environmental recording may already be reverberant'}
            if fn==12:
                segs=[];known={}
                if stratum=='development' and within==14:noise_segs=[];noise_mode=None
            segs+=noise_segs
            scene={'case_id':case_id,'family_id':fid,'family':family['family'],'title':family['family']+' '+str(i+1),'split':split,'reserve_stratum':stratum,'source_partition':source_partition,'duration_s':duration,'sample_rate_hz':FS,'channels':['MIC0','MIC1','MIC2','MIC3'],'receiver_configuration':dict(zip(GROUP_KEYS,g)),'cast':known,'segments':segs,'snr_reference_segments':speech if noise_mode else [],'noise_policy':noise_mode,'speech_interference_policy':{'requested_sir_db':[0,6,-6][i%3],'reference':'Mean target microphone energy over all4 channels on target-active windows; one scalar to whole background-talker image'} if fn==9 else None,'relative_source_level_scalar':1.,'relative_source_level_db':0,'matched_pair_id':fid+'_'+stratum+'_'+str(within//2) if paired else None,'matched_group_id':fid+'_'+stratum+'_'+str(group_index) if matched_triple or paired else None,'transcript_valid':all(n['strict_nonspeech_eligible'] for n in noise_segs),'all_speaker_reference_complete':all(n['strict_nonspeech_eligible'] for n in noise_segs),'estimated_activity_only_for_scoring':True,'task_scoring_allowed':split=='development','coverage_limitations':['Source domains remain distinct; nominal manual angle; measured paths can differ in distance/transfer.']}
            if fn==3:scene['short_turn_durations_s']=[s['duration_s'] for s in clip_sequence]
            if paired or matched_triple:pair_cache[pair_key]=copy.deepcopy(scene)
            scenes.append(scene)
    # Recalculate overlap/truth after paired clones; all intelligible speech retained.
    for scene in scenes:
        utter=[s for s in scene['segments'] if s['kind']=='utterance'];over=[]
        label_counts=collections.Counter()
        for seg in utter:
            label_counts[seg['participant_id']]+=1
            seg['utterance_label']=seg['participant_id']+str(label_counts[seg['participant_id']])
        for j,a in enumerate(utter):
            for b in utter[j+1:]:
                lo=max(a['source_start_sample'],b['source_start_sample']);hi=min(a['source_stop_sample'],b['source_stop_sample'])
                if hi>lo:over.append({'start_sample':lo,'stop_sample':hi,'participants':[a['participant_id'],b['participant_id']],'scope':'Whole-clip schedule; not exact phonetic overlap'})
        scene['overlap_intervals']=over;scene['overlap_scoring_limited']=bool(over)
        scene['all_speaker_references']=[{'source_id':s['source_id'],'participant_id':s['participant_id'],'transcript':s['transcript'],'start_sample':s['source_start_sample'],'stop_sample':s['source_stop_sample'],'role':s['role']} for s in utter]
        scene['target_references']=[r for r in scene['all_speaker_references'] if r['role']!='background_talker']
        scene['background_references']=[r for r in scene['all_speaker_references'] if r['role']=='background_talker']
        assert len(scene['cast'])==len(set(scene['cast'].values()))
        assert all(group(rirs[s['rir_id']])==tuple(scene['receiver_configuration'][k] for k in GROUP_KEYS) for s in scene['segments'])
        assert not any(s['source_start_sample']<0 or s['convolution_stop_sample']>scene['duration_s']*FS-3*FS for s in scene['segments'])
    assert len(scenes)==240 and sum(s['split']=='development' for s in scenes)==180
    sentinels=[]
    for family in alloc:
        candidates=[s for s in scenes if s['family_id']==family['family_id'] and s['split']=='development']
        # Fixed indices alternate corpus/condition; F12 includes its digital-silence control.
        selected=[candidates[0],candidates[14] if family['family_id']=='F12' else candidates[1] if family['family_id'] in ['F05','F07','F08'] else candidates[2] if family['family_id']=='F10' else candidates[4]]
        sentinels += [s['case_id'] for s in selected]
    return scenes,speech_lookup,prepared,sentinels

def component_audio(seg,sources,noises,rirs):
    if seg['kind']=='utterance':
        src=sources[seg['source_id']];b=src['decoded_16k_binding'];scalar=seg['preparation_gain_scalar']*seg['relative_source_scalar']
    else:
        src=noises[seg['source_id']];b={'path':src['prepared_path'],'sha256':src['prepared_sha256']};scalar=1.
    x,fs=sf.read(b['path'],dtype='float64');assert fs==FS and x.ndim==1
    lo,hi=seg['source_crop_samples'];x=x[lo:hi]*scalar
    h,hr=sf.read(rirs[seg['rir_id']]['file']['path'],dtype='float64',always_2d=True);assert hr==FS and h.shape[1]==4
    return np.column_stack([fftconvolve(x,h[:,j]) for j in range(4)])

def place_short_transients(scenes,sources,noises,rirs):
    """Freeze whole transient repeats before rendering, using source activity only."""
    peak_cache={}
    for scene in scenes:
        replacements=[]
        for original in scene['segments']:
            seg=original
            is_transient=seg.get('category')=='transient_event_noise'
            if seg['kind']!='real_noise' or seg['source_crop_samples'][1]-seg['source_crop_samples'][0]>=2*FS and not is_transient:
                replacements.append(seg);continue
            if is_transient and seg['source_crop_samples'][1]-seg['source_crop_samples'][0]>=2*FS:
                # Source-only deterministic event extraction, after parent-role
                # freeze. It is not arbitrary cropping of speech references.
                seg=copy.deepcopy(seg);ns=noises[seg['source_id']]
                raw,rate=sf.read(ns['prepared_path'],dtype='float64');assert rate==FS
                lo,hi=seg['source_crop_samples'];peak=lo+int(np.argmax(np.abs(raw[lo:hi])))
                begin=max(lo,peak-FS//4);end=min(hi,begin+2*FS)
                seg['source_crop_samples']=[begin,end]
                seg['noise_excerpt_selection']={'method':'Metadata-labelled transient: at most 2 seconds around largest dry absolute sample, with 250 ms pre-event where available','prepared_parent_peak_sample':peak,'original_planned_crop_samples':[lo,hi],'uses_device_or_model_output':False}
            key=(seg['source_id'],seg['rir_id'],tuple(seg['source_crop_samples']))
            if key not in peak_cache:
                y=component_audio(seg,sources,noises,rirs)
                peak_cache[key]=(int(np.argmax(np.sum(y*y,axis=1))),len(y))
            peak,frames=peak_cache[key]
            targets=[s for s in scene['snr_reference_segments'] if s.get('role')!='background_talker'][:3]
            assert targets,'A short transient needs predeclared target activity'
            for index,target in enumerate(targets):
                a,b=max(target['activity_ranges_samples_estimated'],key=lambda p:p[1]-p[0])
                center=(a+b)//2;start=max(0,center-peak)
                assert start+frames<=round(scene['duration_s']*FS)-3*FS
                copyseg=copy.deepcopy(seg);take=seg['source_crop_samples'][1]-seg['source_crop_samples'][0]
                copyseg.update(source_start_sample=start,source_stop_sample=start+take,convolution_stop_sample=start+frames,
                    transient_placement={'method':'Selected short noise event repeated at up to three declared target turns; convolved four-mic energy peak aligned to longest estimated activity interval center',
                    'repeat_index':index,'target_source_id':target['source_id'],'target_activity_interval_samples':[a,b],
                    'convolved_energy_peak_sample':peak,'target_center_sample':center,'uses_device_or_model_output':False})
                replacements.append(copyseg)
        scene['segments']=replacements


def render_raw(scene,sources,noises,rirs):
    n=round(scene['duration_s']*FS);speech=np.zeros((n,4),np.float64);interferer=np.zeros_like(speech);background=np.zeros_like(speech)
    def add(target,seg):
        y=component_audio(seg,sources,noises,rirs);at=seg['source_start_sample'];target[at:at+len(y)]+=y
    for seg in scene['segments']:
        target=(background if seg.get('role')=='background_talker' else speech) if seg['kind']=='utterance' else interferer
        add(target,seg)
    speech_interference=None
    if scene.get('speech_interference_policy'):
        mask=np.zeros(n,bool)
        for seg in scene['segments']:
            if seg['kind']=='utterance' and seg.get('role')!='background_talker':
                for a,b in seg['activity_ranges_samples_estimated']:mask[a:b]=True
        ps=float(np.mean(speech[mask]**2));pb=float(np.mean(background[mask]**2));assert ps>0 and pb>0
        requested=scene['speech_interference_policy']['requested_sir_db'];scalar=math.sqrt(ps/(pb*10**(requested/10)));background*=scalar
        achieved=10*math.log10(ps/float(np.mean(background[mask]**2)))
        speech_interference={'requested_sir_db':requested,'achieved_sir_db':achieved,'shared_background_scalar':scalar,'target_power':ps,'unscaled_background_power':pb,'target_active_samples':int(mask.sum()),'scope':scene['speech_interference_policy']['reference']}
        assert abs(achieved-requested)<1e-8
    speech+=background
    noise_details=None
    if scene['noise_policy']:
        reference=np.zeros_like(speech);mask=np.zeros(n,bool)
        for seg in scene['snr_reference_segments']:
            if seg['role']=='background_talker':continue
            add(reference,seg)
            for a,b in seg['activity_ranges_samples_estimated']:mask[max(0,a):min(n,b)]=True
        assert mask.any()
        ps=float(np.mean(reference[mask]**2));pn=float(np.mean(interferer[mask]**2));assert ps>0 and pn>0,'No reference-window noise energy'
        snr=scene['noise_policy']['snr_db'];scalar=math.sqrt(ps/(pn*10**(snr/10)));interferer*=scalar
        achieved=10*math.log10(ps/float(np.mean(interferer[mask]**2)))
        noise_details={'target_power_mean_four_mic':ps,'unscaled_noise_power_same_window':pn,'target_active_samples':int(mask.sum()),'shared_noise_scalar':scalar,'requested_snr_db':snr,'achieved_snr_db':achieved,'reference_scope':scene['noise_policy']['reference'],'interferer_float64_sha256':hashlib.sha256(interferer.tobytes()).hexdigest()}
        assert abs(achieved-snr)<1e-8
    x=speech+interferer;assert np.isfinite(x).all()
    return x,noise_details,speech_interference

def worker(job):
    scene,sources,noises,rirs,scalar,expected=job
    x,noise,sir=render_raw(scene,sources,noises,rirs);rawhash=hashlib.sha256(x.tobytes()).hexdigest();peak=float(np.max(np.abs(x)))
    result={'case_id':scene['case_id'],'unscaled_sha256':rawhash,'unscaled_peak_fs':peak,'noise_details':noise,'speech_interference_details':sir}
    if scalar is not None:
        assert rawhash==expected,'Re-rendered canonical input changed before freeze'
        y=(x*scalar).astype(np.float32);assert np.max(np.abs(y))<=.2500001
        path=PAYLOAD/'canonical_v2'/(scene['case_id']+'.wav');path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            prior,rate=sf.read(path,dtype='float32',always_2d=True);assert rate==FS and np.array_equal(prior,y),'Incompatible existing canonical file'
        else:sf.write(path,y,FS,subtype='FLOAT')
        result.update(canonical_audio=bind(path),common_family_headroom_scalar=scalar,canonical_peak_fs=float(np.max(np.abs(y))),deterministic_second_render_exact=True)
    return result

def main():
    final=BANK/'SCENE_MANIFEST.json'
    if final.exists():
        old=read(final);assert old['validation']['status']=='PASS'
        for scene in old['scenes']:bind(scene['canonical_audio']['path'],scene['canonical_audio']['sha256'])
        print('Existing frozen S4.5 bank verified; no rewrite');return
    sm=read(SOURCE_PATH);nm=read(NOISE_PATH);rirs=load_rirs();scenes,sources,noises,sentinels=build_plan(sm,nm,rirs)
    useds={s['source_id'] for sc in scenes for s in sc['segments']+sc['snr_reference_segments'] if s['kind']=='utterance'}
    usedn={s['source_id'] for sc in scenes for s in sc['segments'] if s['kind']!='utterance'}
    usedr={s['rir_id'] for sc in scenes for s in sc['segments']+sc['snr_reference_segments']}
    sources={k:v for k,v in sources.items() if k in useds};noises={k:v for k,v in noises.items() if k in usedn};rirs={k:v for k,v in rirs.items() if k in usedr}
    for s in sources.values():bind(s['decoded_16k_binding']['path'],s['decoded_16k_binding']['sha256'])
    for s in noises.values():bind(s['prepared_path'],s['prepared_sha256'])
    for r in rirs.values():r['file']=bind(r['file']['path'],r['file']['sha256'])
    place_short_transients(scenes,sources,noises,rirs)
    audio_s=sum(s['duration_s'] for s in scenes);assert audio_s<=LIMITS['canonical_audio_s']
    legacy_path=SIM/'staging/s45_sources/LEGACY_DEVELOPMENT_PROBES.json'
    plan={'legacy_development_sources_binding':bind(legacy_path) if legacy_path.exists() else None,'schema':'jp_s45_plan_v1','created_utc':now(),'scenes':scenes,'sentinel_scene_ids':sentinels,'sources_binding':bind(SOURCE_PATH),'noise_binding':bind(NOISE_PATH),'code':bind(Path(__file__)),'source_override':'No L2 ARCTIC; user-requested original CMU/HiFiTTS/Common Voice only','canonical_audio_s':audio_s}
    draft=BANK/'FROZEN_RENDER_PLAN.json'
    if draft.exists():assert read(draft)['scenes']==scenes,'Frozen plan incompatible; do not overwrite'
    first={};second={}
    with Progress('render_measure',240) as progress, concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        for result in pool.map(worker,[(s,sources,noises,rirs,None,None) for s in scenes]):first[result['case_id']]=result;progress.done+=1;progress.case=result['case_id']
    peaks={fid:max(first[s['case_id']]['unscaled_peak_fs'] for s in scenes if s['family_id']==fid) for fid in {s['family_id'] for s in scenes}}
    gains={f:min(1,.25/max(p,1e-30)) for f,p in peaks.items()}
    if not draft.exists():save(draft,{**plan,'frozen_utc':now(),'freeze_scope':'After source-only numerical input QC and before canonical second render, hardware or H2'})
    save(REPORT/'SENTINEL_PLAN.json',{'frozen_utc':now(),'selection_before_hardware_or_H2':True,'scene_ids':sentinels,'count':24,'reserve_jobs_allowed':0})
    with Progress('render_freeze',240) as progress, concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        for result in pool.map(worker,[(s,sources,noises,rirs,gains[s['family_id']],first[s['case_id']]['unscaled_sha256']) for s in scenes]):second[result['case_id']]=result;progress.done+=1;progress.case=result['case_id']
    for s in scenes:s.update(second[s['case_id']])
    # Matching noise-only/speech pairs must contain precisely the same convolved/scaled noise.
    for s in scenes:
        if s['family_id']=='F12' and s['matched_pair_id']:
            pair=[x for x in scenes if x['matched_pair_id']==s['matched_pair_id']]
            assert len(pair)==2 and pair[0]['noise_details']['interferer_float64_sha256']==pair[1]['noise_details']['interferer_float64_sha256']
    validation={'status':'PASS','scenes':240,'development':180,'reserve':60,'canonical_audio_s':audio_s,'deterministic_second_render_exact':240,'headroom_scalar_by_family':gains,'max_peak_fs':max(s['canonical_peak_fs'] for s in scenes),'geometry_compatible':True,'no_L2_ARCTIC':True,'no_reserve_task_scores':True,'source_and_noise_split_roles_preserved':True,'unique_speech_clips':len(sources),'unique_noise_segments':len(noises),'unique_noise_parents':len({s['parent_id'] for s in noises.values()}),'RIRs_used':len(rirs),'RIRs_allowed_unused':120-len(rirs)}
    manifest={**plan,'schema':'jp_s45_scene_manifest_v1','frozen_utc':now(),'scenes':scenes,'selected_sources':sources,'selected_noise':noises,'selected_rirs':rirs,'validation':validation,'source_preparation':'One recorded scalar before convolution; no RIR/per-mic normalization; one family headroom scalar after source/noise mixing','reserve_task_scoring':False}
    save(final,manifest);save(REPORT/'SCENE_MANIFEST.json',manifest);save(REPORT/'scene_validation.json',validation)
    with (BANK/'FUTURE_TRAINING_MANIFEST.jsonl').open('w',encoding='utf-8') as f:
        for s in scenes:
            row={'scene_id':s['case_id'],'split':s['split'],'reserve_stratum':s['reserve_stratum'],'canonical':s['canonical_audio'],'reference_manifest':str(final),'rights':[sources[x['source_id']]['rights'] if x['kind']=='utterance' else {'rights':noises[x['source_id']]['rights'],'parent_id':noises[x['source_id']]['parent_id'],'attribution':noises[x['source_id']].get('attribution')} for x in s['segments']],'rights_eligibility':'Project evaluation scope only; downstream release/training needs per-source review','acoustic_quality_eligibility':'Measured-path simulation; source reverb/noise and native RIR limits retained; not enclosure/generalization qualification','training_run_authorized':False,'split_eligible':s['split']=='development','reference_complete':s['all_speaker_reference_complete'],'single_speaker_embedding_eligible':len(s['cast'])==1 and not s['overlap_intervals'] and not any(x['kind']!='utterance' for x in s['segments']),'release_required_before_reserve_training':s['split']=='reserve'}
            f.write(json.dumps(row,allow_nan=False)+'\n')
    print(json.dumps(validation,indent=2))

if __name__=='__main__':main()
