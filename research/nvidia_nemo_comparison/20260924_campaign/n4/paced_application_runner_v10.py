"""Fixed supervised coordinator/child wiring. README_APPLICATION_SETUP_V1.md."""
import argparse
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import sys
import time

import psutil
from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_child_admission_v7 import ChildAdmission, SCHEMA, assert_plain_path, write_lease
from paced_panel_plan_guarded_v2 import admit_plan, execution_payload, APPLICATION_POLICY
from application_delivery import review_files as review_delivery_files
from review_application_transport import record
from review_native_journal import inspect as inspect_journal, require_complete
from paced_slot import observe_owner, validate_supervision
from paced_slot_guarded_v1 import ExclusiveApplicationSlot
from private_application_process_v3 import PrivateApplicationProcess, api, checked
from review_scoring_bank_v3 import guard, require, shared_allowance
from scoring_bank_v3 import writer_lock

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
RUN_SCHEMA = 'n4-paced-application-run-v10'
QUALIFICATIONS = {
    'PACED_PANEL_PLAN_CHECK_V4.json': 'PASS_V3_SCORED_PANEL_PLANNER_DEVELOPMENT_ONLY',
    'DELIVERY_APPLICATION_PRESTART_CHECK_V1.json': 'PASS_APPLICATION_DELIVERY_PRESTART_DEVELOPMENT_ONLY',
    'NATIVE_JOURNAL_REVIEW_CHECK_V1.json': 'PASS_NATIVE_JOURNAL_REVIEW_DEVELOPMENT_ONLY',
    'PACED_SLOT_CHECK_V1.json': 'PASS_PACED_SLOT_GUARD_DEVELOPMENT_ONLY',
    'PRIVATE_PROCESS_CHECK_V3.json': 'PASS_PRIVATE_PROCESS_LIFETIME_DEVELOPMENT_ONLY',
    'PACED_CHILD_ADMISSION_CHECK_V1.json': 'PASS_CHILD_ADMISSION_GUARD_DEVELOPMENT_ONLY',
}


def code_bindings():
    from application_family_v10 import code_bindings as family_code
    return family_code()



def qualified_interpreter():
    qualification = load(HERE/'PRIVATE_PROCESS_CHECK_V3.json'); verify(qualification['private_receipt'])
    proof = load(qualification['private_receipt']['path'])['fixture_lifetimes'][0]; verify(proof)
    executable = load(proof['path'])['executable']; verify(executable)
    require(bind(sys.executable) == executable, 'Use the exact qualified application interpreter')
    return executable


def supervised_identity(state):
    coordinator = identity(psutil.Process()); record = load(state/'worker.json')
    supervisor = dict(pid=record['pid'], create_time=record['create_time'])
    observations = {p['pid']: observe_owner(p) for p in (supervisor, coordinator)}
    validate_supervision(record, coordinator, observations, time.time())
    return coordinator, supervisor, record['run_id']


def supervise_child(child, slot, renew, *, maximum_seconds, now=time.monotonic, sleep=time.sleep):
    """Renew only after a successful parent gate; return only when root has exited.

    Cleanup belongs to the caller's finally block, even if this loop fails.
    """
    require(0 < maximum_seconds <= 3900, 'Bounded application lifetime required')
    start = now(); sequence = 1
    while not child.root_exited():
        require(now()-start < maximum_seconds, 'Application child lifetime exceeded')
        try: slot.check()
        except ValueError as exc:
            # The guard observes exact owners; root exit between poll and check
            # is normal only for this specific missing-owner failure.
            if str(exc) == 'Required exact process has exited or PID was reused' and child.root_exited(): break
            raise
        renew(sequence); sequence += 1; sleep(.25)
    return dict(renewals=sequence-1, elapsed_seconds=now()-start)


