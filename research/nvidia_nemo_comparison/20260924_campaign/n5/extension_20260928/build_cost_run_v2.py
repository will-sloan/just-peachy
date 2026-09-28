"""Repair only a legacy README binding in the admission launcher. README_COST_RUN_V2.md."""
import ast,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent


def main():
    receipt=json.loads((HERE/'COST_RUN_DERIVATION_V1.json').read_text())
    source=HERE/'prepare_cost_run_v1.py';raw=source.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==receipt['outputs'][source.name]['sha256']
    target=HERE/'prepare_cost_run_v2.py';manifest=HERE/'COST_RUN_DERIVATION_V2.json'
    if target.exists() or manifest.exists():raise FileExistsError('Fresh outputs required')
    text=raw.decode('utf-8')
    old="'build_e0_harness_v1.py','README_E0_RUNTIME.md','README_COST_RUN_V1.md')"
    new="'build_e0_harness_v1.py','README_E0_RUNTIME.md','README_E0_RUN.md')"
    assert text.count(old)==1;text=text.replace(old,new)
    text=text.replace("'prepare_cost_run_v1.py'","'prepare_cost_run_v2.py'")
    marker="    code=list({b['path']:b for b in code}.values())"
    assert text.count(marker)==1
    text=text.replace(marker,"    code += [bind(HERE/f) for f in ('prepare_cost_run_v1.py','build_cost_run_v2.py','README_COST_RUN_V2.md','COST_RUN_DERIVATION_V2.json')]\n"+marker)
    text=text.replace('See README_COST_RUN_V1.md.','See README_COST_RUN_V2.md.')
    tree=ast.parse(text)
    for node in ast.walk(tree):
        if not isinstance(node,ast.ListComp) or not isinstance(node.elt,ast.Call):continue
        if not isinstance(node.elt.func,ast.Name) or node.elt.func.id!='bind':continue
        expr=node.elt.args[0]
        if not isinstance(expr,ast.BinOp) or not isinstance(expr.left,ast.Name):continue
        roots={'HERE':HERE,'LEGACY':HERE.parent/'prepi_20260928'}
        if expr.left.id not in roots:continue
        names=ast.literal_eval(node.generators[0].iter)
        for name in names:
            path=roots[expr.left.id]/name
            if path not in (target,manifest) and not path.is_file():raise FileNotFoundError(path)
    with target.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    out=target.read_bytes()
    with manifest.open('x',encoding='utf-8') as f:json.dump(dict(schema='cost-launcher-binding-repair.v2',
        parent=receipt['outputs'][source.name],output=dict(path=target.name,sha256=hashlib.sha256(out).hexdigest(),bytes=len(out)),
        application_changed=False,harness_and_reviewer_changed=False,reason='V1 globally renamed a README inside the preserved LEGACY directory; restore the actual legacy README_E0_RUN.md binding.'),f,indent=2)
    print(dict(status='PREPARED_NOT_RUN',output=target.name))


if __name__=='__main__':main()
