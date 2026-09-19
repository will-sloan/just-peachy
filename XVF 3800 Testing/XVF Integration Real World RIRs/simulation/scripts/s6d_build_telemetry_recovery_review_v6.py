"""Record root-reviewed B3 pre-QA recovery authority; see adjacent README."""
import argparse
import json
import os
from pathlib import Path
import s6d_closed_telemetry_restore_v6 as H


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--independent-review', type=Path, required=True)
    parser.add_argument('--independent-sha256', required=True)
    parser.add_argument('--source-freeze', type=Path, required=True)
    parser.add_argument('--source-freeze-sha256', required=True)
    args = parser.parse_args()
    r, s = H.R, H.SIM / 'scripts'
    out = r / 'capture_telemetry_recovery_v3/ROOT_SOURCE_REVIEW_V6.json'
    execution = r / 'runner/capture_owner_v11_source_v1/SOURCE_FREEZE.json'
    H.need(not out.exists() and not execution.exists(), 'Fresh immutable authority paths required')
    proposal = H.bind(args.source_freeze)
    H.need(proposal['sha256'] == args.source_freeze_sha256, 'Exact V6/V11 proposal required')
    H.need(Path(proposal['path']).resolve().is_relative_to(r), 'Campaign source freeze required')
    f = H.verify(proposal)
    independent = H.bind(args.independent_review)
    H.need(independent['sha256'] == args.independent_sha256, 'Exact independently reviewed hash required')
    independent_data = H.verify(independent)
    H.need(str(independent_data['status']).startswith('PASS') and not independent_data.get('findings') and not independent_data.get('blocking_findings'), 'Independent source review must pass')
    H.need(independent_data.get('source_freeze') == proposal, 'Independent review must bind this exact corrected source freeze')
    for pair in f['source_copies']:
        for b in pair.values():
            H.need(H.bind(b['path']) == b, 'Source or frozen copy changed')
    canonical = f['canonical_execution_sources']
    H.need(len(canonical) == 28 and len({Path(b['path']).name.casefold() for b in canonical}) == 28, 'Exact28 canonical dependencies required')
    for b in canonical + f['recovery_required_sources']:
        H.need(H.bind(b['path']) == b, 'Canonical or recovery dependency changed')
    for b in list(f['original_evidence'].values()) + list(f['telemetry_evidence'].values()):
        H.need(H.bind(b['path']) == b, 'Original or telemetry evidence changed')
    checks = H.verify(f['fixture_receipt'])
    H.need(checks['status'] == 'PASS' and checks['passed'] == checks['total'] == len(checks['tests']) and checks['passed'] >= 28 and all(t['status'] == 'PASS' for t in checks['tests']), 'All28 or more focused checks required')
    H.need(checks['source'] == H.bind(s / 's6d_closed_telemetry_restore_v6.py') and checks['owner_source'] == H.bind(s / 's6d_capture_owner_v11.py'), 'Fixtures must bind the exact selected helper and owner')
    snapshot = H.bind(out.parent / 'ROOT_PROCESS_SNAPSHOT.json')
    observation = H.verify(snapshot)
    H.need(observation.get('no_matching_task_control_processes') is True and observation.get('matching_processes') == [] and observation.get('query_errors') == [], 'Root current control snapshot must be complete')
    oldref = H.bind(r / 'capture_telemetry_recovery_v2/ROOT_SOURCE_REVIEW_V5.json')
    H.need(oldref['sha256'] == '5d025f36cb140b84ac72218bbd8e8a3ed4b3a0cebcb725d6ed532ea9d615f218', 'Preserve exact prior root source authority')
    old = H.verify(oldref)
    H.verify(old['output_confirmation'])
    owner = H.bind(s / 's6d_capture_owner_v11.py')
    bridge, policy = H.bind(s / 's6d_capture_supervisor_bridge_v2.py'), H.bind(s / 's6d_restoration_policy_v1.py')
    H.need(all(b in canonical for b in (owner, bridge, policy)), 'Canonical owner/bridge/policy required')
    combined = dict(schema='s6d-owner-execution-source-freeze.v1', status='ROOT_ACCEPTED_V11_RECORDED_QA_TERMINAL_SOURCE_ONLY',
        utc=H.utc(), source_proposal=proposal, independent_review=independent,
        sources=[dict(original=p['original'], frozen=p['copy']) for p in f['source_copies']],
        owner_execution_dependency_bindings=canonical, fixture_receipts=dict(recorded_QA=f['fixture_receipt'], inherited_V5=old['fixture_receipts']['recorded25']),
        owner=owner, bridge=bridge, policy=policy, actual_hardware_or_process_calls=0)
    # Preview final bytes without publishing accepted canonical authority yet.
    encoded = (json.dumps(combined, indent=2, allow_nan=False) + '\n').encode('utf-8')
    import hashlib
    ef = dict(path=str(execution.resolve()), bytes=len(encoded), sha256=hashlib.sha256(encoded).hexdigest())
    paths = [Path(b['path']) for b in canonical + f['recovery_required_sources']]
    paths += [Path(p['original']['path']) for p in f['source_copies']]
    paths += [Path(__file__), s / 'README_S6D_BUILD_TELEMETRY_RECOVERY_REVIEW_V6.md']
    sources = list({str(p.resolve()): H.bind(p) for p in paths}.values())
    review = dict(status=H.REVIEW_STATUS, run_id='20260913T195357Z', owner_thread_id=H.ROOT_THREAD,
        utc=H.utc(), original_batch='bank_v4_P_MAIN6_B3_pre_QA', recovery_kind=H.KIND,
        allow_fresh_exposed_restore=True, original_bindings=f['original_evidence'],
        source_bindings=sources, owner_execution_source_freeze=ef, source_freezes=[ef, proposal],
        independent_source_review=independent, fixture_receipts=combined['fixture_receipts'],
        root_telemetry_review=old['root_telemetry_review'], owner=owner, bridge=bridge, policy=policy,
        root_process_snapshot=snapshot, telemetry_bindings=f['telemetry_evidence'], expected_measurement_rows=614,
        output_confirmation=old['output_confirmation'], recovery_output_root=str(r / 'closed_telemetry_restore_v6'),
        historical_telemetry_pid_creation=dict(pid=602832, creation_time=1789415391.2722838),
        prior_root_source_review=oldref, actual_restoration_performed=False, new_queue_admitted=False,
        root_review_findings=[
            'Root read the complete V5-to-V6 and V10-to-V11 diffs and focused new-QA/supervisor identity checks; independent source review passed. All prior sources and failures remain immutable.',
            'The exact B3 pre-QA Python FAIL, recorded PID/parent/creation,614 native/received rows, lifecycle, cleanup and reader proof are joined. Historical process exit and stderr closure remain unproven; no exit time or race is inferred.',
            'All native work completes before the final C# frame; the saved record does not explain host shutdown delay. No telemetry timing, timeout or scientific capture behavior changes.',
            'Actual recovery requires fresh repeated complete process/TCP checks for all original owners including recorded telemetry PID, sole hardware lease, whole exact original or configured identity, original reapply/reset/readback, strict policy and released lease. Mixed/unknown states reject; no process termination or playback.',
            'New ownerV11 adds only the distinct recorded-terminal recovery verifier and its required sources. All previous recovery kinds remain, and canonical28 execution files are separate from nested historical producer evidence.',
            'This authority admits only the exact fresh restoration after its runtime gates. Actual restoration is not yet claimed. A separately reviewed remaining physical queue with fresh QA and preserved failures is a separate requirement; all original caps/floors/deadline remain.'
        ])
    # Exact file/native/configuration gates run first against an explicitly unapproved stage.
    staged = dict(review, status='PROPOSED_SOURCE_REVIEW_ONLY', allow_fresh_exposed_restore=False)
    stage_path = out.parent / 'PROPOSED_SOURCE_REVIEW_V6.json'
    H.save(stage_path, staged)
    stage_ref = H.bind(stage_path)
    context = H.inspect_review(stage_path, stage_ref['sha256'], execute=False)
    # Recheck stage/input bytes before publishing. No device or process action occurs here.
    H.rehash(context)
    execution.parent.mkdir(parents=True, exist_ok=False)
    with execution.open('xb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    H.need(H.bind(execution) == ef, 'Published source freeze must equal preview exactly')
    H.save(out, review)
    ref = H.bind(out)
    H.save(out.parent / 'ROOT_SOURCE_INPUT_VERIFICATION_V6.json', dict(
        status='ROOT_V6_SOURCE_REVIEW_AND_FILE_INPUTS_ACCEPTED', source_review=ref,
        staged_input_validation=stage_ref, native_closure=context['native_proof'], failed_configuration_proof=context['failed_configuration_proof'],
        source_count=len(sources), hardware_or_process_calls=0))
    print(json.dumps(dict(status='ROOT_V6_SOURCE_REVIEW_AND_FILE_INPUTS_ACCEPTED', source_review=ref, execution_freeze=ef)))


if __name__ == '__main__':
    main()
