"""Source-only sentinel/cross fast_v2 checks; README_S6C_SENTINEL_CROSS_GUARD_V2.md."""
import ast,hashlib,importlib,json
from copy import deepcopy
from pathlib import Path
import s6c_paced_epoch4_fast_v2 as C
BEFORE={k:id(v) for k,v in vars(C).items()}
import s6c_paced_arrival_sentinel_fast_v2 as S
import s6c_paced_cross_routes_fast_v2 as X
L=C.L;HERE=Path(__file__).resolve().parent
OUT=L.REPORT/'observer_fast_v2/SENTINEL_CROSS_GUARD_CHECKS_V1.json'
CHECKS=[]
def ck(name,v):
    if not v:raise AssertionError(name)
    CHECKS.append(name)
def reject(name,fn):
    try:fn()
    except (ValueError,KeyError):CHECKS.append(name);return
    raise AssertionError(name)
def funcs(name):return {n.name:n for n in ast.parse((HERE/name).read_bytes()).body if isinstance(n,ast.FunctionDef)}
def dump(node):return ast.dump(node,include_attributes=False)
class Versions(ast.NodeTransformer):
    def visit_alias(self,n):
        n.name=n.name.replace('_fast_v2','_fast_v1')
        return n
    def visit_Constant(self,n):
        if isinstance(n.value,str):n.value=n.value.replace('_fast_v2','_fast_v1').replace('_FAST_V2','_FAST_V1')
        return n
