"""Single-file atomic promotion/undo; base NPY files untouched. See README_ADAPTATION.md."""
from copy import deepcopy
import hashlib,math,time,uuid
import numpy as np
from .paths import atomic_json,read_json
from .reference_adaptation import BaseAnchors,FEATURE,MAX_STORED,base_version,domain,normalized

def validate_bank(row):
    entries=row.get('environment_bank',[]);history=row.get('enrichment_history',[])
    if not isinstance(entries,list) or len(entries)>MAX_STORED or not isinstance(history,list) or len(history)>32:raise ValueError('Unbounded environment bank/history')
    seen=set();windows=set();transactions={}
    for t in history:
        if str(uuid.UUID(t['id']))!=t['id'] or t['id'] in transactions or t.get('status') not in ('active','undone'):raise ValueError('Invalid enrichment transaction')
        if not isinstance(t.get('candidate_ids'),list) or not 1<=len(t['candidate_ids'])<=MAX_STORED or len(set(t['candidate_ids']))!=len(t['candidate_ids']):raise ValueError('Invalid transaction inventory')
        transactions[t['id']]=t
    for c in entries:
        identifier=c['id'];str(uuid.UUID(identifier))
        if identifier in seen or c['waveform_sha256'] in windows:raise ValueError('Duplicate enriched reference')
        seen.add(identifier);windows.add(c['waveform_sha256'])
        if c['person_id']!=row['id'] or c.get('confirmation',{}).get('kind')!='explicit_user' or c['confirmation'].get('quality_attested') is not True:raise ValueError('Unconfirmed enriched reference')
        t=transactions.get(c.get('transaction_id'))
        if not t or t['status']!='active' or identifier not in t['candidate_ids']:raise ValueError('Missing active transaction')
        for key in ('waveform_sha256','window_sha256','vector_sha256','base_version','gallery_version'):
            if not isinstance(c.get(key),str) or len(c[key])!=64 or any(s not in '0123456789abcdef' for s in c[key]):raise ValueError('Invalid enrichment hash')
        v=np.asarray(c['vector'],np.float32);nv=normalized(v)
        if not np.allclose(v,nv,atol=1e-5,rtol=0) or hashlib.sha256(v.astype('<f4').tobytes()).hexdigest()!=c['vector_sha256']:raise ValueError('Enrichment vector integrity failure')
        if c['domain']!=domain(c['domain']):raise ValueError('Incomplete enrichment domain')
        from .people import PersonalStore
        PersonalStore._route(c['domain'])
        a,b=c['start_sample'],c['end_sample']
        if type(a) is not int or type(b) is not int or not 0<=a<b or not 16000<=b-a<=64000:raise ValueError('Invalid enrichment source span')
        sa,sb=c['source_start_sample'],c['source_end_sample']
        if (not isinstance(c['source_id'],str) or not 1<=len(c['source_id'])<=80 or type(sa) is not int or type(sb) is not int
            or not 0<=sa<sb or sb-sa!=b-a):raise ValueError('Invalid enrichment source identity/support')
        usable=0.;previous=a/16000
        for left,right in c['clean_intervals']:
            if not all(type(v) in (int,float) and math.isfinite(v) for v in (left,right)) or not previous<=left<right<=b/16000:raise ValueError('Invalid enrichment clean support')
            usable+=right-left;previous=right
        if abs(usable-c['usable_sec'])>1e-6 or usable/((b-a)/16000)<.8:raise ValueError('Invalid enrichment usable duration')
        q=c['quality']
        if q['overlap'] is not False or not 0<=q['clipping']<=.005 or not .002<=q['rms']<=1. or abs(q['clean_fraction']-usable/((b-a)/16000))>1e-6:raise ValueError('Invalid enrichment quality')
        if any(c['source_id']==p['source_id'] and max(sa,p['source_start_sample'])<min(sb,p['source_end_sample']) for p in entries if p['id']!=identifier):raise ValueError('Overlapping enriched references')
    active={i for t in history if t['status']=='active' for i in t['candidate_ids']}
    if active!=seen:raise ValueError('Enrichment transaction/reference mismatch')

class AdaptationStore:
    def promote_candidates(self,bank,identifiers,person_id,*,consent=False):
        if consent is not True:raise ValueError('Explicit permanent promotion approval required')
        with bank.lock,self._lock:
            if bank.frozen:raise ValueError('Frozen candidates cannot be promoted')
            identifiers=list(identifiers)
            if not identifiers or len(set(identifiers))!=len(identifiers):raise ValueError('Select unique confirmed candidates')
            selected=[deepcopy(c) for c in bank.candidates if c['id'] in identifiers]
            if len(selected)!=len(identifiers) or any(c['person_id']!=person_id or not c['confirmation'] for c in selected):raise ValueError('Select confirmed references for one person')
            fresh=BaseAnchors(self.gallery(bank.base.route))
            if fresh.version!=bank.base.version:bank.freeze('enrollment_base_changed');raise ValueError('Original enrollment changed; recollect in a fresh session')
            if any(not fresh.agrees(fresh.scores(c['vector']),person_id) for c in selected):raise ValueError('Original voice comparison no longer agrees')
            path=self._path(person_id)/'person.json';row=self._validate(read_json(path),path.parent)
            entries=row.setdefault('environment_bank',[])
            if len(entries)+len(selected)>MAX_STORED:raise ValueError('Personal environment bank cap is six; Undo earlier additions first')
            history=row.setdefault('enrichment_history',[])
            if len(history)>=32:
                old=next((t for t in history if t['status']=='undone'),None)
                if old is None:raise ValueError('Transaction history is full')
                history.remove(old)
            transaction=dict(id=str(uuid.uuid4()),candidate_ids=identifiers,status='active',created_unix=time.time())
            for c in selected:c['transaction_id']=transaction['id']
            entries.extend(selected);history.append(transaction)
            self._validate(row,path.parent)
            # Guard older readers before publishing a new data feature. A failed
            # write may leave a conservative capability marker, never half a bank.
            self._require_script_feature(FEATURE);atomic_json(path,row);self._invalidate()
            bank.candidates=[c for c in bank.candidates if c['id'] not in identifiers]
            bank.persisted.extend(selected)
            return deepcopy(transaction)
    def undo_enrichment(self,person_id,*,consent=False):
        if consent is not True:raise ValueError('Explicit Undo confirmation required')
        with self._lock:
            path=self._path(person_id)/'person.json';row=self._validate(read_json(path),path.parent)
            t=next((t for t in reversed(row.get('enrichment_history',[])) if t['status']=='active'),None)
            if t is None:raise ValueError('No active enrichment transaction to undo')
            row['environment_bank']=[c for c in row['environment_bank'] if c['transaction_id']!=t['id']]
            t.update(status='undone',undone_unix=time.time());self._validate(row,path.parent)
            atomic_json(path,row);self._invalidate();return deepcopy(t)
