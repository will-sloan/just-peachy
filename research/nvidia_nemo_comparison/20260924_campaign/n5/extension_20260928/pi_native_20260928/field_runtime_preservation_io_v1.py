"""Complete finite runtime tree I/O; README_FIELD_RUNTIME_EXPORT_V1.md."""
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import time

from field_runtime_policy_v3 import validate, encoded, digest
from field_runtime_preservation_v2 import partitions, decode_owners
from field_host_budget_v1 import real, floors
from field_operator_broker_streamed_mirror_v1 import MAX_FILES, MAX_DIRS, MAX_FILE, ancestors
from field_local_release_plan_v2 import CONTROL_RECORDS, LAUNCH_RECORDS, RECORDING_RECORDS


def stamp(path, directory=False):
    row = real(path, directory)
    return (row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns, row.st_ctime_ns)


def limits(policy):
    validate(policy)
    a = policy['allocation']
    return dict(files=16+2*(len(CONTROL_RECORDS)+len(a['launch_slots'])*len(LAUNCH_RECORDS)+len(a['recording_slots'])*len(RECORDING_RECORDS))+a['recordings']*MAX_FILES,
                directories=a['metadata_directories']+a['recordings']*MAX_DIRS,
                maximum_bytes=a['metadata_maximum_bytes']+a['recordings']*a['local_backup_per_recording'])


def scan(root, policy, guard):
    root = Path(root).absolute(); ancestors(root); real(root, True)
    bound = limits(policy); result = {}; directories = {''}; stack = [(root, '')]
    while stack:
        guard(); current, prefix = stack.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                guard()
                name = prefix+'/'+entry.name if prefix else entry.name
                path = Path(entry.path); info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    real(path, True); directories.add(name); stack.append((path, name))
                else:
                    row = stamp(path)
                    if row[2] > MAX_FILE:
                        raise ValueError('Original32MiB member cap')
                    result[name] = row
                if len(result) > bound['files'] or len(directories) > bound['directories']:
                    raise ValueError('Sum of independent producer cardinalities')
    return result, directories


def hash_file(path, expected, guard):
    h = hashlib.sha256(); count = 0
    with Path(path).open('rb', buffering=0) as stream:
        while True:
            guard(); block = stream.read(16384)
            if not block:
                break
            count += len(block)
            if count > expected[2]:
                raise ValueError('Source grew during hash')
            h.update(block)
    if count != expected[2] or stamp(path) != expected:
        raise ValueError('Source identity changed during hash')
    return h.hexdigest()


def census(root, policy, manifest, guard):
    """No writes. Caller owns native process/unit/lease/whole-root lock checks."""
    root = Path(root).absolute(); before, directories = scan(root, policy, guard)
    # Reject unknown paths and independent overflow before reading any large payload.
    provisional = {n:dict(bytes=s[2],sha256='0'*64) for n,s in before.items()}
    partitions(provisional, directories, policy, manifest)
    files = {}; owners = {}
    for name, identity in sorted(before.items()):
        guard(); path = root/name
        pin = hash_file(path, identity, guard)
        files[name] = dict(bytes=identity[2], sha256=pin)
        if 'owner' in path.name.lower() and path.name.endswith('.json'):
            if identity[2] > 16384:
                raise ValueError('Completed owner envelope bound')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != pin or stamp(path) != identity:
                raise ValueError('Owner identity changed')
            owners[name] = raw
    ownership = decode_owners(owners, policy)
    after, final_dirs = scan(root, policy, guard)
    if after != before or final_dirs != directories:
        raise ValueError('Whole tree changed during census')
    plan = partitions(files, directories, policy, manifest)
    return dict(plan=plan, ownership=ownership, identities=before, directories=directories)


def write_all(stream, raw, guard):
    view = memoryview(raw)
    while view:
        guard(); count = stream.write(view[:16384])
        if type(count) is not int or not 1 <= count <= min(16384, len(view)):
            raise OSError('Invalid/short bounded stream write')
        view = view[count:]


