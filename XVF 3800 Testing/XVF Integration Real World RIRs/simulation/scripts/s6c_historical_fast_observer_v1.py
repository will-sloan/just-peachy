"""Historical observer adapter utilities; see README_S6C_HISTORICAL_FAST_OBSERVER_V1.md."""
from __future__ import annotations
import argparse, ast, hashlib, importlib.util, json, math, os, re, stat, sys, tempfile, time, types, uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
SIM=HERE.parent
RUN='20260910T123540Z'
REPORT=SIM/'reports/S6C'/RUN
PAYLOAD=Path('G:/Just_Peachy_S6C')/RUN
EDGE=SIM.parents[2]/'.edge-speech-env/python.exe'
PINS={
 's6c_paced_controls.py':'abacc5db48137a808a9417c26e44b921be817dda4e6271efe7a9fb7dfd7bf6a9',
 's6c_paced_b36_v1.py':'8d60474f0517b5f43dbdb64a5194829241ded8d5acdbd622ec3bef6851152abd',
 's6c_long_b36_v1.py':'09b809f6301e696054c4563fdad0d48072ae22716bafcf9002a33bdffd866c66',
 's6c_admission_fast_v1.py':'f7259056cd66d9d031e71b0f319844b2e7aaa798951e538ca0a45160ddcc0166',
 's6c_execution_inventory_v4.py':'426a4eaada68e51d0e6af6decd8b9b56fa3c9660b3cca005f959862c03177876',
 's6c_execution_inventory_v5.py':'aee67604429f12013058ed94c74c3d3965c1e8e55299c87dfb6760394513aad8',
 's6b_paced.py':'e755867e703bc6f4dc457db8ad6e98b078af8cf3abcf15fce8adf58efd10fcd9'}
VARIANTS={
 'controls':dict(parent='s6c_paced_controls.py',wrapper='s6c_paced_controls_fast_v1.py',readme='README_S6C_PACED_CONTROLS_FAST_V1.md',namespace='paced_controls',old_schema='s6c-historical-paced-controls.v1',schema='s6c-historical-paced-controls-fast.v1',profiles=['B00','B01']),
 'b36':dict(parent='s6c_paced_b36_v1.py',wrapper='s6c_paced_b36_fast_v1.py',readme='README_S6C_PACED_B36_FAST_V1.md',namespace='paced_controls',old_schema='s6c-historical-paced-b36.v1',schema='s6c-historical-paced-b36-fast.v1',profiles=['B36']),
 'long_b36':dict(parent='s6c_long_b36_v1.py',wrapper='s6c_long_b36_fast_v1.py',readme='README_S6C_LONG_B36_FAST_V1.md',namespace='long_b36',old_schema='s6c-exact-historical-b36-continuous.v1',schema='s6c-exact-historical-b36-continuous-fast.v1',profiles=['B36'])}
SCOPE='Current regular-file traversal with fresh os.stat for each nondirectory entry, no cross-call cache or atomic snapshot. Directory enumeration sizes are not used for file accounting because Windows hardlink entries can be stale. File symlinks follow their target; dangling file links and nonregular entries contribute zero. Directory symlinks are not traversed. Unsupported reparse entries and traversal/access errors fail closed; this deliberately strengthens old pathlib error suppression. Admission/between-cell/terminal scans, disk limits, reservations and worker settings remain unchanged. The periodic20-second timer restarts after the full scan completes, preventing immediate retrigger after a40-second walk. Paced outer RAM floor is prospectively strengthened from4 to12GiB; continuous was already12GiB.'

def require(ok,message):
    if not ok:raise ValueError(message)