def normal(n):return dump(Versions().visit(deepcopy(n)))
def main():
    ck('fresh result',not OUT.exists())
    pins={'s6c_long_native_epoch4_fast_v2.py':'079642ba24d59f625a6ae0c4342d9a26f51e56221f29b5a50f54830adfa22d67','s6c_paced_epoch4_fast_v2.py':'a8776724003fa2a642575892327b7c3e88eaddf29606881b302b05157c12b270','s6c_paced_arrival_sentinel_fast_v1.py':'63a26b59729e1ed0bd248f459de057b47bf3384b00b0dc1db5b4812a92838a57','s6c_paced_cross_routes_fast_v1.py':'b7552b44a8e24a6387969fb1a08d16bf3e7eded5ddd728e4bdb1181d2274f1ea','s6c_long_b36_v1.py':'09b809f6301e696054c4563fdad0d48072ae22716bafcf9002a33bdffd866c66'}
    for name,sha in pins.items():ck('exact held source '+name,L.bind(HERE/name)['sha256']==sha)
    ck('canonical module globals unchanged',BEFORE=={k:id(v) for k,v in vars(C).items()})
    a,b=funcs('s6c_paced_arrival_sentinel_fast_v1.py'),funcs('s6c_paced_arrival_sentinel_fast_v2.py')
    changes=[n for n in a if normal(a[n])!=normal(b[n])]
    ck('sentinel only required guard/quiet deltas',set(changes)=={'load_native','prepare','admit','quiet'})
    for n in ('worker','run','grid','selected_panel','candidate_routes','source_record','verify_pcm'):
        ck('sentinel scientific/native AST unchanged '+n,dump(a[n])==dump(b[n]))
    cb=funcs('s6c_paced_epoch4_fast_v2.py')
    ck('sentinel validates original driver exactly like C2',dump(b['load_native'])==dump(cb['load_native']))
    policy=L.protected_guard_policy()
    guard=next(n for n in b['admit'].body if isinstance(n,ast.If) and 'protected_guard_policy' in ast.unparse(n.test))
    for value in (None,dict(policy,schema='wrong')):
        ns=dict(vars(S),plan={'protected_guard_policy':value})
        reject('sentinel missing/changed policy rejected',lambda:exec(compile(ast.Module(body=[guard],type_ignores=[]),'<sentinel policy>','exec'),ns))
    ns=dict(vars(S),plan={'protected_guard_policy':policy})
    exec(compile(ast.Module(body=[guard],type_ignores=[]),'<sentinel policy>','exec'),ns);ck('sentinel exact policy accepted',True)
    ck('sentinel prepare records policy',any(isinstance(n,ast.keyword) and n.arg=='protected_guard_policy' and ast.unparse(n.value)=='L.protected_guard_policy()' for n in ast.walk(b['prepare'])))
    sel={'case_ids':['S45_08_07'],'repeated_case_ids':['S45_08_07']}
    sg=S.grid(['C088','C105'],sel)
    ck('sentinel exact12 unique cells',len(sg)==len(set(sg))==12)
    ck('sentinel3repeats both taps matched pair',{x[0] for x in sg}=={'C088','C105'} and {x[2] for x in sg}=={'O0','O1'} and {x[3] for x in sg}=={1,2,3})
    reject('sentinel old namespace rejected',lambda:S.namespace_roots('arrival_fast_v1'))
    ck('sentinel new namespace accepted',S.namespace_roots('arrival_fast_v2')[0].name=='arrival_fast_v2')
    old,new=funcs('s6c_paced_cross_routes_fast_v1.py'),funcs('s6c_paced_cross_routes_fast_v2.py')
    xchanges=[n for n in old if normal(old[n])!=normal(new[n])]
    ck('cross only additive quiet literal delta after source references',xchanges==['compile_adapter'])
    for n in ('candidate_routes','selected_panel','grid','record_spawn'):
        ck('cross scientific/cleanup API unchanged '+n,dump(old[n])==dump(new[n]))
    ck('original D cleanup authority retained',X.D.__file__==str(HERE/'s6c_long_b36_v1.py') and X.PINS['s6c_long_b36_v1.py']==pins['s6c_long_b36_v1.py'])
    ck('cross private namespace differs',X.PRIVATE is not vars(C))
    ck('cross compiles held C2 source',"s6c_paced_epoch4_fast_v2.py" in ast.unparse(new['compile_adapter']))
    # Same exact inherited node plus only the already-reviewed schema/ownership literals.
    class Metadata(ast.NodeTransformer):
        def visit_Constant(self,n):
            if isinstance(n.value,str) and n.value in X.TEXT_REPLACEMENTS:n.value=X.TEXT_REPLACEMENTS[n.value]
            return n
    for name in ('worker','load_native','prepare','admit'):
        expected=Metadata().visit(deepcopy(cb[name]))
        ck('cross exact inherited guarded AST '+name,hashlib.sha256(dump(expected).encode()).hexdigest()==X.ADAPTATION['function_ast_sha256'][name])
    p={'case_ids':[str(i) for i in range(16)],'repeated_case_ids':[str(i) for i in range(4)]}
    xg=X.grid(X.PAIR,p)
    ck('cross40 unique actual routes',len(xg)==len(set(xg))==40 and {(x[0],x[2]) for x in xg}=={('C085','O0'),('C086','O1')})
    reject('cross old namespace refused',lambda:X.PRIVATE['namespace_roots']('cross_fast_v1'))
    ck('cross new namespace accepted',X.PRIVATE['namespace_roots']('cross_fast_v2')[0].name=='cross_fast_v2')
    required={'s6c_paced_epoch4.py','s6c_paced_arrival_sentinel_v1.py','s6c_paced_cross_routes_v1.py','s6c_paced_epoch4_fast_v1.py','s6c_paced_arrival_sentinel_fast_v1.py','s6c_paced_cross_routes_fast_v1.py','s6c_paced_epoch4_fast_v2.py','s6c_paced_arrival_sentinel_fast_v2.py','s6c_paced_cross_routes_fast_v2.py'}
    sentinel_names={n.value for n in ast.walk(b['quiet']) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
    ck('sentinel quiet original/v1/v2 union',required<=sentinel_names)
    ck('cross quiet original/v1/v2 union',all(n in ast.unparse(new['compile_adapter']) for n in required))
    ck('shared L2 scanner pin unchanged',S.L is X.L is C.L and L.FAST_SCAN_SHA=='579963cb5e873a0a08504bb4f022ea8a92a158886d36abfd87ee4a0f9cd6d299')
    files=list(pins)+['s6c_paced_arrival_sentinel_fast_v2.py','README_S6C_PACED_ARRIVAL_SENTINEL_FAST_V2.md','s6c_paced_cross_routes_fast_v2.py','README_S6C_PACED_CROSS_ROUTES_FAST_V2.md','test_s6c_sentinel_cross_guard_v2.py','README_S6C_SENTINEL_CROSS_GUARD_V2.md']
    result=dict(schema='s6c-sentinel-cross-guard-v2-review.v1',status='PASS_SOURCE_ONLY',created_utc=L.utc(),check_count=len(CHECKS),checks=CHECKS,
       sources=[L.bind(HERE/n) for n in files],sentinel_changed_functions=changes,cross_changed_functions=xchanges,guard_policy=policy,
       preserved_initial_reviewer=L.bind(L.STAGING/'observer_fast_v2/sentinel_cross_before_import_normalization/SOURCE_INDEX.json'),inherited_guard_review=L.bind(L.REPORT/'independent_review/guard_v2_component_v1/REVIEW_RECEIPT.json'),
       prior_variant_review=L.bind(L.REPORT/'observer_fast_v1/ROOT_VARIANT_DESIGN_REVIEW_V1.json'),
       scientific_scope=dict(sentinel12='C088/C105 fixedA15 off/real S45_08_07 both same taps,3repeats',cross40='C085 O0-ASR/O1-ID and C086 O1-ASR/O0-ID original16+repeat4'),
       deferred_preparation='prepare invokes original overlay asset hashing and selected PCM verification; do not run during quiet paced interval.',
       native_calls=0,models=0,pcm_reads=0,asset_reads=0,full_scans=0,preparations=0,
       scope='Source/AST, small synthetic grids and pure policy checks only; prior native/scanner/cleanup fixtures reused, no original source_checks or native loading.')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(L.bind(OUT)));print('PASS',len(CHECKS))
if __name__=='__main__':main()
