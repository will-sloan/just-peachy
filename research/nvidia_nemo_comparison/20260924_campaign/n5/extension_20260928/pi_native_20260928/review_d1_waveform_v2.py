"""Independent full waveform arrays/lineage/closure review; README_REVIEW_D1_WAVEFORM_V2.md."""
import hashlib,json
from pathlib import Path
import numpy as np
import psutil
ROOT=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/d1-onnx-waveform-v2')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    psutil.Process().cpu_affinity([14]);r=ROOT
    names=['ADMISSION.json','RESULT.json','GUARD_RESULT.json','JOB_ENVELOPE.json','MODEL_OWNER.json','REGISTERED_OWNER.json','supervision/worker.json']
    docs={n:json.loads((r/n).read_text(encoding='utf-8')) for n in names}
    a=docs['ADMISSION.json'];v=docs['RESULT.json'];g=docs['GUARD_RESULT.json'];w=docs['supervision/worker.json'];j=docs['JOB_ENVELOPE.json']
    for binding in a['bindings']:assert sha(binding['path'])==binding['sha256']
    life=g['lifetime'];assert life['status']=='OWNED_PROCESS_LIFETIME_CLOSED' and not life['forced'] and life['job_empty_verified'] and life['observed_members_exited']
    assert life['input_desktop_before']==life['input_desktop_after']
    owners=[dict(pid=w[k],create_time=w[t]) for k,t in [('pid','create_time'),('child_pid','child_create_time')]]+[docs['MODEL_OWNER.json'],docs['REGISTERED_OWNER.json']['owner']]
    for o in owners:
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    assert j['hard_job_commit_bytes']==a['hard_job_commit_bytes']==6*1024**3 and j['affinity']==a['model_cpus']==docs['MODEL_OWNER.json']['affinity']==[4,14]
    assert a['threads']==1 and not a['gpu'] and a['absolute_tolerance']==1e-5
    assert g['seconds']<600 and sum(p.stat().st_size for p in r.rglob('*') if p.is_file())<a['output_max_bytes']
    checks=[]
    for row in v['cases']:
        name=row['case'];refname='tail' if name=='tail' else 'full'
        with np.load(r/(refname+'-reference.npz')) as ref,np.load(r/(name+'-candidate.npz')) as got:
            truth=ref['probabilities'];actual=got['probabilities'];assert truth.shape==actual.shape==(row['samples']//160,8)
            assert np.isfinite(truth).all() and np.isfinite(actual).all()
            delta=float(np.max(np.abs(truth.astype('float64')-actual.astype('float64')))) if actual.size else 0
            last=len(row['trace'])-1;state_deltas={}
            for label,field in [('spkcache','cache'),('spkcache_preds','cache_probs'),('fifo','fifo'),('fifo_preds','fifo_probs')]:
                key=str(last)+'_'+label
                if key not in ref:continue
                truth_state=ref[key][0];actual_state=got[field];assert truth_state.shape==actual_state.shape
                state_deltas[field]=float(np.max(np.abs(truth_state.astype('float64')-actual_state.astype('float64')))) if actual_state.size else 0.0
            checks.append(dict(case=name,frames=len(actual),max_abs=delta,final_state_max_abs=state_deltas,within_gate=delta<=1e-5 and max(state_deltas.values(),default=0)<=1e-5))
            assert row['samples']==row['source_samples_accepted']==row['frontend_samples'] and row['final_features_empty']
            assert row['peak_feature_rows']<=2334 and row['subhop_remainder_samples']==row['samples']%160
            origin=0
            for entry in row['trace']:
                assert entry['feature_start']==origin and entry['feature_end']>origin
                assert entry['emitted_rows']==entry['feature_end']-origin and entry['cache_rows']<=264 and entry['fifo_rows']==0
                assert entry['trimmed_coarse_padding'] in range(8)
                origin=entry['feature_end']
            assert origin==len(actual)
    passed=v['status']=='HOST_WAVEFORM_FULL_REFERENCE_REVIEW_REQUIRED'
    if passed:
        assert w['status']=='COMPLETED' and w['exit_code']==life['root_exit_code']==0 and len(checks)==4 and all(x['within_gate'] for x in checks)
        assert v['invalid_calls_rejected']==7 and v['empty_contract_samples']==[0,1,159] and v['runtime_released']
        with np.load(r/'full-reference.npz') as ref,np.load(r/'full-candidate.npz') as first,np.load(r/'irregular-candidate.npz') as irregular,np.load(r/'repeat-candidate.npz') as repeat:
            assert np.array_equal(ref['probabilities'],np.load(r/'full-pytorch-repeat.npy'))
            assert np.array_equal(first['probabilities'],irregular['probabilities']) and np.array_equal(first['probabilities'],repeat['probabilities'])
    else:assert w['status']=='FAILED' and life['root_exit_code']==1
    output=dict(status='PASS_HOST_FULL_WAVEFORM_REPEAT_IRREGULAR_ONLY' if passed else 'REVIEWED_HOST_WAVEFORM_FAILURE_ONLY',cases=checks,error=v.get('error'),absolute_tolerance=1e-5,
        exact_owners_closed=True,natural_exit_code=life['root_exit_code'],original_q8_equivalence=False,native_pi_qualified=False,stage_acceptance=False,
        output_bytes=sum(p.stat().st_size for p in r.rglob('*') if p.is_file()),output_bound_bytes=a['output_max_bytes'],hashes={n:sha(r/n) for n in names})
    with (r/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(output,f,indent=2)
    print(json.dumps(output))
if __name__=='__main__':main()
