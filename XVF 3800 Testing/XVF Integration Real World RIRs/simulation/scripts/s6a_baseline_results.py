"""Read-only all-240 S6A baseline aggregation. See README_S6A_BASELINE_RESULTS.md."""
from __future__ import annotations
import argparse
import collections
import copy
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from s5_statistics import paired, room_summaries
from s5_results import aggregate_support, compact_text, distribution, strata, strict_summary, write_csv
from s5_coverage import components
from s4_geometry import source_label

SIM = Path(__file__).resolve().parent.parent
DEFAULT_REPORT = SIM / 'reports/S6A/20260909T202250Z'
BANK = SIM / 'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json'
RIR = SIM / 'rir_library/v1/RIR_MANIFEST.json'
BANK_SHA = '69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18'
RIR_SHA = '468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546'
EXCLUDED_RIR = 'JPXVF_P1_R02_T01_D01_S02_F00_NAT_CU_R13'
EXPECTED = {'primary_nonoverlap': 156, 'overlap_complete': 47, 'ambient_incomplete': 26, 'strict_empty': 11}
STREAMS = ('O0', 'O1')

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

class Inputs:
    """Snapshot small JSON metadata; deliberately never opens audio, models or arrays."""
    def __init__(self):
        self.bindings = {}
    def bind(self, path, expected=None):
        path = Path(path).resolve()
        assert path.suffix.lower() in {'.json', '.py', '.md'}, path
        raw = path.read_bytes()
        b = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        assert expected is None or b['sha256'] == expected, 'Input hash mismatch: ' + str(path)
        old = self.bindings.get(str(path))
        assert old is None or old == b, 'Input changed during aggregation: ' + str(path)
        self.bindings[str(path)] = b
        return b
    def read(self, path, expected=None):
        b = self.bind(path, expected)
        value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        self.bind(path, b['sha256'])
        return value

def population(scene):
    if not scene['all_speaker_reference_complete']:
        return 'ambient_incomplete'
    utterances = [s for s in scene['segments'] if s['kind'] == 'utterance']
    assert scene['transcript_valid']
    if not utterances:
        assert not scene['overlap_intervals']
        assert all(s['strict_nonspeech_eligible'] for s in scene['segments'] if s['kind'] == 'real_noise')
        return 'strict_empty'
    assert all(s['transcript'].strip() for s in utterances)
    return 'overlap_complete' if scene['overlap_intervals'] else 'primary_nonoverlap'

def dependency_plan(scenes, sources):
    primary = {c for c, s in scenes.items() if population(s) == 'primary_nonoverlap'}
    matched = collections.defaultdict(set)
    dependencies = {k: collections.defaultdict(set) for k in ('speaker', 'source_clip', 'prompt', 'book', 'rir', 'noise_parent')}
    for cid, scene in scenes.items():
        for key in ('matched_pair_id', 'matched_group_id'):
            if scene.get(key):
                matched[(key, scene[key])].add(cid)
        for seg in scene['segments']:
            dependencies['rir'][seg['rir_id']].add(cid)
            if seg['kind'] == 'utterance':
                src = sources[seg['source_id']]
                for kind, key in (('speaker', 'identity'), ('source_clip', 'source_id'), ('prompt', 'prompt_group'), ('book', 'parent_book')):
                    if src.get(key):
                        dependencies[kind][src[key]].add(cid)
            elif seg['kind'] == 'real_noise':
                dependencies['noise_parent'][seg['parent_id']].add(cid)
    groups = components(matched.values(), scenes)
    block_for = {c: 'MATCHED_' + g[0] for g in groups for c in g}
    blocks = []
    for g in groups:
        rooms = sorted({scenes[c]['receiver_configuration']['room_table'] for c in g})
        assert len(rooms) == 1, 'Explicit matched block crosses rooms'
        blocks.append({'block_id': block_for[g[0]], 'scene_ids': g, 'room_table': rooms[0],
                       'primary_scene_ids': sorted(set(g) & primary)})
    projected = [b['primary_scene_ids'] for b in blocks if b['primary_scene_ids']]
    diagnostics = {}
    for kind, gs in dependencies.items():
        joined = components(projected + list(gs.values()), primary)
        diagnostics[kind] = {'all240_group_count': len(gs),
            'groups_crossing_explicit_matched_blocks': sum(len({block_for[c] for c in ids}) > 1 for ids in gs.values()),
            'primary_components': [{'component_id': kind.upper() + '_' + g[0], 'scene_ids': g} for g in joined],
            'primary_component_sizes': sorted(map(len, joined), reverse=True)}
    all_components = components(projected + [g for gs in dependencies.values() for g in gs.values()], primary)
    return {'schema': 'jp_s6a_all240_dependencies_v1', 'requested_scenes': len(scenes), 'requested_primary_scenes': len(primary),
        'blocks': blocks, 'all_scene_matched_blocks': len(blocks), 'primary_matched_blocks': len(projected),
        'primary_blocks_by_room': dict(collections.Counter(b['room_table'] for b in blocks if b['primary_scene_ids'])),
        'dependency_diagnostics': diagnostics, 'all_dependencies_primary_component_sizes': sorted(map(len, all_components), reverse=True),
        'scope': 'All 240 scenes authorized by S6A; original split labels are historical metadata, not a new held-out test.'}

