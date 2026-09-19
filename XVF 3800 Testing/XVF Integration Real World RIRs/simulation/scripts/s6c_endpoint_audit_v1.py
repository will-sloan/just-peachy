"""Future actual endpoint/log/token audit; README_S6C_ENDPOINT_AUDIT_V1.md."""
from __future__ import annotations
import argparse,ast,gzip,hashlib,json,math,os,string,time
from collections import Counter,defaultdict
from pathlib import Path

SIM=Path(__file__).resolve().parents[1];REPORT=SIM/'reports/S6C/20260910T123540Z'
PAYLOAD=Path('G:/Just_Peachy_S6C/20260910T123540Z')
EPOCH_SHA='e7c6e91ed9ceaecc587789d96e24ca5ab0f458711a1e604adff71856f3fad934'
SOURCE_EPOCHS={'epoch2':'1f7f0e10186eb1187d05d9be258372d6dfbe39ec3741c2ce2976a2ca3d005cdb',
              'epoch4':'720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945',
              'epoch5':'676ead81afe85b5557494bd851e67f34799106a45976e8f7fa6e2e5900989cbc','epoch6':EPOCH_SHA}
BANK_SHA='69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18'
PIDS=('C065','C079','C195','C196')
PAIRS=(('C065','C195'),('C079','C196'),('C065','C079'),('C195','C196'))

def require(condition,message):
    if not condition:raise ValueError(message)

def canonical(value):return json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def binding(path,raw=None):
    p=Path(path).resolve();raw=p.read_bytes() if raw is None else raw
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def raw_read(b):
    raw=Path(b['path']).read_bytes();actual=binding(b['path'],raw)
    require(actual['sha256']==b['sha256'] and ('bytes' not in b or len(raw)==b['bytes']),'Changed bound bytes: '+b['path'])
    return raw
def read(b):
    raw=raw_read(b)
    if str(b['path']).endswith('.gz'):raw=gzip.decompress(raw)
    return json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON: '+x)))
def save(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write((json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode());f.flush();os.fsync(f.fileno())
    return binding(p)
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def route(v):return (v.get('candidate_id',v.get('profile_id')),v['case_id'],v.get('stream',v.get('asr_tap')),v['identity_tap'])

def text_api():
    # Exact inherited normalization/reference layout, without importing scoring
    # packages or any metric/model implementation.
    names=[('s4_h2_analysis.py','0b5d8a227ca87c4dcee48db8118de35444fb32217291bf022feb458f0982d1a0',{'normalize'}),
           ('s6a_text_metrics.py','c7614c33c04cba1f47660c10235198c8cd697963eb42b12a3656b503a8c884cd',{'reference_layout'})]
    ns=dict(string=string,defaultdict=defaultdict);bindings=[]
    for name,sha,wanted in names:
        p=Path(__file__).with_name(name);raw=raw_read(dict(path=str(p),sha256=sha));tree=ast.parse(raw)
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
        require({n.name for n in nodes}==wanted,'Inherited text function missing')
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),ns);bindings.append(binding(p,raw))
    return ns['normalize'],ns['reference_layout'],bindings

