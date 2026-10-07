"""Build the reviewed35 handoff; see README_CORE_PUBLICATION_V10.md.

Derivative of immutable build_handoff_v2.py. Only the exact named/hash-bound
PowerShell package verifier and exact diagnostic preparer are admitted. ZIP format,
source/working-set bounds and full independent archive restore are unchanged.
"""
import ctypes
from ctypes import wintypes

# Pin the actual host process before reading project data or importing psutil.
_KERNEL = ctypes.WinDLL('kernel32', use_last_error=True)
_KERNEL.GetCurrentProcess.restype = wintypes.HANDLE
_HANDLE = _KERNEL.GetCurrentProcess()
_KERNEL.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
_KERNEL.SetProcessAffinityMask.restype = wintypes.BOOL
if not _KERNEL.SetProcessAffinityMask(_HANDLE, 1 << 14):
    raise ctypes.WinError(ctypes.get_last_error())
_KERNEL.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
_KERNEL.GetProcessTimes.restype = wintypes.BOOL


def registered_identity():
    created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
    if not _KERNEL.GetProcessTimes(_HANDLE, ctypes.byref(created), ctypes.byref(exited),
                                   ctypes.byref(kernel), ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())
    filetime = (created.dwHighDateTime << 32) | created.dwLowDateTime
    return dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(),
                cpu=14, affinity_mask=16384, creation_filetime=filetime,
                create_time=(filetime - 116444736000000000) / 10000000)
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile

MIB = 1024**2
ROOT = Path('G:/Just_Peachy_N1/20260924_campaign/worktree')
ALLOWED = {'.md', '.json', '.py', '.txt', '.toml', '.h', '.cpp', '.c', '.sh'}
HERE = Path(__file__).absolute().parent
PARENT = HERE.parent.parent/'runtime_handoff_tools/build_handoff_v2.py'
PARENT_SHA = '34bd6696f360dd0c50a0e1817fc328b1d5a7983aa968d391c264fb8263349c6f'
SHELL_MEMBER = (HERE/'verify_prepared_runtime_package.ps1').relative_to(ROOT).as_posix()
SHELL_SHA = '3519a7147e8bd8e817769bf5fa115867ce6973764ff4a143d224b5c504f896a2'
DIAGNOSTIC_MEMBER = (HERE/'prepare_normal02_closed.ps1').relative_to(ROOT).as_posix()
DIAGNOSTIC_SHA = 'db131b3bb32724e722c02326c46ac0a14f455fb90560725b52d08b4b7e1c6697'
LEGACY_ADAPTER = HERE/'build_core_handoff_v7.py'
LEGACY_ADAPTER_SHA = 'b2b5bc5cf284b778a2bb67fc8c9695babc765a1c775b41154eae5e49443855c7'



def is_named_shell(name, source, pin):
    return ((name == SHELL_MEMBER and source == ROOT/SHELL_MEMBER and pin == SHELL_SHA)
            or (name == DIAGNOSTIC_MEMBER and source == ROOT/DIAGNOSTIC_MEMBER
                and pin == DIAGNOSTIC_SHA))


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_member(name):
    path = PurePosixPath(name)
    if (not isinstance(name, str) or not name or path.is_absolute()
            or path.as_posix() != name or '\\' in name or ':' in name
            or '..' in path.parts or len(name.encode()) > 512):
        raise ValueError('Unsafe handoff member')
    return name


