"""Correct controls-test navigation without changing the app. README_CONTROLS_V3.md."""
from pathlib import Path
import ast
import hashlib
import json

HERE=Path(__file__).resolve().parent


def main():
    names=['controls_harness_v2.py','controls_child_v2.py','prepare_controls_v2.py','review_controls_v2.py']
    receipt={'schema':'extended-controls-v3-derivation','parents':{},'outputs':{}}
    for name in names:
        p=HERE/name;receipt['parents'][name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
        text=p.read_text(encoding='utf-8')
        for old in names:text=text.replace(old,old.replace('_v2.py','_v3.py'))
        text=text.replace('from controls_harness_v2 import','from controls_harness_v3 import').replace('from controls_child_v2 import','from controls_child_v3 import')
        text=text.replace('EXTENDED_WINDOWS_CONTROLS_V2','EXTENDED_WINDOWS_CONTROLS_V3')
        text=text.replace('README_UI_ERROR_V1.md','README_CONTROLS_V3.md')
        if name=='controls_child_v2.py':
            old="                ui.show_modes();ui.actions['mode_'+mode].invoke();idle()"
            assert text.count(old)==1
            text=text.replace(old,"                if mode=='anonymous_conversation':ui.show_advanced()\n                else:ui.show_modes()\n                ui.actions['mode_'+mode].invoke();idle()")
        if name=='prepare_controls_v2.py':
            marker="    code=list({b['path']:b for b in code}.values())"
            text=text.replace(marker,"    code += [bind(HERE/f) for f in ('build_controls_v3.py','CONTROLS_DERIVATION_V3.json','README_CONTROLS_V3.md')]\n"+marker)
        ast.parse(text);target=HERE/name.replace('_v2.py','_v3.py')
        with target.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
        receipt['outputs'][target.name]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size}
    with (HERE/'CONTROLS_DERIVATION_V3.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2)
    print({'status':'PREPARED_NOT_TESTED','files':list(receipt['outputs'])})


if __name__=='__main__':main()
