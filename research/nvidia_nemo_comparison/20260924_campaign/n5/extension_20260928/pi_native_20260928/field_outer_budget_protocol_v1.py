"""Changed outer-output failures only; README_FIELD_OUTER_BUDGET_V1.md."""
from copy import deepcopy
import json
from pathlib import Path
from field_outer_budget_v1 import OuterOutputs, descriptor, create_layout, sha
from field_sidecar_budget_v1 import encoded


def run(root,admission):
    base=json.loads((root/'OUTER_DESCRIPTOR.json').read_bytes());rows=[]
    fixtures=root/'fixtures';fixtures.mkdir()
    cases=['log-first','log-append-tail','resource','result','dispatch','diagnostic','closure','stop-error','nonfinite']
    for name in cases:
        v=deepcopy(base);events=[];inputs=[]
        if name in ['log-first','diagnostic','stop-error']:v['groups']['logs']['maximum_write_bytes']=2
        if name=='log-append-tail':
            v['groups']['logs']['maximum_write_bytes']=8;v['groups']['logs']['maximum_file_bytes']=8
        if name=='resource':v['groups']['telemetry']['maximum_write_bytes']=2
        if name in ['result','dispatch']:v['groups']['receipts']['maximum_write_bytes']=2
        if name=='diagnostic':v['groups']['failure']['maximum_write_bytes']=2
        if name=='closure':v['groups']['closure_reserve']['maximum_write_bytes']=2
        p=root/(name+'-DESCRIPTOR.json');p.write_bytes(encoded(v));d=fixtures/name
        create_layout(d,descriptor(p,sha(p),admission))
        def stop():
            events.append('stop')
            assert not list((d/'failure').glob('*-rejected.bin'))
            if name=='stop-error':raise RuntimeError('counted Stop failure')
        sink=OuterOutputs(d,p,sha(p),admission,'fixture',stop)
        if name=='closure':
            assert sink.emit('result',{'status':'fixture'})
        elif name=='nonfinite':assert not sink.emit('resource',{'value':float('nan')})
        else:
            site={'resource':'resource','result':'result','dispatch':'dispatch'}.get(name,'log')
            value=b'REJECTED' if site=='log' else {'value':'Unicode \u00e9 " \\'}
            if name=='log-append-tail':assert sink.emit('log',b'old')
            inputs.append(value if site=='log' else encoded(value)+(b'\n' if site=='resource' else b''))
            assert not sink.emit(site,value)
            if name=='log-append-tail':
                inputs.append(b'TAIL');assert not sink.emit('log',b'TAIL')
                assert (d/'logs/service.log').read_bytes()==b'old'
            if site in {'result','dispatch'}:
                try:sink.emit(site,value)
                except RuntimeError:pass
                else:raise AssertionError('Failed receipt retried')
        outcome=sink.finish(True,0)
        assert not outcome['logical_success']
        assert events==([] if name=='closure' else ['stop'])
        before={str(p.relative_to(d)):sha(p) for p in d.rglob('*') if p.is_file()}
        changed=sink.finish(True,0);changed['logical_success']=True
        assert sink.finish(True,0)==outcome
        assert before=={str(p.relative_to(d)):sha(p) for p in d.rglob('*') if p.is_file()}
        if name=='diagnostic':assert not outcome['raw_retention_complete'] and outcome['retained_rejected_bytes']==0
        elif inputs:assert (d/'failure/fixture-rejected.bin').read_bytes()==b''.join(inputs)
        if name=='closure':assert not outcome['closure_retained']
        else:assert outcome['closure_retained']
        if name=='stop-error':assert outcome['stop_error']
        if name=='nonfinite':assert outcome['failure']['error_type']=='ValueError' and outcome['rejected_bytes']==0
        # Independent fixture input retention, even when sink's reserve rejects.
        (root/(name+'-INPUT.bin')).write_bytes(b''.join(inputs))
        rows.append(dict(case=name,outcome=outcome,stop_calls=len(events)))
    (root/'OUTER_CASES.json').write_bytes(encoded(rows))
    return dict(status='PASS_OUTER_OUTPUT_FAILURE_FIXTURES_ONLY',cases=len(rows),models=False,capture=False,GUI=False,
                child_processes=0,source_audio_samples=0,whole_run_integrated=False)
