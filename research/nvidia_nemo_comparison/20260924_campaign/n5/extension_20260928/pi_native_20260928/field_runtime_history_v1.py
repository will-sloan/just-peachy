"""Read-only historical compact recordings; README_RUNTIME_HISTORY_V1.md."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager

_HISTORY_STATE = threading.local()
_HISTORY_AUDIT_INSTALLED = False
_HISTORY_CAPS = {'conversation.json':65536, 'epoch.json':65536,
    'events.jsonl':16777216, 'resources.jsonl':2097152, 'windows.jsonl':2097152,
    'model_input.f32le':8388608, 'model_input.wav':4194304}


def _history_audit(event, args):
    if not getattr(_HISTORY_STATE, 'reading', False): return
    if event == 'open':
        mode, flags = args[1:3]
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            raise PermissionError('History cannot open a writer')
    if event in {'os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink',
                 'os.chmod','os.chown','os.truncate','os.utime','sqlite3.connect','subprocess.Popen','os.system'}:
        raise PermissionError('History cannot mutate or launch')


@contextmanager
def history_reading():
    import sys
    global _HISTORY_AUDIT_INSTALLED
    if not _HISTORY_AUDIT_INSTALLED:
        sys.addaudithook(_history_audit); _HISTORY_AUDIT_INSTALLED = True
    if getattr(_HISTORY_STATE,'reading',False): raise RuntimeError('Nested history read')
    _HISTORY_STATE.reading = True
    try: yield
    finally: _HISTORY_STATE.reading = False


def history_bytes(path, maximum, deadline):
    if time.monotonic() >= deadline: raise TimeoutError('History read deadline')
    path = Path(path)
    for parent in (path.parent,*path.parents):
        if parent.is_symlink() or not parent.is_dir(): raise ValueError('Real history ancestors')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum:
        raise ValueError('History file bound or type')
    raw = path.read_bytes(); after = path.lstat()
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) != (
            after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or len(raw) != before.st_size:
        raise RuntimeError('History changed during read')
    return raw


def history_json(raw):
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result: raise ValueError('Duplicate history JSON key')
            result[key] = value
        return result
    def bad(value): raise ValueError('Nonfinite history JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


def history_census(folder, deadline):
    folder = Path(folder)
    result = {}; directories = []
    for base,names,files in os.walk(folder,followlinks=False):
        if time.monotonic() >= deadline: raise TimeoutError('History census deadline')
        parent=Path(base)
        if parent.is_symlink() or not parent.is_dir(): raise ValueError('Linked history folder')
        directories.append(parent.relative_to(folder).as_posix())
        if len(directories)>3: raise ValueError('One history epoch only')
        for name in names:
            path=parent/name
            if path.is_symlink() or not path.is_dir(): raise ValueError('Linked history child')
        for name in files:
            if name not in _HISTORY_CAPS: raise ValueError('Unknown history member')
            path=parent/name;relative=path.relative_to(folder).as_posix()
            if name=='conversation.json':
                if relative!=name: raise ValueError('History metadata location')
            elif not re.fullmatch(r'epochs/[0-9a-f]{32}/'+re.escape(name),relative):
                raise ValueError('History epoch path')
            before=path.lstat()
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>_HISTORY_CAPS[name]:
                raise ValueError('History member type or ceiling')
            h=hashlib.sha256();count=0
            with path.open('rb') as stream:
                while True:
                    if time.monotonic()>=deadline: raise TimeoutError('History hash deadline')
                    block=stream.read(16384)
                    if not block:break
                    h.update(block);count+=len(block)
            after=path.lstat()
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or count!=before.st_size:
                raise RuntimeError('History hash changed')
            result[relative]=dict(bytes=count,sha256=h.hexdigest())
            if len(result)>7:raise ValueError('History file count')
    if len(result) not in (5,7) or sum(v['bytes'] for v in result.values())>31*1024**2:
        raise ValueError('Complete Off or Processed history required')
    return result


def history_decoder(release, manifest_sha256, deadline):
    """Compile unchanged installed reader methods only; no model/store constructor."""
    release=Path(release)
    raw=history_bytes(release/'RELEASE_MANIFEST.json',262144,deadline)
    if hashlib.sha256(raw).hexdigest()!=manifest_sha256:raise ValueError('History installed manifest drift')
    manifest=history_json(raw);pins={r['path']:r for r in manifest['files']}
    if len(pins)!=len(manifest['files']):raise ValueError('Duplicate installed member')
    selected={'native/field_artifact_limits_v1.py':('validate','resolved','digest'),
              'app/bounded_live_artifacts_v1.py':('encoded',),
              'app/app_bounded_artifacts_v1.py':('compact_records','compact_rows'),
              'app/sessions.py':('folder','metadata','epoch','_quiet','list','iter_rows','rows')}
    sources={};trees={}
    for name in selected:
        raw=history_bytes(release/name,262144,deadline);pin=pins[name]
        if len(raw)!=pin['bytes'] or hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('Installed history reader drift')
        sources[name]=raw;trees[name]=ast.parse(raw)
    ns=dict(__builtins__=__builtins__,Path=Path,hashlib=hashlib,json=json,copy=copy,
        deepcopy=copy.deepcopy,OrderedDict=OrderedDict,re=re,threading=threading,MIB=1024**2,RATE=16000,
        read_json=lambda p:history_json(history_bytes(p,65536,deadline)),
        size_tree=lambda p:sum(v['bytes'] for v in history_census(p,deadline).values()))
    limits=trees['native/field_artifact_limits_v1.py']
    nodes=[n for n in limits.body if isinstance(n,ast.Assign) and any(
        isinstance(t,ast.Name) and t.id in ('MIB','SCHEMA','DEFAULT') for t in n.targets)]
    for name,names in selected.items():
        tree=trees[name]
        if name=='app/sessions.py':
            cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SessionStore')
            methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
            if {n.name for n in methods}!=set(names):raise ValueError('Installed history method set')
            nodes.append(ast.ClassDef(name='SessionStore',bases=[],keywords=[],body=methods,decorator_list=[]))
        else:
            found=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
            if {n.name for n in found}!=set(names):raise ValueError('Installed decoder function set')
            nodes.extend(found)
    # Nodes are the actual original AST bodies. Imports and constructors are excluded.
    module=ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[]))
    exec(compile(module,'<pinned-installed-history-readers>','exec'),ns)
    return ns,sources


def history_open(release,manifest_sha256,folder,metadata_pin,*,deadline):
    folder=Path(folder);identifier=folder.name
    if not re.fullmatch('[0-9a-f]{32}',identifier):raise ValueError('History conversation ID')
    with history_reading():
        before=history_census(folder,deadline)
        if before['conversation.json']!=metadata_pin:raise ValueError('Closed history metadata pin changed')
        metadata=history_json(history_bytes(folder/'conversation.json',65536,deadline))
        if metadata.get('id')!=identifier or metadata.get('state')!='SAVED' or metadata.get('pinned') is not True:
            raise ValueError('Saved pinned history only')
        epochs=metadata.get('epochs')
        if type(epochs) is not list or len(epochs)!=1 or not re.fullmatch('[0-9a-f]{32}',epochs[0]):
            raise ValueError('One complete epoch')
        epoch=history_json(history_bytes(folder/'epochs'/epochs[0]/'epoch.json',65536,deadline))
        if epoch.get('event_format')!='compact-patch-v1' or epoch.get('state')!='CLOSED' or epoch.get('worker_alive') or epoch.get('archive_error'):
            raise ValueError('Closed compact history only')
        expected={'conversation.json'}|{'epochs/'+epochs[0]+'/'+n for n in ('epoch.json','events.jsonl','resources.jsonl','windows.jsonl')}
        audio={'epochs/'+epochs[0]+'/'+n for n in ('model_input.f32le','model_input.wav')}
        if set(before) not in (expected,expected|audio):raise ValueError('Complete exact archive membership')
        ns,sources=history_decoder(release,manifest_sha256,deadline)
        store=ns['SessionStore'].__new__(ns['SessionStore'])
        store.root=folder.parent;store.active={};store.lock=threading.RLock()
        # Source binding restricts this parent to one recorded conversation.
        if {p.name for p in folder.parent.iterdir()}!={identifier}:raise ValueError('One source conversation')
        listing=store.list()
        if len(listing)!=1 or listing[0]['id']!=identifier:raise ValueError('Installed list selection')
        rows=store.rows(identifier,limit=512)
        if len(rows)>512:raise ValueError('History row cap')
        if time.monotonic()>=deadline:raise TimeoutError('History decode deadline')
        if history_census(folder,deadline)!=before:raise RuntimeError('History files changed')
        for name,raw in sources.items():
            if history_bytes(Path(release)/name,262144,deadline)!=raw:raise RuntimeError('Installed reader changed')
    return dict(metadata=listing[0],rows=rows,member_pins=before,read_only=True,
        capture_started=False,constructor_called=False,audio_recorded=bool(set(before)&audio))