def valid_pair(row, metric='text'):
    return all((row.get(s) or {}).get(metric, {}).get('word_counts', {}).get('reference_words', 0) > 0 for s in STREAMS)

def conditional_uncertainty(rows, dependency, replicates=2000, seed=20260909):
    """Drop whole primary block if ANY requested primary member is missing; never shrink it."""
    rowmap = {r['case_id']: r for r in rows}
    by_room = collections.defaultdict(list)
    included, excluded = [], []
    for block in dependency['blocks']:
        ids = block['primary_scene_ids']
        if not ids:
            continue
        missing = [c for c in ids if c not in rowmap or not valid_pair(rowmap[c])]
        if missing:
            excluded.append({'block_id': block['block_id'], 'room': block['room_table'],
                             'excluded_primary_scene_ids': ids, 'missing_or_unscorable_scene_ids': missing})
            continue
        members = [rowmap[c] for c in ids]
        assert all(r['room'] == block['room_table'] for r in members)
        stats = paired(members)
        assert stats['paired_scenes'] == len(ids)
        by_room[block['room_table']].append([stats['O0']['errors'], stats['O1']['errors'], stats['O0']['reference_words']])
        included.extend(ids)
    requested = [c for b in dependency['blocks'] for c in b['primary_scene_ids']]
    excluded_ids = [c for b in excluded for c in b['excluded_primary_scene_ids']]
    assert len(requested) == len(set(requested))
    assert set(included).isdisjoint(excluded_ids)
    assert set(included) | set(excluded_ids) == set(requested)
    kept = [rowmap[c] for c in included]
    rng = np.random.default_rng(seed)
    totals = np.zeros((replicates, 3), dtype=np.int64)
    for room, blocks in sorted(by_room.items()):
        a = np.asarray(blocks, dtype=np.int64)
        totals += a[rng.integers(0, len(a), size=(replicates, len(a)))].sum(axis=1)
    delta = 100 * (totals[:, 1] - totals[:, 0]) / totals[:, 2] if kept else np.asarray([])
    interval = [float(x) for x in np.percentile(delta, [2.5, 97.5])] if len(delta) else None
    point = paired(kept)
    sensitivity = {}
    for kind, diagnostic in dependency['dependency_diagnostics'].items():
        records = []
        for component in diagnostic['primary_components']:
            removed = set(component['scene_ids'])
            records.append({'component_id': component['component_id'],
                'excluded_scenes': len(removed & set(included)),
                'remaining': paired([r for r in kept if r['case_id'] not in removed])})
        sensitivity[kind] = records
    bands = []
    for threshold in (.5, 1., 2.):
        bands.append({'absolute_wer_pp': threshold,
            'point_inside': abs(point['O1_minus_O0_wer_pp']) < threshold if kept else None,
            'conditional_interval_inside': interval[0] > -threshold and interval[1] < threshold if interval else None,
            'interval_favors_O0_beyond': interval[0] > threshold if interval else None,
            'interval_favors_O1_beyond': interval[1] < -threshold if interval else None})
    return {'replicates': replicates, 'seed': seed, 'requested_primary_scenes': len(requested),
        'included_primary_scenes': len(included), 'excluded_whole_blocks': excluded,
        'whole_block_policy': 'Every primary member and both taps move together. Any missing/unscorable primary pair excludes its entire primary block and remains listed.',
        'observed_rooms': len(by_room), 'matched_blocks_by_room': {k: len(v) for k, v in sorted(by_room.items())},
        'matched_block_count': sum(map(len, by_room.values())), 'primary_on_included_blocks': point,
        'paired_O1_minus_O0_wer_pp_percentile95': interval, 'bootstrap_delta_pp': delta.tolist(),
        'room': room_summaries(kept),
        'leave_one_room_out': {room: paired([r for r in kept if r['room'] != room]) for room in sorted(by_room)},
        'dependency_component_deletion': sensitivity,
        'all_dependencies_primary_component_sizes': dependency['all_dependencies_primary_component_sizes'],
        'practical_difference_sensitivity': bands,
        'resampling_scope': f'Whole explicit matched blocks within {len(by_room)} observed rooms. Shared speakers, clips, text, books, RIR and noise cross blocks; interval is conditional and potentially optimistic.',
        'speaker_sensitivity_scope': 'Delete speaker-connected components while retaining all their matched-block members; descriptive only with few uneven components.',
        'nonsignificance_means_equivalence': False, 'independent_holdout': False}

