"""Exact operational-width replay protocol; see README_S6D_WIDTH_PROTOCOL.md."""
from __future__ import annotations
import _thread
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid
import psutil

SIM = Path(__file__).resolve().parents[1]
RUN = SIM / 'reports/S6D/20260913T195357Z'
PLAN_SHA = 'c89cf5169fd4e53335714b34a2bc8111623e95800a74df38e05e9cb9fa7409c1'
HELPER_SHA = '69672b672312b692cab82e20586479ff6618857b843d6efdc8cdcb41c07dd33e'
RUNNER = RUN / 'runner/source_epoch_ready_v2/s6d_runner_v1.py'
RUNNER_SHA = '7a344ee68b3b2044e8fd7f74786eac57a2c3c5dc921caab639419fea2573f97c'
JOBS = [f'S6D_{parent}_W{width:02d}_{tap}' for parent in ('C079', 'C120')
        for width in (2, 5, 10, 20) for tap in ('O0', 'O1')]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def bind(path, expected=None):
    path = Path(path).resolve()
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError('Exact binding mismatch: ' + str(path))
    return {'path': str(path), 'bytes': len(data), 'sha256': digest}


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    # Windows readers/antivirus can briefly deny replacement of an open target.
    # Retry only sharing/access refusal; retain the old destination and the
    # prepared temporary file if all seven bounded attempts fail.
    for attempt in range(7):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 6:
                raise
            time.sleep(.025 * 2 ** attempt)


