"""Derive a full-file cost/parity run without repeating prefix tests. README_COST_RUN_V1.md."""
from pathlib import Path
import ast,hashlib,json
HERE=Path(__file__).resolve().parent
LEGACY=HERE.parent/'prepi_20260928'


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Parent anchor differs: '+old[:90])
    return text.replace(old,new,1)


def main():
    inputs={'cost_lifecycle_v1.py':LEGACY/'e0_lifecycle_v1.py',
            'review_cost_run_v1.py':LEGACY/'review_e0_lifecycle_v1.py',
            'prepare_cost_run_v1.py':HERE/'prepare_controls_v3.py'}
    targets=[HERE/n for n in inputs]+[HERE/'COST_RUN_DERIVATION_V1.json']
    if any(p.exists() for p in targets):raise FileExistsError('Generated outputs already exist')
    parents={};outputs={}
    for name,path in inputs.items():
        raw=path.read_bytes();parents[str(path)]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        s=raw.decode('utf-8')
        s=s.replace('PREPI_WINDOWS_E0_RUNTIME_V1','EXTENDED_WINDOWS_COSTS_V1').replace('EXTENDED_WINDOWS_CONTROLS_V3','EXTENDED_WINDOWS_COSTS_V1')
        s=s.replace('README_E0_RUN.md','README_COST_RUN_V1.md').replace('README_CONTROLS_V3.md','README_COST_RUN_V1.md')
        if name=='cost_lifecycle_v1.py':
            s=once(s,'HERE = CODE.parent',"HERE = CODE.parent\nsys.path.append(str(HERE/'prepi_20260928'))")
            s=once(s,"    require(d['schema']=='prepi-e0-runtime-derivative-v1' and d['parent_source_receipt']==a['parent_source_receipt'],'Shutdown ancestry differs')", """    require(d['schema']=='extended-component-costs-v1','Wrong cost derivative')
    verify(d['parent_source_receipt']);ui=load(d['parent_source_receipt']['path'])
    require(ui['schema']=='extended-ui-error-priority-v1','UI ancestry missing')
    verify(ui['parent_source_receipt']);e0=load(ui['parent_source_receipt']['path'])
    require(e0['schema']=='prepi-e0-runtime-derivative-v1' and e0['parent_source_receipt']==a['parent_source_receipt'],'Shutdown ancestry differs')""")
            s=once(s,"    require(d['changed_code']==['app/controller.py','app/n2_models.py'],'Unexpected source mutation')",
                "    require(d['changed_code']==['app/n2_pipeline.py','app/n3_pipeline.py','app/pipeline.py','vendor/edge_speech_pipeline/runtime.py'],'Unexpected cost source mutation')")
            s=once(s,'                identifier=controller.conversation_id',"""                result['native_activity_frame_end']=engine._n2_timeline.next_frame
                result['asr_quantum_samples']=round(controller.config.sample_rate*controller.config.journal_read_ms/1000)
                result['component_summary']=bind(Path(telemetry['session_dir'])/'session_summary.json')
                from cost_protocol_v1 import validate_costs
                costs=validate_costs(result,load(result['component_summary']['path']))
                freeze(output/'COSTS.json',costs);result['costs']=bind(output/'COSTS.json')
                identifier=controller.conversation_id""")
        elif name=='review_cost_run_v1.py':
            s=s.replace("=='prepi-e0-runtime-derivative-v1'","=='extended-component-costs-v1'")
            s=once(s,"            t=result['telemetry']", """            t=result['telemetry']
            verify(result['component_summary']);verify(result['costs'])
            from cost_protocol_v1 import validate_costs
            costs=validate_costs(result,load(result['component_summary']['path']))
            require(costs==load(result['costs']['path']),'Cost receipt differs from cumulative data')""")
            s=once(s,"summary=dict(shadow=shadow_summary,", "summary=dict(costs=costs,cost_receipt=result['costs'],component_summary=result['component_summary'],shadow=shadow_summary,")
            s=s.replace('PASS_PREPI_E0_RUNTIME_WINDOWS_SHADOW_ONLY','PASS_WINDOWS_CUMULATIVE_COSTS_FULL_FILE_PARITY')
            s=s.replace('Paired one-file 1x saved-source Windows shadow proposals with unchanged PCM, captions/timestamps and native activity; no audio skipping or inference saving',
                'One 1x saved file: cumulative targeted call costs, exact PCM/caption/time/activity parity, render/save/reopen/delete and owner closure; not sustained or CM5 qualification')
        else:
            s=s.replace('/derivatives/ui-error-v1/','/derivatives/component-costs-v1/')
            for old,new in [('controls_harness_v3.py','cost_lifecycle_v1.py'),('prepare_controls_v3.py','prepare_cost_run_v1.py'),('review_controls_v3.py','review_cost_run_v1.py')]:s=s.replace(old,new)
            marker="    code=list({b['path']:b for b in code}.values())"
            s=once(s,marker,"""    code += [bind(HERE/f) for f in ('build_component_costs_v1.py','component_costs_v1.py','test_component_costs_v1.py',
        'README_COMPONENT_COSTS_V1.md','cost_protocol_v1.py','build_cost_run_v1.py','COST_RUN_DERIVATION_V1.json','README_COST_RUN_V1.md')]
"""+marker)
        ast.parse(s,filename=name);outputs[name]=s
    for name,text in outputs.items():
        with (HERE/name).open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    receipt=dict(schema='extended-cumulative-cost-run-derivation-v1',parents=parents,
        outputs={name:dict(sha256=hashlib.sha256((HERE/name).read_bytes()).hexdigest(),bytes=(HERE/name).stat().st_size) for name in outputs})
    with targets[-1].open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
    print(dict(status='PREPARED_NOT_RUN',outputs=list(outputs)))


if __name__=='__main__':main()
