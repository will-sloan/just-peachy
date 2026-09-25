"""New-run-only, recoverable lossless storage; see README_EVIDENCE_STORE.md."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import uuid

import psutil

from common import bind, load, verify
from evidence_archive import pack, verify_archive
from evidence_reader import ControllerEvidence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'supervision'))
from supervisor import atomic, lock

SCHEMA = 'n4-new-run-evidence-store-v1'
GIB = 2**30
REQUIRED_CHECKS = ('stopped', 'no_error', 'all_samples', 'drained',
                   'archive_complete', 'workers_closed')


def dependencies():
    here = Path(__file__).resolve().parent
    return [bind(path) for path in [here/'evidence_store.py', here/'evidence_archive.py',
        here/'evidence_reader.py', here/'common.py', here.parent/'supervision'/'supervisor.py']]


def safe_path(path, root=None):
    """Check lexical ancestors before resolving, including Windows junctions."""
    path = Path(os.path.abspath(path))
    for part in [*reversed(path.parents), path]:
        if not part.exists() and not part.is_symlink():
            continue
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Links/reparse points are not owned storage: '+str(part))
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise ValueError('Hard-linked files are not owned storage')
    resolved = path.resolve()
    if root is not None and not resolved.is_relative_to(root):
        raise ValueError('Path escapes the admitted store')
    return resolved


def seal(path, value):
    """Immutable receipt with flushed file contents; never replace evidence."""
    if path.exists():
        if load(path) != value:
            raise ValueError('Immutable storage receipt changed')
        return
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def initialize(root, *, max_bytes, cell_reserve_bytes, minimum_free):
    """Create a fresh namespace only. Existing directories cannot be adopted."""
    root = safe_path(root)
    if not (type(max_bytes) is int and type(cell_reserve_bytes) is int
            and 0 < cell_reserve_bytes <= max_bytes <= 80*GIB):
        raise ValueError('Declare a positive cell peak and remaining allocation <=80 GiB')
    reserves = []
    for path, minimum in minimum_free.items():
        path = safe_path(path)
        if not path.is_dir() or type(minimum) is not int or minimum < 0:
            raise ValueError('Invalid free-space reserve')
        reserves.append(dict(path=str(path), bytes=minimum))
    if not reserves:
        raise ValueError('Explicit free-space reserves are required')
    if os.name == 'nt':
        floors = {str(Path(r['path']).anchor).upper(): r['bytes'] for r in reserves}
        # Production Windows callers must preserve both campaign drive floors.
        for drive, minimum in [('C:\\', 50*GIB), ('G:\\', 75*GIB)]:
            if floors.get(drive, -1) < minimum:
                raise ValueError('Windows campaign requires C:50 GiB and G:75 GiB reserves')
    root.mkdir()  # exclusive; a failed admission never authorizes adopting old evidence
    admission = dict(schema=SCHEMA, root=str(root), run_id=uuid.uuid4().hex,
        max_bytes=max_bytes, cell_reserve_bytes=cell_reserve_bytes,
        minimum_free=reserves, code=dependencies(),
        scope='new attempts reserved by this store; historical evidence excluded')
    seal(root/'STORE_ADMISSION.json', admission)
    return root


class EvidenceStore:
    """Hold the OS writer lock for the entire runner lifetime, including inference."""
    def __init__(self, root):
        self.root = safe_path(root)
        self.admission_path = safe_path(self.root/'STORE_ADMISSION.json', self.root)
        self.admission = load(self.admission_path)
        if self.admission.get('schema') != SCHEMA or self.admission['root'] != str(self.root):
            raise ValueError('Wrong storage admission/root')
        if self.admission['code'] != dependencies():
            raise ValueError('Storage source changed; preserve this admission')
        self.admission_binding = bind(self.admission_path)
        self.held = False

    @contextmanager
    def writer(self):
        if self.held:
            raise RuntimeError('Writer is already held')
        with lock(safe_path(self.root/'store.lock', self.root)):
            process = psutil.Process()
            atomic(self.root/'STORE_OWNER.json', dict(pid=process.pid,
                create_time=process.create_time(), admission=self.admission_binding))
            self.held = True
            try:
                yield self
            finally:
                self.held = False

    def _require_writer(self):
        if not self.held:
            raise RuntimeError('Hold the store writer lock first')
        safe_path(self.root)
        verify(self.admission_binding)

    def _files(self, directory):
        result = []
        def fail(error):
            raise error
        for current, dirs, files in os.walk(directory, followlinks=False, onerror=fail):
            for name in dirs + files:
                path = safe_path(Path(current)/name, self.root)
                if path.is_file():
                    result.append(path)
        return result

    def guard(self, additional_bytes=0):
        """Runner must call during cell execution too; disk use is not predicted."""
        self._require_writer()
        if type(additional_bytes) is not int or additional_bytes < 0:
            raise ValueError('Invalid additional space')
        used = sum(p.stat().st_size for p in self._files(self.root))
        if used + additional_bytes > self.admission['max_bytes']:
            raise RuntimeError('Store allocation exhausted; preserve and stop')
        root_device = self.root.stat().st_dev
        for row in self.admission['minimum_free']:
            path = safe_path(row['path'])
            pending = additional_bytes if path.stat().st_dev == root_device else 0
            if shutil.disk_usage(path).free < row['bytes'] + pending:
                raise RuntimeError('Disk reserve would be breached; preserve and stop')
        return used

    def reserve(self, job_id, cache_key):
        self._require_writer()
        if not re.fullmatch(r'[A-Za-z0-9_-]+', job_id) or not re.fullmatch(r'[0-9a-f]{64}', cache_key):
            raise ValueError('Invalid job ID or cache key')
        # One unarchived successful/active attempt at a time keeps the bound useful.
        for receipt in self.root.glob('cells/*/STORE_RESERVATION.json'):
            if not (receipt.parent/'STORE_COMPLETE.json').exists():
                raise RuntimeError('Prior attempt requires completion or explicit failed-run review')
        self.guard(self.admission['cell_reserve_bytes'])
        cell = safe_path(self.root/'cells'/job_id, self.root)
        cell.mkdir(parents=True, exist_ok=False)
        attempt = cell/('attempt_'+uuid.uuid4().hex)
        attempt.mkdir()
        seal(cell/'STORE_RESERVATION.json', dict(admission=self.admission_binding,
            attempt=str(attempt), job_id=job_id, cache_key=cache_key))
        return attempt

    def _cell(self, result_path, status='COMPLETE'):
        self._require_writer()
        result_path = safe_path(result_path, self.root)
        attempt = result_path.parent
        cell = attempt.parent
        if cell.parent != self.root/'cells' or result_path.name != 'RESULT.json':
            raise ValueError('Result is outside a reserved cell')
        reservation = load(safe_path(cell/'STORE_RESERVATION.json', self.root))
        if reservation['admission'] != self.admission_binding or reservation['attempt'] != str(attempt):
            raise ValueError('Cell was not reserved by this store')
        result = load(result_path)
        if (result.get('attempt') != str(attempt) or result.get('job_id') != reservation['job_id']
                or result.get('cache_key') != reservation['cache_key']):
            raise ValueError('Execution does not match reservation')
        checks = REQUIRED_CHECKS if status == 'COMPLETE' else ('workers_closed',)
        if result.get('status') != status or not all(
                result.get('checks', {}).get(key) is True for key in checks):
            raise ValueError('Only completed, closed-worker evidence may be compacted')
        checkpoint_path = safe_path(cell/'CHECKPOINT.json', self.root)
        checkpoint = load(checkpoint_path)
        if (checkpoint.get('status') != status or checkpoint.get('result') != bind(result_path)
                or checkpoint.get('cache_key') != reservation['cache_key']):
            raise ValueError('Completed checkpoint changed')
        return result_path, cell, result

    def retain_failed(self, result_path):
        """Count a closed FAILED attempt without deleting/archiving any evidence."""
        result_path, cell, result = self._cell(result_path, status='FAILED')
        bound = {str(safe_path(row['path'], result_path.parent)): row for row in result['evidence']}
        actual = {str(p) for p in self._files(result_path.parent) if p != result_path}
        if len(bound) != len(result['evidence']) or actual != set(bound):
            raise ValueError('Failed evidence inventory differs')
        for row in bound.values():
            verify(row)
        receipt = dict(status='FAILED_EVIDENCE_RETAINED', admission=self.admission_binding,
            execution_result=bind(result_path), checkpoint=bind(cell/'CHECKPOINT.json'),
            reservation=bind(cell/'STORE_RESERVATION.json'), files=len(bound),
            retained_bytes=sum(row['bytes'] for row in bound.values()), released_bytes=0,
            stage_execution_credit=0, content_preserved=True)
        seal(cell/'STORE_COMPLETE.json', receipt)
        return receipt

    def _publish(self, source, archive):
        index_path = safe_path(self.root/'ARCHIVE_INDEX.json', self.root)
        index = load(index_path) if index_path.exists() else dict(schema='n4-archive-index-v1', archives={})
        entry = dict(execution_result=source, archive=archive)
        previous = index['archives'].get(source['sha256'])
        if previous is not None and previous != entry:
            raise ValueError('Existing archive index entry differs')
        index['archives'][source['sha256']] = entry
        atomic(index_path, index)

    def compact(self, result_path):
        """Verify, publish, then remove only verified copies in a NEW reserved cell.

        If interrupted, call again: durable intent permits missing copies only
        after the complete ZIP has been reverified. RESULT/checkpoint stay live.
        """
        result_path, cell, result = self._cell(result_path)
        source = bind(result_path)
        archive_path = safe_path(self.root/'archives'/(source['sha256']+'.zip'), self.root)
        intent_path = safe_path(cell/'STORE_INTENT.json', self.root)
        bound = {str(safe_path(row['path'], result_path.parent)): row for row in result['evidence']}
        if len(bound) != len(result['evidence']) or str(result_path) in bound:
            raise ValueError('Duplicate or recursive execution binding')
        actual = {str(p) for p in self._files(result_path.parent) if p != result_path}
        if actual - set(bound):
            raise ValueError('Unbound files in attempt: preserve all evidence and stop')
        intent = load(intent_path) if intent_path.exists() else None
        if intent is None:
            if actual != set(bound):
                raise ValueError('Missing evidence before archival intent')
            for row in bound.values():
                verify(row)
            # Conservative worst-case ZIP plus metadata bound; not measured compression.
            self.guard(2*(sum(row['bytes'] for row in bound.values())+source['bytes'])+4*2**20)
            if archive_path.exists():
                # A crash after ZIP creation is recoverable only if every source is present.
                manifest = verify_archive(archive_path)
                if manifest['execution_result'] != source:
                    raise ValueError('Orphan archive belongs to a different result')
            else:
                # The historical CLI helper pins itself; do not change the
                # caller's admitted inference allocation for the next cell.
                process = psutil.Process()
                affinity, priority = process.cpu_affinity(), process.nice()
                try:
                    pack(result_path, archive_path)
                finally:
                    process.cpu_affinity(affinity)
                    process.nice(priority)
            with archive_path.open('r+b') as stream:
                os.fsync(stream.fileno())
            archive = bind(archive_path)
            with ControllerEvidence(result, archive) as reader:
                for row in bound.values():
                    reader.read_bytes(row['path'])
            intent = dict(admission=self.admission_binding, source=source, archive=archive,
                checkpoint=bind(cell/'CHECKPOINT.json'), reservation=bind(cell/'STORE_RESERVATION.json'),
                remove=list(bound.values()))
            seal(intent_path, intent)
        else:
            if (intent['admission'] != self.admission_binding or intent['source'] != source
                    or intent['remove'] != list(bound.values()) or intent['archive']['path'] != str(archive_path)):
                raise ValueError('Archival intent changed')
            verify(intent['checkpoint']); verify(intent['reservation'])
            with ControllerEvidence(result, intent['archive']) as reader:
                for row in bound.values():
                    reader.read_bytes(row['path'])
        # Readers can use the complete archive before any local copies disappear.
        self._publish(source, intent['archive'])
        for row in intent['remove']:
            self._remove_verified(row)
        receipt = dict(status='ARCHIVED_COPIES_RELEASED', admission=self.admission_binding,
            execution_result=source, archive=intent['archive'], intent=bind(intent_path),
            files=len(bound), released_bytes=sum(row['bytes'] for row in bound.values()),
            stage_execution_credit=0, content_preserved=True,
            scope='only this newly reserved attempt; RESULT and checkpoint retained')
        seal(cell/'STORE_COMPLETE.json', receipt)
        return receipt

    def _remove_verified(self, row):
        path = safe_path(row['path'], self.root)
        if path.exists():
            verify(row)
            path.unlink()  # no directory or recursive removal; final absolute path checked above