def frame(stream, value, guard):
    raw = encoded(value)
    if not 0 < len(raw) <= 262144:
        raise ValueError('Original256KiB frame bound')
    write_all(stream, struct.pack('!I',len(raw))+raw, guard); stream.flush()


def read_exact(stream, count, guard):
    if type(count) is not int or not 0 <= count <= 262144:
        raise ValueError('Bounded exact read')
    out = bytearray()
    while len(out) < count:
        guard(); block = stream.read(min(16384, count-len(out)))
        if not block:
            raise EOFError('Truncated runtime export')
        out.extend(block)
    return bytes(out)


def read_frame(stream, guard):
    count = struct.unpack('!I', read_exact(stream,4,guard))[0]
    if not 0 < count <= 262144:
        raise ValueError('Original256KiB metadata frame')
    def pairs(rows):
        value={}
        for key,item in rows:
            if key in value:
                raise ValueError('Duplicate frame key')
            value[key]=item
        return value
    def bad(value):
        raise ValueError('Nonfinite frame JSON')
    return json.loads(read_exact(stream,count,guard),object_pairs_hook=pairs,parse_constant=bad)


def send_census(stream, value, guard):
    plan = value['plan']
    header = dict(type='RUNTIME_CENSUS',index=plan['index'],files=plan['files'],
                  reserved_bytes=plan['reserved_bytes'],maximum_bytes=plan['maximum_bytes'],
                  global_manifest_sha256=plan['global_manifest_sha256'],ownership=value['ownership'])
    if len(encoded(header)) > 65536:
        raise ValueError('Bounded census header and actual owner set')
    frame(stream, header, guard)
    for name, partition in sorted(plan['partitions'].items()):
        frame(stream, dict(type='PARTITION',name=name,manifest=partition), guard)


def read_census(stream, policy, manifest, guard):
    header = read_frame(stream,guard)
    fields = {'type','index','files','reserved_bytes','maximum_bytes','global_manifest_sha256','ownership'}
    if type(header) is not dict or set(header) != fields or header['type'] != 'RUNTIME_CENSUS':
        raise ValueError('Exact runtime census header')
    index = header['index']
    if (type(index) is not dict or not 1 <= len(index) <= 1+policy['allocation']['recordings']
            or len(encoded(index)) > 16384 or digest(index) != header['global_manifest_sha256']):
        raise ValueError('Exact independently bounded index')
    files = {}; dirs = set(); parts = {}
    for name in sorted(index):
        row = read_frame(stream,guard)
        if type(row) is not dict or set(row) != {'type','name','manifest'} or row['type']!='PARTITION' or row['name']!=name:
            raise ValueError('Exact ordered partition')
        value = row['manifest']; parts[name] = value
        if type(value) is not dict or set(value) != {'prefix','files','directories','bytes','reserved_bytes','maximum_bytes'}:
            raise ValueError('Exact partition manifest')
        if index[name].get('manifest_sha256') != digest(value):
            raise ValueError('Pinned complete partition')
        prefix = value['prefix']
        for rel, pin in value['files'].items():
            full = prefix+'/'+rel if prefix else rel
            if full in files:
                raise ValueError('Overlapping producer file')
            files[full] = pin
        for rel in value['directories']:
            full = prefix+'/'+rel if prefix and rel else prefix or rel
            if full in dirs:
                raise ValueError('Overlapping producer directory')
            dirs.add(full)
    checked = partitions(files,dirs,policy,manifest)
    if encoded(checked['partitions']) != encoded(parts) or encoded(checked['index']) != encoded(index):
        raise ValueError('Whole independent partition contract')
    for name in ('files','reserved_bytes','maximum_bytes','global_manifest_sha256'):
        if encoded(checked[name]) != encoded(header[name]):
            raise ValueError('Whole census total mismatch')
    # Ownership is re-decoded from actual copied bytes before success; header is not physical closure.
    return dict(plan=checked,files=files,directories=dirs,ownership=header['ownership'])


