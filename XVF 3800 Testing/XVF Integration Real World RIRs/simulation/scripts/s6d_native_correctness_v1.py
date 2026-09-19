"""Prospective closed-output text/name scoring. README_S6D_NATIVE_CORRECTNESS_V1.md."""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
from dataclasses import asdict
import importlib.util
import json
import math
from pathlib import Path
import string
import sys
import s6d_native_evidence_v1 as E

HERE = Path(__file__).resolve().parent
MAX_FINAL_ROWS = 4096
MAX_RELEVANT_EVENTS = 100000
PINS = {'s4_h2_analysis.py':'0b5d8a227ca87c4dcee48db8118de35444fb32217291bf022feb458f0982d1a0',
        's5_text_metrics.py':'4bf822fe40227acf74a17a24666fcb1ddce9f76cbe93adf4ec6b10e6d2b47969',
        's6c_name_analysis_v3.py':'79c58dd9f67ebbaa9d1f5ca2b9ef53ec788b8762e348eda5d6add44d5dac3017',
        's6a_support_metrics.py':'4ecc9240d897598005719b00b803ea5f1f137bba4b66f1e970b1d098a47a68b5'}
WER_SHA = 'fd493e6952b5b4ab7cf2652338511dac99667591b94af84ad1efba8d438adf34'
GALLERY_MAP_SHA = 'ed13643358be9e5d36a8a093a4b7ccac90108f5b4b5cc208d5f80360f49aea8f'
EVIDENCE_SHA = 'bb1b5ff846f8edad386b573dea203df7b08e9c31b8126e7c3aa14a8cccb226d2'
NAME_METRICS = ('first_text_publication','first_text_consumption','first_any_name','first_correct_name','first_confirmed_correct_name','first_stable_correct_name')
RELEVANT = {'source_started','session_completed','s6d_text_ready','s6d_display',
            'transcript_partial','transcript_final','transcript_label_revision'}


def exact_functions(path, names, namespace):
    """Compile only named unchanged pure function ASTs from a hash-admitted source."""
    module = ast.parse(Path(path).read_bytes())
    nodes = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name in names]
    E.need({n.name for n in nodes} == set(names), 'Pinned pure function inventory differs')
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
    return namespace


def dependencies():
    eb = E.binding(E.__file__); E.need(eb['sha256'] == EVIDENCE_SHA, 'Accepted evidence helper differs')
    sources = {n:E.binding(HERE/n) for n in PINS}
    for n,b in sources.items(): E.need(b['sha256'] == PINS[n], 'Pinned scoring source differs: '+n)
    pure = exact_functions(HERE/'s4_h2_analysis.py', {'normalize'}, {'string':string})
    exact_functions(HERE/'s6c_name_analysis_v3.py', {'named','status_against','roster_status'}, pure)
    exact_functions(HERE/'s6a_support_metrics.py', {'union','intersection','subtract','samples'}, pure)
    wer = HERE.parent.parents[2]/'Software Validation from Datasets/Evaluation Tool/app/scoring/wer.py'
    wb = E.binding(wer); E.need(wb['sha256'] == WER_SHA, 'Pinned historical word-error scorer differs')
    spec = importlib.util.spec_from_file_location('_s6d_pinned_word_error',wer)
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod; spec.loader.exec_module(mod)
    pure['compute_wer'] = mod.compute_wer
    # Backend/version check is the original unchanged S5 function, no scene admission bypass.
    from importlib.metadata import version
    exact_functions(HERE/'s5_text_metrics.py', {'_backend','_rate'},
                    backend := dict(version=version, MEETEVAL_VERSION='0.4.3', asdict=asdict, math=math))
    _, pure['cpwer'] = backend['_backend']()
    pure['rate'] = backend['_rate']
    pure['sources'] = [*sources.values(),wb,eb]
    return pure


def validate_reference(reference):
    E.need(reference.get('schema') == 's6d-host-reference-input-plan.v1', 'Exact projected-reference schema required')
    pieces, turns = reference['pieces'], reference['projected_turns']
    E.need(reference['composition_frames'] > 0 and len(pieces) <= 240 and len(turns) <= 777,
           'Reference population bound exceeded')
    E.need(len({r['occurrence_id'] for r in turns}) == len(turns), 'Duplicate reference occurrence')
    shifted = E.shift_reference_pieces(pieces, reference['composition_frames'])
    E.need(shifted == turns and len(turns) == reference['occurrence_count'], 'Projected reference differs from exact pieces')
    E.need([p['index'] for p in pieces]==list(range(len(pieces))) and all(p['end_sample']==p['start_sample']+p['samples'] for p in pieces), 'Piece index/end differs')
    return pieces, turns