def paired_with_cer(rows, metric='text'):
    value = paired(rows, metric)
    eligible = [r for r in rows if valid_pair(r, metric)]
    for stream in STREAMS:
        counts = [r[stream][metric].get('character_counts') for r in eligible]
        counts = [c for c in counts if c and c.get('reference_characters', 0) > 0]
        total = {k: sum(c[k] for c in counts) for k in ('errors', 'substitutions', 'deletions', 'insertions', 'reference_characters', 'hypothesis_characters')}
        value[stream]['character_counts'] = total if counts else None
        value[stream]['character_scored_scenes'] = len(counts)
        value[stream]['cer'] = total['errors'] / total['reference_characters'] if total['reference_characters'] else None
    if all(value[s]['cer'] is not None for s in STREAMS):
        assert value['O0']['character_counts']['reference_characters'] == value['O1']['character_counts']['reference_characters']
        value['O1_minus_O0_cer_pp'] = 100 * (value['O1']['cer'] - value['O0']['cer'])
    return value

def geometry_audit(bank, rir):
    records = {r['run_id']: r for r in rir['records']}
    eligible = {k: r for k, r in records.items() if r['can_proceed_to_hil_proof']}
    assert len(records) == 121 and len(eligible) == 120 and EXCLUDED_RIR not in eligible
    assert all(r['capture_audit_pass'] and r['offline_extraction_checks_pass'] for r in eligible.values())
    rows, corrections = [], []
    selected = bank['selected_rirs']
    for rid, record in sorted(records.items()):
        g = record['geometry']
        distance = g['source_distance_m_effective']
        angle = g['speaker_angle_deg_effective']
        assert math.isfinite(distance) and 0 < distance <= 5 and math.isfinite(angle)
        assert record['original_acquisition_status'].upper() in {'PASS', 'REVIEW'}
        projected = source_label(angle, uncertainty_deg=5)
        if g['geometry_correction_applied']:
            corrections.append({'rir_id': rid, 'distance_original_m': g['source_distance_m_original'],
                                'distance_effective_m': distance, 'angle_original_deg': g['speaker_angle_deg_original'],
                                'angle_effective_deg': angle, 'binding': g['distance_binding']})
        if rid in selected:
            assert rid in eligible
            saved = selected[rid]['geometry']
            for key, value in g.items():
                assert saved[key] == value, f'Selected RIR geometry differs: {rid}/{key}'
            assert saved['active_angle_label'] == projected, 'Nominal folded projection changed: ' + rid
            assert selected[rid]['file']['sha256'] == record['output']['sha256']
        rows.append({'rir_id': rid, 'eligible': rid in eligible, 'used_all240': rid in selected,
                     'room': g['room_table'], 'orientation': g['orientation'], 'obstructed': g['obstructed'],
                     'distance_original_m': g['source_distance_m_original'], 'distance_effective_m': distance,
                     'angle_original_deg': g['speaker_angle_deg_original'], 'angle_effective_deg': angle,
                     'expected_native_nominal_deg': projected['expected_native_nominal_deg'],
                     'expected_native_interval_deg': projected['expected_native_interval_deg']})
    used = {s['rir_id'] for scene in bank['scenes'] for s in scene['segments']}
    assert used == set(selected)
    for scene in bank['scenes']:
        receiver = scene['receiver_configuration']
        for seg in scene['segments']:
            g = records[seg['rir_id']]['geometry']
            for field in ('room_table', 'recorder_position', 'orientation', 'obstructed'):
                assert receiver[field] == g[field], f'Room/receiver mismatch: {scene["case_id"]}/{field}'
    rooms = sorted({r['room'] for r in rows})
    return {'status': 'PASS_METADATA_CONSISTENCY', 'canonical_records': len(records), 'eligible_records': len(eligible),
        'used_rirs': len(used), 'eligible_unused_rirs': len(eligible) - len(used), 'excluded_rir': EXCLUDED_RIR,
        'effective_distance_m': distribution(r['distance_effective_m'] for r in rows if r['eligible']),
        'eligible_over_5m': 0, 'source_angle_signs_changed_in_selected_projection': 0,
        'corrections_preserved': corrections,
        'by_room': {room: {'eligible': sum(r['eligible'] and r['room'] == room for r in rows),
                          'used': sum(r['used_all240'] and r['room'] == room for r in rows)} for room in rooms},
        'rows': rows, 'scope': 'Metadata and retained file-hash consistency, not a fresh waveform/acoustic revalidation. PASS/REVIEW only; no retake/testing records admitted.',
        'angle_limits': 'Signed lab angles remain unchanged. Native acos(-sin(lab)) spans 0..180 degrees, folds front/back, and is not circular. Manual +/-5-degree intervals are label uncertainty, not measured device accuracy or independent sign calibration.',
        'distance_limits': 'The two recorded 100 m typos retain raw values and user-confirmed effective 1.00 m overlays. Bulk RIR delay is inseparable: do not add distance/c.'}

