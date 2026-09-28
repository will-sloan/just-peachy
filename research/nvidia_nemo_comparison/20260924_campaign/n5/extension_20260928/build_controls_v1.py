"""Derive a bounded private-desktop startup/control experiment. README_CONTROLS_V1.md."""
from pathlib import Path
import ast
import hashlib
import json

HERE=Path(__file__).resolve().parent


def main():
    parents={}
    def read(name):
        p=HERE/name;parents[name]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
        return p.read_text(encoding='utf-8')
    base=read('early_stop_lifecycle_v2.py');launcher=read('prepare_early_stop_v2.py')
    if parents['early_stop_lifecycle_v2.py']['sha256']!='3f13b7375279bc8d1576392706fcbe7f79697b5380c2198df5c320daae7d5fad':raise ValueError('Unexpected harness parent')
    if parents['prepare_early_stop_v2.py']['sha256']!='11e92c51bd7ef1b9f6caf7ceb042a8046e933e12fa050918c19c84382751f5f2':raise ValueError('Unexpected launcher parent')
    prefix=base[:base.index('def acceptance(')]
    tail=base[base.index('def output_bytes('):]
    tail=tail.replace("for phase in ('infer','reopen'):","for phase in ('controls',):")
    tail=tail.replace("            if phase=='infer':\n                bypass_acceptance(result,a['arm'],load(a['reference_inputs'][1]['path']) if a['arm']=='candidate' else None)\n",'')
    tail=tail.replace("choices=['infer','reopen']","choices=['controls']")
    start=tail.index("        scope='Early Stop,");end=tail.index('\n        microphone=',start)
    tail=tail[:start]+"        scope='Actual Windows controls, isolated invalid runtime and missing D1 startup, recovery prefix and explicit baseline rollback. Not complete mode or release acceptance.',"+tail[end:]
    tail=tail.replace('PASS_NEMOTRON_WINDOWS_LIFECYCLE_SMOKE','PASS_WINDOWS_CONTROLS_SMOKE')
    middle='''from controls_child_v1 import child


def acceptance(result, lifetime):
    require(result['status']=='PASS_CONTROLS_PHASE' and not result['errors'],'Controls phase failed')
    require(result['controller_closed'] and result['worker_alive'] is False and result['lock_released'],'Controller did not close')
    require(result['baseline_rollback'] and result['sentinel_preserved'] and result['saved_audio_only'],'Isolation/rollback failed')
    require(lifetime['status']=='OWNED_PROCESS_LIFETIME_CLOSED' and not lifetime['forced']
        and lifetime['job_empty_verified'] and lifetime['root_exit_code']==0 and lifetime['observed_members_exited'],'Process closure failed')


'''
    harness=prefix+middle+tail
    names={'early_stop_lifecycle_v2.py':'controls_harness_v1.py','prepare_early_stop_v2.py':'prepare_controls_v1.py',
        'review_early_stop_v2.py':'review_controls_v1.py','README_EARLY_STOP_V2.md':'README_CONTROLS_V1.md',
        'EXTENDED_WINDOWS_STOP_NEW_RESTART_V2':'EXTENDED_WINDOWS_CONTROLS_V1'}
    for a,b in names.items():harness=harness.replace(a,b);launcher=launcher.replace(a,b)
    marker="    code=list({b['path']:b for b in code}.values())"
    launcher=launcher.replace(marker,"    code += [bind(HERE/f) for f in ('controls_child_v1.py','build_controls_v1.py','CONTROLS_DERIVATION_V1.json','early_stop_lifecycle_v2.py')]\n"+marker)
    outputs={'controls_harness_v1.py':harness,'prepare_controls_v1.py':launcher}
    for name,source in outputs.items():
        ast.parse(source);p=HERE/name
        with p.open('x',encoding='utf-8',newline='\n') as f:f.write(source)
    receipt=dict(schema='extended-controls-derivative-v1',parents=parents,outputs={name:dict(sha256=hashlib.sha256((HERE/name).read_bytes()).hexdigest(),bytes=(HERE/name).stat().st_size) for name in outputs})
    with (HERE/'CONTROLS_DERIVATION_V1.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2)
    print({'status':'PREPARED_NOT_EXECUTED','outputs':list(outputs)})


if __name__=='__main__':main()
