"""Import-path derivative of the private viewport probe. README_WIDGET_VISIBILITY_V2.md."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from common import bind,freeze,load,verify
from metric_process import pin,exact_process
from probe_integrated_scoring import guard,private_bytes

MODULE='research.nvidia_nemo_comparison.20260924_campaign.n4.test_widget_visibility_v2'


def run(args):
    pin();here=Path(__file__).resolve().parent;public=load(here/'APPLICATION_PUBLICATION_CHECK_V1.json')
    verify(public['source_receipt']);source=load(public['source_receipt']['path']);root=Path(source['prototype'])
    for rel,b in source['files'].items():verify(dict(path=str((root/rel).resolve()),**b))
    verify(public['private_receipt']);parent=load(public['private_receipt']['path'])
    entries=[{k:r[k] for k in ('backend','mode','tap','projection')} for r in parent['checks']]
    if len(entries)!=160 or len({(r['backend'],r['mode'],r['tap']) for r in entries})!=160:
        raise ValueError('Exact saved composition/mode/tap coverage required')
    for r in entries:verify(r['projection']['compressed'])
    local=Path(public['source_receipt']['path']).parents[2];policy=load(local/'supervision/campaign.json');started=time.monotonic()
    if args.output.exists() or not args.output.resolve().is_relative_to((local/'n4').resolve()):raise ValueError('Fresh private output required')
    guard(args.output,policy,started);size=private_bytes(local)
    if size+6*1024**3+256*1024**2>min(50,policy['resource_policy']['new_payload_allowance_gib'])*1024**3:
        raise ValueError('Shared private allowance unavailable')
    code=[bind(here/n) for n in ('widget_visibility.py','test_widget_visibility_v2.py','probe_widget_visibility_v2.py',
        'README_WIDGET_VISIBILITY.md','README_WIDGET_VISIBILITY_V2.md','integrated_scoring_adapter.py','common.py')]
    args.output.mkdir(parents=True,exist_ok=False)
    admission=dict(output=str(args.output.resolve()),source=public['source_receipt'],parent=public['private_receipt'],
        code=code,launcher=bind(root/'tests/run_private_desktop.py'),saved_checks=entries,
        expected_tests=7,private_bytes_at_start=size,models_loaded=0,physical_scanout=False)
    freeze(args.output/'ADMISSION.json',admission)
    environment=dict(os.environ,N4_WIDGET_ADMISSION=str(args.output.resolve()/'ADMISSION.json'),
        PYTHONPATH=str(here.parents[3]),CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):environment[key]='1'
    command=[sys.executable,'-B',str(root/'tests/run_private_desktop.py'),'--receipt-dir',str(args.output.resolve()),
        '--timeout-seconds','180',MODULE]
    with (args.output/'LAUNCH_OUTPUT.log').open('xb') as stream:
        child=subprocess.run(command,cwd=root.parent,env=environment,stdout=stream,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,check=False)
    isolation=load(args.output/'isolation.json');tests=load(args.output/'tests.json')
    for b in code:verify(b)
    if (child.returncode or isolation['exit_code'] or isolation['timed_out'] or not isolation['input_desktop_unchanged']
            or isolation['switch_desktop_called'] or isolation['input_injection'] or not tests['successful']
            or tests['tests']!=7 or tests['skipped']):
        freeze(args.output/'RESULT.json',dict(status='FAILED_PRESERVED',isolation=bind(args.output/'isolation.json'),
            tests=bind(args.output/'tests.json'),admission=bind(args.output/'ADMISSION.json'),integrated_N4_cells=0))
        raise RuntimeError('Private viewport qualification failed; preserve evidence')
    saved=load(args.output/'SAVED_OUTPUT_CHECKS.json')
    if len(saved['cases'])!=160 or exact_process(saved['owner']) is not None:raise ValueError('Saved check census/owner closure differs')
    for b in saved['cases']:verify(b)
    guard(args.output,policy,started)
    freeze(args.output/'RESULT.json',dict(status='PASS_PRIVATE_TK_VIEWPORT_QUALIFICATION',utc=datetime.now(timezone.utc).isoformat(),
        admission=bind(args.output/'ADMISSION.json'),tests=bind(args.output/'tests.json'),test_log=bind(args.output/'unittest.txt'),
        isolation=bind(args.output/'isolation.json'),saved_checks=bind(args.output/'SAVED_OUTPUT_CHECKS.json'),
        tests_passed=7,saved_cases=160,worker_exited=True,models_loaded=0,integrated_N4_cells=0,
        scope='Private Tk viewport observation, not source-paced actual inference or physical visibility'))
    print(json.dumps(dict(result=bind(args.output/'RESULT.json'))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args())
