"""Independent feature isolation review; README_REVIEW_D1_FEATURE_ISOLATION_V1.md."""
import hashlib,json
from pathlib import Path
import numpy as np
import psutil
ROOT=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/d1-onnx-feature-isolation-v1')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    psutil.Process().cpu_affinity([14]);r=ROOT
    names=['ADMISSION.json','RESULT.json','GUARD_RESULT.json','JOB_ENVELOPE.json','MODEL_OWNER.json','REGISTERED_OWNER.json','supervision/worker.json']
    docs={n:json.loads((r/n).read_text()) for n in names};a=docs['ADMISSION.json'];v=docs['RESULT.json'];g=docs['GUARD_RESULT.json'];w=docs['supervision/worker.json'];j=docs['JOB_ENVELOPE.json']
    for b in a['bindings']:assert sha(b['path'])==b['sha256']
    life=g['lifetime'];assert life['status']=='OWNED_PROCESS_LIFETIME_CLOSED' and not life['forced'] and life['job_empty_verified'] and life['observed_members_exited']
    assert life['input_desktop_before']==life['input_desktop_after'] and life['root_exit_code']==w['exit_code']==0 and w['status']=='COMPLETED'
    owners=[dict(pid=w[k],create_time=w[t]) for k,t in [('pid','create_time'),('child_pid','child_create_time')]]+[docs['MODEL_OWNER.json'],docs['REGISTERED_OWNER.json']['owner']]
    for o in owners:
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    assert j['hard_job_commit_bytes']==a['hard_job_commit_bytes']==6*1024**3 and j['affinity']==a['model_cpus']==docs['MODEL_OWNER.json']['affinity']==[4,14]
    assert a['threads']==1 and not a['gpu'] and a['absolute_tolerance']==1e-5 and a['output_max_bytes']==32*1024**2 and g['seconds']<600
    assert v['status']=='FEATURE_ISOLATION_OBSERVATIONS_REVIEW_REQUIRED' and len(v['cases'])==4
    parent=r.parent/'d1-onnx-waveform-v2';fixtures=r.parent/'d1-onnx-frontend-v1';checks=[];hashes={n:sha(r/n) for n in names}
    fields={'cache':'spkcache','cache_probs':'spkcache_preds','fifo':'fifo','fifo_probs':'fifo_preds'}
    for name in ['tail','full']:
        refpath=parent/(name+'-reference.npz');meta=json.loads((parent/(name+'-reference.json')).read_text());last=len(meta['chunks'])-1
        with np.load(refpath) as ref,np.load(fixtures/(name+'.npz')) as fixture:
            assert np.array_equal(fixture['audio'],ref['audio']);n=len(ref['audio'])//160
            assert fixture['reference'].shape[-1]>=n and ref['probabilities'].shape==(n,8)
            for repetition in range(2):
                row=next(x for x in v['cases'] if x['case']==name and x['repetition']==repetition);path=r/(name+'-'+str(repetition)+'.npz');hashes[path.name]=sha(path)
                with np.load(path) as got:
                    assert got['probabilities'].shape==(n,8) and np.isfinite(got['probabilities']).all()
                    delta=float(np.max(np.abs(got['probabilities'].astype('float64')-ref['probabilities'].astype('float64'))));states={}
                    for field,label in fields.items():
                        truth=ref[str(last)+'_'+label][0];actual=got[field];assert actual.shape==truth.shape and np.isfinite(actual).all()
                        states[field]=float(np.max(np.abs(actual.astype('float64')-truth.astype('float64')))) if actual.size else 0.0
                    assert delta==row['max_abs'] and states==row['state_max_abs']
                    accepted=delta<=1e-5 and max(states.values())<=1e-5;assert accepted==row['within_unchanged_gate']
                    origin=0
                    for entry in row['trace']:
                        assert entry['feature_start']==origin and entry['emitted_rows']==entry['feature_end']-origin
                        assert entry['cache_rows']<=264 and entry['fifo_rows']==0 and 0<=entry['trimmed_coarse_padding']<8
                        origin=entry['feature_end']
                    assert origin==n
                    if repetition:
                        with np.load(r/(name+'-0.npz')) as first:
                            assert all(np.array_equal(first[k],got[k]) for k in got.files)
                    checks.append(dict(case=name,repetition=repetition,frames=n,probability_max_abs=delta,final_state_max_abs=states,within_unchanged_gate=accepted))
        hashes[str(refpath)]=sha(refpath);hashes[str(fixtures/(name+'.npz'))]=sha(fixtures/(name+'.npz'))
    size=sum(x.stat().st_size for x in r.rglob('*') if x.is_file());assert size<a['output_max_bytes']
    out=dict(status='REVIEWED_EXACT_FEATURE_GRAPH_STATE_MISMATCH_ONLY',cases=checks,all_repeats_exact=True,absolute_tolerance=1e-5,exact_owners_closed=True,natural_exit_code=0,output_bytes=size,output_bound_bytes=a['output_max_bytes'],frontend_alone_explains_mismatch=False,precise_graph_operator_cause_established=False,waveform_accepted=False,native_pi_qualified=False,speedup_qualified=False,hashes=hashes)
    with (r/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
    print(json.dumps({k:x for k,x in out.items() if k!='hashes'}))
if __name__=='__main__':main()
