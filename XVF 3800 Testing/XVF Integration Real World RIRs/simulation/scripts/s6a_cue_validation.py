"""Bound cue tests, real-feature causal checks and physical strata; README_S6A_CUES.md."""
from __future__ import annotations
from collections import Counter
from dataclasses import replace
import csv
import io
import json
import math
from pathlib import Path
import time
import unittest
import numpy as np
from s6a_cues import (read,save,binding,verified,write_csv,DEFAULT_REPORT,BANK,H2,MODES,run_policy,
                     load_jobs,load_bridge,digest,now)
from s6a_text_metrics import reference_layout


def run_tests(report):
    modules=('test_s6a_cues','test_s6a_cue_score','test_s6a_cue_delivery')
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in modules)
    output=io.StringIO();result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    folder=Path(__file__).parent
    receipt=dict(schema='jp_s6a_cue_fixture_tests_v1',status='PASS' if result.wasSuccessful() else 'FAIL',
                 tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
                 modules=list(modules),output=output.getvalue(),created_utc=now(),
                 source_bindings=[binding(folder/(name+'.py')) for name in modules+
                                  ('s6a_cues','s6a_cue_score','s6a_cue_delivery')]+
                                 [binding(H2/'app/edge_speech_pipeline/research_tracking.py')])
    save(report/'CUE_FIXTURE_TEST_RECEIPT.json',receipt)
    if not result.wasSuccessful():raise AssertionError('cue fixture tests failed')
    return receipt


class AlteredFutureBridge:
    def __init__(self,base,cutoff):self.base=base;self.cutoff=cutoff
    def observation(self,end,available):
        original=self.base.observation(end,available)
        if original is None or end<=self.cutoff:return original
        return replace(original,angle_deg=None if original.angle_deg is None else 180.-original.angle_deg)


class UnavailableBridge:
    def __init__(self,base,stale=False):self.base=base;self.stale=stale
    def observation(self,end,available):
        if not self.stale:return None
        original=self.base.observation(end,available)
        return None if original is None else replace(original,available_at_sec=end-1.)


def real_feature_checks(report):
    jobs,_=load_jobs(report);lookup={(j['case_id'],j['stream']):j for j in jobs}
    index=read(report/'cues/FEATURE_INDEX.json');ready=[r for r in index['rows'] if r['status']=='COMPLETE']
    # Deterministic evenly spaced ready-output positions, independent of labels
    # or correctness. Empty/short feature streams remain explicit test cases.
    selection=sorted(set(round(i*(len(ready)-1)/11) for i in range(min(12,len(ready)))))
    rows=[];started=time.perf_counter()
    for position in selection:
        item=ready[position];record=read(verified(item['result']));features=record['features']
        vectors=np.load(verified(record['vectors']),allow_pickle=False)['vectors']
        bridge,telemetry_bindings=load_bridge(lookup[(item['case_id'],item['stream'])])
        prefix=len(features)//2;cutoff=features[prefix-1]['source_end_sec'] if prefix else -1.
        altered=vectors.copy()
        if len(altered)>prefix:altered[prefix:]=-altered[prefix:][::-1]
        renamed=[dict(f,true_speaker='renamed',reference_transcript='unavailable',room='unused') for f in features]
        voice,_=run_policy(features,vectors,'voice_time')
        profile_results=[]
        for mode in MODES:
            original,_=run_policy(features,vectors,mode,bridge)
            other,_=run_policy(features,altered,mode,AlteredFutureBridge(bridge,cutoff))
            if original[:prefix]!=other[:prefix]:raise AssertionError('future suffix affected first decisions')
            labels=[d['anonymous_label'] for d in original]
            renamed_result,_=run_policy(renamed,vectors,mode,bridge)
            if original!=renamed_result:raise AssertionError('truth rename affected prediction')
            checks=dict(mode=mode,prefix_decisions=prefix,future_audio_and_metadata_prefix_invariant=True,
                        truth_rename_invariant=True,decision_availability_valid=all(d['available_at_sec']>=d['source_end_sec'] for d in original))
            if mode!='angle_diagnostic':
                for stale in (False,True):
                    missing,_=run_policy(features,vectors,mode,UnavailableBridge(bridge,stale))
                    if [d['anonymous_label'] for d in missing]!=[d['anonymous_label'] for d in voice]:
                        raise AssertionError('unavailable metadata is not exact voice-only label fallback')
                checks['missing_and_stale_voice_fallback_exact']=True
            profile_results.append(checks)
        chunk_labels=[];chunk_availability=[]
        for chunk in (.02,.1):
            changed=[dict(f,available_at_sec=math.ceil((f['source_end_sec']-1e-9)/chunk)*chunk+
                          f['available_at_sec']-f['source_end_sec']) for f in features]
            prediction,_=run_policy(changed,vectors,'voice_time')
            chunk_labels.append([p['anonymous_label'] for p in prediction]);chunk_availability.append([p['available_at_sec'] for p in prediction])
        if chunk_labels[0]!=chunk_labels[1]:raise AssertionError('voice-only labels changed under host chunk grouping')
        rows.append(dict(case_id=item['case_id'],stream=item['stream'],feature_count=len(features),
                         feature_binding=item['result'],telemetry_bindings=telemetry_bindings,profiles=profile_results,
                         host_chunk_patterns_sec=[.02,.1],host_chunk_voice_labels_invariant=True,
                         host_chunk_availability_equal=chunk_availability[0]==chunk_availability[1]))
    result=dict(schema='jp_s6a_real_feature_causality_v1',status='PASS',rows=rows,
                selected_outputs=len(rows),distinct_policy_trials=sum(len(r['profiles']) for r in rows),
                nonempty_prefix_trials=sum(p['prefix_decisions']>0 for r in rows for p in r['profiles']),
                feature_index_binding=binding(report/'cues/FEATURE_INDEX.json'),created_utc=now(),elapsed_sec=time.perf_counter()-started,
                scope='Exact existing physical-bank vectors, no extra inference; state/availability causality, not accuracy or live latency')
    save(report/'CUE_REAL_FEATURE_CAUSALITY.json',result);return result


