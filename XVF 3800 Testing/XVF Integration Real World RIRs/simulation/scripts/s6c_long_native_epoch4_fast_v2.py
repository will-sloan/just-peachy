"""Isolated epoch4 long-native admission; README_S6C_LONG_NATIVE_EPOCH4_FAST_V2.md."""
from __future__ import annotations
import functools
import importlib.util
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import hashlib
import importlib
import json
import struct
import types
import math
import os
from pathlib import Path
import re
import sys
import time
import traceback
import uuid
import psutil

SIM=Path(__file__).resolve().parents[1]
RUN='20260910T123540Z'
REPORT=SIM/'reports/S6C'/RUN
PAYLOAD=Path('G:/Just_Peachy_S6C')/RUN
STAGING=SIM/'staging/s6c'/RUN
EDGE=SIM.parents[2]/'.edge-speech-env/python.exe'
COMPOSITION=REPORT/'long_session/v1/COMPOSITION.json'
COMPOSITION_SHA='bfa18ae06bb224faaad2d4f5096f2e6a0d1aebff5c7c16192d608739d3533bf3'
PINS={
    's6c_orchestrator_scan_v3.py':'436ae9a78319bf54710b3f1ac4a4d8a93034ba4030efda8817a2bdfeefd0d7e7',
    's6c_orchestrator_scan_v2.py':'eb83afe67c21ac1daa9c388d21471167500971bdc358a5fb557b7e4883d8a5ab',
    's6c_orchestrator_scan_v1.py':'6554b2d007223c66edfd67660790cc8f614eaffd5a13ae756833ccef9df4deef',
    's6c_long_session.py':'ba14bf81489e6e99059a7ab21089f517c8c2ac4af51f1c8650d7d6321203c159',
    's6c_native_prefix.py':'4935ce7cb74d54ce957940429d539d7a043c04547da63b4e130ce4b2cdd6bb8f',
    's6c_common.py':'991f5acf5880806a48b0586adb23b04674ed5b12672a09ae66b797475c26259c'}
DEADLINE=datetime(2026,9,13,11,35,40,tzinfo=timezone.utc)
PENDING_BYTES=4*2**30
MAX_WALL_SEC=7200
ALLOWED_OVERRIDES=('load_composition','admit_work','process_sample')
PROTECTED=('native','choose_profile','fixed_gallery_row','import_epoch','record_sample','source_bindings')


def utc():return datetime.now(timezone.utc).isoformat()
def dt(value):
    value=datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None:raise ValueError('Timezone required')
    return value.astimezone(timezone.utc)
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def bind(path):
    p=Path(path).resolve();before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    after=p.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('File changed during binding')
    return dict(path=str(p),bytes=before.st_size,sha256=h.hexdigest())
def verify(b):
    actual=bind(b['path'])
    if actual!=b:raise ValueError('Exact source binding differs: '+b['path'])
    return actual
def read_bound(path,expected=None):
    p=Path(path).resolve();before=p.stat();raw=p.read_bytes();after=p.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or len(raw)!=after.st_size:raise ValueError('Authority changed during exact-buffer read')
    b=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    if expected is not None and b!=expected:raise ValueError('Exact authority bytes differ: '+str(p))
    return json.loads(raw.decode('utf-8-sig')),b
def read(path):return read_bound(path)[0]
def structural_code_value(value):
    """Typed immutable code values; excludes marshal reference/intern flags."""
    if isinstance(value,types.CodeType):
        return dict(type='code',argcount=value.co_argcount,posonlyargcount=value.co_posonlyargcount,
            kwonlyargcount=value.co_kwonlyargcount,nlocals=value.co_nlocals,stacksize=value.co_stacksize,
            flags=value.co_flags,bytecode=value.co_code.hex(),consts=[structural_code_value(v) for v in value.co_consts],
            names=list(value.co_names),varnames=list(value.co_varnames),filename=value.co_filename,
            name=value.co_name,qualname=value.co_qualname,firstlineno=value.co_firstlineno,
            linetable=value.co_linetable.hex(),exceptiontable=value.co_exceptiontable.hex(),
            freevars=list(value.co_freevars),cellvars=list(value.co_cellvars))
    if type(value) is tuple:return ['tuple',[structural_code_value(v) for v in value]]
    if type(value) is frozenset:
        return ['frozenset',sorted([structural_code_value(v) for v in value],key=lambda v:json.dumps(v,sort_keys=True,separators=(',',':')))]
    if type(value) is bytes:return ['bytes',value.hex()]
    if type(value) is float:return ['float64',struct.pack('!d',value).hex()]
    if type(value) is complex:return ['complex128',struct.pack('!dd',value.real,value.imag).hex()]
    if value is Ellipsis:return ['ellipsis']
    if value is None or type(value) in (bool,int,str):return [type(value).__name__,value]
    raise TypeError('Unsupported protected constant type: '+type(value).__name__)


def structural_code_sha256(code):
    if not isinstance(code,types.CodeType):raise TypeError('Protected function code required')
    return digest(structural_code_value(code))


def protected_identities(driver):
    result={}
    for name in PROTECTED:
        function=getattr(driver,name)
        if not isinstance(function,types.FunctionType):raise ValueError('Protected object must be a Python function: '+name)
        result[name]=dict(identity=id(function),code_identity=id(function.__code__),code_sha256=structural_code_sha256(function.__code__))
    return result


def protected_guard_policy():
    path=Path(__file__).with_name('s6c_long_session.py').resolve();raw=path.read_bytes()
    binding=dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    if binding['sha256']!=PINS['s6c_long_session.py']:raise ValueError('Original protected source pin changed')
    # Compile exact complete module bytes; execute no module, imports or native work.
    module=compile(raw,str(path),'exec')
    functions={v.co_name:v for v in module.co_consts if isinstance(v,types.CodeType) and v.co_name in PROTECTED}
    if set(functions)!=set(PROTECTED):raise ValueError('Original protected function set differs')
    return dict(schema='s6c-protected-native-guard.v2',original_source=binding,
        fingerprint='SHA256 typed recursive immutable code fields v1; float/complex IEEE bytes; no marshal reference flags',
        runtime_identity='Same-process function and code-object IDs, with strong references retained throughout override',
        protected=list(PROTECTED),original_structural_code_sha256={name:structural_code_sha256(functions[name]) for name in PROTECTED},
        algorithm_source=bind(__file__))


