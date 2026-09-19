"""Actual-state fake-service orchestration; README_S6D_CLOSED_TELEMETRY_RESTORE_V4.md."""
from __future__ import annotations
import argparse
import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import traceback
from unittest.mock import patch


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();assert out.drive.casefold()=='g:' and 'review_fixtures' in out.parts;out.mkdir(parents=True,exist_ok=False)
    m=load(a.source_root/'s6d_closed_telemetry_restore_v4.py','recovery4');old=load(a.source_root/'s6d_closed_telemetry_restore_v3.py','recovery3');rows=[]
    saved=m.read(m.R/'closed_telemetry_restore_v3/RESULT.json');authority=m.read(saved['source_review']['path']);original=deepcopy(authority['original_bindings'])
    configpath=Path('G:/Just_Peachy_S6D/20260913T195357Z/bank_captures_v1/beam_bank/S45_01_17/P_MAIN6/P_MAIN6_S45_01_17/configuration.json')
    original['failed_configuration']=m.bind(configpath);values={k:m.verify(b) for k,b in original.items()};initial=values['initial_state'];config=values['failed_configuration'];actual_before=saved['before_identity'];current=dict(pid=1234,creation_time=100.0)
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
        review=deepcopy(authority);review.update(status='PROPOSED_SOURCE_REVIEW_ONLY',fixture_only=True,allow_fresh_exposed_restore=False,original_bindings=original,source_bindings=[m.bind(x) for x in m.required_sources()],recovery_output_root=str(out/label))
        ref=write(out/(label+'_FIXTURE_INPUT.json'),review)
        return dict(review=review,review_ref=ref,original=original,values=values,known=saved['known_processes'],native_proof=saved['native_telemetry_closure'],output=out/label)
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
    check('actual_original_plan_configuration_source_ledger_join',lambda:m.failed_configuration_proof(original,values))
    check('old_v3_full_actual_configured_state_reproduces_pre_setter_failure',lambda:orchestration('old_v3_adverse',actual_before,False,old))
    check('v4_full_actual_original_state_restore_and_closure',lambda:orchestration('original_positive',initial['identity']))
    check('v4_full_actual_configured_state_restore_and_closure',lambda:orchestration('configured_positive',actual_before))
    for name,key,value in [('unknown_gain','AUDIO_MGR_MIC_GAIN',[2]),('mixed_original_gain','AUDIO_MGR_MIC_GAIN',[10]),('mixed_original_usb','USB_BIT_DEPTH',[16,16]),('unknown_delay','AUDIO_MGR_SYS_DELAY',[1]),('changed_geometry','AEC_MIC_ARRAY_GEO',[0]*12),('changed_firmware','VERSION',[3,2,2]),('changed_dac','I2S_DAC_DSP_ENABLE',[1])]:
        before=deepcopy(actual_before);before[key]=value;check(name+'_before_setters',lambda name=name,before=before:orchestration(name,before,False))
    check('post_restore_original_policy_still_required',lambda:orchestration('post_bad',actual_before,False,post_bad=True))
    def config_change(field,value):
        changed=deepcopy(config)
        if field=='source':changed['source_input']['source']=dict(changed['source_input']['source'],sha256='0'*64)
        else:changed[field]=value
        actual_verify=m.verify
        with patch.object(m,'verify',lambda b:deepcopy(changed) if b==original['failed_configuration'] else actual_verify(b)):reject(lambda:m.failed_configuration_proof(original,values))
    check('foreign_configuration_profile_rejected',lambda:config_change('profile','P_SCAN6'))
    check('foreign_configuration_source_rejected',lambda:config_change('source',None))
    check('missing_exact_configured_readback_rejected',lambda:config_change('reapply',dict(exact_match=False,observed=config['settings'])))
    def verifier(change=False):
        c,receipt,result=passed['configured_positive'];rec=deepcopy(receipt);rec['fixture_only']=False;measurement=deepcopy(result);measurement['fixture_only']=False
        review=deepcopy(c['review']);review.update(status=m.REVIEW_STATUS,allow_fresh_exposed_restore=True)
        if change:measurement['pre_restore_identity_comparison']['reason']='invented'
        actual_verify=m.verify
        def reader(ref):
            if ref==rec['recovery_measurement']:return deepcopy(measurement)
            if ref==rec['source_review']:return deepcopy(review)
            return actual_verify(ref)
        with patch.object(m,'verify',reader):return m.verify_recovery_record(rec,owner_binding=original['owner'],restoration_binding=original['restoration'],initial_binding=original['initial_state'])
    check('file_only_verifier_recomputes_actual_configured_join_in_memory',lambda:verifier())
    check('tampered_persisted_pre_identity_reason_rejected',lambda:reject(lambda:verifier(True)))
    def unchanged():
        def body(path,name):return ast.dump(next(x for x in ast.parse(path.read_bytes()).body if isinstance(x,(ast.FunctionDef,ast.ClassDef)) and x.name==name),include_attributes=False)
        for name in ('WindowsServices','native_closure','scan_decision','tcp_census','tcp_listener_decision','pre_restore_identity','rehash'):
            equal(body(a.source_root/'s6d_closed_telemetry_restore_v3.py',name),body(a.source_root/'s6d_closed_telemetry_restore_v4.py',name))
        v9=(a.source_root/'s6d_capture_owner_v9.py').read_text(encoding='utf-8');v8=(a.source_root/'s6d_capture_owner_v8.py').read_text(encoding='utf-8')
        equal(v9.replace('s6d_capture_owner_v9','s6d_capture_owner_v8').replace('README_S6D_CAPTURE_V9','README_S6D_CAPTURE_V8').replace('s6d_closed_telemetry_restore_v4','s6d_closed_telemetry_restore_v3').replace('README_S6D_CLOSED_TELEMETRY_RESTORE_V4','README_S6D_CLOSED_TELEMETRY_RESTORE_V3'),v8)
        for ref in original.values():equal(m.bind(ref['path']),ref)
    check('retained_restore_services_native_ports_processes_and_v9_dependency_only',unchanged)
    receipt=dict(status='PASS' if all(x['status']=='PASS' for x in rows) else 'FAIL',fixture_only=True,source=m.bind(a.source_root/'s6d_closed_telemetry_restore_v4.py'),fixture=m.bind(__file__),actual_original=original['initial_state'],actual_failed_configuration=original['failed_configuration'],actual_v3_failure=m.bind(m.R/'closed_telemetry_restore_v3/RESULT.json'),tests=rows,passed=sum(x['status']=='PASS' for x in rows),total=len(rows),hardware_calls=0,actual_process_census=0,models=0,root_approval_created=False,scope='Full recovery orchestration and actual retained restore method with fake services, saved actual state and real bound file provenance; no live control.')
    write(out/'RECEIPT.json',receipt);print(json.dumps(receipt,indent=2));return 0 if receipt['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
