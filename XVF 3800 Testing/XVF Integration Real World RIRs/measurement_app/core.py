from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, subprocess, threading, time, re, os, uuid
import numpy as np
import sounddevice as sd
import soundfile as sf
from . import BASE

HOST = BASE/'tools/xvf321/binary/host_v3.0.0/win32/xvf_host.exe'
RUNS = BASE/'XVF_MEASUREMENT_WORK/experiments'
CREATE_NO_WINDOW = getattr(subprocess,'CREATE_NO_WINDOW',0)

def now(): return datetime.now(timezone.utc).isoformat()
def sha(path):
    """Hash once opened; retry only transient permission failures acquiring it."""
    h=hashlib.sha256()
    for attempt in range(7):
        try:
            handle=Path(path).open('rb')
            break
        except PermissionError:
            if attempt==6:raise
            time.sleep(min(.025*2**attempt,.4))
    with handle as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
def clean_json(x):
    if isinstance(x,np.ndarray): return clean_json(x.tolist())
    if isinstance(x,dict): return {str(k):clean_json(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [clean_json(v) for v in x]
    if isinstance(x,np.generic):return clean_json(x.item())
    if isinstance(x,float) and not np.isfinite(x): return None
    return x
def write_json(p,x):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(clean_json(x),f,indent=2,allow_nan=False);f.write('\n')

def append_command_receipt(path,row):
    """Retry opening a temporarily locked log, never the device command.

    Windows sync/indexing software can briefly deny an append open. Once a
    handle is obtained, a write failure is surfaced rather than retried, since
    an unknown partial write must not be duplicated.
    """
    for attempt in range(7):
        try:
            handle=Path(path).open('a',encoding='utf-8')
            break
        except PermissionError:
            if attempt==6:raise
            time.sleep(min(.025*2**attempt,.4))
    with handle:handle.write(json.dumps(row)+'\n')

class Control:
    def __init__(self,folder):
        self.folder=Path(folder); self.folder.mkdir(parents=True,exist_ok=True);self.seq=0
    def query(self,name,*args):
        self.seq+=1; argv=[str(HOST),'-u','usb',name,*map(str,args)]
        start=time.perf_counter_ns();utc=now()
        try:
            p=subprocess.run(argv,cwd=HOST.parent,capture_output=True,timeout=12,creationflags=CREATE_NO_WINDOW)
            out,err,code=p.stdout,p.stderr,p.returncode; failure=None
        except subprocess.TimeoutExpired as e:out,err,code,failure=e.stdout or b'',e.stderr or b'',None,'timeout'
        row={'sequence':self.seq,'command':name,'arguments':list(args),'argv':argv,'start_utc':utc,
             'start_monotonic_ns':start,'end_monotonic_ns':time.perf_counter_ns(),'exit_code':code,'failure':failure,
             'stdout':out.decode('utf-8-sig',errors='replace'),'stderr':err.decode('utf-8-sig',errors='replace')}
        tag=f'{self.seq:04d}_{name}'
        (self.folder/(tag+'.stdout.bin')).write_bytes(out);(self.folder/(tag+'.stderr.bin')).write_bytes(err)
        append_command_receipt(self.folder/'commands.jsonl',row)
        if code!=0 or failure or row['stderr'].strip():raise RuntimeError(f'{name}: {failure or row["stderr"] or row["stdout"]}')
        return row['stdout']
    def values(self,name):
        text=self.query(name); lines=[l for l in text.splitlines() if l.startswith(name+' ')]
        if len(lines)!=1: raise RuntimeError('Missing or ambiguous reply: '+name)
        vals=[]
        for v in lines[0].split()[1:]:
            enum=re.search(r'\[(\d+)\]',v)
            if enum:vals.append(int(enum[1]))
            else:
                try:vals.append(int(v))
                except ValueError:vals.append(float(v))
        return vals
    def set(self,name,values):
        self.query(name,*values)
        actual=self.values(name)
        if actual!=list(values):raise RuntimeError(f'{name} readback {actual} != {values}')
    def identify(self):
        d={n:self.values(n) for n in ['VERSION','AEC_MIC_ARRAY_TYPE','AEC_NUM_MICS','AEC_MIC_ARRAY_GEO',
              'AUDIO_MGR_MIC_GAIN','AUDIO_MGR_REF_GAIN','AUDIO_MGR_SYS_DELAY','USB_BIT_DEPTH','I2S_INPUT_PACKED','I2S_DAC_DSP_ENABLE']}
        d['build_reply']=self.query('BLD_MSG')
        if d['VERSION']!=[3,2,1] or d['AEC_MIC_ARRAY_TYPE']!=[1] or d['AEC_NUM_MICS']!=[4] or 'ua-io48-lin' not in d['build_reply']:
            raise RuntimeError('Expected verified 3.2.1 ua-io48-lin / four-microphone linear firmware')
        if d['I2S_INPUT_PACKED']!=[0]:raise RuntimeError('Physical microphone mode required; packed injection is enabled')
        if d['I2S_DAC_DSP_ENABLE']!=[0]:raise RuntimeError('Default left-reference DAC routing required for the isolated right-channel continuity signal')
        return d

AUDIO_BACKEND_LOCK = threading.RLock()

def devices():
    with AUDIO_BACKEND_LOCK:
        apis=sd.query_hostapis(); output=[]
        for d in sd.query_devices():
            row=dict(d);row['hostapi_name']=apis[row['hostapi']]['name'];output.append(row)
        return output

def refresh_audio_backend():
    """Caller must hold the hardware lease: never reinitialize active streams."""
    with AUDIO_BACKEND_LOCK:
        sd._terminate()
        sd._initialize()
        return devices()

def playback_endpoint_problem(device,inventory):
    """Pure discovery/validation policy: explicit outputs and one XVF WDM route."""
    if device.get('max_output_channels',0)<1:return 'Selected endpoint has no playback channels'
    name=str(device.get('name',''))
    if re.search(r'sound\s+mapper|primary\s+sound\s+driver',name,re.I):
        return 'Select a named physical output, not a Windows default mapper or primary sound driver'
    xvf_alias=bool(re.search(r'xvf|xmos|echo.*(?:\(\s*x|\bxvf|\bxmos)',name,re.I))
    if xvf_alias:
        canonical=[d for d in inventory if 'XVF3800' in str(d.get('name','')).upper()
                   and d.get('hostapi_name')=='Windows WDM-KS' and d.get('max_output_channels',0)>=2]
        if len(canonical)!=1:return 'A unique XVF3800 Windows WDM-KS playback endpoint is required'
        if device.get('index')!=canonical[0].get('index'):
            return 'Select the explicit XVF3800 Windows WDM-KS LINE OUT output; this Windows alias is unsuitable'
    return None

def xvf_endpoints():
    ds=[d for d in devices() if 'XVF3800' in d['name'] and d['hostapi_name']=='Windows WDM-KS']
    ins=[d for d in ds if d['max_input_channels']>=2];outs=[d for d in ds if d['max_output_channels']>=2]
    if len(ins)!=1 or len(outs)!=1:raise RuntimeError('A unique XVF WDM-KS input/output pair is required')
    return ins[0],outs[0]

def pack_pcm24(x):
    """Signed 24-bit integer counts -> little-endian packed three-byte samples."""
    original=np.asarray(x)
    if not np.issubdtype(original.dtype,np.integer):raise ValueError('PCM24 requires integer counts')
    if original.size and (original.min()<-(1<<23) or original.max()>=(1<<23)):raise ValueError('PCM24 overflow')
    y=original.astype(np.int32).reshape(-1)
    b=np.empty((y.size,3),dtype=np.uint8)
    b[:,0]=y&255;b[:,1]=(y>>8)&255;b[:,2]=(y>>16)&255
    return b.tobytes()

def unpack_pcm24(data,channels=2):
    b=np.frombuffer(data,dtype=np.uint8).reshape(-1,3).astype(np.int32)
    v=b[:,0]|(b[:,1]<<8)|(b[:,2]<<16)
    v=(v^(1<<23))-(1<<23)
    return v.reshape(-1,channels)

def save_counts(path,data,rate,bits):
    sf.write(str(path), np.asarray(data,dtype=np.int32)<<8 if bits==24 else np.asarray(data,dtype=np.int16),rate,
             subtype='PCM_24' if bits==24 else 'PCM_16')

def decode_packed(raw,bits):
    raw=np.asarray(raw);lsb=raw&1
    matches=np.all(lsb[:-2]==0,axis=1)&np.all(lsb[1:-1]==1,axis=1)&np.all(lsb[2:]==1,axis=1)
    starts=np.flatnonzero(matches)
    if not len(starts):raise RuntimeError('No complete six-channel framing group')
    start=int(starts[0]);end=start+3*((len(raw)-start)//3)
    exp=np.tile(np.array([0,1,1],dtype=np.int32),(end-start)//3)
    bad=np.flatnonzero(np.any(lsb[start:end]!=exp[:,None],axis=1))+start
    decoded=(raw[start:end].reshape(-1,6)&np.int32(-2))
    qc={'native_frames':len(raw),'startup_frames_excluded':start,'common_end_native_frame':end,
        'trailing_frames':len(raw)-end,'decoded_frames':len(decoded),'decoded_sample_rate_hz':16000,
        'container_bits':bits,'payload_bits':bits-1,'marker_error_count':len(bad),'first_marker_errors':bad[:100].tolist(),
        'internal_repair_performed':False}
    return decoded,qc

def signal_stats(x,bits):
    x=np.asarray(x,dtype=np.float64);full=2**(bits-1)
    rms=np.sqrt(np.mean(x*x,axis=0));peaks=np.max(np.abs(x),axis=0)
    seconds=x[:len(x)//16000*16000].reshape(-1,16000,x.shape[1])
    return {'peak_counts':peaks.astype(np.int64).tolist(),'peak_to_peak_counts':np.ptp(x,axis=0).astype(np.int64).tolist(),'rms_dbfs':clean_json(20*np.log10(np.maximum(rms,1e-300)/full)),
       'headroom_db':clean_json(20*np.log10(full/np.maximum(peaks,1e-300))),
       'rail_samples':np.count_nonzero((x<=-full)|(x>=full-2),axis=0).tolist(),
       'nonzero_samples':np.count_nonzero(x,axis=0).tolist(),
       'fully_zero_one_second_windows':np.sum(np.all(seconds==0,axis=1),axis=0).tolist()}

def capture_native(seconds,bits=24,output_counts=None,stop_event=None,on_started=None,progress=None):
    """Finite bit-preserving duplex; original native frames and callback times retained."""
    inp,out=xvf_endpoints();dtype='int24' if bits==24 else 'int16';width=bits//8
    sd.check_input_settings(device=inp['index'],channels=2,dtype=dtype,samplerate=48000)
    sd.check_output_settings(device=out['index'],channels=2,dtype=dtype,samplerate=48000)
    frames_total=int(round(seconds*48000));frames_total-=frames_total%3
    output_counts=np.zeros((frames_total,2),dtype=np.int32) if output_counts is None else output_counts
    assert output_counts.shape==(frames_total,2)
    payload=pack_pcm24(output_counts) if bits==24 else output_counts.astype('<i2').tobytes()
    chunks=[];times=[];flags=[];position=0;done=threading.Event();errors=[]
    def callback(indata,outdata,frames,ti,status):
        nonlocal position
        try:
            take=min(frames,frames_total-position);offset=position*2*width;nbytes=take*2*width
            outdata[:nbytes]=payload[offset:offset+nbytes]
            if nbytes<len(outdata):outdata[nbytes:]=bytes(len(outdata)-nbytes)
            chunks.append(bytes(indata[:nbytes]));times.append({'first_native_frame':position,'frames':take,
              'host_callback_monotonic_ns':time.perf_counter_ns(),'input_adc_time':ti.inputBufferAdcTime,
              'output_dac_time':ti.outputBufferDacTime,'stream_current_time':ti.currentTime})
            if status:flags.append({'native_frame':position,'flags':str(status)})
            position+=take
            if position>=frames_total or (stop_event and stop_event.is_set()):raise sd.CallbackStop
        except sd.CallbackStop:raise
        except BaseException as e:errors.append(repr(e));raise sd.CallbackAbort
    start_ns=time.perf_counter_ns();start_utc=now()
    with sd.RawStream(samplerate=48000,channels=2,dtype=dtype,device=(inp['index'],out['index']),
        blocksize=0,latency=0.15,dither_off=True,clip_off=True,callback=callback,finished_callback=done.set) as stream:
        actual={'samplerate':stream.samplerate,'latency':list(stream.latency),'blocksize':stream.blocksize}
        if on_started:
            try:on_started()
            except BaseException as e:
                errors.append('startup hook: '+repr(e));stream.abort();done.set()
        while not done.wait(.1):
            if progress:progress(min(position/frames_total,1))
            if time.perf_counter_ns()-start_ns>(seconds+15)*1e9:
                errors.append('capture timeout');stream.abort();break
    end_ns=time.perf_counter_ns()
    b=b''.join(chunks);raw=unpack_pcm24(b) if bits==24 else np.frombuffer(b,dtype='<i2').astype(np.int32).reshape(-1,2)
    meta={'requested_seconds':seconds,'captured_frames':len(raw),'container_bits':bits,'native_rate_hz':48000,'requested_stream_latency_s':0.15,
      'input_device':inp,'output_device':out,'actual_stream':actual,'callback_flags':flags,'callback_errors':errors,
      'start_utc':start_utc,'start_monotonic_ns':start_ns,'end_monotonic_ns':end_ns,'callback_times':times,
      'stop_requested':bool(stop_event and stop_event.is_set()),'timestamps_calibrated_to_acoustics':False}
    return raw,meta

def freeze(folder):
    folder=Path(folder);manifest=folder/'SHA256SUMS.txt'
    if manifest.exists():raise RuntimeError('Run already frozen')
    paths=sorted(p for p in folder.rglob('*') if p.is_file())
    pending=folder/('.SHA256SUMS.pending_'+uuid.uuid4().hex)
    with pending.open('x',encoding='utf-8') as f:
        for p in paths:f.write(sha(p)+'  '+p.relative_to(folder).as_posix()+'\n')
        f.flush();os.fsync(f.fileno())
    for line in pending.read_text().splitlines():
        expected,relative=line.split('  ',1)
        if sha(folder/relative)!=expected:raise RuntimeError('Evidence hash mismatch')
    digest=sha(pending)
    # Windows rename is atomic and refuses an existing destination. The archive
    # sees its completion marker only after every file has been verified.
    os.rename(pending,manifest)
    return {'files':len(paths),'manifest_sha256':digest}
