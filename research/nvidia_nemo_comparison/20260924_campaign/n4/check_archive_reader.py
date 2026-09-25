"""Read-only live/archived Controller scoring parity; README_EVIDENCE.md."""
import argparse
import json
import os
from pathlib import Path
from common import bind, fingerprint, freeze, load, verify
from score_controller import convert
from metrics import require_versions, score_cell


def main(args):
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    import psutil
    p=psutil.Process();p.cpu_affinity([4])
    if os.name=='nt':p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    if args.output.exists():raise ValueError('Use a fresh output; preserve existing evidence')
    receipt=load(args.receipt)
    if receipt['status']!='LOSSLESS_ARCHIVE_VERIFIED':raise ValueError('Unverified archive receipt')
    for name in ('source','archive'):verify(receipt[name])
    result_path=Path(receipt['source']['path']);result=load(result_path)
    checkpoint_path=result_path.parent.parent/'CHECKPOINT.json';checkpoint=load(checkpoint_path)
    if checkpoint['status']!='COMPLETE' or checkpoint['result']!=receipt['source']:
        raise ValueError('Completed checkpoint changed')
    truth={r['job_id']:r for r in load(args.truth)['cells']}[result['job_id']]
    if truth['frames']!=result['audio']['frames']:raise ValueError('Truth/audio duration differs')
    live=convert(result);archived=convert(result,receipt['archive'])
    live_score=score_cell(truth,live);archived_score=score_cell(truth,archived)
    if live!=archived or live_score!=archived_score:
        raise ValueError('Live/archive prediction or metric mismatch')
    report=dict(status='PASS_EXACT_ARCHIVE_READER_PARITY',job_id=result['job_id'],
        source=receipt['source'],archive=receipt['archive'],
        prediction_sha256=fingerprint(live),score_sha256=fingerprint(live_score),
        predictions_equal=True,metrics_equal=True,metric_versions=require_versions(),
        inputs=[bind(p) for p in (args.receipt,args.truth,checkpoint_path)],
        code=[bind(Path(__file__).with_name(n)) for n in ('check_archive_reader.py',
            'evidence_reader.py','evidence_archive.py','score_controller.py','metrics.py','common.py')],
        scope='One completed N2 cell; exact archive/scorer conformance only',
        source_files_modified=False,source_files_deleted=False,archive_extracted=False,
        model_calls=0,N4_completed_cells=0)
    freeze(args.output,report)
    print(json.dumps(dict(status=report['status'],predictions_equal=True,metrics_equal=True,
        model_calls=0,N4_completed_cells=0)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('receipt','truth','output'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