def piece_for_span(row, pieces):
    try: a,b = E.frame(row['source_start_sec']), E.frame(row['source_end_sec'])
    except (KeyError,ValueError): return None, 'UNAVAILABLE_SOURCE_SPAN'
    if b <= a: return None, 'UNAVAILABLE_SOURCE_SPAN'
    matches = [p for p in pieces if p['start_sample'] <= a < b <= p['start_sample']+p['samples']]
    if len(matches) != 1: return None, 'CROSS_PIECE_OR_GAP_SPAN'
    p = matches[0]
    if not (p['all_reference_complete'] and p['transcript_valid'] and p['task_scoring_allowed']):
        return None, 'INCOMPLETE_REFERENCE_PIECE'
    if p['support_mapping']['source_with_rir_to_output_offset_samples'] is None:
        return None, 'UNAVAILABLE_ALIGNMENT'
    return p, 'QUALIFIED_PIECE'


def text_metrics(reference, finals, dep):
    pieces, turns = validate_reference(reference)
    E.need(len(finals) <= MAX_FINAL_ROWS and len({r['utterance_id'] for r in finals}) == len(finals), 'Final row inventory invalid')
    eligible_pieces = {p['index'] for p in pieces if p['all_reference_complete'] and p['transcript_valid']
                       and p['task_scoring_allowed'] and p['support_mapping']['source_with_rir_to_output_offset_samples'] is not None}
    refs = [t for t in turns if t['piece_index'] in eligible_pieces]
    included, excluded = [], []
    for r in finals:
        E.need(isinstance(r.get('text'),str) and r.get('is_final') is True, 'Actual raw final text required')
        p,status = piece_for_span(r,pieces)
        if p is None: excluded.append(dict(utterance_id=r['utterance_id'],reason=status,raw_text=r['text'],
                                          source_start_sec=r.get('source_start_sec'),source_end_sec=r.get('source_end_sec')))
        else: included.append(r)
    # Preserve native row order and fixed reference occurrence order; no invented word timestamps.
    norm = dep['normalize']
    ref = ' '.join(norm(t['transcript']) for t in refs)
    hyp = ' '.join(norm(r['text']) for r in included)
    wc = asdict(dep['compute_wer'](ref,hyp)); wc.pop('wer',None)
    refstreams, hypstreams = defaultdict(list), defaultdict(list)
    for t in refs: refstreams[t['metadata_identity']].extend(norm(t['transcript']).split())
    unlabeled = []
    for r in included:
        label = r.get('latest_anonymous_label')
        if not isinstance(label,str) or not label: unlabeled.append(r['utterance_id'])
        else: hypstreams[label].extend(norm(r['text']).split())
    if unlabeled:
        cp = dict(status='UNAVAILABLE_ANONYMOUS_LABEL',utterance_ids=unlabeled)
    elif not refstreams:
        cp = dict(status='EMPTY_REFERENCE',wer=None)
    else:
        value = dep['cpwer']({k:' '.join(v) for k,v in refstreams.items()}, {k:' '.join(v) for k,v in hypstreams.items()})
        cp = dep['rate'](value,len(hyp.split()),'CONDITIONED_GLOBAL_ANONYMOUS_CPWER',
             'Global corpus-qualified reference speakers and actual latest anonymous track labels; fixed complete-reference pieces; boundary-ambiguous hypotheses excluded whole, reference words retained.')
    complete = len(eligible_pieces) == len(pieces)
    return dict(full_session_all_speaker_wer_status='COMPLETE_REFERENCE_AVAILABLE' if complete else 'UNAVAILABLE_INCOMPLETE_OR_UNMAPPED_REFERENCE',
        serialized_words=dict(status='CONDITIONED_SERIALIZED_DIAGNOSTIC',wer=wc['errors']/wc['reference_words'] if wc['reference_words'] else None,
                              counts=wc,overlap_order_sensitive=True), anonymous_cpwer=cp,
        eligible_piece_indices=sorted(eligible_pieces), excluded_piece_indices=sorted(set(p['index'] for p in pieces)-eligible_pieces),
        reference_occurrences=len(refs), all_reference_occurrences=len(turns), included_final_rows=len(included),
        excluded_hypothesis_rows=excluded, excluded_hypothesis_word_count=sum(len(norm(r['raw_text']).split()) for r in excluded),
        crossing_policy='Exclude entire ambiguous hypothesis; retain all eligible reference words, so missing hypothesis contributes deletions. No text split or inferred word timestamps. Counts are conditioned diagnostics, not full-session coverage.',
        entire_raw_normalized=' '.join(norm(r['text']) for r in finals), entire_raw_words=sum(len(norm(r['text']).split()) for r in finals))


