"""Reconstruct bounded viewport histories. See README_VIEWPORT_REVIEW.md."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from common import bind, freeze, load, verify
from metric_process import identity, pin
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
from viewport_ledger_v2 import MAX_LOG_BYTES, MAX_RECORD_BYTES, MAX_ROWS, MAX_SPANS, MAX_MEMBERSHIPS, encoded, finite

MAX_OBSERVATIONS = 100000


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def decode(data):
    return json.loads(data, object_pairs_hook=unique_object,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON constant')))


def same(left, right):
    # Preserve numeric/boolean distinctions, not just Python's True == 1.
    return encoded(left) == encoded(right)


def validate_row(row):
    require(type(row) is dict and type(row.get('row_id')) is str and 0 < len(row['row_id']) <= 512,
        'Invalid row identity')
    spans = row.get('span_ids')
    require(type(spans) is list and 0 < len(spans) <= MAX_SPANS
        and all(type(s) is str and 0 < len(s) <= 512 for s in spans) and len(spans) == len(set(spans)), 'Invalid span identities')
    require(set(row['panes']) == {'active', 'history'}, 'Unknown viewport pane')
    for field in ('final', 'strictly_filtered', 'caption_visible', 'heading_visible'):
        require(type(row[field]) is bool, 'Invalid row visibility/finality flag')
    for pane in row['panes'].values():
        for field in ('present_in_widget', 'caption_visible', 'heading_visible'):
            require(type(pane[field]) is bool, 'Invalid pane visibility flag')
        if not pane['present_in_widget']:
            require(not pane['caption_visible'] and not pane['heading_visible'], 'Absent pane claims visible content')
        else:
            require(type(pane['applied_caption_text']) is str and type(pane['applied_heading_text']) is str,
                'Present pane lacks applied text')
        # Actual snapshots contain glyph counts. Synthetic collector fixtures may
        # omit them, but then cannot establish geometry-counter consistency.
        for field in ('caption', 'heading'):
            geometry = pane.get(field+'_viewport')
            if geometry is None: continue
            for counter in ('visible_nonspace_characters', 'checked_characters', 'partially_clipped_characters'):
                require(type(geometry[counter]) is int and 0 <= geometry[counter] <= 4096, 'Invalid glyph counter')
            require(geometry['partially_clipped_characters'] <= geometry['visible_nonspace_characters'] <= geometry['checked_characters'],
                'Inconsistent glyph counters')
            require(type(geometry['mapped']) is bool and type(geometry['any_visible']) is bool
                and geometry['any_visible'] == (geometry['visible_nonspace_characters'] > 0)
                and pane[field+'_visible'] == geometry['any_visible']
                and (geometry['mapped'] or not geometry['any_visible']), 'Geometry disagrees with visibility')
    for field in ('caption_visible', 'heading_visible'):
        require(row[field] == any(p[field] for p in row['panes'].values()), 'Row visibility differs from pane union')
    if row['strictly_filtered']:
        require(all(not p['present_in_widget'] for p in row['panes'].values()), 'Filtered row remains in widget')


def clock(metadata, previous, origin):
    require(metadata['schema'] == 'n4-tk-viewport-observation-v1'
        and metadata['physical_scanout_measured'] is False and metadata['source_to_widget_latency_qualified'] is False,
        'Foreign or overclaimed viewport observation')
    at = metadata['observed_monotonic_sec']; current = metadata['source_origin_monotonic_sec']
    require(finite(at) and (previous is None or at >= previous), 'Regressing viewport clock')
    require(type(metadata['character_checks']) is int and 0 <= metadata['character_checks'] <= 4096, 'Invalid glyph-check budget')
    if current is None:
        require(origin is None and metadata['source_elapsed_sec'] is None and metadata['source_clock'] == 'UNAVAILABLE'
            and metadata['source_relative_times_available'] is False, 'Source clock availability regressed or differs')
    else:
        require(finite(current) and current <= at and metadata['source_clock'] == 'ACTUAL_SOURCE_MONOTONIC'
            and metadata['source_relative_times_available'] is True and finite(metadata['source_elapsed_sec'])
            and metadata['source_elapsed_sec'] == at-current and (origin is None or current == origin),
            'Source origin changed or elapsed time differs')
    return at, current


def review(summary_binding, *, checkpoint=None):
    verify(summary_binding); require(0 < summary_binding['bytes'] <= 8*1024**2, 'Viewport summary exceeds bound')
    summary = decode(Path(summary_binding['path']).read_bytes()); evidence = summary['log']; verify(evidence)
    require(summary['schema'] == 'n4-viewport-ledger-summary-v1' and summary['status'] == 'RECORDED_POINT_OBSERVATIONS'
        and summary['failure'] is None, 'Viewport ledger failed or is a preserved prefix')
    require(all(summary[k] is False for k in ('continuous_exposure_measured','physical_scanout_measured','source_to_widget_latency_qualified')),
        'Viewport summary overclaims acceptance')
    require(Path(evidence['path']).resolve() == Path(summary_binding['path']).resolve().parent/'OBSERVATIONS.jsonl', 'Foreign viewport log')
    require(type(summary['maximum_log_bytes']) is int and 1 <= summary['maximum_log_bytes'] <= MAX_LOG_BYTES
        and 0 < evidence['bytes'] <= summary['maximum_log_bytes'], 'Viewport log allocation differs')
    require(type(summary['samples']) is int and 0 < summary['samples'] <= MAX_OBSERVATIONS
        and same(summary['maximum_rows'], MAX_ROWS) and same(summary['maximum_spans'], MAX_SPANS), 'Viewport census/bounds differ')
    require(finite(summary['observer_elapsed_seconds']) and summary['observer_elapsed_seconds'] >= 0, 'Invalid observer overhead')
    rows = {}; spans = {}; headings = {}; previous = origin = first = None
    samples = total = updates = retirements = source_samples = 0; maximum_interval = 0.; all_geometry = True
    with Path(evidence['path']).open('rb') as stream:
        while True:
            if checkpoint: checkpoint()
            data = stream.readline(MAX_RECORD_BYTES+1)
            if not data: break
            require(len(data) <= MAX_RECORD_BYTES and data.endswith(b'\n') and total+len(data) <= MAX_LOG_BYTES
                and samples < MAX_OBSERVATIONS, 'Viewport log truncated or exceeds bound')
            record = decode(data)
            require(set(record) == {'schema','index','metadata','changes'} and record['schema'] == 'n4-viewport-ledger-record-v1'
                and type(record['index']) is int and record['index'] == samples, 'Viewport observation index/schema differs')
            require(data == encoded(record)+b'\n', 'Viewport record is not the original canonical encoding')
            metadata = record['metadata']; require('rows' not in metadata, 'Rows hidden in observation metadata')
            at, current_origin = clock(metadata, previous, origin)
            base = dict(offset=total, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            changes = record['changes']; require(type(changes) is list and len(changes) <= 2*MAX_ROWS, 'Unbounded changed rows')
            changed_ids = set(); removed = []; removals_done = False
            for index, change in enumerate(changes):
                reference = dict(base, change_index=index)
                if change.get('kind') == 'removed':
                    require(not removals_done and set(change) == {'kind','row_id','from_ref'}, 'Retirement order/schema differs')
                    rid = change['row_id']
                    require(rid not in changed_ids and rid in rows and same(change['from_ref'], rows[rid]['reference']),
                        'Retirement does not reference its exact prior row')
                    require(not removed or removed[-1][0]['row_id'] < rid, 'Retirements not in canonical row order')
                    removed.append((rows.pop(rid)['row'], reference)); retirements += 1
                elif change.get('kind') == 'row':
                    removals_done = True; require(set(change) == {'kind','row'}, 'Unknown changed-row fields')
                    row = change['row']; validate_row(row); rid = row['row_id']
                    require(rid not in changed_ids and (rid not in rows or not same(row, rows[rid]['row'])),
                        'Duplicate or unchanged row emitted as change')
                    rows[rid] = dict(row=row, reference=reference); updates += 1
                else: raise ValueError('Unknown viewport change')
                changed_ids.add(rid)
            require(len(rows) <= MAX_ROWS, 'Active row count exceeds bound')
            memberships = [s for value in rows.values() for s in value['row']['span_ids']]
            # V2 does not persist order for unchanged rows. Never guess which of
            # two simultaneous rows sharing a span was visited last by the UI.
            require(len(memberships) == len(set(memberships)), 'Ambiguous simultaneous rows share a span; row order was not recorded')
            current_spans = set(memberships)
            require(len(memberships) <= MAX_MEMBERSHIPS and len(set(spans)|current_spans) <= MAX_SPANS, 'Span census exceeds bound')
            def state(reference):
                return dict(observed_monotonic_sec=at, source_elapsed_sec=metadata['source_elapsed_sec'], row_ref=reference)
            for row, reference in removed:
                for span in set(row['span_ids'])-current_spans:
                    spans[span]['latest'] = state(reference); headings[span] = dict(active=None, history=None)
            for value in rows.values():
                row = value['row']; observed = state(value['reference'])
                heading = {k:p.get('applied_heading_text') for k,p in row['panes'].items()}
                all_geometry = all_geometry and all(not p['present_in_widget'] or 'caption_viewport' in p and 'heading_viewport' in p
                    for p in row['panes'].values())
                for span in row['span_ids']:
                    item = spans.setdefault(span, dict(first_visible=None, first_final_visible=None, latest=None,
                        observed_heading_changes=0, observed_visible_heading_changes=0))
                    if row['caption_visible'] and item['first_visible'] is None: item['first_visible'] = observed
                    if row['caption_visible'] and row['final'] and item['first_final_visible'] is None: item['first_final_visible'] = observed
                    if item['latest'] is not None and headings[span] != heading:
                        item['observed_heading_changes'] += 1
                        if row['heading_visible']: item['observed_visible_heading_changes'] += 1
                    item['latest'] = observed; headings[span] = heading
            if previous is not None: maximum_interval = max(maximum_interval, at-previous)
            if first is None: first = at
            previous = at; origin = current_origin; source_samples += int(origin is not None)
            samples += 1; total += len(data)
    require(same(summary['spans'], spans), 'Reconstructed span states/references/counts differ')
    require(same(summary['samples'], samples) and same(summary['log_bytes'], total) and total == evidence['bytes']
        and same(summary['maximum_observation_interval_seconds'], maximum_interval), 'Reconstructed observation census/interval differs')
    verify(summary_binding); verify(evidence)
    return dict(status='PASS_RECONSTRUCTED_VIEWPORT_OBSERVATIONS_ONLY', input=summary_binding, evidence=evidence,
        observations=samples, row_updates=updates, row_retirements=retirements, spans_reconstructed=len(spans),
        span_summary_sha256=hashlib.sha256(encoded(spans)).hexdigest(), maximum_observation_interval_seconds=maximum_interval,
        first_observed_monotonic_sec=first, last_observed_monotonic_sec=previous, source_origin_monotonic_sec=origin,
        observations_with_source_clock=source_samples, all_present_panes_have_geometry_counters=all_geometry,
        continuous_exposure_measured=False, physical_scanout_measured=False, actual_source_delivery_verified=False,
        source_to_widget_latency_qualified=False, actual_continuity_test=False, integrated_N4_cells=0,
        limitations=['Saved point observations were reconstructed, not rendered again.',
            'A bound source-clock field does not prove actual source delivery or synchronization with the application.',
            'Unrecorded simultaneous-row order is ambiguous when different rows share a span; such inputs are refused.',
            'Names remain recorded fields; no identity, accuracy, correctness or enrollment is inferred from label text.',
            'No continuous visibility, physical scanout, latency, resource, target or stage acceptance.'])


def run(summary_path, output):
    process = pin(); started = time.monotonic(); local = Path('G:/Just_Peachy_N1/20260924_campaign/local')
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'), 'Fresh private review output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output, local, started, 720); inventory = shared_allowance(local)
        qualifier = load(Path(__file__).with_name('VIEWPORT_REVIEW_CHECK_V1.json'))
        require(qualifier['status'] == 'PASS_VIEWPORT_REVIEW_DEVELOPMENT_ONLY', 'Review implementation qualification required')
        for b in qualifier['code']: verify(b)
        summary = bind(summary_path)
        freeze(output/'ADMISSION.json', dict(owner=identity(process), summary=summary, inventory=inventory,
            qualification=bind(Path(__file__).with_name('VIEWPORT_REVIEW_CHECK_V1.json')), code=qualifier['code']))
        last_check = [0.]
        def checkpoint():
            if time.monotonic()-last_check[0] >= 5:
                guard(output, local, started, 720); last_check[0] = time.monotonic()
        reviewed = review(summary, checkpoint=checkpoint)
        guard(output, local, started, 720)
        freeze(output/'REVIEW.json', dict(reviewed, admission=bind(output/'ADMISSION.json'), utc=datetime.now(timezone.utc).isoformat()))
        print('Reviewed saved viewport history; no source, latency or stage acceptance', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args(); run(args.summary,args.output)
