"""Physical cue quality audit, evaluator only. README_S6C_CUE_AUDIT.md."""
from __future__ import annotations

import argparse
import bisect
import collections
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

import s6c_enrollment as E
# Load this interpreter's NumPy before the legacy S4 helper adds its recorder
# dependency directory (which contains a different Python ABI) to sys.path.
from s4_spatial_analysis import ReceiptTimeline, STREAMS, FIELDS, AGE_NS, union

S6A = E.SIM/'reports/S6A/20260909T202250Z'
S6B = E.SIM/'reports/S6B/20260909T230840Z'
OUT = E.REPORT/'cue_audit_v1'
POLICY = dict(angle_coordinate='linear0..180; no circular180 wrap',
    age_sec=.25, change_deg=35., consistency_deg=25., persistence_sec=.75,
    reference_local_gap_sec=2., causal_match_after_change_sec=1.,
    descriptive_stable_max_std_deg=10., descriptive_large_nominal_error_deg=35.,
    production_rule_fitted=False, score_labels_are_predictor_inputs=False,
    observation_time='host received last-value state, native DSP observation time unknown',
    support='existing callback-quantized estimated activity; no new angle/audio alignment fit')


def moments(pairs):
    weight = sum(w for _, w in pairs)
    if not weight:
        return dict(support_sec=0., mean=None, standard_deviation=None, minimum=None, maximum=None)
    mean = sum(x*w for x, w in pairs)/weight
    return dict(support_sec=weight, mean=mean,
        standard_deviation=math.sqrt(max(0., sum((x-mean)**2*w for x,w in pairs)/weight)),
        minimum=min(x for x,_ in pairs), maximum=max(x for x,_ in pairs))


def changes(intervals):
    """A causal timer on latest valid angle; no reference information accepted."""
    anchor = pending = None
    count = 0.
    result = []
    for a,b,angle,valid in intervals:
        if not valid:
            pending = None
            count = 0.
            continue
        if anchor is None:
            anchor = angle
            continue
        if abs(angle-anchor) < POLICY['change_deg']:
            pending = None
            count = 0.
            continue
        if pending is None or abs(angle-pending) > POLICY['consistency_deg']:
            pending = angle
            count = 0.
        previous = count
        count += b-a
        if count+1e-9 >= POLICY['persistence_sec']:
            result.append(dict(time_sec=a+max(0., POLICY['persistence_sec']-previous),
                               previous_angle_deg=anchor,new_angle_deg=pending,
                               absolute_change_deg=abs(pending-anchor)))
            anchor = pending
            pending = None
            count = 0.
    return result


def match_events(predictions, references):
    unused = set(range(len(references)))
    pairs = []
    for n,p in enumerate(predictions):
        eligible = [j for j in unused if 0 <= p['time_sec']-references[j]['time_sec'] <= POLICY['causal_match_after_change_sec']]
        if eligible:
            j = min(eligible, key=lambda j: (p['time_sec']-references[j]['time_sec'], j))
            unused.remove(j)
            pairs.append(dict(prediction=n, reference=j, lag_sec=p['time_sec']-references[j]['time_sec']))
    return dict(predictions=len(predictions), references=len(references), matched=len(pairs),
                precision=len(pairs)/len(predictions) if predictions else None,
                recall=len(pairs)/len(references) if references else None,
                matching='one-to-one causal lag0..1s, predetermined local reference transitions', pairs=pairs)


def require_grid(index):
    if index['status'] != 'COMPLETE' or len(index['rows']) != 240 or len({r['case_id'] for r in index['rows']}) != 240:
        raise ValueError('Exactly240 complete physical traces required')


