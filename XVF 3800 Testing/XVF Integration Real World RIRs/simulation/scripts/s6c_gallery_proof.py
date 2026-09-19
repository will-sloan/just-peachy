"""Actual cached-C gallery branch proof. See README_S6C_GALLERY_PROOF.md."""
from __future__ import annotations

import argparse
import collections
from copy import deepcopy
import math
from pathlib import Path
import sys
import time

import numpy as np
import soundfile as sf

import s6c_enrollment as E

OUT = E.REPORT / 'enrollment/gallery_branch_proof_v1'


def clip_support(source, left, right):
    return [[max(left, a), min(right, b)] for a, b in source['quality']['active_ranges_samples_estimated']
            if max(left, a) < min(right, b)]


def selected_queries(pool, sources):
    grouped = collections.defaultdict(list)
    for index, row in enumerate(pool):
        source = sources[row['source_id']]
        a, b = row['source_start_sample'], row['source_end_sample']
        clean = clip_support(source, a, b)
        fraction = sum(y-x for x, y in clean)/(b-a)
        if b-a == 32000 and fraction >= .5:
            grouped[row['metadata_identity']].append(dict(row=row, pool_index=index, clean=clean))
    return {k: sorted(v, key=lambda r: (r['row']['source_id'], r['row']['source_start_sample']))[:6]
            for k, v in grouped.items() if len(v) >= 6}


def make_events(chunks, sources):
    events, provenance = [], []
    offset, prior_source = 0., None
    previous_end = 0.
    for index, entry in enumerate(chunks):
        row = entry['row']
        source = sources[row['source_id']]
        if row['source_id'] != prior_source:
            offset = previous_end + (1. if index else 0.) - row['source_start_sample']/16000
            prior_source = row['source_id']
        a, b = row['source_start_sample'], row['source_end_sample']
        start, end = offset+a/16000, offset+b/16000
        clean = [[offset+x/16000, offset+y/16000] for x, y in entry['clean']]
        waveform, rate = sf.read(source['decoded_16k_binding']['path'], dtype='float32', start=a, stop=b)
        if rate != 16000 or waveform.ndim != 1 or len(waveform) != b-a:
            raise ValueError('Bound actual C waveform interval differs')
        event_id = f'Cproof:{index:06d}'
        event = dict(kind='embedding', event_id=event_id, observation_id=event_id,
            vector=row['vector'], source_start_sec=start, source_end_sec=end,
            receptive_start_sec=start, receptive_end_sec=end, available_at_sec=end+.001,
            speech=True, overlap=False, evidence_kind='mature', clean_intervals=clean,
            clean_fraction=sum(y-x for x, y in clean)/(end-start),
            rms=float(np.sqrt(np.mean(waveform.astype(np.float64)**2))),
            clipping_fraction=float(np.mean(np.abs(waveform) >= .999)))
        events.append(event)
        provenance.append(dict(event_id=event_id, C_pool_row=entry['pool_index'], source_id=row['source_id'],
            scorer_only_metadata_identity=row['metadata_identity'], source_binding=source['decoded_16k_binding'],
            original_source_binding=source['source_binding'], original_source_start_sample=a, original_source_end_sample=b,
            modeled_timeline_offset_sec=offset, estimated_clean_source_ranges_samples=entry['clean']))
        previous_end = end
    return events, provenance


def drive(profile, gallery, events):
    from edge_speech_pipeline.research_scheduler_v3 import build_s6c_policy
    scheduler = build_s6c_policy(profile, gallery)
    records = []
    start = time.perf_counter()
    for event in events:
        records.extend(scheduler.push(event, lane='speaker'))
        cursor = math.nextafter(event['available_at_sec'], math.inf)
        records.extend(scheduler.advance({'speaker': cursor, 'asr': cursor}))
    records.extend(scheduler.finish())
    return dict(records=records, snapshot=scheduler.snapshot(), tracker_snapshot=scheduler.tracker.snapshot(),
                policy_elapsed_sec=time.perf_counter()-start)


