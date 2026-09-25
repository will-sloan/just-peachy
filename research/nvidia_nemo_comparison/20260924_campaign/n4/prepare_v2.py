"""Verify all accepted files; freeze the full N4 bank and 16-row matrix. README_PREPARATION_V2.md."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path
import wave
from common import load, bind, sha, fingerprint, freeze, audio_only

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')


def dependency_groups(rows, dimensions):
    """Transitive overlap: a multi-actor scene must never enter several IID clusters."""
    parents = {r['case_id']: r['case_id'] for r in rows}
    def root(k):
        while parents[k] != k:
            parents[k] = parents[parents[k]]
            k = parents[k]
        return k
    seen = {}
    for row in rows:
        cid = row['case_id']
        for dimension in dimensions:
            for value in row[dimension]:
                key = (dimension, str(value))
                if key in seen:
                    a, b = sorted((root(cid), root(seen[key])))
                    parents[b] = a
                else:
                    seen[key] = cid
    return {cid: root(cid) for cid in parents}


def select_paced(rows):
    """One scene per family, deterministic coverage-greedy using reference metadata only."""
    selected = []
    covered = set()
    # Anchor real timing regressions; choose other families by metadata coverage.
    required = {'F03': 'S45_03_03', 'F06': 'S45_06_07', 'F08': 'S45_08_07', 'F12': 'S45_12_15'}
    def features(r):
        return {('room', r['room']), ('reference', r['reference_class']),
                ('pose', r['orientation']), ('level', str(r['relative_source_level_db'])),
                ('noise', str(r['requested_snr_db'])), ('short', r['has_short_turn'])}
    for family in sorted({r['family_id'] for r in rows}):
        pool = [r for r in rows if r['family_id'] == family]
        pick = next((r for r in pool if r['case_id'] == required.get(family)), None)
        if pick is None:
            pick = min(pool, key=lambda r: (-len(features(r) - covered), r['case_id']))
        selected.append(pick['case_id'])
        covered |= features(pick)
    return selected


def prepare(args):
    audit_path = CAMPAIGN/'data/DATA_AUDIT_SUMMARY.json'
    audit = load(audit_path)
    corpus_path = args.local/'data/CORPUS_BINDINGS_240.json'
    expected = next(b for b in audit['local_evidence'] if Path(b['path']).name == corpus_path.name)
    if bind(corpus_path) != expected or audit['status'] != 'PASS':
        raise ValueError('N1 accepted corpus binding differs')
    truth_path = args.local/'n2/evaluation/EVALUATOR_TRUTH.json'
    truth_receipt = load(args.local/'n2/evaluation/MANIFEST_RECEIPT.json')
    truth_binding = next(b for b in truth_receipt['outputs'] if Path(b['path']).name == truth_path.name)
    if bind(truth_path) != truth_binding:
        raise ValueError('Frozen N2 reference truth changed')
    truth = load(truth_path)
    truths = {t['job_id']: t for t in truth['cells']}
    if len(truths) != 480:
        raise ValueError('Truth must retain all 480 scene/tap cells')
    corpus = load(corpus_path)
    jobs, strata, pairs = [], [], []
    for scene in corpus['scenes']:
        meta, original = scene['summary'], scene['scene']
        cid = meta['case_id']
        if len(scene['cells']) != 2 or {c['tap'] for c in scene['cells']} != {'O0', 'O1'}:
            raise ValueError('Incomplete or duplicated capture pair')
        if {c['capture_id'] for c in scene['cells']} != {meta['capture_id']}:
            raise ValueError('Mixed physical capture passes')
        pair = dict(case_id=cid, capture_id=meta['capture_id'], cells=[])
        for cell in sorted(scene['cells'], key=lambda c:c['tap']):
            audio = cell['audio']
            actual = bind(audio['path'])
            if any(actual[k] != audio[k] for k in actual):
                raise ValueError('Accepted prepared audio differs: '+audio['path'])
            with wave.open(audio['path'], 'rb') as f:
                if (f.getframerate(), f.getnchannels(), f.getsampwidth(), f.getnframes()) != (16000, 1, 2, audio['frames']):
                    raise ValueError('Expected original admitted mono16k PCM16')
            expected_gain = 1.4125375446227544 if cell['tap'] == 'O0' else 1.
            if cell['gain_applied_once'] != expected_gain or cell['runtime_gain'] != 1:
                raise ValueError('Gain provenance changed')
            jid = 'N2_'+cid+'_'+cell['tap']  # retain exact audited truth join keys
            if truths[jid]['frames'] != audio['frames'] or truths[jid]['output_mapping'] != cell['output_mapping']:
                raise ValueError('Audio/reference timebase changed')
            jobs.append(audio_only(dict(job_id=jid, audio_path=audio['path'], audio_sha256=audio['sha256'],
                frames=audio['frames'], sample_rate_hz=16000, gain=1., reset_between_scenes=True, tap=cell['tap'])))
            pair['cells'].append(dict(tap=cell['tap'], audio=actual, gain_already_applied=expected_gain,
                                     runtime_gain=1., output_mapping=cell['output_mapping']))
        pairs.append(pair)
        speech = [s for s in original['segments'] if s.get('kind') == 'utterance']
        noise = original.get('noise_details') or {}
        policy = original.get('noise_policy') or {}
        strata.append(dict(case_id=cid, family_id=meta['family_id'], family=meta['family'],
            room=meta['room'], orientation=original['receiver_configuration'].get('orientation'),
            obstructed=original['receiver_configuration'].get('obstructed'),
            corpora=meta['corpora'], quality_partitions=meta['quality_partitions'],
            reference_class=meta['reference_class'], complete_reference=meta['complete_reference'],
            overlap=meta['overlap'], has_short_turn=any(t['estimated_active_seconds'] <= 1.5
                for t in truths['N2_'+cid+'_O0']['turns']),
            relative_source_level_db=original.get('relative_source_level_db'),
            requested_snr_db=noise.get('requested_snr_db'), achieved_snr_db=noise.get('achieved_snr_db'),
            noise_reference_scope=noise.get('reference_scope'), noise_policy=policy,
            noise_label=policy.get('model'), noise_group_ids=[str(policy['component_seed'])] if 'component_seed' in policy else [],
            actor_group_ids=sorted(meta['actor_ids']), text_group_ids=sorted({s['transcript_sha256'] for s in speech}),
            source_group_ids=sorted({s['source_id'] for s in speech}),
            matched_group_ids=[str(original[k]) for k in ('matched_pair_id', 'matched_group_id') if original.get(k)],
            exact_word_timing='UNAVAILABLE', historical_partition=meta['historical_source_partition']))
    counts = dict(Counter(r['reference_class'] for r in strata))
    if len(strata) != 240 or len({r['case_id'] for r in strata}) != 240 or counts != audit['reference_classes']:
        raise ValueError('Authoritative scene population changed')
    dimensions = ['actor_group_ids', 'text_group_ids', 'source_group_ids', 'noise_group_ids', 'matched_group_ids']
    dependencies = dependency_groups(strata, dimensions)
    matched = dependency_groups(strata, ['matched_group_ids'])
    actor = dependency_groups(strata, ['actor_group_ids'])
    for row in strata:
        cid = row['case_id']
        row.update(dependency_cluster=dependencies[cid], matched_cluster=matched[cid], actor_cluster=actor[cid])
    paced = select_paced(strata)
    catalog_path = args.source/'config/backends.json'
    from compose_release_v3 import inventory
    catalog = inventory(load(catalog_path))
    if set(catalog) != set(product(('A0','A1','A2','A3'), ('D0','D1'), ('E0','E1'))):
        raise ValueError('Accepted N3 derivative must implement all sixteen compositions')
    matrix = []
    for a,d,e in product(('A0','A1','A2','A3'), ('D0','D1'), ('E0','E1')):
        backend = catalog[(a,d,e)]
        matrix.append(dict(id='_'.join((a,d,e)), asr=a, diarization=d, embedding=e,
            punctuation='P0_final_only' if a in ('A0','A1') else 'P1_native',
            required=480, completed=0, failed=0, incompatible=0, not_tested=480,
            implementation_status='IMPLEMENTED_VALIDATION_PENDING' if backend else 'ADAPTER_NOT_YET_IMPLEMENTED',
            admission_status='NOT_TESTED_PREREQUISITES_PENDING', backend_key=backend['key'] if backend else None,
            backend_manifest_id=backend['manifest_id'] if backend else None,
            composition=backend['composition'] if backend else None,
            compatibility='PENDING; missing adapter is not a scientific model-family rejection',
            deployment_tier='UNKNOWN', rescue_used=0, operational_name_calibration='UNCALIBRATED_REJECT_ALL'))
    payloads = {
        'AUDIO_ONLY_480.json': dict(schema='n4-audio-only-v1', jobs=jobs),
        'PACED_AUDIO_ONLY_24.json': dict(schema='n4-audio-only-v1', jobs=[j for j in jobs if j['job_id'][3:-3] in paced]),
        'REGRESSION_AUDIO_ONLY_8.json': load(args.local/'n2/evaluation/REGRESSION_AUDIO_ONLY.json'),
        'EVALUATOR_STRATA.json': dict(schema='n4-evaluator-strata-v1', NEVER_PASS_TO_RUNTIME=True, scenes=strata),
        'PAIRED_CAPTURE_PROVENANCE.json': dict(schema='n4-pairs-v1', pairs=pairs),
        'MATRIX_PREPARATION.json': dict(schema='n4-matrix-v1', status='PREPARATION_NOT_COMPLETE', rows=matrix),
    }
    for name, value in payloads.items():
        freeze(args.output/name, value)
    receipt = dict(schema='n4-data-preparation-v1', status='ACTUALLY_RUN_MODEL_FREE',
        inputs=[bind(audit_path), bind(corpus_path), bind(truth_path), bind(catalog_path), bind(__file__), bind(HERE/'common.py'), bind(HERE/'compose_release_v3.py')],
        outputs=[bind(args.output/name) for name in payloads], scenes=240, waveform_files_verified=480,
        paired_physical_passes=240, reference_classes=counts,
        required_core_results=7680, completed_core_results=0, failed_core_results=0, incompatible_core_results=0,
        not_tested_core_results=7680, neural_calls=0, hardware_calls=0,
        total_audio_seconds_one_composition=sum(j['frames']/16000 for j in jobs),
        paced_panel_scene_ids=paced, paced_cells=24,
        dependency_clusters=len(set(dependencies.values())), actor_clusters=len(set(actor.values())),
        matched_clusters=len(set(matched.values())),
        uncertainty='Paired dependency-cluster bootstrap; fewer than 8 clusters suppresses inferential CI. Matched/room/actor sensitivity remains descriptive.',
        raw_transcripts_in_public_report=False, inference_truth_firewall='exact eight audio fields only')
    freeze(args.output/'PREPARATION_RECEIPT.json', receipt)
    print(__import__('json').dumps({k:v for k,v in receipt.items() if k not in ('inputs','outputs')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local', type=Path, default=LOCAL)
    parser.add_argument('--source', type=Path, default=LOCAL/'releases/n4-catalog-v3/prototype')
    parser.add_argument('--output', type=Path, required=True)
    prepare(parser.parse_args())