def validate_protected_driver(driver):
    policy=protected_guard_policy();path=Path(policy['original_source']['path'])
    if Path(driver.__file__).resolve()!=path:raise ValueError('Protected original module path differs')
    identities=protected_identities(driver)
    for name in PROTECTED:
        function=getattr(driver,name)
        if function.__globals__ is not vars(driver) or Path(function.__code__.co_filename).resolve()!=path:
            raise ValueError('Protected original function globals/source differ: '+name)
        if identities[name]['code_sha256']!=policy['original_structural_code_sha256'][name]:
            raise ValueError('Protected original structural code differs: '+name)
    return policy


def assert_protected_unchanged(driver,before,phase):
    after=protected_identities(driver)
    changed={name:dict(before=before[name],after=after[name]) for name in PROTECTED if before[name]!=after[name]}
    if changed:raise ValueError('Protected native function/code changed '+phase+': '+json.dumps(changed,sort_keys=True))

# Observer-only installation is scoped to an explicit wrapper entry. Scientific
# driver functions and frozen common source files are never rewritten.
FAST_SCAN_SHA='579963cb5e873a0a08504bb4f022ea8a92a158886d36abfd87ee4a0f9cd6d299'
FAST_SCAN_README_SHA='9bf140e925fec6b7027386aee8eb10ba6ffa255229ec8c2db6471e5d6ad23a97'
_OBSERVER_SCOPES=[]
_FAST_SCANNER=None

def observer_policy():
    files=[]
    for name,sha in (('s6c_historical_fast_observer_v1.py',FAST_SCAN_SHA),('README_S6C_HISTORICAL_FAST_OBSERVER_V1.md',FAST_SCAN_README_SHA)):
        item=bind(Path(__file__).with_name(name))
        if item['sha256']!=sha:raise ValueError('Exact reviewed observer scanner source changed')
        files.append(item)
    return dict(schema='s6c.fast_resource_observer.v1',scanner_sources=files,
        algorithm='Fresh scandir traversal with explicit os.stat for nondirectory sizes; common tree_bytes policy; no cross-call size cache',
        replaced_callable='frozen common.tree_bytes only',full_scan_cadence='Periodic next start at least 20 seconds after previous scan completes; original mandatory full checks unchanged',
        roots='UNCHANGED_REPORT_STAGING_PAYLOAD',resource_limits='UNCHANGED',
        error_scope='Traversal/access/unsupported reparse entries fail closed; original os.walk could silently skip. Common mode fails on dangling file links and retains nonregular nondirectory stat sizes.',
        prior_scanner_limitation='The unchanged f725 scanner can use stale Windows directory-entry sizes after hardlink growth; it is not installed here.',
        observation_scope='Resource scans still create irregular sample gaps and host overhead; observed values are not continuous maxima.')

def load_observer_scanner(common):
    global _FAST_SCANNER
    observer_policy()
    if sys.modules.get('s6c_common') is not common:raise ValueError('Already admitted frozen common module required before installation')
    if _FAST_SCANNER is None:
        path=Path(__file__).with_name('s6c_historical_fast_observer_v1.py')
        spec=importlib.util.spec_from_file_location('s6c_paced_held_scandir',path)
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=FAST_SCAN_SHA:raise ValueError('Exact scanner execution buffer differs')
        module=importlib.util.module_from_spec(spec);exec(compile(raw,str(path),'exec'),module.__dict__)
        if Path(module.__file__).resolve()!=path.resolve():raise ValueError('Wrong scanner import')
        _FAST_SCANNER=module
    return _FAST_SCANNER

def install_observer_scanner(common):
    if not _OBSERVER_SCOPES:raise ValueError('Explicit observer entry scope required')
    if bind(common.__file__)['sha256']!=PINS['s6c_common.py']:raise ValueError('Frozen common source changed')
    if common.resources.__globals__ is not common.__dict__ or common.admit_work.__globals__ is not common.__dict__:
        raise ValueError('Resource function does not resolve exact frozen globals')
    if common.SIM.resolve()!=SIM.resolve() or common.REPORT.resolve()!=REPORT.resolve() or common.STAGING.resolve()!=STAGING.resolve() or common.PAYLOAD.resolve()!=PAYLOAD.resolve():
        raise ValueError('Exact resource roots changed')
    scanner=load_observer_scanner(common)
    for scope in _OBSERVER_SCOPES:
        for entry in scope:
            if entry['common'] is common:
                if common.tree_bytes is not entry['fast']:raise ValueError('Installed scanner was replaced')
                return
    original=common.tree_bytes
    if original.__globals__ is not common.__dict__ or original.__name__!='tree_bytes' or Path(original.__code__.co_filename).resolve()!=Path(common.__file__).resolve():
        raise ValueError('Original frozen tree_bytes callable changed')
    fast=scanner.ScanMeter(scan=scanner.tree_bytes)
    _OBSERVER_SCOPES[-1].append(dict(common=common,original=original,fast=fast,
        resources=common.resources,admit_work=common.admit_work))
    common.tree_bytes=fast

@contextmanager
def observer_scope():
    records=[];_OBSERVER_SCOPES.append(records)
    try:
        yield records
    finally:
        changed=[]
        for entry in reversed(records):
            common=entry['common']
            if common.tree_bytes is not entry['fast'] or common.resources is not entry['resources'] or common.admit_work is not entry['admit_work']:
                changed.append('observer or protected admission callable changed')
            common.tree_bytes=entry['original']
            entry['restored']=common.tree_bytes is entry['original']
            entry['protected_admission_unchanged']=common.resources is entry['resources'] and common.admit_work is entry['admit_work']
        if _OBSERVER_SCOPES[-1] is not records:raise RuntimeError('Observer scopes closed out of order')
        _OBSERVER_SCOPES.pop()
        if changed:raise RuntimeError('; '.join(changed))

