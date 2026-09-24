"""One guarded private Windows process per frozen test module. See README_CHECK_SUITE.md."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[3]
CHILD_MODULE = 'research.nvidia_nemo_comparison.20260924_campaign.n2.suite_child'
spec = importlib.util.spec_from_file_location('_suite_io', HERE/'io_utils.py')
_io = importlib.util.module_from_spec(spec); spec.loader.exec_module(_io)
atomic = _io.atomic
COUNTS = ('tests', 'failures', 'errors', 'skipped', 'expected_failures', 'unexpected_successes')


def load(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def bound(path):
    path = Path(path).resolve(strict=True)
    with path.open('rb') as stream: sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), sha256=sha, bytes=path.stat().st_size)


def source_bindings(source):
    return {str(p.relative_to(source)).replace('\\', '/'): bound(p)
            for p in sorted(source.rglob('*')) if p.is_file()
            and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.pyo')}


def discover(source):
    modules = ['prototype.tests.'+p.stem for p in sorted((source/'tests').glob('test*.py'))]
    if not modules: raise ValueError('Source contains no test*.py modules')
    return modules


def inspect_module(folder, module, returncode):
    """Zero exit alone never admits missing tests, crashes or incomplete census."""
    folder = Path(folder); reasons = []; evidence = []
    documents = {}
    for name in ('CENSUS.json', 'CHILD_RESULT.json', 'tests.json', 'isolation.json', 'hardware_guard.json'):
        path = folder/name
        if not path.is_file(): reasons.append('missing '+name); continue
        evidence.append(bound(path))
        try: documents[name] = load(path)
        except (ValueError, OSError) as exc: reasons.append(name+': '+str(exc))
    child = documents.get('CHILD_RESULT.json', {})
    census = documents.get('CENSUS.json', {})
    tests = documents.get('tests.json', {})
    isolation = documents.get('isolation.json', {})
    guard = documents.get('hardware_guard.json', {})
    def require(ok, reason):
        if not ok: reasons.append(reason)
    require(returncode == 0, 'launcher returned '+str(returncode))
    require(isolation.get('exit_code') == 0 and isolation.get('timed_out') is False, 'private child failed or timed out')
    require(isolation.get('input_desktop_unchanged') is True and isolation.get('switch_desktop_called') is False
            and isolation.get('input_injection') is False and isolation.get('desktop_handle_closed') is True,
            'desktop isolation was not fully verified')
    ids = census.get('planned_test_ids', [])
    require(census.get('module') == module and child.get('module') == module, 'module identity differs')
    require(bool(ids) and len(ids) == len(set(ids)) and census.get('planned_tests') == len(ids), 'missing/duplicate test census')
    require(not census.get('loader_errors'), 'unittest loader errors')
    require(child.get('planned_test_ids') == ids and child.get('started_test_ids') == ids
            and child.get('completed_test_ids') == ids and child.get('tests') == len(ids), 'not every discovered test finished exactly once')
    require(child.get('successful') is True and tests.get('successful') is True, 'unittest failures/errors/unexpected successes')
    for key in ('tests', 'failures', 'errors', 'skipped'):
        require(child.get(key) == tests.get(key) and isinstance(child.get(key), int), 'test count mismatch: '+key)
    require(guard.get('module') == module and guard.get('before_test_import') is True
            and guard.get('physical_audio_calls') == 'disabled'
            and guard.get('external_non_python_processes') == 'disabled'
            and guard.get('N2_TEST_E1') == '1', 'hardware/actual-E1 guard absent')
    for name in ('unittest.txt', 'NATIVE_OUTPUT.log', 'LAUNCH_OUTPUT.log'):
        if (folder/name).is_file(): evidence.append(bound(folder/name))
    return dict(module=module, output=str(folder), status='COMPLETE' if not reasons else 'FAILED',
        successful=not reasons, launcher_returncode=returncode, reasons=reasons,
        **{key: child.get(key, tests.get(key, 0)) for key in COUNTS}, planned_tests=len(ids),
        test_ids=ids, skipped_tests=[item for item in child.get('outcomes', []) if item['outcome'] == 'addSkip'],
        evidence=evidence)


def aggregate(admission, rows):
    expected = admission['modules']; observed = [row['module'] for row in rows]
    if observed != expected[:len(observed)]: raise ValueError('Unexpected, duplicate or reordered module result')
    finished = len(rows); complete = finished == len(expected)
    failed = [row['module'] for row in rows if not row['successful']]
    return dict(schema='n2-isolated-prototype-suite-v1',
        status=('FAILED' if failed else 'COMPLETE') if complete else 'RUNNING',
        successful=complete and not failed, requested_modules=len(expected), finished_modules=finished,
        successful_modules=finished-len(failed), failed_modules=failed, modules=expected,
        **{key: sum(row[key] for row in rows) for key in COUNTS},
        planned_tests=sum(row['planned_tests'] for row in rows), module_results=rows,
        source=admission['source'], source_receipt=admission['source_receipt'],
        execution_policy='one guarded private desktop child per module, sequential, one CPU, actual saved E1 enabled')


def validate_completed_report(report_path, source_receipt_path):
    """Pure read-only finalizer: recheck every test, binding and owner exit."""
    report_path = Path(report_path).resolve(strict=True); report = load(report_path)
    if report.get('schema') != 'n2-isolated-prototype-suite-v1' or report.get('status') != 'COMPLETE' or report.get('successful') is not True:
        raise ValueError('Isolated suite is not complete and successful')
    admission_path = report_path.parent/'ADMISSION.json'
    if report.get('admission') != bound(admission_path): raise ValueError('Suite admission changed')
    admission = load(admission_path); source = Path(admission['source'])
    if admission.get('source_receipt') != bound(source_receipt_path) or report.get('source_receipt') != bound(source_receipt_path):
        raise ValueError('Frozen source receipt differs')
    if source_bindings(source) != admission['source_bindings'] or report.get('source_unchanged') is not True:
        raise ValueError('Frozen suite source changed')
    for item in admission.get('auxiliary_files', {}).values():
        if item != bound(item['path']): raise ValueError('Frozen auxiliary source changed')
    if discover(source) != admission['modules']: raise ValueError('Test module inventory differs')
    for field in ('runner', 'child_helper', 'io_helper', 'launcher', 'interpreter'):
        item = admission[field]
        if item != bound(item['path']): raise ValueError('Suite tool binding changed: '+field)
    for item in admission.get('tool_snapshots', {}).values():
        if item != bound(item['path']): raise ValueError('Suite tool snapshot changed')
    rows = report['module_results']
    if len(rows) != len(admission['modules']): raise ValueError('Some modules were omitted')
    for module, row in zip(admission['modules'], rows):
        folder = report_path.parent/'modules'/module.rsplit('.', 1)[1]
        if Path(row['output']).resolve() != folder.resolve() or row['module'] != module:
            raise ValueError('Module output or ordering differs')
        if load(folder/'RESULT.json') != row: raise ValueError('Module result changed')
        verified = inspect_module(folder, module, row['launcher_returncode'])
        if not verified['successful'] or any(row.get(k) != v for k, v in verified.items()):
            raise ValueError('Module evidence is incomplete or changed: '+module)
        if row.get('command') != bound(folder/'COMMAND.json'):
            raise ValueError('Module command changed')
        if row.get('source') != admission['source_bindings']['tests/'+module.rsplit('.', 1)[1]+'.py']:
            raise ValueError('Module source binding differs')
        guard = load(folder/'hardware_guard.json')
        if guard.get('cpu_affinity') != [admission['cpu']] or guard.get('CUDA_VISIBLE_DEVICES') != '':
            raise ValueError('Module resource/device contract differs')
        if any(not item.get('reason') for item in row['skipped_tests']): raise ValueError('Skip reason was omitted')
    recomputed = aggregate(admission, rows)
    if any(report.get(k) != v for k, v in recomputed.items()): raise ValueError('Suite aggregate differs from its modules')
    return dict(schema=report['schema'], status='COMPLETE', successful=True,
        **{key: report[key] for key in COUNTS}, planned_tests=report['planned_tests'],
        requested_modules=report['requested_modules'], finished_modules=report['finished_modules'],
        successful_modules=report['successful_modules'], failed_modules=[],
        skipped_tests=[item for row in rows for item in row['skipped_tests']],
        report=bound(report_path), admission=bound(admission_path), source_receipt=bound(source_receipt_path))


def stop_owned(process, created):
    """Kill only this launcher's unchanged process identity and descendants."""
    import psutil
    try:
        owner = psutil.Process(process.pid)
        if owner.create_time() != created: raise RuntimeError('Launcher PID identity changed')
        children = owner.children(recursive=True)
        for child in reversed(children):
            try: child.kill()
            except psutil.NoSuchProcess: pass
        owner.kill(); psutil.wait_procs(children+[owner], timeout=5)
        process.wait(timeout=5)
    except psutil.NoSuchProcess: process.poll()


