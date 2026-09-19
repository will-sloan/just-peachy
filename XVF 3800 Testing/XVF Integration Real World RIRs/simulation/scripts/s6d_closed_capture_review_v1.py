"""Independently check closed capture bytes and owners; see matching README."""
import argparse,datetime,hashlib,json,wave
from pathlib import Path
import numpy as np
import soundfile as sf
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def bind(p):
    p=Path(p).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def verify(b):
    actual=bind(b['path'])
    if (actual['bytes'],actual['sha256'])!=(b['bytes'],b['sha256']):raise ValueError('Binding changed: '+b['path'])
    return actual
def require(value,message):
    if not value:raise ValueError(message)
def field(d,key):
    for k in key.split('.'):d=d[k]
    return d
def counts(path,channels,rate):
    with wave.open(str(path),'rb') as f:
        require((f.getnchannels(),f.getsampwidth(),f.getframerate())==(channels,3,rate),'PCM24 header')
        frames=f.getnframes();raw=f.readframes(frames)
    b=np.frombuffer(raw,dtype=np.uint8).reshape(-1,3).astype(np.int32)
    n=b[:,0]|b[:,1]<<8|b[:,2]<<16;n=np.where(n&0x800000,n-0x1000000,n).astype(np.int32)
    require(len(n)==frames*channels,'Truncated WAV');return n.reshape(-1,channels)
