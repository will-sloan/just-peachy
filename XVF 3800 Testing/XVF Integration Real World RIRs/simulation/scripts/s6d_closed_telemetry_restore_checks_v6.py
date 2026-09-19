"""Recorded B3 pre-QA recovery fixtures; README_S6D_CLOSED_TELEMETRY_RESTORE_V6.md."""
from __future__ import annotations
import argparse, ast, json, sys, traceback, types
from copy import deepcopy
import importlib.util
from pathlib import Path
from unittest.mock import patch


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();assert out.drive.casefold()=='g:' and 'review_fixtures' in out.parts;out.mkdir(parents=True,exist_ok=False)
    m=load(a.source_root/'s6d_closed_telemetry_restore_v6.py','recovery6');rows=[]
    batch=m.R/'hardware_batches/bank_v4_P_MAIN6_B3_pre_QA';case=Path('G:/Just_Peachy_S6D/20260913T195357Z/bank_captures_v1/beam_bank/tagged_C_sentinel/P_INPUT_QA6/QA_P_MAIN6_B3_PRE_R2');td=case/'telemetry'
    original={k:m.bind(batch/n) for k,n in [('owner','owner_acquired.json'),('restoration','restoration.json'),('initial_state','initial_state.json'),('admission','admission.json'),('summary','SUMMARY.json')]}
    original.update(ledger=m.bind(m.R/'physical_ledger.json'),bridge_failure=m.bind(m.R/'physical_supervisor/bank_v4_P_MAIN6_B3_pre_QA/CAPTURE_BRIDGE_FAILURE.json'),supervisor_launch=m.bind(m.R/'runner/bank_queue_v5/ROOT_LAUNCH_V1.json'),capture_launch=m.bind(m.R/'runner/bank_queue_v5/state/LAUNCH_9e237467322d4b13985ce9d7f81b2ad3.json'),failed_configuration=m.bind(case/'configuration.json'),failed_capture_metadata=m.bind(case/'capture_metadata.json'))
    values={k:m.verify(b) for k,b in original.items()};initial=values['initial_state'];config=values['failed_configuration'];bridge=values['bridge_failure'];summary=values['summary'];current=dict(pid=1234,creation_time=100.0)
    refs={k:m.bind(td/n) for k,n in [('native_result','native/result.json'),('native_inspection','native/command_map_inspection.json'),('native_samples','native/samples.jsonl'),('native_transactions','native/transactions.tsv'),('stdout','stdout.bin'),('received','received_telemetry.jsonl'),('stderr','stderr.bin'),('python_terminal','result.json'),('process_identity','PROCESS_IDENTITY.json'),('lifecycle','lifecycle.jsonl'),('late_reader_closure','late_reader_closure.json')]}
    proof=m.recorded_terminal_closure(refs,614,bridge,summary)
    actual_before=m.pre_restore_identity_decision(initial,initial['identity'],config)['expected_configured_identity']
    known=[dict(role='capture_owner',pid=bridge['pid'],creation_time=bridge['creation_time']),dict(role='supervisor',pid=values['supervisor_launch']['pid'],creation_time=values['supervisor_launch']['creation_time']),dict(role='native_telemetry',**proof['historical_telemetry_pid_creation'])]
    def write(path,value):m.save(path,value);return m.bind(path)
    def check(name,call):
        try:call();rows.append(dict(name=name,status='PASS'))
        except BaseException:rows.append(dict(name=name,status='FAIL',error=traceback.format_exc()))
    def reject(call):
        try:call()
        except (ValueError,RuntimeError,KeyError,TypeError):return
        raise AssertionError('Expected fail-closed rejection')
    def equal(a,b):assert a==b,(a,b)
    def context(label):
        review=dict(status='PROPOSED_SOURCE_REVIEW_ONLY',fixture_only=True,allow_fresh_exposed_restore=False,owner_thread_id=m.ROOT_THREAD,run_id='20260913T195357Z',original_batch='bank_v4_P_MAIN6_B3_pre_QA',recovery_kind=m.KIND,historical_telemetry_pid_creation=proof['historical_telemetry_pid_creation'],original_bindings=original,source_bindings=[m.bind(x) for x in m.required_sources()],telemetry_bindings=refs,expected_measurement_rows=614,recovery_output_root=str(out/label))
        ref=write(out/(label+'_FIXTURE_INPUT.json'),review)
        return dict(review=review,review_ref=ref,original=original,values=values,known=known,native_proof=proof,output=out/label)
    class FakeControl:
        def __init__(self,before):self.state=deepcopy(before);self.settings=deepcopy(config['settings']);self.observe=deepcopy(initial['observe_only']);self.queries=[]
        def values(self,name):self.queries.append(name);return deepcopy(self.state[name])
        def query(self,name):self.queries.append(name);assert name=='BLD_MSG';return self.state['build_reply']
        def identify(self):
            result=m.pre_restore_identity(self);assert result['I2S_INPUT_PACKED']==[0];return result
    class Fake:
        fixture=True
        def __init__(self,before,post_bad=False):
            self.identity=current;self.events=[];self.owned=False;self.scans=0;self.control=FakeControl(before);self.static=list(initial['settings']);self.observe_only=list(initial['observe_only']);self.post_bad=post_bad
        def census(self):
            self.events.append('scan');self.scans+=1
            return dict(complete=True,errors=[],observed_unix=1000.0,rows=[dict(current,name='fixture.exe',cmdline=[])])
        def ports_idle(self):
            self.events.append('ports');return dict(schema='s6d-tcp-listener-census.v1',api="psutil.net_connections(kind='tcp')",complete=True,errors=[],rows=[],observed_unix=1000.0)
        def acquire(self):self.events.append('acquire');self.owned=True
        def release(self):self.events.append('release');self.owned=False;return True
        def initialize_control(self,path):assert self.owned and self.scans==2;self.events.append('initialize')
        def identify(self):self.events.append('identify');return m.pre_restore_identity(self.control)
        def values(self,control,name):
            if name in control.state:return deepcopy(control.state[name])
            return deepcopy(control.settings[name] if name in control.settings else control.observe[name])
        def set_verified(self,control,name,value):
            assert self.owned and self.scans==3 and name=='I2S_INPUT_PACKED' and value==[0];self.events.append('set_packed0');control.state[name]=deepcopy(value)
        def reset(self,control,bits,change_width):
            assert bits==16;self.events.append('reset');control.state['USB_BIT_DEPTH']=[bits,bits];return dict(fixture=True,change_width=change_width)
        def restore_exposed(self,control,settings):
            self.events.append('reapply');control.settings=deepcopy(settings)
            for key in set(settings)&set(control.state):control.state[key]=deepcopy(settings[key])
            proof=dict(observed=deepcopy(settings),exact_match=True)
            if self.post_bad:control.settings['SHF_BYPASS']=[99]
            return proof
        def restore(self,expected):
            assert self.owned and self.scans==3 and expected==initial;self.events.append('restore');return m.WindowsServices.restore(self,expected)
    passed={}
    def orchestration(label,before,good=True,helper=m,post_bad=False):
        c=context(label);service=Fake(before,post_bad)
        if good:
            ref=helper.recover_prevalidated(c,service);rec=m.read(ref['path']);result=m.read(c['output']/'RESULT.json')
            assert result['status']=='FRESH_RESTORE_VERIFIED' and result['device_restore_started'] and result['device_restore_completed'] and result['hardware_lock_released'] and rec['fixture_only'] is True
            assert result['policy_evaluation']['accepted'] and result['fresh_restore']['readback']['identity']==initial['identity']
            equal(service.events,['scan','ports','acquire','scan','ports','initialize','identify','scan','ports','restore','set_packed0','reset','reapply','scan','ports','release'])
            equal(service.control.queries[:11],list(m.IDENTITY_GETTERS)+['BLD_MSG']);passed[label]=(c,rec,result)
        else:
            reject(lambda:helper.recover_prevalidated(c,service));result=m.read(c['output']/'RESULT.json')
            assert result['status']=='FAILED_UNRESOLVED' and result['hardware_lock_released'] and not (c['output']/'RECOVERY.json').exists()
            if not post_bad:assert result['device_restore_started'] is False and 'restore' not in service.events
        write(out/(label+'_OBSERVED.json'),dict(events=service.events,queries=service.control.queries,result=m.bind(c['output']/'RESULT.json')))
    check('actual_recorded_terminal_native614_and_parent_binding',lambda:equal(proof['historical_telemetry_pid_creation'],dict(pid=602832,creation_time=1789415391.2722838)))
    check('actual_failed_case_source_config_ledger_audio_closed',lambda:m.failed_configuration_proof(original,values))
    check('exact_actual_bankV5_supervisor_and_QA_child',lambda:equal(m.supervisor_launch_proof(original,values)['supervisor_identity'],dict(pid=638164,creation_time=1789415331.064818)))
    def wrong_old_supervisor():
        previous=m.bind(m.R/'runner/bank_queue_v4/ROOT_LAUNCH_V1.json');wrong=dict(original,supervisor_launch=previous);wrong_values=dict(values,supervisor_launch=m.verify(previous))
        reject(lambda:m.supervisor_launch_proof(wrong,wrong_values))
    check('old_bankV4_supervisor_launch_rejected',wrong_old_supervisor)
    def wrong_child_literal():
        wrong=deepcopy(m.verify(original['capture_launch']));wrong['job_sha256']='0'*64;real=m.verify
        with patch.object(m,'verify',lambda ref:deepcopy(wrong) if ref==original['capture_launch'] else real(ref)):
            reject(lambda:m.supervisor_launch_proof(original,values))
    check('wrong_child_approved_job_join_rejected',wrong_child_literal)

    def configuration_reject(kind):
        wrong=deepcopy(values['failed_configuration'])
        if kind=='profile':wrong['profile']='P_MAIN6'
        else:wrong['source_input']['source']['sha256']='0'*64
        real=m.verify
        with patch.object(m,'verify',lambda ref:deepcopy(wrong) if ref==original['failed_configuration'] else real(ref)):
            reject(lambda:m.failed_configuration_proof(original,values))
    check('QA_profile_cannot_be_replaced_by_MAIN',lambda:configuration_reject('profile'))
    check('QA_source_binding_cannot_change',lambda:configuration_reject('source'))

    def changed_ref(key,mutate):
        d=m.read(refs[key]['path']);mutate(d);changed=dict(refs);changed[key]=write(out/(key+'_'+str(len(rows))+'.json'),d)
        reject(lambda:m.recorded_terminal_closure(changed,614,bridge,summary))
    check('recorded_python_PASS_cannot_replace_FAIL',lambda:changed_ref('python_terminal',lambda d:d.update(status='PASS')))
    check('recorded_python_exit_claim_cannot_replace_unproven',lambda:changed_ref('python_terminal',lambda d:d.update(native_process_exited=True)))
    check('recorded_python_missing_reader_closure_rejected',lambda:changed_ref('python_terminal',lambda d:d.update(reader_thread_closed=False)))
    check('recorded_python_foreign_received_binding_rejected',lambda:changed_ref('python_terminal',lambda d:d.update(receipt_file=dict(d['receipt_file'],sha256='0'*64))))
    check('foreign_parent_process_rejected',lambda:changed_ref('process_identity',lambda d:d.update(parent_pid=1)))
    check('late_receipt_cannot_promote_exit',lambda:changed_ref('late_reader_closure',lambda d:d.update(process_exited=True)))
    check('wrong_native_population_rejected',lambda:reject(lambda:m.recorded_terminal_closure(refs,613,bridge,summary)))
    def lifecycle_change():
        events=m.json_lines(refs['lifecycle']['path']);events[5]['monotonic_ns']=events[2]['monotonic_ns']-1
        path=out/'bad_lifecycle.jsonl';path.write_text(''.join(json.dumps(x)+'\n' for x in events));changed=dict(refs,lifecycle=m.bind(path));reject(lambda:m.recorded_terminal_closure(changed,614,bridge,summary))
    check('impossible_lifecycle_order_rejected',lifecycle_change)
    def census(pid,creation,name='fixture.exe',cmd=[]):return dict(complete=True,errors=[],observed_unix=1000.0,rows=[dict(current,name='fixture.exe',cmdline=[]),dict(pid=pid,creation_time=creation,name=name,cmdline=cmd)])
    check('recorded_telemetry_alive_rejected_even_without_marker',lambda:reject(lambda:m.scan_decision(census(602832,1789415391.2722838),known,current)))
    check('reused_pid_is_not_historical_identity',lambda:m.scan_decision(census(602832,1789415392.0),known,current))
    check('new_task_control_pid_still_rejected',lambda:reject(lambda:m.scan_decision(census(7777,999.,'powershell.exe',['Run-S6D-Telemetry.ps1']),known,current)))
    check('v5_exact_original_full_restore',lambda:orchestration('original_positive',initial['identity']))
    check('v5_exact_recorded_configuration_full_restore',lambda:orchestration('configured_positive',actual_before))
    mixed=deepcopy(actual_before);mixed['AUDIO_MGR_MIC_GAIN']=initial['identity']['AUDIO_MGR_MIC_GAIN']
    check('mixed_identity_blocked_before_setter',lambda:orchestration('mixed_identity',mixed,False))
    def verifier(change=None):
        c,receipt,result=passed['configured_positive'];rec=deepcopy(receipt);rec['fixture_only']=False;measurement=deepcopy(result);measurement['fixture_only']=False
        review=deepcopy(c['review']);review.update(status=m.REVIEW_STATUS,allow_fresh_exposed_restore=True)
        if change=='history':rec['historical_python_terminal_receipt_present']=False
        if change=='known':measurement['known_processes']=measurement['known_processes'][:2]
        if change=='supervisor':review['original_bindings']=dict(review['original_bindings'],supervisor_launch=m.bind(m.R/'runner/bank_queue_v4/ROOT_LAUNCH_V1.json'))
        if change=='preidentity':measurement['pre_restore_identity_comparison']['reason']='invented'
        if change=='kind':rec['recovery_kind']='closed_recorded_telemetry_fresh_restore'
        actual_verify=m.verify
        def reader(ref):
            if ref==rec['recovery_measurement']:return deepcopy(measurement)
            if ref==rec['source_review']:return deepcopy(review)
            return actual_verify(ref)
        with patch.object(m,'verify',reader):return m.verify_recovery_record(rec,owner_binding=original['owner'],restoration_binding=original['restoration'],initial_binding=original['initial_state'])
    check('file_only_verifier_recomputes_recorded_failure_full_restore',lambda:equal(verifier()['status'],'VERIFIED_CLOSED_RECORDED_QA_TELEMETRY_FRESH_RESTORE'))
    for field in ('history','known','preidentity','kind','supervisor'):check('verifier_rejects_'+field,lambda field=field:reject(lambda:verifier(field)))
    def owner_dispatch(mode):
        tree=ast.parse((a.source_root/'s6d_capture_owner_v11.py').read_bytes());node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='prior_closure')
        local=out/('owner_'+mode);folder=local/'hardware_batches/fixture_batch';folder.mkdir(parents=True)
        own=write(folder/'owner_acquired.json',values['owner']);failed=write(folder/'restoration.json',values['restoration']);initialref=write(folder/'initial_state.json',initial)
        write(local/'physical_ledger.json',dict(passes=[],batches=dict(fixture_batch=dict(owner=own,restoration=failed))))
        rec=dict(schema_version=m.SCHEMA,recovery_kind=m.KIND,original_restoration=failed,original_owner=own)
        if mode=='old_kind':rec['recovery_kind']='closed_native_telemetry_fresh_restore'
        if mode=='recorded_parent_kind':rec['recovery_kind']='closed_recorded_telemetry_fresh_restore'
        ref=write(local/'fixture_recovery.json',rec);calls=[]
        def v6(receipt,**kwargs):
            calls.append('v6');equal(kwargs,dict(owner_binding=own,restoration_binding=failed,initial_binding=initialref))
            if mode=='invalid':raise ValueError('Rejected exact new recovery')
            return dict(status='VERIFIED_CLOSED_RECORDED_QA_TELEMETRY_FRESH_RESTORE',old_failure_preserved=True,historical_python_terminal_receipt_present=True)
        def v5(receipt,**kwargs):
            calls.append('v5');return dict(status='VERIFIED_CLOSED_RECORDED_TELEMETRY_FRESH_RESTORE',old_failure_preserved=True,historical_python_terminal_receipt_present=True)
        def v4(receipt,**kwargs):
            calls.append('v4');return dict(status='VERIFIED_CLOSED_NATIVE_TELEMETRY_FRESH_RESTORE',old_failure_preserved=True,historical_python_terminal_receipt_present=False)
        scope=dict(Path=Path,read=m.read,verify=m.verify,binding=m.bind,SCHEMA='fixture-other-schema',POLICY='unused',NO_MUTATION_POLICY='unused')
        exec(compile(ast.Module(body=[node],type_ignores=[]),'owned_fixture','exec'),scope)
        modules={'s6d_closed_telemetry_restore_v6':types.SimpleNamespace(verify_recovery_record=v6),'s6d_closed_telemetry_restore_v5':types.SimpleNamespace(verify_recovery_record=v5),'s6d_closed_telemetry_restore_v4':types.SimpleNamespace(verify_recovery_record=v4)}
        with patch.dict(sys.modules,modules):
            if mode=='invalid':reject(lambda:scope['prior_closure'](local,[ref]))
            else:scope['prior_closure'](local,[ref])
        equal(calls,['v4'] if mode=='old_kind' else ['v5'] if mode=='recorded_parent_kind' else ['v6'])
    for mode in ('valid','invalid','old_kind','recorded_parent_kind'):check('owner_v11_'+mode+'_exact_dispatch',lambda mode=mode:owner_dispatch(mode))
    def retained():
        def tree(path):return ast.parse(path.read_bytes())
        def functions(path):return {n.name:ast.dump(n,include_attributes=False) for n in tree(path).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        old=functions(a.source_root/'s6d_closed_telemetry_restore_v5.py');new=functions(a.source_root/'s6d_closed_telemetry_restore_v6.py')
        for key in ('native_closure','tcp_census','tcp_listener_decision','WindowsServices','pre_restore_identity','pre_restore_identity_decision','rehash'):equal(old[key],new[key])
        old=functions(a.source_root/'s6d_capture_owner_v10.py');new=functions(a.source_root/'s6d_capture_owner_v11.py')
        equal(set(old),set(new))
        for key in set(old)-{'validate_plan','prior_closure'}:equal(old[key],new[key])
        val=next(n for n in tree(a.source_root/'s6d_capture_owner_v11.py').body if isinstance(n,ast.FunctionDef) and n.name=='validate_plan')
        deps=next(n.value for n in ast.walk(val) if isinstance(n,ast.Assign) and isinstance(n.value,ast.List) and any(isinstance(x,ast.Name) and x.id=='required' for x in n.targets))
        equal(len(deps.elts),27)
        for ref in list(original.values())+list(refs.values()):equal(m.bind(ref['path']),ref)
    check('unchanged_native_restore_TCP_owner_science_and27deps',retained)
    receipt=dict(status='PASS' if all(x['status']=='PASS' for x in rows) else 'FAIL',fixture_only=True,source=m.bind(a.source_root/'s6d_closed_telemetry_restore_v6.py'),owner_source=m.bind(a.source_root/'s6d_capture_owner_v11.py'),fixture=m.bind(__file__),actual_original=original,actual_telemetry=refs,native_proof=proof,tests=rows,passed=sum(x['status']=='PASS' for x in rows),total=len(rows),hardware_calls=0,actual_process_census=0,actual_TCP_census=0,models=0,root_approval_created=False,scope='Saved exact recorded FAIL plus native population and fake-service restore/owner dispatch only; no actual closure or restoration claimed.')
    write(out/'RECEIPT.json',receipt);print(json.dumps(dict(status=receipt['status'],passed=receipt['passed'],total=receipt['total'],receipt=m.bind(out/'RECEIPT.json'),failures=[x for x in rows if x['status']=='FAIL']),indent=2));return 0 if receipt['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