def fixtures():
    def row(cid, e0, e1):
        return {'case_id': cid, 'room': 'R', **{s: {'text': {'word_counts': {'errors': e, 'substitutions': e, 'deletions': 0, 'insertions': 0, 'reference_words': 10, 'hypothesis_words': 10}}} for s, e in [('O0', e0), ('O1', e1)]}}
    rows = [row('a', 1, 2), row('b', 4, 1), row('c', 0, 0)]
    d = {'blocks': [{'block_id': 'ab', 'primary_scene_ids': ['a', 'b'], 'room_table': 'R'}, {'block_id': 'c', 'primary_scene_ids': ['c'], 'room_table': 'R'}],
         'dependency_diagnostics': {}, 'all_dependencies_primary_component_sizes': [3]}
    whole = conditional_uncertainty(rows, d, 50)
    assert whole['included_primary_scenes'] == 3 and whole['primary_on_included_blocks']['O1_minus_O0_errors'] == -2
    missing = copy.deepcopy(rows)
    missing[1]['O1'] = None
    dropped = conditional_uncertainty(missing, d, 50)
    assert dropped['included_primary_scenes'] == 1 and dropped['excluded_whole_blocks'][0]['excluded_primary_scene_ids'] == ['a', 'b']
    for lab, expected in [(-90, 0), (0, 90), (90, 180), (180, 90)]:
        assert math.isclose(source_label(lab, uncertainty_deg=5)['expected_native_nominal_deg'], expected, abs_tol=1e-10)
    empty = {'O0': {'text': {'empty_reference_insertions': 2}, 'decoded_duration_s': 60}}
    es = strict_summary([empty], 'O0')
    assert es['wer'] is None and es['words_per_decoded_minute'] == 2
    return {'status': 'PASS', 'checks': ['paired counted errors', 'missing member excludes whole primary block', 'folded angle endpoints/no 0-180 wrap', 'strict-empty insertion rate without WER']}

def load_metadata(ev):
    bank = ev.read(BANK, BANK_SHA)
    rir = ev.read(RIR, RIR_SHA)
    scenes = {s['case_id']: s for s in bank['scenes']}
    assert len(scenes) == len(bank['scenes']) == 240
    assert dict(collections.Counter(population(s) for s in scenes.values())) == EXPECTED
    assert collections.Counter(s['split'] for s in scenes.values()) == {'development': 180, 'reserve': 60}
    return bank, rir, scenes

