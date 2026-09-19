"""Independent V6 source and metadata review; README_S6C_INVENTORY_V6_REVIEW_V1.md."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import argparse,ast,hashlib,importlib.util,json,tempfile,types,__future__
import s6c_execution_inventory_v6 as A
import test_s6c_execution_inventory_v6 as T
PIN='9109a38c9f62ad6aca11a4e60ef57eb9e8712bb43dde10b08d485d03a068921f'
def bind(p):p=Path(p).resolve();return A.base.binding(p,p.read_bytes())
def sig(code):
    def value(x):
        if isinstance(x,types.CodeType):return sig(x)
        if isinstance(x,tuple):return tuple(value(v) for v in x)
        return x
    return (code.co_code,code.co_names,code.co_varnames,tuple(value(v) for v in code.co_consts),code.co_argcount,code.co_kwonlyargcount,code.co_freevars,code.co_cellvars,code.co_flags)
def main(output):
    assert bind(A.__file__)['sha256']==PIN
    checks=[]
    def ok(name,value):assert value,name;checks.append(name)
    before=A.source_bindings()
    held,hb=A.v4.bound(type('R',(),{'read':lambda self,p,b=None:(json.loads(Path(p).read_bytes()),bind(p))})(),bind(A.REPORT/'execution_inventory/ADAPTER_V6_CHECKS_V3.json'))
    for b in held['sources']+[held['test']]:ok('source '+Path(b['path']).name,bind(b['path'])==b)
    # Independently rebuild every public adapted function from V4 with the three allowed literals.
    original={n.name:n for n in ast.parse(Path(A.v4.__file__).read_bytes()).body if isinstance(n,ast.FunctionDef)}
    replacements={'s6c_paced_epoch4.py':'s6c_paced_cross_routes_v1.py','s6c-canonical-paced-cell-result.v1':'s6c-cross-route-paced-cell-result.v1','paced_candidates':'paced_cross_routes'}
    class Replace(ast.NodeTransformer):
        def visit_Constant(self,node):
            if isinstance(node.value,str) and node.value in replacements:return ast.copy_location(ast.Constant(replacements[node.value]),node)
            return node
    for name in sorted(A.NAMES):
        node=Replace().visit(deepcopy(original[name]));ns={}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'<independent literal-only>','exec',flags=__future__.annotations.compiler_flag,dont_inherit=True),ns)
        ok('exact V4 literal-only function '+name,sig(ns[name].__code__)==sig(getattr(A.X,name).__code__))
    coordinator=ast.parse((A.HERE/'s6c_paced_cross_routes_v1.py').read_bytes())
    for name in ('candidate_routes','selected_panel','grid'):
        node=next(n for n in coordinator.body if isinstance(n,ast.FunctionDef) and n.name==name);ns={}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<independent exact selection>','exec',flags=__future__.annotations.compiler_flag,dont_inherit=True),ns)
        ok('exact cross guard '+name,sig(ns[name].__code__)==sig(A.X.GUARDS[name].__code__))
    # Independently repeat the previously reproduced two-invocation counterexample.
    with patch.object(A.v3,'process_state',lambda *args:dict(alive=False,state='INDEPENDENT_SYNTHETIC_CLOSED')):
        for mode in ('launch_only','outcome_without_closure'):
            with tempfile.TemporaryDirectory(prefix='s6c_v6_review_') as d:
                root=Path(d);reader,j,p,pb,s,_=T.fixture(root);inv=root/'invocations/two';o=dict(pid=31337,creation_time=22.,argv=['synthetic-second-coordinator'])
                A.base.write_new(inv/'LAUNCH.json',dict(status='STARTED',owner=o,manifest=pb))
                if mode=='outcome_without_closure':
                    A.base.write_new(inv/'OUTCOME.json',dict(status='PARTIAL',owner=o,manifest=pb,requested=1,completed=0,rows=[],error='injected interruption',remaining_owned=[]))
                records,owners=A.invocation_rows(reader,p,pb)
                ok(mode+' retains unknown owner',any(x['process_state']['alive'] is None for x in owners))
                try:A.admit_complete_cell(reader,j,p,pb,s,state=lambda *args:dict(alive=False))
                except ValueError:checks.append(mode+' rejects completed-cell global closure')
                else:raise AssertionError('Earlier-good/later-unclosed admitted')
    # Same panel proof but no actual native MANIFEST, cell, log or source payload.
    with tempfile.TemporaryDirectory(prefix='s6c_v6_review_metadata_') as d:
        root=Path(d);(root/'snap').mkdir();reader=A.base.MetadataReader(root/'snap')
        spec,sb=reader.read(A.REPORT/'EPOCH4_EXECUTION_MANIFEST.json')
        panel,pb=reader.read(A.REPORT/'design/confirmation_plan_v1/PACED_PANEL_PROPOSAL_V1.json')
        ok('exact epoch4',sb['sha256']=='720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945')
        ok('exact16 plus4 panel',pb['sha256']=='f303d7e80bc9dd8fa8b7ba7444216d1e6b29f75a0cce8762c40d92ce5201c6da')
        routes=A.X.GUARDS['candidate_routes'](spec,['C085','C086'])
        selected=A.X.GUARDS['selected_panel'](panel,'cross16_plus4',['C085','C086'])
        grid=A.X.GUARDS['grid'](['C085','C086'],selected)
        ok('exact40 unique keys',len(grid)==len(set(grid))==40)
        ok('32 base8 repeated',sum(x[-1]==1 for x in grid)==32 and sum(x[-1]==2 for x in grid)==8)
        for (cid,tap),row in routes.items():
            ok(cid+' exact asymmetric route',(tap,row['identity_tap'])==({'C085':('O0','O1'),'C086':('O1','O0')}[cid]))
        ok('canonical V4 source and schema remain unchanged',A.v4.CANONICAL=='s6c-canonical-paired-paced.v1' and bind(A.v4.__file__)['sha256']=='426a4eaada68e51d0e6af6decd8b9b56fa3c9660b3cca005f959862c03177876')
    # Execute the owner's complete 62-check source/metadata suite in a fresh receipt only.
    inherited=output.with_name(output.stem+'_REPRODUCED_FIXTURES.json')
    T.main(inherited);fixture_receipt=json.loads(inherited.read_bytes())
    ok('62 owner checks independently reproduced',fixture_receipt['checks']==62)
    ok('source unchanged after checks',A.source_bindings()==before)
    return A.base.write_new(output,dict(status='PASS_SOURCE_METADATA_REVIEW',check_count=len(checks),checks=checks,
        reproduced_fixture_receipt=bind(inherited),source_bindings=before,owner_receipt=hb,
        finding=bind(A.REPORT/'independent_review/INVENTORY_V6_MISSING_CLOSURE_FINDING_V1.json'),
        review_source=bind(__file__),review_readme=bind(A.HERE/'README_S6C_INVENTORY_V6_REVIEW_V1.md'),
        models=0,actual_native_manifests_prepared=0,actual_inventory_collection=False,actual_native_payloads_read=0,
        scope='Source/isolated metadata only. Nine literal-only adapted V4 functions and three exact cross grid guards reproduce; successful Popen/known-launch dedup, missing/failed completion and released/current owner semantics validated. Earlier missing-invocation-closure finding resolved. Declaration hashes do not freshly verify native payload bytes or authorize a native run.'))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(main(a.output)))