def inspect_case(binding,attempt,route):
    rb=verify(binding);c=read(rb['path']);require(c['attempt']==attempt,'Attempt contract')
    require(c['status']=='PASS' and c['transport_integrity_status']=='PASS','Transport failure')
    verified=[rb]+[verify(c[k]) for k in ('configuration','metadata','native_packed','decoded')]
    verified += [verify(x['audio']) for x in c['streams']]
    verified += [verify(c['source_input'][k]) for k in ('source','packed')]
    require(c['source_input']['source']['sha256']==attempt['source_audio']['sha256'],'Source input binding')
    cfg=read(c['configuration']['path']);meta=read(c['metadata']['path'])
    require(cfg['profile']==attempt['profile'] and cfg['decoded_streams']==route['logical_streams'] and cfg['mux_api_arguments']==route['mux_api_arguments'],'Actual readback route')
    require(cfg['settings']['AUDIO_MGR_OP_ALL']==route['mux_api_arguments'],'Mux readback')
    source,rate=sf.read(c['source_input']['source']['path'],dtype='float64',always_2d=True)
    require(rate==16000 and source.shape[1]==4 and len(source)==round(attempt['duration_sec']*16000) and np.isfinite(source).all(),'Whole finite microphone input')
    expected=np.zeros((len(source)+64000,6),np.int32)
    expected[16000:16000+len(source),2:]=np.rint(source*2**22).astype(np.int32)*2
    carrier=expected.reshape(-1,2).copy();carrier[1::3]|=1;carrier[2::3]|=1
    unsigned=carrier.ravel().astype(np.uint32)
    packed=np.column_stack((unsigned&255,(unsigned>>8)&255,(unsigned>>16)&255)).astype(np.uint8).tobytes()
    require(hashlib.sha256(packed).hexdigest()==c['source_input']['packed']['sha256'],'Whole unity source +1/3s guards input bytes')
    del carrier,unsigned,packed
    require(meta['writer_closed'] and meta['audio_handles_closed'] and not meta['callback_errors'],'Audio closure/errors')
    require(not [f for f in meta['callback_flags'] if f['flags'].strip().lower()!='priming output'],'Callback integrity flags')
    require(meta['carrier_frames_submitted']==len(expected)*3 and meta['source_payload_frames_submitted']==len(source),'Whole submitted source')
    require(0<=meta['terminal_padding_frames']<=16383,'Terminal padding bound')
    native=counts(c['native_packed']['path'],2,48000)
    require(len(native)==meta['captured_frames'] and len(native)==len(expected)*3+meta['terminal_padding_frames'],'Recorded native extent')
    framing=c['framing'];start=framing['startup_frames_excluded'];end=framing['common_end_native_frame']
    require(0<=start<end<=len(native) and (end-start)%3==0 and not framing['marker_error_count'],'Framing bounds')
    marker=np.tile(np.array([0,1,1]),(end-start)//3)
    require(np.all((native[start:end]&1)==marker[:,None]),'Packed marker bytes')
    decoded=native[start:end].reshape(-1,6)&np.int32(-2)
    require(np.array_equal(decoded,counts(c['decoded']['path'],6,16000)),'Saved six-channel derivative')
    streams=[]
    for i,row in enumerate(c['streams']):
        require([row['name'],row['category'],row['source']]==route['logical_streams'][i] and row['raw_gain']==1.,'Named logical stream')
        require(np.array_equal(decoded[:,i:i+1],counts(row['audio']['path'],1,16000)),'Saved mono derivative')
        pcm=decoded[:,i];rail=int(np.count_nonzero((pcm>=8388606)|(pcm<=-8388608)))
        nonzero=int(np.count_nonzero(pcm))
        if row['name'] in attempt['required_nonzero_streams']:require(nonzero>0,'Required stream has zero payload')
        active=np.flatnonzero(pcm)
        streams.append(dict(name=row['name'],nonzero_samples=nonzero,rail_samples=rail,quality='LIMITED' if rail else 'NO_RAIL',peak_abs=float(np.max(np.abs(pcm.astype(np.float64))))/8388608.,first_nonzero_frame=int(active[0]) if len(active) else None,last_nonzero_frame=int(active[-1]) if len(active) else None))
    qa=dict(status='NOT_OBSERVABLE_PROCESSED_ONLY',exact_mic_recovery_claim=False)
    if attempt['profile']=='P_INPUT_QA6':
        require(c['input_qa']['status']=='PASS','QA original status')
        offset=c['input_qa']['capture_minus_source_offset_samples'];a=max(0,offset);b=min(len(decoded),len(expected)+offset)
        active=np.flatnonzero(np.any(expected[:,2:]!=0,axis=1));require(len(active)>0 and a-offset<=active[0] and b-offset>active[-1],'All nonzero MIC source extent')
        mismatch=(decoded[a:b,2:]!=expected[a-offset:b-offset,2:]).sum(axis=0)
        require(not np.any(mismatch) and (b-a)*4==c['input_qa']['compared_mic_samples'],'Exact MIC counts')
        qa=dict(status='PASS',common_offset_samples=offset,compared_mic_samples=(b-a)*4,mismatches=mismatch.tolist(),all_nonzero_source_payload_captured=True)
    require(c['telemetry']['status']=='PASS' and c['telemetry']['control_owner_closed_proven'] and not c['telemetry']['errors'],'Telemetry closure')
    return dict(attempt_id=attempt['attempt_id'],case_id=attempt['case_id'],profile=attempt['profile'],verified_bindings=verified,
        source_frames=len(source),native_frames=len(native),decoded_frames=len(decoded),startup_excluded_native_frames=start,
        all_submitted_source_verified=True,decoded_and_six_derivatives_exact=True,marker_errors=0,streams=streams,
        exact_equal_stream_pairs=[[c['streams'][i]['name'],c['streams'][j]['name']] for i in range(6) for j in range(i+1,6) if np.array_equal(decoded[:,i],decoded[:,j])],
        input_QA=qa,telemetry_owner_closed=True,processed_source_tail_qualification='REQUIRES_MEASURED_DELAY_REVIEW' if attempt['profile']!='P_INPUT_QA6' else 'EXACT_NONZERO_MIC_PAYLOAD_CAPTURED')
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--queue',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    require(not a.output.exists(),'Preserve existing review');q=read(a.queue);require(len(q['jobs'])==1,'One closed qualification stage')
    job=q['jobs'][0];complete=read(job['completion_path']);restore=read(job['restoration_path'])
    for expected in job['expected_artifacts']:
        d=read(expected['path'])
        for key,value in expected['expected_fields'].items():require(field(d,key)==value,'Completion predicate '+key)
    for b in job['source_bindings']:verify(b)
    require(restore['verified'] and all(restore['proof']['checks'].values()),'Actual owner restoration')
    closures=list((a.queue.parent/'state').glob('SUPERVISOR_CLOSURE_*.json'));require(len(closures)==1,'Unique supervisor closure')
    closure=read(closures[0]);require(closure['result']['action']=='FINISH' and not closure['hardware_restoration_unresolved'] and closure['keep_awake']['restored'] and closure['owner_lock']=='RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT','Supervisor fully closed')
    require(closure.get('payload_census_closure',{}).get('closed') is True,'Census worker closed')
    plan=read(verify(complete['plan'])['path']);summary=read(verify(complete['semantic_checks']['summary'])['path'])
    require(summary['status']=='COMPLETE_CAPTURE_BATCH' and summary['executed_source_bytes_unchanged_after_batch'],'Owner batch/source closure')
    contract=read(Path(plan['report_root'])/'physical_preparation_v2/QUALIFICATION_ANALYSIS_CONTRACT.json')
    results={read(b['path'])['attempt']['attempt_id']:b for b in summary['completed_attempts']}
    require(set(results)=={x['attempt_id'] for x in plan['attempts']},'Complete exact attempts')
    inspected=[inspect_case(results[x['attempt_id']],x,contract['route_checks']['profiles'][x['profile']]) for x in plan['attempts']]
    receipt=dict(status='CLOSED_CAPTURE_TRANSPORT_ARTIFACTS_VERIFIED',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=bind(__file__),queue=bind(a.queue),completion=bind(job['completion_path']),restoration=bind(job['restoration_path']),supervisor_closure=bind(closures[0]),attempts=inspected,
        captures=len(inspected),native_or_neural_model_calls=0,hardware_calls=0,
        scope='File-only independent transport, saved-audio and actual closure verification. Processed delay/tail, route identity and observer interpretation require separate review; no bank authority or overall completion.')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(status=receipt['status'],captures=len(inspected),receipt=bind(a.output))))
if __name__=='__main__':main()
