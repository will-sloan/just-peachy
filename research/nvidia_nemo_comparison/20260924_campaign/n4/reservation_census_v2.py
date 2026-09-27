"""Fixture-aware read-only allocation census; README_RESERVATION_CENSUS_V2.md."""
import argparse
import ast
from datetime import datetime, timezone
from pathlib import Path
import shutil

from common import bind, freeze, load, verify
from metric_process import exact_process, pin
from reservation_budget_v1 import calculate, owner_key, read_closed_components, require
from reservation_census_v1 import (admission_paths, classify, epoch, execution_children,
    validate_live, validate_supervision, visible_python_census)

HERE = Path(__file__).resolve().parent
SCHEMA = 'just-peachy.recorded-test-admissions.v2'
PRODUCERS = {
    'restart-runner-probe-v1': ('probe_restart_runner.py', 'test_restart_runner.py'),
    'restart-review-probe-v1': ('probe_restart_review.py', 'test_restart_run_review.py'),
    'restart-plan-probe-v1': ('probe_restart_plan.py', 'test_restart_plan.py'),
    'restart-complete-review-probe-v1': ('probe_restart_complete.py', 'test_restart_run_review.py'),
    'restart-content-run-probe-v1': ('probe_restart_content_run.py', 'test_restart_run_review.py'),
    'restart-content-run-probe-v2': ('probe_restart_content_run.py', 'test_restart_run_review.py'),
    'restart-family-v2-probe-v1': ('probe_restart_family_v2.py', None),
    'restart-family-v2-probe-v2': ('probe_restart_family_v2.py', None),
    'continuity-application-plan-probe-v1': ('probe_continuity_application_plan.py', 'test_continuity_application_plan.py'),
    'paced-panel-plan-v4-probe-v1': ('probe_paced_panel_plan_v4.py', 'test_paced_panel_plan_v4.py'),
}


def fixture_source(relative):
    """Explicit reviewed producers, not a blanket tests-directory exclusion."""
    parts = relative.parts
    require(len(parts) >= 4 and parts[1] == 'tests' and parts[-1] == 'ADMISSION.json',
            'Not a reviewed test admission location')
    require(parts[0] in PRODUCERS, 'Unknown test producer')
    producer, test = PRODUCERS[parts[0]]
    if test is None:
        test = {'plans': 'test_restart_plan_v2.py', 'runner': 'test_restart_runner_v2.py',
                'stopped': 'test_restart_run_review_v2.py'}.get(parts[2])
        require(test is not None, 'Unknown test family')
    methods = [p for p in parts if p.startswith('test_')]
    if not methods:
        if parts[-2] == 'partial':
            method = ('test_production_reconstruction_refuses_partial_review'
                      if parts[0] == 'continuity-application-plan-probe-v1'
                      else 'test_production_reconstruction_refuses_partial_upstream')
        else:
            require(parts[0] == 'paced-panel-plan-v4-probe-v1' and parts[2:-1] == ('v4', 'live-owner'),
                    'Unknown method-free test location')
            method = 'test_exact_live_reviewer_is_rejected_before_qualification'
    else:
        require(len(methods) == 1, 'Ambiguous test method')
        method = methods[0]
    return producer, test, method


def admitted_source(actual, name, admission, parent):
    original = [b for b in admission['code'] if Path(b['path']) == HERE/name]
    require(len(original) == 1, 'Fixture producer or test source was not admitted')
    require(Path(actual['path']) in (HERE/name, parent/'source'/name), 'Foreign fixture source snapshot')
    require(all(actual[k] == original[0][k] for k in ('sha256', 'bytes')),
            'Fixture source bytes differ from the original admission')


def source_binding(name, admission, parent):
    """Use the preserved snapshot when an older failed probe bound older code."""
    for path in (HERE/name, parent/'source'/name):
        if path.exists():
            candidate = bind(path)
            try:
                admitted_source(candidate, name, admission, parent)
                return candidate
            except ValueError:
                continue
    raise ValueError('No unchanged admitted fixture source: '+name)


