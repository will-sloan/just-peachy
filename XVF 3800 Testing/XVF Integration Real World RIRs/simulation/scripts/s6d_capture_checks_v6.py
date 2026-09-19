"""Narrow file-only V6 recovery dispatch checks; README_S6D_CAPTURE_V6.md."""
from __future__ import annotations
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types


def binding(p):
    p=Path(p).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2)
def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def reject(fn):
    try:fn()
    except (ValueError,RuntimeError,KeyError):return
    raise AssertionError('Invalid recovery admitted')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path,required=True);ap.add_argument('--baseline-batch',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    out=a.output.resolve();assert out.is_relative_to(Path('G:/Just_Peachy_S6D').resolve());out.mkdir(parents=True,exist_ok=False)
    s=a.source_root.resolve();sys.path.insert(0,str(s));o=load('review_owner_v6',s/'s6d_capture_owner_v6.py');v5=load('preserved_owner_v5',s/'s6d_capture_owner_v5.py')
    actual_verifier=load('review_actual_verifier',s/'s6d_closed_telemetry_restore_v1.py')
    initial=json.loads((a.baseline_batch/'initial_state.json').read_text());results=[];calls=[]
    original_module=sys.modules.get('s6d_closed_telemetry_restore_v1')
    stub=types.ModuleType('s6d_closed_telemetry_restore_v1')
    def accepted(record,**kwargs):
        calls.append((copy.deepcopy(record),copy.deepcopy(kwargs)))
        return dict(status='VERIFIED_CLOSED_NATIVE_TELEMETRY_FRESH_RESTORE',old_failure_preserved=True)
    stub.verify_recovery_record=accepted;sys.modules['s6d_closed_telemetry_restore_v1']=stub

    def tree(name,kind='v2',started=False,missing=False):
        r=out/name;b=r/'hardware_batches/fixture_failed_owner';save(b/'owner_acquired.json',dict(pid=999,fixture_only=True));save(b/'initial_state.json',initial)
        failed=dict(status='FAIL',telemetry_process_closed=False,audio_handles_closed=True,hardware_lease_released=True,fixture_only=True)
        save(b/'restoration.json',failed)
        owner=binding(b/'owner_acquired.json');restore=binding(b/'restoration.json');init=binding(b/'initial_state.json')
        ledger=dict(passes=[dict(attempt_id='fixture_charged',status='STARTED' if started else 'FAIL',charged_playback_s=1.)],batches={'fixture_failed_owner':dict(owner=owner,restoration=restore)})
        save(r/'physical_ledger.json',ledger)
        recovery=dict(schema_version='edge-s6d-restoration-recovery.'+kind,recovery_kind='closed_native_telemetry_fresh_restore',status='PASS',original_restoration=restore,original_owner=owner,initial_state=init,fixture_only=True)
        save(r/'FIXTURE_RECOVERY.json',recovery)
        if missing:(b/'restoration.json').unlink()
        return r,binding(r/'FIXTURE_RECOVERY.json'),recovery,dict(owner_binding=owner,restoration_binding=restore,initial_binding=init),ledger
    def check(name,fn):fn();results.append(dict(name=name,status='PASS'));print(name+' PASS',flush=True)

    def exact_dispatch():
        r,ref,rec,joins,ledger=tree('exact_dispatch');before=(r/'physical_ledger.json').read_bytes();count=len(calls)
        assert o.prior_closure(r,[ref])==ledger and calls[count]==(rec,joins) and len(calls)==count+1
        assert (r/'physical_ledger.json').read_bytes()==before
    check('authorized_v2_delegates_exact_owner_initial_joins_without_writes',exact_dispatch)
    def missing_authority():
        r,ref,*_=tree('missing_authority');before=len(calls);reject(lambda:o.prior_closure(r,[]));assert len(calls)==before
    check('unlisted_v2_recovery_cannot_bypass_prior_failure',missing_authority)
    def duplicate():
        r,ref,*_=tree('duplicate');before=len(calls);reject(lambda:o.prior_closure(r,[ref,ref]));assert len(calls)==before
    check('duplicate_authorized_matches_reject',duplicate)
    def unresolved():
        r,ref,*_=tree('started',started=True);before=len(calls);reject(lambda:o.prior_closure(r,[ref]));assert len(calls)==before
    check('unresolved_STARTED_still_blocks_before_recovery',unresolved)
    def absent():
        r,ref,*_=tree('missing_restoration',missing=True);before=len(calls);reject(lambda:o.prior_closure(r,[ref]));assert len(calls)==before
    check('missing_original_restoration_still_blocks',absent)
    def old_insufficient():
        r,ref,*_=tree('gain_only',kind='v1');before=len(calls);reject(lambda:o.prior_closure(r,[ref]));reject(lambda:v5.prior_closure(r,[ref]));assert len(calls)==before
    check('v1_gain_only_cannot_close_missing_python_telemetry',old_insufficient)
    def old_v5_refuses():
        r,ref,*_=tree('v5_refusal');reject(lambda:v5.prior_closure(r,[ref]))
    check('preserved_v5_still_refuses_new_recovery_scope',old_v5_refuses)
    def verifier_reject():
        r,ref,*_=tree('verifier_reject');stub.verify_recovery_record=lambda *args,**kwargs:(_ for _ in ()).throw(ValueError('Fixture rejected proof'))
        try:reject(lambda:o.prior_closure(r,[ref]))
        finally:stub.verify_recovery_record=accepted
    check('verifier_failure_propagates_without_gain_fallback',verifier_reject)
    def bad_return():
        r,ref,*_=tree('bad_return');stub.verify_recovery_record=lambda *args,**kwargs:dict(status='PASS',old_failure_preserved=True)
        try:reject(lambda:o.prior_closure(r,[ref]))
        finally:stub.verify_recovery_record=accepted
    check('unexpected_verifier_proof_rejects',bad_return)
    def actual_reject():
        r,ref,rec,joins,_=tree('actual_verifier_fixture');reject(lambda:actual_verifier.verify_recovery_record(rec,**joins))
        rec['fixture_only']=False;rec['recovery_kind']='gain_only';reject(lambda:actual_verifier.verify_recovery_record(rec,**joins))
    check('actual_verifier_rejects_fixture_and_wrong_recovery_kind',actual_reject)
    def unchanged_functions():
        trees=[ast.parse((s/n).read_text()) for n in ('s6d_capture_owner_v5.py','s6d_capture_owner_v6.py')]
        for name in ('check_budget','storage','prepare_input','restoration_permitted','stop_requested','capture_to_disk'):
            nodes=[next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name==name) for t in trees]
            assert ast.dump(nodes[0],include_attributes=False)==ast.dump(nodes[1],include_attributes=False),name
        assert (o.MAX_ATTEMPTS,o.MAX_PLAYBACK_SEC,o.MAX_PAYLOAD_BYTES)==(480,21600.,40*2**30)
    check('capture_recipe_callback_budget_floor_functions_unchanged',unchanged_functions)
    try:
        save(out/'RECEIPT.json',dict(status='PASS',checks=results,sources=[binding(s/n) for n in ('s6d_capture_owner_v5.py','s6d_capture_owner_v6.py','s6d_telemetry_v2.py','s6d_closed_telemetry_restore_v1.py')],fixture=binding(__file__),baseline_initial=binding(a.baseline_batch/'initial_state.json'),hardware_calls=0,processes_launched=0,model_calls=0,scope='File-only owner dispatch tests. Positive fresh-recovery verifier is deliberately a stub; actual verifier rejection tested separately. No fabricated production recovery or authority; listening/root independently test full verifier.'))
    finally:
        if original_module is None:sys.modules.pop('s6d_closed_telemetry_restore_v1',None)
        else:sys.modules['s6d_closed_telemetry_restore_v1']=original_module
    print(str(out/'RECEIPT.json'))


if __name__=='__main__':main()
