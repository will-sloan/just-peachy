"""Evaluator-only S6D angle overlays. See README_S6D_ANGLE_RESCORE.md."""
from __future__ import annotations

import argparse
import bisect
import collections
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import time

# Load the correct NumPy ABI before legacy telemetry code adjusts its imports.
import numpy as np
from s4_geometry import source_label, lab_to_native_deg, angle_error, coarse_sector
from s4_spatial_analysis import ReceiptTimeline, STREAMS, union

SIM = Path(__file__).resolve().parents[1]
S6C = SIM / 'reports/S6C/20260910T123540Z'
WIDTHS = (5., 2., 0.)
THRESHOLDS = (0., 5., 10., 20., 35.)
POLICY = {
    'manual_original_half_width_deg': 5., 'evaluation_overlays_deg': WIDTHS,
    'tolerance_thresholds_deg': THRESHOLDS,
    'coordinate': 'acos(-sin(lab)), folded linear 0..180; endpoints distinct',
    'observation_gate': 'Unchanged S4 ReceiptTimeline with 250 ms receipt/transaction rules and original stream energy gates',
    'primary_population': 'Exactly one active source interval, matching S6C turn diagnostics; all cases retained, empty/invalid turns explicitly present',
    'duration_weighting': 'Causal state interval duration intersected with callback-quantized estimated source activity',
    'coarse_sector': 'Unchanged nominal right[0,60), central[60,120], left(120,180]',
    'interval_sector': 'Allowed sectors intersecting the entire folded closed manual interval; reported separately from nominal sector',
    'strict_sector_population': 'Supplement excludes intervals crossing a coarse-sector boundary; list changing population explicitly',
    'stable_wrong': 'Observed within-turn std <=10 and duration-weighted mean absolute NOMINAL error >=35, independent of manual width',
    'pair_separation': 'Measured difference of turn means; same-person and distinct-person pairs separate; signed reference labels evaluator only',
    'pair_interval_gap': 'Minimum native interval distance; diagnostic thresholds 0,5,10,20,35 unrelated to a production speaker-change threshold',
    'acquisition': 'Reuse verified S4 nominal-sector first and sustained80%-over1s receipts; original per-source envelope population including limited-overlap diagnostics; never-acquired null/censored retained',
    'no_audio_change': True, 'no_model_calls': True, 'no_predictor_calls': True,
    'prediction_invariance_scope': 'All240/both taps C065/C079/C088/C091 frozen compatible policy outputs and full core scores; original A15/B15 naming scores. Byte binding and evaluator graph invariance, not new ASR execution.',
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def bind(path):
    path = Path(path).resolve()
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), str(path)
    return dict(path=str(path), bytes=after.st_size, sha256=h.hexdigest())


def verify(binding):
    actual = bind(binding['path'])
    assert actual['sha256'] == binding['sha256'] and actual['bytes'] == binding['bytes'], str(actual)
    return actual


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def csv_save(path, rows):
    rows = list(rows)
    with Path(path).open('x', encoding='utf-8', newline='') as f:
        fields = list(dict.fromkeys(k for row in rows for k in row))
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def mean(values):
    total = sum(w for _, w in values)
    return sum(v*w for v, w in values)/total if total else None


def allowed_sectors(label):
    lo, hi = label['expected_native_interval_deg']
    # acos/sin can yield 120.00000000000001 for the exact +30 lab boundary.
    # Snap evaluator interval bounds only; historical nominal-sector scores stay exact.
    lo = next((v for v in (0.,60.,120.,180.) if abs(lo-v)<1e-9),lo)
    hi = next((v for v in (0.,60.,120.,180.) if abs(hi-v)<1e-9),hi)
    # Sector boundaries are closed only in the central sector.
    sectors = set()
    if lo < 60: sectors.add('right')
    if hi >= 60 and lo <= 120: sectors.add('central_ambiguous')
    if hi > 120: sectors.add('left')
    return sectors


def interval_gap(left, right):
    a, b = left['expected_native_interval_deg']
    c, d = right['expected_native_interval_deg']
    return max(c-b, a-d, 0.)


