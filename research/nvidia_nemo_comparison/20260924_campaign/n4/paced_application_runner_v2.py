"""Fixed supervised coordinator/child wiring. README_PACED_APPLICATION_RUNNER_V2.md."""
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
from paced_child_admission import ChildAdmission, SCHEMA, assert_plain_path, write_lease
from paced_panel_plan_v2 import admit_plan, execution_payload
from review_application_transport import record
from review_native_journal import inspect as inspect_journal, require_complete
from paced_slot import ExclusiveApplicationSlot, observe_owner, validate_supervision
from private_application_process_v3 import PrivateApplicationProcess, api, checked
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
RUN_SCHEMA = 'n4-paced-application-run-v2'
QUALIFICATIONS = {
    'PACED_PANEL_PLAN_CHECK_V2.json': 'PASS_JOURNAL_DERIVATIVE_PANEL_PLANNER_DEVELOPMENT_ONLY',
    'JOURNAL_APPLICATION_PRESTART_CHECK_V1.json': 'PASS_JOURNAL_APPLICATION_PRESTART_DEVELOPMENT_ONLY',
    'NATIVE_JOURNAL_REVIEW_CHECK_V1.json': 'PASS_NATIVE_JOURNAL_REVIEW_DEVELOPMENT_ONLY',
    'PACED_SLOT_CHECK_V1.json': 'PASS_PACED_SLOT_GUARD_DEVELOPMENT_ONLY',
    'PRIVATE_PROCESS_CHECK_V3.json': 'PASS_PRIVATE_PROCESS_LIFETIME_DEVELOPMENT_ONLY',
    'PACED_CHILD_ADMISSION_CHECK_V1.json': 'PASS_CHILD_ADMISSION_GUARD_DEVELOPMENT_ONLY',
}


def code_bindings():
    names = ('paced_application_runner_v2.py', 'test_paced_application_runner_v2.py', 'probe_paced_application_runner_v2.py',
        'README_PACED_APPLICATION_RUNNER_V2.md')
    entries = [bind(HERE/name) for name in names]
    for name, status in QUALIFICATIONS.items():
        q = load(HERE/name); require(q['status'] == status, 'Prerequisite implementation qualification changed')
        entries += [bind(HERE/name), *q['code']]
    return [value for _, value in sorted({entry['path']: entry for entry in entries}.items())]


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


