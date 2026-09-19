"""Paired count aggregation and conditional block sensitivity. README_S5.md."""
from __future__ import annotations
import collections
import numpy as np

COUNT_FIELDS = ('errors', 'substitutions', 'deletions', 'insertions', 'reference_words', 'hypothesis_words')

def pooled(rows, stream, metric='text'):
    values = [r[stream].get(metric, {}) for r in rows if r.get(stream)]
    values = [v for v in values if v.get('word_counts') and v['word_counts']['reference_words'] > 0]
    count = {k: sum(v['word_counts'][k] for v in values) for k in COUNT_FIELDS}
    n = count['reference_words']
    wers = [v['word_counts']['errors'] / v['word_counts']['reference_words'] for v in values]
    return {'scenes': len(values), **count, 'wer': count['errors'] / n if n else None,
            'macro_scene_wer': float(np.mean(wers)) if wers else None}

def paired(rows, metric='text'):
    eligible = [r for r in rows if all((r.get(s) or {}).get(metric, {}).get('word_counts', {}).get('reference_words', 0) > 0 for s in ('O0', 'O1'))]
    for row in eligible:
        assert row['O0'][metric]['word_counts']['reference_words'] == row['O1'][metric]['word_counts']['reference_words'], 'Paired reference denominator differs'
    a, b = pooled(eligible, 'O0', metric), pooled(eligible, 'O1', metric)
    deltas = [(r['O1'][metric]['word_counts']['errors'] - r['O0'][metric]['word_counts']['errors']) /
              r['O0'][metric]['word_counts']['reference_words'] for r in eligible]
    return {'metric': metric, 'paired_scenes': len(eligible), 'O0': a, 'O1': b,
            'O1_minus_O0_errors': b['errors'] - a['errors'],
            'O1_minus_O0_wer_pp': 100 * (b['wer'] - a['wer']) if a['wer'] is not None else None,
            'O0_better_scenes': sum(x > 0 for x in deltas), 'O1_better_scenes': sum(x < 0 for x in deltas),
            'equal_error_scenes': sum(x == 0 for x in deltas)}

def room_summaries(rows, metric='text'):
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r['room']].append(r)
    rooms = {k: paired(v, metric) for k, v in sorted(groups.items())}
    valid = [r for r in rooms.values() if r['paired_scenes']]
    return {'rooms': rooms,
            'equal_room_O0_wer': float(np.mean([r['O0']['wer'] for r in valid])) if valid else None,
            'equal_room_O1_wer': float(np.mean([r['O1']['wer'] for r in valid])) if valid else None,
            'equal_room_delta_pp': float(np.mean([r['O1_minus_O0_wer_pp'] for r in valid])) if valid else None}

def uncertainty(rows, dependency, replicates=2000, seed=20260909):
    """Whole matched blocks resampled within observed rooms, never words/frames."""
    rowmap = {r['case_id']: r for r in rows}
    blocks_by_room = collections.defaultdict(list)
    covered = []
    for block in dependency['blocks']:
        ids = [c for c in block['primary_scene_ids'] if c in rowmap]
        if not ids:
            continue
        members = [rowmap[c] for c in ids]
        assert all(r['room'] == block['room_table'] for r in members), 'Matched group crosses room'
        summary = paired(members)
        assert summary['paired_scenes'] == len(ids)
        blocks_by_room[block['room_table']].append([summary['O0']['errors'], summary['O1']['errors'], summary['O0']['reference_words']])
        covered.extend(ids)
    assert len(covered) == len(set(covered)) == len(rows), 'Every primary scene appears in exactly one matched block'
    rng = np.random.default_rng(seed)
    totals = np.zeros((replicates, 3), dtype=np.int64)
    block_counts = {}
    for room in sorted(blocks_by_room):
        block = np.asarray(blocks_by_room[room], dtype=np.int64)
        block_counts[room] = len(block)
        picks = rng.integers(0, len(block), size=(replicates, len(block)))
        totals += block[picks].sum(axis=1)
    delta = 100 * (totals[:, 1] - totals[:, 0]) / totals[:, 2]
    interval = [float(x) for x in np.percentile(delta, [2.5, 97.5])]
    actual = paired(rows)
    lroo = {room: paired([r for r in rows if r['room'] != room]) for room in sorted(blocks_by_room)}
    components = dependency['dependency_diagnostics']['speaker']['primary_components']
    # Component records can contain scene_ids; accept the documented list form too.
    ids_per_component = [c['scene_ids'] if isinstance(c, dict) else c for c in components]
    leave_speaker = []
    for i, ids in enumerate(ids_per_component):
        excluded = set(ids)
        kept = [r for r in rows if r['case_id'] not in excluded]
        leave_speaker.append({'component_index': i, 'excluded_scenes': len(excluded & set(rowmap)),
                              'remaining': paired(kept)})
    practical = []
    for threshold in (.5, 1, 2):
        practical.append({'threshold_absolute_wer_pp': threshold,
            'point_inside_practical_band': abs(actual['O1_minus_O0_wer_pp']) < threshold,
            'conditional_interval_entirely_inside_band': interval[0] > -threshold and interval[1] < threshold,
            'conditional_interval_entirely_favors_O0_beyond_threshold': interval[0] > threshold,
            'conditional_interval_entirely_favors_O1_beyond_threshold': interval[1] < -threshold,
            'interpretation': 'Planning sensitivity only; conditional interval ignores remaining cross-block dependencies and cannot certify population equivalence'})
    return {'replicates': replicates, 'seed': seed, 'matched_block_count': sum(block_counts.values()),
            'matched_blocks_by_room': block_counts, 'primary': actual,
            'paired_O1_minus_O0_wer_pp_percentile95': interval,
            'bootstrap_delta_pp': delta.tolist(),
            'resampling_scope': 'Whole explicit matched blocks within four observed development rooms. Shared people/text/books/RIR/noise cross blocks; interval is conditional and potentially optimistic.',
            'all_dependency_component_sizes': dependency['all_dependencies_primary_component_sizes'],
            'room': room_summaries(rows), 'leave_one_room_out': lroo,
            'leave_one_speaker_component_out': leave_speaker,
            'speaker_sensitivity_scope': 'Descriptive deletion of speaker-linked components; small number and uneven size preclude broad independence/CI claims',
            'practical_difference_sensitivity': practical,
            'nonsignificance_means_equivalence': False}