def run(args):
    if os.name != 'nt': raise RuntimeError('Requires the existing Windows private-desktop launcher')
    import psutil
    current = psutil.Process(); current.cpu_affinity([args.cpu]); current.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    source = Path(args.source).resolve(strict=True); output = Path(args.output).resolve()
    if output.exists(): raise ValueError('Use a fresh output directory; prior failure evidence must remain intact')
    modules = discover(source); launcher = source/'tests/run_private_desktop.py'
    receipt = source.parent/'SOURCE_RECEIPT.json'
    bindings = source_bindings(source); auxiliary = {}
    if receipt.is_file():
        for relative, binding in load(receipt)['files'].items():
            actual = bindings.get(relative)
            if actual is None or any(actual[k] != binding[k] for k in ('sha256', 'bytes')):
                raise ValueError('Frozen source differs from SOURCE_RECEIPT: '+relative)
        for relative, binding in load(receipt).get('auxiliary_files', {}).items():
            actual = bound(source.parent/relative)
            if any(actual[k] != binding[k] for k in ('sha256', 'bytes')):
                raise ValueError('Frozen auxiliary source differs: '+relative)
            auxiliary[relative] = actual
    output.mkdir(parents=True)
    snapshot = output/'tool_snapshot'; snapshot.mkdir()
    snapshots = {}
    for name in ('check_suite.py', 'suite_child.py', 'io_utils.py', 'test_check_suite.py', 'README_CHECK_SUITE.md'):
        shutil.copyfile(HERE/name, snapshot/name); snapshots[name] = bound(snapshot/name)
    environment = dict(os.environ, PYTHONPATH=str(WORKTREE), PYTHONDONTWRITEBYTECODE='1',
        N2_SUITE_SOURCE=str(source), N2_SUITE_CPU=str(args.cpu), N2_TEST_E1='1', CUDA_VISIBLE_DEVICES='')
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        environment[name] = '1'
    admission = dict(schema='n2-isolated-suite-admission-v1', created_utc=datetime.now(timezone.utc).isoformat(),
        source=str(source), source_receipt=bound(receipt) if receipt.is_file() else None,
        source_bindings=bindings, auxiliary_files=auxiliary, tool_snapshots=snapshots,
        modules=modules, cpu=args.cpu, module_timeout_seconds=args.timeout_seconds,
        interpreter=bound(sys.executable), runner=bound(__file__), child_helper=bound(HERE/'suite_child.py'),
        io_helper=bound(HERE/'io_utils.py'), launcher=bound(launcher), N2_TEST_E1='1',
        numerical_threads=1, CUDA_VISIBLE_DEVICES='', output=str(output))
    atomic(output/'ADMISSION.json', admission)
    rows = []; started = time.monotonic()
    for module in modules:
        folder = output/'modules'/module.rsplit('.', 1)[1]; folder.mkdir(parents=True)
        command = [sys.executable, '-B', str(launcher), '--receipt-dir', str(folder),
                   '--timeout-seconds', str(args.timeout_seconds), CHILD_MODULE]
        atomic(folder/'COMMAND.json', dict(argv=command, cwd=str(source.parent), module=module,
            source=str(source), N2_TEST_E1='1', cpu=args.cpu))
        report = aggregate(admission, rows); report.update(active_module=module, elapsed_seconds=time.monotonic()-started)
        atomic(output/'PROGRESS.json', report)
        process = None; created = None; launch_error = None; returncode = None
        try:
            with (folder/'LAUNCH_OUTPUT.log').open('xb') as log:
                process = subprocess.Popen(command, cwd=source.parent,
                    env=dict(environment, N2_SUITE_MODULE=module), stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                created = psutil.Process(process.pid).create_time()
                atomic(folder/'OWNER.json', dict(pid=process.pid, create_time=created, module=module))
                returncode = process.wait(timeout=args.timeout_seconds+30)
        except BaseException as exc:
            launch_error = traceback.format_exc()
            if process is not None and process.poll() is None and created is not None:
                stop_owned(process, created)
            atomic(folder/'LAUNCH_FAILURE.json', dict(error=repr(exc), traceback=launch_error))
            if isinstance(exc, (KeyboardInterrupt, SystemExit)): raise
        row = inspect_module(folder, module, returncode)
        row.update(command=bound(folder/'COMMAND.json'), source=bindings['tests/'+module.rsplit('.', 1)[1]+'.py'])
        if launch_error: row.update(status='FAILED', successful=False, launch_error=launch_error)
        rows.append(row); atomic(folder/'RESULT.json', row)
        print(json.dumps(dict(module=module, status=row['status'], tests=row['tests'], skipped=row['skipped'],
                              finished_modules=len(rows), requested_modules=len(modules))), flush=True)
    unchanged = (source_bindings(source) == bindings
        and all(item == bound(item['path']) for item in auxiliary.values())
        and all(admission[field] == bound(admission[field]['path']) for field in ('runner', 'child_helper', 'io_helper')))
    report = aggregate(admission, rows)
    report.update(admission=bound(output/'ADMISSION.json'), elapsed_seconds=time.monotonic()-started,
                  source_unchanged=unchanged)
    if not unchanged: report.update(status='FAILED', successful=False, source_error='Source changed while tests ran')
    atomic(output/'RESULT.json', report); atomic(output/'PROGRESS.json', report)
    return 0 if report['successful'] else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='Frozen prototype directory')
    parser.add_argument('--output', required=True, help='Fresh private receipt directory')
    parser.add_argument('--cpu', type=int, required=True)
    parser.add_argument('--timeout-seconds', type=float, default=240)
    args = parser.parse_args()
    if not 1 <= args.timeout_seconds <= 1800: parser.error('Module timeout must be 1..1800 seconds')
    return run(args)


if __name__ == '__main__': raise SystemExit(main())
