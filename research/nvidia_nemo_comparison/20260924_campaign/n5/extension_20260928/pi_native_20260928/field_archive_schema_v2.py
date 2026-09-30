"""Prepublication metadata and caption contracts. See README_FIELD_ARCHIVE_V2.md."""
from datetime import datetime
import math
import re


def bounded_json(value):
    stack=[(value,0)];nodes=0
    while stack:
        item,depth=stack.pop();nodes+=1
        if depth>24 or nodes>100000:raise ValueError('Archive JSON complexity limit')
        if item is None or type(item) is bool:continue
        if type(item) is str:
            if len(item)>65536:raise ValueError('Archive string limit')
        elif type(item) is int:
            if abs(item)>2**63-1:raise ValueError('Archive integer limit')
        elif type(item) is float:
            if not math.isfinite(item):raise ValueError('Nonfinite archive value')
        elif type(item) is dict:
            if any(type(k) is not str for k in item):raise ValueError('Archive object key')
            stack.extend((v,depth+1) for pair in item.items() for v in pair)
        elif type(item) is list:stack.extend((v,depth+1) for v in item)
        else:raise ValueError('Archive JSON type')


def text(value,label,limit=4096,nullable=False):
    if nullable and value is None:return
    if type(value) is not str or len(value)>limit:raise ValueError(label+' must be bounded text')


def timestamp(value,label):
    text(value,label,64)
    try:parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:raise ValueError(label+' must be ISO timestamp') from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:raise ValueError(label+' must include timezone')


def conversation_metadata(m,identifier):
    try:
        if type(m) is not dict:raise ValueError('object required')
        bounded_json(m)
        if m.get('schema')!='just-peachy.conversation.v1' or m.get('id')!=identifier:raise ValueError('schema/id')
        if m.get('state')!='SAVED' or m.get('pinned') is not True:raise ValueError('saved/pinned required')
        text(m.get('title'),'title',160)
        if not m['title'].strip():raise ValueError('empty title')
        for k in ['created_utc','updated_utc']:timestamp(m.get(k),k)
        if type(m.get('audio_requested')) is not bool or not m['audio_requested']:raise ValueError('audio_requested must be true for this full-audio format')
        epochs=m.get('epochs')
        if type(epochs) is not list or not 1<=len(epochs)<=8 or any(type(e) is not str or not re.fullmatch('[0-9a-f]{32}',e) for e in epochs) or len(set(epochs))!=len(epochs):raise ValueError('epochs')
        for key in ['notes','corrections']:
            entries=m.get(key)
            if type(entries) is not list or len(entries)>200:raise ValueError(key+' list required')
            seen=set()
            for e in entries:
                if type(e) is not dict:raise ValueError(key+' entry object required')
                ident=e.get('id')
                if type(ident) is not str or not re.fullmatch('[0-9a-f]{32}',ident) or ident in seen:raise ValueError(key+' unique entry id required')
                seen.add(ident);timestamp(e.get('utc'),key+' utc')
                text(e.get('row_id'),key+' row_id',512,nullable=key=='notes')
                text(e.get('note') if key=='notes' else e.get('corrected_text'),key+' text')
                if e.get('reverts') is not None:text(e['reverts'],key+' reverts',32)
        if 'audio_reviews' in m:
            if type(m['audio_reviews']) is not list or m['audio_reviews']:
                raise ValueError('Audio review imports are not supported by this version')
        return m
    except (ValueError,TypeError,KeyError) as exc:raise ValueError('Conversation metadata: '+str(exc)) from None


def caption_row(row,samples):
    bounded_json(row)
    if type(row) is not dict:raise ValueError('Caption row object required')
    if type(row.get('utterance_id')) not in (int,str):raise ValueError('Caption utterance_id required')
    text(row.get('caption_key'),'caption_key',512)
    for k in ['text','display_text','archived_provisional_display_text','archived_final_formatted_text']:
        if k in row or k=='text':text(row.get(k),k,65536,nullable=k!='text')
    if type(row.get('final')) is not bool:raise ValueError('Caption final boolean required')
    for k in ['source_start_sample','source_end_sample']:
        if type(row.get(k)) is not int:raise ValueError('Caption sample index type')
    if not 0<=row['source_start_sample']<=row['source_end_sample']<=samples:raise ValueError('Caption sample interval')
    parts=row.get('segments') or [row]
    if type(parts) is not list or len(parts)>1024 or any(type(p) is not dict for p in parts):raise ValueError('Caption segments must be bounded objects')
    for part in parts:
        for k in ['segment_id','raw_text','anonymous_label','known_profile_id','naming_state']:
            if k in part:text(part[k],k,65536 if k=='raw_text' else 512,nullable=k=='known_profile_id')
        if 'token_range' in part:
            pair=part['token_range']
            if type(pair) is not list or len(pair)!=2 or any(type(v) is not int for v in pair) or not 0<=pair[0]<=pair[1]<=len(row['text'].split()):raise ValueError('Caption token range')
        for k in ['source_start_sec','source_end_sec']:
            value=part.get(k,row.get(k))
            if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=samples/16000:raise ValueError('Caption source seconds')
        for k in ['span_ids','token_ids','word_spans','speaker_history']:
            if k in part and (type(part[k]) is not list or len(part[k])>4096):raise ValueError('Caption '+k+' list')
    aid=row.get('text_assistance')
    if aid is not None:
        if type(aid) is not dict:raise ValueError('Text assistance object')
        for k in ['input_text','corrected_text']:
            if k in aid:text(aid[k],k,65536,nullable=k=='corrected_text')
        applied=aid.get('applied',[])
        if type(applied) is not list or any(type(x) is not dict for x in applied):raise ValueError('Text assistance applied entries')


def projected_rows(rows):
    bounded_json(rows)
    if type(rows) is not list or len(rows)>4096:raise ValueError('Projected row limit')
    seen=set()
    for row in rows:
        if type(row) is not dict:raise ValueError('Projected row object')
        ident=row.get('id');text(ident,'Projected id',512)
        if ident in seen:raise ValueError('Duplicate projected caption ID')
        seen.add(ident)
        for k in ['label','raw_asr_text','provisional_display_text','final_punctuated_display_text']:
            text(row.get(k),'Projected '+k,65536,nullable=k=='final_punctuated_display_text')
    return dict(display_rows=len(rows),unique_ids=len(seen))
