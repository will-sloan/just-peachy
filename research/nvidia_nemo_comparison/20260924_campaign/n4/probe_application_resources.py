"""Qualify host accounting with no models or GUI. See README_APPLICATION_RESOURCES.md."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import time
import unittest
from common import bind,freeze,load,verify
from metric_process import pin,identity
from asr_full_bank import payload_inventory
from probe_integrated_scoring import guard


def run(output):
    process=pin();started=time.monotonic();here=Path(__file__).resolve().parent
    local=here.parents[3].parent/'local';policy=load(local/'supervision/campaign.json')
    if output.exists() or not output.resolve().is_relative_to((local/'n4').resolve()):raise ValueError('Fresh private N4 output required')
    guard(output,policy,started);inventory=payload_inventory(local)
    if inventory['errors'] or inventory['total_logical_bytes']+6*1024**3+128*1024**2>min(50,policy['resource_policy']['new_payload_allowance_gib'])*1024**3:
        raise ValueError('Shared allowance unavailable')
    code=[bind(here/n) for n in ('application_resources.py','test_application_resources.py','probe_application_resources.py',
        'README_APPLICATION_RESOURCES.md','resources.py','common.py','metric_process.py','asr_full_bank.py','probe_integrated_scoring.py')]
    output.mkdir(parents=True,exist_ok=False)
    freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,private_inventory=inventory,expected_tests=7,
        scope='Model-free collector qualification, current helper and a hidden 16-MiB child fixture; not a controlled application measurement'))
    import test_application_resources as tests
    tests.CONTEXT['output']=output
    with (output/'unittest.txt').open('x',encoding='utf-8') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    for b in code:verify(b)
    guard(output,policy,started)
    passed=result.wasSuccessful() and result.testsRun==7 and not result.skipped
    freeze(output/'RESULT.json',dict(status='PASS_RESOURCE_HELPER_ONLY' if passed else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),log=bind(output/'unittest.txt'),
        actual_tree=tests.CONTEXT.get('actual'),elapsed_sec=time.monotonic()-started,models_loaded=0,
        source_or_GUI_execution=False,controlled_whole_stack_qualified=False,integrated_N4_cells=0))
    print(bind(output/'RESULT.json'))
    if not passed:raise RuntimeError('Resource helper tests failed; preserve attempt')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
