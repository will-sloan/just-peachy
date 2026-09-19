"""Read-only first-QA audio/closure review; see README_S6D_FIRST_CAPTURE_REVIEW_V1.md."""
from pathlib import Path
import datetime,hashlib,json,wave
import numpy as np
import soundfile as sf
SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
Q=R/'runner/first_capture_queue_v1'
OUT=R/'physical_first_QA_review_v1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def bind(p):
    p=Path(p).resolve();data=p.read_bytes();return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def verify(b):
    a=bind(b['path'])
    if (a['bytes'],a['sha256'])!=(b['bytes'],b['sha256']):raise ValueError('Binding changed: '+b['path'])
    return a
def wav_counts(path,channels,rate):
    with wave.open(str(path),'rb') as f:
        if (f.getnchannels(),f.getsampwidth(),f.getframerate())!=(channels,3,rate):raise ValueError('Wrong PCM24 WAV header')
        count=f.getnframes();raw=f.readframes(count)
    b=np.frombuffer(raw,dtype=np.uint8).reshape(-1,3).astype(np.int32)
    n=b[:,0]|b[:,1]<<8|b[:,2]<<16
    n=np.where(n&0x800000,n-0x1000000,n).astype(np.int32)
    if len(n)!=count*channels:raise ValueError('Truncated WAV')
    return n.reshape(-1,channels)
def field(value,key):
    for p in key.split('.'):value=value[p]
    return value