def aggregate(report, *, require_complete=False, prepare_only=False, plots=False):
    out = report / 'baseline_results'
    ev = Inputs()
    bank, rir, scenes = load_metadata(ev)
    dependency = dependency_plan(scenes, bank['selected_sources'])
    geometry = geometry_audit(bank, rir)
    save(out / 'FIXTURES.json', fixtures())
    save(out / 'DEPENDENCY_PLAN.json', dependency)
    save(out / 'RIR_GEOMETRY_AUDIT.json', geometry)
    if prepare_only:
        save(out / 'PREPARATION_RECEIPT.json', {'status': 'METADATA_AND_FIXTURES_PASS', 'inputs': list(ev.bindings.values()),
                                              'task_metrics_read': 0, 'inference_calls': 0})
        return {'status': 'METADATA_AND_FIXTURES_PASS'}
    jm = ev.read(report / 'JOB_MANIFEST.json')
    receipt = ev.read(report / 'BASELINE_SCORE_RECEIPT.json')
    jobs = jm['jobs']
    assert len(jobs) == len({(j['case_id'], j['stream']) for j in jobs}) == 480
    assert {(j['case_id'], j['stream']) for j in jobs} == {(c, s) for c in scenes for s in STREAMS}
    if require_complete:
        assert receipt['status'] == 'COMPLETE' and receipt['complete'] == 480, 'Full 480-score receipt required'
    score_rows = {(r['case_id'], r['stream']): r for r in receipt['rows']}
    assert len(score_rows) == 480
    rows = {c: {'case_id': c, 'population': population(scene), 'historical_split': scene['split'],
                **strata(scene), 'O0': None, 'O1': None} for c, scene in sorted(scenes.items())}
    support_values, coverage, costs, bindings = {}, [], [], []
    for job in jobs:
        cid, stream = job['case_id'], job['stream']
        sr = score_rows[(cid, stream)]
        state = sr['status']
        wrapper = Path(job['report_dir']) / 'run_receipt.json'
        native_state = ev.read(wrapper).get('status') if wrapper.exists() else 'PENDING_OR_UNAVAILABLE'
        cr = {'case_id': cid, 'stream': stream, 'population': rows[cid]['population'], 'historical_split': rows[cid]['historical_split'],
              'score_status': state, 'native_wrapper_status': native_state, 'reused_prior': bool(job.get('reuse')),
              'scored': False, 'result': None}
        coverage.append(cr)
        if state not in {'COMPLETE', 'COMPLETE_REUSED_SCORE'}:
            continue
        b = sr['result']
        value = ev.read(b['path'], b['sha256'])
        assert value['case_id'] == cid and value['stream'] == stream
        assert value['analysis_identity']['job_key'] == job['job_key']
        assert value['population'] == rows[cid]['population']
        assert value['gain'] == {'O0': 1.4125375446227544, 'O1': 1.0}[stream]
        assert value['adapter']['gain_scalar'] == value['gain']
        assert value['native_completion']['native_summary'] and value['native_completion']['unique_completion_event']
        assert value['native_completion']['exact_full_pcm16_samples'] == value['adapter']['samples']
        assert value['support_metrics']['decoded_samples'] == value['adapter']['samples']
        rows[cid][stream] = compact_text(value['text_metrics'])
        support_values[(cid, stream)] = value['support_metrics']
        cr.update(scored=True, result=b, prior_s5_parity=value['prior_s5_parity'],
                  fresh_s6_native=value['fresh_s6_native'])
        bindings.append(b)
        wall = value.get('model_wall_s')
        duration = value['adapter']['duration_s']
        sm = value['support_metrics']
        costs.append({'case_id': cid, 'stream': stream, 'historical_split': value['historical_split'],
            'origin': 'fresh_s6_native' if value['fresh_s6_native'] else 'prior_native_reused',
            'model_wall_s': wall, 'decoded_duration_s': duration,
            'desktop_whole_process_wall_per_audio': wall / duration if wall is not None and duration else None,
            'embedding_calls': sm['successful_embedding_calls'], 'unique_evidence_audio_s': sm['unique_evidence_audio_s'],
            'processed_embedding_window_s': sm['total_processed_window_s'],
            'processed_window_to_unique_evidence_ratio': sm['total_processed_window_s'] / sm['unique_evidence_audio_s'] if sm['unique_evidence_audio_s'] else None,
            'adapter_gain_scalar': value['gain'], 'adapter_journal_clip_input_samples': value['adapter']['journal_clip_input_samples'],
            'raw_source_rail_samples': value['adapter']['source_rail_samples']})
    assert len(support_values) == receipt['complete']
    if require_complete:
        assert len(support_values) == 480
    values = list(rows.values())
    grouped = {p: [r for r in values if r['population'] == p] for p in EXPECTED}
    primary = grouped['primary_nonoverlap']
    support, turns, returns, regions, shorts = aggregate_support(values, support_values)
    uncertainty = conditional_uncertainty(primary, dependency)
    historical = {}
    for label in ('development', 'reserve'):
        rr = [r for r in values if r['historical_split'] == label]
        historical[label] = {'requested_scenes': len(rr), 'population_counts': dict(collections.Counter(r['population'] for r in rr)),
            'primary': paired_with_cer([r for r in rr if r['population'] == 'primary_nonoverlap']),
            'overlap_mimo': paired_with_cer([r for r in rr if r['population'] == 'overlap_complete'], 'overlap_mimo'),
            'strict_empty': {s: strict_summary([r for r in rr if r['population'] == 'strict_empty'], s) for s in STREAMS},
            'scope': 'Historical original180/former60 descriptive contrast; different allocated sources/rooms/case mix, no independent holdout or split-causal claim.'}
    strata_rows = []
    for pop, metric in [('primary_nonoverlap', 'text'), ('overlap_complete', 'overlap_mimo'), ('ambient_incomplete', 'target_only_text')]:
        rr = grouped[pop]
        for field in ('room', 'family_id', 'corpus', 'quality_partition', 'pose', 'obstructed', 'real_noise',
                      'relative_scene_db', 'relative_utterance_db', 'requested_noise_snr_db', 'requested_speech_sir_db', 'common_headroom_scalar'):
            for val in sorted({r[field] for r in rr}, key=str):
                subset = [r for r in rr if r[field] == val]
                summary = paired_with_cer(subset, metric)
                strata_rows.append({'population': pop, 'metric': metric, 'dimension': field, 'stratum': val,
                    'requested_scenes': len(subset), 'paired_scenes': summary['paired_scenes'],
                    'O0_errors': summary['O0']['errors'], 'O1_errors': summary['O1']['errors'],
                    'reference_words': summary['O0']['reference_words'],
                    'O0_wer': summary['O0']['wer'], 'O1_wer': summary['O1']['wer'],
                    'O0_cer': summary['O0']['cer'], 'O1_cer': summary['O1']['cer'],
                    'delta_O1_minus_O0_wer_pp': summary['O1_minus_O0_wer_pp']})
    cost_summary = {}
    for origin in ('ALL', 'fresh_s6_native', 'prior_native_reused'):
        subset = [r for r in costs if origin == 'ALL' or r['origin'] == origin]
        cost_summary[origin] = {s: {'outputs': len(ss := [r for r in subset if r['stream'] == s]),
            'whole_process_model_wall_s_sum': sum(r['model_wall_s'] for r in ss if r['model_wall_s'] is not None),
            'whole_process_model_wall_s_distribution': distribution(r['model_wall_s'] for r in ss),
            'desktop_wall_per_audio_distribution': distribution(r['desktop_whole_process_wall_per_audio'] for r in ss),
            'embedding_calls': sum(r['embedding_calls'] for r in ss),
            'unique_evidence_audio_s': sum(r['unique_evidence_audio_s'] for r in ss),
            'processed_embedding_window_s': sum(r['processed_embedding_window_s'] for r in ss),
            'journal_clip_input_samples': sum(r['adapter_journal_clip_input_samples'] for r in ss)} for s in STREAMS}
    stats = {'schema': 'jp_s6a_all240_baseline_results_v1',
        'status': 'COMPLETE_480_BASELINE' if len(support_values) == 480 else 'PARTIAL_DIAGNOSTIC',
        'requested_scenes': 240, 'requested_outputs': 480, 'scored_outputs': len(support_values),
        'population_counts': EXPECTED, 'scored_output_counts_by_population': dict(collections.Counter(r['population'] for r in coverage if r['scored'])),
        'missing_or_failed_outputs': [r for r in coverage if not r['scored']],
        'prior_s5_exact_parity_outputs': sum(r.get('prior_s5_parity') == 'EXACT_S5_NUMERIC_AND_POPULATION_PARITY' for r in coverage),
        'primary': paired_with_cer(primary),
        'overlap_mimo': paired_with_cer(grouped['overlap_complete'], 'overlap_mimo'),
        'complete_reference_cpwer': paired_with_cer(grouped['primary_nonoverlap'] + grouped['overlap_complete'], 'attributed_cpwer'),
        'primary_cpwer': paired_with_cer(grouped['primary_nonoverlap'], 'attributed_cpwer'),
        'overlap_cpwer': paired_with_cer(grouped['overlap_complete'], 'attributed_cpwer'),
        'ambient_target_only_limited': paired_with_cer(grouped['ambient_incomplete'], 'target_only_text'),
        'strict_empty': {s: strict_summary(grouped['strict_empty'], s) for s in STREAMS},
        'historical180_former60_descriptive': historical,
        'primary_room': room_summaries(primary),
        'cost': cost_summary,
        'metric_limits': ['Primary WER/CER use pooled native-text edit counts; punctuation display is excluded.',
                          'Overlapping speech uses MIMO-WER separately. cpWER is final-label snapshot and not online revision-aware DER.',
                          'Incomplete ambient transcripts are target-only diagnostics, not complete speech WER and never pooled with primary.',
                          'Empty controls have insertion counts/minutes; WER is undefined.',
                          'Short-turn flags and contained embeddings are temporal proxies, not word recognition or verified speaker identity.',
                          'Component boundaries use frozen source support; unknown ambient speech is not relabeled silence.',
                          'Unique embedding evidence is interval union within each output; summing outputs is workload, not independent acoustic evidence.',
                          'Desktop whole-process wall measurements include startup and historic host contention; no conversion to CM5 RTF.',
                          'All240 are now authorized and observed; former60 are not an unseen held-out confirmation.']}
    delta = stats['primary']['O1_minus_O0_wer_pp']
    stats['conditional_output_preference'] = {'baseline_text_favored_output': None if delta is None or delta == 0 else ('O0' if delta > 0 else 'O1'),
        'primary_O1_minus_O0_wer_pp': delta, 'conditional95_wer_pp': uncertainty['paired_O1_minus_O0_wer_pp_percentile95'],
        'scope': 'This fixed bank, fixed B0, O0 +3 dB once/O1 unity, pooled primary text counts. Conditional descriptive preference only; no device-wide superiority, unseen-room generalization, or final jointly tuned choice.'}
    save(out / 'BASELINE_RESULTS.json', stats)
    save(out / 'PAIRED_UNCERTAINTY.json', uncertainty)
    save(out / 'SUPPORT_RESULTS.json', support)
    save(out / 'SCENE_METRICS_COMPACT.json', values)
    for name, data in [('COVERAGE', coverage), ('STRATIFIED_TEXT', strata_rows), ('COST', costs),
                       ('SHORT_TURNS', shorts), ('RETURN_GROUPS', returns), ('TURN_SUPPORT', turns), ('REGION_SUPPORT', regions)]:
        write_csv(out / (name + '.csv'), data)
    write_csv(out / 'RIR_GEOMETRY.csv', geometry['rows'])
    if plots:
        make_plot(out, stats)
    write_report(out, stats, support, uncertainty, geometry, shorts)
    for source in ('s6a_baseline_results.py', 's5_statistics.py', 's5_results.py', 's5_coverage.py', 's4_geometry.py'):
        ev.bind(SIM / 'scripts' / source)
    ev.bind(SIM / 'scripts/README_S6A_BASELINE_RESULTS.md')
    ev.bind(report / 'BASELINE_SCORE_RECEIPT.json')  # detect changes during read/aggregation
    outputs = []
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != 'AGGREGATION_RECEIPT.json':
            raw = path.read_bytes()
            outputs.append({'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    save(out / 'AGGREGATION_RECEIPT.json', {'status': stats['status'], 'utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'requested_outputs': 480, 'scored_outputs': len(support_values), 'inputs': list(ev.bindings.values()), 'outputs': outputs,
        'inference_calls': 0, 'audio_or_model_payloads_opened': 0, 'workers': 1,
        'raw_sources_modified': False, 'figures': 1 if plots else 0})
    return {k: stats[k] for k in ('status', 'scored_outputs', 'prior_s5_exact_parity_outputs', 'conditional_output_preference')}

