"""Bind a fresh isolated GUI retest after exact label-test diagnosis; README_GUI_RECOVERY.md."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from reuse_results import bound, load


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent-plan',type=Path,required=True)
    p.add_argument('--version',required=True)
    args=p.parse_args()
    if not args.version.isalnum():raise ValueError('Alphanumeric version required')
    parent=load(args.parent_plan);root=args.parent_plan.resolve().parent
    terminal=Path(parent['output'])/'RESULT.json';previous=load(terminal)
    if previous['status']!='READY_FOR_REVIEW' or previous['plan_sha256']!=bound(args.parent_plan)['sha256']:
        raise ValueError('Exact parent must be terminal')
    import psutil
    try:
        if abs(psutil.Process(previous['owner']['pid']).create_time()-previous['owner']['create_time'])<.1:
            raise ValueError('Parent coordinator is still alive')
    except psutil.NoSuchProcess:pass
    here=Path(__file__).resolve().parent
    original=here/'gui.py';revised=here/'gui_labels.py'
    original_text=original.read_text(encoding='utf-8')
    bad=' \u00c2\u00b7 assumed';good=' \u00b7 assumed'
    expected=original_text.replace(bad,r' \u00b7 assumed').replace(
        "MODULE = 'research.nvidia_nemo_comparison.20260924_campaign.n3.gui'",
        "MODULE = 'research.nvidia_nemo_comparison.20260924_campaign.n3.gui_labels'")
    if original_text.count(bad)!=2 or revised.read_text(encoding='utf-8')!=expected:
        raise ValueError('Rescue must change only two label assertions and its private module identifier')
    bindings={r['path']:r for r in parent['bindings']}
    if bindings[str(original)]['sha256']!=bound(original)['sha256']:
        raise ValueError('Original admitted runner changed')
    output=root/('numerical-'+args.version);plan=root/('plan-'+args.version+'.json')
    worker=root/('worker-'+args.version+'.json')
    if any(p.exists() for p in (output,plan,worker)):raise ValueError('Preserve existing evidence; use fresh paths')
    jobs=[];diagnoses=[];extra=[args.parent_plan,terminal,Path(__file__),revised,here/'test_gui_label_recovery.py']
    for variant in ('A2','A3'):
        key='actual-gui-'+variant
        old=next(j for j in parent['jobs'] if j['id']==key)
        evidence=previous['jobs'][key]
        if evidence['status']!='FAILED' or evidence['result']['sha256']!=bound(old['result'])['sha256']:
            raise ValueError('Parent GUI failure binding differs')
        panel=load(old['result']);cell_id=variant+'_boundary'
        cell=Path(old['result']).parent/'private_cells'/cell_id/'cells'/cell_id
        cell_result=load(cell/'RESULT.json')
        if (panel['status']!='FAILED' or panel['completed']!=0 or
            cell_result.get('cleanup_error') or cell_result.get('archive_integrity_passed') is not True or
            "endswith('"+bad+"')" not in cell_result.get('traceback','')):
            raise ValueError('Failure is not the diagnosed expected-label assertion')
        receipts=cell/'PRESENTATION_RECEIPTS.jsonl'
        rows=[json.loads(line) for line in receipts.read_text(encoding='utf-8').splitlines()]
        labels=[r['label'] for r in rows if r.get('display_profile_id')]
        if not labels or not all(label.endswith(good) for label in labels):
            raise ValueError('Actual assumed labels do not confirm the diagnosis')
        diagnoses.append(dict(variant=variant,actual_expected_labels=len(labels),
            assertion_codepoints=[ord(c) for c in bad],actual_suffix_codepoints=[ord(c) for c in good],
            original_panel=bound(old['result']),cell_result=bound(cell/'RESULT.json'),receipts=bound(receipts)))
        extra.extend([Path(old['result']),cell/'RESULT.json',receipts])
        job=dict(old,depends_on=[])
        argv=list(old['argv']);argv[2]=str(revised)
        argv[argv.index('--output')+1]=str(output/('gui-'+variant))
        job.update(argv=argv,result=str(output/('gui-'+variant)/'GUI_PANEL_REPORT.json'))
        jobs.append(job)
    worker_document=load(parent['worker_spec'])
    worker_document['argv']=[worker_document['argv'][0],'-B',str(here/'supervise_n3.py'),'run','--plan',str(plan)]
    worker.write_text(json.dumps(worker_document,indent=2)+'\n',encoding='utf-8');extra.append(worker)
    for path in extra:
        row=bound(path);bindings[row['path']]=row
    document=dict(parent,created_utc=datetime.now(timezone.utc).isoformat(),output=str(output),
        worker_spec=str(worker),jobs=jobs,bindings=list(bindings.values()),
        purpose='Retest all six A2/A3 private GUI cells after correcting expected-label encoding only',
        diagnosis=diagnoses,prototype_changed=False,inference_logic_changed=False)
    plan.write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='PREPARED_NOT_STARTED',plan=bound(plan),jobs=2,gui_cells=6)))


if __name__=='__main__':main()
