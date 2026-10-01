"""Bounded immutable tree mirror; see README_FIELD_STREAMED_MIRROR_V1.md."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

from field_host_budget_v1 import HostBudgetError, encoded, floors, real

CHUNK = 16 * 1024
MAX_FILES = 256
MAX_DIRS = 64
MAX_FILE = 32 * 1024**2
MAX_MIRROR = 146_756_140
MAX_MANIFEST = 256 * 1024


def portable(name):
    if type(name) is not str or not name or len(name) > 480:
        raise ValueError('Bounded relative path required')
    p = PurePosixPath(name)
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(10)),
                *('LPT'+str(i) for i in range(10))}
    if p.is_absolute() or p.as_posix() != name or any(
        not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', part) or part in ('.', '..')
        or part.endswith('.') or part.split('.')[0].upper() in reserved for part in p.parts):
        raise ValueError('Portable unambiguous path required')
    # Leading dots and .pending are actual evidence names, not copy-state flags.
    return p


def ancestors(path):
    path = Path(path).absolute()
    for parent in reversed((path, *path.parents)):
        real(parent, True)
    return path


def identity(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


def inventory(root, deadline):
    root = ancestors(root)
    files, directories, aliases = {}, {''}, set()
    pending = [root]
    while pending:
        if time.monotonic() >= deadline:
            raise TimeoutError('Mirror deadline')
        directory = pending.pop()
        real(directory, True)
        for path in sorted(directory.iterdir()):
            name = path.relative_to(root).as_posix()
            portable(name)
            if name.casefold() in aliases:
                raise ValueError('Case-aliased source path')
            aliases.add(name.casefold())
            s = path.lstat()
            if stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Source link/reparse point')
            if stat.S_ISDIR(s.st_mode):
                directories.add(name)
                if len(directories) > MAX_DIRS:
                    raise HostBudgetError('Mirror directory cardinality')
                pending.append(path)
            else:
                real(path)
                if s.st_size > MAX_FILE:
                    raise HostBudgetError('Mirror file ceiling')
                files[name] = identity(s)
                if len(files) > MAX_FILES:
                    raise HostBudgetError('Mirror file cardinality')
    return files, directories


def plan(source, pinned_files, deadline, maximum_bytes=MAX_MIRROR):
    if type(maximum_bytes) is not int or not 1 <= maximum_bytes <= MAX_MIRROR:
        raise ValueError('Explicit mirror allowance')
    if type(pinned_files) is not dict or not 1 <= len(pinned_files) <= MAX_FILES:
        raise ValueError('Bounded closed source manifest required')
    if len(encoded(pinned_files)) > MAX_MANIFEST:
        raise ValueError('Source manifest ceiling')
    normalized = {}
    for name, row in pinned_files.items():
        portable(name)
        if type(row) is not dict or set(row) != {'bytes', 'sha256'}:
            raise ValueError('Exact source manifest fields')
        if type(row['bytes']) is not int or not 0 <= row['bytes'] <= MAX_FILE:
            raise ValueError('Source manifest file size')
        if type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
            raise ValueError('Source manifest digest')
        normalized[name] = dict(row)
    files, directories = inventory(source, deadline)
    if set(files) != set(normalized) or any(files[n][2] != normalized[n]['bytes'] for n in files):
        raise ValueError('Whole source tree differs from closed manifest')
    logical = sum(row['bytes'] for row in normalized.values())
    reserved = logical + len(directories)*65536
    if reserved > maximum_bytes:
        raise HostBudgetError('Mirror logical bytes plus directory reserve')
    return dict(files=normalized, directories=sorted(directories), bytes=logical,
                reserved_bytes=reserved, source_identities=files)


def _readback(path, expected, deadline):
    before = identity(real(path))
    h, count = hashlib.sha256(), 0
    with path.open('rb', buffering=0) as stream:
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('Mirror readback deadline')
            chunk = stream.read(CHUNK)
            if not chunk:
                break
            count += len(chunk)
            if count > expected['bytes']:
                raise HostBudgetError('Readback file grew')
            h.update(chunk)
    if before != identity(real(path)) or count != expected['bytes'] or h.hexdigest() != expected['sha256']:
        raise HostBudgetError('Exact streamed readback mismatch')


def publish(store, destination, source, pinned_files, *, deadline, maximum_bytes=MAX_MIRROR):
    """Mirror a closed, externally pinned LOCAL source tree, preserving every name.

    Caller must establish source owner closure and bound an earlier absolute
    process deadline. This function does not fetch from SSH or stop source owners.
    Existing destination always rejects, including after partial failure. Copy
    files use their exact names; only BACKUP.json certifies completed readback.
    No raw payload batch, overwrite, deletion, rotation or retry is performed.
    """
    if type(deadline) not in (int, float) or not time.monotonic() < deadline <= time.monotonic()+600:
        raise ValueError('Fresh bounded monotonic deadline required')
    source, destination = Path(source).absolute(), Path(destination).absolute()
    ancestors(source)
    ancestors(destination.parent)
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Disjoint source and destination required')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Mirror already attempted; preserve and inspect it')
    value = plan(source, pinned_files, deadline, maximum_bytes)
    public = {k:v for k,v in value.items() if k != 'source_identities'}
    receipt = encoded(dict(status='EXACT_STREAMED_BACKUP_VERIFIED', chunk_bytes=CHUNK,
                           source=str(source), destination=str(destination), **public))
    if len(receipt) > MAX_MANIFEST:
        raise HostBudgetError('Backup receipt ceiling')
    store.preflight('BACKUP.json', receipt)
    with store.locked():
        rows = store.inventory('metadata')
        cap, _, count = store.limits['metadata']
        if 'BACKUP.json' in rows or any(n.endswith('.pending') for n in rows):
            raise HostBudgetError('Existing/pending backup receipt')
        if sum(rows.values())+len(receipt) > cap or len(rows)+1 > count:
            raise HostBudgetError('Backup metadata reservation')
        floors(value['reserved_bytes']+len(receipt))
        destination.mkdir()
        for name in sorted(value['directories'], key=lambda n:(n.count('/'), n)):
            if name:
                destination.joinpath(*PurePosixPath(name).parts).mkdir()
        chunks, verified_destinations = 0, {}
        for name, expected in sorted(value['files'].items()):
            src = source.joinpath(*PurePosixPath(name).parts)
            dst = destination.joinpath(*PurePosixPath(name).parts)
            ancestors(src.parent); ancestors(dst.parent)
            if identity(real(src)) != value['source_identities'][name]:
                raise HostBudgetError('Source changed before copy')
            h, written = hashlib.sha256(), 0
            with src.open('rb', buffering=0) as reader, dst.open('xb', buffering=0) as writer:
                while True:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Mirror copy deadline')
                    chunk = reader.read(CHUNK)
                    if not chunk:
                        break
                    if written+len(chunk) > expected['bytes']:
                        raise HostBudgetError('Source grew while copying')
                    floors(len(chunk))
                    view = memoryview(chunk)
                    while view:
                        n = writer.write(view)
                        if not n:
                            raise OSError('Incomplete mirror write')
                        written += n
                        view = view[n:]
                    h.update(chunk); chunks += 1
                os.fsync(writer.fileno())
            if identity(real(src)) != value['source_identities'][name] or written != expected['bytes'] or h.hexdigest() != expected['sha256']:
                raise HostBudgetError('Source identity/bytes/digest changed')
            _readback(dst, expected, deadline)
            verified_destinations[name] = identity(real(dst))
        after, directories = inventory(source, deadline)
        if after != value['source_identities'] or directories != set(value['directories']):
            raise HostBudgetError('Source tree changed during mirror')
        copied, copied_dirs = inventory(destination, deadline)
        if copied != verified_destinations or copied_dirs != set(value['directories']):
            raise HostBudgetError('Mirror tree membership drift')
        # The existing bounded host publisher preserves a failed pending receipt.
        store._write_locked('BACKUP.json', receipt, 'metadata')
    return dict(public, chunk_bytes=CHUNK, data_chunks=chunks, completed=True)
