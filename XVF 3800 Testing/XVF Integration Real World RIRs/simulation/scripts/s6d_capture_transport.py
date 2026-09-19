"""Pure S6D packed transport/profile helpers; README_S6D_CAPTURE.md."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import numpy as np

PROFILES = {
    'P_MAIN6': [('auto_asr_raw',7,3),('auto_pp_raw',6,3),('focus0_asr_raw',7,0),('focus1_asr_raw',7,1),('focus0_pp_raw',6,0),('focus1_pp_raw',6,1)],
    'P_SCAN6': [('auto_asr_raw',7,3),('auto_pp_raw',6,3),('focus0_asr_raw',7,0),('focus1_asr_raw',7,1),('scan_asr_raw',7,2),('scan_pp_raw',6,2)],
    'P_INPUT_QA6': [('auto_asr_raw',7,3),('auto_pp_raw',6,3),('dsp_input_mic0',3,0),('dsp_input_mic1',3,1),('dsp_input_mic2',3,2),('dsp_input_mic3',3,3)],
}
API_FROM_DECODED = (0,2,4,1,3,5)
TRANSPORT_PRE_ROLL_SEC = 1.
TRANSPORT_POST_ROLL_SEC = 3.
MAX_CALLBACK_FRAMES = 16384


def timing(source_seconds):
    value=float(source_seconds)
    if not math.isfinite(value) or not 0<value<=900:raise ValueError('Source duration must be finite, positive and at most 900 seconds')
    if abs(value*16000-round(value*16000))>1e-7:raise ValueError('Whole 16 kHz source frames required')
    native_frames=round((value+TRANSPORT_PRE_ROLL_SEC+TRANSPORT_POST_ROLL_SEC)*48000)
    return dict(source_seconds=value,pre_roll_seconds=TRANSPORT_PRE_ROLL_SEC,post_roll_seconds=TRANSPORT_POST_ROLL_SEC,
        source_start_logical_frame=16000,source_frames=round(value*16000),native_carrier_frames=native_frames,
        carrier_seconds=native_frames/48000,maximum_terminal_padding_frames=MAX_CALLBACK_FRAMES-1,
        charged_playback_seconds=(native_frames+MAX_CALLBACK_FRAMES-1)/48000,
        source_sample_clock_hz=16000,source_origin_preserved=True)


def guarded_input(microphones):
    q=quantize(microphones)
    return np.pad(q,((round(TRANSPORT_PRE_ROLL_SEC*16000),round(TRANSPORT_POST_ROLL_SEC*16000)),(0,0))),q


def terminal_packed_silence(first_native_frame,frames):
    result=np.zeros((frames,2),np.int32)
    result[(np.arange(frames)+first_native_frame)%3!=0,:]=1
    return pcm24_bytes(result)


def binding(path):
    p=Path(path).resolve();before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    after=p.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Changed while hashing')
    return dict(path=str(p),bytes=after.st_size,sha256=h.hexdigest())


def verify(b):
    a=binding(b['path'])
    if a['sha256']!=b['sha256'] or ('bytes' in b and a['bytes']!=b['bytes']):raise ValueError('Input bytes differ: '+a['path'])
    return a


def mux_arguments(profile):
    channels=PROFILES[profile]
    return [v for i in API_FROM_DECODED for v in channels[i][1:]]


def quantize(microphones):
    x=np.asarray(microphones,dtype=np.float64)
    if x.ndim!=2 or x.shape[1]!=4 or not np.isfinite(x).all():raise ValueError('Finite four-microphone input required')
    if np.any(np.abs(x)>=1.):raise ValueError('Input exceeds packed microphone full scale')
    q=np.rint(np.column_stack((np.zeros((len(x),2)),x))*2**22).astype(np.int64)*2
    if np.any(np.abs(q)>=2**23):raise ValueError('Packed microphone payload clipping')
    return q.astype(np.int32)


def pack(q):
    if q.ndim!=2 or q.shape[1]!=6 or np.any(q&1):raise ValueError('Six even-count logical inputs required')
    data=q.reshape(-1,2).copy();data[1::3]|=1;data[2::3]|=1
    return data


def pcm24_bytes(counts):
    q=np.asarray(counts,dtype=np.int32)
    if np.any(q>=2**23) or np.any(q<-(2**23)):raise ValueError('PCM24 range exceeded')
    unsigned=q.reshape(-1).view(np.uint32)
    b=np.empty((len(unsigned),3),np.uint8)
    b[:,0]=unsigned&255;b[:,1]=(unsigned>>8)&255;b[:,2]=(unsigned>>16)&255
    return b.tobytes()


def unpack_pcm24(data):
    if len(data)%6:raise ValueError('Whole stereo PCM24 frames required')
    b=np.frombuffer(data,np.uint8).reshape(-1,3).astype(np.int32)
    q=b[:,0]|(b[:,1]<<8)|(b[:,2]<<16);q=np.where(q&0x800000,q-0x1000000,q).astype(np.int32)
    return q.reshape(-1,2)


def input_qa(decoded,expected):
    """P_INPUT_QA6 has MIC0..3 at output columns2..5, not old columns0..3."""
    x=np.asarray(expected)[:,2:6];y=np.asarray(decoded)[:,2:6]
    if not np.any(x):
        mismatches=int(np.count_nonzero(y))
        return dict(status='PASS' if not mismatches else 'FAIL',payload_mismatches=mismatches,
            capture_minus_source_offset_samples=None,alignment_status='UNIDENTIFIABLE_ALL_ZERO_INPUT',
            compared_mic_samples=int(y.size),exact_mic_recovery_claim=True)
    if len(x)<64 or len(y)<64:raise ValueError('At least64 frames required for exact input QA')
    anchor=min(int(np.argmax(np.abs(x[:,0]))),len(x)-64)
    offsets=[int(i)-anchor for i in np.flatnonzero(y[:,0]==x[anchor,0]) if i+64<=len(y) and np.array_equal(y[i:i+64],x[anchor:anchor+64])]
    if len(offsets)!=1:return dict(status='FAIL',reason='No unique common four-microphone exact anchor',matching_offsets=offsets[:20],exact_mic_recovery_claim=False)
    offset=offsets[0];a=max(0,offset);b=min(len(y),len(x)+offset)
    xx=x[a-offset:b-offset];yy=y[a:b];nonzero=np.flatnonzero(np.any(x!=0,axis=1))
    complete=a-offset<=nonzero[0] and b-offset>nonzero[-1]
    mismatches=xx!=yy
    return dict(status='PASS' if not mismatches.any() and complete else 'FAIL',capture_minus_source_offset_samples=offset,
        compared_mic_samples=int(xx.size),payload_mismatches=int(mismatches.sum()),
        per_mic_mismatches=mismatches.sum(axis=0).tolist(),all_nonzero_source_payload_captured=bool(complete),
        exact_mic_recovery_claim=bool(not mismatches.any() and complete),
        scope='One common sample offset, no independent microphone alignment or gain fitting; applies to this QA pass only')


def processed_qc(decoded,profile):
    if decoded.ndim!=2 or decoded.shape[1]!=6:raise ValueError('Six decoded channels required')
    rows=[]
    for i,(name,cat,source) in enumerate(PROFILES[profile]):
        x=decoded[:,i].astype(np.int64)
        rows.append(dict(name=name,index=i,category=cat,source=source,frames=len(x),sample_rate=16000,
            raw_gain=1.,peak_counts=int(np.max(np.abs(x))) if len(x) else None,
            nonzero_samples=int(np.count_nonzero(x)),
            rail_samples=int(np.count_nonzero((x<=-8388608)|(x>=8388606))),
            rms_counts=float(np.sqrt(np.mean(x.astype(float)**2))) if len(x) else None))
    return dict(status='DESCRIPTIVE_OUTPUT_QC',streams=rows,exact_mic_recovery_claim=False,
        channels_equal=[[i,j] for i in range(6) for j in range(i+1,6) if np.array_equal(decoded[:,i],decoded[:,j])],
        equality_interpretation='Equal processed beams can be genuine; identity must be physically qualified with controls, not inferred from inequality')


def audio_gate(qc,policy,required_nonzero):
    if policy.get('schema')!='s6d-audio-acceptance.v1' or policy.get('raw_gain')!=1. or policy.get('max_rail_samples_per_stream')!=0 or policy.get('rail_exceedance_action')!='LIMITED' or policy.get('missing_required_payload_action')!='LIMITED':
        raise ValueError('Bound raw-unity, zero-rail eligibility threshold with LIMITED evidence retention required')
    names={r['name'] for r in qc['streams']}
    if not set(required_nonzero)<=names:raise ValueError('Required nonzero stream absent from this profile')
    failures=[];rows=[]
    for row in qc['streams']:
        rail_pass=row['rail_samples']==0
        nonzero_pass=row['name'] not in required_nonzero or row['nonzero_samples']>0
        usable=rail_pass and nonzero_pass and row['frames']>0
        if not usable:failures.append(row['name'])
        rows.append(dict(name=row['name'],rail_pass=rail_pass,required_nonzero=row['name'] in required_nonzero,
            nonzero_pass=nonzero_pass,status='PASS_LEVEL_SCREEN' if usable else 'LIMITED',eligible_for_unqualified_level_claim=usable))
    return dict(status='PASS_LEVEL_SCREEN' if not failures else 'LIMITED',per_stream=rows,limited_streams=failures,
        gain_changed=False,original_waveforms_retained=True,
        policy_scope='Per-stream rail/payload eligibility screen only; physical route identity, gain calibration and tail delay require separate qualification')


def checks():
    tests={}
    tests['main_mux_order']=mux_arguments('P_MAIN6')==[7,3,7,0,6,0,6,3,7,1,6,1]
    tests['qa_mux_order']=mux_arguments('P_INPUT_QA6')==[7,3,3,0,3,2,6,3,3,1,3,3]
    rng=np.random.default_rng(380062)
    x=rng.uniform(-.05,.05,(4096,4));q=quantize(x);packed=pack(q)
    tests['signed_pcm24_exact']=np.array_equal(unpack_pcm24(pcm24_bytes(packed)),packed)
    tests['markers_and_logical_order']=np.array_equal((packed&~1).reshape(-1,6),q)
    tests['zero_far_end_ignored']=not np.any(q[:,:2])
    # Auto channels deliberately nonzero: confusing QA's0..3 with2..5 must fail.
    decoded=np.column_stack((np.full((len(q),2),876,np.int32),q[:,2:6]))
    tests['qa_columns2_to5_exact']=input_qa(decoded,q)['status']=='PASS'
    for name,data in [('mic_swap',decoded[:,[0,1,3,2,4,5]]),('mic_duplicate',decoded[:,[0,1,2,2,4,5]]),
                      ('source_drop',np.delete(decoded,1000,axis=0)),('source_repeat',np.insert(decoded,1000,decoded[1000],axis=0))]:
        tests[name+'_rejected']=input_qa(data,q)['status']=='FAIL'
    tests['zero_control_no_alignment']=input_qa(np.zeros((500,6),np.int32),np.zeros((500,6),np.int32))['capture_minus_source_offset_samples'] is None
    tests['processed_beam_duplicates_descriptive']=processed_qc(np.zeros((100,6),np.int32),'P_MAIN6')['status']=='DESCRIPTIVE_OUTPUT_QC'
    tests['main_never_claims_microphone_echo']=not processed_qc(decoded,'P_MAIN6')['exact_mic_recovery_claim']
    assert all(tests.values()),tests
    return dict(status='PASS_MODEL_FREE',checks=tests,hardware_calls=0,audio_streams_opened=0)


if __name__=='__main__':print(json.dumps(checks(),indent=2))
