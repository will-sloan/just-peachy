"""Read retained projection arrays independently; README_REVIEW_D1_PROJECTION_V1.md."""
import hashlib,json,math,os
from pathlib import Path
import psutil

ROOT=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/d1-onnx-projection-v1')


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    psutil.Process().cpu_affinity([14])
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='-1'
    import numpy as np,onnx
    r=ROOT;names=['ADMISSION.json','RESULT.json','GUARD_RESULT.json','JOB_ENVELOPE.json','MODEL_OWNER.json','REGISTERED_OWNER.json','supervision/worker.json','GRAPH.json']
    docs={n:json.loads((r/n).read_text()) for n in names};a=docs['ADMISSION.json'];v=docs['RESULT.json'];g=docs['GUARD_RESULT.json'];w=docs['supervision/worker.json'];j=docs['JOB_ENVELOPE.json'];info=docs['GRAPH.json']
    for b in a['bindings']:assert sha(b['path'])==b['sha256']
    life=g['lifetime'];assert life['status']=='OWNED_PROCESS_LIFETIME_CLOSED' and not life['forced'] and life['job_empty_verified'] and life['observed_members_exited']
    assert life['input_desktop_before']==life['input_desktop_after'] and life['root_exit_code']==w['exit_code']==0 and w['status']=='COMPLETED'
    owners=[dict(pid=w[k],create_time=w[t]) for k,t in [('pid','create_time'),('child_pid','child_create_time')]]+[docs['MODEL_OWNER.json'],docs['REGISTERED_OWNER.json']['owner']]
    for o in owners:
        try:assert abs(psutil.Process(o['pid']).create_time()-o['create_time'])>.001
        except psutil.NoSuchProcess:pass
    assert j['hard_job_commit_bytes']==a['hard_job_commit_bytes']==6*1024**3 and j['affinity']==a['model_cpus']==docs['MODEL_OWNER.json']['affinity']==[4,14]
    assert a['threads']==1 and not a['gpu'] and a['absolute_tolerance']==1e-5 and a['output_max_bytes']==32*1024**2 and g['seconds']<600
    assert v['status']=='PROJECTION_ISOLATION_OBSERVATIONS_REVIEW_REQUIRED' and len(v['cases'])==4
    assert not v['checkpoint_files_extracted'] and not v['precision_gate_changed'] and not v['waveform_accepted'] and not v['native_pi_qualified']
    assert not list(r.rglob('*.ckpt')) and not list(r.rglob('*.nemo'))
    weight=np.load(r/'projection_weight.npy');assert weight.shape==(512,1024) and weight.dtype==np.float32
    for path in [Path(a['graph']),r/'preencoder.onnx']:
        graph=onnx.load(path,load_external_data=False)
        node=next(n for n in graph.graph.node if 'chunk_pre_encode_embs' in n.output);assert node.op_type=='MatMul'
        init=next(x for x in graph.graph.initializer if x.name==node.input[1]);assert np.array_equal(onnx.numpy_helper.to_array(init),weight.T)
        if path.name=='preencoder.onnx':
            assert sum(n.op_type=='MatMul' for n in graph.graph.node)==1
            assert [x.name for x in graph.graph.input]==['chunk','chunk_lengths']
            assert [x.name for x in graph.graph.output]==['chunk_pre_encode_embs','chunk_pre_encode_lengths',node.input[0]]
        del graph
    assert info['graph_sha256']==sha(r/'preencoder.onnx') and info['original_graph_sha256']==sha(a['graph'])
    assert (r/'preencoder.onnx').stat().st_size==info['bytes']==v['subgraph_bytes']<4*1024**2
    fixtures=r.parent/'d1-onnx-frontend-v1';parent=r.parent/'d1-onnx-waveform-v2'
    specs=[('tail','tail',0,8,0),('full_first','full',0,2120,1),('full_middle','full',2104,4232,1),('full_tail','full',4216,4469,0)]
    checks=[]
    for index,(name,source,start,end,right) in enumerate(specs):
        row=v['cases'][index];assert row['case']==name
        with np.load(fixtures/(source+'.npz')) as f:chunk=f['reference'][0,:,start:end].T.copy()
        with np.load(r/(name+'.npz')) as z:
            assert np.array_equal(chunk,z['chunk']) and np.isfinite(chunk).all()
            pad=(-len(chunk))%8;stack=np.concatenate([chunk,np.zeros((pad,128),np.float32)],axis=0).reshape(1,-1,1024)
            assert np.array_equal(stack,z['stack']) and np.array_equal(z['lengths'],np.array([(len(chunk)+7)//8],np.int64))
            assert z['pytorch'].shape==z['basic'].shape==z['disabled'].shape==(1,len(stack[0]),512)
            assert np.array_equal(z['basic'],z['disabled'])
            deltas={label:float(np.abs(z[label].astype(np.float64)-z['pytorch'].astype(np.float64)).max()) for label in ['basic','disabled']}
            for label,delta in deltas.items():
                assert delta==row['paths'][label]['max_abs'] and (delta<=1e-5)==row['paths'][label]['within_unchanged_gate']
                assert row['paths'][label]['stack_exact'] and row['paths'][label]['lengths_exact'] and row['paths'][label]['repeat_exact']
                assert np.isfinite(z[label]).all()
                assert float(np.abs(z[label].astype(np.float64)-z['float64_accumulation']).max())==row['paths'][label]['versus_float64_maxabs']
            assert float(np.abs(z['pytorch'].astype(np.float64)-z['float64_accumulation']).max())==row['pytorch_vs_float64_maxabs']
            # Check one worst-discrepancy dot product independently with scalar fsum.
            _,t,c=np.unravel_index(np.argmax(np.abs(z['basic'].astype(np.float64)-z['pytorch'].astype(np.float64))),z['basic'].shape)
            direct=math.fsum(float(x)*float(y) for x,y in zip(stack[0,t],weight[c]))
            assert abs(direct-float(z['float64_accumulation'][0,t,c]))<1e-10
            if name in ['tail','full_first']:
                with np.load(parent/(source+'-reference.npz')) as ref:retained=ref['0_spkcache'].copy()
                assert np.array_equal(retained,z['retained_first_cache']) and np.array_equal(retained,z['pytorch'][:,:z['pytorch'].shape[1]-right if right else None])
                assert row['pytorch_vs_retained_first_cache_maxabs']==0
                if name=='tail':
                    with np.load(r.parent/'d1-onnx-feature-isolation-v1/tail-0.npz') as old:assert np.array_equal(old['cache'],z['basic'][0])
            checks.append(dict(case=name,feature_frames=len(chunk),stack_exact=True,weight_exact=True,lengths_exact=True,basic_disabled_exact=True,projection_maxabs=deltas['basic'],within_state_gate=deltas['basic']<=1e-5,scalar_float64_check=True,original_first_cache_exact=name in ['tail','full_first']))
    size=sum(p.stat().st_size for p in r.rglob('*') if p.is_file());assert size<a['output_max_bytes']
    out=dict(status='REVIEWED_NATURAL_FEATURE_MATMUL_MISMATCH_LOCALIZED_ONLY',cases=checks,subgraph_bytes=info['bytes'],output_bytes=size,seconds=v['seconds'],
             exact_owners_closed=True,natural_exit_code=0,projection_arithmetic_mismatch_established=True,stack_padding_lengths_explain_mismatch=False,
             basic_optimization_toggle_repairs_mismatch=False,all_downstream_errors_explained=False,absolute_tolerance=1e-5,gate_relaxed=False,
             waveform_accepted=False,native_pi_qualified=False,speedup_qualified=False,hashes={n:sha(r/n) for n in names+['preencoder.onnx','projection_weight.npy']})
    with (r/'REVIEW.json').open('x') as f:json.dump(out,f,indent=2)
    print(json.dumps({k:x for k,x in out.items() if k!='hashes'}))


if __name__=='__main__':main()
