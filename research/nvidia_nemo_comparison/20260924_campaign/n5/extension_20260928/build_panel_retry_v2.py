"""Fresh catalog-binding correction and actual-catalog regression checks. README_PANEL_RETRY_V2.md."""
from copy import deepcopy
from pathlib import Path
import ast
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'n4'))
from common import bind,freeze,load
from metric_process import pin
from panel_catalog_v1 import rebind_gallery


def main():
    pin();local=HERE.parent.parents[4]/'local';base=local/'n5/research-extension-20260928'
    old=HERE/'panel_retry_v1.py';target=HERE/'panel_retry_v2.py'
    if target.exists():raise FileExistsError(target)
    plan=load(local/'n4/paced-plan-guarded-v2/PLAN.json')
    gallery=load(plan['context']['gallery_preparation']['path']);oc=load(gallery['catalog']['path'])
    nb=bind(base/'derivatives/panel-journal-v1/prototype/config/backends.json');nc=load(nb['path']);proofs=[]
    for backend in ('nemotron_hybrid','nemotron_600m'):
        contract=next(r['contract'] for r in plan['rows'] if r['contract']['backend_key']==backend)
        rebound,proof=rebind_gallery(gallery,oc,nc,nb,backend,contract);proofs.append(dict(backend=backend,proof=proof))
        assert {k:v for k,v in rebound.items() if k!='catalog'}=={k:v for k,v in gallery.items() if k!='catalog'}
        for mutate in ('label','streaming_profile','duplicate'):
            bad=deepcopy(nc);row=next(r for r in bad['backends'] if r['key']==backend)
            if mutate=='label':row['label']='changed'
            elif mutate=='streaming_profile':row['composition']['n2']['streaming_profile']='ultra_low_latency'
            else:bad['backends'].append(deepcopy(row))
            try:rebind_gallery(gallery,oc,bad,nb,backend,contract)
            except ValueError:pass
            else:raise AssertionError('Accepted mutation '+mutate)
    freeze(base/'A0_PANEL_RETRY_V1_PREFLIGHT_FAILURE.json',dict(status='FAILED_BEFORE_DISPATCH',
        error='Catalog bytes changed',runner=bind(old),new_catalog=nb,old_catalog=gallery['catalog'],numerical_worker_started=False))
    text=old.read_text(encoding='utf-8')
    before="    require({k:v for k,v in gallery['catalog'].items() if k!='path'} == {k:v for k,v in catalog.items() if k!='path'}, 'Catalog bytes changed')\n    gallery = deepcopy(gallery); gallery['catalog'] = catalog"
    after="    from panel_catalog_v1 import rebind_gallery\n    gallery, catalog_proof = rebind_gallery(gallery, load(gallery['catalog']['path']), load(catalog['path']), catalog, backend, contract)"
    assert text.count(before)==1;text=text.replace(before,after)
    text=text.replace("'panel_retry_v1.py','build_panel_source_v1.py'", "'panel_retry_v1.py','panel_retry_v2.py','panel_catalog_v1.py','build_panel_retry_v2.py','README_PANEL_RETRY_V2.md','build_panel_source_v1.py'")
    text=text.replace('original_plan=plan_binding, original_cell_id=', 'catalog_rebinding=catalog_proof, original_plan=plan_binding, original_cell_id=')
    text=text.replace('README_PANEL_RETRY_V1.md.\"\"\"','README_PANEL_RETRY_V2.md.\"\"\"',1)
    ast.parse(text);target.write_text(text,encoding='utf-8',newline='\n')
    freeze(base/'CATALOG_REBIND_V2.json',dict(status='PASS_SELECTED_CATALOG_GUARD',positive_checks=2,negative_checks=6,
        proofs=proofs,parent=bind(old),child=bind(target),code=[bind(HERE/f) for f in ('panel_catalog_v1.py','build_panel_retry_v2.py','README_PANEL_RETRY_V2.md')]))
    print(dict(status='PASS_SELECTED_CATALOG_GUARD',positive=2,negative=6,proofs=proofs))


if __name__=='__main__':main()
