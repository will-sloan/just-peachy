"""Root-owned one-case N6h restart and remaining eleven; see adjacent README."""
from __future__ import annotations
import argparse
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

SIM = Path(__file__).resolve().parents[1]
R = SIM / 'reports/S6D/20260913T195357Z'
G = Path('G:/Just_Peachy_S6D/20260913T195357Z')
Q = R / 'runner/beam_C_queue_proposed_v4'
P = G / 'runner/beam_C_queue_proposed_v4'
OLD = R / 'runner/beam_C_queue_proposed_v3'
OLDP = G / 'runner/beam_C_queue_proposed_v3'
THREAD = '01a0812d-3ff0-7ed0-a06c-4df61b62a459'
DEADLINE = dt.datetime(2026, 9, 16, 19, 8, 57, tzinfo=dt.timezone.utc)

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

# Reuse the already reviewed pure queue transform and full allocation check.
BASE = SIM / 'scripts/s6d_C12_root_admit_v2.py'
import hashlib
if hashlib.sha256(BASE.read_bytes()).hexdigest() != '6730ecf67f287dd972ac8c8b793b4899950800d892eadbb8f893b464438a9f14':
    raise ValueError('Prior helper changed')
b = load(BASE, 'C12_n6h_prior_helpers')
need, read, bound, verify, save, digest = b.require, b.read, b.bound, b.verify, b.save, b.digest
b.Q, b.PROTOCOL, b.STATE, b.OLD_PROTOCOL = Q, P, P / 'pilot_state', OLDP

def pinned(path, sha):
    ref = bound(path)
    need(ref['sha256'] == sha, 'Pinned input changed: ' + str(path))
    return ref, verify(ref)

def inputs():
    refs, vals = {}, {}
    pins = {
        'old_queue': (OLD/'QUEUE.json', '8b5287bf92f2acb2cd20fdda797366027fb80817f901b680c22567f6cf9cbb6c'),
        'old_preparation': (OLD/'PREPARATION.json', '104d051aa9ca003ccd6ed09484cacce6cb304bae422e5622bfd5a1870ae612c3'),
        'old_admission': (OLD/'ROOT_ADMISSION.json', '8da1aead726b1fbacc6f67f4f4f35ebd879ec05a2002df25fe83081e5ca4b7b4'),
        'new_freeze': (R/'application/beam_C_closure_wire_proposal_v1/SOURCE_FREEZE.json', '063005d8236d5b89ed49fc91802231c99852d0c04848babeb760fa61fba26274'),
        'independent': (R/'application/N6h_closure_independent_v1/INDEPENDENT_REVIEW.json', '32c3b04657fc2a793a7d2e468b6afc706fba79c4d76cc6596abb07be5a2bd9c2'),
        'diagnosis': (R/'application/C12_v3_closure_diagnosis_v1/DIAGNOSIS.json', '4fd24e092dd84962b2b715fd63c4196e61d4c674f109cb6cb536d73598107d4a'),
    }
    for key, (path, sha) in pins.items():
        refs[key], vals[key] = pinned(path, sha)
    f = vals['new_freeze']
    need(f['runner']['sha256'] == '7dfe9d8442bdab618edc7760a8e4af8d9178373d85bfecd1fbf422a61ac603ed', 'Exact N6h required')
    for row in f['source_files']:
        for ref in row.values():
            need(bound(ref['path']) == ref, 'N6h source changed')
    for key in ('proposal', 'fixture_receipt', 'diagnosis', 'diff', 'readme'):
        need(bound(f[key]['path']) == f[key], 'Reviewed proposal changed')
    oldm = verify(vals['old_queue']['manifest'])
    need(oldm['runner_helper']['sha256'] == '6de4c1433c1f529e3e62e7d0bc5d0e9739a1ba951f530598abefad8b4ed0d7b2', 'Exact old wrapper required')
    for ref in oldm['source_files']:
        need(bound(ref['path']) == ref, 'Unchanged application source differs')
    need(len(oldm['source_files']) == 48, 'Preserve all 48 application sources')
    return refs, vals, oldm

