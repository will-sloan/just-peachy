"""Pinned Sherpa loop facade: bounded native segments, spoken-group punctuation.

The inherited loop, audio clocks, scheduler and reset are unchanged. See
README_ASR_SEGMENTS.md for the production binding and focused run commands.
The private metadata-cache candidate is described in README_ASR_METADATA_CACHE.md.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from asr_segment_contract import NativeSegmentContract
from asr_metadata_cache import MetadataCache, MISS

RUNTIME_SHA256 = '64c8021099be59578f1408228bd4dda6b76821f9efd29b2f68172b3f0938f78c'
MODELS_SHA256 = 'd15972b6968ea8a1d5a8c76bba2fe30d504df5f0b1e7963a1166c65d4fcd9056'
BOUNDARY_FIELDS = ('recognition_segment_final', 'utterance_final',
                   'utterance_group_id', 'endpoint_kind', 'leading_text_joiner',
                   'utterance_boundary_kind', 'spoken_punctuation_ready')


class SegmentLedger:
    """Disk-owned pieces; bounded keyset reads and exact per-parent lookups.

    One current piece is updated in place. Sealed pieces and display patches are
    durable; no session-sized Python transcript or token list is retained.
    Connections are short lived and commits serialized between the two lanes.
    """
    def __init__(self, path, *, policy=None):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._metadata_cache = MetadataCache()
        if policy is None:
            from storage import StoragePolicy
            policy = StoragePolicy()
        self.policy = policy
        with self._connection(write=True) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS pieces(
                  seq INTEGER PRIMARY KEY, parent TEXT UNIQUE NOT NULL,
                  group_id TEXT NOT NULL, raw TEXT NOT NULL, metadata TEXT NOT NULL,
                  final_published INTEGER NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS piece_group ON pieces(group_id,seq);
                CREATE TABLE IF NOT EXISTS closed_groups(
                  group_id TEXT PRIMARY KEY, boundary TEXT NOT NULL,
                  punctuation_done INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS patches(
                  parent TEXT NOT NULL,start INTEGER NOT NULL,end INTEGER NOT NULL,
                  text TEXT NOT NULL, PRIMARY KEY(parent,start));
                CREATE TABLE IF NOT EXISTS punctuation(
                  parent TEXT PRIMARY KEY, metadata TEXT NOT NULL);
            ''')
        self._metadata_cache.observe(self._metadata_stamp())

    def _metadata_stamp(self):
        """Observe only this ledger and its named sidecars; never read payloads.

        This is a drift/fallback check within the existing owned-session model,
        not atomic protection against an unauthorized concurrent filesystem writer.
        """
        result = []
        for suffix in ('', '-journal', '-wal', '-shm'):
            path = self.path.with_name(self.path.name + suffix)
            try:
                value = path.lstat()
            except FileNotFoundError:
                if not suffix:
                    raise OSError('Existing admitted ASR ledger required for read')
                result.append(None)
            else:
                result.append((value.st_dev, value.st_ino, value.st_mode,
                    value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns))
        return tuple(result)

    @contextmanager
    def _metadata_write(self, *, changed_seq=None, group=None):
        """Refresh/invalidate only after the original durable commit succeeds."""
        with self._lock:
            try:
                self._metadata_cache.observe(self._metadata_stamp())
                parent = None
                with self._connection(write=True) as db:
                    yield db
                    if changed_seq is not None:
                        # The inherited UPSERT keeps the stored parent/group on
                        # seq conflict. Invalidate the actual affected parent,
                        # including SQLite binding affinity and unusual callers.
                        parent = db.execute('SELECT parent FROM pieces WHERE seq=?',
                                            (changed_seq,)).fetchone()[0]
            except BaseException:
                self._metadata_cache.fault()
                raise
            else:
                try:
                    self._metadata_cache.committed(self._metadata_stamp(), parent=parent, group=group)
                except MemoryError:
                    self._metadata_cache.clear()
                    self._metadata_cache.fault()
                except BaseException:
                    self._metadata_cache.fault()
                    raise

    @contextmanager
    def _connection(self, *, write=False):
        if write:
            from storage_support import ensure_sqlite_file_limit
            ensure_sqlite_file_limit(self.path.parent,self.policy,
                                     metadata_bytes=4*1024**2,database_name=self.path.name)
        elif not self.path.is_file():
            raise OSError('Existing admitted ASR ledger required for read')
        db = sqlite3.connect(self.path, timeout=30)
        # Bound SQLite's working cache independently of the on-disk session.
        db.execute('PRAGMA cache_size=-1024')
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def record(self, seq, text, metadata):
        with self._metadata_write(changed_seq=seq) as db:
            db.execute('INSERT INTO pieces(seq,parent,group_id,raw,metadata) VALUES(?,?,?,?,?) ON CONFLICT(seq) DO UPDATE SET '
                       'raw=excluded.raw,metadata=excluded.metadata',
                       (seq, metadata['native_segment_id'], metadata['utterance_group_id'],
                        text, json.dumps(metadata, ensure_ascii=False)))

    def claim_final(self, parent):
        with self._metadata_write() as db:
            return db.execute('UPDATE pieces SET final_published=1 WHERE parent=? '
                              'AND final_published=0', (parent,)).rowcount == 1

    def metadata(self, parent):
        with self._lock:
            try:
                # Preserve the existing read admission before any cache hit.
                if not self.path.is_file():
                    raise OSError('Existing admitted ASR ledger required for read')
                before = self._metadata_stamp()
                self._metadata_cache.observe(before)
                cached = self._metadata_cache.get(parent)
                if cached is not MISS:
                    return dict(json.loads(cached[0]), spoken_punctuation_ready=cached[2])
                with self._connection() as db:
                    row = db.execute('SELECT p.metadata,COALESCE(g.punctuation_done,0),p.group_id FROM pieces p '
                                     'LEFT JOIN closed_groups g ON g.group_id=p.group_id '
                                     'WHERE parent=?', (parent,)).fetchone()
                value = dict(json.loads(row[0]), spoken_punctuation_ready=bool(row[1])) if row else None
                after = self._metadata_stamp()
                if after != before:
                    self._metadata_cache.observe(after)
                elif row is not None:
                    self._metadata_cache.put(parent, row[0], row[2], bool(row[1]))
                return value
            except BaseException:
                # A cached row must not hide a subsequent connection/parse fault
                # observed on another parent. Preserve the original exception.
                self._metadata_cache.fault()
                raise

    def close_group(self, group_id, boundary):
        with self._metadata_write(group=group_id) as db:
            if db.execute('SELECT 1 FROM closed_groups WHERE group_id=?', (group_id,)).fetchone():
                return False
            row = db.execute('SELECT seq,metadata FROM pieces WHERE group_id=? AND raw<>? '
                             'ORDER BY seq DESC LIMIT 1', (group_id, '')).fetchone()
            db.execute('INSERT INTO closed_groups(group_id,boundary) VALUES(?,?)', (group_id, boundary))
            if row is None:
                return False
            metadata = json.loads(row[1])
            metadata.update(utterance_final=True, utterance_boundary_kind=boundary)
            db.execute('UPDATE pieces SET metadata=? WHERE seq=?',
                       (json.dumps(metadata), row[0]))
            return True

    def mark_punctuated(self, group_id):
        with self._metadata_write(group=group_id) as db:
            db.execute('UPDATE closed_groups SET punctuation_done=1 WHERE group_id=?', (group_id,))

    def pieces(self, group_id):
        after = -1
        while True:
            with self._lock, self._connection() as db:
                row = db.execute('SELECT seq,parent,raw,metadata FROM pieces WHERE '
                                 'group_id=? AND seq>? ORDER BY seq LIMIT 1',
                                 (group_id, after)).fetchone()
            if row is None:
                return
            after = row[0]
            if row[2]:
                yield dict(seq=row[0], parent=row[1], raw=row[2], metadata=json.loads(row[3]))

    def save_patches(self, patches, metadata):
        """One bounded window transaction, never a whole-group write buffer."""
        with self._metadata_write() as db:
            db.executemany('INSERT INTO patches VALUES(?,?,?,?) ON CONFLICT(parent,start) '
                           'DO UPDATE SET end=excluded.end,text=excluded.text', patches)
            db.executemany('INSERT INTO punctuation VALUES(?,?) ON CONFLICT(parent) '
                           'DO UPDATE SET metadata=excluded.metadata',
                           ((parent,json.dumps(metadata)) for parent in {p[0] for p in patches}))

    def get(self, parent, default=None):
        """Compatibility with revised-transcript lookup; at most one native piece."""
        with self._lock, self._connection() as db:
            row = db.execute('SELECT p.raw,u.metadata FROM pieces p JOIN punctuation u '
                             'ON u.parent=p.parent WHERE p.parent=?', (parent,)).fetchone()
            if row is None:
                return default
            patches = db.execute('SELECT start,end,text FROM patches WHERE parent=? '
                                 'ORDER BY start', (parent,)).fetchall()
        raw, info = row[0], json.loads(row[1])
        cursor, display = 0, []
        for start,end,text in patches:
            if start < cursor or end < start or end > len(raw):
                raise ValueError('Invalid punctuation patch interval')
            display.extend((raw[cursor:start], text))
            cursor = end
        display.append(raw[cursor:])
        return dict(info, text=''.join(display), raw_text=raw)


def _words(pieces, *, word_byte_budget=180):
    """Yield lexical words and source-character ownership, with bounded fallback.

    The byte budget bounds a *PnC input*, never accepted speech. A giant word
    streams as exact raw chunks instead of reaching the model's 200-BPE assert.
    """
    text, owners, unsafe = '', [], False
    def take():
        return dict(text=text, owners=tuple(owners), unsafe=unsafe)
    for piece in pieces:
        if text and piece['metadata']['leading_text_joiner'] == ' ':
            yield take()
            text, owners, unsafe = '', [], False
        for match in re.finditer(r'\S+|\s+', piece['raw']):
            value = match.group()
            if value.isspace():
                if text:
                    yield take()
                text, owners, unsafe = '', [], False
                continue
            start = match.start()
            for character in value:
                if len((text+character).encode('utf-8')) > word_byte_budget:
                    # Every chunk of this overlong lexical word remains raw.
                    unsafe = True
                    yield take()
                    text, owners = '', []
                if owners and owners[-1][0] == piece['parent'] and owners[-1][2] == start:
                    owner = owners.pop()
                    owners.append((owner[0],owner[1],start+1))
                else:
                    owners.append((piece['parent'],start,start+1))
                text += character
                start += 1
    if text:
        yield take()


def _windows(words, *, word_budget=96, byte_budget=4096):
    window, used = [], 0
    for word in words:
        size = len(word['text'].encode('utf-8'))+1
        if window and (len(window) >= word_budget or used+size > byte_budget or word['unsafe']):
            yield window
            window, used = [], 0
        window.append(word)
        used += size
        if word['unsafe']:
            yield window
            window, used = [], 0
    if window:
        yield window


def _map_case_and_punctuation(words, display):
    """Accept case/punctuation only; raw lexical characters cannot be rewritten."""
    values = display.split()
    if len(values) != len(words):
        raise ValueError('PnC changed lexical word count')
    patches = []
    for word,value in zip(words,values):
        lexical = value[:len(word['text'])]
        suffix = value[len(word['text']):]
        if lexical.casefold() != word['text'].casefold() or any(mark not in ',.?!' for mark in suffix):
            raise ValueError('PnC changed raw lexical characters')
        cursor = 0
        for index,(parent,start,end) in enumerate(word['owners']):
            length = end-start
            part = lexical[cursor:cursor+length]
            cursor += length
            if index == len(word['owners'])-1:
                part += suffix
            patches.append((parent,start,end,part))
    return patches


class _SherpaSegments:
    """Actual-token facade consumed by the exact inherited ASR loop."""
    def __init__(self, engine, asr):
        self.engine, self.asr = engine, asr
        self.samples, self.start = 0, 0.0
        self.native_endpoint = False
        self.last_written = None

    def __getattr__(self, name):
        return getattr(self.asr, name)

    def _observe(self, text, *, endpoint=False, stop=False):
        tokens = list(self.asr.recognizer.tokens(self.asr.stream))
        metadata = self.engine._segment_contract.observe(
            segment_id=f'utterance:{self.asr.utterance_index:06d}', raw_text=text,
            tokens=tokens, source_start_sec=self.start,
            source_end_sec=self.samples/self.asr.sample_rate,
            native_endpoint=endpoint and self.native_endpoint, stop=stop,
            advisory_endpoint=endpoint and not self.native_endpoint)
        changed = (self.asr.utterance_index,text,metadata['leading_text_joiner'])
        if endpoint or stop or changed != self.last_written:
            self.engine._segment_ledger.record(self.asr.utterance_index,text,metadata)
            self.last_written = changed
        return metadata

    def accept(self, audio):
        text, self.native_endpoint = self.asr.accept(audio)
        self.samples += int(audio.size)
        self._observe(text)
        return text, self.native_endpoint

    def reset_endpoint(self):
        # Capture native tokens before reset; the original reset consumes no
        # source samples and keeps its exact encoder/context semantics.
        result = self.asr.recognizer.get_result(self.asr.stream)
        text = (result if isinstance(result,str) else result.get('text','')
                if isinstance(result,dict) else getattr(result,'text',''))
        text = str(text).strip()
        metadata = self._observe(text, endpoint=True)
        final = self.asr.reset_endpoint()
        if final != text:
            raise ValueError('Native text changed during endpoint reset')
        self.start = self.samples/self.asr.sample_rate
        if metadata['utterance_final'] and not final:
            self.engine._close_spoken_group(self.asr,metadata,'native_pause' if self.native_endpoint else 'advisory')
        return final

    def finish(self):
        text = self.asr.finish()
        metadata = self._observe(text, stop=True)
        if not text:
            self.engine._close_spoken_group(self.asr,metadata,'stop')
        return text


class SegmentedAsrMixin:
    """Production mixin; preserves model pins and delegates the immutable loop."""
    def _asr_loop(self, asr):
        inherited = super()._asr_loop
        try:
            if self.config.endpoint_rule3_utterance_sec != 20.0:
                raise ValueError('Admitted 20-second internal resource reset required')
            for path,expected in ((Path(inherited.__func__.__code__.co_filename),RUNTIME_SHA256),
                                  (Path(inspect.getfile(type(asr))),MODELS_SHA256)):
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise ValueError('Exact admitted runtime/model source required')
            self._segment_contract = NativeSegmentContract(native_resource_seconds=20.0)
            self._segment_ledger = SegmentLedger(self._session_dir/'asr_segments.sqlite3',
                                                 policy=getattr(self,'_segment_storage_policy',None))
            self._s6d_punctuated = self._segment_ledger
            self._emit('asr_segment_contract',0.,dict(runtime_sha256=RUNTIME_SHA256,
                       models_sha256=MODELS_SHA256,internal_reset_seconds=20.,
                       token_joiner='actual pinned BPE word-start marker',
                       source_timing='native accepted-sample windows; no phonetic alignment'))
        except Exception as exc:
            self._fail(f'Segmented ASR admission failed: {exc}')
            if self._research_v2 and self._scheduler is not None:
                self._scheduler_advance('asr',float('inf'),self._research_asr_available_sec)
            return
        return inherited(_SherpaSegments(self,asr))

    def asr_segment_row(self, row):
        ledger = getattr(self,'_segment_ledger',None)
        metadata = ledger.metadata(row.get('utterance_id')) if ledger is not None else None
        if metadata is None:
            return row
        return dict(row, **{field:metadata[field] for field in BOUNDARY_FIELDS if field in metadata})

    def _emit(self, kind, source_sec, payload):
        if type(payload) is dict and payload.get('utterance_id'):
            payload = self.asr_segment_row(payload)
        return super()._emit(kind,source_sec,payload)

    def _publish_final(self, asr, text, source_sec, utterance, decode_ms):
        parent = f'utterance:{utterance:06d}'
        metadata = self._segment_ledger.metadata(parent)
        if metadata is None or not metadata['recognition_segment_final']:
            raise ValueError('Native final needs its captured pre-reset boundary')
        if not self._segment_ledger.claim_final(parent):
            return
        # Seal this source piece immediately. Terminal punctuation belongs to
        # the spoken group, never the 20-second resource boundary.
        self._transcript_event(text,source_sec,final=True,utterance=utterance,decode_ms=decode_ms)
        if metadata['utterance_final']:
            self._close_spoken_group(getattr(asr,'asr',asr),metadata,metadata['endpoint_kind'])

    def _close_spoken_group(self, asr, metadata, boundary):
        group = metadata['utterance_group_id']
        if not self._segment_ledger.close_group(group,boundary):
            return
        self._emit('asr_spoken_boundary',metadata['source_end_sec'],dict(
            utterance_group_id=group,utterance_boundary_kind=boundary,
            source_end_sec=metadata['source_end_sec'],raw_words_unchanged=True))
        job = ('spoken_group',asr,group)
        if self._s6d_punctuation is None:
            return self._s6d_punctuate(job)
        self._s6d_punctuation.submit(job)

    def _s6d_punctuate(self, job):
        if not (isinstance(job,tuple) and job[0] == 'spoken_group'):
            return super()._s6d_punctuate(job)
        _,asr,group = job
        windows = iter(_windows(_words(self._segment_ledger.pieces(group))))
        window = next(windows,None)
        while window is not None:
            following = next(windows,None)
            raw = ' '.join(word['text'] for word in window)
            started = time.perf_counter()
            if any(word['unsafe'] for word in window):
                result = dict(text=raw,status='raw_overlong_word',compute_ms=0.,
                              terminal_fallback=None)
            else:
                result = asr.punctuate(raw)
            display = str(result['text'])
            if following is not None:
                display = display.rstrip('.?')
            try:
                patches = _map_case_and_punctuation(window,display)
            except ValueError:
                # Never let a formatting failure alter recognized lexical text.
                result = dict(result,status='raw_lexical_guard',terminal_fallback=None)
                patches = _map_case_and_punctuation(window,raw)
            self._segment_ledger.save_patches(patches,dict(result,
                text='',utterance_group_id=group,punctuation_scope='bounded spoken-group window',
                raw_words_unchanged=True,compute_started_monotonic_sec=started,
                compute_finished_monotonic_sec=time.perf_counter()))
            self._record_punctuation(result)
            window = following
        self._segment_ledger.mark_punctuated(group)
        # Publish each stable original parent, with exact original source bounds.
        for piece in self._segment_ledger.pieces(group):
            result = self._segment_ledger.get(piece['parent'])
            if result is None:
                continue
            self._emit('s6d_punctuation_revision',piece['metadata']['source_end_sec'],dict(
                utterance_id=piece['parent'],text=piece['raw'],display_text=result['text'],
                punctuation=result,
                compute_started_monotonic_sec=result['compute_started_monotonic_sec'],
                compute_finished_monotonic_sec=result['compute_finished_monotonic_sec'],
                changes_raw_words=False))
