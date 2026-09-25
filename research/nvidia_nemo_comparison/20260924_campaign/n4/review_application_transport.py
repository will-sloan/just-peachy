"""Review stopped application transport evidence. README_APPLICATION_TRANSPORT_REVIEW.md."""
import json
import math
from pathlib import Path
import re

from common import bind, fingerprint, verify
from metric_process import exact_process
from paced_child_admission import (assert_plain_path, digest, validate_input,
    validate_permit, validate_lease)
from paced_slot import competitors, key, MAX_CELL_BYTES
from review_scoring_bank import require

MAX_JSON = 1024*1024


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def unique_pairs(pairs):
    result = {}
    for name, value in pairs:
        require(name not in result, 'Duplicate JSON key')
        result[name] = value
    return result


def record(path, root):
    """Snapshot small closed records with no reparse paths or ambiguous JSON."""
    path = assert_plain_path(path, root)
    require(0 < path.stat().st_size <= MAX_JSON, 'Transport record exceeds byte bound')
    binding = bind(path)
    with path.open('rb') as stream: data = stream.read(MAX_JSON+1)
    require(len(data) == binding['bytes'] <= MAX_JSON, 'Transport record changed during read')
    value = json.loads(data.decode('utf-8-sig'), object_pairs_hook=unique_pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))
    require(type(value) is dict, 'Transport record must be an object')
    verify(binding)
    return binding, value


def validate_lifetime(value, *, owner, executable, script, argv_sha256, desktop, cpu):
    """Validate recorded normal closure, plus fresh exit of every observed identity.

    This checks a receipt; it cannot recover unobserved short-lived job members.
    Model-free qualification also uses CPU14 native fixture receipts.
    """
    require(cpu in (4, 14), 'Unsupported expected CPU')
    key(owner)
    require(value['status'] == 'OWNED_PROCESS_LIFETIME_CLOSED' and value['owner'] == owner,
        'Application lifetime owner or completion differs')
    for name, expected in (('executable', executable), ('script', script)):
        require(value[name] == expected, 'Lifetime '+name+' differs'); verify(expected)
    require(value['argv_sha256'] == argv_sha256 and digest(argv_sha256), 'Lifetime command differs')
    require(value['desktop'] == desktop and re.fullmatch('codex-n1-n4-[0-9a-f]{32}', desktop),
        'Lifetime private desktop differs')
    require(type(value['input_desktop_before']) is str and bool(value['input_desktop_before'])
        and value['input_desktop_before'] == value['input_desktop_after']
        and value['input_desktop_before'] != desktop, 'Input desktop changed or was the private desktop')
    require(value['resumed'] is True and value['forced'] is False and value['job_empty_verified'] is True
        and value['observed_members_exited'] is True and type(value['root_exit_code']) is int
        and value['root_exit_code'] == 0 and value['error'] is None and value['cleanup_errors'] == []
        and value['source_execution_authorized'] is False, 'Unclean, forced or unexecuted application lifetime')
    job = value['final_job']
    require(set(job) == {'active', 'total', 'terminated'} and all(type(v) is int for v in job.values())
        and job['active'] == 0 and job['total'] >= 1 and job['terminated'] == 0,
        'Final job accounting is not normal empty closure')
    events = value['events']
    require(type(events) is list and 5 <= len(events) <= 1000, 'Lifetime event census differs')
    require([r['kind'] for r in events[:2]] == ['spawned_suspended_and_assigned', 'resumed_after_registration']
        and [r['kind'] for r in events[-2:]] == ['cancel_requested', 'all_observed_member_identities_exited']
        and all(r['kind'] == 'job_members_observed' for r in events[2:-2]), 'Lifetime event ordering differs')
    times = [r['monotonic'] for r in events]
    require(all(finite(v) and v > 0 for v in times) and times == sorted(times), 'Lifetime event clock differs')
    spawn = events[0]
    require(spawn['owner'] == owner and spawn['affinity'] == [cpu] and spawn['argv_sha256'] == argv_sha256
        and spawn['job'] == {'active': 1, 'total': 1, 'terminated': 0}, 'Suspended root identity or placement differs')
    observed = {key(owner): owner}; races = 0
    for event in events[2:-2]:
        members = event['members']; require(type(members) is list and len(members) <= 16, 'Job member census exceeds limit')
        seen = set()
        for member in members:
            require(type(member.get('pid')) is int and member['pid'] > 0 and member['pid'] not in seen,
                'Duplicate or invalid job member PID'); seen.add(member['pid'])
            if 'create_time' not in member:
                require(set(member) == {'pid', 'exited_during_observation'} and member['exited_during_observation'] is True,
                    'Unknown member identity failure'); races += 1; continue
            member_key = key(member)
            require(member['affinity'] == [cpu] and type(member['executable']) is str and bool(member['executable'])
                and digest(member['argv_sha256']) and type(member['parent_pid']) is int and member['parent_pid'] > 0,
                'Observed job member placement or command missing')
            observed[member_key] = dict(pid=member['pid'], create_time=member['create_time'])
    exited = events[-1]['owners']; require(type(exited) is list, 'Exit owner census missing')
    require(len(exited) == len(observed) and {key(v) for v in exited} == set(observed), 'Observed/closed identity census differs')
    require(job['total'] >= len(observed), 'Observed owners exceed total job assignments')
    for who in observed.values(): require(exact_process(who) is None, 'An exact application identity is still active')
    return dict(status='PASS_RECORDED_NORMAL_PRIVATE_PROCESS_CLOSURE', observed_identities=len(observed),
        job_total_assignments=job['total'], unobserved_assignment_count=job['total']-len(observed),
        members_exited_during_observation=races, suspended_at=times[0], resumed_at=times[1], closed_at=times[-1],
        complete_process_history_available=False)