def bind_exact_sources(output, put):
    """Back and independently restore source before reading the reviewed plan."""
    def read(path):
        before = path.lstat()
        if (path.is_symlink() or any(parent.is_symlink() for parent in path.parents)
                or path.resolve(strict=True) != path or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1 or before.st_size > 2*MIB):
            raise ValueError('Canonical bounded single-link handoff input required')
        with path.open('rb') as stream:
            raw = stream.read(2*MIB+1)
        after = path.lstat()
        if (len(raw) != before.st_size or (before.st_dev, before.st_ino, before.st_size,
                before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise ValueError('Handoff source changed during bounded read')
        return raw
    sources = (Path(__file__).absolute(), HERE/'README_CORE_PUBLICATION_V10.md', PARENT,
               HERE/'verify_prepared_runtime_package.ps1',
               HERE/'prepare_normal02_closed.ps1', LEGACY_ADAPTER)
    pins = {}
    for path in sources:
        raw = read(path)
        if (path == PARENT and digest(raw) != PARENT_SHA
                or path.name == 'verify_prepared_runtime_package.ps1' and digest(raw) != SHELL_SHA
                or path.name == 'prepare_normal02_closed.ps1' and digest(raw) != DIAGNOSTIC_SHA
                or path == LEGACY_ADAPTER and digest(raw) != LEGACY_ADAPTER_SHA):
            raise ValueError('Exact immutable parent and named verifier required')
        for suffix in ('.source', '.backup', '.restore'):
            destination = output/'builder-sources'/(path.name+suffix)
            put(destination, raw)
            if read(destination) != raw:raise OSError('Independent builder source restore differs')
        if read(path) != raw:raise ValueError('Handoff input changed during source closure')
        pins[str(path)] = dict(bytes=len(raw), sha256=digest(raw))
    put(output/'BUILDER_SOURCE_BINDING.json', encoded(dict(
        schema='just-peachy.core-handoff-v10-source-binding.v1', parent_sha256=PARENT_SHA,
        admitted_shell_member=SHELL_MEMBER, admitted_shell_sha256=SHELL_SHA,
        diagnostic_shell_member=DIAGNOSTIC_MEMBER, diagnostic_shell_sha256=DIAGNOSTIC_SHA,
        sources=pins, source_backups_and_independent_restores_exact=True)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify-owner-only', action='store_true')
    args = parser.parse_args()
    if shutil.disk_usage('C:/').free < 50*1024**3 or shutil.disk_usage('G:/').free < 75*1024**3+128*MIB:
        raise OSError('Handoff free-space floor')
    args.output.mkdir(parents=False, exist_ok=False)
    written = 0

    def put(path, raw):
        nonlocal written
        if written+len(raw) > 96*MIB:
            raise OSError('Complete handoff/restore allocation exceeded')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            if stream.write(raw) != len(raw):
                raise OSError('Short handoff write')
            stream.flush(); os.fsync(stream.fileno())
        if path.read_bytes() != raw:
            raise OSError('Handoff readback differs')
        written += len(raw)

    owner = registered_identity()
    put(args.output/'REGISTERED_OWNER.json', encoded(owner))
    try:
        if args.verify_owner_only:
            # Independent process API comparison after durable early registration.
            import psutil
            me = psutil.Process()
            if (me.pid != owner['pid'] or me.cpu_affinity() != [14] or
                    abs(me.create_time() - owner['create_time']) >= .001 or
                    registered_identity() != owner):
                raise ValueError('Exact kernel/psutil identity verification failed')
            receipt = dict(schema='just-peachy.handoff-owner-check.v1', passed=True,
                           exact_filetime=True, actual_affinity=[14],
                           registered_owner_sha256=digest(encoded(owner)),
                           project_plan_read=False, zip_created=False)
            put(args.output/'OWNER_VERIFICATION.json', encoded(receipt))
            print(json.dumps(receipt))
            return
        if args.plan is None:
            raise ValueError('--plan is required unless --verify-owner-only is set')
        bind_exact_sources(args.output, put)
        plan_raw = args.plan.read_bytes()
        if len(plan_raw) > MIB:
            raise ValueError('Plan bound')
        plan = json.loads(plan_raw)
        if plan.get('schema') != 'just-peachy.reviewed-public-handoff.v1' or plan.get('reviewed_publication') is not True:
            raise ValueError('Explicit reviewed publication plan required')
        rows = plan['files']
        if not isinstance(rows, list) or not 1 <= len(rows) <= 4096:
            raise ValueError('Handoff member count')
        members = {}; inventory = []; total = 0; aliases = {'manifest.json'}
        for row in rows:
            name = safe_member(row['member'])
            if name.casefold() in aliases or (PurePosixPath(name).suffix.lower() not in ALLOWED and name not in (SHELL_MEMBER, DIAGNOSTIC_MEMBER)):
                raise ValueError('Duplicate or non-source handoff member')
            aliases.add(name.casefold())
            source = Path(row['source'])
            if ((name in (SHELL_MEMBER, DIAGNOSTIC_MEMBER) or source.suffix.lower() == '.ps1') and not (
                    is_named_shell(name, source, row['sha256']))):
                raise ValueError('Only the exact two shell members/sources/hashes are admitted')
            resolved = source.resolve(strict=True)
            relative = resolved.relative_to(ROOT)
            if source.is_symlink() or os.path.normcase(str(source.absolute())) != os.path.normcase(str(resolved)):
                raise ValueError('Indirect publication source')
            if ((source.suffix.lower() not in ALLOWED and not (
                    is_named_shell(name, source, row['sha256'])))
                    or type(row['bytes']) is not int or not 0 <= row['bytes'] <= 2*MIB):
                raise ValueError('Source type or extent')
            if source.stat().st_size != row['bytes']:
                raise ValueError('Source extent changed')
            raw = source.read_bytes(); total += len(raw)
            if total > 20*MIB or digest(raw) != row['sha256']:
                raise ValueError('Source hash or total bound')
            raw.decode('utf-8')
            members[name] = raw
            inventory.append(dict(member=name, source=relative.as_posix(), bytes=len(raw), sha256=digest(raw)))
        members['MANIFEST.json'] = encoded(dict(schema='just-peachy.public-handoff-manifest.v1', files=inventory,
            scope=plan.get('scope'), model_weights_audio_galleries_included=False))
        put(args.output/'REVIEWED_PLAN.json', plan_raw)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted(members.items()):
                info = zipfile.ZipInfo(name, (2026, 10, 3, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3; info.external_attr = (stat.S_IFREG | 0o600) << 16
                archive.writestr(info, raw)
        raw_zip = buffer.getvalue()
        if len(raw_zip) > 20*MIB:
            raise ValueError('Handoff ZIP exceeds 20MiB')
        name = 'JustPeachy-v29-ChatGPT-handoff.zip'
        put(args.output/name, raw_zip)
        put(args.output/'independent-restore'/name, raw_zip)
        with zipfile.ZipFile(args.output/'independent-restore'/name) as archive:
            if set(archive.namelist()) != set(members):
                raise ValueError('Restore membership differs')
            for member, expected in members.items():
                actual = archive.read(member)
                if actual != expected:
                    raise ValueError('Restore member differs')
                put(args.output/'expanded-restore'/member, actual)
        receipt = dict(schema='just-peachy.v29.public-handoff.v1', path=str(args.output/name),
            bytes=len(raw_zip), sha256=digest(raw_zip), members=len(members), source_bytes=total,
            full_member_readback=True, independent_zip_and_expanded_restore=True,
            reviewed_plan_sha256=digest(plan_raw), output_bytes_before_receipt=written,
            models_audio_galleries_included=False)
        put(args.output/'HANDOFF_RECEIPT.json', encoded(receipt)); print(json.dumps(receipt))
    except BaseException as error:
        put(args.output/'FAILURE.json', encoded(dict(type=type(error).__name__, message=str(error)[:2048])))
        raise


if __name__ == '__main__':
    main()
