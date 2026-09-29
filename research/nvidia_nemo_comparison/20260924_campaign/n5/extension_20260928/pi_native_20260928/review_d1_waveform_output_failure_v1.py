"""Independent forced extraction-stop review; README_D1_WAVEFORM_OUTPUT_FAILURE_V1.md."""
import hashlib,json
from pathlib import Path
import psutil
R=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/d1-onnx-waveform-v1')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    psutil.Process().cpu_affinity([14]);names=['ADMISSION.json','GUARD_RESULT.json','JOB_ENVELOPE.json','MODEL_OWNER.json','REGISTERED_OWNER.json','supervision/worker.json','EXTRACTED_REFERENCE_REVIEW.json']
    d={n:json.loads((R/n).read_text(encoding='utf-8')) for n in names};a=d['ADMISSION.json'];g=d['GUARD_RESULT.json'];life=g['lifetime'];w=d['supervision/worker.json'];j=d['JOB_ENVELOPE.json']
    assert not (R/'RESULT.json').exists() and not (R/'full-reference.npz').exists() and not (R/'tail-reference.npz').exists()
    assert g['status']=='FAILED_PRESERVED' and g['error']=="AssertionError('Output bound')" and g['output_bytes']>a['output_max_bytes']==64*1024**2
    assert life['forced'] and life['root_exit_code']==125 and life['job_empty_verified'] and life['observed_members_exited']
    assert life['input_desktop_before']==life['input_desktop_after'] and w['status']=='FAILED'
    owners=[dict(pid=w[k],create_time=w[t]) for k,t in [('pid','create_time'),('child_pid','child_create_time')]]+[d['MODEL_OWNER.json'],d['REGISTERED_OWNER.json']['owner']]
    for o in owners:
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    for binding in a['bindings']:assert sha(binding['path'])==binding['sha256']
    assert j['affinity']==a['model_cpus']==d['MODEL_OWNER.json']['affinity']==[4,14] and j['hard_job_commit_bytes']==6*1024**3
    partial=d['EXTRACTED_REFERENCE_REVIEW.json'];assert partial['status']=='REJECTED_INCOMPLETE_EXTRACTED_CHECKPOINT_REUSE' and partial['reuse_admitted'] is False
    assert [x['complete'] for x in partial['files']]==[True,False]
    for x in partial['files']:
        p=R/'temp/tmp2g66gcit'/x['name'];assert p.stat().st_size==x['actual_bytes'] and sha(p)==x['actual_sha256']
    out=dict(status='REVIEWED_CHECKPOINT_EXTRACTION_OUTPUT_GUARD_STOP_ONLY',original_output_bound_bytes=a['output_max_bytes'],guard_retained_bytes=g['output_bytes'],sampled_bound_not_quota=True,forced_exit_code=125,exact_owners_closed=True,no_application_result=True,no_model_probability_evidence=True,incomplete_extraction_reuse_rejected=True,hashes={n:sha(R/n) for n in names})
    with (R/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
    print(json.dumps(out))
if __name__=='__main__':main()
