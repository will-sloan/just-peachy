"""Additive actual cadence-floor audit; README_S6C_CADENCE_FLOOR_AUDIT_V2.md."""
from __future__ import annotations
import argparse,ast,hashlib,importlib,json,math,sys,tempfile,time
from collections import Counter,defaultdict
from copy import deepcopy
from pathlib import Path

HERE=Path(__file__).resolve().parent;SIM=HERE.parent;REPORT=SIM/'reports/S6C/20260910T123540Z';PAYLOAD=Path('G:/Just_Peachy_S6C/20260910T123540Z')
OLD_SHA='5491c083c297a62852564e2fd0136ea2922e06aa07eff3829e72a97a4a0ebfe5'
EPOCH_SHA='676ead81afe85b5557494bd851e67f34799106a45976e8f7fa6e2e5900989cbc'
PARENT_SHA='96f9b5d604001f740543dc98945e8ad6f31b30aa137687e973bb9aec77779e4d'
AMENDMENT_SHA='69046b327908410cc7d291c23b7d77205f7cdacd7ca19ac03caf52307ed5d9d5'
CANDIDATES={'C191':('C071',.5),'C192':('C082',.5),'C193':('C071',2.),'C194':('C082',2.)}
SCHEMA='jp_s6c_cadence_floor_native_audit.v2'

def require(ok,message):
    if not ok:raise ValueError(message)

require(hashlib.sha256((HERE/'s6c_native_cadence_audit.py').read_bytes()).hexdigest()==OLD_SHA,'Original held audit changed')
A=importlib.import_module('s6c_native_cadence_audit');require(Path(A.__file__).resolve()==HERE/'s6c_native_cadence_audit.py','Wrong original audit import')

def sources():return [A.bind(p) for p in (Path(__file__),HERE/'README_S6C_CADENCE_FLOOR_AUDIT_V2.md',HERE/'s6c_native_cadence_audit.py')]
def quiet():require(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'Active paced quiet owner; defer native log reads')
def exact(path,sha):
    b=A.bind(path);require(b['sha256']==sha,'Exact declared source hash differs');return b,A.read(b)
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);A.write(path,value);return A.bind(path)
def digest(value):return hashlib.sha256(A.dumps(value).encode()).hexdigest()

def aggregate(records,candidates):
    """Execute the two original compact aggregation statements without editing them."""
    node=next(n for n in ast.parse((HERE/'s6c_native_cadence_audit.py').read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='run')
    starts=[i for i,n in enumerate(node.body) if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=='compact']
    require(len(starts)==1,'Original aggregate marker differs');i=starts[0];nodes=deepcopy(node.body[i:i+2])
    require(isinstance(nodes[1],ast.For) and ast.unparse(nodes[1].iter)=='SOURCES','Original aggregate shape differs')
    ns=dict(records=records,SOURCES=candidates,Counter=Counter,defaultdict=defaultdict)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<exact original cadence aggregate>','exec'),ns)
    return ns['compact'],hashlib.sha256(ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False).encode()).hexdigest()

def grid(rows,count,candidates):
    keys={(r['candidate_id'],r['case_id'],r['asr_tap'],r['identity_tap']) for r in rows}
    require(len(rows)==len(keys)==count and {k[0] for k in keys}==set(candidates),'Exact candidate/grid count differs')
    cases={k[1] for k in keys};require(len(cases)==56 and keys=={(c,s,t,t) for c in candidates for s in cases for t in ('O0','O1')},'Exact56 both-tap native product required')
    require(all(r['status'] in ('COMPLETE','COMPLETE_REUSED') for r in rows),'Unsuccessful native cell cannot be omitted')
    return cases

