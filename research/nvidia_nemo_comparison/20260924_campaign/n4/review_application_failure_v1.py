"""Narrow read-only failure continuation gate. README_APPLICATION_OUTCOMES_V1.md."""
from pathlib import Path
import re
from common import bind, fingerprint, verify
from metric_process import exact_process
from paced_child_admission_v6 import assert_plain_path, digest, validate_input, validate_permit
from paced_slot import key
from reservation_budget_v1 import require
from review_application_transport_v8 import record, finite

PRIMARY = 'session lane {lane} did not finish within 60 seconds'
PARENT_ERROR = 'ValueError: Application child did not exit normally'


def classify(child, cell, closure, engine, observation, payload):
    """No success credit; allow only the observed finite lane-drain failure."""
    lane = next((n for n in ('edge-speaker', 'edge-asr')
                 if engine['finalization_error'] == PRIMARY.format(lane=n)), None)
    require(lane is not None, 'Unrecognized application failure')
    cause = PRIMARY.format(lane=lane)
    require(closure['error'] == PARENT_ERROR and closure['cleanup_error'] is None,
            'Parent admission, supervision or cleanup failed')
    require(child['status'] == 'FAILED_APPLICATION_CELL_PRESERVED'
        and child['error'] == 'RuntimeError: session finalization failed: '+cause,
        'Child primary failure differs')
    require(cell['status'] == 'FAILED_PRESERVED' and cell['source_start_requested'] is True
        and cell['controller_closed'] is True and cell['controller_worker_exited'] is True
        and cell['callback_errors'] == [] and cell['complete_N4_acceptance'] is False
        and cell['integrated_N4_cells'] == 0, 'Failed Controller did not close')
    allowed = ["Source execution: RuntimeError('session finalization failed: "+cause+"')",
        'Source execution did not complete', 'Controller error: session finalization failed: '+cause,
        'Application closure: TypeError("\'NoneType\' object is not subscriptable")',
        'Viewport: RuntimeError("{\'where\': \'viewport\', \'type\': \'ValueError\', \'message\': \'Source clock availability regressed or disagrees\'}")',
        "Source delivery: RuntimeError('Source delivery capture failed')"]
    require(cell['errors'][:3] == allowed[:3] and all(e in allowed for e in cell['errors'])
        and len(cell['errors']) == len(set(cell['errors'])), 'Additional application failure')
    require(engine['state'] == 'FAILED' and engine['job'] == payload['job']
        and engine['engine_class'] == payload['contract']['engine'], 'Different failed job or engine')
    require(engine['threads'] and all(t['alive'] is False for t in engine['threads'].values()),
        'Application thread remains alive')
    require(engine['workers'] and all(w['closed'] is True and w['thread_alive'] is False
        and w['error'] is None for w in engine['workers'].values()), 'Worker closure failed')
    require(engine['text_writers'] and all(w['closed'] is True and w['thread_alive'] is False
        and w['error'] is None and w['sink_closed'] is True for w in engine['text_writers']),
        'Text writer remains active or failed')
    frames = payload['job']['frames']
    source = engine['source']
    require(source['actual_FileSource'] is True and source['sent'] == frames
        and source['path'] == payload['job']['audio_path'] and source['start_sample'] == 0
        and source['journal']['committed_samples'] == frames and source['journal']['overrun_reads'] == 0,
        'Saved source incomplete or different')
    require(observation['job_fingerprint'] == fingerprint(payload['job'])
        and observation['status'] == 'FAILED_SOURCE_DELIVERY_OBSERVATION'
        and observation['source_thread_exited'] is True
        and observation['source_sent'] == observation['journal_committed'] == frames
        and observation['errors'] == {'journal_not_cleanly_finished': 1}
        and observation['summary']['complete_source'] is True
        and observation['summary']['failed_appends'] == 0,
        'Source failure was not solely post-delivery lane drainage')
    return dict(outcome='FAILED_LANE_DRAIN_TIMEOUT', lane=lane, drain_limit_seconds=60,
        source_frames_delivered=frames, success_credit=False, integrated_N4_cells=0,
        N4_accepted=False, latency_accepted=False, CM5_qualified=False)