def check_old_runtime():
    cpref, cp = pinned(OLDP/'supervisor_state/CHECKPOINT.json', '2cbe414beabd0229adb195ce18a594826b361ba6aae5da3febf4879175d0785c')
    cr, closed = pinned(OLDP/'supervisor_state/SUPERVISOR_CLOSURE_f2216373d63747c7a8d4825629d3d568.json', '749c47255f5d19a5a5dfb7b7f484c848bfd20a45244afa4473dad84b1ffba251')
    lockref = bound(OLDP/'supervisor_state/CLOSED_LOCK_f2216373d63747c7a8d4825629d3d568.json')
    lock = verify(lockref)
    need(cp['status'] == 'REVIEW_FAILURE' and cp['completed'] == {} and cp['queue_sha256'] == '8b5287bf92f2acb2cd20fdda797366027fb80817f901b680c22567f6cf9cbb6c', 'Preserve failed zero-credit queue')
    need(closed['result']['action'] == 'REVIEW_FAILURE' and closed['result']['done'] == 0 and closed['result']['total'] == 12, 'Old failure population differs')
    need(closed['owner_lock'] == 'RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT' and closed['keep_awake']['restored'] is True and closed['payload_census_closure']['closed'] is True and closed['hardware_restoration_unresolved'] is False, 'Old ownership not closed')
    need(lock['pid'] == 623740 and abs(lock['creation_time'] - 1789421849.744099) < .02 and cp['active']['pid'] == 641192 and abs(cp['active']['creation_time'] - 1789421879.3122275) < .02, 'Original process identities differ')
    need(not (OLDP/'supervisor_state/SUPERVISOR_LOCK.json').exists(), 'Old lock remains')
    instances = [{k: x[k] for k in ('pid', 'creation_time')} for x in (lock, cp['active'])]
    snapshot, current = b.runtime_snapshot()
    allocation = b.allocation_decision(snapshot, current, instances)
    need(dt.datetime.now(dt.timezone.utc) < DEADLINE, 'Original closeout deadline reached')
    free = {d: shutil.disk_usage(d).free for d in ('C:/', 'G:/')}
    need(free['C:/'] >= 50*2**30 and free['G:/'] >= 75*2**30, 'Disk floors')
    return dict(status='ROOT_C12_V3_FAILED_RUNTIME_CLOSED_ZERO_ACCEPTED', accepted=0, planned=12,
                original_failure_preserved=True, checkpoint=cpref, supervisor_closure=cr, closed_lock=lockref,
                snapshot=snapshot, allocation=allocation, free_bytes=free, utc=dt.datetime.now(dt.timezone.utc).isoformat())

def construct(refs, vals, oldm, newm, mref, closure):
    extras = list(refs.values()) + [closure, bound(__file__), bound(Path(__file__).with_name('README_S6D_C12_N6H_RESUME_V1.md')), bound(BASE)]
    oldap = verify(vals['old_preparation']['approval_proposal'])
    q, ap = b.transform(vals['old_queue'], oldap, oldm, newm, mref, vals['new_freeze']['runner'], [], extras)
    q['status'] = 'PROPOSED_N6H_C12_FRESH_EXECUTION'
    return q, ap

def prepare():
    need(not Q.exists() and not P.exists(), 'Fresh metadata and runtime roots required')
    refs, vals, oldm = inputs()
    runtime = check_old_runtime()
    newm = copy.deepcopy(oldm)
    newm['runner_helper'] = vals['new_freeze']['runner']
    for job in newm['jobs']:
        job['output'] = str(G/'application/beam_C_collection_closure_wire_v1'/job['job_id'])
        need(not Path(job['output']).exists(), 'Fresh actual output required')
    Q.mkdir(parents=True)
    closure = save(Q/'PRIOR_FAILED_RUNTIME_CLOSURE.json', runtime)
    mref = save(Q/'MANIFEST.json', newm)
    q, ap = construct(refs, vals, oldm, newm, mref, closure)
    runnerref = vals['old_preparation']['runner']
    need(bound(runnerref['path']) == runnerref, 'V4 supervisor changed')
    runner = load(runnerref['path'], 'C12_N6h_queue_validator')
    queues = {}
    for name, jobs in (('pilot', q['jobs'][:1]), ('rest', q['jobs'][1:])):
        sq = copy.deepcopy(q); sq['jobs'] = jobs
        sap = copy.deepcopy(ap); sap['proposed_job_sha256'] = [digest(j) for j in jobs]
        sap['authorization_ref'] = str(Q/(name+'_ADMISSION.json'))
        sap['status'] = 'UNAPPROVED_N6H_' + name.upper()
        qr = save(Q/(name+'_QUEUE.json'), sq); sap['queue_sha256'] = qr['sha256']
        ar = save(Q/(name+'_APPROVAL_PROPOSAL.json'), sap)
        testap = copy.deepcopy(sap); testap['approved_job_sha256'] = sap['proposed_job_sha256']
        runner.validate_queue(sq, testap, qr['sha256'])
        queues[name] = dict(queue=qr, approval_proposal=ar, job_count=len(jobs), state_dir=str(P/(name+'_state')))
    result = dict(status='PREPARED_N6H_PILOT1_REST11_NOT_LAUNCHED', owner_thread_id=THREAD, run_id='20260913T195357Z',
                  inputs=refs, failed_runtime_closure=closure, manifest=mref, runner=runnerref, phases=queues,
                  total_jobs=12, total_frames=sum(next(iter(j['stream_proofs'].values()))['frames'] for j in newm['jobs']),
                  source=bound(__file__), readme=bound(Path(__file__).with_name('README_S6D_C12_N6H_RESUME_V1.md')),
                  physical_supervisor_overlap=False, accepted_old_jobs=0)
    receipt = save(Q/'PREPARATION.json', result)
    print(json.dumps(dict(preparation=receipt, phases=queues)))

