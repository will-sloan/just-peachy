"""Retained dependency pins and guarded candidate pointers. README_FIELD_DEPENDENCIES_V2.md."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

MIB = 1024**2
OUTPUT_LIMIT = None


def configure_output(root, byte_limit):
    global OUTPUT_LIMIT
    if OUTPUT_LIMIT is not None: raise RuntimeError('Output policy already bound')
    if byte_limit < 2*MIB: raise ValueError('Output reserve unavailable')
    OUTPUT_LIMIT = (Path(root).resolve(), byte_limit-MIB)



def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    path = Path(path)
    if path.stat().st_size > 8*MIB:
        raise ValueError('Oversized dependency document')
    return json.loads(path.read_text())


def exclusive(path, value, *, total_budget_bytes=None):
    raw = json.dumps(value, indent=2, allow_nan=False).encode()
    if len(raw) > 8*MIB:
        raise ValueError('Dependency document byte bound')
    if OUTPUT_LIMIT is None: raise RuntimeError('Output policy not configured')
    root, bound = OUTPUT_LIMIT
    if root not in Path(path).resolve().parents: raise ValueError('Output outside bound root')
    if total_budget_bytes is not None:
        if type(total_budget_bytes) is not int or not 0 <= total_budget_bytes <= bound: raise ValueError('Only a lower test bound is permitted')
        bound = min(bound,total_budget_bytes)
    used = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if used+len(raw) > bound: raise ValueError('Output quota rejected before write')
    with Path(path).open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())


def fingerprint(path, category):
    path = Path(path)
    if not path.is_absolute(): raise ValueError('Dependency path must be absolute')
    resolved = path.resolve(strict=True)
    row = dict(path=str(path), resolved=str(resolved), category=category,
               link=os.readlink(path) if path.is_symlink() else None)
    if resolved.is_dir() and path.is_symlink():
        return dict(row, kind='directory_link', bytes=0, sha256=None)
    if not resolved.is_file(): raise ValueError('Dependency is not a regular file')
    st = resolved.stat()
    return dict(row, kind='file', bytes=st.st_size, device=st.st_dev, inode=st.st_ino, sha256=sha(resolved))


def inventory(root):
    root = Path(root)
    return sorted(str(p) for p in root.rglob('*') if p.is_file() or p.is_symlink())


def elf(path):
    with Path(path).open('rb') as f: return f.read(4) == b'\x7fELF'


def collect(release, output):
    """Read existing code/assets/runtime, plus bounded DT_NEEDED resolution; copy no binaries."""
    import sysconfig
    start = time.monotonic(); release = Path(release); output = Path(output)
    contract = read(release/'config/field_contract.json'); rows = {}; trees = {}
    def add(path, category):
        path = str(Path(path))
        if path not in rows: rows[path] = fingerprint(path, category)
        if len(rows) > 16000 or time.monotonic()-start > 150:
            raise RuntimeError('Dependency collection count/time bound')
    assets = read(release/'config/assets.json')
    if isinstance(assets, dict): assets = assets['assets']
    for item in assets:
        path = Path(contract['models_root'])/item['sha256']/(item.get('filename') or Path(item['deployment_relative_path']).name)
        add(path, 'shared_model')
        if rows[str(path)]['sha256'] != item['sha256']: raise ValueError('Original model binding mismatch')
    for item in contract['extra_assets']:
        add(item['path'], 'retained_native')
        if rows[item['path']]['sha256'] != item['sha256'] or rows[item['path']]['resolved'] != item['resolved']:
            raise ValueError('Original retained dependency binding mismatch')
    for name, root in [('runtime', contract['runtime_prefix']), ('stdlib', sysconfig.get_path('stdlib'))]:
        paths = inventory(root); trees[root] = paths
        if len(paths) > 12000: raise RuntimeError('Runtime tree count bound')
        for path in paths: add(path, name)
    # Explicit dynamic roots used by PortAudio/Tk even when no stream/window opens.
    catalog = subprocess.run(['/sbin/ldconfig','-p'], capture_output=True, text=True, check=True, timeout=10).stdout
    for soname in ['libportaudio.so.2','libtk8.6.so','libtcl8.6.so']:
        matches = [line.split('=>',1)[1].strip() for line in catalog.splitlines() if line.strip().startswith(soname+' ') and '=>' in line]
        if len(matches) != 1: raise ValueError('Ambiguous/missing dynamic root '+soname)
        add(matches[0], 'dynamic_root')
    roots = sorted({r['resolved'] for r in rows.values() if r['kind']=='file' and elf(r['resolved'])})
    if len(roots) > 256: raise RuntimeError('ELF root bound')
    traces = []
    for path in roots:
        if time.monotonic()-start > 150: raise RuntimeError('ELF collection wall bound')
        done = subprocess.run(['/usr/bin/ldd', path], capture_output=True, text=True, timeout=10)
        text = done.stdout + done.stderr
        if len(text.encode()) > 128*1024 or 'not found' in text: raise ValueError('Unresolved ELF dependency: '+path)
        if done.returncode and not any(s in text for s in ['not a dynamic executable','statically linked']):
            raise ValueError('ELF resolver failed: '+path)
        found = []
        for line in text.splitlines():
            match = re.search(r'(?:=>\s*)?(/[^\s]+)\s+\(0x[0-9a-f]+\)', line)
            if match:
                target = match.group(1); add(target, 'system_elf'); found.append(target)
        traces.append(dict(root=path, returncode=done.returncode, text=text, resolved=found))
    unique = {}
    for row in rows.values():
        if row['kind']=='file': unique[(row['device'],row['inode'])] = row['bytes']
    value = dict(schema='just-peachy.retained-dependencies.v1', release_contract_sha256=sha(release/'config/field_contract.json'),
                 roots=trees, entries=sorted(rows.values(), key=lambda r:r['path']), elf=traces,
                 unique_logical_bytes=sum(unique.values()), unique_files=len(unique),
                 placement='retained exact paths; not relocated or self-contained',
                 dynamic_scope='DT_NEEDED resolution of pinned ELF roots plus explicit PortAudio/Tk/Tcl; not every future dlopen/plugin/resource')
    exclusive(output, value)
    return value


def verify(lock_path, expected_sha):
    if sha(lock_path) != expected_sha: raise ValueError('Dependency lock hash mismatch')
    lock = read(lock_path)
    if lock.get('schema') != 'just-peachy.retained-dependencies.v1': raise ValueError('Dependency lock schema')
    if len(lock['entries']) > 16000: raise ValueError('Dependency row bound')
    for root, expected in lock['roots'].items():
        if inventory(root) != expected: raise ValueError('Runtime membership changed: '+root)
    seen = set()
    for row in lock['entries']:
        if row['path'] in seen: raise ValueError('Duplicate dependency path')
        seen.add(row['path'])
        if fingerprint(row['path'], row['category']) != row: raise ValueError('Dependency changed: '+row['path'])
    return dict(status='RETAINED_DEPENDENCIES_EXACT', entries=len(seen), unique_files=lock['unique_files'], unique_logical_bytes=lock['unique_logical_bytes'])


def check_descriptor(descriptor_path, expected_sha, release_tools):
    path = Path(descriptor_path)
    if sha(path) != expected_sha: raise ValueError('Deployment descriptor hash mismatch')
    d = read(path)
    if d.get('schema') != 'just-peachy.retained-deployment.v1': raise ValueError('Deployment descriptor schema')
    release = Path(d['release'])
    if str(release.resolve()) != d['resolved_release'] or sha(release/'RELEASE_MANIFEST.json') != d['manifest_sha256']:
        raise ValueError('Deployment release identity changed')
    manifest = release_tools.verify_release(release)
    if manifest['version'] != d['version']: raise ValueError('Deployment version mismatch')
    if sha(release/'config/field_contract.json') != d['contract_sha256']: raise ValueError('Deployment contract changed')
    pin = verify(d['dependencies'], d['dependencies_sha256'])
    if read(d['dependencies'])['release_contract_sha256'] != d['contract_sha256']: raise ValueError('Dependency contract mismatch')
    return d, manifest, pin


def activate(root, data, descriptor_path, expected_sha, expected_current_sha, release_tools):
    """Candidate pointer only: caller supplies exact expected prior state; never starts an app."""
    root = Path(root).resolve(); data = Path(data).resolve(); root.mkdir(parents=True, exist_ok=True)
    with release_tools.update_boundary(data):
        current = root/'current.json'
        actual = sha(current) if current.exists() else None
        if actual != expected_current_sha: raise ValueError('Candidate current pointer changed')
        d, manifest, checked = check_descriptor(descriptor_path, expected_sha, release_tools)
        if d.get('candidate_root') != str(root) or d.get('data_root') != str(data):
            raise ValueError('Candidate activation root/data binding')
        if shutil.disk_usage(root).free < 5*1024**3 + 32*MIB: raise ValueError('Fixed-device free reserve')
        release_tools.check_data_schema(data, manifest, initialize=False)
        old = read(current) if current.exists() else None
        pointer = dict(schema='just-peachy.retained-candidate-pointer.v1', version=d['version'],
                       descriptor=str(Path(descriptor_path).resolve()), descriptor_sha256=expected_sha,
                       release=d['release'], manifest_sha256=d['manifest_sha256'], inference_started=False)
        if old: release_tools.write_json(root/'previous.json', old)
        release_tools.write_json(current, pointer)
        history=root/'history'; history.mkdir(exist_ok=True)
        exclusive(history/(uuid.uuid4().hex+'.json'), dict(previous=old, current=pointer, dependency_check=checked))
        return pointer


def rollback(root, data, expected_current_sha, expected_previous_sha, release_tools):
    # Previous descriptor is verified again by activate, including every dependency.
    raw = (Path(root)/'previous.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_previous_sha: raise ValueError('Previous pointer hash mismatch')
    previous = json.loads(raw)
    return activate(root, data, previous['descriptor'], previous['descriptor_sha256'], expected_current_sha, release_tools)
