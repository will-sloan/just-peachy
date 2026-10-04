"""Explicit hash-checked one-shortcut restore; README_DESKTOP_ACTIVATION.md."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid


def read_small(path,maximum):
    info=path.stat()
    if path.is_symlink() or not path.is_file() or info.st_nlink!=1 or info.st_size>maximum:
        raise ValueError('Bounded single-link regular rollback input required')
    with path.open('rb') as stream:raw=stream.read(maximum+1)
    if len(raw)>maximum:raise ValueError('Rollback input grew beyond allowance')
    return raw


def checked_restore_bytes(plan,backup,restore,current,*,desktop,backup_root,manifest_sha256):
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    if (max(map(len,(backup,restore,current)))>65536 or backup!=restore or
        sha(backup)!=plan.get('previous_sha256') or sha(current)!=plan.get('next_sha256') or
        plan.get('desktop')!=str(desktop) or plan.get('backup')!=str(backup_root) or
        plan.get('manifest_sha256')!=manifest_sha256 or plan.get('autostart') is not False):
        raise ValueError('Exact activated launcher and independently retained restore bytes required')
    return restore


def rollback(payload,baseline):
    # Called only by existing host_operations native inspector after its actual
    # early owner and fresh full process/lease/free-space admission.
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot!=payload['boot_id'] or not time.time()<payload['expires_unix']<=time.time()+600:
        raise ValueError('Fresh current-boot rollback admission required')
    if any(baseline.get(key) for key in ('current_project_processes','active_recorded_owners','live_manager_owners')):
        raise ValueError('All owned runtime processes must close before shortcut rollback')
    package=Path(payload['package']);desktop=Path(payload['desktop']);backup=Path(payload['backup'])
    manifest=read_small(package/'PACKAGE_MANIFEST.json',262144)
    if len(manifest)>262144 or hashlib.sha256(manifest).hexdigest()!=payload['package_manifest_sha256']:
        raise ValueError('Pinned current candidate manifest required')
    entries=json.loads(manifest)['files']
    pin=next(row for row in entries if row['path']=='install_candidate.py')
    code=read_small(package/'install_candidate.py',131072)
    if len(code)!=pin['bytes'] or hashlib.sha256(code).hexdigest()!=pin['sha256']:
        raise ValueError('Exact installer helper pin required')
    module=dict(__name__='verified_rollback_installer',__file__=str(package/'install_candidate.py'))
    exec(compile(code,str(package/'install_candidate.py'),'exec'),module)
    module['check_native']();module['verify_tree'](package,payload['package_manifest_sha256'])
    if (not module['allowed_target'](package) or desktop.parent!=Path.home()/'Desktop' or desktop.suffix!='.desktop' or
        backup.parent!=package.parent or not re.fullmatch(r'field-runtime-v29-desktop-backup-[0-9a-f]{32}',backup.name)):
        raise ValueError('Explicit owned candidate backup and one Desktop launcher required')
    for path in (package,desktop,backup):
        if path.is_symlink() or path.resolve(strict=True)!=path:
            raise ValueError('Canonical regular rollback paths required')
    result_path=backup/'ROLLBACK_RESULT.json'
    if result_path.exists() or result_path.is_symlink():
        raise FileExistsError('Prior rollback receipt must be preserved')
    if shutil.disk_usage(desktop.parent).free<5*1024**3+131072:
        raise OSError('Rollback must preserve the existing 5 GiB disk floor')
    plan_path=backup/'ACTIVATION_PLAN.json'
    if plan_path.is_symlink() or not plan_path.is_file() or plan_path.stat().st_nlink!=1:
        raise ValueError('Regular activation receipt required')
    raw_plan=read_small(plan_path,65536)
    if len(raw_plan)>65536:raise ValueError('Bounded activation receipt required')
    plan=module['strict'](raw_plan)
    copies=[backup/(desktop.name+suffix) for suffix in ('.backup','.restore')]
    if any(path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1 for path in copies):
        raise ValueError('Independent regular desktop backup files required')
    current=read_small(desktop,65536)
    if hashlib.sha256(current).hexdigest()!=payload['expected_current_sha256']:
        raise ValueError('Explicit current desktop hash changed')
    restore=checked_restore_bytes(plan,*(read_small(path,65536) for path in copies),current,
        desktop=desktop,backup_root=backup,manifest_sha256=payload['package_manifest_sha256'])
    temporary=desktop.with_name('.'+desktop.name+'.rollback-'+uuid.uuid4().hex)
    module['write'](temporary,restore,copies[1].stat().st_mode & 0o777)
    if read_small(desktop,65536)!=current:raise ValueError('Desktop changed before atomic restore')
    os.replace(temporary,desktop);module['fsync_dir'](desktop.parent)
    if read_small(desktop,65536)!=restore:raise OSError('Desktop rollback readback differs')
    result=dict(status='DESKTOP_ROLLED_BACK_NOT_STARTED',desktop=str(desktop),backup=str(backup),
                current_sha256=hashlib.sha256(restore).hexdigest(),autostart=False,
                source_packages_modified=False,user_recordings_modified=False)
    module['write'](result_path,module['encoded'](result))
    return result


if 'PAYLOAD' in globals():RESULT=rollback(PAYLOAD,BASELINE)