def metadata(core_binding):
    core=A.read(core_binding);require(core['status']=='COMPLETE_REQUESTED_INDEX' and core['requested']==core['scored']==448 and not core['unscored'],'Complete448 core required')
    pred=A.read(core['index']);require(pred['status']=='COMPLETE' and pred['requested']==pred['completed']==448 and len(pred['source_indices'])==1,'Complete448 native/shared index required')
    eb=pred['execution_manifest'];require(eb['sha256']==EPOCH_SHA,'Exact epoch5 required');epoch=A.read(eb)
    require(epoch['execution_digest']==digest({k:epoch[k] for k in ('execution_files','assets','versions','state_policy')}),'Epoch execution digest differs')
    nb=pred['source_indices'][0];native=A.read(nb);require(native['status']=='COMPLETE' and native['completed']==native['requested']==448 and native['execution_manifest']==eb,'Closed448 native index differs')
    cases=grid(native['rows'],448,CANDIDATES)
    require(len(pred['rows'])==448 and {(r['candidate_id'],r['case_id'],r['stream'],r['identity_tap']) for r in pred['rows']}=={(c,s,t,t) for c in CANDIDATES for s in cases for t in ('O0','O1')},'Prediction/native exact grid differs')
    require(all(r['status']=='COMPLETE' for r in pred['rows']),'Actual native/shared failure retained as failure')
    ab,amend=exact(REPORT/'design/CADENCE_FLOOR_NEIGHBORHOOD_V1.json',AMENDMENT_SHA)
    require({r['candidate_id']:r['parent'] for r in amend['candidates']}=={c:p for c,(p,f) in CANDIDATES.items()},'Exact registered parent identities differ')
    method=[b for b in epoch['execution_files'] if Path(b['path']).name in ('research_evidence_v3.py','research_scheduler_v3.py','runtime.py')]
    require(len(method)==3,'Frozen runtime/cadence/scheduler sources required')
    for b in method:require(A.bind(b['path'])==b,'Frozen native method bytes differ')
    parent_b,parent=exact(REPORT/'cadence_audit_v1/RESULT.json',PARENT_SHA);require(parent['status']=='COMPLETE_336_BOUND_NATIVE_CELLS','Original parent audit incomplete')
    parent_cells=A.read(parent['cells_binding'])['rows'];require(len(parent_cells)==336,'Original compact cell count differs')
    require({r['case_id'] for r in parent_cells}==cases,'Parent/new panel cases differ')
    for cid,(parent_id,floor) in CANDIDATES.items():
        for tap in ('O0','O1'):
            row=[r for r in epoch['profiles'] if r['candidate_id']==cid and r['asr_tap']==r['identity_tap']==tap]
            pr=[r for r in epoch['profiles'] if r['candidate_id']==parent_id and r['asr_tap']==r['identity_tap']==tap]
            require(len(row)==len(pr)==1,'Unique registered parent/child route required')
            child=deepcopy(row[0]['profile']);baseline=deepcopy(pr[0]['profile']);child['profile_id']=baseline['profile_id'];child['embedding']['voice_observation_floor_sec']=baseline['embedding']['voice_observation_floor_sec']
            require(child==baseline and row[0]['profile']['embedding']['voice_observation_floor_sec']==floor,'More than exact registered floor changed')
            old=[r for r in parent_cells if r['candidate_id']==parent_id and r['tap']==tap]
            require(len(old)==56 and all(r['profile']==baseline['embedding'] and r['tracker_cues']==baseline['tracker']['cues_enabled'] for r in old),'Original parent audit settings differ')
    return dict(core=core_binding,prediction_index=core['index'],native_index=nb,epoch=eb,amendment=ab,parent_audit=parent_b,parent_cells=parent['cells_binding'],method_sources=method),native,epoch,parent,parent_cells

def validate_native(row,rec,epoch,inputs):
    cid=row['candidate_id'];tap=row['asr_tap'];ident=rec['identity']
    require(rec['status']=='COMPLETE' and rec['job_key']==row['job_key']==digest(ident),'Exact native receipt status/key differs')
    for k in ('candidate_id','case_id','asr_tap','identity_tap','recipe_id'):require(rec[k]==row[k],'Native row/receipt field differs: '+k)
    choices=[r for r in epoch['profiles'] if r['candidate_id']==cid and r['asr_tap']==r['identity_tap']==tap];require(len(choices)==1,'Unique native registered route required');profile=choices[0]
    require(ident['execution_digest']==epoch['execution_digest'] and ident['profile']==profile['profile'] and ident['cue_condition']==profile['cue_condition'],'Actual native epoch/profile/cue differs')
    src=inputs[rec['case_id'],tap];wantcue=None if profile['cue_condition']=='CUES_OFF' else src['telemetry']
    require(ident['asr_audio']==ident['identity_audio']==src['audio'] and ident['telemetry']==wantcue and rec['audio_duration_sec']==src['duration_sec'],'Actual source/tap/cue binding differs')
    require(ident['gallery'] is None and ident['gallery_condition']=='NONE' and ident['realtime'] is False and ident['fresh_state'] is True and ident['inner_threads']==1,'Native execution scope differs')
    require(rec['hardware_invocations']==0 and rec['reference_truth_sent_to_predictor'] is False,'Unadmitted hardware/truth source')
    final=A.read(rec['finalization']);require(final['state']=='COMPLETED' and final['finalization_error'] is None and not final['live_lanes_at_finalization'] and not final['resident_bundle_lease_retained'] and final['event_and_transcript_handles_closed'] is True,'Native finalization incomplete')
    return profile['profile']

