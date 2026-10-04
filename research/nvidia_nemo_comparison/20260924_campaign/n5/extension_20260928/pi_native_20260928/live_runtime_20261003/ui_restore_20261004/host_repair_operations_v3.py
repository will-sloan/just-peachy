"""Hash-bound actual nested supervisor records; see README_HOST_REPAIR_OPERATIONS_V3.md."""
import psutil
psutil.Process().cpu_affinity([14])
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import time
import uuid

PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
NATIVE_PREFIX='/home/peachyprototype/JustPeachy/research/nemotron-20260928/'
GUI_PATH=re.compile(r'production-data-readback/unit-owners/[0-9a-f]{32}/UNIT_OWNERSHIP.json')
KEYS={'control_group','deadline_monotonic','idle_timeout_seconds','invocation_id','main_pid','owner','runtime_max_seconds','unit'}
WATCHDOG_KEYS=KEYS-{'deadline_monotonic','idle_timeout_seconds'}
early=PRIVATE/'audit-preparation'/('ui-repair-dispatch-v3-'+uuid.uuid4().hex)
early.mkdir()
me=psutil.Process()
with (early/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=[14]),stream)
    stream.flush();os.fsync(stream.fileno())
started=time.monotonic()


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate actual mirrored field')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))


def read(path,maximum=32*1024**2):
    if time.monotonic()-started>600:raise TimeoutError('Finite host mirror binding review')
    path=Path(path);before=path.lstat()
    if (path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_size>maximum
        or before.st_nlink!=1):raise ValueError('Bounded actual regular mirror input required: '+str(path))
    raw=path.read_bytes();after=path.stat()
    if len(raw)!=before.st_size or (before.st_ino,before.st_mtime_ns,before.st_size)!=(after.st_ino,after.st_mtime_ns,after.st_size):
        raise ValueError('Actual mirror input changed: '+str(path))
    return raw


