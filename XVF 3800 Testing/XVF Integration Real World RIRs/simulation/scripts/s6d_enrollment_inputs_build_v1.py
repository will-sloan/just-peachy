"""Build exactly the existing 60 E and two900s file inputs. See README_S6D_ENROLLMENT_INPUTS_BUILD.md."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve

REPO=next(p for p in Path(__file__).resolve().parents if (p/'Software Validation from Datasets').is_dir())
SIM=REPO/'XVF 3800 Testing/XVF Integration Real World RIRs/simulation'
R=SIM/'reports/S6D/20260913T195357Z'
PAYLOAD=Path('G:/Just_Peachy_S6D/20260913T195357Z').resolve()
PLANS={'DEVICE_ENROLLMENT_INPUT_PLAN_V1.json':'22851e1e82ec43e803cf795ac8f1476a2a5f36d3c62c43309f34e2cb9d7f8a37',
    'CONTINUOUS_INPUT_PLAN_V1.json':'3a05db6dc5565a830d9656730296fbdd39c7358d61b81216e0be637d8f88188f'}
RATE=16000
CAP=40*2**30


def utc():return datetime.now(timezone.utc).isoformat()
def require(ok,message):
    if not ok:raise ValueError(message)
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def binding(path):
    path=Path(path).resolve(strict=True);h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':h.hexdigest()}
def verify(ref):
    got=binding(ref['path'])
    require(got['sha256']==ref['sha256'] and ('bytes' not in ref or got['bytes']==ref['bytes']),'Changed source: '+got['path'])
    return got
def pcm_hash(x):return hashlib.sha256(np.asarray(x,dtype='<f4').tobytes()).hexdigest()
def tree_bytes(root):
    total=0
    for folder,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            path=Path(folder)/name
            require(path.resolve().is_relative_to(root),'Payload tree has an external link: '+str(path))
        total+=sum((Path(folder)/n).stat().st_size for n in files)
    return total
def headroom(x):
    require(x.ndim==2 and x.shape[1]==4 and np.isfinite(x).all(),'Finite four-MIC block required')
    require(np.max(np.abs(x),initial=0)<1,'Unity input headroom failure; do not normalize')
    # Same signed even PCM24 representability rule as the frozen packer.
    counts=np.rint(np.asarray(x,dtype=np.float64)*2**22).astype(np.int64)*2
    require(not np.any(np.abs(counts)>=2**23),'PCM24 packing headroom failure')
def read_audio(ref,channels,frames,expected_pcm=None):
    verify(ref);info=sf.info(ref['path'])
    require((info.samplerate,info.channels,info.frames,info.subtype)==(RATE,channels,frames,'FLOAT'),'Source FLOAT16k/header mismatch')
    x,rate=sf.read(ref['path'],dtype='float32',always_2d=True)
    require(np.isfinite(x).all(),'Nonfinite source')
    if expected_pcm is not None:require(pcm_hash(x)==expected_pcm,'Source decoded PCM differs')
    return x


def render_enrollment(dry,rir,total_frames):
    require(dry.ndim==1 and rir.ndim==2 and rir.shape[1]==4,'Mono dry and four-MIC RIR required')
    full=np.column_stack([fftconvolve(dry.astype(np.float64),rir[:,i].astype(np.float64),mode='full') for i in range(4)])
    require(len(full)<=total_frames,'Full RIR tail would be clipped')
    x=np.pad(full,((0,total_frames-len(full)),(0,0)))
    headroom(x);headroom(x.astype(np.float32));return x


def header_and_fingerprints(path,frames):
    info=sf.info(path);require((info.samplerate,info.channels,info.frames,info.subtype)==(RATE,4,frames,'FLOAT'),'Built output header mismatch')
    hashes=[hashlib.sha256() for _ in range(4)];interleaved=hashlib.sha256();peaks=np.zeros(4);squares=np.zeros(4);nonzero=np.zeros(4,dtype=np.int64)
    with sf.SoundFile(path) as f:
        for x in f.blocks(blocksize=65536,dtype='float32',always_2d=True):
            headroom(x);interleaved.update(np.asarray(x,dtype='<f4').tobytes())
            for i in range(4):hashes[i].update(np.asarray(x[:,i],dtype='<f4').tobytes())
            peaks=np.maximum(peaks,np.max(np.abs(x),axis=0));squares+=np.sum(x.astype(np.float64)**2,axis=0);nonzero+=np.count_nonzero(x,axis=0)
    return {'audio':binding(path),'frames':frames,'sample_rate_hz':RATE,'channels':4,'subtype':'FLOAT','float32_pcm_sha256':interleaved.hexdigest(),
        'channel_fingerprints':[{'index':i,'float32_pcm_sha256':hashes[i].hexdigest(),'peak_abs':float(peaks[i]),'rms':float(np.sqrt(squares[i]/frames)),
            'nonzero_samples':int(nonzero[i])} for i in range(4)],'headroom':'PASS_UNITY_AND_PCM24_REPRESENTABILITY','source_gain':1.}


def write_enrollment(path,x):
    require(not path.exists(),'Preserve prior payload')
    sf.write(path,x,RATE,subtype='FLOAT')
    actual=read_audio(binding(path),4,len(x));require(np.array_equal(actual,x.astype(np.float32)),'Convolution FLOAT roundtrip mismatch')
    return header_and_fingerprints(path,len(x))|{'verification':'Every output FLOAT sample equals the full float64 convolution rounded once to float32'}


def write_continuous(path,session):
    require(not path.exists(),'Preserve prior payload');cursor=0;regions=[]
    with sf.SoundFile(path,mode='w',samplerate=RATE,channels=4,subtype='FLOAT') as output:
        for block in session['blocks']:
            start,stop=block['source_start_sample'],block['source_stop_sample']
            require(start==cursor and stop-start==720000,'Existing exact45s block schedule changed')
            if block['kind']=='explicit_digital_zero_gap':x=np.zeros((stop-start,4),dtype=np.float32);source=None
            else:
                require(block['kind']=='original_canonical_four_mic_scene' and block['copy_samples']==[0,720000] and block['gain_change']==1.,'Only exact full canonical block copies allowed')
                source=block['canonical_input_verified'];x=read_audio(source['binding'],4,stop-start,source['float32_pcm_sha256'])
            headroom(x);output.write(x);regions.append({'block_index':block['block_index'],'kind':block['kind'],'case_id':block.get('case_id'),
                'source_start_sample':start,'source_stop_sample':stop,'source_audio':source['binding'] if source else None,'float32_pcm_sha256':pcm_hash(x)})
            cursor=stop
    require(cursor==session['source_frames']==14400000,'Continuous900s frame count changed')
    require(Counter(r['kind'] for r in regions)=={'explicit_digital_zero_gap':2,'original_canonical_four_mic_scene':18},'Continuous scene/zero block count differs')
    with sf.SoundFile(path) as f:
        for region in regions:
            f.seek(region['source_start_sample']);x=f.read(region['source_stop_sample']-region['source_start_sample'],dtype='float32',always_2d=True)
            require(pcm_hash(x)==region['float32_pcm_sha256'],'Built continuous block differs from exact source/zero samples')
    return header_and_fingerprints(path,cursor)|{'verified_regions':regions,'verification':'All18canonical and2zero regions match exact float32 PCM hashes after writing'}


def validate_plans():
    refs={name:verify({'path':str(R/'device_enrollment'/name),'sha256':sha}) for name,sha in PLANS.items()}
    e=load(refs['DEVICE_ENROLLMENT_INPUT_PLAN_V1.json']['path']);long=load(refs['CONTINUOUS_INPUT_PLAN_V1.json']['path'])
    require(len(e['planned_passes'])==60 and len(e['people'])==30 and len(long['sessions'])==2,'Existing62 input scope changed')
    require(e['construction_recipe']['input_gain_candidate']==1. and e['construction_recipe']['tail_samples']==11367,'Existing unity/tail recipe changed')
    people={p['metadata_identity']:p for p in e['people']};utterances={u['source_id']:u for p in e['people'] for u in p['utterances']}
    require(len(utterances)==190,'Original190 unique E sources changed')
    material=load(verify(e['authorities']['material'])['path']);queries=load(verify(e['authorities']['queries'])['path'])
    material_rows={r['source_id']:r for r in material['accepted_sources']}
    chosen=[material_rows[s] for s in utterances]
    from s6d_enrollment_plan_v1 import audit_disjoint
    verify({'path':str(Path(__file__).with_name('s6d_enrollment_plan_v1.py')),'sha256':'ef4d7eea9534456b538705b2b1409c5dbcd27f2bb63ea58f0a2a9e9ec80fbcd4'})
    split_audit=audit_disjoint(chosen,material,queries)
    source_refs={}
    def admit(ref):
        got=verify(ref);source_refs[got['path']]=got;return got
    for p in people.values():
        admit(p['template_receipt'])
        for kind in ('metadata','vector'):admit(p['original_gallery_profile'][kind])
        for u in p['utterances']:
            s=material_rows[u['source_id']]
            require(s['s6c_role']=='E' and s['identity']==p['metadata_identity'] and u['role']=='E' and s['whole_clip'] and s['native_eligibility'],'E source/identity eligibility changed')
            require(u['source_gain_scalar']==s['source_gain_applied']==1. and u['transcript']==s['transcript'],'E gain/transcript changed')
            require(u['source_crop_samples']==[0,s['samples']] and u['decoded_audio_verified']['binding']==s['decoded_16k_binding'],'Whole E source binding changed')
            admit(u['source_binding']);admit(u['decoded_audio_verified']['binding'])
    for roster in e['rosters'].values():admit(roster['manifest'])
    require(Counter(p['metadata_identity'] for p in e['planned_passes'])=={k:2 for k in people},'Exactly two E positions per actual person required')
    positions={p['rir_id']:p for p in e['positions']}
    for p in positions.values():admit(p['audio_verified']['binding'])
    for p in e['planned_passes']:
        require(p['input_payload_binding'] is None and p['output_capture_binding'] is None,'Original plan is already populated; inspect instead of rebuild')
        require(p['profile']=='P_MAIN6' and p['role']=='enrollment' and p['sample_rate_hz']==RATE and p['rir_id'] in positions,'Enrollment route/clock changed')
        original=people[p['metadata_identity']]['utterances'];require([x['source_id'] for x in p['source_schedule']]==[x['source_id'] for x in original],'Template E ordering changed')
        cursor=0
        for i,row in enumerate(p['source_schedule']):
            u=original[i];frames=u['decoded_audio_verified']['frames']
            require(row['source_start_sample']==cursor and row['source_stop_sample']==cursor+frames and row['source_crop_samples']==[0,frames], 'E full clip/gap changed')
            require(row['input_gain_scalar']==1. and row['decoded_16k_binding']==u['decoded_audio_verified']['binding'],'E gain/binding changed')
            cursor+=frames+(8000 if i<len(original)-1 else 0)
        require(cursor+11367==p['source_frames'] and math.isclose(p['source_seconds'],p['source_frames']/RATE),'E common tail/frame duration changed')
    for session in long['sessions']:
        require(session['audio_payload_binding'] is None and session['capture_binding'] is None,'Continuous plan is already populated')
        for block in session['blocks']:
            if block['kind']=='original_canonical_four_mic_scene':admit(block['canonical_input_verified']['binding'])
        require(not {q['source_id'] for q in session['Q_evaluation_references']} & set(utterances),'Q enters E')
        require(all(q['role']=='Q_EVALUATION_ONLY_NOT_ENROLLMENT_OR_CALIBRATION' for q in session['Q_evaluation_references']),'Q role changed')
    return e,long,refs,source_refs,split_audit


def build(output,report):
    output=Path(output).resolve();report=Path(report).resolve()
    require(output.is_relative_to(PAYLOAD) and output!=PAYLOAD and report.is_relative_to(R),'Output must be fresh G run child; report small R child')
    require(not output.exists() and not report.exists(),'Fresh output/report required; preserve prior work')
    e,long,plan_refs,source_refs,split_audit=validate_plans()
    expected_frames=sum(p['source_frames'] for p in e['planned_passes'])+sum(s['source_frames'] for s in long['sessions'])
    projected_bytes=expected_frames*4*4+62*4096+8*1024*1024
    before=tree_bytes(PAYLOAD);disk={'C_free_bytes':shutil.disk_usage(R).free,'G_free_bytes':shutil.disk_usage(PAYLOAD).free,'observed_utc':utc()}
    require(before+projected_bytes<CAP,'Total40GiB payload cap would be exceeded')
    require(disk['C_free_bytes']>=2**30 and disk['G_free_bytes']>=75*2**30+projected_bytes,'File-only storage headroom inadequate')
    output.mkdir(parents=True);report.mkdir(parents=True);(output/'enrollment_inputs').mkdir();(output/'continuous_inputs').mkdir()
    save(output/'BUILD_STARTED.json',{'status':'FILE_ONLY_PREPARATION_STARTED','plans':plan_refs,'disk':disk,'global_payload_bytes_before':before,'projected_additional_bytes':projected_bytes,
        'physical_admission_unchanged':{'C_min_free_bytes':50*2**30,'G_min_free_bytes':75*2**30,'currently_met':disk['C_free_bytes']>=50*2**30},'models':0,'devices':0})
    rows=[]
    try:
        positions={p['rir_id']:p for p in e['positions']};rirs={rid:read_audio(p['audio_verified']['binding'],4,p['audio_verified']['frames'],p['audio_verified']['float32_pcm_sha256']) for rid,p in positions.items()}
        people={p['metadata_identity']:p for p in e['people']}
        for index,p in enumerate(e['planned_passes']):
            person=people[p['metadata_identity']];dry=np.zeros(p['source_frames']-p['common_rir_tail_samples'],dtype=np.float64)
            for u,row in zip(person['utterances'],p['source_schedule'],strict=True):
                verified=u['decoded_audio_verified'];x=read_audio(verified['binding'],1,verified['frames'],verified['float32_pcm_sha256'])[:,0]
                dry[row['source_start_sample']:row['source_stop_sample']]=x
            x=render_enrollment(dry,rirs[p['rir_id']],p['source_frames'])
            value=write_enrollment(output/'enrollment_inputs'/(p['planned_pass_id']+'.wav'),x)
            rows.append({'planned_id':p['planned_pass_id'],'kind':'enrollment_E','profile':p['profile'],'metadata_identity':p['metadata_identity'],'roster':p['roster'],
                'source_plan':plan_refs['DEVICE_ENROLLMENT_INPUT_PLAN_V1.json'],'source_schedule':p['source_schedule'],'rir':positions[p['rir_id']],
                'original_template':person['template_receipt'],'template_quality':person['original_template_quality_status'],
                'source_quality':[{'source_id':u['source_id'],'quality_disposition':u['quality_disposition'],'quality_review_flags':u['quality_review_flags']} for u in person['utterances']],
                'source_seconds':p['source_seconds'],'charged_playback_seconds':p['charged_playback_seconds'],'full_common_tail_samples':11367,**value})
            if (index+1)%10==0:print(json.dumps({'stage':'E_inputs_written_verified','complete':index+1,'total':60}),flush=True)
        for s in long['sessions']:
            value=write_continuous(output/'continuous_inputs'/(s['session_id']+'.wav'),s)
            rows.append({'planned_id':s['session_id'],'kind':'continuous_Q_evaluation_only','profile':s['profile'],'source_plan':plan_refs['CONTINUOUS_INPUT_PLAN_V1.json'],
                'receiver_configuration':s['receiver_configuration'],'source_seconds':900,'charged_playback_seconds':s['charged_playback_seconds'],
                'references_preserved_in_bound_original_plan':True,'Q_reference_count':len(s['Q_evaluation_references']),**value})
            print(json.dumps({'stage':'continuous_written_verified','id':s['session_id'],'frames':value['frames']}),flush=True)
        for ref in list(plan_refs.values())+list(source_refs.values()):verify(ref)
        after=tree_bytes(PAYLOAD);require(after<CAP,'Global payload cap exceeded; evidence retained')
        source_dir=report/'source_epoch';source_dir.mkdir()
        sources=[]
        for name in ('s6d_enrollment_inputs_build_v1.py','s6d_enrollment_inputs_build_checks_v1.py','README_S6D_ENROLLMENT_INPUTS_BUILD.md','s6d_enrollment_plan_v1.py'):
            original=Path(__file__).with_name(name);shutil.copy2(original,source_dir/name);sources.append({'original':binding(original),'snapshot':binding(source_dir/name)})
        adoption={'schema':'s6d-prepared-enrollment-continuous-adoption.v1','status':'ROOT_ADOPTION_REQUIRED_NOT_CAPTURE_AUTHORITY','original_plans':plan_refs,
            'entries':[{'planned_id':r['planned_id'],'kind':r['kind'],'profile':r['profile'],'source_audio':r['audio'],'frames':r['frames'],'duration_sec':r['source_seconds'],
                'charged_playback_seconds':r['charged_playback_seconds']} for r in rows],
            'rule':'Root must explicitly bind these62 files in later physical entries; original null plans/owner ledgers remain unchanged. Guards added only by unchanged capture owner.'}
        save(output/'ROOT_ADOPTION_MAP.json',adoption)
        result={'schema':'s6d-enrollment-continuous-input-build.v1','status':'PREPARED_FILES_ONLY_NOT_CAPTURED','created_utc':utc(),'original_plans':plan_refs,
            'inputs':rows,'source_bindings':list(source_refs.values()),'code_sources':sources,'split_audit':split_audit,'enrollment_file_count':60,'continuous_file_count':2,
            'unique_E_people':30,'unique_E_utterances':190,'all_output_frames':expected_frames,'source_seconds_total':expected_frames/RATE,
            'output_WAV_bytes':sum(r['audio']['bytes'] for r in rows),'global_payload_bytes_before':before,'global_payload_bytes_after_WAVs':after,'global_payload_cap_bytes':CAP,
            'root_adoption_map':binding(output/'ROOT_ADOPTION_MAP.json'),'disk_before':disk,'hardware_floor_unchanged':{'C_GiB':50,'G_GiB':75},
            'runtime_state':{'models_run':0,'devices_opened':0,'playbacks':0,'policy_evaluations':0,'physical_ledger_created':False},
            'limitations':['Input construction and numeric headroom only; no physical route/tail/clock acceptance.','All original E REVIEW/template flags preserved.','Continuous Q never enters enrollment/calibration.',
                'Original profile/gallery bytes and exact62-plan schedules unchanged.','New physical entry source bindings still require root adoption and all existing runner/capture/experiment floors.']}
        save(output/'PREPARATION_RESULT.json',result);save(report/'RESULT_BINDING.json',{'result':binding(output/'PREPARATION_RESULT.json'),'adoption':binding(output/'ROOT_ADOPTION_MAP.json'),'source_epoch':sources})
        print(json.dumps({'status':result['status'],'result':binding(output/'PREPARATION_RESULT.json'),'WAV_files':62,'WAV_bytes':result['output_WAV_bytes'],'global_payload_bytes':tree_bytes(PAYLOAD),'physical_entry_adoption_required':True}),flush=True)
        return result
    except Exception as exc:
        save(output/'BUILD_FAILED.json',{'status':'FAILED_PREPARATION_EVIDENCE_RETAINED','error':str(exc),'completed_inputs':rows,'models':0,'devices':0})
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();build(a.output,a.report)
