"""Back up and review the narrowly changed native test helper. See README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid


def main():
    private=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation')
    output=private/('native-helper-review-'+uuid.uuid4().hex);output.mkdir()
    owner=psutil.Process()
    def put(name,value):
        with (output/name).open('x') as stream:
            json.dump(value,stream,sort_keys=True,allow_nan=False);stream.flush();os.fsync(stream.fileno())
    put('REGISTERED_OWNER.json',dict(pid=owner.pid,create_time=owner.create_time(),affinity=[14]))
    started=time.time()
    put('HOST_SCOPE.json',dict(issued_unix=started,maximum_seconds=600,maximum_bytes=2*1024**2,native_action=False))
    here=Path(__file__).resolve().parent
    def definitions(raw):
        result={}
        def visit(nodes,prefix=''):
            for node in nodes:
                if isinstance(node,ast.FunctionDef):result[prefix+node.name]=ast.dump(node,include_attributes=False)
                elif isinstance(node,ast.ClassDef):visit(node.body,prefix+node.name+'.')
        visit(ast.parse(raw).body);return result
    rows=[]
    for name in ('prepare_native_helper_v2.py','native_full_application_check_v3.py','native_full_application_check_v4.py','README.md'):
        source=here/name;raw=source.read_bytes()
        for suffix in ('backup','restore'):
            (output/suffix).mkdir(exist_ok=True);copy=output/suffix/name
            shutil.copyfile(source,copy)
            assert copy.read_bytes()==raw
        if name.endswith('.py'):compile(raw,str(source),'exec')
        rows.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    before=definitions((output/'backup/native_full_application_check_v3.py').read_bytes())
    after=definitions((output/'backup/native_full_application_check_v4.py').read_bytes())
    changed={name for name in before if before[name]!=after.get(name)}
    assert changed=={'ClassicDriver.tick','inside','launch'} and set(before)==set(after)
    total=sum(path.stat().st_size for path in output.rglob('*') if path.is_file())
    assert total<2*1024**2 and time.time()-started<600
    put('SOURCE_CLOSED.json',dict(files=rows,independent_restores=True,closed_unix=time.time(),
        changed_functions=sorted(changed),unchanged_finalize=True,native_action=False,bytes_before_receipt=total))
    print(json.dumps(dict(output=str(output),status='PASS',changed_functions=sorted(changed))))


if __name__=='__main__':main()
