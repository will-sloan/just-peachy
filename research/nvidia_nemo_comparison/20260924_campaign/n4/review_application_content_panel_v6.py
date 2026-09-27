"""Review complete V6 panels with content joins. README_SEMANTIC_FAMILY_V6.md."""
import semantic_family_v6 as family
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_child_admission import assert_plain_path
from paced_panel_plan_guarded_v2 import execution_payload
from review_application_semantics_v6 import review_content as review_cell
from review_application_panel_v6 import compact_cell, stopped_run, validate_population
from review_application_transport_v6 import record
from review_scoring_bank import require
OUTPUT_LIMIT = family.OUTPUT_LIMIT


HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN=('review_application_content_panel.py','test_application_content_panel.py',
     'probe_application_content_panel.py','README_SEMANTIC_FAMILY_V6.md')
QUALIFICATION=family.QUALIFICATION
COUNTS=('native_spans','observed_spans','unobserved_native_spans','never_visible_observed_spans',
        'observed_spans_without_final_visibility','missing_caption_revisions','ambiguous_state_joins',
        'native_segment_entries','changed_rows','sampled_states')


def code_bindings():
    return family.code_bindings()


def add_bindings(registry, entries):
    for b in entries:
        require(b['path'] not in registry or registry[b['path']]==b,'Shared content input changed between cells')
        registry[b['path']]=b
    require(len(registry)<=32768,'Panel input binding census exceeds bound')


def compact_content(checked, row, payload, registry):
    require(checked['status']=='PASS_V6_APPLICATION_CONTENT_AND_FIXED_ROSTER_JOINS_ONLY'
        and checked['integrated_N4_cells']==0 and checked['N4_accepted'] is False
        and all(checked[k] is True for k in ('application_owner_and_primary_settings_joined',
            'fixed_display_roster_independently_joined','primary_caption_text_consistency_reviewed')),
        'Complete cell content composition required')
    require(payload['cell_id']==row['cell_id']==checked['cell']['transport']['cell_id']
        and fingerprint(payload['job'])==fingerprint(row['job'])
        and fingerprint(payload['contract'])==fingerprint(row['contract']), 'Content cell differs from planned row')
    for flag in ('exact_consumed_event_attribution','accuracy_qualified','names_independently_scored',
        'source_to_widget_latency_qualified','controlled_resources_qualified','complete_panel_reviewed',
        'physical_scanout_measured','actual_continuity_test','stop_restart_qualified'):
        require(checked[flag] is False,'Cell content reader improperly promoted '+flag)
    base=compact_cell(checked['cell'],row,payload);w=checked['widget'];r=checked['roster']
    require(w['people_sha256']==r['people_sha256'],'Cell roster fingerprint differs')
    counts=dict(native_spans=w['native_span_population'],observed_spans=w['observed_span_population'],
        unobserved_native_spans=len(w['native_spans_not_observed']),never_visible_observed_spans=w['observed_spans_never_visible'],
        observed_spans_without_final_visibility=w['observed_spans_without_final_visibility'],
        missing_caption_revisions=len(w['missing_native_caption_revisions']),ambiguous_state_joins=w['ambiguous_state_joins'],
        native_segment_entries=w['native_segment_history_entries'],changed_rows=len(w['changed_rows']),sampled_states=len(w['states']))
    require(all(type(n) is int and 0<=n<=262144 for n in counts.values())
        and counts['observed_spans']+counts['unobserved_native_spans']==counts['native_spans']
        and max(counts['never_visible_observed_spans'],counts['observed_spans_without_final_visibility'])<=counts['observed_spans']
        and counts['ambiguous_state_joins']<=counts['sampled_states'],'Content denominator census differs')
    entries=base['evidence']+w['evidence']+r['evidence']+[checked['application_qualification'],checked['source_context'],w['source_receipt'],w['casing_source']]
    unique={};add_bindings(unique,entries);add_bindings(registry,list(unique.values()))
    # All binding bytes are retained once in the panel registry. Native text,
    # heading strings and per-span histories can be reconstructed from them.
    base.pop('evidence')
    delivery=base['source_delivery'];envelope=delivery['envelope']
    require(registry.get(envelope['path'])==envelope,'Delivery summary envelope missing from panel registry')
    summary=delivery.pop('summary')
    delivery.update(summary_sha256=fingerprint(summary),summary_storage='bound_envelope.review.summary',
        raw_summary_preserved_in_bound_envelope=True)
    return dict(base,status='PASS_V6_CELL_CONTENT_COVERAGE_ONLY',
        full_content_review_sha256=fingerprint(checked),content_inputs_sha256=fingerprint(sorted(unique.values(),key=lambda b:b['path'])),
        content_counts=counts,maximum_observation_interval_seconds=w['maximum_observation_interval_seconds'],
        roster={k:r[k] for k in ('people_sha256','available_size','intended_size','unavailable_count','ordering')},
        primary_caption_text_consistency_reviewed=True,exact_consumed_event_attribution=False,names_independently_scored=False)