def make_plot(out, stats):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rooms = stats['primary_room']['rooms']
    data = [{'room': k, 'scenes': v['paired_scenes'], 'reference_words': v['O0']['reference_words'],
             'O0_wer_percent': 100 * v['O0']['wer'] if v['O0']['wer'] is not None else None,
             'O1_wer_percent': 100 * v['O1']['wer'] if v['O1']['wer'] is not None else None} for k, v in rooms.items()]
    save(out / 'FIGURE_DATA.json', {'figure': 'baseline_room_and_empty.png', 'rooms': data,
        'strict_empty': stats['strict_empty'], 'scope': 'Descriptive paired counts. No room error bars or assumed independent scenes.'})
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 5), gridspec_kw={'width_ratios': [2.2, 1]})
    ax = axes[0]
    for i, row in enumerate(data):
        if row['O0_wer_percent'] is None:
            continue
        ax.plot([row['O0_wer_percent'], row['O1_wer_percent']], [i, i], color='#8b959e', zorder=1)
        ax.scatter(row['O0_wer_percent'], i, color='#166a9c', label='O0 +3 dB' if i == 0 else None, zorder=2)
        ax.scatter(row['O1_wer_percent'], i, color='#d17817', marker='s', label='O1 unity' if i == 0 else None, zorder=2)
    ax.set_yticks(range(len(data)), [r['room'] + '\n(n=' + str(r['scenes']) + ', words=' + str(r['reference_words']) + ')' for r in data], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel('Pooled primary WER (%)')
    ax.set_title('Five-room baseline text comparison')
    ax.grid(axis='x', alpha=.2)
    ax.legend(fontsize=8)
    ax = axes[1]
    e = stats['strict_empty']
    ax.bar(STREAMS, [e[s]['words_per_decoded_minute'] or 0 for s in STREAMS], color=['#166a9c', '#d17817'])
    ax.set_ylabel('Inserted words per decoded minute')
    ax.set_title('Strict-empty controls')
    for i, s in enumerate(STREAMS):
        ax.text(i, e[s]['words_per_decoded_minute'] or 0,
                str(e[s]['inserted_words']) + (' word\n' if e[s]['inserted_words'] == 1 else ' words\n') + str(e[s]['controls']) + ' controls', ha='center', va='bottom', fontsize=8)
    ax.margins(y=.25)
    fig.suptitle('S6A original settings: conditional descriptive evidence', fontsize=12)
    fig.tight_layout()
    fig.savefig(out / 'baseline_room_and_empty.png', dpi=180)
    plt.close(fig)

def write_report(out, stats, support, uncertainty, geometry, shorts):
    def pct(v): return 'unavailable' if v is None else f'{100*v:.3f}%'
    p, o, cp = stats['primary'], stats['overlap_mimo'], stats['complete_reference_cpwer']
    preference = stats['conditional_output_preference']
    lines = ['# S6A all-240 original-settings baseline', '',
        f"Status: **{stats['status']}**. Scored {stats['scored_outputs']}/480 requested outputs across 240 scenes; {stats['prior_s5_exact_parity_outputs']} prior S5 outputs retain exact numerical/population parity.", '',
        f"On primary pooled text counts the conditional preference is **{preference['baseline_text_favored_output']}**, with O1 minus O0 WER {p['O1_minus_O0_wer_pp']:.3f} percentage points." if p['O1_minus_O0_wer_pp'] is not None else 'Primary paired preference is unavailable.', '',
        'This describes the fixed bank and original B0 with O0 +3 dB applied once and O1 unity. It does not choose the final jointly tuned pipeline or establish device-wide superiority. All 240 cases are now observed; the original 180/former 60 contrast is descriptive.', '',
        '| Population / metric | Requested scenes | Paired scenes | O0 | O1 | Reference words |',
        '|---|---:|---:|---:|---:|---:|']
    for label, requested, v in [('Primary nonoverlap WER', 156, p), ('Complete overlap MIMO-WER', 47, o), ('Complete-reference final-label cpWER', 203, cp),
                                ('Incomplete ambient target-only WER (limited)', 26, stats['ambient_target_only_limited'])]:
        lines.append(f"| {label} | {requested} | {v['paired_scenes']} | {pct(v['O0']['wer'])} | {pct(v['O1']['wer'])} | {v['O0']['reference_words']} |")
    lines += ['', f"Primary CER: O0 {pct(p['O0']['cer'])}, O1 {pct(p['O1']['cer'])}. Counts, substitutions/deletions/insertions, and per-population diagnostics are in BASELINE_RESULTS.json.", '',
        f"The 2,000-replicate paired bootstrap samples {uncertainty['matched_block_count']} whole matched blocks within {uncertainty['observed_rooms']} observed rooms. Conditional 95% interval for O1 minus O0 WER: {uncertainty['paired_O1_minus_O0_wer_pp_percentile95']} percentage points.",
        f"All-dependency primary component sizes: {uncertainty['all_dependencies_primary_component_sizes']}. Shared people/text/books/RIR/noise connect blocks; this interval can be optimistic. Equal-room means, leave-room-out and each dependency component deletion are explicit in PAIRED_UNCERTAINTY.json. Missing primary members exclude the entire matched block; {len(uncertainty['excluded_whole_blocks'])} blocks excluded.", '',
        '## Empty controls, support, continuity and cost', '',
        '| Tap | Empty inserted words / controls | Words/min | Embedding calls | Unique evidence s | Processed window s | PCM16 rail samples |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for s in STREAMS:
        e, a = stats['strict_empty'][s], support[s]
        rate = e['words_per_decoded_minute']
        lines.append(f"| {s} | {e['inserted_words']} / {e['controls']} | {rate:.3f} | {a['successful_embedding_calls']} | {a['unique_evidence_audio_s']:.3f} | {a['total_processed_window_s']:.3f} | {a['adapter_pcm16_levels']['rail_samples']} |" if rate is not None else f"| {s} | unavailable | unavailable | {a['successful_embedding_calls']} | {a['unique_evidence_audio_s']:.3f} | {a['total_processed_window_s']:.3f} | {a['adapter_pcm16_levels']['rail_samples']} |")
    lines += ['', 'Empty-reference WER is undefined. Short-turn support flags are temporal detection proxies; they do not certify transcript or speaker recognition. SHORT_TURNS.csv retains whole-clip versus active-duration bins, corpus, attribution limits, observed support and misses. RETURN_GROUPS.csv retains consistent/inconsistent/unknown outcomes, with known source schedules used only by evaluation.',
        'SUPPORT_RESULTS.json separates raw and adapter PCM16 levels, headroom/rails, real-noise support, quiet support, overlap, gate reasons and unique-versus-repeated embedding evidence. STRATIFIED_TEXT.csv covers room, family, corpus, quality, pose, obstruction, requested noise/SIR, source level and common headroom. These are uneven descriptive strata, not randomized effects.',
        'COST.csv distinguishes native runs reused from earlier work and fresh S6 native work. Whole-process desktop wall/audio includes process/model startup and historic contention; it is not steady-state inference throughput or a CM5 conversion. Unlogged rejected embedding calls remain unknown.', '',
        '## Geometry and exclusions', '',
        f"{geometry['canonical_records']} canonical RIR records remain bound to the original manifest; {geometry['eligible_records']} are eligible, {geometry['used_rirs']} occur in this scene bank, and {geometry['eligible_unused_rirs']} are unused by this bank. Eligible effective distances span {geometry['effective_distance_m']['min']}–{geometry['effective_distance_m']['max']} m; none exceeds 5 m.",
        'The two 100 m raw-entry typos preserve user-confirmed effective 1.00 m overlays. Selected source angle signs, signed values, room/pose/obstruction and nominal folded projection agree exactly with the canonical metadata. This cannot independently prove that a manual angle was measured with the correct sign. Native 0 and 180 degrees are opposite endpoints; front/back remain ambiguous. Manual ±5 degrees is source-label uncertainty.',
        'RIR_GEOMETRY_AUDIT.json lists every eligible and excluded record and the unmodified historical bindings. No raw recording, RIR or source metadata was rewritten or regenerated.', '',
        '## Interpretation limits', '']
    lines += ['- ' + item for item in stats['metric_limits']]
    lines += ['', '## Reproduction', '', 'See simulation/scripts/README_S6A_BASELINE_RESULTS.md. AGGREGATION_RECEIPT.json binds inputs, code, and outputs. No audio, model payload or embedding vectors are copied into this report.', '']
    (out / 'BASELINE_ANALYSIS.md').write_text('\n'.join(lines), encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=DEFAULT_REPORT)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare-only', action='store_true')
    modes.add_argument('--allow-partial', action='store_true')
    modes.add_argument('--require-complete', action='store_true')
    parser.add_argument('--plots', action='store_true')
    args = parser.parse_args()
    print(json.dumps(aggregate(args.report.resolve(), require_complete=args.require_complete,
                              prepare_only=args.prepare_only, plots=args.plots), ensure_ascii=True))

if __name__ == '__main__':
    main()