def checks():
    count = 0
    def check(test):
        nonlocal count
        assert test
        count += 1
    # Analytic controls exercise wrap, folds, endpoints, sector boundary rules.
    for signed, expected in ((0,90),(90,180),(-90,0),(180,90),(-180,90),(270,0)):
        check(math.isclose(lab_to_native_deg(signed), expected, abs_tol=1e-7))
    check(angle_error(180, source_label(-90,0))['nominal_error_deg'] == 180)
    for signed, bounds in ((89,(174,180)),(-89,(0,6)),(179,(86,96)),(-179,(84,94))):
        actual = source_label(signed,5)['expected_native_interval_deg']
        check(all(math.isclose(a,b,abs_tol=1e-7) for a,b in zip(actual,bounds)))
    check(allowed_sectors(source_label(-30,0)) == {'central_ambiguous'})
    check(allowed_sectors(source_label(30,0)) == {'central_ambiguous'})
    check(allowed_sectors(source_label(-30,2)) == {'right','central_ambiguous'})
    example = [angle_error(125,source_label(0,w))['interval_error_deg'] for w in WIDTHS]
    check(all(math.isclose(a,b,abs_tol=1e-8) for a,b in zip(example,(30,33,35))))
    rng = random.Random(20260913)
    for _ in range(3000):
        signed = rng.uniform(-1800,1800)
        obs = rng.uniform(0,180)
        labels = [source_label(signed,w) for w in WIDTHS]
        errors = [angle_error(obs,label) for label in labels]
        check(errors[0]['interval_error_deg'] <= errors[1]['interval_error_deg'] + 1e-10 <= errors[2]['interval_error_deg'] + 2e-10)
        check(all(math.isclose(e['nominal_error_deg'], errors[0]['nominal_error_deg'],abs_tol=1e-10) for e in errors))
        check(allowed_sectors(labels[0]) >= allowed_sectors(labels[1]) >= allowed_sectors(labels[2]))
        # Independent dense sampling verifies interior extrema, rather than endpoint-only folding.
        for w,label in zip(WIDTHS,labels):
            lo,hi = label['expected_native_interval_deg']
            vals = [lab_to_native_deg(signed-w+2*w*i/20) for i in range(21)]
            check(min(vals) >= lo-1e-6 and max(vals) <= hi+1e-6)
        opposite = rng.uniform(-180,180)
        gaps = [interval_gap(a,source_label(opposite,w)) for a,w in zip(labels,WIDTHS)]
        check(gaps[0] <= gaps[1]+1e-7 <= gaps[2]+2e-7)
    check(angle_error(None, source_label(0))['nominal_error_deg'] is None)
    return dict(status='PASS', assertions=count, seeded_property_draws=3000,
                analytic_example_interval_errors_deg=example, endpoints_distinct=True)


def freeze(out):
    review_path = S6C/'independent_review/PHYSICAL_CUE_METRIC_REVIEW_V1.json'
    review = read(review_path)
    assert review['status'] == 'PASS'
    bound = [verify(b) for b in review['sources']]
    index = read(S6C/'cue_audit_v1/PHYSICAL_CUE_AUDIT.json')
    assert len(index['rows']) == 240 and len({r['case_id'] for r in index['rows']}) == 240
    source_paths = [Path(__file__), Path(__file__).with_name('README_S6D_ANGLE_RESCORE.md'),
        SIM/'scripts/s4_geometry.py', SIM/'scripts/s4_spatial_analysis.py', SIM/'scripts/s4_telemetry.py',
        review_path, S6C/'cue_audit_v1/PHYSICAL_CUE_AUDIT_PLAN.json',
        S6C/'epoch4/full_n01_anonymous_v1_PREDICTION_INDEX.json',
        S6C/'epoch4/full_n01_naming_v1_PREDICTION_INDEX.json',
        S6C/'full_n01_anonymous_core_v3/ANALYSIS_RECEIPT.json',
        S6C/'full_n01_naming_core_v3/ANALYSIS_RECEIPT.json',
        S6C/'full_n01_naming_names_v3/NAME_ANALYSIS_RECEIPT.json']
    plan = dict(schema='s6d-angle-plan.v1', created_utc=datetime.now(timezone.utc).isoformat(),
        status='PREDECLARED_EVALUATOR_ONLY', policy=POLICY, sources=bound+[bind(p) for p in source_paths],
        case_bindings=index['rows'], checks=checks())
    save(out/'PLAN.json', plan)
    return plan


