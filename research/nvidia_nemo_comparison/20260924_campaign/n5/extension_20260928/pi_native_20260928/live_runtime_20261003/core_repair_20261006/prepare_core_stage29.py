"""Host-only build29 stage payload; see README_CORE_STAGE.md.

Derivative of the exact stage28 preparation. Installer/native action unchanged.
No SSH, model import, SQLite open, capture, installed write or desktop activation.
"""
import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid

HERE = Path(__file__).resolve().parent
PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
STABILIZATION = HERE.parent/'stabilization_20261005'
OLD = PRIVATE/'audit-preparation/stabilization-stage24-preparation-1791236770589'
BACKUP = PRIVATE/'production-backup-11-reconcile-01'
TARGET = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-29'
DATA = '/home/peachyprototype/JustPeachy/data/runtime-v29'
BASE_SHA = 'e3d55e232730cb3b06cc12289d94cf04539ee04b8021ebd45553e5fd5027917b'
MANIFEST_SHA = '331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b'
ARCHIVE_SHA = '3a4ca0f9337d2618d1fde502f84d119c9cb25c90e3f2bb03ac4c1443c7ccf928'
SOURCE_REVIEW_SHA = '2f2b7b92fe54c87c5f1713c3cffc2f97420b1fc5d3f7f86566c043348d01549c'
PARENT_PREPARER_SHA = '5025c86eab988737f31fc1616b10cb003f136dec943b057778fecdb1447fa359'
INSTALLER_SHA = 'b4cbc107259556f901da1e47462b9ba238b766e56b7910c3c5982ea3fee68ad6'
ACTION_SHA = '4f5876f32a634db420baf78583a7a0ebac7d27b17bab52aace867d78df0d1c74'
MAX_PREPARATION = 8*1024**2


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path,limit=262144):
    path = Path(path)
    before = path.stat()
    if (path.is_symlink() or any(parent.is_symlink() for parent in path.parents)
            or not path.is_file() or before.st_nlink != 1 or before.st_size > limit):
        raise ValueError('Bounded ordinary single-link input required: '+str(path))
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns) != (after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('Input changed during read: '+str(path))
    return raw


def bootstrap():
    if os.name != 'nt':
        raise RuntimeError('Windows host preparation only')
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
    parent = PRIVATE/'audit-preparation'
    if parent.resolve(strict=True) != parent:
        raise ValueError('Exact existing private preparation parent required')
    root = parent/('core-stage29-preparation-'+uuid.uuid4().hex)
    root.mkdir(exist_ok=False)
    owner = dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000)
    raw = encoded(owner)
    with (root/'REGISTERED_OWNER.json').open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short early owner write')
        stream.flush()
        os.fsync(stream.fileno())
    if (root/'REGISTERED_OWNER.json').read_bytes() != raw:
        raise OSError('Early owner readback differs')
    return root,owner