def clocks(events, consumer_closure=None):
    starts = [e for e in events if e['event_type']=='source_started']
    E.need(len(starts)==1, 'Unique actual source clock required')
    origin = starts[0]['payload'].get('pilot_publication_monotonic_sec')
    E.need(type(origin) in (int,float) and math.isfinite(origin), 'Actual monotonic source origin required')
    result=[]; previous_consumer=None; issues=[]
    source_index = next(i for i,e in enumerate(events) if e['event_type']=='source_started')
    for i,e in enumerate(events):
        p=e['payload']; pub=p.get('pilot_publication_monotonic_sec'); consumed=e.get('actual_consumed_monotonic_sec')
        if not all(type(x) in (int,float) and math.isfinite(x) for x in (pub,consumed)):
            issues.append(dict(event=i,reason='MISSING_OR_NONFINITE_CLOCK')); continue
        if consumed < pub or previous_consumer is not None and consumed < previous_consumer:
            issues.append(dict(event=i,reason='CONSUMER_CLOCK_ORDER'))
        if e['event_type'] in RELEVANT-{'source_started'} and (pub < origin or i < source_index):
            issues.append(dict(event=i,reason='SOURCE_DEPENDENT_PUBLICATION_BEFORE_SOURCE'))
        previous_consumer=consumed
        result.append((i,e,pub-origin,consumed-origin))
    horizon = max((r[3] for r in result),default=0.)
    scope='last actual consumed event after joined/drained native session'
    if consumer_closure is not None:
        stamp=consumer_closure.get('monotonic_sec')
        if type(stamp) not in (int,float) or not math.isfinite(stamp) or stamp-origin < horizon:
            issues.append(dict(reason='INVALID_CONSUMER_CLOSURE_CLOCK'))
        else: horizon=stamp-origin; scope='actual consumer closure monotonic receipt'
    return dict(valid=not issues,origin_monotonic_sec=origin,horizon_sec=horizon,issues=issues,horizon_scope=scope),result


def attribute(row, pieces, turns, dep):
    piece,status=piece_for_span(row,pieces)
    if piece is None:return status,None
    span=[[E.frame(row['source_start_sec']),E.frame(row['source_end_sec'])]]
    candidates=[t for t in turns if t['piece_index']==piece['index']]
    if any(t['active_ranges'] is None or t['sole'] is None or not t['activity_available'] for t in candidates):
        return 'UNAVAILABLE_ALIGNMENT',None
    hits=[t for t in candidates if dep['samples'](dep['intersection'](span,t['active_ranges']))>0]
    if len(hits)!=1:return 'MULTIPLE_OR_NO_SOURCE_OCCURRENCE',None
    if not dep['samples'](dep['intersection'](span,hits[0]['sole'])):return 'NO_SOLE_SUPPORT',None
    return 'QUALIFIED',hits[0]


def display_name_state(kind,p,profiles,dep):
    if kind=='s6d_display':
        pid=p.get('known_profile_id'); label=p.get('label'); name=None
        if pid is not None and pid in profiles and label in (profiles[pid]['display_name'],profiles[pid]['display_name']+' (tentative)'):
            name=profiles[pid]['display_name']
        elif pid is None and label in {v['display_name'] for v in profiles.values()}:
            name=label
        return dep['named'](dict(known_profile_id=pid,known_name=name,display_label=label,naming_state=p.get('naming_state')),profiles)
    return dep['named'](p,profiles,transcript=True)


