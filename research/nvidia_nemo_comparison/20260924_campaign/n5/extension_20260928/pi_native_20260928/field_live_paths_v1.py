"""Concrete one-run path projection; README_FIELD_STREAMED_MIRROR_V1.md."""
import re
from pathlib import PurePosixPath
from field_live_layout_v3 import specification


def project(session, conversation, epoch, runtime_token, code_files):
    """Map actual chosen identities, including partial files and empty guards.

    This is a census contract. It does not install or prove all runtime writers.
    Caller must bind observed IDs to the same admitted process before using it.
    """
    if not re.fullmatch(r'edge_[a-z_]+_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}', session):
        raise ValueError('Actual native session identifier required')
    for value in (conversation, epoch, runtime_token):
        if not re.fullmatch('[0-9a-f]{32}', value):
            raise ValueError('Exact one-run UUID required')
    if type(code_files) is not dict or not 1 <= len(code_files) <= 64:
        raise ValueError('Exact admitted flat code manifest required')
    layout, paths, buckets = specification(), {}, {}

    def add(name, size, bucket, total, count=1):
        if name in paths or type(size) is not int or size < 0:
            raise ValueError('Duplicate/invalid physical slot')
        paths[name] = dict(maximum_bytes=size, bucket=bucket)
        row = dict(maximum_bytes=total, maximum_files=count)
        if bucket in buckets and buckets[bucket] != row:
            raise ValueError('Inconsistent physical aggregate')
        buckets[bucket] = row

    for group, members in layout['groups'].items():
        add(group+'/.budget.guard', 0, group+'/guard', 0)
        if group == 'code':
            for name, size in code_files.items():
                if not re.fullmatch('[A-Za-z0-9_][A-Za-z0-9_.-]{0,100}', name) or type(size) is not int or not 0 < size <= 128*1024:
                    raise ValueError('Code manifest name/size')
                add('code/'+name, size, 'code', 2*1024**2, 64)
                add('code/'+name+'.pending', size, 'code', 2*1024**2, 64)
            if sum(code_files.values()) > 2*1024**2:
                raise ValueError('Code capsule aggregate')
            continue
        for name, row in members.items():
            size, base = row['maximum_bytes'], group+'/'+name
            if group == 'config' and name in ('settings.json', 'DATA_SCHEMA.json', 'last_application.json'):
                add('data/'+name, 32768, base, size, 2)
                add('data/.'+name+'.pending', 32768, base, size, 2)
            elif group == 'config' and name in ('live_config.json', 'n2_runtime.json'):
                add('data/'+name, size, base, size)
            else:
                add(base, size, base, size)
                if row['mode'] != 'append':
                    add(base+'.pending', size, base, size)
    native = 'data/sessions/'+session+'/'
    conv = 'data/conversations/'+conversation+'/'
    ep = conv+'epochs/'+epoch+'/'
    for key, row in layout['artifacts'].items():
        total = row['maximum_bytes']
        if key == 'archive_auxiliary':
            for name in row['paths']:
                add(ep+name, total, key, total, 2)
        elif key == 'native_controls':
            for name in row['paths']:
                add(native+name, 65536, key, total, 6)
                add(native+'.'+name+'.pending', 65536, key, total, 6)
        elif key == 'application_lock':
            # ApplicationLock fixes purpose='application'; both links temporarily
            # coexist during publication. Reserve the same1KiB as two512B names.
            add('data/runtime.lock', 512, key, total, 2)
            add('data/.runtime.'+runtime_token+'.tmp', 512, key, total, 2)
            add('data/.runtime.guard', 0, 'runtime_guard', 0)
        elif key in ('epoch_control', 'conversation_control', 'checkpoint_detail'):
            prefix = conv if key == 'conversation_control' else ep
            name = row['path']
            add(prefix+name, total//2, key, total, 2)
            add(prefix+'.'+name+'.pending', total//2, key, total, 2)
        elif key == 'archive_failure':
            add(ep+row['path'], total, key, total)
        else:
            name = row['path'].replace('<session>', session).replace('<conversation>', conversation).replace('<epoch>', epoch)
            add(name, total, key, total)
    directories = {n.replace('<session>', session).replace('<conversation>', conversation).replace('<epoch>', epoch)
                   for n in layout['directories']}
    for name in paths:
        for parent in PurePosixPath(name).parents:
            if parent.as_posix() != '.' and parent.as_posix() not in directories:
                raise ValueError('Unreserved physical parent: '+str(parent))
    maximum = sum(row['maximum_bytes'] for row in buckets.values()) + len(directories)*65536
    if maximum > layout['target_maximum_bytes']:
        raise ValueError('Physical projection exceeds retained layout')
    return dict(schema='just-peachy.live-physical-paths.v1', paths=paths, buckets=buckets,
                directories=sorted(directories), maximum_bytes=maximum,
                source_layout_maximum_bytes=layout['target_maximum_bytes'],
                runtime_binding_proven=False, live_d1_binding_proven=False)


def check_inventory(contract, files, directories):
    """Check sizes and independent aggregates of an already enumerated tree."""
    if set(directories)-set(contract['directories']):
        raise ValueError('Unassigned physical directory')
    usage = {name:[0,0] for name in contract['buckets']}
    for name, size in files.items():
        row = contract['paths'].get(name)
        if row is None or type(size) is not int or not 0 <= size <= row['maximum_bytes']:
            raise ValueError('Unassigned/oversized physical output: '+name)
        usage[row['bucket']][0] += size
        usage[row['bucket']][1] += 1
    for name, (size, count) in usage.items():
        cap = contract['buckets'][name]
        if size > cap['maximum_bytes'] or count > cap['maximum_files']:
            raise ValueError('Physical aggregate exceeded: '+name)
    return dict(file_bytes=sum(files.values()), file_count=len(files), directories=len(directories),
                within_projection=True, runtime_enforcement_proven=False)
