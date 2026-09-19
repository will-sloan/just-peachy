"""Record completed V2/V7 root source review; see adjacent README."""
import json
from pathlib import Path
import s6d_closed_telemetry_restore_v2 as H

def main():
    r=H.R;s=H.SIM/'scripts';oldref=H.bind(r/'capture_telemetry_recovery_v1/ROOT_SOURCE_REVIEW.json')
    H.need(oldref['sha256']=='e64e2336824a0f869801734b8671f613db0359146fd3a91a45ed6235ccf90661','Original root review differs')
    review=H.verify(oldref);out=r/'capture_telemetry_recovery_v1/ROOT_SOURCE_REVIEW_V2.json'
    H.need(not out.exists(),'Immutable V2 root review exists')
    freeze=H.bind(r/'runner/capture_owner_v7_source_v1/SOURCE_FREEZE.json')
    H.need(freeze['sha256']=='0cea3d2088f1876af87b40d5b70d58d4771bc3a459492705ac099fdfc2eaf9e1','Exact V7 freeze required')
    f=H.verify(freeze)
    for pair in f['sources']:
        for b in pair.values():H.need(H.bind(b['path'])==b,'Frozen source differs')
    for b in f['fixture_receipts'].values():H.verify(b)
    rf=H.bind(r/'capture_telemetry_recovery_source_v2/SOURCE_FREEZE.json')
    H.need(rf['sha256']=='01bc88d8d6ee8be4d9bed82ab91a33ec8acbdd4b4952e4cac1b526f5d64748da','Exact restorationV2 freeze required')
    a=H.verify(rf);H.need(a['checks_passed']==a['checks_total']==20,'Affected20 checks required')
    failure=H.bind(r/'closed_telemetry_restore_v1/RESULT.json');v=H.verify(failure)
    H.need(v['status']=='FAILED_UNRESOLVED' and v['device_restore_started'] is False and v['hardware_lock_acquired'] is False,'Preserved pre-device failure differs')
    for b in review['original_bindings'].values():H.verify(b)
    review['original_bindings'].update(previous_recovery_result=failure,previous_root_source_review=oldref)
    paths=[Path(b['path']) for b in f['owner_execution_dependency_bindings']]+H.required_sources()+[Path(x['original']['path']) for x in f['sources']]
    paths += [Path(__file__),s/'README_S6D_BUILD_TELEMETRY_RECOVERY_REVIEW_V2.md']
    sources=list({str(p.resolve()):H.bind(p) for p in paths}.values())
    review.update(status=H.REVIEW_STATUS,utc=H.utc(),source_bindings=sources,owner_execution_source_freeze=freeze,
        source_freezes=[freeze,rf],fixture_receipts=f['fixture_receipts'],owner=H.bind(s/'s6d_capture_owner_v7.py'),
        recovery_output_root=str(r/'closed_telemetry_restore_v2'),prior_root_source_review=oldref,previous_recovery_failure=failure,
        root_review_findings=[
            'Original complete recovery/telemetry source review and34+23+11 tests remain recorded in boundV1 root authority. V1 actually refused before lock/getter/setter on inconclusive Windows connect_ex; original failure and outputs preserved.',
            'Root read complete V1-to-V2 restore diff and V6-to-V7 owner diff. Existing20 targeted listener/recovery checks and10 affected owner checks pass at these exact frozen hashes; no broad rerun.',
            'V2 uses complete OS TCP listener tables and pure IPv4/IPv6 loopback/wildcard decisions. Tables are persisted before validation; enumeration errors, invalid rows or recorder listeners reject. No timeout is interpreted as idle. The same authoritative check replaces the owner pre-lock socket probe.',
            'Original native2381-row cleanup proof, PID/creation/task control checks, locked getter/setter/readback order, accepted V5 restoration policy, released lease and historical-failure preservation remain required.',
            'V7 physical40GiB policy,480attempts/21600s,C50/G75floors and original deadline remain unchanged. Larger future offline allowance is separate and does not alter this hardware execution.',
            'Actual fresh restore PASS and released lock remain unobserved at source acceptance; separately reviewed378-row queue and freshQA are required for capture continuation.'
        ])
    H.save(out,review);ref=H.bind(out);c=H.inspect_review(out,ref['sha256'],execute=True)
    H.save(out.parent/'ROOT_SOURCE_INPUT_VERIFICATION_V2.json',dict(status='ROOT_V2_SOURCE_REVIEW_AND_FILE_INPUTS_ACCEPTED',source_review=ref,native_closure=c['native_proof'],source_count=len(sources),hardware_or_process_calls=0))
    print(json.dumps(dict(status='ROOT_V2_SOURCE_REVIEW_AND_FILE_INPUTS_ACCEPTED',source_review=ref,measurement_rows=c['native_proof']['measurement_rows'],execution_freeze=freeze)))

if __name__=='__main__':main()