def name_metrics(reference, events, gallery, repaired, dep, consumer_closure=None):
    pieces,turns=validate_reference(reference)
    profiles={p['profile_id']:p for p in gallery['profiles']}
    E.need(len(profiles)==len(gallery['profiles']), 'Duplicate actual gallery profile')
    clock,timed=clocks(events,consumer_closure)
    if not clock['valid']:
        opportunities=[dict(occurrence_id=t['occurrence_id'],status='UNAVAILABLE_ACTUAL_CLOCK',
                            metrics={m:dict(status='UNAVAILABLE_ACTUAL_CLOCK',wait_sec=None) for m in NAME_METRICS}) for t in turns]
        census={m:dict(total=len(turns),observed=0,right_censored=0,unavailable=len(turns)) for m in NAME_METRICS}
        return dict(status='UNAVAILABLE_ACTUAL_CLOCK',clock=clock,
                    opportunities=opportunities,census=census,
                    wait_summaries={m:dict(p50=None,p95=None,p99=None,**census[m]) for m in NAME_METRICS},
                    gui_render_timing='UNAVAILABLE_HEADLESS_CONSUMER',scanout_timing='UNAVAILABLE')
    raw_kinds={'s6d_text_ready'} if repaired else {'transcript_partial','transcript_final'}
    name_kinds={'s6d_display'} if repaired else {'transcript_partial','transcript_final','transcript_label_revision'}
    hits=defaultdict(lambda:defaultdict(list)); rows=defaultdict(list); first_text=[]; row_spans={}; first_ids=set()
    for i,e,pub,cons in timed:
        kind,p=e['event_type'],e['payload']; uid=p.get('utterance_id')
        if kind in raw_kinds or kind=='s6d_display':E.need(isinstance(p.get('text'),str),'Actual emitted text must be a string')
        if kind in raw_kinds and p['text'].strip():
            qualification,t=attribute(p,pieces,turns,dep)
            if t is not None:
                hits[t['occurrence_id']]['first_text_publication'].append(pub)
                hits[t['occurrence_id']]['first_text_consumption'].append(cons)
            E.need(isinstance(uid,str) and uid,'Actual raw text row ID required')
            if uid not in first_ids:
                first_ids.add(uid)
                first_text.append(dict(utterance_id=uid,publication_sec=pub,consumption_sec=cons,
                      queue_delay_sec=cons-pub,raw_text=p['text'],source_start_sec=p.get('source_start_sec'),source_end_sec=p.get('source_end_sec'),reference_status=qualification))
        if kind not in name_kinds:continue
        E.need(isinstance(uid,str) and uid, 'Actual transcript row identity required')
        # Revisions retain the most recent arrived ASR span, never the final span from another file.
        if kind!='transcript_label_revision':row_spans[uid]=(p.get('source_start_sec'),p.get('source_end_sec'))
        a,b=row_spans.get(uid,(None,None)); arrived=dict(p,source_start_sec=a,source_end_sec=b)
        qualification,t=attribute(arrived,pieces,turns,dep)
        state=display_name_state(kind,p,profiles,dep)
        visible=p.get('visible') is True if kind=='s6d_display' else bool(str(p.get('text','')).strip()) if kind!='transcript_label_revision' else bool(rows[uid] and rows[uid][-1]['visible'])
        status=dep['status_against'](state,t['metadata_identity']) if t is not None and visible else 'UNQUALIFIED_OR_HIDDEN'
        rows[uid].append(dict(start_sec=cons,publication_sec=pub,event_index=i,occurrence_id=t['occurrence_id'] if t else None,
                             reference_status=qualification,name_status=status,confirmed=state['confirmed'],visible=visible))
        if t is not None and visible:
            key=t['occurrence_id']
            if status in ('correct_name','wrong_known_name'):hits[key]['first_any_name'].append(cons)
            if status=='correct_name':
                hits[key]['first_correct_name'].append(cons)
                if state['confirmed']:hits[key]['first_confirmed_correct_name'].append(cons)
    exposures=[]; transitions=[]
    for uid,states in rows.items():
        local=[]
        for n,row in enumerate(states):
            end=states[n+1]['start_sec'] if n+1<len(states) else clock['horizon_sec']
            E.need(end>=row['start_sec'], 'Backward retained row clock')
            interval=dict(row,utterance_id=uid,end_sec=end,duration_sec=end-row['start_sec'])
            exposures.append(interval);local.append(interval)
            if n and row['name_status']!=states[n-1]['name_status']:
                transitions.append(dict(utterance_id=uid,time_sec=row['start_sec'],before=states[n-1]['name_status'],after=row['name_status'],
                                        previous_occurrence_id=states[n-1]['occurrence_id'],occurrence_id=row['occurrence_id']))
        start=None; previous=None
        for interval in local:
            qualified=interval['name_status']=='correct_name' and interval['confirmed'] and interval['visible']
            key=interval['occurrence_id']
            if not qualified: start=None; previous=None; continue
            if previous!=key or start is None:start=interval['start_sec']
            previous=key
            if interval['end_sec']-start>=.5:
                hits[key]['first_stable_correct_name'].append(start+.5)
    opportunities=[]
    metrics=NAME_METRICS
    for t in turns:
        roster=dep['roster_status'](t['metadata_identity'],gallery)
        origin=t['file_support'][0][0]/E.RATE if t['file_support'] else None
        piece=pieces[t['piece_index']]
        unavailable='INCOMPLETE_REFERENCE' if not (piece['all_reference_complete'] and piece['transcript_valid'] and piece['task_scoring_allowed']) else 'UNAVAILABLE_ALIGNMENT' if t['sole'] is None or origin is None or not t['activity_available'] else 'NO_SOLE_SUPPORT' if not t['sole'] else None
        row=dict(occurrence_id=t['occurrence_id'],metadata_identity=t['metadata_identity'],roster_status=roster,metrics={})
        for metric in metrics:
            values=hits[t['occurrence_id']][metric]
            status=unavailable
            if status is None and metric.startswith(('first_correct','first_confirmed','first_stable')) and roster!='ENROLLED':status=roster
            if status is not None:entry=dict(status=status,wait_sec=None)
            elif values:entry=dict(status='OBSERVED',wait_sec=min(values)-origin)
            else:
                E.need(clock['horizon_sec']>=origin,'Closed observation precedes reference occurrence')
                entry=dict(status='RIGHT_CENSORED',wait_sec=None,censor_sec=clock['horizon_sec']-origin)
            row['metrics'][metric]=entry
        opportunities.append(row)
    census={metric:E.opportunity_census([dict(occurrence_id=r['occurrence_id'],**r['metrics'][metric]) for r in opportunities]) for metric in metrics}
    quantiles={}
    for metric in metrics:
        xs=sorted(r['metrics'][metric]['wait_sec'] for r in opportunities if r['metrics'][metric]['status']=='OBSERVED')
        def quantile(q):
            if not xs:return None
            at=(len(xs)-1)*q;lo=int(at);hi=math.ceil(at);return xs[lo]+(xs[hi]-xs[lo])*(at-lo)
        quantiles[metric]=dict(p50=quantile(.5),p95=quantile(.95),p99=quantile(.99),**census[metric])
    return dict(status='SCORED_HEADLESS_CONSUMER_NAMES',clock=clock,opportunities=opportunities,census=census,
                wait_summaries=quantiles,first_text_rows=first_text,retained_intervals=exposures,name_transitions=transitions,
                exposure_row_seconds=dict(Counter({k:sum(r['duration_sec'] for r in exposures if r['name_status']==k) for k in {r['name_status'] for r in exposures}})),
                gui_render_timing='UNAVAILABLE_HEADLESS_CONSUMER',scanout_timing='UNAVAILABLE',
                scope='Actual consumed presentation rows; conditional estimated source support. Overlapping retained rows add row-seconds, not wall seconds. Stable=.5s confirmed-correct retained row, no invented expiry.')


