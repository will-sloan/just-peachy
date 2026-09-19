"""Materialize root's completed source review; see adjacent README for inputs and commands."""
import json
from pathlib import Path
import s6d_closed_telemetry_restore_v1 as H

def main():
    r=H.R;s=H.SIM/'scripts';out=r/'capture_telemetry_recovery_v1/ROOT_SOURCE_REVIEW.json'
    H.need(not out.exists(),'Immutable root review already exists')
    frozen=H.bind(r/'runner/capture_owner_v6_source_v1/SOURCE_FREEZE.json')
    H.need(frozen['sha256']=='1b50e155f6af2b14db4a77041c39e22890f09971750d27bfec37a3019eaa1558','Combined source freeze changed')
    f=H.read(frozen['path'])
    for pair in f['sources']:
        for b in pair.values():H.need(H.bind(b['path'])==b,'Frozen source changed')
    for b in f['fixture_receipts'].values():H.verify(b)
    recovery_freeze=H.bind(r/'capture_telemetry_recovery_source_v1/SOURCE_FREEZE.json')
    H.need(recovery_freeze['sha256']=='b49201b771374e27230c9382b1c46417ef69e17af25434224904e25b819d4acf','Recovery freeze changed')
    rf=H.read(recovery_freeze['path']);H.need(rf['checks_passed']==rf['checks_total']==34,'Recovery fixture closure absent')
    telemetry_review=H.bind(r/'capture_telemetry_recovery_v1/ROOT_TELEMETRY_V2_REVIEW.json')
    H.need(telemetry_review['sha256']=='5e677129741dcb3e901322975c4522ccb1f6e468088b2d990d4a0f862be5c483','Root telemetry review changed')
    source_paths=[Path(b['path']) for b in f['owner_execution_dependency_bindings']]+H.required_sources()
    source_paths += [Path(pair['original']['path']) for pair in f['sources']]
    source_paths += [Path(__file__),s/'README_S6D_BUILD_TELEMETRY_RECOVERY_REVIEW_V1.md']
    sources=list({str(p.resolve()):H.bind(p) for p in source_paths}.values())
    batch=r/'hardware_batches/bank_v2_P_MAIN6_B1'
    originals={k:H.bind(batch/n) for k,n in [('owner','owner_acquired.json'),('restoration','restoration.json'),('initial_state','initial_state.json'),('admission','admission.json'),('summary','SUMMARY.json')]}
    originals.update(ledger=H.bind(r/'physical_ledger.json'),bridge_failure=H.bind(r/'physical_supervisor/bank_v2_P_MAIN6_B1/CAPTURE_BRIDGE_FAILURE.json'),supervisor_launch=H.bind(r/'runner/bank_queue_v3/ROOT_LAUNCH_V1.json'))
    passes=H.read(originals['ledger']['path'])['passes']
    H.need(len(passes)==52 and sum(x['status']=='PASS' for x in passes)==51 and [x['attempt_id'] for x in passes if x['status']=='FAIL']==['P_MAIN6_S45_01_17'],'Exact interrupted ledger required')
    folder=Path('G:/Just_Peachy_S6D/20260913T195357Z/bank_captures_v1/beam_bank/S45_01_17/P_MAIN6/P_MAIN6_S45_01_17/telemetry')
    telemetry={k:H.bind(folder/n) for k,n in [('native_result','native/result.json'),('native_inspection','native/command_map_inspection.json'),('native_samples','native/samples.jsonl'),('native_transactions','native/transactions.tsv'),('stdout','stdout.bin'),('received','received_telemetry.jsonl'),('stderr','stderr.bin')]}
    review=dict(status=H.REVIEW_STATUS,run_id='20260913T195357Z',owner_thread_id=H.ROOT_THREAD,utc=H.utc(),original_batch='bank_v2_P_MAIN6_B1',recovery_kind=H.KIND,allow_fresh_exposed_restore=True,
        source_bindings=sources,owner_execution_source_freeze=frozen,source_freezes=[frozen,recovery_freeze],fixture_receipts=f['fixture_receipts'],root_telemetry_review=telemetry_review,
        owner=H.bind(s/'s6d_capture_owner_v6.py'),bridge=H.bind(s/'s6d_capture_supervisor_bridge_v2.py'),policy=H.bind(s/'s6d_restoration_policy_v1.py'),original_bindings=originals,
        root_process_snapshot=H.bind(r/'capture_telemetry_recovery_v1/ROOT_PROCESS_SNAPSHOT.json'),telemetry_bindings=telemetry,expected_measurement_rows=2381,
        output_confirmation=H.bind(r/'FRESH_XVF_OUTPUT_CONFIRMATION_V1.json'),recovery_output_root=str(r/'closed_telemetry_restore_v1'),historical_telemetry_pid_creation=None,
        root_review_findings=[
            'Root read complete recovery helper and README, complete telemetry V2 and native final-frame producer, and complete V5-to-V6 owner diff. Existing 34 recovery,23 telemetry and11 owner checks accepted at exact frozen hashes; no redundant fixture rerun.',
            'Real delayed anonymous-pipe EOF reproduces original manager-finalization failure. The exact historical OS EOF delay cause remains unrecorded.',
            'Fresh restore requires exact source/data hashes, native cleanup and complete received population, original PID/creation absence, complete control-process and recorder-port checks repeated inside exclusive hardware ownership before setters and after readback.',
            'Only accepted existing packed-disable/reset/exposed-setting restoration and unchanged V5 policy are admitted. No audio, termination, firmware, driver or model operations.',
            'Original telemetry Python result/PID remain missing and the failed capture/restoration plus52 charges remain immutable. Fresh recovery does not accept failed capture17 or whole interrupted batch.',
            'Actual restore PASS and released lock, separately reviewed remaining queue admission, and fresh telemetry-V2 physical QA are still required before unattended capture continuation.'
        ],actual_restoration_performed=False,new_queue_admitted=False)
    H.save(out,review);ref=H.bind(out)
    context=H.inspect_review(out,ref['sha256'],execute=True)
    H.save(out.parent/'ROOT_SOURCE_INPUT_VERIFICATION.json',dict(status='ROOT_SOURCE_REVIEW_AND_FILE_INPUTS_ACCEPTED',source_review=ref,native_closure=context['native_proof'],source_count=len(sources),hardware_or_process_calls=0))
    print(json.dumps(dict(status='ROOT_SOURCE_REVIEW_AND_FILE_INPUTS_ACCEPTED',source_review=ref,measurement_rows=context['native_proof']['measurement_rows'],execution_dependencies=len(f['owner_execution_dependency_bindings']))))

if __name__=='__main__':main()