def run_phase(phase, review_path, review_sha):
    refs, vals, oldm = inputs()
    prepref = bound(Q/'PREPARATION.json'); prep = verify(prepref)
    need(prep['inputs'] == refs and prep['source'] == bound(__file__) and bound(prep['readme']['path']) == prep['readme'], 'Prepared source/provenance changed')
    reviewref, review = pinned(review_path, review_sha)
    need(review['status'] == 'ROOT_ACCEPTED_N6H_EXACT_PREPARED_QUEUES' and review['owner_thread_id'] == THREAD and review['preparation'] == prepref, 'Root exact queue acceptance required')
    need(review['phase'] == phase and review['physical_supervisor_overlap'] is False, 'Exact allocated phase required')
    if phase == 'rest':
        pc = read(P/'pilot_state/CHECKPOINT.json')
        pid = verify(prep['phases']['pilot']['queue'])['jobs'][0]['job_id']
        need(pid in pc['completed'] and len(pc['completed']) == 1, 'Pilot must complete before remaining eleven')
        need('pilot_acceptance' in review and verify(review['pilot_acceptance'])['status'] == 'ROOT_ACCEPTED_ACTUAL_N6H_PILOT', 'Actual root pilot acceptance required')
        need(not (P/'pilot_state/SUPERVISOR_LOCK.json').exists(), 'Pilot owner not closed')
    runtime = check_old_runtime()
    newm = verify(prep['manifest'])
    fullq, fullap = construct(refs, vals, oldm, newm, prep['manifest'], prep['failed_runtime_closure'])
    info = prep['phases'][phase]; q = verify(info['queue']); ap = verify(info['approval_proposal'])
    expected_jobs = fullq['jobs'][:1] if phase == 'pilot' else fullq['jobs'][1:]
    fullq['jobs'] = expected_jobs
    need(q == fullq and ap['proposed_job_sha256'] == [digest(j) for j in expected_jobs] and ap['approved_job_sha256'] == [], 'Exact rebuilt jobs changed')
    need(ap['queue_sha256'] == info['queue']['sha256'], 'Approval queue mismatch')
    need(not Path(info['state_dir']).exists() and not (Q/(phase+'_LAUNCH.json')).exists(), 'Fresh execution state required')
    by_id = {j['job_id']: j for j in newm['jobs']}
    for job in q['jobs']:
        need(not Path(by_id[job['job_id']]['output']).exists(), 'Fresh native output required')
        for key in ('heartbeat_path', 'completion_path', 'stop_request_path'):
            need(not Path(job[key]).exists(), 'Occupied protocol artifact')
        for artifact in job['expected_artifacts']:
            need(not Path(artifact['path']).exists(), 'Occupied completion artifact')
        for ref in job['source_bindings']:
            need(bound(ref['path']) == ref, 'Source guard changed')
    need(bound(prep['runner']['path']) == prep['runner'], 'Supervisor changed')
    runner = load(prep['runner']['path'], 'C12_N6h_actual_validator')
    ap['approved_job_sha256'] = ap['proposed_job_sha256']; ap['status'] = 'ROOT_APPROVED_N6H_' + phase.upper()
    runner.validate_queue(q, ap, info['queue']['sha256'])
    admission = save(Q/(phase+'_ADMISSION.json'), dict(status='ROOT_ADMITTED_N6H_' + phase.upper(), root_review=reviewref,
            preparation=prepref, queue=info['queue'], runtime_preflight=runtime, physical_supervisor_overlap=False, job_count=len(q['jobs'])))
    approval = save(Q/(phase+'_APPROVAL.json'), ap)
    argv = [sys.executable, '-B', prep['runner']['path'], '--queue', info['queue']['path'], '--approval', approval['path'],
            '--queue-sha256', info['queue']['sha256'], '--approval-sha256', approval['sha256'], '--state-dir', info['state_dir'], '--keep-awake']
    with (Q/(phase+'.stdout.log')).open('xb') as out, (Q/(phase+'.stderr.log')).open('xb') as err:
        child = subprocess.Popen(argv, cwd=SIM, stdin=subprocess.DEVNULL, stdout=out, stderr=err, shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
    import psutil
    launched = save(Q/(phase+'_LAUNCH.json'), dict(status='SUPERVISOR_LAUNCHED', utc=dt.datetime.now(dt.timezone.utc).isoformat(),
            pid=child.pid, creation_time=psutil.Process(child.pid).create_time(), argv=argv, cwd=str(SIM), admission=admission,
            queue=info['queue'], approval=approval, state_dir=info['state_dir'], physical_supervisor_overlap=False, accepted=0, planned=len(q['jobs'])))
    print(json.dumps(dict(launch=launched, pid=child.pid, phase=phase, planned=len(q['jobs']))))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--run-phase', choices=['pilot', 'rest'])
    parser.add_argument('--root-review', type=Path)
    parser.add_argument('--root-review-sha256')
    args = parser.parse_args()
    need(args.prepare != bool(args.run_phase), 'Choose prepare or reviewed run')
    if args.prepare:
        prepare()
    else:
        need(args.root_review and args.root_review_sha256, 'Exact root review required')
        run_phase(args.run_phase, args.root_review, args.root_review_sha256)
