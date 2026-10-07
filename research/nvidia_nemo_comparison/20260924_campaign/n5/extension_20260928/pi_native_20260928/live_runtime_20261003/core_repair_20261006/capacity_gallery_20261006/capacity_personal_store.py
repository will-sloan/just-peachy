"""Capacity-governed personal records/archives; README_GALLERY_CAPACITY_STORE.md.

Keep the installed validators/math and individual record bounds. Stream archive
payloads; person/reference counts are not admission quotas. No model is loaded.
"""
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import uuid
import zipfile

from runtime_support import DiskBudget, digest, encoded, resource_snapshot, strict

PEOPLE_SHA = '9005a8c987961100c45fdb63ddb23d2969a4e690b8f5e78141ed6571b5714ea5'
RAM_FLOOR = 192*1024**2
CACHE_BYTES = 8*1024**2  # Cache working set only; a larger roster remains iterable.
LIMITS = {'person.json': 128*1024, '.npy': 4096, '.script.json': 256*1024}


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _ordinary(path, maximum):
    before = path.lstat()
    if (path.is_symlink() or getattr(before, 'st_file_attributes', 0)&0x400
            or any(parent.is_symlink() or getattr(parent.lstat(), 'st_file_attributes', 0)&0x400
                   for parent in path.parents)
            or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum):
        raise ValueError('Bounded single-link regular personal payload required')
    return before


def _member(name):
    parts = name.split('/')
    if (len(parts) != 2 or str(uuid.UUID(parts[0])) != parts[0]
            or Path(parts[1]).name != parts[1] or ':' in name or '\\' in name):
        raise ValueError('Canonical personal archive member required')
    suffix = next((suffix for suffix in ('.script.json', '.npy') if parts[1].endswith(suffix)), None)
    if parts[1] == 'person.json':
        return parts, LIMITS['person.json']
    if suffix is None or str(uuid.UUID(parts[1][:-len(suffix)])) != parts[1][:-len(suffix)]:
        raise ValueError('Canonical reference UUID filename required')
    return parts, LIMITS[suffix]


def _derive(people):
    """Remove exactly three count gates from the actual hash-pinned methods."""
    source = Path(people.__file__)
    before = _ordinary(source, 65536)
    raw = source.read_bytes()
    if _identity(before) != _identity(source.stat()) or hashlib.sha256(raw).hexdigest() != PEOPLE_SHA:
        raise ValueError('Exact installed PersonalStore source changed')
    tree = ast.parse(raw)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'PersonalStore']
    if len(classes) != 1:
        raise ValueError('Exact installed PersonalStore definition required')
    methods = {node.name: node for node in classes[0].body if isinstance(node, ast.FunctionDef)}
    validator, saver = methods['_validate'], methods['_save']
    expected = {
        'not isinstance(references, list) or not 1 <= len(references) <= 20':
            'not isinstance(references, list) or not references',
        'len(self.list()) >= 256': None,
        "len(row['references']) >= 20": None,
    }
    found = {key: 0 for key in expected}
    class Counts(ast.NodeTransformer):
        def visit_If(self, node):
            key = ast.unparse(node.test)
            if key in expected:
                found[key] += 1
                replacement = expected[key]
                if replacement is None:
                    if node.orelse:
                        raise ValueError('Unexpected installed count-gate alternative')
                    return None
                node.test = ast.parse(replacement, mode='eval').body
            return self.generic_visit(node)
    nodes = [Counts().visit(validator), Counts().visit(saver)]
    if any(count != 1 for count in found.values()):
        raise ValueError('Exact installed person/reference count gates differ')
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    namespace = dict(people.__dict__)  # Keep the actually bound encoder/math globals.
    exec(compile(module, str(source)+'#capacity-counts', 'exec'), namespace)
    return namespace['_validate'], namespace['_save']


