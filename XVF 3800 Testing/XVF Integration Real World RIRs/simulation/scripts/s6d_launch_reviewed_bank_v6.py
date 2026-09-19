"""Launch the admitted remaining hardware bank after C12 closure; README adjacent."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

SIM = Path(__file__).resolve().parents[1]
R = SIM/'reports/S6D/20260913T195357Z'
G = Path('G:/Just_Peachy_S6D/20260913T195357Z')
Q = R/'runner/bank_queue_v6'
STATE = G/'runner/bank_queue_v6/supervisor_state'

def need(ok, reason):
    if not ok:
        raise ValueError(reason)

def bound(path):
    path = Path(path).resolve(); before = path.stat(); raw = path.read_bytes(); after = path.stat()
    need((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'Changed metadata during hash')
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def verify(ref):
    need(bound(ref['path']) == ref, 'Changed metadata: ' + ref['path'])
    return read(ref['path'])

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m)
    return m

def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')
    return bound(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--c12-acceptance', type=Path, required=True)
    parser.add_argument('--c12-acceptance-sha256', required=True)
    args = parser.parse_args()
    rr = bound(Q/'ROOT_QUEUE_REVIEW.json')
    need(rr['sha256'] == '54f991e5cb1918adf0e465b218073f8d5b9dee629ffdbc238c46b35c212c6f98', 'Exact admitted bank V6 required')
    review = verify(rr)
    independent = bound(R/'runner/bank_queue_v6_independent_v1/INDEPENDENT_REVIEW.json')
    need(independent['sha256'] == 'ab0d54ee40bbf02cf453f4b34795bebd5f4aca300b8716f41411dbad982bfb26', 'Exact independent literal review required')
    check = verify(independent)
    need(check['status'] == 'PASS_INDEPENDENT_LITERAL_BANK_REVIEW' and check['root_receipt'] == rr and check['queue'] == review['queue'] and check['approval'] == review['approval'], 'Actual independent joins differ')
    c12ref = bound(args.c12_acceptance)
    need(c12ref['sha256'] == args.c12_acceptance_sha256, 'Exact root C12 closure required')
    c12 = verify(c12ref)
    need(c12['status'] == 'ROOT_ACCEPTED_C12_ALL12_COLLECTION' and c12['accepted'] == c12['planned'] == 12 and c12['owner_thread_id'] == '01a0812d-3ff0-7ed0-a06c-4df61b62a459', 'Complete current C12 collection required')
    need(c12['old_failure_credit'] == 0 and c12['all_owners_closed'] is True, 'Old failures and ownership closure required')
    for phase in c12['phase_closures']:
        closure = verify(phase['supervisor_closure'])
        need(closure['result']['action'] == 'FINISH' and closure['owner_lock'] == 'RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT' and closure['keep_awake']['restored'] is True and closure['payload_census_closure']['closed'] is True, 'C12 supervisor not fully closed')
        need(not (Path(phase['state_dir'])/'SUPERVISOR_LOCK.json').exists(), 'C12 live lock remains')
    base = SIM/'scripts/s6d_C12_root_admit_v2.py'
    need(bound(base)['sha256'] == '6730ecf67f287dd972ac8c8b793b4899950800d892eadbb8f893b464438a9f14', 'Allocation checker changed')
    allocation_helpers = load(base, 'bankV6_launch_allocation')
    snapshot, current = allocation_helpers.runtime_snapshot()
    allocation = allocation_helpers.allocation_decision(snapshot, current, c12['closed_instances'])
    need(datetime.now(timezone.utc) < datetime(2026,9,16,19,8,57,tzinfo=timezone.utc), 'Original no-new-job deadline reached')
    import shutil
    free = {d: shutil.disk_usage(d).free for d in ('C:/','G:/')}
    need(free['C:/'] >= 50*2**30 and free['G:/'] >= 75*2**30, 'Original free-space floors')
    queue, approval = verify(review['queue']), verify(review['approval'])
    need(len(queue['jobs']) == 54 and review['current_charged_attempts'] == 121 and review['new_attempts_admitted'] == 312, 'Exact remaining scope required')
    need(queue['payload_policy']['max_new_payload_bytes'] == 40*2**30, 'Physical cap remains40GiB')
    guards = {}
    for job in queue['jobs']:
        for ref in job['source_bindings']:
            key = str(Path(ref['path']).resolve())
            need(key not in guards or guards[key] == ref, 'Conflicting source guard')
            guards[key] = ref
    for ref in guards.values():
        need(bound(ref['path']) == ref, 'Admitted per-job source changed')
    need(bound(review['runner']['path']) == review['runner'], 'Frozen V4 supervisor changed')
    runner = load(review['runner']['path'], 'bankV6_exact_runner')
    runner.validate_queue(queue, approval, review['queue']['sha256'])
    need(not STATE.exists() and not (Q/'ROOT_LAUNCH.json').exists(), 'Fresh launch state required')
    preflight = save(Q/'ROOT_LAUNCH_PREFLIGHT.json', dict(status='ROOT_PHYSICAL_BANKV6_LAUNCH_PREFLIGHT_PASS', utc=datetime.now(timezone.utc).isoformat(),
        bank_admission=rr, independent_review=independent, c12_acceptance=c12ref, process_snapshot=snapshot,
        allocation=allocation, free_bytes=free, source_guards_verified=len(guards), initial_allocation='Hardware only; no other NN or device owner at launch. Any later host overlap needs separate root admission.',
        forecast_attempts=433, forecast_charged_seconds=19818.0819375, user_analog_output_disconnection_confirmation='Preserved explicit user authorization in current task',
        launcher=bound(__file__), readme=bound(Path(__file__).with_name('README_S6D_LAUNCH_REVIEWED_BANK_V6.md'))))
    argv = [sys.executable, '-B', review['runner']['path'], '--queue', review['queue']['path'], '--approval', review['approval']['path'],
            '--queue-sha256', review['queue']['sha256'], '--approval-sha256', review['approval']['sha256'], '--state-dir', str(STATE), '--keep-awake']
    with (Q/'SUPERVISOR.stdout.log').open('xb') as out, (Q/'SUPERVISOR.stderr.log').open('xb') as err:
        child = subprocess.Popen(argv, cwd=SIM, stdin=subprocess.DEVNULL, stdout=out, stderr=err, shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
    import psutil
    launched = save(Q/'ROOT_LAUNCH.json', dict(status='SUPERVISOR_LAUNCHED', utc=datetime.now(timezone.utc).isoformat(), pid=child.pid,
        creation_time=psutil.Process(child.pid).create_time(), argv=argv, cwd=str(SIM), preflight=preflight,
        queue=review['queue'], approval=review['approval'], state_dir=str(STATE), stages=54, future_attempts=312, completed_new_stages=0))
    print(json.dumps(dict(launch=launched, pid=child.pid, stages=54, future_attempts=312)))

if __name__ == '__main__':
    main()
