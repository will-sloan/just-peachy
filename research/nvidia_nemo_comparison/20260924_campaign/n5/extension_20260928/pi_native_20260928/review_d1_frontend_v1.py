"""Independent stored-array and closure review. README_REVIEW_D1_FRONTEND_V1.md."""
import hashlib,json
from pathlib import Path
import numpy as np
import psutil

ROOT=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/d1-onnx-frontend-v1')


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    psutil.Process().cpu_affinity([14])
    docs={n:json.loads((ROOT/n).read_text(encoding='utf-8')) for n in ['ADMISSION.json','RESULT.json','GUARD_RESULT.json','JOB_ENVELOPE.json','MODEL_OWNER.json','REGISTERED_OWNER.json','supervision/worker.json']}
    a=docs['ADMISSION.json'];r=docs['RESULT.json'];g=docs['GUARD_RESULT.json'];w=docs['supervision/worker.json'];j=docs['JOB_ENVELOPE.json']
    assert r['status']=='FRONTEND_REFERENCE_CASES_REVIEW_REQUIRED' and w['status']=='COMPLETED' and w['exit_code']==0
    assert g['status']=='WORKER_EXITED_REVIEW_REQUIRED' and g['seconds']<600
    life=g['lifetime'];assert life['status']=='OWNED_PROCESS_LIFETIME_CLOSED' and not life['forced'] and life['root_exit_code']==0
    assert life['job_empty_verified'] and life['observed_members_exited'] and life['input_desktop_before']==life['input_desktop_after']
    owners=[dict(pid=w['pid'],create_time=w['create_time']),dict(pid=w['child_pid'],create_time=w['child_create_time']),docs['MODEL_OWNER.json'],docs['REGISTERED_OWNER.json']['owner']]
    for o in owners:
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    assert j['hard_job_commit_bytes']==a['hard_job_commit_bytes']==6*1024**3
    assert j['affinity']==docs['MODEL_OWNER.json']['affinity']==a['model_cpus']==[4,14]
    assert j['max_processes']==16 and j['kill_on_close'] and a['threads']==1 and not a['gpu']
    for b in a['bindings']:assert sha(b['path'])==b['sha256']
    assert a['absolute_tolerance']==1e-4 and r['invalid_cases_rejected']==4
    checks=[]
    for name in ['empty','one','hop_minus','hop_exact','hop_plus','tail','full','zero','impulse']:
        with np.load(ROOT/(name+'.npz'),allow_pickle=False) as z:
            n=len(z['audio']);valid=n//160;reference=z['reference']
            assert z['length'].tolist()==[valid] and reference.shape==(1,128,((valid+1+15)//16)*16)
            assert np.isfinite(z['audio']).all() and np.isfinite(reference).all()
            deltas=[]
            for mode in ['fixed','irregular','repeat']:
                got=z[mode];assert got.shape==reference.shape and np.isfinite(got).all()
                delta=float(np.max(np.abs(got.astype(np.float64)-reference)))
                assert delta<=1e-4 and np.count_nonzero(got[:,:,valid:])==0
                deltas.append(delta)
            assert np.array_equal(z['fixed'],z['repeat'])
            checks.append(dict(case=name,samples=n,valid_frames=valid,max_abs=deltas,repeat_exact=True))
    assert [x['samples'] for x in checks]==[0,1,159,160,161,1281,715127,3201,1600]
    size=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file());assert size<a['output_max_bytes']
    review=dict(status='PASS_HOST_FRONTEND_FULL_EDGE_IRREGULAR_REFERENCE_ONLY',cases=checks,absolute_tolerance=1e-4,
        source_bindings_verified=True,hard_job_commit_bytes=j['hard_job_commit_bytes'],actual_affinity=[4,14],exact_owners_closed=True,natural_exit_code=0,
        output_bytes=size,output_bound_bytes=a['output_max_bytes'],host_only=True,native_pi_qualified=False,
        portable_frontend_candidate=True,complete_streaming_driver=False,speedup_qualified=False,stage_acceptance=False,
        resource_caveat='Root launcher RSS is not aggregate model peak.',hashes={n:sha(ROOT/n) for n in docs})
    with (ROOT/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(review,f,indent=2)
    print(json.dumps({k:review[k] for k in ['status','cases','output_bytes','exact_owners_closed']}))


if __name__=='__main__':main()
