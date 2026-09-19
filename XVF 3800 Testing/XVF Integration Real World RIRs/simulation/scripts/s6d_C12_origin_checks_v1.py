"""Fake-header/producer fixtures for C12 origin; README_S6D_C12_ORIGIN_CHECKS_V1.md."""
from __future__ import annotations
import argparse, ast, hashlib, json, math, sys, threading, traceback, types
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

def bind(p):
    p=Path(p);d=p.read_bytes();return dict(path=str(p),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())
def read(p):return json.loads(Path(p).read_bytes())

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--proposal',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();assert out.drive.casefold()=='g:' and 'review_fixtures' in out.parts;out.mkdir(parents=True,exist_ok=False)
    plan=read(a.proposal);manifest=read(plan['manifest']['path']);old=read(plan['parent_manifest']['path'])
    source=Path(manifest['source_root'])/'edge_speech_pipeline/research_beams_s6d.py';old_source=Path(old['source_root'])/'edge_speech_pipeline/research_beams_s6d.py'
    rows=[]
    def check(name,call):
        try:call();rows.append(dict(name=name,status='PASS'))
        except BaseException:rows.append(dict(name=name,status='FAIL',error=traceback.format_exc()))
    def reject(call):
        try:call()
        except (ValueError,RuntimeError,KeyError):return
        raise AssertionError('Expected rejection')
    def equal(x,y):assert x==y,(x,y)
    names=('auto_asr','focus0_asr','focus1_asr');routes=((7,3),(7,0),(7,1));registry={}
    def fake_binding(path):return dict(path=str(path),bytes=1,sha256='a'*64)
    def fake_verified(ref):return deepcopy(registry[ref['path']])
    streams=[dict(name=n,category=c,source=s,raw_gain=1.,audio=fake_binding(n+'.wav'),common_capture_start_native_frame=0) for n,(c,s) in zip(names,routes)]
    configuration=fake_binding('configuration');case=fake_binding('case');qualification=fake_binding('qualification')
    registry['admission']=dict(schema_version='edge-s6d-capture-admission.v1',status='ACCEPTED_FOR_NATIVE_ANALYSIS',capture_source_id='fixture-C',route_id='fixture-route',capture_epoch='fixture',common_origin='fixture-common',case_result=case,configuration=configuration,qualification=qualification,sample_count=4,stream_names=list(names))
    registry['configuration']=dict(profile='P_MAIN6');registry['case']=dict(status='PASS',transport_integrity_status='PASS',configuration=configuration,streams=streams)
    registry['qualification']=dict(schema_version='edge-s6d-route-qualification.v1',status='PASS',case_result=case,configuration=configuration,stream_identity_verified=True,common_frame_origin_verified=True,source_tail_validity_verified=True,stream_names=list(names))
    settings=types.SimpleNamespace(asr_stream='auto_asr',identity_streams=('focus0_asr','focus1_asr'),mode='mono_asr_beam_identity',validate=lambda:None)
    def classes(path):
        tree=ast.parse(path.read_bytes());nodes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name in {'CaptureAdmission','CapturedSource'}]
        ns=dict(Path=Path,binding=fake_binding,verified=fake_verified,finite=lambda x:type(x) in (int,float) and math.isfinite(x),PairedWavSource=object,threading=threading,ExitStack=ExitStack)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns);return ns
    current=classes(source);parent=classes(old_source)
    def admission(rates=(16000,16000,16000)):
        seen=[]
        def info(path):
            index=[x['audio']['path'] for x in streams].index(str(path));seen.append(index)
            return types.SimpleNamespace(samplerate=rates[index],channels=1,subtype='PCM_24',frames=4)
        with patch.dict(sys.modules,{'soundfile':types.SimpleNamespace(info=info)}):v=current['CaptureAdmission']('admission',settings)
        equal(seen,[0,1,2]);return v
    check('three_validated_headers_yield_actual_common_rate',lambda:equal(admission().sample_rate,16000))
    for index in range(3):
        def wrong(index=index):
            rates=[16000]*3;rates[index]=8000;reject(lambda:admission(rates))
        check('wrong_header_stream_'+str(index)+'_rejects_before_origin',wrong)
    evidence=Path(manifest['support']['evidence']['path']);et=ast.parse(evidence.read_bytes())
    nodes=[n for n in et.body if isinstance(n,ast.FunctionDef) and n.name in {'need','frame','validate_dispatch'}];ns={'RATE':16000,'math':math}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(evidence),'exec'),ns);guard=ns['validate_dispatch']
    def events(origin):
        return [dict(event_type='source_started',payload=origin),dict(event_type='research_asr_tail_dispatch',payload=dict(source_start_sec=0,source_end_sec=4/16000,samples=4)),dict(event_type='research_asr_drain',payload=dict(source_end_sec=4/16000,padding_is_observed_audio=False,synthetic_right_padding_sec=.66)),dict(event_type='research_scheduler_watermark',payload=dict(lane='asr',lane_closed=True)),dict(event_type='research_scheduler_watermark',payload=dict(lane='speaker',lane_closed=True)),dict(event_type='session_completed',payload={})]
    def produce(which):
        v=admission();published=[]
        class Handle:
            def __init__(self,path):self.done=False
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,*args,**kwargs):
                if self.done:return []
                self.done=True;return [0.]*4
        class Pair:
            committed_samples=0
            error=None
            def append(self,*blocks):equal([len(x) for x in blocks],[4,4,4]);self.committed_samples+=4
            def finish(self,error=None):self.error=error
        pair=Pair();producer=which['CapturedSource'](pair,v,status_callback=lambda k,x:published.append((k,x)),realtime=False)
        with patch.dict(sys.modules,{'soundfile':types.SimpleNamespace(SoundFile=Handle)}):producer._run()
        equal(pair.error,None);equal(pair.committed_samples,4);equal(len(published),1);equal(published[0][0],'source_started');return published[0][1]
    check('actual_producer_one_common_origin_satisfies_bb1b',lambda:equal(guard(iter(events(produce(current))),4)['frames'],4))
    check('preserved_parent_producer_missing_rate_reproduces_failure',lambda:reject(lambda:guard(iter(events(produce(parent))),4)))
    def altered(value,missing=False):
        origin=produce(current)
        if missing:origin.pop('pipeline_sample_rate')
        else:origin['pipeline_sample_rate']=value
        reject(lambda:guard(iter(events(origin)),4))
    check('missing_origin_rate_rejected',lambda:altered(None,True))
    for value in (8000,'16000',None,0):check('wrong_origin_rate_'+repr(value),lambda value=value:altered(value))
    def duplicate():
        e=events(produce(current));reject(lambda:guard(iter(e[:1]+e),4))
    check('duplicate_common_origin_rejected',duplicate)
    def scientific():
        def funcs(path):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(Path(path).read_bytes()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        equal(funcs(plan['runner']['path']),funcs(plan['parent_runner']['path']))
        assert {k for k in funcs(old_source) if funcs(old_source)[k]!=funcs(source)[k]}=={'CaptureAdmission','CapturedSource'}
        equal(bind(evidence)['sha256'],'bb1b5ff846f8edad386b573dea203df7b08e9c31b8126e7c3aa14a8cccb226d2')
    check('wrapper_scientific_functions_and_guard_unchanged',scientific)
    def metadata():
        equal(len(manifest['jobs']),12)
        for j,o in zip(manifest['jobs'],old['jobs']):equal({k:v for k,v in j.items() if k!='output'},{k:v for k,v in o.items() if k!='output'})
        equal(manifest['limits'],old['limits']);equal(manifest['support'],old['support']);assert not Path(plan['fresh_payload_root']).exists()
        for row in plan['source_files']:equal(bind(row['copy']['path']),row['copy'])
        equal(sum(row['copy']['sha256']!=row['original']['sha256'] for row in plan['source_files']),1)
    check('twelve_exact_jobs_fresh_outputs_one_source_change',metadata)
    receipt=dict(status='PASS' if all(x['status']=='PASS' for x in rows) else 'FAIL',passed=sum(x['status']=='PASS' for x in rows),total=len(rows),tests=rows,proposal=bind(a.proposal),fixture=bind(__file__),producer=bind(source),wrapper=plan['runner'],guard=bind(evidence),actual_audio_reads=0,model_calls=0,process_queries=0,device_calls=0,producer_thread_starts=0,old_events_modified=False,root_admission=False)
    (out/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(status=receipt['status'],passed=receipt['passed'],total=receipt['total'],receipt=bind(out/'RECEIPT.json'),failures=[x for x in rows if x['status']=='FAIL'])));return 0 if receipt['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
