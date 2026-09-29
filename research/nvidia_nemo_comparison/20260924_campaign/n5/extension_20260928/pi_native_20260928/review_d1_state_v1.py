"""Independent stored-array and closure review. README_REVIEW_D1_STATE_V1.md."""
import hashlib,json
from pathlib import Path
import numpy as np
import psutil

ROOT=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/d1-onnx-state-v1')


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    psutil.Process().cpu_affinity([14])
    docs={n:json.loads((ROOT/n).read_text(encoding='utf-8')) for n in ['ADMISSION.json','RESULT.json','GUARD_RESULT.json','JOB_ENVELOPE.json','MODEL_OWNER.json','REGISTERED_OWNER.json','supervision/worker.json']}
    a=docs['ADMISSION.json'];r=docs['RESULT.json'];g=docs['GUARD_RESULT.json'];w=docs['supervision/worker.json'];j=docs['JOB_ENVELOPE.json']
    assert r['status']=='FAILED_PRESERVED' and w['status']=='FAILED' and w['exit_code']==1
    assert g['status']=='WORKER_EXITED_REVIEW_REQUIRED' and g['seconds']<600
    life=g['lifetime'];assert life['status']=='OWNED_PROCESS_LIFETIME_CLOSED' and not life['forced'] and life['root_exit_code']==1
    assert life['job_empty_verified'] and life['observed_members_exited'] and life['input_desktop_before']==life['input_desktop_after']
    owners=[dict(pid=w['pid'],create_time=w['create_time']),dict(pid=w['child_pid'],create_time=w['child_create_time']),docs['MODEL_OWNER.json'],docs['REGISTERED_OWNER.json']['owner']]
    for o in owners:
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    assert j['hard_job_commit_bytes']==a['hard_job_commit_bytes']==6*1024**3
    assert j['affinity']==docs['MODEL_OWNER.json']['affinity']==a['model_cpus']==[4,14]
    assert j['max_processes']==16 and j['kill_on_close'] and a['threads']==1 and not a['gpu']
    for b in a['bindings']:assert sha(b['path'])==b['sha256']
    assert a['absolute_tolerance']==1e-5 and r['error']=="AmbiguousSelection('Finite score tie crosses top-k boundary')"
    filenames=[x['case']+'-'+str(x['step'])+'.npz' for x in r['cases']]
    checks=[]
    for filename,entry in zip(filenames,r['cases']):
        with np.load(ROOT/filename,allow_pickle=False) as z:
            cap,refresh,offset,left,right=map(int,z['parameters'])
            assert cap in [0,80] and refresh in [40,188] and offset==entry['offset']
            assert z['chunk'].dtype==np.float32 and z['predictions'].dtype==np.float32
            deltas=[]
            for name in ['chunk','cache','cache_probs','fifo','fifo_probs']:
                ref=z['reference_'+name];got=z['candidate_'+name]
                assert ref.shape==got.shape and np.isfinite(ref).all() and np.isfinite(got).all()
                delta=float(np.max(np.abs(ref.astype(np.float64)-got))) if ref.size else 0.
                assert delta<=1e-5;deltas.append(delta)
            assert len(z['candidate_cache'])<=264 and len(z['candidate_fifo'])<=cap
            assert np.array_equal(z['candidate_chunk'],z['reference_chunk'])
            checks.append(dict(file=filename,offset=offset,new_frames=len(z['reference_chunk']),max_abs=deltas,cache_frames=len(z['reference_cache']),fifo_frames=len(z['reference_fifo'])))
    assert len(checks)==len(r['cases'])==14
    size=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file());assert size<a['output_max_bytes']
    review=dict(status='REVIEWED_14_STATE_UPDATES_THEN_OVERLAP_TIE_REJECTION',cases=checks,absolute_tolerance=1e-5,
        source_bindings_verified=True,hard_job_commit_bytes=j['hard_job_commit_bytes'],actual_affinity=[4,14],exact_owners_closed=True,natural_exit_code=1,
        output_bytes=size,output_bound_bytes=a['output_max_bytes'],host_only=True,native_pi_qualified=False,
        ordered_state_candidate=True,finite_ties_supported=False,finite_tie_rejection_verified=True,failed_update_atomicity_not_observed=True,complete_protocol_pass=False,complete_streaming_driver=False,speedup_qualified=False,stage_acceptance=False,
        resource_caveat='Root launcher RSS is not aggregate model peak.',hashes={n:sha(ROOT/n) for n in docs})
    with (ROOT/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(review,f,indent=2)
    print(json.dumps({k:review[k] for k in ['status','cases','output_bytes','exact_owners_closed']}))


if __name__=='__main__':main()
