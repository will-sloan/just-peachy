"""Read-only S4.5 coverage joins and compact exports; README_S45_COVERAGE.md."""
import argparse
import collections
import csv
import hashlib
import io
import json
import os
from pathlib import Path

from s45_common import BANK, REPORT, RUN_ID, SIM, bind, now, read, save

ALLOWED = {'CMU ARCTIC', 'HiFiTTS', 'Common Voice'}
EXCLUDED_RIR = 'JPXVF_P1_R02_T01_D01_S02_F00_NAT_CU_R13'
GROUP_KEYS = ('room_table', 'recorder_position', 'orientation', 'obstructed')
BINS = ('under_1s', '1_to_under_2s', '2_to_under_3s', '3_to_5s', 'over_5s')
SOURCE = SIM / 'staging/s45_sources/SOURCE_AND_SPLIT_MANIFEST.json'
LEGACY = SIM / 'staging/s45_sources/LEGACY_DEVELOPMENT_PROBES.json'
NOISE = SIM / 'staging/s45_noise/NOISE_CATALOG.json'
RIRS = SIM / 'rir_library/v1/RIR_MANIFEST.json'


class CoverageError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise CoverageError(message)


def duration_bin(seconds):
    return BINS[0 if seconds < 1 else 1 if seconds < 2 else 2 if seconds < 3 else 3 if seconds <= 5 else 4]


def counts(values):
    return dict(sorted(collections.Counter(values).items()))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def gain(source):
    value = source['preparation_gain']
    return value['scalar'] if isinstance(value, dict) else value


def compact_binding(binding):
    return {k: binding[k] for k in ('path', 'sha256', 'bytes') if k in binding}