def analyze(reference, finals, events, gallery, repaired, dep, consumer_closure=None):
    E.need(len(events)<=MAX_RELEVANT_EVENTS, 'Relevant event memory bound exceeded')
    profiles={p['profile_id']:p for p in gallery['profiles']};final_names=[]
    for r in finals:
        status,t=attribute(r,reference['pieces'],reference['projected_turns'],dep)
        state=dep['named'](r,profiles,transcript=True)
        final_names.append(dict(utterance_id=r['utterance_id'],reference_status=status,occurrence_id=t['occurrence_id'] if t else None,
                               name_status=dep['status_against'](state,t['metadata_identity']) if t else 'UNQUALIFIED_REFERENCE',assigned_state=state))
    return dict(schema='s6d-native-correctness.v1',status='ANALYZED_SCOPED_CLOSED_OUTPUT',
                text=text_metrics(reference,finals,dep),names=name_metrics(reference,events,gallery,repaired,dep,consumer_closure),
                final_name_rows=final_names,
                models_started=0,policy_replays=0,gui_tested=False,physical_tested=False,cm5_tested=False)


def bound_json(b):
    value,actual=E.read_json(b['path']);E.need(actual==b,'Exact input bytes differ');return value


def admit_full_source(job, audit):
    """Historical inspection may derive PCM; production scoring must never do so."""
    frames,pcm=job.get('expected_frames'),job.get('audio_pcm_sha256')
    E.need(type(frames) is int and frames>0, 'Positive full source frames must be predeclared')
    E.need(isinstance(pcm,str) and len(pcm)==64 and all(c in '0123456789abcdef' for c in pcm),
           'Full source PCM SHA256 must be predeclared')
    E.need(E.frame(job['audio_duration_sec'])==frames, 'Predeclared source duration/frame mismatch')
    if 'expected_identity_frames' in job:
        E.need(type(job['expected_identity_frames']) is int and job['expected_identity_frames']==frames,
               'Predeclared identity frame count differs')
    authority=audit.get('source')
    E.need(isinstance(authority,dict) and authority.get('sha256')==EVIDENCE_SHA
           and E.binding(authority['path'])==authority, 'Completion audit must bind unchanged accepted evidence helper')
    proofs=audit.get('journals') or {};source=proofs.get('source') or {}
    E.need(source.get('source')==job['audio'] and type(source.get('frames')) is int and source['frames']==frames
           and source.get('bytes')==frames*2 and source.get('sha256')==pcm,
           'Audited source PCM/frame/WAV proof differs from predeclared source')
    for lane in ('asr','identity'):
        proof=proofs.get(lane) or {}
        E.need(proof.get('bytes')==frames*2 and proof.get('sha256')==pcm,
               'Audited full journal differs from predeclared source: '+lane)


