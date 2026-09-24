"""Same-lexical-input P0 diagnostics and independently toggled finite ITN."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import string
import sys
import time


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def lexical(text):return text.lower().translate(str.maketrans('','',string.punctuation)).split()


def boundaries(text):
    # Only punctuation at the existing word boundary, never invented word gold.
    words=list(re.finditer(r"\w+(?:['’]\w+)*",text))
    return {(i,char) for i,word in enumerate(words) for char in text[word.end():words[i+1].start() if i+1<len(words) else len(text)] if char in '.,?!:;'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('prototype','models-root','truth','grammar','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--run',type=Path,action='append',default=[])
    args=p.parse_args()
    import psutil
    process=psutil.Process();process.cpu_affinity([4])
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    sys.path[:0]=[str(args.prototype),str(args.prototype/'vendor')]
    from app.paths import pipeline_config
    from app.n3_text import TextLayers
    from edge_speech_pipeline.assets import validate_assets
    from edge_speech_pipeline.models import SherpaStream
    import sherpa_onnx
    config=pipeline_config(args.output,args.models_root)
    model=config.asset('sherpa_online_punctuation_int8');vocab=config.asset('sherpa_online_punctuation_bpe')
    validate_assets([model,vocab])
    punct=object.__new__(SherpaStream)
    punct.punctuation=sherpa_onnx.OnlinePunctuation(sherpa_onnx.OnlinePunctuationConfig(
        sherpa_onnx.OnlinePunctuationModelConfig(cnn_bilstm=str(model.path),bpe_vocab=str(vocab.path),
            num_threads=1,provider='cpu',debug=False)))
    layer=TextLayers(args.grammar,expected_sha256=sha(args.grammar))
    args.output.mkdir(parents=True,exist_ok=True)
    inputs=[]
    for run in args.run:
        if not (run/'RESULT.json').exists():continue
        result=load(run/'RESULT.json')
        for record in result.get('cells',[]):
            path=Path(record['path'])
            if sha(path)!=record['sha256']:raise ValueError('ASR input result changed')
            cell=load(path)
            for i,text in enumerate(cell.get('final_utterances',[])):
                if text.strip():inputs.append((result['variant']+'_hypothesis',cell['job_id']+':'+str(i),text,None))
    seen=set()
    for cell in load(args.truth)['cells']:
        if not cell.get('screen48'):continue
        for turn in cell['turns']:
            if turn['source_id'] not in seen and turn.get('transcript'):
                seen.add(turn['source_id']);inputs.append(('original_isolated_clip_reference',turn['source_id'],turn['transcript'],turn['transcript']))
    fixtures=[
        'Amir did not pay twenty one dollars.',
        'I did not take five milligrams.',
        'She said we should keep forty centimeters.',
        'Use the lubricant W D forty; do not use water.',
        'My colleague Ameer said he would not call Amir.',
        'one hundred twenty one centimeters',
    ]
    inputs.extend(('text_only_fixture',str(i),text,None) for i,text in enumerate(fixtures))
    metrics=defaultdict(lambda:dict(cases=0,input_words=0,lexically_changed_cases=0,inserted_words=0,removed_words=0,
        p0_compute_ms=0.,input_punctuation_boundaries=0,p0_punctuation_boundaries=0,itn_changed_cases=0,
        itn_trace_edits=0,reference_punctuation_tp=0,reference_punctuation_fp=0,reference_punctuation_fn=0,
        reference_punctuation_eligible_clips=0))
    predictions=args.output/'PRIVATE_TEXT_PREDICTIONS.jsonl'
    if predictions.exists():raise ValueError('Preserve existing private text evidence; use a fresh output')
    with predictions.open('x',encoding='utf-8') as output:
        for group,identifier,text,gold in inputs:
            # Identical lexical hypotheses enter P0 independently of the
            # original/native formatting. This is not an A2/A3 production pass.
            words=' '.join(lexical(text))
            formatted=punct.punctuate(words)
            normalized=layer.transform(formatted['text'],enabled=True)
            original_tokens=lexical(words);result_tokens=lexical(formatted['text'])
            old,new=Counter(original_tokens),Counter(result_tokens)
            row=metrics[group];row['cases']+=1;row['input_words']+=len(original_tokens)
            row['lexically_changed_cases']+=int(original_tokens!=result_tokens)
            row['inserted_words']+=sum((new-old).values());row['removed_words']+=sum((old-new).values())
            row['p0_compute_ms']+=formatted['compute_ms']
            row['input_punctuation_boundaries']+=len(boundaries(text));row['p0_punctuation_boundaries']+=len(boundaries(formatted['text']))
            row['itn_changed_cases']+=int(normalized['text']!=formatted['text']);row['itn_trace_edits']+=len(normalized['trace'])
            if gold is not None and lexical(gold)==result_tokens:
                gold_bound=boundaries(gold);pred_bound=boundaries(formatted['text'])
                # Boundary indices are comparable only if the tokenizers also
                # agree in count (apostrophes/compound spellings can differ).
                tokens=lambda value:re.findall(r"\w+(?:['’]\w+)*",value.lower())
                if tokens(gold)==tokens(formatted['text']):
                    row['reference_punctuation_eligible_clips']+=1
                    row['reference_punctuation_tp']+=len(gold_bound&pred_bound)
                    row['reference_punctuation_fp']+=len(pred_bound-gold_bound)
                    row['reference_punctuation_fn']+=len(gold_bound-pred_bound)
            output.write(json.dumps(dict(group=group,id=identifier,original=text,identical_lexical_input=words,
                P0=formatted,ITN=normalized,manual_corrections=[]),ensure_ascii=False,allow_nan=False)+'\n')
    fixture_mapping=dict(alias='W D forty',preferred='WD-40',context='lubricant',approved=True)
    mapping_result=layer.transform(fixtures[3],enabled=True,approved_mappings=[fixture_mapping])
    if mapping_result['text']!='Use the lubricant WD-40; do not use water.':raise AssertionError('WD-40 contextual mapping fixture failed')
    if layer.transform(fixtures[-1],enabled=True)['text']!=fixtures[-1]:raise AssertionError('Unsupported number was partly rewritten')
    for row in metrics.values():
        tp,fp,fn=(row['reference_punctuation_'+key] for key in ('tp','fp','fn'))
        row['isolated_clip_punctuation_F1']=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None
    report=dict(schema='just-peachy.n3.text-comparison.v1',status='COMPLETE',metrics=dict(metrics),
        P0=dict(model_sha256=model.sha256,vocabulary_sha256=vocab.sha256,final_only=True),
        P1=dict(route='A2/A3 native formatted hypotheses retained unchanged in ASR events',
                comparison='complete stacks scored separately; P0 same-lexical diagnostic is not a redundant production pass'),
        P2=dict(status='UNAVAILABLE_VERIFIED_STANDALONE_CHECKPOINT',reason='Official NVIDIA HF punct and pnc searches returned no candidate; native example filename is not a weight license'),
        ITN=dict(grammar_sha256=sha(args.grammar),number_forms=load(args.grammar)['number_forms_checked'],
            default_enabled=False,WD40_contextual_fixture='PASS',unsupported_large_number_fixture='PASS',personal_mappings_created=0),
        private_predictions=dict(path=str(predictions),sha256=sha(predictions)),
        contextual_reconstruction_F1=None,limits=['Punctuation reference diagnostics apply to original isolated clips only',
            'No invented conversation-level punctuation gold','Name/negation/amount/pronoun preservation measured as lexical preservation',
            'Unconstrained missing-word or grammar rewriting deferred; no LLM captions'])
    (args.output/'TEXT_COMPARISON.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    lines=['# N3 text comparison','','| Input group | Cases | P0 lexical changes | Inserted / removed words | ITN changed cases |','|---|---:|---:|---:|---:|']
    for group,row in metrics.items():lines.append(f'| {group} | {row["cases"]} | {row["lexically_changed_cases"]} | {row["inserted_words"]} / {row["removed_words"]} | {row["itn_changed_cases"]} |')
    lines+=['','P1 is native formatting. P0 comparisons use identical lexical words. Isolated-clip punctuation diagnostics are not contextual reconstruction F1.','ITN is independently toggleable; every changed span has a trace. No personal mappings were created.','']
    (args.output/'TEXT_COMPARISON.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
