"""Derive an isolated A2 startup-failure check. See README_ASR_FAILURE_V1.md."""
from pathlib import Path
import ast
import hashlib
import json

HERE=Path(__file__).resolve().parent
NAMES={name:name.replace('controls','asr_failure').replace('_v3','_v1') for name in
       ('controls_child_v3.py','controls_harness_v3.py','prepare_controls_v3.py','review_controls_v3.py')}

FAULTS='''            require(a['backend_key']=='nemotron_600m','Only A2 admitted')
            runtime=data/'n3_runtime.json';original=runtime.read_bytes()
            select(a['backend_key'])
            ui.show_advanced();ui.actions['mode_anonymous_conversation'].invoke();idle()
            ui.show_recipes();ui.actions['recipe_balanced'].invoke();idle()
            require(controller.mode=='anonymous_conversation' and controller.recipe=='balanced','Setup differs')
            for case in ('missing_asr_model','runtime_hash_mismatch'):
                document=json.loads(original)
                if case=='missing_asr_model':
                    missing=data/'deliberately-absent-asr.gguf'
                    require(not missing.exists(),'Fault fixture exists')
                    document['variants']['A2']['model_path']=str(missing)
                else:document['variants']['A2']['runtime_files'][0]['sha256']='0'*64
                runtime.write_text(json.dumps(document,indent=2),encoding='utf-8')
                config=output/(case+'-CONFIG.json');freeze(config,document)
                select(a['backend_key'])
                require(controller.error is None and controller.backend_id==selected,'Fault must reach ASR startup')
                controller.start_file(a['audio']['path']);idle();pump(lambda:controller.state=='ERROR')
                observed=check_error(case,selected)
                require(observed['models']==dict(asr_loads=0,speaker_loads=0,streams=0),'Unexpected fallback/model allocation')
                require(controller.models.native_asr is None,'Native ASR allocation leaked')
                expected='deliberately-absent-asr.gguf' if case=='missing_asr_model' else 'Native runtime dependency path/hash mismatch'
                require(expected in observed['error'],'Wrong failure reason')
                controller.stop();idle()
                require(controller.engine is None and controller.consumer is None,'Failed epoch retains ownership')
                cleanup=controller.metrics['last_worker_cleanup']
                require(cleanup['owned_threads_joined'],'Startup-failure workers remain')
                journals=[bind(p) for p in data.rglob('audio_spool.pcm16')]
                require(journals and all(p['bytes']==0 for p in journals),'Audio processed during load failure')
                proof=dict(case=case,config=bind(config),observation=bind(output/(case+'.json')),
                    cleanup=cleanup,native_asr_absent=True,journals=journals)
                freeze(output/(case+'-CLOSURE.json'),proof)
            runtime.write_bytes(original);select(a['backend_key'])
'''

REVIEW='''    require(a['backend_key']=='nemotron_600m','Unexpected backend')
    require([x['case'] for x in c['cases']]==['missing_asr_model','runtime_hash_mismatch'],'Fault cases missing')
    runtime=next(b for b in a['runtime_configs'] if Path(b['path']).name=='n3_runtime.json')
    original=load(runtime['path']);proofs=[]
    import copy
    for x in c['cases']:
        require(x['state']=='ERROR' and x['error'] and x['error'][:120] in x['rendered_error'],'Hidden startup fault')
        require(x['backend_id']==c['backend_id'] and not x['engine_retained'],'Fallback or retained engine')
        require(x['models']==dict(asr_loads=0,speaker_loads=0,streams=0),'Unexpected model or stream allocation')
        case=x['case'];expected=copy.deepcopy(original)
        if case=='missing_asr_model':
            expected['variants']['A2']['model_path']=str(Path(a['data'])/'deliberately-absent-asr.gguf')
            require('deliberately-absent-asr.gguf' in x['error'],'Missing-file fault differs')
        else:
            expected['variants']['A2']['runtime_files'][0]['sha256']='0'*64
            require('Native runtime dependency path/hash mismatch' in x['error'],'Runtime hash fault differs')
        proof_path=run/'controls'/(case+'-CLOSURE.json');proof=load(proof_path)
        verify(proof['config']);verify(proof['observation'])
        require(load(proof['config']['path'])==expected,'Fault changed more than one configuration field')
        require(load(proof['observation']['path'])==x,'Observation mismatch')
        require(proof['native_asr_absent'] and proof['cleanup']['owned_threads_joined'],'Failure not drained')
        require(proof['journals'] and all(b['bytes']==0 for b in proof['journals']),'Unexpected captured/processed samples')
        for b in proof['journals']:verify(b)
        proofs.append(bind(proof_path))
    require(not c['controls'],'Unrelated coverage added')
'''


def main():
    targets=[HERE/n for n in NAMES.values()]+[HERE/'ASR_FAILURE_DERIVATION_V1.json']
    if any(p.exists() for p in targets):raise FileExistsError('Fresh generated paths required')
    receipt=dict(schema='extended-asr-failure-derivation-v1',parents={},outputs={})
    for name,target in NAMES.items():
        path=HERE/name;raw=path.read_bytes()
        receipt['parents'][name]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        text=raw.decode('utf-8')
        for old,new in NAMES.items():text=text.replace(old,new).replace(old[:-3]+' import',new[:-3]+' import')
        text=text.replace('EXTENDED_WINDOWS_CONTROLS_V3','EXTENDED_WINDOWS_ASR_FAILURE_V1')
        text=text.replace('README_CONTROLS_V3.md','README_ASR_FAILURE_V1.md')
        if name=='controls_child_v3.py':
            start=text.index("            runtime=data/'n2_runtime.json'")
            end=text.index("            require(controller.error is None and controller.backend_id==selected,'Recovery selection failed')",start)
            text=text[:start]+FAULTS+text[end:]
        if name=='controls_harness_v3.py':
            text=text.replace("a['backend_key'] in ('nemotron_hybrid','nemotron_600m')","a['backend_key']=='nemotron_600m'")
            text=text.replace('Actual Windows controls, isolated invalid runtime and missing D1 startup, recovery prefix and explicit baseline rollback.',
                              'Actual Windows A2 ASR missing-model and runtime-hash startup failures, recovery prefix and explicit baseline rollback.')
        if name=='prepare_controls_v3.py':
            text=text.replace("choices=['nemotron_hybrid','nemotron_600m']","choices=['nemotron_600m']")
            marker="    code=list({b['path']:b for b in code}.values())"
            text=text.replace(marker,"    code += [bind(HERE/f) for f in ('build_asr_failure_v1.py','ASR_FAILURE_DERIVATION_V1.json','README_ASR_FAILURE_V1.md')]\n"+marker)
        if name=='review_controls_v3.py':
            start=text.index("    require([x['case'] for x in c['cases']]")
            end=text.index("    s=c['recovery'];",start)
            text=text[:start]+REVIEW+text[end:]
            text=text.replace('PASS_WINDOWS_CONTROLS_STARTUP_RECOVERY_ONLY','PASS_WINDOWS_A2_ASR_FAILURE_RECOVERY_ONLY')
            text=text.replace("controls=c['controls'],cases=c['cases']","fault_proofs=proofs,cases=c['cases']")
        ast.parse(text)
        with (HERE/target).open('x',encoding='utf-8',newline='\n') as f:f.write(text)
        data=(HERE/target).read_bytes()
        receipt['outputs'][target]=dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
    with targets[-1].open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2)
    print(dict(status='PREPARED_NOT_EXECUTED',outputs=list(receipt['outputs'])))


if __name__=='__main__':main()
