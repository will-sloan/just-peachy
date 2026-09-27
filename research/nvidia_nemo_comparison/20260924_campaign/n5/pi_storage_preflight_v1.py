"""Read-only offline baseline space inventory. README_PI_STORAGE_PREFLIGHT_V1.md."""
import argparse
import ctypes
import ctypes.util
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import sys
import time
import zipfile

GIB = 1024**3
MAX_BYTES = 8*GIB
MAX_FILES = 50000
SHA = re.compile(r'^[0-9a-f]{64}$')


def require(value, message):
    if not value: raise ValueError(message)


def pin_windows():
    """Only this process: existing campaign CPU14, BelowNormal; no host settings."""
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '1'
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    if os.name == 'nt':
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
        kernel.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        handle = kernel.GetCurrentProcess()
        require(kernel.SetProcessAffinityMask(handle, 1 << 14), 'Cannot apply CPU14')
        require(kernel.SetPriorityClass(handle, 0x4000), 'Cannot apply BelowNormal')


def safe_name(name):
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name
        and '\x00' not in name, 'Unsafe ZIP member name')
    p = PurePosixPath(name.rstrip('/'))
    require(not p.is_absolute() and p.parts and all(v not in ('', '.', '..') for v in name.rstrip('/').split('/'))
        and str(p) == name.rstrip('/'), 'Noncanonical ZIP member path')
    return str(p)


def inventory(z):
    infos = z.infolist(); require(0 < len(infos) <= MAX_FILES, 'ZIP member bound exceeded')
    seen = set(); files = {}; total = 0
    for info in infos:
        # Windows ZipInfo normalizes backslashes in filename. Validate the raw
        # central-directory spelling before accepting its normalized view.
        name = safe_name(info.orig_filename)
        require(info.filename.rstrip('/') == name, 'ZIP filename normalization differs')
        require(name.casefold() not in seen, 'Duplicate/case-colliding ZIP member')
        seen.add(name.casefold())
        require(not info.flag_bits & 1 and not stat.S_ISLNK(info.external_attr >> 16),
            'Encrypted or symlink ZIP member refused')
        require(0 <= info.file_size <= MAX_BYTES, 'ZIP member size bound exceeded')
        total += info.file_size; require(total <= MAX_BYTES, 'ZIP expansion bound exceeded')
        if not info.is_dir(): files[name] = info
    return files, total


def digest(stream, deadline):
    result = hashlib.sha256()
    while True:
        require(time.monotonic() < deadline, 'Preflight time bound reached')
        data = stream.read(1024*1024)
        if not data: return result.hexdigest()
        result.update(data)


def small_json(z, name):
    require(z.getinfo(name).file_size <= 1024**2, 'Oversized JSON metadata')
    return json.loads(z.read(name).decode('utf-8-sig'))