def validate_lifetime(value, *, owner, executable, script, argv_sha256, desktop, cpu, expected_exit):
    """Validate recorded normal closure, plus fresh exit of every observed identity.

    This checks a receipt; it cannot recover unobserved short-lived job members.
    Model-free qualification also uses CPU14 native fixture receipts.
    """
    require(cpu == 4 and expected_exit == 1, 'Unsupported expected CPU')
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
        and value['root_exit_code'] == expected_exit and value['error'] is None and value['cleanup_errors'] == []
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
    return dict(status='PASS_RECORDED_EXIT_ONE_PRIVATE_PROCESS_CLOSURE', observed_identities=len(observed),
        job_total_assignments=job['total'], unobserved_assignment_count=job['total']-len(observed),
        members_exited_during_observation=races, suspended_at=times[0], resumed_at=times[1], closed_at=times[-1],
        complete_process_history_available=False)


def review(folder, *, payload, plan_sha256, coordinator, code, executable, script,
           coordinator_argv, state):
    """Reconstruct the failed cell's ownership and source join before continuing."""
    folder = Path(folder).resolve(strict=True)
    assert_plain_path(folder, folder.parent); validate_input(payload)
    require(len(code) <= 512 and script in code, 'Unbound failure reader or child runner')
    for b in code+[executable]: verify(b)
    bindings = []
    def read(relative):
        b, value = record(folder/relative, folder)
        bindings.append(b)
        return b, value
    ib, actual_input = read('transport/INPUT.json')
    require(actual_input == payload, 'Failed input differs from reconstructed plan')
    _, permit = read('transport/PERMIT.json')
    validate_permit(permit, nonce=permit['nonce'], application=permit['application'],
        parent=coordinator, desktop=permit['desktop'])
    require(permit['plan_sha256'] == plan_sha256 and permit['code'] == code and permit['input'] == ib
        and Path(permit['state']).resolve() == Path(state).resolve()
        and Path(permit['output']).resolve() == folder/'application'
        and permit['coordinator_argv_sha256'] == fingerprint(coordinator_argv), 'Foreign failed permit')
    argv = [executable['path'], '-B', script['path'], 'child', '--permit',
            str(folder/'transport/PERMIT.json'), '--nonce', permit['nonce']]
    require(permit['application_argv_sha256'] == fingerprint(argv), 'Different failed child command')
    _, lifetime = read('transport/LIFETIME.json')
    lifetime_review = validate_lifetime(lifetime, owner=permit['application'], executable=executable,
        script=script, argv_sha256=fingerprint(argv), desktop=permit['desktop'], cpu=4, expected_exit=1)
    _, closure = read('PARENT_CLOSURE.json')
    require(closure['lifecycle'] == lifetime, 'Parent and child lifetime differ')
    release = closure['slot_release']
    require(release['status'] == 'APPLICATION_SLOT_RELEASED' and release['coordinator'] == coordinator
        and release['application'] == permit['application'] and release['child_cleanup_performed_by_guard'] is False,
        'Owned application slot did not release normally')
    _, child = read('transport/CHILD_RESULT.json')
    cb, cell = read('application/RESULT.json')
    require(child['owner'] == permit['application'] and child['input'] == ib
        and child['cell_result'] == cb, 'Child failure provenance differs')
    _, engine = read('application/ENGINE_CLOSURE.json')
    _, observation = read('application/delivery/OBSERVATION.json')
    verdict = classify(child, cell, closure, engine, observation, payload)
    rb, resources = read('application/resources/RESULT.json')
    require(cell['resources'] == rb and resources['owner'] == permit['application']
        and resources['status'] == 'OBSERVED_HOST_RESOURCES' and resources['error'] is None
        and resources['observer_thread_exited'] is True, 'Resource observer failed')
    for owner in resources['sampled_owners']:
        require(exact_process(owner) is None, 'A sampled exact process remains alive')
    for b in bindings: verify(b)
    return dict(schema='n4-recorded-lane-timeout-v1', status='VERIFIED_FAILED_CELL_NO_ACCEPTANCE',
        cell_id=payload['cell_id'], job_sha256=fingerprint(payload['job']),
        plan_sha256=plan_sha256, evidence=bindings, failure=verdict,
        lifetime_review=lifetime_review, integrated_N4_cells=0, N4_accepted=False)


