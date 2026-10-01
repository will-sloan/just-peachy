"""Read-only two-recording history check; README_FIELD_OPERATOR_BROKER_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
import sys
sys.dont_write_bytecode=True
import argparse
from pathlib import Path
import json
import hashlib
import shutil
import threading
import time
import traceback
from datetime import datetime,timezone

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed-release',type=Path,required=True)
    parser.add_argument('--saved-root',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if len(args.saved_root)!=2 or args.saved_root[0].resolve()==args.saved_root[1].resolve():
        raise ValueError('Two distinct closed mirrors')
    args.output.mkdir(exist_ok=False)
    me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    (args.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(owner))
    if shutil.disk_usage('C:/').free<50*1024**3 or shutil.disk_usage('G:/').free<75*1024**3:
        raise RuntimeError('Host disk floor')
    timer=threading.Timer(60,lambda:os._exit(124));timer.daemon=True;timer.start()
    began=time.monotonic()
    try:
        from field_operator_history_v1 import History,census,reading
        from field_operator_session_ledger_v2 import file_pin
        manifest='274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0'
        reader=History(args.installed_release,manifest)
        results=[];descriptors=[]
        for index,root in enumerate(args.saved_root,1):
            folders=list((root/'data/conversations').iterdir())
            if len(folders)!=1:raise ValueError('One closed saved conversation per supplied mirror')
            folder=folders[0];before=census(folder)
            descriptor=dict(slot='slot-%02d'%index,root=str(root),conversation_id=folder.name,
                            metadata_pin=file_pin(folder/'conversation.json'))
            value=reader.open(descriptor)
            if value['member_pins']!=before or census(folder)!=before or value['capture_started'] or value['constructor_called']:
                raise AssertionError('Historical payload/ownership contract')
            descriptors.append(descriptor)
            results.append(dict(slot=descriptor['slot'],source_root=str(root),members=len(before),
                bytes=sum(r['bytes'] for r in before.values()),caption_rows=len(value['rows']),
                actual_installed_consumer=True,all_hashes_unchanged=True))
        rejects=[]
        def reject(label,fn):
            try:fn()
            except (ValueError,PermissionError,FileNotFoundError):rejects.append(label)
            else:raise AssertionError('Expected reject: '+label)
        d=descriptors[0]
        reject('descriptor-shape',lambda:reader.open({**d,'unbound':True}))
        reject('identifier-traversal',lambda:reader.open({**d,'conversation_id':'../escape'}))
        reject('stale-metadata-pin',lambda:reader.open({**d,'metadata_pin':dict(bytes=1,sha256='0'*64)}))
        reject('wrong-release-pin',lambda:History(args.installed_release,'0'*64))
        forbidden=args.output/'FORBIDDEN'
        with reading():
            reject('audit-write',lambda:forbidden.open('wb'))
            reject('audit-mkdir',lambda:forbidden.mkdir())
            reject('audit-launch',lambda:__import__('subprocess').Popen([sys.executable,'-V']))
        if forbidden.exists():raise AssertionError('Audit rejection mutated filesystem')
        receipt=dict(status='PASS_TWO_RETAINED_RECORDING_HISTORY_READS_HOST_ONLY',owner=owner,
            sources=results,rejects=rejects,native_execution=False,gui_execution=False,
            capture_or_model_started=False,store_constructor_called=False,
            nonempty_caption_proof=any(r['caption_rows'] for r in results),
            seconds=time.monotonic()-began,ended_utc=datetime.now(timezone.utc).isoformat())
        raw=json.dumps(receipt,indent=2,allow_nan=False).encode()
        if len(raw)>65536:raise RuntimeError('Check receipt cap')
        (args.output/'REVIEW.json').open('xb').write(raw)
        print(json.dumps({k:receipt[k] for k in ('status','sources','rejects','seconds')}))
    except BaseException:
        (args.output/'FAILURE.txt').open('x',encoding='utf-8').write(traceback.format_exc()[:65536])
        raise
    finally:timer.cancel()
if __name__=='__main__':main()
