"""Metadata-only independent bank audit and queue proposal; see matching README."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
SIM = Path(__file__).resolve().parents[1]
R = SIM / 'reports/S6D/20260913T195357Z'
G = Path('G:/Just_Peachy_S6D/20260913T195357Z')
RUNNER_SHA = 'fdffb4cae7c111302b90d4128d8b44049354cd225f241868f6d83a5a2fab15b4'
OWNER_SHA = 'be4a03f729a1165e1b7bca66c12e511d710bf7c7ed095d7d4716084e74583524'
BRIDGE_SHA = '2d1fa47c51e23633fd5bfde788d098312564dc0ec182c43bf4e02ac8de7979d9'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def bind(p):
    p = Path(p).resolve()
    if p.suffix.lower() in ('.wav', '.pcm24') or p.stat().st_size > 16 * 2**20:
        raise ValueError('This metadata review must not rehash audio or large payloads')
    data = p.read_bytes()
    return dict(path=str(p), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def verify(b):
    actual = bind(b['path'])
    require(actual['bytes'] == b['bytes'] and actual['sha256'] == b['sha256'], 'changed metadata/source ' + b['path'])
    return actual


def require(ok, message):
    if not ok:
        raise ValueError(message)


def save(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def same_binding(a, b):
    return Path(a['path']).resolve() == Path(b['path']).resolve() and all(a[k] == b[k] for k in ('bytes', 'sha256'))


def charge(rows):
    return sum((Fraction(str(a['duration_sec'])) + 4 + Fraction(16383, 48000) for a in rows), Fraction())


def audit():
    prep_path = R / 'physical_bank_preparation_v1/PREPARATION_RESULT.json'
    prep = read(prep_path)
    for k in ('grouped_authority', 'enrollment_continuous_adoption', 'helper'):
        verify(prep[k])
    grouped = read(prep['grouped_authority']['path'])
    for k in ('base_authority', 'enrollment_authority', 'continuous_authority'):
        verify(grouped[k])
    original = read(grouped['base_authority']['path'])
    enrollment = read(grouped['enrollment_authority']['path'])
    continuous = read(grouped['continuous_authority']['path'])
    adopt = read(prep['enrollment_continuous_adoption']['path'])
    for name, key in (('DEVICE_ENROLLMENT_INPUT_PLAN_V1.json', 'enrollment_authority'), ('CONTINUOUS_INPUT_PLAN_V1.json', 'continuous_authority')):
        require(same_binding(adopt['original_plans'][name], grouped[key]), 'adoption authority mismatch')
    e = {x['planned_pass_id']: x for x in enrollment['planned_passes']}
    c = {x['session_id']: x for x in continuous['sessions']}
    adopted = {x['planned_id']: x for x in adopt['entries']}
    require(len(e) == 60 and len(c) == 2 and len(adopted) == 62 and set(adopted) == set(e) | set(c), 'exact E/continuous adoption')
    for pid, source in {**e, **c}.items():
        require(adopted[pid]['frames'] == source['source_frames'] and adopted[pid]['duration_sec'] == source['source_seconds'], 'E/continuous extent')
        require(adopted[pid]['profile'] == source['profile'] == 'P_MAIN6', 'E/continuous profile')
    base_path = R / 'physical_preparation_review_v2/CAPTURE_PLAN_PROPOSAL.json'
    base = read(base_path)
    original_main = {x['case_id']: x for x in original['P_MAIN6']['cases']}
    for x in original['P_SCAN6']['cases']:
        require(same_binding(x['input_binding'], original_main[x['case_id']]['input_binding']), 'SCAN changed canonical source')
    proofs = {str(Path(x['binding']['path']).resolve()): x for x in prep['source_verification']}
    require(len(proofs) == len(prep['source_verification']) == 302, '302 distinct verification receipts')
    require(len(prep['groups']) == len(grouped['groups']) == 20, '20 groups')
    all_rows, plans, summary, consumed_proofs = [], [], [], set()
    for reported, authority in zip(prep['groups'], grouped['groups']):
        gid = authority['batch_id']
        require(reported['group_id'] == gid, 'group ordering')
        verify(reported['plan'])
        p = read(reported['plan']['path'])
        plans.append(p)
        for key in ('report_root', 'limits', 'baseline', 'output_level_policy', 'initialization_policy', 'audio_acceptance_policy', 'owner', 'supervisor_bridge', 'route_contract'):
            require(p[key] == base[key], 'inherited capture contract ' + key)
        require(p['safety'] is None and p['no_execution_authorization_created'] is True, 'preparation cannot authorize')
        require(Path(p['payload_root']).resolve() == (G / 'bank_captures_v1').resolve(), 'bank payload root')
        qa_before, qa_after = p['attempts'][0], p['attempts'][-1]
        for row, suffix in ((qa_before, 'PRE'), (qa_after, 'POST')):
            expected = copy.deepcopy(base['attempts'][0])
            expected.update(attempt_id=f'QA_{gid}_{suffix}', stream_identity_qualification='OWN_PASS_EXACT_MIC_QA')
            require(row == expected, 'QA exact source/profile/timing/role')
            require(same_binding(row['source_audio'], grouped['QA_input']['audio']), 'QA authority source')
        expected_rows = []
        if 'source_case_ids' in authority:
            for role, ids in (('canonical', authority['source_case_ids']), ('repeat', authority.get('matched_repeat_cases', []))):
                for cid in ids:
                    x = original_main[cid]
                    aid = authority['profile'] + '_' + cid + ('_REPEAT' if role == 'repeat' else '')
                    expected_rows.append((aid, cid, role, x['input_binding'], x['duration_s']))
            require(len(authority['canonical_source_bindings']) == len(authority['source_case_ids']), 'group source binding coverage')
            for cid, bound in zip(authority['source_case_ids'], authority['canonical_source_bindings']):
                require(bound['case_id'] == cid and same_binding(bound['source_audio'], original_main[cid]['input_binding']), 'group source binding exact order')
        else:
            ids = authority.get('enrollment_pass_ids', [authority.get('continuous_session_id')])
            for pid in ids:
                x = adopted[pid]
                expected_rows.append((pid, pid, 'enrollment' if pid in e else 'continuous', x['source_audio'], x['duration_sec']))
        body = p['attempts'][1:-1]
        require(len(body) == len(expected_rows), 'body count')
        for row, (aid, cid, role, source, seconds) in zip(body, expected_rows):
            require((row['attempt_id'], row['case_id'], row['role'], row['profile'], row['duration_sec']) == (aid, cid, role, authority['profile'], seconds), 'body ID/order/role/profile/duration')
            require(same_binding(row['source_audio'], source), 'body canonical/adopted exact source')
            proof = proofs[str(Path(source['path']).resolve())]
            consumed_proofs.add(str(Path(source['path']).resolve()))
            require(same_binding(proof['binding'], source) and proof['frames'] == round(seconds * 16000), 'root source verification receipt binding/frames')
            require(math.isfinite(proof['peak_abs']) and 0 <= proof['peak_abs'] < 1 and isinstance(proof['nonzero'], bool), 'root peak/nonzero evidence')
            require(row['payload_expectation'] == ('nonzero' if proof['nonzero'] else 'silence'), 'nonzero expectation')
            require(row['required_nonzero_streams'] == (['auto_asr_raw', 'auto_pp_raw'] if proof['nonzero'] else []), 'required taps')
            require(row['reset_before'] is True and row['telemetry_rates'] == base['attempts'][1]['telemetry_rates'], 'reset/telemetry contract')
            require(row['stream_identity_qualification'] == 'PENDING_ROOT_ACTUAL_MAIN_SCAN_QUALIFICATION', 'no fabricated route qualification')
            if role == 'continuous':
                require(row['continuous_dsp_seconds'] == seconds == 900, 'uninterrupted 900-second physical session')
        stage_expected = [[qa_before['attempt_id']], [x['attempt_id'] for x in body], [qa_after['attempt_id']]]
        require([x['attempt_ids'] for x in reported['stages']] == stage_expected, 'three owner stages exact ordering')
        require([x['batch_id'] for x in reported['stages']] == [gid + '_pre_QA', gid, gid + '_post_QA'], 'owner stage identifiers')
        require(reported['attempts'] == len(p['attempts']) and abs(reported['charged_playback_seconds'] - float(charge(p['attempts']))) < 1e-8, 'group counts/charge')
        summary.append(dict(group_id=gid, attempt_count=len(p['attempts']), body_count=len(body), charged_seconds=float(charge(p['attempts'])), plan=reported['plan']))
        all_rows.extend(p['attempts'])
    require(consumed_proofs == set(proofs), 'verification rows exactly cover bank sources')
    require(len(all_rows) == len({x['attempt_id'] for x in all_rows}) == 394, '394 unique attempts')
    for profile in ('P_MAIN6', 'P_SCAN6'):
        require([x['case_id'] for x in all_rows if x['profile'] == profile and x['role'] == 'canonical'] == original[profile]['case_ids'], 'original canonical ordering ' + profile)
    require([x['case_id'] for x in all_rows if x['role'] == 'repeat'] == [x['case_id'] for x in original['matched_repeats']], 'four original matched repeats/order')
    require([x['case_id'] for x in all_rows if x['role'] == 'enrollment'] == list(e), '60 original E order')
    require([x['case_id'] for x in all_rows if x['role'] == 'continuous'] == list(c), 'two original physical continuous order')
    require(sum(x['profile'] == 'P_INPUT_QA6' for x in all_rows) == 40, '40 QA passes')
    bank_charge, full_charge = charge(all_rows), charge(all_rows) + charge(base['attempts'])
    require(len(base['attempts']) == 33 and full_charge == Fraction('19670.0340625'), '427 attempts / exact 19670.0340625s forecast')
    require(abs(prep['bank_charged_seconds'] - float(bank_charge)) < 1e-7 and abs(prep['full_forecast_charged_seconds'] - float(full_charge)) < 1e-7, 'reported aggregate charge')
    for k, expected in dict(main_unique=240, scan_unique=48, additional_repeats=4, E_passes=60, continuous_passes=2, QA_passes=40, bank_attempts=394, full_forecast_attempts=427, hardware_calls=0, models=0, new_RIRs=0, execution_authorized=False, unchanged_audio=True).items():
        require(prep[k] == expected, 'reported scope ' + k)
    return dict(status='PASS_METADATA_AND_SOURCE_REVIEW', utc=datetime.now(timezone.utc).isoformat(), preparation=bind(prep_path),
                preparation_helper=verify(prep['helper']), preparation_readme=bind(SIM / 'scripts/README_S6D_BANK_CAPTURE_PREPARE_V1.md'),
                grouped_authority=verify(prep['grouped_authority']), authorities={k: verify(grouped[k]) for k in ('base_authority', 'enrollment_authority', 'continuous_authority')},
                adoption=verify(prep['enrollment_continuous_adoption']), qualification_plan=bind(base_path), groups=summary,
                counts=dict(MAIN=240, SCAN=48, repeats=4, enrollment_E=60, physical_continuous_900s=2, QA=40, bank=394, qualification=33, full_forecast=427),
                bank_charged_seconds=float(bank_charge), full_forecast_charged_seconds=float(full_charge), unique_verified_input_bindings=302,
                audio_bytes_rehashed=0, inherited_audio_evidence='Root builder verified hashes, whole headers, finite samples and peak <1 for these exact 302 bindings; this independent pass validates metadata coverage only.',
                limitations=['Actual ledger failures/retries remain charged; 427 is the original forecast, not remaining allowance.', 'No actual route, tail, gain or beam efficacy admission is inferred.', 'E/Q/C restrictions remain those of the original exact source authorities; no new material is selected.'],
                reviewed_source=bind(__file__)), prep, plans


def prepare(out):
    out = Path(out).resolve()
    require(not out.exists() and out.is_relative_to(R / 'runner'), 'fresh runner metadata output required')
    review, prep, plans = audit()
    current = R / 'runner/qualification_stage_1_queue_v2'
    template = read(current / 'QUEUE.json')
    auth_source = read(current / 'CAPTURE_AUTHORIZATION.json')
    runner = verify(dict(path=str(R / 'runner/source_epoch_census_v4/s6d_runner_v1.py'), bytes=48597, sha256=RUNNER_SHA))
    sources = [verify(x) for x in auth_source['source_bindings']]
    owner = verify(plans[0]['owner']); bridge = verify(plans[0]['supervisor_bridge'])
    require(owner['sha256'] == OWNER_SHA and bridge['sha256'] == BRIDGE_SHA, 'accepted owner/bridge only')
    safety = verify(auth_source['safety'])
    source_review = verify(auth_source['source_review']); runner_review = verify(auth_source['runner_review'])
    queue = {k: copy.deepcopy(v) for k, v in template.items() if k != 'jobs'}
    queue.update(jobs=[], runner_sha256=RUNNER_SHA)
    group_rows = []
    for index, (group, old_plan) in enumerate(zip(prep['groups'], plans)):
        gid = group['group_id']; directory = out / 'groups' / gid
        plan = copy.deepcopy(old_plan)
        plan.update(schema='s6d-capture-plan.v1', status='PROPOSED_BANK_GROUP_NOT_AUTHORIZED', safety=safety,
                    physical_qualification_review=None, owner_V4_source_review=source_review,
                    adoption_required='Root must bind accepted actual MAIN/SCAN route, tail/delay, observer and QA/restoration evidence before admission.')
        save(directory / 'CAPTURE_PLAN_PROPOSAL.json', plan); pb = bind(directory / 'CAPTURE_PLAN_PROPOSAL.json')
        auth = dict(schema='s6d-root-bank-admission-proposal.v1', root_review_passed=False, plan_sha256=pb['sha256'],
                    source_bindings=sources, group_index=index, group_id=gid, attempt_ids=[a['attempt_id'] for a in plan['attempts']],
                    charged_playback_seconds=float(charge(plan['attempts'])), physical_qualification_review=None, safety=safety,
                    runner_review=runner_review, source_review=source_review, ledger_before_admission=None,
                    root_owner_thread_id=queue['owner_thread_id'], scope='Unapproved data-only proposal; no root review or execution authorization created')
        save(directory / 'CAPTURE_AUTHORIZATION_PROPOSAL.json', auth); ab = bind(directory / 'CAPTURE_AUTHORIZATION_PROPOSAL.json')
        for stage_index, stage in enumerate(group['stages']):
            job_id = 'bank_v1_' + stage['batch_id']
            protocol = R / 'physical_supervisor' / job_id
            attempts = [a for a in plan['attempts'] if a['attempt_id'] in stage['attempt_ids']]
            job = copy.deepcopy(template['jobs'][0])
            job.update(job_id=job_id, timeout_s=math.ceil(float(charge(attempts)) + 120 * len(attempts) + 300),
                       bank_group_index=index, bank_group_id=gid, bank_stage=['pre_QA', 'body', 'post_QA'][stage_index],
                       predecessor_job_id=queue['jobs'][-1]['job_id'] if queue['jobs'] else None)
            for key, name in [('heartbeat_path', 'HEARTBEAT.json'), ('completion_path', 'COMPLETE.json'), ('stop_request_path', 'STOP_REQUEST.json'), ('restoration_path', 'RESTORATION.json')]:
                job[key] = str(protocol / name)
            completion_fields = copy.deepcopy(template['jobs'][0]['expected_artifacts'][0]['expected_fields'])
            completion_fields.update({'semantic_checks.attempt_count': len(attempts), 'plan.sha256': pb['sha256'], 'authorization.sha256': ab['sha256'],
                                      'owner.sha256': OWNER_SHA, 'wrapper.sha256': BRIDGE_SHA,
                                      'semantic_checks.restoration.checks.owner_same_process': True,
                                      'semantic_checks.restoration.checks.exact_configuration_match': True,
                                      'semantic_checks.restoration.checks.telemetry_closed': True,
                                      'semantic_checks.restoration.checks.hardware_lease_released': True,
                                      'semantic_checks.restoration.checks.audio_closed_or_no_playback': True})
            job['expected_artifacts'] = [dict(path=job['completion_path'], format='json', min_bytes=1, expected_fields=completion_fields),
                                         dict(path=job['restoration_path'], format='json', min_bytes=1, expected_fields=dict(status='RESTORED', verified=True))]
            for a in attempts:
                folder = Path(plan['payload_root']) / 'beam_bank' / a['case_id'] / a['profile'] / a['attempt_id']
                fields = {'status': 'PASS', 'transport_integrity_status': 'PASS', 'attempt.attempt_id': a['attempt_id'], 'attempt.case_id': a['case_id'],
                          'attempt.profile': a['profile'], 'attempt.role': a['role'], 'attempt.source_audio.sha256': a['source_audio']['sha256'],
                          'source_input.source.sha256': a['source_audio']['sha256'], 'source_input.source_gain': 1.0,
                          'source_input.applied_RIR_origin_additions': 0, 'source_input.timing.source_frames': round(a['duration_sec'] * 16000),
                          'framing.marker_error_count': 0, 'framing.internal_repair_performed': False, 'telemetry.status': 'PASS',
                          'level_screen.gain_changed': False, 'level_screen.original_waveforms_retained': True}
                if stage_index != 1:
                    fields.update({'input_qa.status': 'PASS', 'input_qa.payload_mismatches': 0,
                                   'input_qa.per_mic_mismatches': [0, 0, 0, 0], 'input_qa.all_nonzero_source_payload_captured': True,
                                   'input_qa.exact_mic_recovery_claim': True, 'physical_stream_identity_qualification': 'OWN_PASS_EXACT_MIC_QA'})
                job['expected_artifacts'].append(dict(path=str(folder / 'case_result.json'), format='json', min_bytes=1, expected_fields=fields))
                job['expected_artifacts'].append(dict(path=str(folder / 'capture_metadata.json'), format='json', min_bytes=1,
                    expected_fields={'source_payload_frames_submitted': round(a['duration_sec'] * 16000),
                                     'carrier_frames_submitted': round((a['duration_sec'] + 4) * 48000), 'callback_errors': [],
                                     'writer_closed': True, 'audio_handles_closed': True}))
            job['argv'] = [template['jobs'][0]['argv'][0], bridge['path'], '--owner', owner['path'], '--owner-sha256', OWNER_SHA,
                           '--plan', pb['path'], '--plan-sha256', pb['sha256'], '--authorization', ab['path'], '--authorization-sha256', ab['sha256'],
                           '--batch', job_id, '--attempt-ids', *stage['attempt_ids']]
            job['source_bindings'] = list({b['path']: b for b in [*sources, runner, bridge, pb, ab, safety]}.values())
            require(not protocol.exists() and not (R / 'hardware_batches' / job_id).exists(), 'fresh owner/protocol output')
            for a in attempts:
                require(not (Path(plan['payload_root']) / 'beam_bank' / a['case_id'] / a['profile'] / a['attempt_id']).exists(), 'fresh capture destination')
            queue['jobs'].append(job)
        group_rows.append(dict(group_id=gid, plan=pb, authorization_proposal=ab, attempt_count=len(plan['attempts']), child_count=3))
    require(len(queue['jobs']) == 60, '60 sequential owner jobs')
    save(out / 'INDEPENDENT_PREPARATION_REVIEW.json', review)
    save(out / 'QUEUE_PROPOSAL.json', queue); qb = bind(out / 'QUEUE_PROPOSAL.json')
    spec = importlib.util.spec_from_file_location('s6d_bank_review_runner', runner['path'])
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    executable = bind(queue['jobs'][0]['argv'][0])
    approval = dict(schema='s6d_queue_approval_v1', run_id=queue['run_id'], queue_sha256=qb['sha256'],
                    authorization_ref='PENDING_ROOT_ACTUAL_QUALIFICATION_AND_WHOLE_BANK_ADMISSION', approved_job_sha256=[],
                    proposed_job_sha256=[module.digest(j) for j in queue['jobs']], executable_bindings=[executable],
                    allowed_working_directories=[str(SIM)], allowed_output_roots=[str(R), str(G), str(SIM / 'listening/S45_all240_v1')])
    save(out / 'APPROVAL_PROPOSAL.json', approval)
    probe = copy.deepcopy(approval); probe['approved_job_sha256'] = probe['proposed_job_sha256']
    require(module.validate_queue(queue, probe, qb['sha256']) is True, 'pure queue structure validation')
    rejected = False
    try:
        module.validate_queue(queue, approval, qb['sha256'])
    except ValueError as exc:
        rejected = 'unapproved job' in str(exc)
    require(rejected, 'empty proposal must not admit jobs')
    result = dict(status='DATA_ONLY_REVIEWED_PROPOSAL_NO_ADMISSION', utc=datetime.now(timezone.utc).isoformat(), queue=qb,
                  approval_proposal=bind(out / 'APPROVAL_PROPOSAL.json'), review=bind(out / 'INDEPENDENT_PREPARATION_REVIEW.json'),
                  helper=bind(__file__), readme=bind(Path(__file__).with_name('README_S6D_BANK_QUEUE_PREPARE_V1.md')),
                  runner=runner, owner=owner, bridge=bridge, source_review=source_review, runner_review=runner_review,
                  groups=group_rows, stage_count=60, attempt_count=394, per_group_attempt_counts=[g['attempt_count'] for g in group_rows],
                  pure_structure_probe='PASS_WITH_TEMPORARY_IN_MEMORY_HASH_ALLOWLIST_ONLY', real_empty_proposal_rejected=True,
                  execution_authorized=False, hardware_calls=0, model_calls=0, processes_launched=0,
                  stage_progression='V4 serial queue advances only after child exit, protocol/artifact predicates and exact owner restoration. Pre-QA failure prevents body; post-QA failure prevents next group. No manual review per30 after root admits whole bank.',
                  limitations=['predecessor_job_id is descriptive; actual order is the immutable queue.jobs list enforced by V4.',
                               'Root must adopt all20 plans/authorizations and rebind literal queue/job hashes to accepted actual qualification evidence before launch.',
                               'LIMITED rail/payload levels remain recorded; transport PASS does not become unqualified audio/route/tail/beam efficacy PASS.',
                               'Each child validates its own group plan only; owner/bridge may repeat those bounded input checks, never all394 inputs per child.',
                               'Actual failed/retried attempts remain in the shared ledger; forecast427 is not an authorization to ignore them.'])
    save(out / 'QUEUE_PREPARATION_RECEIPT.json', result)
    print(json.dumps(dict(status=result['status'], output=str(out), receipt=bind(out / 'QUEUE_PREPARATION_RECEIPT.json'), review=result['review'], counts=review['counts'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=R / 'runner/bank_queue_preparation_v1')
    args = p.parse_args()
    prepare(args.output)