def write_observer_record(function,args,result,records,error):
    manifest=None;job_id=None
    if args:
        supplied=getattr(args[0],'manifest',None);job_id=getattr(args[0],'job_id',None)
        if supplied is not None and Path(supplied).is_file():manifest=bind(supplied)
    if manifest is None and isinstance(result,dict):
        supplied=result.get('manifest',result)
        if isinstance(supplied,dict) and Path(supplied.get('path','')).name=='MANIFEST.json':manifest=supplied
    process=psutil.Process()
    observations=[dict(common=bind(r['common'].__file__),original_callable=r['original'].__qualname__,
        scanner_callable=type(r['fast']).__qualname__+'(tree_bytes)',scan_observations=r['fast'].rows,restored=r.get('restored',False),
        protected_admission_unchanged=r.get('protected_admission_unchanged',False)) for r in records]
    value=dict(schema='s6c.fast_resource_observer_exit.v1',created_utc=utc(),entry=function.__name__,
        wrapper=bind(function.__code__.co_filename),manifest=manifest,job_id=job_id,
        owner=dict(pid=process.pid,creation_time=process.create_time(),argv=process.cmdline()),
        policy=observer_policy(),installations=observations,error=error,
        status='RESTORED' if observations and all(r['restored'] and r['protected_admission_unchanged'] for r in observations) else 'NO_INSTALLATION' if not observations else 'RESTORATION_UNVERIFIED',
        scope='Post-entry scanner restoration only. Native outcome, quiet-lease release and external process closure remain separate authorities. Abrupt process termination may leave no observer exit receipt.')
    folder=REPORT/'observer_fast_v2/attempts';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(uuid.uuid4().hex+'.json')
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    return bind(path)

def observer_entry(function):
    @functools.wraps(function)
    def observed(*args,**kwargs):
        result=None;records=[];error=None
        try:
            with observer_scope() as records:
                result=function(*args,**kwargs)
            return result
        except BaseException:
            error=traceback.format_exc();raise
        finally:
            write_observer_record(function,args,result,records,error)
    return observed

def output_roots(namespace):
    if not re.fullmatch(r'epoch4_[A-Za-z0-9_-]{1,64}',namespace) or not namespace.endswith('_fast_v2'):raise ValueError('New epoch4_ namespace required')
    return REPORT/'long_session'/namespace,PAYLOAD/'long_session'/namespace
def state(pid,created):
    if type(pid) is not int or pid<=0 or type(created) not in (int,float) or not math.isfinite(created) or created<=0:
        raise ValueError('Complete finite owner PID/creation identity required')
    try:return abs(psutil.Process(pid).create_time()-created)<.001
    except psutil.NoSuchProcess:return False


def worker_command(argv):
    words=[str(v).lower() for v in (argv or [])]
    names={Path(v).name for v in words};text=' '.join(words)
    if not any(n.startswith(('s6b_','s6c_')) and n.endswith('.py') for n in names):return False
    if '--worker' in words or '--mode worker' in text:return True
    if 's6c_long_session.py' in names:return '--mode native' in text
    if names & {'s6c_long_native_epoch4.py','s6c_paced_epoch4.py','s6c_paced_controls.py','s6c_paced_b36_v1.py','s6c_long_b36_v1.py','s6c_paced_cross_routes_v1.py','s6c_paced_arrival_sentinel_v1.py','s6c_long_native_epoch4_fast_v1.py','s6c_paced_epoch4_fast_v1.py','s6c_long_native_epoch4_fast_v2.py','s6c_paced_epoch4_fast_v2.py','s6c_paced_cross_routes_fast_v2.py','s6c_paced_arrival_sentinel_fast_v2.py','s6c_paced_controls_fast_v1.py','s6c_paced_b36_fast_v1.py','s6c_long_b36_fast_v1.py','s6c_paced_cross_routes_fast_v1.py','s6c_paced_arrival_sentinel_fast_v1.py'}:return any(v in words for v in ('run','worker'))
    if 's6c_enrollment.py' in names:return 'run' in words
    if names & {'s6c_orchestrator_scan_v1.py','s6c_orchestrator_scan_v2.py','s6c_orchestrator_scan_v3.py'}:return 'run' in words
    return False


def load_sources():
    dependencies=[]
    for name,wanted in PINS.items():
        b=bind(Path(__file__).with_name(name))
        if b['sha256']!=wanted:raise ValueError('Pinned historical/native admission source changed: '+name)
        dependencies.append(b)
    overlay=importlib.import_module('s6c_orchestrator_scan_v3')
    if Path(overlay.__file__).resolve()!=Path(__file__).with_name('s6c_orchestrator_scan_v3.py').resolve():raise ValueError('Wrong overlay import path')
    epoch_binding,spec,common,execution=overlay.load_native('epoch4')
    driver=importlib.import_module('s6c_long_session')
    prefix=importlib.import_module('s6c_native_prefix')
    if Path(driver.__file__).resolve()!=Path(__file__).with_name('s6c_long_session.py').resolve() or Path(prefix.__file__).resolve()!=Path(__file__).with_name('s6c_native_prefix.py').resolve():raise ValueError('Wrong original long/prefix import path')
    if driver.load_epoch is not prefix.load_epoch or driver.admit_work is not common.admit_work or driver.bind is not common.bind or prefix.bind is not common.bind:raise ValueError('Long/prefix did not resolve the admitted frozen common module')
    composition_binding=bind(COMPOSITION)
    if composition_binding['sha256']!=COMPOSITION_SHA:raise ValueError('Existing composition changed')
    composition,original,_=driver.load_composition(argparse.Namespace(version='v1'),assets=True)
    if composition['epoch']['sha256']!=overlay.TRUSTED_EPOCHS['epoch2'] or original['epoch']!='epoch2':raise ValueError('Original composition authority must be epoch2')
    overlay.compatible_native(spec,original)
    if composition['duration_sec']!=1827.426625 or composition['duration_samples']!=29238826 or not composition['no_new_gain']:raise ValueError('Exact existing long PCM duration/gain required')
    for b in composition['driver_sources']:verify(b)
    dependencies.extend([epoch_binding,composition_binding,bind(common.__file__),bind(execution.__file__)])
    dependencies.extend(bind(Path(__file__).with_name(name)) for name in ('README_S6C_LONG_SESSION.md','README_S6C_ORCHESTRATOR_SCAN_V3.md','README_S6C_NATIVE_PREFIX.md'))
    imports=dict(actual_epoch='epoch4',source_composition_epoch='epoch2',common=bind(common.__file__),native_execution=bind(execution.__file__),long_helper=bind(driver.__file__),prefix_helper=bind(prefix.__file__),overlay=bind(overlay.__file__))
    dependencies.extend(observer_policy()['scanner_sources'])
    validate_protected_driver(driver)
    install_observer_scanner(common)
    return driver,common,spec,composition,composition_binding,dependencies,imports