def check_native_envelope(folder, payload):
    """After process closure, bind the complete native journal to this cell.

    This is a collection gate, not payload/accuracy/timing acceptance. Preserve
    a well-formed but incomplete census before rejecting a retained tail.
    """
    application = assert_plain_path(folder/'application', folder)
    closure_binding, closure = record(application/'ENGINE_CLOSURE.json', application)
    require(closure['job'] == payload['job'] and closure['engine_class'] == payload['contract']['engine'],
        'Native envelope job/engine differs from planned cell')
    root = assert_plain_path(application/'data/sessions', application)
    session = assert_plain_path(Path(closure['session']), root)
    require(session.parent == root and session.is_dir(), 'Native session must be a direct child of cell session root')
    review = inspect_journal(session, job=payload['job'])
    verify(closure_binding)
    freeze(folder/'NATIVE_JOURNAL_ENVELOPE.json', dict(
        schema='n4-cell-native-envelope-v1', cell_id=payload['cell_id'],
        job_sha256=fingerprint(payload['job']), engine_closure=closure_binding,
        session=str(session), review=review, integrated_N4_cells=0, N4_accepted=False))
    require_complete(review)
    return bind(folder/'NATIVE_JOURNAL_ENVELOPE.json')


def check_delivery_envelope(folder,payload):
    """Independently parse fixed delivery files after normal process closure."""
    application=assert_plain_path(folder/'application',folder)
    cell_binding,cell=record(application/'RESULT.json',application)
    require(cell['status']==APPLICATION_POLICY['success_status'] and cell['source_start_requested'] is True
        and cell['controller_closed'] is True and cell['controller_worker_exited'] is True
        and cell['errors']==cell['callback_errors']==[] and cell['application_variant']==APPLICATION_POLICY['variant']
        and cell['delivery_policy']==APPLICATION_POLICY['delivery'] and cell['integrated_N4_cells']==0
        and cell['complete_N4_acceptance'] is False and cell['source_to_widget_latency_qualified'] is False,
        'Delivery-cell closure or application policy differs')
    capture_path=assert_plain_path(application/'delivery/CAPTURE.json',application)
    require(capture_path.is_file() and capture_path.stat().st_size<=128*1024,'Oversize delivery capture')
    capture_binding=bind(capture_path)
    require(cell['delivery_capture']==capture_binding,'Cell capture binding differs')
    verify(payload['source_receipt']);source=load(payload['source_receipt']['path']);prototype=Path(source['prototype'])
    files=[dict(path=str((prototype/name).resolve()),**source['files'][name])
        for name in ('app/pipeline.py','app/buffers.py')]
    for b in files:verify(b)
    reviewed=review_delivery_files(application,payload['job'],payload['contract'],files)
    require(cell['delivery_join']==reviewed,'Child and parent delivery joins differ')
    verify(payload['source_receipt']);verify(cell_binding)
    freeze(folder/'SOURCE_DELIVERY_ENVELOPE.json',dict(schema='n4-cell-source-delivery-envelope-v1',
        cell_id=payload['cell_id'],job_sha256=fingerprint(payload['job']),contract_sha256=fingerprint(payload['contract']),
        application_policy=APPLICATION_POLICY,source_receipt=payload['source_receipt'],cell_result=cell_binding,
        review=reviewed,independent_parent_read=True,integrated_N4_cells=0,N4_accepted=False))
    return bind(folder/'SOURCE_DELIVERY_ENVELOPE.json')


