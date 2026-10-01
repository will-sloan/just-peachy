"""Changed host-only auxiliary checks; README_FIELD_LOCAL_BOOTSTRAP_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,hashlib,io,json,sys,time,types
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(exist_ok=False)
    me=psutil.Process()
    owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    (args.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(owner))
    sys.dont_write_bytecode=True
    from field_local_auxiliary_v1 import analyze,install,strict_json,STDLIB,ENTRY
    from field_local_manager_ssh_mirror_v1 import receive_json
    from field_host_budget_v1 import HostBudgetError
    here=Path(__file__).absolute().parent;modules={}
    def collect(name):
        if name in modules:return
        raw=(here/(name+'.py')).read_bytes();modules[name]=raw.decode()
        for node in ast.walk(ast.parse(raw)):
            names=[x.name for x in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) else []
            for dep in names:
                if dep not in STDLIB:collect(dep)
    collect(ENTRY)
    pins=lambda rows:{n:hashlib.sha256(s.encode()).hexdigest() for n,s in rows.items()}
    review=analyze(modules,pins(modules))
    for name,source in modules.items():compile(source,name,'exec')
    synthetic={'fixture_dep':'VALUE=7\n','fixture_entry':'from fixture_dep import VALUE\nRESULT=VALUE+1\n'}
    entry,_=install(synthetic,pins(synthetic),'fixture_entry');assert entry.RESULT==8
    for name in synthetic:
        assert sys.modules[name].__file__=='<manager-export-injected:'+name+'>'
    rejected=[]
    def reject(label,call):
        try:call()
        except (ValueError,TypeError,ImportError,KeyError,SyntaxError,HostBudgetError):rejected.append(label)
        else:raise AssertionError('Expected rejection: '+label)
    reject('preloaded-collision',lambda:install(synthetic,pins(synthetic),'fixture_entry'))
    for name in synthetic:sys.modules.pop(name)
    def variant(label,rows,entry='fixture_entry',bound=None):
        reject(label,lambda:analyze(rows,pins(rows) if bound is None else bound,entry))
    variant('missing-transitive',{'fixture_entry':'from absent_project import VALUE\n'})
    variant('missing-late-transitive',{'fixture_entry':'def f():\n import absent_project\n'})
    variant('relative-import',{'fixture_entry':'from . import missing\n'})
    variant('dynamic-import',{'fixture_entry':"__import__('os')\n"})
    variant('dynamic-exec',{'fixture_entry':"exec('x=1')\n"})
    variant('stdlib-shadow',{'json':'x=1','fixture_entry':'import json\n'})
    variant('case-alias',{'fixture_entry':'import a,A\n','a':'x=1','A':'x=2'})
    variant('source-pin-drift',synthetic,bound={n:'0'*64 for n in synthetic})
    variant('unused-member',{**synthetic,'unused':'x=1'})
    variant('top-level-cycle',{'fixture_entry':'import fixture_dep\n','fixture_dep':'import fixture_entry\n'})
    variant('oversized-source',{'fixture_entry':'#'+'x'*131072})
    variant('nontext-source',{'fixture_entry':True},bound={'fixture_entry':'0'*64})
    reject('duplicate-json',lambda:strict_json(b'{"a":1,"a":2}'))
    reject('oversized-payload',lambda:strict_json(b' '*262145))
    # Execute ONLY the actual nested serialization helper, not native run/imports.
    def framer(version):
        tree=ast.parse((here/('field_local_manager_export_'+version+'.py')).read_bytes())
        run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        frame=next(n for n in run.body if isinstance(n,ast.FunctionDef) and n.name=='frame')
        output=io.BytesIO()
        import struct
        namespace={'sys':types.SimpleNamespace(stdout=types.SimpleNamespace(buffer=output)),'json':json,'struct':struct}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[frame],type_ignores=[])),'actual-frame-only','exec'),namespace)
        return namespace['frame'],output
    f,out=framer('v2');expected={'type':'HELLO','owner':{'pid':17,'start_ticks':23,'boot_id':'fixture'}}
    f(expected);assert receive_json(io.BytesIO(out.getvalue()),time.monotonic()+2)==expected
    old,out=framer('v1');old(expected)
    reject('old-ascii-frame',lambda:receive_json(io.BytesIO(out.getvalue()),time.monotonic()+2))
    reject('new-frame-overflow',lambda:f({'blob':'x'*262144}))
    bootstrap=ast.parse((here/'field_local_manager_bootstrap_v1.py').read_bytes())
    body=next(n for n in bootstrap.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    write=next(n.lineno for n in ast.walk(body) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='write')
    execute=min(n.lineno for n in ast.walk(body) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='exec')
    assert write<execute
    result=dict(status='PASS_CHANGED_HOST_AUXILIARY_GRAPH_AND_BINARY_FRAMING',positive_groups=3,
        actual_graph=review,module_sha256=pins(modules),synthetic_install=True,
        actual_nested_frame_receiver=True,rejected=rejected,native_bootstrap_executed=False,
        ssh_attempts=0,native_or_app_success=False,owner=owner)
    (args.output/'RESULT.json').open('x').write(json.dumps(result,indent=2))
    print(json.dumps(dict(status=result['status'],modules=review['modules'],bytes=review['bytes'],rejects=len(rejected))))
if __name__=='__main__':main()

