"""Focused lossless JSON check; README_RUNTIME_ARCHIVE_ENCODING_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,base64,hashlib,json,os
from pathlib import Path
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--private',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();a.output.mkdir();me=psutil.Process()
    (a.output/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])),encoding='utf-8')
    from field_runtime_archive_encoding_v1 import derive
    original=(a.private/'field-runtime-v4-install/stage-backup/field-runtime-v4-profiles/COMMON_BUNDLE.json').read_bytes()
    changed,review=derive(original);bundle=json.loads(changed);raw=base64.b64decode(bundle['files']['code/field_archive_budget_v4.py'])
    tree=ast.parse(raw);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='encode_control')
    ns={'json':json};exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-changed-serializer>','exec'),ns)
    encode=ns['encode_control'];rows=[]
    root=a.private/'field-operator-sessions-v6-admission/host-backup-mirror/recordings'
    paths=sorted(root.glob('slot-*/data/conversations/*/epochs/*/epoch.json'))
    if len(paths)!=2:raise ValueError('Two actual historical session metadata files required')
    for path in paths:
        original_metadata=path.read_bytes();v=json.loads(original_metadata)
        compact=encode(v,65536);pretty=(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
        assert json.loads(compact)==v and path.read_bytes()==original_metadata
        rows.append(dict(source=str(path),source_sha256=hashlib.sha256(original_metadata).hexdigest(),pretty_bytes=len(pretty),compact_bytes=len(compact),complete_value_equal=True))
    # Byte bounds apply to encoded UTF-8, without truncation or field deletion.
    probe={'text':'é'*20,'values':[1,0.5,True,None]};b=encode(probe,65536);assert json.loads(b)==probe
    rejects=0
    for v,limit in ((probe,len(b)-1),({'bad':float('nan')},65536),({'bad':float('inf')},65536)):
        try:encode(v,limit)
        except ValueError:rejects+=1
        else:raise AssertionError('Required unchanged byte/finite rejection')
    result=dict(status='PASS_CHANGED_LOSSLESS_ARCHIVE_SERIALIZER',actual_metadata_roundtrips=rows,synthetic_boundary_rejects=rejects,derivation=review,native_executed=False)
    (a.output/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
if __name__=='__main__':main()

