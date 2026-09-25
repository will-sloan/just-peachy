"""Admit a fresh deterministic portable A1 screen after actual parity; README_A1_SCREEN.md."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from reuse_results import bound,load


def original_job(parent,key):
    job=next(j for j in parent['jobs'] if j['id']==key)
    if job.get('execution')=='REUSE_VERIFIED_PRIOR_EVIDENCE_NO_INFERENCE':
        path=Path(job['argv'][job['argv'].index('--manifest')+1])
        expected=next(b for b in parent['bindings'] if b['path']==str(path))
        if bound(path)!=expected:raise ValueError('Original reuse mapping changed')
        prior=load(path)['previous_plan']
        if bound(prior['path'])!=prior:raise ValueError('Original plan changed')
        job=next(j for j in load(prior['path'])['jobs'] if j['id']==key)
    if '--audio-manifest' not in job['argv']:raise ValueError('Expected one resolved original inference job')
    return job


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent-plan','service-plan'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--version',required=True);args=p.parse_args()
    if not args.version.isalnum():raise ValueError('Alphanumeric version required')
    parent=load(args.parent_plan);service=load(args.service_plan)
    terminal=Path(service['output'])/'RESULT.json';completion=load(terminal)
    parity=Path(service['output'])/'parity/RESULT.json';check=load(parity)
    if (completion['status']!='READY_FOR_REVIEW' or completion['plan_sha256']!=bound(args.service_plan)['sha256'] or
        not completion.get('numerical_jobs_passed') or check['status']!='PASS_SERVICE_PARITY' or not check['host_service_qualified']):
        raise ValueError('Exact service export and actual parity must pass first')
    if completion['jobs']['A1-service-parity']['result']['sha256']!=bound(parity)['sha256']:
        raise ValueError('Parity receipt changed')
    bundle=Path(service['output'])/'bundle';manifest=load(bundle/'BUNDLE.json')
    if bound(bundle/'BUNDLE.json')['sha256']!=check['bundle_sha256']:raise ValueError('Different bundle was tested')
    if len(check['cases'])!=5 or any(r['status']!='PASS' for r in check['cases']):raise ValueError('Incomplete actual parity population')
    here=Path(__file__).resolve().parent;root=args.parent_plan.resolve().parent
    output=root/('numerical-'+args.version);plan=root/('plan-'+args.version+'.json');worker=root/('worker-'+args.version+'.json')
    if any(p.exists() for p in (output,plan,worker)):raise ValueError('Use fresh outputs')
    worker_document=load(parent['worker_spec']);python=worker_document['argv'][0]
    worker_document['argv']=[python,'-B',str(here/'supervise_n3.py'),'run','--plan',str(plan)]
    worker.write_text(json.dumps(worker_document,indent=2)+'\n',encoding='utf-8')
    prototype=next(j for j in parent['jobs'] if j['id']=='screen-A2')['argv']
    source=prototype[prototype.index('--prototype')+1];models=prototype[prototype.index('--models-root')+1]
    def old_audio(key):
        a=original_job(parent,key)['argv'];path=a[a.index('--audio-manifest')+1]
        lock=load(Path(parent['output'])/key/'RUN_LOCK.json')
        if bound(path)['sha256']!=lock['audio_manifest_sha256']:raise ValueError('Original audio population changed')
        return path
    common=[python,'-B',str(here/'run_asr_a1.py'),'--prototype',source,'--models-root',models,
        '--variant','A1','--runtime','onnx','--binding',str(bundle/'BUNDLE.json'),'--right-context','1','--cpu','4']
    jobs=[]
    for name,old,count,extra,dependencies in [('smoke-A1-onnx','screen-A1',2,['--limit','2'],[]),
        ('screen-A1-onnx','screen-A1',96,[],['smoke-A1-onnx']),
        ('regression-A1-onnx','regression-A1',8,[],['smoke-A1-onnx']),
        ('paced-A1-onnx','paced-A1',4,['--paced'],['smoke-A1-onnx'])]:
        jobs.append(dict(id=name,argv=[*common,'--audio-manifest',old_audio(old),'--output',str(output/name),*extra],
            result=str(output/name/'RESULT.json'),expected_cells=count,depends_on=dependencies,gpu=False,timeout_seconds=14400))
    for key,subfolder in [('lexical-comparison','analysis'),('text-comparison','text')]:
        old=next(j for j in parent['jobs'] if j['id']==key);job=dict(old);argv=list(old['argv'])
        argv[argv.index('--output')+1]=str(output/subfolder)
        old_a1=str(Path(parent['output'])/'screen-A1')
        if argv.count(old_a1)!=1:raise ValueError('Comparison requires one exact A1 replacement')
        argv[argv.index(old_a1)]=str(output/'screen-A1-onnx')
        job.update(argv=argv,result=str(output/subfolder/Path(old['result']).name),depends_on=['screen-A1-onnx']);jobs.append(job)
    bindings={r['path']:r for r in service['bindings']}
    for b in parent['bindings']:bindings[b['path']]=b
    additions=[args.parent_plan,args.service_plan,terminal,parity,worker,bundle/'BUNDLE.json',
        *[Path(old_audio(k)) for k in ('screen-A1','regression-A1','paced-A1')],
        *[bundle/r['name'] for r in manifest['files']],
        *[here/n for n in ('prepare_a1_screen.py','run_asr_a1.py','test_a1_stream.py')]]
    for path in additions:
        b=bound(path);bindings[b['path']]=b
    # Score only the unchanged A0/A2/A3 runs after binding their original cells.
    for variant in ('A0','A2','A3'):
        run=Path(parent['output'])/('screen-'+variant);r=load(run/'RESULT.json')
        if r['status']!='COMPLETE' or r['completed']!=96:raise ValueError('Upstream comparator incomplete')
        for path in [run/'RESULT.json',run/'RUN_LOCK.json',*[Path(c['path']) for c in r['cells']]]:
            b=bound(path);bindings[b['path']]=b
    document=dict(parent,created_utc=datetime.now(timezone.utc).isoformat(),output=str(output),worker_spec=str(worker),jobs=jobs,
        bindings=list(bindings.values()),purpose='Actual A1 portable nominal screen and app-runtime checks with inference-only frontend',
        old_A1_reference='Preserved as historical training-mode-dither route; no predictions reused',
        GUI_scope='No GUI or target performance claims; separate six-cell native GUI audit continues')
    plan.write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='PREPARED_NOT_STARTED',plan=bound(plan),jobs=len(jobs))))


if __name__=='__main__':main()
