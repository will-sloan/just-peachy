"""Model-free protected-code fingerprint diagnosis. See README_S6C_PROTECTED_HASH_DIAGNOSIS_V1.md."""
import ast,hashlib,io,json,marshal,sys,types
from pathlib import Path
SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
DRIVER=SIM/'scripts/s6c_long_session.py'
L=SIM/'scripts/s6c_long_native_epoch4_fast_v1.py'
PROTECTED=('native','choose_profile','fixed_gallery_row','import_epoch','record_sample','source_bindings')
OUT=REPORT/'observer_fast_v1/protected_hash_diagnosis_v1'
def bind(p):
    raw=Path(p).read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def old(f):return dict(function_id=id(f),code_id=id(f.__code__),marshal_sha256=hashlib.sha256(marshal.dumps(f.__code__)).hexdigest())
def code_value(c):
    if isinstance(c,types.CodeType):
        return dict(type='code',argcount=c.co_argcount,posonlyargcount=c.co_posonlyargcount,kwonlyargcount=c.co_kwonlyargcount,nlocals=c.co_nlocals,stacksize=c.co_stacksize,flags=c.co_flags,bytecode=c.co_code.hex(),consts=[code_value(v) for v in c.co_consts],names=list(c.co_names),varnames=list(c.co_varnames),filename=c.co_filename,name=c.co_name,qualname=c.co_qualname,firstlineno=c.co_firstlineno,linetable=c.co_linetable.hex(),exceptiontable=c.co_exceptiontable.hex(),freevars=list(c.co_freevars),cellvars=list(c.co_cellvars))
    if isinstance(c,tuple):return ['tuple',[code_value(x) for x in c]]
    if isinstance(c,frozenset):return ['frozenset',sorted([code_value(x) for x in c],key=lambda x:json.dumps(x,sort_keys=True))]
    if type(c) is bytes:return ['bytes',c.hex()]
    if type(c) is float:return ['float',c.hex()]
    if type(c) is complex:return ['complex',c.real.hex(),c.imag.hex()]
    if c is Ellipsis:return ['ellipsis']
    if c is None or type(c) in (bool,int,str):return [type(c).__name__,c]
    raise TypeError(type(c))
