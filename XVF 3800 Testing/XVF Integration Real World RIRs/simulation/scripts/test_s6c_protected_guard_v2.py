"""Focused fast_v2 structural guard checks. README_S6C_PROTECTED_GUARD_V2.md."""
import ast,hashlib,io,json,marshal,sys,types
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch
import s6c_long_native_epoch4_fast_v2 as L
import s6c_paced_epoch4_fast_v2 as C
SIM=Path(__file__).resolve().parents[1];R=L.REPORT
OUT=R/'observer_fast_v2/GUARD_CHECKS_V2.json'
checks=[];evidence=[]
def check(name,ok):
    if not ok:raise AssertionError(name)
    checks.append(name)
def reject(name,action):
    try:action()
    except (ValueError,TypeError):checks.append(name);return
    raise AssertionError('Expected rejection: '+name)
def binding(p):return L.bind(p)
def asts(p):return {n.name:n for n in ast.parse(Path(p).read_text(encoding='utf-8')).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
class Names(ast.NodeTransformer):
    def visit_Constant(self,n):
        if isinstance(n.value,str):
            n.value=n.value.replace('s6c_long_native_epoch4_fast_v2','s6c_long_native_epoch4_fast_v1').replace('s6c_paced_epoch4_fast_v2','s6c_paced_epoch4_fast_v1').replace('EPOCH4_FAST_V2','EPOCH4_FAST_V1').replace('observer_fast_v2','observer_fast_v1').replace('_fast_v2','_fast_v1')
        return n
def normalized(node):
    return ast.dump(Names().visit(ast.parse(ast.unparse(node)).body[0]),include_attributes=False)
def new_driver():
    path=SIM/'scripts/s6c_long_session.py';module=types.ModuleType('s6c_long_session');module.__file__=str(path)
    module.json=json;module.Path=Path;module.sys=sys;module.bind=lambda p:dict(path=str(p))
    code=compile(path.read_bytes(),str(path),'exec')
    for c in code.co_consts:
        if isinstance(c,types.CodeType) and c.co_name in L.PROTECTED:setattr(module,c.co_name,types.FunctionType(c,vars(module),c.co_name))
    for name in L.ALLOWED_OVERRIDES:setattr(module,name,lambda:None)
    return module
def altered_context(driver,kind):
    replacements={k:lambda:1 for k in L.ALLOWED_OVERRIDES}
    with L.protected_override(driver,replacements):
        f=driver.native
        if kind=='function':driver.native=types.FunctionType(f.__code__,f.__globals__)
        elif kind=='code':f.__code__=f.__code__.replace()
        else:f.__code__=f.__code__.replace(co_consts=(*f.__code__.co_consts[:-1],'changed literal'))
def main():
    check('fresh output',not OUT.exists())
    policy=L.protected_guard_policy()
    check('six source-bound baseline functions',set(policy['original_structural_code_sha256'])==set(L.PROTECTED))
    check('algorithm source exact L',policy['algorithm_source']==binding(L.__file__))
    driver=new_driver();check('original whole-module compiled code admitted',L.validate_protected_driver(driver)==policy)
    replacements={k:lambda:1 for k in L.ALLOWED_OVERRIDES};original={k:getattr(driver,k) for k in replacements}
    old_ns={'PROTECTED':L.PROTECTED,'hashlib':hashlib,'marshal':marshal}
    old_node=asts(SIM/'scripts/s6c_long_native_epoch4_fast_v1.py')['protected_identities']
    exec(compile(ast.Module(body=[old_node],type_ignores=[]),'<old fingerprint>','exec'),old_ns)
    old=old_ns['protected_identities'];before=old(driver);stable=L.protected_identities(driver)
    with L.protected_override(driver,replacements):
        for _ in range(64):driver.source_bindings()
    after=old(driver)
    check('demonstrated old source_bindings marshal changed',before['source_bindings']!=after['source_bindings'])
    check('warm original helper stable structural and object IDs',L.protected_identities(driver)==stable)
    check('allowed observers restored',all(getattr(driver,k) is v for k,v in original.items()))
    evidence.append(dict(test='exact_original_source_bindings_64_calls',before=before['source_bindings'],after=after['source_bindings'],stable=stable['source_bindings']))
    with L.protected_override(driver,replacements):
        held=[v for v in driver.native.__code__.co_consts if type(v) is str]
        check('retained native constants do not change new fingerprints',L.protected_identities(driver)==stable)
    del held
    check('cold/warm persistent manifest policy exact',L.protected_guard_policy()==policy)
    for kind in ('function','code','constant'):
        mutated=new_driver();reject('detect protected '+kind+' replacement',lambda:altered_context(mutated,kind))
    mutated=new_driver();mutated.native=types.FunctionType((lambda:None).__code__,vars(mutated))
    reject('baseline rejects changed native before entry',lambda:L.validate_protected_driver(mutated))
    mutated=new_driver();mutated.__file__='foreign.py';reject('baseline rejects foreign source',lambda:L.validate_protected_driver(mutated))
    mutated=new_driver();mutated.native=types.FunctionType(mutated.native.__code__,{})
    reject('baseline rejects foreign global ownership',lambda:L.validate_protected_driver(mutated))
    with patch.dict(L.PINS,{'s6c_long_session.py':'0'*64}):
        reject('original source pin enforced',L.protected_guard_policy)
    check('typed bool vs integer',L.structural_code_value(True)!=L.structural_code_value(1))
    check('typed signed zero preserved',L.structural_code_value(0.)!=L.structural_code_value(-0.))
    reject('unsupported mutable constant fails',lambda:L.structural_code_value([]))
    for code in ('f.__code__.replace(co_code=bytes([9,0])+f.__code__.co_code[2:])','f.__code__.replace(co_firstlineno=f.__code__.co_firstlineno+1)','f.__code__.replace(co_name="different")','f.__code__.replace(co_flags=f.__code__.co_flags^0x1000000)'):
        f=new_driver().record_sample;altered=eval(code)
        check('structural difference '+code,L.structural_code_sha256(f.__code__)!=L.structural_code_sha256(altered))
    check('canonical namespace v2',C.namespace_roots('c065_main_fast_v2')[0].name=='c065_main_fast_v2')
    reject('canonical old namespace refused',lambda:C.namespace_roots('c065_main_fast_v1'))
    check('long namespace v2',L.output_roots('epoch4_long_c065_o0_fast_v2')[0].name=='epoch4_long_c065_o0_fast_v2')
    reject('long old namespace refused',lambda:L.output_roots('epoch4_long_c065_o0_fast_v1'))
    for n in ('s6c_long_native_epoch4.py','s6c_paced_epoch4.py','s6c_paced_controls.py','s6c_paced_b36_v1.py','s6c_long_b36_v1.py','s6c_paced_cross_routes_v1.py','s6c_paced_arrival_sentinel_v1.py','s6c_long_native_epoch4_fast_v1.py','s6c_paced_epoch4_fast_v1.py','s6c_long_native_epoch4_fast_v2.py','s6c_paced_epoch4_fast_v2.py','s6c_paced_cross_routes_fast_v2.py','s6c_paced_arrival_sentinel_fast_v2.py','s6c_paced_controls_fast_v1.py','s6c_paced_b36_fast_v1.py','s6c_long_b36_fast_v1.py','s6c_paced_cross_routes_fast_v1.py','s6c_paced_arrival_sentinel_fast_v1.py'):
        check('quiet recognizes '+n,L.worker_command(['python.exe',n,'run']))
    # Read only the pure policy-check statements before either admission can load native/assets.
    for module,name in ((L,'validate_plan'),(C,'admit')):
        fn=asts(module.__file__)[name];stmt=next(n for n in fn.body if isinstance(n,ast.If) and 'protected_guard_policy' in ast.unparse(n.test))
        namespace=vars(module).copy()
        for value in (None,dict(policy,schema='foreign')):
            namespace['plan']={'protected_guard_policy':value}
            reject(name+' rejects missing/tampered policy',lambda:exec(compile(ast.Module(body=[stmt],type_ignores=[]),'<policy guard>','exec'),namespace))
        namespace['plan']={'protected_guard_policy':policy}
        exec(compile(ast.Module(body=[stmt],type_ignores=[]),'<policy guard>','exec'),namespace)
        check(name+' accepts exact policy',True)
    deltas={}
    permitted={'long':{'protected_identities','protected_override','load_sources','prepare','validate_plan','worker_command'},'canonical':{'load_native','prepare','admit'}}
    added={'structural_code_value','structural_code_sha256','protected_guard_policy','validate_protected_driver','assert_protected_unchanged'}
    for label,base in [('long','s6c_long_native_epoch4_fast_'),('canonical','s6c_paced_epoch4_fast_')]:
        a,b=asts(SIM/'scripts'/f'{base}v1.py'),asts(SIM/'scripts'/f'{base}v2.py')
        changes=[n for n in a if normalized(a[n])!=normalized(b[n])]
        check(label+' only expected function changes',set(changes)<=permitted[label])
        check(label+' expected additions',set(b)-set(a)==(added if label=='long' else set()))
        deltas[label]=dict(changed_functions=changes,added_functions=sorted(set(b)-set(a)),unchanged_normalized_functions=sorted(set(a)-set(changes)))
    a,b=asts(SIM/'scripts/s6c_paced_epoch4_fast_v1.py'),asts(C.__file__)
    check('actual canonical worker AST identical',ast.dump(a['worker'],include_attributes=False)==ast.dump(b['worker'],include_attributes=False))
    check('canonical coordinator run AST identical',ast.dump(a['run'],include_attributes=False)==ast.dump(b['run'],include_attributes=False))
    a,b=asts(SIM/'scripts/s6c_long_native_epoch4_fast_v1.py'),asts(L.__file__)
    check('long run native body/timer AST identical',ast.dump(a['run'],include_attributes=False)==ast.dump(b['run'],include_attributes=False))
    check('scanner pin unchanged',L.FAST_SCAN_SHA=='579963cb5e873a0a08504bb4f022ea8a92a158886d36abfd87ee4a0f9cd6d299')
    check('observer policy unchanged',normalized(a['observer_policy'])==normalized(b['observer_policy']))
    for key,wanted in [('s6c_long_native_epoch4_fast_v1.py','0160a9a09c54183d2896dc6363e66ed67f1f0e049d7dcdddd4c7d22e6cb6b166'),('s6c_paced_epoch4_fast_v1.py','c13ed3849fb86aeb50341d823c2969b5084cd6e90aa8fee4c24785405e8d20c4')]:
        check('preserved '+key,binding(SIM/'scripts'/key)['sha256']==wanted)
    output=dict(schema='s6c-protected-guard-v2-checks.v1',status='PASS_SOURCE_AND_FOCUSED_GUARDS',checks=checks,check_count=len(checks),evidence=evidence,ast_deltas=deltas,guard_policy=policy,
       sources=[binding(SIM/'scripts'/n) for n in ('s6c_long_native_epoch4_fast_v1.py','s6c_paced_epoch4_fast_v1.py','s6c_long_native_epoch4_fast_v2.py','s6c_paced_epoch4_fast_v2.py','README_S6C_LONG_NATIVE_EPOCH4_FAST_V2.md','README_S6C_PACED_EPOCH4_FAST_V2.md','s6c_historical_fast_observer_v1.py','test_s6c_protected_guard_v2.py','README_S6C_PROTECTED_GUARD_V2.md')],
       previous_version=binding(R/'observer_fast_v2/GUARD_CHECKS_V1.json'),preserved_sources=binding(L.STAGING/'observer_fast_v2/before_quiet_union_v1/SOURCE_INDEX.json'),diagnosis=binding(R/'observer_fast_v1/protected_hash_diagnosis_v1/DIAGNOSIS.json'),native_calls=0,model_calls=0,original_module_imports=0,full_resource_scans=0,preparations=0,
       scope='Exact source and narrow diagnostic guards only. No protected native invocation, original APP import, source/model asset verification, full scan, real prepare or actual runtime.')
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(binding(OUT)));print('PASS',len(checks))
if __name__=='__main__':main()
