"""Independent stored-array and closure review. README_REVIEW_D1_STATE_TIE_V1.md."""
import hashlib,json
from pathlib import Path
import numpy as np
import psutil

BASE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def review(version):
    ROOT=BASE/('d1-onnx-state-tie-v'+str(version))
    psutil.Process().cpu_affinity([14])
    docs={n:json.loads((ROOT/n).read_text(encoding='utf-8')) for n in ['ADMISSION.json','RESULT.json','GUARD_RESULT.json','JOB_ENVELOPE.json','MODEL_OWNER.json','REGISTERED_OWNER.json','supervision/worker.json']}
    a=docs['ADMISSION.json'];r=docs['RESULT.json'];g=docs['GUARD_RESULT.json'];w=docs['supervision/worker.json'];j=docs['JOB_ENVELOPE.json']
    assert w['status'] in ['COMPLETED','FAILED'] and w['exit_code'] in [0,1]
    assert g['status']=='WORKER_EXITED_REVIEW_REQUIRED' and g['seconds']<600
    life=g['lifetime'];assert life['status']=='OWNED_PROCESS_LIFETIME_CLOSED' and not life['forced'] and life['root_exit_code']==w['exit_code']
    assert life['job_empty_verified'] and life['observed_members_exited'] and life['input_desktop_before']==life['input_desktop_after']
    owners=[dict(pid=w['pid'],create_time=w['create_time']),dict(pid=w['child_pid'],create_time=w['child_create_time']),docs['MODEL_OWNER.json'],docs['REGISTERED_OWNER.json']['owner']]
    for o in owners:
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    assert j['hard_job_commit_bytes']==a['hard_job_commit_bytes']==6*1024**3
    assert j['affinity']==docs['MODEL_OWNER.json']['affinity']==a['model_cpus']==[4,14]
    assert j['max_processes']==16 and j['kill_on_close'] and a['threads']==1 and not a['gpu']
    for b in a['bindings']:assert sha(b['path'])==b['sha256']
    assert r['finite_tie_reproduced'] and r['rejection_atomicity_verified'] and len(r['reconstructed_prefix_byte_exact'])==14
    with np.load(ROOT/'reconstructed_input.npz',allow_pickle=False) as z,np.load(BASE/'d1-onnx-state-v1/overlap-1.npz',allow_pickle=False) as previous:
        assert np.array_equal(z['cache'],previous['reference_cache']) and np.array_equal(z['cache_probs'],previous['reference_cache_probs'])
        assert np.array_equal(z['joined'],np.concatenate((z['cache'],z['chunk'][1:])))
        assert np.array_equal(z['joined_probs'],np.concatenate((z['cache_probs'],z['predictions'][265:])))
        assert z['joined'].shape==(281,512) and z['joined_probs'].shape==(281,8)
    errors=None
    if version==1:
        assert r['status']=='FAILED_PRESERVED' and 'INVALID_GRAPH' in r['error'] and "tensor(bool)" in r['error'] and w['exit_code']==1
        status='REVIEWED_RECONSTRUCTED_TIE_ATOMIC_REJECTION_AND_BOOLEAN_EXPORT_FAILURE'
    else:
        repair=json.loads((ROOT/'BOOLEAN_UNION_REPAIR.json').read_text());assert len(repair['repairs'])==1 and repair['repairs'][0]['old_type']=='Add' and repair['repairs'][0]['new_type']=='Or'
        assert sha(ROOT/'cache_compression.onnx')==r['graph_sha256']
        errors=[]
        with np.load(ROOT/'comparison.npz',allow_pickle=False) as z,np.load(ROOT/'pytorch_reference.npz',allow_pickle=False) as original:
            for name,key in [('cache','cache'),('probs','cache_probs')]:
                ref=z['reference_'+name];out=z['ort_'+name];repeat=z['repeat_'+name]
                assert np.array_equal(ref,original[key]) and np.isfinite(out).all() and ref.shape==out.shape and np.array_equal(out,repeat)
                errors.append(float(np.max(np.abs(ref.astype(np.float64)-out))))
        passed=max(errors)<=1e-5
        assert passed==(r['status']=='CACHE_TIE_GRAPH_PASS_REVIEW_REQUIRED') and w['exit_code']==int(not passed)
        status='PASS_ONE_HOST_CACHE_TIE_GRAPH_CASE_ONLY' if passed else 'REVIEWED_CACHE_TIE_GRAPH_NUMERICAL_MISMATCH'
    size=sum(f.stat().st_size for f in ROOT.rglob('*') if f.is_file());assert size<a['output_max_bytes']
    report=dict(status=status,max_abs=errors,absolute_tolerance=1e-5,exact_owners_closed=True,natural_exit_code=w['exit_code'],output_bytes=size,graph_bytes=(ROOT/'cache_compression.onnx').stat().st_size,finite_tie_reproduced=True,rejection_atomicity_verified=True,native_pi_qualified=False,complete_driver=False,hashes={n:sha(ROOT/n) for n in docs})
    with (ROOT/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--version',type=int,choices=[1,2],required=True);review(p.parse_args().version)