def module_at(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def identity():
    return {k: os.environ[e] for k, e in (
        ('run_id', 'S6D_RUN_ID'), ('job_id', 'S6D_JOB_ID'), ('child_run_id', 'S6D_CHILD_RUN_ID'))} | {
        'pid': os.getpid(), 'creation_time': psutil.Process().create_time()}


def same_owner(value, owner):
    return all(value.get(k) == owner[k] for k in ('run_id', 'job_id', 'child_run_id', 'pid')) and abs(value.get('creation_time', 0) - owner['creation_time']) < .001


class Observer:
    def __init__(self, owner, heartbeat, stop_request, cells_dir, interval=5, *, expected_cells=None):
        self.owner, self.heartbeat, self.stop_request = owner, Path(heartbeat), Path(stop_request)
        self.cells_dir, self.interval = Path(cells_dir), interval
        self.closed = threading.Event()
        self.errors = []
        self.stop_requested = False
        self.count = 0
        self.expected_cells = {r['cell_id']: r for r in (expected_cells or [])}
        self.committed = set()
        self.thread = threading.Thread(target=self.observe, name='s6d-width-protocol', daemon=True)

    def check_stop(self, *, raise_on_stop=False):
        if self.stop_request.exists() and same_owner(read(self.stop_request), self.owner):
            self.stop_requested = True
        if self.stop_requested and raise_on_stop:
            raise RuntimeError('Matching owner STOP_REQUEST before completion commit')
        return self.stop_requested

    def publish(self, status='RUNNING', *, final=False, scan=True):
        # Count committed immutable cell receipts only; liveness is not progress.
        if final and scan:
            self.committed.clear()
            self.count = 0
            self.check_stop(raise_on_stop=True)
        for path in self.cells_dir.glob('*.json') if scan else ():
            if final:
                self.check_stop(raise_on_stop=True)
            if self.closed.is_set() and not final:
                break
            if not final and self.check_stop():
                break
            if path.stem in self.committed or path.stem not in self.expected_cells:
                continue
            try:
                if path.stat().st_size > 1024 * 1024:
                    continue
                value = read(path)
                if not isinstance(value, dict):
                    continue
                expected = self.expected_cells[path.stem]
                result = value.get('result', {})
                if not isinstance(result, dict):
                    continue
                target = Path(expected['output_path']).resolve()
                if (value.get('raw_words_invariant') is True and value.get('cell') == expected
                        and Path(result.get('path', '')).resolve() == target
                        and target.is_file() and target.stat().st_size == result.get('bytes')
                        and isinstance(result.get('sha256'), str) and len(result['sha256']) == 64):
                    self.committed.add(path.stem)
            except (OSError, ValueError, TypeError, KeyError):
                # The underlying immutable writer can still be writing its final filename.
                # Partial/invalid receipts are unfinished; only final semantic validation admits results.
                continue
        self.count = len(self.committed)
        if final:
            self.check_stop(raise_on_stop=True)
        save(self.heartbeat, self.owner | {'utc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            'status': status, 'progress_count': self.count, 'completed_policy_cells': self.count,
            'total_policy_cells': 3840, 'queue_age_s': None, 'stop_requested': self.stop_requested,
            'error': self.errors})

    def observe(self):
        last = 0
        try:
            while not self.closed.is_set():
                if self.check_stop():
                    _thread.interrupt_main()
                    return
                if time.monotonic() - last >= self.interval:
                    self.publish()
                    last = time.monotonic()
                self.closed.wait(.2)
        except BaseException as exc:
            self.errors.append(repr(exc))
            _thread.interrupt_main()

    def close(self):
        self.closed.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError('Protocol observer did not close')


def validate_index(value, plan_binding, plan):
    key = lambda row: tuple(row[k] for k in ('candidate_id', 'case_id', 'stream', 'identity_tap'))
    expected = {key(row): Path(row['output_path']).resolve() for row in plan['cells']}
    actual_rows = value.get('rows', [])
    actual = {key(row): Path(row['result']['path']).resolve() for row in actual_rows}
    checks = {
        'complete': value.get('status') == 'COMPLETE_ADMITTED_POLICY_REPLAY_ONLY',
        'all_cells': value.get('completed') == value.get('requested') == len(value.get('rows', [])) == 3840,
        'exact_jobs': value.get('jobs') == JOBS,
        'exact_plan': value.get('source_plan') == plan_binding,
        'no_neural': value.get('new_neural_jobs') == 0,
        'no_hardware': value.get('hardware_jobs') == 0,
        'not_scored': value.get('scoring_complete') is False,
        'unique_cells': len({(r['candidate_id'], r['case_id'], r['stream']) for r in value.get('rows', [])}) == 3840,
        'exact_declared_cells_and_outputs': len(expected) == len(actual) == 3840 and actual == expected,
        'unique_output_paths': len(set(actual.values())) == 3840,
        'all_rows_complete': all(r.get('status') == 'COMPLETE' for r in value.get('rows', [])),
    }
    if not all(checks.values()):
        raise ValueError('Rejected incomplete/changed policy result: ' + repr(checks))
    for row in value['rows']:
        actual = bind(row['result']['path'], row['result']['sha256'])
        if actual['bytes'] != row['result']['bytes']:
            raise ValueError('Prediction byte count mismatch')
    return checks


def execute(plan_path, auth_path):
    plan_binding = bind(plan_path, PLAN_SHA)
    plan = read(plan_path)
    admission_binding = bind(auth_path)
    auth = read(auth_path)
    if auth.get('root_review_passed') is not True or auth.get('plan_sha256') != PLAN_SHA or auth.get('allowed_jobs') != JOBS:
        raise ValueError('Exact root admission required')
    bind(plan['helper']['path'], HELPER_SHA)
    owner = identity()
    heartbeat, completion, stop = [Path(os.environ[e]) for e in ('S6D_HEARTBEAT_PATH', 'S6D_COMPLETION_PATH', 'S6D_STOP_REQUEST_PATH')]
    if heartbeat.exists() or completion.exists():
        raise ValueError('Fresh protocol paths required')
    helper = module_at(plan['helper']['path'], 's6d_width_reviewed_helper')
    report = Path(plan['output_root']) / 'executions' / ('jobs_' + helper.digest(JOBS)[:16])
    if report.exists():
        raise ValueError('Do not overwrite or silently restart partial policy outputs')
    observer = Observer(owner, heartbeat, stop, report / 'cells', expected_cells=plan['cells'])
    failure, checks, result_binding = None, None, None
    try:
        observer.thread.start()
        helper.execute(Path(plan_path), Path(auth_path), JOBS)
        if observer.stop_requested or observer.errors:
            raise RuntimeError('Protocol stop/failure')
        result_binding = bind(report / 'PREDICTION_INDEX.json')
        checks = validate_index(read(result_binding['path']), plan_binding, plan)
        bind(plan['helper']['path'], HELPER_SHA)
        bind(plan_path, PLAN_SHA)
        if bind(auth_path) != admission_binding:
            raise ValueError('Root admission changed during execution')
    except BaseException as exc:
        failure = type(exc).__name__ + ': ' + str(exc)
    finally:
        try:
            if observer.thread.ident is not None:
                observer.close()
        except BaseException as exc:
            failure = failure or repr(exc)
    if failure is None and not observer.errors and not observer.stop_requested:
        try:
            # The observer has joined. Main owns the one complete final scan;
            # background close never waits for an unbounded directory walk.
            observer.publish('FINALIZING', final=True)
            if observer.count != 3840:
                raise ValueError('Not every declared cell has a valid committed receipt')
            if bind(auth_path) != admission_binding:
                raise ValueError('Root admission changed during final receipt validation')
        except BaseException as exc:
            failure = type(exc).__name__ + ': ' + str(exc)
    success = failure is None and not observer.errors and not observer.stop_requested
    observer.publish('COMPLETE' if success else 'FAILED', scan=False)
    result = owner | {'status': 'COMPLETE' if success else 'FAILED', 'failure': failure,
        'plan': plan_binding, 'admission': admission_binding, 'index': result_binding,
        'semantic_checks': checks, 'protocol_observer_closed': not observer.thread.is_alive(),
        'protocol_errors': observer.errors, 'stop_requested': observer.stop_requested,
        'policy_cells': observer.count, 'new_neural_jobs': 0,
        'hardware_jobs': 0, 'scoring_complete': False, 'wrapper': bind(__file__)}
    if success:
        try:
            observer.check_stop(raise_on_stop=True)
        except BaseException as exc:
            success = False
            result.update(status='FAILED', failure=type(exc).__name__ + ': ' + str(exc),
                          stop_requested=observer.stop_requested)
            observer.publish('FAILED', scan=False)
    save(completion if success else completion.with_name('WRAPPER_FAILURE.json'), result)
    print(json.dumps({k: result[k] for k in ('status', 'failure', 'policy_cells', 'index')}), flush=True)
    return success


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if execute(args.plan, args.authorization) else 2)
