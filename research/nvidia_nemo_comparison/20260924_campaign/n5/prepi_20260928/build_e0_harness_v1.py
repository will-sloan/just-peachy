"""Prepare paired E0-only runtime qualification. See README_E0_RUN.md."""
from pathlib import Path

HERE=Path(__file__).resolve().parent


def once(text, old, new):
    if text.count(old)!=1:raise ValueError('Expected one source anchor: '+old[:80])
    return text.replace(old,new,1)


def main():
    source=(HERE/'shadow_lifecycle_v1.py').read_text(encoding='utf-8')
    source=source.replace('PREPI_WINDOWS_SHADOW_V1','PREPI_WINDOWS_E0_RUNTIME_V1')
    source=source.replace('prepi-shutdown-derivative-v1','prepi-e0-runtime-derivative-v1')
    source=source.replace("['app/controller.py','app/session_shutdown_v1.py']","['app/controller.py','app/n2_models.py']")
    source=once(source,"    require(load(a['parent_source_receipt']['path'])['parent_source_receipt']==a['accepted_source_receipt'],'Accepted ancestry differs')", """    shutdown=load(a['parent_source_receipt']['path'])
    require(shutdown['schema']=='prepi-shutdown-derivative-v1','Shutdown ancestry absent')
    stable=shutdown['parent_source_receipt'];verify(stable)
    require(load(stable['path'])['parent_source_receipt']==a['accepted_source_receipt'],'Accepted ancestry differs')
    runtime=next(row for row in a['runtime_configs'] if Path(row['path']).name=='n2_runtime.json')
    require(not {'titanet_manifest','titanet_manifest_sha256','embedding_namespace'} & set(load(runtime['path'])),'Retired E1 dependency remains in selected runtime')""")
    source=source.replace('See README_SHADOW_RUN.md.', 'See README_E0_RUN.md.')
    source=source.replace('Paired shadow diagnostics with every source sample retained;',
                          'E0 runtime without TitaNet fields; paired shadow diagnostics with every source sample retained;')
    prepare=(HERE/'prepare_shadow_lifecycle_v1.py').read_text(encoding='utf-8')
    prepare=prepare.replace('shadow_lifecycle_v1.py','e0_lifecycle_v1.py')
    prepare=prepare.replace('PREPI_WINDOWS_SHADOW_V1','PREPI_WINDOWS_E0_RUNTIME_V1')
    prepare=once(prepare,"local/'releases/prepi-shutdown-v1/DERIVATIVE.json'", "base/'derivatives/e0-runtime-v1/DERIVATIVE.json'")
    prepare=once(prepare,"    if load(parent['path'])['parent_source_receipt']!=a['accepted_source_receipt']:", """    stable=load(parent['path'])['parent_source_receipt'];verify(stable)
    if load(stable['path'])['parent_source_receipt']!=a['accepted_source_receipt']:""")
    prepare=once(prepare, '    cap=128*1024**2', """    pre.mkdir()
    configs=[]
    for row in a['runtime_configs']:
        document=load(row['path'])
        if Path(row['path']).name=='n2_runtime.json':
            for field in ('titanet_manifest','titanet_manifest_sha256','embedding_namespace'):
                document.pop(field,None)
        path=pre/Path(row['path']).name;freeze(path,document);configs.append(bind(path))
    a['runtime_configs']=configs
    cap=128*1024**2""")
    prepare=once(prepare,"    pre.mkdir();freeze(pre/'CENSUS.json',observed)","    freeze(pre/'CENSUS.json',observed)")
    prepare=once(prepare,"    code += [ref_review,ref_result]", """    code += [bind(HERE/f) for f in ('prepare_e0_runtime_v1.py','test_e0_runtime_v1.py',
        'build_e0_harness_v1.py','README_E0_RUNTIME.md','README_E0_RUN.md')]
    code += [ref_review,ref_result]""")
    prepare=prepare.replace('See README_SHADOW_RUN.md.', 'See README_E0_RUN.md.')
    review=(HERE/'review_shadow_v1.py').read_text(encoding='utf-8')
    review=review.replace('PREPI_WINDOWS_SHADOW_V1','PREPI_WINDOWS_E0_RUNTIME_V1')
    review=review.replace("status='PASS_PREPI_ONE_FILE_WINDOWS_SHADOW_ONLY'", "status='PASS_PREPI_E0_RUNTIME_WINDOWS_SHADOW_ONLY'")
    review=review.replace('See README_SHADOW_REVIEW.md.','See README_E0_RUN.md.')
    review=once(review, "    owners=[a['owner']", """    runtime=next(row for row in a['runtime_configs'] if Path(row['path']).name=='n2_runtime.json')
    require(not {'titanet_manifest','titanet_manifest_sha256','embedding_namespace'} & set(load(runtime['path'])),'Retired E1 fields remain')
    require(load(a['source_receipt']['path'])['schema']=='prepi-e0-runtime-derivative-v1','Wrong source derivative')
    owners=[a['owner']""")
    for name,text in [('e0_lifecycle_v1.py',source),('prepare_e0_lifecycle_v1.py',prepare),('review_e0_lifecycle_v1.py',review)]:
        compile(text,name,'exec')
        with (HERE/name).open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    print('Prepared E0 runtime harness and independent reviewer; no model started.')


if __name__=='__main__':
    import psutil
    psutil.Process().cpu_affinity([14]);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    main()
