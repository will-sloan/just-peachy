"""Bounded resource-guard qualification probe; README_RESERVATION_GUARD_V2.md."""
import argparse
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from reservation_budget_v1 import require
from reservation_guard_v1 import HERE, OWN as GUARD_OWN, OutputGuard, code_bindings as core_code, lock
from review_scoring_bank_v3 import guard, shared_allowance

MAXIMUM = 8*1024**2


EXTRA = ('probe_reservation_guard_v2.py', 'test_reservation_guard_closure_v2.py',
         'README_RESERVATION_GUARD_V2.md')
OWN = GUARD_OWN+EXTRA


def code_bindings():
    return core_code()+[bind(HERE/name) for name in EXTRA]


def close_waited_handle(child):
    require(child.poll() is not None, 'Cannot close the handle of a running helper')
    handle = child._handle
    handle.Close()
    require(handle.closed is True, 'Owned completed process handle was not closed')


def wait_exact_exit(owner, *, lookup=exact_process, now=time.monotonic, pause=time.sleep, seconds=5):
    deadline = now()+seconds
    while lookup(owner) is not None:
        remaining = deadline-now()
        require(remaining > 0, 'Exact helper identity remained after its completed handle wait')
        pause(min(.02, remaining))
    return True


def contention(path, output):
    import psutil
    argv=[sys.executable,'-B',str(HERE/'reservation_guard_v1.py'),'--test-lock',str(path)]
    child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS,close_fds=True)
    owner=identity(psutil.Process(child.pid))
    freeze(output/'CONTENDER_STARTED.json',dict(owner=owner,argv=argv,source=bind(HERE/'reservation_guard_v1.py')))
    stdout=stderr=b''
    try:
        stdout,stderr=child.communicate(timeout=20)
        require(child.returncode==0 and not stdout and not stderr,
                'Actual competing process acquired the held lock or failed unexpectedly')
    finally:
        if child.poll() is None:
            require(exact_process(owner) is not None,'Contending child identity became uncertain')
            child.terminate();child.wait(timeout=10)
        for stream in (child.stdout,child.stderr):
            if stream is not None:stream.close()
        # The Windows process object can remain observable while our completed
        # Popen handle is still retained. Close only that owned, waited handle.
        close_waited_handle(child)
        freeze(output/'CONTENDER_WAIT.json',dict(owner=owner,exit_code=child.returncode,
            process_handle_closed=True,pipes_closed=True))
    wait_exact_exit(owner)
    return dict(owner=owner,argv=argv,exit_code=child.returncode,exact_owner_exited=True,
                process_handle_closed=True,pipes_closed=True,
                held_lock_acquisition_refused=True,stdout_bytes=len(stdout),stderr_bytes=len(stderr))


def run(output):
    process=pin();started=time.monotonic();local=HERE.parents[4]/'local';tested=None
    require(not output.exists() and output.resolve().is_relative_to((local/'n4').resolve()),
            'Fresh private N4 output required')
    code=code_bindings()
    for b in code:verify(b)
    guard(output,local,started,1200);legacy=shared_allowance(local)
    freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,maximum_output_bytes=MAXIMUM,
        maximum_seconds=1200,legacy_admission=legacy,cpu_affinity=process.cpu_affinity(),
        worker_execution_authorized=False,N4_accepted=False))
    for name in OWN:
        (output/'source').mkdir(exist_ok=True);shutil.copyfile(HERE/name,output/'source'/name)
    contender=None
    try:
        scratch=output/'temporary-fixtures';scratch.mkdir()
        os.environ['TEMP']=os.environ['TMP']=str(scratch);tempfile.tempdir=str(scratch)
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in
            ('test_reservation_budget_v1','test_reservation_census_v1','test_reservation_census_v2',
             'test_reservation_guard_v1','test_reservation_guard_closure_v2'))
        log=io.StringIO();tested=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        (output/'tests.txt').write_text(log.getvalue(),encoding='utf-8')
        require(tested.wasSuccessful() and not tested.skipped,'Resource guard regression failed')
        print(f'PASS {tested.testsRun} tests; starting held-lock resource check',flush=True)
        before=load(local/'supervision/worker.json')
        with OutputGuard(local,output,code,bind(local/'n4/integrated-main-plan-v3.json'),1200,
                         production=False) as output_guard:
            contender=contention(local/'n4/reservation-guard.owner.lock',output)
            freeze(output/'LOCK_CONTENTION.json',contender)
            observed=output_guard.refresh(1024**2)
            freeze(output/'GUARD_CHECK.json',observed)
            fast=output_guard.fast_check(1024**2)
        with lock(local/'n4/reservation-guard.owner.lock',wait=0):released=True
        after=load(local/'supervision/worker.json')
        if before['status']=='RUNNING' and after['status']=='RUNNING' and before['run_id']==after['run_id']:
            require(after['heartbeat_unix']>before['heartbeat_unix'], 'Supervisor heartbeat failed to advance')
            heartbeat_advanced=True
        else:heartbeat_advanced=None
        guard(output,local,started,1200);shared_allowance(local)
        for b in code:verify(b)
        sources=[bind(output/'source'/name) for name in OWN]
        require(all(b['sha256']==bind(HERE/name)['sha256'] for b,name in zip(sources,OWN)),
                'Source snapshot changed')
        freeze(output/'RESULT.json',dict(status='PASS_SERIALIZED_RESOURCE_GUARD_DEVELOPMENT_ONLY',
            utc=datetime.now(timezone.utc).isoformat(),owner=identity(process),admission=bind(output/'ADMISSION.json'),
            code=code,source_snapshots=sources,tests=bind(output/'tests.txt'),tests_passed=tested.testsRun,
            actual_resource_check=bind(output/'GUARD_CHECK.json'),lock_contention=bind(output/'LOCK_CONTENTION.json'),
            actual_lock_reacquired_after_exit=released,supervisor_before=before,supervisor_after=after,
            supervisor_heartbeat_advanced=heartbeat_advanced,supervisor_writer_lock_held=False,
            final_fast_check=fast,elapsed_seconds=time.monotonic()-started,numerical_workers_started=0,
            helper_processes_started=1,shared_ledger_modified=False,production_family_integrated=False,
            worker_execution_authorized=False,N4_accepted=False,N5_complete=False))
        require(sum(p.stat().st_size for p in output.rglob('*') if p.is_file())<MAXIMUM,'Probe output cap exceeded')
        print('PASS serialized lock, exact allocation accounting and runtime guard',flush=True)
    except BaseException as exc:
        freeze(output/'FAILED.json',dict(status='FAILED_RESOURCE_GUARD_PROBE_PRESERVED',
            utc=datetime.now(timezone.utc).isoformat(),owner=identity(process),admission=bind(output/'ADMISSION.json'),
            error_type=type(exc).__name__,reason=str(exc),tests_run=tested.testsRun if tested else None,
            lock_contender=contender,worker_execution_authorized=False,N4_accepted=False))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
