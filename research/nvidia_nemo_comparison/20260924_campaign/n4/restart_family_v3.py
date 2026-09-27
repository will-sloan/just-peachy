"""Guarded restart execution lineage; README_RESTART_FAMILY_V3.md."""
from pathlib import Path
import sys

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from reservation_budget_v1 import require
import restart_family_v2 as previous
import application_family_v6 as application
import guarded_execution_v1 as resource
import guarded_metadata_probe_v1 as metadata

HERE = Path(__file__).resolve().parent
LOCAL = application.LOCAL
QUALIFICATION = 'RESTART_FAMILY_CHECK_V3.json'
STATUS = 'PASS_V3_GUARDED_RESTART_FAMILY_DEVELOPMENT_ONLY'
SCHEMA = 'n4-guarded-restart-execution-v1'
OWN = ('restart_family_v3.py', 'restart_application_plan_v3.py',
       'restart_application_runner_v3.py', 'review_restart_transport_v3.py',
       'review_restart_run_v3.py', 'review_restart_complete_v3.py',
       'review_restart_content_cell_v3.py', 'review_restart_content_run_v3.py',
       'test_restart_guarded_v3.py', 'probe_restart_family_v3.py',
       'README_RESTART_FAMILY_V3.md')
ENTRIES = dict(probe='probe_restart_family_v3.py', prepare='restart_application_plan_v3.py',
               run='restart_application_runner_v3.py', review='review_restart_run_v3.py',
               content='review_restart_content_run_v3.py')
LIMITS = dict(probe=(16*1024**2, 2400), prepare=(16*1024**2, 2400),
              run=(2*1024**3, 7200), review=(64*1024**2, 3600),
              content=(64*1024**2, 3600))


def code_bindings():
    old, q = previous.qualification()
    app_code = application.code_bindings()
    app = application.qualification(app_code)
    unique = {}
    for b in q['code'] + app_code + [old, app] + [bind(HERE/n) for n in OWN]:
        require(b['path'] not in unique or unique[b['path']] == b, 'Conflicting restart source lineage')
        unique[b['path']] = b
    code = [b for _, b in sorted(unique.items())]
    require(0 < len(code) <= 512, 'Complete restart source bound exceeded')
    for b in code: verify(b)
    return code


def validate_envelope(a, e, *, role, code, plan, qualification):
    """Pure budget/lineage gate shared by closed readers and regression tests."""
    cap, seconds = LIMITS[role]
    require(e['schema'] == SCHEMA and e['role'] == role
        and e['entry_script'] == bind(HERE/ENTRIES[role])
        and e['code'] == a['code'] == code and e['plan'] == a['plan'] == plan,
        'Restart envelope entry, source or plan differs')
    require(type(a['allocation_bytes']) is int and type(a['maximum_seconds']) is int
        and a['allocation_bytes'] == e['allocation_bytes'] == cap
        and a['maximum_seconds'] == e['maximum_seconds'] == seconds
        and a['qualification'] == e['family_qualification'] == qualification
        and e['resource_qualification'] == resource.qualification()
        and e['application_permission_from_envelope'] is False,
        'Restart budget or qualification differs')


def qualification(code=None):
    code = code_bindings() if code is None else code
    qb = bind(HERE/QUALIFICATION); q = load(qb['path'])
    verify(q['private_receipt']); r = load(q['private_receipt']['path'])
    verify(r['admission']); a = load(r['admission']['path'])
    require(q['status'] == STATUS and q['code'] == a['code'] == code
        and r['status'] == 'PASS_V3_GUARDED_RESTART_FAMILY_CHECKS_ONLY'
        and r['positive_production_plan_gate_executed'] is True
        and r['actual_restart_payloads_checked'] == 12
        and type(r['tests_passed']) is int and r['tests_passed'] == 101 and r['tests_skipped'] == 0
        and q['N4_accepted'] is False and q['actual_restart_qualified'] is False
        and exact_process(a['owner']) is None, 'Closed guarded restart qualification required')
    require(len(r['checks']) == 7 and sum(c['tests'] for c in r['checks']) == 101,
            'Complete retained and guarded test census required')
    for c in r['checks']:
        verify(c['log']); text = Path(c['log']['path']).read_text(encoding='utf-8')
        require(f"Ran {c['tests']} tests" in text and text.strip().endswith('OK')
            and 'skipped' not in text, 'Restart test log differs')
    for b in r['source_snapshots']+[r['actual_panel'],r['reconstructed_plan']]: verify(b)
    closed_execution(Path(q['private_receipt']['path']).parent, 'probe', code=code)
    return qb, q


def start_output(output, plan_binding, role, code, extra):
    process = pin(); entry = bind(HERE/ENTRIES[role]); cap, seconds = LIMITS[role]
    require(Path(sys.argv[0]).resolve() == Path(entry['path']), 'Wrong supervised restart entry')
    metadata.validate_manifest(code, resource.code_bindings(), entry)
    qb = None if role == 'probe' else qualification(code)[0]
    output = Path(output).resolve()
    require(not output.exists() and output.is_relative_to(LOCAL/'n4') and output != LOCAL/'n4',
            'Fresh private restart output required')
    for b in code+[plan_binding]: verify(b)
    freeze(output/'EXECUTION_PLAN.json', dict(schema=SCHEMA, role=role, plan=plan_binding,
        code=code, entry_script=entry, resource_qualification=resource.qualification(),
        family_qualification=qb, allocation_bytes=cap, maximum_seconds=seconds,
        application_permission_from_envelope=False))
    a = dict(owner=identity(process), code=code, plan=plan_binding,
        execution_plan=bind(output/'EXECUTION_PLAN.json'), qualification=qb,
        allocation_bytes=cap, maximum_seconds=seconds, cpu_affinity=process.cpu_affinity())
    require(not set(extra).intersection(a), 'Extra fields replace restart provenance')
    a.update(extra); freeze(output/'ADMISSION.json', a)
    return resource.Guard(LOCAL, output, code,
        load(LOCAL/'n4/integrated-main-v3/RESULT.json')['plan'], seconds, production=True)


def closed_execution(folder, role, *, code=None):
    folder = Path(folder).resolve(strict=True); ab = bind(folder/'ADMISSION.json'); a = load(ab['path'])
    eb = bind(folder/'EXECUTION_PLAN.json'); rb = bind(folder/'RESULT.json'); r = load(rb['path'])
    code = code_bindings() if code is None else code
    qb = None if role == 'probe' else qualification(code)[0]
    validate_envelope(a, load(eb['path']), role=role, code=code, plan=a['plan'], qualification=qb)
    require(r['admission'] == ab and r['execution_plan'] == a['execution_plan'] == eb
        and exact_process(a['owner']) is None, 'Restart producer still active or provenance differs')
    checks = r['guard_checks']
    require(len(checks) >= 2 and Path(checks[0]['path']).name == 'GUARD_INITIAL.json'
        and Path(checks[-1]['path']).name == 'GUARD_FINAL.json', 'Complete restart resource boundaries required')
    for b in checks:
        verify(b); v = load(b['path'])['projection']
        require(Path(b['path']).parent == folder and v['own_admission'] == ab
            and v['production_scope_checked'] is True and v['own_allocation_counted_once'] is True
            and v['other_allocation_count'] == 0, 'Restart allocation census differs')
    for b in code+[ab, eb, rb, a['plan']]: verify(b)
    return ab, a, rb, r
