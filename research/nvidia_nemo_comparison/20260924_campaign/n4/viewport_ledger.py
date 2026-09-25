"""Bounded private viewport evidence with span references. README_VIEWPORT_LEDGER.md."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import threading
import time

from common import bind, freeze

MAX_ROWS = 512
MAX_SPANS = 8192
MAX_MEMBERSHIPS = 16384
MAX_LOG_BYTES = 64*1024**2
MAX_RECORD_BYTES = 8*1024**2


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def state(reference, observation):
    return dict(observed_monotonic_sec=observation['observed_monotonic_sec'],
        source_elapsed_sec=observation['source_elapsed_sec'], row_ref=reference)


class ViewportLedger:
    """Store changed row bodies once; spans retain only bounded references.

    This is a point-observation record, not continuous exposure, physical
    scanout, live-source proof or a deployment-memory benchmark. Add on the
    same UI thread after actual viewport observation. No background owner,
    application mutation, replay clock replacement or label inference occurs.
    """
    def __init__(self, directory, *, maximum_log_bytes=MAX_LOG_BYTES):
        if type(maximum_log_bytes) is not int or not 1 <= maximum_log_bytes <= MAX_LOG_BYTES:
            raise ValueError('Bounded log allocation required')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.path = self.directory/'OBSERVATIONS.jsonl'
        self.file = self.path.open('xb')
        self.owner_thread = threading.get_ident()
        self.maximum_log_bytes = maximum_log_bytes
        self.bytes_written = self.samples = 0
        self.previous = self.origin = None
        self.maximum_interval = 0.
        self.rows = {}; self.spans = {}; self.headings = {}
        self.failure = None; self.closed = False
        self.observer_elapsed_seconds = 0.

    def add(self, observation):
        if self.closed or self.failure is not None:
            raise ValueError('Ledger is closed or failed; preserve its prefix')
        if threading.get_ident() != self.owner_thread:
            raise ValueError('Viewport ledger requires its original UI thread')
        started = time.perf_counter()
        try:
            return self._add(observation)
        except Exception as exc:
            self.failure = type(exc).__name__ + ': ' + str(exc)
            raise
        finally:
            self.observer_elapsed_seconds += time.perf_counter() - started

    def _add(self, observation):
        if (observation.get('schema') != 'n4-tk-viewport-observation-v1'
                or observation.get('physical_scanout_measured') is not False
                or observation.get('source_to_widget_latency_qualified') is not False):
            raise ValueError('Require explicitly limited viewport observations')
        at = observation['observed_monotonic_sec']
        if not finite(at) or self.previous is not None and at < self.previous:
            raise ValueError('Invalid or regressing observation clock')
        origin = observation['source_origin_monotonic_sec']; elapsed = observation['source_elapsed_sec']
        if origin is None:
            if self.origin is not None or elapsed is not None or observation['source_relative_times_available'] is not False:
                raise ValueError('Source clock availability regressed or disagrees')
        elif (not finite(origin) or origin > at or observation['source_clock'] != 'ACTUAL_SOURCE_MONOTONIC'
                or observation['source_relative_times_available'] is not True or not finite(elapsed)
                or elapsed != at-origin or self.origin is not None and origin != self.origin):
            raise ValueError('Source clock changed or was modeled')
        rows = observation['rows']
        if len(rows) > MAX_ROWS or len({r['row_id'] for r in rows}) != len(rows):
            raise ValueError('Unique bounded viewport rows required')
        for row in rows:
            if (not isinstance(row['row_id'], str) or not 0 < len(row['row_id']) <= 512
                    or not row['span_ids'] or len(set(row['span_ids'])) != len(row['span_ids'])
                    or any(not isinstance(s, str) or not 0 < len(s) <= 512 for s in row['span_ids'])
                    or set(row['panes']) != {'active', 'history'}):
                raise ValueError('Invalid row, pane or span identifiers')
        current_spans = {s for row in rows for s in row['span_ids']}
        if len(set(self.spans) | current_spans) > MAX_SPANS or sum(len(r['span_ids']) for r in rows) > MAX_MEMBERSHIPS:
            raise ValueError('Span evidence bound exceeded; no silent eviction')
        changes = []; descriptors = {}; removed = []
        for rid in sorted(set(self.rows)-{r['row_id'] for r in rows}):
            previous = self.rows[rid]
            change = dict(kind='removed', row_id=rid, from_ref=previous['row_ref'])
            removed.append((previous, len(changes))); changes.append(change)
        for row in rows:
            checksum = digest(row); previous = self.rows.get(row['row_id'])
            heading_hash = digest({k:p.get('applied_heading_text') for k,p in row['panes'].items()})
            descriptor = dict(sha256=checksum, span_ids=tuple(row['span_ids']), heading_hash=heading_hash)
            if previous is not None and previous['sha256'] == checksum:
                descriptor['row_ref'] = previous['row_ref']
            else:
                descriptor['change_index'] = len(changes)
                changes.append(dict(kind='row', row=row))
            descriptors[row['row_id']] = descriptor
        metadata = {k:v for k,v in observation.items() if k != 'rows'}
        record = dict(schema='n4-viewport-ledger-record-v1', index=self.samples, metadata=metadata, changes=changes)
        data = encoded(record)+b'\n'
        if len(data) > MAX_RECORD_BYTES or self.bytes_written+len(data) > self.maximum_log_bytes:
            raise ValueError('Viewport log allocation exceeded; preserve complete prefix')
        base = dict(offset=self.bytes_written, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        if self.file.write(data) != len(data):
            raise OSError('Incomplete viewport evidence write')
        self.file.flush()
        self.bytes_written += len(data)
        # Commit compact state only after the complete bounded record is written.
        for descriptor in descriptors.values():
            if 'change_index' in descriptor:
                descriptor['row_ref'] = dict(base, change_index=descriptor.pop('change_index'))
        for previous, index in removed:
            reference = dict(base, change_index=index)
            for span in set(previous['span_ids'])-current_spans:
                self.spans[span]['latest'] = state(reference, observation)
                self.headings[span] = digest({'history':None, 'active':None})
        for row in rows:
            descriptor = descriptors[row['row_id']]
            observed = state(descriptor['row_ref'], observation)
            for span in row['span_ids']:
                item = self.spans.setdefault(span, dict(first_visible=None, first_final_visible=None, latest=None,
                    observed_heading_changes=0, observed_visible_heading_changes=0))
                if row['caption_visible'] and item['first_visible'] is None:
                    item['first_visible'] = observed
                if row['caption_visible'] and row['final'] and item['first_final_visible'] is None:
                    item['first_final_visible'] = observed
                if item['latest'] is not None and self.headings[span] != descriptor['heading_hash']:
                    item['observed_heading_changes'] += 1
                    if row['heading_visible']: item['observed_visible_heading_changes'] += 1
                item['latest'] = observed; self.headings[span] = descriptor['heading_hash']
        self.rows = descriptors
        if self.previous is not None: self.maximum_interval = max(self.maximum_interval, at-self.previous)
        self.previous = at; self.origin = origin; self.samples += 1
        return dict(index=record['index'], changed_rows=len(changes), log_bytes=self.bytes_written)

    def compact_summary(self):
        return dict(schema='n4-viewport-ledger-summary-v1', status='FAILED_PRESERVED_PREFIX' if self.failure else 'RECORDED_POINT_OBSERVATIONS',
            failure=self.failure, samples=self.samples, spans=deepcopy(self.spans),
            maximum_observation_interval_seconds=self.maximum_interval,
            observer_elapsed_seconds=self.observer_elapsed_seconds, log_bytes=self.bytes_written,
            maximum_log_bytes=self.maximum_log_bytes, maximum_spans=MAX_SPANS, maximum_rows=MAX_ROWS,
            continuous_exposure_measured=False, physical_scanout_measured=False,
            source_to_widget_latency_qualified=False)

    def close(self):
        if self.closed: raise ValueError('Already closed')
        if threading.get_ident() != self.owner_thread: raise ValueError('Close on the original UI thread')
        self.file.close(); self.closed = True
        result = self.compact_summary(); result['log'] = bind(self.path)
        if len(encoded(result)) > 8*1024**2:
            raise ValueError('Compact summary allocation exceeded')
        freeze(self.directory/'SUMMARY.json', result)
        return result


def read_row(path, reference, *, removal_depth=0):
    """Read a bounded hash-bound record; retirement has at most one back-link."""
    if (set(reference) != {'offset','bytes','sha256','change_index'} or type(reference['offset']) is not int
            or reference['offset'] < 0 or type(reference['bytes']) is not int
            or not 1 <= reference['bytes'] <= MAX_RECORD_BYTES or type(reference['change_index']) is not int
            or reference['change_index'] < 0 or removal_depth > 1):
        raise ValueError('Invalid bounded viewport reference')
    with Path(path).open('rb') as stream:
        stream.seek(reference['offset']); data = stream.read(reference['bytes'])
    if len(data) != reference['bytes'] or hashlib.sha256(data).hexdigest() != reference['sha256'] or not data.endswith(b'\n'):
        raise ValueError('Viewport record truncated or changed')
    record = json.loads(data)
    if record.get('schema') != 'n4-viewport-ledger-record-v1': raise ValueError('Foreign viewport record')
    change = record['changes'][reference['change_index']]
    if change['kind'] == 'row': return change['row']
    if change['kind'] != 'removed' or change['from_ref']['offset'] >= reference['offset']:
        raise ValueError('Invalid retirement reference')
    row = read_row(path, change['from_ref'], removal_depth=removal_depth+1)
    if row['row_id'] != change['row_id']: raise ValueError('Retirement row identity differs')
    row.update(caption_visible=False, heading_visible=False, removed_from_controller=True)
    row['panes'] = {k:dict(present_in_widget=False, caption_visible=False, heading_visible=False) for k in ('history','active')}
    return row


def expand_summary(path, summary):
    """Evaluator-only compatibility view. Do not expand in a paced application."""
    from common import verify
    verify(summary['log'])
    if Path(path).resolve() != Path(summary['log']['path']).resolve(): raise ValueError('Foreign ledger file')
    spans = deepcopy(summary['spans'])
    for item in spans.values():
        for kind in ('first_visible','first_final_visible','latest'):
            v = item[kind]
            if v is not None: v['row'] = read_row(path, v.pop('row_ref'))
    return dict(samples=summary['samples'], maximum_observation_interval_seconds=summary['maximum_observation_interval_seconds'],
        spans=spans, continuous_exposure_measured=False, physical_scanout_measured=False)