def json_snapshot(path):
    """Bind the bytes actually consumed if the coordinator atomically advances a snapshot."""
    payload = path.read_bytes()
    return json.loads(payload.decode('utf-8-sig')), {'path': str(path.resolve()), 'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}


def source_join(row, frozen):
    for key in ('source_id', 'identity', 'dataset', 'split', 'usage', 'samples', 'transcript'):
        require(row[key] == frozen[key], 'Source mismatch: ' + row['source_id'] + '/' + key)
    for key in ('source_binding', 'decoded_16k_binding'):
        require(row[key]['sha256'] == frozen[key]['sha256'], 'Source byte binding mismatch')
    require(gain(row) == gain(frozen), 'Source preparation gain changed')


def validate_sources(source_manifest, legacy):
    people = {p['identity']: p for p in source_manifest['people']}
    require(len(people) == len(source_manifest['people']), 'Repeated roster identity')
    sources = source_manifest['sources'] + legacy.get('sources', [])
    lookup = {}
    split_by_group = {}
    role_by_group = {}
    for source in sources:
        sid, identity = source['source_id'], source['identity']
        require(sid not in lookup, 'Repeated source ID: ' + sid)
        require(source['dataset'] in ALLOWED, 'Unapproved speech corpus')
        require(identity in people and source['split'] == people[identity]['split'], 'Source roster split mismatch')
        require(source['role_frozen_before_QC'] is True, 'Source role not frozen before QC')
        require(source['usage'] in ('probe', 'enrollment_reference'), 'Unknown source role')
        # HiFi parent books and within-corpus CMU/CV text prompts are the frozen
        # dependency units. Cross-corpus people/text are not declared independent.
        parent = source.get('parent_book') if source['dataset'] == 'HiFiTTS' else source.get('prompt_group')
        require(parent, 'Missing source dependency group: ' + sid)
        group = (source['dataset'], parent)
        require(split_by_group.setdefault(group, source['split']) == source['split'], 'Parent/prompt split leakage')
        require(role_by_group.setdefault(group, source['usage']) == source['usage'], 'Parent/prompt probe/enrollment leakage')
        lookup[sid] = source
    return people, lookup


def expected_partition(scene):
    stratum = scene['reserve_stratum']
    require(stratum in ('development', 'new_source_reserve', 'upper_loeb_acoustic_reserve', 'joint_reserve'), 'Unknown reserve stratum')
    require(scene['split'] == ('development' if stratum == 'development' else 'reserve'), 'Scene split/stratum mismatch')
    return 'downstream_reserve' if stratum in ('new_source_reserve', 'joint_reserve') else 'development'


def analyze_bank(manifest, sources, noise_manifest, rir_manifest, expected_scenes=240, expected_development=180):
    scenes = manifest['scenes']
    require(manifest['validation']['status'] == 'PASS', 'Canonical bank validation is not PASS')
    require(len(scenes) == expected_scenes and len({s['case_id'] for s in scenes}) == expected_scenes, 'Canonical scene count or ID duplication')
    require(sum(s['split'] == 'development' for s in scenes) == expected_development, 'Development quota mismatch')
    selected_sources = manifest['selected_sources']
    for sid, row in selected_sources.items():
        require(sid in sources, 'Unfrozen selected source: ' + sid)
        source_join(row, sources[sid])
    noise = {n['noise_id']: n for n in noise_manifest['prepared_segments']}
    require(len(noise) == len(noise_manifest['prepared_segments']), 'Duplicate noise ID')
    parent_splits = {}
    parents = {p['parent_id']: p for p in noise_manifest.get('parents', [])}
    group_splits = {}
    for row in noise.values():
        require(parent_splits.setdefault(row['parent_id'], row['split']) == row['split'], 'Noise parent split leakage')
        if parents:
            require(row['parent_id'] in parents and parents[row['parent_id']]['split'] == row['split'], 'Noise prepared/parent split mismatch')
            parent = parents[row['parent_id']]
            require(row['parent_group_id'] == parent['group_id'], 'Noise parent group changed')
            require(group_splits.setdefault(parent['group_id'], row['split']) == row['split'], 'Noise source-group split leakage')
    all_rirs = {r['run_id']: r for r in rir_manifest['records']}
    allowed_rirs = {rid: r for rid, r in all_rirs.items() if r['can_proceed_to_hil_proof'] and rid != EXCLUDED_RIR}
    actual, calibration, noise_events, compact = [], [], [], []
    rir_actual, rir_calibration = set(), set()
    for scene in scenes:
        cid, part = scene['case_id'], expected_partition(scene)
        require(scene['source_partition'] == part, 'Scene source partition mismatch: ' + cid)
        require(scene['task_scoring_allowed'] == (scene['split'] == 'development'), 'Reserve task scoring permitted')
        receiver = tuple(scene['receiver_configuration'][k] for k in GROUP_KEYS)
        require((receiver[0] == 'Upper Loeb') == (scene['reserve_stratum'] in ('upper_loeb_acoustic_reserve', 'joint_reserve')), 'Acoustic reserve room leakage')
        speech = [s for s in scene['segments'] if s['kind'] == 'utterance']
        actual_ids = {s['speaker_key'] for s in speech}
        require(set(scene['cast'].values()) == actual_ids, 'Scene cast differs from actual speech: ' + cid)
        require(len({sources[s['source_id']]['dataset'] for s in speech}) <= 1, 'Unresolved cross-corpus identities in simultaneous cast')
        for mode, segments in [('actual', scene['segments']), ('calibration', scene.get('snr_reference_segments', []))]:
            for segment in segments:
                sid, rid = segment['source_id'], segment['rir_id']
                require(rid in allowed_rirs and rid in manifest['selected_rirs'], 'Excluded or unknown RIR: ' + rid)
                original = allowed_rirs[rid]
                require(original['capture_audit_pass'] and original['original_acquisition_status'] in ('PASS', 'REVIEW'), 'RIR is not a qualified acquisition')
                geometry = original['geometry']
                require(0 < geometry['source_distance_m_effective'] <= 5, 'RIR distance outside (0,5] m')
                require(tuple(geometry[k] for k in GROUP_KEYS) == receiver, 'Incompatible receiver geometry')
                require(manifest['selected_rirs'][rid]['file']['sha256'] == original['output']['sha256'], 'RIR byte binding changed')
                require(manifest['selected_rirs'][rid]['geometry']['speaker_angle_deg_effective'] == geometry['speaker_angle_deg_effective'], 'RIR angle sign/value changed')
                require(manifest['selected_rirs'][rid]['geometry']['source_distance_m_effective'] == geometry['source_distance_m_effective'], 'RIR distance value changed')
                require(0 <= segment['source_start_sample'] < segment['source_stop_sample'] <= segment['convolution_stop_sample'] <= scene['duration_s'] * 16000, 'Segment timing is invalid')
                (rir_actual if mode == 'actual' else rir_calibration).add(rid)
                if segment['kind'] == 'utterance':
                    require(sid in selected_sources, 'Speech missing from selected source catalog')
                    source = sources[sid]
                    require(source['usage'] == 'probe', 'Enrollment/non-probe speech in canonical or SNR reference')
                    require(source['split'] == part == segment['source_split'], 'Speech reserve leakage')
                    require(source['identity'] == segment['speaker_key'], 'Speaker identity misassignment')
                    require(scene['cast'].get(segment['participant_id']) == source['identity'] or mode == 'calibration', 'Participant alias misassignment')
                    require(segment['whole_clip'] and segment['source_crop_samples'] == [0, source['samples']], 'Canonical probe was cropped')
                    require(segment['source_stop_sample'] - segment['source_start_sample'] == source['samples'], 'Source duration mismatch')
                    require(segment['preparation_gain_scalar'] == gain(source), 'Scene source gain mismatch')
                    require(segment['transcript'] == source['transcript'], 'Transcript source mismatch')
                    row = {'case_id': cid, 'scene_split': scene['split'], 'reserve_stratum': scene['reserve_stratum'], 'family_id': scene['family_id'],
                           'source_id': sid, 'identity': source['identity'], 'dataset': source['dataset'], 'source_split': source['split'],
                           'duration_s': source['samples'] / 16000, 'rir_id': rid, 'partners': sorted(actual_ids - {source['identity']}),
                           'isolated_scene': len(actual_ids) == 1 and not any(s['kind'] != 'utterance' for s in scene['segments']),
                           'conversation_scene': len(actual_ids) > 1, 'geometry': geometry, 'quality': source['quality_disposition']}
                    (actual if mode == 'actual' else calibration).append(row)
                else:
                    require(mode == 'actual' and segment['kind'] == 'real_noise', 'Unknown segment kind')
                    require(sid in noise and sid in manifest['selected_noise'], 'Uncatalogued noise')
                    row = noise[sid]
                    require(row['parent_id'] == segment['parent_id'], 'Noise parent mismatch')
                    require(row['split'] == segment['source_split'] == ('reserve' if part == 'downstream_reserve' else 'development'), 'Noise split leakage')
                    require(row['prepared_sha256'] == manifest['selected_noise'][sid]['prepared_sha256'], 'Noise byte binding changed')
                    require(row['speech_content'] == segment['speech_content'] and row['strict_nonspeech_eligible'] == segment['strict_nonspeech_eligible'], 'Noise truth metadata mismatch')
                    if scene['family_id'] == 'F12':
                        require(row['strict_nonspeech_eligible'], 'F12 contains unknown/speech-bearing noise')
                    noise_events.append({'case_id': cid, 'source_id': sid, 'parent_id': row['parent_id'], 'rir_id': rid,
                                         'scene_split': scene['split'], 'duration_s': (segment['source_stop_sample'] - segment['source_start_sample']) / 16000})
        compact.append({'case_id': cid, 'family_id': scene['family_id'], 'split': scene['split'], 'reserve_stratum': scene['reserve_stratum'],
                        'source_partition': part, 'duration_s': scene['duration_s'], 'canonical_sha256': scene['canonical_audio']['sha256'],
                        'cast': scene['cast'], 'probe_source_ids': sorted({s['source_id'] for s in speech}),
                        'utterance_instances': len(speech), 'whole_probe_scheduled_s': round(sum((s['source_stop_sample'] - s['source_start_sample']) / 16000 for s in speech), 6),
                        'noise_source_ids': sorted({s['source_id'] for s in scene['segments'] if s['kind'] == 'real_noise'}),
                        'rir_ids': sorted({s['rir_id'] for s in scene['segments']}), 'receiver_configuration': scene['receiver_configuration'],
                        'matched_pair_id': scene.get('matched_pair_id'), 'matched_group_id': scene.get('matched_group_id'),
                        'overlap_scoring_limited': scene['overlap_scoring_limited'], 'all_speaker_reference_complete': scene['all_speaker_reference_complete'],
                        'reference_text_sha256': digest(scene.get('all_speaker_references', [])),
                        'requested_snr_db': (scene.get('noise_policy') or {}).get('snr_db'),
                        'requested_sir_db': (scene.get('speech_interference_policy') or {}).get('requested_sir_db'),
                        'common_family_headroom_scalar': scene['common_family_headroom_scalar'], 'canonical_peak_fs': scene['canonical_peak_fs'],
                        'task_scoring_allowed': scene['task_scoring_allowed']})
    return {'actual': actual, 'calibration': calibration, 'noise_events': noise_events, 'compact': compact,
            'allowed_rirs': allowed_rirs, 'rir_actual': rir_actual, 'rir_calibration': rir_calibration}


def analyze_references(manifest, sources, people, canonical_source_ids):
    if manifest is None:
        return []
    require(manifest['validation']['status'] == 'PASS', 'Reference preparation is not PASS')
    require(manifest['task_scoring_allowed'] is False and manifest['enrollment_executed'] is False, 'Reference preparation claims enrollment/scoring')
    rows, seen = [], set()
    for scene in manifest['scenes']:
        require(scene['split'] == 'development' and scene['excluded_from_240_canonical_count'] and not scene['task_scoring_allowed'], 'Reference included in canonical/reserve task bank')
        require(len(scene['segments']) == 1, 'Naming reference is not one isolated utterance')
        segment = scene['segments'][0]
        source = manifest['selected_sources'][segment['source_id']]
        require(source['usage'] == 'enrollment_reference' and source['split'] == 'development', 'Probe/reserve clip used for reference')
        identity, sid = source['identity'], source['source_id']
        require(identity in people and people[identity]['split'] == 'development' and identity not in seen, 'Invalid or duplicate reference identity')
        require(sid not in canonical_source_ids, 'Enrollment/probe source overlap')
        require(source['dataset'] in ALLOWED and segment['speaker_key'] == identity, 'Reference identity or corpus mismatch')
        if sid in sources:
            source_join(source, sources[sid])
        else:
            require(source.get('historical_development_reuse') and source.get('historical_original_usage') == 'enrollment_candidate_not_S4_probe', 'Unbound nonhistorical reference source')
            require(manifest.get('legacy_source_inputs'), 'Historical reference lacks input provenance')
        require(segment['source_crop_samples'] == [0, source['samples']] and segment['whole_clip'], 'Reference whole clip changed')
        require(segment['preparation_gain_scalar'] == gain(source), 'Reference source gain changed')
        seen.add(identity)
        rows.append({'case_id': scene['case_id'], 'identity': identity, 'source_id': sid, 'dataset': source['dataset'],
                     'rir_id': segment['rir_id'], 'duration_s': source['samples'] / 16000,
                     'canonical_duration_s': scene['duration_s'], 'historical_reuse': bool(source.get('historical_development_reuse'))})
    return rows


def capture_snapshot(path, scenes, manifest_binding, reference=False):
    if not path.exists():
        return {'status': 'NOT_YET_REPORTED', 'accepted_count': 0, 'pending_count': len(scenes), 'accepted': [], 'failed_attempts': [], 'input_binding': None}
    document, document_binding = json_snapshot(path)
    binding = document.get('reference_scene_manifest', document.get('scene_manifest'))
    require(binding and binding['sha256'] == manifest_binding['sha256'], 'Capture acceptance points at a different scene manifest')
    scene_lookup = {s['case_id']: s for s in scenes}
    accepted, seen = [], set()
    for row in document['accepted']:
        cid = row['case_id']
        require(cid in scene_lookup and cid not in seen, 'Unknown/duplicate accepted capture')
        scene = scene_lookup[cid]
        receipt_binding = bind(row['case_result']['path'], row['case_result']['sha256'])
        receipt = read(receipt_binding['path'])
        require(receipt['case_id'] == cid and receipt['status'] == 'PASS', 'Accepted capture receipt not PASS')
        require(receipt['audio_integrity_status'] == 'PASS' and receipt['telemetry_status'] == 'PASS', 'Accepted capture integrity/telemetry failed')
        require(receipt['input_scene_sha256'] == row['input_scene_sha256'] == scene['canonical_audio']['sha256'], 'Accepted capture source mismatch')
        require(receipt.get('final_recipe_capture') is True, 'Accepted capture did not use frozen final recipe')
        if not reference:
            require(row['split'] == scene['split'] and row['task_scoring_allowed'] == (scene['split'] == 'development'), 'Accepted split/task eligibility mismatch')
        seen.add(cid)
        accepted.append({'case_id': cid, 'split': scene['split'], 'case_result': compact_binding(receipt_binding),
                         'input_scene_sha256': receipt['input_scene_sha256'], 'code_key': receipt['code_key'],
                         'recipe': receipt.get('recipe'), 'integrity_status': 'PASS',
                         'task_scoring_allowed': False if reference else scene['split'] == 'development',
                         'optional_reference': reference})
    if 'accepted_count' in document:
        require(document['accepted_count'] == len(accepted), 'Accepted capture count mismatch')
    require(document.get('reserve_task_scored', False) is False, 'Reserve task scores appear in acceptance metadata')
    failures = []
    for row in document.get('failed_attempts', []):
        require(row['case_id'] in scene_lookup, 'Unknown failed capture attempt')
        item = {k: row.get(k) for k in ('case_id', 'status', 'audio_valid', 'telemetry_valid', 'error')}
        if row.get('case_result'):
            item['case_result'] = compact_binding(bind(row['case_result']['path'], row['case_result']['sha256']))
        failures.append(item)
    return {'status': 'COMPLETE' if len(accepted) == len(scenes) else 'PARTIAL', 'accepted_count': len(accepted),
            'pending_count': len(scenes) - len(accepted), 'accepted': sorted(accepted, key=lambda r: r['case_id']),
            'failed_attempts': failures, 'input_binding': document_binding}


def source_rows(people, sources, analysis, references, accepted, reference_captures):
    rows = []
    captured = {x['case_id'] for x in accepted['accepted']}
    captured_refs = {x['case_id'] for x in reference_captures['accepted']}
    for identity, person in sorted(people.items()):
        pool = [s for s in sources.values() if s['identity'] == identity]
        events = [e for e in analysis['actual'] if e['identity'] == identity]
        ref = [r for r in references if r['identity'] == identity]
        used = {e['source_id'] for e in events}
        positions = {json.dumps({k: e['geometry'][k] for k in GROUP_KEYS + ('speaker_angle_deg_effective', 'source_distance_m_effective')}, sort_keys=True) for e in events}
        row = {'identity': identity, 'dataset': person['dataset'], 'source_split': person['split'],
               'documented_gender': person.get('gender'), 'documented_age_band': person.get('age_band'),
               'documented_accent': person.get('accent'), 'documented_L1': person.get('L1'),
               'quality_partitions': person.get('quality_partitions'), 'metadata_provenance': person.get('metadata_provenance'),
               'role_frozen_before_QC': person['role_frozen_before_QC'], 'prepared_probe_clips': sum(s['usage'] == 'probe' for s in pool),
               'prepared_enrollment_clips': sum(s['usage'] == 'enrollment_reference' for s in pool),
               'used_canonical_unique_probes': len(used), 'scheduled_utterance_instances': len(events),
               'scheduled_dry_s': round(sum(e['duration_s'] for e in events), 6), 'canonical_scene_count': len({e['case_id'] for e in events}),
               'accepted_canonical_scene_count': len({e['case_id'] for e in events if e['case_id'] in captured}),
               'development_scene_count': len({e['case_id'] for e in events if e['scene_split'] == 'development'}),
               'reserve_scene_count': len({e['case_id'] for e in events if e['scene_split'] == 'reserve'}),
               'conversation_scene_count': len({e['case_id'] for e in events if e['conversation_scene']}),
               'development_conversation_scene_count': len({e['case_id'] for e in events if e['conversation_scene'] and e['scene_split'] == 'development'}),
               'isolated_speech_scene_count': len({e['case_id'] for e in events if e['isolated_scene']}),
               'distinct_partners': sorted({p for e in events for p in e['partners']}),
               'measured_position_count': len(positions), 'rir_ids': sorted({e['rir_id'] for e in events}),
               'room_tables': sorted({e['geometry']['room_table'] for e in events}),
               'scheduled_instances_by_family': counts(e['family_id'] for e in events),
               'scheduled_short_duration_bins': counts(duration_bin(e['duration_s']) for e in events),
               'unique_probe_duration_bins': counts(duration_bin(sources[sid]['samples'] / 16000) for sid in used),
               'used_probe_QC_dispositions': counts(sources[sid]['quality_disposition'] for sid in used),
               'historical_probe_clips_used': sum(bool(sources[sid].get('historical_development_reuse')) for sid in used),
               'optional_reference_prepared_count': len(ref), 'optional_reference_accepted_count': sum(r['case_id'] in captured_refs for r in ref),
               'optional_reference_source_ids': [r['source_id'] for r in ref],
               'source_gap': 'NO_ELIGIBLE_PROBE_AFTER_FROZEN_QC' if not any(s['usage'] == 'probe' for s in pool) else None}
        rows.append(row)
    return rows


def noise_rows(catalog, events):
    result = []
    for noise in catalog['prepared_segments']:
        hits = [e for e in events if e['source_id'] == noise['noise_id']]
        result.append({**{k: noise.get(k) for k in ('noise_id', 'parent_id', 'parent_group_id', 'dataset', 'split', 'category', 'category_evidence', 'speech_content',
                       'strict_nonspeech_eligible', 'effective_license', 'rights', 'attribution', 'duration_s', 'crop_native_samples', 'quality', 'prepared_sha256')},
                       'canonical_scene_count': len({e['case_id'] for e in hits}), 'scheduled_instances': len(hits),
                       'scheduled_noise_s': round(sum(e['duration_s'] for e in hits), 6), 'rir_ids': sorted({e['rir_id'] for e in hits}),
                       'used': bool(hits)})
    return result


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    temporary = path.with_suffix('.csv.pending')
    temporary.write_text(output.getvalue(), encoding='utf-8-sig')
    os.replace(temporary, path)


def build(validate_only=False):
    required = [BANK / 'SCENE_MANIFEST.json', SOURCE, LEGACY, NOISE, RIRS]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        return {'status': 'PENDING_REQUIRED_INPUTS', 'missing': missing, 'outputs_written': False}, 2
    input_bindings = {p.name if p not in (SOURCE, LEGACY, NOISE, RIRS) else {SOURCE: 'speech_sources', LEGACY: 'legacy_probes', NOISE: 'noise_catalog', RIRS: 'RIR_catalog'}[p]: compact_binding(bind(p)) for p in required}
    manifest, sm, legacy, nm, rm = map(read, required)
    for field, key in [('sources_binding', 'speech_sources'), ('legacy_development_sources_binding', 'legacy_probes'), ('noise_binding', 'noise_catalog')]:
        require(manifest[field]['sha256'] == input_bindings[key]['sha256'], 'Frozen bank input binding changed: ' + field)
    people, sources = validate_sources(sm, legacy)
    analysis = analyze_bank(manifest, sources, nm, rm)
    require(len(people) == 44, 'Unexpected frozen roster count')
    refpath = BANK / 'REFERENCE_SCENE_MANIFEST.json'
    refmanifest = read(refpath) if refpath.exists() else None
    if refmanifest:
        input_bindings['reference_scene_manifest'] = compact_binding(bind(refpath))
        require(refmanifest['source_manifest_binding']['sha256'] == input_bindings['speech_sources']['sha256'], 'Reference source manifest changed')
    actual_ids = {e['source_id'] for e in analysis['actual']}
    references = analyze_references(refmanifest, sources, people, actual_ids)
    accepted = capture_snapshot(REPORT / 'ACCEPTED_CAPTURES.json', manifest['scenes'], input_bindings['SCENE_MANIFEST.json'])
    refaccepted = capture_snapshot(REPORT / 'REFERENCE_CAPTURES.json', refmanifest['scenes'], input_bindings['reference_scene_manifest'], True) if refmanifest else {'status': 'NOT_PREPARED', 'accepted_count': 0, 'pending_count': 0, 'accepted': [], 'failed_attempts': [], 'input_binding': None}
    require(not refaccepted['accepted'] or accepted['accepted_count'] == 240, 'Optional reference captures precede canonical completion')
    for name, value in [('accepted_captures', accepted), ('reference_captures', refaccepted)]:
        if value['input_binding']:
            input_bindings[name] = value['input_binding']
    rows = source_rows(people, sources, analysis, references, accepted, refaccepted)
    require(len({e['identity'] for e in analysis['actual']}) == 43, 'Not all 43 eligible roster identities occur in actual canonical speech')
    require(sum(r['source_split'] == 'development' and r['development_conversation_scene_count'] > 0 for r in rows) == 34,
            'Not all 34 development identities have actual development conversation support')
    nr = noise_rows(nm, analysis['noise_events'])
    speech_rights = {}
    for corpus in sorted(ALLOWED):
        rights = {digest(s['rights']): s['rights'] for s in sources.values() if s['dataset'] == corpus}
        speech_rights[corpus] = {'releases': sorted({s['release'] for s in sources.values() if s['dataset'] == corpus}), 'rights_variants': list(rights.values()),
                                 'roster_split_counts': counts(p['split'] for p in people.values() if p['dataset'] == corpus)}
    rights = {'schema': 'jp_s45_rights_and_splits_v1', 'run_id': RUN_ID, 'speech': speech_rights,
              'noise_parent_rights': [{k: p[k] for k in ('parent_id', 'group_id', 'dataset', 'dataset_resource', 'dataset_version', 'download_url', 'split', 'category', 'category_evidence', 'speech_content', 'speech_content_evidence',
                                      'strict_nonspeech_eligible', 'source_group', 'parent_group', 'rights', 'attribution', 'license_binding', 'metadata_bindings', 'source_binding', 'source_url') if k in p} for p in nm.get('parents', [])],
              'source_cohort': [{k: p.get(k) for k in ('identity', 'dataset', 'split', 'role_frozen_before_QC', 'preserved_S4_identity')} for p in people.values()],
              'noise_split_policy': nm.get('split_policy'), 'historical_CV_contributors_excluded': sm['historical_identities_excluded'],
              'historical_S4_roles_preserved': True, 'L2_ARCTIC': 'EXCLUDED_BY_USER_REQUEST',
              'future_training_or_redistribution_automatically_cleared': False, 'voice_synthesis_consent_claimed': False,
              'independence_unit': 'Speaker ID and within-corpus prompt group; HiFi parent book; noise parent recording. Dataset IDs do not prove cross-corpus biological identity independence.',
              'reference_roles': 'Unused enrollment references remain separate, optional, development-only and outside the 240 bank; preparation/capture does not execute enrollment.',
              'input_bindings': input_bindings}
    rir_reference = {r['rir_id'] for r in references}
    used_rirs = analysis['rir_actual']
    calibration_only = {e['source_id'] for e in analysis['calibration']} - actual_ids
    summary = {'schema': 'jp_s45_coverage_summary_v1', 'run_id': RUN_ID, 'generated_utc': now(),
               'status': 'COVERAGE_COMPLETE' if accepted['accepted_count'] == 240 else 'COVERAGE_VALID_CAPTURE_PENDING',
               'counts': {'roster_identities': len(people), 'usable_probe_identities': len({s['identity'] for s in sources.values() if s['usage'] == 'probe'}),
                          'actually_scheduled_identities': len({e['identity'] for e in analysis['actual']}), 'canonical_scenes': len(manifest['scenes']),
                          'canonical_accepted_captures': accepted['accepted_count'], 'canonical_pending_captures': accepted['pending_count'],
                          'canonical_unique_probe_clips': len(actual_ids), 'canonical_utterance_instances': len(analysis['actual']),
                          'canonical_scheduled_dry_s': round(sum(e['duration_s'] for e in analysis['actual']), 6),
                          'canonical_prepared_audio_s': sum(s['duration_s'] for s in manifest['scenes']),
                          'calibration_only_unique_probe_clips': len(calibration_only), 'optional_reference_prepared': len(references),
                          'optional_reference_accepted': refaccepted['accepted_count'], 'optional_reference_pending': refaccepted['pending_count'],
                          'optional_reference_unique_clips': len({r['source_id'] for r in references}),
                          'optional_reference_prepared_audio_s': sum(r['canonical_duration_s'] for r in references),
                          'noise_prepared_segments': len(nr), 'noise_used_segments': sum(r['used'] for r in nr),
                          'noise_used_parents': len({e['parent_id'] for e in analysis['noise_events']}),
                          'rir_allowed': len(analysis['allowed_rirs']), 'rir_actual_canonical_used': len(used_rirs),
                          'rir_allowed_not_in_actual_canonical': len(set(analysis['allowed_rirs']) - used_rirs), 'rir_optional_reference_used': len(rir_reference)},
               'scene_split_counts': counts(s['split'] for s in manifest['scenes']),
               'reserve_strata_counts': counts(s['reserve_stratum'] for s in manifest['scenes']),
               'family_counts': counts(s['family_id'] for s in manifest['scenes']),
               'corpus_coverage': [{ 'dataset': corpus, 'roster': sum(p['dataset'] == corpus for p in people.values()),
                                   'actual_identities': len({e['identity'] for e in analysis['actual'] if e['dataset'] == corpus}),
                                   'unique_probes': len({e['source_id'] for e in analysis['actual'] if e['dataset'] == corpus}),
                                   'scheduled_instances': sum(e['dataset'] == corpus for e in analysis['actual']),
                                   'used_quality_partitions': counts(sources[sid]['quality_partition'] for sid in actual_ids if sources[sid]['dataset'] == corpus)} for corpus in sorted(ALLOWED)],
               'short_duration_bin_definition': {'under_1s': 'duration <1', '1_to_under_2s': '1<=duration<2', '2_to_under_3s': '2<=duration<3', '3_to_5s': '3<=duration<=5', 'over_5s': 'duration>5'},
               'actual_probe_duration_bins': counts(duration_bin(sources[sid]['samples'] / 16000) for sid in actual_ids),
               'scheduled_duration_bins': counts(duration_bin(e['duration_s']) for e in analysis['actual']),
               'unique_probe_duration_bins_by_source_split': {part: counts(duration_bin(sources[sid]['samples'] / 16000) for sid in actual_ids if sources[sid]['split'] == part) for part in ('development', 'downstream_reserve')},
               'scheduled_duration_bins_by_scene_split': {part: counts(duration_bin(e['duration_s']) for e in analysis['actual'] if e['scene_split'] == part) for part in ('development', 'reserve')},
               'development_conversation_identity_count': sum(r['source_split'] == 'development' and r['development_conversation_scene_count'] > 0 for r in rows),
               'source_gaps': [r['identity'] for r in rows if r['source_gap']],
               'explicitly_excluded_RIR': {'run_id': EXCLUDED_RIR, 'reason': 'Existing clock-sensitive path exclusion, unchanged; 121 library records, 120 eligible inputs'},
               'geometry_coverage': [{'rir_id': rid, 'geometry': {k: r['geometry'][k] for k in GROUP_KEYS + ('speaker_angle_deg_effective', 'source_distance_m_effective')},
                                      'used_actual_canonical': rid in used_rirs, 'used_calibration_reference': rid in analysis['rir_calibration'], 'used_optional_reference': rid in rir_reference} for rid, r in sorted(analysis['allowed_rirs'].items())],
               'scene_dependencies': {'matched_groups': {key: [s['case_id'] for s in manifest['scenes'] if s.get('matched_group_id') == key] for key in sorted({s['matched_group_id'] for s in manifest['scenes'] if s.get('matched_group_id')})}},
               'reserve_task_metrics_read': False, 'source_or_reference_audio_read': False,
               'integrity_scope': 'Canonical source/role/geometry joins and SHA-bound acceptance JSON; waveform hashes are preserved from prior rendering/capture receipts, not rehashed by this coverage pass.',
               'limitations': ['This is a deliberately constructed field of measured-path conditions, not a random population sample; 240 scenes are not 240 independent people or rooms.',
                              'Whole recorded utterances and native segmented passages are not claimed spontaneous replies; source room/reverb/noise remain. No auditory or anechoic certification.',
                              'Gender, age, accent and quality labels use only documented metadata; accent is not L1, and pseudonymous corpus IDs are not biometric identity.',
                              'Shared people, utterances, prompts/books, noise parents, RIR paths and matched condition groups create scene dependencies.',
                              'Upper Loeb acoustic reserve intentionally reuses development speech/noise; new-source and joint reserve use held-out source/noise partitions. All reserve task scores remain unread.',
                              'Near/distant paths can differ in transfer response and angle; nominal angle sign matches source geometry but is not a newly measured physical calibration.',
                              'SNR calibration reference segments absent from actual scene segments were not played as speech and are excluded from actual usage counts.',
                              'Optional references are prepared/captured separately; neither event is enrollment execution or enrolled-name accuracy.'],
               'input_bindings': input_bindings, 'coverage_code': compact_binding(bind(Path(__file__)))}
    if not validate_only:
        REPORT.mkdir(parents=True, exist_ok=True)
        write_csv(REPORT / 'SOURCE_COVERAGE.csv', rows)
        write_csv(REPORT / 'NOISE_CATALOG.csv', nr)
        save(REPORT / 'SCENE_MANIFEST_COMPACT.json', {'schema': 'jp_s45_scene_manifest_compact_v1', 'run_id': RUN_ID, 'scene_manifest': input_bindings['SCENE_MANIFEST.json'], 'count': len(analysis['compact']), 'scenes': analysis['compact'], 'full_transcripts_omitted': True})
        save(REPORT / 'ACCEPTED_CAPTURES_COMPACT.json', {'schema': 'jp_s45_accepted_captures_compact_v1', 'run_id': RUN_ID, 'generated_utc': now(), 'canonical': accepted, 'optional_references': refaccepted, 'reference_capture_not_enrollment': True})
        save(REPORT / 'RIGHTS_AND_SPLITS.json', rights)
        summary['export_bindings'] = [compact_binding(bind(REPORT / name)) for name in ('SOURCE_COVERAGE.csv', 'NOISE_CATALOG.csv', 'SCENE_MANIFEST_COMPACT.json', 'ACCEPTED_CAPTURES_COMPACT.json', 'RIGHTS_AND_SPLITS.json')]
        save(REPORT / 'COVERAGE_SUMMARY.json', summary)
    return {'status': summary['status'], 'counts': summary['counts'], 'outputs_written': not validate_only}, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-only', action='store_true', help='Validate current input metadata without writing exports; missing bank exits 2.')
    args = parser.parse_args()
    try:
        result, code = build(args.validate_only)
    except (CoverageError, KeyError, ValueError, FileNotFoundError) as error:
        result, code = {'status': 'INVALID_INPUT_OR_BINDING', 'error': str(error), 'outputs_written': False}, 1
    print(json.dumps(result, indent=2))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