def select_gallery(driver,spec,row):
    mode=row['profile']['identity']['mode']
    if row['cue_condition'] not in ('CUES_OFF','REAL_ALIGNED_CUES'):raise ValueError('Long native only permits real cues or cues off')
    if row['gallery_condition']=='NONE':
        if mode!='none':raise ValueError('Gallery-none profile has a naming mode')
        return None,None
    if row['gallery_condition'] not in ('FIXED_ROTATION_A','FIXED_ROTATION_B') or row['enrollment_tier'] not in (5,15,30) or mode!='post_association':
        raise ValueError('Only exact registered fixed A/B gallery and tier; common30/scene-derived rosters are unsupported here')
    verify(spec['gallery_index']);index=read(spec['gallery_index']['path'])
    found=[r for r in index['rows'] if r['case_id'] is None and r['gallery_condition']==row['gallery_condition'] and r['enrollment_tier']==row['enrollment_tier']]
    if len(found)!=1:raise ValueError('One exact fixed gallery mapping required')
    gallery=found[0]['manifest'];verify(gallery);driver.fixed_gallery_row(index,gallery,row)
    return gallery,found[0]


def validate_plan(plan):
    if plan.get('observer_policy')!=observer_policy():raise ValueError('Exact fast observer policy required')
    if plan.get('protected_guard_policy')!=protected_guard_policy():raise ValueError('Exact structural native guard policy required')
    if plan['schema']!='s6c-epoch4-long-native-admission.v1' or plan['actual_execution_epoch']!='epoch4' or plan['source_composition_epoch']!='epoch2':raise ValueError('Execution/composition lineage differs')
    expected_report,expected_payload=output_roots(plan['namespace'])
    if Path(plan['report_root']).resolve()!=expected_report.resolve() or Path(plan['payload_root']).resolve()!=expected_payload.resolve():raise ValueError('New namespace differs')
    if plan['composition']['sha256']!=COMPOSITION_SHA or Path(plan['composition']['path']).resolve()!=COMPOSITION.resolve():raise ValueError('Source composition substituted')
    if plan['pending_output_reserve_bytes']!=PENDING_BYTES or plan['max_wall_sec']!=MAX_WALL_SEC or plan['worker_limit']!=1:raise ValueError('Resource/worker bound changed')
    if plan['duration_sec']!=1827.426625 or plan['duration_samples']!=29238826:raise ValueError('Exact complete original source duration required')
    if dt(plan['deadline_utc'])>DEADLINE:raise ValueError('Stage closure reserve violated')
    row=plan['profile_row']
    if row['asr_tap'] not in ('O0','O1') or row['identity_tap'] not in ('O0','O1'):raise ValueError('Unsupported exact native route')
    if (row['gallery_condition']=='NONE')!=(plan['gallery'] is None):raise ValueError('Gallery route mismatch')
    if row['gallery_condition'] not in ('NONE','FIXED_ROTATION_A','FIXED_ROTATION_B'):raise ValueError('Unadmitted long roster')
    if plan['allowed_overrides']!=list(ALLOWED_OVERRIDES):raise ValueError('Native override boundary changed')


@observer_entry
def prepare(args):
    driver,common,spec,m,composition,deps,imports=load_sources()
    root,payload=output_roots(args.namespace)
    if root.exists() or payload.exists():raise ValueError('Separate fresh native namespace required')
    row=driver.choose_profile(spec,args.candidate,args.asr_tap,args.identity_tap);gallery,gallery_row=select_gallery(driver,spec,row)
    deadline=dt(args.deadline_utc)
    if deadline<=datetime.now(timezone.utc)+timedelta(seconds=m['duration_sec']+row['profile']['runtime']['lane_drain_timeout_sec']+180) or deadline>DEADLINE:raise ValueError('No adequate bounded long-session time remains')
    deps.extend([bind(__file__),bind(Path(__file__).with_name('README_S6C_LONG_NATIVE_EPOCH4_FAST_V2.md'))])
    plan=dict(schema='s6c-epoch4-long-native-admission.v1',status='PREPARED_NO_MODELS_STARTED',created_utc=utc(),namespace=args.namespace,observer_policy=observer_policy(),protected_guard_policy=protected_guard_policy(),
        source_composition_epoch='epoch2',actual_execution_epoch='epoch4',composition=composition,execution_manifest=bind(REPORT/'EPOCH4_EXECUTION_MANIFEST.json'),
        imports=imports,dependencies=deps,profile_row=row,profile_sha256=digest(row),gallery=gallery,gallery_row=gallery_row,gallery_index=spec.get('gallery_index'),
        report_root=str(root),payload_root=str(payload),audio=m['audio'],pcm_sha256=m['pcm_sha256'],telemetry=m['telemetry'],duration_sec=m['duration_sec'],duration_samples=m['duration_samples'],
        pending_output_reserve_bytes=PENDING_BYTES,max_wall_sec=MAX_WALL_SEC,worker_limit=1,deadline_utc=deadline.isoformat(),allowed_overrides=list(ALLOWED_OVERRIDES),
        native_function_code_sha256=protected_identities(driver)['native']['code_sha256'],
        scope='One later actual epoch4 native host session using exact epoch2 concatenated PCM/cues. No regeneration, capture, RIR change or source copying. Original RESULT remains untouched and keeps its original composition binding.',
        lineage='Wrapper ADMISSION/CLOSURE binds actual epoch4 spec, exact profile and original native RESULT. Source-composition epoch2 must not be reported as execution epoch2.',
        limitations='Host concatenation of independently reset captures is not continuous hidden XVF state, HIL or CM5 qualification; observed sample gaps/maxima remain explicit. Resource guards run at admission, approximately every two seconds in the original sampling loop, and at terminal closure. Original synchronous model admission and bounded finalization join do not call the sampler; these gaps are not continuously guarded.')
    validate_plan(plan);plan['plan_key']=digest(plan)
    target=REPORT/'long_native_epoch4'/args.namespace/'MANIFEST.json'
    if target.exists():raise ValueError('Prepared plan already exists')
    common.save(target,plan,immutable=True)
    return dict(status='PREPARED_NO_MODELS_STARTED',manifest=bind(target),models_started=0)


