"""Render only the fixed S3 development fixtures; no hardware access."""
import argparse, importlib.util, json, shutil, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve
import pyarrow.parquet as pq
from s0_common import ROOT, SIM, REPO, HashCache, save, now

FS=16000

def quantize(x,bits):
    # Round directly to the available (bits-1)-bit payload grid, exactly once.
    q=np.rint(np.asarray(x,dtype=np.float64)*2**(bits-2)).astype(np.int32)*2
    if np.max(np.abs(q.astype(np.int64)))>=2**(bits-1):raise ValueError('Payload clipping')
    return q

def pack(q):
    if q.ndim!=2 or q.shape[1]!=6 or np.any(q&1):raise ValueError('Six even-count payload channels required')
    raw=q.reshape(-1,2).copy();raw[1::3]|=1;raw[2::3]|=1
    return raw

def write_counts(path,q,rate,bits):
    sf.write(str(path),q.astype(np.int32)<<8 if bits==24 else q.astype(np.int16),rate,subtype=f'PCM_{bits}')

def run(report):
    report=Path(report);target=report/'inputs';target.mkdir(exist_ok=False)
    cache=HashCache();ctx=json.loads((ROOT/'Just_Peachy_S3_Codex_Pack/S3_INPUT_CONTEXT.json').read_text())
    manifest=cache.bind(SIM/'rir_library/v1/RIR_MANIFEST.json',ctx['rir_library']['manifest_sha256'])
    rirs={};bindings=[]
    for r in ctx['selected_rirs']:
        if r['role']=='rear_optional':continue
        assert r['can_proceed_to_hil_proof'] and r['run_id'] not in ctx['rir_library']['spatially_deferred_ids']
        assert 0<r['geometry']['source_distance_m_effective']<=5
        b=cache.bind(Path(r['output']['path']),r['output']['sha256']);h,fs=sf.read(b['path'],always_2d=True,dtype='float64')
        assert fs==FS and h.shape[1]==4 and np.isfinite(h).all()
        rirs[r['role']]=h;bindings.append({'role':r['role'],'run_id':r['run_id'],'geometry':r['geometry'],'file':b,'time_origin':r['time_origin']})
    metadata=REPO/'Software Validation from Datasets/Normalized Metadata/LibriSpeech'
    ids=['1272-128104-0000','1272-128104-0003','1462-170138-0006']
    df=pq.read_table(metadata/'recordings.parquet',filters=[('split','=','dev-clean')]).to_pandas()
    selected=[];dry={}
    for label,id_ in zip(['A1','A2','B1'],ids):
        row=df[df.audio_path.str.endswith(id_+'.flac')].iloc[0]
        p=Path(row.audio_path);x,fs=sf.read(p,dtype='float64')
        assert fs==FS and x.ndim==1 and 5<=len(x)/FS<=10 and np.isfinite(x).all()
        transcript_path=Path(row.raw_transcript_path)
        matches=[l for l in transcript_path.read_text().splitlines() if l.startswith(id_+' ')]
        assert len(matches)==1
        selected.append({'label':label,'utterance_id':id_,'speaker_key':'LibriSpeech:'+str(row.speaker_id),'split':row.split,
            'duration_s':len(x)/FS,'source':cache.bind(p),'transcript_source':cache.bind(transcript_path),
            'transcript':matches[0].split(' ',1)[1],'word_times':None,'word_times_null_reason':'Only utterance transcript available; no forced alignment performed'})
        dry[label]=x
    assert selected[0]['speaker_key']==selected[1]['speaker_key']!=selected[2]['speaker_key']
    license_path=Path(selected[0]['source']['path']).parents[3]/'LICENSE.TXT'
    assert 'Creative Commons Attribution 4.0' in license_path.read_text()
    policy={'nominal_dry_drive_scalar':0.25,'nominal_dry_drive_gain_db':20*np.log10(.25),
       'source_level_rule':'Original clean PCM samples times a fixed 0.25 numerical post-software-gain drive scalar. No loudness normalization.',
       'headroom_rule':'If necessary apply one additional attenuation scalar to ALL speech cases/mics, targeting peak <=0.25 FS. Never boost.',
       'included_RIR_gain_delay':'Category3 acquisition gain10/SYS_DELAY-32 remain in RIR; no second -6dB or gain/delay compensation',
       'far_end':'zero for every sample','ignored_channel':'zero for every sample','pre_onset_s':.05,
       'propagation_delay_added_s':0,'per_channel_alignment_or_normalization':False}
    convolved={(u,r):np.column_stack([fftconvolve(x*.25,h[:,j]) for j in range(4)]) for u,x in dry.items() for r,h in rirs.items()}
    common=min(1.,.25/max(np.max(np.abs(y)) for y in convolved.values()));policy['common_headroom_scalar']=common
    definitions=[('T1_tagged',8.,[]),*[(f'T2_{r}',13.,[('A1',r,3.)]) for r in ['front','left','right']],
                 ('T3_ABA',38.,[('A1','left',3.),('B1','right',12.),('A2','left',24.)])]
    cases=[]
    for cid,seconds,turns in definitions:
        vector=np.zeros((round(seconds*FS),6),np.float64);segments=[]
        if cid=='T1_tagged':
            # Channel-distinct deterministic wideband transport tags, low peak level.
            for j in range(4):vector[2*FS:6*FS,j+2]=np.random.default_rng(3800300+j).uniform(-.03125,.03125,4*FS)
            segments=[{'kind':'tagged_noise','source_start_sample':2*FS,'source_stop_sample':6*FS}]
        else:
            for utterance,role,start_s in turns:
                y=convolved[utterance,role]*common;at=round(start_s*FS)
                vector[at:at+len(y),2:]+=y
                source=next(s for s in selected if s['label']==utterance)
                segments.append({'kind':'utterance','utterance_label':utterance,'speaker_key':source['speaker_key'],'rir_role':role,
                    'source_start_sample':at,'source_stop_sample':at+len(dry[utterance]),'rir_expected_significant_onset_sample':at+800,
                    'convolution_stop_sample':at+len(y),'transcript':source['transcript'],
                    'timing_scope':'Exact source-file scheduling and full RIR support; file boundaries are not exact phonetic onsets'})
        np.save(target/(cid+'_float64.npy'),vector)
        formats={}
        for bits in [24,16]:
            q=quantize(vector,bits);raw=pack(q)
            np.save(target/(cid+f'_expected{bits}.npy'),q)
            p=target/(cid+f'_packed{bits}.wav');write_counts(p,raw,48000,bits)
            error=np.abs(q/2**(bits-1)-vector)
            formats[str(bits)]={'packed':cache.bind(p),'expected':cache.bind(target/(cid+f'_expected{bits}.npy')),
                'payload_bits':bits-1,'quantization_max_abs_fs':float(error.max()),'quantization_rms_fs':float(np.sqrt(np.mean(error**2))),
                'quantization_step_fs':2.**(2-bits),'zero_far_end_and_ignored':bool(np.all(q[:,:2]==0))}
        cases.append({'case_id':cid,'duration_s':seconds,'float_vector':cache.bind(target/(cid+'_float64.npy')),
                      'segments':segments,'formats':formats,'peak_fs':float(np.max(np.abs(vector)))})
    # Compare implementation to the local official packer, including channel order.
    vendor=ROOT/'tools/xvf321/source/sources/modules/fwk_xvf/modules/tuning/tuning/packing.py'
    spec=importlib.util.spec_from_file_location('vendor_packing',vendor);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    checks=[]
    for bits in [16,24]:
        q=quantize(np.random.default_rng(321).uniform(-.3,.3,(321,6)),bits)
        source=target/f'offline_six_{bits}.wav';dest=target/f'official_packed_{bits}.wav';write_counts(source,q,16000,bits)
        mod.pack(source,dest,output_bitres=bits)
        official,_=sf.read(dest,dtype='int32');official=official>>(32-bits)
        expected=pack(q)
        checks.append({'check':f'official_pack_equivalence_{bits}','passed':bool(np.array_equal(official,expected)),'compared_transport_samples':int(expected.size)})
        decoded=expected.reshape(-1,6)&np.int32(-2)
        checks.append({'check':f'payload_channel_order_{bits}','passed':bool(np.array_equal(decoded,q)),'compared_payload_samples':int(q.size)})
        checks.append({'check':f'negative_control_dropped_group_{bits}','passed':not np.array_equal(np.delete(decoded,100,axis=0),q[:320])})
        checks.append({'check':f'negative_control_duplicated_group_{bits}','passed':not np.array_equal(np.insert(decoded,100,decoded[100],axis=0)[:321],q)})
    assert all(c['passed'] for c in checks)
    metrics={'schema_version':'jp_s3_inputs_v1','created_utc':now(),'rir_manifest':manifest,'selected_rirs':bindings,
       'speech_fixtures':selected,'reserved_development_speaker_keys':sorted(set(s['speaker_key'] for s in selected)),
       'reserved_policy':'These identities and utterances are development fixtures; exclude from any later untouched evaluation split.',
       'rights':{'license':cache.bind(license_path),'statement':license_path.read_text(),'attribution':'LibriSpeech (Panayotov et al.), based on LibriVox recordings; CC BY 4.0. Audio remains local; derived S3 fixtures only.',
                'source_url':'https://www.openslr.org/12/','alterations':'Numerical gain, measured-room convolution, silence scheduling and transport quantization as documented.'},
       'source_level_policy':policy,'cases':cases,'planned_physical_attempts':['T1_tagged','T2_front','T2_left','T2_right','T3_ABA_repeat1','T3_ABA_repeat2'],
       'planned_playback_s':8+3*13+2*38,'retry_budget':1,'physical_playback_ceiling_s':900,
       'predeclared_transport_tolerances':{'payload_mismatches':0,'marker_errors_after_startup':0,'common_integer_offset_only':True,
           'per_mic_level_error_counts':0,'missing_duplicate_payload_samples':0,'pairwise_input_delay_change_samples':0,
           'scope':'Compare captured Category3 to quantized expected payload. Startup/trailing partial packed groups separately counted.'},
       'offline_checks':checks,'vendor_packer':cache.bind(vendor),
       'resources':{d:{'free_bytes':shutil.disk_usage(d+':/').free,'free_gib':shutil.disk_usage(d+':/').free/2**30} for d in ['C','D','F','G']}}
    assert metrics['resources']['C']['free_gib']>=50
    save(report/'inputs_manifest.json',metrics);cache.flush()
    print(json.dumps({'cases':len(cases),'playback_s':metrics['planned_playback_s'],'checks_passed':len(checks),'policy':policy,'resources':metrics['resources']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);a=p.parse_args();run(a.report)