def validate_fixture(entry, local, *, lookup=exact_process):
    """Verify provenance and the real parent exit; never look up synthetic PIDs."""
    require(entry.get('classification') == 'PRESERVED_NON_EXECUTION_TEST_FIXTURE'
            and entry.get('physical_bytes_retained') is True, 'Fixture scope differs')
    keys = ('fixture', 'parent_admission', 'parent_terminal', 'producer', 'test_source', 'test_log')
    for key in keys:
        verify(entry[key])
    path = Path(entry['fixture']['path']).resolve(strict=True)
    root = Path(local).resolve(strict=True)/'n4'
    require(path.is_relative_to(root), 'Fixture escaped private N4')
    relative = path.relative_to(root)
    producer, test, method = fixture_source(relative)
    parent = root/relative.parts[0]
    require(Path(entry['parent_admission']['path']) == parent/'ADMISSION.json'
            and Path(entry['parent_terminal']['path']) in (parent/'RESULT.json', parent/'FAILED.json'),
            'Foreign fixture parent')
    require(Path(entry['test_log']['path']).parent == parent
            and Path(entry['test_log']['path']).suffix == '.txt', 'Foreign fixture log')
    require(entry['test_method'] == method, 'Fixture method differs')
    admission = load(entry['parent_admission']['path'])
    terminal = load(entry['parent_terminal']['path'])
    owner = admission['owner']; owner_key(owner)
    require(entry['parent_owner'] == owner, 'Fixture parent identity differs')
    require(lookup(owner) is None, 'Fixture producer is still active')
    require(terminal.get('admission') == entry['parent_admission'], 'Fixture parent terminal join differs')
    if 'owner' in terminal:
        require(terminal['owner'] == owner, 'Fixture terminal owner differs')
    require(all(lookup(x) is None for x in execution_children(terminal)), 'Fixture parent child remains active')
    admitted_source(entry['producer'], producer, admission, parent)
    admitted_source(entry['test_source'], test, admission, parent)
    tree = ast.parse(Path(entry['test_source']['path']).read_text(encoding='utf-8-sig'))
    require(any(isinstance(n, ast.FunctionDef) and n.name == method for n in ast.walk(tree)),
            'Fixture test method missing from admitted source')
    lines = Path(entry['test_log']['path']).read_text(encoding='utf-8-sig').splitlines()
    require(any(line.startswith(method+' ') and ' ... ' in line for line in lines),
            'Fixture test was not recorded in its parent log')
    return dict(kind='RECORDED_TEST_FIXTURE', state='NON_EXECUTION_FIXTURE',
        admission=entry['fixture'], root=str(path.parent), parent_owner=owner,
        fixture_method=method, physical_bytes_retained=True,
        dependencies=[entry[key] for key in keys])


def read_fixtures(manifest_binding, local, *, lookup=exact_process):
    verify(manifest_binding); manifest = load(manifest_binding['path'])
    require(manifest.get('schema') == SCHEMA and manifest.get('physical_bytes_retained') is True,
            'Fixture manifest schema/scope differs')
    records = {}
    for entry in manifest['entries']:
        record = validate_fixture(entry, local, lookup=lookup)
        path = Path(record['admission']['path'])
        require(path not in records, 'Duplicate fixture admission')
        records[path] = record
    require(len(records) == manifest['fixture_count'] and len(records) > 0, 'Fixture count differs')
    return records


def build_fixtures(local, output, receipt):
    pin(); local = Path(local).resolve(strict=True)
    require(not output.exists() and not receipt.exists(), 'Use fresh manifest and receipt destinations')
    require(output.resolve().is_relative_to(local/'n4'), 'Private manifest must stay in N4')
    entries = []
    for path in admission_paths(local/'n4'):
        relative = path.relative_to(local/'n4')
        if 'tests' not in relative.parts:
            continue
        producer, test, method = fixture_source(relative)
        parent = local/'n4'/relative.parts[0]
        admission = load(parent/'ADMISSION.json')
        terminal = parent/'RESULT.json'
        if not terminal.exists(): terminal = parent/'FAILED.json'
        logs = [p for p in parent.glob('*.txt') if any(line.startswith(method+' ') and ' ... ' in line
                for line in p.read_text(encoding='utf-8-sig').splitlines())]
        require(len(logs) == 1, 'Fixture requires one exact retained test log')
        entry = dict(fixture=bind(path), parent_admission=bind(parent/'ADMISSION.json'),
            parent_terminal=bind(terminal), parent_owner=admission['owner'],
            producer=source_binding(producer, admission, parent),
            test_source=source_binding(test, admission, parent), test_method=method,
            test_log=bind(logs[0]), classification='PRESERVED_NON_EXECUTION_TEST_FIXTURE',
            physical_bytes_retained=True)
        validate_fixture(entry, local)
        entries.append(entry)
    require(len(entries) == 32 and len({e['parent_admission']['path'] for e in entries}) == 10,
            'Reviewed fixture population changed')
    freeze(output, dict(schema=SCHEMA, utc=datetime.now(timezone.utc).isoformat(), entries=entries,
        fixture_count=len(entries), parent_probes=10, physical_bytes_retained=True,
        numerical_execution_credit=False, shared_ledger_modified=False))
    read_fixtures(bind(output), local)
    freeze(receipt, dict(status='BOUND_PRESERVED_TEST_FIXTURE_INVENTORY', manifest=bind(output),
        fixture_count=32, parent_probes=10, physical_bytes_retained=True,
        synthetic_pid_lookup=False, blanket_directory_exclusion=False,
        worker_execution_authorized=False, N4_accepted=False, N5_complete=False))


