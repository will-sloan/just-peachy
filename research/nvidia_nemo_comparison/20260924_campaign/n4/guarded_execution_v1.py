"""Explicit resource provenance for unchanged V3 methods; README_GUARDED_BANK_V1.md."""
from datetime import datetime, timezone
from pathlib import Path
import shutil

from common import bind, freeze, load, verify
from metric_process import exact_process
from reservation_budget_v1 import calculate, owner_key, read_closed_components, require
from reservation_census_v1 import (admission_paths, classify, epoch, output_argument,
    validate_live, validate_supervision, visible_python_census)
from reservation_census_v2 import read_fixtures
from reservation_guard_v1 import OutputGuard, exact_projection

HERE = Path(__file__).resolve().parent
OWN = ('guarded_execution_v1.py', 'guarded_method_bank_v1.py',
       'guarded_scoring_v1.py', 'guarded_review_v1.py', 'probe_guarded_bank_v1.py',
       'test_guarded_bank_v1.py', 'README_GUARDED_BANK_V1.md')
SCHEMA = 'just-peachy.guarded-v3-execution.v1'


def code_bindings():
    """Read source manifests without importing prediction/application modules."""
    from reservation_guard_v1 import code_bindings as guard_code
    values = guard_code()+load(HERE/'RESERVATION_GUARD_CHECK_V1.json')['probe_code']
    values += [bind(HERE/'RESERVATION_GUARD_CHECK_V1.json')]
    for name, key in [('INTEGRATED_HISTORY_CHECK_V3.json', 'code'),
                      ('SCORING_HISTORY_CHECK_V3.json', 'review_code')]:
        values += load(HERE/name)[key] + [bind(HERE/name)]
    values += [bind(HERE/n) for n in OWN]
    result = {}
    for b in values:
        require(b['path'] not in result or result[b['path']] == b, 'Conflicting source manifests')
        result[b['path']] = b
    return list(result.values())


def qualification():
    path = HERE/'GUARDED_BANK_CHECK_V1.json'; q = load(path)
    require(q['status'] == 'PASS_GUARDED_V3_MODELED_FAMILY_ONLY'
            and q['code'] == code_bindings() and q['exact_probe_owner_exited'] is True,
            'Guarded execution family is not qualified')
    for b in q['code']+[q['private_result']]: verify(b)
    require(exact_process(q['probe_owner']) is None, 'Family probe remains active')
    return bind(path)


def classify_dispatch(path, local, *, lookup=exact_process):
    """Accept both retained supervisor-start field names, with exact joins."""
    a = load(path)
    if a.get('owner') is not None or 'worker_spec' not in a:
        return classify(path, local, lookup=lookup)
    ab = bind(path); root = Path(path).parent; sb = a['worker_spec']; verify(sb)
    target = output_argument(load(sb['path'])['argv'], local)
    require(target != root and not target.is_relative_to(root) and not root.is_relative_to(target),
            'Dispatch overlaps its delegated output')
    started = bind(root/'STARTED.json'); launch = load(started['path'])
    require(launch['worker_spec'] == sb, 'Dispatch start/spec join differs')
    keys = [k for k in ('supervisor_start', 'supervisor') if k in launch]
    require(len(keys) == 1, 'Ambiguous dispatch supervisor fields')
    if keys[0] == 'supervisor':
        require(launch.get('admission') == ab, 'New dispatch admission/start join differs')
    start = launch[keys[0]]; host = {k: start[k] for k in ('pid', 'create_time')}; owner_key(host)
    target_ab = bind(target/'ADMISSION.json'); driver = load(target_ab['path'])['owner']; owner_key(driver)
    require(lookup(host) is None or lookup(driver) is not None, 'Live host has no admitted driver')
    return dict(kind='DELEGATED_DISPATCH', state='ALIAS_NOT_SECOND_ALLOCATION',
        admission=ab, root=str(root), delegate=target_ab, supervisor=host,
        dependencies=[ab, sb, started, target_ab])