def cue_strata(report):
    scenes={s['case_id']:s for s in read(BANK)['scenes']}
    populations={cid:reference_layout(s)['population'] for cid,s in scenes.items()}
    with (report/'CUE_UTTERANCE_RELIABILITY.csv').open(encoding='utf-8') as handle:rows=list(csv.DictReader(handle))
    summary=[]
    for population in sorted(set(populations.values())):
        for stream in sorted({r['stream'] for r in rows}):
            selected=[r for r in rows if r['stream']==stream and populations[r['case_id']]==population]
            if not selected:continue
            seconds=sum(float(r['support_duration_s']) for r in selected)
            usable=sum(float(r['speech_energy_gated_coverage'] or 0)*float(r['support_duration_s']) for r in selected)
            matched=sum(float(r['matching_sector_occupancy'] or 0)*float(r['support_duration_s']) for r in selected)
            summary.append(dict(population=population,stream=stream,utterances=len(selected),summed_source_support_sec=seconds,
                                usable_sec=usable,usable_fraction=usable/seconds if seconds else None,
                                matching_sector_sec=matched,matching_sector_fraction=matched/seconds if seconds else None,
                                wrong_sector_sec=sum(float(r['wrong_sector_duration_s'] or 0) for r in selected),
                                held_wrong_sector_sec=sum(float(r['held_wrong_sector_duration_s'] or 0) for r in selected),
                                sustained_never_acquired=sum(r['sustained_acquisition_censored']=='True' for r in selected)))
    write_csv(report/'CUE_RELIABILITY_BY_POPULATION.csv',summary)
    primary=[dict(r,population=populations[r['case_id']]) for r in rows if r['stream']=='selected_processed' and populations[r['case_id']]=='PRIMARY_NONOVERLAP']
    adverse=sorted(primary,key=lambda r:-float(r['held_wrong_sector_duration_s'] or 0))[:15]
    for r in adverse:r['selection']='Posthoc descriptive adverse examples; not candidate selection or independent samples'
    write_csv(report/'CUE_ADVERSE_EXAMPLES.csv',adverse)
    return summary


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,default=DEFAULT_REPORT)
    args=parser.parse_args();fixture=run_tests(args.report);actual=real_feature_checks(args.report);strata=cue_strata(args.report)
    receipt=dict(schema='jp_s6a_cue_tests_v1',status='PASS',fixture_tests=fixture['tests'],
                 actual_feature_outputs=actual['selected_outputs'],actual_policy_trials=actual['distinct_policy_trials'],
                 fixtures=binding(args.report/'CUE_FIXTURE_TEST_RECEIPT.json'),
                 actual_features=binding(args.report/'CUE_REAL_FEATURE_CAUSALITY.json'),
                 population_table=binding(args.report/'CUE_RELIABILITY_BY_POPULATION.csv'),
                 adverse_examples=binding(args.report/'CUE_ADVERSE_EXAMPLES.csv'),created_utc=now(),code=binding(__file__))
    save(args.report/'CUE_TEST_RECEIPT.json',receipt);print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
