"""Render bounded descriptive retention evidence from already summarized native176 scores."""
import argparse
import collections
import hashlib
import json
from pathlib import Path

BASE=Path('G:/Just_Peachy_S6D/20260913T195357Z/application/native176_results_analysis_v1')
PINS={'SUMMARY.json':'7f816355a9276e38fb09ebc44c156eb13ae4c58d89a326c41ba7b6bf5d13554a',
      'ALL176.json':'3a16451a9faeb9f01e67fb293fbf3275945fa01e4c9dde0049727919615d9550',
      'PAIR176.json':'d397d9f81d93abf823a4172141224a6748320788de93ba374123025d68e671d1',
      'CREDIT68_METADATA_PROPOSAL.json':'cc578c3f14a3f5151efc7f44cfb52c5c2fb7bac2b161072dfb764e27d364bae3'}

def binding(path,data=None):
    p=Path(path).resolve();data=p.read_bytes() if data is None else data
    return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def require(ok,message):
    if not ok:raise ValueError(message)

def observed_census(rows,metric):
    statuses=collections.Counter(o['metrics'][metric]['status'] for r in rows for o in r['names']['opportunities'])
    return dict(statuses)

def main(output):
    output=Path(output).resolve();require(not output.exists(),'Fresh output required')
    data={};bindings={}
    for name,sha in PINS.items():
        p=BASE/name;raw=p.read_bytes();b=binding(p,raw);require(b['sha256']==sha,'Frozen aggregate differs')
        bindings[name]=b;data[name]=json.loads(raw)
    summary=data['SUMMARY.json'];rows=data['ALL176.json'];pairs=data['PAIR176.json'];credits=data['CREDIT68_METADATA_PROPOSAL.json']
    require(len(rows)==len(pairs)==176 and len(credits['credits'])==68 and credits['accepted_credits']==0,'Wrong population')
    byid={r['job_id']:r for r in rows}
    comparisons=[];repeat_checks=[];latest_changes=[]
    for p in pairs:
        left,right=byid[p['left_job_id']],byid[p['right_job_id']]
        lc,rc=(r['text']['anonymous_cpwer'].get('word_counts') for r in (left,right))
        cpdelta=None if lc is None or rc is None else rc['errors']-lc['errors']
        lop={o['occurrence_id']:o for o in left['names']['opportunities']};rop={o['occurrence_id']:o for o in right['names']['opportunities']}
        require(set(lop)==set(rop),'Paired occurrence population differs')
        transitions=collections.Counter((lop[k]['metrics']['first_correct_name']['status'],rop[k]['metrics']['first_correct_name']['status']) for k in lop)
        fl={r['utterance_id']:r for r in left['final_name_rows']};fr={r['utterance_id']:r for r in right['final_name_rows']}
        changes=[dict(utterance_id=k,left=fl.get(k),right=fr.get(k)) for k in sorted(set(fl)|set(fr)) if fl.get(k)!=fr.get(k)]
        if p['comparison']=='C088_original_to_repair' and changes:
            latest_changes.append(dict(left=left['job_id'],right=right['job_id'],rows=changes))
        comparisons.append(dict(left=left['job_id'],right=right['job_id'],family=p['comparison'],raw_equivalent=p['raw_output_timing_gate'],
                                cp_error_delta_right_minus_left=cpdelta,cp_reference_words=lc['reference_words'] if lc else None,
                                correct_status_transitions=[dict(left=k[0],right=k[1],count=v) for k,v in transitions.items()],
                                timing=p['additional_first_text_delay'],changed_final_names=changes))
    for r in rows:
        if r['repeat_index']!=2:continue
        first=byid[r['job_id'][:-1]+'1']
        repeat_checks.append(dict(first=first['job_id'],repeat=r['job_id'],
                                  serialized_counts_equal=first['text']['serialized_words']==r['text']['serialized_words'],
                                  cpwer_first=first['text']['anonymous_cpwer'].get('wer'),cpwer_repeat=r['text']['anonymous_cpwer'].get('wer'),
                                  correct_first=first['names']['census']['first_correct_name'],correct_repeat=r['names']['census']['first_correct_name'],
                                  elapsed_first=first['runtime']['elapsed_sec'],elapsed_repeat=r['runtime']['elapsed_sec']))
    core_rows=[r for r in rows if r['scope']=='CORE']
    never=[dict(job_id=r['job_id'],occurrence_id=o['occurrence_id'],metadata_identity=o['metadata_identity'],censor_sec=o['metrics']['first_correct_name']['censor_sec'])
           for r in rows for o in r['names']['opportunities'] if o['metrics']['first_correct_name']['status']=='RIGHT_CENSORED']
    insufficient=sorted({r['case_id'] for r in core_rows if r['text']['excluded_piece_indices'] and r['text']['all_reference_occurrences']>0})
    short03=[r for r in rows if r['candidate']=='C088' and r['case_id']=='S45_03_03']
    preferred=[r for r in rows if r['variant']=='delivery_repair' and r['candidate'] in ('C065','C088') and r['repeat_index']==1]
    require(len(preferred)==68,'Preferred subset differs')
    paired_late=[]
    for p in pairs:
        if p['comparison'] not in ('C065_original_to_repair','C088_original_to_repair'):continue
        for row in p['first_text_pairs']:
            if row['timing_comparable']:
                paired_late.append(dict(left=p['left_job_id'],right=p['right_job_id'],utterance_id=row['utterance_id'],delta_sec=row['consumer_right_minus_left_sec']))
    paired_late.sort(key=lambda x:x['delta_sec'],reverse=True)
    descriptive=dict(status='DESCRIPTIVE_ONLY',inputs=bindings,comparisons=comparisons,all_repeats=repeat_checks,
                     all_never_correct=never,first_repeat_C088_name_census=observed_census([r for r in preferred if r['candidate']=='C088'],'first_correct_name'),
                     first_repeat_C088_stable_census=observed_census([r for r in preferred if r['candidate']=='C088'],'first_stable_correct_name'),
                     short03_03_C088_census=observed_census(short03,'first_correct_name'),incomplete_speech_cases=insufficient,
                     C088_final_name_changes=latest_changes,largest_ten_repair_consumer_delays=paired_late[:10])
    proposal=dict(schema='s6d-native176-retention-cache-proposal.v1',status='PROPOSAL_ONLY_ROOT_DECISION_REQUIRED',root_acceptance=None,
                  source=binding(__file__),summary=bindings['SUMMARY.json'],credit_metadata=bindings['CREDIT68_METADATA_PROPOSAL.json'],
                  candidate_dispositions=[
                      dict(candidate='C065',proposal='RETAIN_AS_ANONYMOUS_RESEARCH_CONTROL_FOR_FULL240_CONFIRMATION',
                           rationale='All42 matched repair pairs preserve raw words/spans and full source. Pooled conditioned text error unchanged; anonymous cpWER improves descriptively. Latency tails regress in some rows; no universal timing benefit or default promotion.'),
                      dict(candidate='C088',proposal='RETAIN_AS_LIMITED_NAMED_RESEARCH_CANDIDATE_FOR_FULL240_CONFIRMATION',
                           rationale='All42 matched repair pairs preserve raw words/spans. Correct10/34 and stable5/34 enrolled eligible repeated opportunities; same counts as parent, no qualified wrong-known-name exposure.24 never-correct, including short replies, and102 unavailable remain. Two final names improve but this does not establish general short-reply recovery or timing dominance.'),
                      dict(candidate='C105',proposal='RETAIN_SENTINEL_DIAGNOSTIC_ONLY_NO_GENERAL_PROMOTION_OR_CACHE_CREDIT',
                           rationale='Eight boundary jobs now scoped-scoreable under171+5 composite. All4 repair pairs preserve raw words. Names are withheld/unselected; unknown remains. RepairedO0r2 cpWER21/41 versus1/41 parent and repairedr1 is an adverse repeat; actual GUI ordering/render timing remains untested.')],
                  cache=dict(preferred_metadata_matches=68,accepted_credits=0,all_predeclared_repeats_retained=True,
                             membership='Fixed17 cases xC065/C088 xO0/O1, preferred delivery_repair_r1 only. No C105, old-original or recovery5 credit.',
                             predicates_verified='Exact preferred ID, original source manifest, result/audit/completion joins, predeclared PCM/full-frame values, settings/profile/gallery, serial affinity12-15 and all declared repeats. Fulljournal proof delegated to unchanged885634 acceptance; no journal re-read.',
                             pending=['Root retains exact research candidates after reviewing all adverse and unavailable observations.',
                                      'Root accepts each exact preferred credit and full prediction/source-context/pacing compatibility with the future892 epoch; wrapperV5/V3 migration is not automatically scientific equivalence.',
                                      'Full240 plan remains960 cells. Any rejected credit requires explicit replacement scope, never selectingr2 after outcomes.']),
                  serial892_pending=['Root-only literal queue/approval and all V5/V3/80 authority bindings.',
                                     'One total native efficacy NNworker, threadpools1, controlled allocation; no overlap with C/Tk/HOST timing.',
                                     'C12, Tk8 and HOST2 remain separate unmet requirements. Their completion/allocation gates are not waived.',
                                     'Fresh process/resource/closed-owner admission, C>=50GiB, G>=75GiB, exact80GiB exception and all payload roots.',
                                     'Original72h deadline and45min closeout reserve. Root must assess remaining wall time against historical~19.4-20.9h forecast; no timeout/duration shortening or incomplete-case promotion.',
                                     'Original171 blocked checkpoint, old stopped C105 and all charges/failures remain preserved.'],
                  execution_approval_created=False)
    lines=['# Native176 closed results and retention proposal','',
           'All176 scientific IDs are scored:168core and8C105 diagnostic, comprising171 original closed jobs and5 exact fresh recoveries. The old176 checkpoint remains REPORT_BLOCKED; the stopped old C105 result is uncredited. Exact scorer retry exited0. This report is descriptive and creates no retention, cache, or future execution approval.','',
           'All176 predeclared pair comparisons preserve entire raw text, exact final raw rows and supplied final source spans. All388 first-row comparison opportunities are comparable. Reference-conditioned text correctness has a narrower population than this text-equivalence check.','',
           '| Condition | Jobs | Serialized errors/reference words | Pooled per-job anonymous cpWER | Correct / eligible enrolled | Stable / eligible enrolled |',
           '|---|---:|---:|---:|---:|---:|']
    for name in ('C065_original','C065_delivery_repair','C088_original','C088_delivery_repair','C105_original','C105_delivery_repair'):
        v=summary['groups'][name];wc=v['serialized_words']['counts'];co=v['metrics']['first_correct_name'];st=v['metrics']['first_stable_correct_name'];cp=v['anonymous_cpwer']['pooled_error_rate']
        lines.append(f"| {name} | {v['jobs']} | {wc['errors']}/{wc['reference_words']} | {cp:.3%} | {co['observed']}/{co['eligible']} | {st['observed']}/{st['eligible']} |")
    lines += ['', 'Each42-job core group has136 reference occurrences:106 eligible text occurrences and30 excluded due incomplete speech reference. Correct naming for C088 has34 enrolled eligible occurrences:10 observed,24 right-censored; the other102 are30 incomplete,50 withheld/unselected and22 intended-but-unavailable. Confirmed/stable naming is5/34, with29 right-censored. C065 has no gallery, and C105 targets are withheld/unselected; their0/0 naming entries are unavailable controls, not success rates.',
              '', 'The four incomplete speech cases are '+', '.join(insufficient)+'. No full-session WER is claimed there.24 zero-reference noise/silence jobs emitted zero final raw words; they remain separate from reference-word WER. Repeats remain observations, not independent cases. Among the fixed C088 preferredr1 rows, correct-name statuses are '+json.dumps(descriptive['first_repeat_C088_name_census'])+'.',
              '', 'Short-reply S45_03_03 is adverse: all C088 original/repaired O0/O1 repeats have no correct name in the48 combined enrolled opportunities. Raw serialized text is correct for its10 words per job, but anonymous cpWER is100% and only one first-text opportunity is attributable among six reference turns per job. Merged utterance spans are not split into invented word timestamps.',
              '', '| Comparison (right minus left) | Pairs | First rows | Median consumer delta(s) | p95 delta(s) | Right earlier / later |', '|---|---:|---:|---:|---:|---:|']
    for name,v in summary['pair_families'].items():
        q=v['consumer_right_minus_left_sec']
        lines.append(f"| {name} | {v['pairs']} | {q['n']} | {q['p50']:+.3f} | {q['p95']:+.3f} | {q['right_earlier']}/{q['right_later']} |")
    lines += ['', 'These paired observations show mixed timing, not universal improvement. C065 repair has36 later rows (maximum+4.040s); C088 has38 (maximum+4.238s). Two biggest examples and every per-pair delta are in DESCRIPTIVE_COMPARISONS.json/PAIR176.json. First-text reference-level censored cases remain separate; per core group71/106 are observed and35 are right-censored. Timing is actual headless publication/consumer timing, not Tk rendering or physical scanout; host/load/time drift is not causally isolated.',
              '', 'C088 final qualified correct-name rows increase8→10 while opportunity-level ever-correct stays10/34 and stable stays5/34. No wrong-known-name exposure was scored in qualified visible intervals. Unqualified/hidden intervals are retained, so this is not proof of zero wrong names everywhere. Row-seconds overlap and must not be read as wall-clock percentages.',
              '', 'C105 remains diagnostic only. Its four repair comparisons preserve raw words; first-text median delta is−0.833s with four later rows. The repaired O0 second repeat changes anonymous cpWER from1/41 to21/41 despite unchanged text, so the pooled diagnostic cpWER worsens26.829%→39.024%. All12 naming opportunities per condition are withheld/unselected. This does not demonstrate general name recovery or actual GUI ordering repair.',
              '', 'Recommend retaining C065 as the anonymous research control and C088 as a limited named research candidate for the required full240 confirmation, conditional on root review. This is a recommendation to continue evaluation, not default promotion, latency dominance or study completion. Preserve C105 as an adverse sentinel; do not extend it to the general matrix.',
              '', 'The68 fixed preferred repairedr1 metadata joins pass against the accepted full-source composite proof. Accepted credits remain zero until root reviews retention and exact future source/profile/gallery/PCM/context/pacing compatibility. Four repeated cases retain both repeats; none may be replaced by a more favorable repeat. If all68 are accepted,892 new serial jobs plus68 credits cover960 cells. Any rejected credit requires an explicit revised plan.',
              '', 'Future892 remains gated by root authority, one total native efficacy NNworker, threadpools1, controlled allocation, separate C12/Tk/HOST closure, current process/resource checks, C50/G75GiB floors, exact80GiB exception, and original deadline/45min closeout reserve. No current resource census, process query, model/scorer call or approval was performed by this report.',
              '', 'Exact input bindings and all adverse/never-correct cases are retained in the adjacent JSON files and original scored outputs. Metrics are unchanged4260 through composite31408; current accepted specaf0951 uses the reviewed identical-byte dependency relocation.']
    output.mkdir(parents=True)
    outputs=[]
    for name,value in {'DESCRIPTIVE_COMPARISONS.json':descriptive,'RETENTION_CACHE_PROPOSAL.json':proposal}.items():
        p=output/name;p.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8');outputs.append(binding(p))
    p=output/'ANALYSIS.md';p.write_text('\n'.join(lines)+'\n',encoding='utf-8');outputs.append(binding(p))
    receipt=dict(status='DESCRIPTIVE_RETENTION_REPORT_WRITTEN_NOT_APPROVED',source=binding(__file__),inputs=bindings,outputs=outputs,
                 model_calls=0,scorer_calls=0,audio_journal_reads=0,process_device_queries=0,accepted_cache_credits=0)
    p=output/'RECEIPT.json';p.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(binding(p)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args();main(args.output)
