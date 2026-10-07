"""Narrow frozen-build30 one-hour dispatch adapter. README_CORE_BUILD30_HELPERS.md.

Injected PAYLOAD/BASELINE only. Reuse the installed continuous replay and shared
unit envelope; no runtime edits, new model loop, SSH or implicit admission.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import wave

PACKAGE = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-30')
PIN = 'b2eeab82452d5b87515477c4a562ce167cf6d35503a16df6a4febc1b1af25569'
SOURCE = Path('/home/peachyprototype/JustPeachy/data/runtime-v29/recordings/sessions/c24b685b2bd34d6bb04172965d712c0f')


def bind_verified_package(package, manifest):
    """Resolve project dependencies only in the fully inventoried package."""
    from importlib.machinery import PathFinder, SourceFileLoader
    package = Path(package)
    if package.resolve(strict=True) != package or package.is_symlink():
        raise ValueError('Canonical inventoried import root required')
    project = {Path(row['path']).stem: row for row in manifest['files']
        if '/' not in row['path'] and row['path'].endswith('.py')}
    def ordinary(name, origin):
        row = project.get(name)
        if row is None or not isinstance(origin, str):
            raise ValueError('Inventoried ordinary project origin required')
        path = Path(origin)
        expected = package / row['path']
        info = path.lstat()
        if (path != expected or path.resolve(strict=True) != expected or path.is_symlink()
                or not path.is_file() or info.st_nlink != 1
                or info.st_size != row['bytes'] or hash_file(path) != row['sha256']):
            raise ValueError('Project import origin differs from inventory: '+name)
    def verify_loaded():
        for name, module in tuple(sys.modules.items()):
            primary = name.split('.', 1)[0]
            origin = getattr(module, '__file__', None)
            from_package = isinstance(origin, str) and Path(origin).parent == package
            if primary not in project and not from_package:
                continue
            source_name = Path(origin).stem if from_package else primary
            ordinary(source_name, origin)
            spec = getattr(module, '__spec__', None)
            if spec is None or getattr(spec, 'origin', None) != origin:
                raise ValueError('Project module spec/file origins differ: '+name)
    verify_loaded()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(package))
    for name in project:
        spec = PathFinder.find_spec(name, [str(package)])
        if spec is None or not isinstance(spec.loader, SourceFileLoader):
            raise ValueError('Ordinary inventoried source loader required: '+name)
        ordinary(name, spec.origin)
    return verify_loaded


def hash_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def file_identity(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or
        any(p.is_symlink() for p in (path,*path.parents))):
        raise ValueError('Real single-link retained endurance input required')
    return dict(bytes=info.st_size,device=info.st_dev,inode=info.st_ino,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns)


def verify_source(payload):
    rows = payload['original_source_pins']
    if (type(rows) is not list or len(rows)!=8 or rows[0].get('source')!=str(SOURCE/'session.json') or
        [r.get('source') for r in rows[1:]]!=[str(SOURCE/('processed-%08d.wav'%i)) for i in range(7)]):
        raise ValueError('Exact c24 metadata and seven retained PCM16 segments required')
    pcm = hashlib.sha256();frames = 0
    for index,row in enumerate(rows):
        path = Path(row['source'])
        if file_identity(path)!=row['identity'] or hash_file(path)!=row['sha256']:
            raise ValueError('Original current c24 identity/hash differs from accepted host source')
        if index==0:
            meta = json.loads(path.read_bytes())
            if (meta.get('status')!='kept' or meta.get('session_id')!=SOURCE.name or
                meta.get('processed_samples')!=966400 or meta.get('spec',{}).get('sample_rate')!=16000):
                raise ValueError('Exact complete kept c24 source required')
        else:
            with wave.open(str(path),'rb') as source:
                if (source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getcomptype())!=(1,2,16000,'NONE'):
                    raise ValueError('Original mono PCM16 16kHz replay representation required')
                frames += source.getnframes()
                while block:=source.readframes(8192):
                    pcm.update(block)
        if file_identity(path)!=row['identity']:
            raise ValueError('Original retained source changed during native verification')
    path = Path(payload['input'])
    before = file_identity(path)
    if hash_file(path)!=payload['input_sha256']:
        raise ValueError('Staged joined input SHA differs')
    joined = hashlib.sha256()
    with wave.open(str(path),'rb') as source:
        if ((source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getcomptype())!=(1,2,16000,'NONE') or
            source.getnframes()!=frames or frames!=966400):
            raise ValueError('Joined input must retain all exact original source frames')
        while block:=source.readframes(8192):
            joined.update(block)
    if (joined.hexdigest()!=pcm.hexdigest() or pcm.hexdigest()!=payload['input_pcm_sha256'] or
        file_identity(path)!=before):
        raise ValueError('Native joined PCM payload is not the lossless ordered original replay')
    return dict(source_session_id=SOURCE.name,frames=frames,seconds=frames/16000,
        retained_pcm16_representation=True,reencoded=False,lossless_pcm_join=True,
        source_pcm_sha256=pcm.hexdigest(),input_sha256=payload['input_sha256'])


def dispatch(payload,baseline):
    if (payload.get('schema')!='just-peachy.full-app-hour-admission.v1' or
        payload.get('reviewed') is not True or not isinstance(payload.get('reviewer'),str) or
        not 1<=len(payload['reviewer'])<=128 or payload.get('package')!=str(PACKAGE) or
        payload.get('package_manifest_sha256')!=PIN):
        raise ValueError('Exact reviewed frozen build30 continuous application admission required')
    manifest_path = PACKAGE/'PACKAGE_MANIFEST.json'
    if hash_file(manifest_path)!=PIN:
        raise ValueError('Frozen build30 manifest differs')
    manifest = json.loads(manifest_path.read_bytes())
    rows = [r for r in manifest['files'] if r['path']=='launch_raw_qualification_action.py']
    if len(rows)!=1:
        raise ValueError('Exact shared qualified envelope required')
    helper_path = PACKAGE/rows[0]['path']
    if file_identity(helper_path)['bytes']!=rows[0]['bytes'] or hash_file(helper_path)!=rows[0]['sha256']:
        raise ValueError('Pinned shared envelope differs')
    namespace = dict(__name__='verified_core_hour_envelope',__file__=str(helper_path))
    exec(compile(helper_path.read_bytes(),str(helper_path),'exec'),namespace)
    manifest = namespace['inventory'](PACKAGE,PIN)
    verified_imports = bind_verified_package(PACKAGE,manifest)
    lock_path = SOURCE.parent.parent/'locks'/(SOURCE.name+'.lock')
    if lock_path.is_symlink():
        raise ValueError('Real retained source lease required')
    with lock_path.open('rb') as lease:
        fcntl.flock(lease,fcntl.LOCK_SH|fcntl.LOCK_NB)
        source_proof = verify_source(payload)
    original_plan = namespace['budget_plan']
    def capacity_plan(package,binding,request,kind):
        plan = original_plan(package,binding,request,kind)
        verified_imports()
        if kind!='full_app_hour':
            raise ValueError('This adapter admits only the retained integrated hour workflow')
        disk = namespace['shutil'].disk_usage(PACKAGE.parent)
        storage = namespace['load_pure'](package,'storage')
        verified_imports()
        reserve = storage.StoragePolicy(**binding.get('storage_policy',{})).reserve(disk.total)
        ceiling = disk.total-reserve
        if disk.free<reserve+plan['maximum_output_bytes'] or ceiling<plan['maximum_output_bytes']:
            raise OSError('Actual capacity cannot preserve complete hour output and physical reserve')
        plan.update(file_limit_bytes=ceiling,physical_file_reserve_bytes=reserve,
            physical_filesystem_total_bytes=disk.total,physical_free_at_admission_bytes=disk.free,
            file_limit_scope='Per-file capacity guard; complete job output reservation remains unchanged')
        return plan
    namespace['budget_plan'] = capacity_plan
    result = namespace['launch'](payload,baseline,kind='full_app_hour')
    verified_imports()
    return dict(result,original_source_verified=source_proof,
        endurance_scope='One continuous wall-paced headless application session using repeated retained speech',
        natural_conversation=False,gui_endurance=False,quality_evaluated=False)


if 'PAYLOAD' in globals():
    RESULT = dispatch(PAYLOAD,BASELINE)
