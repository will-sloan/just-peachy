"""Bounded read-only allocation census. README_RESERVATION_CENSUS_V1.md."""
import argparse
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import identity, pin
from probe_reservation_budget_v1 import code_bindings as parent_code
from reservation_budget_v1 import GIB, require
from reservation_census_v1 import snapshot
from review_scoring_bank_v3 import guard, shared_allowance

HERE=Path(__file__).resolve().parent
OWN=('reservation_census_v1.py','test_reservation_census_v1.py',
     'probe_reservation_census_v1.py','README_RESERVATION_CENSUS_V1.md')
MAXIMUM=8*1024**2


def code_bindings():
    return parent_code()+[bind(HERE/name) for name in OWN]


def run(output):
    process=pin(); started=time.monotonic(); local=HERE.parents[4]/'local'
    require(not output.exists() and output.resolve().is_relative_to((local/'n4').resolve()),
            'Fresh private N4 diagnostic output required')
    code=code_bindings()
    for b in code:verify(b)
    guard(output,local,started,1200); legacy=shared_allowance(local)
    freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,
        maximum_output_bytes=MAXIMUM,maximum_seconds=1200,legacy_admission=legacy,
        cpu_affinity=process.cpu_affinity(),worker_execution_authorized=False,N4_accepted=False))
    for name in OWN:
        (output/'source').mkdir(exist_ok=True);shutil.copyfile(HERE/name,output/'source'/name)
    tested=None
    try:
        scratch=output/'temporary-fixtures';scratch.mkdir()
        os.environ['TEMP']=os.environ['TMP']=str(scratch);tempfile.tempdir=str(scratch)
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in
                                 ('test_reservation_budget_v1','test_reservation_census_v1'))
        log=io.StringIO();tested=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        (output/'tests.txt').write_text(log.getvalue(),encoding='utf-8')
        require(tested.wasSuccessful(),'Allocation census or arithmetic regression failed')
        print(f'PASS {tested.testsRun} tests; starting actual read-only discovery',flush=True)
        guard(output,local,started,1200)
        observed=snapshot(local,HERE,bind(local/'n4/integrated-main-plan-v3.json'),
                          3*GIB//2,peak_bytes=280*1024**2)
        guard(output,local,started,1200);shared_allowance(local)
        for b in code:verify(b)
        sources=[bind(output/'source'/name) for name in OWN]
        require(all(b['sha256']==bind(HERE/name)['sha256'] for b,name in zip(sources,OWN)),
                'Source snapshot changed')
        freeze(output/'RESULT.json',dict(status='PASS_RECORDED_ALLOCATION_CENSUS_DEVELOPMENT_ONLY',
            utc=datetime.now(timezone.utc).isoformat(),owner=identity(process),
            admission=bind(output/'ADMISSION.json'),tests_passed=tested.testsRun,
            tests=bind(output/'tests.txt'),code=code,source_snapshots=sources,
            snapshot=observed,elapsed_seconds=time.monotonic()-started,
            numerical_workers_started=0,shared_ledger_modified=False,
            serialized_production_admission=False,production_guard_integration_complete=False,
            worker_execution_authorized=False,N4_accepted=False,N5_complete=False))
        require(sum(p.stat().st_size for p in output.rglob('*') if p.is_file())<MAXIMUM,
                'Census diagnostic exceeded its output bound')
        print('PASS: recorded allocation discovery and conservative budget snapshot',flush=True)
    except BaseException as exc:
        freeze(output/'FAILED.json',dict(status='FAILED_ALLOCATION_CENSUS_PRESERVED',
            utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),
            error_type=type(exc).__name__,reason=str(exc),tests_run=tested.testsRun if tested else None,
            worker_execution_authorized=False,N4_accepted=False))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
