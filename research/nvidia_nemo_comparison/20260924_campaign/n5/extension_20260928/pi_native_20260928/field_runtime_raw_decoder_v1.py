"""Strict XVF3800 48kHz S32LE packing decoder; README_RUNTIME_RAW_DECODER_V1.md."""
import array
import struct
import sys

CHANNELS=('auto_asr','processed_auto_select','physical_mic0','physical_mic1','physical_mic2','physical_mic3')

def decode(raw):
    """Return exact 16kHz channels after rejecting every corrupt packing marker."""
    if type(raw) is not bytes or not 24<=len(raw)<=33554432 or len(raw)%8:
        raise ValueError('Finite stereo S32LE input required')
    samples=array.array('i')
    if samples.itemsize!=4:raise RuntimeError('32-bit integer decoder required')
    samples.frombytes(raw)
    if sys.byteorder!='little':samples.byteswap()
    count=len(samples)//2
    starts=[]
    for i in range(3):
        left=samples[2*i]&1;right=samples[2*i+1]&1
        if left!=right:raise ValueError('Left/right packing marker mismatch')
        if left==0:starts.append(i)
    if len(starts)!=1:raise ValueError('Exactly one frame-start marker per triple')
    start=starts[0]
    for i in range(count):
        expected=0 if (i-start)%3==0 else 1
        if samples[2*i]&1!=expected or samples[2*i+1]&1!=expected:
            raise ValueError('Packing marker discontinuity at transport frame '+str(i))
    frames=(count-start)//3
    if frames<1:raise ValueError('No complete six-channel frame')
    packed=array.array('i')
    for i in range(start,start+frames*3,3):
        packed.extend(samples[2*i+j]&~1 for j in range(6))
    if sys.byteorder!='little':packed.byteswap()
    six=packed.tobytes()
    return dict(rate=16000,frames=frames,channels=list(CHANNELS),pcm_s32le=six,
                discarded_prefix_transport_frames=start,
                discarded_suffix_transport_frames=count-start-frames*3,
                marker_bit=0,marker_errors=0,
                raw_tap='MUX_RAW_MICS[1], physical MIC0..3 before gain/delay',
                transport_rate=48000,transport_channels=2,
                shared_clock=True,acoustic_latency_equal_claim=False,
                original_adc_bit_exact_claim=False)

def channel_bytes(decoded,indices):
    if type(indices) is not tuple or not indices or len(set(indices))!=len(indices) or any(type(i) is not int or not 0<=i<6 for i in indices):
        raise ValueError('Unique channel indices')
    raw=decoded['pcm_s32le'];out=bytearray()
    if len(raw)!=decoded['frames']*24:raise ValueError('Exact decoded frame bytes')
    for n in range(decoded['frames']):
        for i in indices:out.extend(raw[n*24+i*4:n*24+i*4+4])
    return bytes(out)
