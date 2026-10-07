"""Finite SQLite file admission and non-content errors. README_STORAGE_RECOVERY.md."""
from __future__ import annotations

from pathlib import Path
import shutil
import stat
import sys
import re


SIDECARS = ('', '-journal', '-wal', '-shm')
MIB = 1024 * 1024


def sqlite_file_size_plan(root, metadata_bytes, policy, usage=None, *, database_name='history.sqlite3'):
    """Account for existing file lengths and fresh metadata/journal headroom.

    This is a per-file OS ceiling, not a recording quota. Already allocated
    database/sidecar bytes are not charged again as future growth. Scoped
    deletion uses bounded transactions instead of reserving a database-sized
    journal for every ordinary operation.
    """
    if type(metadata_bytes) is not int or metadata_bytes < 0:
        raise ValueError('Finite nonnegative SQLite metadata allowance required')
    if type(database_name) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}\.sqlite3',database_name) is None:
        raise ValueError('Bounded SQLite database basename required')
    root = Path(root).absolute()
    sizes = {}
    for suffix in SIDECARS:
        path = root / (database_name + suffix)
        for part in (path, *path.parents):
            try:
                info = part.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Real SQLite file paths required')
        try:
            info = path.stat()
        except FileNotFoundError:
            sizes[suffix] = 0
        else:
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('Regular single-link SQLite files required')
            sizes[suffix] = info.st_size
    usage = usage or shutil.disk_usage(root)
    reserve = policy.reserve(usage.total)
    available = max(0, usage.free - reserve)
    overhead = 8 * MIB
    growth = 2 * metadata_bytes + overhead
    # RLIMIT_FSIZE is an absolute per-file length, not a metadata reservation.
    # Allow a connection to use actual capacity even during a larger index
    # migration; bounded writers/transactions check current free space separately.
    physical_ceiling = max(0,usage.total-reserve)
    ceiling = min(physical_ceiling,max(sizes.values())+available)
    required = growth
    if required > available:
        raise OSError('SQLite writable admission requires %d bytes above reserve; available %d' %
                      (required, available))
    return dict(database_name=database_name,existing_history_bytes=sizes[''], existing_sidecar_bytes=sizes,
                metadata_bytes=metadata_bytes, journal_overhead_bytes=overhead,
                required_free_bytes=required, file_limit_bytes=ceiling,
                physical_file_ceiling_bytes=physical_ceiling,
                available_above_reserve=available, reserve_bytes=reserve)


def ensure_sqlite_file_limit(root, policy, *, metadata_bytes=0, database_name='history.sqlite3'):
    plan = sqlite_file_size_plan(root, metadata_bytes, policy,database_name=database_name)
    if sys.platform == 'linux':
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
        required = plan['file_limit_bytes']
        if hard != resource.RLIM_INFINITY and required > hard:
            raise OSError('SQLite file allowance %d exceeds inherited hard ceiling %d' % (required, hard))
        if soft != resource.RLIM_INFINITY and soft < required:
            resource.setrlimit(resource.RLIMIT_FSIZE, (required, hard))
        plan['effective_file_limit_bytes'] = resource.getrlimit(resource.RLIMIT_FSIZE)[0]
    return plan


def error_facts(error, *, operation=None, database=None):
    """Capture exception chains without SQL parameters, transcripts, or vectors."""
    chain, seen, current = [], set(), error
    while current is not None and id(current) not in seen and len(chain) < 8:
        seen.add(id(current))
        value = dict(type=type(current).__name__, message=str(current)[:1024])
        for field in ('sqlite_errorcode', 'sqlite_errorname', 'errno'):
            detail = getattr(current, field, None)
            if isinstance(detail, (int, str)):
                value[field] = detail
        code = value.get('sqlite_errorcode')
        if isinstance(code, int):
            value['sqlite_primary_errorcode'] = code & 255
        chain.append(value)
        current = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
    return dict(operation=operation, database=str(database) if database else None, chain=chain)


def annotate_error(error, *, operation, database):
    facts = error_facts(error, operation=operation, database=database)
    error.storage_diagnostic = facts
    if hasattr(error, 'add_note'):
        code = getattr(error, 'sqlite_errorcode', None)
        name = getattr(error, 'sqlite_errorname', None)
        error.add_note('Storage operation=%s database=%s SQLite code=%s name=%s' %
                       (operation, database, code, name))
    return facts