def backup_admission(strict,boot,complete_pin,result_pin,reviewer):
    """Bind root-accepted COMPLETE, final source rehash and exact natural closure.

    Completion is a metadata prerequisite; this tool does not rehash the large
    restoration payload. That independent verification belongs to reconciliation.
    """
    if (any(re.fullmatch('[0-9a-f]{64}',pin) is None for pin in (complete_pin,result_pin))
            or not 1 <= len(reviewer.strip()) <= 128):
        raise ValueError('Exact accepted backup SHA pins and bounded reviewer required')
    names = ('COMPLETE.json','RESULT.json','FULL_BACKUP.json','JOB.json','CENSUS.json','MANIFEST.json')
    raw = {name:read(BACKUP/name,2*1024**2) for name in names}
    if sha(raw['COMPLETE.json']) != complete_pin or sha(raw['RESULT.json']) != result_pin:
        raise ValueError('Production-backup11 differs from accepted complete/result pins')
    complete,result,full,job,census = (strict(raw[name]) for name in names[:5])
    closure = complete.get('closure',{})
    if (complete.get('kind') != 'COMPLETE'
            or complete.get('backup_scope') != 'selected-release-and-user-data'
            or complete.get('mirror_scope') != 'all_regular_output_files'
            or complete.get('source_deleted') is not False
            or any(complete.get(key) is not True for key in
                ('source_before_after_verified','external_asset_pins_verified'))
            or any(closure.get(key) is not True for key in ('closed','exact_owner_gone','cgroup_empty'))
            or closure.get('owner') != job.get('owner')
            or closure.get('invocation_id') != job.get('invocation_id')
            or closure.get('job_exit',{}).get('natural_returncode') != 0
            or closure.get('job_exit',{}).get('error')
            or job.get('unit') != 'jp-v29-production-backup-11.service'
            or job.get('boot_id') != boot
            or job.get('package_manifest_sha256') != BASE_SHA
            or complete.get('census_sha256') != sha(raw['CENSUS.json'])
            or complete.get('restoration_directories') != census.get('directories')
            or strict(raw['MANIFEST.json']) != census.get('files')):
        raise ValueError('Actual completed backup11 source rehash/closure/census required')
    expected = dict(scope='selected-release-and-user-data',root=str(BACKUP/'payload'),
        manifest_path=str(BACKUP/'MANIFEST.json'),manifest_sha256=sha(raw['MANIFEST.json']),
        completion_path=str(BACKUP/'COMPLETE.json'),completion_sha256=complete_pin)
    if (full != expected or result.get('status') != 'VERIFIED_CURRENT_RELEASE_BACKUP'
            or result.get('full_backup') != expected or result.get('source_preserved') is not True
            or result.get('desktop_changed') is not False):
        raise ValueError('Canonical independently verified selected-release/user-data backup required')
    admission = dict(schema='just-peachy.core-stage-backup-admission.v1',reviewer=reviewer,
        backup_root=str(BACKUP),completion_sha256=complete_pin,result_sha256=result_pin,
        input_pins={name:dict(bytes=len(value),sha256=sha(value)) for name,value in raw.items()},
        owner=job['owner'],invocation_id=job['invocation_id'],boot_id=boot,
        scope=full['scope'],root=full['root'],source_before_after_verified=True,
        external_asset_pins_verified=True,exact_owner_gone=True,cgroup_empty=True,
        natural_returncode=0,restoration_payload_rehash_not_repeated=True,native_action=False)
    return admission,raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-output',type=Path,required=True)
    parser.add_argument('--boot-id',required=True)
    parser.add_argument('--backup-complete-sha256',required=True)
    parser.add_argument('--backup-result-sha256',required=True)
    parser.add_argument('--backup-reviewer',required=True)
    args = parser.parse_args()
    root,owner = bootstrap()  # Exact CPU14 owner before any project/package read.
    began = time.monotonic()
    written = (root/'REGISTERED_OWNER.json').stat().st_size
    def write(name,raw):
        nonlocal written
        if written+len(raw) > MAX_PREPARATION or time.monotonic()-began > 600:
            raise RuntimeError('Original finite8MiB/600s preparation scope')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free < floor+len(raw):
                raise OSError('Original host free-space floor')
        with (root/name).open('xb') as stream:
            if stream.write(raw) != len(raw):
                raise OSError('Short preparation write')
            stream.flush()
            os.fsync(stream.fileno())
        written += len(raw)
        if (root/name).read_bytes() != raw:
            raise OSError('Independent preparation readback differs')
    def triple(name,raw):
        for suffix in ('','.backup','.restore'):
            write(name+suffix,raw)
    write('HOST_SCOPE.json',encoded(dict(maximum_bytes=MAX_PREPARATION,maximum_seconds=600,
        native_action=False,label='core-stage29-01')))
    triple('PREPARER.py',read(Path(__file__),65536))
    triple('README.md',read(HERE/'README_CORE_STAGE.md',65536))
    try:
        if str(uuid.UUID(args.boot_id)) != args.boot_id:
            raise ValueError('Exact lowercase current boot UUID required')
        parent_raw = read(STABILIZATION/'prepare_stabilization_stage28.py',65536)
        installer_raw = read(OLD/'INSTALLER.py',131072)
        action_raw = read(STABILIZATION/'stage_stabilization_action.py',65536)
        if sha(parent_raw) != PARENT_PREPARER_SHA or sha(installer_raw) != INSTALLER_SHA or sha(action_raw) != ACTION_SHA:
            raise ValueError('Exact unchanged parent preparation/installer/action required')
        triple('PARENT_PREPARER.py',parent_raw)
        triple('INSTALLER.py',installer_raw)
        triple('ACTION.py',action_raw)
        namespace = dict(__name__='verified_host_core_stage29_inspection')
        exec(compile(installer_raw,'<exact-stage24-installer>','exec'),namespace)
        strict = namespace['strict']
        prior_raw = read(OLD/'PAYLOAD.json',8*1024**2)
        if any(read(OLD/('PAYLOAD.json'+suffix),8*1024**2) != prior_raw for suffix in ('.backup','.restore')):
            raise ValueError('Closed stage24 payload independent restore differs')
        prior = strict(prior_raw)
        if base64.b64decode(prior['installer_source_base64'],validate=True) != installer_raw:
            raise ValueError('Exact existing installer binding required')
        backup,backup_raw = backup_admission(strict,args.boot_id,args.backup_complete_sha256,
            args.backup_result_sha256,args.backup_reviewer)
        triple('BACKUP_ADMISSION.json',encoded(backup))
        # Keep the full accepted COMPLETE at its restoration location. Triple its
        # small hash-bound admission; copying it three times would consume scope.
        for name in ('RESULT.json','FULL_BACKUP.json','JOB.json'):
            triple('BACKUP_'+name,backup_raw[name])
        build = args.build_output
        if (build.parent != PRIVATE/'audit-preparation'
                or re.fullmatch('core-package-v1-[0-9a-f]{32}',build.name) is None
                or build.resolve(strict=True) != build):
            raise ValueError('Canonical fresh builder output required')
        build_raw = {name:read(build/name) for name in
            ('BUILD_RESULT.json','SOURCE_CLOSED.json','INDEPENDENT_CLOSURE.json','REGISTERED_OWNER.json','BUILD28_MEMBER_PRESERVATION.json')}
        result,closed,independent,builder_owner,preservation = (strict(value) for value in build_raw.values())
        package = build/'package'
        archive_path = build/'field-runtime-v29-build-29-prepared.tar.gz'
        if (result.get('package') != str(package) or result.get('archive') != str(archive_path)
                or result.get('target') != TARGET or result.get('data_root') != DATA
                or result.get('parent_manifest_sha256') != BASE_SHA
                or result.get('manifest_sha256') != MANIFEST_SHA or result.get('archive_sha256') != ARCHIVE_SHA
                or result.get('installed') is not False or result.get('desktop_changed') is not False
                or result.get('source_backups_and_restores_exact') is not True
                or closed.get('scope_closed') is not True or closed.get('native_action') is not False
                or independent.get('owner') != builder_owner or independent.get('pid_absent') is not True
                or independent.get('natural_returncode') != 0
                or independent.get('source_backups_restores_unchanged') is not True
                or independent.get('source_review_sha256') != SOURCE_REVIEW_SHA
                or independent.get('manifest_sha256') != MANIFEST_SHA
                or independent.get('archive_sha256') != ARCHIVE_SHA
                or preservation.get('removed_members') != []
                or preservation.get('all_other_runtime_assets_models_profiles_raw_proof_bytes_identical') is not True):
            raise ValueError('Exact root-reviewed completed/independently closed build29 required')
        for name,raw in build_raw.items():
            triple('BUILD_'+name,raw)
        if sha(read(build/'SOURCE_DIFF_REVIEW.json')) != SOURCE_REVIEW_SHA:
            raise ValueError('Root-reviewed source/AST/import inventory pin differs')
        archive = read(archive_path,2*1024**2)
        manifest,files = namespace['validate_payload'](archive,ARCHIVE_SHA,MANIFEST_SHA)
        if manifest['target'] != TARGET:
            raise ValueError('Exact fresh build29 target required')
        actual,directories = set(),set()
        if package.resolve(strict=True) != package:
            raise ValueError('Canonical expanded package required')
        for path in package.rglob('*'):
            if path.is_symlink():
                raise ValueError('Real package members required')
            name = path.relative_to(package).as_posix()
            if path.is_dir():
                directories.add(name)
            elif path.is_file():
                actual.add(name)
                if name not in files or read(path,16*1024**2) != files[name]:
                    raise ValueError('Full archive/expanded-package readback differs')
            else:
                raise ValueError('Unsupported package member')
        if actual != set(files):
            raise ValueError('Complete package/archive membership differs')
        expanded = sum(map(len,files.values()))
        reservation = expanded+len(archive)+(len(directories)+1)*65536+65536
        payload = dict(prior,archive_base64=base64.b64encode(archive).decode(),
            archive_sha256=ARCHIVE_SHA,manifest_sha256=MANIFEST_SHA,
            target_reservation_bytes=reservation,expected_boot_id=args.boot_id,
            production_backup_admission=backup,source_review_sha256=SOURCE_REVIEW_SHA)
        triple('PAYLOAD.json',encoded(payload))
        for suffix in ('','.backup','.restore'):
            restored = strict(read(root/('PAYLOAD.json'+suffix),MAX_PREPARATION))
            if (base64.b64decode(restored['archive_base64'],validate=True) != archive
                    or base64.b64decode(restored['installer_source_base64'],validate=True) != installer_raw):
                raise ValueError('Independent decoded payload restore differs')
        if read(archive_path,2*1024**2) != archive or read(package/'PACKAGE_MANIFEST.json') != files['PACKAGE_MANIFEST.json']:
            raise ValueError('Bound package source changed during preparation')
        if any(read(BACKUP/name,2*1024**2) != raw for name,raw in backup_raw.items()):
            raise ValueError('Accepted backup metadata changed during preparation')
        receipt = dict(output=str(root),action=str(root/'ACTION.py'),payload=str(root/'PAYLOAD.json'),
            owner=owner,label='core-stage29-01',target=TARGET,boot_id=args.boot_id,
            manifest_sha256=MANIFEST_SHA,archive_sha256=ARCHIVE_SHA,archive_bytes=len(archive),
            expanded_bytes=expanded,archive_members=len(files),directories=len(directories),
            target_reservation_bytes=reservation,
            allocation_formula='expanded+archive+(directories+1)*65536+65536',
            installer_source_sha256=INSTALLER_SHA,action_sha256=ACTION_SHA,
            source_backup_independent_restores=True,backup_admission=backup,
            source_files={name:dict(bytes=(root/name).stat().st_size,sha256=sha(read(root/name,MAX_PREPARATION)))
                for name in ('PREPARER.py','README.md','PARENT_PREPARER.py','INSTALLER.py','ACTION.py','PAYLOAD.json','BACKUP_ADMISSION.json')},
            prepared_bytes=written,native_action=False,models_started=False,desktop_changed=False)
        write('SOURCE_CLOSED.json',encoded(dict(closed_unix=time.time(),elapsed=time.monotonic()-began,**receipt)))
        print(encoded(receipt).decode())
    except BaseException as error:
        write('FAILURE.json',encoded(dict(type=type(error).__name__,message=str(error))))
        raise


if __name__ == '__main__':
    main()
