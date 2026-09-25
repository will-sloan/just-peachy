"""Retest the same six GUI cells with complete final-state observation; README_GUI_RECOVERY.md."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from reuse_results import bound,load


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent-plan',type=Path,required=True);p.add_argument('--version',required=True)
    args=p.parse_args()
    if not args.version.isalnum():raise ValueError('Alphanumeric version required')
    parent=load(args.parent_plan);here=Path(__file__).resolve().parent;root=args.parent_plan.resolve().parent
    terminal=Path(parent['output'])/'RESULT.json';previous=load(terminal)
    if previous['status']!='READY_FOR_REVIEW' or previous['plan_sha256']!=bound(args.parent_plan)['sha256']:
        raise ValueError('Exact prior GUI plan must be terminal')
    import psutil
    try:
        if abs(psutil.Process(previous['owner']['pid']).create_time()-previous['owner']['create_time'])<.1:
            raise ValueError('Prior GUI coordinator is still alive')
    except psutil.NoSuchProcess:pass
    cell=Path(parent['output'])/'gui-A2/private_cells/A2_returning/cells/A2_returning/RESULT.json'
    failure=load(cell)
    if failure['status']!='FAILED' or failure.get('archive_integrity_passed') is not True or "['first_final']" not in failure.get('traceback',''):
        raise ValueError('Unexpected prior failure; review actual evidence')
    output=root/('numerical-'+args.version);plan=root/('plan-'+args.version+'.json');worker=root/('worker-'+args.version+'.json')
    if any(p.exists() for p in (output,plan,worker)):raise ValueError('Use fresh output paths')
    worker_document=load(parent['worker_spec'])
    worker_document['argv']=[worker_document['argv'][0],'-B',str(here/'supervise_n3.py'),'run','--plan',str(plan)]
    worker.write_text(json.dumps(worker_document,indent=2)+'\n',encoding='utf-8')
    jobs=[]
    for old in parent['jobs']:
        job=dict(old);argv=list(old['argv']);argv[2]=str(here/'gui_finalaudit.py')
        variant=old['id'].split('-')[-1];argv[argv.index('--output')+1]=str(output/('gui-'+variant))
        job.update(argv=argv,result=str(output/('gui-'+variant)/'GUI_PANEL_REPORT.json'));jobs.append(job)
    bindings={r['path']:r for r in parent['bindings']}
    for path in [args.parent_plan,terminal,cell,worker,*[here/n for n in ('prepare_gui_finalaudit.py','gui_finalaudit.py','final_state_audit.py','test_final_state_audit.py')]]:
        b=bound(path);bindings[b['path']]=b
    document=dict(parent,created_utc=datetime.now(timezone.utc).isoformat(),output=str(output),worker_spec=str(worker),
        jobs=jobs,bindings=list(bindings.values()),purpose='Observe unchanged final text after actual render completion; rerun all six GUI cells',
        application_source_changed=False,presentation_receipt_policy_changed=False,
        audit_change='Additional actual-widget final-state observation after render returns, including no-rewrite path')
    plan.write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='PREPARED_NOT_STARTED',plan=bound(plan),gui_cells=6)))


if __name__=='__main__':main()