def score_samples(samples, label, support_sec):
    valid = sum(w for _,w in samples)
    nominal = label['expected_native_nominal_deg']
    errors = [(angle_error(v,label)['interval_error_deg'],w) for v,w in samples]
    sectors = allowed_sectors(label)
    result = dict(support_sec=support_sec, usable_sec=valid,
        nominal_error_mean_deg=mean([(abs(v-nominal),w) for v,w in samples]),
        interval_error_mean_deg=mean(errors),
        nominal_sector_matching_sec=sum(w for v,w in samples if coarse_sector(v)==coarse_sector(nominal)),
        allowed_interval_sector_matching_sec=sum(w for v,w in samples if coarse_sector(v) in sectors),
        strict_single_sector_eligible=len(sectors)==1)
    for tolerance in THRESHOLDS:
        result['interval_within_'+str(int(tolerance))+'_deg_sec'] = sum(w for e,w in errors if e<=tolerance+1e-9)
    return result


def case_rescore(entry):
    old = read(verify(entry['result'])['path'])
    bindings = old['bindings']
    # Exactly the already-bound accepted telemetry/support; no recursive media discovery.
    raw,metadata,foundation = (read(verify(bindings[i])['path']) if i in (1,4) else None for i in (0,1,4))
    raw_binding = verify(bindings[0])
    raw = [json.loads(line) for line in Path(raw_binding['path']).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    timeline = ReceiptTimeline(raw)
    evidence = foundation['evidence']
    previous = {(t['utterance_label'],t['stream']):t for t in old['turns']}
    turns = {k:t for k,t in evidence['turns'].items() if t.get('host_activity_ranges_ns')}
    source_hash_before = digest(evidence)
    # Build sole-source supports once; identical to S6C len(active)==1, including source-internal gaps.
    bounds = sorted({x for t in turns.values() for ab in t['host_activity_ranges_ns'] for x in ab})
    active_ranges = collections.defaultdict(list)
    turn_starts = {k:[a for a,b in t['host_activity_ranges_ns']] for k,t in turns.items()}
    for a,b in zip(bounds,bounds[1:]):
        active = []
        for k,t in turns.items():
            i = bisect.bisect_right(turn_starts[k],a)-1
            if i>=0 and a<t['host_activity_ranges_ns'][i][1]: active.append(k)
        if len(active)==1: active_ranges[active[0]].append([a,b])
    rows=[];pair_rows=[];acquisitions=[];monotonic=0;summary_checks=0
    by_turn={}
    for key,t in turns.items():
        original_label = t['source_angle_label']
        assert original_label['source_angle_manual_uncertainty_deg']==5
        signed = original_label['source_angle_lab_signed_deg']
        labels = {w:source_label(signed,w) for w in WIDTHS}
        assert digest(original_label)==digest(source_label(signed,5.)), (entry['case_id'],key)
        ranges = union(active_ranges[key])
        support_sec = sum(b-a for a,b in ranges)/1e9
        by_turn[key] = (labels, original_label)
        for stream in STREAMS:
            prior = previous[key,stream]
            samples=[]
            for start,stop in ranges:
                samples.extend((s['angle_deg'],(b-a)/1e9) for a,b,s in timeline.intervals(stream,start,stop) if s['available'])
            support = sum(w for _,w in samples)
            assert math.isclose(support,prior['angles']['support_sec'],abs_tol=1e-6),(entry['case_id'],key,stream)
            nominal_error = mean([(abs(v-original_label['expected_native_nominal_deg']),w) for v,w in samples])
            assert nominal_error is None and prior['mean_abs_nominal_error'] is None or math.isclose(nominal_error,prior['mean_abs_nominal_error'],abs_tol=1e-6)
            summary_checks+=2
            scores = [score_samples(samples,labels[w],support_sec) for w in WIDTHS]
            for a,b in zip(scores,scores[1:]):
                if a['interval_error_mean_deg'] is not None:
                    assert a['interval_error_mean_deg'] <= b['interval_error_mean_deg']+1e-8
                assert a['usable_sec']==b['usable_sec'] and a['nominal_error_mean_deg']==b['nominal_error_mean_deg']
                monotonic+=1
            for w,score in zip(WIDTHS,scores):
                lo,hi=labels[w]['expected_native_interval_deg']
                rows.append(dict(case_id=entry['case_id'],utterance_label=key,stream=stream,
                    scorer_only_identity=prior['scorer_only_identity'],manual_original_half_width_deg=5.,
                    evaluator_half_width_deg=w,source_angle_lab_signed_deg=signed,
                    nominal_native_deg=original_label['expected_native_nominal_deg'],native_interval_low_deg=lo,native_interval_high_deg=hi,
                    observed_mean_deg=prior['angles']['mean'],observed_std_deg=prior['angles']['standard_deviation'],
                    stable_large_nominal_error=prior['stable_large_nominal_error_diagnostic'],**score))
            carried=t['streams'][stream]
            acquisitions.append(dict(case_id=entry['case_id'],utterance_label=key,stream=stream,
                all_overlay_widths='5,2,0', reference_status=t['status'],
                source_support_duration_s=carried['support_duration_s'],
                **{k:carried[k] for k in ('first_sector_hit_s','first_hit_censored','already_matching_at_onset',
                'sustained_acquisition_s','sustained_acquisition_censored','observed_envelope_duration_s')}))
    for pair in old['relative_turn_pairs']:
        for w in WIDTHS:
            left=by_turn[pair['left_utterance']][0][w];right=by_turn[pair['right_utterance']][0][w]
            pair_rows.append(dict(case_id=entry['case_id'],evaluator_half_width_deg=w,**pair,
                                 minimum_reference_interval_gap_deg=interval_gap(left,right)))
    assert digest(evidence)==source_hash_before
    return dict(rows=rows,pairs=pair_rows,acquisitions=acquisitions,monotonic_checks=monotonic,
        reproduction_checks=summary_checks,bindings=[entry['result'],raw_binding,bindings[1],bindings[4]],
        preserved_source_empty_control=old['source_empty_control'])


def aggregate(rows):
    result=[]
    for stream in STREAMS:
        for width in WIDTHS:
            subset=[r for r in rows if r['stream']==stream and r['evaluator_half_width_deg']==width]
            usable=[r for r in subset if r['usable_sec']>0]
            support=sum(r['support_sec'] for r in subset);valid=sum(r['usable_sec'] for r in subset)
            strict=[r for r in subset if r['strict_single_sector_eligible']]
            row=dict(stream=stream,evaluator_half_width_deg=width,all_turns=len(subset),usable_turns=len(usable),
                physical_cases=len({r['case_id'] for r in subset}),support_sec=support,usable_sec=valid,
                nominal_error_mean_deg=mean([(r['nominal_error_mean_deg'],r['usable_sec']) for r in usable]),
                interval_error_mean_deg=mean([(r['interval_error_mean_deg'],r['usable_sec']) for r in usable]),
                stable_large_nominal_error_turns=sum(r['stable_large_nominal_error'] for r in subset),
                stable_large_nominal_error_cases=len({r['case_id'] for r in subset if r['stable_large_nominal_error']}),
                strict_single_sector_eligible_turns=len(strict),strict_single_sector_support_sec=sum(r['support_sec'] for r in strict),
                strict_single_sector_usable_sec=sum(r['usable_sec'] for r in strict))
            for key in ('nominal_sector_matching_sec','allowed_interval_sector_matching_sec')+tuple('interval_within_'+str(int(t))+'_deg_sec' for t in THRESHOLDS):
                value=sum(r[key] for r in subset)
                row[key]=value
                row[key.removesuffix('_sec')+'_fraction_of_all_support']=value/support if support else None
                row[key.removesuffix('_sec')+'_fraction_of_usable_support']=value/valid if valid else None
            result.append(row)
    return result


def prediction_invariance(out):
    rows=[];sources=[]
    for family,candidates in (('anonymous',('C065','C079')),('naming',('C088','C091'))):
        index_path=S6C/f'epoch4/full_n01_{family}_v1_PREDICTION_INDEX.json'
        index=read(index_path);sources.append(bind(index_path))
        selected=[r for r in index['rows'] if r['candidate_id'] in candidates]
        assert len(selected)==960
        for entry in selected:
            prediction=verify(entry['result'])
            # Frozen predictions are inputs only. Their exact decompressed object covers ASR,
            # track decisions and gallery queries without guessing a small safe field subset.
            with gzip.open(prediction['path'],'rt',encoding='utf-8') as f: value=json.load(f)
            equivalent=digest(value)
            core=S6C/f'full_n01_{family}_core_v3/scores'/entry['candidate_id']/entry['case_id']/f"{entry['stream']}_ASR_{entry['identity_tap']}_ID.json"
            score_bindings=[bind(core)]
            core_value=read(core)
            assert core_value['case_id']==entry['case_id'] and core_value['profile_id']==entry['candidate_id']
            if family=='naming':
                names=S6C/'full_n01_naming_names_v3/scores'/entry['candidate_id']/entry['case_id']/core.name
                score_bindings.append(bind(names))
            # No width parameter enters these legacy scorers or predictors. Three wrappers
            # retain exact immutable bytes; an evaluator overlay has a separate namespace.
            views=[dict(evaluator_half_width_deg=w, prediction_sha256=prediction['sha256'],
                        prediction_equivalence_sha256=equivalent,score_sha256s=[b['sha256'] for b in score_bindings]) for w in WIDTHS]
            assert all({k:v for k,v in view.items() if k!='evaluator_half_width_deg'}=={k:v for k,v in views[0].items() if k!='evaluator_half_width_deg'} for view in views)
            verify(prediction)
            for b in score_bindings: verify(b)
            rows.append(dict(candidate_id=entry['candidate_id'],case_id=entry['case_id'],stream=entry['stream'],
                identity_tap=entry['identity_tap'],prediction=prediction,prediction_equivalence_sha256=equivalent,
                scores=score_bindings,all_three_overlay_views_identical=True))
    save(out/'PREDICTION_INVARIANCE_BINDINGS.json',dict(schema='s6d-angle-prediction-invariance.v1',
        status='PASS_FROZEN_EVALUATOR_GRAPH_INVARIANCE',sources=sources,rows=rows,
        scope=POLICY['prediction_invariance_scope'],new_asr_or_diarization_or_enrollment_runs=0,
        limitation='This is fixed-output byte/equivalence invariance and source dependency analysis. It is not cross-execution deterministic equivalence under new native scheduling.'))
    return dict(status='PASS_FROZEN_EVALUATOR_GRAPH_INVARIANCE',cells=len(rows),candidates=['C065','C079','C088','C091'],
        cases_per_candidate_per_tap=240,new_model_calls=0,binding=bind(out/'PREDICTION_INVARIANCE_BINDINGS.json'))


def run(out):
    started=time.perf_counter()
    if (out/'RESULT.json').exists(): raise ValueError('Completed output is immutable; choose a fresh output path')
    plan=freeze(out) if not (out/'PLAN.json').exists() else read(out/'PLAN.json')
    for b in plan['sources']: verify(b)
    rows=[];pairs=[];acquisitions=[];cases=[]
    for i,entry in enumerate(plan['case_bindings'],1):
        path=out/'cases'/(entry['case_id']+'.json')
        if path.exists():
            case=read(path)
            for b in case['bindings']:verify(b)
        else:
            case=case_rescore(entry);save(path,case)
        rows+=case['rows'];pairs+=case['pairs'];acquisitions+=case['acquisitions']
        cases.append(dict(case_id=entry['case_id'],result=bind(path),monotonic_checks=case['monotonic_checks'],reproduction_checks=case['reproduction_checks']))
        if i%20==0:print(json.dumps(dict(stage='ANGLE_RESCORING',cases=i,total=240,elapsed_sec=time.perf_counter()-started)),flush=True)
    summary=aggregate(rows)
    selected=[r for r in summary if r['stream']=='selected_processed']
    assert all(r['usable_turns']==768 and r['stable_large_nominal_error_turns']==179 and r['stable_large_nominal_error_cases']==124 for r in selected)
    assert len({r['nominal_error_mean_deg'] for r in selected})==1
    csv_save(out/'TURN_RESCORES.csv',rows)
    csv_save(out/'STREAM_SUMMARY.csv',summary)
    csv_save(out/'PAIR_RESCORES.csv',pairs)
    csv_save(out/'ACQUISITION_CENSORING.csv',acquisitions)
    csv_save(out/'INTERVAL_DEPENDENT_POPULATION.csv',[r for r in rows if r['stream']=='selected_processed' and not r['strict_single_sector_eligible']])
    pair_summary=[]
    for stream in STREAMS:
        for same in (True,False):
            for width in WIDTHS:
                subset=[r for r in pairs if r['stream']==stream and r['same_reference_person']==same and r['evaluator_half_width_deg']==width]
                pair_summary.append(dict(stream=stream,same_reference_person=same,evaluator_half_width_deg=width,
                    pair_count=len(subset),case_count=len({r['case_id'] for r in subset}),
                    measured_mean_difference_mean_deg=statistics.mean(r['measured_mean_difference_deg'] for r in subset) if subset else None,
                    measured_mean_difference_median_deg=statistics.median(r['measured_mean_difference_deg'] for r in subset) if subset else None,
                    reference_same_nominal_pairs=sum(abs(r['nominal_difference_deg'])<1e-7 for r in subset),
                    **{'reference_interval_gap_gt_'+str(int(t))+'_deg_pairs':sum(r['minimum_reference_interval_gap_deg']>t+1e-7 for r in subset) for t in THRESHOLDS}))
    acquisition_summary=[]
    for stream in STREAMS:
        subset=[r for r in acquisitions if r['stream']==stream]
        acquisition_summary.append(dict(stream=stream,all_widths='5,2,0',turns=len(subset),
            first_observed=sum(not r['first_hit_censored'] for r in subset),
            first_censored=sum(r['first_hit_censored'] for r in subset),
            sustained_observed=sum(not r['sustained_acquisition_censored'] for r in subset),
            sustained_censored=sum(r['sustained_acquisition_censored'] for r in subset),
            first_conditional_median_sec=statistics.median(r['first_sector_hit_s'] for r in subset if r['first_sector_hit_s'] is not None),
            sustained_conditional_median_sec=statistics.median(r['sustained_acquisition_s'] for r in subset if r['sustained_acquisition_s'] is not None),
            limited_multispeaker_truth_turns=sum(r['reference_status']=='LIMITED_MULTISPEAKER_TRUTH' for r in subset)))
    csv_save(out/'PAIR_SUMMARY.csv',pair_summary)
    csv_save(out/'ACQUISITION_SUMMARY.csv',acquisition_summary)
    invariance=prediction_invariance(out)
    result=dict(schema='s6d-angle-rescore.v1',status='COMPLETE_BOUNDED_EVALUATOR_ONLY_RESCORING',
        plan=bind(out/'PLAN.json'),checks=checks(),physical_traces=240,shared_physical_taps=['O0','O1'],
        source_turns=len(acquisitions)//len(STREAMS),rows=len(rows),cases=cases,
        original_support_reproduction_assertions=sum(c['reproduction_checks'] for c in cases),
        fullbank_monotonic_invariance_assertions=sum(c['monotonic_checks'] for c in cases),
        summary=summary,pair_summary=pair_summary,acquisition_summary=acquisition_summary,prediction_invariance=invariance,
        new_model_calls=0,new_hardware_passes=0,operational_parameters_changed=False,
        elapsed_sec=time.perf_counter()-started,
        limitations=['No independent source-bearing calibration or source DSP timestamps.',
          'No voice-to-beam identity association inferred from physical angle alone.',
          'Original acquisition is a per-source envelope nominal-sector diagnostic; its population differs from exactly-one-source S6C stability.',
          'Interval-compatible sectors and strict unambiguous-sector eligibility are explicit evaluation-only alternatives.',
          'Original manual metadata stays5 degrees. Narrowed overlays do not sharpen XVF observations.',
          'No other S6D branch is marked complete by this bounded result.'])
    save(out/'RESULT.json',result)
    return dict(status=result['status'],result=bind(out/'RESULT.json'),selected_processed=selected,invariance=invariance)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['checks','freeze','run'])
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    if args.action!='checks' and args.output is None:p.error('--output required')
    result=checks() if args.action=='checks' else freeze(args.output) if args.action=='freeze' else run(args.output)
    print(json.dumps(result,indent=2,allow_nan=False),flush=True)