def admit(path):
    plan,manifest_binding=read_bound(path);copy=dict(plan);wanted=copy.pop('plan_key')
    if digest(copy)!=wanted:raise ValueError('Plan digest differs')
    validate_plan(plan)
    if Path(path).resolve()!=(REPORT/'long_native_epoch4'/plan['namespace']/'MANIFEST.json').resolve():raise ValueError('Plan path differs')
    for b in plan['dependencies']:verify(b)
    driver,common,spec,m,composition,deps,imports=load_sources()
    if composition!=plan['composition'] or imports!=plan['imports'] or bind(REPORT/'EPOCH4_EXECUTION_MANIFEST.json')!=plan['execution_manifest']:raise ValueError('Admitted source/import graph differs')
    row=driver.choose_profile(spec,plan['profile_row']['candidate_id'],plan['profile_row']['asr_tap'],plan['profile_row']['identity_tap']);gallery,gallery_row=select_gallery(driver,spec,row)
    if row!=plan['profile_row'] or digest(row)!=plan['profile_sha256'] or gallery!=plan['gallery'] or gallery_row!=plan['gallery_row']:raise ValueError('Registered profile/roster changed')
    for key in ('audio','pcm_sha256','telemetry','duration_sec','duration_samples'):
        if plan[key]!=m[key]:raise ValueError('Original continuous source changed: '+key)
    if protected_identities(driver)['native']['code_sha256']!=plan['native_function_code_sha256']:raise ValueError('Protected original native function changed')
    return plan,driver,common,spec,m,manifest_binding


def quiet_processes(common):
    me=os.getpid();found={}
    for p in psutil.process_iter(['pid','cmdline','create_time']):
        if p.pid==me:continue
        if worker_command(p.info['cmdline']):
            if not state(p.pid,p.info['create_time']):continue
            found[p.pid]=dict(pid=p.pid,creation_time=p.info['create_time'],scope='study worker/coordinator command')
    for path in REPORT.glob('epoch*/workers/*.json'):
        value=common.read(path);pid=value.get('pid');created=value.get('creation_time')
        if pid!=me and state(pid,created):found[pid]=dict(pid=pid,creation_time=created,scope=str(path))
    if found:raise RuntimeError('Other study model workers remain live: '+json.dumps(list(found.values())))


def check_headroom(resources,reserve=0):
    for drive,minimum in (('C:',50*2**30),('G:',75*2**30)):
        if resources['disks'][drive]['free']<minimum+reserve:raise RuntimeError('Drive free-space/headroom floor violated: '+drive)
    if resources['ram_available_bytes']<12*2**30:raise RuntimeError('Common S6C12GiB available-RAM floor violated')
    size=resources.get('new_payload_bytes')
    if reserve and size is None:raise ValueError('Initial long-session reserve requires actual global accounting')
    if size is not None and size+reserve>120*2**30:raise RuntimeError('Global S6C120GiB output cap/headroom violated')


@contextmanager
def protected_override(driver,replacements):
    if set(replacements)!=set(ALLOWED_OVERRIDES):raise ValueError('Unexpected original-driver override')
    retained={name:(getattr(driver,name),getattr(driver,name).__code__) for name in PROTECTED}
    before=protected_identities(driver);old={name:getattr(driver,name) for name in replacements}
    try:
        for name,value in replacements.items():setattr(driver,name,value)
        assert_protected_unchanged(driver,before,'before execution')
        yield before
        assert_protected_unchanged(driver,before,'during execution')
    finally:
        for name,value in old.items():setattr(driver,name,value)
        assert_protected_unchanged(driver,before,'at restoration')


def release_lease(lock,target,expected):
    outcome=dict(status='RELEASE_FAILED',released=False,source=expected,requested_archive=str(target),archived_binding=None,error=None)
    try:
        verify(expected)
        if Path(expected['path']).resolve()!=lock.resolve() or target.exists():raise ValueError('Lease identity/archive namespace differs')
        lock.rename(target);outcome['released']=True
        outcome['status']='RELEASED_BINDING_UNVERIFIED'
        _,outcome['archived_binding']=read_bound(target,{**expected,'path':str(target.resolve())})
        outcome['status']='RELEASED'
    except Exception:
        outcome['error']=traceback.format_exc()
    return outcome


