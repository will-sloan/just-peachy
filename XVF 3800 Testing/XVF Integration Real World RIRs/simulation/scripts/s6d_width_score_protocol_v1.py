"""Offline same-process scorer protocol; README_S6D_WIDTH_SCORE_PROTOCOL.md."""
from __future__ import annotations
import _thread
import argparse
import csv
from datetime import datetime, timezone
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

PLAN_SHA = '5504e9a6cd49767816ad7dc17c913f5a4f3a76db44f0f235ed30153a619a05dd'
SCORER_SHA = '2ff5541276d66332392d43400b21494b63c65ee79f29e65e424a45a8ee238939'
RUN_ID = '20260913T195357Z'
ROOT_OWNER_ID = '01a0812d-3ff0-7ed0-a06c-4df61b62a459'
JOBS = [f'S6D_{parent}_W{width:02d}_{tap}' for parent in ('C079', 'C120') for width in (2, 5, 10, 20) for tap in ('O0', 'O1')]
POPS = {'PRIMARY_NONOVERLAP': 156, 'COMPLETE_OVERLAP': 47, 'INCOMPLETE_REFERENCE': 26, 'STRICT_EMPTY_REFERENCE': 11}
TABLES = ('SCENE_RESULTS.csv', 'TURN_RESULTS.csv', 'PROFILE_RESULTS.csv', 'SHORT_REPLY_RESULTS.csv', 'REGION_RESULTS.csv',
          'TRACK_LIFECYCLE_RESULTS.csv', 'RECIPE_COST_RESULTS.csv', 'STRATA_RESULTS.csv', 'PAIRED_COMPARISONS.csv', 'COVERAGE.csv')
AGGREGATES = ('PROFILE_RESULTS.json', 'PAIRED_UNCERTAINTY_LEXICAL.json', 'PAIRED_UNCERTAINTY_CP_VIEWS.json', 'PER_CASE_ADVERSE_DELTAS.json', 'DEPENDENCY_PLAN.json')


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def bind(path, expected=None, checkpoint=None):
    path = Path(path).resolve()
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as handle:
        while True:
            if checkpoint:
                checkpoint()
            block = handle.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    after = path.stat()
    value = dict(path=str(path), bytes=after.st_size, sha256=h.hexdigest())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or expected is not None and value['sha256'] != expected:
        raise ValueError('Changed bound file: ' + str(path))
    return value


def verify(value, checkpoint=None):
    actual = bind(value['path'], value['sha256'], checkpoint)
    if actual['bytes'] != value['bytes']:
        raise ValueError('Declared byte count changed')
    return actual


def read(path, max_bytes=None):
    path = Path(path)
    if max_bytes is not None and path.stat().st_size > max_bytes:
        raise ValueError('Bounded JSON size exceeded')
    if max_bytes is None:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    with path.open('rb') as handle:
        raw = handle.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError('Bounded JSON size exceeded during read')
    return json.loads(raw.decode('utf-8-sig'))


