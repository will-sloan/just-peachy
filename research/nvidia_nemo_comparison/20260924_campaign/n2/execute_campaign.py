"""Run the admitted N2 coordinator, then final checks. See README_EXECUTE.md."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_suite
import finish_campaign as finish
import run_campaign as campaign


def utc():
    return datetime.now(timezone.utc).isoformat()


def option(argv, name):
    if argv.count(name) != 1 or argv.index(name) + 1 >= len(argv):
        raise ValueError('Exactly one value required for ' + name)
    return argv[argv.index(name) + 1]


def validate_plan(spec, source):
    keys, cpus = campaign.admit(spec)
    if set(keys) != set(finish.EXPECTED) or set(cpus) != {4, 14}:
        raise ValueError('Exact nine-job plan on CPU lanes 4 and 14 required')
    jobs = {job['id']: job for lane in spec['lanes'] for job in lane['jobs']}
    for lane in spec['lanes']:
        for job in lane['jobs']:
            gui = job['id'] == 'gui-panel'
            if job['cells'] != finish.EXPECTED[job['id']] or job['result_kind'] != ('gui' if gui else 'controller'):
                raise ValueError('Job kind or cell denominator changed')
            argv = job['argv']
            if Path(argv[0]).resolve() != Path(sys.executable).resolve():
                raise ValueError('Coordinator job interpreter differs')
            expected_script = HERE / ('gui/panel.py' if gui else 'run_screen.py')
            scripts = [Path(arg).resolve() for arg in argv[1:] if arg.lower().endswith('.py')]
            if scripts != [expected_script.resolve()]:
                raise ValueError('Unexpected coordinator job script')
            if Path(option(argv, '--source')).resolve() != source or int(option(argv, '--cpu')) != lane['cpu']:
                raise ValueError('Job frozen source or CPU differs')
            output = Path(option(argv, '--output')).resolve()
            if Path(job['result']).resolve() != output / ('GUI_PANEL_REPORT.json' if gui else 'RESULT_INDEX.json'):
                raise ValueError('Job result is outside its exact output location')
            if not gui:
                if option(argv, '--combination') != job['id'].split('-', 1)[1] or '--limit' in argv:
                    raise ValueError('Full Controller combination/population required')
                if option(argv, '--profile') != 'low_latency' or option(argv, '--device') != job['device']:
                    raise ValueError('Nominal profile or explicit device differs')
                manifest = finish.load(option(argv, '--manifest'))
                if len(manifest['jobs']) != job['cells'] or len({j['job_id'] for j in manifest['jobs']}) != job['cells']:
                    raise ValueError('Controller manifest denominator differs')
    if sum(job['cells'] for job in jobs.values()) != 422:
        raise ValueError('Expected 384 screen, 32 regression and six GUI cells')
    return jobs


def reject_live(record):
    for key in ('owner', 'child'):
        owner = record.get(key)
        if owner and campaign.process_identity_state(owner['pid'], owner.get('create_time')) in ('ALIVE', 'UNVERIFIED'):
            raise RuntimeError('Prior chain ' + key + ' remains alive or unverified')


def verify_contract(contract):
    for item in list(contract['inputs'].values()) + list(contract['tools'].values()):
        finish.verify_bound(item)


def existing_coordinator(args):
    """Bind the already supervised coordinator; never take ownership or replace it."""
    worker_path = args.state/'worker.json'
    spec_path = args.state/'worker_spec.json'
    worker, worker_spec = finish.load(worker_path), finish.load(spec_path)
    argv = worker_spec['argv']
    expected = [sys.executable, '-B', str(HERE/'run_campaign.py'), '--spec', str(args.spec),
                '--output', str(args.output), '--state', str(args.state)]
    if len(argv) != len(expected) or any(
            (Path(a).resolve() != Path(b).resolve() if i in (0, 2, 4, 6, 8) else a != b)
            for i, (a, b) in enumerate(zip(argv, expected))):
        raise ValueError('Existing supervisor command is not this exact coordinator/spec/output/state')
    argv_sha = hashlib.sha256(json.dumps(argv).encode()).hexdigest()
    if worker.get('argv_sha256') != argv_sha or worker.get('child_launch_pending') is not False:
        raise ValueError('Existing supervisor launch binding is incomplete')
    child = dict(pid=worker.get('child_pid'), create_time=worker.get('child_create_time'))
    host = dict(pid=worker.get('pid'), create_time=worker.get('create_time'))
    if any(type(p['pid']) is not int or p['pid'] <= 0 or not isinstance(p['create_time'], (int, float)) for p in (child, host)):
        raise ValueError('Existing coordinator lacks exact process identities')
    if campaign.process_identity_state(child['pid'], child['create_time']) == 'UNVERIFIED':
        raise ValueError('Existing coordinator identity is unverified')
    if campaign.process_identity_state(child['pid'], child['create_time']) == 'ALIVE':
        import psutil
        process = psutil.Process(child['pid'])
        if process.ppid() != host['pid'] or process.cmdline() != argv:
            raise ValueError('Live coordinator differs from recorded supervisor child')
    admission = finish.load(args.output/'ADMISSION.json')
    contract = dict(spec=finish.load(args.spec), runner_sha256=campaign.digest(HERE/'run_campaign.py'),
                    io_version=campaign.IO_VERSION, io_helper_sha256=campaign.digest(HERE/'io_utils.py'),
                    supervisor_sha256=campaign.digest(HERE.parent/'supervision/supervisor.py'))
    if admission != dict(contract_sha256=campaign.canonical(contract), contract=contract):
        raise ValueError('Existing coordinator admission differs')
    state = finish.load(args.state/'campaign.json')
    cutoff = datetime.fromisoformat(state['target_utc']) - timedelta(hours=state['packaging_reserve_hours'])
    return dict(host=host, child=child, run_id=worker['run_id'], argv_sha256=argv_sha,
                worker_spec=finish.binding(spec_path), coordinator_admission=finish.binding(args.output/'ADMISSION.json'),
                packaging_cutoff_utc=cutoff.isoformat(), observed_worker_status=worker['status'])


def wait_existing(args, binding):
    """Bounded code-only observation. It never signals the supervised process."""
    cutoff = datetime.fromisoformat(binding['packaging_cutoff_utc'])
    ended_at = None
    while True:
        finish.verify_bound(binding['worker_spec'])
        finish.verify_bound(binding['coordinator_admission'])
        worker = finish.load(args.state/'worker.json')
        if (worker.get('run_id') != binding['run_id'] or worker.get('argv_sha256') != binding['argv_sha256']
                or worker.get('child_pid') != binding['child']['pid']
                or worker.get('child_create_time') != binding['child']['create_time']):
            raise RuntimeError('Supervisor child binding changed while waiting')
        state = campaign.process_identity_state(binding['child']['pid'], binding['child']['create_time'])
        if state == 'UNVERIFIED':
            raise RuntimeError('Existing coordinator identity became unverified')
        if state in ('ABSENT', 'PID_REUSED'):
            if worker.get('status') == 'COMPLETED' and worker.get('exit_code') == 0:
                return
            if worker.get('status') == 'FAILED' or worker.get('exit_code') not in (None, 0):
                raise RuntimeError('Existing coordinator exited unsuccessfully; finalizer not launched')
            if ended_at is None:
                ended_at = time.monotonic()
            if time.monotonic() - ended_at >= 30:
                raise RuntimeError('Coordinator ended without a successful supervisor exit receipt')
        if datetime.now(timezone.utc) >= cutoff:
            raise TimeoutError('Packaging reserve reached while observing coordinator; process left untouched')
        _, low = campaign.disk_reserves(finish.load(args.state/'campaign.json'))
        if low:
            raise RuntimeError('Disk reserve breached while observing coordinator; process left untouched')
        time.sleep(5)


def admit(args):
    source_receipt, source, _ = finish.validate_source(args.source_receipt)
    tests = check_suite.validate_completed_report(args.test_report, args.source_receipt)
    spec = finish.load(args.spec)
    jobs = validate_plan(spec, source)
    analysis, public = args.analysis_output.resolve(), args.public_out.resolve()
    if analysis.is_relative_to(source) or public.is_relative_to(source):
        raise ValueError('Reports must remain outside frozen source')
    if analysis.is_relative_to(public) or public.is_relative_to(analysis):
        raise ValueError('Private and public reports must remain separate')
    tool_paths = [Path(__file__), HERE/'run_campaign.py', HERE/'run_screen.py', HERE/'configure.py',
                  HERE/'finish_campaign.py', HERE/'check_suite.py', HERE/'io_utils.py', HERE/'gui/panel.py',
                  HERE.parent/'data/run_baseline_screen.py', HERE.parent/'supervision/supervisor.py']
    tool_paths += sorted((HERE/'evaluation').glob('*.py'))
    contract = dict(schema='n2-execution-chain-admission-v1',
        inputs={name: finish.binding(getattr(args, name)) for name in ('spec', 'source_receipt', 'test_report')},
        tools={str(path.relative_to(HERE.parent)).replace('\\', '/'): finish.binding(path) for path in tool_paths},
        interpreter=finish.binding(sys.executable),
        destinations={name: str(getattr(args, name).resolve()) for name in ('output', 'state', 'analysis_output', 'public_out')},
        gui_report=str(Path(jobs['gui-panel']['result']).resolve()), expected_jobs=9, expected_cells=422,
        source_frontend_sha256=source_receipt['frontend_runtime_sha256'],
        tests={key: tests[key] for key in ('status', 'successful', 'requested_modules', 'finished_modules', 'tests', 'skipped')},
        scheduling=dict(cpus=[4, 14], priority='BelowNormal', hidden_windows=True, sequential_phases=True),
        wait_for_existing=args.wait_for_existing,
        model_calls_in_wrapper=False, llm_calls=False, git_actions=False, packaging=False, stage_completion=False)
    finish.verify_bound(contract['interpreter'])
    verify_contract(contract)
    if args.wait_for_existing:
        contract['existing_coordinator'] = existing_coordinator(args)
    return contract, spec


def require_fresh_reports(args):
    if args.analysis_output.exists():
        raise ValueError('Private final analysis must be fresh; preserve prior output and choose another destination')
    if any((args.public_out/name).exists() for name in finish.PUBLIC_NAMES):
        raise ValueError('Final public report already exists; preserve it and choose another directory')


def launch(argv, log_path, timeout, started):
    """Own one child until exit; persist its identity before the blocking wait."""
    import psutil
    flags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name == 'nt' else 0
    owner = None
    with log_path.open('ab') as log:
        proc = subprocess.Popen(argv, cwd=HERE, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=flags)
        try:
            try:
                child = psutil.Process(proc.pid)
                owner = dict(pid=proc.pid, create_time=child.create_time())
                child.cpu_affinity([4, 14])
            except psutil.NoSuchProcess:
                if proc.poll() is None:
                    raise
            started(owner or dict(pid=proc.pid, create_time=None))
            return proc.wait(timeout=timeout)
        except BaseException:
            if proc.poll() is None:
                if owner:
                    campaign.stop_owned_tree(owner)
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            raise


def run(args):
    import psutil
    for name in ('spec', 'output', 'state', 'source_receipt', 'test_report', 'analysis_output', 'public_out'):
        setattr(args, name, getattr(args, name).resolve())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    process = psutil.Process()
    process.cpu_affinity([4, 14])
    if os.name == 'nt':
        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    with campaign.lock(output/'chain.owner.lock'):
        # This record is checked across all contracts/destinations, not only one attempt.
        reject_live(campaign.read(output/'CHAIN_RESULT.json', {}))
        if not args.wait_for_existing:
            with campaign.lock(output/'owner.lock'):
                pass
        state = dict(schema='n2-execution-chain-result-v1', status='ADMITTING', phase='admission',
            owner=dict(pid=os.getpid(), create_time=process.create_time()), child=None,
            started_utc=utc(), phases=[], expected_cells=422, stage_completion_claimed=False,
            packaging_performed=False, git_actions=False, llm_invoked=False)
        chain_dir = None

        def report(status, **fields):
            state.update(status=status, updated_utc=utc(), **fields)
            if chain_dir is not None:
                campaign.atomic(chain_dir/'CHAIN_RESULT.json', state)
            campaign.atomic(output/'CHAIN_RESULT.json', state)

        try:
            contract, spec = admit(args)
            checksum = campaign.canonical(contract)
            chain_dir = output/'chains'/checksum
            chain_dir.mkdir(parents=True, exist_ok=True)
            admission = chain_dir/'CHAIN_ADMISSION.json'
            expected = dict(contract_sha256=checksum, contract=contract)
            if admission.exists() and campaign.read(admission) != expected:
                raise ValueError('Execution chain admission changed')
            campaign.atomic(admission, expected)
            state.update(contract_sha256=checksum, admission=finish.binding(admission))
            previous = campaign.read(chain_dir/'CHAIN_RESULT.json', {})
            if previous.get('status') == 'READY_FOR_REVIEW':
                finish.verify_bound(previous['final_checks'])
                if finish.load(previous['final_checks']['path']).get('status') != 'PASS':
                    raise ValueError('Prior final checks changed')
                for binding in previous.get('published_reports', {}).values():
                    finish.verify_bound(binding)
                report('READY_FOR_REVIEW', phase='complete', cached=True,
                       final_checks=previous['final_checks'], published_reports=previous['published_reports'])
                return 0
            require_fresh_reports(args)
            coordinator = [sys.executable, '-B', str(HERE/'run_campaign.py'), '--spec', str(args.spec),
                           '--output', str(args.output), '--state', str(args.state)]
            finalizer = [sys.executable, '-B', str(HERE/'finish_campaign.py'), '--spec', str(args.spec),
                         '--coordinator-result', str(output/'RESULT.json'), '--source-receipt', str(args.source_receipt),
                         '--test-report', str(args.test_report), '--gui-report', contract['gui_report'],
                         '--output', str(args.analysis_output), '--public-out', str(args.public_out), '--cpu', '4']
            coordinator_bound = max(sum(job['timeout_seconds'] for job in lane['jobs']) for lane in spec['lanes']) + 120
            phases = [('coordinator', coordinator, coordinator_bound), ('final_checks', finalizer, 7200)]
            if args.wait_for_existing:
                state['phase'] = 'existing_coordinator'
                report('WAITING_FOR_EXISTING', external_coordinator=contract['existing_coordinator'])
                wait_existing(args, contract['existing_coordinator'])
                report('EXISTING_COORDINATOR_EXITED')
                phases = [('final_checks', finalizer, 7200)]
            for phase, argv, timeout in phases:
                verify_contract(contract)
                finish.verify_bound(contract['interpreter'])
                if phase == 'final_checks':
                    # The prior child wait has finished. Recheck its complete evidence and lifetime lock.
                    with campaign.lock(output/'owner.lock'):
                        finish.validate_coordinator(args.spec, output/'RESULT.json')
                    require_fresh_reports(args)
                state['phase'] = phase
                row = dict(phase=phase, argv=argv, log=str(chain_dir/(phase+'.log')), timeout_seconds=timeout, started_utc=utc())
                state['phases'].append(row)

                def started(owner):
                    row['owner'] = owner
                    report('RUNNING', child=owner)

                code = launch(argv, Path(row['log']), timeout, started)
                row.update(exit_code=code, finished_utc=utc())
                report('RUNNING', child=None)
                if code:
                    report('INCOMPLETE' if phase == 'coordinator' else 'FAILED_FINAL_CHECKS')
                    return 2
            verify_contract(contract)
            checks = args.analysis_output/'FINAL_CHECKS.json'
            if finish.load(checks).get('status') != 'PASS':
                raise ValueError('Zero finalizer exit lacks passing final checks')
            published = {name: finish.binding(args.public_out/name) for name in finish.PUBLIC_NAMES}
            report('READY_FOR_REVIEW', phase='complete', child=None, final_checks=finish.binding(checks), published_reports=published)
            return 0
        except BaseException as exc:
            status = 'FAILED_FINAL_CHECKS' if state['phase'] == 'final_checks' else 'INCOMPLETE'
            report(status, error_type=type(exc).__name__, error=repr(exc))
            return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('spec', 'output', 'state', 'source-receipt', 'test-report', 'analysis-output', 'public-out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--wait-for-existing', action='store_true',
                        help='Observe the exact supervisor child; never stop, replace or launch a coordinator')
    return run(parser.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