@observer_entry
def run(args):
    plan,driver,common,spec,m,manifest_binding=admit(args.manifest)
    admission,admission_binding=read_bound(args.quiet_admission)
    if admission.get('status')!='AUTHORIZED_FOR_QUIET_LONG_NATIVE' or admission.get('manifest_sha256')!=manifest_binding['sha256'] or admission.get('all_other_model_hil_work_stopped') is not True or admission.get('all_heavy_analysis_stopped') is not True:raise ValueError('Exact parent quiet-period admission required')
    deadline=min(dt(plan['deadline_utc']),dt(admission['expires_utc']),DEADLINE)
    if deadline<=datetime.now(timezone.utc)+timedelta(seconds=plan['duration_sec']+plan['profile_row']['profile']['runtime']['lane_drain_timeout_sec']+180):raise ValueError('Quiet period cannot contain the full bounded session')
    quiet_processes(common);initial=common.admit_work(full=True);check_headroom(initial,PENDING_BYTES)
    lock=REPORT/'PACED_QUIET_OWNER.json';owner=psutil.Process();identity=dict(pid=owner.pid,creation_time=owner.create_time(),argv=sys.argv)
    if lock.exists():raise ValueError('Existing quiet lease requires its explicit closure/resolution')
    target=Path(args.manifest).parent/'invocations'/uuid.uuid4().hex;target.mkdir(parents=True)
    started=time.monotonic();last_full=-1.;checks=[];result_binding=None;status='FAILED';error=None;before=protected_identities(driver)
    common.save(target/'ADMISSION.json',dict(status='ADMITTED_NOT_YET_COMPLETED',created_utc=utc(),owner=identity,manifest=manifest_binding,quiet_admission=admission_binding,
        source_composition=plan['composition'],source_composition_epoch='epoch2',actual_execution_manifest=plan['execution_manifest'],actual_execution_epoch='epoch4',profile_row=plan['profile_row'],gallery=plan['gallery'],imports=plan['imports'],resources=initial,protected_functions=before),immutable=True)
    # Durable source/owner admission precedes the exclusive lease, so even a
    # lease or subsequent admission-I/O failure has a resolvable owner record.
    with lock.open('x',encoding='utf-8') as handle:
        json.dump(dict(**identity,manifest=manifest_binding,kind='S6C_EPOCH4_LONG_NATIVE',admission=bind(target/'ADMISSION.json')),handle)
        handle.flush();os.fsync(handle.fileno())
    lease_binding=bind(lock)
    original_sample=driver.process_sample
    def guard(full=False,reserve=0):
        nonlocal last_full
        now=time.monotonic()
        if datetime.now(timezone.utc)>=deadline or now-started>MAX_WALL_SEC:raise TimeoutError('Wrapper quiet/time limit reached')
        full=full or last_full<0 or now-last_full>=20
        if full:quiet_processes(common)
        value=common.admit_work(full=full);check_headroom(value,reserve)
        if full:
            last_full=time.monotonic();record=dict(utc=utc(),elapsed_sec=now-started,resources=value);checks.append(record)
            common.save(target/'RESOURCE_HEARTBEAT.json',record)
        return value
    effective=deepcopy(m);effective['report_root']=plan['report_root'];effective['payload_root']=plan['payload_root']
    def load_override(native_args,assets=False):
        if assets is not True:raise ValueError('Original native asset-admission call required')
        return deepcopy(effective),spec,plan['composition']
    def sample_override(process):guard();return original_sample(process)
    replacements=dict(load_composition=load_override,admit_work=lambda full=False:guard(full=True,reserve=PENDING_BYTES),process_sample=sample_override)
    native_args=argparse.Namespace(version=plan['namespace'],epoch='epoch4',candidate=plan['profile_row']['candidate_id'],asr_tap=plan['profile_row']['asr_tap'],identity_tap=plan['profile_row']['identity_tap'],gallery=Path(plan['gallery']['path']) if plan['gallery'] else None)
    try:
        verify(manifest_binding);verify(admission_binding)
        with protected_override(driver,replacements):result_binding=driver.native(native_args)
        result,result_binding=read_bound(result_binding['path'],result_binding)
        if result['schema']!='s6c_continuous_paced_native.v1' or result['status']!='COMPLETE' or result['composition']!=plan['composition'] or result['profile']!=plan['profile_row'] or result['owner']['pid']!=owner.pid or result['owner']['creation_time']!=identity['creation_time']:raise ValueError('Native result identity/source does not match wrapper')
        if result['long_session_gallery_condition']!=plan['gallery_row'] or result['gallery_index']!=plan['gallery_index'] or result['source_duration_sec']!=plan['duration_sec'] or Path(plan['report_root']).resolve() not in Path(result_binding['path']).resolve().parents:raise ValueError('Native result roster/source/namespace does not match wrapper')
        guard(full=True);status='NATIVE_COMPLETE_RELEASE_PENDING'
    except BaseException:
        error=traceback.format_exc();raise
    finally:
        protected=protected_identities(driver)==before
        outcome=dict(status=status,created_utc=utc(),owner=identity,manifest=manifest_binding,admission=bind(target/'ADMISSION.json'),
            source_composition_epoch='epoch2',source_composition=plan['composition'],actual_execution_epoch='epoch4',actual_execution_manifest=plan['execution_manifest'],profile_row=plan['profile_row'],gallery=plan['gallery'],
            original_native_result=result_binding,original_result_not_rewritten=True,protected_functions_restored=protected,imports=plan['imports'],resource_checks=checks,error=error,
            process_scope='This records native outcome before lease release; current Python process can still be exiting. Final CLOSURE records the actual release attempt; external PID/creation inspection is required for process closure.',
            observation_scope='Resource scans can create irregular sample gaps/host overhead. Model admission and bounded finalization join do not call the periodic guard. Observed resource samples are not continuous maxima; no phonetic, GUI, physical XVF continuity or CM5 claim.')
        pre_release=common.save(target/'NATIVE_OUTCOME.json',outcome,immutable=True)
        release=release_lease(lock,target/'QUIET_LEASE_RELEASED.json',lease_binding)
        if release['status']=='RELEASED':status='NATIVE_COMPLETE_QUIET_LEASE_RELEASED' if status=='NATIVE_COMPLETE_RELEASE_PENDING' else 'NATIVE_FAILED_QUIET_LEASE_RELEASED'
        else:status='NATIVE_COMPLETE_LEASE_RELEASE_FAILED_OR_UNVERIFIED' if status=='NATIVE_COMPLETE_RELEASE_PENDING' else 'NATIVE_FAILED_LEASE_RELEASE_FAILED_OR_UNVERIFIED'
        common.save(target/'CLOSURE.json',{**outcome,'status':status,'created_utc':utc(),'pre_release_outcome':pre_release,'lease_release':release,
            'process_scope':'Actual lease-release outcome is recorded separately from native completion. This current Python process can still be exiting; external PID/creation inspection is required for process closure.'},immutable=True)
        if release['status']!='RELEASED':raise RuntimeError('Quiet lease release failed or could not be verified; inspect durable CLOSURE')
    return dict(status=status,closure=bind(target/'CLOSURE.json'),original_native_result=result_binding)


