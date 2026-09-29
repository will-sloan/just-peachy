"""Independent stored-array and closure review. README_REVIEW_D1_ONNX_EXPORT_V4.md."""
import hashlib,json
from pathlib import Path
import numpy as np
import psutil

ROOT=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/d1-onnx-export-v4')


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    psutil.Process().cpu_affinity([14])
    docs={n:json.loads((ROOT/n).read_text(encoding='utf-8')) for n in ['ADMISSION.json','RESULT.json','GUARD_RESULT.json','JOB_ENVELOPE.json','MODEL_OWNER.json','REGISTERED_OWNER.json','supervision/worker.json','GRAPH.json','FRONTEND.json']}
    a=docs['ADMISSION.json'];r=docs['RESULT.json'];g=docs['GUARD_RESULT.json'];w=docs['supervision/worker.json'];j=docs['JOB_ENVELOPE.json']
    assert r['status']=='EXPORTED_GRAPH_THREE_CASES_REVIEW_REQUIRED' and w['status']=='COMPLETED' and w['exit_code']==0
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
    graph=docs['GRAPH.json'];assert sha(ROOT/'sortformer_highres_fp32.onnx')==graph['sha256']==r['graph_sha256']
    assert set(graph['inputs'])=={'chunk','chunk_lengths','spkcache','spkcache_lengths','fifo','fifo_lengths'}
    assert graph['outputs']==['spkcache_fifo_chunk_preds','chunk_pre_encode_embs','chunk_pre_encode_lengths','high_resolution_preds']
    assert all(n.startswith('ai.onnx:') for n in graph['operators'])
    checks=[]
    for name in ['delayed_warm','cold_short','dynamic_tail']:
        with np.load(ROOT/(name+'.npz'),allow_pickle=False) as z,np.load(ROOT/('attention_'+name+'.npz'),allow_pickle=False) as attention:
            deltas=[];adapter_deltas=[]
            for i in range(4):
                ref=z['reference_'+str(i)];actual=z['ort_'+str(i)]
                assert np.isfinite(ref).all() and np.isfinite(actual).all() and ref.shape==actual.shape
                assert np.array_equal(ref,attention['reference_'+str(i)])
                delta=float(np.max(np.abs(ref.astype('float64')-actual))) if ref.size else 0.0
                adapted=attention['adapted_'+str(i)];assert np.isfinite(adapted).all() and adapted.shape==ref.shape
                adelta=float(np.max(np.abs(ref.astype('float64')-adapted))) if ref.size else 0.0
                assert delta<=1e-5 and adelta<=1e-5
                assert np.array_equal(actual,z['repeat_'+str(i)])
                if i==2:assert delta==adelta==0
                deltas.append(delta);adapter_deltas.append(adelta)
            checks.append(dict(case=name,ort_max_abs=deltas,adapter_max_abs=adapter_deltas,feature_frames=int(z['input_chunk'].shape[1]),cache_frames=int(z['input_spkcache'].shape[1]),fifo_frames=int(z['input_fifo'].shape[1])))
    assert [x['feature_frames'] for x in checks]==[2128,32,17]
    size=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file());assert size<a['output_max_bytes']
    review=dict(status='PASS_HIGH_RESOLUTION_FP32_THREE_FEATURE_CASES_REPEAT_AND_CLOSURE_ONLY',cases=checks,absolute_tolerance=1e-5,
        graph_sha256=graph['sha256'],graph_bytes=graph['bytes'],operators=graph['operators'],source_bindings_verified=True,
        hard_job_commit_bytes=j['hard_job_commit_bytes'],actual_affinity=[4,14],exact_owners_closed=True,natural_exit_code=0,
        output_bytes=size,output_bound_bytes=a['output_max_bytes'],host_only=True,native_pi_qualified=False,
        high_resolution_output_preserved=True,portable_waveform_frontend=False,complete_streaming_driver=False,
        original_q8_numerical_equivalence=False,speedup_qualified=False,stage_acceptance=False,
        resource_caveat='Guard samples root launcher RSS, not aggregate model peak; hard job committed-memory limit covers members.',
        hashes={n:sha(ROOT/n) for n in docs})
    with (ROOT/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(review,f,indent=2)
    print(json.dumps({k:review[k] for k in ['status','cases','graph_bytes','output_bytes','exact_owners_closed']}))


if __name__=='__main__':main()
