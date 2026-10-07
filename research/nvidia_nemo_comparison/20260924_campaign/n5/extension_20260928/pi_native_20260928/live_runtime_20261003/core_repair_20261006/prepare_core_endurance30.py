"""CPU14 host-only c24 PCM join and hour payload. README_CORE_BUILD30_HELPERS.md."""
import ctypes
import os

kernel = ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetCurrentProcess.restype = ctypes.c_void_p
kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p,ctypes.c_size_t]
kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
handle = kernel.GetCurrentProcess()
if not kernel.SetProcessAffinityMask(handle,16384):
    raise ctypes.WinError(ctypes.get_last_error())
stamps = [ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in stamps)):
    raise ctypes.WinError(ctypes.get_last_error())

import argparse
import ast
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import time
import types
import wave

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--package',type=Path,required=True)
parser.add_argument('--manifest-sha256',required=True)
parser.add_argument('--backup-root',type=Path,required=True)
parser.add_argument('--census-sha256',required=True)
parser.add_argument('--complete-sha256',required=True)
parser.add_argument('--boot-id',required=True)
parser.add_argument('--native-input-path',required=True)
parser.add_argument('--operator-id',required=True)
parser.add_argument('--label',required=True)
parser.add_argument('--reviewer',required=True)
parser.add_argument('--output',type=Path,required=True)
args = parser.parse_args()
args.output.mkdir()
owner = dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
    affinity_mask=16384,creation_filetime=stamps[0].value,
    create_time=(stamps[0].value-116444736000000000)/1e7)
with (args.output/'REGISTERED_OWNER.json').open('xb') as stream:
    raw = json.dumps(owner,sort_keys=True).encode()
    stream.write(raw);stream.flush();os.fsync(stream.fileno())
sys.dont_write_bytecode = True

from core_database_recovery import digest,identity,read_pinned_json,real_file,write_receipt
from prepare_core_native_validation import inventory,selected,read,OPERATOR_IDS

SID = 'c24b685b2bd34d6bb04172965d712c0f'
PREFIX = 'runtime-data/recordings/sessions/'+SID+'/'


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def hour_plan(files):
    module = types.ModuleType('_verified_core_hour_profiles')
    sys.modules[module.__name__] = module
    try:
        exec(compile(files['profiles.py'],'<verified-hour-profiles>','exec'),module.__dict__)
        policy = module.SessionPolicy(3600,True,max_drain_seconds=600,max_backlog_seconds=120)
        value = policy.validate();runtime = policy.total_deadline_seconds+300
    finally:
        sys.modules.pop(module.__name__,None)
    tree = ast.parse(files['storage.py'])
    names = {'StoragePolicy','metadata_limits','_validate_spec'}
    nodes = [node for node in tree.body if isinstance(node,(ast.ClassDef,ast.FunctionDef)) and node.name in names]
    if len(nodes)!=3:
        raise ValueError('Exact pinned storage allocation definitions required')
    space = dict(__name__=__name__,dataclass=dataclass,json=json,math=math)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<verified-hour-storage-arithmetic>','exec'),space)
    binding = json.loads(files['BINDING.json'])
    disk = space['StoragePolicy'](**binding.get('storage_policy',{}))
    metadata = 16*1024**2+3600*256*1024
    spec = dict(duration_seconds=3600,sample_rate=16000,mode='processed',metadata_reserve_bytes=metadata)
    audio_metadata = disk.estimate_bytes(spec)
    extra = metadata+disk.metadata_allowance_bytes+32*1024**2
    total = audio_metadata+extra
    if runtime!=4680 or total>3*1024**3:
        raise ValueError('Existing exact one-hour lifetime/complete-output plan required')
    return dict(policy=value,runtime_seconds=runtime,maximum_output_bytes=total,
        audio_and_metadata_bytes=audio_metadata,additional_allocation_bytes=extra,
        maximum_files=2048,physical_ram_guard_unchanged=True,model_limits_unchanged=True)