def collect_one(plan, index, folder, state, code, *, allocation_guard=None, allocation_receipt=None):
    payload = execution_payload(plan, index)
    slot = ExclusiveApplicationSlot(state, folder, allocation_guard=allocation_guard, allocation_receipt=allocation_receipt)
    acquired = slot.acquire(); child = None; result = None; lifecycle = None; release = None; error = None
    try:
        transport = folder/'transport'; nonce = secrets.token_hex(32)
        child = PrivateApplicationProcess(transport, executable_binding=bind(sys.executable), script_binding=bind(__file__),
            arguments=['child', '--permit', str(transport/'PERMIT.json'), '--nonce', nonce], cpu=4)
        freeze(transport/'INPUT.json', payload)
        owner = child.spawn_suspended()
        coordinator, supervisor, run_id = supervised_identity(state)
        permit = dict(schema=SCHEMA, status='ADMITTED_SINGLE_APPLICATION_CHILD', nonce=nonce,
            coordinator=coordinator, application=owner, supervisor=supervisor, supervised_run=run_id,
            coordinator_argv_sha256=fingerprint(psutil.Process().cmdline()), application_argv_sha256=fingerprint(child.argv),
            desktop=child.desktop_name, plan_sha256=fingerprint(plan), input=bind(transport/'INPUT.json'),
            output=str((folder/'application').resolve()), state=str(state.resolve()), code=code)
        freeze(transport/'PERMIT.json', permit); permit_digest = fingerprint(permit)
        def register(actual_owner, **bindings):
            slot.register_application(actual_owner, **bindings)
            write_lease(transport/'LEASE.json', permit, permit_digest, 0)
        child.resume(register)
        monitoring = supervise_child(child, slot, lambda sequence: write_lease(transport/'LEASE.json', permit, permit_digest, sequence),
            maximum_seconds=min(3900, payload['job']['frames']/16000*25+480))
        lifecycle = child.close(grace_seconds=0)
        require(lifecycle['root_exit_code'] == 0 and lifecycle['observed_members_exited'] and not lifecycle['forced'], 'Application child did not exit normally')
        result = load(transport/'CHILD_RESULT.json')
        require(result['status'] == 'COLLECTED_DELIVERY_APPLICATION_CELL_REQUIRES_REVIEW' and result['owner'] == owner
            and result['input'] == permit['input'], 'Child collection failed or input differs')
        require(result['cell_result']==bind(folder/'application/RESULT.json'),'Foreign child cell result')
        verify(result['cell_result']); cell = load(result['cell_result']['path'])
        require(cell['status'] == APPLICATION_POLICY['success_status'] and cell['source_start_requested'] and not cell['errors'], 'Actual source/closure incomplete')
        native_envelope = check_native_envelope(folder, payload)
        delivery_envelope = check_delivery_envelope(folder,payload)
        freeze(folder/'COLLECTED.json', dict(status='COLLECTED_SOURCE_DELIVERY_PACED_CELL_REQUIRES_REVIEW', cell_id=payload['cell_id'],
            input=permit['input'], child_result=bind(transport/'CHILD_RESULT.json'), lifetime=bind(transport/'LIFETIME.json'),
            native_journal_envelope=native_envelope, source_delivery_envelope=delivery_envelope,
            application_policy=APPLICATION_POLICY,monitoring=monitoring, slot_admission=acquired,
            integrated_N4_cells=0, N4_accepted=False))
    except BaseException as exc:
        error = type(exc).__name__+': '+str(exc)[:2000]
        raise
    finally:
        # Closing the private process also creates transport/CANCEL. The child
        # gate sees it at its next callback; job termination remains the bound.
        cleanup_error = None
        try:
            if child is not None and not child.closed: lifecycle = child.close(grace_seconds=150)
            if child is not None:
                lifecycle = lifecycle or child.receipt
                require(lifecycle['status'] == 'OWNED_PROCESS_LIFETIME_CLOSED' and lifecycle['job_empty_verified']
                    and lifecycle['observed_members_exited'], 'Retain slot: child lifetime closure is unverified')
            release = slot.release()
        except BaseException as exc:
            cleanup_error = type(exc).__name__+': '+str(exc)[:2000]
            raise
        finally:
            freeze(folder/'PARENT_CLOSURE.json', dict(error=error, cleanup_error=cleanup_error, lifecycle=lifecycle, slot_release=release,
                integrated_N4_cells=0, N4_accepted=False))
    return bind(folder/'COLLECTED.json')