def bind(path,raw=None):
    p=Path(path).resolve();raw=p.read_bytes() if raw is None else raw
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def read_bound(path,expected=None):
    p=Path(path).resolve();before=p.stat();require(before.st_size<=64*2**20,'Metadata exceeds64MiB')
    raw=p.read_bytes();after=p.stat();require((before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'Metadata changed during read')
    b=bind(p,raw)
    if expected is not None:require(b=={k:expected[k] for k in ('path','bytes','sha256')},'Exact metadata buffer binding differs')
    return json.loads(raw.decode('utf-8-sig')),b

class Reader:
    def read(self,path,expected=None):return read_bound(path,expected)

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()

def save(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    require(not p.exists(),'Preserve prior output: '+str(p))
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();temp=p.with_name('.'+p.name+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('xb') as h:h.write(raw);h.flush();os.fsync(h.fileno())
    temp.rename(p);return bind(p,raw)

def load(name):
    path=HERE/name;require(bind(path)['sha256']==PINS[name],'Held source changed: '+name)
    key='_historical_fast_'+name.removesuffix('.py')
    spec=importlib.util.spec_from_file_location(key,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    require(Path(module.__file__).resolve()==path,'Unexpected imported source')
    return module

def source_bindings(kind):
    v=VARIANTS[kind]
    names=[Path(__file__).name,'README_S6C_HISTORICAL_FAST_OBSERVER_V1.md',v['wrapper'],v['readme'],*PINS,
           'README_S6C_ADMISSION_FAST_V1.md','README_S6C_PACED_CONTROLS.md','README_S6C_PACED_B36_V1.md','README_S6C_LONG_B36_V1.md',
           's6c_paced_controls_fast_v1.py','README_S6C_PACED_CONTROLS_FAST_V1.md']
    for name,wanted in PINS.items():require(bind(HERE/name)['sha256']==wanted,'Held source changed: '+name)
    return [bind(HERE/n) for n in dict.fromkeys(names)]

def reject_reparse(metadata,path,is_symlink):
    if getattr(metadata,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024):
        require(is_symlink,'Unsupported non-symlink reparse entry: '+str(path))

def scan_details(root,regular_files_only=False):
    """Fresh-stat scanner; explicit regular-file or original os.walk file policy."""
    root=Path(root)
    try:m=root.lstat()
    except FileNotFoundError:return dict(bytes=0,files=0,directories=0)
    symlink=stat.S_ISLNK(m.st_mode);reject_reparse(m,root,symlink)
    # pathlib rglob on a regular file yields no descendants. A root directory
    # symlink is explicitly selected and can be traversed; inner ones cannot.
    try:target=root.stat() if symlink else m
    except FileNotFoundError:return dict(bytes=0,files=0,directories=0)
    if not stat.S_ISDIR(target.st_mode):return dict(bytes=0,files=0,directories=0)
    pending=[str(root)];total=files=directories=0
    while pending:
        current=pending.pop()
        with os.scandir(current) as entries:
            directories+=1
            for entry in entries:
                is_link=entry.is_symlink()
                meta=entry.stat(follow_symlinks=False)
                reject_reparse(meta,entry.path,is_link)
                if is_link:
                    try:meta=os.stat(entry.path,follow_symlinks=True)
                    except FileNotFoundError:
                        if regular_files_only:continue
                        raise
                    if not stat.S_ISDIR(meta.st_mode) and (not regular_files_only or stat.S_ISREG(meta.st_mode)):total+=meta.st_size;files+=1
                elif stat.S_ISDIR(meta.st_mode):pending.append(entry.path)
                else:
                    meta=os.stat(entry.path,follow_symlinks=True)
                    if not regular_files_only or stat.S_ISREG(meta.st_mode):total+=meta.st_size;files+=1
    return dict(bytes=total,files=files,directories=directories)

def strict_bytes(root):return scan_details(root,regular_files_only=True)['bytes']
def tree_bytes(root):return scan_details(root,regular_files_only=False)['bytes']

class ScanMeter:
    def __init__(self,scan=None):self.rows={};self.scan=scan
    def __call__(self,root):
        key=str(Path(root).resolve());row=self.rows.setdefault(key,dict(calls=0,successful=0,failed=0,total_wall_sec=0.,total_cpu_sec=0.,max_wall_sec=0.,last_bytes=None,last_error=None))
        start=time.perf_counter();cpu=time.process_time();row['calls']+=1
        try:
            value=(self.scan or strict_bytes)(root);row['successful']+=1;row['last_bytes']=value;row['last_error']=None;return value
        except BaseException as exc:row['failed']+=1;row['last_error']=repr(exc);raise
        finally:
            elapsed=time.perf_counter()-start;row['total_wall_sec']+=elapsed;row['total_cpu_sec']+=time.process_time()-cpu;row['max_wall_sec']=max(row['max_wall_sec'],elapsed)

def original_plan(kind,b):
    inv=load('s6c_execution_inventory_v5.py' if kind=='long_b36' else 's6c_execution_inventory_v4.py')
    result=inv.admit_plan(Reader(),b);plan=result[0]
    require(plan['schema']==VARIANTS[kind]['old_schema'],'Wrong original prepared schema')
    require([j['profile_id'] for j in plan['jobs']] and set(j['profile_id'] for j in plan['jobs'])==set(VARIANTS[kind]['profiles']),'Original profile scope differs')
    return plan

def roots(kind,name):
    require(isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,60}',name) and name.endswith('_fast_v1'),'Simple new namespace ending _fast_v1 required')
    v=VARIANTS[kind];return REPORT/v['namespace']/name,PAYLOAD/v['namespace']/name

def projection(kind,old,ob,name,created):
    v=VARIANTS[kind];r,p=roots(kind,name);new=deepcopy(old);new.pop('manifest_key');new.update(schema=v['schema'],created_utc=created,original_prepared_manifest=ob,
        fast_observer=dict(scope=SCOPE,sources=source_bindings(kind),original_local_function='strict_bytes',native_driver_unchanged=True,outer_ram_min_bytes=12*2**30),output_root=str(p))
    if kind=='long_b36':
        new.update(namespace=name,report_root=str(r),payload_root=str(p),sources=long_sources())
    else:
        new['coordinator']=bind(HERE/v['wrapper']);new['resource_limits']['host_available_min_bytes']=12*2**30
        new['dependencies']=list({x['path']:x for x in old['dependencies']+[ob]+source_bindings(kind)}.values())
    new['manifest_key']=digest(new);return new

def long_sources():return load('s6c_long_b36_v1.py').source_bindings()+source_bindings('long_b36')

def lineage(kind,path):
    value,b=read_bound(path);ob=value['original_prepared_manifest'];old=original_plan(kind,ob)
    name=value['namespace'] if kind=='long_b36' else Path(value['output_root']).name
    expected=projection(kind,old,ob,name,value['created_utc']);require(value==expected,'Only declared observer/namespace metadata may differ')
    r,p=roots(kind,name);require(Path(b['path'])==(r if kind=='long_b36' else p)/'MANIFEST.json','Fast manifest root differs')
    return value,b

def adapt(kind):
    v=VARIANTS[kind];original=load(v['parent']);ns={**vars(original),'__file__':str(HERE/v['wrapper']),'__name__':'_adapted_'+kind}
    replacements={'long_b36' if kind=='long_b36' else 'paced_controls':v['namespace'],v['old_schema']:v['schema']}
    if kind=='long_b36':replacements.update({'s6c-exact-historical-b36-continuous-result.v1':'s6c-exact-historical-b36-continuous-fast-result.v1','S6C_EXACT_HISTORICAL_B36_CONTINUOUS':'S6C_EXACT_HISTORICAL_B36_CONTINUOUS_FAST'})
    # Globals carry schema constants in B36 variants; only metadata strings change.
    for key,value in list(ns.items()):
        if isinstance(value,str) and value in replacements:ns[key]=replacements[value]
    class Transform(ast.NodeTransformer):
        def visit_Assign(self,node):
            if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='lastbeat' and isinstance(node.value,ast.Name) and node.value.id=='elapsed':
                return ast.copy_location(ast.Assign(targets=node.targets,value=ast.parse('time.monotonic()-t0',mode='eval').body),node)
            return self.generic_visit(node)
        def visit_Constant(self,node):
            if isinstance(node.value,str) and node.value in replacements:return ast.copy_location(ast.Constant(replacements[node.value]),node)
            return node
    tree=ast.parse((HERE/v['parent']).read_bytes());nodes=[];changes=[]
    excluded={'main','prepare','checks','source_checks','source_bindings'}
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name not in excluded:
            modified=Transform().visit(deepcopy(node));nodes.append(modified)
            if ast.dump(node,include_attributes=False)!=ast.dump(modified,include_attributes=False):changes.append(node.name)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(HERE/v['parent']),'exec'),ns)
    meter=ScanMeter()
    if kind=='long_b36':
        controls_path=HERE/'s6c_paced_controls_fast_v1.py'
        controls_spec=importlib.util.spec_from_file_location('_explicit_fast_controls',controls_path);controls=importlib.util.module_from_spec(controls_spec);controls_spec.loader.exec_module(controls)
        require(Path(controls.__file__).resolve()==controls_path and controls.strict_bytes is strict_bytes,'Explicit new controls scanner import differs')
        meter=ScanMeter(controls.strict_bytes)
        ns['C']=types.SimpleNamespace(**vars(original.C));ns['C'].__file__=str(controls_path);ns['C'].strict_bytes=meter;ns['source_bindings']=long_sources
        admitted=ns['admit']
        def admit(path,full=False):lineage(kind,path);return admitted(path,full)
        ns['admit']=admit
    else:
        ns['RESOURCE_LIMITS']=dict(original.RESOURCE_LIMITS,host_available_min_bytes=12*2**30);ns['strict_bytes']=meter
        if kind=='b36':
            validated=ns['validate_b36_plan']
            def validate_b36_plan(plan,base,entry):
                base=deepcopy(base);base['resource_limits']=dict(ns['RESOURCE_LIMITS']);return validated(plan,base,entry)
            ns['validate_b36_plan']=validate_b36_plan
        admitted=ns['admit_manifest']
        def admit_manifest(path):lineage(kind,path);return admitted(path)
        ns['admit_manifest']=admit_manifest
    ns['_fast_meter']=meter;ns['_metadata_ast_changed_functions']=changes;ns['_original']=original
    return types.SimpleNamespace(**ns)

def prepare(kind,args):
    require(args.source_manifest is not None and args.source_sha256 and args.namespace,'prepare requires source manifest/SHA and new namespace')
    _,ob=read_bound(args.source_manifest);require(ob['sha256']==args.source_sha256,'Explicit original manifest SHA differs')
    old=original_plan(kind,ob);r,p=roots(kind,args.namespace);require(not r.exists() and not p.exists(),'Fresh fast namespace required')
    original_root=Path(old['output_root']);require(not (original_root/'jobs').exists() and not (original_root/'invocations').exists(),'Only unexecuted original preparation may be projected')
    if kind=='long_b36':require(not (Path(old['report_root'])/'invocations').exists(),'Original continuous invocation already exists')
    value=projection(kind,old,ob,args.namespace,utc());p.mkdir(parents=True);r.mkdir(parents=True)
    mb=save((r if kind=='long_b36' else p)/'MANIFEST.json',value)
    lineage(kind,mb['path'])
    return save(r/'PREPARATION.json',dict(status='PREPARED_METADATA_ONLY_NO_MODELS',manifest=mb,original_prepared_manifest=ob,requested=len(value['jobs']),source_sec=sum(j['duration_sec'] for j in value['jobs']),source_bindings=source_bindings(kind),scope='Original prepared authority is admitted through reviewed inventory metadata guards. Current PCM/model bytes are not reread here; unchanged original full admission rehashes them before actual execution.',models=0,native_sessions=0))

def observer_owner(process):
    owner=dict(pid=process.pid,creation_time=process.create_time(),argv=process.cmdline())
    require(type(owner['pid']) is int and owner['pid']>0 and type(owner['creation_time']) in (int,float) and math.isfinite(owner['creation_time']) and owner['creation_time']>0,'Finite observer PID/creation required')
    require(isinstance(owner['argv'],list) and owner['argv'] and all(isinstance(x,str) and x for x in owner['argv']),'Explicit observer argv required')
    return owner

def execute(kind,args):
    require(Path(sys.executable).resolve()==EDGE.resolve(),'Exact EDGE interpreter required')
    value,mb=lineage(kind,args.manifest);api=adapt(kind)
    if args.action=='worker':
        require(kind=='long_b36' and args.owner_lease is not None,'Only continuous original worker entry is exposed');return api.worker(args)
    require(args.quiet_admission is not None,'Explicit separate quiet admission required')
    r,_=roots(kind,value.get('namespace',Path(value['output_root']).name));folder=r/'observer_invocations'/uuid.uuid4().hex
    start=utc();before=source_bindings(kind);status='FAILED';error=None;owner=observer_owner(api._original.psutil.Process())
    try:result=api.run(args);status=result['status'];return result
    except BaseException as exc:error=repr(exc);raise
    finally:
        after=source_bindings(kind)
        save(folder/'SCANNER_OUTCOME.json',dict(schema='s6c-historical-fast-observer-outcome.v1',status=status,error=error,manifest=mb,started_utc=start,ended_utc=utc(),coordinator_pid=owner['pid'],owner=owner,wrapper=bind(HERE/VARIANTS[kind]['wrapper']),entry='run',sources_before=before,sources_after=after,sources_unchanged=before==after,storage_scans=api._fast_meter.rows,scope=SCOPE,closure_scope='This report measures observer scan calls only. Original invocation/child receipts and observed PID+creation closure remain authoritative; this is not a model-session or quiet-release receipt.'))
        require(before==after,'Observer sources changed during execution')

def checks(kind,args=None):
    checks=[];unavailable=[]
    def ok(condition,name):require(condition,name);checks.append(name)
    original=load('s6c_paced_controls.py')
    with tempfile.TemporaryDirectory(prefix='s6c_historical_fast_') as folder:
        root=Path(folder);ok(strict_bytes(root/'absent')==original.strict_bytes(root/'absent')==0,'missing root zero')
        ok(strict_bytes(root)==0,'empty tree')
        (root/'nested').mkdir();(root/'nested/é.txt').write_bytes(b'abcd');(root/'empty').write_bytes(b'');(root/'.hidden').write_bytes(b'x'*17)
        def same(label):ok(strict_bytes(root)==original.strict_bytes(root),label)
        same('regular nested hidden unicode empty parity');ok(strict_bytes(root/'empty')==0,'regular-file root yields no descendants')
        os.link(root/'.hidden',root/'hardlink');same('hardlink counted per directory entry')
        for raw in (b'x'*29,b'a'):(root/'.hidden').write_bytes(raw);same('growth/shrink reread '+str(len(raw)))
        ok(tree_bytes(root)==original.strict_bytes(root),'common-mode hardlink fresh sizes')
        (root/'hardlink').unlink();same('deletion reread')
        for label,target,is_dir in [('file_link',root/'.hidden',False),('dir_link',root/'nested',True),('dangling_link',root/'absent',False)]:
            try:os.symlink(target,root/label,target_is_directory=is_dir)
            except OSError as exc:unavailable.append(dict(name=label,error=repr(exc)))
            else:same(label+' matches regular-file policy')
        try:
            with patch.object(os,'scandir',side_effect=PermissionError('fixture')):strict_bytes(root)
        except PermissionError:checks.append('unreadable traversal fails closed')
        else:raise AssertionError('access error swallowed')
        class Entries:
            def __init__(self,entries):self.entries=entries
            def __enter__(self):return iter(self.entries)
            def __exit__(self,*args):return False
        class Entry:
            path='synthetic'
            def __init__(self,mode,linked=False,error=None):self.mode=mode;self.linked=linked;self.error=error
            def is_symlink(self):return self.linked
            def stat(self,follow_symlinks=True):
                if self.error and follow_symlinks:raise self.error
                return types.SimpleNamespace(st_mode=stat.S_IFLNK if self.linked and not follow_symlinks else self.mode,st_size=7,st_file_attributes=0)
        real_stat=os.stat
        for label,entry,expected in [('file symlink target size',Entry(stat.S_IFREG,True),7),('directory symlink skipped',Entry(stat.S_IFDIR,True),0),('dangling symlink skipped',Entry(0,True,FileNotFoundError()),0),('nonregular entry skipped',Entry(stat.S_IFIFO),0)]:
            with patch.object(os,'scandir',return_value=Entries([entry])),patch.object(os,'stat',side_effect=lambda path,**k:entry.stat() if str(path)=='synthetic' else real_stat(path,**k)):ok(strict_bytes(root)==expected,'synthetic '+label)
        for label,entry in [('dangling common link',Entry(0,True,FileNotFoundError())),('common permission error',Entry(0,True,PermissionError()))]:
            with patch.object(os,'scandir',return_value=Entries([entry])),patch.object(os,'stat',side_effect=lambda path,**k:entry.stat() if str(path)=='synthetic' else real_stat(path,**k)):
                try:tree_bytes(root)
                except OSError:checks.append(label+' fails closed')
                else:raise AssertionError('common mode swallowed error')
        entry=Entry(stat.S_IFIFO)
        with patch.object(os,'scandir',return_value=Entries([entry])),patch.object(os,'stat',side_effect=lambda path,**k:entry.stat() if str(path)=='synthetic' else real_stat(path,**k)):ok(tree_bytes(root)==7,'common mode retains nonregular stat bytes')
        entry=Entry(0,True,PermissionError('target'))
        with patch.object(os,'scandir',return_value=Entries([entry])),patch.object(os,'stat',side_effect=lambda path,**k:entry.stat() if str(path)=='synthetic' else real_stat(path,**k)):
            try:strict_bytes(root)
            except PermissionError:checks.append('symlink target permission failure propagates')
            else:raise AssertionError('target permission hidden')
        fake=types.SimpleNamespace(st_file_attributes=1024)
        try:reject_reparse(fake,'junction',False)
        except ValueError:checks.append('unsupported junction/reparse fails closed')
        else:raise AssertionError('junction accepted')
        reject_reparse(fake,'file symlink',True);checks.append('recognized symlink permitted')
        meter=ScanMeter();ok(meter(root)==strict_bytes(root),'meter preserves byte result');ok(sum(r['calls'] for r in meter.rows.values())==1,'meter exact call count')
        with patch.dict(globals(),strict_bytes=lambda root:(_ for _ in ()).throw(PermissionError('fixture'))):
            try:meter(root)
            except PermissionError:pass
            else:raise AssertionError('meter hid scan failure')
        ok(next(iter(meter.rows.values()))['failed']==1,'meter retains failure count')
    api=adapt(kind);parent=api._original
    ok(parent.strict_bytes is not api.strict_bytes if kind!='long_b36' else parent.C.strict_bytes is not api.C.strict_bytes,'only isolated adapter scanner changed')
    ok((api.RESOURCE_LIMITS if kind!='long_b36' else api.LIMITS)['host_available_min_bytes']==12*2**30,'prospective outer RAM12GiB')
    expected_limits=dict(parent.RESOURCE_LIMITS,host_available_min_bytes=12*2**30) if kind!='long_b36' else parent.LIMITS
    ok((api.RESOURCE_LIMITS if kind!='long_b36' else api.LIMITS)==expected_limits,'all other resource limits exact')
    original_tree=ast.parse((HERE/VARIANTS[kind]['parent']).read_bytes())
    original_functions={n.name:n for n in original_tree.body if isinstance(n,ast.FunctionDef)}
    run=deepcopy(original_functions['run']);timers=[n for n in ast.walk(run) if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='lastbeat' and isinstance(n.value,ast.Name) and n.value.id=='elapsed']
    ok(len(timers)==1,'one original periodic timer assignment')
    timers[0].value=ast.parse('time.monotonic()-t0',mode='eval').body
    expected_ns=dict(vars(parent));exec(compile(ast.fix_missing_locations(ast.Module(body=[run],type_ignores=[])),'independent_timer_oracle','exec'),expected_ns)
    ok(api.run.__code__.co_code==expected_ns['run'].__code__.co_code and api.run.__code__.co_consts==expected_ns['run'].__code__.co_consts,'run bytecode differs only post-scan timer assignment')
    timer_ns=dict(time=types.SimpleNamespace(monotonic=lambda:60.),t0=0.,elapsed=20.)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[deepcopy(timers[0])],type_ignores=[])),'timer_fixture','exec'),timer_ns)
    ok(timer_ns['lastbeat']==60. and 60.5-timer_ns['lastbeat']<20 and 80.-timer_ns['lastbeat']>=20,'40-second scan restarts20-second interval after completion')
    if kind=='long_b36':ok('worker' not in api._metadata_ast_changed_functions,'original continuous wrapper worker AST exact')
    ok(bind(HERE/'s6b_paced.py')['sha256']==PINS['s6b_paced.py'],'whole original native driver exact')
    for name in ('../escape','a/b','',None):
        try:roots(kind,name)
        except ValueError:checks.append('reject unsafe namespace '+repr(name))
        else:raise AssertionError('unsafe namespace')
    ok(set(api.run.__code__.co_names)==set(parent.run.__code__.co_names),'original coordinator call/name set exact')
    fake=types.SimpleNamespace(pid=42,create_time=lambda:123.5,cmdline=lambda:['python','observer.py','run'])
    ok(observer_owner(fake)==dict(pid=42,creation_time=123.5,argv=['python','observer.py','run']),'exact observer owner fields')
    for label,pid,created,argv in [('boolean PID',True,1.,['python']),('NaN creation',42,float('nan'),['python']),('missing argv',42,1.,[])]:
        try:observer_owner(types.SimpleNamespace(pid=pid,create_time=lambda:created,cmdline=lambda:argv))
        except ValueError:checks.append('reject '+label)
        else:raise AssertionError('unverified observer owner accepted')
    metadata=None
    if args is not None and args.source_manifest is not None:
        _,ob=read_bound(args.source_manifest);ok(ob['sha256']==args.source_sha256,'explicit prior manifest SHA')
        old=original_plan(kind,ob);name='synthetic_checks_fast_v1';new=projection(kind,old,ob,name,utc());r,p=roots(kind,name);mp=(r if kind=='long_b36' else p)/'MANIFEST.json'
        ok(new['jobs']==old['jobs'],'all original native job objects exact')
        ok(new['driver']==old['driver'],'original native driver binding exact')
        ok(new['historical_epoch']==old['historical_epoch'],'actual historical execution epoch exact')
        def attempt(document):
            b=dict(path=str(mp),bytes=1,sha256='0'*64)
            with patch.dict(globals(),read_bound=lambda *a,**k:(document,b),original_plan=lambda *a,**k:old):return lineage(kind,mp)
        attempt(new);checks.append('positive in-memory projected lineage')
        for label,mutate in [('profile',lambda x:x['jobs'][0].update(profile={'wrong':True})),('input',lambda x:x['jobs'][0]['input'].update(sha256='0'*64)),('driver',lambda x:x['driver'].update(sha256='0'*64)),('RAM floor',lambda x:x['resource_limits'].update(host_available_min_bytes=4*2**30)),('timeout',lambda x:x.update(timeout_sec=x['timeout_sec']+1)),('observer source',lambda x:x['fast_observer']['sources'][0].update(sha256='0'*64)),('source authority',lambda x:x['original_prepared_manifest'].update(sha256='0'*64))]:
            bad=deepcopy(new);mutate(bad);bad.pop('manifest_key');bad['manifest_key']=digest(bad)
            # Source authority is checked by original_plan's exact reader in production.
            if label=='source authority':
                try:original_plan(kind,bad['original_prepared_manifest'])
                except ValueError:checks.append('re-bound wrong '+label+' rejected')
                else:raise AssertionError('source authority accepted')
                continue
            try:attempt(bad)
            except ValueError:checks.append('re-bound wrong '+label+' rejected')
            else:raise AssertionError('lineage mutation accepted: '+label)
        metadata=dict(original_manifest=ob,projected_jobs=len(new['jobs']),job_objects_sha256=digest(new['jobs']),total_source_sec=sum(j['duration_sec'] for j in new['jobs']),scope='In-memory projection only; no new manifest or native output written.')
    return dict(status='PASS_MODEL_FREE_SOURCE_CHECKS',created_utc=utc(),checks=checks,check_count=len(checks),optional_link_fixtures_unavailable=unavailable,metadata_ast_changed_functions=api._metadata_ast_changed_functions,actual_original_metadata=metadata,source_bindings=source_bindings(kind),models=0,native_sessions=0,actual_preparations=0,full_storage_walks=0,scope=SCOPE,remaining_scope='Synthetic directory and isolated source checks only. No present187k-file tree measurement or real reparse census. Historical paced launch/cleanup behavior is inherited unchanged, including its preexisting successful-Popen/creation-query gap; this optimization does not certify additional ownership behavior.')

def cli(kind,entry):
    require(Path(entry).resolve()==HERE/VARIANTS[kind]['wrapper'],'Exact variant entry required')
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=('checks','prepare','run','worker'));p.add_argument('--output',type=Path);p.add_argument('--source-manifest',type=Path);p.add_argument('--source-sha256');p.add_argument('--namespace');p.add_argument('--manifest',type=Path);p.add_argument('--quiet-admission',type=Path);p.add_argument('--owner-lease',type=Path);a=p.parse_args()
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
    if a.action=='checks':require(a.output is not None,'Fresh checks output required');result=save(a.output,checks(kind,a))
    elif a.action=='prepare':result=prepare(kind,a)
    else:require(a.manifest is not None,'Explicit manifest required');result=execute(kind,a)
    print(json.dumps(result,allow_nan=False))