def checks():
    from types import SimpleNamespace
    from unittest.mock import patch
    import tempfile
    count=0
    for bad in ('v1','epoch4_../old','epoch4_x/y','epoch4_'):
        try:output_roots(bad)
        except ValueError:count+=1
        else:raise AssertionError('Unsafe old/output namespace admitted')
    r,p=output_roots('epoch4_test_fast_v2');assert r.parent==REPORT/'long_session' and p.parent==PAYLOAD/'long_session';count+=1
    sample=dict(disks={'C:':dict(free=60*2**30),'G:':dict(free=90*2**30)},ram_available_bytes=20*2**30,new_payload_bytes=100*2**30)
    check_headroom(sample,PENDING_BYTES);count+=1
    for mutate in ('C:','G:','ram','cap','missing'):
        bad=deepcopy(sample)
        if mutate in ('C:','G:'):bad['disks'][mutate]['free']=(50 if mutate=='C:' else 75)*2**30
        elif mutate=='ram':bad['ram_available_bytes']=12*2**30-1
        elif mutate=='cap':bad['new_payload_bytes']=120*2**30-1
        else:bad['new_payload_bytes']=None
        try:check_headroom(bad,PENDING_BYTES)
        except (RuntimeError,ValueError):count+=1
        else:raise AssertionError('Resource floor/reserve ignored')
    with patch.object(psutil,'Process',side_effect=psutil.AccessDenied(1)):
        try:state(1,1)
        except psutil.AccessDenied:count+=1
        else:raise AssertionError('Inaccessible owner falsely closed')
    for pid,created in ((True,1),(1,True),(0,1),(1,0),(1,float('nan')),(1,float('inf')),(1,None)):
        try:state(pid,created)
        except ValueError:count+=1
        else:raise AssertionError('Invalid owner identity admitted')
    with patch.object(psutil,'Process',side_effect=psutil.NoSuchProcess(1)):
        assert state(1,1) is False;count+=1
    with patch.object(psutil,'Process',return_value=SimpleNamespace(create_time=lambda:2.)):
        assert state(1,1) is False and state(1,2) is True;count+=1
    for name,args in (('s6c_long_session.py',['--mode','native']),('s6c_long_native_epoch4.py',['run']),('s6c_paced_b36_v1.py',['run']),('s6c_execution.py',['--worker']),('s6c_orchestrator_scan_v3.py',['run'])):
        assert worker_command(['python.exe',str(Path('C:/folder with spaces')/name),*args]);count+=1
    for argv in (['python.exe','s6c_long_session.py','--mode','fixtures'],['python.exe','s6c_long_native_epoch4.py','checks'],['python.exe','unrelated.py','run'],[]):
        assert not worker_command(argv);count+=1
    module=SimpleNamespace(**{name:(lambda:None) for name in PROTECTED+ALLOWED_OVERRIDES});original={k:getattr(module,k) for k in ALLOWED_OVERRIDES};before=protected_identities(module)
    with protected_override(module,{k:(lambda:1) for k in ALLOWED_OVERRIDES}):assert protected_identities(module)==before;count+=1
    assert all(getattr(module,k) is v for k,v in original.items());count+=1
    try:
        with protected_override(module,{'native':lambda:None}):pass
    except ValueError:count+=1
    else:raise AssertionError('Unregistered native override admitted')
    try:
        with protected_override(module,{k:(lambda:1) for k in ALLOWED_OVERRIDES}):raise RuntimeError('fixture')
    except RuntimeError:assert all(getattr(module,k) is v for k,v in original.items());count+=1
    fake_driver=SimpleNamespace(fixed_gallery_row=lambda index,binding,row:None)
    fake_row=dict(cue_condition='CUES_OFF',gallery_condition='NONE',enrollment_tier=None,profile=dict(identity=dict(mode='none')))
    assert select_gallery(fake_driver,{},fake_row)==(None,None);count+=1
    for key,value in (('cue_condition','SHIFTED_CUES'),('gallery_condition','COMMON30_FIXED_ROSTER_A'),('gallery_condition','ALL_EXPECTED_SETUP')):
        bad=deepcopy(fake_row);bad[key]=value
        try:select_gallery(fake_driver,{},bad)
        except ValueError:count+=1
        else:raise AssertionError('Unregistered long cue/gallery mode admitted')
    fixed=deepcopy(fake_row);fixed.update(gallery_condition='FIXED_ROTATION_A',enrollment_tier=15);fixed['profile']['identity']['mode']='post_association'
    mapping=dict(case_id=None,gallery_condition='FIXED_ROTATION_A',enrollment_tier=15,manifest=dict(path='fixture',bytes=0,sha256='fixture'))
    with patch(__name__+'.verify',lambda b:b),patch(__name__+'.read',lambda p:dict(rows=[mapping])):
        assert select_gallery(fake_driver,dict(gallery_index=dict(path='index')),fixed)==(mapping['manifest'],mapping);count+=1
        for key,value in (('gallery_condition','FIXED_ROTATION_B'),('enrollment_tier',5)):
            bad=deepcopy(fixed);bad[key]=value
            try:select_gallery(fake_driver,dict(gallery_index=dict(path='index')),bad)
            except ValueError:count+=1
            else:raise AssertionError('Wrong fixed roster/tier silently substituted')
    with tempfile.TemporaryDirectory(prefix='s6c_long_epoch4_') as temporary:
        root=Path(temporary);authority=root/'authority.json';authority.write_text('{"value":1}',encoding='utf-8')
        value,b=read_bound(authority);assert value=={'value':1} and b==bind(authority);count+=1
        oldstat=authority.stat();authority.write_text('{"value":2}',encoding='utf-8');os.utime(authority,ns=(oldstat.st_atime_ns,oldstat.st_mtime_ns))
        try:read_bound(authority,b)
        except ValueError:count+=1
        else:raise AssertionError('Changed authority with old mtime admitted')
        try:verify(b)
        except ValueError:count+=1
        else:raise AssertionError('Pre-native authority recheck missed changed bytes')
        lock=root/'lease.json';lock.write_text('{"pid":1}',encoding='utf-8');lb=bind(lock);archive=root/'released.json'
        with patch.object(Path,'rename',side_effect=PermissionError('injected sharing denial')):
            release=release_lease(lock,archive,lb)
        assert release['status']=='RELEASE_FAILED' and not release['released'] and lock.exists() and not archive.exists();count+=1
        release=release_lease(lock,archive,lb)
        assert release['status']=='RELEASED' and release['released'] and not lock.exists() and release['archived_binding']==bind(archive);count+=1
        lock.write_text('{"pid":2}',encoding='utf-8');release=release_lease(lock,root/'other.json',lb)
        assert release['status']=='RELEASE_FAILED' and not release['released'] and lock.exists();count+=1
    return dict(status='PASS_MODEL_FREE_CHECKS',checks=count,model_calls=0,native_calls=0,scope='Pure adapter guards only; real epoch/source admission is a separate prepare operation.')


