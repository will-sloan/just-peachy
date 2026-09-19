"""Read only closed scored metadata; aggregate without rerunning scoring or models."""
import argparse
import collections
import datetime
import hashlib
import json
import math
import re
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
R = SIM / 'reports/S6D/20260913T195357Z'
G = Path('G:/Just_Peachy_S6D/20260913T195357Z')
PINS = {
    'spec': (R / 'application/native176_dependency_relocation_v1/SCORING_INPUTS_ACCEPTED.json', 'af0951b64ecd33e54737489b910f18cabf71d750d3a0eb58dfcab45b828a5c26'),
    'index': (G / 'application/native176_composite_closed_inputs_v2/scores/INDEX.json', '3069b2bffbbb9c75f104e81637881c86702371c40c4d978effe03c4777fd5467'),
    'validation': (G / 'application/native176_composite_closed_inputs_v2/VALIDATION.json', '885634c7ec270c8f177d8241cf73b57a108282785ff878a445b0844692fc36c9'),
    'matrix': (G / 'runner/native_serial892_preparation_v2/data/CONDITIONAL_MATRIX.json', '7ceeb49698b01e6c76942b1e3b63cc75ca443ad52a6d3508d1857f006855c69f'),
    'execution': (R / 'application/native176_scoring_execution_v3/EXECUTION.json', '9e2c32d0d6ce6359942a73601332025e292a42aa134551b92b1c6341f035554d'),
}
METRICS = ('first_text_publication', 'first_text_consumption', 'first_any_name', 'first_correct_name', 'first_confirmed_correct_name', 'first_stable_correct_name')
ID = re.compile(r'^(C065|C088|C105)_(S45_\d{2}_\d{2})_(O[01])_(original|delivery_repair)_r([12])$')

def need(value, message):
    if not value:
        raise ValueError(message)