def review_cell(folder, *, payload, plan_sha256, coordinator, code, executable, coordinator_argv, state):
    """Internal join; caller must independently reconstruct the accepted panel plan.

    No standalone acceptance CLI: arbitrary caller-provided expectations do not
    establish a qualified plan. This function never launches or signals anything.
    """
    folder = Path(folder).absolute(); root = folder.parent.resolve(strict=True)
    folder = assert_plain_path(folder, root); validate_input(payload); key(coordinator)
    require(exact_process(coordinator) is None, 'Review requires a stopped panel coordinator')
    require(digest(plan_sha256), 'Expected reconstructed plan digest missing')
    require(type(code) is list and 0 < len(code) <= 128 and len({b['path'] for b in code}) == len(code), 'Expected code census differs')
    for b in [executable, *code]: verify(b)
    scripts = [b for b in code if Path(b['path']).name == 'paced_application_runner.py']
    require(len(scripts) == 1, 'Exactly one bound fixed runner required'); script = scripts[0]
    bindings = []
    def read(relative):
        b, value = record(folder/relative, root); bindings.append(b); return b, value
    input_binding, actual_input = read('transport/INPUT.json')
    require(fingerprint(actual_input) == fingerprint(payload), 'Input differs from reconstructed panel cell')
    _, permit = read('transport/PERMIT.json')
    validate_permit(permit, nonce=permit['nonce'], application=permit['application'], parent=coordinator, desktop=permit['desktop'])
    require(permit['plan_sha256'] == plan_sha256 and permit['code'] == code and permit['input'] == input_binding,
        'Permit plan, code or input differs')
    require(Path(permit['state']).resolve() == Path(state).resolve()
        and Path(permit['output']).resolve() == folder/'application', 'Permit state or application output differs')
    require(permit['coordinator_argv_sha256'] == fingerprint(coordinator_argv), 'Coordinator command differs')
    argv = [executable['path'], '-B', script['path'], 'child', '--permit', str(folder/'transport/PERMIT.json'), '--nonce', permit['nonce']]
    require(permit['application_argv_sha256'] == fingerprint(argv), 'Application command differs')
    lifetime_binding, lifetime = read('transport/LIFETIME.json')
    process_review = validate_lifetime(lifetime, owner=permit['application'], executable=executable,
        script=script, argv_sha256=fingerprint(argv), desktop=permit['desktop'], cpu=4)
    _, lease = read('transport/LEASE.json')
    # A terminal lease is normally expired now. Validate its content at the
    # recorded issuance time, explicitly without asserting live freshness.
    validate_lease(lease, permit, fingerprint(permit), now_monotonic=lease['issued_monotonic'], previous_sequence=0)
    require(process_review['suspended_at'] <= lease['issued_monotonic'] <= process_review['closed_at'], 'Final lease outside process lifetime')
    cancel = assert_plain_path(folder/'transport/CANCEL', root)
    require(cancel.is_file() and cancel.stat().st_size == 0, 'Parent cleanup cancellation marker missing')
    bindings.append(bind(cancel))
    child_binding, child = read('transport/CHILD_RESULT.json')
    require(child['status'] == 'COLLECTED_APPLICATION_CELL_REQUIRES_REVIEW' and child['owner'] == permit['application']
        and child['input'] == input_binding and child['error'] is None and child['integrated_N4_cells'] == 0
        and child['N4_accepted'] is False, 'Child completion identity or error differs')
    cell_binding, cell = read('application/RESULT.json')
    require(child['cell_result'] == cell_binding and cell['status'] == 'CELL_CLOSED_REQUIRES_REVIEW'
        and cell['source_start_requested'] is True and cell['errors'] == [] and cell['callback_errors'] == []
        and cell['controller_closed'] is True and cell['controller_worker_exited'] is True
        and cell['source_to_widget_latency_qualified'] is False and cell['complete_N4_acceptance'] is False
        and cell['integrated_N4_cells'] == 0, 'Application terminal receipt incomplete')
    _, prepared = read('application/PREPARED.json')
    require(prepared['status'] == 'PREPARED_NO_SOURCE_OR_MODELS_STARTED' and prepared['desktop'] == permit['desktop']
        and prepared['contract'] == payload['contract'] and prepared['job'] == payload['job']
        and prepared['runtimes'] == payload['runtimes'] and prepared['gallery_preparation'] == payload['gallery_preparation']
        and prepared['logical_client'] == [480, 800] and prepared['active_height_px'] == 184
        and prepared['no_auto_start'] is True and prepared['integrated_N4_cells'] == 0, 'Prepared application identity or geometry differs')
    collected_binding, collected = read('COLLECTED.json')
    require(collected['status'] == 'COLLECTED_SOURCE_PACED_CELL_REQUIRES_REVIEW' and collected['cell_id'] == payload['cell_id']
        and collected['input'] == input_binding and collected['child_result'] == child_binding and collected['lifetime'] == lifetime_binding
        and collected['integrated_N4_cells'] == 0 and collected['N4_accepted'] is False, 'Collected receipt joins differ')
    monitoring = collected['monitoring']
    require(type(monitoring['renewals']) is int and monitoring['renewals'] > 0 and monitoring['renewals'] == lease['sequence']
        and finite(monitoring['elapsed_seconds']) and 0 < monitoring['elapsed_seconds'] <= 3900,
        'Parent monitoring and final lease census differ')
    slot = collected['slot_admission']
    require(slot['coordinator'] == coordinator and slot['supervised_run'] == permit['supervised_run']
        and slot['cpu_affinity'] == [4] and slot['gpu'] is False and slot['source_execution_authorized'] is False
        and type(slot['reservation_bytes']) is int and 0 < slot['reservation_bytes'] <= MAX_CELL_BYTES, 'Slot admission differs')
    census = slot['census']; allowed = [coordinator, permit['supervisor']]
    require(not competitors(census, allowed) and len(census['rows']) == 2
        and {key(r) for r in census['rows']} == {key(r) for r in allowed}, 'Initial slot census is uncertain or incomplete')
    rows = {key(r): r for r in census['rows']}
    require(all(r['affinity'] == [14] for r in rows.values())
        and rows[key(coordinator)]['parent_pid'] == permit['supervisor']['pid']
        and rows[key(coordinator)]['argv_sha256'] == permit['coordinator_argv_sha256']
        and Path(rows[key(coordinator)]['executable']).resolve() == Path(executable['path']).resolve(), 'Coordinator admission observation differs')
    inventory = slot['inventory']
    require(inventory['errors'] == [] and type(inventory['total_logical_bytes']) is int and inventory['total_logical_bytes'] >= 0
        and inventory['total_logical_bytes']+6*1024**3+slot['reservation_bytes'] <= 50*1024**3, 'Recorded shared allowance exceeded')
    _, parent = read('PARENT_CLOSURE.json')
    require(parent['error'] is None and parent['cleanup_error'] is None and parent['lifecycle'] == lifetime
        and parent['integrated_N4_cells'] == 0 and parent['N4_accepted'] is False, 'Parent closure failed or lifetime changed')
    require(parent['slot_release'] == dict(status='APPLICATION_SLOT_RELEASED', coordinator=coordinator, application=permit['application'],
        child_cleanup_performed_by_guard=False, source_execution_authorized=False), 'Parent slot was not released for this application')
    for b in bindings+[executable, *code]: verify(b)
    return dict(status='PASS_APPLICATION_TRANSPORT_JOINS_ONLY', cell_id=payload['cell_id'], collected=collected_binding,
        evidence=bindings, application=permit['application'], coordinator=coordinator, supervisor=permit['supervisor'],
        supervised_run=permit['supervised_run'], process_review=process_review, final_lease_sequence=lease['sequence'],
        full_lease_history_available=False, source_workers_archive_reviewed=False, viewport_reviewed=False,
        resources_reviewed=False, accuracy_qualified=False, controlled_resources_qualified=False,
        source_to_widget_latency_qualified=False, integrated_N4_cells=0, N4_accepted=False,
        limitations=['Caller must independently reconstruct the qualified full panel plan and terminal run census.',
            'Saved transport joins and current identity exit were checked; historical live gates were not rerun.',
            'Only the final renewable lease is retained; continuous renewal/freshness cannot be reconstructed.',
            'Job totals include assignments without sampled identity; complete process history is unavailable.',
            'Source, workers, archive, frontend content, naming, timing and resource evidence still require independent review.'])
