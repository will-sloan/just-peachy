"""Evaluator-only N3 lexical metrics; no truth is passed to inference."""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def score_run(folder,truth,scoring):
    result=load(folder/'RESULT.json');lock=load(folder/'RUN_LOCK.json')
    groups=defaultdict(lambda:dict(cells=0,reference_words=0,word_errors=0,reference_characters=0,
        character_errors=0,output_words=0,source_seconds=0.,compute_seconds=0.,wall_seconds=0.,
        cpu_seconds=0.,peak_rss_bytes=0,revision_removals=0,cp_errors=0,cp_reference_words=0))
    cells=[]
    for bound in result['cells']:
        path=Path(bound['path'])
        if sha(path)!=bound['sha256']:raise ValueError('Inference receipt hash changed')
        cell=load(path)
        if cell['status']!='COMPLETE':raise ValueError('Aggregate referenced an incomplete cell')
        if sha(path.parent/'events.jsonl')!=cell['events_sha256']:raise ValueError('Raw ASR events changed')
        ref=truth[cell['job_id'].replace('N3_','N2_',1)]
        group=groups[(ref['reference_class'],ref['tap'])]
        ref_words=[];streams=defaultdict(list)
        # Authoritative manifest order, not an alignment optimized to a model.
        for turn in ref['turns']:
            w=scoring.words(turn['transcript_normalized']);ref_words.extend(w);streams[turn['identity']].extend(w)
        hyp=scoring.words(cell['raw_final_text'])
        rchars=list(' '.join(ref_words));hchars=list(' '.join(hyp))
        errors=scoring.edit_distance(ref_words,hyp);char_errors=scoring.edit_distance(rchars,hchars)
        group['cells']+=1;group['reference_words']+=len(ref_words);group['word_errors']+=errors
        group['reference_characters']+=len(rchars);group['character_errors']+=char_errors
        group['output_words']+=len(hyp);group['source_seconds']+=cell['source_seconds']
        group['compute_seconds']+=cell['compute_ms']/1000;group['wall_seconds']+=cell['elapsed_seconds']
        group['cpu_seconds']+=cell['cpu_seconds'];group['peak_rss_bytes']=max(group['peak_rss_bytes'],cell['peak_process_rss_bytes'])
        group['revision_removals']+=cell['word_revision_removals']
        if ref['reference_class']=='complete_overlap' and ref['complete_reference']:
            cp=scoring.cpwer(dict(streams),{'unassigned_mono_output':hyp})
            group['cp_errors']+=cp['errors'];group['cp_reference_words']+=cp['reference_words']
        cells.append(dict(job_id=cell['job_id'],reference_class=ref['reference_class'],tap=ref['tap'],
            reference_words=len(ref_words),word_errors=errors,character_errors=char_errors,
            output_words=len(hyp),all_samples=cell['input_samples']==ref['frames'],
            first_text_elapsed_sec=cell['first_text_elapsed_sec'],finalization_after_source_sec=cell['finalization_after_source_sec']))
    table=[]
    for (category,tap),row in sorted(groups.items()):
        complete=category=='complete_nonoverlap'
        row.update(reference_class=category,tap=tap,
            WER=row['word_errors']/row['reference_words'] if complete and row['reference_words'] else None,
            CER=row['character_errors']/row['reference_characters'] if complete and row['reference_characters'] else None,
            chronological_diagnostic_WER=row['word_errors']/row['reference_words'] if not complete and row['reference_words'] else None,
            diagnostic_scope='fixed chronological order; ambient references are target-only and incomplete' if not complete else 'complete nonoverlap reference',
            single_output_cpWER=row['cp_errors']/row['cp_reference_words'] if row['cp_reference_words'] else None,
            cpWER_scope='complete overlap reference speakers versus one unassigned mono hypothesis; no speaker attribution claim',
            false_words_per_minute=row['output_words']*60/row['source_seconds'] if not row['reference_words'] and row['source_seconds'] else None,
            compute_RTF=row['compute_seconds']/row['source_seconds'] if row['source_seconds'] else None)
        table.append(row)
    return dict(variant=result['variant'],runtime=result['runtime'],status=result['status'],
        completed=result['completed'],total=result['total'],run_result_sha256=sha(folder/'RESULT.json'),
        contract_sha256=result['contract_sha256'],delivery=lock['delivery'],table=table,cells=cells,
        VRAM=dict(status='NOT_MEASURED_PER_PROCESS_NATIVE_WDDM',bytes=None),
        timing_limits='accelerated runs do not establish live latency; sampled RSS is not total CM5 system memory',
        lexical_normalization='N2 words: lowercase, delete ASCII punctuation, whitespace split; CER joins normalized words with spaces')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--truth',type=Path,required=True);p.add_argument('--run',type=Path,action='append',required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    source=Path(__file__).resolve().parents[1]/'n2/evaluation/scoring.py'
    spec=importlib.util.spec_from_file_location('n3_reused_scoring',source)
    scoring=importlib.util.module_from_spec(spec);spec.loader.exec_module(scoring)
    truth={row['job_id']:row for row in load(args.truth)['cells']}
    results=[];missing=[]
    for folder in args.run:
        if not (folder/'RESULT.json').exists() or not (folder/'RUN_LOCK.json').exists():missing.append(str(folder));continue
        results.append(score_run(folder,truth,scoring))
    report=dict(schema='just-peachy.n3.lexical-comparison.v1',status='COMPLETE' if not missing and all(r['status']=='COMPLETE' for r in results) else 'PARTIAL',
        evaluator_truth_sha256=sha(args.truth),scoring_sha256=sha(source),runs=results,missing_runs=missing,
        no_reference_words_removed=True,no_gt_inference=True,
        limitations=['No exact phonetic word timing truth','No contextual reconstruction punctuation F1 from concatenated isolated clips',
                     '48-scene screen cannot select a final campaign winner','Single mono ASR overlap cpWER is a diagnostic, not diarized-system cpWER'])
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'LEXICAL_COMPARISON.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    lines=['# N3 lexical comparison','', '| Variant/runtime | Class | Tap | Cells | WER | CER | Compute RTF |', '|---|---|---|---:|---:|---:|---:|']
    fmt=lambda v:'unavailable' if v is None else f'{v:.4f}'
    for run in results:
        for row in run['table']:
            lines.append(f'| {run["variant"]}/{run["runtime"]} | {row["reference_class"]} | {row["tap"]} | {row["cells"]} | {fmt(row["WER"])} | {fmt(row["CER"])} | {fmt(row["compute_RTF"])} |')
    lines+=['','Primary WER/CER use complete nonoverlap references. See JSON for overlap, incomplete ambient and false-word controls.','Raw transcripts remain private. No winner is selected from this screen.','']
    (args.output/'LEXICAL_COMPARISON.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