def inspect_bundle(path, expected_sha256, *, max_seconds=300):
    """Hash every outer member; inspect nested ZIP metadata without extracting."""
    path = Path(path).resolve(strict=True)
    require(SHA.fullmatch(expected_sha256) is not None, 'Expected SHA256 must be 64 lowercase hex digits')
    before = path.stat(); require(0 < before.st_size <= MAX_BYTES, 'Bundle size bound exceeded')
    deadline = time.monotonic()+max_seconds
    with path.open('rb') as stream: require(digest(stream, deadline) == expected_sha256, 'Archive SHA256 differs')
    with zipfile.ZipFile(path) as z:
        files, extracted = inventory(z)
        require('BUNDLE_MANIFEST.json' in files, 'Bundle manifest missing')
        m = small_json(z, 'BUNDLE_MANIFEST.json')
        require(m.get('schema') == 'n5-private-offline-baseline-v1' and m.get('baseline_only') is True,
            'Only the preserved baseline bundle schema is currently supported')
        rows = m['files']; require(isinstance(rows, list) and 0 < len(rows) <= 1000, 'Invalid manifest population')
        declared = {}
        for row in rows:
            name = safe_name(row['path'])
            require(name not in declared and type(row['bytes']) is int and row['bytes'] >= 0
                and SHA.fullmatch(row['sha256']) is not None, 'Invalid/duplicate manifest entry')
            declared[name] = row
        require(set(files) == set(declared) | {'BUNDLE_MANIFEST.json'}, 'Undeclared or missing bundle member')
        for name, row in declared.items():
            require(files[name].file_size == row['bytes'], 'Member size differs: '+name)
            with z.open(name) as stream: require(digest(stream, deadline) == row['sha256'], 'Member hash differs: '+name)
        app = safe_name(m['application_archive'])
        require(app.startswith('app/') and declared[app]['sha256'] == m['application_sha256'], 'Application archive join differs')
        with z.open(app) as stream, zipfile.ZipFile(stream) as app_zip:
            app_files, app_bytes = inventory(app_zip)
            require('config/assets.json' in app_files, 'Application asset inventory missing')
            assets = small_json(app_zip, 'config/assets.json')
        models = {}; paths = set()
        for asset in assets:
            filename = asset.get('filename') or PurePosixPath(asset['deployment_relative_path']).name
            require(safe_name(filename) == filename and '/' not in filename, 'Noncanonical asset filename')
            key = asset['sha256']; require(SHA.fullmatch(key) is not None, 'Invalid asset digest')
            name = 'models/'+key+'/'+filename; row = declared[name]
            require(type(asset['bytes']) is int and row['sha256'] == key and row['bytes'] == asset['bytes'],
                'Application/model manifest join differs')
            require(key not in models or models[key] == (filename, row['bytes']),
                'Same model digest has different physical filenames/sizes; no unproved deduplication credit')
            models[key] = (filename, row['bytes']); paths.add(name)
        require(paths == {n for n in declared if n.startswith('models/')}, 'Unreferenced model payload')
        wheel_bytes = 0; wheel_count = 0; wheel_files = 0
        for name in declared:
            if name.startswith('wheelhouse/'):
                require(name.endswith('.whl'), 'Unexpected wheelhouse file')
                with z.open(name) as stream, zipfile.ZipFile(stream) as wheel:
                    members, size = inventory(wheel)
                wheel_count += 1; wheel_files += len(members); wheel_bytes += size
        require(models and wheel_count and wheel_bytes <= MAX_BYTES, 'Empty or excessive runtime/model inventory')
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'Bundle changed during inspection')
    require(time.monotonic() < deadline, 'Preflight time bound reached')
    return dict(archive=dict(path=str(path), sha256=expected_sha256, bytes=before.st_size),
        package_status=m.get('status'), application_version=m['application_version'],
        N4_selected=m.get('N4_selected'), baseline_only=True, member_hashes_verified=len(declared),
        extracted_bundle_logical_bytes=extracted, application_unpacked_logical_bytes=app_bytes,
        unique_model_bytes=sum(size for _, size in models.values()), unique_model_count=len(models),
        wheel_unpacked_logical_bytes=wheel_bytes, wheel_count=wheel_count, wheel_member_count=wheel_files,
        archive_extracted=False, models_loaded=False, hardware_contacted=False)


def space_plan(bundle, *, overhead_bytes, reserve_bytes=GIB, rollback_extra_bytes=0, available_bytes=None):
    """Conservative *additional* space; do not credit existing files or deduplication."""
    for name, value in [('overhead', overhead_bytes), ('reserve', reserve_bytes), ('rollback', rollback_extra_bytes)]:
        require(type(value) is int and value >= 0, 'Invalid '+name+' bytes')
    require(overhead_bytes > 0 and reserve_bytes >= GIB, 'Positive runtime overhead and at least 1 GiB reserve required')
    require(available_bytes is None or type(available_bytes) is int and available_bytes >= 0, 'Invalid available bytes')
    installed_payload = bundle['application_unpacked_logical_bytes']+bundle['unique_model_bytes']+bundle['wheel_unpacked_logical_bytes']
    # The current installer checks twice source size and preserves a 256-MiB margin.
    staging_margin = bundle['application_unpacked_logical_bytes']+256*1024**2
    peak = (bundle['archive']['bytes']+bundle['extracted_bundle_logical_bytes']+
        installed_payload+staging_margin+overhead_bytes+rollback_extra_bytes)
    needed = peak+reserve_bytes
    return dict(download_bytes_needed_on_this_host=0, transfer_archive_bytes=bundle['archive']['bytes'],
        extracted_bundle_logical_bytes=bundle['extracted_bundle_logical_bytes'],
        known_installed_payload_logical_bytes=installed_payload,
        installed_size_is_measured=False, runtime_filesystem_overhead_budget_bytes=overhead_bytes,
        extra_staging_margin_bytes=staging_margin, rollback_extra_copy_budget_bytes=rollback_extra_bytes,
        existing_rollback_release_retained=True, existing_file_credit_bytes=0,
        conservative_additional_peak_bytes=peak, reserve_bytes=reserve_bytes,
        required_available_bytes_with_reserve=needed, available_bytes=available_bytes,
        space_status='TARGET_STORAGE_UNCHECKED' if available_bytes is None else
            ('ESTIMATED_FIT' if available_bytes >= needed else 'INSUFFICIENT_SPACE'),
        installation_authorized=False, target_runtime_or_RAM_qualified=False)