def identity(value):
    if (type(value) is not dict or set(value)!={'pid','start_ticks','boot_id'}
        or any(type(value[key]) is not int or value[key]<=0 for key in ('pid','start_ticks'))
        or type(value['boot_id']) is not str or re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',value['boot_id']) is None):
        raise ValueError('Exact actual process identity required')
    return value


def typed_unit(value,kind):
    expected=KEYS if kind=='finite_gui' else WATCHDOG_KEYS
    if type(value) is not dict or set(value)!=expected:
        raise ValueError('Exact nested unit schema required')
    identity(value['owner'])
    if type(value['main_pid']) is not int or value['main_pid']!=value['owner']['pid']:
        raise ValueError('Nested MainPID differs from its process identity')
    pattern=r'jp-v29-[0-9a-f]{32}\.service' if kind=='finite_gui' else r'jp-v29-production-idle-01-watchdog\.service'
    if (type(value['unit']) is not str or re.fullmatch(pattern,value['unit']) is None
        or type(value['invocation_id']) is not str or re.fullmatch('[0-9a-f]{32}',value['invocation_id']) is None
        or value['control_group']!='/user.slice/user-1000.slice/user@1000.service/app.slice/'+value['unit']):
        raise ValueError('Exact nested unit invocation/cgroup required')
    for key in ('runtime_max_seconds',) if kind=='watchdog' else ('runtime_max_seconds','deadline_monotonic','idle_timeout_seconds'):
        if type(value[key]) not in (int,float) or not math.isfinite(value[key]) or value[key]<=0:
            raise ValueError('Finite typed nested lifetime required')
    if value['runtime_max_seconds']!=(120 if kind=='watchdog' else 7200) or kind=='finite_gui' and value['idle_timeout_seconds']!=300:
        raise ValueError('Exact observed watchdog120 / GUI7200 idle300 lifetime required')
    return value


def actual_nested_unit_map():
    pins={};counts={};mirrors=owner_records=duplicates=0
    paths=list(PRIVATE.glob('*-monitor-*/RESULT.json'))
    paths.extend(path for path in PRIVATE.glob('production-backup-*-reconcile-*/guard-monitor/RESULT.json')
        if re.fullmatch(r'production-backup-\d{2}-reconcile-\d{2}',path.parents[1].name))
    for result_path in sorted(set(paths)):
        result=strict(read(result_path,262144))
        if result.get('status')!='FULL_CLOSED_OUTPUT_MIRRORED':continue
        mirror=result_path.parent;job=result['job']
        if (job.get('schema')!='just-peachy.native-component-job.v1'
            or type(job.get('output_root')) is not str or not job['output_root'].startswith(NATIVE_PREFIX+'live-runtime-tests-20261003/')):
            raise ValueError('Actual finite closed job provenance required')
        relative=job['output_root'][len(NATIVE_PREFIX):]
        if re.fullmatch(r'live-runtime-tests-20261003/[a-z0-9-]{4,64}',relative) is None:
            raise ValueError('Canonical actual native output root required')
        rows=strict(read(mirror/'MIRROR_MANIFEST.json'));complete=strict(read(mirror/'MIRROR_COMPLETE.json',262144))
        if (type(rows) is not list or not 1<=len(rows)<=4096 or complete.get('kind')!='COMPLETE'
            or complete.get('files')!=len(rows) or complete.get('mirror_scope')!='all_regular_output_files'
            or complete.get('manifest_sha256')!=sha(encoded(rows))):
            raise ValueError('Complete exact independent mirror inventory required')
        outer=complete['closure']
        if (any(outer.get(key)!=job[key] for key in ('unit','invocation_id','control_group','owner'))
            or any(outer.get(key) is not True for key in ('closed','exact_owner_gone','cgroup_empty'))):
            raise ValueError('Independent closed outer job required before nested binding')
        identity(job['owner']);entries={}
        for row in rows:
            name=row['path'];part=PurePosixPath(name)
            if (type(name) is not str or part.is_absolute() or '..' in part.parts or '\\' in name
                or str(part)!=name or name in entries):raise ValueError('Canonical complete mirrored members required')
            entries[name]=row
        def member(name):
            entry=entries.get(name)
            if entry is None:raise ValueError('Required independent mirrored closure/owner missing: '+name)
            raw=read(mirror/'closed-output'/name,16384)
            if entry['identity']['bytes']!=len(raw) or entry['sha256']!=sha(raw):
                raise ValueError('Actual nested receipt readback differs: '+name)
            return raw,strict(raw)
        # Read/hash every actual owner-like receipt from every complete mirror.
        # Existing direct/source/journal schemas remain bound by driver v6;
        # only the two documented unit forms below receive new exact pins.
        for name in sorted(entries):
            if 'OWNER' not in PurePosixPath(name).name or not name.endswith('.json'):continue
            raw,value=member(name);owner_records+=1
            fields=','.join(sorted(value)) if type(value) is dict else type(value).__name__
            counts[fields]=counts.get(fields,0)+1
            if name=='UNIT_OWNERSHIP.json':continue
            if not name.endswith('/UNIT_OWNERSHIP.json'):continue
            if relative!='live-runtime-tests-20261003/production-idle-01':
                raise ValueError('Unreviewed actual nested supervisor path: '+relative+'/'+name)
            if GUI_PATH.fullmatch(name):
                kind='finite_gui';typed_unit(value,kind)
                _,closure=member(name.removesuffix('UNIT_OWNERSHIP.json')+'UNIT_CLOSURE.json')
                _,registered=member(name.removesuffix('UNIT_OWNERSHIP.json')+'main/REGISTERED_OWNER.json')
                _,exit_row=member(name.removesuffix('UNIT_OWNERSHIP.json')+'SERVICE_EXIT.json')
                if (closure.get('ownership')!=value or closure.get('unit')!=value['unit'] or registered!=value['owner']
                    or any(closure.get(key) is not True for key in ('main_exact_owner_gone','unit_stopped','all_registered_source_owners_gone'))
                    or closure.get('sources')!=[] or closure.get('service_exit')!=exit_row
                    or any(exit_row.get(key)!=value[key] for key in ('unit','invocation_id','owner'))
                    or type(exit_row.get('exit_code')) is not int or exit_row['exit_code']!=0 or exit_row.get('error') is not None
                    or exit_row.get('package_manifest_sha256')!=job['package_manifest_sha256']):
                    raise ValueError('Exact independent closed GUI readback proof required')
            elif name=='watchdog/UNIT_OWNERSHIP.json':
                kind='watchdog';typed_unit(value,kind)
                _,closure=member('WATCHDOG_CLOSURE.json');_,registered=member('watchdog/OWNER.json')
                _,exit_row=member('watchdog/WATCHDOG_EXIT.json')
                if (closure.get('ownership')!=value or registered!=value['owner']
                    or any(closure.get(key) is not True for key in ('exact_owner_gone','cgroup_empty'))
                    or exit_row.get('owner')!=value['owner'] or exit_row.get('control_complete') is not True
                    or exit_row.get('error') is not None):
                    raise ValueError('Exact independent closed watchdog proof required')
            else:raise ValueError('Unreviewed actual nested supervisor path: '+relative+'/'+name)
            key=relative+'/'+name
            pin=dict(sha256=sha(raw),bytes=len(raw),owner=value['owner'],document=value,kind=kind)
            if key in pins:
                duplicates+=1
                if pins[key]!=pin:raise ValueError('Conflicting independently restored nested supervisor bytes')
            pins[key]=pin
        mirrors+=1
    if len(pins)!=2:
        raise ValueError('Exactly the two actual production-idle nested supervisor proofs are required')
    summary=dict(complete_mirrors_read=mirrors,owner_records_read=owner_records,
        duplicate_exact_nested_pins=duplicates,owner_field_shape_counts=counts,
        actual_nested_unit_paths=sorted(pins),actual_nested_unit_map_sha256=sha(encoded(pins)),
        native_action=False,unknown_owner_schemas_accepted=False)
    return pins,summary


def put(name,value):
    raw=encoded(value)
    if len(raw)>262144:raise ValueError('Compact host binding receipt limit')
    with (early/name).open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short exact binding receipt write')
        stream.flush();os.fsync(stream.fileno())
    if read(early/name)!=raw:raise OSError('Host binding receipt readback differs')


sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import host_operations_v6 as driver
original=driver.bind_native_owner_references


def bind(native,new_owners,unit_owners):
    pins,summary=actual_nested_unit_map()
    put('ACTUAL_NESTED_UNIT_MAP.json',pins);put('ACTUAL_NESTED_UNIT_REVIEW.json',summary)
    native=original(native,new_owners,unit_owners)
    boundary='owner_hash=hashlib.sha256();count=0;typed=0;all_ids=set()'
    if native.count(boundary)!=1:raise ValueError('Exact native owner map insertion boundary')
    native=native.replace(boundary,'ACTUAL_NESTED_UNIT_OWNERS='+repr(pins)+'\n'+boundary)
    anchor=" elif 'owner' in v:\n  assert rel in NESTED"
    if native.count(anchor)!=1:raise ValueError('Exact native nested-owner decoder boundary')
    addition=r'''
 elif rel in ACTUAL_NESTED_UNIT_OWNERS:
  import math
  expected=ACTUAL_NESTED_UNIT_OWNERS[rel]
  assert len(raw)==expected['bytes'] and sha(raw)==expected['sha256'] and v==expected['document'], ('Changed actual nested unit bytes',rel)
  identity(v['owner'])
  assert type(v['main_pid']) is int and v['main_pid']==v['owner']['pid']
  assert type(v['invocation_id']) is str and re.fullmatch('[0-9a-f]{32}',v['invocation_id'])
  assert v['control_group']=='/user.slice/user-1000.slice/user@1000.service/app.slice/'+v['unit']
  if expected['kind']=='finite_gui':
   assert re.fullmatch(r'live-runtime-tests-20261003/production-idle-01/production-data-readback/unit-owners/[0-9a-f]{32}/UNIT_OWNERSHIP.json',rel)
   assert set(v)=={'control_group','deadline_monotonic','idle_timeout_seconds','invocation_id','main_pid','owner','runtime_max_seconds','unit'}
   assert re.fullmatch(r'jp-v29-[0-9a-f]{32}\.service',v['unit']) and v['runtime_max_seconds']==7200 and v['idle_timeout_seconds']==300
   assert all(type(v[key]) in (int,float) and math.isfinite(v[key]) and v[key]>0 for key in ('deadline_monotonic','runtime_max_seconds','idle_timeout_seconds'))
  else:
   assert expected['kind']=='watchdog' and rel=='live-runtime-tests-20261003/production-idle-01/watchdog/UNIT_OWNERSHIP.json'
   assert set(v)=={'control_group','invocation_id','main_pid','owner','runtime_max_seconds','unit'}
   assert v['unit']=='jp-v29-production-idle-01-watchdog.service' and type(v['runtime_max_seconds']) is int and v['runtime_max_seconds']==120
  observed=ticks(v['owner']['pid'])
  assert not(v['owner']['boot_id']==boot and observed==v['owner']['start_ticks']), ('Actual nested owner remains live',rel,v['owner'])
  v=v['owner']
'''
    native=native.replace(anchor,addition+anchor)
    unknown="  assert rel in NESTED and set(v)=={'owner','policy_sha256','slot','utc','purpose'}"
    if native.count(unknown)!=1:raise ValueError('Exact unknown nested owner diagnostic boundary')
    native=native.replace(unknown,unknown+", ('Unbound nested completed owner',rel,sorted(v))")
    compile(native,'<strict-repair-v3-native-preread>','exec')
    return native


driver.bind_native_owner_references=bind
if sys.argv[1:]==['--host-review']:
    pins,summary=actual_nested_unit_map()
    put('ACTUAL_NESTED_UNIT_MAP.json',pins);put('ACTUAL_NESTED_UNIT_REVIEW.json',summary)
    print(json.dumps(dict(output=str(early),**summary)))
else:
    driver.main()
