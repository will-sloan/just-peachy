"""Adopt the reviewed S6D physical bank after actual qualification; see README."""
from __future__ import annotations
import argparse
import copy
import datetime as dt
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
SIM = Path(__file__).resolve().parents[1]
R = SIM / 'reports/S6D/20260913T195357Z'
G = Path('G:/Just_Peachy_S6D/20260913T195357Z')
PREP = R / 'runner/bank_queue_preparation_v1'
THREAD = '01a0812d-3ff0-7ed0-a06c-4df61b62a459'
PREP_SHA = '0e77be672f3b39fb6d20c152b1c7e741cb6a9a0821651a1642133c65a6f457e8'

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def require(ok, message):
    if not ok:
        raise ValueError(message)

def bind(p):
    p = Path(p).resolve()
    require(p.stat().st_size <= 16 * 2**20 and p.suffix.lower() not in ('.wav', '.pcm24'), 'metadata binding only')
    data = p.read_bytes()
    return dict(path=str(p), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

def verify(b):
    actual = bind(b['path'])
    require(all(actual[k] == b[k] for k in ('bytes', 'sha256')), 'changed binding: ' + b['path'])
    return actual

def save(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')

def charge(rows):
    return sum((Fraction(str(x['duration_sec'])) + 4 + Fraction(16383, 48000) for x in rows), Fraction())

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--qualification-review', type=Path, required=True)
    ap.add_argument('--output', type=Path, default=R / 'runner/bank_queue_v1')
    args = ap.parse_args()
    out = args.output.resolve()
    require(not out.exists() and out.is_relative_to(R / 'runner'), 'fresh runner directory required')
    require(dt.datetime.now(dt.timezone.utc) < dt.datetime(2026, 9, 16, 19, 8, 57, tzinfo=dt.timezone.utc), 'campaign closeout reserve reached')
    qb = bind(args.qualification_review)
    qual = read(qb['path'])
    require(qual.get('status') == 'ROOT_ACCEPTED_PHYSICAL_QUALIFICATION_WITH_LIMITATIONS', 'actual root scientific qualification required')
    require(qual.get('root_owner_thread_id') == THREAD and qual.get('bank_collection_admitted') is True, 'exact root bank authority required')
    for field in ('routes_reviewed', 'all_four_QA_verified', 'processed_tail_reviewed', 'observer_effect_reviewed', 'owners_closed_and_restored'):
        require(qual.get(field) is True, 'qualification missing ' + field)
    require(len(qual.get('limitations', [])) >= 4, 'explicit scientific limitations must be retained')
    for b in qual['evidence_bindings']:
        verify(b)
    pb = bind(PREP / 'QUEUE_PREPARATION_RECEIPT.json')
    require(pb['sha256'] == PREP_SHA, 'exact independently prepared bank required')
    prep = read(pb['path'])
    for field in ('queue', 'approval_proposal', 'review', 'runner', 'owner', 'bridge', 'helper', 'readme', 'source_review', 'runner_review'):
        verify(prep[field])
    review = read(prep['review']['path'])
    require(review['status'] == 'PASS_METADATA_AND_SOURCE_REVIEW' and review['counts']['bank'] == 394, 'independent metadata review required')
    ledger_path = R / 'physical_ledger.json'
    ledger = read(ledger_path)
    existing = ledger['passes']
    require(len(existing) == 33 and all(x['status'] == 'PASS' for x in existing), 'this admission is for exactly33 closed qualifying attempts; changed history requires a new reviewed admission')
    existing_ids = {x['attempt_id'] for x in existing}
    original = read(prep['queue']['path'])
    queue = copy.deepcopy(original)
    require(queue['owner_thread_id'] == queue['owner_session_id'] == THREAD and queue['fixture_only'] is False, 'actual owner queue')
    groups = []
    replacements = {}
    all_attempts = []
    for group in prep['groups']:
        old_pb, old_ab = verify(group['plan']), verify(group['authorization_proposal'])
        plan = read(old_pb['path'])
        auth = read(old_ab['path'])
        require(auth['root_review_passed'] is False and plan['physical_qualification_review'] is None, 'preserve original unapproved proposals')
        plan.update(status='ROOT_ADMITTED_BANK_COLLECTION_WITH_LIMITATIONS', physical_qualification_review=qb, no_execution_authorization_created=False)
        plan.pop('adoption_required', None)
        for attempt in plan['attempts']:
            require(attempt['attempt_id'] not in existing_ids, 'attempt already charged')
            folder = Path(plan['payload_root']) / 'beam_bank' / attempt['case_id'] / attempt['profile'] / attempt['attempt_id']
            require(not folder.exists(), 'existing attempt destination: ' + str(folder))
            if attempt['profile'] != 'P_INPUT_QA6':
                require(attempt['stream_identity_qualification'] == 'PENDING_ROOT_ACTUAL_MAIN_SCAN_QUALIFICATION', 'unexpected prior qualification')
                attempt['stream_identity_qualification'] = 'QUALIFIED_ROUTE_WITH_RECORDED_LIMITATIONS'
                attempt['physical_qualification_review'] = qb
        directory = out / 'groups' / group['group_id']
        save(directory / 'CAPTURE_PLAN.json', plan)
        plan_binding = bind(directory / 'CAPTURE_PLAN.json')
        auth.update(schema='s6d-root-bank-admission.v1', root_review_passed=True, plan_sha256=plan_binding['sha256'],
                    physical_qualification_review=qb, ledger_before_admission=bind(ledger_path),
                    scope='Root admits this exact group within the60-stage immutable serial bank. Scientific limits and per-scene processed-only status remain explicit. No extra attempts or source/gain changes.')
        save(directory / 'CAPTURE_AUTHORIZATION.json', auth)
        auth_binding = bind(directory / 'CAPTURE_AUTHORIZATION.json')
        replacements[old_pb['path']] = plan_binding
        replacements[old_ab['path']] = auth_binding
        groups.append(dict(group_id=group['group_id'], plan=plan_binding, authorization=auth_binding, attempts=len(plan['attempts'])))
        all_attempts.extend(plan['attempts'])
    require(len(groups) == 20 and len(all_attempts) == len({a['attempt_id'] for a in all_attempts}) == 394, '20groups/394unique attempts')
    current_charge = sum(Fraction(str(x['charged_playback_s'])) for x in existing)
    bank_charge = charge(all_attempts)
    require(current_charge + bank_charge == Fraction('19670.0340625') and len(existing) + len(all_attempts) == 427, 'exact total427/19670.0340625 forecast')
    free = dict(C=shutil.disk_usage('C:/').free, G=shutil.disk_usage('G:/').free)
    require(free['C'] >= 50*2**30 and free['G'] >= 75*2**30, 'storage floors')
    stage_attempts = []
    for j, old in zip(queue['jobs'], original['jobs']):
        require(j['kind'] == 'hardware' and j['allow_owned_termination'] is False, 'cooperative hardware ownership required')
        argv = j['argv']
        for option, hash_option in (('--plan', '--plan-sha256'), ('--authorization', '--authorization-sha256')):
            pos = argv.index(option) + 1
            b = replacements[argv[pos]]
            argv[pos] = b['path']
            argv[argv.index(hash_option)+1] = b['sha256']
        for b in j['source_bindings']:
            if b['path'] not in replacements:
                verify(b)
        sources = [replacements.get(b['path'], b) for b in j['source_bindings']] + [qb, bind(__file__), bind(Path(__file__).with_name('README_S6D_BANK_ADMIT_V1.md'))]
        j['source_bindings'] = list({b['path']: b for b in sources}.values())
        for artifact in j['expected_artifacts']:
            fields = artifact.get('expected_fields', {})
            if 'plan.sha256' in fields:
                fields['plan.sha256'] = argv[argv.index('--plan-sha256')+1]
                fields['authorization.sha256'] = argv[argv.index('--authorization-sha256')+1]
            if fields.get('attempt.profile') in ('P_MAIN6', 'P_SCAN6'):
                fields['physical_stream_identity_qualification'] = 'QUALIFIED_ROUTE_WITH_RECORDED_LIMITATIONS'
        require(j['predecessor_job_id'] == (queue['jobs'][len(stage_attempts)-1]['job_id'] if stage_attempts else None), 'literal serial predecessor order')
        stage_attempts.append(argv[argv.index('--attempt-ids')+1:])
        require(not Path(j['completion_path']).parent.exists() and not (R / 'hardware_batches' / j['job_id']).exists(), 'old stage output must never be reused')
    require(len(queue['jobs']) == 60 and [a for stage in stage_attempts for a in stage] == [a['attempt_id'] for a in all_attempts], 'exact preQA/body/postQA order')
    save(out / 'QUEUE.json', queue)
    queue_binding = bind(out / 'QUEUE.json')
    spec = importlib.util.spec_from_file_location('s6d_bank_admitted_runner', prep['runner']['path'])
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    approval = read(PREP / 'APPROVAL_PROPOSAL.json')
    require(approval['approved_job_sha256'] == [], 'original approval remains empty')
    approval.update(queue_sha256=queue_binding['sha256'], authorization_ref=str(out / 'ROOT_QUEUE_REVIEW.json'),
                    approved_job_sha256=[runner.digest(j) for j in queue['jobs']])
    approval.pop('proposed_job_sha256', None)
    require(runner.validate_queue(queue, approval, queue_binding['sha256']) is True, 'V4 validates literal approved queue')
    save(out / 'APPROVAL.json', approval)
    checks = []
    for group in groups:
        log = out / 'validation' / (group['group_id'] + '.log')
        log.parent.mkdir(parents=True, exist_ok=True)
        argv = [queue['jobs'][0]['argv'][0], '-B', prep['owner']['path'], 'check-plan', '--plan', group['plan']['path'], '--authorization', group['authorization']['path']]
        with log.open('x', encoding='utf-8') as f:
            p = subprocess.run(argv, cwd=SIM, stdout=f, stderr=subprocess.STDOUT, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
        require(p.returncode == 0, 'owner check-plan failed: ' + str(log))
        checks.append(dict(group_id=group['group_id'], argv=argv, result=bind(log), exit_code=p.returncode))
    receipt = dict(status='ROOT_ADMITTED_WHOLE_PHYSICAL_BANK_PENDING_LAUNCH', utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                   root_owner_thread_id=THREAD, queue=queue_binding, approval=bind(out/'APPROVAL.json'), runner=prep['runner'],
                   qualification=qb, preparation=pb, metadata_review=prep['review'], helper=bind(__file__),
                   readme=bind(Path(__file__).with_name('README_S6D_BANK_ADMIT_V1.md')), groups=groups, owner_plan_checks=checks,
                   current_physical_attempts=33, admitted_bank_attempts=394, total_forecast_attempts=427,
                   bank_charged_playback_seconds=float(bank_charge), total_forecast_charged_seconds=float(current_charge + bank_charge),
                   storage_free_bytes=free, expected_new_physical_bytes_conservative=round(float(bank_charge)*900000),
                   source_binding_policy='Small source/config bytes are periodically checked; each bounded group source audio is exactly verified by owner before use. No repeated full-bank audio hashing in health loop.',
                   progression='60 serial immutable jobs; actual preQA gate precedes each body; owner restoration and postQA precede next group. No arbitrary log-generated commands. Any failed predicate stops the queue.',
                   hardware_calls=0, playback_started=False, automatic_model_resume_installed=False)
    save(out/'ROOT_QUEUE_REVIEW.json', receipt)
    print(json.dumps(dict(status=receipt['status'], receipt=bind(out/'ROOT_QUEUE_REVIEW.json'), attempts=394, stages=60)))

if __name__ == '__main__':
    main()
