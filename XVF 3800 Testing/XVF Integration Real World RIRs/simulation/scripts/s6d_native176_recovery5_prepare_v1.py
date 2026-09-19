"""Prepare five native recovery jobs without execution; see accompanying README."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

SIM = Path(__file__).resolve().parents[1]
R = SIM / 'reports/S6D/20260913T195357Z'
G = Path('G:/Just_Peachy_S6D/20260913T195357Z')
OLD = R / 'runner/native_execution_queue_preparation_v1/native176'
STATE = G / 'runner/native_execution_queue_preparation_v1/native176_state'
NONCE = '0c567cc058934a52b4f97fbc89269900'
CHILD = 'acbc5cbb92d24102a6cf255d428275a6'
REMAINING = ['C105_S45_08_07_O1_delivery_repair_r1',
             'C105_S45_08_07_O0_original_r2', 'C105_S45_08_07_O0_delivery_repair_r2',
             'C105_S45_08_07_O1_original_r2', 'C105_S45_08_07_O1_delivery_repair_r2']

def need(ok, message):
    if not ok:
        raise ValueError(message)

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def bind(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

def verify(bound):
    need(bind(bound['path']) == bound, 'Changed source/metadata: ' + bound['path'])
    return read(bound['path']) if Path(bound['path']).suffix.lower() == '.json' else None

def pin(path, sha):
    result = bind(path)
    need(result['sha256'] == sha, 'Changed exact authority: ' + str(path))
    return result

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def write(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')
    return bind(path)

def unique(bindings):
    result = {}
    for bound in bindings:
        key = str(Path(bound['path']).resolve()).casefold()
        if key in result:
            need(result[key]['sha256'] == bound['sha256'] and result[key]['bytes'] == bound['bytes'], 'Conflicting exact source path')
        else:
            result[key] = bound
    return list(result.values())

def replace_strings(value, replacements):
    if isinstance(value, dict):
        return {key: replace_strings(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_strings(item, replacements) for item in value]
    if isinstance(value, str):
        for old, new in replacements.items():
            if value == old or value.startswith(old + '\\') or value.startswith(old + '/'):
                return new + value[len(old):]
    return value

def scientific(job):
    return {key: value for key, value in job.items() if key != 'output'}

def prepare(output):
    output = output.resolve()
    need(output.parent == R / 'runner' and not output.exists(), 'Fresh direct report/runner output required')
    payload = G / 'application/native176_recovery5_v1'
    protocol = G / 'runner/native176_recovery5_v1'
    need(not payload.exists() and not protocol.exists(), 'Fresh recovery native/protocol roots required')
    qb = pin(OLD / 'QUEUE.json', '7cb1efcf8c80093f189acf8803d1e22f55d2ec74c5f5c3ffe04c06ff3fdeb4a2')
    ab = pin(OLD / 'APPROVAL.json', '0a61a716a271e93f16423c138e0ee4e5ecb0683d793a1e4a6b0990bc8eae5ed1')
    cb = pin(STATE / 'CHECKPOINT.json', '4ebc40c4fecee1b8d554b00a4445e486f20cc8fa2e6a5595f5733db9bfcbf863')
    closure_b = bind(STATE / ('SUPERVISOR_CLOSURE_' + NONCE + '.json'))
    lock_b = pin(STATE / ('CLOSED_LOCK_' + NONCE + '.json'), '8ea8001cd40ea688da4726c10de069f3fdba228bece9756899b045b784d2cdca')
    launch_b = pin(STATE / ('LAUNCH_' + CHILD + '.json'), '88862bacfeb567d2d22bc956d542c5450c9dffe46de00276d8ab15d2af464f67')
    q, a, checkpoint, closure, closed_lock, launch = [read(x['path']) for x in [qb, ab, cb, closure_b, lock_b, launch_b]]
    need(len(q['jobs']) == 176 and len(checkpoint['completed']) == 171, 'Exact original176/closed171 required')
    need(checkpoint['queue_sha256'] == qb['sha256'] and a['queue_sha256'] == qb['sha256'], 'Original authority differs')
    need([j['job_id'] for j in q['jobs'] if j['job_id'] not in checkpoint['completed']] == REMAINING, 'Exact final five/order required')
    need(set(checkpoint['completed']) == {j['job_id'] for j in q['jobs'][:171]}, 'Original171 selection differs')
    need(all(v['exit_code'] == 0 and v['status'] == 'DECLARED_ARTIFACTS_VERIFIED' for v in checkpoint['completed'].values()), 'Old selection lacks declared complete evidence')
    active = checkpoint['active']
    need(active['job_id'] == REMAINING[0] and active['child_run_id'] == CHILD and active['pid'] == 635976 and active['creation_time'] == 1789410945.8531685, 'Stopped exact identity differs')
    need(all(active[k] == launch[k] for k in ['run_id', 'job_id', 'child_run_id', 'pid', 'creation_time']), 'Stopped launch provenance differs')
    need(closure['result']['done'] == 171 and closure['result']['total'] == 176 and closure['result']['action'] == 'REPORT_BLOCKED', 'Original blocked closure differs')
    need(closure['result']['reason'].endswith('OFFLINE_CHILD_EXITED_AFTER_STOP') and closure['owner_lock'] == 'RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT', 'Owned stop/lock closure required')
    need(closure['keep_awake']['restored'] is True and closure['payload_census_closure']['closed'] is True and closure['hardware_restoration_unresolved'] is False, 'Original supervisor resources unresolved')
    need(closed_lock['owner_nonce'] == NONCE, 'Closed lock nonce differs')
    need(q['runner_sha256'] == 'fdffb4cae7c111302b90d4128d8b44049354cd225f241868f6d83a5a2fab15b4' and q['protocol_wrapper']['sha256'] == '874d55b0449f5cb53d9b6bf476d7a8cf97d1022e1cffd5ef844f71af5f8c5084', 'Unchanged V4/874d required')
    need(q['payload_policy']['max_new_payload_bytes'] == 40 * 1024 ** 3, 'Original40GiB required')
    old_jobs = {j['job_id']: j for j in q['jobs']}
    manifest_bounds, manifests, native = {}, {}, {}
    for jid in REMAINING:
        argv = old_jobs[jid]['argv']
        path = argv[argv.index('--manifest') + 1]
        mb = pin(path, argv[argv.index('--manifest-sha256') + 1])
        manifest_bounds[path] = mb
        manifests[path] = read(path)
        rows = [j for j in manifests[path]['jobs'] if j['job_id'] == jid]
        need(len(rows) == 1, 'Native scientific ID ambiguous')
        native[jid] = rows[0]
    for source in unique([b for jid in REMAINING for b in old_jobs[jid]['source_bindings']]):
        verify(source)
    for executable in a['executable_bindings']:
        verify(executable)
    stopped_output = Path(native[REMAINING[0]]['output'])
    stopped_protocol = Path(old_jobs[REMAINING[0]]['completion_path']).parent
    stopped_result_b = pin(stopped_output / 'RESULT.json', '2d9cfb3f375b9a7d6af15a0d2faa671633d780c38dbdaee508f59e392f856b2d')
    stop_b = pin(stopped_protocol / 'STOP_REQUEST.json', 'b9b88454f7903b9b5317d656fe63dcf582205ac6f2dc3cdbaa137bb825be4840')
    need(not (stopped_output / 'FULL_SOURCE_AUDIT.json').exists() and not (stopped_protocol / 'COMPLETION.json').exists(), 'Stopped attempt disposition changed; new review required')
    original = dict(queue=qb, approval=ab, checkpoint=cb, supervisor_closure=closure_b, closed_lock=lock_b, stopped_launch=launch_b, stopped_STOP=stop_b, stopped_inner_RESULT=stopped_result_b)
    output.mkdir()
    (output / 'manifests').mkdir()
    (output / 'source_epoch').mkdir()
    helper_files = []
    for path in [Path(__file__), Path(__file__).with_name('README_S6D_NATIVE176_RECOVERY5_PREPARE_V1.md')]:
        target = output / 'source_epoch' / path.name
        shutil.copyfile(path, target)
        helper_files.append(bind(target))
    new_manifest_bounds, new_native = {}, {}
    for oldpath, m in manifests.items():
        new = deepcopy(m)
        selected = [jid for jid in REMAINING if oldpath == old_jobs[jid]['argv'][old_jobs[jid]['argv'].index('--manifest') + 1]]
        new['jobs'] = []
        for jid in selected:
            job = deepcopy(native[jid])
            job['output'] = str(payload / (jid + '_recover1'))
            need(scientific(job) == scientific(native[jid]), 'Scientific job changed')
            new_native[jid] = job
            new['jobs'].append(job)
        new.update(status='PROPOSED_RECOVERY5_ROOT_ADOPTION_REQUIRED', approved=False, approval=None,
            job_count=len(selected), source_audio_total_sec=sum(j['audio_duration_sec'] for j in new['jobs']),
            payload_root=str(payload), created_utc=datetime.now(timezone.utc).isoformat(),
            purpose='Exact remaining native176 declarations after census stop; fresh execution attempts only, no scientific change.',
            prior_recovery_manifest=manifest_bounds[oldpath], recovery_original_authorities=original,
            model_jobs_started=0, hardware_started=False)
        new_manifest_bounds[oldpath] = write(output / 'manifests' / Path(oldpath).name, new)
    scope_rows = [dict(scientific_job_id=jid, execution_job_id=jid + '_recover1',
        native_job_id=jid, original_native_job_sha256=digest(native[jid]),
        scientific_fields_sha256=digest(scientific(native[jid])), output=new_native[jid]['output'],
        original_manifest=manifest_bounds[old_jobs[jid]['argv'][old_jobs[jid]['argv'].index('--manifest')+1]],
        recovery_manifest=new_manifest_bounds[old_jobs[jid]['argv'][old_jobs[jid]['argv'].index('--manifest')+1]]) for jid in REMAINING]
    scope = dict(schema='s6d-native176-recovery5-scope.v1', status='PROPOSED_NOT_ADMITTED', original=original,
        original_order=[j['job_id'] for j in q['jobs']], retained_original_ids=[j['job_id'] for j in q['jobs'][:171]],
        recovery=scope_rows, helper_source=helper_files, actual_old171_revalidated_here=False,
        required_live_gate='Root verifies exact old supervisor/launcher/worker PID+creation absence before admission; metadata-only helper does not query processes.',
        allocation='One serial native worker under original settings; no concurrent physical supervisor/NN/timing work for initial five; record interruption/recovery conditions.',
        old_attempt_retention='Original blocked176 checkpoint,171 completions and stopped C105 inner COMPLETE lacking audit/protocol completion are preserved; stopped attempt receives no scientific credit.')
    scope_b = write(output / 'RECOVERY_SCOPE.json', scope)
    newq = deepcopy(q)
    newq.update(group='native176_recovery5_v1', production_status='PROPOSED_ROOT_RECOVERY_ADOPTION_REQUIRED',
        created_utc=datetime.now(timezone.utc).isoformat(), recovery_scope=scope_b, jobs=[])
    for jid in REMAINING:
        oldj = old_jobs[jid]
        oldpath = oldj['argv'][oldj['argv'].index('--manifest') + 1]
        mb, previous_mb = new_manifest_bounds[oldpath], manifest_bounds[oldpath]
        old_protocol = str(Path(oldj['completion_path']).parent)
        new_protocol = str(protocol / (jid + '_recover1'))
        j = replace_strings(deepcopy(oldj), {str(Path(native[jid]['output'])): new_native[jid]['output'], old_protocol: new_protocol})
        j['job_id'] = jid + '_recover1'
        j['argv'][j['argv'].index('--manifest') + 1] = mb['path']
        j['argv'][j['argv'].index('--manifest-sha256') + 1] = mb['sha256']
        for item in j['expected_artifacts']:
            if 'manifest.sha256' in item['expected_fields']:
                item['expected_fields']['manifest.sha256'] = mb['sha256']
        j['source_bindings'] = unique([mb if b == previous_mb else b for b in oldj['source_bindings']] + [scope_b, *helper_files, previous_mb, *original.values()])
        need(j['argv'][-1] == jid, 'Native scientific ID changed')
        need(j['timeout_s'] == oldj['timeout_s'] and j['stall_after_s'] == oldj['stall_after_s'] and j['heartbeat_stale_s'] == oldj['heartbeat_stale_s'], 'Timing guard changed')
        need(all(b['bytes'] <= 16 * 1024**2 for b in j['source_bindings']) and sum(b['bytes'] for b in j['source_bindings']) <= 64 * 1024**2, 'Repeated source guards too large')
        newq['jobs'].append(j)
    newqb = write(output / 'QUEUE.json', newq)
    approval = deepcopy(a)
    approval.update(queue_sha256=newqb['sha256'], authorization_ref=str(output / 'ROOT_ADMISSION.json'),
        approved_job_sha256=[], proposed_job_sha256=[digest(j) for j in newq['jobs']], approval_state='UNAPPROVED_ROOT_RECOVERY_ADOPTION_REQUIRED')
    newab = write(output / 'APPROVAL_PROPOSAL.json', approval)
    allrows = []
    for ordinal, oldj in enumerate(q['jobs'], 1):
        jid = oldj['job_id']
        row = dict(ordinal=ordinal, scientific_job_id=jid, original_queue_job_sha256=digest(oldj))
        if jid in checkpoint['completed']:
            row.update(origin='original_completed', original_execution_job_id=jid,
                original_completion_path=oldj['completion_path'], saved_checkpoint_record=checkpoint['completed'][jid])
        else:
            selected = next(v for v in scope_rows if v['scientific_job_id'] == jid)
            qj = next(v for v in newq['jobs'] if v['job_id'] == selected['execution_job_id'])
            row.update(origin='recovery_required', **selected, recovery_queue_job_sha256=digest(qj),
                recovery_completion_path=qj['completion_path'], accepted_recovery_result=False)
        allrows.append(row)
    composite = dict(schema='s6d-native176-composite-execution.v1', status='PENDING_EXACT_FIVE_FINISH_AND_ROOT_COMPOSITE_ADMISSION',
        original=original, recovery_scope=scope_b, recovery_queue=newqb, recovery_approval_proposal=newab,
        future_approval_path=str(output/'APPROVAL.json'), future_root_admission_path=str(output/'ROOT_ADMISSION.json'),
        future_state_dir=str(protocol/'supervisor_state'), rows=allrows,
        expected=dict(original_declared=176, original_completed=171, recovery_required=5, recovery_FINISH_done=5, recovery_FINISH_total=5),
        source_queue_rules='Old171 select exact closed checkpoint records and validate each against original literal queue/identity/artifacts. New5 require actual approved recovery queue and immutable FINISH5 closure plus every exact current identity/full-source/protocol predicate. Join using original scientific ID and order, never output directory names.',
        stopped_original_attempt_credited=False, old176_FINISH_claimed=False, science_declaration_changed=False)
    composite_b = write(output/'COMPOSITE_MAP.json', composite)
    root_proposal_b = write(output/'ROOT_ADMISSION_PROPOSAL.json', dict(schema='s6d-native176-recovery5-root-proposal.v1',
        status='PROPOSED_NOT_AUTHORIZED',run_id=q['run_id'],owner_thread_id=q['owner_thread_id'],owner_session_id=q['owner_session_id'],
        queue=newqb,approval_proposal=newab,composite=composite_b,scope=scope_b,
        before_launch=['Independent literal metadata/source review','Exact old supervisor and stopped launcher/worker PID+creation absence; no unresolved ownership',
            'Fresh complete census below40GiB, C>=50/G>=75, unchanged deadline/reserve and original per-job limits',
            'No competing experiment/scanner allocation for initial five; one paced NN worker unchanged affinity12..15/pools1',
            'Root issues actual approval/admission, validates queue and explicitly launches once'],
        recovery_does_not_fix='V4 still fails closed if a future complete census ages beyond60s. No interval/freshness change and no automatic retry.',
        actual_authorization_created=False))
    receipt = dict(schema='s6d-native176-recovery5-preparation.v1',status='PREPARED_NOT_ADMITTED',
        source=helper_files,original=original,manifests=list(new_manifest_bounds.values()),scope=scope_b,queue=newqb,
        approval_proposal=newab,root_admission_proposal=root_proposal_b,composite=composite_b,
        source_frames=sum(j['expected_frames'] for j in new_native.values()),source_seconds=sum(j['audio_duration_sec'] for j in new_native.values()),
        original_completed=171,new_execution_attempts=5,original_stopped_attempts_preserved=1,
        unchanged_scientific_jobs=all(scientific(new_native[j])==scientific(native[j]) for j in REMAINING),
        runner_or_protocol_source_changed=False,full_source_census_staleness_seconds=60,
        actual_models=0,actual_hardware=0,actual_approvals=0,source_audio_or_journals_read=False,
        frozen_completion_claim='All171 retain only their saved declared-artifact verification; full strict composite revalidation remains the additive scorer-input builder and root responsibility.')
    return write(output/'PREPARATION_RESULT.json',receipt)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(parser.parse_args().output)))
