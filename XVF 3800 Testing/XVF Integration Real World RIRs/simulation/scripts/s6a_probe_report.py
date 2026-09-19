"""Paired, population-aware interpretation of completed S6A probes. README_S6A_PROBE_REPORT.md."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import statistics
from s6a_common import *
from s6a_probe_analysis import csv_write

POP_METRIC={'primary_nonoverlap':'text','overlap_complete':'overlap_mimo',
            'ambient_incomplete':'target_only_text','strict_empty':'text'}
PAIRS=[('P0X0','P0X1','original_components_advisory_cue_route'),
       ('P1X0','P1X1','tuned_components_advisory_cue_route'),
       ('P0X0','P1X0','joint_components_cues_off'),
       ('P0X1','P1X1','joint_components_cues_on'),
       ('SEG_X0','SEG_X1','segmentation_soft_energy'),
       ('P0X0','SEG_X0','segmentation_and_tracker_mode_delta'),
       ('P0X0','EMBED_LONG','embedding_duration'),
       ('P0X0','EMBED_CADENCE_QUALITY','embedding_cadence_and_RMS'),
       ('P0X0','ENDPOINT_X0','endpoint_and_dispatch'),
       ('ENDPOINT_X0','ENDPOINT_X1','endpoint_advisory_cue_route')]

def rate(n,d):return n/d if d else None

def identity_short_summary(turns):
    mapped=[t for t in turns if t.get('mapping_available')]
    known=sum(t.get('modal_label') not in (None,'','Unknown') for t in mapped)
    sole=sum(t.get('sole_active_samples') or 0 for t in mapped)
    known_samples=sum(t.get('known_samples') or 0 for t in mapped)
    unknown_samples=sum(t.get('unknown_samples') or 0 for t in mapped)
    assert known_samples+unknown_samples==sole
    return dict(identity_source_turns=len(turns),identity_mapped_turns=len(mapped),
                identity_mapping_unavailable_turns=len(turns)-len(mapped),
                identity_zero_sole_speech_turns=sum(not t.get('sole_active_samples') for t in mapped),
                identity_known_modal_turns=known,identity_unknown_modal_turns=len(mapped)-known,
                identity_sole_active_samples=sole,identity_known_samples=known_samples,identity_unknown_samples=unknown_samples,
                identity_unknown_fraction=rate(unknown_samples,sole))

def text_value(record):
    return record['metrics']['text_metrics'].get(POP_METRIC[record['population']],{})

def paired_rows(records):
    lookup={(r['profile_id'],r['case_id'],r['stream']):r for r in records}
    keys=sorted({(r['case_id'],r['stream']) for r in records})
    rows=[]
    for parent,candidate,mechanism in PAIRS:
        for cid,stream in keys:
            left=lookup[(parent,cid,stream)];right=lookup[(candidate,cid,stream)]
            pop=left['population'];assert pop==right['population']
            lc=text_value(left).get('word_counts',{});rc=text_value(right).get('word_counts',{})
            assert lc.get('reference_words')==rc.get('reference_words')
            row={'parent':parent,'candidate':candidate,'mechanism':mechanism,'case_id':cid,'stream':stream,
                 'population':pop,'reference_words':lc.get('reference_words'),
                 'parent_errors':lc.get('errors'),'candidate_errors':rc.get('errors'),
                 'word_error_delta':rc['errors']-lc['errors'] if 'errors' in lc and 'errors' in rc else None}
            for prefix,key in [('cp','attributed_cpwer')]:
                a=left['metrics']['text_metrics'].get(key,{}).get('word_counts',{})
                b=right['metrics']['text_metrics'].get(key,{}).get('word_counts',{})
                assert a.get('reference_words')==b.get('reference_words')
                row.update(cp_reference_words=a.get('reference_words'),parent_cp_errors=a.get('errors'),
                           candidate_cp_errors=b.get('errors'),cp_error_delta=b['errors']-a['errors'] if a and b else None)
            for k in ('embedding_calls','embedding_compute_s','segmentation_compute_s','asr_compute_s',
                      'native_endpoint_count','advisory_endpoint_count','speech_assisted_segmentation_calls'):
                row['delta_'+k]=right['metrics'][k]-left['metrics'][k]
            rows.append(row)
    return rows

def pooled_pairs(rows):
    groups=defaultdict(list)
    for row in rows:groups[(row['parent'],row['candidate'],row['mechanism'],row['stream'],row['population'])].append(row)
    result=[]
    for (parent,candidate,mechanism,stream,pop),selected in sorted(groups.items()):
        row=dict(parent=parent,candidate=candidate,mechanism=mechanism,stream=stream,population=pop,paired_scenes=len(selected))
        for k in ('reference_words','parent_errors','candidate_errors','cp_reference_words','parent_cp_errors','candidate_cp_errors'):
            vals=[r[k] for r in selected if r[k] is not None];row[k]=sum(vals) if vals else None
        row['candidate_minus_parent_wer_pp']=100*(row['candidate_errors']-row['parent_errors'])/row['reference_words'] if row['reference_words'] else None
        row['candidate_minus_parent_cpwer_pp']=100*(row['candidate_cp_errors']-row['parent_cp_errors'])/row['cp_reference_words'] if row['cp_reference_words'] else None
        deltas=[r['word_error_delta'] for r in selected if r['word_error_delta'] is not None]
        row.update(lower_error_scenes=sum(d<0 for d in deltas),equal_error_scenes=sum(d==0 for d in deltas),higher_error_scenes=sum(d>0 for d in deltas))
        for k in selected[0]:
            if k.startswith('delta_'):row[k]=sum(r[k] for r in selected)
        result.append(row)
    return result

def details(records):
    groups=defaultdict(list)
    for r in records:groups[(r['profile_id'],r['stream'])].append(r)
    rows=[];short_rows=[];region_rows=[]
    for (profile,stream),selected in sorted(groups.items()):
        metrics=[r['metrics'] for r in selected];lineage=Counter();purity=Counter()
        for m in metrics:lineage.update(m['lineage_counts']);purity.update(m['embedding_purity_file_envelopes'])
        row=dict(profile_id=profile,stream=stream,scenes=len(selected))
        row.update({'lineage_'+k:v for k,v in lineage.items()});row.update({'purity_'+k:v for k,v in purity.items()})
        row['purity_scope']='Complete known source file envelopes, not oracle acoustic purity; incomplete ambient speech remains unknown'
        mapped=[r for r in selected if r['metrics']['tracking_metrics']['status']!='UNAVAILABLE_OUTPUT_ALIGNMENT']
        row['mapped_scenes']=len(mapped);row['alignment_unavailable_scenes']=len(selected)-len(mapped)
        empty=[r for r in selected if r['population']=='strict_empty']
        words=sum(text_value(r).get('empty_reference_insertions') or 0 for r in empty)
        duration=sum(r['metrics']['text_metrics']['decoded_duration_s'] for r in empty)
        row.update(strict_empty_scenes=len(empty),strict_inserted_words=words,strict_duration_s=duration,strict_words_per_minute=rate(words*60,duration))
        row['first_partial_modeled_median_s']=statistics.median([m['first_readable_partial_modeled_s'] for m in metrics if m['first_readable_partial_modeled_s'] is not None]) if any(m['first_readable_partial_modeled_s'] is not None for m in metrics) else None
        row['first_partial_modeled_available_outputs']=sum(m['first_readable_partial_modeled_s'] is not None for m in metrics)
        row['first_partial_modeled_unavailable_outputs']=len(metrics)-row['first_partial_modeled_available_outputs']
        row['first_partial_time_scope']='Source file origin; warm modeled first nonempty partial timestamp, not speech-onset latency'
        for population_name in ('primary_nonoverlap','overlap_complete','ambient_incomplete','strict_empty'):
            chosen=[r for r in selected if r['population']==population_name]
            for bin_name in ('<1s','1-<2s','>=2s'):
                turns=[s for r in chosen for s in r['metrics']['short_turns'] if s['whole_clip_bin']==bin_name]
                eligible=[s for s in turns if s['source_specific_eligible']]
                waits=[s['first_contained_embedding_modeled_wait_s'] for s in eligible if s['first_contained_embedding_modeled_wait_s'] is not None]
                identity_turns=[t for r in chosen for t in r['metrics']['tracking_metrics']['turns'] if t['whole_clip_bin']==bin_name]
                short_rows.append(dict(profile_id=profile,stream=stream,population=population_name,whole_clip_bin=bin_name,
                    mapped_turns=len(turns),source_specific_eligible_turns=len(eligible),eligible_without_contained_window=sum(not s['contained_embedding_count'] for s in eligible),
                    supported_samples=sum(s['support_samples'] for s in eligible),speech_flag_samples=sum(s['speech_flag_samples'] for s in eligible),
                    waits_measured=len(waits),wait_median_s=statistics.median(waits) if waits else None,wait_max_s=max(waits) if waits else None,
                    **identity_short_summary(identity_turns),identity_reference_complete=population_name!='ambient_incomplete',
                    scope='Input-only denominator; whole clip bin; full source file containment; wait from aligned file start, warm modeled availability; identity coverage uses all input turns and is not identity correctness'))
            names=sorted({n for r in chosen for n in r['metrics']['regions']})
            for name in names:
                values=[r['metrics']['regions'][name] for r in chosen if name in r['metrics']['regions']]
                totals={k:sum(v[k] for v in values) for k in ('support_samples','observed_samples','speech_flag_samples','overlap_flag_samples')}
                region_rows.append(dict(profile_id=profile,stream=stream,population=population_name,region=name,contributing_scenes=len(values),**totals,
                    speech_flag_fraction=rate(totals['speech_flag_samples'],totals['support_samples']),
                    overlap_flag_fraction=rate(totals['overlap_flag_samples'],totals['support_samples']),
                    scope='Coarse trailing output spans; source activity estimates and alignment; not frame-exact segmentation truth'))
        rows.append(row)
    return rows,short_rows,region_rows

def baseline_comparison(records):
    receipt=read(REPORT/'BASELINE_SCORE_RECEIPT.json')
    assert receipt['status']=='COMPLETE' and receipt['complete']==480, 'Full bound B0 scores required'
    bindings={(r['case_id'],r['stream']):r['result'] for r in receipt['rows']}
    rows=[]
    for record in records:
        cid,out=record['case_id'],record['stream']
        baseline_binding=bindings[(cid,out)];bind(baseline_binding['path'],baseline_binding['sha256'])
        baseline=read(baseline_binding['path'])
        metric=POP_METRIC[record['population']]
        left=baseline['text_metrics'].get(metric,{});right=text_value(record)
        baseline_words=baseline['text_metrics']['text'].get('hypothesis_normalized')
        candidate_words=record['metrics']['text_metrics']['text'].get('hypothesis_normalized')
        assert isinstance(baseline_words,str) and isinstance(candidate_words,str), 'Lexical parity needs actual normalized words, including overlap'
        lc,rc=left.get('word_counts',{}),right.get('word_counts',{})
        assert lc.get('reference_words')==rc.get('reference_words')
        rows.append(dict(profile_id=record['profile_id'],case_id=cid,stream=out,population=record['population'],
            reference_words=lc.get('reference_words'),baseline_errors=lc.get('errors'),candidate_errors=rc.get('errors'),
            candidate_minus_baseline_errors=rc['errors']-lc['errors'] if lc and rc else None,
            exact_normalized_words=baseline_words==candidate_words,
            scope='B0 exact archived implementation; P0 retains original component settings but uses new reliability tracker'))
    return rows

def build():
    receipt=read(REPORT/'PROBE_ANALYSIS_RECEIPT.json');assert receipt['status']=='COMPLETE' and receipt['complete']==720
    rows=[]
    for row in receipt['rows']:
        b=row['result'];bind(b['path'],b['sha256']);rows.append(read(b['path']))
    assert len({(r['profile_id'],r['case_id'],r['stream']) for r in rows})==720
    pairs=paired_rows(rows);pooled=pooled_pairs(pairs);detail,short,regions=details(rows);baseline=baseline_comparison(rows)
    folder=REPORT/'probe_results';tables=[]
    for name,values in [('PAIRED_SCENE_DELTAS.csv',pairs),('PAIRED_POPULATION_DELTAS.csv',pooled),
                        ('EVIDENCE_AND_LINEAGE.csv',detail),('SOURCE_SHORT_TURN_COVERAGE.csv',short),
                        ('SOURCE_REGION_FLAGS.csv',regions),('BASELINE_COMPONENT_COMPARISON.csv',baseline)]:
        path=folder/name;csv_write(path,values);tables.append(bind(path))
    controls=[r for r in baseline if r['profile_id']=='P0X0']
    result={'status':'COMPLETE','created_utc':now(),'native_v2_outputs':len(rows),'paired_rows':len(pairs),
            'P0X0_B0_lexical_parity':{'outputs':len(controls),'exact_words':sum(r['exact_normalized_words'] for r in controls),
                                  'different_words':[r for r in controls if not r['exact_normalized_words']]},
            'inputs':[bind(REPORT/'PROBE_ANALYSIS_RECEIPT.json'),bind(REPORT/'BASELINE_SCORE_RECEIPT.json')],
            'code':[bind(__file__),bind(SIM/'scripts/s6a_probe_analysis.py')], 'tables':tables,
            'scope':'Fixed36 observed scenes, all taps; no population causal claim; dependent scenes and repeated sources; no confirmed winner.',
            'pairwise_population_deltas':pooled,'evidence_and_lineage':detail}
    save(folder/'PROBE_REPORT_RECEIPT.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('pairwise_population_deltas','evidence_and_lineage','tables')}))

def fixtures():
    # An adversarial unequal-denominator pair prevents averaging per-scene WER.
    rows=[]
    for cid,words,old,new in [('short',1,1,0),('long',99,0,2)]:
        rows.append(dict(parent='a',candidate='b',mechanism='x',stream='O0',population='primary_nonoverlap',
                         case_id=cid,reference_words=words,parent_errors=old,candidate_errors=new,word_error_delta=new-old,
                         cp_reference_words=words,parent_cp_errors=old,candidate_cp_errors=new))
    value=pooled_pairs(rows)[0]
    assert value['candidate_minus_parent_wer_pp']==1.0 and value['lower_error_scenes']==1 and value['higher_error_scenes']==1
    rows[0]['population']='ambient_incomplete'
    assert len(pooled_pairs(rows))==2, 'Incomplete references must never be pooled with complete-reference ASR'
    empty=[dict(rows[0],reference_words=None,parent_errors=None,candidate_errors=None,word_error_delta=None,
                cp_reference_words=None,parent_cp_errors=None,candidate_cp_errors=None,population='strict_empty')]
    assert pooled_pairs(empty)[0]['candidate_minus_parent_wer_pp'] is None, 'Empty reference is not zero WER'
    coverage=identity_short_summary([
        dict(mapping_available=True,modal_label='Unknown',sole_active_samples=20,known_samples=5,unknown_samples=15),
        dict(mapping_available=True,modal_label='Speaker_1',sole_active_samples=30,known_samples=30,unknown_samples=0),
        dict(mapping_available=False,modal_label='Unknown',sole_active_samples=None,known_samples=None,unknown_samples=None)])
    assert coverage['identity_source_turns']==3 and coverage['identity_mapping_unavailable_turns']==1
    assert coverage['identity_known_modal_turns']==1 and coverage['identity_unknown_modal_turns']==1
    assert coverage['identity_unknown_fraction']==.3
    save(REPORT/'probe_results/ANALYSIS_FIXTURE_RECEIPT.json',{'status':'PASS','checks':4,'code':bind(__file__),'utc':now()})
    print('PASS: unequal-denominator pooling, reference-population separation, empty-reference rate semantics, retained short-turn unknown/missing support')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--test',action='store_true')
    if parser.parse_args().test:fixtures()
    else:build()
