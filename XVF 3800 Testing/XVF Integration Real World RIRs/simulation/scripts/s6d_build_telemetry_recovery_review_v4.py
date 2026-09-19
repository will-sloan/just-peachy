"""Record root's exact configured-state recovery review; see adjacent README."""
import json
from pathlib import Path
import s6d_closed_telemetry_restore_v4 as H

def main():
    r=H.R;s=H.SIM/'scripts';out=r/'capture_telemetry_recovery_v1/ROOT_SOURCE_REVIEW_V4.json'
    H.need(not out.exists(),'Immutable V4 root review exists')
    oldref=H.bind(r/'capture_telemetry_recovery_v1/ROOT_SOURCE_REVIEW_V3.json')
    H.need(oldref['sha256']=='86a23cc9784b81019243d64a81d0a81924697d481ee607f328084780bfc6cbed','Original V3 root authority changed')
    review=H.verify(oldref)
    freeze=H.bind(r/'runner/capture_owner_v9_source_v1/SOURCE_FREEZE.json')
    H.need(freeze['sha256']=='19e40fe96ab78c16350348c5a7157397805a8919ddc6eedd57f30eea3ca99eb8','Exact V9 freeze required')
    f=H.verify(freeze)
    for pair in f['sources']:
        for b in pair.values():H.need(H.bind(b['path'])==b,'Frozen source changed')
    H.need(len(f['owner_execution_dependency_bindings'])==24,'Exact24 canonical owner dependencies required')
    checks=H.verify(f['fixture_receipts']['narrow18'])
    H.need(checks['status']=='PASS' and checks['passed']==checks['total']==18 and all(c['status']=='PASS' for c in checks['tests']),'Full actual-state18 checks required')
    rf=H.bind(r/'capture_telemetry_recovery_source_v4/SOURCE_FREEZE.json')
    H.need(rf['sha256']=='99f628d0cb68e27408d6fb380e68e0d86def6ec97a695bc6f4ae81ef82ccdeb9','RecoveryV4 freeze changed')
    failure=H.bind(r/'closed_telemetry_restore_v3/RESULT.json');v=H.verify(failure)
    H.need(v['status']=='FAILED_UNRESOLVED' and v['device_restore_started'] is False and v['hardware_lock_acquired'] is True and v['hardware_lock_released'] is True,'Exact pre-setterV3 failure and lease closure required')
    for b in review['original_bindings'].values():H.verify(b)
    config=H.bind(Path('G:/Just_Peachy_S6D/20260913T195357Z/bank_captures_v1/beam_bank/S45_01_17/P_MAIN6/P_MAIN6_S45_01_17/configuration.json'))
    H.need(config['sha256']=='81be101a64abb0b11a1f02b1425330b82cfd6be615d5a87e9ff5e5a82da5a0af','Actual failed17 configuration changed')
    review['original_bindings'].update(previous_v3_recovery_result=failure,previous_v3_root_source_review=oldref,failed_configuration=config)
    paths=[Path(b['path']) for b in f['owner_execution_dependency_bindings']]+H.required_sources()+[Path(x['original']['path']) for x in f['sources']]
    paths += [Path(__file__),s/'README_S6D_BUILD_TELEMETRY_RECOVERY_REVIEW_V4.md']
    sources=list({str(p.resolve()):H.bind(p) for p in paths}.values())
    review.update(status=H.REVIEW_STATUS,utc=H.utc(),source_bindings=sources,owner_execution_source_freeze=freeze,
        source_freezes=[freeze,rf],fixture_receipts=f['fixture_receipts'],owner=H.bind(s/'s6d_capture_owner_v9.py'),
        recovery_output_root=str(r/'closed_telemetry_restore_v4'),prior_root_source_review=oldref,previous_recovery_failure=failure,
        root_review_findings=[
            'V1/V2/V3 root authorities and actual failed recovery directories are preserved. V3 acquired/released the lease and completed getters but rejected the exact intentionally configured gains/delay before any setter.',
            'Root read the complete V3-to-V4 helper and V8-to-V9 owner diffs, focused fixture source and actual18PASS receipt. V4 binds failed17 configuration to its unique admitted source/profile/failed charged ledger row and exact original immediate configuration readback.',
            'Before setters, the entire getter identity must exactly match either original identity or original identity projected through the five recorded configuration fields. Mixed/unknown states and immutable differences reject; no tolerances are introduced. Comparison proof is persisted and recomputed by file-only recovery verification.',
            'Eighteen focused fixtures use actual original state, saved actual fresh getters and exact failed configuration in full recovery orchestration with fake services and the retained WindowsServices.restore method. They reproduce V3 refusal, cover both accepted states, pre-setter adverse states, strict post-policy failure and tampered file joins. Broad tests were not repeated.',
            'Native2381-row cleanup, complete repeated process/TCP checks under lease, original-setting reapplication, strict physical-mode postidentity/readback policy and released lease remain mandatory. Old missing Python receipt, failed capture and charged seconds remain unchanged.',
            'Actual fresh restoration is not claimed by this source review. New378-row V9 queue admission,20check-plans, independent literal review and fresh physical QA remain necessary; physical40GiB/480attempt/21600s/floors/deadline stay unchanged.'
        ])
    H.save(out,review);ref=H.bind(out);c=H.inspect_review(out,ref['sha256'],execute=True)
    H.save(out.parent/'ROOT_SOURCE_INPUT_VERIFICATION_V4.json',dict(status='ROOT_V4_SOURCE_REVIEW_AND_FILE_INPUTS_ACCEPTED',source_review=ref,native_closure=c['native_proof'],failed_configuration_proof=c['failed_configuration_proof'],source_count=len(sources),hardware_or_process_calls=0))
    print(json.dumps(dict(status='ROOT_V4_SOURCE_REVIEW_AND_FILE_INPUTS_ACCEPTED',source_review=ref,execution_freeze=freeze)))

if __name__=='__main__':main()