def actual_desktop():
    kernel, user = api(); kernel.GetCurrentThreadId.argtypes = []; kernel.GetCurrentThreadId.restype = W.DWORD
    user.GetThreadDesktop.argtypes = [W.DWORD]; user.GetThreadDesktop.restype = W.HANDLE
    desktop = checked(user.GetThreadDesktop(kernel.GetCurrentThreadId()))
    buffer = C.create_unicode_buffer(512); needed = W.DWORD()
    checked(user.GetUserObjectInformationW(desktop, 2, buffer, C.sizeof(buffer), C.byref(needed)))
    return buffer.value


def child_main(permit_path, nonce):
    # This branch deliberately does not call pin(), which is the CPU14 helper
    # placement. The suspended launcher has already assigned this child CPU4.
    gate = ChildAdmission(permit_path, nonce=nonce, desktop=actual_desktop(), expected_code=code_bindings())
    cell = None; error = None; result = None; detail = None; phase = 'prime'
    try:
        primed = gate.prime(); source = Path(primed['source'])
        phase = 'application_import'
        sys.path[:0] = [str(source), str(source/'vendor'), str(source.parent)]
        from paced_application_cell_v2 import ApplicationCell
        phase = 'pre_construction_gate'
        gate.check(); payload = gate.payload
        phase = 'application_construction'
        cell = ApplicationCell(gate.output, payload['job'], payload['contract'])
        phase = 'application_prepare'
        cell.prepare(source=source, models_root=Path(payload['models_root']), runtimes=payload['runtimes'], gallery_preparation=payload['gallery_preparation'])
        phase = 'source_execution'
        cell.run_source(admission_check=gate.check)
    except BaseException as exc:
        error = type(exc).__name__+': '+str(exc)[:2000]
        detail = child_failure_detail(exc, phase)
    finally:
        if cell is not None:
            try: result = cell.close()
            except BaseException as exc:
                error = (error or '')+'; close: '+type(exc).__name__+': '+str(exc)[:1000]
                detail = detail or child_failure_detail(exc, 'application_close')
        okay = error is None and result is not None and result['status'] == APPLICATION_POLICY['success_status']
        freeze(gate.transport/'CHILD_RESULT.json', dict(status='COLLECTED_DELIVERY_APPLICATION_CELL_REQUIRES_REVIEW' if okay else 'FAILED_APPLICATION_CELL_PRESERVED',
            owner=identity(psutil.Process()), input=gate.permit['input'], error=error,
            failure_detail=detail,
            cell_result=bind(gate.output/'RESULT.json') if (gate.output/'RESULT.json').exists() else None,
            integrated_N4_cells=0, N4_accepted=False))
    require(okay, 'Application child failed; private evidence preserved')


def child_failure_detail(exc, phase):
    """Bounded private traceback without local variables or exception source text."""
    import traceback
    frames = traceback.extract_tb(exc.__traceback__, limit=32)
    return dict(phase=phase, exception_type=type(exc).__name__, winerror=getattr(exc,'winerror',None),
        filename=str(getattr(exc,'filename',None))[:4096],
        frames=[dict(file=f.filename, line=f.lineno, function=f.name) for f in frames])


def collect_outcome(plan, index, folder, state, code, *, allocation_guard, allocation_receipt):
    """Only a independently verified, already closed lane timeout may continue."""
    try:
        receipt = collect_one(plan, index, folder, state, code,
            allocation_guard=allocation_guard, allocation_receipt=allocation_receipt)
        return dict(outcome='collected_requires_review', receipt=receipt)
    except ValueError as exc:
        if str(exc) != 'Application child did not exit normally': raise
        child = load(folder/'transport/CHILD_RESULT.json')
        require(child.get('cell_result') is not None,
            'Application setup failed before RESULT: '+str(child.get('error'))[:2000])
        from review_application_failure_v1 import review
        result = review(folder, payload=execution_payload(plan,index), plan_sha256=fingerprint(plan),
            coordinator=identity(psutil.Process()), code=code, executable=bind(sys.executable),
            script=bind(__file__), coordinator_argv=psutil.Process().cmdline(), state=state)
        allocation_guard.fast_check(peak=512*1024**2)
        freeze(folder/'FAILED_CELL.json',result)
        return dict(outcome='failed_lane_timeout', receipt=bind(folder/'FAILED_CELL.json'))


