"""Metadata-only S5 input, coverage and dependency reconciliation. README_S5_COVERAGE.md."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import tempfile

SIM = Path(__file__).resolve().parent.parent
PACK = SIM.parent / 'Just_Peachy_S5_Codex_Pack/Just_Peachy_S5_Codex_Pack'
BANK = SIM / 'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json'
S45 = SIM / 'reports/S4_5/20260909T031300Z'
RIR = SIM / 'rir_library/v1/RIR_MANIFEST.json'
RUN_ID = '20260909T130308Z'
REPORT = SIM / 'reports/S5' / RUN_ID
BANK_SHA = '69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18'
RIR_SHA = '468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546'
PROMPT_RIR_SHA_TYPO = '468b2b306f994937a7d02db611080d38c7a4bcc7dc73d93762380f546'
GUIDE = Path('C:/Users/amiri/Downloads/XVF_Measurement_V10.docx')
GUIDE_SHA = 'b9427c76a98965ab418ef252ec0d480b979945d85d4aa0e4e2de6dd41514a67b'
EXCLUDED_RIR = 'JPXVF_P1_R02_T01_D01_S02_F00_NAT_CU_R13'
POPULATIONS = ('COMPLETE_REFERENCE_NONOVERLAP', 'COMPLETE_REFERENCE_OVERLAP',
               'INCOMPLETE_AMBIENT_REFERENCE', 'STRICT_EMPTY_REFERENCE')


def require(value, message):
    if not value:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


class Evidence:
    """Read only explicitly named small metadata inputs; never audio/model payloads."""
    def __init__(self):
        self.bindings = {}

    def bind(self, path, expected=None):
        path = Path(path).resolve()
        require(path.suffix.lower() in {'.json', '.jsonl', '.csv', '.md', '.txt', '.docx', '.zip', '.py'},
                'Coverage cannot open audio, model, embedding or array payload: ' + str(path))
        require(path.name not in {'metrics.json', 'audio_metrics.json', 'spatial_metrics.json', 'events.jsonl', 'session_summary.json'},
                'Coverage cannot inspect task results: ' + str(path))
        require(path.stat().st_size < 32 * 2**20, 'Unexpectedly large metadata input: ' + str(path))
        raw = path.read_bytes()
        item = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        require(expected is None or item['sha256'] == expected, 'Hash mismatch: ' + str(path))
        prior = self.bindings.get(str(path))
        require(prior is None or prior == item, 'Input changed during coverage review: ' + str(path))
        self.bindings[str(path)] = item
        return item

    def read(self, path, expected=None):
        self.bind(path, expected)
        result = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        self.bind(path, expected)
        return result

    def ref(self, item):
        actual = self.bind(item['path'], item['sha256'])
        require('bytes' not in item or item['bytes'] == actual['bytes'], 'Metadata byte count differs')
        return actual


def population(scene):
    if scene['split'] != 'development':
        require(scene['split'] == 'reserve' and scene['task_scoring_allowed'] is False, 'Invalid protected metadata split')
        return 'PROTECTED_RESERVE_METADATA_ONLY'
    require(scene['task_scoring_allowed'] is True, 'Development scene has task scoring disabled')
    speech = [x for x in scene['segments'] if x['kind'] == 'utterance']
    if not scene['all_speaker_reference_complete']:
        return 'INCOMPLETE_AMBIENT_REFERENCE'
    require(scene['transcript_valid'] is True, 'Unexpected complete-reference/invalid-transcript combination')
    if not speech:
        require(not scene['overlap_intervals'], 'Empty control has scheduled speech overlap')
        require(all(x['strict_nonspeech_eligible'] for x in scene['segments'] if x['kind'] == 'real_noise'),
                'Unknown environmental speech cannot become a strict control')
        return 'STRICT_EMPTY_REFERENCE'
    require(all(x.get('transcript', '').strip() for x in speech), 'Complete speech reference missing native text')
    return 'COMPLETE_REFERENCE_OVERLAP' if scene['overlap_intervals'] else 'COMPLETE_REFERENCE_NONOVERLAP'


def components(groups, ids):
    """Deterministic union, preserving complete matched groups before projection."""
    ids = set(ids)
    parent = {x: x for x in ids}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for group in groups:
        members = sorted(set(group) & ids)
        for x in members[1:]:
            a, b = root(members[0]), root(x)
            parent[max(a, b)] = min(a, b)
    out = defaultdict(list)
    for x in sorted(ids):
        out[root(x)].append(x)
    return sorted(out.values())


def dependency_plan(scenes, sources):
    dev = {cid: q for cid, q in scenes.items() if q['split'] == 'development'}
    primary = {cid for cid, q in dev.items() if population(q) == 'COMPLETE_REFERENCE_NONOVERLAP'}
    matched = defaultdict(set)
    dependency = {k: defaultdict(set) for k in ('speaker', 'source_clip', 'prompt', 'book', 'rir', 'noise_parent')}
    for cid, q in dev.items():
        for key in ('matched_pair_id', 'matched_group_id'):
            if q.get(key):
                matched[(key, q[key])].add(cid)
        for x in q['segments']:
            dependency['rir'][x['rir_id']].add(cid)
            if x['kind'] == 'utterance':
                a = sources[x['source_id']]
                dependency['speaker'][a['identity']].add(cid)
                dependency['source_clip'][a['source_id']].add(cid)
                if a.get('prompt_group'):
                    dependency['prompt'][a['prompt_group']].add(cid)
                if a.get('parent_book'):
                    dependency['book'][a['parent_book']].add(cid)
            elif x['kind'] == 'real_noise':
                dependency['noise_parent'][x['parent_id']].add(cid)
    members = components(matched.values(), dev)
    block_for = {cid: 'MATCHED_' + group[0] for group in members for cid in group}
    blocks = []
    for group in members:
        rooms = sorted({dev[c]['receiver_configuration']['room_table'] for c in group})
        require(len(rooms) == 1, 'Matched block crosses rooms; room-stratified proposal needs revision')
        blocks.append({'block_id': block_for[group[0]], 'scene_ids': group, 'room_table': rooms[0],
                       'primary_scene_ids': sorted(set(group) & primary),
                       'matched_keys': [{'field': key, 'value': value} for (key, value), cs in sorted(matched.items()) if set(group) & cs]})
    projected = [b['primary_scene_ids'] for b in blocks if b['primary_scene_ids']]
    diagnostics = {}
    for kind, groups in dependency.items():
        crossing = {key: ids for key, ids in groups.items() if len({block_for[x] for x in ids}) > 1}
        joined = components(projected + list(groups.values()), primary)
        diagnostics[kind] = {'unique_development_group_count': len(groups), 'groups_crossing_explicit_matched_blocks': len(crossing),
                             'primary_merged_component_count': len(joined), 'primary_merged_component_sizes': sorted(map(len, joined), reverse=True),
                             'primary_components': [{'component_id': kind.upper() + '_' + g[0], 'scene_ids': g} for g in joined],
                             'development_groups': [{'group_id': key, 'scene_ids': sorted(ids)} for key, ids in sorted(groups.items())]}
    all_joined = components(projected + [g for groups in dependency.values() for g in groups.values()], primary)
    return {'schema': 'jp_s5_dependency_blocks_v1', 'run_id': RUN_ID,
            'population_scope': '180 development metadata scenes; primary projections retain117 complete-reference nonoverlap scenes',
            'blocks': blocks, 'all_development_block_count': len(blocks), 'primary_block_count': len(projected),
            'all_block_size_counts': dict(Counter(len(b['scene_ids']) for b in blocks)),
            'primary_block_size_counts': dict(Counter(map(len, projected))),
            'primary_room_block_counts': dict(Counter(b['room_table'] for b in blocks if b['primary_scene_ids'])),
            'dependency_diagnostics': diagnostics, 'all_dependencies_primary_component_sizes': sorted(map(len, all_joined), reverse=True),
            'proposed_primary_resampling': 'For the coordinator to freeze: about2000 deterministic paired O1-minus-O0 block replicates; resample explicit matched blocks within each of the4 fixed rooms, carry both outputs and every primary member together, compute summed-error/summed-word ratios.',
            'required_sensitivities': ['Equal-room descriptive summaries', 'Leave-one-room-out', 'Speaker-connected primary component deletion or descriptive ranges; very few components do not support broad population confidence'],
            'limits': ['No matched block crosses a room in this frozen allocation.', 'Shared speakers, text, books, RIRs and noise cross explicit blocks; conditional bootstrap intervals are not population-independent confidence.', 'All primary observations are connected if all listed dependencies are collapsed together; no nontrivial fully independent bootstrap follows from that graph.', 'Prior24 development scene results were already inspected in S4.5; this is not blind preregistration.', 'This file proposes input blocks; SCORING_PROTOCOL.json remains the coordinator-owned analysis authority.']}, block_for


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def csv_text(rows):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow({k: compact_json(v) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    return buffer.getvalue()


def build():
    ev = Evidence()
    ev.bind(PACK / 'SHA256SUMS.txt')
    for line in (PACK / 'SHA256SUMS.txt').read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():
            continue
        sha, name = line.split(None, 1)
        name = name.lstrip('* ').strip()
        require(Path(name).name == name, 'Unexpected pack checksum traversal')
        ev.bind(PACK / name, sha)
    scope = ev.read(PACK / 'S5_SCOPE_AND_SCENE_IDS.json')
    ev.bind(Path('C:/Users/amiri/Downloads/Codex_S5_Definitive_Output_Comparison.md'), ev.bind(PACK / 'Codex_S5_Definitive_Output_Comparison.md')['sha256'])
    prompt = (PACK / 'Codex_S5_Definitive_Output_Comparison.md').read_text(encoding='utf-8')
    match = re.search(r'RIR-manifest SHA-256:\s*`([^`]+)`', prompt)
    require(match is not None and match.group(1) in {RIR_SHA, PROMPT_RIR_SHA_TYPO}, 'Unrecognized prompt RIR identity; do not silently substitute')
    stated_rir_sha = match.group(1)
    ev.bind(GUIDE, GUIDE_SHA)
    ev.bind(SIM / 'handoffs' / scope['source_handoff']['filename'], scope['source_handoff']['sha256'])
    bank = ev.read(BANK, BANK_SHA)
    ev.ref(scope['source_scene_manifest'])
    require(Path(scope['source_scene_manifest']['path']).resolve() == BANK.resolve(), 'Pack points to another bank')
    rir = ev.read(RIR, RIR_SHA)
    source = ev.read(bank['sources_binding']['path'], bank['sources_binding']['sha256'])
    legacy = ev.read(bank['legacy_development_sources_binding']['path'], bank['legacy_development_sources_binding']['sha256'])
    noise = ev.read(bank['noise_binding']['path'], bank['noise_binding']['sha256'])
    accepted = ev.read(S45 / 'ACCEPTED_CAPTURES.json')
    prior = ev.read(S45 / 'FINAL_SOURCE_COVERAGE_REVIEW.json')
    preservation = ev.read(S45 / 'FINAL_RESOURCE_AND_RESTORATION.json')
    rights = ev.read(S45 / 'RIGHTS_AND_SPLITS.json')
    require(prior['status'] == 'PASS_WITH_DOCUMENTED_COVERAGE_GAPS' and prior['verification']['failure_count'] == 0, 'Prior source coverage did not pass')
    require(preservation['status'] == preservation['conservation']['status'] == 'PASS' and preservation['conservation']['RIR_WAV_count'] == 121, 'Prior RIR conservation receipt is not qualified')
    require(preservation['conservation']['RIR_manifest']['sha256'] == RIR_SHA, 'Prior conservation does not support established RIR identity')
    old_bindings = {str(Path(x['path']).resolve()): x for x in prior['input_bindings']}
    for path in [BANK, RIR, Path(bank['sources_binding']['path']), Path(bank['legacy_development_sources_binding']['path']), Path(bank['noise_binding']['path']), S45 / 'ACCEPTED_CAPTURES.json']:
        require(str(path.resolve()) in old_bindings, 'Prior qualified metadata binding missing')
        ev.ref(old_bindings[str(path.resolve())])
    prior_captures = {x['case_id']: x for x in prior['verification']['accepted_case_result_bindings']}
    scenes = {x['case_id']: x for x in bank['scenes']}
    require(len(scenes) == len(bank['scenes']) == 240, 'Canonical scene IDs are not exactly240 unique')
    populations = {cid: population(q) for cid, q in scenes.items()}
    dev = {c for c, p in populations.items() if p != 'PROTECTED_RESERVE_METADATA_ONLY'}
    reserve = set(scenes) - dev
    require(dev == set(scope['development_scene_ids']) and len(dev) == len(scope['development_scene_ids']) == 180, 'Development allowlist differs from full local truth')
    require(reserve == set(scope['protected_reserve_scene_ids']) and len(reserve) == len(scope['protected_reserve_scene_ids']) == 60, 'Protected reserve IDs differ')
    for pop in POPULATIONS:
        require({cid for cid, p in populations.items() if p == pop} == set(scope['expected_development_scoring_populations'][pop]), 'Native population differs from pack: ' + pop)
    selected = {x['case_id']: x for x in accepted['accepted']}
    require(set(selected) == set(scenes) and len(selected) == len(accepted['accepted']) == accepted['accepted_count'] == 240, 'Acceptance does not contain exactly240 canonical cases')
    require(accepted['reserve_task_scored'] is False and accepted['scene_manifest']['sha256'] == BANK_SHA, 'Acceptance split/bank differs')
    for cid, row in selected.items():
        require(row['case_result']['sha256'] == prior_captures[cid]['sha256'] and row['case_result']['path'] == prior_captures[cid]['path'], 'Acceptance receipt differs from qualified review')
        require(row['input_scene_sha256'] == scenes[cid]['canonical_audio']['sha256'], 'Accepted canonical input differs')
        require(row['audio_valid'] is True and row['telemetry_valid'] is True and row['split'] == scenes[cid]['split'] and row['task_scoring_allowed'] == (cid in dev), 'Accepted metadata permission differs')
    sources = {x['source_id']: x for x in source['sources'] + legacy['sources']}
    prepared_noise = {x['noise_id']: x for x in noise['prepared_segments']}
    records = {x['run_id']: x for x in rir['records']}
    saved_wavs = {x['sha256'] for x in preservation['conservation']['RIR_WAV_bindings']}
    require(len(records) == 121 and all(x['output']['sha256'] in saved_wavs for x in records.values()), 'RIR manifest differs from prior waveform conservation bindings')
    dependency, block_for = dependency_plan(scenes, bank['selected_sources'])
    usage = {k: defaultdict(Counter) for k in ('rir', 'source', 'speaker', 'noise')}
    scene_rows = []
    for cid, q in sorted(scenes.items()):
        split = q['split']; us = [x for x in q['segments'] if x['kind'] == 'utterance']; ns = [x for x in q['segments'] if x['kind'] == 'real_noise']
        source_ids = sorted({x['source_id'] for x in us}); speaker_ids = sorted({x['speaker_key'] for x in us}); noise_ids = sorted({x['source_id'] for x in ns}); rids = sorted({x['rir_id'] for x in q['segments']})
        for kind, ids in [('rir', rids), ('source', source_ids), ('speaker', speaker_ids), ('noise', noise_ids)]:
            for identity in ids:
                usage[kind][identity][split] += 1
        for x in us:
            a = sources[x['source_id']]; selected_source = bank['selected_sources'][x['source_id']]
            require(a['usage'] == 'probe' and a['split'] == q['source_partition'] and a['identity'] == x['speaker_key'] == q['cast'][x['participant_id']], 'Speech source role/split/cast differs')
            require(a['dataset'] in {'CMU ARCTIC', 'Common Voice', 'HiFiTTS'}, 'Unauthorized speech corpus')
            for key in ('source_binding', 'decoded_16k_binding', 'decoded_pcm_sha256', 'prompt_group', 'parent_book', 'preparation_gain'):
                require(a.get(key) == selected_source.get(key), 'Selected source binding/group differs: ' + key)
            require(x['whole_clip'] is True and x['source_crop_samples'] == [0, a['samples']] and x['transcript'] == a['transcript'], 'Whole native source truth changed')
            require(x['preparation_gain_scalar'] == a['preparation_gain'] and a['source_gain_applied'] == 1, 'Source preparation metadata differs')
        for x in ns:
            n = prepared_noise[x['source_id']]
            require(n['parent_id'] == x['parent_id'] and n['split'] == x['source_split'] == ('reserve' if q['source_partition'] == 'downstream_reserve' else 'development'), 'Noise parent/split differs')
            require(n['speech_content'] == x['speech_content'] and n['strict_nonspeech_eligible'] == x['strict_nonspeech_eligible'], 'Noise speech uncertainty changed')
        for rid in rids:
            rr = records[rid]; g = bank['selected_rirs'][rid]['geometry']
            require(rr['can_proceed_to_hil_proof'] and rr['original_acquisition_status'] in {'PASS', 'REVIEW'} and rid != EXCLUDED_RIR, 'Ineligible/testing/retake RIR used')
            require({k: v for k, v in g.items() if k != 'active_angle_label'} == rr['geometry'], 'Measured geometry changed')
            require(0 < g['source_distance_m_effective'] <= 5 and all(g[k] == q['receiver_configuration'][k] for k in ('room_table', 'recorder_position', 'orientation', 'obstructed')), 'Invalid effective distance or receiver configuration')
            label = g['active_angle_label']; angle = g['speaker_angle_deg_effective']
            require(label['source_angle_lab_signed_deg'] == angle and label['source_angle_manual_uncertainty_deg'] == 5, 'Manual bearing/uncertainty changed')
            require(math.isclose(label['expected_native_nominal_deg'], math.degrees(math.acos(-math.sin(math.radians(angle))))), 'Nominal angle sign/folding changed')
        g = q['receiver_configuration']
        scene_rows.append({'case_id': cid, 'split': split, 'reserve_stratum': q['reserve_stratum'], 'source_partition': q['source_partition'],
                           'S5_population': populations[cid], 'S5_task_authorized': cid in dev, 'accepted_capture': True,
                           'canonical_audio_sha256': q['canonical_audio']['sha256'], 'accepted_case_receipt_sha256': selected[cid]['case_result']['sha256'],
                           'duration_s': q['duration_s'], 'family_id': q['family_id'], 'family': q['family'], **g,
                           'matched_pair_id': q['matched_pair_id'], 'matched_group_id': q['matched_group_id'], 'resampling_block_id': block_for.get(cid),
                           'source_corpus': sorted({sources[i]['dataset'] for i in source_ids}), 'source_quality_partitions': sorted({sources[i]['quality_partition'] for i in source_ids}),
                           'speaker_ids': speaker_ids, 'source_ids': source_ids, 'utterance_instances': len(us),
                           'prompt_groups': sorted({sources[i]['prompt_group'] for i in source_ids if sources[i].get('prompt_group')}),
                           'book_groups': sorted({sources[i]['parent_book'] for i in source_ids if sources[i].get('parent_book')}),
                           'noise_parent_ids': sorted({prepared_noise[i]['parent_id'] for i in noise_ids}), 'noise_categories': sorted({prepared_noise[i]['category'] for i in noise_ids}),
                           'noise_speech_content': sorted({prepared_noise[i]['speech_content'] for i in noise_ids}), 'noise_segment_instances': len(ns),
                           'rir_ids': rids, 'relative_source_level_db': q['relative_source_level_db'], 'family_headroom_scalar': q['common_family_headroom_scalar'],
                           'requested_noise_snr_db': (q['noise_policy'] or {}).get('snr_db'), 'requested_speech_sir_db': (q['speech_interference_policy'] or {}).get('requested_sir_db'),
                           'noise_level_policy': q['noise_policy'], 'speech_interference_policy': q['speech_interference_policy'],
                           'all_speaker_reference_complete': q['all_speaker_reference_complete'], 'scheduled_overlap': bool(q['overlap_intervals'])})
    rir_rows = []; rooms = defaultdict(lambda: {'eligible': set(), 'all_used': set(), 'dev_used': set(), 'reserve_used': set(), 'development_scenes': 0, 'reserve_scenes': 0})
    for rid, rr in sorted(records.items()):
        g = rr['geometry']; counts = usage['rir'][rid]; eligible = bool(rr['can_proceed_to_hil_proof']); room = rooms[g['room_table']]
        if eligible:
            room['eligible'].add(rid)
        for key, condition in [('all_used', bool(counts)), ('dev_used', bool(counts['development'])), ('reserve_used', bool(counts['reserve']))]:
            if condition:
                room[key].add(rid)
        disposition = 'EXCLUDED_CLOCK_SENSITIVE' if not eligible else 'S5_DEVELOPMENT_USED' if counts['development'] else 'PROTECTED_RESERVE_ONLY' if counts['reserve'] else 'DEFERRED_UNUSED_ELIGIBLE'
        rir_rows.append({'rir_id': rid, 'room_table': g['room_table'], 'recorder_position': g['recorder_position'], 'orientation': g['orientation'],
                         'obstructed': g['obstructed'], 'original_acquisition_status': rr['original_acquisition_status'], 'HIL_eligible': eligible,
                         'development_scene_count': counts['development'], 'reserve_scene_count_metadata_only': counts['reserve'],
                         'all_canonical_scene_count': sum(counts.values()), 'S5_disposition': disposition,
                         'angle_lab_signed_deg': g['speaker_angle_deg_effective'], 'manual_uncertainty_deg': 5,
                         'nominal_folded_angle_deg': math.degrees(math.acos(-math.sin(math.radians(g['speaker_angle_deg_effective'])))),
                         'distance_original_m': g['source_distance_m_original'], 'distance_effective_m': g['source_distance_m_effective'],
                         'distance_correction_applied': g['geometry_correction_applied'], 'waveform_sha256_from_validated_manifest': rr['output']['sha256'],
                         'geometry_missing_preserved': g['unmeasured_geometry'], 'reserve_task_use_authorized': False,
                         'note': 'Unused/deferred means no frozen S5 scene; no worse/equivalent/redundant inference. Manual bearing uncertainty is not XVF accuracy or injected jitter.'})
    for q in scenes.values():
        rooms[q['receiver_configuration']['room_table']][q['split'] + '_scenes'] += 1
    room_rows = []
    for name, values in sorted(rooms.items()):
        room_rows.append({'room_table': name, 'eligible_rirs': len(values['eligible']), 'used_rirs_all_240': len(values['all_used']),
                          'unused_eligible_rirs': len(values['eligible'] - values['all_used']), 'development_scenes': values['development_scenes'],
                          'reserve_scenes': values['reserve_scenes'], 'all_scenes': values['development_scenes'] + values['reserve_scenes'],
                          'development_used_rirs': len(values['dev_used']), 'reserve_used_rirs': len(values['reserve_used'])})
    pack_rooms = {x['room_table']: x for x in csv.DictReader((PACK / 'RIR_AND_ROOM_COVERAGE.csv').open(encoding='utf-8-sig', newline='')) if x['room_table'] != 'TOTAL'}
    for row in room_rows:
        require(all(int(pack_rooms[row['room_table']][k]) == v for k, v in row.items() if k != 'room_table'), 'Pack room counts differ: ' + row['room_table'])
    expected_pop = dict(Counter(populations[c] for c in dev))
    require(expected_pop == dict(zip(POPULATIONS, [117, 36, 19, 8])), 'Unexpected exclusive development populations')
    require(sum(x['HIL_eligible'] for x in rir_rows) == 120 and {x['rir_id'] for x in rir_rows if not x['HIL_eligible']} == {EXCLUDED_RIR}, 'Eligibility set differs')
    corrections = [x for x in rir_rows if x['distance_original_m'] != x['distance_effective_m']]
    require(len(corrections) == 2 and all(x['distance_original_m'] == 100 and x['distance_effective_m'] == 1 and x['angle_lab_signed_deg'] == 20 for x in corrections), 'Effective100cm correction changed')
    dev_rows = [x for x in scene_rows if x['S5_task_authorized']]
    counts = {'canonical_scenes': len(scenes), 'development_scenes': len(dev), 'protected_reserve_scenes': len(reserve),
              'exclusive_development_populations': expected_pop, 'reserve_strata': dict(Counter(scenes[c]['reserve_stratum'] for c in reserve)),
              'canonical_audio_s': sum(q['duration_s'] for q in scenes.values()), 'development_audio_s': sum(scenes[c]['duration_s'] for c in dev),
              'RIR_records': len(records), 'RIR_eligible': 120, 'RIR_all_used': sum(bool(v) for v in usage['rir'].values()),
              'RIR_development_used': sum(bool(v['development']) for v in usage['rir'].values()), 'RIR_unused_eligible': sum(x['S5_disposition'] == 'DEFERRED_UNUSED_ELIGIBLE' for x in rir_rows),
              'development_rooms': len({x['room_table'] for x in dev_rows}), 'development_upright_scenes': sum(x['orientation'] == 'UPRIGHT' for x in dev_rows),
              'development_obstructed_scenes': sum(x['obstructed'] for x in dev_rows), 'development_real_noise_scenes': sum(x['noise_segment_instances'] > 0 for x in dev_rows),
              'all_unique_probes': len(usage['source']), 'development_unique_probes': sum(bool(v['development']) for v in usage['source'].values()),
              'all_scheduled_metadata_identities': len(usage['speaker']), 'development_metadata_identities': sum(bool(v['development']) for v in usage['speaker'].values()),
              'all_used_noise_parents': len({prepared_noise[k]['parent_id'] for k in usage['noise']}), 'development_used_noise_parents': len({prepared_noise[k]['parent_id'] for k, v in usage['noise'].items() if v['development']})}
    require(counts['RIR_all_used'] == 39 and counts['RIR_development_used'] == 33 and counts['RIR_unused_eligible'] == 81, 'RIR use counts differ')
    require(counts['development_upright_scenes'] == counts['development_obstructed_scenes'] == 7 and counts['development_real_noise_scenes'] == 39, 'Sparse pose/obstruction or real-noise coverage differs')
    speaker_rows = []
    for person in source['people']:
        identity = person['identity']; use = usage['speaker'].get(identity, Counter())
        speaker_rows.append({'identity': identity, 'dataset': person['dataset'], 'source_split': person['split'], 'documented_gender': person.get('gender'),
                             'documented_age': person.get('age_band'), 'documented_accent': person.get('accent'), 'documented_L1': person.get('L1'),
                             'metadata_provenance': person.get('metadata_provenance'), 'development_scene_count': use['development'], 'reserve_scene_count_metadata_only': use['reserve'],
                             'known_aliases': person.get('known_aliases'), 'cross_corpus_human_uniqueness': person.get('cross_corpus_human_uniqueness')})
    review = {'schema': 'jp_s5_input_coverage_review_v1', 'run_id': RUN_ID, 'status': 'PASS_WITH_DOCUMENTED_SOURCE_AND_DEPENDENCY_GAPS', 'reviewed_utc': now(),
              'documented_input_discrepancies': [] if stated_rir_sha == RIR_SHA else [{'field': 'S5 prompt RIR-manifest SHA-256', 'stated_value': stated_rir_sha, 'stated_hex_characters': len(stated_rir_sha), 'established_value': RIR_SHA,
                  'disposition': 'MALFORMED_DOCUMENT_TRANSCRIPTION_RESOLVED_BY_EXISTING_QUALIFIED_RECEIPTS', 'evidence': 'Current full RIR manifest and prior final source/conservation receipts agree on the same64-character SHA; original prompt retained unchanged. No library or waveform change.'}],
              'counts': counts, 'room_coverage': room_rows, 'speaker_coverage': speaker_rows,
              'development_family_counts': dict(Counter(x['family_id'] for x in dev_rows)),
              'development_quality_scene_counts': dict(Counter(compact_json({'corpus': x['source_corpus'], 'quality': x['source_quality_partitions']}) for x in dev_rows)),
              'development_level_snr_sir_scene_counts': dict(Counter(compact_json({'level_db': x['relative_source_level_db'], 'snr_db': x['requested_noise_snr_db'], 'sir_db': x['requested_speech_sir_db']}) for x in dev_rows)),
              'noise_parent_coverage': [{'noise_id': k, 'parent_id': prepared_noise[k]['parent_id'], 'category': prepared_noise[k]['category'],
                                        'source_split': prepared_noise[k]['split'], 'speech_content': prepared_noise[k]['speech_content'], 'rights': prepared_noise[k]['rights'],
                                        'development_scene_count': v['development'], 'reserve_scene_count_metadata_only': v['reserve']} for k, v in sorted(usage['noise'].items())],
              'prior_source_limits': prior['limitations'], 'corrected_distance_RIR_ids': [x['rir_id'] for x in corrections],
              'rights_summary': {'authority': ev.bind(S45 / 'RIGHTS_AND_SPLITS.json'), 'future_training_automatically_cleared': False, 'historical_CV_exclusions': rights['historical_CV_contributors_excluded']},
              'prior_inspection': {'development_scene_ids': sorted({x['case_id'] for x in scope['previous_native_job_candidates']}), 'candidate_output_jobs': len(scope['previous_native_job_candidates']), 'blind_preregistration_claim': False, 'prior_predictions_opened_by_this_program': False},
              'integrity_scope': {'freshly_hashed': 'Named pack, guide, manifest and qualified receipt bytes only', 'source_or_RIR_waveforms_rehashed': False,
                                  'qualified_source_review': ev.bind(S45 / 'FINAL_SOURCE_COVERAGE_REVIEW.json'), 'qualified_RIR_conservation_review': ev.bind(S45 / 'FINAL_RESOURCE_AND_RESTORATION.json'),
                                  'accepted_case_bindings_matched_to_prior_qualified_review': 240, 'no_nested_waveform_or_transport_audit_repeated': True},
              'reserve_access': {'metadata_scene_count': 60, 'audio_payload_opens': 0, 'prediction_opens': 0, 'performance_metric_opens': 0, 'model_invocations': 0,
                                 'scope': 'This metadata utility only; the coordinator must consolidate execution access receipts for the entire S5 task.'},
              'limits': ['Only33 RIRs in4 development rooms; Upper Loeb remains protected.', 'Seven upright and seven obstructed development scenes are sparse, not balanced condition samples.',
                         'Manual bearing uncertainty is±5degrees; front/rear folding and unmeasured3D geometry remain, without refitting or jitter.', 'Both original100m records preserve the user-confirmed effective1.00m; only effective values govern use.',
                         'A bare CMU filename can encode different transcript text across speakers; normalized prompt groups and native book/byte identities are the qualified content keys.',
                         'No invented human uniqueness, anechoic quality, causal demographic/condition effect, or independent population samples.', 'Unused81 eligible RIRs are deferred by frozen allocation, not failed, equivalent, redundant or evidence of inferior quality.',
                         'The local prior-source limits include observations explicitly qualified to the earlier audit; S5 execution counts are not inferred from them.'],
              'input_bindings': list(ev.bindings.values()), 'coverage_code': ev.bind(Path(__file__)), 'coverage_readme': ev.bind(Path(__file__).with_name('README_S5_COVERAGE.md'))}
    return review, dependency, rir_rows, scene_rows


def save_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as f:
        f.write(text)
        tmp = Path(f.name)
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-only', action='store_true', help='Reconcile named metadata and print counts without exports')
    args = parser.parse_args()
    written = []
    try:
        review, dependency, rirs, scenes = build()
        if not args.validate_only:
            exports = {'RIR_COVERAGE.csv': csv_text(rirs), 'SCENE_COVERAGE.csv': csv_text(scenes), 'DEPENDENCY_BLOCKS.json': json.dumps(dependency, indent=2, ensure_ascii=False, allow_nan=False) + '\n'}
            for name, text in exports.items():
                save_atomic(REPORT / name, text)
                written.append(name)
            ev = Evidence()
            review['export_bindings'] = [ev.bind(REPORT / name) for name in exports]
            save_atomic(REPORT / 'INPUT_COVERAGE_REVIEW.json', json.dumps(review, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
            written.append('INPUT_COVERAGE_REVIEW.json')
        print(json.dumps({'status': review['status'], 'counts': review['counts'], 'development_blocks': dependency['all_development_block_count'],
                          'primary_blocks': dependency['primary_block_count'], 'validated_only': args.validate_only, 'report': str(REPORT)}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'BLOCKED_INPUT_RECONCILIATION', 'error': str(exc), 'exports_written': written}, indent=2))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