def bind(path, data=None):
    p = Path(path).resolve()
    data = p.read_bytes() if data is None else data
    return dict(path=str(p), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

class Reader:
    def __init__(self):
        self.cache = {}
    def get(self, binding):
        p = str(Path(binding['path']).resolve())
        if p not in self.cache:
            data = Path(p).read_bytes()
            self.cache[p] = (json.loads(data), bind(p, data))
        value, actual = self.cache[p]
        need(actual == binding, 'Closed metadata binding differs: ' + p)
        return value
    def pinned(self, name):
        p, sha = PINS[name]
        b = bind(p)
        need(b['sha256'] == sha, 'Pinned ' + name + ' differs')
        return self.get(b), b

def quantiles(values):
    xs = sorted(values)
    need(all(type(x) in (int, float) and math.isfinite(x) for x in xs), 'Nonfinite value')
    def q(p):
        if not xs:
            return None
        at = (len(xs) - 1) * p
        a, b = math.floor(at), math.ceil(at)
        return xs[a] + (xs[b] - xs[a]) * (at - a)
    return dict(n=len(xs), min=xs[0] if xs else None, p50=q(.5), p95=q(.95), p99=q(.99), max=xs[-1] if xs else None)

def census(opportunities, metric):
    counts = collections.Counter(o['metrics'][metric]['status'] for o in opportunities)
    waits = [o['metrics'][metric]['wait_sec'] for o in opportunities if o['metrics'][metric]['status'] == 'OBSERVED']
    eligible = counts['OBSERVED'] + counts['RIGHT_CENSORED']
    return dict(total=len(opportunities), observed=counts['OBSERVED'], right_censored=counts['RIGHT_CENSORED'],
                unavailable=len(opportunities)-eligible, eligible=eligible, observed_fraction=counts['OBSERVED']/eligible if eligible else None,
                statuses=dict(counts), observed_wait_sec=quantiles(waits),
                limitation='Wait quantiles condition on observed hits; censored and unavailable opportunities remain in the denominator census.')

def pooled_counts(scores, field):
    total = collections.Counter()
    statuses = collections.Counter()
    for s in scores:
        obj = s['text'][field]
        statuses[obj['status']] += 1
        c = obj.get('counts', obj.get('word_counts'))
        if c is not None:
            total.update(c)
    return dict(counts=dict(total), pooled_error_rate=total['errors']/total['reference_words'] if total['reference_words'] else None,
                score_statuses=dict(statuses), scope='Sum existing per-job counts; repeated cases remain repeated observations. cpWER assignments are per job, not a new global cross-job assignment.')

def group_summary(scores):
    ops = [o for s in scores for o in s['names']['opportunities']]
    exposure = collections.Counter()
    finals = collections.Counter()
    for s in scores:
        exposure.update(s['names'].get('exposure_row_seconds', {}))
        finals.update(x['name_status'] for x in s['final_name_rows'])
    return dict(jobs=len(scores), reference_statuses=dict(collections.Counter(s['text']['full_session_all_speaker_wer_status'] for s in scores)),
                all_reference_occurrences=sum(s['text']['all_reference_occurrences'] for s in scores),
                eligible_reference_occurrences=sum(s['text']['reference_occurrences'] for s in scores),
                serialized_words=pooled_counts(scores, 'serialized_words'), anonymous_cpwer=pooled_counts(scores, 'anonymous_cpwer'),
                metrics={m:census(ops, m) for m in METRICS}, exposure_row_seconds=dict(exposure), final_name_row_statuses=dict(finals),
                exposure_scope='Overlapping retained row-seconds, not physical wall seconds; unknown/hidden/unqualified states retained.',
                entire_raw_words=sum(s['text']['entire_raw_words'] for s in scores),
                excluded_hypothesis_words=sum(s['text']['excluded_hypothesis_word_count'] for s in scores))

def pair_summary(pairs):
    rows = [r for p in pairs for r in p['first_text_pairs']]
    result = dict(pairs=len(pairs), raw_equivalent_pairs=sum(p['raw_output_timing_gate'] for p in pairs),
                  status_counts=dict(collections.Counter(p['status'] for p in pairs)), first_row_opportunities=len(rows),
                  comparable_rows=sum(r['timing_comparable'] for r in rows),
                  unavailable_rows=sum(not r['timing_comparable'] for r in rows),
                  non_equivalent_pairs=[dict(left=p['left_job_id'],right=p['right_job_id'],words_equal=p['entire_normalized_words_equal'],
                                             final_spans_equal=p['final_source_spans_equal'],raw_differences=p['utterance_raw_differences']) for p in pairs if not p['raw_output_timing_gate']])
    for key in ('publication_right_minus_left_sec', 'consumer_right_minus_left_sec'):
        vals = [r[key] for r in rows if r['timing_comparable']]
        result[key] = dict(**quantiles(vals), right_earlier=sum(v<0 for v in vals), right_later=sum(v>0 for v in vals),equal=sum(v==0 for v in vals))
    result['scope'] = 'Descriptive paired native runs, exact frozen equivalence gate. Negative means right earlier. No causal isolation from resource/time drift; no GUI/scanout evidence.'
    return result

def checks():
    fixture = lambda status, wait=None: dict(metrics={'x':dict(status=status, wait_sec=wait)})
    c = census([fixture('OBSERVED', 4), fixture('RIGHT_CENSORED'), fixture('INCOMPLETE_REFERENCE')], 'x')
    assert (c['total'],c['eligible'],c['observed_fraction'],c['unavailable']) == (3,2,.5,1)
    a = dict(text={'serialized_words':dict(status='S',counts={'errors':1,'reference_words':1})})
    b = dict(text={'serialized_words':dict(status='S',counts={'errors':0,'reference_words':99})})
    assert pooled_counts([a,b],'serialized_words')['pooled_error_rate'] == .01
    assert quantiles([])['p95'] is None and quantiles([1,3])['p50']==2
    try:
        quantiles([float('nan')])
    except ValueError:
        pass
    else:
        raise AssertionError('NaN accepted')
    p = dict(raw_output_timing_gate=False,status='UNAVAILABLE',first_text_pairs=[dict(timing_comparable=False,publication_right_minus_left_sec=None,consumer_right_minus_left_sec=None)],
             left_job_id='left',right_job_id='right',entire_normalized_words_equal=False,final_source_spans_equal=True,utterance_raw_differences=['changed'])
    x=pair_summary([p])
    assert x['pairs']==1 and x['unavailable_rows']==1 and x['publication_right_minus_left_sec']['n']==0
    return dict(status='PASS',checks=5,scope='Tiny aggregation adversaries only; no input/scorer/model/process calls')

def main(output):
    out = Path(output).resolve()
    need(not out.exists(), 'Fresh output directory required')
    reader=Reader()
    values={}; bindings={}
    for key in PINS:
        values[key],bindings[key]=reader.pinned(key)
    spec,index,validation,matrix=(values[k] for k in ('spec','index','validation','matrix'))
    need(spec['status']=='APPROVED_CLOSED_NATIVE_INPUTS' and index['input_acceptance']==bindings['spec'], 'Input acceptance mismatch')
    need(index['declared_jobs']==index['scored_jobs']==176 and index['unavailable_jobs']==[] and index['complete_metric_matrix'] is True, 'Incomplete score matrix')
    need(validation['status']=='ALL176_COMPOSITE_CLOSED_INPUTS_VERIFIED' and validation['original_completed']==171 and validation['recovery_completed']==5, 'Composite validation differs')
    jobs={j['job_id']:j for j in spec['jobs']}
    need(len(jobs)==len(spec['jobs'])==176, 'Duplicate or missing input ID')
    proofs={j['job_id']:j for j in validation['completion_validations']}
    need(set(proofs)==set(jobs), 'Closure population differs')
    scores={}; score_bindings={}; details=[]; grouped=collections.defaultdict(list)
    for row in index['rows']:
        jid=row['job_id']; need(jid not in scores and jid in jobs, 'Score ID duplicate/unplanned')
        s=reader.get(row['score']); need(s['job_id']==jid and s['inputs']==jobs[jid] and s['input_acceptance']==bindings['spec'], 'Score/source join differs')
        need(s['models_started']==s['policy_replays']==0 and not s['gui_tested'] and not s['physical_tested'], 'Unexpected scorer scope')
        match=ID.fullmatch(jid); need(match is not None, 'Unexpected scientific ID')
        candidate,case,tap,variant,repeat=match.groups()
        for metric in METRICS:
            got=census(s['names']['opportunities'],metric)
            need(all(s['names']['census'][metric][k]==got[k] for k in ('total','observed','right_censored','unavailable')), 'Scorer census mismatch')
        result=reader.get(jobs[jid]['result'])
        need(result['status']=='COMPLETE' and result['resource_observer_closed'] is True and result['event_consumer_drained'] is True and result['observer_errors']==[] and result['completion_errors']==[], 'Closed result differs')
        scores[jid]=s;score_bindings[jid]=row['score']
        for key in (candidate+'_'+variant,candidate+'_'+variant+'_'+tap):
            grouped[key].append(s)
        detail=dict(job_id=jid,candidate=candidate,case_id=case,tap=tap,variant=variant,repeat_index=int(repeat),score=row['score'],
                    scope='C105_DIAGNOSTIC' if candidate=='C105' else 'CORE',execution_origin=next(x['origin'] for x in validation['execution_selection'] if x['scientific_job_id']==jid),
                    text={k:v for k,v in s['text'].items() if k!='entire_raw_normalized'},
                    names={k:v for k,v in s['names'].items() if k not in ('retained_intervals','first_text_rows')},
                    final_name_rows=s['final_name_rows'],full_closure_proof=proofs[jid],
                    runtime=dict(elapsed_sec=result['elapsed_sec'],source_duration_sec=result['telemetry']['source_duration_sec'],
                                 asr_cursor_sec=result['telemetry']['asr_cursor_sec'],speaker_cursor_sec=result['telemetry']['speaker_cursor_sec'],
                                 audio_frames_dropped=result['telemetry']['audio_frames_dropped'],
                                 resource_observer_closed=True,event_consumer_drained=True,observer_errors=[]))
        details.append(detail)
    need(set(scores)==set(jobs), 'Missing score')
    need(len(index['comparison_pairs'])==len(spec['comparison_pairs'])==176, 'Pair population differs')
    pairgroups=collections.defaultdict(list)
    for actual,declared in zip(index['comparison_pairs'],spec['comparison_pairs']):
        need(all(actual[k]==v for k,v in declared.items()), 'Pair declaration/order differs')
        need(actual['left_job_id'] in scores and actual['right_job_id'] in scores, 'Pair endpoint missing')
        pairgroups[actual['comparison']].append(actual)
    credits=[]; source_manifest=None
    need(matrix['accepted_credits']==0 and len(matrix['conditional_credits'])==68 and matrix['full_scope']==960 and len(matrix['rows'])==892, 'Conditional scope differs')
    for credit in matrix['conditional_credits']:
        jid=credit['preferred_predeclared_job']; s=scores[jid]; j=jobs[jid]
        need(jid.endswith('_delivery_repair_r1') and credit['candidate'] in ('C065','C088'), 'Nonpreferred credit')
        need(j['manifest']==credit['source_manifest'] and j['result']['path']==credit['result_path'] and j['completion_audit']['path']==credit['audit_path'], 'Credit joins differ')
        need(proofs[jid]['execution_job_id']==jid, 'Recovery substituted for preferred credit')
        mf=reader.get(j['manifest']); native=next(x for x in mf['jobs'] if x['job_id']==jid)
        need(native['scene_id']==credit['case_id'] and native['candidate']==credit['candidate'] and native['asr_tap']==native['identity_tap']==credit['tap'], 'Credit native identity differs')
        need(native['settings']==dict(schema_version='edge-s6d.v1',text_delivery=True,boundary_repair=True,transcript_mode='T0',direction_mode='V0') and native['repeat_index']==1, 'Credit settings differ')
        need(native['expected_frames']==native['expected_identity_frames'] and len(native['audio_pcm_sha256'])==64 and native['expected_frames']>0, 'Predeclared full PCM absent')
        need(mf['limits']['cpu_affinity']==[12,13,14,15] and mf['limits']['cpu_threads_each']==1 and mf['limits']['serial_jobs'] is True, 'Original controlled allocation differs')
        artifact_paths={x['path']:x for x in proofs[jid]['validation']['artifacts']}
        need(artifact_paths.get(j['result']['path'])==j['result'] and artifact_paths.get(j['completion_audit']['path'])==j['completion_audit'], 'Credit not in accepted full-source closure')
        repeats=credit['all_predeclared_repeats'];need(jid in repeats and all(r in scores for r in repeats), 'Repeat evidence missing')
        credits.append(dict(declaration=credit,status='METADATA_MATCHED_PENDING_ROOT_RETENTION_AND_CACHE_ACCEPTANCE',root_acceptance=None,
                            score=score_bindings[jid],result=j['result'],full_source_audit=j['completion_audit'],completion=proofs[jid]['validation']['completion'],
                            native_source=dict(audio=native['audio'],audio_pcm_sha256=native['audio_pcm_sha256'],expected_frames=native['expected_frames'],
                                               profile=native['profile_binding'],gallery=native['gallery'],settings=native['settings'],helper=mf['helper'],execution_files=mf['execution_files']),
                            all_repeats=[dict(job_id=r,score=score_bindings[r]) for r in repeats]))
    summary=dict(schema='s6d-native176-results-summary.v1',status='DESCRIPTIVE_RESULTS_NOT_RETENTION_OR_CACHE_APPROVAL',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 inputs=bindings,source=bind(__file__),scope=dict(total=176,core=168,C105_diagnostic=8,original_closed=171,fresh_recovery_closed=5,cache_credit_metadata_matches=68,accepted_cache_credits=0),
                 groups={k:group_summary(v) for k,v in sorted(grouped.items())},pair_families={k:pair_summary(v) for k,v in pairgroups.items()},
                 runtime_elapsed_sec=quantiles([x['runtime']['elapsed_sec'] for x in details]),
                 zero_reference_cases=[dict(job_id=x['job_id'],raw_words=scores[x['job_id']]['text']['entire_raw_words']) for x in details if x['text']['all_reference_occurrences']==0],
                 limitations=['Complete output matrix does not mean complete reference coverage or scientific PASS.',
                              'Native headless publication/consumption, not GUI widget timing, scanout, physical efficacy or CM5.',
                              'All declared repeats and adverse outputs retained; panel includes known boundary diagnostic and is not held out.',
                              'No new neural execution or scorer calls. Existing score counts only; no word-timestamp invention.',
                              'Original171 REPORT_BLOCKED and stopped old job remain unchanged; five selected fresh recoveries close only their exact scientific IDs.',
                              'C12/Tk/HOST and future892 execution require separate root authority, controlled serial allocation and current resource/deadline gates.'])
    out.mkdir(parents=True)
    payloads={'SUMMARY.json':summary,'ALL176.json':details,'PAIR176.json':index['comparison_pairs'],
              'CREDIT68_METADATA_PROPOSAL.json':dict(status='PROPOSAL_ONLY_NO_CREDITS_ACCEPTED',accepted_credits=0,metadata_matches=68,root_acceptance=None,inputs=bindings,credits=credits),
              'AGGREGATION_CHECKS.json':checks()}
    outputs=[]
    for name,value in payloads.items():
        p=out/name;p.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8');outputs.append(bind(p))
    receipt=dict(status='CLOSED_SCORE_METADATA_SUMMARIZED',outputs=outputs,source=bind(__file__),
                 unique_metadata_files_read=len(reader.cache),metadata_bytes_read=sum(v[1]['bytes'] for v in reader.cache.values()),
                 audio_or_event_journal_reads=0,scorer_calls=0,model_calls=0,process_queries=0,device_calls=0,root_approval_created=False)
    p=out/'RECEIPT.json';p.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(bind(p)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output');parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:
        print(json.dumps(checks()))
    else:
        need(args.output,'--output required');main(args.output)
