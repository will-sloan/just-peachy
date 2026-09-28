"""Read-only saved-corpus suitability audit; README_FINETUNING_ASSESSMENT_V1.md."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'n4'))
from common import bind, freeze, load, verify
from metric_process import pin


def audit(output):
    pin(); data=HERE.parent/'data'
    receipt=load(data/'DATA_AUDIT_SUMMARY.json')
    selected={Path(b['path']).name:b for b in receipt['local_evidence']}
    bindings=[selected[n] for n in ('CORPUS_BINDINGS_240.json','FULL_TRANSCRIPT_AUDIT.json')]
    for b in bindings:verify(b)
    corpus=load(bindings[0]['path'])['scenes']; occurrences=load(bindings[1]['path'])['occurrences']
    rows=list(csv.DictReader((data/'CORPUS_CATALOGUE_240.csv').open(encoding='utf-8-sig')))
    assert len(rows)==len(corpus)==240 and len(occurrences)==777
    assert {r['case_id'] for r in rows}=={s['summary']['case_id'] for s in corpus}
    by_case={r['case_id']:r for r in rows}
    def groups(key):
        grouped=defaultdict(set)
        for o in occurrences:grouped[str(o[key])].add(o['case_id'])
        return grouped
    def connected(grouped):
        parent={r['case_id']:r['case_id'] for r in rows}
        def root(a):
            while parent[a]!=a:a=parent[a]
            return a
        for cases in grouped.values():
            cases=list(cases)
            for case in cases[1:]:parent[root(case)]=root(cases[0])
        return sorted(Counter(root(case) for case in parent).values(),reverse=True)
    group_stats={}
    for key in ('source_id','speaker_key','transcript_sha256'):
        grouped=groups(key)
        cross=[v for v in grouped.values() if len({by_case[c]['historical_source_partition'] for c in v})>1]
        group_stats[key]=dict(unique=len(grouped),reused_across_scenes=sum(len(v)>1 for v in grouped.values()),
            crosses_historical_partitions=len(cross),scene_component_sizes=connected(grouped))
    result=dict(status='ASSESSMENT_ONLY_NOT_TRAINING_READY',source_audit=bind(data/'DATA_AUDIT_SUMMARY.json'),
        catalogue=bind(data/'CORPUS_CATALOGUE_240.csv'),private_inputs=bindings,
        scenes=len(rows),tap_files=2*len(rows),unique_scenario_seconds=sum(int(r['prepared_frames'])/int(r['sample_rate_hz']) for r in rows),
        references=dict(Counter(r['reference_class'] for r in rows)),families=dict(Counter(r['family'] for r in rows)),
        rooms=len({r['room'] for r in rows}),utterance_occurrences=len(occurrences),
        exact_word_timed_occurrences=sum(bool(o['word_times']) for o in occurrences),
        estimated_activity_occurrences=sum('estimated activity' in o['timing_provenance'] for o in occurrences),
        occurrence_roles=dict(Counter(o['role'] for o in occurrences)),source_reuse=group_stats,
        all_campaign_scenes_already_used_for_comparative_evaluation=True,
        train_validation_test_split_created=False,training_started=False,model_loaded=False,
        limitations=['O0/O1 are paired views, not independent examples.',
          'All timestamps are estimated activity; no exact word/phonetic gold.',
          'Incomplete ambient scenes cannot supply fully supervised all-speaker targets.',
          'Grouping by scene alone does not prevent source/speaker/text leakage.',
          'Current bank is a diagnostic/adaptation candidate, not an untouched future test set.',
          'Training rights and raw recording lineage still require a dedicated review.'],
        code=[bind(__file__),bind(HERE/'README_FINETUNING_ASSESSMENT_V1.md')])
    freeze(output,result)
    print({k:v for k,v in result.items() if k not in ('families','private_inputs','code','source_audit','catalogue','limitations')})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    audit(p.parse_args().output)
