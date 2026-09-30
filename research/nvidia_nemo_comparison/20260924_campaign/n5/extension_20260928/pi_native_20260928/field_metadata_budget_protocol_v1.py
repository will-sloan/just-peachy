"""Changed stage transaction fixtures; README_FIELD_METADATA_BUDGET_V1.md."""
from copy import deepcopy
import base64
import json
from pathlib import Path
from field_metadata_budget_v1 import publish_batch,StageFailure
from field_sidecar_budget_v1 import GroupWriter,encoded


def run(root,admission):
    fixtures=root/'fixtures';fixtures.mkdir();rows=[]
    for name in ['mapped-batch','path','code-bytes','file-count','control-bytes','nonfinite','runtime-reserve','runtime-name','interrupted']:
        limits=deepcopy(admission['metadata_limits'])
        batch={'code':{'a.py':b'# alpha\n','b.py':b'# beta\n'},'control':{'CONFIG.json':encoded({'value':'\u00e9 " \\'}),'ADMISSION.json':b'{"admitted":true}'}}
        if name=='path':batch['code']['../escape.py']=b'x'
        if name=='code-bytes':limits['code']['maximum_write_bytes']=1
        if name=='file-count':limits['code']['maximum_files']=1
        if name=='control-bytes':limits['control']['maximum_write_bytes']=1
        if name=='nonfinite':batch['control']['CONFIG.json']=b'{"value":NaN}'
        if name=='runtime-reserve':limits['control'].update(maximum_bytes=128,maximum_file_bytes=64,maximum_write_bytes=64)
        if name=='runtime-name':batch['control']['OWNER.json']=b'{}'
        class InterruptedWriter(GroupWriter):
            def write(self,key,raw,**kwargs):
                if name=='interrupted' and key=='CONFIG.json':
                    # Explicit injected storage fault with preserved partial bytes.
                    with (self.root/(key+'.pending')).open('xb') as f:f.write(raw[:3])
                    raise OSError('injected stage interruption')
                return super().write(key,raw,**kwargs)
        d=fixtures/name;receipt=None;error=None;published=[]
        try:receipt=publish_batch(d,batch,limits,InterruptedWriter)
        except StageFailure as exc:error=str(exc);published=exc.published
        except ValueError as exc:error=str(exc)
        if name=='mapped-batch':
            assert receipt and receipt['admission_last'] and receipt['published'][-1]=='control/ADMISSION.json'
            before={str(p.relative_to(d)):p.read_bytes() for p in d.rglob('*') if p.is_file()}
            try:publish_batch(d,batch,limits)
            except ValueError:pass
            else:raise AssertionError('Existing stage retried')
            assert before=={str(p.relative_to(d)):p.read_bytes() for p in d.rglob('*') if p.is_file()}
        elif name=='interrupted':
            assert error and published==['code/a.py','code/b.py'] and not (d/'control/ADMISSION.json').exists()
            assert (d/'control/CONFIG.json.pending').read_bytes()==batch['control']['CONFIG.json'][:3]
        else:assert error and not d.exists()
        inputs={g:{n:base64.b64encode(raw).decode() for n,raw in files.items()} for g,files in batch.items()}
        (root/(name+'-INPUT.json')).write_bytes(encoded(inputs))
        rows.append(dict(case=name,receipt=receipt,error=error,published=published,directory_created=d.exists()))
    (root/'METADATA_CASES.json').write_bytes(encoded(rows))
    return dict(status='PASS_METADATA_STAGE_AND_RUNTIME_CONTROLS_ONLY',cases=9,prepublication_rejections=7,
                interrupted_stages=1,models=False,capture=False,GUI=False,child_processes=0,source_audio_samples=0,whole_run_integrated=False)
