"""Exact S4 carrier preparation/integrity checks; no hardware access. README_S45.md."""
import argparse, hashlib, sys
from s45_common import *
sys.path.insert(0,str(ROOT))
import measurement_app
import numpy as np
import soundfile as sf
def quantize(x,bits):
    q=np.rint(np.asarray(x,dtype=np.float64)*2**(bits-2)).astype(np.int32)*2
    if np.max(np.abs(q.astype(np.int64)))>=2**(bits-1):raise ValueError('Payload clipping')
    return q

def pack(q):
    if q.ndim!=2 or q.shape[1]!=6 or np.any(q&1):raise ValueError('Six even-count payload channels required')
    raw=q.reshape(-1,2).copy();raw[1::3]|=1;raw[2::3]|=1
    return raw

def write_counts(path,q,rate,bits):
    sf.write(str(path),q.astype(np.int32)<<8 if bits==24 else q.astype(np.int16),rate,subtype=f'PCM_{bits}')

def prepare(scene):
    path=Path(scene['canonical_audio']['path']);bind(path,scene['canonical_audio']['sha256'])
    x,fs=sf.read(path,dtype='float64',always_2d=True)
    assert fs==16000 and x.shape[1]==4 and np.isfinite(x).all()
    q=quantize(np.column_stack([np.zeros((len(x),2)),x]),24)
    directory=PAYLOAD/'packed';directory.mkdir(parents=True,exist_ok=True)
    packed_path=directory/(scene['case_id']+'_packed24.wav');expected_path=directory/(scene['case_id']+'_expected24.npy')
    if not packed_path.exists():write_counts(packed_path,pack(q),48000,24)
    if not expected_path.exists():np.save(expected_path,q)
    counts,srate=sf.read(packed_path,dtype='int32',always_2d=True)
    assert srate==48000 and np.array_equal(counts>>8,pack(q))
    assert np.array_equal(np.load(expected_path),q)
    return {'packed':bind(packed_path),'expected':bind(expected_path),'quantization_step_fs':2**-22,
            'quantization_max_abs_fs':float(np.max(np.abs(q[:,2:]/2**23-x))),
            'zero_far_end_and_ignored':bool(np.all(q[:,:2]==0))}

def payload_check(decoded,expected):
    # Silence cannot provide a unique alignment anchor. It still must have four
    # exactly zero diagnostic channels throughout; source offset stays unknown.
    if not np.any(expected[:,2:]):
        ok=not np.any(decoded[:,:4])
        return {'status':'PASS' if ok else 'FAIL','capture_minus_source_offset_samples':None,
                'alignment_status':'UNIDENTIFIABLE_ALL_ZERO_INPUT','compared_mic_samples':int(decoded[:,:4].size),
                'payload_mismatches':int(np.count_nonzero(decoded[:,:4])),
                'all_nonzero_source_payload_captured':None,'scope':'Exact zero diagnostic channels; no unique silent sample correspondence claimed'}
    # Importing the owner module loads recorder dependencies but makes no control call.
    from s3_hardware import payload_check as historical_check
    return historical_check(decoded,expected)

def carrier_chunk(payload,position,frames,total_frames,width=3):
    take=min(frames,max(0,total_frames-position));size=frames*2*width
    offset=position*2*width;data=payload[offset:offset+take*2*width]
    if len(data)!=take*2*width:raise ValueError('Truncated carrier: partial payload write forbidden')
    return data+bytes(size-len(data)),take

def tests():
    from s3_hardware import payload_check as old_check
    from measurement_app.core import decode_packed,pack_pcm24,unpack_pcm24
    rng=np.random.default_rng(3800401)
    q=quantize(np.column_stack([np.zeros((5000,2)),rng.uniform(-.02,.02,(5000,4))]),24)
    decoded=np.column_stack([q[:,2:],np.zeros((len(q),2),np.int32)])
    check={}
    check['exact_four_mic_payload']=old_check(decoded,q)['status']=='PASS'
    for name,corrupt in [('swap',decoded[:,[1,0,2,3,4,5]]),('drop',np.delete(decoded,2500,axis=0)),('duplicate',np.insert(decoded,2500,decoded[2500],axis=0))]:check[name+'_rejected']=old_check(corrupt,q)['status']=='FAIL'
    stale=decoded.copy();stale[2500:2600]=stale[2400:2500];check['stale_buffer_rejected']=old_check(stale,q)['status']=='FAIL'
    corrupt=decoded.copy();corrupt[2500,0]+=2;check['single_count_error_rejected']=old_check(corrupt,q)['status']=='FAIL'
    carrier=pack(q);b=pack_pcm24(carrier);parts=[];pos=0
    for frames in [17,511,73,3300,12000]:
        chunk,take=carrier_chunk(b,pos,frames,len(carrier));parts.append(chunk[:take*6]);pos+=take
        check['terminal_padding_zero']=not any(chunk[take*6:])
        if pos==len(carrier):break
    check['arbitrary_callback_partitions_exact']=b''.join(parts)==b
    try:carrier_chunk(b[:-1],0,len(carrier),len(carrier));check['truncated_write_rejected']=False
    except ValueError:check['truncated_write_rejected']=True
    check['signed24_bytes_roundtrip']=np.array_equal(unpack_pcm24(b),carrier)
    parsed,framing=decode_packed(carrier,24)
    check['vendor_frame_order']=np.array_equal(parsed,q) and framing['marker_error_count']==0
    silent=payload_check(np.zeros((5000,6),np.int32),np.zeros((5000,6),np.int32))
    check['silent_alignment_not_invented']=silent['status']=='PASS' and silent['capture_minus_source_offset_samples'] is None
    result={'status':'PASS' if all(check.values()) else 'FAIL','checks':check,'passed':sum(check.values()),'total':len(check),'hardware_calls':0}
    save(REPORT/'transport_regressions.json',result);print(json.dumps(result,indent=2));assert all(check.values())

if __name__=='__main__':tests()