def save(path, value, *, exclusive=False, before_publish=None):
    """Unique temporary + bounded Windows sharing/access retry, never partial JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    for attempt in range(6):
        try:
            if before_publish:
                before_publish()
            if exclusive:
                if path.exists():
                    raise FileExistsError(str(path))
                os.rename(temp, path)  # On Windows, an existing target cannot be replaced.
            else:
                os.replace(temp, path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(min(.02 * 2 ** attempt, .25))
    # Any failed publish retains its unique temporary as explicit evidence.


def same_owner(value, owner):
    try:
        return (all(value.get(key) == owner[key] for key in ('run_id', 'job_id', 'child_run_id', 'pid'))
                and abs(value.get('creation_time', 0) - owner['creation_time']) < .001)
    except (AttributeError, TypeError, ValueError):
        return False


def runtime_owner(auth):
    owner = {key: os.environ[env] for key, env in (('run_id', 'S6D_RUN_ID'), ('job_id', 'S6D_JOB_ID'), ('child_run_id', 'S6D_CHILD_RUN_ID'))}
    owner.update(pid=os.getpid(), creation_time=psutil.Process().create_time())
    if (owner['run_id'] != RUN_ID or auth.get('run_id') != owner['run_id'] or auth.get('job_id') != owner['job_id']
            or auth.get('owner_thread_id') != ROOT_OWNER_ID or auth.get('owner_session_id') != ROOT_OWNER_ID):
        raise ValueError('Root admission and actual runner identity differ')
    return owner


def key(row):
    return row.get('candidate_id', row.get('profile_id')), row['stream'], row['case_id']


def make_contract(plan, plan_binding, indices):
    """Metadata-only contract, also usable with tiny synthetic plans in fixtures."""
    prediction_rows = [row for binding in indices for row in read(binding['path'])['rows']]
    prediction_map = {key(row): row['result'] for row in prediction_rows}
    new = {}
    for cell in plan['new_cells']:
        cell_key = key(cell)
        prediction = prediction_map[cell_key]
        if Path(prediction['path']).resolve() != Path(cell['expected_prediction_path']).resolve():
            raise ValueError('Prediction index changed a declared cell path')
        identity = dict(schema='s6d-width-score-identity.v1', adapter_plan=plan_binding, prediction=prediction,
                        support=cell['support'], bank=plan['bank'], codes=plan['scorer_codes'],
                        adapter_sources=plan['adapter_sources'], packages=plan['packages'])
        target = Path(plan['bulk_score_payload_root']) / cell['candidate_id'] / cell['case_id'] / (cell['stream'] + '.json')
        new[cell_key] = dict(path=target, identity=identity, analysis_key=digest(identity), cell=cell)
    controls = {key(row): row for row in plan['controls']}
    if len(new) != len(plan['new_cells']) or len(controls) != len(plan['controls']) or set(new) & set(controls):
        raise ValueError('Nonunique or overlapping score/control cells')
    return dict(plan=plan, plan_binding=plan_binding, indices=indices, new=new, controls=controls, report=Path(plan['analysis_report_root']))


def read_score(expected, checkpoint=None):
    path = expected['path']
    if path.stat().st_size > 16 * 1024 ** 2:
        raise ValueError('Per-score JSON exceeds bounded observer size')
    first = bind(path, checkpoint=checkpoint)
    value = read(path, 16 * 1024 ** 2)
    cell = expected['cell']
    if (value.get('schema') != 'jp_s6c_core_analysis.v3' or key(value) != key(cell)
            or value.get('identity_tap') != cell['identity_tap'] or value.get('population') != cell['population']
            or value.get('analysis_identity') != expected['identity'] or value.get('analysis_key') != expected['analysis_key']):
        raise ValueError('Score identity/schema/population differs')
    if (set(value.get('text_metrics', {})) != {'first_final', 'latest_revised', 'first_display_label_final_words'}
            or not isinstance(value.get('turns'), list) or not isinstance(value.get('regions'), list)
            or not isinstance(value.get('lifecycle'), dict)):
        raise ValueError('Incomplete scientific score payload')
    if bind(path, checkpoint=checkpoint) != first:
        raise ValueError('Score changed during observer read')
    return first


class Observer:
    def __init__(self, owner, heartbeat, stop, contract, interval=5.):
        self.owner, self.heartbeat, self.stop = owner, Path(heartbeat), Path(stop)
        self.contract, self.interval = contract, interval
        self.closed = threading.Event()
        self.errors = []
        self.stop_requested = False
        self.invalid_stop_since = None
        self.committed = {}
        self.finalizing = False
        self.final_validated_count = 0
        self.next_final_heartbeat = 0.
        self.thread = threading.Thread(target=self.observe, name='s6d-score-protocol', daemon=True)

    def check_stop(self, *, final=False):
        if self.stop.exists():
            try:
                request = read(self.stop, 65536)
                if same_owner(request, self.owner):
                    self.stop_requested = True
                self.invalid_stop_since = None
            except (OSError, ValueError) as exc:
                if self.invalid_stop_since is None:
                    self.invalid_stop_since = time.monotonic()
                if final or time.monotonic() - self.invalid_stop_since >= 2:
                    self.errors.append('Unresolved STOP document: ' + repr(exc))
                    raise RuntimeError('Cannot establish final STOP state') from exc
        if self.stop_requested and final:
            raise RuntimeError('Matching STOP prevents completion')
        return self.stop_requested

    def checkpoint(self):
        self.check_stop(final=True)
        if self.errors:
            raise RuntimeError('Observer failure prevents completion')
        # Main owns final validation after close. Keep liveness fresh without
        # incrementing scientific progress or recursing through this checkpoint.
        if self.finalizing and self.closed.is_set() and time.monotonic() >= self.next_final_heartbeat:
            self.next_final_heartbeat = time.monotonic() + self.interval
            self.publish('FINALIZING')

    def begin_finalization(self):
        self.finalizing = True
        self.final_validated_count = 0
        self.next_final_heartbeat = 0.
        self.checkpoint()

    def scan(self, *, final=False):
        validated = {} if final else None
        for cell_key, expected in self.contract['new'].items():
            if final:
                self.checkpoint()
            elif self.closed.is_set() or self.check_stop():
                return
            if not final and cell_key in self.committed or not expected['path'].exists():
                continue
            try:
                def checkpoint():
                    if final:
                        self.checkpoint()
                    elif self.closed.is_set() or self.check_stop():
                        raise InterruptedError('Observer scan closing')
                binding = read_score(expected, checkpoint)
                if final and cell_key in self.committed and self.committed[cell_key] != binding:
                    raise ValueError('Previously committed score changed before final validation')
                self.committed[cell_key] = binding
                if final:
                    validated[cell_key] = binding
                    self.final_validated_count = len(validated)
            except (OSError, ValueError, TypeError, KeyError):
                if final:
                    raise
                # Frozen scorer's immutable writer can still be writing this name.
                continue
        if final:
            self.committed = validated

    def publish(self, status='RUNNING'):
        save(self.heartbeat, dict(self.owner, utc=utc(), status=status, progress_count=len(self.committed),
             committed_new_scores=len(self.committed), requested_new_scores=len(self.contract['new']),
             phase='FINAL_VALIDATION' if self.finalizing else 'SCORING' if len(self.committed) < len(self.contract['new']) else 'AGGREGATION_NOT_YET_ACCEPTED',
             final_validated_scores=self.final_validated_count,
             queue_age_s=None, stop_requested=self.stop_requested, protocol_errors=self.errors,
             progress_scope='Exact fully parsed score identities only; heartbeat and partial aggregate files do not advance progress'))

    def observe(self):
        last = 0.
        try:
            while not self.closed.is_set():
                if self.check_stop():
                    _thread.interrupt_main()
                    return
                if time.monotonic() - last >= self.interval:
                    self.scan()
                    if self.closed.is_set():
                        return
                    self.publish()
                    last = time.monotonic()
                self.closed.wait(.2)
        except BaseException as exc:
            self.errors.append(repr(exc))
            _thread.interrupt_main()

    def close(self):
        self.closed.set()
        self.thread.join(3)
        if self.thread.is_alive():
            raise RuntimeError('Scoring observer did not close within3 seconds')


def validate_final(contract, observer):
    observer.scan(final=True)
    if len(observer.committed) != len(contract['new']):
        raise ValueError('Missing committed scientific score cells')
    report, plan = contract['report'], contract['plan']
    receipt_path = report / 'SCORING_RECEIPT.json'
    receipt_binding = bind(receipt_path, checkpoint=observer.checkpoint)
    receipt = read(receipt_path)
    checks = dict(status=receipt.get('status') == 'COMPLETE_BOUNDED_MATRIX_SCORING',
        schema=receipt.get('schema') == 's6d-width-scoring-receipt.v1', exact_plan=receipt.get('adapter_plan') == contract['plan_binding'],
        exact_indices=receipt.get('prediction_indices') == contract['indices'],
        new_cells=receipt.get('scored_new_cells') == len(contract['new']), reused_controls=receipt.get('reused_exact_control_cells') == len(contract['controls']),
        total_cells=receipt.get('total_scored_cells') == len(contract['new']) + len(contract['controls']),
        raw_words=receipt.get('raw_word_invariance_cells') == len(contract['new']),
        populations=receipt.get('population_counts_per_route') == plan['populations_per_route'],
        scorer_codes=receipt.get('scorer_codes') == plan['scorer_codes'],
        diagnostics=receipt.get('diagnostic_context') == plan['diagnostics_context'] and receipt.get('diagnostics_are_only_width25') is True,
        no_models=receipt.get('model_calls') == 0, no_hardware=receipt.get('hardware_calls') == 0,
        native_confirmation=receipt.get('native_confirmation_required_before_retention') is True)
    if not all(checks.values()):
        raise ValueError('Scorer completion evidence differs: ' + repr(checks))
    artifacts = receipt.get('tables', []) + receipt.get('other_artifacts', [])
    paths = [Path(b['path']).resolve() for b in artifacts]
    if len(paths) != len(TABLES + AGGREGATES) or set(paths) != {(report / name).resolve() for name in TABLES + AGGREGATES}:
        raise ValueError('Exact aggregate artifact set required')
    for binding in artifacts:
        verify(binding, observer.checkpoint)
    expected_keys = set(contract['new']) | set(contract['controls'])
    coverage = {}
    with (report / 'COVERAGE.csv').open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            observer.checkpoint()
            row_key = key(row)
            if row_key in coverage or row_key not in expected_keys:
                raise ValueError('Duplicate/outside-grid coverage row')
            score_binding = json.loads(row['result'])
            expected_binding = observer.committed.get(row_key, contract['controls'].get(row_key, {}).get('score'))
            if score_binding != expected_binding:
                raise ValueError('Coverage score binding differs')
            expected_status = 'SCORED' if row_key in contract['new'] else 'REUSED_EXACT_BOUND_SCORER_RESULT'
            if row['status'] != expected_status or row_key in contract['new'] and row.get('raw_words_invariant') != 'True':
                raise ValueError('Unsuccessful or unverified coverage row')
            verify(score_binding, observer.checkpoint)
            coverage[row_key] = score_binding
    if set(coverage) != expected_keys:
        raise ValueError('Coverage misses a declared score/control cell')
    scene_keys = set()
    with (report / 'SCENE_RESULTS.csv').open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            observer.checkpoint()
            row_key = key(row)
            expected = contract['new'].get(row_key, {}).get('cell', contract['controls'].get(row_key))
            if expected is None or row_key in scene_keys or row['population'] != expected['population'] or row['identity_tap'] != row['stream']:
                raise ValueError('Scene table identity/population coverage differs')
            scene_keys.add(row_key)
    if scene_keys != expected_keys:
        raise ValueError('Scene table omits a requested cell')
    verify(receipt_binding, observer.checkpoint)
    return dict(receipt=receipt_binding, checks=checks, committed_new_scores=len(observer.committed), exact_coverage_cells=len(coverage),
                exact_scene_cells=len(scene_keys), bound_aggregate_artifacts=len(artifacts))


def run_protocol(contract, owner, paths, invoke, recheck):
    """No production admission bypass: CLI builds this only after fixed-hash admission.

    Tiny fake scorer fixtures call this lower orchestration API with synthetic
    contracts; production passes the original scorer.execute callable unchanged.
    """
    for name in ('heartbeat', 'completion'):
        if Path(paths[name]).exists():
            raise ValueError('Fresh protocol outputs required')
    if contract['report'].exists() or Path(contract['plan']['bulk_score_payload_root']).exists():
        raise ValueError('Fresh scoring output roots required; no implicit restart')
    observer = Observer(owner, paths['heartbeat'], paths['stop'], contract)
    failure, proof = None, None
    try:
        observer.checkpoint()
        observer.thread.start()
        invoke()
        observer.checkpoint()
    except BaseException as exc:
        failure = type(exc).__name__ + ': ' + str(exc)
    finally:
        try:
            if observer.thread.ident is not None:
                observer.close()
        except BaseException as exc:
            failure = failure or repr(exc)
    if failure is None:
        try:
            observer.begin_finalization()
            proof = validate_final(contract, observer)
            recheck(observer.checkpoint)
            observer.checkpoint()
        except BaseException as exc:
            failure = type(exc).__name__ + ': ' + str(exc)
    result = dict(owner, status='FAILED' if failure else 'COMPLETE', failure=failure, semantic_checks=proof,
        protocol_observer_closed=not observer.thread.is_alive(), protocol_errors=observer.errors,
        stop_requested=observer.stop_requested, committed_new_scores=len(observer.committed),
        adapter_plan=contract['plan_binding'], prediction_indices=contract['indices'], wrapper=bind(__file__),
        admission=contract.get('admission'), scorer=contract['plan']['adapter_sources'][0], scoring_complete=failure is None,
        hardware_calls=0, model_calls=0, scope='Exact bounded scorer evidence only; no native, physical, policy or aggregate S6D completion claim')
    def final_gate():
        observer.checkpoint()
        recheck(observer.checkpoint)
        observer.checkpoint()
    if failure is None:
        try:
            observer.publish('FINALIZING')
            save(paths['completion'], result, exclusive=True, before_publish=final_gate)
        except BaseException as exc:
            failure = type(exc).__name__ + ': ' + str(exc)
            result.update(status='FAILED', failure=failure, stop_requested=observer.stop_requested, scoring_complete=False)
    if failure is not None:
        try:
            observer.publish('FAILED')
            save(Path(paths['completion']).with_name('SCORER_PROTOCOL_FAILURE.json'), result, exclusive=True)
        except BaseException as exc:
            result['failure_receipt_write_error'] = repr(exc)
    return result


def execute(plan_path, authorization, prediction_indices):
    plan_binding = bind(plan_path, PLAN_SHA)
    plan = read(plan_path)
    auth_binding = bind(authorization)
    auth = read(authorization)
    indices = [bind(path) for path in prediction_indices]
    if (auth.get('root_review_passed') is not True or auth.get('adapter_plan_sha256') != PLAN_SHA or auth.get('prediction_indices') != indices
            or plan['expected_jobs'] != JOBS or len(plan['new_cells']) != 3840 or len(plan['controls']) != 1920
            or plan['populations_per_route'] != POPS):
        raise ValueError('Exact complete matrix and root scorer admission required')
    owner = runtime_owner(auth)
    helper_binding = verify(plan['adapter_sources'][0])
    if helper_binding['sha256'] != SCORER_SHA or Path(helper_binding['path']).name != 's6d_angle_width_score.py':
        raise ValueError('Wrong frozen scorer helper')
    wrapper_binding = bind(__file__)
    if auth.get('protocol_wrapper_sha256') != wrapper_binding['sha256']:
        raise ValueError('Root admission must bind this exact protocol wrapper')
    rows, jobs = [], []
    for binding in indices:
        index = read(binding['path'])
        if index.get('status') != 'COMPLETE_ADMITTED_POLICY_REPLAY_ONLY' or index.get('source_plan') != plan['width_plan']:
            raise ValueError('Prediction index incomplete or bound to a different plan')
        rows.extend(index['rows']); jobs.extend(index['jobs'])
    expected = {key(row) for row in plan['new_cells']}
    if (len(rows) != 3840 or len({key(row) for row in rows}) != 3840 or {key(row) for row in rows} != expected
            or sorted(jobs) != sorted(JOBS) or any(row.get('status') != 'COMPLETE' for row in rows)):
        raise ValueError('Literal3840-cell/16-job prediction index coverage required')
    frozen = [plan_binding, auth_binding, wrapper_binding] + plan['adapter_sources'] + plan['scorer_codes'] + indices
    def recheck(checkpoint):
        for binding in frozen:
            verify(binding, checkpoint)
    recheck(lambda: None)
    contract = make_contract(plan, plan_binding, indices)
    contract['admission'] = auth_binding
    paths = {key: Path(os.environ[env]) for key, env in (('heartbeat', 'S6D_HEARTBEAT_PATH'), ('completion', 'S6D_COMPLETION_PATH'), ('stop', 'S6D_STOP_REQUEST_PATH'))}
    # Only the already frozen helper is loaded; no globals or registry changed.
    sys.path.insert(0, str(Path(helper_binding['path']).parent))
    spec = importlib.util.spec_from_file_location('s6d_bound_score_adapter', helper_binding['path'])
    helper = importlib.util.module_from_spec(spec); sys.modules[spec.name] = helper; spec.loader.exec_module(helper)
    result = run_protocol(contract, owner, paths,
        lambda: helper.execute(Path(plan_path), Path(authorization), [Path(b['path']) for b in indices]), recheck)
    result['admission'] = auth_binding
    print(json.dumps({key: result.get(key) for key in ('status', 'failure', 'committed_new_scores', 'semantic_checks', 'failure_receipt_write_error')}, indent=2), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter-plan', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--prediction-indices', nargs='+', type=Path, required=True)
    args = parser.parse_args()
    result = execute(args.adapter_plan, args.authorization, args.prediction_indices)
    raise SystemExit(0 if result['status'] == 'COMPLETE' else 2)
