"""Model-free restoration/recovery regressions; README_S6D_CAPTURE_V5.md."""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import traceback

sys.dont_write_bytecode = True


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def binding(path):
    path = Path(path).resolve(); data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).parent)
    parser.add_argument('--baseline-batch', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(Path('G:/Just_Peachy_S6D').resolve()):
        raise ValueError('Fresh G:/Just_Peachy_S6D child output required')
    output.mkdir(parents=True)
    source = args.source_root.resolve(); sys.path.insert(0, str(source))
    P = load_module('s6d_restoration_policy_v1', source/'s6d_restoration_policy_v1.py')
    sys.modules['s6d_restoration_policy_v1'] = P
    O = load_module('reviewed_owner_v5', source/'s6d_capture_owner_v5.py')
    B = load_module('reviewed_bridge_v2', source/'s6d_capture_supervisor_bridge_v2.py')
    initial = read(args.baseline_batch/'initial_state.json')
    original = read(args.baseline_batch/'restoration.json')
    baseline_bindings = [binding(args.baseline_batch/name) for name in ('initial_state.json', 'restoration.json')]
    rows = []

    def check(name, fn):
        try:
            fn(); rows.append(dict(name=name, status='PASS'))
        except BaseException as exc:
            rows.append(dict(name=name, status='FAIL', error=repr(exc), traceback=traceback.format_exc()))

    def require(value, message='Expected assertion'):
        if not value: raise AssertionError(message)

    def rejected(fn):
        try: fn()
        except (ValueError, RuntimeError, KeyError): return
        raise AssertionError('Invalid evidence admitted')

    def decision(mutator=None):
        i, a, r = copy.deepcopy((initial, original['readback'], original['reapply']))
        if mutator: mutator(i, a, r)
        return P.restoration_decision(i, a, r)

    def historical():
        d = decision()
        require(original['status']=='FAIL' and original['exact_recorded_configuration_match'] is False)
        require(d['accepted'] and d['exact_static_configuration_match'] and d['requested_gain_set_verified'])
        require(not d['exact_full_snapshot_match'] and d['autonomous_gain']['exception_used'])
        require(abs(d['autonomous_gain']['delta']-.10386)<1e-10)
        save(output/'SAVED_V4_FAILURE_NEW_POLICY_OBSERVATION.json', dict(evidence='Saved failure re-evaluation only; no current device state and no retroactive PASS', original=baseline_bindings[1], new_policy=d))
    check('saved_actual_V4_failure_preserved_dynamic_only_observation', historical)

    check('exact_full_restoration_does_not_use_dynamic_exception', lambda: require((lambda d: d['accepted'] and d['exact_full_snapshot_match'] and not d['autonomous_gain']['exception_used'])(decision(lambda i,a,r: a['settings'].update(PP_AGCGAIN=i['settings']['PP_AGCGAIN'])))))
    for group in ('settings', 'identity', 'observe_only'):
        check('wrong_'+group+'_rejects', lambda group=group: require(not decision(lambda i,a,r: a[group].update(UNDECLARED=[7]))['accepted']))
    check('changed_existing_static_field_rejects', lambda: require(not decision(lambda i,a,r: a['settings'].update(PP_AGCMAXGAIN=[124]))['accepted']))
    check('missing_static_field_rejects', lambda: require(not decision(lambda i,a,r: a['settings'].pop('PP_AGCMAXGAIN'))['accepted']))
    check('wrong_USB_readback_rejects', lambda: require(not decision(lambda i,a,r: a['identity'].update(USB_BIT_DEPTH=[24,24]))['accepted']))
    check('wrong_initial_USB_binding_rejects', lambda: require(not decision(lambda i,a,r: i.update(usb_bits=[24,24]))['accepted']))

    def all_setting(i, a, r, key, value):
        for m in (i['settings'], a['settings'], r['observed']): m[key]=value
    check('AGC_disabled_drift_rejects', lambda: require(not decision(lambda i,a,r: all_setting(i,a,r,'PP_AGCONOFF',[0]))['accepted']))
    check('boolean_AGC_enabled_drift_rejects', lambda: require(not decision(lambda i,a,r: all_setting(i,a,r,'PP_AGCONOFF',[True]))['accepted']))
    check('different_firmware_drift_rejects', lambda: require(not decision(lambda i,a,r: (i['identity'].update(VERSION=[3,3,0]),a['identity'].update(VERSION=[3,3,0])))['accepted']))
    check('missing_immediate_exact_proof_rejects', lambda: require(not decision(lambda i,a,r: r.pop('exact_match'))['accepted']))
    check('false_immediate_exact_proof_rejects', lambda: require(not decision(lambda i,a,r: r.update(exact_match=False))['accepted']))
    check('integer_cannot_replace_immediate_true', lambda: require(not decision(lambda i,a,r: r.update(exact_match=1))['accepted']))
    check('wrong_immediate_gain_rejects', lambda: require(not decision(lambda i,a,r: r['observed'].update(PP_AGCGAIN=[26.6]))['accepted']))
    check('wrong_immediate_static_rejects', lambda: require(not decision(lambda i,a,r: r['observed'].update(PP_AGCMAXGAIN=[124]))['accepted']))
    check('missing_immediate_full_settings_rejects', lambda: require(not decision(lambda i,a,r: r.pop('observed'))['accepted']))
    for label, value in [('NaN',[float('nan')]),('Inf',[float('inf')]),('low',[.999]),('high',[1000.001]),('bool',[True]),('string',['26.6']),('many',[26,27]),('scalar',26),('null',None)]:
        check('invalid_final_gain_'+label, lambda value=value: require(not decision(lambda i,a,r: a['settings'].update(PP_AGCGAIN=value))['accepted']))
    check('invalid_initial_gain_rejects', lambda: require(not decision(lambda i,a,r: (i['settings'].update(PP_AGCGAIN=[False]),r['observed'].update(PP_AGCGAIN=[False])))['accepted']))
    check('documented_lower_boundary_allowed_without_tolerance', lambda: require(decision(lambda i,a,r: a['settings'].update(PP_AGCGAIN=[1]))['accepted']))
    check('documented_upper_boundary_allowed_without_tolerance', lambda: require(decision(lambda i,a,r: a['settings'].update(PP_AGCGAIN=[1000]))['accepted']))
    for malformed in (None, [], 'bad', True):
        check('malformed_identity_'+repr(malformed), lambda malformed=malformed: require(not decision(lambda i,a,r: a.update(identity=malformed))['accepted']))

    def fixture(name, kind='v5'):
        report=output/name; batch=report/'hardware_batches/batch_A'; batch.mkdir(parents=True)
        save(batch/'owner_acquired.json', dict(pid=7123, acquired_utc='2026-09-14T12:00:01Z'))
        save(batch/'initial_state.json', initial)
        value=copy.deepcopy(original)
        value['initial_state']=binding(batch/'initial_state.json')
        if kind=='v5':
            value.update(schema_version=P.SCHEMA, **decision(), status='PASS', exact_recorded_configuration_match=False)
        elif kind=='no_mutation':
            value=dict(schema_version=P.SCHEMA, policy=P.NO_MUTATION_POLICY, status='PASS',exact_recorded_configuration_match=True,telemetry_process_closed=True,hardware_lease_released=True,scope='No setters or playback occurred under this owner')
        save(batch/'restoration.json', value)
        ledger=dict(passes=[] if kind=='no_mutation' else [dict(batch='batch_A',status='PASS',attempt_id='capture_A',charged_playback_s=12)],batches={'batch_A':dict(owner=binding(batch/'owner_acquired.json'),restoration=binding(batch/'restoration.json'))})
        save(report/'physical_ledger.json',ledger)
        identity=dict(pid=7123,creation_time=1789387200,admission_unix=1789387200)
        return report,batch,ledger,identity,value

    def revise(report,batch,ledger,value):
        save(batch/'restoration.json',value)
        ledger['batches']['batch_A']['restoration']=binding(batch/'restoration.json')
        save(report/'physical_ledger.json',ledger)

    def bridge_good():
        report,batch,ledger,identity,value=fixture('bridge_good')
        proof=B.restoration_proof(batch,ledger,identity)
        require(all(proof['checks'].values()) and proof['exact_full_snapshot_match'] is False)
        require(proof['restoration_policy']==P.POLICY and 'exact_configuration_match' not in proof['checks'])
        O.prior_closure(report)
    check('actual_bridge_and_prior_closure_accept_verified_V5_drift',bridge_good)

    def bridge_bad(name,mutate,kind='v5'):
        report,batch,ledger,identity,value=fixture(name,kind)
        mutate(value,ledger,identity)
        revise(report,batch,ledger,value)
        rejected(lambda: B.restoration_proof(batch,ledger,identity))
    check('bridge_preserved_V4_failure_rejects',lambda: bridge_bad('bridge_old_failure',lambda v,l,i: None,'old'))
    check('bridge_false_static_flag_rejects',lambda: bridge_bad('bridge_flag',lambda v,l,i: v.update(exact_static_configuration_match=False)))
    check('bridge_forged_readback_rejects',lambda: bridge_bad('bridge_readback',lambda v,l,i: v['readback']['settings'].update(PP_AGCMAXGAIN=[124])))
    check('bridge_wrong_owner_rejects',lambda: bridge_bad('bridge_owner',lambda v,l,i: i.update(pid=999)))
    check('bridge_unreleased_lease_rejects',lambda: bridge_bad('bridge_lease',lambda v,l,i: v.update(hardware_lease_released=False)))
    check('bridge_unclosed_audio_rejects',lambda: bridge_bad('bridge_audio',lambda v,l,i: v.update(audio_handles_closed=False)))
    check('bridge_packing_not_disabled_rejects',lambda: bridge_bad('bridge_pack',lambda v,l,i: v.update(packed_input_disabled=False)))
    def no_mutation():
        report,batch,ledger,identity,value=fixture('no_mutation','no_mutation')
        proof=B.restoration_proof(batch,ledger,identity)
        require(proof['checks']['no_mutation_no_gain_set_claim'] is True and 'requested_gain_set_verified' not in proof['checks'])
        O.prior_closure(report)
        ledger['passes']=[dict(batch='batch_A',status='PASS')]
        save(report/'physical_ledger.json',ledger)
        rejected(lambda: B.restoration_proof(batch,ledger,identity))
        rejected(lambda: O.prior_closure(report))
    check('no_mutation_closes_owner_without_gain_claim_and_rejects_capture_row',no_mutation)

    def recovery_fixture(name):
        report,batch,ledger,identity,value=fixture(name,'old')
        rec=dict(schema_version=P.RECOVERY_SCHEMA,status='PASS',original_restoration=ledger['batches']['batch_A']['restoration'],original_owner=ledger['batches']['batch_A']['owner'],reapply_origin=ledger['batches']['batch_A']['restoration'],initial_state=value['initial_state'],reapply=value['reapply'],readback=value['readback'],policy_evaluation=decision(),hardware_lease_released=True,audio_handles_closed=True,telemetry_process_closed=True,packed_input_disabled=True,no_playback=True,no_setters_or_reset=True)
        return report,batch,ledger,value,rec
    def recovery_good():
        report,batch,ledger,value,rec=recovery_fixture('recovery_good')
        before=binding(batch/'restoration.json')
        rejected(lambda: O.prior_closure(report))
        path=report/'RECOVERY.json';save(path,rec)
        O.prior_closure(report,[binding(path)])
        require(binding(batch/'restoration.json')==before and read(batch/'restoration.json')['status']=='FAIL')
        rejected(lambda: O.prior_closure(report,[binding(path),binding(path)]))
    check('explicit_bound_recovery_only_and_duplicate_rejects_old_failure_unchanged',recovery_good)

    def recovery_bad(name,mutator):
        report,batch,ledger,value,rec=recovery_fixture(name)
        mutator(rec)
        path=report/'RECOVERY.json';save(path,rec)
        rejected(lambda: O.prior_closure(report,[binding(path)]))
    for field in ('original_restoration','original_owner','reapply_origin','initial_state'):
        check('recovery_wrong_'+field,lambda field=field: recovery_bad('recovery_wrong_'+field,lambda r:r[field].update(sha256='0'*64)))
    check('recovery_changed_original_immediate_proof_rejects',lambda: recovery_bad('recovery_immediate',lambda r:r['reapply'].update(exact_match=False)))
    check('recovery_forged_decision_rejects',lambda: recovery_bad('recovery_decision',lambda r:r['policy_evaluation'].update(exact_full_snapshot_match=True)))
    for field in ('hardware_lease_released','audio_handles_closed','telemetry_process_closed','packed_input_disabled','no_playback','no_setters_or_reset'):
        check('recovery_missing_'+field,lambda field=field: recovery_bad('recovery_missing_'+field,lambda r:r.pop(field)))
    def wrong_new_policy():
        report,batch,ledger,identity,value=fixture('wrong_v5_policy')
        value.update(policy='unknown',exact_recorded_configuration_match=True)
        revise(report,batch,ledger,value)
        rejected(lambda: O.prior_closure(report))
    check('unknown_V5_policy_cannot_fallback_to_legacy_exact_match',wrong_new_policy)
    def old_open_owner():
        report,batch,ledger,value,rec=recovery_fixture('old_open_owner')
        value['audio_handles_closed']=False;revise(report,batch,ledger,value)
        rec.update(original_restoration=ledger['batches']['batch_A']['restoration'],reapply_origin=ledger['batches']['batch_A']['restoration'])
        path=report/'RECOVERY.json';save(path,rec)
        rejected(lambda: O.prior_closure(report,[binding(path)]))
    check('gain_recovery_cannot_override_unproven_original_audio_closure',old_open_owner)
    for b in baseline_bindings: require(binding(b['path'])==b,'Historical evidence changed')
    result=dict(status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',passed=sum(r['status']=='PASS' for r in rows),failed=sum(r['status']=='FAIL' for r in rows),tests=rows,source_bindings=[binding(source/name) for name in ('s6d_restoration_policy_v1.py','s6d_capture_owner_v5.py','s6d_capture_supervisor_bridge_v2.py')],fixture=binding(__file__),historical_inputs=baseline_bindings,hardware_calls=0,model_calls=0,scope='Pure decisions and file-only owner/bridge receipt admission; no physical restoration demonstrated')
    save(output/'RECEIPT.json',result)
    print(json.dumps(dict(status=result['status'],passed=result['passed'],failed=result['failed'],receipt=binding(output/'RECEIPT.json'))))
    if result['failed']: raise SystemExit(1)


if __name__=='__main__': main()