def run():
    done_path = OUT / 'GALLERY_BRANCH_PROOF.json'
    if done_path.exists():
        receipt = E.read(done_path)
        for b in receipt['bindings']:
            E.verify(b)
        for r in receipt['conditions']:
            E.verify(r['result'])
        return dict(status='VERIFIED_EXISTING_BRANCH_PROOF', receipt=E.bind(done_path), model_calls=0)
    E.verify_complete()
    epoch_path = E.REPORT / 'EPOCH1_EXECUTION_MANIFEST.json'
    epoch = E.read(epoch_path)
    for b in epoch['execution_files']:
        E.verify(b)
    sys.path.insert(0, str(Path(epoch['root'])/'app'))
    from edge_speech_pipeline.research_profiles import ResearchProfile
    from edge_speech_pipeline.research_identity_v3 import ResearchGallery
    registry_path = E.REPORT/'EFFECTIVE_PROFILE_REGISTRY_V1.json'
    registry = E.read(registry_path)
    base = next(x for x in registry['profiles'] if x['candidate_id'] == 'C088' and x['asr_tap'] == x['identity_tap'] == 'O0')
    E.verify(base['profile_binding'])
    profile = ResearchProfile.from_dict(base['profile'])
    if profile.identity.score_threshold != .5128856897354127 or profile.identity.margin_threshold != .03:
        raise ValueError('Original inherited thresholds required for branch proof')
    plan = E.read(E.PLAN)
    material = E.read(plan['material_manifest']['path'])
    sources = {x['source_id']: x for x in material['accepted_sources']}
    cpath = E.PAYLOAD/'calibration/C_WINDOW_EMBEDDINGS.json'
    cpool = E.read(cpath)['rows']
    usable = selected_queries(cpool, sources)
    map_path = E.OUT/'SCORER_GALLERY_MAP.json'
    mapping = E.read(map_path)['rows']
    A = next(x for x in mapping if x['gallery_condition']=='FIXED_ROTATION_A' and x['enrollment_tier']==15 and x['case_id'] is None)
    B = next(x for x in mapping if x['gallery_condition']=='FIXED_ROTATION_B' and x['enrollment_tier']==15 and x['case_id'] is None)
    primary = sorted(set(A['available_identities']) & set(usable))[0]
    conflict = sorted(set(B['available_identities']) & set(usable))[0]
    singles = [x for x in mapping if x['enrollment_tier']==15 and len(x['available_identities'])==1
               and primary not in x['available_identities']]
    distractor = sorted(singles, key=lambda x: (x['available_identities'], x['gallery_condition'], x['case_id'] or ''))[0]
    conditions = [('CORRECT_REFERENCE_PRESENT', A, usable[primary]),
                  ('SAME_PERSON_ABSENT', B, usable[primary]),
                  ('DISTRACTOR_ONLY_PRESENT', distractor, usable[primary]),
                  ('CONFLICTING_OTHER_VOICE_AFTER_PRIMARY', A, usable[primary]+usable[conflict])]
    prepared = []
    for label, gallery, chunks in conditions:
        events, provenance = make_events(chunks, sources)
        prepared.append(dict(condition=label, gallery=gallery['manifest'], events=events, provenance=provenance))
    freeze = dict(schema='s6c-real-C-gallery-proof-plan.v1', status='FROZEN_BEFORE_BRANCH_RESULTS',
        code=E.bind(__file__), readme=E.bind(Path(__file__).with_name('README_S6C_GALLERY_PROOF.md')),
        epoch=E.bind(epoch_path), profile=base['profile_binding'], C_pool=E.bind(cpath),
        enrollment_completion=E.bind(E.OUT/'ENROLLMENT_COMPLETION.json'), scorer_map=E.bind(map_path),
        primary_scorer_only_identity=primary, conflict_scorer_only_identity=conflict,
        selection='Lexicographically first eligible fixed-A and fixed-B people with6 full2s C windows and >=0.5 estimated activity fraction; no cosine/outcome selection',
        conditions=prepared,
        evidence_scope='Real cached normalized C vectors; numerical source-activity support; modeled sequential diagnostic timeline. No new waveform synthesis or graph calls; not actual segmentation/ASR/source-clock capture.')
    E.save(OUT/'BRANCH_PLAN.json', freeze)
    bindings = [E.bind(OUT/'BRANCH_PLAN.json'), freeze['code'], freeze['readme'], freeze['epoch'],
                freeze['profile'], freeze['C_pool'], freeze['enrollment_completion'], freeze['scorer_map']]
    backend = next(a['sha256'] for a in plan['assets'] if a['component_id']=='redimnet2_b2_fp32')
    rows = []
    for condition in prepared:
        E.verify(condition['gallery'])
        gallery = ResearchGallery(condition['gallery']['path'], backend, profile.identity.max_gallery_profiles)
        result = drive(profile, gallery, condition['events'])
        decisions = [x['decision'] for x in result['records'] if x['event_type']=='speaker_decision']
        if len(decisions) != len(condition['events']):
            raise ValueError('Actual scheduler lost a C event')
        truth_names = {x: plan['people'][x]['display_name'] for x in (primary, conflict)}
        true = [truth_names[x['scorer_only_metadata_identity']] for x in condition['provenance']]
        named = [(d.get('known_name'), d.get('naming_state')) for d in decisions]
        counts = dict(queries=len(decisions), actual_name_queries=sum(d['identity']['query_executed'] for d in decisions),
            correct_confirmed=sum(name==t and state=='confirmed' for (name,state),t in zip(named,true)),
            correct_tentative=sum(name==t and state=='tentative' for (name,state),t in zip(named,true)),
            wrong_name=sum(name is not None and name!=t for (name,state),t in zip(named,true)),
            unresolved=sum(name is None for name,state in named),
            tracker_ids=sorted({d['tracker_id'] for d in decisions if d['tracker_id'] is not None}))
        result.update(schema='s6c-actual-gallery-branch-result.v1', condition=condition['condition'],
            gallery_load=gallery.receipt, input_events=condition['events'], scorer_only_provenance=condition['provenance'],
            counts=counts, model_calls=0, ASR_calls=0, hardware_passes=0, thresholds_unchanged=True)
        p = OUT/(condition['condition']+'.json')
        E.save(p,result)
        rows.append(dict(condition=condition['condition'],counts=counts,result=E.bind(p),gallery=condition['gallery']))
    receipt = dict(schema='s6c-gallery-branch-proof.v1',status='COMPLETE_ACTUAL_C_VECTOR_MECHANISM_OBSERVATIONS',
        created_utc=E.utc(),bindings=bindings,conditions=rows,model_calls=0,new_template_calls=0,hardware_passes=0,
        thresholds=dict(score=profile.identity.score_threshold,margin=profile.identity.margin_threshold,
                        minimum_unique_sec=profile.identity.minimum_unique_sec,minimum_disjoint_count=profile.identity.minimum_disjoint_count),
        scope='Actual frozen v3 tracker+identity scheduler and actual native ProfileStore on cached C vectors. Mechanism controls only; not Q accuracy, native full-pipeline confirmation, latency or cohort generalization.',
        clean_support_scope='Numeric C-source activity mask, not an observed pyannote segmentation result; no reference person label is passed to the scheduler.',
        timeline='Modeled sequential concatenation of evidence coordinates with1s gaps between source clips, availability=end+1ms. No physical playback or measured timing claim.',
        transcript_scope='No invented transcript/ASR input; this proof observes speaker/identity events. Root performs separate native fullRuntime gallery integration.')
    E.save(done_path,receipt)
    return dict(status=receipt['status'],conditions=rows,receipt=E.bind(done_path))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    import json
    print(json.dumps(run(),indent=2),flush=True)