def compare_pair(left,right):
    a={r['utterance_id']:r for r in left['first']};b={r['utterance_id']:r for r in right['first']};timings=[]
    differences=[dict(utterance_id=k,left=left['finals'].get(k),right=right['finals'].get(k))
                 for k in sorted(set(left['finals'])|set(right['finals'])) if left['finals'].get(k)!=right['finals'].get(k)]
    normalized_equal=left['normalized']==right['normalized']
    span_equality=left.get('final_spans')==right.get('final_spans')
    def valid_span(span):
        return isinstance(span,(list,tuple)) and len(span)==2 and all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in span) and span[0]<span[1]
    final_spans_valid=all(valid_span(span) for item in (left,right) for span in item.get('final_spans',{}).values())
    raw_equivalent=normalized_equal and not differences and span_equality and final_spans_valid
    for key in sorted(set(a)|set(b)):
        x,y=a.get(key),b.get(key)
        same_start=bool(x and y and x['source_start_sec']==y['source_start_sec'])
        compatible=bool(raw_equivalent and same_start and valid_span([x.get('source_start_sec'),x.get('source_end_sec')])
                        and x.get('source_end_sec')==y.get('source_end_sec') and x['raw_text']==y['raw_text'])
        timings.append(dict(utterance_id=key,compatible_source_start=same_start,timing_comparable=compatible,
             timing_status='OBSERVED_EQUIVALENT_OUTPUT' if compatible else 'UNAVAILABLE_CHANGED_OR_MISSING_RAW_OUTPUT',
             left_never=x is None,right_never=y is None,left_first_row=x,right_first_row=y,
             first_raw_text_equal=x['raw_text']==y['raw_text'] if x and y else None,
             publication_right_minus_left_sec=y['publication_sec']-x['publication_sec'] if compatible else None,
             consumer_right_minus_left_sec=y['consumption_sec']-x['consumption_sec'] if compatible else None))
    stats={}
    for field in ('publication_right_minus_left_sec','consumer_right_minus_left_sec'):
        xs=sorted(r[field] for r in timings if r[field] is not None)
        def q(p):
            if not xs:return None
            at=(len(xs)-1)*p;a=int(at);b=math.ceil(at);return xs[a]+(xs[b]-xs[a])*(at-a)
        stats[field]=dict(observed=len(xs),all_row_opportunities=len(timings),unmatched_or_incompatible=len(timings)-len(xs),p50=q(.5),p95=q(.95),p99=q(.99))
    return dict(status='ANALYZED_SOURCE_MATCHED_PAIR' if raw_equivalent else 'UNAVAILABLE_NON_EQUIVALENT_RAW_OUTPUT',
        entire_normalized_words_equal=normalized_equal,utterance_raw_differences=differences,
        final_source_spans_equal=span_equality,final_source_spans_valid=final_spans_valid,raw_output_timing_gate=raw_equivalent,
        first_text_pairs=timings,additional_first_text_delay=stats,
        limitation='Timing quantiles require equivalent entire normalized output, exact raw final rows and supplied final source spans, then equal first raw text/start/end for each stable ID. Changed/missing pairs retain actual rows and denominators with null comparative delay. CLI always supplies final spans; the pure API compares spans when supplied. Both absent remains in reference-level censored opportunities.')


