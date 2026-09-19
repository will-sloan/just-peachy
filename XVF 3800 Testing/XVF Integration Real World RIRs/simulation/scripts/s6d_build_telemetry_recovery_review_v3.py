"""Record the reviewed packed-mode identity adapter; see adjacent README."""
import json
from pathlib import Path
import s6d_closed_telemetry_restore_v3 as H

def main():
    r=H.R;s=H.SIM/'scripts';out=r/'capture_telemetry_recovery_v1/ROOT_SOURCE_REVIEW_V3.json'
    H.need(not out.exists(),'Immutable V3 root review exists')
    oldref=H.bind(r/'capture_telemetry_recovery_v1/ROOT_SOURCE_REVIEW_V2.json')
    H.need(oldref['sha256']=='1e6ec83bac32d02f6c0a074eedefeabbd1d946d3097e6dd606e91cfc4bea8cd9','Original V2 root authority changed')
    review=H.verify(oldref)
    freeze=H.bind(r/'runner/capture_owner_v8_source_v1/SOURCE_FREEZE.json')
    H.need(freeze['sha256']=='0df79c5481e67215646b94984c5021104953e99bd3552bbe8fa7a021c659c236','Exact V8 freeze required')
    f=H.verify(freeze)
    for pair in f['sources']:
        for b in pair.values():H.need(H.bind(b['path'])==b,'Frozen source changed')
    checks=H.verify(f['fixture_receipts']['narrow16']);H.need(checks['status']=='PASS' and len(checks['checks'])==16 and all(c['status']=='PASS' for c in checks['checks']),'Affected16 checks required')
    rf=H.bind(r/'capture_telemetry_recovery_source_v3/SOURCE_FREEZE.json')
    H.need(rf['sha256']=='7312f193723bb651fd6be3858b43f64298f2b0a1236993c523a84608ade30c8f','RecoveryV3 freeze changed')
    failure=H.bind(r/'closed_telemetry_restore_v2/RESULT.json');v=H.verify(failure)
    H.need(v['status']=='FAILED_UNRESOLVED' and v['device_restore_started'] is False and v['hardware_lock_acquired'] is True and v['hardware_lock_released'] is True,'Exact pre-setterV2 failure and lease closure required')
    for b in review['original_bindings'].values():H.verify(b)
    review['original_bindings'].update(previous_v2_recovery_result=failure,previous_v2_root_source_review=oldref)
    paths=[Path(b['path']) for b in f['owner_execution_dependency_bindings']]+H.required_sources()+[Path(x['original']['path']) for x in f['sources']]
    paths += [Path(__file__),s/'README_S6D_BUILD_TELEMETRY_RECOVERY_REVIEW_V3.md']
    sources=list({str(p.resolve()):H.bind(p) for p in paths}.values())
    review.update(status=H.REVIEW_STATUS,utc=H.utc(),source_bindings=sources,owner_execution_source_freeze=freeze,
        source_freezes=[freeze,rf],fixture_receipts=f['fixture_receipts'],owner=H.bind(s/'s6d_capture_owner_v8.py'),
        recovery_output_root=str(r/'closed_telemetry_restore_v3'),prior_root_source_review=oldref,previous_recovery_failure=failure,
        root_review_findings=[
            'V1/V2 root reviews, sources and actual failures are preserved. V2 OS process/listener checks passed, the lease was acquired/released, and11 actual identity getters completed; the microphone-only Control.identify check refused packed1 before setters.',
            'Root read the actual pinned Control class and complete V2-to-V3 helper and V7-to-V8 owner diffs. The sole new behavioral adapter performs the same10 values getters and BLD_MSG query while explicitly accepting typed packed enum0/1 before restoration.',
            'Exact firmware3.2.1/four-linear-mic/build/DAC constraints and original invariant identity comparison remain. Post-restoration Control.identify is unchanged and requires packed0. No getter exception is swallowed.',
            'Sixteen targeted tests use the actual pinned Control.values/identify AST with saved device replies; they reproduce the original rejection and verify exact getter sequence, valid packed0/1 and invalid modes/firmware/read failures. Existing lifecycle/port/policy logic is unchanged; broad tests were not repeated.',
            'Native2381-row cleanup, complete current process/TCP checks repeated under lease, actual original-setting restoration and full readback/policy plus released lease remain mandatory. Old missing Python receipt and failed capture/charges remain unchanged.',
            'Actual fresh restore is not claimed by this source review. New378-row V8 queue admission,20check-plans, independent literal review and fresh physicalQA remain required; all physical40GiB/480attempt/21600s/floor/deadline limits remain unchanged.'
        ])
    H.save(out,review);ref=H.bind(out);c=H.inspect_review(out,ref['sha256'],execute=True)
    H.save(out.parent/'ROOT_SOURCE_INPUT_VERIFICATION_V3.json',dict(status='ROOT_V3_SOURCE_REVIEW_AND_FILE_INPUTS_ACCEPTED',source_review=ref,native_closure=c['native_proof'],source_count=len(sources),hardware_or_process_calls=0))
    print(json.dumps(dict(status='ROOT_V3_SOURCE_REVIEW_AND_FILE_INPUTS_ACCEPTED',source_review=ref,execution_freeze=freeze)))

if __name__=='__main__':main()