def positional_edits(reference,hypothesis):
    """Deterministic unit-cost token alignment; no acoustic timing inference."""
    n,m=len(reference),len(hypothesis)
    require((n+1)*(m+1)<=2_000_000,'Bounded scene token alignment required')
    costs=[[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1):costs[i][0]=i
    for j in range(m+1):costs[0][j]=j
    for i in range(1,n+1):
        for j in range(1,m+1):costs[i][j]=min(costs[i-1][j-1]+(reference[i-1]!=hypothesis[j-1]),costs[i-1][j]+1,costs[i][j-1]+1)
    ops=[];i=n;j=m
    # Backtrace tie priority: equal, substitution, deletion, insertion.
    while i or j:
        if i and j and reference[i-1]==hypothesis[j-1] and costs[i][j]==costs[i-1][j-1]:
            ops.append(dict(op='equal',reference_index=i-1,hypothesis_index=j-1));i-=1;j-=1
        elif i and j and costs[i][j]==costs[i-1][j-1]+1:
            ops.append(dict(op='substitution',reference_index=i-1,hypothesis_index=j-1));i-=1;j-=1
        elif i and costs[i][j]==costs[i-1][j]+1:
            ops.append(dict(op='deletion',reference_index=i-1,hypothesis_index=None));i-=1
        else:
            ops.append(dict(op='insertion',reference_index=None,hypothesis_index=j-1,reference_boundary=i));j-=1
    ops.reverse();counts=Counter(x['op'] for x in ops)
    indexed={x['reference_index']:x for x in ops if x['reference_index'] is not None}
    return dict(reference_words=n,hypothesis_words=m,errors=costs[n][m],substitutions=counts['substitution'],deletions=counts['deletion'],insertions=counts['insertion'],
        first_reference_token_operation=indexed[0]['op'] if n else None,last_reference_token_operation=indexed[n-1]['op'] if n else None,
        deleted_reference_positions=[x['reference_index'] for x in ops if x['op']=='deletion'],
        substituted_reference_positions=[x['reference_index'] for x in ops if x['op']=='substitution'],
        insertion_hypothesis_positions=[x['hypothesis_index'] for x in ops if x['op']=='insertion'],
        insertion_reference_boundaries=[x['reference_boundary'] for x in ops if x['op']=='insertion'],
        tie_rule='Unit edit costs, backtrace equal/substitution/deletion/insertion; repeated words can admit other optimal alignments. No token time or phonetic clipping proof.')

class NativeLog:
    def __init__(self,duration):
        self.duration=duration;self.counts=Counter();self.reset_types=Counter();self.reasons=Counter();self.costs=defaultdict(lambda:dict(sum_sec=0.,observed_events=0))
        self.dispatch=[];self.reset=[];self.tail=[];self.drain=[];self.finals=[];self.final_ids=set();self.advisor_observed=0;self.proposals=0;self.accepted=0
    def consume(self,event):
        k=event['event_type'];p=event['payload'];require(isinstance(p,dict),'Object event payload required');self.counts[k]+=1
        for field in ('compute_ms','model_api_elapsed_ms','full_dispatch_elapsed_ms','decode_compute_ms','advisor_compute_ms','gate_compute_ms','scheduler_dispatch_ms','postprocess_compute_ms'):
            if field in p and p[field] is not None:
                require(finite(p[field]) and p[field]>=0,'Finite nonnegative logged cost required')
                d=self.costs[k+'/'+field];d['sum_sec']+=p[field]/1000;d['observed_events']+=1
        if k=='research_asr_dispatch':
            require(all(type(p[x]) is bool for x in ('native_endpoint','advisory_endpoint','reset_requested')),'Exact endpoint flags required')
            require(p['reset_requested']==(p['native_endpoint'] or p['advisory_endpoint']),'Endpoint OR invariant differs')
            self.dispatch.append({x:p[x] for x in ('source_start_sec','source_end_sec','native_endpoint','advisory_endpoint','reset_requested')})
        elif k=='research_asr_reset':
            a,b=p['native_endpoint'],p['advisory_endpoint'];require(type(a) is bool and type(b) is bool and (a or b),'Reset without source flag')
            kind='coincident_one_reset' if a and b else 'native_only' if a else 'advice_only';self.reset_types[kind]+=1
            self.reset.append(dict(source_end_sec=event['source_time_sec'],native_endpoint=a,advisory_endpoint=b))
        elif k=='research_asr_full_dispatch_cost':
            a=p.get('advisor')
            if a is not None:
                require(type(a['proposal']) is bool and type(a['accepted']) is bool,'Exact advisor status required')
                self.advisor_observed+=1;self.proposals+=a['proposal'];self.accepted+=a['accepted'];self.reasons[a['reason']]+=1
        elif k=='research_asr_tail_dispatch':self.tail.append(p)
        elif k=='research_asr_drain':self.drain.append(p)
        elif k=='research_asr_observation' and p['final']:
            require(p['utterance_id'] not in self.final_ids,'Duplicate raw finalized utterance');self.final_ids.add(p['utterance_id'])
            self.finals.append({x:p[x] for x in ('utterance_id','text','source_start_sec','source_end_sec','available_at_sec')})
    def finish(self,receipt,summary):
        require(dict(self.counts)==receipt['actual_counts'],'Exact full event counts differ from native receipt')
        require(summary['state']=='COMPLETED','Native summary incomplete')
        tel=summary['telemetry'];require(abs(tel['asr_cursor_sec']-self.duration)<1e-8 and tel['asr_lag_sec']==0,'Full ASR cursor required')
        require(len(self.drain)==1 and self.drain[0]['padding_is_observed_audio'] is False and abs(self.drain[0]['source_end_sec']-self.duration)<1e-8,'Exact nonobserved EOF drain required')
        require(len(self.tail)<=1 and self.counts['research_asr_full_dispatch_cost']==len(self.dispatch),'Full cost/dispatch and tail counts differ')
        for tail in self.tail:
            require(type(tail['samples']) is int and tail['samples']>=0 and tail['samples']==round((tail['source_end_sec']-tail['source_start_sec'])*16000),'Tail sample count must equal its actual source span')
        expected=[dict(source_end_sec=p['source_end_sec'],native_endpoint=p['native_endpoint'],advisory_endpoint=p['advisory_endpoint']) for p in self.dispatch if p['reset_requested']]
        require(self.reset==expected,'Every requested endpoint must create exactly one matching reset event')
        spans=[(x['source_start_sec'],x['source_end_sec']) for x in self.dispatch]+[(x['source_start_sec'],x['source_end_sec']) for x in self.tail]
        require(bool(spans) and abs(spans[0][0])<1e-8 and abs(spans[-1][1]-self.duration)<1e-8,'ASR span coverage mismatch')
        require(all(abs(a[1]-b[0])<1e-8 for a,b in zip(spans,spans[1:])),'ASR gap or duplicate source span')
        require(all(finite(a) and finite(b) and 0<=a<b<=self.duration+1e-8 for a,b in spans),'Invalid ASR source span')
        return dict(event_counts=dict(self.counts),reset_types=dict(self.reset_types),actual_resets=len(self.reset),
            advisor_status_observed_dispatches=self.advisor_observed,advisor_proposals=self.proposals,accepted_advice=self.accepted,advisor_reasons=dict(self.reasons),
            accepted_advice_equals_dispatch_flag=self.accepted==sum(x['advisory_endpoint'] for x in self.dispatch),
            raw_final_observations=self.finals,raw_nonempty_final_count=sum(bool(x['text']) for x in self.finals),
            empty_final_at_reset_count=None,empty_final_scope='Runtime omits empty raw final transcript events; empty reset outcome cannot be inferred from a missing event.',
            source_spans_complete=True,source_samples=round(self.duration*16000),tail_samples=sum(x['samples'] for x in self.tail),
            synthetic_drain_padding_sec=self.drain[0]['synthetic_right_padding_sec'],costs=dict(self.costs),
            queues=dict(scheduler_observed_max_pending=tel.get('scheduler',{}).get('max_pending_events'),asr_final_lag_sec=tel.get('asr_lag_sec'),speaker_final_lag_sec=tel.get('speaker_lag_sec'),continuous_journal_peak=None),
            speaker_unanalyzed_short_tail_sec=tel.get('speaker_unanalyzed_short_tail_sec'))

def scan_log(b,duration):
    require(Path(b['path']).resolve().is_relative_to(PAYLOAD.resolve()),'Native event source outside S6C payload')
    acc=NativeLog(duration);h=hashlib.sha256();size=0
    with Path(b['path']).open('rb') as f:
        for raw in f:
            require(len(raw)<=16*2**20,'Bounded native event line required');h.update(raw);size+=len(raw)
            if raw.strip():acc.consume(json.loads(raw))
    require(size==b['bytes'] and h.hexdigest()==b['sha256'],'Changed exact native event stream')
    return acc

def authorities():
    eb=binding(REPORT/'EPOCH6_EXECUTION_MANIFEST.json');require(eb['sha256']==EPOCH_SHA,'Exact epoch6 required');epoch=read(eb)
    registry=read(epoch['effective_profile_registry']);amendment=read(registry['endpoint_registration']);panel=read(epoch['panel'])
    bb=binding(SIM/'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json');require(bb['sha256']==BANK_SHA,'Canonical bank changed')
    return eb,epoch,registry,amendment,panel,bb

def admitted_source_epochs(target):
    bindings=[];digests=set()
    def inventory(spec):
        root=Path(spec['root'])/'app'
        return {str(Path(b['path']).relative_to(root)):b['sha256'] for b in spec['execution_files'] if root in Path(b['path']).parents}
    target_inventory=inventory(target);require(len(target_inventory)==29,'Exact original APP inventory required')
    for name,sha in SOURCE_EPOCHS.items():
        b=binding(REPORT/(name.upper()+'_EXECUTION_MANIFEST.json'));require(b['sha256']==sha,'Pinned native source epoch changed');source=read(b)
        require(source['execution_digest']==digest({k:source[k] for k in ('execution_files','assets','versions','state_policy')}),'Source epoch digest differs')
        require(inventory(source)==target_inventory,'Source APP inventory differs')
        for field in ('assets','versions','python','input_index','scene_manifest','state_policy'):require(source[field]==target[field],'Source epoch authority differs: '+field)
        for module in ('s6c_execution.py','s6c_common.py'):
            a=next(x for x in target['execution_files'] if Path(x['path']).name==module);z=next(x for x in source['execution_files'] if Path(x['path']).name==module)
            require(a['sha256']==z['sha256'] and a['bytes']==z['bytes'],'Whole native worker/common equality required')
            raw_read(z)
        bindings.append(b);digests.add(source['execution_digest'])
    return bindings,digests

def source_check(pred,native,key,profile,epoch,source_digests,canonical_input):
    require(pred['status']=='COMPLETE' and route(pred)==key and digest(pred['identity'])==pred['prediction_key'],'Prediction identity/status mismatch')
    require(pred['identity']['profile']==profile['profile'],'Registered predictor profile differs')
    require(pred['identity']['cue_condition']==profile['cue_condition'],'Registered prediction cue condition differs')
    require(canonical_input['case_id']==key[1] and canonical_input['stream']==key[2],'Cue input case/tap differs')
    expected_cue=canonical_input['telemetry'] if profile['cue_condition']=='REAL_ALIGNED_CUES' else None
    require(profile['cue_condition'] in ('CUES_OFF','REAL_ALIGNED_CUES') and pred['identity']['telemetry']==expected_cue,'Prediction telemetry differs from exact registered canonical case route')
    require(native['status']=='COMPLETE' and digest(native['identity'])==native['job_key'],'Native identity/status mismatch')
    require((native['case_id'],native['asr_tap'],native['identity_tap'])==key[1:] and native['audio_duration_sec']==pred['duration_sec'],'Native source route/duration differs')
    ni=native['identity'];require(ni['gallery'] is None and pred['identity']['gallery'] is None,'No naming gallery in endpoint factorial')
    require(ni['execution_digest'] in source_digests,'Unadmitted actual native source epoch')
    if key[0] in ('C195','C196'):
        require(native['candidate_id']==key[0] and ni['execution_digest']==epoch['execution_digest'],'Fresh exact child epoch/profile native source required')
        require(ni['profile']==profile['profile'] and ni['telemetry']==pred['identity']['telemetry'] and ni['cue_condition']=='REAL_ALIGNED_CUES','Child full-profile/cue dependency mismatch')
    else:
        require(ni['profile']['xvf']['mode'] in ('none','tracking_only'),'Parent source cannot contain endpoint advice')
        require(ni['profile']['embedding']['cadence_policy']!='uncertainty' and not ni['profile']['embedding']['cadence_cues_enabled'],'Parent cached source has policy-driven neural admission')
        for k in ('input','asr','segmentation','embedding','punctuation','runtime'):require(ni['profile'][k]==profile['profile'][k],'Parent actual neural graph differs: '+k)

def prepare(args):
    require(args.name and args.name.replace('_','').isalnum(),'Simple new audit namespace required')
    output=REPORT/'endpoint_audit'/args.name;require(not output.exists(),'Preserve existing audit')
    eb,epoch,registry,amendment,panel,bb=authorities();profiles={(p['candidate_id'],p['asr_tap'],p['identity_tap']):p for p in epoch['profiles']}
    source_epoch_bindings,source_digests=admitted_source_epochs(epoch)
    inputs={(x['case_id'],x['stream']):x for x in read(epoch['input_index'])['rows']}
    expected={(pid,c,t,t) for pid in PIDS for c in panel['case_ids'] for t in ('O0','O1')};selected={};indices=[]
    for path,sha in args.index:
        b=binding(path);require(b['sha256']==sha,'Caller-pinned prediction index changed');idx=read(b)
        require(idx['status']=='COMPLETE' and idx['completed']==idx['requested']==len(idx['rows']),'Completed explicit prediction index required');indices.append(b)
        for row in idx['rows']:
            key=route(row)
            if key not in expected:continue
            require(row['status'] in ('COMPLETE','COMPLETE_REUSED'),'Selected prediction incomplete')
            require(key not in selected or selected[key]['prediction']==row['result'],'Ambiguous duplicate selected prediction; supply one exact source')
            if key in selected:continue
            pred=read(row['result']);native_b=pred['identity']['source'];native=read(native_b)
            p=profiles[key[0],key[2],key[3]];source_check(pred,native,key,p,epoch,source_digests,inputs[key[1],key[2]])
            selected[key]=dict(candidate_id=key[0],case_id=key[1],stream=key[2],identity_tap=key[3],prediction=row['result'],native_receipt=native_b,source_index=b)
    require(set(selected)==expected and len(expected)==448,'Exact four-candidate 56-case both-tap prediction grid required')
    _,_,text_bindings=text_api()
    plan=dict(schema='jp_s6c_endpoint_audit.v1',status='PREPARED_BOUND_448_PREDICTIONS_NO_EVENT_SCAN',rows=[selected[k] for k in sorted(selected)],indices=indices,
        epoch=eb,registry=epoch['effective_profile_registry'],endpoint_registration=registry['endpoint_registration'],panel=epoch['panel'],bank=bb,
        empty_music_case_ids=amendment['empty_music_case_ids'],source=binding(__file__),readme=binding(Path(__file__).with_name('README_S6C_ENDPOINT_AUDIT_V1.md')),text_helpers=text_bindings,
        expected_prediction_views=448,pairs=PAIRS,admitted_source_epochs=source_epoch_bindings,
        scope='Complete selected prediction grid and native source chains. Parent controls may use compatible cached N01 native ASR and are identified explicitly; children require exact full-profile/cue native sessions. No observed results read for source selection.')
    return save(output/'PLAN.json',plan)

def run(args):
    pb=binding(args.plan);require(pb['sha256']==args.plan_sha256,'Pinned audit plan changed');plan=read(pb);output=Path(pb['path']).parent
    require(plan['source']==binding(__file__) and plan['readme']==binding(Path(__file__).with_name('README_S6C_ENDPOINT_AUDIT_V1.md')),'Audit source changed')
    require(not (output/'RESULT.json').exists(),'Preserve completed result')
    epoch=read(plan['epoch']);require(plan['epoch']['sha256']==EPOCH_SHA,'Exact epoch6 plan required')
    source_epoch_bindings,source_digests=admitted_source_epochs(epoch);require(source_epoch_bindings==plan['admitted_source_epochs'],'Admitted source epochs differ from plan')
    for b in (plan['registry'],plan['endpoint_registration'],plan['panel'],*plan['indices'],*plan['text_helpers']):raw_read(b)
    normalize,layout,text_bindings=text_api();require(text_bindings==plan['text_helpers'],'Text API bindings differ')
    bank=read(plan['bank']);scenes={s['case_id']:s for s in bank['scenes']};inputs={(x['case_id'],x['stream']):x for x in read(epoch['input_index'])['rows']}
    profiles={(p['candidate_id'],p['asr_tap'],p['identity_tap']):p for p in epoch['profiles']};physical={};cells=[];started=time.perf_counter()
    for row in plan['rows']:
        key=route(row);pred=read(row['prediction']);native=read(row['native_receipt']);source_check(pred,native,key,profiles[key[0],key[2],key[3]],epoch,source_digests,inputs[key[1],key[2]])
        require(pred['identity']['source']==row['native_receipt'],'Prediction native source chain changed')
        for tap,field,journal in ((key[2],'asr_audio','audio_spool.pcm16'),(key[3],'identity_audio','identity_audio_spool.pcm16')):
            inp=inputs[key[1],tap];require(native['identity'][field]==inp['audio'],'Exact canonical native audio route differs')
            require(native['journals'][journal]['sha256']==inp['audio_pcm_sha256'] and native['journals'][journal]['bytes']==round(pred['duration_sec']*16000)*2,'Bounded native receipt journal hash/frame proof differs')
        nk=row['native_receipt']['sha256']
        if nk not in physical:
            summary=read(native['summary']);closure=read(native['finalization'])
            require(closure['state']=='COMPLETED' and not closure['live_lanes_at_finalization'] and closure['event_and_transcript_handles_closed'] is True and not closure['resident_bundle_lease_retained'],'Final native lane/writer closure required')
            require(closure['source_samples']==closure['identity_samples']==round(pred['duration_sec']*16000),'Final paired sample counters differ')
            log=scan_log(native['events'],native['audio_duration_sec']);data=log.finish(native,summary)
            require(data['accepted_advice_equals_dispatch_flag'],'Advisor acceptance/dispatch flag mismatch')
            physical[nk]=dict(native_receipt=row['native_receipt'],native_candidate_id=native['candidate_id'],events=native['events'],summary=native['summary'],finalization=native['finalization'],journals=native['journals'],
                duration_sec=native['audio_duration_sec'],native_elapsed_sec=native.get('native_elapsed_sec'),worker_elapsed_sec=native.get('elapsed_sec'),process_cpu_sec=native.get('process_cpu_sec'),
                bundle_admission_sec=native.get('bundle_admission_sec'),source_speed=native.get('source_speed'),data=data)
        data=physical[nk]['data'];finals=data['raw_final_observations'];text=' '.join(x['text'] for x in finals);hyp=normalize(text).split()
        final_prediction=' '.join(x['text'] for x in pred['final_transcripts_first']);require(normalize(final_prediction).split()==hyp,'Prediction words differ from actual raw native ASR finals')
        reference=layout(scenes[key[1]]);ref=reference['reference'].split();population=reference['population']
        diagnostic=positional_edits(ref,hyp) if reference['complete'] else None
        scope='PRIMARY_SERIALIZED_TOKEN_ALIGNMENT' if population=='PRIMARY_NONOVERLAP' else 'EMPTY_REFERENCE_INSERTIONS_NO_WER_DENOMINATOR' if population=='STRICT_EMPTY_REFERENCE' else 'SERIALIZED_OVERLAP_DIAGNOSTIC_NOT_MIMO_WER_OR_TIMED_WORD_RECALL' if population=='COMPLETE_OVERLAP' else 'INCOMPLETE_REFERENCE_NO_FULL_ASR_TOKEN_LOSS_SCORE'
        cells.append(dict(**row,population=population,native_source_sha256=nk,actual_native_candidate_id=native['candidate_id'],reference_words=len(ref),hypothesis_words=len(hyp),
            raw_final_text=text,first_raw_final_word=hyp[0] if hyp else None,last_raw_final_word=hyp[-1] if hyp else None,
            first_reference_word=ref[0] if ref else None,last_reference_word=ref[-1] if ref else None,token_alignment=diagnostic,token_scope=scope,
            reset_types=data['reset_types'],actual_resets=data['actual_resets'],advisor_proposals=data['advisor_proposals'],accepted_advice=data['accepted_advice']))
        if len(cells)%28==0:print(json.dumps(dict(phase='ENDPOINT_AUDIT',views=len(cells),distinct_native_logs=len(physical),elapsed_sec=time.perf_counter()-started)),flush=True)
    bykey={route(x):x for x in cells};paired=[]
    for left,right in PAIRS:
        for case in sorted({x['case_id'] for x in cells}):
            for tap in ('O0','O1'):
                a,b=bykey[left,case,tap,tap],bykey[right,case,tap,tap];require(a['population']==b['population'],'Paired reference population differs')
                pair=dict(left=left,right=right,case_id=case,tap=tap,population=a['population'],raw_final_words_changed=normalize(a['raw_final_text'])!=normalize(b['raw_final_text']),
                    actual_resets_delta=b['actual_resets']-a['actual_resets'],accepted_advice_delta=b['accepted_advice']-a['accepted_advice'],
                    left_native_source=a['native_source_sha256'],right_native_source=b['native_source_sha256'],same_native_receipt=a['native_source_sha256']==b['native_source_sha256'])
                for field in ('errors','deletions','insertions','substitutions'):
                    pair[field+'_delta']=b['token_alignment'][field]-a['token_alignment'][field] if a['token_alignment'] is not None else None
                pair['first_reference_token_operation']={left:a['token_alignment']['first_reference_token_operation'] if a['token_alignment'] else None,right:b['token_alignment']['first_reference_token_operation'] if b['token_alignment'] else None}
                pair['last_reference_token_operation']={left:a['token_alignment']['last_reference_token_operation'] if a['token_alignment'] else None,right:b['token_alignment']['last_reference_token_operation'] if b['token_alignment'] else None}
                paired.append(pair)
    require(len(cells)==448 and len(bykey)==448,'Complete exact view grid required')
    for pid in PIDS:
        for tap in ('O0','O1'):require(sum(c['candidate_id']==pid and c['stream']==tap and c['population']=='STRICT_EMPTY_REFERENCE' for c in cells)==11,'All11 empty/music controls must remain')
    physical_binding=save(output/'NATIVE_SOURCES.json',dict(rows=list(physical.values())))
    cell_binding=save(output/'CELLS.json',dict(rows=cells));pair_binding=save(output/'PAIRED_DIAGNOSTICS.json',dict(rows=paired))
    return save(output/'RESULT.json',dict(schema='jp_s6c_endpoint_audit.v1',status='COMPLETE_BOUND_448_VIEW_ENDPOINT_DIAGNOSTIC',plan=pb,cells=cell_binding,physical=physical_binding,pairs=pair_binding,
        logical_prediction_views=len(cells),unique_native_sources=len(physical),unique_native_event_logs=len({x['events']['sha256'] for x in physical.values()}),
        populations=dict(Counter(x['population'] for x in cells)),elapsed_sec=time.perf_counter()-started,model_calls=0,new_neural_sessions=0,
        scope='Existing successful source receipts only; execution failures remain in original indices and prevent admission, never converted to empty text. Each distinct native receipt is counted once physically; a source reused by parent controls is not another inference.',
        cost_scope='Logged model/API/decode/advisor/reset/full-dispatch/drain fields are nested and lanes overlap. Per-source worker/native/CPU totals remain separate; no sum into latency or CM5 estimate. Bundle admission is not always model cold load.',
        metric_scope='Token-position alignment is a separate diagnostic with declared tie order. Complete overlap serialization is not inherited MIMO/cp scoring. Incomplete all-speaker reference has null full-ASR edit metrics. First/last token deletion is not timed phonetic loss or proof caused by a reset.',
        unobserved=['Empty text returned by individual reset calls','Continuous journal backlog peak','Acoustic/phonetic word-loss timing','Counterfactual causal reason for a word change'],
        reference_score_scope='Authoritative cp/primary/MIMO rates remain in the separately completed frozen core scorer; this helper does not replace them.'))

def tests():
    cases=[(('start middle end'.split(),'middle end'.split()),('deletion','equal',1,0)),(('start middle end'.split(),'start middle'.split()),('equal','deletion',1,0)),
           (('a b'.split(),'a x'.split()),('equal','substitution',0,0)),(([],['noise']),(None,None,0,1)),(([],[]),(None,None,0,0))]
    count=0
    for (ref,hyp),wanted in cases:
        v=positional_edits(ref,hyp);assert (v['first_reference_token_operation'],v['last_reference_token_operation'],v['deletions'],v['insertions'])==wanted;count+=1
    assert positional_edits(['a','a'],['a'])==positional_edits(['a','a'],['a']);count+=1
    for native,advice,kind in ((True,False,'native_only'),(False,True,'advice_only'),(True,True,'coincident_one_reset')):
        acc=NativeLog(.1004375)
        events=[dict(event_type='research_asr_dispatch',payload=dict(source_start_sec=0.,source_end_sec=.1,native_endpoint=native,advisory_endpoint=advice,reset_requested=True)),
            dict(event_type='research_asr_reset',source_time_sec=.1,payload=dict(native_endpoint=native,advisory_endpoint=advice,compute_ms=1.)),
            dict(event_type='research_asr_full_dispatch_cost',payload=dict(advisor=dict(proposal=advice,accepted=advice,reason='accepted' if advice else 'no_proposal'),advisor_compute_ms=2.,full_dispatch_elapsed_ms=10.)),
            dict(event_type='research_asr_tail_dispatch',payload=dict(source_start_sec=.1,source_end_sec=.1004375,samples=7,compute_ms=1.)),
            dict(event_type='research_asr_drain',payload=dict(source_end_sec=.1004375,padding_is_observed_audio=False,synthetic_right_padding_sec=.66,compute_ms=1.))]
        for e in events:acc.consume(e)
        value=acc.finish(dict(actual_counts=dict(acc.counts)),dict(state='COMPLETED',telemetry=dict(asr_cursor_sec=.1004375,asr_lag_sec=0.)))
        assert value['actual_resets']==1 and value['reset_types']=={kind:1} and value['tail_samples']==7 and value['empty_final_at_reset_count'] is None;count+=1
        assert value['costs']['research_asr_full_dispatch_cost/full_dispatch_elapsed_ms']['sum_sec']==.01;count+=1
    # Keep correct spans/event counts while mutating only the declared tail count.
    for bad_count in (True,-1,7.0,6):
        acc.tail[0]['samples']=bad_count
        try:acc.finish(dict(actual_counts=dict(acc.counts)),dict(state='COMPLETED',telemetry=dict(asr_cursor_sec=.1004375,asr_lag_sec=0.)))
        except ValueError:count+=1
        else:raise AssertionError('Malformed tail sample count accepted')
    try:NativeLog(1).consume(dict(event_type='research_asr_dispatch',payload=dict(source_start_sec=0.,source_end_sec=.1,native_endpoint=False,advisory_endpoint=False,reset_requested=True)))
    except ValueError:count+=1
    else:raise AssertionError('Endpoint OR mismatch admitted')
    normalize,layout,bindings=text_api();assert normalize('A, B!')=='a b';count+=1
    scene=dict(segments=[],all_speaker_reference_complete=False,transcript_valid=False);assert layout(scene)['population']=='INCOMPLETE_REFERENCE';count+=1
    return dict(status='PASS_MODEL_FREE',checks=count,text_bindings=bindings,actual_native_event_scans=0,new_models=0)

def cue_source_tests(epoch):
    from copy import deepcopy
    profiles={(p['candidate_id'],p['asr_tap'],p['identity_tap']):p for p in epoch['profiles']}
    inp=read(epoch['input_index'])['rows'][0];key=('C079',inp['case_id'],inp['stream'],inp['stream']);p=profiles['C079',inp['stream'],inp['stream']]
    parent=profiles['C065',inp['stream'],inp['stream']]
    ni=dict(profile=parent['profile'],execution_digest=epoch['execution_digest'],gallery=None)
    native=dict(status='COMPLETE',identity=ni,job_key=digest(ni),candidate_id='C065',case_id=inp['case_id'],asr_tap=inp['stream'],identity_tap=inp['stream'],audio_duration_sec=inp['duration_sec'])
    identity=dict(profile=p['profile'],cue_condition=p['cue_condition'],telemetry=inp['telemetry'],gallery=None)
    pred=dict(status='COMPLETE',candidate_id='C079',case_id=inp['case_id'],stream=inp['stream'],identity_tap=inp['stream'],identity=identity,prediction_key=digest(identity),duration_sec=inp['duration_sec'])
    source_check(pred,native,key,p,epoch,{epoch['execution_digest']},inp);count=1
    for field,value in (('cue_condition','CUES_OFF'),('telemetry',None),('telemetry',dict(inp['telemetry'],sha256='0'*64))):
        bad=deepcopy(pred);bad['identity'][field]=value;bad['prediction_key']=digest(bad['identity'])
        try:source_check(bad,native,key,p,epoch,{epoch['execution_digest']},inp)
        except ValueError:count+=1
        else:raise AssertionError('Canonical cue binding mismatch admitted')
    for changed in (dict(inp,case_id='wrong'),dict(inp,stream='O1' if inp['stream']=='O0' else 'O0')):
        try:source_check(pred,native,key,p,epoch,{epoch['execution_digest']},changed)
        except ValueError:count+=1
        else:raise AssertionError('Wrong canonical case/tap admitted')
    return dict(status='PASS_MODEL_FREE_SYNTHETIC_PARENT_SOURCE',checks=count,scope='Synthetic prediction/native envelopes with exact registered parent profiles and actual canonical metadata; no prediction/event read.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=['checks','prepare','run']);p.add_argument('--name');p.add_argument('--index',nargs=2,action='append',metavar=('PATH','SHA256'));p.add_argument('--plan');p.add_argument('--plan-sha256');a=p.parse_args()
    if a.action=='checks':
        result=tests();eb,epoch,_,_,_,_=authorities();source_bindings,_=admitted_source_epochs(epoch);result['cue_source_fixtures']=cue_source_tests(epoch)
        preserved=SIM/'staging/s6c/20260910T123540Z/endpoint_audit/before_epoch_guard_v1'
        result.update(source=binding(__file__),readme=binding(Path(__file__).with_name('README_S6C_ENDPOINT_AUDIT_V1.md')),epoch=eb,admitted_source_epochs=source_bindings,
            prior_source_resolver=[binding(preserved/name) for name in ('s6c_endpoint_audit_v1.py','README_S6C_ENDPOINT_AUDIT_V1.md','AUDIT_HELPER_CHECKS.json')])
        preserved2=SIM/'staging/s6c/20260910T123540Z/endpoint_audit/before_tail_cue_guards_v2'
        result['pre_review_guard_source_resolver']=[binding(preserved2/name) for name in ('s6c_endpoint_audit_v1.py','README_S6C_ENDPOINT_AUDIT_V1.md','AUDIT_HELPER_CHECKS_V2.json')]
        print(json.dumps(save(REPORT/'endpoint_factorial_v1/AUDIT_HELPER_CHECKS_V3.json',result)))
    elif a.action=='prepare':
        if not a.index or not a.name:p.error('prepare requires --name and repeated --index PATH SHA256')
        print(json.dumps(prepare(a)))
    else:
        if not a.plan or not a.plan_sha256:p.error('run requires --plan and --plan-sha256')
        print(json.dumps(run(a)))