def run(spec_path,sha):
    spec,sb=E.read_json(spec_path);E.need(sb['sha256']==sha,'Scoring matrix hash differs')
    E.need(spec.get('schema')=='s6d-native-scoring-inputs.v1' and spec.get('status')=='APPROVED_CLOSED_NATIVE_INPUTS'
           and spec.get('owner_exit_verified') is True and spec.get('source_graph_verified') is True,
           'Separate explicit closed-output input acceptance required')
    dep=dependencies();E.need(spec['scorer']==E.binding(__file__) and spec['dependencies']==dep['sources'],'Scorer/dependency graph differs')
    gallery_map=bound_json(spec['gallery_map']);E.need(spec['gallery_map']['sha256']==GALLERY_MAP_SHA,'Original completed evaluator gallery map required')
    declared={}
    for mb in spec['execution_manifests']:
        manifest=bound_json(mb)
        for j in manifest['jobs']:
            E.need(j['job_id'] not in declared,'Duplicate job across declared source manifests')
            declared[j['job_id']]=mb
    E.need(1<=len(declared)<=200,'Declared bounded job matrix required')
    scored_ids=[j['job_id'] for j in spec['jobs']];unavailable_ids=[j['job_id'] for j in spec['unavailable_jobs']]
    E.need(len(set(scored_ids+unavailable_ids))==len(scored_ids+unavailable_ids) and set(scored_ids+unavailable_ids)==set(declared),
           'Every declared job must be scored or explicitly unavailable exactly once')
    for item in spec['unavailable_jobs']:
        E.need(item['status'] in {'ABSENT_NATIVE','FAILED_NATIVE','UNADMITTED_NATIVE'} and isinstance(item.get('reason'),str) and item['reason'],
               'Unavailable native outcome needs explicit status/reason')
    output=Path(spec['output_root']).resolve()
    E.need(output.is_relative_to(Path('G:/Just_Peachy_S6D/20260913T195357Z').resolve()),'New score outputs must stay under the S6D G payload root')
    output.mkdir(parents=True,exist_ok=False)
    results=[];paired={};audit_sources=[]
    for index,item in enumerate(spec['jobs']):
        E.need(item['manifest']==declared[item['job_id']],'Job belongs to different declared source manifest')
        manifest=bound_json(item['manifest']);job=next(j for j in manifest['jobs'] if j['job_id']==item['job_id'])
        result=bound_json(item['result']);audit=bound_json(item['completion_audit'])
        E.need(result['manifest']==item['manifest'] and result['helper']==manifest['helper'] and result['job']==job,
               'Literal native result/manifest/job differs')
        E.need(audit['status']=='PASS_OFFLINE_EVIDENCE' and audit['errors']==[] and audit['result']==item['result']
               and audit['manifest']==item['manifest'] and audit['job_id']==item['job_id']
               and audit['expected_frames_predeclared'] is True, 'Full-source admitted completion audit required')
        admit_full_source(job,audit);audit_sources.append(audit['source'])
        reference=bound_json(item['reference']);E.need(reference['composition_frames']==job['expected_frames'] and reference['input_audio']==job['audio'], 'Reference/source audio or frame count differs')
        E.need(item['consumer_events']==audit['consumer_events'], 'Audited native consumer log differs')
        session=Path(result['session_dir']).resolve();E.need(Path(item['latest']['path']).resolve()==session/'latest_labelled_transcript.jsonl','Final transcript path differs')
        finals=[]
        for row in E.stream(item['latest']['path']):
            finals.append(row);E.need(len(finals)<=MAX_FINAL_ROWS,'Final row bound exceeded')
        E.need(E.binding(item['latest']['path'])==item['latest'],'Final transcript changed')
        events=[]
        for e in E.stream(item['consumer_events']['path']):
            if e.get('event_type') in RELEVANT:
                events.append(e);E.need(len(events)<=MAX_RELEVANT_EVENTS,'Relevant event bound exceeded')
        E.need(E.binding(item['consumer_events']['path'])==item['consumer_events'],'Consumer event bytes differ')
        gallery=bound_json(item['gallery_row'])
        E.need(gallery.get('manifest')==job['gallery'],'Scorer gallery differs from actual job')
        if job['gallery'] is not None:
            E.need(gallery in gallery_map['rows'],'Gallery evaluator row is not from original completed map')
            gm=bound_json(job['gallery'])
            E.need({(p['profile_id'],p['display_name']) for p in gm['profiles']}=={(p['profile_id'],p['display_name']) for p in gallery['profiles']},'Gallery profiles differ')
            loaded=result['telemetry']['scheduler']['identity']['gallery']
            E.need(loaded['manifest']==job['gallery'] and loaded['loaded_count']==len(gallery['profiles']),'Actual loaded gallery differs')
        else:
            E.need(gallery==dict(gallery_condition='NONE',manifest=None,profiles=[],available_identities=[],intended_identities=[]),'Exact no-gallery control required')
        closure=bound_json(audit['consumer_closure']) if audit['consumer_closure'] else None
        scored=analyze(reference,finals,events,gallery,bool(job['settings']),dep,closure)
        scored.update(job_id=item['job_id'],inputs=item,input_acceptance=sb)
        target=output/f'{index:03d}_SCORE.json'
        with target.open('x',encoding='utf-8') as f:json.dump(scored,f,indent=2,allow_nan=False)
        results.append(dict(job_id=item['job_id'],score=E.binding(target)))
        paired[item['job_id']]=dict(source=job['audio'],normalized=scored['text']['entire_raw_normalized'],
                                  finals={r['utterance_id']:r['text'] for r in finals},
                                  final_spans={r['utterance_id']:[r.get('source_start_sec'),r.get('source_end_sec')] for r in finals},
                                  first=scored['names'].get('first_text_rows',[]))
    comparisons=[]
    for pair in spec.get('comparison_pairs',[]):
        E.need(pair['left_job_id'] in declared and pair['right_job_id'] in declared,'Pair outside declared matrix')
        if pair['left_job_id'] not in paired or pair['right_job_id'] not in paired:
            comparisons.append(dict(pair,status='UNAVAILABLE_INCOMPLETE_PAIR'));continue
        a,b=paired[pair['left_job_id']],paired[pair['right_job_id']]
        E.need(a['source']==b['source'],'Matched native raw pair has different audio source')
        comparisons.append(dict(pair,**compare_pair(a,b)))
    E.need(E.read_json(spec_path)[1]==sb,'Input acceptance changed')
    E.need(E.binding(__file__)==spec['scorer'] and all(E.binding(b['path'])==b for b in dep['sources']+audit_sources),'Scorer/audit sources changed before completion')
    with (output/'INDEX.json').open('x',encoding='utf-8') as f:
        json.dump(dict(schema='s6d-native-correctness-index.v1',input_acceptance=sb,rows=results,comparison_pairs=comparisons,
                       declared_jobs=len(declared),scored_jobs=len(results),unavailable_jobs=spec['unavailable_jobs'],
                       complete_metric_matrix=len(results)==len(declared),scorer=E.binding(__file__)),f,indent=2)
    print(json.dumps(dict(index=E.binding(output/'INDEX.json'),jobs=len(results))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--spec',type=Path,required=True);p.add_argument('--sha256',required=True)
    a=p.parse_args();run(a.spec,a.sha256)
