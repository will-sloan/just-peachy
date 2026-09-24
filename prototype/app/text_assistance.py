"""Bounded, optional text suggestions; never audio or identity evidence.

Original compact vocabulary, no third-party dictionary. See README_TEXT_ASSISTANCE.md.
"""
from collections import OrderedDict
from copy import deepcopy
import hashlib
import re
import threading
import time
import uuid
from .paths import read_json, atomic_json

WORDS = ('captions','transcript','microphone','enrollment','speaker','prototype',
         'vocabulary','spelling','paragraph','conversation','spatial','calibration',
         'headphones','recording','playback','direction','computer','settings',
         'reference','software','hardware','simulation','diarization','punctuation')
TOKEN = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*",re.UNICODE)
PROTECTED = set(('i me my mine we us our ours you your yours he him his she her hers they them their theirs '
                 'it its no not never none neither nor without cannot cant dont wont isnt arent wasnt werent '
                 "don't won't can't isn't aren't wasn't weren't couldn't wouldn't shouldn't "
                 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen '
                 'sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety '
                 'hundred thousand million billion trillion percent milligram milligrams '
                 'dose dosage medicine medication pill insulin allergy allergic emergency stop danger safe unsafe '
                 'fire pain chest breathe breathing suicide kill password pin bank account money dollars').split())
PROTECTED.update(root+suffix for root in ('i','we','you','he','she','they','it','that','there')
                 for suffix in ("'m","'re","'ve","'ll","'d","'s"))
PROTECTED.update(root+suffix for root in ('is','are','was','were','do','does','did','has','have','had','could','would','should','must','need','ai')
                 for suffix in ("n't",'nt'))
BIAS_UNAVAILABLE = ('Unavailable: installed Sherpa 1.13.4 exposes hotwords, but the qualified '
                    'Giga ASR assets have no matching BPE vocabulary. Punctuation BPE is a different '
                    'tokenizer. Greedy decoding remains active; no hotword file is used.')


def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()


def tokens(text):return [m.group().casefold().replace('’',"'") for m in TOKEN.finditer(text)]


def phrase(value,optional=False):
    if not isinstance(value,str):raise ValueError('Vocabulary must be text')
    value=value.strip()
    if optional and not value:return ''
    if len(value)>80 or not 1<=len(value.split())<=4 or ' '.join(TOKEN.findall(value))!=value:
        raise ValueError('Use 1–4 words (letters/apostrophes), up to 80 characters')
    return value


def one_edit(a,b):
    """One character edit only; an orthographic heuristic, not ASR confidence."""
    if a==b or abs(len(a)-len(b))>1:return False
    if len(a)==len(b):return sum(x!=y for x,y in zip(a,b))==1
    if len(a)>len(b):a,b=b,a
    i=0
    while i<len(a) and a[i]==b[i]:i+=1
    return a[i:]==b[i+1:]


