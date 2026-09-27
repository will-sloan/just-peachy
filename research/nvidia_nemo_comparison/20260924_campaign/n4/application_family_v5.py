"""Guarded selected-plan execution family; README_APPLICATION_FAMILY_V5.md."""
from pathlib import Path
import sys

from common import bind, load, verify, freeze
from metric_process import exact_process, identity, pin
from reservation_budget_v1 import require
import application_family_v4 as previous
import paced_panel_plan_guarded_v2 as planner
import guarded_execution_v1 as resource
import guarded_metadata_probe_v1 as metadata

HERE = Path(__file__).resolve().parent
LOCAL = planner.LOCAL
QUALIFICATION = 'APPLICATION_FAMILY_CHECK_V5.json'
STATUS = 'PASS_V5_APPLICATION_FAMILY_DEVELOPMENT_ONLY'
MAX_CODE_RECORDS = 512
OWN = ('application_family_v5.py', 'paced_child_admission_v3.py', 'paced_application_runner_v5.py',
    'review_application_transport_v5.py', 'review_application_cell_v5.py', 'review_application_panel_v5.py',
    'test_paced_child_admission_v3.py', 'test_paced_application_runner_v5.py',
    'test_application_transport_review_v5.py', 'test_application_cell_review_v5.py',
    'test_application_panel_review_v5.py', 'test_application_family_v5.py',
    'probe_application_family_v5.py', 'README_APPLICATION_FAMILY_V5.md',
    'paced_slot_guarded_v1.py', 'test_paced_slot_guarded_v1.py', 'README_PACED_SLOT_GUARDED_V1.md')
ENTRIES = dict(probe='probe_application_family_v5.py', run='paced_application_runner_v5.py',
               review='review_application_panel_v5.py')


def code_bindings():
    qb = bind(HERE/previous.QUALIFICATION); q = load(qb['path'])
    require(q['status'] == previous.STATUS and q['code'] == previous.code_bindings(), 'Original application family changed')
    verify(q['private_receipt']); old = load(q['private_receipt']['path']); verify(old['admission'])
    a = load(old['admission']['path'])
    require(a['code'] == q['code'] and exact_process(a['owner']) is None, 'Original application proof not closed')
    pb = bind(HERE/planner.QUALIFICATION); pq = load(pb['path']); pc = planner.code_bindings()
    require(pq['status'] == planner.STATUS and pq['code'] == pc
        and pq['exact_preparer_owner_exited'] is True, 'Actual plan preparation not qualified')
    verify(pq['private_result']); pa = load(load(pq['private_result']['path'])['admission']['path'])
    require(exact_process(pa['owner']) is None, 'Actual plan preparer remains active')
    values = q['code'] + pc + [qb, pb] + [bind(HERE/n) for n in OWN]
    unique = {}
    for b in values:
        require(b['path'] not in unique or unique[b['path']] == b, 'Conflicting complete source lineage')
        unique[b['path']] = b
    require(0 < len(unique) <= MAX_CODE_RECORDS, 'Full family source list exceeds bound')
    code = [b for _, b in sorted(unique.items())]
    for b in code: verify(b)
    return code


def qualification(code):
    qb = bind(HERE/QUALIFICATION); q = load(qb['path']); verify(q['private_receipt'])
    r = load(q['private_receipt']['path']); verify(r['admission']); a = load(r['admission']['path'])
    require(q['status'] == STATUS and q['code'] == a['code'] == code
        and r['status'] == 'PASS_V5_APPLICATION_FAMILY_CHECKS_ONLY'
        and r['tests_passed'] == 84 and r['positive_production_plan_gate_executed'] is True
        and exact_process(a['owner']) is None and q['N4_accepted'] is False,
        'Closed matching guarded application family qualification required')
    return qb


def start_output(output, plan_binding, role, code, cap, seconds, extra):
    process = pin(); entry = bind(HERE/ENTRIES[role])
    require(Path(sys.argv[0]).resolve() == Path(entry['path']), 'Wrong supervised family entrypoint')
    metadata.validate_manifest(code, resource.code_bindings(), entry)
    require(type(cap) is int and 8*1024**2 <= cap <= 2*1024**3
        and type(seconds) is int and 0 < seconds <= 14400, 'Bounded family allocation required')
    qb = None if role == 'probe' else qualification(code)
    output = Path(output).resolve(); require(not output.exists() and output.is_relative_to(LOCAL/'n4') and output != LOCAL/'n4', 'Fresh private family output required')
    for b in code+[plan_binding]: verify(b)
    freeze(output/'EXECUTION_PLAN.json', dict(schema='n4-guarded-application-execution-v1', role=role,
        plan=plan_binding, code=code, entry_script=entry, resource_qualification=resource.qualification(),
        family_qualification=qb, allocation_bytes=cap, maximum_seconds=seconds,
        application_permission_from_envelope=False))
    a = dict(owner=identity(process), code=code, plan=plan_binding,
        execution_plan=bind(output/'EXECUTION_PLAN.json'), qualification=qb,
        allocation_bytes=cap, maximum_seconds=seconds, cpu_affinity=process.cpu_affinity())
    require(not set(extra).intersection(a), 'Extra fields replace producer provenance')
    a.update(extra); freeze(output/'ADMISSION.json', a)
    return resource.Guard(LOCAL, output, code, load(LOCAL/'n4/integrated-main-v3/RESULT.json')['plan'], seconds, production=True)


def closed_execution(folder, role):
    folder = Path(folder).resolve(strict=True); ab = bind(folder/'ADMISSION.json'); a = load(ab['path'])
    eb = bind(folder/'EXECUTION_PLAN.json'); e = load(eb['path']); rb = bind(folder/'RESULT.json'); r = load(rb['path'])
    code = code_bindings()
    require(r['admission'] == ab and r['execution_plan'] == a['execution_plan'] == eb
        and a['code'] == e['code'] == code and e['schema'] == 'n4-guarded-application-execution-v1'
        and e['role'] == role and e['entry_script'] == bind(HERE/ENTRIES[role])
        and e['plan'] == a['plan'] and exact_process(a['owner']) is None,
        'Guarded application execution provenance differs or remains active')
    require(e['allocation_bytes'] == a['allocation_bytes'] and e['maximum_seconds'] == a['maximum_seconds']
        and e['resource_qualification'] == resource.qualification()
        and e['application_permission_from_envelope'] is False, 'Guarded application budget or policy differs')
    if role != 'probe': require(a['qualification'] == e['family_qualification'] == qualification(code), 'Family qualification changed')
    checks = r['guard_checks']; require(len(checks) >= 2 and Path(checks[0]['path']).name == 'GUARD_INITIAL.json'
        and Path(checks[-1]['path']).name == 'GUARD_FINAL.json', 'Complete resource boundaries required')
    for b in checks:
        verify(b); v = load(b['path'])['projection']
        require(Path(b['path']).parent == folder and v['own_admission'] == ab
            and v['production_scope_checked'] is True and v['own_allocation_counted_once'] is True
            and v['other_allocation_count'] == 0, 'Complete run allocation proof differs')
    for b in code+[ab, eb, rb, a['plan']]: verify(b)
    return ab, a, rb, r
