"""Reuse installed backend/controller/gallery bindings; README_RUNTIME_CONTROLLER_PROFILE_V1.md."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path,PurePosixPath
import stat
import textwrap

from field_runtime_profiles_v1 import backend_manifest as profile_definition, digest as profile_digest, TITANET_MODEL, REDIMNET, TITANET_PREPROCESSING, TITANET_ONNX, TITANET_FRONTEND


def selected_backend(catalog_raw, definition):
    """Recompute the actual composition from the pinned original catalogue."""
    if type(definition) is not dict or type(definition.get('selection')) is not dict:
        raise ValueError('Explicit prepared profile definition')
    expected=profile_definition(catalog_raw,definition['selection']['profile'])
    if profile_digest(expected)!=profile_digest(definition):
        raise ValueError('Profile differs from existing model/runtime implementation')
    rows=json.loads(catalog_raw)['backends']
    original=next(r for r in rows if r['key']==definition['selection']['backend_key'])
    if original['implemented'] is not True:
        raise ValueError('Original backend implementation is unavailable')
    selected=deepcopy(original)
    selected.update(key=definition['selection']['profile'],label=definition['label'],
                    manifest_id=definition['backend_manifest_id'],composition=deepcopy(definition['composition']))
    return selected


def bind_registry(module,catalog_raw,definition):
    """Fresh-process in-memory selection; original catalogue files stay unchanged."""
    selected=selected_backend(catalog_raw,definition)
    original=json.loads(catalog_raw)['backends']
    if module._BACKENDS!=original:
        raise ValueError('Previously changed backend registry')
    if module.manifest_id(selected['composition'])!=selected['manifest_id']:
        raise ValueError('Actual installed backend ID convention differs')
    rows=deepcopy(original)
    matches=[i for i,row in enumerate(rows) if row['manifest_id']==selected['manifest_id']]
    if len(matches)>1:raise ValueError('Duplicate actual backend identity')
    if matches:rows[matches[0]]=selected
    else:rows.append(selected)
    module._BACKENDS=rows
    actual=module.require_backend(selected['manifest_id'],definition['selection']['ui_mode'],'O0')
    if actual['composition']!=selected['composition']:
        raise ValueError('Actual registry consumer returned another implementation')
    return selected['manifest_id']


def specialize_factory(node,definition):
    """Retain installed Field methods, changing only the explicit profile selectors."""
    if not isinstance(node,ast.FunctionDef) or node.name!='controller_type':
        raise ValueError('Actual derived Field controller factory required')
    node=deepcopy(node);before=deepcopy(node)
    supported=[n for n in node.body if isinstance(n,ast.Assign) and len(n.targets)==1
               and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='supported']
    if len(supported)!=1 or "nemotron_hybrid" not in ast.unparse(supported[0].value):
        raise ValueError('Installed backend selector boundary changed')
    supported[0].value=ast.Constant(definition['backend_manifest_id'])
    cls=next(n for n in node.body if isinstance(n,ast.ClassDef) and n.name=='FieldController')
    methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
    switch=methods['_do_switch'];text=ast.unparse(switch)
    old="('open_with_names', 'balanced', 'O0')"
    if text.count(old)!=1:raise ValueError('Installed mode/tap guard changed')
    new=repr((definition['selection']['ui_mode'],'balanced','O0'))
    replacement=ast.parse(text.replace(old,new).replace(
        'This candidate supports Open with names, Balanced and O0. Spatial and other recipes are unavailable.',
        'This shortcut pins its logical mode, Balanced and O0. Return to modes to select another profile.')).body[0]
    cls.body[cls.body.index(switch)]=replacement
    selector=methods['_do_select_backend']
    for n in ast.walk(selector):
        if isinstance(n,ast.Constant) and n.value=='This candidate supports B01. Other backends need a separately qualified launcher.':
            n.value='This process is pinned to its selected backend and embedding model. Return to modes to change it.'
    snapshot=methods['snapshot'];labels=[n for n in ast.walk(snapshot) if isinstance(n,ast.Constant) and n.value=='B01: Sherpa + Nemotron']
    if len(labels)!=1:raise ValueError('Installed backend display boundary changed')
    labels[0].value=definition['label']
    old_cls=next(n for n in before.body if isinstance(n,ast.ClassDef) and n.name=='FieldController')
    changed={'_do_switch','_do_select_backend','snapshot'}
    bodies=lambda c:{n.name:ast.dump(n,include_attributes=False) for n in c.body if isinstance(n,ast.FunctionDef) and n.name not in changed}
    if bodies(old_cls)!=bodies(cls):raise ValueError('Unrelated installed Field method changed')
    return ast.fix_missing_locations(node)


def verify_gallery(root,manifest_raw,manifest_sha256,namespace,guard):
    """Read an independently reserved immutable gallery snapshot; never convert vectors."""
    if type(manifest_raw) is not bytes or len(manifest_raw)>65536 or hashlib.sha256(manifest_raw).hexdigest()!=manifest_sha256:
        raise ValueError('Pinned bounded gallery snapshot manifest')
    document=json.loads(manifest_raw)
    if set(document)!={'schema','namespace','files','directories','reserved_bytes'} or document['schema']!='just-peachy.runtime-gallery-snapshot.v1':
        raise ValueError('Exact gallery snapshot')
    if document['namespace']!=namespace:
        raise ValueError('Gallery belongs to a different embedding/preprocessing space')
    root=Path(root).absolute()
    for parent in (root,*root.parents):
        s=parent.lstat()
        if not stat.S_ISDIR(s.st_mode) or stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&0x400:
            raise ValueError('Real gallery snapshot path')
    files=document['files'];dirs=document['directories']
    if type(files) is not dict or len(files)>256 or type(dirs) is not list or not 1<=len(dirs)<=64 or '' not in dirs or len(set(dirs))!=len(dirs):
        raise ValueError('Finite gallery member/directory allocation')
    if type(document['reserved_bytes']) is not int or not 0<document['reserved_bytes']<=134217728:
        raise ValueError('Explicit independent gallery reservation')
    aliases=set()
    for name in list(files)+[n for n in dirs if n]:
        path=PurePosixPath(name)
        if type(name) is not str or str(path)!=name or path.is_absolute() or any(p in ('.','..') for p in path.parts) or ':' in name or '\\' in name or name.casefold() in aliases:
            raise ValueError('Portable unique gallery member')
        aliases.add(name.casefold())
        parent=path.parent.as_posix()
        if ('' if parent=='.' else parent) not in dirs:raise ValueError('Complete gallery parents')
    actual_files=set();actual_dirs={''};before={}
    for p in root.rglob('*'):
        guard();rel=p.relative_to(root).as_posix();s=p.lstat()
        if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&0x400:raise ValueError('Gallery link')
        if stat.S_ISDIR(s.st_mode):actual_dirs.add(rel)
        elif stat.S_ISREG(s.st_mode) and s.st_nlink==1:
            actual_files.add(rel);before[rel]=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
        else:raise ValueError('Real gallery member')
        if len(actual_files)>256 or len(actual_dirs)>64:raise ValueError('Actual gallery cardinality')
    if actual_files!=set(files) or actual_dirs!=set(dirs):raise ValueError('Complete pinned gallery membership')
    total=len(dirs)*65536
    for name,row in files.items():
        if type(row) is not dict or set(row)!={'bytes','sha256'} or type(row['bytes']) is not int or not 0<=row['bytes']<=33554432 or before[name][2]!=row['bytes']:
            raise ValueError('Exact bounded gallery member')
        total+=row['bytes']
        if total>document['reserved_bytes']:raise ValueError('Independent gallery allocation exhausted')
        h=hashlib.sha256()
        with (root/name).open('rb') as stream:
            while True:
                guard();block=stream.read(16384)
                if not block:break
                h.update(block)
        s=(root/name).lstat()
        if h.hexdigest()!=row['sha256'] or before[name]!=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns):
            raise ValueError('Gallery changed during verification')
    after_files=set();after_dirs={''}
    for p in root.rglob('*'):
        guard();(after_dirs if p.is_dir() else after_files).add(p.relative_to(root).as_posix())
    if after_files!=actual_files or after_dirs!=actual_dirs:raise ValueError('Gallery membership changed')
    return root


def readonly_store_type(people_module,data_root,galleries,namespace,guard):
    """Reuse the original initializer and TitaNet subclass; redirect only verified roots."""
    expected={'E0':dict(model_sha256=REDIMNET,preprocessing='mono-float32-16k-redimnet2-native-l2-v1',dimension=192,normalization='L2',minimum_samples=8000)}
    if namespace is not None:
        exact=dict(model_sha256=TITANET_MODEL,preprocessing=TITANET_PREPROCESSING,dimension=192,normalization='L2',minimum_samples=8000,onnx_sha256=TITANET_ONNX,frontend_sha256=TITANET_FRONTEND)
        if namespace!=exact:raise ValueError('Original TitaNet namespace required')
        expected['E1']=exact
    if type(galleries) is not dict or set(galleries)!=set(expected):
        raise ValueError('Separate exact required gallery namespaces')
    roots={}
    for key,descriptor in galleries.items():
        if type(descriptor) is not dict or set(descriptor)!={'root','manifest_path','manifest_sha256'}:
            raise ValueError('Pinned independent gallery descriptor')
        path=Path(descriptor['manifest_path']);info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>65536 or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('Bounded real gallery manifest')
        roots[key]=verify_gallery(descriptor['root'],path.read_bytes(),descriptor['manifest_sha256'],expected[key],guard)
    if len(set(roots.values()))!=len(roots):raise ValueError('Distinct gallery snapshot paths')
    data=Path(data_root).absolute()
    namespace_key=None if namespace is None else profile_digest(namespace)
    original=people_module.PersonalStore
    source=Path(people_module.__file__).read_bytes()
    cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='PersonalStore')
    node=deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__'))
    if ast.unparse(node.body[0])!='self.root = Path(root).resolve()' or ast.unparse(node.body[1])!='self.root.mkdir(parents=True, exist_ok=True)':
        raise ValueError('Actual PersonalStore constructor boundary changed')
    node.body[0]=ast.parse('self.root = _runtime_gallery_root(root, backend, self.preprocessing)').body[0]
    del node.body[1]
    def mapped(root,backend,preprocessing):
        requested=Path(root).absolute()
        if backend==REDIMNET and preprocessing==people_module.PREPROCESSING and requested==data/'people':
            return roots['E0']
        if (namespace_key is not None and backend==TITANET_MODEL and preprocessing=='titanet:'+namespace_key
                and requested==data/'embedding_spaces'/namespace_key/'people'):
            return roots['E1']
        raise ValueError('No cross-encoder root or preprocessing fallback')
    namespace_globals=dict(people_module.__dict__,_runtime_gallery_root=mapped)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),
                 str(people_module.__file__)+':readonly-gallery', 'exec'),namespace_globals)
    class ReadOnlyStore(original):
        __init__=namespace_globals['__init__']
    return ReadOnlyStore

