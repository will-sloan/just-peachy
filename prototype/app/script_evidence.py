"""Optional post-recording context selection, not phonetic training. See README_SCRIPT_EVIDENCE.md."""
from copy import deepcopy
from difflib import SequenceMatcher
import hashlib
import json
import math
import re
import time
import numpy as np

SCHEMA='just-peachy.script-evidence.v1'
RATE=16000
MAX_BANK=6
MAX_BYTES=256*1024
MATCHED_UNAVAILABLE='Unavailable: no calibrated query-content confidence or validated acoustic word/phone boundaries; ordinary voice matching remains authoritative.'


def words(text):return re.findall(r"[^\W_]+(?:['’][^\W_]+)*",text.casefold().replace('’',"'"))
def text_hash(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def stored_size(document):
    # Match paths.atomic_json's actual on-disk encoding, including indentation.
    return len((json.dumps(document,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8'))


def estimated_words(utterance,total_samples):
    """Recover BPE words; retain emission bounds, never fabricate word/phone timing."""
    timing=utterance.get('token_timing') or {}
    tokens=timing.get('tokens',[]);ticks=timing.get('timestamps_sec',[]);offset=timing.get('segment_start_sec')
    if not tokens or len(tokens)!=len(ticks) or type(offset) not in (int,float) or not math.isfinite(offset):return []
    groups=[];last=-1
    for token,tick in zip(tokens,ticks):
        if not isinstance(token,str) or '<' in token or type(tick) not in (int,float) or not math.isfinite(tick):return []
        sample=round((offset+tick)*RATE)
        if sample<last or sample<0:return []
        last=sample;piece=token.replace('▁',' ')
        if piece.startswith(' ') or not groups:groups.append([piece.strip(),sample,sample])
        else:groups[-1][0]+=piece;groups[-1][2]=sample
    if words(' '.join(g[0] for g in groups))!=words(utterance['raw_asr_text']):return []
    result=[]
    for i,(text,start,last_token) in enumerate(groups):
        lexical=words(text)
        if len(lexical)!=1:return []
        # The next emission is an upper context hint, NOT the end of a phoneme.
        end=groups[i+1][1] if i+1<len(groups) else utterance['end_sample']
        # Decoder finish padding may emit a tail word beyond the real source.
        # Retain supported earlier words without clamping that tail to the file.
        if not 0<=start<=last_token<total_samples or not start<end<=total_samples:continue
        result.append(dict(word=lexical[0],recognized_index=i,estimated_start_sample=start,estimated_end_sample=end,
            utterance_id=utterance['utterance_id'],confidence=None,
            method='unbiased BPE emission onset to next-word onset/endpoint; uncalibrated',
            phone_boundaries=None,lexical_pronunciations=None,pronunciation_status='dictionary not installed; no pronunciation inferred'))
    return result


def runs(intervals):
    result=[]
    for lo,hi in intervals:
        a,b=round(lo*RATE),round(hi*RATE)
        if result and result[-1][1]==a:result[-1][1]=b
        else:result.append([a,b])
    return result


def build_evidence(audio,quality,estimate,offered,route,models,model_hashes):
    """Select bounded nonoverlapping AUDIO contexts; the base anchor is untouched."""
    started=time.perf_counter();audio=np.asarray(audio,np.float32).reshape(-1)
    if len(audio)>180*RATE or not np.isfinite(audio).all():raise ValueError('Invalid bounded enrollment audio')
    audio_hash=hashlib.sha256(audio.astype('<f4').tobytes()).hexdigest()
    if audio_hash!=quality['source_sha256']:raise ValueError('Script evidence source does not match enrollment audio')
    utterances=deepcopy(estimate.get('utterances',[]))
    actual=' '.join(u['raw_asr_text'] for u in utterances)
    intended=words(offered);heard=words(actual)
    ops=SequenceMatcher(None,intended,heard,autojunk=False).get_opcodes()
    matching={j for tag,a,b,c,d in ops if tag=='equal' for j in range(c,d)}
    spans=[];word_index=0
    for utterance in utterances:
        mapped=estimated_words(utterance,len(audio))
        for row in mapped:
            index=word_index+row['recognized_index']
            row.update(word_index=index,script_agreement=index in matching)
        spans.extend(mapped);word_index+=len(words(utterance['raw_asr_text']))
    clean=runs(quality['accepted_intervals']);candidates=[]
    for lo,hi in clean:
        # Nonoverlapping 2–4 s context blocks, never tiny words or spliced audio.
        for start in range(lo,hi,4*RATE):
            end=min(start+4*RATE,hi)
            if end-start<2*RATE:continue
            included=[w for w in spans if start<=w['estimated_start_sample'] and w['estimated_end_sample']<=end]
            agreed=[w['word'] for w in included if w['script_agreement']]
            if len(agreed)<2:continue
            candidates.append(dict(start_sample=start,end_sample=end,words=[w['word'] for w in included],agreed=agreed))
    selected=[];covered=set();phrases=set()
    while candidates and len(selected)<MAX_BANK and quality.get('can_save'):
        candidates.sort(key=lambda c:(-len(set(c['agreed'])-covered),c['start_sample']))
        candidate=candidates.pop(0);key=tuple(candidate['agreed'])
        if key in phrases or not set(candidate['agreed'])-covered:continue
        phrases.add(key);covered.update(candidate['agreed'])
        start,end=candidate['start_sample'],candidate['end_sample']
        vector=np.asarray(models.embed(audio[start:end]),np.float32)
        from .people import vector_valid
        vector=vector_valid(vector)
        selected.append(dict(clip_id=f'{audio_hash[:16]}:{start}:{end}',span_id=f'samples-{start}-{end}',
            start_sample=start,end_sample=end,unique_duration_sec=(end-start)/RATE,
            context_words=candidate['words'],script_agreement_words=candidate['agreed'],
            vector=vector.tolist(),selection='single estimated speaker; all half-second quality windows admitted',
            content_confidence=None,phone_boundaries=None))
    retained=sum(x['unique_duration_sec'] for x in selected)
    alternate=None
    if selected:
        from .people import vector_valid
        alternate=vector_valid(np.mean(np.array([x['vector'] for x in selected],np.float32),axis=0)).tolist()
    document=dict(schema=SCHEMA,script_version=1,transcript_version=1,
        script=dict(text=offered,sha256=text_hash(offered),role='intended, not ground truth'),
        transcript=dict(raw_asr_text=actual,sha256=text_hash(actual),source='ordinary unbiased Sherpa greedy',utterances=utterances),
        source=dict(audio_sha256=audio_hash,total_samples=len(audio),sample_rate=RATE,route=deepcopy(route),
                    preprocessing_sha256=text_hash(route['preprocessing']),model_sha256=dict(model_hashes)),
        word_spans=spans,phone_boundaries=None,pronunciation_dictionary=None,
        agreement_operations=[dict(operation=tag,script_indices=[a,b],recognized_indices=[c,d]) for tag,a,b,c,d in ops],
        coverage=dict(script_words=len(intended),recognized_words=len(heard),matched_words=len(matching),
                      estimated_fraction=len(matching)/len(intended) if intended else None,
                      unknown_timing_words=len(heard)-len(spans),rejected_or_unknown_audio_sec=len(audio)/RATE-quality['usable_s']),
        quality=dict(base_usable_sec=quality['usable_s'],clipping=quality['clipping'],consistency=quality['consistency'],
                     source_gaps=quality['gaps'],admitted_sample_spans=clean,
                     admission='unchanged RMS/clipping/Pyannote speech>=0.6/overlap<=0.2; not a single-person guarantee'),
        bank=selected,alternate_vector=alternate,retained_unique_sec=retained,
        base_reference_unchanged=True,base_reference_retained_sec=quality['usable_s'],
        selection_state='available' if selected else 'unavailable_use_base',user_corrections=[],
        matched_content_score=None,matched_content_status=MATCHED_UNAVAILABLE,
        advisory_only=True,extra_embedding_calls=len(selected),extra_elapsed_sec=time.perf_counter()-started)
    # Reserve room for the immutable reference ID/hash added on Save.
    if stored_size(document)>MAX_BYTES-512:raise ValueError('Optional ScriptEvidence exceeds bounded storage; use original reference')
    return document


def preview(document):
    result=deepcopy(document)
    result.pop('alternate_vector',None)
    for row in result.get('bank',[]):row.pop('vector',None)
    for row in result.get('transcript',{}).get('utterances',[]):row.pop('token_timing',None)
    result['word_span_count']=len(result.get('word_spans',[]))
    result['word_spans']=result.get('word_spans',[])[:32]
    return result


def validate(document,reference,backend):
    from .people import vector_valid,route_compatible
    if stored_size(document)>MAX_BYTES or document.get('schema')!=SCHEMA:raise ValueError('Invalid ScriptEvidence size/schema')
    source=document['source']
    if (document.get('reference_id')!=reference['id'] or document.get('anchor_file_sha256')!=reference['sha256']
            or source['audio_sha256']!=reference['source_sha256'] or not route_compatible(source['route'],reference['route'])
            or source['model_sha256'].get('redimnet2_b2_fp32')!=backend):raise ValueError('ScriptEvidence binding mismatch')
    if (source['sample_rate']!=RATE or type(source['total_samples']) is not int or not 0<source['total_samples']<=180*RATE
            or source['preprocessing_sha256']!=text_hash(reference['route']['preprocessing'])):raise ValueError('Invalid source sample/preprocessing binding')
    if 'elapsed_s' in reference and source['total_samples']!=round(reference['elapsed_s']*RATE):raise ValueError('Source duration mismatch')
    if 'source_spans' in reference and document['quality']['admitted_sample_spans']!=runs(reference['source_spans']):raise ValueError('Original quality support mismatch')
    if document.get('phone_boundaries') is not None or document.get('advisory_only') is not True:raise ValueError('Unsupported phonetic/identity authority')
    for field in ('script','transcript'):
        text=document[field]['text' if field=='script' else 'raw_asr_text']
        if text_hash(text)!=document[field]['sha256']:raise ValueError('ScriptEvidence text hash mismatch')
    bank=document['bank'];seen=[]
    if len(bank)>MAX_BANK:raise ValueError('Oversized alternate bank')
    for row in bank:
        start,end=row['start_sample'],row['end_sample']
        if type(start) is not int or type(end) is not int or not 0<=start<end<=source['total_samples'] or not 2*RATE<=end-start<=4*RATE:raise ValueError('Invalid context span')
        if any(start<b and end>a for a,b in seen):raise ValueError('Repeated source support in alternate bank')
        if not any(a<=start<end<=b for a,b in document['quality']['admitted_sample_spans']):raise ValueError('Unsupported context quality')
        if row.get('phone_boundaries') is not None:raise ValueError('Unsupported phonetic context')
        if abs(row['unique_duration_sec']-(end-start)/RATE)>1e-6:raise ValueError('Incorrect context duration')
        seen.append((start,end));vector_valid(np.array(row['vector'],np.float32))
    if bool(bank)!=(document['alternate_vector'] is not None):raise ValueError('Alternate vector/bank mismatch')
    if bank:
        actual=vector_valid(np.array(document['alternate_vector'],np.float32))
        expected=vector_valid(np.mean([vector_valid(np.array(row['vector'],np.float32)) for row in bank],axis=0))
        if not np.allclose(actual,expected,atol=1e-5):raise ValueError('Alternate aggregate does not match contexts')
    if abs(document['retained_unique_sec']-sum((b-a)/RATE for a,b in seen))>1e-6:raise ValueError('Incorrect unique duration')
    return document
