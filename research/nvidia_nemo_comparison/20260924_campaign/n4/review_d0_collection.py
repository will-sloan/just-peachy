"""Verify matched C lane collections without fitting. README_D0_REVIEW.md."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from common import load, bind, verify, freeze, fingerprint


def validate_pair(left, right):
    import numpy as np
    if left['status'] != 'COMPLETE' or right['status'] != 'COMPLETE':
        raise ValueError('Incomplete encoder clip')
    if left['encoder'] != 'E0' or right['encoder'] != 'E1' or left['job'] != right['job']:
        raise ValueError('Paired encoder/audio contract differs')
    for key in ('admission_sha256','profile_sha256','segmentation_calls'):
        if left[key] != right[key]:
            raise ValueError('Paired lane configuration differs: '+key)
    if left['error'] is not None or right['error'] is not None:
        raise ValueError('Failed lane carries complete status')
    geometry=[]
    for cell in (left,right):
        if cell['telemetry']['identity_audio_samples'] != cell['job']['frames']:
            raise ValueError('Incomplete source census')
        rows=[]; seen=set()
        for row in cell['vectors']:
            vector=np.asarray(row['normalized_embedding'],dtype=np.float64)
            if vector.shape != (192,) or not np.isfinite(vector).all() or abs(np.linalg.norm(vector)-1)>1e-4:
                raise ValueError('Invalid normalized vector')
            a,b=row['start_sample'],row['end_sample']; role=row['evidence_kind']
            if type(a) is not int or type(b) is not int or not 0<=a<b<=cell['job']['frames']:
                raise ValueError('Window outside actual audio')
            if role not in ('short','mature') or b-a != (8000 if role=='short' else 24000):
                raise ValueError('Changed D0 short/mature query span')
            if (a,b,role) in seen:raise ValueError('Duplicate query window')
            seen.add((a,b,role))
            if any(not a/16000-1e-8<=start<end<=b/16000+1e-8 for start,end in row['clean_intervals']):
                raise ValueError('Clean support outside query')
            rows.append({k:v for k,v in row.items() if k!='normalized_embedding'})
        geometry.append(rows)
    if geometry[0] != geometry[1]:raise ValueError('Encoders used different waveform windows')
    return geometry[0]


def main(args):
    import os
    os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
    import psutil
    import soundfile as sf
    process=psutil.Process();process.cpu_affinity([14]);process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    root=args.run; final=load(root/'RESULT.json'); admission=load(root/'ADMISSION.json')
    if final['status']!='COLLECTED_REQUIRES_CALIBRATION_REVIEW':
        raise ValueError('Collection must finish successfully before review')
    for owner in (final['owner'], final.get('child')):
        if not owner:continue
        try:
            if psutil.Process(owner['pid']).create_time()==owner['create_time']:
                raise ValueError('Collection owner is still alive')
        except psutil.NoSuchProcess:pass
    verify(final['admission']); verify(admission['audio']);verify(admission['source_receipt'])
    for row in admission['model_bindings']+admission['code']:verify(row)
    protocol=load(args.protocol)
    if protocol['collection_admission_sha256']!=final['admission']['sha256']:
        raise ValueError('Scale protocol targets a different collection')
    indexes=[]
    for binding in final['encoders']:
        verify(binding); result=load(binding['path'])
        if result['status']!='COMPLETE' or result['completed']!=admission['expected_clips']:
            raise ValueError('Incomplete collection index')
        indexed={}
        for cell_binding in result['cells']:
            verify(cell_binding);cell=load(cell_binding['path']);key=cell['job']['window_id']
            if key in indexed:raise ValueError('Duplicate C source cell')
            verify(cell['events']);indexed[key]=(cell,cell_binding)
        indexes.append(indexed)
    jobs=load(admission['audio']['path'])['jobs']; required={j['window_id'] for j in jobs}
    if len(required)!=len(jobs) or any(set(idx)!=required for idx in indexes):
        raise ValueError('Missing/extra C source cells')
    details=[]; counts=dict(short=0,mature=0); no_windows=0; seg_calls=0
    for job in jobs:
        pair=[idx[job['window_id']] for idx in indexes]
        if any(cell['job']!=job for cell,_ in pair):raise ValueError('Job differs from admission')
        if any(cell['admission_sha256']!=final['admission']['sha256'] for cell,_ in pair):
            raise ValueError('Cell admission differs')
        geometry=validate_pair(pair[0][0],pair[1][0]);verify(job['audio'])
        audio,rate=sf.read(job['audio']['path'],dtype='float32')
        if rate!=16000 or audio.ndim!=1 or len(audio)!=job['frames']:raise ValueError('Source audio differs')
        for window in geometry:
            wave=audio[window['start_sample']:window['end_sample']]
            if hashlib.sha256(wave.astype('<f4').tobytes()).hexdigest()!=window['waveform_sha256']:
                raise ValueError('Actual waveform slice hash differs')
            counts[window['evidence_kind']]+=1
        no_windows+=not geometry;seg_calls+=pair[0][0]['segmentation_calls']
        details.append(dict(window_id=job['window_id'],query_windows=len(geometry),
            matching_geometry_sha256=fingerprint(geometry),results=[binding for _,binding in pair]))
    if args.output.exists():raise ValueError('Preserve review evidence; choose a fresh output')
    args.output.mkdir(parents=True)
    receipt=dict(schema='n4-d0-C-collection-review-v1',status='PASS_MATCHED_C_COLLECTION_ONLY',
        clips_per_encoder=len(jobs),encoder_clip_cells=2*len(jobs),matched_query_windows_per_encoder=sum(counts.values()),
        query_kinds_per_encoder=counts,clips_without_admitted_windows_per_encoder=no_windows,
        segmentation_calls_per_encoder=seg_calls,source_seconds_per_encoder=sum(j['frames'] for j in jobs)/16000,
        input_bindings=[bind(root/'RESULT.json'),bind(root/'ADMISSION.json'),bind(args.protocol)],
        code=[bind(__file__),bind(Path(__file__).with_name('common.py'))],
        collection_complete=True,calibrated_profile_accepted=False,integrated_N4_cells=0,
        privacy='Detailed matched window evidence and all vectors retained privately',cells=details)
    freeze(args.output/'REVIEW.json',receipt)
    public={k:v for k,v in receipt.items() if k!='cells'}
    public['private_review']=bind(args.output/'REVIEW.json')
    freeze(args.output/'REDACTED_REVIEW.json',public)
    print(json.dumps(public,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('run','protocol','output'):parser.add_argument('--'+name,type=Path,required=True)
    main(parser.parse_args())