def verify_pure_package_imports(action,package,manifest):
    """Exercise the exact adapter binding and real pure storage dependency graph."""
    tree = ast.parse(action)
    names = {'bind_verified_package','hash_file'}
    nodes = [node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
    if len(nodes)!=2:
        raise ValueError('Exact adapter import binding definitions required')
    namespace = dict(Path=Path,sys=sys,hashlib=hashlib)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<exact-core-hour-import-binding>','exec'),namespace)
    check = namespace['bind_verified_package'](package,manifest)
    for name in ('profiles','storage'):
        spec = importlib.util.spec_from_file_location('verified_endurance_'+name,package/(name+'.py'))
        module = importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
        spec.loader.exec_module(module);check()
    return dict(actual_pure_imports=True,verified_dependency='storage_support',
        canonical_inventory_origins=True,model_imports=False,database_opened=False)


def main():
    began = time.monotonic()
    pins = []
    for index,name in enumerate(('prepare_core_endurance30.py','launch_core_full_app_hour30.py',
                                 'README_CORE_BUILD30_HELPERS.md','stage_c24_endurance_input30.py',
                                 'review_core_full_app_hour30.py','README_CORE_BUILD30_HELPERS.md','core_database_recovery.py',
                                 'prepare_core_native_validation_v3.py','activate_core_desktop_action30.py',
                                 'prepare_core_activation30.py')):
        path = Path(__file__).with_name(name);body = read(path,262144)
        for suffix in ('backup','restore'):
            with (args.output/('SOURCE_%02d.%s'%(index,suffix))).open('xb') as stream:
                stream.write(body);stream.flush();os.fsync(stream.fileno())
        if ((args.output/('SOURCE_%02d.backup'%index)).read_bytes()!=body or
            (args.output/('SOURCE_%02d.restore'%index)).read_bytes()!=body or path.read_bytes()!=body):
            raise OSError('Endurance source backup/independent restore differs')
        pins.append(dict(path=str(path),bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
    manifest,files = inventory(args.package,args.manifest_sha256)
    if (manifest['target']!='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-30' or
        args.manifest_sha256!='b2eeab82452d5b87515477c4a562ce167cf6d35503a16df6a4febc1b1af25569' or
        args.operator_id not in OPERATOR_IDS or not re.fullmatch(r'full-app-hour-\d{2}',args.label) or
        not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',args.boot_id) or
        not 1<=len(args.reviewer)<=128):
        raise ValueError('Exact frozen build30, ordinary row, actual boot and explicit reviewed hour label required')
    selection,chooser_label = selected(files,args.operator_id,'saved')
    plan = hour_plan(files)
    for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
        if shutil.disk_usage(drive).free<floor+2*plan['maximum_output_bytes']+8*1024**2:
            raise OSError('Independent complete hour PC reservation cannot retain host floor')
    census = read_pinned_json(args.backup_root/'CENSUS.json',args.census_sha256)
    complete = read_pinned_json(args.backup_root/'COMPLETE.json',args.complete_sha256)
    closure = complete.get('closure',{})
    if (complete.get('kind')!='COMPLETE' or complete.get('census_sha256')!=args.census_sha256 or
        any(complete.get(key) is not True for key in ('independent_readback','source_before_after_verified')) or
        any(closure.get(key) is not True for key in ('closed','exact_owner_gone','cgroup_empty')) or
        complete.get('files')!=len(census['files']) or
        complete.get('bytes')!=sum(row['identity']['bytes'] for row in census['files'])):
        raise ValueError('Actual accepted full backup and exact closed native owner required')
    names = ['session.json']+['processed-%08d.wav'%i for i in range(7)]
    source_rows = []
    copied_pins = []
    for name in names:
        rows = [row for row in census['files'] if row['path']==PREFIX+name]
        if len(rows)!=1:
            raise ValueError('Exact original c24 source member missing from captured census')
        row = rows[0];path = args.backup_root/'payload'/row['path']
        before = identity(path)
        if before['bytes']!=row['identity']['bytes'] or digest(path)!=row['sha256'] or identity(path)!=before:
            raise ValueError('Captured c24 member extent/hash changed')
        source_rows.append(row);copied_pins.append(dict(path=str(path),identity=before,sha256=row['sha256']))
    metadata = json.loads(Path(copied_pins[0]['path']).read_bytes())
    if (metadata.get('session_id')!=SID or metadata.get('status')!='kept' or
        metadata.get('processed_samples')!=966400 or metadata.get('spec',{}).get('sample_rate')!=16000):
        raise ValueError('Exact complete kept c24 source metadata required')
    target = args.output/'c24-processed.wav'
    frames = 0;pcm = hashlib.sha256()
    with target.open('xb') as output:
        with wave.open(output,'wb') as joined:
            joined.setparams((1,2,16000,966400,'NONE','not compressed'))
            for pin in copied_pins[1:]:
                path = Path(pin['path'])
                with wave.open(str(path),'rb') as source:
                    if (source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getcomptype())!=(1,2,16000,'NONE'):
                        raise ValueError('Original exact mono PCM16 16kHz replay WAV required')
                    frames += source.getnframes()
                    while block:=source.readframes(8192):
                        pcm.update(block);joined.writeframesraw(block)
        output.flush();os.fsync(output.fileno())
    if frames!=966400:
        raise ValueError('Concatenation did not retain the full ordered c24 sample timeline')
    restore = args.output/'c24-processed.restore.wav'
    with target.open('rb') as source,restore.open('xb') as output:
        while block:=source.read(16384):
            output.write(block)
        output.flush();os.fsync(output.fileno())
    readback = hashlib.sha256()
    with wave.open(str(restore),'rb') as source:
        if source.getnframes()!=frames:
            raise ValueError('Independent restored WAV sample count differs')
        while block:=source.readframes(8192):
            readback.update(block)
    wav_sha = digest(target)
    if digest(restore)!=wav_sha or readback.hexdigest()!=pcm.hexdigest():
        raise ValueError('Independent joined WAV/PCM restore differs')
    native = PurePosixPath(args.native_input_path)
    parent = PurePosixPath('/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003')
    if (not native.is_absolute() or parent not in native.parents or '..' in native.parts or
        '\\' in args.native_input_path or native.name!='c24-processed.wav' or native.as_posix()!=args.native_input_path):
        raise ValueError('Explicit future staged source under native test parent required')
    action = read(Path(__file__).with_name('launch_core_full_app_hour30.py'),65536)
    compile(action,'<prepared-core-hour-dispatch>','exec')
    stage_action = read(Path(__file__).with_name('stage_c24_endurance_input30.py'),65536)
    compile(stage_action,'<prepared-c24-native-stage>','exec')
    compile(read(Path(__file__).with_name('review_core_full_app_hour30.py'),65536),'<prepared-core-hour-review>','exec')
    for name in ('prepare_core_native_validation_v3.py','activate_core_desktop_action30.py','prepare_core_activation30.py'):
        compile(read(Path(__file__).with_name(name),65536),'<prepared-build30:'+name+'>','exec')
    import_proof = verify_pure_package_imports(action,args.package,manifest)
    compile(files['developer_replay.py'],'<pinned-continuous-replay>','exec')
    payload = dict(schema='just-peachy.full-app-hour-admission.v1',reviewed=True,reviewer=args.reviewer,
        boot_id=args.boot_id,expires_unix=time.time()+590,package=manifest['target'],
        package_manifest_sha256=args.manifest_sha256,label=args.label,
        workflow='continuous-full-application-repeated-wav',input=args.native_input_path,input_sha256=wav_sha,
        input_pcm_sha256=pcm.hexdigest(),original_source_pins=source_rows,repeat_input_seconds=3600,
        runtime_seconds=plan['runtime_seconds'],maximum_output_bytes=plan['maximum_output_bytes'],
        independent_pc_copy_bytes=plan['maximum_output_bytes'],selection=selection,policy=plan['policy'])
    write_receipt(args.output/'PAYLOAD.json',payload)
    stage_payload = dict(schema='just-peachy.core-c24-endurance-input.v1',operation='stage_input',
        reviewed=True,reviewer=args.reviewer,boot_id=args.boot_id,expires_unix=time.time()+590,
        package=manifest['target'],package_manifest_sha256=args.manifest_sha256,
        destination=args.native_input_path,original_source_pins=source_rows,
        source_census_sha256=args.census_sha256,source_complete_sha256=args.complete_sha256,
        output_bytes=target.stat().st_size,output_sha256=wav_sha,pcm_sha256=pcm.hexdigest(),
        maximum_output_bytes=8*1024**2,output_copy_reservation_bytes=8*1024**2)
    write_receipt(args.output/'STAGE_PAYLOAD.json',stage_payload)
    write_receipt(args.output/'SOURCE_JOIN.json',dict(source_session_id=SID,source_rows=source_rows,
        captured_full_backup_census_sha256=args.census_sha256,captured_full_backup_complete_sha256=args.complete_sha256,
        frames=frames,seconds=frames/16000,output=str(target),output_bytes=target.stat().st_size,
        output_sha256=wav_sha,pcm_sha256=pcm.hexdigest(),independent_restore=str(restore),
        independent_wav_readback=True,independent_pcm_readback=True,reencoded=False,
        source_representation='Existing original PCM16 processed replay bytes; regenerated RIFF header only'))
    for pin in copied_pins:
        if identity(pin['path'])!=pin['identity'] or digest(pin['path'])!=pin['sha256']:
            raise ValueError('Original copied c24 source changed during preparation')
    for pin in pins:
        if digest(pin['path'])!=pin['sha256']:
            raise ValueError('Endurance preparation source changed')
    write_receipt(args.output/'SOURCE_CLOSED.json',dict(status='PREPARED',owner=owner,
        native_dispatched=False,native_data_written=False,source_pins=pins,source_unchanged=True,
        original_copied_speech_unchanged=True,action_sha256=hashlib.sha256(action).hexdigest(),
        payload_sha256=digest(args.output/'PAYLOAD.json'),operator_id=args.operator_id,chooser_label=chooser_label,
        stage_action_sha256=hashlib.sha256(stage_action).hexdigest(),
        stage_payload_sha256=digest(args.output/'STAGE_PAYLOAD.json'),pure_import_proof=import_proof,
        hour_plan=plan,elapsed_seconds=time.monotonic()-began,gui_endurance=False,
        natural_conversation=False,quality_evaluated=False))
    print(encoded(dict(status='PREPARED',output=str(args.output),input=str(target),input_sha256=wav_sha,
        action_sha256=hashlib.sha256(action).hexdigest(),native_dispatched=False)).decode())


status = 'FAILED'
try:
    main();status='PREPARED'
finally:
    write_receipt(args.output/'HOST_EXIT.json',dict(owner=owner,status=status,native_dispatched=False,
        physical_closure_claimed=False))
