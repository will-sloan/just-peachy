"""Adapt exact selected ZIP publication peers. See README_DELIVERY_ACTIONS.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def main():
    here=Path(__file__).resolve().parent
    private=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
    out=private/'audit-preparation'/('export-peer-adapter-'+uuid.uuid4().hex);out.mkdir()
    me=psutil.Process();started=time.time()
    def put(name, raw):
        with (out/name).open('xb') as stream:
            assert stream.write(raw)==len(raw);stream.flush();os.fsync(stream.fileno())
        assert (out/name).read_bytes()==raw
    put('REGISTERED_OWNER.json',json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])).encode())
    put('HOST_SCOPE.json',json.dumps(dict(issued_unix=started,maximum_seconds=600,maximum_bytes=2*1024**2)).encode())
    original=(here/'launch_full_recording_export_action_v1.py').read_bytes()
    tree=ast.parse(original);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='export_wrapper')
    replacement='''def export_wrapper(shared,settings):
    """Retain build21's bound checks and conservatively charge both ZIP names."""
    source=shared(settings)
    boundary="    peer=path.with_name(name[:-8]) if name.endswith('.pending') and len(name)>8 else path.with_name(name+'.pending')"
    changed="""    archive=(path.parent==out and (name=='selected-recording.zip' or
      name.startswith('selected-recording.zip.part-') and len(name)==60 and all(c in '0123456789abcdef' for c in name[-32:])))
    if archive:
     if name!='selected-recording.zip':peer=out/'selected-recording.zip'
     else:
      candidates=[p for p in out.iterdir() if p.name.startswith('selected-recording.zip.part-')
       and len(p.name)==60 and all(c in '0123456789abcdef' for c in p.name[-32:])]
      if len(candidates)>1:fail('ambiguous_selected_zip_peer',path,info)
      peer=candidates[0] if candidates else out/'selected-recording.zip.absent-peer'
    else:
     peer=path.with_name(name[:-8]) if name.endswith('.pending') and len(name)>8 else path.with_name(name+'.pending')"""
    if source.count(boundary)!=1:raise ValueError('Exact build21 publication-peer boundary required')
    source=source.replace(boundary,changed)
    compile(source,'<full-selected-export-wrapper>','exec')
    return source
'''
    lines=original.decode().splitlines(keepends=True);lines[node.lineno-1:node.end_lineno]=[replacement]
    result=''.join(lines).encode();compile(result,'<full-export-v2>','exec')
    before={n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)}
    after={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(result).body if isinstance(n,ast.FunctionDef)}
    assert set(before)==set(after) and {n for n in before if before[n]!=after[n]}=={'export_wrapper'}
    for name,raw in [('ORIGINAL.py',original),('ACTION.py',result),('ACTION.restore.py',result),('README.md',(here/'README_DELIVERY_ACTIONS.md').read_bytes()),('PREPARER.py',Path(__file__).read_bytes())]:put(name,raw)
    target=here/'launch_full_recording_export_action_v2.py'
    with target.open('xb') as stream:assert stream.write(result)==len(result);stream.flush();os.fsync(stream.fileno())
    assert target.read_bytes()==result and sum(p.stat().st_size for p in out.iterdir())<2*1024**2 and time.time()-started<600
    put('SOURCE_CLOSED.json',json.dumps(dict(status='PASS',independent_restore=True,sha256=hashlib.sha256(result).hexdigest(),changed_functions=['export_wrapper'],native_action=False,closed_unix=time.time())).encode())
    print(json.dumps(dict(status='PASS',output=str(out),target=str(target))))


if __name__=='__main__':main()
