"""Eight affected model-free checks for the N6h closure-wire proposal; README adjacent."""
from pathlib import Path
import argparse
import ast
import copy
import dataclasses
import hashlib
import json
import math

SIM = Path(r'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation')
R = SIM / 'reports/S6D/20260913T195357Z'
G = Path(r'G:\Just_Peachy_S6D\20260913T195357Z')
JID = 'C_collection_P_MAIN6_C30_calibration_R04_calibration_collection_auto_asr_raw'
OUT = G / 'application/beam_C_collection_source_origin_v1' / JID

def bound(path):
    path = Path(path).resolve(); data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def extract(path, names, ns):
    parsed = ast.parse(Path(path).read_text(encoding='utf-8-sig'))
    nodes = [n for n in parsed.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    return ns

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    candidate=args.source_root/'s6d_beam_native_run_n6h.py'
    original=R/'application/beam_C_source_origin_proposal_v2/helpers/s6d_beam_native_run_n6g.py'
    assert bound(original)['sha256']=='6de4c1433c1f529e3e62e7d0bc5d0e9739a1ba951f530598abefad8b4ed0d7b2'
    before=bound(candidate)
    old_text=original.read_text(encoding='utf-8-sig'); new_text=candidate.read_text(encoding='utf-8-sig')
    expected=old_text.replace("closure.get('queues')==queues,'Consumer closure absent'", "closure_wire(closure.get('queues'))==closure_wire(queues),'Consumer closure absent'",1)
    def funcs(text):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    inherited=funcs(expected); current=funcs(new_text)
    assert set(current)==set(inherited)|{'closure_wire'}
    assert all(current[k]==v for k,v in inherited.items())
    def constants(text):return [ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign))]
    assert constants(new_text)==constants(old_text)
    old=extract(original,['validate_multistream'],{'RATE':16000})['validate_multistream']
    ns=extract(candidate,['closure_wire','validate_multistream'],{'RATE':16000,'json':json})
    new=ns['validate_multistream']
    r=read(OUT/'RESULT.json'); session=Path(r['session_dir'])
    f=read(session/'session_finalization_v3.json'); c=read(session/'s6d_consumer_closure.json'); a=read(OUT/'FULL_MULTISTREAM_AUDIT.json')
    settings_path=Path(read(r['manifest']['path'])['source_root'])/'edge_speech_pipeline/research_s6d.py'
    cls=extract(settings_path,['S6DSettings'],{'dataclass':dataclasses.dataclass,'asdict':dataclasses.asdict,'Path':Path,'json':json,'math':math})['S6DSettings']
    actual=copy.deepcopy(r); actual['telemetry']['s6d']['settings']=cls(**r['job']['settings']).receipt()
    assert a['status']=='REJECTED' and a['errors']==['Consumer closure absent']
    def call(fn,result,closure):return fn(result,r['job'],f,closure,a['journals'],a['dispatch'])
    cases=[]
    assert type(actual['telemetry']['s6d']['settings']['selected_profile_ids']) is tuple
    assert call(old,actual,c)==['Consumer closure absent'] and call(new,actual,c)==[]
    cases.append('actual_default_tuple_receipt_old_rejects_new_accepts_complete_saved_shape')
    rr=copy.deepcopy(actual); cc=copy.deepcopy(c)
    rr['telemetry']['s6d']['settings']['selected_profile_ids']=('fixture_opaque_profile',)
    cc['queues']['settings']['selected_profile_ids']=['fixture_opaque_profile']
    assert call(new,rr,cc)==[]
    cases.append('nonempty_tuple_and_identical_JSON_array_preserve_members')
    cc['queues']['settings']['selected_profile_ids']=['different_fixture_profile']
    assert 'Consumer closure absent' in call(new,rr,cc)
    cases.append('different_selected_profile_rejected')
    rr=copy.deepcopy(actual);cc=copy.deepcopy(c)
    rr['telemetry']['s6d']['event_consumer']['depth']=1;cc['queues']['event_consumer']['depth']=1
    assert 'Consumer closure absent' in call(new,rr,cc)
    cases.append('identical_but_nonzero_consumer_depth_rejected')
    cc=copy.deepcopy(c);cc.pop('full_event_consumer_drained')
    assert 'Consumer closure absent' in call(new,actual,cc)
    cases.append('missing_full_drain_proof_rejected')
    cc=copy.deepcopy(c);cc['queues']['journal']['max_handler_sec']+=0.000000001
    assert 'Consumer closure absent' in call(new,actual,cc)
    cases.append('changed_numeric_queue_measurement_rejected_without_rounding')
    cc=copy.deepcopy(c);cc['queues'].pop('settings')
    assert 'Consumer closure absent' in call(new,actual,cc)
    cases.append('missing_queue_key_rejected')
    rr=copy.deepcopy(actual);cc=copy.deepcopy(c)
    rr['telemetry']['s6d']['journal']['max_handler_sec']=float('nan');cc['queues']['journal']['max_handler_sec']=float('nan')
    try:call(new,rr,cc)
    except ValueError:pass
    else:raise AssertionError('Nonfinite JSON value accepted')
    cases.append('nonfinite_numeric_receipt_rejected')
    assert bound(candidate)==before
    result=dict(status='PASS',passed=len(cases),total=8,tests=[dict(name=x,status='PASS') for x in cases],
        source=before,original=bound(original),source_invariants='Every original function/class/import/constant AST unchanged except the exact full-queues wire comparison; only closure_wire added.',
        actual_inputs={name:bound(p) for name,p in [('result',OUT/'RESULT.json'),('closure',session/'s6d_consumer_closure.json'),('finalization',session/'session_finalization_v3.json'),('rejected_audit',OUT/'FULL_MULTISTREAM_AUDIT.json'),('settings',settings_path)]},
        fixture=bound(__file__),readme=bound(args.source_root/'README_S6D_N6H_CLOSURE_CHECKS_V1.md'),models_started=0,device_calls=0,process_queries=0,audio_reads=0,journal_scans=0,production_output_writes=0,
        limitation='Pure functions on actual saved receipt shape and small in-memory variants. No old result/event/audit edits or retrospective acceptance; no native-loop/model run.')
    args.output.mkdir(parents=True,exist_ok=False)
    output=args.output/'RECEIPT.json';output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(bound(output)))

if __name__=='__main__':main()