def target_observation(install_root, data_root):
    """Later on the reconnected Pi only. No writes, imports of audio modules or GUI."""
    install, data = Path(install_root), Path(data_root)
    require(install.is_absolute() and data.is_absolute(), 'Explicit absolute install and external data roots required')
    install, data = install.resolve(), data.resolve()
    require(not install.is_relative_to(data) and not data.is_relative_to(install), 'Data and install roots must be separate')
    directories = {}
    for label, root in [('install', install), ('data', data)]:
        parent = root
        while not parent.exists(): parent = parent.parent
        require(parent.is_dir(), 'Existing path parent is not a directory')
        directories[label] = dict(root=str(root), existing_parent=str(parent), device=parent.stat().st_dev,
            free_bytes=shutil.disk_usage(parent).free, access_check_writable=os.access(parent, os.W_OK | os.X_OK))
    libc, version = platform.libc_ver()
    version_parts = tuple(int(p) for p in version.split('.') if p.isdigit())
    libraries = {name:ctypes.util.find_library(name) for name in ('portaudio', 'sndfile', 'usb-1.0', 'gomp', 'stdc++', 'gcc_s', 'z')}
    checks = dict(linux=platform.system() == 'Linux', aarch64=platform.machine().lower() in ('aarch64', 'arm64'),
        python311=sys.version_info[:2] == (3,11), glibc236=libc == 'glibc' and version_parts >= (2,36),
        tkinter_metadata=importlib.util.find_spec('tkinter') is not None,
        venv_metadata=importlib.util.find_spec('venv') is not None,
        os_libraries_located=all(libraries.values()), ordinary_user=hasattr(os,'getuid') and os.getuid()!=0,
        roots_appear_writable=all(v['access_check_writable'] for v in directories.values()),
        roots_on_same_filesystem=directories['install']['device']==directories['data']['device'])
    return dict(platform=platform.system(), machine=platform.machine(), python=platform.python_version(),
        libc=[libc,version], directories=directories, library_lookup=libraries, prerequisites=checks,
        status='PREREQUISITE_METADATA_PASS_ONLY' if all(checks.values()) else 'PREREQUISITES_MISSING_OR_UNVERIFIED',
        writes_performed=False, dynamic_imports_or_model_loads_tested=False, hardware_devices_opened=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--runtime-overhead-bytes',type=int,required=True)
    parser.add_argument('--reserve-bytes',type=int,default=GIB);parser.add_argument('--rollback-extra-bytes',type=int,default=0)
    parser.add_argument('--available-bytes',type=int);parser.add_argument('--target-install-root',type=Path)
    parser.add_argument('--target-data-root',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();pin_windows()
    require(not args.output.exists(), 'Preserve existing output; use a fresh filename')
    require(bool(args.target_install_root)==bool(args.target_data_root), 'Supply both target roots or neither')
    require(not args.target_install_root or platform.system()=='Linux' and platform.machine().lower() in ('aarch64','arm64'),
        'Actual target observation requires Linux ARM64; do not label this desktop as the Pi')
    require(not args.target_install_root or args.available_bytes is None, 'Actual free space cannot be replaced by a supplied estimate')
    bundle=inspect_bundle(args.bundle,args.sha256)
    target=target_observation(args.target_install_root,args.target_data_root) if args.target_install_root else None
    available=target['directories']['install']['free_bytes'] if target else args.available_bytes
    report=dict(status='READ_ONLY_PREFLIGHT_NOT_INSTALLATION',bundle=bundle,
        space=space_plan(bundle,overhead_bytes=args.runtime_overhead_bytes,reserve_bytes=args.reserve_bytes,
            rollback_extra_bytes=args.rollback_extra_bytes,available_bytes=available),
        target_observation=target,available_space_source='ACTUAL_TARGET_FILESYSTEM' if target else
            ('USER_SUPPLIED_SCENARIO' if available is not None else 'UNMEASURED_TARGET'),
        CM5_software_functionally_validated=False, N5_complete=False)
    # Only the explicitly requested report is written; no destination roots are created.
    if os.name=='nt':
        require(shutil.disk_usage('C:/').free>=50*GIB and shutil.disk_usage('G:/').free>=75*GIB,
            'Campaign drive floor reached')
    with args.output.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(output=str(args.output.resolve()),space_status=report['space']['space_status'],
        required_available_bytes_with_reserve=report['space']['required_available_bytes_with_reserve'],
        target_observed=target is not None,installation_performed=False)))


if __name__=='__main__':main()
