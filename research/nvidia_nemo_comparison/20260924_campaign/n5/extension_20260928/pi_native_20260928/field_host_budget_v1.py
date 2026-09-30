"""Portable host metadata publication. See README_FIELD_HOST_BUDGET_V1.md."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat

MIB = 1024**2
LIMITS = {'metadata': (2*MIB, MIB, 24), 'failure': (MIB, 256*1024, 8),
          'closure': (512*1024, 128*1024, 8)}
MAP = {name: 'metadata' for name in (
    'ADMISSION.json', 'CENSUS.json', 'PREFLIGHT.json', 'REGISTERED_OWNER.json',
    'JOB_ENVELOPE.json', 'LAUNCH.json', 'RESULT.json', 'REVIEW.json', 'BACKUP.json')}
for role in ('worker', 'coordinator', 'review'):
    MAP[role+'.raw'] = 'failure'
    MAP[role+'-failure.json'] = 'failure'
    MAP[role+'-closure.json'] = 'closure'


class HostBudgetError(RuntimeError):
    pass


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def real(path, directory=False):
    s = Path(path).lstat()
    if stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 0x400:
        raise HostBudgetError('Reparse/symlink rejected')
    if directory:
        if not stat.S_ISDIR(s.st_mode):
            raise HostBudgetError('Real directory required')
    elif not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
        raise HostBudgetError('Single-link regular file required')
    return s


def floors(additional=0):
    # These are host floors, separate from the fixed 32GB Pi floor.
    if os.name == 'nt':
        for drive, gib in (('C:/', 50), ('G:/', 75)):
            if shutil.disk_usage(drive).free < gib*1024**3+additional:
                raise HostBudgetError('Host free-space reserve')
    elif shutil.disk_usage('/').free < 5*1024**3+additional:
        raise HostBudgetError('Portable fixture free-space reserve')


class HostStore:
    """Four declared directories and one lock byte; cooperating writers only.

    Immutable publication, including a pending file until the atomic rename.
    A failed pending write blocks subsequent ordinary writes in that group.
    Failure and closure groups remain separately reserved. No deletion/retry.
    """
    def __init__(self, root, limits=None):
        self.root = Path(root).absolute()
        self.limits = {k: tuple(v) for k, v in (limits or LIMITS).items()}
        if set(self.limits) != set(LIMITS):
            raise ValueError('Exact host groups required')
        for key, values in self.limits.items():
            if len(values) != 3 or any(type(v) is not int or v <= 0 for v in values):
                raise ValueError('Positive integer host limits required')
            if values[1] > values[0] or any(v > cap for v, cap in zip(values, LIMITS[key])):
                raise ValueError('Host ceiling exceeded')

    def preflight(self, name, raw):
        if name not in MAP or type(raw) is not bytes:
            raise ValueError('Mapped host name and exact bytes required')
        group = MAP[name]
        if len(raw) > self.limits[group][1]:
            raise HostBudgetError('Host write/file cap')
        if name.endswith('.json'):
            json.loads(raw.decode('utf-8'), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        return group

    def create(self, initial):
        if type(initial) is not dict:
            raise ValueError('Initial batch required')
        counts = {k: [0, 0] for k in LIMITS}
        for name, raw in initial.items():
            group = self.preflight(name, raw)
            counts[group][0] += len(raw); counts[group][1] += 1
        for group, (size, count) in counts.items():
            if size > self.limits[group][0] or count > self.limits[group][2]:
                raise HostBudgetError('Initial host group cap')
        # No directories exist until the whole initial batch passes.
        floors(sum(v[0] for v in counts.values()) + 512*1024)
        real(self.root.parent, True)
        self.root.mkdir()
        for group in LIMITS:
            (self.root/group).mkdir()
        with (self.root/'.host.guard').open('xb') as f:
            f.write(b'0'); f.flush(); os.fsync(f.fileno())
        for name, raw in initial.items():
            self.write(name, raw)
        return self

    def layout(self):
        real(self.root, True)
        if {p.name for p in self.root.iterdir()} != set(LIMITS) | {'.host.guard'}:
            raise HostBudgetError('Host directory membership drift')
        for group in LIMITS:
            real(self.root/group, True)
        if real(self.root/'.host.guard').st_size != 1:
            raise HostBudgetError('Invalid host guard')

    @contextmanager
    def locked(self):
        self.layout()
        fd = os.open(self.root/'.host.guard', os.O_RDWR | getattr(os, 'O_BINARY', 0))
        held = False
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            held = True
            self.layout()
            yield
        finally:
            if held and os.name == 'nt':
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            os.close(fd)

    def inventory(self, group):
        rows = {}
        for p in (self.root/group).iterdir():
            name = p.name.removesuffix('.pending')
            if name not in MAP or MAP[name] != group:
                raise HostBudgetError('Unmapped host file')
            s = real(p)
            if s.st_size > self.limits[group][1]:
                raise HostBudgetError('Existing host file exceeds cap')
            rows[p.name] = s.st_size
        if sum(rows.values()) > self.limits[group][0] or len(rows) > self.limits[group][2]:
            raise HostBudgetError('Existing host group exceeds cap')
        return rows

    def write(self, name, raw):
        group = self.preflight(name, raw)
        with self.locked():
            return self._write_locked(name, raw, group)

    def _write_locked(self, name, raw, group):
        rows = self.inventory(group)
        if any(n.endswith('.pending') for n in rows):
            raise HostBudgetError('Preserved partial requires review')
        if name in rows:
            raise FileExistsError(name)
        cap, _, count = self.limits[group]
        if sum(rows.values())+len(raw) > cap or len(rows)+1 > count:
            raise HostBudgetError('Host group bytes/count cap')
        floors(len(raw))
        destination = self.root/group/name
        pending = destination.with_name(name+'.pending')
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
        try:
            view = memoryview(raw)
            while view:
                n = os.write(fd, view)
                if n <= 0:
                    raise OSError('Incomplete host write')
                view = view[n:]
            os.fsync(fd)
        finally:
            os.close(fd)
        # No cooperating replacement is permitted; existing destinations fail.
        if destination.exists():
            raise FileExistsError(destination)
        os.rename(pending, destination)
        if destination.read_bytes() != raw:
            raise HostBudgetError('Host publication readback mismatch')
        return {'name': name, 'bytes': len(raw), 'sha256': digest(raw)}

    def json(self, name, value):
        return self.write(name, encoded(value))

    def failure(self, role, raw, error):
        if role not in ('worker', 'coordinator', 'review') or type(raw) is not bytes:
            raise ValueError('Failure role/raw required')
        receipt = {'logical_success': False, 'bytes': len(raw), 'sha256': digest(raw),
                   'error_type': type(error).__name__, 'raw_retained': False}
        try:
            self.write(role+'.raw', raw)
            receipt['raw_retained'] = True
        except Exception as exc:
            receipt['retention_error'] = type(exc).__name__
        try:
            self.json(role+'-failure.json', receipt)
            receipt['receipt_retained'] = True
        except Exception as exc:
            receipt.update(receipt_retained=False, receipt_error=type(exc).__name__)
        return receipt


def backup_plan(batch, max_bytes=MIB, max_files=64, max_dirs=8):
    """Whole in-memory batch and exact manifest checked before any destination."""
    if type(batch) is not dict or not batch:
        raise ValueError('Nonempty backup batch required')
    if any(type(x) is not int or x <= 0 or x > cap for x, cap in ((max_bytes, MIB), (max_files, 64), (max_dirs, 8))):
        raise ValueError('Small backup limits required')
    rows = {}; directories = {''}; folded = set()
    for name, raw in batch.items():
        if type(name) is not str or type(raw) is not bytes or len(raw) > 32*MIB:
            raise ValueError('Backup name/bytes/file cap')
        p = PurePosixPath(name)
        if p.is_absolute() or p.as_posix() != name or any(
            not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,100}', part)
            or part in ('.', '..') or part.endswith(('.', ' '))
            or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(10)],*[f'LPT{i}' for i in range(10)]}
            for part in p.parts):
            raise ValueError('Portable backup path required')
        if name.casefold() in folded or name.endswith('.pending'):
            raise ValueError('Backup alias/pending name')
        folded.add(name.casefold())
        directories.update(parent.as_posix() if parent.as_posix() != '.' else '' for parent in p.parents)
        rows[name] = {'bytes': len(raw), 'sha256': digest(raw)}
    if len({d.casefold() for d in directories}) != len(directories):
        raise ValueError('Backup directory case alias')
    if folded & {d.casefold() for d in directories}:
        raise ValueError('Backup file/directory collision')
    if len(rows) > max_files or len(directories) > max_dirs or sum(r['bytes'] for r in rows.values()) > max_bytes:
        raise HostBudgetError('Backup total/count/directory cap')
    return {'files': rows, 'directories': sorted(directories), 'bytes': sum(r['bytes'] for r in rows.values()),
            'directory_reservation_bytes': len(directories)*65536}


def publish_backup(store, destination, batch, **limits):
    plan = backup_plan(batch, **limits)
    receipt = encoded({'status': 'EXACT_BACKUP_VERIFIED', **plan})
    store.preflight('BACKUP.json', receipt)
    # Reserve metadata bytes and its file slot before publishing backup payload.
    # Keep the store lock through the copy; cooperate through this interface only.
    with store.locked():
        rows = store.inventory('metadata'); cap, _, count = store.limits['metadata']
        if 'BACKUP.json' in rows or any(n.endswith('.pending') for n in rows):
            raise HostBudgetError('Existing/pending backup metadata')
        if sum(rows.values())+len(receipt) > cap or len(rows)+1 > count:
            raise HostBudgetError('Backup metadata reservation')
        destination = Path(destination)
        real(destination.parent, True)
        floors(plan['bytes']+len(receipt)+plan['directory_reservation_bytes'])
        destination.mkdir()
        for name in sorted(plan['directories'], key=lambda n: (n.count('/'), n)):
            if name:
                destination.joinpath(*PurePosixPath(name).parts).mkdir()
        for name, raw in sorted(batch.items()):
            dest = destination.joinpath(*PurePosixPath(name).parts)
            pending = dest.with_name(dest.name+'.pending')
            with pending.open('xb') as f:
                f.write(raw); f.flush(); os.fsync(f.fileno())
            if pending.read_bytes() != raw:
                raise HostBudgetError('Backup readback mismatch')
            os.rename(pending, dest)
        store._write_locked('BACKUP.json', receipt, 'metadata')
    return plan