@observer_entry
def source_checks():
    pure=checks();driver,common,spec,m,composition,deps,imports=load_sources()
    overlay=sys.modules['s6c_orchestrator_scan_v3'];original=read(REPORT/'EPOCH2_EXECUTION_MANIFEST.json');mutations=[]
    for field in ('assets','versions','python','input_index','scene_manifest','state_policy'):
        changed=deepcopy(spec);changed[field]='fixture_changed'
        try:overlay.compatible_native(changed,original)
        except ValueError:mutations.append(field)
        else:raise AssertionError('Changed native dependency admitted: '+field)
    for name in ('s6c_execution.py','s6c_common.py','runtime.py'):
        changed=deepcopy(spec);matches=[b for b in changed['execution_files'] if Path(b['path']).name==name]
        if len(matches)!=1:raise AssertionError('Exact changed-code fixture must identify one file')
        matches[0]['sha256']='0'*64
        try:overlay.compatible_native(changed,original)
        except ValueError:mutations.append(name)
        else:raise AssertionError('Changed native code admitted: '+name)
    prior_path=REPORT/'long_native_epoch4/SOURCE_CHECKS_V1.json';prior,prior_binding=read_bound(prior_path);prior_sources=[]
    for name in ('s6c_long_native_epoch4.py','README_S6C_LONG_NATIVE_EPOCH4.md'):
        old=next(b for b in prior['dependencies'] if Path(b['path']).name==name)
        snapshot=bind(STAGING/'long_native_epoch4/pre_review_repairs_v1'/name)
        if any(old[k]!=snapshot[k] for k in ('sha256','bytes')):raise ValueError('Historical source-check bytes lack exact preserved resolver')
        prior_sources.append(dict(original=old,snapshot=snapshot))
    receipt=dict(schema='s6c-epoch4-long-fast-observer-source-checks.v1',status='PASS_MODEL_FREE_SOURCE_ADMISSION',created_utc=utc(),pure_checks=pure,
        previous_source_checks=prior_binding,preserved_previous_sources=prior_sources,
        correction_scope='Observer-only fresh scandir installation/restoration with unchanged limits, cadence and scientific native body. All original source admission and source bytes preserved.',
        actual_source_checks=['pinned epoch2 and epoch4 manifests','exact APP/worker/common/assets/environment compatibility','live long/prefix file paths and frozen common import identities','original complete PCM/cues/source-composition bindings'],
        rejected_dependency_mutations=mutations,model_calls=0,native_calls=0,composition=composition,execution_manifest=bind(REPORT/'EPOCH4_EXECUTION_MANIFEST.json'),imports=imports,
        protected_functions=protected_identities(driver),dependencies=deps+[bind(__file__),bind(Path(__file__).with_name('README_S6C_LONG_NATIVE_EPOCH4_FAST_V2.md'))],
        duration_sec=m['duration_sec'],duration_samples=m['duration_samples'],scope='Source/guard checks only; no candidate was selected and no native run or current quiet/storage admission is claimed.')
    return common.save(REPORT/'long_native_epoch4/observer_fast_v2/SOURCE_CHECKS_V1.json',receipt,immutable=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);parser.add_argument('action',choices=('prepare','run','checks','source-checks'))
    parser.add_argument('--namespace');parser.add_argument('--candidate');parser.add_argument('--asr-tap',choices=('O0','O1'));parser.add_argument('--identity-tap',choices=('O0','O1'));parser.add_argument('--deadline-utc')
    parser.add_argument('--manifest',type=Path);parser.add_argument('--quiet-admission',type=Path);args=parser.parse_args()
    if args.action=='prepare' and any(getattr(args,k) is None for k in ('namespace','candidate','asr_tap','identity_tap','deadline_utc')):parser.error('prepare requires namespace, exact candidate/ASR/identity taps and deadline')
    if args.action=='run' and (args.manifest is None or args.quiet_admission is None):parser.error('run requires manifest and exact quiet-admission')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
    print(json.dumps({'prepare':lambda:prepare(args),'run':lambda:run(args),'checks':checks,'source-checks':source_checks}[args.action](),indent=2))