def run(plan_path, output):
    import application_family_v10 as family
    import guarded_execution_v1 as resource
    code = code_bindings(); executable = qualified_interpreter(); pb = bind(plan_path)
    g = family.start_output(output, pb, 'run', code, 2*1024**3, 14400,
        dict(schema=RUN_SCHEMA, status='ADMITTED_GUARDED_PACED_RUN_REQUIRES_PLAN_RECONSTRUCTION',
             executable=executable, output=str(output.resolve()), state=str(LOCAL/'supervision'),
             actual_application_started=False))
    argv = [executable['path'], '-B', str(Path(__file__).resolve()), 'run', '--plan', str(Path(pb['path'])), '--output', str(output.resolve())]
    freeze(output/'worker.json', dict(argv=argv, cwd=str(HERE)))
    checks = []; collected = []; outcomes = []; error = None; plan = None
    try:
        with g:
            checks.append(resource.save_check(g, 'GUARD_INITIAL.json'))
            admitted, plan = admit_plan(plan_path); require(admitted == pb, 'Plan changed after run admission')
            require(psutil.Process().cmdline() == argv, 'Different fixed coordinator command')
            for index, row in enumerate(plan['rows']):
                g.fast_check(peak=512*1024**2)
                outcome = collect_outcome(plan, index, output/'cells'/row['cell_id'], LOCAL/'supervision', code,
                    allocation_guard=g, allocation_receipt=checks[-1])
                outcomes.append(dict(cell_id=row['cell_id'], **outcome))
                if outcome['outcome'] == 'collected_requires_review': collected.append(outcome['receipt'])
                freeze(output/'progress'/f'{index+1:04d}.json', dict(attempted=index+1, completed=len(collected), failed=len(outcomes)-len(collected), total=plan['required'], outcome=outcomes[-1], integrated_N4_cells=0))
                if (index+1) % 30 == 0 and index+1 < plan['required']:
                    checks.append(resource.save_check(g, f'GUARD_{index+1:04d}.json'))
            checks.append(resource.save_check(g, 'GUARD_FINAL.json')); g.fast_check()
            for b in code+[pb]: verify(b)
    except BaseException as exc:
        error = type(exc).__name__+': '+str(exc)[:2000]
    freeze(output/'RESULT.json', dict(schema=RUN_SCHEMA,
        status='COLLECTED_PACED_APPLICATION_OUTCOMES_REQUIRES_REVIEW' if error is None else 'FAILED_PACED_APPLICATION_RUN_PRESERVED',
        owner=g.owner, admission=g.admission, execution_plan=bind(output/'EXECUTION_PLAN.json'),
        attempted=len(outcomes), completed=len(collected), failed=len(outcomes)-len(collected), outcomes=outcomes, required=plan['required'] if plan else None,
        collected=collected, error=error, guard_checks=checks, integrated_N4_cells=0, N4_accepted=False,
        continuity_included=False, utc=datetime.now(timezone.utc).isoformat()))
    require(error is None, 'Application panel failed; attempt preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    launch = sub.add_parser('run'); launch.add_argument('--plan', type=Path, required=True); launch.add_argument('--output', type=Path, required=True)
    child = sub.add_parser('child'); child.add_argument('--permit', type=Path, required=True); child.add_argument('--nonce', required=True)
    args = parser.parse_args()
    if args.command == 'run': run(args.plan, args.output)
    else: child_main(args.permit, args.nonce)
