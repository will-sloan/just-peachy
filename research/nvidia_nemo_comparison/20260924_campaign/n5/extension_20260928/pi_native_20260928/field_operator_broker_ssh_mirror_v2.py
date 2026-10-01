"""Native broker qualification component; README_FIELD_OPERATOR_BROKER_QUALIFICATION_V1.md."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import struct
import time

from field_host_budget_v1 import HostBudgetError, encoded, floors, real
from field_operator_broker_streamed_mirror_v1 import (CHUNK, MAX_DIRS, MAX_FILE, MAX_FILES,
    MAX_MANIFEST, MAX_MIRROR, _readback, ancestors, identity, inventory, portable)


def read_exact(stream, count, deadline):
    if type(count) is not int or not 0 <= count <= MAX_MANIFEST:
        raise ValueError('Bounded frame read required')
    parts = []
    remaining = count
    while remaining:
        if time.monotonic() >= deadline:
            raise TimeoutError('SSH mirror deadline')
        part = stream.read(min(remaining, CHUNK))
        if not part:
            raise EOFError('Truncated SSH mirror frame')
        parts.append(part)
        remaining -= len(part)
    return b''.join(parts)


def receive_json(stream, deadline):
    size = struct.unpack('!I', read_exact(stream, 4, deadline))[0]
    if size > MAX_MANIFEST:
        raise HostBudgetError('SSH metadata frame ceiling')
    return json.loads(read_exact(stream, size, deadline),
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))


def send_json(stream, value):
    raw = encoded(value)
    if len(raw) > MAX_MANIFEST:
        raise HostBudgetError('SSH metadata frame ceiling')
    write_all(stream, struct.pack('!I', len(raw)) + raw)
    stream.flush()


def write_all(stream, raw):
    view = memoryview(raw)
    while view:
        count = stream.write(view)
        if not count:
            raise OSError('Incomplete protocol write')
        view = view[count:]


def validate_plan(value, pinned_files, maximum_bytes, allow_empty=False):
    if type(maximum_bytes) is not int or not 1 <= maximum_bytes <= MAX_MIRROR:
        raise ValueError('Explicit mirror ceiling required')
    if type(value) is not dict or set(value) != {'files', 'directories', 'bytes', 'reserved_bytes'}:
        raise ValueError('Exact stream plan fields')
    if type(allow_empty) is not bool:raise ValueError('Exact empty-tree scope')
    if type(value['files']) is not dict or not (0 if allow_empty else 1) <= len(value['files']) <= MAX_FILES:
        raise ValueError('File cardinality')
    if encoded(value['files']) != encoded(pinned_files):
        # Canonical ordering is established by the exporter and caller.
        raise ValueError('Stream manifest differs from independently pinned manifest')
    aliases = set()
    for name, row in value['files'].items():
        portable(name)
        if type(row) is not dict or set(row) != {'bytes', 'sha256'}:
            raise ValueError('File fields')
        if type(row['bytes']) is not int or not 0 <= row['bytes'] <= MAX_FILE:
            raise ValueError('File ceiling')
        if type(row['sha256']) is not str or len(row['sha256']) != 64 or any(c not in '0123456789abcdef' for c in row['sha256']):
            raise ValueError('File digest')
        if name.casefold() in aliases:
            raise ValueError('Case alias')
        aliases.add(name.casefold())
    dirs = value['directories']
    if type(dirs) is not list or not 1 <= len(dirs) <= MAX_DIRS or dirs != sorted(set(dirs)) or '' not in dirs:
        raise ValueError('Directory cardinality/order')
    for name in dirs:
        if name:
            portable(name)
            if name.casefold() in aliases:
                raise ValueError('Directory alias/file collision')
            aliases.add(name.casefold())
    for name in list(value['files']) + [n for n in dirs if n]:
        parent = PurePosixPath(name).parent.as_posix()
        if ('' if parent == '.' else parent) not in dirs:
            raise ValueError('Missing declared parent')
    logical = sum(r['bytes'] for r in value['files'].values())
    reserved = logical + len(dirs)*65536
    if any(type(value[k]) is not int for k in ('bytes', 'reserved_bytes')) or value['bytes'] != logical or value['reserved_bytes'] != reserved or reserved > maximum_bytes:
        raise HostBudgetError('Stream allocation mismatch')
    return value


def receive(store, destination, stream, pinned_files, *, deadline, maximum_bytes,
            verify_process_closed, source_label, partial_binding=None):
    """Receive after owner ACK; caller owns SSH/watchdog/stderr/process closure.

    The callback must reap SSH and verify the exact remote identity is dead.
    No BACKUP.json is published before that callback succeeds. All partial files
    remain under exact source names; a previously attempted destination rejects.
    """
    destination = Path(destination).absolute()
    ancestors(destination.parent)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Preserve attempted mirror; no retry')
    if partial_binding is not None:
        from field_operator_broker_partial_v1 import validate,inventory as partial_inventory
        validate(partial_binding)
        inspect_tree=lambda root,end:partial_inventory(root,end,partial_binding)
    else:inspect_tree=inventory
    value = validate_plan(receive_json(stream, deadline), pinned_files, maximum_bytes, partial_binding is not None)
    if partial_binding is not None:
        from field_operator_broker_partial_v1 import projection
        projection(value['files'],value['directories'],partial_binding)
    receipt = encoded(dict(status='EXACT_SSH_STREAMED_BACKUP_VERIFIED',
        source=source_label, destination=str(destination), chunk_bytes=CHUNK, **value))
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
        chunks, copied, logical = 0, {}, 0
        for name, expected in sorted(value['files'].items()):
            header = receive_json(stream, deadline)
            if encoded(header) != encoded(dict(file=name, bytes=expected['bytes'])):
                raise ValueError('File order/identity/size mismatch')
            dst = destination.joinpath(*PurePosixPath(name).parts)
            ancestors(dst.parent)
            h, remaining = hashlib.sha256(), expected['bytes']
            with dst.open('xb', buffering=0) as writer:
                while remaining:
                    block = read_exact(stream, min(CHUNK, remaining), deadline)
                    floors(len(block))
                    view = memoryview(block)
                    while view:
                        n = writer.write(view)
                        if not n:
                            raise OSError('Incomplete SSH mirror write')
                        view = view[n:]
                    h.update(block); remaining -= len(block); logical += len(block); chunks += 1
                os.fsync(writer.fileno())
            if h.hexdigest() != expected['sha256']:
                raise HostBudgetError('Stream digest mismatch')
            _readback(dst, expected, deadline)
            copied[name] = identity(real(dst))
        terminal = receive_json(stream, deadline)
        if terminal != dict(status='SOURCE_TREE_UNCHANGED', files=len(copied), bytes=logical):
            raise ValueError('Missing exact source terminal')
        verify_process_closed()
        actual, dirs = inspect_tree(destination, deadline)
        if actual != copied or dirs != set(value['directories']):
            raise HostBudgetError('Destination changed before completion')
        store._write_locked('BACKUP.json', receipt, 'metadata')
    return dict(files=len(copied), bytes=logical, data_chunks=chunks,
                chunk_bytes=CHUNK, process_closed_before_completion=True)