def prepare(args):
    quiet();out=REPORT/'cadence_floor_audit_v2';require(not out.exists(),'Preserve prior audit namespace');cb=A.bind(args.core);require(cb['sha256']==args.core_sha256,'Exact completed core receipt required')
    refs,*_=metadata(cb);return save(out/'PLAN.json',dict(schema=SCHEMA,status='PREPARED_NO_EVENT_SCAN',sources=sources(),dependencies=refs,expected_new_native_cells=448,parent_native_cells_reused_as_compact=336))

def run(args):
    quiet();pb,plan=exact(args.plan,args.sha256);out=Path(pb['path']).parent
    require(out==REPORT/'cadence_floor_audit_v2' and plan['schema']==SCHEMA and plan['status']=='PREPARED_NO_EVENT_SCAN' and plan['sources']==sources(),'Exact prepared source/namespace differs')
    require(not (out/'RESULT.json').exists() and not (out/'FAILURE.json').exists(),'Preserve previous audit')
    started=time.perf_counter();records=[]
    try:
        refs,native,epoch,parent,parent_cells=metadata(plan['dependencies']['core']);require(refs==plan['dependencies'],'Prepared source chain changed')
        input_doc=A.read(epoch['input_index']);inputs={(r['case_id'],r['stream']):r for r in input_doc['rows']};require(len(inputs)==480,'Exact canonical480 inputs required')
        for row in native['rows']:
            quiet();rb=row['receipt'];folder=A.within(rb['path'],PAYLOAD/'epoch5').parent;rec=A.read(rb);profile=validate_native(row,rec,epoch,inputs)
            require(Path(rec['events']['path']).resolve().is_relative_to(folder) and Path(rec['summary']['path']).resolve().is_relative_to(folder),'Native event/summary outside exact job')
            acc=A.Accumulator(profile,rec['audio_duration_sec']);streamed=A.stream_exact(rec['events'],acc);summary=A.read(rec['summary']);require(summary['research']['profile']==profile,'Native summary profile differs');data=acc.finish(rec,summary)
            records.append(dict(candidate_id=rec['candidate_id'],case_id=rec['case_id'],tap=rec['asr_tap'],receipt=rb,events=streamed,summary=rec['summary'],finalization=rec['finalization'],duration_sec=rec['audio_duration_sec'],native_elapsed_sec=rec['native_elapsed_sec'],worker_elapsed_sec=rec['elapsed_sec'],process_cpu_sec=rec['process_cpu_sec'],profile=profile['embedding'],tracker_cues=profile['tracker']['cues_enabled'],data=data))
            if len(records)%28==0:print(json.dumps(dict(phase='CADENCE_FLOOR_ACTUAL_AUDIT',read=len(records),requested=448,elapsed_sec=time.perf_counter()-started)),flush=True)
        require(len(records)==448,'Exact new native audit count differs');compact,aggregate_ast=aggregate(records,CANDIDATES)
        cells=save(out/'NATIVE_CELLS.json',dict(schema=SCHEMA,rows=records))
        return save(out/'RESULT.json',dict(schema=SCHEMA,status='COMPLETE_448_NEW_BOUND_NATIVE_CELLS',plan=pb,cells=448,summary=compact,cells_binding=cells,parent_summary=parent['summary'],parent_audit=refs['parent_audit'],parent_cells=refs['parent_cells'],aggregation_ast_sha256=aggregate_ast,source_bindings=sources(),elapsed_sec=time.perf_counter()-started,new_neural_calls=0,parent_event_logs_reread=0,scope='Four registered numeric floor neighbors, all56 cases/both taps. Exact original incidence and aggregation arithmetic; old parent observations reused from certified compact cells, not rescanned. Global due acknowledgments are opportunities, not proof that target voice was served. Direct cue flags and uncertainty overlap do not identify separate onset/cosine causes. Accelerated native/cost observations are not source-paced or CM5 behavior. Scored quality and its populations remain in the separate core tables.'))
    except Exception as exc:
        save(out/'FAILURE.json',dict(status='FAILED_PRESERVED',plan=pb,error=repr(exc),read_cells=len(records)));raise

