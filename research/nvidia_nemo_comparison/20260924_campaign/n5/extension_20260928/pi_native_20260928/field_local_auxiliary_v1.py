"""Pinned auxiliary module graph; README_FIELD_LOCAL_BOOTSTRAP_V1.md."""
import ast
import builtins
import hashlib
import json
import re
import sys
import types

STDLIB=frozenset(('os','sys','json','hashlib','resource','signal','fcntl','time',
 'subprocess','shutil','re','pathlib','datetime','struct','contextlib','stat',
 'msvcrt','copy','math'))
ENTRY='field_local_manager_export_v2'

def strict_json(raw):
    if type(raw) is not bytes or not 0<len(raw)<=262144:
        raise ValueError('Original framed request ceiling')
    def pairs(rows):
        out={}
        for k,v in rows:
            if k in out:raise ValueError('Duplicate JSON key')
            out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda s:(_ for _ in ()).throw(ValueError(s)))

def analyze(modules,pins,entry=ENTRY):
    if type(modules) is not dict or not 1<=len(modules)<=64 or type(pins) is not dict:
        raise ValueError('Original auxiliary module cardinality')
    if set(modules)!=set(pins) or entry not in modules:
        raise ValueError('Exact supplied graph pins/entry')
    aliases=set();total=0;trees={}
    for name,source in modules.items():
        if type(name) is not str or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',name) or name in STDLIB or name.casefold() in aliases:
            raise ValueError('Unique non-stdlib module name')
        aliases.add(name.casefold())
        if type(source) is not str:raise ValueError('Text module source')
        raw=source.encode();total+=len(raw)
        if not 0<len(raw)<=131072 or hashlib.sha256(raw).hexdigest()!=pins[name]:
            raise ValueError('Exact bounded source bytes')
        trees[name]=ast.parse(source,filename=name)
    if total>2097152:raise ValueError('Original auxiliary aggregate')
    graph={};top={}
    def imports(node):
        if isinstance(node,ast.ImportFrom):
            if node.level or not node.module:raise ValueError('No relative import')
            names=[node.module]
        else:names=[x.name for x in node.names]
        for name in names:
            if '.' in name or name not in STDLIB and name not in modules:
                raise ValueError('Every transitive import must be supplied or listed stdlib')
        return {name for name in names if name in modules}
    for name,tree in trees.items():
        dependencies=set();early=set()
        for node in ast.walk(tree):
            if isinstance(node,(ast.Import,ast.ImportFrom)):dependencies.update(imports(node))
            if isinstance(node,ast.Call):
                f=node.func
                if isinstance(f,ast.Name) and f.id in ('__import__','eval','exec','compile'):
                    raise ValueError('No dynamic code/import in admitted auxiliary modules')
        for node in tree.body:
            if isinstance(node,(ast.Import,ast.ImportFrom)):early.update(imports(node))
        graph[name]=dependencies;top[name]=early
    reached=set()
    def visit(name):
        if name in reached:return
        reached.add(name)
        for dep in graph[name]:visit(dep)
    visit(entry)
    if reached!=set(modules):raise ValueError('No extra unreachable module')
    order=[];visiting=set()
    def sorted_visit(name):
        if name in order:return
        if name in visiting:raise ValueError('Top-level import cycle')
        visiting.add(name)
        for dep in sorted(top[name]):sorted_visit(dep)
        visiting.remove(name);order.append(name)
    for name in sorted(modules):sorted_visit(name)
    return dict(entry=entry,modules=len(modules),bytes=total,order=order,
                dependencies={n:sorted(v) for n,v in graph.items()})

def install(modules,pins,entry=ENTRY):
    """Cooperative origin/import binding, not a sandbox for untrusted source."""
    result=analyze(modules,pins,entry)
    if any(n in sys.modules for n in modules):raise ValueError('Preloaded project module collision')
    original=builtins.__import__;created=[]
    def bound_import(name,globals=None,locals=None,fromlist=(),level=0):
        if level or name not in STDLIB and name not in modules:
            raise ImportError('Import outside the verified auxiliary graph')
        return original(name,globals,locals,fromlist,level)
    try:
        for name in result['order']:
            module=types.ModuleType(name)
            module.__file__='<manager-export-injected:'+name+'>'
            module.__builtins__=dict(vars(builtins),__import__=bound_import)
            sys.modules[name]=module;created.append(name)
            exec(compile(modules[name],module.__file__,'exec'),module.__dict__)
        return sys.modules[entry],result
    except BaseException:
        for name in created:sys.modules.pop(name,None)
        raise

