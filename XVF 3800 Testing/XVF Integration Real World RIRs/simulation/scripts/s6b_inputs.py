"""Bind only S6B-consumed accepted data and preserve exact journal bytes. README_S6B.md."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import wave
from s6b_common import *

def native_receipt(job):
    path=Path(job['report_dir'])/'run_receipt.json'
    chain=[]; seen=set()
    while True:
        if str(path) in seen: raise ValueError('cyclic predecessor receipts')
        seen.add(str(path)); receipt=read(path); chain.append(bind(path))
        if receipt['status'] != 'COMPLETE': raise ValueError('incomplete predecessor')
        if not receipt.get('reused_receipt'): break
        bound=receipt['reused_receipt']; path=Path(bound['path']); bind(path,bound['sha256'])
    return receipt,chain

def prepare():
    target=REPORT/'INPUT_INDEX.json'
    if target.exists():
        prior=read(target)
        for row in prior['rows']:
            for key in ('audio','telemetry','baseline_features','baseline_events','support'):
                b=row[key];bind(b['path'],b['sha256'])
        return dict(status='VERIFIED_REUSE',outputs=len(prior['rows']))
    jobs=read(S6A/'JOB_MANIFEST.json')['jobs']
    cues={r['case_id']:r['sanitized'] for r in read(S6A/'CUE_DELIVERY_INDEX.json')['rows']}
    features={(r['case_id'],r['stream']):r['result'] for r in read(S6A/'cues/FEATURE_INDEX.json')['rows']}
    supports={r['case_id']:r['support'] for r in read(S6A/'support/FROZEN_SUPPORT_INDEX.json')['scenes']}
    verified_shared={}; rows=[]
    for i,job in enumerate(jobs):
        cid,out=job['case_id'],job['stream'];rec,chain=native_receipt(job)
        journal=rec['completion_evidence']['journal'];bind(journal['path'],journal['sha256'])
        events=rec['events_binding'];bind(events['path'],events['sha256'])
        summary=rec['session_summary_binding'];bind(summary['path'],summary['sha256'])
        if read(summary['path'])['state'] != 'COMPLETED': raise ValueError('Incomplete baseline session')
        if journal['bytes'] != rec['adapter']['samples']*2: raise ValueError('Baseline full tail journal mismatch')
        for b in (cues[cid],supports[cid]):
            if b['path'] not in verified_shared:
                verified_shared[b['path']]=bind(b['path'],b['sha256'])
        feature=features[cid,out];bind(feature['path'],feature['sha256'])
        fb=read(feature['path']);bind(fb['vectors']['path'],fb['vectors']['sha256'])
        if fb['identity']['audio_sha256'] != journal['sha256']: raise ValueError('Baseline feature waveform mismatch')
        dest=PAYLOAD/'inputs'/cid/(out+'.wav');dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists(): raise ValueError('Unreceipted input exists: '+str(dest))
        with wave.open(str(dest),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
            f.writeframes(Path(journal['path']).read_bytes())
        with wave.open(str(dest),'rb') as f:
            import hashlib
            payload_sha=hashlib.sha256(f.readframes(f.getnframes())).hexdigest()
            if payload_sha != journal['sha256']: raise ValueError('Input PCM changed')
        rows.append(dict(case_id=cid,stream=out,audio=bind(dest),audio_pcm_sha256=payload_sha,
            audio_format='mono PCM16 16000Hz; byte-identical historical full input journal',
            historical_gain_applied_once=job['gain'],input_gain=1.0,already_gained=True,
            duration_sec=journal['bytes']/32000,raw_audio=job['raw_audio'],baseline_receipt_chain=chain,
            baseline_journal=journal,baseline_events=events,baseline_summary=summary,
            baseline_features=feature,baseline_vectors=fb['vectors'],telemetry=cues[cid],support=supports[cid],
            baseline_final_metrics=rec['metrics_binding']))
        if (i+1)%80==0: print(json.dumps(dict(phase='INPUT_BINDING',complete=i+1,requested=480)),flush=True)
    if len(rows)!=480 or len({(r['case_id'],r['stream']) for r in rows})!=480: raise ValueError('All240/two tap coverage required')
    value=dict(schema='jp_s6b_consumed_inputs_v1',status='COMPLETE',created_utc=utc(),rows=rows,
        outputs=len(rows),physical_traces=len(cues),baseline_index=bind(S6A/'JOB_MANIFEST.json'),
        source_reference_audit_reused=bind(S6A/'TRANSCRIPT_COVERAGE_RECEIPT.json'),
        support_index=bind(S6A/'support/FROZEN_SUPPORT_INDEX.json'),
        full_hash_scope='Every consumed WAV PCM payload, native event, vector and support/telemetry file verified once at this admission; historical raw captures and RIRs inherit accepted bound source audits',
        labels_are_reference_only='case/stream/reference identities are coordinator metadata, never sent to prediction policy',
        gain_semantics='Main inputs use exact historical already-gained PCM16 bytes at unity. Any gain alternative must be independently derived from raw capture and bind its own gain exactly once.')
    save(target,value);return dict(status='COMPLETE',outputs=len(rows),index=str(target))

def gain_alternatives():
    import math
    import numpy as np
    import soundfile as sf
    target=REPORT/'GAIN_INPUT_INDEX.json'
    if target.exists():
        old=read(target)
        for r in old['rows']: bind(r['audio']['path'],r['audio']['sha256'])
        return dict(status='VERIFIED_REUSE',outputs=len(old['rows']))
    rows=[]
    for item in read(REPORT/'INPUT_INDEX.json')['rows']:
        raw=item['raw_audio'];bind(raw['path'],raw['sha256'])
        x,rate=sf.read(raw['path'],dtype='float32',always_2d=True)
        if rate!=16000 or x.shape[1]!=1 or not np.isfinite(x).all(): raise ValueError('Invalid mono input')
        gain=1.0 if item['stream']=='O0' else 10**(-3/20)
        y=(x[:,0].astype(np.float64)*gain).astype(np.float32)
        if np.max(np.abs(y))>1: raise ValueError('Gain exceeds headroom')
        dest=PAYLOAD/'inputs_gain_minus3'/item['case_id']/(item['stream']+'.wav')
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists(): raise ValueError('Unreceipted gain alternative exists')
        sf.write(dest,y,rate,subtype='FLOAT')
        rows.append(dict(case_id=item['case_id'],stream=item['stream'],audio=bind(dest),raw_audio=raw,
            input_gain=1.,already_gained=True,raw_gain_applied_once=gain,
            relative_to_historical_gain_db=-3.,duration_sec=len(y)/rate,
            prepared_format='mono float32 WAV; existing native journal conversion consumes at unity',
            peak_fs=float(np.max(np.abs(y))),raw_rail_samples=int(np.count_nonzero(np.abs(x[:,0])>=1-2/2**23))))
    save(target,dict(status='COMPLETE',rows=rows,created_utc=utc(),
        hypothesis='Fixed -3dB relative host gain crossed with dispatch-block/full-window RMS admission on both taps',
        runtime_gain=1.,gain_is_applied_to_raw_capture_exactly_once=True,baseline_gain_input_index=bind(REPORT/'INPUT_INDEX.json')))
    return dict(status='COMPLETE',outputs=len(rows))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gain-alternatives',action='store_true')
    args=parser.parse_args()
    print(json.dumps(gain_alternatives() if args.gain_alternatives else prepare(),indent=2))
