"""Independent metadata-only preparation review. See README_S6C_STRUCTURAL_PACED_REVIEW_V1.md."""
from __future__ import annotations
import argparse, ast, hashlib, json, math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
IDS=['C067','C122','C121','C079','C117','C118']
NAMESPACE='structural_and_matched_controls_v1'
PINS={
 'design/PACED_STRUCTURAL_AND_MATCHED_CONTROLS_V1.json':'0057971fd2fb4d2107b2ce5d8c5215ed84be160776c3bc25f105f0154a262080',
 'paced_candidates/structural_and_matched_controls_v1/MANIFEST.json':'c8490fc3d669dce89023e2de54e4e4547e16985a635fd578d36bd218702279ae',
 'EPOCH4_EXECUTION_MANIFEST.json':'720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945',
 'EFFECTIVE_PROFILE_REGISTRY_V7.json':'924f8b35950ba053c636687766ff579b6310b89c2a3cab0befbdf267871d0734',
 'design/confirmation_plan_v1/PACED_PANEL_PROPOSAL_V1.json':'f303d7e80bc9dd8fa8b7ba7444216d1e6b29f75a0cce8762c40d92ce5201c6da',
}
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def run(output):
    checks=0; bindings={}; cache={}
    def ok(v,label):
        nonlocal checks
        if not v:raise AssertionError(label)
        checks+=1
    def read(path,b=None,sha=None,decode=True):
        path=Path(path).resolve()
        ok(path.suffix.lower() in ('.json','.py','.md'),'metadata/source suffix only')
        if str(path) not in cache:
            raw=path.read_bytes(); cache[str(path)]=raw
            bindings[str(path)]=dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        raw=cache[str(path)];actual=bindings[str(path)]
        if b is not None:ok(actual==dict(path=str(Path(b['path']).resolve()),bytes=b['bytes'],sha256=b['sha256']),'exact metadata binding')
        if sha:ok(actual['sha256']==sha,'pinned metadata bytes')
        return json.loads(raw) if decode else raw
    values={p:read(REPORT/p,sha=h) for p,h in PINS.items()}
    scope=values['design/PACED_STRUCTURAL_AND_MATCHED_CONTROLS_V1.json']
    plan=values['paced_candidates/structural_and_matched_controls_v1/MANIFEST.json']
    epoch=values['EPOCH4_EXECUTION_MANIFEST.json']
    registry=values['EFFECTIVE_PROFILE_REGISTRY_V7.json']
    panel=values['design/confirmation_plan_v1/PACED_PANEL_PROPOSAL_V1.json']
    ok(scope['candidates']==IDS==plan['candidates'],'fixed six ordered IDs')
    ok(scope['namespace']==NAMESPACE==plan['namespace'],'namespace')
    ok(scope['native_execution']=='NOT_STARTED' and scope['quiet_admission']=='NOT_ISSUED','scope no native or quiet admission')
    ok(plan['status']=='PREPARED_NO_MODELS_STARTED','prepared marker')
    ok(plan['schema']=='s6c-canonical-paired-paced.v1','canonical schema')
    ok(plan['manifest_key']==digest({k:v for k,v in plan.items() if k!='manifest_key'}),'plan key')
    ok(plan['execution_manifest']==scope['epoch']==bindings[str((REPORT/'EPOCH4_EXECUTION_MANIFEST.json').resolve())],'exact epoch binding')
    ok(scope['registry']==bindings[str((REPORT/'EFFECTIVE_PROFILE_REGISTRY_V7.json').resolve())],'exact V7')
    ok(epoch['epoch']=='epoch4','execution epoch4')
    ok(scope['panel']==plan['panel']==bindings[str((REPORT/'design/confirmation_plan_v1/PACED_PANEL_PROPOSAL_V1.json').resolve())],'exact original panel binding')
    ok(plan['source_case_ids']==panel['case_ids'] and plan['repeat_case_ids']==panel['repeated_case_ids'],'original panel IDs')
    ok(len(panel['case_ids'])==len(set(panel['case_ids']))==16 and len(panel['repeated_case_ids'])==len(set(panel['repeated_case_ids']))==4 and set(panel['repeated_case_ids'])<=set(panel['case_ids']),'16 plus 4')
    ok(plan['panel_mode']=='full16_plus4' and panel['streams']==['O0','O1'],'panel mode and taps')
    ok(plan['worker_limit']==scope['worker_count']==1 and plan['inner_threads']==scope['inner_threads']==1,'one worker/inner thread')
    ok(plan['pending_cell_bytes']==512*2**20 and plan['max_run_sec']==28800,'held resource constants')
    ok(scope['source_speed'] is True and datetime.fromisoformat(plan['deadline_utc'].replace('Z','+00:00'))==datetime.fromisoformat(scope['deadline_utc'].replace('Z','+00:00')),'paced speed and equivalent absolute deadline')
    ok(scope['expected_total_cells']==240 and scope['expected_per_candidate_cells']==40,'declared grid')
    read(REPORT/'design/README_PACED_STRUCTURAL_AND_MATCHED_CONTROLS_V1.md',decode=False)
    prior=read(REPORT/'paced_candidates/naming_and_empty_controls_v1/MANIFEST.json')
    review=read(REPORT/'independent_review/PACED_COMPONENT_REVIEW_V3.json')
    ok(review['status']=='PASS_BOUNDED_PACED_V3_COMPONENT_REVIEW','held adapter review')
    ok(plan['sources']==prior['sources'],'same reviewed preparation source bindings')
    ok(plan['original_native_function']==prior['original_native_function']=='e18309bf381da458086b524a129bae11bf61382596c607d4c059976051f525f2','unchanged declared native function identity')
    for b in plan['sources']:read(b['path'],b=b,decode=False)
    ok(scope['helper'] in plan['sources'],'scope exact helper')
    # Parse only two pure source constructors: no application/worker/module import.
    tree=ast.parse(read(scope['helper']['path'],b=scope['helper'],decode=False).decode('utf-8-sig'))
    pure=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('validate_source_rows','source_record')],type_ignores=[])
    ok(len(pure.body)==2,'exact source constructor functions located')
    env={};exec(compile(pure,'held pure source constructors','exec'),env)
    ok(plan['input_index']==epoch['input_index'],'canonical input binding')
    inputs=read(plan['input_index']['path'],b=plan['input_index'])
    lookup={(x['case_id'],x['stream']):x for x in inputs['rows']}
    ok(len(lookup)==len(inputs['rows'])==480,'unique original 480 input rows')
    ep={(x['candidate_id'],x['asr_tap'],x['identity_tap']):x for x in epoch['profiles']}
    reg={(x['candidate_id'],x['asr_tap'],x['identity_tap']):x for x in registry['profiles']}
    scope_rows={(x['candidate_id'],x['asr_tap'],x['identity_tap']):x for x in scope['profiles']}
    ok(len(scope_rows)==len(scope['profiles'])==12,'12 scoped routes')
    for cid in IDS:
        for tap in ('O0','O1'):
            key=(cid,tap,tap); row=ep[key]
            ok(row==reg[key],'epoch row equals final V7 row')
            ok(scope_rows[key]=={k:row[k] for k in scope_rows[key]},'scope profile projection')
            prof=read(row['profile_binding']['path'],b=row['profile_binding'])
            ok(prof==row['profile'] and digest(prof)==row['profile_digest'],'exact actual profile bytes/digest')
            real=cid in ('C122','C079','C118')
            ok(row['cue_condition']==('REAL_ALIGNED_CUES' if real else 'CUES_OFF'),'exact intended cue condition')
            ok(prof['tracker']['cues_enabled'] is real and prof['xvf']['mode']==('tracking_only' if real else 'none'),'runtime cue policy')
            ok(row['gallery_condition']=='NONE' and row['enrollment_tier'] is None and prof['identity']['mode']=='none','explicit no gallery naming')
            ok(prof['input']['gain']==1. and prof['input']['already_gained'] is True and prof['input']['asr_tap']==prof['input']['identity_tap']==tap,'unit adapter gain/same tap')
    expected=[(cid,case,tap,rep) for rep,cases in ((1,panel['case_ids']),(2,panel['repeated_case_ids'])) for case in cases for tap in ('O0','O1') for cid in (IDS if rep==1 else list(reversed(IDS)))]
    actual=[(j['candidate_id'],j['case_id'],j['asr_tap'],j['repetition']) for j in plan['jobs']]
    ok(actual==expected and len(actual)==len(set(actual))==240,'exact ordered grid')
    sources={};duration_samples=0
    for j in plan['jobs']:
        cid,case,tap,rep=j['candidate_id'],j['case_id'],j['asr_tap'],j['repetition']
        row=ep[(cid,tap,tap)]
        ok(j['identity_tap']==tap and j['profile_row']==row and j['profile_sha256']==digest(row),'job exact profile and route')
        ok(j['job_id']==f'{cid}_{case}_{tap}_{tap}_r{rep}' and j['job_key']==digest({k:v for k,v in j.items() if k!='job_key'}),'job identity/digest')
        ok(j['gallery'] is None and j['gallery_row'] is None,'job no gallery markers')
        for root in ('report_root','payload_root'):
            ok(Path(j[root])==Path(plan[root])/'jobs'/j['job_id'],'isolated output root')
        source=read(j['source']['path'],b=j['source'])
        ok(Path(j['source']['path'])==Path(plan['report_root'])/'sources'/f'{case}.json','exact per-case metadata path')
        pair={t:lookup[(case,t)] for t in ('O0','O1')}
        ok(source==env['source_record'](pair,plan['input_index']),'full exact canonical source declaration')
        ok(source['source_offset_samples']==source['inserted_gap_samples']==0 and source['no_new_gain'] is True and source['adapter_gain']==1.,'unshifted complete source/no extra gain')
        ok(source['duration_samples']==715127 and source['duration_sec']==44.6954375,'actual panel duration')
        ok(j['timeout_sec']==max(720.,source['duration_sec']*1.75+row['profile']['runtime']['lane_drain_timeout_sec']+120.),'held timeout rule')
        sources[case]=j['source'];duration_samples+=source['duration_samples']
    ok(len(sources)==16,'16 unique source metadata records')
    ok(Counter(x[0] for x in actual)==Counter({x:40 for x in IDS}),'40 cells each')
    ok(Counter(x[3] for x in actual)==Counter({1:192,2:48}),'192 first plus 48 repeated')
    ok(math.isclose(plan['total_source_sec'],duration_samples/16000,abs_tol=1e-9,rel_tol=0) and scope['source_seconds']==duration_samples/16000==10726.905,'integer sample source total')
    rr=Path(plan['report_root']);pr=Path(plan['payload_root'])
    observed_report=sorted(p.name for p in rr.iterdir())
    observed_payload=sorted(p.name for p in pr.iterdir()) if pr.exists() else None
    ok(observed_report==['MANIFEST.json','sources'] and observed_payload in (None,[]),'namespace has preparation only at review')
    result=dict(schema='s6c.structural_paced_preparation_review.v1',status='PASS_METADATA_PREPARATION_ONLY',
        created_utc=datetime.now(timezone.utc).isoformat(),check_count=checks,
        candidates=IDS,cell_count=240,per_candidate=40,first_repetition_cells=192,second_repetition_cells=48,
        source_cases=16,repeated_cases=4,source_samples=duration_samples,source_sec=duration_samples/16000,
        actual_execution_epoch='epoch4',registry_authority='V7 exact selected rows also equal epoch4',
        native_execution='NOT_STARTED_IN_REVIEWED_NAMESPACE_AT_REVIEW',quiet_admission='NOT_ISSUED',
        observed_report_children=observed_report,observed_payload_children=observed_payload,
        source_bindings=list(bindings.values()),
        reviewed_pure_functions=['validate_source_rows','source_record'],
        semantics='C067/C122 representatives and C121/C079/C117/C118 matched controls; this is finite preparation, not final operating selection.',
        limits=['No native execution, application import, fixture rerun, PCM/model/telemetry byte read, pipeline replay or scoring.',
                'Audio hashes, full PCM support and gain history were compared as authoritative input metadata declarations; original byte validation is inherited, not repeated.',
                'No live process/resource/quiet census; later run admission must establish these.',
                'Native-function declaration compared to prior reviewed preparation with identical source bytes; no function/model executed.'],
        preserved_initial_scope_guard=scope['preserved_pre_output_attempt'],
        review_prepublication_attempt='Initial review compared deadline strings; equivalent UTC and -04:00 values correctly compare as one timestamp. It stopped before receipt publication. No source/prepared job changed.')
    for p in (Path(__file__),Path(__file__).with_name('README_S6C_STRUCTURAL_PACED_REVIEW_V1.md')):read(p,decode=False)
    result['source_bindings']=list(bindings.values())
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    raw=output.read_bytes();print(json.dumps(dict(status=result['status'],checks=checks,path=str(output),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
