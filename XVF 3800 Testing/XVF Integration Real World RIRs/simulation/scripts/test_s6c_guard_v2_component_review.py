"""Independent narrow fast_v2 guard review; README_S6C_GUARD_V2_COMPONENT_REVIEW.md."""
import argparse,ast,hashlib,importlib,json,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
EXPECTED={'s6c_long_native_epoch4_fast_v2.py':'079642ba24d59f625a6ae0c4342d9a26f51e56221f29b5a50f54830adfa22d67','s6c_paced_epoch4_fast_v2.py':'a8776724003fa2a642575892327b7c3e88eaddf29606881b302b05157c12b270'}
def binding(path):
 raw=Path(path).read_bytes();return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def functions(path):return {n.name:n for n in ast.parse(Path(path).read_bytes()).body if isinstance(n,ast.FunctionDef)}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
 for n,h in EXPECTED.items():assert binding(HERE/n)['sha256']==h
 names=[*EXPECTED,'README_S6C_LONG_NATIVE_EPOCH4_FAST_V2.md','README_S6C_PACED_EPOCH4_FAST_V2.md','test_s6c_protected_guard_v2.py','README_S6C_PROTECTED_GUARD_V2.md','s6c_long_native_epoch4_fast_v1.py','s6c_paced_epoch4_fast_v1.py']
 before=[binding(HERE/n) for n in names];T=importlib.import_module('test_s6c_protected_guard_v2');T.OUT=a.output/'REPRODUCED_GUARD_CHECKS.json';T.main()
 L=T.L;checks=[]
 def good(name,ok):assert ok,name;checks.append(name)
 for filename,fn in [('s6c_paced_epoch4_fast_', 'worker'),('s6c_paced_epoch4_fast_','run'),('s6c_long_native_epoch4_fast_','run')]:
  old=functions(HERE/(filename+'v1.py'))[fn];new=functions(HERE/(filename+'v2.py'))[fn]
  good('independent_exact_AST_'+filename+fn,ast.dump(old,include_attributes=False)==ast.dump(new,include_attributes=False))
 node=functions(L.__file__)['protected_override'];text=ast.unparse(node)
 good('strong_function_and_code_references_retained','retained = {name: (getattr(driver, name), getattr(driver, name).__code__)' in text)
 good('allowed_overrides_restored_in_finally',bool(node.body[-1].finalbody) and 'setattr(driver, name, value)' in ast.unparse(node.body[-1].finalbody[0]))
 policy=L.protected_guard_policy();original=HERE/'s6c_long_session.py';compiled=compile(original.read_bytes(),str(original),'exec')
 codes={c.co_name:c for c in compiled.co_consts if isinstance(c,types.CodeType) and c.co_name in L.PROTECTED}
 good('whole_source_all_six_baseline_codes',len(codes)==6 and set(codes)==set(policy['protected']))
 for name,code in codes.items():
  value=L.structural_code_value(code)
  good('independent_field_projection_'+name,all(value[k]==v for k,v in {'argcount':code.co_argcount,'posonlyargcount':code.co_posonlyargcount,'kwonlyargcount':code.co_kwonlyargcount,'nlocals':code.co_nlocals,'stacksize':code.co_stacksize,'flags':code.co_flags,'bytecode':code.co_code.hex(),'names':list(code.co_names),'varnames':list(code.co_varnames),'linetable':code.co_linetable.hex(),'exceptiontable':code.co_exceptiontable.hex(),'freevars':list(code.co_freevars),'cellvars':list(code.co_cellvars)}.items()))
 good('source_policy_has_no_process_local_ids','identity' not in json.dumps(policy['original_structural_code_sha256']))
 good('all_exact_inputs_remain_held',before==[binding(HERE/n) for n in names])
 result=dict(status='PASS_NARROW_SOURCE_AND_MODEL_FREE_REVIEW',independent_checks=checks,inherited_focused_checks=len(T.checks),inherited_receipt=binding(T.OUT),sources=before,reviewer=[binding(__file__),binding(HERE/'README_S6C_GUARD_V2_COMPONENT_REVIEW.md')],scope='Source/guard/AST checks only. No original module import or native/APP/model/audio/trajectory execution, storage walk, preparation or retry. Stable typed hashes correct reference-sensitive serialization; no unlogged old per-function cause is inferred. Native/observer timing bodies and v1 evidence remain unchanged.',model_calls=0,native_calls=0)
 target=a.output/'REVIEW_RECEIPT.json';target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(binding(target)))
if __name__=='__main__':main()
