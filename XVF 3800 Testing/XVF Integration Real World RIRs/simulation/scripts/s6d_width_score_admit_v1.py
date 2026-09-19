"""Materialize the one root-reviewed S6D scoring queue. See accompanying README."""
from __future__ import annotations
import hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
R = SIM / 'reports/S6D/20260913T195357Z'
P = R / 'runner/width_score_queue_preparation_v1'
OUT = R / 'runner/width_score_queue_v1'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def bind(path, expected=None):
    path = Path(path).resolve()
    value = dict(path=str(path), bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if expected is not None and value['sha256'] != expected:
        raise ValueError(f'Unexpected source: {path}')
    return value

def verify(value):
    actual = bind(value['path'], value['sha256'])
    if actual['bytes'] != value['bytes']:
        raise ValueError('Binding size changed')
    return actual

def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')

def main():
    if OUT.exists():
        raise ValueError('Preserve existing admission; do not duplicate this queue')
    fixed = {
        'QUEUE_PROPOSAL.json': '9a8631380a3f25866decba8b596178e318afc7bc2a1d01dbe9aa33e402d378f2',
        'APPROVAL_PROPOSAL.json': 'b69e4ead8acec376511fca7130aeef72bcea2d7c26a712def7188cd3a7a8f22c',
        'SOURCE_FREEZE.json': 'd606f004727424636361b0fd9dd2a23c600e06b13284535f0bb6dabf549e3149',
        'INDEX_VALIDATION.json': '39fdce02d5b1d9a5cd0666c85d26e057a82b1e7d55cb9ca2b8353f94d5be847d',
    }
    evidence = [bind(P / name, sha) for name, sha in fixed.items()]
    queue, approval = read(P/'QUEUE_PROPOSAL.json'), read(P/'APPROVAL_PROPOSAL.json')
    recipe = read(P/'ROOT_ADMISSION_RECIPE.json')
    job = queue['jobs'][0]
    if len(queue['jobs']) != 1 or job['kind'] != 'offline' or job['job_id'] != 'OPERATIONAL_WIDTH_SCORE_ALL5760_V1':
        raise ValueError('Unexpected job')
    for binding in job['source_bindings'] + approval['executable_bindings'] + recipe['independent_reviews']:
        verify(binding)
    admission = recipe['required_authorization_values']
    expected_owner = '01a0812d-3ff0-7ed0-a06c-4df61b62a459'
    if any(admission[k] != expected_owner or queue[k] != expected_owner for k in ('owner_thread_id', 'owner_session_id')):
        raise ValueError('Wrong owner')
    for value in admission['prediction_indices']:
        verify(value)
    plan = read(job['argv'][3])
    if any(Path(plan[k]).exists() for k in ('bulk_score_payload_root', 'analysis_report_root')):
        raise ValueError('Scoring output already exists; preserve it')
    disk = {row['path']: shutil.disk_usage(row['path']).free for row in queue['disk_policy']}
    if any(disk[row['path']] < row['minimum_free_bytes'] for row in queue['disk_policy']):
        raise ValueError('Storage floor not met')
    deadline = datetime.fromisoformat(queue['campaign']['deadline_utc']).timestamp() - queue['campaign']['closeout_reserve_s']
    if datetime.now(timezone.utc).timestamp() + job['timeout_s'] + job['stop_grace_s'] >= deadline:
        raise ValueError('Insufficient bounded time')
    admission.update(root_review_passed=True, schema='s6d-root-width-score-admission.v1',
        admitted_utc=datetime.now(timezone.utc).isoformat(), source_preparation=evidence,
        independent_reviews=recipe['independent_reviews'], fresh_free_bytes=disk,
        review='Root reviewed literal matrix/queue, accepted independent3840-file verification,51 protocol fixtures and restored width owner closure. No new model or hardware work.',
        timing_bounds='14400s total/1800s stalled committed progress/45s heartbeat/45s grace are conservative bounds, not measured ETA. Finalization emits genuine validation liveness; partial work is never accepted.',
        overall_S6D_complete=False)
    OUT.mkdir()
    admission_path = OUT/'ROOT_SCORER_ADMISSION_V1.json'
    save(admission_path, admission)
    actual_admission = bind(admission_path)
    job['source_bindings'].append(actual_admission)
    job['expected_artifacts'][0]['expected_fields']['admission.sha256'] = actual_admission['sha256']
    for key in ('production_status', 'final_queue_path', 'final_state_dir', 'unresolved_required_changes'):
        queue.pop(key, None)
    queue['schema'] = 's6d_approved_job_queue_v1'
    queue['root_admission'] = actual_admission
    queue_path = OUT/'QUEUE.json'
    save(queue_path, queue)
    approval.pop('final_approval_path', None)
    approval.update(schema='s6d_queue_approval_v1', queue_sha256=bind(queue_path)['sha256'],
        approved_job_sha256=[hashlib.sha256(json.dumps(job, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()],
        approval_state='ROOT_ACCEPTED_EXACT_OFFLINE_SCORING_ONLY')
    approval_path = OUT/'APPROVAL.json'
    save(approval_path, approval)
    result = dict(status='ADMITTED_PENDING_VALIDATE_ONLY_AND_ROOT_LAUNCH', queue=bind(queue_path), approval=bind(approval_path), admission=actual_admission,
        helper=bind(__file__), hardware_calls=0, model_calls=0, scoring_launches=0)
    save(OUT/'ROOT_QUEUE_REVIEW.json', result)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