def snapshot(local, stage, main_plan, requested_bytes, *, peak_bytes=0):
    from asr_full_bank import payload_inventory
    local = Path(local).resolve(strict=True)
    fb = load(HERE/'RESERVATION_CENSUS_FIXTURES_V2.json')['manifest']
    fixtures = read_fixtures(fb, local)
    closed = read_closed_components(main_plan)
    state = local/'supervision'
    worker = load(state/'worker.json'); spec = load(state/'worker_spec.json'); before = epoch(worker, spec)
    paths = admission_paths(local/'n4')
    require(set(fixtures).issubset(paths), 'A recorded fixture disappeared from the complete census')
    records = [fixtures[p] if p in fixtures else classify(p, local) for p in paths]
    active = [validate_live(r, local) for r in records if r['state'] == 'ACTIVE']
    require(len({owner_key(a['owner']) for a in active}) == len(active), 'Duplicate active owner')
    fresh_worker = load(state/'worker.json')
    require(epoch(fresh_worker, load(state/'worker_spec.json')) == before,
            'Supervisor ownership changed during admission scan; resample')
    supervision = validate_supervision(fresh_worker, spec, active)
    visible = visible_python_census(local, stage, active, supervision)
    inventory = payload_inventory(local)
    policy_binding = bind(state/'campaign.json'); policy = load(policy_binding['path'])
    free = {d: shutil.disk_usage(d+'/').free for d in ('C:', 'G:')}
    calculation = calculate(inventory, closed, active, requested_bytes, policy, free,
                            datetime.now(timezone.utc), peak_bytes=peak_bytes)
    require(admission_paths(local/'n4') == paths, 'Admission set changed during census; resample')
    for record in records:
        for b in record['dependencies']: verify(b)
        if record['state'] == 'ACTIVE': require(exact_process(record['owner']) is not None, 'Live owner exited')
        if record['state'] == 'CLOSED_OWNER': require(exact_process(record['owner']) is None, 'Closed owner changed')
        if record['state'] == 'NON_EXECUTION_FIXTURE':
            require(exact_process(record['parent_owner']) is None, 'Fixture parent changed')
    require(epoch(load(state/'worker.json'), load(state/'worker_spec.json')) == before,
            'Supervisor ownership changed during census; resample')
    validate_supervision(load(state/'worker.json'), spec, active)
    visible_python_census(local, stage, active, supervision)
    verify(main_plan); verify(policy_binding); verify(fb)
    return dict(records=records, active_allocations=active, supervisor=supervision,
        visible_N4_python_processes=visible, inventory=inventory, closed_components=closed,
        fixture_manifest=fb, preserved_fixture_count=len(fixtures), all_physical_fixture_bytes_retained=True,
        policy=policy_binding, free_bytes=free, calculation=calculation,
        complete_recorded_N4_admission_census=True, active_set_supplied_by_caller=False,
        whole_host_exclusivity_proved=False, serialized_production_admission=False,
        production_guard_integration_complete=False, worker_execution_authorized=False,
        N4_accepted=False, N5_complete=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build immutable, individually verified test-fixture inventory')
    parser.add_argument('--local', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    build_fixtures(args.local, args.output, args.receipt)
