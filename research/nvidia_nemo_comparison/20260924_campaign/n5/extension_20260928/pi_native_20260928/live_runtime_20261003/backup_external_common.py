"""Bounded exact-scope backup primitives. See README_BACKUP_EXTERNAL.md."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat

MAX_CENSUS = 2 * 1024**2
MAX_FILES = 4096
CHUNK = 16384

SELECTED_RELEASE = '/home/peachyprototype/JustPeachy/install/releases/proto1-cm5-20260923-rc5'
SELECTOR_PIN = (191, 'fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3')

NATIVE_EXTRA_FILES = {
    '/home/peachyprototype/.config/autostart/just-peachy.desktop':
        (427, '8841a9fe0f62b662906bb9cb0d8914ac9bab86ebb7c4d28f7699194971f39206'),
    '/home/peachyprototype/JustPeachy/start-prototype.sh':
        (405, '79b7b08db6a67060bfc20a02ae8af437b37a938eb1f4e33817adcdb33d57f19f'),
}


def validate_native_source(name, *, is_file, member=None):
    """Native guard/probe share exact scope, including two pinned startup files."""
    path=PurePosixPath(name);base=PurePosixPath('/home/peachyprototype/JustPeachy')
    allowed=(base/'research/nemotron-20260928',base/'data',base/'config')
    exact={PurePosixPath('/home/peachyprototype/.config/kanshi/config'),base/'install/current.json'}
    if (str(path)!=name or '..' in path.parts or
        not (any(root in path.parents for root in allowed) or path in exact or
             name in NATIVE_EXTRA_FILES or path==PurePosixPath(SELECTED_RELEASE) or PurePosixPath(SELECTED_RELEASE) in path.parents or
             is_file and path.parent==PurePosixPath('/home/peachyprototype/Desktop'))):
        raise ValueError('Narrow current release/data/config or explicit desktop file scope required')
    if name in NATIVE_EXTRA_FILES:
        if not is_file:raise ValueError('Exact startup file required')
        if member is not None and (member['identity']['bytes'],member['sha256'])!=NATIVE_EXTRA_FILES[name]:
            raise ValueError('Exact current startup file pin differs')


def validate_native_census(census):
    # The one external extension is bound to the observed current selector.
    selected=PurePosixPath(SELECTED_RELEASE)
    sources=[row['source'] for row in census['files']]+[row['path'] for row in census['external_assets']]
    if any(PurePosixPath(path)==selected or selected in PurePosixPath(path).parents for path in sources):
        rows=[row for row in census['files'] if row['source']=='/home/peachyprototype/JustPeachy/install/current.json']
        if len(rows)!=1 or (rows[0]['identity']['bytes'],rows[0]['sha256'])!=SELECTOR_PIN:
            raise ValueError('Exact observed current selector required for external selected-release backup')
    for row in census['files']:
        validate_native_source(row['source'],is_file=True,member=row)
    for row in census['directories']:
        validate_native_source(row['source'],is_file=False)
    for row in census['external_assets']:
        if row['path'] in NATIVE_EXTRA_FILES:
            raise ValueError('Startup files require copied backup bytes, not external asset references')
        validate_native_source(row['path'],is_file=True)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out: raise ValueError('Duplicate backup field')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def write(path, raw):
    path = Path(path)
    with path.open('xb') as stream:
        if stream.write(raw) != len(raw): raise OSError('Short backup write')
        stream.flush(); os.fsync(stream.fileno())
    if path.read_bytes() != raw: raise OSError('Independent backup receipt readback differs')
    if os.name != 'nt':
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)


def relative(name):
    if not isinstance(name, str) or not name or len(name) > 512:
        raise ValueError('Bounded restoration path required')
    path = PurePosixPath(name)
    if (path.is_absolute() or path.as_posix() != name or '..' in path.parts
        or any(c in name for c in '\\:<>"|?*\x00') or
        any(part in ('', '.') or part.endswith(('.', ' ')) or
            part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}
            for part in path.parts)):
        raise ValueError('Unsafe restoration path')
    return path


def canonical(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path or path.is_symlink():
        raise ValueError('Canonical existing source required')
    return path


def identity(path):
    value = Path(path).lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise ValueError('Single-link regular backup member required')
    return dict(device=value.st_dev, inode=value.st_ino, bytes=value.st_size,
        mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns)


def digest(path):
    before = identity(canonical(path)); result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while raw := stream.read(CHUNK): result.update(raw)
    if identity(path) != before: raise ValueError('Source changed during independent read')
    return before, result.hexdigest()


def bounded_walk(root):
    """Refuse a huge directory before scandir can allocate its entire list."""
    pending=[Path(root)];directories=0
    while pending:
        directory=pending.pop();directories+=1
        if directories>MAX_FILES+1:raise ValueError('Bounded backup directory traversal required')
        children=[];files=[];count=0
        with os.scandir(directory) as entries:
            for entry in entries:
                count+=1
                if count>MAX_FILES:raise ValueError('Bounded backup directory membership required')
                if entry.is_symlink():raise ValueError('Backup directory/file symlink refused')
                if entry.is_dir(follow_symlinks=False):children.append(entry.name)
                else:files.append(entry.name)
        if len(pending)+len(children)>MAX_FILES:raise ValueError('Bounded backup traversal stack required')
        pending.extend(directory/name for name in reversed(sorted(children)))
        yield directory,children,files


def validate_spec(spec):
    if spec.get('schema') != 'just-peachy.production-backup-scope.v1' or spec.get('reviewed') is not True:
        raise ValueError('Explicit reviewed current release/user-data scope required')
    roots = spec['roots']; assets = spec.get('external_assets', [])
    if not isinstance(roots, list) or not 1 <= len(roots) <= 64 or not isinstance(assets, list) or len(assets) > 128:
        raise ValueError('Finite explicit backup roots/assets required')
    for key in ('maximum_payload_bytes', 'maximum_external_asset_bytes'):
        if type(spec[key]) is not int or not 0 <= spec[key] < 2**63:
            raise ValueError('Explicit finite byte reservation required')
    if not spec['maximum_payload_bytes']: raise ValueError('Nonempty backup reservation required')
    if type(spec['runtime_seconds']) is not int or not 180 <= spec['runtime_seconds'] <= 3600:
        raise ValueError('Explicit snapshot lifetime180..3600 seconds required')
    sources = []; aliases = []
    for row in roots:
        source = Path(row['source']); alias = relative(row['destination'])
        if not source.is_absolute() or str(source) != row['source'] or '..' in source.parts:
            raise ValueError('Exact absolute source root required')
        for previous in sources:
            if source == previous or source in previous.parents or previous in source.parents:
                raise ValueError('Overlapping source scopes refused')
        for previous in aliases:
            if alias == previous or alias in previous.parents or previous in alias.parents:
                raise ValueError('Overlapping restoration aliases refused')
        sources.append(source); aliases.append(alias)
    pins = set(); total = 0
    for row in assets:
        source = Path(row['path'])
        if (not source.is_absolute() or row.get('resolved_path') != str(source) or '..' in source.parts
            or str(source) in pins or type(row['bytes']) is not int or not 0 <= row['bytes'] < 2**63
            or not isinstance(row['sha256'], str) or len(row['sha256']) != 64
            or any(c not in '0123456789abcdef' for c in row['sha256'])):
            raise ValueError('Exact immutable external asset pin required')
        if not any(source == root or root in source.parents for root in sources):
            raise ValueError('Asset exclusion must be inside the reviewed scope')
        pins.add(str(source)); total += row['bytes']
    if total > spec['maximum_external_asset_bytes']:
        raise ValueError('External asset hashing reservation exceeded')
    return spec


def validate_absent_reserved_slots(spec, native_home='/home/peachyprototype'):
    """Recheck absent future slots under the actual snapshot leases, twice."""
    proofs=spec.get('absent_reserved_slots',[])
    if not isinstance(proofs,list) or len(proofs)>64:raise ValueError('Bounded explicit absent-slot proof required')
    campaign=Path(native_home)/'JustPeachy/research/nemotron-20260928';seen=set()
    for proof in proofs:
        root=Path(proof['release']);source=Path(proof['source']);slot=proof['slot']
        if (root not in (campaign/'field-runtime-v27',campaign/'field-runtime-v28') or
            source.parent!=campaign or str(source) in seen or
            proof.get('eligible') is not True or proof.get('state') not in ('UNUSED_NEVER_STARTED','RESERVED_NEVER_STARTED')):
            raise ValueError('Exact retained absent-slot association required')
        seen.add(str(source));policy_path=root/'control/RELEASE.json'
        if identity(canonical(policy_path))['bytes']>65536:raise ValueError('Bounded absent-slot policy required')
        info,sha=digest(policy_path)
        if sha!=proof['policy_sha256'] or str(policy_path)!=proof['policy_path']:
            raise ValueError('Actual absent-slot policy changed')
        policy=strict(policy_path.read_bytes());slots=policy['allocation']['recording_slots']
        if (policy['manager_root']!=str(root) or slot not in slots or len(slots)!=len(policy['recording_roots']) or
            policy['recording_roots'][slots.index(slot)]!=str(source)):
            raise ValueError('Actual retained slot/root mapping changed')
        directory=root/'recordings'/slot;backup=root/'backups'/slot
        if (source.exists() or source.is_symlink() or backup.exists() or backup.is_symlink() or
            canonical(directory)!=directory or str(directory)!=proof['slot_directory']):
            raise ValueError('Formerly absent recording now exists or has backup evidence')
        names=[]
        with os.scandir(directory) as entries:
            for entry in entries:
                if len(names)>=16:raise ValueError('Absent-slot journal membership bound')
                names.append(entry.name)
        if proof['state']=='UNUSED_NEVER_STARTED':
            if names or proof.get('slot_membership')!=[]:raise ValueError('Unused slot now has start/owner/data evidence')
        else:
            if names!=['RESERVED.json']:raise ValueError('Reservation-only slot gained start/owner/data evidence')
            reservation_path=directory/'RESERVED.json'
            if identity(canonical(reservation_path))['bytes']>16384:raise ValueError('Bounded absent-slot reservation required')
            info,sha=digest(reservation_path)
            receipt=proof['reservation']
            if info['bytes']>16384 or (info['bytes'],sha)!=(receipt['bytes'],receipt['sha256']):
                raise ValueError('Exact reservation receipt changed')
            value=strict(reservation_path.read_bytes());operation=value.get('operation',{})
            if (value.get('policy_sha256')!=proof['policy_sha256'] or value.get('slot')!='recordings/'+slot or
                operation.get('root')!=str(source) or operation.get('slot')!=slot or
                operation.get('policy_sha256')!=proof['policy_sha256'] or
                operation.get('schema')!='just-peachy.offline-runtime-operation.v1'):
                raise ValueError('Actual reservation-only slot binding changed')


def census(spec):
    """Hash only named scopes; all excluded bytes require exact external pins."""
    validate_spec(spec)
    validate_absent_reserved_slots(spec)
    rows = []; directories = []; external = []; total = 0
    assets = {row['path']: row for row in spec.get('external_assets', [])}
    seen_assets = set(); names = set(); directory_names=set(); walked = 0
    def member(path, name):
        nonlocal total
        relative(name); path = canonical(path)
        before=identity(path)
        if str(path) in assets:
            if before['bytes']!=assets[str(path)]['bytes']:
                raise ValueError('Excluded immutable asset differs from exact pin')
        elif (name.casefold() in names or name.casefold() in directory_names or len(rows)>=MAX_FILES):
            raise ValueError('Duplicate or excessive full-backup membership')
        elif total+before['bytes']>spec['maximum_payload_bytes']:
            raise ValueError('Full backup exceeds independent PC reservation')
        checked,sha=digest(path)
        if checked!=before:raise ValueError('Snapshot identity changed before hashing')
        if str(path) in assets:
            pin = assets[str(path)]
            if before['bytes'] != pin['bytes'] or sha != pin['sha256']:
                raise ValueError('Excluded immutable asset differs from exact pin')
            seen_assets.add(str(path)); external.append(dict(pin, identity=before)); return
        if name.casefold() in names or name.casefold() in directory_names or len(rows) >= MAX_FILES:
            raise ValueError('Duplicate or excessive full-backup membership')
        names.add(name.casefold()); total += before['bytes']
        if total > spec['maximum_payload_bytes']: raise ValueError('Full backup exceeds independent PC reservation')
        rows.append(dict(path=name, source=str(path), identity=before, sha256=sha,
            mode=stat.S_IMODE(path.stat().st_mode)))
    for root in spec['roots']:
        source = canonical(root['source']); alias = root['destination']
        if source.is_file(): member(source, alias); continue
        if not source.is_dir(): raise ValueError('Backup source must be file or directory')
        for directory, children, files in bounded_walk(source):
            walked += 1
            if walked > MAX_FILES or len(children) + len(files) > MAX_FILES:
                raise ValueError('Bounded backup directory membership required')
            directory = canonical(directory)
            name = (PurePosixPath(alias) / directory.relative_to(source).as_posix()).as_posix()
            relative(name); value = directory.stat()
            if name.casefold() in names or name.casefold() in directory_names:
                raise ValueError('Restoration directory collision on PC')
            directory_names.add(name.casefold())
            directories.append(dict(path=name, source=str(directory), mode=stat.S_IMODE(value.st_mode),
                device=value.st_dev, inode=value.st_ino, mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns))
            for child in children:
                if not stat.S_ISDIR((directory/child).lstat().st_mode):
                    raise ValueError('Backup directory symlink/special member refused')
            for child in files:
                path = directory/child
                member(path, (PurePosixPath(alias)/path.relative_to(source).as_posix()).as_posix())
    if seen_assets != set(assets) or not rows:
        raise ValueError('All declared assets and at least one payload member must exist')
    validate_absent_reserved_slots(spec)
    result = dict(schema='just-peachy.production-backup-census.v1', scope=spec,
        files=sorted(rows, key=lambda row: row['path']), directories=sorted(directories, key=lambda row: row['path']),
        external_assets=sorted(external, key=lambda row: row['path']), bytes=total)
    if len(encoded(result)) > MAX_CENSUS: raise ValueError('Full restoration census exceeds2MiB')
    return result


def seed_plan(rows, mappings):
    """Only explicit destination-prefix mappings; old manifests are not trusted."""
    if len(mappings) > 64: raise ValueError('Bounded explicit seed mappings required')
    plan = []
    for row in rows:
        name = relative(row['path']); found = None
        for mapping in mappings:
            prefix = relative(mapping['destination']); root = canonical(mapping['local'])
            if name != prefix and prefix not in name.parents: continue
            candidate = root if name == prefix else root.joinpath(*name.relative_to(prefix).parts)
            if not candidate.exists(): continue
            if identity(canonical(candidate))['bytes']!=row['identity']['bytes']:continue
            actual, sha = digest(candidate)
            if actual['bytes'] == row['identity']['bytes'] and sha == row['sha256']:
                found = str(candidate); break
        plan.append(dict(path=row['path'], bytes=row['identity']['bytes'], sha256=row['sha256'],
                         seed=found, action='reuse' if found else 'fetch'))
    return plan


def copy_seed(source, destination, row):
    source = canonical(source); before = identity(source)
    if before['bytes'] != row['identity']['bytes']: raise ValueError('Seed extent changed')
    destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.parent.resolve(strict=True) != destination.parent: raise ValueError('Backup destination changed')
    with source.open('rb') as src, destination.open('xb') as dst:
        result = hashlib.sha256(); count = 0
        while raw := src.read(CHUNK):
            count += len(raw)
            if count > before['bytes']: raise ValueError('Seed grew during copy')
            if dst.write(raw) != len(raw): raise OSError('Short seed copy')
            result.update(raw)
        dst.flush(); os.fsync(dst.fileno())
    if identity(source) != before or count != before['bytes'] or result.hexdigest() != row['sha256']:
        raise ValueError('Seed changed during copy')
    verify_payload(destination.parent, [dict(row, path=destination.name)], exact_membership=False)


def verify_payload(root, rows, *, exact_membership=True):
    root = canonical(root); expected = set(); total = 0
    for row in rows:
        name = relative(row['path']); expected.add(name.as_posix())
        path=canonical(root.joinpath(*name.parts))
        if identity(path)['bytes']!=row['identity']['bytes']:
            raise ValueError('Independent full PC payload extent differs')
        actual, sha = digest(path)
        if actual['bytes'] != row['identity']['bytes'] or sha != row['sha256']:
            raise ValueError('Independent full PC payload readback differs')
        total += actual['bytes']
    if exact_membership:
        found = set(); count = 0
        for directory, children, files in bounded_walk(root):
            count += 1
            if count > MAX_FILES or len(children) + len(files) > MAX_FILES:
                raise ValueError('PC backup membership bound')
            for name in children:
                if (Path(directory)/name).is_symlink(): raise ValueError('PC backup directory symlink')
            for name in files:
                path = Path(directory)/name; canonical(path); identity(path)
                found.add(path.relative_to(root).as_posix())
        if found != expected: raise ValueError('PC full backup has missing or unlisted files')
    return dict(files=len(rows), bytes=total,
        manifest_sha256=hashlib.sha256(encoded(rows)).hexdigest(), independent_readback=True)
