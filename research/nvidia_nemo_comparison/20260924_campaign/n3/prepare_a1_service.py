"""Create the bounded portable A1 export/parity plan; README_A1_PORTABLE.md."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from reuse_results import bound,load


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent-plan',type=Path,required=True);p.add_argument('--version',required=True)
    args=p.parse_args()
    if not args.version.isalnum():raise ValueError('Alphanumeric fresh version required')
    parent=load(args.parent_plan);root=args.parent_plan.resolve().parent;here=Path(__file__).resolve().parent
    export=next(j for j in parent['jobs'] if j['id']=='A1-export');argv=export['argv']
    model=argv[argv.index('--model')+1];source=argv[argv.index('--source')+1]
    probe=next(j for j in parent['jobs'] if j['id']=='cpu-panel-A2')['argv']
    audio=probe[probe.index('--audio-manifest')+1]
    if len(load(audio)['jobs'])!=4:raise ValueError('Expected the fixed four-cell panel')
    output=root/('numerical-'+args.version);plan=root/('plan-'+args.version+'.json');worker=root/('worker-'+args.version+'.json')
    if any(p.exists() for p in (output,plan,worker)):raise ValueError('Use fresh outputs')
    worker_document=load(parent['worker_spec'])
    worker_document['argv']=[worker_document['argv'][0],'-B',str(here/'supervise_n3.py'),'run','--plan',str(plan)]
    worker.write_text(json.dumps(worker_document,indent=2)+'\n',encoding='utf-8')
    bundle=output/'bundle';check=output/'parity'
    common=['--model',model,'--source',source]
    jobs=[dict(id='A1-service-export',argv=[argv[0],'-B',str(here/'export_a1_service.py'),*common,'--output',str(bundle)],
        result=str(bundle/'RESULT.json'),depends_on=[],gpu=False,timeout_seconds=1800,
        accepted_status=['EXPORTED_SERVICE_BUNDLE_NOT_QUALIFIED']),
        dict(id='A1-service-parity',argv=[argv[0],'-B',str(here/'check_a1_service.py'),*common,'--bundle',str(bundle),
            '--audio-manifest',audio,'--output',str(check)],result=str(check/'RESULT.json'),
            depends_on=['A1-service-export'],gpu=False,timeout_seconds=1800,accepted_status=['PASS_SERVICE_PARITY'])]
    bindings={r['path']:r for r in parent['bindings']}
    for p in [args.parent_plan,worker,*[here/n for n in ('prepare_a1_service.py','export_a1_service.py','check_a1_service.py','a1_onnx.py','test_a1_onnx.py','diagnose_a1_parity.py')]]:
        b=bound(p);bindings[b['path']]=b
    document=dict(parent,created_utc=datetime.now(timezone.utc).isoformat(),output=str(output),worker_spec=str(worker),
        jobs=jobs,bindings=list(bindings.values()),purpose='Actual 80-ms A1 ONNX service and strict fresh-reference saved-audio parity',
        scope='Bounded CPU component diagnostic; no performance, integrated GUI, ARM64 or CM5 qualification')
    plan.write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='PREPARED_NOT_STARTED',plan=bound(plan),jobs=2)))


if __name__=='__main__':main()