def freeze():
    target = OUT/'PHYSICAL_CUE_AUDIT_PLAN.json'
    if target.exists():
        plan = E.read(target)
        for b in plan['bindings']:
            E.verify(b)
        return plan
    delivery = E.read(S6A/'CUE_DELIVERY_INDEX.json')
    require_grid(delivery)
    foundation = E.read(S6A/'CUE_FOUNDATION.json')
    if len(foundation['rows']) != 240:
        raise ValueError('Missing shared trace foundation')
    old = E.read(S6B/'EPOCH2_EXECUTION_MANIFEST.json')
    E.verify(old['scene_manifest'])
    paths = [Path(__file__), Path(__file__).with_name('README_S6C_CUE_AUDIT.md'),
             E.SIM/'scripts/s6c_enrollment.py', S6A/'CUE_DELIVERY_INDEX.json', S6A/'CUE_FOUNDATION.json',
             S6B/'EPOCH2_EXECUTION_MANIFEST.json']
    paths += [E.SIM/'scripts'/x for x in ('s4_spatial_analysis.py','s4_telemetry.py','s4_geometry.py')]
    plan = dict(schema='s6c-physical-cue-audit-plan.v1',status='FROZEN_BEFORE_NEW_CUE_SUMMARIES',created_utc=E.utc(),
        bindings=[E.bind(p) for p in paths]+[old['scene_manifest']], policy=POLICY,
        physical_traces=240, physical_trace_replicates_per_tap=False,
        scope='Read-only diagnostics of existing physical telemetry. Labels/nominal geometry never fit or enter a production predictor.',
        later_phase='Actual model-feature ambiguity and v3 decision-contribution chains require separate bound output evidence and a separate receipt.')
    E.save(target,plan)
    return plan


