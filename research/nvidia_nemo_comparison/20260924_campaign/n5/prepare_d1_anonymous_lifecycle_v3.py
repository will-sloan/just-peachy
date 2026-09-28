"""Admit one saved-file A2 Windows check. See README_D1_ANONYMOUS_LIFECYCLE_V3.md."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'n4'))
from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from guarded_execution_v1 import snapshot
from reservation_budget_v1 import calculate
from paced_slot import process_census, competitors


def prepare(name, arm, reference):
    mode="anonymous_conversation"
    import psutil
    own=identity(pin()); local=HERE.parents[4]/'local'
    assert re.fullmatch(r'd1-anonymous-lifecycle-[a-z0-9-]+',name), 'Bounded run name required'
    assert mode in ('caption_only','anonymous_conversation')
    output=local/'n5'/name; pre=local/'n5'/(name+'-precheck')
    assert not output.exists() and not pre.exists(), 'Fresh names required'
    prior=load(local/'n5/baseline-windows-lifecycle-v1/ADMISSION.json')
    n3=load(HERE.parent/'n3/N3_ACCEPTED_CONFIGS.json')
    parent_source_receipt=n3['source_receipt']; verify(parent_source_receipt)
    source_receipt=(bind(local/'releases/d1-anonymous-v1/DERIVATIVE.json') if arm=='candidate' else parent_source_receipt)
    verify(source_receipt)
    receipt=load(source_receipt['path']); release=Path(source_receipt['path']).parent/'prototype'
    reference_inputs=[]
    if arm=='candidate':
        assert receipt['parent_source_receipt']==parent_source_receipt
        assert reference is not None, 'Candidate requires paired parent evidence'
        reference=Path(reference).resolve(strict=True)
        result=load(reference); ra=load(reference.parent/'ADMISSION.json')
        assert result['status']=='PASS_NEMOTRON_WINDOWS_LIFECYCLE_SMOKE' and ra['arm']=='parent'
        assert ra['source_receipt']==parent_source_receipt
        reference_inputs=[bind(reference),bind(reference.parent/'infer/RESULT.json'),bind(reference.parent/'ADMISSION.json')]
        from d1_anonymous_lifecycle_v3 import acceptance,bypass_acceptance
        for phase in result['phases']:
            verify(phase['result']);verify(phase['lifetime'])
            acceptance(load(phase['result']['path']),load(phase['lifetime']['path']))
            reference_inputs += [phase['result'],phase['lifetime']]
        bypass_acceptance(load(reference_inputs[1]['path']),'parent')
        assert all(exact_process(o) is None for o in [ra['owner'],{k:ra['supervisor'][k] for k in ('pid','create_time')}])
    else:
        assert arm=='parent' and reference is None

    files=[]
    for relative,row in receipt['files'].items():
        b=dict(path=str(release/relative),**row); verify(b); files.append(b)
    n2=bind(local/'n2/runtime/cpu/n2_runtime.json')
    n3runtime=bind(local/'n3/runtime/v4/cpu/n3_runtime.json')
    expected=load(local/'n3/numerical-guifinalv1/gui-A2/ADMISSION.json')['inputs']
    assert n2==expected['runtime_config'] and n3runtime==expected['n3_runtime_config'], 'Accepted CPU bindings changed'
    d2=load(n2['path']); d3=load(n3runtime['path'])
    assert d2['native_device']==dict(kind='cpu',gpu_index=-1)
    a2=d3['variants']['A2']; assert a2['gpu']==-1 and a2['right_context']==1
    assets=list(prior['assets'])+d2['native_runtime_files']+a2['runtime_files']
    model=bind(a2['model_path']); assert model['sha256']==a2['model_sha256']; assets.append(model)
    model=bind(d2['nemotron_model'])
    assert model['sha256']=='08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1'
    assets.append(model)
    assets=list({b['path']:b for b in assets}.values())
    for b in assets+[prior['audio']]: verify(b)
    code=[bind(HERE/f) for f in ('d1_anonymous_lifecycle_v3.py','test_d1_anonymous_lifecycle_v3.py',
        'prepare_d1_anonymous_lifecycle_v3.py','README_D1_ANONYMOUS_LIFECYCLE_V3.md',
        'test_nemotron_windows_lifecycle_v1.py','nemotron_windows_lifecycle_v1.py',
        'private_application_two_cpu_v1.py','test_d1_anonymous_lifecycle_v1.py','test_d1_anonymous_lifecycle_v2.py')]
    code += [b for b in prior['code'] if Path(b['path']).parent!=HERE]
    for b in code: verify(b)
    observed=snapshot(local,bind(local/'n4/integrated-main-plan-v3.json'))
    assert not observed['active_allocations'], 'Existing active evaluation'
    cap=128*1024**2
    budget=calculate(observed['inventory'],observed['closed_components'],observed['active_allocations'],cap,
        load(observed['policy']['path']),observed['free_bytes'],datetime.now(timezone.utc))
    processes=process_census(local.parent)
    assert not competitors(processes,[own,identity(psutil.Process().parent())]), 'Competing worker exists'
    worker=load(local/'supervision/worker.json')
    closed=[{k:worker[k] for k in ('pid','create_time')}]
    if worker.get('child_pid'):closed.append(dict(pid=worker['child_pid'],create_time=worker['child_create_time']))
    assert all(exact_process(o) is None for o in closed), 'Previous supervisor owner still exists'
    pre.mkdir(); freeze(pre/'CENSUS.json',observed)
    now=datetime.now(timezone.utc); expires=now+timedelta(seconds=600)
    assert expires<datetime(2026,9,28,2,48,19,tzinfo=timezone.utc), 'Packaging reserve cannot be extended'
    check=dict(scope='D1_ANONYMOUS_ENCODER_BYPASS_QUALIFICATION',application_cpus=[4,14],numerical_threads_per_model=1,arm=arm,reference_inputs=reference_inputs,parent_source_receipt=parent_source_receipt,admitted_utc=now.isoformat(),
        expires_utc=expires.isoformat(),code=code,release=str(release),release_files=files,
        source_receipt=source_receipt,acceptance=bind(HERE.parent/'n3/N3_ACCEPTANCE.json'),
        runtime_configs=[n2,n3runtime],models=prior['models'],assets=assets,audio=prior['audio'],
        census=bind(pre/'CENSUS.json'),budget=budget,process_census=processes,closed_prior_owners=closed,
        data=str(output/'data'),output_cap_bytes=cap,sentinel_sha256=hashlib.sha256(b'N5 isolated preservation fixture\n').hexdigest(),
        mode=mode,backend_key='nemotron_600m',N4_accepted=False,N5_complete=False,CM5_tested=False)
    freeze(pre/'CHECK.json',check)
    spec=local/'n5'/(name+'-worker.json')
    freeze(spec,dict(argv=[sys.executable,'-B',str(HERE/'d1_anonymous_lifecycle_v3.py'),
        '--precheck',str(pre/'CHECK.json'),'--output',str(output)],cwd=str(HERE)))
    sys.path.insert(0,str(HERE.parent/'supervision'))
    import supervisor
    started=supervisor.start(local/'supervision',spec)
    freeze(pre/'STARTED.json',dict(check=bind(pre/'CHECK.json'),worker_spec=bind(spec),supervisor=started))
    print({'status':'STARTED_NOT_ACCEPTED','output':str(output),'supervisor':started,'budget':budget})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',required=True)
    parser.add_argument('--arm',required=True,choices=['parent','candidate'])
    parser.add_argument('--reference-result',type=Path)
    args=parser.parse_args(); prepare(args.name,args.arm,args.reference_result)
