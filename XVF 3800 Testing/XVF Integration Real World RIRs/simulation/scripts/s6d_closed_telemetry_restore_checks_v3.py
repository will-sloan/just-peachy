"""Pinned Control AST/getter seam checks; README_S6D_CLOSED_TELEMETRY_RESTORE_V3.md."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import types

CORE_SHA='8388988dac90240503bc277aec30b9e476f02d8b9210b620d5961be019a61cc6'
def bind(p):
    p=Path(p).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def save(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2)
def module(p,name):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def rejected(fn):
    try:fn()
    except (ValueError,RuntimeError):return
    raise AssertionError('Invalid pre-restore identity admitted')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path,required=True);ap.add_argument('--baseline-batch',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    s=a.source_root.resolve();out=a.output.resolve();assert out.is_relative_to(Path('G:/Just_Peachy_S6D').resolve());out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(s));core=s.parent.parent/'measurement_app/core.py';assert bind(core)['sha256']==CORE_SHA
    cls=next(n for n in ast.parse(core.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Control')
    methods=[copy.deepcopy(n) for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('values','identify')]
    # Evaluate only the two exact getter methods, never the module's imports or query implementation.
    subset=ast.Module(body=[ast.ClassDef(name='PinnedControl',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[]);ns={'re':re};exec(compile(ast.fix_missing_locations(subset),str(core),'exec'),ns);Control=ns['PinnedControl']
    helper=module(s/'s6d_closed_telemetry_restore_v3.py','helper_v3_fixture');previous=module(s/'s6d_closed_telemetry_restore_v2.py','helper_v2_fixture')
    failure_root=s.parent/'reports/S6D/20260913T195357Z/closed_telemetry_restore_v2';names=list(helper.IDENTITY_GETTERS)+['BLD_MSG'];raw={}
    refs=[]
    for i,name in enumerate(names,1):
        p=failure_root/'commands'/f'{i:04d}_{name}.stdout.bin';raw[name]=p.read_text(encoding='utf-8-sig');refs.append(bind(p))
    class Fake(Control):
        def __init__(self,overrides=None,fail=None):self.calls=[];self.overrides=overrides or {};self.fail=fail
        def query(self,name,*args):
            assert not args,'No setters permitted';self.calls.append(name)
            if name==self.fail:raise RuntimeError('Fixture read failure')
            return self.overrides.get(name,raw[name])
    checks=[]
    def check(name,fn):fn();checks.append(dict(name=name,status='PASS'));print(name+' PASS',flush=True)
    def old_adverse():
        f=Fake()
        try:f.identify()
        except RuntimeError as e:assert 'packed injection is enabled' in str(e);error=str(e)
        else:raise AssertionError('Pinned old identify did not reproduce packed1 refusal')
        assert f.calls==names
        save(out/'PINNED_OLD_IDENTIFY_REPRODUCTION.json',dict(status='REPRODUCED_WITH_FAKE_QUERY_NO_HARDWARE',error=error,query_names=f.calls,core=bind(core),actual_failed_result=bind(failure_root/'RESULT.json'),saved_getter_payloads=refs))
    check('actual_pinned_Control_identify_rejects_saved_packed1_after11_getters',old_adverse)
    def new_accepts():
        f=Fake();d=helper.pre_restore_identity(f);assert d['I2S_INPUT_PACKED']==[1] and f.calls==names and d['build_reply']==raw['BLD_MSG']
        service=object.__new__(helper.WindowsServices);service.control=Fake();assert service.identify()==d and service.control.calls==names
        save(out/'NEW_PRE_RESTORE_IDENTITY_FIXTURE.json',dict(status='READ_ONLY_FIXTURE_ACCEPTS_PACKED1',identity=d,query_names=f.calls,source=bind(s/'s6d_closed_telemetry_restore_v3.py'),no_actual_getters=True))
    check('new_pre_getter_and_actual_WindowsServices_seam_accept_same_exact11_reads',new_accepts)
    def packed_zero():
        changes={'I2S_INPUT_PACKED':'I2S_INPUT_PACKED 0\n'};old=Fake(changes);new=Fake(changes)
        assert old.identify()==helper.pre_restore_identity(new) and old.calls==new.calls==names
    check('packed0_identity_remains_identical_to_pinned_Control',packed_zero)
    for value in ('2','-1','1.0','0 1',''):
        check('invalid_packed_enum_'+repr(value),lambda value=value:rejected(lambda:helper.pre_restore_identity(Fake({'I2S_INPUT_PACKED':'I2S_INPUT_PACKED '+value+'\n'}))))
    for name,value in [('VERSION','3 2 2'),('AEC_MIC_ARRAY_TYPE','2'),('AEC_NUM_MICS','2'),('I2S_DAC_DSP_ENABLE','1')]:
        check('wrong_'+name+'_rejects',lambda name=name,value=value:rejected(lambda:helper.pre_restore_identity(Fake({name:name+' '+value+'\n'}))))
    check('wrong_build_rejects',lambda:rejected(lambda:helper.pre_restore_identity(Fake({'BLD_MSG':'unapproved build\n'}))))
    def read_failure():
        f=Fake(fail='AEC_NUM_MICS');rejected(lambda:helper.pre_restore_identity(f));assert f.calls==names[:3]
    check('getter_failure_stops_without_setters',read_failure)
    def strict_post_restore():
        sources=[ast.parse((s/n).read_text()) for n in ('s6d_closed_telemetry_restore_v2.py','s6d_closed_telemetry_restore_v3.py')]
        for method in ('restore','acquire','release','census','ports_idle','initialize_control'):
            nodes=[next(m for c in t.body if isinstance(c,ast.ClassDef) and c.name=='WindowsServices' for m in c.body if isinstance(m,ast.FunctionDef) and m.name==method) for t in sources]
            assert ast.dump(nodes[0],include_attributes=False)==ast.dump(nodes[1],include_attributes=False)
        for name in ('recover_prevalidated','verify_recovery_record','native_closure','scan_decision','tcp_census','tcp_listener_decision'):
            nodes=[next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name==name) for t in sources]
            assert ast.dump(nodes[0],include_attributes=False)==ast.dump(nodes[1],include_attributes=False),name
        rejected(lambda:Fake().identify())
    check('post_restore_strict_identify_and_all_ownership_port_native_policy_functions_unchanged',strict_post_restore)
    def owner_dependency():
        old=(s/'s6d_capture_owner_v7.py').read_text();new=(s/'s6d_capture_owner_v8.py').read_text()
        new=new.replace('V8 cooperative telemetry','V7 cooperative telemetry').replace('README_S6D_CAPTURE_V8.md','README_S6D_CAPTURE_V7.md').replace('s6d_closed_telemetry_restore_v3','s6d_closed_telemetry_restore_v2').replace('README_S6D_CLOSED_TELEMETRY_RESTORE_V3.md','README_S6D_CLOSED_TELEMETRY_RESTORE_V2.md');assert old==new
    check('V8_owner_only_changes_new_helper_README_dependency',owner_dependency)
    save(out/'RECEIPT.json',dict(status='PASS',checks=checks,sources=[bind(s/n) for n in ('s6d_closed_telemetry_restore_v2.py','s6d_closed_telemetry_restore_v3.py','s6d_capture_owner_v7.py','s6d_capture_owner_v8.py')],control_source=bind(core),fixture=bind(__file__),actual_failure_result=bind(failure_root/'RESULT.json'),models=0,process_census=0,hardware_calls=0,setters=0,real_Control_query_calls=0,only_pinned_values_identify_AST_evaluated=True))
    print(json.dumps(dict(status='PASS',count=len(checks),receipt=bind(out/'RECEIPT.json'))))


if __name__=='__main__':main()