class CapacityPersonalStore:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._capacity_cache_bytes = 0

    def _memory(self, reservation=0):
        self._capacity_external_guard()
        measured = resource_snapshot()
        if measured['available_ram'] < RAM_FLOOR+reservation:
            raise MemoryError('Available RAM cannot preserve personal metadata working set and floor')
        if os.name != 'nt':
            import resource
            maximum = resource.getrlimit(resource.RLIMIT_AS)[0]
            current = measured.get('virtual_bytes')
            if maximum != resource.RLIM_INFINITY and (current is None or current+reservation > maximum):
                raise MemoryError('Personal metadata allocation exceeds the existing address-space budget')

    def _write_capacity(self, path, count):
        self._memory()
        self._capacity_budget.check_free(path, count)

    def _validate(self, row, folder):
        self._memory(2*128*1024)
        _ordinary(folder/'person.json', LIMITS['person.json'])
        if not isinstance(row, dict) or not isinstance(row.get('references'), list):
            return self._capacity_validate(row, folder)
        for ref in row['references']:
            if isinstance(ref, dict) and isinstance(ref.get('vector'), str):
                _member(row['id']+'/'+ref['vector'])
                _ordinary(folder/ref['vector'], LIMITS['.npy'])
            side = ref.get('script_evidence') if isinstance(ref, dict) else None
            if side:
                _member(row['id']+'/'+side['file'])
                _ordinary(folder/side['file'], LIMITS['.script.json'])
        return self._capacity_validate(row, folder)

    def _save(self, *args, **kwargs):
        self._write_capacity(self.root, 2*128*1024+256*1024+4096+65536)
        return self._capacity_save(*args, **kwargs)

    def iter_records(self):
        """Detached validated records, one bounded person at a time."""
        with self._lock:
            self._memory()
            # UUID names only, not accumulated metadata/vector payloads. Keep
            # original sorted-ID ordering and reserve for the path index itself.
            paths = []
            with os.scandir(self.root) as entries:
                for entry in entries:
                    info = entry.stat(follow_symlinks=False)
                    if entry.is_symlink() or getattr(info, 'st_file_attributes', 0)&0x400:
                        raise ValueError('Real owned personal directory entries required')
                    if not stat.S_ISDIR(info.st_mode):
                        continue
                    path = Path(entry.path)/'person.json'
                    if not path.exists():
                        continue
                    self._memory((len(paths)+1)*512)
                    _ordinary(path, LIMITS['person.json'])
                    paths.append(path)
            for path in sorted(paths):
                self._memory(2*128*1024)
                row = strict(path.read_bytes())
                yield self._validate(row, path.parent)

    def list(self, *, refresh=False):
        with self._lock:
            if self._list_cache is not None and not refresh:
                self._memory(2*self._capacity_cache_bytes)
                return deepcopy(self._list_cache)
            rows, size = [], 0
            for row in self.iter_records():
                cost = len(encoded(row))
                self._memory(4*cost)
                rows.append(row)
                size += cost
            if size <= CACHE_BYTES:
                self._memory(4*size)
                self._list_cache = deepcopy(rows)
                self._capacity_cache_bytes = size
            else:
                self._list_cache = None
                self._capacity_cache_bytes = 0
            return rows

    def summaries(self, route=None):
        rows = []
        from app.people import route_compatible
        for row in self.iter_records():
            self._memory()
            rows.append(dict(id=row['id'], name=row['name'], references=len(row['references']),
                environment_references=len(row.get('environment_bank', [])),
                enrichment_undo=any(item['status'] == 'active' for item in row.get('enrichment_history', [])),
                **(dict(compatible_references=sum(route_compatible(ref['route'], route)
                   for ref in row['references'])) if route else {})))
        return rows

    def gallery(self, route, person_ids=None, *, alternate_advisory=False):
        # The original constructor retains centroids, matrices, receipt metadata
        # and optional advisory matrices. Reserve their actual input sizes before
        # asking that unchanged constructor to allocate, rather than a count cap.
        from gallery_capacity_admission import allocation_bytes
        metadata, vectors = 0, 0
        selected = None if person_ids is None else set(person_ids)
        for row in self.iter_records():
            if selected is not None and row['id'] not in selected:
                continue
            metadata += len(encoded(row))
            for name in self._reference_files(row):
                _, maximum = _member(row['id']+'/'+name)
                vectors += _ordinary(self._path(row['id'])/name, maximum).st_size
        self._memory(allocation_bytes(metadata, vectors))
        return super().gallery(route, person_ids, alternate_advisory=alternate_advisory)

    def export(self, path, consent=False):
        if consent is not True:
            raise ValueError('Explicit unencrypted voice profile export consent required')
        path = Path(path)
        if path.exists() or path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise FileExistsError('Personal export never overwrites a path')
        self._write_capacity(self.root, 65536)
        with self._lock, tempfile.TemporaryFile(dir=self.root) as manifest, tempfile.TemporaryFile(dir=self.root) as ledger:
            prefix = b'{"schema_version":1,"privacy":"UNENCRYPTED PERSONAL VOICE VECTORS","files":{'
            self._write_capacity(self.root, len(prefix))
            manifest.write(prefix)
            count = 0
            with zipfile.ZipFile(path, 'x', zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                for row in self.iter_records():
                    folder = self._path(row['id'])
                    for source in [folder/'person.json']+[folder/name for name in self._reference_files(row)]:
                        name = source.relative_to(self.root).as_posix()
                        _, maximum = _member(name)
                        before = _ordinary(source, maximum)
                        self._write_capacity(path.parent, before.st_size+65536)
                        value = hashlib.sha256()
                        with source.open('rb') as original, archive.open(name, 'w', force_zip64=True) as copied:
                            while block := original.read(16384):
                                self._write_capacity(path.parent, len(block))
                                copied.write(block)
                                value.update(block)
                        expected = value.hexdigest()
                        if _identity(source.stat()) != _identity(before) or digest(source) != expected:
                            raise ValueError('Personal source changed during export')
                        membership = (b',' if count else b'')+encoded(name)+b':'+encoded(expected)
                        record = encoded(dict(path=name, sha256=expected, identity=list(_identity(before))))+b'\n'
                        self._write_capacity(self.root, len(membership)+len(record))
                        manifest.write(membership)
                        ledger.write(record)
                        count += 1
                        self._memory(len(archive.filelist)*512)
                self._write_capacity(self.root, 2)
                manifest.write(b'}}')
                manifest.flush()
                manifest.seek(0)
                manifest_hash = hashlib.sha256()
                with archive.open('MANIFEST.json', 'w', force_zip64=True) as copied:
                    while block := manifest.read(16384):
                        self._write_capacity(path.parent, len(block))
                        copied.write(block)
                        manifest_hash.update(block)
            with zipfile.ZipFile(path) as archive:
                if len(archive.infolist()) != count+1:
                    raise ValueError('Export readback membership differs')
                with archive.open('MANIFEST.json') as source:
                    actual_manifest = hashlib.sha256()
                    while block := source.read(16384):
                        self._memory()
                        actual_manifest.update(block)
                if actual_manifest.hexdigest() != manifest_hash.hexdigest():
                    raise ValueError('Export manifest independent readback differs')
                ledger.seek(0)
                for line in ledger:
                    record = strict(line)
                    source = self.root/record['path']
                    if list(_identity(source.stat())) != record['identity'] or digest(source) != record['sha256']:
                        raise ValueError('Original personal export source changed')
                    value = hashlib.sha256()
                    with archive.open(record['path']) as copied:
                        while block := copied.read(16384):
                            self._memory()
                            value.update(block)
                    if value.hexdigest() != record['sha256']:
                        raise ValueError('Export payload independent readback differs')
            with path.open('r+b') as source:
                os.fsync(source.fileno())

    def _import_archive(self, path):
        path = Path(path)
        before = _ordinary(path, path.stat().st_size)
        # CPython's ZIP reader indexes its central directory. Reserve against
        # its actual byte extent before allocating that index; payloads stream.
        with path.open('rb') as source:
            end = zipfile._EndRecData(source)
        if end is None:
            raise ValueError('Invalid personal ZIP central directory')
        self._memory(end[zipfile._ECD_SIZE]*12)
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len({name.casefold() for name in names}):
                raise ValueError('Duplicate personal archive entries')
            manifest_info = archive.getinfo('MANIFEST.json')
            self._memory(manifest_info.file_size*12)
            manifest = strict(archive.read('MANIFEST.json'))
            if (manifest.get('schema_version') != 1 or type(manifest.get('files')) is not dict
                    or set(names) != set(manifest['files']) | {'MANIFEST.json'}):
                raise ValueError('Invalid personal archive manifest')
            total = 0
            for name, expected in manifest['files'].items():
                _, maximum = _member(name)
                info = archive.getinfo(name)
                mode = info.external_attr >> 16
                if (info.is_dir() or info.file_size > maximum or (mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG))
                        or type(expected) is not str or len(expected) != 64
                        or any(char not in '0123456789abcdef' for char in expected)):
                    raise ValueError('Bounded ordinary personal archive member required')
                total += info.file_size
            self._write_capacity(self.root, total+65536)
            with tempfile.TemporaryDirectory(prefix='.peachy-import-', dir=self.root) as temporary:
                staged_root = Path(temporary)
                for name, expected in manifest['files'].items():
                    parts, maximum = _member(name)
                    target = staged_root.joinpath(*parts)
                    target.parent.mkdir(exist_ok=True)
                    value, size = hashlib.sha256(), 0
                    with archive.open(name) as source, target.open('xb') as copied:
                        while block := source.read(16384):
                            size += len(block)
                            if size > maximum:
                                raise ValueError('Individual personal payload exceeds parsing bound')
                            self._write_capacity(self.root, len(block))
                            copied.write(block)
                            value.update(block)
                        copied.flush()
                        os.fsync(copied.fileno())
                    if value.hexdigest() != expected or digest(target) != expected:
                        raise ValueError('Import payload checksum/readback differs')
                staged = type(self)(staged_root, self.backend)
                expected_count = 0
                for row in staged.iter_records():
                    if self._path(row['id']).exists():
                        raise ValueError('UUID already exists; import never overwrites people')
                    expected_count += 1+len(self._reference_files(row))
                if expected_count != len(manifest['files']):
                    raise ValueError('Unreferenced personal archive payload')
                if _identity(path.stat()) != _identity(before):
                    raise ValueError('Personal import archive changed before publication')
                published = []
                try:
                    for row in staged.iter_records():
                        if any(ref.get('script_evidence') for ref in row['references']):
                            self._require_script_feature()
                        if any(ref['route'].get('enhancement') for ref in row['references']):
                            self._require_script_feature('enhanced-reference-v1')
                        if row.get('enrichment_history'):
                            from app.reference_adaptation import FEATURE
                            self._require_script_feature(FEATURE)
                        self._write_capacity(self.root, 65536)
                        destination = self._path(row['id'])
                        if destination.exists():
                            raise ValueError('UUID appeared before import publication')
                        os.replace(staged_root/row['id'], destination)
                        published.append(row['id'])
                    if _identity(path.stat()) != _identity(before):
                        raise ValueError('Personal import archive changed during publication')
                except BaseException:
                    for identifier in published:
                        folder = self._path(identifier)
                        _ordinary(folder/'person.json', LIMITS['person.json'])
                        # These rows/files were fully validated before publication
                        # under the exclusive store owner. Rollback must remain
                        # possible if the very RAM guard caused the failure.
                        row = strict((folder/'person.json').read_bytes())
                        for name in self._reference_files(row):
                            (folder/name).unlink()
                        (folder/'person.json').unlink()
                        folder.rmdir()
                    raise
        self._invalidate()


def capacity_store_type(people, guard, budget=None):
    validator, saver = _derive(people)
    class Store(CapacityPersonalStore, people.PersonalStore):
        _capacity_validate = validator
        _capacity_save = saver
        _capacity_external_guard = staticmethod(guard)
        _capacity_budget = budget if budget is not None else DiskBudget(1)
    return Store
