"""Exact closed backup09 guard binding; see README_HOST_STABILIZATION_OPERATIONS_V5.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ctypes
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
GUI_PATH=re.compile(r'production-data-readback/(?:unit-owners/[0-9a-f]{32}/)?UNIT_OWNERSHIP.json')
KEYS={'control_group','deadline_monotonic','idle_timeout_seconds','invocation_id','main_pid','owner','runtime_max_seconds','unit'}
WATCHDOG_KEYS=KEYS-{'deadline_monotonic','idle_timeout_seconds'}
early=PRIVATE/'audit-preparation'/('ui-repair-dispatch-v3-'+uuid.uuid4().hex)
early.mkdir()
me=psutil.Process()
_kernel=ctypes.WinDLL('kernel32',use_last_error=True)
_kernel.GetCurrentProcess.restype=ctypes.c_void_p
_kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
_times=[ctypes.c_ulonglong() for _ in range(4)]
if not _kernel.GetProcessTimes(_kernel.GetCurrentProcess(),*(ctypes.byref(item) for item in _times)):
    raise ctypes.WinError(ctypes.get_last_error())
with (early/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(schema='just-peachy.host-registered-owner.v1',pid=me.pid,cpu=14,
        affinity_mask=16384,creation_filetime=_times[0].value,
        create_time=(_times[0].value-116444736000000000)/10000000),stream)
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
    expected=(KEYS|{'lifetime_policy'}) if kind=='manual_gui' else KEYS if kind=='finite_gui' else WATCHDOG_KEYS
    if type(value) is not dict or set(value)!=expected:
        raise ValueError('Exact nested unit schema required')
    identity(value['owner'])
    if type(value['main_pid']) is not int or value['main_pid']!=value['owner']['pid']:
        raise ValueError('Nested MainPID differs from its process identity')
    pattern=r'jp-v29-[0-9a-f]{32}\.service' if kind in ('finite_gui','manual_gui') else r'jp-v29-production-idle-(?:01|03|04)-watchdog\.service'
    if (type(value['unit']) is not str or re.fullmatch(pattern,value['unit']) is None
        or type(value['invocation_id']) is not str or re.fullmatch('[0-9a-f]{32}',value['invocation_id']) is None
        or value['control_group']!='/user.slice/user-1000.slice/user@1000.service/app.slice/'+value['unit']):
        raise ValueError('Exact nested unit invocation/cgroup required')
    if kind=='manual_gui':
        if (value['runtime_max_seconds'] is not None or value['deadline_monotonic'] is not None or
            value['lifetime_policy']!='manual_stop_storage_guarded' or type(value['idle_timeout_seconds']) is not int or value['idle_timeout_seconds']!=300):
            raise ValueError('Exact manual-Stop storage-guarded lifetime required')
        return value
    for key in ('runtime_max_seconds',) if kind=='watchdog' else ('runtime_max_seconds','deadline_monotonic','idle_timeout_seconds'):
        if type(value[key]) not in (int,float) or not math.isfinite(value[key]) or value[key]<=0:
            raise ValueError('Finite typed nested lifetime required')
    if value['runtime_max_seconds']!=(120 if kind=='watchdog' else 7200) or kind=='finite_gui' and value['idle_timeout_seconds']!=300:
        raise ValueError('Exact observed watchdog120 / GUI7200 idle300 lifetime required')
    return value


def actual_backup_guard(job,complete,member):
    """Only the independently closed actual backup09 unit, never generic jobs."""
    expected_owner=dict(boot_id='0561d730-3cad-48e0-940a-fe3930c89665',pid=16609,start_ticks=927956)
    expected_unit='jp-v29-production-backup-09.service'
    expected_invocation='872683315993488f8085a51281b735f9'
    if (job.get('output_root')!=NATIVE_PREFIX+'live-runtime-tests-20261003/production-backup-09'
        or job.get('owner')!=expected_owner or job.get('unit')!=expected_unit
        or job.get('invocation_id')!=expected_invocation
        or job.get('package_manifest_sha256')!='1cb7b8c3ac07d7975b2a31585f94b6402d419a12a128b05758ed7af644319f4c'
        or complete.get('manifest_sha256')!='39cda53626233e7276177a7156784c68f6e90814331f335f9f9bb54746220cc1'
        or complete.get('files')!=21):
        raise ValueError('Exact independently mirrored backup09 job required')
    raw,value=member('UNIT_OWNERSHIP.json')
    job_raw,backed_job=member('JOB.json')
    _,registered=member('OWNER.json')
    exit_raw,exit_row=member('JOB_EXIT.json')
    _,released=member('SNAPSHOT_RELEASED.json')
    expected=dict(control_group='/user.slice/user-1000.slice/user@1000.service/app.slice/'+expected_unit,
        deadline_monotonic=9754.698553087,idle_timeout_seconds=300,
        invocation_id=expected_invocation,main_pid=16609,owner=expected_owner,
        runtime_max_seconds=480,unit=expected_unit)
    if (sha(raw)!='cf61f3b44b8a096cfa20c6e7bc8e929dc004ed94f92a4c97ef82bcf5988ab0f2'
        or len(raw)!=405 or type(value) is not dict or set(value)!=KEYS or value!=expected
        or sha(job_raw)!='92d4481cda410194d1c603035594345d64e44d0d2a943958806f9d05982ddc2d'
        or backed_job!=job or registered!=expected_owner
        or sha(exit_raw)!='80cd0b791275d5ab989ed9039ac0335c02f6584cbdd7fb61f98af62a7af7a051'
        or type(value['main_pid']) is not int or value['main_pid']!=value['owner']['pid']
        or type(value['runtime_max_seconds']) is not int or value['runtime_max_seconds']!=480
        or type(value['idle_timeout_seconds']) is not int or value['idle_timeout_seconds']!=300
        or type(value['deadline_monotonic']) not in (int,float)
        or not math.isfinite(value['deadline_monotonic']) or value['deadline_monotonic']<=0):
        raise ValueError('Exact backup09 supervisor document and provenance required')
    identity(value['owner'])
    closure=complete['closure']
    if (any(closure.get(key)!=job[key] for key in ('unit','invocation_id','control_group','owner'))
        or any(closure.get(key) is not True for key in ('closed','exact_owner_gone','cgroup_empty'))
        or closure.get('job_exit')!=exit_row or exit_row.get('owner')!=expected_owner
        or exit_row.get('unit')!=expected_unit or exit_row.get('invocation_id')!=expected_invocation
        or type(exit_row.get('natural_returncode')) is not int or exit_row['natural_returncode']!=0
        or exit_row.get('leases_released') is not True or exit_row.get('error') is not None
        or exit_row.get('output_budget_failure') is not None
        or released.get('owner')!=expected_owner or released.get('hardware_lease_released') is not True
        or released.get('source_verified') is not True or released.get('error') is not None):
        raise ValueError('Exact independent natural0/closed/cgroup/lease backup09 proof required')
    return dict(sha256=sha(raw),bytes=len(raw),owner=value['owner'],document=value,kind='backup_guard')


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
        if relative=='live-runtime-tests-20261003/production-backup-09':
            key=relative+'/UNIT_OWNERSHIP.json'
            pin=actual_backup_guard(job,complete,member)
            if key in pins:
                duplicates+=1
                if pins[key]!=pin:raise ValueError('Conflicting exact backup09 supervisor bytes')
            pins[key]=pin
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
            if relative not in ('live-runtime-tests-20261003/production-idle-01','live-runtime-tests-20261003/production-idle-03','live-runtime-tests-20261003/production-idle-04'):
                raise ValueError('Unreviewed actual nested supervisor path: '+relative+'/'+name)
            if GUI_PATH.fullmatch(name):
                kind='manual_gui' if relative=='live-runtime-tests-20261003/production-idle-04' else 'finite_gui';typed_unit(value,kind)
                if kind=='manual_gui' and job['package_manifest_sha256']!='9abaaaffe35d328fd97f5fc47f1f5b938803705dffb728c5d804d225a646ba6e':
                    raise ValueError('Exact observed build21 manual GUI binding required')
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
    if len(pins)!=7:
        raise ValueError('Exactly seven independently mirrored idle01/idle03/idle04/backup09 supervisor proofs are required')
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
  if expected['kind']=='manual_gui':
   assert re.fullmatch(r'live-runtime-tests-20261003/production-idle-04/production-data-readback/unit-owners/[0-9a-f]{32}/UNIT_OWNERSHIP.json',rel)
   assert set(v)=={'control_group','deadline_monotonic','idle_timeout_seconds','invocation_id','lifetime_policy','main_pid','owner','runtime_max_seconds','unit'}
   assert re.fullmatch(r'jp-v29-[0-9a-f]{32}\.service',v['unit']) and v['runtime_max_seconds'] is None and v['deadline_monotonic'] is None
   assert v['lifetime_policy']=='manual_stop_storage_guarded' and type(v['idle_timeout_seconds']) is int and v['idle_timeout_seconds']==300
  elif expected['kind']=='finite_gui':
   assert re.fullmatch(r'live-runtime-tests-20261003/production-idle-(?:01|03)/production-data-readback/(?:unit-owners/[0-9a-f]{32}/)?UNIT_OWNERSHIP.json',rel)
   assert set(v)=={'control_group','deadline_monotonic','idle_timeout_seconds','invocation_id','main_pid','owner','runtime_max_seconds','unit'}
   assert re.fullmatch(r'jp-v29-[0-9a-f]{32}\.service',v['unit']) and v['runtime_max_seconds']==7200 and v['idle_timeout_seconds']==300
   assert all(type(v[key]) in (int,float) and math.isfinite(v[key]) and v[key]>0 for key in ('deadline_monotonic','runtime_max_seconds','idle_timeout_seconds'))
  elif expected['kind']=='backup_guard':
   assert rel=='live-runtime-tests-20261003/production-backup-09/UNIT_OWNERSHIP.json'
   assert set(v)=={'control_group','deadline_monotonic','idle_timeout_seconds','invocation_id','main_pid','owner','runtime_max_seconds','unit'}
   assert v['unit']=='jp-v29-production-backup-09.service' and v['invocation_id']=='872683315993488f8085a51281b735f9'
   assert v['owner']=={'boot_id':'0561d730-3cad-48e0-940a-fe3930c89665','pid':16609,'start_ticks':927956}
   assert type(v['runtime_max_seconds']) is int and v['runtime_max_seconds']==480
   assert type(v['idle_timeout_seconds']) is int and v['idle_timeout_seconds']==300
   assert type(v['deadline_monotonic']) in (int,float) and math.isfinite(v['deadline_monotonic']) and v['deadline_monotonic']==9754.698553087
  else:
   assert expected['kind']=='watchdog' and re.fullmatch(r'live-runtime-tests-20261003/production-idle-(?:01|03|04)/watchdog/UNIT_OWNERSHIP.json',rel)
   assert set(v)=={'control_group','invocation_id','main_pid','owner','runtime_max_seconds','unit'}
   assert re.fullmatch(r'jp-v29-production-idle-(?:01|03|04)-watchdog\.service',v['unit']) and type(v['runtime_max_seconds']) is int and v['runtime_max_seconds']==120
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
original_lifetime_decoder=driver.bounded_lifetime_decoder


def lifetime_decoder(raw):
    # Preserve the actual completed package-builder registration. Its kernel
    # FILETIME/CPU14 values are correct, but that source omitted a schema tag.
    # This exact path+SHA is the sole new historical format correction.
    path='live-runtime-20261003/audit-preparation/classic-package-repair-3b5aac854f7b454686eb770ffe218054/REGISTERED_OWNER.json'
    owner_raw=read(PRIVATE.parent/path,16384)
    expected=dict(affinity_mask=16384,cpu=14,create_time=1791154855.2343333,
                  creation_filetime=134356284552343333,pid=62896)
    pin='227202a3ea4211aa5cdbd4ce6da5db8f612e4a279dddf3ccc2b2e422c8f224b7'
    if strict(owner_raw)!=expected or sha(owner_raw)!=pin:
        raise ValueError('Exact completed builder owner bytes changed')
    text=raw.decode()
    if not text.startswith('HOST_OWNER_FORMAT_CORRECTIONS='):
        raise ValueError('Exact retained host correction initialization required')
    first,rest=text.split('\n',1)
    correction={path:dict(original=expected,sha256=pin)}
    actual_checks = [
        ('full-application-check-d0b2bbb0ba27441ea517a671d9787aea',
         dict(affinity_mask=16384,cpu=14,create_time=1791168448.8830986,creation_filetime=134356420488830986,pid=28460),
         'a335d6e20ada92a85857a41c6b3807091233937ab96e98a425f949091a8f20b4'),
        ('full-application-check-005a6fcbb489489e840f1c8097ab139d',
         dict(affinity_mask=16384,cpu=14,create_time=1791168691.7550085,creation_filetime=134356422917550084,pid=74352),
         'ec846b416fd707eb6cdb79428562cffe9fc21055069c1b6e84f71f02ee6dab20')]
    actual_checks.append((
        'stabilization-native-preparation-870200b178b34a0c97520681331aaad2',
        dict(schema='just-peachy.host-registered-owner.v1',cpu=14,
             creation_filetime=134357079045678874,pid=15952,create_time=1791234304.567),
        '71afa47324dc53ac36a5cad8d7a38d55e9c9a8a3f9843bf65c4f2bb0e94cc2c5'))
    actual_checks.extend([
        ('stabilization-v5-source-1c0d89648d9a40369f513fb637c8f3fe',
         dict(affinity_mask=16384,cpu=14,create_time=1791241316.2558472,
              creation_filetime=134357149162558473,pid=67144),
         'c80b43363ca5b02a30ace6dd363fec1e76bded29c5ce8f507aded91c81a600e3'),
        ('stabilization-v5-source-corrected-01',
         dict(affinity_mask=16384,cpu=14,create_time=1791241347.6644866,
              creation_filetime=134357149476644866,pid=68864),
         '82eb32e9297fbd45ed44aace6cf56d662fbe339c6260e0c3818e23d853a240e5'),
        ('speech19-independent-restore-82def6dd72ec44f58a86713a36075d6a',
         dict(affinity_mask=16384,cpu=14,create_time=1791241731.9844444,
              creation_filetime=134357153319844443,pid=45048),
         'e3a376a29d07d6c2a32f4fa8b18430f5f3cedf816185c8b44531f03420bef271')])
    for label, document, owner_sha in actual_checks:
        relative = 'live-runtime-20261003/audit-preparation/'+label+'/REGISTERED_OWNER.json'
        raw_owner = read(PRIVATE.parent/relative,16384)
        if strict(raw_owner)!=document or sha(raw_owner)!=owner_sha:
            raise ValueError('Exact original source-check owner changed')
        correction[relative]=dict(original=document,sha256=owner_sha)
    return coordinator_filetime_source(original_lifetime_decoder((first+'\nHOST_OWNER_FORMAT_CORRECTIONS.update('+repr(correction)+')\n'+rest).encode()))


def coordinator_filetime_source(raw):
    """Modify only decoder self-exclusion; preserve exact typed-owner provenance."""
    text=raw.decode('utf-8')
    replacements=(
      ('    me=psutil.Process()\n', '''    me=psutil.Process()
    import ctypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    process_times=[ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(kernel.GetCurrentProcess(),*(ctypes.byref(item) for item in process_times)):
        raise ctypes.WinError(ctypes.get_last_error())
    current_creation_filetime=process_times[0].value
'''),
      ('                    host[(pid,float(created))]=None\n', '''                    key=(pid,float(created))
                    if key not in host:host[key]=set()
                    if (pk=='pid' and relative.startswith('live-runtime-20261003/audit-preparation/')
                        and path.name=='REGISTERED_OWNER.json' and 'creation_filetime' in value):
                        host[key].add(value['creation_filetime'])
'''),
      ('    for pid,created in host:\n        if pid==me.pid and created==me.create_time():continue\n', '''    for (pid,created),filetimes in host.items():
        if pid==me.pid and ((filetimes and filetimes=={current_creation_filetime})
            or (not filetimes and created==me.create_time())):continue
'''))
    for before,after in replacements:
        if text.count(before)!=1:raise ValueError('Exact current-coordinator decoder boundary required')
        text=text.replace(before,after)
    restored=text
    for before,after in reversed(replacements):
        if restored.count(after)!=1:raise ValueError('Exact reversible current-coordinator boundary required')
        restored=restored.replace(after,before)
    if restored!=raw.decode('utf-8'):raise ValueError('Unrelated decoder change')
    compile(text,'<exact-current-coordinator-filetime-decoder>','exec')
    return text.encode('utf-8')


driver.bounded_lifetime_decoder=lifetime_decoder
# The preserved diagnostic01 failed before SSH at the old 100-second complete
# host traversal. A fresh operation admits 300 seconds within its 600-second
# scope; all owner/lifetime files and existing byte/floor checks still apply.
import inspect
_main_source=inspect.getsource(driver.main)
_main_anchor='    s = source.decode()'
if _main_source.count(_main_anchor)!=1:
    raise ValueError('Exact generated-dispatch source boundary')
_main_source=_main_source.replace(_main_anchor,_main_anchor+'''
    preread_anchor='deadline=time.monotonic()+100'
    if s.count(preread_anchor)!=1:
        raise ValueError('Exact complete-host preread deadline boundary')
    s=s.replace(preread_anchor,'deadline=time.monotonic()+300')
''')
# This derivative admits ONLY the pinned read-only failure inspector while an
# idle field GUI exists. It never stops that GUI or sends a hardware command.
if '--writes' in sys.argv or '--action' not in sys.argv:
    raise ValueError('Read-only diagnostics only')
action_path=Path(sys.argv[sys.argv.index('--action')+1])
if action_path.name!='inspect_first_start_failure.py' or sha(read(action_path,65536))!='429ddc6284e0ecac49d1ddcd90688e9fea1b7b60c7b748aae11767f8fbc584fa':
    raise ValueError('Exact bounded read-only source action required')
_source_anchor="    if a.writes:\n        native = native.replace('(resource.RLIMIT_FSIZE,0)', '(resource.RLIMIT_FSIZE,33554432)')"
if _main_source.count(_source_anchor)!=1:raise ValueError('Exact native read-only adaptation boundary')
_main_source=_main_source.replace(_source_anchor,"""    readonly_units="assert units['returncode']==0 and {l.split()[0] for l in units['stdout'].splitlines() if l.strip()}<={unit,'jp-rollback-'+RID+'.service'}|{'jp-'+n+'.service' for n in current_operations}"
    if native.count(readonly_units)!=1:raise ValueError('Exact existing unit census required')
    native=native.replace(readonly_units,"assert units['returncode']==0 # read-only inspection preserves every active GUI")
"""+_source_anchor)
_old="assert not value['current_project_processes'], 'Preserve other running applications'"
if _main_source.count(_old)!=1:raise ValueError('Exact idle/write dispatch boundary')
_main_source=_main_source.replace(_old,"assert OPERATION_WRITES is False # preserve and report current field GUI identities")
exec(compile(_main_source,'<stabilization-bounded-host-main>','exec'),driver.__dict__)
if sys.argv[1:]==['--host-review']:
    pins,summary=actual_nested_unit_map()
    put('ACTUAL_NESTED_UNIT_MAP.json',pins);put('ACTUAL_NESTED_UNIT_REVIEW.json',summary)
    print(json.dumps(dict(output=str(early),**summary)))
else:
    driver.main()