def checks():
    checked=[]
    def bad(name,fn):
        try:fn()
        except (ValueError,KeyError):checked.append(name);return
        raise AssertionError(name+' accepted')
    require(A.tests()==dict(status='PASS',checks=12,neural_calls=0),'Held accumulator fixtures changed');checked.append('Original12 actual parser/causality guards unchanged')
    rows=[dict(candidate_id=c,case_id=str(s),asr_tap=t,identity_tap=t,status='COMPLETE') for c in CANDIDATES for s in range(56) for t in ('O0','O1')]
    require(len(grid(rows,448,CANDIDATES))==56,'Synthetic448 grid');checked.append('Exact four-profile56x2 grid')
    bad('Duplicate native row',lambda:grid(rows[:-1]+rows[:1],448,CANDIDATES));bad('Missing cell',lambda:grid(rows[:-1],448,CANDIDATES))
    other=deepcopy(rows);other[0]['identity_tap']='O1';bad('Split-route substitution',lambda:grid(other,448,CANDIDATES))
    other=deepcopy(rows);other[0]['status']='FAILED';bad('Failed actual cell',lambda:grid(other,448,CANDIDATES))
    _,ast_hash=aggregate([],[]);checked.append('Original aggregate two statements compiled without AST changes')
    with tempfile.TemporaryDirectory(prefix='cadence_floor_admission_') as td:
        f=Path(td)/'finalization.json';A.write(f,dict(state='COMPLETED',finalization_error=None,live_lanes_at_finalization=[],resident_bundle_lease_retained=False,event_and_transcript_handles_closed=True));fb=A.bind(f)
        source=dict(audio=dict(path='audio',bytes=1,sha256='a'*64),telemetry=dict(path='cue',bytes=2,sha256='b'*64),duration_sec=1.)
        route=dict(candidate_id='C192',asr_tap='O0',identity_tap='O0',profile={'profile_id':'C192'},cue_condition='REAL_ALIGNED_CUES')
        epoch=dict(execution_digest='d',profiles=[route]);identity=dict(execution_digest='d',profile=route['profile'],cue_condition=route['cue_condition'],asr_audio=source['audio'],identity_audio=source['audio'],telemetry=source['telemetry'],gallery=None,gallery_condition='NONE',realtime=False,fresh_state=True,inner_threads=1)
        row=dict(candidate_id='C192',case_id='case',asr_tap='O0',identity_tap='O0',recipe_id='N07',job_key=digest(identity))
        rec=dict(row,status='COMPLETE',identity=identity,audio_duration_sec=1.,hardware_invocations=0,reference_truth_sent_to_predictor=False,finalization=fb)
        require(validate_native(row,rec,epoch,{('case','O0'):source})==route['profile'],'Valid synthetic native admission');checked.append('Actual native admission function accepts exact synthetic chain')
        for label,key,value in [('Audio substitution','asr_audio',{}),('Cue substitution','telemetry',None),('Native profile substitution','profile',{}),('Unexpected gallery','gallery',{}),('Paced source substitution','realtime',True),('Mutable tracker reuse','fresh_state',False),('Wrong epoch','execution_digest','other')]:
            rr=deepcopy(rec);rr['identity'][key]=value;rr['job_key']=digest(rr['identity']);rw=dict(row,job_key=rr['job_key'])
            bad(label,lambda rr=rr,rw=rw:validate_native(rw,rr,epoch,{('case','O0'):source}))
        wrong=deepcopy(rec);wrong['reference_truth_sent_to_predictor']=True;bad('Undeclared reference input',lambda:validate_native(row,wrong,epoch,{('case','O0'):source}))
        final=A.read(fb);final['finalization_error']='error';f2=Path(td)/'failed.json';A.write(f2,final);wrong=dict(rec,finalization=A.bind(f2));bad('Failed native finalization',lambda:validate_native(row,wrong,epoch,{('case','O0'):source}))
    return dict(status='PASS_SOURCE_ONLY',checks=checked,inherited_checks=12,aggregation_ast_sha256=ast_hash,sources=sources(),actual_native_log_reads=0,model_calls=0)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);sub=p.add_subparsers(dest='action',required=True)
    t=sub.add_parser('checks');t.add_argument('--output',type=Path)
    a=sub.add_parser('prepare');a.add_argument('--core',type=Path,required=True);a.add_argument('--core-sha256',required=True)
    a=sub.add_parser('run');a.add_argument('--plan',type=Path,required=True);a.add_argument('--sha256',required=True)
    a=p.parse_args();result=checks() if a.action=='checks' else prepare(a) if a.action=='prepare' else run(a)
    if a.action=='checks' and a.output:result=save(a.output,result)
    print(json.dumps(result,indent=2,allow_nan=False))
