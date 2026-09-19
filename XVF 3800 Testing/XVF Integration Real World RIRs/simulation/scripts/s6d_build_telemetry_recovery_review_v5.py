"""Record root-reviewed B3 recovery authority; see adjacent README."""
import argparse
import json
from pathlib import Path
import s6d_closed_telemetry_restore_v5 as H


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--independent-review', type=Path, required=True)
    parser.add_argument('--independent-sha256', required=True)
    args = parser.parse_args()
    r, s = H.R, H.SIM / 'scripts'
    out = r / 'capture_telemetry_recovery_v2/ROOT_SOURCE_REVIEW_V5.json'
    execution = r / 'runner/capture_owner_v10_source_v1/SOURCE_FREEZE.json'
    H.need(not out.exists() and not execution.exists(), 'Fresh immutable authority paths required')
    proposal = H.bind(r / 'capture_telemetry_recovery_source_v5/SOURCE_FREEZE.json')
    H.need(proposal['sha256'] == 'ace2b9be538b00d386bd7111bba694bd534c534cbd7d39c8afb4f7f8c48e5de1', 'Exact V5/V10 proposal required')
    f = H.verify(proposal)
    independent = H.bind(args.independent_review)
    H.need(independent['sha256'] == args.independent_sha256, 'Exact independently reviewed hash required')
    independent_data = H.verify(independent)
    H.need(str(independent_data['status']).startswith('PASS') and not independent_data.get('findings'), 'Independent source review must pass')
    for pair in f['source_copies']:
        for b in pair.values():
            H.need(H.bind(b['path']) == b, 'Source or frozen copy changed')
    canonical = f['canonical_execution_sources']
    H.need(len(canonical) == 26 and len({Path(b['path']).name.casefold() for b in canonical}) == 26, 'Exact26 canonical dependencies required')
    for b in canonical + f['recovery_required_sources']:
        H.need(H.bind(b['path']) == b, 'Canonical or recovery dependency changed')
    for b in list(f['original_evidence'].values()) + list(f['telemetry_evidence'].values()):
        H.need(H.bind(b['path']) == b, 'Original or telemetry evidence changed')
    checks = H.verify(f['fixture_receipt'])
    H.need(checks['status'] == 'PASS' and checks['passed'] == checks['total'] == 25 and all(t['status'] == 'PASS' for t in checks['tests']), 'All25 focused checks required')
    snapshot = H.bind(out.parent / 'ROOT_PROCESS_SNAPSHOT.json')
    observation = H.verify(snapshot)
    H.need(observation.get('no_matching_task_control_processes') is True and observation.get('matching_processes') == [] and observation.get('query_errors') == [], 'Root current control snapshot must be complete')
    oldref = H.bind(r / 'capture_telemetry_recovery_v1/ROOT_SOURCE_REVIEW_V4.json')
    H.need(oldref['sha256'] == '128d2b7a4a7b3c4ae2ff8063c3401d36190272da2a834c2306c240c2352f970d', 'Preserve exact prior root source authority')
    old = H.verify(oldref)
    H.verify(old['output_confirmation'])
    owner = H.bind(s / 's6d_capture_owner_v10.py')
    bridge, policy = H.bind(s / 's6d_capture_supervisor_bridge_v2.py'), H.bind(s / 's6d_restoration_policy_v1.py')
    H.need(all(b in canonical for b in (owner, bridge, policy)), 'Canonical owner/bridge/policy required')
    combined = dict(schema='s6d-owner-execution-source-freeze.v1', status='ROOT_ACCEPTED_V10_RECORDED_TERMINAL_SOURCE_ONLY',
        utc=H.utc(), source_proposal=proposal, independent_review=independent,
        sources=[dict(original=p['original'], frozen=p['copy']) for p in f['source_copies']],
        owner_execution_dependency_bindings=canonical, fixture_receipts=dict(recorded25=f['fixture_receipt']),
        owner=owner, bridge=bridge, policy=policy, actual_hardware_or_process_calls=0)
    execution.parent.mkdir(parents=True, exist_ok=False)
    H.save(execution, combined)
    ef = H.bind(execution)
    paths = [Path(b['path']) for b in canonical + f['recovery_required_sources']]
    paths += [Path(p['original']['path']) for p in f['source_copies']]
    paths += [Path(__file__), s / 'README_S6D_BUILD_TELEMETRY_RECOVERY_REVIEW_V5.md']
    sources = list({str(p.resolve()): H.bind(p) for p in paths}.values())
    review = dict(status=H.REVIEW_STATUS, run_id='20260913T195357Z', owner_thread_id=H.ROOT_THREAD,
        utc=H.utc(), original_batch='bank_v3_P_MAIN6_B3', recovery_kind=H.KIND,
        allow_fresh_exposed_restore=True, original_bindings=f['original_evidence'],
        source_bindings=sources, owner_execution_source_freeze=ef, source_freezes=[ef, proposal],
        independent_source_review=independent, fixture_receipts=combined['fixture_receipts'],
        root_telemetry_review=old['root_telemetry_review'], owner=owner, bridge=bridge, policy=policy,
        root_process_snapshot=snapshot, telemetry_bindings=f['telemetry_evidence'], expected_measurement_rows=2390,
        output_confirmation=old['output_confirmation'], recovery_output_root=str(r / 'closed_telemetry_restore_v5'),
        historical_telemetry_pid_creation=dict(pid=609852, creation_time=1789410880.3176687),
        prior_root_source_review=oldref, actual_restoration_performed=False, new_queue_admitted=False,
        root_review_findings=[
            'Root read the complete V4-to-V5 and V9-to-V10 diffs and25 focused checks; independent source review passed. All prior sources and failures remain immutable.',
            'The exact B3 Python FAIL, recorded PID/parent/creation,2390 native/received rows, lifecycle, cleanup and reader proof are joined. Historical process exit and stderr closure remain unproven; no exit time or race is inferred.',
            'All native work completes before the final C# frame; the saved record does not explain host shutdown delay. No telemetry timing, timeout or scientific capture behavior changes.',
            'Actual recovery requires fresh repeated complete process/TCP checks for all original owners including recorded telemetry PID, sole hardware lease, whole exact original or configured identity, original reapply/reset/readback, strict policy and released lease. Mixed/unknown states reject; no process termination or playback.',
            'New ownerV10 adds only the distinct recorded-terminal recovery verifier and its required sources. All previous recovery kinds remain, and canonical26 execution files are separate from nested historical producer evidence.',
            'This authority admits only the exact fresh restoration after its runtime gates. Actual restoration is not yet claimed. A new reviewed312-attempt physical queue with fresh QA and preserved failures is a separate requirement; all original caps/floors/deadline remain.'
        ])
    H.save(out, review)
    ref = H.bind(out)
    context = H.inspect_review(out, ref['sha256'], execute=True)
    H.save(out.parent / 'ROOT_SOURCE_INPUT_VERIFICATION_V5.json', dict(
        status='ROOT_V5_SOURCE_REVIEW_AND_FILE_INPUTS_ACCEPTED', source_review=ref,
        native_closure=context['native_proof'], failed_configuration_proof=context['failed_configuration_proof'],
        source_count=len(sources), hardware_or_process_calls=0))
    print(json.dumps(dict(status='ROOT_V5_SOURCE_REVIEW_AND_FILE_INPUTS_ACCEPTED', source_review=ref, execution_freeze=ef)))


if __name__ == '__main__':
    main()
