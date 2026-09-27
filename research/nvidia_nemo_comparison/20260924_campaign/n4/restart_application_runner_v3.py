import restart_family_v3 as family
"""Supervised coordinator for selected restart pairs. README_RESTART_FAMILY_V3.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import secrets
import shutil
import sys
import time

import psutil
from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_application_runner_v4 import qualified_interpreter, supervised_identity, supervise_child
from paced_child_admission_v4 import SCHEMA, assert_plain_path, write_lease
from paced_slot import MAX_CELL_BYTES, bounded_output_bytes, validate_policy
from paced_slot_guarded_v1 import ExclusiveApplicationSlot
import guarded_execution_v1 as resource
from private_application_process_v3 import PrivateApplicationProcess
from restart_application_plan_v3 import admit_plan, execution_payload, APPLICATION_POLICY
from restart_application_child import code_bindings as child_bindings, control, CHILD_SUCCESS
from restart_pair_evidence import review_pair
from review_application_transport import record, validate_lifetime
from review_scoring_bank import require
from review_scoring_bank_v3 import guard, shared_allowance
from scoring_bank_v3 import writer_lock

HERE = Path(__file__).resolve().parent
LOCAL = family.LOCAL
OWN = ('restart_application_runner.py', 'test_restart_runner.py', 'probe_restart_runner.py', 'README_RESTART_FAMILY_V3.md')
QUALIFICATIONS = {'RESTART_PAIR_EVIDENCE_CHECK_V1.json': 'PASS_RESTART_PAIR_EVIDENCE_DEVELOPMENT_ONLY',
                  'PACED_RUNNER_CHECK_V3.json': 'PASS_PACED_RUNNER_V3_DEVELOPMENT_ONLY'}
RUN_SCHEMA = 'n4-restart-application-run-v3'
RUN_QUALIFICATION = family.QUALIFICATION
PREPARED = 'PREPARED_SELECTED_RESTART_RUN_ONLY'
COLLECTED = 'COLLECTED_RESTART_PAIR_WITH_EVIDENCE_JOINS_REQUIRES_REVIEW'
MAXIMUM_CHILD_SECONDS = 1200


def code_bindings():
    return family.code_bindings()


def qualified_manifests():
    parent = code_bindings(); child = child_bindings()
    qb, q = record(HERE/'RESTART_CHILD_CHECK_V1.json', HERE)
    require(q['status'] == 'PASS_RESTART_CHILD_DEVELOPMENT_ONLY' and q['code'] == child
        and len(child) == 122 and len(child) <= 128, 'Fixed child qualification differs')
    require(qb in parent and all(b in parent for b in child), 'Parent must preserve the whole qualified child closure')
    for b in parent: verify(b)
    executable = qualified_interpreter()
    script = bind(HERE/'restart_application_child.py'); require(script in child, 'Unbound child entry point')
    return parent, child, executable, script


def check_after_exit(folder, state, started, owner, supervision):
    """Keep disk/deadline/ownership checks after root exit without demanding a live root."""
    require(time.monotonic()-started < MAXIMUM_CHILD_SECONDS+180, 'Restart collection deadline reached')
    require(exact_process(owner) is None and supervised_identity(state) == supervision,
        'Application became live or supervised coordinator changed during review')
    free = {drive: shutil.disk_usage(drive+'/').free for drive in ('C:', 'G:')}
    validate_policy(load(state/'campaign.json'), free, datetime.now(timezone.utc), bounded_output_bytes(folder), MAX_CELL_BYTES)


def check_child_result(value, *, owner, input_binding, payload, application):
    require(value['status'] == CHILD_SUCCESS and value['owner'] == owner and value['input'] == input_binding
        and value['error'] is None and value['restart_control'] == control(payload), 'Child collection, owner, input or policy differs')
    require(value['cell_result'] == bind(application/'RESULT.json'), 'Foreign child application result')
    require(value['actual_restart_qualified'] is False and type(value['integrated_N4_cells']) is int
        and value['integrated_N4_cells'] == 0 and value['N4_accepted'] is False, 'Child cannot grant restart acceptance')


def collect_one(plan, index, folder, state, parent_code, *, allocation_guard, allocation_receipt):
    parent, child_code, executable, script = qualified_manifests()
    require(parent_code == parent, 'Coordinator manifest changed')
    payload = execution_payload(plan, index); planned = control(payload)
    folder = assert_plain_path(folder, LOCAL/'n4'); state = assert_plain_path(state, LOCAL)
    require(state == LOCAL/'supervision' and not folder.exists(), 'Fresh cell and fixed supervision required')
    slot = ExclusiveApplicationSlot(state, folder, allocation_guard=allocation_guard,
        allocation_receipt=allocation_receipt); acquired = slot.acquire()
    started = time.monotonic(); child = None; lifecycle = None; release = None; error = None
    try:
        transport = folder/'transport'; nonce = secrets.token_hex(32)
        child = PrivateApplicationProcess(transport, executable_binding=executable, script_binding=script,
            arguments=['--permit', str(transport/'PERMIT.json'), '--nonce', nonce], cpu=4)
        freeze(transport/'INPUT.json', payload); owner = child.spawn_suspended()
        supervision = supervised_identity(state); coordinator, supervisor, run_id = supervision
        permit = dict(schema=SCHEMA, status='ADMITTED_SINGLE_APPLICATION_CHILD', nonce=nonce,
            coordinator=coordinator, application=owner, supervisor=supervisor, supervised_run=run_id,
            coordinator_argv_sha256=fingerprint(psutil.Process().cmdline()), application_argv_sha256=fingerprint(child.argv),
            desktop=child.desktop_name, plan_sha256=fingerprint(plan), input=bind(transport/'INPUT.json'),
            output=str((folder/'application').resolve()), state=str(state.resolve()), code=child_code)
        freeze(transport/'PERMIT.json', permit); permit_digest = fingerprint(permit)
        def register(actual_owner, **bindings):
            slot.register_application(actual_owner, **bindings)
            write_lease(transport/'LEASE.json', permit, permit_digest, 0)
        child.resume(register)
        monitoring = supervise_child(child, slot,
            lambda sequence: write_lease(transport/'LEASE.json', permit, permit_digest, sequence),
            maximum_seconds=MAXIMUM_CHILD_SECONDS)
        lifecycle = child.close(grace_seconds=0)
        lifetime_binding, persisted = record(transport/'LIFETIME.json', folder)
        require(persisted == lifecycle, 'Returned and persisted lifetime differ')
        lifetime_review = validate_lifetime(persisted, owner=owner, executable=executable, script=script,
            argv_sha256=fingerprint(child.argv), desktop=child.desktop_name, cpu=4)
        checkpoint = lambda: check_after_exit(folder, state, started, owner, supervision)
        checkpoint()
        child_binding, result = record(transport/'CHILD_RESULT.json', folder)
        check_child_result(result, owner=owner, input_binding=permit['input'], payload=payload, application=folder/'application')
        pair = review_pair(folder/'application', payload=payload, application_owner=owner, checkpoint=checkpoint)
        require(pair['status'] == 'PASS_COMPLETE_RESTART_PAIR_EVIDENCE_JOINS_ONLY'
            and pair['cell_result'] == result['cell_result'] and pair['cell_id'] == payload['cell_id']
            and pair['application_owner'] == owner and pair['control'] == planned
            and pair['actual_restart_qualified'] is False and pair['N4_accepted'] is False
            and pair['integrated_N4_cells'] == 0, 'Pair reader returned a foreign or accepted result')
        freeze(folder/'PAIR_EVIDENCE_REVIEW.json', pair)
        for b in parent+[permit['input'], lifetime_binding, child_binding]: verify(b)
        checkpoint()
        freeze(folder/'COLLECTED.json', dict(status=COLLECTED, cell_id=payload['cell_id'], input=permit['input'],
            child_result=child_binding, lifetime=lifetime_binding, lifetime_review=lifetime_review,
            pair_evidence_review=bind(folder/'PAIR_EVIDENCE_REVIEW.json'), application_policy=APPLICATION_POLICY,
            restart_control=planned, parent_code_sha256=fingerprint(parent), child_code_sha256=fingerprint(child_code),
            monitoring=monitoring, slot_admission=acquired, actual_restart_qualified=False,
            independent_complete_transport_reviewed=False, integrated_N4_cells=0, N4_accepted=False))
    except BaseException as exc:
        error = type(exc).__name__+': '+str(exc)[:2000]; raise
    finally:
        cleanup_error = None
        try:
            if child is not None and not child.closed: lifecycle = child.close(grace_seconds=150)
            if child is not None:
                lifecycle = lifecycle or child.receipt
                require(lifecycle['status'] == 'OWNED_PROCESS_LIFETIME_CLOSED'
                    and lifecycle['job_empty_verified'] is True and lifecycle['observed_members_exited'] is True,
                    'Retain slot: child lifetime closure is unverified')
            release = slot.release()
        except BaseException as exc:
            cleanup_error = type(exc).__name__+': '+str(exc)[:2000]; raise
        finally:
            freeze(folder/'PARENT_CLOSURE.json', dict(error=error, cleanup_error=cleanup_error,
                lifecycle=lifecycle, slot_release=release, actual_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False))
    return bind(folder/'COLLECTED.json')


def qualified_runner():
    parent, child, executable, script = qualified_manifests()
    qb, q = family.qualification(parent)
    require(q['status'] == family.STATUS and q['code'] == parent,
        'Restart coordinator is not qualified')
    verify(q['private_receipt'])
    return parent, child, executable, script, qb


def run(plan_path, output):
    code, child_code, executable, script, qb = qualified_runner()
    output = Path(output).resolve(); pb = bind(plan_path); state = LOCAL/'supervision'
    g = family.start_output(output, pb, 'run', code, dict(schema=RUN_SCHEMA, status=PREPARED,
        child_code=child_code, executable=executable, child_script=script,
        output=str(output), state=str(state), actual_application_started=False))
    argv = [executable['path'], '-B', str(Path(__file__).resolve()), 'run',
            '--plan', pb['path'], '--output', str(output)]
    freeze(output/'worker.json', dict(argv=argv, cwd=str(HERE)))
    freeze(output/'RUN_OWNER.json', dict(owner=g.owner, admission=g.admission))
    checks = []; collected = []; error = None; plan = None
    try:
        with g:
            checks.append(resource.save_check(g, 'GUARD_INITIAL.json'))
            admitted, plan = admit_plan(plan_path)
            require(admitted == pb and psutil.Process().cmdline() == argv, 'Restart plan or fixed command changed')
            for index, row in enumerate(plan['rows']):
                g.fast_check(peak=512*1024**2)
                collected.append(collect_one(plan, index, output/'cells'/row['cell_id'], state, code,
                    allocation_guard=g, allocation_receipt=checks[-1]))
                freeze(output/'progress'/f'{index+1:04d}.json', dict(completed=index+1, total=plan['required'],
                    cell=collected[-1], actual_restart_qualified=False, integrated_N4_cells=0))
                if (index+1) % 4 == 0 and index+1 < plan['required']:
                    checks.append(resource.save_check(g, f'GUARD_{index+1:04d}.json'))
            checks.append(resource.save_check(g, 'GUARD_FINAL.json')); g.fast_check()
            for b in code+[pb]: verify(b)
    except BaseException as exc:
        error = type(exc).__name__+': '+str(exc)[:2000]
    freeze(output/'RESULT.json', dict(schema=RUN_SCHEMA,
        status='COLLECTED_SELECTED_RESTART_PAIRS_REQUIRES_REVIEW' if error is None else 'FAILED_RESTART_RUN_PRESERVED',
        owner=g.owner, admission=g.admission, execution_plan=bind(output/'EXECUTION_PLAN.json'),
        completed=len(collected), required=plan['required'] if plan else None,
        required_sessions=plan['required_sessions'] if plan else None, collected=collected, error=error,
        guard_checks=checks, actual_restart_qualified=False, independent_complete_transport_reviewed=False,
        integrated_N4_cells=0, N4_accepted=False, utc=datetime.now(timezone.utc).isoformat()))
    require(error is None, 'Restart collection failed; attempt preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    launch = sub.add_parser('run'); launch.add_argument('--plan', type=Path, required=True)
    launch.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); run(args.plan, args.output)