def stable(f):
    raw=json.dumps(code_value(f.__code__),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return dict(function_id=id(f),code_id=id(f.__code__),structural_sha256=hashlib.sha256(raw).hexdigest())
def main():
    assert not OUT.exists()
    original=DRIVER.read_bytes();assert hashlib.sha256(original).hexdigest()=='ba14bf81489e6e99059a7ab21089f517c8c2ac4af51f1c8650d7d6321203c159'
    # Compile the complete original module, but execute no imports/module body.
    compiled=compile(original,str(DRIVER),'exec')
    codes={c.co_name:c for c in compiled.co_consts if isinstance(c,types.CodeType) and c.co_name in PROTECTED}
    ns={'json':json,'Path':Path,'__file__':str(DRIVER),'bind':lambda p:{'path':str(p)},'sys':sys}
    functions={name:types.FunctionType(codes[name],ns,name) for name in PROTECTED};ns.update(functions)
    evidence=[]
    # A constant referenced by a returned object can change marshal reference flags.
    mini={};exec("def literal():\n    return 'This is a deliberately non-interned literal with spaces.'\n",mini)
    f=mini['literal'];before=old(f);s0=stable(f);held=f();after=old(f);s1=stable(f)
    evidence.append(dict(test='returned_constant_reference',before=before,after=after,stable_equal=s0==s1,return_value_held=True))
    # Exact original code, deliberately retain a code constant without invoking native.
    f=functions['native'];before=old(f);s0=stable(f)
    held_native=[v for v in f.__code__.co_consts if type(v) is str]
    after=old(f);s1=stable(f)
    evidence.append(dict(test='exact_native_constants_retained_no_native_call',before=before,after=after,stable_equal=s0==s1,retained_count=len(held_native)))
    del held_native
    # Pure actual original helpers are exercised; no model, epoch or source-loader imports.
    specs={'profiles':[{'candidate_id':'C065','asr_tap':'O0','identity_tap':'O0'}]}
    g={'manifest':{'path':'fixture'},'case_id':None,'gallery_condition':'FIXED_ROTATION_A','enrollment_tier':15}
    operations={'choose_profile':lambda:functions['choose_profile'](specs,'C065','O0','O0'),
      'fixed_gallery_row':lambda:functions['fixed_gallery_row']({'rows':[g]},g['manifest'],g),
      'record_sample':lambda:functions['record_sample'](io.StringIO(),{'field':'fixture'}),
      'source_bindings':lambda:functions['source_bindings']()}
    for name,action in operations.items():
        f=functions[name];b=old(f);s0=stable(f)
        for _ in range(64):action()
        a=old(f);s1=stable(f)
        evidence.append(dict(test='exact_pure_helper_64_calls',name=name,before=b,after=a,stable_equal=s0==s1))
    # Retain each constant type singly to expose exactly which serialization is ref-sensitive.
    retained=[]
    for name,f in functions.items():
        for i in range(len(f.__code__.co_consts)):
            b=old(f)
            value=f.__code__.co_consts[i]
            a=old(f)
            if b!=a:retained.append(dict(name=name,constant_index=i,constant_type=type(value).__name__,before=b,after=a))
            del value
    # Deliberate replacement remains detectable with the proposed structural+identity record.
    f=functions['record_sample'];s0=stable(f);saved_code=f.__code__
    f.__code__=f.__code__.replace()
    same_values_new_code=stable(f)
    f.__code__=saved_code
    replacement=types.FunctionType(f.__code__,f.__globals__,f.__name__)
    negative=dict(equal_value_new_code_identity_rejected=same_values_new_code!=s0,new_function_same_code_rejected=stable(replacement)!=s0,restored=s0==stable(f))
    assert all(x['stable_equal'] for x in evidence)
    assert all(negative.values())
    assert evidence[0]['before']['marshal_sha256']!=evidence[0]['after']['marshal_sha256']
    assert evidence[1]['before']['marshal_sha256']!=evidence[1]['after']['marshal_sha256']
    job=REPORT/'paced_candidates/c065_main_fast_v1/jobs/C065_S45_01_16_O0_O0_r1'
    outcome=json.loads((job/'CELL_OUTCOME.json').read_bytes());native_path=Path(outcome['native_result']['path']);native=json.loads(native_path.read_bytes())
    assert bind(native_path)==outcome['native_result']
    result=dict(schema='s6c-protected-marshal-diagnosis.v1',status='PROVEN_REFERENCE_SENSITIVE_FINGERPRINT',python=sys.version,executable=sys.executable,sources=[bind(DRIVER),bind(L),bind(__file__),bind(Path(__file__).with_name('README_S6C_PROTECTED_HASH_DIAGNOSIS_V1.md'))],actual_failure=[bind(job/'WORKER_LOG.txt'),bind(job/'CELL_OUTCOME.json'),bind(native_path)],actual_native_status=native['status'],actual_outer_status=outcome['status'],actual_per_function_before_after_fingerprints_logged=False,evidence=evidence,singly_retained_constant_differences=retained,negative_controls=negative,conclusion='Existing marshal.dumps fingerprint is reference-sensitive even with identical function/code identities and immutable structural code. Exact original native code reproduces this without execution. Actual failed worker logs only a compound inequality, so the exact changed helper/constant and exclusion of another simultaneous mutation cannot be established retrospectively. Preserve native COMPLETE under outer FAILED. Proposed future wrapper records stable structural code plus same-process function and code identities, with exact original source binding.',native_calls=0,models=0,original_module_imports=0,source_reads='Only listed source files and three compact actual failed-attempt artifacts; no event/PCM/model reads.')
    OUT.mkdir(parents=True)
    p=OUT/'DIAGNOSIS.json';p.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(bind(p)));print(json.dumps({'tests':evidence,'negative_controls':negative}))
if __name__=='__main__':main()

