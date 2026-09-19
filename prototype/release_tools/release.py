"""Integrity-checked, immutable application releases; read README before use.

Checksums detect damage, not publisher impersonation. Never execute an archive
from an untrusted publisher. Personal data and models are separate from releases.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import importlib
import json
import os
import platform
import re
import shutil
import stat
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SCHEMA = 'just-peachy.release.v1'
VERSION = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z')
ALLOWED_DIRS = {'app', 'vendor', 'config', 'docs', 'release_tools', 'licenses'}
ALLOWED_SUFFIXES = {'.py', '.json', '.md', '.txt', '.ps1', '.cmd', '.sh', '.lock', '.in', '.yaml', '.yml', '.rst', '.csv', '.patch'}
ROOT_FILES = {'main.py', 'Start-Prototype.ps1', 'Start-Prototype.cmd', 'README.md', 'START_PROTOTYPE.md', 'MODE_GUIDE.md', 'LICENSE', 'LICENSE.txt'}
MAX_FILES = 5000
MAX_RELEASE_BYTES = 256 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def relative(name):
    p = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or '\x00' in name or p.is_absolute() or any(x in ('', '.', '..') for x in name.split('/')):
        raise ValueError(f'Unsafe archive path: {name!r}')
    # Keep Windows extraction portable and avoid alternate streams/devices.
    for part in p.parts:
        if part.endswith(('.', ' ')) or part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
            raise ValueError(f'Non-portable archive path: {name!r}')
    return p


def validate_version(version):
    if not VERSION.fullmatch(version) or version in ('.', '..'):
        raise ValueError('Version must be 1-80 safe letters, digits, dots, underscores or hyphens')
    return version


def build(source, output, version):
    source, output = Path(source).resolve(), Path(output).resolve()
    validate_version(version)
    if not (source / 'main.py').is_file() or not (source / 'config' / 'assets.json').is_file():
        raise ValueError('Build source needs main.py and config/assets.json')
    output.mkdir(parents=True, exist_ok=True)
    target = output / f'just-peachy-{version}.zip'
    if target.exists():
        raise FileExistsError(f'Refusing to overwrite a versioned archive: {target}')
    files = []
    for path in sorted(source.rglob('*')):
        rel = path.relative_to(source)
        if not path.is_file() or path.is_symlink() or '__pycache__' in rel.parts:
            continue
        if rel.parts[0] not in ALLOWED_DIRS and rel.as_posix() not in ROOT_FILES:
            continue
        if path.suffix.lower() not in ALLOWED_SUFFIXES and path.name != 'LICENSE':
            continue
        if any(x in {'tests', 'evidence', 'private', 'people', 'sessions', 'models', 'fixtures', '.venv', 'output'} for x in rel.parts):
            continue
        relative(rel.as_posix())
        files.append(dict(path=rel.as_posix(), bytes=path.stat().st_size, sha256=digest(path)))
    if len(files) > MAX_FILES or sum(f['bytes'] for f in files) > MAX_RELEASE_BYTES:
        raise ValueError('Source archive exceeds the bounded release size')
    manifest = dict(schema=SCHEMA, version=version, created_utc=now(), files=files,
        data_schema_min=1, data_schema_max=1, migrations=[], entrypoint='main.py',
        asset_manifest='config/assets.json', assets_included=False,
        runtime_target=dict(os='Raspberry Pi OS 64-bit Bookworm', arch='aarch64', python='3.11', glibc_min='2.36'),
        evidence=dict(WINDOWS_TESTED='Separate test receipt required',
            LINUX_STATIC_BUILD_CHECKED='See release_tools/evidence outside payload',
            ARM64_ARTIFACT_PREPARED='13 pinned wheels; see requirements-arm64.lock', CM5_HARDWARE_NOT_TESTED=True),
        privacy='No people, sessions, voice vectors, recordings, model weights or research fixtures included.',
        authentication='Unsigned: checksums provide integrity only; trust the source separately.')
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for item in files:
            # Recheck to reject a concurrent source edit during the build.
            path = source / item['path']
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != item['sha256']:
                raise RuntimeError(f'Source changed during build: {item["path"]}')
            z.writestr(item['path'], data)
        z.writestr('RELEASE_MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    receipt = dict(status='BUILT', archive=str(target), sha256=digest(target), bytes=target.stat().st_size, file_count=len(files), version=version)
    write_json(target.with_suffix('.receipt.json'), receipt)
    return receipt


def inspect_archive(archive):
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        if len(infos) > MAX_FILES + 1 or sum(i.file_size for i in infos) > MAX_RELEASE_BYTES:
            raise ValueError('Archive exceeds bounded release limits')
        names = []
        for info in infos:
            relative(info.filename)
            if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Archive contains a directory/symlink member')
            names.append(info.filename)
        if len({n.casefold() for n in names}) != len(names):
            raise ValueError('Duplicate or case-colliding archive member')
        if 'RELEASE_MANIFEST.json' not in names or z.getinfo('RELEASE_MANIFEST.json').file_size > 4 * 1024 * 1024:
            raise ValueError('Missing or oversized manifest')
        manifest = json.loads(z.read('RELEASE_MANIFEST.json'))
        if manifest.get('schema') != SCHEMA:
            raise ValueError('Unsupported release schema')
        validate_version(manifest['version'])
        entries = manifest['files']
        listed = [e['path'] for e in entries]
        if len(set(listed)) != len(listed) or set(listed) != set(names) - {'RELEASE_MANIFEST.json'}:
            raise ValueError('Manifest inventory differs from archive')
        for row in entries:
            relative(row['path'])
            if z.getinfo(row['path']).file_size != row['bytes'] or hashlib.sha256(z.read(row['path'])).hexdigest() != row['sha256']:
                raise ValueError(f'Integrity failure: {row["path"]}')
        if manifest.get('migrations'):
            raise ValueError('Automatic data migrations are not supported by PROTO1')
        return manifest


def verify_release(path):
    path = Path(path).resolve()
    manifest = read_json(path / 'RELEASE_MANIFEST.json')
    if manifest.get('schema') != SCHEMA:
        raise ValueError('Unsupported installed manifest')
    validate_version(manifest['version'])
    for item in manifest['files']:
        p = path / str(relative(item['path']))
        if path not in p.resolve().parents or any(parent.is_symlink() for parent in [p, *p.parents] if parent != path and path in parent.parents) or not p.is_file() or p.stat().st_size != item['bytes'] or digest(p) != item['sha256']:
            raise ValueError(f'Installed integrity failure: {item["path"]}')
    return manifest


def stage(archive, install_root, expected_sha256=None):
    archive, root = Path(archive).resolve(), Path(install_root).resolve()
    actual = digest(archive)
    if expected_sha256 and actual.lower() != expected_sha256.lower():
        raise ValueError('Archive checksum does not match expected SHA256')
    manifest = inspect_archive(archive)
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < sum(f['bytes'] for f in manifest['files']) * 2 + 256 * 1024 * 1024:
        raise ValueError('Insufficient staging space: preserve 256 MiB reserve plus twice unpacked source size')
    final = root / 'releases' / manifest['version']
    if final.exists():
        existing = verify_release(final)
        if existing != manifest:
            raise ValueError('Release version already exists with different content')
        return dict(status='ALREADY_STAGED', version=manifest['version'], path=str(final))
    (root / 'staging').mkdir(exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='release-', dir=root / 'staging'))
    try:
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                target = temp / str(relative(info.filename))
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, target.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
        if verify_release(temp) != manifest:
            raise ValueError('Archive changed between validation and staging')
        final.parent.mkdir(parents=True, exist_ok=True)
        os.rename(temp, final)
    except Exception:
        # Only the private mkdtemp created in this call is cleaned up.
        if temp.exists() and temp.parent == root / 'staging':
            shutil.rmtree(temp)
        raise
    return dict(status='STAGED', version=manifest['version'], path=str(final), archive_sha256=actual)


@contextlib.contextmanager
def update_boundary(data_root):
    data = Path(data_root).resolve()
    data.mkdir(parents=True, exist_ok=True)
    lock = data / 'runtime.lock'
    token = uuid.uuid4().hex
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError(f'Application or another updater owns {lock}. Stop the app safely; never auto-delete an owner lock.') from None
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(dict(token=token, pid=os.getpid(), purpose='release_update', created_utc=now()), f)
        yield
    finally:
        if lock.exists() and read_json(lock).get('token') == token:
            lock.unlink()


def check_data_schema(data_root, manifest, initialize=False):
    path = Path(data_root) / 'DATA_SCHEMA.json'
    if not path.exists():
        known = ['people', 'settings', 'sessions', 'saved_excerpts', 'photos']
        if any((Path(data_root) / name).exists() for name in known):
            raise ValueError('Existing personal data lacks DATA_SCHEMA.json; inspect before activation')
        schema = 1
        if initialize:
            write_json(path, dict(schema_version=schema, created_utc=now()))
    else:
        schema = read_json(path)['schema_version']
    if not manifest['data_schema_min'] <= schema <= manifest['data_schema_max']:
        raise ValueError(f'Incompatible personal-data schema {schema}; no automatic migration performed')
    return schema


def activate(install_root, data_root, version, require_assets=False):
    root, data = Path(install_root).resolve(), Path(data_root).resolve()
    validate_version(version)
    if (root / 'releases') == data or (root / 'releases') in data.parents:
        raise ValueError('Personal data must live outside replaceable releases')
    with update_boundary(data):
        manifest = verify_release(root / 'releases' / version)
        check_data_schema(data, manifest, initialize=True)
        if require_assets:
            verify_assets(root / 'releases' / version, root / 'models')
        target = dict(schema='just-peachy.current.v1', version=version, relative_path=f'releases/{version}', activated_utc=now())
        old = read_json(root / 'current.json') if (root / 'current.json').exists() else None
        if old and old['version'] == version:
            return dict(status='ALREADY_ACTIVE', version=version)
        if old:
            write_json(root / 'previous.json', old)
        write_json(root / 'current.json', target)
        (root / 'history').mkdir(exist_ok=True)
        write_json(root / 'history' / (uuid.uuid4().hex + '.json'), dict(previous=old, current=target, data_unchanged=True))
    return dict(status='ACTIVE', version=version, data_root=str(data), inference_started=False)


def rollback(install_root, data_root):
    root = Path(install_root)
    prior = read_json(root / 'previous.json')
    result = activate(root, data_root, prior['version'])
    result['status'] = 'ROLLED_BACK'
    return result


def assets_list(release):
    doc = read_json(Path(release) / 'config' / 'assets.json')
    return doc if isinstance(doc, list) else doc['assets']


def verify_assets(release, models):
    result = []
    for row in assets_list(release):
        sha = row['sha256']
        filename = row.get('filename') or Path(row['deployment_relative_path']).name
        if not re.fullmatch(r'[a-f0-9]{64}', sha) or str(relative(filename)) != filename or '/' in filename:
            raise ValueError('Unsafe asset identity')
        path = Path(models) / sha / filename
        if not path.is_file() or path.is_symlink() or digest(path) != sha:
            raise ValueError(f'Missing/damaged shared asset: {row.get("component_id", filename)} at {path}')
        result.append(dict(component_id=row.get('component_id'), sha256=sha, bytes=path.stat().st_size))
    return result


def import_models(release, source_models, target_models):
    rows = verify_assets(release, source_models)
    for asset in assets_list(release):
        filename = asset.get('filename') or Path(asset['deployment_relative_path']).name
        src = Path(source_models) / asset['sha256'] / filename
        dst = Path(target_models) / asset['sha256'] / filename
        if dst.exists():
            if digest(dst) != asset['sha256']:
                raise ValueError(f'Existing shared model damaged; not overwriting: {dst}')
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        temp = dst.with_name(dst.name + '.' + uuid.uuid4().hex + '.tmp')
        shutil.copyfile(src, temp)
        if digest(temp) != asset['sha256']:
            temp.unlink()
            raise ValueError(f'Asset changed during transfer: {src}')
        os.replace(temp, dst)
    return dict(status='MODELS_IMPORTED', assets=len(rows), target=str(target_models))


def healthcheck(install_root, data_root, version=None, check_models=False, check_imports=False):
    root = Path(install_root).resolve()
    if version is None:
        version = read_json(root / 'current.json')['version']
    validate_version(version)
    release = root / 'releases' / version
    manifest = verify_release(release)
    schema = check_data_schema(data_root, manifest)
    result = dict(status='PASS', version=version, release=str(release), files_verified=len(manifest['files']),
        data_schema=schema, runtime_owner_present=(Path(data_root) / 'runtime.lock').exists(),
        platform=platform.platform(), machine=platform.machine(), python=platform.python_version(),
        free_bytes=shutil.disk_usage(root).free, models='NOT_CHECKED', imports='NOT_CHECKED',
        cm5='CM5_HARDWARE_NOT_TESTED', inference='NOT_RUN', microphone='NOT_OPENED')
    if check_models:
        result['models'] = verify_assets(release, root / 'models')
    if check_imports:
        result['imports'] = {}
        for name in ['numpy', 'scipy', 'onnxruntime', 'sherpa_onnx', 'sounddevice', 'soundfile', 'tkinter', 'psutil']:
            module = importlib.import_module(name)
            result['imports'][name] = getattr(module, '__version__', 'stdlib/unknown')
    return result


def diagnostics(root, data, output):
    # Deliberately excludes settings, names, recordings, vectors, transcripts and environment variables.
    result = dict(schema='just-peachy.diagnostics.v1', collected_utc=now(), platform=platform.platform(),
        machine=platform.machine(), python=platform.python_version(), disk_free_bytes=shutil.disk_usage(root).free,
        current=read_json(Path(root) / 'current.json') if (Path(root) / 'current.json').exists() else None,
        runtime_owner_present=(Path(data) / 'runtime.lock').exists(), private_data_included=False)
    write_json(output, result)
    return dict(status='COLLECTED', output=str(output), private_data_included=False)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build'); b.add_argument('--source', type=Path, required=True); b.add_argument('--output', type=Path, required=True); b.add_argument('--version', required=True)
    s = sub.add_parser('stage'); s.add_argument('--archive', type=Path, required=True); s.add_argument('--root', type=Path, required=True); s.add_argument('--sha256')
    u = sub.add_parser('usb-import'); u.add_argument('--archive', type=Path, required=True); u.add_argument('--root', type=Path, required=True); u.add_argument('--sha256', required=True)
    for cmd in ['activate', 'rollback', 'healthcheck', 'collect-diagnostics']:
        q = sub.add_parser(cmd); q.add_argument('--root', type=Path, required=True); q.add_argument('--data-root', type=Path, required=True)
        if cmd == 'activate':
            q.add_argument('--version', required=True); q.add_argument('--require-assets', action='store_true')
        if cmd == 'healthcheck':
            q.add_argument('--version'); q.add_argument('--models', action='store_true'); q.add_argument('--imports', action='store_true')
        if cmd == 'collect-diagnostics': q.add_argument('--output', type=Path, required=True)
    m = sub.add_parser('import-models'); m.add_argument('--release', type=Path, required=True); m.add_argument('--source-models', type=Path, required=True); m.add_argument('--target-models', type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.command == 'build': result = build(a.source, a.output, a.version)
        elif a.command in ('stage', 'usb-import'): result = stage(a.archive, a.root, a.sha256)
        elif a.command == 'activate': result = activate(a.root, a.data_root, a.version, a.require_assets)
        elif a.command == 'rollback': result = rollback(a.root, a.data_root)
        elif a.command == 'healthcheck': result = healthcheck(a.root, a.data_root, a.version, a.models, a.imports)
        elif a.command == 'collect-diagnostics': result = diagnostics(a.root, a.data_root, a.output)
        elif a.command == 'import-models': result = import_models(a.release, a.source_models, a.target_models)
        print(json.dumps(result, indent=2)); return 0
    except Exception as exc:
        print(json.dumps(dict(status='FAIL', error_type=type(exc).__name__, error=str(exc))), file=sys.stderr); return 1


if __name__ == '__main__':
    raise SystemExit(main())