def aggregate(summaries):
    require(type(summaries) is list and 1<=len(summaries)<=240,'Bounded panel summaries required')
    groups={};ids=set();rosters={}
    for s in summaries:
        require(s['status']=='PASS_V6_CELL_CONTENT_COVERAGE_ONLY' and s['cell_id'] not in ids
            and s['integrated_N4_cells']==0 and s['N4_accepted'] is False,'Repeated or unreviewed panel summary')
        ids.add(s['cell_id']);composition=s['composition'];roster=fingerprint(s['roster'])
        require(composition not in rosters or rosters[composition]==roster,'Fixed roster changed within one composition')
        rosters[composition]=roster;key=(composition,s['kind'],s['tap'])
        g=groups.setdefault(key,dict(composition=composition,kind=s['kind'],tap=s['tap'],cells=0,
            counts={k:0 for k in COUNTS},cells_without_native_segments=0,maximum_observation_interval_seconds=0.))
        g['cells']+=1
        for k in COUNTS:
            n=s['content_counts'][k];require(type(n) is int and n>=0,'Invalid content count');g['counts'][k]+=n
        g['cells_without_native_segments']+=int(s['content_counts']['native_segment_entries']==0)
        interval=s['maximum_observation_interval_seconds']
        require(type(interval) in (int,float) and 0<=interval<3900,'Invalid viewport sampling interval')
        g['maximum_observation_interval_seconds']=max(g['maximum_observation_interval_seconds'],interval)
    return dict(cells=len(summaries),groups=[groups[k] for k in sorted(groups)],
        counting_unit='Cell-span observations; repeats and taps remain separate; not unique corpus words or speakers',
        timing_scope='Maximum recorded sampling interval only; no exact event attribution, latency or continuous visibility',
        naming_accuracy_qualified=False,source_to_widget_latency_qualified=False,integrated_N4_cells=0,N4_accepted=False)


def population(context):
    folder=context['folder'];plan=context['plan']
    cells=assert_plain_path(folder/'cells',folder);progress_root=assert_plain_path(folder/'progress',folder)
    cell_entries=list(cells.iterdir());progress_entries=list(progress_root.iterdir())
    require(len(cell_entries)<=240 and len(progress_entries)<=240,'Panel directory census exceeds bound')
    for p in cell_entries:require(assert_plain_path(p,folder).is_dir(),'Unexpected non-directory cell entry')
    for p in progress_entries:require(assert_plain_path(p,folder).is_file(),'Unexpected non-file progress entry')
    collected=[];progress=[];bindings=[]
    for i,row in enumerate(plan['rows']):
        b,_=record(cells/row['cell_id']/'COLLECTED.json',folder);collected.append(b)
        b,value=record(progress_root/f'{i+1:04d}.json',folder);bindings.append(b);progress.append(value)
    census=validate_population(plan,context['terminal'],collected,progress,[p.name for p in cell_entries],[p.name for p in progress_entries])
    return cells,collected,bindings,census


def run(run_root, output):
    return family.run_panel(run_root, output, 'content')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();run(args.run,args.output)