def snapshot(local, main_plan):
    """Same V2 complete census; only the dispatch schema reader is extended."""
    from asr_full_bank import payload_inventory
    local = Path(local).resolve(strict=True); state = local/'supervision'
    fb = load(HERE/'RESERVATION_CENSUS_FIXTURES_V2.json')['manifest']
    fixtures = read_fixtures(fb, local); closed = read_closed_components(main_plan)
    worker = load(state/'worker.json'); spec = load(state/'worker_spec.json'); before = epoch(worker, spec)
    paths = admission_paths(local/'n4')
    require(set(fixtures).issubset(paths), 'A recorded fixture disappeared')
    records = [fixtures[p] if p in fixtures else classify_dispatch(p, local) for p in paths]
    active = [validate_live(r, local) for r in records if r['state'] == 'ACTIVE']
    require(len({owner_key(a['owner']) for a in active}) == len(active), 'Duplicate active owner')
    require(epoch(load(state/'worker.json'), load(state/'worker_spec.json')) == before, 'Supervisor changed during census')
    supervision = validate_supervision(load(state/'worker.json'), spec, active)
    visible = visible_python_census(local, HERE, active, supervision)
    inventory = payload_inventory(local); policy_binding = bind(state/'campaign.json')
    policy = load(policy_binding['path']); free = {d: shutil.disk_usage(d+'/').free for d in ('C:', 'G:')}
    calculation = calculate(inventory, closed, active, 1, policy, free, datetime.now(timezone.utc))
    require(admission_paths(local/'n4') == paths, 'Admission set changed during census')
    for record in records:
        for b in record['dependencies']: verify(b)
        if record['state'] == 'ACTIVE': require(exact_process(record['owner']) is not None, 'Live owner exited')
        if record['state'] == 'CLOSED_OWNER': require(exact_process(record['owner']) is None, 'Closed owner changed')
        if record['state'] == 'NON_EXECUTION_FIXTURE': require(exact_process(record['parent_owner']) is None, 'Fixture owner changed')
    require(epoch(load(state/'worker.json'), load(state/'worker_spec.json')) == before, 'Supervisor changed during census')
    validate_supervision(load(state/'worker.json'), spec, active)
    visible_python_census(local, HERE, active, supervision)
    verify(main_plan); verify(policy_binding); verify(fb)
    return dict(records=records, active_allocations=active, supervisor=supervision,
        visible_N4_python_processes=visible, inventory=inventory, closed_components=closed,
        fixture_manifest=fb, preserved_fixture_count=len(fixtures), all_physical_fixture_bytes_retained=True,
        policy=policy_binding, free_bytes=free, calculation=calculation,
        complete_recorded_N4_admission_census=True, active_set_supplied_by_caller=False,
        whole_host_exclusivity_proved=False, worker_execution_authorized=False, N4_accepted=False, N5_complete=False)


class Guard(OutputGuard):
    def refresh(self, peak=0):
        self.fast_check(peak); observed = snapshot(self.local, self.main_plan)
        require(next(a for a in observed['active_allocations'] if a['owner'] == self.owner)['admission']
                == self.admission, 'Census own admission differs')
        verify(observed['policy']); require(observed['policy'] == self.policy_binding, 'Policy changed')
        projection = exact_projection(observed, self.owner, self.output, load(observed['policy']['path']),
            datetime.now(timezone.utc), peak, production=self.production)
        self.fast_check(peak)
        for b in self.code: verify(b)
        self.last_check = dict(observed=observed, projection=projection,
            allocation_lock='reservation-guard.owner.lock', supervisor_writer_lock_held=False,
            whole_host_exclusivity_proved=False, N4_accepted=False, N5_complete=False)
        return self.last_check


def envelope(plan_binding, kind, cap, seconds, *, development=False):
    require(kind in ('method', 'method-review', 'scoring', 'score-review', 'probe'), 'Unknown family role')
    require(type(development) is bool and (kind == 'probe') == development, 'Explicit probe scope required')
    require(type(seconds) is int and 0 < seconds <= 14400, 'Invalid elapsed budget')
    require(type(cap) is int and 1024**2 < cap <= 8*1024**3, 'Invalid output cap')
    verify(plan_binding)
    return dict(schema=SCHEMA, kind=kind, original_plan=plan_binding, code=code_bindings(),
        qualification=None if development else qualification(), allocation_bytes=cap,
        maximum_seconds=seconds, development_only=development,
        prediction_implementation='UNCHANGED_QUALIFIED_V3', N4_accepted=False, N5_complete=False)


def check_envelope(value, plan_binding, kind, *, expected_code=None, qualified=None):
    code = code_bindings() if expected_code is None else expected_code
    q = qualification() if qualified is None else qualified
    require(value.get('schema') == SCHEMA and value.get('kind') == kind
            and value.get('original_plan') == plan_binding and value.get('code') == code
            and value.get('qualification') == q and value.get('development_only') is False
            and value.get('prediction_implementation') == 'UNCHANGED_QUALIFIED_V3', 'Execution envelope differs')
    require(type(value.get('maximum_seconds')) is int and 0 < value['maximum_seconds'] <= 14400
            and type(value.get('allocation_bytes')) is int and 1024**2 < value['allocation_bytes'] <= 8*1024**3,
            'Execution budget differs')


