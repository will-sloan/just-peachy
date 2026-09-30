"""Changed transport/TRACE native fixtures; README_FIELD_TRANSPORT_OUTPUTS_V1.md."""
import json,hashlib,sys,time,threading
from pathlib import Path
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace
from field_sidecar_budget_v1 import GroupWriter
from field_transport_outputs_v1 import Outputs,sha
from isolated_source_transport_budget_v1 import IsolatedSource,SourceFault
import field_child_deadline_v1 as deadlines

def run(root,a):
    plan=json.loads((root/'FIELD_WHOLE_RUN_ALLOCATION_V2.json').read_text());fixtures=root/'fixtures';fixtures.mkdir();cases=[]
    def record(name,**kw):
        row=dict(case=name,**kw);(root/(name+'-CASE.json')).write_text(json.dumps(row,indent=2,allow_nan=False),encoding='utf-8');cases.append(row)
    def config(name,max_files=16,max_write=65536,mode='empty'):
        d=fixtures/name;d.mkdir();groups={k:deepcopy(plan['sidecar_groups'][k]) for k in ['source','control','failure','closure_reserve','trace','config']}
        groups['source'].update(maximum_files=max_files,maximum_write_bytes=max_write)
        for group in groups:(d/group).mkdir()
        cfg=dict(schema='transport-output-fixture.v1',capture=False,output_root=str(d),admission_path=str(root/'ADMISSION.json'),admission_sha256=sha(root/'ADMISSION.json'),plan_path=str(root/'FIELD_WHOLE_RUN_ALLOCATION_V2.json'),plan_sha256=sha(root/'FIELD_WHOLE_RUN_ALLOCATION_V2.json'),groups=groups,deadline=deadlines.create(a,lifetime=1.2 if mode=='wait' else 10,grace=.3 if mode=='wait' else 2),source_module='field_transport_empty_fixture_v1',source_factory='create',source_mode=mode,backpressure_seconds=1)
        GroupWriter(d/'config',groups['config']).json('CONFIG.json',cfg)
        return d/'config/CONFIG.json'
    for name,options in [('normal',{}),('owner-quota',dict(max_write=1)),('ready-quota',dict(max_files=1)),('result-quota',dict(max_files=2)),('parent-blocked',dict(mode='wait'))]:
        path=config(name,**options);transport=IsolatedSource(path);errors=[];start=time.monotonic_ns()
        try:
            if name=='parent-blocked':time.sleep(1.5)
            end=time.monotonic()+3
            while transport.terminal is None and time.monotonic()<end:
                try:assert transport.read(.02) is None
                except (SourceFault,OSError) as exc:
                    errors.append(str(exc))
                    if transport.terminal is not None or transport.proc.poll() is not None:break
        finally:
            try:transport.close()
            except SourceFault as exc:errors.append(exc.code)
        assert transport.closed and transport.wire.fileno()==-1 and not transport.watcher.is_alive() and transport.proc.poll() is not None
        d=path.parent.parent;closure=d/'closure_reserve/TRANSPORT_CLOSURE.json'
        if name=='normal':
            assert not errors and transport.proc.returncode==0 and closure.exists()
        elif name=='parent-blocked':
            assert transport.proc.returncode==-9 and transport.watch_result['kill_sent'] and not closure.exists()
            assert transport.watch_result['reaped_ns']<=transport.deadline['hard_ns']+500_000_000
            assert 'CHILD_CLOSURE_MISSING' in errors
        else:
            assert transport.proc.returncode==1 and 'CHILD_OUTPUT_OR_FINALIZATION_FAILED' in errors
            c=json.loads(closure.read_text());assert not c['logical_success'] and c['wire_closed']
            if name=='owner-quota':assert not c['source_created']
            else:assert c['source_close']==dict(fixture=True,stops=1,closes=1,no_hardware=True)
            if name=='result-quota':assert transport.terminal['fault'] is None and c['publication_failure']['name']=='CHILD_RESULT.json'
        if closure.exists():
            c=json.loads(closure.read_text());assert c['terminal_sent'] and c['terminal_acknowledged']
            assert c['deadline']==transport.deadline
        assert transport.seq==transport.offset==0
        record(name,returncode=transport.proc.returncode,errors=errors,terminal=transport.terminal,closure=json.loads(closure.read_text()) if closure.exists() else None,watch=transport.watch_result,deadline=transport.deadline,wire_closed=True,watcher_joined=True,elapsed_ns=time.monotonic_ns()-start,layout=transport.outputs.layout())
    # Test only new TRACE adapter and the retained real _error method. The
    # original accept is a counted stub, not a claimed journal/timing/model pass.
    sys.path[:0]=[a['base_release'],str(Path(a['base_release'])/'vendor')]
    from isolated_pipeline_source_v2 import IsolatedPipelineSource
    from field_trace_accept_v1 import traced_accept
    import numpy as np
    @dataclass
    class Block:
        audio:object
        label:str='fixture'
    for name,write_limit,file_limit,ceiling in [('trace-normal',8192,12582912,10),('trace-first-reject',1,12582912,10),('trace-append-reject',8192,240,10),('accepted-limit',8192,12582912,1)]:
        d=fixtures/name;d.mkdir();groups={k:deepcopy(plan['sidecar_groups'][k]) for k in ['source','control','failure','closure_reserve','trace','config']}
        groups['trace'].update(maximum_write_bytes=min(write_limit,file_limit),maximum_file_bytes=file_limit)
        for group in groups:(d/group).mkdir()
        outputs=Outputs(d,groups,plan);source=SimpleNamespace(sent=0,error=None,journal=SimpleNamespace(fatal_error=None),secondary_errors=[],stop_event=threading.Event(),callback=lambda *x:None)
        source._error=lambda exc:IsolatedPipelineSource._error(source,exc)
        def accepted(self,block,ipc):self.sent+=len(block.audio)
        wrapped=traced_accept(accepted,outputs,ceiling);block=Block(np.zeros(2,dtype='float32'))
        wrapped(source,block,{'test':True})
        if name=='trace-append-reject':
            assert source.error is None
            before=(d/'trace/TRACE.jsonl').read_bytes();wrapped(source,block,{'test':True});assert (d/'trace/TRACE.jsonl').read_bytes()==before
        if name=='trace-normal':assert source.error is None and not source.stop_event.is_set()
        else:assert source.error and source.stop_event.is_set()
        if name=='trace-first-reject':assert not (d/'trace/TRACE.jsonl').exists()
        # Accepted count is retained even when TRACE or sample ceiling fails.
        assert source.sent==(4 if name=='trace-append-reject' else 2)
        record(name,sent=source.sent,error=source.error,stop_requested=source.stop_event.is_set(),trace_exists=(d/'trace/TRACE.jsonl').exists(),trace_bytes=(d/'trace/TRACE.jsonl').stat().st_size if (d/'trace/TRACE.jsonl').exists() else 0,original_accept_stub=True,retained_error_method=True)
    (root/'TRANSPORT_OUTPUT_CASES.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
    return dict(status='PASS_TRANSPORT_OUTPUT_AND_TRACE_ADAPTER_FIXTURES_ONLY',cases=len(cases),children=5,expected_child_failures=4,source_audio_samples=0,models=False,capture=False,GUI=False,controller=False,whole_run_integrated=False,policy_changed=False)
