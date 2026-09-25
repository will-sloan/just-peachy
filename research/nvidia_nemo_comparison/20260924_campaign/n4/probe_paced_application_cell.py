"""Model-free private application integration qualification. README_PACED_APPLICATION_CELL.md."""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import subprocess
import sys
import time
from common import bind,freeze,load,verify
from metric_process import pin,identity,exact_process
from asr_full_bank import payload_inventory
from probe_integrated_scoring import guard

MODULE='research.nvidia_nemo_comparison.20260924_campaign.n4.test_paced_application_cell'


def run(output):
    p=pin();here=Path(__file__).resolve().parent;started=time.monotonic()
    parent=load(here/'PACED_ADAPTERS_CHECK_V3.json');verify(parent['private_receipt']);verify(parent['source_receipt'])
    original=load(Path(parent['private_receipt']['path']).parent/'ADMISSION.json')
    source=load(parent['source_receipt']['path']);root=Path(source['prototype']);local=root.parents[2]
    for rel,b in source['files'].items():verify(dict(path=str((root/rel).resolve()),**b))
    for b in [parent['gallery_preparation'],*original['runtimes']]:verify(b)
    prep=load(here/'PREPARATION_V2_CHECK.json');verify(prep['preparation']);prep=load(prep['preparation']['path'])
    panel=next(b for b in prep['outputs'] if Path(b['path']).name=='PACED_AUDIO_ONLY_24.json');verify(panel)
    job=load(panel['path'])['jobs'][0];gallery=load(parent['gallery_preparation']['path']);verify(gallery['catalog'])
    policy=load(local/'supervision/campaign.json')
    if output.exists() or not output.resolve().is_relative_to((local/'n4').resolve()):raise ValueError('Fresh private N4 output required')
    guard(output,policy,started);inventory=payload_inventory(local)
    if inventory['errors'] or inventory['total_logical_bytes']+6*1024**3+128*1024**2>min(50,policy['resource_policy']['new_payload_allowance_gib'])*1024**3:
        raise ValueError('Shared allowance unavailable')
    names=('paced_application_cell.py','paced_viewport.py','test_paced_application_cell.py','probe_paced_application_cell.py',
        'README_PACED_APPLICATION_CELL.md','paced_adapters_v3.py','mode_galleries.py','widget_visibility.py','viewport_ledger_v2.py',
        'application_resources.py','application_closure.py','application_closure_v2.py','controller_projection.py','common.py','resources.py',
        'metric_process.py','asr_full_bank.py','probe_integrated_scoring.py')
    code=[bind(here/n) for n in names];output.mkdir(parents=True,exist_ok=False)
    freeze(output/'ADMISSION.json',dict(owner=identity(p),output=str(output.resolve()),source=parent['source_receipt'],
        parent=parent['private_receipt'],gallery_preparation=parent['gallery_preparation'],runtimes=original['runtimes'],
        catalog=gallery['catalog'],job=job,panel=panel,code=code,launcher=bind(root/'tests/run_private_desktop.py'),
        expected_tests=8,private_inventory=inventory,source_execution_authorized_by_this_probe=False))
    env=dict(os.environ,N4_PACED_CELL_ADMISSION=str(output.resolve()/'ADMISSION.json'),PYTHONPATH=str(here.parents[3]),
        CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
    command=[sys.executable,'-B',str(root/'tests/run_private_desktop.py'),'--receipt-dir',str(output.resolve()),'--timeout-seconds','180',MODULE]
    with (output/'LAUNCH_OUTPUT.log').open('xb') as stream:
        child=subprocess.run(command,cwd=root.parent,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    isolation=load(output/'isolation.json');tests=load(output/'tests.json')
    for b in code:verify(b)
    passed=(child.returncode==0 and isolation['exit_code']==0 and not isolation['timed_out'] and isolation['input_desktop_unchanged']
        and not isolation['switch_desktop_called'] and not isolation['input_injection'] and tests['successful'] and tests['tests']==8 and not tests['skipped'])
    checks=load(output/'CHECKS.json') if (output/'CHECKS.json').exists() else {}
    passed=passed and len(checks.get('prepared_cells',[]))==3 and exact_process(checks['owner']) is None
    guard(output,policy,started)
    freeze(output/'RESULT.json',dict(status='PASS_PRIVATE_APPLICATION_PRESTART_ONLY' if passed else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.json'),
        test_log=bind(output/'unittest.txt'),isolation=bind(output/'isolation.json'),
        checks=bind(output/'CHECKS.json') if checks else None,tests_passed=8 if passed else None,
        models_loaded=0,actual_source_execution=False,actual_Tk_and_Controller_prestart=True,actual_source_run_branch_tested=False,
        integrated_N4_cells=0,complete_application_acceptance=False))
    print(bind(output/'RESULT.json'))
    if not passed:raise RuntimeError('Pre-start integration qualification failed; preserve attempt')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
