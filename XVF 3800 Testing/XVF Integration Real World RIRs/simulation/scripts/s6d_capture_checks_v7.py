"""Narrow V7 dependency checks only; README_S6D_CAPTURE_V7.md."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types


def bind(p):
    p=Path(p).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path,required=True);ap.add_argument('--baseline-batch',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    out=a.output.resolve();assert out.is_relative_to(Path('G:/Just_Peachy_S6D').resolve());out.mkdir(parents=True,exist_ok=False)
    s=a.source_root.resolve();sys.path.insert(0,str(s));source=s/'s6d_capture_owner_v7.py'
    old=(s/'s6d_capture_owner_v6.py').read_text();new=source.read_text()
    normalized=new.replace('V7 cooperative telemetry','V6 cooperative telemetry').replace('README_S6D_CAPTURE_V7.md','README_S6D_CAPTURE_V6.md').replace('s6d_closed_telemetry_restore_v2','s6d_closed_telemetry_restore_v1').replace('README_S6D_CLOSED_TELEMETRY_RESTORE_V2.md','README_S6D_CLOSED_TELEMETRY_RESTORE_V1.md')
    tree=ast.parse(normalized);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='recorder_port_preflight')
    lines=normalized.splitlines(True);normalized=''.join(lines[:node.lineno-1]+lines[node.end_lineno+2:])
    normalized=normalized.replace("        import psutil\n        summary['recorder_port_preflight']=recorder_port_preflight(batch_dir,psutil)\n", "        for port in (8765,8766,8767):\n            with socket.socket() as sock:\n                sock.settimeout(.2)\n                if sock.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Existing recorder owner port '+str(port))\n")
    assert ast.dump(ast.parse(old),include_attributes=False)==ast.dump(ast.parse(normalized),include_attributes=False),'Owner changed beyond declared dependency and port preflight'
    checks=[dict(name='whole_source_equals_V6_except_declared_dependency_and_port_preflight',status='PASS')]
    spec=importlib.util.spec_from_file_location('owner_v7_review',source);owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
    r=out/'fixture_report';b=r/'hardware_batches/fixture_old_failure';initial=json.loads((a.baseline_batch/'initial_state.json').read_text())
    save(b/'initial_state.json',initial);save(b/'owner_acquired.json',dict(pid=999,fixture_only=True));save(b/'restoration.json',dict(status='FAIL',telemetry_process_closed=False,audio_handles_closed=True,hardware_lease_released=True,fixture_only=True))
    expected=dict(owner_binding=bind(b/'owner_acquired.json'),restoration_binding=bind(b/'restoration.json'),initial_binding=bind(b/'initial_state.json'))
    ledger=dict(passes=[dict(status='FAIL',attempt_id='fixture_charged')],batches={'fixture_old_failure':dict(owner=expected['owner_binding'],restoration=expected['restoration_binding'])});save(r/'physical_ledger.json',ledger)
    rec=dict(schema_version='edge-s6d-restoration-recovery.v2',original_restoration=expected['restoration_binding'],fixture_only=True);save(r/'FIXTURE_RECOVERY.json',rec)
    calls=[];stub=types.ModuleType('s6d_closed_telemetry_restore_v2');previous=sys.modules.get(stub.__name__)
    def verifier(receipt,**kwargs):
        assert receipt==rec and kwargs==expected;calls.append(kwargs)
        return dict(status='VERIFIED_CLOSED_NATIVE_TELEMETRY_FRESH_RESTORE',old_failure_preserved=True)
    stub.verify_recovery_record=verifier;sys.modules[stub.__name__]=stub
    try:assert owner.prior_closure(r,[bind(r/'FIXTURE_RECOVERY.json')])==ledger and len(calls)==1
    finally:
        if previous is None:sys.modules.pop(stub.__name__)
        else:sys.modules[stub.__name__]=previous
    checks.append(dict(name='actual_V7_prior_closure_imports_V2_and_passes_exact_original_joins',status='PASS'))
    spec=importlib.util.spec_from_file_location('actual_recovery_v2_review',s/'s6d_closed_telemetry_restore_v2.py');actual=importlib.util.module_from_spec(spec);spec.loader.exec_module(actual)
    try:actual.verify_recovery_record(rec,**expected)
    except (ValueError,KeyError):pass
    else:raise AssertionError('Actual verifier accepted fixture recovery')
    checks.append(dict(name='actual_V2_verifier_rejects_fixture_without_process_or_device_action',status='PASS'))
    class Provider:
        def __init__(self,rows=(),error=False):self.rows=rows;self.error=error
        def net_connections(self,**kwargs):
            assert kwargs==dict(kind='tcp')
            if self.error:raise OSError('Fixture census failure')
            return self.rows
    def endpoint(ip,port=8765,status='LISTEN',family=2):return types.SimpleNamespace(family=family,type=1,status=status,laddr=(ip,port),raddr=(),pid=999)
    for name,provider,expected_pass in [('empty',Provider(),True),('unrelated_listener',Provider([endpoint('127.0.0.1',9999)]),True),('ipv4_listener',Provider([endpoint('127.0.0.1')]),False),('ipv6_wildcard',Provider([endpoint('::',8767,family=23)]),False),('census_error',Provider(error=True),False),('malformed_address',Provider([endpoint('unknown')]),False)]:
        folder=out/('port_'+name);folder.mkdir()
        try:proof=owner.recorder_port_preflight(folder,provider);passed=True
        except ValueError:passed=False
        assert passed is expected_pass
        receipt=json.loads((folder/'RECORDER_PORT_PREFLIGHT.json').read_text());assert receipt['status']==('PASS' if expected_pass else 'FAIL') and receipt['census']==bind(folder/'RECORDER_TCP_LISTENERS.json') and receipt['checked_before_hardware_lock'] is True and receipt['timeout_interpreted_as_idle'] is False
        checks.append(dict(name='actual_owner_port_preflight_'+name,status='PASS'))
    execute=next(n for n in ast.parse(new).body if isinstance(n,ast.FunctionDef) and n.name=='execute')
    calls=[n for n in ast.walk(execute) if isinstance(n,ast.Call)]
    preflight=next(n.lineno for n in calls if isinstance(n.func,ast.Name) and n.func.id=='recorder_port_preflight')
    locked=next(n.lineno for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='locking')
    assert preflight<locked and 'connect_ex' not in new
    checks.append(dict(name='census_preflight_stays_before_existing_hardware_lock_without_connect_probe',status='PASS'))
    save(out/'RECEIPT.json',dict(status='PASS',checks=checks,sources=[bind(s/n) for n in ('s6d_capture_owner_v6.py','s6d_capture_owner_v7.py','s6d_closed_telemetry_restore_v2.py','s6d_telemetry_v2.py')],fixture=bind(__file__),model_calls=0,hardware_calls=0,processes_launched=0,positive_verifier_is_explicit_stub=True,no_approval_or_actual_recovery=True))
    print(json.dumps(dict(status='PASS',checks=len(checks),receipt=bind(out/'RECEIPT.json'))))


if __name__=='__main__':main()