def main():
    if OUT.exists():raise ValueError('Preserve existing review')
    queue=read(Q/'QUEUE.json');job=queue['jobs'][0]
    completion=read(job['completion_path']);restore=read(job['restoration_path'])
    failures=[]
    for expected in job['expected_artifacts']:
        actual=read(expected['path'])
        for k,v in expected['expected_fields'].items():
            got=field(actual,k)
            if got!=v:failures.append(dict(artifact=expected['path'],field=k,expected=v,actual=got))
    # Preserve this actual root-authored predicate error, not an experimental failure.
    if failures!=[dict(artifact=job['completion_path'],field='progress_count',expected=1,actual=17)]:
        raise ValueError('Unexpected original queue failure set')
    if completion['semantic_checks']['attempt_count']!=1 or completion['protocol_observer_errors'] or not completion['protocol_observer_closed']:
        raise ValueError('Capture semantic closure invalid')
    if restore['status']!='RESTORED' or not restore['verified'] or not all(restore['proof']['checks'].values()):raise ValueError('Restoration invalid')
    for key in ('plan','authorization','owner','wrapper'):verify(completion[key])
    for b in read(completion['authorization']['path'])['source_bindings']:verify(b)
    for b in completion['restoration'].values():
        if isinstance(b,dict) and 'sha256' in b:verify(b)
    verify(completion['semantic_checks']['summary'])
    ledger=read(R/'physical_ledger.json')
    if len(ledger['passes'])!=1 or ledger['passes'][0]['status']!='PASS' or ledger['passes'][0]['charged_playback_s']!=12.3413125:raise ValueError('Wrong first ledger')
    rb=verify(ledger['passes'][0]['result']);case=read(rb['path'])
    if case['status']!='PASS' or case['transport_integrity_status']!='PASS' or case['input_qa']['status']!='PASS':raise ValueError('QA failed')
    bindings=[rb]
    for k in ('configuration','metadata','native_packed','decoded'):bindings.append(verify(case[k]))
    for row in case['streams']:bindings.append(verify(row['audio']))
    bindings.extend(verify(case['source_input'][k]) for k in ('source','packed'))
    source,rate=sf.read(case['source_input']['source']['path'],dtype='float64',always_2d=True)
    if rate!=16000 or source.shape!=(128000,4) or not np.isfinite(source).all():raise ValueError('Wrong source')
    expected=np.zeros((192000,6),np.int32)
    expected[16000:144000,2:]=np.rint(source*2**22).astype(np.int32)*2
    carrier=expected.reshape(-1,2).copy();carrier[1::3]|=1;carrier[2::3]|=1
    unsigned=carrier.ravel().astype(np.uint32)
    packed=np.column_stack((unsigned&255,(unsigned>>8)&255,(unsigned>>16)&255)).astype(np.uint8).tobytes()
    if hashlib.sha256(packed).hexdigest()!=case['source_input']['packed']['sha256']:raise ValueError('Actual transmitted input differs from whole unity source plus guards')
    native=wav_counts(case['native_packed']['path'],2,48000)
    framing=case['framing'];start=framing['startup_frames_excluded'];end=framing['common_end_native_frame']
    if len(native)!=576000 or end!=576000 or (end-start)%3:raise ValueError('Framing extent')
    marker=np.tile(np.array([0,1,1]),(end-start)//3)
    if not np.all((native[start:end]&1)==marker[:,None]):raise ValueError('Packed marker error')
    decoded=native[start:end].reshape(-1,6)&np.int32(-2)
    if not np.array_equal(decoded,wav_counts(case['decoded']['path'],6,16000)):raise ValueError('Decoded saved bytes differ')
    for i,row in enumerate(case['streams']):
        if not np.array_equal(decoded[:,i:i+1],wav_counts(row['audio']['path'],1,16000)):raise ValueError('Mono derivative differs')
    offset=case['input_qa']['capture_minus_source_offset_samples']
    a=max(0,offset);b=min(len(decoded),len(expected)+offset)
    nonzero=np.flatnonzero(np.any(expected[:,2:]!=0,axis=1))
    if not (a-offset<=nonzero[0] and b-offset>nonzero[-1]):raise ValueError('Source activity not fully captured')
    mismatch=(decoded[a:b,2:]!=expected[a-offset:b-offset,2:]).sum(axis=0)
    if np.any(mismatch) or (b-a)*4!=case['input_qa']['compared_mic_samples']:raise ValueError('Exact MIC recovery not reproduced')
    meta=read(case['metadata']['path'])
    if not meta['writer_closed'] or not meta['audio_handles_closed'] or meta['callback_errors'] or meta['carrier_frames_submitted']!=576000 or meta['source_payload_frames_submitted']!=128000:raise ValueError('Audio completion failed')
    if case['telemetry']['status']!='PASS' or not case['telemetry']['control_owner_closed_proven'] or case['telemetry']['errors']:raise ValueError('Telemetry closure failed')
    closures=list((Q/'state').glob('SUPERVISOR_CLOSURE_*.json'))
    if len(closures)!=1:raise ValueError('Unique actual supervisor closure required')
    closure=read(closures[0])
    if closure['hardware_restoration_unresolved'] or not closure['keep_awake']['restored'] or closure['owner_lock']!='RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT':raise ValueError('Supervisor ownership unresolved')
    outcome=dict(schema='s6d-root-first-QA-acceptance.v1',status='ACCEPTED_FIRST_QA_AND_RESTORATION_ONLY',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source=bind(__file__),original_queue=bind(Q/'QUEUE.json'),original_supervisor_closure=bind(closures[0]),original_supervisor_status=closure['result'],
        predicate_correction=dict(original_failures=failures,cause='Root admission mistook durable file-progress count for physical attempt count. Correct attempt count is semantic_checks.attempt_count=1; progress_count=17 is not17 captures.',
            original_queue_preserved=True,capture_repeated=False,root_semantic_acceptance_supersedes_only_this_predicate=True),
        physical_protocol=bind(job['completion_path']),restoration_protocol=bind(job['restoration_path']),verified_case_bindings=bindings,
        independent_audio_checks=dict(transmitted_source_plus_guards_exact=True,native_marker_errors=0,decoded_and_all6_mono_derivatives_exact=True,
            common_recorded_offset_samples=offset,compared_mic_samples=(b-a)*4,per_MIC_mismatches=mismatch.tolist(),all_nonzero_source_payload_captured=True),
        quality_limit=dict(status=case['level_screen']['status'],limited_streams=case['level_screen']['limited_streams'],auto_pp_rail_samples=15,
            gain_changed=False,scope='Transport accepted, auto PP is LIMITED; no blanket audio-quality or beam/tail identity qualification'),
        telemetry=dict(required_fast_count=199,measured_fast_rate_hz=16.08218692790463,requested_fast_rate_hz=20,AGC_gain_samples=0,optional_slow_fields_degraded=True,
            hardware_control_owner_closed=True,scope='No identity/beam/atomic-DSP-frame claim; optional telemetry loss retained'),
        attempts=1,charged_playback_seconds=12.3413125,next_stage='May admit declared MAIN qualification controls/C after exact new queue review; no240-bank admission yet',overall_S6D_complete=False)
    OUT.mkdir();(OUT/'ROOT_ACCEPTANCE.json').write_text(json.dumps(outcome,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=outcome['status'],receipt=bind(OUT/'ROOT_ACCEPTANCE.json'),audio=outcome['independent_audio_checks']),indent=2))
if __name__=='__main__':main()