def export_files(stream, root, value, policy, guard):
    root=Path(root).absolute(); total=0; count=0
    for group, partition in sorted(value['plan']['partitions'].items()):
        for rel,pin in sorted(partition['files'].items()):
            name=partition['prefix']+'/'+rel if partition['prefix'] else rel
            path=root/name; before=value['identities'][name]
            if stamp(path)!=before:
                raise ValueError('Changed pre-send file')
            frame(stream,dict(type='FILE',path=name,bytes=pin['bytes']),guard)
            h=hashlib.sha256();left=pin['bytes']
            with path.open('rb',buffering=0) as source:
                while left:
                    guard();block=source.read(min(left,16384))
                    if not block:
                        raise EOFError('Truncated native source')
                    write_all(stream,block,guard);h.update(block);left-=len(block);total+=len(block)
                if source.read(1):
                    raise ValueError('Native source grew')
            if stamp(path)!=before or h.hexdigest()!=pin['sha256']:
                raise ValueError('Native sent file changed')
            count+=1
    stream.flush()
    after,dirs=scan(root,policy,guard)
    if after!=value['identities'] or dirs!=value['directories']:
        raise ValueError('Final whole native membership/identity changed')
    frame(stream,dict(type='SOURCE_UNCHANGED',files=count,bytes=total,
          global_manifest_sha256=value['plan']['global_manifest_sha256']),guard)


def receive_files(stream, destination, expected, policy, manifest, guard, verify_closed):
    """Fresh complete PC copy; exact native closure must finish before success."""
    if not callable(verify_closed):
        raise ValueError('Independent actual closure callback required')
    destination=Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Fresh output only; failed mirrors remain preserved')
    ancestors(destination.parent); real(destination.parent,True)
    plan=expected['plan']; guard();floors(plan['maximum_bytes'])
    # Validate the complete independent expectation before the first output mutation.
    checked=partitions(expected['files'],expected['directories'],policy,manifest)
    if encoded(checked)!=encoded(plan):
        raise ValueError('Prevalidated complete independent mirror expectation')
    destination.mkdir()
    for name in sorted(expected['directories'],key=lambda n:(len(Path(n).parts),n)):
        if name:
            guard(); (destination/name).mkdir()
    total=0;count=0;chunks=0
    for group,partition in sorted(plan['partitions'].items()):
        for rel,pin in sorted(partition['files'].items()):
            name=partition['prefix']+'/'+rel if partition['prefix'] else rel
            header=read_frame(stream,guard)
            if encoded(header)!=encoded(dict(type='FILE',path=name,bytes=pin['bytes'])):
                raise ValueError('Exact ordered file frame')
            path=destination/name;guard();real(path.parent,True)
            h=hashlib.sha256();left=pin['bytes']
            with path.open('xb',buffering=0) as target:
                while left:
                    guard(); block=read_exact(stream,min(left,16384),guard)
                    if target.write(block)!=len(block):
                        raise OSError('Partial PC write; retain failed destination')
                    h.update(block);left-=len(block);total+=len(block);chunks+=1
                os.fsync(target.fileno())
            if h.hexdigest()!=pin['sha256']:
                raise ValueError('PC transfer hash mismatch')
            count+=1
    final=read_frame(stream,guard)
    if encoded(final)!=encoded(dict(type='SOURCE_UNCHANGED',files=count,bytes=total,
            global_manifest_sha256=plan['global_manifest_sha256'])):
        raise ValueError('Whole source final declaration mismatch')
    closure=verify_closed()
    if closure is not True:
        raise ValueError('Natural source reap and exact closure required before backup')
    # Independent complete readback, strict nested owner decoding and membership.
    actual=census(destination,policy,manifest,guard)
    if encoded(actual['plan'])!=encoded(plan) or encoded(actual['ownership'])!=encoded(expected['ownership']):
        raise ValueError('Full independent PC readback differs')
    return dict(status='EXACT_RUNTIME_TREE_COPY',files=count,bytes=total,chunks=chunks,
                global_manifest_sha256=plan['global_manifest_sha256'],native_source_closed=True,
                ownership=actual['ownership'],recording_success_claimed=False)