def case_audit(entry, foundation, scene):
    for name in ('raw_telemetry','metadata','capture','sanitized'):
        E.verify(entry[name])
    E.verify(foundation['result'])
    evidence = E.read(foundation['result']['path'])['evidence']
    raw = [json.loads(line) for line in Path(entry['raw_telemetry']['path']).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    timeline = ReceiptTimeline(raw)
    metadata = E.read(entry['metadata']['path'])
    callbacks = metadata['callback_times']
    stamps = [r.get('host_copy_complete_monotonic_ns',r['host_callback_monotonic_ns']) for r in callbacks]
    start = stamps[0]
    stop = stamps[-1]+round(callbacks[-1]['frames']/48000*1e9)
    source_segments = {s['utterance_label']:s for s in scene['segments'] if s['kind']=='utterance'}
    empty_category = ('instrumental_music' if any(s.get('category')=='instrumental_music' for s in scene['segments'])
                      else 'digital_silence' if not scene['segments'] else 'other_nonspeech') if not source_segments else None
    turns = []
    for label,t in evidence['turns'].items():
        if not t.get('host_activity_ranges_ns'):
            continue
        segment = source_segments[label]
        ranges = t['host_activity_ranges_ns']
        turns.append(dict(label=label,identity=segment['speaker_key'],ranges=ranges,
            starts=[a for a,b in ranges],nominal=t.get('source_angle_label',{}).get('expected_native_nominal_deg'),
            interval=t.get('source_angle_label',{}).get('expected_native_interval_deg')))
    bounds = {start,stop}
    for stream in STREAMS:
        bounds.update(timeline.boundaries(stream,start,stop))
    for t in turns:
        bounds.update(x for a,b in t['ranges'] for x in (a,b) if start<x<stop)
    bounds = sorted(bounds)
    aggregate = collections.defaultdict(lambda:dict(total_sec=0.,angle_only_sec=0.,usable_sec=0.,
        energy_positive_sec=0.,energy_measured_sec=0.,angles=[],energies=[],age=[]))
    turn_values = collections.defaultdict(list)
    selected_trace, references_person, references_position = [], [], []
    pairs = collections.defaultdict(list)
    previous_truth = None
    last_truth_stop = None
    local_gaps_excluded = 0
    for a,b in zip(bounds,bounds[1:]):
        dt = (b-a)/1e9
        active = []
        for t in turns:
            i = bisect.bisect_right(t['starts'],a)-1
            if i>=0 and a<t['ranges'][i][1]:
                active.append(t)
        identities = {t['identity'] for t in active}
        population = ('source_empty_control' if not source_segments else 'sole_person' if len(identities)==1
                      else 'multiple_people' if len(identities)>1 else 'speech_scene_outside_estimated_activity')
        truth = None
        if len(identities)==1:
            nominals = {t['nominal'] for t in active if t['nominal'] is not None}
            truth = (next(iter(identities)), next(iter(nominals)) if len(nominals)==1 else None)
            if previous_truth is not None and truth!=previous_truth:
                if (a-last_truth_stop)/1e9 <= POLICY['reference_local_gap_sec']:
                    row = dict(time_sec=(a-start)/1e9,previous_identity=previous_truth[0],next_identity=truth[0],
                               previous_nominal_deg=previous_truth[1],next_nominal_deg=truth[1])
                    if truth[0]!=previous_truth[0]:
                        references_person.append(row)
                    if truth[1] is not None and previous_truth[1] is not None and abs(truth[1]-previous_truth[1])>=POLICY['change_deg']:
                        references_position.append(row)
                else:
                    local_gaps_excluded += 1
            previous_truth, last_truth_stop = truth,b
        states = {s:timeline.state(s,a) for s in STREAMS}
        selected = states['selected_processed']
        selected_trace.append(((a-start)/1e9,(b-start)/1e9,selected['angle_deg'],selected['available']))
        for stream,state in states.items():
            pops = ['whole_capture',population]
            if empty_category:
                pops.append('whole_source_empty_'+empty_category+'_scene')
            for pop in pops:
                row = aggregate[(stream,pop)]
                row['total_sec'] += dt
                row['angle_only_sec'] += dt*state['angle_available']
                row['usable_sec'] += dt*state['available']
                if state['energy'] is not None:
                    row['energy_measured_sec'] += dt
                    row['energy_positive_sec'] += dt*(state['energy']>0)
                    row['energies'].append((state['energy'],dt))
                if state['available']:
                    row['angles'].append((state['angle_deg'],dt))
                if state['receipt_ns'] is not None:
                    row['age'].append(((a-state['receipt_ns'])/1e9,dt))
            if state['available'] and len(active)==1:
                turn_values[(active[0]['label'],stream)].append((state['angle_deg'],dt))
        for left,right in (('focused_1','focused_2'),('selected_processed','selected_auto'),('selected_processed','raw_auto')):
            if states[left]['available'] and states[right]['available']:
                pairs[(left,right,population)].append((abs(states[left]['angle_deg']-states[right]['angle_deg']),dt))
        erow,fresh = timeline.latest(FIELDS[1],a)
        if erow is not None and fresh and len(erow['value_valid'])>=4 and all(erow['value_valid'][:4]) and len(erow['values'])>=4:
            energies = erow['values'][:4]
            total = sum(max(0.,v) for v in energies)
            if total:
                pairs[('max_beam_energy_share','all4',population)].append((max(energies)/total,dt))
                pairs[('focused_both_energy_positive','focused1+2',population)].append((float(energies[0]>0 and energies[1]>0),dt))
    predicted = changes(selected_trace)
    measurements = []
    for (stream,population),row in sorted(aggregate.items()):
        measures = {k:v for k,v in row.items() if k not in ('angles','energies','age')}
        measures.update(usable_fraction=row['usable_sec']/row['total_sec'] if row['total_sec'] else None,
                        angle=moments(row['angles']), energy=moments(row['energies']),
                        host_receipt_age=moments(row['age']))
        measurements.append(dict(stream=stream,population=population,**measures))
    summaries = []
    for t in turns:
        for stream in STREAMS:
            stats = moments(turn_values[(t['label'],stream)])
            nominal = t['nominal']
            samples = turn_values[(t['label'],stream)]
            summary = dict(utterance_label=t['label'],scorer_only_identity=t['identity'],stream=stream,
                nominal_native_deg=nominal,manual_native_interval_deg=t['interval'],angles=stats,
                mean_abs_nominal_error=moments([(abs(v-nominal),w) for v,w in samples])['mean'] if nominal is not None else None)
            summaries.append(summary)
            summary['stable_large_nominal_error_diagnostic'] = bool(
                stats['standard_deviation'] is not None and nominal is not None and
                stats['standard_deviation']<=POLICY['descriptive_stable_max_std_deg'] and
                summary['mean_abs_nominal_error']>=POLICY['descriptive_large_nominal_error_deg'])
    comparisons = []
    for stream in STREAMS:
        available = [r for r in summaries if r['stream']==stream and r['angles']['mean'] is not None]
        for i,left in enumerate(available):
            for right in available[i+1:]:
                comparisons.append(dict(stream=stream,left_utterance=left['utterance_label'],right_utterance=right['utterance_label'],
                    same_reference_person=left['scorer_only_identity']==right['scorer_only_identity'],
                    measured_mean_difference_deg=abs(left['angles']['mean']-right['angles']['mean']),
                    nominal_difference_deg=abs(left['nominal_native_deg']-right['nominal_native_deg']) if left['nominal_native_deg'] is not None and right['nominal_native_deg'] is not None else None,
                    left_usable_sec=left['angles']['support_sec'],right_usable_sec=right['angles']['support_sec']))
    delivered = [json.loads(line) for line in Path(entry['sanitized']['path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    source_span_rows = sum(r.get('source_start_sec') is not None and r.get('source_end_sec') is not None for r in delivered)
    return dict(schema='s6c-physical-cue-case-audit.v1',case_id=entry['case_id'],
        scene_metadata={key:scene.get(key) for key in ('family_id','family','title')},
        source_empty_category=empty_category,
        source_empty_control=not bool(source_segments),
        physical_trace_units=1,shared_O0_O1=True,host_capture_span_sec=(stop-start)/1e9,
        bindings=[entry[k] for k in ('raw_telemetry','metadata','capture','sanitized')]+[foundation['result']],
        field_statistics=timeline.field_stats(),delivery_statistics=entry['statistics'],
        source_span_rows=source_span_rows,delivered_rows=len(delivered),
        true_DSP_source_age_observable=False,stream_populations=measurements,turns=summaries,
        relative_turn_pairs=comparisons,pair_disagreements=[dict(left=a,right=b,population=p,statistics=moments(v)) for (a,b,p),v in sorted(pairs.items())],
        sustained_selected_changes=predicted,local_person_transitions=references_person,
        local_nominal_position_transitions=references_position,
        person_transition_detection=match_events(predicted,references_person),
        position_transition_detection=match_events(predicted,references_position),
        local_transition_gap_exclusions=local_gaps_excluded,
        limitations=['Person/nominal labels are evaluator-only.','Same-person turn pairs may include seat changes; nominal difference is retained.',
                     'Turn angle summaries require exactly one active source interval; full population summary separately allows sole person.',
                     'Raw/scanning/focused energies are asynchronous observations and do not establish independent people.',
                     'No true DSP source timestamp exists; fresh host delivery does not prove a fresh device estimate.',
                     'Physical240 traces are shared by output taps; later audio-feature views must not double this physical denominator.'])


def run():
    plan = freeze()
    target = OUT/'PHYSICAL_CUE_AUDIT.json'
    if target.exists():
        result = E.read(target)
        for row in result['rows']:
            E.verify(row['result'])
        return dict(status='VERIFIED_EXISTING_PHYSICAL_AUDIT',receipt=E.bind(target))
    delivery = E.read(S6A/'CUE_DELIVERY_INDEX.json')
    foundation = {r['case_id']:r for r in E.read(S6A/'CUE_FOUNDATION.json')['rows']}
    scene_binding = E.read(S6B/'EPOCH2_EXECUTION_MANIFEST.json')['scene_manifest']
    scenes = {s['case_id']:s for s in E.read(scene_binding['path'])['scenes']}
    rows, cases = [], []
    started = time.perf_counter()
    for entry in delivery['rows']:
        path = OUT/'cases'/(entry['case_id']+'.json')
        if path.exists():
            raise ValueError('Unclosed partial audit retained; use a new output revision or diagnose exact checkpoint authority')
        case = case_audit(entry,foundation[entry['case_id']],scenes[entry['case_id']])
        E.save(path,case)
        cases.append(case)
        rows.append(dict(case_id=entry['case_id'],result=E.bind(path),physical_trace_units=1))
        if len(rows)%20==0:
            print(json.dumps(dict(status='PHYSICAL_CUE_AUDIT_PROGRESS',cases=len(rows),elapsed_sec=time.perf_counter()-started)),flush=True)
    summary = []
    populations = sorted({(r['stream'],r['population']) for c in cases for r in c['stream_populations']})
    for stream,population in populations:
        subset = [r for c in cases for r in c['stream_populations'] if (r['stream'],r['population'])==(stream,population)]
        total = sum(r['total_sec'] for r in subset)
        usable = sum(r['usable_sec'] for r in subset)
        summary.append(dict(stream=stream,population=population,case_rows=len(subset),physical_support_sec=total,
                            usable_sec=usable,usable_fraction=usable/total if total else None))
    transition = {}
    for field in ('person_transition_detection','position_transition_detection'):
        p=sum(c[field]['predictions'] for c in cases);r=sum(c[field]['references'] for c in cases);m=sum(c[field]['matched'] for c in cases)
        transition[field]=dict(predictions=p,references=r,matched=m,precision=m/p if p else None,recall=m/r if r else None)
    result = dict(schema='s6c-physical-cue-audit.v1',status='COMPLETE_PHYSICAL_DIAGNOSTICS_ONLY',created_utc=E.utc(),
        plan=E.bind(OUT/'PHYSICAL_CUE_AUDIT_PLAN.json'),rows=rows,physical_trace_units=240,
        source_empty_controls=sum(c['source_empty_control'] for c in cases),
        delivered_rows=sum(c['delivered_rows'] for c in cases),source_span_rows=sum(c['source_span_rows'] for c in cases),
        raw_DSP_timestamp_rows=0,population_summary=summary,local_sustained_change_summary=transition,
        new_model_calls=0,hardware_passes=0,elapsed_sec=time.perf_counter()-started,
        scope='Existing physical telemetry descriptive audit; not new predictor benefit or an independently calibrated sensor-accuracy claim',
        unfinished_separate_scope=['Voice-ambiguous feature pair separability on sealed R0 observations','Actual v3 candidate-contribution and cue-on/off decision chains'])
    E.save(target,result)
    return dict(status=result['status'],receipt=E.bind(target),physical_traces=240)


def checks():
    assert abs(0.-180.)==180.
    x=[(0.,1.,0.,True),(1.,1.5,180.,True),(1.5,2.,180.,True)]
    out=changes(x)
    assert len(out)==1 and abs(out[0]['time_sec']-1.75)<1e-9
    assert changes(x[:2])==[]
    stale=[(0.,1.,0.,True),(1.,1.5,180.,True),(1.5,1.8,None,False),(1.8,2.3,180.,True)]
    assert changes(stale)==[]
    assert moments([(0.,1.),(180.,1.)])['mean']==90.
    m=match_events([dict(time_sec=.9),dict(time_sec=1.5)], [dict(time_sec=1.)])
    assert m['matched']==1 and m['pairs'][0]['prediction']==1
    return dict(status='PASS',checks=['linear endpoints opposite','sustained timer correct','prefix no future event',
        'invalid receipt breaks persistence','linear weighted mean','matching rejects early cue and is one-to-one'],model_calls=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','run','checks'))
    args=parser.parse_args()
    print(json.dumps({'freeze':freeze,'run':run,'checks':checks}[args.action](),indent=2),flush=True)