def check_cell(value, row, plan_binding, execution_binding):
    require(value.get('execution_plan') == execution_binding and value.get('plan') == plan_binding,
            'Cell execution provenance differs')
    require(all(value[k] == row[k] for k in ('cell_id', 'job_id', 'cache_key', 'parents', 'contract')),
            'Cell numerical contract differs')
    require(not any(k in value for k in ('execution_source', 'reused_from')),
            'Guarded modes bank cannot claim prefix reuse')


def validate_execution(run, *, kind='method'):
    """Pure metadata gate; never imports a prediction/application module."""
    run = Path(run).resolve(strict=True); result = load(run/'RESULT.json')
    ab = bind(run/'ADMISSION.json'); a = load(ab['path']); eb = bind(run/'EXECUTION_PLAN.json')
    require(result['admission'] == ab and a['execution_plan'] == eb and result['execution_plan'] == eb,
            'Execution admission/terminal join differs')
    require(a['code'] == code_bindings() and exact_process(a['owner']) is None, 'Producer source changed or remains active')
    check_envelope(load(eb['path']), a['plan'], kind)
    require(a['allocation_bytes'] == load(eb['path'])['allocation_bytes']
            and a['maximum_seconds'] == load(eb['path'])['maximum_seconds'], 'Admitted limits differ')
    checks = result['guard_checks']
    require(len(checks) >= 2 and len({b['path'] for b in checks}) == len(checks)
            and Path(checks[0]['path']).name == 'GUARD_INITIAL.json'
            and Path(checks[-1]['path']).name == 'GUARD_FINAL.json', 'Initial and final resource checks required')
    for b in checks:
        verify(b); v = load(b['path'])
        require(Path(b['path']).parent == run and v['projection']['own_admission'] == ab
                and v['projection']['production_scope_checked'] is True
                and v['projection']['own_allocation_counted_once'] is True
                and v['projection']['other_allocation_count'] == 0, 'Resource proof differs')
    if kind == 'method':
        plan = load(a['plan']['path']); require(plan['scope'] == 'modes-panel', 'Only modes envelope is admitted')
        require(len(result['cells']) == result['completed'] <= plan['required'], 'Method prefix count differs')
        for i, b in enumerate(result['cells']):
            verify(b); require(Path(b['path']) == run/'cells'/f'{i:05d}'/'RESULT.json', 'Method cell path differs')
            check_cell(load(b['path']), plan['rows'][i], a['plan'], eb)
    for b in a['code']+[a['plan'],eb,ab]: verify(b)
    return dict(result=result, admission=a, execution_plan=eb, terminal=bind(run/'RESULT.json'))


def save_check(guard, name, peak=0):
    path = guard.output/name; freeze(path, guard.refresh(peak)); return bind(path)


def start_output(output, plan_binding, kind, cap, seconds, extra=None, *, development=False):
    from metric_process import identity, pin
    p = pin(); plan = load(plan_binding['path'])
    local = Path(plan['context']['source_receipt']['path']).parents[2]
    output = Path(output).resolve()
    require(not output.exists() and output.is_relative_to(local/'n4') and output != local/'n4', 'Fresh private output required')
    e = envelope(plan_binding, kind, cap, seconds, development=development)
    freeze(output/'EXECUTION_PLAN.json', e); eb = bind(output/'EXECUTION_PLAN.json')
    a = dict(owner=identity(p), plan=plan_binding, execution_plan=eb, code=e['code'],
        allocation_bytes=cap, maximum_seconds=seconds, cpu_affinity=p.cpu_affinity(),
        models_loaded=0, integrated_N4_cells=0)
    require(not set(extra or {}).intersection(a), 'Extra admission fields cannot replace provenance')
    a.update(extra or {}); freeze(output/'ADMISSION.json', a)
    main_plan = load(local/'n4/integrated-main-v3/RESULT.json')['plan']
    return Guard(local, output, e['code'], main_plan, seconds, production=True)


def admit_method(run, review):
    from scoring_bank_v3 import admit
    validate_execution(run, kind='method')
    require(review is not None and Path(review).name == 'RESULT.json', 'Guarded method review is required')
    validated = validate_execution(Path(review).parent, kind='method-review')
    require(validated['result']['terminal'] == bind(Path(run)/'RESULT.json'), 'Method review targets a different bank')
    return admit(Path(run), Path(review))
