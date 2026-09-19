"""S5 complete-panel numerical analysis; no inference or audio edits. README_S5.md."""
from __future__ import annotations
import argparse
import collections
import copy
import csv
import json
import math
from pathlib import Path
import numpy as np
from s5_common import *
from s5_statistics import paired, room_summaries, uncertainty
from s5_text_panel import resolve_native
from s5_timing_metrics import analyze_timing
from s4_h2_analysis import score_text

def write_csv(path, rows):
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, separators=(',', ':')) if isinstance(v, (dict, list)) else v for k, v in row.items()})

def distribution(values):
    x = np.asarray([v for v in values if v is not None and math.isfinite(float(v))], dtype=float)
    return {'n': len(x), 'min': float(x.min()) if len(x) else None,
            'p10': float(np.percentile(x, 10)) if len(x) else None,
            'median': float(np.median(x)) if len(x) else None,
            'p90': float(np.percentile(x, 90)) if len(x) else None,
            'max': float(x.max()) if len(x) else None,
            'mean': float(x.mean()) if len(x) else None}

def level_pool(rows):
    valid = [r for r in rows if r and r['samples']]
    n = sum(r['samples'] for r in valid)
    energy = sum(r['rms_fs'] ** 2 * r['samples'] for r in valid)
    return {'samples': n, 'pooled_rms_fs': math.sqrt(energy / n) if n else None,
            'per_scene_rms_dbfs': distribution(20 * math.log10(r['rms_fs']) for r in valid if r['rms_fs'] > 0),
            'zero_rms_scenes': sum(r['rms_fs'] == 0 for r in valid),
            'rail_samples': sum(r['rail_samples'] for r in valid),
            'scenes_with_rails': sum(r['rail_samples'] > 0 for r in valid),
            'rail_runs': sum(r['rail_runs'] for r in valid),
            'longest_rail_run_samples': max((r['longest_rail_run_samples'] for r in valid), default=0),
            'peak_fs': max((r['peak_fs'] for r in valid), default=None),
            'scope': 'Pooled measured energy/counts and scene-level distribution on stated support; not target-only SNR'}

def strata(scene):
    utts = [s for s in scene['segments'] if s['kind'] == 'utterance']
    corpora = sorted({s['dataset'] for s in utts})
    quality = sorted({s.get('quality_partition') or 'unspecified' for s in utts})
    def label(v): return 'NONE' if not v else v[0] if len(v) == 1 else 'MIXED: ' + ' + '.join(v)
    return {'room': scene['receiver_configuration']['room_table'],
            'family_id': scene['family_id'], 'family': scene['family'],
            'corpus': label(corpora), 'quality_partition': label(quality),
            'pose': scene['receiver_configuration']['orientation'],
            'obstructed': str(scene['receiver_configuration']['obstructed']),
            'relative_scene_db': str(scene['relative_source_level_db']),
            'relative_utterance_db': label(sorted({str(s['relative_source_db']) for s in utts})),
            'requested_noise_snr_db': str((scene.get('noise_policy') or {}).get('snr_db', 'NONE')),
            'requested_speech_sir_db': str((scene.get('speech_interference_policy') or {}).get('requested_sir_db', 'NONE')),
            'common_headroom_scalar': str(scene['common_family_headroom_scalar']),
            'reference_complete': str(scene['all_speaker_reference_complete']),
            'scheduled_overlap': bool(scene.get('overlap_intervals')),
            'scheduled_speaker_order': [s['speaker_key'] for s in sorted(utts, key=lambda s: s['source_start_sample'])],
            'real_noise': any(s['kind'] == 'real_noise' for s in scene['segments']),
            'speaker_ids': sorted({s['speaker_key'] for s in utts}),
            'source_ids': sorted({s['source_id'] for s in utts}),
            'rir_ids': sorted({s['rir_id'] for s in scene['segments']}),
            'matched_pair_id': scene.get('matched_pair_id'), 'matched_group_id': scene.get('matched_group_id')}

def compact_text(t):
    keys = ('population', 'decoded_duration_s', 'hypothesis_empty', 'reference_complete',
            'reference_speakers', 'reference_utterances', 'final_utterances')
    out = {k: t[k] for k in keys}
    for name in ('text', 'overlap_mimo', 'attributed_cpwer', 'target_only_text'):
        if name in t:
            out[name] = {k: v for k, v in t[name].items() if k not in (
                'reference_normalized', 'hypothesis_normalized', 'assignment', 'normalization', 'hypothesis_labels')}
    return out