class TextAssistance:
    def __init__(self,path):
        self.path=path;self.lock=threading.RLock();self.cache=OrderedDict();self.error=None
        self.config={'version':1,'enabled':False,'automatic':False,'revision':0,'entries':[]}
        if path.exists():
            try:
                if path.stat().st_size>65536:raise ValueError('Oversized vocabulary file')
                value=read_json(path)
                if value.get('version')!=1:raise ValueError('Invalid vocabulary file')
                self._validate(value);self.config=value
            except Exception as exc:
                # Optional preferences cannot prevent baseline captioning. Keep
                # invalid bytes intact for explicit repair, not silent overwrite.
                self.error='Vocabulary unavailable; original file preserved: '+str(exc)

    def _validate(self,value):
        if type(value['enabled']) is not bool or type(value['automatic']) is not bool:raise ValueError('Invalid assistance switch')
        if len(value['entries'])>64:raise ValueError('Personal vocabulary is limited to 64 entries')
        ids=set()
        for item in value['entries']:
            if item['id'] in ids:raise ValueError('Duplicate vocabulary ID')
            ids.add(item['id']);phrase(item['preferred']);phrase(item['alias'],True);phrase(item['context'],True)
            if item['kind'] not in ('name','context','spelling'):raise ValueError('Unknown vocabulary kind')
            if item['alias'] and len(item['alias'].split())!=len(item['preferred'].split()):raise ValueError('Mappings must keep the same word count')
            if type(item['approved_auto']) is not bool:raise ValueError('Invalid rule approval')
            if item['approved_auto'] and (not item['alias'] or not item['context']):raise ValueError('Automatic rules need an exact alias and contextual phrase')
            if item['approved_auto'] and not (set(tokens(item['context']))-set(tokens(item['alias'])+tokens(item['preferred']))-PROTECTED):
                raise ValueError('Automatic rules need independent context beyond the name/alias')

    def change(self,action,values,people):
        with self.lock:
            if self.error:raise ValueError(self.error)
            value=deepcopy(self.config)
            if action=='switch':
                for key in ('enabled','automatic'):
                    if key in values:value[key]=values[key]
            elif action=='add':
                if values.get('approved') is not True:raise ValueError('Approve the vocabulary entry explicitly')
                pid=values.get('person_id');person=next((p for p in people if p['id']==pid),None)
                if pid and person is None:raise ValueError('Person no longer exists')
                item={'id':uuid.uuid4().hex,'preferred':phrase(values['preferred']),
                      'alias':phrase(values.get('alias',''),True),'context':phrase(values.get('context',''),True),
                      'kind':values.get('kind','spelling'),'person_id':pid,
                      'approved_person_name':person['name'] if person else None,
                      'approved_auto':values.get('approved_auto',False)}
                value['entries'].append(item)
            elif action=='delete':value['entries']=[x for x in value['entries'] if x['id']!=values['id']]
            else:raise ValueError('Unknown vocabulary action')
            value['revision']+=1;self._validate(value);atomic_json(self.path,value)
            self.config=value;self.cache.clear()

    def snapshot(self,people):
        with self.lock:value=deepcopy(self.config)
        names={p['id']:p['name'] for p in people}
        for item in value['entries']:
            item['active']=not item['person_id'] or names.get(item['person_id'])==item['approved_person_name']
            item['inactive_reason']=None if item['active'] else 'Linked person renamed/deleted; remove and approve a new entry'
        return {**value,'error':self.error,'bias_available':False,'bias_reason':BIAS_UNAVAILABLE,'dictionary_kind':'original compact vocabulary; no frequency corpus'}

    def analyze(self,text,people):
        cfg=self.snapshot(people)
        key=(text,cfg['revision'],tuple((p['id'],p['name']) for p in people))
        with self.lock:
            if key in self.cache:return deepcopy(self.cache[key])
        started=time.perf_counter()
        result={'input_text':text,'input_sha256':digest(text),'corrected_text':None,'suggestions':[],
                'applied':[],'config_revision':cfg['revision'],'enabled':cfg['enabled'],
                'provenance':'text heuristic only; not acoustic/identity confidence','status':'off'}
        if cfg['enabled'] and len(text)<=4000 and len(text.split())<=128:
            result['status']='review';words=tokens(text)
            unsafe=bool(set(words)&PROTECTED) or any(c.isdigit() for c in text) or any(x in text for x in ('@','://','`'))
            matches=[];entries=[e for e in cfg['entries'] if e['active']]
            for entry in entries:
                if not entry['alias']:continue
                context=entry['context']
                if context and not re.search(r'(?<!\w)'+re.escape(context)+r'(?!\w)',text,re.I):continue
                for match in re.finditer(r'(?<![\w’\'\-])'+re.escape(entry['alias'])+r'(?![\w’\'\-])',text,re.I):
                    if match.group()==entry['preferred']:continue
                    other_name=any(p['id']!=entry['person_id'] and re.search(r'(?<!\w)'+re.escape(entry['alias'])+r'(?!\w)',p['name'],re.I) for p in people)
                    automatic=bool(cfg['automatic'] and entry['approved_auto'] and not unsafe and not other_name
                                   and not set(tokens(entry['preferred'])+tokens(entry['alias']))&PROTECTED)
                    matches.append({'start':match.start(),'end':match.end(),'before':match.group(),'after':entry['preferred'],
                                    'rule_id':entry['id'],'context':context,'automatic':automatic,
                                    'reason':'explicit contextual mapping' if automatic else 'review; ambiguity/protection or automatic approval absent'})
            # Conflicting/overlapping rules never select a winner automatically.
            for candidate in matches:
                if any(other is not candidate and candidate['start']<other['end'] and other['start']<candidate['end'] for other in matches):
                    candidate.update(automatic=False,reason='review; conflicting rules')
            result['suggestions']=matches[:16]
            admitted=[m for m in result['suggestions'] if m['automatic']]
            corrected=text
            for item in reversed(sorted(admitted,key=lambda m:m['start'])):
                corrected=corrected[:item['start']]+item['after']+corrected[item['end']:]
            if admitted:result.update(corrected_text=corrected,applied=admitted,status='assisted')
            lexicon=set(WORDS)|{w for e in entries if e['kind']!='name' for w in tokens(e['preferred'])}
            known=lexicon|{w for p in people for w in tokens(p['name'])}|{w for e in entries for w in tokens(e['preferred'])}|PROTECTED
            for match in TOKEN.finditer(text):
                word=match.group().casefold()
                if len(result['suggestions'])>=16:break
                if word in known or not 5<=len(word)<=24 or any(m['start']<=match.start()<m['end'] for m in matches):continue
                options=sorted(w for w in lexicon if one_edit(word,w))[:3]
                for alternative in options:
                    if len(result['suggestions'])>=16:break
                    result['suggestions'].append({'start':match.start(),'end':match.end(),'before':match.group(),'after':alternative,
                                                 'automatic':False,'reason':'possible spelling; compact vocabulary, not proof of an error'})
        elif cfg['enabled']:result['status']='text_limit; unchanged'
        result['compute_ms']=(time.perf_counter()-started)*1000
        with self.lock:
            self.cache[key]=deepcopy(result)
            while len(self.cache)>512:self.cache.popitem(last=False)
        return result


def corrected_partition(base,corrected,token_range):
    """Same-count substitution only: preserve speaker segment token ownership."""
    if corrected is None:return None
    a,b=token_range;words=list(re.finditer(r'\S+',corrected))
    if len(words)!=len(base.split()) or not 0<=a<=b<=len(words):return None
    start=words[a].start() if a<len(words) else len(corrected)
    end=words[b].start() if b<len(words) else len(corrected)
    return corrected[start:end]
