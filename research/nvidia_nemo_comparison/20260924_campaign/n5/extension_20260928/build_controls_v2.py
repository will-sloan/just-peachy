"""Bind unchanged controls assertions to the error-priority derivative. README_UI_ERROR_V1.md."""
from pathlib import Path
import ast
import hashlib
import json

HERE=Path(__file__).resolve().parent


def main():
    names=['controls_harness_v1.py','controls_child_v1.py','prepare_controls_v1.py','review_controls_v1.py']
    receipt={'schema':'extended-controls-v2-derivation','parents':{},'outputs':{}}
    source={}
    for name in names:
        p=HERE/name;receipt['parents'][name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
        source[name]=p.read_text(encoding='utf-8')
    for name,text in source.items():
        for old in names:text=text.replace(old,old.replace('_v1.py','_v2.py'))
        text=text.replace('from controls_harness_v1 import','from controls_harness_v2 import').replace('from controls_child_v1 import','from controls_child_v2 import')
        text=text.replace('EXTENDED_WINDOWS_CONTROLS_V1','EXTENDED_WINDOWS_CONTROLS_V2')
        text=text.replace('README_CONTROLS_V1.md','README_UI_ERROR_V1.md')
        if name=='controls_child_v1.py':
            text=text.replace("result['fault_config']=bind(runtime);freeze(output/'FAULT_CONFIG.json',document)",
                "freeze(output/'FAULT_CONFIG.json',document);result['fault_config']=bind(output/'FAULT_CONFIG.json')")
        if name=='prepare_controls_v1.py':
            text=text.replace("base/'derivatives/e0-runtime-v1/DERIVATIVE.json'","local/'n5/research-extension-20260928/derivatives/ui-error-v1/DERIVATIVE.json'")
            text=text.replace("parent=d['parent_source_receipt'];verify(parent)","verify(d['parent_source_receipt']);parent=d['e0_shutdown_parent'];verify(parent)")
            text=text.replace("    code=list({b['path']:b for b in code}.values())","    code += [bind(HERE/f) for f in ('build_controls_v2.py','CONTROLS_DERIVATION_V2.json','build_ui_error_v1.py','README_UI_ERROR_V1.md')]\n    code=list({b['path']:b for b in code}.values())")
        if name=='controls_harness_v1.py':
            marker="    d=load(a['source_receipt']['path'])\n"
            text=text.replace(marker,marker+"    require(d['schema']=='extended-ui-error-priority-v1' and d['changed_code']==['app/ui.py'],'Unexpected GUI derivative')\n    verify(d['parent_source_receipt']);d=load(d['parent_source_receipt']['path'])\n")
        if name=='review_controls_v1.py':
            marker="    owners=[a['owner'],"
            text=text.replace(marker,"    d=load(a['source_receipt']['path']);require(d['schema']=='extended-ui-error-priority-v1' and d['changed_code']==['app/ui.py'],'Unexpected GUI derivative')\n    verify(d['parent_source_receipt'])\n"+marker)
        ast.parse(text);target=HERE/name.replace('_v1.py','_v2.py')
        with target.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
        receipt['outputs'][target.name]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size}
    with (HERE/'CONTROLS_DERIVATION_V2.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2)
    print({'status':'PREPARED_NOT_TESTED','files':list(receipt['outputs'])})


if __name__=='__main__':main()