def strict_summary(rows, stream):
    texts = [r[stream] for r in rows if r.get(stream)]
    counts = [t['text']['empty_reference_insertions'] for t in texts]
    duration = sum(t['decoded_duration_s'] for t in texts)
    assert all(n is not None for n in counts)
    return {'controls': len(texts), 'inserted_words': sum(counts), 'affected_controls': sum(n > 0 for n in counts),
            'affected_control_fraction': sum(n > 0 for n in counts) / len(counts) if counts else None,
            'decoded_duration_s': duration, 'words_per_decoded_minute': 60 * sum(counts) / duration if duration else None,
            'wer': None, 'scope': 'Strict empty reference only; music vocals=N annotation is not new frame-level certification'}

def return_tags(row, group):
    """Derive return context from frozen reference metadata, never an output."""
    tags = ['returning_person']
    sequence = row['scheduled_speaker_order']
    indices = [i for i, s in enumerate(sequence) if s == group['speaker_key']]
    after_other = any(any(s != group['speaker_key'] for s in sequence[a + 1:b]) for a, b in zip(indices, indices[1:]))
    tags.append('return_after_other_speaker' if after_other else 'repeat_without_intervening_speaker')
    if 'changed_measured_seat' in group['strata']:
        tags.append('changed_measured_seat')
    if row['family_id'] == 'F06':
        tags.append('silent_relocation_or_long_pause_family')
    if row['family_id'] == 'F05':
        tags.append('folded_spatial_contrast_family')
    if row['scheduled_overlap']:
        tags.append('scheduled_overlapping_speech')
    if 'short_reply_present' in group['strata']:
        tags.append('short_reply_present')
    return tags

def failed_empty_sensitivity(primary, scenes, terminal_states):
    hypothetical = copy.deepcopy(primary)
    substitutions = []
    for row in hypothetical:
        for stream in ('O0', 'O1'):
            if row[stream] is not None:
                continue
            state = terminal_states[(row['case_id'], stream)]
            if state not in ('FAILED', 'QUARANTINED'):
                return {'status': 'UNAVAILABLE_PENDING_PRIMARY_JOBS', 'pending_case': row['case_id'], 'stream': stream}
            scene = scenes[row['case_id']]
            reference = ' '.join(s['transcript'] for s in sorted(scene['segments'], key=lambda s: s['source_start_sample']) if s['kind'] == 'utterance')
            row[stream] = {'text': score_text(reference, '', duration_s=scene['duration_s'], overlap=False, transcript_valid=True)}
            substitutions.append({'case_id': row['case_id'], 'stream': stream, 'actual_state': state})
    return {'status': 'IDENTICAL_TO_PRIMARY_NO_FAILED_PRIMARY_JOBS' if not substitutions else 'HYPOTHETICAL_FAILED_OUTPUT_AS_EMPTY',
            'substitutions': substitutions, 'paired': paired(hypothetical),
            'scope': 'Conservative hypothetical full deletion for failed/quarantined primary output; not an observed successful empty decode. No failed job is silently zero error.'}

