"""Verify a closed raw-pair probe and save private PCM; README_RUNTIME_RAW_VERIFY_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,hashlib,io,json,os,shutil,struct,sys,wave
from pathlib import Path
from datetime import datetime,timezone

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('probe','source-closed','scope','output'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();a.output.mkdir()
    def put(path,raw):
        if len(raw)>262144:raise ValueError('Bounded private member')
        with path.open('xb') as f:
            if f.write(raw)!=len(raw):raise IOError('Short write')
            f.flush();os.fsync(f.fileno())
        if path.read_bytes()!=raw:raise IOError('Independent exact readback')
    def save(n,v):put(a.output/n,(json.dumps(v,sort_keys=True,indent=2)+'\n').encode())
    me=psutil.Process();save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    scope=json.loads(a.scope.read_bytes())
    if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Fresh host scope')
    for drive,n in [('C:/',50),('G:/',75)]:
        if shutil.disk_usage(drive).free<n*1024**3+2097152:raise RuntimeError('Host floor')
    source=Path(__file__).with_name('field_runtime_raw_decoder_v1.py')
    pins=json.loads(a.source_closed.read_bytes())['files'];raw=source.read_bytes()
    if pins[source.name]!=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()):raise ValueError('Backed decoder pin')
    from field_runtime_raw_decoder_v1 import decode,channel_bytes,CHANNELS
    # Only changed strict-marker behavior, three alignments and corruption.
    rows=[]
    for i in range(12):
        marker=0 if i%3==0 else 1
        rows.append(struct.pack('<ii',(100+i*2)|marker,(-200-i*2)|marker))
    fixture=b''.join(rows);positive=0
    for head in (0,1,2):
        d=decode(fixture[head*8:]);positive+=1
        if d['marker_errors'] or d['discarded_prefix_transport_frames']>=3:raise AssertionError('Synthetic alignment')
    corrupted=bytearray(fixture);corrupted[8]^=1
    try:decode(bytes(corrupted))
    except ValueError:pass
    else:raise AssertionError('Corrupt markers accepted')
    save('CHANGED_MARKER_CHECK.json',dict(positive_alignments=positive,rejected_marker_discontinuity=True,synthetic=True))
    value=json.loads((a.probe/'RESULT.json').read_bytes());phase=value['raw_pair_probe']
    closure=json.loads((a.probe/'NATIVE_CLOSURE.json').read_bytes())
    child=json.loads((a.probe/'ARECORD_CLOSURE.json').read_bytes())
    if not closure['exact_pid_absent'] or closure['natural_returncode'] or child['returncode'] or child['fault']:raise ValueError('Actual closed processes')
    cap=phase['capture']
    if phase['error'] or cap['child_returncode'] or cap['stderr'] or cap['errors'] or not cap['child_exact_dead'] or not cap['readers_joined']:raise ValueError('Capture closure')
    if phase['route_restoration']!={'AUDIO_MGR_OP_PACKED':'RESTORED','AUDIO_MGR_OP_ALL':'RESTORED'}:raise ValueError('Actual restoration')
    expected={'AUDIO_MGR_OP_ALL':[7,3,1,0,1,2,6,3,1,1,1,3],'AUDIO_MGR_OP_PACKED':[1,1]}
    if phase['route_selected']!=expected:raise ValueError('Actual physical mux routes')
    raw=(a.probe/'PACKED_S32LE.bin').read_bytes()
    if raw!=(a.probe/'PACKED_S32LE.restore.bin').read_bytes() or hashlib.sha256(raw).hexdigest()!=cap['sha256']:raise ValueError('Exact native transport bytes')
    try:decoded=decode(raw)
    except Exception as exc:
        save('DECODE_FAILURE.json',dict(error=type(exc).__name__+': '+str(exc),raw_sha256=hashlib.sha256(raw).hexdigest(),raw_preserved=True))
        raise
    files={}
    for name,channels in [('paired_six_channels.wav',(0,1,2,3,4,5)),('raw_mic0_mic3.wav',(2,3,4,5)),('auto_asr.wav',(0,)),('processed_autoselect.wav',(1,))]:
        payload=channel_bytes(decoded,channels);buf=io.BytesIO()
        with wave.open(buf,'wb') as w:w.setnchannels(len(channels));w.setsampwidth(4);w.setframerate(16000);w.writeframes(payload)
        wav=buf.getvalue()
        for folder in ('primary','independent-restore'):
            directory=a.output/folder;directory.mkdir(exist_ok=True)
            put(directory/name,wav)
            with wave.open(str(directory/name),'rb') as w:
                if (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())!=(len(channels),4,16000,decoded['frames']) or w.readframes(decoded['frames']+1)!=payload:raise IOError('Full WAV audio readback')
        files[name]=dict(bytes=len(wav),sha256=hashlib.sha256(wav).hexdigest(),channels=[CHANNELS[i] for i in channels],frames=decoded['frames'],rate=16000)
    del decoded['pcm_s32le']
    result=dict(status='PASS_ACTUAL_PHYSICAL_RAW_AND_PROCESSED_PACKING',utc=datetime.now(timezone.utc).isoformat(),
        decoder=decoded,files=files,source_capture=cap,probe=str(a.probe),source_policy_sha256=hashlib.sha256((a.probe/'RAW_PAIR_RESOURCE_POLICY.json').read_bytes()).hexdigest(),
        independent_pc_readbacks=2,route_restored=True,model_integration_qualified=False,physical_acoustic_validation=False,
        original_source_unchanged=True,lossless_transport_and_decoded_pcm_copies=True)
    save('RESULT.json',result)
    if sum(p.stat().st_size for folder in (a.probe,a.output) for p in folder.rglob('*') if p.is_file())>2097152:raise ValueError('Combined actual reserved host bytes')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Closed inside host scope')
    print(json.dumps(dict(status=result['status'],frames=decoded['frames'],duration_seconds=decoded['frames']/16000,files=len(files),route_restored=True)))
if __name__=='__main__':main()