def collect_one(plan, index, folder, state, code):
    payload = execution_payload(plan, index); slot = ExclusiveApplicationSlot(state, folder)
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
        require(result['status'] == 'COLLECTED_APPLICATION_CELL_REQUIRES_REVIEW' and result['owner'] == owner
            and result['input'] == permit['input'], 'Child collection failed or input differs')
        verify(result['cell_result']); cell = load(result['cell_result']['path'])
        require(cell['status'] == 'CELL_CLOSED_REQUIRES_REVIEW' and cell['source_start_requested'] and not cell['errors'], 'Actual source/closure incomplete')
        native_envelope = check_native_envelope(folder, payload)
        freeze(folder/'COLLECTED.json', dict(status='COLLECTED_SOURCE_PACED_CELL_REQUIRES_REVIEW', cell_id=payload['cell_id'],
            input=permit['input'], child_result=bind(transport/'CHILD_RESULT.json'), lifetime=bind(transport/'LIFETIME.json'),
            native_journal_envelope=native_envelope, monitoring=monitoring, slot_admission=acquired,
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
    cell = None; error = None; result = None
    try:
        primed = gate.prime(); source = Path(primed['source'])
        sys.path[:0] = [str(source), str(source/'vendor'), str(source.parent)]
        from paced_application_cell import ApplicationCell
        gate.check(); payload = gate.payload
        cell = ApplicationCell(gate.output, payload['job'], payload['contract'])
        cell.prepare(source=source, models_root=Path(payload['models_root']), runtimes=payload['runtimes'], gallery_preparation=payload['gallery_preparation'])
        cell.run_source(admission_check=gate.check)
    except BaseException as exc:
        error = type(exc).__name__+': '+str(exc)[:2000]
    finally:
        if cell is not None:
            try: result = cell.close()
            except BaseException as exc: error = (error or '')+'; close: '+type(exc).__name__+': '+str(exc)[:1000]
        okay = error is None and result is not None and result['status'] == 'CELL_CLOSED_REQUIRES_REVIEW'
        freeze(gate.transport/'CHILD_RESULT.json', dict(status='COLLECTED_APPLICATION_CELL_REQUIRES_REVIEW' if okay else 'FAILED_APPLICATION_CELL_PRESERVED',
            owner=identity(psutil.Process()), input=gate.permit['input'], error=error,
            cell_result=bind(gate.output/'RESULT.json') if (gate.output/'RESULT.json').exists() else None,
            integrated_N4_cells=0, N4_accepted=False))
    require(okay, 'Application child failed; private evidence preserved')


def prepare(plan_path, output):
    process = pin(); started = time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private N4 run output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output, LOCAL, started, 3600); inventory = shared_allowance(LOCAL)
        code = code_bindings(); q = load(HERE/'PACED_RUNNER_CHECK_V2.json')
        require(q['status'] == 'PASS_PACED_RUNNER_V2_DEVELOPMENT_ONLY' and q['code'] == code, 'Fixed runner is not qualified')
        executable = qualified_interpreter(); plan_binding, plan = admit_plan(plan_path)
        freeze(output/'ADMISSION.json', dict(schema=RUN_SCHEMA, status='PREPARED_PACED_APPLICATION_RUN_ONLY', owner=identity(process),
            plan=plan_binding, code=code, executable=executable, qualification=bind(HERE/'PACED_RUNNER_CHECK_V2.json'), inventory=inventory,
            output=str(output.resolve()), state=str(LOCAL/'supervision'), required=plan['required'], actual_application_started=False))
        freeze(output/'worker.json', dict(argv=[sys.executable, '-B', str(Path(__file__).resolve()), 'run', '--admission', str(output.resolve()/'ADMISSION.json')], cwd=str(HERE)))
    print('Prepared supervised application worker; no model or child started', flush=True)


def run(admission_path):
    process = pin(); admission = load(admission_path); verify(admission['plan']); verify(admission['qualification'])
    require(admission['schema'] == RUN_SCHEMA and admission['status'] == 'PREPARED_PACED_APPLICATION_RUN_ONLY' and admission['code'] == code_bindings(), 'Run admission/code differs')
    qualification = load(HERE/'PACED_RUNNER_CHECK_V2.json')
    require(admission['qualification'] == bind(HERE/'PACED_RUNNER_CHECK_V2.json') and
        qualification['status'] == 'PASS_PACED_RUNNER_V2_DEVELOPMENT_ONLY' and qualification['code'] == admission['code'] and
        admission['executable'] == qualified_interpreter(), 'Run qualification or interpreter differs')
    for b in admission['code']: verify(b)
    require(exact_process(admission['owner']) is None, 'Run preparer still active')
    output = Path(admission['output']); state = Path(admission['state'])
    require(output.resolve().is_relative_to(LOCAL/'n4') and state.resolve() == LOCAL/'supervision', 'Run output/state escaped campaign')
    require(not (output/'RESULT.json').exists(), 'Preserve terminal attempt; prepare a fresh derivative')
    # The existing supervisor publishes direct child identity shortly after spawn.
    deadline = time.monotonic()+8
    while True:
        try: supervised_identity(state); break
        except ValueError:
            if time.monotonic() >= deadline: raise
            time.sleep(.1)
    with writer_lock(output/'run.owner.lock'):
        freeze(output/'RUN_OWNER.json', dict(owner=identity(process), admission=bind(admission_path)))
        collected = []; error = None
        try:
            _, plan = admit_plan(Path(admission['plan']['path']))
            require(plan['required'] == admission['required'], 'Run census differs')
            for index, row in enumerate(plan['rows']):
                collected.append(collect_one(plan, index, output/'cells'/row['cell_id'], state, admission['code']))
                freeze(output/'progress'/f'{index+1:04d}.json', dict(completed=index+1, total=plan['required'], cell=collected[-1], integrated_N4_cells=0))
        except BaseException as exc:
            error = type(exc).__name__+': '+str(exc)[:2000]
        freeze(output/'RESULT.json', dict(schema=RUN_SCHEMA, status='COLLECTED_PACED_APPLICATION_PANEL_REQUIRES_REVIEW' if error is None else 'FAILED_PACED_APPLICATION_RUN_PRESERVED',
            owner=identity(process), admission=bind(admission_path), completed=len(collected), required=admission['required'],
            collected=collected, error=error, integrated_N4_cells=0, N4_accepted=False, continuity_included=False,
            utc=datetime.now(timezone.utc).isoformat()))
        require(error is None, 'Application panel failed; attempt preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare'); prep.add_argument('--plan', type=Path, required=True); prep.add_argument('--output', type=Path, required=True)
    launch = sub.add_parser('run'); launch.add_argument('--admission', type=Path, required=True)
    child = sub.add_parser('child'); child.add_argument('--permit', type=Path, required=True); child.add_argument('--nonce', required=True)
    args = parser.parse_args()
    if args.command == 'prepare': prepare(args.plan, args.output)
    elif args.command == 'run': run(args.admission)
    else: child_main(args.permit, args.nonce)
