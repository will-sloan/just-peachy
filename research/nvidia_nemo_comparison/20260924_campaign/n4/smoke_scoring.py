"""Two-cell evaluator conformance using completed N2 evidence. README_SCORING.md."""
import argparse
from pathlib import Path
import json
import os
from common import load,bind,freeze
from score_controller import convert
from metrics import score_cell,require_versions


def main(args):
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    import psutil
    p=psutil.Process();p.cpu_affinity([4])
    if os.name=='nt':p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    truth_path=args.local/'n2/evaluation/EVALUATOR_TRUTH.json'
    truth={r['job_id']:r for r in load(truth_path)['cells']}
    rows=[]
    # Predeclared first common completed cell, not chosen by score.
    for combination in ('D0_E0','D1_E0'):
        index_path=args.local/'n2/factorial-v2'/combination/'RESULT_INDEX.json'
        index=load(index_path)
        if index['status']!='COMPLETE' or len(index['completed'])!=96:
            raise ValueError('Use only a completed 96-cell upstream batch')
        jid=sorted(index['completed'])[0]
        result_path=Path(index['completed'][jid]);result=load(result_path)
        checkpoint=load(result_path.parent.parent/'CHECKPOINT.json')
        if checkpoint['result']!=bind(result_path) or result['status']!='COMPLETE':
            raise ValueError('Completed checkpoint changed')
        prediction=convert(result)
        row=score_cell(truth[jid],prediction)
        rows.append(dict(combination=combination,job_id=jid,score=row,
                         execution=bind(result_path),index=bind(index_path)))
    freeze(args.output,dict(status='PASS_EXISTING_N2_EVIDENCE_SCORING',rows=rows,
        metric_versions=require_versions(),truth=bind(truth_path),
        scope='Two evaluator smoke cells; no new inference and no N4 integrated completion credit',
        N4_completed_cells=0,model_calls=0,hardware_calls=0,code=bind(__file__)))
    print(json.dumps(dict(status='PASS_EXISTING_N2_EVIDENCE_SCORING',cells=len(rows),N4_completed_cells=0),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--local',type=Path,default=Path('G:/Just_Peachy_N1/20260924_campaign/local'))
    p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
