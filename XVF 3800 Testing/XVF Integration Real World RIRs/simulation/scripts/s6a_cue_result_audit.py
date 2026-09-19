"""Audit complete reference coverage and independent B0 text parity; README_S6A_CUES.md."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
from s6a_cues import read, save, binding, verified, load_jobs, PROFILES, DEFAULT_REPORT, now


def audit(report=DEFAULT_REPORT):
    report=Path(report)
    receipt=read(report/'REFERENCE_PROFILE_RECEIPT.json')
    if receipt['status']!='COMPLETE':raise ValueError('Reference scoring must be complete first.')
    jobs,bank=load_jobs(report)
    scene_counts={s['case_id']:sum(t['kind']=='utterance' for t in s['segments']) for s in bank['scenes']}
    counts={(j['case_id'],j['stream']):scene_counts[j['case_id']] for j in jobs}
    # The manifest's intentionally inserted utterances, including limited-reference
    # mixtures, remain the denominator. Empty controls have zero inserted turns.
    expected=sum(counts[(s['case_id'],'O0')] for s in bank['scenes'])
    if expected!=777:raise ValueError('The exact current bank does not match the expected 777 inserted utterances.')
    with (report/'REFERENCE_PROFILE_TURN_RESULTS.csv').open(encoding='utf-8-sig',newline='') as h:turns=list(csv.DictReader(h))
    with (report/'REFERENCE_SHORT_TURN_RESULTS.csv').open(encoding='utf-8-sig',newline='') as h:short=list(csv.DictReader(h))
    turn_counts=Counter((r['case_id'],r['stream'],r['profile']) for r in turns)
    short_counts=Counter()
    for r in short:short_counts[(r['case_id'],r['stream'],r['profile'])]+=int(r['source_turns'])
    profiles=list(PROFILES)+['CONTROL_ONE_PERSON','CONTROL_ALL_UNKNOWN']
    for (cid,stream),n in counts.items():
        for profile in profiles:
            key=(cid,stream,profile)
            if turn_counts[key]!=n or short_counts[key]!=n:
                raise ValueError('Missing or duplicated turn/short-bin coverage: '+repr(key))
    reference_index=read(report/'cues/REFERENCE_INDEX.json')
    predictions={(r['case_id'],r['stream'],r['profile']):r for r in reference_index['rows']}
    lexical=0;parity=[];pending=[];revisions=[]
    cost=dict(unique_redim_vectors=0,measured_embedding_compute_sec=0.,inherited_native_segmentation_compute_sec=0.,
              policy_wall_sec_by_profile={p:0. for p in PROFILES},
              scope='One shared exact feature bank; per-profile policy cost is additional. Inherited segmentation is not recomputed; desktop timing does not qualify CM5.')
    for job in jobs:
        cid,stream=job['case_id'],job['stream']
        baseline=read(verified(predictions[(cid,stream,'B0')]['result']))
        cost['unique_redim_vectors']+=len(baseline['decisions'])
        cost['measured_embedding_compute_sec']+=baseline['feature_model_cost_sec']
        cost['inherited_native_segmentation_compute_sec']+=baseline['inherited_segmentation_cost_sec']
        original=[r['text'] for r in baseline['final_transcripts']]
        for profile in PROFILES:
            value=read(verified(predictions[(cid,stream,profile)]['result']))
            if [r['text'] for r in value['final_transcripts']]!=original:
                raise ValueError('A fixed-ASR reference changed final words: '+repr((cid,stream,profile)))
            cost['policy_wall_sec_by_profile'][profile]+=value['policy_wall_sec']
            for i,decision in enumerate(value['decisions']):
                emitted=[e for e in decision.get('lineage',[]) if e['event']=='label_revision']
                if emitted:
                    revisions.append(dict(case_id=cid,stream=stream,profile=profile,
                                          prediction=predictions[(cid,stream,profile)]['result'],
                                          preceding_and_current_decisions=value['decisions'][max(0,i-1):i+1],
                                          emitted_revisions=emitted,
                                          revised_identity_correctness='NOT_CLAIMED; no retroactive first-decision or text credit'))
            lexical+=1
        external=report/'baseline_metrics'/cid/(stream+'.json')
        if not external.exists():pending.append(dict(case_id=cid,stream=stream));continue
        a=read(external)['text_metrics']['attributed_cpwer']
        score_path=report/'cues/scores'/cid/stream/'B0.json'
        b=read(score_path)['attributed_cpwer']
        if a.get('word_counts')!=b.get('word_counts') or a.get('wer')!=b.get('wer'):
            raise ValueError('B0 cpWER disagrees with independent original-setting scorer: '+repr((cid,stream)))
        parity.append(dict(case_id=cid,stream=stream,baseline_metric=binding(external),reference_score=binding(score_path),
                           reference_words=(a.get('word_counts') or {}).get('reference_words'),status='PASS'))
    controls=[]
    for stream in ('O0','O1'):
        group={r['profile']:r for r in receipt['summary'] if r['stream']==stream and r['population']=='ALL_COMPLETE_NONEMPTY'}
        unknown=group['CONTROL_ALL_UNKNOWN'];single=group['CONTROL_ONE_PERSON']
        if unknown['unknown_samples']!=unknown['sole_active_samples'] or unknown['known_samples']!=0:
            raise ValueError('All-unknown control escaped the unknown denominator.')
        if single['unknown_samples'] or single['false_merge_samples']<=0:
            raise ValueError('One-person control failed to expose mixed identity on the complete bank.')
        controls.append(dict(stream=stream,all_unknown_fraction=unknown['unknown_fraction'],
                             one_person_mixed_identity_fraction=single['false_merge_samples']/single['sole_active_samples'],
                             one_person_return_consistent=single['return_consistent'],
                             scope='Perfect continuity is not identity accuracy; all unknowns remain penalized as unassigned support.'))
    result=dict(schema='jp_s6a_reference_coverage_parity_v1',status='PASS' if len(parity)==480 else 'PARTIAL_BASELINE_SCORER_PENDING',
                inserted_utterances=expected,scene_tap_profile_outputs=3840,retained_turn_rows=len(turns),
                expected_turn_rows=expected*16,short_bin_source_turn_sum=sum(short_counts.values()),
                unchanged_final_word_sequences=lexical,baseline_metric_parity_outputs=len(parity),
                pending_baseline_metrics=pending,controls=controls,parity=parity,cost=cost,
                reference_receipt=binding(report/'REFERENCE_PROFILE_RECEIPT.json'),code=binding(__file__),created_utc=now())
    save(report/'CUE_OBSERVED_REVISIONS.json',dict(status='COMPLETE',revision_events=sum(len(r['emitted_revisions']) for r in revisions),
                                                excerpts=revisions,scope='Actual immutable reference traces; lineage capability is separate from correctness and transcript revisions',
                                                created_utc=now()))
    result['observed_revision_excerpt']=binding(report/'CUE_OBSERVED_REVISIONS.json')
    save(report/'CUE_REFERENCE_COVERAGE_PARITY.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,default=DEFAULT_REPORT)
    output=audit(parser.parse_args().report)
    print(json.dumps({k:v for k,v in output.items() if k!='parity'},indent=2))