def shared_noise_summary(support_receipt, guard):
    values, table = [], []
    for row in support_receipt['shared_direction']:
        if not row['noise_events']:
            continue
        cid = row['case_id']
        guard.require(cid, 'shared_noise_direction_aggregate')
        b = row['result']
        bind(b['path'], b['sha256'])
        metric = read(b['path'])['metrics']
        assert metric['case_id'] == cid and metric['physical_trace_evidence_units'] == 1
        assert metric['paired_output_evidence_units'] == 0
        kinds = sorted({n['interpretation'] for n in metric['noise_events']})
        kind = kinds[0] if len(kinds) == 1 else 'MIXED'
        values.append({'case_id': cid, 'interpretation': kind, 'metrics': metric})
        for stream, s in metric['all_noise_union_streams'].items():
            table.append({'case_id': cid, 'interpretation': kind, 'direction_stream': stream,
                          'source_noise_events': len(metric['noise_events']), **s})
    assert len(values) == len({r['case_id'] for r in values}) == 39
    totals = {}
    for kind in ['ALL'] + sorted({v['interpretation'] for v in values}):
        selected = [v for v in values if kind == 'ALL' or v['interpretation'] == kind]
        totals[kind] = {'scenes': len(selected), 'streams': {}}
        for stream in sorted({k for v in selected for k in v['metrics']['all_noise_union_streams']}):
            ss = [v['metrics']['all_noise_union_streams'][stream] for v in selected]
            duration = sum(s['support_duration_s'] for s in ss)
            totals[kind]['streams'][stream] = {'host_noise_support_s': duration,
                'finite_angle_s': sum(s['support_duration_s'] * (s['angle_only_coverage'] or 0) for s in ss),
                'usable_gated_direction_s': sum(s['support_duration_s'] * (s['speech_energy_gated_coverage'] or 0) for s in ss),
                'scope': 'Shared physical telemetry weighted by source-derived noise-active host support; no O0/O1 attribution and no speech-identity proof'}
    return {'source_noise_scenes': len(values), 'shared_physical_trace_units': len(values),
            'paired_output_evidence_units': 0, 'groups': totals,
            'scope': 'Union within scene, sum across independent capture clocks. Unknown speech stays noise-associated; strict designation comes from original source annotation.'}, table

def aggregate_support(rows, support_rows):
    outputs = {}
    turn_rows, return_rows, region_rows = [], [], []
    rowmap = {r['case_id']: r for r in rows}
    for stream in ('O0', 'O1'):
        entries = [(cid, m) for (cid, out), m in support_rows.items() if out == stream]
        metrics = [m for _, m in entries]
        gate = collections.Counter()
        for m in metrics:
            gate.update(m['embedding_gate']['counts'])
        result = {'outputs': len(metrics), 'decoded_samples': sum(m['decoded_samples'] for m in metrics),
                  'successful_embedding_calls': sum(m['successful_embedding_calls'] for m in metrics),
                  'unique_evidence_audio_s': sum(m['unique_evidence_audio_s'] for m in metrics),
                  'total_processed_window_s': sum(m['total_processed_window_s'] for m in metrics),
                  'native_segmentation_events': sum(m['native_segmentation_event_count'] for m in metrics),
                  'gate_counts': dict(gate), 'unlogged_rejected_embedding_calls': None,
                  'unavailable_output_mapping_cases': [cid for cid, m in entries if m['regions'] is None],
                  'raw_levels': level_pool([m['raw_full_output_levels'] for m in metrics]),
                  'adapter_pcm16_levels': level_pool([m['post_adapter_pcm16_full_output_levels'] for m in metrics]),
                  'native_whole_segmentation_counts': dict(sum((collections.Counter(m['native_whole_output_segmentation']) for m in metrics), collections.Counter())),
                  'regions': {}, 'real_noise_regions': {}, 'continuity_by_population': {}, 'by_population': {}}
        result['decoded_s'] = result['decoded_samples'] / 16000
        result['embedding_calls_per_decoded_minute'] = result['successful_embedding_calls'] / (result['decoded_s'] / 60) if result['decoded_s'] else None
        for cid, m in entries:
            row = rowmap[cid]
            cont = m.get('continuity') or {}
            ct = {t['segment_index']: t for t in cont.get('turns', [])}
            for t in m.get('short_turns') or []:
                c = ct.get(t['segment_index'], {})
                turn_rows.append({'case_id': cid, 'stream': stream, 'population': row['population'],
                    'room': row['room'], 'family_id': row['family_id'], **t,
                    'decision_count': c.get('decision_count'), 'missing_evidence': c.get('missing_evidence'),
                    'dominant_tied': c.get('dominant_tied'), 'dominant_label': c.get('dominant_label'),
                    'within_turn_label_switches': c.get('within_turn_label_switches'),
                    'distinct_decision_labels': len(c.get('decision_label_counts', {})),
                    'strict_active_decisions': c.get('strict_active_decisions'),
                    'unique_evidence_samples': c.get('evidence_unique_samples')})
            for g in cont.get('returning_participant_groups', []):
                return_rows.append({'case_id': cid, 'stream': stream, 'population': row['population'],
                                    'family_id': row['family_id'], 'room': row['room'], **g,
                                    'inherited_support_strata': g['strata'], 'strata': return_tags(row, g)})
            for key, region in (m.get('regions') or {}).items():
                region_rows.append({'case_id': cid, 'stream': stream, 'population': row['population'],
                                    'real_noise': row['real_noise'], 'region': key, **region})
        for target, noise_only in (('regions', False), ('real_noise_regions', True)):
            keys = sorted({r['region'] for r in region_rows if r['stream'] == stream and (not noise_only or r['real_noise'])})
            for key in keys:
                rr = [r for r in region_rows if r['stream'] == stream and r['region'] == key and (not noise_only or r['real_noise'])]
                fields = ('support_samples', 'segmentation_observed_samples', 'speech_flag_intersection_samples', 'overlap_flag_intersection_samples')
                v = {k: sum(r[k] for r in rr) for k in fields}
                v.update(scenes=len(rr), scenes_with_nonempty_support=sum(r['support_samples'] > 0 for r in rr),
                         raw_levels=level_pool([r['raw_levels'] for r in rr]),
                         adapter_pcm16_levels=level_pool([r['adapter_pcm16_levels'] for r in rr]))
                v['speech_flag_fraction_of_full_support'] = v['speech_flag_intersection_samples'] / v['support_samples'] if v['support_samples'] else None
                v['speech_flag_fraction_of_observed_support'] = v['speech_flag_intersection_samples'] / v['segmentation_observed_samples'] if v['segmentation_observed_samples'] else None
                result[target][key] = v
        for pop in ('ALL', 'primary_nonoverlap', 'overlap_complete', 'ambient_incomplete', 'strict_empty'):
            mm = [m for cid, m in entries if pop == 'ALL' or rowmap[cid]['population'] == pop]
            whole = dict(sum((collections.Counter(m['native_whole_output_segmentation']) for m in mm), collections.Counter()))
            stats_pop = {'outputs': len(mm), 'decoded_s': sum(m['decoded_duration_s'] for m in mm),
                         'successful_embedding_calls': sum(m['successful_embedding_calls'] for m in mm),
                         'unique_evidence_audio_s': sum(m['unique_evidence_audio_s'] for m in mm),
                         'native_whole_segmentation_counts': whole,
                         'raw_levels': level_pool([m['raw_full_output_levels'] for m in mm]),
                         'adapter_pcm16_levels': level_pool([m['post_adapter_pcm16_full_output_levels'] for m in mm]),
                         'mapped_outputs': sum(m['regions'] is not None for m in mm)}
            stats_pop['native_speech_flag_fraction_decoded'] = whole.get('speech_flag_interval_samples', 0) / whole['decoded_samples'] if whole.get('decoded_samples') else None
            result['by_population'][pop] = stats_pop
            ts = [t for t in turn_rows if t['stream'] == stream and (pop == 'ALL' or t['population'] == pop)]
            gs = [g for g in return_rows if g['stream'] == stream and (pop == 'ALL' or g['population'] == pop)]
            result['continuity_by_population'][pop] = {
                'supported_turns': len(ts), 'turns_without_evidence': sum(t['missing_evidence'] is True for t in ts),
                'dominant_ties': sum(t['dominant_tied'] is True for t in ts),
                'multilabel_turns': sum(t['distinct_decision_labels'] > 1 for t in ts),
                'within_turn_switches': sum(t['within_turn_label_switches'] or 0 for t in ts),
                'strict_active_decisions': sum(t['strict_active_decisions'] or 0 for t in ts),
                'return_groups': len(gs), 'return_classifications': dict(collections.Counter(g['classification'] for g in gs)),
                'return_strata': {s: dict(collections.Counter(g['classification'] for g in gs if s in g['strata']))
                                  for s in sorted({s for g in gs for s in g['strata']})}}
        result['window_crossings'] = dict(sum((collections.Counter((m.get('continuity') or {}).get('window_crossings', {})) for m in metrics), collections.Counter()))
        outputs[stream] = result
    short_rows = []
    for scope in ('ALL', 'single_source_attributable'):
        for clock in ('whole_clip_bin', 'active_duration_bin'):
            for corpus in ('ALL', 'CMU ARCTIC', 'Common Voice', 'HiFiTTS'):
                for bucket in ('<1s', '1-<2s', '>=2s'):
                    for stream in ('O0', 'O1'):
                        subset = [t for t in turn_rows if t['stream'] == stream and t[clock] == bucket
                                  and (corpus == 'ALL' or t['dataset'] == corpus)
                                  and (scope == 'ALL' or t['source_attribution_status'] == 'SINGLE_SCHEDULED_SOURCE_TEMPORAL_PROXY_NOT_RECOGNITION')]
                        short_rows.append({'scope': scope, 'duration_definition': clock, 'corpus': corpus,
                            'duration_bin': bucket, 'stream': stream, 'turn_instances': len(subset),
                            'source_clips': len({t['source_id'] for t in subset}), 'speakers': len({t['speaker_key'] for t in subset}),
                            'observed_turns': sum(t['segmentation_observed_samples'] > 0 for t in subset),
                            'positive_supported_flags': sum(t['detected_supported_flag'] is True for t in subset),
                            'no_positive_on_observed_support': sum(t['no_positive_on_observed_support'] is True for t in subset),
                            'fully_observed_misses': sum(t['missed_supported_flag'] is True for t in subset),
                            'timing_or_attribution_unknown': sum(t['source_specific_supported_detection'] is None for t in subset),
                            'turns_without_contained_embedding': sum(t['missing_evidence'] is True for t in subset),
                            'support_samples': sum(t['support_samples'] for t in subset),
                            'observed_samples': sum(t['segmentation_observed_samples'] for t in subset),
                            'speech_flag_samples': sum(t['speech_flag_intersection_samples'] for t in subset)})
    return outputs, turn_rows, return_rows, region_rows, short_rows

def analyze(*, allow_partial=False):
    m = manifest()
    guard = DevelopmentGuard(m['scenes'], 'aggregate')
    jm = read(REPORT / 'JOB_MANIFEST.json')
    protocol = read(REPORT / 'SCORING_PROTOCOL.json')
    contract = read(REPORT / 'execution_contract.json')
    bind(REPORT / 'SCORING_PROTOCOL.json', contract['scoring_protocol']['sha256'])
    texts = read(REPORT / 'TEXT_PANEL_RECEIPT.json')
    supports = read(REPORT / 'support/SUPPORT_PANEL_RECEIPT.json')
    terminal_states = {}
    for job in jm['jobs']:
        rp = Path(job['report_dir']) / 'run_receipt.json'
        terminal_states[(job['case_id'], job['stream'])] = read(rp)['status'] if rp.exists() else 'PENDING'
    terminal_failures = sum(v in ('FAILED', 'QUARANTINED') for v in terminal_states.values())
    if not allow_partial:
        assert all(v in ('COMPLETE', 'FAILED', 'QUARANTINED') for v in terminal_states.values()), 'Native panel is not terminal'
        assert texts['complete'] == supports['completed_outputs'] == 360 - terminal_failures
    tm = {(r['case_id'], r['stream']): r for r in texts['rows'] if r['status'].startswith('COMPLETE')}
    sm = {(r['case_id'], r['stream']): r for r in supports['rows'] if r['status'] == 'COMPLETE'}
    rows = {cid: {'case_id': cid, 'population': population(guard.scenes[cid]), **strata(guard.scenes[cid]), 'O0': None, 'O1': None}
            for cid in sorted(guard.allowed)}
    support_values, timing_rows, catalogue_inputs, completion_rows = {}, [], {}, []
    for job in jm['jobs']:
        cid, stream = job['case_id'], job['stream']
        scene = guard.require(cid, 'aggregate_task_metrics')
        assert stable_hash(scene) == job['identity']['scene_reference_sha256']
        key = (cid, stream)
        rp = Path(job['report_dir']) / 'run_receipt.json'
        state = read(rp)['status'] if rp.exists() else 'PENDING'
        completion_rows.append({'case_id': cid, 'stream': stream, 'status': state, 'reused': bool(job['reuse']),
                                'attempts': len(list(Path(job['report_dir']).glob('attempt_*/attempt_receipt.json'))),
                                'raw_audio': job['raw_audio'], 'native_wrapper': bind(rp) if rp.exists() else None})
        if key not in tm or key not in sm:
            continue
        tb, sb = tm[key]['output'], sm[key]['result']
        bind(tb['path'], tb['sha256'])
        bind(sb['path'], sb['sha256'])
        t = read(tb['path'])
        s = read(sb['path'])['metrics']
        assert t['case_id'] == s['case_id'] == cid and t['stream'] == s['output'] == stream
        rows[cid][stream] = compact_text(t)
        support_values[key] = s
        catalogue_inputs[key] = t
        native = resolve_native(job, read(rp))
        bind(native['events_binding']['path'], native['events_binding']['sha256'])
        events = [json.loads(x) for x in Path(native['events_binding']['path']).read_text(encoding='utf-8').splitlines() if x.strip()]
        timing = analyze_timing(native, events, scene=scene, development_ids=guard.allowed,
                                origin='reused_s45' if job['reuse'] else 'fresh_s5')
        timing.update(job_key=job['job_key'], native_receipt=bind(job['reuse']['receipt']['path']) if job['reuse'] else bind(rp),
                      timing_code=bind(SIM / 'scripts/s5_timing_metrics.py'))
        save(REPORT / 'timing' / cid / (stream + '.json'), timing)
        timing_rows.append(timing)
    values = list(rows.values())
    primary = [r for r in values if r['population'] == 'primary_nonoverlap']
    overlap = [r for r in values if r['population'] == 'overlap_complete']
    ambient = [r for r in values if r['population'] == 'ambient_incomplete']
    strict = [r for r in values if r['population'] == 'strict_empty']
    complete_primary = [r for r in primary if r['O0'] and r['O1']]
    stats = {'status': 'PARTIAL_DIAGNOSTIC' if allow_partial else 'COMPLETE_PANEL_WITH_FAILURES' if terminal_failures else 'COMPLETE_PANEL',
             'requested_scenes': 180, 'requested_outputs': 360, 'analyzed_outputs': len(support_values),
             'populations': dict(collections.Counter(r['population'] for r in values)),
             'primary': paired(primary), 'overlap_mimo': paired(overlap, 'overlap_mimo'),
             'cpwer_primary': paired(primary, 'attributed_cpwer'),
             'cpwer_overlap': paired(overlap, 'attributed_cpwer'),
             'cpwer_all_complete_speech': paired(primary + overlap, 'attributed_cpwer'),
             'ambient_target_only_LIMITED': paired(ambient, 'target_only_text'),
             'strict_empty': {s: strict_summary(strict, s) for s in ('O0', 'O1')},
             'primary_character_counts': {}, 'primary_empty_hypotheses': {},
             'cpwer_stream_accounting': {}, 'headroom': {}, 'timing': {}, 'strata': [], 'scoring_protocol': bind(REPORT / 'SCORING_PROTOCOL.json')}
    for stream in ('O0', 'O1'):
        chars = collections.Counter()
        for r in complete_primary:
            chars.update(r[stream]['text']['character_counts'])
        stats['primary_character_counts'][stream] = {**chars, 'cer': chars['errors'] / chars['reference_characters'] if chars['reference_characters'] else None}
        stats['primary_empty_hypotheses'][stream] = sum(r[stream]['hypothesis_empty'] for r in complete_primary)
        stats['cpwer_stream_accounting'][stream] = {}
        for pop, group in (('primary_nonoverlap', primary), ('overlap_complete', overlap)):
            cp = [r[stream]['attributed_cpwer'] for r in group if r[stream] and r[stream]['attributed_cpwer'].get('word_counts')]
            stats['cpwer_stream_accounting'][stream][pop] = {
                 'scenes': len(cp), 'scenes_cpwer_above_100_percent': sum(v['wer'] > 1 for v in cp),
                 **{k: sum(v.get(k, 0) for v in cp) for k in ('missed_speaker', 'falarm_speaker', 'scored_speaker', 'reference_streams', 'hypothesis_streams')},
                 'scope': 'MeetEval final-text stream assignment counts; missing/extra streams are not identified physical-person misses/false alarms'}
    dimensions = ('room', 'family_id', 'corpus', 'quality_partition', 'pose', 'obstructed', 'relative_scene_db',
                  'relative_utterance_db', 'requested_noise_snr_db', 'requested_speech_sir_db', 'common_headroom_scalar', 'reference_complete')
    for population_rows, metric, name in ((primary, 'text', 'primary'), (overlap, 'overlap_mimo', 'overlap'),
                                          (primary + overlap, 'attributed_cpwer', 'cpwer'), (ambient, 'target_only_text', 'ambient_target_only')):
        for dim in dimensions:
            for level in sorted({r[dim] for r in population_rows}):
                subset = [r for r in population_rows if r[dim] == level]
                stats['strata'].append({'population': name, 'dimension': dim, 'level': level,
                                       'requested_scenes': len(subset), **paired(subset, metric)})
    if complete_primary and not allow_partial:
        boot = uncertainty(complete_primary, read(REPORT / 'DEPENDENCY_BLOCKS.json'))
        boot['requested_primary_scenes'] = 117
        boot['complete_primary_scenes'] = len(complete_primary)
        write_csv(REPORT / 'BOOTSTRAP_DRAWS.csv', [{'replicate': i, 'O1_minus_O0_wer_pp': x} for i, x in enumerate(boot.pop('bootstrap_delta_pp'))])
        save(REPORT / 'UNCERTAINTY.json', boot)
        stats['uncertainty'] = boot
    else:
        stats['uncertainty'] = {'status': 'UNAVAILABLE_INCOMPLETE_PRIMARY_PANEL'}
    sup, turns, returns, regions, short = aggregate_support(values, support_values)
    stats['support'] = sup
    stats['shared_noise_direction'], shared_table = shared_noise_summary(supports, guard)
    noise_events = [{'case_id': cid, 'stream': stream, **event} for (cid, stream), output in support_values.items() for event in output.get('noise_events', [])]
    stats['real_noise_output_local_coverage'] = {
         stream: {'requested_noise_cases': 39,
                  'scored_native_noise_outputs': sum(rows[cid]['real_noise'] for cid, out in support_values if out == stream),
                  'mapped_noise_outputs': sum(rows[cid]['real_noise'] and output['regions'] is not None for (cid, out), output in support_values.items() if out == stream),
                  'missing_mapping_case_ids': [cid for (cid, out), output in support_values.items() if out == stream and rows[cid]['real_noise'] and output['regions'] is None]}
         for stream in ('O0', 'O1')}
    for origin in ('fresh_s5', 'reused_s45'):
        stats['timing'][origin] = {}
        for stream in ('O0', 'O1'):
            ts = [t for t in timing_rows if t['origin'] == origin and t['stream'] == stream]
            rc = collections.Counter()
            for t in ts: rc.update(t['transcript_revisions']['counts'])
            stats['timing'][origin][stream] = {'jobs': len(ts),
                'model_child_wall_s': sum(t['model_child_wall_s'] for t in ts),
                'decoded_audio_s': sum(t['decoded_audio_s'] for t in ts),
                'child_wall_distribution_s': distribution(t['model_child_wall_s'] for t in ts),
                'interval_distributions_s': {key: distribution(t['intervals_s'].get(key) for t in ts) for key in sorted({k for t in ts for k in t['intervals_s']})},
                'queue_wait_s': distribution(t['queue_wait_since_s5_start_s'] for t in ts),
                'transcript_revisions': dict(rc)}
    fresh_cids = {t['case_id'] for t in timing_rows if t['origin'] == 'fresh_s5'}
    tmap = {(t['case_id'], t['stream']): t for t in timing_rows}
    deltas = [tmap[(cid, 'O1')]['model_child_wall_s'] - tmap[(cid, 'O0')]['model_child_wall_s']
              for cid in sorted(fresh_cids) if all((cid, s) in tmap for s in ('O0', 'O1'))]
    stats['timing']['fresh_paired_O1_minus_O0_child_wall_s'] = distribution(deltas)
    stats['reliability'] = {'requested': 360, 'complete': sum(r['status'] == 'COMPLETE' for r in completion_rows),
         'reused': sum(r['status'] == 'COMPLETE' and r['reused'] for r in completion_rows),
         'new_complete': sum(r['status'] == 'COMPLETE' and not r['reused'] for r in completion_rows),
         'failed': sum(r['status'] == 'FAILED' for r in completion_rows),
         'pending': sum(r['status'] == 'PENDING' for r in completion_rows),
         'quarantined': sum(r['status'] == 'QUARANTINED' for r in completion_rows),
         'new_attempts': sum(r['attempts'] for r in completion_rows),
         'retry_jobs': sum(r['attempts'] > 1 for r in completion_rows), 'reserve_task_evaluations': 0}
    stats['failed_empty_sensitivity'] = failed_empty_sensitivity(primary, guard.scenes, terminal_states)
    # Deterministic catalogue rule: most word-error difference each way, worst
    # shared total error, and largest cpWER-vs-word disagreement. No listening claim.
    candidates = [r for r in complete_primary if all(r[s]['text'].get('word_counts') for s in ('O0', 'O1'))]
    diff = lambda r: r['O1']['text']['word_counts']['errors'] - r['O0']['text']['word_counts']['errors']
    selected = {'O0_helps': sorted([r for r in candidates if diff(r) > 0], key=lambda r: (-diff(r), r['case_id']))[:3],
                'O1_helps': sorted([r for r in candidates if diff(r) < 0], key=lambda r: (diff(r), r['case_id']))[:3],
                'shared_difficult': sorted(candidates, key=lambda r: (-min(r['O0']['text']['word_counts']['errors'], r['O1']['text']['word_counts']['errors']), r['case_id']))[:3],
                'word_tie': sorted([r for r in candidates if diff(r) == 0], key=lambda r: (-r['O0']['text']['word_counts']['errors'], r['case_id']))[:2]}
    catalogue = []
    for kind, items in selected.items():
        for r in items:
            cid = r['case_id']
            catalogue.append({'kind': kind, 'case_id': cid, 'population': r['population'], 'strata': {k: r[k] for k in dimensions},
                'reference': catalogue_inputs[(cid, 'O0')]['text']['reference_normalized'],
                'O0_hypothesis': catalogue_inputs[(cid, 'O0')]['text']['hypothesis_normalized'],
                'O1_hypothesis': catalogue_inputs[(cid, 'O1')]['text']['hypothesis_normalized'],
                'O0_counts': r['O0']['text']['word_counts'], 'O1_counts': r['O1']['text']['word_counts'],
                'source_ids': r['source_ids'], 'source_bindings': [m['selected_sources'][sid]['source_binding'] for sid in r['source_ids']],
                'source_reference_hashes': {sid: m['selected_sources'][sid]['transcript_sha256'] for sid in r['source_ids']},
                'raw_output_bindings': {s: next(j['raw_audio'] for j in jm['jobs'] if j['case_id'] == cid and j['stream'] == s) for s in ('O0', 'O1')},
                'listened': False})
    save(REPORT / 'FAILURE_CATALOGUE.json', {'selection_rule': 'Top3 signed absolute word-error differences each way; top3 shared minimum errors; top2 highest-error ties; deterministic case-ID ties', 'examples': catalogue})
    save(REPORT / 'PAIRED_METRICS.json', {'schema': 'jp_s5_paired_metrics_v1', 'scope': 'development', 'rows': values})
    save(REPORT / 'SUMMARY_METRICS.json', stats)
    save(REPORT / 'COMPLETION_LEDGER.json', {'schema': 'jp_s5_completion_ledger_v1', 'summary': stats['reliability'], 'jobs': completion_rows})
    write_csv(REPORT / 'TURN_METRICS.csv', [{k: v for k, v in t.items() if k != 'boundary_interval_uncertainty'} for t in turns])
    write_csv(REPORT / 'RETURN_GROUPS.csv', returns)
    write_csv(REPORT / 'REGION_METRICS.csv', regions)
    write_csv(REPORT / 'NOISE_EVENT_METRICS.csv', noise_events)
    write_csv(REPORT / 'SHARED_NOISE_DIRECTION.csv', shared_table)
    write_csv(REPORT / 'SHORT_TURN_SUMMARY.csv', short)
    write_csv(REPORT / 'CONDITION_SUMMARY.csv', stats['strata'])
    write_csv(REPORT / 'TIMING_SUMMARY.csv', [{k: v for k, v in t.items() if k not in ('transcript_revisions', 'timestamps_utc')} for t in timing_rows])
    guard.flush()
    print(json.dumps({'status': stats['status'], 'reliability': stats['reliability'],
                      'primary': stats['primary'], 'overlap': stats['overlap_mimo']}, indent=2), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-partial', action='store_true', help='Label diagnostic output partial; never final selection')
    analyze(allow_partial=parser.parse_args().allow_partial)
